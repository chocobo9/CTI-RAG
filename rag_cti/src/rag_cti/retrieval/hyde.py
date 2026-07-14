from __future__ import annotations

import time
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.observability.tracing import traced
from rag_cti.types import (
    PayloadConstraint,
    RetrievalResult,
    SettingsProto,
    SparseCapableRetrieverProto,
)

logger = get_logger(__name__)

_HYDE_SYSTEM_PROMPT = (
    "You are a cyber threat intelligence analyst. Write a short passage (3-5 sentences) "
    "that directly answers the given CTI query. The passage should read like an excerpt "
    "from a threat intelligence report, using technical terminology, IOCs if relevant, and "
    "ATT&CK technique references where appropriate. Respond with only the passage text."
)


class HyDERetriever:
    """Hypothetical Document Embeddings retriever for CTI queries.

    Generates a hypothetical CTI passage for the query via an LLM, embeds it,
    then performs dense search using that embedding. Falls back to direct query
    embedding when HyDE is disabled or the query is too short to benefit.
    """

    def __init__(
        self,
        base_retriever: SparseCapableRetrieverProto,
        llm_client: object,
        settings: SettingsProto,
        llm_provider: str = "",
    ) -> None:
        self._base = base_retriever
        self._settings = settings
        # Provider-specific OpenAI-compatible chat.completions clients
        # (Groq/Ollama), so Any keeps tests light.
        self._llm: Any
        # Accept (provider, client) tuple from build_llm_client, or a bare client.
        if isinstance(llm_client, tuple) and len(llm_client) == 2:
            detected_provider, bare_client = llm_client
            self._llm = bare_client
            self._llm_provider = llm_provider or str(detected_provider)
        else:
            self._llm = llm_client
            if llm_provider:
                self._llm_provider = llm_provider
            elif hasattr(llm_client, "chat"):
                # OpenAI-compatible interface (RetryingGroqClient or RetryingOllamaClient)
                self._llm_provider = (
                    "ollama" if getattr(settings, "ollama_enabled", False) else "groq"
                )
            else:
                self._llm_provider = "groq"

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
        constraint: PayloadConstraint | None = None,
    ) -> list[RetrievalResult]:
        """Search using a hypothetical document embedding, or fall back to direct query."""
        query_tokens = len(query.split())
        if not self._settings.hyde_enabled or query_tokens < self._settings.hyde_min_query_tokens:
            logger.debug(
                "hyde bypassed",
                hyde_enabled=self._settings.hyde_enabled,
                query_tokens=query_tokens,
                min_tokens=self._settings.hyde_min_query_tokens,
            )
            return self._base.search(
                query, top_k=top_k, source_filter=source_filter, constraint=constraint
            )

        t0 = time.perf_counter()
        hypothetical_doc = self._generate_hypothetical_doc(query)
        search_query = hypothetical_doc if hypothetical_doc is not None else query
        # sparse_query: BM25 always sees the ORIGINAL query — exact IOC/hash
        # tokens must not be replaced by the hypothetical document, which only
        # benefits the dense path.
        results: list[RetrievalResult] = self._base.search(
            search_query,
            top_k=top_k,
            source_filter=source_filter,
            sparse_query=query,
            constraint=constraint,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            "hyde search complete",
            top_k=top_k,
            returned=len(results),
            elapsed_ms=round(elapsed_ms, 1),
        )
        return results

    @traced("retrieval.hyde.generate_doc", run_type="llm")
    def _generate_hypothetical_doc(self, query: str) -> str | None:
        max_tokens = getattr(self._settings, "hyde_max_tokens", 300)
        max_chars = getattr(self._settings, "hyde_output_max_chars", 2000)
        try:
            model = (
                self._settings.ollama_model
                if self._llm_provider == "ollama"
                else self._settings.groq_query_model
            )
            resp = self._llm.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": _HYDE_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
            )
            text: str = (resp.choices[0].message.content or "").strip()[:max_chars]
            return text if text else None
        except Exception as exc:
            logger.warning("hyde llm call failed, falling back to direct query", error=str(exc))
            return None
