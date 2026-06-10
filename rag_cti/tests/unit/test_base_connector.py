from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from rag_cti.connectors.base import BaseConnector
from rag_cti.types import Document


class _MixedConnector(BaseConnector):
    source_name = "test"

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    def fetch(self, **_: Any) -> Iterator[dict[str, Any]]:
        yield from self._records

    def to_document(self, raw: dict[str, Any]) -> Document:
        if raw.get("bad"):
            raise ValueError("malformed")
        return Document(id=raw["id"], source=self.source_name, content="x")


def test_fetch_documents_counts_skipped_records() -> None:
    connector = _MixedConnector([
        {"id": "a"}, {"bad": True}, {"id": "b"}, {"bad": True},
    ])
    docs = list(connector.fetch_documents())
    assert [d.id for d in docs] == ["a", "b"]
    assert connector.skipped_records == 2


def test_skipped_counter_resets_per_call() -> None:
    connector = _MixedConnector([{"bad": True}, {"id": "a"}])
    list(connector.fetch_documents())
    assert connector.skipped_records == 1
    connector._records = [{"id": "b"}]
    list(connector.fetch_documents())
    assert connector.skipped_records == 0
