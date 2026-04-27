from __future__ import annotations

from datetime import datetime
from typing import Any

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


class GeneratedAnswer(BaseModel, frozen=True):
    query: str
    answer: str
    cited_chunk_ids: list[str]
    query_result: QueryResult
    generation_ms: float
    model: str
