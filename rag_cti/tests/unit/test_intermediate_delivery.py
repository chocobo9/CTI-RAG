from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

import rag_cti.intermediate.delivery as delivery_module
from rag_cti.intermediate.delivery import (
    DeliveryAssemblyError,
    assemble_intermediate_delivery_package,
    build_intermediate_delivery_package,
)
from rag_cti.intermediate.validation import validate_delivery


def _otx_pulse() -> dict[str, Any]:
    return {
        "id": "pulse-delivery-1",
        "name": "Delivery Fixture Pulse",
        "created": "2026-06-01T10:00:00Z",
        "modified": "2026-06-02T12:00:00Z",
        "adversary": "Example Panda",
        "attack_ids": ["T1016"],
        "malware_families": [{"display_name": "ExampleRAT"}],
        "targeted_countries": ["Canada"],
        "industries": ["Telecommunications"],
        "indicators": [{"indicator": "evil.example", "type": "domain"}],
        "references": ["https://example.test/report"],
        "tags": ["apt"],
        "TLP": "amber",
    }


def _mitre_objects() -> list[dict[str, Any]]:
    group_id = "intrusion-set--22222222-2222-4222-8222-222222222222"
    campaign_id = "campaign--55555555-5555-4555-8555-555555555555"
    return [
        {
            "type": "intrusion-set",
            "id": group_id,
            "name": "Cleaver",
            "created": "2017-05-31T21:31:22.000Z",
            "modified": "2026-04-15T18:01:00.000Z",
            "aliases": ["Cleaver"],
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "G0003"}
            ],
        },
        {
            "type": "campaign",
            "id": campaign_id,
            "name": "Example Campaign",
            "created": "2017-05-31T21:34:22.000Z",
            "modified": "2026-04-15T18:04:00.000Z",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "C0001"}
            ],
        },
        {
            "type": "relationship",
            "id": "relationship--99999999-9999-4999-8999-999999999999",
            "relationship_type": "attributed-to",
            "source_ref": campaign_id,
            "target_ref": group_id,
            "created": "2026-04-15T18:11:00.000Z",
            "modified": "2026-04-15T18:11:00.000Z",
        },
    ]


def _pdns_raw() -> dict[str, Any]:
    return {
        "source": "pdns",
        "source_id": "evil.example",
        "fetched_at": "2026-06-15T23:33:16.707732+00:00",
        "payload": {
            "count": 2,
            "passive_dns": [
                {
                    "address": "1.2.3.4",
                    "asn": "AS64500 example hosting",
                    "asset_type": "domain",
                    "first": "2024-01-01T00:00:00",
                    "flag_title": "Canada",
                    "hostname": "evil.example",
                    "last": "2026-06-01T00:00:00",
                    "record_type": "A",
                },
                {
                    "address": "ns1.example.net",
                    "asset_type": "domain",
                    "first": "2024-02-01T00:00:00",
                    "hostname": "evil.example",
                    "last": "2026-06-01T00:00:00",
                    "record_type": "NS",
                },
            ],
        },
    }


def _vt_raw() -> dict[str, Any]:
    return {
        "source": "vt",
        "source_id": "evil.example",
        "fetched_at": "2026-06-16T10:20:30+00:00",
        "payload": {
            "data": {
                "type": "domain",
                "id": "evil.example",
                "attributes": {
                    "last_modification_date": 1717200000,
                    "last_analysis_stats": {"malicious": 5, "harmless": 60},
                    "categories": {"engine-a": "malware"},
                    "tags": ["c2"],
                    "registrar": "NameSilo, LLC",
                    "last_dns_records": [
                        {"type": "A", "value": "1.2.3.4"},
                        {"type": "NS", "value": "ns1.example.net"},
                    ],
                },
            }
        },
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_delivery_assembler_builds_valid_sampled_package(tmp_path: Path) -> None:
    build_intermediate_delivery_package(
        output_dir=tmp_path,
        dataset_id="cti_rag_delivery_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-16T00:00:00Z",
        otx_pulses=[_otx_pulse()],
        mitre_objects=_mitre_objects(),
        pdns_records=[_pdns_raw()],
        vt_records=[_vt_raw()],
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

    sources = {source["connector_source"]: source for source in manifest["sources"]}
    assert set(sources) == {"otx", "mitre", "pdns", "vt"}
    assert {source: item["record_count"] for source, item in sources.items()} == {
        "otx": 1,
        "mitre": 3,
        "pdns": 1,
        "vt": 1,
    }

    jsonl_counts = {
        "intermediate_records": len(records),
        "entity_mentions": len(mentions),
        "relation_mentions": len(relations),
        "attribution_signals": len(signals),
    }
    for key, count in jsonl_counts.items():
        assert report["counts"][key] == count
    assert report["counts"]["warnings"] == len(report["warnings"])
    assert report["coverage"]["connector_sources"] == {
        "mitre": 3,
        "otx": 1,
        "pdns": 1,
        "vt": 1,
    }
    assert report["coverage"]["entity_types"]
    assert report["coverage"]["relation_predicates"]
    assert report["coverage"]["attribution_signal_types"] == {
        "direct_attribution": 1,
        "weak_direct_attribution": 1,
    }

    for record in records:
        raw_ref = record["raw_ref"]
        raw_path = tmp_path / raw_ref["raw_path"]
        assert raw_path.is_file()
        assert raw_ref["raw_path"].startswith("raw/")
        assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == raw_ref["raw_sha256"]

    mention_ids = {mention["entity_mention_id"] for mention in mentions}
    assert relations
    assert all(relation["subject"]["entity_mention_id"] in mention_ids for relation in relations)
    assert all(relation["object"]["entity_mention_id"] in mention_ids for relation in relations)

    records_by_id = {record["record_id"]: record for record in records}
    signal_sources = {
        records_by_id[signal["record_id"]]["source"]["connector_source"] for signal in signals
    }
    assert signal_sources == {"otx", "mitre"}
    assert not {"pdns", "vt"} & signal_sources

    serialized_delivery = json.dumps(
        {
            "manifest": manifest,
            "report": report,
            "records": records,
            "mentions": mentions,
            "relations": relations,
            "signals": signals,
            "features": features,
        },
        sort_keys=True,
    )
    assert "related-to" not in serialized_delivery
    assert "observed-with" not in serialized_delivery


def test_delivery_assembler_fails_loud_on_raw_path_conflict(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    for package_dir, payload in ((first, "one"), (second, "two")):
        raw_path = package_dir / "raw" / "vt" / "duplicate.json"
        raw_path.parent.mkdir(parents=True)
        raw_path.write_text(payload, encoding="utf-8")

    with pytest.raises(DeliveryAssemblyError, match="raw path conflict"):
        assemble_intermediate_delivery_package(
            [first, second],
            output_dir=tmp_path / "delivery",
            dataset_id="cti_rag_delivery_test",
            dataset_version="2026-06-28-test",
            generated_at="2026-06-28T00:00:00Z",
        )


def test_delivery_assembler_uses_output_adjacent_temp_dir_and_cleans_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    temp_parents: list[Path | None] = []
    temp_paths: list[Path] = []

    class SpyTemporaryDirectory:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            temp_dir = kwargs.get("dir")
            temp_parents.append(Path(temp_dir) if temp_dir is not None else None)
            self._delegate = tempfile.TemporaryDirectory(*args, **kwargs)

        def __enter__(self) -> str:
            name = self._delegate.__enter__()
            temp_paths.append(Path(name))
            return name

        def __exit__(self, *args: Any) -> bool | None:
            return self._delegate.__exit__(*args)

    monkeypatch.setattr(delivery_module, "TemporaryDirectory", SpyTemporaryDirectory)
    output_dir = tmp_path / "delivery" / "sample"

    build_intermediate_delivery_package(
        output_dir=output_dir,
        dataset_id="cti_rag_delivery_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-16T00:00:00Z",
        vt_records=[_vt_raw()],
    )

    assert temp_parents == [output_dir.parent]
    assert temp_paths
    assert all(not path.exists() for path in temp_paths)
