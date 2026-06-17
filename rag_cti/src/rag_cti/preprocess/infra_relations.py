"""Infrastructure-fact relations from a field-source record (knowledge §5).

pDNS / VT field sources carry infrastructure facts — domain→ip resolutions, ASN
ownership, geolocation, nameservers, subdomains. This module turns the common
structured record (produced by ``pdns_projection`` / ``vt_projection``) into the
chunk payload's ``entity_ids`` + ``relations`` triples.

Endpoint ids are minted **directly** here (``indicator_entity_id`` /
``asn_entity_id`` / ``location_entity_id``), never through the generic
``resolve_relations`` path. That path resolves an ``indicator`` / ``location``
mention via the orphan scheme (``indicator_orphan_<hash(norm name)>``), which
diverges from the ``indicator_<hash(kind:value)>`` used for the same value in
``entity_ids``. Building both sides from the same id functions is what guarantees
a chunk's ``entity_ids[]`` and ``relations[]`` endpoints are equal (retrieval §7
invariant 1: payload must be rebuildable from the knowledge layer).
"""

from __future__ import annotations

from typing import Any

from rag_cti.preprocess.entity_registry import asn_entity_id, location_entity_id
from rag_cti.preprocess.indicator_index import indicator_entity_id
from rag_cti.preprocess.indicators import IndicatorMention

# Infrastructure controlled predicates (CONTEXT.md / knowledge §3).
RESOLVES_TO = "resolves-to"
BELONGS_TO = "belongs-to"
LOCATED_IN = "located-in"
USES_NAMESERVER = "uses-nameserver"
HAS_SUBDOMAIN = "has-subdomain"


def _indicator_id(value: str, canonical: str) -> str:
    """Id for an infra indicator endpoint, keyed on ``(canonical_type, value)`` so a
    domain/ip seen here equals the same one seen anywhere else (cross-source)."""
    return indicator_entity_id(
        IndicatorMention(value=value, type=canonical, canonical_type=canonical)
    )


def build_infra_relations(record: dict[str, Any]) -> dict[str, list[Any]]:
    """Project one structured field-source record into ``{entity_ids, relations}``.

    ``record`` is the common shape from ``project_pdns_raw`` / ``project_vt_raw``:
    ``{domain, resolutions:[{value, ip, record_type, asn, country, ...}], subdomains}``.
    Emits, per resolution: ``domain resolves-to ip`` (A), ``ip belongs-to asn``,
    ``ip located-in country``, ``domain uses-nameserver ns`` (NS); plus
    ``domain has-subdomain sub`` per subdomain. All endpoint ids are stable and
    shared with ``entity_ids`` (see module docstring). Returns empty for a record
    with no domain.
    """
    domain = str(record.get("domain") or "").strip()
    if not domain:
        return {"entity_ids": [], "relations": []}

    domain_id = _indicator_id(domain, "domain")
    entity_ids: set[str] = {domain_id}
    relations: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(subject_id: str, predicate: str, object_id: str) -> None:
        key = (subject_id, predicate, object_id)
        if key in seen:
            return
        seen.add(key)
        entity_ids.add(subject_id)
        entity_ids.add(object_id)
        relations.append({"subject_id": subject_id, "predicate": predicate, "object_id": object_id})

    for res in record.get("resolutions") or []:
        rtype = str(res.get("record_type") or "").upper()
        ip = str(res.get("ip") or "").strip()
        answer = str(res.get("value") or "").strip()
        if rtype == "A" and ip:
            ip_id = _indicator_id(ip, "ipv4")
            add(domain_id, RESOLVES_TO, ip_id)
            asn = str(res.get("asn") or "").strip()
            if asn:
                add(ip_id, BELONGS_TO, asn_entity_id(asn))
            country = str(res.get("country") or "").strip()
            if country:
                add(ip_id, LOCATED_IN, location_entity_id(country))
        elif rtype == "NS" and answer:
            add(domain_id, USES_NAMESERVER, _indicator_id(answer, "domain"))

    for sub in record.get("subdomains") or []:
        name = str(sub or "").strip()
        if name:
            add(domain_id, HAS_SUBDOMAIN, _indicator_id(name, "domain"))

    return {"entity_ids": sorted(entity_ids), "relations": relations}
