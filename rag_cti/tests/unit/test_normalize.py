"""Unit tests for per-source declared normalization (ingestion §4)."""

from __future__ import annotations

import pytest

from rag_cti.ingest.normalize import (
    EntityMention,
    RelationMention,
    SourceClass,
    classify,
    normalize_infrastructure,
    normalize_mitre_relationship,
    normalize_otx_pulse,
)
from rag_cti.preprocess.indicators import IndicatorMention


def test_classify_maps_each_source():
    assert classify("mitre") is SourceClass.ONTOLOGY
    assert classify("otx") is SourceClass.WEAKLY_LABELED
    assert classify("pdf") is SourceClass.UNLABELED_NARRATIVE
    assert classify("whois") is SourceClass.INFRASTRUCTURE
    assert classify("pdns") is SourceClass.INFRASTRUCTURE
    assert classify("virustotal") is SourceClass.INFRASTRUCTURE


def test_classify_unknown_raises():
    with pytest.raises(ValueError, match="unknown source_type"):
        classify("nope")


def test_normalize_otx_emits_structural_mentions():
    raw = {
        "id": "pulse1",
        "adversary": "APT29",
        "attack_ids": ["T1566", "T1059"],
        "targeted_countries": ["Ukraine"],
        "malware_families": [{"display_name": "Cobalt Strike"}],
        "indicators": [{"indicator": "evil.com", "type": "domain"}],
        "modified": "2026-01-01T00:00:00",
    }
    rec = normalize_otx_pulse(raw, fetched_at="2026-06-14T00:00:00Z")

    assert rec.classification is SourceClass.WEAKLY_LABELED
    assert rec.provenance.source_id == "pulse1"
    assert rec.provenance.fetched_at == "2026-06-14T00:00:00Z"
    assert rec.provenance.source_version == "2026-01-01T00:00:00"
    assert EntityMention("APT29", "actor") in rec.entity_mentions
    assert EntityMention("Cobalt Strike", "family") in rec.entity_mentions
    assert EntityMention("T1566", "technique") in rec.entity_mentions
    assert EntityMention("Ukraine", "location") in rec.entity_mentions
    # predicate preserved from structure (zero inference)
    assert RelationMention("APT29", "uses", "T1566", "actor", "technique") in rec.relation_mentions
    assert (
        RelationMention("APT29", "targets", "Ukraine", "actor", "location") in rec.relation_mentions
    )
    assert rec.indicator_mentions[0].value == "evil.com"
    assert rec.indicator_mentions[0].canonical_type == "domain"


def test_normalize_otx_without_adversary_emits_no_relations():
    raw = {"id": "p", "attack_ids": ["T1566"], "indicators": []}
    rec = normalize_otx_pulse(raw)
    assert rec.relation_mentions == []  # no subject => no relation (no inference)
    assert EntityMention("T1566", "technique") in rec.entity_mentions


def _stix_index():
    actor = {"type": "intrusion-set", "id": "is--1", "name": "APT29"}
    malware = {"type": "malware", "id": "mal--1", "name": "Cobalt Strike"}
    technique = {
        "type": "attack-pattern",
        "id": "ap--1",
        "name": "Command and Scripting Interpreter",
        "external_references": [{"source_name": "mitre-attack", "external_id": "T1059"}],
    }
    return {o["id"]: o for o in (actor, malware, technique)}


def test_normalize_mitre_relationship_reads_predicate_from_structure():
    index = _stix_index()
    raw = {
        "id": "rel--1",
        "relationship_type": "uses",
        "source_ref": "is--1",
        "target_ref": "ap--1",
        "description": "APT29 used PowerShell.",
    }
    rec = normalize_mitre_relationship(raw, index)
    assert rec.classification is SourceClass.ONTOLOGY
    assert EntityMention("APT29", "actor") in rec.entity_mentions
    assert EntityMention("Command and Scripting Interpreter", "technique") in rec.entity_mentions
    assert rec.relation_mentions == [
        RelationMention("APT29", "uses", "T1059", "actor", "technique")
    ]
    assert rec.content == "APT29 used PowerShell."


def test_normalize_mitre_malware_subject_maps_to_family():
    index = _stix_index()
    raw = {
        "id": "rel--2",
        "relationship_type": "uses",
        "source_ref": "mal--1",
        "target_ref": "ap--1",
    }
    rec = normalize_mitre_relationship(raw, index)
    assert EntityMention("Cobalt Strike", "family") in rec.entity_mentions
    assert rec.relation_mentions[0].subject_type == "family"


def test_normalize_mitre_unresolvable_ref_raises():
    raw = {
        "id": "rel--x",
        "relationship_type": "uses",
        "source_ref": "missing",
        "target_ref": "ap--1",
    }
    with pytest.raises(ValueError, match="unresolvable"):
        normalize_mitre_relationship(raw, _stix_index())


def test_normalize_infrastructure_emits_indicator_no_relations():
    rec = normalize_infrastructure({"k": "v"}, "whois", "evil.com")
    assert rec.classification is SourceClass.INFRASTRUCTURE
    assert rec.relation_mentions == []
    assert rec.indicator_mentions == [IndicatorMention("evil.com", "domain", "domain")]
