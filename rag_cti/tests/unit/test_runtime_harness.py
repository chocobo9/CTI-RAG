from __future__ import annotations

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
from rag_cti.types import GeneratedAnswer, PayloadConstraint, QueryResult


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
        settings=SimpleNamespace(supervisor_enabled=supervisor_enabled, supervisor_max_branches=4),
        retrieval_pipeline=object(),
        run_retrieve=lambda q, k: _empty_qr(q),
        fact_store=None,
        ontology_nodes=[],
        query_understanding=lambda q, h=None: understanding,
        gather_model=object(),
        generator=object(),
        judge=object(),
        composer=object(),
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
    result = _turn_adapter(
        _FakeAI([{"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"}]),
        ledger,
    ).run_turn(RuntimeInvestigationState(ledger))

    assert any(event.kind == "tool_result" for event in result.events)
    assert [action.name for action in ledger.actions] == ["retrieve"]


def test_runtime_turn_builds_observation_for_tool_result() -> None:
    ledger = EvidenceLedger()
    result = _turn_adapter(
        _FakeAI([{"name": "retrieve", "args": {"query": "APT29"}, "id": "t1"}]),
        ledger,
    ).run_turn(RuntimeInvestigationState(ledger))

    observation = result.observations[0]
    assert isinstance(observation, RuntimeObservation)
    assert observation.tool_name == "retrieve"
    assert observation.action_id
    assert observation.status == "ok"
    assert "APT29" in observation.args_summary
    assert observation.model_visible_content
    assert observation.ledger_delta["actions_added"] == 1
    assert result.events[0] == RuntimeEvent.from_observation(observation)


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


def test_fallback_understanding_uses_single_agent() -> None:
    assert admit_supervisor(_understanding(status="fallback"), max_branches=4) == "single_agent"


def test_simple_query_uses_single_agent() -> None:
    assert admit_supervisor(_understanding(), max_branches=4) == "single_agent"


def test_independent_comparison_admits_supervisor() -> None:
    understanding = _understanding(decomposition=_proposal(_branch("b1", "APT29"), _branch("b2", "Turla")))
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
    assert admit_supervisor(_understanding(decomposition=proposal), max_branches=4) == "single_agent"


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
            ']},'
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
            ']},'
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

    understanding = _understanding(decomposition=_proposal(_branch("b1", "APT29"), _branch("b2", "Turla")))
    with (
        patch.object(rag_cti, "_build_runtime_deps", return_value=_deps(understanding, supervisor_enabled=False)),
        patch("rag_cti.observability.tracing.add_trace_metadata") as meta,
        patch.object(rag_cti, "run_agentic_investigation", return_value=_agentic_answer("q")) as agentic,
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
        patch.object(rag_cti, "_build_runtime_deps", return_value=_deps(_understanding(), supervisor_enabled=False)),
        patch.object(rag_cti, "run_agentic_investigation", return_value=_agentic_answer("q")) as agentic,
        patch("rag_cti.knowledge.agentic_graph.run_agentic_answer") as legacy_agentic,
    ):
        ans = rag_cti.agentic_answer("q")

    assert ans.answer == "answer"
    assert agentic.called
    assert not legacy_agentic.called


def test_ask_reaches_runtime_investigation_through_agentic_answer() -> None:
    import rag_cti

    with (
        patch.object(rag_cti, "_build_runtime_deps", return_value=_deps(_understanding(), supervisor_enabled=False)),
        patch.object(rag_cti, "run_agentic_investigation", return_value=_agentic_answer("q")) as agentic,
        patch("rag_cti.knowledge.agentic_graph.run_agentic_answer") as legacy_agentic,
    ):
        text = rag_cti.ask("q")

    assert text == "answer"
    assert agentic.called
    assert not legacy_agentic.called


def test_answer_passes_validated_branch_plan_to_supervisor() -> None:
    import rag_cti

    understanding = _understanding(decomposition=_proposal(_branch("b1", "APT29"), _branch("b2", "Turla")))
    supervised_answer = _agentic_answer("q").model_copy(update={"branch_count": 2, "decomposed": True})
    with (
        patch.object(rag_cti, "_build_runtime_deps", return_value=_deps(understanding, supervisor_enabled=True)),
        patch("rag_cti.observability.tracing.add_trace_metadata") as meta,
        patch.object(rag_cti, "run_agentic_investigation") as agentic,
        patch("rag_cti.knowledge.supervisor_graph.run_supervised_answer", return_value=supervised_answer) as supervised,
    ):
        ans = rag_cti.answer("q")

    assert ans.model == "supervisor"
    assert not agentic.called
    assert supervised.call_args.kwargs["branch_plan"] == understanding.decomposition.branches
    assert meta.call_args.kwargs["runtime_path"] == "supervisor"
    assert meta.call_args.kwargs["admission_reason"] == "validated_independent_branches"
