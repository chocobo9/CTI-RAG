# RAG Baseline Evaluation Report

**Date:** 2026-05-17
**Evaluator:** Claude Opus 4.6 (automated)

---

## 1. Test Conditions

### Dataset

| Parameter | Value |
|-----------|-------|
| Dataset | `QCRI/TechniqueRAG-Datasets` (HuggingFace) |
| Split | `train` |
| Records evaluated | 50 (of 34,151 total) |
| Cache | `data/eval/techniquerag_cache.jsonl` |

### Retriever Configuration

| Parameter | Value |
|-----------|-------|
| Config | `dense` |
| Collection | `cti_chunks_hybrid` |
| Embedding model | `BAAI/bge-m3` (391 weight files) |
| Vector store | Qdrant (`localhost:6333`) |
| Top-k cutoffs | 1, 5, 10 |

### Environment

| Component | Value |
|-----------|-------|
| OS | Windows 11 (WSL2 for execution) |
| Python venv | `rag_cti/rag-venv` |
| LLM (HyDE) | Not used (`dense` config, no HyDE) |
| Groq model | `llama-3.1-8b-instant` (available but unused) |
| Sparse vocab | `data/sparse_vocab.json` (loaded if present) |

### .env Key Parameters

```
QDRANT_COLLECTION=cti_chunks_hybrid
EMBEDDING_MODEL=BAAI/bge-m3
RETRIEVAL_TOP_K=10
HYBRID_ALPHA=0.5
```

---

## 2. Baseline Results (dense config)

| Metric | Value |
|--------|-------|
| **Hit@1** | 0.3400 |
| **Hit@5** | 0.6800 |
| **Hit@10** | 0.7600 |
| **MRR** | 0.4617 |
| **N** | 50 |

### Interpretation

- **Hit@1 = 34%**: Only one-third of queries place the correct document at rank 1. Significant room for improvement in precision.
- **Hit@5 = 68%**: Two-thirds of queries find the target within top 5. Reasonable for dense-only retrieval.
- **Hit@10 = 76%**: Three-quarters succeed within top 10, but 24% of queries fail entirely even with a generous cutoff.
- **MRR = 0.46**: Average reciprocal rank indicates the correct document, when found, typically lands around rank 2-3.

### Performance Notes

- First query: ~215s (model loading into memory)
- Subsequent queries: 150-400ms each
- LangSmith tracing returned 403 (expired API key) -- non-blocking, no impact on results

---

## 3. Test Quality Audit

### Assertion Quality

| Metric | Count | Ratio |
|--------|-------|-------|
| Weak assertions (`is not None`, `len > 0`, `!= None`) | 13 | 2.1% |
| Total assertions | 614 | 100% |
| Mock usage (`mock`, `Mock`, `patch`, `MagicMock`) | 177 | 28.8% of assertions |

### Assessment

- **Weak assertion ratio (2.1%)**: Low -- the test suite predominantly checks specific behavioral properties rather than mere existence.
- **Mock density (28.8%)**: Moderate, expected for a RAG system that interfaces with external services (Qdrant, LLMs, embedding models). The mocks primarily isolate unit tests from network dependencies.
- **Total assertion count (614)**: Reasonable breadth for the codebase size.

### Patterns Scanned

```
Weak:  assert.*is not None | assert len.*> 0 | assert.*!= None
Total: assert\s
Mock:  mock | Mock | patch | MagicMock
Scope: rag_cti/tests/**/*.py
```

---

## 4. Analysis & Recommendations

### Retrieval Gaps

1. **24% total miss rate at k=10**: Nearly a quarter of queries cannot find the correct document within top 10. Root causes to investigate:
   - Embedding model may not capture ATT&CK technique-specific semantics well
   - Chunking strategy may split technique descriptions across boundaries
   - Collection may lack some techniques present in the TechniqueRAG dataset

2. **Hit@1 to Hit@5 jump (34% -> 68%)**: The correct document is often present but not ranked first. This suggests:
   - Re-ranking could provide significant gains
   - Hybrid retrieval (BM25 + dense) may boost exact-match queries where keyword overlap matters

3. **MRR at 0.46**: Below 0.5 indicates rank positions average worse than 2nd. A cross-encoder re-ranker or query expansion could improve this.

### Recommended Next Experiments

| Priority | Experiment | Expected Impact |
|----------|-----------|-----------------|
| 1 | `hybrid` config (dense + BM25) | +5-10% Hit@5 from keyword matching |
| 2 | `hybrid+hyde` config | +3-7% Hit@5 from query expansion |
| 3 | Full 200+ query eval | More statistically robust baselines |
| 4 | Per-category breakdown (Exact/Conceptual/Fuzzy) | Identify where each retriever variant wins |

### Test Suite Improvements

| Priority | Action | Rationale |
|----------|--------|-----------|
| 1 | Replace 13 weak assertions with property checks | Prevent false-pass on empty/None results |
| 2 | Add integration tests that hit live Qdrant | Current mock-heavy tests may miss connection/schema issues |
| 3 | Add eval regression test | Auto-flag if Hit@5 drops below 0.65 threshold |

---

## 5. Reproducibility

```bash
# Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# Activate environment
cd rag_cti
source rag-venv/bin/activate  # WSL

# Run baseline
python scripts/eval_techniquerag.py --config dense --max-records 50

# Available configs: dense | hybrid | hybrid+hyde | all
```

---

## Appendix: Script Details

- **Entry point**: `rag_cti/scripts/eval_techniquerag.py`
- **Metrics module**: `rag_cti/src/rag_cti/evaluation/retrieval_metrics.py`
- **Dataset loader**: `rag_cti/src/rag_cti/evaluation/techniquerag.py`
- **Pipeline builder**: `rag_cti/src/rag_cti/retrieval/__init__.py` (`build_pipeline`)
- **Collection config**: `.env` -> `QDRANT_COLLECTION`
