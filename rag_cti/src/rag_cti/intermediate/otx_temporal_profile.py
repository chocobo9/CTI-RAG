"""Descriptive time-field coverage for an OTX Pulse dataset."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def build_otx_temporal_profile(
    rows: Iterable[tuple[Mapping[str, Any], str | None]],
    *,
    since: str | None,
    until: str | None,
) -> dict[str, Any]:
    """Summarize observed timestamps without treating their bounds as selection bounds."""

    event_stats = {name: _stats() for name in ("pulse.created", "pulse.modified", "raw.fetched_at")}
    indicator_stats = {name: _indicator_stats() for name in ("indicator.created", "indicator.expiration")}
    event_count = 0
    occurrence_count = 0
    for pulse, fetched_at in rows:
        event_count += 1
        _add(event_stats["pulse.created"], pulse.get("created"))
        _add(event_stats["pulse.modified"], pulse.get("modified"))
        _add(event_stats["raw.fetched_at"], fetched_at)
        indicators = pulse.get("indicators")
        values = indicators if isinstance(indicators, list) else []
        occurrence_count += len(values)
        for field in ("created", "expiration"):
            stats = indicator_stats[f"indicator.{field}"]
            event_has_value = False
            for indicator in values:
                value = indicator.get(field) if isinstance(indicator, Mapping) else None
                if _add(stats, value):
                    stats["occurrence_value_coverage"]["present"] += 1
                    event_has_value = True
                else:
                    stats["occurrence_value_coverage"]["missing"] += 1
            stats["event_coverage"]["present" if event_has_value else "missing"] += 1

    status = "unfiltered" if since is None and until is None else "filtered"
    return {
        "event_count": event_count,
        "indicator_occurrence_count": occurrence_count,
        "time_filter": {"since": since, "until": until, "status": status},
        "fields": {**event_stats, **indicator_stats},
    }


def _stats() -> dict[str, Any]:
    return {"present": 0, "missing": 0, "min": None, "max": None}


def _indicator_stats() -> dict[str, Any]:
    return {
        "event_coverage": {"present": 0, "missing": 0},
        "occurrence_value_coverage": {"present": 0, "missing": 0},
        "min": None,
        "max": None,
    }


def _add(stats: dict[str, Any], value: Any) -> bool:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        if "missing" in stats:
            stats["missing"] += 1
        return False
    if "present" in stats:
        stats["present"] += 1
    stats["min"] = text if stats["min"] is None else min(stats["min"], text)
    stats["max"] = text if stats["max"] is None else max(stats["max"], text)
    return True
