"""JSONL utilities for intermediate dataset artifacts."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    """Write rows as canonical UTF-8 JSONL and return the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            line = json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            line = line.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            fh.write(line)
            fh.write("\n")
            count += 1
    return count
