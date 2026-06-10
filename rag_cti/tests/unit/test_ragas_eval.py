from __future__ import annotations

from datetime import datetime

import pytest

from rag_cti.evaluation.ragas_eval import (
    RagasEvalResult,
    answers_to_ragas_dataset,
)
from rag_cti.types import Chunk, GeneratedAnswer, QueryResult, RetrievalResult


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


def _make_answer(
    query: str,
    answer: str,
    chunks: list[tuple[str, str]],
) -> GeneratedAnswer:
    results = [
        RetrievalResult(
            document=_make_chunk(cid, content),
            score=0.9 - i * 0.1,
            rank=i,
            retriever_source="rrf",
        )
        for i, (cid, content) in enumerate(chunks)
    ]
    qr = QueryResult(
        query=query,
        results=results,
        total_retrieved=len(results),
        retrieval_ms=50.0,
    )
    return GeneratedAnswer(
        query=query,
        answer=answer,
        cited_chunk_ids=[c[0] for c in chunks],
        query_result=qr,
        generation_ms=100.0,
        model="test-model",
    )


CTI_CHUNKS = [
    (
        "mitre_T1566_001_c0",
        "T1566.001 — Spearphishing Attachment: Adversaries may send spearphishing emails "
        "with a malicious attachment in an attempt to gain access to victim systems.",
    ),
    (
        "mitre_T1059_001_c0",
        "T1059.001 — PowerShell: Adversaries may abuse PowerShell commands and scripts for execution.",
    ),
    (
        "mitre_T1078_c0",
        "T1078 — Valid Accounts: Adversaries may obtain and abuse credentials of existing accounts.",
    ),
]


# ---------------------------------------------------------------------------
# Test 1 (happy path): conversion format correct
# ---------------------------------------------------------------------------

def test_answers_to_ragas_dataset_format() -> None:
    answers = [
        _make_answer(
            "How does APT29 use spearphishing?",
            "APT29 uses spearphishing with malicious attachments.",
            CTI_CHUNKS[:2],
        ),
        _make_answer(
            "What is T1059 PowerShell execution?",
            "T1059 involves adversaries abusing PowerShell for execution.",
            CTI_CHUNKS[1:2],
        ),
        _make_answer(
            "How do adversaries use valid accounts for persistence?",
            "Adversaries obtain credentials to maintain persistence.",
            CTI_CHUNKS[2:],
        ),
    ]
    result = answers_to_ragas_dataset(answers)
    assert len(result) == 3
    for sample in result:
        assert "user_input" in sample
        assert "retrieved_contexts" in sample
        assert "response" in sample
        assert isinstance(sample["retrieved_contexts"], list)
        for ctx in sample["retrieved_contexts"]:
            assert isinstance(ctx, str)


# ---------------------------------------------------------------------------
# Test 2 (happy path): contexts content complete
# ---------------------------------------------------------------------------

def test_answers_to_ragas_dataset_contexts_content() -> None:
    answer = _make_answer(
        "What are APT29 techniques?",
        "APT29 uses spearphishing, PowerShell, and valid accounts.",
        CTI_CHUNKS,
    )
    result = answers_to_ragas_dataset([answer])
    assert len(result) == 1
    contexts = result[0]["retrieved_contexts"]
    assert len(contexts) == 3
    assert "T1566.001" in contexts[0]
    assert "T1059.001" in contexts[1]
    assert "T1078" in contexts[2]


# ---------------------------------------------------------------------------
# Test 3 (edge): empty answers list
# ---------------------------------------------------------------------------

def test_answers_to_ragas_dataset_empty() -> None:
    result = answers_to_ragas_dataset([])
    assert result == []


# ---------------------------------------------------------------------------
# Test 4 (edge): answer with no retrieval results
# ---------------------------------------------------------------------------

def test_answers_to_ragas_dataset_no_results() -> None:
    answer = _make_answer(
        "Unknown technique query",
        "No relevant information found.",
        [],
    )
    result = answers_to_ragas_dataset([answer])
    assert len(result) == 1
    assert result[0]["retrieved_contexts"] == []


# ---------------------------------------------------------------------------
# Test 5 (boundary): RagasEvalResult fields
# ---------------------------------------------------------------------------

def test_ragas_eval_result_fields() -> None:
    result = RagasEvalResult(
        n_queries=5,
        faithfulness=0.85,
        answer_relevancy=0.78,
        per_query=[
            {"question": "APT29 techniques?", "faithfulness": 0.9, "answer_relevancy": 0.8},
            {"question": "T1059 usage?", "faithfulness": 0.8, "answer_relevancy": 0.76},
        ],
        config="hybrid+reranker",
        timestamp="2026-05-18T03:00:00+00:00",
    )
    assert result.n_queries == 5
    assert isinstance(result.faithfulness, float)
    assert isinstance(result.answer_relevancy, float)
    assert 0.0 <= result.faithfulness <= 1.0
    assert 0.0 <= result.answer_relevancy <= 1.0
    assert len(result.per_query) == 2
    for pq in result.per_query:
        assert "question" in pq
        assert "faithfulness" in pq
        assert "answer_relevancy" in pq


# ---------------------------------------------------------------------------
# Test 6 (error path): judge LLM missing raises ValueError
# ---------------------------------------------------------------------------

def test_build_judge_llm_missing_key_raises() -> None:
    from pydantic import SecretStr

    class _FakeSettings:
        deepseek_api_key = SecretStr("")

    from rag_cti.evaluation.ragas_eval import _build_judge_llm

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        _build_judge_llm(_FakeSettings())
