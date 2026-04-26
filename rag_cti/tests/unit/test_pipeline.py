from __future__ import annotations

from datetime import datetime

from rag_cti.retrieval.pipeline import Pipeline, build_pipeline
from rag_cti.types import Chunk, QueryResult, RetrievalResult


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

    def search(self, query: str, top_k: int = 10, source_filter=None) -> list[RetrievalResult]:
        self.last_query = query
        self.last_top_k = top_k
        self.last_source_filter = source_filter
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
