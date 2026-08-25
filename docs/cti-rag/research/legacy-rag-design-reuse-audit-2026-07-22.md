# Legacy RAG Design Reuse Audit

Status: non-normative historical-design comparison.  
Review date: 2026-07-22.

This note compares the old Python project at
`D:\proj\CTI-RAG\.claude\worktrees\optimization\rag_cti` with the current
CTI-RAG design in this repository. It does not adopt an old design, select a
model or retrieval stack, change an owner, or authorize implementation.

The old documents are historical project material, not independent external
evidence. Their claims about old code, tests and model behaviour are therefore
recorded as **legacy facts**, not as evidence that the current product has the
same capability.

## 1. Disposition

The old project contains four reusable design lessons:

1. A retrieval index is a relevance projection, not a fact, Case, or evidence
   authority.
2. Model calls and raw Tool results must not be the source of durable
   investigation state; durable state changes must pass through a typed,
   replayable owner boundary.
3. Retrieval must preserve source/provenance identity, keep CTI identifiers
   usable for exact/lexical retrieval, and distinguish empty/failed/denied
   outcomes from negative evidence.
4. A model may propose an action while deterministic policy controls
   admission, budget, authorization, and terminal/publishing semantics.

The current owner model already expresses these lessons more precisely:

```text
Pi                  generic model/tool/session execution
Agent Workspace     task/run/capability admission and Working Set selection
I&E                 resource versions, derivations, retrieval and provenance
Case Management     authoritative Case state and controlled changes
```

Do not carry forward the old monolithic `RuntimeHarness`, `EvidenceLedger`,
`RuntimeActionProposal`, `RuntimeObservation`, or a Python graph/vector stack
as current Module contracts. Their useful behaviour is either already owned by
current contexts or remains a future owner-local design choice.

The old BGE-M3 decision has **no adoption value** for the current embedding
decision. It explicitly says its formal bakeoff was never filled in and that
Recall@5, latency, and comparison results were not recorded. The current
policy correctly leaves embeddings, reranking and vector storage unselected
until a source-permitted corpus, Retrieval Segment profile and CTI evaluation
fixtures demonstrate a lexical-retrieval gap.

## 2. Evidence reviewed

### Legacy facts

The review read the old glossary, retrieval and knowledge-layer designs,
embedding decision, phase-control ledger, target/redefinition architecture
documents, Pi-native harness audit, and ADRs 0001/0002. In particular:

- `docs/retrieval_layer_design.md`
- `docs/knowledge_layer_design.md`
- `docs/rag/EMBEDDING_DECISION.md`
- `docs/runtime_harness_phase_control.md`
- `docs/architecture/CTI_INVESTIGATOR_TARGET_DESIGN.md`
- `docs/architecture/CTI_INVESTIGATION_RUNTIME_REDEFINITION.md`
- `docs/architecture/pi_native_cti_harness_design.md`
- `docs/adr/0001-runtime-harness-orchestration.md`
- `docs/adr/0002-investigation-case-and-policy-authority.md`

### Current facts

Current design authority is [the CTI-RAG documentation index](../README.md),
the [context map](../CONTEXT-MAP.md), the Agent Workspace and I&E
`CONTEXT.md` files, the active contracts/ADRs they link, and
[Agent Model and Retrieval Policy Research](agent-model-and-retrieval-policy-research-2026-07-22.md).

The active I&E core is exact-resource retrieval. It makes zero embedding,
reranker, and model calls. Bounded search, Retrieval Segments, Index
Generations, lexical retrieval, dense retrieval and reranking are later,
separately gated work.

## 3. Reusable lessons, mapped to current owners

| Legacy lesson | Current disposition | Current owner / boundary |
| --- | --- | --- |
| Vector store contains retrieval projections, never facts/ontology/Cases. | Reuse the principle. | I&E owns Retrieval Segments, Index Generations and ranking; Case and Workspace retain their own state. |
| Dense/sparse scores are relevance signals, not confidence or truth. | Reuse the principle. | I&E Ranking Profile/Receipt; Workspace does not convert score into evidence weight. |
| Narratives and field/indicator records require different extraction/chunking treatment. | Reuse as a future evaluation hypothesis. | I&E extraction/segment profile; no chunking policy is adopted now. |
| Exact constraints should be filtered before similarity ranking. | Reuse as later bounded-search evaluation criterion. | Workspace compiles trusted scope; I&E performs eligibility then retrieval. |
| IOC-preserving lexical analysis matters for CTI. | Retain as a fixture and baseline requirement, not an implementation selection. | I&E future lexical-search evaluation. |
| Ontology traversal may expand a controlled identifier query. | Retain only after I&E has a qualified ontology/Index Generation contract. | I&E, not Workspace/model query rewriting. |
| Tool result display text is not durable state. | Already consistent with current design; retain as a hard migration check. | Pi owns Tool protocol; Workspace/I&E/Case owners retain business state and receipts. |
| A model proposes; deterministic policy admits; an owner commits state. | Already a stronger current principle. | Workspace Run Control/capability admission; I&E and Case owner operations. |
| Empty, error, denied and timeout outcomes must remain distinct. | Reuse. | I&E retrieval failures/receipts and Workspace Run disposition/publication gate. |
| Case/transcript/corpus distinction. | Reuse the separation, not old names or stores. | Case Management, Pi Session, and I&E respectively. |
| Evaluation must measure retrieval, grounding, permission and failure behaviour separately. | Reuse. | Future CTI-RAG fixture set and role/retrieval qualification policy. |

## 4. Conflicts and rejected carry-forward designs

### 4.1 One Python runtime as the product control plane

**Legacy fact:** the old `RuntimeHarness` concentrated query understanding,
proposal extraction, Tool execution, `RuntimeObservation`, an `EvidenceLedger`,
reducer logic, stop policy and optional supervisor routing. Its later documents
recognized this was too broad, but continued to treat it as a central runtime
module.

**Current fact:** Pi is the sole generic Agent/model-tool spine. Agent Workspace
is the CTI composition and policy boundary; I&E and Case Management have their
own durable meanings. Current design explicitly avoids a second Agent loop,
duplicate provider protocol, shared Memory authority, and premature fixed Tool
decomposition.

**Recommendation:** do not recreate `RuntimeHarness` under a new TypeScript
name. Translate only a demonstrated requirement to its current owner: for
example, a retrieval outcome to I&E, a Working Set admission to Workspace, or
a controlled Case transition to Case Management.

### 4.2 Old `EvidenceLedger` as a shared authority

**Legacy fact:** the old design used one per-run ledger for chunks, facts,
actions, observations and citation validation, then proposed a future Case
Ledger to repair its missing revision and lifecycle semantics.

**Current fact:** I&E owns reusable resources/provenance and their
derivatives; Case Management owns authoritative Case records; Workspace owns
task-scoped Working Set and non-authoritative outputs. Model output and Session
history do not become Case authority.

**Deduction:** importing the old ledger would duplicate all three current
owners and reintroduce the exact authority collapse current design avoids.

### 4.3 Embedding model locked before a valid decision record

**Legacy fact:** `docs/rag/EMBEDDING_DECISION.md` marks BAAI/bge-m3 as
production but records that the bakeoff table was never filled, Recall@5 and
latency were not recorded, and the decision was qualitative/downstream.
Its old evaluations used a small generated-query protocol.

**Current fact:** the current retrieval-policy research requires a versioned,
source-permitted CTI fixture set, lexical baseline, authorization-safe
evaluation and measured recall/ranking gap before dense/hybrid/reranker choice.

**Recommendation:** do not pin BGE-M3, its 1024-dimensional shape, Qdrant, or
its hybrid pipeline. BGE-M3 may enter a later candidate list only after the
current evaluation contract exists. Any comparison must include identifier/IOC,
structured CTI fields, source lineage, use-eligibility, hidden-resource safety,
and (if in product scope) Chinese/English queries.

### 4.4 Old supervisor and multi-agent topology

**Legacy fact:** old ADR 0001 conditionally admitted supervisor workers for
independently gatherable branches; the old phase ledger still contained
debug/eval supervisor paths.

**Current fact:** current product design has one Pi Agent loop and no
main-agent/worker architecture. Investigation Run Control deliberately has no
planner Agent, scheduler, DAG or sub-Agent coordinator.

**Recommendation:** retain only the evaluation question: can independent work
improve a measurable CTI outcome within shared budget, authority and merge
rules? Do not turn the old supervisor design into current scope. Any future
topology would require an accepted workflow, explicit owner boundaries and a
new decision, after single-loop evidence proves a need.

### 4.5 Query rewriting as executable authority

**Legacy fact:** old query understanding produced rewritten retrieval queries,
entities, constraints and a decomposition proposal before the runtime chose a
path.

**Current fact:** Task Intake preserves an immutable Original User Task;
Task Understanding produces only a non-authoritative interpretation.
Formal-run Query Candidates are target-neutral and cannot authorize retrieval.

**Recommendation:** keep the distinction. Generated rewrites may later be
evaluated as request-local retrieval transformations, but cannot become an
exact selector, entity decision, I&E access grant, Case fact or Tool authority.

## 5. Retrieval-design implications

### Current facts

1. IER1 exact retrieval must remain zero-embedding and zero-reranker.
2. I&E must check use eligibility before relevance. No candidate, count, title,
   score or snippet may reveal inaccessible material.
3. A future searchable unit must retain Resource Version and Source Span
   lineage; a hit is not itself Case evidence or model truth.
4. Raw scores remain request-local and do not measure source reliability,
   credibility, corroboration or confidence.

### Historical ideas worth testing later

- lexical identifier/IOC handling versus generic tokenization;
- field-aware and source-class-aware segmentation rather than a single blind
  chunk profile;
- filter-first evaluation for known ATT&CK/CVE/IOC/entity constraints;
- rank-based fusion such as RRF, only if separately ranked candidates improve
  the held-out fixture results; and
- reranking only over a bounded, already eligible candidate set.

### Unresolved product choices

- which source/file/language populations become searchable;
- the Resource Derivative, Retrieval Segment and lexical analyzer profiles;
- whether CTI recall needs dense, hybrid or reranked retrieval beyond lexical;
- candidate model hosting, residency/licence and version/update policy;
- quality, latency, cost and hidden-resource safety thresholds; and
- query-transformation and result-adoption policy.

None is resolved by old code or its BGE-M3 designation.

## 6. Model and harness implications

### Current facts

Pi already supplies model/provider execution, Tool schemas, validation,
execution lifecycle, Session history, compaction and event surfaces. Workspace
adds CTI qualification, Run Control, context preparation and publication
decisions. Current model policy does not select a provider/model yet.

### Legacy facts with continued design value

- a no-Tool/model stop signal must not be confused with a successful
  investigation outcome;
- model/provider/tool errors, cancellations, timeouts and no-result outcomes
  need distinct classifications;
- state needed in a later turn should be structured owner state, not parsed
  from rendered result prose;
- provider protocol Tool messages remain transport artifacts, not Case or
  evidence authority; and
- replay must use committed owner records, never repeat model calls, network
  actions or remote side effects.

### Current disposition

These are already compatible with Pi-native lifecycle, Workspace Run Control,
I&E receipts and Case/Session separation. They should become acceptance cases
only when an owner-specific product slice is opened; this research does not
introduce an old-style generic `ActionProposal` or `Observation` protocol.

## 7. Recommended use of the old project

1. Use its retrieval corpus/fixtures and implementation only as a **candidate
   benchmark input**, after source licence, provenance, version and access
   suitability are verified.
2. Reuse its tests as behavioural inspiration for: IOC preservation,
   dense/lexical comparison, result provenance, invalid tool arguments, error
   classification, replay without display text and parallel-result isolation.
3. Re-express every accepted behaviour in the current owner’s contract and
   acceptance tests. Do not port its schemas wholesale.
4. Start future retrieval work with deterministic extraction plus a lexical
   baseline, then make a measured decision on dense/hybrid/reranking.

## 8. Questions for a later accepted slice

- What is the first source-permitted CTI evaluation corpus and what relevance,
  source-lineage and citation labels govern it?
- Which lexical searches are valuable after IER1: exact identifiers, fielded
  search, IOC search, natural-language narrative search, or a constrained
  combination?
- How will a future I&E search prove both declared coverage and zero disclosure
  of inaccessible candidates?
- What model qualification thresholds apply separately to Task Intake,
  Investigation Run, independent evidence review and report composition?
- Which observed lexical miss rate/quality gap justifies evaluating dense or
  rerank candidates, and which safety/cost regression rejects them?

## 9. Final conclusion

The old project supports the current direction, not a shortcut around it. Its
best contribution is a set of concrete failure modes and evaluation dimensions.
Its old runtime and BGE-M3 configuration are not reusable current architecture
or a valid model-selection decision. The current owner boundaries and staged
retrieval policy should remain intact.
