"""EvidenceLedger — the structured side channel the agentic loop's hard-rail nodes
read instead of the LLM transcript (agentic plan, "Target architecture").

The inner ``create_react_agent`` only exposes its trajectory as stringified
``ToolMessage``s, and the loop's tools deliberately return *bounded summaries*
(snippets, top-50 object lists). The hard-rail nodes (sufficiency gate, synthesize,
citation assembly) need the **structured, untruncated** chunks/facts. So each tool
closure appends its full result here as a side effect before returning its summary;
the nodes read the ledger, never the transcript.

Mutable by design: one ledger per ``agentic_answer`` invocation, never shared.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rag_cti.types import FactRow, GraphOutline, QueryResult, RetrievalResult


@dataclass
class EvidenceLedger:
    """Per-run accumulator of everything the agent retrieved, deduplicated by id."""

    chunks: dict[str, RetrievalResult] = field(default_factory=dict)
    facts: dict[str, FactRow] = field(default_factory=dict)
    outlines: dict[str, GraphOutline] = field(default_factory=dict)

    def add_query_result(self, qr: QueryResult) -> int:
        """Union retrieved chunks by chunk id (keep the higher-scoring duplicate).

        Returns the count of chunk ids new to the ledger — the agent_turn node uses
        this as the "did this turn add anything" signal.
        """
        new = 0
        for result in qr.results:
            chunk_id = result.document.id
            existing = self.chunks.get(chunk_id)
            if existing is None:
                self.chunks[chunk_id] = result
                new += 1
            elif result.score > existing.score:
                self.chunks[chunk_id] = result
        return new

    def add_facts(self, rows: tuple[FactRow, ...]) -> int:
        """Union facts by fact_id. Returns the count of fact ids new to the ledger."""
        new = 0
        for row in rows:
            if row.fact_id not in self.facts:
                self.facts[row.fact_id] = row
                new += 1
        return new

    def add_outline(self, outline: GraphOutline) -> None:
        """Record a coverage map (a sufficiency *hint*, not citable evidence)."""
        self.outlines[outline.entity_id] = outline

    @property
    def real_id_set(self) -> frozenset[str]:
        """Every citable id: chunk ids ∪ fact ids. The citation guard intersects the
        model's cited ids with this set; anything outside is a hallucinated citation.
        """
        return frozenset(self.chunks) | frozenset(self.facts)

    def union_query_result(self, query: str, limit: int | None = None) -> QueryResult:
        """A QueryResult over the ledger chunks, score-desc with ranks renumbered —
        the context the synthesize node generates over and RAGAS reads as
        ``retrieved_contexts``. ``limit`` caps it to the top-N most relevant so a
        long multi-iteration run does not blow up the synthesis context (an
        unbounded dump makes the reasoning model spend its output budget and return
        empty content)."""
        ordered = sorted(self.chunks.values(), key=lambda r: r.score, reverse=True)
        if limit is not None:
            ordered = ordered[:limit]
        reranked = [r.model_copy(update={"rank": i}) for i, r in enumerate(ordered)]
        return QueryResult(
            query=query,
            results=reranked,
            total_retrieved=len(reranked),
            retrieval_ms=0.0,
        )

    def conflicts(self) -> tuple[FactRow, ...]:
        """The collected facts flagged ``conflict`` — surfaced on the answer, never
        resolved (M4 invariant 6)."""
        return tuple(row for row in self.facts.values() if row.conflict)
