from __future__ import annotations

import hashlib
import re
from enum import StrEnum

from rag_cti.types import Chunk, Document


class ChunkStrategy(StrEnum):
    SEMANTIC = "semantic"  # sentence-aware, for natural language docs
    STRUCTURED = "structured"  # one chunk per record, for JSON/KV sources
    FIXED = "fixed"  # fixed-size overlap, ablation baseline


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_DEFAULT_TARGET_TOKENS = 600
_DEFAULT_OVERLAP_TOKENS = 80
_CHARS_PER_TOKEN = 4  # rough estimate for English prose


def chunk_document(
    doc: Document,
    strategy: ChunkStrategy = ChunkStrategy.SEMANTIC,
    target_tokens: int = _DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = _DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    if strategy == ChunkStrategy.STRUCTURED:
        return _structured_chunks(doc)
    if strategy == ChunkStrategy.FIXED:
        return _fixed_chunks(doc, target_tokens, overlap_tokens)
    return _semantic_chunks(doc, target_tokens, overlap_tokens)


def _make_chunk_id(doc_id: str, index: int) -> str:
    return hashlib.sha256(f"{doc_id}:{index}".encode()).hexdigest()[:16]


def _structured_chunks(doc: Document) -> list[Chunk]:
    """One chunk per document — for WHOIS, pDNS, VT records."""
    return [
        Chunk.from_document(
            doc=doc,
            content=doc.content,
            chunk_index=0,
            chunk_id=_make_chunk_id(doc.id, 0),
        )
    ]


def _semantic_chunks(
    doc: Document,
    target_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    """Sentence-aware chunking with overlap for natural language documents."""
    target_chars = target_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN

    sentences = _SENTENCE_END.split(doc.content.strip())
    if not sentences:
        return _structured_chunks(doc)

    chunks: list[Chunk] = []
    current: list[str] = []
    current_len = 0
    index = 0

    for sentence in sentences:
        sentence_len = len(sentence)
        if current_len + sentence_len > target_chars and current:
            chunks.append(
                Chunk.from_document(
                    doc=doc,
                    content=" ".join(current),
                    chunk_index=index,
                    chunk_id=_make_chunk_id(doc.id, index),
                )
            )
            index += 1
            overlap: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) > overlap_chars:
                    break
                overlap.insert(0, s)
                overlap_len += len(s)
            current = overlap
            current_len = overlap_len

        current.append(sentence)
        current_len += sentence_len

    if current:
        chunks.append(
            Chunk.from_document(
                doc=doc,
                content=" ".join(current),
                chunk_index=index,
                chunk_id=_make_chunk_id(doc.id, index),
            )
        )

    return chunks or _structured_chunks(doc)


def _fixed_chunks(
    doc: Document,
    target_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    """Fixed-size character chunking with overlap — ablation baseline."""
    if overlap_tokens >= target_tokens:
        raise ValueError(
            f"overlap_tokens ({overlap_tokens}) must be strictly less than "
            f"target_tokens ({target_tokens}) to avoid an infinite loop."
        )
    target_chars = target_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN
    text = doc.content
    chunks: list[Chunk] = []
    start = 0
    index = 0

    while start < len(text):
        end = min(start + target_chars, len(text))
        chunks.append(
            Chunk.from_document(
                doc=doc,
                content=text[start:end],
                chunk_index=index,
                chunk_id=_make_chunk_id(doc.id, index),
            )
        )
        index += 1
        start += target_chars - overlap_chars

    return chunks or _structured_chunks(doc)
