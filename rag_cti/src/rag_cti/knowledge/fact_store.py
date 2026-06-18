"""FactStore — query the M3 knowledge graph (DM4-1: an isolated Neo4j).

:class:`FactStoreProto` is the backend-free contract the v1 agent calls;
:class:`Neo4jFactStore` implements it against the reified Entity/Fact/Evidence
graph loaded by ``scripts/load_facts_neo4j.py``. Three deterministic tools:

- ``graph_query``    — enumerate one (subject[, predicate, object_type]) category,
  exhaustively (NOT truncated), credibility-desc, each row carrying its supports.
- ``graph_outline``  — the coverage gauge: which relation categories an entity has
  and how many (the agent's planning/sufficiency basis, M4 §2/§3).
- ``facts_for_evidence`` — the reverse bridge: given a chunk id, the facts it
  supports (enrich vector results with provenance).

Citations come back with empty ``content``; the caller fills it from Qdrant
(M4 invariant: the graph emits structure, the bridge fills content).
"""

from __future__ import annotations

from typing import Any, Protocol

from neo4j import Driver, GraphDatabase

from rag_cti.types import FactCitation, FactRow, GraphOutline, OutlineEntry

_GRAPH_QUERY = """
MATCH (s:Entity {entity_id: $subject_id})-[:SUBJECT]->(f:Fact)-[:OBJECT]->(o:Entity)
WHERE ($predicate IS NULL OR f.predicate = $predicate)
  AND ($object_type IS NULL OR o.type = $object_type)
  AND ($object_id IS NULL OR o.entity_id = $object_id)
  AND f.aggregate_credibility >= $min_credibility
MATCH (ev:Evidence)-[sup:SUPPORTS]->(f)
WITH s, f, o, collect({
    evidence_id: ev.evidence_id, origin: sup.origin, confidence: sup.confidence,
    label_availability: sup.label_availability,
    observed_first: sup.observed_first, observed_last: sup.observed_last}) AS supports
RETURN s.entity_id AS subject_id, coalesce(s.name, s.entity_id) AS subject_name,
       f.fact_id AS fact_id, f.predicate AS predicate,
       o.entity_id AS object_id, coalesce(o.name, o.entity_id) AS object_name,
       o.type AS object_type, f.aggregate_credibility AS aggregate_credibility,
       coalesce(f.conflict, false) AS conflict,
       f.distinct_origins AS distinct_origins,
       coalesce(f.support_count, 0) AS support_count, supports
ORDER BY f.aggregate_credibility DESC, f.fact_id
"""

_FACTS_FOR_EVIDENCE = """
MATCH (:Evidence {evidence_id: $evidence_id})-[:SUPPORTS]->(f:Fact)
MATCH (s:Entity)-[:SUBJECT]->(f)-[:OBJECT]->(o:Entity)
MATCH (ev:Evidence)-[sup:SUPPORTS]->(f)
WITH s, f, o, collect({
    evidence_id: ev.evidence_id, origin: sup.origin, confidence: sup.confidence,
    label_availability: sup.label_availability,
    observed_first: sup.observed_first, observed_last: sup.observed_last}) AS supports
RETURN s.entity_id AS subject_id, coalesce(s.name, s.entity_id) AS subject_name,
       f.fact_id AS fact_id, f.predicate AS predicate,
       o.entity_id AS object_id, coalesce(o.name, o.entity_id) AS object_name,
       o.type AS object_type, f.aggregate_credibility AS aggregate_credibility,
       coalesce(f.conflict, false) AS conflict,
       f.distinct_origins AS distinct_origins,
       coalesce(f.support_count, 0) AS support_count, supports
ORDER BY f.aggregate_credibility DESC, f.fact_id
"""

_ENTITY_INFO = """
MATCH (e:Entity {entity_id: $entity_id})
RETURN e.entity_id AS entity_id, coalesce(e.name, e.entity_id) AS entity_name,
       coalesce(e.type, 'unknown') AS entity_type
"""

_OUTLINE_OUT = """
MATCH (:Entity {entity_id: $entity_id})-[:SUBJECT]->(f:Fact)-[:OBJECT]->(o:Entity)
RETURN f.predicate AS predicate, o.type AS other_type, count(*) AS count,
       max(f.aggregate_credibility) AS max_credibility
ORDER BY count DESC, predicate
"""

_OUTLINE_IN = """
MATCH (s:Entity)-[:SUBJECT]->(f:Fact)-[:OBJECT]->(:Entity {entity_id: $entity_id})
RETURN f.predicate AS predicate, s.type AS other_type, count(*) AS count,
       max(f.aggregate_credibility) AS max_credibility
ORDER BY count DESC, predicate
"""


def _records_to_factrows(records: list[dict[str, Any]]) -> tuple[FactRow, ...]:
    rows: list[FactRow] = []
    for rec in records:
        citations = tuple(
            FactCitation(
                evidence_id=s["evidence_id"],
                origin=s["origin"],
                confidence=s["confidence"],
                label_availability=s["label_availability"],
                observed_first=s.get("observed_first"),
                observed_last=s.get("observed_last"),
            )
            for s in rec["supports"]
            if s.get("evidence_id")
        )
        rows.append(
            FactRow(
                fact_id=rec["fact_id"],
                subject_id=rec["subject_id"],
                subject_name=rec["subject_name"],
                predicate=rec["predicate"],
                object_id=rec["object_id"],
                object_name=rec["object_name"],
                object_type=rec["object_type"],
                aggregate_credibility=rec["aggregate_credibility"],
                conflict=rec["conflict"],
                distinct_origins=tuple(rec.get("distinct_origins") or ()),
                support_count=rec["support_count"],
                citations=citations,
            )
        )
    return tuple(rows)


class FactStoreProto(Protocol):
    """Backend-free contract for the M4 graph tools (the v1 agent's tool set)."""

    def graph_query(
        self,
        *,
        subject_id: str,
        predicate: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        min_credibility: float = 0.0,
    ) -> tuple[FactRow, ...]: ...

    def graph_outline(self, entity_id: str) -> GraphOutline | None: ...

    def facts_for_evidence(self, evidence_id: str) -> tuple[FactRow, ...]: ...

    def close(self) -> None: ...


class Neo4jFactStore:
    """FactStoreProto over the CTI-RAG-isolated Neo4j reified fact graph."""

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    @classmethod
    def connect(cls, uri: str, user: str, password: str, database: str = "neo4j") -> Neo4jFactStore:
        return cls(GraphDatabase.driver(uri, auth=(user, password)), database)

    def close(self) -> None:
        self._driver.close()

    def _read(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            return session.run(cypher, **params).data()

    def graph_query(
        self,
        *,
        subject_id: str,
        predicate: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        min_credibility: float = 0.0,
    ) -> tuple[FactRow, ...]:
        records = self._read(
            _GRAPH_QUERY,
            subject_id=subject_id,
            predicate=predicate,
            object_type=object_type,
            object_id=object_id,
            min_credibility=min_credibility,
        )
        return _records_to_factrows(records)

    def facts_for_evidence(self, evidence_id: str) -> tuple[FactRow, ...]:
        return _records_to_factrows(self._read(_FACTS_FOR_EVIDENCE, evidence_id=evidence_id))

    def graph_outline(self, entity_id: str) -> GraphOutline | None:
        info = self._read(_ENTITY_INFO, entity_id=entity_id)
        if not info:
            return None
        head = info[0]
        outgoing = tuple(
            OutlineEntry(**row) for row in self._read(_OUTLINE_OUT, entity_id=entity_id)
        )
        incoming = tuple(
            OutlineEntry(**row) for row in self._read(_OUTLINE_IN, entity_id=entity_id)
        )
        return GraphOutline(
            entity_id=head["entity_id"],
            entity_name=head["entity_name"],
            entity_type=head["entity_type"],
            outgoing=outgoing,
            incoming=incoming,
        )
