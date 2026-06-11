from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from rag_cti.retrieval.reranker import CrossEncoderReranker, NoOpReranker, Reranker
from rag_cti.types import Chunk, RetrievalResult


def _make_chunk(chunk_id: str, content: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        parent_doc_id="mitre_T1566",
        source="mitre",
        content=content,
        chunk_index=0,
        retrieved_at=datetime(2024, 1, 1),
        embedding_model="BAAI/bge-m3",
    )


def _make_result(chunk_id: str, content: str, score: float, rank: int) -> RetrievalResult:
    return RetrievalResult(
        document=_make_chunk(chunk_id, content),
        score=score,
        rank=rank,
        retriever_source="rrf",
    )


CTI_CONTENT_T1566 = (
    "T1566.001 — Spearphishing Attachment: Adversaries may send spearphishing emails "
    "with a malicious attachment in an attempt to gain access to victim systems."
)
CTI_CONTENT_T1059 = (
    "T1059.001 — PowerShell: Adversaries may abuse PowerShell commands and scripts for execution. "
    "PowerShell is a powerful interactive command-line interface and scripting environment."
)
CTI_CONTENT_T1078 = (
    "T1078 — Valid Accounts: Adversaries may obtain and abuse credentials of existing accounts "
    "as a means of gaining Initial Access, Persistence, Privilege Escalation, or Defense Evasion."
)


# ---------------------------------------------------------------------------
# Test 3 (happy path): rerank changes order
# ---------------------------------------------------------------------------


def test_rerank_changes_order_based_on_scores() -> None:
    reranker = CrossEncoderReranker(model_name="test-model")
    results = [
        _make_result("mitre_T1566_001_c0", CTI_CONTENT_T1566, 0.9, 0),
        _make_result("mitre_T1059_001_c0", CTI_CONTENT_T1059, 0.8, 1),
        _make_result("mitre_T1078_c0", CTI_CONTENT_T1078, 0.7, 2),
    ]

    with patch.object(reranker, "_load") as mock_load:
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.1, 0.9, 0.5]
        mock_load.return_value = mock_model

        reranked = reranker.rerank("APT29 spearphishing techniques", results)

    assert len(reranked) == 3
    assert reranked[0].document.id == "mitre_T1059_001_c0"
    assert reranked[1].document.id == "mitre_T1078_c0"
    assert reranked[2].document.id == "mitre_T1566_001_c0"
    assert reranked[0].score == pytest.approx(0.9)
    assert reranked[1].score == pytest.approx(0.5)
    assert reranked[2].score == pytest.approx(0.1)
    assert reranked[0].rank == 0
    assert reranked[1].rank == 1
    assert reranked[2].rank == 2


# ---------------------------------------------------------------------------
# Test 1 (edge): empty results
# ---------------------------------------------------------------------------


def test_rerank_empty_results_returns_empty() -> None:
    reranker = CrossEncoderReranker(model_name="test-model")
    result = reranker.rerank("credential harvesting techniques", [])
    assert result == []


# ---------------------------------------------------------------------------
# Test 2 (boundary): single result
# ---------------------------------------------------------------------------


def test_rerank_single_result_updates_score_and_rank() -> None:
    reranker = CrossEncoderReranker(model_name="test-model")
    results = [_make_result("mitre_T1566_001_c0", CTI_CONTENT_T1566, 0.9, 5)]

    with patch.object(reranker, "_load") as mock_load:
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.42]
        mock_load.return_value = mock_model

        reranked = reranker.rerank("phishing email detection", results)

    assert len(reranked) == 1
    assert reranked[0].score == pytest.approx(0.42)
    assert reranked[0].rank == 0
    assert reranked[0].document.id == "mitre_T1566_001_c0"


# ---------------------------------------------------------------------------
# Test 4 (adversarial): CTI special characters
# ---------------------------------------------------------------------------


def test_rerank_cti_special_characters_no_crash() -> None:
    reranker = CrossEncoderReranker(model_name="test-model")
    results = [
        _make_result(
            "otx_pulse_ioc_c0",
            "IOC: 192.168.1[.]1 observed in C2 communication for APT28 campaign",
            0.8,
            0,
        ),
        _make_result(
            "mitre_T1566_001_c0",
            "T1566.001 — 鱼叉式网络钓鱼附件：攻击者发送带有恶意附件的鱼叉式网络钓鱼邮件",
            0.7,
            1,
        ),
        _make_result(
            "mitre_T1059_001_c0",
            'T1059.001 — PowerShell: cmd /c "powershell -ep bypass -e <base64>"',
            0.6,
            2,
        ),
    ]

    with patch.object(reranker, "_load") as mock_load:
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.3, 0.7, 0.5]
        mock_load.return_value = mock_model

        reranked = reranker.rerank("APT28 infrastructure indicators", results)

    assert len(reranked) == 3
    for r in reranked:
        assert isinstance(r.score, float)


# ---------------------------------------------------------------------------
# Test 5 (boundary): Protocol satisfaction
# ---------------------------------------------------------------------------


def test_cross_encoder_reranker_satisfies_protocol() -> None:
    assert isinstance(CrossEncoderReranker(model_name="test"), Reranker)


# ---------------------------------------------------------------------------
# Test 6 (regression): NoOpReranker preserves everything
# ---------------------------------------------------------------------------


def test_noop_reranker_preserves_input_unchanged() -> None:
    results = [
        _make_result("mitre_T1566_001_c0", CTI_CONTENT_T1566, 0.9, 0),
        _make_result("mitre_T1059_001_c0", CTI_CONTENT_T1059, 0.7, 1),
        _make_result("mitre_T1078_c0", CTI_CONTENT_T1078, 0.5, 2),
    ]
    reranker = NoOpReranker()
    reranked = reranker.rerank("lateral movement techniques", results)

    assert reranked is results
    for orig, out in zip(results, reranked, strict=True):
        assert out.document.id == orig.document.id
        assert out.score == orig.score
        assert out.rank == orig.rank
        assert out.retriever_source == orig.retriever_source
