from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from rag_cti.intermediate.otx_indicator_summary import summarize_otx_pulse_indicators


def test_summary_preserves_source_and_explicit_activity_time_semantics() -> None:
    pulse = {
        "id": "pulse-1",
        "indicators": [
            {
                "type": "domain",
                "created": "2024-01-02T00:00:00Z",
                "expiration": "2024-03-01T00:00:00Z",
                "is_active": True,
                "first_seen": "2024-01-10T00:00:00Z",
                "last_seen": "2024-02-10T00:00:00Z",
            },
            {
                "type": "IPv4",
                "created": "2023-12-01T00:00:00Z",
                "expiration": "2024-04-01T00:00:00Z",
                "is_active": False,
            },
            {"type": "domain", "is_active": None},
        ],
    }

    row = summarize_otx_pulse_indicators(pulse, raw_record_bytes=321)

    assert row == {
        "event_id": "otx:pulse:pulse-1",
        "source_record_id": "pulse-1",
        "indicator_count": 3,
        "type_counts": {"IPv4": 1, "domain": 2},
        "source_created_min": "2023-12-01T00:00:00Z",
        "source_created_max": "2024-01-02T00:00:00Z",
        "source_expiration_min": "2024-03-01T00:00:00Z",
        "source_expiration_max": "2024-04-01T00:00:00Z",
        "active_true_count": 1,
        "active_false_count": 1,
        "active_unknown_count": 1,
        "explicit_activity_start_min": "2024-01-10T00:00:00Z",
        "explicit_activity_start_max": "2024-01-10T00:00:00Z",
        "explicit_activity_start_count": 1,
        "explicit_activity_end_min": "2024-02-10T00:00:00Z",
        "explicit_activity_end_max": "2024-02-10T00:00:00Z",
        "explicit_activity_end_count": 1,
        "raw_record_bytes": 321,
        "materialization_status": "summary_only",
    }
    assert "first_seen" not in row
    assert "last_seen" not in row


def test_cli_streams_local_jsonl_and_keeps_dataset_window_only_in_manifest(tmp_path: Path) -> None:
    pulses_path = tmp_path / "pulses.jsonl"
    pulses_path.write_text(
        json.dumps({"id": "empty", "indicators": []}) + "\n"
        + json.dumps({"id": "one", "indicators": [{"type": "URL", "created": "2025-01-01Z"}]}) + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_otx_indicator_summaries.py",
            "--pulses",
            str(pulses_path),
            "--output-dir",
            str(output_dir),
            "--coverage-start",
            "2023-01-01",
            "--coverage-end",
            "2026-12-31",
            "--selection-field",
            "pulse.created",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    rows = [json.loads(line) for line in (output_dir / "event_indicator_summaries.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((output_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    assert [row["materialization_status"] for row in rows] == ["none", "summary_only"]
    assert all("coverage_start" not in row and "coverage_end" not in row for row in rows)
    assert manifest == {
        "coverage_basis": "explicit_cli",
        "coverage_start": "2023-01-01",
        "coverage_end": "2026-12-31",
        "coverage_status": "bounded",
        "event_count": 2,
        "input_mode": "local_pulses",
        "selection_field": "pulse.created",
    }


def test_cli_streams_only_completed_pulse_details_from_collection_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    saved_rows = []
    for pulse_id in ("included", "ignored"):
        raw_path = tmp_path / "raw" / pulse_id / "detail.json"
        raw_path.parent.mkdir(parents=True)
        raw_path.write_text(
            json.dumps(
                {
                    "source": "otx",
                    "source_id": pulse_id,
                    "payload": {"id": pulse_id, "indicators": [{"type": "domain"}]},
                }
            ),
            encoding="utf-8",
        )
        saved_rows.append({"kind": "pulse_detail", "pulse_id": pulse_id, "raw_ref": {"path": str(raw_path)}})
    (run_dir / "checkpoint.json").write_text(
        json.dumps({"completed_pulse_details": ["included"]}), encoding="utf-8"
    )
    (run_dir / "saved_files.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in saved_rows), encoding="utf-8"
    )
    output_dir = tmp_path / "output"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_otx_indicator_summaries.py",
            "--run-dir",
            str(run_dir),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    rows = [json.loads(line) for line in (output_dir / "event_indicator_summaries.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((output_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    assert [row["source_record_id"] for row in rows] == ["included"]
    assert rows[0]["raw_record_bytes"] > 0
    assert manifest["input_mode"] == "collection_run"
    assert manifest["event_count"] == 1
    assert manifest["coverage_status"] == "unbounded"
