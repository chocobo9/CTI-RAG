"""Seed MITRE ATT&CK relationship data into data/processed/mitre_relationships.jsonl.

Usage:
    python scripts/seed_mitre_relationships.py
    python scripts/seed_mitre_relationships.py --limit 50
    python scripts/seed_mitre_relationships.py --bundle PATH --out PATH
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti._logging import configure_logging, get_logger
from rag_cti.connectors.mitre_relationship import MitreRelationshipConnector
from rag_cti.preprocess.chunking import ChunkStrategy
from rag_cti.preprocess.seeding import seed_connector_to_jsonl

logger = get_logger(__name__)

DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
DEFAULT_OUT = Path("data/processed/mitre_relationships.jsonl")


def run(bundle_path: Path, out_path: Path, limit: int | None = None) -> None:
    configure_logging("INFO")
    logger.info(
        "seeding MITRE relationships",
        bundle=str(bundle_path),
        out=str(out_path),
        limit=limit,
    )
    connector = MitreRelationshipConnector(bundle_path=bundle_path)
    stats = seed_connector_to_jsonl(connector, out_path, ChunkStrategy.STRUCTURED, limit=limit)
    print(f"\n[ok] {stats.summary(out_path)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MITRE relationships into processed JSONL")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None, help="Max documents to process")
    args = parser.parse_args()
    run(bundle_path=args.bundle, out_path=args.out, limit=args.limit)


if __name__ == "__main__":
    main()
