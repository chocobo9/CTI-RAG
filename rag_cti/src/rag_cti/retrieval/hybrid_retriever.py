from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from rag_cti._logging import get_logger
from rag_cti.retrieval.fusion import reciprocal_rank_fusion
from rag_cti.types import RetrievalResult

logger = get_logger(__name__)


class HybridRetriever:
    """Runs dense and sparse retrieval in parallel and fuses results with RRF."""

    def __init__(self, dense: object, sparse: object, settings: object) -> None:
        self._dense = dense
        self._sparse = sparse
        self._settings = settings

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
    ) -> list[RetrievalResult]:
        t0 = time.perf_counter()

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_dense = executor.submit(
                self._dense.search, query, top_k=top_k, source_filter=source_filter
            )
            f_sparse = executor.submit(
                self._sparse.search, query, top_k=top_k, source_filter=source_filter
            )
            dense_results = f_dense.result()
            sparse_results = f_sparse.result()

        fused = reciprocal_rank_fusion([dense_results, sparse_results])
        results = fused[:top_k]

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            "hybrid search complete",
            dense=len(dense_results),
            sparse=len(sparse_results),
            fused=len(results),
            elapsed_ms=round(elapsed_ms, 1),
        )
        return results
