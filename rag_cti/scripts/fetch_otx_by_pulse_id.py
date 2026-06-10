"""Fetch OTX pulse descriptions by pulse_id from a CSV file.

Usage:
    python scripts/fetch_otx_by_pulse_id.py --csv /path/to/otx_domain_pulse_iocs.csv

Reads unique pulse_ids from CSV, fetches each pulse's full details via OTX API,
chunks the description text, and writes to data/processed/otx.jsonl.
Supports checkpoint-based resume on failure.
"""
from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports - run-without-install pattern)
import argparse
import csv
import json
import os
import subprocess
import sys
import time
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
DEFAULT_CHECKPOINT = Path("data/processed/.otx_checkpoint.jsonl")


def read_pulse_ids(csv_path: Path) -> list[str]:
    pulse_ids: set[str] = set()
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pid = row.get("pulse_id", "").strip()
            if pid:
                pulse_ids.add(pid)
    return sorted(pulse_ids)


def load_checkpoint(checkpoint_path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    if not checkpoint_path.exists():
        return records
    with checkpoint_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                records[rec["pulse_id"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return records


def append_checkpoint(checkpoint_path: Path, record: dict) -> None:
    with checkpoint_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def run(
    csv_path: Path,
    api_key: str,
    out_path: Path,
    checkpoint_path: Path,
    rate_limit: float,
    skip_ingest: bool,
) -> None:
    configure_logging("INFO")

    logger.info(
        "starting fetch_otx_by_pulse_id",
        csv=str(csv_path),
        out=str(out_path),
        checkpoint=str(checkpoint_path),
        rate_limit=rate_limit,
    )

    all_pulse_ids = read_pulse_ids(csv_path)
    logger.info("unique pulse_ids from CSV", count=len(all_pulse_ids))

    done = load_checkpoint(checkpoint_path)
    logger.info("checkpoint loaded", done=len(done))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect all chunks to write at the end (overwrite mode, matching fetch_otx.py)
    # But also include chunks from already-checkpointed OK pulses that we skip
    # We need to re-fetch for those... Actually no. We write as we go and collect.
    # Strategy: write output file fresh. For already-done pulses, we skip API calls
    # but we don't have their chunks cached. So we write output only for new fetches,
    # then prepend nothing. Actually fetch_otx.py opens with "w" mode (overwrite).
    #
    # Better approach: open in "w" mode, re-fetch done pulses from checkpoint?
    # No - that loses the point of checkpoint.
    #
    # Correct approach: open in "a" mode if checkpoint exists (resume), "w" if fresh start.
    # But the spec says "覆盖写入（和 fetch_otx.py 行为一致）".
    #
    # Resolution: if there's an existing checkpoint, we're resuming — append to output.
    # If no checkpoint, start fresh — overwrite output.
    is_resume = len(done) > 0
    file_mode = "a" if is_resume else "w"

    fetched = 0
    skipped_empty = 0
    failed = 0
    chunk_count = 0
    processed = 0

    pending_ids = [pid for pid in all_pulse_ids if pid not in done]
    logger.info("pulses to fetch", pending=len(pending_ids), already_done=len(done))

    # Count chunks from previous checkpoint for final report
    prev_chunks = sum(rec.get("chunks", 0) for rec in done.values() if rec.get("status") == "ok")
    prev_fetched = sum(1 for rec in done.values() if rec.get("status") == "ok")
    prev_empty = sum(1 for rec in done.values() if rec.get("status") == "empty")
    prev_failed = sum(1 for rec in done.values() if rec.get("status") == "error")

    with OTXConnector(api_key=api_key) as connector:
        with out_path.open(file_mode, encoding="utf-8") as fh:
            for i, pulse_id in enumerate(pending_ids):
                try:
                    pulse_data = connector._get(f"/api/v1/pulses/{pulse_id}")
                except Exception as exc:
                    logger.warning("fetch failed", pulse_id=pulse_id, error=str(exc))
                    failed += 1
                    append_checkpoint(checkpoint_path, {
                        "pulse_id": pulse_id,
                        "status": "error",
                        "error": str(exc),
                        "chunks": 0,
                    })
                    processed += 1
                    if i < len(pending_ids) - 1:
                        time.sleep(1.0 / rate_limit)
                    continue

                doc = connector.to_document(pulse_data)

                try:
                    validated = validate_content(doc.content, doc.source, doc.id)
                    clean_doc = doc.model_copy(update={"content": validated})
                except ValueError:
                    skipped_empty += 1
                    append_checkpoint(checkpoint_path, {
                        "pulse_id": pulse_id,
                        "status": "empty",
                        "chunks": 0,
                    })
                    processed += 1
                    if i < len(pending_ids) - 1:
                        time.sleep(1.0 / rate_limit)
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
                fh.flush()

                fetched += 1
                append_checkpoint(checkpoint_path, {
                    "pulse_id": pulse_id,
                    "status": "ok",
                    "chunks": len(chunks),
                })
                processed += 1

                if processed % 50 == 0:
                    logger.info(
                        "progress",
                        processed=processed,
                        pending_remaining=len(pending_ids) - processed,
                        fetched=fetched,
                        chunks=chunk_count,
                    )

                if i < len(pending_ids) - 1:
                    time.sleep(1.0 / rate_limit)

    total_fetched = prev_fetched + fetched
    total_empty = prev_empty + skipped_empty
    total_failed = prev_failed + failed
    total_chunks = prev_chunks + chunk_count

    logger.info(
        "done",
        total_pulses=len(all_pulse_ids),
        fetched=total_fetched,
        skipped_empty=total_empty,
        failed=total_failed,
        chunks_written=total_chunks,
    )
    print(f"\n{'=' * 60}")
    print(f"Total pulses:        {len(all_pulse_ids)}")
    print(f"Fetched (ok):        {total_fetched}")
    print(f"Skipped (empty):     {total_empty}")
    print(f"Failed:              {total_failed}")
    print(f"Chunks written:      {total_chunks}")
    print(f"{'=' * 60}")

    if not skip_ingest:
        print("\nRunning ingest.py --sources otx ...")
        subprocess.run(
            [sys.executable, "scripts/ingest.py", "--sources", "otx"],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch OTX pulse descriptions by pulse_id from a CSV file"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Path to CSV file with pulse_id column",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSONL path")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=DEFAULT_CHECKPOINT,
        help="Checkpoint JSONL path for resume support",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Requests per second (default: 1.0)",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        default=False,
        help="Skip running ingest.py after fetching",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OTX_API_KEY", "")
    if not api_key:
        print("ERROR: OTX_API_KEY not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(1)

    if not args.csv.exists():
        print(f"ERROR: CSV file not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    run(
        csv_path=args.csv,
        api_key=api_key,
        out_path=args.out,
        checkpoint_path=args.checkpoint,
        rate_limit=args.rate_limit,
        skip_ingest=args.skip_ingest,
    )


if __name__ == "__main__":
    main()
