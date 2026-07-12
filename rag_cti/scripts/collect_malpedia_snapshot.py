"""Collect and rebuild the public Malpedia metadata snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_cti.connectors.malpedia_collection import MalpediaCollector


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("collect", "rebuild", "validate", "report", "run"))
    parser.add_argument("--root", type=Path, default=Path("data/malpedia"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--rate-delay", type=float, default=0.15)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    collector = MalpediaCollector(
        args.root, rate_delay=args.rate_delay, retries=args.retries, timeout=args.timeout
    )
    if args.command == "collect":
        result = collector.collect(limit=args.limit)
    elif args.command == "rebuild":
        result = collector.rebuild()
    elif args.command == "validate":
        result = collector.validate()
    elif args.command == "report":
        result = collector.report()
    else:
        state = collector.collect(limit=args.limit)
        collector.rebuild()
        validation = collector.validate()
        report = collector.report()
        terminal = all(
            x.get("status") in {"success", "unchanged", "permanent_failure"}
            for x in state["endpoints"].values()
        )
        result = {"validation": validation, "report": report}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if validation["valid"] and terminal and report["permanent_failures"] == 0 else 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
