"""Composer — combine N worker BranchReports into the final compound answer.

The Composer is a DISTINCT role (its own LLM call). It does NOT gather and does NOT route;
it ONLY combines the workers' self-contained reports. It reasons over each branch's
STRUCTURED technique set, so a union / intersection is exact rather than re-derived from
lossy prose, and it cites ids drawn from the branches' validated cited_ids.

Pure logic only here (the prompt, the render, and a thin ``compose`` over an injected
``ComposeFn``) — it unit-tests with a fake ComposeFn, no real LLM. The real OpenAI-client
wrapper ``build_composer`` is wiring and lives in ``supervisor_graph.py`` (mirrors
``build_judge`` / ``build_decomposer``).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

from rag_cti.knowledge.agentic_state import BranchReport

# (system_prompt, user_prompt) -> raw answer text. Injected so ``compose`` unit-tests with
# a canned fake instead of a real LLM (same shape as JudgeFn / DecomposeFn).
ComposeFn = Callable[[str, str], str]

AGENTIC_COMPOSE_SYSTEM = (
    "You are a CTI analyst writing the FINAL answer to a COMPOUND question by COMBINING "
    "per-entity branch reports gathered by other analysts. You do NOT gather new evidence — "
    "you only synthesize ACROSS the reports you are given.\n"
    "Each branch report has a focus_entity and a structured technique list — each technique "
    "is a triple [attack_id, name, fact_id]. Base set operations on these STRUCTURED lists, "
    "NOT prose: 'shared between X and Y' = the INTERSECTION of their attack_ids; 'compare' = "
    "state which attack_ids are common and which are distinct per actor.\n"
    "When you mention a technique, CITE it as [fact_id] using the 3rd element of its triple "
    "(its fact_id). Use ONLY fact_ids that appear in the reports; never invent one. Surface "
    "disagreements rather than hiding them. If a branch status is partial, empty, or failed, "
    "state the evidence gap instead of treating missing evidence as negative evidence. Be "
    "specific and grounded."
)


def _render_report(report: BranchReport) -> dict[str, object]:
    return {
        "branch_id": report.branch_id,
        "focus_entity": report.focus_entity,
        "facet": report.facet,
        "sub_question": report.sub_question,
        "status": report.status,
        "evidence_summary": report.evidence_summary,
        "key_entities": list(report.key_entities),
        "sub_answer": report.sub_answer,
        "techniques": [list(pair) for pair in report.techniques],
        "cited_ids": list(report.cited_ids),
        "gaps": list(report.gaps),
        "suggested_queries": list(report.suggested_queries),
        "suggested_graph_targets": [list(target) for target in report.suggested_graph_targets],
        "errors": list(report.errors),
        "n_facts": report.n_facts,
        "n_chunks": report.n_chunks,
        "n_outlines": report.n_outlines,
        "stop_reason": report.stop_reason,
    }


def build_compose_user(
    query: str, reports: Sequence[BranchReport], history: list[str] | None = None
) -> str:
    """Render the original compound question + each branch's report as JSON for the
    Composer (structured, so it can do exact set operations over the technique ids)."""
    payload = {
        "question": query,
        "conversation_history": tuple(history or ()),
        "branch_reports": [_render_report(r) for r in reports],
    }
    return json.dumps(payload, default=str)


def compose(
    composer: ComposeFn,
    query: str,
    reports: Sequence[BranchReport],
    history: list[str] | None = None,
) -> str:
    """Combine the branch reports into the final answer text (over an injected LLM)."""
    return composer(AGENTIC_COMPOSE_SYSTEM, build_compose_user(query, reports, history))
