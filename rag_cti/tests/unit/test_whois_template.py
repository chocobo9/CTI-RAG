from __future__ import annotations

from rag_cti.preprocess.whois_template import render_whois


def _full_record() -> dict:
    return {
        "domain": "evil.example",
        "registrar": "NameCheap, Inc.",
        "iana_id": "1468",
        "created": "2021-03-01",
        "expires": "2026-03-01",
        "updated": "2024-01-15",
        "registrant_email": "abuse@evil.example",
        "name_servers": ["ns1.evil.example", "ns2.evil.example"],
        "status": ["clientTransferProhibited"],
    }


def test_renders_all_fields_as_prose() -> None:
    text = render_whois(_full_record())
    assert "Domain evil.example is registered with NameCheap, Inc. (IANA ID: 1468)." in text
    assert "created on 2021-03-01 and expires on 2026-03-01" in text
    assert "Last updated: 2024-01-15." in text
    assert "Registrant contact email: abuse@evil.example." in text
    assert "Name servers: ns1.evil.example, ns2.evil.example." in text
    assert "Registration status: clientTransferProhibited." in text


def test_minimal_record_renders_without_optional_sections() -> None:
    text = render_whois({"domain": "bare.example", "registrar": "R"})
    assert text == "Domain bare.example is registered with R."


def test_created_without_expiry_ends_cleanly() -> None:
    text = render_whois({"domain": "d", "registrar": "R", "created": "2020-01-01"})
    assert "It was created on 2020-01-01." in text
    assert "expires" not in text


def test_registrar_without_iana_id_has_no_parenthetical() -> None:
    text = render_whois({"domain": "d", "registrar": "R"})
    assert "(IANA ID" not in text


def test_scalar_name_servers_and_status_are_tolerated() -> None:
    text = render_whois(
        {
            "domain": "d",
            "registrar": "R",
            "name_servers": "ns1.d",
            "status": "ok",
        }
    )
    assert "Name servers: ns1.d." in text
    assert "Registration status: ok." in text


def test_empty_record_uses_unknown_defaults() -> None:
    text = render_whois({})
    assert text == "Domain unknown domain is registered with unknown registrar."
