"""Freeze auditable TRAIL-style populations from an actor-seeded OTX run.

The module consumes collection ledgers, not search-page or Pulse payload text,
to reproduce the mechanical TRAIL discovery inversion. Query provenance is
never promoted to an OTX attribution claim.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PAPER_START = "2015-02-01T00:00:00+00:00"
PAPER_END = "2023-06-01T00:00:00+00:00"
EXTENDED_END = "2027-01-01T00:00:00+00:00"

OFFICIAL_TRAIL_LABELS = (
    "APT28",
    "TA511",
    "APT34",
    "APT35",
    "COBALT GROUP",
    "APT38",
    "MOLERATS",
    "TA551",
    "APT41",
    "FIN11",
    "GOLD WATERFALL",
    "FIN7",
    "TEAMTNT",
    "APT29",
    "APT27",
    "TURLA",
    "KIMSUKY",
    "MUSTANG PANDA",
    "APT37",
    "BLACKENERGY",
    "MAGECART",
    "MUDDYWATER",
)


@dataclass(frozen=True)
class _Detail:
    pulse_id: str
    created: str
    modified: str | None
    fetched_at: str | None
    indicator_count: int
    raw_path: Path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            yield value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _inside(value: str | None, start: str, end: str) -> bool:
    return value is not None and start <= value < end


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n"
            )
            count += 1
    return count


def _load_details(run_dir: Path) -> dict[str, _Detail]:
    result: dict[str, _Detail] = {}
    for row in _iter_jsonl(run_dir / "pulse_details.jsonl"):
        pulse_id = str(row.get("pulse_id") or "")
        raw_ref = row.get("raw_ref")
        raw_path = (
            Path(str(raw_ref.get("path")))
            if isinstance(raw_ref, Mapping) and raw_ref.get("path")
            else None
        )
        created = _timestamp(row.get("pulse_created"))
        if not pulse_id or raw_path is None or created is None:
            raise ValueError(f"invalid Pulse detail ledger row: {pulse_id!r}")
        if pulse_id in result:
            raise ValueError(f"duplicate Pulse detail ledger row: {pulse_id}")
        result[pulse_id] = _Detail(
            pulse_id=pulse_id,
            created=created,
            modified=_timestamp(row.get("pulse_modified")),
            fetched_at=_timestamp(row.get("fetched_at")),
            indicator_count=int(row.get("indicator_count") or 0),
            raw_path=raw_path,
        )
    return result


def _verify_wrapper(detail: _Detail) -> None:
    if not detail.raw_path.is_file():
        raise FileNotFoundError(detail.raw_path)
    wrapper = _load_json(detail.raw_path)
    payload = wrapper.get("payload") if isinstance(wrapper, Mapping) else None
    if not isinstance(payload, Mapping):
        raise ValueError(f"not an OTX RawStore wrapper: {detail.raw_path}")
    if str(wrapper.get("source_id") or "") != detail.pulse_id:
        raise ValueError(f"wrapper source_id mismatch: {detail.pulse_id}")
    if str(payload.get("id") or "") != detail.pulse_id:
        raise ValueError(f"payload id mismatch: {detail.pulse_id}")


def _actors(candidate: Mapping[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    provenance: list[dict[str, Any]] = []
    actor_values: set[str] = set()
    paths = candidate.get("discovery_paths")
    if not isinstance(paths, list):
        raise ValueError(f"candidate lacks discovery_paths: {candidate.get('pulse_id')}")
    for path in paths:
        if not isinstance(path, Mapping):
            continue
        actor = str(path.get("canonical_actor_from_frozen_map") or "").strip()
        if actor:
            actor_values.add(actor)
        provenance.append(
            {
                "alias": path.get("alias"),
                "canonical_actor": actor or None,
                "query_id": path.get("query_id"),
                "search_page": path.get("search_page"),
                "search_rank": path.get("search_rank"),
                "usage": "discovery_provenance_only",
            }
        )
    provenance.sort(
        key=lambda row: (
            str(row.get("canonical_actor")),
            str(row.get("alias")),
            str(row.get("query_id")),
            int(row.get("search_page") or 0),
            int(row.get("search_rank") or 0),
        )
    )
    return sorted(actor_values), provenance


def _year_month(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    parsed = datetime.fromisoformat(value)
    return f"{parsed.year:04d}", f"{parsed.year:04d}-{parsed.month:02d}"


def _label_rows(
    decisions: list[dict[str, Any]], population: str
) -> list[dict[str, Any]]:
    rows = []
    for row in decisions:
        if not row["populations"][population]:
            continue
        label = row["canonical_label"]
        rows.append(
            {
                "event_id": row["pulse_id"],
                "label": label,
                "class_id": OFFICIAL_TRAIL_LABELS.index(label),
                "pulse_created": row["pulse_created"],
                "raw_indicator_count": row["raw_indicator_count"],
                "raw_path": row["raw_path"],
            }
        )
    return sorted(rows, key=lambda row: row["event_id"])


def build_baseline_population(
    *,
    run_dir: Path,
    output_root: Path,
    expected_query_count: int = 2001,
    min_events: int = 25,
    verify_raw_wrappers: bool = False,
) -> dict[str, Any]:
    """Validate run ledgers and freeze paper/extended actor populations."""

    run_dir = run_dir.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"output root is not empty: {output_root}")
    acceptance_dir = output_root / "00_acceptance"
    population_dir = output_root / "01_population"

    selected = _load_json(run_dir / "selected_alias_queries.json")
    selected_rows = selected.get("queries") if isinstance(selected, Mapping) else None
    if not isinstance(selected_rows, list):
        raise ValueError("selected_alias_queries.queries must be a list")
    query_ids = {
        str(row.get("query_id"))
        for row in selected_rows
        if isinstance(row, Mapping) and row.get("queryable") is not False
    }
    if len(query_ids) != expected_query_count:
        raise ValueError(
            f"queryable alias count {len(query_ids)} != {expected_query_count}"
        )
    terminal_rows = list(_iter_jsonl(run_dir / "query_terminal_states.jsonl"))
    terminal_by_id = {str(row.get("query_id")): row for row in terminal_rows}
    if set(terminal_by_id) != query_ids:
        raise ValueError("terminal query ids do not exactly match selected queries")

    checkpoint = _load_json(run_dir / "checkpoint.json")
    completed_queries = {
        str(value) for value in checkpoint.get("completed_query_ids", [])
    }
    if completed_queries != query_ids:
        raise ValueError("checkpoint completed queries do not match selected queries")
    completed_details = {
        str(value) for value in checkpoint.get("completed_pulse_details", [])
    }
    details = _load_details(run_dir)
    if set(details) != completed_details:
        raise ValueError("Pulse detail ledger does not match checkpoint")
    if verify_raw_wrappers:
        for detail in details.values():
            _verify_wrapper(detail)
    elif any(not detail.raw_path.is_file() for detail in details.values()):
        raise FileNotFoundError("one or more Pulse raw paths do not exist")

    candidates_value = _load_json(run_dir / "candidates.json")
    if not isinstance(candidates_value, list):
        raise ValueError("candidates.json must contain a list")
    candidate_ids = [str(row.get("pulse_id") or "") for row in candidates_value]
    if not all(candidate_ids) or len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate Pulse ids must be non-empty and unique")
    inside_candidate_ids = {
        str(row.get("pulse_id"))
        for row in candidates_value
        if row.get("temporal_eligibility") == "inside_window"
    }
    if inside_candidate_ids != completed_details:
        raise ValueError("inside-window candidates do not match completed details")

    decisions: list[dict[str, Any]] = []
    strict_counts: dict[str, Counter[str]] = {
        "paper": Counter(),
        "extended": Counter(),
    }
    resolution_counts: Counter[str] = Counter()
    year_counts: Counter[str] = Counter()
    month_counts: Counter[str] = Counter()
    modified_after_paper = 0

    for candidate in sorted(candidates_value, key=lambda row: str(row["pulse_id"])):
        pulse_id = str(candidate["pulse_id"])
        detail = details.get(pulse_id)
        created = detail.created if detail else _timestamp(candidate.get("pulse_created"))
        modified = (
            detail.modified if detail else _timestamp(candidate.get("pulse_modified"))
        )
        actor_values, provenance = _actors(candidate)
        if len(actor_values) == 1:
            resolution = "single_actor"
            canonical_label = actor_values[0]
        elif len(actor_values) > 1:
            resolution = "cross_actor"
            canonical_label = None
        else:
            resolution = "unresolved_actor"
            canonical_label = None
        resolution_counts[resolution] += 1
        in_paper = _inside(created, PAPER_START, PAPER_END)
        in_extended = _inside(created, PAPER_START, EXTENDED_END)
        if resolution == "single_actor" and canonical_label is not None:
            if in_paper:
                strict_counts["paper"][canonical_label] += 1
            if in_extended:
                strict_counts["extended"][canonical_label] += 1
        year, month = _year_month(created)
        if year:
            year_counts[year] += 1
        if month:
            month_counts[month] += 1
        if in_paper and modified is not None and modified >= PAPER_END:
            modified_after_paper += 1
        decisions.append(
            {
                "pulse_id": pulse_id,
                "pulse_created": created,
                "pulse_modified": modified,
                "fetched_at": detail.fetched_at if detail else None,
                "raw_path": str(detail.raw_path) if detail else None,
                "raw_indicator_count": detail.indicator_count if detail else None,
                "temporal_eligibility": candidate.get("temporal_eligibility"),
                "canonical_actor_set": actor_values,
                "canonical_label": canonical_label,
                "resolution": resolution,
                "discovery_provenance": provenance,
                "review_flags": (
                    ["raw_indicator_count_gt_1000"]
                    if detail and detail.indicator_count > 1000
                    else []
                ),
                "populations": {
                    "raw_current_snapshot": detail is not None,
                    "paper_envelope_candidates": in_paper,
                    "paper_strict_single_actor": (
                        in_paper and resolution == "single_actor"
                    ),
                    "extended_strict_single_actor": (
                        in_extended and resolution == "single_actor"
                    ),
                },
            }
        )

    eligible = {
        scope: {
            actor
            for actor, count in counts.items()
            if count >= min_events
        }
        for scope, counts in strict_counts.items()
    }
    for row in decisions:
        label = row["canonical_label"]
        row["populations"]["paper_method_ge25"] = bool(
            row["populations"]["paper_strict_single_actor"]
            and label in eligible["paper"]
        )
        row["populations"]["paper_model_22"] = bool(
            row["populations"]["paper_method_ge25"]
            and label in OFFICIAL_TRAIL_LABELS
        )
        row["populations"]["extended_method_ge25"] = bool(
            row["populations"]["extended_strict_single_actor"]
            and label in eligible["extended"]
        )
        row["populations"]["extended_model_22"] = bool(
            row["populations"]["extended_method_ge25"]
            and label in OFFICIAL_TRAIL_LABELS
        )

    population_counts = Counter()
    for row in decisions:
        for name, member in row["populations"].items():
            if member:
                population_counts[name] += 1

    _write_jsonl(population_dir / "event_decisions.jsonl", decisions)
    _write_jsonl(
        population_dir / "cross_actor_events.jsonl",
        (row for row in decisions if row["resolution"] == "cross_actor"),
    )
    _write_jsonl(
        population_dir / "large_event_review.jsonl",
        (row for row in decisions if row["review_flags"]),
    )
    for population in ("paper_model_22", "extended_model_22"):
        _write_jsonl(
            population_dir / f"{population}_labels.jsonl",
            _label_rows(decisions, population),
        )

    actor_report = {
        "min_events": min_events,
        "official_label_order": list(OFFICIAL_TRAIL_LABELS),
        "paper": {
            "strict_event_counts": dict(sorted(strict_counts["paper"].items())),
            "ge_minimum_actors": sorted(eligible["paper"]),
            "official_22_counts": {
                actor: strict_counts["paper"].get(actor, 0)
                for actor in OFFICIAL_TRAIL_LABELS
            },
        },
        "extended": {
            "strict_event_counts": dict(sorted(strict_counts["extended"].items())),
            "ge_minimum_actors": sorted(eligible["extended"]),
            "official_22_counts": {
                actor: strict_counts["extended"].get(actor, 0)
                for actor in OFFICIAL_TRAIL_LABELS
            },
        },
    }
    _write_json(population_dir / "actor_selection_report.json", actor_report)

    capped_queries = [
        {
            "query_id": query_id,
            "reported_total_count": row.get("reported_total_count"),
            "result_rows_collected": row.get("result_rows_collected"),
        }
        for query_id, row in sorted(terminal_by_id.items())
        if int(row.get("result_rows_collected") or 0) >= 1000
        or int(row.get("reported_total_count") or 0) > 1000
    ]
    temporal_report = {
        "paper_window": {"start_inclusive": PAPER_START, "end_exclusive": PAPER_END},
        "extended_window": {
            "start_inclusive": PAPER_START,
            "end_exclusive": EXTENDED_END,
        },
        "candidate_min_created": min(
            row["pulse_created"] for row in decisions if row["pulse_created"]
        ),
        "candidate_max_created": max(
            row["pulse_created"] for row in decisions if row["pulse_created"]
        ),
        "counts_by_year": dict(sorted(year_counts.items())),
        "counts_by_month": dict(sorted(month_counts.items())),
        "paper_created_but_modified_after_window": modified_after_paper,
        "queries_reaching_or_exceeding_1000_row_cap": capped_queries,
        "population_counts": dict(sorted(population_counts.items())),
    }
    _write_json(acceptance_dir / "temporal_acceptance_report.json", temporal_report)

    input_names = (
        "selected_alias_queries.json",
        "quarantined_alias_queries.json",
        "query_terminal_states.jsonl",
        "candidates.json",
        "checkpoint.json",
        "pulse_details.jsonl",
        "collection_manifest.json",
        "collection_summary.json",
    )
    input_hashes = {
        name: _sha256(run_dir / name)
        for name in input_names
        if (run_dir / name).is_file()
    }
    result = {
        "contract": "trail_otx_baseline_population_v1",
        "status": "passed",
        "run_dir": str(run_dir),
        "expected_query_count": expected_query_count,
        "query_count": len(query_ids),
        "candidate_count": len(decisions),
        "completed_detail_count": len(details),
        "raw_wrapper_verification": (
            "parsed_all_wrappers"
            if verify_raw_wrappers
            else "file_existence_only_inventory_validation_required"
        ),
        "resolution_counts": dict(sorted(resolution_counts.items())),
        "population_counts": dict(sorted(population_counts.items())),
        "failed_request_records": len(checkpoint.get("failed_requests", [])),
        "input_hashes": input_hashes,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    _write_json(acceptance_dir / "raw_acceptance_report.json", result)
    _write_json(
        output_root / "run_manifest.json",
        {
            **result,
            "official_label_order": list(OFFICIAL_TRAIL_LABELS),
            "outputs": {
                "raw_acceptance": "00_acceptance/raw_acceptance_report.json",
                "temporal_acceptance": "00_acceptance/temporal_acceptance_report.json",
                "event_decisions": "01_population/event_decisions.jsonl",
                "actor_selection": "01_population/actor_selection_report.json",
                "paper_labels": "01_population/paper_model_22_labels.jsonl",
                "extended_labels": "01_population/extended_model_22_labels.jsonl",
            },
        },
    )
    return result
