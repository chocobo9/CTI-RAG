"""Normalize an OTX enrichment terminal ledger for EviTRAIL consumption."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.evitrail_delivery.enrichment import (  # noqa: E402
    DEFAULT_SNAPSHOT_PULSE_COUNT,
    normalize_otx_enrichment_ledger,
)


def validate_output_paths(output_path: Path, manifest_path: Path) -> None:
    """Keep generated data artifacts off the nearly-full project drive."""
    data_root = Path(r"F:\DATA_COLLECTION").resolve()
    for path in (output_path, manifest_path):
        try:
            path.resolve().relative_to(data_root)
        except ValueError:
            raise ValueError(
                f"large outputs must be under {data_root}: {path}"
            ) from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--evitrail-root",
        type=Path,
        help="path containing the evitrail package; enables exact reader validation",
    )
    parser.add_argument("--subset-pulse-count", type=int, default=4_505)
    parser.add_argument(
        "--task-id",
        action="append",
        default=None,
        help="normalize only these task IDs for a bounded smoke test; repeatable",
    )
    parser.add_argument(
        "--snapshot-pulse-count",
        type=int,
        default=DEFAULT_SNAPSHOT_PULSE_COUNT,
    )
    args = parser.parse_args()
    validate_output_paths(args.output, args.manifest)
    report = normalize_otx_enrichment_ledger(
        ledger_path=args.ledger,
        output_path=args.output,
        manifest_path=args.manifest,
        subset_pulse_count=args.subset_pulse_count,
        snapshot_pulse_count=args.snapshot_pulse_count,
        include_task_ids=set(args.task_id) if args.task_id else None,
        evitrail_root=args.evitrail_root,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
