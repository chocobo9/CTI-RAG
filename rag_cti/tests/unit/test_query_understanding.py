from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from rag_cti.retrieval.constraint_extract import ExtractedEntity, RewriteOutput
from rag_cti.retrieval.query_rewrite import LLMQueryRewriter, QueryRewriteRetriever
from rag_cti.types import Chunk, RetrievalResult

_SHA256 = "b" * 64

_NODES = [
    {
        "ontology_id": "G0016",
        "type": "group",
        "name": "APT29",
        "aliases": ["Cozy Bear"],
        "tactics": [],
        "attack_version": "18.1",
    },
]


def _settings(**over: Any) -> Any:
    base = {
        "query_rewrite_enabled": True,
        "query_rewrite_max_subqueries": 4,
        "constraint_routing_enabled": True,
        "constraint_boost_weight": 1.0,
    }
    base.update(over)
    return SimpleNamespace(**base)


def _rewriter(canned: str | None, settings: Any | None = None) -> LLMQueryRewriter:
    rw = LLMQueryRewriter(llm_client=object(), settings=settings or _settings())
    rw._generate_raw = lambda system, user: canned  # type: ignore[method-assign]
    return rw


# --- rewrite_with_entities: object schema ---


def test_object_form_parses_queries_and_entities() -> None:
    rw = _rewriter(
        '{"queries": ["what does APT29 use"], "entities": [{"name": "APT29", "type": "actor"}]}'
    )
    out = rw.rewrite_with_entities("apt29 stuff")
    assert out.queries == ("what does APT29 use",)
    assert out.entities == (ExtractedEntity("APT29", "actor"),)


def test_legacy_array_form_yields_queries_no_entities() -> None:
    rw = _rewriter('["clean query"]')
    out = rw.rewrite_with_entities("dirty")
    assert out.queries == ("clean query",)
    assert out.entities == ()


def test_malformed_entity_dropped_queries_intact() -> None:
    rw = _rewriter(
        '{"queries": ["q"], "entities": ['
        '{"name": "APT29", "type": "actor"},'  # kept
        '{"name": "", "type": "actor"},'  # empty name -> drop
        '{"name": "X", "type": "location"},'  # bad type -> drop
        '{"type": "actor"},'  # no name -> drop
        '"notadict"]}'  # not a dict -> drop
    )
    out = rw.rewrite_with_entities("q")
    assert out.queries == ("q",)
    assert out.entities == (ExtractedEntity("APT29", "actor"),)


def test_whole_llm_failure_falls_back_empty_entities() -> None:
    rw = _rewriter("not json at all")
    out = rw.rewrite_with_entities("some query")
    assert out.queries == ("some query",)
    assert out.entities == ()


def test_disabled_returns_query_no_llm_no_entities() -> None:
    rw = _rewriter(
        '{"queries": ["x"], "entities": [{"name":"A","type":"actor"}]}',
        _settings(query_rewrite_enabled=False),
    )
    out = rw.rewrite_with_entities("messy")
    assert out == RewriteOutput(queries=("messy",))


def test_pure_ioc_skips_llm_and_refangs() -> None:
    rw = _rewriter('{"queries": ["nope"], "entities": []}')
    out = rw.rewrite_with_entities("evil[.]com")
    assert out.queries == ("evil.com",)


def test_entity_with_ioc_placeholder_rejected() -> None:
    # an IOC placeholder must never become an entity name
    rw = _rewriter(
        '{"queries": ["what drops <IOC_1>"], "entities": [{"name": "<IOC_1>", "type": "family"}]}'
    )
    out = rw.rewrite_with_entities(f"what drops {_SHA256}")
    assert out.queries == (f"what drops {_SHA256}",)
    assert out.entities == ()


def test_rewrite_back_compat_returns_list() -> None:
    rw = _rewriter('{"queries": ["a", "b"], "entities": []}')
    assert rw.rewrite("q") == ["a", "b"]


# --- QueryRewriteRetriever.understand + seam-1 boost ---


def _res(cid: str, score: float, **md: Any) -> RetrievalResult:
    chunk = Chunk(
        id=cid, parent_doc_id="d", source="mitre", content="c", chunk_index=0, metadata=md
    )
    return RetrievalResult(document=chunk, score=score, rank=0, retriever_source="x")


class _FakeBase:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results
        self.calls: list[str] = []

    def search(self, query: str, top_k: int = 10, **_: Any) -> list[RetrievalResult]:
        self.calls.append(query)
        return list(self._results)


class _StubRewriter:
    def __init__(self, out: RewriteOutput) -> None:
        self._out = out
        self.calls = 0

    def rewrite_with_entities(self, query: str, history: Any = None) -> RewriteOutput:
        self.calls += 1
        return self._out


def test_understand_builds_constraint_from_entities() -> None:
    rw = _StubRewriter(
        RewriteOutput(queries=("q",), entities=(ExtractedEntity("Cozy Bear", "actor"),))
    )
    wrap = QueryRewriteRetriever(_FakeBase([]), rw, settings=_settings(), ontology_nodes=_NODES)  # type: ignore[arg-type]
    subqueries, constraint = wrap.understand("q")
    assert subqueries == ("q",)
    assert constraint.entity_ids == ("actor_G0016",)


def test_direct_search_boosts_matching_result() -> None:
    base = _FakeBase([_res("nonmatch", 0.9), _res("match", 0.5, entity_ids=["actor_G0016"])])
    rw = _StubRewriter(RewriteOutput(queries=("q",), entities=(ExtractedEntity("APT29", "actor"),)))
    wrap = QueryRewriteRetriever(
        base,
        rw,
        settings=_settings(constraint_boost_weight=1.0),  # type: ignore[arg-type]
        ontology_nodes=_NODES,
    )
    out = wrap.search("apt29", top_k=10)
    assert [r.document.id for r in out][0] == "match"  # 0.5 + 1.0 > 0.9
    assert rw.calls == 1  # exactly one understanding call


def test_routing_disabled_no_boost() -> None:
    base = _FakeBase([_res("nonmatch", 0.9), _res("match", 0.5, entity_ids=["actor_G0016"])])
    rw = _StubRewriter(RewriteOutput(queries=("q",), entities=(ExtractedEntity("APT29", "actor"),)))
    wrap = QueryRewriteRetriever(
        base,
        rw,
        settings=_settings(constraint_routing_enabled=False),  # type: ignore[arg-type]
        ontology_nodes=_NODES,
    )
    out = wrap.search("apt29", top_k=10)
    assert [r.document.id for r in out][0] == "nonmatch"  # order untouched


def test_pipeline_supplied_subqueries_skip_understand_and_skip_seam1_boost() -> None:
    from rag_cti.types import PayloadConstraint

    base = _FakeBase([_res("nonmatch", 0.9), _res("match", 0.5, attack_ids=["T1003"])])
    rw = _StubRewriter(RewriteOutput(queries=("SHOULD NOT BE USED",)))
    wrap = QueryRewriteRetriever(base, rw, settings=_settings(), ontology_nodes=_NODES)  # type: ignore[arg-type]
    out = wrap.search(
        "creds",
        top_k=10,
        subqueries=("creds",),
        boost_constraint=PayloadConstraint(attack_ids=("T1003",)),
    )
    assert rw.calls == 0  # understand NOT called when subqueries supplied
    assert base.calls == ["creds"]
    # pipeline-driven: the retriever does NOT boost (the pipeline re-applies it after
    # rerank), so the raw base order is preserved here — no double counting.
    assert [r.document.id for r in out] == ["nonmatch", "match"]
