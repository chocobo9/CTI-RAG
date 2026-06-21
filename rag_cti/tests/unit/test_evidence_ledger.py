"""Unit tests for the EvidenceLedger (knowledge.evidence_ledger)."""

from __future__ import annotations

from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.types import Chunk, FactRow, GraphOutline, QueryResult, RetrievalResult


def _chunk(cid: str, content: str = "body") -> Chunk:
    return Chunk(id=cid, parent_doc_id="d", source="otx", content=content, chunk_index=0)


def _result(cid: str, score: float) -> RetrievalResult:
    return RetrievalResult(document=_chunk(cid), score=score, rank=0, retriever_source="dense")


def _qr(*results: RetrievalResult) -> QueryResult:
    return QueryResult(
        query="q", results=list(results), total_retrieved=len(results), retrieval_ms=1.0
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
        aggregate_credibility=0.9,
        conflict=conflict,
    )


def test_add_query_result_dedups_and_keeps_higher_score() -> None:
    led = EvidenceLedger()
    assert led.add_query_result(_qr(_result("c1", 0.5), _result("c2", 0.7))) == 2
    # re-add c1 with a higher score, plus a new c3 -> only c3 counts as new
    assert led.add_query_result(_qr(_result("c1", 0.9), _result("c3", 0.4))) == 1
    assert led.chunks["c1"].score == 0.9
    assert set(led.chunks) == {"c1", "c2", "c3"}


def test_add_query_result_lower_score_does_not_replace() -> None:
    led = EvidenceLedger()
    led.add_query_result(_qr(_result("c1", 0.9)))
    assert led.add_query_result(_qr(_result("c1", 0.2))) == 0
    assert led.chunks["c1"].score == 0.9


def test_add_facts_dedups_by_fact_id() -> None:
    led = EvidenceLedger()
    assert led.add_facts((_row("f1"), _row("f2"))) == 2
    assert led.add_facts((_row("f1"), _row("f3"))) == 1
    assert set(led.facts) == {"f1", "f2", "f3"}


def test_real_id_set_is_chunks_union_facts() -> None:
    led = EvidenceLedger()
    led.add_query_result(_qr(_result("c1", 0.5)))
    led.add_facts((_row("f1"),))
    assert led.real_id_set == frozenset({"c1", "f1"})


def test_union_query_result_orders_by_score_and_renumbers_ranks() -> None:
    led = EvidenceLedger()
    led.add_query_result(_qr(_result("c1", 0.3), _result("c2", 0.9), _result("c3", 0.6)))
    qr = led.union_query_result("q")
    assert [r.document.id for r in qr.results] == ["c2", "c3", "c1"]
    assert [r.rank for r in qr.results] == [0, 1, 2]
    assert qr.total_retrieved == 3


def test_union_query_result_respects_limit() -> None:
    led = EvidenceLedger()
    led.add_query_result(_qr(_result("c1", 0.3), _result("c2", 0.9), _result("c3", 0.6)))
    qr = led.union_query_result("q", limit=2)
    assert [r.document.id for r in qr.results] == ["c2", "c3"]  # top-2 by score
    assert qr.total_retrieved == 2


def test_add_outline_records_by_entity_id() -> None:
    led = EvidenceLedger()
    outline = GraphOutline(entity_id="actor_G0016", entity_name="APT29", entity_type="actor")
    led.add_outline(outline)
    assert led.outlines["actor_G0016"] is outline


def test_conflicts_filters_conflict_flag() -> None:
    led = EvidenceLedger()
    led.add_facts((_row("f1", conflict=True), _row("f2")))
    assert tuple(r.fact_id for r in led.conflicts()) == ("f1",)


def test_merge_unions_chunks_facts_and_outlines() -> None:
    master = EvidenceLedger()
    master.add_query_result(_qr(_result("c1", 0.5)))
    master.add_facts((_row("f1"),))

    branch = EvidenceLedger()
    branch.add_query_result(_qr(_result("c2", 0.4)))
    branch.add_facts((_row("f2"),))
    branch.add_outline(
        GraphOutline(entity_id="actor_G0007", entity_name="APT28", entity_type="actor")
    )

    master.merge(branch)
    assert set(master.chunks) == {"c1", "c2"}
    assert set(master.facts) == {"f1", "f2"}
    assert "actor_G0007" in master.outlines
    assert master.real_id_set == frozenset({"c1", "c2", "f1", "f2"})


def test_merge_keeps_higher_score_on_chunk_collision() -> None:
    master = EvidenceLedger()
    master.add_query_result(_qr(_result("c1", 0.3)))
    branch = EvidenceLedger()
    branch.add_query_result(_qr(_result("c1", 0.9)))
    master.merge(branch)
    assert master.chunks["c1"].score == 0.9


def test_merge_fact_collision_dedups_by_fact_id() -> None:
    master = EvidenceLedger()
    master.add_facts((_row("f1"),))
    branch = EvidenceLedger()
    branch.add_facts((_row("f1"),))
    master.merge(branch)
    assert set(master.facts) == {"f1"}
