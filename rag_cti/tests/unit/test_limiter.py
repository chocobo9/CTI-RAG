"""Unit tests for the B3 concurrency + rate limiter (generation.limiter)."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

from rag_cti.generation.limiter import (
    ConcurrencyLimiter,
    TokenBucket,
    get_limiter,
    reset_limiters,
)

# --- TokenBucket ---------------------------------------------------------------


def test_token_bucket_grants_until_empty_then_throttles() -> None:
    clock = [0.0]
    bucket = TokenBucket(capacity=2, refill_per_sec=1.0, clock=lambda: clock[0])
    assert bucket.take(1) == 0.0  # 2 tokens -> available
    assert bucket.take(1) == 0.0  # 1 token -> available
    assert bucket.take(1) == 1.0  # empty, refill 1/s -> wait 1s for the next


def test_token_bucket_refills_over_time() -> None:
    clock = [0.0]
    bucket = TokenBucket(capacity=1, refill_per_sec=1.0, clock=lambda: clock[0])
    assert bucket.take(1) == 0.0  # uses the one token
    clock[0] = 1.0  # 1s later -> 1 token refilled
    assert bucket.take(1) == 0.0


def test_token_bucket_no_refill_never_blocks() -> None:
    bucket = TokenBucket(capacity=1, refill_per_sec=0.0, clock=lambda: 0.0)
    assert bucket.take(1) == 0.0
    assert bucket.take(1) == 0.0  # deficit, but refill 0 disables rate -> wait 0


# --- ConcurrencyLimiter: cooldown + rate (fake clock/sleep, no real time) ------


def test_cooldown_makes_next_slot_wait() -> None:
    slept: list[float] = []
    clock = [100.0]
    lim = ConcurrencyLimiter(
        max_concurrency=2, sleep=lambda s: slept.append(s), clock=lambda: clock[0]
    )
    lim.cooldown(5.0)  # not_before = 105
    with lim.slot():
        pass
    assert slept == [5.0]  # waited the cooldown BEFORE taking the slot (release-before-sleep)


def test_slot_waits_for_rate_token() -> None:
    slept: list[float] = []
    clock = [0.0]
    lim = ConcurrencyLimiter(
        max_concurrency=4,
        rate_per_sec=1.0,
        sleep=lambda s: slept.append(s),
        clock=lambda: clock[0],
    )
    with lim.slot():
        pass  # first call: token available, no wait
    with lim.slot():
        pass  # second call (no time passed): must wait ~1s for a refill
    assert any(s > 0 for s in slept)


def test_disabled_limiter_is_passthrough() -> None:
    lim = ConcurrencyLimiter(max_concurrency=0, rate_per_sec=0.0)
    entered = False
    with lim.slot():
        entered = True
    assert entered  # no blocking, no error


# --- get_limiter registry ------------------------------------------------------


def test_get_limiter_zero_capacity_returns_passthrough() -> None:
    reset_limiters()
    s = SimpleNamespace(llm_max_global_concurrency=0, llm_rate_limit_per_sec=0.0)
    with get_limiter("groq", s).slot():
        pass  # passthrough, never blocks


def test_get_limiter_singleton_per_provider() -> None:
    reset_limiters()
    s = SimpleNamespace(llm_max_global_concurrency=2, llm_rate_limit_per_sec=0.0)
    assert get_limiter("deepseek", s) is get_limiter("deepseek", s)
    assert get_limiter("deepseek", s) is not get_limiter("groq", s)


# --- real-thread concurrency bound ---------------------------------------------


def test_slot_bounds_peak_concurrency() -> None:
    lim = ConcurrencyLimiter(max_concurrency=2)
    lock = threading.Lock()
    current = [0]
    peak = [0]

    def work() -> None:
        with lim.slot():
            with lock:
                current[0] += 1
                peak[0] = max(peak[0], current[0])
            time.sleep(0.02)
            with lock:
                current[0] -= 1

    threads = [threading.Thread(target=work) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak[0] <= 2  # never more than max_concurrency in the slot at once
