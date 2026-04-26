"""Qdrant vector store wrapper.

One unified collection holds chunks from all CTI sources; the `source` field
in each point's payload is used for per-source filtering at query time.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Iterable

import numpy as np

from rag_cti._logging import get_logger
from rag_cti.types import Chunk, RetrievalResult

logger = get_logger(__name__)

# Stable namespace so a given chunk.id always maps to the same Qdrant point id.
_QDRANT_ID_NAMESPACE = uuid.UUID("d7b3a5a6-4f72-4e86-9b88-2e5f5d8a1c3e")

_DEFAULT_UPSERT_BATCH = 128
_RETRIEVER_NAME = "qdrant_dense"
_SPARSE_RETRIEVER_NAME = "qdrant_sparse"


def chunk_to_point_id(chunk_id: str) -> str:
    """Map an arbitrary chunk id (e.g. 16-char sha256 prefix) to a Qdrant UUID."""
    return str(uuid.uuid5(_QDRANT_ID_NAMESPACE, chunk_id))


class QdrantStore:
    """Thin wrapper around qdrant-client for CTI chunk upsert and dense search."""

    def __init__(
        self,
        url: str,
        collection: str,
        api_key: str = "",
        upsert_batch_size: int = _DEFAULT_UPSERT_BATCH,
    ) -> None:
        from qdrant_client import QdrantClient  # type: ignore[import]

        self.collection = collection
        self.upsert_batch_size = upsert_batch_size
        self._client = QdrantClient(url=url, api_key=api_key or None)

    def ensure_collection(self, vector_size: int) -> None:
        """Create the collection if it does not exist. No-op if already present.

        Creates a hybrid schema: named 'dense' (cosine) + named 'sparse' (BM25).
        Schema matches migrate_to_hybrid.py so ingest.py is the sole lifecycle owner.
        """
        from qdrant_client.http import models as qm  # type: ignore[import]
        from qdrant_client.models import SparseIndexParams, SparseVectorParams  # type: ignore[import]

        existing = {c.name for c in self._client.get_collections().collections}
        if self.collection in existing:
            logger.info("collection already exists", collection=self.collection)
            return

        self._client.create_collection(
            collection_name=self.collection,
            vectors_config={
                "dense": qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=False),
                ),
            },
        )
        logger.info("collection created", collection=self.collection, vector_size=vector_size)

    def upsert(self, chunks: list[Chunk], embeddings: np.ndarray) -> int:
        """Upsert chunks with dense vector only. Returns the number of points written."""
        from qdrant_client.http import models as qm  # type: ignore[import]

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch"
            )
        if not chunks:
            return 0

        points = [
            qm.PointStruct(
                id=chunk_to_point_id(chunk.id),
                vector={"dense": embeddings[i].tolist()},
                payload=_chunk_to_payload(chunk),
            )
            for i, chunk in enumerate(chunks)
        ]

        written = 0
        for batch in _batched(points, self.upsert_batch_size):
            self._client.upsert(collection_name=self.collection, points=batch, wait=True)
            written += len(batch)
        return written

    def upsert_hybrid(
        self,
        chunks: list[Chunk],
        embeddings: np.ndarray,
        sparse_encoder: Any,
    ) -> int:
        """Upsert chunks with dense + BM25 sparse vectors. Returns the number of points written."""
        from qdrant_client.http import models as qm  # type: ignore[import]
        from qdrant_client.models import SparseVector  # type: ignore[import]

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch"
            )
        if not chunks:
            return 0

        points = []
        for i, chunk in enumerate(chunks):
            sp_indices, sp_values = sparse_encoder.encode_document(chunk.content)
            points.append(
                qm.PointStruct(
                    id=chunk_to_point_id(chunk.id),
                    vector={
                        "dense": embeddings[i].tolist(),
                        "sparse": SparseVector(indices=sp_indices, values=sp_values),
                    },
                    payload=_chunk_to_payload(chunk),
                )
            )

        written = 0
        for batch in _batched(points, self.upsert_batch_size):
            self._client.upsert(collection_name=self.collection, points=batch, wait=True)
            written += len(batch)
        return written

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Dense cosine search. Optionally restrict to one or more sources."""
        from qdrant_client.http import models as qm  # type: ignore[import]

        query_filter: qm.Filter | None = None
        if source_filter:
            sources = [source_filter] if isinstance(source_filter, str) else list(source_filter)
            query_filter = qm.Filter(
                must=[qm.FieldCondition(key="source", match=qm.MatchAny(any=sources))]
            )

        hits = self._client.search(
            collection_name=self.collection,
            query_vector=("dense", query_vector.tolist()),
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            RetrievalResult(
                document=_payload_to_chunk(hit.payload or {}),
                score=float(hit.score),
                rank=rank,
                retriever_source=_RETRIEVER_NAME,
            )
            for rank, hit in enumerate(hits)
        ]

    def sparse_search(
        self,
        query_indices: list[int],
        query_values: list[float],
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
    ) -> list[RetrievalResult]:
        """BM25 sparse search. Optionally restrict to one or more sources."""
        from qdrant_client.http import models as qm  # type: ignore[import]
        from qdrant_client.models import NamedSparseVector, SparseVector  # type: ignore[import]

        query_filter: qm.Filter | None = None
        if source_filter:
            sources = [source_filter] if isinstance(source_filter, str) else list(source_filter)
            query_filter = qm.Filter(
                must=[qm.FieldCondition(key="source", match=qm.MatchAny(any=sources))]
            )

        hits = self._client.search(
            collection_name=self.collection,
            query_vector=NamedSparseVector(
                name="sparse",
                vector=SparseVector(indices=query_indices, values=query_values),
            ),
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            RetrievalResult(
                document=_payload_to_chunk(hit.payload or {}),
                score=float(hit.score),
                rank=rank,
                retriever_source=_SPARSE_RETRIEVER_NAME,
            )
            for rank, hit in enumerate(hits)
        ]

    def count(self, source_filter: str | None = None) -> int:
        """Return the number of points, optionally filtered by source."""
        from qdrant_client.http import models as qm  # type: ignore[import]

        query_filter: qm.Filter | None = None
        if source_filter:
            query_filter = qm.Filter(
                must=[qm.FieldCondition(key="source", match=qm.MatchValue(value=source_filter))]
            )
        result = self._client.count(
            collection_name=self.collection, count_filter=query_filter, exact=True
        )
        return int(result.count)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk_to_payload(chunk: Chunk) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "parent_doc_id": chunk.parent_doc_id,
        "source": chunk.source,
        "content": chunk.content,
        "chunk_index": chunk.chunk_index,
        "metadata": chunk.metadata,
        "retrieved_at": chunk.retrieved_at.isoformat(),
        "embedding_model": chunk.embedding_model,
    }


def _payload_to_chunk(payload: dict[str, Any]) -> Chunk:
    return Chunk(
        id=str(payload.get("id", "")),
        parent_doc_id=str(payload.get("parent_doc_id", "")),
        source=str(payload.get("source", "")),
        content=str(payload.get("content", "")),
        chunk_index=int(payload.get("chunk_index", 0)),
        metadata=dict(payload.get("metadata") or {}),
        retrieved_at=_parse_ts(payload.get("retrieved_at")),
        embedding_model=str(payload.get("embedding_model", "")),
    )


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.utcnow()


def _batched(items: list[Any], size: int) -> Iterable[list[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
