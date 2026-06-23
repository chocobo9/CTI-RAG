"""Shared chat-model factory for the agentic answer paths.

This module owns provider admission control for the DeepSeek tool-calling model so
new agent implementations do not depend on the legacy v1 ``agent_graph`` module.
"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from rag_cti.config import Settings
from rag_cti.generation.limiter import ConcurrencyLimiter, get_limiter


class _LimitedChatModel:
    """Wrap LangChain chat models so every invoke goes through provider admission control."""

    def __init__(self, inner: Any, limiter: ConcurrencyLimiter) -> None:
        self._inner = inner
        self._limiter = limiter

    def bind_tools(self, tools: list[Any]) -> _LimitedChatModel:
        return _LimitedChatModel(self._inner.bind_tools(tools), self._limiter)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        with self._limiter.slot():
            return self._inner.invoke(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def build_model(settings: Settings) -> Any:
    """Build the DeepSeek chat model used by gather/supervisor tool-calling loops.

    ``max_retries`` and ``timeout`` are explicit so persistent provider failures fail into
    the loop's graceful-degradation path instead of hanging indefinitely.
    """
    model = ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key=settings.deepseek_api_key,
        temperature=0,
        max_retries=settings.llm_max_retries,
        timeout=settings.deepseek_request_timeout,
    )
    return _LimitedChatModel(model, get_limiter("deepseek", settings))
