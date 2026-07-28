from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from build_evitrail_complete_handoff import build_package


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_build_package_preserves_all_events_claims_and_separates_otx(
    tmp_path: Path,
) -> None:
    processed = tmp_path / "data" / "processed" / "part1"
    raw = tmp_path / "data" / "raw"
    _write_json(processed / "validation_report.json", {"status": "pass"})
    for source in ("misp", "orkl", "aptnotes", "cisa"):
        record_id = f"{source}:record:1"
        _write_jsonl(
            processed / "normalized" / source / "records.jsonl",
            [
                {
                    "source_record_id": record_id,
                    "title": f"{source} report",
                    "event_timestamp": "2026-01-02T03:04:05Z",
                    "raw_ref": f"raw/{record_id}.json",
                    "in_target_window": True,
                }
            ],
        )
        _write_jsonl(
            processed / "normalized" / source / "ioc_evidence.jsonl",
            [
                {
                    "source_record_id": record_id,
                    "ioc_type": "Domain",
                    "ioc_value": f"{source}.example",
                    "ioc_value_raw": f"{source}.example",
                    "source_field": "body[0]",
                    "raw_ref": f"raw/{record_id}.json",
                }
            ],
        )
        claim = {
            "source_record_id": record_id,
            "raw_label": "Example Group",
            "normalized_alias_key": "examplegroup",
            "resolution_status": "resolved",
            "canonical_name": "Example Group",
            "source_location": "actor[0]",
            "raw_ref": f"raw/{record_id}.json",
        }
        _write_jsonl(
            processed / "actor_resolution" / f"{source}.jsonl",
            [claim, claim] if source == "misp" else [claim],
        )

    mitre = raw / "mitre" / "enterprise-attack.json"
    _write_json(
        mitre,
        {
            "objects": [
                {
                    "type": "intrusion-set",
                    "id": "intrusion-set--1",
                    "name": "Example Group",
                    "aliases": ["Example Alias"],
                    "external_references": [
                        {
                            "source_name": "mitre-attack",
                            "external_id": "G9999",
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        raw / "otx" / "pulse-1" / "2026-01-01.json",
        {
            "source": "otx",
            "source_id": "pulse-1",
            "fetched_at": "2026-01-01T00:00:00Z",
            "payload": {
                "id": "pulse-1",
                "name": "OTX example",
                "adversary": "Example Alias",
                "indicators": [
                    {"type": "domain", "indicator": "otx.example"}
                ],
            },
        },
    )
    vocabulary = tmp_path / "vocabulary.json"
    _write_json(vocabulary, {"actors": ["Example Alias"]})

    output = tmp_path / "out"
    manifest = build_package(
        processed_root=processed,
        raw_root=raw,
        otx_root=raw / "otx",
        mitre_path=mitre,
        output_dir=output,
        initial_vocabulary_path=vocabulary,
    )

    assert manifest["counts"]["handoff_events"] == 4
    assert manifest["counts"]["otx_events"] == 1
    assert manifest["counts"]["handoff_source_claims"] == 4
    assert manifest["counts"]["all_source_claims"] == 5
    assert manifest["counts"]["training_labels"] == 3
    assert {
        row["source"] for row in _rows(output / "handoff" / "events.jsonl")
    } == {"circl_misp", "orkl", "aptnotes", "cisa"}
    assert {
        row["source"]
        for row in _rows(output / "labels" / "all_source_claims.jsonl")
    } == {"circl_misp", "orkl", "aptnotes", "cisa", "otx"}
    assert {
        row["source"]
        for row in _rows(output / "labels" / "training_labels.jsonl")
    } == {"circl_misp", "aptnotes", "otx"}
    assert all(
        row["usage"] == "provenance_only"
        for row in _rows(output / "handoff" / "source_claims.jsonl")
        if row["source"] in {"orkl", "cisa"}
    )
    assert manifest["forbidden_artifacts"] == {
        "checkpoints": False,
        "weights": False,
        "predictions": False,
        "training_results": False,
    }


def test_mitre_preferred_names_collapse_legacy_aliases(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed" / "part1"
    raw = tmp_path / "data" / "raw"
    _write_json(processed / "validation_report.json", {"status": "pass"})
    for source in ("misp", "orkl", "aptnotes", "cisa"):
        _write_jsonl(processed / "normalized" / source / "records.jsonl", [])
        _write_jsonl(
            processed / "normalized" / source / "ioc_evidence.jsonl", []
        )
        _write_jsonl(processed / "actor_resolution" / f"{source}.jsonl", [])
    mitre = raw / "mitre" / "enterprise-attack.json"
    _write_json(
        mitre,
        {
            "objects": [
                {
                    "type": "intrusion-set",
                    "id": "intrusion-set--gamaredon",
                    "name": "Gamaredon Group",
                    "aliases": ["Gamaredon"],
                    "external_references": [
                        {
                            "source_name": "mitre-attack",
                            "external_id": "G0047",
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        raw / "otx" / "pulse-1" / "2026-01-01.json",
        {
            "payload": {
                "id": "pulse-1",
                "adversary": "Gamaredon",
                "indicators": [],
            }
        },
    )
    vocabulary = tmp_path / "vocabulary.json"
    _write_json(vocabulary, ["Gamaredon"])

    manifest = build_package(
        processed_root=processed,
        raw_root=raw,
        otx_root=raw / "otx",
        mitre_path=mitre,
        output_dir=tmp_path / "out",
        initial_vocabulary_path=vocabulary,
    )

    review = json.loads(
        (tmp_path / "out" / "labels" / "vocabulary_review.json").read_text(
            encoding="utf-8"
        )
    )
    assert review["initial_actors"] == ["Gamaredon Group"]
    assert "Gamaredon" not in review["approved_actors"]
    assert manifest["counts"]["training_labels"] == 1
