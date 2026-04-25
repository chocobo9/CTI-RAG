"""Integration tests for OTX and VirusTotal connectors.

All HTTP calls are mocked — exercises the full
fetch() -> to_document() -> fetch_documents() pipeline without network access.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from rag_cti.connectors.otx import OTXConnector
from rag_cti.connectors.virustotal import VirusTotalConnector
from rag_cti.types import Document

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

_PULSE_A: dict[str, Any] = {
    "id": "aaa111bbb222ccc3",
    "name": "Cobalt Strike Beacon Activity",
    "description": "C2 traffic patterns observed from Cobalt Strike beacons.",
    "tags": ["apt", "cobalt-strike"],
    "attack_ids": [{"id": "T1055", "name": "Process Injection"}],
    "indicators": [
        {"indicator": "1.2.3.4", "type": "IPv4"},
        {"indicator": "evil.com", "type": "domain"},
    ],
    "modified": "2024-06-01T12:00:00.000Z",
    "pulse_source": "user",
}

_PULSE_B: dict[str, Any] = {
    "id": "ccc333ddd444eee5",
    "name": "Ransomware C2 Infrastructure",
    "description": "",
    "tags": ["ransomware"],
    "attack_ids": [],
    "indicators": [],
    "modified": "2024-07-01T00:00:00.000Z",
    "pulse_source": "research",
}

_VT_DOMAIN_RESPONSE: dict[str, Any] = {
    "data": {
        "id": "malicious.example",
        "attributes": {
            "last_analysis_stats": {
                "malicious": 5,
                "suspicious": 2,
                "harmless": 65,
                "undetected": 3,
            },
            "crowdsourced_yara_results": [
                {"rule_name": "CobaltStrike_Beacon"},
                {"rule_name": "Sliver_C2"},
            ],
            "tags": ["malware", "c2"],
            "last_modification_date": 1717200000,
        },
    }
}


# ---------------------------------------------------------------------------
# OTX: fetch()
# ---------------------------------------------------------------------------

def test_otx_fetch_yields_pulses_from_single_page() -> None:
    connector = OTXConnector(api_key="test-key")
    page = {"results": [_PULSE_A, _PULSE_B], "next": None}

    with patch.object(connector, "_get", return_value=page):
        pulses = list(connector.fetch())

    assert len(pulses) == 2
    assert pulses[0]["id"] == "aaa111bbb222ccc3"


def test_otx_fetch_follows_pagination() -> None:
    connector = OTXConnector(api_key="test-key")
    page1 = {
        "results": [_PULSE_A],
        "next": "https://otx.alienvault.com/api/v1/pulses/subscribed?page=2",
    }
    page2 = {"results": [_PULSE_B], "next": None}

    with patch.object(connector, "_get", side_effect=[page1, page2]) as mock_get:
        pulses = list(connector.fetch())

    assert len(pulses) == 2
    assert mock_get.call_count == 2


def test_otx_fetch_passes_modified_since_param() -> None:
    connector = OTXConnector(api_key="test-key", modified_since="2024-01-01T00:00:00Z")
    page = {"results": [], "next": None}

    with patch.object(connector, "_get", return_value=page) as mock_get:
        list(connector.fetch())

    _, kwargs = mock_get.call_args
    assert kwargs.get("modified_since") == "2024-01-01T00:00:00Z"


def test_otx_fetch_empty_results_yields_nothing() -> None:
    connector = OTXConnector(api_key="test-key")
    with patch.object(connector, "_get", return_value={"results": [], "next": None}):
        assert list(connector.fetch()) == []


# ---------------------------------------------------------------------------
# OTX: to_document()
# ---------------------------------------------------------------------------

def test_otx_to_document_content_includes_name_and_description() -> None:
    connector = OTXConnector(api_key="test-key")
    doc = connector.to_document(_PULSE_A)

    assert "Cobalt Strike Beacon Activity" in doc.content
    assert "C2 traffic patterns" in doc.content


def test_otx_to_document_content_name_only_when_no_description() -> None:
    connector = OTXConnector(api_key="test-key")
    doc = connector.to_document(_PULSE_B)

    assert doc.content == "Ransomware C2 Infrastructure"


def test_otx_to_document_id_is_deterministic() -> None:
    connector = OTXConnector(api_key="test-key")
    assert connector.to_document(_PULSE_A).id == connector.to_document(_PULSE_A).id


def test_otx_to_document_id_differs_per_pulse() -> None:
    connector = OTXConnector(api_key="test-key")
    assert connector.to_document(_PULSE_A).id != connector.to_document(_PULSE_B).id


def test_otx_to_document_id_is_16_char_hex() -> None:
    connector = OTXConnector(api_key="test-key")
    doc_id = connector.to_document(_PULSE_A).id

    assert len(doc_id) == 16
    int(doc_id, 16)  # raises ValueError if not valid hex


def test_otx_to_document_source_is_otx() -> None:
    connector = OTXConnector(api_key="test-key")
    assert connector.to_document(_PULSE_A).source == "otx"


def test_otx_to_document_metadata_has_expected_fields() -> None:
    connector = OTXConnector(api_key="test-key")
    meta = connector.to_document(_PULSE_A).metadata

    assert meta["pulse_id"] == "aaa111bbb222ccc3"
    assert "cobalt-strike" in meta["tags"]
    assert meta["last_modified"] == "2024-06-01T12:00:00.000Z"
    assert meta["pulse_source"] == "user"
    assert isinstance(meta["indicators"], list)


def test_otx_to_document_indicators_capped_at_50() -> None:
    pulse = {**_PULSE_A, "indicators": [{"indicator": f"{i}.0.0.1"} for i in range(60)]}
    connector = OTXConnector(api_key="test-key")
    doc = connector.to_document(pulse)

    assert len(doc.metadata["indicators"]) == 50


def test_otx_to_document_skips_indicators_without_indicator_key() -> None:
    pulse = {**_PULSE_A, "indicators": [{"type": "IPv4"}, {"indicator": "1.1.1.1"}]}
    connector = OTXConnector(api_key="test-key")
    doc = connector.to_document(pulse)

    assert doc.metadata["indicators"] == ["1.1.1.1"]


# ---------------------------------------------------------------------------
# OTX: fetch_documents() pipeline
# ---------------------------------------------------------------------------

def test_otx_fetch_documents_returns_document_objects() -> None:
    connector = OTXConnector(api_key="test-key")
    page = {"results": [_PULSE_A, _PULSE_B], "next": None}

    with patch.object(connector, "_get", return_value=page):
        docs = list(connector.fetch_documents())

    assert len(docs) == 2
    assert all(isinstance(d, Document) for d in docs)


# ---------------------------------------------------------------------------
# VT: fetch()
# ---------------------------------------------------------------------------

def test_vt_fetch_yields_one_result_per_domain() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    with patch.object(connector, "_get", return_value=_VT_DOMAIN_RESPONSE):
        results = list(connector.fetch(domains=["malicious.example", "other.example"]))

    assert len(results) == 2


def test_vt_fetch_skips_failed_domain_and_continues() -> None:
    connector = VirusTotalConnector(api_key="test-key")

    with patch.object(
        connector,
        "_get",
        side_effect=[Exception("connection error"), _VT_DOMAIN_RESPONSE],
    ):
        results = list(connector.fetch(domains=["bad.example", "good.example"]))

    assert len(results) == 1


def test_vt_fetch_empty_domains_yields_nothing() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    assert list(connector.fetch(domains=[])) == []


def test_vt_fetch_no_domains_arg_yields_nothing() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    assert list(connector.fetch()) == []


# ---------------------------------------------------------------------------
# VT: to_document()
# ---------------------------------------------------------------------------

def test_vt_to_document_id_is_deterministic() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    assert connector.to_document(_VT_DOMAIN_RESPONSE).id == connector.to_document(_VT_DOMAIN_RESPONSE).id


def test_vt_to_document_raises_when_domain_missing() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    with pytest.raises(ValueError, match="missing data.id"):
        connector.to_document({"data": {"id": "", "attributes": {}}})


def test_vt_to_document_source_is_virustotal() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    assert connector.to_document(_VT_DOMAIN_RESPONSE).source == "virustotal"


def test_vt_to_document_content_starts_with_domain_line() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    content = connector.to_document(_VT_DOMAIN_RESPONSE).content

    assert content.startswith("VirusTotal analysis of domain malicious.example")


def test_vt_to_document_content_includes_detection_stats() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    content = connector.to_document(_VT_DOMAIN_RESPONSE).content

    assert "5 malicious" in content
    assert "2 suspicious" in content


def test_vt_to_document_content_includes_yara_rules() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    content = connector.to_document(_VT_DOMAIN_RESPONSE).content

    assert "CobaltStrike_Beacon" in content
    assert "Sliver_C2" in content


def test_vt_to_document_content_no_yara_section_when_empty() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    raw: dict[str, Any] = {
        "data": {
            "id": "clean.example",
            "attributes": {
                "last_analysis_stats": {"malicious": 0, "harmless": 70},
                "crowdsourced_yara_results": [],
                "tags": [],
            },
        }
    }
    assert "YARA" not in connector.to_document(raw).content


def test_vt_to_document_metadata_has_domain_and_stats() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    meta = connector.to_document(_VT_DOMAIN_RESPONSE).metadata

    assert meta["domain"] == "malicious.example"
    assert meta["analysis_stats"]["malicious"] == 5
    assert "malware" in meta["tags"]


def test_vt_to_document_last_modified_is_isoformat() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    meta = connector.to_document(_VT_DOMAIN_RESPONSE).metadata

    # unix timestamp 1717200000 → 2024-06-01
    assert meta["last_modified"].startswith("2024-06-01")


def test_vt_to_document_missing_last_modification_date_gives_empty_string() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    raw: dict[str, Any] = {
        "data": {
            "id": "no-ts.example",
            "attributes": {"tags": [], "last_analysis_stats": {}},
        }
    }
    assert connector.to_document(raw).metadata["last_modified"] == ""


# ---------------------------------------------------------------------------
# VT: fetch_documents() pipeline
# ---------------------------------------------------------------------------

def test_vt_fetch_documents_returns_document_objects() -> None:
    connector = VirusTotalConnector(api_key="test-key")
    with patch.object(connector, "_get", return_value=_VT_DOMAIN_RESPONSE):
        docs = list(connector.fetch_documents(domains=["malicious.example"]))

    assert len(docs) == 1
    assert isinstance(docs[0], Document)
    assert docs[0].source == "virustotal"
