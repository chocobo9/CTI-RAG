from __future__ import annotations

import json
from pathlib import Path

from rag_cti.connectors.cisa_collection import CisaCollector, canonicalize_url

LISTING = b"""<html><main>
<article><time>Jan 2, 2025</time><div>Cybersecurity Advisory | AA25-002A</div>
<h3><a href='/news-events/cybersecurity-advisories/aa25-002a'>Example</a></h3></article>
<article><div>Alert</div><a href='/news-events/alerts/nope'>Not included</a></article>
<nav><a rel='next' href='?f%5B0%5D=advisory_type%3A94&amp;page=1'>Next</a></nav>
</main></html>"""

ADVISORY = b"""<html><head><title>Example | CISA</title></head><body><main>
<h1>Example Advisory</h1><div>Cybersecurity Advisory | AA25-002A</div>
<time datetime='2025-01-02'>January 2, 2025</time><p>Last revised: January 3, 2025</p>
<h2>Summary</h2><p>CISA and FBI assess that likely state-sponsored actors targeted energy organizations.</p>
<h2>Indicators of Compromise</h2><table><tr><th>Type</th><th>Value</th></tr>
<tr><td>IP</td><td>192.0.2.4</td></tr><tr><td>Hash</td><td>aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa</td></tr></table>
<h2>References</h2><a href='https://example.test/report'>Report</a>
<a href='/sites/default/files/iocs.json'>STIX JSON</a></main></body></html>"""


def test_listing_filters_type_and_preserves_next_page(tmp_path: Path) -> None:
    collector = CisaCollector(tmp_path)
    entries, next_url = collector.parse_listing(LISTING, collector.listing_url)
    assert [entry.source_record_id for entry in entries] == ["AA25-002A"]
    assert next_url is not None
    assert "page=1" in next_url
    assert canonicalize_url(entries[0].url).endswith("/aa25-002a")


def test_store_rebuild_version_and_observations(tmp_path: Path) -> None:
    collector = CisaCollector(tmp_path)
    url = "https://www.cisa.gov/news-events/cybersecurity-advisories/aa25-002a"
    first = collector.store_advisory(url, ADVISORY, fetched_at="2025-01-04T00:00:00Z")
    same = collector.store_advisory(url, ADVISORY, fetched_at="2025-01-05T00:00:00Z")
    changed = collector.store_advisory(
        url, ADVISORY.replace(b"energy", b"water"), fetched_at="2025-01-06T00:00:00Z"
    )
    assert first["status"] == "created"
    assert same["status"] == "unchanged"
    assert changed["status"] == "versioned"

    counts = collector.rebuild()
    assert counts["advisories"] == 1
    row = json.loads((tmp_path / "normalized/advisories.jsonl").read_text())
    assert row["report_id"] == "cisa:advisory:AA25-002A"
    assert row["updated_at"] is not None
    assert row["attachment_refs"]
    text = (tmp_path / row["content_text_ref"]).read_text()
    assert "## Indicators of Compromise" in text
    assert "Type | Value" in text
    summary = json.loads((tmp_path / "normalized/advisory_observation_summaries.jsonl").read_text())
    assert summary["explicit_ioc_section_present"] is True
    assert summary["ip_candidate_count"] == 1
    assert summary["hash_candidate_count"] == 1
    claims = [
        json.loads(x)
        for x in (tmp_path / "normalized/source_actor_claim_candidates.jsonl")
        .read_text()
        .splitlines()
    ]
    assert claims[0]["raw_actor_text"] == "likely state-sponsored actors"
    assert claims[0]["claim_modality"] == "qualified"


def test_attachment_failure_does_not_block_rebuild(tmp_path: Path) -> None:
    collector = CisaCollector(tmp_path)
    url = "https://www.cisa.gov/news-events/cybersecurity-advisories/aa25-002a"
    collector.store_advisory(url, ADVISORY)
    collector.record_attachment_failure(
        url, "https://www.cisa.gov/sites/default/files/iocs.json", 404, "not found"
    )
    collector.rebuild()
    rows = [
        json.loads(x) for x in (tmp_path / "normalized/attachments.jsonl").read_text().splitlines()
    ]
    assert rows[0]["fetch_status"] == "not_found"
