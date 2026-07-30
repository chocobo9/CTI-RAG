"""Build the strict five-file EviTRAIL handoff for non-OTX report sources."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import sqlite3
from collections import Counter
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .sources import align_source_record, iter_jsonl_evidence

SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "orkl": {
        "records": ("orkl", "reports.jsonl"),
        "claims": ("orkl", "source_actor_claims.jsonl"),
        "processed": "orkl",
    },
    "circl_misp": {
        "records": ("circl_misp", "events.jsonl"),
        "claims": ("circl_misp", "source_actor_claims.jsonl"),
        "processed": "misp",
    },
    "aptnotes": {
        "records": ("aptnotes", "reports.jsonl"),
        "claims": ("aptnotes", "source_actor_claim_candidates.jsonl"),
        "processed": "aptnotes",
    },
    "cisa": {
        "records": ("cisa", "advisories.jsonl"),
        "claims": ("cisa", "source_actor_claim_candidates.jsonl"),
        "processed": "cisa",
    },
}


def build_source_handoff(
    *,
    raw_root: Path,
    processed_root: Path,
    output_dir: Path,
    work_dir: Path,
) -> dict[str, int]:
    """Stream four collected report sources into EviTRAIL's five files.

    Evidence sidecars are joined through a disk-backed index under ``work_dir``.
    ``output_dir`` must be fresh, and raw/normalized inputs are only read.
    """

    raw_root = Path(raw_root).resolve()
    processed_root = Path(processed_root).resolve()
    output_dir = Path(output_dir).resolve()
    work_dir = Path(work_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    required = _required_paths(raw_root, processed_root)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing source handoff inputs: {missing}")

    output_dir.mkdir(parents=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    database_path = work_dir / "_evitrail_source_handoff.sqlite"
    if database_path.exists():
        raise FileExistsError(f"staging database already exists: {database_path}")
    connection = sqlite3.connect(database_path)
    try:
        _create_tables(connection)
        _stage_sidecars(connection, raw_root, processed_root)
        result = _write_handoff(
            connection=connection,
            raw_root=raw_root,
            output_dir=output_dir,
        )
    finally:
        connection.close()
    database_path.unlink()
    return result


def _required_paths(raw_root: Path, processed_root: Path) -> list[Path]:
    paths: list[Path] = []
    for spec in SOURCE_SPECS.values():
        record_source, record_name = spec["records"]
        claim_source, claim_name = spec["claims"]
        paths.extend(
            (
                raw_root / record_source / "normalized" / record_name,
                raw_root / claim_source / "normalized" / claim_name,
                processed_root / "normalized" / spec["processed"] / "ioc_evidence.jsonl",
            )
        )
    return paths


def _create_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE evidence (
            source TEXT NOT NULL,
            record_key TEXT NOT NULL,
            kind TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (source, kind, ordinal)
        );
        CREATE INDEX evidence_join
            ON evidence (source, record_key, kind, ordinal);
        CREATE TABLE stage_rejections (
            ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
            payload TEXT NOT NULL
        );
        CREATE TABLE nodes (
            node_id TEXT PRIMARY KEY,
            node_type TEXT NOT NULL,
            value TEXT NOT NULL,
            properties TEXT NOT NULL
        ) WITHOUT ROWID;
        """
    )


def _stage_sidecars(connection: sqlite3.Connection, raw_root: Path, processed_root: Path) -> None:
    for source, spec in SOURCE_SPECS.items():
        claim_source, claim_name = spec["claims"]
        claim_path = raw_root / claim_source / "normalized" / claim_name
        _stage_file(
            connection,
            path=claim_path,
            source=source,
            kind="claim",
            key_fn=lambda row, source=source: _claim_record_key(source, row),
            portable_root=raw_root,
            portable_prefix="raw",
        )
        ioc_path = processed_root / "normalized" / spec["processed"] / "ioc_evidence.jsonl"
        _stage_file(
            connection,
            path=ioc_path,
            source=source,
            kind="ioc",
            key_fn=lambda row, source=source: _ioc_record_key(source, row),
            portable_root=processed_root,
            portable_prefix="processed",
        )
    connection.commit()


def _stage_file(
    connection: sqlite3.Connection,
    *,
    path: Path,
    source: str,
    kind: str,
    key_fn: Callable[[Mapping[str, Any]], str],
    portable_root: Path,
    portable_prefix: str,
) -> None:
    for ordinal, evidence in enumerate(iter_jsonl_evidence(path, source=source), start=1):
        if evidence.rejection:
            rejection = dict(evidence.rejection)
            rejection["raw_ref"] = _portable_path(path, portable_root, portable_prefix)
            connection.execute(
                "INSERT INTO stage_rejections(payload) VALUES (?)",
                (_json_text(rejection),),
            )
            continue
        assert evidence.record is not None
        key = key_fn(evidence.record)
        if not key:
            rejection = {
                "source": source,
                "raw_ref": _portable_path(path, portable_root, portable_prefix),
                "record_path": f"line[{ordinal}]",
                "reason": f"missing_event_join_key_for_{kind}",
                "raw_type": kind,
            }
            connection.execute(
                "INSERT INTO stage_rejections(payload) VALUES (?)",
                (_json_text(rejection),),
            )
            continue
        connection.execute(
            """
            INSERT INTO evidence(source, record_key, kind, ordinal, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source, key, kind, ordinal, _json_text(evidence.record)),
        )


def _write_handoff(
    *, connection: sqlite3.Connection, raw_root: Path, output_dir: Path
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    with (
        (output_dir / "events.jsonl").open("w", encoding="utf-8", newline="\n") as events,
        (output_dir / "edges.jsonl").open("w", encoding="utf-8", newline="\n") as edges,
        (output_dir / "source_claims.jsonl").open("w", encoding="utf-8", newline="\n") as claims,
        (output_dir / "rejected_records.jsonl").open(
            "w", encoding="utf-8", newline="\n"
        ) as rejected,
    ):
        for (payload,) in connection.execute(
            "SELECT payload FROM stage_rejections ORDER BY ordinal"
        ):
            _write_row(rejected, json.loads(payload))
            counts["rejected"] += 1

        for source, spec in SOURCE_SPECS.items():
            source_name, record_name = spec["records"]
            path = raw_root / source_name / "normalized" / record_name
            for line_number, evidence in enumerate(
                iter_jsonl_evidence(path, source=source), start=1
            ):
                if evidence.rejection:
                    row = dict(evidence.rejection)
                    row["raw_ref"] = _portable_path(path, raw_root, "raw")
                    _write_row(rejected, row)
                    counts["rejected"] += 1
                    continue
                assert evidence.record is not None
                record_key = _record_key(source, evidence.record)
                if not record_key:
                    _write_row(
                        rejected,
                        {
                            "source": source,
                            "raw_ref": _portable_path(path, raw_root, "raw"),
                            "record_path": f"line[{line_number}]",
                            "reason": "not_report_event",
                            "raw_type": "missing_event_join_key",
                        },
                    )
                    counts["rejected"] += 1
                    continue
                ioc_rows = _joined_rows(connection, source, record_key, "ioc")
                claim_rows = _joined_rows(connection, source, record_key, "claim")
                aligned = align_source_record(
                    source,
                    evidence.record,
                    ioc_rows=ioc_rows,
                    claim_rows=claim_rows,
                )
                if aligned.event is None:
                    for row in aligned.rejections:
                        _write_row(rejected, row)
                        counts["rejected"] += 1
                    continue
                event = aligned.event
                _write_row(events, event)
                counts["events"] += 1
                _insert_node(
                    connection,
                    event["event_id"],
                    "event",
                    event["event_id"],
                    {
                        "source": source,
                        "source_record_id": event["source_record_id"],
                    },
                )
                for claim in aligned.claims:
                    _write_row(claims, claim)
                    counts["claims"] += 1
                for row in aligned.rejections:
                    _write_row(rejected, row)
                    counts["rejected"] += 1
                for indicator in aligned.indicators:
                    _write_indicator(connection, edges, event["event_id"], source, indicator)
                    counts["indicators"] += 1
                    counts["edges"] += 1
                    if indicator["type"] == "url" and _write_url_host(
                        connection, edges, source, indicator
                    ):
                        counts["edges"] += 1
            connection.commit()

        _append_misp_object_relations(
            connection=connection,
            edges=edges,
            rejected=rejected,
            raw_root=raw_root,
            counts=counts,
        )

    with (output_dir / "nodes.jsonl").open("w", encoding="utf-8", newline="\n") as nodes:
        for node_id, node_type, value, properties in connection.execute(
            """
            SELECT node_id, node_type, value, properties
            FROM nodes
            ORDER BY node_type, node_id
            """
        ):
            row = {
                "node_id": node_id,
                "type": node_type,
                "value": value,
            }
            decoded = json.loads(properties)
            if decoded:
                row["properties"] = decoded
            _write_row(nodes, row)
            counts["nodes"] += 1
    return dict(sorted(counts.items()))


def _append_misp_object_relations(
    *,
    connection: sqlite3.Connection,
    edges: Any,
    rejected: Any,
    raw_root: Path,
    counts: Counter[str],
) -> None:
    """Preserve source-asserted IP-to-ASN pairs within MISP Objects."""

    source_root = raw_root / "circl_misp"
    events_root = source_root / "raw" / "events"
    if not events_root.is_dir():
        return
    for path in sorted(events_root.glob("*.json")):
        raw_ref = _portable_path(path, source_root, "")
        try:
            wrapper = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            _write_row(
                rejected,
                {
                    "source": "circl_misp",
                    "raw_ref": raw_ref,
                    "record_path": "Event",
                    "reason": "invalid_misp_raw_json",
                },
            )
            counts["rejected"] += 1
            continue
        if not isinstance(wrapper, Mapping):
            continue
        event = wrapper.get("Event", wrapper)
        if not isinstance(event, Mapping):
            continue
        source_id = str(event.get("uuid") or path.stem)
        event_id = f"event:circl_misp:{source_id}"
        if not connection.execute(
            "SELECT 1 FROM nodes WHERE node_id=? AND node_type='event'",
            (event_id,),
        ).fetchone():
            continue
        objects = event.get("Object")
        for object_index, value in enumerate(
            objects if isinstance(objects, list) else []
        ):
            if not isinstance(value, Mapping):
                continue
            ips: set[str] = set()
            asns: set[str] = set()
            attributes = value.get("Attribute")
            for attribute in attributes if isinstance(attributes, list) else []:
                if not isinstance(attribute, Mapping):
                    continue
                raw_type = str(
                    attribute.get("type")
                    or attribute.get("object_relation")
                    or ""
                ).casefold()
                raw_value = str(attribute.get("value") or "")
                if raw_type in {"ip-src", "ip-dst", "ip", "ip-address"}:
                    try:
                        ips.add(
                            ipaddress.ip_address(
                                raw_value.split("|", 1)[0].strip()
                            ).compressed
                        )
                    except ValueError:
                        continue
                elif raw_type in {"as", "asn", "autonomous-system"}:
                    match = re.match(
                        r"(?i)^\s*(?:AS\s*)?(\d+)",
                        raw_value,
                    )
                    if match:
                        asns.add(str(int(match.group(1))))
            if not asns:
                continue
            for ip in sorted(ips):
                ip_id = _node_id("ip", ip)
                _insert_node(connection, ip_id, "ip", ip, {})
                for asn in sorted(asns):
                    asn_id = _node_id("asn", asn)
                    _insert_node(connection, asn_id, "asn", asn, {})
                    relation = "ip_in_asn"
                    record_path = f"Event.Object[{object_index}]"
                    evidence = {
                        "source": "circl_misp",
                        "raw_ref": raw_ref,
                        "record_path": record_path,
                        "derivation": "source_asserted_object_relation",
                    }
                    _write_row(
                        edges,
                        {
                            "edge_id": _edge_id(
                                relation,
                                ip_id,
                                asn_id,
                                raw_ref,
                                record_path,
                            ),
                            "relation": relation,
                            "source_id": ip_id,
                            "target_id": asn_id,
                            "evidence": [evidence],
                        },
                    )
                    counts["edges"] += 1
                    counts["misp_ip_asn_relations"] += 1
    connection.commit()


def _joined_rows(
    connection: sqlite3.Connection, source: str, record_key: str, kind: str
) -> list[dict[str, Any]]:
    return [
        json.loads(payload)
        for (payload,) in connection.execute(
            """
            SELECT payload FROM evidence
            WHERE source = ? AND record_key = ? AND kind = ?
            ORDER BY ordinal
            """,
            (source, record_key, kind),
        )
    ]


def _write_indicator(
    connection: sqlite3.Connection,
    edges: Any,
    event_id: str,
    source: str,
    indicator: Mapping[str, Any],
) -> None:
    node_type = str(indicator["type"])
    value = str(indicator["value"])
    target_id = _node_id(node_type, value)
    _insert_node(connection, target_id, node_type, value, {})
    relation = f"event_contains_{node_type}"
    evidence = _edge_evidence(source, indicator)
    _write_row(
        edges,
        {
            "edge_id": _edge_id(
                relation,
                event_id,
                target_id,
                evidence["raw_ref"],
                evidence["record_path"],
            ),
            "relation": relation,
            "source_id": event_id,
            "target_id": target_id,
            "evidence": [evidence],
        },
    )


def _write_url_host(
    connection: sqlite3.Connection,
    edges: Any,
    source: str,
    indicator: Mapping[str, Any],
) -> bool:
    parsed = urlsplit(str(indicator["value"]))
    host = parsed.hostname
    if not host:
        return False
    try:
        host_type, host_value = "ip", ipaddress.ip_address(host).compressed.lower()
    except ValueError:
        host_type, host_value = "domain", host.lower().rstrip(".")
    url_id = _node_id("url", str(indicator["value"]))
    host_id = _node_id(host_type, host_value)
    _insert_node(connection, host_id, host_type, host_value, {})
    relation = "url_resolves_to_ip" if host_type == "ip" else "url_hosted_on_domain"
    evidence = _edge_evidence(source, indicator)
    evidence["record_path"] = f"{evidence['record_path']}.url_host"
    evidence["derivation"] = "deterministic_url_host"
    _write_row(
        edges,
        {
            "edge_id": _edge_id(
                relation,
                url_id,
                host_id,
                evidence["raw_ref"],
                evidence["record_path"],
            ),
            "relation": relation,
            "source_id": url_id,
            "target_id": host_id,
            "evidence": [evidence],
        },
    )
    return True


def _edge_evidence(source: str, indicator: Mapping[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source": source,
        "raw_ref": str(indicator.get("raw_ref") or ""),
        "record_path": str(indicator.get("record_path") or ""),
        "derivation": str(indicator.get("derivation") or "source_asserted"),
        "raw_value": indicator.get("raw_value"),
    }
    row.update(indicator.get("timestamps") or {})
    return {key: value for key, value in row.items() if value not in (None, "")}


def _insert_node(
    connection: sqlite3.Connection,
    node_id: str,
    node_type: str,
    value: str,
    properties: Mapping[str, Any],
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO nodes(node_id, node_type, value, properties)
        VALUES (?, ?, ?, ?)
        """,
        (node_id, node_type, value, _json_text(properties)),
    )


def _record_key(source: str, row: Mapping[str, Any]) -> str:
    if source == "orkl":
        return str(
            row.get("source_record_id")
            or str(row.get("report_id") or "").removeprefix("orkl:report:")
        )
    if source == "circl_misp":
        uuid = str(
            row.get("source_uuid")
            or row.get("uuid")
            or str(row.get("event_id") or "").removeprefix("circl-misp:event:")
        )
        return f"circl-misp:event:{uuid}" if uuid else ""
    return str(row.get("report_id") or "")


def _claim_record_key(source: str, row: Mapping[str, Any]) -> str:
    if source == "orkl":
        return str(row.get("subject_record_id") or "").removeprefix("orkl:report:")
    if source == "circl_misp":
        return str(row.get("event_id") or "")
    return str(row.get("report_id") or "")


def _ioc_record_key(source: str, row: Mapping[str, Any]) -> str:
    return str(row.get("source_record_id") or "")


def _node_id(node_type: str, value: str) -> str:
    if node_type == "asn":
        return f"asn:{value}"
    return f"{node_type}:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _edge_id(
    relation: str,
    source_id: str,
    target_id: str,
    raw_ref: str,
    record_path: str,
) -> str:
    payload = _json_text((relation, source_id, target_id, raw_ref, record_path))
    return f"edge:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _portable_path(path: Path, root: Path, prefix: str) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return path.name
    return (Path(prefix) / relative).as_posix()


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _write_row(handle: Any, row: Mapping[str, Any]) -> None:
    handle.write(_json_text(row) + "\n")
