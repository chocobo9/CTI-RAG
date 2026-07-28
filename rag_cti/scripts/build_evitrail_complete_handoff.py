"""Build the complete, source-neutral EviTRAIL handoff data package.

The handoff contains every normalized non-OTX report Event, all supported
source-provided five-node observations, and every original actor claim.  OTX is
kept in its lossless RawStore form because its 12M+ indicator occurrences are
already an accepted EviTRAIL raw input and duplicating them into JSONL would
make the delivery needlessly larger.  A package manifest records that routing
explicitly, and ``all_source_claims.jsonl`` still audits OTX and non-OTX claims
together.

No model, checkpoint, prediction, confidence score, or enrichment result is
created by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_cti.intermediate.otx_source_claims import OTXSourceClaimNormalizer


BASE_SOURCE_MAP = {
    "misp": "circl_misp",
    "orkl": "orkl",
    "aptnotes": "aptnotes",
    "cisa": "cisa",
}
DIRECT_TRAINING_SOURCES = {"otx", "circl_misp", "aptnotes"}
CONTEXT_ONLY_SOURCES = {"orkl", "cisa"}
LEGACY_CANONICAL_OVERRIDES = {
    "gamaredon": "Gamaredon Group",
    "sandworm": "Sandworm Team",
}
NODE_TYPES = {"event", "domain", "ip", "url", "asn"}
RELATION_ENDPOINTS = {
    "event_contains_domain": ("event", "domain"),
    "event_contains_ip": ("event", "ip"),
    "event_contains_url": ("event", "url"),
    "url_hosted_on_domain": ("url", "domain"),
    "url_resolves_to_ip": ("url", "ip"),
    "ip_in_asn": ("ip", "asn"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=Path("data/processed/trail_multisource_part1_v1_20260724"),
    )
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--otx-root", type=Path, default=Path("data/raw/otx"))
    parser.add_argument(
        "--mitre",
        type=Path,
        default=Path("data/raw/mitre/enterprise-attack.json"),
    )
    parser.add_argument(
        "--initial-vocabulary",
        type=Path,
        help="Optional JSON list or {'actors': [...]} replacing EviTRAIL's legacy vocabulary.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = build_package(
        processed_root=args.processed_root,
        raw_root=args.raw_root,
        otx_root=args.otx_root,
        mitre_path=args.mitre,
        output_dir=args.output_dir,
        initial_vocabulary_path=args.initial_vocabulary,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def build_package(
    *,
    processed_root: Path,
    raw_root: Path,
    otx_root: Path,
    mitre_path: Path,
    output_dir: Path,
    initial_vocabulary_path: Path | None = None,
) -> dict[str, Any]:
    processed_root = processed_root.resolve()
    raw_root = raw_root.resolve()
    otx_root = otx_root.resolve()
    mitre_path = mitre_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    required = [
        processed_root / "validation_report.json",
        mitre_path,
        otx_root,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing required inputs: {missing}")

    handoff = output_dir / "handoff"
    claims_dir = output_dir / "labels"
    enrichment_dir = output_dir / "enrichment_inputs"
    handoff.mkdir(parents=True)
    claims_dir.mkdir()
    enrichment_dir.mkdir()

    node_db_path = output_dir / "._node_index.sqlite"
    connection = sqlite3.connect(node_db_path)
    connection.execute(
        """
        CREATE TABLE nodes (
            node_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            value TEXT NOT NULL,
            properties TEXT
        ) WITHOUT ROWID
        """
    )

    event_by_source_record: dict[tuple[str, str], str] = {}
    event_counts: Counter[str] = Counter()
    indicator_counts: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    rejection_counts: Counter[str] = Counter()
    edge_count = 0
    rejected_count = 0

    with (
        _jsonl_writer(handoff / "events.jsonl") as events_fh,
        _jsonl_writer(handoff / "edges.jsonl") as edges_fh,
        _jsonl_writer(handoff / "rejected_records.jsonl") as rejected_fh,
    ):
        for original_source, canonical_source in BASE_SOURCE_MAP.items():
            records_path = processed_root / "normalized" / original_source / "records.jsonl"
            for record in _iter_jsonl(records_path):
                source_record_id = str(record["source_record_id"])
                eid = _event_id(canonical_source, source_record_id)
                event_by_source_record[(original_source, source_record_id)] = eid
                raw_ref = _repository_raw_ref(
                    original_source, record.get("raw_ref"), raw_root
                )
                event_row = _event_row(record, canonical_source, eid, raw_ref)
                _write_row(events_fh, event_row)
                _insert_node(
                    connection,
                    eid,
                    "event",
                    eid,
                    {"source": canonical_source, "source_record_id": source_record_id},
                )
                event_counts[canonical_source] += 1

            evidence_path = (
                processed_root / "normalized" / original_source / "ioc_evidence.jsonl"
            )
            for ordinal, evidence in enumerate(_iter_jsonl(evidence_path)):
                source_record_id = str(evidence.get("source_record_id") or "")
                eid = event_by_source_record.get((original_source, source_record_id))
                if not eid:
                    rejected_count += 1
                    rejection_counts["missing_event_for_ioc"] += 1
                    _write_row(
                        rejected_fh,
                        {
                            "source": canonical_source,
                            "raw_ref": _repository_raw_ref(
                                original_source, evidence.get("raw_ref"), raw_root
                            ),
                            "record_path": str(
                                evidence.get("source_field") or f"ioc_evidence[{ordinal}]"
                            ),
                            "reason": "missing_event_for_ioc",
                            "raw_type": evidence.get("ioc_type"),
                            "raw_value": evidence.get("ioc_value_raw"),
                        },
                    )
                    continue
                parsed = _normalized_indicator(
                    evidence.get("ioc_type"), evidence.get("ioc_value")
                )
                if not parsed:
                    rejected_count += 1
                    rejection_counts["unsupported_or_invalid_indicator"] += 1
                    _write_row(
                        rejected_fh,
                        {
                            "source": canonical_source,
                            "event_id": eid,
                            "raw_ref": _repository_raw_ref(
                                original_source, evidence.get("raw_ref"), raw_root
                            ),
                            "record_path": str(
                                evidence.get("source_field") or f"ioc_evidence[{ordinal}]"
                            ),
                            "reason": "unsupported_or_invalid_indicator",
                            "raw_type": evidence.get("ioc_type"),
                            "raw_value": evidence.get("ioc_value_raw"),
                        },
                    )
                    continue
                node_type, value = parsed
                target_id = _node_id(node_type, value)
                _insert_node(connection, target_id, node_type, value)
                indicator_counts[f"{canonical_source}:{node_type}"] += 1
                raw_ref = _repository_raw_ref(
                    original_source, evidence.get("raw_ref"), raw_root
                )
                inline = _inline_evidence(
                    evidence,
                    canonical_source,
                    raw_ref,
                    str(evidence.get("source_field") or f"ioc_evidence[{ordinal}]"),
                )
                relation = f"event_contains_{node_type}"
                if relation in RELATION_ENDPOINTS:
                    _write_row(
                        edges_fh,
                        _edge_row(relation, eid, target_id, inline, ordinal),
                    )
                    relation_counts[relation] += 1
                    edge_count += 1
                if node_type == "url":
                    derived = _url_host(value)
                    if derived:
                        host_type, host_value = derived
                        host_id = _node_id(host_type, host_value)
                        _insert_node(connection, host_id, host_type, host_value)
                        host_relation = (
                            "url_hosted_on_domain"
                            if host_type == "domain"
                            else "url_resolves_to_ip"
                        )
                        derived_evidence = {
                            **inline,
                            "derivation": "deterministic_url_host",
                            "record_path": f"{inline['record_path']}.url_host",
                        }
                        _write_row(
                            edges_fh,
                            _edge_row(
                                host_relation,
                                target_id,
                                host_id,
                                derived_evidence,
                                ordinal,
                            ),
                        )
                        relation_counts[host_relation] += 1
                        edge_count += 1
            connection.commit()

        misp_edge_count = _append_misp_asn_relations(
            raw_root=raw_root,
            connection=connection,
            edges_fh=edges_fh,
            rejected_fh=rejected_fh,
            event_by_source_record=event_by_source_record,
            relation_counts=relation_counts,
            rejection_counts=rejection_counts,
        )
        edge_count += misp_edge_count["edges"]
        rejected_count += misp_edge_count["rejected"]

    node_count = _write_nodes(connection, handoff / "nodes.jsonl")
    connection.close()
    node_db_path.unlink()

    claim_result = _write_claim_artifacts(
        processed_root=processed_root,
        raw_root=raw_root,
        otx_root=otx_root,
        mitre_path=mitre_path,
        event_by_source_record=event_by_source_record,
        handoff_claims_path=handoff / "source_claims.jsonl",
        all_claims_path=claims_dir / "all_source_claims.jsonl",
        training_labels_path=claims_dir / "training_labels.jsonl",
        vocabulary_review_path=claims_dir / "vocabulary_review.json",
        initial_vocabulary_path=initial_vocabulary_path,
    )

    enrichment = _enrichment_manifest(raw_root, processed_root)
    _write_json(enrichment_dir / "manifest.json", enrichment)
    _write_json(
        output_dir / "consumer_contract.json",
        {
            "consumer": "Mitraaaaa/Evitrial evitrail.data.readers.read_handoff",
            "verified_consumer_commit": "da4a29e8ce25cff8cbddebb444b069296f949511",
            "handoff_path": "handoff",
            "otx_route": {
                "mode": "original_raw_source",
                "path": "data/raw/otx",
                "reason": (
                    "Preserves every OTX source field and 12M+ indicator occurrences "
                    "without lossy or duplicative rematerialization."
                ),
            },
            "base_sources_in_handoff": sorted(event_counts),
            "enrichment_is_separate": True,
            "checkpoints_models_predictions_included": False,
            "read_command": (
                "python -m evitrail.data.pipeline --handoff <package>/handoff "
                "--raw-root __disabled__ --otx <cti-rag>/data/raw/otx "
                "--mitre <cti-rag>/data/raw/mitre/enterprise-attack.json "
                "--malpedia <cti-rag>/data/raw/malpedia/raw/actors/actors.json "
                "--enrichment none"
            ),
        },
    )
    coverage = {
        "status": "generated_pending_consumer_validation",
        "base_event_counts": dict(sorted(event_counts.items())),
        "handoff_event_count": sum(event_counts.values()),
        "handoff_node_count": node_count,
        "handoff_edge_count": edge_count,
        "handoff_indicator_occurrence_counts": dict(sorted(indicator_counts.items())),
        "handoff_relation_counts": dict(sorted(relation_counts.items())),
        "handoff_rejected_count": rejected_count,
        "handoff_rejection_counts": dict(sorted(rejection_counts.items())),
        "otx": claim_result["otx"],
        "claims": {
            key: value
            for key, value in claim_result.items()
            if key not in {"otx", "vocabulary"}
        },
        "vocabulary": claim_result["vocabulary"],
        "important_semantics": [
            "OTX round 1 is broad subscribed collection without actor seeds.",
            "OTX round 2 is discovered from MITRE ATT&CK actor names and aliases.",
            "Round-2 query matches are discovery provenance, never actor labels.",
            "Only OTX's adversary source field creates OTX actor claims.",
            "Multiple, conflicting, unresolved, ambiguous, and OOV claims are retained.",
            "ORKL and CISA claims are provenance-only and cannot promote training classes.",
            "Enrichment inputs do not enter the factual base handoff.",
        ],
    }
    _write_json(output_dir / "coverage_audit.json", coverage)
    manifest = {
        "contract": "evitrail_complete_multisource_data_handoff_v1",
        "status": "generated_pending_consumer_validation",
        "format": {
            "handoff": "evitrail-read-handoff-flat-v1",
            "all_claims": "source-neutral-actor-claims-v1",
            "training_labels": "strict-single-canonical-labels-v1",
        },
        "base_sources": {
            "handoff": sorted(event_counts),
            "original_raw": ["otx"],
        },
        "taxonomy_sources": ["mitre", "malpedia"],
        "enrichment_sources": ["threatfox", "urlhaus", "passive_dns", "virustotal"],
        "counts": {
            "handoff_events": sum(event_counts.values()),
            "handoff_nodes": node_count,
            "handoff_edges": edge_count,
            "handoff_source_claims": claim_result["handoff_claims"],
            "all_source_claims": claim_result["all_source_claims"],
            "training_labels": claim_result["training_labels"],
            "otx_events": claim_result["otx"]["events"],
            "otx_indicator_occurrences": claim_result["otx"][
                "indicator_occurrences"
            ],
        },
        "files": _file_manifest(output_dir),
        "forbidden_artifacts": {
            "checkpoints": False,
            "weights": False,
            "predictions": False,
            "training_results": False,
        },
    }
    _write_json(output_dir / "manifest.json", manifest)
    _write_readme(output_dir, manifest)
    return manifest


def _event_row(
    record: Mapping[str, Any], source: str, eid: str, raw_ref: str
) -> dict[str, Any]:
    row = {
        "event_id": eid,
        "source": source,
        "source_record_id": str(record["source_record_id"]),
        "title": str(record.get("title") or ""),
        "description": str(record.get("description") or ""),
        "raw_ref": raw_ref,
        "event_time": record.get("event_timestamp"),
        "created": record.get("created_at"),
        "modified": record.get("modified_at") or record.get("updated_at"),
        "published": record.get("published_at") or record.get("listed_date"),
        "fetched_at": record.get("fetched_at"),
        "timestamp_basis": record.get("timestamp_basis"),
        "timestamp_precision": record.get("timestamp_precision"),
        "original_actor_status": record.get("actor_status"),
        "original_canonical_actor": record.get("canonical_actor"),
        "original_strict_actor_label_eligible": bool(
            record.get("strict_actor_label_eligible")
        ),
        "in_target_window": bool(record.get("in_target_window")),
    }
    return {key: value for key, value in row.items() if value is not None}


def _append_misp_asn_relations(
    *,
    raw_root: Path,
    connection: sqlite3.Connection,
    edges_fh: TextIO,
    rejected_fh: TextIO,
    event_by_source_record: Mapping[tuple[str, str], str],
    relation_counts: Counter[str],
    rejection_counts: Counter[str],
) -> dict[str, int]:
    edges = rejected = 0
    misp_root = raw_root / "circl_misp"
    for (source, source_record_id), eid in sorted(event_by_source_record.items()):
        if source != "misp":
            continue
        uuid = source_record_id.rsplit(":", 1)[-1]
        path = misp_root / "raw" / "events" / f"{uuid}.json"
        if not path.exists():
            continue
        try:
            wrapper = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rejected += 1
            rejection_counts["invalid_misp_raw_json"] += 1
            _write_row(
                rejected_fh,
                {
                    "source": "circl_misp",
                    "event_id": eid,
                    "raw_ref": _relative_or_absolute(path, raw_root.parent.parent),
                    "record_path": "Event",
                    "reason": "invalid_misp_raw_json",
                },
            )
            continue
        event = wrapper.get("Event", wrapper)
        raw_ref = _relative_or_absolute(path, raw_root.parent.parent)
        for object_index, obj in enumerate(event.get("Object") or []):
            if not isinstance(obj, Mapping):
                continue
            ips: list[str] = []
            asns: list[str] = []
            for attribute in obj.get("Attribute") or []:
                if not isinstance(attribute, Mapping):
                    continue
                raw_type = str(
                    attribute.get("type") or attribute.get("object_relation") or ""
                ).lower()
                raw_value = str(attribute.get("value") or "")
                if raw_type in {"ip-src", "ip-dst", "ip", "ip-address"}:
                    parsed = _normalize_ip(raw_value.split("|", 1)[0])
                    if parsed:
                        ips.append(parsed)
                elif raw_type in {"as", "asn", "autonomous-system"}:
                    parsed = _normalize_asn(raw_value)
                    if parsed:
                        asns.append(parsed)
            for ip_value in sorted(set(ips)):
                ip_id = _node_id("ip", ip_value)
                _insert_node(connection, ip_id, "ip", ip_value)
                for asn_value in sorted(set(asns)):
                    asn_id = _node_id("asn", asn_value)
                    _insert_node(connection, asn_id, "asn", asn_value)
                    inline = {
                        "source": "circl_misp",
                        "raw_ref": raw_ref,
                        "record_path": f"Event.Object[{object_index}]",
                        "derivation": "source_asserted_object_relation",
                    }
                    _write_row(
                        edges_fh,
                        _edge_row(
                            "ip_in_asn", ip_id, asn_id, inline, object_index
                        ),
                    )
                    relation_counts["ip_in_asn"] += 1
                    edges += 1
        connection.commit()
    return {"edges": edges, "rejected": rejected}


def _write_claim_artifacts(
    *,
    processed_root: Path,
    raw_root: Path,
    otx_root: Path,
    mitre_path: Path,
    event_by_source_record: Mapping[tuple[str, str], str],
    handoff_claims_path: Path,
    all_claims_path: Path,
    training_labels_path: Path,
    vocabulary_review_path: Path,
    initial_vocabulary_path: Path | None,
) -> dict[str, Any]:
    mitre_taxonomy = _mitre_taxonomy(mitre_path)
    claim_counts: Counter[str] = Counter()
    claim_status: Counter[str] = Counter()
    event_claims: dict[str, list[dict[str, Any]]] = defaultdict(list)
    handoff_claim_count = 0
    written_claim_ids: set[str] = set()

    with (
        _jsonl_writer(handoff_claims_path) as handoff_fh,
        _jsonl_writer(all_claims_path) as all_fh,
    ):
        for original_source, canonical_source in BASE_SOURCE_MAP.items():
            path = processed_root / "actor_resolution" / f"{original_source}.jsonl"
            for ordinal, original in enumerate(_iter_jsonl(path)):
                source_record_id = str(original.get("source_record_id") or "")
                eid = event_by_source_record.get((original_source, source_record_id))
                raw_value = str(
                    original.get("raw_label")
                    or original.get("raw_value")
                    or original.get("claim_excerpt")
                    or ""
                ).strip()
                if not eid or not raw_value:
                    continue
                raw_ref = _repository_raw_ref(
                    original_source, original.get("raw_ref"), raw_root
                )
                source_field = str(
                    original.get("source_location")
                    or original.get("source_field")
                    or f"actor_resolution[{ordinal}]"
                )
                original_status = str(
                    original.get("resolution_status") or "unresolved"
                )
                prior_canonical = (
                    str(original.get("canonical_name") or "").strip()
                    if original_status == "resolved"
                    else ""
                )
                resolution = _resolve_mitre_identity(
                    raw_value, mitre_taxonomy, fallback=prior_canonical
                )
                original_identity = str(
                    original.get("resolved_entity_id") or ""
                ).strip()
                if (
                    original_status == "resolved"
                    and original_identity
                    and original_identity
                    in mitre_taxonomy["preferred_names"]
                ):
                    resolution = {
                        "resolution_status": "resolved",
                        "resolved_actor_ids": [original_identity],
                        "canonical_actor": mitre_taxonomy["preferred_names"][
                            original_identity
                        ],
                    }
                canonical = str(resolution.get("canonical_actor") or "")
                status = str(
                    resolution.get("resolution_status") or original_status
                )
                if status == "unresolved" and original_status != "resolved":
                    status = original_status
                resolved_actor_ids = list(
                    resolution.get("resolved_actor_ids") or []
                )
                if (
                    not resolved_actor_ids
                    and original_status == "resolved"
                    and _is_actor_identity(original_identity)
                ):
                    resolved_actor_ids = [original_identity]
                context_only = canonical_source in CONTEXT_ONLY_SOURCES
                generated_claim_id = _claim_id(
                    eid, canonical_source, raw_value, source_field
                )
                if generated_claim_id in written_claim_ids:
                    continue
                written_claim_ids.add(generated_claim_id)
                row = {
                    "claim_id": generated_claim_id,
                    "event_id": eid,
                    "source": canonical_source,
                    "source_record_id": source_record_id,
                    "raw_value": raw_value,
                    "normalized_value": original.get("normalized_alias_key"),
                    "canonical_actor": canonical or None,
                    "resolution_status": status,
                    "resolved_actor_ids": resolved_actor_ids,
                    "candidate_actor_ids": resolution.get(
                        "candidate_actor_ids"
                    )
                    or [],
                    "original_resolution_status": original_status,
                    "original_canonical_actor": prior_canonical or None,
                    "candidate_canonical_names": _unique_strings(
                        original.get("candidate_canonical_names") or []
                    ),
                    "source_field": source_field,
                    "raw_ref": raw_ref,
                    "claim_scope": "report_context" if context_only else "attribution",
                    "set_semantics": "source_set_member",
                    "usage": "provenance_only" if context_only else "candidate",
                    "claim_kind": original.get("claim_kind"),
                    "mapping_sources": original.get("alias_mapping_sources") or [],
                }
                _write_row(handoff_fh, row)
                _write_row(all_fh, row)
                handoff_claim_count += 1
                claim_counts[canonical_source] += 1
                claim_status[status] += 1
                event_claims[eid].append(row)

        normalizer = OTXSourceClaimNormalizer(mitre_path)
        mitre_names = mitre_taxonomy["preferred_names"]
        otx_events = 0
        otx_indicators = 0
        otx_actor_events = 0
        for raw_path in _canonical_otx_files(otx_root):
            wrapper = json.loads(raw_path.read_text(encoding="utf-8"))
            pulse = wrapper.get("payload", wrapper)
            if not isinstance(pulse, Mapping) or not pulse.get("id"):
                continue
            otx_events += 1
            indicators = pulse.get("indicators") or []
            if isinstance(indicators, list):
                otx_indicators += len(indicators)
            raw_provenance = {
                "raw_path": _relative_or_absolute(raw_path, raw_root.parent.parent),
                "fetched_at": wrapper.get("fetched_at"),
                "raw_layout": "rawstore_wrapper.payload",
            }
            _event, original_claims = normalizer.normalize(
                pulse, raw_provenance=raw_provenance
            )
            if original_claims:
                otx_actor_events += 1
            eid = _event_id("otx", str(pulse["id"]))
            for original in original_claims:
                resolved_ids = _unique_strings(
                    original.get("resolved_actor_ids") or []
                )
                canonicals = [
                    mitre_names[actor_id]
                    for actor_id in resolved_ids
                    if actor_id in mitre_names
                ]
                canonical = canonicals[0] if len(canonicals) == 1 else None
                source_field = (
                    f"adversary[{int(original.get('label_index') or 0)}]"
                )
                status = str(original.get("resolution_status") or "unresolved")
                row = {
                    "claim_id": _claim_id(eid, "otx", original["raw_label"], source_field),
                    "event_id": eid,
                    "source": "otx",
                    "source_record_id": str(pulse["id"]),
                    "raw_value": original["raw_label"],
                    "raw_field_value": original.get("raw_field_value"),
                    "normalized_value": original.get("normalized_label"),
                    "canonical_actor": canonical,
                    "resolution_status": status,
                    "candidate_actor_ids": original.get("candidate_actor_ids") or [],
                    "resolved_actor_ids": resolved_ids,
                    "source_field": source_field,
                    "raw_ref": raw_provenance["raw_path"],
                    "claim_scope": "attribution",
                    "set_semantics": "source_set_member",
                    "usage": "candidate",
                    "parse_status": original.get("parse_status"),
                    "match_method": original.get("match_method"),
                }
                if row["claim_id"] in written_claim_ids:
                    continue
                written_claim_ids.add(str(row["claim_id"]))
                _write_row(all_fh, row)
                claim_counts["otx"] += 1
                claim_status[status] += 1
                event_claims[eid].append(row)

    initial_vocabulary = _unique_strings(
        _preferred_actor_name(actor, mitre_taxonomy)
        for actor in _load_initial_vocabulary(initial_vocabulary_path)
    )
    support_events: dict[str, set[str]] = defaultdict(set)
    support_sources: dict[str, set[str]] = defaultdict(set)
    for eid, rows in event_claims.items():
        for row in rows:
            canonical = str(row.get("canonical_actor") or "")
            if (
                canonical
                and row.get("resolved_actor_ids")
                and row["source"] in DIRECT_TRAINING_SOURCES
                and row["claim_scope"] == "attribution"
                and row["usage"] != "provenance_only"
            ):
                support_events[canonical].add(eid)
                support_sources[canonical].add(str(row["source"]))

    approved = set(initial_vocabulary)
    decisions = []
    for actor in sorted(support_events):
        sources = sorted(support_sources[actor])
        events = len(support_events[actor])
        if actor in approved:
            decision = "existing"
        elif events >= 5 and len(sources) >= 2:
            approved.add(actor)
            decision = "added"
        else:
            decision = "insufficient_support"
        decisions.append(
            {
                "actor": actor,
                "event_count": events,
                "source_count": len(sources),
                "sources": sources,
                "decision": decision,
            }
        )

    training_count = 0
    training_source_counts: Counter[str] = Counter()
    conflict_count = 0
    blocked_count = 0
    with _jsonl_writer(training_labels_path) as training_fh:
        for eid in sorted(event_claims):
            rows = [
                row
                for row in event_claims[eid]
                if row["source"] in DIRECT_TRAINING_SOURCES
                and row["claim_scope"] == "attribution"
                and row["usage"] != "provenance_only"
            ]
            if not rows:
                continue
            canonical = {
                str(row["canonical_actor"])
                for row in rows
                if row.get("canonical_actor") and row.get("resolved_actor_ids")
            }
            blocking = [
                row
                for row in rows
                if not (
                    row.get("canonical_actor")
                    and row.get("resolved_actor_ids")
                )
                and row.get("resolution_status")
                not in {"non_actor_value", "non_attributing"}
            ]
            if len(canonical) > 1:
                conflict_count += 1
                continue
            if blocking or len(canonical) != 1:
                blocked_count += 1
                continue
            actor = next(iter(canonical))
            if actor not in approved:
                blocked_count += 1
                continue
            source = str(rows[0]["source"])
            _write_row(
                training_fh,
                {
                    "event_id": eid,
                    "actor": actor,
                    "source": source,
                    "selection_policy": (
                        "all_direct_source_claims_resolve_to_one_approved_canonical_actor"
                    ),
                    "supporting_claim_ids": sorted(
                        str(row["claim_id"]) for row in rows
                    ),
                },
            )
            training_count += 1
            training_source_counts[source] += 1

    vocabulary = {
        "policy": {
            "minimum_events": 5,
            "minimum_sources": 2,
            "context_or_provenance_only_claims_can_promote": False,
            "automatic_unknown_label_promotion": False,
        },
        "initial_actors": initial_vocabulary,
        "approved_actors": sorted(approved),
        "added_actors": [
            row["actor"] for row in decisions if row["decision"] == "added"
        ],
        "decisions": decisions,
    }
    _write_json(vocabulary_review_path, vocabulary)
    return {
        "handoff_claims": handoff_claim_count,
        "all_source_claims": sum(claim_counts.values()),
        "claims_by_source": dict(sorted(claim_counts.items())),
        "claims_by_resolution_status": dict(sorted(claim_status.items())),
        "training_labels": training_count,
        "training_labels_by_source": dict(sorted(training_source_counts.items())),
        "conflicting_events_not_selected": conflict_count,
        "blocked_or_oov_events_not_selected": blocked_count,
        "otx": {
            "events": otx_events,
            "actor_evidenced_events": otx_actor_events,
            "indicator_occurrences": otx_indicators,
            "route": "original_raw_source",
        },
        "vocabulary": {
            "initial_actor_count": len(initial_vocabulary),
            "approved_actor_count": len(approved),
            "added_actor_count": len(vocabulary["added_actors"]),
            "added_actors": vocabulary["added_actors"],
        },
    }


def _enrichment_manifest(raw_root: Path, processed_root: Path) -> dict[str, Any]:
    sources = {
        "threatfox": {
            "role": "optional_enrichment",
            "raw_path": "data/raw/threatfox",
            "normalized_path": (
                "data/processed/trail_multisource_part1_v1_20260724/"
                "normalized/threatfox/ioc_evidence.jsonl"
            ),
        },
        "urlhaus": {
            "role": "optional_enrichment",
            "raw_path": "data/raw/urlhaus",
            "normalized_path": (
                "data/processed/trail_multisource_part1_v1_20260724/"
                "normalized/urlhaus/ioc_evidence.jsonl"
            ),
        },
        "passive_dns": {
            "role": "optional_enrichment",
            "raw_path": "data/raw/pdns",
        },
        "virustotal": {
            "role": "optional_enrichment",
            "raw_path": "data/raw/vt",
        },
    }
    for value in sources.values():
        raw_path = raw_root.parent.parent / value["raw_path"]
        value["raw_exists"] = raw_path.exists()
        normalized = value.get("normalized_path")
        if normalized:
            normalized_path = processed_root.parents[2] / normalized
            value["normalized_exists"] = normalized_path.exists()
    return {
        "base_graph_contains_enrichment": False,
        "sources": sources,
        "application_stage": "after factual base graph construction",
    }


def _load_initial_vocabulary(path: Path | None) -> list[str]:
    if path:
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload if isinstance(payload, list) else payload.get("actors", [])
        return _unique_strings(values)
    # EviTRAIL's active baseline at the verified consumer commit. This is only
    # the starting set; support decisions below may expand it.
    return [
        "Kimsuky",
        "Cobalt Group",
        "Lazarus Group",
        "APT28",
        "APT29",
        "Mustang Panda",
        "Turla",
        "APT41",
        "Sandworm",
        "APT37",
        "Gamaredon",
    ]


def _canonical_otx_files(root: Path) -> Iterator[Path]:
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        files = sorted(directory.glob("*.json"))
        if files:
            yield files[-1]


def _mitre_taxonomy(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    preferred_names: dict[str, str] = {}
    aliases: dict[str, set[str]] = defaultdict(set)
    for item in payload.get("objects", []):
        if not isinstance(item, Mapping) or item.get("type") != "intrusion-set":
            continue
        attack_id = ""
        for reference in item.get("external_references") or []:
            if (
                isinstance(reference, Mapping)
                and reference.get("source_name") == "mitre-attack"
            ):
                attack_id = str(reference.get("external_id") or "")
                break
        if not attack_id or not item.get("name"):
            continue
        actor_id = f"actor_{attack_id}"
        preferred_names[actor_id] = str(item["name"])
        names = [
            str(item["name"]),
            *(str(value) for value in item.get("aliases") or [] if value),
            *(str(value) for value in item.get("x_mitre_aliases") or [] if value),
            attack_id,
        ]
        for name in names:
            aliases[_actor_key(name)].add(actor_id)
    return {
        "preferred_names": preferred_names,
        "aliases": aliases,
    }


def _resolve_mitre_identity(
    raw_value: str,
    taxonomy: Mapping[str, Any],
    *,
    fallback: str = "",
) -> dict[str, Any]:
    aliases = taxonomy["aliases"]
    raw_key = _actor_key(raw_value)
    override = LEGACY_CANONICAL_OVERRIDES.get(raw_key)
    matches = set(
        aliases.get(_actor_key(override), set())
        if override
        else aliases.get(raw_key, set())
    )
    if not matches and fallback:
        fallback_key = _actor_key(fallback)
        fallback_override = LEGACY_CANONICAL_OVERRIDES.get(fallback_key)
        matches.update(
            aliases.get(_actor_key(fallback_override), set())
            if fallback_override
            else aliases.get(fallback_key, set())
        )
    if len(matches) == 1:
        actor_id = next(iter(matches))
        return {
            "resolution_status": "resolved",
            "resolved_actor_ids": [actor_id],
            "canonical_actor": taxonomy["preferred_names"][actor_id],
        }
    if len(matches) > 1:
        return {
            "resolution_status": "ambiguous_taxonomy",
            "resolved_actor_ids": [],
            "candidate_actor_ids": sorted(matches),
            "canonical_actor": None,
        }
    return {
        "resolution_status": "resolved" if fallback else "unresolved",
        "resolved_actor_ids": [],
        "canonical_actor": fallback or None,
    }


def _preferred_actor_name(
    value: str, taxonomy: Mapping[str, Any]
) -> str:
    resolution = _resolve_mitre_identity(value, taxonomy)
    return str(resolution.get("canonical_actor") or value)


def _actor_key(value: str) -> str:
    return "".join(char for char in str(value).casefold() if char.isalnum())


def _is_actor_identity(value: str) -> bool:
    text = str(value or "")
    return text.startswith(("actor_G", "malpedia:actor:", "intrusion-set--"))


def _normalized_indicator(raw_type: Any, raw_value: Any) -> tuple[str, str] | None:
    kind = str(raw_type or "").strip().lower()
    value = str(raw_value or "").strip()
    if kind == "domain":
        normalized = _normalize_domain(value)
    elif kind == "ip":
        normalized = _normalize_ip(value)
    elif kind == "url":
        normalized = _normalize_url(value)
    elif kind == "asn":
        normalized = _normalize_asn(value)
    else:
        return None
    return (kind, normalized) if normalized else None


def _normalize_domain(value: str) -> str | None:
    text = value.strip().rstrip(".").lower()
    if not text or len(text) > 253:
        return None
    try:
        text = text.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    labels = text.split(".")
    if len(labels) < 2 or any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        for label in labels
    ):
        return None
    return text


def _normalize_ip(value: str) -> str | None:
    text = value.strip()
    if text.startswith("[") and "]" in text:
        text = text[1 : text.index("]")]
    elif text.count(":") == 1:
        host, port = text.rsplit(":", 1)
        if port.isdigit():
            text = host
    try:
        return ipaddress.ip_address(text).compressed
    except ValueError:
        return None


def _normalize_url(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = urlsplit(text)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    host = _normalize_ip(parsed.hostname) or _normalize_domain(parsed.hostname)
    if not host:
        return None
    host_text = f"[{host}]" if ":" in host else host
    netloc = host_text
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunsplit(
        (parsed.scheme.lower(), netloc, parsed.path or "", parsed.query, "")
    )


def _normalize_asn(value: str) -> str | None:
    text = value.strip().upper()
    if text.startswith("AS"):
        text = text[2:].strip()
    if not text.isdigit():
        return None
    number = int(text)
    return f"AS{number}" if 0 <= number <= 4294967295 else None


def _url_host(url: str) -> tuple[str, str] | None:
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    if normalized_ip := _normalize_ip(host):
        return "ip", normalized_ip
    if normalized_domain := _normalize_domain(host):
        return "domain", normalized_domain
    return None


def _inline_evidence(
    evidence: Mapping[str, Any],
    source: str,
    raw_ref: str,
    record_path: str,
) -> dict[str, Any]:
    row = {
        "source": source,
        "raw_ref": raw_ref,
        "record_path": record_path,
        "derivation": "source_asserted",
        "raw_value": evidence.get("ioc_value_raw") or evidence.get("ioc_value"),
        "observed_at": evidence.get("first_seen"),
        "first_seen": evidence.get("first_seen"),
        "last_seen": evidence.get("last_seen"),
        "timestamp_basis": evidence.get("timestamp_basis"),
        "source_record_id": evidence.get("source_record_id"),
        "evidence_id": evidence.get("evidence_id"),
    }
    return {key: value for key, value in row.items() if value is not None}


def _edge_row(
    relation: str,
    source_id: str,
    target_id: str,
    evidence: Mapping[str, Any],
    ordinal: int,
) -> dict[str, Any]:
    edge_identity = _stable_hash(
        relation,
        source_id,
        target_id,
        evidence.get("source"),
        evidence.get("raw_ref"),
        evidence.get("record_path"),
        ordinal,
    )
    return {
        "edge_id": f"edge:{edge_identity}",
        "relation": relation,
        "source_id": source_id,
        "target_id": target_id,
        "evidence": [dict(evidence)],
    }


def _insert_node(
    connection: sqlite3.Connection,
    node_id: str,
    node_type: str,
    value: str,
    properties: Mapping[str, Any] | None = None,
) -> None:
    if node_type not in NODE_TYPES:
        raise ValueError(f"unsupported node type: {node_type}")
    connection.execute(
        "INSERT OR IGNORE INTO nodes(node_id,type,value,properties) VALUES(?,?,?,?)",
        (
            node_id,
            node_type,
            value,
            json.dumps(properties, ensure_ascii=False, sort_keys=True)
            if properties
            else None,
        ),
    )


def _write_nodes(connection: sqlite3.Connection, path: Path) -> int:
    count = 0
    with _jsonl_writer(path) as fh:
        for node_id, node_type, value, properties in connection.execute(
            "SELECT node_id,type,value,properties FROM nodes ORDER BY type,node_id"
        ):
            row = {"node_id": node_id, "type": node_type, "value": value}
            if properties:
                row["properties"] = json.loads(properties)
            _write_row(fh, row)
            count += 1
    return count


def _repository_raw_ref(source: str, value: Any, raw_root: Path) -> str:
    if isinstance(value, Mapping):
        value = (
            value.get("repository_raw_path")
            or value.get("raw_path")
            or value.get("path")
            or ""
        )
    text = str(value or "").replace("\\", "/")
    if not text:
        return ""
    if text.startswith("data/raw/"):
        return text
    folder = {
        "misp": "circl_misp",
        "orkl": "orkl",
        "aptnotes": "aptnotes",
        "cisa": "cisa",
    }[source]
    return f"data/raw/{folder}/{text.lstrip('/')}"


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _event_id(source: str, source_record_id: str) -> str:
    raw = str(source_record_id)
    return raw if raw.startswith("event:") else f"event:{source}:{raw}"


def _node_id(node_type: str, value: str) -> str:
    if node_type == "asn":
        return f"asn:{value}"
    return f"{node_type}:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _claim_id(event: str, source: str, raw_value: str, record_path: str) -> str:
    return f"claim:{_stable_hash(event, source, raw_value, record_path)}"


def _stable_hash(*parts: Any) -> str:
    payload = json.dumps(
        parts, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                if isinstance(row, dict):
                    yield row


def _jsonl_writer(path: Path) -> TextIO:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("w", encoding="utf-8", newline="\n")


def _write_row(fh: TextIO, row: Mapping[str, Any]) -> None:
    fh.write(
        json.dumps(
            row, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        + "\n"
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _unique_strings(values: Iterable[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            output.append(text)
            seen.add(text)
    return output


def _file_manifest(root: Path) -> list[dict[str, Any]]:
    output = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "manifest.json" and path.parent == root:
            continue
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            while chunk := fh.read(1024 * 1024):
                digest.update(chunk)
        output.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest.hexdigest(),
            }
        )
    return output


def _write_readme(root: Path, manifest: Mapping[str, Any]) -> None:
    counts = manifest["counts"]
    content = f"""# EviTRAIL complete multi-source data handoff

This package is data only. It contains no checkpoint, model weight, training
result, confidence score, or prediction.

## What to read

- `handoff/` is directly readable by `evitrail.data.readers.read_handoff`.
- `labels/all_source_claims.jsonl` preserves original and normalized actor
  claims from every Event source, including multiple, conflicting, ambiguous,
  unresolved, and out-of-vocabulary claims.
- `labels/training_labels.jsonl` is the separate strict training-label view.
- `labels/vocabulary_review.json` records review/update decisions; the old
  fixed vocabulary is only the starting set and is not imposed on new sources.
- `enrichment_inputs/manifest.json` keeps ThreatFox, URLhaus, passive DNS, and
  VirusTotal separate from the factual base.
- Full OTX Pulse details remain under `data/raw/otx`. This preserves all OTX
  metadata and all {counts['otx_indicator_occurrences']:,} indicator occurrences
  without duplicating several gigabytes into the handoff.

## Required OTX interpretation

Round 1 was a broad subscribed-feed collection without actor seeds. Round 2
used the MITRE ATT&CK intrusion-set actor list and aliases only as discovery
queries. A query match is never an actor label. OTX actor claims come only from
the Pulse `adversary` source field.

## Base run

```powershell
python -m evitrail.data.pipeline `
  --handoff <package>\\handoff `
  --raw-root __disabled__ `
  --otx <cti-rag>\\data\\raw\\otx `
  --mitre <cti-rag>\\data\\raw\\mitre\\enterprise-attack.json `
  --malpedia <cti-rag>\\data\\raw\\malpedia\\raw\\actors\\actors.json `
  --enrichment none `
  --out build\\data
```

The handoff contributes {counts['handoff_events']:,} non-OTX Events. The OTX
raw route contributes {counts['otx_events']:,} Pulse Events. Enrichment is an
explicit later stage and does not overwrite the base graph.
"""
    (root / "README.md").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
