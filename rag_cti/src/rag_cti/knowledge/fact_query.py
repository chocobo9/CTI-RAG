"""facts() orchestration — graph query + citation-content fill (M4 §5).

Pure orchestration over a :class:`FactStoreProto` + an evidence fetcher, so it
unit-tests with in-memory fakes (no Neo4j / Qdrant). The graph emits structure;
the fetcher fills citation content from the chunk store — keeping the M4 split
(graph = structure, vector bridge = content) explicit.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from rag_cti.knowledge.fact_store import FactStoreProto
from rag_cti.types import Chunk, FactQueryResult, FactRow

EvidenceFetcher = Callable[[list[str]], dict[str, Chunk]]


def fill_citation_content(rows: tuple[FactRow, ...], fetch: EvidenceFetcher) -> tuple[FactRow, ...]:
    """Fill each citation's ``content`` from the chunk store; absent ids stay "" ."""
    evidence_ids = sorted({c.evidence_id for row in rows for c in row.citations})
    chunks = fetch(evidence_ids) if evidence_ids else {}
    if not chunks:
        return rows
    filled: list[FactRow] = []
    for row in rows:
        citations = tuple(
            c.model_copy(update={"content": chunks[c.evidence_id].content})
            if c.evidence_id in chunks
            else c
            for c in row.citations
        )
        filled.append(row.model_copy(update={"citations": citations}))
    return tuple(filled)


def run_fact_query(
    fact_store: FactStoreProto,
    fetch: EvidenceFetcher,
    *,
    subject_id: str,
    predicate: str | None = None,
    object_type: str | None = None,
    min_credibility: float = 0.0,
) -> FactQueryResult:
    """Enumerate a (subject[, predicate, object_type]) category, expand citations."""
    start = time.perf_counter()
    rows = fact_store.graph_query(
        subject_id=subject_id,
        predicate=predicate,
        object_type=object_type,
        min_credibility=min_credibility,
    )
    rows = fill_citation_content(rows, fetch)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    query_repr = " ".join(p for p in (subject_id, predicate, object_type) if p)
    return FactQueryResult(
        query_repr=query_repr,
        subject_id=subject_id,
        predicate=predicate,
        object_type=object_type,
        facts=rows,
        fact_query_ms=elapsed_ms,
    )
