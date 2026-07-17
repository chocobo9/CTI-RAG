from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from langchain_core.messages import ToolMessage

from rag_cti.knowledge.agentic_state import AgenticAnswer
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.retrieval.constraint_extract import ExtractedEntity, RewriteOutput
from rag_cti.runtime_harness import (
    DecompositionProposal,
    ProposedBranch,
    RuntimeActionProposal,
    RuntimeEvent,
    RuntimeInvestigationState,
    RuntimeObservation,
    RuntimeQueryUnderstanding,
    RuntimeTurnAdapter,
    RuntimeTurnResult,
    admit_supervisor,
    apply_observation_to_state,
    build_runtime_query_understanding,
    evaluate_supervisor_admission,
    run_agentic_investigation,
)
from rag_cti.types import (
    Chunk,
    FactRow,
    GeneratedAnswer,
    GraphOutline,
    OutlineEntry,
    PayloadConstraint,
    QueryResult,
    RetrievalResult,
)


def _understanding(
    *,
    status: str = "ok",
    retrieval_queries: tuple[str, ...] = ("q",),
    decomposition: DecompositionProposal | None = None,
    payload_constraint: PayloadConstraint | None = None,
) -> RuntimeQueryUnderstanding:
    return RuntimeQueryUnderstanding(
        original_query="q",
        standalone_query="q",
        retrieval_queries=retrieval_queries,
        entities=(ExtractedEntity(name="APT29", type="actor"),),
        payload_constraint=payload_constraint,
        decomposition=decomposition,
        status=status,  # type: ignore[arg-type]
    )


def _proposal(*branches: ProposedBranch, suitable: bool = True) -> DecompositionProposal:
    return DecompositionProposal(branches=branches, suitable_for_supervisor=suitable)


def _branch(branch_id: str, entity: str) -> ProposedBranch:
    return ProposedBranch(
        branch_id=branch_id,
        sub_question=f"What techniques does {entity} use?",
        focus_entity=entity,
        facet="ttps",
        independent_reason="Separate entity in comparison.",
    )


def _empty_qr(query: str = "q") -> QueryResult:
    return QueryResult(query=query, results=[], total_retrieved=0, retrieval_ms=0.0)


def _qr_with_chunk(query: str, chunk_id: str = "chunk-1") -> QueryResult:
    return QueryResult(
        query=query,
        results=[
            RetrievalResult(
                document=Chunk(
                    id=chunk_id,
                    parent_doc_id="doc-1",
                    source="report.md",
                    content="APT29 uses spearphishing attachments.",
                    chunk_index=0,
                ),
                score=0.91,
                rank=0,
                retriever_source="fake",
            )
        ],
        total_retrieved=1,
        retrieval_ms=1.5,
    )


def _fact_row(fact_id: str = "fact-1") -> FactRow:
    return FactRow(
        fact_id=fact_id,
        subject_id="actor_G0016",
        subject_name="APT29",
        predicate="uses",
        object_id="technique_T1566",
        object_name="Phishing",
        object_type="technique",
        aggregate_credibility=0.97,
        conflict=False,
    )


class _FakeRewriter:
    def __init__(
        self,
        *,
        rewrite_output: RewriteOutput,
        runtime_raw: str | None,
    ) -> None:
        self._rewrite_output = rewrite_output
        self._runtime_raw = runtime_raw
        self.runtime_prompts: list[tuple[str, str]] = []
        self.max_tokens_seen: int | None = None

    def rewrite_with_entities(self, query: str, history: list[str] | None = None) -> RewriteOutput:
        return self._rewrite_output

    def _generate_raw(self, system: str, user: str, max_tokens: int | None = None) -> str | None:
        self.runtime_prompts.append((system, user))
        self.max_tokens_seen = max_tokens
        return self._runtime_raw


class _FakePipeline:
    def __init__(self, rewriter: _FakeRewriter) -> None:
        self._retriever = SimpleNamespace(_rewriter=rewriter)


def _deps(
    understanding: RuntimeQueryUnderstanding,
    *,
    supervisor_enabled: bool,
) -> Any:
    from rag_cti.runtime_harness import RuntimeDeps

    return RuntimeDeps(
        settings=SimpleNamespace(
            supervisor_enabled=supervisor_enabled,
            supervisor_max_branches=4,
            supervisor_max_steps=4,
            agentic_synthesis_top_k=5,
            agentic_max_wall_seconds=0.0,
            agentic_verifier_provider="deepseek",
            llm_max_global_concurrency=4,
            llm_rate_limit_per_sec=0.0,
        ),
        retrieval_pipeline=object(),
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=None,
        ontology_nodes=[],
        query_understanding=lambda q, h=None: understanding,
        gather_model=object(),
        generator=object(),
        judge=object(),
        composer=lambda _system, _user: "supervised answer",
    )


def _agentic_answer(query: str = "q") -> AgenticAnswer:
    return AgenticAnswer(query=query, answer="answer", cited_ids=(), query_result=_empty_qr(query))


class _FakeAI:
    def __init__(self, tool_calls: list[dict[str, Any]]) -> None:
        self.tool_calls = tool_calls
        self.content = ""


class _FakeBoundModel:
    def __init__(self, response: _FakeAI | BaseException) -> None:
        self._response = response

    def invoke(self, _messages: list[Any]) -> _FakeAI:
        if isinstance(self._response, BaseException):
            raise self._response
        return self._response


class _FakeChatModel:
    def __init__(self, response: _FakeAI | BaseException) -> None:
        self._response = response

    def bind_tools(self, _tools: list[Any]) -> _FakeBoundModel:
        return _FakeBoundModel(self._response)


def _runtime_settings() -> Any:
    return SimpleNamespace(
        agentic_hard_tool_budgets={"simple": 4, "comparison": 8, "complex": 12},
        agentic_retrieve_query_max_chars=360,
        agentic_effort_budgets={"simple": 4, "comparison": 8, "complex": 12},
        agentic_keep_last_observations=0,
        agentic_parallel_dispatch_enabled=False,
        agentic_max_parallel_tools=1,
    )


def _turn_adapter(
    response: _FakeAI | BaseException,
    ledger: EvidenceLedger,
    *,
    run_retrieve: Any | None = None,
    settings: Any | None = None,
    deadline: float | None = None,
) -> RuntimeTurnAdapter:
    return RuntimeTurnAdapter(
        settings=settings or _runtime_settings(),
        query="q",
        history=None,
        run_retrieve=run_retrieve or (lambda q, k: _empty_qr(q)),
        fact_store=None,
        ontology_nodes=[],
        chat_model=_FakeChatModel(response),
        ledger=ledger,
        deadline=deadline,
    )


def test_runtime_turn_reports_no_tool_call_event() -> None:
    ledger = EvidenceLedger()
    result = _turn_adapter(_FakeAI([]), ledger).run_turn(RuntimeInvestigationState(ledger))

    assert result.observations[0].status == "no_action"
    assert result.observations[0].model_visible_content
    assert [event.kind for event in result.events] == ["no_tool_call"]
    assert result.provider_error is False


def test_runtime_turn_reports_invalid_tool_call_event() -> None:
    ledger = EvidenceLedger()
    result = _turn_adapter(
        _FakeAI([{"name": "unknown_tool", "args": {"x": 1}, "id": "t1"}]),
        ledger,
    ).run_turn(RuntimeInvestigationState(ledger))

    assert any(event.kind == "invalid_tool_call" for event in result.events)
    assert result.observations[0].status == "invalid"
    assert result.observations[0].error_kind == "unknown_tool"
    assert all(action.name != "unknown_tool" for action in ledger.actions)


def test_runtime_turn_reports_tool_result_event() -> None:
    ledger = EvidenceLedger()
    state = RuntimeInvestigationState(ledger)
    result = _turn_adapter(
        _FakeAI([{"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"}]),
        ledger,
    ).run_turn(state)

    assert any(event.kind == "tool_result" for event in result.events)
    assert ledger.actions == []
    apply_observation_to_state(state, result.observations[0])
    assert [action.name for action in ledger.actions] == ["retrieve"]


def test_runtime_turn_builds_observation_for_tool_result() -> None:
    ledger = EvidenceLedger()
    state = RuntimeInvestigationState(ledger)
    result = _turn_adapter(
        _FakeAI([{"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"}]),
        ledger,
    ).run_turn(state)

    observation = result.observations[0]
    assert isinstance(observation, RuntimeObservation)
    assert observation.tool_name == "retrieve"
    assert observation.action_id
    assert observation.status == "ok"
    assert "APT29" in observation.args_summary
    assert observation.model_visible_content
    assert observation.ledger_delta["actions_added"] == 0
    assert result.events[0] == RuntimeEvent.from_observation(observation)

    apply_observation_to_state(state, observation)

    assert state.observations[0].ledger_delta["actions_added"] == 1


def test_runtime_turn_rejects_malformed_tool_args_before_execution(
    monkeypatch: Any,
) -> None:
    from rag_cti.knowledge import agent_tools

    def fail_resolve(_name: str, _ontology_nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
        raise AssertionError("resolve_entity executed despite invalid args")

    def fail_retrieve(_query: str, _top_k: int) -> QueryResult:
        raise AssertionError("retrieve executed despite invalid args")

    class FailingFactStore:
        def graph_outline(self, _entity_id: str) -> GraphOutline | None:
            raise AssertionError("graph_outline executed despite invalid args")

        def graph_query(self, **_kwargs: Any) -> tuple[Any, ...]:
            raise AssertionError("graph_query executed despite invalid args")

    monkeypatch.setattr(agent_tools, "resolve_entity_candidates", fail_resolve)
    cases = [
        ("resolve_entity", {}),
        ("graph_outline", {"subject_id": 123}),
        ("retrieve", {"query": "APT29", "unexpected": True}),
        ("graph_query", {"subject_id": "actor_G0016", "min_credibility": "high"}),
    ]

    for tool_name, args in cases:
        ledger = EvidenceLedger()
        adapter = RuntimeTurnAdapter(
            settings=_runtime_settings(),
            query="q",
            history=None,
            run_retrieve=fail_retrieve,
            fact_store=FailingFactStore(),
            ontology_nodes=[],
            chat_model=_FakeChatModel(
                _FakeAI([{"name": tool_name, "args": args, "id": f"{tool_name}-call"}])
            ),
            ledger=ledger,
            deadline=None,
        )

        result = adapter.run_turn(RuntimeInvestigationState(ledger))

        assert result.observations[0].status == "invalid"
        assert result.observations[0].error_kind == "invalid_tool_args"
        assert result.events[0].kind == "invalid_tool_call"
        assert ledger.actions == []


def test_runtime_turn_accepts_valid_tool_args(monkeypatch: Any) -> None:
    from rag_cti.knowledge import agent_tools

    outline = GraphOutline(entity_id="actor_G0016", entity_name="APT29", entity_type="actor")

    class FakeFactStore:
        def graph_outline(self, entity_id: str) -> GraphOutline | None:
            assert entity_id == "actor_G0016"
            return outline

        def graph_query(
            self,
            *,
            subject_id: str,
            predicate: str | None = None,
            object_type: str | None = None,
            min_credibility: float = 0.0,
        ) -> tuple[Any, ...]:
            assert subject_id == "actor_G0016"
            assert predicate == "uses"
            assert object_type == "technique"
            assert min_credibility == 0.5
            return ()

    monkeypatch.setattr(
        agent_tools,
        "resolve_entity_candidates",
        lambda name, _ontology_nodes: (
            [{"entity_id": "actor_G0016", "matched_type": "actor"}] if name == "APT29" else []
        ),
    )
    calls = [
        {"name": "resolve_entity", "args": {"name": "APT29"}, "id": "c1"},
        {"name": "graph_outline", "args": {"subject_id": "actor_G0016"}, "id": "c2"},
        {
            "name": "graph_query",
            "args": {
                "subject_id": "actor_G0016",
                "predicate": "uses",
                "object_type": "technique",
                "min_credibility": 0.5,
            },
            "id": "c3",
        },
        {"name": "retrieve", "args": {"query": "APT29", "top_k": 3}, "id": "c4"},
    ]
    ledger = EvidenceLedger()
    state = RuntimeInvestigationState(ledger)
    adapter = RuntimeTurnAdapter(
        settings=_runtime_settings(),
        query="q",
        history=None,
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=FakeFactStore(),
        ontology_nodes=[],
        chat_model=_FakeChatModel(_FakeAI(calls)),
        ledger=ledger,
        deadline=None,
    )

    result = adapter.run_turn(state)

    assert [observation.status for observation in result.observations] == ["ok"] * 4
    assert [event.kind for event in result.events] == ["tool_result"] * 4
    assert ledger.actions == []
    for observation in result.observations:
        apply_observation_to_state(state, observation)
    assert [action.name for action in ledger.actions] == [
        "resolve_entity",
        "graph_outline",
        "graph_query",
        "retrieve",
    ]


def test_runtime_turn_maps_tool_call_to_action_proposal(monkeypatch: Any) -> None:
    seen: list[RuntimeActionProposal] = []
    original_execute = RuntimeTurnAdapter._execute_action_proposal

    def capture_execute(self: RuntimeTurnAdapter, proposal: RuntimeActionProposal) -> Any:
        seen.append(proposal)
        return original_execute(self, proposal)

    monkeypatch.setattr(RuntimeTurnAdapter, "_execute_action_proposal", capture_execute)
    ledger = EvidenceLedger()
    result = _turn_adapter(
        _FakeAI([{"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"}]),
        ledger,
    ).run_turn(RuntimeInvestigationState(ledger))

    observation = result.observations[0]
    event = result.events[0]
    assert seen == [
        RuntimeActionProposal(
            action_id="turn-1-action-1",
            turn_index=1,
            tool_call_id="t1",
            tool_name="retrieve",
            args={"query": "APT29"},
            source="langchain_tool_call",
        )
    ]
    assert observation.action_id == "turn-1-action-1"
    assert event.metadata["action_id"] == observation.action_id
    assert event.metadata["tool_call_id"] == "t1"
    assert event.metadata["proposal_source"] == "langchain_tool_call"


def test_runtime_adapter_extracts_action_proposal_batch() -> None:
    adapter = _turn_adapter(_FakeAI([]), EvidenceLedger())
    adapter._current_turn_index = 2

    proposals = adapter.extract_action_proposals(
        (
            {"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"},
            {"name": "graph_outline", "args": "entity--apt29"},
            {"args": {"query": "missing name"}, "id": "t3"},
        )
    )

    assert proposals == (
        RuntimeActionProposal(
            action_id="turn-2-action-1",
            turn_index=2,
            tool_call_id="t1",
            tool_name="retrieve",
            args={"query": "APT29"},
            source="langchain_tool_call",
        ),
        RuntimeActionProposal(
            action_id="turn-2-action-2",
            turn_index=2,
            tool_call_id="",
            tool_name="graph_outline",
            args={"_raw_args": "entity--apt29"},
            source="langchain_tool_call",
        ),
        RuntimeActionProposal(
            action_id="turn-2-action-3",
            turn_index=2,
            tool_call_id="t3",
            tool_name="",
            args={"query": "missing name"},
            source="langchain_tool_call",
        ),
    )


def test_runtime_turn_executes_action_proposal_batch(monkeypatch: Any) -> None:
    seen_batches: list[tuple[RuntimeActionProposal, ...]] = []
    original_execute_batch = RuntimeTurnAdapter._execute_action_proposals

    def capture_execute_batch(
        self: RuntimeTurnAdapter, proposals: tuple[RuntimeActionProposal, ...]
    ) -> tuple[Any, ...]:
        seen_batches.append(proposals)
        return original_execute_batch(self, proposals)

    monkeypatch.setattr(RuntimeTurnAdapter, "_execute_action_proposals", capture_execute_batch)
    ledger = EvidenceLedger()
    result = _turn_adapter(
        _FakeAI(
            [
                {"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"},
                {"name": "retrieve", "args": {"query": "Turla"}, "id": "t2"},
            ]
        ),
        ledger,
    ).run_turn(RuntimeInvestigationState(ledger))

    assert seen_batches == [
        (
            RuntimeActionProposal(
                action_id="turn-1-action-1",
                turn_index=1,
                tool_call_id="t1",
                tool_name="retrieve",
                args={"query": "APT29"},
                source="langchain_tool_call",
            ),
            RuntimeActionProposal(
                action_id="turn-1-action-2",
                turn_index=1,
                tool_call_id="t2",
                tool_name="retrieve",
                args={"query": "Turla"},
                source="langchain_tool_call",
            ),
        )
    ]
    assert len(result.observations) == 2


def test_runtime_turn_does_not_use_direct_dispatch_paths(monkeypatch: Any) -> None:
    def fail_direct_dispatch(self: RuntimeTurnAdapter, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("production runtime turn bypassed proposal batch")

    monkeypatch.setattr(RuntimeTurnAdapter, "_dispatch", fail_direct_dispatch)
    monkeypatch.setattr(RuntimeTurnAdapter, "_dispatch_tool_call", fail_direct_dispatch)
    ledger = EvidenceLedger()
    result = _turn_adapter(
        _FakeAI([{"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"}]),
        ledger,
    ).run_turn(RuntimeInvestigationState(ledger))

    assert result.proposals
    assert result.observations[0].action_id == result.proposals[0].action_id


def test_runtime_turn_renders_model_visible_text_from_observation() -> None:
    ledger = EvidenceLedger()
    result = _turn_adapter(
        _FakeAI([{"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"}]),
        ledger,
    ).run_turn(RuntimeInvestigationState(ledger))

    tool_messages = [message for message in result.messages if isinstance(message, ToolMessage)]
    assert tool_messages
    assert tool_messages[0].content == result.observations[0].model_visible_content


def test_runtime_turn_reports_tool_error_event() -> None:
    ledger = EvidenceLedger()

    def fail_retrieve(_query: str, _top_k: int) -> QueryResult:
        raise RuntimeError("retriever down")

    result = _turn_adapter(
        _FakeAI([{"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"}]),
        ledger,
        run_retrieve=fail_retrieve,
    ).run_turn(RuntimeInvestigationState(ledger))

    assert any(event.kind == "tool_error" for event in result.events)
    assert result.observations[0].status == "error"
    assert result.observations[0].error_kind == "RuntimeError"
    assert result.provider_error is False


def test_runtime_turn_reports_rejected_tool_observation() -> None:
    ledger = EvidenceLedger()
    for i in range(4):
        ledger.add_action("retrieve", {"query": f"q{i}"})

    result = _turn_adapter(
        _FakeAI([{"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"}]),
        ledger,
    ).run_turn(RuntimeInvestigationState(ledger))

    assert result.observations[0].status == "rejected"
    assert result.observations[0].error_kind == "tool_budget_exhausted"
    assert any(event.kind == "tool_call_rejected" for event in result.events)


def test_runtime_turn_reports_provider_error_event() -> None:
    ledger = EvidenceLedger()
    result = _turn_adapter(RuntimeError("provider down"), ledger).run_turn(
        RuntimeInvestigationState(ledger)
    )

    assert result.provider_error is True
    assert result.observations[0].status == "error"
    assert result.observations[0].error_kind == "provider_error"
    assert any(event.kind == "provider_error" for event in result.events)


def test_runtime_turn_records_deadline_skipped_tool_observation(monkeypatch: Any) -> None:
    from rag_cti.knowledge import react_loop

    first = {"pending": True}

    def fake_monotonic() -> float:
        if first["pending"]:
            first["pending"] = False
            return 0.0
        return 100.0

    monkeypatch.setattr(react_loop.time, "monotonic", fake_monotonic)
    ledger = EvidenceLedger()
    result = _turn_adapter(
        _FakeAI([{"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"}]),
        ledger,
        deadline=5.0,
    ).run_turn(RuntimeInvestigationState(ledger))

    assert result.observations[0].status == "rejected"
    assert result.observations[0].error_kind == "deadline_exceeded"
    assert result.observations[0].tool_name == "retrieve"
    assert result.events[0].metadata["tool_call_id"] == "t1"
    assert [event.kind for event in result.events] == ["tool_call_rejected"]


def test_runtime_turn_parallel_observation_ids_are_unique(monkeypatch: Any) -> None:
    import threading

    original_snapshot = RuntimeTurnAdapter._ledger_snapshot
    barrier = threading.Barrier(2, timeout=5.0)
    lock = threading.Lock()
    calls = {"count": 0}

    def synchronized_snapshot(ledger: Any) -> dict[str, Any]:
        with lock:
            calls["count"] += 1
            count = calls["count"]
        if count > 2:
            barrier.wait()
        return original_snapshot(ledger)

    monkeypatch.setattr(RuntimeTurnAdapter, "_ledger_snapshot", staticmethod(synchronized_snapshot))
    settings = _runtime_settings()
    settings.agentic_parallel_dispatch_enabled = True
    settings.agentic_max_parallel_tools = 2
    ledger = EvidenceLedger()
    tool_barrier = threading.Barrier(2, timeout=5.0)

    def synchronized_retrieve(query: str, top_k: int) -> QueryResult:
        tool_barrier.wait()
        return _empty_qr(query)

    result = _turn_adapter(
        _FakeAI(
            [
                {"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"},
                {"name": "retrieve", "args": {"query": "Turla"}, "id": "t2"},
            ]
        ),
        ledger,
        run_retrieve=synchronized_retrieve,
        settings=settings,
    ).run_turn(RuntimeInvestigationState(ledger))

    observation_ids = [observation.observation_id for observation in result.observations]
    action_ids = [observation.action_id for observation in result.observations]
    assert len(observation_ids) == 2
    assert len(set(observation_ids)) == 2
    assert len(set(action_ids)) == 2


def test_runtime_loop_records_turn_event_metadata(monkeypatch: Any) -> None:
    import rag_cti.runtime_harness as harness

    class FakeAdapter:
        _hard_tool_budget = 4

        def __init__(self, **_kwargs: Any) -> None:
            pass

        def run_turn(self, _state: RuntimeInvestigationState) -> RuntimeTurnResult:
            observation = RuntimeObservation(
                observation_id="obs1",
                turn_index=1,
                action_id="a1",
                tool_name="bad",
                args_summary="",
                status="invalid",
                error_kind="unknown_tool",
                model_visible_content="Invalid tool call: bad",
            )
            return RuntimeTurnResult(
                messages=[],
                tokens_used=3,
                new_evidence=1,
                new_facts=0,
                observations=(observation,),
                events=(RuntimeEvent.from_observation(observation),),
            )

    class FakeGenerator:
        def generate(
            self,
            query: str,
            query_result: QueryResult,
            raise_on_failure: bool = False,
            system_prompt: str | None = None,
        ) -> GeneratedAnswer:
            return GeneratedAnswer(
                query=query,
                answer="answer",
                cited_chunk_ids=[],
                query_result=query_result,
                generation_ms=0.0,
                model="fake",
            )

    metadata: list[dict[str, Any]] = []
    monkeypatch.setattr(harness, "RuntimeTurnAdapter", FakeAdapter)
    monkeypatch.setattr(
        "rag_cti.observability.tracing.add_trace_metadata",
        lambda **kwargs: metadata.append(kwargs),
    )

    answer = run_agentic_investigation(
        "q",
        settings=SimpleNamespace(
            agentic_max_wall_seconds=0.0,
            agentic_max_iterations=3,
            agentic_token_ceiling=100,
            agentic_max_retrieve_rounds=2,
            agentic_open_cat_stall_limit=0,
            agentic_synthesis_top_k=5,
            agentic_synthesis_fact_limit=5,
        ),
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=None,
        ontology_nodes=[],
        generator=FakeGenerator(),
        chat_model=object(),
        judge=lambda s, u: '{"sufficient": true, "next_action": "stop"}',
    )

    assert answer.stop_reason == "sufficient"
    assert any(m.get("runtime_turn_event_kinds") == ["invalid_tool_call"] for m in metadata)
    assert any(m.get("runtime_turn_observation_count") == 1 for m in metadata)
    assert any(m.get("runtime_event_counts") == {"invalid_tool_call": 1} for m in metadata)
    assert any(m.get("runtime_observation_count") == 1 for m in metadata)


def test_runtime_loop_records_proposal_trace_metadata(monkeypatch: Any) -> None:
    import rag_cti.runtime_harness as harness
    from rag_cti.knowledge import agentic_nodes

    proposals = (
        RuntimeActionProposal(
            action_id="a1",
            turn_index=1,
            tool_call_id="t1",
            tool_name="retrieve",
            args={"query": "APT29"},
        ),
        RuntimeActionProposal(
            action_id="a2",
            turn_index=1,
            tool_call_id="t2",
            tool_name="bad",
            args={},
        ),
        RuntimeActionProposal(
            action_id="a3",
            turn_index=1,
            tool_call_id="t3",
            tool_name="retrieve",
            args={"query": "Turla"},
        ),
    )
    observations = (
        RuntimeObservation(
            observation_id="obs1",
            turn_index=1,
            action_id="a1",
            tool_name="retrieve",
            args_summary="query=APT29",
            status="ok",
            model_visible_content="ok",
            event_metadata={"tool_call_id": "t1", "proposal_source": "langchain_tool_call"},
        ),
        RuntimeObservation(
            observation_id="obs2",
            turn_index=1,
            action_id="a2",
            tool_name="bad",
            args_summary="",
            status="invalid",
            error_kind="unknown_tool",
            model_visible_content="invalid",
            event_metadata={"tool_call_id": "t2", "proposal_source": "langchain_tool_call"},
        ),
        RuntimeObservation(
            observation_id="obs3",
            turn_index=1,
            action_id="a3",
            tool_name="retrieve",
            args_summary="query=Turla",
            status="rejected",
            error_kind="deadline_exceeded",
            model_visible_content="deadline",
            event_metadata={"tool_call_id": "t3", "proposal_source": "langchain_tool_call"},
        ),
    )

    class FakeAdapter:
        _hard_tool_budget = 4

        def __init__(self, **_kwargs: Any) -> None:
            pass

        def run_turn(self, _state: RuntimeInvestigationState) -> RuntimeTurnResult:
            return RuntimeTurnResult(
                messages=[],
                tokens_used=3,
                new_evidence=1,
                new_facts=0,
                observations=observations,
                events=tuple(RuntimeEvent.from_observation(obs) for obs in observations),
                proposals=proposals,
            )

    class FakeGenerator:
        def generate(
            self,
            query: str,
            query_result: QueryResult,
            raise_on_failure: bool = False,
            system_prompt: str | None = None,
        ) -> GeneratedAnswer:
            return GeneratedAnswer(
                query=query,
                answer="answer",
                cited_chunk_ids=[],
                query_result=query_result,
                generation_ms=0.0,
                model="fake",
            )

    metadata: list[dict[str, Any]] = []
    monkeypatch.setattr(harness, "RuntimeTurnAdapter", FakeAdapter)
    monkeypatch.setattr(agentic_nodes, "decide_next", lambda *a, **k: ("synthesize", "done"))
    monkeypatch.setattr(
        "rag_cti.observability.tracing.add_trace_metadata",
        lambda **kwargs: metadata.append(kwargs),
    )

    run_agentic_investigation(
        "q",
        settings=SimpleNamespace(
            agentic_max_wall_seconds=0.0,
            agentic_max_iterations=3,
            agentic_token_ceiling=100,
            agentic_max_retrieve_rounds=2,
            agentic_open_cat_stall_limit=0,
            agentic_synthesis_top_k=5,
            agentic_synthesis_fact_limit=5,
        ),
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=None,
        ontology_nodes=[],
        generator=FakeGenerator(),
        chat_model=object(),
        judge=lambda s, u: '{"sufficient": false, "next_action": "retrieve_more"}',
    )

    assert any(m.get("runtime_turn_proposal_count") == 3 for m in metadata)
    assert any(
        m.get("runtime_turn_proposal_status_counts") == {"ok": 1, "invalid": 1, "rejected": 1}
        for m in metadata
    )
    assert any(
        m.get("runtime_turn_proposal_event_counts")
        == {"tool_result": 1, "invalid_tool_call": 1, "tool_call_rejected": 1}
        for m in metadata
    )
    assert any(m.get("runtime_turn_deadline_proposal_count") == 1 for m in metadata)


def test_apply_observation_to_state_records_observation_and_event() -> None:
    state = RuntimeInvestigationState(EvidenceLedger())
    observation = RuntimeObservation(
        observation_id="obs1",
        turn_index=1,
        action_id="a1",
        tool_name="retrieve",
        args_summary="query=APT29",
        status="ok",
        result_summary="ok",
        ledger_delta={"actions_added": 1},
        model_visible_content="ok",
    )

    apply_observation_to_state(state, observation)

    assert state.observations == [observation]
    assert state.events == [RuntimeEvent.from_observation(observation)]


def test_graph_outline_replays_ledger_update_from_runtime_observation() -> None:
    outline = GraphOutline(
        entity_id="actor_G0016",
        entity_name="APT29",
        entity_type="actor",
        outgoing=(
            OutlineEntry(
                predicate="uses",
                other_type="technique",
                count=2,
                max_credibility=1.0,
            ),
        ),
    )

    class FakeFactStore:
        def graph_outline(self, entity_id: str) -> GraphOutline | None:
            assert entity_id == "actor_G0016"
            return outline

    ledger = EvidenceLedger()
    state = RuntimeInvestigationState(ledger)
    adapter = RuntimeTurnAdapter(
        settings=_runtime_settings(),
        query="What techniques does APT29 use?",
        history=None,
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=FakeFactStore(),
        ontology_nodes=[],
        chat_model=_FakeChatModel(
            _FakeAI(
                [
                    {
                        "name": "graph_outline",
                        "args": {"subject_id": "actor_G0016"},
                        "id": "call-1",
                    }
                ]
            )
        ),
        ledger=ledger,
        deadline=None,
    )

    turn = adapter.run_turn(state)

    assert turn.observations[0].tool_name == "graph_outline"
    assert turn.observations[0].status == "ok"
    assert ledger.outlines == {}
    assert turn.observations[0].structured_payload["graph_outline"]["entity_id"] == "actor_G0016"

    apply_observation_to_state(state, turn.observations[0])

    assert ledger.outlines == {"actor_G0016": outline}
    assert state.observations[0].ledger_delta["added_outline_ids"] == ["actor_G0016"]
    assert state.events[0].metadata["ledger_delta"]["added_outline_ids"] == ["actor_G0016"]


def test_retrieve_replays_ledger_update_from_runtime_observation() -> None:
    query_result = _qr_with_chunk("APT29")
    ledger = EvidenceLedger()
    state = RuntimeInvestigationState(ledger)
    adapter = RuntimeTurnAdapter(
        settings=_runtime_settings(),
        query="What does APT29 use?",
        history=None,
        run_retrieve=lambda q, k: query_result,
        fact_store=None,
        ontology_nodes=[],
        chat_model=_FakeChatModel(
            _FakeAI(
                [
                    {
                        "name": "retrieve",
                        "args": {"query": "APT29", "top_k": 3},
                        "id": "call-1",
                    }
                ]
            )
        ),
        ledger=ledger,
        deadline=None,
    )

    turn = adapter.run_turn(state)

    assert turn.observations[0].tool_name == "retrieve"
    assert turn.observations[0].status == "ok"
    assert ledger.chunks == {}
    assert (
        turn.observations[0].structured_payload["retrieve"]["query_result"]["results"][0][
            "document"
        ]["id"]
        == "chunk-1"
    )

    apply_observation_to_state(state, turn.observations[0])

    assert set(ledger.chunks) == {"chunk-1"}
    assert state.observations[0].ledger_delta["added_chunk_ids"] == ["chunk-1"]
    assert state.events[0].metadata["ledger_delta"]["added_chunk_ids"] == ["chunk-1"]


def test_graph_query_replays_ledger_update_from_runtime_observation() -> None:
    row = _fact_row("fact-1")

    class FakeFactStore:
        def graph_query(
            self,
            *,
            subject_id: str,
            predicate: str | None = None,
            object_type: str | None = None,
            min_credibility: float = 0.0,
        ) -> tuple[FactRow, ...]:
            assert subject_id == "actor_G0016"
            assert predicate == "uses"
            assert object_type == "technique"
            assert min_credibility == 0.0
            return (row,)

    ledger = EvidenceLedger()
    state = RuntimeInvestigationState(ledger)
    adapter = RuntimeTurnAdapter(
        settings=_runtime_settings(),
        query="What techniques does APT29 use?",
        history=None,
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=FakeFactStore(),
        ontology_nodes=[],
        chat_model=_FakeChatModel(
            _FakeAI(
                [
                    {
                        "name": "graph_query",
                        "args": {
                            "subject_id": "actor_G0016",
                            "predicate": "uses",
                            "object_type": "technique",
                        },
                        "id": "call-1",
                    }
                ]
            )
        ),
        ledger=ledger,
        deadline=None,
    )

    turn = adapter.run_turn(state)

    assert turn.observations[0].tool_name == "graph_query"
    assert turn.observations[0].status == "ok"
    assert ledger.facts == {}
    assert turn.observations[0].structured_payload["graph_query"]["facts"][0]["fact_id"] == "fact-1"

    apply_observation_to_state(state, turn.observations[0])

    assert set(ledger.facts) == {"fact-1"}
    assert state.observations[0].ledger_delta["added_fact_ids"] == ["fact-1"]
    assert state.events[0].metadata["ledger_delta"]["added_fact_ids"] == ["fact-1"]


def test_facts_for_evidence_replays_ledger_update_from_runtime_observation() -> None:
    row = _fact_row("fact-from-chunk")

    class FakeFactStore:
        def facts_for_evidence(self, evidence_id: str) -> tuple[FactRow, ...]:
            assert evidence_id == "chunk-1"
            return (row,)

    ledger = EvidenceLedger()
    state = RuntimeInvestigationState(ledger)
    adapter = RuntimeTurnAdapter(
        settings=_runtime_settings(),
        query="Which facts does this evidence support?",
        history=None,
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=FakeFactStore(),
        ontology_nodes=[],
        chat_model=_FakeChatModel(
            _FakeAI(
                [
                    {
                        "name": "facts_for_evidence",
                        "args": {"chunk_id": "chunk-1"},
                        "id": "call-1",
                    }
                ]
            )
        ),
        ledger=ledger,
        deadline=None,
    )

    turn = adapter.run_turn(state)

    assert turn.observations[0].tool_name == "facts_for_evidence"
    assert turn.observations[0].status == "ok"
    assert ledger.facts == {}
    assert (
        turn.observations[0].structured_payload["facts_for_evidence"]["facts"][0]["fact_id"]
        == "fact-from-chunk"
    )

    apply_observation_to_state(state, turn.observations[0])

    assert set(ledger.facts) == {"fact-from-chunk"}
    assert state.observations[0].ledger_delta["added_fact_ids"] == ["fact-from-chunk"]
    assert state.events[0].metadata["ledger_delta"]["added_fact_ids"] == ["fact-from-chunk"]


def test_recorded_evidence_observations_replay_without_text_fields_and_citation_guard() -> None:
    from rag_cti.knowledge import agentic_nodes

    outline = GraphOutline(
        entity_id="actor_G0016",
        entity_name="APT29",
        entity_type="actor",
        outgoing=(
            OutlineEntry(
                predicate="uses",
                other_type="technique",
                count=1,
                max_credibility=1.0,
            ),
        ),
    )
    row = _fact_row("fact-1")
    query_result = _qr_with_chunk("APT29", "chunk-1")

    class FakeFactStore:
        def graph_outline(self, entity_id: str) -> GraphOutline | None:
            assert entity_id == "actor_G0016"
            return outline

        def graph_query(
            self,
            *,
            subject_id: str,
            predicate: str | None = None,
            object_type: str | None = None,
            min_credibility: float = 0.0,
        ) -> tuple[FactRow, ...]:
            assert subject_id == "actor_G0016"
            assert predicate == "uses"
            assert object_type == "technique"
            assert min_credibility == 0.0
            return (row,)

    production_ledger = EvidenceLedger()
    production_state = RuntimeInvestigationState(production_ledger)
    adapter = RuntimeTurnAdapter(
        settings=_runtime_settings(),
        query="What techniques does APT29 use?",
        history=None,
        run_retrieve=lambda q, k: query_result,
        fact_store=FakeFactStore(),
        ontology_nodes=[],
        chat_model=_FakeChatModel(
            _FakeAI(
                [
                    {
                        "name": "graph_outline",
                        "args": {"subject_id": "actor_G0016"},
                        "id": "call-1",
                    },
                    {
                        "name": "graph_query",
                        "args": {
                            "subject_id": "actor_G0016",
                            "predicate": "uses",
                            "object_type": "technique",
                        },
                        "id": "call-2",
                    },
                    {
                        "name": "retrieve",
                        "args": {"query": "APT29", "top_k": 3},
                        "id": "call-3",
                    },
                ]
            )
        ),
        ledger=production_ledger,
        deadline=None,
    )

    turn = adapter.run_turn(production_state)
    recorded = [
        replace(
            observation,
            args_summary="wrong=replay must not read this",
            result_summary="truncated display text",
            model_visible_content="provider protocol text is not replay state",
        )
        for observation in turn.observations
    ]
    replay_state = RuntimeInvestigationState(EvidenceLedger())

    for observation in recorded:
        apply_observation_to_state(replay_state, observation)

    assert replay_state.ledger.outlines == {"actor_G0016": outline}
    assert set(replay_state.ledger.facts) == {"fact-1"}
    assert set(replay_state.ledger.chunks) == {"chunk-1"}
    assert [(action.name, action.args) for action in replay_state.ledger.actions] == [
        ("graph_outline", "subject_id=actor_G0016"),
        ("graph_query", "object_type=technique, predicate=uses, subject_id=actor_G0016"),
        ("retrieve", "query=APT29, top_k=3"),
    ]
    assert agentic_nodes.assemble_citations(
        "APT29 uses phishing [fact-1] with prose support [chunk-1] [bogus].",
        replay_state.ledger,
    ) == (("fact-1", "chunk-1"), 1)
    assert "retrieve(query=APT29, top_k=3)" in agentic_nodes.render_action_log(replay_state.ledger)


def test_duplicate_migrated_observation_replay_is_idempotent() -> None:
    observation = RuntimeObservation(
        observation_id="obs1",
        turn_index=1,
        action_id="a1",
        tool_name="retrieve",
        args_summary="query=wrong",
        status="ok",
        result_summary="display text",
        model_visible_content="protocol text",
        structured_payload={
            "action": {"tool_name": "retrieve", "args": {"query": "APT29", "top_k": 3}},
            "retrieve": {
                "query_result": _qr_with_chunk("APT29", "chunk-1").model_dump(mode="python")
            },
        },
    )
    state = RuntimeInvestigationState(EvidenceLedger())

    apply_observation_to_state(state, observation)
    apply_observation_to_state(state, observation)

    assert set(state.ledger.chunks) == {"chunk-1"}
    assert [(action.name, action.args) for action in state.ledger.actions] == [
        ("retrieve", "query=APT29, top_k=3")
    ]
    assert state.observations[1].ledger_delta == {
        "added_chunk_ids": [],
        "added_fact_ids": [],
        "added_outline_ids": [],
        "actions_added": 0,
    }


def test_graph_outline_reducer_preserves_answer_shape_and_citation_guard(
    monkeypatch: Any,
) -> None:
    from rag_cti.knowledge import agentic_nodes

    outline = GraphOutline(
        entity_id="actor_G0016",
        entity_name="APT29",
        entity_type="actor",
        outgoing=(
            OutlineEntry(
                predicate="uses",
                other_type="technique",
                count=2,
                max_credibility=1.0,
            ),
        ),
    )

    class FakeFactStore:
        def graph_outline(self, entity_id: str) -> GraphOutline | None:
            assert entity_id == "actor_G0016"
            return outline

    class FakeGenerator:
        seen_total_retrieved = -1

        def generate(
            self,
            query: str,
            query_result: QueryResult,
            raise_on_failure: bool = False,
            system_prompt: str | None = None,
        ) -> GeneratedAnswer:
            self.seen_total_retrieved = query_result.total_retrieved
            return GeneratedAnswer(
                query=query,
                answer="APT29 has graph coverage [actor_G0016].",
                cited_chunk_ids=["actor_G0016"],
                query_result=query_result,
                generation_ms=0.0,
                model="fake",
            )

    generator = FakeGenerator()
    monkeypatch.setattr(agentic_nodes, "decide_next", lambda *a, **k: ("synthesize", "sufficient"))

    answer = run_agentic_investigation(
        "What techniques does APT29 use?",
        settings=SimpleNamespace(
            **_runtime_settings().__dict__,
            agentic_max_wall_seconds=0.0,
            agentic_max_iterations=3,
            agentic_token_ceiling=100,
            agentic_max_retrieve_rounds=2,
            agentic_open_cat_stall_limit=0,
            agentic_synthesis_top_k=5,
            agentic_synthesis_fact_limit=5,
        ),
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=FakeFactStore(),
        ontology_nodes=[],
        generator=generator,
        chat_model=_FakeChatModel(
            _FakeAI(
                [
                    {
                        "name": "graph_outline",
                        "args": {"subject_id": "actor_G0016"},
                        "id": "call-1",
                    }
                ]
            )
        ),
        judge=lambda s, u: '{"sufficient": false, "next_action": "retrieve_more"}',
    )

    assert answer.query_result.total_retrieved == 0
    assert answer.collected_facts == ()
    assert answer.cited_ids == ()
    assert answer.dropped_citation_count == 1
    assert answer.tool_call_count == 1
    assert answer.stop_reason == "sufficient"
    assert generator.seen_total_retrieved == 0


def test_recorded_graph_outline_observation_replays_without_text_fields() -> None:
    outline = GraphOutline(
        entity_id="actor_G0016",
        entity_name="APT29",
        entity_type="actor",
        outgoing=(
            OutlineEntry(
                predicate="uses",
                other_type="technique",
                count=2,
                max_credibility=1.0,
            ),
        ),
    )

    class FakeFactStore:
        def graph_outline(self, entity_id: str) -> GraphOutline | None:
            assert entity_id == "actor_G0016"
            return outline

    production_ledger = EvidenceLedger()
    production_state = RuntimeInvestigationState(production_ledger)
    adapter = RuntimeTurnAdapter(
        settings=_runtime_settings(),
        query="What techniques does APT29 use?",
        history=None,
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=FakeFactStore(),
        ontology_nodes=[],
        chat_model=_FakeChatModel(
            _FakeAI(
                [
                    {
                        "name": "graph_outline",
                        "args": {"subject_id": "actor_G0016"},
                        "id": "call-1",
                    }
                ]
            )
        ),
        ledger=production_ledger,
        deadline=None,
    )

    turn = adapter.run_turn(production_state)
    recorded = replace(
        turn.observations[0],
        args_summary="subject_id=wrong",
        result_summary="truncated display text",
        model_visible_content="provider protocol text is not replay state",
    )
    replay_state = RuntimeInvestigationState(EvidenceLedger())

    apply_observation_to_state(replay_state, recorded)

    assert replay_state.ledger.outlines == {"actor_G0016": outline}
    assert [(action.name, action.args) for action in replay_state.ledger.actions] == [
        ("graph_outline", "subject_id=actor_G0016")
    ]
    assert replay_state.observations[0].ledger_delta == {
        "added_chunk_ids": [],
        "added_fact_ids": [],
        "added_outline_ids": ["actor_G0016"],
        "actions_added": 1,
    }


def test_parallel_graph_outline_replay_keeps_per_observation_deltas_atomic() -> None:
    import threading

    outlines = {
        "actor_G0016": GraphOutline(
            entity_id="actor_G0016",
            entity_name="APT29",
            entity_type="actor",
            outgoing=(
                OutlineEntry(
                    predicate="uses",
                    other_type="technique",
                    count=2,
                    max_credibility=1.0,
                ),
            ),
        ),
        "actor_G0032": GraphOutline(
            entity_id="actor_G0032",
            entity_name="Lazarus Group",
            entity_type="actor",
            outgoing=(
                OutlineEntry(
                    predicate="uses",
                    other_type="technique",
                    count=3,
                    max_credibility=1.0,
                ),
            ),
        ),
    }
    barrier = threading.Barrier(2, timeout=5.0)

    class FakeFactStore:
        def graph_outline(self, entity_id: str) -> GraphOutline | None:
            barrier.wait()
            return outlines[entity_id]

    settings = _runtime_settings()
    settings.agentic_parallel_dispatch_enabled = True
    settings.agentic_max_parallel_tools = 2
    production_ledger = EvidenceLedger()
    production_state = RuntimeInvestigationState(production_ledger)
    adapter = RuntimeTurnAdapter(
        settings=settings,
        query="Compare APT29 and Lazarus Group techniques.",
        history=None,
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=FakeFactStore(),
        ontology_nodes=[],
        chat_model=_FakeChatModel(
            _FakeAI(
                [
                    {
                        "name": "graph_outline",
                        "args": {"subject_id": "actor_G0016"},
                        "id": "call-1",
                    },
                    {
                        "name": "graph_outline",
                        "args": {"subject_id": "actor_G0032"},
                        "id": "call-2",
                    },
                ]
            )
        ),
        ledger=production_ledger,
        deadline=None,
    )

    turn = adapter.run_turn(production_state)
    raw_deltas_by_entity = {
        observation.structured_payload["graph_outline"]["entity_id"]: observation.ledger_delta
        for observation in turn.observations
    }
    assert raw_deltas_by_entity == {
        "actor_G0016": {
            "added_chunk_ids": [],
            "added_fact_ids": [],
            "added_outline_ids": [],
            "actions_added": 0,
        },
        "actor_G0032": {
            "added_chunk_ids": [],
            "added_fact_ids": [],
            "added_outline_ids": [],
            "actions_added": 0,
        },
    }
    assert {
        event.metadata["args_summary"]: event.metadata["ledger_delta"] for event in turn.events
    } == {
        "subject_id=actor_G0016": {
            "added_chunk_ids": [],
            "added_fact_ids": [],
            "added_outline_ids": [],
            "actions_added": 0,
        },
        "subject_id=actor_G0032": {
            "added_chunk_ids": [],
            "added_fact_ids": [],
            "added_outline_ids": [],
            "actions_added": 0,
        },
    }
    replay_state = RuntimeInvestigationState(EvidenceLedger())
    applied_events = [
        apply_observation_to_state(replay_state, observation) for observation in turn.observations
    ]

    assert set(replay_state.ledger.outlines) == {"actor_G0016", "actor_G0032"}
    assert len(replay_state.ledger.actions) == 2
    deltas_by_entity = {
        observation.structured_payload["graph_outline"]["entity_id"]: observation.ledger_delta
        for observation in replay_state.observations
    }
    assert deltas_by_entity == {
        "actor_G0016": {
            "added_chunk_ids": [],
            "added_fact_ids": [],
            "added_outline_ids": ["actor_G0016"],
            "actions_added": 1,
        },
        "actor_G0032": {
            "added_chunk_ids": [],
            "added_fact_ids": [],
            "added_outline_ids": ["actor_G0032"],
            "actions_added": 1,
        },
    }
    assert {
        event.metadata["args_summary"]: event.metadata["ledger_delta"] for event in applied_events
    } == {
        "subject_id=actor_G0016": deltas_by_entity["actor_G0016"],
        "subject_id=actor_G0032": deltas_by_entity["actor_G0032"],
    }


def test_parallel_retrieve_replay_keeps_per_observation_deltas_atomic() -> None:
    import threading

    chunk_ids = {"APT29": "chunk-apt29", "Turla": "chunk-turla"}
    barrier = threading.Barrier(2, timeout=5.0)

    def synchronized_retrieve(query: str, top_k: int) -> QueryResult:
        assert top_k == 3
        barrier.wait()
        return _qr_with_chunk(query, chunk_ids[query])

    settings = _runtime_settings()
    settings.agentic_parallel_dispatch_enabled = True
    settings.agentic_max_parallel_tools = 2
    production_ledger = EvidenceLedger()
    production_state = RuntimeInvestigationState(production_ledger)
    adapter = RuntimeTurnAdapter(
        settings=settings,
        query="Compare APT29 and Turla.",
        history=None,
        run_retrieve=synchronized_retrieve,
        fact_store=None,
        ontology_nodes=[],
        chat_model=_FakeChatModel(
            _FakeAI(
                [
                    {
                        "name": "retrieve",
                        "args": {"query": "APT29", "top_k": 3},
                        "id": "call-1",
                    },
                    {
                        "name": "retrieve",
                        "args": {"query": "Turla", "top_k": 3},
                        "id": "call-2",
                    },
                ]
            )
        ),
        ledger=production_ledger,
        deadline=None,
    )

    turn = adapter.run_turn(production_state)
    raw_deltas_by_query = {
        observation.structured_payload["action"]["args"]["query"]: observation.ledger_delta
        for observation in turn.observations
    }
    assert raw_deltas_by_query == {
        "APT29": {
            "added_chunk_ids": [],
            "added_fact_ids": [],
            "added_outline_ids": [],
            "actions_added": 0,
        },
        "Turla": {
            "added_chunk_ids": [],
            "added_fact_ids": [],
            "added_outline_ids": [],
            "actions_added": 0,
        },
    }

    replay_state = RuntimeInvestigationState(EvidenceLedger())
    applied_events = [
        apply_observation_to_state(replay_state, observation) for observation in turn.observations
    ]

    assert set(replay_state.ledger.chunks) == {"chunk-apt29", "chunk-turla"}
    deltas_by_query = {
        observation.structured_payload["action"]["args"]["query"]: observation.ledger_delta
        for observation in replay_state.observations
    }
    assert deltas_by_query == {
        "APT29": {
            "added_chunk_ids": ["chunk-apt29"],
            "added_fact_ids": [],
            "added_outline_ids": [],
            "actions_added": 1,
        },
        "Turla": {
            "added_chunk_ids": ["chunk-turla"],
            "added_fact_ids": [],
            "added_outline_ids": [],
            "actions_added": 1,
        },
    }
    assert {
        event.metadata["args_summary"]: event.metadata["ledger_delta"] for event in applied_events
    } == {
        "query=APT29, top_k=3": deltas_by_query["APT29"],
        "query=Turla, top_k=3": deltas_by_query["Turla"],
    }


def test_runtime_loop_calls_stop_policy_with_turn_accounting(monkeypatch: Any) -> None:
    import rag_cti.runtime_harness as harness
    from rag_cti.knowledge import agentic_nodes

    class FakeAdapter:
        _hard_tool_budget = 4

        def __init__(self, **_kwargs: Any) -> None:
            pass

        def run_turn(self, _state: RuntimeInvestigationState) -> RuntimeTurnResult:
            return RuntimeTurnResult(
                messages=[],
                tokens_used=11,
                new_evidence=5,
                new_facts=2,
            )

    class FakeGenerator:
        def generate(
            self,
            query: str,
            query_result: QueryResult,
            raise_on_failure: bool = False,
            system_prompt: str | None = None,
        ) -> GeneratedAnswer:
            return GeneratedAnswer(
                query=query,
                answer="answer",
                cited_chunk_ids=[],
                query_result=query_result,
                generation_ms=0.0,
                model="fake",
            )

    seen: dict[str, int] = {}

    def decide_next(
        _verdict: Any,
        iteration_count: int,
        tokens_used: int,
        new_evidence: int,
        **kwargs: Any,
    ) -> tuple[str, str]:
        seen["iteration_count"] = iteration_count
        seen["tokens_used"] = tokens_used
        seen["new_evidence"] = new_evidence
        seen["new_facts"] = kwargs["new_facts"]
        return "synthesize", "runtime_stop"

    monkeypatch.setattr(harness, "RuntimeTurnAdapter", FakeAdapter)
    monkeypatch.setattr(agentic_nodes, "decide_next", decide_next)

    answer = run_agentic_investigation(
        "q",
        settings=SimpleNamespace(
            agentic_max_wall_seconds=0.0,
            agentic_max_iterations=3,
            agentic_token_ceiling=100,
            agentic_max_retrieve_rounds=2,
            agentic_open_cat_stall_limit=0,
            agentic_synthesis_top_k=5,
            agentic_synthesis_fact_limit=5,
        ),
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=None,
        ontology_nodes=[],
        generator=FakeGenerator(),
        chat_model=object(),
        judge=lambda s, u: '{"sufficient": false, "next_action": "retrieve_more"}',
    )

    assert answer.stop_reason == "runtime_stop"
    assert seen == {
        "iteration_count": 1,
        "tokens_used": 11,
        "new_evidence": 5,
        "new_facts": 2,
    }


def test_runtime_loop_continues_after_resolve_entity_setup_only_turn(monkeypatch: Any) -> None:
    import rag_cti.runtime_harness as harness

    class FakeAdapter:
        _hard_tool_budget = 4

        def __init__(self, **_kwargs: Any) -> None:
            self.turns = 0

        def run_turn(self, state: RuntimeInvestigationState) -> RuntimeTurnResult:
            self.turns += 1
            if self.turns == 1:
                observation = RuntimeObservation(
                    observation_id="turn-1-observation-1",
                    turn_index=1,
                    action_id="turn-1-action-1",
                    tool_name="resolve_entity",
                    args_summary='{"name":"APT29"}',
                    status="ok",
                    result_summary='[{"name":"APT29","entity_id":"intrusion-set--apt29"}]',
                    ledger_delta={
                        "added_chunk_ids": [],
                        "added_fact_ids": [],
                        "added_outline_ids": [],
                        "actions_added": 1,
                    },
                    model_visible_content='[{"name":"APT29","entity_id":"intrusion-set--apt29"}]',
                    event_metadata={"duplicate": False},
                )
                return RuntimeTurnResult(
                    messages=[],
                    tokens_used=3,
                    new_evidence=0,
                    new_facts=0,
                    observations=(observation,),
                    events=(RuntimeEvent.from_observation(observation),),
                    proposals=(
                        RuntimeActionProposal(
                            action_id="turn-1-action-1",
                            turn_index=1,
                            tool_call_id="call-1",
                            tool_name="resolve_entity",
                            args={"name": "APT29"},
                        ),
                    ),
                )
            return RuntimeTurnResult(
                messages=[],
                tokens_used=2,
                new_evidence=0,
                new_facts=0,
                observations=(
                    RuntimeObservation(
                        observation_id="turn-2-observation-1",
                        turn_index=2,
                        action_id="",
                        tool_name="",
                        args_summary="",
                        status="no_action",
                    ),
                ),
            )

    class FakeGenerator:
        def generate(
            self,
            query: str,
            query_result: QueryResult,
            raise_on_failure: bool = False,
            system_prompt: str | None = None,
        ) -> GeneratedAnswer:
            return GeneratedAnswer(
                query=query,
                answer="answer",
                cited_chunk_ids=[],
                query_result=query_result,
                generation_ms=0.0,
                model="fake",
            )

    monkeypatch.setattr(harness, "RuntimeTurnAdapter", FakeAdapter)

    answer = run_agentic_investigation(
        "Compare APT29 and Lazarus techniques.",
        settings=SimpleNamespace(
            agentic_max_wall_seconds=0.0,
            agentic_max_iterations=3,
            agentic_token_ceiling=100,
            agentic_max_retrieve_rounds=2,
            agentic_open_cat_stall_limit=0,
            agentic_synthesis_top_k=5,
            agentic_synthesis_fact_limit=5,
        ),
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=None,
        ontology_nodes=[],
        generator=FakeGenerator(),
        chat_model=object(),
        judge=lambda s, u: '{"sufficient": false, "next_action": "retrieve_more"}',
    )

    assert answer.iteration_count == 2
    assert answer.stop_reason == "no_progress"


def test_runtime_turn_exposes_resolved_entity_ids_to_next_real_turn(monkeypatch: Any) -> None:
    from rag_cti.knowledge import agent_tools, agentic_nodes

    class InspectingBoundModel:
        def __init__(self) -> None:
            self.inputs: list[list[Any]] = []

        def invoke(self, messages: list[Any]) -> _FakeAI:
            self.inputs.append(messages)
            if len(self.inputs) == 1:
                return _FakeAI(
                    [
                        {"name": "resolve_entity", "args": {"name": "APT29"}, "id": "c1"},
                        {
                            "name": "resolve_entity",
                            "args": {"name": "Lazarus Group"},
                            "id": "c2",
                        },
                    ]
                )
            rendered = "\n".join(str(message) for message in messages)
            if "actor_G0016" in rendered and "actor_G0032" in rendered:
                return _FakeAI(
                    [
                        {
                            "name": "graph_outline",
                            "args": {"subject_id": "actor_G0016"},
                            "id": "c3",
                        },
                        {
                            "name": "graph_outline",
                            "args": {"subject_id": "actor_G0032"},
                            "id": "c4",
                        },
                    ]
                )
            return _FakeAI(
                [
                    {"name": "resolve_entity", "args": {"name": "APT29"}, "id": "c3"},
                    {
                        "name": "resolve_entity",
                        "args": {"name": "Lazarus Group"},
                        "id": "c4",
                    },
                ]
            )

    class InspectingChatModel:
        def __init__(self) -> None:
            self.bound = InspectingBoundModel()

        def bind_tools(self, _tools: list[Any]) -> InspectingBoundModel:
            return self.bound

    def resolve_entity(name: str, _ontology_nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
        return {
            "APT29": [{"entity_id": "actor_G0016", "matched_type": "actor"}],
            "Lazarus Group": [{"entity_id": "actor_G0032", "matched_type": "actor"}],
        }.get(name, [])

    def outline_to_ledger(
        _fact_store: object, ledger: EvidenceLedger, subject_id: str
    ) -> dict[str, Any]:
        outline = GraphOutline(
            entity_id=subject_id,
            entity_name={"actor_G0016": "APT29", "actor_G0032": "Lazarus Group"}[subject_id],
            entity_type="actor",
            outgoing=(
                OutlineEntry(
                    predicate="uses", other_type="technique", count=1, max_credibility=1.0
                ),
            ),
        )
        ledger.add_outline(outline)
        return {"found": True, "entity_id": subject_id}

    monkeypatch.setattr(agent_tools, "resolve_entity_candidates", resolve_entity)
    monkeypatch.setattr(agent_tools, "outline_to_ledger", outline_to_ledger)

    ledger = EvidenceLedger()
    state = RuntimeInvestigationState(ledger)
    chat_model = InspectingChatModel()
    adapter = RuntimeTurnAdapter(
        settings=_runtime_settings(),
        query="What techniques do both APT29 and Lazarus Group use?",
        history=None,
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=object(),
        ontology_nodes=[],
        chat_model=chat_model,
        ledger=ledger,
        deadline=None,
    )

    first = adapter.run_turn(state)
    state.messages = first.messages
    state.iteration_count += 1
    state.sufficiency = agentic_nodes.parse_verdict(
        '{"sufficient": false, "next_action": "retrieve_more", '
        '"coverage_gaps": ["need shared techniques"]}'
    )
    for observation in first.observations:
        apply_observation_to_state(state, observation)

    second = adapter.run_turn(state)

    assert [proposal.tool_name for proposal in second.proposals] == [
        "graph_outline",
        "graph_outline",
    ]


def test_resolved_entity_setup_state_uses_structured_payload_not_result_text(
    monkeypatch: Any,
) -> None:
    from rag_cti.knowledge import agent_tools, agentic_nodes

    class InspectingBoundModel:
        def __init__(self) -> None:
            self.inputs: list[list[Any]] = []

        def invoke(self, messages: list[Any]) -> _FakeAI:
            self.inputs.append(messages)
            if len(self.inputs) == 1:
                return _FakeAI([{"name": "resolve_entity", "args": {"name": "APT29"}, "id": "c1"}])
            return _FakeAI([])

    class InspectingChatModel:
        def __init__(self) -> None:
            self.bound = InspectingBoundModel()

        def bind_tools(self, _tools: list[Any]) -> InspectingBoundModel:
            return self.bound

    monkeypatch.setattr(
        agent_tools,
        "resolve_entity_candidates",
        lambda name, _ontology_nodes: (
            [{"entity_id": "actor_G0016", "matched_type": "actor"}] if name == "APT29" else []
        ),
    )

    ledger = EvidenceLedger()
    state = RuntimeInvestigationState(ledger)
    chat_model = InspectingChatModel()
    adapter = RuntimeTurnAdapter(
        settings=_runtime_settings(),
        query="What techniques does APT29 use?",
        history=None,
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=object(),
        ontology_nodes=[],
        chat_model=chat_model,
        ledger=ledger,
        deadline=None,
    )

    first = adapter.run_turn(state)
    state.messages = first.messages
    state.iteration_count += 1
    state.sufficiency = agentic_nodes.parse_verdict(
        '{"sufficient": false, "next_action": "retrieve_more"}'
    )
    recorded = replace(
        first.observations[0],
        args_summary="name=Wrong",
        result_summary="display text is unavailable",
        model_visible_content="provider protocol text is unavailable",
    )
    apply_observation_to_state(state, recorded)

    adapter.run_turn(state)

    rendered = "\n".join(str(message) for message in chat_model.bound.inputs[-1])
    assert "APT29 -> actor_G0016 (actor)" in rendered


def test_runtime_loop_does_not_count_empty_resolve_as_setup_progress(monkeypatch: Any) -> None:
    from rag_cti.knowledge import agent_tools

    class SequenceBoundModel:
        def __init__(self) -> None:
            self.turns = [
                _FakeAI(
                    [{"name": "resolve_entity", "args": {"name": "Unknown Actor"}, "id": "c1"}]
                ),
                _FakeAI([]),
            ]

        def invoke(self, _messages: list[Any]) -> _FakeAI:
            return self.turns.pop(0)

    class SequenceChatModel:
        def __init__(self) -> None:
            self.bound = SequenceBoundModel()

        def bind_tools(self, _tools: list[Any]) -> SequenceBoundModel:
            return self.bound

    class FakeGenerator:
        def generate(
            self,
            query: str,
            query_result: QueryResult,
            raise_on_failure: bool = False,
            system_prompt: str | None = None,
        ) -> GeneratedAnswer:
            return GeneratedAnswer(
                query=query,
                answer="answer",
                cited_chunk_ids=[],
                query_result=query_result,
                generation_ms=0.0,
                model="fake",
            )

    monkeypatch.setattr(
        agent_tools,
        "resolve_entity_candidates",
        lambda _name, _ontology_nodes: [],
    )

    answer = run_agentic_investigation(
        "What techniques does Unknown Actor use?",
        settings=SimpleNamespace(
            **_runtime_settings().__dict__,
            agentic_max_wall_seconds=0.0,
            agentic_max_iterations=3,
            agentic_token_ceiling=100,
            agentic_max_retrieve_rounds=2,
            agentic_open_cat_stall_limit=0,
            agentic_synthesis_top_k=5,
            agentic_synthesis_fact_limit=5,
        ),
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=object(),
        ontology_nodes=[],
        generator=FakeGenerator(),
        chat_model=SequenceChatModel(),
        judge=lambda s, u: '{"sufficient": false, "next_action": "retrieve_more"}',
    )

    assert answer.iteration_count == 1
    assert answer.tool_call_count == 1
    assert answer.stop_reason == "no_progress"


def test_fallback_understanding_uses_single_agent() -> None:
    assert admit_supervisor(_understanding(status="fallback"), max_branches=4) == "single_agent"


def test_simple_query_uses_single_agent() -> None:
    assert admit_supervisor(_understanding(), max_branches=4) == "single_agent"


def test_independent_comparison_admits_supervisor() -> None:
    understanding = _understanding(
        decomposition=_proposal(_branch("b1", "APT29"), _branch("b2", "Turla"))
    )
    assert admit_supervisor(understanding, max_branches=4) == "supervisor"
    admission = evaluate_supervisor_admission(understanding, max_branches=4)
    assert admission.reason == "validated_independent_branches"
    assert [b.branch_id for b in admission.branches] == ["b1", "b2"]


def test_dependent_multihop_rejects_supervisor() -> None:
    proposal = DecompositionProposal(
        branches=(_branch("b1", "APT29"), _branch("b2", "Malware C2")),
        suitable_for_supervisor=True,
        dependency_reason="second branch depends on malware found by first branch",
    )
    assert (
        admit_supervisor(_understanding(decomposition=proposal), max_branches=4) == "single_agent"
    )


def test_retrieval_subqueries_are_not_supervisor_branches() -> None:
    proposal = _proposal(
        ProposedBranch(
            branch_id="b1",
            sub_question="query a",
            independent_reason="retrieval hint",
        ),
        ProposedBranch(
            branch_id="b2",
            sub_question="query b",
            independent_reason="retrieval hint",
        ),
    )
    understanding = _understanding(
        retrieval_queries=("query a", "query b"),
        decomposition=proposal,
    )
    assert admit_supervisor(understanding, max_branches=4) == "single_agent"


def test_payload_constraint_does_not_affect_admission() -> None:
    constrained = _understanding(
        payload_constraint=PayloadConstraint(attack_ids=("T1059",)),
        decomposition=_proposal(_branch("b1", "APT29"), _branch("b2", "Turla")),
    )
    unconstrained = _understanding(
        payload_constraint=None,
        decomposition=_proposal(_branch("b1", "APT29"), _branch("b2", "Turla")),
    )
    assert admit_supervisor(constrained, max_branches=4) == admit_supervisor(
        unconstrained,
        max_branches=4,
    )


def test_unclear_branch_boundaries_reject_supervisor() -> None:
    proposal = _proposal(
        ProposedBranch(branch_id="b1", sub_question="first thing", independent_reason="vague"),
        ProposedBranch(branch_id="b2", sub_question="second thing", independent_reason="vague"),
    )
    admission = evaluate_supervisor_admission(
        _understanding(decomposition=proposal),
        max_branches=4,
    )
    assert admission == "single_agent"
    assert admission.reason == "fewer_than_two_valid_branches"


def test_runtime_understanding_parses_explicit_decomposition() -> None:
    rewriter = _FakeRewriter(
        rewrite_output=RewriteOutput(
            queries=("retrieval hint APT29", "retrieval hint Turla"),
            entities=(ExtractedEntity("APT29", "actor"), ExtractedEntity("Turla", "actor")),
        ),
        runtime_raw=(
            '{"standalone_query": "Compare APT29 and Turla",'
            '"retrieval_queries": ["compare APT29 Turla"],'
            '"entities": [{"name": "APT29", "type": "actor"}, {"name": "Turla", "type": "actor"}],'
            '"decomposition": {'
            '"suitable_for_supervisor": true,'
            '"task_requires_composition": true,'
            '"dependency_reason": "",'
            '"reason": "explicit comparison",'
            '"branches": ['
            '{"branch_id": "apt29", "sub_question": "Gather APT29 evidence",'
            '"focus_entity": "APT29", "facet": "comparison",'
            '"independent_reason": "independent actor branch"},'
            '{"branch_id": "turla", "sub_question": "Gather Turla evidence",'
            '"focus_entity": "Turla", "facet": "comparison",'
            '"independent_reason": "independent actor branch"}'
            "]},"
            '"confidence": 0.8}'
        ),
    )

    understanding = build_runtime_query_understanding(
        "Compare APT29 and Turla",
        ["prior turn"],
        pipeline=_FakePipeline(rewriter),
        settings=SimpleNamespace(constraint_routing_enabled=False),
        ontology_nodes=[],
    )

    assert understanding.status == "ok"
    assert understanding.reason == "runtime_query_understanding"
    assert understanding.standalone_query == "Compare APT29 and Turla"
    assert understanding.retrieval_queries == ("compare APT29 Turla",)
    assert understanding.decomposition is not None
    assert [b.branch_id for b in understanding.decomposition.branches] == ["apt29", "turla"]
    assert evaluate_supervisor_admission(understanding, max_branches=4) == "supervisor"
    assert "prior turn" in rewriter.runtime_prompts[0][1]
    assert rewriter.max_tokens_seen == 1200


def test_runtime_understanding_parse_failure_does_not_use_comparison_heuristic() -> None:
    rewriter = _FakeRewriter(
        rewrite_output=RewriteOutput(
            queries=("Compare APT29 and Turla",),
            entities=(ExtractedEntity("APT29", "actor"), ExtractedEntity("Turla", "actor")),
        ),
        runtime_raw="not json",
    )

    understanding = build_runtime_query_understanding(
        "Compare APT29 and Turla",
        None,
        pipeline=_FakePipeline(rewriter),
        settings=SimpleNamespace(constraint_routing_enabled=False),
        ontology_nodes=[],
    )

    assert understanding.status == "parse_error"
    assert understanding.decomposition is None
    admission = evaluate_supervisor_admission(understanding, max_branches=4)
    assert admission == "single_agent"
    assert admission.reason == "runtime_understanding_parse_error"


def test_runtime_understanding_normalizes_independent_dependency_reason() -> None:
    rewriter = _FakeRewriter(
        rewrite_output=RewriteOutput(
            queries=("Compare APT29 and Turla",),
            entities=(ExtractedEntity("APT29", "actor"), ExtractedEntity("Turla", "actor")),
        ),
        runtime_raw=(
            '{"standalone_query": "Compare APT29 and Turla",'
            '"retrieval_queries": ["APT29 techniques", "Turla techniques"],'
            '"entities": [{"name": "APT29", "type": "actor"}, {"name": "Turla", "type": "actor"}],'
            '"decomposition": {'
            '"suitable_for_supervisor": true,'
            '"task_requires_composition": false,'
            '"dependency_reason": "independent facets",'
            '"reason": "explicit comparison",'
            '"branches": ['
            '{"branch_id": "apt29", "sub_question": "What techniques does APT29 use?",'
            '"focus_entity": "APT29", "facet": "techniques",'
            '"independent_reason": "independent actor branch"},'
            '{"branch_id": "turla", "sub_question": "What techniques does Turla use?",'
            '"focus_entity": "Turla", "facet": "techniques",'
            '"independent_reason": "independent actor branch"}'
            "]},"
            '"confidence": 0.8}'
        ),
    )

    understanding = build_runtime_query_understanding(
        "Compare APT29 and Turla",
        None,
        pipeline=_FakePipeline(rewriter),
        settings=SimpleNamespace(constraint_routing_enabled=False),
        ontology_nodes=[],
    )

    assert understanding.decomposition is not None
    assert understanding.decomposition.dependency_reason == ""
    assert understanding.decomposition.task_requires_composition is True
    admission = evaluate_supervisor_admission(understanding, max_branches=4)
    assert admission == "supervisor"


def test_answer_records_supervisor_disabled_reason_and_uses_agentic() -> None:
    import rag_cti

    understanding = _understanding(
        decomposition=_proposal(_branch("b1", "APT29"), _branch("b2", "Turla"))
    )
    with (
        patch.object(
            rag_cti,
            "_build_runtime_deps",
            return_value=_deps(understanding, supervisor_enabled=False),
        ),
        patch("rag_cti.observability.tracing.add_trace_metadata") as meta,
        patch.object(
            rag_cti, "run_agentic_investigation", return_value=_agentic_answer("q")
        ) as agentic,
        patch("rag_cti.knowledge.agentic_graph.run_agentic_answer") as legacy_agentic,
        patch("rag_cti.knowledge.supervisor_graph.run_supervised_answer") as supervised,
    ):
        ans = rag_cti.answer("q")

    assert ans.model == "agentic"
    assert agentic.called
    assert not legacy_agentic.called
    assert not supervised.called
    assert meta.call_args.kwargs["runtime_path"] == "single_agent"
    assert meta.call_args.kwargs["admission_reason"] == "supervisor_disabled"


def test_agentic_answer_uses_runtime_investigation() -> None:
    import rag_cti

    with (
        patch.object(
            rag_cti,
            "_build_runtime_deps",
            return_value=_deps(_understanding(), supervisor_enabled=False),
        ),
        patch.object(
            rag_cti, "run_agentic_investigation", return_value=_agentic_answer("q")
        ) as agentic,
        patch("rag_cti.knowledge.agentic_graph.run_agentic_answer") as legacy_agentic,
    ):
        ans = rag_cti.agentic_answer("q")

    assert ans.answer == "answer"
    assert agentic.called
    assert not legacy_agentic.called


def test_ask_reaches_runtime_investigation_through_agentic_answer() -> None:
    import rag_cti

    with (
        patch.object(
            rag_cti,
            "_build_runtime_deps",
            return_value=_deps(_understanding(), supervisor_enabled=False),
        ),
        patch.object(
            rag_cti, "run_agentic_investigation", return_value=_agentic_answer("q")
        ) as agentic,
        patch("rag_cti.knowledge.agentic_graph.run_agentic_answer") as legacy_agentic,
    ):
        text = rag_cti.ask("q")

    assert text == "answer"
    assert agentic.called
    assert not legacy_agentic.called


def test_answer_passes_validated_branch_plan_to_supervisor() -> None:
    import rag_cti

    understanding = _understanding(
        decomposition=_proposal(_branch("b1", "APT29"), _branch("b2", "Turla"))
    )
    supervised_answer = _agentic_answer("q").model_copy(
        update={"branch_count": 2, "decomposed": True}
    )
    with (
        patch.object(
            rag_cti,
            "_build_runtime_deps",
            return_value=_deps(understanding, supervisor_enabled=True),
        ),
        patch("rag_cti.observability.tracing.add_trace_metadata") as meta,
        patch.object(rag_cti, "run_agentic_investigation") as agentic,
        patch(
            "rag_cti.knowledge.supervisor_graph.run_supervised_answer",
            return_value=supervised_answer,
        ) as supervised,
    ):
        ans = rag_cti.answer("q")

    assert ans.model == "supervisor"
    assert not agentic.called
    assert supervised.call_args.kwargs["branch_plan"] == understanding.decomposition.branches
    assert meta.call_args.kwargs["runtime_path"] == "supervisor"
    assert meta.call_args.kwargs["admission_reason"] == "validated_independent_branches"


def test_answer_validated_branch_plan_does_not_run_supervisor_loop(monkeypatch: Any) -> None:
    import rag_cti
    from rag_cti.knowledge import supervisor_graph
    from rag_cti.knowledge.agentic_state import BranchReport, SubQuestion

    understanding = _understanding(
        decomposition=_proposal(_branch("b1", "APT29"), _branch("b2", "Turla"))
    )
    gathered: list[str] = []

    def gather(branch: SubQuestion, **_kwargs: Any) -> tuple[EvidenceLedger, BranchReport]:
        gathered.append(branch.branch_id)
        return EvidenceLedger(), BranchReport(
            branch_id=branch.branch_id,
            sub_question=branch.sub_question,
            focus_entity=branch.focus_entity,
            facet=branch.facet,
            status="empty",
            stop_reason="empty",
            iteration_count=1,
        )

    def fail_supervisor_loop(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("production answer must not enter autonomous supervisor loop")

    monkeypatch.setattr(supervisor_graph, "gather_branch", gather)
    monkeypatch.setattr(supervisor_graph, "run_supervisor_loop", fail_supervisor_loop)

    with patch.object(
        rag_cti,
        "_build_runtime_deps",
        return_value=_deps(understanding, supervisor_enabled=True),
    ):
        ans = rag_cti.answer("q")

    assert ans.model == "supervisor"
    assert sorted(gathered) == ["b1", "b2"]
