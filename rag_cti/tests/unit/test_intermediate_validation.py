from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from rag_cti.intermediate.contract import contract_id
from rag_cti.intermediate.jsonl import write_jsonl
from rag_cti.intermediate.validation import validate_delivery


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _tiny_delivery(root: Path) -> dict[str, Any]:
    raw_rel = "raw/otx/pulse-1/2026-06-15T00-00-00Z.json"
    raw_path = root / raw_rel
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps({"source": "otx", "source_id": "pulse-1", "payload": {"id": "pulse-1"}}),
        encoding="utf-8",
    )
    raw_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    record_id = "record_otx_pulse-1_2026-06-15T00-00-00Z"
    actor_mention_id = contract_id("em", (record_id, "adversary", "actor", "Cleaver"))
    technique_mention_id = contract_id(
        "em", (record_id, "attack_ids[]", "technique", "T1016")
    )
    relation_id = contract_id(
        "rm", (record_id, actor_mention_id, "uses", technique_mention_id, "attack_ids[]")
    )
    signal_id = contract_id(
        "as", (record_id, "weak_direct_attribution", "actor", "Cleaver", "adversary")
    )

    intermediate = root / "intermediate"
    _write_json(
        intermediate / "source_manifest.json",
        {
            "dataset_id": "cti_rag_fixture",
            "dataset_version": "2026-06-28-fixture",
            "schema_version": "v0.1",
            "generated_at": "2026-06-28T00:00:00Z",
            "sources": [
                {
                    "connector_source": "otx",
                    "source_class": "weakly_labeled_narrative",
                    "publisher_category": "threat_intelligence_platform",
                    "record_count": 1,
                    "raw_collection": "raw/otx",
                    "provides": {"labels": True, "indicators": True, "timestamps": True},
                }
            ],
        },
    )
    intermediate_records = [
        {
            "record_id": record_id,
            "raw_ref": {
                "connector_source": "otx",
                "source_id": "pulse-1",
                "fetched_at": "2026-06-15T00:00:00Z",
                "raw_path": raw_rel,
                "raw_sha256": raw_sha,
            },
            "source": {
                "connector_source": "otx",
                "source_class": "weakly_labeled_narrative",
                "publisher_category": "threat_intelligence_platform",
                "source_name": "AlienVault OTX",
                "source_record_id": "pulse-1",
            },
            "timestamps": {
                "published_at": None,
                "modified_at": "2017-08-24T09:26:22.235000Z",
                "observed_first": None,
                "observed_last": None,
                "fetched_at": "2026-06-15T00:00:00Z",
                "timestamp_basis": "source_modified",
            },
            "record_signals": {
                "label_availability": "direct",
                "has_attribution_confidence": False,
                "ambiguity_flag": False,
            },
            "counts": {"entity_mentions": 2, "relation_mentions": 1, "indicators": 0},
            "processing_status": {"status": "ok", "warnings": []},
        }
    ]
    entity_mentions = [
        {
            "entity_mention_id": actor_mention_id,
            "record_id": record_id,
            "raw_value": "Cleaver",
            "normalized_value": "Cleaver",
            "entity_type": "actor",
            "source_field": "adversary",
            "extraction_method": "source_field",
            "occurrence_count": 1,
            "value_type": {"raw": None, "canonical": None},
            "resolution": {
                "entity_id": "actor_G0003",
                "canonical_name": "Cleaver",
                "ontology_id": "G0003",
                "resolution_method": "exact_alias",
            },
            "ambiguity": {"status": "resolved", "reason": None, "candidate_entity_ids": []},
            "merge_candidates": [],
        },
        {
            "entity_mention_id": technique_mention_id,
            "record_id": record_id,
            "raw_value": "T1016",
            "normalized_value": "T1016",
            "entity_type": "technique",
            "source_field": "attack_ids[]",
            "extraction_method": "source_field",
            "occurrence_count": 1,
            "value_type": {"raw": None, "canonical": None},
            "resolution": {
                "entity_id": "technique_T1016",
                "canonical_name": "System Network Configuration Discovery",
                "ontology_id": "T1016",
                "resolution_method": "exact_id",
            },
            "ambiguity": {"status": "resolved", "reason": None, "candidate_entity_ids": []},
            "merge_candidates": [],
        },
    ]
    relation_mentions = [
        {
            "relation_mention_id": relation_id,
            "record_id": record_id,
            "subject": {
                "raw_value": "Cleaver",
                "entity_mention_id": actor_mention_id,
                "entity_type": "actor",
            },
            "predicate": {
                "raw_value": "adversary+attack_ids co-occurrence",
                "mapped_value": "uses",
                "mapping_status": "mapped",
            },
            "object": {
                "raw_value": "T1016",
                "entity_mention_id": technique_mention_id,
                "entity_type": "technique",
            },
            "derivation": {
                "source_field": "adversary,attack_ids",
                "extraction_method": "structured_cooccurrence",
                "evidence_type": "ttp",
                "label_availability": "direct",
                "attribution_confidence": None,
            },
            "ambiguity": {"status": "unambiguous", "notes": []},
        }
    ]
    attribution_signals = [
        {
            "attribution_signal_id": signal_id,
            "record_id": record_id,
            "signal_type": "weak_direct_attribution",
            "target_entity_type": "actor",
            "raw_label": "Cleaver",
            "resolved_entity_id": "actor_G0003",
            "source_field": "adversary",
            "source_provided_confidence": None,
            "derivation_method": "source_field",
            "notes": [],
        }
    ]
    record_features = [
        {
            "record_id": record_id,
            "source_features": {
                "connector_source": "otx",
                "source_class": "weakly_labeled_narrative",
                "publisher_category": "threat_intelligence_platform",
            },
            "timestamp_features": {"has_modified_at": True, "timestamp_basis": "source_modified"},
            "content_features": {"indicator_count": 0},
            "label_features": {"label_availability": "direct", "has_confidence": False},
            "ambiguity_features": {
                "ambiguous_entity_mentions": 0,
                "ambiguous_relation_mentions": 0,
            },
        }
    ]

    write_jsonl(intermediate / "intermediate_records.jsonl", intermediate_records)
    write_jsonl(intermediate / "entity_mentions.jsonl", entity_mentions)
    write_jsonl(intermediate / "relation_mentions.jsonl", relation_mentions)
    write_jsonl(intermediate / "attribution_signals.jsonl", attribution_signals)
    write_jsonl(intermediate / "record_features.jsonl", record_features)
    _write_json(
        intermediate / "processing_report.json",
        {
            "dataset_id": "cti_rag_fixture",
            "dataset_version": "2026-06-28-fixture",
            "schema_version": "v0.1",
            "generated_at": "2026-06-28T00:00:00Z",
            "counts": {
                "intermediate_records": 1,
                "entity_mentions": 2,
                "relation_mentions": 1,
                "attribution_signals": 1,
                "warnings": 0,
            },
            "coverage": {},
            "warnings": [],
            "open_issues": [],
        },
    )
    return {
        "record_id": record_id,
        "intermediate_records": intermediate_records,
        "entity_mentions": entity_mentions,
        "relation_mentions": relation_mentions,
        "attribution_signals": attribution_signals,
        "record_features": record_features,
    }


def _codes(result) -> set[str]:
    return {message.code for message in result.messages}


def test_valid_tiny_delivery_passes(tmp_path: Path) -> None:
    _tiny_delivery(tmp_path)

    result = validate_delivery(tmp_path)

    assert result.ok
    assert result.failures == ()


def test_malformed_jsonl_fails(tmp_path: Path) -> None:
    _tiny_delivery(tmp_path)
    (tmp_path / "intermediate" / "entity_mentions.jsonl").write_text("{bad json\n")

    result = validate_delivery(tmp_path)

    assert "jsonl_parse_error" in _codes(result)
    assert not result.ok


def test_duplicate_ids_fail(tmp_path: Path) -> None:
    rows = _tiny_delivery(tmp_path)["entity_mentions"]
    write_jsonl(tmp_path / "intermediate" / "entity_mentions.jsonl", [rows[0], rows[0]])

    result = validate_delivery(tmp_path)

    assert "duplicate_id" in _codes(result)


def test_broken_record_id_join_fails(tmp_path: Path) -> None:
    rows = _tiny_delivery(tmp_path)["attribution_signals"]
    rows[0] = {**rows[0], "record_id": "record_missing"}
    write_jsonl(tmp_path / "intermediate" / "attribution_signals.jsonl", rows)

    result = validate_delivery(tmp_path)

    assert "broken_record_join" in _codes(result)


def test_invalid_controlled_vocabulary_value_fails(tmp_path: Path) -> None:
    rows = _tiny_delivery(tmp_path)["relation_mentions"]
    rows[0]["predicate"] = {**rows[0]["predicate"], "mapped_value": "associated-with"}
    write_jsonl(tmp_path / "intermediate" / "relation_mentions.jsonl", rows)

    result = validate_delivery(tmp_path)

    assert "invalid_vocabulary" in _codes(result)


def test_missing_required_key_fails(tmp_path: Path) -> None:
    rows = _tiny_delivery(tmp_path)["intermediate_records"]
    rows[0] = {key: value for key, value in rows[0].items() if key != "record_signals"}
    write_jsonl(tmp_path / "intermediate" / "intermediate_records.jsonl", rows)

    result = validate_delivery(tmp_path)

    assert "missing_required_key" in _codes(result)


def test_nested_intermediate_record_required_keys_fail(tmp_path: Path) -> None:
    rows = _tiny_delivery(tmp_path)["intermediate_records"]
    rows[0] = {
        **rows[0],
        "source": {},
        "timestamps": {},
        "record_signals": {},
        "processing_status": {},
    }
    write_jsonl(tmp_path / "intermediate" / "intermediate_records.jsonl", rows)

    result = validate_delivery(tmp_path)

    assert "missing_required_key" in _codes(result)
    failing_paths = {message.path for message in result.failures}
    assert "intermediate_records.jsonl:1.source.connector_source" in failing_paths
    assert "intermediate_records.jsonl:1.source.source_class" in failing_paths
    assert "intermediate_records.jsonl:1.source.publisher_category" in failing_paths
    assert "intermediate_records.jsonl:1.timestamps.timestamp_basis" in failing_paths
    assert "intermediate_records.jsonl:1.record_signals.label_availability" in failing_paths
    assert "intermediate_records.jsonl:1.processing_status.status" in failing_paths


def test_source_manifest_count_mismatch_fails(tmp_path: Path) -> None:
    _tiny_delivery(tmp_path)
    manifest_path = tmp_path / "intermediate" / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"][0]["record_count"] = 2
    _write_json(manifest_path, manifest)

    result = validate_delivery(tmp_path)

    assert "manifest_record_count_mismatch" in _codes(result)


def test_processing_report_missing_count_warns(tmp_path: Path) -> None:
    _tiny_delivery(tmp_path)
    report_path = tmp_path / "intermediate" / "processing_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    del report["counts"]["relation_mentions"]
    _write_json(report_path, report)

    result = validate_delivery(tmp_path)

    assert "processing_report_missing_count" in _codes(result)
    assert result.ok


def test_package_layout_requires_raw_and_intermediate_dirs(tmp_path: Path) -> None:
    result = validate_delivery(tmp_path)

    assert "package_layout" in _codes(result)
    assert "missing_artifact" in _codes(result)


def test_optional_projections_path_must_be_directory(tmp_path: Path) -> None:
    _tiny_delivery(tmp_path)
    (tmp_path / "projections").write_text("not a directory", encoding="utf-8")

    result = validate_delivery(tmp_path)

    assert "package_layout" in _codes(result)


def test_raw_collection_must_be_package_relative_under_raw(tmp_path: Path) -> None:
    _tiny_delivery(tmp_path)
    manifest_path = tmp_path / "intermediate" / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"][0]["raw_collection"] = "data/raw/otx"
    _write_json(manifest_path, manifest)

    result = validate_delivery(tmp_path)

    assert "raw_collection_not_package_relative" in _codes(result)


def test_raw_path_must_be_package_relative_under_raw(tmp_path: Path) -> None:
    rows = _tiny_delivery(tmp_path)["intermediate_records"]
    rows[0] = {**rows[0], "raw_ref": {**rows[0]["raw_ref"], "raw_path": "data/raw/otx/pulse.json"}}
    write_jsonl(tmp_path / "intermediate" / "intermediate_records.jsonl", rows)

    result = validate_delivery(tmp_path)

    assert "raw_ref_not_package_relative" in _codes(result)


def test_new_delivery_missing_raw_sha256_fails(tmp_path: Path) -> None:
    rows = _tiny_delivery(tmp_path)["intermediate_records"]
    rows[0] = {**rows[0], "raw_ref": {**rows[0]["raw_ref"]}}
    del rows[0]["raw_ref"]["raw_sha256"]
    write_jsonl(tmp_path / "intermediate" / "intermediate_records.jsonl", rows)

    result = validate_delivery(tmp_path)

    assert "missing_raw_sha256" in _codes(result)
    assert not result.ok


def test_legacy_delivery_missing_raw_sha256_warns(tmp_path: Path) -> None:
    rows = _tiny_delivery(tmp_path)["intermediate_records"]
    rows[0] = {**rows[0], "raw_ref": {**rows[0]["raw_ref"]}}
    del rows[0]["raw_ref"]["raw_sha256"]
    write_jsonl(tmp_path / "intermediate" / "intermediate_records.jsonl", rows)

    result = validate_delivery(tmp_path, legacy=True)

    assert "missing_raw_sha256" in _codes(result)
    assert result.ok
    assert result.warnings


def test_source_backed_missingness_warns(tmp_path: Path) -> None:
    rows = _tiny_delivery(tmp_path)["entity_mentions"]
    rows.append(
        {
            **rows[0],
            "entity_mention_id": contract_id(
                "em", (rows[0]["record_id"], "indicators[].indicator", "indicator", "evil.com")
            ),
            "raw_value": "evil.com",
            "normalized_value": "evil.com",
            "entity_type": "indicator",
            "source_field": "indicators[].indicator",
            "value_type": {"raw": None, "canonical": None},
            "resolution": {
                "entity_id": "indicator_abc",
                "canonical_name": "evil.com",
                "ontology_id": None,
                "resolution_method": "not_applicable",
            },
        }
    )
    write_jsonl(tmp_path / "intermediate" / "entity_mentions.jsonl", rows)

    result = validate_delivery(tmp_path)

    assert "missing_source_backed_field" in _codes(result)
    assert result.ok
