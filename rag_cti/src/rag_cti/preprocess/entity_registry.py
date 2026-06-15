"""Entity registry — mint stable entity_ids and resolve mentions to MITRE identity.

(knowledge-layer §3, construction-pipeline §3.) The gated core of M1:

- exact canonical name / exact alias -> reuse the MITRE-backed entity_id (certain)
- substring / fuzzy match -> a held **merge candidate**, never auto-applied (DECISION-1)
- no match -> an **orphan** entity, kept and flagged, never dropped (DECISION-2)

Every distinct mention yields exactly one Entity (nothing is dropped). Resolution
is scoped to the OntologyNode type matching the mention's entity type
(actor->group, family->software), so a cross-type fusion (the tool *Cobalt
Strike* vs the actor *Cobalt Group*) is structurally impossible, not merely
guarded. The OntologyNode mirror supplies the names/aliases resolved against —
which is why that loader mirrors group + software, not techniques alone.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any

# Entity.type (CONTEXT glossary) -> the OntologyNode.type it resolves against.
_ENTITY_TO_ONTOLOGY_TYPE: dict[str, str] = {
    "actor": "group",
    "family": "software",
    "technique": "technique",
}

_WHITESPACE = re.compile(r"\s+")


def _norm(text: str) -> str:
    """Normalize for matching: lowercased, trimmed, internal whitespace collapsed."""
    return _WHITESPACE.sub(" ", text.strip().lower())


def _orphan_entity_id(entity_type: str, name: str) -> str:
    """Deterministic id for an unresolved entity, keyed on (type, normalized name)."""
    digest = hashlib.sha256(f"{entity_type}:{_norm(name)}".encode()).hexdigest()[:16]
    return f"{entity_type}_orphan_{digest}"


def _resolved_entity_id(entity_type: str, ontology_id: str) -> str:
    """Stable id for a MITRE-backed entity (1:1 with its ontology_id)."""
    return f"{entity_type}_{ontology_id}"


def _resolve_exact(q: str, nodes: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    """Exact canonical-name then exact-alias match (both certain). None if neither."""
    for node in nodes:
        if _norm(node["name"]) == q:
            return node, "exact_name"
    for node in nodes:
        if any(q == _norm(alias) for alias in node.get("aliases", [])):
            return node, "exact_alias"
    return None, ""


def _substring_candidates(q: str, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nodes whose name or an alias contains the mention as a substring.

    Held for review per DECISION-1 — surfaced, never applied. Same-type only
    (the caller already scoped ``nodes`` to the mention's entity type).
    """
    out: list[dict[str, Any]] = []
    for node in nodes:
        names = [node["name"], *node.get("aliases", [])]
        if any(q in _norm(name) for name in names):
            out.append(node)
    return out


def build_entity_registry(
    mentions: Iterable[tuple[str, str]],
    ontology_nodes: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Resolve ``(name, entity_type)`` mentions into Entities + merge candidates.

    Returns ``{"entities": [...], "merge_candidates": [...]}``, both
    deterministically ordered by entity_id. Exact name/alias reuses the MITRE
    ontology_id; otherwise an orphan Entity (``ontology_id=None``), with any
    substring near-misses recorded as held merge candidates (never applied).
    """
    nodes_by_etype: dict[str, list[dict[str, Any]]] = {}
    for node in ontology_nodes:
        for etype, otype in _ENTITY_TO_ONTOLOGY_TYPE.items():
            if node["type"] == otype:
                nodes_by_etype.setdefault(etype, []).append(node)

    entities: dict[str, dict[str, Any]] = {}
    candidates: dict[tuple[str, str], dict[str, Any]] = {}

    for raw_name, etype in mentions:
        q = _norm(raw_name)
        if not q:
            continue
        nodes = nodes_by_etype.get(etype, [])
        matched, how = _resolve_exact(q, nodes)
        if matched is not None:
            eid = _resolved_entity_id(etype, matched["ontology_id"])
            entities.setdefault(
                eid,
                {
                    "entity_id": eid,
                    "type": etype,
                    "canonical_name": matched["name"],
                    "aliases": list(matched.get("aliases", [])),
                    "ontology_id": matched["ontology_id"],
                    "resolution": how,
                },
            )
            continue

        eid = _orphan_entity_id(etype, raw_name)
        entities.setdefault(
            eid,
            {
                "entity_id": eid,
                "type": etype,
                "canonical_name": raw_name,
                "aliases": [],
                "ontology_id": None,
                "resolution": "orphan",
            },
        )
        for cand in _substring_candidates(q, nodes):
            candidates.setdefault(
                (eid, cand["ontology_id"]),
                {
                    "entity_id": eid,
                    "candidate_ontology_id": cand["ontology_id"],
                    "candidate_name": cand["name"],
                    "how": "substring",
                },
            )

    return {
        "entities": [entities[k] for k in sorted(entities)],
        "merge_candidates": [candidates[k] for k in sorted(candidates)],
    }
