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


def _iso(ts: Any) -> str:
    """Epoch seconds -> ISO-8601 UTC, or "" when absent/invalid."""
    if not isinstance(ts, int):
        return ""
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def _nameservers(attrs: dict[str, Any]) -> list[str]:
    """Nameserver hostnames from the domain's last DNS records (NS answers)."""
    return [
        str(r.get("value", ""))
        for r in attrs.get("last_dns_records", [])
        if r.get("type") == "NS" and r.get("value")
    ]


def vt_metadata(domain: str, attrs: dict[str, Any]) -> dict[str, Any]:
    """Preserve the join/enrichment-bearing VT fields (ingestion §2 fix: VT was
    dropping everything but tags/stats). Full whois text / DNS records / rdap /
    cert are kept verbatim here — never capped — so a future projection can mine
    them; the embedded prose (``_build_content``) renders only a readable summary.
    """
    return {
        "domain": domain,
        "tags": attrs.get("tags", []),
        "last_modified": _iso(attrs.get("last_modification_date")),
        "analysis_stats": attrs.get("last_analysis_stats", {}),
        "categories": attrs.get("categories", {}),
        "reputation": attrs.get("reputation"),
        "registrar": attrs.get("registrar", ""),
        "creation_date": _iso(attrs.get("creation_date")),
        "expiration_date": _iso(attrs.get("expiration_date")),
        "name_servers": _nameservers(attrs),
        "whois": attrs.get("whois", ""),
        "last_dns_records": attrs.get("last_dns_records", []),
        "last_https_certificate": attrs.get("last_https_certificate", {}),
        "rdap": attrs.get("rdap", {}),
    }


def render_vt_content(domain: str, attrs: dict[str, Any]) -> str:
    """Readable VT summary for embedding. Renders the structured signal (detection,
    full YARA, categories, registrar, dates, nameservers, cert org), not the bulk
    whois/dns/rdap blobs (those are preserved in metadata, never embedded)."""
    parts = [f"VirusTotal analysis of domain {domain}."]

    stats: dict[str, int] = attrs.get("last_analysis_stats", {})
    if stats:
        total = sum(v for v in stats.values() if isinstance(v, int))
        parts.append(
            f"Detection: {stats.get('malicious', 0)} malicious, "
            f"{stats.get('suspicious', 0)} suspicious, "
            f"{stats.get('harmless', 0)} harmless out of {total} engines."
        )

    # Full YARA rule set — no cap (ingestion §2 fix; the prior [:5] dropped signal).
    rules = [
        str(r.get("rule_name", ""))
        for r in attrs.get("crowdsourced_yara_results", [])
        if r.get("rule_name")
    ]
    if rules:
        parts.append(f"Matched YARA rules: {', '.join(rules)}.")

    categories = sorted({str(v) for v in attrs.get("categories", {}).values() if v})
    if categories:
        parts.append(f"Categories: {', '.join(categories)}.")

    if attrs.get("registrar"):
        parts.append(f"Registrar: {attrs['registrar']}.")

    created, expires = _iso(attrs.get("creation_date")), _iso(attrs.get("expiration_date"))
    if created or expires:
        parts.append(f"Registered {created or '?'} to {expires or '?'}.")

    nameservers = _nameservers(attrs)
    if nameservers:
        parts.append(f"Name servers: {', '.join(nameservers)}.")

    cert_org = (attrs.get("last_https_certificate", {}).get("subject", {}) or {}).get("O", "")
    if cert_org:
        parts.append(f"TLS certificate organization: {cert_org}.")

    tags = attrs.get("tags", [])
    if tags:
        parts.append(f"Tags: {', '.join(tags)}.")

    return " ".join(parts)


class VirusTotalConnector(HttpConnector):
    """VirusTotal domain connector.

    Two modes: live on-demand lookup (``api_key``, 4 req/min free tier), or offline
    replay of pre-fetched raw responses (``records`` — the verbatim VT payloads from
    the raw store), used by the projection/ingest path so the 473 already-fetched
    reports are reused without new API calls.
    """

    source_name = "virustotal"

    def __init__(self, api_key: str = "", records: list[dict[str, Any]] | None = None) -> None:
        super().__init__(base_url=_VT_BASE, api_key="")
        if api_key:
            self._client.headers.update({"x-apikey": api_key})
        self._records = records

    def fetch(self, domains: list[str] | None = None, **_: Any) -> Iterator[dict[str, Any]]:
        if self._records is not None:
            yield from self._records
            return
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
        doc_id = hashlib.sha256(f"vt:{domain}".encode()).hexdigest()[:16]

        return Document(
            id=doc_id,
            source=self.source_name,
            content=render_vt_content(domain, attrs),
            metadata=vt_metadata(domain, attrs),
        )
