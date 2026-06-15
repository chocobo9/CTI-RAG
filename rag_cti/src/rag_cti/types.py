from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Document(BaseModel, frozen=True):
    id: str
    source: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    embedding_model: str = ""

    def with_embedding_model(self, model: str) -> Document:
        return self.model_copy(update={"embedding_model": model})


class Chunk(BaseModel, frozen=True):
    id: str
    parent_doc_id: str
    source: str
    content: str
    chunk_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    embedding_model: str = ""

    @classmethod
    def from_document(cls, doc: Document, content: str, chunk_index: int, chunk_id: str) -> Chunk:
        return cls(
            id=chunk_id,
            parent_doc_id=doc.id,
            source=doc.source,
            content=content,
            chunk_index=chunk_index,
            metadata=doc.metadata,
            retrieved_at=doc.retrieved_at,
            embedding_model=doc.embedding_model,
        )


class RetrievalResult(BaseModel, frozen=True):
    document: Chunk
    score: float
    rank: int
    retriever_source: str


class QueryResult(BaseModel, frozen=True):
    query: str
    results: list[RetrievalResult]
    total_retrieved: int
    retrieval_ms: float


class PayloadConstraint(BaseModel, frozen=True):
    """Structured pre-filter applied before vector search (retrieval-layer §6).

    Each non-empty field becomes an AND'd payload condition (MatchAny *within* a
    field; e.g. ``attack_ids`` matches a chunk whose attack_ids list contains any
    of the requested ids). All-empty means no structured constraint. Deterministic
    constraints filter first instead of going through the similarity channel.
    """

    source_types: tuple[str, ...] = ()
    attack_ids: tuple[str, ...] = ()
    entity_ids: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.source_types or self.attack_ids or self.entity_ids)


class GeneratedAnswer(BaseModel, frozen=True):
    query: str
    answer: str
    cited_chunk_ids: list[str]
    query_result: QueryResult
    generation_ms: float
    model: str


# ---------------------------------------------------------------------------
# Structural protocols — use for type-hinting boundaries, not isinstance checks
# ---------------------------------------------------------------------------


@runtime_checkable
class RetrieverProto(Protocol):
    # source_filter/constraint are keyword-only so a SparseCapable retriever
    # (whose 4th positional is sparse_query) still structurally satisfies this.
    def search(
        self,
        query: str,
        top_k: int = 10,
        *,
        source_filter: str | list[str] | None = None,
        constraint: PayloadConstraint | None = None,
    ) -> list[RetrievalResult]: ...


class SparseCapableRetrieverProto(Protocol):
    """Retriever whose search accepts a separate BM25 ``sparse_query`` (HybridRetriever)."""

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
        sparse_query: str | None = None,
        constraint: PayloadConstraint | None = None,
    ) -> list[RetrievalResult]: ...


class SettingsProto(Protocol):
    """Structural view of config.Settings used by the retrieval/generation layers.

    Test fakes only need the fields the module under test touches at runtime;
    this protocol is a typing aid, never an isinstance check.
    """

    retrieval_top_k: int
    hyde_enabled: bool
    hyde_min_query_tokens: int
    ollama_enabled: bool
    ollama_model: str
    groq_query_model: str
    groq_analysis_model: str
    groq_report_model: str
    llm_routing_model: str
    reranker_model: str


class LLMClientProto(Protocol):
    """Groq / OpenAI-compatible chat-completions client interface."""

    class _CompletionsProto(Protocol):
        def create(self, **kwargs: Any) -> Any: ...

    class _ChatProto(Protocol):
        completions: Any

    chat: _ChatProto


class VectorStoreProto(Protocol):
    def upsert(self, chunks: list[Chunk], embeddings: Any) -> int: ...
    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        source_filter: str | None = None,
    ) -> list[RetrievalResult]: ...
