"""Narrow adapters from collected source sidecars to EviTRAIL handoff records.

The public seam deliberately emits source-neutral Event, indicator, claim, and
rejection rows.  It does not change the five-node graph model and never writes
or mutates a collected source record.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit


@dataclass(frozen=True)
class AlignedSourceRecord:
    """One report-like source record aligned to the current handoff contract."""

    event: dict[str, Any] | None
    indicators: tuple[dict[str, Any], ...] = ()
    claims: tuple[dict[str, Any], ...] = ()
    rejections: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class JsonlEvidence:
    """One decoded JSONL record or an explicit parse rejection."""

    record: dict[str, Any] | None
    rejection: dict[str, Any] | None


def iter_jsonl_evidence(path: Path, *, source: str) -> Iterator[JsonlEvidence]:
    """Read JSONL without silently discarding malformed source evidence."""

    source_path = Path(path)
    with source_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                yield JsonlEvidence(
                    record=None,
                    rejection={
                        "source": source,
                        "raw_ref": str(source_path),
                        "record_path": f"line[{line_number}]",
                        "reason": "invalid_json",
                        "raw_type": "jsonl",
                    },
                )
                continue
            if not isinstance(value, dict):
                yield JsonlEvidence(
                    record=None,
                    rejection={
                        "source": source,
                        "raw_ref": str(source_path),
                        "record_path": f"line[{line_number}]",
                        "reason": "non_object_json_record",
                        "raw_type": type(value).__name__,
                    },
                )
                continue
            yield JsonlEvidence(record=value, rejection=None)


def align_source_record(
    source: str,
    record: Mapping[str, Any],
    *,
    ioc_rows: Iterable[Mapping[str, Any]] = (),
    claim_rows: Iterable[Mapping[str, Any]] = (),
) -> AlignedSourceRecord:
    """Align one collected report plus its source-specific evidence sidecars."""

    normalized_source = source.strip().lower().replace("-", "_")
    rows = tuple(ioc_rows)
    claims = tuple(claim_rows)
    if normalized_source == "orkl":
        return _align_orkl(record, rows, claims)
    if normalized_source in {"misp", "circl_misp"}:
        return _align_misp(record, rows, claims)
    if normalized_source == "aptnotes":
        return _align_aptnotes(record, rows, claims)
    if normalized_source == "cisa":
        return _align_cisa(record, rows, claims)
    raise ValueError(f"unsupported source: {source}")


def _align_orkl(
    record: Mapping[str, Any],
    ioc_rows: tuple[Mapping[str, Any], ...],
    claim_rows: tuple[Mapping[str, Any], ...],
) -> AlignedSourceRecord:
    source = "orkl"
    source_record_id = str(
        record.get("source_record_id")
        or str(record.get("report_id") or "").removeprefix("orkl:report:")
    ).strip()
    raw_ref = str(record.get("raw_ref") or "").strip()
    if not source_record_id:
        return AlignedSourceRecord(
            event=None,
            rejections=(
                {
                    "source": source,
                    "raw_ref": raw_ref,
                    "record_path": "record",
                    "reason": "not_report_event",
                    "raw_type": "missing_source_record_id",
                },
            ),
        )

    event_id = f"event:{source}:{source_record_id}"
    event: dict[str, Any] = {
        "event_id": event_id,
        "source": source,
        "source_record_id": source_record_id,
        "title": str(record.get("title") or ""),
        "description": str(record.get("description") or ""),
        "raw_ref": raw_ref,
    }
    rejections: list[dict[str, Any]] = []
    for input_name, output_name in (
        ("created_at", "created"),
        ("modified_at", "modified"),
        ("published_at", "published"),
        ("fetched_at", "fetched_at"),
    ):
        value = record.get(input_name)
        if not value:
            continue
        if _is_invalid_source_timestamp(value):
            rejections.append(
                {
                    "source": source,
                    "event_id": event_id,
                    "raw_ref": raw_ref,
                    "record_path": input_name,
                    "reason": "invalid_source_timestamp",
                    "raw_type": input_name,
                    "raw_value": str(value),
                }
            )
            continue
        event[output_name] = str(value)

    indicators, indicator_rejections = _align_indicators(source, event_id, raw_ref, ioc_rows)
    claims = _align_claims(
        source=source,
        event_id=event_id,
        source_record_id=source_record_id,
        default_raw_ref=raw_ref,
        claim_rows=claim_rows,
        scope="report_context",
        usage="provenance_only",
    )
    rejections.extend(indicator_rejections)
    return AlignedSourceRecord(
        event=event,
        indicators=tuple(indicators),
        claims=tuple(claims),
        rejections=tuple(rejections),
    )


def _align_misp(
    record: Mapping[str, Any],
    ioc_rows: tuple[Mapping[str, Any], ...],
    claim_rows: tuple[Mapping[str, Any], ...],
) -> AlignedSourceRecord:
    source = "circl_misp"
    source_record_id = str(
        record.get("source_uuid")
        or record.get("uuid")
        or str(record.get("event_id") or "").removeprefix("circl-misp:event:")
    ).strip()
    raw_ref = str(record.get("raw_ref") or "").strip()
    if not source_record_id:
        return _not_report_event(source, raw_ref, "missing_source_uuid")

    event_id = f"event:{source}:{source_record_id}"
    event: dict[str, Any] = {
        "event_id": event_id,
        "source": source,
        "source_record_id": source_record_id,
        "title": str(record.get("title") or record.get("info") or ""),
        "description": str(record.get("description") or ""),
        "raw_ref": raw_ref,
    }
    rejections: list[dict[str, Any]] = []
    for input_name, output_name in (
        ("event_date", "event_time"),
        ("modified_at", "modified"),
        ("published_at", "published"),
        ("fetched_at", "fetched_at"),
    ):
        value = record.get(input_name)
        if not value:
            continue
        if _is_invalid_source_timestamp(value):
            rejections.append(_timestamp_rejection(source, event_id, raw_ref, input_name, value))
            continue
        event[output_name] = str(value)

    indicators, indicator_rejections = _align_indicators(source, event_id, raw_ref, ioc_rows)
    claims = _align_claims(
        source=source,
        event_id=event_id,
        source_record_id=source_record_id,
        default_raw_ref=raw_ref,
        claim_rows=claim_rows,
        scope="attribution",
        usage="candidate",
    )
    rejections.extend(indicator_rejections)
    return AlignedSourceRecord(
        event=event,
        indicators=tuple(indicators),
        claims=tuple(claims),
        rejections=tuple(rejections),
    )


def _align_aptnotes(
    record: Mapping[str, Any],
    ioc_rows: tuple[Mapping[str, Any], ...],
    claim_rows: tuple[Mapping[str, Any], ...],
) -> AlignedSourceRecord:
    source = "aptnotes"
    source_record_id = str(record.get("report_id") or "").strip()
    raw_ref = str(record.get("raw_metadata_ref") or record.get("raw_ref") or "").strip()
    if not source_record_id:
        return _not_report_event(source, raw_ref, "missing_report_id")

    event_id = f"event:{source}:{source_record_id}"
    event: dict[str, Any] = {
        "event_id": event_id,
        "source": source,
        "source_record_id": source_record_id,
        "title": str(record.get("title") or ""),
        "description": str(record.get("description") or ""),
        "raw_ref": raw_ref,
    }
    listed_date = _normalize_aptnotes_date(record.get("listed_date"))
    if listed_date:
        event["published"] = listed_date
    if record.get("fetched_at"):
        event["fetched_at"] = str(record["fetched_at"])
    if record.get("publisher"):
        event["publisher"] = str(record["publisher"])
    references = [
        str(value)
        for value in (
            record.get("references")
            if isinstance(record.get("references"), list)
            else [record.get("original_url")]
        )
        if value
    ]
    if references:
        event["references"] = references

    indicators, rejections = _align_indicators(source, event_id, raw_ref, ioc_rows)
    claims = _align_claims(
        source=source,
        event_id=event_id,
        source_record_id=source_record_id,
        default_raw_ref=raw_ref,
        claim_rows=claim_rows,
        scope="report_context",
        usage="provenance_only",
    )
    return AlignedSourceRecord(
        event=event,
        indicators=tuple(indicators),
        claims=tuple(claims),
        rejections=tuple(rejections),
    )


def _align_cisa(
    record: Mapping[str, Any],
    ioc_rows: tuple[Mapping[str, Any], ...],
    claim_rows: tuple[Mapping[str, Any], ...],
) -> AlignedSourceRecord:
    source = "cisa"
    raw_ref = str(
        record.get("raw_html_ref") or record.get("raw_ref") or record.get("source_url") or ""
    ).strip()
    if (
        not str(record.get("normalization_version") or "").startswith("cisa-")
        or not record.get("raw_html_ref")
        or not record.get("title")
    ):
        return _not_report_event(source, raw_ref, "cisa_attachment_or_non_advisory")

    source_record_id = str(record.get("report_id") or record.get("source_record_id") or "").strip()
    if not source_record_id:
        return _not_report_event(source, raw_ref, "missing_report_id")
    event_id = f"event:{source}:{source_record_id}"
    event: dict[str, Any] = {
        "event_id": event_id,
        "source": source,
        "source_record_id": source_record_id,
        "title": str(record.get("title") or ""),
        "description": str(record.get("summary") or record.get("description") or ""),
        "raw_ref": raw_ref,
    }
    for input_name, output_name in (
        ("published_at", "published"),
        ("updated_at", "modified"),
        ("fetched_at", "fetched_at"),
    ):
        if record.get(input_name):
            event[output_name] = str(record[input_name])
    if record.get("issuing_organizations"):
        event["issuing_organizations"] = list(record["issuing_organizations"])
    references = [str(value) for value in (record.get("reference_urls") or []) if value]
    if references:
        event["references"] = references

    indicators, rejections = _align_indicators(source, event_id, raw_ref, ioc_rows)
    claims = _align_claims(
        source=source,
        event_id=event_id,
        source_record_id=source_record_id,
        default_raw_ref=raw_ref,
        claim_rows=claim_rows,
        scope="report_context",
        usage="provenance_only",
    )
    return AlignedSourceRecord(
        event=event,
        indicators=tuple(indicators),
        claims=tuple(claims),
        rejections=tuple(rejections),
    )


def _align_indicators(
    source: str,
    event_id: str,
    default_raw_ref: str,
    rows: tuple[Mapping[str, Any], ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indicators: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        raw_type = str(row.get("ioc_type") or row.get("type") or "")
        raw_value = str(row.get("ioc_value_raw") or row.get("ioc_value") or row.get("value") or "")
        normalized = _normalize_indicator(
            raw_type, row.get("ioc_value") or row.get("value") or raw_value
        )
        raw_ref = str(row.get("raw_ref") or default_raw_ref)
        record_path = str(
            row.get("source_field")
            or row.get("record_path")
            or _character_path(row)
            or f"ioc_evidence[{index}]"
        )
        if normalized is None:
            rejections.append(
                {
                    "source": source,
                    "event_id": event_id,
                    "raw_ref": raw_ref,
                    "record_path": record_path,
                    "reason": "unsupported_or_invalid_indicator",
                    "raw_type": raw_type,
                    "raw_value": raw_value,
                }
            )
            continue
        node_type, value = normalized
        indicator = {
            "type": node_type,
            "value": value,
            "raw_value": raw_value,
            "raw_ref": raw_ref,
            "record_path": record_path,
            "derivation": str(
                row.get("extraction_method") or row.get("derivation") or "source_asserted"
            ),
        }
        timestamps = {
            key: str(row[key]) for key in ("first_seen", "last_seen", "observed_at") if row.get(key)
        }
        if timestamps:
            indicator["timestamps"] = timestamps
        indicators.append(indicator)
    return indicators, rejections


def _align_claims(
    *,
    source: str,
    event_id: str,
    source_record_id: str,
    default_raw_ref: str,
    claim_rows: tuple[Mapping[str, Any], ...],
    scope: str | None,
    usage: str | None,
) -> list[dict[str, Any]]:
    prepared: list[tuple[Mapping[str, Any], str, str]] = []
    for index, row in enumerate(claim_rows):
        raw_value = str(
            row.get("raw_label") or row.get("raw_actor_text") or row.get("raw_value") or ""
        ).strip()
        if not raw_value:
            continue
        source_field = str(
            row.get("source_location")
            or row.get("source_field")
            or row.get("record_path")
            or _character_path(row)
            or (f"section[{row['section_heading']}]" if row.get("section_heading") else "")
            or f"actor_claim[{index}]"
        )
        prepared.append((row, raw_value, source_field))
    set_semantics = "set" if len(prepared) > 1 else "singleton"
    claims: list[dict[str, Any]] = []
    for row, raw_value, source_field in prepared:
        raw_ref = str(row.get("raw_ref") or default_raw_ref)
        row_scope = scope
        row_usage = usage
        if row_scope is None or row_usage is None:
            is_explicit = row.get("extraction_method") == "explicit_pattern"
            row_scope = "attribution" if is_explicit else "report_context"
            row_usage = "candidate" if is_explicit else "provenance_only"
        claim = {
            "claim_id": _claim_id(event_id, source, raw_value, source_field),
            "event_id": event_id,
            "source": source,
            "source_record_id": source_record_id,
            "raw_value": raw_value,
            "raw_ref": raw_ref,
            "source_field": source_field,
            "claim_scope": row_scope,
            "set_semantics": set_semantics,
            "usage": row_usage,
        }
        properties = {
            key: row[key]
            for key in (
                "claim_excerpt",
                "claim_kind",
                "claim_modality",
                "extraction_method",
                "parse_status",
                "resolution_status",
                "section_heading",
            )
            if row.get(key) not in (None, "", [], {})
        }
        if properties:
            claim["properties"] = properties
        claims.append(claim)
    return claims


def _normalize_indicator(raw_type: str, value: Any) -> tuple[str, str] | None:
    text = _defang(str(value or "")).strip()
    kind = raw_type.strip().lower().replace("_", "-")
    if kind in {"domain", "hostname", "fqdn", "domain-name"}:
        domain = _normalize_domain(text)
        return ("domain", domain) if domain else None
    if kind in {"ip", "ipv4", "ipv6", "ip-src", "ip-dst"}:
        try:
            return "ip", ipaddress.ip_address(text).compressed.lower()
        except ValueError:
            return None
    if kind in {"asn", "as"}:
        match = re.search(r"(?:^|\b)AS\s*(\d+)(?:\b|$)", text, re.IGNORECASE)
        if match:
            return "asn", str(int(match.group(1)))
        if text.isdigit():
            return "asn", str(int(text))
        return None
    if kind in {"url", "uri", "link"}:
        normalized_url = _normalize_url(text)
        return ("url", normalized_url) if normalized_url else None
    return None


def _defang(value: str) -> str:
    text = value.strip()
    for pattern, replacement in (
        (r"(?i)^hxxps://", "https://"),
        (r"(?i)^hxxp://", "http://"),
        (r"\[\.\]|\(\.\)", "."),
        (r"\[:\]", ":"),
    ):
        text = re.sub(pattern, replacement, text)
    return text


def _normalize_domain(value: str) -> str | None:
    text = _defang(value).strip().rstrip(".").lower()
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
        or re.fullmatch(r"[a-z0-9-]+", label) is None
        for label in labels
    ):
        return None
    return text


def _normalize_url(value: str) -> str | None:
    text = _defang(value).strip()
    if not text:
        return None
    if "://" not in text:
        if "/" not in text:
            return None
        text = "http://" + text
    try:
        parsed = urlsplit(text)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        try:
            host_ip = ipaddress.ip_address(parsed.hostname).compressed.lower()
        except ValueError:
            host_ip = ""
        host = host_ip or _normalize_domain(parsed.hostname)
        if not host:
            return None
        scheme = parsed.scheme.lower()
        port = parsed.port
        default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
        userinfo = ""
        if parsed.username:
            userinfo = quote(unquote(parsed.username), safe="")
            if parsed.password:
                userinfo += ":" + quote(unquote(parsed.password), safe="")
            userinfo += "@"
        bracketed_host = f"[{host}]" if ":" in host else host
        netloc = userinfo + bracketed_host
        if port and not default_port:
            netloc += f":{port}"
        return urlunsplit((scheme, netloc, parsed.path or "", parsed.query or "", ""))
    except (ValueError, UnicodeError):
        return None


def _claim_id(event_id: str, source: str, raw_value: str, source_field: str) -> str:
    payload = json.dumps(
        (event_id, source, raw_value, source_field),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"claim:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _is_invalid_source_timestamp(value: Any) -> bool:
    text = str(value).strip()
    return text.startswith(("0000-", "0001-"))


def _not_report_event(source: str, raw_ref: str, raw_type: str) -> AlignedSourceRecord:
    return AlignedSourceRecord(
        event=None,
        rejections=(
            {
                "source": source,
                "raw_ref": raw_ref,
                "record_path": "record",
                "reason": "not_report_event",
                "raw_type": raw_type,
            },
        ),
    )


def _timestamp_rejection(
    source: str,
    event_id: str,
    raw_ref: str,
    field: str,
    value: Any,
) -> dict[str, Any]:
    return {
        "source": source,
        "event_id": event_id,
        "raw_ref": raw_ref,
        "record_path": field,
        "reason": "invalid_source_timestamp",
        "raw_type": field,
        "raw_value": str(value),
    }


def _normalize_aptnotes_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    for date_format in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _character_path(row: Mapping[str, Any]) -> str:
    start = row.get("character_start")
    end = row.get("character_end")
    if start is None and end is None:
        return ""
    return f"characters[{'' if start is None else start}:{'' if end is None else end}]"
