"""Rebuild data/processed/otx.jsonl from the versioned RawStore.

Reads each OTX pulse's latest raw version from the RawStore, renders it with the
canonical connector mapping (render_pulse_content / pulse_metadata — adversary,
malware_families, targeted_countries, references included), chunks with the
SEMANTIC strategy, and writes the output JSONL.

Deterministic: chunk ``retrieved_at`` is taken from the raw version's
``fetched_at`` (not wall-clock), so re-running reproduces byte-identical output.
Pure local — no API calls. Run scripts/migrate_raw_store.py first to populate the
versioned store.
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.connectors.otx import pulse_metadata, render_pulse_content
from rag_cti.connectors.otx_raw_views import (
    indicator_page_source_index,
    latest_indicator_pages,
    pulse_with_full_indicators,
)
from rag_cti.ingest.normalize import normalize_otx_pulse
from rag_cti.preprocess.chunk_projection import project_chunk
from rag_cti.preprocess.chunking import ChunkStrategy, chunk_document
from rag_cti.preprocess.normalizers import validate_content
from rag_cti.preprocess.ontology_nodes import ontology_nodes_from_bundle
from rag_cti.preprocess.seeding import chunk_to_jsonl_dict
from rag_cti.store.raw_store import RawStore
from rag_cti.types import Document

DEFAULT_OUT = Path("data/processed/otx.jsonl")
DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild otx.jsonl from the versioned RawStore")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSONL path")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    args = parser.parse_args()

    # M2.6: ontology nodes for projecting adversary/family/technique mentions into
    # the chunk payload (entity_ids / relations / attack_ids).
    with args.bundle.open(encoding="utf-8") as fh:
        nodes = ontology_nodes_from_bundle(json.load(fh))

    store = RawStore(args.raw_root)
    source_ids = store.source_ids("otx")
    page_index = indicator_page_source_index(store)
    print(f"Found {len(source_ids)} OTX raw records in versioned store")
    if not source_ids:
        print("Nothing to rebuild (run scripts/migrate_raw_store.py first).")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    doc_count = chunk_count = skipped = 0

    with args.out.open("w", encoding="utf-8") as fh:
        for pulse_id in source_ids:
            versions = store.versions("otx", pulse_id)
            if not versions:
                skipped += 1
                continue
            fetched_at = versions[-1]
            raw = store.read("otx", pulse_id, fetched_at)
            raw = pulse_with_full_indicators(
                raw,
                latest_indicator_pages(store, pulse_id, page_index),
            )

            content = render_pulse_content(raw)
            try:
                validated = validate_content(content, "otx", pulse_id)
            except ValueError:
                skipped += 1
                continue

            doc_id = hashlib.sha256(f"otx:{pulse_id}".encode()).hexdigest()[:16]
            projection = project_chunk(normalize_otx_pulse(raw), nodes)
            doc = Document(
                id=doc_id,
                source="otx",
                content=validated,
                metadata={**pulse_metadata(raw), **projection},
                retrieved_at=datetime.fromisoformat(fetched_at),
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
