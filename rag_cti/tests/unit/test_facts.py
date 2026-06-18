from __future__ import annotations

from typing import Any

from rag_cti.preprocess.facts import (
    AGGREGATE_VERSION,
    build_facts,
    entity_type,
    fact_id,
    predicate_group,
)


def _chunk(cid: str, source: str, relations: list[dict[str, str]], **md: Any) -> dict[str, Any]:
    return {"id": cid, "source": source, "metadata": {"relations": relations, **md}}


def _rel(s: str, p: str, o: str) -> dict[str, str]:
    return {"subject_id": s, "predicate": p, "object_id": o}


# --- fact_id / entity_type / predicate_group ---


def test_fact_id_stable_and_slot_separated():
    assert fact_id("a", "uses", "b") == fact_id("a", "uses", "b")
    # slot boundary: "a|uses|b" must not collide with "a|use|sb" style smears
    assert fact_id("ab", "uses", "c") != fact_id("a", "buses", "c")
    assert fact_id("a", "uses", "b").startswith("fact_")


def test_entity_type_from_prefix():
    assert entity_type("actor_G0016") == "actor"
    assert entity_type("actor_orphan_deadbeef") == "actor"
    assert entity_type("technique_T1059.001") == "technique"
    assert entity_type("family_S0154") == "family"
    assert entity_type("detection-strategy_DET0001") == "detection-strategy"
    assert entity_type("mitigation_M0001") == "mitigation"
    assert entity_type("indicator_abcd") == "indicator"
    assert entity_type("asn_abcd") == "asn"
    assert entity_type("location_orphan_x") == "location"
    assert entity_type("weird") == "unknown"


def test_predicate_group():
    assert predicate_group("uses") == "ttp"
    assert predicate_group("attributed-to") == "ttp"
    assert predicate_group("resolves-to") == "infra"
    assert predicate_group("mitigates") == "defensive"
    assert predicate_group("detects") == "defensive"
    assert predicate_group("nonsense") == "unknown"


# --- aggregation: one triple, N supports ---


def test_one_triple_across_two_sources_is_one_fact_two_supports():
    chunks = [
        _chunk("c1", "mitre", [_rel("actor_G0016", "uses", "technique_T1059")]),
        _chunk("c2", "otx", [_rel("actor_G0016", "uses", "technique_T1059")]),
    ]
    facts, supports = build_facts(chunks)
    assert len(facts) == 1
    f = facts[0]
    assert f.support_count == 2
    assert f.distinct_origins == ("mitre", "otx")
    assert f.subject_type == "actor"
    assert f.object_type == "technique"
    assert f.group == "ttp"
    assert {s.evidence_id for s in supports} == {"c1", "c2"}
    assert all(s.fact_id == f.fact_id for s in supports)


def test_duplicate_relation_in_one_chunk_is_one_support():
    chunks = [
        _chunk("c1", "mitre", [_rel("a_x", "uses", "b_y"), _rel("a_x", "uses", "b_y")]),
    ]
    _facts, supports = build_facts(chunks)
    assert len(supports) == 1


def test_empty_or_malformed_relations_skipped():
    chunks = [
        _chunk("c1", "otx", []),
        _chunk("c2", "otx", [{"subject_id": "", "predicate": "uses", "object_id": "b_y"}]),
        _chunk("c3", "otx", [{"subject_id": "a_x", "predicate": "uses"}]),
    ]
    facts, supports = build_facts(chunks)
    assert facts == []
    assert supports == []


# --- supports field mapping (origin-driven) ---


def test_confidence_and_label_availability_by_origin():
    chunks = [
        _chunk("m", "mitre", [_rel("a_x", "uses", "technique_T1")]),
        _chunk("o", "otx", [_rel("a_y", "uses", "technique_T2")]),
        _chunk("p", "pdns", [_rel("indicator_d", "resolves-to", "indicator_i")]),
        _chunk("v", "virustotal", [_rel("indicator_d2", "uses-nameserver", "indicator_n")]),
    ]
    _facts, supports = build_facts(chunks)
    by_evi = {s.evidence_id: s for s in supports}
    assert (by_evi["m"].confidence, by_evi["m"].label_availability) == (0.9, "direct")
    assert (by_evi["o"].confidence, by_evi["o"].label_availability) == (0.7, "direct")
    assert (by_evi["p"].confidence, by_evi["p"].label_availability) == (0.7, "none")
    assert (by_evi["v"].confidence, by_evi["v"].label_availability) == (0.7, "none")


def test_observed_fill_and_null_rules():
    chunks = [
        _chunk(
            "m",
            "mitre",
            [_rel("a_x", "uses", "technique_T1")],
            last_modified="2025-04-28T00:00:00Z",
        ),
        _chunk(
            "v",
            "virustotal",
            [_rel("indicator_d", "uses-nameserver", "indicator_n")],
            creation_date="2007-04-10T00:00:00Z",
            last_modified="2026-06-02T00:00:00Z",
        ),
        _chunk(
            "p",
            "pdns",
            [_rel("indicator_d2", "resolves-to", "indicator_i")],
            first_seen="",
            last_seen="",
        ),  # empty strings -> null
    ]
    _facts, supports = build_facts(chunks)
    by_evi = {s.evidence_id: s for s in supports}
    assert by_evi["m"].observed_first is None
    assert by_evi["m"].observed_last == "2025-04-28T00:00:00Z"
    assert by_evi["v"].observed_first == "2007-04-10T00:00:00Z"
    assert by_evi["v"].observed_last == "2026-06-02T00:00:00Z"
    assert by_evi["p"].observed_first is None
    assert by_evi["p"].observed_last is None


# --- aggregate (D4 v0) ---


def test_aggregate_credibility_v0_and_version():
    # single mitre support: max_conf 0.9 + 0.05*log2(2) = 0.95
    chunks = [_chunk("c1", "mitre", [_rel("a_x", "uses", "b_y")])]
    facts, _ = build_facts(chunks)
    assert facts[0].aggregate_credibility == 0.95
    assert facts[0].aggregate_version == AGGREGATE_VERSION


def test_aggregate_credibility_clamped_to_one():
    # two distinct origins both 0.9-ish: 0.9 + 0.05*log2(3) ~= 0.979, stays <= 1.0
    chunks = [
        _chunk("c1", "mitre", [_rel("a_x", "uses", "b_y")]),
        _chunk("c2", "otx", [_rel("a_x", "uses", "b_y")]),
    ]
    facts, _ = build_facts(chunks)
    assert facts[0].aggregate_credibility <= 1.0


# --- conflict (D5) ---


def test_single_valued_conflict_flags_both_facts_kept():
    chunks = [
        _chunk("c1", "mitre", [_rel("campaign_C1", "attributed-to", "actor_G0016")]),
        _chunk("c2", "otx", [_rel("campaign_C1", "attributed-to", "actor_G0032")]),
    ]
    facts, _ = build_facts(chunks)
    assert len(facts) == 2  # both kept
    assert all(f.conflict for f in facts)


def test_multivalued_predicate_not_a_conflict():
    # an actor using two techniques is normal, not a conflict
    chunks = [
        _chunk("c1", "mitre", [_rel("actor_G0016", "uses", "technique_T1")]),
        _chunk("c2", "mitre", [_rel("actor_G0016", "uses", "technique_T2")]),
    ]
    facts, _ = build_facts(chunks)
    assert not any(f.conflict for f in facts)


def test_single_valued_no_conflict_when_same_object():
    chunks = [
        _chunk("c1", "mitre", [_rel("campaign_C1", "attributed-to", "actor_G0016")]),
        _chunk("c2", "otx", [_rel("campaign_C1", "attributed-to", "actor_G0016")]),
    ]
    facts, _ = build_facts(chunks)
    assert len(facts) == 1
    assert not facts[0].conflict


# --- determinism ---


def test_deterministic_sorted_output():
    chunks = [
        _chunk("c1", "otx", [_rel("actor_G9", "uses", "technique_T9")]),
        _chunk("c2", "mitre", [_rel("actor_G1", "uses", "technique_T1")]),
    ]
    facts_a, sup_a = build_facts(chunks)
    facts_b, sup_b = build_facts(list(reversed(chunks)))
    assert facts_a == facts_b  # order independent of input order
    assert [f.subject_id for f in facts_a] == ["actor_G1", "actor_G9"]  # sorted
    assert sup_a == sup_b
