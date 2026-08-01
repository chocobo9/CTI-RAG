"""Build one bounded, EviTRAIL-native OTX enrichment round.

Selection is based on source-provided, resolved OTX adversary claims in the
published EviTRAIL handoff.  It excludes the previously covered population,
events above the declared network-indicator safety gate, and every seed that
already has a terminal task in the prior official ledger.  Events are admitted
whole, smallest first, until the endpoint-task budget is reached.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path


TERMINAL = {
    "written",
    "empty",
    "reused",
    "terminal_error",
    "retry_exhausted",
}


def _task_id(endpoint: str, seed_type: str, value: str) -> str:
    key = f"{endpoint}\0{seed_type}\0{value}".encode()
    return hashlib.sha256(key).hexdigest()[:24]


def _jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _resolved_otx_events(manifest: Path, data_root: Path) -> set[str]:
    refs = json.loads(manifest.read_text(encoding="utf-8"))["claim_refs"]
    result: set[str] = set()
    for ref in refs:
        if "/otx_handoff/" not in ref.replace("\\", "/"):
            continue
        path = data_root / Path(ref)
        for row in _jsonl(path):
            if (
                row.get("source") == "otx"
                and row.get("claim_scope") == "attribution"
                and str(row.get("source_field") or "").startswith("adversary[")
                and row.get("resolution_status") == "resolved"
                and row.get("resolved_actor_ids")
            ):
                result.add(str(row["source_record_id"]))
    return result


def _covered_events(path: Path) -> set[str]:
    result: set[str] = set()
    for row in _jsonl(path):
        pulse_id = str(row.get("pulse_id") or row.get("event_id") or "")
        if pulse_id.startswith("event:otx:"):
            pulse_id = pulse_id.removeprefix("event:otx:")
        if pulse_id:
            result.add(pulse_id)
    return result


def _terminal_ids(paths: list[Path]) -> set[str]:
    result: set[str] = set()
    for path in paths:
        for row in _jsonl(path):
            if row.get("status") in TERMINAL and row.get("task_id"):
                result.add(str(row["task_id"]))
    return result


def _relation_count(source: sqlite3.Connection, pulse_id: str) -> int:
    return int(
        source.execute(
            "SELECT COUNT(*) FROM event_seed "
            "INDEXED BY sqlite_autoindex_event_seed_1 WHERE pulse_id=?",
            (pulse_id,),
        ).fetchone()[0]
    )


def _seed_ids(source: sqlite3.Connection, pulse_id: str) -> set[str]:
    result = {
        row[0]
        for row in source.execute(
            "SELECT seed_id FROM event_seed "
            "INDEXED BY sqlite_autoindex_event_seed_1 WHERE pulse_id=?",
            (pulse_id,),
        )
    }
    result.update(
        row[0]
        for row in source.execute(
            "SELECT host_seed_id FROM url_host "
            "INDEXED BY sqlite_autoindex_url_host_1 WHERE pulse_id=?",
            (pulse_id,),
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims-manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--covered-population", type=Path, required=True)
    parser.add_argument("--prior-ledger", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--task-budget", type=int, default=2000)
    parser.add_argument("--max-event-relations", type=int, default=1000)
    args = parser.parse_args()

    started = time.monotonic()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    resolved = _resolved_otx_events(args.claims_manifest, args.data_root)
    covered = _covered_events(args.covered_population)
    candidates = resolved - covered
    terminal_ids = _terminal_ids(args.prior_ledger)

    source = sqlite3.connect(
        f"file:{args.inventory.resolve().as_posix()}?mode=ro", uri=True
    )
    source.execute("PRAGMA query_only=ON")
    try:
        seed_lookup: dict[str, tuple[str, str]] = {
            seed_id: (seed_type, value)
            for seed_id, seed_type, value in source.execute(
                "SELECT seed_id,seed_type,value FROM seeds NOT INDEXED "
                "WHERE enrichment_eligible=1 AND seed_type IN ('domain','ip')"
            )
        }
        relation_counts = {
            pulse_id: _relation_count(source, pulse_id)
            for pulse_id in sorted(candidates)
        }
        eligible_events = [
            pulse_id
            for pulse_id, count in relation_counts.items()
            if count <= args.max_event_relations
        ]
        eligible_events.sort(key=lambda pulse_id: (relation_counts[pulse_id], pulse_id))

        selected_events: list[dict[str, object]] = []
        selected_seeds: dict[str, tuple[str, str]] = {}
        selected_tasks: set[str] = set()
        for pulse_id in eligible_events:
            event_seeds: dict[str, tuple[str, str]] = {}
            event_tasks: set[str] = set()
            for seed_id in _seed_ids(source, pulse_id):
                seed = seed_lookup.get(seed_id)
                if seed is None:
                    continue
                seed_type, value = seed
                endpoints = (
                    ("domain_pdns",)
                    if seed_type == "domain"
                    else ("ip_pdns", "ip_general")
                )
                task_ids = {
                    _task_id(endpoint, seed_type, value) for endpoint in endpoints
                }
                if task_ids & terminal_ids:
                    continue
                event_seeds[seed_id] = seed
                event_tasks.update(task_ids)
            new_tasks = event_tasks - selected_tasks
            if not new_tasks:
                continue
            if len(selected_tasks | new_tasks) > args.task_budget:
                continue
            selected_tasks.update(new_tasks)
            selected_seeds.update(event_seeds)
            selected_events.append(
                {
                    "pulse_id": pulse_id,
                    "relation_rows": relation_counts[pulse_id],
                    "seed_count": len(event_seeds),
                    "new_endpoint_tasks": len(new_tasks),
                    "cumulative_endpoint_tasks": len(selected_tasks),
                }
            )
            if len(selected_tasks) == args.task_budget:
                break
    finally:
        source.close()

    seeds_path = output / "enrichment_seeds.jsonl"
    with seeds_path.open("w", encoding="utf-8", newline="\n") as handle:
        for seed_id, (seed_type, value) in sorted(selected_seeds.items()):
            handle.write(
                json.dumps(
                    {
                        "seed_id": seed_id,
                        "seed_type": seed_type,
                        "value": value,
                        "enrichment_eligible": True,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    events_path = output / "selected_events.jsonl"
    with events_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected_events:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    by_type = {"domain": 0, "ip": 0}
    for seed_type, _ in selected_seeds.values():
        by_type[seed_type] += 1
    report = {
        "contract": "evitrail_otx_bounded_enrichment_round_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "selection_policy": {
            "actor_claim": "otx adversary claim resolved to an actor",
            "prior_population_excluded": True,
            "prior_terminal_tasks_excluded": True,
            "max_event_relations": args.max_event_relations,
            "whole_event_selection": True,
            "ordering": "relation_rows_then_pulse_id",
            "endpoint_task_budget": args.task_budget,
        },
        "resolved_adversary_events": len(resolved),
        "previously_covered_events": len(covered),
        "candidate_new_events": len(candidates),
        "safety_eligible_events": sum(
            count <= args.max_event_relations for count in relation_counts.values()
        ),
        "selected_events": len(selected_events),
        "selected_seeds": by_type,
        "selected_endpoint_tasks": len(selected_tasks),
        "elapsed_seconds": time.monotonic() - started,
        "outputs": {
            "seeds": seeds_path.name,
            "events": events_path.name,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
