"""Sentence-transformer embedder wrapper.

Stateless wrapper around sentence-transformers. One instance per process —
the underlying model is expensive to load but thread-safe for read-only
inference once loaded.
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from rag_cti._logging import get_logger

logger = get_logger(__name__)

_DEFAULT_BATCH_SIZE = 64

# sentence-transformers resolves bare names under sentence-transformers/*, which breaks
# for bge-m3 (real checkpoint is BAAI/bge-m3). Accept legacy .env values.
_HF_MODEL_ALIASES: dict[str, str] = {
    "bge-m3": "BAAI/bge-m3",
}


def _resolve_model_name(model_name: str) -> str:
    key = model_name.strip()
    if key in _HF_MODEL_ALIASES:
        resolved = _HF_MODEL_ALIASES[key]
        logger.info("embedding model id normalized", raw=model_name, resolved=resolved)
        return resolved
    return key


class Embedder:
    """Embeds text into dense vectors using a sentence-transformers model."""

    def __init__(
        self,
        model_name: str,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        device: str | None = None,
        normalize: bool = True,
    ) -> None:
        self.model_name = _resolve_model_name(model_name)
        self.batch_size = batch_size
        self.normalize = normalize
        self._device = device
        self._model: Any | None = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    logger.info(
                        "loading embedding model", model=self.model_name, device=self._device
                    )
                    self._model = SentenceTransformer(self.model_name, device=self._device)
        return self._model

    @property
    def dimension(self) -> int:
        """Output vector dimension for this model."""
        model = self._load()
        dim = model.get_sentence_embedding_dimension()
        if not isinstance(dim, int):
            raise RuntimeError(f"model {self.model_name} returned non-int dimension: {dim!r}")
        return dim

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode a list of strings into an (n, dim) float32 array.

        Normalizes to unit length when self.normalize is True so downstream
        cosine search can use a dot-product index.
        """
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        model = self._load()
        vectors = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    def encode_one(self, text: str) -> np.ndarray:
        """Encode a single string, returning a (dim,) vector."""
        vector: np.ndarray = self.encode([text])[0]
        return vector
