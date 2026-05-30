"""Re-fetch OTX pulses as raw JSON for complete field preservation.

Usage:
    python scripts/refetch_otx_raw.py
    python scripts/refetch_otx_raw.py --source checkpoint  # use old checkpoint
    python scripts/refetch_otx_raw.py --csv /path/to/file.csv

Reads pulse_ids from existing otx.jsonl metadata (default), the old
checkpoint, or a CSV file.  Fetches each pulse's full API response and
saves the complete JSON to data/raw/otx/{pulse_id}.json.

Supports checkpoint-based resume: kill and re-run safely.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path("data/raw/otx")
CHECKPOINT = Path("data/raw/otx/.checkpoint.jsonl")
OLD_CHECKPOINT = Path("data/processed/.otx_checkpoint.jsonl")
EXISTING_JSONL = Path("data/processed/otx.jsonl")
CONCURRENCY = 5
BASE_URL = "https://otx.alienvault.com/api/v1/pulses"


def read_pulse_ids_from_jsonl(path: Path) -> list[str]:
    ids: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                pid = rec.get("metadata", {}).get("pulse_id", "")
                if pid:
                    ids.add(pid)
            except json.JSONDecodeError:
                continue
    return sorted(ids)


def read_pulse_ids_from_checkpoint(path: Path) -> list[str]:
    ids: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                pid = rec.get("pulse_id", "")
                if pid:
                    ids.add(pid)
            except json.JSONDecodeError:
                continue
    return sorted(ids)


def read_pulse_ids_from_csv(path: Path) -> list[str]:
    ids: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pid = row.get("pulse_id", "").strip()
            if pid:
                ids.add(pid)
    return sorted(ids)


def load_checkpoint() -> set[str]:
    done: set[str] = set()
    if not CHECKPOINT.exists():
        return done
    with CHECKPOINT.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("status") == "ok":
                    done.add(rec["pulse_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def append_checkpoint(record: dict) -> None:
    with CHECKPOINT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


async def fetch_one(
    client: "httpx.AsyncClient",
    pulse_id: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    import httpx

    async with semaphore:
        url = f"{BASE_URL}/{pulse_id}"
        for attempt in range(3):
            try:
                resp = await client.get(url)
                if resp.status_code == 429:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                (RAW_DIR / f"{pulse_id}.json").write_text(
                    json.dumps(data, ensure_ascii=False), encoding="utf-8"
                )
                return {"pulse_id": pulse_id, "status": "ok"}
            except Exception as e:
                if attempt == 2:
                    return {"pulse_id": pulse_id, "status": "error", "error": str(e)}
                await asyncio.sleep(2 * (attempt + 1))
    return {"pulse_id": pulse_id, "status": "error", "error": "unreachable"}


async def main(pulse_ids: list[str], api_key: str) -> None:
    import httpx

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    done = load_checkpoint()
    pending = [pid for pid in pulse_ids if pid not in done]

    print(f"Total pulse_ids: {len(pulse_ids)}")
    print(f"Already done:    {len(done)}")
    print(f"Pending:         {len(pending)}")

    if not pending:
        print("Nothing to fetch.")
        return

    semaphore = asyncio.Semaphore(CONCURRENCY)
    ok_count = 0
    err_count = 0

    headers = {}
    if api_key:
        headers["X-OTX-API-KEY"] = api_key

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        batch_size = 50
        for batch_start in range(0, len(pending), batch_size):
            batch = pending[batch_start : batch_start + batch_size]
            tasks = [fetch_one(client, pid, semaphore) for pid in batch]
            results = await asyncio.gather(*tasks)

            for result in results:
                # raw written to disk first, then checkpoint (crash-safe order)
                append_checkpoint(result)
                if result["status"] == "ok":
                    ok_count += 1
                else:
                    err_count += 1

            total_done = len(done) + ok_count + err_count
            print(
                f"  Progress: {total_done}/{len(pulse_ids)} "
                f"(ok={ok_count}, err={err_count})"
            )

    print(f"\nDone. ok={ok_count}  errors={err_count}")


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Re-fetch OTX pulses as raw JSON"
    )
    parser.add_argument(
        "--source",
        choices=["jsonl", "checkpoint", "csv"],
        default="jsonl",
        help="Where to read pulse_ids from (default: jsonl)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to CSV with pulse_id column (used when --source csv)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OTX_API_KEY", "")
    if not api_key:
        print("ERROR: OTX_API_KEY not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(1)

    if args.source == "csv":
        if not args.csv or not args.csv.exists():
            print(f"ERROR: CSV file not found: {args.csv}", file=sys.stderr)
            sys.exit(1)
        pulse_ids = read_pulse_ids_from_csv(args.csv)
    elif args.source == "checkpoint":
        if not OLD_CHECKPOINT.exists():
            print(f"ERROR: Old checkpoint not found: {OLD_CHECKPOINT}", file=sys.stderr)
            sys.exit(1)
        pulse_ids = read_pulse_ids_from_checkpoint(OLD_CHECKPOINT)
    else:
        if not EXISTING_JSONL.exists():
            print(f"ERROR: otx.jsonl not found: {EXISTING_JSONL}", file=sys.stderr)
            sys.exit(1)
        pulse_ids = read_pulse_ids_from_jsonl(EXISTING_JSONL)

    print(f"Loaded {len(pulse_ids)} pulse_ids from {args.source}")
    asyncio.run(main(pulse_ids, api_key))


if __name__ == "__main__":
    cli()
