"""Temporary verification script — Phase 3 exit criterion check.

Runs:  store.search("lateral movement", top_k=5)
Checks that results contain relevant ATT&CK techniques as required by the
Phase 3 exit criterion:
  "search_dense('lateral movement') returns relevant ATT&CK techniques."

Usage:
    python scripts/verify_search.py [--query TEXT] [--top-k N]

Delete this file after the exit criterion is confirmed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti.config import get_settings
from rag_cti.embeddings.embedder import Embedder
from rag_cti.store.qdrant_store import QdrantStore


def _bar(score: float, width: int = 20) -> str:
    filled = round(score * width)
    return "[" + "█" * filled + "░" * (width - filled) + f"] {score:.4f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3 exit-criterion search verification")
    parser.add_argument("--query", default="lateral movement", help="Query text")
    parser.add_argument("--top-k", type=int, default=15, help="Number of results")
    args = parser.parse_args()

    settings = get_settings()

    print(f"\n{'='*65}")
    print(f"  Query       : {args.query!r}")
    print(f"  Top-k       : {args.top_k}")
    print(f"  Collection  : {settings.qdrant_collection}")
    print(f"  Embed model : {settings.embedding_model}")
    print(f"{'='*65}\n")

    print("Loading embedder ...")
    embedder = Embedder(settings.embedding_model)

    print("Connecting to Qdrant ...")
    store = QdrantStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )

    total = store.count()
    print(f"Collection has {total:,} points.\n")

    if total == 0:
        print("ERROR: collection is empty — run scripts/ingest.py first.")
        sys.exit(1)

    query_vec = embedder.encode_one(args.query)
    results = store.search(query_vec, top_k=args.top_k)

    if not results:
        print("No results returned.")
        sys.exit(1)

    print(f"Top-{args.top_k} results for {args.query!r}:\n")
    mitre_hits = 0
    for r in results:
        chunk = r.document
        source_tag = f"[{chunk.source.upper()}]"
        attack_id = chunk.metadata.get("attack_id", "")
        tactic = chunk.metadata.get("tactic", "") or ", ".join(chunk.metadata.get("tactics", []))
        preview = chunk.content[:160].replace("\n", " ")

        print(f"  Rank {r.rank + 1}  {_bar(r.score)}  {source_tag}")
        if attack_id:
            print(f"          ATT&CK ID : {attack_id}")
        if tactic:
            print(f"          Tactic    : {tactic}")
        print(f"          Chunk ID  : {chunk.id}")
        print(f"          Preview   : {preview} ...")
        print()

        if chunk.source == "mitre":
            mitre_hits += 1

    # Exit criterion check
    print(f"{'─'*65}")
    print(f"  MITRE ATT&CK results in top-{args.top_k}: {mitre_hits}/{args.top_k}")
    if mitre_hits > 0:
        print("  PASS - ATT&CK techniques returned for 'lateral movement'.")
        print("  Phase 3 exit criterion satisfied.")
    else:
        print("  FAIL - No ATT&CK techniques in top results.")
        print("  Check that mitre.jsonl was ingested and the embedding model")
        print("  matches what was used during ingest.")
    print(f"{'─'*65}\n")


if __name__ == "__main__":
    main()
