from __future__ import annotations

import json
from pathlib import Path

from rag_cti.trail_dataset.builder import (
    SourceRoots,
    _deduplicate_rejected,
    _event_evidence_metrics,
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


def test_builder_projects_orkl_body_iocs_into_event_graph(tmp_path: Path) -> None:
    source_root = tmp_path / "orkl"
    intermediate = source_root / "intermediate"
    intermediate.mkdir(parents=True)
    (intermediate / "intermediate_records.jsonl").write_text(
        json.dumps(
            {
                "record_id": "report-graph-1",
                "source": {
                    "report_identifier": "report-graph-1",
                    "source_record_id": "report-graph-1",
                },
                "raw_ref": {"raw_path": "data/raw/orkl/report-graph-1.json"},
                "timestamps": {"published_at": "2026-01-01T00:00:00Z"},
                "body": "C2 evil-c2-server.com and 2001:db8::1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    build_dataset(SourceRoots(orkl_intermediate=source_root), output_dir)
    nodes = [json.loads(line) for line in (output_dir / "nodes.jsonl").read_text().splitlines()]

    assert {row["value"] for row in nodes} >= {
        "event:orkl:report-graph-1",
        "evil-c2-server.com",
        "2001:db8::1",
    }


def test_builder_applies_event_allowlist_to_otx(tmp_path: Path) -> None:
    source_root = tmp_path / "otx"
    source_root.mkdir(parents=True)
    for event_id in ("keep-me", "exclude-me"):
        (source_root / f"{event_id}.json").write_text(
            json.dumps(
                {
                    "id": event_id,
                    "indicators": [
                        {"type": "domain", "indicator": f"{event_id}.example"}
                    ],
                }
            ),
            encoding="utf-8",
        )

    output_dir = tmp_path / "output"
    build_dataset(
        SourceRoots(otx=source_root),
        output_dir,
        event_allowlist={"otx": {"keep-me"}},
    )

    events = [
        json.loads(line)
        for line in (output_dir / "events.jsonl").read_text().splitlines()
    ]
    assert [row["event_id"] for row in events] == ["event:otx:keep-me"]


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
        "C2 hxxps://evil[.]com/path and hxxps[:]//second[.]example/gate and 2001:db8::1",
        "fixture",
        "record-1",
        "data/raw/fixture/record-1.json",
    )

    assert {(row["ioc_type"], row["ioc_value"]) for row in projected} == {
        ("URL", "https://evil.com/path"),
        ("URL", "https://second.example/gate"),
        ("IP", "2001:db8::1"),
    }


def test_url_canonicalization_preserves_ipv6_brackets_and_drops_fragment() -> None:
    assert normalize_url("HTTPS://[2001:0DB8:0:0::1]:443/x#fragment") == (
        "https://[2001:db8::1]:443/x"
    )
    assert normalize_url("hxxps[://]evil[.]example/gate") == (
        "https://evil.example/gate"
    )


def test_url_boundary_preserves_balanced_parentheses_and_trims_sentence_punctuation() -> None:
    projected, _ = extract_text_iocs(
        "See https://example.com/path(foo), then stop.",
        "fixture",
        "record-boundary",
        "data/raw/fixture/record-boundary.json",
    )

    assert [(row["ioc_type"], row["ioc_value"]) for row in projected] == [
        ("URL", "https://example.com/path(foo)")
    ]


def test_orkl_url_boundary_preserves_balanced_parentheses() -> None:
    observations = _extract_orkl_indicators(
        {"body": "C2 https://example.com/path(foo), then stop."}
    )

    assert [(row["type"], row["value"]) for row in observations] == [
        ("url", "https://example.com/path(foo)")
    ]


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


def test_scalar_reference_url_is_excluded_after_normalization() -> None:
    observations = _extract_orkl_indicators(
        {
            "references": "hxxps://citation[.]example/source",
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


def test_sources_and_further_reading_are_citation_sections() -> None:
    observations = _extract_orkl_indicators(
        {
            "body": (
                "Sources\n"
                "1. hxxps://citation[.]example/source\n\n"
                "Further Reading\n"
                "1. https://reading.example/report\n\n"
                "IOC Appendix\n"
                "1. hxxps://evil[.]example/gate.php"
            )
        }
    )

    assert [(row["type"], row["value"]) for row in observations] == [
        ("url", "https://evil.example/gate.php")
    ]


def test_inline_source_url_is_excluded_but_body_ioc_is_kept() -> None:
    observations = _extract_orkl_indicators(
        {
            "body": (
                "Source: hxxps://citation[.]example/source\n"
                "C2: hxxps://evil[.]example/gate.php"
            )
        }
    )

    assert [(row["type"], row["value"]) for row in observations] == [
        ("url", "https://evil.example/gate.php")
    ]


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
    assert normalize_domain("w3wp.exe") is None
    assert normalize_domain("cat.png") is None
    assert normalize_domain("temp.hex") is None
    assert normalize_domain("foo.py") == "foo.py"


def test_malformed_ip_is_not_projected_as_network_evidence() -> None:
    projected, _ = extract_text_iocs(
        "not an IP: 999.999.999.999",
        "fixture",
        "record-invalid-ip",
        "data/raw/fixture/record-invalid-ip.json",
    )

    assert projected == []


def test_shared_url_identity_is_consistent_across_active_paths() -> None:
    raw_url = "HTTPS://Example.Museum/path#fragment"
    expected = "https://example.museum/path"

    generic, _ = extract_text_iocs(
        raw_url,
        "fixture",
        "record-shared-url",
        "data/raw/fixture/record-shared-url.json",
    )
    orkl = _extract_orkl_indicators({"body": raw_url})

    assert normalize_url(raw_url) == expected
    assert normalize_misp_url(raw_url) == expected
    assert [(row["ioc_type"], row["ioc_value"]) for row in generic] == [
        ("URL", expected)
    ]
    assert [(row["type"], row["value"]) for row in orkl] == [("url", expected)]


def test_misp_scheme_less_ipv6_url_is_bracketed_canonically() -> None:
    assert normalize_misp_url("2001:db8::1/path") == "http://[2001:db8::1]/path"
    assert normalize_misp_url("[2001:db8::1]:443/path") == (
        "http://[2001:db8::1]:443/path"
    )
    projected, _ = _extract_misp_iocs(
        {"Attribute": [{"type": "url", "value": "evil.example/path"}]},
        "misp-scheme-less",
        "data/raw/misp/misp-scheme-less.json",
    )
    assert [(row["ioc_type"], row["ioc_value"]) for row in projected] == [
        ("URL", "http://evil.example/path")
    ]


def test_misp_deleted_attributes_are_ignored_and_ports_are_preserved() -> None:
    projected, _ = _extract_misp_iocs(
        {
                "Attribute": [
                    {"type": "ip-src|port", "value": "192.0.2.1|443"},
                    {"type": "ip-dst|port", "value": "198.51.100.2|8443"},
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
        ("IP", "192.0.2.1", 443),
        ("IP", "198.51.100.2", 8443),
    ]
    deleted_projected, _ = _extract_misp_iocs(
        {
            "deleted": True,
            "Attribute": [{"type": "domain", "value": "event-deleted.example"}],
        },
        "misp-deleted-event",
        "data/raw/misp/misp-deleted-event.json",
    )
    assert deleted_projected == []


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


def test_builder_accepts_scheme_less_otx_url_indicators(tmp_path: Path) -> None:
    source_root = tmp_path / "otx"
    source_root.mkdir()
    (source_root / "pulse.json").write_text(
        json.dumps(
            {
                "id": "pulse-scheme-less-url",
                "indicators": [
                    {"type": "url", "indicator": "evil.example/path"}
                ],
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    build_dataset(SourceRoots(otx=source_root), output_dir)
    nodes = [json.loads(line) for line in (output_dir / "nodes.jsonl").read_text().splitlines()]
    coverage = json.loads((output_dir / "coverage_audit.json").read_text())

    assert {row["value"] for row in nodes} >= {"http://evil.example/path"}
    assert coverage["rejected_record_count"] == 0


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


def test_builder_retains_no_ioc_events_for_rejection_and_metric_closure(tmp_path: Path) -> None:
    source_root = tmp_path / "misp"
    source_root.mkdir()
    (source_root / "event.json").write_text(
        json.dumps(
            {
                "Event": {
                    "uuid": "misp-no-ioc-1",
                    "Attribute": [{"type": "md5", "value": "a" * 32}],
                }
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    build_dataset(SourceRoots(circl_misp=source_root), output_dir)
    events = [json.loads(line) for line in (output_dir / "events.jsonl").read_text().splitlines()]
    rejected = [
        json.loads(line)
        for line in (output_dir / "rejected_records.jsonl").read_text().splitlines()
    ]
    coverage = json.loads((output_dir / "coverage_audit.json").read_text())

    event_id = "event:circl_misp:misp-no-ioc-1"
    assert [row["event_id"] for row in events] == [event_id]
    assert {row["event_id"] for row in rejected} == {event_id}
    assert coverage["zero_network_ioc_event_count"] == 1
    assert coverage["all_evidence_event_count"] == 0
    assert coverage["isolated_event_count"] == 1
    assert coverage["dropped_event_count"] == 1


def test_event_evidence_metrics_separate_network_zero_and_non_network_only() -> None:
    metrics = _event_evidence_metrics(
        [
            {"event_id": "event:network", "ioc_type_counts": {"domain": 1}},
            {"event_id": "event:hash", "ioc_type_counts": {"hash": 1}},
            {"event_id": "event:empty", "ioc_type_counts": {}},
        ],
        [
            {
                "source_id": "event:network",
                "relation": "event_contains_domain",
            }
        ],
        attempted_event_count=3,
    )

    assert metrics == {
        "all_evidence_event_count": 2,
        "network_ioc_event_count": 1,
        "zero_network_ioc_event_count": 2,
        "non_network_only_event_count": 1,
        "isolated_event_count": 2,
    }


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
