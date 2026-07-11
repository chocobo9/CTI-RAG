from __future__ import annotations

import json
from pathlib import Path

from rag_cti.connectors.circl_misp_collection import CirclMispCollector, FeedEntry


def _event(uuid: str = "11111111-1111-4111-8111-111111111111") -> bytes:
    return json.dumps(
        {
            "Event": {
                "uuid": uuid,
                "info": "multi actor example",
                "date": "2024-01-02",
                "timestamp": "1704153600",
                "publish_timestamp": "1704240000",
                "published": True,
                "analysis": "2",
                "threat_level_id": "1",
                "Orgc": {"name": "CIRCL", "uuid": "org-1"},
                "Tag": [
                    {"name": 'misp-galaxy:threat-actor="Actor One"'},
                    {"name": 'misp-galaxy:threat-actor="Actor Two"'},
                    {"name": 'misp-galaxy:malware="Tool"'},
                ],
                "Attribute": [
                    {
                        "uuid": "a1",
                        "type": "domain",
                        "category": "Network activity",
                        "value": "example.test",
                        "to_ids": True,
                        "first_seen": "2024-01-01T00:00:00Z",
                        "Tag": [{"name": "tlp:white"}],
                    }
                ],
                "Object": [
                    {
                        "name": "file",
                        "Attribute": [
                            {"type": "sha256", "value": "a" * 64, "to_ids": False}
                        ],
                    }
                ],
                "unrecognized": {"must": "survive"},
            }
        },
        separators=(",", ":"),
    ).encode()


def test_store_and_rebuild_preserves_source_event(tmp_path: Path) -> None:
    collector = CirclMispCollector(tmp_path)
    entry = FeedEntry(
        filename="11111111-1111-4111-8111-111111111111.json",
        url="https://example.test/event.json",
        listing_last_modified="2024-01-03 00:00",
        listing_size="1K",
    )

    outcome = collector.store_response(entry, _event(), fetched_at="2024-01-04T00:00:00Z")
    collector.rebuild()

    raw = json.loads((tmp_path / outcome.raw_ref).read_text(encoding="utf-8"))
    assert raw["Event"]["unrecognized"] == {"must": "survive"}
    assert raw["Event"]["Object"][0]["Attribute"][0]["type"] == "sha256"

    event_row = json.loads((tmp_path / "normalized/events.jsonl").read_text())
    assert event_row["event_id"] == "circl-misp:event:11111111-1111-4111-8111-111111111111"
    assert event_row["raw_ref"] == outcome.raw_ref
    assert event_row["attribute_count"] == 2
    assert event_row["object_count"] == 1

    claims = [json.loads(line) for line in (tmp_path / "normalized/source_actor_claims.jsonl").read_text().splitlines()]
    assert [claim["raw_label"] for claim in claims] == ["Actor One", "Actor Two"]

    summary = json.loads((tmp_path / "normalized/event_observation_summaries.jsonl").read_text())
    assert summary["has_domain"] is True
    assert summary["has_hash"] is True
    assert summary["first_explicit_observation_time"] == "2024-01-01T00:00:00Z"


def test_rerun_is_idempotent_and_changed_content_is_versioned(tmp_path: Path) -> None:
    collector = CirclMispCollector(tmp_path)
    entry = FeedEntry("11111111-1111-4111-8111-111111111111.json", "https://example.test/e")
    first = collector.store_response(entry, _event(), fetched_at="2024-01-01T00:00:00Z")
    same = collector.store_response(entry, _event(), fetched_at="2024-01-02T00:00:00Z")
    changed_body = _event().replace(b"multi actor example", b"changed source title")
    changed = collector.store_response(entry, changed_body, fetched_at="2024-01-03T00:00:00Z")

    assert first.status == "created"
    assert same.status == "unchanged"
    assert same.raw_ref == first.raw_ref
    assert changed.status == "versioned"
    assert changed.raw_ref != first.raw_ref
    assert len(list((tmp_path / "raw/events").glob("*.json"))) == 2

    collector.rebuild()
    rows = (tmp_path / "normalized/events.jsonl").read_text().splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["title"] == "changed source title"


def test_malformed_record_is_preserved_and_does_not_block_valid_record(tmp_path: Path) -> None:
    collector = CirclMispCollector(tmp_path)
    bad_entry = FeedEntry("bad.json", "https://example.test/bad")
    bad = collector.store_response(bad_entry, b"{not-json", fetched_at="2024-01-01T00:00:00Z")
    good_entry = FeedEntry("11111111-1111-4111-8111-111111111111.json", "https://example.test/good")
    collector.store_response(good_entry, _event(), fetched_at="2024-01-01T00:00:01Z")

    assert bad.malformed is True
    assert (tmp_path / bad.raw_ref).read_bytes() == b"{not-json"
    assert "sha256:" in bad.event_id
    assert collector.rebuild()["events"] == 1
    errors = [json.loads(line) for line in (tmp_path / "manifests/errors.jsonl").read_text().splitlines()]
    assert errors[0]["error_kind"] == "malformed_json"


def test_checkpoint_with_non_ascii_error_is_utf8_readable(tmp_path: Path) -> None:
    collector = CirclMispCollector(tmp_path)
    checkpoint = {"entries": {"bad.json": {"status": "permanent_failure", "error": "拒绝访问"}}}
    path = tmp_path / "checkpoints/collection_state.json"
    path.write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")

    report = collector.report()

    assert report["permanent_failures"] == 1
    assert report["unresolved_collection_problems"] == ["拒绝访问"]


def test_resume_skips_checkpoint_entry_when_local_hash_matches(tmp_path: Path) -> None:
    class NoNetwork:
        def get(self, url: str, headers: dict[str, str] | None = None) -> object:
            raise AssertionError(f"resume unexpectedly requested {url}")

    entry = FeedEntry("11111111-1111-4111-8111-111111111111.json", "https://example.test/e")
    first = CirclMispCollector(tmp_path).store_response(entry, _event(), fetched_at="2024-01-01T00:00:00Z")
    checkpoint = {
        "entries": {
            entry.filename: {
                "status": "success",
                "raw_ref": first.raw_ref,
                "sha256": first.sha256,
            }
        }
    }
    (tmp_path / "checkpoints/collection_state.json").write_text(json.dumps(checkpoint), encoding="utf-8")

    result = CirclMispCollector(tmp_path, transport=NoNetwork()).collect(entries=[entry])  # type: ignore[arg-type]

    assert result["entries"][entry.filename]["status"] == "success"
