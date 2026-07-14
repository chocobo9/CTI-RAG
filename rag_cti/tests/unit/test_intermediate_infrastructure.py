from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_cti.intermediate.infrastructure import build_infrastructure_intermediate_package
from rag_cti.intermediate.validation import validate_delivery


def _pdns_raw() -> dict[str, Any]:
    return {
        "source": "pdns",
        "source_id": "evil.example",
        "fetched_at": "2026-06-15T23:33:16.707732+00:00",
        "payload": {
            "count": 3,
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
                {
                    "address": "5.6.7.8",
                    "asset_type": "hostname",
                    "first": "2024-03-01T00:00:00",
                    "hostname": "www.evil.example",
                    "last": "2025-01-01T00:00:00",
                    "record_type": "A",
                },
            ],
        },
    }


def _vt_payload() -> dict[str, Any]:
    return {
        "data": {
            "type": "domain",
            "id": "evil.example",
            "attributes": {
                "last_modification_date": 1717200000,
                "last_analysis_stats": {"malicious": 5, "harmless": 60},
                "categories": {"engine-a": "malware", "engine-b": "phishing"},
                "tags": ["c2"],
                "registrar": "NameSilo, LLC",
                "creation_date": 1176214113,
                "expiration_date": 1779055337,
                "last_dns_records": [
                    {"type": "A", "value": "1.2.3.4", "ttl": 3600},
                    {"type": "NS", "value": "ns1.example.net"},
                    {"type": "SOA", "value": "ignored.example"},
                ],
            },
        }
    }


def _vt_raw_record() -> dict[str, Any]:
    return {
        "source": "vt",
        "source_id": "evil.example",
        "fetched_at": "2026-06-16T10:20:30+00:00",
        "payload": _vt_payload(),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_infrastructure_happy_path_builds_valid_pdns_and_vt_package(tmp_path: Path) -> None:
    build_infrastructure_intermediate_package(
        pdns_records=[_pdns_raw()],
        vt_payloads=[_vt_payload()],
        output_dir=tmp_path,
        dataset_id="cti_rag_infra_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-16T00:00:00Z",
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

    assert {
        source["connector_source"]: source["record_count"] for source in manifest["sources"]
    } == {"pdns": 1, "vt": 1}
    assert len(records) == 2
    assert len(features) == 2
    assert report["counts"]["attribution_signals"] == 0
    assert any("SOA" in issue for issue in report["open_issues"])
    assert any("VT categories" in issue for issue in report["open_issues"])
    assert not any("related-to" in issue or "observed-with" in issue for issue in report["open_issues"])
    assert all(record["raw_ref"]["raw_path"].startswith("raw/") for record in records)
    assert all(len(record["raw_ref"]["raw_sha256"]) == 64 for record in records)
    assert all((tmp_path / record["raw_ref"]["raw_path"]).is_file() for record in records)

    records_by_source = {record["source"]["connector_source"]: record for record in records}
    pdns_record = records_by_source["pdns"]
    vt_record = records_by_source["vt"]
    assert pdns_record["timestamps"]["observed_first"] == "2024-01-01T00:00:00"
    assert pdns_record["timestamps"]["observed_last"] == "2026-06-01T00:00:00"
    assert pdns_record["timestamps"]["timestamp_basis"] == "observed_range"
    assert vt_record["timestamps"]["modified_at"] == "2024-06-01T00:00:00+00:00"
    assert vt_record["timestamps"]["timestamp_basis"] == "source_modified"
    assert all(record["record_signals"]["label_availability"] == "none" for record in records)

    mention_ids = {mention["entity_mention_id"] for mention in mentions}
    assert relations
    assert all(rel["subject"]["entity_mention_id"] in mention_ids for rel in relations)
    assert all(rel["object"]["entity_mention_id"] in mention_ids for rel in relations)
    assert all(rel["derivation"]["label_availability"] == "none" for rel in relations)
    assert all(rel["derivation"]["extraction_method"] == "structured_relation" for rel in relations)

    by_source_and_predicate = {
        (rel["source"]["connector_source"], rel["predicate"]["mapped_value"]) for rel in relations
    }
    assert ("pdns", "resolves-to") in by_source_and_predicate
    assert ("pdns", "belongs-to") in by_source_and_predicate
    assert ("pdns", "located-in") in by_source_and_predicate
    assert ("pdns", "uses-nameserver") in by_source_and_predicate
    assert ("pdns", "has-subdomain") in by_source_and_predicate
    assert ("vt", "resolves-to") in by_source_and_predicate
    assert ("vt", "uses-nameserver") in by_source_and_predicate

    domain_mentions = [
        mention
        for mention in mentions
        if mention["entity_type"] == "domain" and mention["raw_value"] == "evil.example"
    ]
    assert {mention["source"]["connector_source"] for mention in domain_mentions} == {"pdns", "vt"}
    assert len({mention["resolution"]["entity_id"] for mention in domain_mentions}) == 2

    assert signals == []
    vt_features = next(
        feature for feature in features if feature["source_features"]["connector_source"] == "vt"
    )
    assert vt_features["content_features"]["registrar"] == "NameSilo, LLC"
    assert vt_features["content_features"]["analysis_stats"] == {"malicious": 5, "harmless": 60}


def test_infrastructure_accepts_vt_rawstore_wrapper_and_delivers_raw_snapshot(
    tmp_path: Path,
) -> None:
    raw_record = _vt_raw_record()

    build_infrastructure_intermediate_package(
        pdns_records=[],
        vt_records=[raw_record],
        output_dir=tmp_path,
        dataset_id="cti_rag_infra_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-16T00:00:00Z",
    )

    result = validate_delivery(tmp_path)

    assert result.ok
    intermediate = tmp_path / "intermediate"
    records = _read_jsonl(intermediate / "intermediate_records.jsonl")
    relations = _read_jsonl(intermediate / "relation_mentions.jsonl")

    assert len(records) == 1
    record = records[0]
    assert record["source"]["connector_source"] == "vt"
    assert record["source"]["source_record_id"] == "evil.example"
    assert record["raw_ref"]["source_id"] == "evil.example"
    assert record["raw_ref"]["fetched_at"] == "2026-06-16T10:20:30+00:00"
    assert "source_" not in record["source"]["source_record_id"]

    delivered_raw = _read_json(tmp_path / record["raw_ref"]["raw_path"])
    assert delivered_raw == raw_record
    assert "payload" in delivered_raw
    assert "data" in delivered_raw["payload"]

    vt_relations = [
        rel for rel in relations if rel["source"]["connector_source"] == "vt"
    ]
    assert {rel["predicate"]["mapped_value"] for rel in vt_relations} == {
        "resolves-to",
        "uses-nameserver",
    }
