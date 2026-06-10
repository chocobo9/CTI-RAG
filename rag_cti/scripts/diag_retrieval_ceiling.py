"""TEMPORARY diagnostic — retrieval recall-ceiling instrumentation (retrieval-only).

WHY: Phase C technique extraction FAILED (CTI-ATE Enterprise Micro-F1=0.49), localized
to a retrieval recall ceiling (gold technique presence in top-40). certify_annotator.py
discards pipeline.run() candidates, so the ceiling cannot be recomputed from existing
artifacts. This script persists a reproducible, decomposable diagnostic JSON.

It does NOT touch certification, production code, or any LLM:
  * read-only on the corpus (no writes / no collection mutation)
  * NO LLM calls (ceiling is retrieval-only; the annotator is irrelevant here)
  * adds only this one script; does not modify certify_annotator.py / config.py / src/
  * no mocking, no fabricated data — if it cannot run, it errors honestly

Semantics are aligned EXACTLY with certify_annotator (no custom matching):
  rows   = certify_annotator.load_ate(None) filtered to platform=="enterprise" (47)
  gold   = set_metrics.normalize_set(gold, "technique")
  cand   = set_metrics.normalize_id(attack_id, "technique")
  stack  = collection cti_chunks_v2, HyDE OFF, CrossEncoder reranker ON, RETRIEVE_K=40

Three retrieval modes (fusion is pure RRF — no continuous alpha sweep):
  hybrid_rrf  = build_pipeline(hybrid_alpha_override=None)  -> reproduces the cert stack
  pure_dense  = build_pipeline(hybrid_alpha_override=1.0)   -> dense-only branch
  pure_sparse = manual Pipeline(SparseRetriever, same CrossEncoderReranker)

Each mode also gets a `_dedup` ceiling variant (dedup + deep fetch). The baseline top-40
is diluted because one technique occupies dozens of candidate slots (e.g. T1059 has ~70
docs in the corpus), so top-40 only covers ~16 distinct techniques. The variant instead:
  1. retrieves to depth DEEP_K=300 (pipeline.run(desc, top_k=300)),
  2. collapses candidates to one chunk per normalized technique (highest score; candidates
     with a null attack_id are dropped — no label = useless for technique recall),
  3. sorts the survivors by score and keeps the top DISTINCT_K=40 distinct techniques,
  4. recomputes recall over those 40 (口径 unchanged: pair-level, denominator = Σgold).
This measures the true distinct-technique recall ceiling at width 40.

HARD reproduction gate: hybrid_rrf recall@10/@40 must match the historical
0.321 / 0.542 within ±0.01, else stop with reproduction_mismatch (口径 differs).
The gate is checked BEFORE any _dedup variant runs — an unreproduced baseline makes
the ceiling deltas meaningless.

Usage:
    python scripts/diag_retrieval_ceiling.py
    python scripts/diag_retrieval_ceiling.py --limit 3   # smoke (skips the gate)
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import gc
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))  # import certify_annotator for load_ate

from dotenv import load_dotenv

load_dotenv()

import certify_annotator as ca  # noqa: E402  (load_ate — exact same row loader as cert)

from rag_cti.bootstrap import EVAL_DIR as _EVAL_DIR
from rag_cti.bootstrap import build_retrieval_stack
from rag_cti.config import get_settings
from rag_cti.evaluation.set_metrics import normalize_id, normalize_set
from rag_cti.retrieval import build_pipeline
from rag_cti.retrieval.pipeline import Pipeline
from rag_cti.retrieval.reranker import CrossEncoderReranker
from rag_cti.retrieval.sparse_retriever import SparseRetriever

RETRIEVE_K = 40
K_VALUES = (10, 40)
EXPECTED_R10 = 0.321
EXPECTED_R40 = 0.542
TOL = 0.01

# _dedup variants: fetch deep, then collapse to one chunk per technique.
DEEP_K = 300            # retrieval depth before per-technique dedup
DISTINCT_K = RETRIEVE_K  # distinct techniques kept after dedup (ceiling width = top-40)


def _git_rev() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _free() -> None:
    gc.collect()
    try:
        import torch

        torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass


def build_components(settings: Any, device: str | None) -> tuple[Any, Any, Any]:
    """store / embedder / encoder — same construction as certify_annotator.build()."""
    stack = build_retrieval_stack(settings, device=device)
    return stack.store, stack.embedder, stack.encoder


def _candidate_records(qr: Any) -> list[dict[str, Any]]:
    """Ordered top-k candidates, 1-based rank, technique-normalized attack_id."""
    out: list[dict[str, Any]] = []
    for i, r in enumerate(qr.results, start=1):
        doc = r.document
        aid_raw = doc.metadata.get("attack_id")
        aid_tech = normalize_id(aid_raw, "technique") if aid_raw else None
        out.append({
            "rank": i,
            "attack_id_raw": aid_raw,
            "attack_id_tech": aid_tech,
            "score": round(float(r.score), 6),
            "source": doc.source,
            "chunk_id": doc.id,
            "parent_doc_id": doc.parent_doc_id,
            "content_head": (doc.content or "")[:100],
        })
    return out


def _dedup_candidates(
    cands: list[dict[str, Any]], distinct_k: int
) -> list[dict[str, Any]]:
    """Collapse deep candidates to one chunk per technique, keep the top `distinct_k`.

    Drops candidates with a null attack_id_tech (no technique label = useless for
    technique recall), keeps the highest-scoring chunk per normalized technique,
    sorts the survivors by score desc, truncates to `distinct_k`, and reassigns
    1-based ranks. Returns NEW dicts (no mutation of the input records).
    """
    best: dict[str, dict[str, Any]] = {}
    for c in cands:
        tech = c["attack_id_tech"]
        if tech is None:
            continue
        prev = best.get(tech)
        if prev is None or c["score"] > prev["score"]:
            best[tech] = c
    ranked = sorted(best.values(), key=lambda c: c["score"], reverse=True)[:distinct_k]
    return [{**c, "rank": i} for i, c in enumerate(ranked, start=1)]


def eval_mode(
    pipeline: Any,
    rows: list[tuple[str, list[str], str]],
    *,
    retrieve_k: int = RETRIEVE_K,
    dedup: bool = False,
    distinct_k: int = DISTINCT_K,
) -> dict[str, Any]:
    """Run retrieval for every row; return per-row detail + pair-level aggregates.

    Baseline (dedup=False): retrieve `retrieve_k` candidates and score recall over them
    as-is — one technique may occupy many slots, diluting distinct coverage.
    Dedup variant (dedup=True): retrieve `retrieve_k` (deep, e.g. 300) candidates, collapse
    to one chunk per technique via _dedup_candidates, keep the top `distinct_k` distinct
    techniques by score, then score recall over those. The 口径 is unchanged — still
    pair-level recall@k with denominator = Σgold; only the candidate set differs.
    """
    per_row: list[dict[str, Any]] = []
    covered = dict.fromkeys(K_VALUES, 0)
    n_gold_pairs = 0
    distinct_counts: list[int] = []

    for i, (desc, gold_raw, platform) in enumerate(rows, start=1):
        qr = pipeline.run(desc, top_k=retrieve_k)
        cands = _candidate_records(qr)
        if dedup:
            cands = _dedup_candidates(cands, distinct_k)
        gold = sorted(normalize_set(gold_raw, "technique"))

        # first_hit_rank: 1-based rank where each gold technique first appears (else None)
        first_hit: dict[str, int | None] = {}
        for g in gold:
            fr: int | None = None
            for c in cands:
                if c["attack_id_tech"] == g:
                    fr = int(c["rank"])
                    break
            first_hit[g] = fr

        distinct_tech = {c["attack_id_tech"] for c in cands if c["attack_id_tech"]}
        distinct_counts.append(len(distinct_tech))
        n_gold_pairs += len(gold)
        for k in K_VALUES:
            covered[k] += sum(1 for g in gold if (fr := first_hit[g]) is not None and fr <= k)

        per_row.append({
            "row": i,
            "platform": platform,
            "desc_head": desc[:120],
            "gold_tech": gold,
            "first_hit_rank": first_hit,
            "distinct_tech_in_top40": len(distinct_tech),
            "n_candidates": len(cands),
            "candidates": cands,
        })
        print(f"    row {i}/{len(rows)}: gold={len(gold)} "
              f"covered@40={sum(1 for g in gold if first_hit[g] is not None)} "
              f"distinct_tech={len(distinct_tech)}", flush=True)

    mean_distinct = round(sum(distinct_counts) / len(distinct_counts), 3) if distinct_counts else 0.0
    return {
        "n_rows": len(rows),
        "n_gold_pairs": n_gold_pairs,
        "covered_at_10": covered[10],
        "covered_at_40": covered[40],
        "recall_at_10": round(covered[10] / n_gold_pairs, 4) if n_gold_pairs else 0.0,
        "recall_at_40": round(covered[40] / n_gold_pairs, 4) if n_gold_pairs else 0.0,
        "mean_distinct_tech_in_top40": mean_distinct,
        "per_row": per_row,
    }


def _build_sparse_pipeline(settings: Any, store: Any, encoder: Any) -> Pipeline:
    return Pipeline(
        retriever=SparseRetriever(store, encoder),
        reranker=CrossEncoderReranker(model_name=settings.reranker_model),
        settings=settings,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieval recall-ceiling diagnostic (retrieval-only)")
    parser.add_argument("--device", default=None, help="Embedder/reranker device, e.g. cuda")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows for a smoke run (skips the gate)")
    parser.add_argument("--output", default=None, help="Override output JSON path")
    args = parser.parse_args()

    settings = get_settings()
    store, embedder, encoder = build_components(settings, args.device)

    rows = [r for r in ca.load_ate(None) if r[2].lower() == "enterprise"]
    if args.limit:
        rows = rows[: args.limit]
    print(f"Loaded {len(rows)} Enterprise CTI-ATE rows "
          f"(Σgold={sum(len(normalize_set(g, 'technique')) for _, g, _ in rows)})", flush=True)

    provenance = {
        "collection": settings.qdrant_collection,
        "embedding_model": settings.embedding_model,
        "reranker_model": settings.reranker_model,
        "hyde": False,
        "retrieve_k": RETRIEVE_K,
        "settings_hybrid_alpha": settings.hybrid_alpha,
        "git_rev": _git_rev(),
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "reproduction_gate": {"expected_recall_at_10": EXPECTED_R10,
                              "expected_recall_at_40": EXPECTED_R40, "tol": TOL},
        "smoke_limit": args.limit,
    }

    modes: dict[str, Any] = {}

    # --- Mode 1: hybrid_rrf (reproduces the cert stack) ---
    print("\n[mode] hybrid_rrf (hybrid_alpha_override=None)", flush=True)
    hyb_pipe = build_pipeline(settings=settings, store=store, embedder=embedder,
                              encoder=encoder, llm_client=None, hybrid_alpha_override=None)
    modes["hybrid_rrf"] = eval_mode(hyb_pipe, rows)
    # NB: keep hyb_pipe alive — reused for hybrid_rrf_dedup once the gate passes.

    got10, got40 = modes["hybrid_rrf"]["recall_at_10"], modes["hybrid_rrf"]["recall_at_40"]
    gate_ok = abs(got10 - EXPECTED_R10) <= TOL and abs(got40 - EXPECTED_R40) <= TOL

    if not args.limit and not gate_ok:
        mismatch = {"expected": {"recall_at_10": EXPECTED_R10, "recall_at_40": EXPECTED_R40},
                    "got": {"recall_at_10": got10, "recall_at_40": got40}}
        out = {"provenance": provenance, "reproduction_mismatch": mismatch, "modes": modes}
        path = _write(args, out)
        print("\n" + "!" * 72)
        print(f"REPRODUCTION MISMATCH: hybrid_rrf got recall@10={got10}, recall@40={got40}; "
              f"expected {EXPECTED_R10}/{EXPECTED_R40} (±{TOL}).")
        print("Historical ceiling 口径 differs from this script — ALIGN FIRST before decomposing.")
        print("Stopped; _dedup variants / pure_dense / pure_sparse NOT run.")
        print("!" * 72)
        print(f"Saved: {path}")
        sys.exit(2)

    if args.limit:
        print(f"\n(smoke --limit {args.limit}: reproduction gate skipped)")
    else:
        print(f"\nReproduction gate PASS: recall@10={got10} (~{EXPECTED_R10}), "
              f"recall@40={got40} (~{EXPECTED_R40})")

    # --- Mode 1b: hybrid_rrf_dedup (same pipe, deep fetch + dedup) ---
    print(f"\n[mode] hybrid_rrf_dedup (deep top_k={DEEP_K} → top-{DISTINCT_K} distinct)", flush=True)
    modes["hybrid_rrf_dedup"] = eval_mode(hyb_pipe, rows, retrieve_k=DEEP_K, dedup=True)
    del hyb_pipe
    _free()

    # --- Mode 2: pure_dense (+ dedup variant on the same pipe) ---
    print("\n[mode] pure_dense (hybrid_alpha_override=1.0)", flush=True)
    dense_pipe = build_pipeline(settings=settings, store=store, embedder=embedder,
                                encoder=encoder, llm_client=None, hybrid_alpha_override=1.0)
    modes["pure_dense"] = eval_mode(dense_pipe, rows)
    print(f"\n[mode] pure_dense_dedup (deep top_k={DEEP_K} → top-{DISTINCT_K} distinct)", flush=True)
    modes["pure_dense_dedup"] = eval_mode(dense_pipe, rows, retrieve_k=DEEP_K, dedup=True)
    del dense_pipe
    _free()

    # --- Mode 3: pure_sparse (manual Pipeline; same reranker) + dedup variant ---
    print("\n[mode] pure_sparse (SparseRetriever + same CrossEncoderReranker)", flush=True)
    try:
        sparse_pipe = _build_sparse_pipeline(settings, store, encoder)
        modes["pure_sparse"] = eval_mode(sparse_pipe, rows)
        print(f"\n[mode] pure_sparse_dedup (deep top_k={DEEP_K} → top-{DISTINCT_K} distinct)", flush=True)
        modes["pure_sparse_dedup"] = eval_mode(sparse_pipe, rows, retrieve_k=DEEP_K, dedup=True)
        del sparse_pipe
        _free()
    except Exception as exc:  # noqa: BLE001
        modes["pure_sparse"] = {"skipped": f"{type(exc).__name__}: {exc}"}
        print(f"    pure_sparse skipped: {exc}", flush=True)

    out = {"provenance": provenance, "modes": modes}
    path = _write(args, out)
    _print_table(modes)
    print(f"\nSaved: {path}")


def _write(args: argparse.Namespace, out: dict[str, Any]) -> Path:
    if args.output:
        path = Path(args.output)
    else:
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
        path = _EVAL_DIR / f"diag_retrieval_ceiling_{stamp}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _print_table(modes: dict[str, Any]) -> None:
    """Baseline (top-40) vs _dedup (deep top-300 → top-40 distinct), side by side."""
    print("\n" + "=" * 92)
    print(f"dedup+deep-fetch ceiling — baseline (top-{RETRIEVE_K}) vs "
          f"_dedup (deep top-{DEEP_K} → top-{DISTINCT_K} distinct)")
    print("-" * 92)
    print(f"{'mode':<13}{'base@10':>9}{'dedup@10':>10}{'base@40':>9}{'dedup@40':>10}"
          f"{'Δ@40':>9}{'base_dist':>11}{'dedup_dist':>12}")
    print("-" * 92)
    for base in ("hybrid_rrf", "pure_dense", "pure_sparse"):
        b = modes.get(base)
        if not b:
            continue
        if "skipped" in b:
            print(f"{base:<13}SKIPPED — {b['skipped']}")
            continue
        d = modes.get(base + "_dedup")
        b10, b40, bdist = b["recall_at_10"], b["recall_at_40"], b["mean_distinct_tech_in_top40"]
        if d and "skipped" not in d:
            d10, d40, ddist = d["recall_at_10"], d["recall_at_40"], d["mean_distinct_tech_in_top40"]
            print(f"{base:<13}{b10:>9.4f}{d10:>10.4f}{b40:>9.4f}{d40:>10.4f}"
                  f"{d40 - b40:>+9.4f}{bdist:>11.3f}{ddist:>12.3f}")
        else:
            print(f"{base:<13}{b10:>9.4f}{'—':>10}{b40:>9.4f}{'—':>10}"
                  f"{'—':>9}{bdist:>11.3f}{'—':>12}")
    print("=" * 92)


if __name__ == "__main__":
    main()
