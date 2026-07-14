"""Route OTX discovery candidates into detail acquisition without network access.

Query matches are retained as provenance only.  Acquisition is driven solely by
actor evidence present in the OTX search result itself.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_cti.intermediate.otx_source_claims import OTXSourceClaimNormalizer


@dataclass(frozen=True)
class OTXDetailAcquisitionArtifacts:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def build_detail_acquisition_artifacts(
    candidate_manifest: Path,
    mitre_attack_path: Path,
    raw_root: Path,
) -> OTXDetailAcquisitionArtifacts:
    """Return exactly one deterministic routing row per discovery candidate."""

    candidates = _read_jsonl(candidate_manifest)
    normalizer = OTXSourceClaimNormalizer(mitre_attack_path)
    raw_cache: dict[Path, Mapping[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        pulse_id = str(candidate.get("pulse_id") or "").strip()
        if not pulse_id:
            raise ValueError("each candidate must have a non-empty pulse_id")
        if pulse_id in seen:
            raise ValueError(f"duplicate candidate pulse_id: {pulse_id}")
        seen.add(pulse_id)
        pulse, raw_refs = _find_search_pulse(candidate, pulse_id, candidate_manifest, raw_cache)
        row = _route_candidate(candidate, pulse, raw_refs, normalizer, raw_root)
        rows.append(row)

    decisions = Counter(row["decision"] for row in rows)
    resolution = Counter(row["resolution_status"] for row in rows)
    acquire_count = sum(count for name, count in decisions.items() if name.startswith("acquire_"))
    acquire_rows = [row for row in rows if row["decision"].startswith("acquire_")]
    acquire_existing = sum(row["existing_detail"] for row in acquire_rows)
    return OTXDetailAcquisitionArtifacts(
        rows=rows,
        summary={
            "candidate_count": len(rows),
            "acquire_count": acquire_count,
            "deferred_count": len(rows) - acquire_count,
            "existing_detail_count": sum(row["existing_detail"] for row in rows),
            "acquire_existing_detail_count": acquire_existing,
            "acquire_missing_detail_count": acquire_count - acquire_existing,
            "decision_counts": dict(sorted(decisions.items())),
            "resolution_status_counts": dict(sorted(resolution.items())),
        },
    )


def _route_candidate(
    candidate: Mapping[str, Any],
    pulse: Mapping[str, Any],
    raw_refs: list[dict[str, Any]],
    normalizer: OTXSourceClaimNormalizer,
    raw_root: Path,
) -> dict[str, Any]:
    pulse_id = str(candidate["pulse_id"])
    adversary = pulse.get("adversary")
    adversary_text = adversary.strip() if isinstance(adversary, str) else ""
    adversary_event, adversary_claims = normalizer.normalize(
        {"id": pulse_id, "adversary": adversary_text}, raw_provenance={"search_raw_refs": raw_refs}
    )
    actor_tags: list[dict[str, Any]] = []
    tag_claims: list[dict[str, Any]] = []
    tags = pulse.get("tags") if isinstance(pulse.get("tags"), list) else []
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip():
            continue
        _, claims = normalizer.normalize({"id": pulse_id, "adversary": tag.strip()})
        relevant = [
            claim
            for claim in claims
            if claim["resolution_status"] in {"resolved", "ambiguous_taxonomy"}
        ]
        if relevant:
            actor_tags.append(
                {
                    "raw_value": tag,
                    "resolution_statuses": sorted({claim["resolution_status"] for claim in relevant}),
                    "resolved_actor_ids": _unique(
                        actor_id for claim in relevant for actor_id in claim["resolved_actor_ids"]
                    ),
                    "candidate_actor_ids": _unique(
                        actor_id for claim in relevant for actor_id in claim["candidate_actor_ids"]
                    ),
                }
            )
            tag_claims.extend(relevant)

    statuses = {claim["resolution_status"] for claim in adversary_claims + tag_claims}
    resolved_ids = _unique(
        actor_id for claim in adversary_claims + tag_claims for actor_id in claim["resolved_actor_ids"]
    )
    candidate_ids = _unique(
        actor_id for claim in adversary_claims + tag_claims for actor_id in claim["candidate_actor_ids"]
    )
    if len(resolved_ids) > 1 or adversary_event["actor_label_status"] == "resolved_multi_actor":
        decision, status, reason = (
            "acquire_multi_actor",
            "resolved_multi_actor",
            "OTX source actor evidence resolves to multiple MITRE actors",
        )
    elif "ambiguous_taxonomy" in statuses or "parse_ambiguous" in statuses:
        decision, status, reason = (
            "acquire_ambiguous_actor",
            "ambiguous_actor",
            "OTX source actor evidence is ambiguous and must be preserved",
        )
    elif adversary_text and "unmapped_actor_like" in statuses:
        decision, status, reason = (
            "acquire_unmapped_actor_label",
            "unmapped_actor_like",
            "OTX adversary field contains an actor-like label absent from the taxonomy",
        )
    elif resolved_ids:
        decision, status, reason = (
            "acquire_actor_evidenced",
            adversary_event["actor_label_status"] if adversary_claims else "resolved_single",
            "OTX adversary field or actor-related tag maps to a MITRE actor",
        )
    else:
        decision, status, reason = (
            "deferred_query_only",
            adversary_event["actor_label_status"],
            "candidate has discovery provenance but no source-level actor evidence",
        )
    return {
        "event_id": f"otx:pulse:{pulse_id}",
        "pulse_id": pulse_id,
        "source_evidence": {
            "adversary": adversary_text or None,
            "actor_related_tags": actor_tags,
            "search_raw_refs": raw_refs,
        },
        "resolution_status": status,
        "resolved_actor_ids": resolved_ids,
        "candidate_actor_ids": candidate_ids,
        "decision": decision,
        "reason": reason,
        "existing_detail": (raw_root / "otx" / pulse_id).is_dir()
        and any((raw_root / "otx" / pulse_id).glob("*.json")),
    }


def _find_search_pulse(
    candidate: Mapping[str, Any],
    pulse_id: str,
    manifest: Path,
    cache: dict[Path, Mapping[str, Any]],
) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    refs: list[dict[str, Any]] = []
    for path_row in candidate.get("discovery_paths", []):
        ref = path_row.get("search_raw_ref") if isinstance(path_row, Mapping) else None
        if not isinstance(ref, Mapping) or not ref.get("path"):
            continue
        path = _resolve_path(Path(str(ref["path"])), manifest)
        wrapper = cache.get(path)
        if wrapper is None:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, Mapping):
                raise ValueError(f"search raw must be a JSON object: {path}")
            wrapper = value
            cache[path] = wrapper
        payload = wrapper.get("payload")
        results = payload.get("results", []) if isinstance(payload, Mapping) else []
        for result in results if isinstance(results, list) else []:
            if isinstance(result, Mapping) and str(result.get("id") or "") == pulse_id:
                refs.append(dict(ref))
                return result, refs
    raise ValueError(f"candidate {pulse_id} was not found in its search raw references")


def _resolve_path(path: Path, manifest: Path) -> Path:
    if path.is_absolute() or path.exists():
        return path
    for parent in manifest.resolve().parents:
        candidate = parent / path
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"search raw reference does not exist: {path}")


def _read_jsonl(path: Path) -> list[Mapping[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("candidate manifest must contain JSON objects")
    return rows


def _unique(values: Any) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))
