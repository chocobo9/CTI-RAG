"""Embed processed JSONL chunks and upsert them into Qdrant.

Usage:
    python scripts/ingest.py [--sources mitre otx pdfs] [--collection NAME]
                             [--batch-size 64] [--processed-dir PATH]

Any processed JSONL under data/processed/ works as a source name, e.g.
``--sources mitre mitre_relationships otx pdfs whois``.

Reads chunks from data/processed/<source>.jsonl, computes embeddings with
the configured sentence-transformers model, and upserts them into one
unified Qdrant collection. Idempotent: re-running overwrites by point ID.
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports - run-without-install pattern)
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti._logging import configure_logging, get_logger
from rag_cti.config import get_settings
from rag_cti.embeddings.embedder import Embedder
from rag_cti.retrieval.bm25 import BM25SparseEncoder
from rag_cti.store.qdrant_store import QdrantStore, assert_unique_chunk_ids
from rag_cti.types import Chunk

logger = get_logger(__name__)

_DEFAULT_PROCESSED_DIR = Path("data/processed")
_DEFAULT_SOURCES = ("mitre", "otx", "pdfs")
_DEFAULT_SPARSE_VOCAB = Path("data/processed/sparse_vocab/sparse_vocab.json")


def _load_chunks(jsonl_path: Path, embedding_model: str) -> list[Chunk]:
    """Read a processed JSONL file and return Chunk objects."""
    if not jsonl_path.exists():
        logger.warning("processed file missing, skipping", path=str(jsonl_path))
        return []

    chunks: list[Chunk] = []
    with jsonl_path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                chunks.append(
                    Chunk(
                        id=record["id"],
                        parent_doc_id=record["parent_doc_id"],
                        source=record["source"],
                        content=record["content"],
                        chunk_index=record["chunk_index"],
                        metadata=record.get("metadata", {}),
                        retrieved_at=datetime.fromisoformat(record["retrieved_at"]),
                        embedding_model=embedding_model,
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.warning(
                    "skipping malformed line",
                    path=str(jsonl_path),
                    line=line_no,
                    error=str(exc),
                )
    return chunks


def _ingest_source(
    source: str,
    processed_dir: Path,
    embedder: Embedder,
    store: QdrantStore,
    embed_batch: int,
    sparse_encoder: BM25SparseEncoder | None = None,
    seen_ids: dict[str, str] | None = None,
) -> tuple[int, int]:
    """Ingest one source's JSONL file. Returns (chunks_read, points_written)."""
    jsonl_path = processed_dir / f"{source}.jsonl"
    chunks = _load_chunks(jsonl_path, embedder.model_name)
    if not chunks:
        return 0, 0

    # Fail loud on id collisions before any upsert (Rule 0): a duplicate id with
    # different content would silently overwrite a Qdrant point. seen_ids is
    # shared across sources to catch cross-source collisions too.
    assert_unique_chunk_ids(chunks, seen_ids)

    logger.info(
        "embedding chunks", source=source, count=len(chunks), hybrid=sparse_encoder is not None
    )
    written = 0
    for start in range(0, len(chunks), embed_batch):
        batch = chunks[start : start + embed_batch]
        vectors = embedder.encode([c.content for c in batch])
        if sparse_encoder is not None:
            written += store.upsert_hybrid(batch, vectors, sparse_encoder)
        else:
            written += store.upsert(batch, vectors)
        if (start // embed_batch) % 5 == 0:
            logger.info("progress", source=source, embedded=start + len(batch), total=len(chunks))

    logger.info("source ingested", source=source, chunks=len(chunks), written=written)
    return len(chunks), written


def run(
    sources: list[str],
    collection: str | None,
    processed_dir: Path,
    embed_batch: int,
    device: str | None = None,
    sparse_vocab: Path | None = None,
) -> None:
    configure_logging("INFO")
    settings = get_settings()

    vocab_path = sparse_vocab or _DEFAULT_SPARSE_VOCAB
    coll_name = collection or settings.qdrant_collection
    embedder = Embedder(settings.embedding_model, batch_size=embed_batch, device=device)
    store = QdrantStore(
        url=settings.qdrant_url,
        collection=coll_name,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )

    store.ensure_collection(vector_size=embedder.dimension)
    store.ensure_payload_indexes()

    if vocab_path.exists():
        encoder = BM25SparseEncoder.load(vocab_path)
        logger.info("BM25 encoder loaded", vocab_size=len(encoder.vocab), path=str(vocab_path))
    else:
        logger.info(
            "sparse vocab not found — fitting BM25 on ingestion corpus",
            path=str(vocab_path),
        )
        all_texts: list[str] = []
        for source in sources:
            for chunk in _load_chunks(processed_dir / f"{source}.jsonl", embedder.model_name):
                all_texts.append(chunk.content)
        encoder = BM25SparseEncoder()
        encoder.fit(all_texts)
        encoder.save(vocab_path)
        logger.info("BM25 encoder fitted and saved", vocab_size=len(encoder.vocab))

    total_chunks = 0
    total_written = 0
    seen_ids: dict[str, str] = {}
    for source in sources:
        c, w = _ingest_source(
            source,
            processed_dir,
            embedder,
            store,
            embed_batch,
            sparse_encoder=encoder,
            seen_ids=seen_ids,
        )
        total_chunks += c
        total_written += w

    logger.info(
        "ingest complete",
        sources=sources,
        chunks=total_chunks,
        written=total_written,
        collection=coll_name,
    )
    print(
        f"\n✓ {total_written} points written to Qdrant collection '{coll_name}'"
        f" from {total_chunks} chunks across {len(sources)} source(s)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed and ingest CTI chunks into Qdrant")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=list(_DEFAULT_SOURCES),
        help="Source names (match processed JSONL filenames without extension)",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Qdrant collection name (defaults to QDRANT_COLLECTION from settings)",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=_DEFAULT_PROCESSED_DIR,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Embedding and upsert batch size",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Device for sentence-transformers inference, e.g. 'cpu', 'cuda', 'mps'. "
        "Defaults to auto-detect.",
    )
    parser.add_argument(
        "--sparse-vocab",
        type=Path,
        default=None,
        help="BM25 vocab path (loaded if it exists, else fitted+saved here). Defaults to "
        "data/processed/sparse_vocab/sparse_vocab.json. Pass a per-collection path when "
        "building a new collection.",
    )
    args = parser.parse_args()

    run(
        sources=args.sources,
        collection=args.collection,
        processed_dir=args.processed_dir,
        embed_batch=args.batch_size,
        device=args.device,
        sparse_vocab=args.sparse_vocab,
    )


if __name__ == "__main__":
    main()
