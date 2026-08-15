"""Extract source-backed metadata for attributed frozen Events.

The extractor is intentionally dataset-first.  The frozen handoff files define
the Event population and attribution eligibility; source raw records are read
only when they can add explicit metadata that is not already present in the
handoff.  No network access or document download is performed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from rag_cti.ioc_normalization import URL_TOKEN_RE, normalize_url


EXPECTED = {
    "otx_dataset": {"events": 4_136, "source_claims": 2_704},
    "additional_sources_dataset": {"events": 19_276, "source_claims": 52_550},
}
FORBIDDEN_COUNTS = {17_454, 10_253, 8_597}
SOURCES = ("otx_dataset", "additional_sources_dataset")

OUTPUT_FIELDS = (
    "event_id",
    "source_name",
    "reference_urls",
    "external_report_ids",
    "cve_ids",
    "cisa_advisory_ids",
    "misp_event_uuids",
    "vendor_case_report_ids",
    "document_sha256",
    "publishing_organizations",
    "publish_dates",
    "first_seen_dates",
    "title",
)
ARRAY_FIELDS = set(OUTPUT_FIELDS) - {"event_id", "source_name", "title"}

URL_RE = URL_TOKEN_RE
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
CISA_RE = re.compile(
    r"\b(?:(?:AA|AR|TA)\d{2}-\d{3}[A-Z]?|ICSA-\d{2}-\d{3}-\d{2}|"
    r"ICSMA-\d{2}-\d{3}-\d{2}|MAR-\d{6,10}-[A-Z0-9]+|"
    r"CSA-\d{2}-\d{3}[A-Z]?|ICS-ALERT-\d{2}-\d{3}-\d{2}[A-Z]?|"
    r"IR-ALERT-[A-Z]-\d{2}-\d{3}-\d{2})\b",
    re.IGNORECASE,
)
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
VENDOR_ID_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+){1,}\b")
ID_CONTEXT_PATTERNS = (
    re.compile(
        r"(?i:\b(?:report|advisory|case|incident|ticket|bulletin|alert|"
        r"reference|tracking)\b)\s*(?i:(?:id|number|no\.?|code))?\s*[:#-]?\s*"
        r"(?P<id>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)"
    ),
    re.compile(
        r"(?i:\banalysis\s+(?:of|on|report))\s+"
        r"(?P<id>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)"
    ),
)
TRAILING_URL_CHARS = ".,;:!?)]}" 

STRUCTURED_EXTERNAL_KEYS = {
    "external_report_id",
    "external_report_ids",
    "external_id",
    "external_ids",
    "report_id",
    "report_ids",
    "report_number",
    "report_numbers",
    "document_id",
    "document_ids",
}
STRUCTURED_VENDOR_KEYS = {
    "vendor_case_id",
    "vendor_case_ids",
    "vendor_report_id",
    "vendor_report_ids",
    "case_id",
    "case_ids",
    "case_number",
    "case_numbers",
    "ticket_id",
    "ticket_ids",
    "incident_id",
    "incident_ids",
}


def _jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}: line {line_number} is not an object")
            yield row


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _key_name(path: str) -> str:
    leaf = path.rsplit(".", 1)[-1]
    # _walk includes list indexes in leaf paths (for example
    # ``external_report_ids[0]``).  The field policy is keyed by the
    # structured key, so retain the path for provenance but normalize the
    # index only for matching.
    leaf = re.sub(r"\[\d+\]$", "", leaf)
    return leaf.casefold().replace("-", "_")


def _walk(obj: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            current = f"{path}.{key}" if path else str(key)
            yield current, value
            yield from _walk(value, current)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            current = f"{path}[{index}]"
            yield current, value
            yield from _walk(value, current)


def _flatten_text(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        if value.strip():
            yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _flatten_text(item)
    elif isinstance(value, list):
        for item in value:
            yield from _flatten_text(item)


def _strip_url(value: str) -> str:
    return value.strip().rstrip(TRAILING_URL_CHARS)


def _valid_url(value: str) -> str | None:
    return normalize_url(_strip_url(value))


def _date_value(value: Any) -> str | None:
    text = _clean(value)
    if not text:
        return None
    if text in {"0", "0.0", "0000-00-00", "0000-00-00T00:00:00"}:
        return None
    if text.startswith("0001-01-01"):
        return None
    if text.isdigit() and len(text) in {10, 13}:
        try:
            seconds = int(text) / (1000 if len(text) == 13 else 1)
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return text


def _portable_raw_ref(source: str, value: Any, raw_root: Path) -> str | None:
    """Return a stable repository-relative reference for a raw source file.

    Raw provenance must not contain a developer-machine path.  Absolute paths
    are accepted only when they resolve beneath the configured raw root; a
    path outside that root is an input error rather than something to silently
    rewrite to an unresolvable reference.
    """
    text = _clean(value)
    if not text:
        return None
    normalized = text.replace("\\", "/")
    candidate = Path(text)
    if candidate.is_absolute():
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(raw_root.resolve())
        except ValueError as exc:
            # Older provenance may point to the same repository's raw store
            # through a different checkout root.  Recover only the stable
            # ``data/raw`` suffix; reject unrelated absolute paths.
            marker = "/data/raw/"
            if marker not in normalized.casefold():
                raise ValueError(f"raw reference is outside raw root: {text}") from exc
            suffix = normalized[normalized.casefold().index(marker) + len(marker):]
            return f"data/raw/{suffix}"
        suffix = relative.as_posix()
    else:
        suffix = normalized.lstrip("./")

    if suffix.startswith("data/raw/"):
        return suffix
    if suffix.startswith("data/deliveries/") and "/data/raw/" in suffix:
        return suffix
    if suffix.startswith(f"{source}/"):
        return f"data/raw/{suffix}"
    if suffix.startswith("raw/"):
        return f"data/raw/{source}/{suffix}"
    return f"data/raw/{source}/{suffix}"


def _add(
    values: dict[str, dict[str, dict[str, Any]]],
    field: str,
    value: Any,
    *,
    layer: str,
    path: str,
    raw_ref: str | None,
    method: str,
) -> None:
    if field not in ARRAY_FIELDS:
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _add(values, field, item, layer=layer, path=path, raw_ref=raw_ref, method=method)
        return
    text = _clean(value)
    if not text:
        return
    if field == "reference_urls":
        text = _valid_url(text) or ""
    elif field in {"publish_dates", "first_seen_dates"}:
        text = _date_value(text) or ""
    elif field == "cve_ids":
        text = text.upper()
    elif field == "cisa_advisory_ids":
        text = text.upper()
    elif field == "misp_event_uuids":
        text = text.lower()
    if not text:
        return
    values[field].setdefault(
        text,
        {
            "value": text,
            "layer": layer,
            "paths": set(),
            "raw_refs": set(),
            "methods": set(),
        },
    )
    entry = values[field][text]
    entry["paths"].add(path)
    if raw_ref:
        entry["raw_refs"].add(raw_ref)
    entry["methods"].add(method)


def _add_regex_values(
    values: dict[str, dict[str, dict[str, Any]]],
    field: str,
    text: str,
    *,
    layer: str,
    path: str,
    raw_ref: str | None,
    method: str,
    pattern: re.Pattern[str],
) -> None:
    for match in pattern.findall(text):
        value = match if isinstance(match, str) else match[0]
        _add(values, field, value, layer=layer, path=path, raw_ref=raw_ref, method=method)


def _record_path(source: str, source_record_id: str, raw_root: Path) -> list[Path]:
    if source == "otx":
        directory = raw_root / "otx" / source_record_id
        return sorted(directory.glob("*.json")) if directory.exists() else []
    if source == "orkl":
        directory = raw_root / "orkl" / "raw" / "reports" / source_record_id
        return sorted(directory.glob("*.json")) if directory.exists() else []
    if source == "circl_misp":
        path = raw_root / "circl_misp" / "raw" / "events" / f"{source_record_id}.json"
        return [path] if path.exists() else []
    return []


def _load_orkl_normalized_index(raw_root: Path) -> dict[str, dict[str, Any]]:
    """Index source-normalized ORKL metadata without downloading documents."""
    path = raw_root / "orkl" / "normalized" / "reports.jsonl"
    if not path.is_file():
        return {}
    index: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            source_record_id = _clean(row.get("source_record_id") or row.get("id"))
            if not source_record_id:
                continue
            index[source_record_id] = {
                "record": row,
                "raw_ref": _portable_raw_ref("orkl", path, raw_root),
                "line_number": line_number,
            }
    return index


def _load_raw(source: str, source_record_id: str, raw_root: Path, retries: int) -> tuple[list[tuple[Path, dict[str, Any]]], list[dict[str, Any]]]:
    paths = _record_path(source, source_record_id, raw_root)
    if not paths:
        return [], [{"kind": "raw_record_missing", "source": source, "source_record_id": source_record_id}]
    records: list[tuple[Path, dict[str, Any]]] = []
    errors: list[dict[str, Any]] = []
    for path in paths:
        last_error = ""
        for attempt in range(1, retries + 1):
            try:
                with path.open("r", encoding="utf-8") as handle:
                    row = json.load(handle)
                if not isinstance(row, dict):
                    raise ValueError("raw record is not a JSON object")
                records.append((path, row))
                last_error = ""
                break
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < retries:
                    time.sleep(0.05 * attempt)
        if last_error:
            errors.append(
                {
                    "kind": "raw_record_read_failed",
                    "source": source,
                    "source_record_id": source_record_id,
                    "raw_ref": _portable_raw_ref(source, path, raw_root),
                    "attempts": retries,
                    "error": last_error,
                }
            )
    return records, errors


def _raw_payload(source: str, row: dict[str, Any]) -> dict[str, Any]:
    if source == "otx" and isinstance(row.get("payload"), dict):
        return row["payload"]
    if source == "circl_misp" and isinstance(row.get("Event"), dict):
        return row["Event"]
    return row


def _explicit_urls(source: str, raw: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    payload = _raw_payload(source, raw)
    if source in {"otx", "orkl"}:
        for key in ("references", "sources"):
            value = payload.get(key)
            for text in _flatten_text(value):
                for url in URL_RE.findall(text):
                    out.append((url, key))
    if source == "circl_misp":
        for key, value in _walk(payload):
            leaf = _key_name(key)
            if leaf in {"link", "url", "reference", "references"}:
                for text in _flatten_text(value):
                    for url in URL_RE.findall(text):
                        out.append((url, key))
        for attr_path, attr in _iter_misp_attributes(payload):
            if str(attr.get("type", "")).casefold() == "link":
                for url in URL_RE.findall(str(attr.get("value", ""))):
                    out.append((url, f"{attr_path}.value"))
    return out


def _iter_misp_attributes(event: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for index, attr in enumerate(event.get("Attribute") or []):
        if isinstance(attr, dict):
            yield f"Event.Attribute[{index}]", attr
    for object_index, obj in enumerate(event.get("Object") or []):
        if not isinstance(obj, dict):
            continue
        for index, attr in enumerate(obj.get("Attribute") or []):
            if isinstance(attr, dict):
                yield f"Event.Object[{object_index}].Attribute[{index}]", attr


def _explicit_key_values(
    field: str,
    source: str,
    raw: dict[str, Any],
    values: dict[str, dict[str, dict[str, Any]]],
    raw_ref: str,
) -> None:
    for path, value in _walk(raw):
        key = _key_name(path)
        if not isinstance(value, (str, int, float)):
            continue
        if field == "external_report_ids" and key in STRUCTURED_EXTERNAL_KEYS:
            _add(values, field, value, layer="raw", path=path, raw_ref=raw_ref, method="structured_key")
        if field == "vendor_case_report_ids" and key in STRUCTURED_VENDOR_KEYS:
            _add(values, field, value, layer="raw", path=path, raw_ref=raw_ref, method="structured_key")


def _vendor_pattern_values(
    values: dict[str, dict[str, dict[str, Any]]],
    source: str,
    raw: dict[str, Any],
    raw_ref: str,
) -> None:
    payload = _raw_payload(source, raw)
    candidates: list[tuple[str, str]] = []
    if source == "circl_misp":
        event = payload
        for index, report in enumerate(event.get("EventReport") or []):
            if isinstance(report, dict):
                for key in ("name", "content"):
                    if report.get(key):
                        candidates.append((f"Event.EventReport[{index}].{key}", str(report[key])))
    elif source == "orkl":
        for key in ("title", "report_names", "references", "plain_text"):
            for text in _flatten_text(payload.get(key)):
                candidates.append((key, text))
    elif source == "otx":
        for key in ("name", "description", "references"):
            for text in _flatten_text(payload.get(key)):
                candidates.append((f"payload.{key}", text))
    for path, text in candidates:
        # Only inspect identifiers immediately following explicit report-like
        # context.  A global hyphen-token scan incorrectly classifies cipher
        # names, actor names, dates, and network identifiers as report IDs.
        for pattern in ID_CONTEXT_PATTERNS:
            for match in pattern.finditer(text):
                token = match.group("id")
                upper = token.upper()
                if upper.startswith(
                    (
                        "CVE-",
                        "AA",
                        "AR",
                        "TA",
                        "ICSA-",
                        "ICSMA-",
                        "MAR-",
                        "CSA-",
                        "ICS-ALERT-",
                        "IR-ALERT-",
                        "MISP-",
                        "APT-",
                        "UNC-",
                        "DEV-",
                        "UAC-",
                        "TAG-",
                        "AES-",
                        "ISO-",
                        "SHA-",
                        "UTF-",
                        "YYYY-",
                        "DD-",
                        "NET-",
                        "MNT-",
                        "HOW-",
                        "README-",
                        "COVID-",
                        "CERT-UA",
                        "CERT-",
                    )
                ):
                    continue
                if not any(char.isdigit() for char in token):
                    continue
                _add(
                    values,
                    "vendor_case_report_ids",
                    token,
                    layer="raw",
                    path=path,
                    raw_ref=raw_ref,
                    method="contextual_explicit_id_pattern",
                )


def _extract_one(
    event: dict[str, Any],
    claims: list[dict[str, Any]],
    raw_root: Path,
    retries: int,
    normalized_orkl: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    event_id = str(event["event_id"])
    source = str(event.get("source") or "")
    source_record_id = str(event.get("source_record_id") or "")
    dataset_raw_ref = _portable_raw_ref(source, event.get("raw_ref"), raw_root)
    values: dict[str, dict[str, dict[str, Any]]] = {field: {} for field in ARRAY_FIELDS}
    title_candidates: dict[str, dict[str, Any]] = {}

    if source == "orkl" and normalized_orkl:
        normalized_record = normalized_orkl.get("record") or {}
        normalized_raw_ref = normalized_orkl.get("raw_ref")
        line_number = normalized_orkl.get("line_number")
        published_at = _date_value(normalized_record.get("published_at"))
        if published_at and normalized_raw_ref and line_number:
            _add(
                values,
                "publish_dates",
                published_at,
                layer="raw",
                path=f"reports.jsonl[{line_number}].published_at",
                raw_ref=normalized_raw_ref,
                method="normalized_source_timestamp",
            )

    def add_title(value: Any, *, layer: str, path: str, raw_ref: str | None, method: str) -> None:
        text = _clean(value)
        if not text:
            return
        title_candidates.setdefault(text, {"value": text, "layer": layer, "paths": set(), "raw_refs": set(), "methods": set()})
        item = title_candidates[text]
        item["paths"].add(path)
        if raw_ref:
            item["raw_refs"].add(raw_ref)
        item["methods"].add(method)

    add_title(event.get("title"), layer="dataset", path="events.title", raw_ref=dataset_raw_ref, method="dataset_field")
    for value in event.get("references") or []:
        for url in URL_RE.findall(str(value)):
            _add(values, "reference_urls", url, layer="dataset", path="events.references", raw_ref=dataset_raw_ref, method="dataset_field")

    for text_path, text in (("events.title", event.get("title")), ("events.description", event.get("description"))):
        if text:
            _add_regex_values(values, "cve_ids", str(text), layer="dataset", path=text_path, raw_ref=dataset_raw_ref, method="explicit_id_pattern", pattern=CVE_RE)
            _add_regex_values(values, "cisa_advisory_ids", str(text), layer="dataset", path=text_path, raw_ref=dataset_raw_ref, method="explicit_id_pattern", pattern=CISA_RE)

    records, errors = _load_raw(source, source_record_id, raw_root, retries)
    for path, raw in records:
        raw_ref = _portable_raw_ref(source, path, raw_root)
        payload = _raw_payload(source, raw)
        if source == "otx":
            add_title(payload.get("name"), layer="raw", path="payload.name", raw_ref=raw_ref, method="structured_key")
            _add(values, "external_report_ids", payload.get("id"), layer="raw", path="payload.id", raw_ref=raw_ref, method="source_record_identifier")
            for indicator_index, indicator in enumerate(payload.get("indicators") or []):
                if isinstance(indicator, dict) and "cve" in str(indicator.get("type", "")).casefold():
                    _add_regex_values(values, "cve_ids", str(indicator.get("indicator", "")), layer="raw", path=f"payload.indicators[{indicator_index}].indicator", raw_ref=raw_ref, method="structured_key", pattern=CVE_RE)
            for path_text, text in (("payload.description", payload.get("description")), ("payload.name", payload.get("name"))):
                if text:
                    _add_regex_values(values, "cve_ids", str(text), layer="raw", path=path_text, raw_ref=raw_ref, method="explicit_id_pattern", pattern=CVE_RE)
                    _add_regex_values(values, "cisa_advisory_ids", str(text), layer="raw", path=path_text, raw_ref=raw_ref, method="explicit_id_pattern", pattern=CISA_RE)
            _add(values, "publish_dates", payload.get("created"), layer="raw", path="payload.created", raw_ref=raw_ref, method="source_created_timestamp")
        elif source == "orkl":
            title_key = "title" if _clean(payload.get("title")) else "llm_title"
            add_title(payload.get("title") or payload.get("llm_title"), layer="raw", path=title_key, raw_ref=raw_ref, method="structured_key")
            _add(values, "external_report_ids", payload.get("id"), layer="raw", path="id", raw_ref=raw_ref, method="source_record_identifier")
            for key in ("references",):
                for text in _flatten_text(payload.get(key)):
                    for url in URL_RE.findall(text):
                        _add(values, "reference_urls", url, layer="raw", path=key, raw_ref=raw_ref, method="structured_key")
            # ORKL's ts_created_at and ts_creation_date describe archive or
            # source-document creation, not an explicit publication date.
            # Do not relabel either field as publish_dates; the contract says
            # null is preferable to an inferred date.
            if payload.get("sources"):
                _add(values, "publishing_organizations", payload.get("sources"), layer="raw", path="sources", raw_ref=raw_ref, method="structured_key")
            for text_path, text in (("plain_text", payload.get("plain_text")), ("title", payload.get("title"))):
                if text:
                    _add_regex_values(values, "cve_ids", str(text), layer="raw", path=text_path, raw_ref=raw_ref, method="explicit_id_pattern", pattern=CVE_RE)
                    _add_regex_values(values, "cisa_advisory_ids", str(text), layer="raw", path=text_path, raw_ref=raw_ref, method="explicit_id_pattern", pattern=CISA_RE)
        elif source == "circl_misp":
            add_title(payload.get("info"), layer="raw", path="Event.info", raw_ref=raw_ref, method="structured_key")
            _add(values, "misp_event_uuids", payload.get("uuid"), layer="raw", path="Event.uuid", raw_ref=raw_ref, method="structured_key")
            _add(values, "publish_dates", payload.get("publish_timestamp"), layer="raw", path="Event.publish_timestamp", raw_ref=raw_ref, method="explicit_source_date")
            orgc = payload.get("Orgc")
            if isinstance(orgc, dict):
                _add(values, "publishing_organizations", orgc.get("name"), layer="raw", path="Event.Orgc.name", raw_ref=raw_ref, method="structured_key")
            for attr_path, attr in _iter_misp_attributes(payload):
                for key in ("value", "comment"):
                    text = attr.get(key)
                    if text:
                        _add_regex_values(values, "cve_ids", str(text), layer="raw", path=f"{attr_path}.{key}", raw_ref=raw_ref, method="explicit_id_pattern", pattern=CVE_RE)
                        _add_regex_values(values, "cisa_advisory_ids", str(text), layer="raw", path=f"{attr_path}.{key}", raw_ref=raw_ref, method="explicit_id_pattern", pattern=CISA_RE)
                if attr.get("first_seen"):
                    _add(values, "first_seen_dates", attr.get("first_seen"), layer="raw", path=f"{attr_path}.first_seen", raw_ref=raw_ref, method="explicit_source_date")
                # MISP's generic Attribute.timestamp is a record/update
                # timestamp, not a first-seen timestamp.  Do not relabel it.
            for report_index, report in enumerate(payload.get("EventReport") or []):
                if isinstance(report, dict):
                    for key in ("name", "content"):
                        text = report.get(key)
                        if text:
                            _add_regex_values(values, "cve_ids", str(text), layer="raw", path=f"Event.EventReport[{report_index}].{key}", raw_ref=raw_ref, method="explicit_id_pattern", pattern=CVE_RE)
                            _add_regex_values(values, "cisa_advisory_ids", str(text), layer="raw", path=f"Event.EventReport[{report_index}].{key}", raw_ref=raw_ref, method="explicit_id_pattern", pattern=CISA_RE)
        for field in ("external_report_ids", "vendor_case_report_ids"):
            _explicit_key_values(field, source, raw, values, raw_ref)
        for url, path_text in _explicit_urls(source, raw):
            _add(values, "reference_urls", url, layer="raw", path=path_text, raw_ref=raw_ref, method="explicit_reference_url")

    title = next(iter(title_candidates), None)
    dataset_title = _clean(event.get("title"))
    if dataset_title:
        title = dataset_title
    output: dict[str, Any] = {"event_id": event_id, "source_name": source}
    for field in OUTPUT_FIELDS[2:]:
        if field == "title":
            output[field] = title
        else:
            ordered = sorted(values[field])
            output[field] = ordered if ordered else None

    provenance: dict[str, Any] = {
        "event_id": event_id,
        "source_name": source,
        "source_record_id": source_record_id,
        "attribution_claim_ids": sorted(str(c.get("claim_id")) for c in claims if c.get("claim_id")),
        "fields": {},
    }
    for field, entries in values.items():
        if entries:
            provenance["fields"][field] = []
            for value in sorted(entries):
                item = entries[value]
                provenance["fields"][field].append(
                    {
                        "value": item["value"],
                        "layers": sorted({item["layer"]}),
                        "paths": sorted(item["paths"]),
                        "raw_refs": sorted(item["raw_refs"]),
                        "methods": sorted(item["methods"]),
                    }
                )
    if title_candidates:
        provenance["title_candidates"] = [
            {
                "value": item["value"],
                "layer": item["layer"],
                "paths": sorted(item["paths"]),
                "raw_refs": sorted(item["raw_refs"]),
                "methods": sorted(item["methods"]),
            }
            for item in sorted(title_candidates.values(), key=lambda x: x["value"])
        ]
    return output, provenance, errors


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _extract_with_retries(
    event: dict[str, Any],
    claims: list[dict[str, Any]],
    raw_root: Path,
    retries: int,
    normalized_orkl: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Retry an unexpected per-event extraction failure at most three times."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return _extract_one(event, claims, raw_root, retries, normalized_orkl)
        except Exception as exc:  # pragma: no cover - defensive boundary
            last_error = exc
            if attempt < retries:
                time.sleep(0.05 * attempt)
    assert last_error is not None
    raise last_error


def _validate_contract(
    *,
    events: dict[str, dict[str, Any]],
    attributed_ids: list[str],
    metadata: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    non_attributed: list[dict[str, Any]],
    input_counts: dict[str, dict[str, int]],
) -> list[str]:
    """Return all contract violations before any output directory is written."""
    violations: list[str] = []
    for dataset, spec in EXPECTED.items():
        observed = input_counts.get(dataset)
        if observed != spec:
            violations.append(f"{dataset} counts {observed!r} != {spec!r}")
        if observed and any(value in FORBIDDEN_COUNTS for value in observed.values()):
            violations.append(f"{dataset} contains a forbidden historical count")

    expected_ids = set(attributed_ids)
    metadata_ids = [row.get("event_id") for row in metadata]
    if len(metadata) != len(attributed_ids):
        violations.append(f"metadata count {len(metadata)} != attribution count {len(attributed_ids)}")
    if len(metadata_ids) != len(set(metadata_ids)):
        violations.append("metadata contains duplicate event_id values")
    if set(metadata_ids) != expected_ids:
        violations.append("metadata event_id set does not equal the attribution event set")

    provenance_ids = [row.get("event_id") for row in provenance]
    if len(provenance) != len(metadata):
        violations.append("provenance count does not equal metadata count")
    if set(provenance_ids) != expected_ids:
        violations.append("provenance event_id set does not equal the attribution event set")

    for row in provenance:
        event_id = row.get("event_id")
        for field_entries in (row.get("fields") or {}).values():
            for entry in field_entries or []:
                for raw_ref in entry.get("raw_refs") or []:
                    ref = str(raw_ref)
                    if not ref.startswith("data/raw/") or Path(ref).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", ref):
                        violations.append(f"{event_id}: non-portable raw_ref {ref!r}")
        for entry in row.get("title_candidates") or []:
            for raw_ref in entry.get("raw_refs") or []:
                ref = str(raw_ref)
                if not ref.startswith("data/raw/") or Path(ref).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", ref):
                    violations.append(f"{event_id}: non-portable title raw_ref {ref!r}")

    expected_non_attributed = set(events) - expected_ids
    non_attributed_ids = [row.get("event_id") for row in non_attributed]
    if len(non_attributed_ids) != len(set(non_attributed_ids)):
        violations.append("non-attributed list contains duplicate event_id values")
    if set(non_attributed_ids) != expected_non_attributed:
        violations.append("non-attributed event_id set is not the complement of attribution events")

    for row in metadata:
        event_id = row.get("event_id")
        if set(row) != set(OUTPUT_FIELDS):
            violations.append(f"{event_id}: output schema mismatch")
        if event_id not in events:
            violations.append(f"{event_id}: output event_id is not in frozen input")
        elif row.get("source_name") != events[event_id].get("source"):
            violations.append(f"{event_id}: source_name disagrees with frozen input")
        if not isinstance(row.get("source_name"), str) or not row.get("source_name"):
            violations.append(f"{event_id}: source_name is missing")
        if row.get("title") is not None and not isinstance(row.get("title"), str):
            violations.append(f"{event_id}: title must be string or null")
        for field in ARRAY_FIELDS:
            value = row.get(field)
            if value is not None and (
                not isinstance(value, list)
                or any(not isinstance(item, str) or not item for item in value)
                or len(value) != len(set(value))
            ):
                violations.append(f"{event_id}: {field} must be a unique string array or null")

    if exceptions:
        violations.append(f"{len(exceptions)} extraction exception(s) remain after bounded retries")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="validate and print the result without writing any output")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    if args.workers < 1 or args.retries < 1 or args.retries > 3:
        raise SystemExit("workers must be positive and retries must be between 1 and 3")

    dataset_root = args.dataset_root.resolve()
    raw_root = args.raw_root.resolve()
    orkl_normalized_index = _load_orkl_normalized_index(raw_root)
    if not args.dry_run and args.output_dir is None:
        raise SystemExit("--output-dir is required unless --dry-run is used")
    output_dir = args.output_dir.resolve() if args.output_dir else None
    if not args.dry_run and output_dir is not None and output_dir.exists():
        raise SystemExit(f"refusing to overwrite existing output directory: {output_dir}")

    events: dict[str, dict[str, Any]] = {}
    claims_by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    input_counts: dict[str, dict[str, int]] = {}
    for dataset in SOURCES:
        spec = EXPECTED[dataset]
        handoff = dataset_root / dataset / "handoff"
        event_rows = list(_jsonl(handoff / "events.jsonl"))
        claim_rows = list(_jsonl(handoff / "source_claims.jsonl"))
        if len(event_rows) in FORBIDDEN_COUNTS or len(claim_rows) in FORBIDDEN_COUNTS:
            raise SystemExit(f"historical forbidden population detected in {dataset}")
        if len(event_rows) != spec["events"] or len(claim_rows) != spec["source_claims"]:
            raise SystemExit(
                f"{dataset} count mismatch: events={len(event_rows)} claims={len(claim_rows)} "
                f"expected={spec}"
            )
        input_counts[dataset] = {"events": len(event_rows), "source_claims": len(claim_rows)}
        for row in event_rows:
            event_id = str(row.get("event_id") or "")
            if not event_id or event_id in events:
                raise SystemExit(f"duplicate or missing event_id: {event_id!r}")
            events[event_id] = row
        for row in claim_rows:
            if row.get("claim_scope") == "attribution":
                claims_by_event[str(row.get("event_id"))].append(row)

    attributed_ids = sorted(claims_by_event)
    tasks = [(events[event_id], claims_by_event[event_id]) for event_id in attributed_ids]
    results: dict[str, tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {
            executor.submit(
                _extract_with_retries,
                event,
                claims,
                raw_root,
                args.retries,
                orkl_normalized_index.get(str(event.get("source_record_id") or ""))
                if event.get("source") == "orkl"
                else None,
            ): event["event_id"]
            for event, claims in tasks
        }
        for future in as_completed(future_map):
            event_id = future_map[future]
            try:
                results[event_id] = future.result()
            except Exception as exc:  # keep one task from silently disappearing
                results[event_id] = (
                    {field: (None if field in ARRAY_FIELDS or field == "title" else "") for field in OUTPUT_FIELDS},
                    {"event_id": event_id, "fatal_error": f"{type(exc).__name__}: {exc}"},
                    [{"kind": "event_extraction_failed", "event_id": event_id, "error": f"{type(exc).__name__}: {exc}"}],
                )
                results[event_id][0]["event_id"] = event_id
                results[event_id][0]["source_name"] = events[event_id].get("source")

    metadata = [results[event_id][0] for event_id in attributed_ids]
    provenance = [results[event_id][1] for event_id in attributed_ids]
    exceptions = [error for event_id in attributed_ids for error in results[event_id][2]]
    non_attributed = [
        {"event_id": event_id, "source_name": events[event_id].get("source")}
        for event_id in sorted(set(events) - set(attributed_ids))
    ]

    field_counts = {}
    source_counts = Counter(row["source_name"] for row in metadata)
    for field in OUTPUT_FIELDS[2:]:
        if field == "title":
            field_counts[field] = {
                "non_null": sum(row[field] is not None for row in metadata),
                "null": sum(row[field] is None for row in metadata),
            }
        else:
            field_counts[field] = {
                "non_null": sum(row[field] is not None for row in metadata),
                "null": sum(row[field] is None for row in metadata),
                "value_count": sum(len(row[field] or []) for row in metadata),
            }

    violations = _validate_contract(
        events=events,
        attributed_ids=attributed_ids,
        metadata=metadata,
        provenance=provenance,
        exceptions=exceptions,
        non_attributed=non_attributed,
        input_counts=input_counts,
    )
    summary = {
        "contract": "attributed_event_metadata_v1",
        "status": "complete_with_exceptions" if exceptions else "complete",
        "document_sha256_included": False,
        "document_sha256_policy": "source-provided original-document hash only; unavailable values remain null",
        "input_counts": input_counts,
        "total_events": len(events),
        "attributed_event_count": len(metadata),
        "non_attributed_event_count": len(non_attributed),
        "metadata_record_count": len(metadata),
        "unique_metadata_event_ids": len({row["event_id"] for row in metadata}),
        "attributed_events_by_source": dict(sorted(source_counts.items())),
        "field_coverage": field_counts,
        "exception_count": len(exceptions),
        "exception_counts_by_kind": dict(sorted(Counter(row.get("kind") for row in exceptions).items())),
        "preflight": {
            "passed": not violations,
            "violations": violations,
            "vendor_id_policy": "structured_keys_only; no free-text pattern inference",
            "orkl_publish_date_policy": "explicit publication date only; source/archive creation dates remain null",
        },
        "policy": {
            "eligibility": "at least one claim_scope=attribution",
            "raw_document_download": False,
            "network_access": False,
            "missing_field_value": None,
            "max_read_retries": args.retries,
            "workers": args.workers,
        },
    }
    if violations:
        summary["status"] = "preflight_failed"
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not violations else 2

    assert output_dir is not None
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=str(output_dir.parent)))
    try:
        if violations:
            raise SystemExit("preflight failed; no output directory was published: " + "; ".join(violations[:8]))
        _write_jsonl(staging_dir / "attributed_event_metadata.jsonl", metadata)
        _write_jsonl(staging_dir / "metadata_provenance.jsonl", provenance)
        _write_jsonl(staging_dir / "metadata_exceptions.jsonl", exceptions)
        _write_jsonl(staging_dir / "non_attributed_event_ids.jsonl", non_attributed)
        (staging_dir / "metadata_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging_dir.replace(output_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not exceptions else 2


if __name__ == "__main__":
    sys.exit(main())
