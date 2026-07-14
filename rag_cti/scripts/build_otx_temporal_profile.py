"""Build a descriptive temporal profile for completed OTX Pulse details."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from rag_cti.intermediate.otx_temporal_profile import build_otx_temporal_profile


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--run-dir", type=Path)
    inputs.add_argument("--pulses", type=Path, help="Small local JSON or JSONL fixture")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.run_dir is not None:
        since, until = _time_filter(args.run_dir)
        rows = _iter_completed_pulses(args.run_dir)
    else:
        since, until = None, None
        rows = _iter_local_pulses(args.pulses)
    profile = build_otx_temporal_profile(rows, since=since, until=until)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "dataset_temporal_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def _time_filter(run_dir: Path) -> tuple[str | None, str | None]:
    manifest = json.loads((run_dir / "collection_manifest.json").read_text(encoding="utf-8"))
    params = manifest.get("params") if isinstance(manifest, Mapping) else None
    if not isinstance(params, Mapping):
        return None, None
    since = params.get("since")
    until = params.get("until")
    return _optional_text(since), _optional_text(until)


def _iter_completed_pulses(
    run_dir: Path,
) -> Iterator[tuple[Mapping[str, Any], str | None]]:
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    completed_value = checkpoint.get("completed_pulse_details") if isinstance(checkpoint, Mapping) else None
    if not isinstance(completed_value, list):
        raise ValueError("checkpoint.completed_pulse_details must be a list")
    completed = sorted({_optional_text(value) for value in completed_value} - {None})
    refs: dict[str, Mapping[str, Any]] = {}
    with (run_dir / "saved_files.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping) or row.get("kind") not in {
                "pulse_detail",
                "pulse_detail_reused",
            }:
                continue
            pulse_id = _optional_text(row.get("pulse_id"))
            raw_ref = row.get("raw_ref")
            if pulse_id in completed and isinstance(raw_ref, Mapping) and raw_ref.get("path"):
                refs[pulse_id] = raw_ref
    missing = [pulse_id for pulse_id in completed if pulse_id not in refs]
    if missing:
        raise ValueError(f"missing saved Pulse detail paths for {len(missing)} completed ids")
    for pulse_id in completed:
        raw_ref = refs[pulse_id]
        path = _resolve_raw_path(run_dir, raw_ref["path"])
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        pulse = wrapper.get("payload") if isinstance(wrapper, Mapping) else None
        if not isinstance(pulse, Mapping):
            raise ValueError(f"Pulse detail is not a RawStore wrapper: {path}")
        source_id = _optional_text(wrapper.get("source_id")) or _optional_text(pulse.get("id"))
        if source_id != pulse_id:
            raise ValueError(f"Pulse id mismatch for {pulse_id}: {source_id}")
        fetched_at = _optional_text(wrapper.get("fetched_at")) or _optional_text(raw_ref.get("fetched_at"))
        yield pulse, fetched_at


def _iter_local_pulses(path: Path | None) -> Iterator[tuple[Mapping[str, Any], None]]:
    assert path is not None
    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                pulse = json.loads(line)
                if not isinstance(pulse, Mapping):
                    raise ValueError("Pulse input must contain JSON objects")
                yield pulse, None
        return
    value = json.loads(path.read_text(encoding="utf-8"))
    pulses = value if isinstance(value, list) else [value]
    for pulse in pulses:
        if not isinstance(pulse, Mapping):
            raise ValueError("Pulse input must contain JSON objects")
        yield pulse, None


def _optional_text(value: Any) -> str | None:
    text = value.strip() if isinstance(value, str) else ""
    return text or None


def _resolve_raw_path(run_dir: Path, value: Any) -> Path:
    path = Path(str(value))
    if path.exists():
        return path
    run_relative = run_dir / path
    if not path.is_absolute() and run_relative.exists():
        return run_relative
    raise FileNotFoundError(
        f"Pulse detail raw path does not exist: {path} (also tried {run_relative})"
    )


if __name__ == "__main__":
    raise SystemExit(main())
