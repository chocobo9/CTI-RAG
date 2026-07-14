"""Build offline Event-level OTX indicator summaries and a dataset manifest."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from rag_cti.intermediate.otx_indicator_summary import summarize_otx_pulse_indicators


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--pulses", type=Path, help="Local JSON or JSONL Pulse details")
    inputs.add_argument("--run-dir", type=Path, help="OTX collection run directory")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--coverage-start")
    parser.add_argument("--coverage-end")
    parser.add_argument("--selection-field", default="pulse.created")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "event_indicator_summaries.jsonl"
    mode = "collection_run" if args.run_dir is not None else "local_pulses"
    rows = _iter_run_pulses(args.run_dir) if args.run_dir is not None else _iter_local_pulses(args.pulses)
    event_count = 0
    with output_path.open("w", encoding="utf-8") as fh:
        for pulse, raw_record_bytes in rows:
            row = summarize_otx_pulse_indicators(pulse, raw_record_bytes=raw_record_bytes)
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            event_count += 1
    coverage_start, coverage_end, coverage_basis = _coverage(args)
    manifest = {
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "coverage_basis": coverage_basis,
        "coverage_status": "bounded" if coverage_start or coverage_end else "unbounded",
        "event_count": event_count,
        "input_mode": mode,
        "selection_field": args.selection_field,
    }
    (args.output_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def _coverage(args: argparse.Namespace) -> tuple[str | None, str | None, str]:
    if args.coverage_start is not None or args.coverage_end is not None:
        return args.coverage_start, args.coverage_end, "explicit_cli"
    if args.run_dir is None:
        return None, None, "not_declared"
    manifest_path = args.run_dir / "collection_manifest.json"
    if not manifest_path.exists():
        return None, None, "not_declared"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    params = manifest.get("params") if isinstance(manifest, Mapping) else None
    if not isinstance(params, Mapping):
        return None, None, "not_declared"
    return params.get("since"), params.get("until"), "collection_filter"


def _iter_local_pulses(path: Path | None) -> Iterator[tuple[Mapping[str, Any], int]]:
    assert path is not None
    if path.suffix.lower() == ".jsonl":
        with path.open("rb") as fh:
            for raw_line in fh:
                if not raw_line.strip():
                    continue
                value = json.loads(raw_line)
                if not isinstance(value, Mapping):
                    raise ValueError("Pulse input must contain JSON objects")
                yield value, len(raw_line)
        return
    raw_bytes = path.read_bytes()
    value = json.loads(raw_bytes)
    values = value if isinstance(value, list) else [value]
    for pulse in values:
        if not isinstance(pulse, Mapping):
            raise ValueError("Pulse input must contain JSON objects")
        yield pulse, len(json.dumps(pulse, ensure_ascii=False).encode("utf-8"))


def _iter_run_pulses(run_dir: Path | None) -> Iterator[tuple[Mapping[str, Any], int]]:
    assert run_dir is not None
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    completed_value = checkpoint.get("completed_pulse_details") if isinstance(checkpoint, Mapping) else None
    if not isinstance(completed_value, list):
        raise ValueError("checkpoint.completed_pulse_details must be a list")
    completed = sorted({str(value) for value in completed_value if value})
    paths: dict[str, Path] = {}
    with (run_dir / "saved_files.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping) or row.get("kind") != "pulse_detail":
                continue
            pulse_id = str(row.get("pulse_id") or "")
            raw_ref = row.get("raw_ref")
            if pulse_id in completed and isinstance(raw_ref, Mapping) and raw_ref.get("path"):
                paths[pulse_id] = Path(str(raw_ref["path"]))
    missing = [pulse_id for pulse_id in completed if pulse_id not in paths]
    if missing:
        raise ValueError(f"missing saved Pulse detail paths for {len(missing)} completed ids")
    for pulse_id in completed:
        raw_bytes = paths[pulse_id].read_bytes()
        wrapper = json.loads(raw_bytes)
        pulse = wrapper.get("payload") if isinstance(wrapper, Mapping) else None
        if not isinstance(pulse, Mapping):
            raise ValueError(f"Pulse detail is not a RawStore wrapper: {paths[pulse_id]}")
        source_id = str(wrapper.get("source_id") or pulse.get("id") or "")
        if source_id != pulse_id:
            raise ValueError(f"Pulse id mismatch for {pulse_id}: {source_id}")
        yield pulse, len(raw_bytes)


if __name__ == "__main__":
    raise SystemExit(main())
