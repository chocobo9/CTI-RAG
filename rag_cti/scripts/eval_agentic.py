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
    """ATT&CK ids the agentic loop gathered: graph-enumerated facts (the advantage)
    PLUS any attack_id on the synthesis-context chunks."""
    out: list[str] = []
    for fact in answer.collected_facts:
        if fact.object_type == "technique":
            out.append(fact.object_id.removeprefix("technique_"))
    for r in answer.query_result.results:
        aid = r.document.metadata.get("attack_id")
        if aid:
            out.append(str(aid))
    return out


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

    per_query: list[dict[str, object]] = []
    single_answers: list[GeneratedAnswer] = []
    agentic_answers: list[AgenticAnswer] = []
    rd_gold: list[list[str]] = []
    rd_single_pred: list[list[str]] = []
    rd_agentic_pred: list[list[str]] = []

    for i, rec in enumerate(chosen):
        print(f"[{i + 1}/{len(chosen)}] {rec.category}: {rec.query[:60]}", flush=True)
        single = rag_cti.answer(rec.query)
        agentic = rag_cti.agentic_answer(rec.query)
        single_answers.append(single)
        agentic_answers.append(agentic)

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
        if rec.category == "relationship_direct" and rec.gold_attack_ids:
            single_tech = _singleshot_techniques(single)
            agentic_tech = _agentic_techniques(agentic)
            rd_gold.append(rec.gold_attack_ids)
            rd_single_pred.append(single_tech)
            rd_agentic_pred.append(agentic_tech)
            entry["recall_eval"] = {
                "gold_n": len(set(rec.gold_attack_ids)),
                "single_tech_n": len(set(single_tech)),
                "agentic_tech_n": len(set(agentic_tech)),
            }
        per_query.append(entry)

    summary: dict[str, object] = {"n": len(chosen), "categories": args.categories}

    if rd_gold:
        single_prf = micro_f1(rd_gold, rd_single_pred, level="technique")
        agentic_prf = micro_f1(rd_gold, rd_agentic_pred, level="technique")
        summary["recall_relationship_direct"] = {
            "n": len(rd_gold),
            "single_shot": {
                "P": round(single_prf.precision, 4),
                "R": round(single_prf.recall, 4),
                "F1": round(single_prf.f1, 4),
            },
            "agentic": {
                "P": round(agentic_prf.precision, 4),
                "R": round(agentic_prf.recall, 4),
                "F1": round(agentic_prf.f1, 4),
            },
        }

    summary["agentic_cost"] = {
        "iterations": dict(Counter(a.iteration_count for a in agentic_answers)),
        "stop_reason": dict(Counter(a.stop_reason for a in agentic_answers)),
        "tokens_mean": (
            round(sum(a.tokens_used for a in agentic_answers) / len(agentic_answers))
            if agentic_answers
            else 0
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
        summary["faithfulness"] = {
            "single_shot": round(single_ragas.faithfulness, 4),
            "agentic": round(agentic_ragas.faithfulness, 4),
        }

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
