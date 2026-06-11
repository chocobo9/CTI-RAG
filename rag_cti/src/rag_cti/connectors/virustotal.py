from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.connectors.base import HttpConnector
from rag_cti.types import Document

logger = get_logger(__name__)

_VT_BASE = "https://www.virustotal.com"


class VirusTotalConnector(HttpConnector):
    """On-demand VirusTotal domain enrichment connector.

    VT free tier is rate-limited to 4 req/min — use as on-demand lookup,
    not bulk ingest.
    """

    source_name = "virustotal"

    def __init__(self, api_key: str) -> None:
        super().__init__(base_url=_VT_BASE, api_key="")
        self._client.headers.update({"x-apikey": api_key})

    def fetch(self, domains: list[str] | None = None, **_: Any) -> Iterator[dict[str, Any]]:
        for domain in domains or []:
            try:
                yield self._get(f"/api/v3/domains/{domain}")
            except Exception as exc:
                logger.warning("VT lookup failed", domain=domain, error=str(exc))

    def to_document(self, raw: dict[str, Any]) -> Document:
        data = raw.get("data", {})
        domain: str = data.get("id", "")
        if not domain:
            raise ValueError("VirusTotal response missing data.id (domain)")

        attrs: dict[str, Any] = data.get("attributes", {})
        content = self._build_content(domain, attrs)
        doc_id = hashlib.sha256(f"vt:{domain}".encode()).hexdigest()[:16]

        last_mod_ts: int | None = attrs.get("last_modification_date")
        last_modified = (
            datetime.fromtimestamp(last_mod_ts, tz=UTC).isoformat() if last_mod_ts else ""
        )

        return Document(
            id=doc_id,
            source=self.source_name,
            content=content,
            metadata={
                "domain": domain,
                "tags": attrs.get("tags", []),
                "last_modified": last_modified,
                "analysis_stats": attrs.get("last_analysis_stats", {}),
            },
        )

    @staticmethod
    def _build_content(domain: str, attrs: dict[str, Any]) -> str:
        parts = [f"VirusTotal analysis of domain {domain}."]

        stats: dict[str, int] = attrs.get("last_analysis_stats", {})
        if stats:
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            harmless = stats.get("harmless", 0)
            total = sum(stats.values())
            parts.append(
                f"Detection: {malicious} malicious, {suspicious} suspicious, "
                f"{harmless} harmless out of {total} engines."
            )

        yara_results: list[dict[str, Any]] = attrs.get("crowdsourced_yara_results", [])
        if yara_results:
            rules = [r.get("rule_name", "") for r in yara_results[:5] if r.get("rule_name")]
            if rules:
                parts.append(f"Matched YARA rules: {', '.join(rules)}.")

        tags: list[str] = attrs.get("tags", [])
        if tags:
            parts.append(f"Tags: {', '.join(tags)}.")

        return " ".join(parts)
