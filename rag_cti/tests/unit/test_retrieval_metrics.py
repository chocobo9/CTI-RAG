from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from rag_cti.evaluation.retrieval_metrics import (
    EvalResult,
    _is_match,
    evaluate_retriever,
    hit_at_k,
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
