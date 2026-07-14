# Agentic RAG Engineering Resources

## Knowledge

- [Mind map: Agentic RAG 工程架构](D:\agentic_rag_mindmap.html)
  The user-provided concept map. Use for course scope, lesson ordering, and terminology clusters.
- [Historical framing: Runtime guardrails and eval harness](docs/archive/runtime/HISTORICAL_agentic_rag_guardrails.md)
  Historical north-star reference only; do not use it for current implementation status.
- [ADR: Runtime Harness Orchestration](docs/adr/0001-runtime-harness-orchestration.md)
  Accepted architecture decision. Use as the authority for `answer()`, query understanding, supervisor admission, branch reports, and Composer boundaries.
- [Project glossary: CTI-RAG CONTEXT](docs/CONTEXT.md)
  Existing project term authority for Entity, OntologyNode, Fact, Evidence, supports, Chunk, and source classes.
- [Runtime harness source](src/rag_cti/runtime_harness.py)
  Primary code for runtime query understanding, state, observations, tool validation, single-agent loop, and supervisor admission.
- [Public API source](src/rag_cti/__init__.py)
  Primary code for `answer()`, `agentic_answer()`, `supervised_answer()`, dependency construction, and public surface boundaries.
- [Evidence ledger source](src/rag_cti/knowledge/evidence_ledger.py)
  Primary code for per-run evidence accumulation, dedupe, ledger merge, real citation IDs, and conflict surfacing.
- [Agent tools source](src/rag_cti/knowledge/agent_tools.py)
  Primary code for bounded model-visible summaries and ledger-aware adapters.
- [Supervisor sources](src/rag_cti/knowledge/supervisor_graph.py)
  Primary code for validated branch-plan execution, worker dispatch, Composer invocation, branch ledger merge, and final citation guard.
- [Eval sources](src/rag_cti/evaluation)
  Primary code for retrieval metrics, query-set eval, TechniqueRAG scoring, and RAGAS faithfulness/relevancy evaluation.

## Wisdom

- CTI-RAG tests under [tests](/D:/proj/CTI-RAG/.claude/worktrees/optimization/rag_cti/tests)
  Use for checking whether a concept has executable contracts or only design intent.
- Local traces and eval outputs under `data/eval` and `logs`
  Use for real behavior evidence when deciding whether a guardrail improves runtime quality.

## Gaps

- Need a later lesson to map each runtime claim to its strongest current test.
- Need a later lesson to inspect one real trace/eval run and practice failure attribution.
