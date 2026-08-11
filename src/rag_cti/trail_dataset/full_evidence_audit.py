"""Streaming integrity audit for a full stage-4 graph evidence ledger.

This checks package-internal lineage pointers only.  It intentionally does not
make a claim about the truth, maliciousness, attribution, or quality of a
current local input.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from rag_cti.trail_dataset.factual_audit import classify_evidence


def build_full_evidence_audit(artifact_dir: Path, *, repository_root: Path) -> dict[str, Any]:
    artifact_dir, repository_root = Path(artifact_dir), Path(repository_root)
    manifest = _json(artifact_dir / "manifest.json")
    nodes = {row["node_id"]: (row.get("type"), row.get("value")) for row in _jsonl(artifact_dir / "nodes.jsonl")}
    ledger_path = artifact_dir / "evidence_ledger.jsonl"
    ledger = _jsonl(ledger_path)
    digest = hashlib.sha256()
    totals: Counter[str] = Counter()
    by_stratum: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    raw_presence: dict[str, bool] = {}
    ledger_mismatches = 0
    transforms_failed = 0
    missing_locator = 0
    evidence_count = 0
    for edge in _jsonl(artifact_dir / "edges.jsonl"):
        totals["edges"] += 1
        for evidence_index, evidence in enumerate(edge.get("evidence") or []):
            try:
                row, encoded = next(ledger)
            except StopIteration:
                ledger_mismatches += 1
                continue
            digest.update(encoded)
            evidence_count += 1
            expected = {"edge_id": edge["edge_id"], "evidence_index": evidence_index, "source_id": edge["source_id"], "target_id": edge["target_id"], "relation": edge["relation"], **evidence}
            if row != expected:
                ledger_mismatches += 1
            source = str(evidence.get("source") or "unknown")
            target_type = str(nodes.get(edge["target_id"], ("unknown", None))[0] or "unknown")
            evidence_class = classify_evidence(evidence)
            stratum = by_stratum[(source, target_type, evidence_class)]
            stratum["total"] += 1
            if not evidence.get("record_path"):
                missing_locator += 1
                stratum["missing_locator"] += 1
            raw_key = _raw_path(evidence.get("raw_ref"), repository_root)
            if raw_key is None:
                stratum["missing_raw_ref"] += 1
            else:
                if raw_key not in raw_presence:
                    raw_presence[raw_key] = Path(raw_key).is_file()
                stratum["raw_path_found" if raw_presence[raw_key] else "raw_path_missing"] += 1
            if edge["relation"].startswith("url_"):
                if _url_transform_matches(edge, nodes):
                    stratum["deterministic_transform_matches"] += 1
                else:
                    transforms_failed += 1
                    stratum["deterministic_transform_failed"] += 1
    try:
        next(ledger)
        ledger_mismatches += 1
    except StopIteration:
        pass
    rejects = sum(1 for _ in _jsonl(artifact_dir / "rejected_records.jsonl"))
    result = {
        "format": "trail-five-node-full-evidence-integrity-audit",
        "format_version": 1,
        "scope": "Full streaming package-integrity, local raw-path-presence, locator-presence, and deterministic URL-transform checks. This is not a raw-content reparse or a factual, maliciousness, attribution, or source-acceptance conclusion.",
        "input_snapshot": "current_local_input",
        "artifact": {
            "path": str(artifact_dir),
            "content_sha256": manifest.get("content_sha256"),
            "event_count": manifest.get("event_count"),
            "node_count": manifest.get("node_count"),
            "edge_count": manifest.get("edge_count"),
            "rejected_count": manifest.get("rejected_count"),
        },
        "checks": {
            "edges_streamed": totals["edges"],
            "evidence_rows_streamed": evidence_count,
            "evidence_ledger_rows_expected": (manifest.get("evidence_ledger") or {}).get("row_count"),
            "evidence_ledger_sha256_expected": (manifest.get("evidence_ledger") or {}).get("sha256"),
            "evidence_ledger_sha256_actual": digest.hexdigest(),
            "evidence_ledger_mismatches": ledger_mismatches,
            "rejected_rows_actual": rejects,
            "raw_paths_unique": len(raw_presence),
            "raw_paths_missing": sum(not found for found in raw_presence.values()),
            "missing_record_locators": missing_locator,
            "deterministic_url_transform_failures": transforms_failed,
            "raw_content_or_span_reparsed": False,
        },
        "strata": [
            {"source": source, "ioc_type": ioc_type, "evidence_class": evidence_class, **dict(counts)}
            for (source, ioc_type, evidence_class), counts in sorted(by_stratum.items())
        ],
        "gate_decision": "pending_factual_audit",
    }
    result["checks"]["passed"] = _passed(result, manifest)
    audit_path = artifact_dir / "full_evidence_integrity_audit.json"
    _write(audit_path, result)
    _update_manifest(artifact_dir / "manifest.json", manifest, audit_path)
    return result


def _passed(result: dict[str, Any], manifest: dict[str, Any]) -> bool:
    checks = result["checks"]
    return all((
        checks["edges_streamed"] == manifest.get("edge_count"),
        checks["evidence_rows_streamed"] == checks["evidence_ledger_rows_expected"],
        checks["evidence_ledger_sha256_actual"] == checks["evidence_ledger_sha256_expected"],
        checks["evidence_ledger_mismatches"] == 0,
        checks["rejected_rows_actual"] == manifest.get("rejected_count"),
        checks["raw_paths_missing"] == 0,
        checks["missing_record_locators"] == 0,
        checks["deterministic_url_transform_failures"] == 0,
    ))


def _url_transform_matches(edge: dict[str, Any], nodes: dict[str, tuple[Any, Any]]) -> bool:
    _, url = nodes.get(edge["source_id"], (None, None))
    _, target = nodes.get(edge["target_id"], (None, None))
    if not isinstance(url, str) or not isinstance(target, str):
        return False
    return urlsplit(url).hostname == target


def _raw_path(raw_ref: Any, root: Path) -> str | None:
    if isinstance(raw_ref, dict):
        value = raw_ref.get("repository_raw_path")
    else:
        value = raw_ref
    if not isinstance(value, str) or not value:
        return None
    return str(root / value)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> Iterator[dict[str, Any] | tuple[dict[str, Any], bytes]]:
    with path.open("rb") as source:
        for line in source:
            if line.strip():
                value = json.loads(line)
                if path.name == "evidence_ledger.jsonl":
                    yield value, line
                else:
                    yield value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _update_manifest(path: Path, manifest: dict[str, Any], audit_path: Path) -> None:
    manifest["files"] = sorted(set(manifest.get("files") or []) | {audit_path.name})
    manifest["full_evidence_integrity_audit"] = {
        "path": audit_path.name,
        "sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        "scope": "package integrity only; not factual or semantic verification",
    }
    _write(path, manifest)
