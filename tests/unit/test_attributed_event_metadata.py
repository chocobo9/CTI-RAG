from __future__ import annotations

import json

from scripts.extract_attributed_event_metadata import (
    _extract_one,
    _load_orkl_normalized_index,
)


def test_orkl_metadata_uses_normalized_publication_timestamp_and_source_id(tmp_path) -> None:
    raw_root = tmp_path / "data" / "raw"
    raw_path = raw_root / "orkl" / "raw" / "reports" / "report-1" / "snapshot.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        json.dumps(
            {
                "id": "report-1",
                "plain_text": "A report body with no network indicator.",
                "title": "Example report",
            }
        ),
        encoding="utf-8",
    )
    normalized_path = raw_root / "orkl" / "normalized" / "reports.jsonl"
    normalized_path.parent.mkdir(parents=True)
    normalized_path.write_text(
        json.dumps(
            {
                "report_id": "orkl:report:report-1",
                "source_record_id": "report-1",
                "published_at": "2024-01-02T03:04:05Z",
                "modified_at": "2026-01-01T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    normalized = _load_orkl_normalized_index(raw_root)
    event = {
        "event_id": "event:orkl:report-1",
        "source": "orkl",
        "source_record_id": "report-1",
        "raw_ref": "data/raw/orkl/raw/reports/report-1/snapshot.json",
        "title": "Example report",
    }

    metadata, provenance, errors = _extract_one(
        event,
        [],
        raw_root,
        1,
        normalized.get("report-1"),
    )

    assert errors == []
    assert metadata["external_report_ids"] == ["report-1"]
    assert metadata["publish_dates"] == ["2024-01-02T03:04:05Z"]
    assert provenance["fields"]["publish_dates"][0]["methods"] == [
        "normalized_source_timestamp"
    ]
