"""Traceable, resumable collection of the public CIRCL MISP OSINT feed."""

from __future__ import annotations

import hashlib
import html.parser
import json
import os
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

FEED_URL = "https://www.circl.lu/doc/misp/feed-osint/"
NORMALIZATION_VERSION = "circl-misp-v1"
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
ACTOR_TAG_RE = re.compile(r'^misp-galaxy:(?P<kind>threat-actor|[^=]*intrusion-set)="(?P<label>.*)"$', re.I)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _iso_timestamp(value: Any) -> str | None:
    if value in (None, "", "0", 0):
        return None
    try:
        return datetime.fromtimestamp(float(value), UTC).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        return str(value)


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    for attempt in range(6):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def _write_json(path: Path, value: Any) -> None:
    _write_atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    data = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    _write_atomic(path, data.encode())


@dataclass(frozen=True)
class FeedEntry:
    filename: str
    url: str
    listing_last_modified: str | None = None
    listing_size: str | None = None
    manifest_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class StoreOutcome:
    event_id: str
    source_uuid: str | None
    raw_ref: str
    sha256: str
    status: str
    malformed: bool = False


class Transport(Protocol):
    def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response: ...


class _ListingParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.href: str | None = None
        self.rows: list[tuple[str, str]] = []
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.href is not None:
            self.rows.append((self.href, "".join(self._text)))
            self.href = None


class CirclMispCollector:
    """Deep module for collection, rebuilding, validation, and reporting."""

    def __init__(
        self,
        root: Path,
        *,
        feed_url: str = FEED_URL,
        transport: Transport | None = None,
        timeout: float = 60.0,
        retries: int = 4,
        rate_delay: float = 0.08,
    ) -> None:
        self.root = Path(root)
        self.feed_url = feed_url.rstrip("/") + "/"
        self.transport = transport or httpx.Client(
            timeout=httpx.Timeout(timeout), follow_redirects=True,
            headers={"User-Agent": "rag-cti-circl-misp-collector/1.0"},
        )
        self.retries = retries
        self.rate_delay = rate_delay
        for directory in ("raw/events", "normalized", "manifests", "checkpoints", "logs", "reports"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)

    def _get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.transport.get(url, headers=headers)
                if response.status_code not in {429, 500, 502, 503, 504}:
                    return response
                last = RuntimeError(f"temporary HTTP {response.status_code}")
            except (httpx.TransportError, TimeoutError) as exc:
                last = exc
            if attempt < self.retries:
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"request failed after {self.retries + 1} attempts: {url}: {last}")

    def enumerate_feed(self) -> list[FeedEntry]:
        listing_response = self._get(self.feed_url)
        listing_response.raise_for_status()
        manifest_response = self._get(self.feed_url + "manifest.json")
        manifest_response.raise_for_status()
        manifest = manifest_response.json()
        parser = _ListingParser()
        parser.feed(listing_response.text)
        listing_metadata: dict[str, tuple[str | None, str | None]] = {}
        listing_pattern = re.compile(
            r'href="(?P<name>[0-9a-fA-F-]{36}\.json)"[^>]*>.*?</a>\s*'
            r'.*?>(?P<modified>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*</td>'
            r'.*?>(?P<size>[^<\s]+)</td>',
            re.I,
        )
        for match in listing_pattern.finditer(listing_response.text):
            listing_metadata[match.group("name")] = (match.group("modified"), match.group("size"))
        filenames = {
            href.rsplit("/", 1)[-1] for href, _ in parser.rows
            if re.fullmatch(r"[0-9a-fA-F-]{36}\.json", href.rsplit("/", 1)[-1])
        }
        filenames.update(f"{key}.json" for key in manifest if UUID_RE.fullmatch(key))
        entries = [
            FeedEntry(
                filename=name,
                url=self.feed_url + name,
                listing_last_modified=listing_metadata.get(name, (None, None))[0],
                listing_size=listing_metadata.get(name, (None, None))[1],
                manifest_metadata=manifest.get(name[:-5]),
            )
            for name in sorted(filenames)
        ]
        snapshot = {
            "source": "circl_misp_osint",
            "feed_url": self.feed_url,
            "enumerated_at": utc_now(),
            "entry_count": len(entries),
            "manifest_entry_count": len(manifest),
            "listing_etag": listing_response.headers.get("etag"),
            "manifest_etag": manifest_response.headers.get("etag"),
            "entries": [asdict(entry) for entry in entries],
        }
        _write_json(self.root / "manifests/source_snapshot.json", snapshot)
        return entries

    def store_response(
        self,
        entry: FeedEntry,
        content: bytes,
        *,
        fetched_at: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> StoreOutcome:
        fetched_at = fetched_at or utc_now()
        sha = hashlib.sha256(content).hexdigest()
        malformed = False
        event: dict[str, Any] = {}
        try:
            document = json.loads(content)
            event = document.get("Event", document) if isinstance(document, dict) else {}
            if not isinstance(event, dict):
                event = {}
                malformed = True
        except (json.JSONDecodeError, UnicodeDecodeError):
            malformed = True
        source_uuid = event.get("uuid") if isinstance(event.get("uuid"), str) else None
        valid_uuid = source_uuid if source_uuid and UUID_RE.fullmatch(source_uuid) else None
        identity = valid_uuid or f"sha256-{sha}"
        event_id = f"circl-misp:event:{valid_uuid}" if valid_uuid else f"circl-misp:event:sha256:{sha}"
        preferred = self.root / "raw/events" / f"{identity}.json"
        status = "created"
        if preferred.exists():
            old_sha = hashlib.sha256(preferred.read_bytes()).hexdigest()
            if old_sha == sha:
                status = "unchanged"
            else:
                preferred = self.root / "raw/events" / f"{identity}__{sha}.json"
                status = "versioned"
        if not preferred.exists():
            _write_atomic(preferred, content)
        raw_ref = preferred.relative_to(self.root).as_posix()
        manifest_row = {
            "event_id": event_id, "source_uuid": source_uuid, "feed_entry": entry.filename,
            "source_url": entry.url, "raw_ref": raw_ref, "raw_sha256": sha,
            "byte_size": len(content), "fetched_at": fetched_at, "status": status,
            "malformed": malformed, "http_headers": headers or {},
        }
        self._upsert_manifest(manifest_row)
        if malformed or not valid_uuid:
            self._append_error({
                "event_id": event_id, "feed_entry": entry.filename, "raw_ref": raw_ref,
                "error_kind": "malformed_json" if malformed else "missing_or_invalid_uuid",
                "recorded_at": fetched_at, "permanent": False,
            })
        return StoreOutcome(event_id, source_uuid, raw_ref, sha, status, malformed)

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def _upsert_manifest(self, row: dict[str, Any]) -> None:
        path = self.root / "manifests/raw_manifest.jsonl"
        rows = self._read_jsonl(path)
        key = (row["feed_entry"], row["raw_sha256"])
        if not any((item["feed_entry"], item["raw_sha256"]) == key for item in rows):
            rows.append(row)
            _write_jsonl(path, sorted(rows, key=lambda item: (item["feed_entry"], item["fetched_at"], item["raw_sha256"])))

    def _append_error(self, row: dict[str, Any]) -> None:
        path = self.root / "manifests/errors.jsonl"
        rows = self._read_jsonl(path)
        key = (row.get("feed_entry"), row.get("error_kind"), row.get("raw_ref"))
        if not any((x.get("feed_entry"), x.get("error_kind"), x.get("raw_ref")) == key for x in rows):
            rows.append(row)
            _write_jsonl(path, rows)

    def _mark_errors_recovered(self, feed_entry: str, recovered_at: str) -> None:
        path = self.root / "manifests/errors.jsonl"
        rows = self._read_jsonl(path)
        changed = False
        for row in rows:
            if row.get("feed_entry") == feed_entry and row.get("permanent") is True:
                row.update({"permanent": False, "recovered": True, "recovered_at": recovered_at})
                changed = True
        if changed:
            _write_jsonl(path, rows)

    def collect(self, *, limit: int | None = None, entries: list[FeedEntry] | None = None) -> dict[str, Any]:
        entries = entries or self.enumerate_feed()
        if limit is not None:
            entries = entries[:limit]
        checkpoint_path = self.root / "checkpoints/collection_state.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {"entries": {}}
        checkpoint.update({"feed_url": self.feed_url, "started_at": checkpoint.get("started_at", utc_now())})
        temporary_recovered = 0
        for entry in entries:
            state = checkpoint["entries"].get(entry.filename, {})
            raw_ref = state.get("raw_ref")
            raw_path = self.root / raw_ref if isinstance(raw_ref, str) else None
            if (
                state.get("status") in {"success", "unchanged"}
                and raw_path is not None
                and raw_path.exists()
                and state.get("sha256") == hashlib.sha256(raw_path.read_bytes()).hexdigest()
            ):
                continue
            was_failure = state.get("status") == "permanent_failure"
            headers = {"If-None-Match": state["etag"]} if state.get("etag") else None
            try:
                response = self._get(entry.url, headers=headers)
                if response.status_code == 304:
                    state.update({"status": "unchanged", "checked_at": utc_now()})
                else:
                    response.raise_for_status()
                    outcome = self.store_response(entry, response.content, headers=dict(response.headers))
                    state.update({
                        "status": "success", "raw_ref": outcome.raw_ref, "sha256": outcome.sha256,
                        "etag": response.headers.get("etag"), "last_modified": response.headers.get("last-modified"),
                        "completed_at": utc_now(), "attempts": state.get("attempts", 0) + 1,
                    })
                    if was_failure:
                        temporary_recovered += 1
                        self._mark_errors_recovered(entry.filename, state["completed_at"])
                time.sleep(self.rate_delay)
            except Exception as exc:
                state.update({"status": "permanent_failure", "error": str(exc), "attempts": state.get("attempts", 0) + 1, "completed_at": utc_now()})
                self._append_error({"feed_entry": entry.filename, "source_url": entry.url, "error_kind": "collection_failure", "message": str(exc), "permanent": True, "recorded_at": utc_now()})
            checkpoint["entries"][entry.filename] = state
            checkpoint["updated_at"] = utc_now()
            _write_json(checkpoint_path, checkpoint)
        checkpoint["completed_at"] = utc_now()
        checkpoint["temporary_failures_recovered"] = temporary_recovered
        _write_json(checkpoint_path, checkpoint)
        return checkpoint

    def rebuild(self) -> dict[str, int]:
        rows = self._read_jsonl(self.root / "manifests/raw_manifest.jsonl")
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            latest[row["event_id"]] = row
        events: list[dict[str, Any]] = []
        discoveries: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []
        for event_id, manifest in sorted(latest.items()):
            raw_path = self.root / manifest["raw_ref"]
            try:
                document = json.loads(raw_path.read_bytes())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            event = document.get("Event", document)
            if not isinstance(event, dict):
                continue
            event_claims = self._actor_claims(event_id, event, manifest["raw_ref"])
            attributes = list(event.get("Attribute") or [])
            objects = list(event.get("Object") or [])
            object_attributes = [a for obj in objects for a in (obj.get("Attribute") or [])]
            all_attributes = attributes + object_attributes
            events.append({
                "event_id": event_id, "source": "circl_misp_osint", "source_record_id": event.get("id"),
                "source_uuid": event.get("uuid"), "title": event.get("info"), "event_date": event.get("date"),
                "published_at": _iso_timestamp(event.get("publish_timestamp")),
                "modified_at": _iso_timestamp(event.get("timestamp")), "published": event.get("published"),
                "analysis": event.get("analysis"), "threat_level_id": event.get("threat_level_id"),
                "distribution": event.get("distribution"), "sharing_group_id": event.get("sharing_group_id"),
                "org": event.get("Org"), "orgc": event.get("Orgc"), "tags_raw": event.get("Tag") or [],
                "galaxies_raw": event.get("Galaxy") or [], "attribute_count": len(all_attributes),
                "object_count": len(objects), "raw_ref": manifest["raw_ref"], "raw_sha256": manifest["raw_sha256"],
                "fetched_at": manifest["fetched_at"], "normalization_version": NORMALIZATION_VERSION,
            })
            discoveries.append({
                "event_id": event_id, "discovery_method": "circl_misp_feed_enumeration", "feed_url": self.feed_url,
                "feed_entry": manifest["feed_entry"], "feed_last_modified": manifest.get("http_headers", {}).get("last-modified"),
                "feed_size": manifest.get("byte_size"), "search_query": None, "search_rank": None,
                "raw_ref": manifest["raw_ref"], "discovered_at": manifest["fetched_at"],
            })
            claims.extend(event_claims)
            summaries.append(self._summary(event_id, all_attributes, objects, bool(event_claims), manifest["raw_ref"]))
        _write_jsonl(self.root / "normalized/events.jsonl", events)
        _write_jsonl(self.root / "normalized/discovery_paths.jsonl", discoveries)
        _write_jsonl(self.root / "normalized/source_actor_claims.jsonl", claims)
        _write_jsonl(self.root / "normalized/event_observation_summaries.jsonl", summaries)
        return {"events": len(events), "claims": len(claims), "summaries": len(summaries)}

    def _actor_claims(self, event_id: str, event: dict[str, Any], raw_ref: str) -> list[dict[str, Any]]:
        found: list[tuple[str, str, dict[str, Any]]] = []
        for index, tag in enumerate(event.get("Tag") or []):
            found.append(("event_tag", f"Event.Tag[{index}].name", tag))
        for ai, attribute in enumerate(event.get("Attribute") or []):
            for ti, tag in enumerate(attribute.get("Tag") or []):
                found.append(("attribute_tag", f"Event.Attribute[{ai}].Tag[{ti}].name", tag))
        for oi, obj in enumerate(event.get("Object") or []):
            for ti, tag in enumerate(obj.get("Tag") or []):
                found.append(("object_tag", f"Event.Object[{oi}].Tag[{ti}].name", tag))
            for ai, attribute in enumerate(obj.get("Attribute") or []):
                for ti, tag in enumerate(attribute.get("Tag") or []):
                    found.append(("attribute_tag", f"Event.Object[{oi}].Attribute[{ai}].Tag[{ti}].name", tag))
        claims: list[dict[str, Any]] = []
        for location, path, tag in found:
            name = tag.get("name") if isinstance(tag, dict) else None
            if not isinstance(name, str):
                continue
            match = ACTOR_TAG_RE.match(name)
            if match:
                label, kind = match.group("label"), "galaxy_actor_context"
                galaxy_type = match.group("kind")
            elif re.match(r"^(Threat|adversary):", name, re.I):
                label, kind, galaxy_type = name.split(":", 1)[1], "actor_like_tag", None
            elif name.strip().upper() == "APT":
                label, kind, galaxy_type = name, "unknown", None
            else:
                continue
            claim_key = f"{event_id}|{path}|{name}"
            claims.append({
                "claim_id": "circl-misp:claim:" + hashlib.sha256(claim_key.encode()).hexdigest(),
                "event_id": event_id, "source_location": location, "source_field": path,
                "raw_label": label, "raw_cluster_uuid": None, "raw_galaxy_type": galaxy_type,
                "claim_kind": kind, "parse_status": "preserved_unresolved", "raw_ref": raw_ref,
            })
        return claims

    def _summary(self, event_id: str, attributes: list[dict[str, Any]], objects: list[dict[str, Any]], has_actor: bool, raw_ref: str) -> dict[str, Any]:
        types = Counter(str(a.get("type")) for a in attributes if a.get("type") is not None)
        categories = Counter(str(a.get("category")) for a in attributes if a.get("category") is not None)
        names = Counter(str(o.get("name")) for o in objects if o.get("name") is not None)
        first = [str(a[k]) for a in attributes for k in ("first_seen",) if a.get(k)]
        last = [str(a[k]) for a in attributes for k in ("last_seen",) if a.get(k)]
        type_names = set(types)
        return {
            "event_id": event_id, "attribute_count": len(attributes), "object_count": len(objects),
            "attribute_type_counts": dict(sorted(types.items())), "attribute_category_counts": dict(sorted(categories.items())),
            "object_name_counts": dict(sorted(names.items())), "to_ids_true_count": sum(a.get("to_ids") is True for a in attributes),
            "to_ids_false_count": sum(a.get("to_ids") is False for a in attributes),
            "first_explicit_observation_time": min(first) if first else None,
            "last_explicit_observation_time": max(last) if last else None,
            "has_domain": any("domain" in value for value in type_names),
            "has_ip": any(value in {"ip-src", "ip-dst", "ip-src|port", "ip-dst|port"} for value in type_names),
            "has_url": any(value in {"url", "uri"} for value in type_names),
            "has_hash": any(value.lower() in {"md5", "sha1", "sha224", "sha256", "sha384", "sha512", "ssdeep", "tlsh", "imphash"} or "|" in value and value.rsplit("|", 1)[-1].lower() in {"md5", "sha1", "sha256", "sha512"} for value in type_names),
            "has_actor_context": has_actor, "raw_ref": raw_ref,
        }

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        event_rows = self._read_jsonl(self.root / "normalized/events.jsonl")
        for row in event_rows:
            path = self.root / row["raw_ref"]
            if not path.exists():
                errors.append(f"missing raw_ref: {row['raw_ref']}")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
                errors.append(f"hash mismatch: {row['raw_ref']}")
        ids = [row["event_id"] for row in event_rows]
        if len(ids) != len(set(ids)):
            errors.append("duplicate logical event_id")
        result = {"valid": not errors, "checked_events": len(event_rows), "errors": errors, "validated_at": utc_now()}
        _write_json(self.root / "reports/validation_report.json", result)
        return result

    def report(self) -> dict[str, Any]:
        events = self._read_jsonl(self.root / "normalized/events.jsonl")
        summaries = self._read_jsonl(self.root / "normalized/event_observation_summaries.jsonl")
        claims = self._read_jsonl(self.root / "normalized/source_actor_claims.jsonl")
        manifest = self._read_jsonl(self.root / "manifests/raw_manifest.jsonl")
        claim_counts = Counter(row["event_id"] for row in claims)
        types: Counter[str] = Counter()
        for row in summaries:
            types.update(row["attribute_type_counts"])
        checkpoint_path = self.root / "checkpoints/collection_state.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {"entries": {}}
        report = {
            "source_url": self.feed_url, "collection_time": checkpoint.get("completed_at"),
            "feed_entries_discovered": len(checkpoint.get("entries", {})), "successful_raw_events": len(events),
            "changed_versioned_events": sum(row["status"] == "versioned" for row in manifest),
            "unchanged_events": sum(x.get("status") == "unchanged" for x in checkpoint.get("entries", {}).values()),
            "temporary_failures_recovered": checkpoint.get("temporary_failures_recovered", 0),
            "permanent_failures": sum(x.get("status") == "permanent_failure" for x in checkpoint.get("entries", {}).values()),
            "malformed_records": sum(row.get("malformed", False) for row in manifest),
            "events_with_tags": sum(bool(row["tags_raw"]) for row in events),
            "events_with_galaxies": sum(bool(row["galaxies_raw"]) or any(str(t.get("name", "")).startswith("misp-galaxy:") for t in row["tags_raw"]) for row in events),
            "events_with_actor_like_source_context": len(claim_counts),
            "events_with_multiple_actor_like_labels": sum(count > 1 for count in claim_counts.values()),
            "events_without_actor_like_context": len(events) - len(claim_counts),
            "attribute_total": sum(row["attribute_count"] for row in summaries),
            "object_total": sum(row["object_count"] for row in summaries),
            "attribute_type_distribution": dict(sorted(types.items())),
            "total_raw_storage_size": sum(path.stat().st_size for path in (self.root / "raw/events").glob("*.json")),
            "known_source_limitations": ["Feed Events are source reports, not guaranteed real-world incident occurrences.", "Optional MISP fields vary by Event and feed export version."],
            "unresolved_collection_problems": [x.get("error") for x in checkpoint.get("entries", {}).values() if x.get("status") == "permanent_failure"],
            "generated_at": utc_now(),
        }
        _write_json(self.root / "reports/collection_report.json", report)
        md = "# CIRCL MISP OSINT Collection Report\n\n" + "\n".join(f"- **{key}**: `{json.dumps(value, ensure_ascii=False)}`" for key, value in report.items()) + "\n"
        _write_atomic(self.root / "reports/collection_report.md", md.encode())
        return report
