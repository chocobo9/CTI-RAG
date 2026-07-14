"""Fetch only actor-evidenced OTX Pulse details selected by a routing manifest."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import itertools
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.intermediate.otx_routed_detail_fetch import load_routed_detail_plan
from rag_cti.store.raw_store import RawStore

BASE_URL = "https://otx.alienvault.com/api/v1"
DEFAULT_MANIFEST = Path(
    "data/processed/otx_detail_acquisition_routeA_20260704/detail_acquisition_manifest.jsonl"
)
DEFAULT_EXPECTED_SHA256 = "6AE599CC70E1F40E71509FDFEFD1F2747DB50FBF6685822595491F9886571125"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _fetch_one(pulse_id: str, api_key: str, timeout: float, max_bytes: int) -> dict[str, Any]:
    for attempt in range(1, 4):
        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream(
                    "GET",
                    f"{BASE_URL}/pulses/{pulse_id}",
                    headers={"X-OTX-API-KEY": api_key},
                ) as response:
                    if response.status_code == 404:
                        return {"pulse_id": pulse_id, "status": "not_found"}
                    if response.status_code in {401, 403}:
                        return {
                            "pulse_id": pulse_id,
                            "status": "forbidden",
                            "http_status": response.status_code,
                        }
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < 3:
                            time.sleep(2 * attempt)
                            continue
                        return {
                            "pulse_id": pulse_id,
                            "status": "retryable_error",
                            "http_status": response.status_code,
                        }
                    response.raise_for_status()
                    content_length = int(response.headers.get("content-length", "0") or 0)
                    if content_length > max_bytes:
                        return {
                            "pulse_id": pulse_id,
                            "status": "oversized_failure",
                            "bytes": content_length,
                        }
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            return {
                                "pulse_id": pulse_id,
                                "status": "oversized_failure",
                                "bytes": size,
                            }
                        chunks.append(chunk)
                    payload = json.loads(b"".join(chunks))
                    if not isinstance(payload, dict):
                        raise ValueError("OTX Pulse detail response is not a JSON object")
                    return {
                        "pulse_id": pulse_id,
                        "status": "complete",
                        "payload": payload,
                        "bytes": size,
                    }
        except (
            httpx.TimeoutException,
            httpx.TransportError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            if attempt < 3:
                time.sleep(2 * attempt)
                continue
            return {"pulse_id": pulse_id, "status": "retryable_error", "error": str(exc)}
        except httpx.HTTPStatusError as exc:
            return {
                "pulse_id": pulse_id,
                "status": "retryable_error",
                "http_status": exc.response.status_code,
                "error": str(exc),
            }
    raise AssertionError("unreachable")


def _valid_existing_detail(store: RawStore, pulse_id: str) -> bool:
    payload = store.latest("otx", pulse_id)
    if not isinstance(payload, dict):
        return False
    payload_id = payload.get("id")
    return str(payload_id or "") == pulse_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--expected-sha256", default=DEFAULT_EXPECTED_SHA256)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2, choices=range(1, 5))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-response-mib", type=int, default=300)
    parser.add_argument("--retry-only", action="store_true")
    parser.add_argument("--max-items", type=int, default=0)
    args = parser.parse_args()

    actual_hash = _sha256(args.manifest)
    if args.expected_sha256 and actual_hash != args.expected_sha256.upper():
        raise SystemExit(f"routing manifest SHA256 mismatch: {actual_hash}")
    load_dotenv()
    api_key = os.environ.get("OTX_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OTX_API_KEY is required")

    args.run_dir.mkdir(parents=True, exist_ok=True)
    statuses_path = args.run_dir / "detail_statuses.jsonl"
    plan = load_routed_detail_plan(
        args.manifest, statuses_path=statuses_path, retry_only=args.retry_only
    )
    if len(plan.acquire_ids) != 5558 or plan.deferred_count != 25832:
        raise SystemExit(
            "routing population mismatch: expected acquire=5558 and deferred=25832"
        )
    if plan.declared_missing_count != 2387:
        raise SystemExit("routing manifest mismatch: expected declared missing=2387")
    store = RawStore(args.raw_root)
    latest_status: dict[str, str] = {}
    if statuses_path.exists():
        for line in statuses_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            latest_status[str(row["pulse_id"])] = str(row["status"])

    valid_existing = {pid for pid in plan.acquire_ids if _valid_existing_detail(store, pid)}
    # The frozen manifest is the sole population. Retry mode only schedules latest
    # retryable errors; a normal resume schedules every still-missing acquire ID.
    if args.retry_only:
        eligible = list(plan.network_ids)
    else:
        eligible = [pid for pid in plan.acquire_ids if pid not in valid_existing]
    reused = [pid for pid in plan.acquire_ids if pid in valid_existing and latest_status.get(pid) not in {"complete", "reused"}]
    for pulse_id in reused:
        _append(statuses_path, {"pulse_id": pulse_id, "status": "reused", "recorded_at": _now()})
    eligible = [pid for pid in eligible if pid not in valid_existing]
    if args.max_items:
        eligible = eligible[: args.max_items]

    counts: dict[str, int] = {"reused": len(reused)}
    bytes_written = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        iterator = iter(eligible)
        futures: dict[concurrent.futures.Future[dict[str, Any]], str] = {}
        for pulse_id in itertools.islice(iterator, args.workers):
            futures[pool.submit(
                _fetch_one,
                pulse_id,
                api_key,
                args.timeout,
                args.max_response_mib * 1024 * 1024,
            )] = pulse_id
        index = 0
        while futures:
            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                futures.pop(future)
                index += 1
                result = future.result()
                pulse_id = str(result.pop("pulse_id"))
                status = str(result.pop("status"))
                payload = result.pop("payload", None)
                row = {
                    "pulse_id": pulse_id,
                    "status": status,
                    "recorded_at": _now(),
                    **result,
                }
                if status == "complete":
                    fetched_at = row["recorded_at"]
                    raw_path = store.write("otx", pulse_id, payload, fetched_at)
                    row["raw_ref"] = {
                        "source": "otx",
                        "source_id": pulse_id,
                        "fetched_at": fetched_at,
                        "path": str(raw_path),
                    }
                    bytes_written += int(row.get("bytes", 0))
                _append(statuses_path, row)
                counts[status] = counts.get(status, 0) + 1
                if index % 100 == 0:
                    print(
                        json.dumps(
                            {"processed": index, "total": len(eligible), "counts": counts}
                        ),
                        flush=True,
                    )
                next_id = next(iterator, None)
                if next_id is not None:
                    futures[
                        pool.submit(
                            _fetch_one,
                            next_id,
                            api_key,
                            args.timeout,
                            args.max_response_mib * 1024 * 1024,
                        )
                    ] = next_id

    summary = {
        "manifest": str(args.manifest),
        "manifest_sha256": actual_hash,
        "acquire_count": len(plan.acquire_ids),
        "deferred_count": plan.deferred_count,
        "network_eligible_count": len(eligible),
        "counts_this_invocation": counts,
        "raw_payload_bytes_written": bytes_written,
        "workers": args.workers,
        "retry_only": args.retry_only,
        "completed_at": _now(),
    }
    (args.run_dir / "invocation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
