from __future__ import annotations

import json
from pathlib import Path

from rag_cti.connectors.pdns_projection import load_pdns_raw_dir, project_pdns_raw


def test_project_pdns_raw_preserves_resolution_and_infrastructure_fields() -> None:
    projected = project_pdns_raw(
        {
            "source_id": "example.com",
            "fetched_at": "2026-08-14T00:00:00Z",
            "payload": {
                "passive_dns": [
                    {
                        "hostname": "www.example.com",
                        "record_type": "A",
                        "address": "192.0.2.1",
                        "first": "2024-01-01",
                        "last": "2024-02-01",
                        "asn": "AS64500 Example Network",
                        "flag_title": "Example",
                    },
                    {
                        "hostname": "example.com",
                        "record_type": "NS",
                        "address": "ns1.example.net",
                    },
                ]
            },
        }
    )

    assert projected["domain"] == "example.com"
    assert projected["subdomains"] == ["www.example.com"]
    assert projected["resolutions"] == [
        {
            "value": "192.0.2.1",
            "ip": "192.0.2.1",
            "record_type": "A",
            "asset_type": "",
            "hostname": "www.example.com",
            "asn": "AS64500",
            "asn_name": "Example Network",
            "country": "Example",
            "first_seen": "2024-01-01",
            "last_seen": "2024-02-01",
        },
        {
            "value": "ns1.example.net",
            "ip": "",
            "record_type": "NS",
            "asset_type": "",
            "hostname": "example.com",
            "asn": "",
            "asn_name": "",
            "country": "",
            "first_seen": "",
            "last_seen": "",
        },
    ]


def test_load_pdns_raw_dir_uses_latest_snapshot_per_domain(tmp_path: Path) -> None:
    domain_dir = tmp_path / "example.com"
    domain_dir.mkdir()
    for name, address in (("20240813.json", "192.0.2.1"), ("20240814.json", "192.0.2.2")):
        (domain_dir / name).write_text(
            json.dumps(
                {
                    "source_id": "example.com",
                    "payload": {
                        "passive_dns": [{"address": address, "record_type": "A"}]
                    },
                }
            ),
            encoding="utf-8",
        )

    records = load_pdns_raw_dir(tmp_path)

    assert [row["resolutions"][0]["ip"] for row in records] == ["192.0.2.2"]


def test_project_pdns_raw_normalizes_ipv6_resolution_addresses() -> None:
    projected = project_pdns_raw(
        {
            "source_id": "example.com",
            "payload": {
                "passive_dns": [
                    {
                        "record_type": "AAAA",
                        "address": "2001:0DB8:0:0::1",
                    }
                ]
            },
        }
    )

    assert projected["resolutions"][0]["ip"] == "2001:db8::1"
