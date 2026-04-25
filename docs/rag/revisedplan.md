 Revised Implementation Plan: RAG-Powered CTI System

  Changes Applied

  ┌─────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  #  │                                               Modification                                               │
  ├─────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ M1  │ Embedding bakeoff on own corpus (OTX + ATT&CK), model selected by Top-k relevance                        │
  ├─────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ M2  │ PDF parsing + dirty data preprocessing moved to Phase 2 (after structured pipeline stable)               │
  ├─────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ M3  │ Reranker: interface reserved, not implemented                                                            │
  ├─────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ M4  │ Two-phase evaluation — TechniqueRAG HF dataset (ATT&CK sanity check) → custom Sonnet-generated query set │
  ├─────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ M5  │ Fuzzy query robustness is a primary success criterion                                                    │
  └─────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  Implementation Phases (Revised)

  Phase 0 — Foundations & Scaffolding (1–2 days)

  No change from original plan. Package scaffolding, config, types, Qdrant container, public API stub.

  Deliverables: from rag_cti import query imports; Qdrant reachable; CI green.

  ---
  Phase 1 — Structured Ingestion Pipeline (4–6 days)

  Ingest clean, well-structured sources first: MITRE ATT&CK (STIX), OTX Pulses (JSON), WHOIS (templated), Passive DNS
  (templated), VirusTotal (JSON). No PDF in this phase.

  1. BaseConnector protocol — fetch(params) -> Iterable[RawRecord], retry + rate-limit hook
  2. MITRE ATT&CK connector — STIX 2.1 parser; one Document per technique/subtechnique; preserve technique IDs,
  kill-chain phases, platforms, procedure examples
  3. OTX connector — pulses/subscribed with modified_since; pulse description as content; IOCs + tags + ATT&CK IDs in
  metadata
  4. VirusTotal connector — on-demand enrichment mode (not bulk); focus on semantically rich fields (YARA results,
  community comments, signature info)
  5. WHOIS connector + prose templating — key-value → paragraph ("Domain X registered on D by registrar R, contact E,
  nameservers NS1/NS2"); template versioned in config
  6. Passive DNS connector — (domain, observation-window) → Document with resolution history prose summary
  7. Normalizers — every connector raw record → canonical Document with stable content-hash ID, source, content,
  metadata, retrieved_at
  8. Chunking strategies (two for now):
    - semantic: sentence-aware, 500–800 tokens, 10–15% overlap — for OTX descriptions, MITRE descriptions
    - structured: one chunk per logical record — for WHOIS, pDNS, VT JSON
  9. Incremental refresh — upsert-by-content-hash; time-windowed deletion (3-month half-life per ARES '24)
  10. Unit + integration tests — fixture for each connector; chunker on representative samples; normalizer edge cases
  (empty descriptions, duplicate IDs)

  Exit criteria: MITRE (~823 techniques) + sample OTX pulses chunked and in data/processed/; incremental upsert
  idempotent.

  ---
  Phase 2 — PDF Parsing & Dirty Data Preprocessing (3–4 days)

  Separated from Phase 1 so the clean pipeline is stable before handling noisy sources.

  1. PDF parser (preprocess/pdf_parser.py) — unstructured primary (preserves sections + metadata), pymupdf fallback;
  skip-with-log on failure; section titles propagated to chunk metadata
  2. PDF connector (connectors/pdf_reports.py) — scan data/raw/pdfs/, parse, normalize, chunk with semantic strategy
  3. Dirty data handling — deduplicate by content hash; strip boilerplate headers/footers; handle non-UTF-8 gracefully;
  log coverage gaps
  4. End-to-end ingest test — seed_mitre.py + fetch_otx.py + PDF batch all produce valid chunks in Qdrant

  Exit criteria: 20–50 PDF reports ingested without crashing pipeline; coverage report per source logged.

  ---
  Phase 3 — Embeddings & Vector Store (3–5 days)

  3a — Embedding Model Bakeoff (own corpus)

  1. Embedder protocol + providers — adapters for BGE-M3, GTE-large, nomic-embed-text-v1.5 (add Voyage-2 if budget
  allows)
  2. CTI evaluation corpus (no external benchmark needed):
    - ATT&CK: technique description ↔ procedure example pairs (~50 pairs)
    - OTX: pulse title ↔ pulse description pairs (~50 pairs)
    - Mixed: cross-source (domain IOC → related OTX pulse)
  3. Selection metric: Top-k relevance (k=5, k=10) on this corpus; record latency and embedding cost per 1K tokens
  4. Document decision — chosen model + evidence written to docs/rag/EMBEDDING_DECISION.md
  5. Notebook: notebooks/01_embedding_model_bakeoff.ipynb

  3b — Qdrant Schema & Ingest

  6. Qdrant schema — collection cti_chunks; vector dim matched to chosen embedder; sparse vectors for BM25
  (Qdrant-native sparse preferred); payload indexes on source, retrieved_at, attack_id, ioc_type
  7. Qdrant store wrapper — upsert_chunks, search_dense, search_sparse, search_hybrid, delete_by_filter; batch-tuned
  8. Full corpus embed + ingest — MITRE + OTX + WHOIS + pDNS + PDFs

  Exit criteria: chosen embedder documented with Top-k evidence; full corpus in Qdrant; search_dense("lateral movement")
   returns relevant ATT&CK techniques.

  ---
  Phase 4 — Retrieval Layer (4–6 days)

  1. Dense retriever — embed query → Qdrant vector search → top-N with scores
  2. Sparse retriever (BM25) — Qdrant-native sparse; custom tokenizer that preserves IOC tokens (periods, hyphens in
  IPs/CVEs/domains — highest-risk component)
  3. Hybrid fusion (RRF) — Reciprocal Rank Fusion default; weighted-sum as ablation alternative
  4. HyDE translation — Claude Haiku generates hypothetical CTI document for query; embed hypothetical; fuse with direct
   query retrieval; gated by query length (disabled for short exact lookups)
  5. Reranker interface (retrieval/reranker.py) — define Reranker protocol: rerank(query: str, docs: List[Document]) ->
  List[Document]; NoOpReranker as default; implementation deferred
  6. Retrieval pipeline (retrieval/pipeline.py) — query → HyDE (conditional) → hybrid retrieve → reranker (noop) →
  dedupe → top-k; structured trace events at each stage
  7. Wire public API — replace stub with pipeline.run(query, k)

  Exit criteria: query("APT29 spearphishing") returns relevant ATT&CK + OTX docs; query("1.2.3.4") returns exact-match
  via BM25; query("lateral movement via rdp") returns semantically related results.

  ---
  Phase 5 — Generation Layer (2–3 days)

  1. LLM router — tiered: Haiku for HyDE generation, Sonnet for analysis, Opus for report generation; config-driven
  2. Prompt templates — HyDE generation, context-grounded answer synthesis
  3. Context injection via tool_result — retrieved Documents formatted as tool_result content blocks (not string-stuffed
   in system prompt); preserves citations as structured chunk IDs
  4. Rate limiting + retry wrapper — shared Anthropic client with exponential backoff on 429/529

  Exit criteria: HyDE in Phase 4 routes through this layer; answer(query) helper returns grounded response with cited
  chunk IDs.

  ---
  Phase 6 — Evaluation Framework (5–7 days)

  6a — Phase 1 Evaluation: TechniqueRAG Sanity Check

  1. Load TechniqueRAG dataset from HuggingFace — contains CTI text passages annotated with ATT&CK technique IDs
  2. ATT&CK retrieval validation — for each annotated passage, run query(passage_text) and check whether the correct
  technique is in top-k retrieved set
  3. Metric: Top-k relevance on TechniqueRAG; MRR; compare dense-only vs. hybrid vs. hybrid+HyDE
  4. Purpose: sanity check that ATT&CK retrieval layer works before investing in custom query set

  6b — Phase 2 Evaluation: Custom Query Set

  5. Query set generation via Claude Sonnet (scripts/build_query_set.py) — Sonnet reads ingested corpus (sample of
  Documents per source) and generates queries in three categories:
    - Precise: exact IOC/domain lookup ("What is known about domain cobalt-update[.]com?")
    - Semantic: attack behavior description ("Which technique describes credential dumping from LSASS memory?")
    - Fuzzy: incomplete/ambiguous input ("something about Russian APT targeting finance sector") — primary robustness
  criterion
    - Target: ≥ 60 queries, ~20 per category
  6. Gold relevance labels — Sonnet also generates expected relevant Document IDs per query; spot-check 50
  human-reviewed
  7. Retrieval metrics (evaluation/retrieval_metrics.py) — Top-k relevance, MRR, recall@k, nDCG@k; reported separately
  per query category to surface fuzzy query performance
  8. RAGAS evaluation — faithfulness, answer relevancy, context recall, context precision; Claude-as-judge
  9. RAG vs. baseline comparison — Sonnet with vs. without RAG on post-cutoff CTI queries; hallucination measured via
  faithfulness + human spot-check
  10. Ablation study — {semantic-only, hybrid} × {HyDE on, HyDE off} × {semantic chunking, structured chunking} —
  8-configuration matrix
  11. Eval CLI — rag-cti eval techniquerag, rag-cti eval retrieval, rag-cti eval ragas, rag-cti eval baseline, rag-cti
  eval ablation

  Exit criteria: TechniqueRAG sanity check passes (Top-k ≥ 60% on ATT&CK); custom query set shows fuzzy query Top-k ≥
  60%; overall Top-k ≥ 70%; ablation report committed.

  ---
  Phase 7 — Observability & Hardening (2–3 days)

  LangSmith tracing, metrics, security review, code review, documentation. No change from original.

  ---
  Revised Phase Summary

  ┌───────────────────────────────┬─────────────────────────────────────────────────────────────────┬────────────┐
  │             Phase             │                              Goal                               │    Days    │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────┼────────────┤
  │ 0 — Foundations               │ Scaffolding, config, types, Qdrant, API stub                    │ 1–2        │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────┼────────────┤
  │ 1 — Structured Ingestion      │ MITRE + OTX + WHOIS + pDNS + VT connectors, chunking            │ 4–6        │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────┼────────────┤
  │ 2 — PDF & Dirty Data          │ PDF parsing, dirty data handling, full corpus ingest            │ 3–4        │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────┼────────────┤
  │ 3 — Embeddings & Vector Store │ Model bakeoff on own corpus + Qdrant schema + full ingest       │ 3–5        │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────┼────────────┤
  │ 4 — Retrieval Layer           │ Dense + sparse + HyDE + hybrid RRF + reranker interface         │ 4–6        │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────┼────────────┤
  │ 5 — Generation Layer          │ Tiered LLM, tool_result injection                               │ 2–3        │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────┼────────────┤
  │ 6 — Evaluation                │ TechniqueRAG sanity → custom query set (precise/semantic/fuzzy) │ 5–7        │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────┼────────────┤
  │ 7 — Observability & Hardening │ LangSmith, security review, docs                                │ 2–3        │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────┼────────────┤
  │ Total                         │                                                                 │ 24–36 days │
  └───────────────────────────────┴─────────────────────────────────────────────────────────────────┴────────────┘

  Key Changes from Original

  - PDF isolated to Phase 2 — structured pipeline validates clean before noisy
  - Reranker: NoOpReranker ships, real implementation deferred
  - Embedding bakeoff uses your own OTX + ATT&CK corpus — no MTEB dependency
  - Evaluation is sequential: TechniqueRAG first (fast, off-the-shelf) → custom set second (thorough, fuzzy-robust)
  - Fuzzy query robustness tracked as its own success criterion (separate Top-k reported per query category)

  ---
