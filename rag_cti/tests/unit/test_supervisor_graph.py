"""Wiring tests for the Model-B supervisor ReAct loop (run_supervised_answer) with FAKE
deps — no real LLM, no langgraph. A fake chat model emits dispatch_worker / compose_answer
tool calls; gather_branch is monkeypatched to canned reports; the Composer is a fake. This
exercises the supervisor's orchestration: it never writes the answer (the answer is the
Composer's output), citations are grounded, and single/empty dispatch degrades correctly."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from rag_cti.knowledge import supervisor_graph
from rag_cti.knowledge.agentic_state import BranchReport, SubQuestion
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.runtime_harness import ProposedBranch
from rag_cti.types import FactRow, QueryResult


def _settings() -> Any:
    return SimpleNamespace(
        supervisor_max_branches=4,
        supervisor_max_steps=6,
        agentic_synthesis_top_k=50,
        agentic_max_iterations=6,
        agentic_verifier_provider="deepseek",
        llm_max_global_concurrency=4,
        llm_rate_limit_per_sec=0.0,
    )


def _empty_qr(query: str = "q", top_k: int = 10) -> QueryResult:
    return QueryResult(query=query, results=[], total_retrieved=0, retrieval_ms=0.0)


def _fact(fid: str) -> FactRow:
    return FactRow(
        fact_id=fid,
        subject_id="actor",
        subject_name="A",
        predicate="uses",
        object_id="technique_T1059",
        object_name="Command",
        object_type="technique",
        aggregate_credibility=0.9,
        conflict=False,
    )


def _fake_gather(branch: SubQuestion, **_kwargs: Any) -> tuple[EvidenceLedger, BranchReport]:
    key = (branch.focus_entity or branch.sub_question).replace(" ", "_")
    fid = f"fact_{key}"
    ledger = EvidenceLedger()
    ledger.add_facts((_fact(fid),))
    report = BranchReport(
        sub_question=branch.sub_question,
        focus_entity=branch.focus_entity,
        sub_answer="",  # gather-only worker
        techniques=(("T1059", "Command", fid),),
        cited_ids=(fid,),
        n_facts=1,
        tokens_used=10,
        iteration_count=1,
    )
    return ledger, report


def _fake_composer(system: str, user: str) -> str:
    # cites the per-branch fact ids the workers produced (grounded in the merged evidence)
    return "Compare: APT29 [fact_APT29] vs Turla [fact_Turla]."


class _FakeAI:
    def __init__(self, tool_calls: list[dict[str, Any]]) -> None:
        self.tool_calls = tool_calls
        self.content = ""


class _BoundModel:
    def __init__(self, turns: list[_FakeAI]) -> None:
        self._turns = list(turns)

    def invoke(self, convo: list[Any]) -> _FakeAI:
        return self._turns.pop(0)


class _FakeChatModel:
    def __init__(self, turns: list[_FakeAI]) -> None:
        self._turns = turns

    def bind_tools(self, tools: list[Any]) -> _BoundModel:
        return _BoundModel(self._turns)


def _run(chat_model: _FakeChatModel, query: str) -> Any:
    return supervisor_graph.run_supervised_answer(
        query,
        settings=_settings(),
        run_retrieve=lambda q, k: _empty_qr(q, k),
        fact_store=None,
        ontology_nodes=[],
        generator=object(),
        chat_model=chat_model,
        judge=lambda s, u: "{}",
        composer=_fake_composer,
    )


def test_multi_dispatch_answer_is_composer_output_and_grounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(supervisor_graph, "gather_branch", _fake_gather)
    chat_model = _FakeChatModel(
        [
            _FakeAI(
                [
                    {
                        "name": "dispatch_worker",
                        "args": {"sub_question": "APT29 ttps", "focus_entity": "APT29"},
                        "id": "c1",
                    },
                    {
                        "name": "dispatch_worker",
                        "args": {"sub_question": "Turla ttps", "focus_entity": "Turla"},
                        "id": "c2",
                    },
                ]
            ),
            _FakeAI([{"name": "compose_answer", "args": {}, "id": "c3"}]),
            _FakeAI([]),  # stop
        ]
    )
    ans = _run(chat_model, "Compare APT29 and Turla")

    assert ans.decomposed is True
    assert ans.branch_count == 2
    # the answer is the COMPOSER's output, never the supervisor's own text
    assert ans.answer == "Compare: APT29 [fact_APT29] vs Turla [fact_Turla]."
    # grounding guard: cited ids are exactly the merged branch evidence ids
    assert set(ans.cited_ids) == {"fact_APT29", "fact_Turla"}


def test_single_dispatch_composes_from_one_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(supervisor_graph, "gather_branch", _fake_gather)
    chat_model = _FakeChatModel(
        [
            _FakeAI(
                [
                    {
                        "name": "dispatch_worker",
                        "args": {"sub_question": "APT29 malware comms", "focus_entity": "APT29"},
                        "id": "c1",
                    },
                ]
            ),
            _FakeAI([]),  # stop without composing
        ]
    )
    ans = _run(chat_model, "what does the malware APT29 dropped communicate with")

    assert ans.decomposed is False
    assert ans.branch_count == 1
    # gather-only worker has NO sub_answer -> the Composer is still the sole synthesizer
    assert ans.answer == "Compare: APT29 [fact_APT29] vs Turla [fact_Turla]."
    # only the gathered evidence id survives the deterministic grounding guard
    assert set(ans.cited_ids) == {"fact_APT29"}


def test_no_dispatch_degrades_to_one_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(supervisor_graph, "gather_branch", _fake_gather)
    chat_model = _FakeChatModel([_FakeAI([])])  # supervisor stops immediately, dispatches nothing
    ans = _run(chat_model, "some query")

    assert ans.branch_count == 1  # degraded: one worker on the original query
    assert ans.decomposed is False


def test_validated_branch_plan_skips_supervisor_model_and_composes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def gather(branch: SubQuestion, **kwargs: Any) -> tuple[EvidenceLedger, BranchReport]:
        calls.append(branch.branch_id)
        return _fake_gather(branch, **kwargs)

    class NoSupervisorModel:
        def bind_tools(self, tools: list[Any]) -> Any:
            raise AssertionError("validated branch plans must not invoke supervisor routing")

    compose_calls = 0

    def composer(system: str, user: str) -> str:
        nonlocal compose_calls
        compose_calls += 1
        return _fake_composer(system, user)

    monkeypatch.setattr(supervisor_graph, "gather_branch", gather)
    ans = supervisor_graph.run_supervised_answer(
        "Compare APT29 and Turla",
        settings=_settings(),
        run_retrieve=lambda q, k: _empty_qr(q, k),
        fact_store=None,
        ontology_nodes=[],
        generator=object(),
        chat_model=NoSupervisorModel(),
        judge=lambda s, u: "{}",
        composer=composer,
        branch_plan=(
            ProposedBranch(
                branch_id="apt29",
                sub_question="APT29 branch",
                focus_entity="APT29",
                independent_reason="independent entity",
            ),
            ProposedBranch(
                branch_id="turla",
                sub_question="Turla branch",
                focus_entity="Turla",
                independent_reason="independent entity",
            ),
        ),
    )

    assert sorted(calls) == ["apt29", "turla"]
    assert compose_calls == 1
    assert ans.branch_count == 2
    assert ans.decomposed is True


def test_dispatch_after_compose_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def gather(branch: SubQuestion, **kwargs: Any) -> tuple[EvidenceLedger, BranchReport]:
        calls.append(branch.sub_question)
        return _fake_gather(branch, **kwargs)

    monkeypatch.setattr(supervisor_graph, "gather_branch", gather)
    chat_model = _FakeChatModel(
        [
            _FakeAI(
                [
                    {
                        "name": "dispatch_worker",
                        "args": {"sub_question": "APT29 ttps", "focus_entity": "APT29"},
                        "id": "c1",
                    }
                ]
            ),
            _FakeAI([{"name": "compose_answer", "args": {}, "id": "c2"}]),
            _FakeAI(
                [
                    {
                        "name": "dispatch_worker",
                        "args": {"sub_question": "Turla ttps", "focus_entity": "Turla"},
                        "id": "c3",
                    }
                ]
            ),
            _FakeAI([]),
        ]
    )

    ans = _run(chat_model, "Compare APT29 and Turla")

    assert calls == ["APT29 ttps"]
    assert ans.branch_count == 1


def test_invalid_composer_citation_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(supervisor_graph, "gather_branch", _fake_gather)

    def composer(system: str, user: str) -> str:
        return "APT29 uses Command [fact_APT29] and invented evidence [fact_missing]."

    ans = supervisor_graph.run_supervised_answer(
        "Compare APT29 and Turla",
        settings=_settings(),
        run_retrieve=lambda q, k: _empty_qr(q, k),
        fact_store=None,
        ontology_nodes=[],
        generator=object(),
        chat_model=_FakeChatModel(
            [
                _FakeAI(
                    [
                        {
                            "name": "dispatch_worker",
                            "args": {
                                "sub_question": "APT29 ttps",
                                "focus_entity": "APT29",
                            },
                            "id": "c1",
                        }
                    ]
                ),
                _FakeAI([]),
            ]
        ),
        judge=lambda s, u: "{}",
        composer=composer,
    )

    assert ans.cited_ids == ("fact_APT29",)
    assert "fact_missing" not in ans.cited_ids
    assert ans.dropped_citation_count >= 1


def test_failed_branch_is_reported_and_composed(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_user: dict[str, str] = {}

    def gather(branch: SubQuestion, **_kwargs: Any) -> tuple[EvidenceLedger, BranchReport]:
        if branch.focus_entity == "Turla":
            raise RuntimeError("provider unavailable")
        return _fake_gather(branch)

    def composer(system: str, user: str) -> str:
        captured_user["text"] = user
        return "APT29 evidence is available [fact_APT29]; Turla branch failed."

    monkeypatch.setattr(supervisor_graph, "gather_branch", gather)
    ans = supervisor_graph.run_supervised_answer(
        "Compare APT29 and Turla",
        settings=_settings(),
        run_retrieve=lambda q, k: _empty_qr(q, k),
        fact_store=None,
        ontology_nodes=[],
        generator=object(),
        chat_model=_FakeChatModel(
            [
                _FakeAI(
                    [
                        {
                            "name": "dispatch_worker",
                            "args": {"sub_question": "APT29 ttps", "focus_entity": "APT29"},
                            "id": "c1",
                        },
                        {
                            "name": "dispatch_worker",
                            "args": {"sub_question": "Turla ttps", "focus_entity": "Turla"},
                            "id": "c2",
                        },
                    ]
                ),
                _FakeAI([]),
            ]
        ),
        judge=lambda s, u: "{}",
        composer=composer,
    )

    assert ans.branch_count == 2
    assert ans.cited_ids == ("fact_APT29",)
    assert '"status": "failed"' in captured_user["text"]
    assert "provider unavailable" in captured_user["text"]
