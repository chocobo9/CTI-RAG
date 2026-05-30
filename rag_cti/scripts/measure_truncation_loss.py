"""Tier-0 truncation-loss census.

Question this answers (no retrieval, no Qdrant needed):
    When the reranker truncates a chunk at its 512-token pair limit,
    WHAT is in the discarded tail — attribution signal, or just raw IOCs?

Why it matters:
    bge-reranker-v2-m3 truncates the (query, passage) pair to 512 tokens total.
    So the effective PASSAGE budget is 512 - query_tokens - special_tokens (~480-490).
    Any content past that point is never seen by the reranker today — already.
    The fix-or-not decision hinges on whether that lost tail carries the signal
    the query needs.

What it does NOT do:
    It does not measure retrieval hit-rate. That needs the live pipeline + query set
    and is Tier-1, only worth running if this census says the tail matters.

Usage (on the WSL box, in the rag_cti venv):
    python measure_truncation_loss.py \
        --jsonl data/processed/otx.jsonl \
        --jsonl data/processed/mitre.jsonl \
        --jsonl data/processed/pdf.jsonl \
        --reranker BAAI/bge-reranker-v2-m3 \
        --query-reserve 28

    # --query-reserve = typical query tokens + special tokens to subtract from 512.
    #   Inspect a few of your eval queries; 28 is a conservative default
    #   (~24 query tokens + ~4 specials). Pass the real value if you know it.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

# OTX content markers — copied verbatim from rebuild_otx_jsonl.py::render_otx
# (L38 / L52 / L56 / L65). If render_otx changes, update these.
OTX_ATTRIBUTION_MARKERS = ("Attributed to", "Associated malware:", "Targeted countries:")
OTX_INDICATOR_MARKER = "Key indicators:"


def load_chunks(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"  WARN {path.name}:{line_no} bad json: {exc}", file=sys.stderr)
    return rows


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100) * (len(s) - 1)))))
    return s[k]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", action="append", required=True,
                    help="processed jsonl file. Repeatable.")
    ap.add_argument("--reranker", default="BAAI/bge-reranker-v2-m3")
    ap.add_argument("--pair-limit", type=int, default=512,
                    help="reranker max pair length")
    ap.add_argument("--query-reserve", type=int, default=28,
                    help="tokens reserved for query+specials; subtracted from pair-limit")
    args = ap.parse_args()

    try:
        from transformers import AutoTokenizer
    except ImportError:
        print("ERROR: pip install transformers (and torch) in the rag_cti venv.", file=sys.stderr)
        return 1

    budget = args.pair_limit - args.query_reserve
    print(f"Reranker: {args.reranker.strip()}")
    print(f"Effective passage budget: {args.pair_limit} - {args.query_reserve} = {budget} tokens\n")

    model_id = args.reranker.strip()
    tok = AutoTokenizer.from_pretrained(model_id)

    overall_safe = 0
    overall_costly = 0

    for raw_path in args.jsonl:
        path = Path(str(raw_path).strip())
        if not path.exists():
            print(f"SKIP (missing): {path}", file=sys.stderr)
            continue
        rows = load_chunks(path)
        if not rows:
            print(f"SKIP (empty): {path}", file=sys.stderr)
            continue

        source = rows[0].get("source", path.stem)
        token_lens: list[int] = []
        over_lost: list[int] = []        # tokens discarded, for over-budget chunks
        otx_safe = 0                     # head keeps all attribution markers present in chunk
        otx_costly = 0                   # an attribution marker present in chunk falls into the tail
        otx_over = 0
        sample_tail = None

        for row in rows:
            content = row.get("content", "")
            ids = tok.encode(content, add_special_tokens=False)
            n = len(ids)
            token_lens.append(n)
            if n <= budget:
                continue

            lost = n - budget
            over_lost.append(lost)
            head_text = tok.decode(ids[:budget])
            tail_text = tok.decode(ids[budget:])
            if sample_tail is None:
                sample_tail = tail_text[:200].replace("\n", " ")

            if source == "otx":
                otx_over += 1
                present = [m for m in OTX_ATTRIBUTION_MARKERS if m in content]
                # "safe" iff every attribution marker that exists in the chunk
                # still survives in the head (only indicators / non-attribution lost)
                survives = all(m in head_text for m in present)
                if survives:
                    otx_safe += 1
                else:
                    otx_costly += 1

        n_chunks = len(token_lens)
        n_over = len(over_lost)
        print(f"── {source}  ({path.name}) ─────────────────────────────")
        print(f"  chunks                : {n_chunks}")
        print(f"  over budget (>{budget}) : {n_over}  ({100*n_over/n_chunks:.1f}%)")
        print(f"  token len p50/p90/p99 : {pct(token_lens,50):.0f} / "
              f"{pct(token_lens,90):.0f} / {pct(token_lens,99):.0f}  (max {max(token_lens)})")
        if over_lost:
            print(f"  lost-tail tokens p50/p90/max : {pct(over_lost,50):.0f} / "
                  f"{pct(over_lost,90):.0f} / {max(over_lost)}")
            print(f"  median lost as % of chunk    : "
                  f"{100*statistics.median(over_lost)/pct(token_lens,90):.0f}% (rough)")
        if source == "otx" and otx_over:
            print(f"  OTX truncation verdict:")
            print(f"    SAFE  (only IOCs/non-attribution lost) : {otx_safe}/{otx_over}")
            print(f"    COSTLY (attribution prose lost)        : {otx_costly}/{otx_over}")
            overall_safe += otx_safe
            overall_costly += otx_costly
        if sample_tail:
            print(f"  sample lost tail: …{sample_tail}…")
        print()

    if overall_safe or overall_costly:
        total = overall_safe + overall_costly
        print("══ OTX decision signal ═════════════════════════════════")
        print(f"  {overall_safe}/{total} over-budget OTX chunks lose ONLY indicators (truncation ~free)")
        print(f"  {overall_costly}/{total} lose attribution prose (truncation costly)")
        if overall_costly == 0:
            print("  → render-side indicator trim is cosmetic for rerank; deprioritize.")
        elif overall_costly < total * 0.2:
            print("  → mostly safe; fix is low-priority, cheap render trim suffices.")
        else:
            print("  → real signal loss; chunking fix is warranted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())