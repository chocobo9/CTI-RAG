from __future__ import annotations

from typing import Any

import pytest

from rag_cti.preprocess.vocab_relations import render_markdown, summarize_vocab


def _fact(
    predicate: str, st: str, ot: str, group: str, origins: list[str], s: str, o: str
) -> dict[str, Any]:
    return {
        "predicate": predicate,
        "subject_type": st,
        "object_type": ot,
        "group": group,
        "distinct_origins": origins,
        "subject_id": s,
        "object_id": o,
    }


def test_summarize_groups_and_counts():
    facts = [
        _fact("uses", "actor", "technique", "ttp", ["mitre"], "actor_G1", "technique_T1"),
        _fact("uses", "actor", "technique", "ttp", ["otx"], "actor_G2", "technique_T2"),
        _fact("uses", "actor", "family", "ttp", ["otx"], "actor_G1", "family_S1"),
        _fact(
            "resolves-to", "indicator", "indicator", "infra", ["pdns"], "indicator_d", "indicator_i"
        ),
    ]
    rows = summarize_vocab(facts)
    by_combo = {(r.predicate, r.subject_type, r.object_type): r for r in rows}
    assert by_combo[("uses", "actor", "technique")].fact_count == 2
    # origins are unioned across facts in the combo
    assert by_combo[("uses", "actor", "technique")].origins == ("mitre", "otx")
    assert by_combo[("uses", "actor", "family")].fact_count == 1
    assert by_combo[("resolves-to", "indicator", "indicator")].group == "infra"


def test_example_is_first_seen():
    facts = [
        _fact("uses", "actor", "technique", "ttp", ["mitre"], "actor_FIRST", "technique_T1"),
        _fact("uses", "actor", "technique", "ttp", ["otx"], "actor_SECOND", "technique_T2"),
    ]
    row = summarize_vocab(facts)[0]
    assert (row.example_subject, row.example_object) == ("actor_FIRST", "technique_T1")


def test_unknown_group_predicate_raises():
    facts = [_fact("ASSOCIATED_WITH", "actor", "actor", "unknown", ["pdf"], "actor_G1", "actor_G2")]
    with pytest.raises(ValueError, match="un-sanctioned predicate"):
        summarize_vocab(facts)


def test_group_ordering_ttp_then_infra_then_defensive():
    facts = [
        _fact(
            "mitigates",
            "mitigation",
            "technique",
            "defensive",
            ["mitre"],
            "mitigation_M1",
            "technique_T1",
        ),
        _fact(
            "resolves-to", "indicator", "indicator", "infra", ["pdns"], "indicator_d", "indicator_i"
        ),
        _fact("uses", "actor", "technique", "ttp", ["mitre"], "actor_G1", "technique_T1"),
    ]
    groups = [r.group for r in summarize_vocab(facts)]
    assert groups == ["ttp", "infra", "defensive"]


def test_render_markdown_has_sections_and_rows():
    facts = [
        _fact("uses", "actor", "technique", "ttp", ["mitre"], "actor_G1", "technique_T1"),
        _fact(
            "resolves-to", "indicator", "indicator", "infra", ["pdns"], "indicator_d", "indicator_i"
        ),
    ]
    md = render_markdown(summarize_vocab(facts))
    assert "## TTP" in md
    assert "## 基础设施" in md
    assert "`uses`" in md
    assert "`resolves-to`" in md
    assert "`actor_G1` → `technique_T1`" in md


def test_names_enrich_example_and_prefer_fully_resolvable():
    facts = [
        # first occurrence: object has no name -> not fully resolvable
        _fact(
            "resolves-to", "indicator", "indicator", "infra", ["pdns"], "indicator_a", "indicator_b"
        ),
        # second: both endpoints resolvable -> preferred as the example
        _fact(
            "resolves-to", "indicator", "indicator", "infra", ["pdns"], "indicator_c", "indicator_d"
        ),
    ]
    names = {"indicator_c": "evil.com", "indicator_d": "1.2.3.4"}
    row = summarize_vocab(facts, names)[0]
    assert (row.example_subject, row.example_object) == ("indicator_c", "indicator_d")
    assert (row.example_subject_name, row.example_object_name) == ("evil.com", "1.2.3.4")
    md = render_markdown([row])
    assert "evil.com (`indicator_c`)" in md
    assert "1.2.3.4 (`indicator_d`)" in md


def test_unresolved_endpoint_falls_back_to_id():
    facts = [_fact("belongs-to", "indicator", "asn", "infra", ["pdns"], "indicator_a", "asn_xyz")]
    names = {"indicator_a": "evil.com"}  # asn has no name source
    md = render_markdown(summarize_vocab(facts, names))
    assert "evil.com (`indicator_a`)" in md
    assert "`asn_xyz`" in md  # unresolved → id verbatim
