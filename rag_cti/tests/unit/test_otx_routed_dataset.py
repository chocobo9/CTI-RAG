from __future__ import annotations

import json
from pathlib import Path

from rag_cti.intermediate.otx_routed_dataset import build_routed_otx_dataset


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_builds_one_actor_evidenced_dataset_without_materializing_iocs(tmp_path: Path) -> None:
    taxonomy = tmp_path / "enterprise-attack.json"
    _write_json(
        taxonomy,
        {
            "objects": [
                {
                    "type": "intrusion-set",
                    "id": "intrusion-set--one",
                    "name": "Actor One",
                    "aliases": ["Alias One"],
                    "external_references": [
                        {"source_name": "mitre-attack", "external_id": "G0001"}
                    ],
                }
            ]
        },
    )
    routing = tmp_path / "routing.jsonl"
    routing.write_text(
        "\n".join(
            [
                json.dumps({"pulse_id": "included", "decision": "acquire_actor_evidenced"}),
                json.dumps({"pulse_id": "deferred", "decision": "deferred_query_only"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    raw_root = tmp_path / "raw"
    for pulse_id, adversary in (("included", "Actor One"), ("deferred", None)):
        _write_json(
            raw_root / "otx" / pulse_id / "2026-07-01T00-00-00+00-00.json",
            {
                "source": "otx",
                "source_id": pulse_id,
                "fetched_at": "2026-07-01T00:00:00+00:00",
                "payload": {
                    "id": pulse_id,
                    "name": pulse_id,
                    "adversary": adversary,
                    "created": "2020-01-01T00:00:00Z",
                    "modified": "2020-02-01T00:00:00Z",
                    "indicators": [
                        {
                            "indicator": "example.com",
                            "type": "domain",
                            "created": "2019-01-01T00:00:00Z",
                        }
                    ],
                },
            },
        )
    discovery_run = tmp_path / "discovery"
    discovery_run.mkdir()
    _write_json(discovery_run / "mitre_actor_query_list.json", {"queries": [{}, {}]})
    (discovery_run / "query_terminal_states.jsonl").write_text(
        json.dumps({"query_normalized": "one", "status": "complete"}) + "\n"
        + json.dumps({"query_normalized": "two", "status": "truncated_page_cap"})
        + "\n",
        encoding="utf-8",
    )
    detail_audit = tmp_path / "detail_audit.json"
    _write_json(detail_audit, {"valid_detail_coverage": 1, "invalid_or_missing_count": 0})
    output = tmp_path / "output"

    manifest = build_routed_otx_dataset(
        routing_manifest=routing,
        raw_root=raw_root,
        mitre_taxonomy=taxonomy,
        discovery_run_dir=discovery_run,
        detail_audit_path=detail_audit,
        output_dir=output,
    )

    assert manifest["population"]["candidate_count"] == 2
    assert manifest["population"]["event_count"] == 1
    assert manifest["discovery_terminal_counts"] == {
        "complete": 1,
        "truncated_page_cap": 1,
    }
    assert manifest["detail_coverage"] == {"invalid_or_missing": 0, "valid": 1}
    assert manifest["indicator_materialization"] == "summary_only"
    assert len((output / "events.jsonl").read_text().splitlines()) == 1
    assert len((output / "source_attribution_claims.jsonl").read_text().splitlines()) == 1
    summaries = [json.loads(line) for line in (output / "event_indicator_summaries.jsonl").read_text().splitlines()]
    assert summaries[0]["indicator_count"] == 1
    assert "indicator" not in summaries[0]
    profile = json.loads((output / "dataset_temporal_profile.json").read_text())
    assert profile["event_count"] == 1
    assert profile["indicator_occurrence_count"] == 1
    assert set(manifest["output_sha256"]) == {
        "dataset_temporal_profile.json",
        "event_indicator_summaries.jsonl",
        "events.jsonl",
        "source_attribution_claims.jsonl",
    }
