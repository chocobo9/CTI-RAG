"""Run a resumable OTX pDNS/ASN pilot or full raw enrichment collection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx

from rag_cti.config import get_settings
from rag_cti.trail_dataset.otx_enrichment_collection import (
    OTX_BASE,
    build_tasks,
    collect_tasks,
    httpx_requester,
    select_pilot,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds-jsonl", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--old-pdns-root", type=Path)
    parser.add_argument("--phase", choices=("pilot", "full"), required=True)
    parser.add_argument("--pilot-per-endpoint", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    tasks = build_tasks(args.seeds_jsonl, old_pdns_root=args.old_pdns_root)
    if args.phase == "pilot":
        tasks = select_pilot(tasks, per_endpoint=args.pilot_per_endpoint)
    api_key = get_settings().otx_api_key.get_secret_value()
    if not api_key:
        parser.error("OTX API key is unavailable")
    headers = {"X-OTX-API-KEY": api_key}
    with httpx.Client(
        base_url=OTX_BASE, headers=headers, timeout=args.timeout
    ) as client:
        report = collect_tasks(
            tasks=tasks,
            output_root=args.output_root,
            requester=httpx_requester(client, max_attempts=args.max_attempts),
            phase=args.phase,
            workers=args.workers,
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.phase == "pilot" and not report["pilot_safe_for_full"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
