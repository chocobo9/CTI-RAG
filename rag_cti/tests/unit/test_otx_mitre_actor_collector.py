from __future__ import annotations

import importlib.util
import json
import threading
from argparse import Namespace
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_collector() -> ModuleType:
    path = Path(__file__).parents[2] / "scripts" / "fetch_otx_mitre_actor_raw.py"
    spec = importlib.util.spec_from_file_location("fetch_otx_mitre_actor_raw", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_bundle(path: Path) -> None:
    bundle = {
        "objects": [
            {"type": "x-mitre-collection", "x_mitre_version": "18.1"},
            {
                "type": "intrusion-set",
                "id": "intrusion-set--one",
                "name": "Actor One",
                "aliases": ["Shared Alias"],
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "G0001"}
                ],
            },
        ]
    }
    path.write_text(json.dumps(bundle), encoding="utf-8")


def _args(tmp_path: Path, bundle: Path) -> Namespace:
    return Namespace(
        actor=["G0001"],
        bundle=bundle,
        detail_delay=0.0,
        discovery_workers=2,
        indicator_endpoint_full_threshold=50000,
        indicator_page_limit=1000,
        max_actors=0,
        max_indicator_pages=0,
        max_pulses=0,
        max_queries=1,
        max_search_pages=1,
        page_delay=0.0,
        oversized_indicator_sample_pages=1,
        raw_root=tmp_path / "raw",
        refetch_existing_details=False,
        run_dir=tmp_path / "run",
        run_id="unit-run",
        runs_root=tmp_path / "runs",
        search_page_limit=20,
        since="2026-01-01",
        skip_indicator_pages=False,
        until="2026-02-01",
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_collector_writes_run_artifacts_and_resumes_without_network(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_get_json(_client: Any, path: str, **params: Any) -> dict[str, Any]:
        calls.append((path, params))
        if path == "search/pulses":
            return {
                "count": 2,
                "exact_match": False,
                "previous": None,
                "next": None,
                "results": [
                    {
                        "id": "pulse-in-window",
                        "name": "Inside window",
                        "created": "2026-01-15T00:00:00",
                        "modified": "2026-01-16T00:00:00",
                    },
                    {
                        "id": "pulse-skipped",
                        "name": "Outside window",
                        "created": "2025-01-15T00:00:00",
                        "modified": "2025-01-16T00:00:00",
                    },
                ],
            }
        if path == "pulses/pulse-in-window":
            return {
                "id": "pulse-in-window",
                "name": "Inside window",
                "created": "2026-01-15T00:00:00",
                "modified": "2026-01-16T00:00:00",
                "indicators": [
                    {
                        "id": 1,
                        "indicator": "example.com",
                        "type": "domain",
                        "created": "2026-01-15T00:00:00",
                        "expiration": "2026-02-15T00:00:00",
                        "is_active": True,
                    }
                ],
            }
        if path == "pulses/pulse-in-window/indicators":
            return {
                "count": 1,
                "previous": None,
                "next": None,
                "results": [
                    {
                        "id": 1,
                        "pulse_key": "pulse-in-window",
                        "indicator": "example.com",
                        "type": "domain",
                        "created": "2026-01-15T00:00:00",
                        "expiration": "2026-02-15T00:00:00",
                        "is_active": True,
                        "false_positive": False,
                        "slug": "example-com",
                    }
                ],
            }
        raise AssertionError(f"unexpected OTX path: {path}")

    monkeypatch.setattr(collector, "_get_json", fake_get_json)

    assert collector.run(args) == 0

    run_dir = args.run_dir
    assert (run_dir / "mitre_actor_query_list.json").exists()
    assert (run_dir / "collection_manifest.json").exists()
    assert (run_dir / "collection_invocations.jsonl").exists()
    assert (run_dir / "search_pages.jsonl").exists()
    assert (run_dir / "discovery_metadata.jsonl").exists()
    assert (run_dir / "saved_files.jsonl").exists()
    assert (run_dir / "skipped_pulses.jsonl").exists()
    assert (run_dir / "checkpoint.json").exists()
    assert (run_dir / "collection_summary.json").exists()

    query_list = json.loads((run_dir / "mitre_actor_query_list.json").read_text())
    assert query_list["actor_count"] == 1
    assert query_list["deduplicated_query_count"] == 1
    assert query_list["queries"][0]["query"] == "Actor One"

    discovery = _jsonl(run_dir / "discovery_metadata.jsonl")
    invocations = _jsonl(run_dir / "collection_invocations.jsonl")
    skipped = _jsonl(run_dir / "skipped_pulses.jsonl")
    saved = _jsonl(run_dir / "saved_files.jsonl")
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text())

    assert [row["pulse_id"] for row in discovery] == ["pulse-in-window"]
    assert invocations[0]["params"]["skip_indicator_pages"] is False
    assert [row["pulse_id"] for row in skipped] == ["pulse-skipped"]
    assert skipped[0]["reason"] == "outside_date_window"
    assert {row["kind"] for row in saved} == {"search_page", "pulse_detail", "indicator_page"}
    assert len(checkpoint["completed_query_pages"]) == 1
    assert checkpoint["completed_pulse_details"] == ["pulse-in-window"]
    assert checkpoint["completed_indicator_pages"] == ["pulse-in-window:limit=1000:page=1"]
    assert checkpoint["failed_requests"] == []

    assert len(list((args.raw_root / "otx_search").glob("*/*.json"))) == 1
    assert len(list((args.raw_root / "otx").glob("*/*.json"))) == 1
    assert len(list((args.raw_root / "otx_indicator_page").glob("*/*.json"))) == 1
    assert [path for path, _params in calls] == [
        "search/pulses",
        "pulses/pulse-in-window",
        "pulses/pulse-in-window/indicators",
    ]

    calls.clear()

    def fail_on_network(_client: Any, path: str, **_params: Any) -> dict[str, Any]:
        raise AssertionError(f"resume should not request network path: {path}")

    monkeypatch.setattr(collector, "_get_json", fail_on_network)

    assert collector.run(args) == 0
    assert calls == []


def test_collector_records_phase_pending_when_indicator_pages_are_skipped(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.skip_indicator_pages = True
    calls: list[str] = []

    def fake_get_json(_client: Any, path: str, **_params: Any) -> dict[str, Any]:
        calls.append(path)
        if path == "search/pulses":
            return {
                "count": 1,
                "previous": None,
                "next": None,
                "results": [
                    {
                        "id": "pulse-in-window",
                        "name": "Inside window",
                        "created": "2026-01-15T00:00:00",
                        "modified": "2026-01-16T00:00:00",
                    }
                ],
            }
        if path == "pulses/pulse-in-window":
            return {
                "id": "pulse-in-window",
                "name": "Inside window",
                "created": "2026-01-15T00:00:00",
                "modified": "2026-01-16T00:00:00",
                "indicators": [{"indicator": "example.com", "type": "domain"}],
            }
        raise AssertionError(f"unexpected OTX path: {path}")

    monkeypatch.setattr(collector, "_get_json", fake_get_json)

    assert collector.run(args) == 0

    skipped_indicator_rows = _jsonl(args.run_dir / "skipped_indicator_pages.jsonl")
    invocations = _jsonl(args.run_dir / "collection_invocations.jsonl")
    checkpoint = json.loads((args.run_dir / "checkpoint.json").read_text())

    assert calls == ["search/pulses", "pulses/pulse-in-window"]
    assert skipped_indicator_rows[0]["reason"] == "endpoint_pending_by_phase"
    assert skipped_indicator_rows[0]["pulse_id"] == "pulse-in-window"
    assert invocations[0]["params"]["skip_indicator_pages"] is True
    assert checkpoint["skipped_indicator_endpoints"] == [
        "pulse-in-window:limit=1000:threshold=50000:sample_pages=1:"
        "phase=skip_indicator_pages"
    ]


def test_discovery_phase_writes_deduplicated_candidates_with_all_query_paths(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "discovery"
    args.max_queries = 2
    args.discovery_workers = 1
    calls: list[str] = []

    def fake_get_json(_client: Any, path: str, **_params: Any) -> dict[str, Any]:
        calls.append(path)
        assert path == "search/pulses"
        return {
            "count": 1,
            "previous": None,
            "next": None,
            "results": [
                {
                    "id": "pulse-shared",
                    "name": "Shared candidate",
                    "created": "2026-01-15T00:00:00",
                    "modified": "2026-01-16T00:00:00",
                }
            ],
        }

    monkeypatch.setattr(collector, "_get_json", fake_get_json)

    assert collector.run(args) == 0

    candidates = _jsonl(args.run_dir / "candidate_events.jsonl")
    assert calls == ["search/pulses", "search/pulses"]
    assert len(candidates) == 1
    assert candidates[0]["pulse_id"] == "pulse-shared"
    assert [path["query"] for path in candidates[0]["discovery_paths"]] == [
        "Actor One",
        "Shared Alias",
    ]
    assert not list((args.raw_root / "otx").glob("*/*.json"))
    assert not list((args.raw_root / "otx_indicator_page").glob("*/*.json"))


def test_discovery_fetches_queries_concurrently_but_persists_on_main_thread(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "discovery"
    args.max_queries = 2
    args.discovery_workers = 2
    barrier = threading.Barrier(2)
    network_threads: set[int] = set()
    writer_threads: set[int] = set()
    main_thread = threading.get_ident()

    def fake_get_json(_client: Any, path: str, **params: Any) -> dict[str, Any]:
        assert path == "search/pulses"
        network_threads.add(threading.get_ident())
        barrier.wait(timeout=2)
        return {
            "next": None,
            "results": [
                {
                    "id": f"pulse-{params['q']}",
                    "name": params["q"],
                    "created": "2026-01-15T00:00:00",
                }
            ],
        }

    real_write = collector.RawStore.write

    def tracked_write(store: Any, *values: Any, **kwargs: Any) -> Any:
        writer_threads.add(threading.get_ident())
        return real_write(store, *values, **kwargs)

    monkeypatch.setattr(collector, "_get_json", fake_get_json)
    monkeypatch.setattr(collector.RawStore, "write", tracked_write)

    assert collector.run(args) == 0
    assert len(network_threads) == 2
    assert writer_threads == {main_thread}
    assert len(_jsonl(args.run_dir / "candidate_events.jsonl")) == 2


def test_discovery_replays_completed_cached_search_page_into_candidates(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "discovery"
    source_id_calls: list[str] = []
    real_source_ids = collector.RawStore.source_ids

    def tracked_source_ids(store: Any, source: str) -> list[str]:
        source_id_calls.append(source)
        return real_source_ids(store, source)

    monkeypatch.setattr(collector.RawStore, "source_ids", tracked_source_ids)
    source_id = collector.search_raw_source_id_for_query("actor one", 1)
    collector.RawStore(args.raw_root).write(
        "otx_search",
        source_id,
        {
            "next": None,
            "results": [
                {
                    "id": "pulse-cached",
                    "name": "Cached candidate",
                    "created": "2026-01-15T00:00:00",
                    "modified": "2026-01-16T00:00:00",
                }
            ],
        },
        "2026-01-02T03:04:05+00:00",
    )
    args.run_dir.mkdir(parents=True)
    checkpoint = collector._empty_checkpoint(args.run_id)
    checkpoint["completed_query_pages"] = ["actor one:1"]
    (args.run_dir / "checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")
    monkeypatch.setattr(
        collector,
        "_get_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no network")),
    )
    writes: list[int] = []
    real_write_candidates = collector._write_candidate_events

    def counted_write(path: Path, candidates: dict[str, dict[str, Any]]) -> None:
        writes.append(len(candidates))
        real_write_candidates(path, candidates)

    monkeypatch.setattr(collector, "_write_candidate_events", counted_write)

    assert collector.run(args) == 0
    assert collector.run(args) == 0

    candidates = _jsonl(args.run_dir / "candidate_events.jsonl")
    assert len(candidates) == 1
    assert candidates[0]["pulse_id"] == "pulse-cached"
    assert len(candidates[0]["discovery_paths"]) == 1
    assert writes == [1]
    assert "otx" not in source_id_calls


def test_discovery_records_complete_and_page_cap_terminal_states(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)

    for suffix, next_value, expected_status, expected_completed in (
        ("complete", None, "complete", True),
        ("truncated", "page-2", "truncated_page_cap", False),
    ):
        case_root = tmp_path / suffix
        args = _args(case_root, bundle)
        args.phase = "discovery"
        monkeypatch.setattr(
            collector,
            "_get_json",
            lambda *_args, _next=next_value, **_kwargs: {
                "next": _next,
                "results": [],
            },
        )

        assert collector.run(args) == 0

        terminals = _jsonl(args.run_dir / "query_terminal_states.jsonl")
        assert terminals[0]["query_normalized"] == "actor one"
        assert terminals[0]["status"] == expected_status
        checkpoint = json.loads((args.run_dir / "checkpoint.json").read_text())
        assert (
            "actor one:limit=20:page=1" in checkpoint["completed_query_pages"]
        ) is expected_completed


def test_discovery_uses_legacy_limit_for_touched_queries_and_new_limit_for_untouched(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "discovery"
    args.max_queries = 2
    args.search_page_limit = 100
    args.run_dir.mkdir(parents=True)
    (args.run_dir / "collection_manifest.json").write_text(
        json.dumps({"params": {"search_page_limit": 20}}), encoding="utf-8"
    )
    (args.run_dir / "search_pages.jsonl").write_text(
        json.dumps(
            {
                "query": "Actor One",
                "query_normalized": "actor one",
                "page": 1,
                "status": "error",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    limits: list[int] = []

    def fake_get_json(_client: Any, path: str, **params: Any) -> dict[str, Any]:
        assert path == "search/pulses"
        limits.append(params["limit"])
        return {"next": None, "results": []}

    monkeypatch.setattr(collector, "_get_json", fake_get_json)

    assert collector.run(args) == 0
    assert sorted(limits) == [20, 100]
    rows = _jsonl(args.run_dir / "search_pages.jsonl")
    assert rows[-2]["search_page_limit"] == 20
    assert rows[-1]["search_page_limit"] == 100
    terminal = _jsonl(args.run_dir / "query_terminal_states.jsonl")
    assert {row["query_normalized"]: row["search_page_limit"] for row in terminal} == {
        "actor one": 20,
        "shared alias": 100,
    }


def test_discovery_can_retry_an_exact_generated_query(tmp_path: Path, monkeypatch: Any) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "discovery"
    args.discovery_workers = 1
    args.query = ["Shared Alias"]
    calls: list[str] = []

    def fake_get_json(_client: Any, _path: str, **params: Any) -> dict[str, Any]:
        calls.append(params["q"])
        return {"next": None, "results": []}

    monkeypatch.setattr(collector, "_get_json", fake_get_json)

    assert collector.run(args) == 0
    assert calls == ["Shared Alias"]


def test_candidate_compaction_removes_duplicate_discovery_paths(tmp_path: Path) -> None:
    collector = _load_collector()
    raw_ref = {"source_id": "search-1"}
    base = {
        "query": "Actor One",
        "query_normalized": "actor one",
        "query_actors": [],
        "search_page": 1,
        "search_rank": 1,
        "search_raw_ref": raw_ref,
    }
    candidates = {
        "pulse-1": {
            "pulse_id": "pulse-1",
            "discovery_paths": [base, {**base, "search_page_limit": 20}],
        }
    }
    path = tmp_path / "candidate_events.jsonl"

    collector._write_candidate_events(path, candidates)

    rows = _jsonl(path)
    assert len(rows[0]["discovery_paths"]) == 1
    assert rows[0]["discovery_paths"][0]["search_page_limit"] == 20


def test_get_json_rotates_api_keys_and_cools_down_rate_limited_key(
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    now = [100.0]
    pool = collector._OtxApiKeyPool(
        ["key-one", "key-two"],
        cooldown_seconds=30.0,
        clock=lambda: now[0],
        sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
    )
    requests: list[str] = []

    class Response:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(str(self.status_code))

        def json(self) -> dict[str, Any]:
            return {"ok": True}

    class Client:
        _otx_key_pool = pool

        def get(self, _url: str, *, params: dict[str, Any], headers: dict[str, str]) -> Response:
            del params
            requests.append(headers["X-OTX-API-KEY"])
            return Response(429 if len(requests) == 1 else 200)

    monkeypatch.setattr(collector.time, "sleep", lambda _seconds: None)

    assert collector._get_json(Client(), "search/pulses") == {"ok": True}
    assert collector._get_json(Client(), "search/pulses") == {"ok": True}
    assert requests == ["key-one", "key-two", "key-two"]


def test_detail_phase_fetches_each_candidate_once_without_actor_filtering(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "detail"
    args.run_dir.mkdir(parents=True)
    (args.run_dir / "candidate_events.jsonl").write_text(
        json.dumps(
            {
                "pulse_id": "pulse-multi",
                "pulse_name": "Multi actor source claim",
                "discovery_paths": [{"query": "Actor One"}, {"query": "Shared Alias"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_get_json(_client: Any, path: str, **_params: Any) -> dict[str, Any]:
        calls.append(path)
        assert path == "pulses/pulse-multi"
        return {
            "id": "pulse-multi",
            "name": "Multi actor source claim",
            "adversary": "Actor One, Actor Two",
            "indicators": [],
        }

    monkeypatch.setattr(collector, "_get_json", fake_get_json)

    assert collector.run(args) == 0

    assert calls == ["pulses/pulse-multi"]
    raw = next((args.raw_root / "otx").glob("*/*.json"))
    assert json.loads(raw.read_text(encoding="utf-8"))["payload"]["adversary"] == (
        "Actor One, Actor Two"
    )
    assert not list((args.raw_root / "otx_indicator_page").glob("*/*.json"))


def test_detail_phase_reuses_raw_with_run_reference_and_resume_is_idempotent(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "detail"
    args.run_dir.mkdir(parents=True)
    (args.run_dir / "candidate_events.jsonl").write_text(
        json.dumps({"pulse_id": "pulse-existing", "discovery_paths": []}) + "\n",
        encoding="utf-8",
    )
    raw_path = collector.RawStore(args.raw_root).write(
        "otx",
        "pulse-existing",
        {"id": "pulse-existing", "adversary": "Actor One, Actor Two"},
        "2026-01-02T03:04:05+00:00",
    )
    monkeypatch.setattr(
        collector,
        "_get_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no network")),
    )

    assert collector.run(args) == 0
    assert collector.run(args) == 0

    saved = _jsonl(args.run_dir / "saved_files.jsonl")
    assert len(saved) == 1
    assert saved[0]["kind"] == "pulse_detail"
    assert saved[0]["pulse_id"] == "pulse-existing"
    assert saved[0]["raw_ref"] == {
        "connector_source": "otx",
        "source": "otx",
        "source_id": "pulse-existing",
        "fetched_at": "2026-01-02T03:04:05+00:00",
        "path": str(raw_path),
    }
    checkpoint = json.loads((args.run_dir / "checkpoint.json").read_text())
    assert checkpoint["completed_pulse_details"] == ["pulse-existing"]
    assert checkpoint["saved_pulse_ids"] == ["pulse-existing"]


def test_all_phase_records_reused_detail_without_refetching_it(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "all"
    args.skip_indicator_pages = True
    raw_path = collector.RawStore(args.raw_root).write(
        "otx",
        "pulse-existing",
        {"id": "pulse-existing", "adversary": "Actor One, Actor Two", "indicators": []},
        "2026-01-02T03:04:05+00:00",
    )
    calls: list[str] = []

    def fake_get_json(_client: Any, path: str, **_params: Any) -> dict[str, Any]:
        calls.append(path)
        assert path == "search/pulses"
        return {
            "next": None,
            "results": [
                {
                    "id": "pulse-existing",
                    "name": "Existing multi actor Pulse",
                    "created": "2026-01-15T00:00:00",
                    "modified": "2026-01-16T00:00:00",
                }
            ],
        }

    monkeypatch.setattr(collector, "_get_json", fake_get_json)

    assert collector.run(args) == 0

    assert calls == ["search/pulses"]
    saved = _jsonl(args.run_dir / "saved_files.jsonl")
    detail_rows = [row for row in saved if row["kind"] == "pulse_detail"]
    assert len(detail_rows) == 1
    assert detail_rows[0]["pulse_id"] == "pulse-existing"
    assert detail_rows[0]["raw_ref"]["path"] == str(raw_path)
    checkpoint = json.loads((args.run_dir / "checkpoint.json").read_text())
    assert checkpoint["completed_pulse_details"] == ["pulse-existing"]
    assert checkpoint["saved_pulse_ids"] == ["pulse-existing"]
    assert not list((args.raw_root / "otx_indicator_page").glob("*/*.json"))


def test_detail_phase_rebuilds_candidate_manifest_from_legacy_discovery_metadata(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "detail"
    args.run_dir.mkdir(parents=True)
    discovery = {
        "pulse_id": "pulse-legacy",
        "pulse_name": "Legacy candidate",
        "query": "Actor One",
        "query_normalized": "actor one",
        "query_actors": [{"actor_name": "Actor One"}],
        "search_page": 1,
        "search_rank": 1,
        "search_raw_ref": {"source": "otx_search", "source_id": "legacy-page"},
    }
    (args.run_dir / "discovery_metadata.jsonl").write_text(
        json.dumps(discovery) + "\n" + json.dumps(discovery) + "\n",
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_get_json(_client: Any, path: str, **_params: Any) -> dict[str, Any]:
        calls.append(path)
        return {"id": "pulse-legacy", "adversary": "Actor One, Actor Two", "indicators": []}

    monkeypatch.setattr(collector, "_get_json", fake_get_json)

    assert collector.run(args) == 0

    assert calls == ["pulses/pulse-legacy"]
    candidates = _jsonl(args.run_dir / "candidate_events.jsonl")
    assert len(candidates) == 1
    assert candidates[0]["pulse_id"] == "pulse-legacy"
    assert len(candidates[0]["discovery_paths"]) == 1


def test_indicator_phase_requires_an_explicit_page_bound(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "indicators"
    args.max_indicator_pages = 0

    monkeypatch.setattr(
        collector,
        "_get_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no network")),
    )

    assert collector.run(args) == 1


def test_indicator_phase_uses_candidates_and_stops_at_page_bound(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    collector = _load_collector()
    monkeypatch.setenv("OTX_API_KEY", "test-key")
    bundle = tmp_path / "enterprise-attack.json"
    _write_bundle(bundle)
    args = _args(tmp_path, bundle)
    args.phase = "indicators"
    args.max_indicator_pages = 1
    args.run_dir.mkdir(parents=True)
    (args.run_dir / "candidate_events.jsonl").write_text(
        json.dumps({"pulse_id": "pulse-one", "discovery_paths": []}) + "\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, int]] = []

    def fake_get_json(_client: Any, path: str, **params: Any) -> dict[str, Any]:
        calls.append((path, params["page"]))
        return {
            "count": 2,
            "next": "page-2",
            "results": [{"indicator": "example.com", "type": "domain"}],
        }

    monkeypatch.setattr(collector, "_get_json", fake_get_json)

    assert collector.run(args) == 0

    assert calls == [("pulses/pulse-one/indicators", 1)]
    assert not list((args.raw_root / "otx").glob("*/*.json"))
    assert len(list((args.raw_root / "otx_indicator_page").glob("*/*.json"))) == 1
