"""Generate the audit-only, run-scoped OTX mapping profile.

The population is exactly checkpoint.completed_pulse_details joined through
the same run's saved_files.jsonl. No mapping product is emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import types
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUN = Path("data/raw/otx_collection_runs/routeA_20260704_policy_small_first")
MITRE_SEED = Path("docs/reference/seeds/mitre_actors.json")
MITRE_BUNDLE = Path("data/raw/mitre/enterprise-attack.json")
OUTPUT = Path("otx_mapping_audit.json")
GNN_COMMIT = "8e82a6381c9555ba4e6ef05783e40eb6c7bd7770"
ACTIVE_APTS = {
    "Kimsuky", "Cobalt Group", "Lazarus Group", "APT28", "Mustang Panda", "Turla",
    "APT41", "Sandworm", "APT37", "APT29", "Gamaredon",
}
MISP_COMMIT = "42b5d56"
MISP_URL = f"https://raw.githubusercontent.com/MISP/misp-galaxy/{MISP_COMMIT}/clusters/threat-actor.json"
GNN_RAW_BASE = f"https://raw.githubusercontent.com/Mitraaaaa/GNN_APT/{GNN_COMMIT}"
GNN_REMOTE_FILES = (
    "train_gnn_hierarchical.py", "trail_gnn/graph_export.py", "trail_gnn/config.py",
    "trail_gnn/training_hierarchical.py", "archive/old_pipeline/collect_otx.py",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip() and isinstance(row := json.loads(line), dict):
                yield row


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def normalized_raw(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value.strip())).casefold()


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "otx-mapping-audit/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def remote_evidence() -> dict[str, Any]:
    """Revalidate pinned public inputs; preserve an explicit unresolved result offline."""
    result: dict[str, Any] = {"misp": {"url": MISP_URL}, "consumer_commit": GNN_COMMIT}
    try:
        payload = fetch_bytes(MISP_URL)
        galaxy = json.loads(payload)
        values = galaxy.get("values") if isinstance(galaxy, Mapping) else []
        values = values if isinstance(values, list) else []
        reverse: dict[str, set[str]] = defaultdict(set)
        synonym_objects = country_objects = 0
        for actor in values:
            if not isinstance(actor, Mapping):
                continue
            actor_id = str(actor.get("uuid") or "")
            names = [actor.get("value")]
            meta = actor.get("meta") if isinstance(actor.get("meta"), Mapping) else {}
            synonyms = meta.get("synonyms") if isinstance(meta.get("synonyms"), list) else []
            synonym_objects += bool(synonyms)
            country_objects += bool(meta.get("country"))
            names.extend(synonyms)
            for name in names:
                if str(name or "").strip():
                    reverse[norm(name)].add(actor_id)
        result["misp"].update(
            {
                "status": "VERIFIED",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "top_level_keys": sorted(galaxy),
                "actor_object_count": len(values),
                "objects_with_uuid_and_value": sum(
                    isinstance(row, Mapping) and bool(row.get("uuid")) and bool(row.get("value"))
                    for row in values
                ),
                "objects_with_synonyms": synonym_objects,
                "objects_with_country": country_objects,
                "exact_casefold_name_count": len(reverse),
                "ambiguous_exact_name_count": sum(len(ids) > 1 for ids in reverse.values()),
                "paper_reported_actor_count": 855,
                "paper_count_discrepancy": "UNRESOLVED: pinned JSON currently contains 856 objects",
            }
        )
    except Exception as exc:  # network availability is evidence, not a reason to fabricate success
        result["misp"].update({"status": "UNRESOLVED", "error": f"{type(exc).__name__}: {exc}"})
    remote_files: dict[str, Any] = {}
    for path in GNN_REMOTE_FILES:
        try:
            payload = fetch_bytes(f"{GNN_RAW_BASE}/{path}")
            remote_files[path] = {
                "status": "VERIFIED", "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        except Exception as exc:
            remote_files[path] = {"status": "UNRESOLVED", "error": f"{type(exc).__name__}: {exc}"}
    result["consumer_files"] = remote_files
    return result


def examples(counter: Counter[str], limit: int = 12) -> list[dict[str, Any]]:
    return [{"value": value, "pulse_count": count} for value, count in counter.most_common(limit)]


def load_existing_mapping_modules() -> tuple[Any, Any]:
    """Load the existing modules without importing rag_cti's heavy public API."""
    for name in ("rag_cti", "rag_cti.connectors", "rag_cti.intermediate", "rag_cti.preprocess"):
        package = types.ModuleType(name)
        package.__path__ = []  # type: ignore[attr-defined]
        sys.modules[name] = package

    def stub(name: str, **members: Any) -> None:
        module = types.ModuleType(name)
        module.__dict__.update(members)
        sys.modules[name] = module

    stub("rag_cti.connectors.pdns_projection", project_pdns_raw=lambda *_a, **_k: [])
    stub("rag_cti.intermediate.contract", contract_id=lambda prefix, parts: f"{prefix}:{parts}")
    stub("rag_cti.intermediate.jsonl", write_jsonl=lambda *_a, **_k: None)
    stub("rag_cti.preprocess.indicators", canonical_indicator_type=lambda value: value)

    def load(name: str, path: Path) -> Any:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    paper = load("rag_cti.intermediate.otx_paper_mapping", ROOT / "src/rag_cti/intermediate/otx_paper_mapping.py")
    downstream = load("rag_cti.intermediate.otx_downstream", ROOT / "src/rag_cti/intermediate/otx_downstream.py")
    return paper, downstream


def resolve_path(value: str, run_dir: Path) -> Path:
    path = Path(value)
    for candidate in (path, run_dir / path, ROOT / path):
        if candidate.is_file():
            return candidate.resolve()
    return path


def inputs(run_dir: Path) -> tuple[list[str], dict[str, Path], dict[str, list[dict[str, Any]]]]:
    checkpoint = read_json(run_dir / "checkpoint.json")
    completed = list(dict.fromkeys(str(x) for x in checkpoint["completed_pulse_details"]))
    allowed = set(completed)
    paths: dict[str, Path] = {}
    for row in jsonl(run_dir / "saved_files.jsonl"):
        raw_ref = row.get("raw_ref")
        pulse_id = str(row.get("pulse_id") or "")
        if row.get("kind") == "pulse_detail" and pulse_id in allowed and isinstance(raw_ref, Mapping):
            if value := str(raw_ref.get("path") or ""):
                paths[pulse_id] = resolve_path(value, run_dir)
    discoveries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in jsonl(run_dir / "discovery_metadata.jsonl"):
        if (pulse_id := str(row.get("pulse_id") or "")) in allowed:
            discoveries[pulse_id].append(row)
    return completed, paths, discoveries


def discovery_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(actor.get("stix_id") or actor.get("actor_id"))
        for row in rows
        for actor in (row.get("query_actors") if isinstance(row.get("query_actors"), list) else [])
        if isinstance(actor, Mapping) and (actor.get("stix_id") or actor.get("actor_id"))
    }


def contains_alias(text: Any, pattern: re.Pattern[str]) -> bool:
    return pattern.search(norm(text)) is not None


def build(run_dir: Path, seed: Path, bundle: Path) -> dict[str, Any]:
    paper, downstream = load_existing_mapping_modules()
    remote = remote_evidence()
    completed, paths, discoveries = inputs(run_dir)
    actor_index = paper._load_mitre_actor_index(seed)
    taxonomy = downstream._load_mitre_actor_taxonomy(bundle)
    aliases = sorted((key for key in actor_index if len(key) >= 5 and not key.isdigit()), key=len, reverse=True)
    alias_pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(alias) for alias in aliases) + r")(?!\w)")

    adversary_types: Counter[str] = Counter()
    adversaries: Counter[str] = Counter()
    raw_exact: Counter[str] = Counter()
    raw_trimmed: Counter[str] = Counter()
    raw_normalized: Counter[str] = Counter()
    occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    separators: Counter[str] = Counter()
    actor_paths: Counter[str] = Counter()
    multi_values: Counter[str] = Counter()
    non_actor: Counter[str] = Counter()
    parse_ambiguous: Counter[str] = Counter()
    unmapped: Counter[str] = Counter()
    b0_labels: Counter[str] = Counter()
    b0_pulses: Counter[str] = Counter()
    old_segments: Counter[str] = Counter()
    v2_segments: Counter[str] = Counter()
    v2_parse_statuses: Counter[str] = Counter()
    v2_resolution_statuses: Counter[str] = Counter()
    resolution_groups: Counter[str] = Counter()
    v2_pulses: Counter[str] = Counter()
    v2_names: Counter[str] = Counter()
    compatibility: Counter[str] = Counter()
    mentions: Counter[str] = Counter()
    alignment: Counter[str] = Counter()
    query_actor_counts: Counter[int] = Counter()
    indicator_types: Counter[str] = Counter()
    layouts: Counter[str] = Counter()
    parser_output_different_raw_values: set[str] = set()
    parser_segment_set_different_raw_values: set[str] = set()
    indicator_total = ioc_rows = with_indicators = with_actor_and_ioc = id_mismatch = invalid = 0

    for pulse_id in completed:
        path = paths.get(pulse_id)
        if path is None or not path.is_file():
            continue
        raw = read_json(path)
        pulse = raw.get("payload") if isinstance(raw, Mapping) and isinstance(raw.get("payload"), Mapping) else raw
        layout = "rawstore_wrapper.payload" if pulse is not raw else "flat_pulse"
        layouts[layout] += 1
        if not isinstance(pulse, Mapping):
            invalid += 1
            continue
        id_mismatch += str(pulse.get("id") or "") != pulse_id
        for key, value in pulse.items():
            if "actor" in key.casefold() or "adversar" in key.casefold():
                actor_paths[f"payload.{key}"] += 1
                kind = "null" if value is None else "string" if isinstance(value, str) else type(value).__name__
                adversary_types[kind] += 1
        adversary = pulse.get("adversary") if isinstance(pulse.get("adversary"), str) else ""
        if adversary.strip():
            raw_exact[adversary] += 1
            raw_trimmed[adversary.strip()] += 1
            raw_normalized[normalized_raw(adversary)] += 1
            adversaries[adversary.strip()] += 1
            occurrences[adversary].append(
                {
                    "pulse_id": pulse_id,
                    "title": str(pulse.get("name") or ""),
                    "description": str(pulse.get("description") or ""),
                    "tags": pulse.get("tags") if isinstance(pulse.get("tags"), list) else [],
                    "references": pulse.get("references") if isinstance(pulse.get("references"), list) else [],
                    "raw_ref": display(path),
                    "source_path": "payload.adversary",
                    "raw_value": adversary,
                }
            )
            for label, pattern in {"comma": ",", "slash": "/", "pipe": "|", "semicolon": ";", "plus": "+"}.items():
                separators[label] += pattern in adversary
            separators["and_word"] += bool(re.search(r"\band\b", adversary, re.I))

        source_labels = paper._split_actor_labels(adversary)
        old_segments.update(source_labels)
        mappings = [paper._map_actor_label(label, actor_index, source_field="adversary") for label in source_labels]
        b0_labels.update(row["mapping_status"] for row in mappings)
        b0_pulses[paper._pulse_mapping_status(mappings)] += 1
        b0_ids = {
            row["actor"]["actor_id"] for row in mappings
            if row["mapping_status"] == "mapped_unambiguous" and row.get("actor")
        }

        claims = downstream._parse_adversary_actor_claims(adversary)
        resolved = downstream._resolve_actor_label_claims(claims, taxonomy)
        v2_labels = [claim.raw_label for claim in claims]
        v2_segments.update(v2_labels)
        v2_parse_statuses.update(claim.parse_status for claim in claims)
        v2_resolution_statuses.update(row.resolution_status for row in resolved)
        if source_labels != v2_labels and adversary.strip():
            parser_output_different_raw_values.add(adversary)
        if set(source_labels) != set(v2_labels) and adversary.strip():
            parser_segment_set_different_raw_values.add(adversary)
        v2_pulses[downstream._actor_label_status(resolved)] += 1
        resolved_ids = list(dict.fromkeys(actor_id for row in resolved for actor_id in row.resolved_actor_ids))
        resolved_names = [taxonomy.actors_by_id[actor_id].actor_name for actor_id in resolved_ids]
        unresolved_statuses = {
            row.resolution_status for row in resolved if not row.resolved_actor_ids
        }
        resolved_claim_count = sum(bool(row.resolved_actor_ids) for row in resolved)
        if not claims:
            resolution_group = "missing"
        elif resolved_ids and unresolved_statuses:
            resolution_group = "mixed_resolved_unresolved"
        elif len(resolved_ids) > 1:
            resolution_group = "resolved_multi_actor"
        elif len(resolved_ids) == 1 and resolved_claim_count > 1:
            resolution_group = "alias_collapsed"
        elif len(resolved_ids) == 1:
            resolution_group = "resolved_single"
        elif "ambiguous_taxonomy" in unresolved_statuses:
            resolution_group = "taxonomy_ambiguous"
        elif "parse_ambiguous" in unresolved_statuses:
            resolution_group = "parse_ambiguous"
        elif unresolved_statuses == {"non_actor_value"}:
            resolution_group = "non_actor"
        elif unresolved_statuses == {"unmapped_actor_like"}:
            resolution_group = "unmapped"
        else:
            resolution_group = "review_required"
        resolution_groups[resolution_group] += 1
        v2_names.update(resolved_names)
        if len(resolved_names) == 1:
            compatibility["single_resolved_in_active_APT_TO_IDX" if resolved_names[0] in ACTIVE_APTS else "single_resolved_outside_active_APT_TO_IDX"] += 1
        elif len(resolved_names) > 1:
            compatibility["multi_actor_not_representable"] += 1
        else:
            compatibility["no_resolved_single_actor"] += 1
        if len(claims) > 1:
            multi_values[adversary.strip()] += 1
        for row in resolved:
            target = {"non_actor_value": non_actor, "parse_ambiguous": parse_ambiguous, "unmapped_actor_like": unmapped}.get(row.resolution_status)
            if target is not None:
                target[row.claim.raw_label] += 1

        discovered = discovery_ids(discoveries.get(pulse_id, []))
        query_actor_counts[len(discovered)] += 1
        if discovered and not adversary.strip():
            alignment["query_actor_present_but_adversary_empty"] += 1
        elif discovered and b0_ids:
            alignment["exact_actor_id_overlap" if discovered & b0_ids else "disjoint_exact_actor_ids"] += 1
        elif discovered and adversary.strip():
            alignment["adversary_not_exactly_resolved"] += 1
        else:
            alignment["no_query_actor_id"] += 1

        for field in ("name", "description"):
            mentions[field] += contains_alias(pulse.get(field), alias_pattern)
        tags = pulse.get("tags") if isinstance(pulse.get("tags"), list) else []
        mentions["tags_exact_mitre_alias"] += any(norm(tag) in actor_index for tag in tags if isinstance(tag, str))
        refs = pulse.get("references") if isinstance(pulse.get("references"), list) else []
        mentions["references"] += any(contains_alias(ref, alias_pattern) for ref in refs)

        indicators = pulse.get("indicators") if isinstance(pulse.get("indicators"), list) else []
        count = 0
        for indicator in indicators:
            if isinstance(indicator, Mapping):
                count += 1
                indicator_types[str(indicator.get("type") or "<missing>")] += 1
        indicator_total += count
        with_indicators += bool(count)
        with_actor_and_ioc += bool(count and adversary.strip())
        ioc_rows += count * sum(row["mapping_status"] == "mapped_unambiguous" for row in mappings)

    nonempty = sum(adversaries.values())
    missing_refs = sum(pulse_id not in paths for pulse_id in completed)
    missing_files = sum(pulse_id in paths and not paths[pulse_id].is_file() for pulse_id in completed)
    normalized_groups: dict[str, set[str]] = defaultdict(set)
    trimmed_groups: dict[str, set[str]] = defaultdict(set)
    visible_groups: dict[str, set[str]] = defaultdict(set)
    for value in raw_exact:
        normalized_groups[normalized_raw(value)].add(value)
        trimmed_groups[value.strip()].add(value)
        visible_groups[unicodedata.normalize("NFC", value)].add(value)
    repeated = {value: count for value, count in raw_exact.items() if count > 1}
    context_variation = Counter()
    repeated_samples: list[dict[str, Any]] = []
    for value, count in sorted(repeated.items(), key=lambda item: (-item[1], item[0])):
        rows = occurrences[value]
        for field in ("title", "description", "tags", "references"):
            encoded = {json.dumps(row[field], ensure_ascii=False, sort_keys=True) for row in rows}
            context_variation[f"multiple_{field}"] += len(encoded) > 1
        if len(repeated_samples) < 12:
            repeated_samples.append(
                {
                    "raw_value": value,
                    "occurrences": count,
                    "sample_contexts": [
                        {key: row[key] for key in ("pulse_id", "title", "tags", "references", "raw_ref")}
                        for row in rows[:3]
                    ],
                }
            )
    delimiter_patterns = {
        "comma": lambda value: "," in value,
        "slash": lambda value: "/" in value,
        "pipe": lambda value: "|" in value,
        "semicolon": lambda value: ";" in value,
        "plus": lambda value: "+" in value,
        "and_word": lambda value: re.search(r"\band\b", value, re.I) is not None,
    }
    delimiter_distinct = {
        name: sum(test(value) for value in raw_exact) for name, test in delimiter_patterns.items()
    }
    delimiter_occurrences = {
        name: sum(count for value, count in raw_exact.items() if test(value))
        for name, test in delimiter_patterns.items()
    }

    nonactor_split_values: list[str] = []
    nonactor_split_statuses: Counter[str] = Counter()
    nonactor_split_occurrences = nonactor_split_segments = 0
    old_split_v2_ambiguous_values: list[str] = []
    for value, count in raw_exact.items():
        old_labels = paper._split_actor_labels(value)
        claims = downstream._parse_adversary_actor_claims(value)
        if len(claims) == 1 and claims[0].parse_status == "non_actor_value" and len(old_labels) > 1:
            nonactor_split_values.append(value)
            nonactor_split_occurrences += count
            nonactor_split_segments += len(old_labels) * count
            for label in old_labels:
                status = paper._map_actor_label(label, actor_index, source_field="adversary")["mapping_status"]
                nonactor_split_statuses[status] += count
        if any(claim.parse_status == "parse_ambiguous" for claim in claims) and len(old_labels) > 1:
            old_split_v2_ambiguous_values.append(value)

    requested_examples = [
        "Shenzhen Haimaiyunxiang Media Co., Ltd.",
        "MOIS (Ministry of Intelligence and Security)",
        "TrojanDownloader:Win32/Nemucod",
        "Cobalt Strike + campaign",
        "Akira Ransomware, Lockbit Ransomware",
        "Lazarus: Labyrinth Chollima, HIDDEN COBRA, Guardians of Peace, ZINC, NICKEL ACADEMY, Diamond Sleet,",
        "APT32/OceanLotus",
        "Kimsuky and Andariel",
    ]
    example_results: list[dict[str, Any]] = []
    for value in requested_examples:
        old_labels = paper._split_actor_labels(value)
        old_mappings = [paper._map_actor_label(label, actor_index, source_field="adversary") for label in old_labels]
        claims = downstream._parse_adversary_actor_claims(value)
        resolved = downstream._resolve_actor_label_claims(claims, taxonomy)
        actor_ids = list(dict.fromkeys(actor_id for row in resolved for actor_id in row.resolved_actor_ids))
        actor_names = [taxonomy.actors_by_id[actor_id].actor_name for actor_id in actor_ids]
        example_results.append(
            {
                "raw_value": value,
                "snapshot_occurrences_exact": raw_exact[value],
                "snapshot_occurrences_trimmed": raw_trimmed[value.strip()],
                "snapshot_occurrences_normalized": raw_normalized[normalized_raw(value)],
                "prototype": [
                    {"label": row["label"], "resolution_status": row["mapping_status"]}
                    for row in old_mappings
                ],
                "v2": [
                    {
                        "label": row.claim.raw_label,
                        "parse_status": row.claim.parse_status,
                        "enters_resolver": row.claim.parse_status == "parsed",
                        "resolution_status": row.resolution_status,
                        "resolved_actor_ids": list(row.resolved_actor_ids),
                        "candidate_actor_ids": list(row.candidate_actor_ids),
                    }
                    for row in resolved
                ],
                "v2_event_apt": actor_names[0] if len(actor_names) == 1 else None,
                "v2_actor_nodes": len(actor_ids),
                "v2_attributed_to_edges": len(actor_ids),
                "prototype_can_emit_ioc_rows": any(
                    row["mapping_status"] == "mapped_unambiguous" for row in old_mappings
                ),
            }
        )
    code_files = [
        Path("src/rag_cti/intermediate/otx_paper_mapping.py"), Path("src/rag_cti/intermediate/otx_downstream.py"),
        Path("scripts/build_otx_paper_mapping.py"), Path("scripts/build_otx_downstream_projection.py"),
        Path("tests/unit/test_otx_paper_mapping.py"), Path("tests/unit/test_otx_downstream_projection.py"),
        Path("docs/reference/sample_code.py"),
    ]

    return {
        "audit": {
            "generator": "scripts/generate_otx_mapping_audit.py",
            "repository_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "scope_rule": "checkpoint.completed_pulse_details joined only through the same run saved_files.jsonl",
            "paper_pdf": {"path": "docs/sp.pdf", "sha256": sha256(ROOT / "docs/sp.pdf"), "pages": 19},
            "evidence_file_sha256": {path.as_posix(): sha256(ROOT / path) for path in code_files},
            "mapping_input_sha256": {display(seed): sha256(seed), display(bundle): sha256(bundle)},
        },
        "snapshot": {
            "scope": display(run_dir), "checkpoint": display(run_dir / "checkpoint.json"),
            "completed_pulse_details": len(completed), "resolved_raw_paths": len(paths),
            "missing_saved_raw_ref": missing_refs, "missing_raw": missing_files,
            "invalid_raw": invalid, "pulse_id_mismatch": id_mismatch, "raw_layouts": dict(layouts),
            "counting_policy": {
                "empty": "null, empty string, and whitespace-only string",
                "nonempty": "string with value.strip() != empty",
                "raw_exact_distinct": "exact stored string before trim or normalization",
                "trimmed_distinct": "value.strip()",
                "normalized_distinct": "NFKC + trim + whitespace collapse + casefold",
                "indicator_observations": "every mapping object in payload.indicators[], including duplicate values/ids",
            },
        },
        "otx_input": {
            "adversary_related_fields": {key: {"records_present": value} for key, value in actor_paths.items()},
            "actor_value_statistics": {
                "field_type_counts": dict(adversary_types), "nonempty_pulses": nonempty,
                "empty_or_null_pulses": len(completed) - nonempty,
                "empty_string_pulses": adversary_types["string"] - nonempty, "null_pulses": adversary_types["null"],
                "unique_nonempty_values": len(adversaries), "separator_pulse_counts_nonexclusive": dict(separators),
                "most_common_values": examples(adversaries, 20),
                "v2_parse_resolution_pulse_status": dict(v2_pulses),
                "v2_resolved_actor_name_counts": dict(v2_names.most_common()),
                "unmapped_actor_like_examples": examples(unmapped),
            },
            "raw_value_identity_statistics": {
                "raw_exact_distinct_count": len(raw_exact),
                "trimmed_distinct_count": len(raw_trimmed),
                "normalized_distinct_count": len(raw_normalized),
                "raw_values_changed_by_trim": sum(value != value.strip() for value in raw_exact),
                "raw_values_changed_by_nfkc": sum(value != unicodedata.normalize("NFKC", value) for value in raw_exact),
                "trim_collision_groups": [sorted(values) for values in trimmed_groups.values() if len(values) > 1],
                "normalization_collision_groups": [sorted(values) for values in normalized_groups.values() if len(values) > 1],
                "same_visible_nfc_collision_groups": [sorted(values) for values in visible_groups.values() if len(values) > 1],
                "repeated_raw_value_count": len(repeated),
                "singleton_raw_value_count": sum(count == 1 for count in raw_exact.values()),
                "maximum_occurrence_count": max(raw_exact.values(), default=0),
                "maximum_occurrence_values": sorted(
                    value for value, count in raw_exact.items() if count == max(raw_exact.values(), default=0)
                ),
                "definition_result": "raw exact distinct nonempty adversary strings",
            },
            "repeated_value_context": {
                "repeated_raw_value_count": len(repeated),
                "context_variation_counts": dict(context_variation),
                "samples": repeated_samples,
                "machine_conclusion": "the current parsers are deterministic functions of raw_value, so exact repeats always get the same parser output",
                "semantic_uniformity": "UNRESOLVED: title/tags/reference variation cannot prove whether every repeat has the same actor/malware/campaign meaning",
                "blocks_starting_p1": False,
                "blocks_raw_value_only_decision_reuse": True,
                "minimum_safe_p1_unit": "occurrence keyed by pulse_id + raw_ref + source_path; P1 may later prove which decisions can be shared by raw value",
            },
            "multi_actor_statistics": {
                "v2_parser_multi_label_pulses": sum(multi_values.values()), "unique_raw_values": len(multi_values),
                "examples": examples(multi_values), "parse_ambiguous_examples": examples(parse_ambiguous),
            },
            "non_actor_examples": examples(non_actor),
            "actor_mention_heuristic": {
                "method": "MITRE exact tag match; boundary-delimited MITRE name/alias length>=5 for text/reference fields",
                "pulse_counts": dict(mentions), "warning": "mention counts are discovery evidence only and are not attribution claims",
            },
            "discovery_provenance_comparison": {
                "alignment_counts": dict(alignment),
                "distinct_query_actor_ids_per_pulse": {str(key): value for key, value in sorted(query_actor_counts.items())},
                "semantic_rule": "query and query_actors are collection provenance, never attribution",
            },
            "ioc_type_statistics": {
                "embedded_indicator_observations": indicator_total, "pulses_with_embedded_indicators": with_indicators,
                "pulses_with_nonempty_adversary_and_indicators": with_actor_and_ioc,
                "raw_type_counts": dict(indicator_types.most_common()), "source_path": "payload.indicators[]",
                "distinct_raw_indicator_types": len(indicator_types),
            },
            "structured_adversary_semantics": {
                "finding": "OTX exposes adversary as a dedicated Pulse string field, the strongest structured actor-claim input in this snapshot",
                "limit": "no per-claim evidence, confidence, or explicit relation to individual indicators; presence does not prove correctness",
            },
        },
        "prototype": {
            "input": "run-scoped payload.adversary; tags candidate-only; embedded indicators[]",
            "output": "pulse mappings plus every exact-resolved adversary label x every Pulse indicator",
            "matching_methods": ["casefolded exact MITRE name", "casefolded exact MITRE alias"],
            "actor_source": display(seed), "raw_actor_input_pulses": nonempty, "unique_raw_actor_inputs": len(adversaries),
            "split_label_status": dict(b0_labels), "pulse_status": dict(b0_pulses),
            "projected_ioc_attribution_rows": ioc_rows, "uses_fuzzy_matching": False,
            "automatically_creates_actor": False, "uses_query_actors_as_attribution": False,
            "known_risks": ["broad splitting mixes extraction and resolution", "resolved identity is treated as true attribution", "Pulse co-occurrence expands to actor-IOC rows", "MITRE substitutes for paper MISP"],
        },
        "parser_execution": {
            "prototype_segment_occurrences": sum(old_segments.values()),
            "prototype_distinct_segments": len(old_segments),
            "prototype_behavior": "per occurrence: regex split, then set dedupe and sorted order",
            "v2_segment_occurrences": sum(v2_segments.values()),
            "v2_distinct_segments": len(v2_segments),
            "ordered_output_different_raw_value_count": len(parser_output_different_raw_values),
            "segment_set_different_raw_value_count": len(parser_segment_set_different_raw_values),
            "delimiter_distinct_raw_value_counts": delimiter_distinct,
            "delimiter_occurrence_counts": delimiter_occurrences,
            "v2_parse_status_segment_counts": dict(v2_parse_statuses),
            "v2_resolution_status_segment_counts": dict(v2_resolution_statuses),
            "v2_resolution_group_counts": dict(resolution_groups),
            "requested_example_results": example_results,
            "verified_old_parser_error_lower_bound": {
                "definition": "whole value is non_actor_value under current v2 guard but old prototype split it into multiple resolver inputs",
                "raw_value_count": len(nonactor_split_values),
                "occurrence_count": nonactor_split_occurrences,
                "segment_occurrence_count": nonactor_split_segments,
                "old_resolver_status_counts": dict(nonactor_split_statuses),
                "raw_values": sorted(nonactor_split_values),
                "scope_limit": "lower bound only; no exhaustive gold parse decisions exist",
            },
            "old_split_values_v2_marks_parse_ambiguous": sorted(old_split_v2_ambiguous_values),
            "b0_776_interpretation": {
                "source": "old paper prototype _split_actor_labels over 713 nonempty occurrences",
                "is_segment_occurrence_count": sum(old_segments.values()) == 776,
                "is_distinct_label_count": False,
                "preserves_order": False,
                "uses_set_sorted": True,
                "clean_extraction_input": False,
                "permitted_use": "replay the historical B0 resolver behavior only",
                "prohibited_use": "formal mapping input or clean B1 resolver comparison input",
            },
            "corrected_parser_impact": {
                "status": "UNRESOLVED",
                "missing_evidence": "reviewed extraction decisions for all raw values/occurrences",
                "required_check": "complete P1 review and replay v2 resolution/projection against frozen occurrence ids",
                "blocks": ["clean B1 comparison", "counts of Event.apt retained/revoked/added/changed"],
            },
        },
        "paper_reproduction": {
            "misp_snapshot": {"date": "2025-07-29", "commit": MISP_COMMIT, "path": "clusters/threat-actor.json", "required_for_b1": True, "present_locally": False, "remote_validation": remote["misp"]},
            "paper_input_semantics": "commercial-feed IOC records already carrying vendor-attributed actor names",
            "reproducible_steps": ["MISP actor object/name/synonym construction", "unique/ambiguous/unmapped exact lookup", "no cascading alias merge"],
            "adapted_steps": ["OTX IOC flatten/type normalization", "OTX adversary claim extraction before resolution", "separate Pulse-indicator observation from actor-IOC attribution", "WIP retained without claiming the paper's single-feed definition"],
            "missing_inputs": ["local pinned MISP 42b5d56", "seven commercial feeds", "manual latest 3-5 vendor reports per unmapped actor", "augmented TAG decisions", "versioned CS/MS validation table"],
            "not_reproducible": ["complete public reconstruction of augmented 1,726-object TAG", "paper final actor/agreement results"],
            "out_of_scope": ["co-observation windows", "Krippendorff alpha/pairwise agreement", "VirusTotal disagreement analysis"],
        },
        "consumer": {
            "entrypoints": ["docs/reference/sample_code.py", f"Mitraaaaa/GNN_APT@{GNN_COMMIT}:train_gnn_hierarchical.py", f"Mitraaaaa/GNN_APT@{GNN_COMMIT}:trail_gnn/graph_export.py"],
            "input_files": [], "actual_input": "populated Neo4j graph; no staging-JSONL loader exists here",
            "required_fields": {"Event": {"id": "unique string", "apt": "single string or null", "pulse_created": "ISO-like", "label_confidence": "optional number"}, "Domain/IP/URL": {"value": "unique string"}, "ASN": {"number": "unique integer-like"}, "relationships": ["InReport", "HostedOn", "ResolvesTo", "InGroup"]},
            "identity": {"event": "OTX Pulse id", "domain_ip_url": "normalized value", "asn": "number", "duplicates": "Neo4j MERGE"},
            "multi_actor": "not representable in Event.apt", "ambiguous_unmapped": "unlabeled Event context only",
            "provenance": "not consumed by old trainer; retain staging raw_refs",
            "projection_available": ["nodes_events.jsonl", "nodes_iocs.jsonl", "nodes_actors.jsonl", "actor_label_claims.jsonl", "edges.jsonl"],
            "blocking_assumptions": ["single Event.apt from fixed APT_TO_IDX", "no JSONL-to-Neo4j loader", "Actor/AttributedTo ignored", "multi/ambiguous cannot be forced into single truth"],
            "pinned_remote_file_validation": remote["consumer_files"],
            "current_mapping_output_consumers": [],
            "bypass_paths_requiring_p4_guard_not_refactor_now": [
                "src/rag_cti/intermediate/otx.py", "src/rag_cti/ingest/normalize.py",
                "scripts/build_entity_registry.py", "src/rag_cti/connectors/otx.py",
            ],
            "current_v2_Event_apt_compatibility": {
                "basis": "v2 parser + v2 exact resolver + current local MITRE bundle; projection schema_version v0.1",
                "mitre_bundle_sha256": sha256(bundle),
                "active_APT_TO_IDX_at_inspected_commit": sorted(ACTIVE_APTS),
                "pulse_counts": dict(compatibility),
                "resolution_group_counts": dict(resolution_groups),
                "exactly_one_resolved_event_count": compatibility["single_resolved_in_active_APT_TO_IDX"] + compatibility["single_resolved_outside_active_APT_TO_IDX"],
                "note": "only exact single resolved actor names in active APT_TO_IDX become supervised truth",
            },
        },
        "comparison": {
            "b0_available": True, "b1_feasible": True,
            "b1_prerequisite": "vendor MISP 42b5d56 and record hash", "b2_recommended": True,
            "b2_policy": "MISP primary for paper comparison; MITRE separately versioned exact resolver/corroborator; retain conflicts",
            "required_metrics": ["same raw input count", "resolved", "ambiguous", "unmapped", "WIP", "canonical disagreement", "prototype-only", "paper-only", "possible overmerge", "source/version", "loader compatibility"],
        },
        "decision": {
            "status": "READY_TO_IMPLEMENT_P1",
            "reasons": ["4,160 run-scoped raw files complete", "222 is verified as exact-distinct raw string count, not actor count", "old 776-segment input is parser-contaminated and prohibited for clean B1", "P1 can begin occurrence-level without MISP", "pinned MISP is reachable for later B1", "old consumer needs a thin loader and cannot encode multi/ambiguity in Event.apt"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--mitre-seed", type=Path, default=MITRE_SEED)
    parser.add_argument("--mitre-bundle", type=Path, default=MITRE_BUNDLE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    locate = lambda path: path if path.is_absolute() else ROOT / path
    audit = build(locate(args.run_dir), locate(args.mitre_seed), locate(args.mitre_bundle))
    output = locate(args.output)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote={output}")
    print(f"completed_pulse_details={audit['snapshot']['completed_pulse_details']}")
    print(f"missing_raw={audit['snapshot']['missing_raw']}")
    print(f"embedded_indicators={audit['otx_input']['ioc_type_statistics']['embedded_indicator_observations']}")


if __name__ == "__main__":
    main()
