"""Pure node logic for the multi-agent supervisor (Model B — ReAct orchestration).

Mirrors ``agentic_nodes.py``: testable helpers with the LLM/threads injected, no real LLM.
The supervisor itself is a ReAct loop (``run_supervisor_loop``) whose TOOLS are sub-agents —
it routes itself (LLM picks the next tool), consistent with the rest of the ReAct system,
and never gathers or writes the answer. ``merge_branch_ledgers`` + ``extract_techniques``
feed the deterministic citation guard and the structured BranchReport. The real-LLM tool
wiring (dispatch_worker / compose_answer / build_composer) lives in ``supervisor_graph.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.knowledge.react_loop import run_react_tool_loop
from rag_cti.types import FactRow

if TYPE_CHECKING:
    from rag_cti.generation.limiter import ConcurrencyLimiter

# (tool_name, args) -> tool result. Injected so run_supervisor_loop unit-tests with a fake
# model + fake dispatch — no real LLM, no langgraph.
ToolDispatch = Callable[[str, "dict[str, Any]"], Any]


def merge_branch_ledgers(ledgers: Iterable[EvidenceLedger]) -> EvidenceLedger:
    """Fold N branch ledgers into one master ledger (union/dedup by id). Used by the
    deterministic citation guard to get the union of citable ids across branches."""
    master = EvidenceLedger()
    for led in ledgers:
        master.merge(led)
    return master


def extract_techniques(facts: Iterable[FactRow]) -> tuple[tuple[str, str, str], ...]:
    """The (attack_id, name, fact_id) set of technique-typed facts — the STRUCTURED slice a
    gather-only worker puts on its BranchReport so the Composer can do union/intersection
    over attack_ids AND cite the backing ``fact_id``. ``object_id`` like ``technique_T1059``
    is normalised to ``T1059``; deduped by attack_id, first occurrence wins."""
    seen: set[str] = set()
    out: list[tuple[str, str, str]] = []
    for fact in facts:
        if fact.object_type != "technique":
            continue
        attack_id = fact.object_id.removeprefix("technique_")
        if attack_id not in seen:
            seen.add(attack_id)
            out.append((attack_id, fact.object_name, fact.fact_id))
    return tuple(out)


def run_supervisor_loop(
    model: Any,
    dispatch: ToolDispatch,
    messages: list[Any],
    *,
    max_steps: int,
    max_workers: int,
    limiter: ConcurrencyLimiter | None = None,
    deadline: float | None = None,
    on_model_error: Callable[[BaseException], None] | None = None,
) -> list[Any]:
    """ReAct ORCHESTRATION loop for the supervisor. Like the worker's gather loop, but the
    tool calls of EACH turn run in PARALLEL — so multiple ``dispatch_worker`` calls fan out
    concurrently. The supervisor model picks tool calls; ``dispatch(name, args)`` runs each
    (side-effecting the report / composed-answer side-channels) and its result is fed back
    as a ToolMessage. Stops when the model emits no tool call, or after ``max_steps`` turns.
    The supervisor never writes the answer (that is ``compose_answer``'s job); only the side
    effects matter. A tool error is reported back to the model instead of aborting.

    ``limiter`` (B3) admission-controls each dispatch: 4 parallel branches each running a
    full inner loop would otherwise stampede the provider's 429 ceiling, so the slot bounds
    the in-flight branch count to the global concurrency cap. ``None`` => no limiting.
    ``deadline`` mirrors the worker gather loop's wall-clock guardrail at the orchestration
    layer; once reached, no further model/tool turn starts."""
    return run_react_tool_loop(
        model,
        dispatch,
        messages,
        max_steps=max_steps,
        deadline=deadline,
        on_model_error=on_model_error,
        model_error_observation=lambda exc: f"supervisor model failed: {exc}",
        parallel_dispatch=True,
        max_parallel_tools=max_workers,
        limiter=limiter,
    )
