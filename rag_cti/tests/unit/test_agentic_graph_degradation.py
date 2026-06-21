"""Graceful-degradation wiring test for the agentic graph.

A persistent gather-model failure (provider 429 that survives the client-level retry
policy) must yield a degraded ``AgenticAnswer`` with ``stop_reason="provider_error"`` —
NOT propagate and crash the whole answer (and, in an eval, the whole batch). Pure fakes:
no real LLM / Qdrant / Neo4j, so this runs in `make ci`. It exercises the Iter-3 wiring
(``agentic_graph`` is otherwise coverage-omitted): agent_turn catches the model error and
flags it, sufficiency_gate short-circuits past the judge, synthesize runs over the partial
ledger, and the final answer carries the degraded stop_reason.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from rag_cti.knowledge.agentic_graph import build_agentic_graph
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.types import GeneratedAnswer, QueryResult


class _RaisingBoundModel:
    """A tool-bound chat model whose invoke always raises — a persistent provider 429."""

    def __init__(self) -> None:
        self.invoke_count = 0

    def invoke(self, convo: Any) -> Any:
        self.invoke_count += 1
        raise RuntimeError("429 provider down")


class _ChatModel:
    """Fake chat model: bind_tools returns the raising tool-bound model."""

    def __init__(self, bound: _RaisingBoundModel) -> None:
        self._bound = bound

    def bind_tools(self, tools: Any) -> Any:
        return self._bound


class _DegradedGenerator:
    """Fake generator returning a sentinel-style degraded answer (mirrors the real
    Generator's failure contract) over whatever evidence reaches synthesis."""

    def generate(
        self,
        query: str,
        query_result: QueryResult,
        raise_on_failure: bool = False,
        system_prompt: str | None = None,
    ) -> GeneratedAnswer:
        return GeneratedAnswer(
            query=query,
            answer="Unable to generate answer: LLM call failed.",
            cited_chunk_ids=[],
            query_result=query_result,
            generation_ms=0.0,
            model="fake",
        )


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        agentic_max_inner_steps=8,
        agentic_max_iterations=6,
        agentic_token_ceiling=200000,
        agentic_max_retrieve_rounds=2,
        agentic_max_wall_seconds=180.0,
        agentic_synthesis_top_k=50,
    )


def _judge_must_not_run(system: str, user: str) -> str:
    raise AssertionError("judge must be skipped when the gather model failed")


def _empty_retrieve(query: str, top_k: int) -> QueryResult:
    return QueryResult(query=query, results=[], total_retrieved=0, retrieval_ms=0.0)


def test_agentic_graph_degrades_on_persistent_gather_failure() -> None:
    ledger = EvidenceLedger()
    bound = _RaisingBoundModel()
    graph = build_agentic_graph(
        settings=_settings(),
        ledger=ledger,
        query="anything",
        run_retrieve=_empty_retrieve,
        fact_store=None,
        ontology_nodes=[],
        generator=_DegradedGenerator(),
        chat_model=_ChatModel(bound),
        judge=_judge_must_not_run,
    )

    result = graph.invoke(
        {"messages": [("user", "anything")], "iteration_count": 0, "tokens_used": 0},
        config={"recursion_limit": 25},
    )

    answer = result["answer"]
    assert answer.stop_reason == "provider_error"  # short-circuited, did not crash
    assert answer.answer == "Unable to generate answer: LLM call failed."  # degraded answer
    assert bound.invoke_count == 1  # tried once then ended the burst — no retry storm
    assert answer.cited_ids == ()  # nothing gathered, nothing to cite
