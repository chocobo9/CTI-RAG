from __future__ import annotations

import time

from rag_cti._logging import get_logger
from rag_cti.observability.tracing import add_trace_metadata, traced
from rag_cti.retrieval.dense_retriever import DenseRetriever
from rag_cti.retrieval.hybrid_retriever import HybridRetriever
from rag_cti.retrieval.hyde import HyDERetriever
from rag_cti.retrieval.reranker import NoOpReranker
from rag_cti.retrieval.sparse_retriever import SparseRetriever
from rag_cti.types import QueryResult, RetrievalResult

logger = get_logger(__name__)


class Pipeline:
    """End-to-end retrieval pipeline: retrieve → rerank → truncate."""

    def __init__(self, retriever: object, reranker: object, settings: object) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._settings = settings

    @traced("retrieval.pipeline", run_type="retriever")
    def run(
        self,
        query: str,
        top_k: int | None = None,
        source_filter: str | list[str] | None = None,
    ) -> QueryResult:
        t0 = time.perf_counter()
        k = top_k if top_k is not None else self._settings.retrieval_top_k
        results: list[RetrievalResult] = self._retriever.search(
            query, top_k=k, source_filter=source_filter
        )
        results = self._reranker.rerank(query, results)
        results = results[:k]
        elapsed_ms = (time.perf_counter() - t0) * 1000
        add_trace_metadata(
            top_k=k,
            returned=len(results),
            elapsed_ms=round(elapsed_ms, 1),
            chunk_ids=[r.document.id for r in results],
            scores=[round(r.score, 4) for r in results],
        )
        logger.debug(
            "pipeline run complete",
            query_len=len(query),
            top_k=k,
            returned=len(results),
            elapsed_ms=round(elapsed_ms, 1),
        )
        return QueryResult(
            query=query,
            results=results,
            total_retrieved=len(results),
            retrieval_ms=round(elapsed_ms, 1),
        )


def build_pipeline(
    settings: object,
    store: object,
    embedder: object,
    encoder: object,
    llm_client: object | None = None,
    llm_provider: str = "anthropic",
) -> Pipeline:
    """Wire the full retrieval stack from components."""
    dense = DenseRetriever(store=store, embedder=embedder)
    sparse = SparseRetriever(store=store, encoder=encoder)
    hybrid = HybridRetriever(dense=dense, sparse=sparse, settings=settings)
    if settings.hyde_enabled and llm_client is not None:
        retriever: object = HyDERetriever(
            base_retriever=hybrid,
            llm_client=llm_client,
            settings=settings,
            llm_provider=llm_provider,
        )
    else:
        retriever = hybrid
    return Pipeline(retriever=retriever, reranker=NoOpReranker(), settings=settings)
