from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from rag_cti.generation.client import (
    FallbackChatClient,
    RetryingGroqClient,
    RetryingOllamaClient,
    _is_retryable,
    _RetryingCompletions,
    build_llm_client,
)

# ---------------------------------------------------------------------------
# Settings stub for build_llm_client
# ---------------------------------------------------------------------------


class _FakeSecret:
    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


class _FakeSettings:
    def __init__(
        self,
        ollama: bool = False,
        groq: str = "",
        base_url: str = "http://localhost:11434/v1",
    ) -> None:
        self.ollama_enabled = ollama
        self.ollama_base_url = base_url
        self.ollama_model = "qwen2.5"
        self.groq_api_key = _FakeSecret(groq)
        self.groq_query_model = "llama-3.1-8b-instant"
        self.groq_analysis_model = "llama-3.3-70b-versatile"
        self.groq_report_model = "llama-3.3-70b-versatile"
        self.groq_request_timeout = 30.0
        self.retry_after_ceiling_seconds = 60.0


# ---------------------------------------------------------------------------
# Stub — lightweight exception with status_code, no Groq SDK dependency
# ---------------------------------------------------------------------------


class _StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Retryable statuses
# ---------------------------------------------------------------------------


def test_429_rate_limit_is_retryable() -> None:
    assert _is_retryable(_StatusError(429))


def test_500_internal_server_is_retryable() -> None:
    assert _is_retryable(_StatusError(500))


def test_503_service_unavailable_is_retryable() -> None:
    assert _is_retryable(_StatusError(503))


def test_529_overloaded_is_retryable() -> None:
    assert _is_retryable(_StatusError(529))


# ---------------------------------------------------------------------------
# Non-retryable statuses
# ---------------------------------------------------------------------------


def test_400_bad_request_not_retryable() -> None:
    assert not _is_retryable(_StatusError(400))


def test_401_unauthorized_not_retryable() -> None:
    assert not _is_retryable(_StatusError(401))


def test_404_not_found_not_retryable() -> None:
    assert not _is_retryable(_StatusError(404))


def test_422_unprocessable_not_retryable() -> None:
    assert not _is_retryable(_StatusError(422))


# ---------------------------------------------------------------------------
# Exceptions without status_code
# ---------------------------------------------------------------------------


def test_value_error_not_retryable() -> None:
    assert not _is_retryable(ValueError("bad input"))


def test_runtime_error_not_retryable() -> None:
    assert not _is_retryable(RuntimeError("crash"))


def test_base_exception_not_retryable() -> None:
    assert not _is_retryable(Exception("generic"))


# ---------------------------------------------------------------------------
# RetryingGroqClient — structure and .create() passthrough
# ---------------------------------------------------------------------------


def test_retrying_groq_client_has_chat_completions() -> None:
    with patch("groq.Groq", return_value=MagicMock()):
        client = RetryingGroqClient(api_key="fake-key")
    assert hasattr(client.chat, "completions")


def test_retrying_groq_completions_create_calls_underlying() -> None:
    mock_groq = MagicMock()
    fake_response = MagicMock()
    mock_groq.chat.completions.create.return_value = fake_response
    with patch("groq.Groq", return_value=mock_groq):
        client = RetryingGroqClient(api_key="fake-key")
    result = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[])
    assert result is fake_response


# ---------------------------------------------------------------------------
# RetryingOllamaClient — structure and .create() passthrough
# ---------------------------------------------------------------------------


def test_retrying_ollama_client_has_chat_completions() -> None:
    with patch("openai.OpenAI", return_value=MagicMock()):
        client = RetryingOllamaClient(base_url="http://localhost:11434/v1")
    assert hasattr(client.chat, "completions")


def test_retrying_ollama_completions_create_calls_underlying() -> None:
    mock_openai = MagicMock()
    fake_response = MagicMock()
    mock_openai.chat.completions.create.return_value = fake_response
    with patch("openai.OpenAI", return_value=mock_openai):
        client = RetryingOllamaClient(base_url="http://localhost:11434/v1")
    result = client.chat.completions.create(model="qwen2.5", messages=[])
    assert result is fake_response


# ---------------------------------------------------------------------------
# build_llm_client factory — provider selection
# ---------------------------------------------------------------------------


def test_build_llm_client_ollama_provider_when_ollama_enabled() -> None:
    with patch("openai.OpenAI", return_value=MagicMock()):
        provider, client = build_llm_client(_FakeSettings(ollama=True))
    assert provider == "ollama"
    assert isinstance(client, RetryingOllamaClient)


def test_build_llm_client_groq_provider_when_groq_key_set() -> None:
    with patch("groq.Groq", return_value=MagicMock()):
        provider, client = build_llm_client(_FakeSettings(groq="gsk_fake"))
    assert provider == "groq"
    assert isinstance(client, RetryingGroqClient)


def test_build_llm_client_ollama_takes_priority_over_groq() -> None:
    with patch("openai.OpenAI", return_value=MagicMock()):
        provider, _ = build_llm_client(_FakeSettings(ollama=True, groq="gsk_fake"))
    assert provider == "ollama"


def test_build_llm_client_raises_when_no_provider_configured() -> None:
    with pytest.raises(RuntimeError, match="No LLM provider"):
        build_llm_client(_FakeSettings())


# ---------------------------------------------------------------------------
# FallbackChatClient — generation model-downgrade chain
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, model: str, content: str = "ok") -> None:
        self.model = model
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]


class _FakeCompletions:
    def __init__(self, fail: set[str], tried: list[str], empty: set[str] | None = None) -> None:
        self._fail = fail
        self._tried = tried
        self._empty = empty or set()

    def create(self, model: str, **_: object) -> _FakeResp:
        self._tried.append(model)
        if model in self._fail:
            raise RuntimeError(f"{model} unavailable")
        return _FakeResp(model, content=("" if model in self._empty else "ok"))


class _FakeChat:
    def __init__(self, fail: set[str], tried: list[str], empty: set[str] | None = None) -> None:
        self.completions = _FakeCompletions(fail, tried, empty)


class _FakeClient:
    def __init__(self, fail: tuple[str, ...] = (), empty: tuple[str, ...] = ()) -> None:
        self.tried: list[str] = []
        self.chat = _FakeChat(set(fail), self.tried, set(empty))


def test_fallback_uses_primary_when_it_succeeds() -> None:
    client = _FakeClient()
    fb = FallbackChatClient(client, ["primary", "backup"])
    resp = fb.chat.completions.create(messages=[], max_tokens=10)
    assert resp.model == "primary"
    assert client.tried == ["primary"]  # backup never tried


def test_fallback_downgrades_on_primary_failure() -> None:
    client = _FakeClient(fail=("primary",))
    fb = FallbackChatClient(client, ["primary", "backup"])
    resp = fb.chat.completions.create(messages=[])
    assert resp.model == "backup"
    assert client.tried == ["primary", "backup"]


def test_fallback_downgrades_on_empty_primary_content() -> None:
    client = _FakeClient(empty=("primary",))
    fb = FallbackChatClient(client, ["primary", "backup"])
    resp = fb.chat.completions.create(messages=[])
    assert resp.model == "backup"
    assert client.tried == ["primary", "backup"]


def test_fallback_ignores_caller_model() -> None:
    client = _FakeClient()
    fb = FallbackChatClient(client, ["chain-model"])
    resp = fb.chat.completions.create(model="ignored", messages=[])
    assert resp.model == "chain-model"  # chain owns the model, caller's is dropped


def test_fallback_raises_when_all_models_fail() -> None:
    client = _FakeClient(fail=("a", "b"))
    fb = FallbackChatClient(client, ["a", "b"])
    with pytest.raises(RuntimeError, match="b unavailable"):
        fb.chat.completions.create(messages=[])
    assert client.tried == ["a", "b"]


def test_fallback_requires_at_least_one_model() -> None:
    with pytest.raises(ValueError, match="at least one model"):
        FallbackChatClient(_FakeClient(), [])


# ---------------------------------------------------------------------------
# 429 classification — TPM (retry) vs TPD / large retry-after (fail fast)
# ---------------------------------------------------------------------------


class _RichRateLimitError(Exception):
    """A 429 SDK-style error carrying optional response headers + structured body."""

    def __init__(
        self,
        *,
        retry_after: str | None = None,
        body: object | None = None,
        message: str = "rate limit",
    ) -> None:
        super().__init__(message)
        self.status_code = 429
        self.message = message
        self.body = body
        self.response = (
            SimpleNamespace(headers={"retry-after": retry_after})
            if retry_after is not None
            else None
        )


def test_429_with_large_retry_after_not_retryable() -> None:
    # retry-after beyond the ceiling => recovery is hours away (daily cap) => fail fast.
    assert not _is_retryable(_RichRateLimitError(retry_after="120"), 60.0)


def test_429_with_small_retry_after_is_retryable() -> None:
    # retry-after within the ceiling => transient per-minute (TPM) => keep retrying.
    assert _is_retryable(_RichRateLimitError(retry_after="5"), 60.0)


def test_429_daily_cap_body_not_retryable() -> None:
    body = {"error": {"message": "Rate limit reached: tokens per day (TPD) exhausted"}}
    assert not _is_retryable(_RichRateLimitError(body=body))


def test_429_per_minute_body_is_retryable() -> None:
    body = {"error": {"message": "Rate limit reached for requests per minute"}}
    assert _is_retryable(_RichRateLimitError(body=body))


def test_429_bare_status_still_retryable_backcompat() -> None:
    # No response/body (the original _StatusError shape) keeps the old behaviour.
    assert _is_retryable(_StatusError(429))


# ---------------------------------------------------------------------------
# Single retry authority: groq SDK retries disabled, per-request timeout set
# ---------------------------------------------------------------------------


def test_groq_client_disables_sdk_retries_and_sets_timeout() -> None:
    captured: dict[str, object] = {}

    def _factory(**kwargs: object) -> MagicMock:
        captured.update(kwargs)
        return MagicMock()

    with patch("groq.Groq", side_effect=_factory):
        RetryingGroqClient(api_key="fake-key", timeout=12.5, retry_after_ceiling=42.0)
    assert captured["max_retries"] == 0  # tenacity is the only retry layer
    assert captured["timeout"] == 12.5


def test_groq_retry_exhausts_then_reraises_without_real_sleep() -> None:
    # A persistent TPM 429 is retried up to stop_after_attempt(5) then reraised. The
    # autouse _no_retry_backoff fixture removes the ~15s of real backoff.
    calls = {"n": 0}

    class _Raising:
        def create(self, **_: object) -> object:
            calls["n"] += 1
            raise _RichRateLimitError(body={"error": {"message": "rate limit per minute"}})

    client = SimpleNamespace(chat=SimpleNamespace(completions=_Raising()))
    completions = _RetryingCompletions(client, retry_after_ceiling=60.0)
    with pytest.raises(_RichRateLimitError):
        completions.create(model="llama-3.1-8b-instant", messages=[])
    assert calls["n"] == 5  # exactly the tenacity attempt cap, no infinite loop
