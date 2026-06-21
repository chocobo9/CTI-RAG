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
import time
from collections import Counter
from collections.abc import Callable
from typing import Any, Protocol

from rag_cti._logging import get_logger
from rag_cti.generation.context_builder import extract_cited_ids
from rag_cti.generation.prompts import AGENTIC_SYNTHESIS_SYSTEM
from rag_cti.knowledge.agentic_state import AgenticAnswer, SufficiencyVerdict
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.types import Chunk, GeneratedAnswer, QueryResult, RetrievalResult

logger = get_logger(__name__)

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


def run_gather_loop(
    model: Any,
    dispatch: Callable[[str, dict[str, Any]], Any],
    messages: list[Any],
    *,
    max_steps: int,
    deadline: float | None = None,
    on_model_error: Callable[[BaseException], None] | None = None,
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
    from langchain_core.messages import ToolMessage

    convo = list(messages)
    for _ in range(max_steps):
        if deadline is not None and time.monotonic() >= deadline:
            break  # wall-clock budget spent mid-burst -> stop with what we have
        try:
            ai = model.invoke(convo)
        except Exception as exc:  # provider failure: end the burst, keep the partial ledger
            logger.warning("gather model call failed, ending burst", error=str(exc))
            if on_model_error is not None:
                on_model_error(exc)
            break
        convo.append(ai)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            break  # model emitted no tool call -> it has gathered enough
        for call in tool_calls:
            if deadline is not None and time.monotonic() >= deadline:
                break  # budget spent between tool calls -> stop
            name = call.get("name", "")
            args = call.get("args", {}) or {}
            try:
                result: Any = dispatch(name, args)
            except Exception as exc:  # surface the error to the model, keep gathering
                result = {"error": f"{name} failed: {exc}"}
            convo.append(ToolMessage(content=str(result), tool_call_id=call.get("id", "")))
    return convo


# ---------------------------------------------------------------------------
# sufficiency gate — build prompt, judge, parse
# ---------------------------------------------------------------------------


def build_judge_user(query: str, last_draft: str, ledger: EvidenceLedger) -> str:
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
    judge: JudgeFn, query: str, last_draft: str, ledger: EvidenceLedger
) -> SufficiencyVerdict | None:
    """Call the judge over the bounded evidence view; parse to a verdict (or None)."""
    raw = judge(AGENTIC_SUFFICIENCY_SYSTEM, build_judge_user(query, last_draft, ledger))
    return parse_verdict(raw)


# ---------------------------------------------------------------------------
# router — the structural stop decision (budget is the only HARD stop)
# ---------------------------------------------------------------------------


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
    prev_gaps: tuple[str, ...] = (),
    elapsed_seconds: float = 0.0,
    max_wall_seconds: float = 0.0,
) -> tuple[str, str]:
    """Return (next_node, stop_reason). next_node is "agent_turn" or "synthesize".

    Convergence is task-driven: stop when the judge says sufficient, OR the last burst
    gathered nothing new (``new_evidence == 0`` — retrying is futile). max_iterations /
    token_ceiling are generous runaway backstops, not the primary stop."""
    if iteration_count >= max_iterations or tokens_used >= token_ceiling:
        return "synthesize", "budget"
    # Wall-clock tail-latency guardrail (checked between iterations): bound total latency
    # even if an API hangs, regardless of iteration/token count. 0 disables it.
    if max_wall_seconds > 0 and elapsed_seconds >= max_wall_seconds:
        return "synthesize", "timeout"
    if verdict is not None and verdict.next_action == "stop":
        return "synthesize", "sufficient"
    if new_evidence == 0:
        return "synthesize", "no_progress"
    # Stuck guard: the judge is repeating the EXACT same coverage gaps AND this burst added
    # no new graph facts — further looping just churns (e.g. fetching prose that doesn't
    # advance an enumeration). Stop instead of running to the budget cap.
    if (
        verdict is not None
        and new_facts == 0
        and prev_gaps
        and tuple(verdict.coverage_gaps) == prev_gaps
    ):
        return "synthesize", "no_progress"
    # PRIMARY convergence bound: the judge still wants more, but we've already done our
    # allotted retrieve_more rounds (iteration 1 is the initial gather, so completed
    # re-entries = iteration_count - 1). Synthesize with what we have — this is the
    # deterministic stop that keeps latency bounded; "budget" should stay a rare runaway.
    if iteration_count - 1 >= max_retrieve_rounds:
        return "synthesize", "max_rounds"
    if verdict is None:
        return "synthesize", "parse_fallback"
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
) -> list[Any]:
    """Build the STARTING messages for one gather burst (working-set pattern): a clean
    ``[system, query]`` EVERY iteration — never the prior burst's transcript, which is
    redundant with the ledger and made context (and cost) grow super-linearly across
    iterations. On a retrieve_more re-entry, append the directive (ledger summary + gaps)
    so the fresh burst knows what is done and what is missing."""
    messages: list[Any] = [("system", system_prompt), ("user", query)]
    if verdict is not None and verdict.next_action == "retrieve_more":
        messages.append(("user", build_directives(verdict, ledger)))
    return messages


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
    for cid in extract_cited_ids(answer_text):
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
) -> GeneratedAnswer:
    """Generate the final answer over the gathered evidence: the top-``top_k`` prose
    chunks PLUS the graph facts (as citable pseudo-chunks). ``fact_limit=None`` feeds ALL
    gathered facts: the gold an answer can cite is bounded by what reaches synthesis, so an
    arbitrary fact cap suppresses recall; the real bound is the model's context window, which
    a few hundred triples sit comfortably inside. ``top_k``/``fact_limit`` are generous
    window-safety bounds, not task quotas."""
    chunk_results = list(ledger.union_query_result(query, limit=top_k).results)
    fact_results = _facts_as_results(ledger, fact_limit)
    # Facts FIRST: graph facts are the exact enumeration the answer must cite; putting
    # them ahead of prose gives them primacy (the model anchors on early context) so the
    # gathered [fact_id]s actually reach the answer instead of only the prose chunks.
    merged = [r.model_copy(update={"rank": i}) for i, r in enumerate(fact_results + chunk_results)]
    return generator.generate(
        query,
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
    )
