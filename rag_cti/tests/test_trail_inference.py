from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "trail_inference.py"
SPEC = importlib.util.spec_from_file_location("trail_inference", SCRIPT)
assert SPEC
assert SPEC.loader
trail = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trail)


def test_map_and_validate_supported_otx_types() -> None:
    cases = [
        ("domain", "example.com", "domain"),
        ("hostname", "sub.example.com", "domain"),
        ("IPv4", "192.0.2.1", "ip"),
        ("IPv6", "2001:db8::1", "ip"),
        ("URL", "https://example.com/a", "url"),
        ("URI", "http://example.com/b", "url"),
    ]
    for raw_type, value, expected in cases:
        assert trail.adapt_ioc(raw_type, value) == (expected, value)


def test_rejects_unsupported_empty_and_invalid_values_without_guessing() -> None:
    assert trail.adapt_ioc("FileHash-SHA256", "a" * 64) is None
    assert trail.adapt_ioc("domain", "") is None
    assert trail.adapt_ioc("domain", "192.0.2.1") is None
    assert trail.adapt_ioc("IPv4", "example.com") is None
    assert trail.adapt_ioc("URI", "/relative/path") is None
    assert trail.adapt_ioc("email", "person@example.com") is None


def test_discover_snapshots_prefers_latest_wrapped_version(tmp_path: Path) -> None:
    raw = tmp_path / "otx"
    event_dir = raw / "pulse-1"
    event_dir.mkdir(parents=True)
    old = {
        "source": "otx",
        "source_id": "pulse-1",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "payload": {"id": "pulse-1", "indicators": []},
    }
    new = {
        **old,
        "fetched_at": "2026-01-02T00:00:00+00:00",
        "payload": {
            "id": "pulse-1",
            "indicators": [{"type": "domain", "indicator": "example.com"}],
        },
    }
    (event_dir / "old.json").write_text(json.dumps(old), encoding="utf-8")
    (event_dir / "new.json").write_text(json.dumps(new), encoding="utf-8")
    (raw / "pulse-1.json").write_text(json.dumps(old["payload"]), encoding="utf-8")

    discovery = trail.discover_snapshots(raw)

    assert discovery.raw_file_count == 3
    assert discovery.duplicate_event_id_count == 1
    assert discovery.selected["pulse-1"].name == "new.json"


def test_adapt_event_deduplicates_and_never_emits_attribution() -> None:
    event = {
        "id": "pulse-1",
        "adversary": "APT Example",
        "groups": ["APT Example"],
        "indicators": [
            {"type": "domain", "indicator": "example.com"},
            {"type": "hostname", "indicator": "example.com"},
            {"type": "IPv4", "indicator": "192.0.2.1"},
            {"type": "CVE", "indicator": "CVE-2026-0001"},
        ],
    }

    row, request = trail.adapt_event(event, Path("source.json"))

    assert request == {
        "iocs": [
            {"type": "domain", "value": "example.com"},
            {"type": "ip", "value": "192.0.2.1"},
        ]
    }
    assert row["source_attribution"] == {
        "adversary": "APT Example",
        "groups": ["APT Example"],
    }
    assert row["raw_ioc_count"] == 4
    assert row["supported_ioc_count"] == 3
    assert row["deduplicated_ioc_count"] == 2
    assert "adversary" not in request
