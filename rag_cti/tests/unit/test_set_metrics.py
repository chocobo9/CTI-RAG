"""Unit tests for set_metrics — Micro-F1 and P/R/F1@k.

Expected values are hand-computed from PROJECT_SPEC.md §M / §A.2 step 3, NOT
copied from a run. Inputs use real ATT&CK technique IDs.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from rag_cti.evaluation.set_metrics import (
    SetPRF,
    micro_f1,
    micro_prf_at_k,
    normalize_id,
    normalize_set,
    prf_at_k,
)

# ---------------------------------------------------------------------------
# normalize_id
# ---------------------------------------------------------------------------


def test_normalize_id_technique_strips_subtechnique() -> None:
    assert normalize_id("T1059.001", "technique") == "T1059"


def test_normalize_id_technique_is_default_level() -> None:
    assert normalize_id("T1059.001") == "T1059"


def test_normalize_id_subtechnique_keeps_suffix_and_uppercases() -> None:
    assert normalize_id("t1059.001", "subtechnique") == "T1059.001"


def test_normalize_id_strips_whitespace() -> None:
    assert normalize_id("  T1003  ", "technique") == "T1003"


def test_normalize_id_plain_technique_unchanged_at_subtechnique_level() -> None:
    assert normalize_id("T1003", "subtechnique") == "T1003"


def test_normalize_id_rejects_unknown_level() -> None:
    with pytest.raises(ValueError, match="unknown level"):
        normalize_id("T1059", "tactic")


def test_normalize_set_dedupes_after_normalization_and_drops_blanks() -> None:
    # T1059.001 and T1059.002 both collapse to T1059 at technique level.
    result = normalize_set(["T1059.001", "T1059.002", "  ", "T1003"], "technique")
    assert result == {"T1059", "T1003"}


# ---------------------------------------------------------------------------
# Micro-F1 — single-record cases (SPEC §A.2 step 3)
# ---------------------------------------------------------------------------


def test_micro_f1_single_record_parent_collapse() -> None:
    # G=["T1059.001"], pred=["T1059.001","T1003","T1059.002"]
    # tech level: G={T1059}, P={T1059,T1003} -> TP=1 FP=1 FN=0
    r = micro_f1([["T1059.001"]], [["T1059.001", "T1003", "T1059.002"]], "technique")
    assert (r.tp, r.fp, r.fn) == (1, 1, 0)
    assert r.precision == pytest.approx(0.5)
    assert r.recall == pytest.approx(1.0)
    assert r.f1 == pytest.approx(2 / 3)


def test_micro_f1_single_record_multilabel_partial() -> None:
    # G=["T1566.001","T1204.002"], pred=["T1566.001","T1059"]
    # tech level: G={T1566,T1204}, P={T1566,T1059} -> TP=1 FP=1 FN=1
    r = micro_f1([["T1566.001", "T1204.002"]], [["T1566.001", "T1059"]], "technique")
    assert (r.tp, r.fp, r.fn) == (1, 1, 1)
    assert r.f1 == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Micro-F1 — aggregation across the two records above (SPEC §A.2 step 3)
# ---------------------------------------------------------------------------


def test_micro_f1_aggregates_two_records() -> None:
    gold = [["T1059.001"], ["T1566.001", "T1204.002"]]
    pred = [["T1059.001", "T1003", "T1059.002"], ["T1566.001", "T1059"]]
    r = micro_f1(gold, pred, "technique")
    # ΣTP=2 ΣFP=2 ΣFN=1
    assert (r.tp, r.fp, r.fn, r.n) == (2, 2, 1, 2)
    assert r.precision == pytest.approx(0.5)  # 2/4
    assert r.recall == pytest.approx(2 / 3)  # 2/3
    assert r.f1 == pytest.approx(0.5714, abs=1e-4)  # 2*0.5*0.6667/(1.1667)


def test_micro_f1_subtechnique_level_does_not_collapse() -> None:
    # At subtechnique level T1059.001 != T1059.002, so the parent-collapse FP/FN differ.
    r = micro_f1([["T1059.001"]], [["T1059.001", "T1059.002"]], "subtechnique")
    assert (r.tp, r.fp, r.fn) == (1, 1, 0)


def test_micro_f1_empty_prediction_gives_zero() -> None:
    r = micro_f1([["T1059"]], [[]], "technique")
    assert (r.tp, r.fp, r.fn) == (0, 0, 1)
    assert r.precision == 0.0
    assert r.recall == 0.0
    assert r.f1 == 0.0


def test_micro_f1_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="mismatch"):
        micro_f1([["T1059"]], [["T1059"], ["T1003"]], "technique")


# ---------------------------------------------------------------------------
# P/R/F1@k — single record, hand-computed
# ---------------------------------------------------------------------------


def test_prf_at_k_hand_computed() -> None:
    gold = ["T1059.001", "T1003"]  # tech: {T1059, T1003}
    ranked = ["T1566", "T1059.002", "T1003.001", "T1071", "T1059"]
    out = prf_at_k(ranked, gold, k_values=(1, 3, 5), level="technique")

    # k=1: P={T1566} -> TP0 FP1 FN2
    assert (out[1].tp, out[1].fp, out[1].fn) == (0, 1, 2)
    assert out[1].f1 == 0.0
    # k=3: P={T1566,T1059,T1003} -> TP2 FP1 FN0
    assert (out[3].tp, out[3].fp, out[3].fn) == (2, 1, 0)
    assert out[3].precision == pytest.approx(2 / 3)
    assert out[3].recall == pytest.approx(1.0)
    assert out[3].f1 == pytest.approx(0.8)
    # k=5: P={T1566,T1059,T1003,T1071} (dup T1059 dropped) -> TP2 FP2 FN0
    assert (out[5].tp, out[5].fp, out[5].fn) == (2, 2, 0)
    assert out[5].precision == pytest.approx(0.5)
    assert out[5].f1 == pytest.approx(2 / 3)


def test_micro_prf_at_k_aggregates() -> None:
    ranked = [["T1059.001", "T1003"], ["T1566", "T1204.002"]]
    gold = [["T1059"], ["T1204.002"]]
    out = micro_prf_at_k(ranked, gold, k_values=(1, 2), level="technique")
    # k=1: q1 P={T1059} TP1; q2 P={T1566} TP0 -> ΣTP1 ΣFP1 ΣFN1
    assert (out[1].tp, out[1].fp, out[1].fn, out[1].n) == (1, 1, 1, 2)
    # k=2: q1 P={T1059,T1003} TP1 FP1; q2 P={T1566,T1204} TP1 FP1 -> ΣTP2 ΣFP2 ΣFN0
    assert (out[2].tp, out[2].fp, out[2].fn) == (2, 2, 0)
    assert out[2].recall == pytest.approx(1.0)


def test_setprf_is_frozen() -> None:
    r = SetPRF(precision=1.0, recall=1.0, f1=1.0, tp=1, fp=0, fn=0, n=1)
    with pytest.raises(FrozenInstanceError):
        r.precision = 0.0  # type: ignore[misc]
