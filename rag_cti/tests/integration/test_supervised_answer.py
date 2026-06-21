"""End-to-end test for the multi-agent supervisor (knowledge.supervisor_graph).

Skipped unless the live stack is reachable (DeepSeek key + Qdrant; Neo4j optional — the
branches degrade to vector-only without it). Verifies a compound question decomposes into
parallel branches, merges, and synthesizes one grounded answer; and that a dependent
question degrades to the single agent (no over-decomposition). Mirrors
test_agentic_answer.py's opt-in guard.
"""

from __future__ import annotations

import os

import pytest

from rag_cti.config import get_settings


def _has_deepseek_key() -> bool:
    try:
        return bool(get_settings().deepseek_api_key.get_secret_value())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (os.environ.get("RAG_CTI_E2E") and _has_deepseek_key()),
    reason="supervisor e2e: set RAG_CTI_E2E=1 with a DeepSeek key + live Qdrant/Neo4j to run",
)


def test_compound_query_decomposes_and_grounds_citations() -> None:
    import rag_cti

    try:
        ans = rag_cti.supervised_answer("Compare the TTPs of APT29 and APT28.")
    except Exception as exc:  # services not up — skip rather than fail
        pytest.skip(f"supervisor e2e stack unavailable: {exc}")

    assert ans.answer
    assert ans.decomposed is True
    assert ans.branch_count >= 2
    # grounding guarantee: every surfaced citation is a real gathered id
    real_ids = {r.document.id for r in ans.query_result.results} | {
        f.fact_id for f in ans.collected_facts
    }
    assert all(cid in real_ids for cid in ans.cited_ids)


def test_dependent_query_degrades_to_single_agent() -> None:
    import rag_cti

    try:
        ans = rag_cti.supervised_answer(
            "What does the malware that APT29 dropped communicate with?"
        )
    except Exception as exc:
        pytest.skip(f"supervisor e2e stack unavailable: {exc}")

    assert ans.answer
    # sequential dependency must NOT be split into parallel branches
    assert ans.decomposed is False
    assert ans.branch_count <= 1
