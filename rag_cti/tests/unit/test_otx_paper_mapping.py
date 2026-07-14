from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_cti.intermediate.otx_paper_mapping import build_otx_paper_mapping


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _pulse(**overrides: Any) -> dict[str, Any]:
    pulse = {
        "id": "pulse-1",
        "name": "Operation Example",
        "created": "2026-01-01T00:00:00Z",
        "modified": "2026-01-02T00:00:00Z",
        "adversary": "Fancy Bear",
        "tags": ["apt28", "collection-query-tag"],
        "indicators": [
            {
                "id": 1,
                "indicator": "Example.COM",
                "type": "domain",
                "created": "2026-01-01T01:00:00Z",
            },
            {
                "id": 2,
                "indicator": "d41d8cd98f00b204e9800998ecf8427e",
                "type": "FileHash-MD5",
            },
        ],
    }
    pulse.update(overrides)
    return pulse


def _mitre_seed(path: Path) -> None:
    _write_json(
        path,
        {
            "actors": [
                {
                    "actor_id": "intrusion-set--apt28",
                    "stix_id": "intrusion-set--apt28",
                    "mitre_attack_id": "G0007",
                    "name": "APT28",
                    "aliases": ["Fancy Bear", "Sofacy"],
                },
                {
                    "actor_id": "intrusion-set--apt29",
                    "stix_id": "intrusion-set--apt29",
                    "mitre_attack_id": "G0016",
                    "name": "APT29",
                    "aliases": ["Cozy Bear"],
                },
            ]
        },
    )


def test_otx_paper_mapping_emits_direct_actor_ioc_rows_and_keeps_provenance(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    raw_path = tmp_path / "raw" / "otx" / "pulse-1" / "v1.json"
    mitre_path = tmp_path / "mitre_actors.json"
    _mitre_seed(mitre_path)
    _write_json(run_dir / "checkpoint.json", {"completed_pulse_details": ["pulse-1"]})
    _write_json(
        raw_path,
        {
            "source": "otx",
            "source_id": "pulse-1",
            "fetched_at": "2026-07-04T00:00:00Z",
            "payload": _pulse(),
        },
    )
    _append_jsonl(
        run_dir / "saved_files.jsonl",
        {"kind": "pulse_detail", "pulse_id": "pulse-1", "raw_ref": {"path": str(raw_path)}},
    )
    _append_jsonl(
        run_dir / "discovery_metadata.jsonl",
        {
            "pulse_id": "pulse-1",
            "query": "APT29",
            "query_normalized": "apt29",
            "query_actors": [{"actor_name": "APT29"}],
            "search_page": 1,
            "search_rank": 2,
        },
    )

    result = build_otx_paper_mapping(
        run_dir,
        tmp_path / "out",
        mitre_actors_path=mitre_path,
    )

    assert result.completed_pulses == 1
    assert result.ioc_attribution_rows == 2

    pulse_rows = _read_jsonl(tmp_path / "out" / "pulse_actor_mappings.jsonl")
    ioc_rows = _read_jsonl(tmp_path / "out" / "ioc_attributions_paper_style.jsonl")
    indicator_rows = _read_jsonl(tmp_path / "out" / "indicators_flat.jsonl")
    summary = _read_json(tmp_path / "out" / "mapping_summary.json")

    assert pulse_rows[0]["mapping_status"] == "mapped_single_actor"
    assert pulse_rows[0]["accepted_actor_ids"] == ["intrusion-set--apt28"]
    assert pulse_rows[0]["discovery_provenance"][0]["query"] == "APT29"
    assert "not used as actor attribution" not in json.dumps(ioc_rows).lower()

    assert {row["actor_name"] for row in ioc_rows} == {"APT28"}
    assert {row["actor_mitre_attack_id"] for row in ioc_rows} == {"G0007"}
    assert {row["source_actor_field"] for row in ioc_rows} == {"adversary"}
    assert {row["indicator_type_canonical"] for row in ioc_rows} == {"domain", "hash-md5"}
    assert any(row["indicator_value_normalized"] == "example.com" for row in indicator_rows)
    assert summary["counts"]["ioc_attribution_rows"] == 2


def test_otx_paper_mapping_does_not_promote_tag_only_actor_to_main_table(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    raw_path = tmp_path / "raw" / "otx" / "pulse-1" / "v1.json"
    mitre_path = tmp_path / "mitre_actors.json"
    _mitre_seed(mitre_path)
    _write_json(run_dir / "checkpoint.json", {"completed_pulse_details": ["pulse-1"]})
    _write_json(
        raw_path,
        {"source": "otx", "source_id": "pulse-1", "payload": _pulse(adversary="", tags=["APT28"])},
    )
    _append_jsonl(
        run_dir / "saved_files.jsonl",
        {"kind": "pulse_detail", "pulse_id": "pulse-1", "raw_ref": {"path": str(raw_path)}},
    )

    build_otx_paper_mapping(run_dir, tmp_path / "out", mitre_actors_path=mitre_path)

    pulse_rows = _read_jsonl(tmp_path / "out" / "pulse_actor_mappings.jsonl")
    ioc_rows = _read_jsonl(tmp_path / "out" / "ioc_attributions_paper_style.jsonl")

    assert pulse_rows[0]["mapping_status"] == "missing_direct_actor_label"
    assert pulse_rows[0]["tag_actor_candidates"][0]["mapping_status"] == "mapped_unambiguous"
    assert ioc_rows == []
