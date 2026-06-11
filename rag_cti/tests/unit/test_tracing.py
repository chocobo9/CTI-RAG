from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import rag_cti.observability.tracing as tracing_mod
from rag_cti.observability.tracing import add_trace_metadata, is_tracing_enabled, redact, traced

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_cache() -> None:
    """Reset module-level cache so each test starts clean."""
    tracing_mod._TRACING_ENABLED = None
    tracing_mod._ENV_SETUP_DONE = False


# ---------------------------------------------------------------------------
# is_tracing_enabled
# ---------------------------------------------------------------------------


def test_tracing_disabled_when_api_key_empty() -> None:
    _reset_cache()
    with patch("rag_cti.observability.tracing.get_logger"):
        with patch("rag_cti.config.get_settings") as mock_settings:
            mock_settings.return_value.langsmith_api_key.get_secret_value.return_value = ""
            assert is_tracing_enabled() is False
    _reset_cache()


def test_tracing_disabled_when_langsmith_import_fails() -> None:
    _reset_cache()
    with patch("rag_cti.config.get_settings") as mock_settings:
        mock_settings.return_value.langsmith_api_key.get_secret_value.return_value = "sk-test"
        with patch.dict("sys.modules", {"langsmith": None}):
            result = is_tracing_enabled()
    _reset_cache()
    assert result is False


def test_tracing_enabled_when_key_set_and_sdk_available() -> None:
    _reset_cache()
    fake_langsmith = MagicMock()
    with patch("rag_cti.config.get_settings") as mock_settings:
        mock_settings.return_value.langsmith_api_key.get_secret_value.return_value = "sk-test"
        with patch.dict("sys.modules", {"langsmith": fake_langsmith}):
            result = is_tracing_enabled()
    _reset_cache()
    assert result is True


def test_tracing_result_is_cached() -> None:
    _reset_cache()
    with patch("rag_cti.config.get_settings") as mock_settings:
        mock_settings.return_value.langsmith_api_key.get_secret_value.return_value = ""
        is_tracing_enabled()
        is_tracing_enabled()
        assert mock_settings.call_count == 1
    _reset_cache()


# ---------------------------------------------------------------------------
# traced decorator — disabled path
# ---------------------------------------------------------------------------


def test_traced_returns_original_function_when_disabled() -> None:
    _reset_cache()
    tracing_mod._TRACING_ENABLED = False

    def my_fn(x: int) -> int:
        return x * 2

    decorated = traced("test.span", run_type="chain")(my_fn)
    assert decorated is my_fn
    _reset_cache()


def test_traced_preserves_return_value_when_disabled() -> None:
    _reset_cache()
    tracing_mod._TRACING_ENABLED = False

    @traced("test.span")
    def add(a: int, b: int) -> int:
        return a + b

    assert add(3, 4) == 7
    _reset_cache()


def test_traced_propagates_exceptions_when_disabled() -> None:
    _reset_cache()
    tracing_mod._TRACING_ENABLED = False

    @traced("test.span")
    def boom() -> None:
        raise ValueError("expected")

    with pytest.raises(ValueError, match="expected"):
        boom()
    _reset_cache()


# ---------------------------------------------------------------------------
# traced decorator — enabled path
# ---------------------------------------------------------------------------


def test_traced_calls_traceable_when_enabled() -> None:
    _reset_cache()
    tracing_mod._TRACING_ENABLED = True

    mock_traceable = MagicMock(side_effect=lambda *a, **kw: lambda f: f)
    fake_langsmith = MagicMock()
    fake_langsmith.traceable = mock_traceable

    with patch.dict("sys.modules", {"langsmith": fake_langsmith}):

        @traced("my.span", run_type="llm")
        def fn() -> int:
            return 1

    assert mock_traceable.called
    _reset_cache()


def test_traced_falls_back_to_original_on_import_error() -> None:
    _reset_cache()
    tracing_mod._TRACING_ENABLED = True

    def my_fn() -> str:
        return "ok"

    with patch.dict("sys.modules", {"langsmith": None}):
        result_fn = traced("span")(my_fn)

    assert result_fn is my_fn
    _reset_cache()


def test_traced_wrapped_function_preserves_return_value() -> None:
    _reset_cache()
    tracing_mod._TRACING_ENABLED = True

    fake_langsmith = MagicMock()
    fake_langsmith.traceable = MagicMock(side_effect=lambda *a, **kw: lambda f: f)

    with patch.dict("sys.modules", {"langsmith": fake_langsmith}):

        @traced("span")
        def multiply(x: int, y: int) -> int:
            return x * y

    assert multiply(3, 7) == 21
    _reset_cache()


# ---------------------------------------------------------------------------
# add_trace_metadata
# ---------------------------------------------------------------------------


def test_add_trace_metadata_noop_when_disabled() -> None:
    _reset_cache()
    tracing_mod._TRACING_ENABLED = False
    add_trace_metadata(foo="bar")  # must not raise
    _reset_cache()


def test_add_trace_metadata_noop_when_no_run_tree() -> None:
    _reset_cache()
    tracing_mod._TRACING_ENABLED = True

    fake_run_helpers = MagicMock()
    fake_run_helpers.get_current_run_tree.return_value = None
    fake_langsmith = MagicMock()

    with patch.dict(
        "sys.modules", {"langsmith": fake_langsmith, "langsmith.run_helpers": fake_run_helpers}
    ):
        add_trace_metadata(key="value")  # must not raise

    _reset_cache()


def test_add_trace_metadata_calls_add_metadata_on_run() -> None:
    _reset_cache()
    tracing_mod._TRACING_ENABLED = True

    mock_run = MagicMock()
    fake_run_helpers = MagicMock()
    fake_run_helpers.get_current_run_tree.return_value = mock_run
    fake_langsmith = MagicMock()

    with patch.dict(
        "sys.modules", {"langsmith": fake_langsmith, "langsmith.run_helpers": fake_run_helpers}
    ):
        add_trace_metadata(score=0.9, model="qwen2.5")

    mock_run.add_metadata.assert_called_once_with({"score": 0.9, "model": "qwen2.5"})
    _reset_cache()


# ---------------------------------------------------------------------------
# redact
# ---------------------------------------------------------------------------


def test_redact_removes_api_key_value() -> None:
    s = "request failed: api_key=sk-secret123 not valid"
    assert "sk-secret123" not in redact(s)
    assert "api_key=<redacted>" in redact(s)


def test_redact_removes_bearer_token() -> None:
    s = "Authorization: Bearer eyJhbGciOi..."
    assert "eyJhbGciOi" not in redact(s)


def test_redact_leaves_clean_strings_unchanged() -> None:
    s = "retrieval completed in 45ms"
    assert redact(s) == s


def test_redact_handles_empty_string() -> None:
    assert redact("") == ""
