"""DEPRECATED — use ingest.py for all new collection setup.

ingest.py now owns the full collection lifecycle: it creates a hybrid schema via
ensure_collection() and fits or loads BM25SparseEncoder automatically. Delete the
existing collection and run `python scripts/ingest.py` to rebuild from scratch.

This script remains as a recovery tool (restores from data/migrate_dump.jsonl) but
should not be used for routine ingestion.

Original purpose — one-time migration: cti_chunks dense-only → named dense + BM25-sparse hybrid.

What this script does
─────────────────────
  1. Scroll all points from the existing Qdrant collection (dense vecs + payloads).
  2. Dump them to data/migrate_dump.jsonl as a safety checkpoint.
  3. Delete the collection.
  4. Re-create with named 'dense' + 'sparse' vector configs.
  5. Fit a BM25 encoder (IOC-preserving tokenizer) over the document corpus.
  6. Batch-upsert every point with its existing dense vector + new BM25 sparse vector.
  7. Save the BM25 vocabulary to data/sparse_vocab.json for query-time encoding.
  8. Verify final point count matches the dump.

Why no re-encoding
──────────────────
  Dense vectors are already stored in Qdrant; we scroll them out and re-upload
  them under the new named 'dense' key without calling the embedding model again.
  BM25 sparse vectors are CPU-only (milliseconds per document), so total migration
  time is ~2-3 min instead of a 20 min full re-ingest.

Usage
─────
  python scripts/migrate_to_hybrid.py
  python scripts/migrate_to_hybrid.py --dry-run        # inspect without writing
  python scripts/migrate_to_hybrid.py --batch-size 128

NEXT STEPS (Phase 4 — do NOT edit QdrantStore now)
───────────────────────────────────────────────────
  After running this script:
  1. Update QdrantStore.search()        -> pass using="dense"
  2. Add QdrantStore.sparse_search()   -> using="sparse"
  3. Update ingest.py upsert path      -> write both vectors via
     BM25SparseEncoder.load(Path("data/sparse_vocab.json"))
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from rag_cti._logging import configure_logging, get_logger
from rag_cti.config import get_settings
from rag_cti.retrieval.bm25 import BM25SparseEncoder, tokenize

logger = get_logger(__name__)

_DUMP_PATH = Path("data/migrate_dump.jsonl")
_VOCAB_PATH = Path("data/sparse_vocab.json")


# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------

def _scroll_all(client: QdrantClient, collection: str, batch_size: int) -> list:
    records: list = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=collection,
            with_vectors=True,
            with_payload=True,
            limit=batch_size,
            offset=offset,
        )
        records.extend(batch)
        logger.info("scroll progress", fetched=len(records))
        if offset is None:
            break
    return records


def _dump_records(records: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(
                json.dumps({"id": rec.id, "vector": rec.vector, "payload": rec.payload})
                + "\n"
            )
    logger.info("safety dump written", path=str(path), count=len(records))


def _extract_dense(record) -> list[float]:
    """Extract the dense float list from an unnamed or named-vector record."""
    vec = record.vector
    if isinstance(vec, dict):
        # Named vectors: grab whichever is the dense one
        return list(next(iter(vec.values())))
    return list(vec)  # plain list from an unnamed-vector collection


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

def migrate(
    client: QdrantClient,
    collection: str,
    batch_size: int,
    dry_run: bool,
) -> None:
    total = client.count(collection_name=collection).count
    print(f"\n  Collection : '{collection}'")
    print(f"  Points     : {total:,}")
    print(f"  Dry-run    : {dry_run}\n")

    # ── 1. Scroll ─────────────────────────────────────────────────────────────
    print("[1/6] Scrolling all points from Qdrant ...")
    records = _scroll_all(client, collection, batch_size)
    print(f"      {len(records):,} records fetched.\n")

    if not records:
        print("ERROR: collection is empty. Nothing to migrate.")
        sys.exit(1)

    # ── 2. Safety dump ────────────────────────────────────────────────────────
    print(f"[2/6] Writing safety dump -> {_DUMP_PATH}")
    if not dry_run:
        _dump_records(records, _DUMP_PATH)
        print(f"      Done. ({_DUMP_PATH.stat().st_size // 1024:,} KB)\n")
    else:
        print("      [dry-run] skipped.\n")

    # ── 3. Infer dense dimension ──────────────────────────────────────────────
    dense_dim = len(_extract_dense(records[0]))
    print(f"[3/6] Dense dimension inferred: {dense_dim}\n")

    # ── 4. Delete + recreate ──────────────────────────────────────────────────
    print("[4/6] Recreating collection with named dense + sparse vectors ...")
    if not dry_run:
        client.delete_collection(collection_name=collection)
        client.create_collection(
            collection_name=collection,
            vectors_config={
                "dense": VectorParams(size=dense_dim, distance=Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=False),
                ),
            },
        )
        logger.info("collection recreated", dense_dim=dense_dim)
        print("      Done.\n")
    else:
        print("      [dry-run] skipped.\n")

    # ── 5. Fit BM25 encoder ───────────────────────────────────────────────────
    print(f"[5/6] Fitting BM25 encoder on {len(records):,} documents ...")
    t0 = time.perf_counter()
    encoder = BM25SparseEncoder()
    texts = [rec.payload.get("content", "") for rec in records]
    encoder.fit(texts)
    elapsed = time.perf_counter() - t0
    print(
        f"      vocab={len(encoder.vocab):,} terms | "
        f"avgdl={encoder.avgdl:.0f} tokens | "
        f"elapsed={elapsed:.1f}s\n"
    )
    if not dry_run:
        encoder.save(_VOCAB_PATH)
        print(f"      Vocabulary -> {_VOCAB_PATH}\n")

    # ── 6. Batch upsert ───────────────────────────────────────────────────────
    print(f"[6/6] Upserting {len(records):,} points (batch_size={batch_size}) ...")
    t0 = time.perf_counter()
    upserted = 0

    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        points: list[PointStruct] = []

        for rec in batch:
            dense_vec = _extract_dense(rec)
            content = rec.payload.get("content", "")
            sp_indices, sp_values = encoder.encode_document(content)

            points.append(
                PointStruct(
                    id=rec.id,
                    vector={
                        "dense": dense_vec,
                        "sparse": SparseVector(
                            indices=sp_indices,
                            values=sp_values,
                        ),
                    },
                    payload=rec.payload,
                )
            )

        if not dry_run:
            client.upsert(collection_name=collection, points=points)

        upserted += len(batch)
        pct = upserted / len(records) * 100
        print(f"      {upserted:,}/{len(records):,}  ({pct:.0f}%)", end="\r")

    print(f"\n      Finished in {time.perf_counter() - t0:.1f}s\n")

    # ── Verification ──────────────────────────────────────────────────────────
    if not dry_run:
        final = client.count(collection_name=collection).count
        ok = final == len(records)
        status = "PASS" if ok else "FAIL"
        print(f"Verification [{status}]: {final:,} points in collection (expected {len(records):,})")
        if not ok:
            print(f"\n  Recovery: restore from {_DUMP_PATH} or re-run scripts/ingest.py")
            sys.exit(1)

    _print_summary(collection, dense_dim, len(encoder.vocab), dry_run)


def _print_summary(
    collection: str, dense_dim: int, vocab_size: int, dry_run: bool
) -> None:
    tag = "[DRY-RUN] " if dry_run else ""
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  {tag}Migration complete")
    print(sep)
    print(f"  Collection    : '{collection}'")
    print(f"  Dense vector  : name='dense'   dim={dense_dim}")
    print(f"  Sparse vector : name='sparse'  vocab={vocab_size:,} terms")
    print(f"  Vocab file    : {_VOCAB_PATH}")
    print(f"  Dump file     : {_DUMP_PATH}  (keep until Phase 4 is stable)")
    print(sep)
    print()
    print("  NEXT STEPS (Phase 4):")
    print("  1. QdrantStore.search()        -> pass using='dense'")
    print("  2. QdrantStore.sparse_search() -> using='sparse'")
    print(f"  3. ingest.py upsert            -> write both vectors via")
    print(f"     BM25SparseEncoder.load(Path('{_VOCAB_PATH}'))")
    print(f"{sep}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate cti_chunks to named dense + BM25-sparse hybrid collection"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Points per scroll / upsert batch (default: 64)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scroll + fit encoder without deleting or writing to Qdrant",
    )
    args = parser.parse_args()

    configure_logging("INFO")
    settings = get_settings()

    if args.dry_run:
        print("\n[DRY RUN] No Qdrant writes will be performed.\n")

    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() or None,
    )

    migrate(
        client=client,
        collection=settings.qdrant_collection,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
