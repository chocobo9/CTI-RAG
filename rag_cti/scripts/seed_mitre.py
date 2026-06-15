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
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti._logging import configure_logging, get_logger
from rag_cti.connectors.mitre_attack import MitreAttackConnector
from rag_cti.ingest.normalize import EntityMention, NormalizedRecord, Provenance, SourceClass
from rag_cti.preprocess.chunk_projection import project_chunk
from rag_cti.preprocess.chunking import ChunkStrategy
from rag_cti.preprocess.ontology_nodes import ontology_nodes_from_bundle
from rag_cti.preprocess.seeding import seed_connector_with_projection
from rag_cti.store.raw_store import RawStore, parse_fetched_at

logger = get_logger(__name__)

DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
DEFAULT_OUT = Path("data/processed/mitre.jsonl")


def _attack_id(raw: dict[str, Any]) -> str:
    for ref in raw.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return str(ref.get("external_id", ""))
    return ""


def run(bundle_path: Path, out_path: Path) -> None:
    configure_logging("INFO")
    logger.info("seeding MITRE ATT&CK", bundle=str(bundle_path), out=str(out_path))
    versions = RawStore().versions("mitre", "enterprise-attack")
    fetched_at = parse_fetched_at(versions[-1] if versions else None)
    connector = MitreAttackConnector(bundle_path=bundle_path, fetched_at=fetched_at)

    # M2.6: a technique doc projects to its own attack id + technique entity, so a
    # query filtering attack_id=T#### matches the technique's own chunk.
    with bundle_path.open(encoding="utf-8") as fh:
        nodes = ontology_nodes_from_bundle(json.load(fh))

    def projector(raw: dict[str, Any]) -> dict[str, Any]:
        aid = _attack_id(raw)
        mentions = [EntityMention(aid, "technique")] if aid else []
        record = NormalizedRecord(
            provenance=Provenance(source_type="mitre", source_id=str(raw.get("id", ""))),
            classification=SourceClass.ONTOLOGY,
            content="",
            entity_mentions=mentions,
        )
        return project_chunk(record, nodes)

    stats = seed_connector_with_projection(connector, projector, out_path, ChunkStrategy.SEMANTIC)
    print(f"\n[ok] {stats.summary(out_path)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MITRE ATT&CK into processed JSONL")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(bundle_path=args.bundle, out_path=args.out)


if __name__ == "__main__":
    main()
