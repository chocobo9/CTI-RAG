"""v1 agent tool logic — backend-free functions the LangChain @tools wrap.

Kept separate from the LangGraph wiring so the tool logic unit-tests with fakes
(no langgraph / LLM). Two responsibilities:

1. **Bounded summaries** (§9.4 #1 context strategy): ``summarize_*`` turn full
   graph/vector results into the small object the LLM sees — names + ids + a total
   **count**, NOT the 223 full facts with citations.
2. **Ledger-aware adapters** (agentic plan): ``*_to_ledger`` call the underlying
   tool once, append the **full** structured result to the per-run
   :class:`~rag_cti.knowledge.evidence_ledger.EvidenceLedger`, and return the
   bounded summary — so the hard-rail nodes see untruncated evidence while the LLM
   context stays bounded.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.knowledge.fact_store import FactStoreProto
from rag_cti.preprocess.entity_registry import resolve_entity_ids_strict
from rag_cti.types import FactRow, GraphOutline, QueryResult, RetrievalResult

# Subject-capable entity types resolve_entity tries (NL name -> entity_id).
_SUBJECT_TYPES = ("actor", "family", "campaign", "technique")

# (query, top_k) -> object with .results  /  (query, top_k) -> QueryResult
VectorSearch = Callable[[str, int], Any]
RunRetrieve = Callable[[str, int], QueryResult]


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


# ---------------------------------------------------------------------------
# Pure summarizers — full result -> bounded LLM-facing dict
# ---------------------------------------------------------------------------


def summarize_outline(outline: GraphOutline | None, entity_id: str) -> dict[str, Any]:
    """Coverage map as numbers — the agent's planning/sufficiency hint."""
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


def summarize_rows(rows: tuple[FactRow, ...], limit: int = 50) -> dict[str, Any]:
    """Enumerate a category as a SUMMARY (object names + ids + total), NOT full
    citations (§9.4 #1 — bound the LLM context). ``total`` lets the agent compare
    coverage; full rows live in the ledger and are fetched by id at synthesize."""
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


def summarize_facts_for_evidence(rows: tuple[FactRow, ...]) -> dict[str, Any]:
    """Reverse bridge: the facts a chunk supports (provenance for content)."""
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


def summarize_chunks(results: list[RetrievalResult]) -> dict[str, Any]:
    """Vector content as snippets (the agent decides if it needs full chunks later)."""
    return {
        "chunks": [
            {
                "chunk_id": r.document.id,
                "source": r.document.source,
                "snippet": r.document.content[:240].replace("\n", " "),
            }
            for r in results
        ]
    }


# ---------------------------------------------------------------------------
# v0 tool wrappers (deterministic; used by the `facts` CLI path and unit tests)
# ---------------------------------------------------------------------------


def outline_summary(fact_store: FactStoreProto, entity_id: str) -> dict[str, Any]:
    return summarize_outline(fact_store.graph_outline(entity_id), entity_id)


def query_summary(
    fact_store: FactStoreProto,
    *,
    subject_id: str,
    predicate: str | None = None,
    object_type: str | None = None,
    min_credibility: float = 0.0,
    limit: int = 50,
) -> dict[str, Any]:
    rows = fact_store.graph_query(
        subject_id=subject_id,
        predicate=predicate,
        object_type=object_type,
        min_credibility=min_credibility,
    )
    return summarize_rows(rows, limit)


def facts_for_evidence_summary(fact_store: FactStoreProto, evidence_id: str) -> dict[str, Any]:
    return summarize_facts_for_evidence(fact_store.facts_for_evidence(evidence_id))


def vector_search_summary(search: VectorSearch, query: str, top_k: int = 5) -> dict[str, Any]:
    return summarize_chunks(search(query, top_k).results)


# ---------------------------------------------------------------------------
# Ledger-aware adapters — append full structured evidence, return bounded summary
# ---------------------------------------------------------------------------


def retrieve_to_ledger(
    run: RunRetrieve, ledger: EvidenceLedger, query: str, top_k: int = 10
) -> dict[str, Any]:
    """Vector retrieve: append the QueryResult to the ledger, return chunk snippets."""
    qr = run(query, top_k)
    ledger.add_query_result(qr)
    return summarize_chunks(qr.results)


def graph_query_to_ledger(
    fact_store: FactStoreProto,
    ledger: EvidenceLedger,
    *,
    subject_id: str,
    predicate: str | None = None,
    object_type: str | None = None,
    min_credibility: float = 0.0,
    limit: int = 50,
) -> dict[str, Any]:
    """Enumerate one category once: append the FULL rows to the ledger, return the
    bounded summary (avoids the v0 double-query of querying then re-summarizing).

    The full rows are in the ledger and reach synthesis, so the bounded ``shown``
    preview is NOT a reason to re-query. We therefore drop the misleading
    ``truncated`` flag (which made the gather loop re-query for "more" it already
    held) and return an explicit completeness signal instead."""
    rows = fact_store.graph_query(
        subject_id=subject_id,
        predicate=predicate,
        object_type=object_type,
        min_credibility=min_credibility,
    )
    ledger.add_facts(rows)
    summary = summarize_rows(rows, limit)
    total = summary["total"]
    return {
        "total": total,
        "shown": summary["shown"],
        "objects": summary["objects"],
        "complete": True,
        "note": (
            f"All {total} facts for this query are recorded and available when "
            "composing the answer — this is the complete set; do not query this "
            "category again."
        ),
    }


def outline_to_ledger(
    fact_store: FactStoreProto, ledger: EvidenceLedger, entity_id: str
) -> dict[str, Any]:
    """Coverage map: record it as a sufficiency hint, return the numbers summary."""
    outline = fact_store.graph_outline(entity_id)
    if outline is not None:
        ledger.add_outline(outline)
    return summarize_outline(outline, entity_id)


def facts_for_evidence_to_ledger(
    fact_store: FactStoreProto, ledger: EvidenceLedger, evidence_id: str
) -> dict[str, Any]:
    """Reverse bridge: append the supported facts to the ledger, return the summary."""
    rows = fact_store.facts_for_evidence(evidence_id)
    ledger.add_facts(rows)
    return summarize_facts_for_evidence(rows)
