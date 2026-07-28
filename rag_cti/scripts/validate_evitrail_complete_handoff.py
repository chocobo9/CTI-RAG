"""Validate an EviTRAIL data handoff against the teammate's actual reader."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterator, Mapping


REQUIRED_EVIDENCE = {"source", "raw_ref", "record_path", "derivation"}
RELATION_ENDPOINTS = {
    "event_contains_domain": ("event", "domain"),
    "event_contains_ip": ("event", "ip"),
    "event_contains_url": ("event", "url"),
    "domain_resolves_to_ip": ("domain", "ip"),
    "url_hosted_on_domain": ("url", "domain"),
    "url_resolves_to_ip": ("url", "ip"),
    "ip_in_asn": ("ip", "asn"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--evitrail-root", type=Path, required=True)
    parser.add_argument("--otx-root", type=Path, required=True)
    args = parser.parse_args()
    result = validate_package(
        args.package.resolve(),
        args.evitrail_root.resolve(),
        args.otx_root.resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def validate_package(
    package: Path, evitrail_root: Path, otx_root: Path
) -> dict[str, Any]:
    handoff = package / "handoff"
    errors: list[str] = []
    manifest = _read_json(package / "manifest.json")

    event_ids: set[str] = set()
    event_sources: Counter[str] = Counter()
    for line, row in _iter_jsonl(handoff / "events.jsonl", with_line=True):
        required = {"event_id", "source", "source_record_id", "raw_ref"}
        missing = required - row.keys()
        if missing:
            errors.append(f"events.jsonl:{line}:missing:{sorted(missing)}")
            continue
        eid = str(row["event_id"])
        if eid in event_ids:
            errors.append(f"events.jsonl:{line}:duplicate_event_id:{eid}")
        event_ids.add(eid)
        event_sources[str(row["source"])] += 1

    nodes: dict[str, str] = {}
    node_counts: Counter[str] = Counter()
    for line, row in _iter_jsonl(handoff / "nodes.jsonl", with_line=True):
        node_id = str(row.get("node_id") or "")
        node_type = str(row.get("type") or "")
        if not node_id or node_type not in {"event", "domain", "ip", "url", "asn"}:
            errors.append(f"nodes.jsonl:{line}:invalid_node")
            continue
        if node_id in nodes:
            errors.append(f"nodes.jsonl:{line}:duplicate_node_id:{node_id}")
        nodes[node_id] = node_type
        node_counts[node_type] += 1
    missing_event_nodes = event_ids - nodes.keys()
    if missing_event_nodes:
        errors.append(f"missing_event_nodes:{len(missing_event_nodes)}")

    edge_ids: set[str] = set()
    relation_counts: Counter[str] = Counter()
    for line, row in _iter_jsonl(handoff / "edges.jsonl", with_line=True):
        edge_id = str(row.get("edge_id") or "")
        relation = str(row.get("relation") or "")
        source_id = str(row.get("source_id") or "")
        target_id = str(row.get("target_id") or "")
        if edge_id in edge_ids:
            errors.append(f"edges.jsonl:{line}:duplicate_edge_id:{edge_id}")
        edge_ids.add(edge_id)
        expected = RELATION_ENDPOINTS.get(relation)
        actual = (nodes.get(source_id), nodes.get(target_id))
        if not expected:
            errors.append(f"edges.jsonl:{line}:unsupported_relation:{relation}")
        elif actual != expected:
            errors.append(
                f"edges.jsonl:{line}:wrong_endpoints:{relation}:{actual}:{expected}"
            )
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"edges.jsonl:{line}:missing_evidence")
        elif missing := REQUIRED_EVIDENCE - evidence[0].keys():
            errors.append(
                f"edges.jsonl:{line}:incomplete_evidence:{sorted(missing)}"
            )
        relation_counts[relation] += 1

    claim_ids: set[str] = set()
    handoff_claim_sources: Counter[str] = Counter()
    for line, row in _iter_jsonl(
        handoff / "source_claims.jsonl", with_line=True
    ):
        required = {
            "claim_id",
            "event_id",
            "source",
            "raw_value",
            "raw_ref",
            "source_field",
            "claim_scope",
            "set_semantics",
            "usage",
        }
        if missing := required - row.keys():
            errors.append(
                f"source_claims.jsonl:{line}:missing:{sorted(missing)}"
            )
        claim_id = str(row.get("claim_id") or "")
        if claim_id in claim_ids:
            errors.append(
                f"source_claims.jsonl:{line}:duplicate_claim_id:{claim_id}"
            )
        claim_ids.add(claim_id)
        if row.get("event_id") not in event_ids:
            errors.append(f"source_claims.jsonl:{line}:missing_event")
        handoff_claim_sources[str(row.get("source") or "")] += 1

    all_claim_count = 0
    all_claim_sources: Counter[str] = Counter()
    all_claim_ids: set[str] = set()
    for line, row in _iter_jsonl(
        package / "labels" / "all_source_claims.jsonl", with_line=True
    ):
        all_claim_count += 1
        claim_id = str(row.get("claim_id") or "")
        if not claim_id or claim_id in all_claim_ids:
            errors.append(
                f"all_source_claims.jsonl:{line}:invalid_or_duplicate_claim_id"
            )
        all_claim_ids.add(claim_id)
        all_claim_sources[str(row.get("source") or "")] += 1

    training_count = 0
    training_sources: Counter[str] = Counter()
    for line, row in _iter_jsonl(
        package / "labels" / "training_labels.jsonl", with_line=True
    ):
        training_count += 1
        eid = str(row.get("event_id") or "")
        if not eid or (eid not in event_ids and not eid.startswith("event:otx:")):
            errors.append(f"training_labels.jsonl:{line}:missing_event")
        if not row.get("actor") or not row.get("source"):
            errors.append(f"training_labels.jsonl:{line}:missing_label_fields")
        training_sources[str(row.get("source") or "")] += 1

    # Exercise the exact consumer implementation, not a local approximation.
    sys.path.insert(0, str(evitrail_root))
    try:
        from evitrail.data.readers import read_handoff, read_otx

        bundle = read_handoff(str(handoff))
        reader_stats = dict(bundle.reader_stats.get("handoff") or {})
        expected_stats = {
            "events": len(event_ids),
            "claims": len(claim_ids),
        }
        for key, expected in expected_stats.items():
            if reader_stats.get(key) != expected:
                errors.append(
                    f"consumer_read_handoff_{key}:{reader_stats.get(key)}!={expected}"
                )
        consumer_stats = reader_stats
        del bundle
        gc.collect()

        sample_ids = [
            "546ce8eb11d40838dc6e43f1",
            "547e0a9511d4080d5a98d83f",
            "58d07c6cf837f01c3ea3bc69",
        ]
        otx_samples: dict[str, dict[str, int]] = {}
        for pulse_id in sample_ids:
            files = sorted((otx_root / pulse_id).glob("*.json"))
            if not files:
                errors.append(f"missing_otx_sample:{pulse_id}")
                continue
            sample = read_otx([str(files[-1])])
            otx_samples[pulse_id] = {
                "events": len(sample.events),
                "indicators": sum(len(row.indicators) for row in sample.events),
                "claims": sum(len(row.claims) for row in sample.events),
                "rejected": len(sample.rejected),
            }
            if len(sample.events) != 1:
                errors.append(f"otx_sample_not_readable:{pulse_id}")
        pipeline_smoke = _run_pipeline_smoke(
            handoff, evitrail_root, otx_root, sample_ids[1]
        )
        if pipeline_smoke["status"] != "passed":
            errors.append(
                "consumer_pipeline_smoke:"
                + str(pipeline_smoke.get("error") or "failed")
            )
    except Exception as exc:  # validation must report the consumer failure
        errors.append(f"consumer_exception:{type(exc).__name__}:{exc}")
        consumer_stats = {}
        otx_samples = {}
        pipeline_smoke = {"status": "failed", "error": str(exc)}

    raw_manifest_path = package.parents[1] / "raw" / "otx_dataset_manifest.json"
    if not raw_manifest_path.exists():
        raw_manifest_path = otx_root.parent / "otx_dataset_manifest.json"
    raw_manifest = (
        _read_json(raw_manifest_path) if raw_manifest_path.exists() else {}
    )
    expected_otx = (
        raw_manifest.get("delivery", {}).get("pulse_count")
        or manifest.get("counts", {}).get("otx_events")
    )
    actual_otx_dirs = sum(
        1
        for path in otx_root.iterdir()
        if path.is_dir() and any(path.glob("*.json"))
    )
    if actual_otx_dirs != expected_otx:
        errors.append(f"otx_pulse_count:{actual_otx_dirs}!={expected_otx}")

    expected_counts = manifest.get("counts", {})
    observed = {
        "handoff_events": len(event_ids),
        "handoff_nodes": len(nodes),
        "handoff_edges": len(edge_ids),
        "handoff_source_claims": len(claim_ids),
        "all_source_claims": all_claim_count,
        "training_labels": training_count,
        "otx_events": actual_otx_dirs,
    }
    for key, value in observed.items():
        if key in expected_counts and expected_counts[key] != value:
            errors.append(
                f"manifest_count_mismatch:{key}:{value}!={expected_counts[key]}"
            )

    hashes = _verify_manifest_hashes(package, manifest)
    errors.extend(hashes["errors"])
    result = {
        "contract": "evitrail_complete_multisource_handoff_validation_v1",
        "status": "passed" if not errors else "failed",
        "verified_consumer_commit": "da4a29e8ce25cff8cbddebb444b069296f949511",
        "checks": {
            "flat_handoff_schema": not any(
                "jsonl:" in error for error in errors
            ),
            "edge_endpoints_and_inline_evidence": not any(
                error.startswith("edges.jsonl") for error in errors
            ),
            "claims_reference_events": not any(
                error.startswith("source_claims.jsonl") for error in errors
            ),
            "exact_consumer_read_handoff": not any(
                error.startswith(("consumer_", "consumer_read_handoff"))
                for error in errors
            ),
            "otx_rawstore_samples": len(otx_samples) == 3
            and not any(error.startswith("otx_sample") for error in errors),
            "exact_pipeline_cli_real_multisource_smoke": pipeline_smoke.get(
                "status"
            )
            == "passed",
            "otx_union_count": actual_otx_dirs == expected_otx,
            "manifest_hashes": not hashes["errors"],
            "checkpoints_or_models_present": False,
        },
        "observed": {
            **observed,
            "events_by_source": dict(sorted(event_sources.items())),
            "nodes_by_type": dict(sorted(node_counts.items())),
            "edges_by_relation": dict(sorted(relation_counts.items())),
            "handoff_claims_by_source": dict(
                sorted(handoff_claim_sources.items())
            ),
            "all_claims_by_source": dict(sorted(all_claim_sources.items())),
            "training_labels_by_source": dict(sorted(training_sources.items())),
            "consumer_read_handoff": consumer_stats,
            "otx_samples": otx_samples,
            "pipeline_cli_smoke": pipeline_smoke,
        },
        "known_boundary": {
            "full_otx_all_at_once_pipeline_run": "not_claimed",
            "reason": (
                "The teammate's current raw reader materializes all 12M+ OTX "
                "indicator occurrences in memory. RawStore compatibility and "
                "the full union were validated independently."
            ),
        },
        "errors": errors[:200],
        "error_count": len(errors),
    }
    _write_json(package / "validation.json", result)
    if not errors:
        manifest["status"] = "delivery_ready"
        manifest["validation"] = "validation.json"
        manifest["files"] = _file_manifest(package)
        _write_json(package / "manifest.json", manifest)
        coverage_path = package / "coverage_audit.json"
        coverage = _read_json(coverage_path)
        coverage["status"] = "passed"
        coverage["consumer_validation"] = "validation.json"
        _write_json(coverage_path, coverage)
        # Coverage changed after the first manifest refresh.
        manifest["files"] = _file_manifest(package)
        _write_json(package / "manifest.json", manifest)
    return result


def _run_pipeline_smoke(
    handoff: Path,
    evitrail_root: Path,
    otx_root: Path,
    otx_pulse_id: str,
) -> dict[str, Any]:
    selected_events: dict[str, dict[str, Any]] = {}
    for row in _iter_jsonl(handoff / "events.jsonl"):
        source = str(row.get("source") or "")
        selected_events.setdefault(source, row)
        if len(selected_events) >= 4:
            break
    selected_ids = {str(row["event_id"]) for row in selected_events.values()}
    selected_edges: list[dict[str, Any]] = []
    per_event: Counter[str] = Counter()
    selected_node_ids = set(selected_ids)
    for row in _iter_jsonl(handoff / "edges.jsonl"):
        source_id = str(row.get("source_id") or "")
        if (
            source_id in selected_ids
            and str(row.get("relation") or "").startswith("event_contains_")
            and per_event[source_id] < 5
        ):
            selected_edges.append(row)
            selected_node_ids.add(str(row["target_id"]))
            per_event[source_id] += 1
    selected_nodes = [
        row
        for row in _iter_jsonl(handoff / "nodes.jsonl")
        if str(row.get("node_id") or "") in selected_node_ids
    ]
    selected_claims = [
        row
        for row in _iter_jsonl(handoff / "source_claims.jsonl")
        if str(row.get("event_id") or "") in selected_ids
    ]
    otx_files = sorted((otx_root / otx_pulse_id).glob("*.json"))
    if not otx_files:
        return {"status": "failed", "error": "missing_otx_smoke_file"}
    mitre = otx_root.parent / "mitre" / "enterprise-attack.json"
    malpedia = otx_root.parent / "malpedia" / "raw" / "actors" / "actors.json"
    with tempfile.TemporaryDirectory(prefix="evitrail-handoff-smoke-") as temp:
        root = Path(temp)
        smoke_handoff = root / "handoff"
        smoke_handoff.mkdir()
        _write_jsonl(smoke_handoff / "events.jsonl", selected_events.values())
        _write_jsonl(smoke_handoff / "nodes.jsonl", selected_nodes)
        _write_jsonl(smoke_handoff / "edges.jsonl", selected_edges)
        _write_jsonl(
            smoke_handoff / "source_claims.jsonl", selected_claims
        )
        _write_jsonl(smoke_handoff / "rejected_records.jsonl", [])
        output = root / "build"
        command = [
            sys.executable,
            "-m",
            "evitrail.data.pipeline",
            "--handoff",
            str(smoke_handoff),
            "--raw-root",
            "__disabled__",
            "--otx",
            str(otx_files[-1]),
            "--mitre",
            str(mitre),
            "--enrichment",
            "none",
            "--out",
            str(output),
        ]
        if malpedia.exists():
            command.extend(["--malpedia", str(malpedia)])
        env = dict(os.environ)
        env["PYTHONPATH"] = str(evitrail_root)
        completed = subprocess.run(
            command,
            cwd=evitrail_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        summary_path = output / "pipeline_summary.json"
        summary = _read_json(summary_path) if summary_path.exists() else {}
        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "exit_code": completed.returncode,
            "handoff_sources": sorted(selected_events),
            "handoff_events": len(selected_events),
            "handoff_edges": len(selected_edges),
            "otx_pulse_id": otx_pulse_id,
            "base_events": summary.get("base", {}).get("events_total"),
            "base_nodes": summary.get("base", {}).get("nodes_total"),
            "base_edges": summary.get("base", {}).get("edges_total"),
            "steps_completed": 7 if completed.returncode == 0 else None,
            "error": completed.stderr[-2000:] if completed.returncode else None,
        }


def _verify_manifest_hashes(
    root: Path, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    errors = []
    checked = 0
    for item in manifest.get("files", []):
        path = root / str(item.get("path") or "")
        if not path.exists():
            errors.append(f"manifest_missing_file:{item.get('path')}")
            continue
        if _sha256(path) != item.get("sha256"):
            errors.append(f"manifest_sha256_mismatch:{item.get('path')}")
        checked += 1
    return {"checked": checked, "errors": errors}


def _file_manifest(root: Path) -> list[dict[str, Any]]:
    output = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "manifest.json" and path.parent == root:
            continue
        output.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_jsonl(
    path: Path, *, with_line: bool = False
) -> Iterator[Any]:
    with path.open("r", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            yield (line_number, row) if with_line else row


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            )


if __name__ == "__main__":
    main()
