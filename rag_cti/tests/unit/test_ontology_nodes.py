"""Unit tests for OntologyNode extraction (knowledge-layer §3, authoritative mirror).

OntologyNode is the *definition* half of M1's ontology layer (edges live in
ontology_edges). One node per mirrored MITRE object: technique / sub-technique /
tactic / software (malware|tool) / group (intrusion-set). Zero inference.
"""

from __future__ import annotations

from rag_cti.preprocess.ontology_nodes import ontology_nodes_from_bundle

_COLLECTION = {
    "type": "x-mitre-collection",
    "id": "x-mitre-collection--x",
    "x_mitre_version": "18.1",
}

_TECHNIQUE = {
    "type": "attack-pattern",
    "id": "attack-pattern--t1003",
    "name": "OS Credential Dumping",
    "external_references": [{"source_name": "mitre-attack", "external_id": "T1003"}],
    "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "credential-access"}],
}

_SUBTECH = {
    "type": "attack-pattern",
    "id": "attack-pattern--t1003-002",
    "name": "LSASS Memory",
    "x_mitre_is_subtechnique": True,
    "external_references": [{"source_name": "mitre-attack", "external_id": "T1003.002"}],
    "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "credential-access"}],
}

_TACTIC = {
    "type": "x-mitre-tactic",
    "id": "x-mitre-tactic--credaccess",
    "name": "Credential Access",
    "x_mitre_shortname": "credential-access",
    "external_references": [{"source_name": "mitre-attack", "external_id": "TA0006"}],
}

_GROUP = {
    "type": "intrusion-set",
    "id": "intrusion-set--apt29",
    "name": "APT29",
    "aliases": ["APT29", "Cozy Bear", "NOBELIUM"],
    "external_references": [{"source_name": "mitre-attack", "external_id": "G0016"}],
}

_MALWARE = {
    "type": "malware",
    "id": "malware--hdoor",
    "name": "HDoor",
    "x_mitre_aliases": ["HDoor", "Custom HDoor"],
    "external_references": [{"source_name": "mitre-attack", "external_id": "S0061"}],
}

_TOOL = {
    "type": "tool",
    "id": "tool--net",
    "name": "Net",
    "x_mitre_aliases": ["Net", "net.exe"],
    "external_references": [{"source_name": "mitre-attack", "external_id": "S0039"}],
}


def _bundle(*objs):
    return {"type": "bundle", "objects": [_COLLECTION, *objs]}


def _by_id(nodes):
    return {n["ontology_id"]: n for n in nodes}


def test_technique_node_type_and_tactics():
    n = _by_id(ontology_nodes_from_bundle(_bundle(_TECHNIQUE)))["T1003"]
    assert n["type"] == "technique"
    assert n["name"] == "OS Credential Dumping"
    assert n["tactics"] == ["credential-access"]
    assert n["aliases"] == []


def test_subtechnique_is_still_type_technique():
    # The sub→parent hierarchy is an ontology *edge*, never a node type.
    n = _by_id(ontology_nodes_from_bundle(_bundle(_SUBTECH)))["T1003.002"]
    assert n["type"] == "technique"


def test_tactic_node_has_no_own_tactics():
    n = _by_id(ontology_nodes_from_bundle(_bundle(_TACTIC)))["TA0006"]
    assert n["type"] == "tactic"
    assert n["tactics"] == []


def test_group_aliases_from_aliases_field_excluding_canonical_name():
    n = _by_id(ontology_nodes_from_bundle(_bundle(_GROUP)))["G0016"]
    assert n["type"] == "group"
    assert n["name"] == "APT29"
    assert n["aliases"] == ["Cozy Bear", "NOBELIUM"]  # canonical name dropped from aliases


def test_malware_and_tool_map_to_software_with_x_mitre_aliases():
    nodes = _by_id(ontology_nodes_from_bundle(_bundle(_MALWARE, _TOOL)))
    assert nodes["S0061"]["type"] == "software"
    assert nodes["S0061"]["aliases"] == ["Custom HDoor"]
    assert nodes["S0039"]["type"] == "software"
    assert nodes["S0039"]["aliases"] == ["net.exe"]


def test_attack_version_from_collection_is_uniform():
    nodes = ontology_nodes_from_bundle(_bundle(_TECHNIQUE, _GROUP, _TACTIC))
    assert {n["attack_version"] for n in nodes} == {"18.1"}


def test_revoked_excluded():
    revoked = {**_MALWARE, "id": "malware--rev", "revoked": True}
    assert "S0061" not in _by_id(ontology_nodes_from_bundle(_bundle(revoked)))


def test_unmirrored_type_and_missing_attack_id_excluded():
    # x-mitre-data-source is NOT in _TYPE_MAP (we mirror techniques/tactics/software/
    # group/campaign/mitigation/detection-strategy), so it is excluded even with a DS id.
    data_source = {
        "type": "x-mitre-data-source",
        "id": "x-mitre-data-source--ds1",
        "name": "Process",
        "external_references": [{"source_name": "mitre-attack", "external_id": "DS0009"}],
    }
    no_id = {
        "type": "malware",
        "id": "malware--noid",
        "name": "Nameless",
        "external_references": [],
    }
    assert ontology_nodes_from_bundle(_bundle(data_source, no_id)) == []


def test_defensive_objects_are_mirrored():
    """course-of-action and x-mitre-detection-strategy mirror to mitigation /
    detection-strategy OntologyNodes (so mitigates/detects subjects resolve)."""
    coa = {
        "type": "course-of-action",
        "id": "course-of-action--m1",
        "name": "Antivirus/Antimalware",
        "external_references": [{"source_name": "mitre-attack", "external_id": "M1049"}],
    }
    det = {
        "type": "x-mitre-detection-strategy",
        "id": "x-mitre-detection-strategy--d1",
        "name": "Detection Strategy X",
        "external_references": [{"source_name": "mitre-attack", "external_id": "DET0001"}],
    }
    by_id = _by_id(ontology_nodes_from_bundle(_bundle(coa, det)))
    assert by_id["M1049"]["type"] == "mitigation"
    assert by_id["DET0001"]["type"] == "detection-strategy"


def test_deterministic_sort_by_ontology_id():
    nodes = ontology_nodes_from_bundle(_bundle(_TOOL, _GROUP, _TECHNIQUE, _TACTIC, _MALWARE))
    ids = [n["ontology_id"] for n in nodes]
    assert ids == sorted(ids)
