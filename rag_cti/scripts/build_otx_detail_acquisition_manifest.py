"""Build an offline, actor-evidence-driven OTX Pulse detail acquisition manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_cti.intermediate.otx_detail_acquisition import build_detail_acquisition_artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--mitre-taxonomy", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    artifacts = build_detail_acquisition_artifacts(
        args.candidate_manifest, args.mitre_taxonomy, args.raw_root
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "detail_acquisition_manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as handle:
        for row in artifacts.rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        **artifacts.summary,
        "candidate_manifest": args.candidate_manifest.as_posix(),
        "mitre_taxonomy": args.mitre_taxonomy.as_posix(),
        "raw_root": args.raw_root.as_posix(),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
