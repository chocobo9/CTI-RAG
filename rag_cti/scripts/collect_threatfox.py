#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_cti.connectors.abuse_export_collection import AbuseExportCollector


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("collect", "rebuild", "report", "validate", "blocked"))
    p.add_argument("--root", type=Path, default=Path("data/threatfox"))
    p.add_argument("--reuse-archive", type=Path)
    a = p.parse_args()
    c = AbuseExportCollector("threatfox", a.root)
    result = (
        c.collect(reuse_archive=a.reuse_archive)
        if a.command == "collect"
        else c.rebuild()
        if a.command == "rebuild"
        else c.report()
        if a.command == "report"
        else c.validate()
        if a.command == "validate"
        else c.mark_blocked()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
