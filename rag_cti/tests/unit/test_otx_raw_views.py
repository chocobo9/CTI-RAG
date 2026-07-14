from __future__ import annotations

from rag_cti.connectors.otx_actor_collection import indicator_page_source_id
from rag_cti.connectors.otx_raw_views import (
    indicator_completeness,
    latest_indicator_pages,
    pulse_with_full_indicators,
)
from rag_cti.store.raw_store import RawStore


def test_pulse_view_prefers_indicator_endpoint_results(tmp_path):
    store = RawStore(tmp_path)
    fetched_at = "2026-07-04T00:00:00+00:00"
    pulse = {
        "id": "pulse-1",
        "name": "Pulse",
        "indicators": [{"indicator": "detail-only.example", "type": "domain"}],
    }
    endpoint_page = {
        "count": 2,
        "next": None,
        "results": [
            {
                "indicator": "endpoint-1.example",
                "type": "domain",
                "pulse_key": "pulse-1",
                "false_positive": False,
                "slug": "endpoint-1-example",
            },
            {
                "indicator": "endpoint-2.example",
                "type": "hostname",
                "pulse_key": "pulse-1",
                "false_positive": False,
                "slug": "endpoint-2-example",
            },
        ],
    }

    store.write("otx", "pulse-1", pulse, fetched_at)
    store.write("otx_indicator_page", indicator_page_source_id("pulse-1", 1), endpoint_page, fetched_at)

    pages = latest_indicator_pages(store, "pulse-1")
    view = pulse_with_full_indicators(pulse, pages)

    assert [row["indicator"] for row in view["indicators"]] == [
        "endpoint-1.example",
        "endpoint-2.example",
    ]
    assert "pulse_key" in view["indicators"][0]


def test_indicator_completeness_reports_missing_pages_and_mismatches():
    pulse = {
        "id": "pulse-1",
        "name": "Pulse",
        "description": "",
        "author_name": "author",
        "modified": "2026-01-02",
        "created": "2026-01-01",
        "tags": [],
        "references": [],
        "public": 1,
        "adversary": "",
        "targeted_countries": [],
        "malware_families": [],
        "attack_ids": [],
        "industries": [],
        "TLP": "white",
        "indicators": [{"indicator": "one.example", "type": "domain"}],
        "revision": 1,
        "groups": [],
        "in_group": False,
        "author": {},
        "is_subscribing": False,
    }

    missing = indicator_completeness("pulse-1", pulse, [])
    mismatch = indicator_completeness(
        "pulse-1",
        pulse,
        [{"count": 2, "results": [{"indicator": "one.example", "type": "domain"}]}],
    )

    assert missing["status"] == "missing_indicator_pages"
    assert mismatch["status"] == "indicator_count_mismatch"
    assert mismatch["indicator_counts_match"] is False
