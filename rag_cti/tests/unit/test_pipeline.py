from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from rag_cti.retrieval.pipeline import Pipeline, build_pipeline
from rag_cti.types import Chunk, PayloadConstraint, QueryResult, RetrievalResult

_SUBTECH_EDGES = [{"child": "T1003.001", "parent": "T1003", "edge": "subtechnique-of"}]

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


def _make_result(chunk_id: str, score: float = 0.9) -> RetrievalResult:
    chunk = Chunk(
        id=chunk_id,
        parent_doc_id="doc1",
        source="mitre",
        content=f"content for {chunk_id}",
        chunk_index=0,
        retrieved_at=datetime(2024, 1, 1),
        embedding_model="test-model",
    )
    return RetrievalResult(document=chunk, score=score, rank=0, retriever_source="rrf")


class _FakeRetriever:
    def __init__(self, results: list[RetrievalResult] | None = None) -> None:
        self.last_query: str = ""
        self.last_top_k: int = 0
        self.last_source_filter = None
        self._results = results or []

    def search(
        self, query: str, top_k: int = 10, source_filter=None, constraint=None
    ) -> list[RetrievalResult]:
        self.last_query = query
        self.last_top_k = top_k
        self.last_source_filter = source_filter
        self.last_constraint = constraint
        return self._results


class _FakeReranker:
    def __init__(self) -> None:
        self.called_with: tuple[str, list] | None = None

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        self.called_with = (query, results)
        return results


class _FakeSettings:
    def __init__(self, retrieval_top_k: int = 10) -> None:
        self.retrieval_top_k = retrieval_top_k
        self.hyde_enabled = False


# ---------------------------------------------------------------------------
# Tests — Pipeline.run
# ---------------------------------------------------------------------------


def test_run_returns_query_result() -> None:
    pipeline = Pipeline(
        retriever=_FakeRetriever([_make_result("a")]),
        reranker=_FakeReranker(),
        settings=_FakeSettings(),
    )
    result = pipeline.run("ransomware initial access via email")
    assert isinstance(result, QueryResult)


def test_run_query_preserved_in_result() -> None:
    pipeline = Pipeline(
        retriever=_FakeRetriever(),
        reranker=_FakeReranker(),
        settings=_FakeSettings(),
    )
    result = pipeline.run("credential dumping T1003")
    assert result.query == "credential dumping T1003"


def test_run_uses_settings_top_k_by_default() -> None:
    retriever = _FakeRetriever()
    pipeline = Pipeline(
        retriever=retriever,
        reranker=_FakeReranker(),
        settings=_FakeSettings(retrieval_top_k=7),
    )
    pipeline.run("some query")
    assert retriever.last_top_k == 7


def test_run_top_k_arg_overrides_settings() -> None:
    retriever = _FakeRetriever()
    pipeline = Pipeline(
        retriever=retriever,
        reranker=_FakeReranker(),
        settings=_FakeSettings(retrieval_top_k=10),
    )
    pipeline.run("some query", top_k=3)
    assert retriever.last_top_k == 3


def test_run_passes_source_filter() -> None:
    retriever = _FakeRetriever()
    pipeline = Pipeline(
        retriever=retriever,
        reranker=_FakeReranker(),
        settings=_FakeSettings(),
    )
    pipeline.run("some query", source_filter="mitre")
    assert retriever.last_source_filter == "mitre"


def test_run_calls_reranker_with_query_and_results() -> None:
    results = [_make_result("a"), _make_result("b")]
    reranker = _FakeReranker()
    pipeline = Pipeline(
        retriever=_FakeRetriever(results),
        reranker=reranker,
        settings=_FakeSettings(),
    )
    pipeline.run("T1566 spearphishing query here")
    assert reranker.called_with is not None
    assert reranker.called_with[0] == "T1566 spearphishing query here"


def test_run_truncates_to_top_k() -> None:
    many = [_make_result(f"c{i}", 1.0 - i * 0.05) for i in range(20)]
    pipeline = Pipeline(
        retriever=_FakeRetriever(many),
        reranker=_FakeReranker(),
        settings=_FakeSettings(retrieval_top_k=5),
    )
    result = pipeline.run("query")
    assert len(result.results) <= 5


def test_run_total_retrieved_matches_results_length() -> None:
    results = [_make_result("a"), _make_result("b"), _make_result("c")]
    pipeline = Pipeline(
        retriever=_FakeRetriever(results),
        reranker=_FakeReranker(),
        settings=_FakeSettings(),
    )
    result = pipeline.run("query")
    assert result.total_retrieved == len(result.results)


def test_run_retrieval_ms_is_non_negative() -> None:
    pipeline = Pipeline(
        retriever=_FakeRetriever(),
        reranker=_FakeReranker(),
        settings=_FakeSettings(),
    )
    result = pipeline.run("query")
    assert result.retrieval_ms >= 0.0


def test_run_empty_results_returns_empty_query_result() -> None:
    pipeline = Pipeline(
        retriever=_FakeRetriever([]),
        reranker=_FakeReranker(),
        settings=_FakeSettings(),
    )
    result = pipeline.run("no match query")
    assert result.results == []
    assert result.total_retrieved == 0


# ---------------------------------------------------------------------------
# Tests — build_pipeline
# ---------------------------------------------------------------------------


class _FakeStore:
    pass


class _FakeEmbedder:
    pass


class _FakeEncoder:
    pass


class _FakeLLMClient:
    pass


def test_build_pipeline_returns_pipeline_instance() -> None:
    pipeline = build_pipeline(
        settings=_FakeSettings(),
        store=_FakeStore(),
        embedder=_FakeEmbedder(),
        encoder=_FakeEncoder(),
    )
    assert isinstance(pipeline, Pipeline)


def test_build_pipeline_without_llm_client() -> None:
    pipeline = build_pipeline(
        settings=_FakeSettings(),
        store=_FakeStore(),
        embedder=_FakeEmbedder(),
        encoder=_FakeEncoder(),
        llm_client=None,
    )
    assert isinstance(pipeline, Pipeline)


def test_build_pipeline_with_llm_client_when_hyde_disabled() -> None:
    settings = _FakeSettings()
    settings.hyde_enabled = False
    pipeline = build_pipeline(
        settings=settings,
        store=_FakeStore(),
        embedder=_FakeEmbedder(),
        encoder=_FakeEncoder(),
        llm_client=_FakeLLMClient(),
    )
    assert isinstance(pipeline, Pipeline)


# ---------------------------------------------------------------------------
# Tests — tracing integration
# ---------------------------------------------------------------------------


def test_run_calls_add_trace_metadata_with_chunk_ids_and_scores() -> None:
    results = [_make_result("chunk-a", 0.9), _make_result("chunk-b", 0.7)]
    pipeline = Pipeline(
        retriever=_FakeRetriever(results),
        reranker=_FakeReranker(),
        settings=_FakeSettings(),
    )
    with patch("rag_cti.retrieval.pipeline.add_trace_metadata") as mock_meta:
        pipeline.run("test tracing query here")
    mock_meta.assert_called_once()
    kwargs = mock_meta.call_args.kwargs
    assert "chunk_ids" in kwargs
    assert "scores" in kwargs
    assert "elapsed_ms" in kwargs
    assert kwargs["chunk_ids"] == ["chunk-a", "chunk-b"]


def test_run_result_unchanged_when_tracing_metadata_added() -> None:
    results = [_make_result("x1", 0.8)]
    pipeline = Pipeline(
        retriever=_FakeRetriever(results),
        reranker=_FakeReranker(),
        settings=_FakeSettings(),
    )
    with patch("rag_cti.retrieval.pipeline.add_trace_metadata"):
        result = pipeline.run("query for tracing test")
    assert result.query == "query for tracing test"
    assert len(result.results) == 1
    assert result.results[0].document.id == "x1"


# ---------------------------------------------------------------------------
# Tests — reranker integration (Step 4, tests 7-9)
# ---------------------------------------------------------------------------


class _FakeSettingsWithReranker:
    def __init__(
        self,
        retrieval_top_k: int = 10,
        reranker_enabled: bool = False,
        reranker_model: str = "BAAI/bge-reranker-v2-m3",
        reranker_candidates_k: int = 50,
    ) -> None:
        self.retrieval_top_k = retrieval_top_k
        self.hyde_enabled = False
        self.reranker_enabled = reranker_enabled
        self.reranker_model = reranker_model
        self.reranker_candidates_k = reranker_candidates_k


def test_build_pipeline_reranker_enabled_uses_cross_encoder() -> None:
    settings = _FakeSettingsWithReranker(reranker_enabled=True)
    with patch("rag_cti.retrieval.reranker.CrossEncoderReranker") as mock_cls:
        mock_cls.return_value = _FakeReranker()
        pipeline = build_pipeline(
            settings=settings,
            store=_FakeStore(),
            embedder=_FakeEmbedder(),
            encoder=_FakeEncoder(),
        )
    mock_cls.assert_called_once_with(
        model_name="BAAI/bge-reranker-v2-m3", max_length=512, serialize_predict=False
    )
    assert isinstance(pipeline, Pipeline)


def test_build_pipeline_reranker_disabled_uses_noop() -> None:
    from rag_cti.retrieval.reranker import NoOpReranker

    settings = _FakeSettingsWithReranker(reranker_enabled=False)
    pipeline = build_pipeline(
        settings=settings,
        store=_FakeStore(),
        embedder=_FakeEmbedder(),
        encoder=_FakeEncoder(),
    )
    assert isinstance(pipeline._reranker, NoOpReranker)


def test_build_pipeline_no_reranker_field_uses_noop() -> None:
    from rag_cti.retrieval.reranker import NoOpReranker

    pipeline = build_pipeline(
        settings=_FakeSettings(),
        store=_FakeStore(),
        embedder=_FakeEmbedder(),
        encoder=_FakeEncoder(),
    )
    assert isinstance(pipeline._reranker, NoOpReranker)


def test_over_fetch_when_reranker_enabled() -> None:
    retriever = _FakeRetriever()
    settings = _FakeSettingsWithReranker(
        retrieval_top_k=10,
        reranker_enabled=True,
        reranker_candidates_k=50,
    )
    pipeline = Pipeline(
        retriever=retriever,
        reranker=_FakeReranker(),
        settings=settings,
    )
    pipeline.run("APT29 lateral movement techniques")
    assert retriever.last_top_k == 50


def test_no_over_fetch_when_reranker_disabled() -> None:
    retriever = _FakeRetriever()
    settings = _FakeSettingsWithReranker(
        retrieval_top_k=10,
        reranker_enabled=False,
        reranker_candidates_k=50,
    )
    pipeline = Pipeline(
        retriever=retriever,
        reranker=_FakeReranker(),
        settings=settings,
    )
    pipeline.run("credential access via Mimikatz")
    assert retriever.last_top_k == 10


# ---------------------------------------------------------------------------
# Tests — hybrid_alpha_override (OVERNIGHT_TASK bugfix)
# ---------------------------------------------------------------------------


def test_build_pipeline_alpha_1_uses_dense_retriever() -> None:
    from rag_cti.retrieval.dense_retriever import DenseRetriever

    pipeline = build_pipeline(
        settings=_FakeSettings(),
        store=_FakeStore(),
        embedder=_FakeEmbedder(),
        encoder=_FakeEncoder(),
        hybrid_alpha_override=1.0,
    )
    assert isinstance(pipeline._retriever, DenseRetriever)


def test_build_pipeline_alpha_05_uses_hybrid_retriever() -> None:
    from rag_cti.retrieval.hybrid_retriever import HybridRetriever

    pipeline = build_pipeline(
        settings=_FakeSettings(),
        store=_FakeStore(),
        embedder=_FakeEmbedder(),
        encoder=_FakeEncoder(),
        hybrid_alpha_override=0.5,
    )
    assert isinstance(pipeline._retriever, HybridRetriever)


def test_build_pipeline_alpha_none_uses_settings_default() -> None:
    from rag_cti.retrieval.hybrid_retriever import HybridRetriever

    settings = _FakeSettings()
    settings.hybrid_alpha = 0.5
    pipeline = build_pipeline(
        settings=settings,
        store=_FakeStore(),
        embedder=_FakeEmbedder(),
        encoder=_FakeEncoder(),
        hybrid_alpha_override=None,
    )
    assert isinstance(pipeline._retriever, HybridRetriever)


def test_trace_metadata_includes_reranker_and_fetch_k() -> None:
    retriever = _FakeRetriever([_make_result("mitre_T1566_c0")])
    settings = _FakeSettingsWithReranker(reranker_enabled=True, reranker_candidates_k=50)
    pipeline = Pipeline(
        retriever=retriever,
        reranker=_FakeReranker(),
        settings=settings,
    )
    with patch("rag_cti.retrieval.pipeline.add_trace_metadata") as mock_meta:
        pipeline.run("supply chain compromise techniques")
    kwargs = mock_meta.call_args.kwargs
    assert kwargs["reranker"] == "_FakeReranker"
    assert kwargs["fetch_k"] == 50


def test_pipeline_ontology_expands_constraint_before_retrieval() -> None:
    """With ontology_edges, a sub-technique constraint reaches the retriever widened
    to include its parent (retrieval §6 done-when: sub-technique query hits parent)."""
    retriever = _FakeRetriever([])
    pipeline = Pipeline(
        retriever=retriever,
        reranker=_FakeReranker(),
        settings=_FakeSettings(),
        ontology_edges=_SUBTECH_EDGES,
    )
    pipeline.run("creds", constraint=PayloadConstraint(attack_ids=("T1003.001",)))
    assert retriever.last_constraint.attack_ids == ("T1003", "T1003.001")


def test_pipeline_without_edges_does_not_expand() -> None:
    retriever = _FakeRetriever([])
    pipeline = Pipeline(retriever=retriever, reranker=_FakeReranker(), settings=_FakeSettings())
    pipeline.run("creds", constraint=PayloadConstraint(attack_ids=("T1003.001",)))
    assert retriever.last_constraint.attack_ids == ("T1003.001",)


# ---------------------------------------------------------------------------
# Tests — constraint routing (soft boost) seam-2 (after rerank)
# ---------------------------------------------------------------------------

_ROUTING_NODES = [
    {
        "ontology_id": "G0016",
        "type": "group",
        "name": "APT29",
        "aliases": ["Cozy Bear"],
        "tactics": [],
        "attack_version": "18.1",
    },
]


class _RoutingSettings:
    """Minimal settings exposing the routing flags (no reranker over-fetch)."""

    def __init__(self, enabled: bool = True, weight: float = 1.0, multiplier: int = 1) -> None:
        self.retrieval_top_k = 10
        self.hyde_enabled = False
        self.constraint_routing_enabled = enabled
        self.constraint_boost_weight = weight
        self.constraint_boost_fetch_multiplier = multiplier


class _FixedScoreReranker:
    """Reranker that assigns a fixed score per chunk id then sorts — models the
    cross-encoder fully overwriting upstream scores, independent of input order."""

    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        rescored = [r.model_copy(update={"score": self._scores[r.document.id]}) for r in results]
        rescored.sort(key=lambda r: r.score, reverse=True)
        return [r.model_copy(update={"rank": i}) for i, r in enumerate(rescored)]


def _entity_result(cid: str, *entity_ids: str) -> RetrievalResult:
    chunk = Chunk(
        id=cid,
        parent_doc_id="d",
        source="mitre",
        content="c",
        chunk_index=0,
        metadata={"entity_ids": list(entity_ids)},
    )
    return RetrievalResult(document=chunk, score=0.0, rank=0, retriever_source="rrf")


def _routing_pipeline(reranker, settings, base_results):
    """A real QueryRewriteRetriever (so understand() runs) over a fake base."""
    from rag_cti.retrieval.constraint_extract import ExtractedEntity, RewriteOutput
    from rag_cti.retrieval.query_rewrite import QueryRewriteRetriever

    class _Base:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def search(self, query, top_k=10, **_):
            self.calls.append(query)
            return list(base_results)

    class _Rewriter:
        def __init__(self) -> None:
            self.calls = 0

        def rewrite_with_entities(self, query, history=None):
            self.calls += 1
            return RewriteOutput(queries=("q",), entities=(ExtractedEntity("APT29", "actor"),))

    base, rewriter = _Base(), _Rewriter()
    retriever = QueryRewriteRetriever(
        base, rewriter, settings=settings, ontology_nodes=_ROUTING_NODES
    )
    pipeline = Pipeline(
        retriever=retriever, reranker=reranker, settings=settings, ontology_nodes=_ROUTING_NODES
    )
    return pipeline, base, rewriter


def test_boost_after_rerank_beats_score_erasure() -> None:
    # rerank puts nonmatch on top; the post-rerank boost must flip the entity match up.
    results = [_entity_result("nonmatch"), _entity_result("match", "actor_G0016")]
    reranker = _FixedScoreReranker({"nonmatch": 1.0, "match": 0.5})
    pipeline, _, _ = _routing_pipeline(reranker, _RoutingSettings(weight=1.0), results)
    out = pipeline.run("apt29 stuff")
    assert [r.document.id for r in out.results][0] == "match"  # 0.5 + 1.0 > 1.0


def test_routing_disabled_preserves_reranker_order() -> None:
    results = [_entity_result("nonmatch"), _entity_result("match", "actor_G0016")]
    reranker = _FixedScoreReranker({"nonmatch": 1.0, "match": 0.5})
    pipeline, _, _ = _routing_pipeline(reranker, _RoutingSettings(enabled=False), results)
    out = pipeline.run("apt29 stuff")
    assert [r.document.id for r in out.results][0] == "nonmatch"  # no boost


def test_exactly_one_understanding_call_per_run() -> None:
    results = [_entity_result("a", "actor_G0016")]
    pipeline, base, rewriter = _routing_pipeline(
        _FixedScoreReranker({"a": 1.0}), _RoutingSettings(), results
    )
    pipeline.run("apt29 stuff")
    assert rewriter.calls == 1  # LLM understanding fires once
    assert base.calls == ["q"]  # base searched the rewritten sub-query, not re-rewritten


def test_cross_path_consistency_direct_vs_pipeline_noop() -> None:
    """Same constraint + corpus through retriever.search and pipeline.run(NoOpReranker)
    must yield identical ordering — the historical 'eval can't see the gain' fix."""
    from rag_cti.retrieval.reranker import NoOpReranker

    def fresh_results():
        return [
            RetrievalResult(
                document=Chunk(
                    id="nonmatch",
                    parent_doc_id="d",
                    source="mitre",
                    content="c",
                    chunk_index=0,
                    metadata={},
                ),
                score=0.9,
                rank=0,
                retriever_source="rrf",
            ),
            RetrievalResult(
                document=Chunk(
                    id="match",
                    parent_doc_id="d",
                    source="mitre",
                    content="c",
                    chunk_index=0,
                    metadata={"entity_ids": ["actor_G0016"]},
                ),
                score=0.5,
                rank=1,
                retriever_source="rrf",
            ),
        ]

    settings = _RoutingSettings(weight=1.0)
    # Direct path: retriever.search self-rewrites + seam-1 boosts.
    pipeline_d, _, _ = _routing_pipeline(NoOpReranker(), settings, fresh_results())
    direct = pipeline_d._retriever.search("apt29", top_k=10)
    # Pipeline path: understand once, NoOp rerank, seam-2 boost.
    pipeline_p, _, _ = _routing_pipeline(NoOpReranker(), settings, fresh_results())
    piped = pipeline_p.run("apt29", top_k=10).results
    assert (
        [r.document.id for r in direct] == [r.document.id for r in piped] == ["match", "nonmatch"]
    )
