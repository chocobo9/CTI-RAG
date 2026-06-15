"""Ingest PDF reports: bytes → BlobStore (CAS), manifest → RawStore.

- C1: RawStore unchanged; PDF bytes never enter RawStore; manifest is pure JSON.
- C2: ``blob.put`` first (get the sha), then ``raw_store.write(manifest)`` — so a
  blob-write failure leaves no dangling manifest reference.
- C4: the manifest stores no physical path; the blob path is computed from the
  sha via ``BlobStore.path_for``.
- C5: ``retrieved_at`` provenance uses the shared ``SENTINEL_FETCHED_AT`` (existing
  PDFs have no recorded fetch event).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.store.blob_store import BlobStore
from rag_cti.store.raw_store import SENTINEL_FETCHED_AT, RawStore

logger = get_logger(__name__)

_PDF_DIR = Path("data/raw/pdfs")


def ingest_pdf(path: Path, blob: BlobStore, raw_store: RawStore) -> dict[str, Any]:
    """Ingest one PDF: store its bytes in the BlobStore, then write a manifest to
    the RawStore. Returns the manifest. Blob-first (C2)."""
    data = path.read_bytes()
    sha = blob.put(data)  # C2: blob succeeds (returns sha) before the manifest
    manifest: dict[str, Any] = {
        "kind": "blob_ref",  # forward-compat marker; no resolver layer yet
        "sha256": sha,
        "size_bytes": len(data),
        "content_type": "application/pdf",
        "filename": path.name,  # C4: a name, never a physical path
    }
    raw_store.write("pdf", path.name, manifest, SENTINEL_FETCHED_AT.isoformat())  # C5
    return manifest


def backfill_pdfs(
    pdf_dir: Path = _PDF_DIR,
    blob: BlobStore | None = None,
    raw_store: RawStore | None = None,
) -> int:
    """Ingest every PDF under ``pdf_dir`` into BlobStore + RawStore. Idempotent
    (C6): an existing blob is skipped (dedup) and an identical manifest is a
    RawStore no-op, so re-running has no side effect. Returns the count seen."""
    blob = blob or BlobStore()
    raw_store = raw_store or RawStore()
    seen = 0
    for pdf in sorted(pdf_dir.glob("**/*.pdf")):
        ingest_pdf(pdf, blob, raw_store)
        seen += 1
    logger.info("backfill complete", pdf_dir=str(pdf_dir), seen=seen)
    return seen
