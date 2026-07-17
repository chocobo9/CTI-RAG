"""RAG-powered Cyber Threat Intelligence retrieval system.

Public interface:
    query(text, top_k) -> QueryResult      retrieve relevant CTI chunks with scores and metadata
    answer(text, k)    -> GeneratedAnswer  retrieve + generate a grounded answer with cited IDs
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from rag_cti.config import get_settings
from rag_cti.observability.tracing import traced
from rag_cti.retrieval import Pipeline, build_pipeline
from rag_cti.runtime_harness import (
    RuntimeDeps,
    RuntimeQueryUnderstanding,
    build_runtime_query_understanding,
    evaluate_supervisor_admission,
    run_agentic_investigation,
)
from rag_cti.types import FactQueryResult, GeneratedAnswer, QueryResult

if TYPE_CHECKING:
    from rag_cti.knowledge.agentic_state import AgenticAnswer

__all__ = [
    "query",
    "answer",
    "answer_single_shot",
    "agentic_answer",
    "supervised_answer",
    "close_cached_resources",
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


@traced("runtime.answer", run_type="chain")
def answer(text: str, k: int = 10, history: list[str] | None = None) -> GeneratedAnswer:
    """Generate a grounded answer with cited chunk IDs.

    Agentic RAG is the mainline answer path. Runtime query understanding may admit
    a validated independent decomposition to the supervisor path when supervisor support
    is enabled. ``answer_single_shot`` remains available as an explicit baseline/fallback
    API. ``k`` is kept for API compatibility and still applies to single-shot callers,
    but the agentic path sizes its own retrieval tools.
    """
    from rag_cti.knowledge.supervisor_graph import run_supervised_answer
    from rag_cti.observability.tracing import add_trace_metadata

    deps = _build_runtime_deps(history)
    understanding = deps.query_understanding(text, history)
    max_branches = int(getattr(deps.settings, "supervisor_max_branches", 4))
    supervisor_allowed = bool(getattr(deps.settings, "supervisor_enabled", False))
    admission = evaluate_supervisor_admission(understanding, max_branches=max_branches)
    if not supervisor_allowed and admission.admitted:
        admission = admission.__class__(
            "single_agent",
            "supervisor_disabled",
            admission.branches,
        )
    add_trace_metadata(
        runtime_path=admission.decision,
        supervisor_enabled=supervisor_allowed,
        admission_reason=admission.reason,
        understanding_status=understanding.status,
        understanding_fallback_reason=understanding.fallback_reason,
        standalone_query=understanding.standalone_query,
        retrieval_query_count=len(understanding.retrieval_queries),
        entity_count=len(understanding.entities),
        proposed_branch_count=(
            len(understanding.decomposition.branches)
            if understanding.decomposition is not None
            else 0
        ),
        admitted_branch_count=len(admission.branches),
        admitted_branch_ids=[b.branch_id for b in admission.branches],
    )
    if admission.admitted:
        supervised = run_supervised_answer(
            understanding.standalone_query,
            settings=deps.settings,
            history=history,
            run_retrieve=deps.run_retrieve,
            fact_store=deps.fact_store,
            ontology_nodes=deps.ontology_nodes,
            generator=deps.generator,
            chat_model=deps.gather_model,
            judge=deps.judge,
            composer=deps.composer,
            branch_plan=admission.branches,
        )
        return GeneratedAnswer(
            query=supervised.query,
            answer=supervised.answer,
            cited_chunk_ids=list(supervised.cited_ids),
            query_result=supervised.query_result,
            generation_ms=0.0,
            model="supervisor",
        )
    agentic = run_agentic_investigation(
        understanding.standalone_query,
        settings=deps.settings,
        history=history,
        run_retrieve=deps.run_retrieve,
        fact_store=deps.fact_store,
        ontology_nodes=deps.ontology_nodes,
        generator=deps.generator,
        chat_model=deps.gather_model,
        judge=deps.judge,
    )
    return GeneratedAnswer(
        query=agentic.query,
        answer=agentic.answer,
        cited_chunk_ids=list(agentic.cited_ids),
        query_result=agentic.query_result,
        generation_ms=0.0,
        model="agentic",
    )


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


def agentic_answer(text: str, history: list[str] | None = None) -> AgenticAnswer:
    """Debug/baseline forced single-agent surface.

    Answer a CTI question via the agentic loop (workflow->agentic): adaptive
    retrieve -> assess sufficiency -> retrieve more -> synthesize. Reuses the
    single-shot retrieval pipeline as the agent's `retrieve` tool and the knowledge
    graph as graph tools; citations are validated against the gathered evidence and
    conflicts are surfaced. Graph tools degrade to no-ops when Neo4j is disabled
    (empty NEO4J_PASSWORD) so the loop still runs vector-only."""
    deps = _build_runtime_deps(history)
    return run_agentic_investigation(
        text,
        settings=deps.settings,
        history=history,
        run_retrieve=deps.run_retrieve,
        fact_store=deps.fact_store,
        ontology_nodes=deps.ontology_nodes,
        generator=deps.generator,
        chat_model=deps.gather_model,
        judge=deps.judge,
    )


def supervised_answer(text: str, history: list[str] | None = None) -> AgenticAnswer:
    """Debug/baseline forced supervisor surface.

    Answer a CTI question via the multi-agent supervisor (Model B): a ReAct ORCHESTRATION
    agent dispatches worker sub-agents (one per independent entity/facet, in parallel),
    each gathering evidence into a branch-local ledger, then a distinct Composer LLM
    combines the reports into the final answer. The supervisor never gathers or synthesizes;
    a deterministic citation guard validates the answer against the union of branch evidence.
    Simple / dependent questions degrade to a single worker (no regression). Builds the same
    deps as the agentic loop plus a composer (which reuses the verifier client)."""
    from rag_cti.knowledge.supervisor_graph import run_supervised_answer

    deps = _build_runtime_deps(history)
    return run_supervised_answer(
        text,
        settings=deps.settings,
        history=history,
        run_retrieve=deps.run_retrieve,
        fact_store=deps.fact_store,
        ontology_nodes=deps.ontology_nodes,
        generator=deps.generator,
        chat_model=deps.gather_model,
        judge=deps.judge,
        composer=deps.composer,
    )


def _build_runtime_deps(history: list[str] | None = None) -> RuntimeDeps:
    """Build reusable runtime dependencies; no per-run state belongs here."""
    from typing import cast

    from rag_cti.bootstrap import load_ontology_nodes
    from rag_cti.knowledge.agentic_graph import build_judge
    from rag_cti.knowledge.agentic_nodes import GeneratorProto
    from rag_cti.knowledge.fact_store import FactStoreProto
    from rag_cti.knowledge.model_factory import build_model
    from rag_cti.knowledge.supervisor_graph import build_composer

    settings = get_settings()
    pipeline = _default_pipeline()
    ontology_nodes = load_ontology_nodes()

    def run_retrieve(query_text: str, top_k: int) -> QueryResult:
        return pipeline.run(query_text, top_k=top_k, history=history)

    def query_understanding(
        query_text: str, query_history: list[str] | None = None
    ) -> RuntimeQueryUnderstanding:
        return build_runtime_query_understanding(
            query_text,
            query_history,
            pipeline=pipeline,
            settings=settings,
            ontology_nodes=ontology_nodes,
        )

    fact_store = (
        cast(FactStoreProto, _default_fact_store())
        if settings.neo4j_password.get_secret_value()
        else None
    )
    verifier_client = _build_verifier_client(settings)
    return RuntimeDeps(
        settings=settings,
        retrieval_pipeline=pipeline,
        run_retrieve=run_retrieve,
        fact_store=fact_store,
        ontology_nodes=ontology_nodes,
        query_understanding=query_understanding,
        gather_model=build_model(settings),
        generator=cast(GeneratorProto, _default_generator()),
        judge=build_judge(
            verifier_client,
            settings.agentic_verifier_model,
            max_tokens=settings.agentic_verifier_max_tokens,
        ),
        composer=build_composer(
            verifier_client,
            settings.agentic_verifier_model,
            max_tokens=settings.supervisor_compose_max_tokens,
        ),
    )


def _build_verifier_client(settings: object) -> object:
    """Build the OpenAI-compatible client for the sufficiency judge, per
    ``agentic_verifier_provider``. "qwen" gives an INDEPENDENT cross-family verifier
    (DashScope); "deepseek" (default) reuses the DeepSeek client — same family as the
    gatherer, so not independent. ``build_judge`` accepts any OpenAI-compatible client."""
    provider = getattr(settings, "agentic_verifier_provider", "deepseek")
    if provider == "qwen":
        from rag_cti.bootstrap import build_qwen_client

        return build_qwen_client(settings)
    from rag_cti.bootstrap import build_deepseek_client

    return build_deepseek_client(settings)


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


def _close_cached_factory(factory: Any) -> None:
    cache_info = factory.cache_info()
    if cache_info.currsize <= 0:
        return
    resource = factory()
    close = getattr(resource, "close", None)
    try:
        if callable(close):
            close()
    finally:
        factory.cache_clear()


def close_cached_resources() -> None:
    """Close cached external resources without creating caches that do not exist."""
    _close_cached_factory(_default_fact_store)
    _close_cached_factory(_default_chunk_store)


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
    """Compatibility wrapper for the retired v1 ``ask`` API.

    The ``recursion_limit`` argument is accepted for old callers but ignored; the
    supported implementation is the hard-railed ``agentic_answer`` path.
    """
    _ = recursion_limit
    return agentic_answer(text).answer
