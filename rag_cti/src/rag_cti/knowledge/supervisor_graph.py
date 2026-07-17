"""Multi-agent supervisor (Model B) — a ReAct ORCHESTRATION agent.

The supervisor is itself an LLM agent that routes ITSELF (picks the next tool), exactly
like the inner worker loop — consistent with the rest of the ReAct system. Its tools are
SUB-AGENTS, not retrieval:

  - dispatch_worker(sub_question, focus_entity): runs one gather-only worker sub-agent
    through the runtime-owned gather investigation on a sub-question; side-effects its
    BranchReport into a report side-channel; returns a BOUNDED summary so the supervisor's
    own context stays small. The supervisor may emit several in one turn -> they run in
    PARALLEL (``run_supervisor_loop``).
  - compose_answer(): hands all reports to the Composer (a distinct LLM role) which writes
    the final combined answer.

Hard invariant: the supervisor NEVER gathers or synthesizes. The final answer always comes
from the Composer (or a single worker's own sub_answer); a deterministic citation guard
validates it against the union of the workers' evidence. This file is the langgraph /
langchain WIRING (coverage-omitted); the pure logic is in ``supervisor_nodes.py`` /
``composer.py`` / ``agentic_nodes.py``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar, cast

from rag_cti.config import Settings
from rag_cti.knowledge.agent_tools import RunRetrieve
from rag_cti.knowledge.agentic_nodes import GeneratorProto, JudgeFn, build_agentic_answer
from rag_cti.knowledge.agentic_state import AgenticAnswer, BranchReport, SubQuestion
from rag_cti.knowledge.chat_fn import build_chat_fn
from rag_cti.knowledge.composer import ComposeFn, compose
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.knowledge.fact_store import FactStoreProto
from rag_cti.knowledge.supervisor_nodes import (
    extract_techniques,
    merge_branch_ledgers,
    run_supervisor_loop,
)
from rag_cti.observability.tracing import add_trace_metadata, traced
from rag_cti.runtime_harness import ProposedBranch, run_agentic_gather_investigation
from rag_cti.types import GeneratedAnswer

F = TypeVar("F", bound=Callable[..., Any])

_SUPERVISOR_SYSTEM = """You are a CTI ORCHESTRATOR. You do NOT answer questions yourself and \
you do NOT gather evidence yourself — you only coordinate worker sub-agents via tools.

Tools:
- dispatch_worker(sub_question, focus_entity): assign ONE self-contained sub-question to a \
worker sub-agent; it gathers evidence and returns a report. Call it once PER INDEPENDENT \
sub-question. You MAY emit several dispatch_worker calls in one turn to run workers in PARALLEL.
- compose_answer(): once the needed reports are gathered, call this to produce the final \
combined answer from the reports.

How to orchestrate:
- MULTIPLE independent entities or facets (e.g. "compare APT29 and Turla", "techniques shared \
between X and Y", "APT29's TTPs + infrastructure") -> dispatch ONE worker per entity/facet, \
in parallel.
- A SIMPLE question, or a SEQUENTIAL/DEPENDENT multi-hop (e.g. "what does the malware X dropped \
communicate with") -> dispatch ONE worker on the whole question. Do NOT split a dependent chain.
- After the reports are in, call compose_answer exactly once, then stop.
- Never write the answer yourself; the answer comes from compose_answer."""


def build_composer(client: Any, model: str, max_tokens: int = 1024) -> ComposeFn:
    """A ComposeFn (system, user) -> raw answer text over any OpenAI-compatible chat
    endpoint. Mirrors ``agentic_graph.build_judge`` — the Composer is a distinct LLM role
    that only combines reports, so it reuses the same client plumbing."""
    return build_chat_fn(client, model, max_tokens)


def gather_branch(
    branch: SubQuestion,
    *,
    settings: Settings,
    history: list[str] | None = None,
    run_retrieve: RunRetrieve,
    fact_store: FactStoreProto | None,
    ontology_nodes: list[dict[str, Any]],
    generator: GeneratorProto,
    chat_model: Any,
    judge: JudgeFn,
) -> tuple[EvidenceLedger, BranchReport]:
    """Run ONE worker sub-agent gather loop over its OWN ledger and return (ledger, BranchReport).

    Uses the runtime-owned gather-only investigation path. Safe
    from a worker thread: ledger/graph are branch-local, shared deps are thread-safe."""
    result = run_agentic_gather_investigation(
        branch.sub_question,
        settings=settings,
        history=history,
        run_retrieve=run_retrieve,
        fact_store=fact_store,
        ontology_nodes=ontology_nodes,
        generator=generator,
        chat_model=chat_model,
        judge=judge,
    )
    ledger = result.ledger
    branch_answer: AgenticAnswer = result.answer
    techniques = extract_techniques(ledger.facts.values())
    status = "ok" if ledger.facts or ledger.chunks else "empty"
    report = BranchReport(
        branch_id=branch.branch_id,
        sub_question=branch.sub_question,
        focus_entity=branch.focus_entity,
        facet=branch.facet,
        status=status,
        evidence_summary=(
            f"Gathered {len(ledger.facts)} facts, {len(ledger.chunks)} chunks, "
            f"and {len(ledger.outlines)} outlines."
        ),
        sub_answer="",  # gather-only: no per-worker synthesis (the Composer synthesizes once)
        techniques=techniques,
        cited_ids=tuple(fid for _, _, fid in techniques),
        n_facts=len(ledger.facts),
        n_chunks=len(ledger.chunks),
        n_outlines=len(ledger.outlines),
        stop_reason=branch_answer.stop_reason,
        tokens_used=branch_answer.tokens_used,
        iteration_count=branch_answer.iteration_count,
    )
    return ledger, report


@traced("supervisor.answer", run_type="chain")
def run_supervised_answer(
    query: str,
    *,
    settings: Settings,
    history: list[str] | None = None,
    run_retrieve: RunRetrieve,
    fact_store: FactStoreProto | None,
    ontology_nodes: list[dict[str, Any]],
    generator: GeneratorProto,
    chat_model: Any,
    judge: JudgeFn,
    composer: ComposeFn,
    branch_plan: Sequence[ProposedBranch] | None = None,
) -> AgenticAnswer:
    """Run supervised coordination and assemble the final grounded answer.

    Production runtime callers pass a validated ``branch_plan`` from query understanding;
    that path dispatches workers deterministically and skips the supervisor routing loop.
    ``branch_plan=None`` keeps the legacy autonomous ReAct supervisor available only for
    debug/eval/manual baselines. This function never produces answer content itself; the
    Composer writes the final answer and the deterministic citation guard validates it.
    """
    from langchain_core.tools import tool

    typed_tool = cast(Callable[[F], Any], tool)

    reports: list[BranchReport] = []
    ledgers: list[EvidenceLedger] = []
    reports_lock = threading.Lock()
    composed: dict[str, str] = {}
    max_wall_seconds = getattr(settings, "agentic_max_wall_seconds", 0.0)
    deadline = time.monotonic() + max_wall_seconds if max_wall_seconds > 0 else None

    def _run_worker(
        sub_question: str,
        focus_entity: str | None,
        *,
        branch_id: str = "",
        facet: str | None = None,
    ) -> BranchReport:
        branch = SubQuestion(
            sub_question=sub_question,
            branch_id=branch_id,
            focus_entity=focus_entity,
            facet=facet,
        )
        try:
            ledger, report = gather_branch(
                branch,
                settings=settings,
                history=history,
                run_retrieve=run_retrieve,
                fact_store=fact_store,
                ontology_nodes=ontology_nodes,
                generator=generator,
                chat_model=chat_model,
                judge=judge,
            )
        except Exception as exc:
            ledger = EvidenceLedger()
            report = BranchReport(
                branch_id=branch.branch_id,
                sub_question=branch.sub_question,
                focus_entity=branch.focus_entity,
                facet=branch.facet,
                status="failed",
                evidence_summary="Branch failed before gathering usable evidence.",
                errors=(f"{type(exc).__name__}: {exc}",),
                stop_reason="failed",
            )
        with reports_lock:
            ledgers.append(ledger)
            reports.append(report)
        return report

    def _run_validated_plan(plan: Sequence[ProposedBranch]) -> None:
        branches = list(plan[: settings.supervisor_max_branches])

        def _one(branch: ProposedBranch) -> BranchReport:
            return _run_worker(
                branch.sub_question,
                branch.focus_entity,
                branch_id=branch.branch_id,
                facet=branch.facet,
            )

        with ThreadPoolExecutor(
            max_workers=max(1, min(len(branches), settings.supervisor_max_branches))
        ) as ex:
            list(ex.map(_one, branches))

    @typed_tool
    def dispatch_worker(sub_question: str, focus_entity: str | None = None) -> dict[str, Any]:
        """Assign one self-contained sub-question to a worker sub-agent; it gathers and
        returns a report. Returns a bounded summary (entity, technique count, answer preview)."""
        with reports_lock:
            if composed:
                return {"error": "final answer already composed"}
            dispatched = len(reports)
        if dispatched >= settings.supervisor_max_branches:
            return {"error": f"max {settings.supervisor_max_branches} workers already dispatched"}
        report = _run_worker(sub_question, focus_entity)
        return {
            "focus_entity": focus_entity,
            "n_techniques": len(report.techniques),
            "sub_answer_preview": report.sub_answer[:200],
            "stop_reason": report.stop_reason,
        }

    @typed_tool
    def compose_answer() -> str:
        """Combine all gathered branch reports into the final answer (call once, at the end)."""
        if not reports:
            return "no reports gathered yet — dispatch workers first"
        with reports_lock:
            snapshot = list(reports)
        composed["text"] = compose(composer, query, snapshot, history=history)
        return "composed the final answer from the branch reports"

    add_trace_metadata(
        supervisor_entrypoint=(
            "runtime_validated_branch_plan"
            if branch_plan is not None
            else "legacy_autonomous_debug_eval"
        ),
        supervisor_branch_plan_count=len(branch_plan or ()),
    )
    if branch_plan is not None:
        _run_validated_plan(branch_plan)
    else:
        tools = [dispatch_worker, compose_answer]
        model_with_tools = chat_model.bind_tools(tools)
        tools_by_name = {t.name: t for t in tools}

        def dispatch(name: str, args: dict[str, Any]) -> Any:
            selected = tools_by_name.get(name)
            if selected is None:
                return {"error": f"unknown tool {name}"}
            return selected.invoke(args)

        # B3 admission control: bound the in-flight worker branches (each runs a full inner loop of
        # provider calls) so a 4-branch fan-out cannot stampede the DeepSeek 429 ceiling. Reuses
        # the verifier provider's quota family (the gather/judge family).
        from rag_cti.generation.limiter import get_limiter

        run_supervisor_loop(
            model_with_tools,
            dispatch,
            [("system", _SUPERVISOR_SYSTEM), ("user", query)],
            max_steps=settings.supervisor_max_steps,
            max_workers=settings.supervisor_max_branches,
            limiter=get_limiter(settings.agentic_verifier_provider, settings),
            deadline=deadline,
        )

    # --- deterministic post-assembly (no LLM reasoning in the supervisor) ---
    if not reports:  # supervisor dispatched nothing -> degrade to one worker on the query
        _run_worker(query, None)

    # The Composer is the SOLE synthesizer (workers are gather-only). If the supervisor
    # already called compose_answer in-loop, use that; else compose now. Works for 1 or N.
    with reports_lock:
        report_snapshot = list(reports)
        ledger_snapshot = list(ledgers)
    answer_text = composed.get("text") or compose(composer, query, report_snapshot, history=history)

    master = merge_branch_ledgers(ledger_snapshot)
    gen_answer = GeneratedAnswer(
        query=query,
        answer=answer_text,
        cited_chunk_ids=[],
        query_result=master.union_query_result(query, limit=settings.agentic_synthesis_top_k),
        generation_ms=0.0,
        model="composer",
    )
    # build_agentic_answer runs the deterministic citation guard (assemble_citations) over
    # the merged master ledger — validates the answer's [id]s against the union of branch
    # evidence. No synthesis here; the text already came from the Composer.
    decomposed = len(report_snapshot) > 1
    answer = build_agentic_answer(
        query,
        gen_answer,
        master,
        iteration_count=sum(r.iteration_count for r in report_snapshot),
        tokens_used=sum(r.tokens_used for r in report_snapshot),
        stop_reason="decomposed" if decomposed else "single",
    )
    add_trace_metadata(
        decomposed=decomposed,
        branch_count=len(report_snapshot),
        branch_stop_reasons=[r.stop_reason for r in report_snapshot],
        n_facts=len(master.facts),
        n_chunks=len(master.chunks),
        cited_ids=list(answer.cited_ids),
        dropped_citation_count=answer.dropped_citation_count,
    )
    return answer.model_copy(
        update={"branch_count": len(report_snapshot), "decomposed": decomposed}
    )
