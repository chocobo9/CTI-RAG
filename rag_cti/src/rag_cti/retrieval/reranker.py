from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from rag_cti._logging import get_logger
from rag_cti.types import RetrievalResult

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder
    from sentence_transformers.base.modality_types import PairInput

logger = get_logger(__name__)

# Process-global lock to SERIALIZE cross-encoder forward passes when several retrieve tool
# calls dispatch concurrently (B2 parallel dispatch): one 8GB GPU cannot run parallel predicts
# without risking CUDA OOM, and they would serialize on the compute stream anyway — so guard the
# forward pass while the I/O-bound Groq/Qdrant/Neo4j stages of the concurrent retrieves overlap.
# Only used when a reranker is built with serialize_predict=True.
_PREDICT_LOCK = threading.Lock()


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]: ...


class NoOpReranker:
    """Pass-through reranker — preserves input order unchanged."""

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        return results


class CrossEncoderReranker:
    """Cross-encoder reranker using sentence-transformers CrossEncoder."""

    def __init__(
        self,
        model_name: str,
        device: str | None = None,
        max_length: int = 512,
        *,
        serialize_predict: bool = False,
    ) -> None:
        self._model_name = model_name
        self._device = device or self._detect_device()
        self._max_length = max_length
        self._model: CrossEncoder | None = None
        self._lock = threading.Lock()
        # Serialize forward passes across threads (B2): the GPU is the binding constraint under
        # concurrent retrieve dispatch. Off by default — single-threaded retrieval pays nothing.
        self._serialize_predict = serialize_predict

    @staticmethod
    def _detect_device() -> str:
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _load(self) -> CrossEncoder:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    import torch
                    from sentence_transformers import CrossEncoder

                    logger.info(
                        "loading cross-encoder model",
                        model=self._model_name,
                        device=self._device,
                        max_length=self._max_length,
                    )
                    self._model = CrossEncoder(
                        self._model_name,
                        device=self._device,
                        max_length=self._max_length,
                        model_kwargs={"torch_dtype": torch.float16},
                    )
        return self._model

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        import time

        if not results:
            return results

        t0 = time.perf_counter()
        model = self._load()
        t_load = time.perf_counter()
        pairs = cast("list[PairInput]", [[query, r.document.content] for r in results])
        if self._serialize_predict:
            with _PREDICT_LOCK:  # one forward pass at a time on the shared GPU (B2)
                scores = model.predict(pairs, show_progress_bar=False, batch_size=8)
        else:
            scores = model.predict(pairs, show_progress_bar=False, batch_size=8)
        t_predict = time.perf_counter()

        reranked = sorted(
            zip(results, scores, strict=True),
            key=lambda x: float(x[1]),
            reverse=True,
        )
        logger.info(
            "rerank complete",
            candidates=len(results),
            load_ms=round((t_load - t0) * 1000, 1),
            predict_ms=round((t_predict - t_load) * 1000, 1),
            total_ms=round((t_predict - t0) * 1000, 1),
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
