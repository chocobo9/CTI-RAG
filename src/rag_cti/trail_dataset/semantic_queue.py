"""Deterministic stratified human-confirmation queues over internal lineage records."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HIGH_RISK_WORDS = re.compile(r"(?i)\b(example|sample|reference|citation|bibliography|retrieved|accessed|published|not\s+malicious|benign)\b")


def build_semantic_review_queue(lineage_dir: Path, output_dir: Path, *, repository_root: Path, per_stratum: int = 5) -> dict[str, Any]:
    lineage_dir, output_dir, repository_root = Path(lineage_dir), Path(output_dir), Path(repository_root)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    if per_stratum < 1:
        raise ValueError("per_stratum must be positive")
    records = _jsonl(lineage_dir / "lineage_records.jsonl")
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[(record["source"], record["relation"], record["ioc_type"], record["evidence_class"])].append(record)
    packets: list[dict[str, Any]] = []
    for key, rows in sorted(groups.items()):
        for ordinal, row in enumerate(sorted(rows, key=lambda value: value["lineage_id"])[:per_stratum], 1):
            packets.append(_packet(row, key, ordinal, repository_root))
    results = [_factual_review_pending_result(packet) for packet in packets]
    output_dir.mkdir(parents=True)
    _write_jsonl(output_dir / "human_confirmation_queue.jsonl", packets)
    _write_jsonl(output_dir / "human_confirmation_results.jsonl", results)
    summary = summarize_semantic_queue(packets, results)
    _write_json(output_dir / "human_confirmation_coverage.json", summary)
    return {"packet_count": len(packets), "reviewed_count": summary["totals"]["reviewed"], "gate_decision": summary["gate_decision"]}


def summarize_semantic_queue(packets: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    result_by_id = {row["queue_id"]: row for row in results}
    grouped: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for packet in packets:
        key = tuple(packet["stratum"][name] for name in ("source", "relation", "ioc_type", "evidence_class"))
        grouped[key][result_by_id.get(packet["queue_id"], {"review_status": "unreviewed"})["review_status"]] += 1
    totals: Counter[str] = Counter()
    rows = []
    for key, counts in sorted(grouped.items()):
        totals.update(counts)
        total = sum(counts.values())
        rows.append({"source": key[0], "relation": key[1], "ioc_type": key[2], "evidence_class": key[3], "total": total, "reviewed": total - counts["unreviewed"], "verified": counts["verified"], "rejected": counts["rejected"], "ambiguous": counts["ambiguous"], "unreviewed": counts["unreviewed"], "coverage_ratio": (total - counts["unreviewed"]) / total, "gate_decision": "pending_factual_audit"})
    total = sum(totals.values())
    return {"format": "trail-five-node-human-confirmation-coverage", "format_version": 1, "scope": "Stratified queue over current-local-input lineage records; no factual, maliciousness, or source-acceptance decision is made.", "rows": rows, "totals": {"total": total, "reviewed": total - totals["unreviewed"], "verified": totals["verified"], "rejected": totals["rejected"], "ambiguous": totals["ambiguous"], "unreviewed": totals["unreviewed"], "coverage_ratio": (total - totals["unreviewed"]) / total if total else 0.0}, "gate_decision": "pending_factual_audit"}


def _packet(record: dict[str, Any], key: tuple[str, str, str, str], ordinal: int, root: Path) -> dict[str, Any]:
    context = _context(record, root)
    priority, risk_reasons = _risk(record, context, root)
    source, relation, ioc_type, evidence_class = key
    return {"queue_id": f"confirmation:{record['lineage_id']}", "stratum": {"source": source, "relation": relation, "ioc_type": ioc_type, "evidence_class": evidence_class}, "sample_ordinal": ordinal, "priority": priority, "risk_reasons": risk_reasons, "graph": {name: record[name] for name in ("edge_id", "source_id", "target_id", "relation")}, "provenance": {name: record.get(name) for name in ("raw_ref", "record_path", "raw_value", "derivation", "extraction_method")}, "context": context, "review_question": _question(evidence_class), "lineage_status": record["lineage_status"], "human_confirmation_status": "unreviewed", "input_snapshot": "current_local_input"}


def _factual_review_pending_result(packet: dict[str, Any]) -> dict[str, Any]:
    return {"queue_id": packet["queue_id"], "review_status": "unreviewed", "reason_code": "factual_review_pending", "reviewer": {"identifier": "stage4-queue-generator", "procedure": "deterministic queue creation only; no factual or semantic decision", "reviewed_at": "2026-07-24T12:00:00-07:00"}}


def _risk(record: dict[str, Any], context: dict[str, Any] | None, root: Path) -> tuple[str, list[str]]:
    reasons: list[str] = []
    source = record["source"]
    if source == "orkl":
        text = str((context or {}).get("text") or "")
        if HIGH_RISK_WORDS.search(text):
            reasons.append("body_near_example_negation_or_citation")
        if "hxxp" in text.lower():
            reasons.append("obfuscated_indicator_text")
    elif record["evidence_class"] == "source_asserted":
        raw = _raw_field(record, root)
        if raw is None:
            reasons.append("structured_field_unavailable")
        elif source == "circl_misp" and (raw.get("to_ids") is False or str(raw.get("category") or "").lower() == "external analysis"):
            reasons.append("misp_external_or_non_detection_context")
        elif source == "otx" and not any(str(raw.get(key) or "").strip() for key in ("description", "content", "title")):
            reasons.append("otx_indicator_has_no_local_context")
    return ("high", reasons) if reasons else ("normal", [])


def _context(record: dict[str, Any], root: Path) -> dict[str, Any] | None:
    if record["source"] != "orkl":
        return None
    match = re.fullmatch(r"body\.char\[(\d+):(\d+)\]", str(record.get("record_path") or ""))
    raw_ref = record.get("raw_ref")
    if not match or not isinstance(raw_ref, dict):
        return None
    try:
        body = json.loads((root / "data/raw/orkl" / raw_ref["raw_path"]).read_text(encoding="utf-8")).get("plain_text")
        if not isinstance(body, str):
            return None
        start, end = (int(value) for value in match.groups())
        return {"start": start, "end": end, "text": body[max(0, start - 180):min(len(body), end + 180)]}
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError):
        return None


def _raw_field(record: dict[str, Any], root: Path) -> dict[str, Any] | None:
    raw_ref, path = record.get("raw_ref"), str(record.get("record_path") or "")
    if not isinstance(raw_ref, str):
        return None
    try:
        raw = json.loads((root / raw_ref).read_text(encoding="utf-8"))
        if record["source"] == "otx":
            match = re.fullmatch(r"indicators\[(\d+)\]", path)
            rows = raw.get("payload", raw).get("indicators") or []
        else:
            match = re.fullmatch(r"Event\.Attribute\[(\d+)\]", path)
            rows = raw.get("Event", raw).get("Attribute") or []
        return rows[int(match.group(1))] if match and int(match.group(1)) < len(rows) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _question(evidence_class: str) -> str:
    if evidence_class == "source_asserted":
        return "Does the cited local structured field explicitly provide this exact observation, without extending it to maliciousness or attribution?"
    if evidence_class == "body_mentioned":
        return "Does the cited local context support only an exact mention, and is it free of citation/example/negation ambiguity?"
    return "Does the cited traceable input support this exact deterministic transform, without claiming an independent source relationship?"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
