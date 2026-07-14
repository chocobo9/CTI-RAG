from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from rag_cti.intermediate.otx_source_claims import build_otx_source_claim_artifacts


def _pulse(pulse_id: str, adversary: Any = "") -> dict[str, Any]:
    return {
        "id": pulse_id,
        "name": f"Pulse {pulse_id}",
        "description": "Local fixture",
        "adversary": adversary,
    }


def _write_taxonomy(path: Path, actors: list[dict[str, Any]]) -> Path:
    path.write_text(json.dumps({"type": "bundle", "objects": actors}), encoding="utf-8")
    return path


def _actor(name: str, attack_id: str, aliases: list[str]) -> dict[str, Any]:
    return {
        "type": "intrusion-set",
        "id": f"intrusion-set--{attack_id.lower()}",
        "name": name,
        "aliases": aliases,
        "external_references": [{"source_name": "mitre-attack", "external_id": attack_id}],
    }


def test_builder_retains_event_when_source_actor_claim_is_missing(tmp_path: Path) -> None:
    taxonomy = _write_taxonomy(tmp_path / "enterprise-attack.json", [])

    artifacts = build_otx_source_claim_artifacts([_pulse("missing")], taxonomy)

    assert [row["source_record_id"] for row in artifacts.event_rows] == ["missing"]
    assert artifacts.event_rows[0]["actor_label_status"] == "missing"
    assert artifacts.claim_rows == []
    assert artifacts.summary == {"event_count": 1, "claim_count": 0, "status_counts": {"missing": 1}}


def test_builder_preserves_every_source_claim_resolution_state(tmp_path: Path) -> None:
    taxonomy = _write_taxonomy(
        tmp_path / "enterprise-attack.json",
        [
            _actor("APT32", "G0050", ["OceanLotus", "Shared Alias"]),
            _actor("APT28", "G0007", ["Fancy Bear", "Shared Alias"]),
            _actor("APT29", "G0016", ["Cozy Bear"]),
        ],
    )
    pulses = [
        _pulse("single", "APT32"),
        _pulse("collapsed", "APT32, OceanLotus"),
        _pulse("multi", "APT28 and APT29"),
        _pulse("taxonomy-ambiguous", "Shared Alias"),
        _pulse("parse-ambiguous", "APT 28/29 - campaign"),
        _pulse("non-attributing", "Malware Advisory"),
        _pulse("unmapped", "BlindEagle"),
    ]
    provenance = {pulse["id"]: {"raw_path": f"fixtures/{pulse['id']}.json", "sha256": pulse["id"]} for pulse in pulses}

    artifacts = build_otx_source_claim_artifacts(
        pulses,
        taxonomy,
        raw_provenance_by_pulse_id=provenance,
    )

    events = {row["source_record_id"]: row for row in artifacts.event_rows}
    assert {pulse_id: row["actor_label_status"] for pulse_id, row in events.items()} == {
        "single": "resolved_single",
        "collapsed": "resolved_alias_collapsed",
        "multi": "resolved_multi_actor",
        "taxonomy-ambiguous": "ambiguous_taxonomy",
        "parse-ambiguous": "parse_ambiguous",
        "non-attributing": "non_attributing",
        "unmapped": "unmapped_actor_like",
    }
    assert events["collapsed"]["resolved_actor_ids"] == ["actor_G0050"]
    assert events["multi"]["resolved_actor_ids"] == ["actor_G0007", "actor_G0016"]

    claims = {(row["source_record_id"], row["raw_label"]): row for row in artifacts.claim_rows}
    assert claims[("taxonomy-ambiguous", "Shared Alias")]["candidate_actor_ids"] == [
        "actor_G0007",
        "actor_G0050",
    ]
    assert claims[("parse-ambiguous", "APT 28/29 - campaign")]["parse_status"] == "parse_ambiguous"
    assert claims[("non-attributing", "Malware Advisory")]["resolution_status"] == "non_actor_value"
    assert claims[("unmapped", "BlindEagle")]["resolution_status"] == "unmapped_actor_like"
    assert all(row["source_field"] == "adversary" for row in artifacts.claim_rows)
    assert all(row["raw_field_value"] for row in artifacts.claim_rows)
    assert claims[("single", "APT32")]["raw_provenance"] == provenance["single"]


def test_cli_writes_offline_jsonl_artifacts(tmp_path: Path) -> None:
    pulses_path = tmp_path / "pulses.jsonl"
    pulses_path.write_text(
        "\n".join(json.dumps(row) for row in [_pulse("one", "APT32"), _pulse("two")]) + "\n",
        encoding="utf-8",
    )
    taxonomy = _write_taxonomy(
        tmp_path / "enterprise-attack.json",
        [_actor("APT32", "G0050", ["OceanLotus"])],
    )
    output_dir = tmp_path / "artifacts"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_otx_source_claims.py",
            "--pulses",
            str(pulses_path),
            "--mitre-taxonomy",
            str(taxonomy),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    events = [json.loads(line) for line in (output_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    claims = [json.loads(line) for line in (output_dir / "source_attribution_claims.jsonl").read_text(encoding="utf-8").splitlines()]
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert [row["source_record_id"] for row in events] == ["one", "two"]
    assert [row["source_record_id"] for row in claims] == ["one"]
    assert summary["status_counts"] == {"missing": 1, "resolved_single": 1}


def test_cli_streams_only_completed_pulses_from_collection_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    raw_dir = tmp_path / "raw" / "otx"
    run_dir.mkdir()
    saved_rows = []
    for pulse in [
        _pulse("single", "APT32"),
        _pulse("multi", "APT32, APT28"),
        _pulse("ignored", "APT28"),
    ]:
        path = raw_dir / pulse["id"] / "20260701.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "source": "otx",
                    "source_id": pulse["id"],
                    "fetched_at": "2026-07-01T00:00:00+00:00",
                    "payload": pulse,
                }
            ),
            encoding="utf-8",
        )
        saved_rows.append(
            {
                "kind": "pulse_detail",
                "pulse_id": pulse["id"],
                "raw_ref": {"path": str(path)},
            }
        )
    (run_dir / "checkpoint.json").write_text(
        json.dumps({"completed_pulse_details": ["single", "multi"]}),
        encoding="utf-8",
    )
    (run_dir / "saved_files.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in saved_rows),
        encoding="utf-8",
    )
    taxonomy = _write_taxonomy(
        tmp_path / "enterprise-attack.json",
        [
            _actor("APT32", "G0050", ["OceanLotus"]),
            _actor("APT28", "G0007", ["Fancy Bear"]),
        ],
    )
    output_dir = tmp_path / "artifacts"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_otx_source_claims.py",
            "--run-dir",
            str(run_dir),
            "--mitre-taxonomy",
            str(taxonomy),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    events = [
        json.loads(line)
        for line in (output_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    claims = [
        json.loads(line)
        for line in (output_dir / "source_attribution_claims.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert [row["source_record_id"] for row in events] == ["multi", "single"]
    assert {row["source_record_id"] for row in claims} == {"multi", "single"}
    assert summary["event_count"] == 2
    assert summary["status_counts"] == {
        "resolved_multi_actor": 1,
        "resolved_single": 1,
    }
    assert summary["input_mode"] == "collection_run"
    assert summary["completed_pulse_count"] == 2
