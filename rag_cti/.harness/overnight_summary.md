## 执行摘要

### Alpha Bugfix
- 改了: `pipeline.py` (加 `hybrid_alpha_override`), `eval_techniquerag.py`, `eval_query_set.py`, `cli.py` (3处加 ALPHA_MAP)
- 新增3个测试: alpha=1.0→DenseRetriever, alpha=0.5→HybridRetriever, alpha=None→default
- CrossEncoderReranker: 加了 CUDA auto-detect + batch_size=8
- 测试结果: 486 passed, 1 failed (pre-existing test_client.py), coverage 94.27%

### Eval 重跑 — 全部完成

#### TechniqueRAG (50 queries, collection: cti_chunks_hybrid)

| Config | Hit@1 | Hit@5 | Hit@10 | MRR |
|--------|-------|-------|--------|-----|
| dense (no reranker) | 0.32 | 0.58 | 0.64 | 0.4384 |
| hybrid (no reranker) | 0.16 | 0.50 | 0.58 | 0.2766 |
| dense + reranker | 0.34 | 0.66 | 0.72 | 0.4717 |
| **hybrid + reranker** | **0.36** | **0.64** | **0.70** | **0.4714** |

#### Custom Query Set (64 queries)

| Config | Overall Hit@1 | Overall MRR | Precise Hit@1 | Semantic Hit@1 | Fuzzy Hit@1 |
|--------|--------------|-------------|---------------|----------------|-------------|
| dense (no reranker) | 0.5000 | 0.5234 | 0.3462 | 0.4783 | 0.8000 |
| hybrid (no reranker) | 0.3281 | 0.4123 | 0.1923 | 0.1739 | 0.8000 |
| dense + reranker | 0.5156 | 0.5282 | 0.3462 | 0.5217 | 0.8000 |
| hybrid + reranker | 0.5156 | 0.5260 | 0.3462 | 0.5217 | 0.8000 |

### Goal 2 RAGAS — 完成
- **Faithfulness: 0.9177** (excellent)
- **Answer Relevancy: 0.4784** (moderate)
- 10 queries, hybrid config, DeepSeek generation + judge

### 未解决的问题
1. Groq API key 过期 — 用 DeepSeek 替代
2. hybrid 无 reranker 时在 cti_chunks_hybrid 上表现差
3. pre-existing test failure: test_build_llm_client_groq_provider_when_groq_key_set
4. Answer Relevancy 偏低 (0.48) — strictness=1 限制或 DeepSeek 判断偏严
