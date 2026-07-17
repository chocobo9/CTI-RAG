#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_cti.connectors.orkl_collection import OrklCollector

DEFAULT_ROOT = Path("data/raw/orkl")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("collect", "documents", "rebuild", "validate", "report", "finalize")
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--document-limit", type=int)
    parser.add_argument("--max-document-bytes", type=int)
    args = parser.parse_args()
    collector = OrklCollector(args.root)
    if args.command == "collect":
        result = collector.collect(max_reports=args.limit)
    elif args.command == "documents":
        result = collector.collect_documents(
            max_documents=args.document_limit,
            max_total_bytes=args.max_document_bytes,
        )
    elif args.command == "rebuild":
        result = collector.rebuild()
    elif args.command == "validate":
        result = collector.validate()
    elif args.command == "report":
        result = collector.report()
    else:
        result = {
            "rebuild": collector.rebuild(),
            "validation": collector.validate(),
            "report": collector.report(),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
