"""Retry transient OTX enrichment failures once and validate the canonical ledger."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx

from rag_cti.config import get_settings
from rag_cti.trail_dataset.otx_enrichment_collection import (
    OTX_BASE,
    build_tasks,
    collect_tasks,
    httpx_requester,
)
from rag_cti.trail_dataset.otx_enrichment_validation import (
    canonicalize_ledgers,
    read_jsonl,
    validate_enrichment_ledger,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds-jsonl", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--old-pdns-root", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-attempts", type=int, default=7)
    parser.add_argument(
        "--finalize-existing",
        action="store_true",
        help="Canonicalize existing primary/retry ledgers without new requests.",
    )
    args = parser.parse_args()

    tasks = build_tasks(args.seeds_jsonl, old_pdns_root=args.old_pdns_root)
    task_by_id = {task.task_id: task for task in tasks}
    primary = args.output_root / "enrichment_terminal_states.jsonl"
    failed_ids = {
        str(row.get("task_id"))
        for row in read_jsonl(primary)
        if row.get("status") == "retry_exhausted"
    }
    prior_retry_ledgers = sorted(
        (args.output_root / "_retry_attempts").glob(
            "*/enrichment_terminal_states.jsonl"
        )
    )
    latest_prior_retry: dict[str, dict[str, object]] = {}
    for ledger in prior_retry_ledgers:
        for row in read_jsonl(ledger):
            task_id = str(row.get("task_id") or "")
            if task_id:
                latest_prior_retry[task_id] = row
    previously_resolved_ids = {
        task_id
        for task_id, row in latest_prior_retry.items()
        if str(row.get("status")) in {"written", "empty", "reused"}
    }
    unresolved_retry_tasks = [
        task_by_id[task_id]
        for task_id in sorted(failed_ids)
        if task_id in task_by_id and task_id not in previously_resolved_ids
    ]
    retry_tasks = [] if args.finalize_existing else unresolved_retry_tasks

    retry_ledgers: list[Path] = list(prior_retry_ledgers)
    retry_root: Path | None = None
    if retry_tasks:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        retry_root = args.output_root / "_retry_attempts" / stamp
        api_key = get_settings().otx_api_key.get_secret_value()
        if not api_key:
            parser.error("OTX API key is unavailable")
        with httpx.Client(
            base_url=OTX_BASE,
            headers={"X-OTX-API-KEY": api_key},
            timeout=args.timeout,
        ) as client:
            collect_tasks(
                tasks=retry_tasks,
                output_root=retry_root,
                requester=httpx_requester(
                    client, max_attempts=args.max_attempts
                ),
                phase="retry",
                workers=args.workers,
            )
        retry_ledgers.append(retry_root / "enrichment_terminal_states.jsonl")

    canonical = args.output_root / "enrichment_terminal_states.canonical.jsonl"
    history = args.output_root / "enrichment_attempt_history.jsonl"
    canonicalization = canonicalize_ledgers(
        primary_ledger=primary,
        retry_ledgers=retry_ledgers,
        canonical_ledger=canonical,
        attempt_history=history,
    )
    backup = (
        retry_root / "primary_ledger_before_retry.jsonl"
        if retry_root is not None
        else args.output_root / "enrichment_terminal_states.precanonical.jsonl"
    )
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(primary, backup)
    canonical.replace(primary)

    report = validate_enrichment_ledger(
        tasks=tasks, ledger_path=primary, raw_root=args.output_root
    )
    report["canonicalization"] = canonicalization
    report["retry_requested_tasks"] = len(retry_tasks)
    report["retry_unresolved_at_finalization"] = len(
        unresolved_retry_tasks
    )
    report["finalize_existing_only"] = args.finalize_existing
    report["retry_previously_resolved_tasks"] = len(
        failed_ids & previously_resolved_ids
    )
    report["prior_retry_ledgers"] = [
        str(path.resolve()) for path in prior_retry_ledgers
    ]
    report["retry_root"] = str(retry_root.resolve()) if retry_root else None
    report["generated_at"] = datetime.now(UTC).isoformat()
    output = args.output_root / "final_enrichment_report.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
