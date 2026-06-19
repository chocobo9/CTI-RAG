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
from collections.abc import Callable
from typing import Any, Protocol

from rag_cti.generation.context_builder import extract_cited_ids
from rag_cti.knowledge.agentic_state import AgenticAnswer, SufficiencyVerdict
from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.types import Chunk, GeneratedAnswer, QueryResult, RetrievalResult

# (system_prompt, user_prompt) -> raw model text. Injected so the gate unit-tests
# with a canned-JSON fake instead of a real LLM.
JudgeFn = Callable[[str, str], str]

# How much evidence the judge sees — bounded so the gate's own context stays small.
_JUDGE_MAX_CHUNKS = 20
_JUDGE_MAX_FACTS = 50

# langgraph's create_react_agent returns this AIMessage when it hits recursion_limit
# before drafting an answer. It is NOT a real draft — judging grounding on it always
# fails, so the loop never converges. Treat it as "no draft yet".
_RECURSION_STUB = "Sorry, need more steps to process this request."


def is_recursion_stub(text: str) -> bool:
    """True if ``text`` is langgraph's recursion-limit stub (the inner agent ran out of
    steps before writing an answer) — callers must not treat it as a real draft."""
    return text.strip() == _RECURSION_STUB


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
        self, query: str, query_result: QueryResult, raise_on_failure: bool = False
    ) -> GeneratedAnswer: ...


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
) -> tuple[str, str]:
    """Return (next_node, stop_reason). next_node is "agent_turn" or "synthesize".

    Convergence is task-driven: stop when the judge says sufficient, OR the last burst
    gathered nothing new (``new_evidence == 0`` — retrying is futile). max_iterations /
    token_ceiling are generous runaway backstops, not the primary stop."""
    if iteration_count >= max_iterations or tokens_used >= token_ceiling:
        return "synthesize", "budget"
    if verdict is not None and verdict.next_action == "stop":
        return "synthesize", "sufficient"
    if new_evidence == 0:
        return "synthesize", "no_progress"
    if verdict is None:
        return "synthesize", "parse_fallback"
    return "agent_turn", ""


def build_directives(verdict: SufficiencyVerdict) -> str:
    """The re-entry instruction for agent_turn — names the gap + concrete next step."""
    parts: list[str] = []
    if verdict.coverage_gaps:
        parts.append("Still missing: " + "; ".join(verdict.coverage_gaps))
    if verdict.suggested_queries:
        parts.append("Try vector_search for: " + "; ".join(verdict.suggested_queries))
    for subject, predicate, object_type in verdict.suggested_graph_targets:
        slots = ", ".join(s for s in (predicate, object_type) if s)
        target = f"{subject} ({slots})" if slots else subject
        parts.append(f"Try graph_query: {target}")
    return "\n".join(parts) if parts else "Gather more evidence to fully answer the question."


# ---------------------------------------------------------------------------
# synthesize + citation guarantee + final assembly
# ---------------------------------------------------------------------------


def assemble_citations(answer_text: str, ledger: EvidenceLedger) -> tuple[tuple[str, ...], int]:
    """Intersect the model's cited [id]s with the ledger's real ids. Returns
    (validated cited ids, count of hallucinated ids dropped). Truth is the ledger,
    not the regex."""
    cited = extract_cited_ids(answer_text)
    real = ledger.real_id_set
    kept = tuple(cid for cid in cited if cid in real)
    return kept, len(cited) - len(kept)


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
    merged = [r.model_copy(update={"rank": i}) for i, r in enumerate(chunk_results + fact_results)]
    return generator.generate(
        query,
        QueryResult(query=query, results=merged, total_retrieved=len(merged), retrieval_ms=0.0),
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
