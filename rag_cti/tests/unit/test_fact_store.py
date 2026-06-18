"""Unit tests for FactStore record assembly + Neo4jFactStore (fake driver)."""

from __future__ import annotations

from typing import Any

from rag_cti.knowledge.fact_store import Neo4jFactStore, _records_to_factrows


def _support(evidence_id: str | None) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "origin": "mitre",
        "confidence": 0.9,
        "label_availability": "direct",
        "observed_first": None,
        "observed_last": None,
    }


def _record(
    fact_id: str, supports: list[dict[str, Any]], *, conflict: bool = False
) -> dict[str, Any]:
    return {
        "subject_id": "actor_G0016",
        "subject_name": "APT29",
        "fact_id": fact_id,
        "predicate": "uses",
        "object_id": "technique_T1566",
        "object_name": "Phishing",
        "object_type": "technique",
        "aggregate_credibility": 0.95,
        "conflict": conflict,
        "distinct_origins": ["mitre", "otx"],
        "support_count": len(supports),
        "supports": supports,
    }


def test_records_to_factrows_builds_rows_and_citations() -> None:
    rows = _records_to_factrows([_record("f1", [_support("e1"), _support("e2")], conflict=True)])
    assert len(rows) == 1
    row = rows[0]
    assert row.fact_id == "f1"
    assert row.subject_name == "APT29"
    assert row.conflict is True
    assert row.distinct_origins == ("mitre", "otx")
    assert tuple(c.evidence_id for c in row.citations) == ("e1", "e2")


def test_records_to_factrows_skips_null_evidence() -> None:
    # A fact whose supports collapse to a null-evidence map yields no citations.
    rows = _records_to_factrows([_record("f1", [_support(None)])])
    assert rows[0].citations == ()


class _FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def data(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.queries: list[str] = []

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def run(self, cypher: str, **params: object) -> _FakeResult:
        self.queries.append(cypher)
        return _FakeResult(self._rows)


class _FakeDriver:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.closed = False

    def session(self, database: str = "neo4j") -> _FakeSession:
        return _FakeSession(self._rows)

    def close(self) -> None:
        self.closed = True


def test_neo4j_fact_store_graph_query_maps_records() -> None:
    driver = _FakeDriver([_record("f1", [_support("e1")])])
    store = Neo4jFactStore(driver, database="neo4j")  # type: ignore[arg-type]
    rows = store.graph_query(subject_id="actor_G0016", predicate="uses")
    assert len(rows) == 1
    assert rows[0].fact_id == "f1"


def test_neo4j_fact_store_facts_for_evidence_maps_records() -> None:
    driver = _FakeDriver([_record("f1", [_support("e1")])])
    store = Neo4jFactStore(driver, database="neo4j")  # type: ignore[arg-type]
    rows = store.facts_for_evidence("e1")
    assert rows[0].subject_id == "actor_G0016"


def test_neo4j_fact_store_close_closes_driver() -> None:
    driver = _FakeDriver([])
    Neo4jFactStore(driver).close()  # type: ignore[arg-type]
    assert driver.closed is True


class _RoutingSession:
    """Returns entity-info rows or outline-entry rows by inspecting the Cypher."""

    def __init__(self, info: list[dict[str, Any]], entries: list[dict[str, Any]]) -> None:
        self._info = info
        self._entries = entries

    def __enter__(self) -> _RoutingSession:
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def run(self, cypher: str, **params: object) -> _FakeResult:
        if "entity_name" in cypher:
            return _FakeResult(self._info)
        if "other_type" in cypher:
            return _FakeResult(self._entries)
        return _FakeResult([])


class _RoutingDriver:
    def __init__(self, info: list[dict[str, Any]], entries: list[dict[str, Any]]) -> None:
        self._info = info
        self._entries = entries

    def session(self, database: str = "neo4j") -> _RoutingSession:
        return _RoutingSession(self._info, self._entries)

    def close(self) -> None:
        pass


def test_graph_outline_assembles_coverage_map() -> None:
    info = [{"entity_id": "actor_G0016", "entity_name": "APT29", "entity_type": "actor"}]
    entries = [
        {"predicate": "uses", "other_type": "technique", "count": 24, "max_credibility": 0.97}
    ]
    store = Neo4jFactStore(_RoutingDriver(info, entries))  # type: ignore[arg-type]
    outline = store.graph_outline("actor_G0016")
    assert outline is not None
    assert outline.entity_name == "APT29"
    assert outline.outgoing[0].predicate == "uses"
    assert outline.outgoing[0].count == 24
    assert outline.incoming[0].other_type == "technique"


def test_graph_outline_returns_none_when_entity_absent() -> None:
    store = Neo4jFactStore(_RoutingDriver([], []))  # type: ignore[arg-type]
    assert store.graph_outline("nope") is None
