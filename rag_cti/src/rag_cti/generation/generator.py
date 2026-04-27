from __future__ import annotations

import time
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.generation.context_builder import build_context_messages, extract_cited_ids
from rag_cti.generation.llm_router import LLMRouter, TaskType
from rag_cti.types import GeneratedAnswer, QueryResult

logger = get_logger(__name__)


class Generator:
    """Generates grounded CTI answers via Groq, with context injected in the user message."""

    def __init__(self, client: Any, router: LLMRouter, settings: Any) -> None:
        self._client = client
        self._router = router
        self._settings = settings

    def generate(self, query: str, query_result: QueryResult) -> GeneratedAnswer:
        model = self._router.model_for(TaskType.ANALYSIS)
        messages = build_context_messages(query, query_result.results)

        t0 = time.perf_counter()
        answer_text = self._call_llm(model, messages)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

        cited = extract_cited_ids(answer_text)
        logger.debug(
            "generation complete",
            model=model,
            cited_count=len(cited),
            elapsed_ms=elapsed_ms,
        )
        return GeneratedAnswer(
            query=query,
            answer=answer_text,
            cited_chunk_ids=cited,
            query_result=query_result,
            generation_ms=elapsed_ms,
            model=model,
        )

    def _call_llm(self, model: str, messages: list[dict[str, Any]]) -> str:
        try:
            response = self._client.chat.completions.create(
                model=model,
                max_tokens=self._settings.generation_max_tokens,
                messages=messages,
            )
            return _extract_text(response)
        except Exception as exc:
            logger.warning("generation llm call failed", error=str(exc))
            return "Unable to generate answer: LLM call failed."


def _extract_text(response: Any) -> str:
    return response.choices[0].message.content or ""
