from __future__ import annotations

from rag_cti.trail_dataset.builder import _extract_orkl_indicators


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
