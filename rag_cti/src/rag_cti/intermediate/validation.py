"""Validation harness for intermediate dataset delivery packages."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from rag_cti.intermediate.contract import CONTROLLED_VOCABULARIES

Severity = Literal["fail", "warn", "report"]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_JSON_FILES = {
    "source_manifest": "source_manifest.json",
    "processing_report": "processing_report.json",
}
_JSONL_FILES = {
    "intermediate_records": "intermediate_records.jsonl",
    "entity_mentions": "entity_mentions.jsonl",
    "relation_mentions": "relation_mentions.jsonl",
    "attribution_signals": "attribution_signals.jsonl",
    "record_features": "record_features.jsonl",
}
_REQUIRED_TOP_LEVEL = {
    "source_manifest": frozenset(
        {"dataset_id", "dataset_version", "schema_version", "generated_at", "sources"}
    ),
    "source_manifest.sources[]": frozenset(
        {
            "connector_source",
            "source_class",
            "publisher_category",
            "record_count",
            "raw_collection",
            "provides",
        }
    ),
    "intermediate_records": frozenset(
        {
            "record_id",
            "raw_ref",
            "source",
            "timestamps",
            "record_signals",
            "counts",
            "processing_status",
        }
    ),
    "entity_mentions": frozenset(
        {
            "entity_mention_id",
            "record_id",
            "raw_value",
            "normalized_value",
            "entity_type",
            "source_field",
            "extraction_method",
            "occurrence_count",
            "value_type",
            "resolution",
            "ambiguity",
            "merge_candidates",
        }
    ),
    "relation_mentions": frozenset(
        {"relation_mention_id", "record_id", "subject", "predicate", "object", "derivation", "ambiguity"}
    ),
    "attribution_signals": frozenset(
        {
            "attribution_signal_id",
            "record_id",
            "signal_type",
            "target_entity_type",
            "raw_label",
            "source_field",
            "derivation_method",
        }
    ),
    "record_features": frozenset(
        {
            "record_id",
            "source_features",
            "timestamp_features",
            "content_features",
            "label_features",
            "ambiguity_features",
        }
    ),
    "processing_report": frozenset(
        {
            "dataset_id",
            "dataset_version",
            "schema_version",
            "generated_at",
            "counts",
            "coverage",
            "warnings",
            "open_issues",
        }
    ),
}
_INTERMEDIATE_RECORD_NESTED_REQUIRED = {
    "source": frozenset({"connector_source", "source_class", "publisher_category"}),
    "timestamps": frozenset({"timestamp_basis"}),
    "record_signals": frozenset({"label_availability"}),
    "processing_status": frozenset({"status"}),
}
_ID_FIELDS = {
    "intermediate_records": "record_id",
    "entity_mentions": "entity_mention_id",
    "relation_mentions": "relation_mention_id",
    "attribution_signals": "attribution_signal_id",
    "record_features": "record_id",
}


@dataclass(frozen=True)
class ValidationMessage:
    severity: Severity
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    messages: tuple[ValidationMessage, ...]

    @property
    def failures(self) -> tuple[ValidationMessage, ...]:
        return tuple(message for message in self.messages if message.severity == "fail")

    @property
    def warnings(self) -> tuple[ValidationMessage, ...]:
        return tuple(message for message in self.messages if message.severity == "warn")

    @property
    def reports(self) -> tuple[ValidationMessage, ...]:
        return tuple(message for message in self.messages if message.severity == "report")

    @property
    def ok(self) -> bool:
        return not self.failures


def validate_delivery(root: Path, legacy: bool = False) -> ValidationResult:
    """Validate one intermediate delivery package.

    ``legacy=True`` preserves compatibility for processed fixtures that predate
    the raw-hash requirement: missing ``raw_sha256`` is a warning instead of a
    failure.
    """
    root = Path(root)
    messages: list[ValidationMessage] = []
    raw_dir = root / "raw"
    intermediate_dir = root / "intermediate"

    _validate_layout(messages, root, raw_dir, intermediate_dir)

    json_objects = _load_json_artifacts(messages, intermediate_dir)
    jsonl_rows = _load_jsonl_artifacts(messages, intermediate_dir)

    manifest = json_objects.get("source_manifest")
    report = json_objects.get("processing_report")

    if isinstance(manifest, dict):
        _validate_manifest(messages, root, manifest)
    if isinstance(report, dict):
        _require_keys(messages, "processing_report", report, "processing_report.json")

    for artifact, rows in jsonl_rows.items():
        for index, row in enumerate(rows, start=1):
            path = f"{_JSONL_FILES[artifact]}:{index}"
            _require_keys(messages, artifact, row, path)
            if artifact == "intermediate_records":
                _require_intermediate_record_nested_keys(messages, row, path)

    _validate_ids(messages, jsonl_rows)
    record_ids = {
        str(row.get("record_id"))
        for row in jsonl_rows["intermediate_records"]
        if row.get("record_id") is not None
    }
    entity_mention_ids = {
        str(row.get("entity_mention_id"))
        for row in jsonl_rows["entity_mentions"]
        if row.get("entity_mention_id") is not None
    }

    _validate_record_joins(messages, jsonl_rows, record_ids)
    _validate_relation_entity_joins(messages, jsonl_rows["relation_mentions"], entity_mention_ids)
    _validate_raw_refs(messages, root, raw_dir, jsonl_rows["intermediate_records"], legacy=legacy)
    _validate_vocabularies(messages, manifest, jsonl_rows)

    if isinstance(manifest, dict):
        _validate_manifest_counts(messages, manifest, jsonl_rows["intermediate_records"])
    if isinstance(report, dict):
        _validate_report_counts(messages, report, jsonl_rows)

    return ValidationResult(tuple(messages))


def _validate_layout(
    messages: list[ValidationMessage], root: Path, raw_dir: Path, intermediate_dir: Path
) -> None:
    if not raw_dir.is_dir():
        _add(messages, "fail", "package_layout", "raw/", "delivery is missing raw/ directory")
    if not intermediate_dir.is_dir():
        _add(
            messages,
            "fail",
            "package_layout",
            "intermediate/",
            "delivery is missing intermediate/ directory",
        )
    projections = root / "projections"
    if projections.exists() and not projections.is_dir():
        _add(
            messages,
            "fail",
            "package_layout",
            "projections/",
            "optional projections path must be a directory when present",
        )

    for filename in (*_JSON_FILES.values(), *_JSONL_FILES.values()):
        path = intermediate_dir / filename
        if not path.is_file():
            _add(messages, "fail", "missing_artifact", f"intermediate/{filename}", "missing artifact")


def _load_json_artifacts(
    messages: list[ValidationMessage], intermediate_dir: Path
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for artifact, filename in _JSON_FILES.items():
        path = intermediate_dir / filename
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            _add(messages, "fail", "json_parse_error", filename, str(exc))
            continue
        if not isinstance(value, dict):
            _add(messages, "fail", "json_parse_error", filename, "artifact must be a JSON object")
            continue
        out[artifact] = value
    return out


def _load_jsonl_artifacts(
    messages: list[ValidationMessage], intermediate_dir: Path
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {artifact: [] for artifact in _JSONL_FILES}
    for artifact, filename in _JSONL_FILES.items():
        path = intermediate_dir / filename
        if not path.is_file():
            continue
        rows: list[dict[str, Any]] = []
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                _add(messages, "fail", "jsonl_parse_error", f"{filename}:{index}", str(exc))
                continue
            if not isinstance(value, dict):
                _add(
                    messages,
                    "fail",
                    "jsonl_parse_error",
                    f"{filename}:{index}",
                    "JSONL row must be a JSON object",
                )
                continue
            rows.append(value)
        out[artifact] = rows
    return out


def _validate_manifest(messages: list[ValidationMessage], root: Path, manifest: dict[str, Any]) -> None:
    _require_keys(messages, "source_manifest", manifest, "source_manifest.json")
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        _add(
            messages,
            "fail",
            "invalid_source_manifest",
            "source_manifest.json:sources",
            "sources must be a list",
        )
        return
    for index, source in enumerate(sources, start=1):
        path = f"source_manifest.json:sources[{index}]"
        if not isinstance(source, dict):
            _add(messages, "fail", "invalid_source_manifest", path, "source entry must be an object")
            continue
        _require_keys(messages, "source_manifest.sources[]", source, path)
        raw_collection = source.get("raw_collection")
        if not isinstance(raw_collection, str) or not raw_collection:
            continue
        if not _is_package_relative_raw_path(raw_collection):
            _add(
                messages,
                "fail",
                "raw_collection_not_package_relative",
                f"{path}.raw_collection",
                "raw_collection must be a package-relative path under raw/",
            )
            continue
        if not (root / raw_collection).exists():
            _add(
                messages,
                "fail",
                "raw_collection_missing",
                f"{path}.raw_collection",
                f"raw_collection does not exist: {raw_collection}",
            )


def _validate_ids(
    messages: list[ValidationMessage], rows_by_artifact: dict[str, list[dict[str, Any]]]
) -> None:
    for artifact, id_field in _ID_FIELDS.items():
        seen: dict[str, str] = {}
        for index, row in enumerate(rows_by_artifact[artifact], start=1):
            value = row.get(id_field)
            if value is None:
                continue
            key = str(value)
            path = f"{_JSONL_FILES[artifact]}:{index}.{id_field}"
            if key in seen:
                _add(
                    messages,
                    "fail",
                    "duplicate_id",
                    path,
                    f"duplicate {id_field} {key!r}; first seen at {seen[key]}",
                )
            else:
                seen[key] = path


def _validate_record_joins(
    messages: list[ValidationMessage],
    rows_by_artifact: dict[str, list[dict[str, Any]]],
    record_ids: set[str],
) -> None:
    for artifact in ("entity_mentions", "relation_mentions", "attribution_signals", "record_features"):
        for index, row in enumerate(rows_by_artifact[artifact], start=1):
            record_id = row.get("record_id")
            if record_id is not None and str(record_id) not in record_ids:
                _add(
                    messages,
                    "fail",
                    "broken_record_join",
                    f"{_JSONL_FILES[artifact]}:{index}.record_id",
                    f"record_id does not exist in intermediate_records: {record_id}",
                )


def _validate_relation_entity_joins(
    messages: list[ValidationMessage],
    relation_rows: list[dict[str, Any]],
    entity_mention_ids: set[str],
) -> None:
    for index, row in enumerate(relation_rows, start=1):
        for side in ("subject", "object"):
            side_value = row.get(side)
            if not isinstance(side_value, dict):
                continue
            mention_id = side_value.get("entity_mention_id")
            if mention_id is not None and str(mention_id) not in entity_mention_ids:
                _add(
                    messages,
                    "fail",
                    "broken_entity_mention_join",
                    f"relation_mentions.jsonl:{index}.{side}.entity_mention_id",
                    f"entity_mention_id does not exist: {mention_id}",
                )


def _validate_raw_refs(
    messages: list[ValidationMessage],
    root: Path,
    raw_dir: Path,
    record_rows: list[dict[str, Any]],
    *,
    legacy: bool,
) -> None:
    for index, row in enumerate(record_rows, start=1):
        path_label = f"intermediate_records.jsonl:{index}.raw_ref"
        raw_ref = row.get("raw_ref")
        if not isinstance(raw_ref, dict):
            _add(messages, "fail", "missing_required_key", path_label, "raw_ref must be an object")
            continue
        raw_path_value = raw_ref.get("raw_path")
        if not isinstance(raw_path_value, str) or not raw_path_value:
            _add(messages, "fail", "missing_required_key", path_label, "raw_ref.raw_path is required")
            continue
        if not _is_package_relative_raw_path(raw_path_value):
            _add(
                messages,
                "fail",
                "raw_ref_not_package_relative",
                f"{path_label}.raw_path",
                "raw_path must be a package-relative path under raw/",
            )
            continue
        raw_path = _resolve_package_path(root, raw_path_value)
        if not _is_under(raw_path, raw_dir):
            _add(
                messages,
                "fail",
                "raw_ref_outside_raw",
                f"{path_label}.raw_path",
                f"raw_path must point inside raw/: {raw_path_value}",
            )
        if not raw_path.is_file():
            _add(
                messages,
                "fail",
                "raw_ref_missing",
                f"{path_label}.raw_path",
                f"raw file does not exist: {raw_path_value}",
            )
            continue

        raw_sha = raw_ref.get("raw_sha256")
        if not raw_sha:
            severity: Severity = "warn" if legacy else "fail"
            _add(
                messages,
                severity,
                "missing_raw_sha256",
                f"{path_label}.raw_sha256",
                "raw_sha256 is required for new delivery packages",
            )
            continue
        if not isinstance(raw_sha, str) or _SHA256.fullmatch(raw_sha) is None:
            _add(
                messages,
                "fail",
                "invalid_raw_sha256",
                f"{path_label}.raw_sha256",
                "raw_sha256 must be a full lowercase SHA-256 hex digest",
            )
            continue
        actual = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        if raw_sha != actual:
            _add(
                messages,
                "fail",
                "raw_sha256_mismatch",
                f"{path_label}.raw_sha256",
                "raw_sha256 does not match delivered raw file",
            )


def _validate_vocabularies(
    messages: list[ValidationMessage],
    manifest: dict[str, Any] | None,
    rows_by_artifact: dict[str, list[dict[str, Any]]],
) -> None:
    if isinstance(manifest, dict):
        sources = manifest.get("sources")
        if isinstance(sources, list):
            for index, source in enumerate(sources, start=1):
                if isinstance(source, dict):
                    path = f"source_manifest.json:sources[{index}]"
                    _check_vocab(messages, source, "connector_source", "connector_source", path)
                    _check_vocab(messages, source, "source_class", "source_class", path)
                    _check_vocab(messages, source, "publisher_category", "publisher_category", path)
                    _warn_unknown_publisher(messages, source.get("publisher_category"), path)

    for index, row in enumerate(rows_by_artifact["intermediate_records"], start=1):
        path = f"intermediate_records.jsonl:{index}"
        source = row.get("source") if isinstance(row.get("source"), dict) else {}
        timestamps = row.get("timestamps") if isinstance(row.get("timestamps"), dict) else {}
        signals = row.get("record_signals") if isinstance(row.get("record_signals"), dict) else {}
        status = row.get("processing_status") if isinstance(row.get("processing_status"), dict) else {}
        _check_vocab(messages, source, "connector_source", "connector_source", f"{path}.source")
        _check_vocab(messages, source, "source_class", "source_class", f"{path}.source")
        _check_vocab(messages, source, "publisher_category", "publisher_category", f"{path}.source")
        _warn_unknown_publisher(messages, source.get("publisher_category"), f"{path}.source")
        _check_vocab(messages, timestamps, "timestamp_basis", "timestamp_basis", f"{path}.timestamps")
        _check_vocab(
            messages, signals, "label_availability", "label_availability", f"{path}.record_signals"
        )
        _check_vocab(
            messages, status, "status", "processing_status.status", f"{path}.processing_status"
        )

    for index, row in enumerate(rows_by_artifact["entity_mentions"], start=1):
        path = f"entity_mentions.jsonl:{index}"
        _check_vocab(messages, row, "entity_type", "entity_type", path)
        _check_vocab(messages, row, "extraction_method", "extraction_method", path)
        _check_vocab(
            messages,
            row.get("ambiguity") if isinstance(row.get("ambiguity"), dict) else {},
            "status",
            "ambiguity.status",
            f"{path}.ambiguity",
        )
        _check_vocab(
            messages,
            row.get("resolution") if isinstance(row.get("resolution"), dict) else {},
            "resolution_method",
            "resolution_method",
            f"{path}.resolution",
        )
        _warn_missing_indicator_type(messages, row, path)

    for index, row in enumerate(rows_by_artifact["relation_mentions"], start=1):
        path = f"relation_mentions.jsonl:{index}"
        _check_vocab(
            messages,
            row.get("subject") if isinstance(row.get("subject"), dict) else {},
            "entity_type",
            "entity_type",
            f"{path}.subject",
        )
        predicate = row.get("predicate") if isinstance(row.get("predicate"), dict) else {}
        _check_vocab(messages, predicate, "mapped_value", "predicate.mapped_value", f"{path}.predicate")
        _check_vocab(
            messages, predicate, "mapping_status", "predicate.mapping_status", f"{path}.predicate"
        )
        if predicate.get("mapping_status") == "document_proposed_unsupported":
            _add(
                messages,
                "report",
                "document_proposed_unsupported_predicate",
                f"{path}.predicate.mapping_status",
                "document-proposed unsupported predicate was reported by the delivery",
            )
        _check_vocab(
            messages,
            row.get("object") if isinstance(row.get("object"), dict) else {},
            "entity_type",
            "entity_type",
            f"{path}.object",
        )
        derivation = row.get("derivation") if isinstance(row.get("derivation"), dict) else {}
        _check_vocab(messages, derivation, "extraction_method", "extraction_method", f"{path}.derivation")
        _check_vocab(messages, derivation, "derivation_method", "extraction_method", f"{path}.derivation")
        _check_vocab(
            messages, derivation, "label_availability", "label_availability", f"{path}.derivation"
        )
        _check_vocab(
            messages,
            row.get("ambiguity") if isinstance(row.get("ambiguity"), dict) else {},
            "status",
            "ambiguity.status",
            f"{path}.ambiguity",
        )

    for index, row in enumerate(rows_by_artifact["attribution_signals"], start=1):
        path = f"attribution_signals.jsonl:{index}"
        _check_vocab(messages, row, "signal_type", "signal_type", path)
        _check_vocab(messages, row, "target_entity_type", "entity_type", path)
        _check_vocab(messages, row, "derivation_method", "extraction_method", path)

    for index, row in enumerate(rows_by_artifact["record_features"], start=1):
        path = f"record_features.jsonl:{index}"
        source = row.get("source_features") if isinstance(row.get("source_features"), dict) else {}
        timestamp = (
            row.get("timestamp_features") if isinstance(row.get("timestamp_features"), dict) else {}
        )
        label = row.get("label_features") if isinstance(row.get("label_features"), dict) else {}
        _check_vocab(messages, source, "connector_source", "connector_source", f"{path}.source_features")
        _check_vocab(messages, source, "source_class", "source_class", f"{path}.source_features")
        _check_vocab(
            messages, source, "publisher_category", "publisher_category", f"{path}.source_features"
        )
        _warn_unknown_publisher(messages, source.get("publisher_category"), f"{path}.source_features")
        _check_vocab(
            messages, timestamp, "timestamp_basis", "timestamp_basis", f"{path}.timestamp_features"
        )
        _check_vocab(messages, label, "label_availability", "label_availability", f"{path}.label_features")


def _validate_manifest_counts(
    messages: list[ValidationMessage],
    manifest: dict[str, Any],
    record_rows: list[dict[str, Any]],
) -> None:
    counts = Counter(
        source.get("connector_source")
        for row in record_rows
        if isinstance(source := row.get("source"), dict)
    )
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        return
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            continue
        connector = source.get("connector_source")
        expected = source.get("record_count")
        if connector is None or expected is None:
            continue
        if not isinstance(expected, int):
            _add(
                messages,
                "fail",
                "invalid_source_manifest",
                f"source_manifest.json:sources[{index}].record_count",
                "record_count must be an integer",
            )
            continue
        actual = counts.get(connector, 0)
        if actual != expected:
            _add(
                messages,
                "fail",
                "manifest_record_count_mismatch",
                f"source_manifest.json:sources[{index}].record_count",
                f"record_count={expected} but intermediate_records has {actual}",
            )


def _validate_report_counts(
    messages: list[ValidationMessage],
    report: dict[str, Any],
    rows_by_artifact: dict[str, list[dict[str, Any]]],
) -> None:
    counts = report.get("counts")
    if not isinstance(counts, dict):
        _add(
            messages,
            "warn",
            "processing_report_missing_count",
            "processing_report.json:counts",
            "processing_report counts must be an object",
        )
        return
    expected = {
        "intermediate_records": len(rows_by_artifact["intermediate_records"]),
        "entity_mentions": len(rows_by_artifact["entity_mentions"]),
        "relation_mentions": len(rows_by_artifact["relation_mentions"]),
        "attribution_signals": len(rows_by_artifact["attribution_signals"]),
    }
    for key, value in expected.items():
        if key not in counts:
            _add(
                messages,
                "warn",
                "processing_report_missing_count",
                f"processing_report.json:counts.{key}",
                f"processing_report is missing {key} count",
            )
        elif counts[key] != value:
            _add(
                messages,
                "warn",
                "processing_report_count_mismatch",
                f"processing_report.json:counts.{key}",
                f"processing_report count {counts[key]!r} does not match observed {value}",
            )
    if "warnings" not in counts:
        _add(
            messages,
            "warn",
            "processing_report_missing_count",
            "processing_report.json:counts.warnings",
            "processing_report is missing warnings count",
        )


def _require_keys(
    messages: list[ValidationMessage], artifact: str, row: dict[str, Any], path: str
) -> None:
    for key in sorted(_REQUIRED_TOP_LEVEL[artifact] - row.keys()):
        _add(messages, "fail", "missing_required_key", f"{path}.{key}", f"missing key {key!r}")


def _require_intermediate_record_nested_keys(
    messages: list[ValidationMessage], row: dict[str, Any], path: str
) -> None:
    for parent, keys in _INTERMEDIATE_RECORD_NESTED_REQUIRED.items():
        value = row.get(parent)
        parent_path = f"{path}.{parent}"
        if not isinstance(value, dict):
            _add(
                messages,
                "fail",
                "missing_required_key",
                parent_path,
                f"{parent!r} must be an object with required contract fields",
            )
            continue
        for key in sorted(keys):
            if value.get(key) is None:
                _add(
                    messages,
                    "fail",
                    "missing_required_key",
                    f"{parent_path}.{key}",
                    f"missing key {key!r}",
                )


def _check_vocab(
    messages: list[ValidationMessage],
    row: dict[str, Any],
    key: str,
    vocab_key: str,
    path: str,
) -> None:
    if key not in row or row.get(key) is None:
        return
    value = row[key]
    allowed = CONTROLLED_VOCABULARIES[vocab_key]
    if not isinstance(value, str) or value not in allowed:
        _add(
            messages,
            "fail",
            "invalid_vocabulary",
            f"{path}.{key}",
            f"{value!r} is not in controlled vocabulary {vocab_key}",
        )


def _warn_unknown_publisher(
    messages: list[ValidationMessage], value: Any, path: str
) -> None:
    if value == "unknown":
        _add(
            messages,
            "warn",
            "missing_source_backed_field",
            f"{path}.publisher_category",
            "publisher_category is unknown",
        )


def _warn_missing_indicator_type(
    messages: list[ValidationMessage], row: dict[str, Any], path: str
) -> None:
    if row.get("entity_type") != "indicator":
        return
    value_type = row.get("value_type")
    if not isinstance(value_type, dict) or not value_type.get("raw") or not value_type.get("canonical"):
        _add(
            messages,
            "warn",
            "missing_source_backed_field",
            f"{path}.value_type",
            "indicator mention is missing raw or canonical indicator type",
        )


def _resolve_package_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _is_package_relative_raw_path(value: str) -> bool:
    path = Path(value)
    parts = path.parts
    return not path.is_absolute() and bool(parts) and parts[0] == "raw" and ".." not in parts


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _add(
    messages: list[ValidationMessage],
    severity: Severity,
    code: str,
    path: str,
    message: str,
) -> None:
    messages.append(ValidationMessage(severity, code, path, message))
