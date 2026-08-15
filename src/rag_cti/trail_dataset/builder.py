"""Build a shareable five-node TRAIL dataset from existing local snapshots.

The public interface deliberately hides source-specific schemas and graph
bookkeeping.  Inputs are read only.  Every output is a deterministic derivative
that can be discarded and rebuilt from the recorded ``raw_ref`` values.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from rag_cti.connectors.pdns_projection import project_pdns_raw
from rag_cti.ioc_normalization import (
    DOMAIN_TOKEN_RE,
    IP_TOKEN_RE,
    URL_TOKEN_RE,
    normalize_domain,
    normalize_misp_url,
    normalize_url,
)

NODE_TYPES = ("event", "domain", "ip", "url", "asn")
RELATION_MAP = {
    "event_contains_domain": ("event", "in_report", "domain"),
    "event_contains_ip": ("event", "in_report", "ip"),
    "event_contains_url": ("event", "in_report", "url"),
    "domain_resolves_to_ip": ("domain", "resolves_to", "ip"),
    "url_hosted_on_domain": ("url", "hosted_on", "domain"),
    "url_resolves_to_ip": ("url", "resolves_to_ip", "ip"),
    "ip_in_asn": ("ip", "in_group", "asn"),
}

OTX_TYPE_MAP = {
    "domain": "domain",
    "hostname": "domain",
    "fqdn": "domain",
    "ipv4": "ip",
    "ipv6": "ip",
    "ip": "ip",
    "url": "url",
    "uri": "url",
}

MISP_TYPE_MAP = {
    "domain": "domain",
    "hostname": "domain",
    "ip-src": "ip",
    "ip-dst": "ip",
    "url": "url",
    "uri": "url",
}

ORKL_URL_PATTERN = URL_TOKEN_RE
ORKL_IP_PATTERN = IP_TOKEN_RE
ORKL_DOMAIN_PATTERN = re.compile(
    r"(?i)(?<![\w@.-])"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.|\[\.]))+"
    r"(?:com|net|org|io|co|ru|cn|info|biz|online|top|xyz|site|me|de|uk|us|gov|edu|mil|"
    r"cloud|app|tech|live|pro|cc|pw|tk|work|support|website|shop|store|dev|ai|"
    r"ca|au|jp|kr|in|br|ch|it|nl|se|no|es|pl|be|fr|ly|tv|mobi|name|onion)"
    r"(?![\w-])"
)
ORKL_DOMAIN_PATTERN = DOMAIN_TOKEN_RE
ORKL_SECTION_BOUNDARY_PATTERN = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:\d+(?:\.\d+)*[.)]?\s+)?"
    r"(?:"
    r"(?:ioc|iocs|indicator|indicators|observable|observables|network\s+indicators?)"
    r"(?:\s+(?:appendix|appendices|list|inventory))?"
    r"|appendix(?:\s+[a-z0-9]+)?(?:\s*[:\-].*)?"
    r")\s*:?\s*$"
)
ORKL_SECTION_BOUNDARY_PATTERN = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:\d+(?:\.\d+)*[.)]?\s+)?"
    r"(?:(?:(?:network\s+)?(?:ioc|iocs|indicator|indicators)|observable|observables)"
    r"(?:\s+(?:appendix|appendices|list|inventory))?|"
    r"appendix(?:\s+[a-z0-9]+)?(?:\s*[:\-].*)?)\s*:?\s*$"
)


@dataclass(frozen=True)
class SourceRoots:
    """Local roots containing already-collected source snapshots."""

    otx: Path | None = None
    circl_misp: Path | None = None
    pdns: Path | None = None
    orkl_intermediate: Path | None = None
    urlhaus_normalized: Path | None = None


@dataclass(frozen=True)
class BuildPolicy:
    """Projection controls.  ``max_events`` is a deterministic bounded smoke gate."""

    max_events: int | None = None
    max_input_files: int | None = None

    def __post_init__(self) -> None:
        if self.max_events is not None and self.max_events < 1:
            raise ValueError("max_events must be positive or None")
        if self.max_input_files is not None and self.max_input_files < 1:
            raise ValueError("max_input_files must be positive or None")


@dataclass(frozen=True)
class DatasetManifest:
    output_dir: Path
    event_count: int
    node_count: int
    edge_count: int
    rejected_count: int
    content_sha256: str


@dataclass(frozen=True)
class _Event:
    event_id: str
    source: str
    source_record_id: str
    raw_ref: Any
    event_time: str | None
    fetched_at: str | None
    indicators: tuple[dict[str, Any], ...]
    claims: tuple[dict[str, Any], ...]


def build_dataset(
    sources: SourceRoots,
    output_dir: Path,
    policy: BuildPolicy | None = None,
    event_allowlist: dict[str, set[str]] | None = None,
) -> DatasetManifest:
    """Project local raw snapshots into deterministic five-node JSONL artifacts.

    The caller only supplies source roots and a fresh output directory.  Raw
    files are never written.  Existing output directories are rejected so a
    rerun cannot silently mix artifacts from different source states.
    """

    policy = policy or BuildPolicy()
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")

    rejected: list[dict[str, Any]] = []
    candidates: list[_Event] = []
    if sources.otx is not None:
        candidates.extend(_load_otx(Path(sources.otx), rejected, policy.max_input_files))
    if sources.circl_misp is not None:
        candidates.extend(_load_misp(
            Path(sources.circl_misp), rejected, policy.max_input_files,
            (event_allowlist or {}).get("circl_misp"),
        ))
    if sources.orkl_intermediate is not None:
        candidates.extend(_load_orkl_intermediate(
            Path(sources.orkl_intermediate), rejected, policy.max_input_files,
            (event_allowlist or {}).get("orkl"),
        ))
    if sources.urlhaus_normalized is not None:
        candidates.extend(_load_urlhaus_normalized(Path(sources.urlhaus_normalized), rejected, policy.max_input_files))

    # Duplicate source snapshots collapse by stable Event id, preferring the
    # lexicographically latest fetched_at/raw_ref tuple.
    latest: dict[str, _Event] = {}
    for event in candidates:
        current = latest.get(event.event_id)
        if current is None or ((event.fetched_at or ""), _stable_value(event.raw_ref)) > (
            (current.fetched_at or ""), _stable_value(current.raw_ref)
        ):
            latest[event.event_id] = event
    events = sorted(latest.values(), key=lambda row: row.event_id)
    discovered_event_count = len(events)
    if policy.max_events is not None:
        events = events[: policy.max_events]

    nodes: dict[str, dict[str, Any]] = {}
    evidence_by_edge: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    event_rows: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    supported_type_counts: Counter[str] = Counter()
    raw_ioc_count = deduplicated_ioc_count = duplicate_ioc_count = 0

    for event in events:
        event_rejected = 0
        raw_ioc_count += len(event.indicators)
        normalised_indicators: list[tuple[dict[str, Any], str, str]] = []
        for index, indicator in enumerate(event.indicators):
            result = _normalise_indicator(indicator.get("type"), indicator.get("value"), event.source)
            if result is None:
                rejected.append(
                    {
                        "source": event.source,
                        "event_id": event.event_id,
                        "raw_ref": event.raw_ref,
                        "record_path": indicator.get("path", f"indicator[{index}]"),
                        "reason": _rejection_reason(indicator.get("type"), indicator.get("value"), event.source),
                        "raw_type": indicator.get("type"),
                        "raw_value": indicator.get("value"),
                    }
                )
                event_rejected += 1
                continue
            node_type, value = result
            normalised_indicators.append((indicator, node_type, value))

        if not normalised_indicators:
            rejected.append(
                {
                    "source": event.source,
                    "event_id": event.event_id,
                    "raw_ref": event.raw_ref,
                    "record_path": "event",
                    "reason": "no_supported_iocs",
                }
            )
            continue

        _add_node(nodes, "event", event.event_id, event.event_id, {"source": event.source})
        seen: set[tuple[str, str]] = set()
        event_counts: Counter[str] = Counter()
        event_supported_count = len(normalised_indicators)
        for indicator, node_type, value in normalised_indicators:
            key = (node_type, value)
            if key in seen:
                duplicate_ioc_count += 1
                continue
            seen.add(key)
            deduplicated_ioc_count += 1
            event_counts[node_type] += 1
            supported_type_counts[node_type] += 1
            target_id = _node_id(node_type, value)
            _add_node(nodes, node_type, target_id, value)
            relation = f"event_contains_{node_type}"
            _add_evidence(
                evidence_by_edge,
                event.event_id,
                relation,
                target_id,
                source=event.source,
                raw_ref=event.raw_ref,
                observed_at=indicator.get("first_seen") or event.event_time,
                derivation=indicator.get("derivation") or "source_asserted",
                record_path=indicator.get("path"),
                raw_value=indicator.get("raw_value", indicator.get("value")),
                extraction_method=indicator.get("extraction_method"),
                network_port=indicator.get("network_port"),
            )
            if node_type == "url":
                _project_url(value, event, indicator, nodes, evidence_by_edge)

        source_claim_ids = sorted(
            str(claim["claim_id"])
            for claim in event.claims
            if claim.get("claim_id")
        )
        event_rows.append(
            {
                "event_id": event.event_id,
                "source": event.source,
                "source_record_id": event.source_record_id,
                "raw_ref": event.raw_ref,
                "event_time": event.event_time,
                "fetched_at": event.fetched_at,
                "raw_ioc_count": len(event.indicators),
                "deduplicated_supported_ioc_count": len(seen),
                "duplicate_supported_ioc_count": event_supported_count - len(seen),
                "rejected_ioc_count": event_rejected,
                "ioc_type_counts": dict(sorted(event_counts.items())),
                "source_claim_ids": source_claim_ids,
            }
        )
        claims.extend(event.claims)

    if sources.pdns is not None:
        _join_pdns(Path(sources.pdns), nodes, evidence_by_edge, rejected)

    edges = _materialise_edges(evidence_by_edge)
    node_rows = sorted(nodes.values(), key=lambda row: (row["type"], row["node_id"]))
    event_rows.sort(key=lambda row: row["event_id"])
    claims.sort(key=lambda row: row["claim_id"])
    rejected.sort(key=lambda row: (str(row.get("raw_ref")), str(row.get("record_path")), str(row.get("reason"))))
    rejected, duplicate_rejected_row_count = _deduplicate_rejected(rejected)
    rejection_metrics = _rejection_metrics(rejected)
    claim_validation = _validate_claim_provenance(event_rows, claims)
    event_evidence_metrics = _event_evidence_metrics(event_rows, edges, len(events))

    asn_linked_ips = {edge["source_id"] for edge in edges if edge["relation"] == "ip_in_asn"}
    all_ips = {row["node_id"] for row in node_rows if row["type"] == "ip"}
    missing_asn = sorted(all_ips - asn_linked_ips)
    coverage = {
        "discovered_event_count": discovered_event_count,
        "attempted_event_count": len(events),
        "selected_event_count": len(event_rows),
        "bounded_by_max_events": policy.max_events is not None and discovered_event_count > len(events),
        "input_scan_bounded": policy.max_input_files is not None,
        "max_input_files": policy.max_input_files,
        "raw_ioc_count": raw_ioc_count,
        "deduplicated_supported_ioc_count": deduplicated_ioc_count,
        "duplicate_supported_ioc_count": duplicate_ioc_count,
        "supported_ioc_type_counts": dict(sorted(supported_type_counts.items())),
        "node_type_counts": dict(sorted(Counter(row["type"] for row in node_rows).items())),
        "relation_counts": dict(sorted(Counter(row["relation"] for row in edges).items())),
        "missing_asn_evidence_count": len(missing_asn),
        "ip_nodes_without_asn_evidence": missing_asn,
        "rejected_record_count": len(rejected),
        "duplicate_rejected_row_count": duplicate_rejected_row_count,
        "source_claim_count": len(claims),
        "events_with_source_claims": sum(bool(row["source_claim_ids"]) for row in event_rows),
        "unreferenced_source_claim_count": claim_validation["unreferenced_claim_count"],
        **event_evidence_metrics,
        **rejection_metrics,
    }
    source_mapping = _source_mapping()
    compatibility_validation = _validate_graph(node_rows, edges)
    consumer_contract = _consumer_contract(compatibility_validation)
    validation_audit = {
        "format": "trail-five-node-validation-audit",
        "format_version": 1,
        "status": "passed",
        "node_and_edge_semantics": compatibility_validation,
        "provenance": {
            "all_edges_have_source_raw_ref_observed_at_derivation_and_record_path": True,
            "raw_inputs_are_read_only": True,
            "source_attribution_used_as_graph_label": False,
        },
        "claim_provenance": claim_validation,
        "event_evidence_metrics": {
            "network_ioc_types": ["domain", "ip", "url"],
            "zero_network_ioc_event_count": "attempted events minus events with a supported network IOC",
            "non_network_only_event_count": "events with supported evidence but no supported network IOC",
            "isolated_event_count": "selected Event rows with no materialized outgoing relation",
        },
        "rejected_records_artifact": "rejected_records.jsonl",
        "coverage_artifact": "coverage_audit.json",
        "coverage_gaps": {
            "ip_nodes_without_asn_evidence": missing_asn,
            "orkl_intermediate_records_without_supported_iocs": sum(
                1 for row in rejected if row.get("reason") == "no_supported_iocs"
                and row.get("source") == "orkl"
            ),
        },
        "rejection_taxonomy": {
            "rejected_record_count": "unique rejected-record rows written to rejected_records.jsonl",
            "duplicate_rejected_row_count": "exact duplicate rejected rows suppressed before publication",
            "rejected_event_count": "unique event_id values represented by a rejection row",
            "unsupported_ioc_type_count": "rejected IOC rows whose type is outside the source mapping",
            "invalid_ioc_value_count": "rejected IOC rows with empty or malformed values",
            "dropped_event_count": "unique events with no supported IOC after normalization",
        },
    }

    output_dir.mkdir(parents=True)
    jsonl_outputs: tuple[tuple[str, list[dict[str, Any]]], ...] = (
        ("nodes.jsonl", node_rows),
        ("edges.jsonl", edges),
        ("events.jsonl", event_rows),
        ("source_claims.jsonl", claims),
        ("rejected_records.jsonl", rejected),
    )
    for name, rows in jsonl_outputs:
        _write_jsonl(output_dir / name, rows)
    json_outputs: tuple[tuple[str, Any], ...] = (
        ("source_mapping.json", source_mapping),
        ("coverage_audit.json", coverage),
        ("consumer_contract.json", consumer_contract),
        ("validation_audit.json", validation_audit),
    )
    for name, value in json_outputs:
        (output_dir / name).write_bytes(_json_bytes(value))

    output_names = tuple(name for name, _ in (*jsonl_outputs, *json_outputs))
    content_hash = _content_hash(output_dir, output_names)
    manifest_value = {
        "format": "trail-five-node-dataset",
        "format_version": 1,
        "input_policy": asdict(policy),
        "source_roots": {
            key: str(value) if value is not None else None for key, value in asdict(sources).items()
        },
        "raw_inputs_are_read_only": True,
        "event_allowlist_applied": event_allowlist is not None,
        "source_attribution_used_as_graph_label": False,
        "event_count": len(event_rows),
        "node_count": len(node_rows),
        "edge_count": len(edges),
        "rejected_count": len(rejected),
        "content_sha256": content_hash,
        "files": sorted(output_names),
    }
    (output_dir / "manifest.json").write_bytes(_json_bytes(manifest_value))
    return DatasetManifest(
        output_dir=output_dir,
        event_count=len(event_rows),
        node_count=len(node_rows),
        edge_count=len(edges),
        rejected_count=len(rejected),
        content_sha256=content_hash,
    )


def _load_otx(root: Path, rejected: list[dict[str, Any]], max_input_files: int | None = None) -> list[_Event]:
    events: list[_Event] = []
    paths = sorted(root.rglob("*.json"))
    if max_input_files is not None:
        paths = paths[:max_input_files]
    for path in paths:
        raw_ref = path.as_posix()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            rejected.append({"source": "otx", "raw_ref": raw_ref, "reason": "invalid_json", "error": str(exc)})
            continue
        if not isinstance(document, dict):
            continue
        wrapped = isinstance(document.get("payload"), dict)
        payload = document["payload"] if wrapped else document
        # Avoid treating indicator page snapshots as Events.
        if not isinstance(payload, dict) or not isinstance(payload.get("indicators"), list):
            continue
        event_id = str(payload.get("id") or document.get("source_id") or "").strip()
        if not event_id:
            rejected.append({"source": "otx", "raw_ref": raw_ref, "reason": "missing_event_id"})
            continue
        indicators = tuple(
            {
                "type": item.get("type"),
                "value": item.get("indicator", item.get("value")),
                "first_seen": item.get("created"),
                "path": f"indicators[{index}]",
            }
            for index, item in enumerate(payload.get("indicators", []))
            if isinstance(item, dict)
        )
        canonical_event_id = f"event:otx:{event_id}"
        claims = _otx_claims(payload, canonical_event_id, raw_ref)
        events.append(
            _Event(
                event_id=canonical_event_id,
                source="otx",
                source_record_id=event_id,
                raw_ref=raw_ref,
                event_time=_text(payload.get("created") or payload.get("modified")),
                fetched_at=_text(document.get("fetched_at")) if wrapped else None,
                indicators=indicators,
                claims=tuple(claims),
            )
        )
    return events


def _load_misp(
    root: Path,
    rejected: list[dict[str, Any]],
    max_input_files: int | None = None,
    allowed_event_ids: set[str] | None = None,
) -> list[_Event]:
    event_root = root / "raw" / "events"
    paths = sorted((event_root if event_root.is_dir() else root).rglob("*.json"))
    events: list[_Event] = []
    if max_input_files is not None:
        paths = paths[:max_input_files]
    for path in paths:
        raw_ref = path.as_posix()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            rejected.append({"source": "circl_misp", "raw_ref": raw_ref, "reason": "invalid_json", "error": str(exc)})
            continue
        event = document.get("Event", document) if isinstance(document, dict) else None
        if not isinstance(event, dict):
            rejected.append({"source": "circl_misp", "raw_ref": raw_ref, "reason": "invalid_event_payload"})
            continue
        source_id = str(event.get("uuid") or event.get("id") or "").strip()
        if not source_id:
            rejected.append({"source": "circl_misp", "raw_ref": raw_ref, "reason": "missing_event_id"})
            continue
        if allowed_event_ids is not None and not _event_is_allowed(
            "circl_misp", source_id, allowed_event_ids
        ):
            continue
        indicators: list[dict[str, Any]] = []
        for prefix, attributes in _misp_attribute_groups(event):
            for index, item in enumerate(attributes):
                if not isinstance(item, dict):
                    continue
                parts = _split_misp_attribute(item.get("type"), item.get("value"))
                for part_index, (raw_type, value) in enumerate(parts):
                    if raw_type == "port":
                        continue
                    indicator = {
                        "type": raw_type,
                        "value": value,
                        "first_seen": item.get("first_seen"),
                        "path": f"{prefix}.Attribute[{index}]",
                    }
                    if raw_type in {"ip-src", "ip-dst"} and part_index + 1 < len(parts):
                        next_type, next_value = parts[part_index + 1]
                        if next_type == "port":
                            try:
                                port = int(next_value)
                            except (TypeError, ValueError):
                                port = None
                            if port is not None and 0 < port <= 65535:
                                indicator["network_port"] = port
                    indicators.append(indicator)
        events.append(
            _Event(
                event_id=f"event:circl_misp:{source_id}",
                source="circl_misp",
                source_record_id=source_id,
                raw_ref=raw_ref,
                event_time=_text(event.get("date") or event.get("timestamp")),
                fetched_at=None,
                indicators=tuple(indicators),
                claims=tuple(_misp_claims(event, f"event:circl_misp:{source_id}", raw_ref)),
            )
        )
    return events


def _load_orkl_intermediate(
    root: Path,
    rejected: list[dict[str, Any]],
    max_input_files: int | None = None,
    allowed_event_ids: set[str] | None = None,
) -> list[_Event]:
    """Expose ORKL reports to the compatibility gate without reinterpreting them.

    The ORKL intermediate contract intentionally records reports, actor candidates,
    and external references, but not source-asserted domain/IP/URL IOC fields.
    Returning zero indicators makes that absence visible in rejected_records rather
    than fabricating graph observations from narrative or attribution metadata.
    """
    path = root / "intermediate" / "intermediate_records.jsonl"
    if not path.is_file():
        path = root / "intermediate_records.jsonl"
    if not path.is_file():
        rejected.append({"source": "orkl", "raw_ref": str(root), "reason": "missing_intermediate_records"})
        return []
    events: list[_Event] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if max_input_files is not None and line_number > max_input_files:
                break
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                rejected.append({"source": "orkl", "raw_ref": str(path), "record_path": f"line[{line_number}]", "reason": "invalid_json", "error": str(exc)})
                continue
            if not isinstance(record, dict) or not _text(record.get("record_id")):
                rejected.append({"source": "orkl", "raw_ref": str(path), "record_path": f"line[{line_number}]", "reason": "missing_event_id"})
                continue
            source_info = record.get("source") if isinstance(record.get("source"), dict) else {}
            # Prefer the canonical v3 source identity, while retaining compatibility
            # with older ORKL intermediate rows that exposed only ``record_id``.
            legacy_record_id = _text(record.get("record_id"))
            report_identifier = _text(source_info.get("report_identifier")) or legacy_record_id
            source_id = _text(source_info.get("source_record_id")) or legacy_record_id
            if not report_identifier or not source_id:
                rejected.append({"source": "orkl", "raw_ref": str(path), "record_path": f"line[{line_number}]", "reason": "missing_source_report_identity"})
                continue
            if allowed_event_ids is not None and not _event_is_allowed(
                "orkl", report_identifier, allowed_event_ids
            ):
                continue
            raw_ref = record.get("raw_ref")
            if not isinstance(raw_ref, dict) or not raw_ref.get("raw_path"):
                rejected.append({"source": "orkl", "raw_ref": str(path), "record_path": f"line[{line_number}]", "reason": "missing_raw_provenance"})
                continue
            timestamps = record.get("timestamps") if isinstance(record.get("timestamps"), dict) else {}
            events.append(_Event(
                event_id=f"event:orkl:{source_id}", source="orkl",
                source_record_id=source_id, raw_ref=raw_ref,
                event_time=_text(timestamps.get("published_at") or timestamps.get("modified_at")) or None,
                fetched_at=_text(timestamps.get("fetched_at")) or None,
                indicators=tuple(_extract_orkl_indicators(record)), claims=(),
            ))
    return events


def _event_is_allowed(source: str, source_record_id: str, allowed: set[str]) -> bool:
    if source_record_id in allowed:
        return True
    if source == "circl_misp":
        return f"circl-misp:event:{source_record_id}" in allowed
    if source == "orkl":
        return f"orkl:report:{source_record_id}" in allowed
    return False


def _load_urlhaus_normalized(root: Path, rejected: list[dict[str, Any]], max_input_files: int | None = None) -> list[_Event]:
    """Project URLhaus's existing normalized URL rows without reading payload blobs."""
    path = root / "normalized" / "urls.jsonl" if root.is_dir() else root
    if not path.is_file():
        rejected.append({"source": "urlhaus", "raw_ref": str(root), "reason": "missing_normalized_url_rows"})
        return []
    events: list[_Event] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if max_input_files is not None and line_number > max_input_files:
                break
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                rejected.append({"source": "urlhaus", "raw_ref": str(path), "record_path": f"line[{line_number}]", "reason": "invalid_json", "error": str(exc)})
                continue
            if not isinstance(row, dict):
                rejected.append({"source": "urlhaus", "raw_ref": str(path), "record_path": f"line[{line_number}]", "reason": "invalid_normalized_row"})
                continue
            record_id = _text(row.get("source_record_id") or row.get("url_id"))
            url = _text(row.get("url_raw"))
            if not record_id:
                rejected.append({"source": "urlhaus", "raw_ref": row.get("raw_ref") or str(path), "record_path": f"line[{line_number}]", "reason": "missing_event_id"})
                continue
            events.append(_Event(
                event_id=f"event:urlhaus:{record_id}", source="urlhaus", source_record_id=record_id,
                raw_ref=_text(row.get("raw_ref")) or str(path), event_time=_text(row.get("date_added")) or None,
                fetched_at=_text(row.get("fetched_at")) or None,
                indicators=({"type": "url", "value": url, "raw_value": url, "first_seen": row.get("date_added"), "path": "url_raw", "derivation": "source_asserted", "extraction_method": "normalized_source_field"},) if url else (),
                claims=(),
            ))
    return events


def _extract_orkl_indicators(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract compatible observations from locally stored ORKL report body text.

    This is intentionally not a claim that an observed value is malicious. It
    records a deterministic source-text occurrence for the five-node adapter.
    URLs already represented as report references or stored document links are
    excluded so citation metadata is not silently reclassified as an IOC.
    """
    body = record.get("body")
    if not isinstance(body, str) or not body:
        return []
    excluded_urls = _orkl_reference_urls(record)
    body_reference_spans = _orkl_body_reference_spans(body)
    observations: list[dict[str, Any]] = []
    url_spans: list[tuple[int, int]] = []
    for match in ORKL_URL_PATTERN.finditer(body):
        raw_value = match.group().rstrip(".,;:!?)]}\"")
        if not raw_value:
            continue
        end = match.start() + len(raw_value)
        url_spans.append((match.start(), end))
        normalized = _normalise_url(raw_value)
        if (
            normalized is None
            or normalized in excluded_urls
            or any(start <= match.start() < end for start, end in body_reference_spans)
            or _orkl_url_is_inline_citation(body, match.start())
        ):
            continue
        observations.append(_orkl_observation("url", raw_value, normalized, match.start(), end))
    for match in ORKL_DOMAIN_PATTERN.finditer(body):
        if any(start <= match.start() < end for start, end in url_spans):
            continue
        raw_value = match.group().rstrip(".,;:!?)]}\"")
        normalized = _normalise_domain(raw_value)
        if (
            normalized is None
            or any(start <= match.start() < end for start, end in body_reference_spans)
        ):
            continue
        observations.append(
            _orkl_observation(
                "domain",
                raw_value,
                normalized,
                match.start(),
                match.start() + len(raw_value),
            )
        )
    for match in ORKL_IP_PATTERN.finditer(body):
        if any(start <= match.start() < end for start, end in url_spans):
            continue
        raw_value = match.group()
        try:
            normalized_ip = ipaddress.ip_address(raw_value).compressed.lower()
        except ValueError:
            continue
        observations.append(_orkl_observation("ip", raw_value, normalized_ip, match.start(), match.end()))
    return observations


def _orkl_observation(indicator_type: str, raw_value: str, value: str, start: int, end: int) -> dict[str, Any]:
    return {
        "type": indicator_type,
        "value": value,
        "raw_value": raw_value,
        "path": f"body.char[{start}:{end}]",
        "character_start": start,
        "character_end": end,
        "derivation": "deterministic_orkl_body_ioc_extraction",
        "extraction_method": "text_extraction",
    }


def _orkl_reference_urls(record: dict[str, Any]) -> set[str]:
    values: list[Any] = list(record.get("references") or [])
    for document in record.get("document_refs") or []:
        if isinstance(document, dict):
            values.append(document.get("url"))
    result: set[str] = set()
    for value in values:
        normalized = _normalise_url(str(value or ""))
        if normalized:
            result.add(normalized)
    return result


def _orkl_body_reference_spans(body: str) -> list[tuple[int, int]]:
    """Return explicitly headed bibliography/reference sections in a report body.

    Only standalone, conventional headings are classified. Text that cannot be
    classified this way remains a body mention and is not promoted by inference.
    """
    spans: list[tuple[int, int]] = []
    for match in re.finditer(
        r"(?im)^\s*(?:\d+(?:\.\d+)*\.?\s+)?(?:recommended\s+reading\s+)?"
        r"(?:references?|citations?|bibliography|websites?)\s*:?\s*$",
        body,
    ):
        next_boundary = next(
            (
                boundary.start()
                for boundary in ORKL_SECTION_BOUNDARY_PATTERN.finditer(body, match.end())
            ),
            len(body),
        )
        spans.append((match.start(), next_boundary))
    return spans


def _orkl_url_is_inline_citation(body: str, offset: int) -> bool:
    """Identify a URL in an explicitly citation-like line without inferring IOC meaning."""
    line_start = body.rfind("\n", 0, offset) + 1
    line_end = body.find("\n", offset)
    line = body[line_start:len(body) if line_end < 0 else line_end]
    preceding_context = body[max(0, line_start - 160):line_start]
    if re.search(r"(?i)\b(?:accessed|published|retrieved)\b", line + preceding_context):
        return True
    return False


def _misp_attribute_groups(event: dict[str, Any]) -> Iterable[tuple[str, list[Any]]]:
    if event.get("deleted"):
        return
    yield "Event", [
        item for item in (event.get("Attribute") or [])
        if isinstance(item, dict) and not item.get("deleted")
    ]
    for index, obj in enumerate(event.get("Object") or []):
        if isinstance(obj, dict) and not obj.get("deleted"):
            yield f"Event.Object[{index}]", [
                item for item in (obj.get("Attribute") or [])
                if isinstance(item, dict) and not item.get("deleted")
            ]


def _split_misp_attribute(raw_type: Any, raw_value: Any) -> list[tuple[str, Any]]:
    type_text = str(raw_type or "").lower()
    if "|" not in type_text:
        if type_text in {"ip-src", "ip-dst"} and "|" in str(raw_value or ""):
            value, port = str(raw_value).split("|", 1)
            return [(type_text, value), ("port", port)]
        return [(type_text, raw_value)]
    types = type_text.split("|")
    values = str(raw_value or "").split("|", len(types) - 1)
    if len(types) == len(values):
        return list(zip(types, values, strict=True))
    return [(type_text, raw_value)]


def _normalise_indicator(raw_type: Any, raw_value: Any, source: str) -> tuple[str, str] | None:
    type_text = str(raw_type or "").strip().lower()
    mapping = OTX_TYPE_MAP if source in {"otx", "orkl", "urlhaus"} else MISP_TYPE_MAP
    node_type = mapping.get(type_text)
    value = str(raw_value or "").strip()
    if not node_type or not value:
        return None
    if node_type == "ip":
        try:
            return node_type, ipaddress.ip_address(value).compressed.lower()
        except ValueError:
            return None
    if node_type == "domain":
        domain = _normalise_domain(value)
        return (node_type, domain) if domain else None
    url = normalize_misp_url(value) if source == "circl_misp" else _normalise_url(value)
    return (node_type, url) if url else None


def _normalise_domain(value: str) -> str | None:
    return normalize_domain(value)


def _normalise_url(value: str) -> str | None:
    return normalize_url(value)


def _project_url(
    url: str,
    event: _Event,
    indicator: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> None:
    host = urlsplit(url).hostname or ""
    try:
        host = ipaddress.ip_address(host).compressed.lower()
        node_type, relation = "ip", "url_resolves_to_ip"
    except ValueError:
        domain = _normalise_domain(host)
        if not domain:
            return
        host, node_type, relation = domain, "domain", "url_hosted_on_domain"
    target_id = _node_id(node_type, host)
    _add_node(nodes, node_type, target_id, host)
    _add_evidence(
        edges,
        _node_id("url", url),
        relation,
        target_id,
        source=event.source,
        raw_ref=event.raw_ref,
        observed_at=indicator.get("first_seen") or event.event_time,
        derivation="deterministic_url_hostname_parse",
        record_path=indicator.get("path"),
    )


def _join_pdns(
    root: Path,
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], list[dict[str, Any]]],
    rejected: list[dict[str, Any]],
) -> None:
    wanted_domains = {row["value"] for row in nodes.values() if row["type"] == "domain"}
    wanted_ips = {row["value"] for row in nodes.values() if row["type"] == "ip"}
    for domain_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        snapshots = sorted(domain_dir.glob("*.json"))
        if not snapshots:
            continue
        path = snapshots[-1]
        raw_ref = path.as_posix()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            projected = project_pdns_raw(raw)
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError) as exc:
            rejected.append({"source": "pdns", "raw_ref": raw_ref, "reason": "invalid_pdns_snapshot", "error": str(exc)})
            continue
        domain = _normalise_domain(str(projected.get("domain") or ""))
        domain_wanted = domain is not None and domain in wanted_domains
        domain_id = _node_id("domain", domain) if domain_wanted and domain is not None else None
        for index, resolution in enumerate(projected.get("resolutions") or []):
            if str(resolution.get("record_type") or "").upper() not in {"A", "AAAA"}:
                continue
            try:
                ip = ipaddress.ip_address(str(resolution.get("ip") or resolution.get("value") or "")).compressed.lower()
            except ValueError:
                continue
            ip_wanted = ip in wanted_ips
            if not domain_wanted and not ip_wanted:
                continue
            ip_id = _node_id("ip", ip)
            observed_at = _text(resolution.get("last_seen") or resolution.get("first_seen") or projected.get("fetched_at"))
            if domain_wanted and domain_id is not None:
                _add_node(nodes, "ip", ip_id, ip)
                _add_evidence(
                    edges,
                    domain_id,
                    "domain_resolves_to_ip",
                    ip_id,
                    source="pdns",
                    raw_ref=raw_ref,
                    observed_at=observed_at,
                    derivation="source_asserted",
                    record_path=f"payload.passive_dns[{index}]",
                )
            asn = _normalise_asn(resolution.get("asn"))
            if asn and (domain_wanted or ip_wanted):
                _add_node(nodes, "ip", ip_id, ip)
                asn_id = _node_id("asn", asn)
                _add_node(nodes, "asn", asn_id, asn, {"name": _text(resolution.get("asn_name"))})
                _add_evidence(
                    edges,
                    ip_id,
                    "ip_in_asn",
                    asn_id,
                    source="pdns",
                    raw_ref=raw_ref,
                    observed_at=observed_at,
                    derivation="source_asserted",
                    record_path=f"payload.passive_dns[{index}].asn",
                )


def _normalise_asn(value: Any) -> str | None:
    match = re.fullmatch(r"AS(\d+)", str(value or "").strip(), re.I)
    return f"AS{int(match.group(1))}" if match else None


def _node_id(node_type: str, value: str) -> str:
    if node_type == "event":
        return value
    return f"{node_type}:{hashlib.sha256(value.encode()).hexdigest()}"


def _add_node(
    nodes: dict[str, dict[str, Any]],
    node_type: str,
    node_id: str,
    value: str,
    properties: dict[str, Any] | None = None,
) -> None:
    row: dict[str, Any] = {"node_id": node_id, "type": node_type, "value": value}
    if properties:
        row["properties"] = {key: val for key, val in sorted(properties.items()) if val is not None}
    nodes.setdefault(node_id, row)


def _add_evidence(
    edges: dict[tuple[str, str, str], list[dict[str, Any]]],
    source_id: str,
    relation: str,
    target_id: str,
    *,
    source: str,
    raw_ref: str,
    observed_at: Any,
    derivation: str,
    record_path: Any,
    raw_value: Any = None,
    extraction_method: Any = None,
    network_port: Any = None,
) -> None:
    evidence = {
        "source": source,
        "raw_ref": raw_ref,
        "observed_at": _text(observed_at),
        "derivation": derivation,
        "record_path": _text(record_path),
    }
    if raw_value is not None:
        evidence["raw_value"] = _text(raw_value)
    if extraction_method is not None:
        evidence["extraction_method"] = _text(extraction_method)
    if network_port is not None:
        evidence["network_port"] = int(network_port)
    bucket = edges[(source_id, relation, target_id)]
    if evidence not in bucket:
        bucket.append(evidence)


def _materialise_edges(edges: dict[tuple[str, str, str], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (source_id, relation, target_id), evidence in sorted(edges.items()):
        edge_key = f"{source_id}|{relation}|{target_id}"
        rows.append(
            {
                "edge_id": "edge:" + hashlib.sha256(edge_key.encode()).hexdigest(),
                "source_id": source_id,
                "relation": relation,
                "target_id": target_id,
                "evidence": sorted(evidence, key=lambda row: json.dumps(row, sort_keys=True)),
            }
        )
    return rows


def _otx_claims(payload: dict[str, Any], event_id: str, raw_ref: str) -> list[dict[str, Any]]:
    adversary = _text(payload.get("adversary"))
    if not adversary:
        return []
    return [_claim(event_id, "otx", adversary, "adversary", raw_ref)]


def _misp_claims(event: dict[str, Any], event_id: str, raw_ref: str) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    tags: list[tuple[str, Any]] = [(f"Event.Tag[{i}]", tag) for i, tag in enumerate(event.get("Tag") or [])]
    for prefix, attrs in _misp_attribute_groups(event):
        for ai, attr in enumerate(attrs):
            if isinstance(attr, dict):
                tags.extend((f"{prefix}.Attribute[{ai}].Tag[{ti}]", tag) for ti, tag in enumerate(attr.get("Tag") or []))
    pattern = re.compile(r'^misp-galaxy:(?:threat-actor|[^=]*intrusion-set)="(?P<label>.*)"$', re.I)
    for path, tag in tags:
        name = tag.get("name") if isinstance(tag, dict) else None
        match = pattern.match(str(name or ""))
        if match:
            claims.append(_claim(event_id, "circl_misp", match.group("label"), path, raw_ref))
    return claims


def _claim(event_id: str, source: str, value: str, field: str, raw_ref: str) -> dict[str, Any]:
    key = f"{event_id}|{field}|{value}"
    return {
        "claim_id": "claim:" + hashlib.sha256(key.encode()).hexdigest(),
        "event_id": event_id,
        "source": source,
        "source_field": field,
        "raw_value": value,
        "raw_ref": raw_ref,
        "claim_status": "candidate",
        "usage": "provenance_only_not_graph_label",
    }


def _rejection_reason(raw_type: Any, raw_value: Any, source: str) -> str:
    mapping = OTX_TYPE_MAP if source in {"otx", "orkl", "urlhaus"} else MISP_TYPE_MAP
    if str(raw_type or "").strip().lower() not in mapping:
        return "unsupported_ioc_type"
    if not str(raw_value or "").strip():
        return "empty_ioc_value"
    return "invalid_ioc_format"


def _source_mapping() -> dict[str, Any]:
    return {
        "version": 1,
        "node_types": list(NODE_TYPES),
        "otx_indicator_type_mapping": dict(sorted(OTX_TYPE_MAP.items())),
        "misp_attribute_type_mapping": dict(sorted(MISP_TYPE_MAP.items())),
        "orkl_intermediate_mapping": {
            "status": "deterministic_body_text_projection",
            "source_field": "intermediate_records.body (locally normalized ORKL plain text)",
            "compatible_observations": ["ip", "http_url", "https_url", "hxxp_deobfuscated_url", "url_hostname_derived_domain"],
            "provenance": "raw source reference plus body character offsets and raw matched value",
            "actor_candidates": "provenance_only_not_graph_label",
            "external_references": "not_reinterpreted_as_iocs",
            "standalone_body_domains": "deterministic_domain_pattern_with_tld_allowlist_and_reference_section_exclusion",
        },
        "urlhaus_normalized_mapping": {
            "source_field": "normalized/urls.jsonl.url_raw",
            "compatible_observations": ["http_url", "https_url", "url_hostname_derived_domain"],
            "provenance": "normalized row raw_ref, raw_sha256, source_record_id, and url_raw field",
            "payload_blobs": "not read or projected",
            "source_threat_and_tags": "not promoted to graph labels",
        },
        "relations": {
            key: {"source_type": value[0], "trail_name": value[1], "target_type": value[2]}
            for key, value in sorted(RELATION_MAP.items())
        },
        "derivation_policy": {
            "event_membership": "source_asserted",
            "url_host_relation": "deterministic_url_hostname_parse",
            "domain_ip_relation": "local_pdns_evidence_only",
            "ip_asn_relation": "explicit_asn_in_local_pdns_only",
            "missing_asn": "omit_node_and_edge_and_report_coverage_gap",
        },
    }


def _consumer_contract(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "consumer": "TRAIL graph_export five-node schema",
        "node_type_mapping": {node_type: node_type for node_type in NODE_TYPES},
        "edge_type_mapping": {
            relation: {"source_type": source, "edge_type": edge, "target_type": target}
            for relation, (source, edge, target) in sorted(RELATION_MAP.items())
        },
        "validation": {
            "expected_node_types": list(NODE_TYPES),
            "allowed_edge_types": sorted({value[1] for value in RELATION_MAP.values()}),
            "reverse_edges": "consumer_adds_reverse_edges_for_message_passing",
            "training_or_model_execution_performed": False,
            **validation,
        },
    }


def _validate_graph(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, Any]:
    """Fail closed if projected endpoints do not match old TRAIL semantics."""
    node_types = {row["node_id"]: row["type"] for row in nodes}
    errors: list[str] = []
    for edge in edges:
        source_type = node_types.get(edge["source_id"])
        target_type = node_types.get(edge["target_id"])
        expected = RELATION_MAP.get(edge["relation"])
        if expected is None:
            errors.append(f"unknown relation: {edge['relation']}")
        elif (source_type, expected[1], target_type) != expected:
            errors.append(
                f"invalid endpoints for {edge['relation']}: {source_type}->{target_type}"
            )
        evidence = edge.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"missing evidence for {edge.get('edge_id')}")
        else:
            for item in evidence:
                if not isinstance(item, dict) or any(key not in item for key in ("source", "raw_ref", "observed_at", "derivation", "record_path")):
                    errors.append(f"incomplete evidence for {edge.get('edge_id')}")
    invalid_node_types = sorted(set(node_types.values()) - set(NODE_TYPES))
    if invalid_node_types:
        errors.append(f"unknown node types: {invalid_node_types}")
    if errors:
        raise ValueError("TRAIL consumer compatibility validation failed: " + "; ".join(errors))
    return {
        "status": "passed",
        "validated_node_count": len(nodes),
        "validated_edge_count": len(edges),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _content_hash(output_dir: Path, names: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(names):
        digest.update(name.encode())
        digest.update(b"\0")
        with (output_dir / name).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _deduplicate_rejected(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Remove exact duplicate rejection rows while preserving deterministic order."""
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for row in rows:
        key = _stable_value(row)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        unique.append(row)
    return unique, duplicate_count


def _rejection_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    reason_counts = Counter(str(row.get("reason") or "unknown") for row in rows)
    rejected_event_ids = {
        str(row["event_id"])
        for row in rows
        if row.get("event_id")
    }
    dropped_event_ids = {
        str(row["event_id"])
        for row in rows
        if row.get("reason") == "no_supported_iocs" and row.get("event_id")
    }
    invalid_value_reasons = {"empty_ioc_value", "invalid_ioc_format"}
    return {
        "rejected_event_count": len(rejected_event_ids),
        "unsupported_ioc_type_count": reason_counts.get("unsupported_ioc_type", 0),
        "invalid_ioc_value_count": sum(reason_counts.get(reason, 0) for reason in invalid_value_reasons),
        "dropped_event_count": len(dropped_event_ids),
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
    }


def _validate_claim_provenance(
    event_rows: Iterable[dict[str, Any]], claims: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Verify the separate claim artifact is reachable from its Event rows."""
    events = {str(row.get("event_id")): row for row in event_rows}
    claim_rows = list(claims)
    claims_by_id = {str(row.get("claim_id")): row for row in claim_rows if row.get("claim_id")}
    referenced_ids = {
        str(claim_id)
        for row in events.values()
        for claim_id in row.get("source_claim_ids") or []
    }
    errors: list[str] = []
    duplicate_claim_ids = len(claims_by_id) != len(claim_rows)
    if duplicate_claim_ids:
        errors.append("duplicate or missing source claim IDs")
    unknown_references = sorted(referenced_ids - set(claims_by_id))
    if unknown_references:
        errors.append("Event rows reference unknown source claim IDs")
    missing_references = sorted(set(claims_by_id) - referenced_ids)
    if missing_references:
        errors.append("source claims are not referenced by an Event row")
    wrong_event_references = sorted(
        claim_id
        for claim_id, claim in claims_by_id.items()
        if str(claim.get("event_id")) not in events
        or claim_id not in set(events.get(str(claim.get("event_id")), {}).get("source_claim_ids") or [])
    )
    if wrong_event_references:
        errors.append("source claim event_id does not match its Event reference")
    return {
        "status": "passed" if not errors else "failed",
        "claim_count": len(claim_rows),
        "event_count": len(events),
        "events_with_claims": sum(bool(row.get("source_claim_ids")) for row in events.values()),
        "unreferenced_claim_count": len(missing_references),
        "unknown_reference_count": len(unknown_references),
        "errors": errors,
        "claim_status_policy": "candidate provenance only; never a graph label",
    }


def _event_evidence_metrics(
    event_rows: Iterable[dict[str, Any]],
    edges: Iterable[dict[str, Any]],
    attempted_event_count: int,
) -> dict[str, int]:
    """Keep zero-network, evidence-bearing, and isolated populations distinct."""
    rows = list(event_rows)
    network_types = {"domain", "ip", "url"}
    all_evidence_ids = {
        str(row["event_id"])
        for row in rows
        if row.get("ioc_type_counts")
    }
    network_evidence_ids = {
        str(row["event_id"])
        for row in rows
        if set(row.get("ioc_type_counts") or {}) & network_types
    }
    edge_source_ids = {
        str(edge.get("source_id"))
        for edge in edges
        if str(edge.get("relation") or "").startswith("event_contains_")
    }
    return {
        "all_evidence_event_count": len(all_evidence_ids),
        "network_ioc_event_count": len(network_evidence_ids),
        "zero_network_ioc_event_count": max(0, attempted_event_count - len(network_evidence_ids)),
        "non_network_only_event_count": len(all_evidence_ids - network_evidence_ids),
        "isolated_event_count": len({str(row["event_id"]) for row in rows} - edge_source_ids),
    }
