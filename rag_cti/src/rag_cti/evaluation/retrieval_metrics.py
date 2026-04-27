from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from rag_cti._logging import get_logger
from rag_cti.evaluation.techniquerag import TechniqueRAGRecord

logger = get_logger(__name__)


@dataclass(frozen=True)
class EvalResult:
    config: str
    k_values: list[int]
    top_k: dict[int, float]  # {1: 0.42, 5: 0.71, 10: 0.82}
    mrr: float
    n_queries: int


class Retriever(Protocol):
    def search(self, text: str, top_k: int) -> list[Any]: ...


def _chunk_attack_id(chunk: Any) -> str | None:
    val = chunk.metadata.get("attack_id")
    return str(val).strip().upper() if val else None


def _is_match(chunk_attack: str, gold_id: str) -> bool:
    """True if chunk_attack matches gold_id via exact, parent, or subtechnique."""
    c = chunk_attack.upper()
    g = gold_id.upper()
    if c == g:
        return True
    # chunk is parent, gold is subtechnique: T1003 matches T1003.001
    if g.startswith(c + "."):
        return True
    # chunk is subtechnique, gold is parent: T1003.001 matches T1003
    if c.startswith(g + "."):
        return True
    return False


def hit_at_k(results: list[Any], gold_ids: list[str], k: int) -> bool:
    """True if any result in top-k has an attack_id matching any gold technique ID."""
    for result in results[:k]:
        chunk_attack = _chunk_attack_id(result.document)
        if chunk_attack is None:
            continue
        for gold in gold_ids:
            if _is_match(chunk_attack, gold):
                return True
    return False


def reciprocal_rank(results: list[Any], gold_ids: list[str]) -> float:
    """Return 1/rank of the first matching result (1-indexed), or 0.0 if no match."""
    for rank, result in enumerate(results, start=1):
        chunk_attack = _chunk_attack_id(result.document)
        if chunk_attack is None:
            continue
        for gold in gold_ids:
            if _is_match(chunk_attack, gold):
                return 1.0 / rank
    return 0.0


def evaluate_retriever(
    retriever: Retriever,
    dataset: list[TechniqueRAGRecord],
    config: str,
    k_values: tuple[int, ...] = (1, 5, 10),
) -> EvalResult:
    """Evaluate retriever against TechniqueRAG dataset.

    Args:
        retriever: Object with a `search(text, top_k)` method returning RetrievalResult list.
        dataset: TechniqueRAGRecord list from load_techniquerag().
        config: Label for this run (e.g. "dense", "hybrid", "hybrid+hyde").
        k_values: k cutoffs for top-k hit rate.

    Returns:
        EvalResult with per-k hit rates and MRR.
    """
    max_k = max(k_values)
    hit_counts: dict[int, int] = {k: 0 for k in k_values}
    rr_sum = 0.0
    n = len(dataset)

    for i, record in enumerate(dataset):
        results = retriever.search(record.text, top_k=max_k)
        for k in k_values:
            if hit_at_k(results, record.gold_ids, k):
                hit_counts[k] += 1
        rr_sum += reciprocal_rank(results, record.gold_ids)

        if (i + 1) % 50 == 0:
            logger.info("eval progress", completed=i + 1, total=n, config=config)

    top_k = {k: round(hit_counts[k] / n, 4) if n > 0 else 0.0 for k in k_values}
    mrr = round(rr_sum / n, 4) if n > 0 else 0.0

    logger.info(
        "eval complete",
        config=config,
        n_queries=n,
        top_k=top_k,
        mrr=mrr,
    )
    return EvalResult(
        config=config,
        k_values=list(k_values),
        top_k=top_k,
        mrr=mrr,
        n_queries=n,
    )
