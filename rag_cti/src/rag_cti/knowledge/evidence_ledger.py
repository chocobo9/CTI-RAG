"""EvidenceLedger — the structured side channel the agentic loop's hard-rail nodes
read instead of the LLM transcript (agentic plan, "Target architecture").

The inner ReAct-style tool loop exposes its trajectory as stringified ``ToolMessage``s,
and the loop's tools deliberately return *bounded summaries*
(snippets, top-50 object lists). The hard-rail nodes (sufficiency gate, synthesize,
citation assembly) need the **structured, untruncated** chunks/facts. So each tool
closure appends its full result here as a side effect before returning its summary;
the nodes read the ledger, never the transcript.

Mutable by design: one ledger per ``agentic_answer`` invocation, never shared.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any

from rag_cti.knowledge.tool_cache import ToolCache, canonicalize_args
from rag_cti.types import FactRow, GraphOutline, QueryResult, RetrievalResult


@dataclass(frozen=True)
class ActionRecord:
    """One tool call the gather loop already dispatched — its name + a compact, value-
    truncated arg string — so the model can be shown 'what I already did' and skip an
    identical repeat (the documented amnesia / duplicate-work mitigation)."""

    name: str
    args: str


@dataclass
class EvidenceLedger:
    """Per-run accumulator of everything the agent retrieved, deduplicated by id."""

    chunks: dict[str, RetrievalResult] = field(default_factory=dict)
    facts: dict[str, FactRow] = field(default_factory=dict)
    outlines: dict[str, GraphOutline] = field(default_factory=dict)
    actions: list[ActionRecord] = field(default_factory=list)
    # Per-run idempotent-tool dedup cache (over-calling mitigation); excluded from equality
    # since it is execution scratch, not gathered evidence. Off unless the dispatch seam opts in.
    cache: ToolCache = field(default_factory=ToolCache, compare=False)
    # Guards every mutation so concurrent within-turn dispatch (B2) and parallel supervisor
    # workers writing to one ledger cannot corrupt the dict/list updates. Re-entrant because
    # merge() re-enters add_*; read-only properties stay lock-free (only read single-threaded
    # after a parallel burst joins). Excluded from equality/repr — it is not data.
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def add_query_result(self, qr: QueryResult) -> int:
        """Union retrieved chunks by chunk id (keep the higher-scoring duplicate).

        Returns the count of chunk ids new to the ledger — the agent_turn node uses
        this as the "did this turn add anything" signal.
        """
        with self._lock:
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
        with self._lock:
            new = 0
            for row in rows:
                if row.fact_id not in self.facts:
                    self.facts[row.fact_id] = row
                    new += 1
            return new

    def add_outline(self, outline: GraphOutline) -> None:
        """Record a coverage map (a sufficiency *hint*, not citable evidence)."""
        with self._lock:
            self.outlines[outline.entity_id] = outline

    def add_action(self, name: str, args: dict[str, Any]) -> None:
        """Record a dispatched tool call as its name + the canonical, value-truncated arg
        string (sorted keys — the same ``canonicalize_args`` the tool cache keys on, so the
        action log and the dedup cache agree on call identity). The recorded log is the
        model-facing 'what I already did' view (render_action_log) AND the exact tool-call
        count surfaced on the answer."""
        with self._lock:
            self.actions.append(ActionRecord(name=name, args=canonicalize_args(args)))

    def cache_get(self, name: str, args: dict[str, Any]) -> Any | None:
        """Look up a prior identical tool result (idempotent-tool dedup at the dispatch seam).
        ``None`` = miss. Lock-guarded alongside the mutators so concurrent dispatch is safe."""
        with self._lock:
            return self.cache.store.get(self._cache_key(name, args))

    def cache_put(self, name: str, args: dict[str, Any], result: Any) -> None:
        """Record a tool result for dedup of a later identical call this run."""
        with self._lock:
            self.cache.store[self._cache_key(name, args)] = result

    @staticmethod
    def _cache_key(name: str, args: dict[str, Any]) -> str:
        """Full-fidelity cache key; unlike the action log, this never truncates values."""
        return f"{name}({json.dumps(args, sort_keys=True, default=str, separators=(',', ':'))})"

    def merge(self, other: EvidenceLedger) -> None:
        """Fold another ledger into this one — used to combine N parallel branch ledgers
        into a single master ledger for ONE grounded synthesis. Reuses the existing union
        semantics: chunks keep the higher score (``add_query_result``), facts are
        first-wins (``add_facts``), outlines are overwritten by entity_id. Ids are
        globally unique, so a cross-branch id collision is a correct union, not a clash.
        """
        with self._lock:  # RLock: the add_* calls below re-acquire it
            self.add_query_result(
                QueryResult(
                    query="",
                    results=list(other.chunks.values()),
                    total_retrieved=len(other.chunks),
                    retrieval_ms=0.0,
                )
            )
            self.add_facts(tuple(other.facts.values()))
            for outline in other.outlines.values():
                self.add_outline(outline)
            self.actions.extend(other.actions)

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
