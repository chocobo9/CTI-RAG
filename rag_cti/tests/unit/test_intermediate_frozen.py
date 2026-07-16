from __future__ import annotations

import json
from pathlib import Path

from rag_cti.intermediate.frozen import build_frozen_intermediate_package


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_frozen_processor_preserves_multi_actor_and_source_provenance(tmp_path: Path) -> None:
    otx = tmp_path / "data" / "processed" / "otx_actor_event_dataset_routeA_20260712"
    raw_otx = tmp_path / "data" / "raw" / "otx" / "pulse-1" / "pulse.json"
    raw_otx.parent.mkdir(parents=True)
    raw_otx.write_text(
        json.dumps(
            {
                "payload": {
                    "id": "pulse-1",
                    "created": "2026-01-01T00:00:00Z",
                    "modified": "2026-01-02T00:00:00Z",
                    "adversary": "Example Panda",
                    "attack_ids": ["T1059"],
                    "malware_families": [{"display_name": "Example RAT"}],
                    "targeted_countries": ["Canada"],
                    "tags": ["apt"],
                    "references": ["https://example.test/report"],
                }
            }
        ),
        encoding="utf-8",
    )
    _jsonl(
        otx / "events.jsonl",
        [
            {
                "event_id": "otx:pulse:pulse-1",
                "source_record_id": "pulse-1",
                "raw_provenance": {"raw_path": "data/raw/otx/pulse-1/pulse.json", "fetched_at": "2026-01-03T00:00:00Z"},
            }
        ],
    )
    _jsonl(
        otx / "source_attribution_claims.jsonl",
        [
            {"claim_id": "c1", "event_id": "otx:pulse:pulse-1", "raw_label": "Example Panda", "resolved_actor_ids": [], "resolution_status": "unmapped"},
            {"claim_id": "c2", "event_id": "otx:pulse:pulse-1", "raw_label": "Other Panda", "resolved_actor_ids": [], "resolution_status": "unmapped"},
        ],
    )
    _jsonl(otx / "event_indicator_summaries.jsonl", [{"event_id": "otx:pulse:pulse-1", "indicator_count": 2, "type_counts": {"domain": 2}}])

    misp = tmp_path / "data" / "raw" / "circl_misp"
    _jsonl(
        misp / "normalized" / "events.jsonl",
        [{"event_id": "circl-misp:event:m1", "source_uuid": "m1", "raw_ref": "raw/events/m1.json", "raw_sha256": "a" * 64, "fetched_at": "2026-01-04T00:00:00Z", "published_at": "2026-01-01T00:00:00Z", "modified_at": "2026-01-02T00:00:00Z", "tags_raw": [{"name": "misp-galaxy:threat-actor=\"Example Panda\""}], "attribute_count": 1, "object_count": 0}],
    )
    misp_raw = misp / "raw" / "events" / "m1.json"
    misp_raw.parent.mkdir(parents=True, exist_ok=True)
    misp_raw.write_text(json.dumps({"Event": {"Attribute": [{"type": "domain", "value": "evil.example"}]}}), encoding="utf-8")
    _jsonl(
        misp / "normalized" / "source_actor_claims.jsonl",
        [{"claim_id": "mclaim", "event_id": "circl-misp:event:m1", "raw_label": "Example Panda", "claim_kind": "galaxy_actor_context", "raw_galaxy_type": "threat-actor", "parse_status": "preserved_unresolved", "source_field": "Event.Tag[0].name"}],
    )

    malpedia = tmp_path / "data" / "raw" / "malpedia" / "normalized"
    _jsonl(malpedia / "actors.jsonl", [{"actor_id": "malpedia:actor:example", "primary_name": "Example Panda", "aliases_raw": ["Second Panda"], "references_raw": [], "raw_ref": "raw/actors/actors.json", "fetched_at": "2026-01-05T00:00:00Z"}])
    _jsonl(malpedia / "families.jsonl", [{"family_id": "malpedia:family:rat", "primary_name": "Example RAT", "aliases_raw": [], "references_raw": [], "raw_ref": "raw/families/families.json", "fetched_at": "2026-01-05T00:00:00Z"}])
    _jsonl(malpedia / "actor_family_links.jsonl", [{"link_id": "link-1", "actor_id": "malpedia:actor:example", "actor_source_id_raw": "Example Panda", "family_id": "malpedia:family:rat", "family_source_id_raw": "Example RAT", "raw_ref": "raw/families/families.json"}])

    result = build_frozen_intermediate_package(repository_root=tmp_path, output_dir=tmp_path / "out", temporal_cutoff="2026-01-02T00:00:00Z", generated_at="2026-01-06T00:00:00Z")

    assert result.counts["otx_records"] == 1
    assert result.counts["circl_misp_records"] == 1
    assert result.counts["malpedia_records"] == 3
    records = [json.loads(line) for line in (tmp_path / "out" / "intermediate" / "intermediate_records.jsonl").read_text(encoding="utf-8").splitlines()]
    otx_record = next(record for record in records if record["source"]["connector_source"] == "otx")
    assert otx_record["record_signals"]["multi_actor_flag"] is True
    assert otx_record["record_signals"]["ambiguity_flag"] is True
    assert otx_record["indicators"]["occurrence_count"] == 2
    assert otx_record["raw_ref"]["raw_path"].startswith("data/raw/otx/")
    assert otx_record["temporal_split"] == "train"
    assert (tmp_path / "out" / "intermediate" / "alias_mappings.jsonl").is_file()
    assert (tmp_path / "out" / "neo4j" / "nodes.jsonl").is_file()
    assert (tmp_path / "out" / "neo4j" / "relationships.jsonl").is_file()
