from __future__ import annotations

import json

from scripts.extract_attributed_event_metadata import (
    _date_value,
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
        "references": ["hxxps://citation[.]example/source#fragment"],
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
    assert metadata["reference_urls"] == ["https://citation.example/source"]
    assert metadata["publish_dates"] == ["2024-01-02T03:04:05Z"]
    assert provenance["fields"]["publish_dates"][0]["methods"] == [
        "normalized_source_timestamp"
    ]


def test_zero_date_sentinel_is_not_published_as_a_date() -> None:
    assert _date_value(0) is None
    assert _date_value("0") is None
    assert _date_value("0000-00-00T00:00:00Z") is None
    assert _date_value("2024-01-02T03:04:05Z") == "2024-01-02T03:04:05Z"


def test_array_form_structured_ids_are_extracted(tmp_path) -> None:
    raw_root = tmp_path / "data" / "raw"
    raw_path = raw_root / "circl_misp" / "raw" / "events" / "misp-1.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        json.dumps(
            {
                "Event": {
                    "uuid": "11111111-1111-4111-8111-111111111111",
                    "publish_timestamp": "0",
                    "external_report_ids": ["REP-123", "REP-456"],
                    "vendor_case_ids": ["CASE-789"],
                }
            }
        ),
        encoding="utf-8",
    )

    event = {
        "event_id": "event:circl_misp:misp-1",
        "source": "circl_misp",
        "source_record_id": "misp-1",
        "raw_ref": "data/raw/circl_misp/raw/events/misp-1.json",
    }
    metadata, provenance, errors = _extract_one(event, [], raw_root, 1)

    assert errors == []
    assert metadata["external_report_ids"] == ["REP-123", "REP-456"]
    assert metadata["vendor_case_report_ids"] == ["CASE-789"]
    assert metadata["publish_dates"] is None
    assert "Event.external_report_ids[0]" in provenance["fields"]["external_report_ids"][0]["paths"]
