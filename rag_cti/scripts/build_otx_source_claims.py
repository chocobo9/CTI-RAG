"""Build offline OTX Event and source-attribution claim artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rag_cti.intermediate.otx_source_claims import (
    OTXSourceClaimNormalizer,
    build_otx_source_claim_artifacts,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--pulses", type=Path, help="Local JSON or JSONL Pulse details")
    inputs.add_argument("--run-dir", type=Path, help="OTX collection run directory")
    parser.add_argument("--mitre-taxonomy", type=Path, required=True, help="Local MITRE ATT&CK bundle")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _read_pulses(path: Path) -> list[Mapping[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        values = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        value = json.loads(text)
        values = value if isinstance(value, list) else [value]
    if not all(isinstance(value, Mapping) for value in values):
        raise ValueError("Pulse input must contain JSON objects")
    return values


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    args = _parse_args()
    if args.run_dir is not None:
        return _build_from_run(args.run_dir, args.mitre_taxonomy, args.output_dir)
    assert args.pulses is not None
    pulses = _read_pulses(args.pulses)
    raw_sha256 = hashlib.sha256(args.pulses.read_bytes()).hexdigest()
    provenance = {
        str(pulse.get("id")): {
            "raw_path": args.pulses.as_posix(),
            "raw_sha256": raw_sha256,
            "raw_layout": "jsonl" if args.pulses.suffix.lower() == ".jsonl" else "json",
        }
        for pulse in pulses
        if pulse.get("id")
    }
    artifacts = build_otx_source_claim_artifacts(
        pulses,
        args.mitre_taxonomy,
        raw_provenance_by_pulse_id=provenance,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "events.jsonl", artifacts.event_rows)
    _write_jsonl(args.output_dir / "source_attribution_claims.jsonl", artifacts.claim_rows)
    (args.output_dir / "summary.json").write_text(
        json.dumps(artifacts.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def _build_from_run(run_dir: Path, taxonomy_path: Path, output_dir: Path) -> int:
    completed = _completed_pulse_ids(run_dir)
    raw_paths = _pulse_detail_paths(run_dir, set(completed))
    missing = [pulse_id for pulse_id in completed if pulse_id not in raw_paths]
    if missing:
        raise ValueError(f"missing saved Pulse detail paths for {len(missing)} completed ids")

    normalizer = OTXSourceClaimNormalizer(taxonomy_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    claim_count = 0
    with (
        (output_dir / "events.jsonl").open("w", encoding="utf-8") as event_fh,
        (output_dir / "source_attribution_claims.jsonl").open("w", encoding="utf-8") as claim_fh,
    ):
        for pulse_id in completed:
            path = raw_paths[pulse_id]
            raw_bytes = path.read_bytes()
            raw = json.loads(raw_bytes.decode("utf-8"))
            pulse = raw.get("payload") if isinstance(raw, Mapping) else None
            if not isinstance(pulse, Mapping):
                raise ValueError(f"Pulse detail is not a RawStore wrapper: {path}")
            source_id = str(raw.get("source_id") or pulse.get("id") or "")
            if source_id != pulse_id:
                raise ValueError(f"Pulse id mismatch for {pulse_id}: {source_id}")
            event, claims = normalizer.normalize(
                pulse,
                raw_provenance={
                    "raw_path": path.as_posix(),
                    "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                    "raw_layout": "rawstore_wrapper.payload",
                    "fetched_at": raw.get("fetched_at"),
                },
            )
            event_fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            counts[event["actor_label_status"]] += 1
            for claim in claims:
                claim_fh.write(json.dumps(claim, ensure_ascii=False, sort_keys=True) + "\n")
            claim_count += len(claims)

    summary = {
        "input_mode": "collection_run",
        "run_dir": run_dir.as_posix(),
        "completed_pulse_count": len(completed),
        "event_count": len(completed),
        "claim_count": claim_count,
        "status_counts": dict(sorted(counts.items())),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def _completed_pulse_ids(run_dir: Path) -> list[str]:
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    values = checkpoint.get("completed_pulse_details", [])
    if not isinstance(values, list):
        raise ValueError("checkpoint.completed_pulse_details must be a list")
    return sorted({str(value) for value in values if value})


def _pulse_detail_paths(run_dir: Path, completed: set[str]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for line in (run_dir / "saved_files.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        pulse_id = str(row.get("pulse_id") or "") if isinstance(row, Mapping) else ""
        raw_ref = row.get("raw_ref") if isinstance(row, Mapping) else None
        if (
            row.get("kind") == "pulse_detail"
            and pulse_id in completed
            and isinstance(raw_ref, Mapping)
            and raw_ref.get("path")
        ):
            paths[pulse_id] = Path(str(raw_ref["path"]))
    return paths


if __name__ == "__main__":
    raise SystemExit(main())
