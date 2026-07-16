#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_cti.connectors.abuse_export_collection import AbuseExportCollector
from rag_cti.connectors.orkl_collection import OrklCollector
from rag_cti.connectors.source_collection_common import atomic_write, now_utc, write_json


def main() -> int:
    roots = {"orkl": Path("data/orkl"), "urlhaus": Path("data/urlhaus"), "threatfox": Path("data/threatfox")}
    validations: dict[str, Any] = {
        "orkl": OrklCollector(roots["orkl"]).validate(),
        "urlhaus": AbuseExportCollector("urlhaus", roots["urlhaus"]).validate(),
        "threatfox": AbuseExportCollector("threatfox", roots["threatfox"]).validate(),
    }
    reports: dict[str, Any] = {}
    snapshots: dict[str, Any] = {}
    for source, root in roots.items():
        path = root / "reports/collection_report.json"
        reports[source] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "missing"}
        snapshot_path = root / "manifests/source_snapshot.json"
        snapshots[source] = (
            json.loads(snapshot_path.read_text(encoding="utf-8"))
            if snapshot_path.exists()
            else {}
        )
    blocked = [source for source, report in reports.items() if report.get("status") == "blocked_external_access"]
    total_storage = sum(report.get("total_raw_storage_size", 0) or 0 for report in reports.values())
    total_raw = (
        reports["orkl"].get("successful_raw_report_records", 0)
        + reports["orkl"].get("successful_actor_profile_records", 0)
        + reports["urlhaus"].get("url_records_discovered", 0)
        + reports["urlhaus"].get("url_payload_links", 0)
        + reports["threatfox"].get("ioc_records_discovered", 0)
    )
    total_normalized = sum(
        sum(1 for line in path.open("r", encoding="utf-8") if line.strip())
        for root in roots.values()
        for path in (root / "normalized").glob("*.jsonl")
    )
    combined = {
        "generated_at": now_utc(),
        "collection_started_at": min(
            value
            for snapshot in snapshots.values()
            if (value := snapshot.get("collection_started_at"))
        ),
        "collection_completed_at": max(
            value
            for snapshot in snapshots.values()
            if (value := snapshot.get("collection_completed_at"))
        ),
        "sources": reports, "source_status": {source: report.get("status") for source, report in reports.items()},
        "total_raw_records": total_raw, "total_normalized_records": total_normalized,
        "total_storage": total_storage, "blocked_sources": blocked,
        "credential_requirements": {"urlhaus": "ABUSECH_AUTH_KEY", "threatfox": "ABUSECH_AUTH_KEY"},
        "validation_results": validations, "reconciliation_results": {source: result["valid"] for source, result in validations.items()},
        "source_role_summary": {"orkl": "actor/source tag to report or actor profile", "urlhaus": "malicious URL to malware/payload context", "threatfox": "IOC to malware/threat context"},
        "important_semantic_boundaries": [
            "ORKL actor-report context, URLhaus malware-URL context and ThreatFox malware-IOC context are separately sourced observations.",
            "No cross-source actor attribution was generated during this task.",
        ],
    }
    write_json(Path("data/collection_report.json"), combined)
    markdown = "# Source Collection Summary\n\n" + "\n".join(f"- **{key}**: `{json.dumps(value, ensure_ascii=False)}`" for key, value in combined.items()) + "\n"
    atomic_write(Path("data/collection_report.md"), markdown.encode())
    print(json.dumps(combined, ensure_ascii=False, indent=2))
    return 0 if all(result["valid"] for result in validations.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
