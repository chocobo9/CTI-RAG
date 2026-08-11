"""Add source-backed original-document SHA-256 values to metadata.

Only a source-provided hash whose field explicitly identifies the original
document/report is accepted. Raw JSON hashes, IOC hashes, and hashes of
derived text are not document hashes. If the original-document hash is not
available, the value remains null.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

from extract_attributed_event_metadata import _portable_raw_ref


REQUIRED_FIELDS = {
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
}
HASH_FIELD = "document_sha256"
HASH_RE = __import__("re").compile(r"\A[0-9a-f]{64}\Z", __import__("re").IGNORECASE)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}: line {line_number} is not an object")
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _read_json(path: Path, retries: int) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(row, dict):
                raise ValueError("raw record is not a JSON object")
            return row
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(0.05 * attempt)
    assert last is not None
    raise last


def _raw_paths(source: str, record_id: str, raw_root: Path) -> list[Path]:
    if source == "orkl":
        return sorted((raw_root / "orkl" / "raw" / "reports" / record_id).glob("*.json"))
    if source == "circl_misp":
        path = raw_root / "circl_misp" / "raw" / "events" / f"{record_id}.json"
        return [path] if path.exists() else []
    if source == "otx":
        return sorted((raw_root / "otx" / record_id).glob("*.json"))
    return []


def _walk(obj: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            current = f"{path}.{key}" if path else str(key)
            yield current, value
            yield from _walk(value, current)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from _walk(value, f"{path}[{index}]")


def _explicit_hashes(raw: dict[str, Any], raw_ref: str) -> list[dict[str, Any]]:
    allowed = {
        "document_sha256",
        "document_hash_sha256",
        "original_document_sha256",
        "report_sha256",
    }
    out: list[dict[str, Any]] = []
    for path, value in _walk(raw):
        key = path.rsplit(".", 1)[-1].casefold().replace("-", "_")
        text = str(value).strip().lower() if isinstance(value, (str, int)) else ""
        if key in allowed and HASH_RE.fullmatch(text):
            out.append({
                "value": text,
                "path": path,
                "raw_ref": raw_ref,
                "method": "source_provided_document_sha256",
            })
    return out


def _hash_event(source: str, record_id: str, raw_root: Path, retries: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    paths = _raw_paths(source, record_id, raw_root)
    for path in paths:
        try:
            raw = _read_json(path, retries)
        except Exception as exc:
            exceptions.append({
                "kind": "document_hash_raw_read_failed",
                "source": source,
                "source_record_id": record_id,
                "raw_ref": _portable_raw_ref(source, path, raw_root),
                "attempts": retries,
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        raw_ref = _portable_raw_ref(source, path, raw_root)
        candidates.extend(_explicit_hashes(raw, raw_ref))
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in candidates:
        unique[(item["value"], item["method"])] = item
    return sorted(unique.values(), key=lambda item: (item["value"], item["method"], item["path"])), exceptions


def _normalize_provenance(source: str, source_record_id: str, provenance: dict[str, Any], raw_root: Path) -> tuple[dict[str, Any], int]:
    """Normalize every existing provenance reference and remove old hash claims."""
    normalized = dict(provenance)
    removed_missing_refs = 0
    orkl_title_path: str | None = None
    if source == "orkl":
        raw_paths = _raw_paths(source, source_record_id, raw_root)
        if raw_paths:
            raw = _read_json(raw_paths[0], 3)
            orkl_title_path = "title" if str(raw.get("title") or "").strip() else "llm_title"

    def normalize_refs(raw_refs: Any) -> list[str]:
        nonlocal removed_missing_refs
        original = list(raw_refs or [])
        refs: set[str] = set()
        for raw_ref in original:
            ref = _portable_raw_ref(source, raw_ref, raw_root)
            if ref is None:
                continue
            local_path = raw_root / ref.removeprefix("data/raw/")
            if not local_path.is_file():
                removed_missing_refs += 1
                continue
            refs.add(ref)
        if original and not refs:
            raise ValueError(f"all provenance raw_refs are missing for source={source}")
        return sorted(refs)

    fields: dict[str, list[dict[str, Any]]] = {}
    for field, entries in (provenance.get("fields") or {}).items():
        if field == HASH_FIELD:
            continue
        normalized_entries: list[dict[str, Any]] = []
        for entry in entries or []:
            item = dict(entry)
            item["raw_refs"] = normalize_refs(item.get("raw_refs"))
            normalized_entries.append(item)
        fields[field] = normalized_entries
    normalized["fields"] = fields
    title_candidates: list[dict[str, Any]] = []
    for entry in provenance.get("title_candidates") or []:
        item = dict(entry)
        item["raw_refs"] = normalize_refs(item.get("raw_refs"))
        if source == "orkl" and orkl_title_path:
            item["paths"] = [orkl_title_path if path == "title" else path for path in item.get("paths") or []]
        title_candidates.append(item)
    if title_candidates:
        normalized["title_candidates"] = title_candidates
    return normalized, removed_missing_refs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-dir", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.retries <= 3:
        raise SystemExit("retries must be between 1 and 3")
    metadata_dir = args.metadata_dir.resolve()
    raw_root = args.raw_root.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise SystemExit(f"refusing to overwrite existing output directory: {output_dir}")

    metadata = _jsonl(metadata_dir / "attributed_event_metadata.jsonl")
    provenance = _jsonl(metadata_dir / "metadata_provenance.jsonl")
    exceptions = _jsonl(metadata_dir / "metadata_exceptions.jsonl")
    non_attributed = _jsonl(metadata_dir / "non_attributed_event_ids.jsonl")
    summary = json.loads((metadata_dir / "metadata_summary.json").read_text(encoding="utf-8"))
    if len(metadata) != len(provenance) or exceptions:
        raise SystemExit("input metadata/provenance mismatch or existing exceptions; refusing hash publication")
    provenance_by_id = {row["event_id"]: row for row in provenance}
    hash_exceptions: list[dict[str, Any]] = []
    hash_coverage = {"otx": 0, "orkl": 0, "circl_misp": 0}
    basis_counts: dict[str, int] = {}
    new_metadata: list[dict[str, Any]] = []
    new_provenance: list[dict[str, Any]] = []
    removed_missing_raw_ref_count = 0
    for row in metadata:
        event_id = row["event_id"]
        source = str(row["source_name"])
        prov = provenance_by_id[event_id]
        candidates, event_errors = _hash_event(source, str(prov.get("source_record_id") or ""), raw_root, args.retries)
        hash_exceptions.extend({**error, "event_id": event_id} for error in event_errors)
        values = sorted({item["value"] for item in candidates})
        if values:
            hash_coverage[source] = hash_coverage.get(source, 0) + 1
        for item in candidates:
            basis_counts[item["method"]] = basis_counts.get(item["method"], 0) + 1
        new_row = dict(row)
        new_row[HASH_FIELD] = values or None
        new_metadata.append(new_row)
        new_prov, removed_count = _normalize_provenance(source, str(prov.get("source_record_id") or ""), prov, raw_root)
        removed_missing_raw_ref_count += removed_count
        fields = dict(new_prov.get("fields") or {})
        if candidates:
            fields[HASH_FIELD] = [
                {
                    "value": item["value"],
                    "layers": ["raw"],
                    "paths": [item["path"]],
                    "raw_refs": [item["raw_ref"]],
                    "methods": [item["method"]],
                }
                for item in candidates
            ]
        new_prov["fields"] = fields
        new_provenance.append(new_prov)

    if hash_exceptions:
        raise SystemExit(f"document hash read errors after bounded retries: {len(hash_exceptions)}")
    if any(set(row) != REQUIRED_FIELDS | {HASH_FIELD} for row in new_metadata):
        raise SystemExit("hash output schema validation failed")
    if len({row["event_id"] for row in new_metadata}) != len(new_metadata):
        raise SystemExit("hash output contains duplicate event IDs")
    if any(row[HASH_FIELD] is not None and len(row[HASH_FIELD]) != len(set(row[HASH_FIELD])) for row in new_metadata):
        raise SystemExit("hash output contains duplicate hash values")
    for provenance_row in new_provenance:
        for entries in (provenance_row.get("fields") or {}).values():
            for entry in entries or []:
                if any(not str(ref).startswith("data/raw/") for ref in entry.get("raw_refs") or []):
                    raise SystemExit("non-portable raw_ref remains in metadata provenance")
        for entry in provenance_row.get("title_candidates") or []:
            if any(not str(ref).startswith("data/raw/") for ref in entry.get("raw_refs") or []):
                raise SystemExit("non-portable title raw_ref remains in metadata provenance")

    new_summary = dict(summary)
    new_summary["document_sha256_included"] = True
    new_summary["document_sha256_coverage"] = {
        "non_null_events": sum(row[HASH_FIELD] is not None for row in new_metadata),
        "null_events": sum(row[HASH_FIELD] is None for row in new_metadata),
        "hash_value_count": sum(len(row[HASH_FIELD] or []) for row in new_metadata),
        "events_by_source": dict(sorted(hash_coverage.items())),
        "basis_by_method": dict(sorted(basis_counts.items())),
        "original_binary_document_bytes_downloaded": False,
    }
    new_summary["provenance_raw_ref_cleanup"] = {
        "missing_refs_removed": removed_missing_raw_ref_count,
        "policy": "retain only raw references that resolve to files in the configured raw root",
    }
    new_summary["preflight"] = {
        **(summary.get("preflight") or {}),
        "passed": True,
        "document_hash_policy": "source-provided original-document SHA-256 only; derived text/raw JSON/IOC hashes excluded",
    }
    new_summary["policy"] = {
        **(summary.get("policy") or {}),
        "document_sha256": "source-provided original-document hash only; unavailable remains null",
        "network_access": False,
        "raw_document_download": False,
        "max_read_retries": args.retries,
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=str(output_dir.parent)))
    try:
        _write_jsonl(staging_dir / "attributed_event_metadata.jsonl", new_metadata)
        _write_jsonl(staging_dir / "metadata_provenance.jsonl", new_provenance)
        _write_jsonl(staging_dir / "metadata_exceptions.jsonl", [])
        _write_jsonl(staging_dir / "non_attributed_event_ids.jsonl", non_attributed)
        (staging_dir / "metadata_summary.json").write_text(
            json.dumps(new_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging_dir.replace(output_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    print(json.dumps(new_summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
