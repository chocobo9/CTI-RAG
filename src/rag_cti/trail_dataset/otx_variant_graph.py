"""Build disk-backed direct/pDNS/pDNS+ASN graphs for one frozen population."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VARIANTS = ("direct", "pdns", "pdns_asn")


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value


def _node_id(kind: str, value: str) -> str:
    return f"{kind}:{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _event_id(pulse_id: str) -> str:
    return f"event:otx:{pulse_id}"


def _normalise_ip(value: Any) -> str | None:
    try:
        return ipaddress.ip_address(str(value or "").strip()).compressed.lower()
    except ValueError:
        return None


def _normalise_domain(value: Any) -> str | None:
    text = str(value or "").strip().rstrip(".").lower()
    if not text or "." not in text:
        return None
    try:
        ipaddress.ip_address(text)
        return None
    except ValueError:
        pass
    try:
        encoded = text.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if len(encoded) > 253 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in encoded.split(".")
    ):
        return None
    return encoded


def _asn(value: Any) -> tuple[str | None, str | None]:
    text = " ".join(str(value or "").split())
    match = re.match(r"(?i)^AS?(\d+)(?:\s+(.*))?$", text)
    if not match:
        return None, None
    return f"AS{int(match.group(1))}", match.group(2)


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.executescript(
        """
        CREATE TABLE nodes (
            node_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            value TEXT NOT NULL,
            properties_json TEXT
        );
        CREATE TABLE edges (
            source_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            target_id TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            PRIMARY KEY(source_id, relation, target_id)
        );
        CREATE TABLE events (
            event_id TEXT PRIMARY KEY,
            pulse_id TEXT NOT NULL,
            label TEXT NOT NULL,
            class_id INTEGER NOT NULL,
            event_time TEXT,
            raw_ref TEXT,
            expansion_state TEXT NOT NULL
        );
        """
    )
    return connection


def _add_node(
    connection: sqlite3.Connection,
    kind: str,
    value: str,
    *,
    node_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> str:
    node_id = node_id or _node_id(kind, value)
    connection.execute(
        "INSERT OR IGNORE INTO nodes VALUES (?, ?, ?, ?)",
        (
            node_id,
            kind,
            value,
            json.dumps(properties, sort_keys=True) if properties else None,
        ),
    )
    return node_id


def _add_edge(
    connection: sqlite3.Connection,
    source_id: str,
    relation: str,
    target_id: str,
    evidence: dict[str, Any],
) -> None:
    connection.execute(
        "INSERT OR IGNORE INTO edges VALUES (?, ?, ?, ?)",
        (source_id, relation, target_id, json.dumps(evidence, sort_keys=True)),
    )


def _pdns_records(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("passive_dns")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    yield row


def _project_pdns(
    connection: sqlite3.Connection,
    *,
    endpoint: str,
    seed_value: str,
    wrapper: dict[str, Any],
    include_asn: bool,
    raw_ref: str,
) -> None:
    payload = wrapper.get("payload")
    fetched_at = wrapper.get("fetched_at")
    if endpoint == "ip_general":
        if not include_asn or not isinstance(payload, dict):
            return
        ip = _normalise_ip(seed_value)
        asn, name = _asn(payload.get("asn"))
        if ip and asn:
            ip_id = _add_node(connection, "ip", ip)
            asn_id = _add_node(connection, "asn", asn, properties={"name": name})
            _add_edge(
                connection,
                ip_id,
                "ip_in_asn",
                asn_id,
                {"raw_ref": raw_ref, "endpoint": endpoint, "observed_at": fetched_at},
            )
        return
    for index, row in enumerate(_pdns_records(payload)):
        hostname = _normalise_domain(row.get("hostname"))
        address = _normalise_ip(row.get("address"))
        if endpoint == "domain_pdns":
            domain = _normalise_domain(seed_value) or hostname
            ip = address
        else:
            domain = hostname
            ip = _normalise_ip(seed_value) or address
        if not domain or not ip:
            continue
        domain_id = _add_node(connection, "domain", domain)
        ip_id = _add_node(connection, "ip", ip)
        evidence = {
            "raw_ref": raw_ref,
            "endpoint": endpoint,
            "record_index": index,
            "record_type": row.get("record_type"),
            "first_seen": row.get("first"),
            "last_seen": row.get("last"),
            "observed_at": fetched_at,
        }
        _add_edge(connection, domain_id, "domain_resolves_to_ip", ip_id, evidence)
        if include_asn:
            asn, name = _asn(row.get("asn"))
            if asn:
                asn_id = _add_node(
                    connection, "asn", asn, properties={"name": name}
                )
                _add_edge(connection, ip_id, "ip_in_asn", asn_id, evidence)


def _write_outputs(connection: sqlite3.Connection, output_dir: Path) -> None:
    queries = {
        "nodes.jsonl": """
            SELECT node_id, type, value, properties_json
            FROM nodes ORDER BY type, node_id
        """,
        "edges.jsonl": """
            SELECT source_id, relation, target_id, evidence_json
            FROM edges ORDER BY source_id, relation, target_id
        """,
        "events.jsonl": """
            SELECT event_id, pulse_id, label, class_id, event_time, raw_ref,
                   expansion_state
            FROM events ORDER BY event_id
        """,
    }
    for name, query in queries.items():
        with (output_dir / name).open("w", encoding="utf-8", newline="\n") as handle:
            for row in connection.execute(query):
                if name == "nodes.jsonl":
                    value = {"node_id": row[0], "type": row[1], "value": row[2]}
                    if row[3]:
                        value["properties"] = json.loads(row[3])
                elif name == "edges.jsonl":
                    edge_key = f"{row[0]}|{row[1]}|{row[2]}"
                    value = {
                        "edge_id": "edge:" + hashlib.sha256(edge_key.encode()).hexdigest(),
                        "source_id": row[0],
                        "relation": row[1],
                        "target_id": row[2],
                        "evidence": [json.loads(row[3])],
                    }
                else:
                    value = {
                        "event_id": row[0],
                        "pulse_id": row[1],
                        "label": row[2],
                        "class_id": row[3],
                        "event_time": row[4],
                        "raw_ref": row[5],
                        "expansion_state": row[6],
                        "source": "otx",
                    }
                handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def build_variant_graph(
    *,
    population_dir: Path,
    enrichment_root: Path,
    variant: str,
    output_dir: Path,
) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {VARIANTS}")
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    database = output_dir / "_build.sqlite"
    connection = _connect(database)
    try:
        for row in _iter_jsonl(population_dir / "population_events.jsonl"):
            event = _event_id(str(row["event_id"]))
            _add_node(
                connection,
                "event",
                event,
                node_id=event,
                properties={"source": "otx"},
            )
            connection.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event,
                    row["event_id"],
                    row["label"],
                    row["class_id"],
                    row.get("pulse_created"),
                    row.get("raw_path"),
                    row["expansion_state"],
                ),
            )
        for row in _iter_jsonl(
            population_dir / "event_seed_occurrences.jsonl"
        ):
            seed_id = str(row["seed_id"])
            _add_node(
                connection,
                str(row["seed_type"]),
                str(row["value"]),
                node_id=seed_id,
            )
            _add_edge(
                connection,
                _event_id(str(row["event_id"])),
                f"event_contains_{row['seed_type']}",
                seed_id,
                {
                    "derivation": row.get("derivation"),
                    "indicator_created_first": row.get("indicator_created_first"),
                    "indicator_created_last": row.get("indicator_created_last"),
                },
            )
        for row in _iter_jsonl(population_dir / "url_host_occurrences.jsonl"):
            host_id = str(row["host_seed_id"])
            _add_node(
                connection,
                str(row["host_seed_type"]),
                str(row["host_value"]),
                node_id=host_id,
            )
            relation = (
                "url_hosted_on_domain"
                if row["host_seed_type"] == "domain"
                else "url_resolves_to_ip"
            )
            _add_edge(
                connection,
                str(row["url_seed_id"]),
                relation,
                host_id,
                {"derivation": row.get("derivation")},
            )
        if variant in {"pdns", "pdns_asn"}:
            ledger = enrichment_root / "enrichment_terminal_states.jsonl"
            for row in _iter_jsonl(ledger):
                if row.get("status") not in {"written", "empty", "reused"}:
                    continue
                raw_ref = str(row.get("raw_ref") or "")
                raw_path = Path(raw_ref)
                if not raw_path.is_absolute():
                    raw_path = enrichment_root / raw_path
                if not raw_ref or not raw_path.is_file():
                    continue
                wrapper = json.loads(raw_path.read_text(encoding="utf-8"))
                _project_pdns(
                    connection,
                    endpoint=str(row["endpoint"]),
                    seed_value=str(row["value"]),
                    wrapper=wrapper,
                    include_asn=variant == "pdns_asn",
                    raw_ref=raw_ref,
                )
        connection.commit()
        _write_outputs(connection, output_dir)
        node_counts = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT type, COUNT(*) FROM nodes GROUP BY type"
            )
        }
        relation_counts = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT relation, COUNT(*) FROM edges GROUP BY relation"
            )
        }
        event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        edge_count = connection.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        node_count = connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    finally:
        connection.close()
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(database) + suffix)
        if path.exists():
            path.unlink()
    report = {
        "contract": "trail_otx_variant_graph_v1",
        "variant": variant,
        "event_count": event_count,
        "node_count": node_count,
        "edge_count": edge_count,
        "node_type_counts": dict(sorted(node_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "event_population_invariant": True,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def validate_variant_equivalence(variant_dirs: Iterable[Path]) -> dict[str, Any]:
    signatures = {}
    for directory in variant_dirs:
        rows = [
            (row["event_id"], row["label"], row["class_id"])
            for row in _iter_jsonl(directory / "events.jsonl")
        ]
        signatures[directory.name] = hashlib.sha256(
            json.dumps(rows, sort_keys=True).encode()
        ).hexdigest()
    if len(set(signatures.values())) != 1:
        raise ValueError("variant Event/label populations differ")
    return {"status": "passed", "event_label_signatures": signatures}
