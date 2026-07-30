"""Build one shared EviTRAIL actor vocabulary across delivery shards/sources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_cti.evitrail_delivery.vocabulary import (
    build_global_vocabulary,
    write_global_vocabulary,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim-root", action="append", type=Path, required=True)
    parser.add_argument(
        "--claim-ref-root",
        type=Path,
        required=True,
        help="common delivery root used to write portable claim references",
    )
    parser.add_argument("--evitrail-root", type=Path, required=True)
    parser.add_argument("--initial-vocabulary", type=Path)
    parser.add_argument("--mitre", type=Path)
    parser.add_argument("--malpedia", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-events", type=int, default=5)
    parser.add_argument("--min-sources", type=int, default=2)
    parser.add_argument(
        "--consumer-revision",
        default="da4a29e8ce25cff8cbddebb444b069296f949511",
    )
    args = parser.parse_args()

    claim_paths = sorted(
        {
            path.resolve()
            for root in args.claim_root
            for path in (
                [root]
                if root.is_file() and root.name == "source_claims.jsonl"
                else root.rglob("source_claims.jsonl")
            )
        }
    )
    if not claim_paths:
        parser.error("no source_claims.jsonl files found under --claim-root")

    reference_root = args.claim_ref_root.resolve()
    try:
        claim_refs = [
            path.relative_to(reference_root).as_posix() for path in claim_paths
        ]
    except ValueError as exc:
        parser.error(f"claim file is outside --claim-ref-root: {exc}")

    initial_actors = _initial_actors(
        args.initial_vocabulary,
        args.evitrail_root,
    )
    result = build_global_vocabulary(
        claim_paths=claim_paths,
        evitrail_root=args.evitrail_root,
        initial_actors=initial_actors,
        mitre_path=args.mitre,
        malpedia_path=args.malpedia,
        min_events=args.min_events,
        min_sources=args.min_sources,
    )
    output = write_global_vocabulary(
        result=result,
        output_dir=args.output_dir,
        consumer_revision=args.consumer_revision,
        claim_refs=claim_refs,
        min_events=args.min_events,
        min_sources=args.min_sources,
    )
    print(
        json.dumps(
            {
                "output_dir": str(output),
                "claim_files": len(claim_paths),
                "actor_count": len(result["actors"]),
                "added_count": len(result["changes"]["added"]),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _initial_actors(path: Path | None, evitrail_root: Path) -> list[str]:
    if path is not None:
        row = json.loads(path.read_text(encoding="utf-8"))
        actors = row.get("actors") if isinstance(row, dict) else row
        if not isinstance(actors, list) or not all(
            isinstance(actor, str) for actor in actors
        ):
            raise ValueError("initial vocabulary must be a list or {'actors': [...]}")
        return actors

    root_text = str(evitrail_root.resolve())
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    from evitrail import config

    return list(config.APT_GROUPS)


if __name__ == "__main__":
    main()
