from __future__ import annotations

from typing import Protocol, runtime_checkable

from rag_cti._logging import get_logger
from rag_cti.types import RetrievalResult

logger = get_logger(__name__)


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]: ...


class NoOpReranker:
    """Pass-through reranker — preserves input order unchanged."""

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        return results


class CrossEncoderReranker:
    """Cross-encoder reranker using sentence-transformers CrossEncoder."""

    def __init__(self, model_name: str, device: str | None = None) -> None:
        self._model_name = model_name
        self._device = device
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("loading cross-encoder model", model=self._model_name)
            self._model = CrossEncoder(self._model_name, device=self._device)
        return self._model

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        if not results:
            return results

        model = self._load()
        pairs = [[query, r.document.content] for r in results]
        scores = model.predict(pairs, show_progress_bar=False)

        reranked = sorted(
            zip(results, scores),
            key=lambda x: float(x[1]),
            reverse=True,
        )
        return [
            RetrievalResult(
                document=r.document,
                score=float(s),
                rank=i,
                retriever_source=r.retriever_source,
            )
            for i, (r, s) in enumerate(reranked)
        ]
