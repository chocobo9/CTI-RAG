"""Bounded-memory projection of immutable OTX wrappers to EviTRAIL handoff."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import sqlite3
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from rag_cti.intermediate.otx_source_claims import (
    OTXSourceClaimNormalizer,
    _parse_claims,
)


@dataclass(frozen=True)
class OTXDeliveryResult:
    output_dir: Path
    event_count: int
    node_count: int
    edge_count: int
    claim_count: int
    rejected_count: int
    content_sha256: str
    shard_count: int
    handoff_dirs: tuple[Path, ...]


def build_otx_delivery(
    raw_root: Path,
    output_dir: Path,
    *,
    discovery_evidence: Path | None = None,
    mitre_attack_path: Path | None = None,
    events_per_shard: int = 1000,
    max_indicator_occurrences_per_shard: int = 250_000,
    expected_event_count: int | None = None,
    include_source_ids: Iterable[str] | None = None,
) -> OTXDeliveryResult:
    """Build one deterministic, consumer-readable OTX handoff.

    Only one wrapper is held in memory at a time. Global deduplication and
    deterministic ordering use a temporary SQLite database inside the output
    directory; the database is removed after a successful build.
    """

    raw_root = Path(raw_root)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    if not raw_root.is_dir():
        raise NotADirectoryError(raw_root)
    if events_per_shard < 1:
        raise ValueError("events_per_shard must be positive")
    if max_indicator_occurrences_per_shard < 1:
        raise ValueError(
            "max_indicator_occurrences_per_shard must be positive"
        )
    if expected_event_count is not None and expected_event_count < 1:
        raise ValueError("expected_event_count must be positive")
    output_dir.mkdir(parents=True)
    database_path = output_dir / "_build.sqlite3"
    connection = sqlite3.connect(database_path)
    selected_source_ids = (
        _normalize_include_source_ids(include_source_ids)
        if include_source_ids is not None
        else None
    )
    try:
        _create_schema(connection)
        _index_wrappers(connection, raw_root, selected_source_ids)
        if discovery_evidence is not None:
            _index_discovery(connection, Path(discovery_evidence))
        normalizer = (
            OTXSourceClaimNormalizer(Path(mitre_attack_path))
            if mitre_attack_path is not None
            else None
        )
        _project_latest_wrappers(
            connection,
            normalizer,
            events_per_shard,
            max_indicator_occurrences_per_shard,
        )
        connection.commit()
        counts, shard_rows, handoff_dirs = _write_handoff(
            connection, output_dir
        )
        if (
            expected_event_count is not None
            and counts["events"] != expected_event_count
        ):
            raise ValueError(
                f"expected {expected_event_count} Events, "
                f"built {counts['events']}"
            )
    finally:
        connection.close()

    database_path.unlink()
    population_scope = (
        "selected_delta"
        if selected_source_ids is not None
        else "raw_root_latest"
    )
    selected_source_id_count = (
        len(selected_source_ids)
        if selected_source_ids is not None
        else None
    )
    selected_delta_complete = (
        counts["events"] == selected_source_id_count
        if selected_source_id_count is not None
        else None
    )
    full_latest_snapshot = (
        selected_source_ids is None and expected_event_count is not None
    )
    validation = {
        "status": "builder_checks_passed",
        "validation_scope": {
            "input": "only the raw_root supplied to this invocation",
            "population_scope": population_scope,
            "selected_source_id_count": selected_source_id_count,
            "selected_delta_complete": selected_delta_complete,
            "full_latest_snapshot": full_latest_snapshot,
            "expected_event_count": expected_event_count,
            "exact_current_evitrail_consumer": "not_run_by_builder",
            "claim": "artifact shape and builder invariants only",
        },
        "consumer_contract_target": "EviTRAIL five-file handoff per shard",
        "checks": {
            "strict_five_files_per_shard": True,
            "flat_full_handoff_absent": True,
            "sqlite_staging_removed": True,
            "portable_raw_reference_policy": "data/raw/...",
            "expected_event_count_match": (
                counts["events"] == expected_event_count
                if expected_event_count is not None
                else None
            ),
        },
        "node_types": ["event", "domain", "ip", "url", "asn"],
        "claim_policy": {
            "adversary": {"claim_scope": "attribution", "usage": "candidate"},
            "tags": {
                "claim_scope": "report_context",
                "usage": "provenance_only",
            },
            "discovery_query": {
                "claim_scope": "discovery_only",
                "usage": "provenance_only",
            },
        },
        "counts": counts,
    }
    _write_json(output_dir / "validation.json", validation)
    content_hash = _content_hash(output_dir)
    manifest = {
        "format": "evitrail-otx-five-file-handoff",
        "format_version": 1,
        "source": "otx",
        "source_root": "data/raw/otx",
        "raw_inputs_are_read_only": True,
        "snapshot_expectation": {
            "population_scope": population_scope,
            "selected_source_id_count": selected_source_id_count,
            "selected_delta_complete": selected_delta_complete,
            "full_latest_snapshot": full_latest_snapshot,
            "expected_event_count": expected_event_count,
            "event_count_match": (
                counts["events"] == expected_event_count
                if expected_event_count is not None
                else None
            ),
        },
        "bounded_memory": {
            "strategy": "one_raw_wrapper_at_a_time_with_sqlite_global_index",
            "staging_database_removed": True,
            "events_per_shard": events_per_shard,
            "max_indicator_occurrences_per_shard": (
                max_indicator_occurrences_per_shard
            ),
            "flat_full_handoff_written": False,
        },
        "sharding_policy": {
            "algorithm": "greedy_in_stable_event_id_order",
            "events_per_shard": events_per_shard,
            "max_indicator_occurrences_per_shard": (
                max_indicator_occurrences_per_shard
            ),
            "single_event_oversize_policy": (
                "retain_whole_event_in_own_shard"
            ),
        },
        "event_count": counts["events"],
        "node_count": counts["nodes"],
        "edge_count": counts["edges"],
        "claim_count": counts["claims"],
        "rejected_count": counts["rejected"],
        "content_sha256": content_hash,
        "content_hash_scope": {
            "algorithm": "sha256",
            "includes": [
                "validation.json",
                "shards/*/nodes.jsonl",
                "shards/*/edges.jsonl",
                "shards/*/events.jsonl",
                "shards/*/source_claims.jsonl",
                "shards/*/rejected_records.jsonl",
            ],
            "excludes": ["manifest.json"],
            "path_names_are_hashed": True,
            "file_bytes_are_streamed_in_1_mib_chunks": True,
        },
        "shards": shard_rows,
        "files": ["validation.json"],
    }
    _write_json(output_dir / "manifest.json", manifest)
    return OTXDeliveryResult(
        output_dir=output_dir,
        event_count=counts["events"],
        node_count=counts["nodes"],
        edge_count=counts["edges"],
        claim_count=counts["claims"],
        rejected_count=counts["rejected"],
        content_sha256=content_hash,
        shard_count=len(handoff_dirs),
        handoff_dirs=handoff_dirs,
    )


def _normalize_include_source_ids(values: Iterable[str]) -> set[str]:
    source_ids: set[str] = set()
    for value in values:
        source_id = str(value).strip()
        if source_id.startswith("event:otx:"):
            source_id = source_id.removeprefix("event:otx:").strip()
        if source_id:
            source_ids.add(source_id)
    return source_ids


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        -- The database is disposable staging inside a fresh output directory.
        -- Final JSONL is written only after the build succeeds, so journaling
        -- would only duplicate tens of millions of bulk projection writes.
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA locking_mode=EXCLUSIVE;
        PRAGMA temp_store=MEMORY;
        PRAGMA cache_size=-524288;
        CREATE TABLE snapshots(
          event_id TEXT NOT NULL,
          fetched_at TEXT NOT NULL,
          raw_path TEXT NOT NULL,
          raw_ref TEXT NOT NULL,
          PRIMARY KEY(event_id, fetched_at, raw_path)
        ) WITHOUT ROWID;
        CREATE TABLE discovery(
          pulse_id TEXT NOT NULL,
          ordinal INTEGER NOT NULL,
          row_json TEXT NOT NULL,
          PRIMARY KEY(pulse_id, ordinal)
        ) WITHOUT ROWID;
        CREATE TABLE shard_assignments(
          event_id TEXT PRIMARY KEY,
          shard_id INTEGER NOT NULL,
          raw_indicator_occurrence_count INTEGER NOT NULL,
          occurrence_cap_oversize INTEGER NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE nodes(
          shard_id INTEGER NOT NULL,
          node_id TEXT NOT NULL,
          type TEXT NOT NULL,
          row_json TEXT NOT NULL,
          PRIMARY KEY(shard_id,node_id)
        ) WITHOUT ROWID;
        CREATE TABLE edges(
          shard_id INTEGER NOT NULL,
          edge_id TEXT NOT NULL,
          row_json TEXT NOT NULL,
          PRIMARY KEY(shard_id,edge_id)
        ) WITHOUT ROWID;
        CREATE TABLE events(
          shard_id INTEGER NOT NULL,
          event_id TEXT NOT NULL,
          row_json TEXT NOT NULL,
          PRIMARY KEY(shard_id,event_id)
        ) WITHOUT ROWID;
        CREATE TABLE claims(
          shard_id INTEGER NOT NULL,
          claim_id TEXT NOT NULL,
          row_json TEXT NOT NULL,
          PRIMARY KEY(shard_id,claim_id)
        ) WITHOUT ROWID;
        CREATE TABLE rejected(
          shard_id INTEGER NOT NULL,
          rejection_id TEXT NOT NULL,
          row_json TEXT NOT NULL,
          PRIMARY KEY(shard_id,rejection_id)
        ) WITHOUT ROWID;
        """
    )


def _index_wrappers(
    connection: sqlite3.Connection,
    raw_root: Path,
    include_source_ids: set[str] | None = None,
) -> None:
    if include_source_ids is not None:
        for pulse_id in sorted(include_source_ids):
            pulse_root = raw_root / pulse_id
            paths = (
                sorted(pulse_root.rglob("*.json"))
                if pulse_root.is_dir()
                else []
            )
            if len(paths) == 1:
                path = paths[0]
                _insert_snapshot(
                    connection,
                    event_id=f"event:otx:{pulse_id}",
                    fetched_at="",
                    path=path,
                    raw_root=raw_root,
                )
                continue
            for path in paths:
                _index_wrapper(connection, path, raw_root)
        return

    for path in sorted(raw_root.rglob("*.json")):
        _index_wrapper(connection, path, raw_root)


def _index_wrapper(
    connection: sqlite3.Connection,
    path: Path,
    raw_root: Path,
) -> None:
    raw_ref = _portable_otx_ref(path, raw_root)
    try:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _reject(
            connection,
            {
                "source": "otx",
                "raw_ref": raw_ref,
                "record_path": "wrapper",
                "reason": "invalid_json",
                "error": str(exc),
            },
        )
        return
    if not isinstance(wrapper, Mapping):
        return
    payload = wrapper.get("payload", wrapper)
    if not isinstance(payload, Mapping) or not isinstance(
        payload.get("indicators"), list
    ):
        return
    source_id = str(payload.get("id") or wrapper.get("source_id") or "").strip()
    if not source_id:
        _reject(
            connection,
            {
                "source": "otx",
                "raw_ref": raw_ref,
                "record_path": "payload.id",
                "reason": "missing_event_id",
            },
        )
        return
    _insert_snapshot(
        connection,
        event_id=f"event:otx:{source_id}",
        fetched_at=str(wrapper.get("fetched_at") or ""),
        path=path,
        raw_root=raw_root,
    )


def _insert_snapshot(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    fetched_at: str,
    path: Path,
    raw_root: Path,
) -> None:
    raw_path = path.resolve().as_posix()
    raw_ref = _portable_otx_ref(path, raw_root)
    connection.execute(
        "INSERT OR IGNORE INTO snapshots VALUES(?,?,?,?)",
        (event_id, fetched_at, raw_path, raw_ref),
    )


def _index_discovery(connection: sqlite3.Connection, path: Path) -> None:
    ordinal = 0
    for candidate in _iter_json_objects(path):
        pulse_id = _text(candidate.get("pulse_id"))
        paths = candidate.get("discovery_paths")
        if not pulse_id or not isinstance(paths, list):
            continue
        for discovery_path in paths:
            if not isinstance(discovery_path, Mapping):
                continue
            connection.execute(
                "INSERT OR IGNORE INTO discovery VALUES(?,?,?)",
                (pulse_id, ordinal, _compact_json(discovery_path)),
            )
            ordinal += 1


def _project_latest_wrappers(
    connection: sqlite3.Connection,
    normalizer: OTXSourceClaimNormalizer | None,
    events_per_shard: int,
    max_indicator_occurrences_per_shard: int,
) -> None:
    query = """
      SELECT s.event_id, s.raw_path, s.raw_ref
      FROM snapshots s
      WHERE NOT EXISTS (
        SELECT 1 FROM snapshots newer
        WHERE newer.event_id=s.event_id
          AND (newer.fetched_at>s.fetched_at OR
               (newer.fetched_at=s.fetched_at AND newer.raw_path>s.raw_path))
      )
      ORDER BY s.event_id
    """
    shard_id = 0
    shard_event_count = 0
    shard_indicator_count = 0
    for event_id, raw_path, raw_ref in connection.execute(query):
        try:
            wrapper = json.loads(
                Path(raw_path).read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            _reject(
                connection,
                {
                    "source": "otx",
                    "event_id": event_id,
                    "raw_ref": raw_ref,
                    "record_path": "wrapper",
                    "reason": "invalid_json",
                    "error": str(exc),
                },
                shard_id,
            )
            continue
        if not isinstance(wrapper, Mapping):
            continue
        payload = wrapper.get("payload", wrapper)
        if not isinstance(payload, Mapping) or not isinstance(
            payload.get("indicators"), list
        ):
            continue
        indicators = payload.get("indicators")
        occurrence_count = len(indicators) if isinstance(indicators, list) else 0
        if shard_event_count and (
            shard_event_count >= events_per_shard
            or shard_indicator_count + occurrence_count
            > max_indicator_occurrences_per_shard
        ):
            shard_id += 1
            shard_event_count = 0
            shard_indicator_count = 0
        oversize = occurrence_count > max_indicator_occurrences_per_shard
        connection.execute(
            "INSERT INTO shard_assignments VALUES(?,?,?,?)",
            (event_id, shard_id, occurrence_count, int(oversize)),
        )
        _project_pulse(
            connection,
            shard_id,
            event_id,
            raw_ref,
            wrapper,
            payload,
            normalizer,
        )
        shard_event_count += 1
        shard_indicator_count += occurrence_count


def _project_pulse(
    connection: sqlite3.Connection,
    shard_id: int,
    event_id: str,
    raw_ref: str,
    wrapper: Mapping[str, Any],
    pulse: Mapping[str, Any],
    normalizer: OTXSourceClaimNormalizer | None,
) -> None:
    source_id = str(pulse.get("id") or wrapper.get("source_id"))
    fetched_at = _text(wrapper.get("fetched_at"))
    event_row = {
        "event_id": event_id,
        "source": "otx",
        "source_record_id": source_id,
        "title": _text(pulse.get("name")) or "",
        "description": _text(pulse.get("description")) or "",
        "raw_ref": raw_ref,
        "event_time": _text(pulse.get("created") or pulse.get("modified")),
        "created": _text(pulse.get("created")),
        "modified": _text(pulse.get("modified")),
        "fetched_at": fetched_at,
        "tags": _strings(pulse.get("tags")),
        "references": _strings(pulse.get("references")),
    }
    _insert_json(
        connection, "events", "event_id", event_id, event_row, shard_id
    )
    _insert_node(
        connection,
        shard_id,
        event_id,
        "event",
        event_id,
        {"source": "otx"},
    )

    indicators = pulse.get("indicators")
    for index, indicator in enumerate(indicators if isinstance(indicators, list) else []):
        if not isinstance(indicator, Mapping):
            continue
        raw_type = _text(indicator.get("type")) or ""
        raw_value = _text(indicator.get("indicator") or indicator.get("value")) or ""
        normalized = _normalize_indicator(raw_type, raw_value)
        record_path = f"payload.indicators[{index}]"
        if normalized is None:
            _reject(
                connection,
                {
                    "source": "otx",
                    "event_id": event_id,
                    "raw_ref": raw_ref,
                    "record_path": record_path,
                    "reason": "unsupported_or_invalid_indicator",
                    "raw_type": raw_type,
                    "raw_value": raw_value,
                },
                shard_id,
            )
            continue
        node_type, value = normalized
        target_id = _node_id(node_type, value)
        _insert_node(connection, shard_id, target_id, node_type, value)
        evidence = {
            "source": "otx",
            "source_record_id": source_id,
            "raw_ref": raw_ref,
            "record_path": record_path,
            "derivation": "source_asserted",
            "raw_value": raw_value,
            "observed_at": _text(indicator.get("created"))
            or _text(pulse.get("created")),
            "created": _text(indicator.get("created")),
            "expiration": _text(indicator.get("expiration")),
            "fetched_at": fetched_at,
        }
        _insert_edge(
            connection,
            shard_id,
            f"event_contains_{node_type}",
            event_id,
            target_id,
            evidence,
            index,
        )
        if node_type == "url":
            _project_url_host(
                connection,
                shard_id,
                event_id,
                target_id,
                value,
                evidence,
                index,
            )

    claim_rows = _adversary_claims(pulse, normalizer)
    semantics = _set_semantics(claim_rows)
    for claim in claim_rows:
        source_field = f"adversary[{claim['label_index']}]"
        row = {
            "claim_id": _claim_id(
                event_id, "otx", claim["raw_label"], source_field
            ),
            "event_id": event_id,
            "source": "otx",
            "source_record_id": source_id,
            "source_field": source_field,
            "raw_field_value": claim["raw_field_value"],
            "raw_value": claim["raw_label"],
            "normalized_value": claim["normalized_label"],
            "raw_ref": raw_ref,
            "record_path": f"payload.{source_field}",
            "claim_scope": "attribution",
            "set_semantics": semantics,
            "usage": "candidate",
            "resolution_status": claim["resolution_status"],
            "resolved_actor_ids": claim["resolved_actor_ids"],
            "candidate_actor_ids": claim["candidate_actor_ids"],
            "parse_status": claim["parse_status"],
            "created": _text(pulse.get("created")),
            "modified": _text(pulse.get("modified")),
            "fetched_at": fetched_at,
        }
        if claim.get("canonical_actor"):
            row["canonical_actor"] = claim["canonical_actor"]
        _insert_json(
            connection,
            "claims",
            "claim_id",
            row["claim_id"],
            row,
            shard_id,
        )

    tags = _strings(pulse.get("tags"))
    tag_semantics = "set" if len(tags) > 1 else "singleton"
    for index, tag in enumerate(tags):
        source_field = f"tags[{index}]"
        claim_id = _claim_id(event_id, "otx", tag, source_field)
        _insert_json(
            connection,
            "claims",
            "claim_id",
            claim_id,
            {
                "claim_id": claim_id,
                "event_id": event_id,
                "source": "otx",
                "source_record_id": source_id,
                "source_field": source_field,
                "raw_value": tag,
                "normalized_value": tag.casefold(),
                "raw_ref": raw_ref,
                "record_path": f"payload.{source_field}",
                "claim_scope": "report_context",
                "set_semantics": tag_semantics,
                "usage": "provenance_only",
                "resolution_status": "context_only",
                "resolved_actor_ids": [],
                "candidate_actor_ids": [],
                "created": _text(pulse.get("created")),
                "modified": _text(pulse.get("modified")),
                "fetched_at": fetched_at,
            },
            shard_id,
        )

    discovery_count = connection.execute(
        "SELECT COUNT(*) FROM discovery WHERE pulse_id=?", (source_id,)
    ).fetchone()[0]
    discovery_semantics = "set" if discovery_count > 1 else "singleton"
    discovery_rows = connection.execute(
        "SELECT ordinal,row_json FROM discovery WHERE pulse_id=? ORDER BY ordinal",
        (source_id,),
    )
    for ordinal, row_json in discovery_rows:
        discovery = json.loads(row_json)
        raw_value = _text(discovery.get("alias") or discovery.get("otx_query"))
        if not raw_value:
            continue
        source_field = f"discovery_paths[{ordinal}].alias"
        claim_id = _claim_id(event_id, "otx_search", raw_value, source_field)
        search_ref = discovery.get("search_raw_ref")
        search_path = (
            search_ref.get("path")
            if isinstance(search_ref, Mapping)
            else search_ref
        )
        _insert_json(
            connection,
            "claims",
            "claim_id",
            claim_id,
            {
                "claim_id": claim_id,
                "event_id": event_id,
                "source": "otx_search",
                "source_record_id": source_id,
                "source_field": source_field,
                "raw_value": raw_value,
                "normalized_value": raw_value.casefold(),
                "query_value": _text(discovery.get("otx_query")),
                "discovery_method": _text(discovery.get("method")),
                "query_seed_canonical_actor": _text(
                    discovery.get("canonical_actor_from_frozen_map")
                ),
                "raw_ref": _portable_search_ref(search_path),
                "record_path": source_field,
                "claim_scope": "discovery_only",
                "set_semantics": discovery_semantics,
                "usage": "provenance_only",
                "resolution_status": "discovery_provenance_only",
                "resolved_actor_ids": [],
                "candidate_actor_ids": [],
                "fetched_at": (
                    _text(search_ref.get("fetched_at"))
                    if isinstance(search_ref, Mapping)
                    else None
                ),
            },
            shard_id,
        )


def _project_url_host(
    connection: sqlite3.Connection,
    shard_id: int,
    event_id: str,
    url_id: str,
    url: str,
    evidence: Mapping[str, Any],
    ordinal: int,
) -> None:
    host = urlsplit(url).hostname
    if not host:
        return
    normalized_ip = _normalize_ip(host)
    if normalized_ip:
        target_type, target_value, relation = "ip", normalized_ip, "url_resolves_to_ip"
    else:
        normalized_domain = _normalize_domain(host)
        if not normalized_domain:
            return
        target_type, target_value, relation = (
            "domain",
            normalized_domain,
            "url_hosted_on_domain",
        )
    target_id = _node_id(target_type, target_value)
    _insert_node(
        connection, shard_id, target_id, target_type, target_value
    )
    derived = dict(evidence)
    derived["derivation"] = "derived_url_host"
    _insert_edge(
        connection,
        shard_id,
        relation,
        url_id,
        target_id,
        derived,
        f"{event_id}:{ordinal}",
    )


def _insert_node(
    connection: sqlite3.Connection,
    shard_id: int,
    node_id: str,
    node_type: str,
    value: str,
    properties: Mapping[str, Any] | None = None,
) -> None:
    row: dict[str, Any] = {"node_id": node_id, "type": node_type, "value": value}
    if properties:
        row["properties"] = dict(properties)
    connection.execute(
        "INSERT OR IGNORE INTO nodes VALUES(?,?,?,?)",
        (shard_id, node_id, node_type, _compact_json(row)),
    )


def _insert_edge(
    connection: sqlite3.Connection,
    shard_id: int,
    relation: str,
    source_id: str,
    target_id: str,
    evidence: Mapping[str, Any],
    ordinal: Any,
) -> None:
    edge_id = "edge:" + _stable_hash(
        relation,
        source_id,
        target_id,
        evidence.get("raw_ref"),
        evidence.get("record_path"),
        ordinal,
    )
    row = {
        "edge_id": edge_id,
        "relation": relation,
        "source_id": source_id,
        "target_id": target_id,
        "evidence": [{key: value for key, value in evidence.items() if value is not None}],
    }
    _insert_json(
        connection, "edges", "edge_id", edge_id, row, shard_id
    )


def _reject(
    connection: sqlite3.Connection,
    row: Mapping[str, Any],
    shard_id: int = 0,
) -> None:
    rejection_id = _stable_hash(row)
    _insert_json(
        connection,
        "rejected",
        "rejection_id",
        rejection_id,
        row,
        shard_id,
    )


def _insert_json(
    connection: sqlite3.Connection,
    table: str,
    key_name: str,
    key: str,
    row: Mapping[str, Any],
    shard_id: int,
) -> None:
    connection.execute(
        f"INSERT OR IGNORE INTO {table}(shard_id,{key_name},row_json) VALUES(?,?,?)",
        (
            shard_id,
            key,
            _compact_json({k: v for k, v in row.items() if v is not None}),
        ),
    )


def _write_handoff(
    connection: sqlite3.Connection, output_dir: Path
) -> tuple[dict[str, int], list[dict[str, Any]], tuple[Path, ...]]:
    outputs = (
        ("nodes", "nodes.jsonl", "type,node_id"),
        ("edges", "edges.jsonl", "edge_id"),
        ("events", "events.jsonl", "event_id"),
        ("claims", "source_claims.jsonl", "claim_id"),
        ("rejected", "rejected_records.jsonl", "rejection_id"),
    )
    shard_ids = [
        row[0]
        for row in connection.execute(
            """
            SELECT shard_id FROM events
            UNION SELECT shard_id FROM rejected
            ORDER BY shard_id
            """
        )
    ]
    counts = {table: 0 for table, _name, _order in outputs}
    shard_rows: list[dict[str, Any]] = []
    handoff_dirs: list[Path] = []
    for shard_id in shard_ids:
        shard_dir = output_dir / "shards" / f"shard-{shard_id:05d}"
        shard_dir.mkdir(parents=True)
        handoff_dirs.append(shard_dir)
        shard_counts: dict[str, int] = {}
        for table, name, order_by in outputs:
            count = 0
            with (shard_dir / name).open(
                "w", encoding="utf-8", newline="\n"
            ) as handle:
                for (row_json,) in connection.execute(
                    f"SELECT row_json FROM {table} "
                    f"WHERE shard_id=? ORDER BY {order_by}",
                    (shard_id,),
                ):
                    handle.write(row_json + "\n")
                    count += 1
            shard_counts[table] = count
            counts[table] += count
        assignment = connection.execute(
            """
            SELECT COALESCE(SUM(raw_indicator_occurrence_count),0)
            FROM shard_assignments WHERE shard_id=?
            """,
            (shard_id,),
        ).fetchone()
        oversize_events = [
            event_id
            for (event_id,) in connection.execute(
                """
                SELECT event_id FROM shard_assignments
                WHERE shard_id=? AND occurrence_cap_oversize=1
                ORDER BY event_id
                """,
                (shard_id,),
            )
        ]
        shard_rows.append(
            {
                "shard_id": shard_id,
                "path": shard_dir.relative_to(output_dir).as_posix(),
                "event_count": shard_counts["events"],
                "node_count": shard_counts["nodes"],
                "edge_count": shard_counts["edges"],
                "claim_count": shard_counts["claims"],
                "rejected_count": shard_counts["rejected"],
                "raw_indicator_occurrence_count": assignment[0],
                "single_event_oversize_exceptions": oversize_events,
                "content_sha256": _content_hash(shard_dir),
            }
        )
    return counts, shard_rows, tuple(handoff_dirs)


def _adversary_claims(
    pulse: Mapping[str, Any],
    normalizer: OTXSourceClaimNormalizer | None,
) -> list[dict[str, Any]]:
    if normalizer is not None:
        _event, claims = normalizer.normalize(pulse)
        return [
            {
                "raw_field_value": row["raw_field_value"],
                "raw_label": row["raw_label"],
                "normalized_label": row["normalized_label"],
                "label_index": row["label_index"],
                "parse_status": row["parse_status"],
                "resolution_status": row["resolution_status"],
                "resolved_actor_ids": row["resolved_actor_ids"],
                "candidate_actor_ids": row["candidate_actor_ids"],
                "canonical_actor": (
                    (row.get("matched_taxonomy_labels") or [None])[0]
                    if len(row.get("resolved_actor_ids") or []) == 1
                    else None
                ),
            }
            for row in claims
        ]
    return [
        {
            "raw_field_value": claim.raw_field_value,
            "raw_label": claim.raw_label,
            "normalized_label": claim.raw_label.casefold(),
            "label_index": claim.label_index,
            "parse_status": claim.parse_status,
            "resolution_status": (
                "unmapped_actor_like"
                if claim.parse_status == "parsed"
                else claim.parse_status
            ),
            "resolved_actor_ids": [],
            "candidate_actor_ids": [],
            "canonical_actor": None,
        }
        for claim in _parse_claims(_text(pulse.get("adversary")) or "")
    ]


def _set_semantics(claims: list[Mapping[str, Any]]) -> str:
    if any(
        "ambiguous" in str(claim.get("resolution_status") or "")
        for claim in claims
    ):
        return "ambiguous"
    return "set" if len(claims) > 1 else "singleton"


def _iter_json_objects(path: Path) -> Iterator[dict[str, Any]]:
    """Yield a JSONL file or top-level JSON array without loading it whole."""

    if path.suffix.casefold() in {".jsonl", ".ndjson"}:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    if isinstance(row, dict):
                        yield row
        return

    with path.open(encoding="utf-8") as handle:
        current: list[str] = []
        depth = 0
        in_string = False
        escaped = False
        for chunk in iter(lambda: handle.read(1024 * 1024), ""):
            for character in chunk:
                if depth == 0:
                    if character == "{":
                        current = [character]
                        depth = 1
                    continue
                current.append(character)
                if in_string:
                    if escaped:
                        escaped = False
                    elif character == "\\":
                        escaped = True
                    elif character == '"':
                        in_string = False
                    continue
                if character == '"':
                    in_string = True
                elif character in "[{":
                    depth += 1
                elif character in "]}":
                    depth -= 1
                    if depth == 0:
                        row = json.loads("".join(current))
                        if isinstance(row, dict):
                            yield row
                        current = []
        if depth:
            raise ValueError(f"incomplete JSON object in {path}")


def _portable_otx_ref(path: Path, raw_root: Path) -> str:
    relative = path.resolve().relative_to(raw_root.resolve()).as_posix()
    return f"data/raw/otx/{relative}"


def _portable_search_ref(value: Any) -> str:
    text = str(value or "").replace("\\", "/")
    lowered = text.casefold()
    marker = "/raw/otx_search/"
    if marker in lowered:
        index = lowered.index(marker) + len(marker)
        return f"data/raw/otx_search/{text[index:]}"
    if lowered.startswith("data/raw/"):
        return text
    if lowered.startswith("raw/"):
        return f"data/{text}"
    name = Path(text).name if text else "unknown"
    return f"data/raw/otx_search/{name}"


def _normalize_indicator(raw_type: str, raw_value: str) -> tuple[str, str] | None:
    kind = raw_type.strip().casefold()
    if kind in {"domain", "hostname", "fqdn"}:
        value = _normalize_domain(raw_value)
        return ("domain", value) if value else None
    if kind in {"ipv4", "ipv6", "ip"}:
        value = _normalize_ip(raw_value)
        return ("ip", value) if value else None
    if kind in {"url", "uri"}:
        value = _normalize_url(raw_value)
        return ("url", value) if value else None
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
    text = _defang(value).strip().rstrip(".").casefold()
    if not text:
        return None
    try:
        text = text.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    labels = text.split(".")
    if (
        len(labels) < 2
        or len(text) > 253
        or any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or not re.fullmatch(r"[a-z0-9-]+", label)
            for label in labels
        )
    ):
        return None
    return text


def _normalize_ip(value: str) -> str | None:
    try:
        return ipaddress.ip_address(_defang(value).strip()).compressed
    except ValueError:
        return None


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
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            return None
        host = _normalize_ip(parsed.hostname) or _normalize_domain(parsed.hostname)
        if not host:
            return None
        scheme = parsed.scheme.casefold()
        port = parsed.port
        default_port = (scheme == "http" and port == 80) or (
            scheme == "https" and port == 443
        )
        userinfo = ""
        if parsed.username:
            userinfo = quote(unquote(parsed.username), safe="")
            if parsed.password:
                userinfo += ":" + quote(unquote(parsed.password), safe="")
            userinfo += "@"
        host_text = f"[{host}]" if ":" in host else host
        netloc = userinfo + host_text
        if port and not default_port:
            netloc += f":{port}"
        return urlunsplit((scheme, netloc, parsed.path or "", parsed.query or "", ""))
    except (ValueError, UnicodeError):
        return None


def _node_id(node_type: str, value: str) -> str:
    return f"{node_type}:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _claim_id(event_id: str, source: str, value: str, field: str) -> str:
    return "claim:" + _stable_hash(event_id, source, value, field)


def _stable_hash(*parts: Any) -> str:
    return hashlib.sha256(_compact_json(parts).encode("utf-8")).hexdigest()


def _compact_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _content_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
