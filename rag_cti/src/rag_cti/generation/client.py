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
    def create(self, **kwargs: object) -> groq.types.chat.ChatCompletion:
        logger.debug("groq chat.completions.create", model=kwargs.get("model"))
        return self._client.chat.completions.create(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Ollama client (OpenAI-compatible, drop-in for RetryingGroqClient)
# ---------------------------------------------------------------------------

class RetryingOllamaClient:
    """OpenAI-compatible client for Ollama with retry on transient errors.

    Exposes the same .chat.completions.create() interface as RetryingGroqClient.
    """

    def __init__(self, base_url: str) -> None:
        from openai import OpenAI  # type: ignore[import]

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
# Provider factory — priority: Ollama > Groq > Anthropic
# ---------------------------------------------------------------------------

def build_llm_client(settings: Any) -> tuple[str, Any]:
    """Select LLM client by priority: Ollama > Groq > Anthropic.

    Returns (provider_name, client) where provider_name is one of
    "ollama", "groq", or "anthropic".
    """
    if settings.ollama_enabled:
        logger.info("llm provider: ollama", base_url=settings.ollama_base_url, model=settings.ollama_model)
        return "ollama", RetryingOllamaClient(base_url=settings.ollama_base_url)

    groq_key = settings.groq_api_key.get_secret_value()
    if groq_key:
        logger.info("llm provider: groq")
        return "groq", RetryingGroqClient(api_key=groq_key)

    anthropic_key = settings.anthropic_api_key.get_secret_value()
    if anthropic_key:
        import anthropic  # type: ignore[import]
        logger.info("llm provider: anthropic")
        return "anthropic", anthropic.Anthropic(api_key=anthropic_key)

    raise RuntimeError(
        "No LLM provider configured. "
        "Set OLLAMA_ENABLED=true, GROQ_API_KEY, or ANTHROPIC_API_KEY."
    )
