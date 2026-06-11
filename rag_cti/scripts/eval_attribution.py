"""Evaluate retrieval on query_set_v2.jsonl with stable-identifier matching.

Usage:
    python scripts/eval_attribution.py
    python scripts/eval_attribution.py --collection cti_chunks_v2
    python scripts/eval_attribution.py --query-set data/eval/query_set_v2.jsonl
    python scripts/eval_attribution.py --config hybrid --k 1 --k 5 --k 10

Matching logic (no chunk_id dependency):
  - gold_attack_ids: chunk metadata.attack_id matches any gold ID
  - gold_pulse_id:   chunk metadata.pulse_id matches (sole criterion for
                     otx_actor — the old actor_in_content backdoor was removed:
                     any chunk merely mentioning the actor counted as a hit)
  - gold_malware:    malware name appears in chunk content
  - gold_sources:    chunk source tag matches

Reports hit@k/MRR for single-target categories and set-based P/R/F1@k /
Recall@k for multi-label categories, grouped by category.
"""

from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports - run-without-install pattern)
import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from rag_cti._logging import configure_logging, get_logger
from rag_cti.bootstrap import build_eval_pipeline, build_retrieval_stack
from rag_cti.config import get_settings
from rag_cti.evaluation.set_metrics import SetPRF, micro_prf_at_k
from rag_cti.generation.client import build_llm_client

# Categories whose gold is a multi-label ATT&CK technique set → scored with
# set-based P/R/F1@k (SPEC §M), NOT hit@k/MRR. relationship_direct gold is now
# DETERMINISTIC (ATT&CK graph traversal — see query_set_v3 gold_provenance), not
# LLM-guessed; relationship_reverse still has single-id LLM gold (directional).
# The Phase C technique gate PASSED (CTI-ATE Micro-F1 0.67 >= 0.65).
_ATTACK_SET_CATEGORIES = ("precise", "semantic", "relationship_direct", "relationship_reverse")
# Single-target categories keep hit@k/MRR (SPEC §M).
_SINGLE_TARGET_CATEGORIES = ("otx_actor",)
# pulse-list categories → Recall@k over pulse_ids.
_PULSE_SET_CATEGORIES = ("otx_malware",)

logger = get_logger(__name__)


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
            records.append(
                QueryRecord(
                    query_id=obj["query_id"],
                    query=obj["query"],
                    category=obj["category"],
                    gold_attack_ids=obj.get("gold_attack_ids") or [],
                    gold_sources=obj.get("gold_sources") or [],
                    gold_actor=obj.get("gold_actor"),
                    gold_pulse_ids=_normalize_pulse_ids(obj.get("gold_pulse_id")),
                    gold_malware=obj.get("gold_malware"),
                    notes=obj.get("notes", ""),
                )
            )
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

    if record.category in ("relationship_direct", "relationship_reverse"):
        chunk_attack = doc.metadata.get("attack_id", "")
        if not chunk_attack:
            return False
        attack_ok = any(_attack_id_match(str(chunk_attack), gid) for gid in record.gold_attack_ids)
        actor_ok = record.gold_actor and record.gold_actor.lower() in doc.content.lower()
        return attack_ok and actor_ok

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

    # NOTE (Phase D, SPEC §D.1): the `actor_in_content` backdoor was REMOVED here.
    # Previously any chunk whose content merely mentioned record.gold_actor counted
    # as a hit, inflating otx_actor toward 1.000. otx_actor now matches ONLY on the
    # hard pulse_id identifier (handled above). Do NOT reintroduce a content
    # substring match for actor names.

    # fuzzy unification (SPEC §D.1): a fuzzy query has gold_attack_ids and/or
    # gold_sources. attack_id is matched above; here we allow the source fallback
    # for fuzzy/source-only queries. This is the single, explicit fuzzy criterion.
    if not record.gold_attack_ids and not record.gold_pulse_ids and not record.gold_malware:
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
        1.0 / math.log2(i + 1) for i, r in enumerate(results[:k], start=1) if is_hit(r, record)
    )
    idcg = 1.0 / math.log2(2)
    return round(dcg / idcg, 4) if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Set-based metrics for multi-label categories (SPEC §M / §D.1).
# These use set_metrics (normalize to T#### then EXACT set ops) — deliberately
# NOT the parent/child wildcard _attack_id_match used by hit@k. They replace the
# metric-mismatch (hit@k masquerading for multi-label) flagged in the eval audit.
# ---------------------------------------------------------------------------


def _ranked_attack_ids(results: list, k: int) -> list[str]:
    """attack_ids of the top-k results in rank order (blanks dropped)."""
    out: list[str] = []
    for r in results[:k]:
        aid = r.document.metadata.get("attack_id")  # type: ignore[attr-defined]
        if aid:
            out.append(str(aid))
    return out


def _ranked_pulse_ids(results: list, k: int) -> list[str]:
    out: list[str] = []
    for r in results[:k]:
        pid = r.document.metadata.get("pulse_id")  # type: ignore[attr-defined]
        if pid:
            out.append(str(pid))
    return out


def _pulse_recall_at_k(
    ranked_per_query: list[list[str]], gold_per_query: list[list[str]], k_values: tuple[int, ...]
) -> dict[int, float]:
    """Micro Recall@k over pulse_id sets: ΣTP / Σ|gold|."""
    out: dict[int, float] = {}
    for k in k_values:
        tp = denom = 0
        for ranked, gold in zip(ranked_per_query, gold_per_query, strict=True):
            g = set(gold)
            tp += len(set(ranked[:k]) & g)
            denom += len(g)
        out[k] = round(tp / denom, 4) if denom else 0.0
    return out


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
    # Collected for set-based metrics, keyed by category.
    attack_ranked: dict[str, list[list[str]]] = defaultdict(list)
    attack_gold: dict[str, list[list[str]]] = defaultdict(list)
    pulse_ranked: dict[str, list[list[str]]] = defaultdict(list)
    pulse_gold: dict[str, list[list[str]]] = defaultdict(list)

    for i, rec in enumerate(records):
        results = pipeline.run(rec.query, top_k=max_k).results  # type: ignore[attr-defined]

        cat = rec.category
        if cats[cat].hits is None:
            cats[cat].init_k(k_values)
        cm = cats[cat]
        cm.n += 1
        overall.n += 1

        if cat in _ATTACK_SET_CATEGORIES and rec.gold_attack_ids:
            attack_ranked[cat].append(_ranked_attack_ids(results, max_k))
            attack_gold[cat].append(rec.gold_attack_ids)
        if cat in _PULSE_SET_CATEGORIES and rec.gold_pulse_ids:
            pulse_ranked[cat].append(_ranked_pulse_ids(results, max_k))
            pulse_gold[cat].append(rec.gold_pulse_ids)

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

        per_query.append(
            {
                "query_id": rec.query_id,
                "query": rec.query,
                "category": cat,
                "hit_at_k": {str(k): v for k, v in q_hits.items()},
                "rr": round(rr, 4),
                "target_rank": round(1.0 / rr) if rr > 0 else None,
            }
        )

        if (i + 1) % 10 == 0:
            logger.info("eval progress", done=i + 1, total=len(records))

    # Set-based metrics for multi-label categories (technique-level, exact).
    set_metrics: dict[str, dict[str, object]] = {}
    for cat in attack_ranked:
        prf: dict[int, SetPRF] = micro_prf_at_k(
            attack_ranked[cat], attack_gold[cat], k_values=k_values, level="technique"
        )
        set_metrics[cat] = {
            "metric": "attack_set_prf@k(technique)",
            "n": len(attack_ranked[cat]),
            "prf_at_k": {
                k: {
                    "P": round(prf[k].precision, 4),
                    "R": round(prf[k].recall, 4),
                    "F1": round(prf[k].f1, 4),
                }
                for k in k_values
            },
        }
    for cat in pulse_ranked:
        rec_at_k = _pulse_recall_at_k(pulse_ranked[cat], pulse_gold[cat], k_values)
        set_metrics[cat] = {
            "metric": "pulse_recall@k",
            "n": len(pulse_ranked[cat]),
            "recall_at_k": rec_at_k,
        }

    return {
        "config": config_name,
        "k_values": list(k_values),
        "overall": overall.report(k_values),
        "by_category": {c: m.report(k_values) for c, m in sorted(cats.items())},
        "set_metrics": set_metrics,
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

    set_metrics = result.get("set_metrics") or {}
    if set_metrics:
        print(
            "\nSet-based metrics (multi-label categories — SPEC §M; normalize+exact, NOT wildcard):"
        )
        for cat in sorted(set_metrics):
            sm = set_metrics[cat]
            if sm["metric"].startswith("attack_set_prf"):
                parts = " ".join(
                    f"@{k}:P{v['P']:.3f}/R{v['R']:.3f}/F1{v['F1']:.3f}"
                    for k, v in sm["prf_at_k"].items()
                )
                if cat == "relationship_direct":
                    note = "  [deterministic ATT&CK-graph gold]"
                elif cat == "relationship_reverse":
                    note = "  [single-id LLM gold, directional]"
                else:
                    note = "  [self-set LLM gold, directional]"
                print(f"  {cat:<22} (n={sm['n']}) {parts}{note}")
            else:
                parts = " ".join(f"@{k}:R{v:.3f}" for k, v in sm["recall_at_k"].items())
                print(f"  {cat:<22} (n={sm['n']}) pulse Recall {parts}  [pulse_id-grounded]")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval with stable-identifier matching"
    )
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
    print(
        f"Loaded {len(records)} queries: "
        + ", ".join(f"{c}={n}" for c, n in sorted(cat_counts.items()))
    )

    settings = get_settings()
    stack = build_retrieval_stack(settings, collection=args.collection, device=args.device)
    coll = stack.collection
    llm_provider, llm_client = build_llm_client(settings)

    all_results: list[dict] = []

    for cfg in configs:
        print(f"\nRunning config: {cfg} ...")
        pipeline = build_eval_pipeline(
            stack, settings, cfg, llm_client=llm_client, llm_provider=llm_provider
        )
        result = run_eval(records, pipeline, k_values, cfg)
        all_results.append(result)
        print_report(result, k_values)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "query_set": args.query_set,
        "collection": coll,
        "results": all_results,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved -> {output_path}")


if __name__ == "__main__":
    main()
