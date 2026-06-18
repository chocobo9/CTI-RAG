"""Qdrant vector store wrapper.

One unified collection holds chunks from all CTI sources; the `source` field
in each point's payload is used for per-source filtering at query time.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import numpy as np

from rag_cti._logging import get_logger
from rag_cti.types import Chunk, PayloadConstraint, RetrievalResult

_MAX_CONTENT_LEN = 8_000

logger = get_logger(__name__)

# Stable namespace so a given chunk.id always maps to the same Qdrant point id.
_QDRANT_ID_NAMESPACE = uuid.UUID("d7b3a5a6-4f72-4e86-9b88-2e5f5d8a1c3e")

_DEFAULT_UPSERT_BATCH = 128
_RETRIEVER_NAME = "qdrant_dense"
_SPARSE_RETRIEVER_NAME = "qdrant_sparse"

# Payload fields given keyword indexes for query-time pre-filtering (retrieval §4).
_PAYLOAD_INDEX_FIELDS = ("source_type", "attack_ids", "entity_ids")


class ChunkIdCollisionError(RuntimeError):
    """Two distinct chunks share an id — upserting would silently overwrite one
    (ingestion §6/§7, Rule 0). Raised loudly instead of letting it happen."""


def assert_unique_chunk_ids(
    chunks: Iterable[Chunk], seen: dict[str, str] | None = None
) -> dict[str, str]:
    """Fail loud on an id collision between chunks of different content.

    Same id + identical content is idempotent (allowed); same id + different
    content is a silent-overwrite hazard. Pass a shared ``seen`` map across
    sources to catch cross-source collisions. Returns the updated map.
    """
    seen = {} if seen is None else seen
    for chunk in chunks:
        content_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
        prev = seen.get(chunk.id)
        if prev is not None and prev != content_hash:
            raise ChunkIdCollisionError(
                f"chunk id {chunk.id!r} maps to two different contents — refusing to upsert"
            )
        seen[chunk.id] = content_hash
    return seen


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
        max_content_len: int = _MAX_CONTENT_LEN,
    ) -> None:
        from qdrant_client import QdrantClient

        self.collection = collection
        self.upsert_batch_size = upsert_batch_size
        self.max_content_len = max_content_len
        self._client = QdrantClient(url=url, api_key=api_key or None)

    def ensure_collection(self, vector_size: int) -> None:
        """Create the collection if it does not exist. No-op if already present.

        Creates a hybrid schema: named 'dense' (cosine) + named 'sparse' (BM25).
        ingest.py is the sole collection lifecycle owner.
        """
        from qdrant_client.http import models as qm
        from qdrant_client.models import (
            SparseIndexParams,
            SparseVectorParams,
        )

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

    def ensure_payload_indexes(self) -> None:
        """Create keyword payload indexes for query-time pre-filtering (retrieval §4).

        A constrained query (``attack_id = T1566 AND source_type = otx``, or an
        entity filter) then runs as a Qdrant index lookup *before* vector scoring,
        instead of going through the similarity channel. Idempotent — re-creating
        an existing index is a no-op, so it is safe to call on every ingest.
        """
        from qdrant_client.http import models as qm

        for field in _PAYLOAD_INDEX_FIELDS:
            self._client.create_payload_index(
                collection_name=self.collection,
                field_name=field,
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
            logger.info("payload index ensured", collection=self.collection, field=field)

    def upsert(self, chunks: list[Chunk], embeddings: np.ndarray) -> int:
        """Upsert chunks with dense vector only. Returns the number of points written."""
        from qdrant_client.http import models as qm

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
        from qdrant_client.http import models as qm
        from qdrant_client.models import SparseVector

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
        constraint: PayloadConstraint | None = None,
    ) -> list[RetrievalResult]:
        """Dense cosine search. Optionally pre-filter by source / structured constraint."""
        query_filter = _build_query_filter(source_filter, constraint)

        hits = self._client.search(
            collection_name=self.collection,
            query_vector=("dense", query_vector.tolist()),
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            RetrievalResult(
                document=_payload_to_chunk(hit.payload or {}, self.max_content_len),
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
        constraint: PayloadConstraint | None = None,
    ) -> list[RetrievalResult]:
        """BM25 sparse search. Optionally pre-filter by source / structured constraint."""
        from qdrant_client.models import NamedSparseVector, SparseVector

        query_filter = _build_query_filter(source_filter, constraint)

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
                document=_payload_to_chunk(hit.payload or {}, self.max_content_len),
                score=float(hit.score),
                rank=rank,
                retriever_source=_SPARSE_RETRIEVER_NAME,
            )
            for rank, hit in enumerate(hits)
        ]

    def count(self, source_filter: str | None = None) -> int:
        """Return the number of points, optionally filtered by source."""
        from qdrant_client.http import models as qm

        query_filter: qm.Filter | None = None
        if source_filter:
            query_filter = qm.Filter(
                must=[qm.FieldCondition(key="source", match=qm.MatchValue(value=source_filter))]
            )
        result = self._client.count(
            collection_name=self.collection, count_filter=query_filter, exact=True
        )
        return int(result.count)

    def get_by_chunk_ids(self, chunk_ids: list[str]) -> dict[str, Chunk]:
        """Fetch chunks by chunk.id (== ``supports.evidence_id``) for M4 citation
        expansion. Maps each id through :func:`chunk_to_point_id` and retrieves by
        point id; missing ids are simply absent — never fabricated (M4 invariant)."""
        if not chunk_ids:
            return {}
        point_ids = [chunk_to_point_id(cid) for cid in chunk_ids]
        records = self._client.retrieve(
            collection_name=self.collection, ids=point_ids, with_payload=True
        )
        out: dict[str, Chunk] = {}
        for record in records:
            chunk = _payload_to_chunk(record.payload or {}, self.max_content_len)
            out[chunk.id] = chunk
        return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_query_filter(
    source_filter: str | list[str] | None,
    constraint: PayloadConstraint | None,
) -> Any:
    """Combine the source filter + structured constraint into one AND'd Qdrant Filter.

    Each field is a MatchAny condition on a payload key; together they pre-filter
    the candidate set *before* vector scoring (retrieval §6). Returns None when
    there is nothing to constrain.
    """
    from qdrant_client.http import models as qm

    must: list[Any] = []
    if source_filter:
        sources = [source_filter] if isinstance(source_filter, str) else list(source_filter)
        must.append(qm.FieldCondition(key="source", match=qm.MatchAny(any=sources)))
    if constraint is not None and not constraint.is_empty:
        for key, values in (
            ("source_type", constraint.source_types),
            ("attack_ids", constraint.attack_ids),
            ("entity_ids", constraint.entity_ids),
        ):
            if values:
                must.append(qm.FieldCondition(key=key, match=qm.MatchAny(any=list(values))))
    return qm.Filter(must=must) if must else None


def _chunk_to_payload(chunk: Chunk) -> dict[str, Any]:
    # M2 §4 filter projections, surfaced top-level so they can be payload-indexed
    # and pre-filtered (retrieval §6). They are produced by chunk_projection and
    # carried in chunk.metadata; absent -> safe defaults (source_type falls back
    # to source; the rest empty). These are filter keys only, never embedded.
    md = chunk.metadata or {}
    return {
        "id": chunk.id,
        "parent_doc_id": chunk.parent_doc_id,
        "source": chunk.source,
        "content": chunk.content,
        "chunk_index": chunk.chunk_index,
        "metadata": chunk.metadata,
        "retrieved_at": chunk.retrieved_at.isoformat(),
        "embedding_model": chunk.embedding_model,
        "source_type": md.get("source_type", chunk.source),
        "attack_ids": md.get("attack_ids", []),
        "entity_ids": md.get("entity_ids", []),
        "relations": md.get("relations", []),
    }


def _payload_to_chunk(payload: dict[str, Any], max_content_len: int = _MAX_CONTENT_LEN) -> Chunk:
    return Chunk(
        id=str(payload.get("id", "")),
        parent_doc_id=str(payload.get("parent_doc_id", "")),
        source=str(payload.get("source", "")),
        content=str(payload.get("content", ""))[:max_content_len],
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
