"""Fetch WHOIS records via the Whoxy API into data/processed/whois.jsonl.

Bridges the gap that left WHOISConnector unused: the connector consumes
pre-fetched record dicts, and this script is the fetcher that produces them.

Usage:
    python scripts/fetch_whois.py --domains domains.txt
    python scripts/fetch_whois.py --domain evil.example --domain bad.example
    python scripts/fetch_whois.py --records prefetched_records.json   # offline

Requires WHOXY_API_KEY in .env (not needed with --records).
The output JSONL feeds scripts/ingest.py like every other processed source.
"""
from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti._logging import configure_logging, get_logger
from rag_cti.config import get_settings
from rag_cti.connectors.whois_connector import WHOISConnector
from rag_cti.connectors.whoxy import WhoxyClient
from rag_cti.preprocess.chunking import ChunkStrategy
from rag_cti.preprocess.seeding import seed_connector_to_jsonl

logger = get_logger(__name__)

DEFAULT_OUT = Path("data/processed/whois.jsonl")
# Whoxy allows generous rates, but stay polite on batch lookups.
DEFAULT_DELAY_S = 0.5


def _load_domains(domains_file: Path | None, domains: list[str]) -> list[str]:
    out: list[str] = list(domains)
    if domains_file:
        out += [
            line.strip()
            for line in domains_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    # de-dup, preserve order
    seen: set[str] = set()
    unique = [d for d in out if not (d in seen or seen.add(d))]
    return unique


def fetch_records(domains: list[str], api_key: str, delay_s: float) -> list[dict]:
    records: list[dict] = []
    failed: list[str] = []
    with WhoxyClient(api_key=api_key) as client:
        for i, domain in enumerate(domains, start=1):
            try:
                records.append(client.whois(domain))
            except Exception as exc:
                logger.warning("whois lookup failed", domain=domain, error=str(exc))
                failed.append(domain)
            if i % 10 == 0:
                logger.info("progress", looked_up=i, total=len(domains), failed=len(failed))
            if delay_s and i < len(domains):
                time.sleep(delay_s)
    if failed:
        print(f"  WARNING: {len(failed)} lookups failed: {failed}", file=sys.stderr)
    return records


def main() -> None:
    configure_logging("INFO")
    parser = argparse.ArgumentParser(description="Fetch WHOIS records (Whoxy) into processed JSONL")
    parser.add_argument("--domains", type=Path, default=None, help="File with one domain per line")
    parser.add_argument("--domain", action="append", default=[], help="Domain to look up (repeatable)")
    parser.add_argument(
        "--records", type=Path, default=None,
        help="Pre-fetched JSON list of WHOIS record dicts (skips the Whoxy API)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_S, help="Seconds between lookups")
    args = parser.parse_args()

    if args.records:
        records = json.loads(args.records.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            print("ERROR: --records must contain a JSON list of record dicts.", file=sys.stderr)
            sys.exit(1)
    else:
        domains = _load_domains(args.domains, args.domain)
        if not domains:
            print("ERROR: no domains given — use --domains FILE, --domain D, or --records JSON.",
                  file=sys.stderr)
            sys.exit(1)
        api_key = get_settings().whoxy_api_key.get_secret_value()
        if not api_key:
            print("ERROR: WHOXY_API_KEY not set. Add it to .env.", file=sys.stderr)
            sys.exit(1)
        logger.info("fetching WHOIS via Whoxy", domains=len(domains))
        records = fetch_records(domains, api_key, args.delay)

    connector = WHOISConnector(records=records)
    stats = seed_connector_to_jsonl(connector, args.out, ChunkStrategy.STRUCTURED)
    print(f"\n[ok] {stats.summary(args.out)}")


if __name__ == "__main__":
    main()
