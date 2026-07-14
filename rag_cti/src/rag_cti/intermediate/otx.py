"""OTX raw pulse to intermediate dataset transformer."""

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
from rag_cti.preprocess.indicators import canonical_indicator_type

_CONNECTOR_SOURCE = "otx"
_SOURCE_CLASS = "weakly_labeled_narrative"
_PUBLISHER_CATEGORY = "threat_intelligence_platform"
_SCHEMA_VERSION = "v0.1"
_UNSAFE_PATH = '<>:"/\\|?*'


@dataclass(frozen=True)
class RawRef:
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
class OTXRows:
    intermediate_records: list[dict[str, Any]]
    entity_mentions: list[dict[str, Any]]
    relation_mentions: list[dict[str, Any]]
    attribution_signals: list[dict[str, Any]]
    record_features: list[dict[str, Any]]
    warnings: list[str]
    open_issues: list[str]


def transform_otx_pulse(
    raw: Mapping[str, Any],
    raw_ref: RawRef,
    *,
    actor_resolutions: Mapping[str, Mapping[str, str | None]] | None = None,
) -> OTXRows:
    """Transform one raw OTX pulse into intermediate artifact rows."""
    source_record_id = _text(raw.get("id")) or raw_ref.source_id
    record_id = f"record_otx_{_safe_segment(source_record_id)}_{raw_ref.raw_sha256[:24]}"
    warnings: list[str] = []
    open_issues = ["OTX industries are emitted as sector mentions; sector relations are deferred."]

    entity_mentions: list[dict[str, Any]] = []
    mention_by_role: dict[tuple[str, str, str], dict[str, Any]] = {}

    adversary = _text(raw.get("adversary"))
    actor_mention: dict[str, Any] | None = None
    if adversary:
        actor_mention = _entity_mention(
            record_id=record_id,
            raw_value=adversary,
            entity_type="actor",
            source_field="adversary",
            occurrence_count=1,
            resolution=_actor_resolution(adversary, actor_resolutions or {}),
        )
        entity_mentions.append(actor_mention)
        mention_by_role[("adversary", "actor", adversary)] = actor_mention

    for attack_id, count in _counted_strings(raw.get("attack_ids")).items():
        mention = _entity_mention(
            record_id=record_id,
            raw_value=attack_id,
            entity_type="technique",
            source_field="attack_ids[]",
            occurrence_count=count,
            resolution={
                "entity_id": f"technique_{attack_id}",
                "canonical_name": attack_id,
                "ontology_id": attack_id,
                "resolution_method": "exact_id",
            },
        )
        entity_mentions.append(mention)
        mention_by_role[("attack_ids[]", "technique", attack_id)] = mention

    for family, count in _counted_strings(_malware_family_names(raw.get("malware_families"))).items():
        mention = _entity_mention(
            record_id=record_id,
            raw_value=family,
            entity_type="family",
            source_field="malware_families[]",
            occurrence_count=count,
            resolution=_orphan_resolution("family", family),
        )
        entity_mentions.append(mention)
        mention_by_role[("malware_families[]", "family", family)] = mention

    for country, count in _counted_strings(raw.get("targeted_countries")).items():
        mention = _entity_mention(
            record_id=record_id,
            raw_value=country,
            entity_type="location",
            source_field="targeted_countries[]",
            occurrence_count=count,
            resolution=_orphan_resolution("location", country),
        )
        entity_mentions.append(mention)
        mention_by_role[("targeted_countries[]", "location", country)] = mention

    for industry, count in _counted_strings(raw.get("industries")).items():
        entity_mentions.append(
            _entity_mention(
                record_id=record_id,
                raw_value=industry,
                entity_type="sector",
                source_field="industries[]",
                occurrence_count=count,
                resolution=_orphan_resolution("sector", industry),
            )
        )

    for tag, count in _counted_strings(raw.get("tags")).items():
        entity_mentions.append(
            _entity_mention(
                record_id=record_id,
                raw_value=tag,
                entity_type="tag",
                source_field="tags[]",
                occurrence_count=count,
                resolution=_not_applicable_resolution("tag", tag),
            )
        )

    for reference, count in _counted_strings(raw.get("references")).items():
        entity_mentions.append(
            _entity_mention(
                record_id=record_id,
                raw_value=reference,
                entity_type="external_reference",
                source_field="references[]",
                occurrence_count=count,
                resolution=_not_applicable_resolution("external_reference", reference),
            )
        )

    indicator_mentions = _indicator_entity_mentions(record_id, raw.get("indicators"), warnings)
    entity_mentions.extend(indicator_mentions)

    relation_mentions = _relation_mentions(record_id, actor_mention, mention_by_role)
    attribution_signals = _attribution_signals(record_id, actor_mention, adversary)

    record = _intermediate_record(
        raw=raw,
        raw_ref=raw_ref,
        record_id=record_id,
        entity_mentions=len(entity_mentions),
        relation_mentions=len(relation_mentions),
        warnings=warnings,
    )
    features = _record_features(raw, record_id, entity_mentions, relation_mentions, adversary)

    return OTXRows(
        intermediate_records=[record],
        entity_mentions=entity_mentions,
        relation_mentions=relation_mentions,
        attribution_signals=attribution_signals,
        record_features=[features],
        warnings=warnings,
        open_issues=open_issues,
    )


def build_otx_intermediate_package(
    raw_pulses: Iterable[Mapping[str, Any]],
    output_dir: Path,
    *,
    dataset_id: str,
    dataset_version: str,
    generated_at: str,
    fetched_at: str,
    schema_version: str = _SCHEMA_VERSION,
    actor_resolutions: Mapping[str, Mapping[str, str | None]] | None = None,
) -> OTXRows:
    """Write an OTX-only intermediate delivery package."""
    output_dir = Path(output_dir)
    rows = OTXRows([], [], [], [], [], [], [])

    for raw in raw_pulses:
        raw_ref = _write_raw_pulse(output_dir, raw, fetched_at)
        pulse_rows = transform_otx_pulse(
            raw,
            raw_ref,
            actor_resolutions=actor_resolutions,
        )
        rows.intermediate_records.extend(pulse_rows.intermediate_records)
        rows.entity_mentions.extend(pulse_rows.entity_mentions)
        rows.relation_mentions.extend(pulse_rows.relation_mentions)
        rows.attribution_signals.extend(pulse_rows.attribution_signals)
        rows.record_features.extend(pulse_rows.record_features)
        rows.warnings.extend(pulse_rows.warnings)
        rows.open_issues.extend(pulse_rows.open_issues)

    intermediate = output_dir / "intermediate"
    _write_json(
        intermediate / "source_manifest.json",
        _source_manifest(dataset_id, dataset_version, schema_version, generated_at, len(rows.intermediate_records)),
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


def _write_raw_pulse(root: Path, raw: Mapping[str, Any], fetched_at: str) -> RawRef:
    source_id = _text(raw.get("id")) or contract_id("source", (dict(raw),))
    raw_text = json.dumps(raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    raw_sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    filename = f"{_safe_segment(fetched_at)}_{raw_sha[:24]}.json"
    raw_rel = Path("raw") / "otx" / _safe_segment(source_id) / filename
    raw_path = root / raw_rel
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw_text, encoding="utf-8")
    return RawRef(
        connector_source=_CONNECTOR_SOURCE,
        source_id=source_id,
        fetched_at=fetched_at,
        raw_path=raw_rel.as_posix(),
        raw_sha256=raw_sha,
    )


def _intermediate_record(
    *,
    raw: Mapping[str, Any],
    raw_ref: RawRef,
    record_id: str,
    entity_mentions: int,
    relation_mentions: int,
    warnings: list[str],
) -> dict[str, Any]:
    label_availability = "direct" if _text(raw.get("adversary")) else "none"
    return {
        "record_id": record_id,
        "raw_ref": raw_ref.to_dict(),
        "source": {
            "connector_source": _CONNECTOR_SOURCE,
            "source_class": _SOURCE_CLASS,
            "publisher_category": _PUBLISHER_CATEGORY,
            "source_name": "AlienVault OTX",
            "source_record_id": raw_ref.source_id,
            "source_contributor": {
                "author": _text(raw.get("author")) or None,
                "author_name": _text(raw.get("author_name")) or None,
            },
            "tlp": _text(raw.get("TLP")) or None,
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
            "indicators": len(_indicator_dicts(raw.get("indicators"))),
            "tags": len(_strings(raw.get("tags"))),
            "references": len(_strings(raw.get("references"))),
        },
        "processing_status": {"status": "partial" if warnings else "ok", "warnings": warnings},
    }


def _entity_mention(
    *,
    record_id: str,
    raw_value: str,
    entity_type: str,
    source_field: str,
    occurrence_count: int,
    resolution: dict[str, Any],
    value_type: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    normalized = raw_value.strip()
    mention_id = contract_id(
        "em",
        (
            record_id,
            source_field,
            entity_type,
            normalized,
            value_type or {"raw": None, "canonical": None},
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
        "value_type": value_type or {"raw": None, "canonical": None},
        "resolution": resolution,
        "ambiguity": {
            "status": "resolved"
            if resolution["resolution_method"]
            in {"exact_id", "exact_name", "exact_alias", "embedded_id", "not_applicable"}
            else "unresolved",
            "reason": None,
            "candidate_entity_ids": [],
        },
        "merge_candidates": [],
    }


def _indicator_entity_mentions(
    record_id: str, raw_indicators: Any, warnings: list[str]
) -> list[dict[str, Any]]:
    counted: dict[tuple[str, str | None, str | None], int] = Counter()
    for indicator in _indicator_dicts(raw_indicators):
        value = _text(indicator.get("indicator"))
        if not value:
            continue
        raw_type = _text(indicator.get("type")) or None
        canonical = canonical_indicator_type(raw_type) if raw_type else None
        if raw_type is None:
            warnings.append(f"indicator {value!r} is missing raw indicator type")
        counted[(value, raw_type, canonical)] += 1

    rows: list[dict[str, Any]] = []
    for (value, raw_type, canonical), count in sorted(counted.items(), key=_indicator_sort_key):
        rows.append(
            _entity_mention(
                record_id=record_id,
                raw_value=value,
                entity_type="indicator",
                source_field="indicators[].indicator",
                occurrence_count=count,
                value_type={"raw": raw_type, "canonical": canonical},
                resolution={
                    "entity_id": contract_id("indicator", (canonical, value)),
                    "canonical_name": value,
                    "ontology_id": None,
                    "resolution_method": "not_applicable",
                },
            )
        )
    return rows


def _indicator_sort_key(
    item: tuple[tuple[str, str | None, str | None], int],
) -> tuple[str, bool, str, bool, str]:
    value, raw_type, canonical = item[0]
    return (value, raw_type is not None, raw_type or "", canonical is not None, canonical or "")


def _relation_mentions(
    record_id: str,
    actor_mention: dict[str, Any] | None,
    mention_by_role: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    if actor_mention is None:
        return []
    rows: list[dict[str, Any]] = []
    for source_field, entity_type, raw_value in sorted(mention_by_role):
        if source_field == "adversary":
            continue
        target = mention_by_role[(source_field, entity_type, raw_value)]
        if entity_type == "technique":
            rows.append(
                _relation_mention(
                    record_id,
                    actor_mention,
                    target,
                    "uses",
                    "adversary+attack_ids co-occurrence",
                    "adversary,attack_ids",
                    "ttp",
                )
            )
        elif entity_type == "family":
            rows.append(
                _relation_mention(
                    record_id,
                    actor_mention,
                    target,
                    "uses",
                    "adversary+malware_families co-occurrence",
                    "adversary,malware_families",
                    "malware",
                )
            )
        elif entity_type == "location":
            rows.append(
                _relation_mention(
                    record_id,
                    actor_mention,
                    target,
                    "targets",
                    "adversary+targeted_countries co-occurrence",
                    "adversary,targeted_countries",
                    "victimology",
                )
            )
    return rows


def _relation_mention(
    record_id: str,
    subject: dict[str, Any],
    obj: dict[str, Any],
    predicate: str,
    raw_predicate: str,
    source_field: str,
    evidence_type: str,
) -> dict[str, Any]:
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
            "raw_value": raw_predicate,
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
            "extraction_method": "structured_cooccurrence",
            "evidence_type": evidence_type,
            "label_availability": "direct",
            "attribution_confidence": None,
        },
        "ambiguity": {"status": "unambiguous", "notes": []},
    }


def _attribution_signals(
    record_id: str, actor_mention: dict[str, Any] | None, adversary: str
) -> list[dict[str, Any]]:
    if actor_mention is None:
        return []
    return [
        {
            "attribution_signal_id": contract_id(
                "as", (record_id, "weak_direct_attribution", "actor", adversary, "adversary")
            ),
            "record_id": record_id,
            "signal_type": "weak_direct_attribution",
            "target_entity_type": "actor",
            "raw_label": adversary,
            "resolved_entity_id": actor_mention["resolution"]["entity_id"],
            "source_field": "adversary",
            "source_provided_confidence": None,
            "derivation_method": "source_field",
            "notes": ["OTX adversary is preserved as a weak source cue, not ground truth."],
        }
    ]


def _record_features(
    raw: Mapping[str, Any],
    record_id: str,
    entity_mentions: list[dict[str, Any]],
    relation_mentions: list[dict[str, Any]],
    adversary: str,
) -> dict[str, Any]:
    indicator_types = Counter(
        mention["value_type"]["canonical"] or "unknown"
        for mention in entity_mentions
        if mention["entity_type"] == "indicator"
    )
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
            "timestamp_basis": "source_modified" if _text(raw.get("modified")) else "fetched_only",
        },
        "content_features": {
            "indicator_count": len(_indicator_dicts(raw.get("indicators"))),
            "indicator_type_distribution": dict(sorted(indicator_types.items())),
            "tag_count": len(_strings(raw.get("tags"))),
            "reference_count": len(_strings(raw.get("references"))),
        },
        "label_features": {
            "label_availability": "direct" if adversary else "none",
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
    dataset_id: str, dataset_version: str, schema_version: str, generated_at: str, record_count: int
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
                "raw_collection": "raw/otx",
                "provides": {
                    "labels": True,
                    "enrichment": False,
                    "timestamps": True,
                    "actor_aliases": False,
                    "campaign_names": True,
                    "malware_names": True,
                    "tools": False,
                    "techniques": True,
                    "indicators": True,
                },
            }
        ],
    }


def _processing_report(
    dataset_id: str,
    dataset_version: str,
    schema_version: str,
    generated_at: str,
    rows: OTXRows,
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
                    Counter(
                        row["predicate"]["mapped_value"] for row in rows.relation_mentions
                    ).items()
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


def _orphan_resolution(entity_type: str, value: str) -> dict[str, Any]:
    return {
        "entity_id": contract_id(f"{entity_type}_orphan", (entity_type, value.strip().lower())),
        "canonical_name": value,
        "ontology_id": None,
        "resolution_method": "orphan",
    }


def _actor_resolution(
    value: str, actor_resolutions: Mapping[str, Mapping[str, str | None]]
) -> dict[str, Any]:
    resolved = actor_resolutions.get(value) or actor_resolutions.get(value.strip().lower())
    if resolved is None:
        return _orphan_resolution("actor", value)
    entity_id = resolved.get("entity_id")
    if not entity_id:
        return _orphan_resolution("actor", value)
    return {
        "entity_id": entity_id,
        "canonical_name": resolved.get("canonical_name") or value,
        "ontology_id": resolved.get("ontology_id"),
        "resolution_method": resolved.get("resolution_method") or "exact_alias",
    }


def _not_applicable_resolution(entity_type: str, value: str) -> dict[str, Any]:
    return {
        "entity_id": contract_id(entity_type, (entity_type, value.strip().lower())),
        "canonical_name": value,
        "ontology_id": None,
        "resolution_method": "not_applicable",
    }


def _counted_strings(value: Any) -> Counter[str]:
    return Counter(_strings(value))


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _text(item)
        if text:
            out.append(text)
    return out


def _indicator_dicts(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _malware_family_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            name = _text(item.get("display_name")) or _text(item.get("name"))
        else:
            name = _text(item)
        if name:
            names.append(name)
    return names


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_segment(value: str) -> str:
    out = "".join("-" if char in _UNSAFE_PATH else char for char in value)
    return out.strip().strip(".") or "_"
