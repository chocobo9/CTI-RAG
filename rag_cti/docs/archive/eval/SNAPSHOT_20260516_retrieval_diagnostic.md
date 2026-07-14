# SNAPSHOT — Retrieval Quality Diagnostic Report (2026-05-16)

> Archive category: dated Retrieval evaluation.
>
> **Status: HISTORICAL EVALUATION SNAPSHOT.** Findings describe the dated pipeline
> named below and must not be used as the current Retrieval implementation map.

**Date**: 2026-05-16
**Codebase**: CTI-RAG (`rag_cti/`)
**Scope**: Pipeline architecture audit, ground truth quality audit, HyDE ablation experiment design, RRF parameter documentation

---

## D1: Pipeline Architecture Audit

### Data Flow Diagram

```
User Query
    │
    ├──────────────────────────────┐
    │                              │
    ▼                              ▼
[HyDERetriever]           (bypass if hyde_enabled=false
    │                       OR query_tokens < hyde_min_query_tokens)
    │                              │
    │  LLM generates               │
    │  hypothetical doc             │
    │  (3-5 sentences)              │
    │                              │
    ▼                              │
 search_query =                    │
 hypothetical_doc                  │
    │                              │
    └──────────┬───────────────────┘
               │
               ▼
        [HybridRetriever]
               │
      ┌────────┴────────┐
      │  ThreadPool(2)   │
      ▼                  ▼
[DenseRetriever]   [SparseRetriever]
      │                  │
      │ BGE-M3           │ BM25 tokenize
      │ encode_one()     │ encode_query()
      │                  │
      ▼                  ▼
 Qdrant dense       Qdrant sparse
 cosine search      dot-product search
      │                  │
      │ top_k results    │ top_k results
      │ (ranked 0-based) │ (ranked 0-based)
      └────────┬─────────┘
               │
               ▼
    [reciprocal_rank_fusion]    ← SINGLE RRF (not two-layer)
     inputs: [dense_results, sparse_results]
     k=60
               │
               ▼
         fused[:top_k]
               │
               ▼
        [NoOpReranker]         ← pass-through, no reranking
               │
               ▼
          QueryResult
```

### Answers to Specific Questions

**Q: What does BGE-M3 output?**

BGE-M3 is used through `sentence-transformers` (`Embedder.encode()` at `embedder.py:78-85`, called via `encode_one()` at line 87). It produces a **single dense vector** (not 3 separate representations). The multi-representation capability (dense + sparse + colbert) that BGE-M3 supports natively is **not used**. The code calls `model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)` which returns a single normalized dense vector per text. Sparse and ColBERT representations from BGE-M3 are never extracted.

**Q: Where does the first RRF happen? What inputs does it merge?**

There is only **one RRF call**. It happens at `hybrid_retriever.py:39`:
```python
fused = reciprocal_rank_fusion([dense_results, sparse_results])
```
It merges two lists:
1. `dense_results` — BGE-M3 dense cosine search from Qdrant
2. `sparse_results` — BM25 sparse search from Qdrant

**Q: Where does the second RRF happen?**

**There is no second RRF.** The task description mentioned "Two-layer RRF" but the code implements a single RRF fusion step. The pipeline stack is: HyDE (optional) → HybridRetriever (dense + sparse → single RRF) → NoOpReranker → truncate.

**Q: Where does HyDE fit in?**

HyDE wraps the HybridRetriever (`hyde.py:51-81`). When enabled:
1. HyDE generates a hypothetical document via LLM (3-5 sentence CTI passage)
2. The hypothetical document **replaces the original query** as the search string
3. This modified string is passed to `self._base.search()` (which is HybridRetriever)
4. HybridRetriever then embeds the hypothetical doc with BGE-M3 for dense search AND tokenizes it with BM25 for sparse search

**Critical finding**: HyDE replaces the query for **both** dense and sparse retrieval. The BM25 sparse search receives the LLM-generated hypothetical document as input, not the original user query. This means BM25 keyword matching operates on LLM-hallucinated text rather than the user's actual terms.

**Q: What is the current RRF k value?**

`k=60` — hardcoded as the default parameter in `fusion.py:8`:
```python
def reciprocal_rank_fusion(result_lists, k: int = 60)
```
The HybridRetriever calls it without overriding k (`hybrid_retriever.py:39`), so the effective value is always 60.

### Architectural Issues Found

1. **BGE-M3 underutilization**: Only dense embeddings are extracted. BGE-M3's native sparse and ColBERT representations are ignored. The separate BM25 encoder reimplements sparse retrieval from scratch.

2. **HyDE poisons BM25**: When HyDE is active, the hypothetical document (not the user query) is fed to BM25. An LLM-generated passage will have different term frequencies and vocabulary than the user's actual query, making BM25 matching unreliable under HyDE.

3. **No second fusion layer**: Contrary to the task description, there is no two-layer RRF. The architecture is simpler than expected.

4. **`hybrid_alpha` is dead code**: `config.py:50` defines `hybrid_alpha: float = 0.5` with a validator, but it is never read by any retrieval component. RRF is used instead of weighted averaging.

---

## D2: Ground Truth Quality Audit

### Eval Set Status

**The eval dataset (`data/eval/query_set.jsonl`) does not exist on disk.** The `data/` directory is entirely absent from the repository and local filesystem.

The eval set is generated at runtime by `scripts/build_query_set.py`, which:
1. Samples chunks from a running Qdrant instance
2. Uses an LLM (Groq `llama-3.3-70b-versatile`) via `instructor` to generate queries
3. Outputs JSONL to `data/eval/query_set.jsonl`

### Source Analysis

Based on `build_query_set.py` and README:

| Property | Value |
|----------|-------|
| Total queries | 64 (per README) |
| Source | **100% AI-generated** by Groq LLM from sampled corpus chunks |
| Relevance labels | **Binary** (match / no match) |
| Human verification | **0 samples verified** — no human review step exists in the pipeline |
| Generation method | `instructor` structured outputs with per-category system prompts |
| Reproducibility | Seeded (`--seed 42`) but depends on Qdrant corpus state and LLM non-determinism |

**Per CLAUDE.md Section 6.4**: `WARNING: UNVERIFIED GROUND TRUTH` — generation method is LLM (Groq llama-3.3-70b-versatile), total count is 64, human-verified samples is 0.

### Category Distribution (from README and build script defaults)

| Category | Count (default) | Matching strategy |
|----------|-----------------|-------------------|
| Precise | 20 | chunk ID must appear in results |
| Semantic | 20 | chunk ID must appear in results |
| Fuzzy | 20 (batches of 5 chunks each) | source tag OR ATT&CK ID match |

### Category Mapping to CLAUDE.md Section 6.2

The codebase uses different category names than CLAUDE.md:

| Codebase category | CLAUDE.md category | Rationale |
|---|---|---|
| `precise` | **Exact** | Contains specific IOCs, CVEs, tool names, hashes, domains |
| `semantic` | **Conceptual** | Asks about techniques/behaviors conceptually |
| `fuzzy` | **Fuzzy** | "Memory fog" vague queries without specific entities |

### Query Generation Prompts (Quality Assessment)

**Precise queries** (`_PRECISE_SYSTEM`):
- Explicitly FORBIDS ATT&CK IDs as query anchors (good — forces unique identifiers)
- Requires concrete details: tool names, malware families, CVEs, IPs, domains
- Maps to CLAUDE.md "Exact" category
- **Risk**: LLM may generate queries that over-fit to the specific chunk it was given

**Semantic queries** (`_SEMANTIC_SYSTEM`):
- Explicitly forbids IOC values, CVE IDs, specific tool names
- Requires general questions about technique/behavior classes
- Maps to CLAUDE.md "Conceptual" category
- **Risk**: May generate generic questions retrievable by many chunks, inflating Hit@k

**Fuzzy queries** (`_FUZZY_SYSTEM`):
- Uses "memory fog" framing with hedging language
- Batch-based (5 chunks → 1 query), so ground truth is broader
- Uses source/ATT&CK matching (not chunk ID), more lenient
- Maps to CLAUDE.md "Fuzzy" category
- **Risk**: Lenient matching (source OR ATT&CK) may accept irrelevant results as hits

### Ground Truth Quality Concerns

1. **Circular evaluation risk**: The LLM generates both the eval queries AND the HyDE hypothetical documents. Both use Groq models. CLAUDE.md 6.4 warns: "Relevance labels must not be generated by the same LLM that is part of the retrieval pipeline."

2. **In-distribution inflation**: Queries are generated FROM the corpus. README correctly flags this: "scores are optimistic relative to the external benchmark."

3. **Fuzzy matching is too lenient**: For fuzzy queries, any chunk from the same source (e.g., "mitre") or sharing any ATT&CK ID counts as a hit. With ~20 sources and thousands of chunks per source, this produces high hit rates by chance.

4. **No eval set is committed to the repo**: Results are not reproducible without re-generating (depends on Qdrant state + LLM non-determinism).

5. **Cannot sample 20 queries**: Since the eval set does not exist on disk, I cannot print individual queries or assign categories. The categorization can only be done after regenerating the dataset.

### TechniqueRAG External Benchmark

A second eval protocol uses [QCRI/TechniqueRAG-Datasets](https://huggingface.co/datasets/QCRI/TechniqueRAG-Datasets):
- Source: External academic benchmark (not AI-generated for this project)
- Queries: Real CTI report passages
- Ground truth: ATT&CK technique IDs (parsed from output column)
- Not in-distribution: Queries were never seen during corpus construction
- **This is the more trustworthy evaluation**, per the README's own assessment

---

## D3: HyDE Ablation Experiment

### Experiment Status: CANNOT RUN

The ablation experiment cannot be executed because:

1. **No Qdrant instance is running**: The vector store is not available (data/ directory doesn't exist, no Docker container running)
2. **No eval dataset exists on disk**: `data/eval/query_set.jsonl` must be regenerated first
3. **No LLM API keys are configured**: No `.env` file exists (only `.env.example`)

### Analysis from Previously Reported Results

The README reports results from a prior run. Analyzing those numbers:

#### Configuration

- **baseline**: `hybrid` (dense + sparse + RRF, no HyDE)
- **no_hyde variant**: `dense` (dense only, no sparse, no HyDE)
- **hyde variant**: `hybrid+hyde` (dense + sparse + RRF + HyDE)

Note: The README doesn't report a clean `hybrid` vs `hybrid+hyde` comparison with the same base retriever — `dense` and `hybrid` produce identical results (discussed below).

#### Previously Reported Results — TechniqueRAG (External)

| Config | Hit@1 | Hit@5 | Hit@10 | MRR |
|---|---|---|---|---|
| dense | 0.360 | 0.620 | 0.680 | 0.484 |
| hybrid | 0.360 | 0.620 | 0.680 | 0.484 |
| hybrid+HyDE | 0.280 | 0.500 | 0.660 | 0.372 |

**Observations**:
- `dense == hybrid` exactly. BM25 adds zero lift. This means RRF fusion with sparse results contributes nothing beyond what dense retrieval already finds.
- `hybrid+HyDE` degrades all metrics: Hit@1 drops 22% (0.360→0.280), Hit@5 drops 19% (0.620→0.500), MRR drops 23% (0.484→0.372).
- Hit@10 barely changes (0.680→0.660): HyDE pushes relevant docs lower in the ranking but doesn't fully exclude them.

#### Previously Reported Results — Custom Query Set (Overall)

| Config | Hit@1 | Hit@10 | MRR |
|---|---|---|---|
| dense | 0.875 | 0.984 | 0.930 |
| hybrid | 0.875 | 0.984 | 0.930 |
| hybrid+HyDE | 0.672 | 0.922 | 0.752 |

**Observations**:
- Again `dense == hybrid`. BM25 adds nothing.
- HyDE drops Hit@1 by 23% (0.875→0.672) and MRR by 19% (0.930→0.752).
- The overall pattern is consistent with the external benchmark.

#### Per-Category Pattern (from README)

| Category | dense/hybrid Hit@1 | hybrid+HyDE Hit@1 | Direction |
|---|---|---|---|
| Precise (Exact) | ~1.000 (inferred) | degraded (drives overall down) | HyDE HURTS |
| Fuzzy | 0.800 | 0.933 | HyDE HELPS |

**Root cause hypothesis for HyDE hurting precise queries**: When a user queries a specific IOC (e.g., "CVE-2023-34362"), HyDE generates a hypothetical passage that semantically describes the vulnerability but may not contain the exact CVE string. Dense search then matches on the semantic content of the hallucinated passage rather than the specific identifier, pulling in tangentially related but wrong chunks. Meanwhile, BM25 also receives the hallucinated text, so even the keyword-matching safety net is compromised.

**Root cause hypothesis for HyDE helping fuzzy queries**: Vague "memory fog" queries like "something about persistence on Windows" are too underspecified for direct embedding. HyDE expands them into a concrete CTI passage mentioning specific techniques, tools, and registry keys — producing a denser embedding that's closer to actual corpus documents in vector space.

### What a Proper Ablation Would Require

To execute D3 per CLAUDE.md Section 6.3:

1. **Prerequisites**:
   - Running Qdrant with ingested corpus
   - `.env` configured with API keys (Groq for HyDE)
   - Query set generated (or TechniqueRAG cache downloaded)

2. **Configurations to compare**:
   - `hybrid` (baseline — no HyDE)
   - `hybrid+hyde` (HyDE enabled)
   - Optionally `dense` (to isolate BM25's contribution)

3. **Metrics required** (per CLAUDE.md): Hit@1, Hit@5, Hit@10, MRR, nDCG@5, nDCG@10

4. **Mandatory reporting**:
   - Overall comparison table
   - Per-category breakdown (precise/semantic/fuzzy)
   - Every flipped query individually listed with root cause analysis
   - Pre-completion checklist (Section 6.6)

5. **Execution command**:
   ```bash
   cd rag_cti
   python scripts/eval_query_set.py --config hybrid --output data/eval/results_hybrid.json
   python scripts/eval_query_set.py --config hybrid+hyde --output data/eval/results_hyde.json
   ```

### INCOMPLETE Designation

Per CLAUDE.md Section 6.1: **INCOMPLETE — 0/N queries evaluated.** The ablation cannot be run without infrastructure (Qdrant + API keys + eval dataset). The analysis above is based on previously reported results from the README, which lack:
- Per-query flipped analysis
- nDCG metrics
- Per-category breakdown for semantic queries
- Individual query-level results

---

## D4: RRF Parameter Documentation

### RRF Formula

From `fusion.py:29`:

```
score(chunk) = Σ  1 / (k + rank_i + 1)
               i∈retrievers
```

Where:
- `k` = smoothing constant (default 60)
- `rank_i` = 0-based position of the chunk in retriever i's result list
- Sum is across all retrievers that returned this chunk

This is the standard RRF formula from the original paper (Cormack et al., 2009), with one implementation note: the `+1` in the denominator accounts for 0-based ranking. With 1-based ranking the formula would be `1/(k + rank)`.

### Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| **k** (smoothing constant) | 60 | `fusion.py:8` — hardcoded default, never overridden |
| **Retriever weights** | Equal (1.0 each) | No weighting — each retriever contributes `1/(k+rank+1)` identically |
| **Number of retrievers fused** | 2 | `[dense_results, sparse_results]` at `hybrid_retriever.py:39` |
| **top_k per retriever** | Same as final top_k (default 10) | `hybrid_retriever.py:30-35` — both receive the same `top_k` argument |
| **Deduplication** | By chunk ID | `fusion.py:28` — best (highest individual score) representative kept |

### Observations

1. **Equal weighting**: Both dense and sparse retrievers contribute equally to fusion scores. Given that dense and hybrid produce identical results (sparse adds no lift), the sparse results are either identical to dense results or contribute chunks that don't affect the top-k ranking.

2. **Small candidate pool**: Both retrievers return only `top_k` results (default 10). RRF fuses 10 + 10 = up to 20 unique candidates, then truncates to 10. A common RRF pattern is to retrieve more candidates per retriever (e.g., 3x top_k) to give fusion more material to work with.

3. **k=60 is standard but untuned**: The value comes from the original paper and is reasonable, but no tuning has been done for this specific corpus and query distribution.

4. **`hybrid_alpha` is unused**: `config.py:50` defines `hybrid_alpha: float = 0.5` but it is never referenced in any retrieval code. The comment says "weight for dense vs sparse (1.0 = pure dense)" but RRF fusion doesn't use weights — this is dead configuration.

---

## Pre-Completion Checklist (CLAUDE.md Section 6.6)

### 1. List 3 sample queries from the eval set verbatim. Are they realistic CTI scenarios?

**Cannot comply.** The eval set (`data/eval/query_set.jsonl`) does not exist on disk. The `data/` directory is absent. No queries can be sampled.

However, the `build_query_set.py` script provides example queries in its prompt templates:
- Precise: "CVE-2023-46604 Apache ActiveMQ exploit in the wild" — realistic CTI exact query
- Precise: "Kinsing cryptominer targeting Docker API" — realistic threat hunting query
- Fuzzy: "something about Eastern European actors going after bank login pages, credential theft vibes" — realistic analyst memory-fog scenario

These examples suggest the generator produces realistic queries, but without the actual dataset, this cannot be verified.

### 2. Which query category performed worst? What is the gap vs the best category?

From the previously reported results, **fuzzy queries without HyDE** performed worst on Hit@1 (0.800 vs precise ~1.000, gap = ~0.200). With HyDE enabled, **precise queries** performed worst (overall Hit@1 dropped from 0.875 to 0.672, driven by precise degradation).

On the external benchmark (TechniqueRAG), there are no per-category breakdowns because the external dataset doesn't have the precise/semantic/fuzzy categorization.

### 3. List the top 3 queries with the largest rank changes. What caused each?

**Cannot comply.** No per-query results are available. The eval scripts (`eval_query_set.py`, `eval_techniquerag.py`) report aggregate metrics only — they do not log individual query results or rank positions. This is a gap in the evaluation infrastructure.

### 4. How many ground truth labels were human-verified?

**Zero.** The custom query set is 100% LLM-generated with no human verification step. The TechniqueRAG benchmark is externally curated (academic dataset), so its labels have been through a separate review process, but this project has not independently verified them.

### 5. State one finding that surprised you or contradicted expectations.

**The complete identity of dense and hybrid results was surprising.** I expected BM25 to at least occasionally promote different chunks than dense retrieval, even if the net effect was small. The fact that `dense == hybrid` on every metric across two separate eval protocols means either:
- (a) BM25 returns the same chunks in the same order as dense (unlikely given different scoring mechanisms), or
- (b) BM25 returns different chunks but RRF fusion with a small candidate pool (top_k=10 per retriever) doesn't produce any ranking changes in the final top-k

Hypothesis (b) is more likely. With only 10 candidates from each retriever, and k=60 making score differences very small (range: 1/61 to 1/70 ≈ 0.0164 to 0.0143), the dense retriever's top-k likely dominates the fused ranking. Increasing the per-retriever candidate pool (e.g., `top_k * 3` per retriever, then truncate after fusion) would give BM25 results more opportunity to influence the final ranking.

---

## Summary of Findings and Recommended Actions

### Critical Issues

| # | Issue | Impact | Priority |
|---|-------|--------|----------|
| 1 | HyDE poisons BM25 input | BM25 receives LLM-hallucinated text instead of user query under HyDE | P0 |
| 2 | BM25 adds zero retrieval lift | Entire sparse retrieval path is dead weight | P1 |
| 3 | Eval dataset not persisted | Results are not reproducible; no committed ground truth | P1 |
| 4 | Per-retriever top_k too small | RRF has insufficient candidate diversity for meaningful fusion | P1 |
| 5 | No per-query eval logging | Cannot identify which queries flip between configs | P2 |

### Recommended Actions (Prioritized)

1. **Fix HyDE query routing** (P0): When HyDE is active, pass the original user query (not the hypothetical doc) to BM25 sparse search. Only use the hypothetical doc for dense retrieval. This requires splitting the HyDE logic so it wraps DenseRetriever, not HybridRetriever.

2. **Increase per-retriever candidate pool** (P1): Change `hybrid_retriever.py` to request `top_k * 3` from each retriever, then truncate after RRF fusion. This gives sparse results more opportunity to influence rankings.

3. **Commit eval dataset to repo** (P1): Run `build_query_set.py`, human-verify at least 20% of queries, commit the JSONL to version control so experiments are reproducible.

4. **Add per-query eval logging** (P2): Modify `evaluate_on_query_set()` to return per-query hit/miss/rank data, enabling flipped-query analysis between configurations.

5. **Remove `hybrid_alpha` dead config** (P2): Delete the unused configuration field to avoid confusion.

6. **Extract BGE-M3 native sparse vectors** (P3): Replace the custom BM25 encoder with BGE-M3's built-in sparse representation, eliminating the separate vocabulary and potentially improving sparse retrieval quality.
