#!/usr/bin/env python3
"""Collect and preserve the pinned APTnotes report corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rag_cti.connectors.aptnotes_collection import AptnotesCollector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "snapshot", "collect", "rebuild", "validate", "report", "finalize"))
    parser.add_argument("--root", type=Path, default=Path("data/aptnotes"))
    parser.add_argument("--source-repo", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--indices", help="comma-separated zero-based source row indices")
    parser.add_argument("--rate-delay", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--max-bytes", type=int, default=200 * 1024 * 1024)
    args = parser.parse_args()
    collector = AptnotesCollector(
        args.root,
        rate_delay=args.rate_delay,
        timeout=args.timeout,
        attempts=args.attempts,
        max_bytes=args.max_bytes,
    )
    indices = {int(value) for value in args.indices.split(",")} if args.indices else None
    result: dict[str, Any]
    if args.command == "snapshot":
        result = collector.snapshot(args.source_repo)
    elif args.command == "inspect":
        result = collector.inspect()
    elif args.command == "collect":
        result = collector.collect(indices=indices, limit=args.limit)
    elif args.command == "rebuild":
        result = collector.rebuild()
    elif args.command == "validate":
        result = collector.validate()
    elif args.command == "report":
        result = collector.report()
    else:
        result = collector.finalize()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    validation = result.get("validation")
    valid = validation.get("valid", True) if isinstance(validation, dict) else result.get("valid", True)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
