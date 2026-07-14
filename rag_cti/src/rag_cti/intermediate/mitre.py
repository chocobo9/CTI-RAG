"""MITRE ATT&CK STIX objects to intermediate dataset transformer."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_cti.intermediate.contract import contract_id
from rag_cti.intermediate.jsonl import write_jsonl

_CONNECTOR_SOURCE = "mitre"
_SOURCE_CLASS = "ontology"
_PUBLISHER_CATEGORY = "knowledge_base"
_SCHEMA_VERSION = "v0.1"
_UNSAFE_PATH = '<>:"/\\|?*'

_OBJECT_TYPE_TO_ENTITY: dict[str, str] = {
    "attack-pattern": "technique",
    "x-mitre-tactic": "tactic",
    "intrusion-set": "actor",
    "malware": "family",
    "tool": "family",
    "campaign": "campaign",
    "course-of-action": "mitigation",
    "x-mitre-detection-strategy": "detection-strategy",
}
_RELATIONSHIP_TYPES = frozenset({"uses", "attributed-to", "mitigates", "detects"})


@dataclass(frozen=True)
class MITRERawRef:
    connector_source: str
    source_id: str
    fetched_at: str
    raw_path: str
    raw_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "connector_source": self.connector_source,
            "source_id": self.source_id,
            "fetched_at": self.fetched_at,
            "raw_path": self.raw_path,
            "raw_sha256": self.raw_sha256,
        }


@dataclass(frozen=True)
class MITRERows:
    intermediate_records: list[dict[str, Any]]
    entity_mentions: list[dict[str, Any]]
    relation_mentions: list[dict[str, Any]]
    attribution_signals: list[dict[str, Any]]
    record_features: list[dict[str, Any]]
    warnings: list[str]
    open_issues: list[str]


def transform_mitre_object(raw: Mapping[str, Any], raw_ref: MITRERawRef) -> MITRERows:
    """Transform one supported MITRE ATT&CK STIX object."""
    record_id = _record_id(raw_ref)
    entity_mentions = _object_entity_mentions(record_id, raw)
    record = _intermediate_record(
        raw=raw,
        raw_ref=raw_ref,
        record_id=record_id,
        entity_mentions=len(entity_mentions),
        relation_mentions=0,
        label_availability="none",
        status="ok",
        warnings=[],
    )
    features = _record_features(raw, record_id, entity_mentions, [])
    return MITRERows(
        intermediate_records=[record],
        entity_mentions=entity_mentions,
        relation_mentions=[],
        attribution_signals=[],
        record_features=[features],
        warnings=[],
        open_issues=[],
    )


def transform_mitre_relationship(
    raw: Mapping[str, Any],
    raw_ref: MITRERawRef,
    stix_index: Mapping[str, Mapping[str, Any]],
) -> MITRERows:
    """Transform one supported MITRE ATT&CK STIX relationship."""
    record_id = _record_id(raw_ref)
    source_ref = _text(raw.get("source_ref"))
    target_ref = _text(raw.get("target_ref"))
    source_obj = stix_index[source_ref]
    target_obj = stix_index[target_ref]
    subject = _endpoint_entity_mention(record_id, source_obj, "source_ref")
    obj = _endpoint_entity_mention(record_id, target_obj, "target_ref")
    relation = _relation_mention(record_id, raw, subject, obj)
    attribution_signals = _attribution_signals(record_id, raw, obj)
    entity_mentions = [subject, obj]
    record = _intermediate_record(
        raw=raw,
        raw_ref=raw_ref,
        record_id=record_id,
        entity_mentions=len(entity_mentions),
        relation_mentions=1,
        label_availability=_label_availability(raw),
        status="ok",
        warnings=[],
    )
    features = _record_features(raw, record_id, entity_mentions, [relation])
    return MITRERows(
        intermediate_records=[record],
        entity_mentions=entity_mentions,
        relation_mentions=[relation],
        attribution_signals=attribution_signals,
        record_features=[features],
        warnings=[],
        open_issues=[],
    )


def build_mitre_intermediate_package(
    raw_objects: Iterable[Mapping[str, Any]],
    output_dir: Path,
    *,
    dataset_id: str,
    dataset_version: str,
    generated_at: str,
    fetched_at: str,
    schema_version: str = _SCHEMA_VERSION,
) -> MITRERows:
    """Write a MITRE-only intermediate delivery package."""
    output_dir = Path(output_dir)
    (output_dir / "raw" / "mitre").mkdir(parents=True, exist_ok=True)
    objects = list(raw_objects)
    stix_index = {
        stix_id: raw
        for raw in objects
        if (stix_id := _text(raw.get("id"))) and _text(raw.get("type")) != "relationship"
    }
    rows = MITRERows([], [], [], [], [], [], [])

    for raw in objects:
        raw_ref = _write_raw_object(output_dir, raw, fetched_at)
        stix_type = _text(raw.get("type"))
        if stix_type == "relationship":
            relationship_type = _text(raw.get("relationship_type"))
            if relationship_type not in _RELATIONSHIP_TYPES:
                rows.warnings.append(
                    f"unsupported MITRE relationship_type {relationship_type!r} was skipped"
                )
                continue
            source_ref = _text(raw.get("source_ref"))
            target_ref = _text(raw.get("target_ref"))
            if source_ref not in stix_index or target_ref not in stix_index:
                rows.warnings.append(
                    f"MITRE relationship {raw_ref.source_id!r} has unresolvable endpoint"
                )
                continue
            endpoint_types = {
                _text(stix_index[source_ref].get("type")),
                _text(stix_index[target_ref].get("type")),
            }
            if not endpoint_types <= _OBJECT_TYPE_TO_ENTITY.keys():
                rows.warnings.append(
                    f"MITRE relationship {raw_ref.source_id!r} has unsupported endpoint type"
                )
                continue
            item_rows = transform_mitre_relationship(raw, raw_ref, stix_index)
        elif stix_type in _OBJECT_TYPE_TO_ENTITY and not raw.get("revoked", False):
            item_rows = transform_mitre_object(raw, raw_ref)
        else:
            rows.warnings.append(f"unsupported MITRE object type {stix_type!r} was skipped")
            continue

        rows.intermediate_records.extend(item_rows.intermediate_records)
        rows.entity_mentions.extend(item_rows.entity_mentions)
        rows.relation_mentions.extend(item_rows.relation_mentions)
        rows.attribution_signals.extend(item_rows.attribution_signals)
        rows.record_features.extend(item_rows.record_features)
        rows.warnings.extend(item_rows.warnings)
        rows.open_issues.extend(item_rows.open_issues)

    intermediate = output_dir / "intermediate"
    _write_json(
        intermediate / "source_manifest.json",
        _source_manifest(
            dataset_id,
            dataset_version,
            schema_version,
            generated_at,
            len(rows.intermediate_records),
        ),
    )
    write_jsonl(intermediate / "intermediate_records.jsonl", rows.intermediate_records)
    write_jsonl(intermediate / "entity_mentions.jsonl", rows.entity_mentions)
    write_jsonl(intermediate / "relation_mentions.jsonl", rows.relation_mentions)
    write_jsonl(intermediate / "attribution_signals.jsonl", rows.attribution_signals)
    write_jsonl(intermediate / "record_features.jsonl", rows.record_features)
    _write_json(
        intermediate / "processing_report.json",
        _processing_report(dataset_id, dataset_version, schema_version, generated_at, rows),
    )
    return rows


def _write_raw_object(root: Path, raw: Mapping[str, Any], fetched_at: str) -> MITRERawRef:
    source_id = _text(raw.get("id")) or contract_id("source", (dict(raw),))
    raw_text = json.dumps(raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    raw_sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    filename = f"{_safe_segment(fetched_at)}_{raw_sha[:24]}.json"
    raw_rel = Path("raw") / "mitre" / _safe_segment(source_id) / filename
    raw_path = root / raw_rel
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw_text, encoding="utf-8")
    return MITRERawRef(
        connector_source=_CONNECTOR_SOURCE,
        source_id=source_id,
        fetched_at=fetched_at,
        raw_path=raw_rel.as_posix(),
        raw_sha256=raw_sha,
    )


def _record_id(raw_ref: MITRERawRef) -> str:
    return f"record_mitre_{_safe_segment(raw_ref.source_id)}_{raw_ref.raw_sha256[:24]}"


def _object_entity_mentions(record_id: str, raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    mentions = [_primary_entity_mention(record_id, raw, _primary_source_field(raw))]
    if _text(raw.get("type")) == "attack-pattern":
        for tactic in _tactics(raw):
            mentions.append(
                _entity_mention(
                    record_id=record_id,
                    raw_value=tactic,
                    entity_type="tactic",
                    source_field="kill_chain_phases[].phase_name",
                    occurrence_count=1,
                    resolution={
                        "entity_id": contract_id("tactic", (tactic.lower(),)),
                        "canonical_name": tactic,
                        "ontology_id": None,
                        "resolution_method": "not_applicable",
                    },
                    value_type={"raw": "kill_chain_phase", "canonical": "tactic"},
                )
            )
    return mentions


def _endpoint_entity_mention(
    record_id: str, raw: Mapping[str, Any], source_field: str
) -> dict[str, Any]:
    return _primary_entity_mention(record_id, raw, source_field)


def _primary_entity_mention(
    record_id: str, raw: Mapping[str, Any], source_field: str
) -> dict[str, Any]:
    stix_type = _text(raw.get("type"))
    entity_type = _OBJECT_TYPE_TO_ENTITY[stix_type]
    attack_id = _attack_id(raw)
    name = _text(raw.get("name"))
    raw_value = attack_id if entity_type == "technique" and attack_id else name
    if not raw_value:
        raw_value = attack_id or _text(raw.get("id"))
    return _entity_mention(
        record_id=record_id,
        raw_value=raw_value,
        entity_type=entity_type,
        source_field=source_field,
        occurrence_count=1,
        resolution=_resolution(raw, entity_type, raw_value),
        value_type={"raw": stix_type, "canonical": entity_type},
    )


def _entity_mention(
    *,
    record_id: str,
    raw_value: str,
    entity_type: str,
    source_field: str,
    occurrence_count: int,
    resolution: dict[str, Any],
    value_type: dict[str, str | None],
) -> dict[str, Any]:
    normalized = raw_value.strip()
    mention_id = contract_id(
        "em",
        (
            record_id,
            source_field,
            entity_type,
            normalized,
            value_type,
            resolution.get("entity_id"),
        ),
    )
    return {
        "entity_mention_id": mention_id,
        "record_id": record_id,
        "raw_value": raw_value,
        "normalized_value": normalized,
        "entity_type": entity_type,
        "source_field": source_field,
        "extraction_method": "source_field",
        "occurrence_count": occurrence_count,
        "value_type": value_type,
        "resolution": resolution,
        "ambiguity": {
            "status": "resolved"
            if resolution["resolution_method"] in {"exact_id", "not_applicable"}
            else "unresolved",
            "reason": None,
            "candidate_entity_ids": [],
        },
        "merge_candidates": [],
    }


def _resolution(raw: Mapping[str, Any], entity_type: str, raw_value: str) -> dict[str, Any]:
    attack_id = _attack_id(raw)
    ontology_id = attack_id or None
    entity_id = f"{entity_type}_{attack_id}" if attack_id else contract_id(f"{entity_type}_orphan", (raw_value,))
    return {
        "entity_id": entity_id,
        "canonical_name": _text(raw.get("name")) or raw_value,
        "ontology_id": ontology_id,
        "resolution_method": "exact_id" if attack_id else "orphan",
        "stix_id": _text(raw.get("id")) or None,
        "aliases": _aliases(raw),
    }


def _relation_mention(
    record_id: str,
    raw: Mapping[str, Any],
    subject: dict[str, Any],
    obj: dict[str, Any],
) -> dict[str, Any]:
    predicate = _text(raw.get("relationship_type"))
    source_field = "relationship_type,source_ref,target_ref"
    relation_id = contract_id(
        "rm",
        (
            record_id,
            subject["entity_mention_id"],
            predicate,
            obj["entity_mention_id"],
            source_field,
        ),
    )
    return {
        "relation_mention_id": relation_id,
        "record_id": record_id,
        "subject": {
            "raw_value": subject["raw_value"],
            "entity_mention_id": subject["entity_mention_id"],
            "entity_type": subject["entity_type"],
        },
        "predicate": {
            "raw_value": predicate,
            "mapped_value": predicate,
            "mapping_status": "mapped",
        },
        "object": {
            "raw_value": obj["raw_value"],
            "entity_mention_id": obj["entity_mention_id"],
            "entity_type": obj["entity_type"],
        },
        "derivation": {
            "source_field": source_field,
            "extraction_method": "structured_relation",
            "derivation_method": "structured_relation",
            "evidence_type": _evidence_type(predicate),
            "label_availability": _label_availability(raw),
            "attribution_confidence": None,
        },
        "ambiguity": {"status": "unambiguous", "notes": []},
    }


def _attribution_signals(
    record_id: str, raw: Mapping[str, Any], target: dict[str, Any]
) -> list[dict[str, Any]]:
    if _text(raw.get("relationship_type")) != "attributed-to" or target["entity_type"] != "actor":
        return []
    return [
        {
            "attribution_signal_id": contract_id(
                "as",
                (
                    record_id,
                    "direct_attribution",
                    "actor",
                    target["raw_value"],
                    "relationship_type,target_ref",
                ),
            ),
            "record_id": record_id,
            "signal_type": "direct_attribution",
            "target_entity_type": "actor",
            "raw_label": target["raw_value"],
            "resolved_entity_id": target["resolution"]["entity_id"],
            "source_field": "relationship_type,target_ref",
            "source_provided_confidence": None,
            "derivation_method": "structured_relation",
            "notes": ["MITRE attributed-to is direct source-backed attribution, not independent verification."],
        }
    ]


def _intermediate_record(
    *,
    raw: Mapping[str, Any],
    raw_ref: MITRERawRef,
    record_id: str,
    entity_mentions: int,
    relation_mentions: int,
    label_availability: str,
    status: str,
    warnings: list[str],
) -> dict[str, Any]:
    stix_type = _text(raw.get("type"))
    return {
        "record_id": record_id,
        "raw_ref": raw_ref.to_dict(),
        "source": {
            "connector_source": _CONNECTOR_SOURCE,
            "source_class": _SOURCE_CLASS,
            "publisher_category": _PUBLISHER_CATEGORY,
            "source_name": "MITRE ATT&CK",
            "source_record_id": raw_ref.source_id,
            "stix_id": raw_ref.source_id,
            "object_type": stix_type,
            "attack_id": _attack_id(raw) or None,
            "relationship_type": _text(raw.get("relationship_type")) or None,
        },
        "timestamps": {
            "published_at": _text(raw.get("created")) or None,
            "modified_at": _text(raw.get("modified")) or None,
            "observed_first": None,
            "observed_last": None,
            "fetched_at": raw_ref.fetched_at,
            "timestamp_basis": "source_modified" if _text(raw.get("modified")) else "fetched_only",
        },
        "record_signals": {
            "label_availability": label_availability,
            "has_attribution_confidence": False,
            "ambiguity_flag": False,
        },
        "counts": {
            "entity_mentions": entity_mentions,
            "relation_mentions": relation_mentions,
            "external_references": len(_list(raw.get("external_references"))),
            "aliases": len(_aliases(raw)),
            "tactics": len(_tactics(raw)),
        },
        "processing_status": {"status": status, "warnings": warnings},
    }


def _record_features(
    raw: Mapping[str, Any],
    record_id: str,
    entity_mentions: list[dict[str, Any]],
    relation_mentions: list[dict[str, Any]],
) -> dict[str, Any]:
    timestamp_basis = "source_modified" if _text(raw.get("modified")) else "fetched_only"
    return {
        "record_id": record_id,
        "source_features": {
            "connector_source": _CONNECTOR_SOURCE,
            "source_class": _SOURCE_CLASS,
            "publisher_category": _PUBLISHER_CATEGORY,
        },
        "timestamp_features": {
            "has_published_at": bool(_text(raw.get("created"))),
            "has_modified_at": bool(_text(raw.get("modified"))),
            "has_observed_range": False,
            "age_days_at_collection": None,
            "timestamp_basis": timestamp_basis,
        },
        "content_features": {
            "stix_type": _text(raw.get("type")) or None,
            "entity_type_distribution": dict(
                sorted(Counter(row["entity_type"] for row in entity_mentions).items())
            ),
            "relationship_type": _text(raw.get("relationship_type")) or None,
            "tactics": _tactics(raw),
        },
        "label_features": {
            "label_availability": _label_availability(raw),
            "has_confidence": False,
            "supporting_sources_count": None,
            "conflicting_sources_count": None,
        },
        "ambiguity_features": {
            "ambiguous_entity_mentions": sum(
                1 for mention in entity_mentions if mention["ambiguity"]["status"] == "ambiguous"
            ),
            "ambiguous_relation_mentions": sum(
                1 for relation in relation_mentions if relation["ambiguity"]["status"] == "ambiguous"
            ),
        },
    }


def _source_manifest(
    dataset_id: str,
    dataset_version: str,
    schema_version: str,
    generated_at: str,
    record_count: int,
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "schema_version": schema_version,
        "generated_at": generated_at,
        "sources": [
            {
                "connector_source": _CONNECTOR_SOURCE,
                "source_class": _SOURCE_CLASS,
                "publisher_category": _PUBLISHER_CATEGORY,
                "record_count": record_count,
                "raw_collection": "raw/mitre",
                "provides": {
                    "labels": True,
                    "enrichment": False,
                    "timestamps": True,
                    "actor_aliases": True,
                    "campaign_names": True,
                    "malware_names": True,
                    "tools": True,
                    "techniques": True,
                    "indicators": False,
                    "mitigations": True,
                    "detection_strategies": True,
                },
            }
        ],
    }


def _processing_report(
    dataset_id: str,
    dataset_version: str,
    schema_version: str,
    generated_at: str,
    rows: MITRERows,
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "schema_version": schema_version,
        "generated_at": generated_at,
        "counts": {
            "intermediate_records": len(rows.intermediate_records),
            "entity_mentions": len(rows.entity_mentions),
            "relation_mentions": len(rows.relation_mentions),
            "attribution_signals": len(rows.attribution_signals),
            "warnings": len(rows.warnings),
        },
        "coverage": {
            "connector_sources": {_CONNECTOR_SOURCE: len(rows.intermediate_records)},
            "entity_types": dict(
                sorted(Counter(row["entity_type"] for row in rows.entity_mentions).items())
            ),
            "relation_predicates": dict(
                sorted(
                    Counter(row["predicate"]["mapped_value"] for row in rows.relation_mentions).items()
                )
            ),
            "attribution_signal_types": dict(
                sorted(Counter(row["signal_type"] for row in rows.attribution_signals).items())
            ),
        },
        "warnings": rows.warnings,
        "open_issues": sorted(set(rows.open_issues)),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _attack_id(raw: Mapping[str, Any]) -> str:
    for ref in _list(raw.get("external_references")):
        if isinstance(ref, Mapping) and ref.get("source_name") == "mitre-attack":
            return _text(ref.get("external_id"))
    return ""


def _aliases(raw: Mapping[str, Any]) -> list[str]:
    name = _text(raw.get("name"))
    values = raw.get("aliases") or raw.get("x_mitre_aliases") or []
    if not isinstance(values, list):
        return []
    aliases: list[str] = []
    for value in values:
        alias = _text(value)
        if alias and alias != name:
            aliases.append(alias)
    return aliases


def _tactics(raw: Mapping[str, Any]) -> list[str]:
    tactics: list[str] = []
    for phase in _list(raw.get("kill_chain_phases")):
        if not isinstance(phase, Mapping):
            continue
        if phase.get("kill_chain_name") == "mitre-attack":
            tactic = _text(phase.get("phase_name"))
            if tactic:
                tactics.append(tactic)
    return tactics


def _primary_source_field(raw: Mapping[str, Any]) -> str:
    entity_type = _OBJECT_TYPE_TO_ENTITY[_text(raw.get("type"))]
    if entity_type == "technique" and _attack_id(raw):
        return "external_references[].external_id"
    return "name"


def _evidence_type(predicate: str) -> str:
    if predicate in {"mitigates", "detects"}:
        return "defensive"
    if predicate == "attributed-to":
        return "attribution"
    return "ttp"


def _label_availability(raw: Mapping[str, Any]) -> str:
    return "direct" if _text(raw.get("relationship_type")) == "attributed-to" else "none"


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_segment(value: str) -> str:
    out = "".join("-" if char in _UNSAFE_PATH else char for char in value)
    return out.strip().strip(".") or "_"
