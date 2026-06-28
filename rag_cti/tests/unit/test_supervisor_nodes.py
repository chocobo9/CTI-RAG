"""Unit tests for supervisor_nodes (ledger merge, technique extraction, ReAct loop)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.knowledge.supervisor_nodes import (
    extract_techniques,
    merge_branch_ledgers,
    run_supervisor_loop,
)
from rag_cti.types import Chunk, FactRow, QueryResult, RetrievalResult

# --- merge_branch_ledgers --------------------------------------------------


def _ledger_with_chunk(cid: str, score: float) -> EvidenceLedger:
    led = EvidenceLedger()
    chunk = Chunk(id=cid, parent_doc_id="d", source="otx", content="x", chunk_index=0)
    led.add_query_result(
        QueryResult(
            query="q",
            results=[
                RetrievalResult(document=chunk, score=score, rank=0, retriever_source="dense")
            ],
            total_retrieved=1,
            retrieval_ms=0.0,
        )
    )
    return led


def _fact(fid: str, attack_id: str, name: str, *, object_type: str = "technique") -> FactRow:
    return FactRow(
        fact_id=fid,
        subject_id="actor_G0016",
        subject_name="APT29",
        predicate="uses",
        object_id=(f"technique_{attack_id}" if object_type == "technique" else attack_id),
        object_name=name,
        object_type=object_type,
        aggregate_credibility=0.9,
        conflict=False,
    )


def _ledger_with_fact(fid: str) -> EvidenceLedger:
    led = EvidenceLedger()
    led.add_facts((_fact(fid, "T1566", "Phishing"),))
    return led


def test_merge_branch_ledgers_unions_all() -> None:
    master = merge_branch_ledgers(
        [_ledger_with_chunk("c1", 0.5), _ledger_with_chunk("c2", 0.7), _ledger_with_fact("f1")]
    )
    assert master.real_id_set == frozenset({"c1", "c2", "f1"})


def test_merge_branch_ledgers_empty_input_yields_empty() -> None:
    assert merge_branch_ledgers([]).real_id_set == frozenset()


# --- extract_techniques (structured slice for the BranchReport) -------------


def test_extract_techniques_normalises_id_and_filters_non_techniques() -> None:
    facts = [
        _fact("f1", "T1059", "Command and Scripting Interpreter"),
        _fact("f2", "S0001", "SomeMalware", object_type="family"),  # dropped
        _fact("f3", "T1566", "Phishing"),
    ]
    assert extract_techniques(facts) == (
        ("T1059", "Command and Scripting Interpreter", "f1"),
        ("T1566", "Phishing", "f3"),
    )


def test_extract_techniques_dedups_by_id_first_wins() -> None:
    facts = [_fact("f1", "T1059", "first"), _fact("f2", "T1059", "second")]
    assert extract_techniques(facts) == (("T1059", "first", "f1"),)


def test_extract_techniques_empty() -> None:
    assert extract_techniques([]) == ()


# --- run_supervisor_loop (ReAct orchestration; fake model + fake dispatch) --


class _FakeAI:
    def __init__(self, tool_calls: list[dict[str, Any]]) -> None:
        self.tool_calls = tool_calls
        self.content = ""


class _ScriptedModel:
    """Returns pre-scripted AI messages on successive invoke() calls."""

    def __init__(self, turns: list[_FakeAI]) -> None:
        self._turns = list(turns)
        self.invocations = 0

    def invoke(self, convo: list[Any]) -> _FakeAI:
        self.invocations += 1
        return self._turns.pop(0)


class _LoopingModel:
    """Always emits a tool call (would loop forever without a max_steps cap)."""

    def __init__(self) -> None:
        self.invocations = 0

    def invoke(self, convo: list[Any]) -> _FakeAI:
        self.invocations += 1
        return _FakeAI([{"name": "dispatch_worker", "args": {}, "id": "x"}])


class _RaisingModel:
    def __init__(self) -> None:
        self.invocations = 0

    def invoke(self, convo: list[Any]) -> _FakeAI:
        self.invocations += 1
        raise RuntimeError("provider down")


def test_supervisor_loop_dispatches_in_parallel_then_composes_then_stops() -> None:
    calls: list[str] = []

    def dispatch(name: str, args: dict[str, Any]) -> Any:
        calls.append(name)
        return {"ok": name}

    model = _ScriptedModel(
        [
            _FakeAI(
                [
                    {"name": "dispatch_worker", "args": {"sub_question": "APT29"}, "id": "c1"},
                    {"name": "dispatch_worker", "args": {"sub_question": "Turla"}, "id": "c2"},
                ]
            ),
            _FakeAI([{"name": "compose_answer", "args": {}, "id": "c3"}]),
            _FakeAI([]),  # no tool calls -> stop
        ]
    )
    run_supervisor_loop(model, dispatch, [("user", "compare")], max_steps=6, max_workers=4)
    assert model.invocations == 3
    assert sorted(calls[:2]) == ["dispatch_worker", "dispatch_worker"]  # parallel pair
    assert calls[2] == "compose_answer"


def test_supervisor_loop_respects_max_steps() -> None:
    def dispatch(name: str, args: dict[str, Any]) -> Any:
        return "ok"

    model = _LoopingModel()
    run_supervisor_loop(model, dispatch, [("user", "q")], max_steps=3, max_workers=2)
    assert model.invocations == 3


def test_supervisor_loop_surfaces_tool_error_without_crashing() -> None:
    def dispatch(name: str, args: dict[str, Any]) -> Any:
        raise RuntimeError("boom")

    model = _ScriptedModel(
        [_FakeAI([{"name": "dispatch_worker", "args": {}, "id": "c1"}]), _FakeAI([])]
    )
    convo = run_supervisor_loop(model, dispatch, [("user", "q")], max_steps=6, max_workers=2)
    assert any("boom" in str(getattr(m, "content", "")) for m in convo)


def test_supervisor_loop_routes_dispatch_through_limiter() -> None:
    # B4 wiring: every worker dispatch must pass through limiter.slot() so the B3 admission cap
    # applies (the limiter's own concurrency bounding is covered in test_limiter). Assert one slot
    # was acquired per dispatched worker call.
    acquired: list[str] = []

    class _SpyLimiter:
        @contextmanager
        def slot(self) -> Any:
            acquired.append("slot")
            yield

    calls: list[str] = []

    def dispatch(name: str, args: dict[str, Any]) -> Any:
        calls.append(name)
        return {"ok": name}

    model = _ScriptedModel(
        [
            _FakeAI(
                [
                    {"name": "dispatch_worker", "args": {"sub_question": "APT29"}, "id": "c1"},
                    {"name": "dispatch_worker", "args": {"sub_question": "Turla"}, "id": "c2"},
                ]
            ),
            _FakeAI([]),
        ]
    )
    run_supervisor_loop(
        model, dispatch, [("user", "compare")], max_steps=6, max_workers=4, limiter=_SpyLimiter()
    )
    assert len(acquired) == 2  # one slot per worker dispatch
    assert sorted(calls) == ["dispatch_worker", "dispatch_worker"]


def test_supervisor_loop_stops_immediately_when_deadline_passed() -> None:
    model = _LoopingModel()

    run_supervisor_loop(
        model,
        lambda name, args: {"ok": True},
        [("user", "q")],
        max_steps=6,
        max_workers=2,
        deadline=time.monotonic() - 1,
    )

    assert model.invocations == 0


def test_supervisor_loop_catches_model_error_and_reports_callback() -> None:
    errors: list[BaseException] = []
    model = _RaisingModel()

    convo = run_supervisor_loop(
        model,
        lambda name, args: {"ok": True},
        [("user", "q")],
        max_steps=6,
        max_workers=2,
        on_model_error=errors.append,
    )

    assert model.invocations == 1
    assert len(errors) == 1
    assert any(
        "supervisor model failed: provider down" in str(getattr(m, "content", "")) for m in convo
    )
