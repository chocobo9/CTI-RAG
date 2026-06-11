"""Whoxy WHOIS API client — fetches live WHOIS records for the WHOISConnector.

Whoxy (https://www.whoxy.com/) returns JSON WHOIS records via a simple GET
API keyed by query parameter. This module maps Whoxy's response shape onto the
flat record dict that :class:`rag_cti.connectors.whois_connector.WHOISConnector`
and :func:`rag_cti.preprocess.whois_template.render_whois` expect:

    domain, registrar, iana_id, created, updated, expires,
    registrant_email, name_servers, status
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rag_cti._logging import get_logger
from rag_cti.connectors.base import RetryKwargs

logger = get_logger(__name__)

_WHOXY_BASE_URL = "https://api.whoxy.com/"

_RETRY_KWARGS: RetryKwargs = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=30),
    "reraise": True,
}


def whoxy_to_whois_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a Whoxy live-WHOIS JSON payload to the WHOISConnector record shape.

    Raises ValueError when the payload signals failure (``status != 1``) or
    lacks a domain name, so callers can count and skip bad rows explicitly.
    """
    if payload.get("status") != 1:
        raise ValueError(f"Whoxy lookup failed: {payload.get('status_reason') or 'status != 1'}")
    domain = (payload.get("domain_name") or "").strip().lower()
    if not domain:
        raise ValueError("Whoxy payload missing domain_name")

    registrar = payload.get("domain_registrar") or {}
    registrant = payload.get("registrant_contact") or {}

    return {
        "domain": domain,
        "registrar": registrar.get("registrar_name", ""),
        "iana_id": str(registrar.get("iana_id", "") or ""),
        "created": payload.get("create_date", ""),
        "updated": payload.get("update_date", ""),
        "expires": payload.get("expiry_date", ""),
        "registrant_email": registrant.get("email_address", ""),
        "name_servers": payload.get("name_servers") or [],
        "status": payload.get("domain_status") or [],
    }


def whoxy_history_to_whois_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a Whoxy WHOIS-history payload (``?history=domain``) to a record.

    The history endpoint wraps an array of per-snapshot records in
    ``whois_records``; this picks the most recent snapshot (by ``query_time``)
    and maps it through :func:`whoxy_to_whois_record`. Raises ValueError on
    failure status or an empty history, mirroring the live mapper.
    """
    if payload.get("status") != 1:
        raise ValueError(
            f"Whoxy history lookup failed: {payload.get('status_reason') or 'status != 1'}"
        )
    records = payload.get("whois_records") or []
    if not records:
        raise ValueError("Whoxy history payload has no whois_records")

    latest = max(records, key=lambda r: str(r.get("query_time", "")))
    snapshot = dict(latest)
    # Per-snapshot records omit the envelope's status/domain_name; inherit them
    # so the live mapper's validation applies unchanged.
    snapshot["status"] = 1
    if not (snapshot.get("domain_name") or "").strip():
        snapshot["domain_name"] = payload.get("domain_name", "")
    return whoxy_to_whois_record(snapshot)


class WhoxyClient:
    """Thin Whoxy API client (auth via ``key`` query parameter, not a header)."""

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        if not api_key:
            raise ValueError("Whoxy API key is required")
        self._api_key = api_key
        self._client = httpx.Client(timeout=timeout)

    @retry(**_RETRY_KWARGS)
    def _get(self, **params: Any) -> dict[str, Any]:
        response = self._client.get(_WHOXY_BASE_URL, params={"key": self._api_key, **params})
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def whois(self, domain: str) -> dict[str, Any]:
        """Live WHOIS lookup; returns the WHOISConnector-shaped record."""
        return whoxy_to_whois_record(self._get(whois=domain))

    def history(self, domain: str) -> dict[str, Any]:
        """WHOIS-history lookup; returns the latest snapshot as a record.

        Uses the ``?history=`` endpoint, which is billed separately from live
        WHOIS — useful when the account balance covers history credits only.
        """
        return whoxy_history_to_whois_record(self._get(history=domain))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> WhoxyClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
