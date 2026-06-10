from __future__ import annotations

import pytest

from rag_cti.connectors.whois_connector import WHOISConnector
from rag_cti.connectors.whoxy import WhoxyClient, whoxy_to_whois_record


def _whoxy_payload() -> dict:
    return {
        "status": 1,
        "domain_name": "Evil.Example",
        "create_date": "2021-03-01",
        "update_date": "2024-01-15",
        "expiry_date": "2026-03-01",
        "domain_registrar": {"iana_id": 1468, "registrar_name": "NameCheap, Inc."},
        "registrant_contact": {"full_name": "Redacted", "email_address": "abuse@evil.example"},
        "name_servers": ["ns1.evil.example", "ns2.evil.example"],
        "domain_status": ["clientTransferProhibited"],
    }


def test_maps_whoxy_fields_to_whois_record() -> None:
    record = whoxy_to_whois_record(_whoxy_payload())
    assert record["domain"] == "evil.example"
    assert record["registrar"] == "NameCheap, Inc."
    assert record["iana_id"] == "1468"
    assert record["created"] == "2021-03-01"
    assert record["updated"] == "2024-01-15"
    assert record["expires"] == "2026-03-01"
    assert record["registrant_email"] == "abuse@evil.example"
    assert record["name_servers"] == ["ns1.evil.example", "ns2.evil.example"]
    assert record["status"] == ["clientTransferProhibited"]


def test_mapped_record_feeds_whois_connector() -> None:
    record = whoxy_to_whois_record(_whoxy_payload())
    doc = WHOISConnector(records=[record]).to_document(record)
    assert doc.source == "whois"
    assert doc.metadata["domain"] == "evil.example"
    assert "NameCheap" in doc.content


def test_failed_status_raises() -> None:
    with pytest.raises(ValueError, match="Whoxy lookup failed"):
        whoxy_to_whois_record({"status": 0, "status_reason": "invalid domain"})


def test_missing_domain_name_raises() -> None:
    with pytest.raises(ValueError, match="domain_name"):
        whoxy_to_whois_record({"status": 1})


def test_missing_optional_fields_default_empty() -> None:
    record = whoxy_to_whois_record({"status": 1, "domain_name": "bare.example"})
    assert record["domain"] == "bare.example"
    assert record["registrar"] == ""
    assert record["name_servers"] == []
    assert record["status"] == []


def test_client_requires_api_key() -> None:
    with pytest.raises(ValueError, match="API key"):
        WhoxyClient(api_key="")
