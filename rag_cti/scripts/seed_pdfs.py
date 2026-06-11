"""Ingest CTI PDF reports into data/processed/pdfs.jsonl.

Usage:
    python scripts/seed_pdfs.py [--pdf-dir PATH] [--out PATH]

Prerequisites:
    Place PDF reports under data/raw/pdfs/ (sub-directories are scanned recursively).
    Install optional PDF deps: pip install "unstructured[pdf]" pymupdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti._logging import configure_logging, get_logger
from rag_cti.connectors.pdf_reports import PDFReportsConnector
from rag_cti.preprocess.chunking import ChunkStrategy
from rag_cti.preprocess.seeding import seed_connector_to_jsonl

logger = get_logger(__name__)

DEFAULT_PDF_DIR = Path("data/raw/pdfs")
DEFAULT_OUT = Path("data/processed/pdfs.jsonl")


def run(pdf_dir: Path, out_path: Path) -> None:
    configure_logging("INFO")
    logger.info("ingesting PDF reports", pdf_dir=str(pdf_dir), out=str(out_path))
    connector = PDFReportsConnector(pdf_dir=pdf_dir)
    stats = seed_connector_to_jsonl(connector, out_path, ChunkStrategy.SEMANTIC, progress_every=20)
    print(f"\n[ok] {stats.summary(out_path)}")


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
