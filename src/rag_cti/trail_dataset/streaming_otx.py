"""Compatibility entry points for the five-node OTX projection.

The new actor-seeded TRAIL workflow uses :mod:`otx_variant_graph`, whose
SQLite-backed implementation freezes population and enrichment variants.
These functions preserve the older raw-root command interface.
"""

from __future__ import annotations

import json
from pathlib import Path

from rag_cti.trail_dataset.builder import (
    BuildPolicy,
    DatasetManifest,
    SourceRoots,
    build_dataset,
)


def build_otx_streaming(otx_root: Path, output_dir: Path) -> DatasetManifest:
    result = build_dataset(
        SourceRoots(otx=Path(otx_root)),
        Path(output_dir),
        BuildPolicy(),
    )
    manifest_path = Path(output_dir) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("input_policy", {})["streaming"] = True
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def build_otx_route_a_streaming(
    route_a_events: Path, output_dir: Path
) -> DatasetManifest:
    """Build from the raw-root recorded by a Route-A event manifest.

    The accepted manifest is a JSON object containing ``otx_root``. Ambiguous
    JSONL layouts fail closed instead of being silently reinterpreted.
    """

    value = json.loads(Path(route_a_events).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value.get("otx_root"):
        raise ValueError("Route-A manifest must contain an explicit otx_root")
    return build_otx_streaming(Path(str(value["otx_root"])), output_dir)
