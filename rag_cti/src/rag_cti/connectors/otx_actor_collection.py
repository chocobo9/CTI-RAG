"""Helpers for MITRE actor/alias-driven OTX raw collection.

This module contains only deterministic parsing and id helpers. Network access
and filesystem writes live in the collection script so this code is easy to
unit-test.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MitreActorSeed:
    """One MITRE intrusion-set used as an OTX search seed."""

    name: str
    mitre_id: str
    stix_id: str
    aliases: tuple[str, ...]
    attack_version: str

    @property
    def queries(self) -> tuple[str, ...]:
        """Canonical name plus aliases, deduplicated case-insensitively."""
        return _dedupe_terms((self.name, *self.aliases))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mitre_id": self.mitre_id,
            "stix_id": self.stix_id,
            "aliases": list(self.aliases),
            "attack_version": self.attack_version,
        }


@dataclass(frozen=True)
class QueryActor:
    """MITRE actor association for one OTX search query.

    This is collection provenance only. It does not assert that an OTX pulse is
    attributed to this actor.
    """

    actor_name: str
    mitre_attack_id: str
    stix_id: str
    matched_from: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_name": self.actor_name,
            "mitre_attack_id": self.mitre_attack_id,
            "stix_id": self.stix_id,
            "matched_from": self.matched_from,
        }


@dataclass(frozen=True)
class OtxQuery:
    """One deduplicated OTX search query derived from MITRE actor records."""

    query: str
    query_normalized: str
    actors: tuple[QueryActor, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "query_normalized": self.query_normalized,
            "actors": [actor.to_dict() for actor in self.actors],
        }


def mitre_actor_seeds_from_bundle(bundle: dict[str, Any]) -> list[MitreActorSeed]:
    """Extract actor search seeds from a MITRE ATT&CK STIX bundle.

    Only non-revoked ``intrusion-set`` objects with a MITRE external id are used.
    This keeps collection discovery anchored to the ATT&CK actor ontology.
    """
    version = _attack_version(bundle)
    seeds: list[MitreActorSeed] = []
    for obj in bundle.get("objects", []):
        if obj.get("type") != "intrusion-set" or obj.get("revoked", False):
            continue
        mitre_id = _attack_id(obj)
        if not mitre_id:
            continue
        name = str(obj.get("name", "")).strip()
        if not name:
            continue
        aliases = _dedupe_terms(str(alias).strip() for alias in obj.get("aliases", []))
        aliases = tuple(alias for alias in aliases if alias != name)
        seeds.append(
            MitreActorSeed(
                name=name,
                mitre_id=mitre_id,
                stix_id=str(obj.get("id", "")),
                aliases=aliases,
                attack_version=version,
            )
        )
    return sorted(seeds, key=lambda seed: (seed.mitre_id, seed.name.lower()))


def otx_queries_from_mitre_actor_seeds(seeds: list[MitreActorSeed]) -> list[OtxQuery]:
    """Build a deduplicated MITRE actor/alias query list for OTX search."""
    grouped: dict[str, dict[str, Any]] = {}
    actor_keys: dict[str, set[tuple[str, str, str, str]]] = {}
    for seed in seeds:
        terms = [(seed.name, "name"), *((alias, "alias") for alias in seed.aliases)]
        for term, matched_from in terms:
            query = str(term).strip()
            if not query:
                continue
            normalized = normalize_query(query)
            if not normalized:
                continue
            grouped.setdefault(normalized, {"query": query, "actors": []})
            actor_key = (seed.name, seed.mitre_id, seed.stix_id, matched_from)
            actor_keys.setdefault(normalized, set())
            if actor_key in actor_keys[normalized]:
                continue
            actor_keys[normalized].add(actor_key)
            grouped[normalized]["actors"].append(
                QueryActor(
                    actor_name=seed.name,
                    mitre_attack_id=seed.mitre_id,
                    stix_id=seed.stix_id,
                    matched_from=matched_from,
                )
            )

    queries: list[OtxQuery] = []
    for normalized, item in grouped.items():
        actors = tuple(
            sorted(
                item["actors"],
                key=lambda actor: (
                    actor.mitre_attack_id,
                    actor.actor_name.casefold(),
                    actor.matched_from,
                ),
            )
        )
        queries.append(
            OtxQuery(
                query=str(item["query"]),
                query_normalized=normalized,
                actors=actors,
            )
        )
    return sorted(queries, key=lambda query: query.query_normalized)


def normalize_query(value: str) -> str:
    """Normalize a MITRE actor search term for dedupe and audit keys."""
    return re.sub(r"\s+", " ", value.strip()).casefold()


def search_raw_source_id_for_query(
    query_normalized: str, page: int, page_limit: int | None = None
) -> str:
    """Stable RawStore source id for one OTX search response page."""
    identity = {
        "kind": "otx_search",
        "query_normalized": query_normalized,
        "page": page,
    }
    if page_limit is not None:
        identity["page_limit"] = page_limit
    digest = _digest(identity)
    return f"query_{page:04d}_{digest}"


def search_raw_source_id(seed: MitreActorSeed, query: str, page: int) -> str:
    """Stable RawStore source id for one actor-scoped OTX search response page."""
    digest = _digest(
        {
            "kind": "otx_search",
            "mitre_id": seed.mitre_id,
            "stix_id": seed.stix_id,
            "query": query,
            "page": page,
        }
    )
    return f"{seed.mitre_id}_{page:04d}_{digest}"


def indicator_page_source_id(pulse_id: str, page: int, page_limit: int = 1000) -> str:
    """Stable RawStore source id for one OTX pulse-indicator response page."""
    digest = _digest(
        {
            "kind": "otx_indicator_page",
            "pulse_id": pulse_id,
            "page": page,
            "page_limit": page_limit,
        }
    )
    return f"{pulse_id}_l{page_limit}_{page:04d}_{digest}"


def search_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return OTX search result rows with usable pulse ids."""
    rows = payload.get("results")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("id")]


def _attack_id(obj: dict[str, Any]) -> str:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return str(ref.get("external_id", ""))
    return ""


def _attack_version(bundle: dict[str, Any]) -> str:
    for obj in bundle.get("objects", []):
        if obj.get("type") == "x-mitre-collection":
            return str(obj.get("x_mitre_version", ""))
    return ""


def _dedupe_terms(values: Any) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        term = str(value).strip()
        if not term:
            continue
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(term)
    return tuple(out)


def _digest(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
