from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from rag_cti._logging import get_logger
from rag_cti.evaluation.query_set import QuerySetRecord
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
    hit_counts: dict[int, int] = dict.fromkeys(k_values, 0)
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


# ---------------------------------------------------------------------------
# Query-set evaluation (chunk-ID + source/ATT&CK matching)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CategoryMetrics:
    n_queries: int
    top_k: dict[int, float]
    mrr: float
    ndcg: dict[int, float]


@dataclass(frozen=True)
class PerQueryResult:
    query_id: str
    query_text: str
    category: str
    expected_doc_ids: list[str]
    retrieved_doc_ids: list[str]
    hit_at_k: dict[int, bool]
    reciprocal_rank: float
    target_rank: int | None


@dataclass(frozen=True)
class QuerySetEvalResult:
    config: str
    k_values: list[int]
    overall: CategoryMetrics
    by_category: dict[str, CategoryMetrics]
    per_query: list[PerQueryResult] = field(default_factory=list)


def ndcg_at_k(
    results: list[Any],
    is_relevant: Callable[[Any], bool],
    k: int,
    n_relevant: int = 1,
) -> float:
    """nDCG@k with binary relevance. n_relevant is the total number of relevant docs."""
    dcg = sum(1.0 / math.log2(i + 1) for i, r in enumerate(results[:k], start=1) if is_relevant(r))
    n_ideal = min(n_relevant, k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, n_ideal + 1))
    return round(dcg / idcg, 4) if idcg > 0 else 0.0


def _is_query_set_match(result: Any, record: QuerySetRecord) -> bool:
    """True if result is relevant for the given QuerySetRecord.

    precise/semantic: chunk ID must be in expected_chunk_ids.
    fuzzy: source in gold_sources OR ATT&CK ID matches gold_attack_ids.
    """
    if record.expected_chunk_ids:
        return result.document.id in record.expected_chunk_ids
    if result.document.source in record.gold_sources:
        return True
    attack_id = _chunk_attack_id(result.document)
    if attack_id:
        return any(_is_match(attack_id, g) for g in record.gold_attack_ids)
    return False


def _hit_at_k_qs(results: list[Any], record: QuerySetRecord, k: int) -> bool:
    return any(_is_query_set_match(r, record) for r in results[:k])


def _reciprocal_rank_qs(results: list[Any], record: QuerySetRecord) -> float:
    for rank, result in enumerate(results, start=1):
        if _is_query_set_match(result, record):
            return 1.0 / rank
    return 0.0


def evaluate_on_query_set(
    retriever: Retriever,
    records: list[QuerySetRecord],
    config: str,
    k_values: tuple[int, ...] = (1, 5, 10),
) -> QuerySetEvalResult:
    """Evaluate retriever against the custom query set.

    Matching strategy:
      precise/semantic — chunk ID must appear in top-k results.
      fuzzy            — source tag in gold_sources, or ATT&CK ID match.

    Returns QuerySetEvalResult with per-category and overall metrics.
    """
    max_k = max(k_values)

    cat_hits: dict[str, dict[int, int]] = defaultdict(lambda: dict.fromkeys(k_values, 0))
    cat_ndcg: dict[str, dict[int, float]] = defaultdict(lambda: dict.fromkeys(k_values, 0.0))
    cat_rr: dict[str, float] = defaultdict(float)
    cat_n: dict[str, int] = defaultdict(int)
    per_query_results: list[PerQueryResult] = []

    for i, record in enumerate(records):
        results = retriever.search(record.query, top_k=max_k)
        cat = record.category.value
        cat_n[cat] += 1
        n_rel = max(len(record.expected_chunk_ids), 1)

        def _is_rel(r: Any, _rec: QuerySetRecord = record) -> bool:
            return _is_query_set_match(r, _rec)

        query_hits: dict[int, bool] = {}
        for k in k_values:
            hit = _hit_at_k_qs(results, record, k)
            query_hits[k] = hit
            if hit:
                cat_hits[cat][k] += 1
            cat_ndcg[cat][k] += ndcg_at_k(results, _is_rel, k, n_relevant=n_rel)

        rr = _reciprocal_rank_qs(results, record)
        cat_rr[cat] += rr

        target_rank: int | None = None
        if rr > 0.0:
            target_rank = round(1.0 / rr)

        per_query_results.append(
            PerQueryResult(
                query_id=record.query_id,
                query_text=record.query,
                category=cat,
                expected_doc_ids=record.expected_chunk_ids,
                retrieved_doc_ids=[r.document.id for r in results],
                hit_at_k=query_hits,
                reciprocal_rank=rr,
                target_rank=target_rank,
            )
        )

        if (i + 1) % 10 == 0:
            logger.info(
                "query set eval progress", completed=i + 1, total=len(records), config=config
            )

    by_category: dict[str, CategoryMetrics] = {}
    overall_hits: dict[int, int] = dict.fromkeys(k_values, 0)
    overall_ndcg: dict[int, float] = dict.fromkeys(k_values, 0.0)
    overall_rr = 0.0
    overall_n = 0

    for cat, n in cat_n.items():
        top_k = {k: round(cat_hits[cat][k] / n, 4) if n > 0 else 0.0 for k in k_values}
        mrr = round(cat_rr[cat] / n, 4) if n > 0 else 0.0
        ndcg = {k: round(cat_ndcg[cat][k] / n, 4) if n > 0 else 0.0 for k in k_values}
        by_category[cat] = CategoryMetrics(n_queries=n, top_k=top_k, mrr=mrr, ndcg=ndcg)
        for k in k_values:
            overall_hits[k] += cat_hits[cat][k]
            overall_ndcg[k] += cat_ndcg[cat][k]
        overall_rr += cat_rr[cat]
        overall_n += n

    overall_top_k = {
        k: round(overall_hits[k] / overall_n, 4) if overall_n > 0 else 0.0 for k in k_values
    }
    overall_mrr = round(overall_rr / overall_n, 4) if overall_n > 0 else 0.0
    overall_ndcg_out = {
        k: round(overall_ndcg[k] / overall_n, 4) if overall_n > 0 else 0.0 for k in k_values
    }
    overall = CategoryMetrics(
        n_queries=overall_n, top_k=overall_top_k, mrr=overall_mrr, ndcg=overall_ndcg_out
    )

    logger.info(
        "query set eval complete", config=config, n_queries=overall_n, overall_mrr=overall_mrr
    )
    return QuerySetEvalResult(
        config=config,
        k_values=list(k_values),
        overall=overall,
        by_category=by_category,
        per_query=per_query_results,
    )
