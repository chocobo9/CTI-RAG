from __future__ import annotations

import json
from pathlib import Path

from rag_cti.connectors.malpedia_collection import MalpediaCollector


def test_rebuild_preserves_aliases_links_and_references(tmp_path: Path) -> None:
    collector = MalpediaCollector(tmp_path)
    collector.store_payload(
        "version",
        b'{"version":123,"date":"2025-01-01T00:00:00Z"}',
        fetched_at="2025-01-02T00:00:00Z",
    )
    collector.store_payload("actor_inventory", b'["actor_one"]')
    collector.store_payload("family_inventory", b'["win.tool"]')
    collector.store_payload(
        "actors",
        json.dumps(
            {
                "Actor One": {
                    "value": "Actor One",
                    "uuid": "u1",
                    "description": "desc",
                    "meta": {"synonyms": ["Alias"], "refs": ["https://a.test"]},
                }
            }
        ).encode(),
    )
    collector.store_payload(
        "families",
        json.dumps(
            {
                "win.tool": {
                    "common_name": "Tool",
                    "alt_names": ["Other"],
                    "description": "family",
                    "platform": "Windows",
                    "attribution": ["Actor One"],
                    "urls": ["https://f.test"],
                }
            }
        ).encode(),
    )
    collector.store_payload(
        "references",
        json.dumps(
            {
                "references": {
                    "https://f.test": [{"type": "family", "id": "win.tool", "common_name": "Tool"}]
                },
                "malpedia_version": 123,
            }
        ).encode(),
    )

    result = collector.rebuild()
    assert result == {"actors": 1, "families": 1, "links": 1, "references": 2}
    actor = json.loads((tmp_path / "normalized/actors.jsonl").read_text())
    family = json.loads((tmp_path / "normalized/families.jsonl").read_text())
    assert actor["aliases_raw"] == ["Alias"]
    assert family["associated_actor_ids_raw"] == ["Actor One"]
    assert collector.validate()["valid"] is True


def test_changed_payload_is_versioned_and_latest_is_rebuilt(tmp_path: Path) -> None:
    collector = MalpediaCollector(tmp_path)
    first = collector.store_payload("actors", b'{"A":{"value":"A"}}')
    same = collector.store_payload("actors", b'{"A":{"value":"A"}}')
    changed = collector.store_payload("actors", b'{"A":{"value":"A","description":"new"}}')
    assert first["status"] == "created"
    assert same["status"] == "unchanged"
    assert changed["status"] == "versioned"
    collector.rebuild()
    assert json.loads((tmp_path / "normalized/actors.jsonl").read_text())["description"] == "new"
