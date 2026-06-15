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
    mock_cls.assert_called_once_with(model_name="BAAI/bge-reranker-v2-m3", max_length=512)
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
