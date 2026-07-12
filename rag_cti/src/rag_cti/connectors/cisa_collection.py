"""Traceable collection of CISA Cybersecurity Advisories (advisory type 94)."""

from __future__ import annotations

import hashlib
import html
import html.parser
import json
import mimetypes
import os
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx

BASE_URL = "https://www.cisa.gov"
LISTING_URL = BASE_URL + "/news-events/cybersecurity-advisories?f%5B0%5D=advisory_type%3A94"
NORMALIZATION_VERSION = "cisa-v1"
ADVISORY_ID_RE = re.compile(r"\b((?:AA|TA|AR)\d{2}-\d{3}[A-Z]?)\b", re.I)
DOWNLOAD_EXTENSIONS = {".pdf", ".json", ".csv", ".txt", ".xlsx", ".xls", ".xml", ".zip", ".stix"}
TRANSIENT = {429, 500, 502, 503, 504}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _write_json(path: Path, value: Any) -> None:
    _atomic(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ).encode(),
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def canonicalize_url(url: str, base: str = BASE_URL) -> str:
    parts = urlsplit(urljoin(base, html.unescape(url)))
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    path = re.sub(r"/+", "/", parts.path).rstrip("/") or "/"
    return urlunsplit(("https", parts.netloc.lower(), path, query, ""))


def _slug(url: str) -> str:
    value = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or hashlib.sha256(url.encode()).hexdigest()[:16]


def _safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return value[:180] or "attachment.bin"


@dataclass(frozen=True)
class AdvisoryEntry:
    url: str
    title: str
    source_record_id: str | None
    listing_url: str
    listing_date: str | None = None


class Transport(Protocol):
    def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response: ...


class _ListingParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.article_depth = 0
        self.article_text: list[str] = []
        self.article_links: list[tuple[str, str]] = []
        self.link: str | None = None
        self.link_rel = ""
        self.link_text: list[str] = []
        self.entries: list[tuple[str, str, str]] = []
        self.next_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "article":
            self.article_depth += 1
        if tag == "a":
            self.link = values.get("href")
            self.link_rel = values.get("rel") or ""
            self.link_text = []

    def handle_data(self, data: str) -> None:
        if self.article_depth:
            self.article_text.append(data)
        if self.link is not None:
            self.link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.link is not None:
            text = " ".join("".join(self.link_text).split())
            if self.article_depth:
                self.article_links.append((self.link, text))
            if "next" in self.link_rel.lower() or "go to next page" in text.lower():
                self.next_href = self.link
            self.link = None
        if tag == "article" and self.article_depth:
            self.article_depth -= 1
            if self.article_depth == 0:
                text = " ".join(" ".join(self.article_text).split())
                if re.search(r"\bCybersecurity Advisory\b", text, re.I):
                    for href, title in self.article_links:
                        if "/news-events/cybersecurity-advisories/" in href:
                            self.entries.append((href, title, text))
                            break
                self.article_text, self.article_links = [], []


class _AdvisoryParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_main = False
        self.main_depth = 0
        self.skip_depth = 0
        self.current_heading: str | None = None
        self.heading_buf: list[str] = []
        self.block_buf: list[str] = []
        self.blocks: list[tuple[str | None, str]] = []
        self.headings: list[str] = []
        self.links: list[tuple[str, str, str | None]] = []
        self.link_href: str | None = None
        self.link_buf: list[str] = []
        self.table_rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.title_buf: list[str] = []
        self.in_title = False

    def _flush(self) -> None:
        text = " ".join("".join(self.block_buf).split())
        if text:
            self.blocks.append((self.current_heading, text))
        self.block_buf = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "main":
            self.in_main = True
            self.main_depth = 1
            return
        if self.in_main:
            if tag == "main":
                self.main_depth += 1
            if tag in {"script", "style", "nav", "aside", "form"}:
                self.skip_depth += 1
            if not self.skip_depth and tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                self._flush()
                self.heading_buf = []
            if not self.skip_depth and tag == "a":
                self.link_href, self.link_buf = values.get("href"), []
            if not self.skip_depth and tag == "tr":
                self.row = []
            if not self.skip_depth and tag in {"td", "th"}:
                self.cell = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_buf.append(data)
        if not self.in_main or self.skip_depth:
            return
        self.block_buf.append(data)
        if self.heading_buf is not None:
            self.heading_buf.append(data)
        if self.link_href is not None:
            self.link_buf.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if not self.in_main:
            return
        if tag in {"script", "style", "nav", "aside", "form"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            heading = " ".join("".join(self.heading_buf).split())
            if heading:
                self.current_heading = heading
                self.headings.append(heading)
                self.blocks.append((heading, "#" * int(tag[1]) + " " + heading))
            self.block_buf, self.heading_buf = [], []
        elif tag == "a" and self.link_href is not None:
            self.links.append(
                (self.link_href, " ".join("".join(self.link_buf).split()), self.current_heading)
            )
            self.link_href = None
        elif tag in {"td", "th"} and self.cell is not None:
            if self.row is not None:
                self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.table_rows.append(self.row)
                self.blocks.append((self.current_heading, " | ".join(self.row)))
            self.row = None
            self.block_buf = []
        elif tag in {"p", "li", "div", "section", "blockquote", "pre"}:
            self._flush()
        elif tag == "main":
            self._flush()
            self.main_depth -= 1
            if self.main_depth <= 0:
                self.in_main = False

    @property
    def text(self) -> str:
        return "\n\n".join(value for _, value in self.blocks if value).strip() + "\n"


class CisaCollector:
    """CISA-specific enumeration, acquisition, normalization, validation and reporting."""

    def __init__(
        self,
        root: Path,
        *,
        transport: Transport | None = None,
        timeout: float = 60,
        retries: int = 3,
        rate_delay: float = 0.25,
        spool: Path | None = None,
    ) -> None:
        self.root, self.listing_url = Path(root), LISTING_URL
        self.transport = transport or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "rag-cti-cisa-collector/1.0",
                "Accept": "text/html,application/json,*/*",
            },
        )
        self.retries, self.rate_delay, self.spool = (
            retries,
            rate_delay,
            Path(spool) if spool else None,
        )
        for directory in (
            "raw/html",
            "raw/metadata",
            "raw/attachments",
            "extracted/text",
            "normalized",
            "manifests",
            "checkpoints",
            "logs",
            "reports",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        self._spool_rows = self._load_spool()

    def _load_spool(self) -> dict[str, dict[str, Any]]:
        if not self.spool or not self.spool.exists():
            return {}
        rows = (
            _read_jsonl(self.spool)
            if self.spool.is_file()
            else _read_jsonl(self.spool / "responses.jsonl")
        )
        return {canonicalize_url(row["request_url"]): row for row in rows if row.get("request_url")}

    def _get(
        self, url: str, headers: dict[str, str] | None = None
    ) -> tuple[bytes, str, int, dict[str, str]]:
        key = canonicalize_url(url)
        if key in self._spool_rows:
            row = self._spool_rows[key]
            body_path = Path(row["body_path"])
            if not body_path.is_absolute() and self.spool:
                body_path = (self.spool if self.spool.is_dir() else self.spool.parent) / body_path
            body = body_path.read_bytes()
            if row.get("sha256") and hashlib.sha256(body).hexdigest() != row["sha256"]:
                raise ValueError(f"capture spool hash mismatch: {body_path}")
            return (
                body,
                row.get("final_url", url),
                int(row.get("status", 200)),
                dict(row.get("headers") or {}),
            )
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.transport.get(url, headers=headers)
                if response.status_code not in TRANSIENT:
                    return (
                        response.content,
                        str(response.url),
                        response.status_code,
                        dict(response.headers),
                    )
                last = RuntimeError(f"transient HTTP {response.status_code}")
            except (httpx.TransportError, TimeoutError) as exc:
                last = exc
            if attempt < self.retries:
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"request failed after retries: {url}: {last}")

    def parse_listing(
        self, content: bytes, listing_url: str
    ) -> tuple[list[AdvisoryEntry], str | None]:
        parser = _ListingParser()
        parser.feed(content.decode("utf-8", "replace"))
        entries: list[AdvisoryEntry] = []
        for href, title, source_text in parser.entries:
            url = canonicalize_url(href, listing_url)
            match = ADVISORY_ID_RE.search(source_text)
            date = re.search(
                r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
                source_text,
                re.I,
            )
            entries.append(
                AdvisoryEntry(
                    url,
                    title,
                    match.group(1).upper() if match else None,
                    listing_url,
                    date.group(0) if date else None,
                )
            )
        next_url = canonicalize_url(parser.next_href, listing_url) if parser.next_href else None
        return entries, next_url

    def enumerate(self, *, limit: int | None = None) -> list[AdvisoryEntry]:
        url: str | None = self.listing_url
        pages: list[dict[str, Any]] = []
        all_entries: list[AdvisoryEntry] = []
        seen_pages: set[str] = set()
        while url and url not in seen_pages:
            seen_pages.add(url)
            body, final, status, headers = self._get(url)
            if status != 200:
                raise RuntimeError(f"listing HTTP {status}: {url}")
            entries, next_url = self.parse_listing(body, final)
            sha = hashlib.sha256(body).hexdigest()
            page_path = self.root / "raw/metadata" / f"listing_{len(pages):04d}_{sha[:12]}.html"
            if not page_path.exists():
                _atomic(page_path, body)
            pages.append(
                {
                    "page_index": len(pages),
                    "request_url": url,
                    "final_url": final,
                    "status": status,
                    "sha256": sha,
                    "raw_ref": page_path.relative_to(self.root).as_posix(),
                    "next_url": next_url,
                    "response_headers": headers,
                    "entries": [asdict(x) for x in entries],
                    "fetched_at": utc_now(),
                }
            )
            all_entries.extend(entries)
            if limit is not None and len({x.url for x in all_entries}) >= limit:
                break
            url = next_url
            time.sleep(self.rate_delay)
        unique = {entry.url: entry for entry in all_entries}
        selected = sorted(unique.values(), key=lambda x: x.url)
        if limit is not None:
            selected = selected[:limit]
        _write_json(
            self.root / "manifests/source_snapshot.json",
            {
                "source": "cisa_cybersecurity_advisory",
                "filter": "advisory_type:94",
                "listing_url": self.listing_url,
                "enumerated_at": utc_now(),
                "page_count": len(pages),
                "urls_discovered": len(unique),
                "pages": pages,
                "advisories": [asdict(x) for x in selected],
            },
        )
        return selected

    def _parse(self, content: bytes) -> _AdvisoryParser:
        parser = _AdvisoryParser()
        parser.feed(content.decode("utf-8", "replace"))
        return parser

    def _identity(self, url: str, content: bytes) -> tuple[str, str | None]:
        text = content.decode("utf-8", "replace")
        match = ADVISORY_ID_RE.search(text)
        source_id = match.group(1).upper() if match else None
        return source_id or _slug(url), source_id

    def store_advisory(
        self,
        url: str,
        content: bytes,
        *,
        fetched_at: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        fetched_at, url = fetched_at or utc_now(), canonicalize_url(url)
        identity, source_id = self._identity(url, content)
        sha = hashlib.sha256(content).hexdigest()
        base = self.root / "raw/html" / f"{_safe_filename(identity)}.html"
        status, target = "created", base
        if base.exists():
            if hashlib.sha256(base.read_bytes()).hexdigest() == sha:
                status = "unchanged"
            else:
                status, target = (
                    "versioned",
                    self.root / "raw/html" / f"{_safe_filename(identity)}__{sha[:16]}.html",
                )
        if not target.exists():
            _atomic(target, content)
        row = {
            "report_id": f"cisa:advisory:{identity}",
            "source_record_id": source_id,
            "canonical_url": url,
            "raw_html_ref": target.relative_to(self.root).as_posix(),
            "raw_sha256": sha,
            "byte_size": len(content),
            "fetched_at": fetched_at,
            "status": status,
            "http_headers": headers or {},
        }
        rows = _read_jsonl(self.root / "manifests/advisory_manifest.jsonl")
        if not any(x["canonical_url"] == url and x["raw_sha256"] == sha for x in rows):
            rows.append(row)
            _write_jsonl(
                self.root / "manifests/advisory_manifest.jsonl",
                sorted(rows, key=lambda x: (x["canonical_url"], x["fetched_at"], x["raw_sha256"])),
            )
        return row

    def _attachment_id(self, report_id: str, url: str) -> str:
        return (
            "cisa:attachment:"
            + hashlib.sha256(f"{report_id}|{canonicalize_url(url)}".encode()).hexdigest()
        )

    def record_attachment_failure(
        self, advisory_url: str, source_url: str, status: int | None, message: str
    ) -> dict[str, Any]:
        identity, _ = self._identity(advisory_url, advisory_url.encode())
        report_id = f"cisa:advisory:{identity}"
        row = {
            "attachment_id": self._attachment_id(report_id, source_url),
            "report_id": report_id,
            "source_url": canonicalize_url(source_url),
            "final_url": canonicalize_url(source_url),
            "filename": _safe_filename(urlsplit(source_url).path.rsplit("/", 1)[-1]),
            "media_type": None,
            "byte_size": 0,
            "sha256": None,
            "local_path": None,
            "fetch_status": "not_found"
            if status == 404
            else "blocked"
            if status in {401, 403}
            else "failed",
            "fetched_at": utc_now(),
            "error": message,
        }
        self._upsert_attachment(row)
        return row

    def _upsert_attachment(self, row: dict[str, Any]) -> None:
        path = self.root / "raw/metadata/attachments.jsonl"
        rows = [x for x in _read_jsonl(path) if x["attachment_id"] != row["attachment_id"]]
        rows.append(row)
        _write_jsonl(path, sorted(rows, key=lambda x: x["attachment_id"]))

    def _download_attachment(self, report_id: str, source_url: str) -> dict[str, Any]:
        fetched_at = utc_now()
        try:
            body, final, status, headers = self._get(source_url)
            if status != 200:
                raise httpx.HTTPStatusError(
                    str(status),
                    request=httpx.Request("GET", source_url),
                    response=httpx.Response(status),
                )
            sha = hashlib.sha256(body).hexdigest()
            filename = _safe_filename(
                urlsplit(final).path.rsplit("/", 1)[-1] or f"attachment-{sha[:12]}"
            )
            path = self.root / "raw/attachments" / f"{sha[:16]}_{filename}"
            if not path.exists():
                _atomic(path, body)
            row = {
                "attachment_id": self._attachment_id(report_id, source_url),
                "report_id": report_id,
                "source_url": canonicalize_url(source_url),
                "final_url": canonicalize_url(final),
                "filename": filename,
                "media_type": headers.get("content-type", "").split(";", 1)[0]
                or mimetypes.guess_type(filename)[0],
                "byte_size": len(body),
                "sha256": sha,
                "local_path": path.relative_to(self.root).as_posix(),
                "fetch_status": "success",
                "fetched_at": fetched_at,
            }
        except httpx.HTTPStatusError as exc:
            row = {
                "attachment_id": self._attachment_id(report_id, source_url),
                "report_id": report_id,
                "source_url": canonicalize_url(source_url),
                "final_url": canonicalize_url(source_url),
                "filename": _safe_filename(urlsplit(source_url).path.rsplit("/", 1)[-1]),
                "media_type": None,
                "byte_size": 0,
                "sha256": None,
                "local_path": None,
                "fetch_status": "not_found"
                if exc.response.status_code == 404
                else "blocked"
                if exc.response.status_code in {401, 403}
                else "failed",
                "fetched_at": fetched_at,
                "error": str(exc),
            }
        except Exception as exc:  # noqa: BLE001
            row = {
                "attachment_id": self._attachment_id(report_id, source_url),
                "report_id": report_id,
                "source_url": canonicalize_url(source_url),
                "final_url": canonicalize_url(source_url),
                "filename": _safe_filename(urlsplit(source_url).path.rsplit("/", 1)[-1]),
                "media_type": None,
                "byte_size": 0,
                "sha256": None,
                "local_path": None,
                "fetch_status": "failed",
                "fetched_at": fetched_at,
                "error": str(exc),
            }
        self._upsert_attachment(row)
        return row

    def collect(
        self, entries: list[AdvisoryEntry] | None = None, *, limit: int | None = None
    ) -> dict[str, Any]:
        entries = entries or self.enumerate(limit=limit)
        checkpoint_path = self.root / "checkpoints/collection_state.json"
        checkpoint = (
            json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if checkpoint_path.exists()
            else {"entries": {}}
        )
        for entry in entries[:limit] if limit else entries:
            state = checkpoint["entries"].get(entry.url, {})
            raw = self.root / state.get("raw_html_ref", "") if state.get("raw_html_ref") else None
            if (
                state.get("status") == "success"
                and raw
                and raw.is_file()
                and hashlib.sha256(raw.read_bytes()).hexdigest() == state.get("sha256")
            ):
                continue
            try:
                body, final, status, headers = self._get(
                    entry.url, {"If-None-Match": state["etag"]} if state.get("etag") else None
                )
                if status != 200:
                    raise RuntimeError(f"HTTP {status}")
                result = self.store_advisory(final, body, headers=headers)
                parser = self._parse(body)
                for href, _, _ in parser.links:
                    absolute = canonicalize_url(href, final)
                    extension = Path(urlsplit(absolute).path).suffix.lower()
                    if (
                        extension in DOWNLOAD_EXTENSIONS
                        or "/sites/default/files/" in absolute
                        and extension
                    ):
                        self._download_attachment(result["report_id"], absolute)
                        time.sleep(self.rate_delay)
                state = {
                    "status": "success",
                    "raw_html_ref": result["raw_html_ref"],
                    "sha256": result["raw_sha256"],
                    "etag": headers.get("etag"),
                    "completed_at": utc_now(),
                }
            except Exception as exc:  # noqa: BLE001
                state = {
                    "status": "permanent_failure",
                    "error": str(exc),
                    "completed_at": utc_now(),
                }
            checkpoint["entries"][entry.url] = state
            checkpoint["updated_at"] = utc_now()
            _write_json(checkpoint_path, checkpoint)
            time.sleep(self.rate_delay)
        checkpoint["completed_at"] = utc_now()
        _write_json(checkpoint_path, checkpoint)
        self._write_errors(checkpoint)
        return checkpoint

    def _write_errors(self, checkpoint: dict[str, Any]) -> None:
        rows = [
            {
                "source_url": url,
                "error_kind": "collection_failure",
                "message": state.get("error"),
                "permanent": True,
                "recorded_at": state.get("completed_at"),
            }
            for url, state in checkpoint.get("entries", {}).items()
            if state.get("status") == "permanent_failure"
        ]
        _write_jsonl(self.root / "manifests/errors.jsonl", rows)

    def _latest_manifests(self) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for row in _read_jsonl(self.root / "manifests/advisory_manifest.jsonl"):
            latest[row["canonical_url"]] = row
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in latest.values():
            grouped.setdefault(row["report_id"], []).append(row)
        resolved: list[dict[str, Any]] = []
        for rows in grouped.values():
            for index, original in enumerate(sorted(rows, key=lambda x: x["canonical_url"])):
                row = dict(original)
                if index:
                    suffix = hashlib.sha256(row["canonical_url"].encode()).hexdigest()[:12]
                    row["report_id"] = f"{row['report_id']}:{suffix}"
                resolved.append(row)
        return resolved

    def _date(self, pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, re.I)
        if not match:
            return None
        value = match.group(1).strip()
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
            try:
                return (
                    datetime.strptime(value, fmt)
                    .replace(tzinfo=UTC)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
            except ValueError:
                pass
        return value

    def _claims(
        self, report_id: str, parser: _AdvisoryParser, raw_ref: str
    ) -> list[dict[str, Any]]:
        patterns = [
            re.compile(
                r"\b(?:(?:likely|possible|suspected|assessed|potentially)\s+)?(?:(?:Chinese|Russian|Iranian|North Korean|DPRK|PRC)\s+)?(?:state-sponsored|state-linked|government-backed|nation-state|affiliated|associated)\s+(?:cyber\s+)?actors?\b",
                re.I,
            ),
            re.compile(
                r"\b(?:unnamed|unknown|unidentified|multiple|threat|malicious|ransomware|cyber)\s+actors?\b",
                re.I,
            ),
        ]
        claims: list[dict[str, Any]] = []
        for heading, block in parser.blocks:
            if block.startswith("#"):
                continue
            for pattern in patterns:
                for match in pattern.finditer(block):
                    raw = match.group(0)
                    before = block[max(0, match.start() - 80) : match.start()].lower()
                    combined = (before + raw.lower())[-140:]
                    modality = (
                        "negative"
                        if re.search(r"\b(?:not|no evidence|cannot)\b", combined)
                        else "comparison"
                        if re.search(r"\b(?:similar|consistent with|compared)\b", combined)
                        else "qualified"
                        if re.search(
                            r"\b(?:likely|possible|suspected|assessed|potentially|affiliated|associated)\b",
                            combined,
                        )
                        else "explicit"
                    )
                    excerpt = block[
                        max(0, match.start() - 100) : min(len(block), match.end() + 140)
                    ]
                    key = f"{report_id}|{heading}|{match.start()}|{raw}"
                    claims.append(
                        {
                            "candidate_id": "cisa:candidate:"
                            + hashlib.sha256(key.encode()).hexdigest(),
                            "report_id": report_id,
                            "raw_actor_text": raw,
                            "claim_excerpt": excerpt,
                            "section_heading": heading,
                            "character_start": None,
                            "character_end": None,
                            "claim_modality": modality,
                            "resolution_status": "unresolved",
                            "raw_ref": raw_ref,
                        }
                    )
        return claims

    def rebuild(self) -> dict[str, int]:
        advisories, claims, summaries = [], [], []
        attachment_rows = _read_jsonl(self.root / "raw/metadata/attachments.jsonl")
        attachments_by_report: dict[str, list[dict[str, Any]]] = {}
        for row in attachment_rows:
            attachments_by_report.setdefault(row["report_id"], []).append(row)
        for manifest in sorted(self._latest_manifests(), key=lambda x: x["report_id"]):
            raw_path = self.root / manifest["raw_html_ref"]
            parser = self._parse(raw_path.read_bytes())
            text = parser.text
            text_path = (
                self.root
                / "extracted/text"
                / f"{_safe_filename(manifest['report_id'].rsplit(':', 1)[-1])}.txt"
            )
            _atomic(text_path, text.encode())
            title = next(
                (h for h in parser.headings if h),
                " ".join("".join(parser.title_buf).split()).split(" | ")[0],
            )
            published = self._date(
                r"(?:Release Date|Published)?\s*:?\s*((?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})",
                text,
            )
            updated = self._date(
                r"(?:Last\s+(?:revised|updated)|Updated)\s*:?\s*((?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})",
                text,
            )
            refs = sorted(
                {
                    canonicalize_url(href, manifest["canonical_url"])
                    for href, _, heading in parser.links
                    if heading and "reference" in heading.lower()
                }
            )
            report_attachments = attachments_by_report.get(manifest["report_id"], [])
            known_attachment_urls = {x["source_url"] for x in report_attachments}
            for href, _, _ in parser.links:
                absolute = canonicalize_url(href, manifest["canonical_url"])
                extension = Path(urlsplit(absolute).path).suffix.lower()
                if (
                    extension in DOWNLOAD_EXTENSIONS
                    or "/sites/default/files/" in absolute
                    and extension
                ) and absolute not in known_attachment_urls:
                    pending = {
                        "attachment_id": self._attachment_id(manifest["report_id"], absolute),
                        "report_id": manifest["report_id"],
                        "source_url": absolute,
                        "final_url": absolute,
                        "filename": _safe_filename(urlsplit(absolute).path.rsplit("/", 1)[-1]),
                        "media_type": mimetypes.guess_type(absolute)[0],
                        "byte_size": 0,
                        "sha256": None,
                        "local_path": None,
                        "fetch_status": "failed",
                        "fetched_at": manifest["fetched_at"],
                        "error": "discovered but not collected",
                    }
                    attachment_rows.append(pending)
                    report_attachments.append(pending)
                    known_attachment_urls.add(absolute)
            report_claims = self._claims(manifest["report_id"], parser, manifest["raw_html_ref"])
            claims.extend(report_claims)
            summary_text = next(
                (
                    value
                    for heading, value in parser.blocks
                    if heading
                    and heading.lower() in {"summary", "executive summary"}
                    and not value.startswith("#")
                ),
                None,
            )
            organizations = sorted(
                set(
                    re.findall(
                        r"\b(?:CISA|FBI|NSA|USCG|DOE|EPA|NCSC-[A-Z]{2}|CERT-[A-Z]{2})\b", text
                    )
                )
            )
            advisories.append(
                {
                    "report_id": manifest["report_id"],
                    "source": "cisa_cybersecurity_advisory",
                    "source_record_id": manifest["source_record_id"],
                    "title": title,
                    "canonical_url": manifest["canonical_url"],
                    "published_at": published,
                    "updated_at": updated,
                    "issuing_organizations": organizations,
                    "summary": summary_text,
                    "content_text_ref": text_path.relative_to(self.root).as_posix(),
                    "reference_urls": refs,
                    "attachment_refs": [x["attachment_id"] for x in report_attachments],
                    "raw_html_ref": manifest["raw_html_ref"],
                    "raw_sha256": manifest["raw_sha256"],
                    "fetched_at": manifest["fetched_at"],
                    "normalization_version": NORMALIZATION_VERSION,
                }
            )
            non_reference = "\n".join(
                value
                for heading, value in parser.blocks
                if not heading or "reference" not in heading.lower()
            )
            domains = set(
                re.findall(
                    r"(?<![@\w-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}\b",
                    non_reference,
                    re.I,
                )
            )
            ips = {
                x
                for x in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", non_reference)
                if all(int(p) <= 255 for p in x.split("."))
            }
            urls = set(re.findall(r"https?://[^\s<>\]\)\"']+", non_reference))
            hashes = set(
                re.findall(r"\b(?:[a-f0-9]{32}|[a-f0-9]{40}|[a-f0-9]{64})\b", non_reference, re.I)
            )
            techniques = set(re.findall(r"\bT\d{4}(?:\.\d{3})?\b", text))
            sector_vocab = (
                "energy",
                "water",
                "healthcare",
                "communications",
                "government",
                "transportation",
                "financial",
                "manufacturing",
                "information technology",
            )
            summaries.append(
                {
                    "report_id": manifest["report_id"],
                    "section_headings": parser.headings,
                    "reference_count": len(refs),
                    "attachment_count": len(report_attachments),
                    "explicit_ioc_section_present": any(
                        re.search(r"indicators? of compromise|\biocs?\b", h, re.I)
                        for h in parser.headings
                    ),
                    "attack_technique_mentions_count": len(techniques),
                    "domain_candidate_count": len(domains),
                    "ip_candidate_count": len(ips),
                    "url_candidate_count": len(urls),
                    "hash_candidate_count": len(hashes),
                    "actor_claim_candidate_count": len(report_claims),
                    "target_or_sector_terms": [
                        term
                        for term in sector_vocab
                        if re.search(rf"\b{re.escape(term)}\b", text, re.I)
                    ],
                    "raw_ref": manifest["raw_html_ref"],
                }
            )
        attachment_rows = list({row["attachment_id"]: row for row in attachment_rows}.values())
        _write_jsonl(self.root / "normalized/advisories.jsonl", advisories)
        _write_jsonl(
            self.root / "normalized/attachments.jsonl",
            sorted(attachment_rows, key=lambda x: x["attachment_id"]),
        )
        _write_jsonl(
            self.root / "normalized/source_actor_claim_candidates.jsonl",
            sorted(claims, key=lambda x: x["candidate_id"]),
        )
        _write_jsonl(self.root / "normalized/advisory_observation_summaries.jsonl", summaries)
        return {
            "advisories": len(advisories),
            "attachments": len(attachment_rows),
            "claims": len(claims),
            "summaries": len(summaries),
        }

    def validate(self) -> dict[str, Any]:
        errors, rows = [], _read_jsonl(self.root / "normalized/advisories.jsonl")
        required = {
            "report_id",
            "source",
            "source_record_id",
            "title",
            "canonical_url",
            "published_at",
            "updated_at",
            "issuing_organizations",
            "summary",
            "content_text_ref",
            "reference_urls",
            "attachment_refs",
            "raw_html_ref",
            "raw_sha256",
            "fetched_at",
            "normalization_version",
        }
        ids = [row.get("report_id") for row in rows]
        if len(ids) != len(set(ids)):
            errors.append("duplicate report_id")
        for row in rows:
            if not required <= row.keys():
                errors.append(f"missing fields: {row.get('report_id')}")
            raw = self.root / row["raw_html_ref"]
            if (
                not raw.is_file()
                or hashlib.sha256(raw.read_bytes()).hexdigest() != row["raw_sha256"]
            ):
                errors.append(f"raw reference/hash invalid: {row['report_id']}")
            if row.get("content_text_ref") and not (self.root / row["content_text_ref"]).is_file():
                errors.append(f"text reference invalid: {row['report_id']}")
        attachment_rows = _read_jsonl(self.root / "normalized/attachments.jsonl")
        attachment_ids = {x["attachment_id"] for x in attachment_rows}
        terminal_statuses = {"success", "not_found", "blocked", "failed"}
        for attachment in attachment_rows:
            if attachment.get("fetch_status") not in terminal_statuses:
                errors.append(f"non-terminal attachment: {attachment.get('attachment_id')}")
            if attachment.get("fetch_status") == "success":
                local_path = attachment.get("local_path")
                local = self.root / local_path if isinstance(local_path, str) else None
                if (
                    local is None
                    or not local.is_file()
                    or hashlib.sha256(local.read_bytes()).hexdigest() != attachment.get("sha256")
                ):
                    errors.append(
                        f"attachment reference/hash invalid: {attachment['attachment_id']}"
                    )
        for row in rows:
            if not set(row["attachment_refs"]) <= attachment_ids:
                errors.append(f"attachment reference invalid: {row['report_id']}")
        result = {
            "valid": not errors,
            "checked_advisories": len(rows),
            "errors": errors,
            "validated_at": utc_now(),
        }
        _write_json(self.root / "reports/validation_report.json", result)
        return result

    def report(self) -> dict[str, Any]:
        advisories = _read_jsonl(self.root / "normalized/advisories.jsonl")
        attachments = _read_jsonl(self.root / "normalized/attachments.jsonl")
        claims = _read_jsonl(self.root / "normalized/source_actor_claim_candidates.jsonl")
        summaries = _read_jsonl(self.root / "normalized/advisory_observation_summaries.jsonl")
        manifest = _read_jsonl(self.root / "manifests/advisory_manifest.jsonl")
        checkpoint_path = self.root / "checkpoints/collection_state.json"
        checkpoint = (
            json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if checkpoint_path.exists()
            else {"entries": {}}
        )
        claim_counts = Counter(x["report_id"] for x in claims)
        attachment_failures = sum(x["fetch_status"] != "success" for x in attachments)
        report = {
            "source_url": self.listing_url,
            "collection_time": checkpoint.get("completed_at"),
            "urls_discovered": len(checkpoint.get("entries", {})),
            "advisories_successfully_saved": len(advisories),
            "page_versions": len(manifest),
            "changed_page_versions": sum(x["status"] == "versioned" for x in manifest),
            "attachment_total": len(attachments),
            "attachment_types": dict(
                sorted(Counter(x.get("media_type") or "unknown" for x in attachments).items())
            ),
            "recovered_errors": 0,
            "permanent_errors": attachment_failures
            + sum(
                x.get("status") == "permanent_failure"
                for x in checkpoint.get("entries", {}).values()
            ),
            "attachment_statuses": dict(
                sorted(Counter(x["fetch_status"] for x in attachments).items())
            ),
            "actor_claim_candidate_count": len(claims),
            "multi_actor_advisory_count": sum(value > 1 for value in claim_counts.values()),
            "advisories_without_explicit_actor_wording": len(advisories) - len(claim_counts),
            "advisories_with_ioc_sections": sum(
                x["explicit_ioc_section_present"] for x in summaries
            ),
            "publication_date_coverage": sum(bool(x["published_at"]) for x in advisories),
            "update_date_coverage": sum(bool(x["updated_at"]) for x in advisories),
            "storage_size": sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file()),
            "known_source_limitations": [
                "CISA may block non-browser clients at its CDN edge.",
                "Source dates are report metadata, not attack occurrence dates.",
                "Actor and IOC observations are conservative lexical candidates.",
            ],
            "generated_at": utc_now(),
        }
        _write_json(self.root / "reports/collection_report.json", report)
        _atomic(
            self.root / "reports/collection_report.md",
            (
                "# CISA Cybersecurity Advisory Collection Report\n\n"
                + "\n".join(
                    f"- **{key}**: `{json.dumps(value, ensure_ascii=False)}`"
                    for key, value in report.items()
                )
                + "\n"
            ).encode(),
        )
        return report
