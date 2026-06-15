"""Unit tests for the Entity registry (M1, knowledge-layer §3 + construction §3).

Resolution policy is the gated part of M1:
- exact canonical name / exact alias -> reuse the MITRE-backed entity_id (certain)
- substring / fuzzy -> a held **merge candidate**, never auto-applied (DECISION-1)
- no match -> an **orphan** entity, kept and flagged, never dropped (DECISION-2)

Every distinct mention yields exactly one Entity (nothing is dropped).
"""

from __future__ import annotations

from rag_cti.ingest.normalize import RelationMention
from rag_cti.preprocess.entity_registry import build_entity_registry, resolve_relations

# OntologyNodes as produced by ontology_nodes_from_bundle (group = intrusion-set).
_NODES = [
    {
        "ontology_id": "T1003",
        "type": "technique",
        "name": "OS Credential Dumping",
        "aliases": [],
        "tactics": ["credential-access"],
        "attack_version": "18.1",
    },
    {
        "ontology_id": "G0016",
        "type": "group",
        "name": "APT29",
        "aliases": ["Cozy Bear", "NOBELIUM"],
        "tactics": [],
        "attack_version": "18.1",
    },
    {
        "ontology_id": "G0080",
        "type": "group",
        "name": "Cobalt Group",
        "aliases": ["Cobalt Gang", "GOLD KINGSWOOD"],
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
]


def _entities(result):
    return {e["entity_id"]: e for e in result["entities"]}


def test_exact_name_resolves_and_reuses_ontology_id():
    r = build_entity_registry([("APT29", "actor")], _NODES)
    e = _entities(r)["actor_G0016"]
    assert e["ontology_id"] == "G0016"
    assert e["type"] == "actor"
    assert e["canonical_name"] == "APT29"
    assert e["resolution"] == "exact_name"


def test_exact_alias_resolves_to_same_entity():
    # "cozy bear" (an alias, any casing) resolves to APT29's entity.
    r = build_entity_registry([("cozy bear", "actor")], _NODES)
    e = _entities(r)["actor_G0016"]
    assert e["ontology_id"] == "G0016"
    assert e["resolution"] == "exact_alias"


def test_two_mentions_one_entity_reused_not_duplicated():
    r = build_entity_registry([("APT29", "actor"), ("NOBELIUM", "actor")], _NODES)
    ids = [e["entity_id"] for e in r["entities"]]
    assert ids.count("actor_G0016") == 1  # same fact-anchor, one Entity


def test_substring_is_merge_candidate_not_auto_merged():
    # "Cobalt" substring-matches both Cobalt Group (actor) and Cobalt Strike
    # (software). DECISION-1: never auto-merge — it becomes an orphan + candidates.
    r = build_entity_registry([("Cobalt", "actor")], _NODES)
    ents = r["entities"]
    assert len(ents) == 1
    assert ents[0]["ontology_id"] is None  # NOT fused into G0080 or S0154
    assert ents[0]["resolution"] == "orphan"
    cand_oids = {c["candidate_ontology_id"] for c in r["merge_candidates"]}
    assert "G0080" in cand_oids  # surfaced for review, held not applied


def test_unresolved_becomes_orphan_kept_not_dropped():
    r = build_entity_registry([("[unnamed group]", "actor")], _NODES)
    ents = r["entities"]
    assert len(ents) == 1
    e = ents[0]
    assert e["ontology_id"] is None
    assert e["resolution"] == "orphan"
    assert e["canonical_name"] == "[unnamed group]"
    assert e["entity_id"].startswith("actor_orphan_")


def test_nothing_dropped_every_mention_yields_an_entity():
    mentions = [("APT29", "actor"), ("Cobalt", "actor"), ("totally unknown", "actor")]
    r = build_entity_registry(mentions, _NODES)
    # 3 distinct mentions -> 3 entities (1 resolved, 2 orphan), none lost.
    assert len(r["entities"]) == 3
    resolved = [e for e in r["entities"] if e["ontology_id"]]
    orphans = [e for e in r["entities"] if not e["ontology_id"]]
    assert len(resolved) == 1
    assert len(orphans) == 2


def test_deterministic_order_by_entity_id():
    mentions = [("totally unknown", "actor"), ("APT29", "actor"), ("Cobalt", "actor")]
    r = build_entity_registry(mentions, _NODES)
    ids = [e["entity_id"] for e in r["entities"]]
    assert ids == sorted(ids)


def test_resolved_entity_carries_ontology_aliases():
    r = build_entity_registry([("APT29", "actor")], _NODES)
    e = _entities(r)["actor_G0016"]
    assert e["aliases"] == ["Cozy Bear", "NOBELIUM"]


def test_technique_resolved_by_attack_id_not_by_name():
    # A technique mention is its attack_id (= the ontology_id), resolved directly
    # — exact identity, ungated. Name/alias matching does not apply.
    e = _entities(build_entity_registry([("T1003", "technique")], _NODES))["technique_T1003"]
    assert e["ontology_id"] == "T1003"
    assert e["resolution"] == "exact_id"
    assert e["canonical_name"] == "OS Credential Dumping"


def test_unknown_attack_id_becomes_orphan_technique():
    r = build_entity_registry([("T9999", "technique")], _NODES)
    assert r["entities"][0]["ontology_id"] is None
    assert r["entities"][0]["resolution"] == "orphan"


def test_family_resolves_to_software_node():
    e = _entities(build_entity_registry([("Cobalt Strike", "family")], _NODES))["family_S0154"]
    assert e["ontology_id"] == "S0154"
    assert e["type"] == "family"


def test_resolve_relations_maps_subject_and_object_to_entity_ids():
    rels = [RelationMention("APT29", "uses", "T1003", "actor", "technique")]
    triples = resolve_relations(rels, _NODES)
    assert triples == [
        {"subject_id": "actor_G0016", "predicate": "uses", "object_id": "technique_T1003"}
    ]


def test_resolve_relations_keeps_orphan_subject_and_object():
    # campaign (not mirrored) -> orphan subject; a location -> orphan object.
    # Resolved but not dropped, so the edge survives with stable ids (DECISION-2).
    rels = [RelationMention("Operation X", "targets", "Iran", "campaign", "location")]
    triple = resolve_relations(rels, _NODES)[0]
    assert triple["subject_id"].startswith("campaign_orphan_")
    assert triple["object_id"].startswith("location_orphan_")
    assert triple["predicate"] == "targets"


def test_ambiguous_exact_alias_orphans_with_all_candidates_not_silent_merge():
    """A surface string that is the exact alias of TWO nodes (like the real shared
    alias "DNSMessenger" on S0145 + S0146) must NOT silently bind to whichever
    iterates first — it orphans and surfaces every claimant (Rule 0 / DECISION-1)."""
    nodes = [
        {
            "ontology_id": "S0145",
            "type": "software",
            "name": "POWERSOURCE",
            "aliases": ["DNSMessenger"],
            "tactics": [],
            "attack_version": "18.1",
        },
        {
            "ontology_id": "S0146",
            "type": "software",
            "name": "TEXTMATE",
            "aliases": ["DNSMessenger"],
            "tactics": [],
            "attack_version": "18.1",
        },
    ]
    r = build_entity_registry([("DNSMessenger", "family")], nodes)
    e = r["entities"][0]
    assert e["ontology_id"] is None
    assert e["resolution"] == "orphan"
    assert sorted(c["candidate_ontology_id"] for c in r["merge_candidates"]) == ["S0145", "S0146"]


def test_ambiguous_exact_name_orphans_not_silent_merge():
    nodes = [
        {
            "ontology_id": "G0001",
            "type": "group",
            "name": "Twins",
            "aliases": [],
            "tactics": [],
            "attack_version": "18.1",
        },
        {
            "ontology_id": "G0002",
            "type": "group",
            "name": "Twins",
            "aliases": [],
            "tactics": [],
            "attack_version": "18.1",
        },
    ]
    r = build_entity_registry([("Twins", "actor")], nodes)
    assert r["entities"][0]["ontology_id"] is None
    assert sorted(c["candidate_ontology_id"] for c in r["merge_candidates"]) == ["G0001", "G0002"]


def test_id_resolution_is_case_insensitive():
    r = build_entity_registry([("t1003", "technique")], _NODES)
    assert r["entities"][0]["entity_id"] == "technique_T1003"
    assert r["entities"][0]["ontology_id"] == "T1003"
