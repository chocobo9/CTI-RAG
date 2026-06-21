"""Multi-agent supervisor (Model B) — a ReAct ORCHESTRATION agent.

The supervisor is itself an LLM agent that routes ITSELF (picks the next tool), exactly
like the inner worker loop — consistent with the rest of the ReAct system. Its tools are
SUB-AGENTS, not retrieval:

  - dispatch_worker(sub_question, focus_entity): runs one full worker sub-agent (the
    existing single-agent gather+synth loop) on a sub-question; side-effects its
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

from typing import Any

from rag_cti.config import Settings
from rag_cti.knowledge.agent_tools import RunRetrieve
from rag_cti.knowledge.agentic_graph import build_agentic_graph
from rag_cti.knowledge.agentic_nodes import GeneratorProto, JudgeFn, build_agentic_answer
from rag_cti.knowledge.agentic_state import AgenticAnswer, BranchReport, SubQuestion
from rag_cti.knowledge.composer import ComposeFn, compose
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.knowledge.fact_store import FactStoreProto
from rag_cti.knowledge.supervisor_nodes import (
    extract_techniques,
    merge_branch_ledgers,
    run_supervisor_loop,
)
from rag_cti.observability.tracing import add_trace_metadata, traced
from rag_cti.types import GeneratedAnswer

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

    def compose_fn(system: str, user: str) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        content: str = response.choices[0].message.content or ""
        return content

    return compose_fn


def gather_branch(
    branch: SubQuestion,
    *,
    settings: Settings,
    run_retrieve: RunRetrieve,
    fact_store: FactStoreProto | None,
    ontology_nodes: list[dict[str, Any]],
    generator: GeneratorProto,
    chat_model: Any,
    judge: JudgeFn,
) -> tuple[EvidenceLedger, BranchReport]:
    """Run ONE worker sub-agent (the existing single-agent gather+synth loop) over its OWN
    ledger and return (ledger, BranchReport). Reuses ``build_agentic_graph`` unchanged. Safe
    from a worker thread: ledger/graph are branch-local, shared deps are thread-safe."""
    ledger = EvidenceLedger()
    graph = build_agentic_graph(
        settings=settings,
        ledger=ledger,
        query=branch.sub_question,
        run_retrieve=run_retrieve,
        fact_store=fact_store,
        ontology_nodes=ontology_nodes,
        generator=generator,
        chat_model=chat_model,
        judge=judge,
        gather_only=True,  # workers GATHER only; the Composer is the sole synthesizer
    )
    outer_limit = max(25, settings.agentic_max_iterations * 4)
    result = graph.invoke(
        {"iteration_count": 0, "tokens_used": 0},
        config={"recursion_limit": outer_limit},
    )
    branch_answer: AgenticAnswer = result["answer"]
    techniques = extract_techniques(ledger.facts.values())
    report = BranchReport(
        sub_question=branch.sub_question,
        focus_entity=branch.focus_entity,
        sub_answer="",  # gather-only: no per-worker synthesis (the Composer synthesizes once)
        techniques=techniques,
        cited_ids=tuple(fid for _, _, fid in techniques),
        n_facts=len(ledger.facts),
        n_chunks=len(ledger.chunks),
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
    run_retrieve: RunRetrieve,
    fact_store: FactStoreProto | None,
    ontology_nodes: list[dict[str, Any]],
    generator: GeneratorProto,
    chat_model: Any,
    judge: JudgeFn,
    composer: ComposeFn,
) -> AgenticAnswer:
    """Run the ReAct orchestration loop and assemble the final grounded answer.

    The supervisor LLM decides what to dispatch and when to compose; this function only
    wires the tools, runs the loop, and does the DETERMINISTIC post-assembly (citation guard
    over the union of branch evidence). It never produces answer content itself.
    """
    from langchain_core.tools import tool

    reports: list[BranchReport] = []
    ledgers: list[EvidenceLedger] = []
    composed: dict[str, str] = {}

    def _run_worker(sub_question: str, focus_entity: str | None) -> BranchReport:
        ledger, report = gather_branch(
            SubQuestion(sub_question=sub_question, focus_entity=focus_entity),
            settings=settings,
            run_retrieve=run_retrieve,
            fact_store=fact_store,
            ontology_nodes=ontology_nodes,
            generator=generator,
            chat_model=chat_model,
            judge=judge,
        )
        ledgers.append(ledger)
        reports.append(report)
        return report

    @tool
    def dispatch_worker(sub_question: str, focus_entity: str | None = None) -> dict[str, Any]:
        """Assign one self-contained sub-question to a worker sub-agent; it gathers and
        returns a report. Returns a bounded summary (entity, technique count, answer preview)."""
        if len(reports) >= settings.supervisor_max_branches:
            return {"error": f"max {settings.supervisor_max_branches} workers already dispatched"}
        report = _run_worker(sub_question, focus_entity)
        return {
            "focus_entity": focus_entity,
            "n_techniques": len(report.techniques),
            "sub_answer_preview": report.sub_answer[:200],
            "stop_reason": report.stop_reason,
        }

    @tool
    def compose_answer() -> str:
        """Combine all gathered branch reports into the final answer (call once, at the end)."""
        if not reports:
            return "no reports gathered yet — dispatch workers first"
        composed["text"] = compose(composer, query, reports)
        return "composed the final answer from the branch reports"

    tools = [dispatch_worker, compose_answer]
    model_with_tools = chat_model.bind_tools(tools)
    tools_by_name = {t.name: t for t in tools}

    def dispatch(name: str, args: dict[str, Any]) -> Any:
        selected = tools_by_name.get(name)
        if selected is None:
            return {"error": f"unknown tool {name}"}
        return selected.invoke(args)

    run_supervisor_loop(
        model_with_tools,
        dispatch,
        [("system", _SUPERVISOR_SYSTEM), ("user", query)],
        max_steps=settings.supervisor_max_steps,
        max_workers=settings.supervisor_max_branches,
    )

    # --- deterministic post-assembly (no LLM reasoning in the supervisor) ---
    if not reports:  # supervisor dispatched nothing -> degrade to one worker on the query
        _run_worker(query, None)

    # The Composer is the SOLE synthesizer (workers are gather-only). If the supervisor
    # already called compose_answer in-loop, use that; else compose now. Works for 1 or N.
    answer_text = composed.get("text") or compose(composer, query, reports)

    master = merge_branch_ledgers(ledgers)
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
    decomposed = len(reports) > 1
    answer = build_agentic_answer(
        query,
        gen_answer,
        master,
        iteration_count=sum(r.iteration_count for r in reports),
        tokens_used=sum(r.tokens_used for r in reports),
        stop_reason="decomposed" if decomposed else "single",
    )
    add_trace_metadata(
        decomposed=decomposed,
        branch_count=len(reports),
        branch_stop_reasons=[r.stop_reason for r in reports],
        n_facts=len(master.facts),
        n_chunks=len(master.chunks),
        cited_ids=list(answer.cited_ids),
        dropped_citation_count=answer.dropped_citation_count,
    )
    return answer.model_copy(update={"branch_count": len(reports), "decomposed": decomposed})
