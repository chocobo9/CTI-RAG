"""Contract primitives for the reusable intermediate CTI dataset."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

CONTRACT_ID_LENGTH = 24
_ID_DELIMITER = "\x1f"

CONTROLLED_VOCABULARIES: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "connector_source": frozenset(
            {"otx", "mitre", "pdns", "vt", "whois", "pdf", "unknown"}
        ),
        "source_class": frozenset(
            {
                "ontology",
                "weakly_labeled_narrative",
                "unlabeled_narrative",
                "infrastructure",
                "unknown",
            }
        ),
        "publisher_category": frozenset(
            {
                "vendor",
                "government",
                "community",
                "knowledge_base",
                "threat_intelligence_platform",
                "other",
                "unknown",
            }
        ),
        "entity_type": frozenset(
            {
                "actor",
                "campaign",
                "family",
                "technique",
                "tactic",
                "indicator",
                "domain",
                "ip",
                "url",
                "file_hash",
                "email",
                "asn",
                "location",
                "sector",
                "organization",
                "cve",
                "tag",
                "external_reference",
                "source",
                "source_contributor",
                "timestamp",
                "mitigation",
                "detection-strategy",
                "unknown",
            }
        ),
        "predicate.mapped_value": frozenset(
            {
                "uses",
                "attributed-to",
                "targets",
                "resolves-to",
                "belongs-to",
                "located-in",
                "uses-nameserver",
                "has-subdomain",
                "mitigates",
                "detects",
                "unmapped",
            }
        ),
        "predicate.mapping_status": frozenset(
            {
                "mapped",
                "source_backed_unmapped",
                "document_proposed_unsupported",
                "unknown",
            }
        ),
        "extraction_method": frozenset(
            {
                "source_field",
                "structured_relation",
                "structured_cooccurrence",
                "text_extraction",
                "inferred_join",
                "manual_review",
                "unknown",
            }
        ),
        "resolution_method": frozenset(
            {
                "exact_id",
                "exact_name",
                "exact_alias",
                "embedded_id",
                "orphan",
                "unresolved",
                "not_applicable",
            }
        ),
        "merge_candidate_reason": frozenset(
            {"ambiguous_name", "ambiguous_alias", "substring", "unknown"}
        ),
        "ambiguity.status": frozenset(
            {"resolved", "unambiguous", "ambiguous", "candidate", "unresolved", "not_applicable"}
        ),
        "timestamp_basis": frozenset(
            {"published", "source_modified", "observed_range", "fetched_only", "missing", "mixed"}
        ),
        "label_availability": frozenset({"direct", "indirect", "none", "unknown"}),
        "signal_type": frozenset(
            {
                "direct_attribution",
                "weak_direct_attribution",
                "indirect_attribution",
                "supporting_evidence",
                "conflicting_attribution",
                "no_attribution",
            }
        ),
        "processing_status.status": frozenset({"ok", "partial", "failed", "skipped"}),
    }
)


def contract_id(prefix: str, parts: Sequence[Any], length: int = CONTRACT_ID_LENGTH) -> str:
    """Mint a deterministic contract id from a documented input tuple.

    Slot values are separated with ``\\x1f`` so adjacent tuple positions cannot
    smear together into the same hash input.
    """
    if not prefix:
        raise ValueError("prefix is required")
    if length <= 0:
        raise ValueError("length must be positive")
    payload = _ID_DELIMITER.join(_slot(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _slot(value: Any) -> str:
    return json.dumps(_typed_value(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _typed_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": value}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, tuple):
        return {"type": "tuple", "value": [_typed_value(item) for item in value]}
    if isinstance(value, list):
        return {"type": "list", "value": [_typed_value(item) for item in value]}
    if isinstance(value, dict):
        pairs = [(_typed_value(key), _typed_value(item)) for key, item in value.items()]
        pairs.sort(
            key=lambda pair: json.dumps(
                pair[0], ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
        )
        return {"type": "object", "value": pairs}
    raise TypeError(f"unsupported contract id slot type: {type(value).__name__}")
