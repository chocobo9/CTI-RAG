from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from rag_cti.connectors.otx_actor_collection import indicator_page_source_id
from rag_cti.store.raw_store import RawStore


def _load_audit_script() -> ModuleType:
    path = Path(__file__).parents[2] / "scripts" / "audit_otx_raw_completeness.py"
    spec = importlib.util.spec_from_file_location("audit_otx_raw_completeness", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _complete_pulse(pulse_id: str) -> dict:
    return {
        "id": pulse_id,
        "name": "Pulse",
        "description": "",
        "author_name": "author",
        "modified": "2026-01-02",
        "created": "2026-01-01",
        "tags": [],
        "references": [],
        "public": 1,
        "adversary": "",
        "targeted_countries": [],
        "malware_families": [],
        "attack_ids": [],
        "industries": [],
        "TLP": "white",
        "indicators": [{"indicator": "one.example", "type": "domain"}],
        "revision": 1,
        "groups": [],
        "in_group": False,
        "author": {},
        "is_subscribing": False,
    }


def test_build_report_counts_raw_completeness(tmp_path):
    audit_script = _load_audit_script()
    store = RawStore(tmp_path)
    fetched_at = "2026-07-04T00:00:00+00:00"
    pulse = _complete_pulse("pulse-1")
    store.write("otx_search", "query_0001_abc", {"results": [{"id": "pulse-1"}]}, fetched_at)
    store.write("otx", "pulse-1", pulse, fetched_at)
    store.write(
        "otx_indicator_page",
        indicator_page_source_id("pulse-1", 1),
        {
            "count": 1,
            "next": None,
            "results": [{"indicator": "one.example", "type": "domain"}],
        },
        fetched_at,
    )

    report = audit_script.build_report(tmp_path, tmp_path / "run")

    assert report["counts"]["otx_search_records"] == 1
    assert report["counts"]["pulse_detail_records"] == 1
    assert report["counts"]["indicator_page_records"] == 1
    assert report["counts"]["pulses_with_indicator_pages"] == 1
    assert report["counts"]["pulses_missing_indicator_pages"] == 0
    assert report["pulses"][0]["status"] == "ok"
    assert report["pulses"][0]["indicator_counts_match"] is True


def test_build_report_classifies_policy_skipped_endpoint(tmp_path):
    audit_script = _load_audit_script()
    raw_root = tmp_path / "raw"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    store = RawStore(raw_root)
    fetched_at = "2026-07-04T00:00:00+00:00"
    pulse = _complete_pulse("pulse-large")
    pulse["indicators"] = [
        {"id": 1, "indicator": "one.example", "type": "domain"},
        {"id": 2, "indicator": "two.example", "type": "domain"},
        {"id": 3, "indicator": "three.example", "type": "domain"},
    ]
    store.write("otx", "pulse-large", pulse, fetched_at)
    store.write(
        "otx_indicator_page",
        indicator_page_source_id("pulse-large", 1, 1000),
        {"count": 3, "next": "next", "results": [pulse["indicators"][0]]},
        fetched_at,
    )
    (run_dir / "skipped_indicator_pages.jsonl").write_text(
        (
            '{"pulse_id":"pulse-large","reason":"indicator_count_exceeds_policy_threshold",'
            '"indicator_count":3,"fetched_pages":1,"fetched_results":1}\n'
        ),
        encoding="utf-8",
    )

    report = audit_script.build_report(raw_root, run_dir)

    assert report["counts"]["pulses_endpoint_partial_skipped_by_policy"] == 1
    assert report["counts"]["pulses_with_indicator_count_mismatch"] == 0
    assert report["pulses"][0]["status"] == "core_complete_endpoint_partial_skipped_by_policy"
    assert report["pulses"][0]["indicator_endpoint_policy"]["reason"] == (
        "indicator_count_exceeds_policy_threshold"
    )


def test_build_report_classifies_policy_deferred_endpoint(tmp_path):
    audit_script = _load_audit_script()
    raw_root = tmp_path / "raw"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    store = RawStore(raw_root)
    fetched_at = "2026-07-04T00:00:00+00:00"
    pulse = _complete_pulse("pulse-large")
    pulse["indicators"] = [
        {"id": 1, "indicator": "one.example", "type": "domain"},
        {"id": 2, "indicator": "two.example", "type": "domain"},
    ]
    store.write("otx", "pulse-large", pulse, fetched_at)
    (run_dir / "skipped_indicator_pages.jsonl").write_text(
        (
            '{"pulse_id":"pulse-large","reason":"deferred_oversized_indicator_endpoint",'
            '"indicator_count":2,"fetched_pages":0,"fetched_results":0}\n'
        ),
        encoding="utf-8",
    )

    report = audit_script.build_report(raw_root, run_dir)

    assert report["counts"]["pulses_endpoint_deferred_by_policy"] == 1
    assert report["counts"]["pulses_missing_indicator_pages"] == 0
    assert report["pulses"][0]["status"] == "core_complete_endpoint_deferred_by_policy"


def test_build_report_scopes_to_run_discoveries(tmp_path):
    audit_script = _load_audit_script()
    raw_root = tmp_path / "raw"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    store = RawStore(raw_root)
    fetched_at = "2026-07-04T00:00:00+00:00"
    store.write("otx", "pulse-in-run", _complete_pulse("pulse-in-run"), fetched_at)
    store.write("otx", "pulse-old", _complete_pulse("pulse-old"), fetched_at)
    (run_dir / "mitre_actor_query_list.json").write_text(
        '{"queries":[{"query":"Actor","query_normalized":"actor"}]}\n',
        encoding="utf-8",
    )
    (run_dir / "search_pages.jsonl").write_text(
        '{"query":"Actor","query_normalized":"actor","status":"ok","has_next":false}\n',
        encoding="utf-8",
    )
    (run_dir / "discovery_metadata.jsonl").write_text(
        '{"query":"Actor","query_normalized":"actor","pulse_id":"pulse-in-run"}\n',
        encoding="utf-8",
    )

    report = audit_script.build_report(raw_root, run_dir)

    assert report["scope"] == "run"
    assert report["run_scope"]["query_total"] == 1
    assert report["run_scope"]["queries_completed"] == 1
    assert report["counts"]["run_discovered_pulses"] == 1
    assert [row["pulse_id"] for row in report["pulses"]] == ["pulse-in-run"]


def test_build_report_classifies_endpoint_pending_by_phase(tmp_path):
    audit_script = _load_audit_script()
    raw_root = tmp_path / "raw"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    store = RawStore(raw_root)
    fetched_at = "2026-07-04T00:00:00+00:00"
    pulse = _complete_pulse("pulse-phase")
    store.write("otx", "pulse-phase", pulse, fetched_at)
    (run_dir / "discovery_metadata.jsonl").write_text(
        '{"query":"Actor","query_normalized":"actor","pulse_id":"pulse-phase"}\n',
        encoding="utf-8",
    )
    (run_dir / "skipped_indicator_pages.jsonl").write_text(
        (
            '{"pulse_id":"pulse-phase","reason":"endpoint_pending_by_phase",'
            '"indicator_count":1,"fetched_pages":0,"fetched_results":0}\n'
        ),
        encoding="utf-8",
    )

    report = audit_script.build_report(raw_root, run_dir)

    assert report["counts"]["pulses_endpoint_pending_by_phase"] == 1
    assert report["counts"]["pulses_missing_indicator_pages"] == 0
    assert report["pulses"][0]["status"] == "core_complete_endpoint_pending_by_phase"


def test_build_progress_report_uses_run_artifacts_only(tmp_path):
    audit_script = _load_audit_script()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "mitre_actor_query_list.json").write_text(
        (
            '{"queries":['
            '{"query":"Actor","query_normalized":"actor"},'
            '{"query":"Alias","query_normalized":"alias"}'
            "]}\n"
        ),
        encoding="utf-8",
    )
    (run_dir / "search_pages.jsonl").write_text(
        (
            '{"query":"Actor","query_normalized":"actor","status":"ok",'
            '"has_next":false}\n'
        ),
        encoding="utf-8",
    )

    report = audit_script.build_progress_report(tmp_path / "raw", run_dir)

    assert report["scope"] == "run_progress"
    assert report["run_scope"]["query_total"] == 2
    assert report["run_scope"]["queries_touched"] == 1
    assert report["run_scope"]["queries_untouched"] == 1
    assert report["gates"]["query_coverage"]["status"] == "fail"


def test_progress_recovered_page_error_is_not_active_when_query_completes(tmp_path):
    audit_script = _load_audit_script()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "mitre_actor_query_list.json").write_text(
        '{"queries":[{"query_normalized":"actor"}]}\n', encoding="utf-8"
    )
    (run_dir / "search_pages.jsonl").write_text(
        (
            '{"query_normalized":"actor","page":1,"status":"error"}\n'
            '{"query_normalized":"actor","page":1,"status":"ok","has_next":true}\n'
            '{"query_normalized":"actor","page":2,"status":"ok","has_next":false}\n'
        ),
        encoding="utf-8",
    )

    report = audit_script.build_progress_report(tmp_path / "raw", run_dir)

    assert report["run_scope"]["queries_completed"] == 1
    assert report["run_scope"]["queries_with_errors"] == 0
    assert report["gates"]["query_coverage"]["status"] == "pass"


def test_progress_unrecovered_latest_page_error_remains_active(tmp_path):
    audit_script = _load_audit_script()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "mitre_actor_query_list.json").write_text(
        '{"queries":[{"query_normalized":"actor"}]}\n', encoding="utf-8"
    )
    (run_dir / "search_pages.jsonl").write_text(
        (
            '{"query_normalized":"actor","page":1,"status":"ok","has_next":true}\n'
            '{"query_normalized":"actor","page":2,"status":"error"}\n'
        ),
        encoding="utf-8",
    )

    report = audit_script.build_progress_report(tmp_path / "raw", run_dir)

    assert report["run_scope"]["queries_completed"] == 0
    assert report["run_scope"]["queries_with_errors"] == 1
    assert report["gates"]["query_coverage"]["status"] == "fail"


def test_progress_open_query_does_not_pass_coverage_gate(tmp_path):
    audit_script = _load_audit_script()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "mitre_actor_query_list.json").write_text(
        '{"queries":[{"query_normalized":"actor"}]}\n', encoding="utf-8"
    )
    (run_dir / "search_pages.jsonl").write_text(
        '{"query_normalized":"actor","page":1,"status":"ok","has_next":true}\n',
        encoding="utf-8",
    )

    report = audit_script.build_progress_report(tmp_path / "raw", run_dir)

    assert report["run_scope"]["queries_untouched"] == 0
    assert report["run_scope"]["queries_with_errors"] == 0
    assert report["run_scope"]["queries_completed"] == 0
    assert report["gates"]["query_coverage"]["status"] == "fail"


def test_progress_requires_contiguous_pages_for_complete(tmp_path):
    audit_script = _load_audit_script()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "mitre_actor_query_list.json").write_text(
        '{"queries":[{"query_normalized":"actor"}]}\n', encoding="utf-8"
    )
    (run_dir / "search_pages.jsonl").write_text(
        (
            '{"query_normalized":"actor","page":1,"status":"ok","has_next":true}\n'
            '{"query_normalized":"actor","page":3,"status":"ok","has_next":false}\n'
        ),
        encoding="utf-8",
    )

    report = audit_script.build_progress_report(tmp_path / "raw", run_dir)

    assert report["run_scope"]["queries_completed"] == 0
    assert report["run_scope"]["queries_with_errors"] == 1


def test_progress_rejects_multiple_explicit_page_limits_for_one_query(tmp_path):
    audit_script = _load_audit_script()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "mitre_actor_query_list.json").write_text(
        '{"queries":[{"query_normalized":"actor"}]}\n', encoding="utf-8"
    )
    (run_dir / "search_pages.jsonl").write_text(
        (
            '{"query_normalized":"actor","page":1,"search_page_limit":20,'
            '"status":"ok","has_next":true}\n'
            '{"query_normalized":"actor","page":2,"search_page_limit":100,'
            '"status":"ok","has_next":false}\n'
        ),
        encoding="utf-8",
    )

    report = audit_script.build_progress_report(tmp_path / "raw", run_dir)

    assert report["run_scope"]["queries_completed"] == 0
    assert report["run_scope"]["queries_with_errors"] == 1
    assert report["run_scope"]["query_terminal_status_counts"] == {
        "invalid_mixed_page_limit": 1
    }


def test_progress_reads_explicit_terminal_states_without_counting_truncated_complete(
    tmp_path,
):
    audit_script = _load_audit_script()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "mitre_actor_query_list.json").write_text(
        (
            '{"queries":['
            '{"query_normalized":"complete"},'
            '{"query_normalized":"truncated"},'
            '{"query_normalized":"retryable"},'
            '{"query_normalized":"permanent"}'
            ']}\n'
        ),
        encoding="utf-8",
    )
    (run_dir / "search_pages.jsonl").write_text(
        (
            '{"query_normalized":"complete","page":1,"status":"ok","has_next":false}\n'
            '{"query_normalized":"truncated","page":1,"status":"ok","has_next":true}\n'
        ),
        encoding="utf-8",
    )
    (run_dir / "query_terminal_states.jsonl").write_text(
        (
            '{"query_normalized":"complete","status":"complete","page":1,"has_next":false}\n'
            '{"query_normalized":"truncated","terminal_state":"truncated_page_cap"}\n'
            '{"query_normalized":"retryable","query_status":"error_retryable"}\n'
            '{"query_normalized":"permanent","status":"error_permanent"}\n'
        ),
        encoding="utf-8",
    )

    report = audit_script.build_progress_report(tmp_path / "raw", run_dir)

    assert report["run_scope"]["queries_completed"] == 1
    assert report["run_scope"]["queries_with_errors"] == 3
    assert report["run_scope"]["query_terminal_status_counts"] == {
        "complete": 1,
        "error_permanent": 1,
        "error_retryable": 1,
        "truncated_page_cap": 1,
    }
