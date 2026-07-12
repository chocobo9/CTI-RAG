"""Collect and rebuild CISA Cybersecurity Advisories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_cti.connectors.cisa_collection import CisaCollector


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("enumerate", "collect", "rebuild", "validate", "report", "run")
    )
    parser.add_argument("--root", type=Path, default=Path("data/cisa"))
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--spool", type=Path, help="Browser capture responses.jsonl or its directory"
    )
    parser.add_argument("--rate-delay", type=float, default=0.25)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    collector = CisaCollector(
        args.root,
        spool=args.spool,
        rate_delay=args.rate_delay,
        retries=args.retries,
        timeout=args.timeout,
    )
    if args.command == "enumerate":
        result = {"entries": len(collector.enumerate(limit=args.limit))}
    elif args.command == "collect":
        result = collector.collect(limit=args.limit)
    elif args.command == "rebuild":
        result = collector.rebuild()
    elif args.command == "validate":
        result = collector.validate()
    elif args.command == "report":
        result = collector.report()
    else:
        collector.collect(limit=args.limit)
        collector.rebuild()
        validation = collector.validate()
        report = collector.report()
        result = {"validation": validation, "report": report}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if validation["valid"] and report["permanent_errors"] == 0 else 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
