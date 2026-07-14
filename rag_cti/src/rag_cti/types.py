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
# M4-era graph-query outputs (historical rationale:
# docs/archive/runtime/HISTORICAL_M4_consumption_langgraph_design.md §6)
# ---------------------------------------------------------------------------


class FactCitation(BaseModel, frozen=True):
    """One ``supports`` edge: an evidence chunk attesting a fact, from one origin.

    ``content`` is filled best-effort from Qdrant by ``evidence_id`` (== chunk.id);
    "" when the chunk is absent — never fabricated (M4 invariant 2).
    """

    evidence_id: str
    origin: str
    confidence: float
    label_availability: str
    observed_first: str | None = None
    observed_last: str | None = None
    content: str = ""


class FactRow(BaseModel, frozen=True):
    """One Fact ready to render: the triple + materialized credibility + citations."""

    fact_id: str
    subject_id: str
    subject_name: str
    predicate: str
    object_id: str
    object_name: str
    object_type: str
    aggregate_credibility: float
    conflict: bool
    distinct_origins: tuple[str, ...] = ()
    support_count: int = 0
    citations: tuple[FactCitation, ...] = ()


class FactQueryResult(BaseModel, frozen=True):
    """A graph query's result: enumerated facts (credibility-desc), conflicts surfaced.

    Not truncated — completeness is the point (M4 §2). ``conflicts`` keeps both
    sides of a single-valued-predicate clash side by side (DECISION-5).
    """

    query_repr: str
    subject_id: str | None = None
    predicate: str | None = None
    object_type: str | None = None
    facts: tuple[FactRow, ...] = ()
    fact_query_ms: float = 0.0

    @property
    def conflicts(self) -> tuple[FactRow, ...]:
        return tuple(f for f in self.facts if f.conflict)


class OutlineEntry(BaseModel, frozen=True):
    """One relation category in an entity's coverage map: predicate + far-end type."""

    predicate: str
    other_type: str
    count: int
    max_credibility: float


class GraphOutline(BaseModel, frozen=True):
    """Coverage gauge for one entity (M4 §2/§3): which relation categories exist and
    how many. The agent's planning/sufficiency basis — the graph, being exhaustively
    enumerable, is the completeness signal a vector top-k cannot give.
    """

    entity_id: str
    entity_name: str
    entity_type: str
    outgoing: tuple[OutlineEntry, ...] = ()
    incoming: tuple[OutlineEntry, ...] = ()


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
