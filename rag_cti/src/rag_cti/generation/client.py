from __future__ import annotations

from typing import Any

import groq
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from rag_cti._logging import get_logger

logger = get_logger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient API errors worth retrying (429, 5xx)."""
    status = getattr(exc, "status_code", None)
    return status is not None and (status == 429 or status >= 500)


# ---------------------------------------------------------------------------
# Groq client (unchanged)
# ---------------------------------------------------------------------------


class RetryingGroqClient:
    """Thin wrapper around groq.Groq with exponential backoff on 429 and 5xx."""

    def __init__(self, api_key: str) -> None:
        self._raw = groq.Groq(api_key=api_key)
        self.chat = _RetryingChat(self._raw)


class _RetryingChat:
    def __init__(self, client: groq.Groq) -> None:
        self.completions = _RetryingCompletions(client)


class _RetryingCompletions:
    def __init__(self, client: groq.Groq) -> None:
        self._client = client

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def create(self, **kwargs: Any) -> groq.types.chat.ChatCompletion:
        logger.debug("groq chat.completions.create", model=kwargs.get("model"))
        response: groq.types.chat.ChatCompletion = self._client.chat.completions.create(**kwargs)
        return response


# ---------------------------------------------------------------------------
# Ollama client (OpenAI-compatible, drop-in for RetryingGroqClient)
# ---------------------------------------------------------------------------


class RetryingOllamaClient:
    """OpenAI-compatible client for Ollama with retry on transient errors.

    Exposes the same .chat.completions.create() interface as RetryingGroqClient.
    """

    def __init__(self, base_url: str) -> None:
        from openai import OpenAI

        self._raw = OpenAI(base_url=base_url, api_key="ollama")
        self.chat = _RetryingOllamaChat(self._raw)


class _RetryingOllamaChat:
    def __init__(self, client: Any) -> None:
        self.completions = _RetryingOllamaCompletions(client)


class _RetryingOllamaCompletions:
    def __init__(self, client: Any) -> None:
        self._client = client

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def create(self, **kwargs: object) -> Any:
        logger.debug("ollama chat.completions.create", model=kwargs.get("model"))
        return self._client.chat.completions.create(**kwargs)


# ---------------------------------------------------------------------------
# Provider factory — when OLLAMA_ENABLED: Ollama; else Groq if key; else Anthropic
# ---------------------------------------------------------------------------


class FallbackChatClient:
    """OpenAI-compatible client that downgrades across an ordered model list on one
    backend, returning the first success (generation model-downgrade chain).

    The same DeepSeek client is called with each model in turn; a backend failure
    (after that call's own retries) downgrades to the next model. Exposes the same
    ``.chat.completions.create()`` surface, so ``Generator`` uses it unchanged — the
    ``model=`` it passes is ignored; the chain decides the model.
    """

    def __init__(self, client: Any, models: list[str]) -> None:
        if not models:
            raise ValueError("FallbackChatClient needs at least one model")
        self.chat = _FallbackChat(client, models)


class _FallbackChat:
    def __init__(self, client: Any, models: list[str]) -> None:
        self.completions = _FallbackCompletions(client, models)


class _FallbackCompletions:
    def __init__(self, client: Any, models: list[str]) -> None:
        self._client = client
        self._models = models

    def create(self, **kwargs: Any) -> Any:
        kwargs.pop("model", None)  # the chain owns the model, not the caller
        last_exc: Exception | None = None
        for model in self._models:
            try:
                return self._client.chat.completions.create(model=model, **kwargs)
            except Exception as exc:  # downgrade to the next model
                last_exc = exc
                logger.warning("generation model failed, downgrading", model=model, error=str(exc))
        assert last_exc is not None  # loop ran >=1 time (models non-empty)
        raise last_exc


def build_llm_client(settings: Any) -> tuple[str, Any]:
    """Select LLM client: local Ollama if enabled, else Groq (API), else Anthropic.

    Returns (provider_name, client) where provider_name is one of
    "ollama", "groq", or "anthropic".
    """
    if settings.ollama_enabled:
        logger.info(
            "llm provider: ollama", base_url=settings.ollama_base_url, model=settings.ollama_model
        )
        return "ollama", RetryingOllamaClient(base_url=settings.ollama_base_url)

    groq_key = settings.groq_api_key.get_secret_value()
    if groq_key:
        logger.info(
            "llm provider: groq",
            hyde_model=settings.groq_query_model,
            analysis_model=settings.groq_analysis_model,
        )
        return "groq", RetryingGroqClient(api_key=groq_key)

    anthropic_key = settings.anthropic_api_key.get_secret_value()
    if anthropic_key:
        import anthropic

        logger.info("llm provider: anthropic")
        return "anthropic", anthropic.Anthropic(api_key=anthropic_key)

    raise RuntimeError(
        "No LLM provider configured. "
        "Set GROQ_API_KEY, ANTHROPIC_API_KEY, or OLLAMA_ENABLED=true for local Ollama."
    )
