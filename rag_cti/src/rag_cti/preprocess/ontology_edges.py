"""Ontology edges — axiomatic definitional edges from the MITRE STIX bundle.

Two edge kinds, both straight from ATT&CK structure with zero inference
(knowledge-layer §4): ``subtechnique-of`` (T####.### → T####) and
``belongs-to-tactic`` (technique → TA#### via kill-chain phases). These are
definitional, carry **no confidence and no supports**, and are reloaded wholesale
on an ATT&CK version bump. They are decidedly *not* fact edges.

This is the part of M1's ontology layer that is ungated by DECISION-1/2 (those
gate entity *resolution*, not axiomatic edges), so it is produced during M0.
"""

from __future__ import annotations

from typing import Any


def _attack_id(obj: dict[str, Any]) -> str:
    """The ATT&CK external id (T####, TA####, …) of a STIX object, or ""."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return str(ref.get("external_id", ""))
    return ""


def ontology_edges_from_bundle(bundle: dict[str, Any]) -> list[dict[str, str]]:
    """Extract deduplicated, deterministically-ordered ontology edges.

    Revoked objects/relationships are excluded. Output rows look like
    ``{"child": "T1003.002", "parent": "T1003", "edge": "subtechnique-of"}``.
    """
    objects = bundle.get("objects", [])
    index = {o["id"]: o for o in objects if "id" in o}

    tactic_by_shortname: dict[str, str] = {
        o["x_mitre_shortname"]: _attack_id(o)
        for o in objects
        if o.get("type") == "x-mitre-tactic"
        and o.get("x_mitre_shortname")
        and not o.get("revoked", False)
    }

    edges: set[tuple[str, str, str]] = set()
    for o in objects:
        if o.get("revoked", False):
            continue
        otype = o.get("type")
        if otype == "relationship" and o.get("relationship_type") == "subtechnique-of":
            src = index.get(o.get("source_ref", ""))
            tgt = index.get(o.get("target_ref", ""))
            if src is None or tgt is None:
                continue
            child, parent = _attack_id(src), _attack_id(tgt)
            if child and parent:
                edges.add((child, parent, "subtechnique-of"))
        elif otype == "attack-pattern":
            child = _attack_id(o)
            if not child:
                continue
            for kc in o.get("kill_chain_phases", []):
                if kc.get("kill_chain_name") == "mitre-attack":
                    tactic_id = tactic_by_shortname.get(kc.get("phase_name", ""))
                    if tactic_id:
                        edges.add((child, tactic_id, "belongs-to-tactic"))

    return [{"child": c, "parent": p, "edge": e} for c, p, e in sorted(edges)]
