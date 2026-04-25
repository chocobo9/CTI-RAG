"""Fetch AlienVault OTX pulses into data/processed/otx.jsonl.

Usage:
    python scripts/fetch_otx.py [--since 2024-01-01] [--out PATH]

Requires:
    OTX_API_KEY in .env or environment
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti._logging import configure_logging, get_logger
from rag_cti.connectors.otx import OTXConnector
from rag_cti.preprocess.chunking import ChunkStrategy, chunk_document
from rag_cti.preprocess.normalizers import validate_content
from rag_cti.types import Chunk

logger = get_logger(__name__)

DEFAULT_OUT = Path("data/processed/otx.jsonl")


def run(api_key: str, modified_since: str, out_path: Path) -> None:
    configure_logging("INFO")
    logger.info("fetching OTX pulses", modified_since=modified_since or "all", out=str(out_path))

    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc_count = 0
    chunk_count = 0
    skipped = 0

    with OTXConnector(api_key=api_key, modified_since=modified_since) as connector:
        with out_path.open("w", encoding="utf-8") as fh:
            for doc in connector.fetch_documents():
                try:
                    validated = validate_content(doc.content, doc.source, doc.id)
                    clean_doc = doc.model_copy(update={"content": validated})
                except ValueError as exc:
                    logger.warning("skipping document", doc_id=doc.id, reason=str(exc))
                    skipped += 1
                    continue

                chunks: list[Chunk] = chunk_document(
                    clean_doc, strategy=ChunkStrategy.SEMANTIC
                )
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

                if doc_count % 50 == 0:
                    logger.info("progress", documents=doc_count, chunks=chunk_count)

    logger.info("done", documents=doc_count, chunks=chunk_count, skipped=skipped)
    print(f"\n✓ {doc_count} pulses → {chunk_count} chunks written to {out_path}")
    if skipped:
        print(f"  {skipped} pulses skipped (empty content)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch OTX pulses into processed JSONL")
    parser.add_argument(
        "--since",
        default="",
        help="Only fetch pulses modified since this date (ISO 8601, e.g. 2024-01-01)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    api_key = os.environ.get("OTX_API_KEY", "")
    if not api_key:
        print("ERROR: OTX_API_KEY not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(1)

    run(api_key=api_key, modified_since=args.since, out_path=args.out)


if __name__ == "__main__":
    main()
