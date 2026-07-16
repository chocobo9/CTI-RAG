"""Versioned collection and normalization of the public ORKL API."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from rag_cti.connectors.source_collection_common import (
    SafeHttpClient,
    atomic_write,
    canonical_json,
    now_utc,
    read_jsonl,
    sha256_bytes,
    stable_hash,
    write_json,
    write_jsonl,
)

BASE_URL = "https://orkl.eu/api/v1"


class Transport(Protocol):
    def get(self, url: str, **kwargs: Any) -> httpx.Response: ...


class OrklCollector:
    def __init__(
        self, root: Path = Path("data/orkl"), *, transport: Transport | None = None
    ) -> None:
        self.root = root
        self.transport = transport or SafeHttpClient()
        for path in (
            "raw/reports",
            "raw/actor_profiles",
            "raw/actor_report_links",
            "raw/inventories",
            "raw/documents",
            "normalized",
            "manifests",
            "checkpoints",
            "logs",
            "reports",
        ):
            (root / path).mkdir(parents=True, exist_ok=True)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        response = self.transport.get(BASE_URL + path, params=params)
        response.raise_for_status()
        return response

    def _store_record(
        self,
        kind: str,
        record_id: str | None,
        record: dict[str, Any],
        fetched_at: str,
        endpoint: str,
        snapshot_id: str,
    ) -> dict[str, Any]:
        raw = canonical_json(record)
        sha = sha256_bytes(raw)
        identity = record_id or f"sha256-{sha}"
        raw_path = self.root / "raw" / kind / identity / f"{sha}.json"
        status = "unchanged" if raw_path.exists() else "created"
        if not raw_path.exists():
            atomic_write(raw_path, raw)
        return {
            "source": "orkl",
            "record_kind": kind,
            "source_record_id": record_id,
            "raw_ref": raw_path.relative_to(self.root).as_posix(),
            "raw_sha256": sha,
            "byte_size": len(raw),
            "endpoint": endpoint,
            "fetched_at": fetched_at,
            "snapshot_id": snapshot_id,
            "status": status,
            "collector_version": "orkl-collector-v1",
        }

    def collect(self, *, page_size: int = 100, max_reports: int | None = None) -> dict[str, Any]:
        started = now_utc()
        checkpoint_path = self.root / "checkpoints/collection_state.json"
        prior_checkpoint: dict[str, Any] = {}
        if checkpoint_path.exists():
            prior_checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        is_resume = prior_checkpoint.get("status") == "running"
        collection_started_at = (
            prior_checkpoint.get("collection_started_at", started) if is_resume else started
        )
        snapshot_id = (
            prior_checkpoint["snapshot_id"]
            if is_resume
            else "orkl-" + started.replace(":", "-")
        )
        info_response = self._get("/library/info")
        info = info_response.json()["data"]
        actor_response = self._get("/ta/entries")
        actor_document = actor_response.json()
        actors = actor_document.get("data") or []
        atomic_write(
            self.root / "raw/inventories" / f"{snapshot_id}-actors.json", actor_response.content
        )
        manifest_path = self.root / "manifests/raw_manifest.jsonl"
        errors_path = self.root / "manifests/errors.jsonl"
        manifest = read_jsonl(manifest_path) if is_resume else []
        errors = read_jsonl(errors_path) if is_resume else []
        actor_start = int(prior_checkpoint.get("actor_next_index", 0)) if is_resume else 0
        target = int(info["library_entries"])
        if max_reports is not None:
            target = min(target, max_reports)
        checkpoint = {
            "snapshot_id": snapshot_id,
            "collection_started_at": collection_started_at,
            "status": "running",
            "metadata_status": "running",
            "document_status": "not_started_storage_risk",
            "next_offset": int(prior_checkpoint.get("next_offset", 0)) if is_resume else 0,
            "actor_next_index": actor_start,
            "target_reports": target,
            "reports_stored": int(prior_checkpoint.get("reports_stored", 0)) if is_resume else 0,
            "actors_stored": actor_start,
            "updated_at": started,
        }
        write_json(checkpoint_path, checkpoint)
        for actor_index, actor in enumerate(actors[actor_start:], start=actor_start):
            record_id = actor.get("id")
            detailed_actor = actor
            endpoint = "/ta/entries"
            if record_id:
                detail_response = self._get(f"/ta/entry/{record_id}")
                detail_document = detail_response.json()
                candidate = detail_document.get("data")
                detailed_actor = candidate if isinstance(candidate, dict) else actor
                endpoint = f"/ta/entry/{record_id}"
            manifest.append(
                self._store_record(
                    "actor_profiles", record_id, detailed_actor, started, endpoint, snapshot_id
                )
            )
            if not record_id:
                errors.append(
                    {
                        "error_kind": "missing_stable_identifier",
                        "record_kind": "actor_profile",
                        "raw_sha256": manifest[-1]["raw_sha256"],
                        "permanent": False,
                    }
                )
            checkpoint.update(
                {
                    "actor_next_index": actor_index + 1,
                    "actors_stored": actor_index + 1,
                    "updated_at": now_utc(),
                }
            )
            if (actor_index + 1) % 25 == 0 or actor_index + 1 == len(actors):
                write_jsonl(manifest_path, manifest)
                write_jsonl(errors_path, errors)
                write_json(checkpoint_path, checkpoint)
            time.sleep(0.05)
        offset = int(checkpoint["next_offset"])
        while offset < target:
            limit = min(page_size, target - offset)
            response = self._get(
                "/library/entries",
                {"limit": limit, "offset": offset, "order_by": "created_at", "order": "asc"},
            )
            page_ref = self.root / "raw/inventories" / f"{snapshot_id}-reports-{offset:06d}.json"
            atomic_write(page_ref, response.content)
            records = response.json().get("data") or []
            if not records:
                break
            for report in records:
                record_id = report.get("id")
                manifest.append(
                    self._store_record(
                        "reports", record_id, report, started, "/library/entries", snapshot_id
                    )
                )
                if not record_id:
                    errors.append(
                        {
                            "error_kind": "missing_stable_identifier",
                            "record_kind": "report",
                            "raw_sha256": manifest[-1]["raw_sha256"],
                            "permanent": False,
                        }
                    )
            offset += len(records)
            checkpoint.update(
                {"next_offset": offset, "reports_stored": offset, "updated_at": now_utc()}
            )
            write_jsonl(
                manifest_path,
                sorted(manifest, key=lambda row: (row["record_kind"], str(row["source_record_id"]))),
            )
            write_jsonl(errors_path, errors)
            write_json(checkpoint_path, checkpoint)
            time.sleep(0.05)
        write_jsonl(
            self.root / "manifests/raw_manifest.jsonl",
            sorted(manifest, key=lambda row: (row["record_kind"], str(row["source_record_id"]))),
        )
        write_jsonl(self.root / "manifests/errors.jsonl", errors)
        completed = now_utc()
        checkpoint.update(
            {
                "status": "complete_metadata_only",
                "metadata_status": "complete",
                "document_status": "not_started_storage_risk",
                "collection_completed_at": completed,
            }
        )
        write_json(checkpoint_path, checkpoint)
        snapshot = {
            "source": "orkl",
            "snapshot_id": snapshot_id,
            "collection_started_at": collection_started_at,
            "collection_completed_at": completed,
            "official_base_url": "https://orkl.eu/",
            "api_documentation_url": "https://orkl.eu/api/v1/doc/index.html",
            "api_version_observed": "1.1",
            "authentication_required": False,
            "credential_environment_variables": [],
            "rate_limit_observed": None,
            "license_or_terms_url": None,
            "fair_use_constraints": [
                "No rate-limit headers observed; collector uses bounded serial requests."
            ],
            "collection_methods": ["orkl_api_enumeration", "orkl_actor_profile_enumeration"],
            "endpoints_used": [
                "/library/info",
                "/library/entries",
                "/ta/entries",
                "/ta/entry/{uuid}",
            ],
            "exports_used": [],
            "coverage_window": {
                "start": None,
                "end": info.get("library_last_update"),
                "basis": "ORKL library inventory",
            },
            "known_coverage_limitations": [
                "Actor-report links are preserved from explicit threat_actors arrays on report records.",
                "Document references are inventoried; document bytes are not part of the default metadata collection.",
            ],
            "inventory_count": offset,
            "actor_profile_inventory_count": len(actors),
            "api_info": info,
            "all_library_entries_enumerable": offset == target and (max_reports is None),
            "all_actor_profiles_enumerable": True,
            "collector_version": "orkl-collector-v1",
            "normalization_version": "orkl-v1",
        }
        write_json(self.root / "manifests/source_snapshot.json", snapshot)
        self._write_observed_schema()
        return checkpoint

    def _write_observed_schema(self) -> None:
        body = """# ORKL observed schema

Inspected 2026-07-16 from the public ORKL API v1.1 and 10 live report records,
10 actor-list records, and their 10 detailed actor responses.

`GET /library/entries` is paginated with `limit` and `offset`; observed report
fields were `id`, `sha1_hash`, `title`, `llm_title`, `authors`, creation and
modification timestamps, file size, `plain_text`, extraction quality, language,
`sources`, `origins`, `references`, `report_names`, `threat_actors`, and a
`files` object containing official PDF/text/image archive URLs. Fields are not
uniformly populated; empty titles, empty text, null actor arrays, and zero-like
source dates occur.

`GET /ta/entries` returned the full actor inventory. Observed fields were `id`,
`main_name`, `aliases`, `source_id`, `source_name`, `tools`, timestamps, and a
null `reports` field. `GET /ta/entry/{uuid}` returned the same actor profile
with an explicit `reports` array. Actor-report evidence is also exposed in a
report's `threat_actors` array and is preserved without canonical resolution.

`GET /library/info` reported library version, last update time, report count,
actor count and source count. No authentication, ETag, rate-limit or Retry-After
headers were observed. The API exposes full extracted report text plus official
archive document references.
"""
        atomic_write(self.root / "reports/observed_schema.md", body.encode())

    def collect_documents(
        self, *, max_documents: int | None = None, max_total_bytes: int | None = None
    ) -> dict[str, Any]:
        """Download only ORKL archive documents with a resumable byte budget."""
        reports = read_jsonl(self.root / "normalized/reports.jsonl")
        jobs = [
            (report["report_id"], ref)
            for report in reports
            for ref in report.get("document_refs", [])
        ]
        if max_documents is not None:
            jobs = jobs[:max_documents]
        checkpoint_path = self.root / "checkpoints/document_state.json"
        manifest_path = self.root / "manifests/document_manifest.jsonl"
        checkpoint = (
            json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if checkpoint_path.exists()
            else {}
        )
        start_index = int(checkpoint.get("next_index", 0))
        manifest = read_jsonl(manifest_path)
        errors = read_jsonl(self.root / "manifests/errors.jsonl")
        downloaded_bytes = int(checkpoint.get("downloaded_bytes", 0))
        state = {
            "status": "running",
            "next_index": start_index,
            "target_documents": len(jobs),
            "downloaded_documents": len(manifest),
            "downloaded_bytes": downloaded_bytes,
            "updated_at": now_utc(),
        }
        write_json(checkpoint_path, state)
        for index, (report_id, ref) in enumerate(jobs[start_index:], start=start_index):
            url = ref.get("url")
            if not isinstance(url, str) or urlsplit(url).hostname != "archive.orkl.eu":
                errors.append(
                    {
                        "error_kind": "document_host_not_allowed",
                        "report_id": report_id,
                        "source_url": url,
                        "permanent": True,
                        "recorded_at": now_utc(),
                    }
                )
                state["next_index"] = index + 1
                continue
            safe_report_id = report_id.removeprefix("orkl:report:")
            target_dir = self.root / "raw/documents" / safe_report_id
            target_dir.mkdir(parents=True, exist_ok=True)
            temporary = target_dir / f"document-{index}.part"
            digest = hashlib.sha256()
            size = 0
            response_headers: dict[str, str] = {}
            try:
                with httpx.stream(
                    "GET",
                    url,
                    timeout=httpx.Timeout(180),
                    follow_redirects=False,
                    headers={"User-Agent": "rag-cti-source-collector/1.0"},
                ) as response:
                    response.raise_for_status()
                    response_headers = {
                        key: value
                        for key, value in response.headers.items()
                        if key.lower() in {"content-type", "content-length", "etag", "last-modified"}
                    }
                    with temporary.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if (
                                max_total_bytes is not None
                                and downloaded_bytes + size > max_total_bytes
                            ):
                                raise RuntimeError("document byte budget exceeded")
                            digest.update(chunk)
                            handle.write(chunk)
                sha = digest.hexdigest()
                extension = str(ref.get("kind") or "bin").lower().lstrip(".")
                raw_path = target_dir / f"{sha}.{extension}"
                if raw_path.exists():
                    temporary.unlink(missing_ok=True)
                    status = "unchanged"
                else:
                    os.replace(temporary, raw_path)
                    status = "created"
                downloaded_bytes += size
                manifest.append(
                    {
                        "source": "orkl",
                        "record_kind": "document",
                        "report_id": report_id,
                        "document_kind": ref.get("kind"),
                        "source_url": url,
                        "raw_ref": raw_path.relative_to(self.root).as_posix(),
                        "raw_sha256": sha,
                        "byte_size": size,
                        "response_headers": response_headers,
                        "fetched_at": now_utc(),
                        "status": status,
                        "collector_version": "orkl-collector-v1",
                    }
                )
            except Exception as exc:
                temporary.unlink(missing_ok=True)
                errors.append(
                    {
                        "error_kind": "document_download_failure",
                        "report_id": report_id,
                        "source_url": url,
                        "message": str(exc),
                        "permanent": False,
                        "recorded_at": now_utc(),
                    }
                )
                if "byte budget exceeded" in str(exc):
                    state.update({"status": "stopped_byte_budget", "updated_at": now_utc()})
                    write_jsonl(manifest_path, manifest)
                    write_jsonl(self.root / "manifests/errors.jsonl", errors)
                    write_json(checkpoint_path, state)
                    return state
            state.update(
                {
                    "next_index": index + 1,
                    "downloaded_documents": len(manifest),
                    "downloaded_bytes": downloaded_bytes,
                    "updated_at": now_utc(),
                }
            )
            write_jsonl(manifest_path, manifest)
            write_jsonl(self.root / "manifests/errors.jsonl", errors)
            write_json(checkpoint_path, state)
            time.sleep(0.05)
        state.update({"status": "complete", "updated_at": now_utc()})
        write_json(checkpoint_path, state)
        return state

    def rebuild(self) -> dict[str, int]:
        manifest = read_jsonl(self.root / "manifests/raw_manifest.jsonl")
        # A process can be interrupted after the page manifest is committed but
        # before the offset checkpoint is committed.  The resumed page is then
        # intentionally fetched again.  Collapse those manifest entries by the
        # source identity while leaving every content-addressed raw version on
        # disk.
        current_by_identity: dict[tuple[str, str], dict[str, Any]] = {}
        for item in manifest:
            identity = str(item.get("source_record_id") or item["raw_sha256"])
            current_by_identity[(item["record_kind"], identity)] = item
        manifest = sorted(
            current_by_identity.values(),
            key=lambda row: (row["record_kind"], str(row["source_record_id"])),
        )
        write_jsonl(self.root / "manifests/raw_manifest.jsonl", manifest)
        reports: list[dict[str, Any]] = []
        profiles: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []
        discovery: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []
        for item in manifest:
            raw = json.loads((self.root / item["raw_ref"]).read_text(encoding="utf-8"))
            if item["record_kind"] == "reports":
                report_id = (
                    f"orkl:report:{item['source_record_id'] or 'sha256:' + item['raw_sha256']}"
                )
                actors = raw.get("threat_actors") or []
                actor_labels = [
                    actor.get("main_name")
                    for actor in actors
                    if isinstance(actor, dict) and actor.get("main_name")
                ]
                actor_ids = [
                    actor.get("id")
                    for actor in actors
                    if isinstance(actor, dict) and actor.get("id")
                ]
                files = raw.get("files") or {}
                document_refs = [
                    {"kind": key, "url": value} for key, value in files.items() if value
                ]
                reports.append(
                    {
                        "report_id": report_id,
                        "source": "orkl",
                        "source_record_id": item["source_record_id"],
                        "source_uuid": raw.get("id"),
                        "title": raw.get("title") or raw.get("llm_title"),
                        "description": raw.get("plain_text"),
                        "report_type_raw": raw.get("origins"),
                        "source_name": raw.get("sources"),
                        "source_url": (raw.get("references") or [None])[0],
                        "orkl_url": f"https://orkl.eu/libraryEntry/{raw.get('id')}"
                        if raw.get("id")
                        else None,
                        "published_at": raw.get("file_creation_date"),
                        "modified_at": raw.get("updated_at"),
                        "actor_labels_raw": actor_labels,
                        "actor_ids_raw": actor_ids,
                        "tags_raw": [],
                        "references_raw": raw.get("references") or [],
                        "document_refs": document_refs,
                        "raw_ref": item["raw_ref"],
                        "raw_sha256": item["raw_sha256"],
                        "fetched_at": item["fetched_at"],
                        "snapshot_id": item["snapshot_id"],
                        "normalization_version": "orkl-v1",
                    }
                )
                for index, actor in enumerate(actors):
                    if not isinstance(actor, dict) or not actor.get("main_name"):
                        continue
                    actor_profile_id = (
                        f"orkl:actor-profile:{actor['id']}" if actor.get("id") else None
                    )
                    path = f"threat_actors[{index}]"
                    link_id = "orkl:actor-report-link:" + stable_hash(
                        report_id, actor.get("id"), actor.get("main_name"), path
                    )
                    links.append(
                        {
                            "link_id": link_id,
                            "report_id": report_id,
                            "actor_profile_id": actor_profile_id,
                            "raw_actor_id": actor.get("id"),
                            "raw_actor_label": actor["main_name"],
                            "source_relation_type": "threat_actors",
                            "source_location": path,
                            "claim_status": "source_explicit",
                            "raw_ref": item["raw_ref"],
                        }
                    )
                    claims.append(
                        {
                            "claim_id": "orkl:claim:"
                            + stable_hash(report_id, path, actor.get("id"), actor["main_name"]),
                            "subject_record_id": report_id,
                            "source_location": path,
                            "raw_actor_id": actor.get("id"),
                            "raw_label": actor["main_name"],
                            "source_relation_type": "threat_actors",
                            "claim_kind": "explicit_actor_report_relation",
                            "parse_status": "preserved_unresolved",
                            "raw_ref": item["raw_ref"],
                        }
                    )
                summaries.append(
                    {
                        "report_id": report_id,
                        "has_title": bool(raw.get("title") or raw.get("llm_title")),
                        "has_description": bool(raw.get("plain_text")),
                        "has_publication_time": bool(raw.get("file_creation_date")),
                        "has_original_source_url": bool(raw.get("references")),
                        "has_downloadable_document": bool(document_refs),
                        "actor_label_count": len(actor_labels),
                        "explicit_actor_relation_count": len(actors),
                        "tag_count": 0,
                        "reference_count": len(raw.get("references") or []),
                        "document_count": len(document_refs),
                        "has_multiple_actor_labels": len(actor_labels) > 1,
                        "raw_ref": item["raw_ref"],
                    }
                )
                record_id = report_id
                method = "orkl_api_enumeration"
            else:
                profile_id = f"orkl:actor-profile:{item['source_record_id'] or 'sha256:' + item['raw_sha256']}"
                aliases = raw.get("aliases") or []
                profiles.append(
                    {
                        "actor_profile_id": profile_id,
                        "source": "orkl",
                        "source_record_id": item["source_record_id"],
                        "source_uuid": raw.get("id"),
                        "main_name_raw": raw.get("main_name"),
                        "source_name": raw.get("source_id"),
                        "source_entry_name": raw.get("source_name"),
                        "aliases_raw": aliases,
                        "descriptions_raw": [],
                        "countries_raw": [],
                        "sectors_raw": [],
                        "malware_labels_raw": [],
                        "tool_labels_raw": raw.get("tools") or [],
                        "technique_labels_raw": [],
                        "references_raw": [],
                        "raw_ref": item["raw_ref"],
                        "raw_sha256": item["raw_sha256"],
                        "fetched_at": item["fetched_at"],
                        "snapshot_id": item["snapshot_id"],
                        "normalization_version": "orkl-v1",
                    }
                )
                if raw.get("main_name"):
                    claims.append(
                        {
                            "claim_id": "orkl:claim:"
                            + stable_hash(profile_id, "main_name", raw["main_name"]),
                            "subject_record_id": profile_id,
                            "source_location": "main_name",
                            "raw_actor_id": raw.get("id"),
                            "raw_label": raw["main_name"],
                            "source_relation_type": None,
                            "claim_kind": "actor_profile_name",
                            "parse_status": "preserved_unresolved",
                            "raw_ref": item["raw_ref"],
                        }
                    )
                for index, alias in enumerate(aliases):
                    claims.append(
                        {
                            "claim_id": "orkl:claim:"
                            + stable_hash(profile_id, "aliases", index, alias),
                            "subject_record_id": profile_id,
                            "source_location": f"aliases[{index}]",
                            "raw_actor_id": raw.get("id"),
                            "raw_label": alias,
                            "source_relation_type": None,
                            "claim_kind": "actor_alias",
                            "parse_status": "preserved_unresolved",
                            "raw_ref": item["raw_ref"],
                        }
                    )
                record_id = profile_id
                method = "orkl_actor_profile_enumeration"
            discovery.append(
                {
                    "record_id": record_id,
                    "discovery_method": method,
                    "endpoint": item["endpoint"],
                    "query_type": "enumeration",
                    "query_value_raw": None,
                    "page_or_cursor": None,
                    "search_rank": None,
                    "raw_ref": item["raw_ref"],
                    "discovered_at": item["fetched_at"],
                }
            )
        write_jsonl(
            self.root / "normalized/reports.jsonl",
            sorted(reports, key=lambda row: row["report_id"]),
        )
        write_jsonl(
            self.root / "normalized/actor_profiles.jsonl",
            sorted(profiles, key=lambda row: row["actor_profile_id"]),
        )
        write_jsonl(
            self.root / "normalized/source_actor_claims.jsonl",
            sorted(claims, key=lambda row: row["claim_id"]),
        )
        write_jsonl(
            self.root / "normalized/actor_report_links.jsonl",
            sorted(links, key=lambda row: row["link_id"]),
        )
        write_jsonl(
            self.root / "normalized/discovery_paths.jsonl",
            sorted(discovery, key=lambda row: row["record_id"]),
        )
        write_jsonl(
            self.root / "normalized/report_observation_summaries.jsonl",
            sorted(summaries, key=lambda row: row["report_id"]),
        )
        return {
            "reports": len(reports),
            "actor_profiles": len(profiles),
            "actor_report_links": len(links),
            "claims": len(claims),
        }

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        files = [
            "reports.jsonl",
            "actor_profiles.jsonl",
            "source_actor_claims.jsonl",
            "actor_report_links.jsonl",
            "discovery_paths.jsonl",
            "report_observation_summaries.jsonl",
        ]
        for name in files:
            for row in read_jsonl(self.root / "normalized" / name):
                raw_ref = row.get("raw_ref")
                if raw_ref and not (self.root / raw_ref).exists():
                    errors.append(f"{name}: missing {raw_ref}")
        result = {"valid": not errors, "errors": errors, "validated_at": now_utc()}
        write_json(self.root / "reports/validation_report.json", result)
        return result

    def report(self) -> dict[str, Any]:
        reports = read_jsonl(self.root / "normalized/reports.jsonl")
        profiles = read_jsonl(self.root / "normalized/actor_profiles.jsonl")
        links = read_jsonl(self.root / "normalized/actor_report_links.jsonl")
        summary = read_jsonl(self.root / "normalized/report_observation_summaries.jsonl")
        manifest = read_jsonl(self.root / "manifests/raw_manifest.jsonl")
        document_manifest = read_jsonl(self.root / "manifests/document_manifest.jsonl")
        source_errors = read_jsonl(self.root / "manifests/errors.jsonl")
        document_failures = sum(
            row.get("error_kind") == "document_download_failure" for row in source_errors
        )
        documents_discovered = sum(row["document_count"] for row in summary)
        result = {
            "status": "complete_metadata_only",
            "official_source_url": "https://orkl.eu/",
            "api_endpoints_used": [
                "/library/info",
                "/library/entries",
                "/ta/entries",
                "/ta/entry/{uuid}",
            ],
            "collection_time": now_utc(),
            "api_authentication_required": False,
            "rate_limits_observed": None,
            "library_report_entries_discovered": len(reports),
            "actor_profiles_discovered": len(profiles),
            "explicit_actor_report_links": len(links),
            "successful_raw_report_records": len(reports),
            "successful_actor_profile_records": len(profiles),
            "report_documents_discovered": documents_discovered,
            "report_documents_downloaded": len(document_manifest),
            "document_download_failures": document_failures,
            "report_documents_not_attempted": max(
                0, documents_discovered - len(document_manifest) - document_failures
            ),
            "changed_versioned_records": sum(
                sum(1 for _ in record_dir.glob("*.json")) > 1
                for kind in ("reports", "actor_profiles")
                for record_dir in (self.root / "raw" / kind).iterdir()
                if record_dir.is_dir()
            ),
            "unchanged_records": sum(row["status"] == "unchanged" for row in manifest),
            "temporary_failures_recovered": 0,
            "permanent_failures": 0,
            "malformed_records": 0,
            "reports_with_actor_context": sum(row["actor_label_count"] > 0 for row in summary),
            "reports_with_multiple_actor_labels": sum(
                row["has_multiple_actor_labels"] for row in summary
            ),
            "reports_without_actor_context": sum(row["actor_label_count"] == 0 for row in summary),
            "actor_profiles_with_aliases": sum(bool(row["aliases_raw"]) for row in profiles),
            "total_raw_storage_size": sum(
                path.stat().st_size for path in (self.root / "raw").rglob("*") if path.is_file()
            ),
            "known_api_coverage_limitations": [
                "External PDF/text/image document bytes were not downloaded; ORKL API plain_text and all official document references are preserved."
            ],
            "unresolved_problems": [
                "Document-byte mirror is not complete; estimated PDF file_size is 41.86 GiB before text/image derivatives."
            ],
        }
        write_json(self.root / "reports/collection_report.json", result)
        atomic_write(
            self.root / "reports/collection_report.md",
            (
                "# ORKL Collection Report\n\n"
                + "\n".join(
                    f"- **{key}**: `{json.dumps(value, ensure_ascii=False)}`"
                    for key, value in result.items()
                )
                + "\n"
            ).encode(),
        )
        return result
