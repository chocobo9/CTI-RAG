"""Seed MITRE ATT&CK data into data/processed/mitre.jsonl.

Usage:
    python scripts/seed_mitre.py [--bundle PATH] [--out PATH]

Prerequisites:
    Download enterprise-attack.json from:
    https://github.com/mitre-attack/attack-stix-data/tree/master/enterprise-attack
    Place at data/raw/mitre/enterprise-attack.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti._logging import configure_logging, get_logger
from rag_cti.connectors.mitre_attack import MitreAttackConnector
from rag_cti.preprocess.chunking import ChunkStrategy
from rag_cti.preprocess.seeding import seed_connector_to_jsonl

logger = get_logger(__name__)

DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
DEFAULT_OUT = Path("data/processed/mitre.jsonl")


def run(bundle_path: Path, out_path: Path) -> None:
    configure_logging("INFO")
    logger.info("seeding MITRE ATT&CK", bundle=str(bundle_path), out=str(out_path))
    connector = MitreAttackConnector(bundle_path=bundle_path)
    stats = seed_connector_to_jsonl(connector, out_path, ChunkStrategy.SEMANTIC)
    print(f"\n[ok] {stats.summary(out_path)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MITRE ATT&CK into processed JSONL")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(bundle_path=args.bundle, out_path=args.out)


if __name__ == "__main__":
    main()
