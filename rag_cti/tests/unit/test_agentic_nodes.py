"""Unit tests for the agentic loop's pure node logic (knowledge.agentic_nodes)."""

from __future__ import annotations

import json
import threading
import time

import pytest
from langchain_core.messages import ToolMessage

from rag_cti.knowledge import agentic_nodes as nodes
from rag_cti.knowledge import react_loop
from rag_cti.knowledge.agentic_state import AgenticAnswer, SufficiencyVerdict
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.types import (
    Chunk,
    FactRow,
    GeneratedAnswer,
    GraphOutline,
    OutlineEntry,
    QueryResult,
    RetrievalResult,
)


def _result(cid: str, score: float = 0.9, content: str = "body") -> RetrievalResult:
    chunk = Chunk(id=cid, parent_doc_id="d", source="otx", content=content, chunk_index=0)
    return RetrievalResult(document=chunk, score=score, rank=0, retriever_source="dense")


def _row(fid: str, *, conflict: bool = False) -> FactRow:
    return FactRow(
        fact_id=fid,
        subject_id="actor_G0016",
        subject_name="APT29",
        predicate="uses",
        object_id="technique_T1566",
        object_name="Phishing",
        object_type="technique",
        aggregate_credibility=0.9,
        conflict=conflict,
    )


def _ledger_with_chunks(*results: RetrievalResult) -> EvidenceLedger:
    led = EvidenceLedger()
    led.add_query_result(
        QueryResult(
            query="q", results=list(results), total_retrieved=len(results), retrieval_ms=1.0
        )
    )
    return led


# --- parse_verdict -------------------------------------------------------------


def test_parse_verdict_valid() -> None:
    raw = json.dumps(
        {
            "grounded": True,
            "faithfulness_estimate": 0.8,
            "sufficient": True,
            "coverage_gaps": [],
            "next_action": "stop",
            "suggested_queries": [],
            "suggested_graph_targets": [],
        }
    )
    v = nodes.parse_verdict(raw)
    assert v is not None
    assert v.grounded
    assert v.sufficient
    assert v.next_action == "stop"
    assert v.faithfulness_estimate == 0.8


def test_parse_verdict_strips_code_fence() -> None:
    raw = "```json\n" + json.dumps({"next_action": "retrieve_more"}) + "\n```"
    v = nodes.parse_verdict(raw)
    assert v is not None
    assert v.next_action == "retrieve_more"


def test_parse_verdict_invalid_json_returns_none() -> None:
    assert nodes.parse_verdict("not json at all") is None


def test_parse_verdict_non_dict_returns_none() -> None:
    assert nodes.parse_verdict("[1, 2, 3]") is None


def test_parse_verdict_missing_next_action_computed_stop() -> None:
    v = nodes.parse_verdict(json.dumps({"grounded": True, "sufficient": True}))
    assert v is not None
    assert v.next_action == "stop"


def test_parse_verdict_missing_next_action_computed_retrieve() -> None:
    v = nodes.parse_verdict(json.dumps({"grounded": True, "sufficient": False}))
    assert v is not None
    assert v.next_action == "retrieve_more"


def test_parse_verdict_sufficient_without_grounded_stops() -> None:
    # Sufficiency drives convergence; a missing/ungrounded draft must not block stop
    # (grounding is enforced at synthesis). No next_action -> computed from sufficient.
    v = nodes.parse_verdict(json.dumps({"grounded": False, "sufficient": True}))
    assert v is not None
    assert v.next_action == "stop"


def test_parse_verdict_bad_faithfulness_defaults_zero() -> None:
    v = nodes.parse_verdict(json.dumps({"sufficient": True, "faithfulness_estimate": "high"}))
    assert v is not None
    assert v.faithfulness_estimate == 0.0


def test_parse_verdict_coerces_graph_targets() -> None:
    raw = json.dumps(
        {
            "next_action": "retrieve_more",
            "suggested_graph_targets": [
                ["actor_G0016", "uses", "technique"],
                ["ip_1", None, None],
                [],
                "garbage",
                ["", "uses", "x"],
            ],
        }
    )
    v = nodes.parse_verdict(raw)
    assert v is not None
    assert v.suggested_graph_targets == (
        ("actor_G0016", "uses", "technique"),
        ("ip_1", None, None),
    )


# --- build_judge_user ----------------------------------------------------------


def test_build_judge_user_is_bounded_json() -> None:
    led = _ledger_with_chunks(*[_result(f"c{i}", score=i / 100) for i in range(30)])
    led.add_facts(tuple(_row(f"f{i}") for i in range(60)))
    data = json.loads(nodes.build_judge_user("the question", "the draft", led))
    assert data["question"] == "the question"
    assert data["draft"] == "the draft"
    assert len(data["evidence"]["chunks"]) == nodes._JUDGE_MAX_CHUNKS
    assert len(data["evidence"]["facts"]) == nodes._JUDGE_MAX_FACTS


# --- assess_sufficiency --------------------------------------------------------


def test_assess_sufficiency_parses_judge_output() -> None:
    captured: dict[str, str] = {}

    def judge(system: str, user: str) -> str:
        captured["system"] = system
        return json.dumps({"grounded": True, "sufficient": True, "next_action": "stop"})

    v = nodes.assess_sufficiency(judge, "q", "draft", EvidenceLedger())
    assert v is not None
    assert v.next_action == "stop"
    assert "grounded" in captured["system"]


def test_assess_sufficiency_garbage_returns_none() -> None:
    assert nodes.assess_sufficiency(lambda s, u: "garbage", "q", "d", EvidenceLedger()) is None


# --- decide_next (the router) --------------------------------------------------


def _verdict(action: str = "retrieve_more") -> SufficiencyVerdict:
    return SufficiencyVerdict(next_action=action)


def test_decide_next_iteration_ceiling_is_budget() -> None:
    assert nodes.decide_next(_verdict(), 3, 0, 5, max_iterations=3, token_ceiling=100) == (
        "synthesize",
        "budget",
    )


def test_decide_next_token_ceiling_is_budget() -> None:
    assert nodes.decide_next(_verdict(), 1, 100, 5, max_iterations=3, token_ceiling=100) == (
        "synthesize",
        "budget",
    )


def test_decide_next_none_verdict_is_parse_fallback() -> None:
    assert nodes.decide_next(None, 1, 0, 5, max_iterations=3, token_ceiling=100) == (
        "synthesize",
        "parse_fallback",
    )


def test_decide_next_stop_is_sufficient() -> None:
    assert nodes.decide_next(_verdict("stop"), 1, 0, 5, max_iterations=3, token_ceiling=100) == (
        "synthesize",
        "sufficient",
    )


def test_decide_next_continue_is_agent_turn() -> None:
    assert nodes.decide_next(
        _verdict("retrieve_more"), 1, 0, 5, max_iterations=15, token_ceiling=100
    ) == ("agent_turn", "")


def test_decide_next_no_new_evidence_stops() -> None:
    # A burst that gathered nothing new -> retrying is futile -> stop (not budget).
    assert nodes.decide_next(
        _verdict("retrieve_more"), 1, 0, 0, max_iterations=15, token_ceiling=100
    ) == ("synthesize", "no_progress")


def test_decide_next_repeated_gap_without_new_facts_stops() -> None:
    # Judge repeats the EXACT same gap and the burst added no new graph facts (only churned
    # prose) -> stuck -> stop, rather than looping to the budget cap. new_evidence>0 so the
    # plain no-progress guard does NOT fire; the stuck guard must.
    v = SufficiencyVerdict(next_action="retrieve_more", coverage_gaps=("same gap",))
    assert nodes.decide_next(
        v, 2, 0, 5, max_iterations=15, token_ceiling=100, new_facts=0, prev_gaps=("same gap",)
    ) == ("synthesize", "no_progress")


def test_decide_next_repeated_gap_but_new_facts_continues() -> None:
    # Same repeated gap but the burst DID add new facts -> still making progress -> continue.
    v = SufficiencyVerdict(next_action="retrieve_more", coverage_gaps=("same gap",))
    assert nodes.decide_next(
        v, 2, 0, 5, max_iterations=15, token_ceiling=100, new_facts=4, prev_gaps=("same gap",)
    ) == ("agent_turn", "")


def test_decide_next_changed_gap_continues() -> None:
    # Gaps changed (judge refining) -> not stuck -> continue even with no new facts.
    v = SufficiencyVerdict(next_action="retrieve_more", coverage_gaps=("new gap",))
    assert nodes.decide_next(
        v, 2, 0, 5, max_iterations=15, token_ceiling=100, new_facts=0, prev_gaps=("old gap",)
    ) == ("agent_turn", "")


def test_decide_next_retrieve_rounds_exhausted_stops_before_budget() -> None:
    # Judge is insatiable (keeps wanting more, fresh gaps, real progress) — the patience cap
    # must stop it DETERMINISTICALLY (max_rounds), NOT let it run to the token/iter backstop.
    v = SufficiencyVerdict(next_action="retrieve_more", coverage_gaps=("g",))
    # iteration_count=3 -> 2 retrieve_more rounds done == max_retrieve_rounds -> stop.
    assert nodes.decide_next(
        v, 3, 0, 5, max_iterations=15, token_ceiling=10**9, max_retrieve_rounds=2, new_facts=5
    ) == ("synthesize", "max_rounds")


def test_decide_next_within_retrieve_rounds_continues() -> None:
    # One retrieve_more round done (iteration_count=2) < cap(2) -> still allowed to continue.
    v = SufficiencyVerdict(next_action="retrieve_more", coverage_gaps=("g",))
    assert nodes.decide_next(
        v, 2, 0, 5, max_iterations=15, token_ceiling=10**9, max_retrieve_rounds=2, new_facts=5
    ) == ("agent_turn", "")


def test_decide_next_wall_clock_timeout_stops() -> None:
    # Elapsed exceeds the wall-clock guardrail -> stop with "timeout", bounding tail latency
    # even when iteration/token budgets are nowhere near and the judge wants more.
    v = _verdict("retrieve_more")
    assert nodes.decide_next(
        v,
        1,
        0,
        5,
        max_iterations=15,
        token_ceiling=10**9,
        elapsed_seconds=200.0,
        max_wall_seconds=180.0,
    ) == ("synthesize", "timeout")


def test_decide_next_wall_clock_disabled_when_zero() -> None:
    # max_wall_seconds=0 disables the guardrail -> elapsed is ignored, loop continues.
    v = _verdict("retrieve_more")
    assert nodes.decide_next(
        v,
        1,
        0,
        5,
        max_iterations=15,
        token_ceiling=10**9,
        elapsed_seconds=9999.0,
        max_wall_seconds=0.0,
    ) == ("agent_turn", "")


def test_decide_next_tool_budget_stops() -> None:
    v = _verdict("retrieve_more")
    assert nodes.decide_next(
        v,
        1,
        0,
        5,
        max_iterations=15,
        token_ceiling=10**9,
        tool_calls_used=3,
        max_tool_calls=3,
    ) == ("synthesize", "tool_budget")


def test_decide_next_tool_budget_does_not_preempt_sufficient() -> None:
    assert nodes.decide_next(
        _verdict("stop"),
        1,
        0,
        5,
        max_iterations=15,
        token_ceiling=10**9,
        tool_calls_used=99,
        max_tool_calls=3,
    ) == ("synthesize", "sufficient")


def test_decide_next_open_cat_stall_stops() -> None:
    # No new facts AND the open-category count hasn't shrunk for the stall limit -> stop early
    # with a meaningful reason instead of churning prose to max_rounds. new_evidence>0 so the
    # plain no-progress guard does NOT fire; no prev_gaps so the stuck guard does NOT fire.
    v = SufficiencyVerdict(next_action="retrieve_more", coverage_gaps=("g",))
    assert nodes.decide_next(
        v,
        2,
        0,
        5,
        max_iterations=15,
        token_ceiling=10**9,
        new_facts=0,
        open_cat_stall=2,
        max_open_cat_stall=2,
    ) == ("synthesize", "open_cat_stall")


def test_decide_next_open_cat_stall_disabled_when_zero() -> None:
    # max_open_cat_stall=0 disables the guard -> the stall count is ignored, loop continues.
    v = SufficiencyVerdict(next_action="retrieve_more", coverage_gaps=("g",))
    assert nodes.decide_next(
        v,
        2,
        0,
        5,
        max_iterations=15,
        token_ceiling=10**9,
        new_facts=0,
        open_cat_stall=9,
        max_open_cat_stall=0,
    ) == ("agent_turn", "")


def test_decide_next_open_cat_stall_but_new_facts_continues() -> None:
    # Still adding facts -> the enumeration IS advancing -> continue even if open count is flat.
    v = SufficiencyVerdict(next_action="retrieve_more", coverage_gaps=("g",))
    assert nodes.decide_next(
        v,
        2,
        0,
        5,
        max_iterations=15,
        token_ceiling=10**9,
        new_facts=4,
        open_cat_stall=2,
        max_open_cat_stall=2,
    ) == ("agent_turn", "")


# --- build_directives ----------------------------------------------------------


def test_build_directives_includes_gaps_queries_targets() -> None:
    v = SufficiencyVerdict(
        coverage_gaps=("what malware",),
        suggested_queries=("APT29 malware",),
        suggested_graph_targets=(("actor_G0016", "uses", "family"),),
    )
    d = nodes.build_directives(v, EvidenceLedger())
    assert "Still missing: what malware" in d
    assert "Try retrieve for: APT29 malware" in d
    assert "Try graph_query: actor_G0016 (uses, family)" in d


def test_build_directives_empty_default() -> None:
    assert (
        nodes.build_directives(SufficiencyVerdict(), EvidenceLedger())
        == "Gather more evidence to fully answer the question."
    )


def test_build_directives_graph_target_without_slots() -> None:
    v = SufficiencyVerdict(suggested_graph_targets=(("ip_1", None, None),))
    assert "Try graph_query: ip_1" in nodes.build_directives(v, EvidenceLedger())


def test_build_directives_prepends_ledger_working_set_summary() -> None:
    # With a non-empty ledger, the directive tells the burst what it already has so it
    # does not re-resolve / re-outline / re-query the completed graph (the cost fix).
    led = _ledger_with_chunks(_result("c1"))
    led.add_facts((_row("f1"),))
    d = nodes.build_directives(SufficiencyVerdict(coverage_gaps=("more",)), led)
    assert "Already gathered" in d
    assert "1 graph facts for APT29" in d
    assert "do NOT call resolve_entity" in d
    assert "Still missing: more" in d  # gaps still present, after the summary


def test_build_turn_messages_iteration_one_has_no_directive() -> None:
    msgs = nodes.build_turn_messages("SYS", "the question", None, EvidenceLedger())
    assert msgs == [("system", "SYS"), ("user", "the question")]  # clean start, no carry


def test_build_turn_messages_retrieve_more_appends_directive() -> None:
    led = _ledger_with_chunks(_result("c1"))
    v = SufficiencyVerdict(next_action="retrieve_more", coverage_gaps=("gap1",))
    msgs = nodes.build_turn_messages("SYS", "q", v, led)
    assert msgs[0] == ("system", "SYS")
    assert msgs[1] == ("user", "q")
    assert msgs[2][0] == "user"
    assert "Still missing: gap1" in msgs[2][1]
    assert "Already gathered" in msgs[2][1]  # working-set summary from the ledger


def test_build_turn_messages_includes_history() -> None:
    msgs = nodes.build_turn_messages(
        "SYS", "and who do they target?", None, EvidenceLedger(), history=["What does APT29 use?"]
    )
    assert "Conversation so far" in msgs[1][1]
    assert "What does APT29 use?" in msgs[1][1]
    assert "Latest query: and who do they target?" in msgs[1][1]


# --- assemble_citations (the grounding guarantee) ------------------------------


def test_assemble_citations_keeps_real_drops_hallucinated() -> None:
    led = _ledger_with_chunks(_result("c1"))
    led.add_facts((_row("f1"),))
    kept, dropped = nodes.assemble_citations("uses [c1] and [f1] but also [fake99]", led)
    assert kept == ("c1", "f1")
    assert dropped == 1


def test_assemble_citations_recovers_chunk_prefixed_id() -> None:
    # The model mirrors the fact_ prefix and writes chunk_<id> for a bare chunk id;
    # recover the real id instead of dropping a valid citation.
    led = _ledger_with_chunks(_result("86f0abc"))
    kept, dropped = nodes.assemble_citations("see [chunk_86f0abc] but not [chunk_nope]", led)
    assert kept == ("86f0abc",)
    assert dropped == 1  # chunk_nope has no real id behind it


def test_assemble_citations_recovers_bare_fact_ids() -> None:
    led = _ledger_with_chunks()
    led.add_facts((_row("fact_f1"),))
    kept, dropped = nodes.assemble_citations("APT29 fact_f1 supports this.", led)
    assert kept == ("fact_f1",)
    assert dropped == 0


# --- synthesize_answer + build_agentic_answer ----------------------------------


class _FakeGenerator:
    def __init__(self, answer_text: str) -> None:
        self._text = answer_text
        self.seen: QueryResult | None = None
        self.seen_system_prompt: str | None = None

    def generate(
        self,
        query: str,
        query_result: QueryResult,
        raise_on_failure: bool = False,
        system_prompt: str | None = None,
    ) -> GeneratedAnswer:
        self.seen = query_result
        self.seen_system_prompt = system_prompt
        return GeneratedAnswer(
            query=query,
            answer=self._text,
            cited_chunk_ids=[],
            query_result=query_result,
            generation_ms=1.0,
            model="fake",
        )


def test_synthesize_answer_generates_over_ledger_union() -> None:
    led = _ledger_with_chunks(_result("c1", 0.3), _result("c2", 0.9))
    gen = _FakeGenerator("answer [c2]")
    ga = nodes.synthesize_answer(gen, "q", led)
    assert ga.answer == "answer [c2]"
    assert gen.seen is not None
    assert [r.document.id for r in gen.seen.results] == ["c2", "c1"]  # union, score-desc


def test_synthesize_answer_caps_context_to_top_k() -> None:
    led = _ledger_with_chunks(_result("c1", 0.3), _result("c2", 0.9), _result("c3", 0.6))
    gen = _FakeGenerator("answer")
    nodes.synthesize_answer(gen, "q", led, top_k=1, fact_limit=0)
    assert gen.seen is not None
    assert [r.document.id for r in gen.seen.results] == ["c2"]  # only the top-1 by score


def test_synthesize_answer_caps_fact_context() -> None:
    led = _ledger_with_chunks(_result("c1", 0.9))
    led.add_facts((_row("f1"), _row("f2"), _row("f3")))
    gen = _FakeGenerator("answer")
    nodes.synthesize_answer(gen, "q", led, fact_limit=2)
    assert gen.seen is not None
    fact_ids = [r.document.id for r in gen.seen.results if r.document.source == "graph"]
    assert fact_ids == ["f1", "f2"]


def test_synthesize_answer_injects_facts_as_citable_pseudo_chunks() -> None:
    led = _ledger_with_chunks(_result("c1", 0.9))
    led.add_facts((_row("f1"),))
    gen = _FakeGenerator("answer")
    nodes.synthesize_answer(gen, "q", led)
    assert gen.seen is not None
    ids = [r.document.id for r in gen.seen.results]
    assert "c1" in ids  # prose chunk
    assert "f1" in ids  # graph fact, injected as a citable pseudo-chunk
    fact_row = next(r for r in gen.seen.results if r.document.id == "f1")
    assert fact_row.document.source == "graph"
    assert "APT29 uses Phishing" in fact_row.document.content


def test_synthesize_answer_orders_facts_before_chunks() -> None:
    led = _ledger_with_chunks(_result("c1", 0.9))
    led.add_facts((_row("f1"),))
    gen = _FakeGenerator("answer")
    nodes.synthesize_answer(gen, "q", led)
    assert gen.seen is not None
    ids = [r.document.id for r in gen.seen.results]
    assert ids == ["f1", "c1"]  # facts first (primacy) so they reach the cited answer


def test_synthesize_answer_uses_fact_aware_system_prompt() -> None:
    led = _ledger_with_chunks(_result("c1", 0.9))
    gen = _FakeGenerator("answer")
    nodes.synthesize_answer(gen, "q", led)
    assert gen.seen_system_prompt == nodes.AGENTIC_SYNTHESIS_SYSTEM


def test_build_agentic_answer_citation_guard_and_conflicts() -> None:
    led = _ledger_with_chunks(_result("c1"))
    led.add_facts((_row("f1", conflict=True), _row("f2")))
    qr = led.union_query_result("q")
    gen = GeneratedAnswer(
        query="q",
        answer="see [c1] and [bogus]",
        cited_chunk_ids=[],
        query_result=qr,
        generation_ms=1.0,
        model="fake",
    )
    ans = nodes.build_agentic_answer(
        "q", gen, led, iteration_count=2, tokens_used=42, stop_reason="sufficient"
    )
    assert isinstance(ans, AgenticAnswer)
    assert ans.cited_ids == ("c1",)
    assert ans.dropped_citation_count == 1
    assert tuple(f.fact_id for f in ans.conflicts) == ("f1",)
    assert ans.iteration_count == 2
    assert ans.tokens_used == 42
    assert ans.stop_reason == "sufficient"
    assert len(ans.collected_facts) == 2


# --- run_gather_loop (the GATHER-only inner burst) -----------------------------


class _FakeAI:
    """Minimal stand-in for an AIMessage with tool_calls (what model.invoke returns)."""

    type = "ai"

    def __init__(self, tool_calls: list[dict], content: str = "") -> None:
        self.tool_calls = tool_calls
        self.content = content


class _ScriptedModel:
    """Returns canned AIMessages in order — fakes a tool-bound chat model."""

    def __init__(self, responses: list[_FakeAI]) -> None:
        self._responses = list(responses)
        self.invoke_count = 0
        self.seen_inputs: list[list] = []

    def invoke(self, messages: list) -> _FakeAI:
        self.invoke_count += 1
        self.seen_inputs.append(list(messages))
        return self._responses.pop(0)


def test_run_gather_loop_dispatches_tools_then_stops_on_no_tool_call() -> None:
    calls: list[tuple[str, dict]] = []

    def dispatch(name: str, args: dict) -> dict:
        calls.append((name, args))
        return {"ok": name}

    model = _ScriptedModel(
        [
            _FakeAI([{"name": "graph_query", "args": {"subject_id": "x"}, "id": "t1"}]),
            _FakeAI([], content="done gathering"),  # no tool call -> stop
        ]
    )
    msgs = nodes.run_gather_loop(model, dispatch, [("user", "q")], max_steps=8)
    assert calls == [("graph_query", {"subject_id": "x"})]
    assert model.invoke_count == 2  # stopped as soon as the model emitted no tool call
    assert any(getattr(m, "content", "") == str({"ok": "graph_query"}) for m in msgs)


def test_run_gather_loop_respects_max_steps() -> None:
    calls: list[str] = []

    def dispatch(name: str, args: dict) -> str:
        calls.append(name)
        return "r"

    never_stops = _FakeAI([{"name": "retrieve", "args": {"query": "q"}, "id": "t"}])
    model = _ScriptedModel([never_stops] * 10)
    nodes.run_gather_loop(model, dispatch, [("user", "q")], max_steps=3)
    assert len(calls) == 3  # capped at max_steps rounds, never runs away


def test_run_gather_loop_surfaces_tool_error_and_continues() -> None:
    def dispatch(name: str, args: dict) -> str:
        raise ValueError("boom")

    model = _ScriptedModel(
        [
            _FakeAI([{"name": "graph_query", "args": {}, "id": "t1"}]),
            _FakeAI([], content="stop"),
        ]
    )
    msgs = nodes.run_gather_loop(model, dispatch, [("user", "q")], max_steps=8)
    assert any("boom" in getattr(m, "content", "") for m in msgs)  # error fed back, not raised


class _RaisingModel:
    """A tool-bound chat model whose invoke always raises (a persistent provider 429)."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.invoke_count = 0

    def invoke(self, messages: list) -> object:
        self.invoke_count += 1
        raise self._exc


def test_run_gather_loop_stops_immediately_when_deadline_passed() -> None:
    # An already-expired deadline stops the burst BEFORE the first model turn (the
    # fine-grained guard the coarse decide_next check cannot provide).
    model = _ScriptedModel([_FakeAI([], content="never reached")])
    msgs = nodes.run_gather_loop(
        model, lambda n, a: {}, [("user", "q")], max_steps=8, deadline=time.monotonic() - 1.0
    )
    assert model.invoke_count == 0
    assert msgs == [("user", "q")]  # transcript untouched


def test_run_gather_loop_none_deadline_keeps_prior_behaviour() -> None:
    model = _ScriptedModel([_FakeAI([], content="done")])
    nodes.run_gather_loop(model, lambda n, a: {}, [("user", "q")], max_steps=8, deadline=None)
    assert model.invoke_count == 1  # default None == pre-deadline behaviour


def test_run_gather_loop_catches_model_error_and_reports_via_callback() -> None:
    seen: list[BaseException] = []

    class _BoomError(Exception):
        pass

    model = _RaisingModel(_BoomError("429 provider down"))
    msgs = nodes.run_gather_loop(
        model, lambda n, a: {}, [("user", "q")], max_steps=8, on_model_error=seen.append
    )
    assert model.invoke_count == 1  # tried once, did not retry-storm
    assert isinstance(seen[0], _BoomError)  # reported via callback, NOT propagated
    assert msgs == [("user", "q")]  # partial transcript returned, no crash


# --- render_state_view + per-turn state injection (env perception, Iter1) ------


def _outline(entity_id: str, name: str, *entries: tuple[str, str, int]) -> GraphOutline:
    return GraphOutline(
        entity_id=entity_id,
        entity_name=name,
        entity_type="actor",
        outgoing=tuple(
            OutlineEntry(predicate=p, other_type=o, count=c, max_credibility=0.9)
            for p, o, c in entries
        ),
    )


def test_render_state_view_empty_ledger_is_blank() -> None:
    assert nodes.render_state_view(EvidenceLedger()) == ""


def test_render_state_view_marks_complete_category() -> None:
    led = EvidenceLedger()
    led.add_outline(_outline("actor_G0016", "APT29", ("uses", "technique", 2)))
    led.add_facts((_row("f1"), _row("f2")))  # 2 facts == count -> COMPLETE
    view = nodes.render_state_view(led)
    assert "APT29 (actor_G0016): resolved" in view
    assert "COMPLETE (do NOT graph_query again): uses->technique 2/2" in view
    assert "open categories" not in view


def test_render_state_view_lists_open_and_zero_categories() -> None:
    led = EvidenceLedger()
    led.add_outline(
        _outline("actor_G0016", "APT29", ("uses", "technique", 3), ("targets", "country", 5))
    )
    led.add_facts((_row("f1"), _row("f2")))  # 2/3 uses->technique; 0/5 targets->country
    view = nodes.render_state_view(led)
    assert "uses->technique 2/3" in view
    assert "targets->country 0/5" in view
    assert "open categories" in view
    # nothing reached its total -> no per-category COMPLETE line (header word doesn't count)
    assert "COMPLETE (do NOT graph_query again)" not in view


def test_render_state_view_reports_prose() -> None:
    view = nodes.render_state_view(_ledger_with_chunks(_result("c1"), _result("c2")))
    assert "prose: 2 chunks from otx" in view


# --- count_open_categories (A2 deterministic convergence signal) ---------------


def test_count_open_categories_empty_is_zero() -> None:
    assert nodes.count_open_categories(EvidenceLedger()) == 0


def test_count_open_categories_complete_category_not_counted() -> None:
    led = EvidenceLedger()
    led.add_outline(_outline("actor_G0016", "APT29", ("uses", "technique", 2)))
    led.add_facts((_row("f1"), _row("f2")))  # 2/2 reached the total -> COMPLETE -> not open
    assert nodes.count_open_categories(led) == 0


def test_count_open_categories_counts_open_and_zero_categories() -> None:
    led = EvidenceLedger()
    led.add_outline(
        _outline("actor_G0016", "APT29", ("uses", "technique", 3), ("targets", "country", 5))
    )
    led.add_facts((_row("f1"), _row("f2")))  # 2/3 uses->technique open; 0/5 targets->country open
    assert nodes.count_open_categories(led) == 2


def test_run_gather_loop_injects_fresh_state_view_at_end_each_turn() -> None:
    model = _ScriptedModel(
        [
            _FakeAI([{"name": "graph_query", "args": {}, "id": "t1"}]),
            _FakeAI([], content="stop"),
        ]
    )
    states = iter(["STATE-1", "STATE-2"])
    convo = nodes.run_gather_loop(
        model,
        lambda n, a: {"ok": 1},
        [("user", "q")],
        max_steps=8,
        render_state=lambda: next(states),
    )
    # fresh state view appended LAST on each turn (high-attention end position)
    assert model.seen_inputs[0][-1] == ("user", "STATE-1")
    assert model.seen_inputs[1][-1] == ("user", "STATE-2")
    # ephemeral: never persisted into the returned transcript (no stale accumulation)
    assert ("user", "STATE-1") not in convo
    assert ("user", "STATE-2") not in convo


def test_run_gather_loop_empty_state_view_is_not_injected() -> None:
    model = _ScriptedModel([_FakeAI([], content="done")])
    nodes.run_gather_loop(
        model, lambda n, a: {}, [("user", "q")], max_steps=8, render_state=lambda: ""
    )
    assert model.seen_inputs[0] == [("user", "q")]  # "" => no injection, input == convo


# --- action log + tool_call_count telemetry (Iter2) ----------------------------


def test_render_action_log_empty_is_blank() -> None:
    assert nodes.render_action_log(EvidenceLedger()) == ""


def test_render_action_log_formats_calls() -> None:
    led = EvidenceLedger()
    led.add_action("resolve_entity", {"name": "APT29"})
    led.add_action("graph_query", {"subject_id": "actor_G0016", "predicate": "uses"})
    log = nodes.render_action_log(led)
    assert "ACTIONS ALREADY TAKEN" in log
    assert "resolve_entity(name=APT29)" in log
    assert "graph_query(predicate=uses, subject_id=actor_G0016)" in log


def test_render_action_log_respects_limit_most_recent_last() -> None:
    led = EvidenceLedger()
    for i in range(5):
        led.add_action("retrieve", {"query": f"q{i}"})
    log = nodes.render_action_log(led, limit=2)
    assert "q3" in log  # only the last 2 kept
    assert "q4" in log
    assert "q0" not in log
    assert "q2" not in log


def test_build_agentic_answer_reports_tool_call_count() -> None:
    led = EvidenceLedger()
    led.add_action("resolve_entity", {"name": "APT29"})
    led.add_action("graph_query", {"subject_id": "s1"})
    gen = GeneratedAnswer(
        query="q",
        answer="answer",
        cited_chunk_ids=[],
        query_result=QueryResult(query="q", results=[], total_retrieved=0, retrieval_ms=0.0),
        generation_ms=0.0,
        model="x",
    )
    ans = nodes.build_agentic_answer(
        "q", gen, led, iteration_count=1, tokens_used=10, stop_reason="sufficient"
    )
    assert ans.tool_call_count == 2


# --- within-burst observation masking (Iter3, eval-gated removal) --------------


def test_mask_stale_observations_disabled_returns_same_list() -> None:
    msgs = [ToolMessage(content="a", tool_call_id="t1")]
    assert nodes.mask_stale_observations(msgs, 0) is msgs  # 0 => no copy, no change


def test_mask_stale_observations_noop_when_within_keep() -> None:
    msgs = [
        ToolMessage(content="a", tool_call_id="t1"),
        ToolMessage(content="b", tool_call_id="t2"),
    ]
    assert nodes.mask_stale_observations(msgs, 5) is msgs  # <= keep_last => unchanged


def test_mask_stale_observations_masks_old_keeps_recent_and_ids() -> None:
    msgs = [
        ("user", "q"),
        ToolMessage(content="obs1", tool_call_id="t1"),
        ToolMessage(content="obs2", tool_call_id="t2"),
        ToolMessage(content="obs3", tool_call_id="t3"),
    ]
    out = nodes.mask_stale_observations(msgs, keep_last=2)
    assert out[1].content == nodes._TRIMMED_STUB  # oldest masked
    assert out[1].tool_call_id == "t1"  # id preserved for pairing
    assert out[2].content == "obs2"  # last 2 intact
    assert out[3].content == "obs3"
    assert out[0] == ("user", "q")  # non-tool message untouched
    assert msgs[1].content == "obs1"  # input not mutated


def test_run_gather_loop_masks_stale_observations_in_model_input() -> None:
    model = _ScriptedModel(
        [
            _FakeAI(
                [
                    {"name": "retrieve", "args": {}, "id": "t1"},
                    {"name": "retrieve", "args": {}, "id": "t2"},
                    {"name": "retrieve", "args": {}, "id": "t3"},
                ]
            ),
            _FakeAI([], content="stop"),
        ]
    )
    convo = nodes.run_gather_loop(
        model, lambda n, a: {"r": 1}, [("user", "q")], max_steps=8, keep_last_observations=1
    )
    turn2 = model.seen_inputs[1]  # second turn's model input
    tool_msgs = [m for m in turn2 if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 3  # all kept (pairing intact)
    assert sum(m.content == nodes._TRIMMED_STUB for m in tool_msgs) == 2  # 2 oldest masked
    # the persistent transcript keeps the real observations (masking is input-only)
    assert sum(isinstance(m, ToolMessage) and m.content == "{'r': 1}" for m in convo) == 3


# --- within-turn parallel dispatch (B2, experimental) --------------------------


def _three_call_model() -> _ScriptedModel:
    return _ScriptedModel(
        [
            _FakeAI(
                [
                    {"name": "graph_query", "args": {}, "id": "t1"},
                    {"name": "retrieve", "args": {}, "id": "t2"},
                    {"name": "graph_outline", "args": {}, "id": "t3"},
                ]
            ),
            _FakeAI([], content="done"),
        ]
    )


def test_run_gather_loop_parallel_preserves_toolmessage_order() -> None:
    convo = nodes.run_gather_loop(
        _three_call_model(),
        lambda n, a: {"tool": n},
        [("user", "q")],
        max_steps=8,
        parallel_dispatch=True,
        max_parallel_tools=3,
    )
    ids = [m.tool_call_id for m in convo if isinstance(m, ToolMessage)]
    assert ids == ["t1", "t2", "t3"]  # ex.map preserves submission order -> pairing intact


def test_run_gather_loop_parallel_disabled_is_serial() -> None:
    calls: list[str] = []
    nodes.run_gather_loop(
        _three_call_model(),
        lambda n, a: calls.append(n) or {"ok": 1},
        [("user", "q")],
        max_steps=8,
        parallel_dispatch=False,
    )
    assert calls == ["graph_query", "retrieve", "graph_outline"]  # serial, in order


def test_run_gather_loop_parallel_runs_concurrently() -> None:
    # A 3-party barrier only releases if all three dispatches run AT ONCE — a definitive
    # concurrency proof immune to timing jitter. Serial dispatch would block on the first call,
    # time out the barrier, and leave `passed` empty.
    barrier = threading.Barrier(3, timeout=5.0)
    passed: list[str] = []
    plock = threading.Lock()

    def dispatch(name: str, args: dict) -> dict:
        barrier.wait()  # returns only when all 3 are concurrently in flight
        with plock:
            passed.append(name)
        return {"ok": name}

    nodes.run_gather_loop(
        _three_call_model(),
        dispatch,
        [("user", "q")],
        max_steps=8,
        parallel_dispatch=True,
        max_parallel_tools=3,
    )
    assert sorted(passed) == ["graph_outline", "graph_query", "retrieve"]  # all 3 cleared together


def test_run_gather_loop_parallel_surfaces_tool_error() -> None:
    def dispatch(name: str, args: dict) -> dict:
        if name == "retrieve":
            raise RuntimeError("kaboom")
        return {"ok": name}

    convo = nodes.run_gather_loop(
        _three_call_model(),
        dispatch,
        [("user", "q")],
        max_steps=8,
        parallel_dispatch=True,
        max_parallel_tools=3,
    )
    tool_msgs = [m for m in convo if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 3  # every call produced a ToolMessage, the burst did not crash
    assert any("kaboom" in str(m.content) for m in tool_msgs)  # error surfaced, not raised


def test_run_gather_loop_parallel_skips_dispatch_past_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # time.sleep is a suite-wide no-op (conftest), so DRIVE the monotonic clock instead (per the
    # conftest note "deadline tests drive monotonic"): the FIRST reading (the outer-loop check) is
    # under the deadline so the burst proceeds, every LATER reading (the per-call _run_one checks)
    # is past it — so each parallel call skips its dispatch and returns the sentinel. The clock fn
    # is thread-safe because the parallel _run_one checks read it concurrently.
    first = {"pending": True}
    guard = threading.Lock()

    def fake_monotonic() -> float:
        with guard:
            if first["pending"]:
                first["pending"] = False
                return 0.0
        return 100.0

    monkeypatch.setattr(react_loop.time, "monotonic", fake_monotonic)
    dispatched: list[str] = []
    model = _ScriptedModel(
        [
            _FakeAI(
                [
                    {"name": "retrieve", "args": {}, "id": "t1"},
                    {"name": "retrieve", "args": {}, "id": "t2"},
                ]
            )
        ]
    )
    convo = nodes.run_gather_loop(
        model,
        lambda n, a: dispatched.append(n) or {"ok": 1},
        [("user", "q")],
        max_steps=8,
        deadline=5.0,
        parallel_dispatch=True,
        max_parallel_tools=2,
    )
    assert dispatched == []  # nothing dispatched after the deadline
    sentinels = [m for m in convo if isinstance(m, ToolMessage)]
    assert sentinels  # both calls still produced a (sentinel) ToolMessage -> pairing intact
    assert all("skipped" in str(m.content) for m in sentinels)
