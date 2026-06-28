"""Provider-aware concurrency + rate limiter for the parallel agentic paths (B3).

Every parallel path the optimization adds — subquery fan-out, within-turn tool dispatch,
supervisor worker fan-out — can stampede a provider's 429 ceiling (4 workers × ~5 inner calls
≈ 20 concurrent). This admission-controls them WITHOUT retrying: the tenacity policy in
``generation.client`` stays the single per-call retry authority (TPM-retry / TPD-fail-fast);
this only bounds how many calls are in flight and how fast they start.

Two layered limits — the standard pair for LLM APIs that enforce BOTH RPM and TPM:
  * a semaphore bounds CONCURRENCY (how many calls run at once), and
  * an optional token bucket bounds RATE (how many start per second).
A call waits for the rate token (and any post-429 cooldown) BEFORE taking a semaphore slot, and
releases the slot in a ``finally`` — so a slow call or a cooldown never holds a slot while
sleeping, which would starve the pool. ``cooldown`` applies a global pause after a server
``Retry-After``.

Disabled only when ``max_concurrency<=0`` with no rate => ``slot()`` is a
pass-through. Provider protection is otherwise part of the default runtime, not
a feature flag. Limiters are per-provider singletons (Groq and DeepSeek have
independent quotas)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rag_cti.config import Settings


class TokenBucket:
    """Monotonic-clock token bucket: ``capacity`` tokens, refilled at ``refill_per_sec``.

    ``take(n)`` reserves ``n`` tokens (allowing the count to go negative so concurrent callers
    serialize their waits instead of all seeing "available") and returns the seconds the caller
    must sleep before the reservation is satisfied (0 if available now). Thread-safe."""

    def __init__(
        self,
        capacity: float,
        refill_per_sec: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capacity = max(0.0, capacity)
        self._refill = max(0.0, refill_per_sec)
        self._clock = clock
        self._tokens = self._capacity
        self._last = clock()
        self._lock = threading.Lock()

    def take(self, n: float = 1.0) -> float:
        with self._lock:
            now = self._clock()
            self._tokens = min(self._capacity, self._tokens + (now - self._last) * self._refill)
            self._last = now
            if self._tokens >= n:
                wait = 0.0
            elif self._refill > 0:
                wait = (n - self._tokens) / self._refill
            else:
                wait = 0.0  # no refill configured -> never block on rate
            self._tokens -= n
            return wait


class ConcurrencyLimiter:
    """Admission control for parallel provider calls: a concurrency semaphore + an optional
    rate bucket + a global post-429 cooldown gate. ``max_concurrency<=0`` disables the
    semaphore; ``rate_per_sec<=0`` disables the bucket; both disabled => ``slot()`` only honours
    a pending cooldown (none by default) and is otherwise a pass-through."""

    def __init__(
        self,
        max_concurrency: int,
        rate_per_sec: float = 0.0,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sem = threading.Semaphore(max_concurrency) if max_concurrency > 0 else None
        self._bucket = (
            TokenBucket(max(1.0, rate_per_sec), rate_per_sec, clock) if rate_per_sec > 0 else None
        )
        self._sleep = sleep
        self._clock = clock
        self._lock = threading.Lock()
        self._not_before = 0.0  # monotonic ts before which no new call may start (cooldown)

    @contextmanager
    def slot(self) -> Iterator[None]:
        # 1) honour a pending cooldown, 2) wait for a rate token — BOTH before taking a slot, so
        # no semaphore slot is held while sleeping. 3) take the slot, release it in finally.
        self._wait_cooldown()
        if self._bucket is not None:
            wait = self._bucket.take(1.0)
            if wait > 0:
                self._sleep(wait)
        if self._sem is not None:
            self._sem.acquire()
        try:
            yield
        finally:
            if self._sem is not None:
                self._sem.release()

    def _wait_cooldown(self) -> None:
        with self._lock:
            wait = self._not_before - self._clock()
        if wait > 0:
            self._sleep(wait)

    def cooldown(self, retry_after: float) -> None:
        """Apply a global pause of ``retry_after`` seconds before the next call may start (after
        a server Retry-After). Extends, never shortens, an existing cooldown."""
        with self._lock:
            self._not_before = max(self._not_before, self._clock() + max(0.0, retry_after))


# A disabled limiter: no semaphore, no bucket, no cooldown -> slot() is a pure pass-through.
_PASSTHROUGH = ConcurrencyLimiter(max_concurrency=0, rate_per_sec=0.0)

_LIMITERS: dict[str, ConcurrencyLimiter] = {}
_REGISTRY_LOCK = threading.Lock()


def get_limiter(provider: str, settings: Settings) -> ConcurrencyLimiter:
    """Per-provider singleton limiter built from settings.

    Capacity is controlled by ``llm_max_global_concurrency`` and
    ``llm_rate_limit_per_sec``; both zero yields passthrough.
    """
    with _REGISTRY_LOCK:
        limiter = _LIMITERS.get(provider)
        if limiter is None:
            max_concurrency = getattr(settings, "llm_max_global_concurrency", 4)
            rate_per_sec = getattr(settings, "llm_rate_limit_per_sec", 0.0)
            if max_concurrency <= 0 and rate_per_sec <= 0:
                return _PASSTHROUGH
            limiter = ConcurrencyLimiter(
                max_concurrency=max_concurrency,
                rate_per_sec=rate_per_sec,
            )
            _LIMITERS[provider] = limiter
        return limiter


def reset_limiters() -> None:
    """Drop the per-provider singletons — for tests that vary the limiter settings."""
    with _REGISTRY_LOCK:
        _LIMITERS.clear()
