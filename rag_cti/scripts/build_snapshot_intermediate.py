"""Build the read-only Stage 1 package from the current local CTI snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path

from rag_cti.intermediate.snapshot import build_snapshot_intermediate_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-id", default="cti_rag_snapshot_reverse_enrichment")
    parser.add_argument("--dataset-version", default="2026-07-12-v1")
    parser.add_argument("--generated-at")
    parser.add_argument("--temporal-cutoff", help="ISO timestamp; records before it are train, others test")
    args = parser.parse_args()
    result = build_snapshot_intermediate_package(
        repository_root=args.repository_root,
        output_dir=args.output_dir,
        dataset_id=args.dataset_id,
        dataset_version=args.dataset_version,
        generated_at=args.generated_at,
        temporal_cutoff=args.temporal_cutoff,
    )
    print(result.output_dir)
    for key, value in sorted(result.counts.items()):
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
