"""Runtime harness contracts and conservative supervisor admission.

This module sits above retrieval query rewriting. Retrieval subqueries remain search hints;
only an explicit validated decomposition can admit the supervisor path.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from rag_cti.retrieval.constraint_extract import ExtractedEntity, build_constraint
from rag_cti.types import PayloadConstraint, QueryResult

if TYPE_CHECKING:
    from rag_cti.config import Settings
    from rag_cti.knowledge.agentic_nodes import JudgeFn
    from rag_cti.knowledge.composer import ComposeFn
    from rag_cti.knowledge.fact_store import FactStoreProto

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

    settings: Settings
    retrieval_pipeline: object
    run_retrieve: Callable[[str, int], QueryResult]
    fact_store: FactStoreProto | None
    ontology_nodes: list[dict[str, object]]
    query_understanding: Callable[[str, list[str] | None], RuntimeQueryUnderstanding]
    gather_model: Any
    generator: object
    judge: JudgeFn
    composer: ComposeFn


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

_RUNTIME_UNDERSTANDING_SYSTEM = """You are the runtime query-understanding step for a CTI RAG agent.
Return ONLY one JSON object with these keys:
- "standalone_query": a history-resolved version of the latest user question.
- "retrieval_queries": one or more CTI search queries. These are retrieval hints, not worker branches.
- "entities": explicitly named CTI entities, each {"name": string, "type": "actor"|"family"|"technique"}.
- "decomposition": null OR an object with:
  - "suitable_for_supervisor": boolean
  - "dependency_reason": string, empty unless branches are sequentially dependent
  - "task_requires_composition": boolean
  - "reason": string
  - "branches": array of independent worker branches, each with
    {"branch_id": string, "sub_question": string, "focus_entity": string|null,
     "facet": string|null, "independent_reason": string}
- "confidence": number from 0 to 1.

Supervisor branches are only for independent work that can be gathered in parallel and composed.
Use them for explicit comparisons, shared/distinct technique questions, or independent facets.
Do NOT use them for simple questions, retrieval-only subqueries, sequential/dependent chains, or
questions where later branches depend on discoveries from earlier branches.
For comparison/shared/distinct questions with two or more branches, set task_requires_composition
to true and dependency_reason to "".
If a branch is proposed, it must have a specific sub_question and an independent_reason.
Do not invent entities or facts not present in the query/history."""


def build_runtime_query_understanding(
    query: str,
    history: list[str] | None,
    *,
    pipeline: object,
    settings: object,
    ontology_nodes: list[dict[str, object]],
) -> RuntimeQueryUnderstanding:
    """Build the runtime understanding contract before orchestration selection.

    This intentionally separates retrieval hints from supervisor branches. The retrieval
    rewriter may provide a good fallback set of queries/entities, but supervisor admission
    requires the runtime prompt to return an explicit decomposition object.
    """

    retrieval_queries, entities, constraint, retrieval_reason = _retrieval_understanding(
        query,
        history,
        pipeline=pipeline,
        settings=settings,
        ontology_nodes=ontology_nodes,
    )
    raw = _generate_runtime_understanding(query, history, pipeline, settings)
    if raw is None:
        return RuntimeQueryUnderstanding(
            original_query=query,
            standalone_query=retrieval_queries[0] if retrieval_queries else query,
            retrieval_queries=retrieval_queries,
            entities=entities,
            payload_constraint=constraint,
            status="fallback",
            fallback_reason="runtime_understanding_unavailable",
            confidence=0.0,
            reason=retrieval_reason,
        )
    parsed = _parse_runtime_understanding(raw)
    if parsed is None:
        return RuntimeQueryUnderstanding(
            original_query=query,
            standalone_query=retrieval_queries[0] if retrieval_queries else query,
            retrieval_queries=retrieval_queries,
            entities=entities,
            payload_constraint=constraint,
            status="parse_error",
            fallback_reason="runtime_understanding_parse_error",
            confidence=0.0,
            reason=retrieval_reason,
        )
    standalone_query = parsed.get("standalone_query")
    runtime_queries = _parse_string_tuple(parsed.get("retrieval_queries"))
    runtime_entities = _parse_entities(parsed.get("entities"))
    out_entities = runtime_entities or entities
    out_queries = runtime_queries or retrieval_queries
    return RuntimeQueryUnderstanding(
        original_query=query,
        standalone_query=standalone_query.strip()
        if isinstance(standalone_query, str) and standalone_query.strip()
        else (out_queries[0] if out_queries else query),
        retrieval_queries=out_queries,
        entities=out_entities,
        payload_constraint=constraint,
        decomposition=_parse_decomposition(parsed.get("decomposition")),
        status="ok",
        fallback_reason="",
        confidence=_parse_confidence(parsed.get("confidence")),
        reason="runtime_query_understanding",
    )


def _retrieval_understanding(
    query: str,
    history: list[str] | None,
    *,
    pipeline: object,
    settings: object,
    ontology_nodes: list[dict[str, object]],
) -> tuple[tuple[str, ...], tuple[ExtractedEntity, ...], PayloadConstraint | None, str]:
    try:
        retriever = getattr(pipeline, "_retriever", None)
        rewriter = getattr(retriever, "_rewriter", None)
        rewrite_with_entities = getattr(rewriter, "rewrite_with_entities", None)
        rewrite = getattr(rewriter, "rewrite", None)
        if callable(rewrite_with_entities):
            out = rewrite_with_entities(query, history)
            retrieval_queries = out.queries
            entities = out.entities
        elif callable(rewrite):
            retrieval_queries = tuple(rewrite(query, history))
            entities = ()
        else:
            retrieval_queries = (query,)
            entities = ()
        constraint = (
            build_constraint(query, entities, ontology_nodes)
            if bool(getattr(settings, "constraint_routing_enabled", False))
            else None
        )
        return retrieval_queries, entities, constraint, "retrieval_understanding"
    except Exception as exc:
        _ = exc
        return (query,), (), None, f"retrieval_understanding_error:{type(exc).__name__}"


def _generate_runtime_understanding(
    query: str,
    history: list[str] | None,
    pipeline: object,
    settings: object | None = None,
) -> str | None:
    retriever = getattr(pipeline, "_retriever", None)
    rewriter = getattr(retriever, "_rewriter", None)
    generate = getattr(rewriter, "_generate_raw", None)
    if not callable(generate):
        return None
    max_tokens = max(1200, int(getattr(settings, "query_rewrite_max_tokens", 300)) * 4)
    try:
        generated = generate(
            _RUNTIME_UNDERSTANDING_SYSTEM,
            _runtime_understanding_user_prompt(query, history),
            max_tokens=max_tokens,
        )
        return generated if isinstance(generated, str) else None
    except TypeError:
        generated = generate(
            _RUNTIME_UNDERSTANDING_SYSTEM, _runtime_understanding_user_prompt(query, history)
        )
        return generated if isinstance(generated, str) else None


def _runtime_understanding_user_prompt(query: str, history: list[str] | None) -> str:
    prefix = ""
    if history:
        turns = "\n".join(f"- {h}" for h in history)
        prefix = f"Conversation so far (most recent last):\n{turns}\n\n"
    return f"{prefix}Latest query: {query}"


def _parse_runtime_understanding(raw: str) -> dict[str, Any] | None:
    text = _FENCE_RE.sub("", raw.strip())
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_entities(raw: object) -> tuple[ExtractedEntity, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[ExtractedEntity] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        etype = item.get("type")
        if isinstance(name, str) and name.strip() and etype in {"actor", "family", "technique"}:
            out.append(ExtractedEntity(name=name.strip(), type=etype))
    return tuple(out)


def _parse_decomposition(raw: object) -> DecompositionProposal | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    branches = tuple(
        branch
        for branch in (_parse_branch(item, i) for i, item in enumerate(raw.get("branches", []), 1))
        if branch is not None
    )
    dependency_reason = _parse_string(raw.get("dependency_reason"))
    if dependency_reason.lower().startswith("independent"):
        dependency_reason = ""
    return DecompositionProposal(
        branches=branches,
        suitable_for_supervisor=bool(raw.get("suitable_for_supervisor", False)),
        dependency_reason=dependency_reason,
        task_requires_composition=_parse_task_requires_composition(raw, branches),
        reason=_parse_string(raw.get("reason")),
    )


def _parse_branch(raw: object, index: int) -> ProposedBranch | None:
    if not isinstance(raw, dict):
        return None
    sub_question = _parse_string(raw.get("sub_question"))
    if not sub_question:
        return None
    return ProposedBranch(
        branch_id=_parse_string(raw.get("branch_id")) or f"b{index}",
        sub_question=sub_question,
        focus_entity=_parse_optional_string(raw.get("focus_entity")),
        facet=_parse_optional_string(raw.get("facet")),
        independent_reason=_parse_string(raw.get("independent_reason")),
    )


def _parse_string_tuple(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(item.strip() for item in raw if isinstance(item, str) and item.strip())


def _parse_string(raw: object) -> str:
    return raw.strip() if isinstance(raw, str) else ""


def _parse_optional_string(raw: object) -> str | None:
    value = _parse_string(raw)
    return value or None


def _parse_confidence(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, value))


def _parse_task_requires_composition(
    raw: dict[str, object], branches: tuple[ProposedBranch, ...]
) -> bool:
    value = raw.get("task_requires_composition", True)
    reason = _parse_string(raw.get("reason")).lower()
    branch_text = " ".join(b.sub_question.lower() for b in branches)
    comparison_signal = any(
        word in f"{reason} {branch_text}"
        for word in ("compare", "comparison", "shared", "distinct", "versus", " vs ")
    )
    if bool(raw.get("suitable_for_supervisor", False)) and len(branches) >= 2 and comparison_signal:
        return True
    return bool(value)


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
        if b.sub_question.strip() and b.independent_reason.strip() and (b.focus_entity or b.facet)
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
