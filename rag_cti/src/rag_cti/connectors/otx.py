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
            logger.info("page fetched", total_on_page=len(data.get("results", [])), new=new_on_page, seen_total=len(seen_ids))
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
        name: str = raw.get("name", "")
        description: str = (raw.get("description") or "").strip()
        content = f"{name}\n\n{description}" if description else name

        indicators = [
            ind.get("indicator", "")
            for ind in raw.get("indicators", [])
            if ind.get("indicator")
        ]

        doc_id = hashlib.sha256(f"otx:{pulse_id}".encode()).hexdigest()[:16]

        return Document(
            id=doc_id,
            source=self.source_name,
            content=content,
            metadata={
                "pulse_id": pulse_id,
                "name": name,
                "tags": raw.get("tags", []),
                "attack_ids": raw.get("attack_ids", []),
                "indicators": indicators[:50],
                "last_modified": raw.get("modified", ""),
                "pulse_source": raw.get("pulse_source", ""),
            },
        )
