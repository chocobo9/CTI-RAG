"""Generate docs/vocab_relations.md — the data-grounded controlled-vocabulary listing.

Reads the M3 ``facts.jsonl`` and writes a grouped Markdown table of every relation
pattern that occurs, with source origins, Fact counts, and a readable example.
Examples are de-hashed via the M1 name sources (entity registry / indicator index /
ontology nodes); ids with no name source fall back to the id. Validates that no
un-sanctioned predicate slipped in (raises via summarize_vocab).

  python scripts/build_vocab_relations.py \
      --facts data/processed/v5_staging/facts.jsonl --registry-dir data/processed
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.preprocess.ontology_nodes import ontology_nodes_from_bundle
from rag_cti.preprocess.vocab_relations import render_markdown, summarize_vocab

_DEFAULT_FACTS = Path("data/processed/v5_staging/facts.jsonl")
_DEFAULT_REGISTRY_DIR = Path("data/processed")
_DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
_DEFAULT_OUT = Path("docs/vocab_relations.md")

# OntologyNode.type → entity_id prefix, to reconstruct a resolved entity_id and map
# it to the node name (covers MITRE objects not present in the OTX entity registry).
_NODE_TYPE_TO_ENTITY: dict[str, str] = {
    "group": "actor",
    "software": "family",
    "technique": "technique",
    "mitigation": "mitigation",
    "detection-strategy": "detection-strategy",
    "campaign": "campaign",
}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _ontology_nodes(bundle: Path, registry_dir: Path) -> list[dict]:
    """All MITRE ontology nodes — from the authoritative bundle (current code mirrors
    all 7 types incl. campaign/mitigation/detection-strategy), or the processed
    snapshot as a fallback when the bundle is absent."""
    if bundle.exists():
        with bundle.open(encoding="utf-8") as fh:
            nodes: list[dict] = ontology_nodes_from_bundle(json.load(fh))
        return nodes
    return _read_jsonl(registry_dir / "ontology_nodes.jsonl")


def _load_names(registry_dir: Path, bundle: Path) -> dict[str, str]:
    """entity_id → readable name, merged from all M1 name sources (best-effort)."""
    names: dict[str, str] = {}
    # ontology nodes: authoritative MITRE names, reconstructed by entity prefix.
    for node in _ontology_nodes(bundle, registry_dir):
        prefix = _NODE_TYPE_TO_ENTITY.get(node.get("type", ""))
        if prefix and node.get("ontology_id") and node.get("name"):
            names[f"{prefix}_{node['ontology_id']}"] = node["name"]
    # entity registry: canonical names incl. orphans (locations, untracked actors).
    for row in _read_jsonl(registry_dir / "entity_registry.jsonl"):
        if row.get("entity_id") and row.get("canonical_name"):
            names[row["entity_id"]] = row["canonical_name"]
    # indicator index: the indicator value is its readable form.
    for row in _read_jsonl(registry_dir / "indicator_index.jsonl"):
        if row.get("entity_id") and row.get("value"):
            names[row["entity_id"]] = row["value"]
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the controlled-vocabulary listing")
    parser.add_argument("--facts", type=Path, default=_DEFAULT_FACTS)
    parser.add_argument("--registry-dir", type=Path, default=_DEFAULT_REGISTRY_DIR)
    parser.add_argument("--bundle", type=Path, default=_DEFAULT_BUNDLE)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    if not args.facts.exists():
        print(f"ERROR: not found: {args.facts} (run build_facts.py first)", file=sys.stderr)
        sys.exit(1)

    facts = _read_jsonl(args.facts)
    names = _load_names(args.registry_dir, args.bundle)
    rows = summarize_vocab(facts, names)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_markdown(rows), encoding="utf-8")

    resolved = sum(
        1 for r in rows if r.example_subject_name is not None and r.example_object_name is not None
    )
    print(
        f"✓ {len(rows)} relation patterns ({resolved} with both example endpoints named), "
        f"{sum(r.fact_count for r in rows)} facts | names loaded: {len(names)} -> {args.out}"
    )
    for row in rows:
        subj = row.example_subject_name or row.example_subject
        obj = row.example_object_name or row.example_object
        print(
            f"  {row.group:9} {row.predicate:16} {row.subject_type} -> {row.object_type:18} "
            f"[{', '.join(row.origins)}]  ({row.fact_count})  e.g. {subj} -> {obj}"
        )


if __name__ == "__main__":
    main()
