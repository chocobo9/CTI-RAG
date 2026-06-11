"""Phase D — capability-split evaluation summary (four capabilities, NEVER averaged).

PROJECT_SPEC.md §2 / CLAUDE.md §5: the four capabilities are reported SEPARATELY,
each with its own metric, data split, and trust provenance. This script aggregates
already-produced, traceable artifacts into one canonical report:

  1. technique extraction  — CERTIFIED external anchor: CTI-ATE (Enterprise) Micro-F1(tech)
                              (Phase C result). Sourced from the latest certification
                              record that carries a technique result; pass/fail read live.
  2. actor attribution     — CERTIFIED external anchor: CTI-TAA correct/plausible
                              (sourced from the latest cert that carries an actor result).
  3. heterogeneous retrieval — self query-set, de-backdoored eval_attribution, set metrics.
                              relationship_direct gold is DETERMINISTIC (ATT&CK graph
                              traversal — see query_set_v3 gold_provenance), not LLM-guessed.
  4. generation grounding  — RAGAS faithfulness + answer_relevancy over real generations
                              (real Groq generator + DeepSeek judge). context_precision/
                              recall only when the query set carries reference answers.

It does NOT average across capabilities and does NOT fabricate any score: a capability
whose artifact is missing is reported "not available", never as 0 or a guess. RAGAS runs
real LLMs (no mock — CLAUDE.md §2.6); a missing API key aborts with an error.

Usage:
    python scripts/eval_capabilities.py                       # aggregate existing artifacts
    python scripts/eval_capabilities.py --ragas               # also run generation grounding
    python scripts/eval_capabilities.py --ragas --ragas-n 0   # RAGAS over the full query set
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import glob
import json
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.bootstrap import (
    DEEPSEEK_DEFAULT_MODEL,
    FixedRouter,
    build_deepseek_client,
    build_retrieval_stack,
)
from rag_cti.bootstrap import (
    EVAL_DIR as _EVAL_DIR,
)

_DEFAULT_QUERY_SET = _EVAL_DIR / "query_set_v3.jsonl"
_RAGAS_ARTIFACT = _EVAL_DIR / "ragas_v3_results.json"
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _rel(path: Path | str | None) -> str | None:
    """Project-root-relative form for paths recorded in the summary.

    Absolute paths broke traceability across machines/mounts (the summary
    pointed at /mnt/d/... that other checkouts don't have).
    """
    if path is None:
        return None
    p = Path(path).resolve()
    try:
        return p.relative_to(_PROJECT_ROOT).as_posix()
    except ValueError:
        return str(p)


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def _latest(pattern: str) -> Path | None:
    """Latest file matching pattern, by mtime (robust to lexical name drift)."""
    matches = glob.glob(str(_EVAL_DIR / pattern))
    return Path(max(matches, key=lambda p: Path(p).stat().st_mtime)) if matches else None


def _latest_cert_where(predicate: Callable[[dict[str, Any]], bool]) -> tuple[Path, dict] | None:
    """Latest certification_full_*.json (by mtime) whose loaded JSON satisfies predicate."""
    candidates: list[tuple[float, Path, dict]] = []
    for p in glob.glob(str(_EVAL_DIR / "certification_full_*.json")):
        d = _load_json(Path(p))
        if d and predicate(d):
            candidates.append((Path(p).stat().st_mtime, Path(p), d))
    if not candidates:
        return None
    _, path, doc = max(candidates, key=lambda t: t[0])
    return path, doc


def _fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    return f"{v:.4f}" if isinstance(v, (int, float)) else str(v)


# ---------------------------------------------------------------------------
# Capability 4: generation grounding — real RAGAS run (no mock).
# ---------------------------------------------------------------------------


def _stratified_sample(rows: list[dict], n: int) -> list[dict]:
    """Pick up to n rows spread evenly across categories (deterministic, query_id order).

    n<=0 or n>=len -> all rows. Otherwise round-robin across categories so generation
    grounding is measured on heterogeneous content, not one category. No silent cap:
    the caller logs exactly which query_ids were used.
    """
    if n <= 0 or n >= len(rows):
        return list(rows)
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(rows, key=lambda x: x.get("query_id", "")):
        by_cat[r["category"]].append(r)
    picked: list[dict] = []
    idx = 0
    while len(picked) < n:
        added = False
        for cat in sorted(by_cat):
            if idx < len(by_cat[cat]):
                picked.append(by_cat[cat][idx])
                added = True
                if len(picked) >= n:
                    break
        if not added:
            break
        idx += 1
    return picked


def run_generation_grounding(
    query_set: Path,
    collection: str | None,
    device: str | None,
    n: int,
    top_k: int,
    gen_provider: str = "groq",
) -> dict[str, Any]:
    """Generate answers with the real production path, then score with RAGAS.

    Writes the artifact to _RAGAS_ARTIFACT and returns it. Real Groq generator +
    DeepSeek judge (ragas_eval). references=None (the query set has no reference
    answers), so context_precision/recall are NOT computed — reported as not-available
    rather than fabricated (CLAUDE.md §2.7: no hand-written gold).
    """
    from rag_cti.config import get_settings
    from rag_cti.evaluation.ragas_eval import run_ragas_eval
    from rag_cti.generation.client import build_llm_client
    from rag_cti.generation.generator import _LLM_FAILURE_SENTINEL, Generator
    from rag_cti.generation.llm_router import LLMRouter
    from rag_cti.retrieval import build_pipeline

    settings = get_settings()
    stack = build_retrieval_stack(settings, collection=collection, device=device)
    coll = stack.collection

    # Generator provider. Production answer-synthesis uses Groq (groq_analysis_model).
    # When Groq's daily token cap is exhausted, --gen-provider deepseek routes generation
    # to DeepSeek (the RAGAS judge already uses DeepSeek). The actual generator model is
    # recorded in the artifact so the grounding measurement is never mislabeled.
    if gen_provider == "deepseek":
        client = build_deepseek_client(settings)
        gen_model = DEEPSEEK_DEFAULT_MODEL
        router: Any = FixedRouter(gen_model)
    else:
        _provider, client = build_llm_client(settings)
        gen_model = settings.groq_analysis_model
        router = LLMRouter(settings)
    # Production hybrid + reranker, HyDE OFF (same as certify/eval).
    pipeline = build_pipeline(
        settings=settings,
        store=stack.store,
        embedder=stack.embedder,
        encoder=stack.encoder,
        llm_client=None,
    )
    generator = Generator(client=client, router=router, settings=settings)

    rows = [
        json.loads(line)
        for line in query_set.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    sample = _stratified_sample(rows, n)
    print(
        f"  RAGAS generation grounding: {len(sample)}/{len(rows)} queries "
        f"(collection={coll}, gen={gen_model} [{gen_provider}], top_k={top_k})",
        flush=True,
    )
    print(f"  sampled query_ids: {[r.get('query_id') for r in sample]}", flush=True)

    # Generate, but NEVER score a failed generation. _call_llm returns a sentinel
    # string on provider failure (e.g. Groq daily-token cap); feeding that to RAGAS
    # would fabricate a (zero) grounding score. Exclude failures and report them
    # (CLAUDE.md §2.6: LLM unavailable -> FAIL+report, don't fake a number).
    answers = []
    used_rows: list[dict] = []
    failed: list[str] = []
    for i, r in enumerate(sample, start=1):
        qr = pipeline.run(r["query"], top_k=top_k)
        ans = generator.generate(r["query"], qr)
        if not (ans.answer or "").strip() or ans.answer.strip() == _LLM_FAILURE_SENTINEL:
            failed.append(r.get("query_id"))
        else:
            answers.append(ans)
            used_rows.append(r)
        if i % 5 == 0:
            print(f"    generated {i}/{len(sample)} ({len(failed)} failed)", flush=True)

    if failed:
        print(
            f"  WARNING: {len(failed)} generations failed (LLM unavailable / quota) — "
            f"EXCLUDED from RAGAS so they do not fabricate a score: {failed}",
            flush=True,
        )

    base = {
        "timestamp": datetime.now(UTC).isoformat(),
        "query_set": str(query_set),
        "collection": coll,
        "generator_model": gen_model,
        "generator_provider": gen_provider,
        "judge": "deepseek-chat (ragas)",
        "n_requested": len(sample),
        "n_failed": len(failed),
        "generation_failures": failed,
        "sampled_query_ids": [r.get("query_id") for r in sample],
        "references_available": False,
    }
    if not answers:
        # All generations failed -> do NOT fabricate a grounding score.
        artifact = {
            **base,
            "status": "BLOCKED — all generations failed (LLM unavailable / quota); no score computed",
            "n": 0,
            "faithfulness": None,
            "answer_relevancy": None,
            "context_precision": None,
            "context_recall": None,
            "per_query": [],
        }
        _RAGAS_ARTIFACT.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  saved RAGAS artifact (BLOCKED) -> {_RAGAS_ARTIFACT}", flush=True)
        return artifact

    result = run_ragas_eval(answers, config=f"hybrid@k{top_k}", settings=settings, references=None)

    # attach query_id/category onto per_query for traceability (aligned to used_rows)
    for pq, r in zip(result.per_query, used_rows, strict=True):
        pq["query_id"] = r.get("query_id")
        pq["category"] = r.get("category")

    artifact = {
        **base,
        "config": result.config,
        "n": result.n_queries,  # scored = successfully generated
        "faithfulness": result.faithfulness,
        "answer_relevancy": result.answer_relevancy,
        "context_precision": result.context_precision,  # -1.0 == not computed (no references)
        "context_recall": result.context_recall,
        "per_query": result.per_query,
    }
    _RAGAS_ARTIFACT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  saved RAGAS artifact -> {_RAGAS_ARTIFACT}", flush=True)
    return artifact


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def build_summary(attribution_path: Path | None) -> dict[str, Any]:
    capabilities: dict[str, Any] = {}
    sources: dict[str, str | None] = {}

    # 1. technique extraction — latest cert with a technique result; prefer a PASS.
    tech_hit = _latest_cert_where(
        lambda d: ((d.get("technique") or {}).get("enterprise") or {}).get("pass") is True
    ) or _latest_cert_where(
        lambda d: ((d.get("technique") or {}).get("enterprise") or {}).get("micro_f1") is not None
    )
    if tech_hit:
        tpath, cert = tech_hit
        sources["technique_cert"] = _rel(tpath)
        ent = cert["technique"]["enterprise"]
        mob = cert["technique"].get("mobile_out_of_corpus") or {}
        thr = (cert.get("thresholds") or {}).get("tech_micro_f1")
        capabilities["technique_extraction"] = {
            "metric": "Micro-F1(technique)",
            "data": f"CTI-ATE Enterprise n={ent.get('n')}",
            "score": {
                "micro_f1": ent.get("micro_f1"),
                "precision": ent.get("precision"),
                "recall": ent.get("recall"),
            },
            "external_anchor": "TechniqueRAG/CTIBench RAG-no-ft 0.65-0.79",
            "gate": {"threshold": thr, "pass": ent.get("pass")},
            "trust": "CERTIFIED against external human GT (Phase C). "
            + ("Gate PASSED." if ent.get("pass") else "Gate NOT passed."),
            "mobile_out_of_corpus": {
                "micro_f1": mob.get("micro_f1"),
                "n": mob.get("n"),
                "note": "corpus is Enterprise ATT&CK only; not gated",
            },
        }
    else:
        capabilities["technique_extraction"] = {
            "status": "NOT AVAILABLE — no certification record with a technique result"
        }
        sources["technique_cert"] = None

    # 2. actor attribution — latest cert that actually carries an actor result.
    actor_hit = _latest_cert_where(
        lambda d: (d.get("actor") or {}).get("plausible_acc") is not None
    )
    if actor_hit:
        apath, cert = actor_hit
        sources["actor_cert"] = _rel(apath)
        a = cert["actor"]
        thr = (cert.get("thresholds") or {}).get("actor_plausible")
        capabilities["actor_attribution"] = {
            "metric": "correct / plausible accuracy (faithful cti-bench scorer)",
            "data": f"CTI-TAA n={a.get('n')}",
            "score": {
                "correct_acc": a.get("correct_acc"),
                "plausible_acc": a.get("plausible_acc"),
                "C": a.get("correct"),
                "P": a.get("plausible"),
                "I": a.get("incorrect"),
            },
            "external_anchor": "cti-bench published models (e.g. ChatGPT-3.5 ~0.44/0.62)",
            "gate": {"threshold": thr, "pass": a.get("pass")},
            "trust": "CERTIFIED against external human GT. "
            + ("Plausible gate PASSED." if a.get("pass") else "Plausible gate NOT passed.")
            + " Actor self-gold not generated (per user).",
        }
    else:
        capabilities["actor_attribution"] = {
            "status": "NOT AVAILABLE — no certification record with an actor result"
        }
        sources["actor_cert"] = None

    # 3. heterogeneous retrieval — latest v3 attribution result.
    apath = attribution_path or _latest("attribution_v3*.json")
    attribution = _load_json(apath)
    sources["attribution"] = _rel(apath)
    if attribution and attribution.get("results"):
        res = attribution["results"][0]
        capabilities["heterogeneous_retrieval"] = {
            "metric": "set P/R/F1@k (multi-label) + pulse Recall@k + hit@k (single-target)",
            "data": f"self query-set {attribution.get('query_set')}",
            "by_category_hit": {
                c: m.get("hit_at_k") for c, m in res.get("by_category", {}).items()
            },
            "set_metrics": res.get("set_metrics"),
            "external_anchor": "none",
            "trust": "relationship_direct gold is DETERMINISTIC (ATT&CK graph traversal, see "
            "query_set_v3 gold_provenance) — not LLM-guessed. otx_actor backdoor REMOVED "
            "(pulse_id-only). pulse_id categories rest on hard identifiers. Other categories "
            "(precise/semantic/fuzzy/relationship_reverse) keep LLM self-gold — directional.",
        }
    else:
        capabilities["heterogeneous_retrieval"] = {
            "status": "NOT AVAILABLE — run scripts/eval_attribution.py --query-set data/eval/query_set_v3.jsonl "
            "--output data/eval/attribution_v3_results.json"
        }

    # 4. generation grounding — latest RAGAS artifact (written by --ragas).
    ragas = _load_json(_RAGAS_ARTIFACT)
    sources["ragas"] = _rel(_RAGAS_ARTIFACT) if ragas else None
    if ragas and ragas.get("status", "").startswith("BLOCKED"):
        capabilities["generation_grounding"] = {
            "status": ragas["status"],
            "data": f"requested n={ragas.get('n_requested')}, all failed: {ragas.get('generation_failures')}",
        }
    elif ragas:
        ctx_avail = ragas.get("references_available")
        n_failed = ragas.get("n_failed", 0)
        trunc = (
            f" QUOTA-TRUNCATED: {n_failed}/{ragas.get('n_requested')} generations failed "
            f"(Groq daily-token cap) and were EXCLUDED ({ragas.get('generation_failures')}); "
            f"re-run after quota reset for the full sample."
            if n_failed
            else ""
        )
        capabilities["generation_grounding"] = {
            "metric": "RAGAS faithfulness + answer_relevancy"
            + (" + context_precision/recall" if ctx_avail else ""),
            "data": f"self query-set {ragas.get('query_set')} n={ragas.get('n')} scored"
            f" of {ragas.get('n_requested')} requested ({ragas.get('config')})",
            "score": {
                "faithfulness": ragas.get("faithfulness"),
                "answer_relevancy": ragas.get("answer_relevancy"),
                "context_precision": (ragas.get("context_precision") if ctx_avail else None),
                "context_recall": (ragas.get("context_recall") if ctx_avail else None),
            },
            "external_anchor": "none",
            "trust": f"Real generations ({ragas.get('generator_model')}) judged by {ragas.get('judge')} — no mock."
            + trunc
            + (
                ""
                if ctx_avail
                else " context_precision/recall NOT computed: query set has no reference "
                "answers, and fabricating them is forbidden (CLAUDE.md §2.7)."
            ),
        }
    else:
        capabilities["generation_grounding"] = {
            "status": "NOT RUN — run with --ragas (real Groq generator + DeepSeek judge)."
        }

    return {
        "phase": "D — capability-split summary (four capabilities, never averaged)",
        "generated_utc": datetime.now(UTC).isoformat(),
        "artifact_sources": sources,
        "capabilities_NEVER_averaged": capabilities,
    }


def print_summary(summary: dict[str, Any]) -> None:
    caps = summary["capabilities_NEVER_averaged"]
    print("\n" + "=" * 78)
    print("CAPABILITY-SPLIT EVALUATION — four capabilities, reported SEPARATELY (never averaged)")
    print("=" * 78)

    tech = caps["technique_extraction"]
    print("\n[1] technique extraction")
    if "score" in tech:
        s = tech["score"]
        print(f"    metric: {tech['metric']} | {tech['data']}")
        print(
            f"    score : F1={_fmt(s['micro_f1'])} P={_fmt(s['precision'])} R={_fmt(s['recall'])}"
        )
        print(
            f"    gate  : >= {tech['gate']['threshold']} -> {'PASS' if tech['gate']['pass'] else 'FAIL'}"
        )
        print(f"    anchor: {tech['external_anchor']}")
        print(
            f"    mobile (out-of-corpus, not gated): F1={_fmt(tech['mobile_out_of_corpus']['micro_f1'])}"
        )
        print(f"    trust : {tech['trust']}")
    else:
        print(f"    {tech['status']}")

    actor = caps["actor_attribution"]
    print("\n[2] actor attribution")
    if "score" in actor:
        s = actor["score"]
        print(f"    metric: {actor['metric']} | {actor['data']}")
        print(
            f"    score : correct={_fmt(s['correct_acc'])} plausible={_fmt(s['plausible_acc'])} (C={s['C']} P={s['P']} I={s['I']})"
        )
        print(
            f"    gate  : plausible >= {actor['gate']['threshold']} -> {'PASS' if actor['gate']['pass'] else 'FAIL'}"
        )
        print(f"    anchor: {actor['external_anchor']}")
        print(f"    trust : {actor['trust']}")
    else:
        print(f"    {actor['status']}")

    het = caps["heterogeneous_retrieval"]
    print("\n[3] heterogeneous retrieval")
    if "set_metrics" in het:
        print(f"    metric: {het['metric']} | {het['data']}")
        print(f"    hit@k by category: {json.dumps(het['by_category_hit'], ensure_ascii=False)}")
        print(f"    set metrics      : {json.dumps(het['set_metrics'], ensure_ascii=False)}")
        print(f"    trust : {het['trust']}")
    else:
        print(f"    {het['status']}")

    gen = caps["generation_grounding"]
    print("\n[4] generation grounding")
    if "score" in gen:
        s = gen["score"]
        print(f"    metric: {gen['metric']} | {gen['data']}")
        print(
            f"    score : faithfulness={_fmt(s['faithfulness'])} answer_relevancy={_fmt(s['answer_relevancy'])}"
        )
        print(
            f"            context_precision={_fmt(s['context_precision'])} context_recall={_fmt(s['context_recall'])}"
        )
        print(f"    trust : {gen['trust']}")
    else:
        print(f"    {gen['status']}")

    print("\n" + "=" * 78)
    print("Note: scores are NEVER averaged across capabilities. Each rests on its own gold/anchor.")
    print("=" * 78 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Capability-split eval summary (never averaged)")
    parser.add_argument(
        "--attribution", default=None, help="Path to a v3 attribution result JSON (default: latest)"
    )
    parser.add_argument("--output", default=str(_EVAL_DIR / "capabilities_summary.json"))
    parser.add_argument(
        "--ragas",
        action="store_true",
        help="Run generation grounding (real generator + DeepSeek judge)",
    )
    parser.add_argument(
        "--ragas-n", type=int, default=14, help="Queries for RAGAS (stratified; 0 = all)"
    )
    parser.add_argument(
        "--ragas-k", type=int, default=10, help="Retrieval top_k for the generation context"
    )
    parser.add_argument(
        "--gen-provider",
        choices=["groq", "deepseek"],
        default="groq",
        help="LLM that generates answers for grounding (deepseek when Groq quota is exhausted)",
    )
    parser.add_argument("--query-set", default=str(_DEFAULT_QUERY_SET))
    parser.add_argument("--collection", default=None, help="Override qdrant collection")
    parser.add_argument("--device", default=None, help="Embedder device, e.g. cuda")
    args = parser.parse_args()

    if args.ragas:
        print("Running generation grounding (RAGAS) — real LLMs, no mock ...", flush=True)
        run_generation_grounding(
            query_set=Path(args.query_set),
            collection=args.collection,
            device=args.device,
            n=args.ragas_n,
            top_k=args.ragas_k,
            gen_provider=args.gen_provider,
        )

    attribution_path = Path(args.attribution) if args.attribution else None
    summary = build_summary(attribution_path)
    print_summary(summary)
    Path(args.output).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved capability summary: {args.output}")


if __name__ == "__main__":
    main()
