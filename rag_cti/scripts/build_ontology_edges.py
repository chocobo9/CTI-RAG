"""Build the ontology-edges artifact from the MITRE STIX bundle.

Reads data/raw/mitre/enterprise-attack.json and writes axiomatic ontology edges
(subtechnique-of, belongs-to-tactic) to data/processed/ontology_edges.jsonl.
Pure local — no API calls, no inference (MITRE structure is authoritative).
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.preprocess.ontology_edges import ontology_edges_from_bundle

_DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
_DEFAULT_OUT = Path("data/processed/ontology_edges.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ontology edges from MITRE STIX bundle")
    parser.add_argument("--bundle", type=Path, default=_DEFAULT_BUNDLE)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    if not args.bundle.exists():
        print(f"ERROR: bundle not found: {args.bundle}", file=sys.stderr)
        sys.exit(1)

    with args.bundle.open(encoding="utf-8") as fh:
        bundle = json.load(fh)

    edges = ontology_edges_from_bundle(bundle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for edge in edges:
            fh.write(json.dumps(edge) + "\n")

    by_kind: dict[str, int] = {}
    for edge in edges:
        by_kind[edge["edge"]] = by_kind.get(edge["edge"], 0) + 1
    print(f"✓ {len(edges)} ontology edges -> {args.out}  {by_kind}")


if __name__ == "__main__":
    main()
