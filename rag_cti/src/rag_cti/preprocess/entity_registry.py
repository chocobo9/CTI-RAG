"""Entity registry — mint stable entity_ids and resolve mentions to MITRE identity.

(knowledge-layer §3, construction-pipeline §3.) The gated core of M1:

- exact canonical name / exact alias -> reuse the MITRE-backed entity_id (certain)
- substring / fuzzy match -> a held **merge candidate**, never auto-applied (DECISION-1)
- no match -> an **orphan** entity, kept and flagged, never dropped (DECISION-2)

Resolution is scoped by entity type, so a cross-type fusion (the tool *Cobalt
Strike* vs the actor *Cobalt Group*) is structurally impossible, not merely
guarded:

- ``actor`` / ``family`` resolve by **name/alias** against group / software nodes.
- ``technique`` resolves by **attack id** (the mention *is* the ontology_id) —
  exact identity, ungated.
- ``campaign`` / ``location`` have no MITRE mirror, so they are always orphans.

Every distinct mention yields exactly one Entity (nothing dropped).
:func:`resolve_relations` reuses the same resolver to back-fill RelationMention
subject/object strings into entity_id triples — the bridge into M2.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from rag_cti.ingest.normalize import RelationMention

# Entity.type -> OntologyNode.type resolved by name/alias.
_NAME_RESOLVED: dict[str, str] = {"actor": "group", "family": "software"}
# Entity.type -> OntologyNode.type resolved by attack id (mention == ontology_id).
_ID_RESOLVED: dict[str, str] = {"technique": "technique"}

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class _Resolution:
    entity_id: str
    resolution: str  # exact_name | exact_alias | exact_id | orphan
    canonical_name: str
    aliases: tuple[str, ...]
    ontology_id: str | None
    candidates: tuple[dict[str, Any], ...]  # held merge candidates (DECISION-1)


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


def _build_indexes(
    ontology_nodes: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, dict[str, Any]]]]:
    """Bucket nodes for resolution: name-resolved lists and id-resolved maps."""
    name_nodes: dict[str, list[dict[str, Any]]] = {}
    oid_nodes: dict[str, dict[str, dict[str, Any]]] = {}
    for node in ontology_nodes:
        for etype, otype in _NAME_RESOLVED.items():
            if node["type"] == otype:
                name_nodes.setdefault(etype, []).append(node)
        for etype, otype in _ID_RESOLVED.items():
            if node["type"] == otype:
                oid_nodes.setdefault(etype, {})[node["ontology_id"]] = node
    return name_nodes, oid_nodes


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
    """Nodes whose name or an alias contains the mention (held per DECISION-1)."""
    out: list[dict[str, Any]] = []
    for node in nodes:
        names = [node["name"], *node.get("aliases", [])]
        if any(q in _norm(name) for name in names):
            out.append(node)
    return out


def _orphan(etype: str, name: str, candidates: tuple[dict[str, Any], ...] = ()) -> _Resolution:
    return _Resolution(_orphan_entity_id(etype, name), "orphan", name, (), None, candidates)


def _resolved(etype: str, node: dict[str, Any], how: str) -> _Resolution:
    return _Resolution(
        _resolved_entity_id(etype, node["ontology_id"]),
        how,
        str(node["name"]),
        tuple(node.get("aliases", [])),
        node["ontology_id"],
        (),
    )


def _resolve_one(
    name: str,
    etype: str,
    name_nodes: dict[str, list[dict[str, Any]]],
    oid_nodes: dict[str, dict[str, dict[str, Any]]],
) -> _Resolution:
    """Resolve one (name, entity_type) mention to a stable identity. See module doc."""
    if etype in _ID_RESOLVED:
        node = oid_nodes.get(etype, {}).get(name.strip())
        return _resolved(etype, node, "exact_id") if node is not None else _orphan(etype, name)

    if etype in _NAME_RESOLVED:
        nodes = name_nodes.get(etype, [])
        q = _norm(name)
        matched, how = _resolve_exact(q, nodes)
        if matched is not None:
            return _resolved(etype, matched, how)
        cands = tuple(
            {
                "candidate_ontology_id": n["ontology_id"],
                "candidate_name": n["name"],
                "how": "substring",
            }
            for n in _substring_candidates(q, nodes)
        )
        return _orphan(etype, name, cands)

    return _orphan(etype, name)  # campaign / location / indicator: no MITRE mirror


def build_entity_registry(
    mentions: Iterable[tuple[str, str]],
    ontology_nodes: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Resolve ``(name, entity_type)`` mentions into Entities + merge candidates.

    Returns ``{"entities": [...], "merge_candidates": [...]}``, both
    deterministically ordered by entity_id. One Entity per distinct mention;
    substring near-misses are recorded as held candidates (never applied).
    """
    name_nodes, oid_nodes = _build_indexes(ontology_nodes)
    entities: dict[str, dict[str, Any]] = {}
    candidates: dict[tuple[str, str], dict[str, Any]] = {}

    for raw_name, etype in mentions:
        if not _norm(raw_name):
            continue
        res = _resolve_one(raw_name, etype, name_nodes, oid_nodes)
        entities.setdefault(
            res.entity_id,
            {
                "entity_id": res.entity_id,
                "type": etype,
                "canonical_name": res.canonical_name,
                "aliases": list(res.aliases),
                "ontology_id": res.ontology_id,
                "resolution": res.resolution,
            },
        )
        for cand in res.candidates:
            candidates.setdefault(
                (res.entity_id, cand["candidate_ontology_id"]),
                {"entity_id": res.entity_id, **cand},
            )

    return {
        "entities": [entities[k] for k in sorted(entities)],
        "merge_candidates": [candidates[k] for k in sorted(candidates)],
    }


def resolve_relations(
    relation_mentions: Iterable[RelationMention],
    ontology_nodes: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Back-fill RelationMention subject/object strings into entity_id triples.

    Each ``RelationMention`` becomes ``{subject_id, predicate, object_id}`` with
    both endpoints resolved (orphans included — the edge survives with stable ids,
    never dropped, DECISION-2). This is what M2 writes into ``relations[]``.
    """
    name_nodes, oid_nodes = _build_indexes(ontology_nodes)
    out: list[dict[str, str]] = []
    for rel in relation_mentions:
        subject = _resolve_one(rel.subject, rel.subject_type, name_nodes, oid_nodes)
        obj = _resolve_one(rel.object, rel.object_type, name_nodes, oid_nodes)
        out.append(
            {
                "subject_id": subject.entity_id,
                "predicate": rel.predicate,
                "object_id": obj.entity_id,
            }
        )
    return out
