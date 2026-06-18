"""Unit tests for the M4 facts() orchestration (knowledge.fact_query)."""

from __future__ import annotations

from rag_cti.knowledge.fact_query import fill_citation_content, run_fact_query
from rag_cti.types import Chunk, FactCitation, FactRow, GraphOutline


def _citation(evidence_id: str) -> FactCitation:
    return FactCitation(
        evidence_id=evidence_id, origin="mitre", confidence=0.9, label_availability="direct"
    )


def _row(
    fact_id: str, *, conflict: bool = False, citations: tuple[FactCitation, ...] = ()
) -> FactRow:
    return FactRow(
        fact_id=fact_id,
        subject_id="actor_G0016",
        subject_name="APT29",
        predicate="uses",
        object_id="technique_T1566",
        object_name="Phishing",
        object_type="technique",
        aggregate_credibility=0.95,
        conflict=conflict,
        distinct_origins=("mitre",),
        support_count=len(citations),
        citations=citations,
    )


def _chunk(chunk_id: str, content: str) -> Chunk:
    return Chunk(id=chunk_id, parent_doc_id="doc", source="mitre", content=content, chunk_index=0)


class _FakeFactStore:
    def __init__(self, rows: tuple[FactRow, ...]) -> None:
        self._rows = rows
        self.last_kwargs: dict[str, object] = {}

    def graph_query(self, **kwargs: object) -> tuple[FactRow, ...]:
        self.last_kwargs = kwargs
        return self._rows

    def graph_outline(self, entity_id: str) -> GraphOutline | None:
        return None

    def facts_for_evidence(self, evidence_id: str) -> tuple[FactRow, ...]:
        return ()

    def close(self) -> None:
        pass


def test_fill_citation_content_fills_from_fetch() -> None:
    rows = (_row("f1", citations=(_citation("e1"),)),)
    out = fill_citation_content(rows, lambda ids: {"e1": _chunk("e1", "phishing email body")})
    assert out[0].citations[0].content == "phishing email body"


def test_fill_citation_content_missing_chunk_stays_empty() -> None:
    # An evidence_id absent from the store must yield "" — never fabricated.
    rows = (_row("f1", citations=(_citation("e1"), _citation("missing"))),)
    out = fill_citation_content(rows, lambda ids: {"e1": _chunk("e1", "body")})
    by_id = {c.evidence_id: c.content for c in out[0].citations}
    assert by_id == {"e1": "body", "missing": ""}


def test_fill_citation_content_no_evidence_returns_rows_unchanged() -> None:
    rows = (_row("f1"),)
    assert fill_citation_content(rows, lambda ids: {}) == rows


def test_run_fact_query_assembles_result_and_surfaces_conflicts() -> None:
    store = _FakeFactStore((_row("f1"), _row("f2", conflict=True)))
    result = run_fact_query(
        store, lambda ids: {}, subject_id="actor_G0016", predicate="uses", object_type="technique"
    )
    assert result.subject_id == "actor_G0016"
    assert result.query_repr == "actor_G0016 uses technique"
    assert len(result.facts) == 2
    assert tuple(f.fact_id for f in result.conflicts) == ("f2",)
    assert store.last_kwargs["min_credibility"] == 0.0
