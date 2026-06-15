"""Re-fetch passive-DNS records as raw JSON into the versioned RawStore.

Provider: the AlienVault OTX passive-DNS endpoint, reusing the OTX API key we
already hold (``settings.otx_api_key``) — no separate account or paid feed. Each
domain from the indicator index is looked up at
``/api/v1/indicators/domain/{domain}/passive_dns`` and its raw JSON is stored
verbatim via ``RawStore`` (L0: preserve raw, project later), mirroring the
VT/WHOIS fetchers.

Resumable: a domain already present in the raw store is skipped (no wasted API
call), so re-running only fetches the remainder. A non-200 lookup (e.g. a
wildcard or unknown domain) is logged and skipped, never stored as a fake record.
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx

from rag_cti._logging import configure_logging, get_logger
from rag_cti.config import get_settings
from rag_cti.connectors.otx import _OTX_BASE
from rag_cti.ingest.raw_ingest import read_domains_from_index
from rag_cti.store.raw_store import RawStore

logger = get_logger(__name__)

_INDEX = Path("data/processed/indicator_index.jsonl")
_PDNS_PATH = "/api/v1/indicators/domain/{domain}/passive_dns"
_TIMEOUT_SECONDS = 45.0  # OTX pdns is slow for high-volume domains
_THROTTLE_SECONDS = 1.0  # polite spacing; OTX is far more generous than VT


def _fetch_pdns(client: httpx.Client, domain: str) -> dict[str, Any] | None:
    """One domain's passive-DNS JSON from OTX, or None on a non-200 lookup."""
    resp = client.get(_PDNS_PATH.format(domain=domain))
    if resp.status_code != 200:
        logger.warning("pdns lookup failed", domain=domain, status=resp.status_code)
        return None
    payload: dict[str, Any] = resp.json()
    return payload


def _store_one(store: RawStore, client: httpx.Client, fetched_at: str, domain: str) -> str:
    """Fetch+store one domain. Returns 'skipped' | 'empty' | 'written'.

    Thread-safe: each domain is a distinct RawStore path, and httpx.Client is shared
    across threads by design — so this is the unit a worker pool fans out over.
    """
    if store.versions("pdns", domain):  # already fetched -> resume, no API call
        return "skipped"
    raw = _fetch_pdns(client, domain)
    if raw is None:
        return "empty"
    store.write("pdns", domain, raw, fetched_at)
    return "written"


def main() -> None:
    configure_logging("INFO")
    parser = argparse.ArgumentParser(description="Fetch passive DNS (OTX) into RawStore")
    parser.add_argument("--index", type=Path, default=_INDEX)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--limit", type=int, default=0, help="max domains (0 = all)")
    parser.add_argument("--throttle", type=float, default=_THROTTLE_SECONDS)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="concurrent fetchers (1 = serial+throttle). OTX rate-limits per key, so "
        "concurrency only helps up to that limit, then non-200s rise.",
    )
    args = parser.parse_args()

    api_key = get_settings().otx_api_key.get_secret_value()
    if not api_key:
        print("ERROR: otx_api_key not set in .env", file=sys.stderr)
        sys.exit(1)

    domains = read_domains_from_index(args.index)
    if args.limit:
        domains = domains[: args.limit]
    if not domains:
        print(f"No domains in {args.index}. Run scripts/build_indicator_index.py first.")
        return

    store = RawStore(args.raw_root)
    fetched_at = datetime.now(UTC).isoformat()
    counts = {"written": 0, "skipped": 0, "empty": 0}
    headers = {"Authorization": f"Bearer {api_key}"}
    total = len(domains)

    def _tick(done: int) -> None:
        if done % 50 == 0 or done == total:
            print(
                f"  progress: {done}/{total} "
                f"({counts['written']} written, {counts['skipped']} skipped, "
                f"{counts['empty']} no-data)",
                flush=True,
            )

    with httpx.Client(base_url=_OTX_BASE, headers=headers, timeout=_TIMEOUT_SECONDS) as client:
        if args.workers > 1:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(_store_one, store, client, fetched_at, d) for d in domains]
                for done, future in enumerate(as_completed(futures), 1):
                    counts[future.result()] += 1
                    _tick(done)
        else:
            for done, domain in enumerate(domains, 1):
                result = _store_one(store, client, fetched_at, domain)
                counts[result] += 1
                if result != "skipped" and args.throttle:
                    time.sleep(args.throttle)
                _tick(done)

    print(
        f"✓ {counts['written']} passive-DNS reports -> raw store (pdns) from {total} domains "
        f"({counts['skipped']} already present, {counts['empty']} no-data)"
    )


if __name__ == "__main__":
    main()
