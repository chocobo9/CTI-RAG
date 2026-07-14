"""Paper-style OTX actor/IOC attribution mapping artifacts.

The mapping follows the "APT to Disagree" shape: keep source actor labels,
normalize them through a public actor alias map, and emit flat IOC attribution
rows that can be compared by indicator value, type, actor id, and time.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_cti.intermediate.contract import contract_id
from rag_cti.preprocess.indicators import canonical_indicator_type

_ACTOR_SPLIT_RE = re.compile(r"\s*(?:,|/|\||;|\band\b|\+)\s*", re.IGNORECASE)


@dataclass(frozen=True)
class OTXPaperMappingResult:
    output_dir: Path
    completed_pulses: int
    pulses_read: int
    pulse_actor_rows: int
    ioc_attribution_rows: int
    indicator_rows: int


def build_otx_paper_mapping(
    run_dir: Path,
    output_dir: Path,
    *,
    mitre_actors_path: Path,
    indicator_source: str = "detail",
    compress_large_outputs: bool = False,
    emit_indicator_flat: bool = True,
    progress_every: int = 0,
) -> OTXPaperMappingResult:
    """Build deterministic OTX actor mapping and paper-style IOC attribution rows."""
    run_dir = Path(run_dir)
    output_dir = Path(output_dir)
    if indicator_source != "detail":
        raise ValueError("only indicator_source='detail' is currently supported")

    checkpoint = _read_json(run_dir / "checkpoint.json")
    completed_pulses = sorted(str(pid) for pid in checkpoint.get("completed_pulse_details", []))
    raw_refs = _load_pulse_detail_refs(run_dir, set(completed_pulses))
    discoveries = _load_discoveries(run_dir)
    actor_index = _load_mitre_actor_index(mitre_actors_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    unmapped_labels: Counter[str] = Counter()
    ambiguous_labels: Counter[str] = Counter()
    pulse_status: Counter[str] = Counter()
    indicator_type_raw: Counter[str] = Counter()
    indicator_type_canonical: Counter[str] = Counter()
    mapped_actor_ids: set[str] = set()
    pulses_with_indicators: set[str] = set()
    actor_row_count = 0
    pulses_read = 0
    indicator_count = 0
    ioc_count = 0
    ioc_artifact = (
        "ioc_attributions_paper_style.jsonl.gz"
        if compress_large_outputs
        else "ioc_attributions_paper_style.jsonl"
    )
    indicator_artifact = (
        ("indicators_flat.jsonl.gz" if compress_large_outputs else "indicators_flat.jsonl")
        if emit_indicator_flat
        else None
    )

    with (
        _JsonlWriter(output_dir / "pulse_actor_mappings.jsonl") as pulse_writer,
        _JsonlWriter(output_dir / ioc_artifact) as ioc_writer,
        _optional_jsonl_writer(output_dir, indicator_artifact) as indicator_writer,
    ):
        for pulse_index, pulse_id in enumerate(completed_pulses, start=1):
            if progress_every and pulse_index % progress_every == 0:
                print(
                    f"processed_pulses={pulse_index}/{len(completed_pulses)} "
                    f"ioc_rows={ioc_count} indicator_rows={indicator_count}",
                    file=sys.stderr,
                    flush=True,
                )
            raw_ref = raw_refs.get(pulse_id)
            if raw_ref is None:
                pulse_actor_row = _missing_pulse_row(pulse_id, discoveries.get(pulse_id, []))
                pulse_writer.write(pulse_actor_row)
                pulse_status[pulse_actor_row["mapping_status"]] += 1
                continue

            raw_obj = _read_json(raw_ref)
            pulse = _payload(raw_obj)
            if not isinstance(pulse, Mapping):
                pulse_actor_row = _missing_pulse_row(pulse_id, discoveries.get(pulse_id, []))
                pulse_writer.write(pulse_actor_row)
                pulse_status[pulse_actor_row["mapping_status"]] += 1
                continue
            pulses_read += 1

            source_actor_labels = _split_actor_labels(_text(pulse.get("adversary")))
            tag_actor_labels = _strings(pulse.get("tags"))
            source_mappings = [
                _map_actor_label(label, actor_index, source_field="adversary")
                for label in source_actor_labels
            ]
            tag_mappings = [
                _map_actor_label(label, actor_index, source_field="tags")
                for label in tag_actor_labels
            ]
            accepted_source_mappings = [
                row for row in source_mappings if row["mapping_status"] == "mapped_unambiguous"
            ]
            for row in source_mappings:
                if row["mapping_status"] == "unmapped":
                    unmapped_labels[row["label"]] += 1
                if row["mapping_status"] == "mapped_ambiguous":
                    ambiguous_labels[row["label"]] += 1

            discovery_rows = discoveries.get(pulse_id, [])
            if emit_indicator_flat or accepted_source_mappings:
                pulse_has_indicators = False
                for indicator in _iter_indicator_rows_from_pulse(pulse, raw_ref):
                    pulse_has_indicators = True
                    if emit_indicator_flat:
                        indicator_writer.write(indicator)
                        indicator_count += 1
                        indicator_type_raw[str(indicator.get("indicator_type_raw"))] += 1
                        indicator_type_canonical[str(indicator.get("indicator_type_canonical"))] += 1
                    if accepted_source_mappings:
                        for mapping in accepted_source_mappings:
                            row = _ioc_attribution_row(pulse, indicator, mapping)
                            ioc_writer.write(row)
                            ioc_count += 1
                            mapped_actor_ids.add(row["actor_id"])
                if pulse_has_indicators:
                    pulses_with_indicators.add(pulse_id)

            pulse_actor_row = {
                "pulse_id": pulse_id,
                "pulse_name": _text(pulse.get("name")) or None,
                "pulse_created": _text(pulse.get("created")) or None,
                "pulse_modified": _text(pulse.get("modified")) or None,
                "source_actor_label_raw": _text(pulse.get("adversary")) or None,
                "source_actor_labels": source_actor_labels,
                "source_actor_mappings": source_mappings,
                "tag_actor_candidates": tag_mappings,
                "accepted_actor_ids": sorted(
                    {row["actor"]["actor_id"] for row in accepted_source_mappings}
                ),
                "mapping_status": _pulse_mapping_status(source_mappings),
                "direct_attribution_basis": "otx.adversary",
                "discovery_provenance": _compact_discoveries(discovery_rows),
                "collection_provenance_note": (
                    "MITRE search query provenance is audit metadata only; it is not used as "
                    "actor attribution in this mapping."
                ),
                "raw_ref": _raw_ref(raw_ref, raw_obj),
            }
            pulse_writer.write(pulse_actor_row)
            pulse_status[pulse_actor_row["mapping_status"]] += 1
            actor_row_count += len(source_mappings)

    summary = _summary(
        completed_pulses=completed_pulses,
        pulse_status=pulse_status,
        pulses_with_indicators=pulses_with_indicators,
        indicator_count=indicator_count,
        ioc_count=ioc_count,
        mapped_actor_ids=mapped_actor_ids,
        indicator_type_raw=indicator_type_raw,
        indicator_type_canonical=indicator_type_canonical,
        actor_index=actor_index,
        unmapped_labels=unmapped_labels,
        ambiguous_labels=ambiguous_labels,
        indicator_source=indicator_source,
        run_dir=run_dir,
        mitre_actors_path=mitre_actors_path,
    )
    _write_json(output_dir / "mapping_summary.json", summary)
    _write_json(
        output_dir / "mapping_manifest.json",
        {
            "projection": "otx_paper_style_actor_ioc_mapping",
            "schema_version": "v0.1",
            "method": {
                "paper_basis": (
                    "Normalize source-provided actor labels through an actor alias map, "
                    "then compare attributed IOCs by normalized indicator value, type, actor id, "
                    "and observation time."
                ),
                "actor_taxonomy": "MITRE ATT&CK intrusion-set actors and aliases",
                "direct_actor_label_source": "OTX pulse detail field: adversary",
                "not_used_as_attribution": ["MITRE actor search query provenance"],
                "candidate_only": ["OTX tags mapped through MITRE aliases"],
                "misp_tag_gap": (
                    "The paper used MISP Threat Actor Galaxy; no local MISP Galaxy snapshot "
                    "is present in this repo, so this run is MITRE-backed."
                ),
            },
            "inputs": {
                "run_dir": str(run_dir),
                "mitre_actors_path": str(mitre_actors_path),
                "indicator_source": indicator_source,
                "compress_large_outputs": compress_large_outputs,
                "emit_indicator_flat": emit_indicator_flat,
            },
            "artifacts": {
                "pulse_actor_mappings": "pulse_actor_mappings.jsonl",
                "ioc_attributions_paper_style": ioc_artifact,
                "indicators_flat": indicator_artifact,
                "mapping_summary": "mapping_summary.json",
            },
            "counts": summary["counts"],
        },
    )

    return OTXPaperMappingResult(
        output_dir=output_dir,
        completed_pulses=len(completed_pulses),
        pulses_read=pulses_read,
        pulse_actor_rows=actor_row_count,
        ioc_attribution_rows=ioc_count,
        indicator_rows=indicator_count,
    )


def _load_mitre_actor_index(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _read_json(path)
    actors = payload.get("actors")
    if not isinstance(actors, list):
        raise ValueError(f"MITRE actor seed does not contain actors[]: {path}")

    by_alias: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for actor in actors:
        if not isinstance(actor, Mapping):
            continue
        aliases = actor.get("aliases") if isinstance(actor.get("aliases"), list) else []
        names = [_text(actor.get("name")), *[_text(alias) for alias in aliases]]
        for alias in names:
            if not alias:
                continue
            row = {
                "actor_id": _text(actor.get("actor_id")) or _text(actor.get("stix_id")) or alias,
                "actor_name": _text(actor.get("name")) or alias,
                "stix_id": _text(actor.get("stix_id")) or None,
                "mitre_attack_id": _text(actor.get("mitre_attack_id")) or None,
                "matched_alias": alias,
                "matched_alias_normalized": _normalize(alias),
                "source": "mitre_attack",
            }
            key = _normalize(alias)
            if row not in by_alias[key]:
                by_alias[key].append(row)
    return {key: sorted(rows, key=lambda item: item["actor_id"]) for key, rows in by_alias.items()}


def _load_pulse_detail_refs(run_dir: Path, completed_pulses: set[str]) -> dict[str, Path]:
    refs: dict[str, Path] = {}
    for row in _read_jsonl(run_dir / "saved_files.jsonl"):
        if row.get("kind") != "pulse_detail":
            continue
        pulse_id = _text(row.get("pulse_id"))
        if pulse_id not in completed_pulses:
            continue
        raw_ref = row.get("raw_ref")
        if isinstance(raw_ref, Mapping) and raw_ref.get("path"):
            refs[pulse_id] = Path(str(raw_ref["path"]))
    return refs


def _load_discoveries(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    path = run_dir / "discovery_metadata.jsonl"
    if not path.exists():
        return {}
    for row in _read_jsonl(path):
        pulse_id = _text(row.get("pulse_id"))
        if pulse_id:
            out[pulse_id].append(row)
    return dict(out)


def _iter_indicator_rows_from_pulse(
    pulse: Mapping[str, Any],
    raw_path: Path,
) -> Iterable[dict[str, Any]]:
    pulse_id = _text(pulse.get("id"))
    indicators = pulse.get("indicators")
    if not isinstance(indicators, list):
        return
    for ind in indicators:
        if not isinstance(ind, Mapping):
            continue
        value = _text(ind.get("indicator"))
        if not value:
            continue
        raw_type = _text(ind.get("type")) or None
        canonical = canonical_indicator_type(raw_type) if raw_type else None
        created = _text(ind.get("created")) or None
        expiration = _text(ind.get("expiration")) or None
        yield {
            "row_id": contract_id(
                "otx_indicator",
                (pulse_id, value, raw_type, created, _text(ind.get("id"))),
            ),
            "pulse_id": pulse_id,
            "indicator_id": ind.get("id"),
            "indicator_value": value,
            "indicator_value_normalized": _normalize_indicator_value(value, canonical),
            "indicator_type_raw": raw_type,
            "indicator_type_canonical": canonical,
            "indicator_created": created,
            "indicator_expiration": expiration,
            "observed_start": created or _text(pulse.get("created")) or None,
            "observed_end": expiration,
            "observation_window_basis": (
                "indicator_created_to_expiration"
                if created and expiration
                else "indicator_created_point"
                if created
                else "pulse_created_fallback"
                if _text(pulse.get("created"))
                else "missing"
            ),
            "is_active": ind.get("is_active"),
            "title": _text(ind.get("title")) or None,
            "description": _text(ind.get("description")) or None,
            "raw_path": str(raw_path),
        }


def _ioc_attribution_row(
    pulse: Mapping[str, Any],
    indicator: Mapping[str, Any],
    mapping: Mapping[str, Any],
) -> dict[str, Any]:
    actor = mapping["actor"]
    return {
        "row_id": contract_id(
            "otx_ioc_attr",
            (
                indicator["pulse_id"],
                indicator["indicator_value_normalized"],
                indicator.get("indicator_type_canonical"),
                actor["actor_id"],
                indicator.get("indicator_created"),
            ),
        ),
        "vendor": "otx",
        "pulse_id": indicator["pulse_id"],
        "pulse_name": _text(pulse.get("name")) or None,
        "pulse_created": _text(pulse.get("created")) or None,
        "pulse_modified": _text(pulse.get("modified")) or None,
        "indicator_value": indicator["indicator_value"],
        "indicator_value_normalized": indicator["indicator_value_normalized"],
        "indicator_type_raw": indicator.get("indicator_type_raw"),
        "indicator_type_canonical": indicator.get("indicator_type_canonical"),
        "indicator_created": indicator.get("indicator_created"),
        "observed_start": indicator.get("observed_start"),
        "observed_end": indicator.get("observed_end"),
        "observation_window_basis": indicator.get("observation_window_basis"),
        "source_actor_label": mapping["label"],
        "source_actor_field": mapping["source_field"],
        "actor_id": actor["actor_id"],
        "actor_name": actor["actor_name"],
        "actor_stix_id": actor.get("stix_id"),
        "actor_mitre_attack_id": actor.get("mitre_attack_id"),
        "matched_alias": actor.get("matched_alias"),
        "actor_country": None,
        "actor_taxonomy": "mitre_attack",
        "mapping_status": mapping["mapping_status"],
    }


def _map_actor_label(
    label: str,
    actor_index: Mapping[str, list[dict[str, Any]]],
    *,
    source_field: str,
) -> dict[str, Any]:
    normalized = _normalize(label)
    actors = actor_index.get(normalized, [])
    if len(actors) == 1:
        status = "mapped_unambiguous"
    elif len(actors) > 1:
        status = "mapped_ambiguous"
    else:
        status = "unmapped"
    return {
        "label": label,
        "label_normalized": normalized,
        "source_field": source_field,
        "mapping_status": status,
        "actor": actors[0] if len(actors) == 1 else None,
        "candidate_actors": actors,
    }


def _pulse_mapping_status(source_mappings: list[dict[str, Any]]) -> str:
    if not source_mappings:
        return "missing_direct_actor_label"
    statuses = {row["mapping_status"] for row in source_mappings}
    if statuses == {"mapped_unambiguous"}:
        actor_ids = {
            row["actor"]["actor_id"]
            for row in source_mappings
            if isinstance(row.get("actor"), Mapping)
        }
        return "mapped_single_actor" if len(actor_ids) == 1 else "mapped_multi_actor"
    if "mapped_ambiguous" in statuses:
        return "ambiguous_actor_label"
    if statuses == {"unmapped"}:
        return "unmapped_direct_actor_label"
    return "partial_actor_mapping"


def _compact_discoveries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        item = {
            "query": row.get("query"),
            "query_normalized": row.get("query_normalized"),
            "query_actors": row.get("query_actors", []),
            "search_page": row.get("search_page"),
            "search_rank": row.get("search_rank"),
            "fetched_at": row.get("fetched_at"),
        }
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            compact.append(item)
    return sorted(compact, key=lambda item: (str(item.get("query_normalized")), str(item.get("search_rank"))))


def _summary(
    *,
    completed_pulses: list[str],
    pulse_status: Counter[str],
    pulses_with_indicators: set[str],
    indicator_count: int,
    ioc_count: int,
    mapped_actor_ids: set[str],
    indicator_type_raw: Counter[str],
    indicator_type_canonical: Counter[str],
    actor_index: Mapping[str, list[dict[str, Any]]],
    unmapped_labels: Counter[str],
    ambiguous_labels: Counter[str],
    indicator_source: str,
    run_dir: Path,
    mitre_actors_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "v0.1",
        "method": "paper_style_actor_ioc_mapping",
        "inputs": {
            "run_dir": str(run_dir),
            "mitre_actors_path": str(mitre_actors_path),
            "indicator_source": indicator_source,
        },
        "counts": {
            "completed_pulses": len(completed_pulses),
            "pulse_rows": sum(pulse_status.values()),
            "pulses_with_any_indicator": len(pulses_with_indicators),
            "indicator_rows": indicator_count,
            "ioc_attribution_rows": ioc_count,
            "normalized_actor_count": len(mapped_actor_ids),
            "mitre_alias_keys": len(actor_index),
        },
        "pulse_mapping_status": dict(sorted(pulse_status.items())),
        "indicator_type_raw": dict(sorted(indicator_type_raw.items())),
        "indicator_type_canonical": dict(sorted(indicator_type_canonical.items())),
        "top_unmapped_direct_actor_labels": unmapped_labels.most_common(50),
        "top_ambiguous_direct_actor_labels": ambiguous_labels.most_common(50),
        "comparison_notes": [
            "This is an OTX-only table, so cross-vendor Krippendorff alpha cannot be computed yet.",
            "Rows are ready to join with paper/vendor-style data by normalized indicator value, canonical type, actor id, and observation window.",
            "actor_country is null because MITRE actor seeds do not provide country the way MISP TAG does.",
        ],
    }


def _missing_pulse_row(pulse_id: str, discoveries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pulse_id": pulse_id,
        "pulse_name": None,
        "pulse_created": None,
        "pulse_modified": None,
        "source_actor_label_raw": None,
        "source_actor_labels": [],
        "source_actor_mappings": [],
        "tag_actor_candidates": [],
        "accepted_actor_ids": [],
        "mapping_status": "missing_raw",
        "direct_attribution_basis": "otx.adversary",
        "discovery_provenance": _compact_discoveries(discoveries),
        "collection_provenance_note": "Raw pulse detail file was not available.",
        "raw_ref": None,
    }


def _raw_ref(path: Path, raw_obj: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "source": raw_obj.get("source"),
        "source_id": raw_obj.get("source_id"),
        "fetched_at": raw_obj.get("fetched_at"),
    }


def _payload(raw_obj: Any) -> Any:
    if isinstance(raw_obj, Mapping) and isinstance(raw_obj.get("payload"), Mapping):
        return raw_obj["payload"]
    return raw_obj


def _split_actor_labels(raw_value: str) -> list[str]:
    if not raw_value:
        return []
    return sorted({part.strip() for part in _ACTOR_SPLIT_RE.split(raw_value) if part.strip()})


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _normalize_indicator_value(value: str, canonical_type: str | None) -> str:
    if canonical_type in {"domain", "email"}:
        return value.strip().casefold()
    return value.strip()


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({_text(item) for item in value if _text(item)})


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class _JsonlWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: Any = None

    def __enter__(self) -> _JsonlWriter:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.suffix == ".gz":
            self._fh = gzip.open(self.path, "wt", encoding="utf-8", newline="")
        else:
            self._fh = self.path.open("w", encoding="utf-8", newline="")
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._fh is not None:
            self._fh.close()

    def write(self, row: Mapping[str, Any]) -> None:
        if self._fh is None:
            raise RuntimeError("JSONL writer is not open")
        line = json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        line = line.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        self._fh.write(line)
        self._fh.write("\n")


def _optional_jsonl_writer(output_dir: Path, artifact: str | None) -> _JsonlWriter | _NullJsonlWriter:
    if artifact is None:
        return _NullJsonlWriter()
    return _JsonlWriter(output_dir / artifact)


class _NullJsonlWriter:
    def __enter__(self) -> _NullJsonlWriter:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def write(self, row: Mapping[str, Any]) -> None:
        return None
