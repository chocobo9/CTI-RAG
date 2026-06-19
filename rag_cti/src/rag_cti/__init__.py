"""RAG-powered Cyber Threat Intelligence retrieval system.

Public interface:
    query(text, top_k) -> QueryResult      retrieve relevant CTI chunks with scores and metadata
    answer(text, k)    -> GeneratedAnswer  retrieve + generate a grounded answer with cited IDs
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from rag_cti.config import get_settings
from rag_cti.retrieval import Pipeline, build_pipeline
from rag_cti.types import FactQueryResult, GeneratedAnswer, QueryResult

if TYPE_CHECKING:
    from rag_cti.knowledge.agentic_state import AgenticAnswer

__all__ = [
    "query",
    "answer",
    "answer_single_shot",
    "agentic_answer",
    "facts",
    "ask",
    "QueryResult",
    "GeneratedAnswer",
    "FactQueryResult",
    "Pipeline",
    "build_pipeline",
]

__version__ = "0.1.0"


@lru_cache(maxsize=1)
def _default_pipeline() -> Pipeline:
    from rag_cti.bootstrap import load_ontology_nodes, load_sparse_encoder, vocab_path_for
    from rag_cti.embeddings.embedder import Embedder
    from rag_cti.store.qdrant_store import QdrantStore

    settings = get_settings()
    store = QdrantStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )
    embedder = Embedder(model_name=settings.embedding_model)
    embedder._load()  # eager load: avoid first-query penalty
    encoder = load_sparse_encoder(vocab_path_for(settings.qdrant_collection))

    llm_client = None
    llm_provider = "anthropic"
    if settings.hyde_enabled or settings.query_rewrite_enabled:
        from rag_cti.generation.client import build_llm_client

        llm_provider, llm_client = build_llm_client(settings)

    pipeline = build_pipeline(
        settings=settings,
        store=store,
        embedder=embedder,
        encoder=encoder,
        llm_client=llm_client,
        llm_provider=llm_provider,
        ontology_nodes=load_ontology_nodes(),
    )

    # eager load reranker model if enabled
    if settings.reranker_enabled and hasattr(pipeline._reranker, "_load"):
        pipeline._reranker._load()

    return pipeline


def query(text: str, top_k: int = 10, history: list[str] | None = None) -> QueryResult:
    """Retrieve the top-k most relevant CTI chunks for the given query text.

    Args:
        text: Natural language query or IOC string.
        top_k: Number of results to return.
        history: Prior user queries (most recent last) for multi-turn reference
            resolution; used only when query rewrite is enabled.

    Returns:
        QueryResult with ranked chunks, scores, ranks, and timing metadata.
    """
    return _default_pipeline().run(text, top_k=top_k, history=history)


@lru_cache(maxsize=1)
def _default_generator() -> object:
    # Generation is pinned to DeepSeek (provider not variable) with a model-downgrade
    # chain (settings.generation_models). HyDE/query-rewrite still run on Groq via the
    # retrieval pipeline — they are a separate, smaller tier.
    from rag_cti.bootstrap import FixedRouter, build_deepseek_client
    from rag_cti.generation.client import FallbackChatClient
    from rag_cti.generation.generator import Generator

    settings = get_settings()
    models = settings.generation_models
    client = FallbackChatClient(build_deepseek_client(settings), models)
    return Generator(client=client, router=FixedRouter(models[0]), settings=settings)


def answer(text: str, k: int = 10, history: list[str] | None = None) -> GeneratedAnswer:
    """Generate a grounded answer with cited chunk IDs.

    Routes by ``settings.agentic_enabled``: when ON, delegates to the agentic loop
    (:func:`agentic_answer`) and adapts its result to ``GeneratedAnswer`` (``k`` /
    ``history`` are ignored — the agent composes its own retrieval); when OFF
    (default until eval proves the agentic win), runs the single-shot path
    (:func:`answer_single_shot`).
    """
    if get_settings().agentic_enabled:
        agentic = agentic_answer(text)
        return GeneratedAnswer(
            query=agentic.query,
            answer=agentic.answer,
            cited_chunk_ids=list(agentic.cited_ids),
            query_result=agentic.query_result,
            generation_ms=0.0,
            model="agentic",
        )
    return answer_single_shot(text, k=k, history=history)


def answer_single_shot(text: str, k: int = 10, history: list[str] | None = None) -> GeneratedAnswer:
    """Single-shot retrieve -> generate (the pre-agentic behaviour).

    Args:
        text: Natural language CTI query.
        k: Number of context chunks to retrieve before generation.
        history: Prior user queries (most recent last) for multi-turn reference
            resolution; used only when query rewrite is enabled.

    Returns:
        GeneratedAnswer with the response text, cited chunk IDs, and the underlying QueryResult.
    """
    from rag_cti.generation.generator import Generator

    query_result = query(text, top_k=k, history=history)
    gen: Generator = _default_generator()  # type: ignore[assignment]
    return gen.generate(text, query_result)


def agentic_answer(text: str) -> AgenticAnswer:
    """Answer a CTI question via the agentic loop (workflow->agentic): adaptive
    retrieve -> assess sufficiency -> retrieve more -> synthesize. Reuses the
    single-shot retrieval pipeline as the agent's `retrieve` tool and the knowledge
    graph as graph tools; citations are validated against the gathered evidence and
    conflicts are surfaced. Graph tools degrade to no-ops when Neo4j is disabled
    (empty NEO4J_PASSWORD) so the loop still runs vector-only."""
    from typing import cast

    from rag_cti.bootstrap import build_deepseek_client, load_ontology_nodes
    from rag_cti.knowledge.agent_graph import build_model
    from rag_cti.knowledge.agentic_graph import build_judge, run_agentic_answer
    from rag_cti.knowledge.agentic_nodes import GeneratorProto
    from rag_cti.knowledge.fact_store import FactStoreProto

    settings = get_settings()
    pipeline = _default_pipeline()

    def run_retrieve(query_text: str, top_k: int) -> QueryResult:
        return pipeline.run(query_text, top_k=top_k)

    fact_store = (
        cast(FactStoreProto, _default_fact_store())
        if settings.neo4j_password.get_secret_value()
        else None
    )
    return run_agentic_answer(
        text,
        settings=settings,
        run_retrieve=run_retrieve,
        fact_store=fact_store,
        ontology_nodes=load_ontology_nodes(),
        generator=cast(GeneratorProto, _default_generator()),
        chat_model=build_model(settings),
        judge=build_judge(build_deepseek_client(settings), settings.agentic_verifier_model),
    )


@lru_cache(maxsize=1)
def _default_fact_store() -> object:
    from rag_cti.knowledge import Neo4jFactStore

    settings = get_settings()
    return Neo4jFactStore.connect(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password.get_secret_value(),
        settings.neo4j_database,
    )


@lru_cache(maxsize=1)
def _default_chunk_store() -> object:
    from rag_cti.store.qdrant_store import QdrantStore

    settings = get_settings()
    return QdrantStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )


def facts(
    subject_id: str,
    predicate: str | None = None,
    object_type: str | None = None,
    min_credibility: float = 0.0,
) -> FactQueryResult:
    """Enumerate facts for a (subject[, predicate, object_type]) from the knowledge
    graph (M4) — bypassing vector search for exact, exhaustive enumeration. Each
    fact carries its supports as citations (content filled from Qdrant), aggregate
    credibility, and a conflict flag; conflicting facts are surfaced, not resolved.
    """
    from typing import cast

    from rag_cti.knowledge.fact_query import run_fact_query
    from rag_cti.knowledge.fact_store import FactStoreProto
    from rag_cti.store.qdrant_store import QdrantStore

    fact_store = cast("FactStoreProto", _default_fact_store())
    chunk_store = cast("QdrantStore", _default_chunk_store())
    return run_fact_query(
        fact_store,
        chunk_store.get_by_chunk_ids,
        subject_id=subject_id,
        predicate=predicate,
        object_type=object_type,
        min_credibility=min_credibility,
    )


def ask(text: str, *, recursion_limit: int = 16) -> str:
    """Answer an NL question via the v1 agentic loop (M4 §9): an LLM orchestrates
    the graph tools (resolve/outline/query) and vector search, comparing coverage
    against the graph's counts, and returns a cited prose answer. `recursion_limit`
    is the hard step ceiling."""
    from rag_cti.knowledge.agent_graph import ask as _ask

    return _ask(text, recursion_limit=recursion_limit)
