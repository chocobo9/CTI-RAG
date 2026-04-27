"""Metrics loading and rendering for the `rag-cti metrics` command.

Pure functions only — no Typer dependency so they are testable in isolation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

FUZZY_HIT10_THRESHOLD = 0.60
OVERALL_HIT10_THRESHOLD = 0.70

_CATEGORIES = ("precise", "semantic", "fuzzy")


@dataclass(frozen=True)
class Thresholds:
    fuzzy_hit10: float = FUZZY_HIT10_THRESHOLD
    overall_hit10: float = OVERALL_HIT10_THRESHOLD


_DEFAULT_THRESHOLDS = Thresholds()


def load_results(path: Path) -> dict:  # type: ignore[type-arg]
    """Load retrieval_results.json produced by `rag-cti eval retrieval`.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if the file is not valid JSON or missing required keys.
    """
    if not path.exists():
        raise FileNotFoundError(f"Results file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if "results" not in data:
        raise ValueError(f"Missing 'results' key in {path}")
    return data  # type: ignore[return-value]


def check_thresholds(
    data: dict,  # type: ignore[type-arg]
    thresholds: Thresholds = _DEFAULT_THRESHOLDS,
) -> list[str]:
    """Return warning strings for any threshold violations across all configs.

    Returns an empty list when all thresholds are met.
    """
    warnings: list[str] = []
    for result in data.get("results", []):
        cfg = result.get("config", "?")
        overall = result.get("overall", {})
        top_k = overall.get("top_k", {})
        hit10 = top_k.get(10) or top_k.get("10", 0.0)
        if hit10 < thresholds.overall_hit10:
            warnings.append(
                f"[{cfg}] overall Hit@10={hit10:.4f} < threshold {thresholds.overall_hit10:.2f}"
            )
        by_cat = result.get("by_category", {})
        fuzzy = by_cat.get("fuzzy", {})
        fuzzy_top_k = fuzzy.get("top_k", {})
        fuzzy_hit10 = fuzzy_top_k.get(10) or fuzzy_top_k.get("10", 0.0)
        if fuzzy_hit10 < thresholds.fuzzy_hit10:
            warnings.append(
                f"[{cfg}] fuzzy Hit@10={fuzzy_hit10:.4f} < threshold {thresholds.fuzzy_hit10:.2f}"
            )
    return warnings


def render_summary_table(data: dict, console: object) -> None:  # type: ignore[type-arg]
    """Render per-category Rich tables to console.

    Prints four tables: overall, precise, semantic, fuzzy.
    Falls back to plain print if Rich is unavailable.
    """
    try:
        from rich.table import Table

        k_values: list[int] = data.get("k_values", [1, 5, 10])

        for cat in ("overall", *_CATEGORIES):
            t = Table(title=f"Retrieval Metrics — {cat.upper()}", show_lines=True)
            t.add_column("Config", style="cyan")
            for k in k_values:
                t.add_column(f"Hit@{k}", justify="right")
            t.add_column("MRR", justify="right")
            for k in k_values:
                t.add_column(f"nDCG@{k}", justify="right")
            t.add_column("N", justify="right")

            for result in data.get("results", []):
                cfg = result.get("config", "?")
                metrics = result.get("overall", {}) if cat == "overall" else result.get("by_category", {}).get(cat)
                if not metrics:
                    continue
                top_k = metrics.get("top_k", {})
                ndcg = metrics.get("ndcg", {})
                row = [cfg]
                for k in k_values:
                    row.append(f"{top_k.get(k) or top_k.get(str(k), 0.0):.4f}")
                row.append(f"{metrics.get('mrr', 0.0):.4f}")
                for k in k_values:
                    row.append(f"{ndcg.get(k) or ndcg.get(str(k), 0.0):.4f}")
                row.append(str(metrics.get("n_queries", 0)))
                t.add_row(*row)

            console.print(t)  # type: ignore[union-attr]

    except ImportError:
        for result in data.get("results", []):
            print(f"\n=== {result.get('config', '?')} ===")
            for cat in ("overall", *_CATEGORIES):
                m = (
                    result.get("overall")
                    if cat == "overall"
                    else result.get("by_category", {}).get(cat)
                )
                if not m:
                    continue
                print(
                    f"  [{cat}] Hit@k={m.get('top_k')}  MRR={m.get('mrr')}"
                    f"  nDCG={m.get('ndcg')}  N={m.get('n_queries')}"
                )
