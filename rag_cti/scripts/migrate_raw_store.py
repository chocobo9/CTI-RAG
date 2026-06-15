"""Migrate the legacy flat raw stores into the versioned RawStore layout.

Legacy: data/raw/otx/{pulse_id}.json, data/raw/mitre/enterprise-attack.json.
Versioned: data/raw/{source}/{source_id}/{fetched_at}.json (RawStore).

Each legacy file is **copied** in (via RawStore.write) as a version keyed by the
file's mtime — originals are left untouched, so the migration is reversible and
idempotent (re-running writes the same content => no-op). Run before the
RawStore-backed builders (build_indicator_index.py, the reconciled rebuilds).
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.store.raw_store import RawStore


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def migrate_otx(store: RawStore, raw_dir: Path) -> tuple[int, int]:
    written = skipped = 0
    for fp in sorted(raw_dir.glob("*.json")):
        try:
            payload = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            skipped += 1
            continue
        source_id = str(payload.get("id") or fp.stem)
        store.write("otx", source_id, payload, _mtime_iso(fp))
        written += 1
    return written, skipped


def migrate_mitre(store: RawStore, bundle: Path) -> int:
    if not bundle.exists():
        return 0
    payload = json.loads(bundle.read_text(encoding="utf-8"))
    store.write("mitre", "enterprise-attack", payload, _mtime_iso(bundle))
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate flat raw stores into versioned RawStore")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--sources", nargs="+", default=["otx", "mitre"])
    args = parser.parse_args()

    store = RawStore(args.raw_root)
    if "otx" in args.sources:
        w, s = migrate_otx(store, args.raw_root / "otx")
        print(f"otx: {w} pulses migrated, {s} skipped")
    if "mitre" in args.sources:
        n = migrate_mitre(store, args.raw_root / "mitre" / "enterprise-attack.json")
        print(f"mitre: {n} bundle migrated")
    print("✓ migration complete (originals left in place; idempotent)")


if __name__ == "__main__":
    main()
