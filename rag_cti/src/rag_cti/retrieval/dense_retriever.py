from __future__ import annotations

import time
from typing import Protocol

import numpy as np

from rag_cti._logging import get_logger
from rag_cti.types import PayloadConstraint, RetrievalResult

logger = get_logger(__name__)


class DenseSearchStore(Protocol):
    """Vector store surface DenseRetriever needs (QdrantStore.search)."""

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
        constraint: PayloadConstraint | None = None,
    ) -> list[RetrievalResult]: ...


class QueryEmbedder(Protocol):
    """Embedder surface DenseRetriever needs (Embedder.encode_one)."""

    def encode_one(self, text: str) -> np.ndarray: ...


class DenseRetriever:
    """Dense cosine-similarity retriever backed by Qdrant."""

    def __init__(self, store: DenseSearchStore, embedder: QueryEmbedder) -> None:
        self._store = store
        self._embedder = embedder

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
        sparse_query: str | None = None,
        constraint: PayloadConstraint | None = None,
    ) -> list[RetrievalResult]:
        """Embed *query* and return top-k dense results from Qdrant.

        ``sparse_query`` is accepted and ignored — there is no BM25 path here.
        HyDE always passes it (the hypothetical document must not replace the
        original query on the sparse side), so pure-dense configs
        (hybrid_alpha >= 1.0) with HyDE enabled would otherwise TypeError.
        """
        t0 = time.perf_counter()
        query_vector: np.ndarray = self._embedder.encode_one(query)
        results: list[RetrievalResult] = self._store.search(
            query_vector=query_vector,
            top_k=top_k,
            source_filter=source_filter,
            constraint=constraint,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            "dense search complete",
            top_k=top_k,
            returned=len(results),
            elapsed_ms=round(elapsed_ms, 1),
        )
        return results
