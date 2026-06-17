from __future__ import annotations

from rag_cti.retrieval.constraint_extract import (
    ExtractedEntity,
    build_constraint,
    extract_attack_ids,
    extract_source_types,
)

# Minimal ontology (OntologyNode shape from ontology_nodes_from_bundle).
_NODES = [
    {
        "ontology_id": "G0016",
        "type": "group",
        "name": "APT29",
        "aliases": ["Cozy Bear", "NOBELIUM"],
        "tactics": [],
        "attack_version": "18.1",
    },
    {
        "ontology_id": "S0154",
        "type": "software",
        "name": "Cobalt Strike",
        "aliases": ["cobaltstrike"],
        "tactics": [],
        "attack_version": "18.1",
    },
    {
        "ontology_id": "T1003",
        "type": "technique",
        "name": "OS Credential Dumping",
        "aliases": [],
        "tactics": [],
        "attack_version": "18.1",
    },
]


def _ent(name: str, type_: str) -> ExtractedEntity:
    return ExtractedEntity(name=name, type=type_)


# --- extract_attack_ids ---


def test_extract_attack_ids_finds_technique_and_subtechnique():
    assert extract_attack_ids("how about T1059 and T1059.001") == ("T1059", "T1059.001")


def test_extract_attack_ids_is_case_insensitive_and_uppercases():
    assert extract_attack_ids("uses t1003 for creds") == ("T1003",)


def test_extract_attack_ids_excludes_tactics_and_object_codes():
    # TA0001 (tactic), S0154 (software), G0016 (group) are NOT attack_ids.
    assert extract_attack_ids("TA0001 S0154 G0016 T1566") == ("T1566",)


def test_extract_attack_ids_dedupes_and_sorts():
    assert extract_attack_ids("T1059 again T1059 then T1003") == ("T1003", "T1059")


def test_extract_attack_ids_none_when_absent():
    assert extract_attack_ids("what malware does the group use") == ()


# --- extract_source_types ---


def test_extract_source_types_single():
    assert extract_source_types("look it up in whois records") == ("whois",)


def test_extract_source_types_multiple_sorted():
    assert extract_source_types("alienvault pulse and passive dns history") == ("otx", "pdns")


def test_extract_source_types_none_when_no_trigger():
    assert extract_source_types("what techniques does APT29 use") == ()


def test_extract_source_types_bare_report_not_a_trigger():
    assert extract_source_types("give me a report on this actor") == ()


# --- build_constraint: merge rules ---


def test_build_constraint_regex_attack_ids_only():
    c = build_constraint("persistence via T1547.001")
    assert c.attack_ids == ("T1547.001",)
    assert c.entity_ids == ()
    assert c.source_types == ()


def test_build_constraint_technique_entity_feeds_both_namespaces():
    c = build_constraint("spearphishing attachment", (_ent("T1566.001", "technique"),))
    assert c.attack_ids == ("T1566.001",)
    assert c.entity_ids == ("technique_T1566.001",)


def test_build_constraint_resolves_actor_and_family_entities():
    ents = (_ent("Cozy Bear", "actor"), _ent("Cobalt Strike", "family"))
    c = build_constraint("what does it use", ents, _NODES)
    assert c.entity_ids == ("actor_G0016", "family_S0154")


def test_build_constraint_drops_unresolvable_entity():
    c = build_constraint("q", (_ent("Totally Unknown APT", "actor"),), _NODES)
    assert c.entity_ids == ()


def test_build_constraint_actor_dropped_without_ontology_nodes():
    # name->id needs the alias table; absent it, named actors contribute nothing,
    # but a technique-id entity still resolves (it carries its own id).
    c = build_constraint("q", (_ent("Cozy Bear", "actor"), _ent("T1003", "technique")), None)
    assert c.entity_ids == ("technique_T1003",)
    assert c.attack_ids == ("T1003",)


def test_build_constraint_combines_regex_entity_and_source():
    ents = (_ent("APT29", "actor"), _ent("T1003", "technique"))
    c = build_constraint("APT29 credential dumping per the mitre att&ck matrix T1059", ents, _NODES)
    assert c.attack_ids == ("T1003", "T1059")
    assert set(c.entity_ids) == {"actor_G0016", "technique_T1003"}
    assert c.source_types == ("mitre",)


def test_build_constraint_all_empty_is_empty():
    assert build_constraint("what malware is bad").is_empty


def test_build_constraint_non_id_technique_name_contributes_nothing():
    # technique resolution is by id only; a prose name yields no attack_id.
    assert build_constraint("q", (_ent("spearphishing", "technique"),)).is_empty
