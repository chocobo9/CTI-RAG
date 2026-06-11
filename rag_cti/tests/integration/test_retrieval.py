"""Integration tests for the Phase 4 retrieval layer.

Requires a running Qdrant instance at http://localhost:6333.
All tests are skipped automatically when Qdrant is unreachable.

Run:
    pytest tests/integration/test_retrieval.py -v
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from rag_cti.retrieval.bm25 import BM25SparseEncoder
from rag_cti.retrieval.dense_retriever import DenseRetriever
from rag_cti.retrieval.hybrid_retriever import HybridRetriever
from rag_cti.retrieval.pipeline import Pipeline
from rag_cti.retrieval.reranker import NoOpReranker
from rag_cti.retrieval.sparse_retriever import SparseRetriever
from rag_cti.store.qdrant_store import QdrantStore
from rag_cti.types import Chunk, QueryResult, RetrievalResult

# ---------------------------------------------------------------------------
# Constants — synthetic corpus
# ---------------------------------------------------------------------------

_QDRANT_URL = "http://localhost:6333"
_TEST_COLLECTION = "cti_test_retrieval"
_VECTOR_SIZE = 4  # tiny vectors keep the test fast

# Five chunks across two sources with hand-crafted 4-dim unit vectors.
# Cluster 0 (dim-0): spearphishing / initial-access
# Cluster 1 (dim-1): C2 / beaconing
# Cluster 2 (dim-2): lateral movement
_CORPUS: list[dict] = [
    {
        "id": "c1",
        "source": "mitre",
        "content": "Spearphishing email attachment T1566.001 initial access technique",
        "vec": [1.0, 0.0, 0.0, 0.0],
    },
    {
        "id": "c2",
        "source": "mitre",
        "content": "Credential dumping NTLM hashes T1003 post-exploitation",
        "vec": [0.9, 0.1, 0.0, 0.0],
    },
    {
        "id": "c3",
        "source": "otx",
        "content": "Cobalt Strike beacon HTTPS C2 communication 1.2.3.4 port 443",
        "vec": [0.0, 1.0, 0.0, 0.0],
    },
    {
        "id": "c4",
        "source": "otx",
        "content": "Ransomware AES-256 file encryption drops ransom note",
        "vec": [0.0, 0.8, 0.2, 0.0],
    },
    {
        "id": "c5",
        "source": "mitre",
        "content": "Pass-the-hash SMB lateral movement T1550.002 CVE-2021-44228",
        "vec": [0.0, 0.0, 1.0, 0.0],
    },
]

_CORPUS_TEXTS = [c["content"] for c in _CORPUS]


# ---------------------------------------------------------------------------
# Fake embedder — deterministic, no sentence-transformers load
# ---------------------------------------------------------------------------


class _FakeEmbedder:
    """Returns the predefined 4-dim vector for corpus chunks; keyword-based for queries."""

    _CONTENT_MAP = {c["content"]: np.array(c["vec"], dtype=np.float32) for c in _CORPUS}

    def encode_one(self, text: str) -> np.ndarray:
        if text in self._CONTENT_MAP:
            return self._CONTENT_MAP[text]
        tl = text.lower()
        if "spearphishing" in tl or "t1566" in tl or "initial access" in tl:
            return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        if "cobalt" in tl or "beacon" in tl or "c2" in tl:
            return np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        if "lateral" in tl or "pass-the-hash" in tl or "smb" in tl:
            return np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32)
        return np.array([0.5, 0.5, 0.0, 0.0], dtype=np.float32)


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qdrant_store() -> QdrantStore:
    """Create an isolated test collection; populate it; delete it after all tests."""
    try:
        from qdrant_client import QdrantClient  # type: ignore[import]

        client = QdrantClient(url=_QDRANT_URL, timeout=3)
        client.get_collections()
    except Exception:
        pytest.skip("Qdrant not available at http://localhost:6333")

    store = QdrantStore(url=_QDRANT_URL, collection=_TEST_COLLECTION)
    store.ensure_collection(vector_size=_VECTOR_SIZE)

    chunks = [
        Chunk(
            id=c["id"],
            parent_doc_id=f"doc-{c['id']}",
            source=c["source"],
            content=c["content"],
            chunk_index=0,
            retrieved_at=datetime(2024, 1, 1),
            embedding_model="fake-4d",
        )
        for c in _CORPUS
    ]
    embeddings = np.array([c["vec"] for c in _CORPUS], dtype=np.float32)

    encoder = BM25SparseEncoder()
    encoder.fit(_CORPUS_TEXTS)
    store.upsert_hybrid(chunks=chunks, embeddings=embeddings, sparse_encoder=encoder)

    yield store

    try:
        from qdrant_client import QdrantClient  # type: ignore[import]

        QdrantClient(url=_QDRANT_URL).delete_collection(_TEST_COLLECTION)
    except Exception:
        pass


@pytest.fixture(scope="module")
def bm25_encoder() -> BM25SparseEncoder:
    enc = BM25SparseEncoder()
    enc.fit(_CORPUS_TEXTS)
    return enc


@pytest.fixture(scope="module")
def embedder() -> _FakeEmbedder:
    return _FakeEmbedder()


# ---------------------------------------------------------------------------
# Tests — DenseRetriever
# ---------------------------------------------------------------------------


def test_dense_retriever_returns_retrieval_results(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder
) -> None:
    retriever = DenseRetriever(store=qdrant_store, embedder=embedder)
    results = retriever.search("spearphishing email T1566 initial access", top_k=3)
    assert len(results) > 0
    assert all(isinstance(r, RetrievalResult) for r in results)


def test_dense_retriever_scores_are_descending(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder
) -> None:
    retriever = DenseRetriever(store=qdrant_store, embedder=embedder)
    results = retriever.search("spearphishing email T1566 initial access", top_k=5)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_dense_retriever_top_k_limits_results(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder
) -> None:
    retriever = DenseRetriever(store=qdrant_store, embedder=embedder)
    results = retriever.search("spearphishing email T1566", top_k=2)
    assert len(results) <= 2


def test_dense_retriever_source_filter_restricts_source(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder
) -> None:
    retriever = DenseRetriever(store=qdrant_store, embedder=embedder)
    results = retriever.search("spearphishing email T1566", top_k=5, source_filter="mitre")
    assert len(results) > 0
    assert all(r.document.source == "mitre" for r in results)


def test_dense_retriever_spearphishing_query_returns_c1_first(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder
) -> None:
    retriever = DenseRetriever(store=qdrant_store, embedder=embedder)
    results = retriever.search("spearphishing email T1566 initial access", top_k=5)
    assert results[0].document.id == "c1"


# ---------------------------------------------------------------------------
# Tests — SparseRetriever
# ---------------------------------------------------------------------------


def test_sparse_retriever_returns_retrieval_results(
    qdrant_store: QdrantStore, bm25_encoder: BM25SparseEncoder
) -> None:
    retriever = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    results = retriever.search("spearphishing T1566", top_k=3)
    assert len(results) > 0
    assert all(isinstance(r, RetrievalResult) for r in results)


def test_sparse_retriever_oov_query_returns_empty(
    qdrant_store: QdrantStore, bm25_encoder: BM25SparseEncoder
) -> None:
    retriever = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    results = retriever.search("xyzzy qwerty frobnicator", top_k=5)
    assert results == []


def test_sparse_retriever_top_k_limits_results(
    qdrant_store: QdrantStore, bm25_encoder: BM25SparseEncoder
) -> None:
    retriever = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    results = retriever.search("spearphishing email lateral", top_k=2)
    assert len(results) <= 2


def test_sparse_retriever_source_filter_restricts_source(
    qdrant_store: QdrantStore, bm25_encoder: BM25SparseEncoder
) -> None:
    retriever = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    results = retriever.search("spearphishing T1566", top_k=5, source_filter="mitre")
    assert len(results) > 0
    assert all(r.document.source == "mitre" for r in results)


# ---------------------------------------------------------------------------
# Tests — HybridRetriever
# ---------------------------------------------------------------------------


def test_hybrid_retriever_returns_retrieval_results(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder, bm25_encoder: BM25SparseEncoder
) -> None:
    dense = DenseRetriever(store=qdrant_store, embedder=embedder)
    sparse = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    hybrid = HybridRetriever(dense=dense, sparse=sparse, settings=object())
    results = hybrid.search("spearphishing email T1566 initial access", top_k=5)
    assert len(results) > 0
    assert all(isinstance(r, RetrievalResult) for r in results)


def test_hybrid_retriever_result_source_is_rrf(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder, bm25_encoder: BM25SparseEncoder
) -> None:
    dense = DenseRetriever(store=qdrant_store, embedder=embedder)
    sparse = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    hybrid = HybridRetriever(dense=dense, sparse=sparse, settings=object())
    results = hybrid.search("spearphishing email T1566 initial access", top_k=5)
    assert all(r.retriever_source == "rrf" for r in results)


def test_hybrid_retriever_no_duplicate_chunk_ids(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder, bm25_encoder: BM25SparseEncoder
) -> None:
    dense = DenseRetriever(store=qdrant_store, embedder=embedder)
    sparse = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    hybrid = HybridRetriever(dense=dense, sparse=sparse, settings=object())
    results = hybrid.search("spearphishing email lateral SMB T1566", top_k=10)
    ids = [r.document.id for r in results]
    assert len(ids) == len(set(ids))


def test_hybrid_retriever_top_k_respected(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder, bm25_encoder: BM25SparseEncoder
) -> None:
    dense = DenseRetriever(store=qdrant_store, embedder=embedder)
    sparse = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    hybrid = HybridRetriever(dense=dense, sparse=sparse, settings=object())
    results = hybrid.search("spearphishing email T1566", top_k=2)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# Tests — Pipeline (end-to-end)
# ---------------------------------------------------------------------------


class _PipelineSettings:
    retrieval_top_k = 5
    hyde_enabled = False
    hyde_min_query_tokens = 5


def test_pipeline_run_returns_query_result(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder, bm25_encoder: BM25SparseEncoder
) -> None:
    dense = DenseRetriever(store=qdrant_store, embedder=embedder)
    sparse = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    hybrid = HybridRetriever(dense=dense, sparse=sparse, settings=_PipelineSettings())
    pipeline = Pipeline(retriever=hybrid, reranker=NoOpReranker(), settings=_PipelineSettings())
    result = pipeline.run("spearphishing email T1566 initial access")
    assert isinstance(result, QueryResult)


def test_pipeline_run_query_field_preserved(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder, bm25_encoder: BM25SparseEncoder
) -> None:
    dense = DenseRetriever(store=qdrant_store, embedder=embedder)
    sparse = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    hybrid = HybridRetriever(dense=dense, sparse=sparse, settings=_PipelineSettings())
    pipeline = Pipeline(retriever=hybrid, reranker=NoOpReranker(), settings=_PipelineSettings())
    q = "Cobalt Strike beacon C2 communication"
    result = pipeline.run(q)
    assert result.query == q


def test_pipeline_run_total_retrieved_matches_results(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder, bm25_encoder: BM25SparseEncoder
) -> None:
    dense = DenseRetriever(store=qdrant_store, embedder=embedder)
    sparse = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    hybrid = HybridRetriever(dense=dense, sparse=sparse, settings=_PipelineSettings())
    pipeline = Pipeline(retriever=hybrid, reranker=NoOpReranker(), settings=_PipelineSettings())
    result = pipeline.run("spearphishing email T1566 initial access")
    assert result.total_retrieved == len(result.results)


def test_pipeline_source_filter_mitre_only(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder, bm25_encoder: BM25SparseEncoder
) -> None:
    dense = DenseRetriever(store=qdrant_store, embedder=embedder)
    sparse = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    hybrid = HybridRetriever(dense=dense, sparse=sparse, settings=_PipelineSettings())
    pipeline = Pipeline(retriever=hybrid, reranker=NoOpReranker(), settings=_PipelineSettings())
    result = pipeline.run("spearphishing T1566", source_filter="mitre")
    assert all(r.document.source == "mitre" for r in result.results)


def test_pipeline_retrieval_ms_is_non_negative(
    qdrant_store: QdrantStore, embedder: _FakeEmbedder, bm25_encoder: BM25SparseEncoder
) -> None:
    dense = DenseRetriever(store=qdrant_store, embedder=embedder)
    sparse = SparseRetriever(store=qdrant_store, encoder=bm25_encoder)
    hybrid = HybridRetriever(dense=dense, sparse=sparse, settings=_PipelineSettings())
    pipeline = Pipeline(retriever=hybrid, reranker=NoOpReranker(), settings=_PipelineSettings())
    result = pipeline.run("lateral movement SMB")
    assert result.retrieval_ms >= 0.0
