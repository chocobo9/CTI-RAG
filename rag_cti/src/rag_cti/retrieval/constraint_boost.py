"""Soft-boost re-scoring against a structured constraint (retrieval routing).

Given retrieval results and a :class:`PayloadConstraint`, add ``weight`` per matched
constraint *field* to each result's score, then re-sort. This is a *soft* signal:
a non-matching chunk keeps its score and can still rank first — nothing is excluded
(contrast the hard ``must`` pre-filter in ``qdrant_store``). The boost is re-applied
fresh after reranking (the cross-encoder overwrites scores), so it survives the
reranker in production while also working on the rerank-free direct-search path.

Addition (not multiplication) because scores live in different scales across the
pipeline — cosine, fused-RRF sums, and CrossEncoder logits — and a multiplier would
behave erratically (and can invert sign on negative logits); an additive bump is
monotone and predictable in every scale.
"""

from __future__ import annotations

from rag_cti.types import PayloadConstraint, RetrievalResult


def _chunk_attack_ids(metadata: dict[str, object]) -> set[str]:
    """All attack ids on a chunk, upper-normalized.

    Reads BOTH the projected plural ``attack_ids`` (list; mitre_relationships/otx) AND
    the connector-native singular ``attack_id`` (string; the core mitre technique
    corpus carries only this). Missing either is fine.
    """
    ids: set[str] = set()
    plural = metadata.get("attack_ids")
    if isinstance(plural, (list, tuple)):
        ids.update(str(a).upper() for a in plural)
    singular = metadata.get("attack_id")
    if isinstance(singular, str) and singular:
        ids.add(singular.upper())
    return ids


def _matched_fields(result: RetrievalResult, constraint: PayloadConstraint) -> int:
    """Number of constraint fields (0–3) the result's payload satisfies."""
    md = result.document.metadata or {}
    hits = 0

    if constraint.source_types:
        source_type = str(md.get("source_type") or result.document.source).lower()
        if source_type in {s.lower() for s in constraint.source_types}:
            hits += 1

    if constraint.attack_ids:
        if {a.upper() for a in constraint.attack_ids} & _chunk_attack_ids(md):
            hits += 1

    if constraint.entity_ids:
        chunk_entities = md.get("entity_ids")
        if isinstance(chunk_entities, (list, tuple)) and (
            set(constraint.entity_ids) & {str(e) for e in chunk_entities}
        ):
            hits += 1

    return hits


def apply_constraint_boost(
    results: list[RetrievalResult],
    constraint: PayloadConstraint | None,
    weight: float,
) -> list[RetrievalResult]:
    """Return *results* re-scored (``score + weight * matched_fields``) and re-sorted.

    A no-op (returns the input unchanged) when there is no constraint, it is empty,
    or ``weight`` is zero. The sort is stable, so ties keep their prior order; ranks
    are renumbered 0-based. Inputs are never mutated (``RetrievalResult`` is frozen).
    """
    if constraint is None or constraint.is_empty or weight == 0:
        return results

    scored = [(r, r.score + weight * _matched_fields(r, constraint)) for r in results]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [
        r.model_copy(update={"score": boosted, "rank": rank})
        for rank, (r, boosted) in enumerate(scored)
    ]
