from __future__ import annotations

from rag_cti.trail_dataset.builder import _extract_orkl_indicators
from rag_cti.trail_part1 import _extract_orkl_iocs


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
