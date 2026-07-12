from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx

from rag_cti.connectors.aptnotes_collection import (
    AptnotesCollector,
    IndexRecord,
    canonical_report_id,
    detect_media_type,
    normalize_text,
    simhash64,
)

COMMIT = "8595fbdee6747be9e9f730fd0bacd247157314df"


def _record(index: int = 0, occurrence: int = 0) -> IndexRecord:
    return IndexRecord(
        source_record_index=index,
        duplicate_occurrence=occurrence,
        filename="same-name",
        title="APT Report",
        publisher="Vendor",
        url="https://app.box.com/s/token",
        expected_sha1=hashlib.sha1(b"%PDF-1.4\nbody").hexdigest(),
        listed_date="01/02/2024",
        listed_year="2024",
        raw={"Filename": "same-name"},
    )


def _snapshot(root: Path, rows: list[dict[str, str]]) -> None:
    repository = root / "raw/repository"
    repository.mkdir(parents=True)
    (repository / "APTnotes.json").write_text(json.dumps(rows), encoding="utf-8")
    (repository / "APTnotes.csv").write_text(
        "Filename,Title,Source,Link,SHA-1,Date,Year\n"
        + "\n".join(
            f'{r["Filename"]},{r["Title"]},{r["Source"]},{r["Link"]},{r["SHA-1"]},{r["Date"]},{r["Year"]}'
            for r in rows
        ),
        encoding="utf-8",
    )
    (root / "manifests").mkdir(parents=True)
    (root / "manifests/repository_snapshot.json").write_text(
        json.dumps({"repository_commit": COMMIT}), encoding="utf-8"
    )


def test_ids_preserve_identical_index_rows() -> None:
    first = canonical_report_id(_record(10, 0))
    second = canonical_report_id(_record(11, 1))
    assert first != second
    assert first == canonical_report_id(_record(99, 0))


def test_media_text_and_simhash_are_deterministic() -> None:
    assert detect_media_type(b"%PDF-1.7\n", None)[0] == "application/pdf"
    assert detect_media_type(b"<html><body>x</body></html>", None)[0] == "text/html"
    assert normalize_text(" A\r\n  B\tC ") == "a b c"
    assert simhash64("alpha beta beta") == simhash64("alpha beta beta")
    assert len(simhash64("alpha beta")) == 16


def test_identical_rows_rebuild_as_separate_reports(tmp_path: Path) -> None:
    row = {
        "Filename": "duplicate",
        "Title": "Same",
        "Source": "Vendor",
        "Link": "https://app.box.com/s/token",
        "SHA-1": "a" * 40,
        "Date": "01/02/2024",
        "Year": "2024",
    }
    _snapshot(tmp_path, [row, row])
    collector = AptnotesCollector(tmp_path)
    result = collector.rebuild()
    reports = collector.read_jsonl(tmp_path / "normalized/reports.jsonl")
    assert result["reports"] == 2
    assert len({r["report_id"] for r in reports}) == 2
    assert [r["duplicate_occurrence"] for r in reports] == [0, 1]


def test_collection_downloads_and_resume_skips_network(tmp_path: Path) -> None:
    body = b"%PDF-1.4\nbody"
    row = {
        "Filename": "report",
        "Title": "Report",
        "Source": "Vendor",
        "Link": "https://app.box.com/s/token",
        "SHA-1": hashlib.sha1(body).hexdigest(),
        "Date": "01/02/2024",
        "Year": "2024",
    }
    _snapshot(tmp_path, [row])
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "/s/token" in str(request.url):
            page = (
                '<script> Box.postStreamData = {"/app-api/enduserapp/shared-item":'
                '{"sharedName":"token","itemID":123,"itemType":"file"}};</script>'
            )
            return httpx.Response(200, text=page, headers={"content-type": "text/html"})
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": "application/pdf", "content-disposition": 'attachment; filename="x.pdf"'},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    collector = AptnotesCollector(tmp_path, transport=client, rate_delay=0)
    state = collector.collect()
    assert list(state["reports"].values())[0]["status"] == "success"
    assert len(calls) == 2

    class NoNetwork:
        def get(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("resume requested the network")

    AptnotesCollector(tmp_path, transport=NoNetwork(), rate_delay=0).collect()  # type: ignore[arg-type]


def test_bad_download_is_terminal_and_does_not_stop_batch(tmp_path: Path) -> None:
    good = b"%PDF-1.4\ngood"
    rows = [
        {"Filename": "bad", "Title": "Bad", "Source": "V", "Link": "https://app.box.com/s/bad", "SHA-1": "0" * 40, "Date": "01/01/2024", "Year": "2024"},
        {"Filename": "good", "Title": "Good", "Source": "V", "Link": "https://app.box.com/s/good", "SHA-1": hashlib.sha1(good).hexdigest(), "Date": "01/02/2024", "Year": "2024"},
    ]
    _snapshot(tmp_path, rows)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/s/bad" in url:
            return httpx.Response(404)
        if "/s/good" in url:
            return httpx.Response(200, text='<script> Box.postStreamData = {"/app-api/enduserapp/shared-item":{"sharedName":"good","itemID":2,"itemType":"file"}};</script>')
        return httpx.Response(200, content=good, headers={"content-type": "application/pdf"})

    state = AptnotesCollector(tmp_path, transport=httpx.Client(transport=httpx.MockTransport(handler)), rate_delay=0).collect()
    assert sorted(x["status"] for x in state["reports"].values()) == ["not_found", "success"]


def test_actor_candidates_require_explicit_claim_and_actor_like_capitalization(tmp_path: Path) -> None:
    collector = AptnotesCollector(tmp_path)
    text = (
        "Analysts possibly attributed the campaign to Wicked Rose. "
        "This report linked the attack to regular civilians and online activity."
    )
    rows = collector._actor_candidates("aptnotes:report:x", text, "extracted/text/x.txt")
    assert [row["raw_actor_text"] for row in rows] == ["Wicked Rose"]
    assert "possibly attributed" in rows[0]["claim_excerpt"]
