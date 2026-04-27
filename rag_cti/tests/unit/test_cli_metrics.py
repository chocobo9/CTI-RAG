"""Unit tests for cli_metrics pure functions."""
from __future__ import annotations

import json

import pytest

from rag_cti.cli_metrics import (
    FUZZY_HIT10_THRESHOLD,
    OVERALL_HIT10_THRESHOLD,
    Thresholds,
    check_thresholds,
    load_results,
    render_summary_table,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_data(overall_hit10: float, fuzzy_hit10: float) -> dict:  # type: ignore[type-arg]
    return {
        "k_values": [1, 5, 10],
        "results": [
            {
                "config": "dense",
                "overall": {"top_k": {10: overall_hit10}, "mrr": 0.5, "ndcg": {10: 0.5}, "n_queries": 20},
                "by_category": {
                    "fuzzy": {"top_k": {10: fuzzy_hit10}, "mrr": 0.4, "ndcg": {10: 0.4}, "n_queries": 5},
                    "precise": {"top_k": {10: 0.9}, "mrr": 0.8, "ndcg": {10: 0.8}, "n_queries": 10},
                    "semantic": {"top_k": {10: 0.85}, "mrr": 0.75, "ndcg": {10: 0.78}, "n_queries": 5},
                },
            }
        ],
    }


class _FakeConsole:
    def __init__(self) -> None:
        self.printed: list[object] = []

    def print(self, *args: object, **kwargs: object) -> None:
        self.printed.extend(args)


# ---------------------------------------------------------------------------
# load_results
# ---------------------------------------------------------------------------

def test_load_results_raises_file_not_found(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_results(tmp_path / "nonexistent.json")


def test_load_results_raises_value_error_on_invalid_json(tmp_path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_results(p)


def test_load_results_raises_value_error_on_missing_results_key(tmp_path) -> None:
    p = tmp_path / "no_results.json"
    p.write_text(json.dumps({"timestamp": "2026-01-01"}), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing 'results'"):
        load_results(p)


def test_load_results_returns_dict_on_valid_file(tmp_path) -> None:
    data = {"results": [], "k_values": [1, 5, 10]}
    p = tmp_path / "ok.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = load_results(p)
    assert result["results"] == []


def test_load_results_preserves_k_values(tmp_path) -> None:
    data = {"results": [], "k_values": [1, 5, 10, 20]}
    p = tmp_path / "ok.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    assert load_results(p)["k_values"] == [1, 5, 10, 20]


# ---------------------------------------------------------------------------
# check_thresholds
# ---------------------------------------------------------------------------

def test_check_thresholds_no_warnings_when_all_met() -> None:
    assert check_thresholds(_make_data(0.80, 0.65)) == []


def test_check_thresholds_warns_overall_below_threshold() -> None:
    warnings = check_thresholds(_make_data(0.65, 0.65))
    assert any("overall Hit@10" in w for w in warnings)


def test_check_thresholds_warns_fuzzy_below_threshold() -> None:
    warnings = check_thresholds(_make_data(0.80, 0.50))
    assert any("fuzzy Hit@10" in w for w in warnings)


def test_check_thresholds_both_violations_returns_two_warnings() -> None:
    warnings = check_thresholds(_make_data(0.60, 0.55))
    assert len(warnings) == 2


def test_check_thresholds_custom_thresholds_applied() -> None:
    t = Thresholds(fuzzy_hit10=0.90, overall_hit10=0.90)
    warnings = check_thresholds(_make_data(0.80, 0.80), t)
    assert len(warnings) == 2


def test_check_thresholds_empty_results_returns_empty_list() -> None:
    assert check_thresholds({"results": []}) == []


def test_check_thresholds_string_key_fallback() -> None:
    data = {
        "results": [
            {
                "config": "dense",
                "overall": {"top_k": {"10": 0.50}, "mrr": 0.4, "ndcg": {}},
                "by_category": {"fuzzy": {"top_k": {"10": 0.50}, "mrr": 0.4, "ndcg": {}}},
            }
        ]
    }
    warnings = check_thresholds(data)
    assert len(warnings) == 2


def test_check_thresholds_warning_contains_config_name() -> None:
    warnings = check_thresholds(_make_data(0.60, 0.55))
    assert all("[dense]" in w for w in warnings)


def test_check_thresholds_default_thresholds_match_constants() -> None:
    t = Thresholds()
    assert t.fuzzy_hit10 == FUZZY_HIT10_THRESHOLD
    assert t.overall_hit10 == OVERALL_HIT10_THRESHOLD


def test_check_thresholds_at_exact_threshold_no_warning() -> None:
    assert check_thresholds(_make_data(OVERALL_HIT10_THRESHOLD, FUZZY_HIT10_THRESHOLD)) == []


# ---------------------------------------------------------------------------
# render_summary_table
# ---------------------------------------------------------------------------

def test_render_summary_table_calls_console_print() -> None:
    c = _FakeConsole()
    render_summary_table({"k_values": [1, 5, 10], "results": []}, c)
    assert len(c.printed) > 0


def test_render_summary_table_prints_four_tables() -> None:
    c = _FakeConsole()
    render_summary_table({"k_values": [1, 5, 10], "results": []}, c)
    assert len(c.printed) == 4


def test_render_summary_table_with_result_row_does_not_raise() -> None:
    c = _FakeConsole()
    render_summary_table(_make_data(0.8, 0.65), c)
    assert len(c.printed) == 4


def test_render_summary_table_multiple_configs_does_not_raise() -> None:
    data = {
        "k_values": [1, 5, 10],
        "results": [
            {
                "config": "dense",
                "overall": {"top_k": {10: 0.8}, "mrr": 0.7, "ndcg": {10: 0.75}, "n_queries": 20},
                "by_category": {},
            },
            {
                "config": "hybrid",
                "overall": {"top_k": {10: 0.85}, "mrr": 0.75, "ndcg": {10: 0.80}, "n_queries": 20},
                "by_category": {},
            },
        ],
    }
    c = _FakeConsole()
    render_summary_table(data, c)
    assert len(c.printed) == 4


def test_render_summary_table_skips_missing_category_gracefully() -> None:
    data = {
        "k_values": [1, 5, 10],
        "results": [
            {
                "config": "dense",
                "overall": {"top_k": {10: 0.8}, "mrr": 0.7, "ndcg": {10: 0.75}, "n_queries": 20},
                "by_category": {},
            }
        ],
    }
    c = _FakeConsole()
    render_summary_table(data, c)
    assert len(c.printed) == 4
