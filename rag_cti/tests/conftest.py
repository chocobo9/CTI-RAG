from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from rag_cti.types import Chunk, Document


@pytest.fixture(autouse=True)
def _no_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kill tenacity's exponential backoff in tests so a retry-exhaustion path runs in
    ~0s instead of ~15s. tenacity 9's ``nap.sleep`` wrapper calls ``time.sleep`` at call
    time (the controller holds the wrapper, so patching ``nap.sleep`` itself is a no-op),
    so we patch ``time.sleep`` — the single point every backoff strategy routes through.
    No unit test depends on real wall-clock sleep; deadline tests drive ``monotonic``
    arithmetic directly. Production retry COUNTS are unchanged — only the waiting is."""
    monkeypatch.setattr(time, "sleep", lambda *_a: None)


@pytest.fixture
def fixed_datetime() -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0)


@pytest.fixture
def sample_document(fixed_datetime: datetime) -> Document:
    return Document(
        id="doc-mitre-T1566.001",
        source="mitre",
        content=(
            "Spearphishing Attachment: Adversaries may send spearphishing emails "
            "with a malicious attachment in an attempt to gain access to victim systems."
        ),
        metadata={
            "attack_id": "T1566.001",
            "tactic": "initial-access",
            "platform": ["Windows", "macOS", "Linux"],
        },
        retrieved_at=fixed_datetime,
    )


@pytest.fixture
def sample_chunk(sample_document: Document) -> Chunk:
    return Chunk.from_document(
        doc=sample_document,
        content=sample_document.content,
        chunk_index=0,
        chunk_id="chunk-mitre-T1566.001-0",
    )


@pytest.fixture
def sample_otx_document(fixed_datetime: datetime) -> Document:
    return Document(
        id="doc-otx-pulse-abc123",
        source="otx",
        content=(
            "APT29 Cozy Bear campaign targeting government entities via spearphishing. "
            "Uses SUNBURST malware for lateral movement."
        ),
        metadata={
            "pulse_id": "abc123",
            "tags": ["apt29", "cozy-bear", "sunburst"],
            "attack_ids": ["T1566", "T1078"],
        },
        retrieved_at=fixed_datetime,
    )


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.qdrant_url = "http://localhost:6333"
    settings.qdrant_collection = "cti_chunks_test"
    settings.embedding_model = "BAAI/bge-m3"
    settings.retrieval_top_k = 5
    settings.hybrid_alpha = 0.5
    settings.hyde_enabled = False
    settings.hyde_min_query_tokens = 5
    return settings
