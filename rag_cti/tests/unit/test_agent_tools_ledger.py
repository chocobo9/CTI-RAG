"""Unit tests for the ledger-aware tool adapters (knowledge.agent_tools.*_to_ledger)."""

from __future__ import annotations

from typing import Any

from rag_cti.knowledge import agent_tools
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.types import (
    Chunk,
    FactRow,
    GraphOutline,
    OutlineEntry,
    QueryResult,
    RetrievalResult,
)


def _row(fact_id: str) -> FactRow:
    return FactRow(
        fact_id=fact_id,
        subject_id="actor_G0016",
        subject_name="APT29",
        predicate="uses",
        object_id="technique_T1566",
        object_name="Phishing",
        object_type="technique",
        aggregate_credibility=0.9,
        conflict=False,
    )


def _qr(cid: str) -> QueryResult:
    chunk = Chunk(id=cid, parent_doc_id="d", source="otx", content="body text", chunk_index=0)
    return QueryResult(
        query="q",
        results=[RetrievalResult(document=chunk, score=0.9, rank=0, retriever_source="dense")],
        total_retrieved=1,
        retrieval_ms=1.0,
    )


class _CountingFactStore:
    """Records graph_query call count — the adapter must hit the store exactly once."""

    def __init__(self, rows: tuple[FactRow, ...] = (), outline: GraphOutline | None = None) -> None:
        self._rows = rows
        self._outline = outline
        self.graph_query_calls = 0

    def graph_query(self, **kwargs: Any) -> tuple[FactRow, ...]:
        self.graph_query_calls += 1
        return self._rows

    def graph_outline(self, entity_id: str) -> GraphOutline | None:
        return self._outline

    def facts_for_evidence(self, evidence_id: str) -> tuple[FactRow, ...]:
        return self._rows

    def close(self) -> None:
        pass


def test_retrieve_to_ledger_appends_chunks_and_returns_snippets() -> None:
    led = EvidenceLedger()
    out = agent_tools.retrieve_to_ledger(lambda q, k: _qr("c1"), led, "query", top_k=3)
    assert out["chunks"][0]["chunk_id"] == "c1"
    assert "c1" in led.chunks


def test_graph_query_to_ledger_single_call_full_rows_to_ledger() -> None:
    led = EvidenceLedger()
    store = _CountingFactStore(rows=tuple(_row(f"f{i}") for i in range(60)))
    out = agent_tools.graph_query_to_ledger(store, led, subject_id="actor_G0016", limit=50)
    assert store.graph_query_calls == 1  # one store call, not query-then-resummarize
    assert out["total"] == 60
    assert out["shown"] == 50
    # No misleading "truncated" flag: the FULL set is recorded and reaches synthesis, so
    # the bounded preview is not a reason to re-query — signal completeness instead.
    assert "truncated" not in out
    assert out["complete"] is True
    assert "complete set" in out["note"]
    assert len(led.facts) == 60  # FULL rows in the ledger, untruncated


def test_outline_to_ledger_records_when_found() -> None:
    outline = GraphOutline(
        entity_id="actor_G0016",
        entity_name="APT29",
        entity_type="actor",
        outgoing=(
            OutlineEntry(predicate="uses", other_type="technique", count=5, max_credibility=0.9),
        ),
    )
    led = EvidenceLedger()
    out = agent_tools.outline_to_ledger(_CountingFactStore(outline=outline), led, "actor_G0016")
    assert out["found"] is True
    assert "actor_G0016" in led.outlines


def test_outline_to_ledger_absent_does_not_record() -> None:
    led = EvidenceLedger()
    out = agent_tools.outline_to_ledger(_CountingFactStore(outline=None), led, "actor_X")
    assert out == {"found": False, "entity_id": "actor_X"}
    assert led.outlines == {}


def test_facts_for_evidence_to_ledger_appends() -> None:
    led = EvidenceLedger()
    out = agent_tools.facts_for_evidence_to_ledger(
        _CountingFactStore(rows=(_row("f1"),)), led, "chunk1"
    )
    assert out["count"] == 1
    assert "f1" in led.facts
