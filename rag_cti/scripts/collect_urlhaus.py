#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_cti.connectors.abuse_export_collection import AbuseExportCollector

DEFAULT_ROOT = Path("data/raw/urlhaus")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "command",
        choices=(
            "collect",
            "payloads",
            "normalize-payloads",
            "clean-null-sentinels",
            "rebuild",
            "report",
            "validate",
            "blocked",
        ),
    )
    p.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--reuse-archive", type=Path)
    a = p.parse_args()
    c = AbuseExportCollector("urlhaus", a.root)
    result = (
        c.collect(reuse_archive=a.reuse_archive)
        if a.command == "collect"
        else c.download_urlhaus_payload_export()
        if a.command == "payloads"
        else c.normalize_urlhaus_payload_export()
        if a.command == "normalize-payloads"
        else c.clean_urlhaus_null_sentinels()
        if a.command == "clean-null-sentinels"
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
