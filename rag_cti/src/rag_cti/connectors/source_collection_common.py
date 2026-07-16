"""Small filesystem/HTTP helpers for source-specific collection modules."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


def now_utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(*values: Any) -> str:
    encoded = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
    return sha256_bytes(encoded)


def canonical_json(value: Any) -> bytes:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    text = text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return (text + "\n").encode()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    for attempt in range(6):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2).encode() + b"\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    atomic_write(
        path,
        b"".join(canonical_json(row) for row in rows),
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class SafeHttpClient:
    """HTTP adapter restricted by each caller to its official host allow-list."""

    def __init__(self, *, timeout: float = 90, retries: int = 4, delay: float = 0.1) -> None:
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": "rag-cti-source-collector/1.0"},
        )
        self.retries = retries
        self.delay = delay

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.client.get(url, **kwargs)
                if response.status_code not in {429, 500, 502, 503, 504}:
                    return response
                retry_after = response.headers.get("retry-after")
                wait = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else min(2**attempt, 8)
                )
                last = RuntimeError(f"temporary HTTP {response.status_code}")
            except httpx.TransportError as exc:
                last = exc
                wait = min(2**attempt, 8)
            if attempt < self.retries:
                time.sleep(wait)
        raise RuntimeError(f"request failed after retries: {url}: {last}")
