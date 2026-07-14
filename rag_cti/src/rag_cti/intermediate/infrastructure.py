"""pDNS and VirusTotal raw records to intermediate infrastructure artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rag_cti.connectors.pdns_projection import project_pdns_raw
from rag_cti.connectors.vt_projection import project_vt_infra
from rag_cti.intermediate.contract import contract_id
from rag_cti.intermediate.jsonl import write_jsonl

_SCHEMA_VERSION = "v0.1"
_SOURCE_CLASS = "infrastructure"
_UNSAFE_PATH = '<>:"/\\|?*'

_SOURCE_METADATA = {
    "pdns": {
        "publisher_category": "unknown",
        "source_name": "Passive DNS",
        "raw_collection": "raw/pdns",
    },
    "vt": {
        "publisher_category": "vendor",
        "source_name": "VirusTotal",
        "raw_collection": "raw/vt",
    },
}


@dataclass(frozen=True)
class InfrastructureRawRef:
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
class InfrastructureRows:
    intermediate_records: list[dict[str, Any]]
    entity_mentions: list[dict[str, Any]]
    relation_mentions: list[dict[str, Any]]
    attribution_signals: list[dict[str, Any]]
    record_features: list[dict[str, Any]]
    warnings: list[str]
    open_issues: list[str]


def build_infrastructure_intermediate_package(
    *,
    pdns_records: Iterable[Mapping[str, Any]],
    output_dir: Path,
    dataset_id: str,
    dataset_version: str,
    generated_at: str,
    fetched_at: str,
    vt_payloads: Iterable[Mapping[str, Any]] = (),
    vt_records: Iterable[Mapping[str, Any]] = (),
    schema_version: str = _SCHEMA_VERSION,
) -> InfrastructureRows:
    """Write a pDNS + VirusTotal intermediate delivery package."""
    output_dir = Path(output_dir)
    (output_dir / "raw" / "pdns").mkdir(parents=True, exist_ok=True)
    (output_dir / "raw" / "vt").mkdir(parents=True, exist_ok=True)
    rows = InfrastructureRows([], [], [], [], [], [], [])

    for raw in pdns_records:
        raw_ref = _write_raw_object(output_dir, "pdns", raw, _pdns_source_id(raw), fetched_at)
        item_rows = transform_pdns_record(raw, raw_ref)
        _extend(rows, item_rows)

    for raw in vt_records:
        payload = _vt_payload_from_raw_record(raw)
        raw_ref = _write_raw_object(
            output_dir,
            "vt",
            raw,
            _vt_record_source_id(raw, payload),
            fetched_at,
        )
        item_rows = transform_vt_payload(payload, raw_ref)
        _extend(rows, item_rows)

    for payload in vt_payloads:
        raw_ref = _write_raw_object(output_dir, "vt", payload, _vt_source_id(payload), fetched_at)
        item_rows = transform_vt_payload(payload, raw_ref)
        _extend(rows, item_rows)

    intermediate = output_dir / "intermediate"
    _write_json(
        intermediate / "source_manifest.json",
        _source_manifest(dataset_id, dataset_version, schema_version, generated_at, rows),
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


def transform_pdns_record(raw: Mapping[str, Any], raw_ref: InfrastructureRawRef) -> InfrastructureRows:
    """Transform one raw pDNS snapshot into intermediate rows."""
    structured = project_pdns_raw(dict(raw))
    return _transform_structured_infrastructure(
        connector_source="pdns",
        raw_ref=raw_ref,
        structured=structured,
        raw_features={
            "payload_count": (raw.get("payload") or {}).get("count")
            if isinstance(raw.get("payload"), Mapping)
            else None,
        },
        open_issues=_pdns_open_issues(raw),
    )


def transform_vt_payload(
    payload: Mapping[str, Any], raw_ref: InfrastructureRawRef
) -> InfrastructureRows:
    """Transform one raw VirusTotal v3 domain payload into intermediate rows."""
    attrs = _vt_attrs(payload)
    structured = {
        **project_vt_infra(dict(payload)),
        "last_modification_date": _iso(attrs.get("last_modification_date")),
    }
    return _transform_structured_infrastructure(
        connector_source="vt",
        raw_ref=raw_ref,
        structured=structured,
        raw_features={
            "analysis_stats": attrs.get("last_analysis_stats", {}),
            "categories": attrs.get("categories", {}),
            "tags": attrs.get("tags", []),
            "registrar": attrs.get("registrar", ""),
            "creation_date": _iso(attrs.get("creation_date")),
            "expiration_date": _iso(attrs.get("expiration_date")),
            "last_modification_date": _iso(attrs.get("last_modification_date")),
        },
        open_issues=_vt_open_issues(payload),
    )


def _transform_structured_infrastructure(
    *,
    connector_source: str,
    raw_ref: InfrastructureRawRef,
    structured: Mapping[str, Any],
    raw_features: Mapping[str, Any],
    open_issues: Iterable[str],
) -> InfrastructureRows:
    record_id = f"record_{connector_source}_{_safe_segment(raw_ref.source_id)}_{raw_ref.raw_sha256[:24]}"
    mentions: dict[tuple[str, str, str], dict[str, Any]] = {}
    relations: list[dict[str, Any]] = []
    domain = _text(structured.get("domain")) or raw_ref.source_id
    domain_mention = _upsert_mention(
        mentions,
        record_id=record_id,
        connector_source=connector_source,
        raw_value=domain,
        entity_type="domain",
        source_field="domain",
        value_type={"raw": "domain", "canonical": "domain"},
    )

    for resolution in _list(structured.get("resolutions")):
        if not isinstance(resolution, Mapping):
            continue
        record_type = _text(resolution.get("record_type")).upper()
        if record_type == "A":
            ip_value = _text(resolution.get("ip")) or _text(resolution.get("value"))
            if not ip_value:
                continue
            ip = _upsert_mention(
                mentions,
                record_id=record_id,
                connector_source=connector_source,
                raw_value=ip_value,
                entity_type="ip",
                source_field="resolutions[].ip",
                value_type={"raw": "A", "canonical": "ip"},
            )
            relations.append(
                _relation_mention(
                    connector_source,
                    record_id,
                    domain_mention,
                    "resolves-to",
                    ip,
                    "resolutions[]",
                    "dns",
                )
            )
            asn_value = _text(resolution.get("asn"))
            if asn_value:
                asn = _upsert_mention(
                    mentions,
                    record_id=record_id,
                    connector_source=connector_source,
                    raw_value=_normalize_asn(asn_value),
                    entity_type="asn",
                    source_field="resolutions[].asn",
                    value_type={"raw": "asn", "canonical": "asn"},
                )
                relations.append(
                    _relation_mention(
                        connector_source,
                        record_id,
                        ip,
                        "belongs-to",
                        asn,
                        "resolutions[].asn",
                        "routing",
                    )
                )
            country = _text(resolution.get("country"))
            if country:
                location = _upsert_mention(
                    mentions,
                    record_id=record_id,
                    connector_source=connector_source,
                    raw_value=country,
                    entity_type="location",
                    source_field="resolutions[].country",
                    value_type={"raw": "country", "canonical": "location"},
                )
                relations.append(
                    _relation_mention(
                        connector_source,
                        record_id,
                        ip,
                        "located-in",
                        location,
                        "resolutions[].country",
                        "geolocation",
                    )
                )
        elif record_type == "NS":
            nameserver_value = _text(resolution.get("value"))
            if not nameserver_value:
                continue
            nameserver = _upsert_mention(
                mentions,
                record_id=record_id,
                connector_source=connector_source,
                raw_value=nameserver_value,
                entity_type="domain",
                source_field="resolutions[].value",
                value_type={"raw": "NS", "canonical": "domain"},
            )
            relations.append(
                _relation_mention(
                    connector_source,
                    record_id,
                    domain_mention,
                    "uses-nameserver",
                    nameserver,
                    "resolutions[]",
                    "dns",
                )
            )

    for subdomain_value in _strings(structured.get("subdomains")):
        subdomain = _upsert_mention(
            mentions,
            record_id=record_id,
            connector_source=connector_source,
            raw_value=subdomain_value,
            entity_type="domain",
            source_field="subdomains[]",
            value_type={"raw": "subdomain", "canonical": "domain"},
        )
        relations.append(
            _relation_mention(
                connector_source,
                record_id,
                domain_mention,
                "has-subdomain",
                subdomain,
                "subdomains[]",
                "dns",
            )
        )

    entity_mentions = sorted(mentions.values(), key=lambda row: row["entity_mention_id"])
    relation_mentions = _dedupe_relations(relations)
    record = _intermediate_record(
        connector_source=connector_source,
        raw_ref=raw_ref,
        record_id=record_id,
        structured=structured,
        entity_mentions=len(entity_mentions),
        relation_mentions=len(relation_mentions),
    )
    features = _record_features(
        connector_source=connector_source,
        record_id=record_id,
        structured=structured,
        entity_mentions=entity_mentions,
        relation_mentions=relation_mentions,
        raw_features=raw_features,
    )
    return InfrastructureRows(
        intermediate_records=[record],
        entity_mentions=entity_mentions,
        relation_mentions=relation_mentions,
        attribution_signals=[],
        record_features=[features],
        warnings=[],
        open_issues=list(open_issues),
    )


def _upsert_mention(
    mentions: dict[tuple[str, str, str], dict[str, Any]],
    *,
    record_id: str,
    connector_source: str,
    raw_value: str,
    entity_type: str,
    source_field: str,
    value_type: dict[str, str | None],
) -> dict[str, Any]:
    normalized = _normalize_value(entity_type, raw_value)
    key = (entity_type, source_field, normalized)
    if key in mentions:
        mentions[key]["occurrence_count"] += 1
        return mentions[key]
    resolution = _resolution(connector_source, entity_type, raw_value)
    mention_id = contract_id(
        "em",
        (
            record_id,
            source_field,
            entity_type,
            normalized,
            value_type,
            resolution["entity_id"],
        ),
    )
    mentions[key] = {
        "entity_mention_id": mention_id,
        "record_id": record_id,
        "source": {"connector_source": connector_source},
        "raw_value": raw_value,
        "normalized_value": normalized,
        "entity_type": entity_type,
        "source_field": source_field,
        "extraction_method": "source_field",
        "occurrence_count": 1,
        "value_type": value_type,
        "resolution": resolution,
        "ambiguity": {"status": "resolved", "reason": None, "candidate_entity_ids": []},
        "merge_candidates": [],
    }
    return mentions[key]


def _relation_mention(
    connector_source: str,
    record_id: str,
    subject: Mapping[str, Any],
    predicate: str,
    obj: Mapping[str, Any],
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
        "source": {"connector_source": connector_source},
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
            "evidence_type": evidence_type,
            "label_availability": "none",
            "attribution_confidence": None,
        },
        "ambiguity": {"status": "unambiguous", "notes": []},
    }


def _intermediate_record(
    *,
    connector_source: str,
    raw_ref: InfrastructureRawRef,
    record_id: str,
    structured: Mapping[str, Any],
    entity_mentions: int,
    relation_mentions: int,
) -> dict[str, Any]:
    metadata = _SOURCE_METADATA[connector_source]
    timestamps = _timestamps(connector_source, raw_ref, structured)
    return {
        "record_id": record_id,
        "raw_ref": raw_ref.to_dict(),
        "source": {
            "connector_source": connector_source,
            "source_class": _SOURCE_CLASS,
            "publisher_category": metadata["publisher_category"],
            "source_name": metadata["source_name"],
            "source_record_id": raw_ref.source_id,
        },
        "timestamps": timestamps,
        "record_signals": {
            "label_availability": "none",
            "has_attribution_confidence": False,
            "ambiguity_flag": False,
        },
        "counts": {
            "entity_mentions": entity_mentions,
            "relation_mentions": relation_mentions,
            "resolutions": len(_list(structured.get("resolutions"))),
            "subdomains": len(_strings(structured.get("subdomains"))),
        },
        "processing_status": {"status": "ok", "warnings": []},
    }


def _record_features(
    *,
    connector_source: str,
    record_id: str,
    structured: Mapping[str, Any],
    entity_mentions: list[dict[str, Any]],
    relation_mentions: list[dict[str, Any]],
    raw_features: Mapping[str, Any],
) -> dict[str, Any]:
    timestamps = _timestamps(
        connector_source,
        InfrastructureRawRef(connector_source, "", "", "", ""),
        structured,
    )
    content_features = {
        "domain": _text(structured.get("domain")),
        "resolution_count": len(_list(structured.get("resolutions"))),
        "subdomain_count": len(_strings(structured.get("subdomains"))),
        "entity_type_distribution": dict(
            sorted(Counter(row["entity_type"] for row in entity_mentions).items())
        ),
        "relation_predicate_distribution": dict(
            sorted(
                Counter(row["predicate"]["mapped_value"] for row in relation_mentions).items()
            )
        ),
    }
    content_features.update(raw_features)
    metadata = _SOURCE_METADATA[connector_source]
    return {
        "record_id": record_id,
        "source_features": {
            "connector_source": connector_source,
            "source_class": _SOURCE_CLASS,
            "publisher_category": metadata["publisher_category"],
        },
        "timestamp_features": {
            "has_published_at": False,
            "has_modified_at": bool(timestamps["modified_at"]),
            "has_observed_range": bool(timestamps["observed_first"] or timestamps["observed_last"]),
            "age_days_at_collection": None,
            "timestamp_basis": timestamps["timestamp_basis"],
        },
        "content_features": content_features,
        "label_features": {
            "label_availability": "none",
            "has_confidence": False,
            "supporting_sources_count": None,
            "conflicting_sources_count": None,
        },
        "ambiguity_features": {
            "ambiguous_entity_mentions": 0,
            "ambiguous_relation_mentions": 0,
        },
    }


def _timestamps(
    connector_source: str, raw_ref: InfrastructureRawRef, structured: Mapping[str, Any]
) -> dict[str, Any]:
    if connector_source == "pdns":
        first_seen = _text(structured.get("first_seen")) or None
        last_seen = _text(structured.get("last_seen")) or None
        return {
            "published_at": None,
            "modified_at": None,
            "observed_first": first_seen,
            "observed_last": last_seen,
            "fetched_at": _text(structured.get("fetched_at")) or raw_ref.fetched_at,
            "timestamp_basis": "observed_range" if first_seen or last_seen else "fetched_only",
        }
    last_modified = _text(_vt_last_modified(structured)) or None
    return {
        "published_at": None,
        "modified_at": last_modified,
        "observed_first": None,
        "observed_last": None,
        "fetched_at": raw_ref.fetched_at,
        "timestamp_basis": "source_modified" if last_modified else "fetched_only",
    }


def _source_manifest(
    dataset_id: str,
    dataset_version: str,
    schema_version: str,
    generated_at: str,
    rows: InfrastructureRows,
) -> dict[str, Any]:
    counts = Counter(row["source"]["connector_source"] for row in rows.intermediate_records)
    return {
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "schema_version": schema_version,
        "generated_at": generated_at,
        "sources": [
            _source_entry("pdns", counts.get("pdns", 0)),
            _source_entry("vt", counts.get("vt", 0)),
        ],
    }


def _source_entry(connector_source: str, record_count: int) -> dict[str, Any]:
    metadata = _SOURCE_METADATA[connector_source]
    return {
        "connector_source": connector_source,
        "source_class": _SOURCE_CLASS,
        "publisher_category": metadata["publisher_category"],
        "record_count": record_count,
        "raw_collection": metadata["raw_collection"],
        "provides": {
            "labels": False,
            "enrichment": connector_source == "vt",
            "timestamps": True,
            "actor_aliases": False,
            "campaign_names": False,
            "malware_names": False,
            "tools": False,
            "techniques": False,
            "indicators": True,
            "infrastructure_relations": True,
        },
    }


def _processing_report(
    dataset_id: str,
    dataset_version: str,
    schema_version: str,
    generated_at: str,
    rows: InfrastructureRows,
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
            "connector_sources": dict(
                sorted(Counter(row["source"]["connector_source"] for row in rows.intermediate_records).items())
            ),
            "entity_types": dict(
                sorted(Counter(row["entity_type"] for row in rows.entity_mentions).items())
            ),
            "relation_predicates": dict(
                sorted(Counter(row["predicate"]["mapped_value"] for row in rows.relation_mentions).items())
            ),
            "attribution_signal_types": dict(
                sorted(Counter(row["signal_type"] for row in rows.attribution_signals).items())
            ),
        },
        "warnings": rows.warnings,
        "open_issues": sorted(set(rows.open_issues)),
    }


def _write_raw_object(
    root: Path,
    connector_source: str,
    raw: Mapping[str, Any],
    source_id: str,
    fallback_fetched_at: str,
) -> InfrastructureRawRef:
    source_id = source_id or contract_id("source", (dict(raw),))
    fetched_at = _text(raw.get("fetched_at")) or fallback_fetched_at
    raw_text = json.dumps(raw, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    raw_sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    filename = f"{_safe_segment(fetched_at)}_{raw_sha[:24]}.json"
    raw_rel = Path("raw") / connector_source / _safe_segment(source_id) / filename
    raw_path = root / raw_rel
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw_text, encoding="utf-8")
    return InfrastructureRawRef(
        connector_source=connector_source,
        source_id=source_id,
        fetched_at=fetched_at,
        raw_path=raw_rel.as_posix(),
        raw_sha256=raw_sha,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _extend(target: InfrastructureRows, source: InfrastructureRows) -> None:
    target.intermediate_records.extend(source.intermediate_records)
    target.entity_mentions.extend(source.entity_mentions)
    target.relation_mentions.extend(source.relation_mentions)
    target.attribution_signals.extend(source.attribution_signals)
    target.record_features.extend(source.record_features)
    target.warnings.extend(source.warnings)
    target.open_issues.extend(source.open_issues)


def _dedupe_relations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        out[row["relation_mention_id"]] = row
    return [out[key] for key in sorted(out)]


def _resolution(connector_source: str, entity_type: str, raw_value: str) -> dict[str, Any]:
    return {
        "entity_id": _entity_id(connector_source, entity_type, raw_value),
        "canonical_name": raw_value,
        "ontology_id": None,
        "resolution_method": "not_applicable",
    }


def _entity_id(connector_source: str, entity_type: str, raw_value: str) -> str:
    return contract_id(
        entity_type,
        (connector_source, entity_type, _normalize_value(entity_type, raw_value)),
    )


def _normalize_value(entity_type: str, raw_value: str) -> str:
    value = " ".join(raw_value.strip().split())
    if entity_type in {"domain", "ip"}:
        return value.lower()
    if entity_type == "asn":
        return _normalize_asn(value)
    if entity_type == "location":
        return value.casefold()
    return value


def _normalize_asn(value: str) -> str:
    compact = " ".join(value.strip().split())
    return compact.upper() if compact.upper().startswith("AS") else compact


def _pdns_source_id(raw: Mapping[str, Any]) -> str:
    return _text(raw.get("source_id"))


def _vt_source_id(payload: Mapping[str, Any]) -> str:
    data = payload.get("data") if isinstance(payload.get("data"), Mapping) else {}
    return _text(data.get("id"))


def _vt_record_source_id(raw: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    return _vt_source_id(payload) or _text(raw.get("source_id"))


def _vt_payload_from_raw_record(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = raw.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def _vt_attrs(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), Mapping) else {}
    attrs = data.get("attributes") if isinstance(data.get("attributes"), Mapping) else {}
    return attrs


def _pdns_open_issues(raw: Mapping[str, Any]) -> list[str]:
    payload = raw.get("payload") if isinstance(raw.get("payload"), Mapping) else {}
    passive_dns = payload.get("passive_dns") if isinstance(payload.get("passive_dns"), list) else []
    deferred_types = sorted(
        {
            record_type
            for item in passive_dns
            if isinstance(item, Mapping)
            if (record_type := _text(item.get("record_type")).upper())
            and record_type not in {"A", "NS"}
        }
    )
    issues = [
        "pDNS per-answer first/last timestamps are preserved in raw; relation-level temporal qualifiers are deferred.",
    ]
    if deferred_types:
        issues.append(
            "pDNS DNS record types outside A/NS are preserved in raw; "
            f"relation mapping is deferred for: {', '.join(deferred_types)}."
        )
    return issues


def _vt_open_issues(payload: Mapping[str, Any]) -> list[str]:
    attrs = _vt_attrs(payload)
    dns_records = (
        attrs.get("last_dns_records") if isinstance(attrs.get("last_dns_records"), list) else []
    )
    deferred_types = sorted(
        {
            record_type
            for item in dns_records
            if isinstance(item, Mapping)
            if (record_type := _text(item.get("type")).upper()) and record_type not in {"A", "NS"}
        }
    )
    issues = [
        "VT categories, tags, registrar, whois, rdap, and certificate fields are preserved as metadata/features/raw; promotion to entity or relation rows is deferred.",
    ]
    if deferred_types:
        issues.append(
            "VT DNS record types outside A/NS are preserved in raw; "
            f"relation mapping is deferred for: {', '.join(deferred_types)}."
        )
    return issues


def _vt_last_modified(structured: Mapping[str, Any]) -> str:
    # `project_vt_infra` intentionally returns the common infra relation shape,
    # so VT's enrichment timestamp is carried through `raw_features` elsewhere.
    return _text(structured.get("last_modification_date"))


def _iso(value: Any) -> str:
    if not isinstance(value, int):
        return ""
    return datetime.fromtimestamp(value, tz=UTC).isoformat()


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [_text(item) for item in _list(value) if _text(item)]


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_segment(value: str) -> str:
    out = "".join("-" if char in _UNSAFE_PATH else char for char in value)
    return out.strip().strip(".") or "_"
