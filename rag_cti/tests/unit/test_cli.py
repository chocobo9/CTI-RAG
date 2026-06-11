"""Tests for the rag-cti Typer CLI commands."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from rag_cti.cli import app

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(output: str) -> str:
    """Strip ANSI escape codes — newer typer/rich render help with style codes
    that split option names (e.g. ``--top-k``) mid-token in captured output."""
    return _ANSI_RE.sub("", output)


def _fake_query_result() -> MagicMock:
    mock = MagicMock()
    mock.results = []
    return mock


# ---------------------------------------------------------------------------
# Help / registration
# ---------------------------------------------------------------------------


def test_root_help_exits_cleanly() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "rag-cti" in result.output


def test_all_commands_listed_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    for cmd in ("query", "ingest", "refresh", "eval", "metrics"):
        assert cmd in result.output


def test_query_help_shows_top_k_option() -> None:
    result = runner.invoke(app, ["query", "--help"])
    assert result.exit_code == 0
    assert "--top-k" in _plain(result.output)


def test_ingest_help_shows_source_argument() -> None:
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "SOURCE" in result.output or "source" in result.output.lower()


def test_refresh_help_shows_since_option() -> None:
    result = runner.invoke(app, ["refresh", "--help"])
    assert result.exit_code == 0
    assert "--since" in _plain(result.output)


def test_eval_help_shows_suite_argument() -> None:
    result = runner.invoke(app, ["eval", "--help"])
    assert result.exit_code == 0
    assert "suite" in result.output.lower() or "SUITE" in result.output


def test_metrics_help_shows_strict_option() -> None:
    result = runner.invoke(app, ["metrics", "--help"])
    assert result.exit_code == 0
    assert "--strict" in _plain(result.output)


# ---------------------------------------------------------------------------
# Graceful stubs — ingest / refresh
# ---------------------------------------------------------------------------


def test_ingest_exits_with_code_1() -> None:
    result = runner.invoke(app, ["ingest", "mitre"])
    assert result.exit_code == 1


def test_ingest_prints_not_available_message() -> None:
    result = runner.invoke(app, ["ingest", "mitre"])
    assert "not available" in result.output.lower() or "scripts/" in result.output


def test_refresh_exits_with_code_1() -> None:
    result = runner.invoke(app, ["refresh"])
    assert result.exit_code == 1


def test_refresh_since_option_is_accepted() -> None:
    result = runner.invoke(app, ["refresh", "--since", "7d"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Eval — unknown suite
# ---------------------------------------------------------------------------


def test_eval_command_unknown_suite_exits_nonzero() -> None:
    result = runner.invoke(app, ["eval", "foobar"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Query command
# ---------------------------------------------------------------------------


def test_query_command_exits_zero_on_success() -> None:
    with patch("rag_cti.query", return_value=_fake_query_result()):
        result = runner.invoke(app, ["query", "lateral movement via registry run key"])
    assert result.exit_code == 0


def test_query_top_k_option_is_accepted() -> None:
    with patch("rag_cti.query", return_value=_fake_query_result()) as mock_q:
        runner.invoke(app, ["query", "ransomware c2", "--top-k", "5"])
    mock_q.assert_called_once_with("ransomware c2", top_k=5)


def test_query_short_k_flag_is_accepted() -> None:
    with patch("rag_cti.query", return_value=_fake_query_result()) as mock_q:
        runner.invoke(app, ["query", "ransomware c2", "-k", "3"])
    mock_q.assert_called_once_with("ransomware c2", top_k=3)


def test_log_level_option_is_accepted_before_subcommand() -> None:
    with patch("rag_cti.query", return_value=_fake_query_result()):
        result = runner.invoke(app, ["--log-level", "DEBUG", "query", "test query"])
    assert result.exit_code == 0


def test_query_renders_table_header() -> None:
    with patch("rag_cti.query", return_value=_fake_query_result()):
        result = runner.invoke(app, ["query", "test"])
    assert "Score" in result.output or "Rank" in result.output or "Top" in result.output


# ---------------------------------------------------------------------------
# Metrics command
# ---------------------------------------------------------------------------


def test_metrics_exits_1_when_file_missing(tmp_path) -> None:
    missing = tmp_path / "nonexistent.json"
    result = runner.invoke(app, ["metrics", str(missing)])
    assert result.exit_code == 1


def test_metrics_exits_1_on_invalid_json(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    result = runner.invoke(app, ["metrics", str(bad)])
    assert result.exit_code == 1


def test_metrics_exits_0_on_valid_file(tmp_path) -> None:
    import json

    data = {"k_values": [1, 5, 10], "results": []}
    f = tmp_path / "ok.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    result = runner.invoke(app, ["metrics", str(f)])
    assert result.exit_code == 0


def test_metrics_strict_exits_1_on_threshold_violation(tmp_path) -> None:
    import json

    data = {
        "k_values": [1, 5, 10],
        "results": [
            {
                "config": "dense",
                "overall": {"top_k": {10: 0.50}, "mrr": 0.4, "ndcg": {10: 0.4}, "n_queries": 10},
                "by_category": {
                    "fuzzy": {"top_k": {10: 0.40}, "mrr": 0.3, "ndcg": {10: 0.3}, "n_queries": 5}
                },
            }
        ],
    }
    f = tmp_path / "results.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    result = runner.invoke(app, ["metrics", str(f), "--strict"])
    assert result.exit_code == 1


def test_metrics_strict_exits_0_when_thresholds_met(tmp_path) -> None:
    import json

    data = {
        "k_values": [1, 5, 10],
        "results": [
            {
                "config": "dense",
                "overall": {"top_k": {10: 0.80}, "mrr": 0.7, "ndcg": {10: 0.75}, "n_queries": 10},
                "by_category": {
                    "fuzzy": {"top_k": {10: 0.70}, "mrr": 0.6, "ndcg": {10: 0.65}, "n_queries": 5}
                },
            }
        ],
    }
    f = tmp_path / "results.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    result = runner.invoke(app, ["metrics", str(f), "--strict"])
    assert result.exit_code == 0


def test_metrics_prints_warning_on_violation(tmp_path) -> None:
    import json

    data = {
        "k_values": [1, 5, 10],
        "results": [
            {
                "config": "dense",
                "overall": {"top_k": {10: 0.50}, "mrr": 0.4, "ndcg": {10: 0.4}, "n_queries": 10},
                "by_category": {},
            }
        ],
    }
    f = tmp_path / "results.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    result = runner.invoke(app, ["metrics", str(f)])
    assert "WARNING" in result.output
