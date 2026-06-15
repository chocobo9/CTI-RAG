"""Tests for MitreRelationshipConnector.

Distribution: happy 2 / edge 3 / adversarial 2
All fixtures use real STIX 2.1 object structure with realistic IDs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from rag_cti.connectors.mitre_relationship import MitreRelationshipConnector

# ---------------------------------------------------------------------------
# Fixtures: realistic STIX objects
# ---------------------------------------------------------------------------

_INTRUSION_SET_APT29 = {
    "type": "intrusion-set",
    "id": "intrusion-set--899ce53f-13a0-479b-a0e4-67d46e241542",
    "name": "APT29",
    "created": "2017-05-31T21:31:48.664Z",
    "modified": "2024-04-18T15:31:30.641Z",
}

_CAMPAIGN_NIGHTSKY = {
    "type": "campaign",
    "id": "campaign--7e21077d-2589-43a7-a5f9-490061289526",
    "name": "Night Dragon",
    "created": "2024-08-07T19:44:50.695Z",
    "modified": "2025-04-16T21:55:34.508Z",
}

_ATTACK_PATTERN_T1059 = {
    "type": "attack-pattern",
    "id": "attack-pattern--d1fcf083-a721-4223-aedf-bf8960798d62",
    "name": "Command and Scripting Interpreter",
    "created": "2017-05-31T21:30:41.022Z",
    "modified": "2024-10-14T22:11:30.271Z",
    "external_references": [{"source_name": "mitre-attack", "external_id": "T1059"}],
}

_MALWARE_COBALTSTRIKE = {
    "type": "malware",
    "id": "malware--a7881f21-e978-4fe4-af56-92c9416a2616",
    "name": "Cobalt Strike",
    "created": "2017-05-31T21:32:09.460Z",
    "modified": "2024-10-14T22:11:30.271Z",
}

_TOOL_MIMIKATZ = {
    "type": "tool",
    "id": "tool--afc079f3-c0ea-4096-b75d-3f05338b01e0",
    "name": "Mimikatz",
    "created": "2017-05-31T21:32:11.544Z",
    "modified": "2024-10-14T22:11:30.271Z",
}

_IDENTITY = {
    "type": "identity",
    "id": "identity--c78cb6e5-0c4b-4611-8297-d1b8b55e40b5",
    "name": "The MITRE Corporation",
}

_COURSE_OF_ACTION = {
    "type": "course-of-action",
    "id": "course-of-action--ffffffff-0000-0000-0000-000000000001",
    "name": "User Training",
}

# Relationships

_REL_APT29_USES_T1059 = {
    "type": "relationship",
    "id": "relationship--aaa11111-1111-1111-1111-111111111111",
    "relationship_type": "uses",
    "source_ref": _INTRUSION_SET_APT29["id"],
    "target_ref": _ATTACK_PATTERN_T1059["id"],
    "description": "APT29 used PowerShell for C2 communication via T1059.",
    "created": "2021-01-01T00:00:00.000Z",
    "modified": "2024-01-01T00:00:00.000Z",
}

_REL_CAMPAIGN_ATTRIBUTED_TO = {
    "type": "relationship",
    "id": "relationship--bbb22222-2222-2222-2222-222222222222",
    "relationship_type": "attributed-to",
    "source_ref": _CAMPAIGN_NIGHTSKY["id"],
    "target_ref": _INTRUSION_SET_APT29["id"],
    "description": "Night Dragon is attributed to APT29.",
    "created": "2024-08-07T19:44:50.695Z",
    "modified": "2025-04-16T21:55:34.508Z",
}

_REL_APT29_USES_MALWARE = {
    "type": "relationship",
    "id": "relationship--ccc33333-3333-3333-3333-333333333333",
    "relationship_type": "uses",
    "source_ref": _INTRUSION_SET_APT29["id"],
    "target_ref": _MALWARE_COBALTSTRIKE["id"],
    "description": "APT29 deployed Cobalt Strike beacons.",
    "created": "2021-01-01T00:00:00.000Z",
    "modified": "2024-01-01T00:00:00.000Z",
}

_REL_NO_DESCRIPTION = {
    "type": "relationship",
    "id": "relationship--ddd44444-4444-4444-4444-444444444444",
    "relationship_type": "uses",
    "source_ref": _INTRUSION_SET_APT29["id"],
    "target_ref": _TOOL_MIMIKATZ["id"],
    "created": "2021-01-01T00:00:00.000Z",
    "modified": "2024-01-01T00:00:00.000Z",
}

_REL_DANGLING_REF = {
    "type": "relationship",
    "id": "relationship--eee55555-5555-5555-5555-555555555555",
    "relationship_type": "uses",
    "source_ref": "intrusion-set--00000000-0000-0000-0000-000000000000",
    "target_ref": _ATTACK_PATTERN_T1059["id"],
    "description": "This ref does not resolve.",
    "created": "2021-01-01T00:00:00.000Z",
    "modified": "2024-01-01T00:00:00.000Z",
}

_REL_MALWARE_USES_TECHNIQUE = {
    "type": "relationship",
    "id": "relationship--fff66666-6666-6666-6666-666666666666",
    "relationship_type": "uses",
    "source_ref": _MALWARE_COBALTSTRIKE["id"],
    "target_ref": _ATTACK_PATTERN_T1059["id"],
    "description": "Cobalt Strike uses T1059 for execution.",
    "created": "2021-01-01T00:00:00.000Z",
    "modified": "2024-01-01T00:00:00.000Z",
}

_REL_REVOKED = {
    "type": "relationship",
    "id": "relationship--77777777-7777-7777-7777-777777777777",
    "relationship_type": "uses",
    "source_ref": _INTRUSION_SET_APT29["id"],
    "target_ref": _ATTACK_PATTERN_T1059["id"],
    "revoked": True,
    "description": "This relationship is revoked.",
    "created": "2021-01-01T00:00:00.000Z",
    "modified": "2024-01-01T00:00:00.000Z",
}

_REL_MITIGATES = {
    "type": "relationship",
    "id": "relationship--88888888-8888-8888-8888-888888888888",
    "relationship_type": "mitigates",
    "source_ref": _COURSE_OF_ACTION["id"],
    "target_ref": _ATTACK_PATTERN_T1059["id"],
    "description": "User Training mitigates T1059.",
    "created": "2021-01-01T00:00:00.000Z",
    "modified": "2024-01-01T00:00:00.000Z",
}


def _make_bundle(*objects) -> dict:
    return {"type": "bundle", "id": "bundle--test", "objects": list(objects)}


def _write_bundle(tmp_path: Path, *objects) -> Path:
    bundle = _make_bundle(
        _IDENTITY,
        _COURSE_OF_ACTION,
        _INTRUSION_SET_APT29,
        _CAMPAIGN_NIGHTSKY,
        _ATTACK_PATTERN_T1059,
        _MALWARE_COBALTSTRIKE,
        _TOOL_MIMIKATZ,
        *objects,
    )
    p = tmp_path / "enterprise-attack.json"
    p.write_text(json.dumps(bundle), encoding="utf-8")
    return p


def _fetch_and_convert(connector: MitreRelationshipConnector) -> list:
    return list(connector.fetch_documents())


# ---------------------------------------------------------------------------
# Happy path (2)
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_intrusion_set_uses_attack_pattern(self, tmp_path: Path) -> None:
        """intrusion-set -> uses -> attack-pattern produces correct doc."""
        bundle_path = _write_bundle(tmp_path, _REL_APT29_USES_T1059)
        conn = MitreRelationshipConnector(bundle_path=bundle_path)
        docs = _fetch_and_convert(conn)

        assert len(docs) == 1
        doc = docs[0]
        assert doc.source == "mitre"
        assert "APT29" in doc.content
        assert "T1059" in doc.content
        assert doc.metadata["attack_id"] == "T1059"
        assert doc.metadata["relationship_type"] == "uses"
        assert doc.metadata["source_name"] == "APT29"
        assert doc.metadata["target_name"] == "Command and Scripting Interpreter"

    def test_campaign_attributed_to_intrusion_set(self, tmp_path: Path) -> None:
        """campaign -> attributed-to -> intrusion-set."""
        bundle_path = _write_bundle(tmp_path, _REL_CAMPAIGN_ATTRIBUTED_TO)
        conn = MitreRelationshipConnector(bundle_path=bundle_path)
        docs = _fetch_and_convert(conn)

        assert len(docs) == 1
        doc = docs[0]
        assert doc.metadata["relationship_type"] == "attributed-to"
        assert doc.metadata["attack_id"] == ""
        assert "Night Dragon" in doc.content
        assert "APT29" in doc.content


# ---------------------------------------------------------------------------
# Edge cases (3)
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_target_is_malware_no_attack_id(self, tmp_path: Path) -> None:
        """intrusion-set -> uses -> malware: attack_id should be empty."""
        bundle_path = _write_bundle(tmp_path, _REL_APT29_USES_MALWARE)
        conn = MitreRelationshipConnector(bundle_path=bundle_path)
        docs = _fetch_and_convert(conn)

        assert len(docs) == 1
        doc = docs[0]
        assert doc.metadata["attack_id"] == ""
        assert "Cobalt Strike" in doc.content
        assert "APT29" in doc.content

    def test_no_description_renders_first_line_only(self, tmp_path: Path) -> None:
        """Missing description -> content is just the first line."""
        bundle_path = _write_bundle(tmp_path, _REL_NO_DESCRIPTION)
        conn = MitreRelationshipConnector(bundle_path=bundle_path)
        docs = _fetch_and_convert(conn)

        assert len(docs) == 1
        doc = docs[0]
        assert "\n" not in doc.content
        assert "APT29" in doc.content
        assert "Mimikatz" in doc.content

    def test_dangling_source_ref_skipped(self, tmp_path: Path) -> None:
        """source_ref pointing to non-existent id -> edge skipped, no crash."""
        bundle_path = _write_bundle(tmp_path, _REL_DANGLING_REF)
        conn = MitreRelationshipConnector(bundle_path=bundle_path)
        docs = _fetch_and_convert(conn)

        assert len(docs) == 0


# ---------------------------------------------------------------------------
# Adversarial (2)
# ---------------------------------------------------------------------------


class TestAdversarial:
    def test_malware_uses_technique_included(self, tmp_path: Path) -> None:
        """malware/tool -> uses -> attack-pattern IS collected (decision 2026-06):
        malware and tool are threat-entity subjects; dropping them lost ~10.6k
        edges. The earlier behaviour excluded them — deliberately reversed."""
        bundle_path = _write_bundle(
            tmp_path,
            _REL_APT29_USES_T1059,
            _REL_MALWARE_USES_TECHNIQUE,
        )
        conn = MitreRelationshipConnector(bundle_path=bundle_path)
        docs = _fetch_and_convert(conn)

        assert len(docs) == 2
        source_names = {d.metadata["source_name"] for d in docs}
        assert source_names == {"APT29", "Cobalt Strike"}

    def test_mitigates_edge_excluded(self, tmp_path: Path) -> None:
        """course-of-action -> mitigates -> attack-pattern MUST be filtered out:
        mitigates is a defensive predicate, not a threat fact edge."""
        bundle_path = _write_bundle(tmp_path, _REL_APT29_USES_T1059, _REL_MITIGATES)
        conn = MitreRelationshipConnector(bundle_path=bundle_path)
        docs = _fetch_and_convert(conn)

        assert len(docs) == 1
        assert docs[0].metadata["source_name"] == "APT29"

    def test_revoked_relationship_excluded(self, tmp_path: Path) -> None:
        """Revoked relationship MUST be filtered out."""
        bundle_path = _write_bundle(tmp_path, _REL_REVOKED)
        conn = MitreRelationshipConnector(bundle_path=bundle_path)
        docs = _fetch_and_convert(conn)

        assert len(docs) == 0


def test_description_only_drops_redundant_template_first_line(tmp_path: Path) -> None:
    """retrieval §5: embed the procedure description only; the templated
    'X uses Y (Tnnnn)' first line duplicates the Fact (now in relations[] / the
    knowledge layer) and is dropped, leaving the genuine prose to be embedded."""
    bundle_path = _write_bundle(tmp_path, _REL_APT29_USES_T1059)
    doc = list(MitreRelationshipConnector(bundle_path=bundle_path).fetch_documents())[0]
    assert doc.content == "APT29 used PowerShell for C2 communication via T1059."
    assert "uses Command and Scripting Interpreter (T1059)" not in doc.content


def test_retrieved_at_is_fetched_at_not_stix_modified(tmp_path: Path) -> None:
    """retrieved_at = when WE fetched (passed in), deterministic; the edge's STIX
    modified is preserved separately in metadata.last_modified (Rule 0)."""
    fetched = datetime(2026, 6, 1, tzinfo=UTC)
    bundle_path = _write_bundle(tmp_path, _REL_APT29_USES_T1059)
    doc = list(
        MitreRelationshipConnector(bundle_path=bundle_path, fetched_at=fetched).fetch_documents()
    )[0]
    assert doc.retrieved_at == fetched
    assert doc.metadata["last_modified"] == "2024-01-01T00:00:00.000Z"  # source time, separate


def test_retrieved_at_default_is_deterministic_sentinel(tmp_path: Path) -> None:
    """No fetched_at => deterministic sentinel, never wall-clock (rebuild reproduces)."""
    bundle_path = _write_bundle(tmp_path, _REL_APT29_USES_T1059)
    d1 = list(MitreRelationshipConnector(bundle_path=bundle_path).fetch_documents())[0]
    d2 = list(MitreRelationshipConnector(bundle_path=bundle_path).fetch_documents())[0]
    assert d1.retrieved_at == d2.retrieved_at
