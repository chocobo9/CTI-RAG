"""Run retrieval evaluation over data/eval/query_set.jsonl.

Usage:
    python scripts/eval_query_set.py [--query-set data/eval/query_set.jsonl] \
        [--output data/eval/retrieval_results.json] \
        [--config dense|hybrid|hybrid+hyde|all] \
        [--k 1 --k 5 --k 10]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.config import get_settings
from rag_cti.embeddings.embedder import Embedder
from rag_cti.evaluation.query_set import load_query_set
from rag_cti.evaluation.retrieval_metrics import QuerySetEvalResult, evaluate_on_query_set
from rag_cti.generation.client import build_llm_client
from rag_cti.retrieval import build_pipeline
from rag_cti.retrieval.bm25 import BM25SparseEncoder
from rag_cti.store.qdrant_store import QdrantStore

_VOCAB_PATH = Path(__file__).parent.parent / "data" / "sparse_vocab.json"
_CATEGORIES = ("precise", "semantic", "fuzzy")


def _print_tables(results: list[QuerySetEvalResult], k_values: list[int]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        for cat in ("overall", *_CATEGORIES):
            t = Table(title=f"Retrieval Results — {cat.upper()}", show_lines=True)
            t.add_column("Config", style="cyan")
            for k in k_values:
                t.add_column(f"Hit@{k}", justify="right")
            t.add_column("MRR", justify="right")
            for k in k_values:
                t.add_column(f"nDCG@{k}", justify="right")
            t.add_column("N", justify="right")

            for r in results:
                metrics = r.overall if cat == "overall" else r.by_category.get(cat)
                if metrics is None:
                    continue
                row = [r.config]
                for k in k_values:
                    row.append(f"{metrics.top_k.get(k, 0.0):.4f}")
                row.append(f"{metrics.mrr:.4f}")
                for k in k_values:
                    row.append(f"{metrics.ndcg.get(k, 0.0):.4f}")
                row.append(str(metrics.n_queries))
                t.add_row(*row)

            console.print(t)

    except ImportError:
        for r in results:
            print(f"\n=== {r.config} ===")
            for cat in ("overall", *_CATEGORIES):
                m = r.overall if cat == "overall" else r.by_category.get(cat)
                if m is None:
                    continue
                print(f"  [{cat}] Hit@k={m.top_k}  MRR={m.mrr}  nDCG={m.ndcg}  N={m.n_queries}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retriever on custom query set")
    parser.add_argument("--query-set", default="data/eval/query_set.jsonl")
    parser.add_argument("--output", default="data/eval/retrieval_results.json")
    parser.add_argument("--config", default="all", help="dense | hybrid | hybrid+hyde | all")
    parser.add_argument("--k", type=int, action="append", default=None)
    parser.add_argument("--per-query-output", default=None, help="Path for per-query JSONL (e.g. data/eval/results_per_query.jsonl)")
    args = parser.parse_args()

    k_values = tuple(sorted(set(args.k or [1, 5, 10])))
    configs = ["dense", "hybrid", "hybrid+hyde"] if args.config == "all" else [args.config]
    query_set_path = Path(args.query_set)
    output_path = Path(args.output)

    print(f"Loading query set from {query_set_path} ...")
    records = load_query_set(query_set_path)
    cat_counts = {c: sum(1 for r in records if r.category.value == c) for c in _CATEGORIES}
    print(f"  {len(records)} records  " + "  ".join(f"{c}={cat_counts[c]}" for c in _CATEGORIES))

    settings = get_settings()
    store = QdrantStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )
    embedder = Embedder(model_name=settings.embedding_model)
    encoder = (
        BM25SparseEncoder.load(_VOCAB_PATH)
        if _VOCAB_PATH.exists()
        else BM25SparseEncoder()
    )

    llm_provider, llm_client = build_llm_client(settings)
    print(f"LLM provider: {llm_provider}")

    eval_results: list[QuerySetEvalResult] = []

    for cfg in configs:
        print(f"\nRunning config: {cfg} ...")
        use_hyde = cfg == "hybrid+hyde"
        pipeline = build_pipeline(
            settings=settings,
            store=store,
            embedder=embedder,
            encoder=encoder,
            llm_client=llm_client if use_hyde else None,
            llm_provider=llm_provider if use_hyde else "anthropic",
        )

        class _Retriever:
            def search(self, text: str, top_k: int) -> list:  # type: ignore[type-arg]
                return pipeline.run(text, top_k=top_k).results

        result = evaluate_on_query_set(
            retriever=_Retriever(),
            records=records,
            config=cfg,
            k_values=k_values,
        )
        eval_results.append(result)
        print(f"  done — MRR={result.overall.mrr:.4f}  Hit@10={result.overall.top_k.get(10, 0.0):.4f}")

    _print_tables(eval_results, list(k_values))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_set": str(query_set_path),
        "k_values": list(k_values),
        "results": [asdict(r) for r in eval_results],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nSaved → {output_path}")

    if args.per_query_output:
        pq_path = Path(args.per_query_output)
        pq_path.parent.mkdir(parents=True, exist_ok=True)
        with pq_path.open("w", encoding="utf-8") as f:
            for r in eval_results:
                for pq in r.per_query:
                    record = {
                        "config": r.config,
                        "query_id": pq.query_id,
                        "query_text": pq.query_text,
                        "category": pq.category,
                        "expected_doc_ids": pq.expected_doc_ids,
                        "retrieved_doc_ids": pq.retrieved_doc_ids,
                        "hit_at_k": {str(k): v for k, v in pq.hit_at_k.items()},
                        "reciprocal_rank": pq.reciprocal_rank,
                        "target_rank": pq.target_rank,
                    }
                    f.write(json.dumps(record) + "\n")
        print(f"Per-query results → {pq_path}")


if __name__ == "__main__":
    main()
