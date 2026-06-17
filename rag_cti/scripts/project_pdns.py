"""Project append-only raw pDNS captures into processed JSONL chunks."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from typing import Any

from rag_cti.connectors.passive_dns import PassiveDNSConnector
from rag_cti.connectors.pdns_projection import load_pdns_raw_dir
from rag_cti.ingest.normalize import normalize_infrastructure
from rag_cti.preprocess.chunk_projection import project_chunk
from rag_cti.preprocess.normalizers import source_to_strategy
from rag_cti.preprocess.seeding import SeedStats, seed_connector_with_projection

DEFAULT_RAW_DIR = Path("data/raw/pdns")
DEFAULT_OUT = Path("data/processed/pdns.jsonl")


def _pdns_projection(raw: dict[str, Any]) -> dict[str, Any]:
    """Payload projection for one structured pDNS record: infra entity_ids + edges."""
    record = normalize_infrastructure(
        raw, "pdns", str(raw.get("domain", "")), indicator_type="domain"
    )
    return project_chunk(record, ontology_nodes=[])


def project_pdns(raw_dir: Path = DEFAULT_RAW_DIR, out_path: Path = DEFAULT_OUT) -> SeedStats:
    records = load_pdns_raw_dir(raw_dir)
    connector = PassiveDNSConnector(records=records)
    return seed_connector_with_projection(
        connector=connector,
        projector=_pdns_projection,
        out_path=out_path,
        strategy=source_to_strategy("pdns"),
        progress_every=100,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Project raw pDNS snapshots into processed JSONL")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    stats = project_pdns(raw_dir=args.raw_dir, out_path=args.out)
    print(stats.summary(args.out))


if __name__ == "__main__":
    main()
