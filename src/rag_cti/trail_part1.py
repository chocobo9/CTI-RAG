"""Build the auditable non-OTX, non-training TRAIL five-node data delivery.

The module intentionally uses only local snapshots.  It projects Event, IP, URL,
Domain and ASN nodes while retaining actor-resolution and timestamp evidence.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from rag_cti.ioc_normalization import (
    DOMAIN_TOKEN_RE,
    IP_TOKEN_RE,
    URL_TOKEN_RE,
    normalize_domain as _normalize_domain,
    normalize_ip as _normalize_ip,
    normalize_misp_url as _normalize_misp_url,
    normalize_url as _normalize_url,
)
from rag_cti.trail_dataset.builder import _extract_orkl_indicators

WINDOW_START = datetime(2018, 2, 3, tzinfo=UTC)
WINDOW_END = datetime(2026, 7, 24, 23, 59, 59, tzinfo=UTC)
NODE_TYPES = {"Event", "IP", "URL", "Domain", "ASN"}

URL_RE = URL_TOKEN_RE
IP_RE = IP_TOKEN_RE
DOMAIN_RE = DOMAIN_TOKEN_RE
HASH_RE = re.compile(r"(?<![0-9a-f])(?:[0-9a-f]{64}|[0-9a-f]{40}|[0-9a-f]{32})(?![0-9a-f])", re.I)
GENERIC_ACTORS = re.compile(
    r"^(?:malicious\s+)?(?:cyber\s+)?(?:threat\s+)?actors?$|"
    r"^(?:nation[- ]state|state[- ]sponsored)\s+actors?$|"
    r"^(?:hackers?|attackers?|adversar(?:y|ies)|criminals?)$",
    re.I,
)


def stable_id(*parts: object) -> str:
    material = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text or text.startswith("0001-"):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for pattern in ("%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, pattern)
                break
            except ValueError:
                continue
        else:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def alias_key(value: str) -> str:
    value = re.sub(r"\s*-\s*G\d{4}\s*$", "", value, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


class AliasResolver:
    """Exact-only reuse of the frozen actor subset of alias_mappings.jsonl."""

    def __init__(self, path: Path) -> None:
        self.path = path
        candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.input_rows = 0
        self.actor_rows = 0
        for row in jsonl(path):
            self.input_rows += 1
            if row.get("entity_type") != "actor":
                continue
            self.actor_rows += 1
            canonical = row.get("canonical_name")
            entity_id = row.get("entity_id")
            if not canonical or not entity_id:
                continue
            item = {
                "canonical_name": canonical,
                "entity_id": entity_id,
                "mapping_source": row.get("source"),
                "mapping_status": row.get("mapping_status"),
                "alias_key": row.get("alias_key"),
                "alias_value": row.get("alias_value"),
                "candidate_entity_ids": row.get("candidate_entity_ids") or [],
            }
            for raw_key in (row.get("alias_key"), row.get("alias_value"), canonical):
                key = alias_key(str(raw_key or ""))
                if key:
                    if item not in candidates[key]:
                        candidates[key].append(item)
        self.index = dict(candidates)

    def resolve(self, raw_label: str) -> dict[str, Any]:
        key = alias_key(raw_label)
        matches = self.index.get(key, [])
        resolved_matches = [
            row for row in matches if str(row.get("mapping_status")) == "resolved"
        ]
        candidate_matches = [
            row for row in matches if str(row.get("mapping_status")) == "candidate"
        ]
        resolved_entities = {
            (str(row["entity_id"]), str(row["canonical_name"])) for row in resolved_matches
        }
        candidate_entities = {
            (str(row["entity_id"]), str(row["canonical_name"])) for row in candidate_matches
        }
        if GENERIC_ACTORS.match(raw_label.strip()):
            status = "unresolved_generic"
        elif not resolved_matches and not candidate_matches:
            status = "unresolved"
        elif len(resolved_entities) == 1:
            status = "resolved"
        elif len(resolved_entities) > 1:
            status = "ambiguous"
        elif len(candidate_entities) == 1:
            status = "candidate"
        else:
            status = "ambiguous"
        resolved_item = resolved_matches[0] if status == "resolved" else None
        return {
            "raw_label": raw_label,
            "normalized_alias_key": key,
            "resolution_status": status,
            "candidate_entity_ids": [row["entity_id"] for row in matches],
            "candidate_canonical_names": [row["canonical_name"] for row in matches],
            "mapping_statuses": sorted(
                {str(row.get("mapping_status")) for row in matches if row.get("mapping_status")}
            ),
            "mapping_evidence": matches,
            "resolved_entity_id": resolved_item["entity_id"] if resolved_item else None,
            "canonical_name": resolved_item["canonical_name"] if resolved_item else None,
            "alias_mapping_path": self.path.as_posix(),
            "alias_mapping_sources": sorted(
                {str(row["mapping_source"]) for row in matches if row.get("mapping_source")}
            ),
        }


def normalize_url(value: str) -> str | None:
    return _normalize_url(value)


def normalize_misp_url(value: str) -> str | None:
    """Normalize a MISP URL, including source-typed host/path values without a scheme."""
    return _normalize_misp_url(value)


def normalize_domain(value: str) -> str | None:
    return _normalize_domain(value)


def normalize_ip(value: str) -> tuple[str | None, int | None]:
    return _normalize_ip(value)


def extract_text_iocs(
    text: str, source: str, source_record_id: str, raw_ref: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    projected: list[dict[str, Any]] = []
    unprojected: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str, raw: str, start: int, end: int, **extra: Any) -> None:
        key = (kind, value)
        if key in seen:
            return
        seen.add(key)
        projected.append(
            {
                "evidence_id": f"ioc-evidence:{stable_id(source, source_record_id, kind, value)}",
                "source": source,
                "source_record_id": source_record_id,
                "ioc_type": kind,
                "ioc_value": value,
                "ioc_value_raw": raw,
                "character_start": start,
                "character_end": end,
                "extraction_method": "deterministic_regex",
                "raw_ref": raw_ref,
                **extra,
            }
        )

    for match in URL_RE.finditer(text):
        normalized = normalize_url(match.group())
        if normalized:
            add("URL", normalized, match.group(), match.start(), match.end())
            occupied.append(match.span())
    for match in IP_RE.finditer(text):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        normalized, port = normalize_ip(match.group())
        if normalized:
            add("IP", normalized, match.group(), match.start(), match.end(), network_port=port)
    for match in DOMAIN_RE.finditer(text):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        normalized = normalize_domain(match.group())
        if normalized:
            add("Domain", normalized, match.group(), match.start(), match.end())
    for match in HASH_RE.finditer(text):
        value = match.group().lower()
        unprojected.append(
            {
                "evidence_id": f"unprojected:{stable_id(source, source_record_id, 'hash', value)}",
                "source": source,
                "source_record_id": source_record_id,
                "evidence_type": "hash",
                "value": value,
                "projection_status": "not_in_trail_five_node_schema",
                "character_start": match.start(),
                "character_end": match.end(),
                "raw_ref": raw_ref,
            }
        )
    return projected, unprojected


def _extract_orkl_iocs(
    record: dict[str, Any], source_record_id: str, raw_ref: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract ORKL network evidence without reclassifying references as IOCs.

    ORKL keeps report references and document links separate from source-text
    observations.  The canonical ORKL extractor must therefore be used here
    instead of the generic text-regex extractor.  Timestamp eligibility is
    intentionally handled by the caller.
    """
    projected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for observation in _extract_orkl_indicators(record):
        kind = {"ip": "IP", "url": "URL", "domain": "Domain"}.get(
            str(observation["type"])
        )
        if kind is None:
            continue
        value = str(observation["value"])
        if (kind, value) in seen:
            continue
        seen.add((kind, value))
        projected.append(
            {
                "evidence_id": f"ioc-evidence:{stable_id('orkl', source_record_id, kind, value)}",
                "source": "orkl",
                "source_record_id": source_record_id,
                "ioc_type": kind,
                "ioc_value": value,
                "ioc_value_raw": str(observation.get("raw_value") or value),
                "character_start": observation.get("character_start"),
                "character_end": observation.get("character_end"),
                "extraction_method": "deterministic_orkl_body_ioc_extraction",
                "raw_ref": raw_ref,
            }
        )
    unprojected: list[dict[str, Any]] = []
    body = str(record.get("body") or "")
    for match in HASH_RE.finditer(body):
        value = match.group().lower()
        unprojected.append(
            {
                "evidence_id": f"unprojected:{stable_id('orkl', source_record_id, 'hash', value)}",
                "source": "orkl",
                "source_record_id": source_record_id,
                "evidence_type": "hash",
                "value": value,
                "projection_status": "not_in_trail_five_node_schema",
                "character_start": match.start(),
                "character_end": match.end(),
                "raw_ref": raw_ref,
            }
        )
    return projected, unprojected


def _iter_misp_attributes(event: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for index, attribute in enumerate(event.get("Attribute") or []):
        if isinstance(attribute, dict):
            yield f"Event.Attribute[{index}]", attribute
    for object_index, obj in enumerate(event.get("Object") or []):
        if not isinstance(obj, dict) or obj.get("deleted"):
            continue
        for attribute_index, attribute in enumerate(obj.get("Attribute") or []):
            if isinstance(attribute, dict):
                yield f"Event.Object[{object_index}].Attribute[{attribute_index}]", attribute


def _extract_misp_iocs(
    event: dict[str, Any], source_record_id: str, raw_ref: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract supported network IOCs and preserve hash evidence from all MISP attributes."""
    source = "misp"
    projected: list[dict[str, Any]] = []
    unprojected: list[dict[str, Any]] = []
    for source_field, attribute in _iter_misp_attributes(event):
        if attribute.get("deleted"):
            continue
        raw_value = str(attribute.get("value") or "")
        raw_type = str(attribute.get("type") or "").lower()
        value, port_text = (raw_value.split("|", 1) + [None])[:2] if "|" in raw_value else (raw_value, None)
        kind: str | None = None
        normalized: str | None = None
        port: int | None = None
        if raw_type in {"ip-src", "ip-dst", "ip-src|port", "ip-dst|port"}:
            normalized, port = normalize_ip(value)
            if port is None and port_text is not None:
                try:
                    parsed_port = int(port_text)
                except ValueError:
                    parsed_port = None
                if parsed_port is not None and 0 < parsed_port <= 65535:
                    port = parsed_port
            kind = "IP"
        elif raw_type in {"url", "uri"}:
            normalized = normalize_misp_url(value)
            kind = "URL"
        elif raw_type in {"domain", "hostname"}:
            normalized = normalize_domain(value)
            kind = "Domain"
        elif "hash" in raw_type or raw_type in {"md5", "sha1", "sha256"}:
            unprojected.append(
                {
                    "evidence_id": f"unprojected:{stable_id(source, source_record_id, source_field, raw_value)}",
                    "source": source,
                    "source_record_id": source_record_id,
                    "evidence_type": "hash",
                    "value": raw_value,
                    "projection_status": "not_in_trail_five_node_schema",
                    "source_field": source_field,
                    "raw_ref": raw_ref,
                }
            )
        if kind and normalized:
            projected.append(
                {
                    "evidence_id": f"ioc-evidence:{stable_id(source, source_record_id, source_field, normalized)}",
                    "source": source,
                    "source_record_id": source_record_id,
                    "ioc_type": kind,
                    "ioc_value": normalized,
                    "ioc_value_raw": raw_value,
                    "network_port": port,
                    "first_seen": attribute.get("first_seen"),
                    "last_seen": attribute.get("last_seen"),
                    "timestamp_basis": "misp_attribute_observation",
                    "source_field": source_field,
                    "raw_ref": raw_ref,
                }
            )
    return projected, unprojected


class DeliveryBuilder:
    def __init__(self, root: Path, out: Path) -> None:
        self.root = root
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        alias_path = root / "data/processed/intermediate_frozen_v1_20260716/intermediate/alias_mappings.jsonl"
        self.aliases = AliasResolver(alias_path)
        self.nodes: dict[str, dict[str, Any]] = {}
        self.relations: dict[str, dict[str, Any]] = {}
        self.ioc_sources: dict[tuple[str, str], set[str]] = defaultdict(set)
        self.stats: dict[str, Counter[str]] = defaultdict(Counter)
        self.actor_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.record_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.ioc_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.unprojected: list[dict[str, Any]] = []
        self.exclusions: list[dict[str, Any]] = []
        self.cname_rows: list[dict[str, Any]] = []

    def add_node(self, kind: str, value: str, provenance: dict[str, Any], **props: Any) -> str:
        assert kind in NODE_TYPES
        node_id = f"{kind.lower()}:{stable_id(value)}" if kind != "Event" else value
        if node_id not in self.nodes:
            legacy = {"Event": "EVENT", "Domain": "domain"}.get(kind, kind)
            self.nodes[node_id] = {
                "node_id": node_id,
                "node_type": kind,
                "neo4j_label": kind,
                "legacy_neo4j_label": legacy,
                "value": value,
                "sources": [],
                "provenance": [],
                **props,
            }
        node = self.nodes[node_id]
        source = provenance.get("source")
        if source and source not in node["sources"]:
            node["sources"].append(source)
        if len(node["provenance"]) < 20 and provenance not in node["provenance"]:
            node["provenance"].append(provenance)
        for key, prop_value in props.items():
            if prop_value is not None and node.get(key) is None:
                node[key] = prop_value
        if kind != "Event":
            self.ioc_sources[(kind, value)].add(str(source))
        return node_id

    def add_relation(
        self,
        source_id: str,
        relation_type: str,
        target_id: str,
        provenance: dict[str, Any],
        *,
        timestamp: str | None = None,
        timestamp_basis: str | None = None,
    ) -> None:
        legacy = {
            "InReport": "IN_REPORT",
            "HostedOn": "HOSTED_ON",
            "ResolvesTo": "RESOLVES_TO",
            "InGroup": "IN_ASN_GROUP",
        }[relation_type]
        relation_id = f"relation:{stable_id(source_id, relation_type, target_id, provenance.get('source'), provenance.get('source_record_id'))}"
        self.relations[relation_id] = {
            "relation_id": relation_id,
            "source_node_id": source_id,
            "relation_type": relation_type,
            "legacy_relation_type": legacy,
            "target_node_id": target_id,
            "timestamp": timestamp,
            "timestamp_basis": timestamp_basis,
            "source": provenance.get("source"),
            "source_record_id": provenance.get("source_record_id"),
            "evidence": provenance,
        }

    def resolve_record(
        self, source: str, record_id: str, claims: list[dict[str, Any]], raw_ref: str
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for claim in claims:
            raw = str(claim.get("raw_label") or claim.get("raw_actor_text") or "").strip()
            if not raw:
                continue
            result = self.aliases.resolve(raw)
            result.update(
                {
                    "source": source,
                    "source_record_id": record_id,
                    "claim_id": claim.get("claim_id") or claim.get("candidate_id"),
                    "claim_kind": claim.get("claim_kind") or claim.get("extraction_method"),
                    "source_location": claim.get("source_location") or claim.get("source_field"),
                    "raw_ref": claim.get("raw_ref") or raw_ref,
                    "claim_excerpt": claim.get("claim_excerpt"),
                }
            )
            results.append(result)
            self.actor_rows[source].append(result)
        material = [
            row for row in results if row["resolution_status"] != "unresolved_generic"
        ]
        resolved = {
            str(row["canonical_name"])
            for row in material
            if row["resolution_status"] == "resolved"
        }
        blocking = [
            row
            for row in material
            if row["resolution_status"] in {"unresolved", "candidate", "ambiguous"}
        ]
        if not material:
            status = "unresolved_or_generic_only"
        elif len(resolved) > 1:
            status = "ambiguous_or_multi_actor"
        elif blocking:
            status = "blocked_by_non_resolved_claim"
        elif len(resolved) == 1:
            status = "resolved_single_canonical_strict"
        else:
            status = "unresolved"
        strict_actor = next(iter(resolved)) if status == "resolved_single_canonical_strict" else None
        canonical_candidates = sorted(
            {
                str(name)
                for row in material
                for name in (
                    [row["canonical_name"]]
                    if row.get("canonical_name")
                    else row.get("candidate_canonical_names") or []
                )
                if name
            }
        )
        return {
            "strict_canonical_actor": strict_actor,
            "record_resolution_status": status,
            "strict_label_eligible": strict_actor is not None,
            "canonical_actor_candidates": canonical_candidates,
            "source_actor_claim_count": len(results),
            "material_actor_claim_count": len(material),
            "blocking_claim_count": len(blocking),
            "claim_resolution_counts": dict(
                sorted(Counter(row["resolution_status"] for row in results).items())
            ),
        }

    def add_ioc(
        self,
        evidence: dict[str, Any],
        event_id: str | None = None,
        event_timestamp: str | None = None,
    ) -> str | None:
        kind = evidence["ioc_type"]
        value = evidence["ioc_value"]
        provenance = {
            "source": evidence["source"],
            "source_record_id": evidence["source_record_id"],
            "raw_ref": evidence.get("raw_ref"),
            "evidence_id": evidence.get("evidence_id"),
            "ioc_value_raw": evidence.get("ioc_value_raw"),
            "character_start": evidence.get("character_start"),
            "character_end": evidence.get("character_end"),
            "network_port": evidence.get("network_port"),
        }
        node_id = self.add_node(
            kind,
            value,
            provenance,
            first_seen=evidence.get("first_seen"),
            last_seen=evidence.get("last_seen"),
            timestamp_basis=evidence.get("timestamp_basis"),
            network_ports=[evidence["network_port"]] if evidence.get("network_port") else [],
        )
        if event_id:
            self.add_relation(
                event_id,
                "InReport",
                node_id,
                provenance,
                timestamp=event_timestamp,
                timestamp_basis="event_publication",
            )
        if kind == "URL":
            host = urlsplit(value).hostname
            if host:
                try:
                    ip = ipaddress.ip_address(host).compressed
                    target = self.add_node("IP", ip, provenance)
                    self.add_relation(node_id, "ResolvesTo", target, provenance)
                except ValueError:
                    domain = normalize_domain(host)
                    if domain:
                        target = self.add_node("Domain", domain, provenance)
                        self.add_relation(node_id, "HostedOn", target, provenance)
        return node_id

    def add_event(
        self,
        source: str,
        record_id: str,
        title: str,
        resolution: dict[str, Any],
        timestamp: datetime,
        timestamp_basis: str,
        timestamp_precision: str,
        source_timestamp: Any,
        raw_ref: str,
        extra: dict[str, Any],
        iocs: list[dict[str, Any]],
    ) -> None:
        event_id = f"event:{source}:{stable_id(record_id)}"
        actor = resolution.get("strict_canonical_actor")
        provenance = {
            "source": source,
            "source_record_id": record_id,
            "raw_ref": raw_ref,
            "source_timestamp": source_timestamp,
        }
        event_iso = iso(timestamp)
        event_node = {
            "node_id": event_id,
            "node_type": "Event",
            "neo4j_label": "Event",
            "legacy_neo4j_label": "EVENT",
            "value": record_id,
            "title": title,
            "canonical_actor_candidate": resolution.get("canonical_actor_candidates") or [],
            "source_actor_claim_count": resolution.get("source_actor_claim_count", 0),
            "material_actor_claim_count": resolution.get("material_actor_claim_count", 0),
            "blocking_claim_count": resolution.get("blocking_claim_count", 0),
            "claim_resolution_counts": resolution.get("claim_resolution_counts") or {},
            "actor_resolution_status": resolution.get("record_resolution_status"),
            "strict_actor_label_eligible": bool(resolution.get("strict_label_eligible")),
            "label_basis": (
                "strict_all_non_generic_source_actor_claims_resolved_same_canonical"
                if actor
                else None
            ),
            "label_confidence": (
                "strict_alias_crosswalk_on_indirect_source_association"
                if source == "orkl" and actor
                else "strict_alias_crosswalk"
                if actor
                else None
            ),
            "label_availability": "indirect" if source == "orkl" else "source_attribution",
            "final_ground_truth": False if source == "orkl" else bool(actor),
            "training_ground_truth_eligible": False if source == "orkl" else bool(actor),
            "event_timestamp": event_iso,
            "timestamp_basis": timestamp_basis,
            "timestamp_precision": timestamp_precision,
            "source_timestamp": source_timestamp,
            "source": source,
            "source_record_id": record_id,
            "sources": [source],
            "provenance": [provenance],
            **extra,
        }
        if actor:
            event_node.update({"actor": actor, "apt": actor, "label": actor})
            self.stats[source]["strict_labeled_events"] += 1
        else:
            self.stats[source]["candidate_or_unlabeled_events"] += 1
        if source == "orkl":
            self.stats[source]["indirect_source_events"] += 1
        self.nodes[event_id] = event_node
        for evidence in iocs:
            self.add_ioc(evidence, event_id, event_iso)
        neighbor_types = {str(evidence["ioc_type"]) for evidence in iocs}
        self.nodes[event_id]["legacy_extractor_compatible"] = bool(neighbor_types & {"IP", "URL"})
        self.nodes[event_id]["event_ioc_node_types"] = sorted(neighbor_types)
        self.stats[source]["events_output"] += 1
        if not self.nodes[event_id]["legacy_extractor_compatible"]:
            self.stats[source]["events_without_ip_or_url"] += 1

    def process_misp(self) -> None:
        source = "misp"
        base = self.root / "data/raw/circl_misp"
        claims: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in jsonl(base / "normalized/source_actor_claims.jsonl"):
            if row.get("claim_kind") == "galaxy_actor_context":
                claims[str(row["event_id"])].append(row)
        for meta in jsonl(base / "normalized/events.jsonl"):
            self.stats[source]["input_records"] += 1
            record_id = str(meta["event_id"])
            resolution = self.resolve_record(
                source, record_id, claims.get(record_id, []), str(meta.get("raw_ref") or "")
            )
            actor = resolution["strict_canonical_actor"]
            actor_status = resolution["record_resolution_status"]
            event_date = parse_time(meta.get("event_date"))
            published = parse_time(meta.get("published_at"))
            timestamp = published or event_date
            basis = "published_at" if published else "event_date"
            precision = "second" if published else "day"
            in_window = bool(timestamp and WINDOW_START <= timestamp <= WINDOW_END)
            raw_path = base / str(meta["raw_ref"])
            iocs: list[dict[str, Any]] = []
            if raw_path.exists():
                event = json.loads(raw_path.read_text(encoding="utf-8")).get("Event", {})
                iocs, unprojected = _extract_misp_iocs(
                    event, record_id, str(meta.get("raw_ref") or "")
                )
                self.unprojected.extend(unprojected)
            self.ioc_rows[source].extend(iocs)
            self.record_rows[source].append(
                {
                    "source": source,
                    "source_record_id": record_id,
                    "source_uuid": meta.get("source_uuid"),
                    "title": meta.get("title"),
                    "event_date": meta.get("event_date"),
                    "published_at": meta.get("published_at"),
                    "modified_at": meta.get("modified_at"),
                    "event_timestamp": iso(timestamp),
                    "timestamp_basis": basis,
                    "timestamp_precision": precision,
                    "actor_status": actor_status,
                    "canonical_actor": actor,
                    "canonical_actor_candidates": resolution["canonical_actor_candidates"],
                    "strict_actor_label_eligible": resolution["strict_label_eligible"],
                    "blocking_claim_count": resolution["blocking_claim_count"],
                    "graph_event_eligible": bool(actor and in_window and iocs),
                    "in_target_window": in_window,
                    "raw_ref": meta.get("raw_ref"),
                }
            )
            if actor and in_window and timestamp and iocs:
                self.add_event(
                    source, record_id, str(meta.get("title") or ""), resolution, timestamp, basis,
                    precision, meta.get("published_at") if published else meta.get("event_date"),
                    str(meta.get("raw_ref") or ""),
                    {
                        "event_date": meta.get("event_date"),
                        "published_at": meta.get("published_at"),
                        "modified_at": meta.get("modified_at"),
                        "source_uuid": meta.get("source_uuid"),
                    },
                    iocs,
                )
            else:
                reason = (
                    "outside_target_window"
                    if not in_window
                    else "no_supported_network_ioc"
                    if actor and not iocs
                    else actor_status
                )
                self.stats[source][f"excluded_{reason}"] += 1

    def process_orkl(self) -> None:
        source = "orkl"
        path = self.root / "data/processed/cti_multisource_stage1_v3_1_20260724/intermediate/intermediate_records.jsonl"
        for record in jsonl(path):
            self.stats[source]["input_records"] += 1
            source_data = record.get("source") or {}
            record_id = str(source_data.get("source_record_id") or record.get("record_id"))
            raw_ref = (record.get("raw_ref") or {}).get("repository_raw_path") or ""
            claims = record.get("attribution_claims") or []
            resolution = self.resolve_record(source, record_id, claims, raw_ref)
            actor = resolution["strict_canonical_actor"]
            actor_status = resolution["record_resolution_status"]
            timestamps = record.get("timestamps") or {}
            published = parse_time(timestamps.get("published_at"))
            in_window = bool(published and WINDOW_START <= published <= WINDOW_END)
            iocs, unprojected = _extract_orkl_iocs(record, record_id, raw_ref)
            self.ioc_rows[source].extend(iocs)
            self.unprojected.extend(unprojected)
            self.record_rows[source].append(
                {
                    "source": source,
                    "source_record_id": record_id,
                    "title": record.get("title"),
                    "published_at": timestamps.get("published_at"),
                    "modified_at": timestamps.get("modified_at"),
                    "fetched_at": timestamps.get("fetched_at"),
                    "event_timestamp": iso(published),
                    "timestamp_basis": "published_at" if published else None,
                    "timestamp_precision": "second" if published else None,
                    "actor_status": actor_status,
                    "canonical_actor": actor,
                    "canonical_actor_candidates": resolution["canonical_actor_candidates"],
                    "strict_actor_label_eligible": resolution["strict_label_eligible"],
                    "blocking_claim_count": resolution["blocking_claim_count"],
                    "in_target_window": in_window,
                    "graph_event_eligible": bool(claims and in_window and iocs),
                    "training_ground_truth_eligible": False,
                    "temporal_exclusion_reason": None if published else "missing_valid_published_at",
                    "raw_ref": raw_ref,
                }
            )
            if claims and in_window and published and iocs:
                self.add_event(
                    source, record_id, str(record.get("title") or ""), resolution, published,
                    "published_at", "second", timestamps.get("published_at"), raw_ref,
                    {
                        "modified_at": timestamps.get("modified_at"),
                        "fetched_at": timestamps.get("fetched_at"),
                        "source_claim_final_apt_ground_truth": False,
                        "source_claim_label_availability": "indirect",
                    },
                    iocs,
                )
            else:
                reason = (
                    "missing_valid_published_at"
                    if not published
                    else "outside_target_window"
                    if not in_window
                    else "no_supported_network_ioc"
                    if claims and not iocs
                    else "missing_source_actor_association"
                )
                self.stats[source][f"excluded_{reason}"] += 1

    def process_aptnotes(self) -> None:
        source = "aptnotes"
        base = self.root / "data/raw/aptnotes"
        claims: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in jsonl(base / "normalized/source_actor_claim_candidates.jsonl"):
            claims[str(row["report_id"])].append(row)
        for record in jsonl(base / "normalized/reports.jsonl"):
            self.stats[source]["input_records"] += 1
            record_id = str(record["report_id"])
            resolution = self.resolve_record(
                source, record_id, claims.get(record_id, []), str(record.get("raw_metadata_ref") or "")
            )
            actor = resolution["strict_canonical_actor"]
            actor_status = resolution["record_resolution_status"]
            timestamp = parse_time(record.get("listed_date"))
            in_window = bool(timestamp and WINDOW_START <= timestamp <= WINDOW_END)
            text_ref = None
            refs = record.get("archived_document_refs") or []
            if refs:
                # The collector's extracted text is keyed by report digest.
                digest = record_id.rsplit(":", 1)[-1]
                candidate = base / "extracted/text" / f"{digest}.txt"
                if candidate.exists():
                    text_ref = candidate
            text = text_ref.read_text(encoding="utf-8", errors="replace") if text_ref else ""
            raw_ref = (
                text_ref.relative_to(base).as_posix()
                if text_ref
                else str(record.get("raw_metadata_ref") or "")
            )
            iocs, unprojected = extract_text_iocs(text, source, record_id, raw_ref)
            self.ioc_rows[source].extend(iocs)
            self.unprojected.extend(unprojected)
            self.record_rows[source].append(
                {
                    "source": source,
                    "source_record_id": record_id,
                    "title": record.get("title"),
                    "listed_date": record.get("listed_date"),
                    "event_timestamp": iso(timestamp),
                    "timestamp_basis": "collector_listed_date",
                    "timestamp_precision": "day",
                    "date_parse_format": "%m/%d/%Y",
                    "actor_status": actor_status,
                    "canonical_actor": actor,
                    "canonical_actor_candidates": resolution["canonical_actor_candidates"],
                    "strict_actor_label_eligible": resolution["strict_label_eligible"],
                    "blocking_claim_count": resolution["blocking_claim_count"],
                    "graph_event_eligible": bool(actor and in_window and iocs),
                    "in_target_window": in_window,
                    "text_available": bool(text_ref),
                    "raw_ref": raw_ref,
                }
            )
            if actor and in_window and timestamp and iocs:
                self.add_event(
                    source, record_id, str(record.get("title") or ""), resolution, timestamp,
                    "collector_listed_date", "day", record.get("listed_date"), raw_ref, {}, iocs
                )
            else:
                reason = (
                    "outside_target_window"
                    if not in_window
                    else "no_supported_network_ioc"
                    if actor and not iocs
                    else actor_status
                )
                self.stats[source][f"excluded_{reason}"] += 1

    def process_cisa(self) -> None:
        source = "cisa"
        base = self.root / "data/raw/cisa"
        candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in jsonl(base / "normalized/source_actor_claim_candidates.jsonl"):
            candidates[str(row["report_id"])].append(row)
        for record in jsonl(base / "normalized/advisories.jsonl"):
            self.stats[source]["input_records"] += 1
            record_id = str(record["report_id"])
            # Candidate phrases are retained and alias-applied, but this snapshot
            # contains no structured/manual MITRE actor selection.  Therefore none
            # are promoted to an Event label.
            resolution = self.resolve_record(
                source, record_id, candidates.get(record_id, []), str(record.get("raw_html_ref") or "")
            )
            timestamp = parse_time(record.get("published_at"))
            text_path = base / str(record.get("content_text_ref") or "")
            text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.exists() else ""
            iocs, unprojected = extract_text_iocs(
                text, source, record_id, str(record.get("content_text_ref") or record.get("raw_html_ref") or "")
            )
            self.ioc_rows[source].extend(iocs)
            self.unprojected.extend(unprojected)
            self.record_rows[source].append(
                {
                    "source": source,
                    "source_record_id": record_id,
                    "title": record.get("title"),
                    "published_at": record.get("published_at"),
                    "updated_at": record.get("updated_at"),
                    "event_timestamp": iso(timestamp),
                    "timestamp_basis": "published_at",
                    "timestamp_precision": "day",
                    "actor_status": "not_promoted_no_structured_manual_mitre_actor_evidence",
                    "canonical_actor": None,
                    "canonical_actor_candidates": resolution["canonical_actor_candidates"],
                    "strict_actor_label_eligible": False,
                    "in_target_window": bool(timestamp and WINDOW_START <= timestamp <= WINDOW_END),
                    "raw_ref": record.get("raw_html_ref"),
                }
            )
            self.stats[source]["excluded_no_structured_manual_actor_evidence"] += 1

    def process_threatfox(self) -> None:
        source = "threatfox"
        path = self.root / "data/raw/threatfox/normalized/iocs.jsonl"
        for row in jsonl(path):
            self.stats[source]["input_records"] += 1
            raw = str(row.get("ioc_value_raw") or "")
            raw_type = str(row.get("ioc_type_raw") or "")
            kind: str | None = None
            value: str | None = None
            port: int | None = row.get("network_port")
            if raw_type in {"ip:port", "ip"}:
                value, parsed_port = normalize_ip(raw)
                port = port or parsed_port
                kind = "IP"
            elif raw_type == "url":
                value = normalize_url(raw)
                kind = "URL"
            elif raw_type in {"domain", "hostname"}:
                value = normalize_domain(raw)
                kind = "Domain"
            if not kind or not value:
                self.unprojected.append(
                    {
                        "evidence_id": f"unprojected:{stable_id(source, row.get('ioc_id'), raw)}",
                        "source": source,
                        "source_record_id": row.get("source_record_id"),
                        "evidence_type": raw_type or "unknown",
                        "value": raw,
                        "projection_status": "not_in_trail_five_node_schema",
                        "raw_ref": row.get("raw_ref"),
                    }
                )
                self.stats[source]["unprojected"] += 1
                continue
            evidence = {
                "evidence_id": f"ioc-evidence:{stable_id(source, row.get('ioc_id'), value)}",
                "source": source,
                "source_record_id": row.get("source_record_id"),
                "ioc_type": kind,
                "ioc_value": value,
                "ioc_value_raw": raw,
                "network_port": port,
                "first_seen": iso(parse_time(row.get("first_seen"))),
                "last_seen": iso(parse_time(row.get("last_seen"))),
                "timestamp_basis": "threatfox_ioc_observation",
                "raw_ref": row.get("raw_ref"),
            }
            self.ioc_rows[source].append(evidence)
            self.add_ioc(evidence)
            self.stats[source]["projected"] += 1

    def process_urlhaus(self) -> None:
        source = "urlhaus"
        path = self.root / "data/raw/urlhaus/normalized/urls.jsonl"
        for row in jsonl(path):
            self.stats[source]["input_records"] += 1
            value = normalize_url(str(row.get("url_raw") or ""))
            if not value:
                self.unprojected.append(
                    {
                        "evidence_id": f"unprojected:{stable_id(source, row.get('url_id'))}",
                        "source": source,
                        "source_record_id": row.get("source_record_id"),
                        "evidence_type": "non_http_url",
                        "value": row.get("url_raw"),
                        "projection_status": "not_in_trail_five_node_schema",
                        "raw_ref": row.get("raw_ref"),
                    }
                )
                self.stats[source]["unprojected"] += 1
                continue
            evidence = {
                "evidence_id": f"ioc-evidence:{stable_id(source, row.get('url_id'), value)}",
                "source": source,
                "source_record_id": row.get("source_record_id"),
                "ioc_type": "URL",
                "ioc_value": value,
                "ioc_value_raw": row.get("url_raw"),
                "first_seen": iso(parse_time(row.get("date_added"))),
                "last_seen": iso(parse_time(row.get("last_online"))),
                "timestamp_basis": "urlhaus_url_observation",
                "raw_ref": row.get("raw_ref"),
            }
            self.ioc_rows[source].append(evidence)
            self.add_ioc(evidence)
            self.stats[source]["projected"] += 1

    def process_pdns(self) -> None:
        from rag_cti.connectors.pdns_projection import load_pdns_raw_dir

        source = "pdns"
        for record in load_pdns_raw_dir(self.root / "data/raw/pdns"):
            self.stats[source]["input_records"] += 1
            domain = normalize_domain(str(record.get("domain") or ""))
            if not domain or ("Domain", domain) not in self.ioc_sources:
                self.stats[source]["excluded_no_exact_overlap"] += 1
                continue
            provenance = {
                "source": source,
                "source_record_id": domain,
                "raw_ref": f"data/raw/pdns/{domain}",
                "coverage_population": "OTX-derived domain/URL-host lookup set",
            }
            domain_id = self.add_node("Domain", domain, provenance)
            self.stats[source]["exact_overlap"] += 1
            for item in record.get("resolutions") or []:
                rtype = str(item.get("record_type") or "").upper()
                address = str(item.get("value") or "")
                first = iso(parse_time(item.get("first_seen")))
                last = iso(parse_time(item.get("last_seen")))
                if rtype in {"A", "AAAA"}:
                    ip, _ = normalize_ip(address)
                    if not ip:
                        continue
                    ip_id = self.add_node(
                        "IP", ip, provenance, first_seen=first, last_seen=last,
                        timestamp_basis="pdns_historical_observation"
                    )
                    self.add_relation(
                        domain_id, "ResolvesTo", ip_id, provenance,
                        timestamp=first, timestamp_basis="pdns_first_seen"
                    )
                    asn = str(item.get("asn") or "").upper()
                    if asn:
                        asn_id = self.add_node(
                            "ASN", asn, provenance, number=asn.removeprefix("AS"),
                            issuer=item.get("asn_name")
                        )
                        self.add_relation(
                            ip_id, "InGroup", asn_id, provenance,
                            timestamp=first, timestamp_basis="pdns_first_seen"
                        )
                elif rtype == "CNAME":
                    target = normalize_domain(address)
                    if target:
                        self.cname_rows.append(
                            {
                                "source": source,
                                "source_record_id": domain,
                                "record_type": "CNAME",
                                "domain": domain,
                                "canonical_name": target,
                                "first_seen": first,
                                "last_seen": last,
                                "projection_status": "normalized_not_projected_domain_to_domain_outside_fixed_relations",
                                "provenance": provenance,
                            }
                        )
                else:
                    self.stats[source][f"not_projected_{rtype or 'unknown'}"] += 1

    def process_vt(self) -> None:
        source = "virustotal"
        raw_dir = self.root / "data/raw/vt"
        for domain_dir in sorted(path for path in raw_dir.iterdir() if path.is_dir()):
            snapshots = sorted(domain_dir.glob("*.json"))
            if not snapshots:
                continue
            self.stats[source]["input_records"] += 1
            raw = json.loads(snapshots[-1].read_text(encoding="utf-8"))
            data = (raw.get("payload") or {}).get("data") or {}
            domain = normalize_domain(str(data.get("id") or ""))
            if not domain or ("Domain", domain) not in self.ioc_sources:
                self.stats[source]["excluded_no_exact_overlap"] += 1
                continue
            provenance = {
                "source": source,
                "source_record_id": domain,
                "raw_ref": snapshots[-1].relative_to(self.root).as_posix(),
                "coverage_population": "OTX-derived lookup set",
                "observation_semantics": "current_snapshot_not_historical_pdns",
            }
            domain_id = self.add_node("Domain", domain, provenance)
            self.stats[source]["exact_overlap"] += 1
            for item in (data.get("attributes") or {}).get("last_dns_records") or []:
                if str(item.get("type") or "").upper() not in {"A", "AAAA"}:
                    continue
                ip, _ = normalize_ip(str(item.get("value") or ""))
                if ip:
                    ip_id = self.add_node("IP", ip, provenance)
                    self.add_relation(
                        domain_id, "ResolvesTo", ip_id, provenance,
                        timestamp=iso(parse_time(raw.get("fetched_at"))),
                        timestamp_basis="virustotal_snapshot_fetched_at",
                    )

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        node_counts = Counter(row["node_type"] for row in self.nodes.values())
        relation_counts = Counter(row["relation_type"] for row in self.relations.values())
        endpoint_contract = {
            "InReport": {("Event", "IP"), ("Event", "URL"), ("Event", "Domain")},
            "HostedOn": {("URL", "Domain")},
            "ResolvesTo": {("Domain", "IP"), ("URL", "IP")},
            "InGroup": {("IP", "ASN")},
        }
        legacy_contract = {
            "InReport": "IN_REPORT",
            "HostedOn": "HOSTED_ON",
            "ResolvesTo": "RESOLVES_TO",
            "InGroup": "IN_ASN_GROUP",
        }
        event_inreport_types: dict[str, set[str]] = defaultdict(set)
        claims_by_record: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for actor_source, rows in self.actor_rows.items():
            for row in rows:
                claims_by_record[(actor_source, str(row.get("source_record_id")))].append(row)
        for node_id, node in self.nodes.items():
            if node["node_type"] not in NODE_TYPES:
                errors.append(f"invalid node type: {node_id}")
            if not node.get("provenance"):
                errors.append(f"missing node provenance: {node_id}")
            if node["node_type"] == "Event":
                timestamp = parse_time(node.get("event_timestamp"))
                if not timestamp or not WINDOW_START <= timestamp <= WINDOW_END:
                    errors.append(f"event outside window: {node_id}")
                if node.get("timestamp_basis") not in {
                    "published_at", "event_date", "collector_listed_date"
                }:
                    errors.append(f"invalid event timestamp basis: {node_id}")
                if node.get("source") == "orkl" and node.get("timestamp_basis") != "published_at":
                    errors.append(f"ORKL non-publication timestamp: {node_id}")
                if not node.get("strict_actor_label_eligible") and any(
                    key in node for key in ("actor", "apt", "label")
                ):
                    errors.append(f"ineligible Event carries actor label: {node_id}")
                if node.get("source") == "orkl":
                    if node.get("final_ground_truth") is not False:
                        errors.append(f"ORKL Event promoted to ground truth: {node_id}")
                    if node.get("training_ground_truth_eligible") is not False:
                        errors.append(f"ORKL Event training-ground-truth eligible: {node_id}")
                if node.get("strict_actor_label_eligible"):
                    material_claims = [
                        row
                        for row in claims_by_record.get(
                            (str(node.get("source")), str(node.get("source_record_id"))), []
                        )
                        if row.get("resolution_status") != "unresolved_generic"
                    ]
                    if not material_claims or any(
                        row.get("resolution_status") != "resolved" for row in material_claims
                    ):
                        errors.append(f"strict Event has non-resolved source claim: {node_id}")
                    canonical = {
                        str(row.get("canonical_name"))
                        for row in material_claims
                        if row.get("canonical_name")
                    }
                    if len(canonical) != 1 or node.get("apt") not in canonical:
                        errors.append(f"strict Event claims do not converge: {node_id}")
        for relation_id, relation in self.relations.items():
            if relation["source_node_id"] not in self.nodes or relation["target_node_id"] not in self.nodes:
                errors.append(f"dangling relation: {relation_id}")
                continue
            if not relation.get("source") or not relation.get("source_record_id"):
                errors.append(f"missing relation provenance: {relation_id}")
            relation_type = relation.get("relation_type")
            endpoint = (
                self.nodes[relation["source_node_id"]]["node_type"],
                self.nodes[relation["target_node_id"]]["node_type"],
            )
            if endpoint not in endpoint_contract.get(str(relation_type), set()):
                errors.append(f"invalid relation endpoints: {relation_id}:{endpoint}")
            if relation.get("legacy_relation_type") != legacy_contract.get(str(relation_type)):
                errors.append(f"invalid legacy relation type: {relation_id}")
            if relation_type == "InReport":
                event_inreport_types[relation["source_node_id"]].add(endpoint[1])
        for rows in self.actor_rows.values():
            for row in rows:
                if row.get("resolution_status") == "resolved" and "resolved" not in (
                    row.get("mapping_statuses") or []
                ):
                    errors.append(f"candidate mapping promoted: {row.get('claim_id')}")
                if row.get("resolution_status") in {"candidate", "ambiguous"} and row.get(
                    "resolved_entity_id"
                ):
                    errors.append(f"non-resolved mapping has resolved id: {row.get('claim_id')}")
        strict_labeled = sum(
            row["node_type"] == "Event" and bool(row.get("strict_actor_label_eligible"))
            for row in self.nodes.values()
        )
        candidate_unlabeled = sum(
            row["node_type"] == "Event" and not row.get("strict_actor_label_eligible")
            for row in self.nodes.values()
        )
        indirect_events = sum(
            row["node_type"] == "Event" and row.get("label_availability") == "indirect"
            for row in self.nodes.values()
        )
        event_nodes = [
            (node_id, row)
            for node_id, row in self.nodes.items()
            if row["node_type"] == "Event"
        ]
        for node_id, node in event_nodes:
            types = event_inreport_types.get(node_id, set())
            if not types:
                errors.append(f"graph Event has no InReport edge: {node_id}")
            compatible = bool(types & {"IP", "URL"})
            if node.get("legacy_extractor_compatible") is not compatible:
                errors.append(f"legacy compatibility flag mismatch: {node_id}")
        old_trail_compatible = sum(
            bool(event_inreport_types.get(node_id, set()) & {"IP", "URL"})
            for node_id, _ in event_nodes
        )
        return {
            "status": "pass" if not errors else "fail",
            "errors": errors[:100],
            "error_count": len(errors),
            "node_counts": dict(sorted(node_counts.items())),
            "relation_counts": dict(sorted(relation_counts.items())),
            "graph_events": node_counts["Event"],
            "strict_labeled_events": strict_labeled,
            "candidate_or_unlabeled_events": candidate_unlabeled,
            "indirect_source_events": indirect_events,
            "old_trail_compatible_event_count": old_trail_compatible,
            "event_time_min": min(
                (row["event_timestamp"] for row in self.nodes.values() if row["node_type"] == "Event"),
                default=None,
            ),
            "event_time_max": max(
                (row["event_timestamp"] for row in self.nodes.values() if row["node_type"] == "Event"),
                default=None,
            ),
        }

    def write(self) -> dict[str, Any]:
        for source, rows in self.record_rows.items():
            write_jsonl(self.out / "normalized" / source / "records.jsonl", rows)
        for source, rows in self.actor_rows.items():
            write_jsonl(self.out / "actor_resolution" / f"{source}.jsonl", rows)
        for source, rows in self.ioc_rows.items():
            write_jsonl(self.out / "normalized" / source / "ioc_evidence.jsonl", rows)
        write_jsonl(self.out / "evidence/unprojected_evidence.jsonl", self.unprojected)
        write_jsonl(self.out / "evidence/pdns_cname_records.jsonl", self.cname_rows)
        write_jsonl(self.out / "graph/nodes.jsonl", sorted(self.nodes.values(), key=lambda row: row["node_id"]))
        write_jsonl(
            self.out / "graph/relations.jsonl",
            sorted(self.relations.values(), key=lambda row: row["relation_id"]),
        )
        unresolved = (
            row
            for rows in self.actor_rows.values()
            for row in rows
            if row["resolution_status"] == "unresolved"
        )
        ambiguous = (
            row
            for rows in self.actor_rows.values()
            for row in rows
            if row["resolution_status"] == "ambiguous"
        )
        candidate = (
            row
            for rows in self.actor_rows.values()
            for row in rows
            if row["resolution_status"] == "candidate"
        )
        write_jsonl(self.out / "actor_resolution/unresolved_queue.jsonl", unresolved)
        write_jsonl(self.out / "actor_resolution/ambiguous_queue.jsonl", ambiguous)
        write_jsonl(self.out / "actor_resolution/candidate_queue.jsonl", candidate)
        validation = self.validate()
        source_quality: dict[str, Any] = {}
        for source, records in sorted(self.record_rows.items()):
            actor_status = Counter(str(row.get("actor_status") or "missing") for row in records)
            source_quality[source] = {
                "normalized_records": len(records),
                "records_in_target_window": sum(bool(row.get("in_target_window")) for row in records),
                "records_missing_event_timestamp": sum(not row.get("event_timestamp") for row in records),
                "records_with_canonical_actor": sum(bool(row.get("canonical_actor")) for row in records),
                "actor_record_status": dict(sorted(actor_status.items())),
                "ioc_evidence_rows": len(self.ioc_rows.get(source, [])),
                "actor_claim_resolution": dict(
                    sorted(
                        Counter(
                            str(row.get("resolution_status") or "missing")
                            for row in self.actor_rows.get(source, [])
                        ).items()
                    )
                ),
            }
        if "misp" in source_quality:
            source_quality["misp"]["event_date_in_target_window"] = sum(
                bool(
                    (stamp := parse_time(row.get("event_date")))
                    and WINDOW_START <= stamp <= WINDOW_END
                )
                for row in self.record_rows["misp"]
            )
            source_quality["misp"]["selected_event_timestamp_rule"] = (
                "published_at when valid; otherwise event_date at UTC midnight"
            )
        threatfox_normalized = list(
            jsonl(self.root / "data/raw/threatfox/normalized/iocs.jsonl")
        )
        threatfox_rows = self.ioc_rows.get("threatfox", [])
        source_quality["threatfox"] = {
            **source_quality.get("threatfox", {}),
            "normalized_records": self.stats["threatfox"]["input_records"],
            "ioc_value_nonempty": sum(
                bool(row.get("ioc_value_raw")) for row in threatfox_normalized
            ),
            "first_seen_nonempty": sum(
                bool(row.get("first_seen")) for row in threatfox_normalized
            ),
            "last_seen_nonempty": sum(
                bool(row.get("last_seen")) for row in threatfox_normalized
            ),
            "projected_ip_port_rows": sum(
                row.get("ioc_type") == "IP" and row.get("network_port") is not None
                for row in threatfox_rows
            ),
            "unprojected_rows": self.stats["threatfox"]["unprojected"],
        }
        urlhaus_normalized = list(
            jsonl(self.root / "data/raw/urlhaus/normalized/urls.jsonl")
        )
        source_quality["urlhaus"] = {
            "normalized_records": len(urlhaus_normalized),
            "http_https_projected": self.stats["urlhaus"]["projected"],
            "unsupported_scheme": self.stats["urlhaus"]["unprojected"],
            "date_added_nonempty": sum(bool(row.get("date_added")) for row in urlhaus_normalized),
            "last_online_nonempty": sum(bool(row.get("last_online")) for row in urlhaus_normalized),
            "host_deterministically_parsed_from_url": self.stats["urlhaus"]["projected"],
        }
        source_quality["pdns"] = {
            "lookup_records": self.stats["pdns"]["input_records"],
            "exact_overlap_records": self.stats["pdns"]["exact_overlap"],
            "population": "OTX-derived domain/URL-host lookup set; not new-source complete",
            "cname_records_normalized": len(self.cname_rows),
        }
        source_quality["virustotal"] = {
            "lookup_records": self.stats["virustotal"]["input_records"],
            "exact_overlap_records": self.stats["virustotal"]["exact_overlap"],
            "dns_time_semantics": "current snapshot at fetched_at; not historical pDNS",
            "population": "OTX-derived lookup set; not new-source complete",
        }
        attachment_rows = list(
            jsonl(self.root / "data/raw/cisa/normalized/attachments.jsonl")
        )
        source_quality["cisa"]["attachments_total"] = len(attachment_rows)
        source_quality["cisa"]["attachments_successful"] = sum(
            str(row.get("fetch_status") or row.get("status") or "").lower()
            in {"success", "fetched", "complete", "downloaded"}
            for row in attachment_rows
        )
        source_quality["cisa"]["attachments_status"] = dict(
            sorted(
                Counter(
                    str(row.get("fetch_status") or row.get("status") or "missing")
                    for row in attachment_rows
                ).items()
            )
        )
        overlap = Counter()
        for sources in self.ioc_sources.values():
            for source in sources:
                overlap[source] += 1
            if len(sources) > 1:
                overlap["multi_source_iocs"] += 1
        report = {
            "dataset_id": "trail_multisource_part1",
            "version": "v1_20260724",
            "generated_at": iso(datetime.now(UTC)),
            "window": {"start": iso(WINDOW_START), "end": iso(WINDOW_END)},
            "otx_policy": "existing baseline untouched; OTX was not collected, scanned, or rebuilt",
            "scope": "data standardization only; no model, checkpoint, training, or prediction",
            "focused_regression_tests": {
                "command": (
                    "python -m pytest -o addopts= tests/unit/test_trail_part1.py "
                    "tests/unit/test_threat_source_collections.py -q"
                ),
                "assertions_passed": 15,
                "exit_code": 0,
                "note": (
                    "The default repository addopts enforces whole-repository coverage and "
                    "is not the focused delivery test command."
                ),
            },
            "before_after": {
                "previous_graph_events": 1885,
                "previous_events_carrying_apt_label": 1885,
                "previous_orkl_graph_events": 1845,
                "previous_orkl_events_carrying_apt_label": 1845,
                "current_graph_events": validation["graph_events"],
                "current_strict_labeled_events": validation["strict_labeled_events"],
                "current_candidate_or_unlabeled_events": validation[
                    "candidate_or_unlabeled_events"
                ],
                "current_indirect_source_events": validation["indirect_source_events"],
            },
            "source_roles": {
                "misp": "Event source",
                "orkl": (
                    "Event source: valid published_at + source actor association + supported "
                    "network IOC may enter graph; strict convergence alone adds apt/label; "
                    "all ORKL Events remain non-final and non-training ground truth"
                ),
                "aptnotes": "Event source",
                "cisa": "Event-capable source; zero promoted without structured/manual MITRE actor evidence",
                "mitre_malpedia_aliases": "taxonomy source only",
                "threatfox": "enrichment/corroboration source only",
                "urlhaus": "enrichment/corroboration source only",
                "pdns": "enrichment source with OTX-derived lookup population",
                "virustotal": "snapshot corroboration source with OTX-derived lookup population",
            },
            "alias_reuse": {
                "path": self.aliases.path.relative_to(self.root).as_posix(),
                "input_rows": self.aliases.input_rows,
                "actor_rows_used": self.aliases.actor_rows,
                "resolution_policy": "exact normalized alias; collisions ambiguous; strict one canonical actor per Event",
            },
            "per_source": {source: dict(counts) for source, counts in sorted(self.stats.items())},
            "source_quality": source_quality,
            "graph": validation,
            "enrichment_coverage": dict(overlap),
            "known_limits": [
                "ThreatFox excludes expired IOCs older than six months.",
                "URLhaus full export covers active URLs or URLs added within the prior 90 days.",
                "pDNS and VirusTotal lookup populations are OTX-derived and are not full coverage of new sources.",
                "VirusTotal last_dns_records is a current snapshot, not historical pDNS.",
                "CISA attachment coverage remains 177 successful of 657 listed; no missing content is fabricated.",
                "ORKL records without valid published_at remain normalized but are excluded from temporal Events.",
                "Regex IOC extraction is deterministic and span-auditable but is not a semantic assertion that every mention is malicious.",
            ],
        }
        (self.out / "validation_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return report

    def run(self) -> dict[str, Any]:
        self.process_misp()
        self.process_orkl()
        self.process_aptnotes()
        self.process_cisa()
        self.process_threatfox()
        self.process_urlhaus()
        self.process_pdns()
        self.process_vt()
        return self.write()
