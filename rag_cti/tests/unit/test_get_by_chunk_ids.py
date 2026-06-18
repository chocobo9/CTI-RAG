"""Unit tests for QdrantStore.get_by_chunk_ids (M4 evidence fetch)."""

from __future__ import annotations

from typing import Any

from rag_cti.store.qdrant_store import QdrantStore, chunk_to_point_id


class _FakeRecord:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload


class _FakeClient:
    def __init__(self, records: list[_FakeRecord]) -> None:
        self._records = records
        self.last_ids: list[str] | None = None

    def retrieve(
        self, collection_name: str, ids: list[str], with_payload: bool
    ) -> list[_FakeRecord]:
        self.last_ids = ids
        return self._records


def _store(records: list[_FakeRecord]) -> QdrantStore:
    store = object.__new__(QdrantStore)
    store.collection = "c"
    store.max_content_len = 8000
    store._client = _FakeClient(records)  # type: ignore[assignment]  # noqa: SLF001
    return store


def test_get_by_chunk_ids_maps_point_ids_and_returns_chunks() -> None:
    payload = {
        "id": "e1",
        "parent_doc_id": "doc",
        "source": "mitre",
        "content": "phishing body",
        "chunk_index": 0,
        "metadata": {},
    }
    store = _store([_FakeRecord(payload)])
    out = store.get_by_chunk_ids(["e1"])
    assert set(out) == {"e1"}
    assert out["e1"].content == "phishing body"
    # retrieved by the uuid5 point id, not the raw chunk id
    assert store._client.last_ids == [chunk_to_point_id("e1")]  # type: ignore[attr-defined]  # noqa: SLF001


def test_get_by_chunk_ids_empty_returns_empty() -> None:
    assert _store([]).get_by_chunk_ids([]) == {}
