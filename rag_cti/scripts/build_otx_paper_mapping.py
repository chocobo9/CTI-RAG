"""Build OTX paper-style actor/IOC mapping artifacts from local raw data."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.intermediate.otx_paper_mapping import build_otx_paper_mapping

DEFAULT_RUN_DIR = Path("data/raw/otx_collection_runs/routeA_20260704_policy_small_first")
DEFAULT_MITRE_ACTORS = Path("docs/reference/seeds/mitre_actors.json")
DEFAULT_OUTPUT_DIR = Path("data/processed/otx_paper_mapping")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--mitre-actors", type=Path, default=DEFAULT_MITRE_ACTORS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--indicator-source",
        choices=["detail"],
        default="detail",
        help="Use embedded pulse-detail indicators. Endpoint-preferred can be added later.",
    )
    parser.add_argument(
        "--no-gzip-large-outputs",
        action="store_false",
        dest="gzip_large_outputs",
        help="Write large JSONL artifacts uncompressed. Default is gzip.",
    )
    parser.add_argument(
        "--emit-indicators-flat",
        action="store_true",
        help="Also write the all-pulse flat indicator table. Large and slower; default is off.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print progress every N pulses. Use 0 to disable.",
    )
    parser.set_defaults(gzip_large_outputs=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not args.run_dir.is_dir():
        raise SystemExit(f"run directory does not exist: {args.run_dir}")
    if not args.mitre_actors.is_file():
        raise SystemExit(f"MITRE actor seed does not exist: {args.mitre_actors}")
    if args.output_dir.exists():
        if not args.overwrite:
            raise SystemExit(f"output directory exists; pass --overwrite: {args.output_dir}")
        _remove_output_dir(args.output_dir)

    result = build_otx_paper_mapping(
        args.run_dir,
        args.output_dir,
        mitre_actors_path=args.mitre_actors,
        indicator_source=args.indicator_source,
        compress_large_outputs=args.gzip_large_outputs,
        emit_indicator_flat=args.emit_indicators_flat,
        progress_every=args.progress_every,
    )
    print(f"output_dir={result.output_dir}")
    print(f"completed_pulses={result.completed_pulses}")
    print(f"pulses_read={result.pulses_read}")
    print(f"pulse_actor_rows={result.pulse_actor_rows}")
    print(f"indicator_rows={result.indicator_rows}")
    print(f"ioc_attribution_rows={result.ioc_attribution_rows}")


def _remove_output_dir(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    processed_root = (Path.cwd() / "data" / "processed").resolve()
    if processed_root not in resolved.parents and resolved != processed_root:
        raise SystemExit(f"refusing to delete output outside data/processed: {output_dir}")
    if not output_dir.name.startswith("otx_paper_mapping"):
        raise SystemExit(f"refusing to delete unexpected mapping dir: {output_dir}")
    shutil.rmtree(output_dir)


if __name__ == "__main__":
    main()
