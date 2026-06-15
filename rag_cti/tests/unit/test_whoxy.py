from __future__ import annotations

import pytest

from rag_cti.connectors.whois_connector import WHOISConnector
from rag_cti.connectors.whoxy import (
    WhoxyClient,
    whoxy_history_to_whois_record,
    whoxy_to_whois_record,
)


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


def _whoxy_history_payload() -> dict:
    return {
        "status": 1,
        "domain_name": "evil.example",
        "total_records_found": 2,
        "whois_records": [
            {
                "num": 1,
                "query_time": "2022-06-10 08:00:00",
                "create_date": "2021-03-01",
                "update_date": "2022-06-01",
                "expiry_date": "2023-03-01",
                "domain_registrar": {"iana_id": 146, "registrar_name": "GoDaddy.com, LLC"},
                "registrant_contact": {"email_address": "old-owner@evil.example"},
                "name_servers": ["ns1.parked.example"],
                "domain_status": ["clientHold"],
            },
            {
                "num": 2,
                "query_time": "2024-05-20 14:30:00",
                "create_date": "2021-03-01",
                "update_date": "2024-01-15",
                "expiry_date": "2026-03-01",
                "domain_registrar": {"iana_id": 1468, "registrar_name": "NameCheap, Inc."},
                "registrant_contact": {"email_address": "abuse@evil.example"},
                "name_servers": ["ns1.evil.example", "ns2.evil.example"],
                "domain_status": ["clientTransferProhibited"],
            },
        ],
    }


def test_history_picks_latest_snapshot_by_query_time() -> None:
    record = whoxy_history_to_whois_record(_whoxy_history_payload())
    assert record["registrar"] == "NameCheap, Inc."
    assert record["updated"] == "2024-01-15"
    assert record["registrant_email"] == "abuse@evil.example"


def test_history_record_inherits_envelope_domain_name() -> None:
    record = whoxy_history_to_whois_record(_whoxy_history_payload())
    assert record["domain"] == "evil.example"


def test_history_failed_status_raises() -> None:
    with pytest.raises(ValueError, match="history lookup failed"):
        whoxy_history_to_whois_record({"status": 0, "status_reason": "Zero Account Balance"})


def test_history_empty_records_raises() -> None:
    with pytest.raises(ValueError, match="no whois_records"):
        whoxy_history_to_whois_record(
            {"status": 1, "domain_name": "evil.example", "whois_records": []}
        )


def test_history_record_feeds_whois_connector() -> None:
    record = whoxy_history_to_whois_record(_whoxy_history_payload())
    doc = WHOISConnector(records=[record]).to_document(record)
    assert doc.source == "whois"
    assert doc.metadata["domain"] == "evil.example"
    assert "NameCheap" in doc.content


def test_whois_raw_returns_verbatim_payload(monkeypatch) -> None:
    client = WhoxyClient(api_key="x")
    monkeypatch.setattr(client, "_get", lambda **kw: {"status": 1, "echo": kw})
    assert client.whois_raw("evil.example") == {"status": 1, "echo": {"whois": "evil.example"}}
    assert client.history_raw("evil.example") == {"status": 1, "echo": {"history": "evil.example"}}
