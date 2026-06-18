"""v1 agent tool logic — backend-free functions the LangChain @tools wrap.

Kept separate from the LangGraph wiring so the tool logic unit-tests with fakes
(no langgraph / LLM). Critically this is where the §9.4 #1 context strategy lives:
``query_summary`` returns object names + ids + a total **count**, NOT the 223 full
facts with citations — keeping the LLM context bounded. Full facts/citations are
fetched by id only at synthesize time (reuse v0 ``facts()`` / ``get_by_chunk_ids``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rag_cti.knowledge.fact_store import FactStoreProto
from rag_cti.preprocess.entity_registry import resolve_entity_ids_strict

# Subject-capable entity types resolve_entity tries (NL name -> entity_id).
_SUBJECT_TYPES = ("actor", "family", "campaign", "technique")

VectorSearch = Callable[[str, int], Any]  # (query, top_k) -> object with .results


def resolve_entity_candidates(
    name: str,
    ontology_nodes: list[dict[str, Any]],
    types: tuple[str, ...] = _SUBJECT_TYPES,
) -> list[dict[str, str]]:
    """NL name -> entity_id candidates (strict, exact-only across subject types).

    Empty list = unresolved (agent should clarify); >1 = ambiguous (agent picks /
    asks). Never guesses an id — a wrong subject would query the wrong graph node.
    """
    seen: dict[str, str] = {}
    for etype in types:
        for entity_id in resolve_entity_ids_strict([(name, etype)], ontology_nodes):
            seen.setdefault(entity_id, etype)
    return [{"entity_id": eid, "matched_type": t} for eid, t in seen.items()]


def outline_summary(fact_store: FactStoreProto, entity_id: str) -> dict[str, Any]:
    """Coverage map as numbers — the agent's planning/sufficiency gauge (§9.4)."""
    outline = fact_store.graph_outline(entity_id)
    if outline is None:
        return {"found": False, "entity_id": entity_id}
    return {
        "found": True,
        "entity_id": outline.entity_id,
        "entity_name": outline.entity_name,
        "entity_type": outline.entity_type,
        "outgoing": [
            {"predicate": e.predicate, "object_type": e.other_type, "count": e.count}
            for e in outline.outgoing
        ],
        "incoming": [
            {"predicate": e.predicate, "subject_type": e.other_type, "count": e.count}
            for e in outline.incoming
        ],
    }


def query_summary(
    fact_store: FactStoreProto,
    *,
    subject_id: str,
    predicate: str | None = None,
    object_type: str | None = None,
    min_credibility: float = 0.0,
    limit: int = 50,
) -> dict[str, Any]:
    """Enumerate a category, return a SUMMARY (object names + ids + total), NOT full
    citations (§9.4 #1 — bound the LLM context). ``total`` lets the agent compare
    coverage; full facts are fetched by fact_id at synthesize."""
    rows = fact_store.graph_query(
        subject_id=subject_id,
        predicate=predicate,
        object_type=object_type,
        min_credibility=min_credibility,
    )
    shown = rows[:limit]
    return {
        "total": len(rows),
        "shown": len(shown),
        "truncated": len(rows) > len(shown),
        "objects": [
            {
                "object_name": r.object_name,
                "object_id": r.object_id,
                "object_type": r.object_type,
                "credibility": r.aggregate_credibility,
                "conflict": r.conflict,
                "fact_id": r.fact_id,
            }
            for r in shown
        ],
    }


def facts_for_evidence_summary(fact_store: FactStoreProto, evidence_id: str) -> dict[str, Any]:
    """Reverse bridge: a chunk -> the facts it supports (provenance for content)."""
    rows = fact_store.facts_for_evidence(evidence_id)
    return {
        "count": len(rows),
        "facts": [
            {
                "subject_name": r.subject_name,
                "predicate": r.predicate,
                "object_name": r.object_name,
                "fact_id": r.fact_id,
            }
            for r in rows
        ],
    }


def vector_search_summary(search: VectorSearch, query: str, top_k: int = 5) -> dict[str, Any]:
    """Vector content as snippets (the agent decides if it needs full chunks later)."""
    result = search(query, top_k)
    return {
        "chunks": [
            {
                "chunk_id": r.document.id,
                "source": r.document.source,
                "snippet": r.document.content[:240].replace("\n", " "),
            }
            for r in result.results
        ]
    }
