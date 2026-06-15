"""Re-fetch WHOIS records (via Whoxy) as raw JSON into the versioned RawStore.

Domains come from the indicator index (canonical_type=domain). Stores the
**verbatim** Whoxy payload (not the mapped record), so any future projection can
be regenerated. Use --history to hit the WHOIS-history endpoint instead of live.
Resumable: RawStore writes are idempotent per (domain, fetched_at).
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti.connectors.whoxy import WhoxyClient
from rag_cti.ingest.raw_ingest import read_domains_from_index
from rag_cti.store.raw_store import RawStore

_INDEX = Path("data/processed/indicator_index.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch WHOIS (Whoxy) records into RawStore")
    parser.add_argument("--index", type=Path, default=_INDEX)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--limit", type=int, default=0, help="max domains (0 = all)")
    parser.add_argument("--history", action="store_true", help="use the WHOIS-history endpoint")
    parser.add_argument("--throttle", type=float, default=0.0)
    args = parser.parse_args()

    api_key = os.environ.get("WHOXY_API_KEY", "")
    if not api_key:
        print("ERROR: WHOXY_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    domains = read_domains_from_index(args.index)
    if args.limit:
        domains = domains[: args.limit]
    if not domains:
        print(f"No domains in {args.index}. Run scripts/build_indicator_index.py first.")
        return

    store = RawStore(args.raw_root)
    fetched_at = datetime.now(UTC).isoformat()
    written = 0
    skipped = 0
    with WhoxyClient(api_key=api_key) as client:
        for i, domain in enumerate(domains):
            try:
                raw = client.history_raw(domain) if args.history else client.whois_raw(domain)
            except Exception as exc:  # network/quota — count, don't crash the batch
                skipped += 1
                print(f"  WARN: {domain}: {exc}", file=sys.stderr)
                continue
            store.write("whois", domain, raw, fetched_at)
            written += 1
            if i < len(domains) - 1 and args.throttle:
                time.sleep(args.throttle)

    print(f"✓ {written} WHOIS records -> raw store (whois); {skipped} skipped")


if __name__ == "__main__":
    main()
