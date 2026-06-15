"""Seed MITRE ATT&CK relationship data into data/processed/mitre_relationships.jsonl.

Usage:
    python scripts/seed_mitre_relationships.py
    python scripts/seed_mitre_relationships.py --limit 50
    python scripts/seed_mitre_relationships.py --bundle PATH --out PATH
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti._logging import configure_logging, get_logger
from rag_cti.connectors.mitre_relationship import MitreRelationshipConnector
from rag_cti.ingest.normalize import normalize_mitre_relationship
from rag_cti.preprocess.chunk_projection import project_chunk
from rag_cti.preprocess.chunking import ChunkStrategy
from rag_cti.preprocess.ontology_nodes import ontology_nodes_from_bundle
from rag_cti.preprocess.seeding import seed_connector_with_projection
from rag_cti.store.raw_store import RawStore, parse_fetched_at

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
    versions = RawStore().versions("mitre", "enterprise-attack")
    fetched_at = parse_fetched_at(versions[-1] if versions else None)
    connector = MitreRelationshipConnector(bundle_path=bundle_path, fetched_at=fetched_at)

    # M2.6: project each edge's entity_ids/relations into the chunk payload. The
    # connector yields raw STIX relationships; normalize→project resolves them
    # against the ontology (the same bundle), where the STIX types are available.
    with bundle_path.open(encoding="utf-8") as fh:
        bundle = json.load(fh)
    nodes = ontology_nodes_from_bundle(bundle)
    index = {o["id"]: o for o in bundle.get("objects", []) if "id" in o}

    def projector(raw: dict[str, Any]) -> dict[str, Any]:
        return project_chunk(normalize_mitre_relationship(raw, index), nodes)

    stats = seed_connector_with_projection(
        connector, projector, out_path, ChunkStrategy.STRUCTURED, limit=limit
    )
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
