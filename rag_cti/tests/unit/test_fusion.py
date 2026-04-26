from __future__ import annotations

from datetime import datetime

import pytest

from rag_cti.retrieval.fusion import reciprocal_rank_fusion
from rag_cti.types import Chunk, RetrievalResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(chunk_id: str, source: str = "mitre") -> Chunk:
    return Chunk(
        id=chunk_id,
        parent_doc_id="doc1",
        source=source,
        content=f"content for {chunk_id}",
        chunk_index=0,
        retrieved_at=datetime(2024, 1, 1),
        embedding_model="test-model",
    )


def _result(chunk_id: str, score: float, rank: int, retriever: str = "dense") -> RetrievalResult:
    return RetrievalResult(
        document=_chunk(chunk_id),
        score=score,
        rank=rank,
        retriever_source=retriever,
    )


# ---------------------------------------------------------------------------
# Tests — empty / trivial inputs
# ---------------------------------------------------------------------------

def test_empty_input_returns_empty() -> None:
    assert reciprocal_rank_fusion([]) == []


def test_single_empty_list_returns_empty() -> None:
    assert reciprocal_rank_fusion([[]]) == []


def test_single_list_returns_same_order() -> None:
    results = [_result("a", 0.9, 0), _result("b", 0.7, 1), _result("c", 0.5, 2)]
    fused = reciprocal_rank_fusion([results])
    assert [r.document.id for r in fused] == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Tests — score correctness
# ---------------------------------------------------------------------------

def test_rrf_score_formula_single_list() -> None:
    results = [_result("a", 1.0, 0)]
    fused = reciprocal_rank_fusion(result_lists=[results], k=60)
    assert fused[0].score == pytest.approx(1.0 / 61)


def test_rrf_score_accumulates_across_lists() -> None:
    list1 = [_result("a", 0.9, 0)]
    list2 = [_result("a", 0.5, 0)]
    fused = reciprocal_rank_fusion([list1, list2], k=60)
    assert fused[0].score == pytest.approx(2.0 / 61)


def test_rrf_score_different_ranks() -> None:
    list1 = [_result("a", 0.9, 0)]
    list2 = [_result("b", 0.8, 0), _result("c", 0.6, 1), _result("a", 0.4, 2)]
    fused = reciprocal_rank_fusion([list1, list2], k=60)
    a_score = next(r.score for r in fused if r.document.id == "a")
    assert a_score == pytest.approx(1.0 / 61 + 1.0 / 63)


# ---------------------------------------------------------------------------
# Tests — deduplication
# ---------------------------------------------------------------------------

def test_deduplication_same_id_appears_once() -> None:
    list1 = [_result("a", 0.9, 0), _result("b", 0.7, 1)]
    list2 = [_result("a", 0.6, 0), _result("c", 0.5, 1)]
    fused = reciprocal_rank_fusion([list1, list2])
    ids = [r.document.id for r in fused]
    assert ids.count("a") == 1


def test_best_score_document_kept_for_duplicate() -> None:
    list1 = [_result("a", 0.9, 0)]
    list2 = [_result("a", 0.3, 0)]
    fused = reciprocal_rank_fusion([list1, list2])
    assert fused[0].document.id == "a"


# ---------------------------------------------------------------------------
# Tests — ordering
# ---------------------------------------------------------------------------

def test_results_sorted_descending_by_fused_score() -> None:
    list1 = [_result("a", 0.9, 0), _result("b", 0.5, 1)]
    list2 = [_result("b", 0.8, 0), _result("c", 0.3, 1)]
    fused = reciprocal_rank_fusion([list1, list2])
    scores = [r.score for r in fused]
    assert scores == sorted(scores, reverse=True)


def test_ranks_are_zero_based_sequential() -> None:
    list1 = [_result("a", 0.9, 0), _result("b", 0.7, 1), _result("c", 0.5, 2)]
    fused = reciprocal_rank_fusion([list1])
    assert [r.rank for r in fused] == list(range(len(fused)))


def test_retriever_source_is_rrf() -> None:
    fused = reciprocal_rank_fusion([[_result("a", 0.9, 0)]])
    assert all(r.retriever_source == "rrf" for r in fused)


# ---------------------------------------------------------------------------
# Tests — k parameter
# ---------------------------------------------------------------------------

def test_custom_k_affects_score() -> None:
    results = [_result("a", 1.0, 0)]
    fused_k10 = reciprocal_rank_fusion([results], k=10)
    fused_k60 = reciprocal_rank_fusion([results], k=60)
    assert fused_k10[0].score == pytest.approx(1.0 / 11)
    assert fused_k60[0].score == pytest.approx(1.0 / 61)
    assert fused_k10[0].score > fused_k60[0].score


def test_multiple_empty_lists_returns_empty() -> None:
    assert reciprocal_rank_fusion([[], [], []]) == []
