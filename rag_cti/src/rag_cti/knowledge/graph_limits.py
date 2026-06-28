"""Shared guardrail helpers for LangGraph recursion backstops."""

from __future__ import annotations

from rag_cti.config import Settings


def outer_recursion_limit(settings: Settings) -> int:
    """Runaway backstop for outer agentic/supervisor graphs.

    The structural loop is bounded by ``agentic_max_iterations``; this value is only
    LangGraph's defensive recursion ceiling.
    """
    return max(25, settings.agentic_max_iterations * 4)
