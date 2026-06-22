"""Unit tests for deterministic query effort-tiering (knowledge.agentic_effort)."""

from __future__ import annotations

from rag_cti.knowledge.agentic_effort import classify_effort_tier, render_budget_line

_BUDGETS = {"simple": 3, "comparison": 8, "complex": 12}


def test_classify_simple_single_topic() -> None:
    assert classify_effort_tier("Office template macros persistence") == "simple"


def test_classify_comparison_shared_between() -> None:
    assert classify_effort_tier("techniques shared between APT29 and Turla") == "comparison"


def test_classify_comparison_vs() -> None:
    assert classify_effort_tier("APT29 vs Turla tooling") == "comparison"


def test_classify_complex_multi_clause() -> None:
    q = "What techniques does APT29 use, what malware does FIN7 deploy, and how does TA505 persist?"
    assert classify_effort_tier(q) == "complex"


def test_classify_complex_three_entities() -> None:
    assert classify_effort_tier("link APT29 FIN7 TA505 infrastructure") == "complex"


def test_render_budget_line_shows_tier_budget_and_used() -> None:
    line = render_budget_line("simple", 1, _BUDGETS)
    assert "SIMPLE" in line
    assert "3" in line  # the simple tier budget
    assert "used 1" in line


def test_render_budget_line_unknown_tier_falls_back_to_complex() -> None:
    assert "12" in render_budget_line("mystery", 0, _BUDGETS)  # complex budget fallback
