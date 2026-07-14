"""Local derived views over OTX RawStore records.

These helpers never fetch network data and never mutate raw records. They join
the OTX pulse-detail raw response with the richer OTX indicator endpoint pages
when those pages are available.
"""

from __future__ import annotations

import re
from typing import Any

from rag_cti.store.raw_store import RawStore

REQUIRED_PULSE_DETAIL_FIELDS = (
    "id",
    "name",
    "description",
    "author_name",
    "modified",
    "created",
    "tags",
    "references",
    "public",
    "adversary",
    "targeted_countries",
    "malware_families",
    "attack_ids",
    "industries",
    "TLP",
    "indicators",
    "revision",
    "groups",
    "in_group",
    "author",
    "is_subscribing",
)

_INDICATOR_PAGE_RE = re.compile(
    r"^(?P<pulse_id>.+?)(?:_l(?P<limit>\d+))?_(?P<page>\d{4})_[0-9a-f]{24}$"
)


def indicator_page_source_ids(store: RawStore, pulse_id: str) -> list[str]:
    """Return indicator-page source ids for a pulse, sorted by page number."""
    return indicator_page_source_index(store).get(pulse_id, [])


def indicator_page_source_index(store: RawStore) -> dict[str, list[str]]:
    """Return ``pulse_id -> indicator-page source ids`` for all OTX indicator pages."""
    groups: dict[tuple[str, int], list[tuple[int, str]]] = {}
    latest_by_group: dict[tuple[str, int], str] = {}
    for source_id in store.source_ids("otx_indicator_page"):
        match = _INDICATOR_PAGE_RE.match(source_id)
        if not match:
            continue
        pulse_id = match.group("pulse_id")
        page_limit = int(match.group("limit") or 1000)
        group_key = (pulse_id, page_limit)
        groups.setdefault(group_key, []).append((int(match.group("page")), source_id))
        versions = store.versions("otx_indicator_page", source_id)
        if versions and versions[-1] > latest_by_group.get(group_key, ""):
            latest_by_group[group_key] = versions[-1]

    selected: dict[str, tuple[int, str, list[tuple[int, str]]]] = {}
    for (pulse_id, page_limit), pages in groups.items():
        latest = latest_by_group.get((pulse_id, page_limit), "")
        current = selected.get(pulse_id)
        if current is None or (latest, page_limit) > (current[1], current[0]):
            selected[pulse_id] = (page_limit, latest, pages)

    index: dict[str, list[str]] = {}
    for pulse_id, (_page_limit, _latest, pages) in selected.items():
        index[pulse_id] = [source_id for _page, source_id in sorted(pages)]
    return index


def latest_indicator_pages(
    store: RawStore,
    pulse_id: str,
    page_index: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Read latest OTX indicator endpoint pages for a pulse."""
    pages: list[dict[str, Any]] = []
    if page_index is not None:
        source_ids = page_index.get(pulse_id, [])
    else:
        source_ids = indicator_page_source_ids(store, pulse_id)
    for source_id in source_ids:
        payload = store.latest("otx_indicator_page", source_id)
        if isinstance(payload, dict):
            pages.append(payload)
    return pages


def indicator_results_from_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten OTX indicator endpoint ``results[]`` across pages."""
    indicators: list[dict[str, Any]] = []
    for page in pages:
        results = page.get("results")
        if not isinstance(results, list):
            continue
        indicators.extend(row for row in results if isinstance(row, dict))
    return indicators


def pulse_with_full_indicators(
    pulse: dict[str, Any],
    indicator_pages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return an in-memory pulse view using endpoint indicators when present."""
    indicators = indicator_results_from_pages(indicator_pages)
    if not indicator_pages:
        return dict(pulse)
    enriched = dict(pulse)
    enriched["indicators"] = indicators
    return enriched


def latest_pulse_with_full_indicators(
    store: RawStore,
    pulse_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Read latest pulse detail and merge latest endpoint indicators if present."""
    versions = store.versions("otx", pulse_id)
    if not versions:
        return None, None
    fetched_at = versions[-1]
    pulse = store.read("otx", pulse_id, fetched_at)
    if not isinstance(pulse, dict):
        return None, fetched_at
    return pulse_with_full_indicators(pulse, latest_indicator_pages(store, pulse_id)), fetched_at


def indicator_completeness(
    pulse_id: str,
    pulse: dict[str, Any],
    indicator_pages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize indicator endpoint coverage for one pulse."""
    detail_indicators = pulse.get("indicators")
    detail_count = len(detail_indicators) if isinstance(detail_indicators, list) else 0
    endpoint_count = _endpoint_count(indicator_pages)
    endpoint_results_total = len(indicator_results_from_pages(indicator_pages))
    missing_fields = [field for field in REQUIRED_PULSE_DETAIL_FIELDS if field not in pulse]
    has_pages = bool(indicator_pages)
    counts_match = has_pages and endpoint_count == endpoint_results_total == detail_count
    status = "ok"
    if missing_fields:
        status = "missing_required_detail_fields"
    elif not has_pages:
        status = "missing_indicator_pages"
    elif not counts_match:
        status = "indicator_count_mismatch"
    return {
        "pulse_id": pulse_id,
        "indicator_page_count": len(indicator_pages),
        "detail_indicator_count": detail_count,
        "indicator_endpoint_count": endpoint_count,
        "indicator_endpoint_results_total": endpoint_results_total,
        "indicator_counts_match": counts_match,
        "missing_required_detail_fields": missing_fields,
        "status": status,
    }


def _endpoint_count(indicator_pages: list[dict[str, Any]]) -> int:
    if not indicator_pages:
        return 0
    count = indicator_pages[0].get("count")
    return count if isinstance(count, int) else 0
