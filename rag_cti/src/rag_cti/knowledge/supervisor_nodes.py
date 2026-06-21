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
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.types import FactRow

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
) -> list[Any]:
    """ReAct ORCHESTRATION loop for the supervisor. Like the worker's gather loop, but the
    tool calls of EACH turn run in PARALLEL — so multiple ``dispatch_worker`` calls fan out
    concurrently. The supervisor model picks tool calls; ``dispatch(name, args)`` runs each
    (side-effecting the report / composed-answer side-channels) and its result is fed back
    as a ToolMessage. Stops when the model emits no tool call, or after ``max_steps`` turns.
    The supervisor never writes the answer (that is ``compose_answer``'s job); only the side
    effects matter. A tool error is reported back to the model instead of aborting."""
    from langchain_core.messages import ToolMessage

    def run_one(call: dict[str, Any]) -> Any:
        name = call.get("name", "")
        args = call.get("args", {}) or {}
        try:
            result: Any = dispatch(name, args)
        except Exception as exc:  # surface to the model, keep orchestrating
            result = {"error": f"{name} failed: {exc}"}
        return ToolMessage(content=str(result), tool_call_id=call.get("id", ""))

    convo = list(messages)
    for _ in range(max_steps):
        ai = model.invoke(convo)
        convo.append(ai)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            break  # supervisor emitted no tool call -> done orchestrating
        if len(tool_calls) == 1:
            convo.append(run_one(tool_calls[0]))
        else:  # parallel fan-out of this turn's tool calls (the multi-worker dispatch)
            with ThreadPoolExecutor(max_workers=max(1, min(len(tool_calls), max_workers))) as ex:
                convo.extend(ex.map(run_one, tool_calls))
    return convo
