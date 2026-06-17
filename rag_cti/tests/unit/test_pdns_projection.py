from __future__ import annotations

import json
from pathlib import Path

from rag_cti.connectors.pdns_projection import load_pdns_raw_dir, project_pdns_raw


def test_project_pdns_raw_maps_securitytrails_payload() -> None:
    raw = {
        "fetched_at": "2026-06-15T23:33:16.707732+00:00",
        "source": "pdns",
        "source_id": "0-02.net",
        "payload": {
            "count": 3,
            "passive_dns": [
                {
                    "address": "23.111.191.180",
                    "asn": "AS29802 hivelocity  inc.",
                    "asset_type": "domain",
                    "first": "2021-03-09T19:05:05",
                    "flag_title": "United States",
                    "hostname": "0-02.net",
                    "last": "2025-12-09T21:50:55",
                    "record_type": "A",
                },
                {
                    "address": "ns12.1-19.net",
                    "asn": "AS29802 hivelocity  inc.",
                    "asset_type": "domain",
                    "first": "2019-09-27T10:56:47",
                    "flag_title": "United States",
                    "hostname": "0-02.net",
                    "last": "2025-12-09T21:50:55",
                    "record_type": "NS",
                },
                {
                    "address": "75.126.23.192",
                    "asn": "AS36351 softlayer technologies inc.",
                    "asset_type": "hostname",
                    "first": "2014-11-17T21:45:10",
                    "flag_title": "United States",
                    "hostname": "www.0-02.net",
                    "last": "2019-01-19T23:00:00",
                    "record_type": "A",
                },
            ],
        },
    }

    record = project_pdns_raw(raw)

    assert record["domain"] == "0-02.net"
    assert record["fetched_at"] == "2026-06-15T23:33:16.707732+00:00"
    assert record["first_seen"] == "2014-11-17T21:45:10"
    assert record["last_seen"] == "2025-12-09T21:50:55"
    assert record["subdomains"] == ["www.0-02.net"]
    assert record["resolutions"][0] == {
        "value": "23.111.191.180",
        "ip": "23.111.191.180",
        "record_type": "A",
        "asset_type": "domain",
        "hostname": "0-02.net",
        "asn": "AS29802",
        "asn_name": "hivelocity inc.",
        "country": "United States",
        "first_seen": "2021-03-09T19:05:05",
        "last_seen": "2025-12-09T21:50:55",
    }
    assert record["resolutions"][1]["record_type"] == "NS"
    assert record["resolutions"][1]["ip"] == ""
    # NS answer (the nameserver) is preserved in `value`, not lost.
    assert record["resolutions"][1]["value"] == "ns12.1-19.net"


def test_project_pdns_raw_keeps_empty_payload_as_domain_record() -> None:
    record = project_pdns_raw(
        {
            "fetched_at": "2026-06-15T23:33:16.707732+00:00",
            "source_id": "*.av.lometr.pl",
            "payload": {"count": 0, "passive_dns": []},
        }
    )

    assert record["domain"] == "*.av.lometr.pl"
    assert record["resolutions"] == []
    assert record["subdomains"] == []


def test_load_pdns_raw_dir_uses_latest_snapshot_per_domain(tmp_path: Path) -> None:
    domain_dir = tmp_path / "example.com"
    domain_dir.mkdir()
    older = {
        "fetched_at": "2026-06-15T00:00:00+00:00",
        "source_id": "example.com",
        "payload": {"passive_dns": []},
    }
    newer = {
        "fetched_at": "2026-06-16T00:00:00+00:00",
        "source_id": "example.com",
        "payload": {
            "passive_dns": [
                {
                    "address": "1.2.3.4",
                    "hostname": "example.com",
                    "record_type": "A",
                }
            ]
        },
    }
    (domain_dir / "2026-06-15.json").write_text(json.dumps(older), encoding="utf-8")
    (domain_dir / "2026-06-16.json").write_text(json.dumps(newer), encoding="utf-8")

    records = load_pdns_raw_dir(tmp_path)

    assert len(records) == 1
    assert records[0]["domain"] == "example.com"
    assert records[0]["resolutions"][0]["ip"] == "1.2.3.4"
