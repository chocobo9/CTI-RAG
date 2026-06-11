"""JSONL checkpoint helpers shared by the OTX fetch scripts.

A checkpoint file holds one JSON record per processed item (keyed by
``pulse_id``) so a killed fetch can resume without re-hitting the API.
Malformed lines are skipped silently — a torn write from a crash must not
poison the resume.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_checkpoint(path: Path) -> dict[str, dict[str, Any]]:
    """Read a checkpoint JSONL into a dict keyed by ``pulse_id``.

    Returns an empty dict when the file does not exist. Later records for the
    same pulse_id win (append-only log semantics).
    """
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                records[rec["pulse_id"]] = rec
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    return records


def append_checkpoint(path: Path, record: dict[str, Any]) -> None:
    """Append one record to the checkpoint JSONL (creates parents as needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
