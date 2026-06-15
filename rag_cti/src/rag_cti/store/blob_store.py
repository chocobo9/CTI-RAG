"""Content-addressed blob store (CAS) for binary raw (e.g. PDF reports).

Immutable, addressed by sha256. Bytes never enter the JSON RawStore — RawStore
holds only a ``{kind:"blob_ref", sha256, ...}`` manifest; the binary lives here,
keyed by its hash. Atomic writes (tmp under ``<root>/.tmp`` on the same volume →
``os.replace``); verify-on-read by default (re-hash, raise on mismatch).
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from rag_cti._logging import get_logger

logger = get_logger(__name__)

_DEFAULT_ROOT = Path("data/raw/blobs")


class BlobIntegrityError(RuntimeError):
    """A blob's bytes do not hash to its address — corruption detected on read."""


class BlobStore:
    """Immutable content-addressed store. Same bytes → same path → dedup."""

    def __init__(self, root: Path = _DEFAULT_ROOT) -> None:
        self._root = Path(root)
        self._tmp = self._root / ".tmp"

    def path_for(self, sha: str) -> Path:
        """The CAS path for a sha. Sharding (sha[:2]/sha[2:4]/sha) is a single-
        function change here — left as a TODO until the file count warrants it."""
        return self._root / sha

    def exists(self, sha: str) -> bool:
        return self.path_for(sha).exists()

    def put(self, data: bytes) -> str:
        """Store bytes, return their sha256 address. Idempotent: an existing blob
        is a no-op (CAS dedup). Atomic: tmp under ``<root>/.tmp`` → ``os.replace``."""
        sha = hashlib.sha256(data).hexdigest()
        dst = self.path_for(sha)
        if dst.exists():
            logger.info("blob exists, dedup", sha=sha, size_bytes=len(data))
            return sha

        self._tmp.mkdir(parents=True, exist_ok=True)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._tmp / f"{uuid.uuid4().hex}.part"
        try:
            with open(tmp, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, dst)  # atomic; tmp and dst both under <root> = same volume
        finally:
            if tmp.exists():
                tmp.unlink()
        logger.info("blob written", sha=sha, size_bytes=len(data))
        return sha

    def get(self, sha: str, verify: bool = True) -> bytes:
        """Read a blob. By default re-hash and verify against ``sha`` (C7)."""
        path = self.path_for(sha)
        if not path.exists():
            raise FileNotFoundError(f"no blob: {sha}")
        data = path.read_bytes()
        if verify:
            actual = hashlib.sha256(data).hexdigest()
            if actual != sha:
                raise BlobIntegrityError(f"blob {sha} hashes to {actual} — corrupted")
        return data
