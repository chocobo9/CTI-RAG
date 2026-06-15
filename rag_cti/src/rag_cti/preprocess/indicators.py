"""Indicator typing — preserve ``{value, type}`` from the source (ingestion §5).

The indicator type is the join discriminator for the entire field-source layer
(domain → WHOIS/pDNS, hash → VT). It is preserved **verbatim** from the source.

Rule 0: a source type with no clean mapping into the controlled canonical set
(``hostname``, ``CVE``, ``YARA``, ``CIDR``, ``SSLCertFingerprint``, …) keeps
``canonical_type=None`` and is logged — never dropped, never force-merged into a
canonical bucket it does not belong to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag_cti._logging import get_logger

logger = get_logger(__name__)

# Controlled canonical indicator types (ingestion §5).
CANONICAL_TYPES = frozenset(
    {
        "domain",
        "ipv4",
        "ipv6",
        "hash-md5",
        "hash-sha1",
        "hash-sha256",
        "url",
        "email",
    }
)

# OTX source type -> canonical controlled type. ``hostname``/``URI`` join the same
# class as domain/url so they map (the verbatim source type is still kept on the
# mention, so this groups without losing information). Source types absent here
# (BitcoinAddress, FilePath, Mutex, CVE, YARA, CIDR, SSLCertFingerprint, …) keep
# canonical_type=None — preserved verbatim, never force-mapped (Rule 0).
_OTX_CANONICAL: dict[str, str] = {
    "domain": "domain",
    "hostname": "domain",
    "IPv4": "ipv4",
    "IPv6": "ipv6",
    "FileHash-MD5": "hash-md5",
    "FileHash-SHA1": "hash-sha1",
    "FileHash-SHA256": "hash-sha256",
    "URL": "url",
    "URI": "url",
    "email": "email",
}


@dataclass(frozen=True)
class IndicatorMention:
    """A typed indicator: the source type is kept verbatim, canonical is derived."""

    value: str
    type: str  # source type, verbatim (e.g. "FileHash-SHA256", "hostname")
    canonical_type: str | None  # controlled type, or None when unmapped

    def to_dict(self) -> dict[str, str | None]:
        return {"value": self.value, "type": self.type, "canonical_type": self.canonical_type}


def canonical_indicator_type(source_type: str) -> str | None:
    """Map a source indicator type to the controlled canonical type, or None."""
    return _OTX_CANONICAL.get(source_type)


def indicator_mentions(raw_indicators: list[dict[str, Any]]) -> list[IndicatorMention]:
    """Convert raw OTX indicator dicts to typed mentions, preserving type.

    Empty indicator values are skipped (no value = nothing to join on). Source
    types that do not map to the canonical set are kept verbatim and logged once
    per call so the loss-of-canonical is never silent.
    """
    out: list[IndicatorMention] = []
    unmapped: set[str] = set()
    for ind in raw_indicators:
        value = ind.get("indicator", "")
        if not value:
            continue
        src_type = ind.get("type", "")
        canon = canonical_indicator_type(src_type)
        if src_type and canon is None:
            unmapped.add(src_type)
        out.append(IndicatorMention(value=value, type=src_type, canonical_type=canon))
    if unmapped:
        logger.info(
            "indicator types preserved without canonical mapping",
            types=sorted(unmapped),
        )
    return out
