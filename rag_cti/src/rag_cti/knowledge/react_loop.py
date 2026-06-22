"""Shared ReAct-style tool loop used by agentic gatherers and supervisors."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from typing import Any

from langchain_core.messages import ToolMessage

from rag_cti._logging import get_logger

logger = get_logger(__name__)

TRIMMED_OBSERVATION_STUB = "[observation trimmed — see GATHERED STATE]"
DEADLINE_OBSERVATION_STUB = "[observation skipped — wall-clock budget reached]"

ToolDispatch = Callable[[str, dict[str, Any]], Any]


def mask_stale_observations(messages: list[Any], keep_last: int) -> list[Any]:
    """Mask old ToolMessage contents while preserving tool_call_id pairing."""
    if keep_last <= 0:
        return messages
    tool_idxs = [i for i, m in enumerate(messages) if isinstance(m, ToolMessage)]
    if len(tool_idxs) <= keep_last:
        return messages
    stale = set(tool_idxs[:-keep_last])
    return [
        m.model_copy(update={"content": TRIMMED_OBSERVATION_STUB}) if i in stale else m
        for i, m in enumerate(messages)
    ]


def run_react_tool_loop(
    model: Any,
    dispatch: ToolDispatch,
    messages: list[Any],
    *,
    max_steps: int,
    deadline: float | None = None,
    on_model_error: Callable[[BaseException], None] | None = None,
    model_error_observation: Callable[[BaseException], str] | None = None,
    render_state: Callable[[], str] | None = None,
    keep_last_observations: int = 0,
    parallel_dispatch: bool = False,
    max_parallel_tools: int = 1,
    limiter: Any | None = None,
) -> list[Any]:
    """Drive a chat model's tool-call loop and return the accumulated transcript.

    The loop preserves the required AIMessage(tool_calls) -> ToolMessage pairing, can
    dispatch independent tool calls concurrently, and stops cleanly on provider errors or
    wall-clock deadline exhaustion.
    """

    def run_one(call: dict[str, Any]) -> Any:
        if deadline is not None and time.monotonic() >= deadline:
            return ToolMessage(
                content=DEADLINE_OBSERVATION_STUB,
                tool_call_id=call.get("id", ""),
            )
        name = call.get("name", "")
        args = call.get("args", {}) or {}
        slot = limiter.slot() if limiter is not None else nullcontext()
        try:
            with slot:
                result: Any = dispatch(name, args)
        except Exception as exc:  # surface to the model, keep looping
            result = {"error": f"{name} failed: {exc}"}
        return ToolMessage(content=str(result), tool_call_id=call.get("id", ""))

    convo = list(messages)
    for _ in range(max_steps):
        if deadline is not None and time.monotonic() >= deadline:
            break
        base = mask_stale_observations(convo, keep_last_observations)
        turn_input = base
        if render_state is not None:
            state = render_state()
            if state:
                turn_input = base + [("user", state)]
        try:
            ai = model.invoke(turn_input)
        except Exception as exc:
            logger.warning("react loop model call failed, ending loop", error=str(exc))
            if on_model_error is not None:
                on_model_error(exc)
            if model_error_observation is not None:
                convo.append(ToolMessage(content=model_error_observation(exc), tool_call_id=""))
            break
        convo.append(ai)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            break
        if parallel_dispatch and len(tool_calls) > 1:
            cap = max(1, min(len(tool_calls), max_parallel_tools))
            with ThreadPoolExecutor(max_workers=cap) as ex:
                convo.extend(ex.map(run_one, tool_calls))
        else:
            for call in tool_calls:
                if deadline is not None and time.monotonic() >= deadline:
                    break
                convo.append(run_one(call))
    return convo
