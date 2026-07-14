"""Audit OTX RawStore completeness without calling OTX APIs."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.connectors.otx_raw_views import (
    indicator_completeness,
    indicator_page_source_index,
    latest_indicator_pages,
)
from rag_cti.store.raw_store import RawStore


def build_progress_report(raw_root: Path, run_dir: Path | None = None) -> dict[str, Any]:
    run_scope = _load_run_scope(run_dir)
    queries_untouched = len(run_scope["queries_untouched"])
    queries_with_errors = len(run_scope["queries_with_errors"])
    query_total = run_scope["query_total"]
    queries_completed = len(run_scope["queries_completed"])
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "raw_root": str(raw_root),
        "run_dir": str(run_dir) if run_dir else None,
        "scope": "run_progress",
        "run_scope": _public_run_scope(run_scope),
        "gates": {
            "query_coverage": {
                "status": "pass"
                if query_total is not None
                and queries_untouched == 0
                and queries_with_errors == 0
                and queries_completed == query_total
                else "fail",
                "query_total": query_total,
                "queries_completed": queries_completed,
                "queries_untouched": queries_untouched,
                "queries_with_errors": queries_with_errors,
            }
        },
        "note": (
            "Progress mode reads only run artifacts. Use full mode for pulse detail "
            "and indicator endpoint completeness."
        ),
    }


def build_report(raw_root: Path, run_dir: Path | None = None) -> dict[str, Any]:
    store = RawStore(raw_root)
    run_scope = _load_run_scope(run_dir)
    if run_dir and run_scope["has_run_artifacts"]:
        page_index = run_scope["indicator_page_source_ids_by_pulse"]
    else:
        page_index = indicator_page_source_index(store)
    policy_skips = _load_indicator_policy_skips(run_dir)
    raw_pulse_ids = set() if run_scope["has_run_artifacts"] else set(store.source_ids("otx"))
    scoped_pulse_ids = run_scope["discovered_pulse_ids"] or raw_pulse_ids
    pulse_rows: list[dict[str, Any]] = []
    for pulse_id in scoped_pulse_ids:
        versions = store.versions("otx", pulse_id)
        if not versions:
            pulse_rows.append(
                {
                    "pulse_id": pulse_id,
                    "pulse_fetched_at": None,
                    "indicator_page_count": 0,
                    "detail_indicator_count": 0,
                    "indicator_endpoint_count": 0,
                    "indicator_endpoint_results_total": 0,
                    "indicator_counts_match": False,
                    "missing_required_detail_fields": [],
                    "indicator_endpoint_policy": None,
                    "status": "missing_pulse_detail",
                }
            )
            continue
        fetched_at = versions[-1]
        pulse = store.read("otx", pulse_id, fetched_at)
        if not isinstance(pulse, dict):
            continue
        row = indicator_completeness(
            pulse_id,
            pulse,
            latest_indicator_pages(store, pulse_id, page_index),
        )
        policy = policy_skips.get(pulse_id)
        if policy:
            row["indicator_endpoint_policy"] = policy
            policy_count = policy.get("indicator_count")
            if (
                row["status"] == "missing_indicator_pages"
                and row["detail_indicator_count"] == policy_count
                and policy.get("reason") == "deferred_oversized_indicator_endpoint"
            ):
                row["status"] = "core_complete_endpoint_deferred_by_policy"
            if (
                row["status"] == "missing_indicator_pages"
                and row["detail_indicator_count"] == policy_count
                and policy.get("reason") == "endpoint_pending_by_phase"
            ):
                row["status"] = "core_complete_endpoint_pending_by_phase"
            if (
                row["status"] == "indicator_count_mismatch"
                and row["detail_indicator_count"] == row["indicator_endpoint_count"]
                and row["indicator_endpoint_results_total"] < row["indicator_endpoint_count"]
            ):
                row["status"] = "core_complete_endpoint_partial_skipped_by_policy"
        else:
            row["indicator_endpoint_policy"] = None
        row["pulse_fetched_at"] = fetched_at
        pulse_rows.append(row)

    status_counts: dict[str, int] = {}
    for row in pulse_rows:
        status = str(row["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    counts = {
        "otx_search_records": run_scope["search_pages_ok"]
        if run_dir and run_scope["has_run_artifacts"]
        else len(store.source_ids("otx_search")),
        "pulse_detail_records": sum(1 for row in pulse_rows if row["pulse_fetched_at"]),
        "indicator_page_records": sum(
            len(source_ids)
            for source_ids in run_scope["indicator_page_source_ids_by_pulse"].values()
        )
        if run_dir and run_scope["has_run_artifacts"]
        else len(store.source_ids("otx_indicator_page")),
        "run_discovered_pulses": len(scoped_pulse_ids)
        if run_dir and run_scope["has_run_artifacts"]
        else None,
        "pulses_missing_pulse_detail": status_counts.get("missing_pulse_detail", 0),
        "pulses_with_indicator_pages": sum(
            1 for row in pulse_rows if row["indicator_page_count"] > 0
        ),
        "pulses_endpoint_partial_skipped_by_policy": sum(
            1
            for row in pulse_rows
            if row["status"] == "core_complete_endpoint_partial_skipped_by_policy"
        ),
        "pulses_endpoint_deferred_by_policy": sum(
            1
            for row in pulse_rows
            if row["status"] == "core_complete_endpoint_deferred_by_policy"
        ),
        "pulses_endpoint_pending_by_phase": sum(
            1
            for row in pulse_rows
            if row["status"] == "core_complete_endpoint_pending_by_phase"
        ),
        "pulses_missing_indicator_pages": sum(
            1 for row in pulse_rows if row["status"] == "missing_indicator_pages"
        ),
        "pulses_with_indicator_count_mismatch": sum(
            1 for row in pulse_rows if row["status"] == "indicator_count_mismatch"
        ),
        "pulses_missing_required_detail_fields": sum(
            1 for row in pulse_rows if row["status"] == "missing_required_detail_fields"
        ),
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "raw_root": str(raw_root),
        "run_dir": str(run_dir) if run_dir else None,
        "scope": "run" if run_dir and run_scope["has_run_artifacts"] else "raw_store",
        "run_scope": _public_run_scope(run_scope),
        "counts": counts,
        "status_counts": status_counts,
        "pulses": sorted(pulse_rows, key=lambda row: row["pulse_id"]),
    }


def _load_indicator_policy_skips(run_dir: Path | None) -> dict[str, dict[str, Any]]:
    if run_dir is None:
        return {}
    path = run_dir / "skipped_indicator_pages.jsonl"
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            pulse_id = str(row.get("pulse_id") or "")
            if pulse_id:
                out[pulse_id] = row
    return out


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _load_run_scope(run_dir: Path | None) -> dict[str, Any]:
    empty: dict[str, Any] = {
        "has_run_artifacts": False,
        "query_total": None,
        "queries_touched": set(),
        "queries_completed": set(),
        "queries_with_errors": set(),
        "queries_untouched": set(),
        "query_terminal_status_counts": {},
        "search_pages_total": 0,
        "search_pages_ok": 0,
        "search_pages_error": 0,
        "discovered_pulse_ids": set(),
        "saved_pulse_detail_ids": set(),
        "indicator_page_source_ids_by_pulse": {},
        "latest_invocation_params": None,
        "manifest_params": None,
    }
    if run_dir is None:
        return empty

    query_list_path = run_dir / "mitre_actor_query_list.json"
    query_normalized_values: set[str] = set()
    query_total: int | None = None
    if query_list_path.exists():
        query_list = json.loads(query_list_path.read_text(encoding="utf-8"))
        queries = query_list.get("queries")
        if isinstance(queries, list):
            for row in queries:
                if isinstance(row, dict) and row.get("query_normalized"):
                    query_normalized_values.add(str(row["query_normalized"]))
            query_total = len(queries)

    search_rows = _load_jsonl(run_dir / "search_pages.jsonl")
    terminal_rows = _load_jsonl(run_dir / "query_terminal_states.jsonl")
    query_states = _current_query_states(search_rows, terminal_rows)
    queries_touched = set(query_states)
    queries_completed = {
        query for query, state in query_states.items() if state == "complete"
    }
    queries_with_errors = {
        query
        for query, state in query_states.items()
        if state in {
            "error",
            "error_permanent",
            "error_retryable",
            "invalid_complete",
            "invalid_mixed_page_limit",
            "truncated_page_cap",
        }
    }
    terminal_status_counts: dict[str, int] = {}
    for state in query_states.values():
        terminal_status_counts[state] = terminal_status_counts.get(state, 0) + 1

    discovery_rows = _load_jsonl(run_dir / "discovery_metadata.jsonl")
    discovered_pulse_ids = {
        str(row["pulse_id"])
        for row in discovery_rows
        if isinstance(row.get("pulse_id"), str) and row["pulse_id"]
    }
    saved_rows = _load_jsonl(run_dir / "saved_files.jsonl")
    saved_pulse_detail_ids = {
        str(row["pulse_id"])
        for row in saved_rows
        if row.get("kind") == "pulse_detail"
        and isinstance(row.get("pulse_id"), str)
        and row["pulse_id"]
    }
    indicator_page_source_ids_by_pulse: dict[str, list[str]] = {}
    for row in saved_rows:
        if row.get("kind") != "indicator_page":
            continue
        pulse_id = row.get("pulse_id")
        raw_ref = row.get("raw_ref")
        if not isinstance(pulse_id, str) or not pulse_id or not isinstance(raw_ref, dict):
            continue
        source_id = raw_ref.get("source_id")
        if isinstance(source_id, str) and source_id:
            indicator_page_source_ids_by_pulse.setdefault(pulse_id, []).append(source_id)
    invocation_rows = _load_jsonl(run_dir / "collection_invocations.jsonl")
    latest_invocation_params = None
    if invocation_rows:
        params = invocation_rows[-1].get("params")
        if isinstance(params, dict):
            latest_invocation_params = params

    manifest_params = None
    manifest_path = run_dir / "collection_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        params = manifest.get("params")
        if isinstance(params, dict):
            manifest_params = params

    return {
        "has_run_artifacts": any(
            path.exists()
            for path in (
                query_list_path,
                run_dir / "search_pages.jsonl",
                run_dir / "discovery_metadata.jsonl",
            )
        ),
        "query_total": query_total,
        "queries_touched": queries_touched,
        "queries_completed": queries_completed,
        "queries_with_errors": queries_with_errors,
        "queries_untouched": query_normalized_values - queries_touched,
        "query_terminal_status_counts": terminal_status_counts,
        "search_pages_total": len(search_rows),
        "search_pages_ok": sum(1 for row in search_rows if row.get("status") == "ok"),
        "search_pages_error": sum(
            1 for row in search_rows if row.get("status") == "error"
        ),
        "discovered_pulse_ids": discovered_pulse_ids,
        "saved_pulse_detail_ids": saved_pulse_detail_ids,
        "indicator_page_source_ids_by_pulse": indicator_page_source_ids_by_pulse,
        "latest_invocation_params": latest_invocation_params,
        "manifest_params": manifest_params,
    }


def _public_run_scope(run_scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_run_artifacts": run_scope["has_run_artifacts"],
        "query_total": run_scope["query_total"],
        "queries_touched": len(run_scope["queries_touched"]),
        "queries_completed": len(run_scope["queries_completed"]),
        "queries_with_errors": len(run_scope["queries_with_errors"]),
        "queries_untouched": len(run_scope["queries_untouched"]),
        "query_terminal_status_counts": run_scope["query_terminal_status_counts"],
        "search_pages_total": run_scope["search_pages_total"],
        "search_pages_ok": run_scope["search_pages_ok"],
        "search_pages_error": run_scope["search_pages_error"],
        "discovered_pulse_ids": len(run_scope["discovered_pulse_ids"]),
        "saved_pulse_detail_ids": len(run_scope["saved_pulse_detail_ids"]),
        "indicator_page_records": sum(
            len(source_ids)
            for source_ids in run_scope["indicator_page_source_ids_by_pulse"].values()
        ),
        "latest_invocation_params": run_scope["latest_invocation_params"],
        "manifest_params": run_scope["manifest_params"],
    }


_EXPLICIT_QUERY_STATES = {
    "complete",
    "truncated_page_cap",
    "error_retryable",
    "error_permanent",
}


def _current_query_states(
    search_rows: list[dict[str, Any]],
    terminal_rows: list[dict[str, Any]],
) -> dict[str, str]:
    """Resolve the current state of each query from append-only run artifacts.

    Later rows replace earlier attempts for the same query/page. Explicit
    terminal rows take precedence, but ``complete`` is accepted only when the
    latest successful pages are contiguous and end with ``has_next=false``.
    """

    page_rows: dict[str, dict[int, dict[str, Any]]] = {}
    explicit_page_limits: dict[str, set[int]] = {}
    legacy_rows: dict[str, dict[str, Any]] = {}
    for row in search_rows:
        query = str(row.get("query_normalized") or "")
        if not query:
            continue
        page = row.get("page")
        if isinstance(page, int) and page > 0:
            page_rows.setdefault(query, {})[page] = row
            page_limit = row.get("search_page_limit")
            if isinstance(page_limit, int) and page_limit > 0:
                explicit_page_limits.setdefault(query, set()).add(page_limit)
        else:
            legacy_rows[query] = row

    explicit: dict[str, str] = {}
    for row in terminal_rows:
        query = str(row.get("query_normalized") or "")
        if not query:
            continue
        state = str(
            row.get("terminal_state")
            or row.get("query_status")
            or row.get("status")
            or ""
        )
        if state in _EXPLICIT_QUERY_STATES:
            explicit[query] = state

    queries = set(page_rows) | set(legacy_rows) | set(explicit)
    states: dict[str, str] = {}
    for query in queries:
        if len(explicit_page_limits.get(query, set())) > 1:
            states[query] = "invalid_mixed_page_limit"
            continue
        inferred = _query_state_from_latest_pages(
            page_rows.get(query, {}), legacy_rows.get(query)
        )
        terminal = explicit.get(query)
        if terminal == "complete":
            states[query] = "complete" if inferred == "complete" else "invalid_complete"
        elif terminal:
            states[query] = terminal
        else:
            states[query] = inferred
    return states


def _query_state_from_latest_pages(
    pages: dict[int, dict[str, Any]], legacy_row: dict[str, Any] | None
) -> str:
    if not pages:
        if legacy_row is None:
            return "open"
        if legacy_row.get("status") == "error":
            return "error"
        if legacy_row.get("status") == "ok" and legacy_row.get("has_next") is False:
            return "complete"
        return "open"

    last_page = max(pages)
    if set(pages) != set(range(1, last_page + 1)):
        return "error"
    ordered = [pages[page] for page in range(1, last_page + 1)]
    if any(row.get("status") != "ok" for row in ordered):
        return "error"
    if any(row.get("has_next") is not True for row in ordered[:-1]):
        return "error"
    return "complete" if ordered[-1].get("has_next") is False else "open"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit OTX raw completeness")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--mode",
        choices=("full", "progress"),
        default="full",
        help="progress reads only run artifacts; full reads RawStore payloads.",
    )
    args = parser.parse_args()

    report = (
        build_progress_report(args.raw_root, args.run_dir)
        if args.mode == "progress"
        else build_report(args.raw_root, args.run_dir)
    )
    out = args.out
    if out is None:
        if args.run_dir:
            out = (
                args.run_dir / "run_progress_report.json"
                if args.mode == "progress"
                else args.run_dir / "raw_completeness_report.json"
            )
        else:
            out = Path("data/raw/otx_raw_completeness_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            report.get("counts", report.get("gates", {})),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
