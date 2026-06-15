"""PLACEHOLDER: re-fetch passive-DNS records as raw JSON into the versioned RawStore.

No passive-DNS provider is wired yet: ``PassiveDNSConnector`` consumes
pre-fetched records, and there is no API key or endpoint configured for a live
feed. This script is structurally complete (domain work-list from the indicator
index → RawStore, mirroring the VT/WHOIS fetchers) but **cannot run** until a
provider client and ``PDNS_API_KEY`` are supplied. It fails loudly rather than
silently doing nothing.

To finish it: implement ``_fetch_pdns(domain, api_key)`` against a chosen
provider (e.g. SecurityTrails / Farsight DNSDB / Circl pDNS), yielding the raw
per-domain JSON, then store each via ``RawStore.write("pdns", domain, raw, ts)``.
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti.ingest.raw_ingest import read_domains_from_index

_INDEX = Path("data/processed/indicator_index.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description="[placeholder] Fetch passive DNS into RawStore")
    parser.add_argument("--index", type=Path, default=_INDEX)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.parse_args()

    api_key = os.environ.get("PDNS_API_KEY", "")
    if not api_key:
        print(
            "pDNS raw fetch is NOT configured: set PDNS_API_KEY and wire a provider "
            "endpoint (see module docstring TODO). This is a placeholder script.",
            file=sys.stderr,
        )
        sys.exit(1)

    # The work-list plumbing is ready; only the provider client is missing.
    _domains = read_domains_from_index(_INDEX)
    raise NotImplementedError(
        "passive-DNS provider client not implemented — see scripts/refetch_pdns_raw.py docstring"
    )


if __name__ == "__main__":
    main()
