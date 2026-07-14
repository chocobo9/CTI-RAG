from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_cti.intermediate.otx import build_otx_intermediate_package
from rag_cti.intermediate.validation import validate_delivery


def _happy_pulse() -> dict[str, Any]:
    return {
        "id": "pulse-otx-1",
        "name": "Operation Example",
        "description": "Example pulse describing actor activity.",
        "created": "2026-06-01T10:00:00Z",
        "modified": "2026-06-02T12:00:00Z",
        "author": "otx-user-7",
        "author_name": "OTX Contributor",
        "adversary": "Example Panda",
        "attack_ids": ["T1016", "T1059"],
        "malware_families": [{"display_name": "ExampleRAT"}],
        "targeted_countries": ["Canada"],
        "industries": ["Telecommunications"],
        "indicators": [
            {"indicator": "evil.example", "type": "domain"},
            {"indicator": "abcd" * 16, "type": "FileHash-SHA256"},
        ],
        "references": ["https://example.test/report"],
        "tags": ["apt", "example"],
        "TLP": "amber",
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_otx_happy_path_builds_valid_intermediate_package(tmp_path: Path) -> None:
    build_otx_intermediate_package(
        [_happy_pulse()],
        tmp_path,
        dataset_id="cti_rag_otx_test",
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

    assert manifest["sources"][0]["connector_source"] == "otx"
    assert manifest["sources"][0]["record_count"] == 1
    assert report["counts"]["intermediate_records"] == 1
    assert len(records) == 1
    assert len(features) == 1

    record = records[0]
    assert record["source"]["connector_source"] == "otx"
    assert record["source"]["source_class"] == "weakly_labeled_narrative"
    assert record["source"]["publisher_category"] == "threat_intelligence_platform"
    assert record["source"]["source_contributor"] == {
        "author": "otx-user-7",
        "author_name": "OTX Contributor",
    }
    assert record["timestamps"]["timestamp_basis"] == "source_modified"
    assert record["raw_ref"]["raw_path"].startswith("raw/otx/")
    assert len(record["raw_ref"]["raw_sha256"]) == 64
    assert (tmp_path / record["raw_ref"]["raw_path"]).is_file()

    mentions_by_type = {}
    for mention in mentions:
        mentions_by_type.setdefault(mention["entity_type"], set()).add(mention["raw_value"])
    assert "Example Panda" in mentions_by_type["actor"]
    assert {"T1016", "T1059"} <= mentions_by_type["technique"]
    assert "ExampleRAT" in mentions_by_type["family"]
    assert "evil.example" in mentions_by_type["indicator"]
    assert "Telecommunications" in mentions_by_type["sector"]
    assert "OTX Contributor" not in mentions_by_type["actor"]
    assert "otx-user-7" not in mentions_by_type["actor"]

    indicator = next(m for m in mentions if m["raw_value"] == "evil.example")
    assert indicator["value_type"] == {"raw": "domain", "canonical": "domain"}
    file_hash = next(m for m in mentions if m["raw_value"] == "abcd" * 16)
    assert file_hash["value_type"] == {
        "raw": "FileHash-SHA256",
        "canonical": "hash-sha256",
    }

    signal = signals[0]
    assert signal["signal_type"] == "weak_direct_attribution"
    assert signal["target_entity_type"] == "actor"
    assert signal["raw_label"] == "Example Panda"
    assert "ground_truth" not in signal
    actor = next(m for m in mentions if m["entity_type"] == "actor")
    assert actor["resolution"]["resolution_method"] == "orphan"

    mention_ids = {mention["entity_mention_id"] for mention in mentions}
    assert relations
    assert all(rel["subject"]["entity_mention_id"] in mention_ids for rel in relations)
    assert all(rel["object"]["entity_mention_id"] in mention_ids for rel in relations)
    assert any(rel["predicate"]["mapped_value"] == "uses" for rel in relations)
    assert any(rel["predicate"]["mapped_value"] == "targets" for rel in relations)


def test_otx_indicator_missing_type_warns_but_package_validates(tmp_path: Path) -> None:
    pulse = _happy_pulse()
    pulse["indicators"] = [{"indicator": "missing-type.example"}]

    build_otx_intermediate_package(
        [pulse],
        tmp_path,
        dataset_id="cti_rag_otx_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-15T00:00:00Z",
    )

    result = validate_delivery(tmp_path)

    assert result.ok
    assert any(message.code == "missing_source_backed_field" for message in result.warnings)
    report = _read_json(tmp_path / "intermediate" / "processing_report.json")
    records = _read_jsonl(tmp_path / "intermediate" / "intermediate_records.jsonl")
    indicators = [
        row
        for row in _read_jsonl(tmp_path / "intermediate" / "entity_mentions.jsonl")
        if row["entity_type"] == "indicator"
    ]
    assert report["counts"]["warnings"] == 1
    assert records[0]["processing_status"]["status"] == "partial"
    assert indicators[0]["value_type"] == {"raw": None, "canonical": None}


def test_otx_mixed_indicator_type_for_same_value_does_not_crash(
    tmp_path: Path,
) -> None:
    pulse = _happy_pulse()
    pulse["indicators"] = [
        {"indicator": "mixed-type.example"},
        {"indicator": "mixed-type.example", "type": "domain"},
    ]

    build_otx_intermediate_package(
        [pulse],
        tmp_path,
        dataset_id="cti_rag_otx_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-15T00:00:00Z",
    )

    result = validate_delivery(tmp_path)

    assert result.ok
    indicators = [
        row
        for row in _read_jsonl(tmp_path / "intermediate" / "entity_mentions.jsonl")
        if row["entity_type"] == "indicator"
    ]
    assert [row["value_type"] for row in indicators] == [
        {"raw": None, "canonical": None},
        {"raw": "domain", "canonical": "domain"},
    ]


def test_otx_duplicate_id_same_fetch_writes_distinct_raw_files(
    tmp_path: Path,
) -> None:
    first = _happy_pulse()
    second = {**_happy_pulse(), "name": "Operation Example Updated", "tags": ["updated"]}

    build_otx_intermediate_package(
        [first, second],
        tmp_path,
        dataset_id="cti_rag_otx_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-15T00:00:00Z",
    )

    result = validate_delivery(tmp_path)

    assert result.ok
    records = _read_jsonl(tmp_path / "intermediate" / "intermediate_records.jsonl")
    raw_paths = [record["raw_ref"]["raw_path"] for record in records]
    assert len(records) == 2
    assert len(set(raw_paths)) == 2
    assert all((tmp_path / raw_path).is_file() for raw_path in raw_paths)


def test_otx_resolved_actor_uses_provided_resolution(tmp_path: Path) -> None:
    pulse = _happy_pulse()
    pulse["adversary"] = "Cleaver"

    build_otx_intermediate_package(
        [pulse],
        tmp_path,
        dataset_id="cti_rag_otx_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-15T00:00:00Z",
        actor_resolutions={"Cleaver": {"entity_id": "actor_G0003", "ontology_id": "G0003"}},
    )

    result = validate_delivery(tmp_path)

    assert result.ok
    actor = next(
        row
        for row in _read_jsonl(tmp_path / "intermediate" / "entity_mentions.jsonl")
        if row["entity_type"] == "actor"
    )
    signal = _read_jsonl(tmp_path / "intermediate" / "attribution_signals.jsonl")[0]
    assert actor["resolution"] == {
        "entity_id": "actor_G0003",
        "canonical_name": "Cleaver",
        "ontology_id": "G0003",
        "resolution_method": "exact_alias",
    }
    assert actor["ambiguity"]["status"] == "resolved"
    assert signal["resolved_entity_id"] == "actor_G0003"


def test_otx_adversary_without_relation_fields_preserves_attribution_signal(
    tmp_path: Path,
) -> None:
    pulse = _happy_pulse()
    pulse["attack_ids"] = []
    pulse["malware_families"] = []
    pulse["targeted_countries"] = []

    build_otx_intermediate_package(
        [pulse],
        tmp_path,
        dataset_id="cti_rag_otx_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-15T00:00:00Z",
    )

    result = validate_delivery(tmp_path)

    assert result.ok
    relations = _read_jsonl(tmp_path / "intermediate" / "relation_mentions.jsonl")
    signals = _read_jsonl(tmp_path / "intermediate" / "attribution_signals.jsonl")
    assert relations == []
    assert signals[0]["signal_type"] == "weak_direct_attribution"
    assert signals[0]["raw_label"] == "Example Panda"
