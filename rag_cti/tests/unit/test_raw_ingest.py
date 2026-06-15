"""Unit tests for routing connector fetches through the versioned RawStore."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from rag_cti.ingest.raw_ingest import fetch_to_raw, read_domains_from_index
from rag_cti.store.raw_store import RawStore


class _FakeConnector:
    source_name = "otx"

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    def fetch(self, **_: Any) -> Iterator[dict[str, Any]]:
        yield from self._records


def test_fetch_to_raw_writes_each_record(tmp_path):
    store = RawStore(tmp_path)
    conn = _FakeConnector([{"id": "p1", "x": 1}, {"id": "p2", "x": 2}])
    n = fetch_to_raw(conn, store, "2026-01-01T00:00:00Z")
    assert n == 2
    assert dict(store.iter_latest("otx")) == {
        "p1": {"id": "p1", "x": 1},
        "p2": {"id": "p2", "x": 2},
    }


def test_refetch_appends_version_and_high_water_mark_advances(tmp_path):
    store = RawStore(tmp_path)
    fetch_to_raw(_FakeConnector([{"id": "p1", "v": "old"}]), store, "2026-01-01T00:00:00Z")
    fetch_to_raw(_FakeConnector([{"id": "p1", "v": "new"}]), store, "2026-02-01T00:00:00Z")
    assert store.versions("otx", "p1") == ["2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"]
    assert store.latest("otx", "p1") == {"id": "p1", "v": "new"}
    assert store.latest_fetched_at("otx") == "2026-02-01T00:00:00Z"


def test_records_without_id_are_skipped(tmp_path):
    store = RawStore(tmp_path)
    n = fetch_to_raw(
        _FakeConnector([{"x": 1}, {"id": "p2", "x": 2}]), store, "2026-01-01T00:00:00Z"
    )
    assert n == 1
    assert store.source_ids("otx") == ["p2"]


def test_custom_source_id_fn(tmp_path):
    store = RawStore(tmp_path)
    conn = _FakeConnector([{"domain": "evil.com", "k": "v"}])
    conn.source_name = "vt"
    n = fetch_to_raw(conn, store, "2026-01-01T00:00:00Z", source_id_fn=lambda r: r["domain"])
    assert n == 1
    assert store.latest("vt", "evil.com") == {"domain": "evil.com", "k": "v"}


def test_latest_fetched_at_none_when_empty(tmp_path):
    store = RawStore(tmp_path)
    assert store.latest_fetched_at("otx") is None


def test_read_domains_from_index_filters_dedups_sorts(tmp_path):
    idx = tmp_path / "indicator_index.jsonl"
    rows = [
        {"value": "b.com", "canonical_type": "domain"},
        {"value": "a.com", "canonical_type": "domain"},
        {"value": "1.2.3.4", "canonical_type": "ipv4"},
        {"value": "host.x", "canonical_type": None},
        {"value": "a.com", "canonical_type": "domain"},
    ]
    idx.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert read_domains_from_index(idx) == ["a.com", "b.com"]
    assert read_domains_from_index(idx, canonical_type="ipv4") == ["1.2.3.4"]


def test_read_domains_from_missing_index_is_empty(tmp_path):
    assert read_domains_from_index(tmp_path / "nope.jsonl") == []
