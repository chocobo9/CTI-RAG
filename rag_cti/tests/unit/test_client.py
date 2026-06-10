from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rag_cti.generation.client import (
    RetryingGroqClient,
    RetryingOllamaClient,
    _is_retryable,
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
        anthropic: str = "",
        base_url: str = "http://localhost:11434/v1",
    ) -> None:
        self.ollama_enabled = ollama
        self.ollama_base_url = base_url
        self.ollama_model = "qwen2.5"
        self.groq_api_key = _FakeSecret(groq)
        self.groq_query_model = "llama-3.1-8b-instant"
        self.groq_analysis_model = "llama-3.3-70b-versatile"
        self.groq_report_model = "llama-3.3-70b-versatile"
        self.anthropic_api_key = _FakeSecret(anthropic)


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


def test_build_llm_client_anthropic_provider_when_only_anthropic_key() -> None:
    mock_anthropic_cls = MagicMock()
    mock_anthropic_inst = MagicMock()
    mock_anthropic_cls.return_value = mock_anthropic_inst
    with patch("anthropic.Anthropic", mock_anthropic_cls):
        provider, client = build_llm_client(_FakeSettings(anthropic="sk-ant-fake"))
    assert provider == "anthropic"
    assert client is mock_anthropic_inst


def test_build_llm_client_ollama_takes_priority_over_groq() -> None:
    with patch("openai.OpenAI", return_value=MagicMock()):
        provider, _ = build_llm_client(_FakeSettings(ollama=True, groq="gsk_fake"))
    assert provider == "ollama"


def test_build_llm_client_raises_when_no_provider_configured() -> None:
    with pytest.raises(RuntimeError, match="No LLM provider"):
        build_llm_client(_FakeSettings())
