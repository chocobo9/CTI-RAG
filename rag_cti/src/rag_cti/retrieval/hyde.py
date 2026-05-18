from __future__ import annotations

import time

from rag_cti._logging import get_logger
from rag_cti.observability.tracing import traced
from rag_cti.types import RetrievalResult

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
        base_retriever: object,
        llm_client: object,
        settings: object,
        llm_provider: str = "",
    ) -> None:
        self._base = base_retriever
        self._settings = settings
        # Accept (provider, client) tuple from build_llm_client, or a bare client.
        if isinstance(llm_client, tuple) and len(llm_client) == 2:
            detected_provider, bare_client = llm_client  # type: ignore[misc]
            self._llm = bare_client
            self._llm_provider = llm_provider or str(detected_provider)
        else:
            self._llm = llm_client
            if llm_provider:
                self._llm_provider = llm_provider
            elif hasattr(llm_client, "chat"):
                # OpenAI-compatible interface (RetryingGroqClient or RetryingOllamaClient)
                self._llm_provider = "ollama" if getattr(settings, "ollama_enabled", False) else "groq"
            else:
                self._llm_provider = "anthropic"

    def search(
        self,
        query: str,
        top_k: int = 10,
        source_filter: str | list[str] | None = None,
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
            return self._base.search(query, top_k=top_k, source_filter=source_filter)

        t0 = time.perf_counter()
        hypothetical_doc = self._generate_hypothetical_doc(query)
        search_query = hypothetical_doc if hypothetical_doc is not None else query
        results: list[RetrievalResult] = self._base.search(
            search_query, top_k=top_k, source_filter=source_filter,
            sparse_query=query,
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
        try:
            if self._llm_provider in ("groq", "ollama"):
                model = (
                    self._settings.ollama_model
                    if self._llm_provider == "ollama"
                    else self._settings.groq_query_model
                )
                resp = self._llm.chat.completions.create(
                    model=model,
                    max_tokens=300,
                    messages=[
                        {"role": "system", "content": _HYDE_SYSTEM_PROMPT},
                        {"role": "user", "content": query},
                    ],
                )
                text = (resp.choices[0].message.content or "").strip()[:2000]
                return text if text else None
            else:
                response = self._llm.messages.create(
                    model=self._settings.llm_routing_model,
                    max_tokens=300,
                    system=_HYDE_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": query}],
                )
                return response.content[0].text.strip()[:2000]
        except Exception as exc:
            logger.warning("hyde llm call failed, falling back to direct query", error=str(exc))
            return None
