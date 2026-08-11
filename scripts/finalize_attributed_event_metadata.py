"""Preflight and atomically publish the attributed-event metadata candidate.

This finalizer is intentionally conservative.  It reads the already collected
candidate and provenance, removes only values whose provenance shows that they
were inferred from free text or archive timestamps, validates the complete
event contract in memory, and publishes one output directory atomically.
No network access, document download, or source-data mutation is performed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


EXPECTED_INPUT_COUNTS = {
    "otx_dataset": {"events": 4_136, "source_claims": 2_704},
    "additional_sources_dataset": {"events": 19_276, "source_claims": 52_550},
}
FORBIDDEN_COUNTS = {17_454, 10_253, 8_597}
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


def _value_list(row: dict[str, Any], field: str) -> list[str]:
    value = row.get(field)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{row.get('event_id')}: {field} is not a string array or null")
    if len(value) != len(set(value)):
        raise ValueError(f"{row.get('event_id')}: {field} contains duplicate values")
    return list(value)


def _entry_is_structured(entry: dict[str, Any]) -> bool:
    return "structured_key" in set(entry.get("methods") or [])


def _entry_is_orkl_archive_date(entry: dict[str, Any]) -> bool:
    archive_paths = {
        "ts_created_at",
        "ts_creation_date",
        "ts_modification_date",
        "ts_updated_at",
        "created_at",
        "file_creation_date",
        "file_modification_date",
    }
    return any(path in archive_paths for path in entry.get("paths") or [])


def _normalize(
    candidate_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[str]]:
    metadata = _jsonl(candidate_dir / "attributed_event_metadata.jsonl")
    provenance = _jsonl(candidate_dir / "metadata_provenance.jsonl")
    exceptions = _jsonl(candidate_dir / "metadata_exceptions.jsonl")
    non_attributed = _jsonl(candidate_dir / "non_attributed_event_ids.jsonl")
    candidate_summary = json.loads((candidate_dir / "metadata_summary.json").read_text(encoding="utf-8"))
    violations: list[str] = []

    if candidate_summary.get("input_counts") != EXPECTED_INPUT_COUNTS:
        violations.append("candidate input_counts do not match the frozen 4,136/19,276 datasets")
    if any(
        value in FORBIDDEN_COUNTS
        for spec in (candidate_summary.get("input_counts") or {}).values()
        if isinstance(spec, dict)
        for value in spec.values()
    ):
        violations.append("candidate contains a forbidden historical population count")
    if candidate_summary.get("document_sha256_included") is not True:
        violations.append("candidate document_sha256 field is not present as a completed contract field")
    if len(metadata) != 21_973 or len(provenance) != 21_973 or len(non_attributed) != 1_439:
        violations.append("candidate record counts do not match the frozen attribution population")
    if exceptions:
        violations.append(f"candidate contains {len(exceptions)} extraction exceptions")

    metadata_by_id = {row.get("event_id"): row for row in metadata}
    provenance_by_id = {row.get("event_id"): row for row in provenance}
    non_attributed_ids = [row.get("event_id") for row in non_attributed]
    if len(metadata_by_id) != len(metadata):
        violations.append("candidate metadata has duplicate event_id values")
    if len(provenance_by_id) != len(provenance):
        violations.append("candidate provenance has duplicate event_id values")
    if len(set(non_attributed_ids)) != len(non_attributed_ids):
        violations.append("candidate non-attributed list has duplicate event_id values")
    if set(metadata_by_id) & set(non_attributed_ids):
        violations.append("candidate attributed and non-attributed event sets overlap")

    normalized_metadata: list[dict[str, Any]] = []
    normalized_provenance: list[dict[str, Any]] = []
    dropped = Counter()
    for row in metadata:
        event_id = row.get("event_id")
        prov = provenance_by_id.get(event_id)
        if prov is None:
            violations.append(f"{event_id}: missing provenance")
            continue
        if set(row) != set(OUTPUT_FIELDS):
            violations.append(f"{event_id}: candidate schema mismatch")
        if prov.get("source_name") != row.get("source_name"):
            violations.append(f"{event_id}: provenance source_name mismatch")
        for field_entries in (prov.get("fields") or {}).values():
            for entry in field_entries or []:
                for raw_ref in entry.get("raw_refs") or []:
                    ref = str(raw_ref)
                    if not ref.startswith("data/raw/") or Path(ref).is_absolute() or (len(ref) >= 2 and ref[1] == ":"):
                        violations.append(f"{event_id}: non-portable raw_ref {ref!r}")
        for entry in prov.get("title_candidates") or []:
            for raw_ref in entry.get("raw_refs") or []:
                ref = str(raw_ref)
                if not ref.startswith("data/raw/") or Path(ref).is_absolute() or (len(ref) >= 2 and ref[1] == ":"):
                    violations.append(f"{event_id}: non-portable title raw_ref {ref!r}")

        new_row = dict(row)
        new_prov = dict(prov)
        new_fields: dict[str, list[dict[str, Any]]] = {}
        source = row.get("source_name")
        for field in ARRAY_FIELDS:
            current_values = _value_list(row, field)
            entries = list((prov.get("fields") or {}).get(field) or [])
            keep_entries: list[dict[str, Any]] = []
            for entry in entries:
                keep = True
                if field == "vendor_case_report_ids" and not _entry_is_structured(entry):
                    keep = False
                    dropped["vendor_case_report_ids.free_text_pattern"] += 1
                if field == "publish_dates" and source == "orkl" and _entry_is_orkl_archive_date(entry):
                    keep = False
                    dropped["publish_dates.orkl_archive_timestamp"] += 1
                if keep:
                    keep_entries.append(entry)
            retained_values = sorted({entry.get("value") for entry in keep_entries if entry.get("value")})
            if set(retained_values) - set(current_values):
                violations.append(f"{event_id}: provenance contains a value absent from candidate row for {field}")
            new_row[field] = retained_values or None
            if keep_entries:
                new_fields[field] = keep_entries
        new_prov["fields"] = new_fields
        normalized_metadata.append(new_row)
        normalized_provenance.append(new_prov)

    normalized_non_attributed = list(non_attributed)
    if len({row.get("event_id") for row in normalized_metadata}) != len(normalized_metadata):
        violations.append("normalized metadata has duplicate event_id values")
    if set(row.get("event_id") for row in normalized_metadata) != set(provenance_by_id):
        violations.append("normalized metadata/provenance event sets differ")
    if not violations:
        source_counts = Counter(row.get("source_name") for row in normalized_metadata)
        expected_source_counts = candidate_summary.get("attributed_events_by_source")
        if dict(sorted(source_counts.items())) != dict(sorted((expected_source_counts or {}).items())):
            violations.append("normalized source counts differ from candidate source counts")

    summary = {
        "contract": "attributed_event_metadata_v1",
        "status": "complete" if not violations else "preflight_failed",
        "document_sha256_included": True,
        "input_counts": EXPECTED_INPUT_COUNTS,
        "total_events": 23_412,
        "attributed_event_count": len(normalized_metadata),
        "non_attributed_event_count": len(normalized_non_attributed),
        "metadata_record_count": len(normalized_metadata),
        "unique_metadata_event_ids": len({row.get("event_id") for row in normalized_metadata}),
        "attributed_events_by_source": dict(sorted(Counter(row.get("source_name") for row in normalized_metadata).items())),
        "field_coverage": {},
        "exception_count": len(exceptions),
        "exception_counts_by_kind": dict(sorted(Counter(row.get("kind") for row in exceptions).items())),
        "preflight": {
            "passed": not violations,
            "violations": violations,
            "candidate_path_retained": False,
            "dropped_inferred_values": dict(sorted(dropped.items())),
            "vendor_id_policy": "structured_keys_only; no free-text pattern inference",
            "orkl_publish_date_policy": "explicit publication date only; source/archive creation dates remain null",
        },
        "policy": {
            "eligibility": "at least one claim_scope=attribution",
            "raw_document_download": False,
            "network_access": False,
            "missing_field_value": None,
            "document_sha256": "source-provided original-document hash only; unavailable remains null",
            "candidate_normalization": True,
        },
    }
    for field in OUTPUT_FIELDS[2:]:
        if field == "title":
            summary["field_coverage"][field] = {
                "non_null": sum(row.get(field) is not None for row in normalized_metadata),
                "null": sum(row.get(field) is None for row in normalized_metadata),
            }
        else:
            summary["field_coverage"][field] = {
                "non_null": sum(row.get(field) is not None for row in normalized_metadata),
                "null": sum(row.get(field) is None for row in normalized_metadata),
                "value_count": sum(len(row.get(field) or []) for row in normalized_metadata),
            }
    return normalized_metadata, normalized_provenance, exceptions, normalized_non_attributed, summary, violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and args.output_dir is None:
        raise SystemExit("--output-dir is required unless --dry-run is used")

    candidate_dir = args.candidate_dir.resolve()
    if not candidate_dir.is_dir():
        raise SystemExit(f"candidate directory does not exist: {candidate_dir}")
    metadata, provenance, exceptions, non_attributed, summary, violations = _normalize(candidate_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.dry_run:
        return 0 if not violations else 2
    if violations:
        raise SystemExit("preflight failed; no output directory was published")

    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise SystemExit(f"refusing to overwrite existing output directory: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=str(output_dir.parent)))
    try:
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
