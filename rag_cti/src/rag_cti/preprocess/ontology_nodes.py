"""OntologyNode definitions — the authoritative MITRE object mirror (knowledge-layer §3).

One node per mirrored ATT&CK object: technique / sub-technique / tactic /
software (malware|tool) / group (intrusion-set), each
``{ontology_id, type, name, aliases, tactics, attack_version}``. Definitional,
**no confidence and no supports**; reloaded wholesale on an ATT&CK version bump
(the version is the bundle's ``x-mitre-collection`` ``x_mitre_version``). Zero
inference — MITRE is authoritative.

This is the *node* half of M1's ontology layer; the *edge* half is
``ontology_edges``. Both are ungated by DECISION-1/2 (those gate entity
*resolution*). The Entity registry resolves aliases against the group/software
``aliases`` mirrored here — which is why software + group are mirrored, not
techniques alone (knowledge-layer §3).
"""

from __future__ import annotations

from typing import Any

# STIX object type -> OntologyNode type (knowledge-layer §3 enum). malware and
# tool both mirror to "software"; the sub/parent technique split is an edge, not
# a node type, so attack-pattern is always "technique". campaign is mirrored so a
# campaign mention (always a relationship subject; never an object — verified over
# the bundle) resolves to its C#### object by exact STIX-derived name, not orphan.
_TYPE_MAP: dict[str, str] = {
    "attack-pattern": "technique",
    "x-mitre-tactic": "tactic",
    "intrusion-set": "group",
    "malware": "software",
    "tool": "software",
    "campaign": "campaign",
}


def _attack_id(obj: dict[str, Any]) -> str:
    """The ATT&CK external id (T####, TA####, S####, G####, C####) of a STIX object, or ""."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return str(ref.get("external_id", ""))
    return ""


def _aliases(obj: dict[str, Any], name: str) -> list[str]:
    """Alternative names, canonical ``name`` excluded (it is stored separately).

    intrusion-set carries ``aliases``; malware/tool carry ``x_mitre_aliases``.
    Both lists include the canonical name as the first element. Missing -> [].
    """
    raw = obj.get("aliases") or obj.get("x_mitre_aliases") or []
    return [a for a in raw if a and a != name]


def _tactics(obj: dict[str, Any]) -> list[str]:
    """Tactic shortnames from a technique's ATT&CK kill-chain phases."""
    return [
        kc["phase_name"]
        for kc in obj.get("kill_chain_phases", [])
        if kc.get("kill_chain_name") == "mitre-attack"
    ]


def _attack_version(bundle: dict[str, Any]) -> str:
    """The ATT&CK release version — the x-mitre-collection's ``x_mitre_version``.

    This is the release the whole bundle belongs to (uniform across nodes), not a
    per-object ``x_mitre_version`` (which versions a single object).
    """
    for obj in bundle.get("objects", []):
        if obj.get("type") == "x-mitre-collection":
            return str(obj.get("x_mitre_version", ""))
    return ""


def ontology_nodes_from_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract deduplicated, deterministically-ordered OntologyNodes from a bundle.

    Revoked objects and objects without an ATT&CK external id are excluded. Output
    rows look like ``{"ontology_id": "T1003.002", "type": "technique", "name":
    "LSASS Memory", "aliases": [], "tactics": ["credential-access"],
    "attack_version": "18.1"}``, sorted by ``ontology_id``.
    """
    version = _attack_version(bundle)
    nodes: dict[str, dict[str, Any]] = {}
    for obj in bundle.get("objects", []):
        node_type = _TYPE_MAP.get(obj.get("type", ""))
        if node_type is None or obj.get("revoked", False):
            continue
        ontology_id = _attack_id(obj)
        if not ontology_id:
            continue
        name = str(obj.get("name", ""))
        nodes[ontology_id] = {
            "ontology_id": ontology_id,
            "type": node_type,
            "name": name,
            "aliases": _aliases(obj, name),
            "tactics": _tactics(obj) if node_type == "technique" else [],
            "attack_version": version,
        }
    return [nodes[k] for k in sorted(nodes)]
