"""Project append-only raw VirusTotal captures into processed JSONL chunks.

Replays the 473 already-fetched VT domain reports from the raw store (no new API
calls) into ``data/processed/vt.jsonl``, each chunk carrying the infra payload
projection (entity_ids + resolves-to / uses-nameserver edges).
"""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.connectors.virustotal import VirusTotalConnector
from rag_cti.connectors.vt_projection import load_vt_raw_payloads, project_vt_infra
from rag_cti.ingest.normalize import normalize_infrastructure
from rag_cti.preprocess.chunk_projection import project_chunk
from rag_cti.preprocess.normalizers import source_to_strategy
from rag_cti.preprocess.seeding import SeedStats, seed_connector_with_projection

DEFAULT_RAW_DIR = Path("data/raw/vt")
DEFAULT_OUT = Path("data/processed/vt.jsonl")


def _vt_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Payload projection for one raw VT response: infra entity_ids + edges."""
    structured = project_vt_infra(payload)
    record = normalize_infrastructure(
        structured, "vt", structured["domain"], indicator_type="domain"
    )
    return project_chunk(record, ontology_nodes=[])


def project_vt(raw_dir: Path = DEFAULT_RAW_DIR, out_path: Path = DEFAULT_OUT) -> SeedStats:
    payloads = load_vt_raw_payloads(raw_dir)
    connector = VirusTotalConnector(records=payloads)
    return seed_connector_with_projection(
        connector=connector,
        projector=_vt_projection,
        out_path=out_path,
        strategy=source_to_strategy("virustotal"),
        progress_every=100,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Project raw VT snapshots into processed JSONL")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    stats = project_vt(raw_dir=args.raw_dir, out_path=args.out)
    print(stats.summary(args.out))


if __name__ == "__main__":
    main()
