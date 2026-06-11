from __future__ import annotations

import time
from typing import Protocol

from rag_cti._logging import get_logger
from rag_cti.observability.tracing import add_trace_metadata, traced
from rag_cti.retrieval.dense_retriever import DenseRetriever, DenseSearchStore, QueryEmbedder
from rag_cti.retrieval.hybrid_retriever import HybridRetriever
from rag_cti.retrieval.hyde import HyDERetriever
from rag_cti.retrieval.reranker import NoOpReranker, Reranker
from rag_cti.retrieval.sparse_retriever import (
    SparseQueryEncoder,
    SparseRetriever,
    SparseSearchStore,
)
from rag_cti.types import (
    QueryResult,
    RetrievalResult,
    RetrieverProto,
    SettingsProto,
)

logger = get_logger(__name__)


class RetrievalStore(DenseSearchStore, SparseSearchStore, Protocol):
    """Store offering both dense search and BM25 sparse search (QdrantStore)."""


class Pipeline:
    """End-to-end retrieval pipeline: retrieve → rerank → truncate."""

    def __init__(
        self, retriever: RetrieverProto, reranker: Reranker, settings: SettingsProto
    ) -> None:
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

        fetch_k = k
        if getattr(self._settings, "reranker_enabled", False):
            fetch_k = max(k, getattr(self._settings, "reranker_candidates_k", k))

        results: list[RetrievalResult] = self._retriever.search(
            query, top_k=fetch_k, source_filter=source_filter
        )
        t_retrieve = time.perf_counter()
        results = self._reranker.rerank(query, results)
        t_rerank = time.perf_counter()
        results = results[:k]
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "pipeline breakdown",
            retrieve_ms=round((t_retrieve - t0) * 1000, 1),
            rerank_ms=round((t_rerank - t_retrieve) * 1000, 1),
            total_ms=round(elapsed_ms, 1),
        )
        add_trace_metadata(
            top_k=k,
            returned=len(results),
            elapsed_ms=round(elapsed_ms, 1),
            chunk_ids=[r.document.id for r in results],
            scores=[round(r.score, 4) for r in results],
            reranker=type(self._reranker).__name__,
            fetch_k=fetch_k,
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
    settings: SettingsProto,
    store: RetrievalStore,
    embedder: QueryEmbedder,
    encoder: SparseQueryEncoder,
    llm_client: object | None = None,
    llm_provider: str = "anthropic",
    hybrid_alpha_override: float | None = None,
) -> Pipeline:
    """Wire the full retrieval stack from components.

    ``hybrid_alpha_override`` (or ``settings.hybrid_alpha``) is the dense weight
    in the weighted-RRF fusion; ``>= 1.0`` skips the sparse retriever entirely
    (pure dense).
    """
    dense = DenseRetriever(store=store, embedder=embedder)

    effective_alpha = (
        hybrid_alpha_override
        if hybrid_alpha_override is not None
        else getattr(settings, "hybrid_alpha", 0.5)
    )

    if effective_alpha >= 1.0:
        base_retriever: DenseRetriever | HybridRetriever = dense
    else:
        sparse = SparseRetriever(store=store, encoder=encoder)
        base_retriever = HybridRetriever(
            dense=dense, sparse=sparse, settings=settings, alpha=effective_alpha
        )

    if settings.hyde_enabled and llm_client is not None:
        retriever: RetrieverProto = HyDERetriever(
            base_retriever=base_retriever,
            llm_client=llm_client,
            settings=settings,
            llm_provider=llm_provider,
        )
    else:
        retriever = base_retriever
    if getattr(settings, "reranker_enabled", False):
        from rag_cti.retrieval.reranker import CrossEncoderReranker

        reranker: Reranker = CrossEncoderReranker(
            model_name=settings.reranker_model,
            max_length=getattr(settings, "reranker_max_length", 640),
        )
    else:
        reranker = NoOpReranker()

    return Pipeline(retriever=retriever, reranker=reranker, settings=settings)
