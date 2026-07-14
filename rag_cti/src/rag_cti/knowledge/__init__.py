"""M4 consumption layer — knowledge-graph query tools over the Neo4j fact graph.

Backend-free contract (:class:`FactStoreProto`) + the Neo4j implementation. These
are the deterministic tools the v1 agent will call; v0 exercises them via the
``facts`` CLI with structured params. Historical rationale is retained in
docs/archive/runtime/HISTORICAL_M4_consumption_langgraph_design.md.
"""

from rag_cti.knowledge.fact_store import FactStoreProto, Neo4jFactStore

__all__ = ["FactStoreProto", "Neo4jFactStore"]
