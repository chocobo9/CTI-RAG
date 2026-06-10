"""Does the IOC blob dilute OTX chunk embeddings?

Background:
    99% of OTX chunks are single-chunk and mix attribution prose with the
    "Key indicators:" hash blob in ONE chunk. bge-m3 (8k ctx) embeds the whole
    thing at ingest — no truncation — so the IOC text (55-97% of the chunk by
    char) sits inside the dense vector. The reranker truncates it away; the
    dense retriever does not. This script asks whether that IOC mass moves the
    chunk's vector off its attribution topic.

Tier A (primary, no queries, no Qdrant):
    For each sampled chunk, cos(full_vec, stripped_vec) where stripped = content
    with the "Key indicators:" tail removed. Calibrated against the floor:
    cos(full_i, stripped_j) for random j != i.
      self-sim ~= 1.0      -> IOCs don't move the vector; dilution negligible.
      self-sim near floor  -> IOC text dominates; attribution signal washed out.
    Broken out by "stub" chunks (tiny attribution head) vs "rich" chunks,
    because dilution should be worst for stubs.

Tier B (--retrieval, actionable): actor-retrieval delta.
    Query = adversary name. Gold = chunks with that adversary. Measure hit@10 /
    MRR over the FULL corpus vs the STRIPPED corpus. If STRIPPED ranks gold
    higher, trimming IOCs from embedded content improves actor retrieval.
    NOTE: the adversary name also appears in content ("Attributed to X"), so
    absolute scores are leaky-optimistic — but the leak is symmetric across
    FULL and STRIPPED, so the DELTA is the honest signal.

Usage (on the box with bge-m3 cached, in the venv):
    python measure_embedding_dilution.py \
        --jsonl data/processed/otx.jsonl \
        --model BAAI/bge-m3 \
        --sample 400 --retrieval
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

IND = "Key indicators:"


def load_otx(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def strip_iocs(content: str) -> str:
    pos = content.find(IND)
    return content[:pos].rstrip() if pos != -1 else content.strip()


def pctl(v, p):
    if not v:
        return 0.0
    s = sorted(v)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--model", default="BAAI/bge-m3")
    ap.add_argument("--sample", type=int, default=400)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--stub-threshold", type=int, default=120,
                    help="stripped content shorter than this (chars) = 'stub'")
    ap.add_argument("--retrieval", action="store_true", help="run Tier B actor-retrieval delta")
    ap.add_argument("--_dry-embedder", action="store_true", help=argparse.SUPPRESS)  # logic test only
    args = ap.parse_args()

    path = Path(str(args.jsonl).strip())
    if not path.exists():
        print(f"missing: {path}  [looked in: {path.resolve()}]", file=sys.stderr)
        return 1

    rows = [r for r in load_otx(path)
            if (r.get("metadata", {}).get("adversary") or "").strip() and IND in r["content"]]
    random.seed(args.seed)
    if len(rows) > args.sample:
        rows = random.sample(rows, args.sample)
    n = len(rows)
    print(f"sampled {n} OTX chunks (with adversary label + indicator blob)\n")

    full = [r["content"] for r in rows]
    stripped = [strip_iocs(r["content"]) for r in rows]
    advs = [r["metadata"]["adversary"].strip() for r in rows]

    # --- embed ---
    if args._dry_embedder:
        import numpy as np
        def embed(texts):
            # deterministic per-text pseudo-vector keyed on length+hash, just to exercise logic
            vs = []
            for t in texts:
                rng2 = np.random.default_rng(abs(hash(t)) % (2**32))
                v = rng2.standard_normal(64)
                vs.append(v / (np.linalg.norm(v) + 1e-9))
            return np.array(vs)
    else:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("ERROR: pip install sentence-transformers (or adapt embed() to your bge-m3 call).",
                  file=sys.stderr)
            return 1
        import numpy as np
        model = SentenceTransformer(args.model.strip())
        def embed(texts):
            return model.encode(texts, normalize_embeddings=True, batch_size=32,
                                show_progress_bar=False)

    import numpy as np
    ef = np.asarray(embed(full))
    es = np.asarray(embed(stripped))

    # --- Tier A: geometry ---
    self_sim = np.sum(ef * es, axis=1)  # cos(full_i, stripped_i), vectors normalized
    # floor: full_i vs a random stripped_j
    perm = np.random.default_rng(args.seed).permutation(n)
    perm = np.where(perm == np.arange(n), (perm + 1) % n, perm)
    floor = np.sum(ef * es[perm], axis=1)

    is_stub = np.array([len(s) < args.stub_threshold for s in stripped])
    print("── Tier A: does the IOC blob move the chunk's own vector? ──")
    print(f"  cos(full, stripped)  p10/p50/p90 : "
          f"{pctl(list(self_sim),10):.3f} / {pctl(list(self_sim),50):.3f} / {pctl(list(self_sim),90):.3f}")
    print(f"  floor cos(full, other stripped) median : {pctl(list(floor),50):.3f}")
    if is_stub.any():
        print(f"  stub chunks  (attribution < {args.stub_threshold} chars, n={int(is_stub.sum())}): "
              f"self-sim median {np.median(self_sim[is_stub]):.3f}")
    if (~is_stub).any():
        print(f"  rich chunks  (n={int((~is_stub).sum())}): "
              f"self-sim median {np.median(self_sim[~is_stub]):.3f}")
    print()

    # --- Tier B: actor-retrieval delta ---
    if args.retrieval:
        # unique adversaries with >=2 chunks in sample so a gold neighbor exists
        from collections import defaultdict
        idx_by_adv = defaultdict(list)
        for i, a in enumerate(advs):
            idx_by_adv[a].append(i)
        qadvs = [a for a, ix in idx_by_adv.items() if len(ix) >= 2]
        if not qadvs:
            print("Tier B skipped: no adversary has >=2 sampled chunks.")
            return 0
        qvecs = np.asarray(embed(qadvs))

        def hit_mrr(corpus_vecs):
            hits10 = 0
            rr = 0.0
            for qi, a in enumerate(qadvs):
                gold = set(idx_by_adv[a])
                sims = corpus_vecs @ qvecs[qi]
                order = np.argsort(-sims)
                rank = next((r for r, ci in enumerate(order) if ci in gold), None)
                if rank is not None:
                    if rank < 10:
                        hits10 += 1
                    rr += 1.0 / (rank + 1)
            m = len(qadvs)
            return hits10 / m, rr / m

        f_hit, f_mrr = hit_mrr(ef)
        s_hit, s_mrr = hit_mrr(es)
        print(f"── Tier B: actor retrieval, {len(qadvs)} adversary queries ──")
        print(f"  FULL corpus     hit@10 {f_hit:.3f}  MRR {f_mrr:.3f}")
        print(f"  STRIPPED corpus hit@10 {s_hit:.3f}  MRR {s_mrr:.3f}")
        print(f"  delta (stripped - full): hit@10 {s_hit-f_hit:+.3f}  MRR {s_mrr-f_mrr:+.3f}")
        print("  (absolute scores leaky via 'Attributed to X'; the DELTA is the signal)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
