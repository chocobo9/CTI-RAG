"""Agentic answer loop — outer hard-rail StateGraph wrapping an inner create_react_agent.

The inner ``create_react_agent`` is a free ReAct burst (the agent plans + calls the
five tools autonomously). Its tools append full structured evidence to a per-run
``EvidenceLedger`` (side effect) before returning bounded summaries. The outer
``StateGraph`` adds the hard rails as nodes that read the *ledger*, not the message
transcript: a sufficiency-gate LLM judge, a budget-bounded router, and a synthesize
step with deterministic citation assembly.

This file is the langgraph/langchain WIRING only — it is coverage-omitted. The pure,
unit-tested logic lives in ``agentic_nodes.py`` / ``evidence_ledger.py`` /
``agentic_state.py``; the loop is verified end-to-end (key-guarded integration test).
"""

from __future__ import annotations

from typing import Any, TypedDict

from rag_cti.config import Settings
from rag_cti.knowledge import agent_tools, agentic_nodes
from rag_cti.knowledge.agentic_nodes import GeneratorProto, JudgeFn
from rag_cti.knowledge.agentic_state import AgenticAnswer
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.knowledge.fact_store import FactStoreProto
from rag_cti.observability.tracing import add_trace_metadata, traced

# (query, top_k) -> QueryResult. Injected so this file never imports rag_cti.__init__.
RunRetrieve = agent_tools.RunRetrieve

_RETRIEVE_SYSTEM = """You are a CTI analyst gathering evidence to answer a question. Use the tools to \
retrieve what you need, then write an answer grounded ONLY in what you retrieved, citing sources \
inline as [chunk_id] or [fact_id].

Tools:
- resolve_entity(name): a CTI name like "APT29" -> entity_id(s). The graph tools need an entity_id.
- graph_outline(entity_id): which relation categories an entity has and how many of each.
- graph_query(subject_id, predicate, object_type): the exact, exhaustive facts in one category.
- facts_for_evidence(chunk_id): which facts a given evidence chunk supports.
- retrieve(query): semantic search over source prose, for explanation/context the graph lacks.

Pick the tools each question needs — the graph is exact/enumerate, vector is prose. Stop calling \
tools once you can draft an answer; a verifier may hand you specific gaps to fill, so gather what \
it asks and revise."""


class _AgentState(TypedDict, total=False):
    messages: list[Any]
    iteration_count: int
    tokens_used: int
    new_evidence: int  # chunks+facts gathered in the last burst (0 => no progress)
    last_draft: str
    sufficiency: Any  # SufficiencyVerdict | None
    stop_reason: str
    route: str
    answer: Any  # AgenticAnswer


def build_judge(deepseek_client: Any, model: str) -> JudgeFn:
    """A JudgeFn (system, user) -> raw text over the DeepSeek chat endpoint."""

    def judge(system: str, user: str) -> str:
        response = deepseek_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=512,
        )
        content: str = response.choices[0].message.content or ""
        return content

    return judge


def _last_ai_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if getattr(message, "type", "") == "ai":
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                # A recursion-limit stub is not a real draft — treat as no draft so the
                # sufficiency judge does not reject it as ungrounded every iteration.
                return "" if agentic_nodes.is_recursion_stub(content) else content
    return ""


def _sum_tokens(messages: list[Any]) -> int:
    total = 0
    for message in messages:
        usage = getattr(message, "usage_metadata", None)
        if isinstance(usage, dict):
            total += int(usage.get("total_tokens", 0) or 0)
    return total


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

    @tool
    def resolve_entity(name: str) -> list[dict[str, str]]:
        """Resolve a threat-intel name (e.g. 'APT29') to entity_id candidates."""
        if fact_store is None:
            return []
        return agent_tools.resolve_entity_candidates(name, ontology_nodes)

    @tool
    def graph_outline(entity_id: str) -> dict[str, Any]:
        """Coverage map for an entity: which relation categories exist and how many."""
        if fact_store is None:
            return {"found": False, "entity_id": entity_id}
        return agent_tools.outline_to_ledger(fact_store, ledger, entity_id)

    @tool
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

    @tool
    def facts_for_evidence(chunk_id: str) -> dict[str, Any]:
        """Which facts a given evidence chunk_id supports (reverse provenance bridge)."""
        if fact_store is None:
            return {"count": 0, "facts": []}
        return agent_tools.facts_for_evidence_to_ledger(fact_store, ledger, chunk_id)

    @tool
    def retrieve(query: str, top_k: int = 10) -> dict[str, Any]:
        """Semantic search over source prose; returns chunk snippets."""
        return agent_tools.retrieve_to_ledger(run_retrieve, ledger, query, top_k)

    return [resolve_entity, graph_outline, graph_query, facts_for_evidence, retrieve]


def build_agentic_graph(
    *,
    settings: Settings,
    ledger: EvidenceLedger,
    query: str,
    run_retrieve: RunRetrieve,
    fact_store: FactStoreProto | None,
    ontology_nodes: list[dict[str, Any]],
    generator: GeneratorProto,
    chat_model: Any,
    judge: JudgeFn,
) -> Any:
    """Compile the outer StateGraph; nodes close over the per-run deps."""
    from langgraph.errors import GraphRecursionError
    from langgraph.graph import END, START, StateGraph
    from langgraph.prebuilt import create_react_agent

    tools = _build_tools(fact_store, ontology_nodes, run_retrieve, ledger)
    inner_agent = create_react_agent(chat_model, tools, prompt=_RETRIEVE_SYSTEM)

    def agent_turn(state: _AgentState) -> dict[str, Any]:
        messages = list(state.get("messages", []))
        verdict = state.get("sufficiency")
        if verdict is not None and getattr(verdict, "next_action", "") == "retrieve_more":
            from langchain_core.messages import HumanMessage

            messages.append(HumanMessage(content=agentic_nodes.build_directives(verdict)))
        before = len(ledger.facts) + len(ledger.chunks)
        try:
            result = inner_agent.invoke(
                {"messages": messages},
                config={"recursion_limit": settings.agentic_inner_recursion_limit},
            )
            out_messages = result["messages"]
        except GraphRecursionError:
            # The agent used its whole gather budget without terminating in a draft. Its
            # tool calls already populated the ledger (side effect), so proceed with what
            # was gathered: the sufficiency judge decides on the EVIDENCE and synthesize
            # produces the answer. (The inner agent is unreliable at stopping to draft.)
            out_messages = messages
        # out_messages is the FULL accumulated transcript each burst, so summing it
        # gives the cumulative token total directly — overwrite, never add (adding
        # would re-count every prior turn's messages).
        return {
            "messages": out_messages,
            "iteration_count": state.get("iteration_count", 0) + 1,
            "tokens_used": _sum_tokens(out_messages),
            "new_evidence": len(ledger.facts) + len(ledger.chunks) - before,
            "last_draft": _last_ai_text(out_messages),
        }

    def sufficiency_gate(state: _AgentState) -> dict[str, Any]:
        verdict = agentic_nodes.assess_sufficiency(
            judge, query, state.get("last_draft", ""), ledger
        )
        route, reason = agentic_nodes.decide_next(
            verdict,
            state.get("iteration_count", 0),
            state.get("tokens_used", 0),
            state.get("new_evidence", 0),
            max_iterations=settings.agentic_max_iterations,
            token_ceiling=settings.agentic_token_ceiling,
        )
        add_trace_metadata(
            sufficient=bool(verdict and verdict.sufficient),
            grounded=bool(verdict and verdict.grounded),
            faithfulness_estimate=(verdict.faithfulness_estimate if verdict else None),
            coverage_gaps=list(verdict.coverage_gaps) if verdict else [],
            next_action=(verdict.next_action if verdict else "parse_fallback"),
            route=route,
            iteration_count=state.get("iteration_count", 0),
        )
        return {"sufficiency": verdict, "route": route, "stop_reason": reason}

    def synthesize(state: _AgentState) -> dict[str, Any]:
        gen_answer = agentic_nodes.synthesize_answer(
            generator, query, ledger, top_k=settings.agentic_synthesis_top_k
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
        run_retrieve=run_retrieve,
        fact_store=fact_store,
        ontology_nodes=ontology_nodes,
        generator=generator,
        chat_model=chat_model,
        judge=judge,
    )
    # Outer recursion guard: agent_turn<->sufficiency_gate cycles, ended structurally
    # by decide_next at agentic_max_iterations. This is just the runaway backstop.
    outer_limit = max(25, settings.agentic_max_iterations * 4)
    result = graph.invoke(
        {"messages": [("user", query)], "iteration_count": 0, "tokens_used": 0},
        config={"recursion_limit": outer_limit},
    )
    answer: AgenticAnswer = result["answer"]
    return answer
