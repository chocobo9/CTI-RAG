"""PDF CTI report connector — scans a directory and yields Document per section."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.connectors.base import BaseConnector
from rag_cti.preprocess.pdf_parser import parse_pdf
from rag_cti.store.raw_store import SENTINEL_FETCHED_AT
from rag_cti.types import Document

logger = get_logger(__name__)

_DEFAULT_PDF_DIR = Path("data/raw/pdfs")


class PDFReportsConnector(BaseConnector):
    """Converts CTI PDF reports under a directory into section-level Documents."""

    source_name = "pdf"

    def __init__(
        self, pdf_dir: Path = _DEFAULT_PDF_DIR, fetched_at: datetime | None = None
    ) -> None:
        self._pdf_dir = pdf_dir
        # retrieved_at = when WE ingested the PDF; existing PDFs have no recorded
        # fetch event, so a deterministic sentinel (never wall-clock).
        self._fetched_at = fetched_at or SENTINEL_FETCHED_AT

    def fetch(self, **_: Any) -> Iterator[dict[str, Any]]:
        if not self._pdf_dir.exists():
            logger.warning("pdf directory not found, yielding nothing", path=str(self._pdf_dir))
            return

        pdf_files = sorted(self._pdf_dir.glob("**/*.pdf"))
        if not pdf_files:
            logger.warning("no PDF files found", path=str(self._pdf_dir))
            return

        for pdf_path in pdf_files:
            sections = parse_pdf(pdf_path)
            if not sections:
                logger.warning("no sections extracted from pdf", path=str(pdf_path))
                continue
            for idx, section in enumerate(sections):
                yield {
                    "pdf_path": str(pdf_path),
                    "section_index": idx,
                    "text": section["text"],
                    "section_title": section.get("section_title", ""),
                    "page": section.get("page", 1),
                }

    def to_document(self, raw: dict[str, Any]) -> Document:
        pdf_path = raw["pdf_path"]
        filename = Path(pdf_path).name
        section_index = raw["section_index"]

        file_id = hashlib.sha256(f"pdf:{filename}".encode()).hexdigest()[:16]
        section_id = hashlib.sha256(f"pdf:{pdf_path}:{section_index}".encode()).hexdigest()[:16]

        return Document(
            id=section_id,
            source=self.source_name,
            content=raw["text"],
            retrieved_at=self._fetched_at,
            metadata={
                "pdf_path": pdf_path,
                "filename": filename,
                "file_id": file_id,
                "section_title": raw["section_title"],
                "page": raw["page"],
                "section_index": section_index,
            },
        )
