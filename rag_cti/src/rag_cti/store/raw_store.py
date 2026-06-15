"""Append-only, versioned raw record store (Layer-0 evidence substrate).

Source-ingestion design §3/§7.1: the raw source response is preserved verbatim,
versioned by ``(source_id, fetched_at)``, and **never overwritten**. A re-fetch
of a modified record appends a new version; the prior version is kept. This is
the permanent evidence substrate that makes every downstream projection (chunks,
entities, facts) regenerable, and the reason most other ingestion drops are
reversible.

Layout::

    {root}/{source}/{source_id}/{fetched_at}.json

Each version file stores ``{source, source_id, fetched_at, payload}`` so the
canonical keys survive filename sanitisation. ``fetched_at`` is an ISO-8601
timestamp; unsafe characters (``:`` etc.) are replaced for filename safety while
preserving lexicographic == chronological ordering of fixed-width timestamps.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rag_cti._logging import get_logger

logger = get_logger(__name__)

_DEFAULT_ROOT = Path("data/raw")
_UNSAFE = '<>:"/\\|?*'

# Deterministic "no recorded fetch event" sentinel for retrieved_at — never
# wall-clock, so rebuilds reproduce. Used for records with no RawStore fetch
# timestamp yet (e.g. pre-existing PDFs).
SENTINEL_FETCHED_AT = datetime(1970, 1, 1, tzinfo=UTC)


def parse_fetched_at(value: str | None) -> datetime:
    """Parse a RawStore ``fetched_at`` id to a datetime; SENTINEL when absent/bad.

    This is the single source of a chunk's ``retrieved_at`` — *when we fetched
    the record* — distinct from the source's own modification time (which stays
    in ``metadata.last_modified``)."""
    if not value:
        return SENTINEL_FETCHED_AT
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return SENTINEL_FETCHED_AT


def _sanitize(name: str) -> str:
    """Make a key component safe as a single path segment.

    The canonical value is also stored inside each version file, so this only
    needs to be deterministic and collision-rare for real ids (pulse hashes,
    domains, STIX ids); genuine collisions are detected at write time.
    """
    out = "".join("-" if c in _UNSAFE else c for c in name)
    return out.strip().strip(".") or "_"


class RawStoreConflictError(RuntimeError):
    """A write would overwrite an existing version with different content, or two
    distinct source_ids collide after sanitisation — an append-only / Rule-0
    violation. Raised loudly instead of silently destroying prior state."""


class RawStore:
    """Append-only versioned store for raw source records."""

    def __init__(self, root: Path = _DEFAULT_ROOT) -> None:
        self._root = Path(root)

    # -- paths -------------------------------------------------------------
    def _dir(self, source: str, source_id: str) -> Path:
        return self._root / _sanitize(source) / _sanitize(source_id)

    def _path(self, source: str, source_id: str, fetched_at: str) -> Path:
        return self._dir(source, source_id) / f"{_sanitize(fetched_at)}.json"

    # -- write -------------------------------------------------------------
    def write(self, source: str, source_id: str, payload: Any, fetched_at: str) -> Path:
        """Append a version. Idempotent for an identical payload at the same key;
        raises ``RawStoreConflictError`` if the key exists with different content or
        the directory already holds a different source_id (sanitisation clash)."""
        if not source or not source_id or not fetched_at:
            raise ValueError("source, source_id and fetched_at are all required")

        path = self._path(source, source_id, fetched_at)
        self._assert_no_id_collision(path.parent, source_id)

        record = {
            "source": source,
            "source_id": source_id,
            "fetched_at": fetched_at,
            "payload": payload,
        }
        new_bytes = json.dumps(record, ensure_ascii=False, sort_keys=True)

        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing == new_bytes:
                return path  # idempotent no-op
            raise RawStoreConflictError(
                "raw version already exists with different content: "
                f"source={source} source_id={source_id} fetched_at={fetched_at}"
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(new_bytes)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)  # atomic; same dir = same volume
        finally:
            if tmp.exists():
                tmp.unlink()
        logger.info(
            "raw version written", source=source, source_id=source_id, fetched_at=fetched_at
        )
        return path

    @staticmethod
    def _assert_no_id_collision(dir_: Path, source_id: str) -> None:
        if not dir_.exists():
            return
        for fp in dir_.glob("*.json"):
            try:
                other = json.loads(fp.read_text(encoding="utf-8")).get("source_id")
            except (json.JSONDecodeError, OSError):
                continue
            if other is not None and other != source_id:
                raise RawStoreConflictError(
                    f"source_id path collision after sanitisation: {source_id!r} vs {other!r}"
                )
            return

    # -- read --------------------------------------------------------------
    def versions(self, source: str, source_id: str) -> list[str]:
        """Sorted ``fetched_at`` ids for a source_id (chronological)."""
        d = self._dir(source, source_id)
        if not d.exists():
            return []
        out: list[str] = []
        for fp in d.glob("*.json"):
            try:
                rec = json.loads(fp.read_text(encoding="utf-8"))
                out.append(str(rec.get("fetched_at", fp.stem)))
            except (json.JSONDecodeError, OSError):
                continue
        return sorted(out)

    def read(self, source: str, source_id: str, fetched_at: str) -> Any:
        path = self._path(source, source_id, fetched_at)
        if not path.exists():
            raise FileNotFoundError(
                f"no raw version: source={source} source_id={source_id} fetched_at={fetched_at}"
            )
        return json.loads(path.read_text(encoding="utf-8"))["payload"]

    def latest(self, source: str, source_id: str) -> Any | None:
        vs = self.versions(source, source_id)
        if not vs:
            return None
        return self.read(source, source_id, vs[-1])

    def source_ids(self, source: str) -> list[str]:
        sdir = self._root / _sanitize(source)
        if not sdir.exists():
            return []
        ids: list[str] = []
        for d in sdir.iterdir():
            if not d.is_dir():
                continue
            for fp in d.glob("*.json"):
                try:
                    rec = json.loads(fp.read_text(encoding="utf-8"))
                    ids.append(str(rec.get("source_id", d.name)))
                    break
                except (json.JSONDecodeError, OSError):
                    continue
        return sorted(ids)

    def iter_latest(self, source: str) -> Iterator[tuple[str, Any]]:
        """``(source_id, latest payload)`` for every source_id under ``source``."""
        for sid in self.source_ids(source):
            payload = self.latest(source, sid)
            if payload is not None:
                yield sid, payload

    def latest_fetched_at(self, source: str) -> str | None:
        """The max ``fetched_at`` across all source_ids — the incremental
        high-water mark to feed a connector's ``modified_since``. None if empty."""
        latest: str | None = None
        for sid in self.source_ids(source):
            vs = self.versions(source, sid)
            if vs and (latest is None or vs[-1] > latest):
                latest = vs[-1]
        return latest
