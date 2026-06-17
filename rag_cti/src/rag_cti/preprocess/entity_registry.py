"""Entity registry — mint stable entity_ids and resolve mentions to MITRE identity.

(knowledge-layer §3, construction-pipeline §3.) The gated core of M1:

- exact canonical name / exact alias -> reuse the MITRE-backed entity_id (certain)
- substring / fuzzy match -> a held **merge candidate**, never auto-applied (DECISION-1)
- no match -> an **orphan** entity, kept and flagged, never dropped (DECISION-2)

Resolution is scoped by entity type, so a cross-type fusion (the tool *Cobalt
Strike* vs the actor *Cobalt Group*) is structurally impossible, not merely
guarded:

- ``actor`` / ``family`` resolve by **name/alias** against group / software nodes;
  a ``family`` mention may also carry an embedded id (``"Mimikatz - S0002"``),
  resolved only when a name-back check confirms the id matches the named object.
- ``technique`` resolves by **attack id** (the mention *is* the ontology_id) —
  exact identity, ungated.
- ``campaign`` resolves by **name** against its mirrored C#### object (the mention
  name is read from that STIX object, so the match is exact). ``location`` has no
  MITRE mirror, so it is always an orphan.

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

# Entity.type -> OntologyNode.type resolved by name/alias. campaign resolves to its
# own C#### object (mirrored in the ontology); its mention name is read from the STIX
# object itself, so the match is exact and unambiguous — no fuzzy/normalization added.
_NAME_RESOLVED: dict[str, str] = {"actor": "group", "family": "software", "campaign": "campaign"}
# Entity.type -> OntologyNode.type resolved by attack id (mention == ontology_id).
# technique by T####; mitigation/detection-strategy by M####/DET#### — these MITRE
# objects have unique ids but COLLIDING names (≈29 detection-strategies share a
# name), so id resolution avoids ambiguous-name orphaning (the mention carries the id).
_ID_RESOLVED: dict[str, str] = {
    "technique": "technique",
    "mitigation": "mitigation",
    "detection-strategy": "detection-strategy",
}
# Every resolvable type, for building the ontology_id -> node lookup used by both the
# id path (technique) and the embedded-id name-back check (software/group/campaign).
_RESOLVED: dict[str, str] = {**_NAME_RESOLVED, **_ID_RESOLVED}

_WHITESPACE = re.compile(r"\s+")
# An author-typed name can carry the object's attack id, e.g. "Mimikatz - S0002".
_EMBEDDED_ATTACK_ID = re.compile(r"\b([SGT]\d{4})(?:\.\d{3})?\b")


@dataclass(frozen=True)
class _Resolution:
    entity_id: str
    resolution: str  # exact_name | exact_alias | exact_id | embedded_id | orphan
    canonical_name: str
    aliases: tuple[str, ...]
    ontology_id: str | None
    candidates: tuple[dict[str, Any], ...]  # held merge candidates (DECISION-1)


def _norm(text: str) -> str:
    """Normalize for matching: lowercased, trimmed, internal whitespace collapsed."""
    return _WHITESPACE.sub(" ", text.strip().lower())


def _loose(text: str) -> str:
    """Lowercase, drop every non-alphanumeric char. Used ONLY for the embedded-id
    name-back check (so 'Cobalt Strike' agrees with 'CobaltStrike'); never a
    resolution path of its own."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _orphan_entity_id(entity_type: str, name: str) -> str:
    """Deterministic id for an unresolved entity, keyed on (type, normalized name)."""
    digest = hashlib.sha256(f"{entity_type}:{_norm(name)}".encode()).hexdigest()[:16]
    return f"{entity_type}_orphan_{digest}"


def _resolved_entity_id(entity_type: str, ontology_id: str) -> str:
    """Stable id for a MITRE-backed entity (1:1 with its ontology_id)."""
    return f"{entity_type}_{ontology_id}"


def location_entity_id(name: str) -> str:
    """Stable id for a location entity (country). Location has no MITRE mirror, so
    it shares the orphan scheme that OTX ``targets``→location resolves through —
    keeping the same country a single entity across OTX and pDNS ``located-in``.
    This is the reuse point that prevents the endpoint-id mismatch (infra edges
    must NOT go through the generic resolver, which would re-derive a divergent id).
    """
    return _orphan_entity_id("location", name)


def asn_entity_id(value: str) -> str:
    """Stable id for an autonomous-system entity, keyed on the AS number
    (e.g. ``AS29802``). Exact identity like an indicator (the number *is* the
    identity), so minting it is ungated by DECISION-1/2."""
    digest = hashlib.sha256(f"asn:{_norm(value)}".encode()).hexdigest()[:16]
    return f"asn_{digest}"


def _build_indexes(
    ontology_nodes: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, dict[str, Any]]]]:
    """Bucket nodes for resolution: name-resolved lists and id-resolved maps."""
    name_nodes: dict[str, list[dict[str, Any]]] = {}
    oid_nodes: dict[str, dict[str, dict[str, Any]]] = {}
    for node in ontology_nodes:
        ntype = node["type"]
        for etype, otype in _NAME_RESOLVED.items():
            if ntype == otype:
                name_nodes.setdefault(etype, []).append(node)
        # oid map for every resolvable type: the technique id path AND the embedded-id
        # name-back lookup (software/group/campaign) both read it, scoped by entity type.
        for etype, otype in _RESOLVED.items():
            if ntype == otype:
                oid_nodes.setdefault(etype, {})[node["ontology_id"]] = node
    return name_nodes, oid_nodes


def _candidate_dicts(nodes: list[dict[str, Any]], how: str) -> tuple[dict[str, Any], ...]:
    """Held merge-candidate rows (surfaced, never auto-applied) for near-miss nodes."""
    return tuple(
        {"candidate_ontology_id": n["ontology_id"], "candidate_name": n["name"], "how": how}
        for n in nodes
    )


def _substring_candidates(q: str, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nodes whose name or an alias contains the mention (held per DECISION-1)."""
    out: list[dict[str, Any]] = []
    for node in nodes:
        names = [node["name"], *node.get("aliases", [])]
        if any(q in _norm(name) for name in names):
            out.append(node)
    return out


def _resolve_embedded_id(name: str, oid_map: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Resolve a mention that embeds a MITRE attack id (``"Mimikatz - S0002"``).

    Gated by a mandatory name-back check: the embedded id is NEVER trusted on its own.
    Returns the node iff (a) the id maps to a present node in *this entity type's* own
    ontology pool (so cross-type/cross-matrix cannot leak) AND (b) the surrounding name
    agrees with that node's name/aliases. Any mismatch -> ``None`` -> the mention
    orphans. This is what stops the namespace-collision trap: ``"SpyNote RAT -
    MOB-S0021"`` grabs ``S0021`` (enterprise *Derusbi*), the name disagrees, so it is
    rejected rather than silently mis-attributed.
    """
    match = _EMBEDDED_ATTACK_ID.search(name)
    if match is None:
        return None
    node = oid_map.get(match.group(1).upper())
    if node is None:
        return None
    name_part = _loose(_EMBEDDED_ATTACK_ID.sub("", name))
    if not name_part:
        return None
    surfaces = {_loose(node["name"]), *(_loose(a) for a in node.get("aliases", []))}
    return node if name_part in surfaces else None


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
        # Attack ids are case-insensitive (T1003 == t1003) — resolve on the upper form.
        node = oid_nodes.get(etype, {}).get(name.strip().upper())
        return _resolved(etype, node, "exact_id") if node is not None else _orphan(etype, name)

    if etype in _NAME_RESOLVED:
        nodes = name_nodes.get(etype, [])
        q = _norm(name)
        # Exact name (strongest), then exact alias. A UNIQUE exact match auto-reuses
        # (certain). An AMBIGUOUS one — the same surface string claimed by two ontology
        # nodes (e.g. the alias "DNSMessenger" shared by S0145 and S0146) — is NOT
        # silently bound to whichever iterates first: that is a cheap+irreversible+
        # silent fusion (Rule 0 / DECISION-1). It orphans and surfaces every claimant
        # as a held candidate, exactly like a substring near-miss.
        name_hits = [n for n in nodes if _norm(n["name"]) == q]
        if len(name_hits) == 1:
            return _resolved(etype, name_hits[0], "exact_name")
        if len(name_hits) > 1:
            return _orphan(etype, name, _candidate_dicts(name_hits, "ambiguous_name"))
        alias_hits = [n for n in nodes if any(q == _norm(a) for a in n.get("aliases", []))]
        if len(alias_hits) == 1:
            return _resolved(etype, alias_hits[0], "exact_alias")
        if len(alias_hits) > 1:
            return _orphan(etype, name, _candidate_dicts(alias_hits, "ambiguous_alias"))
        # Embedded attack id ("Name - S####"), gated by a name-back check (see helper).
        embedded = _resolve_embedded_id(name, oid_nodes.get(etype, {}))
        if embedded is not None:
            return _resolved(etype, embedded, "embedded_id")
        return _orphan(etype, name, _candidate_dicts(_substring_candidates(q, nodes), "substring"))

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


def resolve_entity_ids(
    mentions: Iterable[tuple[str, str]],
    ontology_nodes: list[dict[str, Any]],
) -> list[str]:
    """Resolve ``(name, entity_type)`` mentions to deduped, sorted entity_ids.

    The id-only projection used to populate a chunk payload's ``entity_ids`` filter
    keys (orphans included — every mention has a stable id). Indexes are built once.
    """
    name_nodes, oid_nodes = _build_indexes(ontology_nodes)
    seen: dict[str, None] = {}
    for name, etype in mentions:
        if not _norm(name):
            continue
        seen[_resolve_one(name, etype, name_nodes, oid_nodes).entity_id] = None
    return sorted(seen)


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
