from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from rag_cti.knowledge.agentic_state import AgenticAnswer
from rag_cti.retrieval.constraint_extract import ExtractedEntity, RewriteOutput
from rag_cti.runtime_harness import (
    DecompositionProposal,
    ProposedBranch,
    RuntimeQueryUnderstanding,
    admit_supervisor,
    build_runtime_query_understanding,
    evaluate_supervisor_admission,
)
from rag_cti.types import PayloadConstraint, QueryResult


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
        patch(
            "rag_cti.knowledge.agentic_graph.run_agentic_answer", return_value=_agentic_answer("q")
        ) as agentic,
        patch("rag_cti.knowledge.supervisor_graph.run_supervised_answer") as supervised,
    ):
        ans = rag_cti.answer("q")

    assert ans.model == "agentic"
    assert agentic.called
    assert not supervised.called
    assert meta.call_args.kwargs["runtime_path"] == "single_agent"
    assert meta.call_args.kwargs["admission_reason"] == "supervisor_disabled"


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
        patch("rag_cti.knowledge.agentic_graph.run_agentic_answer") as agentic,
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
