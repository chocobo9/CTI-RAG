"""Unit tests for chunk payload projection (M2 retrieval-layer §4).

A normalized record's typed mentions project into the payload filter fields
(source_type / attack_ids / entity_ids / relations) with entity_ids and
relations resolved to stable ids via the M1 registry — never strings.
"""

from __future__ import annotations

from rag_cti.ingest.normalize import (
    EntityMention,
    NormalizedRecord,
    Provenance,
    RelationMention,
    SourceClass,
    normalize_infrastructure,
    normalize_mitre_relationship,
)
from rag_cti.preprocess.chunk_projection import project_chunk

_NODES = [
    {
        "ontology_id": "G0016",
        "type": "group",
        "name": "APT29",
        "aliases": ["Cozy Bear"],
        "tactics": [],
        "attack_version": "18.1",
    },
    {
        "ontology_id": "T1003",
        "type": "technique",
        "name": "OS Credential Dumping",
        "aliases": [],
        "tactics": ["credential-access"],
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

# Minimal real STIX index for normalize_mitre_relationship (the path that broke).
_STIX = {
    "is--1": {
        "type": "intrusion-set",
        "id": "is--1",
        "name": "APT29",
        "external_references": [{"source_name": "mitre-attack", "external_id": "G0016"}],
    },
    "mal--1": {
        "type": "malware",
        "id": "mal--1",
        "name": "Cobalt Strike",
        "external_references": [{"source_name": "mitre-attack", "external_id": "S0154"}],
    },
    "ap--1": {
        "type": "attack-pattern",
        "id": "ap--1",
        "name": "OS Credential Dumping",
        "external_references": [{"source_name": "mitre-attack", "external_id": "T1003"}],
    },
}


def _rel(src, tgt, rtype="uses"):
    return {
        "id": f"rel--{src}-{tgt}",
        "relationship_type": rtype,
        "source_ref": src,
        "target_ref": tgt,
    }


def _record() -> NormalizedRecord:
    return NormalizedRecord(
        provenance=Provenance(source_type="otx", source_id="p1"),
        classification=SourceClass.WEAKLY_LABELED,
        content="...",
        entity_mentions=[
            EntityMention("APT29", "actor"),
            EntityMention("T1003", "technique"),
            EntityMention("Iran", "location"),
        ],
        relation_mentions=[
            RelationMention("APT29", "uses", "T1003", "actor", "technique"),
            RelationMention("APT29", "targets", "Iran", "actor", "location"),
        ],
    )


def test_source_type_from_provenance():
    assert project_chunk(_record(), _NODES)["source_type"] == "otx"


def test_attack_ids_are_the_technique_mentions():
    assert project_chunk(_record(), _NODES)["attack_ids"] == ["T1003"]


def test_entity_ids_resolved_and_orphan_deduped_and_sorted():
    eids = project_chunk(_record(), _NODES)["entity_ids"]
    assert "actor_G0016" in eids  # resolved actor
    assert "technique_T1003" in eids  # technique by attack id
    assert any(e.startswith("location_orphan_") for e in eids)  # no MITRE location
    assert eids == sorted(eids)


def test_relations_resolved_to_entity_id_triples():
    rels = project_chunk(_record(), _NODES)["relations"]
    assert {
        "subject_id": "actor_G0016",
        "predicate": "uses",
        "object_id": "technique_T1003",
    } in rels


def test_narrative_record_with_no_structured_mentions_projects_empty():
    rec = NormalizedRecord(
        provenance=Provenance(source_type="pdf", source_id="d1"),
        classification=SourceClass.UNLABELED_NARRATIVE,
        content="prose only",
    )
    assert project_chunk(rec, _NODES) == {
        "source_type": "pdf",
        "attack_ids": [],
        "entity_ids": [],
        "relations": [],
    }


# --- end-to-end regression: real normalize -> project_chunk (the path that broke) ---


def test_mitre_relationship_to_technique_projects_resolved_not_orphan():
    """actor uses technique: attack_ids = T#### (not the technique name); the
    technique entity_id resolves (not technique_orphan); relations[] agrees."""
    rec = normalize_mitre_relationship(_rel("is--1", "ap--1"), _STIX)
    proj = project_chunk(rec, _NODES)
    assert proj["attack_ids"] == ["T1003"]
    assert "technique_T1003" in proj["entity_ids"]
    assert "actor_G0016" in proj["entity_ids"]
    assert not any("orphan" in e for e in proj["entity_ids"])
    assert proj["relations"] == [
        {"subject_id": "actor_G0016", "predicate": "uses", "object_id": "technique_T1003"}
    ]


def test_mitre_relationship_to_software_entity_id_and_relation_agree():
    """actor uses malware: the software resolves to ONE id in BOTH entity_ids and
    relations[].object_id — no split into family_S#### vs family_orphan."""
    rec = normalize_mitre_relationship(_rel("is--1", "mal--1"), _STIX)
    proj = project_chunk(rec, _NODES)
    assert "family_S0154" in proj["entity_ids"]
    assert proj["relations"][0]["object_id"] == "family_S0154"
    assert not any("orphan" in e for e in proj["entity_ids"])


def test_field_source_chunk_carries_indicator_in_entity_ids():
    """A field-source (infrastructure) chunk's keying indicator IS its entity and
    must appear in entity_ids (retrieval §4/§5)."""
    rec = normalize_infrastructure({"k": "v"}, source_type="vt", indicator_value="evil.com")
    proj = project_chunk(rec, _NODES)
    assert proj["source_type"] == "vt"
    assert len(proj["entity_ids"]) == 1
    assert proj["entity_ids"][0].startswith("indicator_")


def test_mitre_mitigates_and_detects_resolve_to_defensive_entities():
    """Defensive edges: course-of-action mitigates / detection-strategy detects a
    technique. Subjects resolve by name to mitigation_M#### / detection-strategy_DET####
    (not orphan); the technique object resolves by attack id."""
    nodes = [
        {
            "ontology_id": "T1003",
            "type": "technique",
            "name": "OS Credential Dumping",
            "aliases": [],
            "tactics": [],
            "attack_version": "18.1",
        },
        {
            "ontology_id": "M1049",
            "type": "mitigation",
            "name": "Antivirus/Antimalware",
            "aliases": [],
            "tactics": [],
            "attack_version": "18.1",
        },
        {
            "ontology_id": "DET0001",
            "type": "detection-strategy",
            "name": "Detection Strategy for OS Credential Dumping",
            "aliases": [],
            "tactics": [],
            "attack_version": "18.1",
        },
    ]
    stix = {
        "coa--1": {
            "type": "course-of-action",
            "id": "coa--1",
            "name": "Antivirus/Antimalware",
            "external_references": [{"source_name": "mitre-attack", "external_id": "M1049"}],
        },
        "det--1": {
            "type": "x-mitre-detection-strategy",
            "id": "det--1",
            "name": "Detection Strategy for OS Credential Dumping",
            "external_references": [{"source_name": "mitre-attack", "external_id": "DET0001"}],
        },
        "ap--1": {
            "type": "attack-pattern",
            "id": "ap--1",
            "name": "OS Credential Dumping",
            "external_references": [{"source_name": "mitre-attack", "external_id": "T1003"}],
        },
    }

    mit = normalize_mitre_relationship(_rel("coa--1", "ap--1", "mitigates"), stix)
    proj = project_chunk(mit, nodes)
    assert proj["relations"] == [
        {"subject_id": "mitigation_M1049", "predicate": "mitigates", "object_id": "technique_T1003"}
    ]
    assert "mitigation_M1049" in proj["entity_ids"]
    assert not any("orphan" in e for e in proj["entity_ids"])

    det = normalize_mitre_relationship(_rel("det--1", "ap--1", "detects"), stix)
    projd = project_chunk(det, nodes)
    assert projd["relations"] == [
        {
            "subject_id": "detection-strategy_DET0001",
            "predicate": "detects",
            "object_id": "technique_T1003",
        }
    ]
    assert not any("orphan" in e for e in projd["entity_ids"])


def test_infrastructure_record_builds_infra_edges_from_metadata():
    """A field-source record carrying structured resolutions (domain→ip with asn)
    projects infra edges; every relation endpoint is also an entity_id."""
    raw = {
        "domain": "evil.com",
        "resolutions": [{"value": "1.2.3.4", "ip": "1.2.3.4", "record_type": "A", "asn": "AS123"}],
        "subdomains": [],
    }
    rec = normalize_infrastructure(raw, source_type="pdns", indicator_value="evil.com")
    proj = project_chunk(rec, _NODES)
    preds = {r["predicate"] for r in proj["relations"]}
    assert {"resolves-to", "belongs-to"} <= preds
    endpoints = {r["subject_id"] for r in proj["relations"]} | {
        r["object_id"] for r in proj["relations"]
    }
    assert endpoints <= set(proj["entity_ids"])
