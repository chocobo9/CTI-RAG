from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from rag_cti._logging import get_logger

logger = get_logger(__name__)


class QueryCategory(StrEnum):
    PRECISE = "precise"
    SEMANTIC = "semantic"
    FUZZY = "fuzzy"


@dataclass(frozen=True)
class QuerySetRecord:
    query_id: str
    query: str
    category: QueryCategory
    expected_chunk_ids: list[str]  # seeded chunk IDs for precise/semantic; empty for fuzzy
    gold_attack_ids: list[str]  # ATT&CK technique IDs extracted from seed chunks
    gold_sources: list[str]  # acceptable source tags (for fuzzy hit evaluation)
    reference_answer: str | None  # human-readable GT for RAGAS context_recall; None for fuzzy
    notes: str


def load_query_set(path: Path) -> list[QuerySetRecord]:
    records: list[QuerySetRecord] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            records.append(
                QuerySetRecord(
                    query_id=obj["query_id"],
                    query=obj["query"],
                    category=QueryCategory(obj["category"]),
                    expected_chunk_ids=obj.get("expected_chunk_ids") or [],
                    gold_attack_ids=obj.get("gold_attack_ids") or [],
                    gold_sources=obj.get("gold_sources") or [],
                    reference_answer=obj.get("reference_answer"),
                    notes=obj.get("notes", ""),
                )
            )
    logger.info("query set loaded", path=str(path), n=len(records))
    return records


def save_query_set(records: list[QuerySetRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            obj = asdict(r)
            obj["category"] = r.category.value
            f.write(json.dumps(obj) + "\n")
    logger.info("query set saved", path=str(path), n=len(records))
