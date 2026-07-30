"""Build the EviTRAIL five-file handoff for ORKL, MISP, APTnotes, and CISA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_cti.evitrail_delivery.source_handoff import (  # noqa: E402
    build_source_handoff,
)


def resolve_storage_path(path: Path, required_root: Path | None = None) -> Path:
    """Resolve a build path and optionally require it to stay under a storage root."""

    resolved = path.resolve()
    if required_root is None:
        return resolved

    storage_root = required_root.resolve()
    try:
        resolved.relative_to(storage_root)
    except ValueError as exc:
        raise ValueError(
            f"large handoff output/work must be under {storage_root}: {resolved}"
        ) from exc
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--processed-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--work-dir",
        type=Path,
        required=True,
        help="Fresh staging directory.",
    )
    parser.add_argument(
        "--required-storage-root",
        type=Path,
        help=(
            "Optional root that --output-dir and --work-dir must stay under; "
            "for example F:\\DATA_COLLECTION."
        ),
    )
    args = parser.parse_args()
    try:
        output_dir = resolve_storage_path(args.output_dir, args.required_storage_root)
        work_dir = resolve_storage_path(args.work_dir, args.required_storage_root)
    except ValueError as exc:
        parser.error(str(exc))
    result = build_source_handoff(
        raw_root=args.raw_root,
        processed_root=args.processed_root,
        output_dir=output_dir,
        work_dir=work_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
