from __future__ import annotations

import groq
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from rag_cti._logging import get_logger

logger = get_logger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient Groq API errors worth retrying (429, 5xx)."""
    status = getattr(exc, "status_code", None)
    return status is not None and (status == 429 or status >= 500)


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
