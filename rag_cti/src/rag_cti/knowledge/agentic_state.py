"""Agentic answer-loop data types (workflow→agentic plan).

``SufficiencyVerdict`` is the sufficiency-gate judge's structured output.
``AgenticAnswer`` is the public result — a superset of ``GeneratedAnswer`` that
also carries the gathered facts/conflicts and the loop telemetry. Frozen pydantic,
matching the house style in ``types.py``. No langgraph here: these are pure data so
the node logic unit-tests without the [agentic] deps.
"""

from __future__ import annotations

from pydantic import BaseModel

from rag_cti.types import FactRow, QueryResult


class SufficiencyVerdict(BaseModel, frozen=True):
    """The sufficiency gate's two-axis judgement + the concrete next step.

    ``grounded`` / ``faithfulness_estimate`` = does the draft's claims trace to
    evidence (faithfulness). ``sufficient`` / ``coverage_gaps`` = does the evidence
    cover the question (recall). On insufficient, the judge proposes the next
    retrieval so the loop re-enters with a concrete target, not a vague "try again".
    """

    grounded: bool = False
    faithfulness_estimate: float = 0.0
    sufficient: bool = False
    coverage_gaps: tuple[str, ...] = ()
    next_action: str = "retrieve_more"  # "stop" | "retrieve_more"
    suggested_queries: tuple[str, ...] = ()
    # (subject_id, predicate|None, object_type|None) graph-enumeration targets.
    suggested_graph_targets: tuple[tuple[str, str | None, str | None], ...] = ()


class AgenticAnswer(BaseModel, frozen=True):
    """Public result of the agentic loop. ``query_result`` is the ledger-union so it
    stays RAGAS-compatible; ``cited_ids`` are validated against the ledger (the
    grounding guarantee); ``conflicts`` are surfaced, never resolved."""

    query: str
    answer: str
    cited_ids: tuple[str, ...] = ()
    query_result: QueryResult
    collected_facts: tuple[FactRow, ...] = ()
    conflicts: tuple[FactRow, ...] = ()
    iteration_count: int = 0
    tokens_used: int = 0
    stop_reason: str = ""  # "sufficient" | "budget" | "parse_fallback"
    dropped_citation_count: int = 0
