#!/usr/bin/env python3
"""
Merge MITRE raw OTX part directories by pulse_id.

Raw OTX JSON is copied, not rewritten:
  merged/pulses/<pulse_id>.json
  merged/indicators/<pulse_id>.json

Actor files under merged/by_actor/ are index files only. They point at pulse
IDs and merged raw paths; they do not duplicate raw OTX payloads.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE_DIR = PROJECT_ROOT / "data" / "raw_otx_mitre"
SHARD_COUNT = 4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(path)


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def slugify_filename(value: str, max_len: int = 120) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._-")
    return (slug or "actor")[:max_len]


def copy_once(src: Path, dst: Path) -> bool:
    if dst.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def dedupe_dicts(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def load_seed_actors(base_dir: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    actors_path = base_dir / "seeds" / "mitre_actors.json"
    if not actors_path.exists():
        raise SystemExit(f"Missing {actors_path}. Run build_mitre_query_shards.py first.")
    actors_payload = read_json(actors_path)
    by_id: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for actor in actors_payload.get("actors", []):
        actor_id = actor.get("actor_id")
        name = actor.get("name")
        if actor_id:
            by_id[actor_id] = actor
        if name:
            by_name[name] = actor
    return by_id, by_name


def scan_saved_pulses(part_dirs: list[Path]) -> dict[str, dict]:
    pulses: dict[str, dict] = {}
    for part_dir in part_dirs:
        pulse_dir = part_dir / "pulses"
        if not pulse_dir.exists():
            continue
        for path in pulse_dir.glob("*.json"):
            pulse_id = path.stem
            entry = pulses.setdefault(
                pulse_id,
                {
                    "pulse_id": pulse_id,
                    "pulse_sources": [],
                    "indicator_sources": [],
                },
            )
            entry["pulse_sources"].append(str(path))
            indicator_path = part_dir / "indicators" / f"{pulse_id}.json"
            if indicator_path.exists():
                entry["indicator_sources"].append(str(indicator_path))
    return pulses


def collect_metadata(part_dirs: list[Path]) -> tuple[dict[str, dict], list[dict], list[dict]]:
    by_pulse: dict[str, dict] = {}
    failures: list[dict] = []
    search_pages: list[dict] = []

    for part_dir in part_dirs:
        metadata_dir = part_dir / "metadata"

        for row in read_jsonl(metadata_dir / "discovery_metadata.jsonl"):
            pulse_id = row.get("pulse_id")
            if not pulse_id:
                continue
            entry = by_pulse.setdefault(
                pulse_id,
                {
                    "pulse_id": pulse_id,
                    "discoveries": [],
                    "queries": [],
                    "actors": [],
                    "parts": [],
                },
            )
            discovery = {
                "part": row.get("part"),
                "query": row.get("query"),
                "query_normalized": row.get("query_normalized"),
                "query_actors": row.get("query_actors", []),
                "pulse_created": row.get("pulse_created"),
                "in_date_window": row.get("in_date_window"),
                "since": row.get("since"),
                "until": row.get("until"),
                "search_page": row.get("search_page"),
                "search_file": row.get("search_file"),
                "time": row.get("time"),
            }
            entry["discoveries"].append(discovery)
            if row.get("query") not in entry["queries"]:
                entry["queries"].append(row.get("query"))
            part_name = f"part_{int(row.get('part')):02d}" if isinstance(row.get("part"), int) else part_dir.name
            if part_name not in entry["parts"]:
                entry["parts"].append(part_name)
            for actor_ref in row.get("query_actors", []) or []:
                actor_ref_min = {
                    "actor_id": actor_ref.get("actor_id"),
                    "actor_name": actor_ref.get("actor_name"),
                    "stix_id": actor_ref.get("stix_id"),
                    "mitre_attack_id": actor_ref.get("mitre_attack_id"),
                    "alias": actor_ref.get("alias"),
                    "alias_normalized": actor_ref.get("alias_normalized"),
                }
                entry["actors"].append(actor_ref_min)

        failures.extend(read_jsonl(metadata_dir / "failed_requests.jsonl"))
        search_pages.extend(read_jsonl(metadata_dir / "search_pages.jsonl"))

    for entry in by_pulse.values():
        entry["discoveries"] = dedupe_dicts(entry["discoveries"])
        entry["actors"] = dedupe_dicts(entry["actors"])
        entry["queries"] = sorted(q for q in entry["queries"] if q)
        entry["parts"] = sorted(entry["parts"])

    return by_pulse, failures, search_pages


def build_actor_indexes(
    actor_by_id: dict[str, dict],
    metadata_by_pulse: dict[str, dict],
    saved_pulse_ids: set[str],
) -> dict[str, dict]:
    indexes: dict[str, dict] = {}

    for actor_id, actor in actor_by_id.items():
        indexes[actor_id] = {
            "actor": actor,
            "aliases": actor.get("aliases", []),
            "matched_queries": [],
            "pulse_ids": [],
            "pulses": [],
        }

    for pulse_id in sorted(saved_pulse_ids):
        pulse_meta = metadata_by_pulse.get(pulse_id)
        if not pulse_meta:
            continue
        for discovery in pulse_meta.get("discoveries", []):
            if discovery.get("in_date_window") is not True:
                continue
            for actor_ref in discovery.get("query_actors", []) or []:
                actor_id = actor_ref.get("actor_id")
                if not actor_id:
                    continue
                idx = indexes.setdefault(
                    actor_id,
                    {
                        "actor": {
                            "actor_id": actor_id,
                            "name": actor_ref.get("actor_name"),
                            "stix_id": actor_ref.get("stix_id"),
                            "mitre_attack_id": actor_ref.get("mitre_attack_id"),
                            "aliases": [],
                        },
                        "aliases": [],
                        "matched_queries": [],
                        "pulse_ids": [],
                        "pulses": [],
                    },
                )
                query = discovery.get("query")
                if query and query not in idx["matched_queries"]:
                    idx["matched_queries"].append(query)
                alias = actor_ref.get("alias")
                if alias and alias not in idx["aliases"]:
                    idx["aliases"].append(alias)
                if pulse_id not in idx["pulse_ids"]:
                    idx["pulse_ids"].append(pulse_id)
                    idx["pulses"].append(
                        {
                            "pulse_id": pulse_id,
                            "pulse_path": f"../pulses/{pulse_id}.json",
                            "indicators_path": f"../indicators/{pulse_id}.json",
                        }
                    )

    for idx in indexes.values():
        idx["matched_queries"] = sorted(idx["matched_queries"], key=str.casefold)
        idx["aliases"] = sorted(set(idx["aliases"]), key=str.casefold)
        idx["pulse_ids"] = sorted(idx["pulse_ids"])
        idx["pulses"] = sorted(idx["pulses"], key=lambda item: item["pulse_id"])
        idx["pulse_count"] = len(idx["pulse_ids"])

    return indexes


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge MITRE raw OTX part outputs.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    args = parser.parse_args()

    part_dirs = [args.base_dir / f"part_{idx:02d}" for idx in range(SHARD_COUNT)]
    missing = [str(path) for path in part_dirs if not path.exists()]
    if missing:
        raise SystemExit(f"Missing part directories: {missing}")

    actor_by_id, actor_by_name = load_seed_actors(args.base_dir)
    saved_pulses = scan_saved_pulses(part_dirs)
    metadata_by_pulse, failures, search_pages = collect_metadata(part_dirs)

    merged_dir = args.base_dir / "merged"
    pulse_out = merged_dir / "pulses"
    indicator_out = merged_dir / "indicators"
    by_actor_out = merged_dir / "by_actor"
    metadata_out = merged_dir / "metadata"
    pulse_out.mkdir(parents=True, exist_ok=True)
    indicator_out.mkdir(parents=True, exist_ok=True)
    by_actor_out.mkdir(parents=True, exist_ok=True)
    metadata_out.mkdir(parents=True, exist_ok=True)

    copied_pulses = 0
    copied_indicators = 0
    missing_indicators: list[str] = []

    for pulse_id, entry in sorted(saved_pulses.items()):
        pulse_sources = sorted(entry["pulse_sources"])
        indicator_sources = sorted(entry["indicator_sources"])
        if pulse_sources and copy_once(Path(pulse_sources[0]), pulse_out / f"{pulse_id}.json"):
            copied_pulses += 1
        if indicator_sources:
            if copy_once(Path(indicator_sources[0]), indicator_out / f"{pulse_id}.json"):
                copied_indicators += 1
        else:
            missing_indicators.append(pulse_id)

        metadata_by_pulse.setdefault(
            pulse_id,
            {
                "pulse_id": pulse_id,
                "discoveries": [],
                "queries": [],
                "actors": [],
                "parts": [],
            },
        )
        metadata_by_pulse[pulse_id]["merged_paths"] = {
            "pulse": f"merged/pulses/{pulse_id}.json",
            "indicators": f"merged/indicators/{pulse_id}.json"
            if indicator_sources
            else None,
        }

    saved_pulse_ids = set(saved_pulses)
    actor_indexes = build_actor_indexes(actor_by_id, metadata_by_pulse, saved_pulse_ids)

    actor_file_manifest = []
    used_filenames: set[str] = set()
    for actor_id, index in sorted(actor_indexes.items(), key=lambda item: (item[1]["actor"].get("name") or item[0]).casefold()):
        actor_name = index["actor"].get("name") or actor_id
        filename = f"{slugify_filename(actor_name)}.json"
        if filename in used_filenames:
            filename = f"{slugify_filename(actor_name)}_{slugify_filename(actor_id, 40)}.json"
        used_filenames.add(filename)
        write_json(by_actor_out / filename, index)
        actor_file_manifest.append(
            {
                "actor_id": actor_id,
                "actor_name": actor_name,
                "file": f"by_actor/{filename}",
                "pulse_count": index["pulse_count"],
            }
        )

    pulse_metadata_records = [
        metadata_by_pulse[pulse_id]
        for pulse_id in sorted(metadata_by_pulse)
        if pulse_id in saved_pulse_ids
    ]
    write_json(metadata_out / "pulse_discovery_metadata.json", pulse_metadata_records)
    write_json(metadata_out / "failed_requests.json", failures)
    write_json(metadata_out / "search_pages.json", search_pages)
    write_json(
        metadata_out / "actor_index_manifest.json",
        {
            "generated_at": utc_now(),
            "actor_count": len(actor_file_manifest),
            "actors": actor_file_manifest,
        },
    )
    write_json(
        metadata_out / "merge_manifest.json",
        {
            "merged_at": utc_now(),
            "base_dir": str(args.base_dir),
            "part_dirs": [str(path) for path in part_dirs],
            "unique_saved_pulse_ids": len(saved_pulse_ids),
            "copied_raw_pulse_files": copied_pulses,
            "copied_raw_indicator_files": copied_indicators,
            "missing_indicator_files": missing_indicators,
            "failed_request_count": len(failures),
            "actor_index_count": len(actor_file_manifest),
        },
    )

    print(
        f"Merged {len(saved_pulse_ids)} saved pulse IDs into {merged_dir}. "
        f"Copied {copied_pulses} pulse files and {copied_indicators} indicator files."
    )


if __name__ == "__main__":
    main()
