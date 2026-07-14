"""Offline, Event-level summaries of source-provided OTX indicators."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any


def summarize_otx_pulse_indicators(
    pulse: Mapping[str, Any], *, raw_record_bytes: int
) -> dict[str, Any]:
    """Summarize indicators without materializing Event-Indicator occurrences."""

    source_record_id = str(pulse.get("id") or "").strip()
    if not source_record_id:
        raise ValueError("each Pulse must have a non-empty id")
    raw_indicators = pulse.get("indicators", [])
    indicators = raw_indicators if isinstance(raw_indicators, list) else []
    type_counts: Counter[str] = Counter()
    active_counts: Counter[str] = Counter()
    source_created: list[str] = []
    source_expiration: list[str] = []
    explicit_starts: list[str] = []
    explicit_ends: list[str] = []
    for indicator in indicators:
        if not isinstance(indicator, Mapping):
            active_counts["unknown"] += 1
            continue
        indicator_type = indicator.get("type")
        if isinstance(indicator_type, str) and indicator_type.strip():
            type_counts[indicator_type.strip()] += 1
        active = indicator.get("is_active")
        active_counts["true" if active is True else "false" if active is False else "unknown"] += 1
        _append_time(source_created, indicator.get("created"))
        _append_time(source_expiration, indicator.get("expiration"))
        _append_time(explicit_starts, indicator.get("first_seen"))
        _append_time(explicit_ends, indicator.get("last_seen"))

    count = len(indicators)
    return {
        "event_id": f"otx:pulse:{source_record_id}",
        "source_record_id": source_record_id,
        "indicator_count": count,
        "type_counts": dict(sorted(type_counts.items())),
        "source_created_min": min(source_created, default=None),
        "source_created_max": max(source_created, default=None),
        "source_expiration_min": min(source_expiration, default=None),
        "source_expiration_max": max(source_expiration, default=None),
        "active_true_count": active_counts["true"],
        "active_false_count": active_counts["false"],
        "active_unknown_count": active_counts["unknown"],
        "explicit_activity_start_min": min(explicit_starts, default=None),
        "explicit_activity_start_max": max(explicit_starts, default=None),
        "explicit_activity_start_count": len(explicit_starts),
        "explicit_activity_end_min": min(explicit_ends, default=None),
        "explicit_activity_end_max": max(explicit_ends, default=None),
        "explicit_activity_end_count": len(explicit_ends),
        "raw_record_bytes": raw_record_bytes,
        "materialization_status": "summary_only" if count else "none",
    }


def _append_time(values: list[str], value: Any) -> None:
    if isinstance(value, str) and value.strip():
        values.append(value.strip())
