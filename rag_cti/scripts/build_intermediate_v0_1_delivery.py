"""Build and audit the sampled intermediate v0.1 delivery package.

This is a delivery/audit runner only. It samples real ``data/raw`` inputs,
delegates conversion to the intermediate source exporters, and writes a README
plus acceptance audit beside the generated package.
"""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.intermediate.delivery import build_intermediate_delivery_package
from rag_cti.intermediate.validation import validate_delivery

DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_OUTPUT_DIR = Path("data/deliveries/intermediate_v0_1_2026-06-28")
DEFAULT_DATASET_ID = "cti_rag_intermediate_v0_1"
DEFAULT_DATASET_VERSION = "2026-06-28-sampled"
GENERATED_AT = "2026-06-28T00:00:00Z"
FALLBACK_FETCHED_AT = "2026-06-28T00:00:00Z"
JSONL_ARTIFACTS = {
    "intermediate_records": "intermediate_records.jsonl",
    "entity_mentions": "entity_mentions.jsonl",
    "relation_mentions": "relation_mentions.jsonl",
    "attribution_signals": "attribution_signals.jsonl",
    "record_features": "record_features.jsonl",
}
JSON_ARTIFACTS = {
    "source_manifest": "source_manifest.json",
    "processing_report": "processing_report.json",
}
ID_FIELDS = {
    "intermediate_records": "record_id",
    "entity_mentions": "entity_mention_id",
    "relation_mentions": "relation_mention_id",
    "attribution_signals": "attribution_signal_id",
    "record_features": "record_id",
}
CONFIRMED_RELATIONS = {"related-to", "observed-with"}
SUPPORTED_INFRA_DNS_TYPES = {"A", "NS"}
PDNS_TARGET_DNS_TYPES = {"A", "NS", "AAAA", "CNAME", "SOA"}
VT_TARGET_DNS_TYPES = {"A", "NS", "AAAA", "CNAME", "SOA", "MX", "TXT"}
SUPPORTED_MITRE_TYPES = {
    "attack-pattern",
    "campaign",
    "course-of-action",
    "intrusion-set",
    "malware",
    "relationship",
    "tool",
    "x-mitre-detection-strategy",
    "x-mitre-tactic",
}


@dataclass(frozen=True)
class LoadedSources:
    otx_pulses: list[dict[str, Any]]
    mitre_objects: list[dict[str, Any]]
    pdns_records: list[dict[str, Any]]
    vt_records: list[dict[str, Any]]
    sample_metadata: dict[str, Any]


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "details": self.details}


def build_delivery(
    *,
    raw_dir: Path,
    output_dir: Path,
    overwrite: bool,
    otx_limit: int,
    pdns_limit: int,
    vt_limit: int,
    mitre_full: bool,
) -> dict[str, Any]:
    """Build the delivery package and return the final audit payload."""
    raw_dir = Path(raw_dir)
    output_dir = Path(output_dir)
    _prepare_output_dir(output_dir, overwrite=overwrite)
    loaded = load_real_raw_samples(
        raw_dir,
        otx_limit=otx_limit,
        pdns_limit=pdns_limit,
        vt_limit=vt_limit,
        mitre_full=mitre_full,
    )

    build_intermediate_delivery_package(
        output_dir=output_dir,
        dataset_id=DEFAULT_DATASET_ID,
        dataset_version=DEFAULT_DATASET_VERSION,
        generated_at=GENERATED_AT,
        fetched_at=FALLBACK_FETCHED_AT,
        otx_pulses=loaded.otx_pulses,
        mitre_objects=loaded.mitre_objects,
        pdns_records=loaded.pdns_records,
        vt_records=loaded.vt_records,
    )

    artifacts = _load_delivery_artifacts(output_dir)
    _write_readme(output_dir, artifacts, loaded.sample_metadata, audit_status="pending")
    audit = run_acceptance_audit(output_dir, sample_metadata=loaded.sample_metadata)
    _write_json(output_dir / "acceptance_audit.json", audit)
    final_audit = run_acceptance_audit(output_dir, sample_metadata=loaded.sample_metadata)
    _write_json(output_dir / "acceptance_audit.json", final_audit)
    _write_readme(
        output_dir,
        artifacts,
        loaded.sample_metadata,
        audit_status="passed" if final_audit["ok"] else "failed",
    )
    return final_audit


def load_real_raw_samples(
    raw_dir: Path,
    *,
    otx_limit: int,
    pdns_limit: int,
    vt_limit: int,
    mitre_full: bool,
) -> LoadedSources:
    """Load deterministic source slices from the local real raw directory."""
    raw_dir = Path(raw_dir)
    otx_paths = _sample_otx_paths(raw_dir / "otx", otx_limit)
    pdns_paths = _sample_dns_wrapper_paths(
        raw_dir / "pdns",
        pdns_limit,
        target_types=PDNS_TARGET_DNS_TYPES,
        dns_path=("payload", "passive_dns"),
        type_key="record_type",
    )
    vt_paths = _sample_dns_wrapper_paths(
        raw_dir / "vt",
        vt_limit,
        target_types=VT_TARGET_DNS_TYPES,
        dns_path=("payload", "data", "attributes", "last_dns_records"),
        type_key="type",
    )
    mitre_path, mitre_objects = _load_mitre_objects(raw_dir / "mitre", full=mitre_full)

    otx_pulses = [_read_json(path) for path in otx_paths]
    pdns_records = [_read_json(path) for path in pdns_paths]
    vt_records = [_read_json(path) for path in vt_paths]

    sample_metadata = {
        "package_scope": {
            "otx": "sampled",
            "mitre": "full_supported_bundle" if mitre_full else "sampled_bundle",
            "pdns": "sampled",
            "vt": "sampled",
        },
        "raw_inputs": {
            "otx": [path.as_posix() for path in otx_paths],
            "mitre": mitre_path.as_posix(),
            "pdns": [path.as_posix() for path in pdns_paths],
            "vt": [path.as_posix() for path in vt_paths],
        },
        "requested_sample_counts": {
            "otx": otx_limit,
            "pdns": pdns_limit,
            "vt": vt_limit,
            "mitre_full": mitre_full,
        },
        "loaded_source_counts": {
            "otx": len(otx_pulses),
            "mitre_objects": len(mitre_objects),
            "pdns": len(pdns_records),
            "vt": len(vt_records),
        },
        "raw_dns_type_coverage": {
            "pdns": dict(_dns_type_counter(pdns_records, ("payload", "passive_dns"), "record_type")),
            "vt": dict(
                _dns_type_counter(
                    vt_records,
                    ("payload", "data", "attributes", "last_dns_records"),
                    "type",
                )
            ),
        },
        "sampling_notes": _sampling_notes(
            raw_dir,
            otx_limit=otx_limit,
            pdns_limit=pdns_limit,
            vt_limit=vt_limit,
            actual_otx=len(otx_pulses),
            actual_pdns=len(pdns_records),
            actual_vt=len(vt_records),
        ),
    }
    return LoadedSources(otx_pulses, mitre_objects, pdns_records, vt_records, sample_metadata)


def run_acceptance_audit(delivery_dir: Path, *, sample_metadata: dict[str, Any]) -> dict[str, Any]:
    """Run final acceptance checks over a built intermediate delivery package."""
    delivery_dir = Path(delivery_dir)
    artifacts = _load_delivery_artifacts(delivery_dir)
    checks = [
        _check_validate_delivery(delivery_dir),
        _check_all_json_parse(delivery_dir),
        _check_raw_refs(delivery_dir, artifacts),
        _check_duplicate_ids(artifacts),
        _check_relation_endpoint_joins(artifacts),
        _check_attribution_record_joins(artifacts),
        _check_manifest_counts(artifacts),
        _check_processing_report_counts(artifacts),
        _check_infrastructure_sources_have_no_attribution(artifacts),
        _check_otx_is_weak_cue(artifacts),
        _check_mitre_attribution_boundary(artifacts),
        _check_no_unconfirmed_relations(artifacts),
        _check_unsupported_dns_types_are_deferred(artifacts),
        _check_raw_payload_preserved(delivery_dir, artifacts),
        _check_readme_exists(delivery_dir),
    ]
    counts = {
        name: len(rows)
        for name, rows in artifacts["jsonl"].items()
        if name in JSONL_ARTIFACTS
    }
    sources = {
        source["connector_source"]: source["record_count"]
        for source in artifacts["json"]["source_manifest"].get("sources", [])
        if isinstance(source, dict)
    }
    validation = validate_delivery(delivery_dir)
    return {
        "audit_id": "intermediate_v0_1_acceptance_2026-06-28",
        "generated_at": GENERATED_AT,
        "delivery_dir": delivery_dir.as_posix(),
        "ok": all(check.ok for check in checks),
        "package_scope": sample_metadata["package_scope"],
        "sample_metadata": sample_metadata,
        "source_record_counts": dict(sorted(sources.items())),
        "artifact_row_counts": counts,
        "validation": {
            "ok": validation.ok,
            "failures": [message.__dict__ for message in validation.failures],
            "warnings": [message.__dict__ for message in validation.warnings],
            "reports": [message.__dict__ for message in validation.reports],
        },
        "checks": [check.to_dict() for check in checks],
        "deferred": [
            "PDF richer extraction deferred.",
            "WHOIS deferred because no local data/raw/whois directory is present.",
            "Temporal split deferred.",
            "Confidence/source reliability deferred.",
            "Production RAG/GNN/Neo4j export deferred.",
            "Cross-source entity resolution deferred.",
        ],
    }


def _sample_otx_paths(raw_dir: Path, limit: int) -> list[Path]:
    paths = sorted(path for path in raw_dir.glob("*.json") if path.is_file())
    scored: list[tuple[tuple[int, int, int, str], Path]] = []
    for path in paths:
        raw = _read_json(path)
        indicator_count = len(raw.get("indicators") if isinstance(raw.get("indicators"), list) else [])
        score = (
            0 if _text(raw.get("adversary")) else 1,
            0 if indicator_count else 1,
            abs(indicator_count - 25),
            path.as_posix(),
        )
        scored.append((score, path))
    return [path for _, path in sorted(scored)[:limit]]


def _sample_dns_wrapper_paths(
    raw_dir: Path,
    limit: int,
    *,
    target_types: set[str],
    dns_path: tuple[str, ...],
    type_key: str,
) -> list[Path]:
    candidates: list[tuple[tuple[int, int, int, str], Path]] = []
    for path in sorted(raw_dir.glob("*/*.json")):
        raw = _read_json(path)
        counts = _dns_type_counter([raw], dns_path, type_key)
        covered = set(counts) & target_types
        if not covered:
            continue
        score = (-len(covered), -sum(counts.values()), 0 if "A" in counts and "NS" in counts else 1, path.as_posix())
        candidates.append((score, path))

    selected: list[Path] = []
    covered_types: set[str] = set()
    for _, path in sorted(candidates):
        if len(selected) >= limit:
            break
        counts = _dns_type_counter([_read_json(path)], dns_path, type_key)
        new_types = (set(counts) & target_types) - covered_types
        if new_types or len(selected) < min(limit, len(target_types)):
            selected.append(path)
            covered_types.update(set(counts) & target_types)
    for _, path in sorted(candidates):
        if len(selected) >= limit:
            break
        if path not in selected:
            selected.append(path)
    return selected


def _load_mitre_objects(raw_dir: Path, *, full: bool) -> tuple[Path, list[dict[str, Any]]]:
    wrapper_paths = sorted((raw_dir / "enterprise-attack").glob("*.json"))
    path = wrapper_paths[-1] if wrapper_paths else raw_dir / "enterprise-attack.json"
    raw = _read_json(path)
    bundle = raw.get("payload") if isinstance(raw.get("payload"), dict) else raw
    objects = [obj for obj in bundle.get("objects", []) if isinstance(obj, dict)]
    if full:
        return path, objects

    object_rows = [obj for obj in objects if obj.get("type") in SUPPORTED_MITRE_TYPES]
    rel_rows = [
        obj
        for obj in objects
        if obj.get("type") == "relationship"
        and obj.get("relationship_type") in {"uses", "attributed-to", "mitigates", "detects"}
    ]
    needed_refs = {
        ref
        for rel in rel_rows[:50]
        for ref in (rel.get("source_ref"), rel.get("target_ref"))
        if isinstance(ref, str)
    }
    endpoints = [obj for obj in object_rows if obj.get("id") in needed_refs]
    sampled = endpoints + rel_rows[:50]
    return path, sampled


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    if not output_dir.exists():
        return
    if not overwrite:
        raise SystemExit(f"output directory already exists; pass --overwrite: {output_dir}")
    resolved = output_dir.resolve()
    deliveries_root = (Path.cwd() / "data" / "deliveries").resolve()
    if deliveries_root not in resolved.parents:
        raise SystemExit(f"refusing to delete output outside data/deliveries: {output_dir}")
    if not output_dir.name.startswith("intermediate_v0_1_"):
        raise SystemExit(f"refusing to delete unexpected delivery dir: {output_dir}")
    shutil.rmtree(output_dir)


def _load_delivery_artifacts(delivery_dir: Path) -> dict[str, dict[str, Any]]:
    intermediate_dir = delivery_dir / "intermediate"
    json_artifacts = {
        artifact: _read_json(intermediate_dir / filename)
        for artifact, filename in JSON_ARTIFACTS.items()
    }
    jsonl_artifacts = {
        artifact: _read_jsonl(intermediate_dir / filename)
        for artifact, filename in JSONL_ARTIFACTS.items()
    }
    return {"json": json_artifacts, "jsonl": jsonl_artifacts}


def _check_validate_delivery(delivery_dir: Path) -> CheckResult:
    validation = validate_delivery(delivery_dir)
    return CheckResult(
        "validate_delivery",
        validation.ok,
        {
            "failure_count": len(validation.failures),
            "warning_count": len(validation.warnings),
            "failures": [message.__dict__ for message in validation.failures],
        },
    )


def _check_all_json_parse(delivery_dir: Path) -> CheckResult:
    failures: list[str] = []
    for path in sorted(delivery_dir.rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{path.as_posix()}: {exc}")
    for path in sorted(delivery_dir.rglob("*.jsonl")):
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                failures.append(f"{path.as_posix()}:{index}: {exc}")
    return CheckResult("json_and_jsonl_parse", not failures, {"failures": failures})


def _check_raw_refs(delivery_dir: Path, artifacts: dict[str, dict[str, Any]]) -> CheckResult:
    failures: list[str] = []
    for record in artifacts["jsonl"]["intermediate_records"]:
        raw_ref = record.get("raw_ref") if isinstance(record.get("raw_ref"), dict) else {}
        raw_path = delivery_dir / str(raw_ref.get("raw_path", ""))
        expected = raw_ref.get("raw_sha256")
        if not raw_path.is_file():
            failures.append(f"{record.get('record_id')}: raw missing {raw_path}")
            continue
        actual = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        if actual != expected:
            failures.append(f"{record.get('record_id')}: raw sha mismatch")
    return CheckResult("raw_refs_exist_and_hash_match", not failures, {"failures": failures})


def _check_duplicate_ids(artifacts: dict[str, dict[str, Any]]) -> CheckResult:
    failures: list[str] = []
    for artifact, id_field in ID_FIELDS.items():
        seen: set[str] = set()
        for row in artifacts["jsonl"][artifact]:
            value = str(row.get(id_field))
            if value in seen:
                failures.append(f"{artifact}.{id_field}: {value}")
            seen.add(value)
    return CheckResult("duplicate_ids", not failures, {"duplicates": failures})


def _check_relation_endpoint_joins(artifacts: dict[str, dict[str, Any]]) -> CheckResult:
    mention_ids = {
        row["entity_mention_id"] for row in artifacts["jsonl"]["entity_mentions"]
    }
    failures: list[str] = []
    for relation in artifacts["jsonl"]["relation_mentions"]:
        for side in ("subject", "object"):
            mention_id = relation[side]["entity_mention_id"]
            if mention_id not in mention_ids:
                failures.append(f"{relation['relation_mention_id']} {side}={mention_id}")
    return CheckResult("relation_endpoints_join_entity_mentions", not failures, {"failures": failures})


def _check_attribution_record_joins(artifacts: dict[str, dict[str, Any]]) -> CheckResult:
    record_ids = {row["record_id"] for row in artifacts["jsonl"]["intermediate_records"]}
    failures = [
        row["attribution_signal_id"]
        for row in artifacts["jsonl"]["attribution_signals"]
        if row["record_id"] not in record_ids
    ]
    return CheckResult("attribution_signals_join_records", not failures, {"failures": failures})


def _check_manifest_counts(artifacts: dict[str, dict[str, Any]]) -> CheckResult:
    actual = Counter(
        row["source"]["connector_source"] for row in artifacts["jsonl"]["intermediate_records"]
    )
    manifest = {
        row["connector_source"]: row["record_count"]
        for row in artifacts["json"]["source_manifest"].get("sources", [])
    }
    return CheckResult(
        "manifest_source_counts_match_records",
        dict(actual) == manifest,
        {"actual": dict(sorted(actual.items())), "manifest": dict(sorted(manifest.items()))},
    )


def _check_processing_report_counts(artifacts: dict[str, dict[str, Any]]) -> CheckResult:
    actual = {
        "intermediate_records": len(artifacts["jsonl"]["intermediate_records"]),
        "entity_mentions": len(artifacts["jsonl"]["entity_mentions"]),
        "relation_mentions": len(artifacts["jsonl"]["relation_mentions"]),
        "attribution_signals": len(artifacts["jsonl"]["attribution_signals"]),
    }
    report_counts = artifacts["json"]["processing_report"].get("counts", {})
    expected = {key: report_counts.get(key) for key in actual}
    return CheckResult(
        "processing_report_counts_match_jsonl",
        actual == expected,
        {"actual": actual, "processing_report": expected},
    )


def _check_infrastructure_sources_have_no_attribution(
    artifacts: dict[str, dict[str, Any]]
) -> CheckResult:
    records = {
        row["record_id"]: row["source"]["connector_source"]
        for row in artifacts["jsonl"]["intermediate_records"]
    }
    offenders = [
        row["attribution_signal_id"]
        for row in artifacts["jsonl"]["attribution_signals"]
        if records.get(row["record_id"]) in {"pdns", "vt"}
    ]
    return CheckResult("pdns_vt_no_attribution_signals", not offenders, {"offenders": offenders})


def _check_otx_is_weak_cue(artifacts: dict[str, dict[str, Any]]) -> CheckResult:
    records = {
        row["record_id"]: row["source"]["connector_source"]
        for row in artifacts["jsonl"]["intermediate_records"]
    }
    otx_signals = [
        row
        for row in artifacts["jsonl"]["attribution_signals"]
        if records.get(row["record_id"]) == "otx"
    ]
    bad = [
        row["attribution_signal_id"]
        for row in otx_signals
        if row.get("signal_type") != "weak_direct_attribution"
    ]
    ground_truth_claims = [
        row["attribution_signal_id"]
        for row in otx_signals
        if "ground truth" in json.dumps(row).lower()
        and "not ground truth" not in json.dumps(row).lower()
    ]
    return CheckResult(
        "otx_attribution_is_weak_cue_not_ground_truth",
        not bad and not ground_truth_claims,
        {
            "otx_signal_count": len(otx_signals),
            "bad_signal_types": bad,
            "ground_truth_claims": ground_truth_claims,
        },
    )


def _check_mitre_attribution_boundary(artifacts: dict[str, dict[str, Any]]) -> CheckResult:
    records = {
        row["record_id"]: row["source"]["connector_source"]
        for row in artifacts["jsonl"]["intermediate_records"]
    }
    bad_direct_relations: list[str] = []
    bad_non_direct_relations: list[str] = []
    for relation in artifacts["jsonl"]["relation_mentions"]:
        if records.get(relation["record_id"]) != "mitre":
            continue
        predicate = relation["predicate"]["mapped_value"]
        label = relation["derivation"].get("label_availability")
        if label == "direct" and predicate != "attributed-to":
            bad_direct_relations.append(relation["relation_mention_id"])
        if predicate in {"uses", "mitigates", "detects"} and label != "none":
            bad_non_direct_relations.append(relation["relation_mention_id"])

    mitre_signals = [
        row
        for row in artifacts["jsonl"]["attribution_signals"]
        if records.get(row["record_id"]) == "mitre"
    ]
    bad_signals = [
        row["attribution_signal_id"]
        for row in mitre_signals
        if row.get("signal_type") != "direct_attribution"
    ]
    return CheckResult(
        "mitre_direct_only_for_attributed_to",
        not bad_direct_relations and not bad_non_direct_relations and not bad_signals,
        {
            "mitre_signal_count": len(mitre_signals),
            "bad_direct_relations": bad_direct_relations,
            "bad_non_direct_relations": bad_non_direct_relations,
            "bad_signals": bad_signals,
        },
    )


def _check_no_unconfirmed_relations(artifacts: dict[str, dict[str, Any]]) -> CheckResult:
    serialized = json.dumps(artifacts, sort_keys=True)
    present = sorted(relation for relation in CONFIRMED_RELATIONS if relation in serialized)
    return CheckResult("no_related_to_or_observed_with", not present, {"present": present})


def _check_unsupported_dns_types_are_deferred(
    artifacts: dict[str, dict[str, Any]]
) -> CheckResult:
    records = {
        row["record_id"]: row["source"]["connector_source"]
        for row in artifacts["jsonl"]["intermediate_records"]
    }
    emitted = {
        row["predicate"]["mapped_value"]
        for row in artifacts["jsonl"]["relation_mentions"]
        if records.get(row["record_id"]) in {"pdns", "vt"}
    }
    unsupported_relation_names = emitted - {
        "resolves-to",
        "belongs-to",
        "located-in",
        "uses-nameserver",
        "has-subdomain",
    }
    open_issues_text = "\n".join(artifacts["json"]["processing_report"].get("open_issues", []))
    mentions_deferred = "DNS record types outside A/NS" in open_issues_text
    return CheckResult(
        "unsupported_dns_types_are_deferred",
        not unsupported_relation_names and mentions_deferred,
        {
            "infrastructure_relation_predicates": sorted(emitted),
            "unsupported_relation_names": sorted(unsupported_relation_names),
            "open_issue_mentions_dns_deferred": mentions_deferred,
        },
    )


def _check_raw_payload_preserved(delivery_dir: Path, artifacts: dict[str, dict[str, Any]]) -> CheckResult:
    failures: list[str] = []
    for record in artifacts["jsonl"]["intermediate_records"]:
        source = record["source"]["connector_source"]
        raw_path = delivery_dir / record["raw_ref"]["raw_path"]
        raw = _read_json(raw_path)
        if source in {"pdns", "vt"} and "payload" not in raw:
            failures.append(f"{record['record_id']}: missing RawStore payload")
        if source == "otx" and "id" not in raw:
            failures.append(f"{record['record_id']}: missing OTX pulse id")
        if source == "mitre" and ("id" not in raw or "type" not in raw):
            failures.append(f"{record['record_id']}: missing MITRE STIX id/type")
    return CheckResult("raw_payload_preserved", not failures, {"failures": failures})


def _check_readme_exists(delivery_dir: Path) -> CheckResult:
    readme = delivery_dir / "README.md"
    return CheckResult("readme_present", readme.is_file(), {"path": readme.as_posix()})


def _write_readme(
    output_dir: Path,
    artifacts: dict[str, dict[str, Any]],
    sample_metadata: dict[str, Any],
    *,
    audit_status: str,
) -> None:
    manifest_sources = artifacts["json"]["source_manifest"].get("sources", [])
    source_counts = {
        row["connector_source"]: row["record_count"]
        for row in manifest_sources
        if isinstance(row, dict)
    }
    row_counts = {
        artifact: len(rows)
        for artifact, rows in artifacts["jsonl"].items()
        if artifact in JSONL_ARTIFACTS
    }
    report = artifacts["json"]["processing_report"]
    raw_dns = sample_metadata["raw_dns_type_coverage"]
    readme = f"""# CTI-RAG Intermediate Delivery v0.1

This package is the Stage 1 / Structured CTI Representation v0.1 delivery for
the CTI-RAG project. It is a reusable intermediate layer, not a retrieval chunk
corpus and not a final resolved graph.

Generated: `{GENERATED_AT}`
Dataset id: `{DEFAULT_DATASET_ID}`
Dataset version: `{DEFAULT_DATASET_VERSION}`
Acceptance audit status: `{audit_status}`

## Scope

This is a sampled delivery package for OTX, pDNS, and VirusTotal, plus the
supported records from the local MITRE ATT&CK bundle. It does not claim complete
coverage of AlienVault OTX, passive DNS, VirusTotal, or the internet.

Source record counts in this package:

```json
{json.dumps(dict(sorted(source_counts.items())), indent=2, sort_keys=True)}
```

Artifact row counts:

```json
{json.dumps(row_counts, indent=2, sort_keys=True)}
```

Raw DNS record type coverage in the sampled infrastructure sources:

```json
{json.dumps(raw_dns, indent=2, sort_keys=True)}
```

## Files

- `raw/`: delivered raw snapshots used as provenance for intermediate records.
- `intermediate/source_manifest.json`: dataset metadata and source summaries.
- `intermediate/intermediate_records.jsonl`: one source-backed intermediate record per transformed source item.
- `intermediate/entity_mentions.jsonl`: source-backed entity mentions.
- `intermediate/relation_mentions.jsonl`: source-backed relation mentions.
- `intermediate/attribution_signals.jsonl`: attribution cues preserved as signals.
- `intermediate/record_features.jsonl`: per-record feature summaries.
- `intermediate/processing_report.json`: counts, coverage, warnings, and open issues.
- `acceptance_audit.json`: final package validation and audit checks.
- `README.md`: this handoff note.

## Attribution Boundary

OTX adversary fields are preserved as `weak_direct_attribution` signals. They
are weak source cues, not ground truth. MITRE `attributed-to` relationships are
preserved as `direct_attribution` source-backed signals, not independent
verification. MITRE `uses`, `mitigates`, and `detects` relationships are
source-backed relations and do not become direct labels.

pDNS and VirusTotal are infrastructure/enrichment sources. They do not produce
attribution signals in this package.

## Entity And Relation Semantics

Entity and relation rows are source-backed mentions. They are not a final
cross-source entity-resolution graph. The package intentionally does not merge
OTX, MITRE, pDNS, or VirusTotal entities across sources.

The infrastructure exporters currently map A and NS DNS answers into
`resolves-to` and `uses-nameserver` relation mentions, with pDNS ASN and country
fields also supporting `belongs-to` and `located-in`. DNS record types outside
A/NS remain in `raw/` and are reported in `processing_report.open_issues`.

The package does not contain proposed but unconfirmed relations such as
`related-to` or `observed-with`.

## Raw Preservation And Hash Checks

Every `intermediate_records.jsonl` row contains `raw_ref.raw_path` and
`raw_ref.raw_sha256`. The audit verifies that each raw path points inside this
package and that each SHA-256 matches the delivered raw file. pDNS and VT raw
snapshots preserve the RawStore wrapper shape
`{{source, source_id, fetched_at, payload}}`.

## Validation Summary

`validate_delivery(...)` result: see `acceptance_audit.json`. Processing report
coverage:

```json
{json.dumps(report.get("coverage", {}), indent=2, sort_keys=True)}
```

## Deferred / Known Limits

- PDF richer extraction deferred.
- WHOIS deferred because no local `data/raw/whois` directory is present.
- Temporal split deferred.
- Confidence and source reliability deferred.
- Production RAG/GNN/Neo4j export deferred.
- Cross-source entity resolution deferred.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def _sampling_notes(
    raw_dir: Path,
    *,
    otx_limit: int,
    pdns_limit: int,
    vt_limit: int,
    actual_otx: int,
    actual_pdns: int,
    actual_vt: int,
) -> list[str]:
    notes: list[str] = []
    if actual_otx < otx_limit:
        notes.append(f"Only {actual_otx} OTX flat raw pulses found under {raw_dir / 'otx'}.")
    if actual_pdns < pdns_limit:
        notes.append(f"Only {actual_pdns} pDNS RawStore snapshots found with DNS records.")
    if actual_vt < vt_limit:
        notes.append(f"Only {actual_vt} VT RawStore snapshots found with DNS records.")
    if not (raw_dir / "whois").exists():
        notes.append("No local data/raw/whois directory was present; WHOIS remains deferred.")
    return notes


def _dns_type_counter(
    records: list[dict[str, Any]],
    dns_path: tuple[str, ...],
    type_key: str,
) -> Counter[str]:
    counter: Counter[str] = Counter()
    for raw in records:
        value: Any = raw
        for key in dns_path:
            value = value.get(key) if isinstance(value, dict) else None
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            dns_type = _text(item.get(type_key)).upper()
            if dns_type:
                counter[dns_type] += 1
    return Counter(dict(sorted(counter.items())))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row must be an object: {path}")
        rows.append(value)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--otx-limit", type=int, default=20)
    parser.add_argument("--pdns-limit", type=int, default=20)
    parser.add_argument("--vt-limit", type=int, default=20)
    parser.add_argument("--sample-mitre", action="store_true", help="sample MITRE instead of full")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    audit = build_delivery(
        raw_dir=args.raw_dir,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        otx_limit=args.otx_limit,
        pdns_limit=args.pdns_limit,
        vt_limit=args.vt_limit,
        mitre_full=not args.sample_mitre,
    )
    print(f"delivery_dir={args.output_dir}")
    print(f"audit_ok={audit['ok']}")
    print(f"source_record_counts={json.dumps(audit['source_record_counts'], sort_keys=True)}")
    print(f"artifact_row_counts={json.dumps(audit['artifact_row_counts'], sort_keys=True)}")
    print(f"validation_ok={audit['validation']['ok']}")


if __name__ == "__main__":
    main()
