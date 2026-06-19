"""Unit tests for the agentic loop's pure node logic (knowledge.agentic_nodes)."""

from __future__ import annotations

import json

from rag_cti.knowledge import agentic_nodes as nodes
from rag_cti.knowledge.agentic_state import AgenticAnswer, SufficiencyVerdict
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.types import Chunk, FactRow, GeneratedAnswer, QueryResult, RetrievalResult


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
    assert nodes.decide_next(
        _verdict(), iteration_count=3, tokens_used=0, max_iterations=3, token_ceiling=100
    ) == ("synthesize", "budget")


def test_decide_next_token_ceiling_is_budget() -> None:
    assert nodes.decide_next(
        _verdict(), iteration_count=1, tokens_used=100, max_iterations=3, token_ceiling=100
    ) == ("synthesize", "budget")


def test_decide_next_none_verdict_is_parse_fallback() -> None:
    assert nodes.decide_next(
        None, iteration_count=1, tokens_used=0, max_iterations=3, token_ceiling=100
    ) == ("synthesize", "parse_fallback")


def test_decide_next_stop_is_sufficient() -> None:
    assert nodes.decide_next(
        _verdict("stop"), iteration_count=1, tokens_used=0, max_iterations=3, token_ceiling=100
    ) == ("synthesize", "sufficient")


def test_decide_next_continue_is_agent_turn() -> None:
    assert nodes.decide_next(
        _verdict("retrieve_more"),
        iteration_count=1,
        tokens_used=0,
        max_iterations=3,
        token_ceiling=100,
    ) == ("agent_turn", "")


# --- build_directives ----------------------------------------------------------


def test_build_directives_includes_gaps_queries_targets() -> None:
    v = SufficiencyVerdict(
        coverage_gaps=("what malware",),
        suggested_queries=("APT29 malware",),
        suggested_graph_targets=(("actor_G0016", "uses", "family"),),
    )
    d = nodes.build_directives(v)
    assert "Still missing: what malware" in d
    assert "Try vector_search for: APT29 malware" in d
    assert "Try graph_query: actor_G0016 (uses, family)" in d


def test_build_directives_empty_default() -> None:
    assert (
        nodes.build_directives(SufficiencyVerdict())
        == "Gather more evidence to fully answer the question."
    )


def test_build_directives_graph_target_without_slots() -> None:
    v = SufficiencyVerdict(suggested_graph_targets=(("ip_1", None, None),))
    assert "Try graph_query: ip_1" in nodes.build_directives(v)


# --- assemble_citations (the grounding guarantee) ------------------------------


def test_assemble_citations_keeps_real_drops_hallucinated() -> None:
    led = _ledger_with_chunks(_result("c1"))
    led.add_facts((_row("f1"),))
    kept, dropped = nodes.assemble_citations("uses [c1] and [f1] but also [fake99]", led)
    assert kept == ("c1", "f1")
    assert dropped == 1


# --- synthesize_answer + build_agentic_answer ----------------------------------


class _FakeGenerator:
    def __init__(self, answer_text: str) -> None:
        self._text = answer_text
        self.seen: QueryResult | None = None

    def generate(
        self, query: str, query_result: QueryResult, raise_on_failure: bool = False
    ) -> GeneratedAnswer:
        self.seen = query_result
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
