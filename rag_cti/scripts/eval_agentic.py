"""Compare the agentic answer loop vs single-shot RAG on query_set_v3.

Capability-split, reported side by side, NEVER averaged:

  - Sufficiency / evidence recall (headline): on ``relationship_direct`` (deterministic
    ATT&CK technique gold), the set-Recall/P/F1 of each path's gathered technique
    evidence vs gold. The agentic path enumerates via the graph (``collected_facts``),
    so this is where its completeness should show over a single top-k pass.
  - Grounding / faithfulness (optional ``--ragas``): RAGAS faithfulness of each path's
    answers, DeepSeek judge.
  - Cost: the agentic iteration_count / tokens_used / stop_reason distribution — the
    data to set the operating point (``agentic_max_iterations``), measured not pinned.

Real LLM, no mock (CLAUDE.md S2.6). The agentic path is slow; keep ``--per-category``
small and set ``AGENTIC_MAX_ITERATIONS=1`` for quick smoke runs.

Usage:
    python scripts/eval_agentic.py --categories relationship_direct --per-category 3
    AGENTIC_MAX_ITERATIONS=1 python scripts/eval_agentic.py --per-category 2
    python scripts/eval_agentic.py --ragas --categories relationship_direct semantic
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports - run-without-install pattern)
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))  # sibling eval_attribution import

from dotenv import load_dotenv

load_dotenv()

from eval_attribution import QueryRecord, load_query_set

from rag_cti._logging import configure_logging, get_logger
from rag_cti.evaluation.set_metrics import micro_f1
from rag_cti.knowledge.agentic_state import AgenticAnswer
from rag_cti.types import GeneratedAnswer

logger = get_logger(__name__)


def _singleshot_techniques(answer: GeneratedAnswer) -> list[str]:
    """ATT&CK ids carried by the single-shot retrieved chunks' metadata."""
    out: list[str] = []
    for r in answer.query_result.results:
        aid = r.document.metadata.get("attack_id")
        if aid:
            out.append(str(aid))
    return out


def _agentic_techniques(answer: AgenticAnswer) -> list[str]:
    """ATT&CK ids the agentic ANSWER actually claims — the techniques of the facts/chunks
    it CITED, not the full gathered set. Measuring all collected_facts conflates gathering
    breadth (good for recall) with answer precision; the answer cites far fewer than it
    gathers, so this reflects the answer, not the enumeration."""
    cited = set(answer.cited_ids)
    out: list[str] = []
    for fact in answer.collected_facts:
        if fact.fact_id in cited and fact.object_type == "technique":
            out.append(fact.object_id.removeprefix("technique_"))
    for r in answer.query_result.results:
        if r.document.id in cited:
            aid = r.document.metadata.get("attack_id")
            if aid:
                out.append(str(aid))
    return out


def _gathered_techniques(answer: AgenticAnswer) -> list[str]:
    """ATT&CK ids the path GATHERED (all collected technique facts), regardless of whether
    the final answer cited them. This isolates ENUMERATION COMPLETENESS (did parallel
    branches collect more?) from synthesis-citation behaviour — the cited-technique metric
    is unreliable on prose comparison answers (bimodal/zero), so gathered-recall is the
    cleaner read on whether the multi-agent mechanism actually works."""
    return [
        fact.object_id.removeprefix("technique_")
        for fact in answer.collected_facts
        if fact.object_type == "technique"
    ]


def _to_generated(answer: AgenticAnswer) -> GeneratedAnswer:
    """AgenticAnswer -> GeneratedAnswer so RAGAS (which reads query/answer/contexts)
    scores both paths through the same harness."""
    return GeneratedAnswer(
        query=answer.query,
        answer=answer.answer,
        cited_chunk_ids=list(answer.cited_ids),
        query_result=answer.query_result,
        generation_ms=0.0,
        model="agentic",
    )


def sample_queries(
    records: list[QueryRecord], categories: list[str], per_category: int
) -> list[QueryRecord]:
    by_cat: dict[str, list[QueryRecord]] = defaultdict(list)
    for record in records:
        by_cat[record.category].append(record)
    chosen: list[QueryRecord] = []
    for category in categories:
        chosen.extend(by_cat.get(category, [])[:per_category])
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic vs single-shot RAG comparison")
    parser.add_argument("--query-set", default="data/eval/query_set_v3.jsonl")
    parser.add_argument("--output", default="data/eval/agentic_vs_singleshot.json")
    parser.add_argument("--categories", nargs="+", default=["relationship_direct"])
    parser.add_argument("--per-category", type=int, default=3)
    parser.add_argument("--ragas", action="store_true", help="also run RAGAS faithfulness (slow)")
    parser.add_argument(
        "--supervised",
        action="store_true",
        help="also run the multi-agent supervisor arm (compound queries; expensive)",
    )
    args = parser.parse_args()

    configure_logging("INFO")

    import rag_cti
    from rag_cti.config import get_settings

    settings = get_settings()
    records = load_query_set(Path(args.query_set))
    chosen = sample_queries(records, args.categories, args.per_category)
    print(
        f"Running {len(chosen)} queries across {args.categories} "
        f"(per_category={args.per_category}); collection={settings.qdrant_collection} "
        f"agentic_max_iterations={settings.agentic_max_iterations}",
        flush=True,
    )

    # Categories whose gold is a multi-label ATT&CK technique set scored with set-Micro-F1.
    gold_scored = {"relationship_direct", "compound"}

    per_query: list[dict[str, object]] = []
    single_answers: list[GeneratedAnswer] = []
    agentic_answers: list[AgenticAnswer] = []
    supervised_answers: list[AgenticAnswer] = []
    # Per-category gold/pred so a mixed run (e.g. compound + relationship_direct for the
    # no-regression check) is reported side by side, never averaged across categories.
    gold_by_cat: dict[str, list[list[str]]] = defaultdict(list)
    single_by_cat: dict[str, list[list[str]]] = defaultdict(list)
    agentic_by_cat: dict[str, list[list[str]]] = defaultdict(list)
    supervised_by_cat: dict[str, list[list[str]]] = defaultdict(list)
    # gathered-technique sets (enumeration completeness, decoupled from citation)
    agentic_gath_by_cat: dict[str, list[list[str]]] = defaultdict(list)
    supervised_gath_by_cat: dict[str, list[list[str]]] = defaultdict(list)

    for i, rec in enumerate(chosen):
        print(f"[{i + 1}/{len(chosen)}] {rec.category}: {rec.query[:60]}", flush=True)
        single = rag_cti.answer(rec.query)
        agentic = rag_cti.agentic_answer(rec.query)
        single_answers.append(single)
        agentic_answers.append(agentic)
        supervised = rag_cti.supervised_answer(rec.query) if args.supervised else None
        if supervised is not None:
            supervised_answers.append(supervised)

        entry: dict[str, object] = {
            "query_id": rec.query_id,
            "category": rec.category,
            "query": rec.query,
            "single": {
                "answer_len": len(single.answer),
                "n_chunks": len(single.query_result.results),
            },
            "agentic": {
                "answer_len": len(agentic.answer),
                "iterations": agentic.iteration_count,
                "tokens": agentic.tokens_used,
                "stop": agentic.stop_reason,
                "n_facts": len(agentic.collected_facts),
                "dropped_citations": agentic.dropped_citation_count,
            },
        }
        if supervised is not None:
            entry["supervised"] = {
                "answer_len": len(supervised.answer),
                "decomposed": supervised.decomposed,
                "branches": supervised.branch_count,
                "tokens": supervised.tokens_used,
                "stop": supervised.stop_reason,
                "n_facts": len(supervised.collected_facts),
                "dropped_citations": supervised.dropped_citation_count,
            }

        if rec.category in gold_scored and rec.gold_attack_ids:
            single_tech = _singleshot_techniques(single)
            agentic_tech = _agentic_techniques(agentic)
            gold_by_cat[rec.category].append(rec.gold_attack_ids)
            single_by_cat[rec.category].append(single_tech)
            agentic_by_cat[rec.category].append(agentic_tech)
            agentic_gath_by_cat[rec.category].append(_gathered_techniques(agentic))
            recall_eval: dict[str, object] = {
                "gold_n": len(set(rec.gold_attack_ids)),
                "single_tech_n": len(set(single_tech)),
                "agentic_tech_n": len(set(agentic_tech)),
                "agentic_gathered_n": len(set(_gathered_techniques(agentic))),
            }
            if supervised is not None:
                supervised_tech = _agentic_techniques(supervised)
                supervised_by_cat[rec.category].append(supervised_tech)
                supervised_gath_by_cat[rec.category].append(_gathered_techniques(supervised))
                recall_eval["supervised_tech_n"] = len(set(supervised_tech))
                recall_eval["supervised_gathered_n"] = len(set(_gathered_techniques(supervised)))
            entry["recall_eval"] = recall_eval
        per_query.append(entry)

    summary: dict[str, object] = {"n": len(chosen), "categories": args.categories}

    def _prf(gold: list[list[str]], pred: list[list[str]]) -> dict[str, float]:
        prf = micro_f1(gold, pred, level="technique")
        return {"P": round(prf.precision, 4), "R": round(prf.recall, 4), "F1": round(prf.f1, 4)}

    recall_by_cat: dict[str, object] = {}
    for cat, golds in gold_by_cat.items():
        cat_block: dict[str, object] = {
            "n": len(golds),
            "single_shot": _prf(golds, single_by_cat[cat]),
            "agentic": _prf(golds, agentic_by_cat[cat]),
        }
        if supervised_by_cat[cat]:
            cat_block["supervised"] = _prf(golds, supervised_by_cat[cat])
        recall_by_cat[cat] = cat_block
    if recall_by_cat:
        summary["recall_by_category"] = recall_by_cat

    # Gathered-recall (enumeration completeness, decoupled from citation) — the clean read
    # on whether the multi-agent mechanism actually collects more, when the cited metric is
    # unreliable on prose comparison answers.
    gathered_by_cat: dict[str, object] = {}
    for cat, golds in gold_by_cat.items():
        block: dict[str, object] = {
            "n": len(golds),
            "agentic": _prf(golds, agentic_gath_by_cat[cat]),
        }
        if supervised_gath_by_cat[cat]:
            block["supervised"] = _prf(golds, supervised_gath_by_cat[cat])
        gathered_by_cat[cat] = block
    if gathered_by_cat:
        summary["gathered_recall_by_category"] = gathered_by_cat

    summary["agentic_cost"] = {
        "iterations": dict(Counter(a.iteration_count for a in agentic_answers)),
        "stop_reason": dict(Counter(a.stop_reason for a in agentic_answers)),
        "tokens_mean": (
            round(sum(a.tokens_used for a in agentic_answers) / len(agentic_answers))
            if agentic_answers
            else 0
        ),
    }
    if supervised_answers:
        summary["supervised_cost"] = {
            "decomposed": dict(Counter(a.decomposed for a in supervised_answers)),
            "branches": dict(Counter(a.branch_count for a in supervised_answers)),
            "stop_reason": dict(Counter(a.stop_reason for a in supervised_answers)),
            "tokens_mean": round(
                sum(a.tokens_used for a in supervised_answers) / len(supervised_answers)
            ),
        }

    if args.ragas:
        from rag_cti.evaluation.ragas_eval import run_ragas_eval

        print("Running RAGAS faithfulness (single-shot)...", flush=True)
        single_ragas = run_ragas_eval(single_answers, config="single_shot", settings=settings)
        print("Running RAGAS faithfulness (agentic)...", flush=True)
        agentic_ragas = run_ragas_eval(
            [_to_generated(a) for a in agentic_answers], config="agentic", settings=settings
        )
        faithfulness: dict[str, float] = {
            "single_shot": round(single_ragas.faithfulness, 4),
            "agentic": round(agentic_ragas.faithfulness, 4),
        }
        if supervised_answers:
            print("Running RAGAS faithfulness (supervised)...", flush=True)
            supervised_ragas = run_ragas_eval(
                [_to_generated(a) for a in supervised_answers],
                config="supervised",
                settings=settings,
            )
            faithfulness["supervised"] = round(supervised_ragas.faithfulness, 4)
        summary["faithfulness"] = faithfulness

    print("\n" + json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "summary": summary,
                "per_query": per_query,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved -> {output_path}", flush=True)


if __name__ == "__main__":
    main()
