"""Tests for the rag-cti Typer CLI commands."""
from __future__ import annotations

from typer.testing import CliRunner

from rag_cti.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Help / registration
# ---------------------------------------------------------------------------

def test_root_help_exits_cleanly() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "rag-cti" in result.output


def test_all_commands_listed_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    for cmd in ("query", "ingest", "refresh", "eval"):
        assert cmd in result.output


def test_query_help_shows_top_k_option() -> None:
    result = runner.invoke(app, ["query", "--help"])
    assert result.exit_code == 0
    assert "--top-k" in result.output


def test_ingest_help_shows_source_argument() -> None:
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "SOURCE" in result.output or "source" in result.output.lower()


def test_refresh_help_shows_since_option() -> None:
    result = runner.invoke(app, ["refresh", "--help"])
    assert result.exit_code == 0
    assert "--since" in result.output


def test_eval_help_shows_suite_argument() -> None:
    result = runner.invoke(app, ["eval", "--help"])
    assert result.exit_code == 0
    assert "suite" in result.output.lower() or "SUITE" in result.output


# ---------------------------------------------------------------------------
# NotImplementedError stubs
# ---------------------------------------------------------------------------

def test_query_command_raises_not_implemented() -> None:
    result = runner.invoke(app, ["query", "lateral movement via registry run key"])
    assert isinstance(result.exception, NotImplementedError)


def test_ingest_command_raises_not_implemented() -> None:
    result = runner.invoke(app, ["ingest", "mitre"])
    assert isinstance(result.exception, NotImplementedError)


def test_refresh_command_raises_not_implemented() -> None:
    result = runner.invoke(app, ["refresh"])
    assert isinstance(result.exception, NotImplementedError)


def test_eval_command_unknown_suite_exits_nonzero() -> None:
    result = runner.invoke(app, ["eval", "retrieval"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def test_query_top_k_option_is_accepted() -> None:
    result = runner.invoke(app, ["query", "ransomware c2", "--top-k", "5"])
    # NotImplementedError means the command ran — top-k was parsed successfully
    assert isinstance(result.exception, NotImplementedError)


def test_query_short_k_flag_is_accepted() -> None:
    result = runner.invoke(app, ["query", "ransomware c2", "-k", "3"])
    assert isinstance(result.exception, NotImplementedError)


def test_log_level_option_is_accepted_before_subcommand() -> None:
    result = runner.invoke(app, ["--log-level", "DEBUG", "query", "test query"])
    assert isinstance(result.exception, NotImplementedError)


def test_refresh_since_option_is_accepted() -> None:
    result = runner.invoke(app, ["refresh", "--since", "7d"])
    assert isinstance(result.exception, NotImplementedError)
