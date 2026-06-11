from __future__ import annotations

import hashlib
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

from rag_cti._logging import get_logger
from rag_cti.connectors.base import HttpConnector
from rag_cti.types import Document

logger = get_logger(__name__)

_OTX_BASE = "https://otx.alienvault.com"
_SUBSCRIBED_PATH = "/api/v1/pulses/subscribed"
_PAGE_LIMIT = 20
# Prose keeps a readable sample; metadata keeps more for exact-match lookups
# but stays capped so Qdrant payloads don't balloon on indicator-heavy pulses.
_CONTENT_INDICATOR_SAMPLE = 20
_METADATA_INDICATOR_CAP = 50


def render_pulse_content(raw: dict[str, Any]) -> str:
    """Render a raw OTX pulse into retrieval prose.

    Single source of truth for the OTX content shape — used by both the live
    connector and scripts/rebuild_otx_jsonl.py. Includes adversary, malware
    families, and targeted countries so attribution queries have text to rank
    on (name-only chunks are unrankable).
    """
    parts = [raw.get("name", "")]

    desc = (raw.get("description") or "").strip()
    if desc:
        parts.append(desc)

    adversary = raw.get("adversary", "")
    if adversary:
        parts.append(f"Attributed to {adversary}.")

    family_names = _malware_family_names(raw)
    if family_names:
        parts.append(f"Associated malware: {', '.join(family_names)}.")

    countries = raw.get("targeted_countries", [])
    if countries:
        parts.append(f"Targeted countries: {', '.join(countries)}.")

    indicators = _indicator_values(raw)
    if indicators:
        sample = indicators[:_CONTENT_INDICATOR_SAMPLE]
        parts.append(f"Key indicators: {', '.join(sample)}.")

    return "\n\n".join(p for p in parts if p)


def pulse_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    """Metadata payload for an OTX pulse — companion to render_pulse_content."""
    return {
        "pulse_id": raw.get("id", ""),
        "name": raw.get("name", ""),
        "tags": raw.get("tags", []),
        "attack_ids": raw.get("attack_ids", []),
        "adversary": raw.get("adversary", ""),
        "malware_families": raw.get("malware_families", []),
        "targeted_countries": raw.get("targeted_countries", []),
        "references": raw.get("references", []),
        "indicators": _indicator_values(raw)[:_METADATA_INDICATOR_CAP],
        "last_modified": raw.get("modified", ""),
        "pulse_source": raw.get("pulse_source", ""),
    }


def _indicator_values(raw: dict[str, Any]) -> list[str]:
    return [ind.get("indicator", "") for ind in raw.get("indicators", []) if ind.get("indicator")]


def _malware_family_names(raw: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for fam in raw.get("malware_families", []):
        if isinstance(fam, str):
            if fam:
                names.append(fam)
        elif isinstance(fam, dict):
            display_name = fam.get("display_name", "")
            if display_name:
                names.append(display_name)
    return names


class OTXConnector(HttpConnector):
    """Fetches AlienVault OTX pulse subscriptions as Documents."""

    source_name = "otx"

    def __init__(self, api_key: str, modified_since: str = "") -> None:
        super().__init__(base_url=_OTX_BASE, api_key=api_key)
        self._modified_since = modified_since

    def fetch(self, **_: Any) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {"limit": _PAGE_LIMIT}
        if self._modified_since:
            params["modified_since"] = self._modified_since

        seen_ids: set[str] = set()
        path: str = _SUBSCRIBED_PATH
        while path:
            data = self._get(path, **params)
            new_on_page = 0
            for pulse in data.get("results", []):
                pulse_id = pulse.get("id", "")
                if pulse_id in seen_ids:
                    continue
                seen_ids.add(pulse_id)
                new_on_page += 1
                yield pulse
            logger.info(
                "page fetched",
                total_on_page=len(data.get("results", [])),
                new=new_on_page,
                seen_total=len(seen_ids),
            )
            if new_on_page == 0:
                # Every pulse on this page was already seen — pagination has cycled
                break
            next_url: str | None = data.get("next")
            if next_url:
                parsed = urlparse(next_url)
                path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
                params = {}
            else:
                path = ""

    def to_document(self, raw: dict[str, Any]) -> Document:
        pulse_id: str = raw.get("id", "")
        doc_id = hashlib.sha256(f"otx:{pulse_id}".encode()).hexdigest()[:16]

        return Document(
            id=doc_id,
            source=self.source_name,
            content=render_pulse_content(raw),
            metadata=pulse_metadata(raw),
        )
