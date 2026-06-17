"""Per-source declared normalization (ingestion §4).

Turns a raw source record into a :class:`NormalizedRecord`: a declared
classification, provenance, content, and *mentions* — entity mentions
(name + type, **unresolved**), relation mentions (predicate read from structure,
never inferred for structured sources), and typed indicator mentions.

This layer emits mentions and provenance; it does **not** mint canonical entity
ids or resolve aliases — that is the Entity registry's job (M1), invariant 5.

- Structured sources (MITRE, OTX): structure → mentions with zero inference.
- Narrative sources (PDF): relation/entity extraction defers to NLP (not here).
- Infrastructure (WHOIS/pDNS/VT): emits the keying indicator mention, never a
  TTP relation (infrastructure never predicts attribution — knowledge §2(a)).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from rag_cti.connectors.otx import render_pulse_content
from rag_cti.preprocess.indicators import (
    IndicatorMention,
    canonical_indicator_type,
    indicator_mentions,
)


class SourceClass(StrEnum):
    ONTOLOGY = "ontology"
    WEAKLY_LABELED = "weakly-labeled"
    UNLABELED_NARRATIVE = "unlabeled-narrative"
    INFRASTRUCTURE = "infrastructure"


_CLASSIFICATION: dict[str, SourceClass] = {
    "mitre": SourceClass.ONTOLOGY,
    "otx": SourceClass.WEAKLY_LABELED,
    "pdf": SourceClass.UNLABELED_NARRATIVE,
    "whois": SourceClass.INFRASTRUCTURE,
    "pdns": SourceClass.INFRASTRUCTURE,
    "virustotal": SourceClass.INFRASTRUCTURE,
    "vt": SourceClass.INFRASTRUCTURE,
}


def classify(source_type: str) -> SourceClass:
    """The declared classification for a source; raises on an unknown source."""
    try:
        return _CLASSIFICATION[source_type]
    except KeyError:
        raise ValueError(f"unknown source_type for classification: {source_type!r}") from None


@dataclass(frozen=True)
class EntityMention:
    name: str
    type: str  # actor | campaign | technique | family | indicator | location


@dataclass(frozen=True)
class RelationMention:
    subject: str
    predicate: str  # controlled vocabulary: uses | attributed-to | targets
    object: str
    subject_type: str
    object_type: str


@dataclass(frozen=True)
class Provenance:
    source_type: str
    source_id: str
    url: str = ""
    fetched_at: str = ""
    source_version: str = ""


@dataclass(frozen=True)
class NormalizedRecord:
    provenance: Provenance
    classification: SourceClass
    content: str
    entity_mentions: list[EntityMention] = field(default_factory=list)
    relation_mentions: list[RelationMention] = field(default_factory=list)
    indicator_mentions: list[IndicatorMention] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


_STIX_TYPE_TO_ENTITY: dict[str, str] = {
    "intrusion-set": "actor",
    "campaign": "campaign",
    "malware": "family",
    "tool": "family",
    "attack-pattern": "technique",
    "course-of-action": "mitigation",
    "x-mitre-detection-strategy": "detection-strategy",
}


def _otx_family_names(raw: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for fam in raw.get("malware_families", []):
        if isinstance(fam, str) and fam:
            names.append(fam)
        elif isinstance(fam, dict):
            display_name = fam.get("display_name", "")
            if display_name:
                names.append(display_name)
    return names


def normalize_otx_pulse(raw: dict[str, Any], fetched_at: str = "") -> NormalizedRecord:
    """OTX pulse → mentions from structure (adversary×attack_id → uses;
    adversary×targeted_country → targets). Zero inference."""
    pulse_id = str(raw.get("id", ""))
    adversary = str(raw.get("adversary", "") or "")
    attack_ids = [str(a) for a in raw.get("attack_ids", []) if a]
    countries = [str(c) for c in raw.get("targeted_countries", []) if c]
    families = _otx_family_names(raw)

    entities: list[EntityMention] = []
    if adversary:
        entities.append(EntityMention(adversary, "actor"))
    entities += [EntityMention(f, "family") for f in families]
    entities += [EntityMention(a, "technique") for a in attack_ids]
    entities += [EntityMention(c, "location") for c in countries]

    relations: list[RelationMention] = []
    if adversary:
        relations += [
            RelationMention(adversary, "uses", a, "actor", "technique") for a in attack_ids
        ]
        relations += [RelationMention(adversary, "uses", f, "actor", "family") for f in families]
        relations += [
            RelationMention(adversary, "targets", c, "actor", "location") for c in countries
        ]

    return NormalizedRecord(
        provenance=Provenance(
            source_type="otx",
            source_id=pulse_id,
            url=f"https://otx.alienvault.com/pulse/{pulse_id}" if pulse_id else "",
            fetched_at=fetched_at,
            source_version=str(raw.get("modified", "")),
        ),
        classification=SourceClass.WEAKLY_LABELED,
        content=render_pulse_content(raw),
        entity_mentions=entities,
        relation_mentions=relations,
        indicator_mentions=indicator_mentions(raw.get("indicators", [])),
        metadata={"attack_ids": attack_ids},
    )


def _technique_attack_id(obj: dict[str, Any]) -> str:
    """The T#### attack id of a *technique* object, or "".

    Type-guarded to attack-pattern: intrusion-set / malware / tool also carry a
    mitre-attack external_id (G####/S####), but those are resolved by NAME, not by
    id (entity_registry). Returning their id here would make the relation object
    a G####/S#### string that the name resolver cannot match → a silent orphan
    split (the actor/family target then resolves differently from the same entity
    seen elsewhere). Only techniques resolve by attack id, so only techniques get
    one here.
    """
    if obj.get("type") != "attack-pattern":
        return ""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return str(ref.get("external_id", ""))
    return ""


# Subject types resolved by attack id (their names collide; ids are unique).
_ID_SUBJECT_TYPES = frozenset({"mitigation", "detection-strategy"})


def _subject_ref(obj: dict[str, Any], src_type: str) -> str:
    """Reference form for a relationship subject. mitigation / detection-strategy
    resolve by id (unique M#### / DET####; their names collide), so emit the id;
    actor / family / campaign resolve by name (emitting their G####/S#### id would
    break name resolution into a silent orphan split — see _technique_attack_id)."""
    if src_type in _ID_SUBJECT_TYPES:
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                return str(ref.get("external_id", ""))
    return str(obj.get("name", ""))


def normalize_mitre_relationship(
    raw: dict[str, Any], index: dict[str, dict[str, Any]], fetched_at: str = ""
) -> NormalizedRecord:
    """MITRE STIX relationship → subject/object mentions + predicate from
    ``relationship_type`` (read directly from structure, never inferred)."""
    src = index.get(raw.get("source_ref", ""))
    tgt = index.get(raw.get("target_ref", ""))
    if src is None or tgt is None:
        raise ValueError("unresolvable source_ref/target_ref")

    predicate = str(raw.get("relationship_type", ""))
    tgt_name = str(tgt.get("name", ""))
    src_type = _STIX_TYPE_TO_ENTITY.get(str(src.get("type", "")), "")
    tgt_type = _STIX_TYPE_TO_ENTITY.get(str(tgt.get("type", "")), "")
    attack_id = _technique_attack_id(tgt)
    # Each endpoint's reference form must match how its entity type resolves: a
    # technique / mitigation / detection-strategy by its attack id, an actor /
    # family / campaign by name. Use the SAME ref for the entity mention and the
    # relation endpoint so a chunk's entity_ids and relations[] never disagree.
    tgt_ref = attack_id or tgt_name
    src_ref = _subject_ref(src, src_type)

    return NormalizedRecord(
        provenance=Provenance(
            source_type="mitre",
            source_id=str(raw.get("id", "")),
            url="https://attack.mitre.org/",
            fetched_at=fetched_at,
        ),
        classification=SourceClass.ONTOLOGY,
        content=str(raw.get("description", "")),
        entity_mentions=[EntityMention(src_ref, src_type), EntityMention(tgt_ref, tgt_type)],
        relation_mentions=[RelationMention(src_ref, predicate, tgt_ref, src_type, tgt_type)],
        metadata={"attack_id": attack_id, "relationship_type": predicate},
    )


def normalize_infrastructure(
    raw: dict[str, Any],
    source_type: str,
    indicator_value: str,
    fetched_at: str = "",
    indicator_type: str = "domain",
) -> NormalizedRecord:
    """Field-source record: emits the keying indicator as a mention and no TTP
    relations (infrastructure never predicts attribution — knowledge §2(a))."""
    mentions: list[IndicatorMention] = []
    if indicator_value:
        mentions.append(
            IndicatorMention(
                indicator_value, indicator_type, canonical_indicator_type(indicator_type)
            )
        )
    return NormalizedRecord(
        provenance=Provenance(
            source_type=source_type, source_id=indicator_value, fetched_at=fetched_at
        ),
        classification=SourceClass.INFRASTRUCTURE,
        content="",
        indicator_mentions=mentions,
        metadata=dict(raw) if raw else {},
    )
