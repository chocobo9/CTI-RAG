"""Full internal lineage-consistency checks for structurally projected five-node graphs."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from rag_cti.trail_dataset.builder import (
    _normalise_indicator,
    _orkl_body_reference_spans,
    _orkl_url_is_inline_citation,
    _split_misp_attribute,
)
from rag_cti.trail_dataset.factual_audit import classify_evidence


def build_lineage_audit(artifact_dir: Path, output_dir: Path, *, repository_root: Path) -> dict[str, Any]:
    artifact_dir, output_dir, repository_root = Path(artifact_dir), Path(output_dir), Path(repository_root)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    nodes = {
        row["node_id"]: {"type": row.get("type"), "value": row.get("value")}
        for row in _iter_jsonl(artifact_dir / "nodes.jsonl")
    }
    # Keep only the event-IOC result required to establish the input of URL
    # transforms.  Retaining all parsed edges/evidence caused full MISP runs to
    # exhaust memory; the graph itself remains read-only.
    containment: dict[tuple[str, str], str] = {}
    raw_cache: dict[str, dict[str, Any] | None] = {}
    counts: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    output_dir.mkdir(parents=True)
    record_path = output_dir / "lineage_records.jsonl"
    with record_path.open("x", encoding="utf-8", newline="\n") as destination:
        # First pass proves every EVENT -> IOC observation and records its result.
        for edge in _iter_jsonl(artifact_dir / "edges.jsonl"):
            if not edge["relation"].startswith("event_contains_"):
                continue
            source_node, target_node = nodes.get(edge["source_id"], {}), nodes.get(edge["target_id"], {})
            for index, evidence in enumerate(edge.get("evidence") or []):
                record = _check_evidence(edge, index, evidence, source_node, target_node, {}, repository_root, raw_cache)
                _write_record(destination, record)
                _count_record(counts, record)
                containment[(edge["target_id"], _stable_ref(evidence.get("raw_ref")))] = record["lineage_status"]
        # Second pass proves only deterministic graph transforms and supporting
        # pDNS joins.  The output is deterministic by source edge ordering.
        for edge in _iter_jsonl(artifact_dir / "edges.jsonl"):
            if edge["relation"].startswith("event_contains_"):
                continue
            source_node, target_node = nodes.get(edge["source_id"], {}), nodes.get(edge["target_id"], {})
            for index, evidence in enumerate(edge.get("evidence") or []):
                record = _check_evidence(edge, index, evidence, source_node, target_node, containment, repository_root, raw_cache)
                _write_record(destination, record)
                _count_record(counts, record)
    summary = _summarize_counts(counts)
    _write_json(output_dir / "lineage_coverage.json", summary)
    _write_json(output_dir / "audit_manifest.json", _audit_manifest(artifact_dir, summary))
    return {"record_count": summary["totals"]["total"], "coverage": summary["totals"], "gate_decision": summary["gate_decision"]}


def summarize_lineage(records: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for row in records:
        groups[(row["source"], row["ioc_type"], row["evidence_class"])][row["lineage_status"]] += 1
    return _summarize_counts(groups)


def _summarize_counts(groups: dict[tuple[str, str, str], Counter[str]]) -> dict[str, Any]:
    rows = []
    totals: Counter[str] = Counter()
    for (source, ioc_type, evidence_class), counts in sorted(groups.items()):
        totals.update(counts)
        rows.append({"source": source, "ioc_type": ioc_type, "evidence_class": evidence_class, "total": sum(counts.values()), "traceable": counts["traceable"], "failed": counts["failed"], "unlocatable": counts["unlocatable"], "human_confirmation": "unreviewed", "gate_decision": "pending_factual_audit"})
    return {"format": "trail-five-node-lineage-coverage", "format_version": 1, "scope": "Full internal lineage and transformation-consistency checks over the current local input snapshot; not factual or semantic review.", "rows": rows, "totals": {"total": sum(totals.values()), "traceable": totals["traceable"], "failed": totals["failed"], "unlocatable": totals["unlocatable"], "human_confirmation": "unreviewed"}, "gate_decision": "pending_factual_audit"}


def _count_record(groups: dict[tuple[str, str, str], Counter[str]], record: dict[str, Any]) -> None:
    groups[(record["source"], record["ioc_type"], record["evidence_class"])][record["lineage_status"]] += 1


def _check_evidence(edge: dict[str, Any], index: int, evidence: dict[str, Any], source_node: dict[str, Any], target_node: dict[str, Any], containment: dict[tuple[str, str], str], repository_root: Path, raw_cache: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    source = str(evidence.get("source") or "unknown")
    status, reason = _verify(edge, evidence, source_node, target_node, containment, repository_root, raw_cache)
    return {"lineage_id": f"lineage:{edge['edge_id']}:{index}", "source": source, "edge_id": edge["edge_id"], "relation": edge["relation"], "source_id": edge["source_id"], "target_id": edge["target_id"], "ioc_type": str(target_node.get("type") or "unknown"), "evidence_class": classify_evidence(evidence), "raw_ref": evidence.get("raw_ref"), "record_path": evidence.get("record_path"), "raw_value": evidence.get("raw_value"), "derivation": evidence.get("derivation"), "extraction_method": evidence.get("extraction_method"), "lineage_status": status, "reason_code": reason, "human_confirmation": "unreviewed", "input_snapshot": "current_local_input"}


def _verify(edge: dict[str, Any], evidence: dict[str, Any], source_node: dict[str, Any], target_node: dict[str, Any], containment: dict[tuple[str, str], str], root: Path, cache: dict[str, dict[str, Any] | None]) -> tuple[str, str]:
    source, relation = str(evidence.get("source") or ""), edge["relation"]
    if relation.startswith("event_contains_"):
        return _verify_event_ioc(source, evidence, target_node, root, cache)
    if relation.startswith("url_"):
        return _verify_url_derivation(edge, evidence, source_node, target_node, containment, root, cache)
    if source == "pdns":
        return _verify_pdns(relation, evidence, source_node, target_node, root, cache)
    return "unlocatable", "unsupported_relation_or_source"


def _verify_event_ioc(source: str, evidence: dict[str, Any], target: dict[str, Any], root: Path, cache: dict[str, dict[str, Any] | None]) -> tuple[str, str]:
    raw = _raw_document(source, evidence.get("raw_ref"), root, cache)
    path = str(evidence.get("record_path") or "")
    if raw is None:
        return "unlocatable", "raw_input_not_found_or_invalid"
    if source == "orkl":
        return _verify_orkl_body(raw, path, target, evidence)
    item = _attribute_at(raw, source, path)
    if not isinstance(item, dict):
        return "unlocatable", "structured_field_not_found"
    values = _attribute_values(item, source)
    for raw_type, raw_value in values:
        normalized = _normalise_indicator(raw_type, raw_value, source)
        if normalized == (target.get("type"), target.get("value")):
            return "traceable", "structured_field_normalizes_to_graph_ioc"
    return "failed", "structured_field_value_or_type_mismatch"


def _verify_orkl_body(raw: dict[str, Any], path: str, target: dict[str, Any], evidence: dict[str, Any]) -> tuple[str, str]:
    match = re.fullmatch(r"body\.char\[(\d+):(\d+)\]", path)
    body = raw.get("plain_text")
    if not match or not isinstance(body, str):
        return "unlocatable", "body_span_not_found"
    start, end = (int(value) for value in match.groups())
    token = body[start:end]
    raw_value = evidence.get("raw_value")
    if raw_value is not None and token != raw_value:
        return "failed", "body_span_raw_value_mismatch"
    if target.get("type") == "url" and (
        any(span_start <= start < span_end for span_start, span_end in _orkl_body_reference_spans(body))
        or _orkl_url_is_inline_citation(body, start)
    ):
        return "failed", "orkl_body_reference_or_citation_context"
    normalized = _normalise_indicator(target.get("type"), re.sub(r"(?i)^hxxp", "http", token), "orkl")
    if normalized == (target.get("type"), target.get("value")):
        return "traceable", "body_span_normalizes_to_graph_ioc"
    return "failed", "body_span_normalization_mismatch"


def _verify_url_derivation(edge: dict[str, Any], evidence: dict[str, Any], source_node: dict[str, Any], target_node: dict[str, Any], containment: dict[tuple[str, str], str], root: Path, cache: dict[str, dict[str, Any] | None]) -> tuple[str, str]:
    url = str(source_node.get("value") or "")
    parsed = urlsplit(url)
    expected = parsed.hostname.lower() if parsed.hostname else None
    if edge["relation"] == "url_resolves_to_ip":
        expected = parsed.hostname.lower() if parsed.hostname else None
    if expected != target_node.get("value"):
        return "failed", "deterministic_url_transform_mismatch"
    if containment.get((edge["source_id"], _stable_ref(evidence.get("raw_ref")))) == "traceable":
        return "traceable", "traceable_url_input_and_deterministic_host_transform"
    return "unlocatable", "url_input_evidence_not_traceable"


def _verify_pdns(relation: str, evidence: dict[str, Any], source_node: dict[str, Any], target_node: dict[str, Any], root: Path, cache: dict[str, dict[str, Any] | None]) -> tuple[str, str]:
    raw = _raw_document("pdns", evidence.get("raw_ref"), root, cache)
    match = re.search(r"passive_dns\[(\d+)\]", str(evidence.get("record_path") or ""))
    rows = (raw or {}).get("payload", raw or {}).get("passive_dns") or []
    if not match or int(match.group(1)) >= len(rows):
        return "unlocatable", "pdns_resolution_not_found"
    row = rows[int(match.group(1))]
    address = str(row.get("address") or "")
    asn_parts = str(row.get("asn") or "").split()
    asn = asn_parts[0] if asn_parts else ""
    if relation == "domain_resolves_to_ip" and address == target_node.get("value"):
        return "traceable", "pdns_resolution_matches_graph_ip"
    if relation == "ip_in_asn" and address == source_node.get("value") and asn == target_node.get("value"):
        return "traceable", "pdns_asn_matches_graph_endpoints"
    return "failed", "pdns_value_or_endpoint_mismatch"


def _raw_document(source: str, raw_ref: Any, root: Path, cache: dict[str, dict[str, Any] | None]) -> dict[str, Any] | None:
    if isinstance(raw_ref, dict):
        path = root / "data" / "raw" / "orkl" / str(raw_ref.get("raw_path") or "")
    else:
        path = root / str(raw_ref or "")
    key = str(path)
    if key not in cache:
        try:
            cache[key] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            cache[key] = None
        # Full ORKL reports can be large.  This deliberately tiny cache keeps
        # repeated local lookups efficient without retaining the raw corpus.
        if len(cache) > 8:
            cache.pop(next(iter(cache)))
    return cache[key]


def _attribute_at(raw: dict[str, Any], source: str, path: str) -> dict[str, Any] | None:
    if source == "otx":
        match = re.fullmatch(r"indicators\[(\d+)\]", path)
        rows = raw.get("payload", raw).get("indicators") or []
    else:
        event = raw.get("Event", raw)
        object_match = re.fullmatch(r"Event\.Object\[(\d+)\]\.Attribute\[(\d+)\]", path)
        if object_match:
            object_index, attribute_index = (int(value) for value in object_match.groups())
            objects = event.get("Object") or []
            if object_index >= len(objects):
                return None
            rows = objects[object_index].get("Attribute") or []
            return rows[attribute_index] if attribute_index < len(rows) else None
        match = re.fullmatch(r"Event\.Attribute\[(\d+)\]", path)
        rows = event.get("Attribute") or []
    if not match or int(match.group(1)) >= len(rows):
        return None
    return rows[int(match.group(1))]


def _attribute_values(item: dict[str, Any], source: str) -> list[tuple[Any, Any]]:
    if source == "otx":
        return [(item.get("type"), item.get("indicator", item.get("value")))]
    return _split_misp_attribute(item.get("type"), item.get("value"))


def _stable_ref(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_record(destination: Any, record: dict[str, Any]) -> None:
    destination.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _audit_manifest(artifact_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    manifest_path = artifact_dir / "manifest.json"
    manifest_bytes = manifest_path.read_bytes() if manifest_path.is_file() else b""
    artifact_manifest = json.loads(manifest_bytes) if manifest_bytes else {}
    return {
        "format": "trail-five-node-full-internal-lineage-audit",
        "format_version": 1,
        "scope": "Internal raw-path, field/span, normalization, and deterministic-transform consistency only; not a factual, maliciousness, attribution, or source-acceptance conclusion.",
        "artifact": {
            "path": str(artifact_dir),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest() if manifest_bytes else None,
            "content_sha256": artifact_manifest.get("content_sha256"),
            "evidence_ledger": artifact_manifest.get("evidence_ledger"),
            "rejected_count": artifact_manifest.get("rejected_count"),
        },
        "coverage": summary,
        "input_snapshot": "current_local_input",
        "raw_inputs_modified": False,
    }
