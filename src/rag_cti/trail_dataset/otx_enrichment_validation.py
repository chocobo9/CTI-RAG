"""Canonicalize and validate population-scoped OTX enrichment ledgers."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rag_cti.trail_dataset.otx_enrichment_collection import EnrichmentTask

TERMINAL_STATUSES = {
    "written",
    "empty",
    "reused",
    "terminal_error",
    "retry_exhausted",
}
SUCCESS_STATUSES = {"written", "empty", "reused"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        return [
            json.loads(line)
            for line in handle
            if line.strip()
        ]


def write_jsonl_atomic(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".canonicalization.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(
                    json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                )
            handle.flush()
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def canonicalize_ledgers(
    *,
    primary_ledger: Path,
    retry_ledgers: Iterable[Path],
    canonical_ledger: Path,
    attempt_history: Path,
) -> dict[str, Any]:
    sources = [primary_ledger, *retry_ledgers]
    combined: list[dict[str, Any]] = []
    latest: dict[str, dict[str, Any]] = {}
    for source in sources:
        for row in read_jsonl(source):
            tagged = dict(row)
            tagged["attempt_ledger"] = str(source.resolve())
            combined.append(tagged)
            task_id = str(row.get("task_id") or "")
            if task_id:
                latest[task_id] = dict(row)
    canonical = sorted(
        latest.values(),
        key=lambda row: (
            str(row.get("endpoint") or ""),
            str(row.get("value") or ""),
            str(row.get("task_id") or ""),
        ),
    )
    write_jsonl_atomic(attempt_history, combined)
    write_jsonl_atomic(canonical_ledger, canonical)
    return {
        "attempt_rows": len(combined),
        "canonical_rows": len(canonical),
        "overridden_attempt_rows": len(combined) - len(canonical),
    }


def validate_enrichment_ledger(
    *,
    tasks: Iterable[EnrichmentTask],
    ledger_path: Path,
    raw_root: Path | None = None,
) -> dict[str, Any]:
    expected = {task.task_id: task for task in tasks}
    rows = read_jsonl(ledger_path)
    counts_by_id = Counter(str(row.get("task_id") or "") for row in rows)
    duplicates = sorted(
        task_id for task_id, count in counts_by_id.items() if task_id and count != 1
    )
    actual = {
        str(row.get("task_id")): row
        for row in rows
        if str(row.get("task_id") or "")
    }
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    invalid_status = sorted(
        task_id
        for task_id, row in actual.items()
        if str(row.get("status")) not in TERMINAL_STATUSES
    )
    authentication_failures = sorted(
        task_id
        for task_id, row in actual.items()
        if int(row.get("http_status") or 0) in {401, 403}
    )
    missing_raw_refs: list[str] = []
    invalid_raw_json: list[str] = []
    status_counts: Counter[str] = Counter()
    endpoint_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for task_id, row in actual.items():
        status = str(row.get("status") or "")
        endpoint = str(row.get("endpoint") or "")
        status_counts[status] += 1
        endpoint_counts[endpoint][status] += 1
        if status not in SUCCESS_STATUSES:
            continue
        raw_ref = Path(str(row.get("raw_ref") or ""))
        if not raw_ref.is_absolute() and raw_root is not None:
            raw_ref = raw_root / raw_ref
        if not raw_ref.is_file():
            missing_raw_refs.append(task_id)
            continue
        try:
            json.loads(raw_ref.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            invalid_raw_json.append(task_id)
    structural_errors = {
        "missing_task_ids": missing,
        "unexpected_task_ids": unexpected,
        "duplicate_task_ids": duplicates,
        "invalid_status_task_ids": invalid_status,
        "authentication_failure_task_ids": authentication_failures,
        "missing_raw_ref_task_ids": sorted(missing_raw_refs),
        "invalid_raw_json_task_ids": sorted(invalid_raw_json),
    }
    status = (
        "pass"
        if not any(structural_errors.values()) and len(rows) == len(expected)
        else "fail"
    )
    return {
        "contract": "trail_otx_enrichment_validation_v1",
        "status": status,
        "expected_tasks": len(expected),
        "ledger_rows": len(rows),
        "unique_task_ids": len(actual),
        "status_counts": dict(sorted(status_counts.items())),
        "endpoint_counts": {
            endpoint: dict(sorted(values.items()))
            for endpoint, values in sorted(endpoint_counts.items())
        },
        "structural_errors": structural_errors,
        "network_terminal_failures": (
            status_counts["retry_exhausted"] + status_counts["terminal_error"]
        ),
    }
