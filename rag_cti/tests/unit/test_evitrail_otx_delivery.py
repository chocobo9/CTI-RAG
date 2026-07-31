from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
from pathlib import Path

import pytest

from rag_cti.evitrail_delivery.otx import build_otx_delivery


def _evitrail_root() -> Path:
    configured = os.environ.get("EVITRAIL_ROOT")
    root = (
        Path(configured).resolve()
        if configured
        else (
            Path(__file__).resolve().parents[2]
            / "tmp"
            / "evitrial-delivery-builder-20260727"
        )
    )
    if not (root / "evitrail").is_dir():
        pytest.skip(
            "set EVITRAIL_ROOT to run exact-current-consumer integration checks"
        )
    return root


def _write_wrapper(root: Path, pulse_id: str, fetched_at: str, payload: dict) -> Path:
    path = root / pulse_id / f"{fetched_at.replace(':', '-')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "fetched_at": fetched_at,
                "payload": {"id": pulse_id, **payload},
                "source": "otx",
                "source_id": pulse_id,
            }
        ),
        encoding="utf-8",
    )
    return path


def _rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_delivery_preserves_pulse_clocks_metadata_and_direct_attribution(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    raw_path = _write_wrapper(
        raw_root,
        "pulse-1",
        "2026-07-28T22:20:47+00:00",
        {
            "name": "Source pulse",
            "description": "Original narrative",
            "created": "2024-01-02T03:04:05",
            "modified": "2024-02-03T04:05:06",
            "adversary": "APT28",
            "tags": ["APT28", "phishing"],
            "references": ["https://example.test/report"],
            "indicators": [
                {
                    "type": "URL",
                    "indicator": "https://bad.example/drop",
                    "created": "2024-01-03T00:00:00",
                }
            ],
        },
    )
    before = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    output = tmp_path / "delivery"

    result = build_otx_delivery(raw_root, output)

    assert result.event_count == 1
    handoff = result.handoff_dirs[0]
    assert {
        "nodes.jsonl",
        "edges.jsonl",
        "events.jsonl",
        "source_claims.jsonl",
        "rejected_records.jsonl",
    }.issubset(path.name for path in handoff.iterdir())
    event = _rows(handoff / "events.jsonl")[0]
    assert event["created"] == "2024-01-02T03:04:05"
    assert event["modified"] == "2024-02-03T04:05:06"
    assert event["fetched_at"] == "2026-07-28T22:20:47+00:00"
    assert event["tags"] == ["APT28", "phishing"]
    assert event["references"] == ["https://example.test/report"]
    claim = next(
        row
        for row in _rows(handoff / "source_claims.jsonl")
        if row["source_field"] == "adversary[0]"
    )
    assert claim["raw_value"] == "APT28"
    assert claim["claim_scope"] == "attribution"
    assert claim["usage"] == "candidate"
    assert claim["set_semantics"] == "singleton"
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == before


def test_context_and_discovery_evidence_cannot_become_attribution(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    _write_wrapper(
        raw_root,
        "pulse-2",
        "2026-07-28T23:00:00+00:00",
        {
            "created": "2025-01-01T00:00:00",
            "adversary": "APT28, Unknown Cluster",
            "tags": ["APT28", "phishing"],
            "references": [],
            "indicators": [{"type": "IPv4", "indicator": "8.8.8.8"}],
        },
    )
    discovery = tmp_path / "candidates.json"
    discovery.write_text(
        json.dumps(
            [
                {
                    "pulse_id": "pulse-2",
                    "discovery_paths": [
                        {
                            "alias": "Fancy Bear",
                            "canonical_actor_from_frozen_map": "APT28",
                            "otx_query": 'tag:"Fancy Bear"',
                            "method": "trail_exact_actor_tag_search",
                            "search_raw_ref": {
                                "path": "raw/otx_search/query.json",
                                "fetched_at": "2026-07-28T20:00:00+00:00",
                            },
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    result = build_otx_delivery(
        raw_root,
        tmp_path / "delivery",
        discovery_evidence=discovery,
    )

    claims = _rows(result.handoff_dirs[0] / "source_claims.jsonl")
    adversary = [row for row in claims if row["claim_scope"] == "attribution"]
    assert sorted(row["raw_value"] for row in adversary) == [
        "APT28",
        "Unknown Cluster",
    ]
    assert {row["set_semantics"] for row in adversary} == {"set"}
    context = [row for row in claims if row["claim_scope"] == "report_context"]
    assert sorted(row["raw_value"] for row in context) == ["APT28", "phishing"]
    assert {row["usage"] for row in context} == {"provenance_only"}
    discovery_rows = [
        row for row in claims if row["claim_scope"] == "discovery_only"
    ]
    assert len(discovery_rows) == 1
    assert discovery_rows[0]["raw_value"] == "Fancy Bear"
    assert discovery_rows[0]["query_value"] == 'tag:"Fancy Bear"'
    assert discovery_rows[0]["usage"] == "provenance_only"
    assert all(
        row["usage"] == "candidate"
        for row in claims
        if row["claim_scope"] == "attribution"
    )


def test_delivery_uses_portable_deterministic_shards_readable_by_current_consumer(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    _write_wrapper(
        raw_root,
        "pulse-1",
        "2026-01-01T00:00:00+00:00",
        {
            "created": "2024-01-01",
            "indicators": [{"type": "domain", "indicator": "old.example"}],
        },
    )
    newest = _write_wrapper(
        raw_root,
        "pulse-1",
        "2026-02-01T00:00:00+00:00",
        {
            "created": "2024-01-01",
            "indicators": [{"type": "domain", "indicator": "new.example"}],
        },
    )
    _write_wrapper(
        raw_root,
        "pulse-2",
        "2026-03-01T00:00:00+00:00",
        {
            "created": "2024-02-01",
            "indicators": [{"type": "IPv4", "indicator": "1.1.1.1"}],
        },
    )

    result = build_otx_delivery(
        raw_root,
        tmp_path / "delivery",
        events_per_shard=1,
        expected_event_count=2,
    )

    assert result.shard_count == 2
    assert [path.name for path in result.handoff_dirs] == [
        "shard-00000",
        "shard-00001",
    ]
    assert not (tmp_path / "delivery" / "nodes.jsonl").exists()
    events = [
        row
        for handoff in result.handoff_dirs
        for row in _rows(handoff / "events.jsonl")
    ]
    pulse_1 = next(row for row in events if row["source_record_id"] == "pulse-1")
    assert pulse_1["raw_ref"].startswith("data/raw/otx/pulse-1/")
    assert ":" not in pulse_1["raw_ref"].split("/", 3)[0]
    assert "\\" not in pulse_1["raw_ref"]
    assert newest.name.replace(":", "-") in pulse_1["raw_ref"]
    manifest = json.loads(
        (tmp_path / "delivery" / "manifest.json").read_text(encoding="utf-8")
    )
    assert [row["event_count"] for row in manifest["shards"]] == [1, 1]
    assert manifest["bounded_memory"]["flat_full_handoff_written"] is False
    assert manifest["content_hash_scope"]["excludes"] == ["manifest.json"]
    validation = json.loads(
        (tmp_path / "delivery" / "validation.json").read_text(encoding="utf-8")
    )
    assert validation["status"] == "builder_checks_passed"
    assert (
        validation["validation_scope"]["exact_current_evitrail_consumer"]
        == "not_run_by_builder"
    )
    assert validation["validation_scope"]["full_latest_snapshot"] is True
    assert validation["checks"]["expected_event_count_match"] is True
    for handoff in result.handoff_dirs:
        assert {
            "nodes.jsonl",
            "edges.jsonl",
            "events.jsonl",
            "source_claims.jsonl",
            "rejected_records.jsonl",
        } == {path.name for path in handoff.iterdir()}

    consumer_checkout = _evitrail_root()
    sys.path.insert(0, str(consumer_checkout))
    try:
        read_handoff = importlib.import_module(
            "evitrail.data.readers"
        ).read_handoff
        bundles = [read_handoff(str(path)) for path in result.handoff_dirs]
    finally:
        sys.path.remove(str(consumer_checkout))
    assert [len(bundle.events) for bundle in bundles] == [1, 1]

    with pytest.raises(ValueError, match="expected 3 Events, built 2"):
        build_otx_delivery(
            raw_root,
            tmp_path / "count-mismatch",
            expected_event_count=3,
        )


def test_delivery_rejects_hosts_the_current_consumer_cannot_parse(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    _write_wrapper(
        raw_root,
        "pulse-invalid-hosts",
        "2026-07-28T22:20:47+00:00",
        {
            "created": "2024-01-01",
            "indicators": [
                {"type": "domain", "indicator": "good.example"},
                {"type": "domain", "indicator": "bad_name.example"},
                {"type": "URL", "indicator": "http://*.example.com/"},
                {"type": "URL", "indicator": "https://bad_name.example/"},
                {
                    "type": "URL",
                    "indicator": "http://good.example:80/path[.]part",
                },
            ],
        },
    )

    result = build_otx_delivery(raw_root, tmp_path / "delivery")
    handoff = result.handoff_dirs[0]
    assert result.edge_count == 3
    assert result.rejected_count == 3
    assert next(
        row["value"]
        for row in _rows(handoff / "nodes.jsonl")
        if row["type"] == "url"
    ) == "http://good.example/path.part"

    consumer_checkout = _evitrail_root()
    sys.path.insert(0, str(consumer_checkout))
    try:
        read_handoff = importlib.import_module(
            "evitrail.data.readers"
        ).read_handoff
        bundle = read_handoff(str(handoff))
    finally:
        sys.path.remove(str(consumer_checkout))
    indicator_count = sum(len(event.indicators) for event in bundle.events)
    assert indicator_count + len(bundle.relations) == result.edge_count


def test_delivery_greedily_caps_indicator_occurrences_and_records_oversize_event(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    for pulse_id, count in (("pulse-1", 2), ("pulse-2", 2), ("pulse-3", 5)):
        _write_wrapper(
            raw_root,
            pulse_id,
            "2026-01-01T00:00:00+00:00",
            {
                "created": "2024-01-01",
                "indicators": [
                    {
                        "type": "domain",
                        "indicator": f"{index}.{pulse_id}.example",
                    }
                    for index in range(count)
                ],
            },
        )

    result = build_otx_delivery(
        raw_root,
        tmp_path / "delivery",
        events_per_shard=100,
        max_indicator_occurrences_per_shard=3,
    )

    assert result.shard_count == 3
    manifest = json.loads(
        (tmp_path / "delivery" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["sharding_policy"] == {
        "algorithm": "greedy_in_stable_event_id_order",
        "events_per_shard": 100,
        "max_indicator_occurrences_per_shard": 3,
        "single_event_oversize_policy": "retain_whole_event_in_own_shard",
    }
    assert [
        row["raw_indicator_occurrence_count"] for row in manifest["shards"]
    ] == [2, 2, 5]
    assert manifest["shards"][0]["single_event_oversize_exceptions"] == []
    assert manifest["shards"][1]["single_event_oversize_exceptions"] == []
    assert manifest["shards"][2]["single_event_oversize_exceptions"] == [
        "event:otx:pulse-3"
    ]


def test_delivery_include_source_ids_projects_only_selected_pulses(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    for pulse_id in ("pulse-1", "pulse-2"):
        _write_wrapper(
            raw_root,
            pulse_id,
            "2026-01-01T00:00:00+00:00",
            {
                "created": "2024-01-01",
                "indicators": [
                    {
                        "type": "domain",
                        "indicator": f"{pulse_id}.example",
                    }
                ],
            },
        )

    result = build_otx_delivery(
        raw_root,
        tmp_path / "delivery",
        include_source_ids={"pulse-2"},
        expected_event_count=1,
    )

    assert result.event_count == 1
    assert _rows(result.handoff_dirs[0] / "events.jsonl")[0][
        "source_record_id"
    ] == "pulse-2"
    validation_scope = json.loads(
        (result.output_dir / "validation.json").read_text(encoding="utf-8")
    )["validation_scope"]
    assert validation_scope["population_scope"] == "selected_delta"
    assert validation_scope["selected_source_id_count"] == 1
    assert validation_scope["selected_delta_complete"] is True
    assert validation_scope["full_latest_snapshot"] is False
    snapshot_expectation = json.loads(
        (result.output_dir / "manifest.json").read_text(encoding="utf-8")
    )["snapshot_expectation"]
    assert snapshot_expectation["population_scope"] == "selected_delta"
    assert snapshot_expectation["selected_source_id_count"] == 1
    assert snapshot_expectation["selected_delta_complete"] is True
    assert snapshot_expectation["full_latest_snapshot"] is False


def test_delivery_reads_allowlisted_single_wrapper_only_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    raw_path = _write_wrapper(
        raw_root,
        "pulse-1",
        "2026-01-01T00:00:00+00:00",
        {
            "created": "2024-01-01",
            "indicators": [
                {"type": "domain", "indicator": "pulse-1.example"}
            ],
        },
    ).resolve()
    original_read_text = Path.read_text
    raw_read_count = 0

    def count_raw_reads(path: Path, *args: object, **kwargs: object) -> str:
        nonlocal raw_read_count
        if path.resolve() == raw_path:
            raw_read_count += 1
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", count_raw_reads)

    result = build_otx_delivery(
        raw_root,
        tmp_path / "delivery",
        include_source_ids={"pulse-1"},
        expected_event_count=1,
    )

    assert result.event_count == 1
    assert raw_read_count == 1


def test_delivery_does_not_read_excluded_invalid_wrapper(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    _write_wrapper(
        raw_root,
        "selected",
        "2026-01-01T00:00:00+00:00",
        {
            "created": "2024-01-01",
            "indicators": [
                {"type": "domain", "indicator": "selected.example"}
            ],
        },
    )
    excluded = raw_root / "excluded" / "invalid.json"
    excluded.parent.mkdir(parents=True)
    excluded.write_text("{not json", encoding="utf-8")

    result = build_otx_delivery(
        raw_root,
        tmp_path / "delivery",
        include_source_ids={"selected"},
    )

    assert result.event_count == 1
    assert result.rejected_count == 0
    assert _rows(result.handoff_dirs[0] / "rejected_records.jsonl") == []


def test_delivery_rejects_allowlisted_invalid_wrapper_without_rereading(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    invalid = raw_root / "selected" / "invalid.json"
    invalid.parent.mkdir(parents=True)
    invalid.write_text("{not json", encoding="utf-8")

    result = build_otx_delivery(
        raw_root,
        tmp_path / "delivery",
        include_source_ids={"selected"},
    )

    assert result.event_count == 0
    assert result.rejected_count == 1
    rejected = _rows(
        result.handoff_dirs[0] / "rejected_records.jsonl"
    )
    assert rejected[0]["reason"] == "invalid_json"


def test_delivery_normalizes_and_deduplicates_prefixed_include_source_ids(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    for pulse_id in ("pulse-1", "pulse-2"):
        _write_wrapper(
            raw_root,
            pulse_id,
            "2026-01-01T00:00:00+00:00",
            {
                "created": "2024-01-01",
                "indicators": [
                    {
                        "type": "domain",
                        "indicator": f"{pulse_id}.example",
                    }
                ],
            },
        )

    result = build_otx_delivery(
        raw_root,
        tmp_path / "delivery",
        include_source_ids=[
            " event:otx:pulse-2 ",
            "pulse-1",
            "",
            "event:otx:pulse-2",
        ],
    )

    assert result.event_count == 2
    assert {
        row["source_record_id"]
        for row in _rows(result.handoff_dirs[0] / "events.jsonl")
    } == {"pulse-1", "pulse-2"}


def test_delivery_expected_count_gate_detects_missing_allowlisted_id(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw" / "otx"
    _write_wrapper(
        raw_root,
        "pulse-1",
        "2026-01-01T00:00:00+00:00",
        {
            "created": "2024-01-01",
            "indicators": [{"type": "domain", "indicator": "pulse-1.example"}],
        },
    )

    with pytest.raises(ValueError, match="expected 2 Events, built 1"):
        build_otx_delivery(
            raw_root,
            tmp_path / "delivery",
            include_source_ids={"pulse-1", "missing-pulse"},
            expected_event_count=2,
        )


def test_cli_event_id_file_selects_raw_and_prefixed_pulse_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import build_evitrail_otx_delivery as delivery_cli

    raw_root = tmp_path / "raw" / "otx"
    for pulse_id in ("pulse-1", "pulse-2", "pulse-3"):
        _write_wrapper(
            raw_root,
            pulse_id,
            "2026-01-01T00:00:00+00:00",
            {
                "created": "2024-01-01",
                "indicators": [
                    {
                        "type": "domain",
                        "indicator": f"{pulse_id}.example",
                    }
                ],
            },
        )
    event_ids = tmp_path / "event-ids.txt"
    event_ids.write_text(
        "pulse-1\nevent:otx:pulse-2\npulse-1\n\n",
        encoding="utf-8",
    )
    real_builder = build_otx_delivery

    def build_in_test_directory(
        raw_root_arg: Path,
        _output_dir_arg: Path,
        **kwargs: object,
    ):
        return real_builder(
            raw_root_arg,
            tmp_path / "actual-delivery",
            **kwargs,
        )

    monkeypatch.setattr(
        delivery_cli,
        "build_otx_delivery",
        build_in_test_directory,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_evitrail_otx_delivery.py",
            "--raw-root",
            str(raw_root),
            "--output-dir",
            str(tmp_path / "requested-output"),
            "--event-id-file",
            str(event_ids),
        ],
    )

    delivery_cli.main()

    assert json.loads(capsys.readouterr().out)["event_count"] == 2


def test_cli_required_output_root_rejects_an_outside_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import build_evitrail_otx_delivery as delivery_cli

    def unexpected_build(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("builder must not run for an outside output path")

    monkeypatch.setattr(
        delivery_cli,
        "build_otx_delivery",
        unexpected_build,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_evitrail_otx_delivery.py",
            "--raw-root",
            str(tmp_path / "raw"),
            "--output-dir",
            str(tmp_path / "outside" / "delivery"),
            "--required-output-root",
            str(tmp_path / "storage-root"),
        ],
    )

    with pytest.raises(SystemExit, match="--output-dir must be under"):
        delivery_cli.main()
