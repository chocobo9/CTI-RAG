"""Evaluate ATT&CK retrieval quality against the TechniqueRAG dataset.

Usage:
    python scripts/eval_techniquerag.py [--max-records N] [--k 1 5 10] [--config dense|hybrid|hybrid+hyde]

Outputs a results table comparing hit@k and MRR across retriever configurations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Allow running from the rag_cti/ project root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.config import get_settings
from rag_cti.embeddings.embedder import Embedder
from rag_cti.evaluation.retrieval_metrics import EvalResult, evaluate_retriever
from rag_cti.evaluation.techniquerag import load_techniquerag
from rag_cti.retrieval import build_pipeline
from rag_cti.retrieval.bm25 import BM25SparseEncoder
from rag_cti.store.qdrant_store import QdrantStore

_VOCAB_PATH = Path(__file__).parent.parent / "data" / "sparse_vocab.json"
_DATASET_ID = "QCRI/TechniqueRAG-Datasets"


class _PipelineRetriever:
    """Thin adapter: wraps Pipeline so evaluate_retriever can call .search()."""

    def __init__(self, pipeline: Any) -> None:
        self._pipeline = pipeline

    def search(self, text: str, top_k: int) -> list[Any]:
        result = self._pipeline.run(text, top_k=top_k)
        return result.results


def _build_store_and_embedder(settings: Any) -> tuple[QdrantStore, Embedder, BM25SparseEncoder]:
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
    return store, embedder, encoder


def _build_groq_client(settings: Any) -> Any | None:
    try:
        from groq import Groq  # type: ignore[import]
        api_key = settings.groq_api_key.get_secret_value()
        return Groq(api_key=api_key) if api_key else None
    except ImportError:
        return None


def _print_results(results: list[EvalResult]) -> None:
    k_values = results[0].k_values if results else []
    header_parts = ["Config".ljust(20)] + [f"Hit@{k}".rjust(8) for k in k_values] + ["MRR".rjust(8), "N".rjust(6)]
    sep = "-" * (20 + 8 * len(k_values) + 8 + 6 + 2 * (len(k_values) + 2))
    print()
    print("  ".join(header_parts))
    print(sep)
    for r in results:
        row = [r.config.ljust(20)]
        for k in k_values:
            row.append(f"{r.top_k.get(k, 0.0):.4f}".rjust(8))
        row.append(f"{r.mrr:.4f}".rjust(8))
        row.append(str(r.n_queries).rjust(6))
        print("  ".join(row))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ATT&CK retrieval on TechniqueRAG")
    parser.add_argument("--max-records", type=int, default=None, help="Limit dataset size for quick runs")
    parser.add_argument("--k", type=int, nargs="+", default=[1, 5, 10], help="k cutoffs for hit@k")
    parser.add_argument(
        "--config",
        choices=["dense", "hybrid", "hybrid+hyde", "all"],
        default="all",
        help="Retriever configuration to evaluate",
    )
    parser.add_argument("--dataset-id", default=_DATASET_ID, help="HuggingFace dataset ID")
    parser.add_argument("--split", default="train", help="Dataset split")
    parser.add_argument(
        "--cache",
        default="data/eval/techniquerag_cache.jsonl",
        help="Path to JSONL cache file",
    )
    args = parser.parse_args()

    k_values = tuple(sorted(set(args.k)))
    configs_to_run: list[str] = (
        ["dense", "hybrid", "hybrid+hyde"] if args.config == "all" else [args.config]
    )

    print(f"Loading TechniqueRAG dataset (split={args.split}, max={args.max_records or 'all'})...")
    dataset = load_techniquerag(
        dataset_id=args.dataset_id,
        split=args.split,
        cache_path=Path(args.cache),
        max_records=args.max_records,
    )
    print(f"  {len(dataset)} records loaded.")

    settings = get_settings()
    store, embedder, encoder = _build_store_and_embedder(settings)
    groq_client = _build_groq_client(settings)

    results: list[EvalResult] = []

    ALPHA_MAP = {"dense": 1.0, "hybrid": 0.5, "hybrid+hyde": 0.5}

    for config in configs_to_run:
        print(f"\nRunning config: {config}")
        use_hyde = config == "hybrid+hyde"
        alpha = ALPHA_MAP.get(config, 0.5)

        pipeline = build_pipeline(
            settings=settings,
            store=store,
            embedder=embedder,
            encoder=encoder,
            llm_client=groq_client if use_hyde else None,
            llm_provider="groq" if use_hyde and groq_client else "anthropic",
            hybrid_alpha_override=alpha,
        )

        retriever = _PipelineRetriever(pipeline)
        result = evaluate_retriever(
            retriever=retriever,
            dataset=dataset,
            config=config,
            k_values=k_values,
        )
        results.append(result)

    _print_results(results)


if __name__ == "__main__":
    main()
