#!/usr/bin/env python3
"""Deterministically build COMPOUND-query gold from the project's ATT&CK bundle.

A compound query asks about MULTIPLE actors at once. Its gold is a set operation over
each actor's FULL technique set (direct + via_software, NO tactic filter), computed by
the SAME deterministic STIX traversal as relationship_direct gold (reuses ``AttackGraph``
from ``rebuild_relationship_gold``):
  - op="union":        compare / profile  -> union of the actors' technique sets
  - op="intersection": "shared between"   -> intersection

NO LLM. NO hand-written gold. NO guessing. Writes data/eval/query_set_compound.jsonl,
which the supervised-vs-single-shot eval (eval_agentic.py --supervised) scores against.

Run:  python3 scripts/build_compound_gold.py
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before sibling import - run-without-install pattern)
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # sibling rebuild_relationship_gold import

from rebuild_relationship_gold import (
    AttackGraph,
    attack_pattern_external_id,
    base_technique,
    is_active,
)

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "data" / "raw" / "mitre" / "enterprise-attack.json"
OUT_PATH = ROOT / "data" / "eval" / "query_set_compound.jsonl"
_TID_RE = re.compile(r"^T\d{4}(\.\d{3})?$", re.IGNORECASE)

# Compound specs over actors CONFIRMED resolvable in relationship_direct gold (so the
# corpus actually holds their techniques — a fair retrieval target). union = compare /
# profile; intersection = "shared between".
SPECS = [
    {
        "id": "C001",
        "op": "union",
        "actors": ["APT29", "Turla"],
        "query": "Compare the TTPs used by APT29 and Turla.",
    },
    {
        "id": "C002",
        "op": "union",
        "actors": ["Lazarus", "Kimsuky"],
        "query": "Compare the techniques used by the Lazarus Group and Kimsuky.",
    },
    {
        "id": "C003",
        "op": "union",
        "actors": ["APT1", "OilRig"],
        "query": "Compare the TTPs of APT1 and OilRig.",
    },
    {
        "id": "C004",
        "op": "union",
        "actors": ["APT29", "Turla", "OilRig"],
        "query": "Profile and compare the techniques of APT29, Turla, and OilRig.",
    },
    {
        "id": "C005",
        "op": "union",
        "actors": ["Kimsuky", "OilRig"],
        "query": "Compare the techniques of Kimsuky and OilRig.",
    },
    {
        "id": "C006",
        "op": "intersection",
        "actors": ["Lazarus", "APT38"],
        "query": "Which techniques are shared between the Lazarus Group and APT38?",
    },
    {
        "id": "C007",
        "op": "intersection",
        "actors": ["APT29", "Turla"],
        "query": "Which techniques do both APT29 and Turla use?",
    },
    {
        "id": "C008",
        "op": "intersection",
        "actors": ["Kimsuky", "Lazarus"],
        "query": "What techniques are common to both Kimsuky and the Lazarus Group?",
    },
]


def _normalise(graph: AttackGraph, ap_ids: set[str]) -> set[str]:
    techs: set[str] = set()
    for ap_id in ap_ids:
        ap = graph.by_id.get(ap_id)
        if not ap or not is_active(ap):
            continue
        ext = attack_pattern_external_id(ap)
        if ext and _TID_RE.match(ext):
            techs.add(base_technique(ext))
    return techs


def direct_techniques(graph: AttackGraph, is_obj: dict) -> set[str]:
    """An actor's DIRECT base-technique set: intrusion-set --uses--> attack-pattern,
    active only, NO tactic filter. Direct-only (NOT the via-software 2-hop) so the gold
    matches what ``graph_query(actor, uses, technique)`` can actually enumerate — a fair
    target. The via-software footprint is reported in provenance for audit, not scored."""
    is_id = is_obj["id"]
    direct = {
        tgt
        for tgt in graph.uses.get(is_id, [])
        if graph.by_id.get(tgt, {}).get("type") == "attack-pattern"
    }
    return _normalise(graph, direct)


def via_software_count(graph: AttackGraph, is_obj: dict) -> int:
    """Count of EXTRA base techniques reachable only via the actor's software (audit)."""
    is_id = is_obj["id"]
    via: set[str] = set()
    for tgt in graph.uses.get(is_id, []):
        if graph.by_id.get(tgt, {}).get("type") in ("malware", "tool"):
            via |= {
                t
                for t in graph.uses.get(tgt, [])
                if graph.by_id.get(t, {}).get("type") == "attack-pattern"
            }
    return len(_normalise(graph, via) - direct_techniques(graph, is_obj))


def main() -> int:
    if not BUNDLE_PATH.exists():
        print(f"FATAL: bundle not found at {BUNDLE_PATH}", file=sys.stderr)
        return 2
    graph = AttackGraph(BUNDLE_PATH)
    print(f"BUNDLE: {graph.spec_label}")

    out_rows: list[dict] = []
    for spec in SPECS:
        per_actor: dict[str, list[str]] = {}
        matched: dict[str, dict] = {}
        ok = True
        for actor in spec["actors"]:
            is_obj, how = graph.match_intrusion_set(actor)
            if is_obj is None:
                print(f"  {spec['id']}: SKIP actor unmatched {actor!r} ({how})", file=sys.stderr)
                ok = False
                break
            per_actor[actor] = sorted(direct_techniques(graph, is_obj))
            matched[actor] = {
                "name": is_obj.get("name"),
                "stix_id": is_obj["id"],
                "mode": how,
                "via_software_extra_n": via_software_count(graph, is_obj),
            }
        if not ok:
            continue
        sets = [set(per_actor[a]) for a in spec["actors"]]
        gold = set().union(*sets) if spec["op"] == "union" else set(sets[0]).intersection(*sets[1:])
        gold_sorted = sorted(gold)
        out_rows.append(
            {
                "query_id": spec["id"],
                "query": spec["query"],
                "category": "compound",
                "gold_attack_ids": gold_sorted,
                "gold_sources": ["mitre"],
                "gold_actor": None,
                "gold_pulse_id": None,
                "gold_malware": None,
                "gold_op": spec["op"],
                "gold_actors": spec["actors"],
                "gold_branches": [
                    {"entity": a, "attack_ids": per_actor[a]} for a in spec["actors"]
                ],
                "notes": f"compound {spec['op']} over {', '.join(spec['actors'])}",
                "gold_provenance": {
                    "method": "attack_graph_traversal_multi_actor",
                    "paths": ["direct", "via_software"],
                    "tactic_filter": None,
                    "op": spec["op"],
                    "bundle": graph.spec_label,
                    "actors_matched": matched,
                    "per_actor_n": {a: len(per_actor[a]) for a in spec["actors"]},
                    "gold_n": len(gold_sorted),
                },
            }
        )
        print(
            f"  {spec['id']} {spec['op']:12} {' + '.join(spec['actors']):32} "
            f"per-actor={[len(per_actor[a]) for a in spec['actors']]} -> gold_n={len(gold_sorted)}"
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for r in out_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nARTIFACT: {OUT_PATH} ({len(out_rows)} compound rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
