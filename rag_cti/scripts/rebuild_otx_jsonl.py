"""Rebuild data/processed/otx.jsonl from raw JSON files.

Usage:
    python scripts/rebuild_otx_jsonl.py [--out data/processed/otx.jsonl]

Reads every data/raw/otx/{pulse_id}.json, renders it with the canonical
connector mapping (rag_cti.connectors.otx.render_pulse_content /
pulse_metadata — adversary, malware_families, targeted_countries,
references included), chunks with SEMANTIC strategy, and overwrites the
output JSONL.

Pure local — no API calls.
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.connectors.otx import pulse_metadata, render_pulse_content
from rag_cti.preprocess.chunking import ChunkStrategy, chunk_document
from rag_cti.preprocess.normalizers import validate_content
from rag_cti.preprocess.seeding import chunk_to_jsonl_dict
from rag_cti.types import Document

RAW_DIR = Path("data/raw/otx")
DEFAULT_OUT = Path("data/processed/otx.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild otx.jsonl from data/raw/otx/*.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSONL path")
    args = parser.parse_args()

    if not RAW_DIR.exists():
        print(f"ERROR: Raw directory not found: {RAW_DIR}", file=sys.stderr)
        sys.exit(1)

    raw_files = sorted(RAW_DIR.glob("*.json"))
    print(f"Found {len(raw_files)} raw JSON files")

    if not raw_files:
        print("Nothing to rebuild.")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)

    doc_count = 0
    chunk_count = 0
    skipped = 0

    with args.out.open("w", encoding="utf-8") as fh:
        for raw_path in raw_files:
            try:
                raw = json.loads(raw_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  WARN: skipping {raw_path.name}: {exc}")
                skipped += 1
                continue

            pulse_id = raw.get("id", raw_path.stem)
            content = render_pulse_content(raw)

            try:
                validated = validate_content(content, "otx", pulse_id)
            except ValueError:
                skipped += 1
                continue

            doc_id = hashlib.sha256(f"otx:{pulse_id}".encode()).hexdigest()[:16]
            doc = Document(
                id=doc_id,
                source="otx",
                content=validated,
                metadata=pulse_metadata(raw),
            )

            for chunk in chunk_document(doc, strategy=ChunkStrategy.SEMANTIC):
                fh.write(json.dumps(chunk_to_jsonl_dict(chunk)) + "\n")
                chunk_count += 1
            doc_count += 1

            if doc_count % 200 == 0:
                print(f"  Progress: {doc_count} docs, {chunk_count} chunks")

    print(f"\nDone. {doc_count} docs -> {chunk_count} chunks written to {args.out}")
    if skipped:
        print(f"  Skipped: {skipped}")


if __name__ == "__main__":
    main()
