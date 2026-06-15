"""Unit tests for PDF ingest: BlobStore (bytes) + RawStore (JSON manifest)."""

from __future__ import annotations

import hashlib
import json

import pytest

from rag_cti.ingest.ingest_pdf import backfill_pdfs, ingest_pdf
from rag_cti.store.blob_store import BlobStore
from rag_cti.store.raw_store import SENTINEL_FETCHED_AT, RawStore, parse_fetched_at


def _pdf(d, name, content):
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_bytes(content)
    return p


def _blob_files(root):
    return [p for p in root.iterdir() if p.is_file()]


def test_ingest_pdf_manifest_shape_and_blob_stored(tmp_path):
    # C1/C4: manifest is pure JSON, no physical path; blob holds the bytes.
    pdf = _pdf(tmp_path / "pdfs", "a.pdf", b"%PDF fake bytes")
    blob = BlobStore(tmp_path / "blobs")
    rs = RawStore(tmp_path / "raw")
    manifest = ingest_pdf(pdf, blob, rs)
    assert manifest == {
        "kind": "blob_ref",
        "sha256": hashlib.sha256(b"%PDF fake bytes").hexdigest(),
        "size_bytes": len(b"%PDF fake bytes"),
        "content_type": "application/pdf",
        "filename": "a.pdf",
    }
    assert blob.exists(manifest["sha256"])  # bytes are in the BlobStore
    assert "path" not in manifest  # C4: no physical path
    assert "pdf_path" not in manifest


def test_blob_put_failure_leaves_no_dangling_manifest(tmp_path, monkeypatch):
    # C2: blob.put before raw_store.write => a blob failure writes no manifest.
    pdf = _pdf(tmp_path / "pdfs", "a.pdf", b"x")
    blob = BlobStore(tmp_path / "blobs")
    rs = RawStore(tmp_path / "raw")

    def boom(_data):
        raise OSError("blob disk failure")

    monkeypatch.setattr(blob, "put", boom)
    with pytest.raises(OSError, match="disk"):
        ingest_pdf(pdf, blob, rs)
    assert rs.latest("pdf", "a.pdf") is None  # no dangling reference


def test_backfill_is_idempotent(tmp_path):
    # A1: backfill twice => 2nd run no new blobs, no error, manifest unchanged.
    pdfdir = tmp_path / "pdfs"
    _pdf(pdfdir, "a.pdf", b"aaa")
    _pdf(pdfdir, "b.pdf", b"bbb")
    blob = BlobStore(tmp_path / "blobs")
    rs = RawStore(tmp_path / "raw")

    assert backfill_pdfs(pdfdir, blob, rs) == 2
    blobs_1 = sorted(p.name for p in _blob_files(tmp_path / "blobs"))
    m_before = rs.latest("pdf", "a.pdf")

    backfill_pdfs(pdfdir, blob, rs)  # 2nd run must not raise
    blobs_2 = sorted(p.name for p in _blob_files(tmp_path / "blobs"))
    assert blobs_1 == blobs_2  # zero new blobs
    assert rs.latest("pdf", "a.pdf") == m_before  # manifest unchanged (no-op)


def test_backfill_dedups_identical_files(tmp_path):
    # A2: two byte-identical PDFs => ONE blob, TWO manifests pointing to same sha.
    pdfdir = tmp_path / "pdfs"
    _pdf(pdfdir, "ms.pdf", b"identical-bytes")
    _pdf(pdfdir, "ms (1).pdf", b"identical-bytes")
    blob = BlobStore(tmp_path / "blobs")
    rs = RawStore(tmp_path / "raw")
    backfill_pdfs(pdfdir, blob, rs)
    assert len(_blob_files(tmp_path / "blobs")) == 1  # ONE blob (dedup)
    m1 = rs.latest("pdf", "ms.pdf")
    m2 = rs.latest("pdf", "ms (1).pdf")
    assert m1["sha256"] == m2["sha256"]  # two manifests, same sha


def test_manifest_on_disk_has_no_absolute_path(tmp_path):
    # A5: the manifest file has no drive-letter / absolute-path substring.
    _pdf(tmp_path / "pdfs", "a.pdf", b"x")
    blob = BlobStore(tmp_path / "blobs")
    rs = RawStore(tmp_path / "raw")
    backfill_pdfs(tmp_path / "pdfs", blob, rs)
    raw_file = next((tmp_path / "raw" / "pdf").rglob("*.json"))
    text = raw_file.read_text(encoding="utf-8")
    assert "D:/" not in text
    assert "D:\\" not in text
    assert str(tmp_path) not in text  # no absolute root path leaked


def test_manifest_roundtrips_via_latest(tmp_path):
    # A6: latest("pdf", fname) returns non-None payload, json round-trips equal.
    _pdf(tmp_path / "pdfs", "a.pdf", b"x")
    blob = BlobStore(tmp_path / "blobs")
    rs = RawStore(tmp_path / "raw")
    backfill_pdfs(tmp_path / "pdfs", blob, rs)
    payload = rs.latest("pdf", "a.pdf")
    assert payload is not None
    assert json.loads(json.dumps(payload)) == payload


def test_fetched_at_is_sentinel(tmp_path):
    # A7: versions("pdf",fname) -> str; parse_fetched_at -> == SENTINEL_FETCHED_AT.
    # (parse must accept the "+00:00" offset, not only "Z".)
    _pdf(tmp_path / "pdfs", "a.pdf", b"x")
    blob = BlobStore(tmp_path / "blobs")
    rs = RawStore(tmp_path / "raw")
    backfill_pdfs(tmp_path / "pdfs", blob, rs)
    versions = rs.versions("pdf", "a.pdf")
    assert len(versions) == 1
    assert parse_fetched_at(versions[-1]) == SENTINEL_FETCHED_AT
