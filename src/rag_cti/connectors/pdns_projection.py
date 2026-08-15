from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def project_pdns_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Project one append-only pDNS raw snapshot into builder input."""
    domain = str(raw.get("source_id") or "").strip()
    payload = raw.get("payload") or {}
    passive_dns = payload.get("passive_dns") or []

    resolutions: list[dict[str, Any]] = []
    subdomains: set[str] = set()
    first_seen_values: list[str] = []
    last_seen_values: list[str] = []

    for item in passive_dns:
        if not isinstance(item, dict):
            continue

        hostname = str(item.get("hostname") or "").strip()
        record_type = str(item.get("record_type") or "").strip()
        address = str(item.get("address") or "").strip()
        first_seen = str(item.get("first") or "").strip()
        last_seen = str(item.get("last") or "").strip()
        asn, asn_name = _split_asn(str(item.get("asn") or ""))

        if first_seen:
            first_seen_values.append(first_seen)
        if last_seen:
            last_seen_values.append(last_seen)
        if hostname and domain and hostname != domain and hostname.endswith(f".{domain}"):
            subdomains.add(hostname)

        resolutions.append(
            {
                "value": address,
                "ip": address if _IPV4_RE.match(address) else "",
                "record_type": record_type,
                "asset_type": str(item.get("asset_type") or "").strip(),
                "hostname": hostname,
                "asn": asn,
                "asn_name": asn_name,
                "country": str(item.get("flag_title") or "").strip(),
                "first_seen": first_seen,
                "last_seen": last_seen,
            }
        )

    return {
        "domain": domain,
        "fetched_at": str(raw.get("fetched_at") or "").strip(),
        "first_seen": min(first_seen_values) if first_seen_values else "",
        "last_seen": max(last_seen_values) if last_seen_values else "",
        "resolutions": resolutions,
        "subdomains": sorted(subdomains),
    }


def load_pdns_raw_dir(raw_dir: Path) -> list[dict[str, Any]]:
    """Load the latest pDNS snapshot for each domain directory."""
    records: list[dict[str, Any]] = []
    for domain_dir in sorted(path for path in raw_dir.iterdir() if path.is_dir()):
        snapshots = sorted(domain_dir.glob("*.json"))
        if not snapshots:
            continue
        raw = json.loads(snapshots[-1].read_text(encoding="utf-8"))
        records.append(project_pdns_raw(raw))
    return records


def _split_asn(value: str) -> tuple[str, str]:
    value = " ".join(value.split())
    if not value:
        return "", ""
    parts = value.split(" ", 1)
    asn = parts[0] if parts[0].upper().startswith("AS") else ""
    asn_name = parts[1] if len(parts) > 1 and asn else value if not asn else ""
    return asn, asn_name
