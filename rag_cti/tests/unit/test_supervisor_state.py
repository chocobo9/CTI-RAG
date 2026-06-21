"""Unit tests for the multi-agent supervisor data types (agentic_state additions)."""

from __future__ import annotations

from rag_cti.knowledge.agentic_state import (
    AgenticAnswer,
    BranchReport,
    SubQuestion,
)
from rag_cti.types import QueryResult


def _empty_qr() -> QueryResult:
    return QueryResult(query="q", results=[], total_retrieved=0, retrieval_ms=0.0)


def test_subquestion_defaults_have_no_focus_or_facet() -> None:
    sq = SubQuestion(sub_question="What techniques does APT29 use?")
    assert sq.focus_entity is None
    assert sq.facet is None


def test_branch_report_defaults() -> None:
    br = BranchReport(sub_question="q")
    assert br.sub_answer == ""
    assert br.techniques == ()
    assert br.cited_ids == ()
    assert br.n_facts == 0
    assert br.n_chunks == 0
    assert br.stop_reason == ""


def test_agentic_answer_supervisor_fields_default_off() -> None:
    ans = AgenticAnswer(query="q", answer="a", query_result=_empty_qr())
    assert ans.branch_count == 0
    assert ans.decomposed is False
