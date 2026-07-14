"""Plan actor-evidenced OTX Pulse detail acquisition without broadening scope."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RoutedDetailPlan:
    acquire_ids: tuple[str, ...]
    network_ids: tuple[str, ...]
    deferred_count: int
    declared_missing_count: int


def _latest_statuses(path: Path | None) -> dict[str, str]:
    statuses: dict[str, str] = {}
    if path is None or not path.exists():
        return statuses
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        statuses[str(row["pulse_id"])] = str(row["status"])
    return statuses


def load_routed_detail_plan(
    manifest_path: Path,
    *,
    statuses_path: Path | None = None,
    retry_only: bool = False,
) -> RoutedDetailPlan:
    """Return the immutable acquire population and the IDs eligible for network I/O."""

    acquire: list[str] = []
    initially_missing: list[str] = []
    deferred = 0
    seen: set[str] = set()
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        pulse_id = str(row.get("pulse_id") or "")
        if not pulse_id:
            raise ValueError("routing row missing pulse_id")
        if pulse_id in seen:
            raise ValueError(f"duplicate pulse_id: {pulse_id}")
        seen.add(pulse_id)
        if not str(row.get("decision") or "").startswith("acquire_"):
            deferred += 1
            continue
        acquire.append(pulse_id)
        if row.get("existing_detail") is not True:
            initially_missing.append(pulse_id)

    statuses = _latest_statuses(statuses_path)
    if retry_only:
        network = [pid for pid in initially_missing if statuses.get(pid) == "retryable_error"]
    else:
        terminal = {"complete", "reused", "not_found", "forbidden", "oversized_failure"}
        network = [pid for pid in initially_missing if statuses.get(pid) not in terminal]
    return RoutedDetailPlan(tuple(acquire), tuple(network), deferred, len(initially_missing))
