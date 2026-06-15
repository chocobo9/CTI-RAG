"""Build the OntologyNode artifact from the MITRE STIX bundle.

Reads data/raw/mitre/enterprise-attack.json and writes the authoritative node
mirror (technique / sub-technique / tactic / software / group) to
data/processed/ontology_nodes.jsonl. Pure local — no API calls, no inference
(MITRE structure is authoritative). Companion to build_ontology_edges.py.
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.preprocess.ontology_nodes import ontology_nodes_from_bundle

_DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
_DEFAULT_OUT = Path("data/processed/ontology_nodes.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build OntologyNodes from MITRE STIX bundle")
    parser.add_argument("--bundle", type=Path, default=_DEFAULT_BUNDLE)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    if not args.bundle.exists():
        print(f"ERROR: bundle not found: {args.bundle}", file=sys.stderr)
        sys.exit(1)

    with args.bundle.open(encoding="utf-8") as fh:
        bundle = json.load(fh)

    nodes = ontology_nodes_from_bundle(bundle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for node in nodes:
            fh.write(json.dumps(node) + "\n")

    by_type = Counter(n["type"] for n in nodes)
    version = nodes[0]["attack_version"] if nodes else "?"
    print(f"✓ {len(nodes)} ontology nodes (ATT&CK {version}) -> {args.out}  {dict(by_type)}")


if __name__ == "__main__":
    main()
