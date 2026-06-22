"""Deterministic query effort-tiering for the agentic loop's budget-visibility nudge (A3).

Anthropic's multi-agent research found agents "struggle to judge appropriate effort" and
over-invest on simple queries, so they hard-code per-query-class call budgets in the prompt.
This mirrors that deterministically: classify a query into an effort tier, then render a budget
line at the high-attention END of each gather turn showing the tier's suggested call budget and
how many tool calls have been spent so far — GUIDANCE the model can self-limit against, NOT a
hard quota (the router ``decide_next`` is untouched, same as the state view). No LLM: a cheap
heuristic over compare-signals and entity mentions (attack ids reuse the retrieval-side
extractor so query and index agree on technique-id shape)."""

from __future__ import annotations

import re

from rag_cti.retrieval.constraint_extract import extract_attack_ids

# Phrases signalling a comparison / set-operation question (compare X and Y, shared between …).
_COMPARE_SIGNALS = (
    " vs ",
    " versus ",
    "compare",
    "comparison",
    "between ",
    "shared",
    "in common",
    "common to",
    "both ",
    "difference",
)

# Entity-shaped tokens: alphanumeric codes (APT29, FIN7, TA505, UNC2452) and CamelCase names
# (CobaltStrike). Deliberately conservative — a single Capitalized word (ambiguous with a
# sentence start) does NOT count, so the entity count is a floor, not exact. That is fine: the
# tier only drives a guidance number, and the compare-signal / multi-clause checks catch the
# rest. Technique ids are added separately via ``extract_attack_ids``.
_ENTITY_TOKEN = re.compile(r"\b(?:[A-Za-z]+\d+[A-Za-z0-9]*|[A-Z][a-z]+[A-Z][a-zA-Z]+)\b")


def _count_entities(query: str) -> int:
    tokens = {m.upper() for m in _ENTITY_TOKEN.findall(query)}
    return len(tokens | set(extract_attack_ids(query)))


def classify_effort_tier(query: str) -> str:
    """Classify *query* into ``"simple" | "comparison" | "complex"`` (deterministic, no LLM).

    ``comparison`` = a compare / set-operation phrase is present. ``complex`` = >=3 distinct
    entity mentions OR a multi-clause question (several sub-questions). Otherwise ``simple``."""
    q = query.lower()
    if any(sig in q for sig in _COMPARE_SIGNALS):
        return "comparison"
    clauses = q.count(";") + q.count("?") + q.count(" and ")
    if _count_entities(query) >= 3 or clauses >= 2:
        return "complex"
    return "simple"


def render_budget_line(tier: str, calls_used: int, budgets: dict[str, int]) -> str:
    """The high-attention budget nudge: the query's effort tier, the suggested call budget for
    it, and how many tool calls have already been spent. Guidance, not a hard cap — phrased so
    the model converges toward the budget. Unknown tier -> the ``complex`` budget (lenient)."""
    budget = budgets.get(tier, budgets.get("complex", 0))
    return (
        f"EFFORT BUDGET (guidance — stop and answer once you have enough): this looks like a "
        f"{tier.upper()} question; aim for roughly {budget} tool calls. You have used "
        f"{calls_used} so far."
    )
