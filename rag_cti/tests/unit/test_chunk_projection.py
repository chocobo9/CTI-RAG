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
]


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
