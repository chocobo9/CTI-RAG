"""Independently audit attributed-event metadata against the local raw store."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

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
ABSOLUTE_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")
TOKEN_RE = re.compile(r"([^\.\[\]]+)|\[(\d+)\]")
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"{path}:{number}: expected object")
                rows.append(row)
    return rows


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date_value(value: Any) -> str | None:
    text = _clean(value)
    if not text:
        return None
    if text.isdigit() and len(text) in {10, 13}:
        from datetime import datetime, timezone

        seconds = int(text) / (1000 if len(text) == 13 else 1)
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return text


def _raw_paths(source: str, source_record_id: str, raw_root: Path) -> list[Path]:
    if source == "otx":
        return sorted((raw_root / "otx" / source_record_id).glob("*.json"))
    if source == "orkl":
        return sorted((raw_root / "orkl" / "raw" / "reports" / source_record_id).glob("*.json"))
    if source == "circl_misp":
        path = raw_root / "circl_misp" / "raw" / "events" / f"{source_record_id}.json"
        return [path] if path.is_file() else []
    return []


def _raw_ref_path(raw_ref: Any, raw_root: Path) -> Path | None:
    text = _clean(raw_ref)
    if not text or ABSOLUTE_RE.match(text):
        return None
    normalized = text.replace("\\", "/")
    if not normalized.startswith("data/raw/"):
        return None
    return raw_root / Path(normalized.removeprefix("data/raw/") )


def _tokens(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for match in TOKEN_RE.finditer(path):
        key, index = match.groups()
        tokens.append(int(index) if index is not None else key)
    return tokens


def _at_path(root: Any, path: str) -> list[Any]:
    values = [root]
    for token in _tokens(path):
        next_values: list[Any] = []
        for value in values:
            if isinstance(token, int):
                if isinstance(value, list) and token < len(value):
                    next_values.append(value[token])
            elif isinstance(value, dict) and token in value:
                next_values.append(value[token])
        values = next_values
    return values


def _flatten_text(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _flatten_text(item)
    elif isinstance(value, list):
        for item in value:
            yield from _flatten_text(item)


def _raw_value_matches(field: str, expected: str, values: Iterable[Any]) -> bool:
    texts = [text for value in values for text in _flatten_text(value)]
    expected_text = str(expected)
    if field in {"publish_dates", "first_seen_dates"}:
        return any(_date_value(text) == expected_text for text in texts)
    if field == "reference_urls":
        return any(expected_text == url.rstrip(".,;:!?)]}") for text in texts for url in URL_RE.findall(text))
    if field in {"cve_ids", "cisa_advisory_ids"}:
        return any(expected_text.casefold() in text.casefold() for text in texts)
    if field == "misp_event_uuids":
        return any(expected_text.casefold() == text.strip().casefold() for text in texts)
    if field == "document_sha256":
        return any(expected_text.casefold() == text.strip().casefold() for text in texts)
    return any(expected_text == text.strip() or expected_text in text for text in texts)


def _entry_raw_match(
    *,
    source: str,
    raw_records: list[dict[str, Any]],
    field: str,
    value: str,
    path: str,
) -> bool:
    if path.startswith("events."):
        return False
    for raw in raw_records:
        if source == "otx" and not path.startswith("payload."):
            root = raw.get("payload") if isinstance(raw.get("payload"), dict) else raw
        else:
            root = raw
        if _raw_value_matches(field, value, _at_path(root, path)):
            return True
    return False


def audit(metadata_dir: Path, raw_root: Path) -> dict[str, Any]:
    metadata = _jsonl(metadata_dir / "attributed_event_metadata.jsonl")
    provenance = _jsonl(metadata_dir / "metadata_provenance.jsonl")
    metadata_by_id = {str(row.get("event_id")): row for row in metadata}
    provenance_by_id = {str(row.get("event_id")): row for row in provenance}
    errors: list[dict[str, Any]] = []
    raw_ref_count = 0
    raw_ref_existing_count = 0
    raw_value_checks = Counter()
    source_record_counts = Counter()
    document_hash_methods: Counter[str] = Counter()

    if len(metadata) != len(metadata_by_id):
        errors.append({"kind": "duplicate_metadata_event_id"})
    if len(provenance) != len(provenance_by_id):
        errors.append({"kind": "duplicate_provenance_event_id"})
    if set(metadata_by_id) != set(provenance_by_id):
        errors.append({"kind": "metadata_provenance_event_set_mismatch"})

    for event_id, row in metadata_by_id.items():
        source = str(row.get("source_name") or "")
        source_record_id = str(provenance_by_id.get(event_id, {}).get("source_record_id") or "")
        paths = _raw_paths(source, source_record_id, raw_root)
        source_record_counts[(source, "found" if paths else "missing")] += 1
        if not paths:
            errors.append({"kind": "source_raw_record_missing", "event_id": event_id, "source": source, "source_record_id": source_record_id})
            continue
        raw_records = []
        for path in paths:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    raw_records.append(value)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                errors.append({"kind": "source_raw_record_unreadable", "event_id": event_id, "path": str(path), "error": str(exc)})
        prov = provenance_by_id.get(event_id) or {}
        if set(row) != set(OUTPUT_FIELDS):
            errors.append({"kind": "metadata_schema_mismatch", "event_id": event_id, "fields": sorted(set(row) ^ set(OUTPUT_FIELDS))})
        for field in OUTPUT_FIELDS[2:]:
            values = [row.get(field)] if field == "title" else list(row.get(field) or [])
            if row.get(field) is None:
                continue
            entries = (prov.get("fields") or {}).get(field, []) if field != "title" else (prov.get("title_candidates") or [])
            entry_values = {str(entry.get("value")) for entry in entries}
            for value in values:
                if str(value) not in entry_values:
                    errors.append({"kind": "metadata_value_without_provenance", "event_id": event_id, "field": field, "value": value})
            for entry in entries:
                entry_value = str(entry.get("value") or "")
                for raw_ref in entry.get("raw_refs") or []:
                    raw_ref_count += 1
                    ref_path = _raw_ref_path(raw_ref, raw_root)
                    if ref_path is None or not ref_path.is_file():
                        errors.append({"kind": "provenance_raw_ref_missing", "event_id": event_id, "field": field, "raw_ref": raw_ref})
                    else:
                        raw_ref_existing_count += 1
                layers = set(entry.get("layers") or ([entry.get("layer")] if entry.get("layer") else []))
                raw_paths = [str(path) for path in entry.get("paths") or [] if not str(path).startswith("events.")]
                if "events.title" in (entry.get("paths") or []):
                    title_path = {
                        "circl_misp": "Event.info",
                        "otx": "payload.name",
                        "orkl": "title",
                    }.get(source)
                    if title_path:
                        raw_paths.append(title_path)
                if not raw_paths:
                    raw_value_checks["dataset_layer_value"] += 1
                    continue
                matched = any(
                    _entry_raw_match(source=source, raw_records=raw_records, field=field, value=entry_value, path=str(path))
                    for path in raw_paths
                )
                raw_value_checks["raw_value_verified" if matched else "raw_value_mismatch"] += 1
                if not matched:
                    errors.append({"kind": "raw_value_mismatch", "event_id": event_id, "field": field, "value": entry_value, "paths": entry.get("paths")})
                if field == "document_sha256":
                    for method in entry.get("methods") or []:
                        document_hash_methods[str(method)] += 1

    summary = {
        "status": "pass" if not errors else "fail",
        "metadata_records": len(metadata),
        "provenance_records": len(provenance),
        "source_raw_records": {f"{source}:{status}": count for (source, status), count in sorted(source_record_counts.items())},
        "raw_ref_count": raw_ref_count,
        "raw_ref_existing_count": raw_ref_existing_count,
        "raw_value_checks": dict(sorted(raw_value_checks.items())),
        "document_hash_methods": dict(sorted(document_hash_methods.items())),
        "error_count": len(errors),
        "errors": errors[:100],
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-dir", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    summary = audit(args.metadata_dir.resolve(), args.raw_root.resolve())
    payload = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if summary["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
