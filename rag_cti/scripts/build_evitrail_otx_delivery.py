"""Build deterministic EviTRAIL OTX shards from immutable raw wrappers."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_cti.evitrail_delivery.otx import build_otx_delivery


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--required-output-root",
        type=Path,
        help=(
            "optional safety guard requiring --output-dir to remain under "
            "this storage root"
        ),
    )
    parser.add_argument("--discovery-evidence", type=Path)
    parser.add_argument("--mitre-attack", type=Path)
    parser.add_argument(
        "--event-id-file",
        type=Path,
        help=(
            "optional allowlist with one raw Pulse ID or event:otx:<id> "
            "per line"
        ),
    )
    parser.add_argument("--events-per-shard", type=int, default=1000)
    parser.add_argument(
        "--max-indicator-occurrences-per-shard",
        type=int,
        default=250_000,
    )
    parser.add_argument(
        "--expected-event-count",
        type=int,
        help=(
            "fail the build unless the selected latest-wrapper population "
            "has exactly this many Events"
        ),
    )
    args = parser.parse_args()

    output = args.output_dir.resolve()
    if args.required_output_root is not None:
        required_root = args.required_output_root.resolve()
        try:
            output.relative_to(required_root)
        except ValueError:
            raise SystemExit(
                f"--output-dir must be under {required_root}; got {output}"
            ) from None

    result = build_otx_delivery(
        args.raw_root,
        output,
        discovery_evidence=args.discovery_evidence,
        mitre_attack_path=args.mitre_attack,
        events_per_shard=args.events_per_shard,
        max_indicator_occurrences_per_shard=(
            args.max_indicator_occurrences_per_shard
        ),
        expected_event_count=args.expected_event_count,
        include_source_ids=(
            args.event_id_file.read_text(encoding="utf-8").splitlines()
            if args.event_id_file is not None
            else None
        ),
    )
    payload = asdict(result)
    payload["output_dir"] = str(result.output_dir)
    payload["handoff_dirs"] = [str(path) for path in result.handoff_dirs]
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
