"""Build the final actor-evidenced OTX dataset in one RawStore pass."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from rag_cti.intermediate.otx_indicator_summary import summarize_otx_pulse_indicators
from rag_cti.intermediate.otx_source_claims import OTXSourceClaimNormalizer
from rag_cti.intermediate.otx_temporal_profile import build_otx_temporal_profile


def build_routed_otx_dataset(
    *,
    routing_manifest: Path,
    raw_root: Path,
    mitre_taxonomy: Path,
    discovery_run_dir: Path,
    detail_audit_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Write routed Event artifacts while never expanding deferred candidates."""

    routing_rows = _read_jsonl(routing_manifest)
    pulse_ids = [str(row.get("pulse_id") or "") for row in routing_rows]
    if not all(pulse_ids) or len(set(pulse_ids)) != len(pulse_ids):
        raise ValueError("routing manifest must contain one non-empty unique pulse_id per row")
    decisions = Counter(str(row.get("decision") or "") for row in routing_rows)
    acquire_ids = sorted(
        str(row["pulse_id"])
        for row in routing_rows
        if str(row.get("decision") or "").startswith("acquire_")
    )
    detail_audit = _read_json(detail_audit_path)
    valid_detail = int(detail_audit.get("valid_detail_coverage", -1))
    invalid_detail = int(detail_audit.get("invalid_or_missing_count", -1))
    if valid_detail != len(acquire_ids) or invalid_detail != 0:
        raise ValueError(
            "detail audit does not cover the routed acquire population: "
            f"valid={valid_detail} expected={len(acquire_ids)} invalid={invalid_detail}"
        )

    paths = {pulse_id: _latest_raw_path(raw_root, pulse_id) for pulse_id in acquire_ids}
    output_dir.mkdir(parents=True, exist_ok=True)
    normalizer = OTXSourceClaimNormalizer(mitre_taxonomy)
    claim_statuses: Counter[str] = Counter()
    claim_count = 0

    event_path = output_dir / "events.jsonl"
    claim_path = output_dir / "source_attribution_claims.jsonl"
    summary_path = output_dir / "event_indicator_summaries.jsonl"

    def rows() -> Iterator[tuple[Mapping[str, Any], str | None]]:
        nonlocal claim_count
        with (
            event_path.open("w", encoding="utf-8") as event_fh,
            claim_path.open("w", encoding="utf-8") as claim_fh,
            summary_path.open("w", encoding="utf-8") as summary_fh,
        ):
            for pulse_id in acquire_ids:
                path = paths[pulse_id]
                raw_bytes = path.read_bytes()
                wrapper = json.loads(raw_bytes)
                pulse = wrapper.get("payload") if isinstance(wrapper, Mapping) else None
                if not isinstance(pulse, Mapping):
                    raise ValueError(f"Pulse detail is not a RawStore wrapper: {path}")
                source_id = str(wrapper.get("source_id") or pulse.get("id") or "")
                if source_id != pulse_id or str(pulse.get("id") or "") != pulse_id:
                    raise ValueError(f"Pulse id mismatch for {pulse_id}: {source_id}")
                raw_provenance = {
                    "raw_path": path.as_posix(),
                    "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                    "raw_layout": "rawstore_wrapper.payload",
                    "fetched_at": wrapper.get("fetched_at"),
                }
                event, claims = normalizer.normalize(pulse, raw_provenance=raw_provenance)
                event_fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                claim_statuses[str(event["actor_label_status"])] += 1
                for claim in claims:
                    claim_fh.write(json.dumps(claim, ensure_ascii=False, sort_keys=True) + "\n")
                claim_count += len(claims)
                summary = summarize_otx_pulse_indicators(
                    pulse, raw_record_bytes=len(raw_bytes)
                )
                summary_fh.write(json.dumps(summary, ensure_ascii=False, sort_keys=True) + "\n")
                yield pulse, _text(wrapper.get("fetched_at"))

    temporal_profile = build_otx_temporal_profile(rows(), since=None, until=None)
    temporal_path = output_dir / "dataset_temporal_profile.json"
    _write_json(temporal_path, temporal_profile)

    terminal_counts = _terminal_counts(discovery_run_dir)
    query_list = _read_json(discovery_run_dir / "mitre_actor_query_list.json")
    query_count = len(query_list.get("queries", []))
    outputs = (event_path, claim_path, summary_path, temporal_path)
    manifest = {
        "contract": "otx_actor_evidenced_event_dataset_v1",
        "population": {
            "candidate_count": len(routing_rows),
            "event_count": len(acquire_ids),
            "deferred_count": len(routing_rows) - len(acquire_ids),
            "routing_decision_counts": dict(sorted(decisions.items())),
        },
        "discovery_query_count": query_count,
        "discovery_terminal_counts": terminal_counts,
        "detail_coverage": {
            "valid": valid_detail,
            "invalid_or_missing": invalid_detail,
        },
        "source_claim_count": claim_count,
        "source_claim_status_counts": dict(sorted(claim_statuses.items())),
        "indicator_occurrence_count": temporal_profile["indicator_occurrence_count"],
        "indicator_materialization": "summary_only",
        "time_filter": {"since": None, "until": None, "status": "unfiltered"},
        "input_sha256": {
            "routing_manifest": _sha256(routing_manifest),
            "mitre_taxonomy": _sha256(mitre_taxonomy),
            "detail_audit": _sha256(detail_audit_path),
        },
        "output_sha256": {path.name: _sha256(path) for path in outputs},
        "notes": [
            "Query actor associations are discovery provenance, not attribution.",
            "Multi-actor and ambiguous source claims are retained.",
            "IOC occurrences remain in Pulse raw and are not flattened here.",
            "Enrichment and attribution confidence are outside this dataset.",
        ],
    }
    _write_json(output_dir / "dataset_manifest.json", manifest)
    return manifest


def _latest_raw_path(raw_root: Path, pulse_id: str) -> Path:
    paths = sorted((raw_root / "otx" / pulse_id).glob("*.json"), key=lambda path: path.name)
    if not paths:
        raise FileNotFoundError(f"missing routed Pulse detail: {pulse_id}")
    return paths[-1]


def _terminal_counts(run_dir: Path) -> dict[str, int]:
    latest: dict[str, str] = {}
    for row in _read_jsonl(run_dir / "query_terminal_states.jsonl"):
        query = str(row.get("query_normalized") or "")
        status = str(row.get("status") or row.get("terminal_state") or "")
        if query and status:
            latest[query] = status
    return dict(sorted(Counter(latest.values()).items()))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object in {path}")
            rows.append(value)
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any) -> str | None:
    text = value.strip() if isinstance(value, str) else ""
    return text or None
