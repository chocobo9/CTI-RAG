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

_SYSTEM = """You are a CTI analyst agent. Answer threat-intelligence questions by \
orchestrating a knowledge graph (exact, exhaustive controlled facts) and vector \
search (source prose). Workflow:
1. resolve_entity: turn a name (e.g. "APT29") into an entity_id before any graph call.
2. graph_outline: see which relation categories exist for that entity and HOW MANY \
(this is your coverage map / completeness gauge).
3. For enumerate/who/what questions, graph_query the relevant category. It returns a \
`total` and object summaries. Compare what you covered against `total` — do NOT claim \
completeness if you covered fewer than total.
4. Use vector_search ONLY for prose/explanation (why/how) the graph cannot give.
5. Answer concisely. Cite fact_ids and chunk_ids. Surface conflict=true facts as \
"sources disagree", never silently pick one.
Prefer the graph for who/what/enumerate; vector for why/how/explain."""


def build_model(settings: Settings) -> Any:
    """DeepSeek (OpenAI-compatible) chat model bound for tool calling; temperature 0."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key=settings.deepseek_api_key,
        temperature=0,
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
