#!/usr/bin/env python3
"""
Build MITRE ATT&CK intrusion-set query shards for raw OTX collection.

Outputs:
  data/raw_otx_mitre/seeds/mitre_actors.json
  data/raw_otx_mitre/seeds/mitre_actor_aliases.json
  data/raw_otx_mitre/seeds/query_shard_00.json
  data/raw_otx_mitre/seeds/query_shard_01.json
  data/raw_otx_mitre/seeds/query_shard_02.json
  data/raw_otx_mitre/seeds/query_shard_03.json
  data/raw_otx_mitre/seeds/query_manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE_DIR = PROJECT_ROOT / "data" / "raw_otx_mitre"
DEFAULT_SEED_DIR = DEFAULT_BASE_DIR / "seeds"
MITRE_ATTACK_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/"
    "enterprise-attack/enterprise-attack.json"
)
SHARD_COUNT = 4
REQUEST_TIMEOUT = 60
RETRY_MAX = 5
RETRY_BASE_DELAY = 2.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+", " ", value.strip())
    return cleaned or None


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def safe_actor_id(stix_id: str | None, name: str) -> str:
    if stix_id:
        return stix_id
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return slug or normalize(name)


def fetch_json(url: str) -> dict:
    last_error = None
    for attempt in range(RETRY_MAX):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            last_error = f"HTTP {resp.status_code}"
            if resp.status_code not in (429, 502, 503, 504):
                break
        except (
            requests.Timeout,
            requests.ConnectionError,
            requests.exceptions.SSLError,
            requests.RequestException,
        ) as exc:
            last_error = repr(exc)
        time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
    raise RuntimeError(f"Failed to fetch MITRE ATT&CK data from {url}: {last_error}")


def mitre_external_id(obj: dict) -> str | None:
    for ref in obj.get("external_references", []) or []:
        if ref.get("source_name") == "mitre-attack" and ref.get("external_id"):
            return ref["external_id"]
    return None


def mitre_url(obj: dict) -> str | None:
    for ref in obj.get("external_references", []) or []:
        if ref.get("source_name") == "mitre-attack" and ref.get("url"):
            return ref["url"]
    return None


def collect_actors(data: dict, source_url: str) -> tuple[list[dict], list[dict], list[dict]]:
    actors: list[dict] = []
    alias_rows: list[dict] = []
    query_by_norm: dict[str, dict] = {}

    for obj in data.get("objects", []) or []:
        if obj.get("type") != "intrusion-set":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue

        name = clean_string(obj.get("name"))
        if not name:
            continue

        actor = {
            "actor_id": safe_actor_id(obj.get("id"), name),
            "stix_id": obj.get("id"),
            "mitre_attack_id": mitre_external_id(obj),
            "name": name,
            "description": obj.get("description"),
            "mitre_url": mitre_url(obj),
            "source": "mitre_attack",
            "source_url": source_url,
            "aliases": [],
        }

        seen_aliases: set[str] = set()
        for raw_alias in [name, *(obj.get("aliases", []) or [])]:
            alias = clean_string(raw_alias)
            if not alias:
                continue
            alias_norm = normalize(alias)
            if alias_norm in seen_aliases:
                continue
            seen_aliases.add(alias_norm)
            actor["aliases"].append(alias)

            alias_row = {
                "actor_id": actor["actor_id"],
                "actor_name": name,
                "stix_id": actor["stix_id"],
                "mitre_attack_id": actor["mitre_attack_id"],
                "alias": alias,
                "alias_normalized": alias_norm,
                "source": "mitre_attack",
                "source_url": source_url,
            }
            alias_rows.append(alias_row)

            query = query_by_norm.setdefault(
                alias_norm,
                {
                    "query": alias,
                    "query_normalized": alias_norm,
                    "actors": [],
                },
            )
            query["actors"].append(alias_row)

        actors.append(actor)

    for query in query_by_norm.values():
        query["actors"] = sorted(
            query["actors"],
            key=lambda item: (item["actor_name"].casefold(), item["alias"].casefold()),
        )

    queries = sorted(query_by_norm.values(), key=lambda item: item["query_normalized"])
    actors = sorted(actors, key=lambda item: item["name"].casefold())
    alias_rows = sorted(alias_rows, key=lambda item: (item["actor_name"].casefold(), item["alias"].casefold()))
    return actors, alias_rows, queries


def split_exactly_four(items: list[dict]) -> list[list[dict]]:
    base, extra = divmod(len(items), SHARD_COUNT)
    shards: list[list[dict]] = []
    start = 0
    for idx in range(SHARD_COUNT):
        size = base + (1 if idx < extra else 0)
        shards.append(items[start:start + size])
        start += size
    return shards


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build four MITRE ATT&CK actor/alias query shards for raw OTX collection."
    )
    parser.add_argument("--seed-dir", type=Path, default=DEFAULT_SEED_DIR)
    parser.add_argument("--mitre-url", default=MITRE_ATTACK_URL)
    args = parser.parse_args()

    generated_at = utc_now()
    data = fetch_json(args.mitre_url)
    actors, aliases, queries = collect_actors(data, args.mitre_url)
    shards = split_exactly_four(queries)

    write_json(
        args.seed_dir / "mitre_actors.json",
        {
            "generated_at": generated_at,
            "source_url": args.mitre_url,
            "actor_count": len(actors),
            "actors": actors,
        },
    )
    write_json(
        args.seed_dir / "mitre_actor_aliases.json",
        {
            "generated_at": generated_at,
            "source_url": args.mitre_url,
            "alias_record_count": len(aliases),
            "aliases": aliases,
        },
    )

    manifest = {
        "generated_at": generated_at,
        "source_url": args.mitre_url,
        "actor_count": len(actors),
        "alias_record_count": len(aliases),
        "deduplicated_query_count": len(queries),
        "shard_count": SHARD_COUNT,
        "shards": [],
    }

    for shard_index, shard_queries in enumerate(shards):
        shard_name = f"query_shard_{shard_index:02d}.json"
        write_json(
            args.seed_dir / shard_name,
            {
                "generated_at": generated_at,
                "source_url": args.mitre_url,
                "shard_index": shard_index,
                "shard_count": SHARD_COUNT,
                "query_count": len(shard_queries),
                "queries": shard_queries,
            },
        )
        manifest["shards"].append(
            {
                "shard_index": shard_index,
                "file": shard_name,
                "query_count": len(shard_queries),
            }
        )

    write_json(args.seed_dir / "query_manifest.json", manifest)
    print(
        f"Wrote {len(queries)} deduplicated MITRE actor/alias queries "
        f"into 4 shards under {args.seed_dir}"
    )


if __name__ == "__main__":
    main()
