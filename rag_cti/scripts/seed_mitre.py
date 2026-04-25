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

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti._logging import configure_logging, get_logger
from rag_cti.connectors.mitre_attack import MitreAttackConnector
from rag_cti.preprocess.chunking import ChunkStrategy, chunk_document
from rag_cti.preprocess.normalizers import validate_content
from rag_cti.types import Chunk

logger = get_logger(__name__)

DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
DEFAULT_OUT = Path("data/processed/mitre.jsonl")


def run(bundle_path: Path, out_path: Path) -> None:
    configure_logging("INFO")
    logger.info("seeding MITRE ATT&CK", bundle=str(bundle_path), out=str(out_path))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    connector = MitreAttackConnector(bundle_path=bundle_path)

    doc_count = 0
    chunk_count = 0
    skipped = 0

    with out_path.open("w", encoding="utf-8") as fh:
        for doc in connector.fetch_documents():
            try:
                validated = validate_content(doc.content, doc.source, doc.id)
                clean_doc = doc.model_copy(update={"content": validated})
            except ValueError as exc:
                logger.warning("skipping document", doc_id=doc.id, reason=str(exc))
                skipped += 1
                continue

            chunks: list[Chunk] = chunk_document(clean_doc, strategy=ChunkStrategy.SEMANTIC)
            for chunk in chunks:
                fh.write(
                    json.dumps({
                        "id": chunk.id,
                        "parent_doc_id": chunk.parent_doc_id,
                        "source": chunk.source,
                        "content": chunk.content,
                        "chunk_index": chunk.chunk_index,
                        "metadata": chunk.metadata,
                        "retrieved_at": chunk.retrieved_at.isoformat(),
                    }) + "\n"
                )
                chunk_count += 1
            doc_count += 1

    logger.info("done", documents=doc_count, chunks=chunk_count, skipped=skipped)
    print(f"\n✓ {doc_count} documents → {chunk_count} chunks written to {out_path}")
    if skipped:
        print(f"  {skipped} documents skipped (empty content)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MITRE ATT&CK into processed JSONL")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(bundle_path=args.bundle, out_path=args.out)


if __name__ == "__main__":
    main()
