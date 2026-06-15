"""Unit tests for query-time ontology expansion (retrieval-layer §6).

A technique filter is widened along the ATT&CK sub-technique hierarchy by one
hop in each direction: a sub-technique also matches its parent, a parent also
matches its sub-techniques. Siblings are NOT pulled in (that would be two hops).
"""

from __future__ import annotations

from rag_cti.retrieval.ontology_expand import expand_attack_ids, expand_constraint
from rag_cti.types import PayloadConstraint

# subtechnique-of edges (the M0 ontology_edges shape) + one non-subtechnique edge.
_EDGES = [
    {"child": "T1056.001", "parent": "T1056", "edge": "subtechnique-of"},
    {"child": "T1056.002", "parent": "T1056", "edge": "subtechnique-of"},
    {"child": "T1003.001", "parent": "T1003", "edge": "subtechnique-of"},
    {"child": "T1056", "parent": "TA0009", "edge": "belongs-to-tactic"},  # ignored
]


def test_subtechnique_expands_to_include_its_parent():
    assert expand_attack_ids(["T1056.001"], _EDGES) == ("T1056", "T1056.001")


def test_parent_expands_to_include_its_subtechniques():
    assert expand_attack_ids(["T1056"], _EDGES) == ("T1056", "T1056.001", "T1056.002")


def test_subtechnique_does_not_pull_in_siblings():
    # T1056.001 -> {T1056.001, T1056}; the sibling T1056.002 is two hops away.
    assert "T1056.002" not in expand_attack_ids(["T1056.001"], _EDGES)


def test_belongs_to_tactic_edges_are_ignored():
    # T1056's only non-subtechnique edge is to a tactic — never expanded into.
    assert "TA0009" not in expand_attack_ids(["T1056"], _EDGES)


def test_unknown_id_passes_through_unchanged():
    assert expand_attack_ids(["T9999"], _EDGES) == ("T9999",)


def test_output_is_deduped_and_sorted():
    out = expand_attack_ids(["T1056", "T1056.001"], _EDGES)
    assert out == tuple(sorted(set(out)))
    assert set(out) == {"T1056", "T1056.001", "T1056.002"}


def test_empty_inputs():
    assert expand_attack_ids([], _EDGES) == ()
    assert expand_attack_ids(["T1056.001"], []) == ("T1056.001",)


def test_expand_constraint_widens_attack_ids_only():
    c = PayloadConstraint(
        attack_ids=("T1056.001",), source_types=("otx",), entity_ids=("actor_G0016",)
    )
    out = expand_constraint(c, _EDGES)
    assert out.attack_ids == ("T1056", "T1056.001")
    assert out.source_types == ("otx",)  # untouched
    assert out.entity_ids == ("actor_G0016",)  # untouched


def test_expand_constraint_no_attack_ids_is_unchanged():
    c = PayloadConstraint(source_types=("mitre",))
    assert expand_constraint(c, _EDGES) == c
