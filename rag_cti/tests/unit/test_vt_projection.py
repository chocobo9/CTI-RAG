from __future__ import annotations

from typing import Any

from rag_cti.connectors.virustotal import (
    VirusTotalConnector,
    render_vt_content,
    vt_metadata,
)
from rag_cti.connectors.vt_projection import project_vt_infra
from rag_cti.ingest.normalize import normalize_infrastructure
from rag_cti.preprocess.chunk_projection import project_chunk

# A rich VT v3 domain response — the fields the old connector dropped.
_PAYLOAD: dict[str, Any] = {
    "data": {
        "id": "evil.example",
        "attributes": {
            "last_analysis_stats": {"malicious": 5, "harmless": 60},
            "crowdsourced_yara_results": [{"rule_name": f"R{i}"} for i in range(1, 7)],
            "tags": ["c2"],
            "categories": {"v1": "malware", "v2": "malware", "v3": "phishing"},
            "reputation": -40,
            "registrar": "NameSilo, LLC",
            "creation_date": 1176214113,
            "expiration_date": 1779055337,
            "last_modification_date": 1717200000,
            "whois": "Registrar: NameSilo, LLC\nRegistrant Email: REDACTED FOR PRIVACY",
            "last_dns_records": [
                {"type": "A", "value": "1.2.3.4", "ttl": 3600},
                {"type": "NS", "value": "ns1.example.net"},
                {"type": "NS", "value": "ns2.example.net"},
                {"type": "SOA", "value": "ignored"},
            ],
            "last_https_certificate": {"subject": {"CN": "evil.example", "O": "Evil Corp"}},
            "rdap": {"object_class_name": "domain"},
        },
    }
}

_ATTRS = _PAYLOAD["data"]["attributes"]


def test_vt_metadata_preserves_previously_dropped_fields() -> None:
    meta = vt_metadata("evil.example", _ATTRS)
    assert meta["whois"].startswith("Registrar: NameSilo")
    assert meta["registrar"] == "NameSilo, LLC"
    assert meta["name_servers"] == ["ns1.example.net", "ns2.example.net"]
    assert meta["last_dns_records"] == _ATTRS["last_dns_records"]  # full, verbatim
    assert meta["last_https_certificate"]["subject"]["O"] == "Evil Corp"
    assert meta["categories"] == _ATTRS["categories"]
    assert meta["reputation"] == -40
    assert meta["rdap"] == {"object_class_name": "domain"}
    assert meta["creation_date"].startswith("2007-")  # epoch -> iso


def test_vt_content_renders_full_yara_no_cap_and_cert_org() -> None:
    content = render_vt_content("evil.example", _ATTRS)
    # the old connector capped YARA at 5 — R6 proves the cap is gone
    assert "R6" in content
    assert "TLS certificate organization: Evil Corp." in content
    assert "Registrar: NameSilo, LLC." in content
    assert "ns1.example.net" in content
    # categories deduped + sorted
    assert "Categories: malware, phishing." in content


def test_connector_offline_records_mode_replays_payloads() -> None:
    connector = VirusTotalConnector(records=[_PAYLOAD])
    docs = list(connector.fetch_documents())
    assert len(docs) == 1
    assert docs[0].source == "virustotal"
    assert docs[0].metadata["name_servers"] == ["ns1.example.net", "ns2.example.net"]


def test_project_vt_infra_extracts_a_and_ns_resolutions() -> None:
    record = project_vt_infra(_PAYLOAD)
    assert record["domain"] == "evil.example"
    by_type = {(r["record_type"], r["value"]) for r in record["resolutions"]}
    assert ("A", "1.2.3.4") in by_type
    assert ("NS", "ns1.example.net") in by_type
    assert ("NS", "ns2.example.net") in by_type
    # SOA is not an edge-bearing record kind
    assert not any(r["record_type"] == "SOA" for r in record["resolutions"])


def test_vt_end_to_end_projects_resolves_to_and_uses_nameserver_edges() -> None:
    structured = project_vt_infra(_PAYLOAD)
    record = normalize_infrastructure(
        structured, "vt", structured["domain"], indicator_type="domain"
    )
    proj = project_chunk(record, ontology_nodes=[])
    preds = {r["predicate"] for r in proj["relations"]}
    assert "resolves-to" in preds
    assert "uses-nameserver" in preds
    endpoints = {r["subject_id"] for r in proj["relations"]} | {
        r["object_id"] for r in proj["relations"]
    }
    assert endpoints <= set(proj["entity_ids"])
