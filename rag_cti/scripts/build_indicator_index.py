"""Build the standalone indicator index (indicators as entities) from raw OTX.

Reads each OTX source record's latest version from the versioned RawStore, types
every indicator (preserving the source type), and writes one entity-shaped record
per distinct indicator to data/processed/indicator_index.jsonl. Indicators live
here, not in the Qdrant payload (decision 2026-06: the vector store is never the
system of record, and a single pulse can carry ~20k indicators).

Pure local 鈥?no API calls. Requires the versioned RawStore to be populated
(see scripts/migrate_raw_store.py / the per-source raw fetchers).
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports 鈥?run-without-install pattern)
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.connectors.otx_raw_views import (
    indicator_page_source_index,
    latest_indicator_pages,
    pulse_with_full_indicators,
)
from rag_cti.preprocess.indicator_index import build_indicator_index
from rag_cti.preprocess.indicators import indicator_mentions
from rag_cti.store.raw_store import RawStore

_DEFAULT_OUT = Path("data/processed/indicator_index.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build indicator index from raw OTX")
    parser.add_argument("--source", default="otx", help="Raw source to index")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    store = RawStore(args.raw_root)
    page_index = indicator_page_source_index(store) if args.source == "otx" else {}

    def _pairs():
        for sid, payload in store.iter_latest(args.source):
            if args.source == "otx" and isinstance(payload, dict):
                payload = pulse_with_full_indicators(
                    payload,
                    latest_indicator_pages(store, sid, page_index),
                )
            inds = payload.get("indicators", []) if isinstance(payload, dict) else []
            yield sid, indicator_mentions(inds)

    records = build_indicator_index(_pairs())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"OK {len(records)} indicator entities -> {args.out}")


if __name__ == "__main__":
    main()

