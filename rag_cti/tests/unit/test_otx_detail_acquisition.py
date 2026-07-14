import json
from pathlib import Path

from rag_cti.intermediate.otx_detail_acquisition import build_detail_acquisition_artifacts


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_routes_every_candidate_without_treating_query_actor_as_source_evidence(tmp_path: Path) -> None:
    taxonomy = tmp_path / "enterprise-attack.json"
    _write_json(
        taxonomy,
        {
            "objects": [
                {
                    "type": "intrusion-set",
                    "id": "intrusion-set--one",
                    "name": "APT One",
                    "aliases": ["Shared"],
                    "external_references": [{"source_name": "mitre-attack", "external_id": "G0001"}],
                },
                {
                    "type": "intrusion-set",
                    "id": "intrusion-set--two",
                    "name": "APT Two",
                    "aliases": ["Shared"],
                    "external_references": [{"source_name": "mitre-attack", "external_id": "G0002"}],
                },
            ]
        },
    )
    raw = tmp_path / "data/raw/otx_search/q1/t.json"
    pulses = [
        {"id": "p1", "adversary": "APT One", "tags": []},
        {"id": "p2", "adversary": "APT One, APT Two", "tags": []},
        {"id": "p3", "adversary": "", "tags": ["Shared"]},
        {"id": "p4", "adversary": "New Actor Label", "tags": []},
        {"id": "p5", "adversary": "", "tags": ["malware", "finance"]},
    ]
    _write_json(raw, {"source": "otx_search", "source_id": "q1", "fetched_at": "2026-01-01Z", "payload": {"results": pulses}})
    candidates = tmp_path / "candidate_events.jsonl"
    ref = {"path": raw.as_posix(), "source_id": "q1", "fetched_at": "2026-01-01Z"}
    candidates.write_text(
        "".join(
            json.dumps({"pulse_id": pulse["id"], "discovery_paths": [{"query": "APT One", "query_actors": [{"mitre_attack_id": "G0001"}], "search_raw_ref": ref}]}) + "\n"
            for pulse in pulses
        ),
        encoding="utf-8",
    )

    artifacts = build_detail_acquisition_artifacts(candidates, taxonomy, tmp_path / "data/raw")

    assert [row["pulse_id"] for row in artifacts.rows] == ["p1", "p2", "p3", "p4", "p5"]
    assert [row["decision"] for row in artifacts.rows] == [
        "acquire_actor_evidenced",
        "acquire_multi_actor",
        "acquire_ambiguous_actor",
        "acquire_unmapped_actor_label",
        "deferred_query_only",
    ]
    assert artifacts.rows[-1]["source_evidence"]["adversary"] is None
    assert artifacts.rows[-1]["source_evidence"]["actor_related_tags"] == []
    assert artifacts.rows[-1]["resolution_status"] == "missing"
    assert artifacts.summary["candidate_count"] == 5
    assert artifacts.summary["acquire_count"] == 4
    assert artifacts.summary["deferred_count"] == 1
    assert artifacts.summary["acquire_missing_detail_count"] == 4


def test_marks_existing_detail_from_rawstore_without_reading_detail_payload(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.json"
    _write_json(taxonomy, {"objects": []})
    raw = tmp_path / "data/raw/otx_search/q/t.json"
    _write_json(raw, {"payload": {"results": [{"id": "p", "adversary": "Unknown Actor", "tags": []}]}})
    candidates = tmp_path / "candidates.jsonl"
    candidates.write_text(json.dumps({"pulse_id": "p", "discovery_paths": [{"search_raw_ref": {"path": raw.as_posix()}}]}) + "\n", encoding="utf-8")
    detail = tmp_path / "data/raw/otx/p/now.json"
    detail.parent.mkdir(parents=True)
    detail.write_text("not parsed by routing", encoding="utf-8")

    artifacts = build_detail_acquisition_artifacts(candidates, taxonomy, tmp_path / "data/raw")

    assert artifacts.rows[0]["existing_detail"] is True
    assert artifacts.summary["existing_detail_count"] == 1
    assert artifacts.summary["acquire_existing_detail_count"] == 1
