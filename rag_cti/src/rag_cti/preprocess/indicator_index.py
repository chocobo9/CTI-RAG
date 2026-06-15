"""Indicator index — indicators as Knowledge-Layer entities, not payload metadata.

Decision (2026-06): the full indicator set does not belong in the Qdrant payload.
A single OTX pulse carries up to ~20k indicators, and the vector store is never
the system of record (retrieval invariant). Instead every indicator becomes an
entity-shaped record in a standalone index that can evolve into the Entity
registry's indicator subset.

``actor_ids`` linkage is intentionally **not** populated here — it requires M1
actor resolution. The interface is left open (callers can add it later);
fabricating it now would violate the leave-the-interface / don't-fabricate rule.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

from rag_cti.preprocess.indicators import IndicatorMention

_INDICATOR_ID_PREFIX = "indicator_"


def indicator_entity_id(mention: IndicatorMention) -> str:
    """Deterministic entity id keyed on ``(kind, value)``.

    Kind is the canonical type when known, else the verbatim source type. This is
    an exact identity (no fuzzy/substring merge), so minting it is ungated by
    DECISION-1/2; the same value seen under two different kinds stays two
    entities (never silently merged).
    """
    kind = mention.canonical_type or mention.type or ""
    digest = hashlib.sha256(f"{kind}:{mention.value}".encode()).hexdigest()[:16]
    return f"{_INDICATOR_ID_PREFIX}{digest}"


def build_indicator_index(
    per_source: Iterable[tuple[str, list[IndicatorMention]]],
) -> list[dict[str, Any]]:
    """Build entity-shaped indicator records from ``(source_id, mentions)`` pairs.

    Returns one record per distinct indicator entity, each carrying the sorted set
    of source_ids that referenced it (occurrence map). Output is deterministically
    ordered by entity_id.
    """
    entities: dict[str, dict[str, Any]] = {}
    occurrences: dict[str, set[str]] = {}

    for source_id, mentions in per_source:
        for m in mentions:
            eid = indicator_entity_id(m)
            if eid not in entities:
                entities[eid] = {
                    "entity_id": eid,
                    "type": "indicator",  # CONTEXT Entity.type
                    "indicator_type": m.type,  # source kind, verbatim
                    "canonical_type": m.canonical_type,
                    "value": m.value,
                    "ontology_id": None,  # indicators have no MITRE OntologyNode
                    "source_ids": [],
                    # actor_ids: deferred to M1 (actor resolution) — interface only
                }
            if source_id:
                occurrences.setdefault(eid, set()).add(source_id)

    out: list[dict[str, Any]] = []
    for eid in sorted(entities):
        rec = dict(entities[eid])
        rec["source_ids"] = sorted(occurrences.get(eid, set()))
        out.append(rec)
    return out
