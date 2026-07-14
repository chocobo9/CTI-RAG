from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from rag_cti.intermediate.otx_temporal_profile import build_otx_temporal_profile


def test_profile_reports_event_and_indicator_occurrence_coverage() -> None:
    rows = [
        (
            {
                "id": "one",
                "created": "2020-01-01T00:00:00Z",
                "modified": "2020-02-01T00:00:00Z",
                "indicators": [
                    {"created": "2019-01-01T00:00:00Z", "expiration": "2021-01-01T00:00:00Z"},
                    {},
                ],
            },
            "2026-07-01T00:00:00Z",
        ),
        ({"id": "two", "indicators": [{"created": "2018-01-01T00:00:00Z"}]}, None),
    ]

    profile = build_otx_temporal_profile(rows, since=None, until=None)

    assert profile["event_count"] == 2
    assert profile["indicator_occurrence_count"] == 3
    assert profile["time_filter"] == {"since": None, "until": None, "status": "unfiltered"}
    assert profile["fields"]["pulse.created"] == {
        "present": 1,
        "missing": 1,
        "min": "2020-01-01T00:00:00Z",
        "max": "2020-01-01T00:00:00Z",
    }
    assert profile["fields"]["raw.fetched_at"]["missing"] == 1
    assert profile["fields"]["indicator.created"] == {
        "event_coverage": {"present": 2, "missing": 0},
        "occurrence_value_coverage": {"present": 2, "missing": 1},
        "min": "2018-01-01T00:00:00Z",
        "max": "2019-01-01T00:00:00Z",
    }
    assert profile["fields"]["indicator.expiration"]["event_coverage"] == {
        "present": 1,
        "missing": 1,
    }
    assert "selection_window" not in profile
    assert "activity" not in str(profile).lower()


def test_cli_profiles_only_run_scoped_completed_pulse_details(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    saved = []
    for pulse_id, created in (("included", "2020-01-01Z"), ("ignored", "1999-01-01Z")):
        raw_path = tmp_path / "raw" / f"{pulse_id}.json"
        raw_path.parent.mkdir(exist_ok=True)
        raw_path.write_text(
            json.dumps(
                {
                    "source": "otx",
                    "source_id": pulse_id,
                    "fetched_at": "2026-07-01T00:00:00Z",
                    "payload": {"id": pulse_id, "created": created, "indicators": []},
                }
            ),
            encoding="utf-8",
        )
        saved.append({"kind": "pulse_detail", "pulse_id": pulse_id, "raw_ref": {"path": str(raw_path)}})
    (run_dir / "checkpoint.json").write_text(
        json.dumps({"completed_pulse_details": ["included"]}), encoding="utf-8"
    )
    (run_dir / "saved_files.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in saved), encoding="utf-8"
    )
    (run_dir / "collection_manifest.json").write_text(
        json.dumps({"params": {"since": "2015-01-01", "until": None}}), encoding="utf-8"
    )
    output_dir = tmp_path / "output"
    env = {**os.environ, "PYTHONPATH": "src"}

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_otx_temporal_profile.py",
            "--run-dir",
            str(run_dir),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    profile = json.loads((output_dir / "dataset_temporal_profile.json").read_text(encoding="utf-8"))
    assert profile["event_count"] == 1
    assert profile["time_filter"] == {"since": "2015-01-01", "until": None, "status": "filtered"}
    assert profile["fields"]["pulse.created"]["min"] == "2020-01-01Z"


def test_cli_supports_a_small_local_jsonl_fixture(tmp_path: Path) -> None:
    pulses = tmp_path / "pulses.jsonl"
    pulses.write_text(
        json.dumps({"id": "fixture", "modified": "2024-03-01Z", "indicators": []}) + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_otx_temporal_profile.py",
            "--pulses",
            str(pulses),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )

    assert completed.returncode == 0, completed.stderr
    profile = json.loads((output_dir / "dataset_temporal_profile.json").read_text(encoding="utf-8"))
    assert profile["event_count"] == 1
    assert profile["time_filter"]["status"] == "unfiltered"
    assert profile["fields"]["pulse.modified"]["max"] == "2024-03-01Z"


def test_run_dir_prefers_existing_cwd_relative_raw_path(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    cwd_raw = tmp_path / "data" / "raw.json"
    cwd_raw.parent.mkdir()
    cwd_raw.write_text(
        json.dumps(
            {
                "source_id": "pulse-1",
                "fetched_at": "2026-07-01Z",
                "payload": {"id": "pulse-1", "created": "2020-01-01Z"},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "checkpoint.json").write_text(
        json.dumps({"completed_pulse_details": ["pulse-1"]}), encoding="utf-8"
    )
    (run_dir / "saved_files.jsonl").write_text(
        json.dumps(
            {"kind": "pulse_detail", "pulse_id": "pulse-1", "raw_ref": {"path": "data/raw.json"}}
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "collection_manifest.json").write_text(json.dumps({"params": {}}), encoding="utf-8")
    output_dir = tmp_path / "output"
    repository = Path(__file__).resolve().parents[2]

    completed = subprocess.run(
        [
            sys.executable,
            str(repository / "scripts" / "build_otx_temporal_profile.py"),
            "--run-dir",
            str(run_dir),
            "--output-dir",
            str(output_dir),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(repository / "src")},
    )

    assert completed.returncode == 0, completed.stderr
    profile = json.loads((output_dir / "dataset_temporal_profile.json").read_text(encoding="utf-8"))
    assert profile["fields"]["pulse.created"]["min"] == "2020-01-01Z"


def test_run_dir_falls_back_to_run_relative_raw_path(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    raw_path = run_dir / "raw" / "pulse.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        json.dumps({"source_id": "p", "payload": {"id": "p", "modified": "2021-01-01Z"}}),
        encoding="utf-8",
    )
    (run_dir / "checkpoint.json").write_text(
        json.dumps({"completed_pulse_details": ["p"]}), encoding="utf-8"
    )
    (run_dir / "saved_files.jsonl").write_text(
        json.dumps({"kind": "pulse_detail", "pulse_id": "p", "raw_ref": {"path": "raw/pulse.json"}})
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "collection_manifest.json").write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "output"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_otx_temporal_profile.py",
            "--run-dir",
            str(run_dir),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )

    assert completed.returncode == 0, completed.stderr
    profile = json.loads((output_dir / "dataset_temporal_profile.json").read_text(encoding="utf-8"))
    assert profile["fields"]["pulse.modified"]["max"] == "2021-01-01Z"


def test_run_dir_reports_both_attempted_locations_when_raw_path_is_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "checkpoint.json").write_text(
        json.dumps({"completed_pulse_details": ["p"]}), encoding="utf-8"
    )
    (run_dir / "saved_files.jsonl").write_text(
        json.dumps({"kind": "pulse_detail", "pulse_id": "p", "raw_ref": {"path": "missing.json"}})
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "collection_manifest.json").write_text("{}", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_otx_temporal_profile.py",
            "--run-dir",
            str(run_dir),
            "--output-dir",
            str(tmp_path / "output"),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )

    assert completed.returncode != 0
    assert "Pulse detail raw path does not exist: missing.json (also tried" in completed.stderr
    assert str(run_dir / "missing.json") in completed.stderr
