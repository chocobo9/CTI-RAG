"""Load M3 facts/supports into the CTI-RAG Neo4j (M4 DM4-1, isolated instance).

Reified schema — supports/evidence are first-class so the reverse bridge
(evidence -> facts) is an indexed one-hop, not an edge-property scan:

    (:Entity   {entity_id, type, name})
    (:Fact     {fact_id, predicate, group, aggregate_credibility,
                aggregate_version, conflict, support_count, distinct_origins})
    (:Evidence {evidence_id})                     # == chunk.id; content stays in Qdrant
    (subject:Entity)-[:SUBJECT]->(:Fact)
    (:Fact)-[:OBJECT]->(object:Entity)
    (:Evidence)-[:SUPPORTS {origin, confidence, label_availability,
                            observed_first, observed_last}]->(:Fact)

Idempotent: MERGE on entity_id / fact_id / (evidence_id, fact_id, origin) — the M3
identity keys — so re-runs upsert, never duplicate. Names are best-effort from the
entity registry (indicators/asns have none -> fall back to the id).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from rag_cti.config import get_settings

_ROOT = Path(__file__).resolve().parents[1]
_STAGING = _ROOT / "data" / "processed" / "v5_staging"
FACTS_PATH = _STAGING / "facts.jsonl"
SUPPORTS_PATH = _STAGING / "supports.jsonl"
REGISTRY_PATH = _ROOT / "data" / "processed" / "entity_registry.jsonl"
BATCH = 2000

_CONSTRAINTS = (
    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
    "CREATE CONSTRAINT fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE",
    "CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (v:Evidence) REQUIRE v.evidence_id IS UNIQUE",
)

_FACT_CYPHER = """
UNWIND $rows AS r
MERGE (s:Entity {entity_id: r.subject_id})
  ON CREATE SET s.type = r.subject_type
SET s.name = coalesce(r.subject_name, s.name, r.subject_id)
MERGE (o:Entity {entity_id: r.object_id})
  ON CREATE SET o.type = r.object_type
SET o.name = coalesce(r.object_name, o.name, r.object_id)
MERGE (f:Fact {fact_id: r.fact_id})
SET f.predicate = r.predicate, f.group = r.group,
    f.aggregate_credibility = r.aggregate_credibility,
    f.aggregate_version = r.aggregate_version,
    f.conflict = r.conflict, f.support_count = r.support_count,
    f.distinct_origins = r.distinct_origins
MERGE (s)-[:SUBJECT]->(f)
MERGE (f)-[:OBJECT]->(o)
"""

# SUPPORTS identity = (evidence_id, fact_id, origin): MERGE keyed on origin so two
# sources asserting the same fact via the same chunk stay distinct edges.
_SUPPORT_CYPHER = """
UNWIND $rows AS r
MATCH (f:Fact {fact_id: r.fact_id})
MERGE (e:Evidence {evidence_id: r.evidence_id})
MERGE (e)-[sup:SUPPORTS {origin: r.origin}]->(f)
SET sup.confidence = r.confidence,
    sup.label_availability = r.label_availability,
    sup.observed_first = r.observed_first,
    sup.observed_last = r.observed_last
"""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _load_registry_names() -> dict[str, str]:
    if not REGISTRY_PATH.exists():
        return {}
    names: dict[str, str] = {}
    for rec in _load_jsonl(REGISTRY_PATH):
        eid, name = rec.get("entity_id"), rec.get("canonical_name")
        if eid and name:
            names[eid] = name
    return names


def _batched(rows: list[dict[str, Any]], size: int):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def main() -> None:
    settings = get_settings()
    names = _load_registry_names()

    facts = _load_jsonl(FACTS_PATH)
    for f in facts:
        f["subject_name"] = names.get(f["subject_id"])
        f["object_name"] = names.get(f["object_id"])
    supports = _load_jsonl(SUPPORTS_PATH)

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    try:
        with driver.session(database=settings.neo4j_database) as sess:
            for ddl in _CONSTRAINTS:
                sess.run(ddl)
            for batch in _batched(facts, BATCH):
                sess.run(_FACT_CYPHER, rows=batch)
            for batch in _batched(supports, BATCH):
                sess.run(_SUPPORT_CYPHER, rows=batch)

            def count(q: str) -> int:
                return int(sess.run(q).single()[0])

            print(f"registry names loaded : {len(names)}")
            print(f"Entity nodes          : {count('MATCH (e:Entity) RETURN count(e)')}")
            print(f"Fact nodes            : {count('MATCH (f:Fact) RETURN count(f)')}")
            print(f"Evidence nodes        : {count('MATCH (v:Evidence) RETURN count(v)')}")
            print(f"SUBJECT edges         : {count('MATCH ()-[r:SUBJECT]->() RETURN count(r)')}")
            print(f"OBJECT edges          : {count('MATCH ()-[r:OBJECT]->() RETURN count(r)')}")
            print(f"SUPPORTS edges        : {count('MATCH ()-[r:SUPPORTS]->() RETURN count(r)')}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
