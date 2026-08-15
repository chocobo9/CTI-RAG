from __future__ import annotations

import json
from pathlib import Path

from rag_cti.trail_dataset.builder import (
    SourceRoots,
    _deduplicate_rejected,
    _extract_orkl_indicators,
    build_dataset,
)
from rag_cti.trail_part1 import (
    _extract_misp_iocs,
    _extract_orkl_iocs,
    extract_text_iocs,
    normalize_domain,
    normalize_misp_url,
    normalize_url,
)


def test_orkl_body_extracts_standalone_domains_and_numbered_ioc_urls() -> None:
    observations = _extract_orkl_indicators(
        {
            "body": (
                "1. evil-c2-server.com\n"
                "2. malicious-payload-host.net\n"
                "3. hxxps://evil-c2-server.com/gate.php\n"
                "4. 45.33.12.9"
            )
        }
    )

    assert {(row["type"], row["value"]) for row in observations} == {
        ("domain", "evil-c2-server.com"),
        ("domain", "malicious-payload-host.net"),
        ("url", "https://evil-c2-server.com/gate.php"),
        ("ip", "45.33.12.9"),
    }


def test_orkl_reference_section_stops_before_ioc_appendix() -> None:
    observations = _extract_orkl_indicators(
        {
            "body": (
                "References\n"
                "1. https://citation.example/source\n\n"
                "IOC Appendix\n"
                "1. evil-c2-server.com\n"
                "2. hxxps://evil-c2-server.com/gate.php\n"
                "3. 45.33.12.9"
            )
        }
    )

    assert {(row["type"], row["value"]) for row in observations} == {
        ("domain", "evil-c2-server.com"),
        ("url", "https://evil-c2-server.com/gate.php"),
        ("ip", "45.33.12.9"),
    }


def test_orkl_domain_observations_reach_event_graph_projection() -> None:
    projected, _ = _extract_orkl_iocs(
        {"body": "C2 domain: evil-c2-server.com"},
        "report-1",
        "data/raw/orkl/report-1.json",
    )

    assert {(row["ioc_type"], row["ioc_value"]) for row in projected} == {
        ("Domain", "evil-c2-server.com"),
    }


def test_orkl_defanged_url_and_ipv6_are_projected_canonically() -> None:
    observations = _extract_orkl_indicators(
        {"body": "C2 hxxps://evil[.]com/gate.php and 2001:db8::1"}
    )

    assert {(row["type"], row["value"]) for row in observations} == {
        ("url", "https://evil.com/gate.php"),
        ("ip", "2001:db8::1"),
    }


def test_generic_text_does_not_truncate_defanged_url_and_extracts_ipv6() -> None:
    projected, _ = extract_text_iocs(
        "C2 hxxps://evil[.]com/path and 2001:db8::1",
        "fixture",
        "record-1",
        "data/raw/fixture/record-1.json",
    )

    assert {(row["ioc_type"], row["ioc_value"]) for row in projected} == {
        ("URL", "https://evil.com/path"),
        ("IP", "2001:db8::1"),
    }


def test_url_canonicalization_preserves_ipv6_brackets_and_drops_fragment() -> None:
    assert normalize_url("HTTPS://[2001:0DB8:0:0::1]:443/x#fragment") == (
        "https://[2001:db8::1]:443/x"
    )


def test_orkl_stores_canonical_url_value() -> None:
    observations = _extract_orkl_indicators({"body": "HTTPS://Example.COM/path#fragment"})

    assert [(row["type"], row["value"]) for row in observations] == [
        ("url", "https://example.com/path")
    ]


def test_defanged_reference_is_excluded_after_normalization() -> None:
    observations = _extract_orkl_indicators(
        {
            "references": ["hxxps://citation[.]example/source"],
            "body": (
                "Citation mention: hxxps://citation[.]example/source\n"
                "C2: hxxps://evil[.]example/gate.php"
            ),
        }
    )

    assert [(row["type"], row["value"]) for row in observations] == [
        ("url", "https://evil.example/gate.php")
    ]


def test_reference_section_stops_at_network_indicators_heading() -> None:
    observations = _extract_orkl_indicators(
        {
            "body": (
                "References\n"
                "1. https://citation.example/source\n\n"
                "Network Indicators\n"
                "1. evil-c2-server.com\n"
                "2. hxxps://evil-c2-server.com/gate.php"
            )
        }
    )

    assert {(row["type"], row["value"]) for row in observations} == {
        ("domain", "evil-c2-server.com"),
        ("url", "https://evil-c2-server.com/gate.php"),
    }


def test_domain_boundaries_accept_valid_tlds_and_reject_malformed_values() -> None:
    projected, _ = extract_text_iocs(
        "foo.museum foo.network foo.onion a..com -bad.com",
        "fixture",
        "record-2",
        "data/raw/fixture/record-2.json",
    )

    assert {row["ioc_value"] for row in projected} == {
        "foo.museum",
        "foo.network",
        "foo.onion",
    }
    assert normalize_domain("a..com") is None
    assert normalize_domain("-bad.com") is None
    assert normalize_domain("numeric.123") is None


def test_misp_scheme_less_ipv6_url_is_bracketed_canonically() -> None:
    assert normalize_misp_url("2001:db8::1/path") == "http://[2001:db8::1]/path"


def test_misp_deleted_attributes_are_ignored_and_ports_are_preserved() -> None:
    projected, _ = _extract_misp_iocs(
        {
            "Attribute": [
                {"type": "ip-src|port", "value": "192.0.2.1|443"},
                {"type": "domain", "value": "deleted.example", "deleted": True},
            ],
            "Object": [
                {
                    "deleted": True,
                    "Attribute": [{"type": "domain", "value": "object-deleted.example"}],
                }
            ],
        },
        "misp-1",
        "data/raw/misp/misp-1.json",
    )

    assert [(row["ioc_type"], row["ioc_value"], row["network_port"]) for row in projected] == [
        ("IP", "192.0.2.1", 443)
    ]


def test_builder_filters_deleted_misp_and_accepts_scheme_less_url(tmp_path: Path) -> None:
    source_root = tmp_path / "misp"
    source_root.mkdir()
    (source_root / "event.json").write_text(
        json.dumps(
            {
                "Event": {
                    "uuid": "misp-1",
                    "Attribute": [
                        {"type": "url", "value": "evil.example/path"},
                        {"type": "domain", "value": "deleted.example", "deleted": True},
                    ],
                    "Object": [
                        {
                            "deleted": True,
                            "Attribute": [{"type": "domain", "value": "object-deleted.example"}],
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    build_dataset(SourceRoots(circl_misp=source_root), output_dir)
    nodes = [json.loads(line) for line in (output_dir / "nodes.jsonl").read_text().splitlines()]

    assert {row["value"] for row in nodes} == {
        "event:circl_misp:misp-1",
        "http://evil.example/path",
        "evil.example",
    }


def test_builder_preserves_misp_ip_port_in_edge_evidence(tmp_path: Path) -> None:
    source_root = tmp_path / "misp"
    source_root.mkdir()
    (source_root / "event.json").write_text(
        json.dumps(
            {
                "Event": {
                    "uuid": "misp-port-1",
                    "Attribute": [{"type": "ip-src|port", "value": "192.0.2.1|443"}],
                }
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    build_dataset(SourceRoots(circl_misp=source_root), output_dir)
    edges = [json.loads(line) for line in (output_dir / "edges.jsonl").read_text().splitlines()]
    ip_edges = [row for row in edges if row["relation"] == "event_contains_ip"]

    assert ip_edges[0]["evidence"][0]["network_port"] == 443


def test_builder_joins_projected_pdns_facts(tmp_path: Path) -> None:
    source_root = tmp_path / "misp"
    source_root.mkdir()
    (source_root / "event.json").write_text(
        json.dumps(
            {
                "Event": {
                    "uuid": "misp-pdns-1",
                    "Attribute": [{"type": "domain", "value": "example.com"}],
                }
            }
        ),
        encoding="utf-8",
    )
    pdns_root = tmp_path / "pdns" / "example.com"
    pdns_root.mkdir(parents=True)
    (pdns_root / "20260814.json").write_text(
        json.dumps(
            {
                "source_id": "example.com",
                "payload": {
                    "passive_dns": [
                        {
                            "hostname": "example.com",
                            "record_type": "A",
                            "address": "192.0.2.7",
                            "asn": "AS64500 Example Network",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    build_dataset(SourceRoots(circl_misp=source_root, pdns=tmp_path / "pdns"), output_dir)
    edges = [json.loads(line) for line in (output_dir / "edges.jsonl").read_text().splitlines()]

    assert {row["relation"] for row in edges} >= {"domain_resolves_to_ip", "ip_in_asn"}


def test_rejected_records_are_deduplicated_and_duplicates_are_reported() -> None:
    row = {
        "source": "otx",
        "raw_ref": "data/raw/otx/event-1.json",
        "reason": "unsupported_ioc_type",
    }

    unique, duplicate_count = _deduplicate_rejected([row, dict(row)])

    assert unique == [row]
    assert duplicate_count == 1


def test_builder_reports_rejection_taxonomy_separately(tmp_path: Path) -> None:
    source_root = tmp_path / "misp"
    source_root.mkdir()
    (source_root / "event.json").write_text(
        json.dumps(
            {
                "Event": {
                    "uuid": "misp-rejection-1",
                    "Attribute": [
                        {"type": "domain", "value": "valid.example"},
                        {"type": "domain", "value": "not a domain"},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    build_dataset(SourceRoots(circl_misp=source_root), output_dir)
    coverage = json.loads((output_dir / "coverage_audit.json").read_text())

    assert coverage["rejected_record_count"] == 1
    assert coverage["rejected_event_count"] == 1
    assert coverage["unsupported_ioc_type_count"] == 0
    assert coverage["invalid_ioc_value_count"] == 1
    assert coverage["dropped_event_count"] == 0
    assert coverage["all_evidence_event_count"] == 1
    assert coverage["network_ioc_event_count"] == 1
    assert coverage["zero_network_ioc_event_count"] == 0
    assert coverage["non_network_only_event_count"] == 0
    assert coverage["isolated_event_count"] == 0


def test_event_rows_reference_source_claim_ids(tmp_path: Path) -> None:
    source_root = tmp_path / "otx"
    source_root.mkdir()
    (source_root / "pulse.json").write_text(
        json.dumps(
            {
                "id": "pulse-claim-1",
                "adversary": "Candidate Actor",
                "indicators": [{"type": "domain", "indicator": "example.com"}],
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    build_dataset(SourceRoots(otx=source_root), output_dir)
    event = json.loads((output_dir / "events.jsonl").read_text().splitlines()[0])
    claim = json.loads((output_dir / "source_claims.jsonl").read_text().splitlines()[0])
    coverage = json.loads((output_dir / "coverage_audit.json").read_text())
    validation = json.loads((output_dir / "validation_audit.json").read_text())

    assert event["source_claim_ids"] == [claim["claim_id"]]
    assert claim["event_id"] == event["event_id"]
    assert claim["claim_status"] == "candidate"
    assert coverage["unreferenced_source_claim_count"] == 0
    assert validation["claim_provenance"]["status"] == "passed"
