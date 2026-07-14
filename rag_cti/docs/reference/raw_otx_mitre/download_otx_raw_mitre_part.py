#!/usr/bin/env python3
"""
Download one MITRE raw OTX query shard.

This script intentionally does not:
  - write to Neo4j
  - enrich IOCs
  - resolve domains/IPs/URLs
  - filter ambiguous or duplicate pulses
  - compute attribution confidence
  - convert raw OTX responses into a custom schema

Raw OTX search, pulse, and indicator responses are written exactly as returned
by the API. Discovery, date-window, and failure information is stored as
separate metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE_DIR = PROJECT_ROOT / "data" / "raw_otx_mitre"
OTX_BASE = "https://otx.alienvault.com/api/v1"
SHARD_COUNT = 4
DEFAULT_SINCE = "2018-01-01"
DEFAULT_UNTIL = "2023-01-01"
REQUEST_TIMEOUT = 60
RETRY_MAX = 5
RETRY_BASE_DELAY = 10.0
RATE_LIMIT_COOLDOWN = 30.0
TRANSIENT_STATUSES = {429, 502, 503, 504}
PERMANENT_MISSING_STATUSES = {403, 404}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_day(value: str) -> date:
    return date.fromisoformat(value)


def parse_otx_created(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def in_date_window(created_value: Any, since: date, until: date) -> bool | None:
    created = parse_otx_created(created_value)
    if created is None:
        return None
    return since <= created < until


def slugify(value: str, max_len: int = 90) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._-")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"{(slug or 'query')[:max_len]}_{digest}"


def pulse_id_from_result(result: dict) -> str | None:
    for key in ("id", "pulse_id", "pulseId"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def created_from_search_result(result: dict) -> Any:
    for key in ("created", "created_at", "pulse_created"):
        if result.get(key):
            return result.get(key)
    return None


def search_results(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        results = payload.get("results", [])
        return [item for item in results if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def load_api_keys() -> list[str]:
    keys = [k.strip() for k in os.environ.get("OTX_API_KEYS", "").split(",") if k.strip()]
    single = os.environ.get("OTX_API_KEY", "").strip()
    if single:
        keys.append(single)
    keys = list(dict.fromkeys(keys))
    if not keys:
        raise SystemExit("Set OTX_API_KEY or OTX_API_KEYS before downloading.")
    return keys


class KeyPool:
    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        self.index = 0
        self.cooldowns: dict[str, float] = {}

    def next_key(self) -> str:
        while True:
            now = time.time()
            for _ in range(len(self.keys)):
                key = self.keys[self.index]
                self.index = (self.index + 1) % len(self.keys)
                if self.cooldowns.get(key, 0.0) <= now:
                    return key
            wait_s = max(0.5, min(self.cooldowns.values()) - now)
            logging.warning("All OTX keys are cooling down; sleeping %.1fs", wait_s)
            time.sleep(wait_s)

    def cooldown(self, key: str) -> None:
        self.cooldowns[key] = time.time() + RATE_LIMIT_COOLDOWN


class RawOTXClient:
    def __init__(self, keys: list[str]) -> None:
        self.pool = KeyPool(keys)

    def get_raw_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[Any | None, str | None, int | None, str | None]:
        last_status: int | None = None
        last_error: str | None = None

        for attempt in range(RETRY_MAX):
            key = self.pool.next_key()
            headers = {"X-OTX-API-KEY": key}
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
                last_status = resp.status_code
                if resp.status_code == 200:
                    try:
                        parsed = resp.json()
                    except ValueError as exc:
                        return None, resp.text, resp.status_code, f"json_decode_error: {exc}"
                    return parsed, resp.text, resp.status_code, None

                if resp.status_code == 429:
                    self.pool.cooldown(key)
                    logging.warning("HTTP 429 for %s; rotating key", url)
                    continue

                if resp.status_code in PERMANENT_MISSING_STATUSES:
                    return None, resp.text, resp.status_code, None

                if resp.status_code in TRANSIENT_STATUSES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logging.warning("HTTP %s for %s; sleeping %.1fs", resp.status_code, url, delay)
                    time.sleep(delay)
                    continue

                return None, resp.text, resp.status_code, None
            except (
                requests.Timeout,
                requests.ConnectionError,
                requests.exceptions.SSLError,
                requests.RequestException,
            ) as exc:
                last_error = repr(exc)
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logging.warning("Transport error for %s: %s; sleeping %.1fs", url, last_error, delay)
                time.sleep(delay)

        return None, None, last_status, last_error or "retry_exhausted"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    replace_with_retry(tmp, path)


def write_raw(path: Path, raw_text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(raw_text, encoding="utf-8")
    replace_with_retry(tmp, path)


def replace_with_retry(tmp: Path, target: Path, attempts: int = 12, delay_s: float = 0.25) -> None:
    """Replace target, retrying transient Windows file-lock failures."""
    last_exc: PermissionError | None = None
    for attempt in range(attempts):
        try:
            tmp.replace(target)
            return
        except PermissionError as exc:
            last_exc = exc
            time.sleep(delay_s * (attempt + 1))
    raise last_exc or PermissionError(f"Could not replace {target}")


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def setup_logging(part_dir: Path) -> None:
    part_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(part_dir / "download.log", encoding="utf-8"),
        ],
        force=True,
    )


def load_checkpoint(path: Path, part: int, since: str, until: str) -> dict:
    candidates = []
    if path.exists():
        candidates.append(path)
    candidates.extend(path.parent.glob(f"{path.stem}.recovery.*{path.suffix}"))
    if candidates:
        checkpoint_path = max(candidates, key=lambda item: item.stat().st_mtime)
        try:
            checkpoint = read_json(checkpoint_path)
            checkpoint["resume_count"] = int(checkpoint.get("resume_count", 0)) + 1
            checkpoint["last_resume_at"] = utc_now()
            if checkpoint_path != path:
                checkpoint["loaded_from_recovery_checkpoint"] = str(checkpoint_path)
            return checkpoint
        except json.JSONDecodeError:
            logging.warning("Corrupt checkpoint at %s; starting fresh", checkpoint_path)
    return {
        "part": part,
        "started_at": utc_now(),
        "updated_at": None,
        "resume_count": 0,
        "last_resume_at": None,
        "since": since,
        "until": until,
        "completed_query_norms": [],
        "completed_search_pages": {},
        "discovered_pulse_ids": [],
        "saved_pulse_ids": [],
        "saved_indicator_pulse_ids": [],
        "skipped_pulse_ids": [],
        "discovery_keys": [],
        "failed_requests": [],
    }


def save_checkpoint(path: Path, checkpoint: dict) -> None:
    checkpoint["updated_at"] = utc_now()
    try:
        write_json(path, checkpoint)
    except PermissionError as exc:
        recovery = path.with_name(
            f"{path.stem}.recovery.{os.getpid()}.{int(time.time())}{path.suffix}"
        )
        recovery.write_text(
            json.dumps(checkpoint, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        logging.warning(
            "Could not replace checkpoint %s because Windows denied access: %s. "
            "Wrote recovery checkpoint %s and continuing.",
            path,
            exc,
            recovery,
        )


def mark(checkpoint: dict, key: str, value: str) -> None:
    if value not in checkpoint[key]:
        checkpoint[key].append(value)


def record_failure(part_dir: Path, checkpoint: dict, failure: dict) -> None:
    failure = {"time": utc_now(), **failure}
    checkpoint["failed_requests"].append(failure)
    append_jsonl(part_dir / "metadata" / "failed_requests.jsonl", failure)


def save_pulse_and_indicators(
    client: RawOTXClient,
    part_dir: Path,
    checkpoint: dict,
    checkpoint_path: Path,
    pulse_id: str,
    pulse_payload: Any | None,
    pulse_raw_text: str | None,
    detail_source: str,
) -> bool:
    pulse_path = part_dir / "pulses" / f"{pulse_id}.json"
    indicator_path = part_dir / "indicators" / f"{pulse_id}.json"

    if pulse_id not in checkpoint["saved_pulse_ids"]:
        if pulse_path.exists():
            mark(checkpoint, "saved_pulse_ids", pulse_id)
        else:
            if pulse_raw_text is None:
                pulse_payload, pulse_raw_text, status, error = client.get_raw_json(f"{OTX_BASE}/pulses/{pulse_id}")
                detail_source = "pulse_detail_endpoint"
                if pulse_raw_text is None or status != 200:
                    record_failure(
                        part_dir,
                        checkpoint,
                        {
                            "stage": "pulse_detail",
                            "pulse_id": pulse_id,
                            "url": f"{OTX_BASE}/pulses/{pulse_id}",
                            "status": status,
                            "error": error,
                        },
                    )
                    save_checkpoint(checkpoint_path, checkpoint)
                    return False
            write_raw(pulse_path, pulse_raw_text)
            mark(checkpoint, "saved_pulse_ids", pulse_id)
            append_jsonl(
                part_dir / "metadata" / "saved_files.jsonl",
                {
                    "time": utc_now(),
                    "pulse_id": pulse_id,
                    "kind": "pulse",
                    "source": detail_source,
                    "path": str(pulse_path.relative_to(part_dir)),
                },
            )

    if pulse_id not in checkpoint["saved_indicator_pulse_ids"]:
        if indicator_path.exists():
            mark(checkpoint, "saved_indicator_pulse_ids", pulse_id)
        else:
            payload, raw_text, status, error = client.get_raw_json(
                f"{OTX_BASE}/pulses/{pulse_id}/indicators",
                params={"limit": 1000},
            )
            if raw_text is None or status != 200:
                record_failure(
                    part_dir,
                    checkpoint,
                    {
                        "stage": "indicators",
                        "pulse_id": pulse_id,
                        "url": f"{OTX_BASE}/pulses/{pulse_id}/indicators",
                        "params": {"limit": 1000},
                        "status": status,
                        "error": error,
                    },
                )
                save_checkpoint(checkpoint_path, checkpoint)
                return False
            write_raw(indicator_path, raw_text)
            mark(checkpoint, "saved_indicator_pulse_ids", pulse_id)
            append_jsonl(
                part_dir / "metadata" / "saved_files.jsonl",
                {
                    "time": utc_now(),
                    "pulse_id": pulse_id,
                    "kind": "indicators",
                    "source": "indicators_endpoint",
                    "path": str(indicator_path.relative_to(part_dir)),
                },
            )

    save_checkpoint(checkpoint_path, checkpoint)
    return True


def decide_and_download_pulse(
    client: RawOTXClient,
    part_dir: Path,
    checkpoint: dict,
    checkpoint_path: Path,
    pulse_id: str,
    search_result: dict,
    query_item: dict,
    part: int,
    page: int,
    search_file: Path,
    since_day: date,
    until_day: date,
) -> None:
    mark(checkpoint, "discovered_pulse_ids", pulse_id)

    created_value = created_from_search_result(search_result)
    in_window = in_date_window(created_value, since_day, until_day)
    detail_payload = None
    detail_raw = None
    detail_source = "search_result_created"

    if in_window is None:
        detail_payload, detail_raw, status, error = client.get_raw_json(f"{OTX_BASE}/pulses/{pulse_id}")
        detail_source = "pulse_detail_endpoint_for_created"
        if detail_raw is None or status != 200:
            record_failure(
                part_dir,
                checkpoint,
                {
                    "stage": "pulse_detail_for_created",
                    "pulse_id": pulse_id,
                    "url": f"{OTX_BASE}/pulses/{pulse_id}",
                    "status": status,
                    "error": error,
                },
            )
            save_checkpoint(checkpoint_path, checkpoint)
            return
        if isinstance(detail_payload, dict):
            created_value = detail_payload.get("created")
            in_window = in_date_window(created_value, since_day, until_day)

    discovery_key = f"{query_item['query_normalized']}|{pulse_id}|{page}"
    if discovery_key not in checkpoint["discovery_keys"]:
        append_jsonl(
            part_dir / "metadata" / "discovery_metadata.jsonl",
            {
                "time": utc_now(),
                "part": part,
                "query": query_item["query"],
                "query_normalized": query_item["query_normalized"],
                "query_actors": query_item.get("actors", []),
                "pulse_id": pulse_id,
                "pulse_created": created_value,
                "in_date_window": in_window,
                "since": since_day.isoformat(),
                "until": until_day.isoformat(),
                "search_page": page,
                "search_file": str(search_file.relative_to(part_dir)),
            },
        )
        checkpoint["discovery_keys"].append(discovery_key)

    if in_window is not True:
        mark(checkpoint, "skipped_pulse_ids", pulse_id)
        append_jsonl(
            part_dir / "metadata" / "skipped_pulses.jsonl",
            {
                "time": utc_now(),
                "part": part,
                "pulse_id": pulse_id,
                "pulse_created": created_value,
                "reason": "outside_date_window" if in_window is False else "missing_or_unparseable_created",
                "query": query_item["query"],
                "query_normalized": query_item["query_normalized"],
                "search_page": page,
            },
        )
        save_checkpoint(checkpoint_path, checkpoint)
        return

    save_pulse_and_indicators(
        client=client,
        part_dir=part_dir,
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
        pulse_id=pulse_id,
        pulse_payload=detail_payload,
        pulse_raw_text=detail_raw,
        detail_source=detail_source,
    )


def process_query(
    client: RawOTXClient,
    part_dir: Path,
    checkpoint: dict,
    checkpoint_path: Path,
    query_item: dict,
    part: int,
    max_pages: int,
    limit: int,
    delay_s: float,
    since_day: date,
    until_day: date,
) -> None:
    query = query_item["query"]
    query_norm = query_item["query_normalized"]
    query_slug = slugify(query)
    completed_pages = set(checkpoint["completed_search_pages"].get(query_norm, []))
    logging.info("Query: %s", query)

    for page in range(1, max_pages + 1):
        if page in completed_pages:
            continue

        payload, raw_text, status, error = client.get_raw_json(
            f"{OTX_BASE}/search/pulses",
            params={"q": query, "page": page, "limit": limit, "sort": "-modified"},
        )
        if raw_text is None or status != 200:
            record_failure(
                part_dir,
                checkpoint,
                {
                    "stage": "search",
                    "query": query,
                    "query_normalized": query_norm,
                    "url": f"{OTX_BASE}/search/pulses",
                    "params": {"q": query, "page": page, "limit": limit, "sort": "-modified"},
                    "status": status,
                    "error": error,
                },
            )
            save_checkpoint(checkpoint_path, checkpoint)
            return

        search_file = part_dir / "search" / query_slug / f"page_{page:04d}.json"
        write_raw(search_file, raw_text)
        append_jsonl(
            part_dir / "metadata" / "search_pages.jsonl",
            {
                "time": utc_now(),
                "part": part,
                "query": query,
                "query_normalized": query_norm,
                "page": page,
                "path": str(search_file.relative_to(part_dir)),
                "status": status,
            },
        )

        results = search_results(payload)
        for result in results:
            pulse_id = pulse_id_from_result(result)
            if not pulse_id:
                continue
            decide_and_download_pulse(
                client=client,
                part_dir=part_dir,
                checkpoint=checkpoint,
                checkpoint_path=checkpoint_path,
                pulse_id=pulse_id,
                search_result=result,
                query_item=query_item,
                part=part,
                page=page,
                search_file=search_file,
                since_day=since_day,
                until_day=until_day,
            )
            time.sleep(delay_s)

        checkpoint["completed_search_pages"].setdefault(query_norm, []).append(page)
        save_checkpoint(checkpoint_path, checkpoint)

        if not results:
            break
        time.sleep(delay_s)

    mark(checkpoint, "completed_query_norms", query_norm)
    save_checkpoint(checkpoint_path, checkpoint)


def main(default_part: int | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download one MITRE raw OTX shard.")
    parser.add_argument(
        "--part",
        type=int,
        choices=range(SHARD_COUNT),
        required=default_part is None,
        default=default_part,
    )
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--since", default=DEFAULT_SINCE)
    parser.add_argument("--until", default=DEFAULT_UNTIL)
    parser.add_argument("--max-pages", type=int, default=80)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    if args.part is None:
        raise SystemExit("--part is required unless using a fixed-part wrapper.")

    since_day = parse_day(args.since)
    until_day = parse_day(args.until)
    if since_day >= until_day:
        raise SystemExit("--since must be earlier than --until")

    seed_dir = args.base_dir / "seeds"
    shard_path = seed_dir / f"query_shard_{args.part:02d}.json"
    if not shard_path.exists():
        raise SystemExit(f"Missing {shard_path}. Run build_mitre_query_shards.py first.")

    part_dir = args.base_dir / f"part_{args.part:02d}"
    setup_logging(part_dir)
    checkpoint_path = part_dir / "checkpoint.json"
    checkpoint = load_checkpoint(checkpoint_path, args.part, args.since, args.until)
    save_checkpoint(checkpoint_path, checkpoint)

    shard = read_json(shard_path)
    client = RawOTXClient(load_api_keys())
    completed_queries = set(checkpoint["completed_query_norms"])
    queries = shard.get("queries", [])

    logging.info(
        "Part %02d starting: %d queries, since=%s until=%s",
        args.part,
        len(queries),
        args.since,
        args.until,
    )

    for query_item in queries:
        if query_item["query_normalized"] in completed_queries:
            continue
        process_query(
            client=client,
            part_dir=part_dir,
            checkpoint=checkpoint,
            checkpoint_path=checkpoint_path,
            query_item=query_item,
            part=args.part,
            max_pages=args.max_pages,
            limit=args.limit,
            delay_s=args.delay,
            since_day=since_day,
            until_day=until_day,
        )
        completed_queries = set(checkpoint["completed_query_norms"])

    logging.info("Part %02d complete", args.part)
    save_checkpoint(checkpoint_path, checkpoint)


if __name__ == "__main__":
    main()
