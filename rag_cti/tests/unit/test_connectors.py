from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_cti.connectors.mitre_attack import MitreAttackConnector
from rag_cti.connectors.passive_dns import PassiveDNSConnector
from rag_cti.connectors.whois_connector import WHOISConnector
from rag_cti.types import Document

MITRE_STUB = {
    "type": "bundle",
    "objects": [
        {
            "type": "attack-pattern",
            "id": "attack-pattern--abc123",
            "name": "Spearphishing Attachment",
            "description": "Adversaries send malicious attachments via email.",
            "external_references": [{"source_name": "mitre-attack", "external_id": "T1566.001"}],
            "kill_chain_phases": [
                {"kill_chain_name": "mitre-attack", "phase_name": "initial-access"}
            ],
            "x_mitre_platforms": ["Windows", "macOS"],
            "x_mitre_is_subtechnique": True,
            "modified": "2024-01-01T00:00:00.000Z",
            "revoked": False,
        },
        {
            "type": "attack-pattern",
            "id": "attack-pattern--revoked",
            "name": "Revoked Technique",
            "description": "Should be skipped.",
            "external_references": [],
            "kill_chain_phases": [],
            "modified": "2023-01-01T00:00:00.000Z",
            "revoked": True,
        },
        {"type": "malware", "id": "malware--xyz", "name": "Not a technique"},
    ],
}

WHOIS_RECORD = {
    "domain": "example.com",
    "registrar": "TestRegistrar Inc",
    "iana_id": "999",
    "created": "2020-03-15",
    "expires": "2025-03-15",
    "registrant_email": "admin@example.com",
    "name_servers": ["ns1.example.com", "ns2.example.com"],
    "status": ["clientTransferProhibited"],
}

PDNS_RECORD = {
    "domain": "malicious.example",
    "first_seen": "2023-01-01",
    "last_seen": "2024-06-01",
    "resolutions": [
        {
            "ip": "1.2.3.4",
            "asn": "AS12345",
            "asn_name": "BadISP",
            "first_seen": "2023-01-01",
            "last_seen": "2023-12-31",
        }
    ],
    "subdomains": ["c2.malicious.example", "panel.malicious.example"],
}


@pytest.fixture
def mitre_bundle_file(tmp_path: Path) -> Path:
    bundle_path = tmp_path / "enterprise-attack.json"
    bundle_path.write_text(json.dumps(MITRE_STUB), encoding="utf-8")
    return bundle_path


# --- MITRE ---


def test_mitre_yields_only_non_revoked_attack_patterns(mitre_bundle_file: Path) -> None:
    docs = list(MitreAttackConnector(bundle_path=mitre_bundle_file).fetch_documents())
    assert len(docs) == 1
    assert docs[0].metadata["attack_id"] == "T1566.001"


def test_mitre_document_content_includes_id_and_tactic(mitre_bundle_file: Path) -> None:
    doc = list(MitreAttackConnector(bundle_path=mitre_bundle_file).fetch_documents())[0]
    assert "T1566.001" in doc.content
    assert "initial-access" in doc.content


def test_mitre_document_metadata(mitre_bundle_file: Path) -> None:
    doc = list(MitreAttackConnector(bundle_path=mitre_bundle_file).fetch_documents())[0]
    assert isinstance(doc, Document)
    assert doc.source == "mitre"
    assert doc.metadata["last_modified"] == "2024-01-01T00:00:00.000Z"
    assert "initial-access" in doc.metadata["tactics"]


def test_mitre_raises_on_missing_bundle(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(MitreAttackConnector(bundle_path=tmp_path / "missing.json").fetch_documents())


def test_mitre_retrieved_at_is_deterministic_sentinel(mitre_bundle_file: Path) -> None:
    # retrieved_at = our fetch time (sentinel by default), deterministic — not wall-clock.
    # The technique's STIX modified stays in metadata.last_modified (tested above).
    d1 = list(MitreAttackConnector(bundle_path=mitre_bundle_file).fetch_documents())[0]
    d2 = list(MitreAttackConnector(bundle_path=mitre_bundle_file).fetch_documents())[0]
    assert d1.retrieved_at == d2.retrieved_at


# --- WHOIS ---


def test_whois_produces_document() -> None:
    docs = list(WHOISConnector(records=[WHOIS_RECORD]).fetch_documents())
    assert len(docs) == 1
    assert docs[0].source == "whois"
    assert "example.com" in docs[0].content
    assert "TestRegistrar Inc" in docs[0].content


def test_whois_document_id_is_stable() -> None:
    id1 = list(WHOISConnector(records=[WHOIS_RECORD]).fetch_documents())[0].id
    id2 = list(WHOISConnector(records=[WHOIS_RECORD]).fetch_documents())[0].id
    assert id1 == id2


def test_whois_skips_record_missing_domain() -> None:
    docs = list(WHOISConnector(records=[{"registrar": "NoName"}]).fetch_documents())
    assert len(docs) == 0


# --- Passive DNS ---


def test_pdns_produces_document() -> None:
    docs = list(PassiveDNSConnector(records=[PDNS_RECORD]).fetch_documents())
    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "pdns"
    assert "1.2.3.4" in doc.content
    assert "AS12345" in doc.content


def test_pdns_subdomains_appear_in_content() -> None:
    doc = list(PassiveDNSConnector(records=[PDNS_RECORD]).fetch_documents())[0]
    assert "c2.malicious.example" in doc.content


def test_pdns_skips_record_missing_domain() -> None:
    docs = list(PassiveDNSConnector(records=[{"resolutions": []}]).fetch_documents())
    assert len(docs) == 0


def test_pdns_join_fields_are_not_capped() -> None:
    # 25 resolutions / 30 subdomains exceed the old [:20]/[:10] caps — join
    # fields must be preserved in full (ingestion §6/§7.3).
    record = {
        "domain": "big.example",
        "resolutions": [{"ip": f"10.0.0.{i}", "asn": f"AS{i}"} for i in range(25)],
        "subdomains": [f"s{i}.big.example" for i in range(30)],
    }
    doc = list(PassiveDNSConnector(records=[record]).fetch_documents())[0]
    assert len(doc.metadata["ip_addresses"]) == 25
    assert len(doc.metadata["asns"]) == 25
    assert len(doc.metadata["subdomains"]) == 30
