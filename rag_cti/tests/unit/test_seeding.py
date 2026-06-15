from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from rag_cti.connectors.base import BaseConnector
from rag_cti.preprocess.chunking import ChunkStrategy
from rag_cti.preprocess.seeding import seed_connector_to_jsonl, seed_connector_with_projection
from rag_cti.types import Document


class _ListConnector(BaseConnector):
    source_name = "whois"

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    def fetch(self, **_: Any) -> Iterator[dict[str, Any]]:
        yield from self._records

    def to_document(self, raw: dict[str, Any]) -> Document:
        if not raw.get("id"):
            raise ValueError("missing id")
        return Document(
            id=raw["id"],
            source=self.source_name,
            content=raw.get("content", ""),
            metadata={"domain": raw.get("domain", "")},
        )


def _records(n: int) -> list[dict[str, Any]]:
    return [
        {
            "id": f"r{i}",
            "content": f"Domain d{i}.example is registered with R.",
            "domain": f"d{i}.example",
        }
        for i in range(n)
    ]


def test_writes_one_jsonl_line_per_chunk(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    stats = seed_connector_to_jsonl(_ListConnector(_records(3)), out, ChunkStrategy.STRUCTURED)
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert stats.documents == 3
    assert stats.chunks == len(lines)
    assert all(line["source"] == "whois" for line in lines)


def test_with_projection_merges_projection_into_chunk_metadata(tmp_path: Path) -> None:
    """M2.6 wiring: projector(raw) output is merged into each chunk's metadata,
    alongside the connector's own metadata."""
    out = tmp_path / "out.jsonl"

    def projector(raw: dict[str, Any]) -> dict[str, Any]:
        return {"source_type": "whois", "attack_ids": [], "entity_ids": [f"indicator_{raw['id']}"]}

    seed_connector_with_projection(
        _ListConnector(_records(2)), projector, out, ChunkStrategy.STRUCTURED
    )
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert lines, "expected at least one chunk"
    md = lines[0]["metadata"]
    assert md["source_type"] == "whois"
    assert md["entity_ids"] == ["indicator_r0"]
    assert md["domain"] == "d0.example"  # connector metadata preserved


def test_with_projection_failure_falls_back_to_no_projection(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"

    def boom(_: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("projector blew up")

    stats = seed_connector_with_projection(
        _ListConnector(_records(1)), boom, out, ChunkStrategy.STRUCTURED
    )
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert lines  # chunk still written despite the projector failure
    assert stats.chunks == len(lines)
    assert "source_type" not in lines[0]["metadata"]  # no projection, but no crash


def test_jsonl_record_has_canonical_keys(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    seed_connector_to_jsonl(_ListConnector(_records(1)), out, ChunkStrategy.STRUCTURED)
    record = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert set(record) == {
        "id",
        "parent_doc_id",
        "source",
        "content",
        "chunk_index",
        "metadata",
        "retrieved_at",
    }


def test_empty_content_documents_are_counted_as_skipped(tmp_path: Path) -> None:
    records = _records(2) + [{"id": "bad", "content": "   ", "domain": "x"}]
    out = tmp_path / "out.jsonl"
    stats = seed_connector_to_jsonl(_ListConnector(records), out, ChunkStrategy.STRUCTURED)
    assert stats.documents == 2
    assert stats.skipped == 1


def test_limit_caps_documents(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    stats = seed_connector_to_jsonl(
        _ListConnector(_records(5)), out, ChunkStrategy.STRUCTURED, limit=2
    )
    assert stats.documents == 2


def test_stats_summary_mentions_skips(tmp_path: Path) -> None:
    records = [{"id": "bad", "content": "", "domain": "x"}] + _records(1)
    out = tmp_path / "out.jsonl"
    stats = seed_connector_to_jsonl(_ListConnector(records), out, ChunkStrategy.STRUCTURED)
    summary = stats.summary(out)
    assert "1 documents skipped" in summary


def test_chunk_to_jsonl_dict_roundtrips_via_json(tmp_path: Path) -> None:
    out = tmp_path / "out.jsonl"
    seed_connector_to_jsonl(_ListConnector(_records(1)), out, ChunkStrategy.STRUCTURED)
    record = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    # retrieved_at must be ISO-parseable for ingest.py
    from datetime import datetime

    datetime.fromisoformat(record["retrieved_at"])


def test_malformed_connector_records_counted_on_connector(tmp_path: Path) -> None:
    records = [{"content": "no id"}] + _records(1)
    connector = _ListConnector(records)
    out = tmp_path / "out.jsonl"
    stats = seed_connector_to_jsonl(connector, out, ChunkStrategy.STRUCTURED)
    assert connector.skipped_records == 1
    assert stats.documents == 1
