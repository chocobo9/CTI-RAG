"""LangSmith tracing seam.

Single integration point for LangSmith observability. All wiring goes through
this module so the rest of the codebase never imports langsmith directly.

Behaviour:
  - Tracing enabled when settings.langsmith_api_key is non-empty AND the
    langsmith package is importable.
  - When disabled every decorator and helper is a true no-op (the original
    function object is returned unwrapped — zero per-call overhead).
  - Trace payloads never include raw API keys or full chunk text; outputs carry
    IDs, scores, and short text snippets only.
"""

from __future__ import annotations

import atexit
import functools
import os
import re
import threading
from collections.abc import Callable
from typing import Any, Literal, TypeVar, cast

from rag_cti._logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Mirrors langsmith.client.RUN_TYPE_T so callers stay typo-safe without
# importing langsmith eagerly.
RunType = Literal["tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"]

_TRACING_ENABLED: bool | None = None  # cached after first call
_ENV_SETUP_DONE: bool = False


def is_tracing_enabled() -> bool:
    """Return True if LangSmith tracing is configured and the SDK is available."""
    global _TRACING_ENABLED
    if _TRACING_ENABLED is not None:
        return _TRACING_ENABLED

    try:
        from rag_cti.config import get_settings

        key = get_settings().langsmith_api_key.get_secret_value()
        if not key:
            _TRACING_ENABLED = False
            return False
        import langsmith  # noqa: F401

        _TRACING_ENABLED = True
    except Exception:
        _TRACING_ENABLED = False

    return _TRACING_ENABLED


def _setup_env_once() -> None:
    """Set LangSmith env vars from settings (idempotent)."""
    global _ENV_SETUP_DONE
    if _ENV_SETUP_DONE:
        return
    _ENV_SETUP_DONE = True
    try:
        from rag_cti.config import get_settings

        s = get_settings()
        key = s.langsmith_api_key.get_secret_value()
        if key and not os.environ.get("LANGCHAIN_API_KEY"):
            os.environ["LANGCHAIN_API_KEY"] = key
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true" if s.langchain_tracing_v2 else "false")
        os.environ.setdefault("LANGCHAIN_PROJECT", s.langsmith_project)
        # Default the submission to synchronous-but-bounded (background=false) so a
        # tracing-side 429 cannot leave a background queue blocking process exit; bound
        # the worst case further with an atexit flush (abandoned after its own timeout).
        os.environ.setdefault(
            "LANGCHAIN_CALLBACKS_BACKGROUND",
            "true" if s.langchain_callbacks_background else "false",
        )
        atexit.register(flush_tracers)
    except Exception as exc:
        logger.warning("langsmith env setup failed", error=str(exc))


def traced(
    name: str,
    run_type: RunType = "chain",
) -> Callable[[F], F]:
    """Decorator that wraps a function with a LangSmith trace span.

    When tracing is disabled the original function is returned unwrapped —
    zero per-call overhead.

    Args:
        name: Span name shown in LangSmith UI.
        run_type: LangSmith run type — "retriever", "llm", "chain", etc.

    Returns:
        Decorator that wraps the target function, or the identity when tracing
        is disabled.
    """

    def decorator(fn: F) -> F:
        if not is_tracing_enabled():
            return fn

        _setup_env_once()

        try:
            from langsmith import traceable

            trace_decorator = cast(Callable[[F], F], traceable(run_type=run_type, name=name))

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return fn(*args, **kwargs)

            return trace_decorator(cast(F, wrapper))
        except Exception as exc:
            logger.warning(
                "langsmith traceable setup failed — tracing disabled for this function",
                function=fn.__name__,
                error=str(exc),
            )
            return fn

    return decorator


def flush_tracers(timeout: float = 5.0) -> None:
    """Best-effort, time-bounded flush of pending LangSmith traces.

    No-op when tracing is disabled. Never raises and never blocks longer than ``timeout``:
    the SDK's blocking ``wait_for_all_tracers`` runs in a daemon thread we only join for
    ``timeout`` seconds, so a tracing-side 429 (which would otherwise retry on the
    background queue) cannot hang process exit — the daemon thread is abandoned at exit.
    Registered via ``atexit`` when tracing is enabled."""
    if not is_tracing_enabled():
        return
    try:
        # Canonical, version-stable location (langsmith dropped the top-level re-export).
        from langchain_core.tracers.langchain import wait_for_all_tracers

        worker = threading.Thread(target=wait_for_all_tracers, daemon=True)
        worker.start()
        worker.join(timeout)
    except Exception as exc:
        logger.debug("flush_tracers failed", error=str(exc))


def add_trace_metadata(**kwargs: Any) -> None:
    """Attach extra key/value metadata to the current LangSmith run span.

    No-op when tracing is disabled or called outside a traced context.
    Never raises.
    """
    if not is_tracing_enabled():
        return
    try:
        from langsmith.run_helpers import get_current_run_tree

        run = get_current_run_tree()
        if run is not None:
            run.add_metadata(kwargs)
    except Exception as exc:
        # Never raise from observability, but never swallow invisibly either.
        logger.debug("add_trace_metadata failed", error=str(exc))


_SECRET_PATTERN = re.compile(
    r"(api[_-]?key|token|authorization)\s*[=:]\s*(?:bearer\s+)?\S+",
    re.IGNORECASE,
)


def redact(value: str) -> str:
    """Redact substrings that look like secrets from a string.

    Used before any value is added to a trace payload.
    """
    return _SECRET_PATTERN.sub(r"\1=<redacted>", value)
