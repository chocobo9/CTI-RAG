from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from rag_cti.intermediate.contract import contract_id
from rag_cti.intermediate.otx_downstream import (
    build_otx_downstream_projection,
    lint_otx_downstream_projection,
)


def _pulse(**overrides: Any) -> dict[str, Any]:
    pulse = {
        "id": "pulse-1",
        "name": "Operation Projection",
        "description": "Projection fixture.",
        "created": "2026-06-01T10:00:00Z",
        "modified": "2026-06-02T12:00:00Z",
        "author": "otx-user",
        "author_name": "OTX Contributor",
        "adversary": "APT28, APT29",
        "indicators": [
            {
                "indicator": "evil.example",
                "type": "domain",
                "created": "2026-06-01T11:00:00Z",
            },
            {
                "indicator": "https://evil.example/a",
                "type": "URL",
                "created": "2026-06-01T11:05:00Z",
            },
            {
                "indicator": "203.0.113.10",
                "type": "IPv4",
                "created": "2026-06-01T11:10:00Z",
            },
        ],
        "tags": ["apt28", "apt29"],
        "references": ["https://example.test/report"],
        "TLP": "amber",
    }
    pulse.update(overrides)
    return pulse


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _write_mitre_bundle(path: Path, objects: list[dict[str, Any]]) -> Path:
    _write_json(path, {"type": "bundle", "id": "bundle--test", "objects": objects})
    return path


def _mitre_actor(
    *,
    stix_id: str,
    name: str,
    attack_id: str,
    aliases: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "intrusion-set",
        "id": stix_id,
        "name": name,
        "created": "2020-01-01T00:00:00.000Z",
        "modified": "2026-01-01T00:00:00.000Z",
        "aliases": aliases or [name],
        "external_references": [
            {
                "source_name": "mitre-attack",
                "external_id": attack_id,
                "url": f"https://attack.mitre.org/groups/{attack_id}/",
            }
        ],
    }


def _empty_mitre_bundle(tmp_path: Path) -> Path:
    return _write_mitre_bundle(tmp_path / "mitre" / "enterprise-attack.json", [])


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")


def _load_build_script() -> ModuleType:
    path = Path(__file__).parents[2] / "scripts" / "build_otx_downstream_projection.py"
    spec = importlib.util.spec_from_file_location("build_otx_downstream_projection", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_otx_downstream_projection_scopes_inputs_to_completed_run_pulse_details(
    tmp_path: Path,
) -> None:
    raw_otx_dir = tmp_path / "raw" / "otx"
    run_dir = tmp_path / "raw" / "otx_collection_runs" / "run-a"
    detail_a = raw_otx_dir / "pulse-a" / "2026-07-04T00-00-00.json"
    detail_b = raw_otx_dir / "pulse-b" / "2026-07-04T00-00-00.json"
    outside_detail = raw_otx_dir / "pulse-outside" / "2026-07-04T00-00-00.json"
    search_page = tmp_path / "raw" / "otx_search" / "query" / "2026-07-04T00-00-00.json"
    indicator_page = tmp_path / "raw" / "otx_indicator_page" / "pulse-a-page" / "2026-07-04T00-00-00.json"

    _write_json(detail_a, {"source": "otx", "source_id": "pulse-a", "payload": _pulse(id="pulse-a")})
    _write_json(
        detail_b,
        {"source": "otx", "source_id": "pulse-b", "payload": _pulse(id="pulse-b")},
    )
    _write_json(
        outside_detail,
        {
            "source": "otx",
            "source_id": "pulse-outside",
            "payload": _pulse(id="pulse-outside"),
        },
    )
    _write_json(search_page, {"source": "otx_search", "payload": {"results": [{"id": "pulse-a"}]}})
    _write_json(
        indicator_page,
        {"source": "otx_indicator_page", "payload": {"results": [{"indicator": "page.example"}]}},
    )
    _write_json(run_dir / "checkpoint.json", {"completed_pulse_details": ["pulse-a", "pulse-b"]})
    _write_jsonl(
        run_dir / "saved_files.jsonl",
        [
            {"kind": "search_page", "raw_ref": {"path": str(search_page)}},
            {"kind": "pulse_detail", "pulse_id": "pulse-a", "raw_ref": {"path": str(detail_a)}},
            {"kind": "indicator_page", "pulse_id": "pulse-a", "raw_ref": {"path": str(indicator_page)}},
            {"kind": "pulse_detail", "pulse_id": "pulse-b", "raw_ref": {"path": str(detail_b)}},
            {
                "kind": "pulse_detail",
                "pulse_id": "pulse-outside",
                "raw_ref": {"path": str(outside_detail)},
            },
        ],
    )

    result = build_otx_downstream_projection(
        raw_otx_dir,
        tmp_path / "projection",
        otx_run_dir=run_dir,
    )

    events = _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")
    manifest = _read_json(tmp_path / "projection" / "projection_manifest.json")

    assert result.event_count == 2
    assert result.raw_observation_count == 2
    assert {event["source_record_id"] for event in events} == {"pulse-a", "pulse-b"}
    raw_paths = {
        raw_ref["raw_path"]
        for event in events
        for raw_ref in event["raw_refs"]
    }
    assert raw_paths == {detail_a.as_posix(), detail_b.as_posix()}
    assert manifest["inputs"]["otx_input_policy"] == "run_completed_pulse_details"
    assert manifest["inputs"]["otx_run_dir"] == str(run_dir)
    assert manifest["inputs"]["checkpoint_path"] == str(run_dir / "checkpoint.json")
    assert manifest["inputs"]["saved_files_path"] == str(run_dir / "saved_files.jsonl")
    assert manifest["counts"]["completed_pulse_details"] == 2
    assert manifest["counts"]["resolved_pulse_detail_files"] == 2


def test_otx_downstream_projection_enriches_embedded_indicator_from_endpoint_page(
    tmp_path: Path,
) -> None:
    raw_otx_dir = tmp_path / "raw" / "otx"
    run_dir = tmp_path / "raw" / "otx_collection_runs" / "run-a"
    detail_path = raw_otx_dir / "pulse-a" / "2026-07-04T00-00-00.json"
    indicator_page_path = (
        tmp_path / "raw" / "otx_indicator_page" / "pulse-a" / "2026-07-04T00-00-00.json"
    )

    _write_json(
        detail_path,
        {
            "source": "otx",
            "source_id": "pulse-a",
            "payload": _pulse(
                id="pulse-a",
                indicators=[
                    {
                        "indicator": "evil.example",
                        "type": "domain",
                        "created": "2026-06-01T11:00:00Z",
                    }
                ],
            ),
        },
    )
    _write_json(
        indicator_page_path,
        {
            "source": "otx_indicator_page",
            "source_id": "pulse-a",
            "payload": {
                "results": [
                    {
                        "indicator": "evil.example",
                        "type": "domain",
                        "created": "2026-06-01T11:00:00Z",
                        "false_positive": False,
                        "slug": "evil-example",
                        "pulse_key": "pulse-a:evil.example",
                    }
                ]
            },
        },
    )
    _write_json(run_dir / "checkpoint.json", {"completed_pulse_details": ["pulse-a"]})
    _write_jsonl(
        run_dir / "saved_files.jsonl",
        [
            {"kind": "pulse_detail", "pulse_id": "pulse-a", "raw_ref": {"path": str(detail_path)}},
            {
                "kind": "indicator_page",
                "pulse_id": "pulse-a",
                "raw_ref": {"path": str(indicator_page_path)},
            },
        ],
    )

    build_otx_downstream_projection(
        raw_otx_dir,
        tmp_path / "projection",
        otx_run_dir=run_dir,
    )

    edges = _read_jsonl(tmp_path / "projection" / "edges.jsonl")
    iocs = _read_jsonl(tmp_path / "projection" / "nodes_iocs.jsonl")
    manifest = _read_json(tmp_path / "projection" / "projection_manifest.json")
    coverage = _read_json(tmp_path / "projection" / "indicator_source_coverage.json")

    in_report = [edge for edge in edges if edge["type"] == "InReport"]
    assert len(in_report) == 1
    assert len(iocs) == 1
    assert iocs[0]["value"] == "evil.example"
    assert in_report[0]["properties"]["endpoint_enriched"] is True
    assert in_report[0]["properties"]["endpoint_indicator_observation_count"] == 1
    assert in_report[0]["properties"]["endpoint_indicator_false_positive"] is False
    assert in_report[0]["properties"]["endpoint_indicator_slug"] == "evil-example"
    assert in_report[0]["properties"]["endpoint_indicator_pulse_key"] == "pulse-a:evil.example"
    assert in_report[0]["properties"]["endpoint_raw_refs"] == [
        {
            "connector_source": "otx_indicator_page",
            "fetched_at": None,
            "raw_layout": "rawstore",
            "raw_path": indicator_page_path.as_posix(),
            "raw_sha256": in_report[0]["properties"]["endpoint_raw_refs"][0]["raw_sha256"],
        }
    ]
    assert manifest["artifacts"]["indicator_source_coverage"] == "indicator_source_coverage.json"
    assert coverage["counts"] == {
        "completed_pulses": 1,
        "pulses_with_endpoint_pages": 1,
        "pulses_missing_endpoint_pages": 0,
        "endpoint_count_matches_embedded": 1,
        "endpoint_count_less_than_embedded": 0,
        "endpoint_count_greater_than_embedded": 0,
        "endpoint_count_different_from_embedded": 0,
        "embedded_indicator_observations": 1,
        "endpoint_indicator_observations": 1,
        "endpoint_indicator_matches_embedded": 1,
    }


def test_otx_downstream_projection_keeps_embedded_indicators_when_endpoint_page_missing(
    tmp_path: Path,
) -> None:
    raw_otx_dir = tmp_path / "raw" / "otx"
    run_dir = tmp_path / "raw" / "otx_collection_runs" / "run-a"
    detail_path = raw_otx_dir / "pulse-a" / "2026-07-04T00-00-00.json"

    _write_json(
        detail_path,
        {
            "source": "otx",
            "source_id": "pulse-a",
            "payload": _pulse(
                id="pulse-a",
                indicators=[
                    {
                        "indicator": "missing-endpoint.example",
                        "type": "domain",
                        "created": "2026-06-01T11:00:00Z",
                    }
                ],
            ),
        },
    )
    _write_json(run_dir / "checkpoint.json", {"completed_pulse_details": ["pulse-a"]})
    _write_jsonl(
        run_dir / "saved_files.jsonl",
        [{"kind": "pulse_detail", "pulse_id": "pulse-a", "raw_ref": {"path": str(detail_path)}}],
    )

    build_otx_downstream_projection(
        raw_otx_dir,
        tmp_path / "projection",
        otx_run_dir=run_dir,
    )

    iocs = _read_jsonl(tmp_path / "projection" / "nodes_iocs.jsonl")
    edges = _read_jsonl(tmp_path / "projection" / "edges.jsonl")
    coverage = _read_json(tmp_path / "projection" / "indicator_source_coverage.json")

    in_report = [edge for edge in edges if edge["type"] == "InReport"]
    assert [ioc["value"] for ioc in iocs] == ["missing-endpoint.example"]
    assert len(in_report) == 1
    assert "endpoint_enriched" not in in_report[0]["properties"]
    assert coverage["counts"]["completed_pulses"] == 1
    assert coverage["counts"]["pulses_with_endpoint_pages"] == 0
    assert coverage["counts"]["pulses_missing_endpoint_pages"] == 1
    assert coverage["counts"]["embedded_indicator_observations"] == 1
    assert coverage["counts"]["endpoint_indicator_observations"] == 0


def test_otx_downstream_projection_keeps_embedded_indicators_when_endpoint_count_is_less(
    tmp_path: Path,
) -> None:
    raw_otx_dir = tmp_path / "raw" / "otx"
    run_dir = tmp_path / "raw" / "otx_collection_runs" / "run-a"
    detail_path = raw_otx_dir / "pulse-a" / "2026-07-04T00-00-00.json"
    indicator_page_path = (
        tmp_path / "raw" / "otx_indicator_page" / "pulse-a" / "2026-07-04T00-00-00.json"
    )

    _write_json(
        detail_path,
        {
            "source": "otx",
            "source_id": "pulse-a",
            "payload": _pulse(
                id="pulse-a",
                indicators=[
                    {"indicator": "matched.example", "type": "domain"},
                    {"indicator": "embedded-only.example", "type": "domain"},
                ],
            ),
        },
    )
    _write_json(
        indicator_page_path,
        {
            "source": "otx_indicator_page",
            "source_id": "pulse-a",
            "payload": {"results": [{"indicator": "matched.example", "type": "domain"}]},
        },
    )
    _write_json(run_dir / "checkpoint.json", {"completed_pulse_details": ["pulse-a"]})
    _write_jsonl(
        run_dir / "saved_files.jsonl",
        [
            {"kind": "pulse_detail", "pulse_id": "pulse-a", "raw_ref": {"path": str(detail_path)}},
            {
                "kind": "indicator_page",
                "pulse_id": "pulse-a",
                "raw_ref": {"path": str(indicator_page_path)},
            },
        ],
    )

    build_otx_downstream_projection(
        raw_otx_dir,
        tmp_path / "projection",
        otx_run_dir=run_dir,
    )

    iocs = _read_jsonl(tmp_path / "projection" / "nodes_iocs.jsonl")
    in_report = [
        edge
        for edge in _read_jsonl(tmp_path / "projection" / "edges.jsonl")
        if edge["type"] == "InReport"
    ]
    coverage = _read_json(tmp_path / "projection" / "indicator_source_coverage.json")

    assert {ioc["value"] for ioc in iocs} == {"matched.example", "embedded-only.example"}
    assert len(in_report) == 2
    assert {
        edge["end_value"]: edge["properties"].get("endpoint_enriched", False)
        for edge in in_report
    } == {"matched.example": True, "embedded-only.example": False}
    assert coverage["counts"]["endpoint_count_less_than_embedded"] == 1
    assert coverage["counts"]["endpoint_count_different_from_embedded"] == 1
    assert coverage["counts"]["endpoint_indicator_matches_embedded"] == 1


def test_otx_downstream_projection_does_not_add_endpoint_only_indicator_to_backbone(
    tmp_path: Path,
) -> None:
    raw_otx_dir = tmp_path / "raw" / "otx"
    run_dir = tmp_path / "raw" / "otx_collection_runs" / "run-a"
    detail_path = raw_otx_dir / "pulse-a" / "2026-07-04T00-00-00.json"
    indicator_page_path = (
        tmp_path / "raw" / "otx_indicator_page" / "pulse-a" / "2026-07-04T00-00-00.json"
    )

    _write_json(
        detail_path,
        {
            "source": "otx",
            "source_id": "pulse-a",
            "payload": _pulse(id="pulse-a", indicators=[]),
        },
    )
    _write_json(
        indicator_page_path,
        {
            "source": "otx_indicator_page",
            "source_id": "pulse-a",
            "payload": {"results": [{"indicator": "endpoint-only.example", "type": "domain"}]},
        },
    )
    _write_json(run_dir / "checkpoint.json", {"completed_pulse_details": ["pulse-a"]})
    _write_jsonl(
        run_dir / "saved_files.jsonl",
        [
            {"kind": "pulse_detail", "pulse_id": "pulse-a", "raw_ref": {"path": str(detail_path)}},
            {
                "kind": "indicator_page",
                "pulse_id": "pulse-a",
                "raw_ref": {"path": str(indicator_page_path)},
            },
        ],
    )

    build_otx_downstream_projection(
        raw_otx_dir,
        tmp_path / "projection",
        otx_run_dir=run_dir,
    )

    iocs = _read_jsonl(tmp_path / "projection" / "nodes_iocs.jsonl")
    edges = _read_jsonl(tmp_path / "projection" / "edges.jsonl")
    coverage = _read_json(tmp_path / "projection" / "indicator_source_coverage.json")

    assert iocs == []
    assert [edge for edge in edges if edge["type"] == "InReport"] == []
    assert coverage["counts"]["embedded_indicator_observations"] == 0
    assert coverage["counts"]["endpoint_indicator_observations"] == 1
    assert coverage["counts"]["endpoint_count_greater_than_embedded"] == 1
    assert coverage["counts"]["endpoint_indicator_matches_embedded"] == 0


def test_otx_downstream_projection_fails_when_completed_run_pulse_detail_is_missing(
    tmp_path: Path,
) -> None:
    raw_otx_dir = tmp_path / "raw" / "otx"
    run_dir = tmp_path / "raw" / "otx_collection_runs" / "run-a"
    present_detail = raw_otx_dir / "pulse-present" / "2026-07-04T00-00-00.json"

    _write_json(
        present_detail,
        {"source": "otx", "source_id": "pulse-present", "payload": _pulse(id="pulse-present")},
    )
    _write_json(
        run_dir / "checkpoint.json",
        {"completed_pulse_details": ["pulse-present", "pulse-missing"]},
    )
    _write_jsonl(
        run_dir / "saved_files.jsonl",
        [
            {
                "kind": "pulse_detail",
                "pulse_id": "pulse-present",
                "raw_ref": {"path": str(present_detail)},
            },
        ],
    )

    with pytest.raises(ValueError, match="pulse-missing"):
        build_otx_downstream_projection(
            raw_otx_dir,
            tmp_path / "projection",
            otx_run_dir=run_dir,
        )


def test_build_otx_downstream_projection_cli_passes_run_dir_and_mitre_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_build_script()
    raw_otx_dir = tmp_path / "raw" / "otx"
    raw_otx_dir.mkdir(parents=True)
    run_dir = tmp_path / "raw" / "otx_collection_runs" / "run-a"
    run_dir.mkdir(parents=True)
    mitre_path = tmp_path / "mitre" / "enterprise-attack.json"
    _write_json(mitre_path, {"type": "bundle", "objects": []})
    output_dir = tmp_path / "projection"
    received: dict[str, Any] = {}

    def fake_build_otx_downstream_projection(
        raw_arg: Path,
        output_arg: Path,
        **kwargs: Any,
    ) -> SimpleNamespace:
        received["raw_otx_dir"] = raw_arg
        received["output_dir"] = output_arg
        received.update(kwargs)
        return SimpleNamespace(
            output_dir=output_arg,
            event_count=0,
            ioc_count=0,
            edge_count=0,
            raw_observation_count=0,
            raw_layouts={},
        )

    monkeypatch.setattr(script, "build_otx_downstream_projection", fake_build_otx_downstream_projection)
    monkeypatch.setattr(
        script.sys,
        "argv",
        [
            "build_otx_downstream_projection.py",
            "--raw-otx-dir",
            str(raw_otx_dir),
            "--otx-run-dir",
            str(run_dir),
            "--mitre-attack-path",
            str(mitre_path),
            "--output-dir",
            str(output_dir),
            "--no-pdns",
        ],
    )

    script.main()

    assert received["raw_otx_dir"] == raw_otx_dir
    assert received["output_dir"] == output_dir
    assert received["otx_run_dir"] == run_dir
    assert received["mitre_attack_path"] == mitre_path
    assert received["pdns_raw_dir"] is None


def test_otx_downstream_projection_reads_flat_and_rawstore_records(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "pulse-1.json", _pulse(id="pulse-1"))
    _write_json(
        raw_dir / "pulse-2" / "2026-07-02T22-49-02.640621+00-00.json",
        {
            "source": "otx",
            "source_id": "pulse-2",
            "fetched_at": "2026-07-02T22:49:02.640621+00:00",
            "payload": _pulse(
                id="pulse-2",
                adversary="Example Panda",
                indicators=[
                    {
                        "indicator": "203.0.113.99/path",
                        "type": "URL",
                        "created": "2026-07-02T22:00:00Z",
                    }
                ],
            ),
        },
    )
    mitre_path = _write_mitre_bundle(
        tmp_path / "mitre" / "enterprise-attack.json",
        [
            _mitre_actor(
                stix_id="intrusion-set--11111111-1111-4111-8111-111111111111",
                name="APT28",
                attack_id="G0007",
                aliases=["APT28"],
            ),
            _mitre_actor(
                stix_id="intrusion-set--22222222-2222-4222-8222-222222222222",
                name="APT29",
                attack_id="G0016",
                aliases=["APT29"],
            ),
        ],
    )

    result = build_otx_downstream_projection(raw_dir, tmp_path / "projection", mitre_attack_path=mitre_path)

    assert result.event_count == 2
    assert result.raw_observation_count == 2

    events = _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")
    iocs = _read_jsonl(tmp_path / "projection" / "nodes_iocs.jsonl")
    edges = _read_jsonl(tmp_path / "projection" / "edges.jsonl")
    manifest = _read_json(tmp_path / "projection" / "projection_manifest.json")

    event_by_source_id = {event["source_record_id"]: event for event in events}
    assert set(event_by_source_id) == {"pulse-1", "pulse-2"}
    assert event_by_source_id["pulse-1"]["apt"] is None
    assert event_by_source_id["pulse-1"]["actor_labels"] == ["APT28", "APT29"]
    assert event_by_source_id["pulse-1"]["actor_label_status"] == "resolved_multi_actor"
    assert "occurrence_count" not in event_by_source_id["pulse-1"]
    assert "disagreement" not in event_by_source_id["pulse-1"]
    assert event_by_source_id["pulse-1"]["source_contributor"]["author_name"] == "OTX Contributor"
    assert "OTX Contributor" not in event_by_source_id["pulse-1"]["actor_labels"]
    assert event_by_source_id["pulse-2"]["apt"] is None
    assert event_by_source_id["pulse-2"]["initial_labels"] == ["Example Panda"]
    assert event_by_source_id["pulse-2"]["actor_labels"] == []
    assert event_by_source_id["pulse-2"]["actor_label_status"] == "unmapped_actor_like"
    assert event_by_source_id["pulse-2"]["raw_refs"][0]["raw_layout"] == "rawstore"

    iocs_by_value = {ioc["value"]: ioc for ioc in iocs}
    assert iocs_by_value["evil.example"]["labels"] == ["Domain"]
    assert iocs_by_value["203.0.113.10"]["labels"] == ["IP"]
    assert iocs_by_value["https://evil.example/a"]["labels"] == ["URL"]

    in_report = [
        edge for edge in edges if edge["type"] == "InReport" and edge["end_value"] == "evil.example"
    ]
    assert in_report[0]["properties"]["indicator_created"] == "2026-06-01T11:00:00Z"
    assert in_report[0]["properties"]["source"] == "otx"

    hosted_on = [edge for edge in edges if edge["type"] == "HostedOn"]
    assert hosted_on
    assert hosted_on[0]["start_value"] == "https://evil.example/a"
    assert hosted_on[0]["end_value"] == "evil.example"

    url_to_ip = [edge for edge in edges if edge["type"] == "ResolvesTo"]
    assert any(edge["start_value"] == "203.0.113.99/path" for edge in url_to_ip)
    assert not any(
        edge["start_label"] == "Domain" and edge["type"] == "ResolvesTo" for edge in edges
    )
    assert manifest["counts"]["raw_layouts"] == {"flat": 1, "rawstore": 1}


def test_otx_downstream_projection_aggregates_duplicate_raw_observations_by_pulse(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "pulse-1.json", _pulse(id="pulse-1", adversary="APT28"))
    _write_json(
        raw_dir / "pulse-1" / "2026-07-02T22-49-02.640621+00-00.json",
        {
            "source": "otx",
            "source_id": "pulse-1",
            "fetched_at": "2026-07-02T22:49:02.640621+00:00",
            "payload": _pulse(id="pulse-1", adversary="APT29"),
        },
    )
    mitre_path = _write_mitre_bundle(
        tmp_path / "mitre" / "enterprise-attack.json",
        [
            _mitre_actor(
                stix_id="intrusion-set--22222222-2222-4222-8222-222222222222",
                name="APT29",
                attack_id="G0016",
                aliases=["APT29"],
            )
        ],
    )

    result = build_otx_downstream_projection(raw_dir, tmp_path / "projection", mitre_attack_path=mitre_path)

    events = _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")
    assert result.event_count == 1
    assert result.raw_observation_count == 2
    assert events[0]["source_record_id"] == "pulse-1"
    assert events[0]["raw_observation_count"] == 2
    assert {ref["raw_layout"] for ref in events[0]["raw_refs"]} == {"flat", "rawstore"}
    assert events[0]["actor_labels"] == ["APT29"]
    assert events[0]["apt"] == "APT29"


def test_otx_downstream_projection_can_add_forward_pdns_enrichment(
    tmp_path: Path,
) -> None:
    raw_otx_dir = tmp_path / "raw" / "otx"
    raw_pdns_dir = tmp_path / "raw" / "pdns"
    _write_json(
        raw_otx_dir / "pulse-1.json",
        _pulse(
            id="pulse-1",
            indicators=[{"indicator": "evil.example", "type": "domain"}],
        ),
    )
    _write_json(
        raw_pdns_dir / "evil.example" / "2026-06-15T23-33-16.707732+00-00.json",
        {
            "source": "pdns",
            "source_id": "evil.example",
            "fetched_at": "2026-06-15T23:33:16.707732+00:00",
            "payload": {
                "passive_dns": [
                    {
                        "address": "203.0.113.10",
                        "asn": "AS64500 example hosting",
                        "first": "2024-01-01T00:00:00",
                        "hostname": "evil.example",
                        "last": "2026-06-01T00:00:00",
                        "record_type": "A",
                    },
                    {
                        "address": "ns1.example.net",
                        "hostname": "evil.example",
                        "record_type": "NS",
                    },
                ],
            },
        },
    )

    build_otx_downstream_projection(
        raw_otx_dir,
        tmp_path / "projection",
        pdns_raw_dir=raw_pdns_dir,
    )

    iocs = _read_jsonl(tmp_path / "projection" / "nodes_iocs.jsonl")
    edges = _read_jsonl(tmp_path / "projection" / "edges.jsonl")
    manifest = _read_json(tmp_path / "projection" / "projection_manifest.json")

    iocs_by_value = {ioc["value"]: ioc for ioc in iocs}
    assert iocs_by_value["203.0.113.10"]["labels"] == ["IP"]
    assert iocs_by_value["AS64500"]["labels"] == ["ASN"]

    domain_to_ip = [
        edge
        for edge in edges
        if edge["type"] == "ResolvesTo"
        and edge["start_label"] == "Domain"
        and edge["start_value"] == "evil.example"
    ]
    assert len(domain_to_ip) == 1
    assert domain_to_ip[0]["end_value"] == "203.0.113.10"
    assert domain_to_ip[0]["properties"]["source"] == "pdns"
    assert domain_to_ip[0]["properties"]["first_seen"] == "2024-01-01T00:00:00"
    assert domain_to_ip[0]["properties"]["last_seen"] == "2026-06-01T00:00:00"
    assert domain_to_ip[0]["properties"]["duration_days"] == 882

    ip_to_asn = [
        edge for edge in edges if edge["type"] == "InGroup" and edge["start_value"] == "203.0.113.10"
    ]
    assert len(ip_to_asn) == 1
    assert ip_to_asn[0]["end_value"] == "AS64500"
    assert not any(edge["end_value"] == "ns1.example.net" for edge in edges)
    assert manifest["counts"]["pdns_forward_records"] == 1


def test_otx_downstream_projection_writes_time_feature_coverage(
    tmp_path: Path,
) -> None:
    raw_otx_dir = tmp_path / "raw" / "otx"
    raw_pdns_dir = tmp_path / "raw" / "pdns"
    _write_json(
        raw_otx_dir / "pulse-1.json",
        _pulse(
            id="pulse-1",
            created="2026-06-01T10:00:00Z",
            modified="",
            indicators=[
                {
                    "indicator": "evil.example",
                    "type": "domain",
                    "created": "2026-06-01T11:00:00Z",
                },
                {"indicator": "203.0.113.10", "type": "IPv4"},
            ],
        ),
    )
    _write_json(
        raw_pdns_dir / "evil.example" / "2026-06-15T23-33-16.707732+00-00.json",
        {
            "source": "pdns",
            "source_id": "evil.example",
            "fetched_at": "2026-06-15T23:33:16.707732+00:00",
            "payload": {
                "passive_dns": [
                    {
                        "address": "203.0.113.10",
                        "first": "2024-01-01T00:00:00",
                        "hostname": "evil.example",
                        "last": "2026-06-01T00:00:00",
                        "record_type": "A",
                    }
                ],
            },
        },
    )

    build_otx_downstream_projection(
        raw_otx_dir,
        tmp_path / "projection",
        pdns_raw_dir=raw_pdns_dir,
    )

    manifest = _read_json(tmp_path / "projection" / "projection_manifest.json")
    coverage = _read_json(tmp_path / "projection" / "time_feature_coverage.json")

    assert manifest["artifacts"]["time_feature_coverage"] == "time_feature_coverage.json"
    assert coverage["event_time_features"]["pulse_created"]["present"] == 1
    assert coverage["event_time_features"]["pulse_modified"]["present"] == 0
    assert coverage["in_report_edge_time_features"]["indicator_created"]["total"] == 2
    assert coverage["in_report_edge_time_features"]["indicator_created"]["present"] == 1
    assert coverage["infrastructure_edge_time_features"]["pdns_domain_resolves_to_ip"] == {
        "total": 1,
        "first_seen_present": 1,
        "last_seen_present": 1,
        "duration_days_present": 1,
        "source": "pdns",
        "source_fields": {
            "first_seen": "passive_dns[].first",
            "last_seen": "passive_dns[].last",
        },
    }


def test_otx_downstream_projection_writes_actor_label_summary(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "multi.json", _pulse(id="multi", adversary="APT28, APT29"))
    _write_json(raw_dir / "single.json", _pulse(id="single", adversary="APT32"))
    _write_json(raw_dir / "missing.json", _pulse(id="missing", adversary=""))
    mitre_path = _write_mitre_bundle(
        tmp_path / "mitre" / "enterprise-attack.json",
        [
            _mitre_actor(
                stix_id="intrusion-set--11111111-1111-4111-8111-111111111111",
                name="APT28",
                attack_id="G0007",
                aliases=["APT28"],
            ),
            _mitre_actor(
                stix_id="intrusion-set--22222222-2222-4222-8222-222222222222",
                name="APT29",
                attack_id="G0016",
                aliases=["APT29"],
            ),
            _mitre_actor(
                stix_id="intrusion-set--33333333-3333-4333-8333-333333333333",
                name="APT32",
                attack_id="G0050",
                aliases=["APT32"],
            ),
        ],
    )

    build_otx_downstream_projection(raw_dir, tmp_path / "projection", mitre_attack_path=mitre_path)

    manifest = _read_json(tmp_path / "projection" / "projection_manifest.json")
    summary = _read_json(tmp_path / "projection" / "actor_label_summary.json")

    assert manifest["artifacts"]["actor_label_summary"] == "actor_label_summary.json"
    assert summary["counts"] == {
        "events": 3,
        "single_actor": 1,
        "multi_actor": 1,
        "missing_actor": 1,
    }
    assert summary["multi_actor_events"] == [
        {
            "event_id": "otx:pulse:multi",
            "source_record_id": "multi",
            "actor_label_raw": "APT28, APT29",
            "actor_labels": ["APT28", "APT29"],
        }
    ]
    assert summary["actor_label_counts"] == {
        "APT28": 1,
        "APT29": 1,
        "APT32": 1,
    }


def test_otx_downstream_projection_writes_adversary_label_claims_in_source_order(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "pulse-1.json", _pulse(id="pulse-1", adversary="APT32, APT-C-00"))
    mitre_path = _write_mitre_bundle(
        tmp_path / "mitre" / "enterprise-attack.json",
        [
            _mitre_actor(
                stix_id="intrusion-set--11111111-1111-4111-8111-111111111111",
                name="APT32",
                attack_id="G0050",
                aliases=["APT32", "APT-C-00", "OceanLotus"],
            )
        ],
    )

    build_otx_downstream_projection(raw_dir, tmp_path / "projection", mitre_attack_path=mitre_path)

    manifest = _read_json(tmp_path / "projection" / "projection_manifest.json")
    events = _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")
    claims = _read_jsonl(tmp_path / "projection" / "actor_label_claims.jsonl")
    actors = _read_jsonl(tmp_path / "projection" / "nodes_actors.jsonl")
    edges = _read_jsonl(tmp_path / "projection" / "edges.jsonl")

    assert manifest["artifacts"]["actor_label_claims"] == "actor_label_claims.jsonl"
    assert manifest["artifacts"]["actors"] == "nodes_actors.jsonl"
    assert events[0]["actor_labels"] == ["APT32"]
    assert events[0]["initial_labels"] == ["APT32", "APT-C-00"]
    assert events[0]["apt"] == "APT32"
    assert events[0]["actor_label_status"] == "resolved_alias_collapsed"
    assert [actor["actor_id"] for actor in actors] == ["actor_G0050"]
    actor_required_keys = {
        "node_id",
        "node_kind",
        "labels",
        "actor_id",
        "actor_name",
        "taxonomy",
        "taxonomy_id",
        "stix_id",
        "aliases",
        "taxonomy_ref",
        "modified",
        "revoked",
        "deprecated",
    }
    claim_required_keys = {
        "claim_id",
        "event_id",
        "source",
        "source_record_id",
        "source_field",
        "raw_field_value",
        "raw_label",
        "normalized_label",
        "label_index",
        "parse_status",
        "resolution_status",
        "resolved_actor_ids",
        "candidate_actor_ids",
        "match_method",
        "matched_taxonomy_labels",
        "resolution_taxonomy",
        "taxonomy_version",
        "contributes_to_attribution",
        "raw_refs",
        "notes",
    }
    attributed_to_required_properties = {
        "source",
        "source_field",
        "attribution_kind",
        "claim_ids",
        "raw_labels",
        "resolution_taxonomy",
        "resolver_policy_version",
        "raw_refs",
    }
    attributed_to_edges = [edge for edge in edges if edge["type"] == "AttributedTo"]
    assert all(actor_required_keys <= actor.keys() for actor in actors)
    assert all(claim_required_keys <= claim.keys() for claim in claims)
    assert len(attributed_to_edges) == 1
    assert attributed_to_edges[0]["end_node_id"] == "actor_G0050"
    assert attributed_to_required_properties <= attributed_to_edges[0]["properties"].keys()
    assert attributed_to_edges[0]["properties"]["claim_ids"] == [
        claim["claim_id"] for claim in claims
    ]
    assert attributed_to_edges[0]["properties"]["raw_labels"] == ["APT32", "APT-C-00"]
    assert attributed_to_edges[0]["edge_id"] == contract_id(
        "otx_edge",
        ("otx:pulse:pulse-1", "AttributedTo", "actor_G0050", "adversary"),
    )
    assert attributed_to_edges[0]["edge_id"] != contract_id(
        "otx_edge",
        ("otx:pulse:pulse-1", "AttributedTo", "actor_G0050", claims[0]["claim_id"]),
    )
    assert [
        {
            "raw_label": claim["raw_label"],
            "normalized_label": claim["normalized_label"],
            "label_index": claim["label_index"],
            "parse_status": claim["parse_status"],
            "source": claim["source"],
            "raw_refs_present": bool(claim["raw_refs"]),
            "resolution_status": claim["resolution_status"],
            "resolved_actor_ids": claim["resolved_actor_ids"],
            "match_method": claim["match_method"],
            "matched_taxonomy_labels": claim["matched_taxonomy_labels"],
            "resolution_taxonomy": claim["resolution_taxonomy"],
            "contributes_to_attribution": claim["contributes_to_attribution"],
        }
        for claim in claims
    ] == [
        {
            "raw_label": "APT32",
            "normalized_label": "apt32",
            "label_index": 0,
            "parse_status": "parsed",
            "source": "otx",
            "raw_refs_present": True,
            "resolution_status": "resolved",
            "resolved_actor_ids": ["actor_G0050"],
            "match_method": "mitre_exact_name",
            "matched_taxonomy_labels": ["APT32"],
            "resolution_taxonomy": "mitre-attack-enterprise",
            "contributes_to_attribution": True,
        },
        {
            "raw_label": "APT-C-00",
            "normalized_label": "apt-c-00",
            "label_index": 1,
            "parse_status": "parsed",
            "source": "otx",
            "raw_refs_present": True,
            "resolution_status": "resolved",
            "resolved_actor_ids": ["actor_G0050"],
            "match_method": "mitre_exact_alias",
            "matched_taxonomy_labels": ["APT-C-00"],
            "resolution_taxonomy": "mitre-attack-enterprise",
            "contributes_to_attribution": True,
        },
    ]


def test_otx_downstream_projection_splits_actor_and_but_not_parenthetical_and(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "and.json", _pulse(id="and", adversary="Kimsuky and Andariel"))
    _write_json(
        raw_dir / "parenthetical.json",
        _pulse(id="parenthetical", adversary="MOIS (Ministry of Intelligence and Security)"),
    )
    mitre_path = _write_mitre_bundle(
        tmp_path / "mitre" / "enterprise-attack.json",
        [
            _mitre_actor(
                stix_id="intrusion-set--11111111-1111-4111-8111-111111111111",
                name="Kimsuky",
                attack_id="G0094",
                aliases=["Kimsuky"],
            ),
            _mitre_actor(
                stix_id="intrusion-set--22222222-2222-4222-8222-222222222222",
                name="Andariel",
                attack_id="G0138",
                aliases=["Andariel"],
            ),
        ],
    )

    build_otx_downstream_projection(raw_dir, tmp_path / "projection", mitre_attack_path=mitre_path)

    events = {
        event["source_record_id"]: event
        for event in _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")
    }
    claims_by_event = {
        event_id: [claim for claim in _read_jsonl(tmp_path / "projection" / "actor_label_claims.jsonl") if claim["source_record_id"] == event_id]
        for event_id in ("and", "parenthetical")
    }

    assert events["and"]["actor_labels"] == ["Kimsuky", "Andariel"]
    assert events["and"]["apt"] is None
    assert events["and"]["actor_label_status"] == "resolved_multi_actor"
    assert [claim["raw_label"] for claim in claims_by_event["and"]] == ["Kimsuky", "Andariel"]
    assert events["parenthetical"]["initial_labels"] == [
        "MOIS (Ministry of Intelligence and Security)"
    ]
    assert events["parenthetical"]["actor_labels"] == []
    assert events["parenthetical"]["apt"] is None
    assert events["parenthetical"]["actor_label_status"] == "unmapped_actor_like"
    assert [claim["raw_label"] for claim in claims_by_event["parenthetical"]] == [
        "MOIS (Ministry of Intelligence and Security)"
    ]


def test_otx_downstream_projection_preserves_mitre_alias_ambiguity_as_claim_only(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "ambiguous.json", _pulse(id="ambiguous", adversary="UAC-0056"))
    mitre_path = _write_mitre_bundle(
        tmp_path / "mitre" / "enterprise-attack.json",
        [
            _mitre_actor(
                stix_id="intrusion-set--11111111-1111-4111-8111-111111111111",
                name="Actor One",
                attack_id="G1001",
                aliases=["Actor One", "UAC-0056"],
            ),
            _mitre_actor(
                stix_id="intrusion-set--22222222-2222-4222-8222-222222222222",
                name="Actor Two",
                attack_id="G1002",
                aliases=["Actor Two", "UAC-0056"],
            ),
        ],
    )

    build_otx_downstream_projection(raw_dir, tmp_path / "projection", mitre_attack_path=mitre_path)

    event = _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")[0]
    claims = _read_jsonl(tmp_path / "projection" / "actor_label_claims.jsonl")
    actors = _read_jsonl(tmp_path / "projection" / "nodes_actors.jsonl")
    edges = _read_jsonl(tmp_path / "projection" / "edges.jsonl")

    assert event["initial_labels"] == ["UAC-0056"]
    assert event["actor_labels"] == []
    assert event["apt"] is None
    assert event["actor_label_status"] == "ambiguous_taxonomy"
    assert actors == []
    assert [edge for edge in edges if edge["type"] == "AttributedTo"] == []
    assert claims[0]["resolution_status"] == "ambiguous_taxonomy"
    assert claims[0]["candidate_actor_ids"] == ["actor_G1001", "actor_G1002"]
    assert claims[0]["resolved_actor_ids"] == []
    assert claims[0]["contributes_to_attribution"] is False


def test_otx_downstream_projection_does_not_expand_unmapped_actor_like_labels(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "blind.json", _pulse(id="blind", adversary="BlindEagle"))
    _write_json(raw_dir / "apt28.json", _pulse(id="apt28", adversary="APT 28"))
    mitre_path = _write_mitre_bundle(
        tmp_path / "mitre" / "enterprise-attack.json",
        [
            _mitre_actor(
                stix_id="intrusion-set--11111111-1111-4111-8111-111111111111",
                name="APT-C-36",
                attack_id="G0099",
                aliases=["APT-C-36", "Blind Eagle"],
            ),
            _mitre_actor(
                stix_id="intrusion-set--22222222-2222-4222-8222-222222222222",
                name="APT28",
                attack_id="G0007",
                aliases=["APT28"],
            ),
        ],
    )

    build_otx_downstream_projection(raw_dir, tmp_path / "projection", mitre_attack_path=mitre_path)

    events = {
        event["source_record_id"]: event
        for event in _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")
    }
    claims = _read_jsonl(tmp_path / "projection" / "actor_label_claims.jsonl")
    actors = _read_jsonl(tmp_path / "projection" / "nodes_actors.jsonl")
    edges = _read_jsonl(tmp_path / "projection" / "edges.jsonl")

    assert events["blind"]["initial_labels"] == ["BlindEagle"]
    assert events["apt28"]["initial_labels"] == ["APT 28"]
    assert events["blind"]["actor_labels"] == []
    assert events["apt28"]["actor_labels"] == []
    assert events["blind"]["actor_label_status"] == "unmapped_actor_like"
    assert events["apt28"]["actor_label_status"] == "unmapped_actor_like"
    assert actors == []
    assert [edge for edge in edges if edge["type"] == "AttributedTo"] == []
    assert {
        claim["raw_label"]: (
            claim["resolution_status"],
            claim["resolved_actor_ids"],
            claim["candidate_actor_ids"],
            claim["contributes_to_attribution"],
        )
        for claim in claims
    } == {
        "APT 28": ("unmapped_actor_like", [], [], False),
        "BlindEagle": ("unmapped_actor_like", [], [], False),
    }


def test_otx_downstream_projection_preserves_url_like_adversary_as_non_attributing_claim(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    url_value = "https://example.test/report/APT32/OceanLotus"
    _write_json(raw_dir / "url.json", _pulse(id="url", adversary=url_value))

    build_otx_downstream_projection(raw_dir, tmp_path / "projection")

    event = _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")[0]
    claims = _read_jsonl(tmp_path / "projection" / "actor_label_claims.jsonl")

    assert event["actor_labels"] == []
    assert event["apt"] is None
    assert event["actor_label_status"] == "non_attributing"
    assert len(claims) == 1
    assert claims[0]["raw_field_value"] == url_value
    assert claims[0]["raw_label"] == url_value
    assert claims[0]["parse_status"] == "non_actor_value"
    assert claims[0]["contributes_to_attribution"] is False


def test_otx_downstream_projection_preserves_advisory_category_as_non_attributing_claim(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "advisory.json", _pulse(id="advisory", adversary="Malware Advisory"))

    build_otx_downstream_projection(raw_dir, tmp_path / "projection")

    event = _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")[0]
    claims = _read_jsonl(tmp_path / "projection" / "actor_label_claims.jsonl")

    assert event["actor_labels"] == []
    assert event["actor_label_status"] == "non_attributing"
    assert [(claim["raw_label"], claim["parse_status"], claim["contributes_to_attribution"]) for claim in claims] == [
        ("Malware Advisory", "non_actor_value", False)
    ]


def test_otx_downstream_projection_marks_ambiguous_slash_adversary_without_expanding_it(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    raw_value = "APT 28/29 - too much time too many problems"
    _write_json(raw_dir / "ambiguous.json", _pulse(id="ambiguous", adversary=raw_value))

    build_otx_downstream_projection(raw_dir, tmp_path / "projection")

    event = _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")[0]
    claims = _read_jsonl(tmp_path / "projection" / "actor_label_claims.jsonl")

    assert event["actor_labels"] == []
    assert event["apt"] is None
    assert event["actor_label_status"] == "parse_ambiguous"
    assert len(claims) == 1
    assert claims[0]["raw_label"] == raw_value
    assert claims[0]["parse_status"] == "parse_ambiguous"
    assert claims[0]["contributes_to_attribution"] is False


def test_otx_downstream_projection_preserves_company_adversary_as_non_attributing_claim(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    raw_value = "Shenzhen Haimaiyunxiang Media Co., Ltd."
    _write_json(raw_dir / "company.json", _pulse(id="company", adversary=raw_value))

    build_otx_downstream_projection(raw_dir, tmp_path / "projection")

    event = _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")[0]
    claims = _read_jsonl(tmp_path / "projection" / "actor_label_claims.jsonl")

    assert event["actor_labels"] == []
    assert event["apt"] is None
    assert event["actor_label_status"] == "non_attributing"
    assert len(claims) == 1
    assert claims[0]["raw_label"] == raw_value
    assert claims[0]["parse_status"] == "non_actor_value"
    assert claims[0]["contributes_to_attribution"] is False


def test_otx_downstream_projection_splits_clean_slash_actor_pair(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "slash.json", _pulse(id="slash", adversary="APT32/OceanLotus"))
    mitre_path = _empty_mitre_bundle(tmp_path)

    build_otx_downstream_projection(raw_dir, tmp_path / "projection", mitre_attack_path=mitre_path)

    event = _read_jsonl(tmp_path / "projection" / "nodes_events.jsonl")[0]
    claims = _read_jsonl(tmp_path / "projection" / "actor_label_claims.jsonl")

    assert event["initial_labels"] == ["APT32", "OceanLotus"]
    assert event["actor_labels"] == []
    assert event["apt"] is None
    assert event["actor_label_status"] == "unmapped_actor_like"
    assert [
        (
            claim["raw_label"],
            claim["label_index"],
            claim["parse_status"],
            claim["contributes_to_attribution"],
        )
        for claim in claims
    ] == [
        ("APT32", 0, "parsed", False),
        ("OceanLotus", 1, "parsed", False),
    ]


def test_otx_downstream_projection_writes_acceptance_lint_with_fail_handles(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "pulse-1.json", _pulse(id="pulse-1"))

    build_otx_downstream_projection(raw_dir, tmp_path / "projection")

    manifest = _read_json(tmp_path / "projection" / "projection_manifest.json")
    lint = _read_json(tmp_path / "projection" / "acceptance_lint.json")

    assert manifest["artifacts"]["acceptance_lint"] == "acceptance_lint.json"
    assert lint["ok"] is True
    assert lint["counts"]["fail"] == 0
    assert lint["counts"]["warn"] == 0
    assert lint["counts"]["report"] >= 1
    for finding in lint["findings"]:
        assert {"check_id", "severity", "message", "impact", "handle"} <= finding.keys()
        assert {
            "next_step",
            "likely_causes",
            "do_not",
        } <= finding["handle"].keys()


def test_otx_downstream_lint_reports_actionable_failure_for_broken_edge_join(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "pulse-1.json", _pulse(id="pulse-1"))
    build_otx_downstream_projection(raw_dir, tmp_path / "projection")
    edge_path = tmp_path / "projection" / "edges.jsonl"
    edges = _read_jsonl(edge_path)
    edges[0]["end_node_id"] = "missing-node"
    edge_path.write_text("\n".join(json.dumps(edge, sort_keys=True) for edge in edges) + "\n")

    lint = lint_otx_downstream_projection(tmp_path / "projection")

    assert lint["ok"] is False
    failure = next(finding for finding in lint["findings"] if finding["check_id"] == "edge_endpoint_missing")
    assert failure["severity"] == "fail"
    assert failure["artifact"] == "edges.jsonl"
    assert failure["failed_examples"][0]["missing_node_id"] == "missing-node"
    assert "fix node emission/id normalization" in failure["handle"]["next_step"]
    assert "do not create placeholder nodes without raw_refs" in failure["handle"]["do_not"]


def test_otx_downstream_lint_fails_reverse_pdns_shape_with_policy_handle(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "pulse-1.json", _pulse(id="pulse-1"))
    build_otx_downstream_projection(raw_dir, tmp_path / "projection")
    edge_path = tmp_path / "projection" / "edges.jsonl"
    edges = _read_jsonl(edge_path)
    edges.append(
        {
            "edge_id": "bad-reverse",
            "type": "ResolvesTo",
            "start_node_id": "otx_ioc_a",
            "end_node_id": "otx_ioc_b",
            "start_label": "IP",
            "end_label": "Domain",
            "start_value": "203.0.113.10",
            "end_value": "evil.example",
            "properties": {"source": "pdns", "raw_refs": edges[0]["properties"]["raw_refs"]},
        }
    )
    edge_path.write_text("\n".join(json.dumps(edge, sort_keys=True) for edge in edges) + "\n")

    lint = lint_otx_downstream_projection(tmp_path / "projection")

    failure = next(finding for finding in lint["findings"] if finding["check_id"] == "reverse_pdns_detected")
    assert lint["ok"] is False
    assert failure["severity"] == "fail"
    assert "policy explicitly excludes reverse pDNS" in failure["impact"]
    assert "do not relabel reverse pDNS edges as forward resolution" in failure["handle"]["do_not"]


def test_otx_downstream_lint_fails_manifest_count_mismatch_with_regeneration_handle(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw" / "otx"
    _write_json(raw_dir / "pulse-1.json", _pulse(id="pulse-1"))
    build_otx_downstream_projection(raw_dir, tmp_path / "projection")
    manifest_path = tmp_path / "projection" / "projection_manifest.json"
    manifest = _read_json(manifest_path)
    manifest["counts"]["edges"] += 1
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    lint = lint_otx_downstream_projection(tmp_path / "projection")

    failure = next(
        finding for finding in lint["findings"] if finding["check_id"] == "manifest_count_mismatch"
    )
    assert lint["ok"] is False
    assert failure["failed_examples"][0]["edges"]["actual"] != failure["failed_examples"][0]["edges"]["manifest"]
    assert "Regenerate the projection manifest" in failure["handle"]["next_step"]
    assert "do not manually edit counts without regenerating artifacts" in failure["handle"]["do_not"]
