"""Rebuild data/processed/otx.jsonl from raw JSON files.

Usage:
    python scripts/rebuild_otx_jsonl.py

Reads every data/raw/otx/{pulse_id}.json, applies the new field mapping
(adversary, malware_families, targeted_countries in content), chunks with
SEMANTIC strategy, and overwrites data/processed/otx.jsonl.

Pure local — no API calls.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.preprocess.chunking import ChunkStrategy, chunk_document
from rag_cti.preprocess.normalizers import validate_content
from rag_cti.types import Document

RAW_DIR = Path("data/raw/otx")
OUT_PATH = Path("data/processed/otx.jsonl")


def render_otx(raw: dict) -> str:
    parts = [raw.get("name", "")]

    desc = (raw.get("description") or "").strip()
    if desc:
        parts.append(desc)

    adversary = raw.get("adversary", "")
    if adversary:
        parts.append(f"Attributed to {adversary}.")

    families = raw.get("malware_families", [])
    if families:
        names = []
        for f in families:
            if isinstance(f, str):
                if f:
                    names.append(f)
            elif isinstance(f, dict):
                dn = f.get("display_name", "")
                if dn:
                    names.append(dn)
        if names:
            parts.append(f"Associated malware: {', '.join(names)}.")

    countries = raw.get("targeted_countries", [])
    if countries:
        parts.append(f"Targeted countries: {', '.join(countries)}.")

    indicators = [
        i.get("indicator", "")
        for i in raw.get("indicators", [])
        if i.get("indicator")
    ]
    if indicators:
        sample = indicators[:20]
        parts.append(f"Key indicators: {', '.join(sample)}.")

    return "\n\n".join(parts)


def build_metadata(raw: dict) -> dict:
    pulse_id = raw.get("id", "")
    indicators = [
        i.get("indicator", "")
        for i in raw.get("indicators", [])
        if i.get("indicator")
    ]
    return {
        "pulse_id": pulse_id,
        "name": raw.get("name", ""),
        "tags": raw.get("tags", []),
        "attack_ids": raw.get("attack_ids", []),
        "adversary": raw.get("adversary", ""),
        "malware_families": raw.get("malware_families", []),
        "targeted_countries": raw.get("targeted_countries", []),
        "references": raw.get("references", []),
        "indicators": indicators,
        "last_modified": raw.get("modified", ""),
        "pulse_source": raw.get("pulse_source", ""),
    }


def main() -> None:
    if not RAW_DIR.exists():
        print(f"ERROR: Raw directory not found: {RAW_DIR}", file=sys.stderr)
        sys.exit(1)

    raw_files = sorted(RAW_DIR.glob("*.json"))
    print(f"Found {len(raw_files)} raw JSON files")

    if not raw_files:
        print("Nothing to rebuild.")
        return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    doc_count = 0
    chunk_count = 0
    skipped = 0

    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for raw_path in raw_files:
            try:
                raw = json.loads(raw_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  WARN: skipping {raw_path.name}: {exc}")
                skipped += 1
                continue

            pulse_id = raw.get("id", raw_path.stem)
            content = render_otx(raw)

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
                metadata=build_metadata(raw),
            )

            chunks = chunk_document(doc, strategy=ChunkStrategy.SEMANTIC)
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

            if doc_count % 200 == 0:
                print(f"  Progress: {doc_count} docs, {chunk_count} chunks")

    print(f"\nDone. {doc_count} docs -> {chunk_count} chunks written to {OUT_PATH}")
    if skipped:
        print(f"  Skipped: {skipped}")


if __name__ == "__main__":
    main()
