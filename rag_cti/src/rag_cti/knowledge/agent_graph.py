"""v1 agentic loop — a LangGraph ReAct agent over the v0 tools (M4 §9).

Uses LangGraph's prebuilt ``create_react_agent`` (an agent⇄tools StateGraph with a
``recursion_limit`` hard ceiling). The §9.3 flow (resolve → outline → query by
coverage → synthesize) is encoded in the system prompt; an explicit multi-node
StateGraph with a hard coverage-check is the escalation if the prompt's soft
coverage gauge proves insufficient on real queries (§9.4 #2).

Tools are in-process LangChain ``@tool``s wrapping :mod:`agent_tools` (NOT MCP).
The §9.4 #1 context strategy lives in agent_tools (summaries, not 223 full facts).
"""

from __future__ import annotations

from typing import Any

from rag_cti.config import Settings
from rag_cti.knowledge import agent_tools
from rag_cti.knowledge.fact_store import FactStoreProto

_SYSTEM = """You are a CTI analyst agent. Decide for yourself how to answer each question \
using the tools below. There is no fixed script — reason about what you still need before \
each call, and revise your plan as you learn.

Tools:
- resolve_entity(name): a CTI name like "APT29" -> entity_id(s). The graph tools need an entity_id, not a raw name.
- graph_outline(entity_id): which relation categories an entity has and how many of each. A coverage map / completeness gauge.
- graph_query(subject_id, predicate, object_type): the exact, exhaustive facts in one category, with a total count.
- facts_for_evidence(chunk_id): which facts a given evidence chunk supports.
- vector_search(query): semantic search over source prose, for explanation/context the graph does not hold.

Principles (not a sequence):
- The graph is exact and exhaustive: good for who/what/enumerate and for knowing how much exists. Vector is prose: good for why/how/explain. Pick what each question needs.
- Plan your own steps. Some questions need one tool, some need several, some need you to revisit the graph after reading prose, or to query two entities and compare. Some need no tool at all.
- Before claiming you listed everything, check your count against the graph's total. Never claim completeness you do not have.
- Cite fact_ids and chunk_ids. Surface conflicting facts as a disagreement; never silently pick one."""


def build_model(settings: Settings) -> Any:
    """DeepSeek (OpenAI-compatible) chat model bound for tool calling; temperature 0.

    ``max_retries`` / ``timeout`` are set explicitly (LangChain's default is max_retries=2
    with NO timeout — an unbounded hang source for the gather/judge model under a stalled
    or rate-limited provider). Bounded here so a persistent 429 fails fast into the loop's
    graceful-degradation path instead of stalling a gather burst."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key=settings.deepseek_api_key,
        temperature=0,
        max_retries=settings.llm_max_retries,
        timeout=settings.deepseek_request_timeout,
    )


def build_agent(
    fact_store: FactStoreProto,
    ontology_nodes: list[dict[str, Any]],
    search: agent_tools.VectorSearch,
    model: Any,
) -> Any:
    """Build the ReAct agent with the five in-process tools bound."""
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent

    @tool
    def resolve_entity(name: str) -> list[dict[str, str]]:
        """Resolve a threat-intel name (e.g. 'APT29', 'Lazarus Group') to entity_id candidates."""
        return agent_tools.resolve_entity_candidates(name, ontology_nodes)

    @tool
    def graph_outline(entity_id: str) -> dict[str, Any]:
        """Coverage map for an entity: which relation categories exist and how many."""
        return agent_tools.outline_summary(fact_store, entity_id)

    @tool
    def graph_query(
        subject_id: str,
        predicate: str | None = None,
        object_type: str | None = None,
        min_credibility: float = 0.0,
    ) -> dict[str, Any]:
        """Enumerate facts for (subject_id[, predicate, object_type]); returns total + object summaries."""
        return agent_tools.query_summary(
            fact_store,
            subject_id=subject_id,
            predicate=predicate,
            object_type=object_type,
            min_credibility=min_credibility,
        )

    @tool
    def facts_for_evidence(chunk_id: str) -> dict[str, Any]:
        """Facts supported by a given evidence chunk_id (reverse provenance bridge)."""
        return agent_tools.facts_for_evidence_summary(fact_store, chunk_id)

    @tool
    def vector_search(query: str, top_k: int = 5) -> dict[str, Any]:
        """Semantic search over source prose; returns chunk snippets for why/how questions."""
        return agent_tools.vector_search_summary(search, query, top_k)

    tools = [resolve_entity, graph_outline, graph_query, facts_for_evidence, vector_search]
    return create_react_agent(model, tools, prompt=_SYSTEM)


def ask(query: str, *, recursion_limit: int = 16) -> str:
    """NL question -> cited prose answer via the agentic loop (graph + vector)."""
    from rag_cti.bootstrap import load_ontology_nodes
    from rag_cti.config import get_settings
    from rag_cti.knowledge.fact_store import Neo4jFactStore

    settings = get_settings()
    fact_store = Neo4jFactStore.connect(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password.get_secret_value(),
        settings.neo4j_database,
    )

    def search(text: str, top_k: int) -> Any:
        import rag_cti

        return rag_cti.query(text, top_k=top_k)

    try:
        agent = build_agent(fact_store, load_ontology_nodes(), search, build_model(settings))
        result = agent.invoke(
            {"messages": [("user", query)]}, config={"recursion_limit": recursion_limit}
        )
        final = result["messages"][-1]
        return str(getattr(final, "content", final))
    finally:
        fact_store.close()
