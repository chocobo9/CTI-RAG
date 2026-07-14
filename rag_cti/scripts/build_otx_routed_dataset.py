"""Build the final actor-evidenced OTX Event dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from rag_cti.intermediate.otx_routed_dataset import build_routed_otx_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routing-manifest", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--mitre-taxonomy", type=Path, required=True)
    parser.add_argument("--discovery-run-dir", type=Path, required=True)
    parser.add_argument("--detail-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build_routed_otx_dataset(
        routing_manifest=args.routing_manifest,
        raw_root=args.raw_root,
        mitre_taxonomy=args.mitre_taxonomy,
        discovery_run_dir=args.discovery_run_dir,
        detail_audit_path=args.detail_audit,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
