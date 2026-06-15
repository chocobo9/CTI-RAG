"""Shared connector -> validated chunks -> processed JSONL pipeline.

Every seed/fetch script (MITRE, relationships, PDFs, OTX, WHOIS) runs the same
loop: ``connector.fetch_documents()`` -> ``validate_content`` -> ``chunk_document``
-> one JSON line per chunk. This module is the single implementation; scripts
only pick the connector, the output path, and the chunk strategy.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.preprocess.chunking import ChunkStrategy, chunk_document
from rag_cti.preprocess.normalizers import validate_content
from rag_cti.types import Chunk

logger = get_logger(__name__)


@dataclass(frozen=True)
class SeedStats:
    documents: int
    chunks: int
    skipped: int

    def summary(self, out_path: Path) -> str:
        line = f"{self.documents} documents -> {self.chunks} chunks written to {out_path}"
        if self.skipped:
            line += f"\n  {self.skipped} documents skipped (empty content)"
        return line


def chunk_to_jsonl_dict(chunk: Chunk) -> dict[str, Any]:
    """The canonical processed-JSONL record shape shared by all seed scripts."""
    return {
        "id": chunk.id,
        "parent_doc_id": chunk.parent_doc_id,
        "source": chunk.source,
        "content": chunk.content,
        "chunk_index": chunk.chunk_index,
        "metadata": chunk.metadata,
        "retrieved_at": chunk.retrieved_at.isoformat(),
    }


def seed_connector_to_jsonl(
    connector: Any,
    out_path: Path,
    strategy: ChunkStrategy,
    limit: int | None = None,
    progress_every: int = 50,
) -> SeedStats:
    """Drain a connector into a processed-chunks JSONL file (overwrites).

    Documents failing content validation are counted in ``skipped`` (and logged),
    matching the previous per-script behaviour.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc_count = 0
    chunk_count = 0
    skipped = 0

    with out_path.open("w", encoding="utf-8") as fh:
        for doc in connector.fetch_documents():
            if limit is not None and doc_count >= limit:
                break

            try:
                validated = validate_content(doc.content, doc.source, doc.id)
                clean_doc = doc.model_copy(update={"content": validated})
            except ValueError as exc:
                logger.warning("skipping document", doc_id=doc.id, reason=str(exc))
                skipped += 1
                continue

            for chunk in chunk_document(clean_doc, strategy=strategy):
                fh.write(json.dumps(chunk_to_jsonl_dict(chunk)) + "\n")
                chunk_count += 1
            doc_count += 1

            if progress_every and doc_count % progress_every == 0:
                logger.info("progress", documents=doc_count, chunks=chunk_count)

    logger.info("done", documents=doc_count, chunks=chunk_count, skipped=skipped)
    return SeedStats(documents=doc_count, chunks=chunk_count, skipped=skipped)


def seed_connector_with_projection(
    connector: Any,
    projector: Callable[[dict[str, Any]], dict[str, Any]],
    out_path: Path,
    strategy: ChunkStrategy,
    limit: int | None = None,
    progress_every: int = 50,
) -> SeedStats:
    """Like :func:`seed_connector_to_jsonl`, but iterate the connector's **raw**
    records so each chunk also carries the M2 payload projection (M2.6 wiring).

    ``projector(raw)`` returns the projection dict (source_type / attack_ids /
    entity_ids / relations) for that record — computed from normalize→project_chunk
    on the raw, where the STIX types are still available. It is merged into the
    Document metadata before chunking, so QdrantStore._chunk_to_payload surfaces it
    as top-level filter keys. A projector failure logs and falls back to no
    projection (the chunk still ingests, just without filter keys).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc_count = chunk_count = skipped = 0

    with out_path.open("w", encoding="utf-8") as fh:
        for raw in connector.fetch():
            if limit is not None and doc_count >= limit:
                break
            try:
                doc = connector.to_document(raw)
            except Exception as exc:
                logger.warning(
                    "skipping malformed record", source=connector.source_name, error=str(exc)
                )
                skipped += 1
                continue
            try:
                projection = projector(raw)
            except Exception as exc:
                logger.warning("projection failed", doc_id=doc.id, error=str(exc))
                projection = {}
            doc = doc.model_copy(update={"metadata": {**doc.metadata, **projection}})

            try:
                validated = validate_content(doc.content, doc.source, doc.id)
                clean_doc = doc.model_copy(update={"content": validated})
            except ValueError as exc:
                logger.warning("skipping document", doc_id=doc.id, reason=str(exc))
                skipped += 1
                continue

            for chunk in chunk_document(clean_doc, strategy=strategy):
                fh.write(json.dumps(chunk_to_jsonl_dict(chunk)) + "\n")
                chunk_count += 1
            doc_count += 1

            if progress_every and doc_count % progress_every == 0:
                logger.info("progress", documents=doc_count, chunks=chunk_count)

    logger.info("done", documents=doc_count, chunks=chunk_count, skipped=skipped)
    return SeedStats(documents=doc_count, chunks=chunk_count, skipped=skipped)
