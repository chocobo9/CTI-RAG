"""Re-fetch VirusTotal domain reports as raw JSON into the versioned RawStore.

Domains come from the indicator index (canonical_type=domain). VT free tier is
rate-limited to ~4 req/min, so this throttles by default and is resumable:
RawStore writes are idempotent per (domain, fetched_at), and identical payloads
are no-ops, so a killed run can be re-run safely.
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti.connectors.virustotal import VirusTotalConnector
from rag_cti.store.raw_store import RawStore


def _registered_domains(index_path: Path) -> list[str]:
    """Registered domains (``indicator_type=domain``) from the index — the OTX threat
    indicators (C2 / phishing). Skips ``hostname`` entries (subdomains / ISP PTR /
    CDN), which are pDNS-resolution infrastructure noise with no VT threat value."""
    out: list[str] = []
    with index_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("indicator_type") == "domain" and rec.get("value"):
                out.append(rec["value"])
    return out


_INDEX = Path("data/processed/indicator_index.jsonl")
_THROTTLE_SECONDS = 15.0  # 4 requests/min on the VT free tier


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch VT domain reports into RawStore")
    parser.add_argument("--index", type=Path, default=_INDEX)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--limit", type=int, default=0, help="max domains (0 = all)")
    parser.add_argument("--throttle", type=float, default=_THROTTLE_SECONDS)
    args = parser.parse_args()

    api_key = os.environ.get("VT_API_KEY", "")
    if not api_key:
        print("ERROR: VT_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    # Registered domains only (indicator_type=domain) — skips hostname/PTR/CDN noise.
    domains = _registered_domains(args.index)
    # VT API returns 400 for wildcard (*.x) domains — skip them.
    domains = [d for d in domains if not d.startswith("*")]
    # Skip domains already in the raw store: RawStore writes are idempotent, but
    # re-fetching wastes the rate-limited free-tier quota.
    vt_dir = args.raw_root / "vt"
    if vt_dir.is_dir():
        already = set(os.listdir(vt_dir))
        domains = [d for d in domains if d not in already]
    if args.limit:
        domains = domains[: args.limit]
    if not domains:
        print(f"No domains in {args.index}. Run scripts/build_indicator_index.py first.")
        return

    store = RawStore(args.raw_root)
    fetched_at = datetime.now(UTC).isoformat()
    conn = VirusTotalConnector(api_key=api_key)

    written = 0
    for i, domain in enumerate(domains):
        for raw in conn.fetch(domains=[domain]):
            source_id = raw.get("data", {}).get("id", "") or domain
            store.write("vt", source_id, raw, fetched_at)
            written += 1
        if i < len(domains) - 1 and args.throttle:
            time.sleep(args.throttle)
        if (i + 1) % 20 == 0:
            print(f"  progress: {i + 1}/{len(domains)} domains, {written} written")

    print(f"✓ {written} VT reports -> raw store (vt) from {len(domains)} domains")


if __name__ == "__main__":
    main()
