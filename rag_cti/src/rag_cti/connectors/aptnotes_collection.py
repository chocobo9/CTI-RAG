"""Reproducible, source-faithful collection of the APTnotes report corpus."""

from __future__ import annotations

import csv
import hashlib
import html.parser
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx

REPOSITORY_URL = "https://github.com/aptnotes/data.git"
PINNED_COMMIT = "8595fbdee6747be9e9f730fd0bacd247157314df"
NORMALIZATION_VERSION = "aptnotes-v1"
RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}
BLOCKED_STATUSES = {401, 403, 407, 451}
TERMINAL_STATUSES = {"success", "not_found", "blocked", "failed"}
INDEX_FIELDS = ("Filename", "Title", "Source", "Link", "SHA-1", "Date", "Year")


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _write_json(path: Path, value: Any) -> None:
    _write_atomic(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    body = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    _write_atomic(path, body.encode())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def simhash64(text: str) -> str:
    weights = [0] * 64
    for token, count in Counter(re.findall(r"[\w-]+", normalize_text(text))).items():
        value = int.from_bytes(hashlib.sha256(token.encode()).digest()[:8], "big")
        for bit in range(64):
            weights[bit] += count if value & (1 << bit) else -count
    result = sum(1 << bit for bit, weight in enumerate(weights) if weight >= 0)
    return f"{result:016x}"


def detect_media_type(content: bytes, header: str | None) -> tuple[str, str | None]:
    head = content[:512].lstrip().lower()
    if content.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"
    if content.startswith(b"PK\x03\x04"):
        return "application/zip", ".zip"
    if content.startswith(b"\xd0\xcf\x11\xe0"):
        return "application/x-ole-storage", None
    if head.startswith((b"<!doctype html", b"<html")):
        return "text/html", ".html"
    media = (header or "").split(";", 1)[0].strip().lower()
    extensions = {"text/html": ".html", "text/plain": ".txt", "application/pdf": ".pdf"}
    return media or "application/octet-stream", extensions.get(media)


@dataclass(frozen=True)
class IndexRecord:
    source_record_index: int
    duplicate_occurrence: int
    filename: str
    title: str
    publisher: str
    url: str
    expected_sha1: str
    listed_date: str
    listed_year: str
    raw: dict[str, Any]


def _identity_payload(record: IndexRecord) -> str:
    stable = {key: record.raw.get(key) for key in INDEX_FIELDS}
    return json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_report_id(record: IndexRecord) -> str:
    identity = f"{_identity_payload(record)}|occurrence={record.duplicate_occurrence}"
    return "aptnotes:report:" + hashlib.sha256(identity.encode()).hexdigest()


class Transport(Protocol):
    def get(self, url: str, **kwargs: Any) -> httpx.Response: ...


class _TextHTMLParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


class AptnotesCollector:
    """Collect, rebuild, validate, and report the pinned APTnotes corpus."""

    def __init__(
        self,
        root: Path,
        *,
        transport: Transport | None = None,
        timeout: float = 30.0,
        attempts: int = 3,
        rate_delay: float = 1.0,
        max_bytes: int = 200 * 1024 * 1024,
    ) -> None:
        self.root = Path(root)
        self.transport = transport or httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": "rag-cti-aptnotes-collector/1.0 (+https://github.com/aptnotes/data)"},
        )
        self.attempts = max(1, attempts)
        self.rate_delay = max(0.0, rate_delay)
        self.max_bytes = max_bytes
        for directory in (
            "raw", "raw/documents", "raw/external_html", "extracted/text", "normalized",
            "manifests", "checkpoints", "logs", "reports",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def snapshot(self, source_repo: Path | None = None) -> dict[str, Any]:
        repository = self.root / "raw/repository"
        if source_repo is None:
            if (repository / ".git").exists():
                source_repo = repository
            else:
                clone_cache = self.root / "checkpoints/repository_clone"
                if not (clone_cache / ".git").exists():
                    subprocess.run(["git", "clone", REPOSITORY_URL, str(clone_cache)], check=True)
                source_repo = clone_cache
        source_repo = Path(source_repo)
        subprocess.run(["git", "-C", str(source_repo), "fetch", "origin", PINNED_COMMIT], check=True)
        subprocess.run(["git", "-C", str(source_repo), "checkout", "--detach", PINNED_COMMIT], check=True)
        if source_repo.resolve() != repository.resolve():
            repository.mkdir(parents=True, exist_ok=True)
            for name in ("APTnotes.json", "APTnotes.csv", "README.md"):
                shutil.copy2(source_repo / name, repository / name)
            bundle = (repository / "aptnotes-data.bundle").resolve()
            subprocess.run(["git", "-C", str(source_repo), "bundle", "create", str(bundle), "--all"], check=True)
        commit = subprocess.check_output(["git", "-C", str(source_repo), "rev-parse", "HEAD"], text=True).strip()
        tree = subprocess.check_output(["git", "-C", str(source_repo), "rev-parse", "HEAD^{tree}"], text=True).strip()
        if commit != PINNED_COMMIT:
            raise RuntimeError(f"snapshot commit mismatch: {commit}")
        manifest = {
            "source": "aptnotes", "repository_url": REPOSITORY_URL, "repository_commit": commit,
            "repository_tree": tree, "snapshot_path": "raw/repository", "snapshot_at": utc_now(),
            "python_version": sys.version, "git_version": subprocess.check_output(["git", "--version"], text=True).strip(),
            "files": {
                name: {"sha256": _sha256(repository / name), "byte_size": (repository / name).stat().st_size}
                for name in ("APTnotes.json", "APTnotes.csv", "README.md")
            },
        }
        _write_json(self.root / "manifests/repository_snapshot.json", manifest)
        return manifest

    def records(self) -> list[IndexRecord]:
        path = self.root / "raw/repository/APTnotes.json"
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(document, list):
            raise ValueError("APTnotes.json must contain an array")
        occurrences: Counter[str] = Counter()
        records: list[IndexRecord] = []
        for index, raw in enumerate(document):
            if not isinstance(raw, dict):
                self._error("malformed_metadata", None, f"row {index} is not an object", permanent=True)
                continue
            payload = json.dumps({k: raw.get(k) for k in INDEX_FIELDS}, ensure_ascii=False, sort_keys=True)
            occurrence = occurrences[payload]
            occurrences[payload] += 1
            records.append(IndexRecord(
                index, occurrence, str(raw.get("Filename") or ""), str(raw.get("Title") or ""),
                str(raw.get("Source") or ""), str(raw.get("Link") or ""), str(raw.get("SHA-1") or "").lower(),
                str(raw.get("Date") or ""), str(raw.get("Year") or ""), raw,
            ))
        return records

    def inspect(self) -> dict[str, Any]:
        records = self.records()
        malformed: list[dict[str, Any]] = []
        for record in records:
            missing = [key for key in INDEX_FIELDS if not str(record.raw.get(key) or "").strip()]
            try:
                parsed = datetime.strptime(record.listed_date, "%m/%d/%Y")
                if str(parsed.year) != record.listed_year:
                    missing.append("Date/Year mismatch")
            except ValueError:
                missing.append("invalid Date")
            if not re.fullmatch(r"[0-9a-f]{40}", record.expected_sha1):
                missing.append("invalid SHA-1")
            if missing:
                malformed.append({"source_record_index": record.source_record_index, "problems": missing})
        csv_path = self.root / "raw/repository/APTnotes.csv"
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            csv_rows = list(csv.DictReader(handle))
        differences = [i for i in range(max(len(csv_rows), len(records))) if i >= len(csv_rows) or i >= len(records) or any(str(csv_rows[i].get(k, "")) != str(records[i].raw.get(k, "")) for k in INDEX_FIELDS)]
        result = {
            "repository_commit": self._commit(), "index_records": len(records), "csv_records": len(csv_rows),
            "csv_json_difference_rows": differences, "malformed_metadata": malformed,
            "exact_duplicate_row_groups": sum(count > 1 for count in Counter(_identity_payload(r) for r in records).values()),
            "exact_sha1_duplicate_groups": sum(count > 1 for count in Counter(r.expected_sha1 for r in records).values()),
        }
        _write_json(self.root / "manifests/index_inspection.json", result)
        return result

    def _commit(self) -> str:
        path = self.root / "manifests/repository_snapshot.json"
        return str(json.loads(path.read_text(encoding="utf-8"))["repository_commit"])

    def _request(self, url: str) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self.transport.get(url)
                if response.status_code not in RETRYABLE_STATUSES:
                    return response
                last = RuntimeError(f"temporary HTTP {response.status_code}")
            except (httpx.TransportError, TimeoutError) as exc:
                last = exc
            if attempt + 1 < self.attempts:
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"request failed after {self.attempts} attempts: {last}")

    def _download(self, record: IndexRecord, report_id: str) -> dict[str, Any]:
        fetched_at = utc_now()
        page = self._request(record.url)
        if page.status_code in BLOCKED_STATUSES:
            return {"status": "blocked", "http_status": page.status_code, "fetched_at": fetched_at, "error": "access restricted"}
        if page.status_code in {404, 410}:
            return {"status": "not_found", "http_status": page.status_code, "fetched_at": fetched_at, "error": "share not found"}
        page.raise_for_status()
        if len(page.content) > self.max_bytes:
            raise ValueError("preview exceeds maximum response size")
        match = re.search(r"Box\.postStreamData\s*=\s*(\{.*?\})\s*;\s*</script>", page.text, re.S)
        if not match:
            html_path = self.root / "raw/external_html" / f"{report_id.rsplit(':', 1)[-1]}.html"
            _write_atomic(html_path, page.content)
            return {"status": "failed", "http_status": page.status_code, "fetched_at": fetched_at, "error": "Box download metadata unavailable", "html_snapshot_ref": html_path.relative_to(self.root).as_posix()}
        stream = json.loads(match.group(1))
        shared = stream.get("/app-api/enduserapp/shared-item", {})
        shared_name, item_id = shared.get("sharedName"), shared.get("itemID")
        if not shared_name or not item_id or shared.get("itemType") != "file":
            raise ValueError("Box share is not a downloadable file")
        download_url = f"https://app.box.com/index.php?rm=box_download_shared_file&shared_name={shared_name}&file_id=f_{item_id}"
        response = self._request(download_url)
        if response.status_code in BLOCKED_STATUSES:
            return {"status": "blocked", "http_status": response.status_code, "fetched_at": fetched_at, "error": "download restricted"}
        if response.status_code in {404, 410}:
            return {"status": "not_found", "http_status": response.status_code, "fetched_at": fetched_at, "error": "download not found"}
        response.raise_for_status()
        content = response.content
        if len(content) > self.max_bytes:
            raise ValueError("document exceeds maximum response size")
        media_type, extension = detect_media_type(content, response.headers.get("content-type"))
        if media_type == "text/html":
            destination = self.root / "raw/external_html" / f"{report_id.rsplit(':', 1)[-1]}.html"
            role = "html_snapshot"
        else:
            destination = self.root / "raw/documents" / f"{report_id.rsplit(':', 1)[-1]}{extension or ''}"
            role = "original_download"
        sha1 = hashlib.sha1(content).hexdigest()
        sha256 = hashlib.sha256(content).hexdigest()
        _write_atomic(destination, content)
        return {
            "status": "success", "http_status": response.status_code, "fetched_at": fetched_at,
            "local_path": destination.relative_to(self.root).as_posix(), "media_type": media_type,
            "file_extension": extension, "byte_size": len(content), "sha1": sha1, "sha256": sha256,
            "checksum_status": "match" if sha1 == record.expected_sha1 else "mismatch",
            "final_url": str(response.url), "source_url": record.url, "artifact_role": role,
        }

    def collect(self, *, indices: set[int] | None = None, limit: int | None = None) -> dict[str, Any]:
        records = [r for r in self.records() if indices is None or r.source_record_index in indices]
        if limit is not None:
            records = records[:limit]
        checkpoint_path = self.root / "checkpoints/collection_state.json"
        state: dict[str, Any] = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {"reports": {}, "started_at": utc_now()}
        report_states: dict[str, dict[str, Any]] = state["reports"]
        state["repository_commit"] = self._commit()
        for record in records:
            report_id = canonical_report_id(record)
            current = report_states.get(report_id, {})
            local_ref = current.get("local_path")
            if current.get("status") == "success" and isinstance(local_ref, str) and (self.root / local_ref).exists() and current.get("sha256") == _sha256(self.root / local_ref):
                continue
            try:
                outcome = self._download(record, report_id)
            except Exception as exc:
                outcome = {"status": "failed", "error": str(exc), "fetched_at": utc_now(), "http_status": None}
            outcome.update({"source_record_index": record.source_record_index, "attempts": current.get("attempts", 0) + 1})
            report_states[report_id] = outcome
            if outcome["status"] != "success":
                self._error("collection_failure", report_id, str(outcome.get("error")), permanent=True, extra=outcome)
            state["updated_at"] = utc_now()
            _write_json(checkpoint_path, state)
            time.sleep(self.rate_delay)
        state["completed_at"] = utc_now()
        _write_json(checkpoint_path, state)
        return state

    def _error(self, kind: str, report_id: str | None, message: str, *, permanent: bool, extra: dict[str, Any] | None = None) -> None:
        path = self.root / "manifests/errors.jsonl"
        rows = self.read_jsonl(path)
        key = (kind, report_id, message)
        if not any((r.get("error_kind"), r.get("report_id"), r.get("message")) == key for r in rows):
            rows.append({"error_kind": kind, "report_id": report_id, "message": message, "permanent": permanent, "recorded_at": utc_now(), "details": extra or {}})
            _write_jsonl(path, rows)

    def _extract(self, report_id: str, artifact: dict[str, Any]) -> tuple[str | None, str, int | None, str | None]:
        path = self.root / artifact["local_path"]
        media = artifact["media_type"]
        text, pages, tool = "", None, None
        try:
            if media == "application/pdf":
                import pymupdf

                chunks: list[str] = []
                with pymupdf.open(str(path)) as document:  # type: ignore[no-untyped-call]
                    pages = len(document)
                    for number, page in enumerate(document, 1):
                        chunks.append(f"\n\n--- PAGE {number} ---\n\n{page.get_text('text')}")
                text, tool = "".join(chunks).strip(), f"PyMuPDF {getattr(pymupdf, '__version__', 'unknown')}"
            elif media == "text/html":
                parser = _TextHTMLParser()
                parser.feed(path.read_text(encoding="utf-8", errors="replace"))
                text, tool = "\n".join(parser.parts), "stdlib.html.parser"
            elif media == "text/plain":
                text, tool = path.read_text(encoding="utf-8", errors="replace"), "stdlib"
            else:
                return None, "unsupported", None, None
            status = "success" if text.strip() else "empty"
            ref = f"extracted/text/{report_id.rsplit(':', 1)[-1]}.txt"
            _write_atomic(self.root / ref, text.encode())
            return ref, status, pages, tool
        except Exception as exc:
            self._error("text_extraction_failure", report_id, str(exc), permanent=False)
            return None, "failed", pages, tool

    def _actor_candidates(self, report_id: str, text: str, text_ref: str) -> list[dict[str, Any]]:
        pattern = re.compile(
            r"(?P<excerpt>"
            r"(?i:(?:(?:possibly|likely|reportedly|not)\s+)?"
            r"(?:attributed|linked|associated)\s+(?:the\s+)?"
            r"(?:activity|campaign|attacks?|operation)?\s*(?:to|with)\s+)"
            r"(?P<actor>[A-Z][A-Za-z0-9_-]*(?:\s+(?:[A-Z][A-Za-z0-9_-]*|Group|Team)){0,5}))"
        )
        rows: list[dict[str, Any]] = []
        for match in pattern.finditer(text):
            actor = match.group("actor").strip(" .,:;\n")
            if not actor or len(actor.split()) > 10:
                continue
            start, end = match.span("actor")
            page = text[:start].count("--- PAGE ") or None
            identity = f"{report_id}|{start}|{end}|{actor}"
            rows.append({
                "candidate_id": "aptnotes:candidate:" + hashlib.sha256(identity.encode()).hexdigest(),
                "report_id": report_id, "raw_actor_text": actor,
                "claim_excerpt": text[max(0, match.start() - 100):min(len(text), match.end() + 100)].replace("\n", " "),
                "document_ref": text_ref, "page": page, "section": None,
                "character_start": start, "character_end": end, "extraction_method": "explicit_pattern",
                "resolution_status": "unresolved", "candidate_actor_ids": [], "raw_ref": text_ref,
            })
        return rows

    def rebuild(self) -> dict[str, int]:
        records = self.records()
        checkpoint_path = self.root / "checkpoints/collection_state.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {"reports": {}}
        commit = self._commit()
        reports: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        features: list[dict[str, Any]] = []
        for record in records:
            report_id = canonical_report_id(record)
            state = checkpoint["reports"].get(report_id, {})
            artifact_refs: list[str] = []
            text, text_ref, pages = "", None, None
            if state.get("status") == "success" and state.get("local_path") and (self.root / state["local_path"]).exists():
                artifact_id = "aptnotes:artifact:" + hashlib.sha256(f"{report_id}|{state['local_path']}".encode()).hexdigest()
                text_ref, extraction_status, pages, tool = self._extract(report_id, state)
                artifact_refs.append(artifact_id)
                artifacts.append({
                    "artifact_id": artifact_id, "report_id": report_id, "artifact_role": state.get("artifact_role", "original_download"),
                    "source_url": record.url, "final_url": state.get("final_url"), "local_path": state["local_path"],
                    "media_type": state.get("media_type"), "file_extension": state.get("file_extension"),
                    "byte_size": state.get("byte_size"), "sha256": state.get("sha256"), "expected_sha1": record.expected_sha1,
                    "actual_sha1": state.get("sha1"), "checksum_verification_status": state.get("checksum_status"),
                    "fetch_status": "success", "http_status": state.get("http_status"),
                    "text_extraction_status": extraction_status, "extracted_text_ref": text_ref,
                    "extraction_tool": tool, "extraction_detail": "embedded text only; OCR disabled", "fetched_at": state.get("fetched_at"),
                })
                if text_ref:
                    text = (self.root / text_ref).read_text(encoding="utf-8")
                    candidates.extend(self._actor_candidates(report_id, text, text_ref))
            status = state.get("status")
            document_status = "fetched_external" if status == "success" else ("failed" if status in TERMINAL_STATUSES else "metadata_only")
            reports.append({
                "report_id": report_id, "source": "aptnotes", "repository_path": "APTnotes.json",
                "repository_commit": commit, "source_record_index": record.source_record_index,
                "duplicate_occurrence": record.duplicate_occurrence, "source_filename": record.filename,
                "title": record.title or None, "listed_date": record.listed_date or None,
                "listed_date_raw": record.listed_date or None, "listed_year": record.listed_year or None,
                "publisher": record.publisher or None, "original_url": record.url or None,
                "archived_document_refs": artifact_refs, "document_status": document_status,
                "raw_metadata_ref": "raw/repository/APTnotes.json", "fetched_at": state.get("fetched_at"),
                "normalization_version": NORMALIZATION_VERSION,
            })
            normalized = normalize_text(text) if text else ""
            features.append({
                "report_id": report_id, "title_normalized": normalize_text(record.title) or None,
                "document_sha256s": [state["sha256"]] if state.get("sha256") else [],
                "exact_text_sha256": hashlib.sha256(text.encode()).hexdigest() if text else None,
                "normalized_text_sha256": hashlib.sha256(normalized.encode()).hexdigest() if normalized else None,
                "simhash_or_minhash": simhash64(normalized) if normalized else None,
                "reference_urls_normalized": [normalize_url(record.url)] if record.url else [],
                "document_length_chars": len(text) if text else None, "document_page_count": pages,
                "listed_publisher_normalized": normalize_text(record.publisher) or None,
            })
        _write_jsonl(self.root / "normalized/reports.jsonl", reports)
        _write_jsonl(self.root / "normalized/document_artifacts.jsonl", artifacts)
        _write_jsonl(self.root / "normalized/source_actor_claim_candidates.jsonl", candidates)
        _write_jsonl(self.root / "normalized/report_matching_features.jsonl", features)
        _write_jsonl(self.root / "manifests/document_manifest.jsonl", artifacts)
        return {"reports": len(reports), "artifacts": len(artifacts), "actor_candidates": len(candidates), "features": len(features)}

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        reports = self.read_jsonl(self.root / "normalized/reports.jsonl")
        artifacts = self.read_jsonl(self.root / "normalized/document_artifacts.jsonl")
        features = self.read_jsonl(self.root / "normalized/report_matching_features.jsonl")
        expected = len(self.records())
        if len(reports) != expected:
            errors.append(f"report count {len(reports)} != index count {expected}")
        ids = [r["report_id"] for r in reports]
        if len(ids) != len(set(ids)):
            errors.append("duplicate report_id")
        if len(features) != expected:
            errors.append("matching feature count mismatch")
        known = set(ids)
        for artifact in artifacts:
            path = self.root / artifact["local_path"]
            if artifact["report_id"] not in known:
                errors.append(f"orphan artifact {artifact['artifact_id']}")
            elif not path.exists():
                errors.append(f"missing artifact {artifact['local_path']}")
            elif _sha256(path) != artifact["sha256"]:
                errors.append(f"artifact hash mismatch {artifact['local_path']}")
            text_ref = artifact.get("extracted_text_ref")
            if text_ref and not (self.root / text_ref).exists():
                errors.append(f"missing extracted text {text_ref}")
        checkpoint_path = self.root / "checkpoints/collection_state.json"
        if checkpoint_path.exists():
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            unexplained = [rid for rid, state in checkpoint.get("reports", {}).items() if state.get("status") not in TERMINAL_STATUSES]
            if unexplained:
                errors.append(f"nonterminal checkpoint entries: {len(unexplained)}")
        result = {"valid": not errors, "repository_commit": self._commit(), "checked_reports": len(reports), "checked_artifacts": len(artifacts), "errors": errors, "validated_at": utc_now()}
        _write_json(self.root / "reports/validation_report.json", result)
        return result

    def report(self) -> dict[str, Any]:
        reports = self.read_jsonl(self.root / "normalized/reports.jsonl")
        artifacts = self.read_jsonl(self.root / "normalized/document_artifacts.jsonl")
        candidates = self.read_jsonl(self.root / "normalized/source_actor_claim_candidates.jsonl")
        errors = self.read_jsonl(self.root / "manifests/errors.jsonl")
        checkpoint_path = self.root / "checkpoints/collection_state.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {"reports": {}}
        statuses = Counter(s.get("status") for s in checkpoint.get("reports", {}).values())
        media = Counter(a.get("media_type") for a in artifacts)
        extraction = Counter(a.get("text_extraction_status") for a in artifacts)
        sha_groups = Counter(a["sha256"] for a in artifacts)
        title_groups = Counter(normalize_text(r.get("title") or "") for r in reports)
        candidate_counts = Counter(c["report_id"] for c in candidates)
        report = {
            "repository_commit": self._commit(), "total_index_records": len(reports),
            "total_local_artifacts": len(artifacts), "successful_external_downloads": statuses["success"],
            "html_snapshots": media["text/html"], "unavailable_urls": statuses["not_found"],
            "blocked_urls": statuses["blocked"], "failed_urls": statuses["failed"],
            "format_counts": {"pdf": media["application/pdf"], "html": media["text/html"], "other": len(artifacts) - media["application/pdf"] - media["text/html"]},
            "text_extraction_counts": dict(sorted(extraction.items())),
            "exact_duplicate_byte_groups": sum(count > 1 for count in sha_groups.values()),
            "duplicate_looking_title_groups": sum(count > 1 for title, count in title_groups.items() if title),
            "reports_with_actor_claim_candidates": len(candidate_counts),
            "reports_with_multiple_actor_candidates": sum(count > 1 for count in candidate_counts.values()),
            "reports_without_actor_candidates": len(reports) - len(candidate_counts),
            "total_storage_bytes": sum(p.stat().st_size for p in (self.root / "raw").rglob("*") if p.is_file()),
            "malformed_metadata": json.loads((self.root / "manifests/index_inspection.json").read_text(encoding="utf-8")).get("malformed_metadata", []) if (self.root / "manifests/index_inspection.json").exists() else [],
            "known_corpus_limitations": ["The pinned repository contains metadata only; report availability depends on public Box shares.", "OCR is disabled, so image-only documents have empty extracted text.", "Actor candidates are conservative text matches and remain unresolved."],
            "unresolved_failures": [e for e in errors if e.get("permanent")],
            "corpus_path": str(self.root.resolve()), "report_path": str((self.root / "reports/collection_report.md").resolve()),
            "generated_at": utc_now(),
        }
        _write_json(self.root / "reports/collection_report.json", report)
        md = "# APTnotes Collection Report\n\n" + "\n".join(f"- **{key}**: `{json.dumps(value, ensure_ascii=False)}`" for key, value in report.items()) + "\n"
        _write_atomic(self.root / "reports/collection_report.md", md.encode())
        return report

    def finalize(self) -> dict[str, Any]:
        inspection = self.inspect()
        rebuilt = self.rebuild()
        validation = self.validate()
        report = self.report()
        return {"inspection": inspection, "rebuild": rebuilt, "validation": validation, "report": report}
