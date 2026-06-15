"""Unit tests for the Entity registry (M1, knowledge-layer §3 + construction §3).

Resolution policy is the gated part of M1:
- exact canonical name / exact alias -> reuse the MITRE-backed entity_id (certain)
- substring / fuzzy -> a held **merge candidate**, never auto-applied (DECISION-1)
- no match -> an **orphan** entity, kept and flagged, never dropped (DECISION-2)

Every distinct mention yields exactly one Entity (nothing is dropped).
"""

from __future__ import annotations

from rag_cti.preprocess.entity_registry import build_entity_registry

# OntologyNodes as produced by ontology_nodes_from_bundle (group = intrusion-set).
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
