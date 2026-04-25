"""Ingest CTI PDF reports into data/processed/pdfs.jsonl.

Usage:
    python scripts/seed_pdfs.py [--pdf-dir PATH] [--out PATH]

Prerequisites:
    Place PDF reports under data/raw/pdfs/ (sub-directories are scanned recursively).
    Install optional PDF deps: pip install "unstructured[pdf]" pymupdf
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti._logging import configure_logging, get_logger
from rag_cti.connectors.pdf_reports import PDFReportsConnector
from rag_cti.preprocess.chunking import ChunkStrategy, chunk_document
from rag_cti.preprocess.normalizers import validate_content
from rag_cti.types import Chunk

logger = get_logger(__name__)

DEFAULT_PDF_DIR = Path("data/raw/pdfs")
DEFAULT_OUT = Path("data/processed/pdfs.jsonl")


def run(pdf_dir: Path, out_path: Path) -> None:
    configure_logging("INFO")
    logger.info("ingesting PDF reports", pdf_dir=str(pdf_dir), out=str(out_path))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    connector = PDFReportsConnector(pdf_dir=pdf_dir)

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

            if doc_count % 20 == 0:
                logger.info("progress", documents=doc_count, chunks=chunk_count)

    logger.info("done", documents=doc_count, chunks=chunk_count, skipped=skipped)
    print(f"\n✓ {doc_count} PDF sections → {chunk_count} chunks written to {out_path}")
    if skipped:
        print(f"  {skipped} sections skipped (empty content)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest CTI PDF reports into processed JSONL")
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help="Directory containing PDF files (searched recursively)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(pdf_dir=args.pdf_dir, out_path=args.out)


if __name__ == "__main__":
    main()
