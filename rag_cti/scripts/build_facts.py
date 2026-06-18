"""M3 — build the global Fact table + supports edges from the chunk corpus.

Aggregates every chunk's ``metadata.relations[]`` (the projection-bearing corpus,
NOT resolved_relations.jsonl) into ``facts.jsonl`` + ``supports.jsonl``. One Fact per
distinct (subject, predicate, object) triple; one supports row per asserting chunk
(= Evidence). Deterministic + idempotent: re-running on the same corpus is byte-identical.

  python scripts/build_facts.py --processed-dir data/processed/v5_staging
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.preprocess.facts import build_facts

_DEFAULT_PROCESSED_DIR = Path("data/processed/v5_staging")


def _load_chunks(processed_dir: Path) -> list[dict]:
    """Read every *.jsonl chunk, keeping only the fields the aggregator needs."""
    chunks: list[dict] = []
    for path in sorted(processed_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                chunks.append(
                    {
                        "id": rec.get("id"),
                        "source": rec.get("source"),
                        "metadata": rec.get("metadata") or {},
                    }
                )
    return chunks


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Fact table + supports from the chunk corpus"
    )
    parser.add_argument("--processed-dir", type=Path, default=_DEFAULT_PROCESSED_DIR)
    parser.add_argument("--out-dir", type=Path, default=None, help="defaults to --processed-dir")
    args = parser.parse_args()

    if not args.processed_dir.exists():
        print(f"ERROR: not found: {args.processed_dir}", file=sys.stderr)
        sys.exit(1)
    out_dir = args.out_dir or args.processed_dir

    chunks = _load_chunks(args.processed_dir)
    raw_relations = sum(len(c["metadata"].get("relations") or []) for c in chunks)
    facts, supports = build_facts(chunks)

    _write_jsonl(out_dir / "facts.jsonl", [asdict(f) for f in facts])
    _write_jsonl(out_dir / "supports.jsonl", [asdict(s) for s in supports])

    # Net checks (correctness, not decoration).
    by_group = Counter(f.group for f in facts)
    cross_source = sum(1 for f in facts if len(f.distinct_origins) > 1)
    conflicts = sum(1 for f in facts if f.conflict)
    by_predicate = Counter(f.predicate for f in facts)
    print(f"✓ chunks read: {len(chunks)}  | raw relations: {raw_relations}")
    print(
        f"  facts: {len(facts)}  | supports: {len(supports)}  (aggregation: {raw_relations}→{len(facts)} facts)"
    )
    print(f"  group split: {dict(by_group)}")
    print(f"  predicate split: {dict(by_predicate.most_common())}")
    print(f"  cross-source facts (≥2 origins): {cross_source}  | conflicts flagged: {conflicts}")
    print(f"  -> {out_dir}/(facts|supports).jsonl")


if __name__ == "__main__":
    main()
