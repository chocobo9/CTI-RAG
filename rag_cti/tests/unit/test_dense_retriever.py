from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from rag_cti.retrieval.dense_retriever import DenseRetriever
from rag_cti.types import Chunk, RetrievalResult


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

def _make_result(score: float, rank: int) -> RetrievalResult:
    chunk = Chunk(
        id="abc123",
        parent_doc_id="doc1",
        source="mitre",
        content="lateral movement via T1021",
        chunk_index=0,
        retrieved_at=datetime(2024, 1, 1),
        embedding_model="test-model",
    )
    return RetrievalResult(document=chunk, score=score, rank=rank, retriever_source="qdrant_dense")


class _FakeEmbedder:
    def encode_one(self, text: str) -> np.ndarray:
        return np.array([0.1, 0.2, 0.3], dtype=np.float32)


class _FakeStore:
    def __init__(self, results: list[RetrievalResult] | None = None) -> None:
        self.last_call: dict = {}
        self._results = results or []

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        source_filter=None,
    ) -> list[RetrievalResult]:
        self.last_call = {
            "query_vector": query_vector,
            "top_k": top_k,
            "source_filter": source_filter,
        }
        return self._results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_search_returns_store_results() -> None:
    expected = [_make_result(0.9, 0), _make_result(0.7, 1)]
    retriever = DenseRetriever(store=_FakeStore(expected), embedder=_FakeEmbedder())
    assert retriever.search("lateral movement") == expected


def test_search_passes_top_k_to_store() -> None:
    store = _FakeStore()
    DenseRetriever(store=store, embedder=_FakeEmbedder()).search("phishing", top_k=5)
    assert store.last_call["top_k"] == 5


def test_search_default_top_k_is_ten() -> None:
    store = _FakeStore()
    DenseRetriever(store=store, embedder=_FakeEmbedder()).search("exploit")
    assert store.last_call["top_k"] == 10


def test_search_passes_source_filter_string() -> None:
    store = _FakeStore()
    DenseRetriever(store=store, embedder=_FakeEmbedder()).search("malware", source_filter="mitre")
    assert store.last_call["source_filter"] == "mitre"


def test_search_passes_source_filter_list() -> None:
    store = _FakeStore()
    DenseRetriever(store=store, embedder=_FakeEmbedder()).search("ransomware", source_filter=["mitre", "otx"])
    assert store.last_call["source_filter"] == ["mitre", "otx"]


def test_search_default_source_filter_is_none() -> None:
    store = _FakeStore()
    DenseRetriever(store=store, embedder=_FakeEmbedder()).search("exploit")
    assert store.last_call["source_filter"] is None


def test_search_uses_embedder_vector() -> None:
    store = _FakeStore()
    DenseRetriever(store=store, embedder=_FakeEmbedder()).search("credential dumping")
    np.testing.assert_array_equal(
        store.last_call["query_vector"],
        np.array([0.1, 0.2, 0.3], dtype=np.float32),
    )


def test_search_returns_empty_list_when_no_results() -> None:
    retriever = DenseRetriever(store=_FakeStore([]), embedder=_FakeEmbedder())
    assert retriever.search("unknown query") == []
