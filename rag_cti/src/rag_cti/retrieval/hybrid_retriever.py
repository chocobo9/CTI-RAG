from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from rag_cti._logging import get_logger
from rag_cti.retrieval.fusion import reciprocal_rank_fusion
from rag_cti.types import RetrievalResult, RetrieverProto

logger = get_logger(__name__)


class HybridRetriever:
    """Runs dense and sparse retrieval in parallel and fuses results with weighted RRF.

    ``alpha`` is the dense weight in the fusion (sparse gets ``1 - alpha``).
    ``None`` falls back to ``settings.hybrid_alpha``.
    """

    def __init__(
        self,
        dense: RetrieverProto,
        sparse: RetrieverProto,
        settings: object,
        alpha: float | None = None,
    ) -> None:
        self._dense = dense
        self._sparse = sparse
        self._settings = settings
        self._alpha = alpha if alpha is not None else getattr(settings, "hybrid_alpha", 0.5)

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
        sparse_query: str | None = None,
    ) -> list[RetrievalResult]:
        t0 = time.perf_counter()
        bm25_query = sparse_query if sparse_query is not None else query
        multiplier = getattr(self._settings, "rrf_candidate_multiplier", 1)
        fetch_k = top_k * max(multiplier, 1)

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_dense = executor.submit(
                self._dense.search, query, top_k=fetch_k, source_filter=source_filter
            )
            f_sparse = executor.submit(
                self._sparse.search, bm25_query, top_k=fetch_k, source_filter=source_filter
            )
            dense_results = f_dense.result()
            sparse_results = f_sparse.result()

        fused = reciprocal_rank_fusion(
            [dense_results, sparse_results],
            weights=[self._alpha, 1.0 - self._alpha],
        )
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
