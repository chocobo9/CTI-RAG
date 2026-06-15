"""Unit tests for the append-only versioned RawStore (ingestion §3/§7.1)."""

from __future__ import annotations

import pytest

from rag_cti.store.raw_store import RawStore, RawStoreConflictError


def test_write_and_read_roundtrip(tmp_path):
    store = RawStore(tmp_path)
    store.write(
        "otx",
        "pulse1",
        {"a": 1, "indicators": [{"v": "x", "type": "domain"}]},
        "2026-01-01T00:00:00Z",
    )
    assert store.read("otx", "pulse1", "2026-01-01T00:00:00Z") == {
        "a": 1,
        "indicators": [{"v": "x", "type": "domain"}],
    }


def test_write_is_idempotent_for_identical_payload(tmp_path):
    store = RawStore(tmp_path)
    p1 = store.write("otx", "pulse1", {"a": 1}, "2026-01-01T00:00:00Z")
    p2 = store.write("otx", "pulse1", {"a": 1}, "2026-01-01T00:00:00Z")
    assert p1 == p2
    assert len(list((tmp_path / "otx" / "pulse1").glob("*.json"))) == 1


def test_conflicting_payload_at_same_key_raises(tmp_path):
    store = RawStore(tmp_path)
    store.write("otx", "pulse1", {"a": 1}, "2026-01-01T00:00:00Z")
    with pytest.raises(RawStoreConflictError):
        store.write("otx", "pulse1", {"a": 2}, "2026-01-01T00:00:00Z")
    # prior version is intact, not overwritten
    assert store.read("otx", "pulse1", "2026-01-01T00:00:00Z") == {"a": 1}


def test_new_fetched_at_appends_version_without_overwriting(tmp_path):
    store = RawStore(tmp_path)
    store.write("otx", "pulse1", {"v": "old"}, "2026-01-01T00:00:00Z")
    store.write("otx", "pulse1", {"v": "new"}, "2026-02-01T00:00:00Z")
    assert store.versions("otx", "pulse1") == [
        "2026-01-01T00:00:00Z",
        "2026-02-01T00:00:00Z",
    ]
    assert store.read("otx", "pulse1", "2026-01-01T00:00:00Z") == {"v": "old"}
    assert store.latest("otx", "pulse1") == {"v": "new"}


def test_latest_and_versions_missing_are_empty(tmp_path):
    store = RawStore(tmp_path)
    assert store.latest("otx", "nope") is None
    assert store.versions("otx", "nope") == []


def test_read_missing_raises(tmp_path):
    store = RawStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.read("otx", "nope", "2026-01-01T00:00:00Z")


def test_iter_latest_one_entry_per_source_id(tmp_path):
    store = RawStore(tmp_path)
    store.write("otx", "p1", {"n": 1}, "2026-01-01T00:00:00Z")
    store.write("otx", "p1", {"n": 2}, "2026-02-01T00:00:00Z")
    store.write("otx", "p2", {"n": 9}, "2026-01-01T00:00:00Z")
    assert dict(store.iter_latest("otx")) == {"p1": {"n": 2}, "p2": {"n": 9}}


def test_source_id_with_unsafe_chars_roundtrips(tmp_path):
    store = RawStore(tmp_path)
    store.write("vt", "http://evil.com/x", {"k": "v"}, "2026-01-01T00:00:00Z")
    assert store.source_ids("vt") == ["http://evil.com/x"]
    assert store.latest("vt", "http://evil.com/x") == {"k": "v"}


def test_sanitisation_collision_between_distinct_ids_raises(tmp_path):
    store = RawStore(tmp_path)
    # 'a:b' and 'a/b' both sanitise to 'a-b' — must not silently share a dir
    store.write("vt", "a:b", {"id": "first"}, "2026-01-01T00:00:00Z")
    with pytest.raises(RawStoreConflictError):
        store.write("vt", "a/b", {"id": "second"}, "2026-01-02T00:00:00Z")


def test_missing_required_fields_raise(tmp_path):
    store = RawStore(tmp_path)
    with pytest.raises(ValueError, match="required"):
        store.write("", "id", {}, "2026-01-01T00:00:00Z")
    with pytest.raises(ValueError, match="required"):
        store.write("otx", "", {}, "2026-01-01T00:00:00Z")
    with pytest.raises(ValueError, match="required"):
        store.write("otx", "id", {}, "")
