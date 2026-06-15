"""Unit tests for the content-addressed BlobStore (CAS)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from rag_cti.store.blob_store import BlobIntegrityError, BlobStore


def test_put_returns_sha_and_get_roundtrips(tmp_path):
    store = BlobStore(tmp_path)
    sha = store.put(b"hello pdf bytes")
    assert sha == hashlib.sha256(b"hello pdf bytes").hexdigest()
    assert store.exists(sha)
    assert store.get(sha) == b"hello pdf bytes"


def test_put_is_idempotent_dedup(tmp_path):
    # Identical bytes => one blob file (CAS dedup), same sha.
    store = BlobStore(tmp_path)
    sha1 = store.put(b"same")
    sha2 = store.put(b"same")
    assert sha1 == sha2
    blob_files = [p for p in tmp_path.iterdir() if p.is_file()]
    assert len(blob_files) == 1


def test_get_verify_raises_on_tampered_blob(tmp_path):
    # A3 / C7: tamper a stored blob's bytes => get() raises BlobIntegrityError.
    store = BlobStore(tmp_path)
    sha = store.put(b"original content")
    store.path_for(sha).write_bytes(b"tampered content")
    with pytest.raises(BlobIntegrityError, match="corrupted"):
        store.get(sha)
    # verify=False bypasses the check (returns the tampered bytes).
    assert store.get(sha, verify=False) == b"tampered content"


def test_put_replace_src_dst_under_blob_root(tmp_path, monkeypatch):
    # A4 / C3: os.replace src (tmp) and dst both under <blob_root> => same volume.
    real_replace = os.replace
    captured: dict[str, str] = {}

    def spy(src, dst):
        captured["src"], captured["dst"] = str(src), str(dst)
        return real_replace(src, dst)

    monkeypatch.setattr("os.replace", spy)
    store = BlobStore(tmp_path)
    store.put(b"x")
    root = str(tmp_path)
    assert captured["src"].startswith(root)
    assert captured["dst"].startswith(root)
    assert Path(captured["src"]).parent == tmp_path / ".tmp"  # tmp staged under <root>/.tmp


def test_get_missing_raises(tmp_path):
    store = BlobStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.get("deadbeef")
