"""Source-specific URLhaus and ThreatFox official export collectors."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import sqlite3
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import httpx

from rag_cti.connectors.source_collection_common import (
    atomic_write,
    canonical_json,
    now_utc,
    read_jsonl,
    sha256_bytes,
    stable_hash,
    write_json,
    write_jsonl,
)

SourceName = Literal["urlhaus", "threatfox"]


class AbuseExportCollector:
    def __init__(self, source: SourceName, root: Path | None = None) -> None:
        self.source = source
        self.root = root or Path("data") / source
        for path in (
            "raw/exports",
            "raw/inventories",
            "normalized",
            "manifests",
            "checkpoints",
            "logs",
            "reports",
        ):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        if source == "urlhaus":
            for path in ("raw/urls", "raw/payloads"):
                (self.root / path).mkdir(parents=True, exist_ok=True)
        else:
            for path in ("raw/iocs", "raw/malware"):
                (self.root / path).mkdir(parents=True, exist_ok=True)

    @property
    def official_url(self) -> str:
        return f"https://{self.source}.abuse.ch/"

    @property
    def export_host(self) -> str:
        return f"{self.source}-api.abuse.ch"

    @property
    def export_url(self) -> str:
        return f"https://{self.export_host}/v2/files/exports/<AUTH_KEY>/full.csv.zip"

    def _empty_outputs(self) -> None:
        names = (
            (
                "urls",
                "payloads",
                "url_payload_links",
                "source_malware_claims",
                "discovery_paths",
                "url_observation_summaries",
            )
            if self.source == "urlhaus"
            else (
                "iocs",
                "malware",
                "ioc_malware_links",
                "source_malware_claims",
                "source_actor_claims",
                "discovery_paths",
                "ioc_observation_summaries",
            )
        )
        for name in names:
            write_jsonl(self.root / "normalized" / f"{name}.jsonl", [])

    def mark_blocked(self) -> dict[str, Any]:
        timestamp = now_utc()
        self._empty_outputs()
        reason = (
            "ABUSECH_AUTH_KEY is required by the official Community API and exports but is not set."
        )
        error = {
            "error_kind": "missing_credential",
            "environment_variable": "ABUSECH_AUTH_KEY",
            "permanent": False,
            "message": reason,
            "recorded_at": timestamp,
        }
        write_jsonl(self.root / "manifests/errors.jsonl", [error])
        checkpoint = {
            "source": self.source,
            "status": "blocked_external_access",
            "open_entries": 0,
            "blocked_reason": reason,
            "updated_at": timestamp,
        }
        write_json(self.root / "checkpoints/collection_state.json", checkpoint)
        limitation = (
            "The selected full dump contains active URLs or URLs added within the past 90 days; it is not an all-time historical corpus."
            if self.source == "urlhaus"
            else "Expired IOCs older than six months are omitted from both API and exports since 2025-05-01."
        )
        snapshot = {
            "source": self.source,
            "snapshot_id": f"{self.source}-blocked-{timestamp.replace(':', '-')}",
            "collection_started_at": timestamp,
            "collection_completed_at": timestamp,
            "official_base_url": self.official_url,
            "api_documentation_url": self.official_url + "api/",
            "api_version_observed": "Community API v2 exports / v1 query API",
            "authentication_required": True,
            "credential_environment_variables": ["ABUSECH_AUTH_KEY"],
            "rate_limit_observed": None,
            "license_or_terms_url": "https://abuse.ch/terms/",
            "fair_use_constraints": [
                "Free Community API is governed by abuse.ch fair-use principles.",
                "Exports are generated every five minutes and must not be fetched more often than every five minutes.",
            ],
            "collection_methods": [],
            "endpoints_used": [],
            "exports_used": [],
            "coverage_window": {"start": None, "end": None, "basis": None},
            "known_coverage_limitations": [limitation],
            "inventory_count": 0,
            "collector_version": f"{self.source}-collector-v1",
            "normalization_version": f"{self.source}-v1",
            "status": "blocked_external_access",
        }
        if self.source == "threatfox":
            snapshot["expired_iocs_excluded"] = True
        else:
            snapshot["selected_export_coverage_type"] = "full: active or added within past 90 days"
        write_json(self.root / "manifests/source_snapshot.json", snapshot)
        result = self._report(status="blocked_external_access", unresolved=[reason])
        self._write_observed_schema(blocked=True)
        return result

    def collect(
        self, *, auth_key: str | None = None, reuse_archive: Path | None = None
    ) -> dict[str, Any]:
        key = auth_key or os.environ.get("ABUSECH_AUTH_KEY")
        if not key:
            return self.mark_blocked()
        started = now_utc()
        snapshot_id = (
            reuse_archive.parent.name
            if reuse_archive is not None
            else f"{self.source}-{started.replace(':', '-')}"
        )
        endpoint = f"https://{self.export_host}/v2/files/exports/{key}/full.csv.zip"
        archive_dir = self.root / "raw/exports" / snapshot_id
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive = reuse_archive or archive_dir / "full.csv.zip"
        temporary = archive.with_suffix(".zip.part")
        digest = hashlib.sha256()
        if reuse_archive is not None:
            if not archive.is_file():
                raise FileNotFoundError(archive)
            with archive.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            try:
                with httpx.stream(
                    "GET",
                    endpoint,
                    timeout=httpx.Timeout(180),
                    follow_redirects=True,
                    headers={"User-Agent": "rag-cti-source-collector/1.0"},
                ) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            digest.update(chunk)
                            handle.write(chunk)
                os.replace(temporary, archive)
            except Exception as exc:
                message = str(exc).replace(key, "<redacted>")
                write_jsonl(
                    self.root / "manifests/errors.jsonl",
                    [
                        {
                            "error_kind": "export_download_failure",
                            "message": message,
                            "permanent": False,
                            "recorded_at": now_utc(),
                        }
                    ],
                )
                raise RuntimeError(message) from None
        with zipfile.ZipFile(archive) as bundle:
            csv_names = [
                name
                for name in bundle.namelist()
                if name.lower().endswith((".csv", ".txt"))
            ]
            if not csv_names:
                raise RuntimeError("official archive contains no CSV-compatible member")
            extracted = self.root / "raw/inventories" / snapshot_id / Path(csv_names[0]).name
            extracted.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(csv_names[0]) as source_handle:
                atomic_write(extracted, source_handle.read())
        fetched_at = now_utc()
        raw_ref = archive.resolve().relative_to(self.root.resolve()).as_posix()
        archive_sha = digest.hexdigest()
        count = self._normalize_csv(extracted, raw_ref, archive_sha, fetched_at, snapshot_id)
        manifest = [
            {
                "source": self.source,
                "record_kind": "full_csv_export",
                "source_record_id": None,
                "raw_ref": raw_ref,
                "raw_sha256": archive_sha,
                "byte_size": archive.stat().st_size,
                "endpoint": f"https://{self.export_host}/v2/files/exports/<redacted>/full.csv.zip",
                "fetched_at": fetched_at,
                "snapshot_id": snapshot_id,
                "status": "created",
                "collector_version": f"{self.source}-collector-v1",
            }
        ]
        write_jsonl(self.root / "manifests/raw_manifest.jsonl", manifest)
        write_jsonl(self.root / "manifests/errors.jsonl", [])
        checkpoint = {
            "source": self.source,
            "status": "complete",
            "inventory_count": count,
            "normalization_complete": True,
            "updated_at": fetched_at,
            "open_entries": 0,
        }
        write_json(self.root / "checkpoints/collection_state.json", checkpoint)
        limitation = (
            "Full dump is active URLs or URLs added within 90 days."
            if self.source == "urlhaus"
            else "Expired IOCs older than six months are excluded from exports."
        )
        snapshot = {
            "source": self.source,
            "snapshot_id": snapshot_id,
            "collection_started_at": started,
            "collection_completed_at": fetched_at,
            "official_base_url": self.official_url,
            "api_documentation_url": self.official_url + "api/",
            "api_version_observed": "Community API v2 exports",
            "authentication_required": True,
            "credential_environment_variables": ["ABUSECH_AUTH_KEY"],
            "rate_limit_observed": None,
            "license_or_terms_url": "https://abuse.ch/terms/",
            "fair_use_constraints": ["Do not fetch exports more often than every five minutes."],
            "collection_methods": [f"{self.source}_full_export"],
            "endpoints_used": [],
            "exports_used": ["full.csv.zip"],
            "coverage_window": {"start": None, "end": fetched_at, "basis": limitation},
            "known_coverage_limitations": [limitation],
            "inventory_count": count,
            "collector_version": f"{self.source}-collector-v1",
            "normalization_version": f"{self.source}-v1",
            "status": "complete",
        }
        if self.source == "threatfox":
            snapshot["expired_iocs_excluded"] = True
        else:
            snapshot["selected_export_coverage_type"] = "full: active or added within past 90 days"
        write_json(self.root / "manifests/source_snapshot.json", snapshot)
        self._write_observed_schema(blocked=False)
        return self._report(status="complete", unresolved=[])

    def download_urlhaus_payload_export(self) -> dict[str, Any]:
        if self.source != "urlhaus":
            raise ValueError("payload export is URLhaus-specific")
        started = now_utc()
        snapshot_id = f"urlhaus-payloads-{started.replace(':', '-')}"
        endpoint = "https://urlhaus.abuse.ch/downloads/payloads/"
        archive_dir = self.root / "raw/exports" / snapshot_id
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive = archive_dir / "payloads.zip"
        temporary = archive.with_suffix(".zip.part")
        digest = hashlib.sha256()
        downloaded = 0
        checkpoint_path = self.root / "checkpoints/payload_collection_state.json"
        write_json(
            checkpoint_path,
            {
                "status": "running",
                "snapshot_id": snapshot_id,
                "downloaded_bytes": 0,
                "updated_at": started,
            },
        )
        with httpx.stream(
            "GET",
            endpoint,
            timeout=httpx.Timeout(600),
            follow_redirects=False,
            headers={"User-Agent": "rag-cti-source-collector/1.0"},
        ) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_bytes():
                    digest.update(chunk)
                    handle.write(chunk)
                    downloaded += len(chunk)
        os.replace(temporary, archive)
        state = {
            "status": "downloaded_pending_normalization",
            "snapshot_id": snapshot_id,
            "archive_ref": archive.relative_to(self.root).as_posix(),
            "archive_sha256": digest.hexdigest(),
            "downloaded_bytes": downloaded,
            "updated_at": now_utc(),
        }
        write_json(checkpoint_path, state)
        return state

    def normalize_urlhaus_payload_export(self) -> dict[str, Any]:
        if self.source != "urlhaus":
            raise ValueError("payload export is URLhaus-specific")
        archives = sorted((self.root / "raw/exports").rglob("payloads.zip"))
        if not archives:
            raise FileNotFoundError("URLhaus payload archive not found")
        archive = archives[-1]
        raw_ref = archive.relative_to(self.root).as_posix()
        archive_digest = hashlib.sha256()
        with archive.open("rb") as archive_handle:
            for archive_chunk in iter(lambda: archive_handle.read(1024 * 1024), b""):
                archive_digest.update(archive_chunk)
        archive_sha = archive_digest.hexdigest()
        snapshot_id = archive.parent.name
        fetched_at = now_utc()
        url_rows = [
            json.loads(line)
            for line in (self.root / "normalized/urls.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        url_ids = {row["url_raw"]: row["url_id"] for row in url_rows}
        work_db = self.root / "checkpoints/payload_normalization.sqlite3"
        state_path = self.root / "checkpoints/payload_normalization_state.json"
        links_path = self.root / "normalized/url_payload_links.jsonl"
        links_temp = links_path.with_suffix(".jsonl.part")
        prior_state = (
            json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        )
        can_resume = (
            prior_state.get("status") == "running" and work_db.exists() and links_temp.exists()
        )
        start_at = int(prior_state.get("processed_associations", 0)) if can_resume else 0
        if not can_resume:
            work_db.unlink(missing_ok=True)
            links_temp.unlink(missing_ok=True)
        connection = sqlite3.connect(work_db)
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;
            CREATE TABLE IF NOT EXISTS payloads (
              payload_id TEXT PRIMARY KEY, md5 TEXT, sha256 TEXT, filetype TEXT,
              signature TEXT, firstseen TEXT
            );
            CREATE TABLE IF NOT EXISTS claims (
              claim_id TEXT PRIMARY KEY, payload_id TEXT, signature TEXT
            );
            CREATE TABLE IF NOT EXISTS url_counts (
              url_id TEXT PRIMARY KEY, payload_count INTEGER NOT NULL
            );
            """
        )
        processed = start_at
        seen_rows = 0
        link_mode = "ab" if can_resume else "wb"
        with links_temp.open(link_mode) as links_handle, zipfile.ZipFile(archive) as bundle:
            member = next(
                name for name in bundle.namelist() if name.lower().endswith((".csv", ".txt"))
            )
            with bundle.open(member) as binary:
                text_handle = io.TextIOWrapper(
                    binary, encoding="utf-8-sig", errors="replace", newline=""
                )
                header: list[str] | None = None
                for line in text_handle:
                    if line.startswith("#"):
                        candidate = line.lstrip("#").strip()
                        if "," in candidate:
                            header = next(csv.reader([candidate]))
                        continue
                    if not line.strip():
                        continue
                    if header is None:
                        raise ValueError("payload export header not found")
                    seen_rows += 1
                    if seen_rows <= start_at:
                        continue
                    values = next(csv.reader([line]))
                    row = dict(zip(header, values, strict=False))
                    exact_url = row.get("url", "")
                    sha256 = row.get("sha256", "")
                    md5 = row.get("md5", "")
                    identity = sha256 or md5 or stable_hash(row)
                    payload_id = "urlhaus:payload:" + identity
                    url_id = url_ids.get(exact_url) or "urlhaus:url:sha256:" + sha256_bytes(
                        exact_url.encode()
                    )
                    raw_signature = row.get("signature") or ""
                    signature = (
                        None
                        if raw_signature.strip().lower() in {"", "none", "null", "n/a"}
                        else raw_signature
                    )
                    connection.execute(
                        "INSERT OR IGNORE INTO payloads VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            payload_id,
                            md5 or None,
                            sha256 or None,
                            row.get("filetype") or None,
                            signature,
                            row.get("firstseen") or None,
                        ),
                    )
                    connection.execute(
                        "INSERT INTO url_counts VALUES (?, 1) "
                        "ON CONFLICT(url_id) DO UPDATE SET payload_count=payload_count+1",
                        (url_id,),
                    )
                    link_id = "urlhaus:url-payload-link:" + stable_hash(
                        exact_url, payload_id, row.get("firstseen")
                    )
                    links_handle.write(
                        canonical_json(
                            {
                                "link_id": link_id,
                                "url_id": url_id,
                                "payload_id": payload_id,
                                "raw_url": exact_url,
                                "first_seen": row.get("firstseen") or None,
                                "source_relation_type": "urlhaus_payload_export",
                                "raw_ref": raw_ref,
                            }
                        )
                    )
                    if signature:
                        claim_id = "urlhaus:claim:" + stable_hash(payload_id, signature)
                        connection.execute(
                            "INSERT OR IGNORE INTO claims VALUES (?, ?, ?)",
                            (claim_id, payload_id, signature),
                        )
                    processed += 1
                    if processed % 100_000 == 0:
                        connection.commit()
                        links_handle.flush()
                        write_json(
                            state_path,
                            {
                                "status": "running",
                                "processed_associations": processed,
                                "updated_at": now_utc(),
                            },
                        )
        connection.commit()
        os.replace(links_temp, links_path)

        def stream_query(
            path: Path,
            query: str,
            builder: Any,
            prefix_rows: list[dict[str, Any]] | None = None,
        ) -> int:
            temporary = path.with_suffix(path.suffix + ".part")
            count = 0
            with temporary.open("wb") as handle:
                for prefix_row in prefix_rows or []:
                    handle.write(canonical_json(prefix_row))
                    count += 1
                for db_row in connection.execute(query):
                    handle.write(canonical_json(builder(db_row)))
                    count += 1
            os.replace(temporary, path)
            return count

        payload_count = stream_query(
            self.root / "normalized/payloads.jsonl",
            "SELECT payload_id, md5, sha256, filetype, signature, firstseen FROM payloads ORDER BY payload_id",
            lambda row: {
                "payload_id": row[0],
                "source": "urlhaus",
                "source_record_id": None,
                "md5": row[1],
                "sha256": row[2],
                "file_type_raw": row[3],
                "file_size": None,
                "signature_raw": row[4],
                "first_seen": row[5],
                "last_seen": None,
                "references_raw": [],
                "raw_ref": raw_ref,
                "raw_sha256": archive_sha,
                "fetched_at": fetched_at,
                "snapshot_id": snapshot_id,
                "normalization_version": "urlhaus-v1",
            },
        )
        existing_claims = read_jsonl(self.root / "normalized/source_malware_claims.jsonl")
        claim_count = stream_query(
            self.root / "normalized/source_malware_claims.jsonl",
            "SELECT claim_id, payload_id, signature FROM claims ORDER BY claim_id",
            lambda row: {
                "claim_id": row[0],
                "subject_record_id": row[1],
                "source_location": "payload.signature",
                "raw_label": row[2],
                "claim_kind": "payload_signature",
                "parse_status": "preserved_unresolved",
                "raw_ref": raw_ref,
            },
            existing_claims,
        )
        counts = dict(connection.execute("SELECT url_id, payload_count FROM url_counts"))
        connection.close()
        for row in url_rows:
            row["payload_count"] = counts.get(row["url_id"], 0)
        write_jsonl(self.root / "normalized/urls.jsonl", url_rows)
        summaries = [
            json.loads(line)
            for line in (self.root / "normalized/url_observation_summaries.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        for row in summaries:
            count = counts.get(row["url_id"], 0)
            row["has_payload"] = count > 0
            row["payload_count"] = count
        write_jsonl(self.root / "normalized/url_observation_summaries.jsonl", summaries)
        manifest = [
            json.loads(line)
            for line in (self.root / "manifests/raw_manifest.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        manifest.append(
            {
                "source": "urlhaus",
                "record_kind": "payload_export",
                "source_record_id": None,
                "raw_ref": raw_ref,
                "raw_sha256": archive_sha,
                "byte_size": archive.stat().st_size,
                "endpoint": "https://urlhaus.abuse.ch/downloads/payloads/",
                "fetched_at": fetched_at,
                "snapshot_id": snapshot_id,
                "status": "created",
                "collector_version": "urlhaus-collector-v1",
            }
        )
        write_jsonl(self.root / "manifests/raw_manifest.jsonl", manifest)
        state = {
            "status": "complete",
            "processed_associations": processed,
            "payload_records": payload_count,
            "malware_claims": claim_count,
            "updated_at": now_utc(),
        }
        write_json(state_path, state)
        snapshot_path = self.root / "manifests/source_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["collection_completed_at"] = state["updated_at"]
        snapshot["collection_methods"] = [
            "urlhaus_full_export",
            "urlhaus_collected_payload_export",
        ]
        snapshot["exports_used"] = ["full.csv.zip", "payloads.zip"]
        snapshot["payload_inventory_count"] = payload_count
        snapshot["url_payload_association_count"] = processed
        write_json(snapshot_path, snapshot)
        return state

    def clean_urlhaus_null_sentinels(self) -> dict[str, int]:
        if self.source != "urlhaus":
            raise ValueError("cleanup is URLhaus-specific")
        sentinel = {"none", "null", "n/a", ""}
        changed = 0
        for name in ("urls", "payloads"):
            path = self.root / "normalized" / f"{name}.jsonl"
            temporary = path.with_suffix(".jsonl.part")
            with path.open("r", encoding="utf-8") as source, temporary.open("wb") as target:
                for line in source:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if name == "urls":
                        before = row.get("tags_raw") or []
                        after = [tag for tag in before if str(tag).strip().lower() not in sentinel]
                        changed += len(before) - len(after)
                        row["tags_raw"] = after
                    elif str(row.get("signature_raw") or "").strip().lower() in sentinel:
                        changed += row.get("signature_raw") is not None
                        row["signature_raw"] = None
                    target.write(canonical_json(row))
            os.replace(temporary, path)
        claims = self.root / "normalized/source_malware_claims.jsonl"
        claims_temp = claims.with_suffix(".jsonl.part")
        removed_claims = 0
        with claims.open("r", encoding="utf-8") as source, claims_temp.open("wb") as target:
            for line in source:
                if not line.strip():
                    continue
                row = json.loads(line)
                if str(row.get("raw_label") or "").strip().lower() in sentinel:
                    removed_claims += 1
                    continue
                target.write(canonical_json(row))
        os.replace(claims_temp, claims)
        return {"changed_values": changed, "removed_claims": removed_claims}

    def rebuild(self) -> dict[str, int]:
        csv_files = sorted(
            path
            for path in (self.root / "raw/inventories").rglob("*")
            if path.is_file() and path.suffix.lower() in {".csv", ".txt"}
        )
        if not csv_files:
            self._empty_outputs()
            return {"records": 0}
        csv_path = csv_files[-1]
        manifest_path = self.root / "manifests/raw_manifest.jsonl"
        manifest_rows = []
        if manifest_path.exists():
            manifest_rows = [
                json.loads(line)
                for line in manifest_path.read_text(encoding="utf-8").splitlines()
                if line
            ]
        if manifest_rows:
            item = manifest_rows[-1]
            raw_ref = item["raw_ref"]
            raw_sha = item["raw_sha256"]
            fetched = item["fetched_at"]
            snapshot = item["snapshot_id"]
        else:
            raw_ref = csv_path.relative_to(self.root).as_posix()
            raw_sha = sha256_bytes(csv_path.read_bytes())
            fetched = now_utc()
            snapshot = csv_path.parent.name
        count = self._normalize_csv(csv_path, raw_ref, raw_sha, fetched, snapshot)
        result: dict[str, int] = {"records": count}
        if self.source == "urlhaus" and any(
            (self.root / "raw/exports").rglob("payloads.zip")
        ):
            payload_result = self.normalize_urlhaus_payload_export()
            result["payload_records"] = int(payload_result["payload_records"])
            result["url_payload_links"] = int(payload_result["processed_associations"])
        return result

    def report(self) -> dict[str, Any]:
        checkpoint = self.root / "checkpoints/collection_state.json"
        status = "missing"
        if checkpoint.exists():
            status = json.loads(checkpoint.read_text(encoding="utf-8")).get("status", "missing")
        return self._report(status=status, unresolved=[])

    def _rows(self, csv_path: Path) -> list[dict[str, str]]:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            header: str | None = None
            data_lines: list[str] = []
            for line in handle:
                if line.startswith("#"):
                    candidate = line.lstrip("#").strip()
                    if "," in candidate:
                        header = candidate
                    continue
                if line.strip():
                    if header is None:
                        header = line.strip()
                        continue
                    data_lines.append(line)
            if header is None:
                raise ValueError(f"export header not found in {csv_path.name}")
            return list(csv.DictReader([header + "\n", *data_lines], skipinitialspace=True))

    @staticmethod
    def _value(row: dict[str, str], *names: str) -> str | None:
        lowered = {
            key.strip().lstrip("#").lower(): value for key, value in row.items() if key is not None
        }
        for name in names:
            value = lowered.get(name.lower())
            if value is not None and value != "" and value.strip().lower() not in {
                "none",
                "null",
                "n/a",
            }:
                return value
        return None

    def _normalize_csv(
        self, csv_path: Path, raw_ref: str, raw_sha: str, fetched_at: str, snapshot_id: str
    ) -> int:
        rows = self._rows(csv_path)
        if self.source == "urlhaus":
            self._normalize_urlhaus(rows, raw_ref, raw_sha, fetched_at, snapshot_id)
        else:
            self._normalize_threatfox(rows, raw_ref, raw_sha, fetched_at, snapshot_id)
        return len(rows)

    def _normalize_urlhaus(
        self,
        source_rows: list[dict[str, str]],
        raw_ref: str,
        raw_sha: str,
        fetched: str,
        snapshot: str,
    ) -> None:
        urls: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        discoveries: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []
        for row in source_rows:
            source_id = self._value(row, "id", "url_id")
            url = self._value(row, "url") or ""
            identity = source_id or "sha256:" + sha256_bytes(url.encode())
            url_id = "urlhaus:url:" + identity
            tags = [
                tag.strip() for tag in (self._value(row, "tags") or "").split(",") if tag.strip()
            ]
            status = self._value(row, "url_status", "status")
            record = {
                "url_id": url_id,
                "source": "urlhaus",
                "source_record_id": source_id,
                "url_raw": url,
                "url_status_raw": status,
                "host_raw": self._value(row, "host"),
                "date_added": self._value(row, "dateadded", "date_added"),
                "last_online": self._value(row, "last_online"),
                "threat_raw": self._value(row, "threat"),
                "tags_raw": tags,
                "reporter_raw": self._value(row, "reporter"),
                "references_raw": [
                    value for value in [self._value(row, "urlhaus_link", "reference")] if value
                ],
                "payload_count": 0,
                "raw_ref": raw_ref,
                "raw_sha256": raw_sha,
                "fetched_at": fetched,
                "snapshot_id": snapshot,
                "normalization_version": "urlhaus-v1",
            }
            urls.append(record)
            for index, tag in enumerate(tags):
                claims.append(
                    {
                        "claim_id": "urlhaus:claim:" + stable_hash(url_id, index, tag),
                        "subject_record_id": url_id,
                        "source_location": f"tags[{index}]",
                        "raw_label": tag,
                        "claim_kind": "generic_tag",
                        "parse_status": "preserved_unresolved",
                        "raw_ref": raw_ref,
                    }
                )
            discoveries.append(
                {
                    "record_id": url_id,
                    "discovery_method": "urlhaus_bulk_export",
                    "export_name": "full.csv.zip",
                    "export_generated_at": None,
                    "endpoint": f"https://{self.export_host}/v2/files/exports/<redacted>/full.csv.zip",
                    "query_value_raw": None,
                    "raw_ref": raw_ref,
                    "discovered_at": fetched,
                }
            )
            summaries.append(
                {
                    "url_id": url_id,
                    "has_status": bool(status),
                    "has_tags": bool(tags),
                    "has_malware_like_context": False,
                    "has_payload": False,
                    "payload_count": 0,
                    "has_reference": bool(record["references_raw"]),
                    "has_reporter": bool(record["reporter_raw"]),
                    "has_first_seen": bool(record["date_added"]),
                    "has_last_seen": bool(record["last_online"]),
                    "raw_ref": raw_ref,
                }
            )
        write_jsonl(
            self.root / "normalized/urls.jsonl", sorted(urls, key=lambda row: row["url_id"])
        )
        write_jsonl(self.root / "normalized/payloads.jsonl", [])
        write_jsonl(self.root / "normalized/url_payload_links.jsonl", [])
        write_jsonl(
            self.root / "normalized/source_malware_claims.jsonl",
            sorted(claims, key=lambda row: row["claim_id"]),
        )
        write_jsonl(
            self.root / "normalized/discovery_paths.jsonl",
            sorted(discoveries, key=lambda row: row["record_id"]),
        )
        write_jsonl(
            self.root / "normalized/url_observation_summaries.jsonl",
            sorted(summaries, key=lambda row: row["url_id"]),
        )

    def _normalize_threatfox(
        self,
        source_rows: list[dict[str, str]],
        raw_ref: str,
        raw_sha: str,
        fetched: str,
        snapshot: str,
    ) -> None:
        iocs: list[dict[str, Any]] = []
        malware: dict[str, dict[str, Any]] = {}
        links: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        discoveries: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []
        for row in source_rows:
            source_id = self._value(row, "id", "ioc_id")
            source_uuid = self._value(row, "uuid")
            ioc = self._value(row, "ioc") or ""
            identity = source_id or source_uuid or "sha256:" + sha256_bytes(ioc.encode())
            ioc_id = "threatfox:ioc:" + identity
            malware_id = self._value(row, "malware", "malware_id")
            malware_name = self._value(row, "malware_printable", "malware_name")
            aliases = [
                x.strip() for x in (self._value(row, "malware_alias") or "").split(",") if x.strip()
            ]
            tags = [x.strip() for x in (self._value(row, "tags") or "").split(",") if x.strip()]
            references = [x for x in [self._value(row, "reference")] if x]
            record = {
                "ioc_id": ioc_id,
                "source": "threatfox",
                "source_record_id": source_id,
                "source_uuid": source_uuid,
                "ioc_value_raw": ioc,
                "ioc_type_raw": self._value(row, "ioc_type"),
                "threat_type_raw": self._value(row, "threat_type"),
                "malware_id_raw": malware_id,
                "malware_name_raw": malware_name,
                "malware_aliases_raw": aliases,
                "confidence_level_raw": self._value(row, "confidence_level"),
                "is_compromised_raw": self._value(row, "is_compromised"),
                "first_seen": self._value(row, "first_seen"),
                "last_seen": self._value(row, "last_seen"),
                "expired_at": self._value(row, "expired_at"),
                "is_expired": None,
                "reporter_raw": self._value(row, "reporter"),
                "tags_raw": tags,
                "references_raw": references,
                "raw_ref": raw_ref,
                "raw_sha256": raw_sha,
                "fetched_at": fetched,
                "snapshot_id": snapshot,
                "normalization_version": "threatfox-v1",
            }
            iocs.append(record)
            if malware_id or malware_name:
                mid = "threatfox:malware:" + (malware_id or "sha256:" + stable_hash(malware_name))
                malware[mid] = {
                    "malware_id": mid,
                    "source": "threatfox",
                    "source_malware_id": malware_id,
                    "name_raw": malware_id,
                    "printable_name_raw": malware_name,
                    "aliases_raw": aliases,
                    "malpedia_id_raw": self._value(row, "malware_malpedia"),
                    "references_raw": [],
                    "raw_ref": raw_ref,
                    "raw_sha256": raw_sha,
                    "fetched_at": fetched,
                    "snapshot_id": snapshot,
                    "normalization_version": "threatfox-v1",
                }
                links.append(
                    {
                        "link_id": "threatfox:ioc-malware-link:"
                        + stable_hash(ioc_id, malware_id, malware_name),
                        "ioc_id": ioc_id,
                        "malware_id": mid,
                        "raw_malware_id": malware_id,
                        "raw_malware_name": malware_name,
                        "source_relation_type": "threatfox_ioc_malware_association",
                        "raw_ref": raw_ref,
                    }
                )
                claims.append(
                    {
                        "claim_id": "threatfox:claim:"
                        + stable_hash(ioc_id, malware_id, malware_name),
                        "ioc_id": ioc_id,
                        "source_location": "malware",
                        "raw_malware_id": malware_id,
                        "raw_label": malware_name,
                        "raw_aliases": aliases,
                        "claim_kind": "explicit_ioc_malware_association",
                        "parse_status": "preserved_unresolved",
                        "raw_ref": raw_ref,
                    }
                )
            discoveries.append(
                {
                    "record_id": ioc_id,
                    "discovery_method": "threatfox_full_export",
                    "export_name": "full.csv.zip",
                    "export_generated_at": None,
                    "endpoint": f"https://{self.export_host}/v2/files/exports/<redacted>/full.csv.zip",
                    "query_type": "enumeration",
                    "query_value_raw": None,
                    "raw_ref": raw_ref,
                    "discovered_at": fetched,
                }
            )
            summaries.append(
                {
                    "ioc_id": ioc_id,
                    "ioc_type_raw": record["ioc_type_raw"],
                    "has_malware_mapping": bool(malware_id or malware_name),
                    "has_malware_aliases": bool(aliases),
                    "has_tags": bool(tags),
                    "has_reference": bool(references),
                    "has_reporter": bool(record["reporter_raw"]),
                    "has_confidence": record["confidence_level_raw"] is not None,
                    "has_first_seen": bool(record["first_seen"]),
                    "has_last_seen": bool(record["last_seen"]),
                    "is_expired": None,
                    "raw_ref": raw_ref,
                }
            )
        write_jsonl(
            self.root / "normalized/iocs.jsonl", sorted(iocs, key=lambda row: row["ioc_id"])
        )
        write_jsonl(
            self.root / "normalized/malware.jsonl",
            sorted(malware.values(), key=lambda row: row["malware_id"]),
        )
        write_jsonl(
            self.root / "normalized/ioc_malware_links.jsonl",
            sorted(links, key=lambda row: row["link_id"]),
        )
        write_jsonl(
            self.root / "normalized/source_malware_claims.jsonl",
            sorted(claims, key=lambda row: row["claim_id"]),
        )
        write_jsonl(self.root / "normalized/source_actor_claims.jsonl", [])
        write_jsonl(
            self.root / "normalized/discovery_paths.jsonl",
            sorted(discoveries, key=lambda row: row["record_id"]),
        )
        write_jsonl(
            self.root / "normalized/ioc_observation_summaries.jsonl",
            sorted(summaries, key=lambda row: row["ioc_id"]),
        )

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        checked_refs: dict[str, bool] = {}
        for path in (self.root / "normalized").glob("*.jsonl"):
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    raw_ref = row.get("raw_ref")
                    if raw_ref and raw_ref not in checked_refs:
                        checked_refs[raw_ref] = (self.root / raw_ref).exists()
                    if raw_ref and not checked_refs[raw_ref]:
                        errors.append(f"{path.name}: missing {raw_ref}")
        result = {"valid": not errors, "errors": errors, "validated_at": now_utc()}
        write_json(self.root / "reports/validation_report.json", result)
        return result

    def _report(self, *, status: str, unresolved: list[str]) -> dict[str, Any]:
        def count(name: str) -> int:
            path = self.root / "normalized" / f"{name}.jsonl"
            return (
                sum(1 for line in path.open("r", encoding="utf-8") if line.strip())
                if path.exists()
                else 0
            )

        if self.source == "urlhaus":
            status_counts: Counter[str] = Counter()
            tag_counts: Counter[str] = Counter()
            records_with_tags = 0
            records_with_payloads = 0
            url_count = 0
            with (self.root / "normalized/urls.jsonl").open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    url_count += 1
                    status_counts[str(row.get("url_status_raw"))] += 1
                    tags = row.get("tags_raw") or []
                    records_with_tags += bool(tags)
                    tag_counts.update(str(tag) for tag in tags)
                    records_with_payloads += int(row.get("payload_count", 0) or 0) > 0
            result: dict[str, Any] = {
                "source": self.source,
                "status": status,
                "official_source_url": self.official_url,
                "api_export_endpoint": self.export_url,
                "collection_time": now_utc(),
                "authentication_required": True,
                "credential_environment_variable": "ABUSECH_AUTH_KEY",
                "url_records_discovered": url_count,
                "url_records_normalized": url_count,
                "url_status_distribution": dict(sorted(status_counts.items())),
                "records_with_tags": records_with_tags,
                "records_with_malware_like_tags": 0,
                "records_with_payload_associations": records_with_payloads,
                "payload_records": count("payloads"),
                "url_payload_links": count("url_payload_links"),
                "records_without_payload_context": url_count - records_with_payloads,
                "tag_distribution": dict(tag_counts.most_common()),
                "malformed_records": 0,
                "permanent_failures": 0,
                "total_raw_storage_size": sum(
                    p.stat().st_size for p in (self.root / "raw").rglob("*") if p.is_file()
                ),
                "known_source_limitations": [
                    "Full dump is active URLs or URLs added in the past 90 days."
                ],
                "unresolved_problems": unresolved,
            }
        else:
            ioc_types: Counter[str] = Counter()
            threat_types: Counter[str] = Counter()
            with_mapping = unknown_malware = with_aliases = with_tags = 0
            with_references = with_confidence = compromised = 0
            ioc_count = 0
            with (self.root / "normalized/iocs.jsonl").open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    ioc_count += 1
                    ioc_types[str(row.get("ioc_type_raw"))] += 1
                    threat_types[str(row.get("threat_type_raw"))] += 1
                    mapped = bool(row.get("malware_id_raw") or row.get("malware_name_raw"))
                    with_mapping += mapped
                    unknown_malware += not mapped
                    with_aliases += bool(row.get("malware_aliases_raw"))
                    with_tags += bool(row.get("tags_raw"))
                    with_references += bool(row.get("references_raw"))
                    with_confidence += row.get("confidence_level_raw") is not None
                    compromised += str(row.get("is_compromised_raw")).lower() in {"1", "true"}
            result = {
                "source": self.source,
                "status": status,
                "official_source_url": self.official_url,
                "api_export_endpoint": self.export_url,
                "collection_time": now_utc(),
                "authentication_required": True,
                "credential_environment_variable": "ABUSECH_AUTH_KEY",
                "ioc_records_discovered": ioc_count,
                "ioc_records_normalized": ioc_count,
                "ioc_type_distribution": dict(sorted(ioc_types.items())),
                "threat_type_distribution": dict(sorted(threat_types.items())),
                "records_with_malware_mapping": with_mapping,
                "records_with_unknown_malware": unknown_malware,
                "records_with_aliases": with_aliases,
                "records_with_tags": with_tags,
                "records_with_references": with_references,
                "records_with_confidence_values": with_confidence,
                "records_marked_compromised": compromised,
                "malware_records": count("malware"),
                "ioc_malware_links": count("ioc_malware_links"),
                "expired_records_known_to_be_excluded": True,
                "malformed_records": 0,
                "permanent_failures": 0,
                "total_raw_storage_size": sum(
                    p.stat().st_size for p in (self.root / "raw").rglob("*") if p.is_file()
                ),
                "known_source_limitations": [
                    "Expired IOCs older than six months are excluded from API and exports."
                ],
                "unresolved_problems": unresolved,
            }
        result["generated_at"] = now_utc()
        write_json(self.root / "reports/collection_report.json", result)
        title = "URLhaus" if self.source == "urlhaus" else "ThreatFox"
        atomic_write(
            self.root / "reports/collection_report.md",
            (
                f"# {title} Collection Report\n\n"
                + "\n".join(
                    f"- **{key}**: `{json.dumps(value, ensure_ascii=False)}`"
                    for key, value in result.items()
                )
                + "\n"
            ).encode(),
        )
        return result

    def _write_observed_schema(self, *, blocked: bool) -> None:
        if self.source == "urlhaus":
            body = """# URLhaus observed schema\n\nOfficial documentation and live exports were inspected at https://urlhaus.abuse.ch/api/. The Auth-Key full archive contained `csv.txt` with fields `id,dateadded,url,url_status,last_online,threat,tags,urlhaus_link,reporter`; fields are not uniformly populated. Its coverage is active URLs or URLs added in the past 90 days. The separate official collected-payload archive contained `payload.txt` with `firstseen,url,filetype,md5,sha256,signature`. The URL value is preserved only as source data and is never requested. Literal `None` values are source null sentinels, not labels.\n"""
        else:
            body = """# ThreatFox observed schema\n\nOfficial documentation and the live full CSV export were inspected at https://threatfox.abuse.ch/api/ and /export/. Observed fields include id, uuid, exact IOC, IOC/threat type, malware identifier/printable name/alias/Malpedia reference, confidence, first/last seen, reporter, reference, tags and compromised flag. The CSV uses spaces before quoted fields and literal `None` null sentinels. Records do not have identical optional values. Since 2025-05-01, IOCs older than six months expire and are excluded from API and exports.\n"""
        if blocked:
            body += "\nLive export record inspection was blocked because ABUSECH_AUTH_KEY was not present; no response schema was fabricated.\n"
        atomic_write(self.root / "reports/observed_schema.md", body.encode())
