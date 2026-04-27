from __future__ import annotations

import sys
import types
import uuid
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from rag_cti.types import Chunk

# ---------------------------------------------------------------------------
# Fake qdrant_client stand-ins — installed into sys.modules before import
# ---------------------------------------------------------------------------

class _FakeVectorParams:
    def __init__(self, size: int, distance: Any) -> None:
        self.size = size
        self.distance = distance


class _FakeDistance:
    COSINE = "COSINE"


class _FakePointStruct:
    def __init__(self, id: Any, vector: Any, payload: dict[str, Any]) -> None:
        self.id = id
        self.vector = vector
        self.payload = payload


class _FakeSparseVector:
    def __init__(self, indices: list[int], values: list[float]) -> None:
        self.indices = indices
        self.values = values


class _FakeMatchValue:
    def __init__(self, value: Any) -> None:
        self.value = value


class _FakeMatchAny:
    def __init__(self, any: list[Any]) -> None:
        self.any = any


class _FakeFieldCondition:
    def __init__(self, key: str, match: Any) -> None:
        self.key = key
        self.match = match


class _FakeFilter:
    def __init__(
        self, must: list[Any] | None = None, should: list[Any] | None = None
    ) -> None:
        self.must = must or []
        self.should = should or []


class _FakeSparseIndexParams:
    def __init__(self, on_disk: bool = False) -> None:
        self.on_disk = on_disk


class _FakeSparseVectorParams:
    def __init__(self, index: Any = None) -> None:
        self.index = index


class _FakeCollectionInfo:
    def __init__(self, name: str) -> None:
        self.name = name


@pytest.fixture
def fake_qdrant() -> dict[str, MagicMock]:
    """Install fake qdrant_client + qdrant_client.http.models in sys.modules."""
    client_cls = MagicMock(name="QdrantClient")

    root = types.ModuleType("qdrant_client")
    root.QdrantClient = client_cls  # type: ignore[attr-defined]

    http = types.ModuleType("qdrant_client.http")
    models = types.ModuleType("qdrant_client.http.models")
    models.VectorParams = _FakeVectorParams  # type: ignore[attr-defined]
    models.Distance = _FakeDistance  # type: ignore[attr-defined]
    models.PointStruct = _FakePointStruct  # type: ignore[attr-defined]
    models.MatchValue = _FakeMatchValue  # type: ignore[attr-defined]
    models.MatchAny = _FakeMatchAny  # type: ignore[attr-defined]
    models.FieldCondition = _FakeFieldCondition  # type: ignore[attr-defined]
    models.Filter = _FakeFilter  # type: ignore[attr-defined]
    http.models = models  # type: ignore[attr-defined]

    # qdrant_client.models is imported separately by upsert_hybrid and ensure_collection
    qdrant_models = types.ModuleType("qdrant_client.models")
    qdrant_models.SparseVector = _FakeSparseVector  # type: ignore[attr-defined]
    qdrant_models.SparseIndexParams = _FakeSparseIndexParams  # type: ignore[attr-defined]
    qdrant_models.SparseVectorParams = _FakeSparseVectorParams  # type: ignore[attr-defined]

    modules = {
        "qdrant_client": root,
        "qdrant_client.http": http,
        "qdrant_client.http.models": models,
        "qdrant_client.models": qdrant_models,
    }
    with patch.dict(sys.modules, modules):
        yield {"client_cls": client_cls}


def _make_chunk(chunk_id: str = "chunk-001", source: str = "mitre") -> Chunk:
    return Chunk(
        id=chunk_id,
        parent_doc_id="doc-aaa",
        source=source,
        content="example content",
        chunk_index=0,
        metadata={"attack_id": "T1566.001"},
        retrieved_at=datetime(2026, 4, 22, 12, 0, 0),
        embedding_model="bge-small-en-v1.5",
    )


def _make_hit(chunk: Chunk, score: float) -> MagicMock:
    hit = MagicMock()
    hit.score = score
    hit.payload = {
        "id": chunk.id,
        "parent_doc_id": chunk.parent_doc_id,
        "source": chunk.source,
        "content": chunk.content,
        "chunk_index": chunk.chunk_index,
        "metadata": chunk.metadata,
        "retrieved_at": chunk.retrieved_at.isoformat(),
        "embedding_model": chunk.embedding_model,
    }
    return hit


# ---------------------------------------------------------------------------
# chunk_to_point_id
# ---------------------------------------------------------------------------

def test_chunk_to_point_id_is_deterministic(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import chunk_to_point_id

    assert chunk_to_point_id("abc123") == chunk_to_point_id("abc123")


def test_chunk_to_point_id_is_valid_uuid(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import chunk_to_point_id

    point_id = chunk_to_point_id("abc123")
    uuid.UUID(point_id)  # raises ValueError if invalid


def test_chunk_to_point_id_differs_per_chunk(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import chunk_to_point_id

    assert chunk_to_point_id("a") != chunk_to_point_id("b")


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

def test_ensure_collection_creates_when_absent(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    client.get_collections.return_value = MagicMock(collections=[])
    fake_qdrant["client_cls"].return_value = client

    store = QdrantStore(url="http://x", collection="rag-cti")
    store.ensure_collection(vector_size=384)

    client.create_collection.assert_called_once()
    _, kwargs = client.create_collection.call_args
    assert kwargs["collection_name"] == "rag-cti"
    assert isinstance(kwargs["vectors_config"], dict)
    assert kwargs["vectors_config"]["dense"].size == 384
    assert kwargs["vectors_config"]["dense"].distance == "COSINE"
    assert "sparse" in kwargs["sparse_vectors_config"]


def test_ensure_collection_noop_when_present(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    client.get_collections.return_value = MagicMock(
        collections=[_FakeCollectionInfo("rag-cti")]
    )
    fake_qdrant["client_cls"].return_value = client

    store = QdrantStore(url="http://x", collection="rag-cti")
    store.ensure_collection(vector_size=384)

    client.create_collection.assert_not_called()


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------

def test_upsert_builds_points_with_expected_payload(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore, chunk_to_point_id

    client = MagicMock()
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    chunk = _make_chunk(chunk_id="xyz")
    vectors = np.ones((1, 4), dtype=np.float32)
    written = store.upsert([chunk], vectors)

    assert written == 1
    _, kwargs = client.upsert.call_args
    points = kwargs["points"]
    assert len(points) == 1
    point = points[0]
    assert point.id == chunk_to_point_id("xyz")
    assert point.payload["source"] == "mitre"
    assert point.payload["content"] == "example content"
    assert point.payload["metadata"]["attack_id"] == "T1566.001"
    assert point.payload["retrieved_at"] == "2026-04-22T12:00:00"


def test_upsert_raises_on_length_mismatch(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    with pytest.raises(ValueError, match="length mismatch"):
        store.upsert([_make_chunk()], np.ones((2, 4), dtype=np.float32))


def test_upsert_empty_chunks_returns_zero(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    assert store.upsert([], np.zeros((0, 4), dtype=np.float32)) == 0
    client.upsert.assert_not_called()


def test_upsert_batches_at_configured_size(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti", upsert_batch_size=2)

    chunks = [_make_chunk(chunk_id=f"c{i}") for i in range(5)]
    vectors = np.ones((5, 4), dtype=np.float32)
    store.upsert(chunks, vectors)

    # 5 items / batch size 2 → 3 calls (2, 2, 1)
    assert client.upsert.call_count == 3


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def test_search_returns_retrieval_results_with_ranks(
    fake_qdrant: dict[str, MagicMock],
) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    client.search.return_value = [
        _make_hit(_make_chunk(chunk_id="a"), score=0.9),
        _make_hit(_make_chunk(chunk_id="b"), score=0.7),
    ]
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    results = store.search(np.ones(4, dtype=np.float32), top_k=2)

    assert len(results) == 2
    assert results[0].rank == 0
    assert results[1].rank == 1
    assert results[0].score == pytest.approx(0.9)
    assert results[0].document.id == "a"
    assert results[0].retriever_source == "qdrant_dense"


def test_search_without_filter_passes_none(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    client.search.return_value = []
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    store.search(np.ones(4, dtype=np.float32), top_k=5)

    _, kwargs = client.search.call_args
    assert kwargs["query_filter"] is None
    assert kwargs["limit"] == 5


def test_search_with_single_source_filter_builds_match_any(
    fake_qdrant: dict[str, MagicMock],
) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    client.search.return_value = []
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    store.search(np.ones(4, dtype=np.float32), top_k=3, source_filter="mitre")

    _, kwargs = client.search.call_args
    flt = kwargs["query_filter"]
    assert flt is not None
    assert flt.must[0].key == "source"
    assert flt.must[0].match.any == ["mitre"]


def test_search_with_multi_source_filter_passes_list(
    fake_qdrant: dict[str, MagicMock],
) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    client.search.return_value = []
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    store.search(np.ones(4, dtype=np.float32), source_filter=["mitre", "otx"])

    _, kwargs = client.search.call_args
    assert kwargs["query_filter"].must[0].match.any == ["mitre", "otx"]


# ---------------------------------------------------------------------------
# count
# ---------------------------------------------------------------------------

def test_count_without_filter(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    client.count.return_value = MagicMock(count=42)
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    assert store.count() == 42
    _, kwargs = client.count.call_args
    assert kwargs["count_filter"] is None


def test_count_with_source_filter(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    client.count.return_value = MagicMock(count=7)
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    assert store.count(source_filter="otx") == 7
    _, kwargs = client.count.call_args
    assert kwargs["count_filter"].must[0].key == "source"
    assert kwargs["count_filter"].must[0].match.value == "otx"


# ---------------------------------------------------------------------------
# upsert_hybrid
# ---------------------------------------------------------------------------

class _FakeEncoder:
    """Minimal sparse encoder stub: returns fixed indices/values."""
    def encode_document(self, text: str) -> tuple[list[int], list[float]]:
        return [0, 1], [1.5, 0.8]


def test_upsert_hybrid_writes_both_vectors(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore, chunk_to_point_id

    client = MagicMock()
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    chunk = _make_chunk(chunk_id="hyb1")
    vectors = np.ones((1, 4), dtype=np.float32)
    written = store.upsert_hybrid([chunk], vectors, _FakeEncoder())

    assert written == 1
    _, kwargs = client.upsert.call_args
    point = kwargs["points"][0]
    assert point.id == chunk_to_point_id("hyb1")
    assert isinstance(point.vector, dict)
    assert "dense" in point.vector
    assert "sparse" in point.vector
    assert point.vector["sparse"].indices == [0, 1]
    assert point.vector["sparse"].values == [1.5, 0.8]


def test_upsert_hybrid_raises_on_length_mismatch(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    with pytest.raises(ValueError, match="length mismatch"):
        store.upsert_hybrid([_make_chunk()], np.ones((2, 4), dtype=np.float32), _FakeEncoder())


def test_upsert_hybrid_empty_returns_zero(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti")

    assert store.upsert_hybrid([], np.zeros((0, 4), dtype=np.float32), _FakeEncoder()) == 0
    client.upsert.assert_not_called()


def test_upsert_hybrid_batches_at_configured_size(fake_qdrant: dict[str, MagicMock]) -> None:
    from rag_cti.store.qdrant_store import QdrantStore

    client = MagicMock()
    fake_qdrant["client_cls"].return_value = client
    store = QdrantStore(url="http://x", collection="rag-cti", upsert_batch_size=2)

    chunks = [_make_chunk(chunk_id=f"h{i}") for i in range(5)]
    vectors = np.ones((5, 4), dtype=np.float32)
    store.upsert_hybrid(chunks, vectors, _FakeEncoder())

    # 5 items / batch 2 → 3 calls (2, 2, 1)
    assert client.upsert.call_count == 3
