"""Read-only OTX-to-TRAIL adapter, audit, and inference client.

The script never writes beneath ``--raw-root``. All derived requests, audit
records, predictions, failures, and logs are written beneath ``--output-dir``.
It does not import or invoke any OTX collector or model training entry point.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import urlsplit

MODEL_NAME = "TRAIL paper baseline 2-layer GraphSAGE"
CHECKPOINT = "gnn_train-0.777_max_lprop+feats+ae-new-data.pt"
TYPE_MAPPING = {
    "domain": "domain",
    "hostname": "domain",
    "ipv4": "ip",
    "ipv6": "ip",
    "ip": "ip",
    "url": "url",
    "uri": "url",
}
TYPE_MAPPING_EVIDENCE = {
    "domain": "OTX native domain type; accepted by TRAIL /attribute",
    "hostname": "OTX hostname values are DNS host names; accepted as TRAIL domain",
    "IPv4": "OTX explicit IPv4 type; accepted as TRAIL ip",
    "IPv6": "OTX explicit IPv6 type; accepted as TRAIL ip",
    "ip": "Generic explicit IP type, validated with ipaddress before use",
    "URL": "OTX native URL type; accepted as TRAIL url",
    "url": "Case variant of explicit URL type",
    "URI": "Mapped only when the value is an absolute HTTP(S) URL",
}
REQUIRED_RESPONSE_FIELDS = {
    "status",
    "predicted_apt",
    "confidence",
    "scores",
    "iocs_processed",
    "matched_existing_in_graph",
    "newly_enriched",
    "temp_event_node_id",
}
_DOMAIN_LABEL = re.compile(r"^(?!-)[A-Za-z0-9_-]{1,63}(?<!-)$")
_FETCHED_AT = re.compile(r'"fetched_at"\s*:\s*"([^"]+)"')


class Discovery(NamedTuple):
    selected: dict[str, Path]
    files_by_event: dict[str, list[Path]]
    raw_file_count: int
    duplicate_event_id_count: int


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def _append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(_json_dump(value) + "\n")


def _domain_is_valid(value: str) -> bool:
    candidate = value[:-1] if value.endswith(".") else value
    if len(candidate) > 253 or "." not in candidate:
        return False
    try:
        ascii_name = candidate.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    if _looks_like_ip(ascii_name):
        return False
    return all(_DOMAIN_LABEL.fullmatch(label) for label in ascii_name.split("."))


def _looks_like_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _url_is_valid(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)
    except ValueError:
        return False


def adapt_ioc(raw_type: Any, raw_value: Any) -> tuple[str, str] | None:
    """Map only explicit supported OTX types and validate without guessing."""
    if not isinstance(raw_type, str) or not isinstance(raw_value, str):
        return None
    value = raw_value.strip()
    mapped = TYPE_MAPPING.get(raw_type.strip().casefold())
    if not mapped or not value:
        return None
    valid = (
        _domain_is_valid(value)
        if mapped == "domain"
        else _looks_like_ip(value)
        if mapped == "ip"
        else _url_is_valid(value)
    )
    return (mapped, value) if valid else None


def _source_attribution(event: dict[str, Any]) -> dict[str, Any] | None:
    attribution = {
        key: event[key]
        for key in ("adversary", "groups")
        if event.get(key) not in (None, "", [], {})
    }
    return attribution or None


def _inspect_event(
    event: dict[str, Any], source_file: Path
) -> tuple[dict[str, Any], dict[str, Any], Counter[str], Counter[str]]:
    indicators = event.get("indicators")
    raw_indicators = indicators if isinstance(indicators, list) else []
    unsupported: Counter[str] = Counter()
    invalid: Counter[str] = Counter()
    adapted: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    supported_valid_count = 0
    empty_value_count = 0

    for raw_ioc in raw_indicators:
        if not isinstance(raw_ioc, dict):
            invalid["non_object_indicator"] += 1
            continue
        raw_type = raw_ioc.get("type")
        raw_value = raw_ioc.get("indicator")
        type_key = raw_type.strip().casefold() if isinstance(raw_type, str) else ""
        if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
            empty_value_count += 1
            invalid[str(raw_type) if raw_type is not None else "<missing_type>"] += 1
            continue
        if type_key not in TYPE_MAPPING:
            unsupported[str(raw_type) if raw_type is not None else "<missing_type>"] += 1
            continue
        mapped = adapt_ioc(raw_type, raw_value)
        if mapped is None:
            invalid[str(raw_type)] += 1
            continue
        supported_valid_count += 1
        canonical = (mapped[0], mapped[1].casefold() if mapped[0] != "url" else mapped[1])
        if canonical in seen:
            continue
        seen.add(canonical)
        adapted.append({"type": mapped[0], "value": mapped[1]})

    type_counts = Counter(ioc["type"] for ioc in adapted)
    row = {
        "event_id": str(event.get("id", "")),
        "source_file": str(source_file.absolute()),
        "source_attribution": _source_attribution(event),
        "source_attribution_used_as_model_input": False,
        "raw_ioc_count": len(raw_indicators),
        "supported_ioc_count": supported_valid_count,
        "deduplicated_ioc_count": len(adapted),
        "event_internal_duplicate_ioc_count": supported_valid_count - len(adapted),
        "ioc_type_counts": {key: type_counts.get(key, 0) for key in ("domain", "ip", "url")},
        "empty_value_count": empty_value_count,
        "invalid_format_count": sum(invalid.values()),
        "unsupported_ioc_count": sum(unsupported.values()),
    }
    return row, {"iocs": adapted}, unsupported, invalid


def adapt_event(event: dict[str, Any], source_file: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    row, request, _unsupported, _invalid = _inspect_event(event, source_file)
    return row, request


def _peek_fetched_at(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            prefix = handle.read(8192)
        match = _FETCHED_AT.search(prefix)
        return match.group(1) if match else ""
    except OSError:
        return ""


def discover_snapshots(raw_root: Path) -> Discovery:
    """Discover all JSON snapshots and select the newest wrapped version per ID."""
    files = sorted(raw_root.rglob("*.json"))
    files_by_event: dict[str, list[Path]] = {}
    ranked: dict[str, tuple[tuple[int, str, str], Path]] = {}
    for path in files:
        is_wrapped = path.parent != raw_root
        event_id = path.parent.name if is_wrapped else path.stem
        fetched_at = _peek_fetched_at(path) if is_wrapped else ""
        rank = (1 if is_wrapped else 0, fetched_at, str(path))
        files_by_event.setdefault(event_id, []).append(path)
        if event_id not in ranked or rank > ranked[event_id][0]:
            ranked[event_id] = (rank, path)
    selected = {event_id: value[1] for event_id, value in ranked.items()}
    return Discovery(
        selected=selected,
        files_by_event=files_by_event,
        raw_file_count=len(files),
        duplicate_event_id_count=sum(len(paths) > 1 for paths in files_by_event.values()),
    )


def _tree_fingerprint(raw_root: Path) -> dict[str, Any]:
    rows = []
    total_bytes = 0
    for path in sorted(raw_root.rglob("*.json")):
        stat = path.stat()
        total_bytes += stat.st_size
        rows.append(f"{path.relative_to(raw_root)}\0{stat.st_size}\0{stat.st_mtime_ns}")
    digest = hashlib.sha256("\n".join(rows).encode()).hexdigest()
    return {"file_count": len(rows), "total_bytes": total_bytes, "metadata_sha256": digest}


def audit(raw_root: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)
    for name in (
        "eligible_events.jsonl",
        "skipped_events.jsonl",
        "predictions.jsonl",
        "failures.jsonl",
    ):
        (output_dir / name).write_text("", encoding="utf-8")

    started = time.perf_counter()
    before = _tree_fingerprint(raw_root)
    discovery = discover_snapshots(raw_root)
    selected_paths = set(discovery.selected.values())
    duplicate_event_ids = {
        event_id for event_id, paths in discovery.files_by_event.items() if len(paths) > 1
    }
    parse_success = 0
    parse_failures = 0
    stable_id_count = 0
    events_with_iocs = 0
    eligible_count = 0
    skipped_count = 0
    type_counts: Counter[str] = Counter()
    unsupported_types: Counter[str] = Counter()
    invalid_types: Counter[str] = Counter()
    empty_values = 0
    invalid_formats = 0
    internal_duplicates = 0
    cross_event_counts: Counter[bytes] = Counter()
    duplicate_versions_changed = 0
    payload_hashes: dict[str, set[str]] = {}
    skip_reasons: Counter[str] = Counter()
    schema_counts: Counter[str] = Counter()

    for path in sorted(raw_root.rglob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            parse_success += 1
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            parse_failures += 1
            event_id = path.parent.name if path.parent != raw_root else path.stem
            if path in selected_paths:
                skipped_count += 1
                skip_reasons["parse_failure"] += 1
                _append_jsonl(
                    output_dir / "skipped_events.jsonl",
                    {
                        "event_id": event_id,
                        "source_file": str(path.absolute()),
                        "reasons": ["parse_failure"],
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
            continue
        if not isinstance(raw, dict):
            schema_counts["non_object"] += 1
            continue
        wrapped = isinstance(raw.get("payload"), dict)
        schema_counts["wrapped_payload"] += int(wrapped)
        schema_counts["plain_pulse"] += int(not wrapped)
        event = raw["payload"] if wrapped else raw
        event_id = str(event.get("id", "")) if isinstance(event, dict) else ""
        if event_id in duplicate_event_ids:
            payload_hashes.setdefault(event_id, set()).add(
                hashlib.sha256(_json_dump(event).encode()).hexdigest()
            )
        if path not in selected_paths:
            continue
        reasons: list[str] = []
        expected_id = path.parent.name if path.parent != raw_root else path.stem
        if not isinstance(event, dict):
            reasons.append("event_not_object")
        elif not event_id or event_id != expected_id:
            reasons.append("missing_or_unstable_event_id")
        else:
            stable_id_count += 1
        indicators = event.get("indicators") if isinstance(event, dict) else None
        if not isinstance(indicators, list):
            reasons.append("missing_or_non_list_indicators")
        elif indicators:
            events_with_iocs += 1
        else:
            reasons.append("no_iocs")

        if isinstance(event, dict):
            row, request, unsupported, invalid = _inspect_event(event, path)
            unsupported_types.update(unsupported)
            invalid_types.update(invalid)
            empty_values += row["empty_value_count"]
            invalid_formats += row["invalid_format_count"] - row["empty_value_count"]
            internal_duplicates += row["event_internal_duplicate_ioc_count"]
            type_counts.update(row["ioc_type_counts"])
            if not request["iocs"]:
                reasons.append("no_valid_supported_iocs")
        else:
            row, request = {}, {"iocs": []}

        if reasons:
            skipped_count += 1
            unique_reasons = list(dict.fromkeys(reasons))
            skip_reasons.update(unique_reasons)
            _append_jsonl(
                output_dir / "skipped_events.jsonl",
                {
                    "event_id": event_id or expected_id,
                    "source_file": str(path.absolute()),
                    "reasons": unique_reasons,
                    **row,
                },
            )
            continue

        eligible_count += 1
        for ioc in request["iocs"]:
            value = ioc["value"] if ioc["type"] == "url" else ioc["value"].casefold()
            identity = f"{ioc['type']}\0{value}".encode()
            cross_event_counts[hashlib.sha256(identity).digest()] += 1
        _append_jsonl(output_dir / "eligible_events.jsonl", {**row, "adapter_request": request})

    duplicate_versions_changed = sum(len(hashes) > 1 for hashes in payload_hashes.values())
    after = _tree_fingerprint(raw_root)
    audit_result = {
        "generated_at": utc_now(),
        "raw_root": str(raw_root.absolute()),
        "schema": {
            "file_organization": "one OTX Pulse/Event per JSON snapshot",
            "event_path": "payload (wrapped RawStore JSON) or root (legacy plain JSON)",
            "event_id_path": "payload.id or id",
            "wrapper_id_path": "source_id",
            "ioc_list_path": "payload.indicators[] or indicators[]",
            "ioc_type_path": "indicators[].type",
            "ioc_value_path": "indicators[].indicator",
            "source_attribution_paths": ["adversary", "groups"],
            "collection_status_fields_found": [],
            "canonical_snapshot_rule": "newest wrapped fetched_at per Event ID; legacy plain file is audit-only",
        },
        "counts": {
            "raw_file_count": discovery.raw_file_count,
            "parsed_file_count": parse_success,
            "parse_failed_file_count": parse_failures,
            "event_count": len(discovery.selected),
            "stable_event_id_count": stable_id_count,
            "events_with_iocs": events_with_iocs,
            "events_with_supported_iocs": eligible_count,
            "events_without_supported_iocs": skipped_count,
            "eligible_event_count": eligible_count,
            "skipped_event_count": skipped_count,
            "domain_count_after_event_dedup": type_counts["domain"],
            "ip_count_after_event_dedup": type_counts["ip"],
            "url_count_after_event_dedup": type_counts["url"],
            "unsupported_ioc_count": sum(unsupported_types.values()),
            "empty_value_count": empty_values,
            "invalid_format_count": invalid_formats,
            "duplicate_event_id_count": discovery.duplicate_event_id_count,
            "duplicate_snapshot_excess_count": sum(
                len(paths) - 1 for paths in discovery.files_by_event.values()
            ),
            "duplicate_event_ids_with_changed_payload": duplicate_versions_changed,
            "event_internal_duplicate_supported_ioc_count": internal_duplicates,
            "cross_event_duplicate_distinct_ioc_count": sum(
                count > 1 for count in cross_event_counts.values()
            ),
            "cross_event_duplicate_ioc_excess_count": sum(
                count - 1 for count in cross_event_counts.values() if count > 1
            ),
        },
        "unsupported_ioc_type_distribution": dict(unsupported_types.most_common()),
        "invalid_supported_type_distribution": dict(invalid_types.most_common()),
        "skip_reason_distribution": dict(skip_reasons.most_common()),
        "schema_distribution": dict(schema_counts),
        "raw_integrity": {
            "before": before,
            "after": after,
            "unchanged": before == after,
            "basis": "relative path + byte size + mtime_ns for every JSON file",
        },
        "elapsed_seconds": time.perf_counter() - started,
    }
    mapping = {
        "accepted_output_types": ["domain", "ip", "url"],
        "mapping": TYPE_MAPPING_EVIDENCE,
        "unsupported_policy": "Do not map; record by original OTX type",
        "validation": {
            "domain": "IDNA DNS name, at least two labels, not an IP literal",
            "ip": "Python ipaddress IPv4 or IPv6 literal",
            "url": "absolute HTTP(S) URL with a hostname",
        },
    }
    _write_json(output_dir / "data_audit.json", audit_result)
    _write_json(output_dir / "type_mapping.json", mapping)
    return audit_result


def http_json(
    method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 120.0
) -> dict[str, Any]:
    body = _json_dump(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("response is not a JSON object")
    return result


def verify_status(server_url: str) -> dict[str, Any]:
    status = http_json("GET", f"{server_url.rstrip('/')}/status")
    problems = []
    if status.get("ready") is not True:
        problems.append("service not ready")
    if status.get("ensemble_size") != 1:
        problems.append(f"ensemble_size={status.get('ensemble_size')!r}, expected 1")
    weights = status.get("weights") or []
    if len(weights) != 1 or Path(weights[0]).name != CHECKPOINT:
        problems.append(f"wrong checkpoint list: {weights!r}")
    if not status.get("classes"):
        problems.append("APT class list is empty")
    if not status.get("graph"):
        problems.append("graph path missing")
    if problems:
        raise RuntimeError("; ".join(problems))
    return status


def smoke_plan(eligible_path: Path) -> dict[str, Any]:
    selected: dict[str, tuple[int, dict[str, Any]]] = {}
    largest_safe: tuple[int, dict[str, Any]] | None = None
    largest_overall: tuple[int, dict[str, Any]] | None = None
    with eligible_path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            row = json.loads(line)
            counts = row["ioc_type_counts"]
            nonzero = {key for key, value in counts.items() if value}
            category = (
                "domain_only"
                if nonzero == {"domain"}
                else "ip_only"
                if nonzero == {"ip"}
                else "mixed"
                if nonzero == {"domain", "ip", "url"}
                else None
            )
            if category and (
                category not in selected
                or row["deduplicated_ioc_count"] < selected[category][1]["deduplicated_ioc_count"]
            ):
                selected[category] = (index, row)
            if row["deduplicated_ioc_count"] <= 500 and (
                largest_safe is None
                or row["deduplicated_ioc_count"] > largest_safe[1]["deduplicated_ioc_count"]
            ):
                largest_safe = (index, row)
            if (
                largest_overall is None
                or row["deduplicated_ioc_count"] > largest_overall[1]["deduplicated_ioc_count"]
            ):
                largest_overall = (index, row)
    if largest_safe:
        selected["high_ioc_count"] = largest_safe
    plan = {
        key: {
            "eligible_index": indexed_row[0],
            "event_id": indexed_row[1]["event_id"],
            "source_file": indexed_row[1]["source_file"],
            "deduplicated_ioc_count": indexed_row[1]["deduplicated_ioc_count"],
            "ioc_type_counts": indexed_row[1]["ioc_type_counts"],
        }
        for key, indexed_row in selected.items()
    }
    plan["largest_overall_capacity_observation"] = {
        "eligible_index": largest_overall[0],
        "event_id": largest_overall[1]["event_id"],
        "deduplicated_ioc_count": largest_overall[1]["deduplicated_ioc_count"],
        "ioc_type_counts": largest_overall[1]["ioc_type_counts"],
        "selected_for_smoke": False,
    }
    return plan


def infer(
    eligible_path: Path,
    predictions_path: Path,
    failures_path: Path,
    server_url: str,
    start_index: int,
    limit: int | None,
    phase: str,
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    status_before = verify_status(server_url)
    succeeded = failed = attempted = 0
    elapsed_values: list[float] = []
    with eligible_path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if index < start_index:
                continue
            if limit is not None and attempted >= limit:
                break
            row = json.loads(line)
            request_payload = row["adapter_request"]
            attempted += 1
            started = time.perf_counter()
            last_error: Exception | None = None
            response: dict[str, Any] | None = None
            retry_count = 0
            for attempt_index in range(retries + 1):
                retry_count = attempt_index
                try:
                    response = http_json(
                        "POST",
                        f"{server_url.rstrip('/')}/attribute",
                        request_payload,
                        timeout,
                    )
                    missing = REQUIRED_RESPONSE_FIELDS - response.keys()
                    if missing:
                        raise RuntimeError(f"response missing fields: {sorted(missing)}")
                    if response["status"] != "success":
                        raise RuntimeError(f"response status={response['status']!r}")
                    if response["iocs_processed"] != row["deduplicated_ioc_count"]:
                        raise RuntimeError("server iocs_processed does not match adapter request")
                    break
                except Exception as exc:  # recorded with stage and bounded retries
                    last_error = exc
                    response = None
            elapsed = time.perf_counter() - started
            elapsed_values.append(elapsed)
            if response is None:
                failed += 1
                _append_jsonl(
                    failures_path,
                    {
                        "event_id": row["event_id"],
                        "source_file": row["source_file"],
                        "stage": "request",
                        "error_type": type(last_error).__name__ if last_error else "UnknownError",
                        "error_message": str(last_error),
                        "retry_count": retry_count,
                        "phase": phase,
                    },
                )
                continue
            succeeded += 1
            _append_jsonl(
                predictions_path,
                {
                    **{
                        key: row[key]
                        for key in (
                            "event_id",
                            "source_file",
                            "source_attribution",
                            "raw_ioc_count",
                            "supported_ioc_count",
                            "deduplicated_ioc_count",
                            "ioc_type_counts",
                        )
                    },
                    "predicted_apt": response["predicted_apt"],
                    "confidence": response["confidence"],
                    "scores": response["scores"],
                    "matched_existing_in_graph": response["matched_existing_in_graph"],
                    "newly_enriched": response["newly_enriched"],
                    "temp_event_node_id": response["temp_event_node_id"],
                    "iocs_processed": response["iocs_processed"],
                    "model": {"name": MODEL_NAME, "checkpoint": CHECKPOINT},
                    "status": "success",
                    "phase": phase,
                    "elapsed_seconds": elapsed,
                    "source_attribution_used_as_model_input": False,
                },
            )
    status_after = verify_status(server_url)
    return {
        "phase": phase,
        "started_at_index": start_index,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "elapsed_seconds_total": sum(elapsed_values),
        "elapsed_seconds_mean": sum(elapsed_values) / len(elapsed_values)
        if elapsed_values
        else 0.0,
        "elapsed_seconds_max": max(elapsed_values, default=0.0),
        "graph_nodes_before": status_before.get("graph_nodes"),
        "graph_nodes_after": status_after.get("graph_nodes"),
        "graph_node_growth": status_after.get("graph_nodes", 0)
        - status_before.get("graph_nodes", 0),
        "service_status": status_after,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--raw-root", type=Path, required=True)
    audit_parser.add_argument("--output-dir", type=Path, required=True)
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--server-url", default="http://127.0.0.1:47823")
    sanity_parser = sub.add_parser("predict-event")
    sanity_parser.add_argument("--server-url", default="http://127.0.0.1:47823")
    sanity_parser.add_argument("--event-id", type=int, required=True)
    smoke_parser = sub.add_parser("smoke-plan")
    smoke_parser.add_argument("--eligible", type=Path, required=True)
    infer_parser = sub.add_parser("infer")
    infer_parser.add_argument("--eligible", type=Path, required=True)
    infer_parser.add_argument("--predictions", type=Path, required=True)
    infer_parser.add_argument("--failures", type=Path, required=True)
    infer_parser.add_argument("--server-url", default="http://127.0.0.1:47823")
    infer_parser.add_argument("--start-index", type=int, default=0)
    infer_parser.add_argument("--limit", type=int)
    infer_parser.add_argument("--phase", required=True)
    infer_parser.add_argument("--timeout", type=float, default=300.0)
    infer_parser.add_argument("--retries", type=int, default=1)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "audit":
        result = audit(args.raw_root, args.output_dir)
    elif args.command == "status":
        result = verify_status(args.server_url)
    elif args.command == "predict-event":
        verify_status(args.server_url)
        result = http_json(
            "POST", f"{args.server_url.rstrip('/')}/predict_event", {"event_id": args.event_id}
        )
    elif args.command == "smoke-plan":
        result = smoke_plan(args.eligible)
    else:
        result = infer(
            args.eligible,
            args.predictions,
            args.failures,
            args.server_url,
            args.start_index,
            args.limit,
            args.phase,
            args.timeout,
            args.retries,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
