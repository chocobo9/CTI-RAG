"""Unit tests for chunk-id collision detection (ingestion §6/§7, Rule 0)."""

from __future__ import annotations

import pytest

from rag_cti.store.qdrant_store import ChunkIdCollisionError, assert_unique_chunk_ids
from rag_cti.types import Chunk


def _chunk(chunk_id: str, content: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        parent_doc_id="doc",
        source="otx",
        content=content,
        chunk_index=0,
    )


def test_unique_ids_pass():
    chunks = [_chunk("a", "alpha"), _chunk("b", "beta")]
    seen = assert_unique_chunk_ids(chunks)
    assert set(seen) == {"a", "b"}


def test_same_id_same_content_is_idempotent():
    chunks = [_chunk("a", "alpha"), _chunk("a", "alpha")]
    assert_unique_chunk_ids(chunks)  # no raise


def test_same_id_different_content_raises():
    chunks = [_chunk("a", "alpha"), _chunk("a", "DIFFERENT")]
    with pytest.raises(ChunkIdCollisionError, match="a"):
        assert_unique_chunk_ids(chunks)


def test_shared_seen_catches_cross_source_collision():
    seen: dict[str, str] = {}
    assert_unique_chunk_ids([_chunk("a", "alpha")], seen)
    with pytest.raises(ChunkIdCollisionError):
        assert_unique_chunk_ids([_chunk("a", "other source content")], seen)
