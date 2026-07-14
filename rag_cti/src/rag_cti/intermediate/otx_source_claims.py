"""Offline OTX source-attribution claim normalization.

This module intentionally stops at source claims.  It performs no attribution
assessment, filtering, indicator projection, enrichment, or network access.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rag_cti.intermediate.contract import contract_id

_WHITESPACE_RE = re.compile(r"\s+")
_AND_RE = re.compile(r"\band\b", re.IGNORECASE)
_ACTOR_RE = re.compile(r"^(?:APT\s*-?\s*[A-Z0-9-]+|[A-Z][A-Za-z0-9-]*(?:[- ][A-Z0-9][A-Za-z0-9-]*){0,4})$")
_NON_ACTOR_VALUES = {"advisory", "informational", "malware advisory", "n/a", "none", "unknown"}
_ORG_RE = re.compile(r"\b(?:co\.?|corp\.?|corporation|inc\.?|llc|ltd\.?|limited|media)\b", re.I)


@dataclass(frozen=True)
class OTXSourceClaimArtifacts:
    """In-memory artifacts produced without network or enrichment work."""

    event_rows: list[dict[str, Any]]
    claim_rows: list[dict[str, Any]]
    summary: dict[str, Any]


class OTXSourceClaimNormalizer:
    """Normalize local OTX Pulse actor fields against one loaded taxonomy."""

    def __init__(self, mitre_attack_path: Path) -> None:
        self._taxonomy = _load_taxonomy(mitre_attack_path)

    def normalize(
        self,
        pulse: Mapping[str, Any],
        *,
        raw_provenance: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Return one retained Event and zero or more source-claim rows."""

        source_id = str(pulse.get("id") or "").strip()
        if not source_id:
            raise ValueError("each Pulse must have a non-empty id")
        raw_value = pulse.get("adversary")
        raw_text = raw_value.strip() if isinstance(raw_value, str) else ""
        parsed = _parse_claims(raw_text)
        resolved = [_resolve_claim(claim, self._taxonomy) for claim in parsed]
        resolved_ids = _unique(
            actor_id for item in resolved for actor_id in item["resolved_actor_ids"]
        )
        status = _event_status(resolved, resolved_ids)
        provenance = dict(raw_provenance or {})
        event_id = f"otx:pulse:{source_id}"
        event_row = {
            "event_id": event_id,
            "source": "otx",
            "source_record_id": source_id,
            "name": pulse.get("name"),
            "description": pulse.get("description"),
            "source_field": "adversary",
            "raw_field_value": raw_text or None,
            "actor_label_status": status,
            "resolved_actor_ids": resolved_ids,
            "candidate_actor_ids": _unique(
                actor_id for item in resolved for actor_id in item["candidate_actor_ids"]
            ),
            "raw_provenance": provenance,
        }
        claim_rows = []
        for claim, resolution in zip(parsed, resolved, strict=True):
            claim_rows.append(
                {
                    "claim_id": contract_id(
                        "otx_actor_label_claim",
                        (event_id, "adversary", claim.label_index, claim.raw_label, claim.parse_status),
                    ),
                    "event_id": event_id,
                    "source": "otx",
                    "source_record_id": source_id,
                    "source_field": "adversary",
                    "raw_field_value": claim.raw_field_value,
                    "raw_label": claim.raw_label,
                    "normalized_label": claim.raw_label.lower(),
                    "label_index": claim.label_index,
                    "parse_status": claim.parse_status,
                    **resolution,
                    "raw_provenance": provenance,
                    "notes": list(claim.notes),
                }
            )
        return event_row, claim_rows


@dataclass(frozen=True)
class _ParsedClaim:
    raw_field_value: str
    raw_label: str
    label_index: int
    parse_status: str
    notes: tuple[str, ...] = ()


def build_otx_source_claim_artifacts(
    pulses: Iterable[Mapping[str, Any]],
    mitre_attack_path: Path,
    *,
    raw_provenance_by_pulse_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> OTXSourceClaimArtifacts:
    """Return deterministic Event, claim, and summary artifacts for local Pulses."""

    normalizer = OTXSourceClaimNormalizer(mitre_attack_path)
    provenance = raw_provenance_by_pulse_id or {}
    event_rows: list[dict[str, Any]] = []
    claim_rows: list[dict[str, Any]] = []
    for pulse in pulses:
        source_id = str(pulse.get("id") or "").strip()
        event_row, pulse_claim_rows = normalizer.normalize(
            pulse,
            raw_provenance=provenance.get(source_id),
        )
        event_rows.append(event_row)
        claim_rows.extend(pulse_claim_rows)
    counts = Counter(row["actor_label_status"] for row in event_rows)
    return OTXSourceClaimArtifacts(
        event_rows=event_rows,
        claim_rows=claim_rows,
        summary={
            "event_count": len(event_rows),
            "claim_count": len(claim_rows),
            "status_counts": dict(sorted(counts.items())),
        },
    )


def _load_taxonomy(path: Path) -> dict[str, Any]:
    bundle = json.loads(Path(path).read_text(encoding="utf-8"))
    objects = bundle.get("objects", []) if isinstance(bundle, Mapping) else []
    matches: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    version = next((str(bundle[key]) for key in ("x_mitre_version", "spec_version", "modified") if bundle.get(key)), None)
    for item in objects if isinstance(objects, list) else []:
        if not isinstance(item, Mapping) or item.get("type") != "intrusion-set":
            continue
        attack_id = _attack_id(item)
        stix_id = str(item.get("id") or "")
        if not stix_id or not item.get("name"):
            continue
        actor_id = f"actor_{attack_id}" if attack_id else contract_id("mitre_actor", (stix_id,))
        labels = [(str(item["name"]), "mitre_exact_name")]
        labels.extend((alias, "mitre_exact_alias") for alias in _string_list(item.get("aliases")))
        labels.extend((alias, "mitre_exact_alias") for alias in _string_list(item.get("x_mitre_aliases")))
        for label, method in labels:
            matches[_normalize(label)].setdefault(actor_id, (label, method))
    return {"matches": matches, "version": version}


def _attack_id(item: Mapping[str, Any]) -> str:
    refs = item.get("external_references")
    if not isinstance(refs, list):
        return ""
    for ref in refs:
        if isinstance(ref, Mapping) and ref.get("source_name") == "mitre-attack":
            return str(ref.get("external_id") or "")
    return ""


def _resolve_claim(claim: _ParsedClaim, taxonomy: Mapping[str, Any]) -> dict[str, Any]:
    common = {
        "resolved_actor_ids": [],
        "candidate_actor_ids": [],
        "match_method": None,
        "matched_taxonomy_labels": [],
        "resolution_taxonomy": "mitre-attack-enterprise",
        "taxonomy_version": taxonomy["version"],
    }
    if claim.parse_status != "parsed":
        return {"resolution_status": claim.parse_status, **common}
    matches = taxonomy["matches"].get(claim.raw_label, {})
    if not matches:
        return {"resolution_status": "unmapped_actor_like", **common}
    actor_ids = sorted(matches)
    labels = _unique(matches[actor_id][0] for actor_id in actor_ids)
    if len(actor_ids) > 1:
        return {
            "resolution_status": "ambiguous_taxonomy",
            **common,
            "candidate_actor_ids": actor_ids,
            "match_method": "mitre_exact_label",
            "matched_taxonomy_labels": labels,
        }
    return {
        "resolution_status": "resolved",
        **common,
        "resolved_actor_ids": actor_ids,
        "match_method": matches[actor_ids[0]][1],
        "matched_taxonomy_labels": labels,
    }


def _event_status(resolved: list[dict[str, Any]], actor_ids: list[str]) -> str:
    if not resolved:
        return "missing"
    if len(actor_ids) == 1:
        count = sum(bool(item["resolved_actor_ids"]) for item in resolved)
        return "resolved_alias_collapsed" if count > 1 else "resolved_single"
    if len(actor_ids) > 1:
        return "resolved_multi_actor"
    statuses = {item["resolution_status"] for item in resolved}
    for resolution_status, event_status in (
        ("ambiguous_taxonomy", "ambiguous_taxonomy"),
        ("unmapped_actor_like", "unmapped_actor_like"),
        ("parse_ambiguous", "parse_ambiguous"),
        ("non_actor_value", "non_attributing"),
    ):
        if resolution_status in statuses:
            return event_status
    return "non_attributing"


def _parse_claims(raw_value: str) -> list[_ParsedClaim]:
    raw = _normalize(raw_value)
    if not raw:
        return []
    if _is_non_actor(raw):
        return [_ParsedClaim(raw, raw, 0, "non_actor_value", ("non-actor value preserved",))]
    claims: list[_ParsedClaim] = []
    for index, label in enumerate(_split_actor_field(raw)):
        if "/" in label and not _is_clean_slash_pair(label):
            claims.append(_ParsedClaim(raw, label, index, "parse_ambiguous", ("ambiguous slash value preserved",)))
        elif _is_non_actor(label):
            claims.append(_ParsedClaim(raw, label, index, "non_actor_value"))
        else:
            claims.append(_ParsedClaim(raw, label, index, "parsed"))
    return claims


def _split_actor_field(value: str) -> list[str]:
    parts: list[str] = []
    start = depth = 0
    for index, char in enumerate(value):
        depth += 1 if char == "(" else -1 if char == ")" and depth else 0
        if depth == 0 and char in {",", "|", ";", "+"}:
            if part := _normalize(value[start:index]):
                parts.append(part)
            start = index + 1
    if part := _normalize(value[start:]):
        parts.append(part)
    expanded: list[str] = []
    for part in parts:
        and_parts = _split_top_level_and(part)
        for label in and_parts:
            expanded.extend(_normalize(piece) for piece in label.split("/")) if _is_clean_slash_pair(label) else expanded.append(label)
    return [label for label in expanded if label]


def _split_top_level_and(value: str) -> list[str]:
    for match in _AND_RE.finditer(value):
        if _parentheses_depth(value, match.start()) == 0:
            left, right = _normalize(value[: match.start()]), _normalize(value[match.end() :])
            if _looks_actor_like(left) and _looks_actor_like(right):
                return [left, right]
    return [value]


def _parentheses_depth(value: str, position: int) -> int:
    depth = 0
    for char in value[:position]:
        depth += 1 if char == "(" else -1 if char == ")" and depth else 0
    return depth


def _is_clean_slash_pair(value: str) -> bool:
    if value.count("/") != 1 or _is_url(value):
        return False
    left, right = (_normalize(part) for part in value.split("/", 1))
    return bool(left and right and " " not in left and " " not in right and _looks_actor_like(left) and _looks_actor_like(right))


def _is_non_actor(value: str) -> bool:
    normalized = _normalize(value)
    return normalized.lower() in _NON_ACTOR_VALUES or _is_url(normalized) or bool(_ORG_RE.search(normalized))


def _is_url(value: str) -> bool:
    lowered = value.lower()
    parsed = urlparse(value)
    return "://" in lowered or lowered.startswith(("www.", "http:", "https:")) or bool(parsed.scheme and parsed.netloc)


def _looks_actor_like(value: str) -> bool:
    normalized = _normalize(value)
    return bool(normalized and len(normalized) <= 80 and not _is_non_actor(normalized) and _ACTOR_RE.match(normalized))


def _normalize(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip())


def _string_list(value: Any) -> list[str]:
    return [_normalize(item) for item in value if isinstance(item, str) and _normalize(item)] if isinstance(value, list) else []


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))
