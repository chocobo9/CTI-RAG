"""Pure node logic for the agentic answer loop (workflow→agentic plan).

These are the hard-rail guarantees as *code*, not prose prompt: the sufficiency
judge (parse + decide), the deterministic citation guard, the synthesize step, and
the final assembly. Every function takes its LLM/generator as an injected
dependency, so each branch unit-tests with fakes — no langgraph, no real LLM. The
langgraph wiring (``agentic_graph.py``) adapts these to StateGraph nodes.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from rag_cti.generation.context_builder import extract_cited_ids
from rag_cti.generation.prompts import AGENTIC_SYNTHESIS_SYSTEM
from rag_cti.knowledge.agentic_state import AgenticAnswer, SufficiencyVerdict
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.knowledge.react_loop import (
    DEADLINE_OBSERVATION_STUB,
    TRIMMED_OBSERVATION_STUB,
    mask_stale_observations,  # noqa: F401 - re-exported for tests/debug callers
    run_react_tool_loop,
)
from rag_cti.types import Chunk, GeneratedAnswer, QueryResult, RetrievalResult

_BARE_FACT_ID_RE = re.compile(r"\bfact_[a-zA-Z0-9_\-]+\b")

# (system_prompt, user_prompt) -> raw model text. Injected so the gate unit-tests
# with a canned-JSON fake instead of a real LLM.
JudgeFn = Callable[[str, str], str]

# How much evidence the judge sees — bounded so the gate's own context stays small.
_JUDGE_MAX_CHUNKS = 20
_JUDGE_MAX_FACTS = 50

AGENTIC_SUFFICIENCY_SYSTEM = (
    "You are a verification gate inside a CTI retrieval loop. You are given the user's "
    "QUESTION, the EVIDENCE gathered so far (entity relation-category COUNTS, facts, and "
    "prose chunks), and optionally a DRAFT answer.\n"
    "Judge sufficiency FROM THE EVIDENCE: does it contain enough to answer the QUESTION? "
    "coverage_gaps = the sub-questions NOT yet answerable from the evidence. Read the "
    "relation-category counts in coverage_outlines (e.g. 'uses->technique: 195') — a large "
    "count for the relation the QUESTION asks about means the evidence is ALREADY "
    "sufficient; do NOT ask to retrieve more of a category you already hold in bulk.\n"
    "If a non-empty DRAFT is present, also set grounded: is each draft claim supported by "
    "the evidence? faithfulness_estimate in [0,1] = fraction supported. If there is NO "
    "draft, grounding is not required to stop.\n"
    'next_action = "stop" when the evidence is sufficient (and any non-empty draft is '
    'grounded); otherwise "retrieve_more" with concrete suggested_queries (vector-search '
    "strings for prose gaps) and suggested_graph_targets ([subject_id, predicate, "
    "object_type] triples for enumeration gaps; reuse ids seen in the evidence; null for "
    "an unknown slot).\n"
    "Output ONLY a JSON object with keys: grounded (bool), faithfulness_estimate "
    "(number), sufficient (bool), coverage_gaps (list of strings), next_action "
    "(string), suggested_queries (list of strings), suggested_graph_targets "
    "(list of [string, string-or-null, string-or-null]). No prose."
)


class GeneratorProto(Protocol):
    """Structural view of generation.Generator used by synthesize (typing aid)."""

    def generate(
        self,
        query: str,
        query_result: QueryResult,
        raise_on_failure: bool = False,
        system_prompt: str | None = None,
    ) -> GeneratedAnswer: ...


# ---------------------------------------------------------------------------
# inner gather loop — GATHER-only ReAct burst (no answer; the ledger is the output)
# ---------------------------------------------------------------------------

_TRIMMED_STUB = TRIMMED_OBSERVATION_STUB
_DEADLINE_STUB = DEADLINE_OBSERVATION_STUB
_GRAPH_ENUMERATION_TERMS = (
    "compare",
    "shared",
    "unique",
    "both",
    "common",
    "overlap",
    "enumerate",
    "list",
    "which techniques",
    "attack techniques",
    "att&ck techniques",
)


def render_history_context(history: list[str] | None, limit: int = 6) -> str:
    """Render recent user turns for agentic prompts. Empty history returns ``""``."""
    if not history:
        return ""
    recent = [h.strip() for h in history[-limit:] if h.strip()]
    if not recent:
        return ""
    lines = ["Conversation so far (most recent last):"]
    lines.extend(f"- {turn}" for turn in recent)
    return "\n".join(lines)


def query_with_history(query: str, history: list[str] | None) -> str:
    """Prompt-facing latest query with conversation context prepended when present."""
    context = render_history_context(history)
    if not context:
        return query
    return f"{context}\n\nLatest query: {query}"


def should_suppress_retrieve_after_graph_coverage(query: str, ledger: EvidenceLedger) -> bool:
    """Return True when graph facts already cover an ATT&CK technique enumeration.

    This is intentionally conservative: it only suppresses prose retrieval for graph-heavy
    compare/enumerate questions when at least two named outlined entities have their complete
    ``uses -> technique`` category represented in the fact ledger. Explanation/how/why queries
    still fall through to retrieve because prose context is useful there.
    """
    q = query.lower()
    if not any(term in q for term in _GRAPH_ENUMERATION_TERMS):
        return False
    covered_entities = 0
    for outline in ledger.outlines.values():
        if outline.entity_name.lower() not in q:
            continue
        expected = sum(
            entry.count
            for entry in outline.outgoing
            if entry.predicate == "uses" and entry.other_type == "technique"
        )
        if expected <= 0:
            continue
        actual = sum(
            1
            for fact in ledger.facts.values()
            if (
                fact.subject_id == outline.entity_id
                and fact.predicate == "uses"
                and fact.object_type == "technique"
            )
        )
        if actual >= expected:
            covered_entities += 1
    return covered_entities >= 2


def run_gather_loop(
    model: Any,
    dispatch: Callable[[str, dict[str, Any]], Any],
    messages: list[Any],
    *,
    max_steps: int,
    deadline: float | None = None,
    on_model_error: Callable[[BaseException], None] | None = None,
    render_state: Callable[[], str] | None = None,
    keep_last_observations: int = 0,
    parallel_dispatch: bool = False,
    max_parallel_tools: int = 1,
) -> list[Any]:
    """Drive a GATHER-only tool loop and return the accumulated message transcript.

    The model (a chat model with tools bound) picks tool calls; ``dispatch(name, args)``
    runs each (side-effecting the EvidenceLedger) and its result is fed back as a
    ``ToolMessage``. The loop stops as soon as the model emits no tool call — meaning it
    judged it has gathered enough — or ``max_steps`` rounds are reached. The model never
    writes the final answer (the synthesize node does), so any text it emits is ignored;
    only the ledger (populated via ``dispatch``) and the transcript (for token counting)
    matter. A tool error is reported back to the model instead of aborting the burst.

    ``deadline`` (a ``time.monotonic()`` value) is the per-answer wall-clock budget pushed
    DOWN into the loop body — checked before each model turn and each tool call — so a burst
    stalled in provider-retry latency stops at the deadline instead of only between graph
    nodes. ``None`` disables it. ``on_model_error`` is invoked when ``model.invoke`` raises
    (a persistent provider failure): the burst ends with whatever it gathered rather than
    propagating and crashing the whole answer — the gather-side analogue of the tool-error
    guard below and of ``Generator``'s failure sentinel. ``None`` keeps the prior behaviour
    except that the error is now caught and logged."""
    return run_react_tool_loop(
        model,
        dispatch,
        messages,
        max_steps=max_steps,
        deadline=deadline,
        on_model_error=on_model_error,
        render_state=render_state,
        keep_last_observations=keep_last_observations,
        parallel_dispatch=parallel_dispatch,
        max_parallel_tools=max_parallel_tools,
    )


# ---------------------------------------------------------------------------
# sufficiency gate — build prompt, judge, parse
# ---------------------------------------------------------------------------


def build_judge_user(
    query: str, last_draft: str, ledger: EvidenceLedger, history: list[str] | None = None
) -> str:
    """Render a bounded JSON view of (question, draft, evidence) for the judge."""
    top_chunks = sorted(ledger.chunks.values(), key=lambda r: r.score, reverse=True)
    chunks = [
        {
            "chunk_id": r.document.id,
            "source": r.document.source,
            "snippet": r.document.content[:240].replace("\n", " "),
        }
        for r in top_chunks[:_JUDGE_MAX_CHUNKS]
    ]
    facts = [
        {
            "fact_id": f.fact_id,
            "triple": f"{f.subject_name} {f.predicate} {f.object_name}",
            "credibility": f.aggregate_credibility,
            "conflict": f.conflict,
        }
        for f in list(ledger.facts.values())[:_JUDGE_MAX_FACTS]
    ]
    outlines = [
        {
            "entity_id": o.entity_id,
            "outgoing": [
                {"predicate": e.predicate, "object_type": e.other_type, "count": e.count}
                for e in o.outgoing
            ],
        }
        for o in ledger.outlines.values()
    ]
    payload: dict[str, Any] = {
        "question": query,
        "conversation_history": tuple(history or ()),
        "draft": last_draft,
        "evidence": {"chunks": chunks, "facts": facts, "coverage_outlines": outlines},
    }
    return json.dumps(payload, default=str)


def _coerce_targets(raw: Any) -> tuple[tuple[str, str | None, str | None], ...]:
    if not isinstance(raw, list):
        return ()
    out: list[tuple[str, str | None, str | None]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or not item:
            continue
        subject = str(item[0]) if item[0] is not None else ""
        predicate = str(item[1]) if len(item) > 1 and item[1] is not None else None
        object_type = str(item[2]) if len(item) > 2 and item[2] is not None else None
        if subject:
            out.append((subject, predicate, object_type))
    return tuple(out)


def parse_verdict(raw: str) -> SufficiencyVerdict | None:
    """Parse the judge's JSON into a verdict. Returns None on unparseable output —
    the router fails closed (stop) rather than looping on a broken judge."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    grounded = bool(data.get("grounded", False))
    sufficient = bool(data.get("sufficient", False))
    try:
        faithfulness = float(data.get("faithfulness_estimate", 0.0))
    except (TypeError, ValueError):
        faithfulness = 0.0
    gaps = tuple(str(g) for g in (data.get("coverage_gaps") or []))
    queries = tuple(str(q) for q in (data.get("suggested_queries") or []))
    targets = _coerce_targets(data.get("suggested_graph_targets") or [])
    action = data.get("next_action")
    if action not in ("stop", "retrieve_more"):
        # Sufficiency drives convergence; grounding of the final answer is enforced by
        # the citation guard at synthesis, so it is not required here.
        action = "stop" if sufficient else "retrieve_more"

    return SufficiencyVerdict(
        grounded=grounded,
        faithfulness_estimate=faithfulness,
        sufficient=sufficient,
        coverage_gaps=gaps,
        next_action=action,
        suggested_queries=queries,
        suggested_graph_targets=targets,
    )


def assess_sufficiency(
    judge: JudgeFn,
    query: str,
    last_draft: str,
    ledger: EvidenceLedger,
    history: list[str] | None = None,
) -> SufficiencyVerdict | None:
    """Call the judge over the bounded evidence view; parse to a verdict (or None)."""
    raw = judge(AGENTIC_SUFFICIENCY_SYSTEM, build_judge_user(query, last_draft, ledger, history))
    return parse_verdict(raw)


# ---------------------------------------------------------------------------
# router — the structural stop decision (budget is the only HARD stop)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StopContext:
    verdict: SufficiencyVerdict | None
    iteration_count: int
    tokens_used: int
    new_evidence: int
    max_iterations: int
    token_ceiling: int
    max_retrieve_rounds: int
    new_facts: int
    setup_progress: int
    prev_gaps: tuple[str, ...]
    elapsed_seconds: float
    max_wall_seconds: float
    open_cat_stall: int
    max_open_cat_stall: int
    tool_calls_used: int
    max_tool_calls: int


def _over_budget(ctx: _StopContext) -> bool:
    return ctx.iteration_count >= ctx.max_iterations or ctx.tokens_used >= ctx.token_ceiling


def _timed_out(ctx: _StopContext) -> bool:
    return ctx.max_wall_seconds > 0 and ctx.elapsed_seconds >= ctx.max_wall_seconds


def _sufficient(ctx: _StopContext) -> bool:
    return ctx.verdict is not None and ctx.verdict.next_action == "stop"


def _no_progress(ctx: _StopContext) -> bool:
    return ctx.new_evidence == 0 and ctx.setup_progress == 0


def _repeated_gap_without_new_facts(ctx: _StopContext) -> bool:
    return (
        ctx.verdict is not None
        and ctx.new_facts == 0
        and bool(ctx.prev_gaps)
        and tuple(ctx.verdict.coverage_gaps) == ctx.prev_gaps
    )


def _open_category_stalled(ctx: _StopContext) -> bool:
    return (
        ctx.max_open_cat_stall > 0
        and ctx.new_facts == 0
        and ctx.open_cat_stall >= ctx.max_open_cat_stall
    )


def _tool_budget_spent(ctx: _StopContext) -> bool:
    return ctx.max_tool_calls > 0 and ctx.tool_calls_used >= ctx.max_tool_calls


def _retrieve_rounds_spent(ctx: _StopContext) -> bool:
    return ctx.iteration_count - 1 >= ctx.max_retrieve_rounds


def _parse_failed(ctx: _StopContext) -> bool:
    return ctx.verdict is None


_STOP_RULES: tuple[tuple[str, Callable[[_StopContext], bool]], ...] = (
    ("budget", _over_budget),
    ("timeout", _timed_out),
    ("sufficient", _sufficient),
    ("no_progress", _no_progress),
    ("no_progress", _repeated_gap_without_new_facts),
    ("open_cat_stall", _open_category_stalled),
    ("tool_budget", _tool_budget_spent),
    ("max_rounds", _retrieve_rounds_spent),
    ("parse_fallback", _parse_failed),
)


def decide_next(
    verdict: SufficiencyVerdict | None,
    iteration_count: int,
    tokens_used: int,
    new_evidence: int,
    *,
    max_iterations: int,
    token_ceiling: int,
    max_retrieve_rounds: int = 2,
    new_facts: int = 0,
    setup_progress: int = 0,
    prev_gaps: tuple[str, ...] = (),
    elapsed_seconds: float = 0.0,
    max_wall_seconds: float = 0.0,
    open_cat_stall: int = 0,
    max_open_cat_stall: int = 0,
    tool_calls_used: int = 0,
    max_tool_calls: int = 0,
) -> tuple[str, str]:
    """Return (next_node, stop_reason). next_node is "agent_turn" or "synthesize".

    Convergence is task-driven: stop when the judge says sufficient, OR the last burst
    gathered nothing new (``new_evidence == 0`` — retrying is futile). max_iterations /
    token_ceiling are generous runaway backstops, not the primary stop."""
    ctx = _StopContext(
        verdict=verdict,
        iteration_count=iteration_count,
        tokens_used=tokens_used,
        new_evidence=new_evidence,
        max_iterations=max_iterations,
        token_ceiling=token_ceiling,
        max_retrieve_rounds=max_retrieve_rounds,
        new_facts=new_facts,
        setup_progress=setup_progress,
        prev_gaps=prev_gaps,
        elapsed_seconds=elapsed_seconds,
        max_wall_seconds=max_wall_seconds,
        open_cat_stall=open_cat_stall,
        max_open_cat_stall=max_open_cat_stall,
        tool_calls_used=tool_calls_used,
        max_tool_calls=max_tool_calls,
    )
    for reason, predicate in _STOP_RULES:
        if predicate(ctx):
            return "synthesize", reason
    return "agent_turn", ""


def _ledger_summary(ledger: EvidenceLedger) -> str:
    """A compact 'what you already have' note for a re-entry directive. Each gather burst
    starts from a CLEAN context (working-set pattern — the ledger, not the transcript, is
    the cross-iteration memory), so this is how the burst learns what prior bursts found
    and avoids re-resolving / re-outlining / re-querying the graph it already enumerated."""
    if not ledger.facts and not ledger.chunks:
        return ""
    lines: list[str] = ["Already gathered (use these — do NOT collect them again):"]
    if ledger.facts:
        subjects = sorted({f.subject_name for f in ledger.facts.values()})
        cats = Counter((f.predicate, f.object_type) for f in ledger.facts.values())
        cat_str = ", ".join(f"{p}->{o}: {n}" for (p, o), n in sorted(cats.items()))
        lines.append(
            f"- {len(ledger.facts)} graph facts for {', '.join(subjects)} ({cat_str}); the "
            "graph enumeration for these is COMPLETE — do NOT call resolve_entity / "
            "graph_outline / graph_query for them again."
        )
    if ledger.chunks:
        lines.append(f"- {len(ledger.chunks)} prose chunks already retrieved.")
    return "\n".join(lines)


def build_directives(verdict: SufficiencyVerdict, ledger: EvidenceLedger) -> str:
    """The re-entry instruction for a fresh gather burst: a compact summary of what the
    ledger already holds (so the burst does not re-collect it), then the concrete gaps to
    fill. Since the burst starts from a clean context (working-set pattern), this note is
    how it learns prior progress."""
    parts: list[str] = []
    summary = _ledger_summary(ledger)
    if summary:
        parts.append(summary)
    gap_parts: list[str] = []
    if verdict.coverage_gaps:
        gap_parts.append("Still missing: " + "; ".join(verdict.coverage_gaps))
    if verdict.suggested_queries:
        gap_parts.append("Try retrieve for: " + "; ".join(verdict.suggested_queries))
    for subject, predicate, object_type in verdict.suggested_graph_targets:
        slots = ", ".join(s for s in (predicate, object_type) if s)
        target = f"{subject} ({slots})" if slots else subject
        gap_parts.append(f"Try graph_query: {target}")
    if gap_parts:
        parts.append("\n".join(gap_parts))
    return "\n".join(parts) if parts else "Gather more evidence to fully answer the question."


def build_turn_messages(
    system_prompt: str,
    query: str,
    verdict: SufficiencyVerdict | None,
    ledger: EvidenceLedger,
    history: list[str] | None = None,
) -> list[Any]:
    """Build the STARTING messages for one gather burst (working-set pattern): a clean
    ``[system, query]`` EVERY iteration — never the prior burst's transcript, which is
    redundant with the ledger and made context (and cost) grow super-linearly across
    iterations. On a retrieve_more re-entry, append the directive (ledger summary + gaps)
    so the fresh burst knows what is done and what is missing."""
    messages: list[Any] = [("system", system_prompt), ("user", query_with_history(query, history))]
    if verdict is not None and verdict.next_action == "retrieve_more":
        messages.append(("user", build_directives(verdict, ledger)))
    return messages


def render_state_view(ledger: EvidenceLedger) -> str:
    """Deterministic 'what you already have' coverage view, rebuilt from the ledger and
    injected fresh each gather turn so the model can SEE its accumulated state — which
    entities are resolved, which graph categories are already COMPLETE vs still open (with
    gathered/total counts from the outlines), and how much prose it holds — instead of
    re-deriving it from scattered bounded tool summaries. The ledger holds the truth the
    summaries never showed the model; this surfaces a faithful index of it. The outline's
    per-category ``count`` is the graph TOTAL; a category whose gathered facts reach that
    total is COMPLETE (re-querying it adds nothing). Empty ledger -> '' (nothing yet)."""
    if not ledger.facts and not ledger.outlines and not ledger.chunks:
        return ""
    entities: dict[str, str] = {o.entity_id: o.entity_name for o in ledger.outlines.values()}
    for f in ledger.facts.values():
        entities.setdefault(f.subject_id, f.subject_name)
    gathered: Counter[tuple[str, str, str]] = Counter(
        (f.subject_id, f.predicate, f.object_type) for f in ledger.facts.values()
    )
    lines: list[str] = [
        "GATHERED STATE (refreshed each turn — do NOT re-collect what is marked COMPLETE):"
    ]
    for entity_id, name in sorted(entities.items(), key=lambda kv: kv[1]):
        lines.append(f"- {name} ({entity_id}): resolved.")
        outline = ledger.outlines.get(entity_id)
        if outline is None:
            continue
        complete: list[str] = []
        open_cats: list[str] = []
        for e in outline.outgoing:
            g = gathered.get((entity_id, e.predicate, e.other_type), 0)
            label = f"{e.predicate}->{e.other_type} {g}/{e.count}"
            (complete if e.count > 0 and g >= e.count else open_cats).append(label)
        if complete:
            lines.append("    COMPLETE (do NOT graph_query again): " + ", ".join(complete))
        if open_cats:
            lines.append("    open categories (query only if relevant): " + ", ".join(open_cats))
    if ledger.chunks:
        sources = sorted({r.document.source for r in ledger.chunks.values()})
        lines.append(f"- prose: {len(ledger.chunks)} chunks from {', '.join(sources)}.")
    return "\n".join(lines)


def count_open_categories(ledger: EvidenceLedger) -> int:
    """Count the (entity, predicate, object_type) outline categories whose gathered facts
    have NOT reached the graph total — the SAME COMPLETE test ``render_state_view`` uses (an
    outline ``count`` is the graph total; a category is COMPLETE once gathered >= count). The
    count is monotonic non-increasing as the loop enumerates, so a stall (no shrink) across
    gather turns with no new facts means the loop is churning prose instead of closing the
    graph enumeration — the signal the open-category stall guard in ``decide_next`` reads.
    Only categories with a known total (``count > 0``) are counted. Empty graph -> 0."""
    gathered: Counter[tuple[str, str, str]] = Counter(
        (f.subject_id, f.predicate, f.object_type) for f in ledger.facts.values()
    )
    open_count = 0
    for outline in ledger.outlines.values():
        for e in outline.outgoing:
            held = gathered.get((outline.entity_id, e.predicate, e.other_type), 0)
            if e.count > 0 and held < e.count:
                open_count += 1
    return open_count


def render_action_log(ledger: EvidenceLedger, limit: int = 30) -> str:
    """The model-facing 'what I already did' view: one line per dispatched tool call (name
    + compact args), most-recent last, bounded to the last ``limit`` so the block stays
    small. Lets the model see it already called e.g. resolve_entity(name=APT29) and skip an
    identical repeat — the amnesia / duplicate-work mitigation. Empty log -> ''."""
    if not ledger.actions:
        return ""
    recent = ledger.actions[-limit:]
    lines = ["ACTIONS ALREADY TAKEN (do NOT repeat an identical call):"]
    lines += [f"- {a.name}({a.args})" for a in recent]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# synthesize + citation guarantee + final assembly
# ---------------------------------------------------------------------------


def assemble_citations(answer_text: str, ledger: EvidenceLedger) -> tuple[tuple[str, ...], int]:
    """Intersect the model's cited [id]s with the ledger's real ids. Returns
    (validated cited ids, count of hallucinated ids dropped). Truth is the ledger,
    not the regex.

    Fact pseudo-chunk ids carry a ``fact_`` prefix while prose chunk ids are bare, so the
    model sometimes mirrors that and writes ``chunk_<id>`` for a prose chunk. That is a
    real citation lightly mangled, not a hallucination — recover it by stripping the
    spurious ``chunk_`` prefix rather than dropping it."""
    real = ledger.real_id_set
    kept: list[str] = []
    dropped = 0
    candidate_ids = [*extract_cited_ids(answer_text), *_BARE_FACT_ID_RE.findall(answer_text)]
    for cid in candidate_ids:
        if cid in real:
            kept.append(cid)
        elif cid.startswith("chunk_") and cid[len("chunk_") :] in real:
            kept.append(cid[len("chunk_") :])
        else:
            dropped += 1
    # A normalized id may collide with one already kept — dedup, order-preserving.
    seen: set[str] = set()
    deduped: list[str] = []
    for k in kept:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    return tuple(deduped), dropped


def _facts_as_results(ledger: EvidenceLedger, limit: int | None) -> list[RetrievalResult]:
    """Render the top facts (credibility-desc) as pseudo-chunks so synthesis can cite
    controlled graph facts as ``[fact_id]`` beside prose ``[chunk_id]``s. Comparison /
    enumeration answers live in the graph; without this the synthesis sees only vector
    prose and the gathered facts never reach the answer."""
    rows = sorted(ledger.facts.values(), key=lambda f: f.aggregate_credibility, reverse=True)
    results: list[RetrievalResult] = []
    for i, fact in enumerate(rows[:limit]):
        flag = ", CONFLICTED" if fact.conflict else ""
        content = (
            f"FACT: {fact.subject_name} {fact.predicate} {fact.object_name} "
            f"(credibility {fact.aggregate_credibility:.2f}{flag})"
        )
        chunk = Chunk(
            id=fact.fact_id,
            parent_doc_id=fact.fact_id,
            source="graph",
            content=content,
            chunk_index=0,
        )
        results.append(
            RetrievalResult(
                document=chunk,
                score=fact.aggregate_credibility,
                rank=i,
                retriever_source="graph",
            )
        )
    return results


def synthesize_answer(
    generator: GeneratorProto,
    query: str,
    ledger: EvidenceLedger,
    *,
    top_k: int | None = None,
    fact_limit: int | None = None,
    history: list[str] | None = None,
) -> GeneratedAnswer:
    """Generate the final answer over gathered evidence with bounded context.

    The gather ledger can hold hundreds of graph facts for compound comparisons. Feeding all
    of them to a reasoning model can consume the output budget and produce empty content, so
    synthesis receives a high-credibility fact slice plus top prose chunks. The full ledger is
    still retained on the public AgenticAnswer for inspection/eval.
    """
    chunk_results = list(ledger.union_query_result(query, limit=top_k).results)
    fact_results = _facts_as_results(ledger, fact_limit)
    # Facts FIRST: graph facts are the exact enumeration the answer must cite; putting
    # them ahead of prose gives them primacy (the model anchors on early context) so the
    # gathered [fact_id]s actually reach the answer instead of only the prose chunks.
    merged = [r.model_copy(update={"rank": i}) for i, r in enumerate(fact_results + chunk_results)]
    return generator.generate(
        query_with_history(query, history),
        QueryResult(query=query, results=merged, total_retrieved=len(merged), retrieval_ms=0.0),
        system_prompt=AGENTIC_SYNTHESIS_SYSTEM,
    )


def build_agentic_answer(
    query: str,
    gen_answer: GeneratedAnswer,
    ledger: EvidenceLedger,
    *,
    iteration_count: int,
    tokens_used: int,
    stop_reason: str,
) -> AgenticAnswer:
    """Assemble the public result: validated citations + surfaced conflicts + telemetry."""
    cited_ids, dropped = assemble_citations(gen_answer.answer, ledger)
    return AgenticAnswer(
        query=query,
        answer=gen_answer.answer,
        cited_ids=cited_ids,
        query_result=gen_answer.query_result,
        collected_facts=tuple(ledger.facts.values()),
        conflicts=ledger.conflicts(),
        iteration_count=iteration_count,
        tokens_used=tokens_used,
        stop_reason=stop_reason,
        dropped_citation_count=dropped,
        tool_call_count=len(ledger.actions),
    )
