"""Collect OTX raw data using MITRE ATT&CK actor names and aliases.

This is the canonical actor-centric OTX raw collector:

1. Read MITRE ATT&CK intrusion-set objects from the local STIX bundle.
2. Build a deduplicated actor/alias OTX query list.
3. Store raw OTX search response pages under RawStore source ``otx_search``.
4. Fetch each discovered pulse detail and store it under RawStore source ``otx``.
5. Fetch pulse indicator pages and store them under RawStore source
   ``otx_indicator_page``.

Run artifacts under ``data/raw/otx_collection_runs/<run_id>`` are collection
audit data only. They are not OTX source metadata and should not be used as
knowledge-layer labels.
"""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.connectors.otx_actor_collection import (
    OtxQuery,
    indicator_page_source_id,
    mitre_actor_seeds_from_bundle,
    normalize_query,
    otx_queries_from_mitre_actor_seeds,
    search_raw_source_id_for_query,
    search_results,
)
from rag_cti.store.raw_store import RawStore

BASE_URL = "https://otx.alienvault.com/api/v1"
DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
DEFAULT_RUNS_ROOT = Path("data/raw/otx_collection_runs")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _run_id_from_timestamp(value: str) -> str:
    dt = datetime.fromisoformat(value)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_json_if_missing(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        return
    _write_json(path, value)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _load_candidate_events(path: Path) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return candidates
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if isinstance(row, dict) and row.get("pulse_id"):
            candidates[str(row["pulse_id"])] = row
    return candidates


def _load_candidates_from_discovery(path: Path) -> dict[str, dict[str, Any]]:
    """Rebuild the candidate manifest from legacy per-path discovery rows."""

    candidates: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return candidates
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if not isinstance(row, dict) or not row.get("pulse_id"):
            continue
        pulse_id = str(row["pulse_id"])
        candidate = candidates.setdefault(
            pulse_id,
            {
                "pulse_id": pulse_id,
                "pulse_name": row.get("pulse_name", ""),
                "pulse_created": row.get("pulse_created", ""),
                "pulse_modified": row.get("pulse_modified", ""),
                "discovery_paths": [],
            },
        )
        discovery_path = {
            "query": row.get("query", ""),
            "query_normalized": row.get("query_normalized", ""),
            "query_actors": row.get("query_actors", []),
            "search_page": row.get("search_page"),
            "search_rank": row.get("search_rank"),
            "search_raw_ref": row.get("search_raw_ref", {}),
        }
        key = json.dumps(discovery_path, ensure_ascii=False, sort_keys=True)
        existing = {
            json.dumps(item, ensure_ascii=False, sort_keys=True)
            for item in candidate["discovery_paths"]
        }
        if key not in existing:
            candidate["discovery_paths"].append(discovery_path)
    return candidates


def _write_candidate_events(path: Path, candidates: dict[str, dict[str, Any]]) -> None:
    for candidate in candidates.values():
        paths = candidate.get("discovery_paths")
        if isinstance(paths, list):
            deduplicated: dict[tuple[str, int, int, str], dict[str, Any]] = {}
            for item in paths:
                key = (
                    str(item.get("query_normalized", "")),
                    int(item.get("search_page", 0) or 0),
                    int(item.get("search_rank", 0) or 0),
                    str((item.get("search_raw_ref") or {}).get("source_id", "")),
                )
                previous = deduplicated.get(key)
                if previous is None or (
                    previous.get("search_page_limit") is None
                    and item.get("search_page_limit") is not None
                ):
                    deduplicated[key] = item
            paths[:] = deduplicated.values()
            paths.sort(
                key=lambda item: (
                    str(item.get("query_normalized", "")),
                    int(item.get("search_page", 0) or 0),
                    int(item.get("search_rank", 0) or 0),
                )
            )
    _write_jsonl(path, [candidates[key] for key in sorted(candidates)])


def _discovery_keys(path: Path) -> set[tuple[str, str, int, int]]:
    if not path.exists():
        return set()
    keys: set[tuple[str, str, int, int]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            keys.add(
                (
                    str(row.get("pulse_id", "")),
                    str(row.get("query_normalized", "")),
                    int(row.get("search_page", 0)),
                    int(row.get("search_rank", 0)),
                )
            )
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return keys


def _record_query_terminal(
    path: Path, *, run_id: str, query: OtxQuery, page: int, page_limit: int,
    status: str, fetched_at: str
) -> None:
    rows: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("query_normalized"):
                rows[str(row["query_normalized"])] = row
    rows[query.query_normalized] = {
        "run_id": run_id,
        "query": query.query,
        "query_normalized": query.query_normalized,
        "query_actors": _query_actors(query),
        "last_page": page,
        "search_page_limit": page_limit,
        "status": status,
        "fetched_at": fetched_at,
    }
    _write_jsonl(path, [rows[key] for key in sorted(rows)])


def _merge_candidate(
    candidates: dict[str, dict[str, Any]],
    *,
    pulse_meta: dict[str, Any],
    query: OtxQuery,
    page: int,
    page_limit: int,
    rank: int,
    search_raw_ref: dict[str, Any],
) -> bool:
    pulse_id = str(pulse_meta["id"])
    is_new_candidate = pulse_id not in candidates
    candidate = candidates.setdefault(
        pulse_id,
        {
            "pulse_id": pulse_id,
            "pulse_name": pulse_meta.get("name", ""),
            "pulse_created": pulse_meta.get("created", ""),
            "pulse_modified": pulse_meta.get("modified", ""),
            "discovery_paths": [],
        },
    )
    path = {
        "query": query.query,
        "query_normalized": query.query_normalized,
        "query_actors": _query_actors(query),
        "search_page": page,
        "search_page_limit": page_limit,
        "search_rank": rank,
        "search_raw_ref": search_raw_ref,
    }
    key = (query.query_normalized, page, rank, search_raw_ref["source_id"])
    existing = {
        (
            item.get("query_normalized"),
            item.get("search_page"),
            item.get("search_rank"),
            item.get("search_raw_ref", {}).get("source_id"),
        )
        for item in candidate["discovery_paths"]
    }
    if key not in existing:
        candidate["discovery_paths"].append(path)
        return True
    return is_new_candidate


def _historical_query_paging(
    search_pages_path: Path, manifest_path: Path
) -> dict[str, tuple[int, bool]]:
    """Return query -> (page limit, uses legacy raw/checkpoint identity)."""

    legacy_limit = 20
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            value = manifest.get("params", {}).get("search_page_limit")
            if isinstance(value, int) and value > 0:
                legacy_limit = value
        except (AttributeError, json.JSONDecodeError, OSError):
            pass
    paging: dict[str, tuple[int, bool]] = {}
    if not search_pages_path.exists():
        return paging
    for line in search_pages_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        query = str(row.get("query_normalized") or "")
        if not query:
            continue
        value = row.get("search_page_limit")
        explicit_limit = value if isinstance(value, int) and value > 0 else legacy_limit
        previous = paging.get(query)
        uses_legacy_identity = value is None or (previous[1] if previous else False)
        if previous is not None and previous[0] != explicit_limit:
            raise ValueError(
                f"query {query!r} has conflicting search page limits: "
                f"{previous[0]} and {explicit_limit}"
            )
        paging[query] = (explicit_limit, uses_legacy_identity)
    return paging


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _OtxApiKeyPool:
    def __init__(
        self,
        keys: list[str],
        *,
        cooldown_seconds: float = 30.0,
        clock: Any = time.monotonic,
        sleep: Any = time.sleep,
    ) -> None:
        self.keys = keys
        self.cooldown_seconds = cooldown_seconds
        self.clock = clock
        self.sleep = sleep
        self.cursor = 0
        self.cooldown_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def next_key(self) -> str:
        while True:
            with self._lock:
                now = self.clock()
                for _ in self.keys:
                    key = self.keys[self.cursor]
                    self.cursor = (self.cursor + 1) % len(self.keys)
                    if self.cooldown_until.get(key, 0.0) <= now:
                        return key
                delay = max(0.0, min(self.cooldown_until.values()) - now)
            self.sleep(delay)

    def cool_down(self, key: str) -> None:
        with self._lock:
            self.cooldown_until[key] = self.clock() + self.cooldown_seconds


def _get_json(client: httpx.Client, path: str, **params: Any) -> dict[str, Any]:
    last_error: Exception | None = None
    key_pool = getattr(client, "_otx_key_pool", None)
    max_attempts = max(3, len(key_pool.keys) * 3) if key_pool is not None else 3
    for attempt in range(1, max_attempts + 1):
        try:
            key = key_pool.next_key() if key_pool is not None else ""
            headers = {"X-OTX-API-KEY": key} if key else None
            response = client.get(
                f"{BASE_URL}/{path.lstrip('/')}", params=params, headers=headers
            )
            if response.status_code == 429:
                if key_pool is not None:
                    key_pool.cool_down(key)
                else:
                    time.sleep(10 * attempt)
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("OTX response was not a JSON object")
            return payload
        except Exception as exc:  # noqa: BLE001 - checkpoint and continue at caller.
            last_error = exc
            time.sleep(2 * attempt)
    raise RuntimeError(str(last_error) if last_error else "OTX request failed")


def _api_keys() -> list[str]:
    single = os.environ.get("OTX_API_KEY", "").strip()
    if single:
        return [single]
    multi = os.environ.get("OTX_API_KEYS", "")
    return list(dict.fromkeys(value.strip() for value in multi.split(",") if value.strip()))


def _api_key() -> str:
    keys = _api_keys()
    return keys[0] if keys else ""


def _select_seeds(seeds: list[Any], actor_filters: list[str], max_actors: int) -> list[Any]:
    if actor_filters:
        wanted = {value.casefold() for value in actor_filters}
        seeds = [
            seed
            for seed in seeds
            if seed.name.casefold() in wanted
            or seed.mitre_id.casefold() in wanted
            or seed.stix_id.casefold() in wanted
        ]
    if max_actors:
        seeds = seeds[:max_actors]
    return seeds


def _within_window(row: dict[str, Any], since: str, until: str) -> bool:
    created = str(row.get("created", "") or "")
    if since and created < since:
        return False
    if until and created >= until:
        return False
    return True


def _query_actors(query: OtxQuery) -> list[dict[str, Any]]:
    return [actor.to_dict() for actor in query.actors]


def _raw_ref(source: str, source_id: str, fetched_at: str, path: Path | None = None) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "connector_source": source,
        "source": source,
        "source_id": source_id,
        "fetched_at": fetched_at,
    }
    if path is not None:
        ref["path"] = str(path)
    return ref


def _latest_raw_refs(root: Path, source: str) -> dict[str, dict[str, Any]]:
    """Index the latest persisted RawStore version for run-scoped reuse records."""

    refs: dict[str, dict[str, Any]] = {}
    source_dir = root / source
    if not source_dir.exists():
        return refs
    for raw_path in source_dir.glob("*/*.json"):
        try:
            record = json.loads(raw_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        source_id = str(record.get("source_id", "") or "")
        fetched_at = str(record.get("fetched_at", "") or "")
        if not source_id or not fetched_at:
            continue
        previous = refs.get(source_id)
        if previous is None or fetched_at > str(previous["fetched_at"]):
            refs[source_id] = _raw_ref(source, source_id, fetched_at, raw_path)
    return refs


def _saved_pulse_detail_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    saved: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("kind") == "pulse_detail" and row.get("pulse_id"):
            saved.add(str(row["pulse_id"]))
    return saved


def _record_reused_pulse_detail(
    *,
    pulse_id: str,
    raw_refs: dict[str, dict[str, Any]],
    saved_pulse_detail_ids: set[str],
    saved_files_path: Path,
    run_id: str,
    checkpoint_path: Path,
    checkpoint: dict[str, Any],
    checkpoint_members: dict[str, set[str]],
) -> None:
    raw_ref = raw_refs.get(pulse_id)
    if raw_ref is None:
        return
    if pulse_id not in saved_pulse_detail_ids:
        _record_saved(
            path=saved_files_path,
            run_id=run_id,
            fetched_at=str(raw_ref["fetched_at"]),
            kind="pulse_detail",
            pulse_id=pulse_id,
            raw_ref=raw_ref,
        )
        saved_pulse_detail_ids.add(pulse_id)
    _checkpoint_add(checkpoint, checkpoint_members, "completed_pulse_details", pulse_id)
    _checkpoint_add(checkpoint, checkpoint_members, "saved_pulse_ids", pulse_id)
    _save_checkpoint(checkpoint_path, checkpoint)


def _empty_checkpoint(run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "updated_at": "",
        "completed_query_pages": [],
        "completed_pulse_details": [],
        "completed_indicator_pages": [],
        "skipped_indicator_endpoints": [],
        "failed_requests": [],
        "discovered_pulse_ids": [],
        "saved_pulse_ids": [],
    }


def _load_checkpoint(path: Path, run_id: str) -> dict[str, Any]:
    if not path.exists():
        return _empty_checkpoint(run_id)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _empty_checkpoint(run_id)
    if not isinstance(value, dict):
        return _empty_checkpoint(run_id)
    base = _empty_checkpoint(run_id)
    base.update(value)
    base["run_id"] = str(base.get("run_id") or run_id)
    for key in (
        "completed_query_pages",
        "completed_pulse_details",
        "completed_indicator_pages",
        "skipped_indicator_endpoints",
        "failed_requests",
        "discovered_pulse_ids",
        "saved_pulse_ids",
    ):
        if not isinstance(base.get(key), list):
            base[key] = []
    return base


def _checkpoint_sets(state: dict[str, Any]) -> dict[str, set[str]]:
    return {
        "completed_query_pages": {str(value) for value in state["completed_query_pages"]},
        "completed_pulse_details": {str(value) for value in state["completed_pulse_details"]},
        "completed_indicator_pages": {
            str(value) for value in state["completed_indicator_pages"]
        },
        "skipped_indicator_endpoints": {
            str(value) for value in state["skipped_indicator_endpoints"]
        },
        "discovered_pulse_ids": {str(value) for value in state["discovered_pulse_ids"]},
        "saved_pulse_ids": {str(value) for value in state["saved_pulse_ids"]},
    }


def _save_checkpoint(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _utc_now()
    _write_json(path, state)


def _checkpoint_add(
    state: dict[str, Any],
    sets: dict[str, set[str]],
    key: str,
    value: str,
) -> None:
    if value in sets[key]:
        return
    sets[key].add(value)
    state[key].append(value)


def _checkpoint_failure(
    state: dict[str, Any],
    *,
    kind: str,
    key: str,
    error: str,
    fetched_at: str,
    context: dict[str, Any] | None = None,
) -> None:
    row = {
        "kind": kind,
        "key": key,
        "error": error,
        "fetched_at": fetched_at,
    }
    if context:
        row["context"] = context
    state["failed_requests"].append(row)


def _query_list_doc(
    *,
    generated_at: str,
    bundle: Path,
    bundle_sha256: str,
    actor_count: int,
    queries: list[OtxQuery],
) -> dict[str, Any]:
    alias_record_count = 0
    for query in queries:
        alias_record_count += sum(1 for actor in query.actors if actor.matched_from == "alias")
    return {
        "generated_at": generated_at,
        "mitre_bundle": {
            "path": str(bundle),
            "sha256": bundle_sha256,
            "source": "local_mitre_raw",
        },
        "actor_count": actor_count,
        "alias_record_count": alias_record_count,
        "deduplicated_query_count": len(queries),
        "queries": [query.to_dict() for query in queries],
        "note": (
            "MITRE-derived query associations are collection input only; they are "
            "not OTX actor labels or graph facts."
        ),
    }


def _collection_manifest(
    *,
    run_id: str,
    started_at: str,
    query_count: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "started_at": started_at,
        "collector": "otx_mitre_actor_raw_collector",
        "input_query_list": "mitre_actor_query_list.json",
        "otx_endpoints": [
            "/api/v1/search/pulses",
            "/api/v1/pulses/{pulse_id}",
            "/api/v1/pulses/{pulse_id}/indicators",
        ],
        "params": {
            "actor_filters": args.actor,
            "query_count": query_count,
            "since": args.since or None,
            "until": args.until or None,
            "max_actors": args.max_actors,
            "max_queries": args.max_queries,
            "max_pulses": args.max_pulses,
            "max_search_pages": args.max_search_pages,
            "max_indicator_pages": args.max_indicator_pages,
            "search_page_limit": args.search_page_limit,
            "discovery_workers": int(getattr(args, "discovery_workers", 2)),
            "indicator_page_limit": args.indicator_page_limit,
            "indicator_endpoint_full_threshold": args.indicator_endpoint_full_threshold,
            "oversized_indicator_sample_pages": args.oversized_indicator_sample_pages,
            "skip_indicator_pages": args.skip_indicator_pages,
            "refetch_existing_details": args.refetch_existing_details,
            "phase": getattr(args, "phase", "all"),
        },
        "note": "Run artifacts are collection audit only, not OTX source metadata.",
    }


def _record_invocation(
    *,
    path: Path,
    run_id: str,
    started_at: str,
    query_count: int,
    args: argparse.Namespace,
) -> None:
    _append_jsonl(
        path,
        {
            "run_id": run_id,
            "started_at": started_at,
            "collector": "otx_mitre_actor_raw_collector",
            "params": {
                "actor_filters": args.actor,
                "query_count": query_count,
                "since": args.since or None,
                "until": args.until or None,
                "max_actors": args.max_actors,
                "max_queries": args.max_queries,
                "max_pulses": args.max_pulses,
                "max_search_pages": args.max_search_pages,
                "max_indicator_pages": args.max_indicator_pages,
                "search_page_limit": args.search_page_limit,
                "discovery_workers": int(getattr(args, "discovery_workers", 2)),
                "indicator_page_limit": args.indicator_page_limit,
                "indicator_endpoint_full_threshold": args.indicator_endpoint_full_threshold,
                "oversized_indicator_sample_pages": args.oversized_indicator_sample_pages,
                "skip_indicator_pages": args.skip_indicator_pages,
                "refetch_existing_details": args.refetch_existing_details,
                "phase": getattr(args, "phase", "all"),
            },
            "note": (
                "Invocation audit only. This records resume-time parameters, "
                "including phase flags that may differ from the initial manifest."
            ),
        },
    )


def _run_paths(args: argparse.Namespace, started_at: str) -> tuple[str, Path]:
    if args.run_dir:
        run_dir = args.run_dir
        run_id = args.run_id or run_dir.name
        return run_id, run_dir
    run_id = args.run_id or _run_id_from_timestamp(started_at)
    return run_id, args.runs_root / run_id


def _record_saved(
    *,
    path: Path,
    run_id: str,
    fetched_at: str,
    kind: str,
    raw_ref: dict[str, Any],
    status: str = "ok",
    pulse_id: str = "",
    query: OtxQuery | None = None,
    page: int | None = None,
) -> None:
    row: dict[str, Any] = {
        "run_id": run_id,
        "fetched_at": fetched_at,
        "kind": kind,
        "status": status,
        "raw_ref": raw_ref,
    }
    if pulse_id:
        row["pulse_id"] = pulse_id
    if query is not None:
        row["query"] = query.query
        row["query_normalized"] = query.query_normalized
        row["query_actors"] = _query_actors(query)
    if page is not None:
        row["page"] = page
    _append_jsonl(path, row)


def _record_indicator_endpoint_skip(
    *,
    path: Path,
    run_id: str,
    fetched_at: str,
    pulse_id: str,
    page_limit: int,
    indicator_count: int,
    fetched_pages: int,
    fetched_results: int,
    full_threshold: int,
    sample_pages: int,
    reason: str,
) -> None:
    _append_jsonl(
        path,
        {
            "run_id": run_id,
            "fetched_at": fetched_at,
            "pulse_id": pulse_id,
            "reason": reason,
            "page_limit": page_limit,
            "indicator_count": indicator_count,
            "fetched_pages": fetched_pages,
            "fetched_results": fetched_results,
            "indicator_endpoint_full_threshold": full_threshold,
            "oversized_indicator_sample_pages": sample_pages,
            "note": (
                "Endpoint enrichment was intentionally partial by collection "
                "policy; pulse detail raw remains the core IOC source."
            ),
        },
    )


def _detail_indicator_count(detail: Any) -> int:
    if not isinstance(detail, dict):
        return 0
    indicators = detail.get("indicators")
    return len(indicators) if isinstance(indicators, list) else 0


def _fetch_discovery_query(
    query: OtxQuery,
    *,
    page_limit: int,
    legacy_identity: bool,
    max_pages: int,
    completed_pages: set[str],
    store: RawStore,
    key_pool: _OtxApiKeyPool,
    page_delay: float,
) -> list[dict[str, Any]]:
    """Fetch one query serially without mutating collection artifacts."""

    pages: list[dict[str, Any]] = []
    with httpx.Client(timeout=60.0) as client:
        client._otx_key_pool = key_pool  # type: ignore[attr-defined]
        for page in range(1, max_pages + 1):
            source_id = search_raw_source_id_for_query(
                query.query_normalized,
                page,
                None if legacy_identity else page_limit,
            )
            key = (
                f"{query.query_normalized}:{page}"
                if legacy_identity
                else f"{query.query_normalized}:limit={page_limit}:page={page}"
            )
            payload = store.latest("otx_search", source_id) if key in completed_pages else None
            cached = payload is not None
            try:
                if payload is None:
                    payload = _get_json(
                        client,
                        "search/pulses",
                        q=query.query,
                        page=page,
                        limit=page_limit,
                        sort="-modified",
                    )
            except Exception as exc:  # noqa: BLE001
                pages.append(
                    {"page": page, "source_id": source_id, "key": key, "error": str(exc)}
                )
                break
            pages.append(
                {
                    "page": page,
                    "source_id": source_id,
                    "key": key,
                    "payload": payload,
                    "cached": cached,
                }
            )
            if not payload.get("next") or page == max_pages:
                break
            if page_delay:
                time.sleep(page_delay)
    return pages


def _fetch_indicator_pages(
    *,
    client: httpx.Client,
    store: RawStore,
    run_id: str,
    checkpoint_path: Path,
    checkpoint: dict[str, Any],
    checkpoint_members: dict[str, set[str]],
    saved_files_path: Path,
    skipped_indicator_pages_path: Path,
    pulse_id: str,
    fetched_at: str,
    page_limit: int,
    max_pages: int,
    full_threshold: int,
    oversized_sample_pages: int,
    page_delay: float,
    stats: dict[str, int],
) -> int:
    written = 0
    page = 1
    fetched_results = 0
    policy_key = (
        f"{pulse_id}:limit={page_limit}:"
        f"threshold={full_threshold}:sample_pages={oversized_sample_pages}"
    )
    if policy_key in checkpoint_members["skipped_indicator_endpoints"]:
        stats["indicator_endpoints_skipped_by_policy_existing"] += 1
        return 0
    while True:
        if max_pages and page > max_pages:
            break
        source_id = indicator_page_source_id(pulse_id, page, page_limit)
        key = f"{pulse_id}:limit={page_limit}:page={page}"
        payload: dict[str, Any] | None = None
        if key in checkpoint_members["completed_indicator_pages"]:
            payload = store.latest("otx_indicator_page", source_id)
            if payload is not None:
                stats["indicator_pages_skipped_completed"] += 1
        if payload is None:
            try:
                payload = _get_json(
                    client,
                    f"pulses/{pulse_id}/indicators",
                    limit=page_limit,
                    page=page,
                )
                raw_path = store.write("otx_indicator_page", source_id, payload, fetched_at)
                _checkpoint_add(
                    checkpoint,
                    checkpoint_members,
                    "completed_indicator_pages",
                    key,
                )
                _record_saved(
                    path=saved_files_path,
                    run_id=run_id,
                    fetched_at=fetched_at,
                    kind="indicator_page",
                    pulse_id=pulse_id,
                    page=page,
                    raw_ref=_raw_ref("otx_indicator_page", source_id, fetched_at, raw_path),
                )
                _save_checkpoint(checkpoint_path, checkpoint)
                written += 1
            except Exception as exc:  # noqa: BLE001 - preserve partial progress.
                stats["errors"] += 1
                _checkpoint_failure(
                    checkpoint,
                    kind="indicator_page",
                    key=key,
                    error=str(exc),
                    fetched_at=fetched_at,
                    context={"pulse_id": pulse_id, "page": page},
                )
                _save_checkpoint(checkpoint_path, checkpoint)
                break

        results = payload.get("results")
        result_count = len(results) if isinstance(results, list) else 0
        fetched_results += result_count
        endpoint_count = payload.get("count")
        endpoint_total = endpoint_count if isinstance(endpoint_count, int) else 0
        if (
            full_threshold
            and endpoint_total > full_threshold
            and page >= max(1, oversized_sample_pages)
            and payload.get("next")
        ):
            if policy_key not in checkpoint_members["skipped_indicator_endpoints"]:
                _record_indicator_endpoint_skip(
                    path=skipped_indicator_pages_path,
                    run_id=run_id,
                    fetched_at=fetched_at,
                    pulse_id=pulse_id,
                    page_limit=page_limit,
                    indicator_count=endpoint_total,
                    fetched_pages=page,
                    fetched_results=fetched_results,
                    full_threshold=full_threshold,
                    sample_pages=oversized_sample_pages,
                    reason="indicator_count_exceeds_policy_threshold",
                )
                _checkpoint_add(
                    checkpoint,
                    checkpoint_members,
                    "skipped_indicator_endpoints",
                    policy_key,
                )
                _save_checkpoint(checkpoint_path, checkpoint)
                stats["indicator_endpoints_skipped_by_policy"] += 1
            break
        if not isinstance(results, list) or not results or not payload.get("next"):
            break
        page += 1
        if page_delay:
            time.sleep(page_delay)
    return written


def _run_parallel_discovery(
    *,
    args: argparse.Namespace,
    queries: list[OtxQuery],
    store: RawStore,
    key_pool: _OtxApiKeyPool,
    historical_query_paging: dict[str, tuple[int, bool]],
    checkpoint: dict[str, Any],
    checkpoint_members: dict[str, set[str]],
    checkpoint_path: Path,
    existing_search_raw_refs: dict[str, dict[str, Any]],
    run_id: str,
    fetched_at: str,
    started_at: str,
    stats: dict[str, int],
    run_dir: Path,
    search_pages_path: Path,
    discovery_path: Path,
    query_terminal_states_path: Path,
    saved_files_path: Path,
    skipped_pulses_path: Path,
    candidate_events_path: Path,
    candidates: dict[str, dict[str, Any]],
    discovery_keys: set[tuple[str, str, int, int]],
    seen_pulses: set[str],
) -> int:
    """Fetch queries concurrently and serialize every mutation in this thread."""

    workers = max(1, int(getattr(args, "discovery_workers", 2)))

    def submit(
        executor: concurrent.futures.ThreadPoolExecutor, query: OtxQuery
    ) -> concurrent.futures.Future[list[dict[str, Any]]]:
        historical = historical_query_paging.get(query.query_normalized)
        limit = historical[0] if historical else args.search_page_limit
        legacy = bool(historical and historical[1])
        future = executor.submit(
            _fetch_discovery_query,
            query,
            page_limit=limit,
            legacy_identity=legacy,
            max_pages=args.max_search_pages,
            completed_pages=set(checkpoint_members["completed_query_pages"]),
            store=store,
            key_pool=key_pool,
            page_delay=args.page_delay,
        )
        future.query_context = (query, limit)  # type: ignore[attr-defined]
        return future

    query_iter = iter(queries)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        pending: set[concurrent.futures.Future[list[dict[str, Any]]]] = set()
        for _ in range(workers):
            query = next(query_iter, None)
            if query is not None:
                pending.add(submit(executor, query))
        while pending:
            done, pending = concurrent.futures.wait(
                pending, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                query, page_limit = future.query_context  # type: ignore[attr-defined]
                try:
                    pages = future.result()
                except Exception as exc:  # noqa: BLE001
                    pages = [{"page": 1, "key": query.query_normalized, "error": str(exc)}]
                for item in pages:
                    page = int(item["page"])
                    search_key = str(item["key"])
                    if "error" in item:
                        stats["errors"] += 1
                        _checkpoint_failure(
                            checkpoint,
                            kind="search",
                            key=search_key,
                            error=str(item["error"]),
                            fetched_at=fetched_at,
                            context={"query": query.query, "page": page},
                        )
                        _append_jsonl(
                            search_pages_path,
                            {
                                "run_id": run_id, "fetched_at": fetched_at,
                                "query": query.query, "query_normalized": query.query_normalized,
                                "query_actors": _query_actors(query), "page": page,
                                "search_page_limit": page_limit, "status": "error",
                                "error": str(item["error"]),
                            },
                        )
                        _save_checkpoint(checkpoint_path, checkpoint)
                        break
                    payload = item["payload"]
                    source_id = str(item["source_id"])
                    if item["cached"]:
                        stats["search_pages_skipped_completed"] += 1
                        raw_ref = existing_search_raw_refs.get(
                            source_id, _raw_ref("otx_search", source_id, fetched_at)
                        )
                    else:
                        raw_path = store.write("otx_search", source_id, payload, fetched_at)
                        raw_ref = _raw_ref("otx_search", source_id, fetched_at, raw_path)
                        _record_saved(
                            path=saved_files_path, run_id=run_id, fetched_at=fetched_at,
                            kind="search_page", raw_ref=raw_ref, query=query, page=page,
                        )
                        stats["search_pages_written"] += 1
                    rows = search_results(payload)
                    _append_jsonl(
                        search_pages_path,
                        {
                            "run_id": run_id, "fetched_at": fetched_at,
                            "query": query.query, "query_normalized": query.query_normalized,
                            "query_actors": _query_actors(query), "page": page,
                            "search_page_limit": page_limit, "status": "ok",
                            "result_count": len(rows), "has_next": bool(payload.get("next")),
                            "raw_ref": raw_ref,
                        },
                    )
                    dirty = False
                    for rank, pulse_meta in enumerate(rows, start=1):
                        pulse_id = str(pulse_meta.get("id", "") or "")
                        if not pulse_id:
                            continue
                        if not _within_window(pulse_meta, args.since, args.until):
                            stats["skipped_pulses"] += 1
                            _append_jsonl(
                                skipped_pulses_path,
                                {
                                    "run_id": run_id, "fetched_at": fetched_at,
                                    "pulse_id": pulse_id, "pulse_name": pulse_meta.get("name", ""),
                                    "reason": "outside_date_window", "since": args.since or None,
                                    "until": args.until or None,
                                    "pulse_created": pulse_meta.get("created", ""),
                                    "pulse_modified": pulse_meta.get("modified", ""),
                                    "query": query.query, "query_normalized": query.query_normalized,
                                    "query_actors": _query_actors(query), "search_page": page,
                                    "search_rank": rank, "search_raw_ref": raw_ref,
                                },
                            )
                            continue
                        stats["discoveries"] += 1
                        dirty |= _merge_candidate(
                            candidates, pulse_meta=pulse_meta, query=query, page=page,
                            page_limit=page_limit, rank=rank, search_raw_ref=raw_ref,
                        )
                        discovery_key = (pulse_id, query.query_normalized, page, rank)
                        if discovery_key not in discovery_keys:
                            _append_jsonl(
                                discovery_path,
                                {
                                    "run_id": run_id,
                                    "collection_record_type": "otx_mitre_actor_search_discovery",
                                    "fetched_at": fetched_at, "method": "mitre_actor_alias_search",
                                    "query": query.query, "query_normalized": query.query_normalized,
                                    "query_actors": _query_actors(query), "search_page": page,
                                    "search_page_limit": page_limit, "search_rank": rank,
                                    "pulse_id": pulse_id, "pulse_name": pulse_meta.get("name", ""),
                                    "pulse_created": pulse_meta.get("created", ""),
                                    "pulse_modified": pulse_meta.get("modified", ""),
                                    "in_date_window": True, "search_raw_ref": raw_ref,
                                    "note": "Collection audit only; not an OTX actor label or graph fact.",
                                },
                            )
                            discovery_keys.add(discovery_key)
                        if pulse_id not in seen_pulses:
                            seen_pulses.add(pulse_id)
                            _checkpoint_add(
                                checkpoint, checkpoint_members, "discovered_pulse_ids", pulse_id
                            )
                    stats["unique_pulses_discovered"] = len(seen_pulses)
                    if dirty:
                        _write_candidate_events(candidate_events_path, candidates)
                    if not payload.get("next"):
                        _checkpoint_add(
                            checkpoint, checkpoint_members, "completed_query_pages", search_key
                        )
                        _record_query_terminal(
                            query_terminal_states_path, run_id=run_id, query=query, page=page,
                            page_limit=page_limit, status="complete", fetched_at=fetched_at,
                        )
                    elif page == args.max_search_pages:
                        checkpoint_members["completed_query_pages"].discard(search_key)
                        checkpoint["completed_query_pages"] = [
                            value for value in checkpoint["completed_query_pages"]
                            if str(value) != search_key
                        ]
                        _record_query_terminal(
                            query_terminal_states_path, run_id=run_id, query=query, page=page,
                            page_limit=page_limit, status="truncated_page_cap", fetched_at=fetched_at,
                        )
                    else:
                        _checkpoint_add(
                            checkpoint, checkpoint_members, "completed_query_pages", search_key
                        )
                    _save_checkpoint(checkpoint_path, checkpoint)
                next_query = next(query_iter, None)
                if next_query is not None:
                    pending.add(submit(executor, next_query))
    _write_summary(run_dir, run_id, started_at, stats)
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


def run(args: argparse.Namespace) -> int:
    api_keys = _api_keys()
    if not api_keys:
        print("ERROR: OTX_API_KEY or OTX_API_KEYS not set in .env or environment", file=sys.stderr)
        return 1
    if not args.bundle.exists():
        print(f"ERROR: MITRE bundle not found: {args.bundle}", file=sys.stderr)
        return 1

    started_at = _utc_now()
    run_id, run_dir = _run_paths(args, started_at)
    run_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = run_dir / "checkpoint.json"
    search_pages_path = run_dir / "search_pages.jsonl"
    discovery_path = run_dir / "discovery_metadata.jsonl"
    query_terminal_states_path = run_dir / "query_terminal_states.jsonl"
    saved_files_path = run_dir / "saved_files.jsonl"
    invocations_path = run_dir / "collection_invocations.jsonl"
    skipped_pulses_path = run_dir / "skipped_pulses.jsonl"
    skipped_indicator_pages_path = run_dir / "skipped_indicator_pages.jsonl"
    candidate_events_path = run_dir / "candidate_events.jsonl"
    phase = getattr(args, "phase", "all")
    if phase not in {"all", "discovery", "detail", "indicators"}:
        print(f"ERROR: unsupported phase: {phase}", file=sys.stderr)
        return 1
    if phase == "indicators" and args.max_indicator_pages <= 0:
        print("ERROR: indicators phase requires --max-indicator-pages > 0", file=sys.stderr)
        return 1

    with args.bundle.open(encoding="utf-8") as fh:
        bundle = json.load(fh)
    seeds = mitre_actor_seeds_from_bundle(bundle)
    seeds = _select_seeds(seeds, args.actor, args.max_actors)
    if not seeds:
        print("No MITRE actor seeds selected.")
        return 0
    queries = otx_queries_from_mitre_actor_seeds(seeds)
    query_filters = {
        normalize_query(value) for value in getattr(args, "query", []) if value.strip()
    }
    if query_filters:
        available = {query.query_normalized for query in queries}
        unknown = sorted(query_filters - available)
        if unknown:
            print(f"ERROR: OTX query filters not in MITRE query list: {unknown}", file=sys.stderr)
            return 1
        queries = [query for query in queries if query.query_normalized in query_filters]
    if args.max_queries:
        queries = queries[: args.max_queries]
    if not queries:
        print("No OTX queries selected.")
        return 0

    bundle_sha256 = _sha256_file(args.bundle)
    _write_json_if_missing(
        run_dir / "mitre_actor_query_list.json",
        _query_list_doc(
            generated_at=started_at,
            bundle=args.bundle,
            bundle_sha256=bundle_sha256,
            actor_count=len(seeds),
            queries=queries,
        ),
    )
    _write_json_if_missing(
        run_dir / "collection_manifest.json",
        _collection_manifest(
            run_id=run_id,
            started_at=started_at,
            query_count=len(queries),
            args=args,
        ),
    )
    _record_invocation(
        path=invocations_path,
        run_id=run_id,
        started_at=started_at,
        query_count=len(queries),
        args=args,
    )

    store = RawStore(args.raw_root)
    needs_pulse_details = phase in {"all", "detail", "indicators"}
    existing_pulses = set(store.source_ids("otx")) if needs_pulse_details else set()
    existing_pulse_raw_refs = (
        _latest_raw_refs(args.raw_root, "otx") if needs_pulse_details else {}
    )
    existing_search_raw_refs = _latest_raw_refs(args.raw_root, "otx_search")
    historical_query_paging = _historical_query_paging(
        search_pages_path, run_dir / "collection_manifest.json"
    )
    saved_pulse_detail_ids = (
        _saved_pulse_detail_ids(saved_files_path) if needs_pulse_details else set()
    )
    fetched_at = started_at
    checkpoint = _load_checkpoint(checkpoint_path, run_id)
    checkpoint_members = _checkpoint_sets(checkpoint)
    manifest_page_limit = 20
    manifest_path = run_dir / "collection_manifest.json"
    if manifest_path.exists():
        manifest_doc = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_value = manifest_doc.get("params", {}).get("search_page_limit")
        if isinstance(manifest_value, int) and manifest_value > 0:
            manifest_page_limit = manifest_value
    for completed_key in checkpoint_members["completed_query_pages"]:
        if ":limit=" in completed_key or ":" not in completed_key:
            continue
        query_normalized, page_text = completed_key.rsplit(":", 1)
        if page_text.isdigit():
            historical_query_paging.setdefault(
                query_normalized, (manifest_page_limit, True)
            )
    seen_pulses: set[str] = set(checkpoint_members["discovered_pulse_ids"])
    candidates = _load_candidate_events(candidate_events_path)
    discovery_keys = _discovery_keys(discovery_path)
    if not candidates and discovery_path.exists():
        candidates = _load_candidates_from_discovery(discovery_path)
        if candidates:
            _write_candidate_events(candidate_events_path, candidates)
    stats = {
        "actors": len(seeds),
        "queries": len(queries),
        "search_pages_written": 0,
        "search_pages_skipped_completed": 0,
        "discoveries": 0,
        "unique_pulses_discovered": len(seen_pulses),
        "pulse_details_written": 0,
        "pulse_details_skipped_existing": 0,
        "indicator_pages_written": 0,
        "indicator_pages_skipped_completed": 0,
        "indicator_endpoints_skipped_by_policy": 0,
        "indicator_endpoints_skipped_by_policy_existing": 0,
        "indicator_endpoints_pending_by_phase": 0,
        "indicator_endpoints_pending_by_phase_existing": 0,
        "skipped_pulses": 0,
        "errors": 0,
    }

    if (
        phase == "discovery"
        and int(getattr(args, "discovery_workers", 2)) > 1
        and not args.max_pulses
    ):
        return _run_parallel_discovery(
            args=args, queries=queries, store=store, key_pool=_OtxApiKeyPool(api_keys),
            historical_query_paging=historical_query_paging, checkpoint=checkpoint,
            checkpoint_members=checkpoint_members, checkpoint_path=checkpoint_path,
            existing_search_raw_refs=existing_search_raw_refs, run_id=run_id,
            fetched_at=fetched_at, started_at=started_at, stats=stats, run_dir=run_dir,
            search_pages_path=search_pages_path, discovery_path=discovery_path,
            query_terminal_states_path=query_terminal_states_path,
            saved_files_path=saved_files_path, skipped_pulses_path=skipped_pulses_path,
            candidate_events_path=candidate_events_path, candidates=candidates,
            discovery_keys=discovery_keys, seen_pulses=seen_pulses,
        )

    with httpx.Client(timeout=60.0) as client:
        client._otx_key_pool = _OtxApiKeyPool(api_keys)  # type: ignore[attr-defined]
        if phase in {"detail", "indicators"}:
            selected_pulse_ids = sorted(candidates)
            if args.max_pulses:
                selected_pulse_ids = selected_pulse_ids[: args.max_pulses]
            for pulse_id in selected_pulse_ids:
                detail_payload = store.latest("otx", pulse_id)
                if phase == "detail":
                    if detail_payload is not None and not args.refetch_existing_details:
                        stats["pulse_details_skipped_existing"] += 1
                        _record_reused_pulse_detail(
                            pulse_id=pulse_id,
                            raw_refs=existing_pulse_raw_refs,
                            saved_pulse_detail_ids=saved_pulse_detail_ids,
                            saved_files_path=saved_files_path,
                            run_id=run_id,
                            checkpoint_path=checkpoint_path,
                            checkpoint=checkpoint,
                            checkpoint_members=checkpoint_members,
                        )
                        continue
                    try:
                        detail_payload = _get_json(client, f"pulses/{pulse_id}")
                        raw_path = store.write("otx", pulse_id, detail_payload, fetched_at)
                        stats["pulse_details_written"] += 1
                        _checkpoint_add(checkpoint, checkpoint_members, "completed_pulse_details", pulse_id)
                        _checkpoint_add(checkpoint, checkpoint_members, "saved_pulse_ids", pulse_id)
                        _record_saved(
                            path=saved_files_path, run_id=run_id, fetched_at=fetched_at,
                            kind="pulse_detail", pulse_id=pulse_id,
                            raw_ref=_raw_ref("otx", pulse_id, fetched_at, raw_path),
                        )
                        _save_checkpoint(checkpoint_path, checkpoint)
                    except Exception as exc:  # noqa: BLE001
                        stats["errors"] += 1
                        _checkpoint_failure(checkpoint, kind="pulse_detail", key=pulse_id,
                                            error=str(exc), fetched_at=fetched_at,
                                            context={"pulse_id": pulse_id})
                        _save_checkpoint(checkpoint_path, checkpoint)
                else:
                    stats["indicator_pages_written"] += _fetch_indicator_pages(
                        client=client, store=store, run_id=run_id,
                        checkpoint_path=checkpoint_path, checkpoint=checkpoint,
                        checkpoint_members=checkpoint_members, saved_files_path=saved_files_path,
                        skipped_indicator_pages_path=skipped_indicator_pages_path,
                        pulse_id=pulse_id, fetched_at=fetched_at,
                        page_limit=args.indicator_page_limit, max_pages=args.max_indicator_pages,
                        full_threshold=args.indicator_endpoint_full_threshold,
                        oversized_sample_pages=args.oversized_indicator_sample_pages,
                        page_delay=args.page_delay, stats=stats,
                    )
            _write_summary(run_dir, run_id, started_at, stats)
            print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
            return 0

        for query in queries:
            historical_paging = historical_query_paging.get(query.query_normalized)
            query_page_limit = (
                historical_paging[0] if historical_paging else args.search_page_limit
            )
            uses_legacy_search_identity = bool(
                historical_paging and historical_paging[1]
            )
            for page in range(1, args.max_search_pages + 1):
                search_source_id = search_raw_source_id_for_query(
                    query.query_normalized,
                    page,
                    None if uses_legacy_search_identity else query_page_limit,
                )
                search_key = (
                    f"{query.query_normalized}:{page}"
                    if uses_legacy_search_identity
                    else f"{query.query_normalized}:limit={query_page_limit}:page={page}"
                )
                search_raw_ref = _raw_ref("otx_search", search_source_id, fetched_at)
                search_payload: dict[str, Any] | None = None

                if search_key in checkpoint_members["completed_query_pages"]:
                    search_payload = store.latest("otx_search", search_source_id)
                    if search_payload is not None:
                        stats["search_pages_skipped_completed"] += 1
                        search_raw_ref = existing_search_raw_refs.get(
                            search_source_id, search_raw_ref
                        )

                if search_payload is None:
                    try:
                        search_payload = _get_json(
                            client,
                            "search/pulses",
                            q=query.query,
                            page=page,
                            limit=query_page_limit,
                            sort="-modified",
                        )
                        raw_path = store.write("otx_search", search_source_id, search_payload, fetched_at)
                        search_raw_ref = _raw_ref("otx_search", search_source_id, fetched_at, raw_path)
                        _record_saved(
                            path=saved_files_path,
                            run_id=run_id,
                            fetched_at=fetched_at,
                            kind="search_page",
                            raw_ref=search_raw_ref,
                            query=query,
                            page=page,
                        )
                        stats["search_pages_written"] += 1
                    except Exception as exc:  # noqa: BLE001
                        stats["errors"] += 1
                        _checkpoint_failure(
                            checkpoint,
                            kind="search",
                            key=search_key,
                            error=str(exc),
                            fetched_at=fetched_at,
                            context={"query": query.query, "page": page},
                        )
                        _save_checkpoint(checkpoint_path, checkpoint)
                        _append_jsonl(
                            search_pages_path,
                            {
                                "run_id": run_id,
                                "fetched_at": fetched_at,
                                "query": query.query,
                                "query_normalized": query.query_normalized,
                                "query_actors": _query_actors(query),
                                "page": page,
                                "search_page_limit": query_page_limit,
                                "status": "error",
                                "error": str(exc),
                            },
                        )
                        break

                rows = search_results(search_payload)
                _append_jsonl(
                    search_pages_path,
                    {
                        "run_id": run_id,
                        "fetched_at": fetched_at,
                        "query": query.query,
                        "query_normalized": query.query_normalized,
                        "query_actors": _query_actors(query),
                        "page": page,
                        "search_page_limit": query_page_limit,
                        "status": "ok",
                        "result_count": len(rows),
                        "has_next": bool(search_payload.get("next")),
                        "raw_ref": search_raw_ref,
                    },
                )
                page_had_errors = False
                candidate_manifest_dirty = False
                for rank, pulse_meta in enumerate(rows, start=1):
                    pulse_id = str(pulse_meta.get("id", "") or "")
                    if not pulse_id:
                        continue
                    in_date_window = _within_window(pulse_meta, args.since, args.until)
                    if not in_date_window:
                        stats["skipped_pulses"] += 1
                        _append_jsonl(
                            skipped_pulses_path,
                            {
                                "run_id": run_id,
                                "fetched_at": fetched_at,
                                "pulse_id": pulse_id,
                                "pulse_name": pulse_meta.get("name", ""),
                                "reason": "outside_date_window",
                                "since": args.since or None,
                                "until": args.until or None,
                                "pulse_created": pulse_meta.get("created", ""),
                                "pulse_modified": pulse_meta.get("modified", ""),
                                "query": query.query,
                                "query_normalized": query.query_normalized,
                                "query_actors": _query_actors(query),
                                "search_page": page,
                                "search_rank": rank,
                                "search_raw_ref": search_raw_ref,
                            },
                        )
                        continue

                    if (
                        args.max_pulses
                        and pulse_id not in seen_pulses
                        and len(seen_pulses) >= args.max_pulses
                    ):
                        if candidate_manifest_dirty:
                            _write_candidate_events(candidate_events_path, candidates)
                        _write_summary(run_dir, run_id, started_at, stats)
                        print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
                        return 0

                    stats["discoveries"] += 1
                    candidate_manifest_dirty |= _merge_candidate(
                        candidates,
                        pulse_meta=pulse_meta,
                        query=query,
                        page=page,
                        page_limit=query_page_limit,
                        rank=rank,
                        search_raw_ref=search_raw_ref,
                    )
                    discovery_key = (pulse_id, query.query_normalized, page, rank)
                    if discovery_key not in discovery_keys:
                        _append_jsonl(
                            discovery_path,
                            {
                            "run_id": run_id,
                            "collection_record_type": "otx_mitre_actor_search_discovery",
                            "fetched_at": fetched_at,
                            "method": "mitre_actor_alias_search",
                            "query": query.query,
                            "query_normalized": query.query_normalized,
                            "query_actors": _query_actors(query),
                            "search_page": page,
                            "search_page_limit": query_page_limit,
                            "search_rank": rank,
                            "pulse_id": pulse_id,
                            "pulse_name": pulse_meta.get("name", ""),
                            "pulse_created": pulse_meta.get("created", ""),
                            "pulse_modified": pulse_meta.get("modified", ""),
                            "in_date_window": True,
                            "search_raw_ref": search_raw_ref,
                            "note": (
                                "Collection audit only; not an OTX actor label or "
                                "graph fact."
                            ),
                            },
                        )
                        discovery_keys.add(discovery_key)
                    if pulse_id not in seen_pulses:
                        seen_pulses.add(pulse_id)
                        _checkpoint_add(
                            checkpoint,
                            checkpoint_members,
                            "discovered_pulse_ids",
                            pulse_id,
                        )
                    stats["unique_pulses_discovered"] = len(seen_pulses)

                    if phase == "discovery":
                        continue

                    pulse_completed = pulse_id in checkpoint_members["completed_pulse_details"]
                    detail_payload: dict[str, Any] | None = None
                    if (
                        (pulse_completed or pulse_id in existing_pulses)
                        and not args.refetch_existing_details
                    ):
                        stats["pulse_details_skipped_existing"] += 1
                        existing_detail = store.latest("otx", pulse_id)
                        if isinstance(existing_detail, dict):
                            detail_payload = existing_detail
                            _record_reused_pulse_detail(
                                pulse_id=pulse_id,
                                raw_refs=existing_pulse_raw_refs,
                                saved_pulse_detail_ids=saved_pulse_detail_ids,
                                saved_files_path=saved_files_path,
                                run_id=run_id,
                                checkpoint_path=checkpoint_path,
                                checkpoint=checkpoint,
                                checkpoint_members=checkpoint_members,
                            )
                    else:
                        try:
                            detail = _get_json(client, f"pulses/{pulse_id}")
                            detail_payload = detail
                            raw_path = store.write("otx", pulse_id, detail, fetched_at)
                            existing_pulses.add(pulse_id)
                            stats["pulse_details_written"] += 1
                            _checkpoint_add(
                                checkpoint,
                                checkpoint_members,
                                "completed_pulse_details",
                                pulse_id,
                            )
                            _checkpoint_add(
                                checkpoint,
                                checkpoint_members,
                                "saved_pulse_ids",
                                pulse_id,
                            )
                            _record_saved(
                                path=saved_files_path,
                                run_id=run_id,
                                fetched_at=fetched_at,
                                kind="pulse_detail",
                                pulse_id=pulse_id,
                                raw_ref=_raw_ref("otx", pulse_id, fetched_at, raw_path),
                            )
                            _save_checkpoint(checkpoint_path, checkpoint)
                        except Exception as exc:  # noqa: BLE001
                            page_had_errors = True
                            stats["errors"] += 1
                            _checkpoint_failure(
                                checkpoint,
                                kind="pulse_detail",
                                key=pulse_id,
                                error=str(exc),
                                fetched_at=fetched_at,
                                context={"pulse_id": pulse_id},
                            )
                            _save_checkpoint(checkpoint_path, checkpoint)
                            continue
                        if args.detail_delay:
                            time.sleep(args.detail_delay)

                    detail_indicator_count = _detail_indicator_count(detail_payload)
                    policy_key = (
                        f"{pulse_id}:limit={args.indicator_page_limit}:"
                        f"threshold={args.indicator_endpoint_full_threshold}:"
                        f"sample_pages={args.oversized_indicator_sample_pages}"
                    )
                    if args.skip_indicator_pages:
                        phase_key = f"{policy_key}:phase=skip_indicator_pages"
                        if phase_key not in checkpoint_members["skipped_indicator_endpoints"]:
                            _record_indicator_endpoint_skip(
                                path=skipped_indicator_pages_path,
                                run_id=run_id,
                                fetched_at=fetched_at,
                                pulse_id=pulse_id,
                                page_limit=args.indicator_page_limit,
                                indicator_count=detail_indicator_count,
                                fetched_pages=0,
                                fetched_results=0,
                                full_threshold=args.indicator_endpoint_full_threshold,
                                sample_pages=args.oversized_indicator_sample_pages,
                                reason="endpoint_pending_by_phase",
                            )
                            _checkpoint_add(
                                checkpoint,
                                checkpoint_members,
                                "skipped_indicator_endpoints",
                                phase_key,
                            )
                            _save_checkpoint(checkpoint_path, checkpoint)
                            stats["indicator_endpoints_pending_by_phase"] += 1
                        else:
                            stats["indicator_endpoints_pending_by_phase_existing"] += 1
                    else:
                        if (
                            args.indicator_endpoint_full_threshold
                            and detail_indicator_count > args.indicator_endpoint_full_threshold
                            and args.oversized_indicator_sample_pages <= 0
                        ):
                            if policy_key not in checkpoint_members["skipped_indicator_endpoints"]:
                                _record_indicator_endpoint_skip(
                                    path=skipped_indicator_pages_path,
                                    run_id=run_id,
                                    fetched_at=fetched_at,
                                    pulse_id=pulse_id,
                                    page_limit=args.indicator_page_limit,
                                    indicator_count=detail_indicator_count,
                                    fetched_pages=0,
                                    fetched_results=0,
                                    full_threshold=args.indicator_endpoint_full_threshold,
                                    sample_pages=args.oversized_indicator_sample_pages,
                                    reason="deferred_oversized_indicator_endpoint",
                                )
                                _checkpoint_add(
                                    checkpoint,
                                    checkpoint_members,
                                    "skipped_indicator_endpoints",
                                    policy_key,
                                )
                                _save_checkpoint(checkpoint_path, checkpoint)
                                stats["indicator_endpoints_skipped_by_policy"] += 1
                            else:
                                stats["indicator_endpoints_skipped_by_policy_existing"] += 1
                            continue
                        errors_before_indicator = stats["errors"]
                        stats["indicator_pages_written"] += _fetch_indicator_pages(
                            client=client,
                            store=store,
                            run_id=run_id,
                            checkpoint_path=checkpoint_path,
                            checkpoint=checkpoint,
                            checkpoint_members=checkpoint_members,
                            saved_files_path=saved_files_path,
                            skipped_indicator_pages_path=skipped_indicator_pages_path,
                            pulse_id=pulse_id,
                            fetched_at=fetched_at,
                            page_limit=args.indicator_page_limit,
                            max_pages=args.max_indicator_pages,
                            full_threshold=args.indicator_endpoint_full_threshold,
                            oversized_sample_pages=args.oversized_indicator_sample_pages,
                            page_delay=args.page_delay,
                            stats=stats,
                        )
                        if stats["errors"] > errors_before_indicator:
                            page_had_errors = True

                if candidate_manifest_dirty:
                    _write_candidate_events(candidate_events_path, candidates)
                if page_had_errors:
                    _save_checkpoint(checkpoint_path, checkpoint)
                    break
                if not search_payload.get("next"):
                    _checkpoint_add(
                        checkpoint,
                        checkpoint_members,
                        "completed_query_pages",
                        search_key,
                    )
                    _save_checkpoint(checkpoint_path, checkpoint)
                    _record_query_terminal(
                        query_terminal_states_path,
                        run_id=run_id,
                        query=query,
                        page=page,
                        page_limit=query_page_limit,
                        status="complete",
                        fetched_at=fetched_at,
                    )
                    break
                if page == args.max_search_pages:
                    checkpoint_members["completed_query_pages"].discard(search_key)
                    checkpoint["completed_query_pages"] = [
                        value
                        for value in checkpoint["completed_query_pages"]
                        if str(value) != search_key
                    ]
                    _save_checkpoint(checkpoint_path, checkpoint)
                    _record_query_terminal(
                        query_terminal_states_path,
                        run_id=run_id,
                        query=query,
                        page=page,
                        page_limit=query_page_limit,
                        status="truncated_page_cap",
                        fetched_at=fetched_at,
                    )
                    break
                _checkpoint_add(
                    checkpoint,
                    checkpoint_members,
                    "completed_query_pages",
                    search_key,
                )
                _save_checkpoint(checkpoint_path, checkpoint)
                if args.page_delay:
                    time.sleep(args.page_delay)

    _write_summary(run_dir, run_id, started_at, stats)
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


def _write_summary(
    run_dir: Path,
    run_id: str,
    started_at: str,
    stats: dict[str, int],
) -> None:
    summary = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": _utc_now(),
        **stats,
    }
    _write_json(run_dir / "collection_summary.json", summary)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect raw OTX data discovered from MITRE actor names and aliases"
    )
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument(
        "--actor",
        action="append",
        default=[],
        help="Restrict to a MITRE actor name, G-id, or STIX id. Can repeat.",
    )
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="Restrict to an exact generated OTX actor/alias query. Can repeat.",
    )
    parser.add_argument(
        "--since", default="", help="Keep search hits created on/after this ISO string"
    )
    parser.add_argument(
        "--until", default="", help="Keep search hits created before this ISO string"
    )
    parser.add_argument("--max-actors", type=int, default=0)
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--max-pulses", type=int, default=0)
    parser.add_argument("--max-search-pages", type=int, default=80)
    parser.add_argument("--max-indicator-pages", type=int, default=0)
    parser.add_argument("--search-page-limit", type=int, default=20)
    parser.add_argument(
        "--discovery-workers",
        type=int,
        default=2,
        help="Concurrent discovery queries; each query remains serial and all writes stay single-threaded.",
    )
    parser.add_argument("--indicator-page-limit", type=int, default=1000)
    parser.add_argument(
        "--indicator-endpoint-full-threshold",
        type=int,
        default=50000,
        help="Fetch all indicator endpoint pages only when count is at or below this value; 0 disables policy skip.",
    )
    parser.add_argument(
        "--oversized-indicator-sample-pages",
        type=int,
        default=0,
        help="Number of endpoint pages to keep for pulses above the full threshold; 0 defers them without endpoint requests.",
    )
    parser.add_argument("--page-delay", type=float, default=0.5)
    parser.add_argument("--detail-delay", type=float, default=0.0)
    parser.add_argument("--skip-indicator-pages", action="store_true")
    parser.add_argument("--refetch-existing-details", action="store_true")
    parser.add_argument(
        "--phase",
        choices=("all", "discovery", "detail", "indicators"),
        default="all",
        help="Run the compatible all-in-one flow or one independently resumable phase.",
    )
    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
