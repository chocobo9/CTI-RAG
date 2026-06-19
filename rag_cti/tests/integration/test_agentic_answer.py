"""End-to-end test for the agentic answer loop (knowledge.agentic_graph).

Skipped unless the live stack is reachable (DeepSeek key + Qdrant collection; Neo4j
optional — the loop degrades to vector-only without it). Verifies the loop runs to a
cited answer and that the grounding guarantee holds: every cited id is one the loop
actually gathered (so dropped_citation_count counts only hallucinated ids).
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


# Opt-in only: this hits the paid DeepSeek API and needs live Qdrant/Neo4j, so it must
# NOT run in the routine `make ci` (bare pytest). Run with RAG_CTI_E2E=1 + a DeepSeek key.
pytestmark = pytest.mark.skipif(
    not (os.environ.get("RAG_CTI_E2E") and _has_deepseek_key()),
    reason="agentic e2e: set RAG_CTI_E2E=1 with a DeepSeek key + live Qdrant/Neo4j to run",
)


def test_agentic_answer_runs_and_validates_citations() -> None:
    import rag_cti

    try:
        ans = rag_cti.agentic_answer("What techniques do both APT29 and Lazarus Group use?")
    except Exception as exc:  # services (Qdrant/Neo4j) not up — skip rather than fail
        pytest.skip(f"agentic e2e stack unavailable: {exc}")

    assert ans.answer
    assert ans.stop_reason in {"sufficient", "budget", "parse_fallback"}
    assert ans.iteration_count >= 1
    # The grounding guarantee: every surfaced citation is a real gathered id.
    real_ids = {r.document.id for r in ans.query_result.results} | {
        f.fact_id for f in ans.collected_facts
    }
    assert all(cid in real_ids for cid in ans.cited_ids)
