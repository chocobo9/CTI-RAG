from __future__ import annotations

from typing import Any

import pytest

from rag_cti.generation.generator import _LLM_FAILURE_SENTINEL, Generator
from rag_cti.types import QueryResult


class _FailingCompletions:
    def create(self, **_: Any) -> Any:
        raise RuntimeError("provider down")


class _FailingChat:
    completions = _FailingCompletions()


class _FailingClient:
    chat = _FailingChat()


class _Router:
    def model_for(self, task: object) -> str:
        return "test-model"


class _Settings:
    generation_max_tokens = 64


def _empty_query_result() -> QueryResult:
    return QueryResult(query="q", results=[], total_retrieved=0, retrieval_ms=0.0)


def test_generate_returns_sentinel_by_default_on_llm_failure() -> None:
    gen = Generator(client=_FailingClient(), router=_Router(), settings=_Settings())
    answer = gen.generate("what is T1566?", _empty_query_result())
    assert answer.answer == _LLM_FAILURE_SENTINEL


def test_generate_raises_when_raise_on_failure_set() -> None:
    gen = Generator(client=_FailingClient(), router=_Router(), settings=_Settings())
    with pytest.raises(RuntimeError, match="LLM call failed"):
        gen.generate("what is T1566?", _empty_query_result(), raise_on_failure=True)
