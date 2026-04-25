from __future__ import annotations

import pytest

from rag_cti.preprocess.chunking import ChunkStrategy, chunk_document
from rag_cti.types import Chunk, Document

_LONG_TEXT = (
    "Adversaries may send spearphishing emails with malicious attachments. "
    "These attachments may be documents, executables, or archive files. "
    "Once opened, the malicious content executes and may establish persistence. "
    "Defenders should enable email filtering and user awareness training. "
    "Monitoring for unusual email attachments can help detect this technique. "
    "Anti-virus software may also detect malicious payloads in attachments. "
    "Network-based detection can identify command and control communications. "
    "Sandboxing suspicious attachments before delivery is a recommended mitigation. "
) * 5


@pytest.fixture
def long_doc() -> Document:
    return Document(
        id="doc-long-001",
        source="mitre",
        content=_LONG_TEXT,
        metadata={"attack_id": "T1566.001"},
    )


@pytest.fixture
def short_doc() -> Document:
    return Document(
        id="doc-short-001",
        source="whois",
        content="Domain example.com registered with GoDaddy on 2020-01-01.",
        metadata={"domain": "example.com"},
    )


# --- Structured ---

def test_structured_produces_single_chunk(short_doc: Document) -> None:
    chunks = chunk_document(short_doc, strategy=ChunkStrategy.STRUCTURED)
    assert len(chunks) == 1
    assert chunks[0].content == short_doc.content


def test_structured_chunk_has_correct_parent_and_index(short_doc: Document) -> None:
    chunk = chunk_document(short_doc, strategy=ChunkStrategy.STRUCTURED)[0]
    assert chunk.parent_doc_id == short_doc.id
    assert chunk.source == short_doc.source
    assert chunk.chunk_index == 0


# --- Semantic ---

def test_semantic_splits_long_doc(long_doc: Document) -> None:
    chunks = chunk_document(long_doc, strategy=ChunkStrategy.SEMANTIC, target_tokens=100)
    assert len(chunks) > 1


def test_semantic_chunk_ids_are_unique(long_doc: Document) -> None:
    chunks = chunk_document(long_doc, strategy=ChunkStrategy.SEMANTIC, target_tokens=100)
    assert len({c.id for c in chunks}) == len(chunks)


def test_semantic_chunk_indices_are_sequential(long_doc: Document) -> None:
    chunks = chunk_document(long_doc, strategy=ChunkStrategy.SEMANTIC, target_tokens=100)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_semantic_all_chunks_are_chunk_instances(long_doc: Document) -> None:
    chunks = chunk_document(long_doc, strategy=ChunkStrategy.SEMANTIC, target_tokens=100)
    assert all(isinstance(c, Chunk) for c in chunks)


def test_semantic_short_doc_returns_at_least_one_chunk(short_doc: Document) -> None:
    chunks = chunk_document(short_doc, strategy=ChunkStrategy.SEMANTIC)
    assert len(chunks) >= 1


# --- Fixed ---

def test_fixed_produces_multiple_chunks(long_doc: Document) -> None:
    chunks = chunk_document(
        long_doc, strategy=ChunkStrategy.FIXED, target_tokens=200, overlap_tokens=40
    )
    assert len(chunks) > 1


def test_fixed_chunk_ids_are_unique(long_doc: Document) -> None:
    chunks = chunk_document(
        long_doc, strategy=ChunkStrategy.FIXED, target_tokens=200, overlap_tokens=40
    )
    assert len({c.id for c in chunks}) == len(chunks)


def test_fixed_raises_when_overlap_gte_target(long_doc: Document) -> None:
    with pytest.raises(ValueError, match="overlap_tokens"):
        chunk_document(
            long_doc, strategy=ChunkStrategy.FIXED, target_tokens=80, overlap_tokens=80
        )


# --- ID stability ---

def test_chunk_id_is_deterministic(short_doc: Document) -> None:
    id1 = chunk_document(short_doc, strategy=ChunkStrategy.STRUCTURED)[0].id
    id2 = chunk_document(short_doc, strategy=ChunkStrategy.STRUCTURED)[0].id
    assert id1 == id2
