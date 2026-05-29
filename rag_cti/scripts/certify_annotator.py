"""Phase C — certify the LLM annotator against CTI-ATE / CTI-TAA HUMAN ground truth.

This is the project's命门 (hard gate, PROJECT_SPEC.md §C): the annotator may only be
used to build/expand self-gold if it reproduces HUMAN GT above the user-set thresholds.
Certification is done ONLY against the external human-annotated anchors (CTI-ATE 60,
CTI-TAA 50) — NEVER against any LLM-generated data (CLAUDE.md §2.4).

Gates (defaults are the SPEC §C suggestions; override on the CLI):
  - technique: CTI-ATE Micro-F1 (technique level) >= --tech-threshold   (default 0.65)
  - actor:     CTI-TAA Plausible Acc            >= --actor-threshold     (default 0.50)

Platform stratification: CTI-ATE mixes Enterprise (47) and Mobile (13) ATT&CK, but the
ingested corpus is Enterprise-only. The technique gate is therefore scored on the
ENTERPRISE subset (fair to the corpus); the Mobile subset is reported separately as
out-of-corpus and is NOT gated.

LLM provider: --provider groq uses the production model (Groq llama-3.3-70b-versatile);
--provider deepseek uses DeepSeek (OpenAI-compatible) — chosen when Groq's free-tier
daily-token cap blocks a full run. NOTE: certifying DeepSeek certifies THAT annotator;
Phase D self-gold generation must then use the same certified annotator.

Calls a REAL LLM (no mock). If the LLM is unavailable, certification ABORTS rather than
scoring a fabricated answer (CLAUDE.md §2.6).

Usage:
    python scripts/certify_annotator.py --provider deepseek
    python scripts/certify_annotator.py --provider groq --max-records 3   # smoke
"""

from __future__ import annotations

# E402: imports intentionally follow sys.path.insert + load_dotenv (run-without-install pattern).
# ruff: noqa: E402
import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti._logging import configure_logging, get_logger
from rag_cti.config import get_settings
from rag_cti.embeddings.embedder import Embedder
from rag_cti.evaluation.set_metrics import SetPRF, micro_f1, normalize_set
from rag_cti.evaluation.taa_metrics import (
    TAAResult,
    load_actor_dicts,
    score_taa,
    threat_actor_connection,
)
from rag_cti.evaluation.techniquerag import parse_gold_ids
from rag_cti.generation.client import build_llm_client
from rag_cti.generation.generator import DEFAULT_CANDIDATE_K, Generator
from rag_cti.generation.llm_router import LLMRouter
from rag_cti.retrieval import build_pipeline
from rag_cti.retrieval.bm25 import BM25SparseEncoder
from rag_cti.store.qdrant_store import QdrantStore

logger = get_logger(__name__)

_CTIBENCH = Path(__file__).parent.parent / "data" / "eval" / "ctibench"
_VOCAB_PATH = Path(__file__).parent.parent / "data" / "sparse_vocab.json"
_OUT_DIR = Path(__file__).parent.parent / "data" / "eval"

DEFAULT_TECH_THRESHOLD = 0.65
DEFAULT_ACTOR_THRESHOLD = 0.50  # plausible accuracy
RETRIEVE_K = 40  # retrieve top-40, then annotate_techniques injects top-10 (SPEC §B.1)

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"


class _FixedRouter:
    """Minimal LLMRouter substitute: returns one model for every task.

    Used when the annotator runs on a provider/model other than the settings-derived
    Groq model (e.g. DeepSeek). Generator only calls .model_for(task) -> str.
    """

    def __init__(self, model: str) -> None:
        self._model = model

    def model_for(self, task: object) -> str:
        return self._model


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_ate(max_records: int | None) -> list[tuple[str, list[str], str]]:
    """Return [(description, gold_technique_ids, platform)] from CTI-ATE."""
    rows: list[tuple[str, list[str], str]] = []
    with open(_CTIBENCH / "cti-ate.tsv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            desc = (row["Description"] or "").strip()
            gold = parse_gold_ids(row["GT"] or "")
            platform = (row.get("Platform") or "").strip()
            if desc and gold:
                rows.append((desc, gold, platform))
    return rows[:max_records] if max_records else rows


def load_taa(max_records: int | None) -> list[tuple[str, str]]:
    """Return [(text, gt_actor)] by row-aligning CTI-TAA Text with responses GT."""
    with open(_CTIBENCH / "cti-taa.tsv", encoding="utf-8") as fh:
        texts = [(r["Text"] or "").strip() for r in csv.DictReader(fh, delimiter="\t")]
    with open(_CTIBENCH / "cti-taa-responses.tsv", encoding="utf-8") as fh:
        gts = [(r["GT"] or "").strip() for r in csv.DictReader(fh, delimiter="\t")]
    if len(texts) != len(gts):
        raise RuntimeError(f"CTI-TAA misalignment: {len(texts)} texts vs {len(gts)} GTs")
    rows = list(zip(texts, gts, strict=True))
    return rows[:max_records] if max_records else rows


# ---------------------------------------------------------------------------
# Certification passes (REAL LLM)
# ---------------------------------------------------------------------------

def certify_techniques(
    gen: Generator, pipeline: Any, rows: list[tuple[str, list[str], str]], candidate_k: int
) -> list[dict[str, Any]]:
    """Retrieve + annotate each row; return per-row details (gold/pred/platform)."""
    details: list[dict[str, Any]] = []
    for i, (desc, gold, platform) in enumerate(rows, start=1):
        qr = pipeline.run(desc, top_k=RETRIEVE_K)
        pred = gen.annotate_techniques(desc, qr, candidate_k=candidate_k)  # raises on LLM failure
        g_norm = sorted(normalize_set(gold, "technique"))
        p_norm = sorted(normalize_set(pred, "technique"))
        details.append({
            "i": i, "platform": platform, "gold": gold, "pred": pred,
            "gold_tech": g_norm, "pred_tech": p_norm,
            "tp": len(set(g_norm) & set(p_norm)),
        })
        print(f"  [ATE {i}/{len(rows)}] platform={platform} gold={g_norm} pred={p_norm}", flush=True)
    return details


def prf_for_platform(details: list[dict[str, Any]], platform: str | None) -> SetPRF:
    """Micro-F1(tech) over the subset matching `platform` (case-insensitive); None = all."""
    sel = [d for d in details if platform is None or d["platform"].lower() == platform.lower()]
    gold = [d["gold"] for d in sel]
    pred = [d["pred"] for d in sel]
    return micro_f1(gold, pred, "technique")


def certify_actors(
    gen: Generator,
    pipeline: Any,
    rows: list[tuple[str, str]],
    candidate_k: int,
    alias: dict[str, list[str]],
    related: dict[str, list[str]],
) -> tuple[TAAResult, list[dict[str, Any]]]:
    pairs: list[tuple[str, str]] = []
    details: list[dict[str, Any]] = []
    for i, (text, gt) in enumerate(rows, start=1):
        qr = pipeline.run(text, top_k=RETRIEVE_K)
        pred = gen.attribute_actor(text, qr, candidate_k=candidate_k)  # raises on LLM failure
        pairs.append((gt, pred))
        cls = threat_actor_connection(gt, pred, alias, related) if pred else "I"
        details.append({"i": i, "gt": gt, "pred": pred, "class": cls})
        print(f"  [TAA {i}/{len(rows)}] gt={gt!r} pred={pred!r} -> {cls}", flush=True)
    return score_taa(pairs, alias, related), details


# ---------------------------------------------------------------------------
# Build + run
# ---------------------------------------------------------------------------

def build_client(settings: Any, provider: str, model_override: str | None) -> tuple[Any, str]:
    """Return (llm_client, model) for the annotator. REAL provider — no mock."""
    if provider == "deepseek":
        from openai import OpenAI

        key = settings.deepseek_api_key.get_secret_value()
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY not set — cannot certify on DeepSeek")
        client = OpenAI(base_url=_DEEPSEEK_BASE_URL, api_key=key, max_retries=5, timeout=120)
        return client, (model_override or _DEEPSEEK_DEFAULT_MODEL)
    if provider == "groq":
        prov, client = build_llm_client(settings)
        if prov != "groq":
            raise RuntimeError(f"expected Groq client, got {prov}")
        return client, (model_override or settings.groq_analysis_model)
    raise RuntimeError(f"unknown provider {provider!r}")


def build(
    settings: Any, collection: str, device: str | None, provider: str, model_override: str | None
) -> tuple[Generator, Any, str]:
    store = QdrantStore(
        url=settings.qdrant_url,
        collection=collection,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )
    embedder = Embedder(model_name=settings.embedding_model, device=device)
    encoder = BM25SparseEncoder.load(_VOCAB_PATH) if _VOCAB_PATH.exists() else BM25SparseEncoder()

    client, model = build_client(settings, provider, model_override)

    # llm_client=None => HyDE OFF (inputs are full passages, not short queries);
    # production hybrid + CrossEncoder reranker stay ON.
    pipeline = build_pipeline(settings=settings, store=store, embedder=embedder, encoder=encoder, llm_client=None)
    router = LLMRouter(settings) if provider == "groq" and not model_override else _FixedRouter(model)
    gen = Generator(client=client, router=router, settings=settings)
    return gen, pipeline, model


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Certify the LLM annotator (Phase C hard gate)")
    parser.add_argument("--provider", choices=["groq", "deepseek"], default="groq")
    parser.add_argument("--model", default=None, help="Override the annotator model name")
    parser.add_argument("--max-records", type=int, default=None, help="Limit rows for a smoke test")
    parser.add_argument("--tech-threshold", type=float, default=DEFAULT_TECH_THRESHOLD)
    parser.add_argument("--actor-threshold", type=float, default=DEFAULT_ACTOR_THRESHOLD)
    parser.add_argument("--candidate-k", type=int, default=DEFAULT_CANDIDATE_K)
    parser.add_argument("--collection", default=None, help="Override qdrant collection")
    parser.add_argument("--device", default=None, help="Embedder device, e.g. cuda")
    parser.add_argument("--skip-actor", action="store_true", help="Run technique cert only")
    args = parser.parse_args()

    settings = get_settings()
    collection = args.collection or settings.qdrant_collection

    print(f"\nBuilding pipeline (collection={collection}, provider={args.provider})...", flush=True)
    gen, pipeline, model = build(settings, collection, args.device, args.provider, args.model)
    alias, related = load_actor_dicts(_CTIBENCH)

    ate_rows = load_ate(args.max_records)
    taa_rows = load_taa(args.max_records)

    print(f"\n=== Technique certification: CTI-ATE n={len(ate_rows)} ===", flush=True)
    tech_details = certify_techniques(gen, pipeline, ate_rows, args.candidate_k)
    ent_prf = prf_for_platform(tech_details, "enterprise")
    mob_prf = prf_for_platform(tech_details, "mobile")

    actor_taa: TAAResult | None = None
    actor_details: list[dict[str, Any]] = []
    if not args.skip_actor:
        print(f"\n=== Actor certification: CTI-TAA n={len(taa_rows)} ===", flush=True)
        actor_taa, actor_details = certify_actors(
            gen, pipeline, taa_rows, args.candidate_k, alias, related
        )

    _report(args, settings, collection, model, ent_prf, mob_prf, actor_taa)
    _save(args, collection, model, ent_prf, mob_prf, tech_details, actor_taa, actor_details)


def _verdict(value: float, threshold: float) -> str:
    return "PASS" if value >= threshold else "FAIL"


def _report(
    args: argparse.Namespace,
    settings: Any,
    collection: str,
    model: str,
    ent: SetPRF,
    mob: SetPRF,
    actor: TAAResult | None,
) -> None:
    tech_v = _verdict(ent.f1, args.tech_threshold)
    print("\n" + "=" * 72)
    print("PHASE C — ANNOTATOR CERTIFICATION RESULT")
    print("=" * 72)
    print(f"环境: collection={collection}, generator={model} (provider={args.provider})")
    print(f"retrieval: hybrid(alpha={settings.hybrid_alpha})+reranker, HyDE=off, candidate_k={args.candidate_k}\n")

    print("能力分项表(外部锚,独立报,绝不平均):")
    print(f"  technique 抽取 (Enterprise) | Micro-F1(tech) | CTI-ATE-ent n={ent.n} | "
          f"F1={ent.f1:.4f} P={ent.precision:.4f} R={ent.recall:.4f} "
          f"(TP={ent.tp} FP={ent.fp} FN={ent.fn}) | 论文 RAG-no-ft 0.65-0.79")
    print(f"  technique 抽取 (Mobile,out-of-corpus,NOT gated) | CTI-ATE-mob n={mob.n} | "
          f"F1={mob.f1:.4f} P={mob.precision:.4f} R={mob.recall:.4f} (TP={mob.tp} FP={mob.fp} FN={mob.fn})")
    if actor is not None:
        print(f"  actor 归因                 | correct/plaus  | CTI-TAA n={actor.n} | "
              f"correct={actor.correct_acc:.4f} plausible={actor.plausible_acc:.4f} "
              f"(C={actor.correct} P={actor.plausible} I={actor.incorrect})")

    print("\n认证结论:")
    print(f"  标注器 CTI-ATE(Enterprise) Micro-F1(tech) = {ent.f1:.4f}  "
          f"(阈值 >= {args.tech_threshold}) -> {tech_v}")
    print(f"    [Mobile out-of-corpus: F1={mob.f1:.4f} — 语料缺 Mobile 技术,仅记录不 gate]")
    if actor is not None:
        actor_v = _verdict(actor.plausible_acc, args.actor_threshold)
        print(f"  attributor CTI-TAA Plausible              = {actor.plausible_acc:.4f}  "
              f"(阈值 >= {args.actor_threshold}) -> {actor_v}  [Correct={actor.correct_acc:.4f} 供参考]")
        print(f"  -> 准许 technique 标注器生成自建 gold: {'是' if tech_v == 'PASS' else '否'}")
        print(f"  -> 准许 actor attributor 生成自建 gold: {'是' if actor_v == 'PASS' else '否'}")
    else:
        print(f"  -> 准许 technique 标注器生成自建 gold: {'是' if tech_v == 'PASS' else '否'}")

    print("\n小样本警示: CTI-ATE Enterprise n=47 / CTI-TAA n=50,置信区间宽,仅作校准锚,不支撑强声明。")
    if args.provider != "groq":
        print(f"⚠️  认证对象 = {model} (provider={args.provider}),非产品默认 Groq 模型;"
              f"若通过,Phase D 自建 gold MUST 用同一标注器。")
    if args.max_records:
        print(f"⚠️  SMOKE RUN: --max-records {args.max_records} (NOT a full certification).")
    print("=" * 72 + "\n")


def _save(
    args: argparse.Namespace,
    collection: str,
    model: str,
    ent: SetPRF,
    mob: SetPRF,
    tech_details: list[dict[str, Any]],
    actor: TAAResult | None,
    actor_details: list[dict[str, Any]],
) -> None:
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    tag = "smoke" if args.max_records else "full"

    def prf_dict(p: SetPRF) -> dict[str, Any]:
        return {"n": p.n, "micro_f1": p.f1, "precision": p.precision, "recall": p.recall,
                "tp": p.tp, "fp": p.fp, "fn": p.fn}

    record: dict[str, Any] = {
        "phase": "C",
        "timestamp_utc": stamp,
        "smoke": bool(args.max_records),
        "max_records": args.max_records,
        "collection": collection,
        "annotator_model": model,
        "provider": args.provider,
        "candidate_k": args.candidate_k,
        "retrieve_k": RETRIEVE_K,
        "thresholds": {"tech_micro_f1": args.tech_threshold, "actor_plausible": args.actor_threshold},
        "technique": {
            "gated_on": "enterprise",
            "enterprise": {**prf_dict(ent), "pass": ent.f1 >= args.tech_threshold},
            "mobile_out_of_corpus": prf_dict(mob),
            "details": tech_details,
        },
    }
    if actor is not None:
        record["actor"] = {
            "n": actor.n, "correct_acc": actor.correct_acc, "plausible_acc": actor.plausible_acc,
            "correct": actor.correct, "plausible": actor.plausible, "incorrect": actor.incorrect,
            "pass": actor.plausible_acc >= args.actor_threshold,
            "details": actor_details,
        }
    out = _OUT_DIR / f"certification_{tag}_{args.provider}_{stamp}.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved certification record: {out}", flush=True)


if __name__ == "__main__":
    main()
