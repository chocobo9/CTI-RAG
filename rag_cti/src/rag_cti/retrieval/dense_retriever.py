from __future__ import annotations

import time

import numpy as np

from rag_cti._logging import get_logger
from rag_cti.types import RetrievalResult

logger = get_logger(__name__)


class DenseRetriever:
    """Dense cosine-similarity retriever backed by Qdrant."""

    def __init__(self, store: object, embedder: object) -> None:
        self._store = store
        self._embedder = embedder

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Embed *query* and return top-k dense results from Qdrant."""
        t0 = time.perf_counter()
        query_vector: np.ndarray = self._embedder.encode_one(query)
        results: list[RetrievalResult] = self._store.search(
            query_vector=query_vector,
            top_k=top_k,
            source_filter=source_filter,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            "dense search complete",
            top_k=top_k,
            returned=len(results),
            elapsed_ms=round(elapsed_ms, 1),
        )
        return results
