"""Unit tests for ontology-edge extraction (knowledge-layer §4, axiomatic)."""

from __future__ import annotations

from rag_cti.preprocess.ontology_edges import ontology_edges_from_bundle

_TACTIC_CRED = {
    "type": "x-mitre-tactic",
    "id": "x-mitre-tactic--credaccess",
    "x_mitre_shortname": "credential-access",
    "external_references": [{"source_name": "mitre-attack", "external_id": "TA0006"}],
}

_PARENT = {
    "type": "attack-pattern",
    "id": "attack-pattern--parent",
    "external_references": [{"source_name": "mitre-attack", "external_id": "T1003"}],
    "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "credential-access"}],
}

_SUB = {
    "type": "attack-pattern",
    "id": "attack-pattern--sub",
    "external_references": [{"source_name": "mitre-attack", "external_id": "T1003.002"}],
    "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "credential-access"}],
}

_REL_SUBTECH = {
    "type": "relationship",
    "id": "relationship--sub-of",
    "relationship_type": "subtechnique-of",
    "source_ref": "attack-pattern--sub",
    "target_ref": "attack-pattern--parent",
}


def _bundle(*objs):
    return {"type": "bundle", "objects": [_TACTIC_CRED, _PARENT, _SUB, *objs]}


def test_subtechnique_of_edge():
    edges = ontology_edges_from_bundle(_bundle(_REL_SUBTECH))
    assert {"child": "T1003.002", "parent": "T1003", "edge": "subtechnique-of"} in edges


def test_belongs_to_tactic_edge_maps_shortname_to_ta_id():
    edges = ontology_edges_from_bundle(_bundle(_REL_SUBTECH))
    assert {"child": "T1003", "parent": "TA0006", "edge": "belongs-to-tactic"} in edges
    assert {"child": "T1003.002", "parent": "TA0006", "edge": "belongs-to-tactic"} in edges


def test_revoked_relationship_excluded():
    revoked = {**_REL_SUBTECH, "id": "relationship--rev", "revoked": True}
    edges = ontology_edges_from_bundle(_bundle(revoked))
    assert not any(e["edge"] == "subtechnique-of" for e in edges)


def test_edges_deduped_and_sorted():
    dup = {**_REL_SUBTECH, "id": "relationship--dup"}  # same child/parent, different stix id
    edges = ontology_edges_from_bundle(_bundle(_REL_SUBTECH, dup))
    subtech = [e for e in edges if e["edge"] == "subtechnique-of"]
    assert len(subtech) == 1  # deduped
    keys = [(e["child"], e["parent"], e["edge"]) for e in edges]
    assert keys == sorted(keys)  # deterministic order (child, parent, edge)


def test_no_edges_when_no_mitre_id():
    odd = {
        "type": "attack-pattern",
        "id": "attack-pattern--noid",
        "external_references": [],
        "kill_chain_phases": [
            {"kill_chain_name": "mitre-attack", "phase_name": "credential-access"}
        ],
    }
    edges = ontology_edges_from_bundle({"type": "bundle", "objects": [_TACTIC_CRED, odd]})
    assert edges == []
