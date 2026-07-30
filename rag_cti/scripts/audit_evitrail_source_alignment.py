"""Audit collected non-OTX sources against the current EviTRAIL readers.

The audit is intentionally sample-based and read-only.  It compares the exact
consumer reader with the narrow sidecar adapter and writes only a compact JSON
report; it never copies source payloads or generated graph data.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_cti.evitrail_delivery.sources import (  # noqa: E402
    align_source_record,
    iter_jsonl_evidence,
)

SAMPLES = {
    "orkl": "00007130-a1ca-4f6e-af36-44f78a8fdd8c",
    "circl_misp": "dbc619e5-1b69-44c6-81d0-7fb79390bde4",
    "aptnotes": (
        "aptnotes:report:25e44caab7943e7c51c6c2b68797d41608088c4675e75684a314b21146ce0f18"
    ),
    "cisa": "cisa:advisory:AA23-108",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--processed-root", type=Path, required=True)
    parser.add_argument("--evitrail-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(
        raw_root=args.raw_root.resolve(),
        processed_root=args.processed_root.resolve(),
        evitrail_root=args.evitrail_root.resolve(),
    )
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")


def audit(*, raw_root: Path, processed_root: Path, evitrail_root: Path) -> dict[str, Any]:
    _load_consumer(evitrail_root)
    from evitrail.data.readers import read_aptnotes, read_misp, read_orkl, read_source

    sample_inputs = _load_sample_inputs(raw_root, processed_root)
    result: dict[str, Any] = {
        "contract": {
            "consumer_revision": _git_revision(evitrail_root),
            "five_node_model_unchanged": True,
            "old_complete_handoff_status": "usable_via_read_handoff",
            "raw_roots_status": "not_all_directly_consumer_readable",
        },
        "roots": {
            "raw_root": str(raw_root),
            "processed_root": str(processed_root),
        },
        "sources": {},
    }

    for source, values in sample_inputs.items():
        aligned = align_source_record(
            source,
            values["record"],
            ioc_rows=values["iocs"],
            claim_rows=values["claims"],
        )
        result["sources"][source] = {
            "sample": values["sample"],
            "decision": {
                "orkl": "narrow_adapter",
                "circl_misp": "narrow_adapter",
                "aptnotes": "narrow_adapter",
                "cisa": "handoff_adapter_required",
            }[source],
            "adapter": _aligned_summary(aligned),
            "source_sidecar_parse_rejections": values["parse_rejections"],
        }

    orkl_path = Path(sample_inputs["orkl"]["sample"]["raw_path"])
    misp_path = Path(sample_inputs["circl_misp"]["sample"]["raw_path"])
    apt_index = raw_root / "aptnotes" / "raw" / "repository" / "APTnotes.json"
    apt_normalized = raw_root / "aptnotes" / "normalized" / "reports.jsonl"
    result["sources"]["orkl"]["consumer_smoke"] = _bundle_summary(read_orkl(str(orkl_path)))
    result["sources"]["circl_misp"]["consumer_smoke"] = _bundle_summary(read_misp(str(misp_path)))
    result["sources"]["aptnotes"]["consumer_smoke"] = {
        "raw_index": _bundle_summary(read_aptnotes(str(apt_index))),
        "normalized_reports": _bundle_summary(read_aptnotes(str(apt_normalized))),
    }
    try:
        read_source("cisa", [str(raw_root / "cisa")])
    except ValueError as exc:
        cisa_smoke: dict[str, Any] = {
            "supported": False,
            "error": str(exc),
        }
    else:
        cisa_smoke = {"supported": True}
    result["sources"]["cisa"]["consumer_smoke"] = cisa_smoke

    result["not_event_samples"] = {
        "cisa_attachment": _aligned_summary(
            align_source_record(
                "cisa",
                _first_record(raw_root / "cisa" / "normalized" / "attachments.jsonl"),
            )
        ),
        "aptnotes_document_artifact": {
            "classification": "report_evidence_not_event",
            "sample": _select_keys(
                _first_record(raw_root / "aptnotes" / "normalized" / "document_artifacts.jsonl"),
                ("artifact_id", "report_id", "raw_ref", "local_path", "fetch_status"),
            ),
        },
    }
    return result


def _load_sample_inputs(raw_root: Path, processed_root: Path) -> dict[str, dict[str, Any]]:
    orkl_id = SAMPLES["orkl"]
    misp_uuid = SAMPLES["circl_misp"]
    apt_id = SAMPLES["aptnotes"]
    cisa_id = SAMPLES["cisa"]
    source_specs = {
        "orkl": {
            "record_path": raw_root / "orkl" / "normalized" / "reports.jsonl",
            "record_match": lambda row: row.get("source_record_id") == orkl_id,
            "claim_path": (raw_root / "orkl" / "normalized" / "source_actor_claims.jsonl"),
            "claim_match": lambda row: row.get("subject_record_id") == f"orkl:report:{orkl_id}",
            "ioc_path": processed_root / "normalized" / "orkl" / "ioc_evidence.jsonl",
            "ioc_match": lambda row: row.get("source_record_id") == orkl_id,
        },
        "circl_misp": {
            "record_path": (raw_root / "circl_misp" / "normalized" / "events.jsonl"),
            "record_match": lambda row: row.get("source_uuid") == misp_uuid,
            "claim_path": (raw_root / "circl_misp" / "normalized" / "source_actor_claims.jsonl"),
            "claim_match": lambda row: row.get("event_id") == f"circl-misp:event:{misp_uuid}",
            "ioc_path": processed_root / "normalized" / "misp" / "ioc_evidence.jsonl",
            "ioc_match": lambda row: row.get("source_record_id") == f"circl-misp:event:{misp_uuid}",
        },
        "aptnotes": {
            "record_path": raw_root / "aptnotes" / "normalized" / "reports.jsonl",
            "record_match": lambda row: row.get("report_id") == apt_id,
            "claim_path": (
                raw_root / "aptnotes" / "normalized" / "source_actor_claim_candidates.jsonl"
            ),
            "claim_match": lambda row: row.get("report_id") == apt_id,
            "ioc_path": (processed_root / "normalized" / "aptnotes" / "ioc_evidence.jsonl"),
            "ioc_match": lambda row: row.get("source_record_id") == apt_id,
        },
        "cisa": {
            "record_path": raw_root / "cisa" / "normalized" / "advisories.jsonl",
            "record_match": lambda row: row.get("report_id") == cisa_id,
            "claim_path": (
                raw_root / "cisa" / "normalized" / "source_actor_claim_candidates.jsonl"
            ),
            "claim_match": lambda row: row.get("report_id") == cisa_id,
            "ioc_path": processed_root / "normalized" / "cisa" / "ioc_evidence.jsonl",
            "ioc_match": lambda row: row.get("source_record_id") == cisa_id,
        },
    }

    output: dict[str, dict[str, Any]] = {}
    for source, spec in source_specs.items():
        records, record_rejections = _matching_rows(
            spec["record_path"], source, spec["record_match"], limit=1
        )
        if not records:
            raise RuntimeError(f"sample record missing for {source}")
        claims, claim_rejections = _matching_rows(
            spec["claim_path"], source, spec["claim_match"], limit=20
        )
        iocs, ioc_rejections = _matching_rows(spec["ioc_path"], source, spec["ioc_match"], limit=20)
        record = records[0]
        raw_ref = (
            record.get("raw_ref") or record.get("raw_html_ref") or record.get("raw_metadata_ref")
        )
        raw_path = _resolve_source_ref(raw_root / source, raw_ref)
        if source == "circl_misp":
            raw_path = _resolve_source_ref(raw_root / "circl_misp", raw_ref)
        output[source] = {
            "record": record,
            "claims": claims,
            "iocs": iocs,
            "parse_rejections": (record_rejections + claim_rejections + ioc_rejections),
            "sample": {
                "source_record_id": (
                    record.get("source_record_id")
                    or record.get("source_uuid")
                    or record.get("report_id")
                ),
                "raw_ref": raw_ref,
                "raw_path": str(raw_path),
                "claim_rows": len(claims),
                "ioc_rows": len(iocs),
            },
        }
    return output


def _matching_rows(
    path: Path,
    source: str,
    predicate: Callable[[dict[str, Any]], bool],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for evidence in iter_jsonl_evidence(path, source=source):
        if evidence.rejection:
            rejections.append(evidence.rejection)
        elif evidence.record and predicate(evidence.record) and len(rows) < limit:
            rows.append(evidence.record)
    return rows, rejections


def _first_record(path: Path) -> dict[str, Any]:
    for evidence in iter_jsonl_evidence(path, source="audit"):
        if evidence.record:
            return evidence.record
    raise RuntimeError(f"no JSON object records in {path}")


def _resolve_source_ref(source_root: Path, raw_ref: Any) -> Path:
    value = Path(str(raw_ref or ""))
    if value.is_absolute():
        return value
    return source_root / value


def _aligned_summary(value: Any) -> dict[str, Any]:
    event = value.event
    return {
        "event": (
            None
            if event is None
            else _select_keys(
                event,
                (
                    "event_id",
                    "source_record_id",
                    "event_time",
                    "created",
                    "modified",
                    "published",
                    "fetched_at",
                ),
            )
        ),
        "indicator_count": len(value.indicators),
        "indicator_types": sorted({row["type"] for row in value.indicators}),
        "claim_count": len(value.claims),
        "claim_values": [row["raw_value"] for row in value.claims],
        "claim_scope_usage": sorted({(row["claim_scope"], row["usage"]) for row in value.claims}),
        "rejection_count": len(value.rejections),
        "rejection_reasons": [row["reason"] for row in value.rejections],
    }


def _bundle_summary(bundle: Any) -> dict[str, Any]:
    first = bundle.events[0] if bundle.events else None
    return {
        "events": len(bundle.events),
        "indicators": sum(len(row.indicators) for row in bundle.events),
        "claims": sum(len(row.claims) for row in bundle.events),
        "rejected": len(bundle.rejected),
        "first_event": (
            None
            if first is None
            else {
                "source_record_id": first.event.source_record_id,
                "timestamps": first.event.timestamps,
                "provenance_collected_at": first.event.provenance.collected_at,
                "claim_values": [claim.raw_name for claim in first.claims],
                "claim_scope_usage": sorted({(claim.scope, claim.usage) for claim in first.claims}),
            }
        ),
    }


def _select_keys(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: row[key] for key in keys if row.get(key) is not None}


def _load_consumer(root: Path) -> None:
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def _git_revision(root: Path) -> str | None:
    head = root / ".git"
    if not head.exists():
        return None
    import subprocess

    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() or None


if __name__ == "__main__":
    main()
