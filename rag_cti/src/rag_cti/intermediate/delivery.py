"""Assemble source-slice intermediate packages into one delivery."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from rag_cti.intermediate.infrastructure import build_infrastructure_intermediate_package
from rag_cti.intermediate.jsonl import write_jsonl
from rag_cti.intermediate.mitre import build_mitre_intermediate_package
from rag_cti.intermediate.otx import build_otx_intermediate_package
from rag_cti.intermediate.validation import ValidationResult, validate_delivery

_SCHEMA_VERSION = "v0.1"
_JSONL_ARTIFACTS = (
    "intermediate_records",
    "entity_mentions",
    "relation_mentions",
    "attribution_signals",
    "record_features",
)
_JSONL_FILENAMES = {
    "intermediate_records": "intermediate_records.jsonl",
    "entity_mentions": "entity_mentions.jsonl",
    "relation_mentions": "relation_mentions.jsonl",
    "attribution_signals": "attribution_signals.jsonl",
    "record_features": "record_features.jsonl",
}
_SOURCE_IDENTITY_FIELDS = (
    "connector_source",
    "source_class",
    "publisher_category",
    "raw_collection",
    "provides",
)


class DeliveryAssemblyError(RuntimeError):
    """Raised when source slices cannot be assembled safely."""


@dataclass(frozen=True)
class DeliveryRows:
    intermediate_records: list[dict[str, Any]]
    entity_mentions: list[dict[str, Any]]
    relation_mentions: list[dict[str, Any]]
    attribution_signals: list[dict[str, Any]]
    record_features: list[dict[str, Any]]
    warnings: list[str]
    open_issues: list[str]


@dataclass(frozen=True)
class DeliveryBuildResult:
    rows: DeliveryRows
    validation: ValidationResult


def build_intermediate_delivery_package(
    *,
    output_dir: Path,
    dataset_id: str,
    dataset_version: str,
    generated_at: str,
    fetched_at: str,
    otx_pulses: Iterable[Mapping[str, Any]] = (),
    mitre_objects: Iterable[Mapping[str, Any]] = (),
    pdns_records: Iterable[Mapping[str, Any]] = (),
    vt_records: Iterable[Mapping[str, Any]] = (),
    vt_payloads: Iterable[Mapping[str, Any]] = (),
    schema_version: str = _SCHEMA_VERSION,
    actor_resolutions: Mapping[str, Mapping[str, str | None]] | None = None,
) -> DeliveryBuildResult:
    """Build a sampled v0.1 delivery package from raw source-slice inputs."""
    output_dir = Path(output_dir)
    temp_parent = output_dir.parent
    temp_parent.mkdir(parents=True, exist_ok=True)
    otx_pulses = list(otx_pulses)
    mitre_objects = list(mitre_objects)
    pdns_records = list(pdns_records)
    vt_records = list(vt_records)
    vt_payloads = list(vt_payloads)

    with TemporaryDirectory(prefix=".tmp-intermediate-", dir=temp_parent) as temp_root_name:
        temp_root = Path(temp_root_name)
        source_packages: list[Path] = []

        if otx_pulses:
            source_dir = temp_root / "otx"
            build_otx_intermediate_package(
                otx_pulses,
                source_dir,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                generated_at=generated_at,
                fetched_at=fetched_at,
                schema_version=schema_version,
                actor_resolutions=actor_resolutions,
            )
            source_packages.append(source_dir)

        if mitre_objects:
            source_dir = temp_root / "mitre"
            build_mitre_intermediate_package(
                mitre_objects,
                source_dir,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                generated_at=generated_at,
                fetched_at=fetched_at,
                schema_version=schema_version,
            )
            source_packages.append(source_dir)

        if pdns_records or vt_records or vt_payloads:
            source_dir = temp_root / "infrastructure"
            build_infrastructure_intermediate_package(
                pdns_records=pdns_records,
                vt_records=vt_records,
                vt_payloads=vt_payloads,
                output_dir=source_dir,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                generated_at=generated_at,
                fetched_at=fetched_at,
                schema_version=schema_version,
            )
            source_packages.append(source_dir)

        return assemble_intermediate_delivery_package(
            source_packages,
            output_dir=output_dir,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            generated_at=generated_at,
            schema_version=schema_version,
        )


def assemble_intermediate_delivery_package(
    source_packages: Iterable[Path],
    *,
    output_dir: Path,
    dataset_id: str,
    dataset_version: str,
    generated_at: str,
    schema_version: str = _SCHEMA_VERSION,
) -> DeliveryBuildResult:
    """Merge already-built source-slice packages into one validated delivery."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "raw").mkdir(parents=True, exist_ok=True)
    intermediate_dir = output_dir / "intermediate"
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    rows_by_artifact: dict[str, list[dict[str, Any]]] = {
        artifact: [] for artifact in _JSONL_ARTIFACTS
    }
    source_entries: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    open_issues: list[str] = []

    source_packages = [Path(package_dir) for package_dir in source_packages]
    for package_dir in source_packages:
        _copy_raw_tree(package_dir, output_dir)

    for package_dir in source_packages:
        package_dir = Path(package_dir)
        manifest = _read_json(package_dir / "intermediate" / "source_manifest.json")
        report = _read_json(package_dir / "intermediate" / "processing_report.json")
        _merge_sources(source_entries, manifest)
        warnings.extend(_strings(report.get("warnings")))
        open_issues.extend(_strings(report.get("open_issues")))
        for artifact, filename in _JSONL_FILENAMES.items():
            rows_by_artifact[artifact].extend(
                _read_jsonl(package_dir / "intermediate" / filename)
            )

    source_manifest = {
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "schema_version": schema_version,
        "generated_at": generated_at,
        "sources": [source_entries[key] for key in sorted(source_entries)],
    }
    rows = DeliveryRows(
        intermediate_records=rows_by_artifact["intermediate_records"],
        entity_mentions=rows_by_artifact["entity_mentions"],
        relation_mentions=rows_by_artifact["relation_mentions"],
        attribution_signals=rows_by_artifact["attribution_signals"],
        record_features=rows_by_artifact["record_features"],
        warnings=warnings,
        open_issues=sorted(set(open_issues)),
    )
    processing_report = _processing_report(
        dataset_id,
        dataset_version,
        schema_version,
        generated_at,
        rows,
    )

    _write_json(intermediate_dir / "source_manifest.json", source_manifest)
    for artifact, filename in _JSONL_FILENAMES.items():
        write_jsonl(intermediate_dir / filename, rows_by_artifact[artifact])
    _write_json(intermediate_dir / "processing_report.json", processing_report)

    validation = validate_delivery(output_dir)
    if not validation.ok:
        details = "; ".join(
            f"{message.code} at {message.path}: {message.message}"
            for message in validation.failures
        )
        raise DeliveryAssemblyError(f"assembled delivery failed validation: {details}")
    return DeliveryBuildResult(rows=rows, validation=validation)


def _copy_raw_tree(source_package: Path, output_dir: Path) -> None:
    raw_dir = source_package / "raw"
    if not raw_dir.exists():
        return
    for source_path in sorted(path for path in raw_dir.rglob("*") if path.is_file()):
        relative_path = source_path.relative_to(source_package)
        target_path = output_dir / relative_path
        if target_path.exists():
            raise DeliveryAssemblyError(
                f"raw path conflict while assembling delivery: {relative_path.as_posix()}"
            )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)


def _merge_sources(target: dict[str, dict[str, Any]], manifest: Mapping[str, Any]) -> None:
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise DeliveryAssemblyError("source_manifest.json sources must be a list")
    for source in sources:
        if not isinstance(source, Mapping):
            raise DeliveryAssemblyError("source_manifest.json source entry must be an object")
        record_count = source.get("record_count")
        if not isinstance(record_count, int):
            raise DeliveryAssemblyError("source_manifest.json source record_count must be an int")
        if record_count == 0:
            continue
        connector_source = source.get("connector_source")
        if not isinstance(connector_source, str) or not connector_source:
            raise DeliveryAssemblyError("source_manifest.json source connector_source is required")
        source_entry = dict(source)
        if connector_source not in target:
            target[connector_source] = source_entry
            continue
        existing = target[connector_source]
        for field in _SOURCE_IDENTITY_FIELDS:
            if existing.get(field) != source_entry.get(field):
                raise DeliveryAssemblyError(
                    f"conflicting source manifest metadata for {connector_source}: {field}"
                )
        existing["record_count"] += record_count


def _processing_report(
    dataset_id: str,
    dataset_version: str,
    schema_version: str,
    generated_at: str,
    rows: DeliveryRows,
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "schema_version": schema_version,
        "generated_at": generated_at,
        "counts": {
            "intermediate_records": len(rows.intermediate_records),
            "entity_mentions": len(rows.entity_mentions),
            "relation_mentions": len(rows.relation_mentions),
            "attribution_signals": len(rows.attribution_signals),
            "warnings": len(rows.warnings),
        },
        "coverage": {
            "connector_sources": dict(
                sorted(
                    Counter(
                        row["source"]["connector_source"]
                        for row in rows.intermediate_records
                    ).items()
                )
            ),
            "entity_types": dict(
                sorted(Counter(row["entity_type"] for row in rows.entity_mentions).items())
            ),
            "relation_predicates": dict(
                sorted(
                    Counter(
                        row["predicate"]["mapped_value"] for row in rows.relation_mentions
                    ).items()
                )
            ),
            "attribution_signal_types": dict(
                sorted(Counter(row["signal_type"] for row in rows.attribution_signals).items())
            ),
        },
        "warnings": rows.warnings,
        "open_issues": rows.open_issues,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DeliveryAssemblyError(f"missing source package artifact: {path}") from exc
    if not isinstance(value, dict):
        raise DeliveryAssemblyError(f"JSON artifact must be an object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise DeliveryAssemblyError(f"missing source package artifact: {path}") from exc
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise DeliveryAssemblyError(f"JSONL row must be an object: {path}")
        rows.append(value)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
