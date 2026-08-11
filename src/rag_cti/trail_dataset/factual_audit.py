"""Deterministic, non-semantic factual-audit packets for five-node artifacts."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

EVIDENCE_CLASSES = ("source_asserted", "body_mentioned", "deterministically_derived")
REVIEW_STATUSES = ("verified", "rejected", "ambiguous", "unreviewed")


def build_factual_audit_packets(
    artifact_dir: Path, output_dir: Path, *, repository_root: Path, per_stratum: int = 1
) -> dict[str, Any]:
    """Sample every present evidence stratum without making semantic decisions."""
    artifact_dir, output_dir, repository_root = Path(artifact_dir), Path(output_dir), Path(repository_root)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    if per_stratum < 1:
        raise ValueError("per_stratum must be positive")
    nodes = {row["node_id"]: row for row in _jsonl(artifact_dir / "nodes.jsonl")}
    candidates: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in _jsonl(artifact_dir / "edges.jsonl"):
        source_node, target_node = nodes.get(edge["source_id"], {}), nodes.get(edge["target_id"], {})
        for evidence_index, evidence in enumerate(edge.get("evidence") or []):
            source = str(evidence.get("source") or "unknown")
            evidence_class = classify_evidence(evidence)
            key = (source, str(source_node.get("type") or "unknown"), str(edge.get("relation") or "unknown"), str(target_node.get("type") or "unknown"), evidence_class)
            candidates[key].append({
                "edge": edge, "evidence": evidence, "evidence_index": evidence_index,
                "source_node": source_node, "target_node": target_node,
            })
    packets: list[dict[str, Any]] = []
    for key, rows in sorted(candidates.items()):
        for ordinal, row in enumerate(sorted(rows, key=_candidate_key)[:per_stratum], 1):
            packets.append(_packet(key, ordinal, row, repository_root))
    output_dir.mkdir(parents=True)
    _write_jsonl(output_dir / "audit_packets.jsonl", packets)
    _write_jsonl(output_dir / "audit_results.jsonl", [])
    _write_json(output_dir / "audit_contract.json", audit_contract())
    summary = summarize_audit_packets(packets, [])
    _write_json(output_dir / "audit_summary.json", summary)
    return {"packet_count": len(packets), "stratum_count": len(candidates), "gate_decision": summary["gate_decision"]}


def classify_evidence(evidence: dict[str, Any]) -> str:
    derivation = str(evidence.get("derivation") or "")
    if derivation == "source_asserted":
        return "source_asserted"
    if derivation == "deterministic_orkl_body_ioc_extraction":
        return "body_mentioned"
    return "deterministically_derived"


def audit_contract() -> dict[str, Any]:
    return {
        "format": "trail-five-node-factual-audit", "format_version": 1,
        "evidence_classes": {
            "source_asserted": "A source structured field explicitly supplied the observation or relationship.",
            "body_mentioned": "A local report body contains the exact token; this is not a maliciousness or relationship claim.",
            "deterministically_derived": "A deterministic transform, such as accepted URL hostname parsing, produced the graph fact.",
        },
        "review_statuses": list(REVIEW_STATUSES),
        "result_record": {
            "required": ["packet_id", "review_status", "reason_code", "reviewer.identifier", "reviewer.procedure", "reviewer.reviewed_at"],
            "verified_requires": "semantic_basis",
            "reviewer_fields": ["identifier", "procedure", "reviewed_at"],
        },
        "semantic_verification_policy": "No packet or evidence-integrity check is semantic verification by default. A reviewer must supply a semantic basis before using verified.",
        "input_boundary": "Raw paths identify the current local input snapshot. Derived graph and audit conclusions remain separate from the raw-input identity.",
        "default_gate": "pending_factual_audit",
    }


def validate_result(record: dict[str, Any]) -> None:
    if record.get("review_status") not in REVIEW_STATUSES:
        raise ValueError("invalid review_status")
    if not record.get("packet_id") or not record.get("reason_code"):
        raise ValueError("packet_id and reason_code are required")
    if not isinstance(record.get("reviewer"), dict):
        raise ValueError("reviewer is required")
    for field in ("identifier", "procedure", "reviewed_at"):
        if not record["reviewer"].get(field):
            raise ValueError(f"reviewer.{field} is required")
    if record.get("review_status") == "verified" and not record.get("semantic_basis"):
        raise ValueError("verified requires semantic_basis")


def summarize_audit_packets(packets: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    result_by_packet = {row.get("packet_id"): row for row in results}
    rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for packet in packets:
        stratum = packet["stratum"]
        grouped[(stratum["source"], stratum["source_type"], stratum["relation"], stratum["target_type"], stratum["evidence_class"])].append(packet)
    total = dict.fromkeys(REVIEW_STATUSES, 0)
    for key, members in sorted(grouped.items()):
        counts = dict.fromkeys(REVIEW_STATUSES, 0)
        for packet in members:
            status = str(result_by_packet.get(packet["packet_id"], {}).get("review_status") or "unreviewed")
            counts[status] += 1
            total[status] += 1
        rows.append({"stratum": dict(zip(("source", "source_type", "relation", "target_type", "evidence_class"), key, strict=True)), "sample_count": len(members), "reviewed_count": len(members) - counts["unreviewed"], **counts, "gate_decision": _gate_decision(counts)})
    source_totals: dict[str, dict[str, int]] = {}
    for packet in packets:
        source = packet["stratum"]["source"]
        counts = source_totals.setdefault(source, dict.fromkeys(REVIEW_STATUSES, 0))
        status = str(result_by_packet.get(packet["packet_id"], {}).get("review_status") or "unreviewed")
        counts[status] += 1
    sources = {
        source: {
            "sample_count": sum(counts.values()),
            "reviewed_count": sum(counts.values()) - counts["unreviewed"],
            **counts,
            "factual_scope": "sampled_local_evidence_only_not_source_wide_acceptance",
        }
        for source, counts in sorted(source_totals.items())
    }
    return {
        "format": "trail-five-node-factual-audit-summary",
        "format_version": 2,
        "scope": "Per-stratum checks over the current local input snapshot; they do not establish source-wide factual correctness, maliciousness, or usability.",
        "strata": rows,
        "sources": sources,
        "totals": {"sample_count": len(packets), "reviewed_count": len(packets) - total["unreviewed"], **total},
        "gate_decision": _gate_decision(total),
    }


def regenerate_audit_summary(audit_dir: Path) -> dict[str, Any]:
    """Validate reviewer-authored records and rewrite only the audit summary."""
    audit_dir = Path(audit_dir)
    packets = _jsonl(audit_dir / "audit_packets.jsonl")
    results = _jsonl(audit_dir / "audit_results.jsonl")
    packet_ids = {row["packet_id"] for row in packets}
    for result in results:
        validate_result(result)
        if result["packet_id"] not in packet_ids:
            raise ValueError(f"unknown packet_id: {result['packet_id']}")
    summary = summarize_audit_packets(packets, results)
    _write_json(audit_dir / "audit_summary.json", summary)
    return summary


def _gate_decision(counts: dict[str, int]) -> str:
    del counts
    return "pending_factual_audit"


def _packet(key: tuple[str, str, str, str, str], ordinal: int, row: dict[str, Any], repository_root: Path) -> dict[str, Any]:
    source, source_type, relation, target_type, evidence_class = key
    evidence = row["evidence"]
    packet_id = "audit:" + "|".join((*key, row["edge"]["edge_id"], str(row["evidence_index"])))
    context = _body_context(evidence, repository_root)
    return {
        "packet_id": packet_id, "stratum": {"source": source, "source_type": source_type, "relation": relation, "target_type": target_type, "evidence_class": evidence_class}, "sample_ordinal": ordinal,
        "graph": {"edge_id": row["edge"]["edge_id"], "source_id": row["edge"]["source_id"], "target_id": row["edge"]["target_id"], "relation": relation, "source_node": row["source_node"], "target_node": row["target_node"]},
        "provenance": {"raw_ref": evidence.get("raw_ref"), "record_path": evidence.get("record_path"), "raw_value": evidence.get("raw_value"), "observed_at": evidence.get("observed_at"), "extraction_method": evidence.get("extraction_method"), "derivation": evidence.get("derivation"), "body_context": context},
        "review_status": "unreviewed", "evidence_integrity_status": _integrity_status(evidence, context), "semantic_verification": "not_automatic",
    }


def _body_context(evidence: dict[str, Any], repository_root: Path) -> dict[str, Any] | None:
    path = str(evidence.get("record_path") or "")
    raw_ref = evidence.get("raw_ref")
    if not path.startswith("body.char[") or not isinstance(raw_ref, dict):
        return None
    try:
        start, end = (int(value) for value in path.removeprefix("body.char[").removesuffix("]").split(":"))
        raw_path = repository_root / "data" / "raw" / "orkl" / str(raw_ref["raw_path"])
        body = json.loads(raw_path.read_text(encoding="utf-8")).get("plain_text")
        if not isinstance(body, str):
            return {"status": "unavailable"}
        return {"status": "available", "start": start, "end": end, "text": body[max(0, start - 120):min(len(body), end + 120)]}
    except (KeyError, OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return {"status": "unavailable"}


def _integrity_status(evidence: dict[str, Any], context: dict[str, Any] | None) -> str:
    if not context or context.get("status") != "available":
        return "not_checked"
    raw_value = evidence.get("raw_value")
    if not isinstance(raw_value, str):
        return "checked_no_raw_value"
    return "checked_match" if raw_value in str(context.get("text") or "") else "checked_mismatch"


def _candidate_key(row: dict[str, Any]) -> tuple[str, int]:
    return (str(row["edge"]["edge_id"]), int(row["evidence_index"]))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
