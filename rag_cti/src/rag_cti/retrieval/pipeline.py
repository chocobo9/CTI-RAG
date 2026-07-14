from __future__ import annotations

import time
from typing import Any, Protocol

from rag_cti._logging import get_logger
from rag_cti.observability.tracing import add_trace_metadata, traced
from rag_cti.retrieval.constraint_boost import apply_constraint_boost
from rag_cti.retrieval.constraint_extract import build_constraint
from rag_cti.retrieval.dense_retriever import DenseRetriever, DenseSearchStore, QueryEmbedder
from rag_cti.retrieval.hybrid_retriever import HybridRetriever
from rag_cti.retrieval.hyde import HyDERetriever
from rag_cti.retrieval.ontology_expand import expand_constraint
from rag_cti.retrieval.query_rewrite import LLMQueryRewriter, QueryRewriteRetriever
from rag_cti.retrieval.reranker import NoOpReranker, Reranker
from rag_cti.retrieval.sparse_retriever import (
    SparseQueryEncoder,
    SparseRetriever,
    SparseSearchStore,
)
from rag_cti.types import (
    PayloadConstraint,
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
        self,
        retriever: RetrieverProto,
        reranker: Reranker,
        settings: SettingsProto,
        ontology_edges: list[dict[str, Any]] | None = None,
        ontology_nodes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._settings = settings
        # subtechnique-of edges for query-time ontology expansion (retrieval §6);
        # None disables it (a constraint then filters on the literal attack_ids).
        self._ontology_edges = ontology_edges
        # ontology nodes (name/alias -> id) for query-time entity resolution in the
        # boost constraint; None disables actor/family routing (deterministic still works).
        self._ontology_nodes = ontology_nodes

    def _routing_enabled(self) -> bool:
        return bool(getattr(self._settings, "constraint_routing_enabled", False))

    def _boost_weight(self) -> float:
        return float(getattr(self._settings, "constraint_boost_weight", 0.0))

    def _fetch_multiplier(self) -> int:
        return max(1, int(getattr(self._settings, "constraint_boost_fetch_multiplier", 1)))

    @traced("retrieval.pipeline", run_type="retriever")
    def run(
        self,
        query: str,
        top_k: int | None = None,
        source_filter: str | list[str] | None = None,
        constraint: PayloadConstraint | None = None,
        history: list[str] | None = None,
    ) -> QueryResult:
        t0 = time.perf_counter()
        k = top_k if top_k is not None else self._settings.retrieval_top_k

        fetch_k = k
        if getattr(self._settings, "reranker_enabled", False):
            fetch_k = max(k, getattr(self._settings, "reranker_candidates_k", k))
        # Widen the candidate pool when routing so a soft-boosted but lower-scored
        # match can still surface (matters only when reranker is off — fetch_k == k).
        if self._routing_enabled():
            fetch_k *= self._fetch_multiplier()

        # Ontology expansion (retrieval §6): a sub-technique HARD filter also matches its
        # parent (and a parent its sub-techniques) before vector search. (Boost constraints
        # are NOT expanded — that would dilute the signal.)
        if constraint is not None and self._ontology_edges:
            constraint = expand_constraint(constraint, self._ontology_edges)

        # Query understanding happens here exactly ONCE: a QueryRewriteRetriever yields
        # both the sub-queries and the boost constraint from a single LLM call, then
        # search() is told the sub-queries so it skips its own rewrite call. The boost
        # is re-applied after reranking (the cross-encoder overwrites scores), so it
        # survives rerank in production while the retriever's own seam-1 boost covers
        # the rerank-free direct-search path.
        boost_constraint: PayloadConstraint | None = None
        if isinstance(self._retriever, QueryRewriteRetriever):
            subqueries, boost_constraint = self._retriever.understand(query, history)
            results: list[RetrievalResult] = self._retriever.search(
                query,
                top_k=fetch_k,
                source_filter=source_filter,
                constraint=constraint,
                subqueries=subqueries,
                boost_constraint=boost_constraint,
            )
        else:
            if self._routing_enabled():
                boost_constraint = build_constraint(query, (), self._ontology_nodes)
            results = self._retriever.search(
                query, top_k=fetch_k, source_filter=source_filter, constraint=constraint
            )
        t_retrieve = time.perf_counter()
        results = self._reranker.rerank(query, results)
        # Seam 2: re-apply the soft boost on the reranked scores, before truncation.
        if (
            self._routing_enabled()
            and boost_constraint is not None
            and not boost_constraint.is_empty
        ):
            results = apply_constraint_boost(results, boost_constraint, self._boost_weight())
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
    llm_provider: str = "groq",
    hybrid_alpha_override: float | None = None,
    ontology_nodes: list[dict[str, Any]] | None = None,
    ontology_edges: list[dict[str, Any]] | None = None,
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

    # Outermost wrapper: rewrite the query (normalize/decompose/contextualize), fuse
    # sub-query results, and soft-boost on the structured constraint. Wraps HyDE so
    # HyDE sees clean sub-queries. ontology_nodes enable actor/family entity routing.
    if getattr(settings, "query_rewrite_enabled", False) and llm_client is not None:
        retriever = QueryRewriteRetriever(
            retriever,
            LLMQueryRewriter(llm_client, settings, llm_provider),
            settings=settings,
            ontology_nodes=ontology_nodes,
        )

    if getattr(settings, "reranker_enabled", False):
        from rag_cti.retrieval.reranker import CrossEncoderReranker

        reranker: Reranker = CrossEncoderReranker(
            model_name=settings.reranker_model,
            max_length=getattr(settings, "reranker_max_length", 512),
            serialize_predict=getattr(settings, "reranker_serialize_predict", False),
        )
    else:
        reranker = NoOpReranker()

    return Pipeline(
        retriever=retriever,
        reranker=reranker,
        settings=settings,
        ontology_edges=ontology_edges,
        ontology_nodes=ontology_nodes,
    )
