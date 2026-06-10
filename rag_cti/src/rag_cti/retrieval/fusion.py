from __future__ import annotations

from rag_cti.types import RetrievalResult

# RRF smoothing constant from the original paper (Cormack et al., 2009).
DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievalResult]],
    k: int = DEFAULT_RRF_K,
    weights: list[float] | None = None,
) -> list[RetrievalResult]:
    """Fuse multiple ranked result lists using (weighted) Reciprocal Rank Fusion.

    Each result contributes ``weight / (k + rank + 1)`` to its chunk's total
    score, where ``weight`` is the weight of the list it came from. Duplicates
    (same chunk.id) are merged; the result with the highest individual score is
    kept as the representative document.

    With uniform weights (the default) this is standard RRF. Weighted RRF lets
    callers bias the fusion, e.g. ``weights=[alpha, 1 - alpha]`` for a
    dense/sparse pair driven by ``settings.hybrid_alpha``.

    Args:
        result_lists: One list per retriever, each already ranked 0-based.
        k: RRF smoothing constant.
        weights: Optional per-list weights, aligned with ``result_lists``.
            Must be non-negative with at least one positive entry.
            ``None`` means uniform weights (plain RRF).

    Returns:
        Deduplicated results sorted by descending fused score, re-ranked 0-based.

    Raises:
        ValueError: When ``weights`` is misaligned with ``result_lists``,
            contains a negative entry, or sums to zero.
    """
    if weights is None:
        weights = [1.0] * len(result_lists)
    if len(weights) != len(result_lists):
        raise ValueError(
            f"weights ({len(weights)}) must align with result_lists ({len(result_lists)})"
        )
    if any(w < 0 for w in weights):
        raise ValueError(f"weights must be non-negative, got {weights}")
    if result_lists and sum(weights) <= 0:
        raise ValueError(f"at least one weight must be positive, got {weights}")

    scores: dict[str, float] = {}
    best: dict[str, RetrievalResult] = {}

    for weight, results in zip(weights, result_lists, strict=True):
        if weight == 0:
            continue
        for result in results:
            chunk_id = result.document.id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (k + result.rank + 1)
            if chunk_id not in best or result.score > best[chunk_id].score:
                best[chunk_id] = result

    fused = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    return [
        RetrievalResult(
            document=best[cid].document,
            score=scores[cid],
            rank=rank,
            retriever_source="rrf",
        )
        for rank, cid in enumerate(fused)
    ]
