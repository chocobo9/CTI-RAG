"""OTX-only downstream projection for teammate Neo4j/GNN consumption."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rag_cti.connectors.pdns_projection import project_pdns_raw
from rag_cti.intermediate.contract import contract_id
from rag_cti.intermediate.jsonl import write_jsonl
from rag_cti.preprocess.indicators import canonical_indicator_type

_WHITESPACE_RE = re.compile(r"\s+")
_TOP_LEVEL_AND_RE = re.compile(r"\band\b", re.IGNORECASE)
_ACTOR_TOKEN_RE = re.compile(r"^(?:APT\s*-?\s*[A-Z0-9-]+|[A-Z][A-Za-z0-9-]*(?:[- ][A-Z0-9][A-Za-z0-9-]*){0,4})$")
_NON_ACTOR_VALUES = {
    "advisory",
    "informational",
    "malware advisory",
    "n/a",
    "none",
    "unknown",
}
_ORG_MARKERS_RE = re.compile(
    r"\b(?:co\.?|corp\.?|corporation|inc\.?|llc|ltd\.?|limited|media)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OTXDownstreamProjectionResult:
    output_dir: Path
    event_count: int
    ioc_count: int
    edge_count: int
    raw_observation_count: int
    raw_layouts: dict[str, int]


@dataclass(frozen=True)
class _RawObservation:
    source_id: str
    fetched_at: str | None
    raw_path: str
    raw_sha256: str
    raw_layout: str
    pulse: Mapping[str, Any]


@dataclass(frozen=True)
class _PDNSObservation:
    domain: str
    raw_path: str
    raw_sha256: str
    fetched_at: str | None
    record: Mapping[str, Any]


@dataclass(frozen=True)
class _EndpointIndicatorPageObservation:
    pulse_id: str
    raw_path: str
    raw_sha256: str
    fetched_at: str | None
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class _ActorLabelClaim:
    raw_field_value: str
    raw_label: str
    normalized_label: str
    label_index: int
    parse_status: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _MitreActor:
    actor_id: str
    actor_name: str
    taxonomy_id: str | None
    stix_id: str
    aliases: tuple[str, ...]
    taxonomy_ref: str | None
    modified: str | None
    revoked: bool
    deprecated: bool


@dataclass(frozen=True)
class _MitreActorMatch:
    actor: _MitreActor
    matched_label: str
    match_method: str


@dataclass(frozen=True)
class _MitreActorTaxonomy:
    taxonomy: str
    taxonomy_version: str | None
    actors_by_id: dict[str, _MitreActor]
    matches_by_label: dict[str, tuple[_MitreActorMatch, ...]]


@dataclass(frozen=True)
class _ResolvedActorLabelClaim:
    claim: _ActorLabelClaim
    resolution_status: str
    resolved_actor_ids: tuple[str, ...]
    candidate_actor_ids: tuple[str, ...]
    match_method: str | None
    matched_taxonomy_labels: tuple[str, ...]
    resolution_taxonomy: str | None
    taxonomy_version: str | None
    contributes_to_attribution: bool


@dataclass(frozen=True)
class _OTXInputSelection:
    observations: list[_RawObservation]
    endpoint_pages_by_pulse: dict[str, list[_EndpointIndicatorPageObservation]]
    completed_pulse_ids: tuple[str, ...]
    input_metadata: dict[str, Any]
    input_counts: dict[str, int]


def build_otx_downstream_projection(
    raw_otx_dir: Path,
    output_dir: Path,
    *,
    pdns_raw_dir: Path | None = None,
    mitre_attack_path: Path | None = None,
    otx_run_dir: Path | None = None,
    checkpoint_path: Path | None = None,
) -> OTXDownstreamProjectionResult:
    """Build OTX-only graph-ready JSONL artifacts from local raw OTX material.

    The projection is downstream-only: it reads flat OTX pulse JSON files and
    versioned RawStore wrapper files, but writes only projection artifacts.
    """
    input_selection = _select_otx_input_observations(
        raw_otx_dir=Path(raw_otx_dir),
        otx_run_dir=Path(otx_run_dir) if otx_run_dir is not None else None,
        checkpoint_path=Path(checkpoint_path) if checkpoint_path is not None else None,
    )
    observations = input_selection.observations
    actor_taxonomy = _load_mitre_actor_taxonomy(mitre_attack_path)
    grouped: dict[str, list[_RawObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.source_id].append(observation)

    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges_by_id: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    actors_by_id: dict[str, dict[str, Any]] = {}
    actor_label_claims: list[dict[str, Any]] = []

    for source_id in sorted(grouped):
        event_observations = sorted(grouped[source_id], key=_observation_sort_key)
        endpoint_pages = input_selection.endpoint_pages_by_pulse.get(source_id, [])
        event = _event_row(source_id, event_observations, actor_taxonomy)
        events.append(event)
        nodes_by_id[event["node_id"]] = event
        event_claim_rows = _actor_label_claim_rows(event, actor_taxonomy)
        actor_label_claims.extend(event_claim_rows)
        for actor_row in _actor_rows_from_claims(event_claim_rows, actor_taxonomy):
            actors_by_id.setdefault(actor_row["node_id"], actor_row)
        for edge in _attributed_to_edges(event, event_claim_rows):
            edges_by_id[edge["edge_id"]] = edge

        for indicator, evidence_refs, endpoint_matches in _indicator_evidence(
            event_observations,
            endpoint_pages,
        ):
            ioc = _ioc_from_indicator(indicator, evidence_refs)
            if ioc is None:
                continue
            nodes_by_id.setdefault(ioc["node_id"], ioc)
            edge = _in_report_edge(event, ioc, indicator, evidence_refs, endpoint_matches)
            edges_by_id[edge["edge_id"]] = edge

            for derived_node, derived_edge in _url_host_projection(ioc, evidence_refs):
                nodes_by_id.setdefault(derived_node["node_id"], derived_node)
                edges_by_id[derived_edge["edge_id"]] = derived_edge

    pdns_forward_records = 0
    if pdns_raw_dir is not None:
        pdns_forward_records = _add_forward_pdns_projection(
            pdns_raw_dir=Path(pdns_raw_dir),
            nodes_by_id=nodes_by_id,
            edges_by_id=edges_by_id,
        )

    event_rows = sorted(events, key=lambda row: row["node_id"])
    actor_rows = sorted(actors_by_id.values(), key=lambda row: row["node_id"])
    ioc_rows = sorted(
        (
            row
            for row in nodes_by_id.values()
            if row["node_kind"] in {"ioc", "infrastructure"}
        ),
        key=lambda row: (row["labels"], row["value"], row["node_id"]),
    )
    edge_rows = sorted(edges_by_id.values(), key=lambda row: row["edge_id"])
    actor_label_claim_rows = sorted(
        actor_label_claims,
        key=lambda row: (str(row["source_record_id"]), row["label_index"], row["claim_id"]),
    )
    layout_counts = dict(sorted(Counter(obs.raw_layout for obs in observations).items()))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "nodes_events.jsonl", event_rows)
    write_jsonl(output_dir / "nodes_actors.jsonl", actor_rows)
    write_jsonl(output_dir / "nodes_iocs.jsonl", ioc_rows)
    write_jsonl(output_dir / "actor_label_claims.jsonl", actor_label_claim_rows)
    write_jsonl(output_dir / "edges.jsonl", edge_rows)
    indicator_source_coverage = _indicator_source_coverage(
        input_selection.completed_pulse_ids,
        grouped,
        input_selection.endpoint_pages_by_pulse,
    )
    _write_json(output_dir / "indicator_source_coverage.json", indicator_source_coverage)
    time_feature_coverage = _time_feature_coverage(event_rows, edge_rows)
    _write_json(output_dir / "time_feature_coverage.json", time_feature_coverage)
    actor_label_summary = _actor_label_summary(event_rows)
    _write_json(output_dir / "actor_label_summary.json", actor_label_summary)
    _write_json(
        output_dir / "projection_manifest.json",
        {
            "projection": "otx_downstream_neo4j_ready",
            "schema_version": "v0.1",
            "source": "otx",
            "inputs": {
                "raw_otx_dir": str(Path(raw_otx_dir)),
                "mitre_attack_path": str(
                    Path(mitre_attack_path)
                    if mitre_attack_path is not None
                    else Path("data/raw/mitre/enterprise-attack.json")
                ),
                **input_selection.input_metadata,
            },
            "artifacts": {
                "events": "nodes_events.jsonl",
                "actors": "nodes_actors.jsonl",
                "iocs": "nodes_iocs.jsonl",
                "edges": "edges.jsonl",
                "actor_label_claims": "actor_label_claims.jsonl",
                "indicator_source_coverage": "indicator_source_coverage.json",
                "time_feature_coverage": "time_feature_coverage.json",
                "actor_label_summary": "actor_label_summary.json",
                "acceptance_lint": "acceptance_lint.json",
            },
            "counts": {
                "events": len(event_rows),
                "actors": len(actor_rows),
                "iocs": len(ioc_rows),
                "edges": len(edge_rows),
                "actor_label_claims": len(actor_label_claim_rows),
                "raw_observations": len(observations),
                "raw_layouts": layout_counts,
                "endpoint_indicator_pages": sum(
                    len(pages) for pages in input_selection.endpoint_pages_by_pulse.values()
                ),
                "pdns_forward_records": pdns_forward_records,
                **input_selection.input_counts,
            },
            "time_features": {
                "event": ["pulse_created", "pulse_modified", "fetched_first", "fetched_last"],
                "in_report_edge": ["indicator_created"],
                "pdns_domain_resolves_to_ip_edge": ["first_seen", "last_seen", "duration_days"],
            },
            "deferred": [
                "reverse pDNS is intentionally not performed in this first OTX pass",
                "ASN nodes are emitted only when source-backed pDNS data is available; OTX pulses usually do not provide ASN",
                "actor-label normalization expansion remains an open issue; only exact MITRE actor names and aliases resolve",
                "Neo4j loader, confidence field policy, and disagreement calculation remain open or deferred",
            ],
        },
    )
    lint_result = lint_otx_downstream_projection(output_dir)
    _write_json(output_dir / "acceptance_lint.json", lint_result)
    return OTXDownstreamProjectionResult(
        output_dir=output_dir,
        event_count=len(event_rows),
        ioc_count=len(ioc_rows),
        edge_count=len(edge_rows),
        raw_observation_count=len(observations),
        raw_layouts=layout_counts,
    )


def lint_otx_downstream_projection(output_dir: Path) -> dict[str, Any]:
    """Validate OTX downstream artifacts and return actionable findings."""
    output_dir = Path(output_dir)
    findings: list[dict[str, Any]] = []
    artifacts = _load_projection_artifacts(output_dir, findings)
    if artifacts is not None:
        manifest, events, actors, iocs, edges = artifacts
        _lint_manifest_counts(findings, manifest, events, actors, iocs, edges)
        _lint_edge_endpoints(findings, events, actors, iocs, edges)
        _lint_raw_refs(findings, output_dir, events, iocs, edges)
        _lint_semantics(findings, events, edges)
        _add_report(
            findings,
            "artifact_coverage_summary",
            "projection artifacts parsed and semantic lint completed",
            {
                "events": len(events),
                "iocs": len(iocs),
                "edges": len(edges),
            },
        )
    counts = Counter(finding["severity"] for finding in findings)
    return {
        "schema_version": "v0.1",
        "ok": counts.get("fail", 0) == 0,
        "counts": {
            "fail": counts.get("fail", 0),
            "warn": counts.get("warn", 0),
            "report": counts.get("report", 0),
            "deferred": counts.get("deferred", 0),
        },
        "findings": findings,
    }


def _time_feature_coverage(
    event_rows: list[dict[str, Any]],
    edge_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    in_report_edges = [edge for edge in edge_rows if edge.get("type") == "InReport"]
    pdns_domain_resolves_to_ip = [
        edge
        for edge in edge_rows
        if edge.get("type") == "ResolvesTo"
        and edge.get("start_label") == "Domain"
        and edge.get("end_label") == "IP"
        and edge.get("properties", {}).get("source") == "pdns"
    ]
    url_resolves_to_ip = [
        edge
        for edge in edge_rows
        if edge.get("type") == "ResolvesTo"
        and edge.get("start_label") == "URL"
        and edge.get("end_label") == "IP"
    ]
    hosted_on = [edge for edge in edge_rows if edge.get("type") == "HostedOn"]
    return {
        "schema_version": "v0.1",
        "source": "otx_downstream_projection",
        "event_time_features": {
            "pulse_created": _row_field_coverage(
                event_rows,
                "pulse_created",
                source="otx",
                source_field="pulse.created",
            ),
            "pulse_modified": _row_field_coverage(
                event_rows,
                "pulse_modified",
                source="otx",
                source_field="pulse.modified",
            ),
            "fetched_first": _row_field_coverage(
                event_rows,
                "fetched_first",
                source="otx_rawstore",
                source_field="raw_ref.fetched_at",
            ),
            "fetched_last": _row_field_coverage(
                event_rows,
                "fetched_last",
                source="otx_rawstore",
                source_field="raw_ref.fetched_at",
            ),
        },
        "in_report_edge_time_features": {
            "indicator_created": _edge_property_coverage(
                in_report_edges,
                "indicator_created",
                source="otx",
                source_field="indicators[].created",
            )
        },
        "infrastructure_edge_time_features": {
            "pdns_domain_resolves_to_ip": {
                "total": len(pdns_domain_resolves_to_ip),
                "first_seen_present": _edge_property_present(pdns_domain_resolves_to_ip, "first_seen"),
                "last_seen_present": _edge_property_present(pdns_domain_resolves_to_ip, "last_seen"),
                "duration_days_present": _edge_property_present(
                    pdns_domain_resolves_to_ip,
                    "duration_days",
                ),
                "source": "pdns",
                "source_fields": {
                    "first_seen": "passive_dns[].first",
                    "last_seen": "passive_dns[].last",
                },
            },
            "url_resolves_to_ip": {
                "total": len(url_resolves_to_ip),
                "source": "otx",
                "time_fields": [],
                "notes": [
                    "URL-to-IP edges are derived by parsing an IP host from the URL; OTX does not provide observed first/last for this derived relation."
                ],
            },
            "url_hosted_on_domain": {
                "total": len(hosted_on),
                "source": "otx",
                "time_fields": [],
                "notes": [
                    "URL-to-domain HostedOn edges are deterministic URL host decomposition; OTX does not provide observed first/last for this derived relation."
                ],
            },
        },
    }


def _actor_label_summary(event_rows: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts: Counter[str] = Counter()
    multi_actor_events: list[dict[str, Any]] = []
    single_actor = 0
    multi_actor = 0
    missing_actor = 0

    for event in event_rows:
        labels = [
            label
            for label in event.get("actor_labels", [])
            if isinstance(label, str) and label.strip()
        ]
        label_counts.update(labels)
        if len(labels) == 0:
            missing_actor += 1
        elif len(labels) == 1:
            single_actor += 1
        else:
            multi_actor += 1
            multi_actor_events.append(
                {
                    "event_id": event["node_id"],
                    "source_record_id": event["source_record_id"],
                    "actor_label_raw": event.get("actor_label_raw"),
                    "actor_labels": labels,
                }
            )

    return {
        "schema_version": "v0.1",
        "source": "otx_downstream_projection",
        "counts": {
            "events": len(event_rows),
            "single_actor": single_actor,
            "multi_actor": multi_actor,
            "missing_actor": missing_actor,
        },
        "actor_label_counts": dict(sorted(label_counts.items())),
        "multi_actor_events": sorted(
            multi_actor_events,
            key=lambda row: str(row["source_record_id"]),
        ),
        "notes": [
            "This summary preserves OTX actor labels as source-provided cues.",
            "It does not perform actor alias mapping or disagreement classification.",
        ],
    }


def _indicator_source_coverage(
    completed_pulse_ids: tuple[str, ...],
    grouped_observations: Mapping[str, list[_RawObservation]],
    endpoint_pages_by_pulse: Mapping[str, list[_EndpointIndicatorPageObservation]],
) -> dict[str, Any]:
    completed = list(completed_pulse_ids)
    embedded_counts: dict[str, int] = {}
    endpoint_counts: dict[str, int] = {}
    endpoint_matches_embedded = 0

    for pulse_id in completed:
        observations = grouped_observations.get(pulse_id, [])
        endpoint_pages = endpoint_pages_by_pulse.get(pulse_id, [])
        embedded_count = sum(
            len(_indicator_dicts(observation.pulse.get("indicators")))
            for observation in observations
        )
        endpoint_count = sum(
            len(_endpoint_indicator_dicts(page.payload))
            for page in endpoint_pages
        )
        embedded_counts[pulse_id] = embedded_count
        endpoint_counts[pulse_id] = endpoint_count
        endpoint_matches_embedded += _endpoint_match_count_for_observations(
            observations,
            endpoint_pages,
        )

    endpoint_covered = [pulse_id for pulse_id in completed if endpoint_pages_by_pulse.get(pulse_id)]
    count_matches = sum(
        1
        for pulse_id in endpoint_covered
        if endpoint_counts[pulse_id] == embedded_counts[pulse_id]
    )
    count_less = sum(
        1
        for pulse_id in endpoint_covered
        if endpoint_counts[pulse_id] < embedded_counts[pulse_id]
    )
    count_greater = sum(
        1
        for pulse_id in endpoint_covered
        if endpoint_counts[pulse_id] > embedded_counts[pulse_id]
    )
    return {
        "schema_version": "v0.1",
        "source": "otx_downstream_projection",
        "indicator_source_policy": "embedded_pulse_detail_primary_endpoint_optional_enrichment",
        "counts": {
            "completed_pulses": len(completed),
            "pulses_with_endpoint_pages": len(endpoint_covered),
            "pulses_missing_endpoint_pages": len(completed) - len(endpoint_covered),
            "endpoint_count_matches_embedded": count_matches,
            "endpoint_count_less_than_embedded": count_less,
            "endpoint_count_greater_than_embedded": count_greater,
            "endpoint_count_different_from_embedded": count_less + count_greater,
            "embedded_indicator_observations": sum(embedded_counts.values()),
            "endpoint_indicator_observations": sum(endpoint_counts.values()),
            "endpoint_indicator_matches_embedded": endpoint_matches_embedded,
        },
        "notes": [
            "Embedded pulse_detail.indicators are the primary Event-IOC source.",
            "Endpoint indicator pages only enrich exact embedded indicator matches.",
            "Endpoint-only indicators are audit evidence and do not create Event-IOC backbone edges.",
        ],
    }


def _endpoint_match_count_for_observations(
    observations: list[_RawObservation],
    endpoint_pages: list[_EndpointIndicatorPageObservation],
) -> int:
    endpoint_matches = _endpoint_matches_by_key(endpoint_pages)
    count = 0
    for observation in observations:
        for indicator in _indicator_dicts(observation.pulse.get("indicators")):
            value = _text(indicator.get("indicator"))
            if not value:
                continue
            raw_type = _text(indicator.get("type")) or None
            canonical = canonical_indicator_type(raw_type) if raw_type else None
            count += len(
                _endpoint_matches_for_indicator(
                    {
                        "value": value,
                        "raw_type": raw_type,
                        "canonical_type": canonical,
                        "created": _text(indicator.get("created")) or None,
                    },
                    endpoint_matches,
                )
            )
    return count


def _load_projection_artifacts(
    output_dir: Path,
    findings: list[dict[str, Any]],
) -> (
    tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]
    | None
):
    manifest = _read_json_artifact(output_dir / "projection_manifest.json", findings)
    events = _read_jsonl_artifact(output_dir / "nodes_events.jsonl", findings)
    actors = _read_jsonl_artifact(output_dir / "nodes_actors.jsonl", findings)
    iocs = _read_jsonl_artifact(output_dir / "nodes_iocs.jsonl", findings)
    edges = _read_jsonl_artifact(output_dir / "edges.jsonl", findings)
    if manifest is None or events is None or actors is None or iocs is None or edges is None:
        return None
    return manifest, events, actors, iocs, edges


def _read_json_artifact(path: Path, findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not path.is_file():
        _add_failure(
            findings,
            "missing_artifact",
            path.name,
            f"required artifact is missing: {path.name}",
            "Projection package is incomplete and should not be delivered.",
            failed_examples=[{"path": path.as_posix()}],
            next_step="Regenerate the projection package from raw inputs.",
            likely_causes=["writer did not emit the artifact", "output directory is stale or partial"],
            do_not=["do not hand-create empty artifacts to pass lint"],
        )
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _add_failure(
            findings,
            "json_parse_error",
            path.name,
            f"JSON artifact does not parse: {path.name}",
            "Downstream consumers cannot safely read the projection package.",
            failed_examples=[{"path": path.as_posix(), "error": str(exc)}],
            next_step="Fix the writer and regenerate the artifact.",
            likely_causes=["partial write", "manual edit", "non-JSON content"],
            do_not=["do not delete fields or hand-edit JSON to hide the parse error"],
        )
        return None
    if not isinstance(value, dict):
        _add_failure(
            findings,
            "json_shape_error",
            path.name,
            f"JSON artifact must be an object: {path.name}",
            "Lint cannot validate artifact counts or metadata.",
            failed_examples=[{"path": path.as_posix(), "actual_type": type(value).__name__}],
            next_step="Fix the artifact writer to emit a JSON object.",
            likely_causes=["wrong serializer input"],
            do_not=["do not wrap invalid content without fixing the writer"],
        )
        return None
    return value


def _read_jsonl_artifact(
    path: Path,
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    if not path.is_file():
        _add_failure(
            findings,
            "missing_artifact",
            path.name,
            f"required artifact is missing: {path.name}",
            "Projection package is incomplete and should not be delivered.",
            failed_examples=[{"path": path.as_posix()}],
            next_step="Regenerate the projection package from raw inputs.",
            likely_causes=["writer did not emit the artifact", "output directory is stale or partial"],
            do_not=["do not hand-create empty artifacts to pass lint"],
        )
        return None
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            _add_failure(
                findings,
                "jsonl_parse_error",
                path.name,
                f"JSONL row does not parse in {path.name}",
                "Downstream import may fail or silently skip rows.",
                failed_examples=[{"path": path.as_posix(), "line": index, "error": str(exc)}],
                next_step="Fix the writer and regenerate the full artifact.",
                likely_causes=["partial write", "manual edit", "invalid escaping"],
                do_not=["do not delete bad lines and continue delivery"],
            )
            return None
        if not isinstance(value, dict):
            _add_failure(
                findings,
                "jsonl_shape_error",
                path.name,
                f"JSONL row must be an object in {path.name}",
                "Projection rows need stable keys for downstream import.",
                failed_examples=[
                    {"path": path.as_posix(), "line": index, "actual_type": type(value).__name__}
                ],
                next_step="Fix the writer to emit object rows and regenerate.",
                likely_causes=["wrong serializer input"],
                do_not=["do not wrap invalid rows without fixing their schema"],
            )
            return None
        rows.append(value)
    return rows


def _lint_manifest_counts(
    findings: list[dict[str, Any]],
    manifest: Mapping[str, Any],
    events: list[dict[str, Any]],
    actors: list[dict[str, Any]],
    iocs: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    expected = manifest.get("counts") if isinstance(manifest.get("counts"), Mapping) else {}
    actual = {
        "events": len(events),
        "actors": len(actors),
        "iocs": len(iocs),
        "edges": len(edges),
    }
    mismatches = {
        key: {"manifest": expected.get(key), "actual": actual[key]}
        for key in actual
        if expected.get(key) != actual[key]
    }
    if mismatches:
        _add_failure(
            findings,
            "manifest_count_mismatch",
            "projection_manifest.json",
            "manifest row counts do not match artifact row counts",
            "Consumers may size imports or validate completeness using incorrect counts.",
            failed_examples=[mismatches],
            next_step="Regenerate the projection manifest from actual emitted rows.",
            likely_causes=["manifest was written before final rows", "artifact edited after generation"],
            do_not=["do not manually edit counts without regenerating artifacts"],
        )


def _lint_edge_endpoints(
    findings: list[dict[str, Any]],
    events: list[dict[str, Any]],
    actors: list[dict[str, Any]],
    iocs: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    node_ids = {str(row.get("node_id")) for row in events + actors + iocs if row.get("node_id")}
    failed: list[dict[str, Any]] = []
    for edge in edges:
        for field in ("start_node_id", "end_node_id"):
            node_id = str(edge.get(field))
            if node_id not in node_ids:
                failed.append(
                    {
                        "edge_id": edge.get("edge_id"),
                        "field": field,
                        "missing_node_id": node_id,
                    }
                )
                if len(failed) >= 10:
                    break
        if len(failed) >= 10:
            break
    if failed:
        _add_failure(
            findings,
            "edge_endpoint_missing",
            "edges.jsonl",
            "edge endpoint node_id does not exist in node artifacts",
            "Graph import cannot reliably join edges to nodes.",
            failed_examples=failed,
            next_step="Regenerate projection after you fix node emission/id normalization.",
            likely_causes=[
                "edge was emitted before derived node was added",
                "node id normalization differs between node and edge builders",
            ],
            do_not=[
                "do not create placeholder nodes without raw_refs",
                "do not drop failing edges silently",
            ],
        )


def _lint_raw_refs(
    findings: list[dict[str, Any]],
    output_dir: Path,
    events: list[dict[str, Any]],
    iocs: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    failed: list[dict[str, Any]] = []
    checked: dict[tuple[str, str | None], str | None] = {}
    for row in events + iocs:
        _collect_raw_ref_failures(
            failed,
            output_dir,
            row.get("raw_refs"),
            row.get("node_id"),
            checked,
        )
        if len(failed) >= 10:
            break
    for edge in edges:
        props = edge.get("properties") if isinstance(edge.get("properties"), Mapping) else {}
        _collect_raw_ref_failures(
            failed,
            output_dir,
            props.get("raw_refs"),
            edge.get("edge_id"),
            checked,
        )
        if len(failed) >= 10:
            break
    if failed:
        _add_failure(
            findings,
            "raw_ref_missing_or_hash_mismatch",
            "projection artifacts",
            "raw_refs are missing, unreadable, or hash mismatched",
            "Projection rows are not source-traceable and cannot be audited.",
            failed_examples=failed[:10],
            next_step="Rebuild projection from raw; if raw is missing, repair the collection package first.",
            likely_causes=["stale projection", "raw file moved", "hash computed over different bytes"],
            do_not=[
                "do not remove raw_refs to pass lint",
                "do not reconstruct raw from projected rows",
            ],
        )


def _collect_raw_ref_failures(
    failed: list[dict[str, Any]],
    output_dir: Path,
    raw_refs: Any,
    owner_id: Any,
    checked: dict[tuple[str, str | None], str | None],
) -> None:
    if not isinstance(raw_refs, list) or not raw_refs:
        failed.append({"owner_id": owner_id, "reason": "missing_raw_refs"})
        return
    for raw_ref in raw_refs:
        if not isinstance(raw_ref, Mapping):
            failed.append({"owner_id": owner_id, "reason": "raw_ref_not_object"})
            continue
        raw_path = raw_ref.get("raw_path")
        expected_sha = raw_ref.get("raw_sha256")
        if not isinstance(raw_path, str) or not raw_path:
            failed.append({"owner_id": owner_id, "reason": "missing_raw_path"})
            continue
        cache_key = (raw_path, expected_sha if isinstance(expected_sha, str) else None)
        cached_reason = checked.get(cache_key)
        if cache_key in checked:
            if cached_reason is not None:
                failed.append({"owner_id": owner_id, "raw_path": raw_path, "reason": cached_reason})
            continue
        path = Path(raw_path)
        candidates = [path]
        if not path.is_absolute():
            candidates.append(output_dir / raw_path)
        existing = next((candidate for candidate in candidates if candidate.is_file()), None)
        if existing is None:
            checked[cache_key] = "raw_path_missing"
            failed.append({"owner_id": owner_id, "raw_path": raw_path, "reason": "raw_path_missing"})
            continue
        if isinstance(expected_sha, str) and expected_sha:
            actual_sha = hashlib.sha256(existing.read_bytes()).hexdigest()
            if actual_sha != expected_sha:
                checked[cache_key] = "raw_sha256_mismatch"
                failed.append(
                    {
                        "owner_id": owner_id,
                        "raw_path": raw_path,
                        "reason": "raw_sha256_mismatch",
                    }
                )
                continue
        checked[cache_key] = None


def _lint_semantics(
    findings: list[dict[str, Any]],
    events: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    metadata_actor = [
        {
            "event_id": event.get("node_id"),
            "author_name": event.get("source_contributor", {}).get("author_name")
            if isinstance(event.get("source_contributor"), Mapping)
            else None,
        }
        for event in events
        if isinstance(event.get("source_contributor"), Mapping)
        and event.get("source_contributor", {}).get("author_name")
        in set(event.get("actor_labels", []))
    ]
    if metadata_actor:
        _add_failure(
            findings,
            "metadata_as_actor",
            "nodes_events.jsonl",
            "source contributor metadata appears in actor labels",
            "Contributor identity would be misrepresented as threat actor attribution.",
            failed_examples=metadata_actor[:10],
            next_step="Fix actor extraction to use OTX adversary/approved actor fields only.",
            likely_causes=["author_name was treated as actor", "metadata fields joined into labels"],
            do_not=["do not map source contributors to actor entities"],
        )

    reverse_edges = [
        {"edge_id": edge.get("edge_id"), "start_value": edge.get("start_value"), "end_value": edge.get("end_value")}
        for edge in edges
        if edge.get("type") == "ResolvesTo"
        and edge.get("start_label") == "IP"
        and edge.get("end_label") == "Domain"
    ]
    if reverse_edges:
        _add_failure(
            findings,
            "reverse_pdns_detected",
            "edges.jsonl",
            "reverse pDNS shaped IP-to-Domain edge detected",
            "Current policy explicitly excludes reverse pDNS from this OTX output.",
            failed_examples=reverse_edges[:10],
            next_step="Remove reverse pDNS projection and regenerate output from allowed sources.",
            likely_causes=["reverse pDNS enrichment was accidentally enabled"],
            do_not=["do not relabel reverse pDNS edges as forward resolution"],
        )

    unsupported_domain_resolves = [
        {"edge_id": edge.get("edge_id"), "source": edge.get("properties", {}).get("source")}
        for edge in edges
        if edge.get("type") == "ResolvesTo"
        and edge.get("start_label") == "Domain"
        and edge.get("end_label") == "IP"
        and (
            not isinstance(edge.get("properties"), Mapping)
            or edge.get("properties", {}).get("source") != "pdns"
        )
    ]
    if unsupported_domain_resolves:
        _add_failure(
            findings,
            "unsupported_domain_resolves_to",
            "edges.jsonl",
            "Domain-to-IP ResolvesTo edge lacks approved forward pDNS source",
            "Infrastructure edges would mix source-backed pDNS with unsupported inference.",
            failed_examples=unsupported_domain_resolves[:10],
            next_step="Emit Domain->IP only from local forward pDNS A/AAAA records.",
            likely_causes=["URL host parse or other source was projected as Domain->IP"],
            do_not=["do not infer Domain->IP from URL strings or NS/SOA/CNAME records"],
        )


def _add_failure(
    findings: list[dict[str, Any]],
    check_id: str,
    artifact: str,
    message: str,
    impact: str,
    *,
    failed_examples: list[Any],
    next_step: str,
    likely_causes: list[str],
    do_not: list[str],
) -> None:
    findings.append(
        {
            "check_id": check_id,
            "severity": "fail",
            "artifact": artifact,
            "message": message,
            "impact": impact,
            "failed_examples": failed_examples,
            "handle": {
                "next_step": next_step,
                "likely_causes": likely_causes,
                "do_not": do_not,
            },
        }
    )


def _add_report(
    findings: list[dict[str, Any]],
    check_id: str,
    message: str,
    details: dict[str, Any],
) -> None:
    findings.append(
        {
            "check_id": check_id,
            "severity": "report",
            "artifact": "projection package",
            "message": message,
            "impact": "Informational summary for delivery review.",
            "details": details,
            "handle": {
                "next_step": "No action required unless counts differ from delivery expectations.",
                "likely_causes": [],
                "do_not": ["do not treat this report as semantic correctness proof"],
            },
        }
    )



def load_otx_raw_observations(raw_otx_dir: Path) -> Iterable[_RawObservation]:
    """Yield flat and versioned RawStore OTX observations under ``raw_otx_dir``."""
    raw_otx_dir = Path(raw_otx_dir)
    paths = [path for path in raw_otx_dir.glob("*.json") if path.is_file()]
    paths.extend(path for path in raw_otx_dir.glob("*/*.json") if path.is_file())
    for path in sorted(paths):
        raw_bytes = path.read_bytes()
        value = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(value, Mapping):
            continue
        observation = _raw_observation(path, value, raw_bytes)
        if observation is not None:
            yield observation


def _select_otx_input_observations(
    *,
    raw_otx_dir: Path,
    otx_run_dir: Path | None,
    checkpoint_path: Path | None,
) -> _OTXInputSelection:
    if otx_run_dir is None and checkpoint_path is None:
        observations = list(load_otx_raw_observations(raw_otx_dir))
        return _OTXInputSelection(
            observations=observations,
            endpoint_pages_by_pulse={},
            completed_pulse_ids=tuple(sorted({observation.source_id for observation in observations})),
            input_metadata={"otx_input_policy": "raw_otx_dir_scan"},
            input_counts={},
        )

    run_dir = otx_run_dir
    if run_dir is None and checkpoint_path is not None:
        run_dir = checkpoint_path.parent
    if run_dir is None:
        raise ValueError("otx_run_dir or checkpoint_path is required for run-scoped input")
    checkpoint = checkpoint_path or run_dir / "checkpoint.json"
    saved_files_path = run_dir / "saved_files.jsonl"
    completed_pulses = _completed_pulse_details(checkpoint)
    pulse_detail_paths = _load_run_pulse_detail_paths(saved_files_path, set(completed_pulses), run_dir)
    endpoint_page_paths = _load_run_indicator_page_paths(
        saved_files_path,
        set(completed_pulses),
        run_dir,
    )

    observations: list[_RawObservation] = []
    failures: list[dict[str, str]] = []
    for pulse_id in completed_pulses:
        path = pulse_detail_paths.get(pulse_id)
        if path is None:
            failures.append({"pulse_id": pulse_id, "reason": "missing_saved_pulse_detail"})
            continue
        if not path.is_file():
            failures.append(
                {
                    "pulse_id": pulse_id,
                    "raw_path": path.as_posix(),
                    "reason": "raw_path_missing",
                }
            )
            continue
        observation = _raw_observation_from_path(path)
        if observation is None:
            failures.append(
                {
                    "pulse_id": pulse_id,
                    "raw_path": path.as_posix(),
                    "reason": "raw_observation_unreadable",
                }
            )
            continue
        if observation.source_id != pulse_id:
            failures.append(
                {
                    "pulse_id": pulse_id,
                    "raw_path": path.as_posix(),
                    "raw_source_id": observation.source_id,
                    "reason": "raw_source_id_mismatch",
                }
            )
            continue
        observations.append(observation)

    if failures:
        raise ValueError(
            "missing completed pulse detail files for run-scoped OTX projection: "
            + json.dumps(failures, sort_keys=True)
        )

    endpoint_pages_by_pulse: dict[str, list[_EndpointIndicatorPageObservation]] = defaultdict(list)
    endpoint_page_failures = 0
    for pulse_id, paths in endpoint_page_paths.items():
        for path in paths:
            observation = _endpoint_indicator_page_from_path(path, pulse_id)
            if observation is None:
                endpoint_page_failures += 1
                continue
            endpoint_pages_by_pulse[pulse_id].append(observation)

    return _OTXInputSelection(
        observations=observations,
        endpoint_pages_by_pulse={
            pulse_id: sorted(pages, key=lambda page: (page.fetched_at or "", page.raw_path))
            for pulse_id, pages in endpoint_pages_by_pulse.items()
        },
        completed_pulse_ids=tuple(completed_pulses),
        input_metadata={
            "otx_input_policy": "run_completed_pulse_details",
            "otx_run_dir": str(run_dir),
            "checkpoint_path": str(checkpoint),
            "saved_files_path": str(saved_files_path),
        },
        input_counts={
            "completed_pulse_details": len(completed_pulses),
            "resolved_pulse_detail_files": len(observations),
            "resolved_indicator_page_files": sum(len(paths) for paths in endpoint_page_paths.values())
            - endpoint_page_failures,
            "unreadable_indicator_page_files": endpoint_page_failures,
        },
    )


def _completed_pulse_details(checkpoint_path: Path) -> list[str]:
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    values = checkpoint.get("completed_pulse_details") if isinstance(checkpoint, Mapping) else None
    if not isinstance(values, list):
        raise ValueError(f"checkpoint completed_pulse_details must be a list: {checkpoint_path}")
    completed: list[str] = []
    seen: set[str] = set()
    for value in values:
        pulse_id = str(value).strip()
        if not pulse_id or pulse_id in seen:
            continue
        seen.add(pulse_id)
        completed.append(pulse_id)
    return completed


def _load_run_pulse_detail_paths(
    saved_files_path: Path,
    completed_pulses: set[str],
    run_dir: Path,
) -> dict[str, Path]:
    refs: dict[str, Path] = {}
    for row in _read_jsonl_rows(saved_files_path):
        if row.get("kind") != "pulse_detail":
            continue
        raw_ref = row.get("raw_ref")
        if not isinstance(raw_ref, Mapping):
            continue
        pulse_id = _text(row.get("pulse_id")) or _text(raw_ref.get("source_id"))
        if pulse_id not in completed_pulses:
            continue
        path_value = _text(raw_ref.get("path"))
        if not path_value:
            continue
        refs[pulse_id] = _resolve_saved_raw_path(path_value, run_dir)
    return refs


def _load_run_indicator_page_paths(
    saved_files_path: Path,
    completed_pulses: set[str],
    run_dir: Path,
) -> dict[str, list[Path]]:
    refs: dict[str, list[Path]] = defaultdict(list)
    for row in _read_jsonl_rows(saved_files_path):
        if row.get("kind") != "indicator_page":
            continue
        raw_ref = row.get("raw_ref")
        if not isinstance(raw_ref, Mapping):
            continue
        pulse_id = _text(row.get("pulse_id")) or _text(raw_ref.get("source_id"))
        if pulse_id not in completed_pulses:
            continue
        path_value = _text(raw_ref.get("path"))
        if not path_value:
            continue
        refs[pulse_id].append(_resolve_saved_raw_path(path_value, run_dir))
    return refs


def _read_jsonl_rows(path: Path) -> Iterable[Mapping[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, Mapping):
            yield value


def _resolve_saved_raw_path(path_value: str, run_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute() or path.is_file():
        return path
    run_relative = run_dir / path
    if run_relative.is_file():
        return run_relative
    return path


def _raw_observation_from_path(path: Path) -> _RawObservation | None:
    raw_bytes = path.read_bytes()
    value = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(value, Mapping):
        return None
    return _raw_observation(path, value, raw_bytes)


def _endpoint_indicator_page_from_path(
    path: Path,
    pulse_id: str,
) -> _EndpointIndicatorPageObservation | None:
    if not path.is_file():
        return None
    raw_bytes = path.read_bytes()
    value = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(value, Mapping):
        return None
    payload = value.get("payload")
    if not isinstance(payload, Mapping):
        payload = value
    source_id = _text(value.get("source_id")) or pulse_id
    if source_id != pulse_id:
        return None
    return _EndpointIndicatorPageObservation(
        pulse_id=pulse_id,
        raw_path=path.as_posix(),
        raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        fetched_at=_text(value.get("fetched_at")) or None,
        payload=payload,
    )


def _add_forward_pdns_projection(
    *,
    pdns_raw_dir: Path,
    nodes_by_id: dict[str, dict[str, Any]],
    edges_by_id: dict[str, dict[str, Any]],
) -> int:
    if not pdns_raw_dir.is_dir():
        return 0
    domain_values = {
        row["value"]
        for row in nodes_by_id.values()
        if row.get("node_kind") == "ioc" and row.get("labels") == ["Domain"]
    }
    projected = 0
    for observation in _load_latest_pdns_observations(pdns_raw_dir):
        domain = observation.domain.lower()
        if domain not in domain_values:
            continue
        domain_node = nodes_by_id[_ioc_node_id("Domain", domain)]
        raw_refs = [_pdns_raw_ref(observation)]
        for resolution in observation.record.get("resolutions", []):
            if not isinstance(resolution, Mapping):
                continue
            record_type = _text(resolution.get("record_type")).upper()
            ip_value = _text(resolution.get("ip")) or _text(resolution.get("value"))
            if record_type not in {"A", "AAAA"} or not _is_ip(ip_value):
                continue
            ip_value = _normalize_ioc_value(ip_value, "IP")
            ip_node = _ioc_row(
                "IP",
                ip_value,
                raw_refs,
                source="pdns",
                source_indicator_type="pdns_forward",
            )
            nodes_by_id.setdefault(ip_node["node_id"], ip_node)
            edge = _pdns_resolves_to_edge(domain_node, ip_node, resolution, raw_refs)
            edges_by_id[edge["edge_id"]] = edge
            projected += 1

            asn_value = _text(resolution.get("asn"))
            if asn_value:
                asn_node = _asn_node(asn_value, _text(resolution.get("asn_name")), raw_refs)
                nodes_by_id.setdefault(asn_node["node_id"], asn_node)
                asn_edge = _pdns_in_group_edge(ip_node, asn_node, resolution, raw_refs)
                edges_by_id[asn_edge["edge_id"]] = asn_edge
    return projected


def _load_latest_pdns_observations(pdns_raw_dir: Path) -> Iterable[_PDNSObservation]:
    for domain_dir in sorted(path for path in pdns_raw_dir.iterdir() if path.is_dir()):
        snapshots = sorted(domain_dir.glob("*.json"))
        if not snapshots:
            continue
        path = snapshots[-1]
        raw_bytes = path.read_bytes()
        raw = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(raw, dict):
            continue
        record = project_pdns_raw(raw)
        domain = _text(record.get("domain")).lower()
        if not domain:
            continue
        yield _PDNSObservation(
            domain=domain,
            raw_path=path.as_posix(),
            raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),
            fetched_at=_text(raw.get("fetched_at")) or None,
            record=record,
        )


def _raw_observation(
    path: Path,
    value: Mapping[str, Any],
    raw_bytes: bytes,
) -> _RawObservation | None:
    payload = value.get("payload")
    if isinstance(payload, Mapping) and value.get("source") == "otx":
        pulse = payload
        source_id = _text(value.get("source_id")) or _text(payload.get("id")) or path.parent.name
        return _RawObservation(
            source_id=source_id,
            fetched_at=_text(value.get("fetched_at")) or None,
            raw_path=path.as_posix(),
            raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),
            raw_layout="rawstore",
            pulse=pulse,
        )
    source_id = _text(value.get("id")) or path.stem
    return _RawObservation(
        source_id=source_id,
        fetched_at=None,
        raw_path=path.as_posix(),
        raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        raw_layout="flat",
        pulse=value,
    )


def _load_mitre_actor_taxonomy(mitre_attack_path: Path | None) -> _MitreActorTaxonomy:
    path = (
        Path(mitre_attack_path)
        if mitre_attack_path is not None
        else Path("data/raw/mitre/enterprise-attack.json")
    )
    if not path.is_file():
        return _MitreActorTaxonomy(
            taxonomy="mitre-attack-enterprise",
            taxonomy_version=None,
            actors_by_id={},
            matches_by_label={},
        )
    bundle = json.loads(path.read_text(encoding="utf-8"))
    objects = bundle.get("objects") if isinstance(bundle, Mapping) else None
    if not isinstance(objects, list):
        objects = []
    taxonomy_version = _mitre_taxonomy_version(bundle, objects)
    actors_by_id: dict[str, _MitreActor] = {}
    matches_by_label: dict[str, dict[str, _MitreActorMatch]] = defaultdict(dict)
    for raw in objects:
        if not isinstance(raw, Mapping) or raw.get("type") != "intrusion-set":
            continue
        actor = _mitre_actor_from_object(raw)
        if actor is None:
            continue
        actors_by_id[actor.actor_id] = actor
        for label, method in _mitre_actor_match_labels(actor):
            matches_by_label[label].setdefault(
                actor.actor_id,
                _MitreActorMatch(actor=actor, matched_label=label, match_method=method),
            )
    return _MitreActorTaxonomy(
        taxonomy="mitre-attack-enterprise",
        taxonomy_version=taxonomy_version,
        actors_by_id=actors_by_id,
        matches_by_label={
            label: tuple(sorted(matches.values(), key=lambda match: match.actor.actor_id))
            for label, matches in matches_by_label.items()
        },
    )


def _mitre_actor_from_object(raw: Mapping[str, Any]) -> _MitreActor | None:
    stix_id = _text(raw.get("id"))
    name = _normalize_actor_label(_text(raw.get("name")))
    if not stix_id or not name:
        return None
    taxonomy_id = _mitre_attack_id(raw) or None
    actor_id = f"actor_{taxonomy_id}" if taxonomy_id else contract_id("mitre_actor", (stix_id,))
    return _MitreActor(
        actor_id=actor_id,
        actor_name=name,
        taxonomy_id=taxonomy_id,
        stix_id=stix_id,
        aliases=tuple(_mitre_aliases(raw, name)),
        taxonomy_ref=_mitre_attack_url(raw),
        modified=_text(raw.get("modified")) or None,
        revoked=bool(raw.get("revoked", False)),
        deprecated=bool(raw.get("x_mitre_deprecated", False)),
    )


def _mitre_actor_match_labels(actor: _MitreActor) -> Iterable[tuple[str, str]]:
    yield actor.actor_name, "mitre_exact_name"
    for alias in actor.aliases:
        yield alias, "mitre_exact_alias"


def _mitre_attack_id(raw: Mapping[str, Any]) -> str:
    for ref in _mapping_list(raw.get("external_references")):
        if ref.get("source_name") == "mitre-attack":
            return _text(ref.get("external_id"))
    return ""


def _mitre_attack_url(raw: Mapping[str, Any]) -> str | None:
    for ref in _mapping_list(raw.get("external_references")):
        if ref.get("source_name") == "mitre-attack":
            return _text(ref.get("url")) or None
    return None


def _mitre_aliases(raw: Mapping[str, Any], name: str) -> list[str]:
    aliases: list[str] = []
    for value in _strings(raw.get("aliases")) + _strings(raw.get("x_mitre_aliases")):
        alias = _normalize_actor_label(value)
        if alias and alias != name and alias not in aliases:
            aliases.append(alias)
    return aliases


def _mitre_taxonomy_version(bundle: Mapping[str, Any], objects: list[Any]) -> str | None:
    for key in ("x_mitre_version", "spec_version", "modified"):
        value = _text(bundle.get(key))
        if value:
            return value
    for raw in objects:
        if not isinstance(raw, Mapping) or raw.get("type") != "x-mitre-collection":
            continue
        for key in ("x_mitre_version", "modified"):
            value = _text(raw.get(key))
            if value:
                return value
    return None


def _resolve_actor_label_claims(
    claims: list[_ActorLabelClaim],
    actor_taxonomy: _MitreActorTaxonomy,
) -> list[_ResolvedActorLabelClaim]:
    return [_resolve_actor_label_claim(claim, actor_taxonomy) for claim in claims]


def _resolve_actor_label_claim(
    claim: _ActorLabelClaim,
    actor_taxonomy: _MitreActorTaxonomy,
) -> _ResolvedActorLabelClaim:
    if claim.parse_status in {"non_actor_value", "parse_ambiguous"}:
        return _resolved_claim(
            claim,
            resolution_status=claim.parse_status,
            actor_taxonomy=actor_taxonomy,
        )
    matches = actor_taxonomy.matches_by_label.get(claim.raw_label, ())
    if not matches:
        return _resolved_claim(
            claim,
            resolution_status="unmapped_actor_like",
            actor_taxonomy=actor_taxonomy,
        )
    if len(matches) > 1:
        return _resolved_claim(
            claim,
            resolution_status="ambiguous_taxonomy",
            actor_taxonomy=actor_taxonomy,
            candidate_actor_ids=tuple(match.actor.actor_id for match in matches),
            matched_taxonomy_labels=tuple(_unique(match.matched_label for match in matches)),
            match_method="mitre_exact_label",
        )
    match = matches[0]
    return _resolved_claim(
        claim,
        resolution_status="resolved",
        actor_taxonomy=actor_taxonomy,
        resolved_actor_ids=(match.actor.actor_id,),
        matched_taxonomy_labels=(match.matched_label,),
        match_method=match.match_method,
        contributes_to_attribution=True,
    )


def _resolved_claim(
    claim: _ActorLabelClaim,
    *,
    resolution_status: str,
    actor_taxonomy: _MitreActorTaxonomy,
    resolved_actor_ids: tuple[str, ...] = (),
    candidate_actor_ids: tuple[str, ...] = (),
    matched_taxonomy_labels: tuple[str, ...] = (),
    match_method: str | None = None,
    contributes_to_attribution: bool = False,
) -> _ResolvedActorLabelClaim:
    return _ResolvedActorLabelClaim(
        claim=claim,
        resolution_status=resolution_status,
        resolved_actor_ids=tuple(_unique(resolved_actor_ids)),
        candidate_actor_ids=tuple(_unique(candidate_actor_ids)),
        match_method=match_method,
        matched_taxonomy_labels=tuple(_unique(matched_taxonomy_labels)),
        resolution_taxonomy=actor_taxonomy.taxonomy,
        taxonomy_version=actor_taxonomy.taxonomy_version,
        contributes_to_attribution=contributes_to_attribution,
    )


def _resolved_actor_names(
    resolved_claims: list[_ResolvedActorLabelClaim],
    actor_taxonomy: _MitreActorTaxonomy,
) -> list[str]:
    actor_ids = _resolved_actor_ids_from_claims(resolved_claims)
    return [
        actor.actor_name
        for actor_id in actor_ids
        if (actor := actor_taxonomy.actors_by_id.get(actor_id)) is not None
    ]


def _resolved_actor_ids_from_claims(
    resolved_claims: list[_ResolvedActorLabelClaim],
) -> list[str]:
    actor_ids: list[str] = []
    seen: set[str] = set()
    for resolved in resolved_claims:
        for actor_id in resolved.resolved_actor_ids:
            if actor_id not in seen:
                seen.add(actor_id)
                actor_ids.append(actor_id)
    return actor_ids


def _event_row(
    source_id: str,
    observations: list[_RawObservation],
    actor_taxonomy: _MitreActorTaxonomy,
) -> dict[str, Any]:
    latest = observations[-1].pulse
    actor_label_claims = _parse_adversary_actor_claims(_text(latest.get("adversary")))
    resolved_claims = _resolve_actor_label_claims(actor_label_claims, actor_taxonomy)
    actor_labels = _resolved_actor_names(resolved_claims, actor_taxonomy)
    initial_labels = [claim.raw_label for claim in actor_label_claims]
    apt = actor_labels[0] if len(actor_labels) == 1 else None
    raw_refs = [_raw_ref(obs) for obs in observations]
    fetched_values = [ref["fetched_at"] for ref in raw_refs if ref["fetched_at"]]
    return {
        "node_id": _event_node_id(source_id),
        "node_kind": "event",
        "labels": ["Event"],
        "source": "otx",
        "source_record_id": source_id,
        "name": _text(latest.get("name")) or None,
        "description": _text(latest.get("description")) or None,
        "pulse_created": _text(latest.get("created")) or None,
        "pulse_modified": _text(latest.get("modified")) or None,
        "timestamp_basis": "source_modified" if _text(latest.get("modified")) else "published",
        "apt": apt,
        "actor_label_raw": _text(latest.get("adversary")) or None,
        "actor_labels": actor_labels,
        "initial_labels": initial_labels,
        "raw_observation_count": len(observations),
        "actor_label_status": _actor_label_status(resolved_claims),
        "source_contributor": {
            "author": _text(latest.get("author")) or None,
            "author_name": _text(latest.get("author_name")) or None,
        },
        "tlp": _text(latest.get("TLP")) or None,
        "references": _strings(latest.get("references")),
        "tags": _strings(latest.get("tags")),
        "raw_refs": raw_refs,
        "fetched_first": min(fetched_values) if fetched_values else None,
        "fetched_last": max(fetched_values) if fetched_values else None,
    }


def _actor_label_claim_rows(
    event: Mapping[str, Any],
    actor_taxonomy: _MitreActorTaxonomy,
) -> list[dict[str, Any]]:
    claims = _parse_adversary_actor_claims(_text(event.get("actor_label_raw")))
    resolved_claims = _resolve_actor_label_claims(claims, actor_taxonomy)
    rows: list[dict[str, Any]] = []
    for resolved in resolved_claims:
        claim = resolved.claim
        rows.append(
            {
                "claim_id": contract_id(
                    "otx_actor_label_claim",
                    (
                        event["node_id"],
                        "adversary",
                        claim.label_index,
                        claim.raw_label,
                        claim.parse_status,
                    ),
                ),
                "event_id": event["node_id"],
                "source_record_id": event["source_record_id"],
                "source": "otx",
                "source_field": "adversary",
                "raw_field_value": claim.raw_field_value,
                "raw_label": claim.raw_label,
                "normalized_label": claim.normalized_label,
                "label_index": claim.label_index,
                "parse_status": claim.parse_status,
                "resolution_status": resolved.resolution_status,
                "resolved_actor_ids": list(resolved.resolved_actor_ids),
                "candidate_actor_ids": list(resolved.candidate_actor_ids),
                "match_method": resolved.match_method,
                "matched_taxonomy_labels": list(resolved.matched_taxonomy_labels),
                "resolution_taxonomy": resolved.resolution_taxonomy,
                "taxonomy_version": resolved.taxonomy_version,
                "contributes_to_attribution": resolved.contributes_to_attribution,
                "raw_refs": event.get("raw_refs", []),
                "notes": list(claim.notes),
            }
        )
    return rows


def _actor_rows_from_claims(
    claim_rows: list[dict[str, Any]],
    actor_taxonomy: _MitreActorTaxonomy,
) -> Iterable[dict[str, Any]]:
    seen: set[str] = set()
    for claim in claim_rows:
        for actor_id in claim.get("resolved_actor_ids", []):
            if not isinstance(actor_id, str) or actor_id in seen:
                continue
            seen.add(actor_id)
            actor = actor_taxonomy.actors_by_id.get(actor_id)
            if actor is None:
                continue
            yield {
                "node_id": actor.actor_id,
                "node_kind": "actor",
                "labels": ["Actor"],
                "actor_id": actor.actor_id,
                "actor_name": actor.actor_name,
                "taxonomy": actor_taxonomy.taxonomy,
                "taxonomy_id": actor.taxonomy_id,
                "stix_id": actor.stix_id,
                "aliases": list(actor.aliases),
                "taxonomy_ref": actor.taxonomy_ref,
                "modified": actor.modified,
                "revoked": actor.revoked,
                "deprecated": actor.deprecated,
            }


def _attributed_to_edges(
    event: Mapping[str, Any],
    claim_rows: list[dict[str, Any]],
) -> Iterable[dict[str, Any]]:
    claims_by_actor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claim_rows:
        if not claim.get("contributes_to_attribution"):
            continue
        for actor_id in claim.get("resolved_actor_ids", []):
            if isinstance(actor_id, str):
                claims_by_actor[actor_id].append(claim)
    for actor_id, claims in sorted(claims_by_actor.items()):
        claim_ids = [claim["claim_id"] for claim in claims]
        raw_refs: list[dict[str, Any]] = []
        for claim in claims:
            raw_refs.extend(ref for ref in claim.get("raw_refs", []) if isinstance(ref, dict))
        yield {
            "edge_id": contract_id("otx_edge", (event["node_id"], "AttributedTo", actor_id, "adversary")),
            "type": "AttributedTo",
            "start_node_id": event["node_id"],
            "end_node_id": actor_id,
            "start_label": "Event",
            "end_label": "Actor",
            "start_value": event["source_record_id"],
            "end_value": actor_id,
            "properties": {
                "source": "otx",
                "source_field": "adversary",
                "attribution_kind": "direct_actor_attribution",
                "claim_ids": claim_ids,
                "raw_labels": [claim["raw_label"] for claim in claims],
                "resolution_taxonomy": _first_claim_value(claims, "resolution_taxonomy"),
                "resolver_policy_version": "mitre_exact_actor_resolver_v1",
                "raw_refs": _dedupe_raw_refs(raw_refs),
            },
        }


def _first_claim_value(claims: list[dict[str, Any]], field: str) -> Any:
    for claim in claims:
        value = claim.get(field)
        if value:
            return value
    return None


def _indicator_evidence(
    observations: list[_RawObservation],
    endpoint_pages: list[_EndpointIndicatorPageObservation] | None = None,
) -> Iterable[tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]]:
    evidence_by_key: dict[tuple[str, str | None, str | None, str | None], list[dict[str, Any]]] = (
        defaultdict(list)
    )
    indicator_by_key: dict[tuple[str, str | None, str | None, str | None], dict[str, Any]] = {}
    endpoint_matches_by_key = _endpoint_matches_by_key(endpoint_pages or [])
    for observation in observations:
        for indicator in _indicator_dicts(observation.pulse.get("indicators")):
            value = _text(indicator.get("indicator"))
            if not value:
                continue
            raw_type = _text(indicator.get("type")) or None
            canonical = canonical_indicator_type(raw_type) if raw_type else None
            created = _text(indicator.get("created")) or None
            key = (value, raw_type, canonical, created)
            indicator_by_key[key] = {
                "value": value,
                "raw_type": raw_type,
                "canonical_type": canonical,
                "created": created,
            }
            evidence_by_key[key].append(_raw_ref(observation))
    for key in sorted(indicator_by_key):
        indicator = indicator_by_key[key]
        endpoint_matches = _endpoint_matches_for_indicator(indicator, endpoint_matches_by_key)
        yield indicator, evidence_by_key[key], endpoint_matches


def _endpoint_matches_by_key(
    endpoint_pages: list[_EndpointIndicatorPageObservation],
) -> dict[tuple[str, str | None], list[dict[str, Any]]]:
    matches_by_key: dict[tuple[str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for page in endpoint_pages:
        raw_ref = _endpoint_raw_ref(page)
        for indicator in _endpoint_indicator_dicts(page.payload):
            value = _text(indicator.get("indicator"))
            if not value:
                continue
            raw_type = _text(indicator.get("type")) or None
            matches_by_key[(value, raw_type)].append(
                {
                    "indicator": dict(indicator),
                    "raw_ref": raw_ref,
                }
            )
    return {
        key: sorted(
            matches,
            key=lambda match: (
                _text(match["indicator"].get("created")),
                str(match["raw_ref"].get("raw_path")),
            ),
        )
        for key, matches in matches_by_key.items()
    }


def _endpoint_matches_for_indicator(
    indicator: Mapping[str, Any],
    endpoint_matches_by_key: dict[tuple[str, str | None], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    matches = endpoint_matches_by_key.get((str(indicator["value"]), indicator.get("raw_type")), [])
    created = _text(indicator.get("created")) or None
    if not created:
        return matches
    created_matches = [
        match
        for match in matches
        if (_text(match["indicator"].get("created")) or None) == created
    ]
    return created_matches or matches


def _endpoint_indicator_dicts(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for field in ("results", "indicators"):
        value = payload.get(field)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _endpoint_enrichment_properties(endpoint_matches: list[dict[str, Any]]) -> dict[str, Any]:
    raw_refs = [
        match["raw_ref"]
        for match in endpoint_matches
        if isinstance(match.get("raw_ref"), Mapping)
    ]
    indicators = [
        match["indicator"]
        for match in endpoint_matches
        if isinstance(match.get("indicator"), Mapping)
    ]
    properties: dict[str, Any] = {
        "endpoint_enriched": True,
        "endpoint_source": "otx_indicator_page",
        "endpoint_indicator_observation_count": len(endpoint_matches),
        "endpoint_raw_refs": _dedupe_raw_refs(raw_refs),
    }
    false_positive_values = [
        indicator["false_positive"]
        for indicator in indicators
        if isinstance(indicator.get("false_positive"), bool)
    ]
    slugs = [_text(indicator.get("slug")) for indicator in indicators if _text(indicator.get("slug"))]
    pulse_keys = [
        _text(indicator.get("pulse_key"))
        for indicator in indicators
        if _text(indicator.get("pulse_key"))
    ]
    properties["endpoint_indicator_false_positive"] = _single_or_list(false_positive_values)
    properties["endpoint_indicator_slug"] = _single_or_list(slugs)
    properties["endpoint_indicator_pulse_key"] = _single_or_list(pulse_keys)
    return properties


def _ioc_from_indicator(
    indicator: Mapping[str, Any],
    raw_refs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    canonical = indicator.get("canonical_type")
    label = _label_for_canonical_type(canonical)
    if label is None:
        return None
    value = _normalize_ioc_value(str(indicator["value"]), label)
    return _ioc_row(label, value, raw_refs, source_indicator_type=indicator.get("raw_type"))


def _ioc_row(
    label: str,
    value: str,
    raw_refs: list[dict[str, Any]],
    *,
    source: str = "otx",
    source_indicator_type: Any = None,
) -> dict[str, Any]:
    return {
        "node_id": _ioc_node_id(label, value),
        "node_kind": "ioc",
        "labels": [label],
        "value": value,
        "source": source,
        "source_indicator_type": source_indicator_type,
        "raw_refs": _dedupe_raw_refs(raw_refs),
    }


def _in_report_edge(
    event: Mapping[str, Any],
    ioc: Mapping[str, Any],
    indicator: Mapping[str, Any],
    raw_refs: list[dict[str, Any]],
    endpoint_matches: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    properties = {
        "source": "otx",
        "indicator_created": indicator.get("created"),
        "first_seen": indicator.get("created"),
        "last_seen": indicator.get("created"),
        "duration_days": None,
        "source_indicator_type": indicator.get("raw_type"),
        "raw_refs": _dedupe_raw_refs(raw_refs),
    }
    if endpoint_matches:
        properties.update(_endpoint_enrichment_properties(endpoint_matches))
    return {
        "edge_id": contract_id("otx_edge", (event["node_id"], "InReport", ioc["node_id"], indicator)),
        "type": "InReport",
        "start_node_id": event["node_id"],
        "end_node_id": ioc["node_id"],
        "start_label": "Event",
        "end_label": ioc["labels"][0],
        "start_value": event["source_record_id"],
        "end_value": ioc["value"],
        "properties": properties,
    }


def _url_host_projection(
    ioc: Mapping[str, Any],
    raw_refs: list[dict[str, Any]],
) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    if ioc["labels"] != ["URL"]:
        return
    parsed = urlparse(str(ioc["value"]) if "://" in str(ioc["value"]) else f"http://{ioc['value']}")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return
    if _is_ip(host):
        ip_value = _normalize_ioc_value(host, "IP")
        node = _ioc_row("IP", ip_value, raw_refs, source_indicator_type="url_host")
        yield node, _derived_edge(ioc, node, "ResolvesTo", raw_refs)
    else:
        node = _ioc_row("Domain", host, raw_refs, source_indicator_type="url_host")
        yield node, _derived_edge(ioc, node, "HostedOn", raw_refs)


def _derived_edge(
    start: Mapping[str, Any],
    end: Mapping[str, Any],
    edge_type: str,
    raw_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "edge_id": contract_id("otx_edge", (start["node_id"], edge_type, end["node_id"])),
        "type": edge_type,
        "start_node_id": start["node_id"],
        "end_node_id": end["node_id"],
        "start_label": start["labels"][0],
        "end_label": end["labels"][0],
        "start_value": start["value"],
        "end_value": end["value"],
        "properties": {
            "source": "otx",
            "derivation_method": "url_host_parse",
            "raw_refs": _dedupe_raw_refs(raw_refs),
        },
    }


def _pdns_resolves_to_edge(
    domain: Mapping[str, Any],
    ip: Mapping[str, Any],
    resolution: Mapping[str, Any],
    raw_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    first_seen = _text(resolution.get("first_seen")) or None
    last_seen = _text(resolution.get("last_seen")) or None
    return {
        "edge_id": contract_id(
            "otx_edge",
            (domain["node_id"], "ResolvesTo", ip["node_id"], "pdns", first_seen, last_seen),
        ),
        "type": "ResolvesTo",
        "start_node_id": domain["node_id"],
        "end_node_id": ip["node_id"],
        "start_label": "Domain",
        "end_label": "IP",
        "start_value": domain["value"],
        "end_value": ip["value"],
        "properties": {
            "source": "pdns",
            "record_type": _text(resolution.get("record_type")) or None,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "duration_days": _duration_days(first_seen, last_seen),
            "fetched_at": _first_raw_ref_value(raw_refs, "fetched_at"),
            "raw_refs": _dedupe_raw_refs(raw_refs),
        },
    }


def _pdns_in_group_edge(
    ip: Mapping[str, Any],
    asn: Mapping[str, Any],
    resolution: Mapping[str, Any],
    raw_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "edge_id": contract_id("otx_edge", (ip["node_id"], "InGroup", asn["node_id"], "pdns")),
        "type": "InGroup",
        "start_node_id": ip["node_id"],
        "end_node_id": asn["node_id"],
        "start_label": "IP",
        "end_label": "ASN",
        "start_value": ip["value"],
        "end_value": asn["value"],
        "properties": {
            "source": "pdns",
            "asn_name": _text(resolution.get("asn_name")) or None,
            "country": _text(resolution.get("country")) or None,
            "raw_refs": _dedupe_raw_refs(raw_refs),
        },
    }


def _asn_node(asn: str, asn_name: str, raw_refs: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = asn.strip().upper()
    return {
        "node_id": _ioc_node_id("ASN", normalized),
        "node_kind": "infrastructure",
        "labels": ["ASN"],
        "value": normalized,
        "name": asn_name or None,
        "source": "pdns",
        "source_indicator_type": "pdns_asn",
        "raw_refs": _dedupe_raw_refs(raw_refs),
    }


def _label_for_canonical_type(canonical: Any) -> str | None:
    if canonical == "domain":
        return "Domain"
    if canonical in {"ipv4", "ipv6"}:
        return "IP"
    if canonical == "url":
        return "URL"
    return None


def _normalize_ioc_value(value: str, label: str) -> str:
    stripped = value.strip()
    if label == "Domain":
        return stripped.lower()
    if label == "IP":
        try:
            return str(ipaddress.ip_address(stripped))
        except ValueError:
            return stripped
    return stripped


def _parse_adversary_actor_claims(raw_value: str) -> list[_ActorLabelClaim]:
    raw_field_value = _normalize_actor_label(raw_value)
    if not raw_field_value:
        return []
    if _is_obvious_non_actor_value(raw_field_value):
        return [
            _actor_label_claim(
                raw_field_value,
                raw_field_value,
                0,
                "non_actor_value",
                ("obvious non-actor adversary value preserved before splitting",),
            )
        ]

    labels = _split_actor_field(raw_field_value)
    claims: list[_ActorLabelClaim] = []
    for index, label in enumerate(labels):
        parse_status = "parsed"
        notes: tuple[str, ...] = ()
        if _is_ambiguous_slash_value(label):
            parse_status = "parse_ambiguous"
            notes = ("slash value is ambiguous and was not expanded",)
        elif _is_obvious_non_actor_value(label):
            parse_status = "non_actor_value"
            notes = ("non-actor label preserved after parsing",)
        claims.append(
            _actor_label_claim(
                raw_field_value,
                label,
                index,
                parse_status,
                notes,
            )
        )
    return claims


def _split_actor_field(raw_field_value: str) -> list[str]:
    base_parts = _split_top_level_separators(raw_field_value)
    labels: list[str] = []
    for part in base_parts:
        labels.extend(_split_top_level_and(part))

    slash_expanded: list[str] = []
    for label in labels:
        if _is_clean_slash_actor_pair(label):
            left, right = label.split("/", 1)
            slash_expanded.extend([_normalize_actor_label(left), _normalize_actor_label(right)])
        else:
            slash_expanded.append(label)
    return [label for label in slash_expanded if label]


def _split_top_level_separators(value: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(value):
        if char == "(":
            depth += 1
            continue
        if char == ")" and depth > 0:
            depth -= 1
            continue
        if depth == 0 and char in {",", "|", ";", "+"}:
            part = _normalize_actor_label(value[start:index])
            if part:
                parts.append(part)
            start = index + 1
    last = _normalize_actor_label(value[start:])
    if last:
        parts.append(last)
    return parts


def _split_top_level_and(value: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for match in _TOP_LEVEL_AND_RE.finditer(value):
        depth = _parentheses_depth_at(value, match.start())
        if depth != 0:
            continue
        left = _normalize_actor_label(value[start : match.start()])
        right = _normalize_actor_label(value[match.end() :])
        if left and right and _looks_like_actor_label(left) and _looks_like_actor_label(right):
            parts.append(left)
            start = match.end()
    if parts:
        last = _normalize_actor_label(value[start:])
        if last:
            parts.append(last)
        return parts
    return [value]


def _parentheses_depth_at(value: str, target: int) -> int:
    depth = 0
    for char in value[:target]:
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
    return depth


def _actor_label_status(claims: list[_ResolvedActorLabelClaim]) -> str:
    if not claims:
        return "missing"
    actor_ids = _resolved_actor_ids_from_claims(claims)
    if len(actor_ids) == 1:
        resolved_claim_count = sum(1 for claim in claims if claim.resolved_actor_ids)
        return "resolved_alias_collapsed" if resolved_claim_count > 1 else "resolved_single"
    if len(actor_ids) > 1:
        return "resolved_multi_actor"
    statuses = {claim.resolution_status for claim in claims}
    if "ambiguous_taxonomy" in statuses:
        return "ambiguous_taxonomy"
    if "unmapped_actor_like" in statuses:
        return "unmapped_actor_like"
    if "parse_ambiguous" in statuses:
        return "parse_ambiguous"
    if "non_actor_value" in statuses:
        return "non_attributing"
    return "non_attributing"


def _actor_label_claim(
    raw_field_value: str,
    raw_label: str,
    label_index: int,
    parse_status: str,
    notes: tuple[str, ...] = (),
) -> _ActorLabelClaim:
    return _ActorLabelClaim(
        raw_field_value=raw_field_value,
        raw_label=_normalize_actor_label(raw_label),
        normalized_label=_normalize_actor_label(raw_label).lower(),
        label_index=label_index,
        parse_status=parse_status,
        notes=notes,
    )


def _normalize_actor_label(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip())


def _is_obvious_non_actor_value(value: str) -> bool:
    normalized = _normalize_actor_label(value)
    lowered = normalized.lower()
    if lowered in _NON_ACTOR_VALUES:
        return True
    if _is_url_like(normalized):
        return True
    return bool(_ORG_MARKERS_RE.search(normalized))


def _is_url_like(value: str) -> bool:
    lowered = value.lower()
    if "://" in lowered or lowered.startswith(("www.", "http:", "https:")):
        return True
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _is_clean_slash_actor_pair(value: str) -> bool:
    if value.count("/") != 1 or _is_url_like(value):
        return False
    left, right = (_normalize_actor_label(part) for part in value.split("/", 1))
    if not left or not right:
        return False
    if " " in left or " " in right:
        return False
    return _looks_like_actor_label(left) and _looks_like_actor_label(right)


def _is_ambiguous_slash_value(value: str) -> bool:
    return "/" in value and not _is_clean_slash_actor_pair(value)


def _looks_like_actor_label(value: str) -> bool:
    normalized = _normalize_actor_label(value)
    if not normalized or _is_obvious_non_actor_value(normalized):
        return False
    if len(normalized) > 80:
        return False
    return bool(_ACTOR_TOKEN_RE.match(normalized))


def _raw_ref(observation: _RawObservation) -> dict[str, Any]:
    return {
        "raw_path": observation.raw_path,
        "raw_sha256": observation.raw_sha256,
        "raw_layout": observation.raw_layout,
        "fetched_at": observation.fetched_at,
    }


def _endpoint_raw_ref(observation: _EndpointIndicatorPageObservation) -> dict[str, Any]:
    return {
        "raw_path": observation.raw_path,
        "raw_sha256": observation.raw_sha256,
        "raw_layout": "rawstore",
        "fetched_at": observation.fetched_at,
        "connector_source": "otx_indicator_page",
    }


def _pdns_raw_ref(observation: _PDNSObservation) -> dict[str, Any]:
    return {
        "raw_path": observation.raw_path,
        "raw_sha256": observation.raw_sha256,
        "raw_layout": "rawstore",
        "fetched_at": observation.fetched_at,
        "connector_source": "pdns",
    }


def _dedupe_raw_refs(raw_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in sorted(
            {json.dumps(ref, sort_keys=True): ref for ref in raw_refs}.values(),
            key=lambda ref: (str(ref.get("raw_layout")), str(ref.get("raw_path"))),
        )
    ]


def _first_raw_ref_value(raw_refs: list[dict[str, Any]], key: str) -> Any:
    for raw_ref in raw_refs:
        value = raw_ref.get(key)
        if value:
            return value
    return None


def _single_or_list(values: Iterable[Any]) -> Any:
    unique_values: list[Any] = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    if len(unique_values) == 1:
        return unique_values[0]
    return unique_values


def _observation_sort_key(observation: _RawObservation) -> tuple[str, str, str]:
    return (observation.fetched_at or "", observation.raw_layout, observation.raw_path)


def _event_node_id(source_id: str) -> str:
    return f"otx:pulse:{source_id}"


def _ioc_node_id(label: str, value: str) -> str:
    return contract_id("otx_ioc", (label, value))


def _indicator_dicts(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _unique(values: Iterable[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _duration_days(first_seen: str | None, last_seen: str | None) -> int | None:
    first = _parse_datetime(first_seen)
    last = _parse_datetime(last_seen)
    if first is None or last is None or last < first:
        return None
    return (last - first).days


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _row_field_coverage(
    rows: list[dict[str, Any]],
    field: str,
    *,
    source: str,
    source_field: str,
) -> dict[str, Any]:
    present = sum(1 for row in rows if _has_value(row.get(field)))
    return {
        "total": len(rows),
        "present": present,
        "missing": len(rows) - present,
        "coverage_ratio": _coverage_ratio(present, len(rows)),
        "source": source,
        "source_field": source_field,
    }


def _edge_property_coverage(
    edges: list[dict[str, Any]],
    property_name: str,
    *,
    source: str,
    source_field: str,
) -> dict[str, Any]:
    present = _edge_property_present(edges, property_name)
    return {
        "total": len(edges),
        "present": present,
        "missing": len(edges) - present,
        "coverage_ratio": _coverage_ratio(present, len(edges)),
        "source": source,
        "source_field": source_field,
    }


def _edge_property_present(edges: list[dict[str, Any]], property_name: str) -> int:
    return sum(
        1
        for edge in edges
        if isinstance(edge.get("properties"), Mapping)
        and _has_value(edge["properties"].get(property_name))
    )


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _coverage_ratio(present: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(present / total, 6)
