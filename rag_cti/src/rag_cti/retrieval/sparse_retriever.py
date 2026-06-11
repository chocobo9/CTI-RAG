from __future__ import annotations

import time
from typing import Protocol

from rag_cti._logging import get_logger
from rag_cti.types import RetrievalResult

logger = get_logger(__name__)


class SparseSearchStore(Protocol):
    """Vector store surface SparseRetriever needs (QdrantStore.sparse_search)."""

    def sparse_search(
        self,
        query_indices: list[int],
        query_values: list[float],
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
    ) -> list[RetrievalResult]: ...


class SparseQueryEncoder(Protocol):
    """Encoder surface SparseRetriever needs (BM25SparseEncoder.encode_query)."""

    def encode_query(self, text: str) -> tuple[list[int], list[float]]: ...


class SparseRetriever:
    """BM25 sparse retriever backed by Qdrant sparse vector index."""

    def __init__(self, store: SparseSearchStore, encoder: SparseQueryEncoder) -> None:
        self._store = store
        self._encoder = encoder

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Encode *query* with BM25 and return top-k sparse results from Qdrant.

        Returns empty list immediately when the query contains no in-vocabulary
        terms (avoids sending an empty sparse vector to Qdrant).
        """
        t0 = time.perf_counter()
        indices, values = self._encoder.encode_query(query)
        if not indices:
            logger.debug("sparse search skipped — all query terms OOV", query=query)
            return []

        results: list[RetrievalResult] = self._store.sparse_search(
            query_indices=indices,
            query_values=values,
            top_k=top_k,
            source_filter=source_filter,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            "sparse search complete",
            top_k=top_k,
            returned=len(results),
            query_terms=len(indices),
            elapsed_ms=round(elapsed_ms, 1),
        )
        return results
