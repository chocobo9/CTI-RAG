from __future__ import annotations

from datetime import datetime

from rag_cti.retrieval.sparse_retriever import SparseRetriever
from rag_cti.types import Chunk, RetrievalResult

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


def _make_result(score: float, rank: int) -> RetrievalResult:
    chunk = Chunk(
        id="xyz789",
        parent_doc_id="doc2",
        source="otx",
        content="ransomware CVE-2021-44228 exploitation",
        chunk_index=0,
        retrieved_at=datetime(2024, 1, 1),
        embedding_model="test-model",
    )
    return RetrievalResult(document=chunk, score=score, rank=rank, retriever_source="qdrant_sparse")


class _FakeEncoder:
    def __init__(self, indices: list[int], values: list[float]) -> None:
        self._indices = indices
        self._values = values

    def encode_query(self, text: str) -> tuple[list[int], list[float]]:
        return self._indices, self._values


class _FakeStore:
    def __init__(self, results: list[RetrievalResult] | None = None) -> None:
        self.last_call: dict = {}
        self._results = results or []

    def sparse_search(
        self,
        query_indices: list[int],
        query_values: list[float],
        top_k: int = 10,
        source_filter=None,
        constraint=None,
    ) -> list[RetrievalResult]:
        self.last_call = {
            "query_indices": query_indices,
            "query_values": query_values,
            "top_k": top_k,
            "source_filter": source_filter,
            "constraint": constraint,
        }
        return self._results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_search_returns_store_results() -> None:
    expected = [_make_result(1.5, 0), _make_result(0.8, 1)]
    encoder = _FakeEncoder([1, 42], [1.2, 0.9])
    retriever = SparseRetriever(store=_FakeStore(expected), encoder=encoder)
    assert retriever.search("ransomware CVE") == expected


def test_search_passes_indices_and_values_to_store() -> None:
    store = _FakeStore()
    encoder = _FakeEncoder([3, 7, 11], [0.5, 1.0, 0.3])
    SparseRetriever(store=store, encoder=encoder).search("lateral movement")
    assert store.last_call["query_indices"] == [3, 7, 11]
    assert store.last_call["query_values"] == [0.5, 1.0, 0.3]


def test_search_passes_top_k_to_store() -> None:
    store = _FakeStore()
    encoder = _FakeEncoder([1], [1.0])
    SparseRetriever(store=store, encoder=encoder).search("malware", top_k=5)
    assert store.last_call["top_k"] == 5


def test_search_default_top_k_is_ten() -> None:
    store = _FakeStore()
    encoder = _FakeEncoder([1], [1.0])
    SparseRetriever(store=store, encoder=encoder).search("malware")
    assert store.last_call["top_k"] == 10


def test_search_passes_source_filter_string() -> None:
    store = _FakeStore()
    encoder = _FakeEncoder([1], [1.0])
    SparseRetriever(store=store, encoder=encoder).search("phishing", source_filter="mitre")
    assert store.last_call["source_filter"] == "mitre"


def test_search_passes_source_filter_list() -> None:
    store = _FakeStore()
    encoder = _FakeEncoder([1], [1.0])
    SparseRetriever(store=store, encoder=encoder).search("phishing", source_filter=["mitre", "otx"])
    assert store.last_call["source_filter"] == ["mitre", "otx"]


def test_search_default_source_filter_is_none() -> None:
    store = _FakeStore()
    encoder = _FakeEncoder([1], [1.0])
    SparseRetriever(store=store, encoder=encoder).search("exploit")
    assert store.last_call["source_filter"] is None


def test_search_returns_empty_when_all_oov() -> None:
    store = _FakeStore([_make_result(1.0, 0)])
    encoder = _FakeEncoder([], [])
    assert SparseRetriever(store=store, encoder=encoder).search("xyzzy_unknown") == []


def test_search_does_not_call_store_when_oov() -> None:
    store = _FakeStore()
    encoder = _FakeEncoder([], [])
    SparseRetriever(store=store, encoder=encoder).search("xyzzy_unknown")
    assert store.last_call == {}


def test_search_returns_empty_list_when_store_returns_nothing() -> None:
    encoder = _FakeEncoder([5], [0.7])
    assert SparseRetriever(store=_FakeStore([]), encoder=encoder).search("credential theft") == []
