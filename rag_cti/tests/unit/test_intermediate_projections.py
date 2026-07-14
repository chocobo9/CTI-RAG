from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from rag_cti.intermediate.delivery import build_intermediate_delivery_package
from rag_cti.intermediate.projections import (
    project_delivery_to_gnn_smoke,
    project_delivery_to_rag_smoke,
)
from rag_cti.intermediate.validation import validate_delivery


def _otx_pulse() -> dict[str, Any]:
    return {
        "id": "pulse-projection-1",
        "name": "Projection Fixture Pulse",
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


def _build_sample_delivery(root: Path) -> None:
    build_intermediate_delivery_package(
        output_dir=root,
        dataset_id="cti_rag_projection_test",
        dataset_version="2026-06-28-test",
        generated_at="2026-06-28T00:00:00Z",
        fetched_at="2026-06-16T00:00:00Z",
        otx_pulses=[_otx_pulse()],
        mitre_objects=_mitre_objects(),
        pdns_records=[_pdns_raw()],
        vt_records=[_vt_raw()],
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _intermediate_hashes(root: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((root / "intermediate").iterdir())
        if path.is_file()
    }


def test_projection_smoke_checks_consume_delivery_without_mutating_it(
    tmp_path: Path,
) -> None:
    _build_sample_delivery(tmp_path)
    result = validate_delivery(tmp_path)
    before_hashes = _intermediate_hashes(tmp_path)

    rag_rows = project_delivery_to_rag_smoke(tmp_path)
    gnn_projection = project_delivery_to_gnn_smoke(tmp_path)

    assert result.ok
    assert before_hashes == _intermediate_hashes(tmp_path)

    records = _read_jsonl(tmp_path / "intermediate" / "intermediate_records.jsonl")
    assert len(rag_rows) == len(records)
    assert {row["connector_source"] for row in rag_rows} == {"otx", "mitre", "pdns", "vt"}
    for row in rag_rows:
        assert {
            "record_id",
            "connector_source",
            "source_record_id",
            "summary_text",
            "entity_ids",
            "relation_predicates",
            "attribution_signal_types",
            "raw_ref",
        } <= row.keys()
        assert "payload" not in json.dumps(row, sort_keys=True)

    nodes = gnn_projection["nodes"]
    edges = gnn_projection["edges"]
    label_evidence = gnn_projection["label_evidence"]
    assert nodes
    assert edges
    node_ids = {node["node_id"] for node in nodes}
    assert all(edge["subject_node_id"] in node_ids for edge in edges)
    assert all(edge["object_node_id"] in node_ids for edge in edges)
    assert all("raw_ref" in node for node in nodes)
    assert all("raw_ref" in edge for edge in edges)

    evidence_sources = {row["connector_source"] for row in label_evidence}
    assert evidence_sources == {"otx", "mitre"}
    assert not {"pdns", "vt"} & evidence_sources

    infra_edges = [
        edge
        for edge in edges
        if edge["connector_source"] in {"pdns", "vt"}
        and edge["predicate"] in {"resolves-to", "uses-nameserver"}
    ]
    assert {edge["connector_source"] for edge in infra_edges} == {"pdns", "vt"}

    serialized_projection = json.dumps(
        {"rag": rag_rows, "gnn": gnn_projection},
        sort_keys=True,
    )
    assert "related-to" not in serialized_projection
    assert "observed-with" not in serialized_projection
