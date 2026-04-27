from __future__ import annotations

from rag_cti.generation.client import _is_retryable


# ---------------------------------------------------------------------------
# Stub — lightweight exception with status_code, no Groq SDK dependency
# ---------------------------------------------------------------------------

class _StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Retryable statuses
# ---------------------------------------------------------------------------

def test_429_rate_limit_is_retryable() -> None:
    assert _is_retryable(_StatusError(429))


def test_500_internal_server_is_retryable() -> None:
    assert _is_retryable(_StatusError(500))


def test_503_service_unavailable_is_retryable() -> None:
    assert _is_retryable(_StatusError(503))


def test_529_overloaded_is_retryable() -> None:
    assert _is_retryable(_StatusError(529))


# ---------------------------------------------------------------------------
# Non-retryable statuses
# ---------------------------------------------------------------------------

def test_400_bad_request_not_retryable() -> None:
    assert not _is_retryable(_StatusError(400))


def test_401_unauthorized_not_retryable() -> None:
    assert not _is_retryable(_StatusError(401))


def test_404_not_found_not_retryable() -> None:
    assert not _is_retryable(_StatusError(404))


def test_422_unprocessable_not_retryable() -> None:
    assert not _is_retryable(_StatusError(422))


# ---------------------------------------------------------------------------
# Exceptions without status_code
# ---------------------------------------------------------------------------

def test_value_error_not_retryable() -> None:
    assert not _is_retryable(ValueError("bad input"))


def test_runtime_error_not_retryable() -> None:
    assert not _is_retryable(RuntimeError("crash"))


def test_base_exception_not_retryable() -> None:
    assert not _is_retryable(Exception("generic"))
