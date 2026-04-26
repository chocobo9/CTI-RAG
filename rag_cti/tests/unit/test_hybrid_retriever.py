from __future__ import annotations

from datetime import datetime

from rag_cti.retrieval.hybrid_retriever import HybridRetriever
from rag_cti.types import Chunk, RetrievalResult


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

def _make_result(chunk_id: str, score: float, rank: int, source: str = "dense") -> RetrievalResult:
    chunk = Chunk(
        id=chunk_id,
        parent_doc_id="doc1",
        source="mitre",
        content=f"content for {chunk_id}",
        chunk_index=0,
        retrieved_at=datetime(2024, 1, 1),
        embedding_model="test-model",
    )
    return RetrievalResult(document=chunk, score=score, rank=rank, retriever_source=source)


class _FakeRetriever:
    def __init__(self, results: list[RetrievalResult] | None = None) -> None:
        self.last_query: str = ""
        self.last_top_k: int = 0
        self.last_source_filter = None
        self._results = results or []

    def search(self, query: str, top_k: int = 10, source_filter=None) -> list[RetrievalResult]:
        self.last_query = query
        self.last_top_k = top_k
        self.last_source_filter = source_filter
        return self._results


class _FakeSettings:
    pass


# ---------------------------------------------------------------------------
# Tests — forwarding
# ---------------------------------------------------------------------------

def test_passes_query_to_both_retrievers() -> None:
    dense = _FakeRetriever()
    sparse = _FakeRetriever()
    retriever = HybridRetriever(dense=dense, sparse=sparse, settings=_FakeSettings())
    retriever.search("ransomware lateral movement via SMB")
    assert dense.last_query == "ransomware lateral movement via SMB"
    assert sparse.last_query == "ransomware lateral movement via SMB"


def test_passes_top_k_to_both_retrievers() -> None:
    dense = _FakeRetriever()
    sparse = _FakeRetriever()
    retriever = HybridRetriever(dense=dense, sparse=sparse, settings=_FakeSettings())
    retriever.search("apt lateral movement", top_k=7)
    assert dense.last_top_k == 7
    assert sparse.last_top_k == 7


def test_passes_source_filter_to_both_retrievers() -> None:
    dense = _FakeRetriever()
    sparse = _FakeRetriever()
    retriever = HybridRetriever(dense=dense, sparse=sparse, settings=_FakeSettings())
    retriever.search("apt lateral movement", source_filter="mitre")
    assert dense.last_source_filter == "mitre"
    assert sparse.last_source_filter == "mitre"


# ---------------------------------------------------------------------------
# Tests — fusion and truncation
# ---------------------------------------------------------------------------

def test_results_truncated_to_top_k() -> None:
    dense_results = [_make_result(f"d{i}", 1.0 - i * 0.1, i) for i in range(8)]
    sparse_results = [_make_result(f"s{i}", 0.9 - i * 0.1, i, "sparse") for i in range(8)]
    dense = _FakeRetriever(dense_results)
    sparse = _FakeRetriever(sparse_results)
    retriever = HybridRetriever(dense=dense, sparse=sparse, settings=_FakeSettings())
    results = retriever.search("query", top_k=5)
    assert len(results) <= 5


def test_returns_list_of_retrieval_results() -> None:
    dense = _FakeRetriever([_make_result("a", 0.9, 0)])
    sparse = _FakeRetriever([_make_result("b", 0.8, 0, "sparse")])
    retriever = HybridRetriever(dense=dense, sparse=sparse, settings=_FakeSettings())
    results = retriever.search("some query")
    assert isinstance(results, list)
    assert all(isinstance(r, RetrievalResult) for r in results)


def test_deduplicates_results_from_both_retrievers() -> None:
    shared = _make_result("shared", 0.9, 0)
    dense = _FakeRetriever([shared, _make_result("a", 0.7, 1)])
    sparse = _FakeRetriever([shared, _make_result("b", 0.6, 1, "sparse")])
    retriever = HybridRetriever(dense=dense, sparse=sparse, settings=_FakeSettings())
    results = retriever.search("query")
    ids = [r.document.id for r in results]
    assert ids.count("shared") == 1


def test_retriever_source_is_rrf_after_fusion() -> None:
    dense = _FakeRetriever([_make_result("a", 0.9, 0)])
    sparse = _FakeRetriever([_make_result("b", 0.8, 0, "sparse")])
    retriever = HybridRetriever(dense=dense, sparse=sparse, settings=_FakeSettings())
    results = retriever.search("query")
    assert all(r.retriever_source == "rrf" for r in results)


def test_empty_dense_returns_sparse_only() -> None:
    sparse_results = [_make_result("s1", 0.9, 0, "sparse")]
    dense = _FakeRetriever([])
    sparse = _FakeRetriever(sparse_results)
    retriever = HybridRetriever(dense=dense, sparse=sparse, settings=_FakeSettings())
    results = retriever.search("query")
    assert len(results) == 1
    assert results[0].document.id == "s1"


def test_both_empty_returns_empty() -> None:
    retriever = HybridRetriever(dense=_FakeRetriever(), sparse=_FakeRetriever(), settings=_FakeSettings())
    assert retriever.search("query") == []
