"""Resumable raw-first OTX pDNS and ASN enrichment for a frozen seed list."""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rag_cti.store.raw_store import RawStore

OTX_BASE = "https://otx.alienvault.com"
ENDPOINT_SOURCE = {
    "domain_pdns": "otx_domain_pdns",
    "ip_pdns": "otx_ip_pdns",
    "ip_general": "otx_ip_general",
}


@dataclass(frozen=True)
class EnrichmentTask:
    task_id: str
    endpoint: str
    seed_type: str
    value: str
    reuse_path: Path | None = None

    @classmethod
    def create(
        cls,
        endpoint: str,
        seed_type: str,
        value: str,
        reuse_path: Path | None = None,
    ) -> EnrichmentTask:
        key = f"{endpoint}\0{seed_type}\0{value}"
        return cls(
            task_id=hashlib.sha256(key.encode()).hexdigest()[:24],
            endpoint=endpoint,
            seed_type=seed_type,
            value=value,
            reuse_path=reuse_path,
        )

    @property
    def api_path(self) -> str:
        escaped = quote(self.value, safe="")
        if self.endpoint == "domain_pdns":
            return f"/api/v1/indicators/domain/{escaped}/passive_dns"
        if self.endpoint == "ip_pdns":
            return f"/api/v1/indicators/IPv4/{escaped}/passive_dns"
        if self.endpoint == "ip_general":
            return f"/api/v1/indicators/IPv4/{escaped}/general"
        raise ValueError(f"unknown endpoint: {self.endpoint}")


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path} contains a non-object row")
                yield value


def _old_pdns_path(root: Path | None, domain: str) -> Path | None:
    if root is None:
        return None
    directory = root / domain
    files = sorted(directory.glob("*.json")) if directory.is_dir() else []
    return files[-1] if files else None


def build_tasks(
    seeds_jsonl: Path, *, old_pdns_root: Path | None = None
) -> list[EnrichmentTask]:
    tasks: list[EnrichmentTask] = []
    seen: set[str] = set()
    for row in _iter_jsonl(seeds_jsonl):
        seed_type = str(row.get("seed_type") or "")
        value = str(row.get("value") or "").strip()
        if not value:
            continue
        if seed_type == "domain":
            reuse = (
                _old_pdns_path(old_pdns_root, value)
                if row.get("old_pdns_lookup")
                else None
            )
            candidate = EnrichmentTask.create(
                "domain_pdns", "domain", value, reuse
            )
            if candidate.task_id not in seen:
                tasks.append(candidate)
                seen.add(candidate.task_id)
        elif seed_type == "ip":
            for endpoint in ("ip_pdns", "ip_general"):
                candidate = EnrichmentTask.create(endpoint, "ip", value)
                if candidate.task_id not in seen:
                    tasks.append(candidate)
                    seen.add(candidate.task_id)
    return sorted(tasks, key=lambda task: (task.endpoint, task.value))


def select_pilot(
    tasks: Iterable[EnrichmentTask], *, per_endpoint: int
) -> list[EnrichmentTask]:
    groups: dict[str, list[EnrichmentTask]] = defaultdict(list)
    for task in tasks:
        groups[task.endpoint].append(task)
    result = []
    for endpoint in sorted(groups):
        ordered = sorted(
            groups[endpoint],
            key=lambda task: hashlib.sha256(task.task_id.encode()).hexdigest(),
        )
        result.extend(ordered[:per_endpoint])
    return sorted(result, key=lambda task: (task.endpoint, task.task_id))


def _is_empty(endpoint: str, payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return True
    if endpoint in {"domain_pdns", "ip_pdns"}:
        return not bool(payload.get("passive_dns"))
    return not bool(payload)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def collect_tasks(
    *,
    tasks: list[EnrichmentTask],
    output_root: Path,
    requester: Callable[[EnrichmentTask], tuple[int, Any, int, float]],
    phase: str,
    fetched_at: str | None = None,
    workers: int = 4,
) -> dict[str, Any]:
    """Collect tasks serially at the persistence boundary.

    ``requester`` may perform bounded internal retries. It returns HTTP status,
    decoded payload (or error metadata), attempt count, and elapsed seconds.
    """

    output_root.mkdir(parents=True, exist_ok=True)
    ledger_path = output_root / "enrichment_terminal_states.jsonl"
    completed = {
        str(row.get("task_id"))
        for row in _iter_jsonl(ledger_path)
        if row.get("status") in {
            "written",
            "empty",
            "reused",
            "terminal_error",
            "retry_exhausted",
        }
    } if ledger_path.is_file() else set()
    fetched_at = fetched_at or datetime.now(UTC).isoformat()
    store = RawStore(output_root / "raw")
    counts: Counter[str] = Counter()
    endpoint_counts: dict[str, Counter[str]] = defaultdict(Counter)

    def process(task: EnrichmentTask) -> dict[str, Any]:
        if task.reuse_path is not None and task.reuse_path.is_file():
            return {
                "task_id": task.task_id,
                "endpoint": task.endpoint,
                "seed_type": task.seed_type,
                "value": task.value,
                "status": "reused",
                "raw_ref": str(task.reuse_path.resolve()),
                "source": "existing_local_pdns",
                "attempts": 0,
                "elapsed_seconds": 0.0,
                "finished_at": datetime.now(UTC).isoformat(),
            }
        http_status, payload, attempts, elapsed = requester(task)
        if http_status == 200:
            source = ENDPOINT_SOURCE[task.endpoint]
            path = store.write(source, task.value, payload, fetched_at)
            return {
                "task_id": task.task_id,
                "endpoint": task.endpoint,
                "seed_type": task.seed_type,
                "value": task.value,
                "status": (
                    "empty" if _is_empty(task.endpoint, payload) else "written"
                ),
                "http_status": http_status,
                "raw_ref": str(path.resolve()),
                "source": source,
                "attempts": attempts,
                "elapsed_seconds": elapsed,
                "finished_at": datetime.now(UTC).isoformat(),
            }
        return {
            "task_id": task.task_id,
            "endpoint": task.endpoint,
            "seed_type": task.seed_type,
            "value": task.value,
            "status": (
                "retry_exhausted"
                if http_status in {0, 429} or http_status >= 500
                else "terminal_error"
            ),
            "http_status": http_status,
            "error": payload,
            "attempts": attempts,
            "elapsed_seconds": elapsed,
            "finished_at": datetime.now(UTC).isoformat(),
        }

    pending = []
    for task in tasks:
        if task.task_id in completed:
            counts["already_terminal"] += 1
        else:
            pending.append(task)

    with (
        ledger_path.open("a", encoding="utf-8", newline="\n") as ledger,
        ThreadPoolExecutor(max_workers=max(1, workers)) as pool,
    ):
        iterator = iter(pending)
        active: dict[Future[dict[str, Any]], EnrichmentTask] = {}

        def submit_next() -> bool:
            try:
                task = next(iterator)
            except StopIteration:
                return False
            active[pool.submit(process, task)] = task
            return True

        for _ in range(max(1, workers)):
            if not submit_next():
                break
        while active:
            finished, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in finished:
                task = active.pop(future)
                row = future.result()
                ledger.write(
                    json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                )
                ledger.flush()
                counts[row["status"]] += 1
                endpoint_counts[task.endpoint][row["status"]] += 1
                submit_next()

    all_rows = list(_iter_jsonl(ledger_path))
    total_counts = Counter(str(row.get("status")) for row in all_rows)
    report = {
        "contract": "trail_otx_enrichment_raw_v1",
        "phase": phase,
        "requested_tasks": len(tasks),
        "new_terminal_counts": dict(sorted(counts.items())),
        "all_terminal_counts": dict(sorted(total_counts.items())),
        "new_endpoint_counts": {
            endpoint: dict(sorted(values.items()))
            for endpoint, values in sorted(endpoint_counts.items())
        },
        "fetched_at": fetched_at,
        "generated_at": datetime.now(UTC).isoformat(),
        "pilot_safe_for_full": (
            total_counts["retry_exhausted"] == 0
            and not any(
                int(row.get("http_status") or 0) in {401, 403} for row in all_rows
            )
        ),
    }
    _write_json(output_root / f"{phase}_enrichment_report.json", report)
    return report


def httpx_requester(
    client: Any,
    *,
    max_attempts: int = 5,
    base_delay: float = 1.0,
) -> Callable[[EnrichmentTask], tuple[int, Any, int, float]]:
    """Create a bounded-retry requester without exposing credentials."""

    def request(task: EnrichmentTask) -> tuple[int, Any, int, float]:
        started = time.monotonic()
        last_status = 0
        last_error: Any = {"kind": "not_attempted"}
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.get(task.api_path)
                last_status = int(response.status_code)
                if last_status == 200:
                    return (
                        200,
                        response.json(),
                        attempt,
                        time.monotonic() - started,
                    )
                last_error = {
                    "kind": "http_error",
                    "status": last_status,
                    "body_sample": response.text[:500],
                }
                if last_status not in {429, 500, 502, 503, 504}:
                    break
                retry_after = response.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else base_delay * (2 ** (attempt - 1))
                )
            except Exception as exc:  # network boundary; serialized below
                last_status = 0
                last_error = {"kind": type(exc).__name__, "message": str(exc)}
                delay = base_delay * (2 ** (attempt - 1))
            if attempt < max_attempts:
                time.sleep(min(delay, 30.0))
        return (
            last_status,
            last_error,
            max_attempts,
            time.monotonic() - started,
        )

    return request
