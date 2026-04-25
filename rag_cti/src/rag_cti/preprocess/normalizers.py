from __future__ import annotations

import re

from rag_cti.preprocess.chunking import ChunkStrategy

# Sources that produce structured single-record documents
_STRUCTURED_SOURCES = {"whois", "pdns", "virustotal"}

# Sources that produce natural language prose
_SEMANTIC_SOURCES = {"mitre", "otx", "pdf"}


def source_to_strategy(source: str) -> ChunkStrategy:
    """Return the appropriate chunking strategy for a given source name."""
    if source in _STRUCTURED_SOURCES:
        return ChunkStrategy.STRUCTURED
    if source in _SEMANTIC_SOURCES:
        return ChunkStrategy.SEMANTIC
    return ChunkStrategy.SEMANTIC


def validate_content(content: str, source: str, doc_id: str) -> str:
    """Validate and sanitize document content at the ingestion boundary.

    Raises ValueError for empty content that would produce useless embeddings.
    """
    if not content or not content.strip():
        raise ValueError(f"Empty content for document id={doc_id!r} source={source!r}")

    cleaned = re.sub(r"[ \t]+", " ", content.strip())
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned
