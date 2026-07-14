from __future__ import annotations

from typing import Any

import groq
from tenacity import (
    Retrying,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from rag_cti._logging import get_logger
from rag_cti.generation.limiter import ConcurrencyLimiter

logger = get_logger(__name__)

# Default ceiling (seconds): a 429 advertising a retry-after above this recovers only
# hours later (daily cap), so it is treated as un-recoverable. Mirrors the
# ``retry_after_ceiling_seconds`` Settings default; both can be overridden from config.
_DEFAULT_RETRY_AFTER_CEILING = 60.0

# Substrings that mark a per-day quota (TPD/RPD) in an error body/message. A daily cap
# resets only at the day boundary, so retrying it with backoff is pure dead time.
_DAILY_CAP_MARKERS = (
    "per day",
    "per-day",
    "tokens per day",
    "tpd",
    "requests per day",
    "rpd",
    "daily limit",
    "daily quota",
)


def _retry_after_seconds(exc: BaseException) -> float | None:
    """Best-effort numeric Retry-After (seconds) from an SDK exception's response headers.

    Returns None when absent or in HTTP-date form (then classification falls through to
    the body markers). httpx.Headers is a case-insensitive mapping."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        raw = headers.get("retry-after")
    except Exception:  # noqa: BLE001 - a non-mapping headers object is just "unknown"
        return None
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _is_daily_cap(exc: BaseException) -> bool:
    """True when a 429's message/body names a per-day quota (TPD/RPD), read defensively
    across the common OpenAI/groq error shapes ({"error": {"message": ...}}, .message, str)."""
    text = str(getattr(exc, "message", "") or "") + " " + str(exc)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            text += " " + " ".join(str(err.get(k, "")) for k in ("message", "code", "type"))
        else:
            text += " " + str(body)
    elif body is not None:
        text += " " + str(body)
    low = text.lower()
    return any(marker in low for marker in _DAILY_CAP_MARKERS)


def _is_retryable(
    exc: BaseException, retry_after_ceiling: float = _DEFAULT_RETRY_AFTER_CEILING
) -> bool:
    """Return True for transient API errors worth retrying.

    5xx -> always (transient server error). 429 -> retry ONLY when it looks recoverable
    within a backoff window (a per-minute / TPM rate limit). A 429 carrying a Retry-After
    larger than ``retry_after_ceiling`` seconds, or whose body names a daily cap (TPD/RPD),
    recovers only hours later, so retrying it just burns the backoff ladder — fail fast
    (return False) and let the caller degrade. An exception without a status code is not
    retryable (kept identical to the original behaviour for back-compat)."""
    status = getattr(exc, "status_code", None)
    if status is None:
        return False
    if status >= 500:
        return True
    if status != 429:
        return False
    retry_after = _retry_after_seconds(exc)
    if retry_after is not None and retry_after > retry_after_ceiling:
        return False
    return not _is_daily_cap(exc)


# ---------------------------------------------------------------------------
# Groq client — tenacity is the SINGLE retry authority (groq SDK max_retries=0),
# with a per-request timeout and 429 classification (TPM retried, TPD fails fast).
# ---------------------------------------------------------------------------


class RetryingGroqClient:
    """Thin wrapper around groq.Groq with exponential backoff on transient 429/5xx.

    ``timeout`` bounds a single HTTP request; ``retry_after_ceiling`` separates a
    recoverable (TPM) 429 from an un-recoverable (TPD) one. ``max_retries=0`` on the
    underlying SDK makes tenacity the only retry layer (no nested SDK retries multiplying
    with the tenacity ladder)."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 30.0,
        retry_after_ceiling: float = _DEFAULT_RETRY_AFTER_CEILING,
        limiter: ConcurrencyLimiter | None = None,
    ) -> None:
        self._raw = groq.Groq(api_key=api_key, max_retries=0, timeout=timeout)
        self.chat = _RetryingChat(
            self._raw, retry_after_ceiling=retry_after_ceiling, limiter=limiter
        )


class _RetryingChat:
    def __init__(
        self,
        client: groq.Groq,
        *,
        retry_after_ceiling: float = _DEFAULT_RETRY_AFTER_CEILING,
        limiter: ConcurrencyLimiter | None = None,
    ) -> None:
        self.completions = _RetryingCompletions(
            client, retry_after_ceiling=retry_after_ceiling, limiter=limiter
        )


class _RetryingCompletions:
    def __init__(
        self,
        client: groq.Groq,
        *,
        retry_after_ceiling: float = _DEFAULT_RETRY_AFTER_CEILING,
        limiter: ConcurrencyLimiter | None = None,
    ) -> None:
        self._client = client
        self._limiter = limiter
        # Instance-level Retrying (not a class decorator) so the per-config retry-after
        # ceiling closes over the predicate. tenacity is the single retry authority.
        self._retrying = Retrying(
            retry=retry_if_exception(lambda exc: _is_retryable(exc, retry_after_ceiling)),
            wait=wait_exponential(multiplier=1, min=1, max=60),
            stop=stop_after_attempt(5),
            reraise=True,
        )

    def create(self, **kwargs: Any) -> groq.types.chat.ChatCompletion:
        return self._retrying(self._create_once, **kwargs)

    def _create_once(self, **kwargs: Any) -> groq.types.chat.ChatCompletion:
        logger.debug("groq chat.completions.create", model=kwargs.get("model"))
        try:
            if self._limiter is None:
                response: groq.types.chat.ChatCompletion = self._client.chat.completions.create(
                    **kwargs
                )
            else:
                with self._limiter.slot():
                    response = self._client.chat.completions.create(**kwargs)
            return response
        except Exception as exc:
            retry_after = _retry_after_seconds(exc)
            if retry_after is not None and self._limiter is not None:
                self._limiter.cooldown(retry_after)
            raise


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
# Provider factory — when OLLAMA_ENABLED: Ollama; else Groq if key
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
                response = self._client.chat.completions.create(model=model, **kwargs)
                if _is_empty_chat_response(response):
                    raise RuntimeError(f"{model} returned empty content")
                return response
            except Exception as exc:  # downgrade to the next model
                last_exc = exc
                logger.warning("generation model failed, downgrading", model=model, error=str(exc))
        assert last_exc is not None  # loop ran >=1 time (models non-empty)
        raise last_exc


def _is_empty_chat_response(response: Any) -> bool:
    """True when a chat completion succeeded transport-wise but produced no content."""
    try:
        content = response.choices[0].message.content
    except Exception:
        return False
    return not str(content or "").strip()


def build_llm_client(settings: Any) -> tuple[str, Any]:
    """Select LLM client: local Ollama if enabled, else Groq (API).

    Returns (provider_name, client) where provider_name is one of
    "ollama" or "groq".
    """
    if settings.ollama_enabled:
        logger.info(
            "llm provider: ollama", base_url=settings.ollama_base_url, model=settings.ollama_model
        )
        return "ollama", RetryingOllamaClient(base_url=settings.ollama_base_url)

    groq_key = settings.groq_api_key.get_secret_value()
    if groq_key:
        from rag_cti.generation.limiter import get_limiter

        logger.info(
            "llm provider: groq",
            hyde_model=settings.groq_query_model,
            analysis_model=settings.groq_analysis_model,
        )
        return "groq", RetryingGroqClient(
            api_key=groq_key,
            timeout=settings.groq_request_timeout,
            retry_after_ceiling=settings.retry_after_ceiling_seconds,
            limiter=get_limiter("groq", settings),
        )

    raise RuntimeError(
        "No LLM provider configured. "
        "Set GROQ_API_KEY or OLLAMA_ENABLED=true for local Ollama."
    )
