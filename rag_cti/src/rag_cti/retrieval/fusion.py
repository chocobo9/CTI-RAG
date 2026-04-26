from __future__ import annotations

from rag_cti.types import RetrievalResult


def reciprocal_rank_fusion(
    result_lists: list[list[RetrievalResult]],
    k: int = 60,
) -> list[RetrievalResult]:
    """Fuse multiple ranked result lists using Reciprocal Rank Fusion.

    Each result contributes 1 / (k + rank + 1) to its chunk's total score.
    Duplicates (same chunk.id) are merged; the result with the highest
    individual score is kept as the representative document.

    Args:
        result_lists: One list per retriever, each already ranked 0-based.
        k: RRF smoothing constant (default 60 per the original paper).

    Returns:
        Deduplicated results sorted by descending fused score, re-ranked 0-based.
    """
    scores: dict[str, float] = {}
    best: dict[str, RetrievalResult] = {}

    for results in result_lists:
        for result in results:
            chunk_id = result.document.id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + result.rank + 1)
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
