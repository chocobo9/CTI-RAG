"""Slice the global OTX seed inventory by a frozen TRAIL Event population."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path) -> list[dict[str, Any]]:
    result = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path} contains a non-object row")
                result.append(value)
    return result


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(
                json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n"
            )
            count += 1
    return count


def build_population_inventory(
    *,
    inventory_db: Path,
    labels_jsonl: Path,
    output_dir: Path,
    max_supported_mentions: int = 1000,
) -> dict[str, Any]:
    """Export expansion-approved Event/seed relations for one frozen population."""

    inventory_db = inventory_db.resolve()
    labels_jsonl = labels_jsonl.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    labels = _rows(labels_jsonl)
    label_by_event = {str(row["event_id"]): row for row in labels}
    if len(label_by_event) != len(labels):
        raise ValueError("duplicate event_id in label manifest")

    connection = sqlite3.connect(f"file:{inventory_db.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("CREATE TEMP TABLE selected_events (pulse_id TEXT PRIMARY KEY)")
        connection.executemany(
            "INSERT INTO selected_events VALUES (?)",
            ((event_id,) for event_id in sorted(label_by_event)),
        )
        missing = [
            row[0]
            for row in connection.execute(
                """
                SELECT s.pulse_id FROM selected_events s
                LEFT JOIN events e ON e.pulse_id = s.pulse_id
                WHERE e.pulse_id IS NULL ORDER BY s.pulse_id
                """
            )
        ]
        if missing:
            raise ValueError(f"{len(missing)} population Events are absent from inventory")

        event_stats = {
            row["pulse_id"]: {
                "supported_network_mentions": int(row["mentions"] or 0),
                "unique_primary_seeds": int(row["unique_seeds"] or 0),
            }
            for row in connection.execute(
                """
                SELECT se.pulse_id,
                       COALESCE(SUM(es.mention_count), 0) AS mentions,
                       COUNT(es.seed_id) AS unique_seeds
                FROM selected_events se
                LEFT JOIN event_seed es ON es.pulse_id = se.pulse_id
                GROUP BY se.pulse_id
                """
            )
        }
        decision_rows = []
        approved: set[str] = set()
        reasons: Counter[str] = Counter()
        for event_id in sorted(label_by_event):
            stats = event_stats[event_id]
            if stats["supported_network_mentions"] == 0:
                state = "no_supported_ioc"
            elif stats["supported_network_mentions"] > max_supported_mentions:
                state = "quarantined_large_event"
            else:
                state = "expanded"
                approved.add(event_id)
            reasons[state] += 1
            decision_rows.append(
                {
                    **label_by_event[event_id],
                    **stats,
                    "max_supported_mentions": max_supported_mentions,
                    "expansion_state": state,
                    "event_membership_preserved": True,
                }
            )
        _write_jsonl(output_dir / "population_events.jsonl", decision_rows)

        connection.execute("CREATE TEMP TABLE approved_events (pulse_id TEXT PRIMARY KEY)")
        connection.executemany(
            "INSERT INTO approved_events VALUES (?)",
            ((event_id,) for event_id in sorted(approved)),
        )
        occurrence_rows = (
            {
                "event_id": row["pulse_id"],
                "seed_id": row["seed_id"],
                "seed_type": row["seed_type"],
                "value": row["value"],
                "mention_count": row["mention_count"],
                "source_types": json.loads(row["source_types_json"]),
                "indicator_created_first": row["indicator_created_first"],
                "indicator_created_last": row["indicator_created_last"],
                "indicator_expiration_first": row["indicator_expiration_first"],
                "indicator_expiration_last": row["indicator_expiration_last"],
                "derivation": "otx_event_indicator_occurrence",
            }
            for row in connection.execute(
                """
                SELECT es.*, s.seed_type, s.value
                FROM event_seed es
                JOIN approved_events a ON a.pulse_id = es.pulse_id
                JOIN seeds s ON s.seed_id = es.seed_id
                ORDER BY es.pulse_id, s.seed_type, s.value
                """
            )
        )
        occurrence_count = _write_jsonl(
            output_dir / "event_seed_occurrences.jsonl", occurrence_rows
        )
        url_host_rows = (
            {
                "event_id": row["pulse_id"],
                "url_seed_id": row["url_seed_id"],
                "host_seed_id": row["host_seed_id"],
                "host_seed_type": row["seed_type"],
                "host_value": row["value"],
                "derivation": "deterministic_url_hostname_parse",
            }
            for row in connection.execute(
                """
                SELECT uh.*, s.seed_type, s.value
                FROM url_host uh
                JOIN approved_events a ON a.pulse_id = uh.pulse_id
                JOIN seeds s ON s.seed_id = uh.host_seed_id
                ORDER BY uh.pulse_id, uh.url_seed_id, uh.host_seed_id
                """
            )
        )
        url_host_count = _write_jsonl(
            output_dir / "url_host_occurrences.jsonl", url_host_rows
        )

        seed_query = """
            WITH reachable(seed_id, origin, pulse_id) AS (
                SELECT es.seed_id, 'primary', es.pulse_id
                FROM event_seed es JOIN approved_events a ON a.pulse_id = es.pulse_id
                UNION ALL
                SELECT uh.host_seed_id, 'url_host', uh.pulse_id
                FROM url_host uh JOIN approved_events a ON a.pulse_id = uh.pulse_id
            )
            SELECT s.*,
                   COUNT(DISTINCT r.pulse_id) AS event_count,
                   MAX(CASE WHEN r.origin = 'primary' THEN 1 ELSE 0 END) AS primary_origin,
                   MAX(CASE WHEN r.origin = 'url_host' THEN 1 ELSE 0 END) AS url_host_origin
            FROM reachable r JOIN seeds s ON s.seed_id = r.seed_id
            WHERE s.seed_type IN ('domain', 'ip') AND s.enrichment_eligible = 1
            GROUP BY s.seed_id
            ORDER BY s.seed_type, s.value
        """
        seed_rows = []
        old_coverage = Counter()
        seed_types = Counter()
        for row in connection.execute(seed_query):
            seed_types[row["seed_type"]] += 1
            if row["seed_type"] == "domain" and row["old_pdns_lookup"]:
                old_coverage["domain_lookup_covered"] += 1
            if row["seed_type"] == "domain" and row["old_pdns_nonempty"]:
                old_coverage["domain_nonempty_covered"] += 1
            if row["seed_type"] == "ip" and row["old_pdns_asn_observed"]:
                old_coverage["ip_asn_observed"] += 1
            origins = []
            if row["primary_origin"]:
                origins.append("primary")
            if row["url_host_origin"]:
                origins.append("url_host")
            seed_rows.append(
                {
                    "seed_id": row["seed_id"],
                    "seed_type": row["seed_type"],
                    "value": row["value"],
                    "ip_version": row["ip_version"],
                    "ip_scope": row["ip_scope"],
                    "origins": origins,
                    "event_count": row["event_count"],
                    "old_pdns_lookup": bool(row["old_pdns_lookup"]),
                    "old_pdns_nonempty": bool(row["old_pdns_nonempty"]),
                    "old_pdns_record_count": row["old_pdns_record_count"],
                    "old_pdns_asn_observed": bool(row["old_pdns_asn_observed"]),
                }
            )
        _write_jsonl(output_dir / "enrichment_seeds.jsonl", seed_rows)
    finally:
        connection.close()

    report = {
        "contract": "trail_population_enrichment_inventory_v1",
        "population_events": len(labels),
        "expansion_approved_events": reasons["expanded"],
        "quarantined_large_events": reasons["quarantined_large_event"],
        "no_supported_ioc_events": reasons["no_supported_ioc"],
        "max_supported_mentions": max_supported_mentions,
        "event_seed_occurrences": occurrence_count,
        "url_host_occurrences": url_host_count,
        "enrichment_seed_count": len(seed_rows),
        "enrichment_seed_types": dict(sorted(seed_types.items())),
        "old_coverage": {
            "domain_lookup_covered": old_coverage["domain_lookup_covered"],
            "domain_nonempty_covered": old_coverage["domain_nonempty_covered"],
            "ip_asn_observed": old_coverage["ip_asn_observed"],
        },
        "input": {
            "inventory_db": str(inventory_db),
            "inventory_db_sha256": _sha256(inventory_db),
            "labels_jsonl": str(labels_jsonl),
            "labels_jsonl_sha256": _sha256(labels_jsonl),
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }
    _write_json(output_dir / "seed_coverage_report.json", report)
    return report

