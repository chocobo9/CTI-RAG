"""Normalize the collected OTX infrastructure ledger for EviTRAIL.

The collector ledger is the authority for task terminal state.  Raw response
wrappers remain immutable; this module reads one wrapper at a time and emits
flat JSONL rows accepted by EviTRAIL's ``read_cached_infrastructure`` reader.
"""

from __future__ import annotations

import hashlib
import importlib
import ipaddress
import json
import re
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

DEFAULT_SNAPSHOT_PULSE_COUNT = 17_454
EVITRAIL_CONSUMER_REVISION = "da4a29e8ce25cff8cbddebb444b069296f949511"
EVITRAIL_READER = "evitrail.data.readers.read_cached_infrastructure"
TERMINAL_STATUSES = frozenset(
    {"written", "empty", "reused", "terminal_error", "retry_exhausted"}
)


def _jsonl_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            yield value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raw_path(collection_root: Path, raw_ref: str) -> Path:
    path = Path(raw_ref)
    return path if path.is_absolute() else collection_root / path


def _asn_name(value: Any) -> str | None:
    match = re.match(r"(?i)^\s*AS\s*\d+\s+(.+?)\s*$", str(value or ""))
    return match.group(1) if match else None


def _ip_general_row(
    ledger_row: dict[str, Any],
    raw_wrapper: dict[str, Any],
) -> dict[str, Any]:
    payload = (
        raw_wrapper.get("payload")
        if isinstance(raw_wrapper.get("payload"), dict)
        else {}
    )
    ip = payload.get("ip") or payload.get("address") or payload.get("indicator")
    asn = payload.get("asn_number") or payload.get("asn") or payload.get(
        "autonomous_system"
    )
    row = {
        **_outcome_row(ledger_row, raw_wrapper),
        "asn": asn,
        "asn_name": payload.get("asn_name")
        or payload.get("asn_description")
        or payload.get("as_owner")
        or _asn_name(asn),
        "collected_at": raw_wrapper.get("fetched_at"),
        "country_code": payload.get("country_code"),
        "ip": ip,
    }
    return {key: value for key, value in row.items() if value not in (None, "")}


def _outcome_row(
    ledger_row: dict[str, Any],
    raw_wrapper: dict[str, Any] | None,
) -> dict[str, Any]:
    wrapper = raw_wrapper or {}
    row = {
        "attempts": ledger_row.get("attempts"),
        "collected_at": wrapper.get("fetched_at"),
        "collection_error": ledger_row.get("error"),
        "collection_source": ledger_row.get("source"),
        "collection_status": ledger_row.get("status"),
        "elapsed_seconds": ledger_row.get("elapsed_seconds"),
        "endpoint": ledger_row.get("endpoint"),
        "finished_at": ledger_row.get("finished_at"),
        "http_status": ledger_row.get("http_status"),
        "ioc": ledger_row.get("value"),
        "ioc_type": ledger_row.get("seed_type"),
        "raw_ref": ledger_row.get("raw_ref"),
        "source": wrapper.get("source")
        or ledger_row.get("source")
        or f"otx_{ledger_row.get('endpoint')}",
        "task_id": ledger_row.get("task_id"),
    }
    return {key: value for key, value in row.items() if value not in (None, "")}


def _is_ip(value: Any) -> bool:
    try:
        ipaddress.ip_address(str(value or ""))
    except ValueError:
        return False
    return True


def _pdns_rows(
    ledger_row: dict[str, Any],
    raw_wrapper: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    payload = (
        raw_wrapper.get("payload")
        if isinstance(raw_wrapper.get("payload"), dict)
        else {}
    )
    records = payload.get("passive_dns")
    if not isinstance(records, list) or not records:
        yield _outcome_row(ledger_row, raw_wrapper)
        return
    base = _outcome_row(ledger_row, raw_wrapper)
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        value = {**base, **record}
        address = record.get("ip") or record.get("address")
        if _is_ip(address):
            value["ip"] = address
        hostname = record.get("domain") or record.get("hostname") or record.get("host")
        if hostname:
            value["domain"] = hostname
        asn = record.get("asn_number") or record.get("asn") or record.get(
            "autonomous_system"
        )
        if asn:
            value["asn"] = asn
            value["asn_name"] = (
                record.get("asn_name")
                or record.get("asn_description")
                or record.get("as_owner")
                or _asn_name(asn)
            )
        if record.get("first"):
            value["first_seen"] = record["first"]
        if record.get("last"):
            value["last_seen"] = record["last"]
        value["source_record_path"] = f"payload.passive_dns[{index}]"
        yield {
            key: item
            for key, item in value.items()
            if item not in (None, "")
        }


def _normalized_rows(
    ledger_row: dict[str, Any],
    collection_root: Path,
) -> Iterator[dict[str, Any]]:
    status = str(ledger_row.get("status") or "")
    if status not in TERMINAL_STATUSES:
        raise ValueError(
            f"task {ledger_row.get('task_id')}: unsupported terminal status {status!r}"
        )
    raw_wrapper: dict[str, Any] | None = None
    raw_ref = str(ledger_row.get("raw_ref") or "")
    if raw_ref:
        raw_value = json.loads(
            _raw_path(collection_root, raw_ref).read_text(encoding="utf-8")
        )
        if not isinstance(raw_value, dict):
            raise ValueError(f"{raw_ref}: expected a JSON object")
        raw_wrapper = raw_value

    endpoint = str(ledger_row.get("endpoint") or "")
    if endpoint == "ip_general" and raw_wrapper is not None:
        yield _ip_general_row(ledger_row, raw_wrapper)
    elif endpoint in {"domain_pdns", "ip_pdns"} and raw_wrapper is not None:
        yield from _pdns_rows(ledger_row, raw_wrapper)
    else:
        yield _outcome_row(ledger_row, raw_wrapper)


def normalize_otx_enrichment_ledger(
    *,
    ledger_path: Path,
    output_path: Path,
    manifest_path: Path,
    subset_pulse_count: int,
    snapshot_pulse_count: int = DEFAULT_SNAPSHOT_PULSE_COUNT,
    include_task_ids: set[str] | None = None,
    evitrail_root: Path | None = None,
) -> dict[str, Any]:
    """Write normalized rows and an explicit partial-coverage manifest."""
    if output_path.resolve() == manifest_path.resolve():
        raise ValueError("output and manifest must be different versioned artifacts")
    existing = [path for path in (output_path, manifest_path) if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite versioned artifact: "
            + ", ".join(str(path) for path in existing)
        )
    collection_root = ledger_path.resolve().parent
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".tmp")
    status_counts: Counter[str] = Counter()
    output_rows = 0
    ledger_rows = 0
    examined_ledger_rows = 0
    selected_task_ids: set[str] = set()

    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as output:
            for ledger_row in _jsonl_rows(ledger_path):
                examined_ledger_rows += 1
                task_id = str(ledger_row.get("task_id") or "")
                if include_task_ids is not None and task_id not in include_task_ids:
                    continue
                ledger_rows += 1
                if task_id:
                    selected_task_ids.add(task_id)
                status = str(ledger_row.get("status") or "")
                status_counts[status] += 1
                for normalized_row in _normalized_rows(
                    ledger_row,
                    collection_root,
                ):
                    output.write(
                        json.dumps(
                            normalized_row,
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    output_rows += 1
        temporary.replace(output_path)
    finally:
        if temporary.exists():
            temporary.unlink()

    manifest: dict[str, Any] = {
        "contract": "evitrail_otx_enrichment_input_v1",
        "coverage": {
            "full_snapshot_coverage": False,
            "scope": "partial",
            "subset_pulse_count": subset_pulse_count,
            "snapshot_pulse_count": snapshot_pulse_count,
        },
        "consumer_validation": {
            "reader": EVITRAIL_READER,
            "revision": EVITRAIL_CONSUMER_REVISION,
            "scope": "not_run",
            "status": "not_run",
        },
        "input": {
            "ledger_hash_scope": "complete_file",
            "ledger_portable_ref": ledger_path.name,
            "ledger_sha256": _sha256(ledger_path),
        },
        "ledger_rows": ledger_rows,
        "ledger_rows_examined": examined_ledger_rows,
        "normalized_output": {
            "hash_scope": "complete_file",
            "portable_ref": output_path.name,
            "sha256": _sha256(output_path),
        },
        "output_rows": output_rows,
        "status_counts": dict(sorted(status_counts.items())),
    }
    if include_task_ids is not None:
        manifest["sample"] = {
            "requested_task_ids": sorted(include_task_ids),
            "selected_task_ids": sorted(selected_task_ids),
            "missing_task_ids": sorted(include_task_ids - selected_task_ids),
        }
    if evitrail_root is not None:
        manifest["consumer_validation"] = _validate_consumer_output(
            output_path,
            evitrail_root,
            "sample" if include_task_ids is not None else "full_normalized_input",
        )
    manifest_temporary = manifest_path.with_name(manifest_path.name + ".tmp")
    try:
        with manifest_temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        manifest_temporary.replace(manifest_path)
    finally:
        if manifest_temporary.exists():
            manifest_temporary.unlink()
    return manifest


def _validate_consumer_output(
    output_path: Path,
    evitrail_root: Path,
    scope: str,
) -> dict[str, Any]:
    root = str(evitrail_root.resolve())
    sys.path.insert(0, root)
    try:
        readers = importlib.import_module("evitrail.data.readers")
        reader_path = Path(str(readers.__file__)).resolve()
        try:
            reader_path.relative_to(Path(root))
        except ValueError:
            raise ImportError(
                f"loaded EviTRAIL reader outside requested root: {reader_path}"
            ) from None
        bundle = readers.read_cached_infrastructure(str(output_path))
    finally:
        if sys.path and sys.path[0] == root:
            sys.path.pop(0)
    collection_status_counts = Counter(
        str(observation.values.get("collection_status"))
        for observation in bundle.enrichments
    )
    relation_counts = Counter(relation.relation for relation in bundle.relations)
    return {
        "collection_status_counts": dict(sorted(collection_status_counts.items())),
        "reader": EVITRAIL_READER,
        "reader_stats": bundle.reader_stats.get("otx", {}),
        "relation_counts": dict(sorted(relation_counts.items())),
        "revision": EVITRAIL_CONSUMER_REVISION,
        "scope": scope,
        "status": "passed",
    }
