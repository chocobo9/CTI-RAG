from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from rag_cti.evaluation.query_set import QueryCategory, QuerySetRecord
from rag_cti.evaluation.retrieval_metrics import (
    CategoryMetrics,
    EvalResult,
    PerQueryResult,
    QuerySetEvalResult,
    _hit_at_k_qs,
    _is_match,
    _is_query_set_match,
    _reciprocal_rank_qs,
    evaluate_on_query_set,
    evaluate_retriever,
    hit_at_k,
    ndcg_at_k,
    reciprocal_rank,
)
from rag_cti.evaluation.techniquerag import TechniqueRAGRecord

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

@dataclass
class _FakeChunk:
    metadata: dict[str, Any]


@dataclass
class _FakeResult:
    document: _FakeChunk


def _result(attack_id: str | None) -> _FakeResult:
    meta = {"attack_id": attack_id} if attack_id is not None else {}
    return _FakeResult(document=_FakeChunk(metadata=meta))


class _FakeRetriever:
    def __init__(self, results: list[_FakeResult]) -> None:
        self._results = results

    def search(self, text: str, top_k: int) -> list[_FakeResult]:
        return self._results[:top_k]


# ---------------------------------------------------------------------------
# _is_match
# ---------------------------------------------------------------------------

def test_is_match_exact() -> None:
    assert _is_match("T1012", "T1012")


def test_is_match_case_insensitive() -> None:
    assert _is_match("t1012", "T1012")


def test_is_match_chunk_is_parent_gold_is_subtechnique() -> None:
    assert _is_match("T1003", "T1003.001")


def test_is_match_chunk_is_subtechnique_gold_is_parent() -> None:
    assert _is_match("T1003.001", "T1003")


def test_is_match_different_techniques() -> None:
    assert not _is_match("T1012", "T1059")


def test_is_match_different_subtechniques_same_parent() -> None:
    assert not _is_match("T1003.001", "T1003.002")


def test_is_match_prefix_not_dot_separated() -> None:
    # T100 should NOT match T1003 — must be separated by "."
    assert not _is_match("T100", "T1003")


# ---------------------------------------------------------------------------
# hit_at_k
# ---------------------------------------------------------------------------

def test_hit_at_k_exact_match_in_top1() -> None:
    results = [_result("T1012")]
    assert hit_at_k(results, ["T1012"], k=1)


def test_hit_at_k_match_beyond_k_is_miss() -> None:
    results = [_result("T1059"), _result("T1012")]
    assert not hit_at_k(results, ["T1012"], k=1)


def test_hit_at_k_match_at_boundary() -> None:
    results = [_result("T1059"), _result("T1012")]
    assert hit_at_k(results, ["T1012"], k=2)


def test_hit_at_k_no_attack_id_in_results() -> None:
    results = [_result(None), _result(None)]
    assert not hit_at_k(results, ["T1012"], k=5)


def test_hit_at_k_multi_gold_any_hit_counts() -> None:
    results = [_result("T1059")]
    assert hit_at_k(results, ["T1012", "T1059"], k=1)


def test_hit_at_k_parent_subtechnique_match() -> None:
    results = [_result("T1003")]
    assert hit_at_k(results, ["T1003.001"], k=1)


def test_hit_at_k_empty_results() -> None:
    assert not hit_at_k([], ["T1012"], k=5)


# ---------------------------------------------------------------------------
# reciprocal_rank
# ---------------------------------------------------------------------------

def test_reciprocal_rank_first_result_match() -> None:
    results = [_result("T1012")]
    assert reciprocal_rank(results, ["T1012"]) == pytest.approx(1.0)


def test_reciprocal_rank_second_result_match() -> None:
    results = [_result("T1059"), _result("T1012")]
    assert reciprocal_rank(results, ["T1012"]) == pytest.approx(0.5)


def test_reciprocal_rank_no_match() -> None:
    results = [_result("T1059"), _result("T1566")]
    assert reciprocal_rank(results, ["T1012"]) == 0.0


def test_reciprocal_rank_none_attack_id_skipped() -> None:
    results = [_result(None), _result("T1012")]
    assert reciprocal_rank(results, ["T1012"]) == pytest.approx(0.5)


def test_reciprocal_rank_empty_results() -> None:
    assert reciprocal_rank([], ["T1012"]) == 0.0


# ---------------------------------------------------------------------------
# evaluate_retriever
# ---------------------------------------------------------------------------

def test_evaluate_retriever_all_hits() -> None:
    dataset = [
        TechniqueRAGRecord(text="query1", gold_ids=["T1012"]),
        TechniqueRAGRecord(text="query2", gold_ids=["T1059"]),
    ]
    _query_map = {"query1": "T1012", "query2": "T1059"}

    class _MatchingRetriever:
        def search(self, text: str, top_k: int) -> list[_FakeResult]:
            return [_result(_query_map[text])]

    result = evaluate_retriever(_MatchingRetriever(), dataset, config="test", k_values=(1, 5))
    assert result.top_k[1] == pytest.approx(1.0)
    assert result.mrr == pytest.approx(1.0)
    assert result.n_queries == 2


def test_evaluate_retriever_no_hits() -> None:
    dataset = [TechniqueRAGRecord(text="query1", gold_ids=["T1012"])]
    retriever = _FakeRetriever([_result("T9999")])
    result = evaluate_retriever(retriever, dataset, config="test", k_values=(1,))
    assert result.top_k[1] == 0.0
    assert result.mrr == 0.0


def test_evaluate_retriever_config_label_preserved() -> None:
    dataset = [TechniqueRAGRecord(text="q", gold_ids=["T1012"])]
    retriever = _FakeRetriever([_result("T1012")])
    result = evaluate_retriever(retriever, dataset, config="hybrid+hyde", k_values=(1,))
    assert result.config == "hybrid+hyde"


def test_evaluate_retriever_k_values_in_result() -> None:
    dataset = [TechniqueRAGRecord(text="q", gold_ids=["T1012"])]
    retriever = _FakeRetriever([_result("T1012")])
    result = evaluate_retriever(retriever, dataset, config="dense", k_values=(1, 5, 10))
    assert result.k_values == [1, 5, 10]


def test_evaluate_retriever_empty_dataset() -> None:
    retriever = _FakeRetriever([])
    result = evaluate_retriever(retriever, [], config="dense", k_values=(1,))
    assert result.n_queries == 0
    assert result.top_k[1] == 0.0
    assert result.mrr == 0.0


def test_evaluate_retriever_returns_eval_result() -> None:
    dataset = [TechniqueRAGRecord(text="q", gold_ids=["T1012"])]
    retriever = _FakeRetriever([_result("T1012")])
    result = evaluate_retriever(retriever, dataset, config="dense", k_values=(1,))
    assert isinstance(result, EvalResult)


def test_evaluate_retriever_logs_progress_at_50_records() -> None:
    dataset = [TechniqueRAGRecord(text=f"q{i}", gold_ids=["T1012"]) for i in range(51)]
    retriever = _FakeRetriever([_result("T1012")])
    result = evaluate_retriever(retriever, dataset, config="dense", k_values=(1,))
    assert result.n_queries == 51


# ---------------------------------------------------------------------------
# ndcg_at_k
# ---------------------------------------------------------------------------

def _always_rel(r: object) -> bool:
    return True


def _never_rel(r: object) -> bool:
    return False


def test_ndcg_at_k_perfect_single_hit() -> None:
    assert ndcg_at_k(["r1"], _always_rel, k=1, n_relevant=1) == pytest.approx(1.0)


def test_ndcg_at_k_no_hits_returns_zero() -> None:
    assert ndcg_at_k(["r1", "r2"], _never_rel, k=5, n_relevant=1) == 0.0


def test_ndcg_at_k_hit_at_rank_2_less_than_1() -> None:
    results = ["miss", "hit"]
    calls = iter([False, True])
    score = ndcg_at_k(results, lambda r: next(calls), k=2, n_relevant=1)
    assert 0.0 < score < 1.0


def test_ndcg_at_k_empty_results_returns_zero() -> None:
    assert ndcg_at_k([], _always_rel, k=5, n_relevant=1) == 0.0


def test_ndcg_at_k_truncates_to_k() -> None:
    results = ["r1", "r2", "r3"]
    calls = iter([False, False, True])
    score = ndcg_at_k(results, lambda r: next(calls), k=2, n_relevant=1)
    assert score == 0.0


# ---------------------------------------------------------------------------
# Query-set stubs
# ---------------------------------------------------------------------------

@dataclass
class _FakeQSDoc:
    id: str
    source: str
    metadata: dict  # type: ignore[type-arg]


@dataclass
class _FakeQSResult:
    document: _FakeQSDoc


def _qs_result(
    chunk_id: str = "chunk1",
    source: str = "mitre",
    attack_id: str | None = None,
) -> _FakeQSResult:
    meta = {"attack_id": attack_id} if attack_id else {}
    return _FakeQSResult(document=_FakeQSDoc(id=chunk_id, source=source, metadata=meta))


def _qs_record(
    category: str = "precise",
    expected_ids: list[str] | None = None,
    gold_attack: list[str] | None = None,
    gold_sources: list[str] | None = None,
) -> QuerySetRecord:
    return QuerySetRecord(
        query_id="q1",
        query="test CTI query",
        category=QueryCategory(category),
        expected_chunk_ids=expected_ids or [],
        gold_attack_ids=gold_attack or [],
        gold_sources=gold_sources or [],
        reference_answer=None,
        notes="",
    )


# ---------------------------------------------------------------------------
# _is_query_set_match
# ---------------------------------------------------------------------------

def test_is_qs_match_precise_chunk_id_hit() -> None:
    assert _is_query_set_match(_qs_result("chunk1"), _qs_record(expected_ids=["chunk1"]))


def test_is_qs_match_precise_chunk_id_miss() -> None:
    assert not _is_query_set_match(_qs_result("chunk2"), _qs_record(expected_ids=["chunk1"]))


def test_is_qs_match_fuzzy_source_hit() -> None:
    record = _qs_record("fuzzy", gold_sources=["mitre"])
    assert _is_query_set_match(_qs_result(source="mitre"), record)


def test_is_qs_match_fuzzy_attack_id_hit() -> None:
    record = _qs_record("fuzzy", gold_attack=["T1566"])
    assert _is_query_set_match(_qs_result(attack_id="T1566"), record)


def test_is_qs_match_fuzzy_no_source_no_attack_miss() -> None:
    record = _qs_record("fuzzy", gold_sources=["otx"], gold_attack=["T1012"])
    assert not _is_query_set_match(_qs_result(source="mitre", attack_id=None), record)


def test_is_qs_match_fuzzy_wrong_source_wrong_attack_miss() -> None:
    record = _qs_record("fuzzy", gold_sources=["otx"], gold_attack=["T1012"])
    assert not _is_query_set_match(_qs_result(source="mitre", attack_id="T1059"), record)


# ---------------------------------------------------------------------------
# _hit_at_k_qs / _reciprocal_rank_qs
# ---------------------------------------------------------------------------

def test_hit_at_k_qs_hit_in_top1() -> None:
    record = _qs_record(expected_ids=["chunk1"])
    assert _hit_at_k_qs([_qs_result("chunk1")], record, k=1)


def test_hit_at_k_qs_miss_beyond_k() -> None:
    record = _qs_record(expected_ids=["chunk1"])
    assert not _hit_at_k_qs([_qs_result("chunk2"), _qs_result("chunk1")], record, k=1)


def test_reciprocal_rank_qs_first_rank_is_1() -> None:
    record = _qs_record(expected_ids=["chunk1"])
    assert _reciprocal_rank_qs([_qs_result("chunk1")], record) == pytest.approx(1.0)


def test_reciprocal_rank_qs_second_rank_is_half() -> None:
    record = _qs_record(expected_ids=["chunk1"])
    results = [_qs_result("miss"), _qs_result("chunk1")]
    assert _reciprocal_rank_qs(results, record) == pytest.approx(0.5)


def test_reciprocal_rank_qs_no_match_is_zero() -> None:
    record = _qs_record(expected_ids=["chunk1"])
    assert _reciprocal_rank_qs([_qs_result("other")], record) == 0.0


# ---------------------------------------------------------------------------
# evaluate_on_query_set
# ---------------------------------------------------------------------------

class _FakeQSRetriever:
    def __init__(self, results: list[_FakeQSResult] | None = None) -> None:
        self._results = results or []

    def search(self, query: str, top_k: int) -> list[_FakeQSResult]:
        return self._results[:top_k]


def test_evaluate_on_query_set_returns_query_set_eval_result() -> None:
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("chunk1")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1, 5, 10))
    assert isinstance(result, QuerySetEvalResult)


def test_evaluate_on_query_set_config_preserved() -> None:
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("chunk1")])
    result = evaluate_on_query_set(retriever, records, config="hybrid", k_values=(1,))
    assert result.config == "hybrid"


def test_evaluate_on_query_set_perfect_hit() -> None:
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("chunk1")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1,))
    assert result.overall.mrr == pytest.approx(1.0)
    assert result.overall.top_k[1] == pytest.approx(1.0)


def test_evaluate_on_query_set_no_hit() -> None:
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("other")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1,))
    assert result.overall.mrr == 0.0
    assert result.overall.top_k[1] == 0.0


def test_evaluate_on_query_set_per_category_populated() -> None:
    records = [
        _qs_record("precise", expected_ids=["c1"]),
        _qs_record("fuzzy", gold_sources=["mitre"]),
    ]
    precise_ret = _FakeQSRetriever([_qs_result("c1")])
    result = evaluate_on_query_set(precise_ret, records, config="dense", k_values=(1,))
    assert "precise" in result.by_category
    assert "fuzzy" in result.by_category


def test_evaluate_on_query_set_k_values_in_result() -> None:
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("chunk1")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1, 5, 10))
    assert result.k_values == [1, 5, 10]


def test_evaluate_on_query_set_overall_n_queries_correct() -> None:
    records = [_qs_record(expected_ids=[f"c{i}"]) for i in range(5)]
    retriever = _FakeQSRetriever([_qs_result("c0")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1,))
    assert result.overall.n_queries == 5


# ---------------------------------------------------------------------------
# Per-query results
# ---------------------------------------------------------------------------

def test_per_query_results_populated() -> None:
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("chunk1")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1, 5))
    assert len(result.per_query) == 1


def test_per_query_result_has_required_fields() -> None:
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("chunk1")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1, 5, 10))
    pq = result.per_query[0]
    assert isinstance(pq, PerQueryResult)
    assert pq.query_id == "q1"
    assert pq.query_text == "test CTI query"
    assert pq.category == "precise"
    assert pq.expected_doc_ids == ["chunk1"]
    assert isinstance(pq.retrieved_doc_ids, list)
    assert isinstance(pq.hit_at_k, dict)
    assert isinstance(pq.reciprocal_rank, float)


def test_per_query_hit_at_k_reflects_actual_hits() -> None:
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("miss"), _qs_result("chunk1")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1, 5))
    pq = result.per_query[0]
    assert pq.hit_at_k[1] is False
    assert pq.hit_at_k[5] is True


def test_per_query_target_rank_on_hit() -> None:
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("miss"), _qs_result("chunk1")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1, 5))
    pq = result.per_query[0]
    assert pq.target_rank == 2
    assert pq.reciprocal_rank == pytest.approx(0.5)


def test_per_query_target_rank_none_on_miss() -> None:
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("other")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1,))
    pq = result.per_query[0]
    assert pq.target_rank is None
    assert pq.reciprocal_rank == 0.0


def test_per_query_count_matches_records() -> None:
    records = [
        _qs_record("precise", expected_ids=["c1"]),
        _qs_record("fuzzy", gold_sources=["mitre"]),
        _qs_record("semantic", expected_ids=["c2"]),
    ]
    retriever = _FakeQSRetriever([_qs_result("c1")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1,))
    assert len(result.per_query) == 3


def test_per_query_does_not_change_aggregate_metrics() -> None:
    """Adding per-query logging must not alter aggregate metric values."""
    records = [_qs_record(expected_ids=["chunk1"])]
    retriever = _FakeQSRetriever([_qs_result("chunk1")])
    result = evaluate_on_query_set(retriever, records, config="dense", k_values=(1,))
    assert result.overall.mrr == pytest.approx(1.0)
    assert result.overall.top_k[1] == pytest.approx(1.0)


def test_per_query_default_is_empty_list() -> None:
    """QuerySetEvalResult created without per_query should default to empty list."""
    r = QuerySetEvalResult(
        config="test",
        k_values=[1],
        overall=CategoryMetrics(n_queries=0, top_k={1: 0.0}, mrr=0.0, ndcg={1: 0.0}),
        by_category={},
    )
    assert r.per_query == []
