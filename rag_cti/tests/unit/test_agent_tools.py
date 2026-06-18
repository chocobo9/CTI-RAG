"""Unit tests for v1 agent tool logic (knowledge.agent_tools)."""

from __future__ import annotations

from typing import Any

import pytest

from rag_cti.knowledge import agent_tools
from rag_cti.types import (
    Chunk,
    FactRow,
    GraphOutline,
    OutlineEntry,
    QueryResult,
    RetrievalResult,
)


def _row(fact_id: str, *, conflict: bool = False) -> FactRow:
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
    )


class _FakeFactStore:
    def __init__(self, outline: GraphOutline | None = None, rows: tuple[FactRow, ...] = ()) -> None:
        self._outline = outline
        self._rows = rows

    def graph_outline(self, entity_id: str) -> GraphOutline | None:
        return self._outline

    def graph_query(self, **kwargs: Any) -> tuple[FactRow, ...]:
        return self._rows

    def facts_for_evidence(self, evidence_id: str) -> tuple[FactRow, ...]:
        return self._rows

    def close(self) -> None:
        pass


def test_resolve_entity_candidates_resolves_and_dedups(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_strict(mentions: list[tuple[str, str]], nodes: object) -> list[str]:
        name, etype = mentions[0]
        return ["actor_G0016"] if (name == "APT29" and etype == "actor") else []

    monkeypatch.setattr(agent_tools, "resolve_entity_ids_strict", fake_strict)
    assert agent_tools.resolve_entity_candidates("APT29", []) == [
        {"entity_id": "actor_G0016", "matched_type": "actor"}
    ]


def test_resolve_entity_candidates_unresolved_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_tools, "resolve_entity_ids_strict", lambda m, n: [])
    assert agent_tools.resolve_entity_candidates("nonsense", []) == []


def test_outline_summary_maps_numbers() -> None:
    outline = GraphOutline(
        entity_id="actor_G0016",
        entity_name="APT29",
        entity_type="actor",
        outgoing=(
            OutlineEntry(predicate="uses", other_type="technique", count=173, max_credibility=0.97),
        ),
        incoming=(
            OutlineEntry(
                predicate="attributed-to", other_type="campaign", count=2, max_credibility=0.9
            ),
        ),
    )
    out = agent_tools.outline_summary(_FakeFactStore(outline=outline), "actor_G0016")
    assert out["found"] is True
    assert out["entity_name"] == "APT29"
    assert out["outgoing"][0] == {"predicate": "uses", "object_type": "technique", "count": 173}
    assert out["incoming"][0] == {
        "predicate": "attributed-to",
        "subject_type": "campaign",
        "count": 2,
    }


def test_outline_summary_not_found() -> None:
    out = agent_tools.outline_summary(_FakeFactStore(outline=None), "actor_X")
    assert out == {"found": False, "entity_id": "actor_X"}


def test_query_summary_truncates_and_reports_total() -> None:
    rows = tuple(_row(f"f{i}") for i in range(60))
    out = agent_tools.query_summary(_FakeFactStore(rows=rows), subject_id="actor_G0016", limit=50)
    assert out["total"] == 60
    assert out["shown"] == 50
    assert out["truncated"] is True
    assert len(out["objects"]) == 50
    assert out["objects"][0]["fact_id"] == "f0"


def test_facts_for_evidence_summary() -> None:
    out = agent_tools.facts_for_evidence_summary(_FakeFactStore(rows=(_row("f1"),)), "chunk1")
    assert out["count"] == 1
    assert out["facts"][0]["predicate"] == "uses"


def test_vector_search_summary() -> None:
    chunk = Chunk(id="c1", parent_doc_id="d", source="otx", content="body text", chunk_index=0)
    qr = QueryResult(
        query="q",
        results=[RetrievalResult(document=chunk, score=0.9, rank=0, retriever_source="dense")],
        total_retrieved=1,
        retrieval_ms=1.0,
    )
    out = agent_tools.vector_search_summary(lambda q, k: qr, "query")
    assert out["chunks"][0] == {"chunk_id": "c1", "source": "otx", "snippet": "body text"}
