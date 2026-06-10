"""Fetch AlienVault OTX pulses into data/processed/otx.jsonl.

Usage:
    python scripts/fetch_otx.py [--since 2024-01-01] [--out PATH]

Requires:
    OTX_API_KEY in .env or environment
"""
from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti._logging import configure_logging, get_logger
from rag_cti.config import get_settings
from rag_cti.connectors.otx import OTXConnector
from rag_cti.preprocess.chunking import ChunkStrategy
from rag_cti.preprocess.seeding import seed_connector_to_jsonl

logger = get_logger(__name__)

DEFAULT_OUT = Path("data/processed/otx.jsonl")


def run(api_key: str, modified_since: str, out_path: Path) -> None:
    configure_logging("INFO")
    logger.info("fetching OTX pulses", modified_since=modified_since or "all", out=str(out_path))
    with OTXConnector(api_key=api_key, modified_since=modified_since) as connector:
        stats = seed_connector_to_jsonl(connector, out_path, ChunkStrategy.SEMANTIC)
    print(f"\n[ok] {stats.summary(out_path)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch OTX pulses into processed JSONL")
    parser.add_argument(
        "--since",
        default="",
        help="Only fetch pulses modified since this date (ISO 8601, e.g. 2024-01-01)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    api_key = get_settings().otx_api_key.get_secret_value()
    if not api_key:
        print("ERROR: OTX_API_KEY not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(1)

    run(api_key=api_key, modified_since=args.since, out_path=args.out)


if __name__ == "__main__":
    main()
