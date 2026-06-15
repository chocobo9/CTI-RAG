"""Build the actor Entity registry by resolving OTX adversaries against MITRE.

Reads the MITRE STIX bundle (-> OntologyNodes) and the distinct
``metadata.adversary`` strings in data/processed/otx.jsonl, then resolves each as
an ``actor`` mention against MITRE intrusion-set (group) nodes. Writes:

  data/processed/entity_registry.jsonl          one row per resolved/orphan Entity
  data/processed/entity_merge_candidates.jsonl  held substring near-misses (DECISION-1)

Exact name/alias -> reuse the G#### entity; everything else -> orphan, kept
(DECISION-2). The exact/orphan split is *derived* from the data, never hardcoded.
Family/tool resolution (metadata.malware_families vs software nodes) is the next
sub-step; this script is the M1 "done-when" actor pass.
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.preprocess.entity_registry import build_entity_registry
from rag_cti.preprocess.ontology_nodes import ontology_nodes_from_bundle

_DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
_DEFAULT_OTX = Path("data/processed/otx.jsonl")
_DEFAULT_OUT = Path("data/processed/entity_registry.jsonl")
_DEFAULT_CANDIDATES = Path("data/processed/entity_merge_candidates.jsonl")


def _distinct_adversaries(otx_path: Path) -> list[str]:
    seen: set[str] = set()
    order: list[str] = []
    with otx_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            adv = json.loads(line).get("metadata", {}).get("adversary")
            if adv and adv not in seen:
                seen.add(adv)
                order.append(adv)
    return order


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build actor Entity registry from OTX + MITRE")
    parser.add_argument("--bundle", type=Path, default=_DEFAULT_BUNDLE)
    parser.add_argument("--otx", type=Path, default=_DEFAULT_OTX)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--candidates", type=Path, default=_DEFAULT_CANDIDATES)
    args = parser.parse_args()

    for required in (args.bundle, args.otx):
        if not required.exists():
            print(f"ERROR: not found: {required}", file=sys.stderr)
            sys.exit(1)

    with args.bundle.open(encoding="utf-8") as fh:
        nodes = ontology_nodes_from_bundle(json.load(fh))

    adversaries = _distinct_adversaries(args.otx)
    result = build_entity_registry([(adv, "actor") for adv in adversaries], nodes)

    _write_jsonl(args.out, result["entities"])
    _write_jsonl(args.candidates, result["merge_candidates"])

    by_res = Counter(e["resolution"] for e in result["entities"])
    resolved = sum(v for k, v in by_res.items() if k != "orphan")
    orphans = by_res.get("orphan", 0)
    print(
        f"✓ {len(adversaries)} distinct OTX adversaries -> "
        f"{len(result['entities'])} entities "
        f"({resolved} resolved, {orphans} orphan) "
        f"+ {len(result['merge_candidates'])} held merge-candidates"
    )
    print(f"  resolution split: {dict(by_res)}")
    print(f"  -> {args.out}  +  {args.candidates}")


if __name__ == "__main__":
    main()
