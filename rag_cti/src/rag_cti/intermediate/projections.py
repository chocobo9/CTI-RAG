"""Smoke-level consumer projections over intermediate delivery artifacts."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

_JSONL_FILENAMES = {
    "intermediate_records": "intermediate_records.jsonl",
    "entity_mentions": "entity_mentions.jsonl",
    "relation_mentions": "relation_mentions.jsonl",
    "attribution_signals": "attribution_signals.jsonl",
    "record_features": "record_features.jsonl",
}


def project_delivery_to_rag_smoke(delivery_dir: Path) -> list[dict[str, Any]]:
    """Build deterministic record-level RAG smoke rows from a delivery package."""
    artifacts = _load_artifacts(Path(delivery_dir))
    records = artifacts["intermediate_records"]
    mentions_by_record = _group_by_record(artifacts["entity_mentions"])
    relations_by_record = _group_by_record(artifacts["relation_mentions"])
    signals_by_record = _group_by_record(artifacts["attribution_signals"])

    rows: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda row: str(row["record_id"])):
        record_id = str(record["record_id"])
        source = record.get("source") if isinstance(record.get("source"), dict) else {}
        mentions = mentions_by_record.get(record_id, [])
        relations = relations_by_record.get(record_id, [])
        signals = signals_by_record.get(record_id, [])
        entity_ids = sorted(
            {
                entity_id
                for mention in mentions
                if isinstance(resolution := mention.get("resolution"), dict)
                if isinstance(entity_id := resolution.get("entity_id"), str)
            }
        )
        relation_predicates = sorted(
            {
                predicate
                for relation in relations
                if isinstance(predicate_row := relation.get("predicate"), dict)
                if isinstance(predicate := predicate_row.get("mapped_value"), str)
            }
        )
        attribution_signal_types = sorted(
            {
                signal_type
                for signal in signals
                if isinstance(signal_type := signal.get("signal_type"), str)
            }
        )
        rows.append(
            {
                "record_id": record_id,
                "connector_source": source.get("connector_source"),
                "source_record_id": source.get("source_record_id"),
                "summary_text": _summary_text(
                    record,
                    mentions,
                    relation_predicates,
                    attribution_signal_types,
                ),
                "entity_ids": entity_ids,
                "relation_predicates": relation_predicates,
                "attribution_signal_types": attribution_signal_types,
                "raw_ref": dict(record["raw_ref"]),
            }
        )
    return rows


def project_delivery_to_gnn_smoke(delivery_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Build smoke-level GNN-shaped nodes, edges, and label evidence rows."""
    artifacts = _load_artifacts(Path(delivery_dir))
    records_by_id = {
        str(record["record_id"]): record for record in artifacts["intermediate_records"]
    }

    nodes = [
        _node_row(mention, records_by_id[str(mention["record_id"])])
        for mention in sorted(
            artifacts["entity_mentions"],
            key=lambda row: str(row["entity_mention_id"]),
        )
    ]
    edges = [
        _edge_row(relation, records_by_id[str(relation["record_id"])])
        for relation in sorted(
            artifacts["relation_mentions"],
            key=lambda row: str(row["relation_mention_id"]),
        )
    ]
    label_evidence = [
        _label_evidence_row(signal, records_by_id[str(signal["record_id"])])
        for signal in sorted(
            artifacts["attribution_signals"],
            key=lambda row: str(row["attribution_signal_id"]),
        )
    ]
    return {"nodes": nodes, "edges": edges, "label_evidence": label_evidence}


def _node_row(mention: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    source = record["source"]
    resolution = mention.get("resolution") if isinstance(mention.get("resolution"), dict) else {}
    return {
        "node_id": mention["entity_mention_id"],
        "entity_mention_id": mention["entity_mention_id"],
        "record_id": mention["record_id"],
        "connector_source": source["connector_source"],
        "raw_ref": dict(record["raw_ref"]),
        "entity_type": mention["entity_type"],
        "raw_value": mention["raw_value"],
        "normalized_value": mention["normalized_value"],
        "resolved_entity_id": resolution.get("entity_id"),
        "resolution_method": resolution.get("resolution_method"),
        "value_type": dict(mention["value_type"]),
    }


def _edge_row(relation: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    source = record["source"]
    predicate = relation["predicate"]
    derivation = relation["derivation"]
    return {
        "edge_id": relation["relation_mention_id"],
        "relation_mention_id": relation["relation_mention_id"],
        "record_id": relation["record_id"],
        "connector_source": source["connector_source"],
        "raw_ref": dict(record["raw_ref"]),
        "subject_node_id": relation["subject"]["entity_mention_id"],
        "object_node_id": relation["object"]["entity_mention_id"],
        "subject_entity_type": relation["subject"]["entity_type"],
        "object_entity_type": relation["object"]["entity_type"],
        "predicate": predicate["mapped_value"],
        "predicate_mapping_status": predicate["mapping_status"],
        "source_field": derivation.get("source_field"),
        "extraction_method": derivation.get("extraction_method"),
        "label_availability": derivation.get("label_availability"),
    }


def _label_evidence_row(signal: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    source = record["source"]
    return {
        "label_evidence_id": signal["attribution_signal_id"],
        "attribution_signal_id": signal["attribution_signal_id"],
        "record_id": signal["record_id"],
        "connector_source": source["connector_source"],
        "raw_ref": dict(record["raw_ref"]),
        "signal_type": signal["signal_type"],
        "target_entity_type": signal["target_entity_type"],
        "raw_label": signal["raw_label"],
        "resolved_entity_id": signal.get("resolved_entity_id"),
        "source_field": signal["source_field"],
        "derivation_method": signal["derivation_method"],
        "is_ground_truth": False,
    }


def _summary_text(
    record: dict[str, Any],
    mentions: list[dict[str, Any]],
    relation_predicates: list[str],
    attribution_signal_types: list[str],
) -> str:
    source = record["source"]
    values = sorted(
        {
            raw_value
            for mention in mentions
            if isinstance(raw_value := mention.get("raw_value"), str)
        }
    )
    return (
        f"{source['connector_source']} record {source.get('source_record_id')}: "
        f"entities={', '.join(values) or 'none'}; "
        f"relations={', '.join(relation_predicates) or 'none'}; "
        f"attribution_signals={', '.join(attribution_signal_types) or 'none'}"
    )


def _load_artifacts(delivery_dir: Path) -> dict[str, list[dict[str, Any]]]:
    intermediate_dir = delivery_dir / "intermediate"
    return {
        artifact: _read_jsonl(intermediate_dir / filename)
        for artifact, filename in _JSONL_FILENAMES.items()
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row must be an object: {path}")
        rows.append(value)
    return rows


def _group_by_record(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["record_id"])].append(row)
    return grouped
