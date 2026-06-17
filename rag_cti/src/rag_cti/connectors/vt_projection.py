"""Project append-only raw VirusTotal captures into ingestible inputs.

A raw VT snapshot in the store is ``{fetched_at, payload, source, source_id}`` where
``payload`` is the verbatim VT v3 domain response ``{data: {id, attributes}}``. The
connector's ``to_document`` already consumes a payload directly (live and offline
share it), so the offline path just replays payloads. This module additionally
derives the **common structured infra record** (``{domain, resolutions, subdomains}``,
the same shape ``pdns_projection`` produces) from VT's ``last_dns_records`` so
``infra_relations`` can build domain→ip / domain→ns edges from the 473 already-fetched
reports — no new API calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def project_vt_infra(payload: dict[str, Any]) -> dict[str, Any]:
    """VT response payload -> common infra record (domain + DNS resolutions).

    VT's ``last_dns_records`` carries A answers (an IP) and NS answers (a nameserver
    host); it has no per-record ASN/country (those come from pDNS), so VT backs
    ``resolves-to`` and ``uses-nameserver`` only.
    """
    data = payload.get("data") or {}
    domain = str(data.get("id") or "").strip()
    attrs = data.get("attributes") or {}

    resolutions: list[dict[str, Any]] = []
    for rec in attrs.get("last_dns_records") or []:
        rtype = str(rec.get("type") or "").upper()
        value = str(rec.get("value") or "").strip()
        if not value:
            continue
        if rtype == "A":
            resolutions.append(
                {"value": value, "ip": value, "record_type": "A", "asn": "", "country": ""}
            )
        elif rtype == "NS":
            resolutions.append({"value": value, "ip": "", "record_type": "NS"})

    return {"domain": domain, "resolutions": resolutions, "subdomains": []}


def load_vt_raw_payloads(raw_dir: Path) -> list[dict[str, Any]]:
    """Load the latest VT payload (the verbatim VT response) per domain directory."""
    payloads: list[dict[str, Any]] = []
    for domain_dir in sorted(path for path in raw_dir.iterdir() if path.is_dir()):
        snapshots = sorted(domain_dir.glob("*.json"))
        if not snapshots:
            continue
        raw = json.loads(snapshots[-1].read_text(encoding="utf-8"))
        payload = raw.get("payload") or {}
        if payload.get("data"):
            payloads.append(payload)
    return payloads
