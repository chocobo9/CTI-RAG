from __future__ import annotations

import json
from pathlib import Path

import httpx

from rag_cti.connectors.abuse_export_collection import AbuseExportCollector
from rag_cti.connectors.orkl_collection import OrklCollector
from rag_cti.connectors.source_collection_common import read_jsonl, write_jsonl


class OrklFakeTransport:
    def get(self, url: str, **kwargs: object) -> httpx.Response:
        request = httpx.Request("GET", url)
        if url.endswith("/library/info"):
            data = {"library_version": 1, "library_last_update": "2026-01-01T00:00:00Z", "library_entries": 2, "threat_actor_entries": 2, "source_entries": 1}
        elif url.endswith("/ta/entries"):
            data = [
                {"id": "actor-1", "main_name": "Actor One", "aliases": ["Alias One"], "source_id": "TEST", "source_name": "TEST:Actor One", "tools": [], "reports": None},
                {"id": "actor-2", "main_name": "Actor Two", "aliases": [], "source_id": "TEST", "source_name": "TEST:Actor Two", "tools": [], "reports": None},
            ]
        else:
            data = [
                {"id": "report-1", "title": "Tagged report", "plain_text": "text", "threat_actors": [{"id": "actor-1", "main_name": "Actor One"}, {"id": "actor-2", "main_name": "Actor Two"}], "files": {"pdf": "https://archive.orkl.eu/a.pdf"}, "references": ["https://publisher.test/report"], "sources": ["TEST"], "origins": ["pdf"], "file_creation_date": "2025-01-01T00:00:00Z", "updated_at": "2025-01-02T00:00:00Z"},
                {"id": "report-2", "title": "Untagged report", "plain_text": "", "threat_actors": [], "files": {}, "references": [], "sources": [], "origins": ["web"], "file_creation_date": None, "updated_at": None},
            ]
        return httpx.Response(200, request=request, json={"status": "success", "data": data})


def test_orkl_collection_preserves_explicit_actor_links_and_untagged_reports(tmp_path: Path) -> None:
    collector = OrklCollector(tmp_path, transport=OrklFakeTransport())
    collector.collect(page_size=20)
    result = collector.rebuild()

    assert result == {"reports": 2, "actor_profiles": 2, "actor_report_links": 2, "claims": 5}
    reports = [json.loads(line) for line in (tmp_path / "normalized/reports.jsonl").read_text().splitlines()]
    assert reports[0]["actor_labels_raw"] == ["Actor One", "Actor Two"]
    assert reports[1]["actor_labels_raw"] == []
    assert collector.validate()["valid"] is True


def test_missing_abuse_key_creates_explicit_blocked_terminal_state(tmp_path: Path, monkeypatch: object) -> None:
    del monkeypatch
    collector = AbuseExportCollector("urlhaus", tmp_path)
    result = collector.mark_blocked()

    assert result["status"] == "blocked_external_access"
    checkpoint = json.loads((tmp_path / "checkpoints/collection_state.json").read_text())
    assert checkpoint["status"] == "blocked_external_access"
    assert "ABUSECH_AUTH_KEY" not in (tmp_path / "manifests/errors.jsonl").read_text() or "required" in (tmp_path / "manifests/errors.jsonl").read_text()


def test_urlhaus_rebuild_preserves_exact_url_without_requesting_it(tmp_path: Path) -> None:
    collector = AbuseExportCollector("urlhaus", tmp_path)
    inventory = tmp_path / "raw/inventories/snapshot/full.csv"
    inventory.parent.mkdir(parents=True)
    inventory.write_text("id,dateadded,url,url_status,last_online,threat,tags,urlhaus_link,reporter\n1,2026-01-01,http://malicious.invalid/a?x=1,online,2026-01-02,malware_download,elf|Mozi,https://urlhaus.abuse.ch/url/1/,alice\n", encoding="utf-8")

    assert collector.rebuild() == {"records": 1}
    row = json.loads((tmp_path / "normalized/urls.jsonl").read_text())
    assert row["url_raw"] == "http://malicious.invalid/a?x=1"


def test_threatfox_rebuild_keeps_malware_mapping_separate_from_actor_claims(tmp_path: Path) -> None:
    collector = AbuseExportCollector("threatfox", tmp_path)
    inventory = tmp_path / "raw/inventories/snapshot/full.csv"
    inventory.parent.mkdir(parents=True)
    inventory.write_text("id,uuid,ioc,threat_type,ioc_type,malware,malware_printable,malware_alias,first_seen,last_seen,confidence_level,reference,tags,reporter\n7,u-7,evil.invalid,botnet_cc,domain,win.test,Test Malware,Alias M,2026-01-01,,75,https://example.test/ref,tag1|tag2,bob\n", encoding="utf-8")

    assert collector.rebuild() == {"records": 1}
    assert len((tmp_path / "normalized/ioc_malware_links.jsonl").read_text().splitlines()) == 1
    assert (tmp_path / "normalized/source_actor_claims.jsonl").read_text() == ""


def test_threatfox_csv_handles_spaced_quotes_and_none_sentinels(tmp_path: Path) -> None:
    collector = AbuseExportCollector("threatfox", tmp_path)
    inventory = tmp_path / "raw/inventories/snapshot/full.txt"
    inventory.parent.mkdir(parents=True)
    inventory.write_text(
        '# id,ioc,threat_type,ioc_type,malware,malware_printable,malware_alias,confidence_level,reference,tags,reporter,is_compromised\n'
        '7, "evil.invalid", "botnet_cc", "domain", "win.test", "Test Malware", "None", "75", "None", "None", "bob", "1"\n',
        encoding="utf-8",
    )

    assert collector.rebuild() == {"records": 1}
    row = json.loads((tmp_path / "normalized/iocs.jsonl").read_text())
    assert row["ioc_type_raw"] == "domain"
    assert row["malware_aliases_raw"] == []
    assert row["tags_raw"] == []
    assert row["references_raw"] == []


def test_jsonl_round_trip_preserves_unicode_line_separator(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    write_jsonl(path, [{"text": "before\u2028after"}])

    assert read_jsonl(path) == [{"text": "before\u2028after"}]
    assert len(path.read_text(encoding="utf-8").split("\n")) == 2
