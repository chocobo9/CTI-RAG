"""Set-based ATT&CK metrics: Micro-F1 (unranked) and P/R/F1@k (ranked).

Definitions are fixed by PROJECT_SPEC.md §M and are NOT custom:
  - Micro-F1 over set predictions — used for CTI-ATE / annotation scoring.
  - P/R/F1@k over ranked retrieval results — used for multi-label retrieval.

Both normalize ATT&CK IDs to a requested granularity ("technique" or
"subtechnique") and then do EXACT set operations. This module deliberately does
NOT import ``retrieval_metrics._is_match``: that helper does bidirectional
parent/child wildcarding (T1003 matches T1003.001 and vice-versa), which
inflates scores. Here, matching is exact after normalization.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

_VALID_LEVELS = ("technique", "subtechnique")


def normalize_id(tid: str, level: str = "technique") -> str:
    """Normalize an ATT&CK technique ID to the requested granularity.

    level == "technique"    -> parent technique only: "T1059.001" -> "T1059"
    level == "subtechnique" -> full ID, upper-cased:  "t1059.001" -> "T1059.001"

    Leading/trailing whitespace is stripped first so callers can pass raw,
    comma-split tokens.
    """
    if level not in _VALID_LEVELS:
        raise ValueError(f"unknown level {level!r}; expected one of {_VALID_LEVELS}")
    s = tid.strip().upper()
    if level == "technique":
        return s.split(".")[0]
    return s


def normalize_set(ids: Iterable[str], level: str = "technique") -> set[str]:
    """Normalize an iterable of IDs to a set at the given level. Empty/blank dropped."""
    return {normalize_id(x, level) for x in ids if x and x.strip()}


@dataclass(frozen=True)
class SetPRF:
    """Precision/Recall/F1 plus the raw TP/FP/FN counts they were derived from."""

    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int
    n: int  # number of records aggregated


def _prf_from_counts(tp: int, fp: int, fn: int, n: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def micro_f1(
    gold_sets: Sequence[Iterable[str]],
    pred_sets: Sequence[Iterable[str]],
    level: str = "technique",
) -> SetPRF:
    """Micro-averaged Precision/Recall/F1 over per-record set predictions.

    For each record: G = normalize(gold), P = normalize(pred);
        TP = |P ∩ G|, FP = |P \\ G|, FN = |G \\ P|.
    Micro aggregation sums TP/FP/FN across all records, then:
        P = ΣTP/(ΣTP+ΣFP), R = ΣTP/(ΣTP+ΣFN), F1 = 2PR/(P+R)  (0 if denom 0).
    """
    if len(gold_sets) != len(pred_sets):
        raise ValueError(
            f"gold_sets ({len(gold_sets)}) and pred_sets ({len(pred_sets)}) length mismatch"
        )
    tp = fp = fn = 0
    n = len(gold_sets)
    for gold, pred in zip(gold_sets, pred_sets, strict=True):
        g = normalize_set(gold, level)
        p = normalize_set(pred, level)
        tp += len(p & g)
        fp += len(p - g)
        fn += len(g - p)
    precision, recall, f1 = _prf_from_counts(tp, fp, fn, n)
    return SetPRF(precision=precision, recall=recall, f1=f1, tp=tp, fp=fp, fn=fn, n=n)


def prf_at_k(
    ranked_ids: Sequence[str],
    gold_ids: Iterable[str],
    k_values: Sequence[int] = (1, 3, 5, 10),
    level: str = "technique",
) -> dict[int, SetPRF]:
    """Per-record P/R/F1 at each k.

    P_k = normalized set of attack_ids among the first k ranked results.
    Gold set is the normalized gold. Same TP/FP/FN set math as micro_f1.
    """
    g = normalize_set(gold_ids, level)
    out: dict[int, SetPRF] = {}
    for k in k_values:
        p = normalize_set(ranked_ids[:k], level)
        tp = len(p & g)
        fp = len(p - g)
        fn = len(g - p)
        precision, recall, f1 = _prf_from_counts(tp, fp, fn, 1)
        out[k] = SetPRF(precision=precision, recall=recall, f1=f1, tp=tp, fp=fp, fn=fn, n=1)
    return out


def micro_prf_at_k(
    ranked_ids_per_query: Sequence[Sequence[str]],
    gold_per_query: Sequence[Iterable[str]],
    k_values: Sequence[int] = (1, 3, 5, 10),
    level: str = "technique",
) -> dict[int, SetPRF]:
    """Micro-averaged P/R/F1@k across many ranked queries (for retrieval scoring)."""
    if len(ranked_ids_per_query) != len(gold_per_query):
        raise ValueError(
            f"ranked ({len(ranked_ids_per_query)}) and gold ({len(gold_per_query)}) length mismatch"
        )
    n = len(gold_per_query)
    counts: dict[int, list[int]] = {k: [0, 0, 0] for k in k_values}
    for ranked, gold in zip(ranked_ids_per_query, gold_per_query, strict=True):
        g = normalize_set(gold, level)
        for k in k_values:
            p = normalize_set(ranked[:k], level)
            counts[k][0] += len(p & g)
            counts[k][1] += len(p - g)
            counts[k][2] += len(g - p)
    out: dict[int, SetPRF] = {}
    for k in k_values:
        tp, fp, fn = counts[k]
        precision, recall, f1 = _prf_from_counts(tp, fp, fn, n)
        out[k] = SetPRF(precision=precision, recall=recall, f1=f1, tp=tp, fp=fp, fn=fn, n=n)
    return out
