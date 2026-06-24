"""Runtime harness contracts and conservative supervisor admission.

This module sits above retrieval query rewriting. Retrieval subqueries remain search hints;
only an explicit validated decomposition can admit the supervisor path.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from rag_cti.retrieval.constraint_extract import ExtractedEntity, build_constraint
from rag_cti.types import PayloadConstraint, QueryResult

AdmissionDecision = Literal["single_agent", "supervisor"]
UnderstandingStatus = Literal["ok", "fallback", "parse_error"]
BranchStatus = Literal["ok", "partial", "empty", "failed"]
RuntimeObservationStatus = Literal["ok", "error", "rejected", "invalid", "no_action"]


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


@dataclass
class RuntimeInvestigationState:
    """Runtime-owned state for one agentic investigation.

    This is intentionally a thin Phase-1 trunk over the existing EvidenceLedger and
    node helpers. Tool side effects still update the ledger through legacy adapters,
    but the repeating investigation loop is owned here rather than by LangGraph wiring.
    """

    ledger: Any
    messages: list[Any] = field(default_factory=list)
    iteration_count: int = 0
    tokens_used: int = 0
    new_evidence: int = 0
    new_facts: int = 0
    sufficiency: Any | None = None
    prev_gaps: tuple[str, ...] = ()
    open_categories: int = 0
    open_cat_stall: int = 0
    stop_reason: str = ""
    provider_error: bool = False
    observations: list[RuntimeObservation] = field(default_factory=list)
    events: list[RuntimeEvent] = field(default_factory=list)


@dataclass(frozen=True)
class RuntimeObservation:
    """Runtime-owned observation produced from one action/tool boundary outcome."""

    observation_id: str
    turn_index: int
    action_id: str
    tool_name: str
    args_summary: str
    status: RuntimeObservationStatus
    error_kind: str = ""
    error_message: str = ""
    result_summary: str = ""
    ledger_delta: dict[str, Any] = field(default_factory=dict)
    model_visible_content: str = ""
    event_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeTurnResult:
    """Result of one runtime-owned gather turn."""

    messages: list[Any]
    tokens_used: int
    new_evidence: int
    new_facts: int
    provider_error: bool = False
    observations: tuple[RuntimeObservation, ...] = ()
    events: tuple[RuntimeEvent, ...] = ()


@dataclass(frozen=True)
class RuntimeEvent:
    """Small runtime event envelope for Phase-2 boundary accounting.

    This is not the full trajectory/event store. It is the minimal seam that lets
    runtime-owned turns report action validation, tool execution, and provider
    outcomes without callers scraping ToolMessage text.
    """

    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_observation(cls, observation: RuntimeObservation) -> RuntimeEvent:
        kind_by_status = {
            "ok": "tool_result",
            "error": "tool_error" if observation.tool_name else "provider_error",
            "rejected": "tool_call_rejected",
            "invalid": "invalid_tool_call",
            "no_action": "no_tool_call",
        }
        kind = kind_by_status.get(observation.status, observation.status)
        if observation.error_kind == "provider_error":
            kind = "provider_error"
        metadata = {
            "observation_id": observation.observation_id,
            "turn_index": observation.turn_index,
            "action_id": observation.action_id,
            "tool_name": observation.tool_name,
            "status": observation.status,
            "args_summary": observation.args_summary,
            "error_kind": observation.error_kind,
            "error_message": observation.error_message,
            "ledger_delta": observation.ledger_delta,
            **observation.event_metadata,
        }
        return cls(kind=kind, metadata=metadata)


def apply_observation_to_state(
    state: RuntimeInvestigationState, observation: RuntimeObservation
) -> RuntimeEvent:
    """Record a runtime-owned observation on investigation state.

    Phase 3 keeps legacy tool side effects for ledger mutation, but makes the
    state-update seam explicit so a later reducer can move the actual ledger writes
    behind this function.
    """
    event = RuntimeEvent.from_observation(observation)
    state.observations.append(observation)
    state.events.append(event)
    return event


@dataclass(frozen=True)
class RuntimeInvestigationResult:
    """Internal result for runtime-owned investigations that need the ledger."""

    ledger: Any
    answer: Any


_RUNTIME_GATHER_SYSTEM = """You are a CTI analyst GATHERING evidence for a question. Your ONLY job is to call \
tools to collect the facts and prose needed to answer it. Another step writes the final answer, so do \
NOT write the answer yourself.

Tools:
- resolve_entity(name): a CTI name like "APT29" -> entity_id(s). The graph tools need an entity_id.
- graph_outline(subject_id): which relation categories a subject has and how many of each.
- graph_query(subject_id, predicate, object_type): the exact, exhaustive facts in one category. It \
records the COMPLETE set and reports `total` + `complete: true` - once you query a category you already \
hold all of it, so never query the same category twice.
- facts_for_evidence(chunk_id): which facts a given evidence chunk supports.
- retrieve(query): semantic search over source prose, for explanation/context the graph lacks.

How to gather:
- Graph for who/what/enumerate (exact and exhaustive); retrieve for why/how/explain prose.
- Plan minimally: resolve the entity, outline it, query the relevant category ONCE, optionally retrieve \
prose. Never repeat a tool call you have already made.
- A verifier may hand you specific gaps to fill - gather exactly those.
- When you have gathered enough to answer, STOP: emit no further tool call. Do not write the answer."""


def _sum_tokens(messages: list[Any]) -> int:
    total = 0
    for message in messages:
        usage = getattr(message, "usage_metadata", None)
        if isinstance(usage, dict):
            total += int(usage.get("total_tokens", 0) or 0)
    return total


def _normalize_runtime_tool_args(
    name: str, args: dict[str, Any], *, retrieve_query_max_chars: int
) -> dict[str, Any]:
    if name != "retrieve":
        return args
    query = str(args.get("query", "") or "")
    compact_query = " ".join(query.split())
    if retrieve_query_max_chars > 0 and len(compact_query) > retrieve_query_max_chars:
        compact_query = compact_query[:retrieve_query_max_chars].rsplit(" ", 1)[0].strip()
    if compact_query == query:
        return args
    return {**args, "query": compact_query}


class RuntimeTurnAdapter:
    """Adapter for one runtime gather turn over the legacy tool stack.

    The adapter may use LangChain tools and ``react_loop`` internally, but it does not
    own the repeating investigation loop. It performs one model turn/tool burst and
    returns a bounded result for the runtime trunk to evaluate.
    """

    def __init__(
        self,
        *,
        settings: object,
        query: str,
        history: list[str] | None,
        run_retrieve: Callable[[str, int], QueryResult],
        fact_store: object | None,
        ontology_nodes: list[dict[str, Any]],
        chat_model: Any,
        ledger: Any,
        deadline: float | None,
    ) -> None:
        self._settings = settings
        self._query = query
        self._history = history
        self._ledger = ledger
        self._deadline = deadline
        self._tools = self._build_tools(fact_store, ontology_nodes, run_retrieve, ledger)
        self._model_with_tools = chat_model.bind_tools(self._tools)
        self._tools_by_name = {tool.name: tool for tool in self._tools}
        self._dispatch_lock = threading.Lock()
        self._event_lock = threading.Lock()
        self._current_turn_index = 0
        self._turn_observations: list[RuntimeObservation] = []
        self._turn_events: list[RuntimeEvent] = []

        from rag_cti.knowledge import agentic_effort

        self._effort_tier = agentic_effort.classify_effort_tier(query)
        hard_tool_budgets = getattr(
            settings,
            "agentic_hard_tool_budgets",
            {"simple": 10, "comparison": 20, "complex": 32},
        )
        self._hard_tool_budget = int(hard_tool_budgets.get(self._effort_tier, 0))

    @staticmethod
    def _ledger_snapshot(ledger: Any) -> dict[str, set[str] | int]:
        return {
            "chunks": set(ledger.chunks),
            "facts": set(ledger.facts),
            "outlines": set(ledger.outlines),
            "actions": len(ledger.actions),
        }

    @staticmethod
    def _ledger_delta(before: dict[str, set[str] | int], after: dict[str, set[str] | int]) -> dict[str, Any]:
        before_chunks = before["chunks"] if isinstance(before["chunks"], set) else set()
        after_chunks = after["chunks"] if isinstance(after["chunks"], set) else set()
        before_facts = before["facts"] if isinstance(before["facts"], set) else set()
        after_facts = after["facts"] if isinstance(after["facts"], set) else set()
        before_outlines = before["outlines"] if isinstance(before["outlines"], set) else set()
        after_outlines = after["outlines"] if isinstance(after["outlines"], set) else set()
        before_actions = before["actions"] if isinstance(before["actions"], int) else 0
        after_actions = after["actions"] if isinstance(after["actions"], int) else 0
        return {
            "added_chunk_ids": sorted(after_chunks - before_chunks),
            "added_fact_ids": sorted(after_facts - before_facts),
            "added_outline_ids": sorted(after_outlines - before_outlines),
            "actions_added": max(0, after_actions - before_actions),
        }

    @staticmethod
    def _summarize_result(result: Any, limit: int = 800) -> str:
        text = str(result)
        return text if len(text) <= limit else text[:limit].rstrip() + "..."

    def _make_observation(
        self,
        *,
        tool_name: str = "",
        args: dict[str, Any] | None = None,
        status: RuntimeObservationStatus,
        result: Any = "",
        error_kind: str = "",
        error_message: str = "",
        before: dict[str, set[str] | int] | None = None,
        event_metadata: dict[str, Any] | None = None,
    ) -> RuntimeObservation:
        from rag_cti.knowledge.tool_cache import canonicalize_args

        index = len(self._turn_observations) + 1
        action_id = f"turn-{self._current_turn_index}-action-{index}" if tool_name else ""
        observation_id = f"turn-{self._current_turn_index}-observation-{index}"
        after = self._ledger_snapshot(self._ledger)
        ledger_delta = self._ledger_delta(before or after, after)
        result_summary = self._summarize_result(result)
        if status == "no_action":
            model_visible_content = "No tool call proposed."
        elif status == "invalid":
            model_visible_content = f"Invalid tool call: {tool_name}"
        elif status == "rejected":
            model_visible_content = result_summary or f"Tool call rejected: {tool_name}"
        elif status == "error":
            model_visible_content = result_summary or f"{tool_name or 'provider'} failed: {error_message}"
        else:
            model_visible_content = result_summary
        return RuntimeObservation(
            observation_id=observation_id,
            turn_index=self._current_turn_index,
            action_id=action_id,
            tool_name=tool_name,
            args_summary=canonicalize_args(args or {}) if args else "",
            status=status,
            error_kind=error_kind,
            error_message=error_message,
            result_summary=result_summary,
            ledger_delta=ledger_delta,
            model_visible_content=model_visible_content,
            event_metadata=event_metadata or {},
        )

    def _record_observation(self, observation: RuntimeObservation) -> None:
        with self._event_lock:
            self._turn_observations.append(observation)
            self._turn_events.append(RuntimeEvent.from_observation(observation))

    @staticmethod
    def _build_tools(
        fact_store: object | None,
        ontology_nodes: list[dict[str, Any]],
        run_retrieve: Callable[[str, int], QueryResult],
        ledger: Any,
    ) -> list[Any]:
        from langchain_core.tools import tool

        from rag_cti.knowledge import agent_tools

        @tool
        def resolve_entity(name: str) -> list[dict[str, str]]:
            """Resolve a threat-intel name (e.g. 'APT29') to entity_id candidates."""
            if fact_store is None:
                return []
            return agent_tools.resolve_entity_candidates(name, ontology_nodes)

        @tool
        def graph_outline(subject_id: str) -> dict[str, Any]:
            """Coverage map for a subject_id: which relation categories exist and how many."""
            if fact_store is None:
                return {"found": False, "entity_id": subject_id}
            return agent_tools.outline_to_ledger(fact_store, ledger, subject_id)  # type: ignore[arg-type]

        @tool
        def graph_query(
            subject_id: str,
            predicate: str | None = None,
            object_type: str | None = None,
            min_credibility: float = 0.0,
        ) -> dict[str, Any]:
            """Enumerate the exact facts for (subject_id[, predicate, object_type])."""
            if fact_store is None:
                return {"total": 0, "shown": 0, "truncated": False, "objects": []}
            return agent_tools.graph_query_to_ledger(  # type: ignore[arg-type]
                fact_store,
                ledger,
                subject_id=subject_id,
                predicate=predicate,
                object_type=object_type,
                min_credibility=min_credibility,
            )

        @tool
        def facts_for_evidence(chunk_id: str) -> dict[str, Any]:
            """Which facts a given evidence chunk_id supports (reverse provenance bridge)."""
            if fact_store is None:
                return {"count": 0, "facts": []}
            return agent_tools.facts_for_evidence_to_ledger(fact_store, ledger, chunk_id)  # type: ignore[arg-type]

        @tool
        def retrieve(query: str, top_k: int = 10) -> dict[str, Any]:
            """Semantic search over source prose; returns chunk snippets."""
            return agent_tools.retrieve_to_ledger(run_retrieve, ledger, query, top_k)

        return [resolve_entity, graph_outline, graph_query, facts_for_evidence, retrieve]

    def _dispatch(self, name: str, args: dict[str, Any]) -> Any:
        from rag_cti.knowledge import agentic_nodes, tool_cache

        before = self._ledger_snapshot(self._ledger)
        tool = self._tools_by_name.get(name)
        if tool is None:
            result = {"error": f"unknown tool {name}"}
            observation = self._make_observation(
                tool_name=name,
                args=args,
                status="invalid",
                result=result,
                error_kind="unknown_tool",
                error_message=f"unknown tool {name}",
                before=before,
            )
            self._record_observation(observation)
            return observation.model_visible_content
        args = _normalize_runtime_tool_args(
            name,
            args,
            retrieve_query_max_chars=int(
                getattr(self._settings, "agentic_retrieve_query_max_chars", 360)
            ),
        )
        with self._dispatch_lock:
            if self._hard_tool_budget > 0 and len(self._ledger.actions) >= self._hard_tool_budget:
                result = {
                    "error": "tool budget exhausted",
                    "max_tool_calls": self._hard_tool_budget,
                    "executed_tool_calls": len(self._ledger.actions),
                }
                observation = self._make_observation(
                    tool_name=name,
                    args=args,
                    status="rejected",
                    result=result,
                    error_kind="tool_budget_exhausted",
                    error_message="tool budget exhausted",
                    before=before,
                )
                self._record_observation(observation)
                return observation.model_visible_content
            self._ledger.add_action(name, args)
        if name == "retrieve" and agentic_nodes.should_suppress_retrieve_after_graph_coverage(
            self._query, self._ledger
        ):
            result = {
                "error": "retrieve suppressed: graph evidence is already sufficient",
                "reason": "complete graph uses->technique facts cover the comparison",
            }
            observation = self._make_observation(
                tool_name=name,
                args=args,
                status="rejected",
                result=result,
                error_kind="retrieve_suppressed_after_graph_coverage",
                error_message="retrieve suppressed: graph evidence is already sufficient",
                before=before,
            )
            self._record_observation(observation)
            return observation.model_visible_content
        hit = self._ledger.cache_get(name, args)
        if hit is not None:
            result = tool_cache.as_duplicate(hit)
            observation = self._make_observation(
                tool_name=name,
                args=args,
                status="ok",
                result=result,
                before=before,
                event_metadata={"duplicate": True},
            )
            self._record_observation(observation)
            return observation.model_visible_content
        try:
            result = tool.invoke(args)
        except Exception as exc:
            result = {"error": f"{name} failed: {exc}"}
            observation = self._make_observation(
                tool_name=name,
                args=args,
                status="error",
                result=result,
                error_kind=type(exc).__name__,
                error_message=str(exc),
                before=before,
            )
            self._record_observation(observation)
            return observation.model_visible_content
        self._ledger.cache_put(name, args, result)
        observation = self._make_observation(
            tool_name=name,
            args=args,
            status="ok",
            result=result,
            before=before,
            event_metadata={"duplicate": False},
        )
        self._record_observation(observation)
        return observation.model_visible_content

    def _render_context(self) -> str:
        from rag_cti.knowledge import agentic_effort, agentic_nodes

        blocks: list[str] = []
        blocks.append(agentic_nodes.render_state_view(self._ledger))
        blocks.append(agentic_nodes.render_action_log(self._ledger))
        blocks.append(
            agentic_effort.render_budget_line(
                self._effort_tier,
                len(self._ledger.actions),
                getattr(self._settings, "agentic_effort_budgets", {}),
            )
        )
        return "\n\n".join(block for block in blocks if block)

    def run_turn(self, state: RuntimeInvestigationState) -> RuntimeTurnResult:
        from rag_cti.knowledge import agentic_nodes
        from rag_cti.knowledge.react_loop import run_react_tool_loop

        self._current_turn_index = state.iteration_count + 1
        self._turn_observations = []
        self._turn_events = []
        messages = agentic_nodes.build_turn_messages(
            _RUNTIME_GATHER_SYSTEM,
            self._query,
            state.sufficiency,
            self._ledger,
            history=self._history,
        )
        before_facts = len(self._ledger.facts)
        before = before_facts + len(self._ledger.chunks)
        errors: list[BaseException] = []
        out_messages = run_react_tool_loop(
            self._model_with_tools,
            self._dispatch,
            messages,
            max_steps=1,
            deadline=self._deadline,
            on_model_error=errors.append,
            render_state=self._render_context,
            keep_last_observations=int(getattr(self._settings, "agentic_keep_last_observations", 0)),
            parallel_dispatch=bool(
                getattr(self._settings, "agentic_parallel_dispatch_enabled", False)
            ),
            max_parallel_tools=int(getattr(self._settings, "agentic_max_parallel_tools", 1)),
        )
        if errors:
            observation = self._make_observation(
                status="error",
                error_kind="provider_error",
                error_message=str(errors[-1]),
                result={"error": f"provider failed: {errors[-1]}"},
            )
            self._record_observation(observation)
        elif not self._turn_observations:
            observation = self._make_observation(status="no_action")
            self._record_observation(observation)
        return RuntimeTurnResult(
            messages=out_messages,
            tokens_used=_sum_tokens(out_messages),
            new_evidence=len(self._ledger.facts) + len(self._ledger.chunks) - before,
            new_facts=len(self._ledger.facts) - before_facts,
            provider_error=bool(errors),
            observations=tuple(self._turn_observations),
            events=tuple(self._turn_events),
        )


def _run_agentic_investigation_result(
    query: str,
    *,
    settings: object,
    history: list[str] | None = None,
    run_retrieve: Callable[[str, int], QueryResult],
    fact_store: object | None,
    ontology_nodes: list[dict[str, Any]],
    generator: Any,
    chat_model: Any,
    judge: Callable[[str, str], str],
    gather_only: bool,
) -> RuntimeInvestigationResult:
    """Run the runtime-owned investigation loop and keep the evidence ledger.

    Phase 1 moves loop ownership into the runtime harness while deliberately
    reusing the existing ledger, tool adapters, sufficiency gate, stop policy, and
    citation guard. The legacy LangGraph wiring remains available for debug/baseline
    callers, but public agentic paths should enter here.
    """

    from rag_cti.knowledge import agentic_nodes
    from rag_cti.knowledge.evidence_ledger import EvidenceLedger
    from rag_cti.observability.tracing import add_trace_metadata, traced
    from rag_cti.types import GeneratedAnswer

    @traced("agentic.investigation", run_type="chain")
    def _run() -> RuntimeInvestigationResult:
        ledger = EvidenceLedger()
        state = RuntimeInvestigationState(ledger=ledger)
        started_at = time.monotonic()
        max_wall_seconds = float(getattr(settings, "agentic_max_wall_seconds", 0.0))
        deadline = started_at + max_wall_seconds if max_wall_seconds > 0 else None
        adapter = RuntimeTurnAdapter(
            settings=settings,
            query=query,
            history=history,
            run_retrieve=run_retrieve,
            fact_store=fact_store,
            ontology_nodes=ontology_nodes,
            chat_model=chat_model,
            ledger=ledger,
            deadline=deadline,
        )

        event_counts: Counter[str] = Counter()
        while True:
            turn = adapter.run_turn(state)
            state.messages = turn.messages
            state.iteration_count += 1
            state.tokens_used += turn.tokens_used
            state.new_evidence = turn.new_evidence
            state.new_facts = turn.new_facts
            state.provider_error = turn.provider_error
            for observation in turn.observations:
                apply_observation_to_state(state, observation)
            turn_event_kinds = [event.kind for event in turn.events]
            event_counts.update(turn_event_kinds)
            add_trace_metadata(
                runtime_turn_event_kinds=turn_event_kinds,
                runtime_turn_event_count=len(turn.events),
                runtime_turn_observation_count=len(turn.observations),
                runtime_invalid_tool_call_count=turn_event_kinds.count("invalid_tool_call"),
                runtime_tool_error_count=turn_event_kinds.count("tool_error"),
                runtime_provider_error_count=turn_event_kinds.count("provider_error"),
                runtime_no_tool_call=any(kind == "no_tool_call" for kind in turn_event_kinds),
            )

            if state.provider_error:
                state.sufficiency = None
                state.stop_reason = "provider_error"
                add_trace_metadata(route="synthesize", stop_reason="provider_error")
                break

            if agentic_nodes.should_suppress_retrieve_after_graph_coverage(query, ledger):
                state.sufficiency = None
                state.stop_reason = "graph_sufficient"
                state.prev_gaps = ()
                state.open_categories = 0
                state.open_cat_stall = 0
                add_trace_metadata(route="synthesize", stop_reason="graph_sufficient")
                break

            verdict = agentic_nodes.assess_sufficiency(judge, query, "", ledger, history=history)
            current_open = agentic_nodes.count_open_categories(ledger)
            prev_open = state.open_categories if state.open_categories else current_open + 1
            open_cat_stall = state.open_cat_stall + 1 if current_open >= prev_open else 0
            route, reason = agentic_nodes.decide_next(
                verdict,
                state.iteration_count,
                state.tokens_used,
                state.new_evidence,
                max_iterations=int(getattr(settings, "agentic_max_iterations", 1)),
                token_ceiling=int(getattr(settings, "agentic_token_ceiling", 10**9)),
                max_retrieve_rounds=int(getattr(settings, "agentic_max_retrieve_rounds", 2)),
                new_facts=state.new_facts,
                prev_gaps=state.prev_gaps,
                elapsed_seconds=time.monotonic() - started_at,
                max_wall_seconds=max_wall_seconds,
                open_cat_stall=open_cat_stall,
                max_open_cat_stall=int(getattr(settings, "agentic_open_cat_stall_limit", 0)),
                tool_calls_used=len(ledger.actions),
                max_tool_calls=adapter._hard_tool_budget,
            )
            add_trace_metadata(
                sufficient=bool(verdict and verdict.sufficient),
                grounded=bool(verdict and verdict.grounded),
                faithfulness_estimate=(verdict.faithfulness_estimate if verdict else None),
                coverage_gaps=list(verdict.coverage_gaps) if verdict else [],
                next_action=(verdict.next_action if verdict else "parse_fallback"),
                route=route,
                iteration_count=state.iteration_count,
                open_categories=current_open,
                open_cat_stall=open_cat_stall,
            )
            state.sufficiency = verdict
            state.stop_reason = reason
            state.prev_gaps = tuple(verdict.coverage_gaps) if verdict else ()
            state.open_categories = current_open
            state.open_cat_stall = open_cat_stall
            if route == "synthesize":
                break

        if gather_only:
            gen_answer = GeneratedAnswer(
                query=query,
                answer="",
                cited_chunk_ids=[],
                query_result=ledger.union_query_result(
                    query,
                    limit=int(getattr(settings, "agentic_synthesis_top_k", 10)),
                ),
                generation_ms=0.0,
                model="gather-only",
            )
        else:
            gen_answer = agentic_nodes.synthesize_answer(
                generator,
                query,
                ledger,
                top_k=int(getattr(settings, "agentic_synthesis_top_k", 10)),
                fact_limit=getattr(settings, "agentic_synthesis_fact_limit", 120),
                history=history,
            )
        answer = agentic_nodes.build_agentic_answer(
            query,
            gen_answer,
            ledger,
            iteration_count=state.iteration_count,
            tokens_used=state.tokens_used,
            stop_reason=state.stop_reason,
        )
        add_trace_metadata(
            iteration_count=answer.iteration_count,
            stop_reason=answer.stop_reason,
            cited_ids=list(answer.cited_ids),
            dropped_citation_count=answer.dropped_citation_count,
            n_chunks=len(ledger.chunks),
            n_facts=len(ledger.facts),
            n_conflicts=len(answer.conflicts),
            runtime_observation_count=len(state.observations),
            runtime_event_counts=dict(event_counts),
        )
        return RuntimeInvestigationResult(ledger=ledger, answer=answer)

    return _run()


def run_agentic_investigation(
    query: str,
    *,
    settings: object,
    history: list[str] | None = None,
    run_retrieve: Callable[[str, int], QueryResult],
    fact_store: object | None,
    ontology_nodes: list[dict[str, Any]],
    generator: Any,
    chat_model: Any,
    judge: Callable[[str, str], str],
) -> Any:
    """Run the production/public single-agent investigation loop."""

    return _run_agentic_investigation_result(
        query,
        settings=settings,
        history=history,
        run_retrieve=run_retrieve,
        fact_store=fact_store,
        ontology_nodes=ontology_nodes,
        generator=generator,
        chat_model=chat_model,
        judge=judge,
        gather_only=False,
    ).answer


def run_agentic_gather_investigation(
    query: str,
    *,
    settings: object,
    history: list[str] | None = None,
    run_retrieve: Callable[[str, int], QueryResult],
    fact_store: object | None,
    ontology_nodes: list[dict[str, Any]],
    generator: Any,
    chat_model: Any,
    judge: Callable[[str, str], str],
) -> RuntimeInvestigationResult:
    """Run a runtime-owned gather-only investigation for supervisor branch workers."""

    return _run_agentic_investigation_result(
        query,
        settings=settings,
        history=history,
        run_retrieve=run_retrieve,
        fact_store=fact_store,
        ontology_nodes=ontology_nodes,
        generator=generator,
        chat_model=chat_model,
        judge=judge,
        gather_only=True,
    )


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
        if hasattr(rewriter, "rewrite_with_entities"):
            out = rewriter.rewrite_with_entities(query, history)
            retrieval_queries = out.queries
            entities = out.entities
        elif hasattr(rewriter, "rewrite"):
            retrieval_queries = tuple(rewriter.rewrite(query, history))
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
        return generate(
            _RUNTIME_UNDERSTANDING_SYSTEM,
            _runtime_understanding_user_prompt(query, history),
            max_tokens=max_tokens,
        )
    except TypeError:
        return generate(_RUNTIME_UNDERSTANDING_SYSTEM, _runtime_understanding_user_prompt(query, history))


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
