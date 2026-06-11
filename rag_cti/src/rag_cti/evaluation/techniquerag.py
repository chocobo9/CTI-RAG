from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from rag_cti._logging import get_logger

logger = get_logger(__name__)

_TECHNIQUE_RE = re.compile(r"T\d{4}(?:\.\d{3})?")
_DEFAULT_CACHE = Path("data/eval/techniquerag_cache.jsonl")


@dataclass(frozen=True)
class TechniqueRAGRecord:
    text: str  # "input" column — the CTI passage used as the query
    gold_ids: list[str]  # technique IDs parsed from "output" column


def parse_gold_ids(output: str) -> list[str]:
    """Extract ATT&CK technique IDs from the dataset output column.

    Example input:
        "- T1012: Query Registry;\\n- T1218.010: System Binary Proxy Execution - Regsvr32;"
    Returns:
        ["T1012", "T1218.010"]
    """
    return _TECHNIQUE_RE.findall(output)


def load_techniquerag(
    dataset_id: str,
    split: str = "train",
    cache_path: Path = _DEFAULT_CACHE,
    max_records: int | None = None,
) -> list[TechniqueRAGRecord]:
    """Load TechniqueRAG records from cache or HuggingFace Hub.

    Column mapping:
        "instruction" -> ignored
        "input"       -> TechniqueRAGRecord.text
        "output"      -> parsed into TechniqueRAGRecord.gold_ids

    Records with no parseable technique IDs in the output are dropped.
    Results are written to cache_path on first successful HuggingFace load.
    """
    if cache_path.exists():
        logger.info("loading techniquerag from cache", path=str(cache_path))
        records = _load_cache(cache_path, max_records=max_records)
    else:
        logger.info(
            "downloading techniquerag from HuggingFace",
            dataset_id=dataset_id,
            split=split,
        )
        records = _load_from_hub(dataset_id, split)
        _save_cache(records, cache_path)
        logger.info("cached techniquerag dataset", path=str(cache_path), n=len(records))

    if max_records is not None:
        records = records[:max_records]

    logger.info("techniquerag dataset ready", n=len(records))
    return records


def _load_from_hub(dataset_id: str, split: str) -> list[TechniqueRAGRecord]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "The 'datasets' package is required. Install it with: pip install datasets"
        ) from exc

    # streaming=True processes only the requested split row-by-row, avoiding the
    # schema mismatch that occurs when download_and_prepare tries to cast all splits
    # to a single inferred schema (train=3 cols, test=5 cols in this dataset).
    ds = load_dataset(dataset_id, split=split, streaming=True)
    records: list[TechniqueRAGRecord] = []
    skipped = 0

    for row in ds:
        text = (row.get("input") or "").strip()
        output = row.get("output") or ""
        gold_ids = parse_gold_ids(output)

        if not text or not gold_ids:
            skipped += 1
            continue

        records.append(TechniqueRAGRecord(text=text, gold_ids=gold_ids))

    if skipped:
        logger.warning("skipped records with no parseable technique IDs", count=skipped)

    return records


def _save_cache(records: list[TechniqueRAGRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({"text": r.text, "gold_ids": r.gold_ids}) + "\n")


def _load_cache(path: Path, max_records: int | None = None) -> list[TechniqueRAGRecord]:
    limit = max_records if (max_records is not None and max_records > 0) else None
    records: list[TechniqueRAGRecord] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if limit is not None and len(records) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            records.append(TechniqueRAGRecord(text=obj["text"], gold_ids=obj["gold_ids"]))
    return records
