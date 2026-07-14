from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_cti.intermediate.mitre import build_mitre_intermediate_package
from rag_cti.intermediate.validation import validate_delivery


def _mitre_objects() -> list[dict[str, Any]]:
    return [
        {
            "type": "attack-pattern",
            "id": "attack-pattern--11111111-1111-4111-8111-111111111111",
            "name": "System Network Configuration Discovery",
            "description": "Adversaries may look for details about the network configuration.",
            "created": "2017-05-31T21:30:22.000Z",
            "modified": "2026-04-15T18:00:00.000Z",
            "external_references": [
                {
                    "source_name": "mitre-attack",
                    "external_id": "T1016",
                    "url": "https://attack.mitre.org/techniques/T1016/",
                }
            ],
            "kill_chain_phases": [
                {"kill_chain_name": "mitre-attack", "phase_name": "discovery"}
            ],
        },
        {
            "type": "intrusion-set",
            "id": "intrusion-set--22222222-2222-4222-8222-222222222222",
            "name": "Cleaver",
            "description": "Example ATT&CK group.",
            "created": "2017-05-31T21:31:22.000Z",
            "modified": "2026-04-15T18:01:00.000Z",
            "aliases": ["Cleaver", "TG-2889"],
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "G0003"}
            ],
        },
        {
            "type": "malware",
            "id": "malware--33333333-3333-4333-8333-333333333333",
            "name": "Example Malware",
            "description": "Example ATT&CK malware.",
            "created": "2017-05-31T21:32:22.000Z",
            "modified": "2026-04-15T18:02:00.000Z",
            "x_mitre_aliases": ["Example Malware", "Example RAT"],
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "S0001"}
            ],
        },
        {
            "type": "tool",
            "id": "tool--44444444-4444-4444-8444-444444444444",
            "name": "Example Tool",
            "description": "Example ATT&CK tool.",
            "created": "2017-05-31T21:33:22.000Z",
            "modified": "2026-04-15T18:03:00.000Z",
            "x_mitre_aliases": ["Example Tool", "Example CLI"],
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "S0002"}
            ],
        },
        {
            "type": "campaign",
            "id": "campaign--55555555-5555-4555-8555-555555555555",
            "name": "Example Campaign",
            "description": "Example ATT&CK campaign.",
            "created": "2017-05-31T21:34:22.000Z",
            "modified": "2026-04-15T18:04:00.000Z",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "C0001"}
            ],
        },
        {
            "type": "course-of-action",
            "id": "course-of-action--66666666-6666-4666-8666-666666666666",
            "name": "Audit",
            "description": "Example ATT&CK mitigation.",
            "created": "2017-05-31T21:35:22.000Z",
            "modified": "2026-04-15T18:05:00.000Z",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "M1047"}
            ],
        },
        {
            "type": "x-mitre-detection-strategy",
            "id": "x-mitre-detection-strategy--77777777-7777-4777-8777-777777777777",
            "name": "Network Discovery Monitoring",
            "description": "Example ATT&CK detection strategy.",
            "created": "2026-01-01T00:00:00.000Z",
            "modified": "2026-04-15T18:06:00.000Z",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "DET0001"}
            ],
        },
        {
            "type": "relationship",
            "id": "relationship--88888888-8888-4888-8888-888888888888",
            "relationship_type": "uses",
            "source_ref": "malware--33333333-3333-4333-8333-333333333333",
            "target_ref": "attack-pattern--11111111-1111-4111-8111-111111111111",
            "description": "Example Malware uses System Network Configuration Discovery.",
            "created": "2026-04-15T18:10:00.000Z",
            "modified": "2026-04-15T18:10:00.000Z",
        },
        {
            "type": "relationship",
            "id": "relationship--99999999-9999-4999-8999-999999999999",
            "relationship_type": "attributed-to",
            "source_ref": "campaign--55555555-5555-4555-8555-555555555555",
            "target_ref": "intrusion-set--22222222-2222-4222-8222-222222222222",
            "description": "Example Campaign is attributed to Cleaver.",
            "created": "2026-04-15T18:11:00.000Z",
            "modified": "2026-04-15T18:11:00.000Z",
        },
        {
            "type": "relationship",
            "id": "relationship--aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "relationship_type": "mitigates",
            "source_ref": "course-of-action--66666666-6666-4666-8666-666666666666",
            "target_ref": "attack-pattern--11111111-1111-4111-8111-111111111111",
            "description": "Audit mitigates System Network Configuration Discovery.",
            "created": "2026-04-15T18:12:00.000Z",
            "modified": "2026-04-15T18:12:00.000Z",
        },
        {
            "type": "relationship",
            "id": "relationship--bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "relationship_type": "detects",
            "source_ref": "x-mitre-detection-strategy--77777777-7777-4777-8777-777777777777",
            "target_ref": "attack-pattern--11111111-1111-4111-8111-111111111111",
            "description": "Network Discovery Monitoring detects the technique.",
            "created": "2026-04-15T18:13:00.000Z",
            "modified": "2026-04-15T18:13:00.000Z",
        },
    ]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_mitre_happy_path_builds_valid_intermediate_package(tmp_path: Path) -> None:
    build_mitre_intermediate_package(
        _mitre_objects(),
        tmp_path,
        dataset_id="cti_rag_mitre_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-15T00:00:00Z",
    )

    result = validate_delivery(tmp_path)

    assert result.ok
    intermediate = tmp_path / "intermediate"
    manifest = _read_json(intermediate / "source_manifest.json")
    report = _read_json(intermediate / "processing_report.json")
    records = _read_jsonl(intermediate / "intermediate_records.jsonl")
    mentions = _read_jsonl(intermediate / "entity_mentions.jsonl")
    relations = _read_jsonl(intermediate / "relation_mentions.jsonl")
    signals = _read_jsonl(intermediate / "attribution_signals.jsonl")
    features = _read_jsonl(intermediate / "record_features.jsonl")

    assert manifest["sources"][0]["connector_source"] == "mitre"
    assert manifest["sources"][0]["record_count"] == 11
    assert report["counts"]["intermediate_records"] == 11
    assert len(records) == 11
    assert all(record["raw_ref"]["raw_path"].startswith("raw/mitre/") for record in records)
    assert all(len(record["raw_ref"]["raw_sha256"]) == 64 for record in records)
    assert all((tmp_path / record["raw_ref"]["raw_path"]).is_file() for record in records)

    object_records = [row for row in records if row["source"]["object_type"] != "relationship"]
    assert len(object_records) == 7
    assert len({row["source"]["source_record_id"] for row in object_records}) == 7

    mentions_by_type: dict[str, set[str]] = {}
    for mention in mentions:
        mentions_by_type.setdefault(mention["entity_type"], set()).add(mention["raw_value"])
    assert "T1016" in mentions_by_type["technique"]
    assert "discovery" in mentions_by_type["tactic"]
    assert "Cleaver" in mentions_by_type["actor"]
    assert "Example Campaign" in mentions_by_type["campaign"]
    assert "Audit" in mentions_by_type["mitigation"]
    assert "Network Discovery Monitoring" in mentions_by_type["detection-strategy"]

    family_mentions = [
        mention
        for mention in mentions
        if mention["entity_type"] == "family" and mention["source_field"] == "name"
    ]
    assert {
        mention["raw_value"]: mention["value_type"] for mention in family_mentions
    } == {
        "Example Malware": {"raw": "malware", "canonical": "family"},
        "Example Tool": {"raw": "tool", "canonical": "family"},
    }
    assert {
        mention["raw_value"]: mention["resolution"]["entity_id"] for mention in family_mentions
    } == {"Example Malware": "family_S0001", "Example Tool": "family_S0002"}

    mention_ids = {mention["entity_mention_id"] for mention in mentions}
    assert all(rel["subject"]["entity_mention_id"] in mention_ids for rel in relations)
    assert all(rel["object"]["entity_mention_id"] in mention_ids for rel in relations)
    assert {rel["predicate"]["mapped_value"] for rel in relations} == {
        "uses",
        "attributed-to",
        "mitigates",
        "detects",
    }
    assert all(
        rel["derivation"]["extraction_method"] == "structured_relation" for rel in relations
    )
    label_by_predicate = {
        rel["predicate"]["mapped_value"]: rel["derivation"]["label_availability"]
        for rel in relations
    }
    assert label_by_predicate == {
        "uses": "none",
        "attributed-to": "direct",
        "mitigates": "none",
        "detects": "none",
    }
    record_label_by_type = {
        record["source"]["relationship_type"]: record["record_signals"]["label_availability"]
        for record in records
        if record["source"]["relationship_type"]
    }
    assert record_label_by_type == {
        "uses": "none",
        "attributed-to": "direct",
        "mitigates": "none",
        "detects": "none",
    }
    feature_label_by_type = {
        feature["content_features"]["relationship_type"]: feature["label_features"]["label_availability"]
        for feature in features
        if feature["content_features"]["relationship_type"]
    }
    assert feature_label_by_type == {
        "uses": "none",
        "attributed-to": "direct",
        "mitigates": "none",
        "detects": "none",
    }

    attributed = next(
        rel for rel in relations if rel["predicate"]["mapped_value"] == "attributed-to"
    )
    assert attributed["subject"]["entity_type"] == "campaign"
    assert attributed["object"]["entity_type"] == "actor"

    assert len(signals) == 1
    signal = signals[0]
    assert signal["signal_type"] == "direct_attribution"
    assert signal["target_entity_type"] == "actor"
    assert signal["raw_label"] == "Cleaver"
    assert signal["resolved_entity_id"] == "actor_G0003"
    assert signal["source_field"] == "relationship_type,target_ref"
