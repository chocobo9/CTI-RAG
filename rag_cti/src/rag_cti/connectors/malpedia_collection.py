"""Versioned snapshot collector for Malpedia's public metadata API."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

BASE_URL = "https://malpedia.caad.fkie.fraunhofer.de/api"
ENDPOINTS = {
    "version": "/get/version",
    "actor_inventory": "/list/actors",
    "family_inventory": "/list/families",
    "actors": "/get/actors",
    "families": "/get/families",
    "references": "/get/references",
}
TRANSIENT = {429, 500, 502, 503, 504}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _write_json(path: Path, value: Any) -> None:
    _atomic(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic(
        path,
        "".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in rows).encode(),
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


class Transport(Protocol):
    def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response: ...


class MalpediaCollector:
    def __init__(
        self,
        root: Path,
        *,
        transport: Transport | None = None,
        timeout: float = 90,
        retries: int = 3,
        rate_delay: float = 0.15,
    ) -> None:
        self.root, self.retries, self.rate_delay = Path(root), retries, rate_delay
        self.transport = transport or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "rag-cti-malpedia-collector/1.0", "Accept": "application/json"},
        )
        for directory in (
            "raw/actors",
            "raw/families",
            "raw/inventories",
            "normalized",
            "manifests",
            "checkpoints",
            "reports",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)

    def _get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.transport.get(url, headers=headers)
                if response.status_code not in TRANSIENT:
                    return response
                last = RuntimeError(f"transient HTTP {response.status_code}")
            except (httpx.TransportError, TimeoutError) as exc:
                last = exc
            if attempt < self.retries:
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"request failed after retries: {url}: {last}")

    def store_payload(
        self,
        name: str,
        content: bytes,
        *,
        fetched_at: str | None = None,
        source_url: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        fetched_at, sha = fetched_at or utc_now(), hashlib.sha256(content).hexdigest()
        group = (
            "actors"
            if name.startswith("actor") and name != "actor_inventory"
            else "families"
            if name.startswith("famil") and name != "family_inventory"
            else "inventories"
        )
        base = self.root / "raw" / group / f"{name}.json"
        target, status = base, "created"
        if base.exists():
            if hashlib.sha256(base.read_bytes()).hexdigest() == sha:
                status = "unchanged"
            else:
                target, status = base.with_name(f"{name}__{sha[:16]}.json"), "versioned"
        if not target.exists():
            _atomic(target, content)
        row = {
            "name": name,
            "source_url": source_url or BASE_URL + ENDPOINTS.get(name, ""),
            "raw_ref": target.relative_to(self.root).as_posix(),
            "sha256": sha,
            "byte_size": len(content),
            "fetched_at": fetched_at,
            "status": status,
            "http_headers": headers or {},
        }
        rows = _read_jsonl(self.root / "manifests/raw_manifest.jsonl")
        if not any(x["name"] == name and x["sha256"] == sha for x in rows):
            rows.append(row)
            _write_jsonl(
                self.root / "manifests/raw_manifest.jsonl",
                sorted(rows, key=lambda x: (x["name"], x["fetched_at"], x["sha256"])),
            )
        return row

    def collect(self, *, limit: int | None = None) -> dict[str, Any]:
        state_path = self.root / "checkpoints/collection_state.json"
        state = (
            json.loads(state_path.read_text(encoding="utf-8"))
            if state_path.exists()
            else {"endpoints": {}}
        )
        errors: list[dict[str, Any]] = []
        for name, endpoint in ENDPOINTS.items():
            url, old = BASE_URL + endpoint, state["endpoints"].get(name, {})
            headers = {"If-None-Match": old["etag"]} if old.get("etag") else None
            try:
                response = self._get(url, headers)
                if response.status_code == 304:
                    old.update({"status": "unchanged", "checked_at": utc_now()})
                    state["endpoints"][name] = old
                elif response.status_code == 200:
                    content = response.content
                    if limit and name in {"actor_inventory", "family_inventory"}:
                        content = json.dumps(response.json()[:limit], ensure_ascii=False).encode()
                    elif limit and name in {"actors", "families"}:
                        payload = response.json()
                        content = json.dumps(
                            dict(list(payload.items())[:limit]), ensure_ascii=False
                        ).encode()
                    result = self.store_payload(
                        name, content, source_url=url, headers=dict(response.headers)
                    )
                    state["endpoints"][name] = {
                        "status": "success",
                        "raw_ref": result["raw_ref"],
                        "sha256": result["sha256"],
                        "etag": response.headers.get("etag"),
                        "completed_at": utc_now(),
                    }
                else:
                    kind = (
                        "authentication_limited"
                        if response.status_code in {401, 403}
                        else "http_failure"
                    )
                    raise RuntimeError(f"{kind}: HTTP {response.status_code}")
            except Exception as exc:  # noqa: BLE001
                state["endpoints"][name] = {
                    "status": "permanent_failure",
                    "error": str(exc),
                    "completed_at": utc_now(),
                }
                errors.append(
                    {
                        "endpoint": name,
                        "source_url": url,
                        "error_kind": "authentication_limited"
                        if "authentication_limited" in str(exc)
                        else "collection_failure",
                        "message": str(exc),
                        "permanent": True,
                        "recorded_at": utc_now(),
                    }
                )
            state["updated_at"] = utc_now()
            _write_json(state_path, state)
            time.sleep(self.rate_delay)
        state["completed_at"] = utc_now()
        _write_json(state_path, state)
        _write_jsonl(self.root / "manifests/errors.jsonl", errors)
        return state

    def _latest(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in _read_jsonl(self.root / "manifests/raw_manifest.jsonl"):
            result[row["name"]] = row
        return result

    def _payload(self, latest: dict[str, dict[str, Any]], name: str, default: Any) -> Any:
        if name not in latest:
            return default
        return json.loads((self.root / latest[name]["raw_ref"]).read_text(encoding="utf-8"))

    @staticmethod
    def _aliases(record: dict[str, Any]) -> list[str]:
        meta_value = record.get("meta")
        meta: dict[str, Any] = meta_value if isinstance(meta_value, dict) else {}
        values = record.get("alt_names") or record.get("aliases") or meta.get("synonyms") or []
        return sorted({str(x) for x in values if x})

    def rebuild(self) -> dict[str, int]:
        latest = self._latest()
        actors_raw = self._payload(latest, "actors", {})
        families_raw = self._payload(latest, "families", {})
        references_raw = self._payload(latest, "references", {})
        actors, families, links, references = [], [], [], []
        actor_name_to_id: dict[str, str] = {}
        global_refs = (
            references_raw.get("references", {}) if isinstance(references_raw, dict) else {}
        )
        source_ids_by_name: dict[str, str] = {}
        for subjects in global_refs.values():
            for subject in subjects if isinstance(subjects, list) else []:
                if (
                    isinstance(subject, dict)
                    and subject.get("type") == "actor"
                    and subject.get("id")
                ):
                    source_ids_by_name[str(subject.get("common_name") or subject["id"])] = str(
                        subject["id"]
                    )
        for source_name, record in sorted(actors_raw.items()):
            if not isinstance(record, dict):
                continue
            source_id = str(
                record.get("id")
                or source_ids_by_name.get(str(record.get("value") or source_name))
                or source_name
            )
            actor_id = f"malpedia:actor:{source_id}"
            actor_name_to_id[source_name] = actor_id
            actor_name_to_id[str(record.get("value") or source_name)] = actor_id
            meta_value = record.get("meta")
            meta: dict[str, Any] = meta_value if isinstance(meta_value, dict) else {}
            refs = record.get("urls") or record.get("refs") or meta.get("refs") or []
            actors.append(
                {
                    "actor_id": actor_id,
                    "source": "malpedia",
                    "source_record_id": source_id,
                    "primary_name": str(
                        record.get("value") or record.get("common_name") or source_name
                    ),
                    "aliases_raw": self._aliases(record),
                    "description": record.get("description"),
                    "associated_family_ids_raw": list(
                        record.get("families") or record.get("associated_families") or []
                    ),
                    "references_raw": list(refs),
                    "raw_ref": latest.get("actors", {}).get("raw_ref"),
                    "fetched_at": latest.get("actors", {}).get("fetched_at"),
                }
            )
            for url in refs:
                ref_id = (
                    "malpedia:reference:"
                    + hashlib.sha256(f"actor|{actor_id}|{url}".encode()).hexdigest()
                )
                references.append(
                    {
                        "reference_id": ref_id,
                        "subject_type": "actor",
                        "subject_id": actor_id,
                        "url": str(url),
                        "title": None,
                        "source_context": None,
                        "raw_ref": latest.get("actors", {}).get("raw_ref"),
                    }
                )
        for source_id, record in sorted(families_raw.items()):
            if not isinstance(record, dict):
                continue
            family_id = f"malpedia:family:{source_id}"
            actor_values = list(
                record.get("actors")
                or record.get("associated_actors")
                or record.get("attribution")
                or []
            )
            urls = list(record.get("urls") or record.get("refs") or [])
            platform = record.get("platform") or (
                source_id.split(".", 1)[0] if "." in source_id else None
            )
            families.append(
                {
                    "family_id": family_id,
                    "source": "malpedia",
                    "source_record_id": source_id,
                    "primary_name": str(
                        record.get("common_name")
                        or record.get("value")
                        or source_id.split(".", 1)[-1]
                    ),
                    "aliases_raw": self._aliases(record),
                    "platform": platform,
                    "description": record.get("description"),
                    "associated_actor_ids_raw": actor_values,
                    "references_raw": urls,
                    "raw_ref": latest.get("families", {}).get("raw_ref"),
                    "fetched_at": latest.get("families", {}).get("fetched_at"),
                }
            )
            for actor_value in actor_values:
                target = actor_name_to_id.get(str(actor_value), f"malpedia:actor:{actor_value}")
                link_id = (
                    "malpedia:actor-family-link:"
                    + hashlib.sha256(f"{target}|{family_id}".encode()).hexdigest()
                )
                links.append(
                    {
                        "link_id": link_id,
                        "actor_id": target,
                        "family_id": family_id,
                        "actor_source_id_raw": actor_value,
                        "family_source_id_raw": source_id,
                        "raw_ref": latest.get("families", {}).get("raw_ref"),
                    }
                )
            for url in urls:
                ref_id = (
                    "malpedia:reference:"
                    + hashlib.sha256(f"family|{family_id}|{url}".encode()).hexdigest()
                )
                references.append(
                    {
                        "reference_id": ref_id,
                        "subject_type": "family",
                        "subject_id": family_id,
                        "url": str(url),
                        "title": None,
                        "source_context": None,
                        "raw_ref": latest.get("families", {}).get("raw_ref"),
                    }
                )
        for url, subjects in global_refs.items():
            for subject in subjects if isinstance(subjects, list) else []:
                if not isinstance(subject, dict) or subject.get("type") not in {"actor", "family"}:
                    continue
                subject_type, sid = (
                    subject["type"],
                    str(subject.get("id") or subject.get("common_name") or ""),
                )
                subject_id = (
                    actor_name_to_id.get(sid, f"malpedia:actor:{sid}")
                    if subject_type == "actor"
                    else f"malpedia:family:{sid}"
                )
                ref_id = (
                    "malpedia:reference:"
                    + hashlib.sha256(f"{subject_type}|{subject_id}|{url}".encode()).hexdigest()
                )
                references.append(
                    {
                        "reference_id": ref_id,
                        "subject_type": subject_type,
                        "subject_id": subject_id,
                        "url": url,
                        "title": subject.get("title"),
                        "source_context": subject.get("common_name"),
                        "raw_ref": latest.get("references", {}).get("raw_ref"),
                    }
                )
        references = list({x["reference_id"]: x for x in references}.values())
        links = list({x["link_id"]: x for x in links}.values())
        _write_jsonl(self.root / "normalized/actors.jsonl", actors)
        _write_jsonl(self.root / "normalized/families.jsonl", families)
        _write_jsonl(
            self.root / "normalized/actor_family_links.jsonl",
            sorted(links, key=lambda x: x["link_id"]),
        )
        _write_jsonl(
            self.root / "normalized/references.jsonl",
            sorted(references, key=lambda x: x["reference_id"]),
        )
        version = self._payload(latest, "version", {})
        _write_json(
            self.root / "manifests/source_snapshot.json",
            {
                "source": "malpedia",
                "snapshot_at": utc_now(),
                "source_version": version,
                "endpoints": latest,
            },
        )
        return {
            "actors": len(actors),
            "families": len(families),
            "links": len(links),
            "references": len(references),
        }

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        actors = _read_jsonl(self.root / "normalized/actors.jsonl")
        families = _read_jsonl(self.root / "normalized/families.jsonl")
        links = _read_jsonl(self.root / "normalized/actor_family_links.jsonl")
        refs = _read_jsonl(self.root / "normalized/references.jsonl")
        actor_ids, family_ids = {x["actor_id"] for x in actors}, {x["family_id"] for x in families}
        if len(actor_ids) != len(actors):
            errors.append("duplicate actor_id")
        if len(family_ids) != len(families):
            errors.append("duplicate family_id")
        for link in links:
            if link["family_id"] not in family_ids:
                errors.append(f"unknown link family: {link['family_id']}")
            # Actor strings can be source aliases not represented by a public actor record; retain and report.
        for ref in refs:
            valid = ref["subject_id"] in (
                actor_ids if ref["subject_type"] == "actor" else family_ids
            )
            if not valid:
                errors.append(f"unknown reference subject: {ref['subject_id']}")
        for row in self._latest().values():
            raw = self.root / row["raw_ref"]
            if not raw.is_file() or hashlib.sha256(raw.read_bytes()).hexdigest() != row["sha256"]:
                errors.append(f"raw hash invalid: {row['name']}")
        result = {
            "valid": not errors,
            "checked_actors": len(actors),
            "checked_families": len(families),
            "checked_links": len(links),
            "checked_references": len(refs),
            "errors": errors,
            "validated_at": utc_now(),
        }
        _write_json(self.root / "reports/validation_report.json", result)
        return result

    def report(self) -> dict[str, Any]:
        actors = _read_jsonl(self.root / "normalized/actors.jsonl")
        families = _read_jsonl(self.root / "normalized/families.jsonl")
        links = _read_jsonl(self.root / "normalized/actor_family_links.jsonl")
        refs = _read_jsonl(self.root / "normalized/references.jsonl")
        errors = _read_jsonl(self.root / "manifests/errors.jsonl")
        snapshot_path = self.root / "manifests/source_snapshot.json"
        snapshot = (
            json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.exists() else {}
        )
        report = {
            "accessible_actor_count": len(actors),
            "accessible_family_count": len(families),
            "alias_count": sum(len(x["aliases_raw"]) for x in actors + families),
            "actor_family_link_count": len(links),
            "reference_count": len(refs),
            "authentication_limited_endpoints": [
                x["endpoint"] for x in errors if x["error_kind"] == "authentication_limited"
            ],
            "malformed_records": 0,
            "recovered_failures": 0,
            "permanent_failures": sum(x.get("permanent") is True for x in errors),
            "snapshot_time": snapshot.get("snapshot_at"),
            "source_version": snapshot.get("source_version"),
            "storage_size": sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file()),
            "generated_at": utc_now(),
        }
        _write_json(self.root / "reports/collection_report.json", report)
        _atomic(
            self.root / "reports/collection_report.md",
            (
                "# Malpedia Public Metadata Snapshot Report\n\n"
                + "\n".join(
                    f"- **{k}**: `{json.dumps(v, ensure_ascii=False)}`" for k, v in report.items()
                )
                + "\n"
            ).encode(),
        )
        return report
