from __future__ import annotations

import hashlib
from collections.abc import Iterator
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.connectors.base import BaseConnector
from rag_cti.types import Document

logger = get_logger(__name__)


class PassiveDNSConnector(BaseConnector):
    """Converts pre-fetched passive DNS records into prose Documents."""

    source_name = "pdns"

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._records = records or []

    def fetch(self, **_: Any) -> Iterator[dict[str, Any]]:
        yield from self._records

    def to_document(self, raw: dict[str, Any]) -> Document:
        domain: str = raw.get("domain", "")
        if not domain:
            raise ValueError("Passive DNS record missing required 'domain' field")

        content = self._render(raw)
        doc_id = hashlib.sha256(f"pdns:{domain}".encode()).hexdigest()[:16]

        resolutions = raw.get("resolutions", [])
        ips = [r.get("ip", "") for r in resolutions if r.get("ip")]
        asns = list({r.get("asn", "") for r in resolutions if r.get("asn")})

        return Document(
            id=doc_id,
            source=self.source_name,
            content=content,
            metadata={
                "domain": domain,
                "first_seen": raw.get("first_seen", ""),
                "last_seen": raw.get("last_seen", ""),
                "ip_addresses": ips[:20],
                "asns": asns[:10],
                "subdomains": raw.get("subdomains", [])[:20],
            },
        )

    @staticmethod
    def _render(raw: dict[str, Any]) -> str:
        domain = raw.get("domain", "unknown")
        first_seen = raw.get("first_seen", "")
        last_seen = raw.get("last_seen", "")
        resolutions: list[dict[str, Any]] = raw.get("resolutions", [])
        subdomains: list[str] = raw.get("subdomains", [])

        parts = [f"Passive DNS history for domain {domain}."]

        if first_seen and last_seen:
            parts.append(f"Observed from {first_seen} to {last_seen}.")

        if resolutions:
            res_parts = []
            for r in resolutions[:10]:
                ip = r.get("ip", "")
                asn = r.get("asn", "")
                asn_name = r.get("asn_name", "")
                fs = r.get("first_seen", "")
                ls = r.get("last_seen", "")
                entry = ip
                if asn:
                    entry += f" ({asn}"
                    if asn_name:
                        entry += f" / {asn_name}"
                    entry += ")"
                if fs and ls:
                    entry += f" seen {fs} to {ls}"
                res_parts.append(entry)
            parts.append(f"IP resolutions: {'; '.join(res_parts)}.")

        if subdomains:
            parts.append(f"Known subdomains: {', '.join(subdomains[:10])}.")

        return " ".join(parts)
