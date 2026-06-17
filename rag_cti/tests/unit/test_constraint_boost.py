from __future__ import annotations

from typing import Any

from rag_cti.retrieval.constraint_boost import apply_constraint_boost
from rag_cti.types import Chunk, PayloadConstraint, RetrievalResult


def _res(cid: str, score: float, source: str = "mitre", **md: Any) -> RetrievalResult:
    chunk = Chunk(id=cid, parent_doc_id="d", source=source, content="c", chunk_index=0, metadata=md)
    return RetrievalResult(document=chunk, score=score, rank=0, retriever_source="x")


def _ids(results: list[RetrievalResult]) -> list[str]:
    return [r.document.id for r in results]


# --- identity / no-op ---


def test_empty_constraint_is_identity():
    results = [_res("a", 0.9), _res("b", 0.5)]
    out = apply_constraint_boost(results, PayloadConstraint(), 1.0)
    assert out is results  # unchanged object, no rebuild


def test_none_constraint_is_identity():
    results = [_res("a", 0.9)]
    assert apply_constraint_boost(results, None, 1.0) is results


def test_zero_weight_is_identity():
    results = [_res("a", 0.9, attack_ids=["T1003"])]
    c = PayloadConstraint(attack_ids=("T1003",))
    assert apply_constraint_boost(results, c, 0.0) is results


# --- single-field reorders ---


def test_attack_id_match_lifts_low_scorer_above_non_match():
    results = [
        _res("nonmatch", 0.9),
        _res("match", 0.5, attack_ids=["T1003"]),
    ]
    c = PayloadConstraint(attack_ids=("T1003",))
    out = apply_constraint_boost(results, c, 1.0)
    assert _ids(out)[0] == "match"  # 0.5 + 1.0 = 1.5 > 0.9


def test_singular_attack_id_also_matches():
    # the core mitre corpus carries only the singular metadata.attack_id (regression 0.1)
    results = [_res("nonmatch", 0.9), _res("m", 0.5, attack_id="T1055.011")]
    c = PayloadConstraint(attack_ids=("T1055.011",))
    out = apply_constraint_boost(results, c, 1.0)
    assert _ids(out)[0] == "m"


def test_entity_id_match():
    results = [_res("n", 0.9), _res("m", 0.5, entity_ids=["actor_G0016"])]
    c = PayloadConstraint(entity_ids=("actor_G0016",))
    out = apply_constraint_boost(results, c, 1.0)
    assert _ids(out)[0] == "m"


def test_source_type_falls_back_to_document_source():
    # mitre.jsonl chunks lack metadata.source_type; matcher uses document.source.
    results = [_res("n", 0.9, source="otx"), _res("m", 0.5, source="mitre")]
    c = PayloadConstraint(source_types=("mitre",))
    out = apply_constraint_boost(results, c, 1.0)
    assert _ids(out)[0] == "m"


def test_source_type_metadata_preferred_over_source():
    results = [_res("m", 0.5, source="virustotal", source_type="vt")]
    c = PayloadConstraint(source_types=("vt",))
    out = apply_constraint_boost(results, c, 1.0)
    assert out[0].score == 1.5


# --- multi-field additive ---


def test_three_field_match_adds_three_times_weight():
    r = _res(
        "m",
        0.0,
        source="mitre",
        source_type="mitre",
        attack_ids=["T1003"],
        entity_ids=["actor_G0016"],
    )
    c = PayloadConstraint(
        source_types=("mitre",), attack_ids=("T1003",), entity_ids=("actor_G0016",)
    )
    out = apply_constraint_boost([r], c, 0.5)
    assert out[0].score == 1.5  # 0.0 + 0.5 * 3


# --- bookkeeping ---


def test_ranks_renumbered_zero_based_contiguous():
    results = [_res("a", 0.9), _res("b", 0.5, attack_ids=["T1003"]), _res("c", 0.3)]
    out = apply_constraint_boost(results, PayloadConstraint(attack_ids=("T1003",)), 1.0)
    assert [r.rank for r in out] == [0, 1, 2]


def test_inputs_not_mutated():
    r = _res("a", 0.5, attack_ids=["T1003"])
    apply_constraint_boost([r], PayloadConstraint(attack_ids=("T1003",)), 1.0)
    assert r.score == 0.5  # frozen original untouched
    assert r.rank == 0


def test_stable_on_ties_preserves_prior_order():
    # neither matches -> equal (unchanged) scores -> original order preserved
    results = [_res("a", 0.7), _res("b", 0.7)]
    out = apply_constraint_boost(results, PayloadConstraint(attack_ids=("T9999",)), 1.0)
    assert _ids(out) == ["a", "b"]
