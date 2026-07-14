# SNAPSHOT — `cti_chunks_v2` Chunk Truncation & Size Distribution Audit

> Archive category: collection-specific evaluation.
>
> **Status: HISTORICAL COLLECTION SNAPSHOT.** Results apply only to the dated
> `cti_chunks_v2` collection and configuration below.

Date: 2026-05-29
Collection: `cti_chunks_v2` (10123 points)
Reranker: `BAAI/bge-reranker-v2-m3`, `max_length=512`
Embedder: `BAAI/bge-m3`, `max_seq_length=8192`
Tokenizer: XLM-RoBERTa (shared by both models)

---

## 1. MITRE ATT&CK Bundle — Relationship Statistics

Bundle: `enterprise-attack.json`, 20048 non-revoked relationships.

| Edge type | Count | Ingested |
|-----------|------:|:--------:|
| malware → uses → attack-pattern | 9836 | No (excluded: non-actor attribution) |
| intrusion-set → uses → attack-pattern | 4362 | Yes |
| course-of-action → mitigates → attack-pattern | 1445 | No (defensive, non-CTI) |
| campaign → uses → attack-pattern | 1019 | Yes |
| tool → uses → attack-pattern | 800 | No (tool capability, non-actor) |
| x-mitre-detection-strategy → detects → attack-pattern | 691 | No (detection rules) |
| intrusion-set → uses → malware | 647 | Yes |
| attack-pattern → subtechnique-of → attack-pattern | 477 | No (hierarchy metadata) |
| intrusion-set → uses → tool | 457 | Yes |
| attack-pattern → revoked-by → attack-pattern | 132 | No (deprecation mapping) |
| campaign → uses → malware | 84 | Yes |
| campaign → uses → tool | 65 | Yes |
| campaign → attributed-to → intrusion-set | 25 | Yes |
| intrusion-set → revoked-by → intrusion-set | 6 | No |
| malware → revoked-by → malware/tool | 2 | No |
| **Total** | **20048** | **6659** |

Ingested breakdown: `uses` 6634 + `attributed-to` 25 = 6659.

## 2. Qdrant Collection State

| source | points | origin |
|--------|-------:|--------|
| mitre | 7425 | 766 technique definitions + 6659 relationship chunks |
| otx | 2072 | OTX pulse summaries |
| pdf | 626 | PDF report extracts |
| **Total** | **10123** | |

Note: `pdfs_bench` (12717 chunks on disk) is NOT in Qdrant. `cti_chunks` (old collection) is deprecated.

## 3. Chunk Size Distribution (actual tokenizer counts)

### mitre — technique definitions (766 chunks)

| Percentile | Tokens |
|:----------:|-------:|
| p50 | 340 |
| p90 | 566 |
| p99 | 652 |
| max | 720 |

### mitre_relationships (6659 chunks)

| Percentile | Tokens |
|:----------:|-------:|
| p50 | 74 |
| p90 | 116 |
| p99 | 198 |
| max | 463 |

### otx — OTX pulse summaries (2072 chunks)

| Percentile | Tokens |
|:----------:|-------:|
| p50 | 467 |
| p90 | 745 |
| p99 | 1020 |
| max | 1429 |

### pdfs — PDF report extracts (626 chunks)

| Percentile | Tokens |
|:----------:|-------:|
| p50 | 152 |
| p90 | 527 |
| p99 | 794 |
| max | 1217 |

## 4. Reranker Truncation (>512 tokens)

| Source | Chunks over 512 | Total | % truncated |
|--------|----------------:|------:|------------:|
| mitre (technique) | 140 | 766 | 18.3% |
| mitre_relationships | 0 | 6659 | 0% |
| otx | 870 | 2072 | **42.0%** |
| pdfs | 72 | 626 | 11.5% |

Embedder (>8192 tokens): **0 chunks across all sources.** No embedder truncation.

## 5. What Gets Truncated

### mitre (technique definitions)
Tail of ATT&CK technique descriptions. Lost content: detection guidance, citation references, supplementary attack variant descriptions. Typical loss: 26–101 tokens (5–16% of chunk).

### otx (worst offender)
Primarily **IOC hash lists** (SHA256, MD5 strings) at the end of pulse summaries. The truncated portion is often 40%+ of the chunk — hundreds of tokens of comma-separated hex hashes. Low impact on semantic retrieval (hashes don't participate in semantic matching), but complete loss for hash-based lookup.

### pdfs
Report paragraph tails. Lost content: specific case details, statistics, named entities (e.g., ransom amounts, actor names, exploitation details). This content has real semantic value. Typical loss: 7–67 tokens (1–12%).

## 6. Truncation Mechanisms in Codebase

| Location | Mechanism | Limit | Behavior |
|----------|-----------|------:|----------|
| `reranker.py:52` | `CrossEncoder(max_length=512)` | 512 tok | **Silent truncation** on `(query, chunk)` pairs. No warning. Affects rerank scoring accuracy. |
| `chunking.py:17` | `_DEFAULT_TARGET_TOKENS=600` | ~600 tok (soft) | Sentence-aware chunking target. Soft limit — single sentences exceeding target are not split. No hard cap. |
| `embedder.py:60` | `SentenceTransformer(model)` | 8192 tok (model built-in) | bge-m3 internal max_seq_length. Silent truncation by tokenizer. Currently no chunks exceed this. |
| `hyde.py:95,106` | `max_tokens=300` | 300 tok | LLM output cap for HyDE hypothetical document generation. Not an input truncation. |
| `hyde.py:101,110` | `[:2000]` char slice | 2000 chars | Hard safety cap on HyDE output before passing to embedder. |
| `config.py:57` | `generation_max_tokens=1024` | 1024 tok | Final answer generation LLM output cap. Not related to retrieval. |

### HyDE consumption path
HyDE-generated document (≤300 tok) → `Embedder.encode_one()` (dense vector) → Qdrant dense search. BM25 sparse search uses the **original query**, not the HyDE document. The HyDE document never reaches the reranker.

## 7. The Chunker–Reranker Gap

Chunker targets 600 tokens. Reranker truncates at 512. This creates an **88-token gap** where content is produced by the chunker but silently discarded by the reranker.

- The chunker's 600 is a soft target (sentence-boundary-aware, frequently exceeded).
- No component in the pipeline enforces a hard 512-token ceiling.
- Result: 1082 out of 9497 in-collection chunks (11.4%) are truncated during reranking.

The gap is most severe for OTX (42% truncated) because OTX pulse summaries are ingested via STRUCTURED strategy (one-chunk-per-document, no splitting), and many pulses exceed 512 tokens.
