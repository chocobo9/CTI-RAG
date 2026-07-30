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


def require_data_collection_path(path: Path) -> Path:
    """Resolve a large-build path and require the designated F: data root."""

    resolved = path.resolve()
    collection_root = Path(r"F:\DATA_COLLECTION").resolve()
    try:
        resolved.relative_to(collection_root)
    except ValueError as exc:
        raise ValueError(
            f"large handoff output/work must be under {collection_root}: {resolved}"
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
        help="Fresh staging directory; place large runs under F:\\DATA_COLLECTION.",
    )
    args = parser.parse_args()
    try:
        output_dir = require_data_collection_path(args.output_dir)
        work_dir = require_data_collection_path(args.work_dir)
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
