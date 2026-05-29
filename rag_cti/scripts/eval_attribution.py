"""Evaluate retrieval on query_set_v2.jsonl with stable-identifier matching.

Usage:
    python scripts/eval_attribution.py
    python scripts/eval_attribution.py --collection cti_chunks_v2
    python scripts/eval_attribution.py --query-set data/eval/query_set_v2.jsonl
    python scripts/eval_attribution.py --config hybrid --k 1 --k 5 --k 10

Matching logic (no chunk_id dependency):
  - gold_attack_ids: chunk metadata.attack_id matches any gold ID
  - gold_pulse_id:   chunk metadata.pulse_id matches
  - gold_actor:      actor name appears in chunk content
  - gold_malware:    malware name appears in chunk content
  - gold_sources:    chunk source tag matches

Reports Hit@k, MRR, nDCG@k grouped by category.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti._logging import configure_logging, get_logger
from rag_cti.config import get_settings
from rag_cti.embeddings.embedder import Embedder
from rag_cti.generation.client import build_llm_client
from rag_cti.retrieval import build_pipeline
from rag_cti.retrieval.bm25 import BM25SparseEncoder
from rag_cti.store.qdrant_store import QdrantStore

logger = get_logger(__name__)

_VOCAB_PATH = Path(__file__).parent.parent / "data" / "sparse_vocab.json"


@dataclass(frozen=True)
class QueryRecord:
    query_id: str
    query: str
    category: str
    gold_attack_ids: list[str]
    gold_sources: list[str]
    gold_actor: str | None
    gold_pulse_ids: list[str]
    gold_malware: str | None
    notes: str


def _normalize_pulse_ids(raw: str | list | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    return [str(raw)] if raw else []


def load_query_set(path: Path) -> list[QueryRecord]:
    records: list[QueryRecord] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            records.append(QueryRecord(
                query_id=obj["query_id"],
                query=obj["query"],
                category=obj["category"],
                gold_attack_ids=obj.get("gold_attack_ids") or [],
                gold_sources=obj.get("gold_sources") or [],
                gold_actor=obj.get("gold_actor"),
                gold_pulse_ids=_normalize_pulse_ids(obj.get("gold_pulse_id")),
                gold_malware=obj.get("gold_malware"),
                notes=obj.get("notes", ""),
            ))
    return records


def _attack_id_match(chunk_id: str, gold_id: str) -> bool:
    c = chunk_id.upper()
    g = gold_id.upper()
    if c == g:
        return True
    if g.startswith(c + "."):
        return True
    if c.startswith(g + "."):
        return True
    return False


def is_hit(result: object, record: QueryRecord) -> bool:
    doc = result.document  # type: ignore[attr-defined]

    if record.gold_attack_ids:
        chunk_attack = doc.metadata.get("attack_id", "")
        if chunk_attack:
            for gid in record.gold_attack_ids:
                if _attack_id_match(str(chunk_attack), gid):
                    return True

    if record.gold_pulse_ids:
        chunk_pulse = doc.metadata.get("pulse_id", "")
        if chunk_pulse in record.gold_pulse_ids:
            return True

    if record.gold_actor:
        if record.gold_actor.lower() in doc.content.lower():
            return True

    if not record.gold_attack_ids and not record.gold_pulse_ids and not record.gold_actor and not record.gold_malware:
        if record.gold_sources and doc.source in record.gold_sources:
            return True

    return False


def hit_at_k(results: list, record: QueryRecord, k: int) -> bool:
    return any(is_hit(r, record) for r in results[:k])


def reciprocal_rank(results: list, record: QueryRecord) -> float:
    for rank, r in enumerate(results, start=1):
        if is_hit(r, record):
            return 1.0 / rank
    return 0.0


def ndcg_at_k(results: list, record: QueryRecord, k: int) -> float:
    dcg = sum(
        1.0 / math.log2(i + 1)
        for i, r in enumerate(results[:k], start=1)
        if is_hit(r, record)
    )
    idcg = 1.0 / math.log2(2)
    return round(dcg / idcg, 4) if idcg > 0 else 0.0


@dataclass
class CategoryMetrics:
    n: int = 0
    hits: dict[int, int] | None = None
    rr_sum: float = 0.0
    ndcg_sum: dict[int, float] | None = None

    def init_k(self, k_values: tuple[int, ...]) -> None:
        self.hits = dict.fromkeys(k_values, 0)
        self.ndcg_sum = dict.fromkeys(k_values, 0.0)

    def report(self, k_values: tuple[int, ...]) -> dict:
        n = self.n or 1
        return {
            "n": self.n,
            "hit_at_k": {k: round(self.hits[k] / n, 4) for k in k_values},
            "mrr": round(self.rr_sum / n, 4),
            "ndcg_at_k": {k: round(self.ndcg_sum[k] / n, 4) for k in k_values},
        }


def run_eval(
    records: list[QueryRecord],
    pipeline: object,
    k_values: tuple[int, ...],
    config_name: str,
) -> dict:
    max_k = max(k_values)
    cats: dict[str, CategoryMetrics] = defaultdict(CategoryMetrics)
    overall = CategoryMetrics()
    overall.init_k(k_values)

    per_query: list[dict] = []

    for i, rec in enumerate(records):
        results = pipeline.run(rec.query, top_k=max_k).results  # type: ignore[attr-defined]

        cat = rec.category
        if cats[cat].hits is None:
            cats[cat].init_k(k_values)
        cm = cats[cat]
        cm.n += 1
        overall.n += 1

        rr = reciprocal_rank(results, rec)
        cm.rr_sum += rr
        overall.rr_sum += rr

        q_hits: dict[int, bool] = {}
        for k in k_values:
            h = hit_at_k(results, rec, k)
            q_hits[k] = h
            if h:
                cm.hits[k] += 1
                overall.hits[k] += 1
            nd = ndcg_at_k(results, rec, k)
            cm.ndcg_sum[k] += nd
            overall.ndcg_sum[k] += nd

        per_query.append({
            "query_id": rec.query_id,
            "query": rec.query,
            "category": cat,
            "hit_at_k": {str(k): v for k, v in q_hits.items()},
            "rr": round(rr, 4),
            "target_rank": round(1.0 / rr) if rr > 0 else None,
        })

        if (i + 1) % 10 == 0:
            logger.info("eval progress", done=i + 1, total=len(records))

    return {
        "config": config_name,
        "k_values": list(k_values),
        "overall": overall.report(k_values),
        "by_category": {c: m.report(k_values) for c, m in sorted(cats.items())},
        "per_query": per_query,
    }


def print_report(result: dict, k_values: tuple[int, ...]) -> None:
    header = f"{'Category':<25}"
    for k in k_values:
        header += f"  Hit@{k:<3}"
    header += f"  {'MRR':>6}"
    for k in k_values:
        header += f"  nDCG@{k:<3}"
    header += f"  {'N':>4}"

    print(f"\n{'=' * len(header)}")
    print(f"Config: {result['config']}")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for cat_name in ["overall"] + sorted(result["by_category"].keys()):
        m = result["overall"] if cat_name == "overall" else result["by_category"].get(cat_name)
        if not m:
            continue
        row = f"{cat_name:<25}"
        for k in k_values:
            row += f"  {m['hit_at_k'][k]:>5.3f}"
        row += f"  {m['mrr']:>6.3f}"
        for k in k_values:
            row += f"  {m['ndcg_at_k'][k]:>7.3f}"
        row += f"  {m['n']:>4}"
        print(row)

    print("=" * len(header))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval with stable-identifier matching")
    parser.add_argument("--query-set", default="data/eval/query_set_v2.jsonl")
    parser.add_argument("--output", default="data/eval/attribution_results.json")
    parser.add_argument("--collection", default=None)
    parser.add_argument("--config", default="hybrid", help="dense | hybrid | hybrid+hyde | all")
    parser.add_argument("--k", type=int, action="append", default=None)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    configure_logging("INFO")
    k_values = tuple(sorted(set(args.k or [1, 5, 10])))
    configs = ["dense", "hybrid", "hybrid+hyde"] if args.config == "all" else [args.config]

    records = load_query_set(Path(args.query_set))
    cat_counts = defaultdict(int)
    for r in records:
        cat_counts[r.category] += 1
    print(f"Loaded {len(records)} queries: " + ", ".join(f"{c}={n}" for c, n in sorted(cat_counts.items())))

    settings = get_settings()
    coll = args.collection or settings.qdrant_collection
    store = QdrantStore(
        url=settings.qdrant_url,
        collection=coll,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )
    embedder = Embedder(model_name=settings.embedding_model, device=args.device)
    encoder = (
        BM25SparseEncoder.load(_VOCAB_PATH)
        if _VOCAB_PATH.exists()
        else BM25SparseEncoder()
    )
    llm_provider, llm_client = build_llm_client(settings)

    ALPHA_MAP = {"dense": 1.0, "hybrid": 0.5, "hybrid+hyde": 0.5}
    all_results: list[dict] = []

    for cfg in configs:
        print(f"\nRunning config: {cfg} ...")
        pipeline = build_pipeline(
            settings=settings,
            store=store,
            embedder=embedder,
            encoder=encoder,
            llm_client=llm_client if cfg == "hybrid+hyde" else None,
            llm_provider=llm_provider if cfg == "hybrid+hyde" else "anthropic",
            hybrid_alpha_override=ALPHA_MAP.get(cfg, 0.5),
        )
        result = run_eval(records, pipeline, k_values, cfg)
        all_results.append(result)
        print_report(result, k_values)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_set": args.query_set,
        "collection": coll,
        "results": all_results,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved -> {output_path}")


if __name__ == "__main__":
    main()
