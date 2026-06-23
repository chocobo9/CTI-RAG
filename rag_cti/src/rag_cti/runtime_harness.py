"""Runtime harness contracts and conservative supervisor admission.

This module sits above retrieval query rewriting. Retrieval subqueries remain search hints;
only an explicit validated decomposition can admit the supervisor path.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from rag_cti.retrieval.constraint_extract import ExtractedEntity
from rag_cti.types import PayloadConstraint, QueryResult

AdmissionDecision = Literal["single_agent", "supervisor"]
UnderstandingStatus = Literal["ok", "fallback", "parse_error"]
BranchStatus = Literal["ok", "partial", "empty", "failed"]


@dataclass(frozen=True)
class ProposedBranch:
    """One independent supervisor branch proposed by runtime query understanding."""

    branch_id: str
    sub_question: str
    focus_entity: str | None = None
    facet: str | None = None
    independent_reason: str = ""


@dataclass(frozen=True)
class DecompositionProposal:
    """A validated-looking plan candidate; admission still makes the final decision."""

    branches: tuple[ProposedBranch, ...] = ()
    suitable_for_supervisor: bool = False
    dependency_reason: str = ""
    task_requires_composition: bool = True
    reason: str = ""


@dataclass(frozen=True)
class RuntimeQueryUnderstanding:
    """Runtime-level understanding result consumed by the production answer harness."""

    original_query: str
    standalone_query: str
    retrieval_queries: tuple[str, ...] = ()
    entities: tuple[ExtractedEntity, ...] = ()
    payload_constraint: PayloadConstraint | None = None
    decomposition: DecompositionProposal | None = None
    status: UnderstandingStatus = "ok"
    fallback_reason: str = ""
    confidence: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class AdmissionResult:
    """Supervisor admission decision with the validated branch plan and reason."""

    decision: AdmissionDecision
    reason: str
    branches: tuple[ProposedBranch, ...] = ()

    @property
    def admitted(self) -> bool:
        return self.decision == "supervisor"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.decision == other
        return super().__eq__(other)


@dataclass(frozen=True)
class RuntimeDeps:
    """Reusable services and provider policy shared by runtime answer paths.

    Per-run state such as the understanding result, admission decision, evidence ledgers,
    branch reports, and answers intentionally does not live here.
    """

    settings: object
    retrieval_pipeline: object
    run_retrieve: Callable[[str, int], QueryResult]
    fact_store: object | None
    ontology_nodes: list[dict[str, object]]
    query_understanding: Callable[[str, list[str] | None], RuntimeQueryUnderstanding]
    gather_model: object
    generator: object
    judge: object
    composer: object


def evaluate_supervisor_admission(
    understanding: RuntimeQueryUnderstanding,
    *,
    max_branches: int,
) -> AdmissionResult:
    """Conservatively validate a supervisor branch plan."""

    if understanding.status != "ok":
        reason = understanding.fallback_reason or f"understanding_status_{understanding.status}"
        return AdmissionResult("single_agent", reason)
    proposal = understanding.decomposition
    if proposal is None or not proposal.suitable_for_supervisor:
        return AdmissionResult("single_agent", "no_suitable_decomposition")
    if proposal.dependency_reason.strip():
        return AdmissionResult("single_agent", "dependent_branches")
    if not proposal.task_requires_composition:
        return AdmissionResult("single_agent", "composition_not_required")
    branches = tuple(
        b
        for b in proposal.branches
        if b.sub_question.strip()
        and b.independent_reason.strip()
        and (b.focus_entity or b.facet)
    )
    if len(branches) < 2:
        return AdmissionResult("single_agent", "fewer_than_two_valid_branches", branches)
    if len(branches) > max_branches:
        return AdmissionResult("single_agent", "branch_count_exceeds_cap", branches)
    if tuple(b.sub_question for b in branches) == understanding.retrieval_queries:
        return AdmissionResult("single_agent", "branches_match_retrieval_queries", branches)
    return AdmissionResult("supervisor", "validated_independent_branches", branches)


def admit_supervisor(
    understanding: RuntimeQueryUnderstanding,
    *,
    max_branches: int,
) -> AdmissionDecision:
    """Back-compatible thin wrapper returning only the decision."""

    return evaluate_supervisor_admission(understanding, max_branches=max_branches).decision
