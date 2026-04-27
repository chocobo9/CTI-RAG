"""RAG-powered Cyber Threat Intelligence retrieval system.

Public interface:
    query(text, k)  -> QueryResult      retrieve relevant CTI chunks with scores and metadata
    answer(text, k) -> GeneratedAnswer  retrieve + generate a grounded answer with cited IDs
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from rag_cti.config import get_settings
from rag_cti.retrieval import Pipeline, build_pipeline
from rag_cti.types import GeneratedAnswer, QueryResult

__all__ = ["query", "answer", "QueryResult", "GeneratedAnswer", "Pipeline", "build_pipeline"]

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


@lru_cache(maxsize=1)
def _default_generator() -> object:
    from rag_cti.generation.client import RetryingGroqClient
    from rag_cti.generation.generator import Generator
    from rag_cti.generation.llm_router import LLMRouter

    settings = get_settings()
    api_key = settings.groq_api_key.get_secret_value()
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is required for answer generation. "
            "Set it in your .env file or environment."
        )
    client = RetryingGroqClient(api_key=api_key)
    router = LLMRouter(settings=settings)
    return Generator(client=client, router=router, settings=settings)


def answer(text: str, k: int = 10) -> GeneratedAnswer:
    """Retrieve relevant CTI chunks and generate a grounded answer with cited chunk IDs.

    Args:
        text: Natural language CTI query.
        k: Number of context chunks to retrieve before generation.

    Returns:
        GeneratedAnswer with the response text, cited chunk IDs, and the underlying QueryResult.
    """
    from rag_cti.generation.generator import Generator

    query_result = query(text, k=k)
    gen: Generator = _default_generator()  # type: ignore[assignment]
    return gen.generate(text, query_result)
