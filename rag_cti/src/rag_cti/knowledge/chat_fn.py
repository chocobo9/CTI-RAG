"""Shared OpenAI-compatible chat wrapper for injected judge/composer roles."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ChatFn = Callable[[str, str], str]


def build_chat_fn(client: Any, model: str, max_tokens: int = 1024) -> ChatFn:
    """Return a ``(system, user) -> text`` function over an OpenAI-compatible client."""

    def chat_fn(system: str, user: str) -> str:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
            )
            content: str = response.choices[0].message.content or ""
            return content
        except Exception:
            return ""

    return chat_fn
