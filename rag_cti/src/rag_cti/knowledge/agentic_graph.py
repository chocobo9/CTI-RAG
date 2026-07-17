"""Agentic answer loop — outer hard-rail StateGraph wrapping an inner GATHER-only loop.

Production/public agentic paths are owned by ``runtime_harness.run_agentic_investigation``.
This module remains as legacy debug/baseline wiring and for tests that exercise the old
LangGraph integration directly.

The inner loop is a hand-rolled ReAct-style burst (``agentic_nodes.run_gather_loop``): a
tool-bound chat model picks tool calls, each tool appends full structured evidence to a
per-run ``EvidenceLedger`` (side effect) and returns a bounded summary, and the burst
stops as soon as the model emits no tool call (gathered enough) or a step cap is hit. It
is GATHER-only — it never writes the answer, so it cannot over-explore into a recursion
stub the way ``create_react_agent`` did. The outer ``StateGraph`` adds the hard rails as
nodes that read the *ledger*, not the transcript: a sufficiency-gate LLM judge, a
budget-bounded router, and a synthesize step with deterministic citation assembly.

This file is the langgraph/langchain WIRING only — it is coverage-omitted. The pure,
unit-tested logic lives in ``agentic_nodes.py`` / ``evidence_ledger.py`` /
``agentic_state.py``; the loop is verified end-to-end (key-guarded integration test).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, TypedDict, TypeVar, cast

from rag_cti.config import Settings
from rag_cti.knowledge import agent_tools, agentic_effort, agentic_nodes, tool_cache
from rag_cti.knowledge.agentic_nodes import GeneratorProto, JudgeFn
from rag_cti.knowledge.agentic_state import AgenticAnswer
from rag_cti.knowledge.chat_fn import build_chat_fn
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.knowledge.fact_store import FactStoreProto
from rag_cti.knowledge.graph_limits import outer_recursion_limit
from rag_cti.observability.tracing import add_trace_metadata, traced
from rag_cti.types import GeneratedAnswer

# (query, top_k) -> QueryResult. Injected so this file never imports rag_cti.__init__.
RunRetrieve = agent_tools.RunRetrieve
F = TypeVar("F", bound=Callable[..., Any])

_GATHER_SYSTEM = """You are a CTI analyst GATHERING evidence for a question. Your ONLY job is to call \
tools to collect the facts and prose needed to answer it. Another step writes the final answer, so do \
NOT write the answer yourself.

Tools:
- resolve_entity(name): a CTI name like "APT29" -> entity_id(s). The graph tools need an entity_id.
- graph_outline(subject_id): which relation categories a subject has and how many of each.
- graph_query(subject_id, predicate, object_type): the exact, exhaustive facts in one category. It \
records the COMPLETE set and reports `total` + `complete: true` — once you query a category you already \
hold all of it, so never query the same category twice.
- facts_for_evidence(chunk_id): which facts a given evidence chunk supports.
- retrieve(query): semantic search over source prose, for explanation/context the graph lacks.

How to gather:
- Graph for who/what/enumerate (exact and exhaustive); retrieve for why/how/explain prose.
- Plan minimally: resolve the entity, outline it, query the relevant category ONCE, optionally retrieve \
prose. Never repeat a tool call you have already made.
- A verifier may hand you specific gaps to fill — gather exactly those.
- When you have gathered enough to answer, STOP: emit no further tool call. Do not write the answer."""


class _AgentState(TypedDict, total=False):
    messages: list[Any]  # this burst's transcript only (not carried across iterations)
    iteration_count: int
    tokens_used: int  # running total across bursts (accumulated, not overwritten)
    new_evidence: int  # chunks+facts gathered in the last burst (0 => no progress)
    new_facts: int  # graph facts gathered in the last burst (0 + repeated gap => stuck)
    last_draft: str
    sufficiency: Any  # SufficiencyVerdict | None
    prev_gaps: tuple[str, ...]  # previous verdict's coverage_gaps (repeat => stuck)
    open_categories: int  # last gate's count of still-open graph enumeration categories
    open_cat_stall: int  # consecutive gate turns the open-category count did NOT shrink
    stop_reason: str
    route: str
    answer: Any  # AgenticAnswer
    provider_error: bool  # last burst's gather model.invoke raised (persistent 429 etc.)


def build_judge(client: Any, model: str, max_tokens: int = 1024) -> JudgeFn:
    """A JudgeFn (system, user) -> raw text over ANY OpenAI-compatible chat endpoint
    (DeepSeek, or — for an independent cross-family verifier — Qwen/DashScope). ``max_tokens``
    is sized so a thinking-style model has room to reason before emitting the JSON verdict."""
    return build_chat_fn(client, model, max_tokens)


def _sum_tokens(messages: list[Any]) -> int:
    total = 0
    for message in messages:
        usage = getattr(message, "usage_metadata", None)
        if isinstance(usage, dict):
            total += int(usage.get("total_tokens", 0) or 0)
    return total


def _normalize_tool_args(
    name: str, args: dict[str, Any], *, retrieve_query_max_chars: int
) -> dict[str, Any]:
    if name != "retrieve":
        return args
    query = str(args.get("query", "") or "")
    compact_query = " ".join(query.split())
    if retrieve_query_max_chars > 0 and len(compact_query) > retrieve_query_max_chars:
        compact_query = compact_query[:retrieve_query_max_chars].rsplit(" ", 1)[0].strip()
    if compact_query == query:
        return args
    return {**args, "query": compact_query}


def _build_tools(
    fact_store: FactStoreProto | None,
    ontology_nodes: list[dict[str, Any]],
    run_retrieve: RunRetrieve,
    ledger: EvidenceLedger,
) -> list[Any]:
    """The five in-process tools, each appending full evidence to ``ledger``.

    When ``fact_store`` is None (Neo4j disabled), the graph tools degrade to no-ops
    so the loop runs vector-only — the "orthogonal to PDF->graph" guarantee.
    """
    from langchain_core.tools import tool

    typed_tool = cast(Callable[[F], F], tool)

    @typed_tool
    def resolve_entity(name: str) -> list[dict[str, str]]:
        """Resolve a threat-intel name (e.g. 'APT29') to entity_id candidates."""
        if fact_store is None:
            return []
        return agent_tools.resolve_entity_candidates(name, ontology_nodes)

    @typed_tool
    def graph_outline(subject_id: str) -> dict[str, Any]:
        """Coverage map for a subject_id: which relation categories exist and how many."""
        if fact_store is None:
            return {"found": False, "entity_id": subject_id}
        return agent_tools.outline_to_ledger(fact_store, ledger, subject_id)

    @typed_tool
    def graph_query(
        subject_id: str,
        predicate: str | None = None,
        object_type: str | None = None,
        min_credibility: float = 0.0,
    ) -> dict[str, Any]:
        """Enumerate the exact facts for (subject_id[, predicate, object_type])."""
        if fact_store is None:
            return {"total": 0, "shown": 0, "truncated": False, "objects": []}
        return agent_tools.graph_query_to_ledger(
            fact_store,
            ledger,
            subject_id=subject_id,
            predicate=predicate,
            object_type=object_type,
            min_credibility=min_credibility,
        )

    @typed_tool
    def facts_for_evidence(chunk_id: str) -> dict[str, Any]:
        """Which facts a given evidence chunk_id supports (reverse provenance bridge)."""
        if fact_store is None:
            return {"count": 0, "facts": []}
        return agent_tools.facts_for_evidence_to_ledger(fact_store, ledger, chunk_id)

    @typed_tool
    def retrieve(query: str, top_k: int = 10) -> dict[str, Any]:
        """Semantic search over source prose; returns chunk snippets."""
        return agent_tools.retrieve_to_ledger(run_retrieve, ledger, query, top_k)

    return [resolve_entity, graph_outline, graph_query, facts_for_evidence, retrieve]


def build_agentic_graph(
    *,
    settings: Settings,
    ledger: EvidenceLedger,
    query: str,
    history: list[str] | None = None,
    run_retrieve: RunRetrieve,
    fact_store: FactStoreProto | None,
    ontology_nodes: list[dict[str, Any]],
    generator: GeneratorProto,
    chat_model: Any,
    judge: JudgeFn,
    gather_only: bool = False,
) -> Any:
    """Compile the outer StateGraph; nodes close over the per-run deps.

    ``gather_only=True`` skips the (expensive) synthesize generation: the loop gathers into
    the ledger and the final node packages the evidence with an EMPTY answer. Used by the
    multi-agent supervisor's workers — only the Composer synthesizes, so a per-worker
    synthesis is wasted (the N+1-synthesis cost sink)."""
    from langgraph.graph import END, START, StateGraph

    # Per-run wall clock for the latency guardrail (graph is built once per query, right
    # before invoke, so this ~= loop start). The deadline is the SAME budget the coarse
    # decide_next check uses, pushed DOWN into the gather loop so an in-node retry storm is
    # bounded too (0 disables it).
    started_at = time.monotonic()
    deadline = (
        started_at + settings.agentic_max_wall_seconds
        if settings.agentic_max_wall_seconds > 0
        else None
    )
    tools = _build_tools(fact_store, ontology_nodes, run_retrieve, ledger)
    model_with_tools = chat_model.bind_tools(tools)
    tools_by_name = {t.name: t for t in tools}
    # Effort tier is a deterministic function of the (fixed) query, so classify once here and
    # close over it — the per-turn budget line just re-reads len(ledger.actions).
    effort_tier = agentic_effort.classify_effort_tier(query)
    hard_tool_budgets = getattr(
        settings,
        "agentic_hard_tool_budgets",
        {"simple": 10, "comparison": 20, "complex": 32},
    )
    hard_tool_budget = hard_tool_budgets.get(effort_tier, 0)
    dispatch_lock = threading.Lock()

    def dispatch(name: str, args: dict[str, Any]) -> Any:
        """Run a tool by name (tools side-effect the ledger); used by the gather loop.

        Records every valid dispatch on the ledger action log — the model-facing 'what I
        already did' view (when shown) AND the exact tool-call count on the answer. The count
        is taken BEFORE the cache check so it stays the exact over-calling metric (attempts).
        When the tool cache is enabled, an identical re-dispatch returns the cached result
        flagged as a duplicate instead of re-executing — the tools are idempotent within a
        run, so this skips only wasted work and tells the model it already gathered this."""
        tool = tools_by_name.get(name)
        if tool is None:
            return {"error": f"unknown tool {name}"}
        args = _normalize_tool_args(
            name,
            args,
            retrieve_query_max_chars=getattr(settings, "agentic_retrieve_query_max_chars", 360),
        )
        with dispatch_lock:
            if hard_tool_budget > 0 and len(ledger.actions) >= hard_tool_budget:
                return {
                    "error": "tool budget exhausted",
                    "max_tool_calls": hard_tool_budget,
                    "executed_tool_calls": len(ledger.actions),
                }
            ledger.add_action(name, args)
        if name == "retrieve" and agentic_nodes.should_suppress_retrieve_after_graph_coverage(
            query, ledger
        ):
            return {
                "error": "retrieve suppressed: graph evidence is already sufficient",
                "reason": "complete graph uses->technique facts cover the comparison",
            }
        hit = ledger.cache_get(name, args)
        if hit is not None:
            return tool_cache.as_duplicate(hit)
        result = tool.invoke(args)
        ledger.cache_put(name, args, result)
        return result

    def agent_turn(state: _AgentState) -> dict[str, Any]:
        # Working-set pattern: start each burst from a CLEAN [system, query(, directive)] —
        # never the prior burst's transcript (redundant with the ledger, and carrying it
        # made context + cost grow super-linearly across iterations). The ledger is the
        # cross-iteration memory; the directive carries a summary of it + the gaps.
        verdict = state.get("sufficiency")
        messages = agentic_nodes.build_turn_messages(
            _GATHER_SYSTEM, query, verdict, ledger, history=history
        )
        before_facts = len(ledger.facts)
        before = before_facts + len(ledger.chunks)
        errors: list[BaseException] = []

        def _render_context() -> str:
            # One end-of-turn block: gathered state, action log, effort budget (non-empty
            # sections only). Budget line goes LAST for highest-attention placement.
            blocks: list[str] = []
            blocks.append(agentic_nodes.render_state_view(ledger))
            blocks.append(agentic_nodes.render_action_log(ledger))
            blocks.append(
                agentic_effort.render_budget_line(
                    effort_tier, len(ledger.actions), settings.agentic_effort_budgets
                )
            )
            return "\n\n".join(b for b in blocks if b)

        render_state = _render_context
        out_messages = agentic_nodes.run_gather_loop(
            model_with_tools,
            dispatch,
            messages,
            max_steps=settings.agentic_max_inner_steps,
            deadline=deadline,
            on_model_error=errors.append,
            render_state=render_state,
            keep_last_observations=settings.agentic_keep_last_observations,
            parallel_dispatch=settings.agentic_parallel_dispatch_enabled,
            max_parallel_tools=settings.agentic_max_parallel_tools,
        )
        # GATHER-only: synthesize produces the answer over the ledger, so no draft to carry.
        # out_messages is just THIS burst now (not carried), so _sum_tokens(out_messages) is
        # this burst's real cost — ACCUMULATE into the running total (linear in iterations).
        return {
            "messages": out_messages,
            "iteration_count": state.get("iteration_count", 0) + 1,
            "tokens_used": state.get("tokens_used", 0) + _sum_tokens(out_messages),
            "new_evidence": len(ledger.facts) + len(ledger.chunks) - before,
            "new_facts": len(ledger.facts) - before_facts,
            "last_draft": "",
            "provider_error": bool(errors),
        }

    def sufficiency_gate(state: _AgentState) -> dict[str, Any]:
        # A persistent gather-model failure (provider 429) ends the run: the judge runs on
        # the same provider, so skip it and synthesize over whatever the ledger holds —
        # degrade gracefully instead of crashing the answer (mirrors Generator's sentinel).
        if state.get("provider_error"):
            add_trace_metadata(route="synthesize", stop_reason="provider_error")
            return {
                "sufficiency": None,
                "route": "synthesize",
                "stop_reason": "provider_error",
                "prev_gaps": (),
            }
        if agentic_nodes.should_suppress_retrieve_after_graph_coverage(query, ledger):
            add_trace_metadata(route="synthesize", stop_reason="graph_sufficient")
            return {
                "sufficiency": None,
                "route": "synthesize",
                "stop_reason": "graph_sufficient",
                "prev_gaps": (),
                "open_categories": 0,
                "open_cat_stall": 0,
            }
        verdict = agentic_nodes.assess_sufficiency(
            judge, query, state.get("last_draft", ""), ledger, history=history
        )
        # Deterministic open-category stall signal (additive convergence guard): how many
        # graph enumeration categories are still open, and for how many consecutive gate
        # turns that count has failed to shrink. The first gate never stalls (prev defaults
        # to current+1). Disabled => max_open_cat_stall=0 keeps decide_next behaviour exact.
        current_open = agentic_nodes.count_open_categories(ledger)
        prev_open = state.get("open_categories", current_open + 1)
        open_cat_stall = state.get("open_cat_stall", 0) + 1 if current_open >= prev_open else 0
        max_open_cat_stall = settings.agentic_open_cat_stall_limit
        route, reason = agentic_nodes.decide_next(
            verdict,
            state.get("iteration_count", 0),
            state.get("tokens_used", 0),
            state.get("new_evidence", 0),
            max_iterations=settings.agentic_max_iterations,
            token_ceiling=settings.agentic_token_ceiling,
            max_retrieve_rounds=settings.agentic_max_retrieve_rounds,
            new_facts=state.get("new_facts", 0),
            prev_gaps=state.get("prev_gaps", ()),
            elapsed_seconds=time.monotonic() - started_at,
            max_wall_seconds=settings.agentic_max_wall_seconds,
            open_cat_stall=open_cat_stall,
            max_open_cat_stall=max_open_cat_stall,
            tool_calls_used=len(ledger.actions),
            max_tool_calls=hard_tool_budget,
        )
        add_trace_metadata(
            sufficient=bool(verdict and verdict.sufficient),
            grounded=bool(verdict and verdict.grounded),
            faithfulness_estimate=(verdict.faithfulness_estimate if verdict else None),
            coverage_gaps=list(verdict.coverage_gaps) if verdict else [],
            next_action=(verdict.next_action if verdict else "parse_fallback"),
            route=route,
            iteration_count=state.get("iteration_count", 0),
            open_categories=current_open,
            open_cat_stall=open_cat_stall,
        )
        # Stash this verdict's gaps so the next gate can detect the judge repeating itself.
        return {
            "sufficiency": verdict,
            "route": route,
            "stop_reason": reason,
            "prev_gaps": tuple(verdict.coverage_gaps) if verdict else (),
            "open_categories": current_open,
            "open_cat_stall": open_cat_stall,
        }

    def synthesize(state: _AgentState) -> dict[str, Any]:
        if gather_only:
            # No generation: package the gathered evidence with an empty answer. The
            # supervisor's Composer is the only synthesizer.
            gen_answer = GeneratedAnswer(
                query=query,
                answer="",
                cited_chunk_ids=[],
                query_result=ledger.union_query_result(
                    query, limit=settings.agentic_synthesis_top_k
                ),
                generation_ms=0.0,
                model="gather-only",
            )
        else:
            gen_answer = agentic_nodes.synthesize_answer(
                generator,
                query,
                ledger,
                top_k=settings.agentic_synthesis_top_k,
                fact_limit=getattr(settings, "agentic_synthesis_fact_limit", 120),
                history=history,
            )
        answer = agentic_nodes.build_agentic_answer(
            query,
            gen_answer,
            ledger,
            iteration_count=state.get("iteration_count", 0),
            tokens_used=state.get("tokens_used", 0),
            stop_reason=state.get("stop_reason", ""),
        )
        add_trace_metadata(
            iteration_count=answer.iteration_count,
            stop_reason=answer.stop_reason,
            cited_ids=list(answer.cited_ids),
            dropped_citation_count=answer.dropped_citation_count,
            n_chunks=len(ledger.chunks),
            n_facts=len(ledger.facts),
            n_conflicts=len(answer.conflicts),
        )
        return {"answer": answer}

    def route_edge(state: _AgentState) -> str:
        return state.get("route", "synthesize")

    graph = StateGraph(_AgentState)
    graph.add_node("agent_turn", agent_turn)
    graph.add_node("sufficiency_gate", sufficiency_gate)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "agent_turn")
    graph.add_edge("agent_turn", "sufficiency_gate")
    graph.add_conditional_edges(
        "sufficiency_gate",
        route_edge,
        {"agent_turn": "agent_turn", "synthesize": "synthesize"},
    )
    graph.add_edge("synthesize", END)
    return graph.compile()


@traced("agentic.answer", run_type="chain")
def run_agentic_answer(
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
) -> AgenticAnswer:
    """Run the loop end to end for one question and return the cited AgenticAnswer."""
    ledger = EvidenceLedger()
    graph = build_agentic_graph(
        settings=settings,
        ledger=ledger,
        query=query,
        history=history,
        run_retrieve=run_retrieve,
        fact_store=fact_store,
        ontology_nodes=ontology_nodes,
        generator=generator,
        chat_model=chat_model,
        judge=judge,
    )
    # Outer recursion guard: agent_turn<->sufficiency_gate cycles, ended structurally
    # by decide_next at agentic_max_iterations. This is just the runaway backstop.
    outer_limit = outer_recursion_limit(settings)
    result = graph.invoke(
        {
            "messages": [("system", _GATHER_SYSTEM), ("user", query)],
            "iteration_count": 0,
            "tokens_used": 0,
        },
        config={"recursion_limit": outer_limit},
    )
    answer: AgenticAnswer = result["answer"]
    return answer
