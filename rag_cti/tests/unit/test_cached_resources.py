from __future__ import annotations

from types import SimpleNamespace

import rag_cti
import rag_cti.knowledge as knowledge


class _Secret:
    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


class _FakeStore:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_close_cached_resources_closes_fact_store_and_clears_cache(monkeypatch) -> None:
    created: list[_FakeStore] = []

    def connect(_uri: str, _user: str, _password: str, _database: str) -> _FakeStore:
        store = _FakeStore()
        created.append(store)
        return store

    monkeypatch.setattr(
        rag_cti,
        "get_settings",
        lambda: SimpleNamespace(
            neo4j_uri="bolt://example",
            neo4j_user="neo4j",
            neo4j_password=_Secret("secret"),
            neo4j_database="neo4j",
        ),
    )
    monkeypatch.setattr(knowledge.Neo4jFactStore, "connect", staticmethod(connect))
    rag_cti._default_fact_store.cache_clear()

    first = rag_cti._default_fact_store()
    assert first is created[0]

    rag_cti.close_cached_resources()

    assert first.closed
    second = rag_cti._default_fact_store()
    assert second is not first
