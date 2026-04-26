from __future__ import annotations

from typing import Protocol, runtime_checkable

from rag_cti.types import RetrievalResult


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]: ...


class NoOpReranker:
    """Pass-through reranker — preserves input order unchanged."""

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        return results
