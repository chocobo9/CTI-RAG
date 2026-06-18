"""M3 — aggregate per-chunk relation triples into global Facts + supports edges.

(`knowledge_layer_design.md §6 Phase 2`, `construction_pipeline_design.md §4-7`.)
Each chunk is one Evidence (`evidence_id = chunk.id`). A claim seen N times across
chunks becomes **one Fact** (keyed by the `(subject_id, predicate, object_id)` triple)
plus **N supports** rows — never a duplicate Fact. Aggregate credibility is
materialized on the Fact at build time (DECISION-3), from a versioned, swappable v0
function (DECISION-4); conflicting single-valued claims are flagged but both kept
(DECISION-5). Pure + deterministic so the build is idempotent and re-runnable.

Input is the projection-bearing chunk corpus (`metadata.relations[]`), NOT
`resolved_relations.jsonl` (which has lost evidence/origin/time). Fields that no
source provides are left ``null`` — never guessed.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# Aggregate-function version (DECISION-4). Bump on any formula change so a Fact
# records which credibility model produced its score; a change implies a rebuild.
AGGREGATE_VERSION = "v0"

# Per-supports confidence by source (construction_pipeline_design.md §5): how the
# fact was derived, fixed when written. These are TIERS, not measured precision —
# mitre explicit edge = high, otx co-occurrence / infra match = medium.
_CONFIDENCE_BY_ORIGIN: dict[str, float] = {
    "mitre": 0.9,
    "otx": 0.7,
    "pdns": 0.7,
    "virustotal": 0.7,
}
_DEFAULT_CONFIDENCE = 0.5

# label_availability (CONTEXT.md §supports): mitre/otx assert the link directly;
# infra (pdns/vt) facts are structural, carrying no TTP attribution (= none). The
# "indirect" inheritance path (attribution borrowed via a shared indicator) needs a
# reverse lookup and is out of M3 scope.
_LABEL_AVAILABILITY_BY_ORIGIN: dict[str, str] = {
    "mitre": "direct",
    "otx": "direct",
    "pdns": "none",
    "virustotal": "none",
}
_DEFAULT_LABEL_AVAILABILITY = "none"

# Observed-range candidates, first non-empty wins (sources name them differently).
_OBSERVED_FIRST_KEYS = ("creation_date", "first_seen")
_OBSERVED_LAST_KEYS = ("last_modified", "last_seen")

# Predicate → group (CONTEXT.md §Fact controlled set).
_GROUP_BY_PREDICATE: dict[str, str] = {
    **dict.fromkeys(("uses", "attributed-to", "targets"), "ttp"),
    **dict.fromkeys(
        ("resolves-to", "belongs-to", "located-in", "uses-nameserver", "has-subdomain"),
        "infra",
    ),
    **dict.fromkeys(("mitigates", "detects"), "defensive"),
}

# Single-valued predicates: a subject may have only one object, so two distinct
# objects is a conflict (DECISION-5). Conservative v0: only attributed-to (and even
# that is "soft" — co-attribution exists, so we flag for review, never auto-resolve).
_SINGLE_VALUED = frozenset({"attributed-to"})

# Entity-id prefixes → entity type. Order so a longer prefix is tried before any
# that could shadow it (none currently overlap, but keep it explicit).
_TYPE_PREFIXES = (
    "detection-strategy",
    "mitigation",
    "technique",
    "campaign",
    "location",
    "indicator",
    "family",
    "actor",
    "asn",
)


@dataclass(frozen=True)
class Support:
    """One Evidence→Fact edge. Identity = (fact_id, evidence_id, origin)."""

    fact_id: str
    evidence_id: str
    origin: str
    confidence: float
    label_availability: str
    observed_first: str | None
    observed_last: str | None


@dataclass(frozen=True)
class Fact:
    """A controlled triple with materialized aggregate over its supports."""

    fact_id: str
    subject_id: str
    predicate: str
    object_id: str
    subject_type: str
    object_type: str
    group: str
    support_count: int
    distinct_origins: tuple[str, ...]
    aggregate_credibility: float
    aggregate_version: str
    conflict: bool


def fact_id(subject_id: str, predicate: str, object_id: str) -> str:
    """Stable id for the triple (\\x1f-joined so values can't collide across slots)."""
    digest = hashlib.sha256(f"{subject_id}\x1f{predicate}\x1f{object_id}".encode()).hexdigest()
    return f"fact_{digest[:16]}"


def entity_type(entity_id: str) -> str:
    """Entity type from an entity_id prefix (``actor_G0016`` → ``actor``)."""
    for prefix in _TYPE_PREFIXES:
        if entity_id.startswith(f"{prefix}_"):
            return prefix
    return "unknown"


def predicate_group(predicate: str) -> str:
    return _GROUP_BY_PREDICATE.get(predicate, "unknown")


def _first_nonempty(metadata: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _aggregate_credibility(supports: list[Support]) -> float:
    """DECISION-4 v0 (provisional, swappable): strongest support, nudged by
    cross-source agreement. Stores the materialized cache; not the final model."""
    if not supports:
        return 0.0
    max_conf = max(s.confidence for s in supports)
    distinct = len({s.origin for s in supports})
    return round(min(max_conf + 0.05 * math.log2(1 + distinct), 1.0), 4)


def _conflicted_fact_ids(triples: Iterable[tuple[str, str, str]]) -> set[str]:
    """Fact ids whose (subject, single-valued predicate) carries >1 distinct object."""
    objects_by_sp: dict[tuple[str, str], set[str]] = {}
    for subject, predicate, obj in triples:
        if predicate in _SINGLE_VALUED:
            objects_by_sp.setdefault((subject, predicate), set()).add(obj)
    conflicted: set[str] = set()
    for (subject, predicate), objects in objects_by_sp.items():
        if len(objects) > 1:
            conflicted.update(fact_id(subject, predicate, o) for o in objects)
    return conflicted


def build_facts(chunks: Iterable[dict[str, Any]]) -> tuple[list[Fact], list[Support]]:
    """Aggregate chunk ``metadata.relations[]`` into Facts + supports.

    One Fact per distinct triple; one Support per (fact, evidence chunk, origin),
    deduped. Both returned sorted by their identity key for deterministic output.
    """
    support_by_key: dict[tuple[str, str, str], Support] = {}
    triples: dict[tuple[str, str, str], None] = {}  # ordered set

    for chunk in chunks:
        origin = str(chunk.get("source", ""))
        evidence_id = str(chunk.get("id", ""))
        metadata = chunk.get("metadata") or {}
        observed_first = _first_nonempty(metadata, _OBSERVED_FIRST_KEYS)
        observed_last = _first_nonempty(metadata, _OBSERVED_LAST_KEYS)
        confidence = _CONFIDENCE_BY_ORIGIN.get(origin, _DEFAULT_CONFIDENCE)
        label = _LABEL_AVAILABILITY_BY_ORIGIN.get(origin, _DEFAULT_LABEL_AVAILABILITY)

        for relation in metadata.get("relations") or []:
            subject = str(relation.get("subject_id", ""))
            predicate = str(relation.get("predicate", ""))
            obj = str(relation.get("object_id", ""))
            if not (subject and predicate and obj):
                continue
            fid = fact_id(subject, predicate, obj)
            triples[(subject, predicate, obj)] = None
            support_key = (fid, evidence_id, origin)
            if support_key not in support_by_key:
                support_by_key[support_key] = Support(
                    fact_id=fid,
                    evidence_id=evidence_id,
                    origin=origin,
                    confidence=confidence,
                    label_availability=label,
                    observed_first=observed_first,
                    observed_last=observed_last,
                )

    supports_by_fact: dict[str, list[Support]] = {}
    for support in support_by_key.values():
        supports_by_fact.setdefault(support.fact_id, []).append(support)

    conflicted = _conflicted_fact_ids(triples)

    facts = [
        Fact(
            fact_id=(fid := fact_id(subject, predicate, obj)),
            subject_id=subject,
            predicate=predicate,
            object_id=obj,
            subject_type=entity_type(subject),
            object_type=entity_type(obj),
            group=predicate_group(predicate),
            support_count=len(supports_by_fact.get(fid, [])),
            distinct_origins=tuple(sorted({s.origin for s in supports_by_fact.get(fid, [])})),
            aggregate_credibility=_aggregate_credibility(supports_by_fact.get(fid, [])),
            aggregate_version=AGGREGATE_VERSION,
            conflict=fid in conflicted,
        )
        for subject, predicate, obj in triples
    ]
    facts.sort(key=lambda f: (f.subject_id, f.predicate, f.object_id))
    supports = sorted(support_by_key.values(), key=lambda s: (s.fact_id, s.evidence_id, s.origin))
    return facts, supports
