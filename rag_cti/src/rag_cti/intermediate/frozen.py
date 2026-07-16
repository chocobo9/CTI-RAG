"""Post-collection processing for the frozen APT reverse-enrichment dataset.

This module is deliberately read-only with respect to source collection.  Its
public seam accepts a repository root and an output directory, then adapts the
already persisted OTX, CIRCL MISP and Malpedia views into one graph-ready
intermediate package.  Source claims are kept as claims; resolution only adds
canonical and candidate identities.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag_cti.intermediate.contract import contract_id

_SCHEMA_VERSION = "v1.0"
_SOURCE_CLASS = {
    "otx": "weakly_labeled_narrative",
    "circl_misp": "weakly_labeled_narrative",
    "malpedia": "ontology",
}
_PUBLISHER_CATEGORY = {
    "otx": "threat_intelligence_platform",
    "circl_misp": "community",
    "malpedia": "knowledge_base",
}
_INDICATOR_TYPES = {
    "domain": "domain",
    "hostname": "domain",
    "url": "url",
    "uri": "url",
    "ip-src": "ip",
    "ip-dst": "ip",
    "ipv4": "ip",
    "ipv6": "ip",
    "md5": "file_hash",
    "sha1": "file_hash",
    "sha224": "file_hash",
    "sha256": "file_hash",
    "sha384": "file_hash",
    "sha512": "file_hash",
    "filename|md5": "file_hash",
    "filename|sha1": "file_hash",
    "filename|sha256": "file_hash",
    "malware-sample": "file_hash",
    "email-src": "email",
    "email-dst": "email",
    "target-location": "location",
    "campaign-name": "campaign",
    "campaign-id": "campaign",
    "threat-actor": "actor",
    "vulnerability": "cve",
}
_ACTOR_GALAXY_TYPES = {"threat-actor", "mitre-intrusion-set"}
_UNRESOLVED = {"ambiguous", "candidate", "unresolved"}


@dataclass
class FrozenBuildResult:
    """Summary returned after a frozen package is written."""

    output_dir: Path
    counts: Counter[str] = field(default_factory=Counter)
    warnings: list[str] = field(default_factory=list)


class _JsonlWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open("w", encoding="utf-8")

    def write(self, row: Mapping[str, Any]) -> None:
        payload = json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        self.handle.write(payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
        self.handle.write("\n")

    def close(self) -> None:
        self.handle.close()


@dataclass
class _Artifacts:
    records: _JsonlWriter
    entities: _JsonlWriter
    relations: _JsonlWriter
    signals: _JsonlWriter
    claims: _JsonlWriter
    aliases: _JsonlWriter
    features: _JsonlWriter

    def close(self) -> None:
        for writer in self.__dict__.values():
            writer.close()


class AliasRegistry:
    """Exact, source-backed alias resolver that preserves collisions."""

    def __init__(self) -> None:
        self._names: dict[str, list[dict[str, str]]] = defaultdict(list)

    def add(
        self,
        *,
        entity_id: str,
        entity_type: str,
        canonical_name: str,
        aliases: Iterable[str] = (),
        source: str,
    ) -> None:
        values = [canonical_name, *aliases]
        for value in values:
            key = _normal_key(value)
            if not key:
                continue
            candidate = {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "canonical_name": canonical_name,
                "source": source,
                "alias_value": value,
            }
            if candidate not in self._names[key]:
                self._names[key].append(candidate)

    def resolve(self, raw_value: str, *, entity_type: str | None = None) -> dict[str, Any]:
        candidates = self._names.get(_normal_key(raw_value), [])
        if entity_type:
            typed = [item for item in candidates if item["entity_type"] == entity_type]
            candidates = typed or candidates
        candidates = sorted(candidates, key=lambda item: (item["entity_id"], item["source"]))
        if len(candidates) == 1:
            item = candidates[0]
            return {
                "entity_id": item["entity_id"],
                "canonical_name": item["canonical_name"],
                "ontology_id": _ontology_id(item["entity_id"]),
                "resolution_method": "exact_alias" if _normal_key(raw_value) != _normal_key(item["canonical_name"]) else "exact_name",
                "candidate_entity_ids": [item["entity_id"]],
                "status": "resolved",
            }
        if candidates:
            return {
                "entity_id": None,
                "canonical_name": None,
                "ontology_id": None,
                "resolution_method": "unresolved",
                "candidate_entity_ids": [item["entity_id"] for item in candidates],
                "status": "ambiguous",
            }
        return {
            "entity_id": None,
            "canonical_name": None,
            "ontology_id": None,
            "resolution_method": "unresolved",
            "candidate_entity_ids": [],
            "status": "unresolved",
        }

    def mappings(self) -> Iterator[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        for key, candidates in sorted(self._names.items()):
            for candidate in candidates:
                marker = (key, candidate["entity_id"])
                if marker in seen:
                    continue
                seen.add(marker)
                yield {
                    "alias_key": key,
                    "alias_value": candidate["alias_value"],
                    "canonical_name": candidate["canonical_name"],
                    "entity_id": candidate["entity_id"],
                    "entity_type": candidate["entity_type"],
                    "source": candidate["source"],
                    "mapping_status": "candidate" if len(candidates) > 1 else "resolved",
                    "candidate_entity_ids": [item["entity_id"] for item in candidates],
                }


def build_frozen_intermediate_package(
    *,
    repository_root: Path,
    output_dir: Path,
    dataset_id: str = "cti_rag_frozen_reverse_enrichment",
    dataset_version: str = "2026-07-12-v1",
    generated_at: str | None = None,
    temporal_cutoff: str | None = None,
) -> FrozenBuildResult:
    """Build the unified post-collection package from local frozen inputs.

    The interface is intentionally small.  ``repository_root`` must contain
    ``data/processed/otx_actor_event_dataset_routeA_20260712``,
    ``data/raw/circl_misp`` and ``data/raw/malpedia``.  No network client is
    created and no source file is modified.  ``temporal_cutoff`` is optional;
    when omitted, records receive ``unassigned`` split metadata.
    """
    root = Path(repository_root)
    output = Path(output_dir)
    generated = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    output.mkdir(parents=True, exist_ok=True)
    intermediate = output / "intermediate"
    artifacts = _Artifacts(
        records=_JsonlWriter(intermediate / "intermediate_records.jsonl"),
        entities=_JsonlWriter(intermediate / "entity_mentions.jsonl"),
        relations=_JsonlWriter(intermediate / "relation_mentions.jsonl"),
        signals=_JsonlWriter(intermediate / "attribution_signals.jsonl"),
        claims=_JsonlWriter(intermediate / "attribution_claims.jsonl"),
        aliases=_JsonlWriter(intermediate / "alias_mappings.jsonl"),
        features=_JsonlWriter(intermediate / "record_features.jsonl"),
    )
    result = FrozenBuildResult(output_dir=output)
    registry = _build_alias_registry(root)
    for mapping in registry.mappings():
        artifacts.aliases.write(mapping)
        result.counts["alias_mappings"] += 1

    try:
        _process_otx(root, artifacts, registry, result, temporal_cutoff)
        _process_misp(root, artifacts, registry, result, temporal_cutoff)
        _process_malpedia(root, artifacts, registry, result, temporal_cutoff)
    finally:
        artifacts.close()

    _write_projection(output, root, dataset_version)
    _write_metadata(
        output,
        root=root,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        generated_at=generated,
        result=result,
        temporal_cutoff=temporal_cutoff,
    )
    return result


def _build_alias_registry(root: Path) -> AliasRegistry:
    registry = AliasRegistry()
    mitre_path = root / "data" / "raw" / "mitre" / "enterprise-attack.json"
    if mitre_path.is_file():
        bundle = _read_json(mitre_path)
        for raw in bundle.get("objects", []):
            entity = _mitre_entity(raw)
            if entity:
                registry.add(**entity)

    actors_path = root / "data" / "raw" / "malpedia" / "normalized" / "actors.jsonl"
    for raw in _read_jsonl(actors_path):
        name = _text(raw.get("primary_name"))
        if name:
            registry.add(
                entity_id=_text(raw.get("actor_id")),
                entity_type="actor",
                canonical_name=name,
                aliases=_strings(raw.get("aliases_raw")),
                source="malpedia",
            )
    families_path = root / "data" / "raw" / "malpedia" / "normalized" / "families.jsonl"
    for raw in _read_jsonl(families_path):
        name = _text(raw.get("primary_name"))
        if name:
            registry.add(
                entity_id=_text(raw.get("family_id")),
                entity_type="family",
                canonical_name=name,
                aliases=_strings(raw.get("aliases_raw")),
                source="malpedia",
            )
    return registry


def _process_otx(
    root: Path,
    artifacts: _Artifacts,
    registry: AliasRegistry,
    result: FrozenBuildResult,
    temporal_cutoff: str | None,
) -> None:
    base = root / "data" / "processed" / "otx_actor_event_dataset_routeA_20260712"
    claims_by_event = _group_by(_read_jsonl(base / "source_attribution_claims.jsonl"), "event_id")
    summaries = {row.get("event_id"): row for row in _read_jsonl(base / "event_indicator_summaries.jsonl")}
    for event in _read_jsonl(base / "events.jsonl"):
        event_id = _text(event.get("event_id"))
        record_id = f"record_otx_{_safe(event.get('source_record_id') or event_id)}"
        raw = _load_otx_raw(root, event.get("raw_provenance", {}).get("raw_path"))
        entities: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []
        signals: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        event_mention = _mention(record_id, event_id, "event", "event_id", "source_field", "not_applicable")
        entities.append(event_mention)
        for claim in claims_by_event.get(event_id, []):
            raw_label = _text(claim.get("raw_label") or claim.get("raw_field_value"))
            if not raw_label:
                continue
            resolution = _claim_resolution(claim, registry, raw_label, "actor")
            actor = _mention(record_id, raw_label, "actor", "adversary", "source_field", resolution)
            entities.append(actor)
            claim_row = _attribution_claim(
                source="otx",
                record_id=record_id,
                event_id=event_id,
                raw_label=raw_label,
                resolution=resolution,
                source_claim=claim,
                label_availability="direct",
            )
            claims.append(claim_row)
            signals.append(_signal(claim_row, "weak_direct_attribution", "source_attribution_claims.jsonl"))
            relations.append(_relation(record_id, event_mention, "attributed-to", actor, "source_field", "direct"))

        for attack_id in _strings(raw.get("attack_ids")):
            target = _mention(record_id, attack_id, "technique", "attack_ids[]", "source_field", _resolved_id(f"technique_{attack_id}", attack_id, "exact_id", attack_id))
            entities.append(target)
            relations.append(_relation(record_id, event_mention, "uses", target, "structured_cooccurrence", "none"))
        for family in _malware_names(raw.get("malware_families")):
            target = _mention(record_id, family, "family", "malware_families[]", "source_field", registry.resolve(family, entity_type="family"))
            entities.append(target)
            relations.append(_relation(record_id, event_mention, "uses", target, "structured_cooccurrence", "none"))
        for country in _strings(raw.get("targeted_countries")):
            target = _mention(record_id, country, "location", "targeted_countries[]", "source_field", _unresolved_resolution("location", country))
            entities.append(target)
            relations.append(_relation(record_id, event_mention, "targets", target, "structured_cooccurrence", "none"))

        summary = summaries.get(event_id, {})
        record = _record(
            record_id=record_id,
            source="otx",
            source_record_id=event.get("source_record_id") or event_id,
            raw_ref={"connector_source": "otx", "source_id": event.get("source_record_id") or event_id, **dict(event.get("raw_provenance", {}))},
            timestamps={"published_at": _first(raw.get("created"), raw.get("modified")), "modified_at": raw.get("modified"), "fetched_at": event.get("raw_provenance", {}).get("fetched_at")},
            entities=entities,
            relations=relations,
            claims=claims,
            tags=_strings(raw.get("tags")),
            references=_strings(raw.get("references")),
            indicators={"materialization": "summary_only", "occurrence_count": summary.get("indicator_count", 0), "type_counts": summary.get("type_counts", {})},
            ambiguity=_ambiguity(entities, claims),
            discovery_provenance={"actor_label_status": event.get("actor_label_status"), "candidate_actor_ids": event.get("candidate_actor_ids", [])},
            temporal_cutoff=temporal_cutoff,
        )
        _write_rows(artifacts, result, record, entities, relations, signals, claims)


def _process_misp(
    root: Path,
    artifacts: _Artifacts,
    registry: AliasRegistry,
    result: FrozenBuildResult,
    temporal_cutoff: str | None,
) -> None:
    base = root / "data" / "raw" / "circl_misp"
    events = {row.get("event_id"): row for row in _read_jsonl(base / "normalized" / "events.jsonl")}
    claims_by_event = _group_by(_read_jsonl(base / "normalized" / "source_actor_claims.jsonl"), "event_id")
    raw_dir = base / "raw" / "events"
    for event_id, event in events.items():
        if not event_id:
            continue
        record_id = f"record_circl_misp_{_safe(event_id)}"
        raw = _read_json(raw_dir / f"{_text(event.get('source_uuid'))}.json") if event.get("source_uuid") else {}
        entities: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []
        signals: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        event_mention = _mention(record_id, event_id, "event", "event_id", "source_field", "not_applicable")
        entities.append(event_mention)
        tags = [_tag_name(tag) for tag in event.get("tags_raw", [])]
        for tag in filter(None, tags):
            entities.append(_mention(record_id, tag, "tag", "Event.Tag[].name", "source_field", "not_applicable"))
        for claim in claims_by_event.get(event_id, []):
            raw_label = _text(claim.get("raw_label"))
            if not raw_label:
                continue
            is_actor_context = claim.get("claim_kind") == "galaxy_actor_context" or claim.get("raw_galaxy_type") in _ACTOR_GALAXY_TYPES
            resolution = _claim_resolution(claim, registry, raw_label, "actor")
            actor = _mention(record_id, raw_label, "actor", claim.get("source_field", "Event.Tag[].name"), "source_field", resolution)
            entities.append(actor)
            claim_row = _attribution_claim(
                source="circl_misp",
                record_id=record_id,
                event_id=event_id,
                raw_label=raw_label,
                resolution=resolution,
                source_claim=claim,
                label_availability="direct" if is_actor_context else "indirect",
            )
            claims.append(claim_row)
            signals.append(_signal(claim_row, "direct_attribution" if is_actor_context else "supporting_evidence", "source_actor_claims.jsonl"))
            if is_actor_context:
                relations.append(_relation(record_id, event_mention, "attributed-to", actor, "source_field", claim_row["label_availability"]))

        for attribute in _misp_attributes(raw):
            value = _text(attribute.get("value"))
            attr_type = _text(attribute.get("type"))
            entity_type = _INDICATOR_TYPES.get(attr_type, "indicator")
            target = _mention(record_id, value, entity_type, f"Event.Attribute[{attr_type}]", "source_field", "not_applicable", value_type=attr_type)
            entities.append(target)
            relations.append(_relation(record_id, event_mention, "has-indicator", target, "structured_relation", "none"))

        record = _record(
            record_id=record_id,
            source="circl_misp",
            source_record_id=event.get("source_uuid") or event_id,
            raw_ref={"connector_source": "circl_misp", "source_id": event.get("source_uuid") or event_id, "raw_store_root": "data/raw/circl_misp", "raw_path": event.get("raw_ref"), "raw_sha256": event.get("raw_sha256"), "fetched_at": event.get("fetched_at")},
            timestamps={"published_at": event.get("published_at"), "modified_at": event.get("modified_at"), "observed_first": None, "observed_last": None, "fetched_at": event.get("fetched_at")},
            entities=entities,
            relations=relations,
            claims=claims,
            tags=tags,
            references=[],
            indicators={"materialization": "attribute_level", "attribute_count": event.get("attribute_count", 0), "object_count": event.get("object_count", 0)},
            ambiguity=_ambiguity(entities, claims),
            discovery_provenance={"discovery_method": "circl_misp_feed_enumeration"},
            temporal_cutoff=temporal_cutoff,
        )
        _write_rows(artifacts, result, record, entities, relations, signals, claims)


def _process_malpedia(
    root: Path,
    artifacts: _Artifacts,
    registry: AliasRegistry,
    result: FrozenBuildResult,
    temporal_cutoff: str | None,
) -> None:
    base = root / "data" / "raw" / "malpedia" / "normalized"
    actors = list(_read_jsonl(base / "actors.jsonl"))
    families = list(_read_jsonl(base / "families.jsonl"))
    for raw, entity_type, name_key, id_key in [
        *[(row, "actor", "primary_name", "actor_id") for row in actors],
        *[(row, "family", "primary_name", "family_id") for row in families],
    ]:
        name = _text(raw.get(name_key))
        entity_id = _text(raw.get(id_key))
        if not name or not entity_id:
            continue
        record_id = f"record_malpedia_{_safe(entity_id)}"
        primary = _mention(record_id, name, entity_type, name_key, "source_field", _resolved_id(entity_id, name, "exact_id", entity_id))
        entities = [primary]
        aliases = _strings(raw.get("aliases_raw"))
        for alias in aliases:
            entities.append(_mention(record_id, alias, entity_type, "aliases_raw[]", "source_field", _resolved_id(entity_id, name, "exact_alias", entity_id)))
        references = _strings(raw.get("references_raw"))
        for reference in references:
            entities.append(_mention(record_id, reference, "external_reference", "references_raw[]", "source_field", "not_applicable"))
        relations: list[dict[str, Any]] = []
        record = _record(
            record_id=record_id,
            source="malpedia",
            source_record_id=entity_id,
            raw_ref={"connector_source": "malpedia", "source_id": entity_id, "raw_store_root": "data/raw/malpedia", "raw_path": raw.get("raw_ref"), "fetched_at": raw.get("fetched_at")},
            timestamps={"published_at": None, "modified_at": raw.get("updated"), "fetched_at": raw.get("fetched_at")},
            entities=entities,
            relations=relations,
            claims=[],
            tags=[],
            references=references,
            indicators={},
            ambiguity=False,
            discovery_provenance={"taxonomy_record": True},
            temporal_cutoff=temporal_cutoff,
        )
        _write_rows(artifacts, result, record, entities, relations, [], [])

    links_path = base / "actor_family_links.jsonl"
    for link in _read_jsonl(links_path):
        actor_id = _text(link.get("actor_id"))
        family_id = _text(link.get("family_id"))
        if not actor_id or not family_id:
            continue
        record_id = f"record_{_safe(link.get('link_id') or contract_id('malpedia_link', [actor_id, family_id]))}"
        actor = _mention(record_id, _text(link.get("actor_source_id_raw")) or actor_id, "actor", "actor_source_id_raw", "source_field", _resolved_id(actor_id, actor_id, "exact_id", actor_id))
        family = _mention(record_id, _text(link.get("family_source_id_raw")) or family_id, "family", "family_source_id_raw", "source_field", _resolved_id(family_id, family_id, "exact_id", family_id))
        relation = _relation(record_id, actor, "associated-with", family, "structured_relation", "none")
        record = _record(
            record_id=record_id,
            source="malpedia",
            source_record_id=link.get("link_id") or record_id,
            raw_ref={"connector_source": "malpedia", "source_id": link.get("link_id") or record_id, "raw_store_root": "data/raw/malpedia", "raw_path": link.get("raw_ref")},
            timestamps={"published_at": None, "modified_at": None, "fetched_at": None},
            entities=[actor, family],
            relations=[relation],
            claims=[],
            tags=[],
            references=[],
            indicators={},
            ambiguity=False,
            discovery_provenance={"taxonomy_link": True},
            temporal_cutoff=temporal_cutoff,
        )
        _write_rows(artifacts, result, record, [actor, family], [relation], [], [])


def _record(
    *,
    record_id: str,
    source: str,
    source_record_id: str,
    raw_ref: Mapping[str, Any],
    timestamps: Mapping[str, Any],
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    tags: list[str],
    references: list[str],
    indicators: Mapping[str, Any],
    ambiguity: bool,
    discovery_provenance: Mapping[str, Any],
    temporal_cutoff: str | None,
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "record_kind": "source_record",
        "source": {
            "connector_source": source,
            "source_name": {"otx": "AlienVault OTX", "circl_misp": "CIRCL MISP OSINT", "malpedia": "Malpedia"}[source],
            "source_record_id": source_record_id,
            "source_class": _SOURCE_CLASS[source],
            "publisher_category": _PUBLISHER_CATEGORY[source],
        },
        "raw_ref": dict(raw_ref),
        "timestamps": {**dict(timestamps), "timestamp_basis": _timestamp_basis(timestamps)},
        "matched_actors": [
            {
                "raw_label": claim["raw_label"],
                "entity_id": claim.get("resolved_entity_id"),
                "candidate_entity_ids": claim.get("candidate_entity_ids", []),
                "resolution_status": claim.get("resolution_status"),
            }
            for claim in claims
        ],
        "aliases": [],
        "tags": tags,
        "references": references,
        "indicators": dict(indicators),
        "attribution_claims": claims,
        "extracted_entities": [mention["entity_mention_id"] for mention in entities],
        "candidate_relationships": [relation["relation_mention_id"] for relation in relations],
        "discovery_provenance": dict(discovery_provenance),
        "record_signals": {
            "label_availability": _record_label_availability(claims),
            "ambiguity_flag": ambiguity,
            "multi_actor_flag": len({claim.get("resolved_entity_id") or f"raw:{claim['raw_label']}" for claim in claims}) > 1,
            "has_attribution_confidence": False,
        },
        "counts": {
            "entity_mentions": len(entities),
            "relation_mentions": len(relations),
            "attribution_claims": len(claims),
            "tag_count": len(tags),
            "reference_count": len(references),
        },
        "temporal_split": _split_value(timestamps, temporal_cutoff),
        "processing_status": {"status": "ok", "warnings": []},
    }


def _write_rows(
    artifacts: _Artifacts,
    result: FrozenBuildResult,
    record: Mapping[str, Any],
    entities: Iterable[Mapping[str, Any]],
    relations: Iterable[Mapping[str, Any]],
    signals: Iterable[Mapping[str, Any]],
    claims: Iterable[Mapping[str, Any]],
) -> None:
    artifacts.records.write(record)
    result.counts["intermediate_records"] += 1
    source = record.get("source", {}).get("connector_source", "unknown")
    result.counts[f"{source}_records"] += 1
    for row, writer, key in [
        *[(item, artifacts.entities, "entity_mentions") for item in entities],
        *[(item, artifacts.relations, "relation_mentions") for item in relations],
        *[(item, artifacts.signals, "attribution_signals") for item in signals],
        *[(item, artifacts.claims, "attribution_claims") for item in claims],
    ]:
        writer.write(row)
        result.counts[key] += 1
    feature = _features(record)
    artifacts.features.write(feature)
    result.counts["record_features"] += 1


def _features(record: Mapping[str, Any]) -> dict[str, Any]:
    signals = record.get("record_signals", {})
    counts = record.get("counts", {})
    return {
        "record_id": record["record_id"],
        "source_features": record["source"],
        "timestamp_features": {
            "timestamp_basis": record["timestamps"].get("timestamp_basis"),
            "has_published_at": bool(record["timestamps"].get("published_at")),
            "has_modified_at": bool(record["timestamps"].get("modified_at")),
            "has_observed_range": bool(record["timestamps"].get("observed_first") or record["timestamps"].get("observed_last")),
            "temporal_split": record.get("temporal_split"),
        },
        "content_features": {
            "indicator_count": record.get("indicators", {}).get("attribute_count", record.get("indicators", {}).get("occurrence_count", 0)),
            "object_count": record.get("indicators", {}).get("object_count", 0),
            "tag_count": counts.get("tag_count", 0),
            "reference_count": counts.get("reference_count", 0),
        },
        "label_features": {
            "label_availability": signals.get("label_availability"),
            "has_confidence": False,
            "supporting_sources_count": None,
            "conflicting_sources_count": None,
        },
        "ambiguity_features": {
            "ambiguity_flag": signals.get("ambiguity_flag", False),
            "multi_actor_flag": signals.get("multi_actor_flag", False),
        },
    }


def _write_metadata(
    output: Path,
    *,
    root: Path,
    dataset_id: str,
    dataset_version: str,
    generated_at: str,
    result: FrozenBuildResult,
    temporal_cutoff: str | None,
) -> None:
    intermediate = output / "intermediate"
    source_manifest = {
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "schema_version": _SCHEMA_VERSION,
        "generated_at": generated_at,
        "collection_frozen_at": "2026-07-12",
        "post_collection_only": True,
        "sources": [
            {"connector_source": "circl_misp", "source_class": _SOURCE_CLASS["circl_misp"], "publisher_category": _PUBLISHER_CATEGORY["circl_misp"], "raw_collection": "data/raw/circl_misp", "record_count": result.counts.get("circl_misp_records", 0), "provides": {"labels": True, "indicators": True, "aliases": False, "enrichment": False}},
            {"connector_source": "malpedia", "source_class": _SOURCE_CLASS["malpedia"], "publisher_category": _PUBLISHER_CATEGORY["malpedia"], "raw_collection": "data/raw/malpedia", "record_count": result.counts.get("malpedia_records", 0), "provides": {"labels": False, "indicators": False, "aliases": True, "enrichment": False}},
            {"connector_source": "otx", "source_class": _SOURCE_CLASS["otx"], "publisher_category": _PUBLISHER_CATEGORY["otx"], "raw_collection": "data/raw/otx", "record_count": result.counts.get("otx_records", 0), "provides": {"labels": True, "indicators": True, "aliases": False, "enrichment": False}},
        ],
        "reference_sources": [{"connector_source": "mitre", "raw_collection": "data/raw/mitre/enterprise-attack.json", "role": "apt_seed_and_alias_ontology"}],
        "input_root": str(root),
    }
    _write_json(intermediate / "source_manifest.json", source_manifest)
    entity_counts: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    claim_counts: Counter[str] = Counter()
    for row in _read_jsonl(intermediate / "entity_mentions.jsonl"):
        entity_counts[_text(row.get("entity_type")) or "unknown"] += 1
    for row in _read_jsonl(intermediate / "relation_mentions.jsonl"):
        relation_counts[_text(row.get("predicate", {}).get("mapped_value")) or "unknown"] += 1
    for row in _read_jsonl(intermediate / "attribution_claims.jsonl"):
        claim_counts[_text(row.get("resolution_status")) or "unknown"] += 1
    _write_json(intermediate / "entity_inventory.json", {"entity_mentions": sum(entity_counts.values()), "by_type": dict(sorted(entity_counts.items()))})
    _write_json(intermediate / "relation_inventory.json", {"relation_mentions": sum(relation_counts.values()), "by_predicate": dict(sorted(relation_counts.items()))})
    _write_json(intermediate / "temporal_split.json", {"policy": "source publication/modified time; missing remains unassigned", "cutoff": temporal_cutoff, "assignment": "train_before_cutoff_test_on_or_after_cutoff" if temporal_cutoff else "unassigned_until_cutoff_is_selected"})
    _write_json(intermediate / "processing_report.json", {"dataset_id": dataset_id, "dataset_version": dataset_version, "schema_version": _SCHEMA_VERSION, "generated_at": generated_at, "counts": dict(result.counts), "coverage": {"entity_types": dict(entity_counts), "relation_predicates": dict(relation_counts), "claim_resolution_status": dict(claim_counts)}, "warnings": result.warnings, "open_issues": ["supporting and conflicting source counts are deferred to data fusion", "OTX indicators remain summary-only in this Stage 1 materialization"]})


def _write_projection(output: Path, root: Path, dataset_version: str) -> None:
    neo4j = output / "neo4j"
    nodes = _JsonlWriter(neo4j / "nodes.jsonl")
    relationships = _JsonlWriter(neo4j / "relationships.jsonl")
    try:
        seen_nodes: set[str] = set()
        for mention in _read_jsonl(output / "intermediate" / "entity_mentions.jsonl"):
            entity_id = mention.get("resolution", {}).get("entity_id") or mention.get("entity_mention_id")
            if entity_id in seen_nodes:
                continue
            seen_nodes.add(entity_id)
            nodes.write({"id": entity_id, "entity_type": mention.get("entity_type"), "canonical_name": mention.get("resolution", {}).get("canonical_name") or mention.get("normalized_value"), "raw_value": mention.get("raw_value"), "source_record_id": mention.get("record_id"), "dataset_version": dataset_version})
        for relation in _read_jsonl(output / "intermediate" / "relation_mentions.jsonl"):
            relationships.write({"id": relation.get("relation_mention_id"), "source": relation.get("subject", {}).get("entity_mention_id"), "target": relation.get("object", {}).get("entity_mention_id"), "predicate": relation.get("predicate", {}).get("mapped_value"), "record_id": relation.get("record_id"), "dataset_version": dataset_version})
    finally:
        nodes.close()
        relationships.close()


def _attribution_claim(*, source: str, record_id: str, event_id: str, raw_label: str, resolution: Mapping[str, Any], source_claim: Mapping[str, Any], label_availability: str) -> dict[str, Any]:
    return {"attribution_claim_id": contract_id("claim", [source, event_id, raw_label, source_claim.get("claim_id")]), "record_id": record_id, "event_id": event_id, "source": source, "raw_label": raw_label, "label_availability": label_availability, "resolved_entity_id": resolution.get("entity_id"), "candidate_entity_ids": resolution.get("candidate_entity_ids", []), "resolution_status": source_claim.get("resolution_status") or source_claim.get("parse_status") or resolution.get("status"), "source_claim_ref": source_claim.get("claim_id"), "source_field": source_claim.get("source_field"), "notes": source_claim.get("notes", [])}


def _signal(claim: Mapping[str, Any], signal_type: str, source_field: str) -> dict[str, Any]:
    return {"attribution_signal_id": contract_id("signal", [claim.get("attribution_claim_id"), signal_type]), "record_id": claim["record_id"], "signal_type": signal_type, "target_entity_type": "actor", "raw_label": claim["raw_label"], "source_field": source_field, "derivation_method": "source_field", "source_provided_confidence": None, "label_availability": claim["label_availability"], "resolved_entity_id": claim.get("resolved_entity_id"), "candidate_entity_ids": claim.get("candidate_entity_ids", [])}


def _relation(record_id: str, subject: Mapping[str, Any], predicate: str, object_: Mapping[str, Any], method: str, label_availability: str) -> dict[str, Any]:
    return {"relation_mention_id": contract_id("relation", [record_id, subject.get("entity_mention_id"), predicate, object_.get("entity_mention_id")]), "record_id": record_id, "subject": {"entity_mention_id": subject["entity_mention_id"], "entity_type": subject["entity_type"], "raw_value": subject["raw_value"]}, "predicate": {"raw_value": predicate, "mapped_value": predicate, "mapping_status": "mapped"}, "object": {"entity_mention_id": object_["entity_mention_id"], "entity_type": object_["entity_type"], "raw_value": object_["raw_value"]}, "derivation": {"extraction_method": method, "label_availability": label_availability, "evidence_type": "source_record"}, "ambiguity": {"status": "ambiguous" if object_.get("ambiguity", {}).get("status") in _UNRESOLVED else "unambiguous", "notes": []}}


def _mention(record_id: str, raw_value: str, entity_type: str, source_field: str, extraction_method: str, resolution: Any, *, value_type: str | None = None) -> dict[str, Any]:
    resolved = _resolution_dict(resolution, entity_type, raw_value)
    return {"entity_mention_id": contract_id("mention", [record_id, entity_type, source_field, raw_value]), "record_id": record_id, "raw_value": raw_value, "normalized_value": raw_value.strip(), "entity_type": entity_type, "source_field": source_field, "extraction_method": extraction_method, "occurrence_count": 1, "value_type": {"canonical": value_type, "raw": value_type}, "resolution": {"entity_id": resolved.get("entity_id"), "canonical_name": resolved.get("canonical_name"), "ontology_id": resolved.get("ontology_id"), "resolution_method": resolved.get("resolution_method")}, "ambiguity": {"status": resolved.get("status", "not_applicable"), "candidate_entity_ids": resolved.get("candidate_entity_ids", []), "reason": "multiple_exact_alias_matches" if resolved.get("status") == "ambiguous" else None}, "merge_candidates": resolved.get("candidate_entity_ids", [])}


def _claim_resolution(claim: Mapping[str, Any], registry: AliasRegistry, raw_label: str, entity_type: str) -> dict[str, Any]:
    existing = _strings(claim.get("resolved_actor_ids"))
    if len(existing) == 1:
        return _resolved_id(existing[0], raw_label, "embedded_id", existing[0])
    if len(existing) > 1:
        return {"entity_id": None, "canonical_name": None, "ontology_id": None, "resolution_method": "unresolved", "candidate_entity_ids": existing, "status": "ambiguous"}
    resolved = registry.resolve(raw_label, entity_type=entity_type)
    if claim.get("resolution_status") in {"ambiguous", "ambiguous_taxonomy", "parse_ambiguous"}:
        resolved["status"] = "ambiguous"
    return resolved


def _resolution_dict(value: Any, entity_type: str, raw_value: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value == "not_applicable":
        return {"status": "not_applicable", "resolution_method": "not_applicable", "candidate_entity_ids": []}
    return _unresolved_resolution(entity_type, raw_value)


def _resolved_id(entity_id: str, canonical_name: str, method: str, ontology_id: str | None) -> dict[str, Any]:
    return {"entity_id": entity_id, "canonical_name": canonical_name, "ontology_id": ontology_id, "resolution_method": method, "candidate_entity_ids": [entity_id], "status": "resolved"}


def _unresolved_resolution(entity_type: str, raw_value: str) -> dict[str, Any]:
    return {"entity_id": None, "canonical_name": None, "ontology_id": None, "resolution_method": "unresolved", "candidate_entity_ids": [], "status": "unresolved"}


def _ambiguity(entities: Iterable[Mapping[str, Any]], claims: Iterable[Mapping[str, Any]]) -> bool:
    return any(entity.get("ambiguity", {}).get("status") in _UNRESOLVED for entity in entities) or any(_is_ambiguous_status(claim.get("resolution_status")) for claim in claims)


def _is_ambiguous_status(value: Any) -> bool:
    status = _text(value).casefold()
    return status in _UNRESOLVED or "ambiguous" in status or "unresolved" in status or "unmapped" in status


def _record_label_availability(claims: Iterable[Mapping[str, Any]]) -> str:
    values = {_text(claim.get("label_availability")) for claim in claims}
    if "direct" in values:
        return "direct"
    if "indirect" in values:
        return "indirect"
    return "none"


def _timestamp_basis(timestamps: Mapping[str, Any]) -> str:
    if timestamps.get("published_at"):
        return "published"
    if timestamps.get("modified_at"):
        return "source_modified"
    if timestamps.get("observed_first") or timestamps.get("observed_last"):
        return "observed_range"
    if timestamps.get("fetched_at"):
        return "fetched_only"
    return "missing"


def _split_value(timestamps: Mapping[str, Any], cutoff: str | None) -> str:
    if not cutoff:
        return "unassigned"
    value = _first(timestamps.get("published_at"), timestamps.get("modified_at"), timestamps.get("fetched_at"))
    if not value:
        return "unassigned"
    return "train" if value < cutoff else "test"


def _mitre_entity(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    type_map = {"intrusion-set": "actor", "campaign": "campaign", "malware": "family", "tool": "tool", "attack-pattern": "technique", "course-of-action": "mitigation", "x-mitre-detection-strategy": "detection-strategy"}
    entity_type = type_map.get(_text(raw.get("type")))
    name = _text(raw.get("name"))
    entity_id = _text(raw.get("id"))
    if not entity_type or not name or not entity_id:
        return None
    external_ids = [_text(item.get("external_id")) for item in raw.get("external_references", []) if isinstance(item, Mapping)]
    aliases = _strings(raw.get("aliases") or raw.get("x_mitre_aliases")) + [item for item in external_ids if item]
    stable_id = next((value for value in external_ids if value), None)
    prefix = {"actor": "actor", "campaign": "campaign", "family": "family", "tool": "tool", "technique": "technique"}.get(entity_type, entity_type)
    canonical_id = f"{prefix}_{stable_id}" if stable_id else entity_id.replace("--", "_")
    return {"entity_id": canonical_id, "entity_type": entity_type, "canonical_name": name, "aliases": aliases, "source": "mitre"}


def _misp_attributes(raw: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    event = raw.get("Event") if isinstance(raw.get("Event"), Mapping) else raw
    for attribute in event.get("Attribute", []) if isinstance(event, Mapping) else []:
        if isinstance(attribute, Mapping) and not attribute.get("deleted"):
            yield attribute
    if isinstance(event, Mapping):
        for obj in event.get("Object", []) or []:
            if not isinstance(obj, Mapping) or obj.get("deleted"):
                continue
            for attribute in obj.get("Attribute", []) or []:
                if isinstance(attribute, Mapping) and not attribute.get("deleted"):
                    yield attribute


def _load_otx_raw(root: Path, raw_path: Any) -> dict[str, Any]:
    if not raw_path:
        return {}
    path = _resolve_path(root, _text(raw_path))
    if not path.is_file():
        return {}
    payload = _read_json(path)
    return payload.get("payload", payload) if isinstance(payload, Mapping) else {}


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    candidates = [path if path.is_absolute() else root / path, root / "data" / path]
    if value.startswith("raw/"):
        candidates.extend([root / "data" / "raw" / "circl_misp" / path, root / "data" / "raw" / "malpedia" / path])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def _group_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = _text(row.get(key))
        if value:
            grouped[value].append(dict(row))
    return grouped


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _malware_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return _strings(value)
    names: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            name = _text(item.get("display_name") or item.get("name"))
            if name:
                names.append(name)
        elif isinstance(item, str) and item.strip():
            names.append(item.strip())
    return names


def _tag_name(value: Any) -> str:
    if isinstance(value, Mapping):
        return _text(value.get("name"))
    return _text(value)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _first(*values: Any) -> str | None:
    for value in values:
        text = _text(value)
        if text:
            return text
    return None


def _normal_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _text(value).casefold())


def _ontology_id(entity_id: str) -> str | None:
    match = re.search(r"\b([GSCM]\d{4}(?:\.\d{3})?)\b", entity_id)
    return match.group(1) if match else None


def _safe(value: Any) -> str:
    text = _text(value) or "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
