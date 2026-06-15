"""Build the Entity registry + back-fill OTX relations to entity_id triples.

The M1 resolution pass over OTX (the weakly-labeled source — where entity
resolution actually bites; MITRE names are canonical and resolve trivially).
Reads the MITRE STIX bundle (-> OntologyNodes) and data/processed/otx.jsonl, then:

  1. resolves every OTX entity mention (adversary->actor, malware_families->family,
     attack_ids->technique, targeted_countries->location) into Entities, and
  2. back-fills the structural relations (adversary uses attack_id; adversary
     targets country) into {subject_id, predicate, object_id} triples.

Writes:
  data/processed/entity_registry.jsonl          one row per Entity (resolved/orphan)
  data/processed/entity_merge_candidates.jsonl  held substring near-misses (DECISION-1)
  data/processed/resolved_relations.jsonl       entity_id triples (the M2 bridge)

Exact name/alias (or attack-id) -> reuse the MITRE entity; everything else ->
orphan, kept (DECISION-2). Splits are derived from the data, never hardcoded.
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.ingest.normalize import RelationMention
from rag_cti.preprocess.entity_registry import build_entity_registry, resolve_relations
from rag_cti.preprocess.ontology_nodes import ontology_nodes_from_bundle

_DEFAULT_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
_DEFAULT_OTX = Path("data/processed/otx.jsonl")
_OUT_DIR = Path("data/processed")


def _collect_otx(otx_path: Path) -> tuple[list[tuple[str, str]], list[RelationMention]]:
    """Distinct entity mentions + relation mentions from OTX pulses (deduped by pulse)."""
    seen_pulses: set[str] = set()
    entities: list[tuple[str, str]] = []
    relations: set[tuple[str, str, str, str, str]] = set()
    with otx_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            md = json.loads(line).get("metadata", {})
            pulse_id = md.get("pulse_id")
            if pulse_id in seen_pulses:
                continue
            seen_pulses.add(pulse_id)

            adversary = (md.get("adversary") or "").strip()
            attack_ids = [a for a in md.get("attack_ids", []) if a]
            families = [f for f in md.get("malware_families", []) if f]
            countries = [c for c in md.get("targeted_countries", []) if c]

            if adversary:
                entities.append((adversary, "actor"))
            entities += [(f, "family") for f in families]
            entities += [(a, "technique") for a in attack_ids]
            entities += [(c, "location") for c in countries]

            if adversary:
                for a in attack_ids:
                    relations.add((adversary, "uses", a, "actor", "technique"))
                for c in countries:
                    relations.add((adversary, "targets", c, "actor", "location"))

    rel_mentions = [RelationMention(*t) for t in sorted(relations)]
    return entities, rel_mentions


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Entity registry + resolved relations")
    parser.add_argument("--bundle", type=Path, default=_DEFAULT_BUNDLE)
    parser.add_argument("--otx", type=Path, default=_DEFAULT_OTX)
    parser.add_argument("--out-dir", type=Path, default=_OUT_DIR)
    args = parser.parse_args()

    for required in (args.bundle, args.otx):
        if not required.exists():
            print(f"ERROR: not found: {required}", file=sys.stderr)
            sys.exit(1)

    with args.bundle.open(encoding="utf-8") as fh:
        nodes = ontology_nodes_from_bundle(json.load(fh))

    entity_mentions, relation_mentions = _collect_otx(args.otx)
    registry = build_entity_registry(entity_mentions, nodes)
    # distinct triples, deterministically ordered by (subject_id, predicate, object_id)
    by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for t in resolve_relations(relation_mentions, nodes):
        by_key[(t["subject_id"], t["predicate"], t["object_id"])] = t
    triples = [by_key[k] for k in sorted(by_key)]

    _write_jsonl(args.out_dir / "entity_registry.jsonl", registry["entities"])
    _write_jsonl(args.out_dir / "entity_merge_candidates.jsonl", registry["merge_candidates"])
    _write_jsonl(args.out_dir / "resolved_relations.jsonl", triples)

    by_type = Counter(
        (e["type"], "resolved" if e["ontology_id"] else "orphan") for e in registry["entities"]
    )
    orphan_endpoints = sum(
        1 for t in triples if "orphan" in t["subject_id"] or "orphan" in t["object_id"]
    )
    print(f"✓ entities: {len(registry['entities'])}  (split: {dict(by_type)})")
    print(f"  held merge-candidates: {len(registry['merge_candidates'])}  (DECISION-1)")
    print(
        f"  resolved relations: {len(triples)}  ({orphan_endpoints} with an orphan endpoint, kept)"
    )
    print(f"  -> {args.out_dir}/(entity_registry|entity_merge_candidates|resolved_relations).jsonl")


if __name__ == "__main__":
    main()
