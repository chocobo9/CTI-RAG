"""Phase D — capability-split evaluation summary (four capabilities, NEVER averaged).

PROJECT_SPEC.md §2 / CLAUDE.md §5: the four capabilities are reported SEPARATELY,
each with its own metric, data split, and trust provenance. This script aggregates
the already-produced, traceable artifacts into one canonical report:

  1. technique extraction  — CERTIFIED external anchor: CTI-ATE (Enterprise) Micro-F1(tech)
                              (Phase C result + recall decomposition). Self-gold NOT built:
                              technique annotator FAILED Phase C → no technique self-gold.
  2. actor attribution     — CERTIFIED external anchor: CTI-TAA correct/plausible (Phase C PASS).
  3. heterogeneous retrieval — self query-set (v2), de-backdoored eval_attribution, set metrics.
                              Gold is LLM-generated & UNCERTIFIED → directional; pulse_id-grounded
                              categories rest on hard identifiers.
  4. generation grounding  — RAGAS faithfulness (+ context_precision/recall when reference answers
                              are supplied). Optional (needs an LLM judge) via --ragas.

It does NOT average across capabilities and does NOT fabricate any score: a capability
whose artifact is missing is reported as "not available", never as 0 or a guess.

Usage:
    python scripts/eval_capabilities.py
    python scripts/eval_capabilities.py --cert data/eval/certification_full_deepseek_*.json
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports — run-without-install pattern)
import argparse
import glob
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

_EVAL_DIR = Path(__file__).parent.parent / "data" / "eval"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def _latest(pattern: str) -> Path | None:
    matches = sorted(glob.glob(str(_EVAL_DIR / pattern)))
    return Path(matches[-1]) if matches else None


def _fmt(v: Any) -> str:
    return f"{v:.4f}" if isinstance(v, (int, float)) else str(v)


def build_summary(cert_path: Path | None) -> dict[str, Any]:
    cert = _load_json(cert_path) if cert_path else None
    recall = _load_json(_EVAL_DIR / "recall_decomposition.json")
    attribution = _load_json(_EVAL_DIR / "attribution_v3_debackdoored.json")

    capabilities: dict[str, Any] = {}

    # 1. technique extraction (certified external anchor)
    if cert and "technique" in cert:
        ent = cert["technique"]["enterprise"]
        mob = cert["technique"].get("mobile_out_of_corpus", {})
        capabilities["technique_extraction"] = {
            "metric": "Micro-F1(technique)",
            "data": f"CTI-ATE Enterprise n={ent.get('n')}",
            "score": {"micro_f1": ent.get("micro_f1"), "precision": ent.get("precision"), "recall": ent.get("recall")},
            "external_anchor": "TechniqueRAG/CTIBench RAG-no-ft 0.65-0.79",
            "gate": {"threshold": cert["thresholds"]["tech_micro_f1"], "pass": ent.get("pass")},
            "trust": "CERTIFIED external human GT (Phase C). Technique self-gold NOT generated (gate FAILED).",
            "mobile_out_of_corpus": {"micro_f1": mob.get("micro_f1"), "n": mob.get("n"),
                                     "note": "corpus is Enterprise ATT&CK only; not gated"},
            "diagnosis": recall.get("conclusion") if recall else None,
        }
    else:
        capabilities["technique_extraction"] = {"status": "NOT AVAILABLE — no certification record"}

    # 2. actor attribution (certified external anchor)
    if cert and "actor" in cert:
        a = cert["actor"]
        capabilities["actor_attribution"] = {
            "metric": "correct / plausible accuracy (faithful cti-bench scorer)",
            "data": f"CTI-TAA n={a.get('n')}",
            "score": {"correct_acc": a.get("correct_acc"), "plausible_acc": a.get("plausible_acc"),
                      "C": a.get("correct"), "P": a.get("plausible"), "I": a.get("incorrect")},
            "external_anchor": "cti-bench published models (e.g. ChatGPT-3.5 ~0.44/0.62)",
            "gate": {"threshold": cert["thresholds"]["actor_plausible"], "pass": a.get("pass")},
            "trust": "CERTIFIED external human GT (Phase C PASS). Actor self-gold not generated (per user).",
        }
    else:
        capabilities["actor_attribution"] = {"status": "NOT AVAILABLE — no certification record"}

    # 3. heterogeneous retrieval (self query-set, de-backdoored)
    if attribution and attribution.get("results"):
        res = attribution["results"][0]
        capabilities["heterogeneous_retrieval"] = {
            "metric": "set P/R/F1@k (multi-label) + pulse Recall@k + hit@k (single-target)",
            "data": f"self query-set {attribution.get('query_set')}",
            "by_category_hit": {c: m.get("hit_at_k") for c, m in res.get("by_category", {}).items()},
            "set_metrics": res.get("set_metrics"),
            "external_anchor": "none",
            "trust": "Self-set gold is LLM-generated & UNCERTIFIED (directional). otx_actor backdoor "
                     "REMOVED (now pulse_id-only). pulse_id categories rest on hard identifiers. "
                     "relationship_* gold uncertified (technique gate failed) — directional only.",
        }
    else:
        capabilities["heterogeneous_retrieval"] = {
            "status": "NOT AVAILABLE — run scripts/eval_attribution.py --output data/eval/attribution_v3_debackdoored.json"
        }

    # 4. generation grounding (RAGAS) — populated by --ragas, else marked pending
    capabilities["generation_grounding"] = {
        "status": "NOT RUN — run with --ragas (needs LLM judge + reference answers); "
                  "metrics available: faithfulness, answer_relevancy, context_precision, context_recall"
    }

    return {
        "phase": "D (reduced — technique self-gold blocked by Phase C gate)",
        "generated_utc": datetime.now(UTC).isoformat(),
        "cert_record": str(cert_path) if cert_path else None,
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
        print(f"    score : F1={_fmt(s['micro_f1'])} P={_fmt(s['precision'])} R={_fmt(s['recall'])}")
        print(f"    gate  : >= {tech['gate']['threshold']} -> {'PASS' if tech['gate']['pass'] else 'FAIL'}")
        print(f"    anchor: {tech['external_anchor']}")
        print(f"    mobile (out-of-corpus, not gated): F1={_fmt(tech['mobile_out_of_corpus']['micro_f1'])}")
        print(f"    trust : {tech['trust']}")
    else:
        print(f"    {tech['status']}")

    actor = caps["actor_attribution"]
    print("\n[2] actor attribution")
    if "score" in actor:
        s = actor["score"]
        print(f"    metric: {actor['metric']} | {actor['data']}")
        print(f"    score : correct={_fmt(s['correct_acc'])} plausible={_fmt(s['plausible_acc'])} (C={s['C']} P={s['P']} I={s['I']})")
        print(f"    gate  : plausible >= {actor['gate']['threshold']} -> {'PASS' if actor['gate']['pass'] else 'FAIL'}")
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

    print("\n[4] generation grounding")
    print(f"    {caps['generation_grounding']['status']}")
    print("\n" + "=" * 78)
    print("Note: scores are NEVER averaged across capabilities. Each rests on its own gold/anchor.")
    print("=" * 78 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Capability-split eval summary (never averaged)")
    parser.add_argument("--cert", default=None, help="Path to a certification_full_*.json record")
    parser.add_argument("--output", default=str(_EVAL_DIR / "capabilities_summary.json"))
    args = parser.parse_args()

    cert_path = Path(args.cert) if args.cert else _latest("certification_full_*.json")
    summary = build_summary(cert_path)
    print_summary(summary)
    Path(args.output).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved capability summary: {args.output}")


if __name__ == "__main__":
    main()
