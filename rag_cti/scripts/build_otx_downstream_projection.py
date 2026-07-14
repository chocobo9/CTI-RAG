"""Build OTX-only Neo4j-ready downstream projection artifacts.

This reads existing OTX raw material only and writes projection JSONL files.
It does not rewrite raw or intermediate artifacts.
"""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.intermediate.otx_downstream import build_otx_downstream_projection

DEFAULT_RAW_OTX_DIR = Path("data/raw/otx")
DEFAULT_RAW_PDNS_DIR = Path("data/raw/pdns")
DEFAULT_OUTPUT_DIR = Path("data/processed/otx_downstream_neo4j")
DEFAULT_MITRE_ATTACK_PATH = Path("data/raw/mitre/enterprise-attack.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-otx-dir", type=Path, default=DEFAULT_RAW_OTX_DIR)
    parser.add_argument(
        "--otx-run-dir",
        type=Path,
        default=None,
        help="OTX collection run directory containing checkpoint.json and saved_files.jsonl.",
    )
    parser.add_argument(
        "--checkpoint-path",
        type=Path,
        default=None,
        help="Optional checkpoint.json path; saved_files.jsonl is read from the checkpoint parent.",
    )
    parser.add_argument("--pdns-raw-dir", type=Path, default=DEFAULT_RAW_PDNS_DIR)
    parser.add_argument("--mitre-attack-path", type=Path, default=DEFAULT_MITRE_ATTACK_PATH)
    parser.add_argument(
        "--no-pdns",
        action="store_true",
        help="Skip local forward pDNS enrichment and emit OTX raw-only graph rows.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.otx_run_dir is not None and not args.otx_run_dir.is_dir():
        raise SystemExit(f"OTX run directory does not exist: {args.otx_run_dir}")
    if args.checkpoint_path is not None and not args.checkpoint_path.is_file():
        raise SystemExit(f"checkpoint path does not exist: {args.checkpoint_path}")
    if args.otx_run_dir is None and args.checkpoint_path is None and not args.raw_otx_dir.is_dir():
        raise SystemExit(f"raw OTX directory does not exist: {args.raw_otx_dir}")
    if args.output_dir.exists():
        if not args.overwrite:
            raise SystemExit(f"output directory exists; pass --overwrite: {args.output_dir}")
        _remove_output_dir(args.output_dir)

    pdns_raw_dir = None if args.no_pdns else args.pdns_raw_dir
    if pdns_raw_dir is not None and not pdns_raw_dir.is_dir():
        raise SystemExit(f"pDNS raw directory does not exist: {pdns_raw_dir}")

    result = build_otx_downstream_projection(
        args.raw_otx_dir,
        args.output_dir,
        pdns_raw_dir=pdns_raw_dir,
        mitre_attack_path=args.mitre_attack_path,
        otx_run_dir=args.otx_run_dir,
        checkpoint_path=args.checkpoint_path,
    )
    print(f"output_dir={result.output_dir}")
    print(f"events={result.event_count}")
    print(f"iocs={result.ioc_count}")
    print(f"edges={result.edge_count}")
    print(f"raw_observations={result.raw_observation_count}")
    print(f"raw_layouts={result.raw_layouts}")


def _remove_output_dir(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    processed_root = (Path.cwd() / "data" / "processed").resolve()
    if processed_root not in resolved.parents:
        raise SystemExit(f"refusing to delete output outside data/processed: {output_dir}")
    if not output_dir.name.startswith("otx_downstream_"):
        raise SystemExit(f"refusing to delete unexpected projection dir: {output_dir}")
    shutil.rmtree(output_dir)


if __name__ == "__main__":
    main()
