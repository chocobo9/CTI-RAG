"""Evaluate candidate embedding models on the local CTI corpus.

Usage:
    python scripts/embedding_bakeoff.py [--sample-size 200] [--n-queries 20]
                                        [--models MODEL1 MODEL2 ...]

Pipeline:
  1. Sample N chunks from data/processed/mitre.jsonl + otx.jsonl as the corpus.
  2. For the first M chunks, use Groq (preferred) or Claude to generate a
     realistic CTI retrieval query whose gold answer is that chunk.
  3. For each candidate model, encode corpus + queries, score Recall@K and MRR.
  4. Print a ranked table and write results to data/eval/bakeoff_results.json.

Set the winning model's name as EMBEDDING_MODEL in .env before running
scripts/ingest.py to build the production index.

# ---------------------------------------------------------------------------
# Candidate Models  (Phase 3a, revised plan — bullet 1)
# ---------------------------------------------------------------------------
#
# BAAI/bge-m3
#   Primary candidate and configured production default (EMBEDDING_MODEL=bge-m3).
#   BGE-M3 from BAAI supports dense, sparse, and multi-vector retrieval from a
#   single checkpoint and leads the MTEB leaderboard across multilingual and
#   domain-specific benchmarks. Strong fit for a corpus that mixes English
#   technical prose (ATT&CK), semi-structured JSON (OTX pulses), and varied
#   threat report formats.
#
# thenlper/gte-large
#   GTE-Large (General Text Embeddings, Alibaba DAMO). Strong MTEB English
#   retrieval scores at 1024 dimensions. Included as a validated alternative —
#   its higher dimensionality preserves fine-grained distinctions between
#   closely related ATT&CK subtechniques that smaller models can collapse.
#
# nomic-ai/nomic-embed-text-v1.5
#   Fully open-source (Apache 2.0). Supports Matryoshka dimensionality reduction
#   (64–768) and is optimised for long-context documents up to 8192 tokens,
#   which benefits lengthy CTI PDF sections and verbose OTX pulse descriptions.
#   NOTE: requires trust_remote_code=True in SentenceTransformer(). If this
#   model fails, add a trust_remote_code param to Embedder._load() before
#   re-running.
#
# Voyage-2  (deferred — budget-dependent per Phase 3a plan)
#   Proprietary API model from Voyage AI; not included by default because it
#   requires a separate client (not sentence-transformers) and incurs per-token
#   API cost. Add via --models if budget allows.
# ---------------------------------------------------------------------------
"""
from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports - run-without-install pattern)
import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti._logging import configure_logging, get_logger
from rag_cti.config import get_settings
from rag_cti.embeddings.embedder import Embedder

logger = get_logger(__name__)

_DEFAULT_SOURCES = ("mitre", "otx")
_DEFAULT_MODELS = (
    "BAAI/bge-m3",
    "thenlper/gte-large",
    "nomic-ai/nomic-embed-text-v1.5",
)
_DEFAULT_OUT = Path("data/eval/bakeoff_results.json")
'''
_QUERY_SYSTEM_PROMPT = (
    "You are a CTI analyst generating realistic retrieval queries. Given one "
    "document chunk, produce a single short natural-language question or keyword "
    "query (5-15 words) that a threat analyst would type to find this chunk. "
    "Output ONLY the query text, no quotes, no explanation."
)
'''
_QUERY_SYSTEM_PROMPT = (
    "Role: You are a seasoned Cyber Threat Intelligence (CTI) analyst working under pressure."
    "Context: You are searching a massive database for a specific piece of intelligence you vaguely remember, "
    "but you cannot recall the exact technical terms or indicators."
    "Task: Given a document chunk, generate ONE realistic search query that is intentionally difficult to retrieve. Follow these guidelines to ensure the query is fuzzy:"

    "Conceptual Overlap, not Keyword Overlap: Describe the intent, impact, or behavior without using the unique technical IDs, malware names, or specific CVEs found in the chunk."
    "Analyst 'Memory Fog': Write the query as if you only remember the 'vibe' of the threat (e.g., instead of 'Registry Run Key persistence,' use 'how does this thing stay on the machine after reboot?')."
    "Natural & Imperfect: Use natural language that might be slightly imprecise, or include common analyst 'noise' words."
    "Partial Info: Assume you only know one side of the story (e.g., the victim's industry or the observed effect, but not the tool used). Output Requirement: Output ONLY the query text. No quotes, no preamble, no explanations. 15-30 words."
)

# ---------------------------------------------------------------------------
# Corpus + query generation
# ---------------------------------------------------------------------------

def _sample_chunks(
    processed_dir: Path, sources: tuple[str, ...], n: int, seed: int
) -> list[dict]:
    rng = random.Random(seed)
    pool: list[dict] = []
    for src in sources:
        path = processed_dir / f"{src}.jsonl"
        if not path.exists():
            logger.warning("source missing from processed dir", path=str(path))
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    pool.append(json.loads(line))
    if not pool:
        raise RuntimeError(
            f"No chunks found under {processed_dir} for sources {sources}. "
            f"Run seed scripts first."
        )
    rng.shuffle(pool)
    return pool[:n]


def _generate_queries(
    gold_chunks: list[dict], anthropic_key: str, model: str
) -> list[str]:
    """Call a Claude model to generate one retrieval query per gold chunk."""
    from anthropic import Anthropic  # type: ignore[import]

    client = Anthropic(api_key=anthropic_key)
    queries: list[str] = []
    for i, chunk in enumerate(gold_chunks):
        snippet = chunk["content"][:1200]
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=64,
                system=_QUERY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": snippet}],
            )
            text = "".join(block.text for block in resp.content if getattr(block, "text", None))
            queries.append(text.strip())
        except Exception as exc:
            logger.warning("query generation failed, using fallback", error=str(exc))
            queries.append(chunk["content"][:80])
        if (i + 1) % 5 == 0:
            logger.info("query generation progress", done=i + 1, total=len(gold_chunks))
    return queries


def _generate_queries_groq(
    gold_chunks: list[dict], groq_key: str, model: str
) -> list[str]:
    """Call a Groq-hosted Llama model to generate one retrieval query per gold chunk."""
    from groq import Groq  # type: ignore[import]

    client = Groq(api_key=groq_key)
    queries: list[str] = []
    for i, chunk in enumerate(gold_chunks):
        snippet = chunk["content"][:1200]
        try:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=64,
                messages=[
                    {"role": "system", "content": _QUERY_SYSTEM_PROMPT},
                    {"role": "user", "content": snippet},
                ],
            )
            text = resp.choices[0].message.content or ""
            queries.append(text.strip())
        except Exception as exc:
            logger.warning("query generation failed, using fallback", error=str(exc))
            queries.append(chunk["content"][:80])
        if (i + 1) % 5 == 0:
            logger.info("query generation progress", done=i + 1, total=len(gold_chunks))
    return queries


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _evaluate(
    model_name: str,
    corpus_texts: list[str],
    queries: list[str],
    gold_indices: list[int],
    top_k: int,
    device: str | None = None,
) -> dict:
    embedder = Embedder(model_name, device=device)

    t0 = time.perf_counter()
    corpus_vecs = embedder.encode(corpus_texts)
    t_corpus = time.perf_counter() - t0

    t0 = time.perf_counter()
    query_vecs = embedder.encode(queries)
    t_query = time.perf_counter() - t0

    # Cosine on L2-normalised vectors is a dot product.
    scores = query_vecs @ corpus_vecs.T
    top_idx = np.argsort(-scores, axis=1)[:, :top_k]

    hits = 0
    reciprocal_ranks: list[float] = []
    for q_idx, gold in enumerate(gold_indices):
        ranked = top_idx[q_idx]
        if gold in ranked:
            rank = int(np.where(ranked == gold)[0][0]) + 1
            reciprocal_ranks.append(1.0 / rank)
            hits += 1
        else:
            reciprocal_ranks.append(0.0)

    return {
        "name": model_name,
        "dim": int(embedder.dimension),
        "recall_at_k": hits / len(queries) if queries else 0.0,
        "mrr": float(np.mean(reciprocal_ranks)) if reciprocal_ranks else 0.0,
        "corpus_encode_seconds": round(t_corpus, 3),
        "query_encode_seconds": round(t_query, 3),
        "seconds_per_query": round(t_query / len(queries), 4) if queries else 0.0,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(
    sample_size: int,
    n_queries: int,
    models: tuple[str, ...],
    sources: tuple[str, ...],
    processed_dir: Path,
    top_k: int,
    out_path: Path,
    seed: int,
    query_provider: str = "auto",
    device: str | None = None,
) -> None:
    configure_logging("INFO")
    settings = get_settings()

    logger.info("sampling corpus", size=sample_size, sources=sources)
    corpus = _sample_chunks(processed_dir, sources, sample_size, seed=seed)
    if len(corpus) < sample_size:
        logger.warning(
            "corpus smaller than requested", got=len(corpus), requested=sample_size
        )

    gold_chunks = corpus[:n_queries]
    gold_indices = list(range(len(gold_chunks)))

    groq_key = settings.groq_api_key.get_secret_value()
    anthropic_key = settings.anthropic_api_key.get_secret_value()

    use_groq = (
        query_provider == "groq"
        or (query_provider == "auto" and bool(groq_key))
    )

    if use_groq:
        logger.info(
            "generating queries with Groq", model=settings.groq_query_model, count=len(gold_chunks)
        )
        queries = _generate_queries_groq(
            gold_chunks,
            groq_key=groq_key,
            model=settings.groq_query_model,
        )
        query_model_label = f"groq/{settings.groq_query_model}"
    else:
        logger.info(
            "generating queries with Anthropic", model=settings.llm_routing_model, count=len(gold_chunks)
        )
        queries = _generate_queries(
            gold_chunks,
            anthropic_key=anthropic_key,
            model=settings.llm_routing_model,
        )
        query_model_label = settings.llm_routing_model

    corpus_texts = [c["content"] for c in corpus]

    results: list[dict] = []
    for model_name in models:
        logger.info("evaluating model", model=model_name)
        try:
            result = _evaluate(model_name, corpus_texts, queries, gold_indices, top_k, device=device)
            results.append(result)
        except Exception as exc:
            logger.error("model evaluation failed", model=model_name, error=str(exc))

    # Rank by (recall desc, mrr desc)
    results.sort(key=lambda r: (-r["recall_at_k"], -r["mrr"]))

    query_log = [
        {
            "query": queries[i],
            "gold_chunk_id": gold_chunks[i].get("id", ""),
            "gold_chunk_preview": gold_chunks[i].get("content", "")[:120],
            "generated_by": query_model_label,
        }
        for i in range(len(queries))
    ]

    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "corpus_size": len(corpus),
        "n_queries": len(queries),
        "top_k": top_k,
        "query_generation_model": query_model_label,
        "sources": list(sources),
        "queries": query_log,
        "results": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    _print_table(results, top_k)
    print(f"\n✓ Wrote {out_path}")
    if results:
        print(f"  Winner: {results[0]['name']}  (set EMBEDDING_MODEL in .env)")


def _print_table(results: list[dict], top_k: int) -> None:
    if not results:
        print("\nNo successful evaluations.")
        return
    header = f"{'Model':<45} {'Dim':>5} {'R@' + str(top_k):>7} {'MRR':>7} {'s/query':>9}"
    print("\n" + header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['name']:<45} {r['dim']:>5} "
            f"{r['recall_at_k']:>7.3f} {r['mrr']:>7.3f} {r['seconds_per_query']:>9.4f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Embedding model bakeoff on local CTI corpus")
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--n-queries", type=int, default=50)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--models", nargs="+", default=list(_DEFAULT_MODELS))
    parser.add_argument("--sources", nargs="+", default=list(_DEFAULT_SOURCES))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--device",
        default=None,
        help="Device for sentence-transformers inference, e.g. 'cpu', 'cuda', 'mps'. "
             "Defaults to auto-detect.",
    )
    parser.add_argument(
        "--query-provider",
        choices=["auto", "groq", "anthropic"],
        default="auto",
        help=(
            "LLM provider for query generation. "
            "'auto' prefers Groq when GROQ_API_KEY is set, falls back to Anthropic."
        ),
    )
    args = parser.parse_args()

    if args.n_queries > args.sample_size:
        parser.error("--n-queries cannot exceed --sample-size")

    run(
        sample_size=args.sample_size,
        n_queries=args.n_queries,
        models=tuple(args.models),
        sources=tuple(args.sources),
        processed_dir=args.processed_dir,
        top_k=args.top_k,
        out_path=args.out,
        seed=args.seed,
        query_provider=args.query_provider,
        device=args.device,
    )


if __name__ == "__main__":
    main()
