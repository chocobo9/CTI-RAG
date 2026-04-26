"""RAG-powered Cyber Threat Intelligence retrieval system.

Public interface:
    query(text, k) -> QueryResult   retrieve relevant CTI chunks with scores and metadata
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from rag_cti.config import get_settings
from rag_cti.retrieval import Pipeline, build_pipeline
from rag_cti.types import QueryResult

__all__ = ["query", "QueryResult", "Pipeline", "build_pipeline"]

__version__ = "0.1.0"

_VOCAB_PATH = Path(__file__).parent.parent.parent / "data" / "sparse_vocab.json"


@lru_cache(maxsize=1)
def _default_pipeline() -> Pipeline:
    from rag_cti.embeddings.embedder import Embedder
    from rag_cti.retrieval.bm25 import BM25SparseEncoder
    from rag_cti.store.qdrant_store import QdrantStore

    settings = get_settings()
    store = QdrantStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )
    embedder = Embedder(model_name=settings.embedding_model)
    encoder = (
        BM25SparseEncoder.load(_VOCAB_PATH)
        if _VOCAB_PATH.exists()
        else BM25SparseEncoder()
    )

    llm_client = None
    llm_provider = "anthropic"
    if settings.hyde_enabled:
        groq_key = settings.groq_api_key.get_secret_value()
        anthropic_key = settings.anthropic_api_key.get_secret_value()
        if groq_key:
            from groq import Groq  # type: ignore[import]

            llm_client = Groq(api_key=groq_key)
            llm_provider = "groq"
        elif anthropic_key:
            import anthropic  # type: ignore[import]

            llm_client = anthropic.Anthropic(api_key=anthropic_key)

    return build_pipeline(
        settings=settings,
        store=store,
        embedder=embedder,
        encoder=encoder,
        llm_client=llm_client,
        llm_provider=llm_provider,
    )


def query(text: str, k: int = 10) -> QueryResult:
    """Retrieve the top-k most relevant CTI chunks for the given query text.

    Args:
        text: Natural language query or IOC string.
        k: Number of results to return.

    Returns:
        QueryResult with ranked chunks, scores, ranks, and timing metadata.
    """
    return _default_pipeline().run(text, top_k=k)
