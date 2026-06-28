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

from rag_cti.knowledge.agentic_graph import _normalize_tool_args, build_agentic_graph
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.types import FactRow, GeneratedAnswer, GraphOutline, OutlineEntry, QueryResult


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


class _RetrieveThenStopModel:
    def __init__(self) -> None:
        self.invoke_count = 0

    def invoke(self, convo: Any) -> Any:
        self.invoke_count += 1
        if self.invoke_count == 1:
            return SimpleNamespace(
                tool_calls=[
                    {
                        "id": "call_retrieve",
                        "name": "retrieve",
                        "args": {"query": "APT29 Turla shared ATT&CK techniques", "top_k": 5},
                    }
                ],
                usage_metadata={"total_tokens": 1},
            )
        return SimpleNamespace(tool_calls=[], usage_metadata={"total_tokens": 1})


class _NoToolModel:
    def __init__(self) -> None:
        self.invoke_count = 0

    def invoke(self, convo: Any) -> Any:
        self.invoke_count += 1
        return SimpleNamespace(tool_calls=[], usage_metadata={"total_tokens": 1})


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
        agentic_keep_last_observations=0,
        agentic_open_cat_stall_limit=2,
        agentic_effort_budgets={"simple": 3, "comparison": 8, "complex": 12},
        agentic_parallel_dispatch_enabled=False,
        agentic_max_parallel_tools=2,
    )


def _judge_must_not_run(system: str, user: str) -> str:
    raise AssertionError("judge must be skipped when the gather model failed")


def _empty_retrieve(query: str, top_k: int) -> QueryResult:
    return QueryResult(query=query, results=[], total_retrieved=0, retrieval_ms=0.0)


def _fact(subject_id: str, subject_name: str, technique: str, idx: int) -> FactRow:
    return FactRow(
        fact_id=f"fact_{subject_id}_{idx}",
        subject_id=subject_id,
        subject_name=subject_name,
        predicate="uses",
        object_id=f"technique_{idx}",
        object_name=technique,
        object_type="technique",
        aggregate_credibility=0.9,
        conflict=False,
    )


def _complete_uses_outline(entity_id: str, entity_name: str, count: int) -> GraphOutline:
    return GraphOutline(
        entity_id=entity_id,
        entity_name=entity_name,
        entity_type="threat-actor",
        outgoing=(
            OutlineEntry(
                predicate="uses", other_type="technique", count=count, max_credibility=0.9
            ),
        ),
    )


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


def test_normalize_tool_args_compacts_long_retrieve_query() -> None:
    query = "APT29\n\n" + " ".join(f"term{i}" for i in range(100))
    normalized = _normalize_tool_args(
        "retrieve", {"query": query, "top_k": 30}, retrieve_query_max_chars=80
    )
    assert normalized["query"].startswith("APT29 term0 term1")
    assert len(normalized["query"]) <= 80
    assert normalized["top_k"] == 30


def test_agentic_graph_suppresses_retrieve_when_graph_facts_cover_comparison() -> None:
    ledger = EvidenceLedger()
    ledger.add_outline(_complete_uses_outline("actor_APT29", "APT29", 2))
    ledger.add_outline(_complete_uses_outline("actor_Turla", "Turla", 2))
    ledger.add_facts(
        (
            _fact("actor_APT29", "APT29", "PowerShell", 1),
            _fact("actor_APT29", "APT29", "Spearphishing Link", 2),
            _fact("actor_Turla", "Turla", "PowerShell", 3),
            _fact("actor_Turla", "Turla", "Ingress Tool Transfer", 4),
        )
    )
    bound = _RetrieveThenStopModel()
    retrieve_calls: list[tuple[str, int]] = []

    def run_retrieve(query: str, top_k: int) -> QueryResult:
        retrieve_calls.append((query, top_k))
        return _empty_retrieve(query, top_k)

    graph = build_agentic_graph(
        settings=_settings(),
        ledger=ledger,
        query="Compare APT29 and Turla ATT&CK techniques: shared and unique.",
        run_retrieve=run_retrieve,
        fact_store=None,
        ontology_nodes=[],
        generator=_DegradedGenerator(),
        chat_model=_ChatModel(bound),
        judge=lambda _system, _user: '{"next_action":"stop","sufficient":true}',
    )

    graph.invoke(
        {"messages": [("user", "anything")], "iteration_count": 0, "tokens_used": 0},
        config={"recursion_limit": 25},
    )

    assert retrieve_calls == []


def test_agentic_graph_stops_graph_covered_comparison_without_judge() -> None:
    ledger = EvidenceLedger()
    ledger.add_outline(_complete_uses_outline("actor_APT29", "APT29", 2))
    ledger.add_outline(_complete_uses_outline("actor_Turla", "Turla", 2))
    ledger.add_facts(
        (
            _fact("actor_APT29", "APT29", "PowerShell", 1),
            _fact("actor_APT29", "APT29", "Spearphishing Link", 2),
            _fact("actor_Turla", "Turla", "PowerShell", 3),
            _fact("actor_Turla", "Turla", "Ingress Tool Transfer", 4),
        )
    )
    bound = _NoToolModel()
    graph = build_agentic_graph(
        settings=_settings(),
        ledger=ledger,
        query="Compare APT29 and Turla ATT&CK techniques: shared and unique.",
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

    assert result["answer"].stop_reason == "graph_sufficient"
