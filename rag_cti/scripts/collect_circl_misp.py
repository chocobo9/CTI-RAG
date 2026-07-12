#!/usr/bin/env python3
"""Collect and rebuild the public CIRCL MISP OSINT feed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rag_cti.connectors.circl_misp_collection import CirclMispCollector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "collect", "rebuild", "validate", "report", "finalize"))
    parser.add_argument("--root", type=Path, default=Path("data/raw/circl_misp"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--rate-delay", type=float, default=0.08)
    args = parser.parse_args()
    collector = CirclMispCollector(args.root, rate_delay=args.rate_delay)
    result: dict[str, Any]
    if args.command == "inspect":
        result = {"entries": len(collector.enumerate_feed())}
    elif args.command == "collect":
        checkpoint = collector.collect(limit=args.limit)
        statuses: dict[str, int] = {}
        for state in checkpoint["entries"].values():
            status = state["status"]
            statuses[status] = statuses.get(status, 0) + 1
        result = {"entries": len(checkpoint["entries"]), "statuses": statuses, "completed_at": checkpoint.get("completed_at")}
    elif args.command == "rebuild":
        result = collector.rebuild()
    elif args.command == "validate":
        result = collector.validate()
    elif args.command == "report":
        result = collector.report()
    else:
        result = {
            "rebuild": collector.rebuild(),
            "validate": collector.validate(),
            "report": collector.report(),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not isinstance(result, dict) or result.get("valid", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
