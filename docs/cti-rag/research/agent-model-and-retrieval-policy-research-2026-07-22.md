# Agent Model and Retrieval Policy Research

Status: non-normative research.  
Research date: 2026-07-22.

This note records a decision framework for the remaining Agent area: model
policy and the later I&E retrieval stack. It does **not** select a provider,
model, embedding model, vector store, reranker, database, Tool interface, or
delivery scope. It does not amend any contract, ADR, `CONTEXT.md`, or
`PROGRESS.md`.

The source order is: current local CTI-RAG design and Pi source; then primary
vendor documentation and original papers. Product recommendations below remain
candidate recommendations until an owning contract or ADR adopts them.

## 1. Executive disposition

There are two different questions which should not be conflated:

1. **Which model policy makes the Pi-based investigation Agent dependable?**
2. **When I&E later supports search, which retrieval method is justified by
   measured failure of the preceding method?**

The current design has already made the correct first separation:

- Pi is the generic provider/model-tool execution spine.
- Workspace owns task/capability admission, bounded context composition, Run
  budgets, and publication gating.
- I&E owns Resource Versions, Retrieval Segments, Index Generations, ranking
  evidence, Retrieval Receipts, and later embedding/reranking choice.
- Case Management owns authoritative Case state and conclusions.

Consequently, neither a general-purpose Agent model nor an embedding model is
part of Case authority. A model-produced analysis is non-authoritative, and an
embedding is a reproducible I&E derivative, not a fact or an evidentiary
weight.

The current active I&E slice is exact resource retrieval. It explicitly makes
zero model or embedding calls; bounded lexical search, semantic/vector search,
embeddings, reranking, production Index Generation, OCR, and model-based
extraction are deferred. Selecting an embedding or reranker now would therefore
freeze a dependency before the first searchable corpus, query distribution,
authorization boundary, and failure measurements exist. It is premature.

The next appropriate model decision is smaller: define the **evaluation and
qualification policy** that any candidate provider/model must pass for a named
Agent role. The next retrieval decision is smaller still: after file/text
extraction and lexical search are operating, measure its misses on a
source-qualified CTI corpus before adding dense retrieval or reranking.

## 2. Current local facts

### 2.1 Current CTI-RAG decisions and gates

The accepted I&E platform design assigns extraction, Source Spans, Retrieval
Segments, optional embeddings, Index Generation, and Derivation Manifests to
I&E. Workspace owns Working Set selection and the model-input boundary. It also
states that the first core has no model/embedding dependency and that
embeddings/vector/reranking follow only when measured retrieval failure
justifies them.

The active `opencti-exact-resource-retrieval/v1` contract is intentionally a
single existing OpenCTI object -> exact immutable Resource Version ->
Resource Capsule path. Its model/embedding-call budget is zero. It is neither a
RAG search system nor an embedding prototype.

The current Workspace context design keeps the logical context distinct from
owner state. Its provider projection has seven logical inputs: system
instructions, original user task, additional task context, Working Set, layered
Case Context, eligible Session history, and activated Tools. Tools remain in
the provider Tool channel, not prompt prose. The context compiler does not do
optional historical recall or vector search.

The first task-understanding step is deliberately a bounded no-Tool structured
model call. Investigation Run Control then owns later goal, Query Candidate,
capability and budget policy. Neither contract selects a model vendor or a
specific model name.

Sources:

- [I&E platform design](../intelligence-evidence/intelligence-evidence-platform-design.md)
- [Exact resource retrieval v1](../intelligence-evidence/opencti-exact-resource-retrieval-v1-contract.md)
- [I&E delivery state](../intelligence-evidence/PROGRESS.md)
- [Workspace language](../agent-workspace/CONTEXT.md)
- [Workspace Run Context Preparation v1](../agent-workspace/workspace-run-context-preparation-v1-contract.md)
- [Pre-Investigation Task Understanding v1](../agent-workspace/pre-investigation-task-understanding-v1-contract.md)
- [Investigation Run Control v1](../agent-workspace/investigation-run-control-v1-contract.md)

### 2.2 What current Pi supplies

Pi models carry provider identity, model identity, reasoning capability,
context-window size, output-token limit and cost metadata. The generic
Harness/Provider Dispatch path snapshots the resolved model, context, Tool
schemas, credentials and closed options before adapter start. Its Session
facilities include compaction and branch summaries; compaction is bounded by a
context-window reserve. Pi does not make a CTI judgement about which model is
appropriate, whether a retrieved Resource may be disclosed, or whether a
retrieval score is evidence.

Pi therefore already supplies a place to execute a selected model policy, but
does not contain one for CTI-RAG. The local CTI package has no configured
provider/model allow-list, embedding provider, reranker, search implementation,
or fallback policy at the time of this review.

Sources:

- [Pi model type](../../../packages/ai/src/types.ts)
- [Pi model registry](../../../packages/ai/src/models.ts)
- [Pi Harness](../../../packages/agent/src/harness/agent-harness.ts)
- [Pi compaction policy](../../../packages/agent/src/harness/compaction/compaction.ts)
- [Pi Provider Dispatch canonical input](../../../packages/agent/src/harness/provider-dispatch/canonical.ts)

### 2.3 Consequences already implied by local contracts

The following are current design implications, not new recommendations:

- A provider invocation must identify the actual resolved model and closed
  options in its logical input evidence; a model substitution is a different
  logical invocation.
- A later I&E embedding, reranker, chunker or index is a versioned derivative
  with exact inputs and method/configuration binding.
- A Retrieval Receipt records processing versions, index generation, declared
  coverage, ordered results and a result digest. Raw ranking scores are
  request-local; they are not confidence or evidence weight.
- Use eligibility, marking/licence/retention constraints and source status are
  checked before model disclosure. A high semantic score cannot repair a failed
  use decision.
- Session/Working Set/model output do not become Case authority merely because
  they are rendered into context.

## 3. What a model policy must decide

### 3.1 Separate roles before selecting a model

One product may use the same provider/model for several roles, but the policy
should assess the roles separately because their failure modes differ.

| Role | Current status | What success means | What must not be inferred |
| --- | --- | --- | --- |
| Task understanding | designed, later implementation-gated | structured normalization/ambiguity result respecting an immutable Original User Task | investigation plan, retrieval target, Tool choice or authority |
| Investigation loop | designed, no CTI vertical implemented | follows context labels, selects exposed Tools appropriately, reasons over qualified material and abstains when needed | Case conclusion or permission |
| Final response drafting | publication-gated design | satisfies output/citation requirements from supplied material | truth, Case acceptance or external publication |
| Session compaction / branch summary | generic Pi capability | preserves interaction continuity under bounded context policy | authoritative Case history or general Memory |
| Future extraction/query transformation | deferred I&E/Workspace choice | reproducible bounded derivative or request-local proposal | source fact, exact selector or autonomous retrieval authority |
| Future embedding/reranking | deferred I&E choice | rank eligible Retrieval Segments for a declared request | source reliability, corroboration, factual confidence or authorization |

This role table is a policy vocabulary, not a mandate to deploy multiple models
or multiple Agents.

### 3.2 Candidate acceptance criteria

Every selected model/provider combination should be evaluated against a
representative CTI-RAG fixture set, not chosen from a generic leaderboard.

1. **Protocol fit.** Required Tool calling, structured output, streaming,
   context size, image/PDF needs and cancellation behavior work through Pi's
   actual provider Adapter.
2. **Task quality.** The model meets task-specific correctness, grounding,
   uncertainty, citation and Tool-use metrics on held-out CTI cases.
3. **Context behavior.** It remains useful when shown bounded, labelled,
   potentially conflicting Resource Capsules and a growing eligible Session;
   it must not treat a large advertised context window as a licence to inject
   everything.
4. **Safety and governance.** Deployment/data-residency terms, retention,
   access controls, abuse/safety behavior and audit fields are compatible with
   the source-profile and Workspace disclosure constraints. A provider-side
   cache is itself a disclosure consideration.
5. **Operational fit.** Latency distribution, rate limits, outage behavior,
   observability and cost satisfy the Run's declared budgets.
6. **Reproducibility.** The resolved provider/model version, reasoning/output
   settings and prompt/tool projection can be bound in the logical invocation
   evidence. Alias-only selection is insufficient for a regression benchmark.
7. **Failure behavior.** Refusal, truncation, invalid structured output,
   Tool-call error, timeout and context overflow produce a bounded run outcome,
   never fabricated CTI content or silent ungrounded fallback.

OpenAI's current guidance independently recommends comparing reasoning effort
on representative workloads rather than assuming the highest setting is best,
and measuring task success, completeness, evidence, tokens, latency and cost.
It also recommends keeping only task-relevant Tools and lean prompts. Claude's
context documentation explicitly cautions that larger context does not
automatically improve accuracy or recall; all system messages, history, Tool
results and Tool definitions consume the window.

Sources:

- [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [Anthropic context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)

### 3.3 Routing and fallback: candidate policy

**Recommendation:** start with one qualified Investigation model configuration
and, separately, one qualified low-complexity configuration for the bounded
Task Understanding call only if evaluation demonstrates that split is useful.
Do not introduce routing by task labels, a cheapest-first cascade, or
multi-agent delegation as a default.

Reasons:

- the current architecture deliberately has one Pi Agent loop, one Workspace
  Harness and a bounded pre-run call rather than a planner/worker system;
- early product work lacks an accepted corpus and ground-truth evaluation to
  prove a complex router improves outcomes; and
- a model/provider change affects Tool behavior, context limits, costs,
  refusals and result quality simultaneously, making faults harder to assign.

**Recommendation:** no silent semantic fallback. A network retry of the same
prepared logical invocation is a transport concern. If an outage policy later
permits another provider/model, it must create a new prepared invocation and
new receipt/budget decision, keep the same owner-qualified input basis, and
mark the run outcome. It must not quietly reuse an output as if it came from
the original model. The policy must explicitly decide whether continuation,
user-visible failure or retry is safe for each role.

**Undecided product choices:** provider(s), geographic deployment, model
version-pinning rule, allowed aliases, reasoning effort per role, same-model
versus separate compaction model, fallback eligibility, and budget thresholds.

## 4. Context and token policy

### 4.1 A large context window is capacity, not retrieval policy

The current Workspace design is stronger than a "put all history into a large
window" approach: it reconstructs only mandatory qualified state, places each
kind of material in a defined channel, and separately admits bounded optional
recall. This preserves authorization, currentness, provenance and token
discipline.

The appropriate order is:

```text
current-owner reconstruction
-> eligibility / disclosure checks
-> bounded Working Set or qualified recall view
-> provider-context compilation
-> token/output reservation check
-> Pi Provider Dispatch
```

Compaction is continuity management, not source summarization. A compaction
summary must remain labelled Session history and cannot replace current Case
Context, Resource Capsules, or the current authorization fence.

### 4.2 Candidate budgeting approach

**Recommendation:** define a five-part budget envelope in the future Run
policy, with each limit measured from the final provider projection rather than
characters or estimates:

| Budget | Controls | Owner of the meaning |
| --- | --- | --- |
| input/context tokens | bounded selected context plus Tool definitions | Workspace/Pi |
| output + reasoning tokens | response quality, latency and provider cost | Workspace/Pi |
| Tool turns/calls/wall time | investigation exploration | Workspace Run Control |
| retrieval candidates/segments/bytes | discovery and disclosure volume | I&E plus Workspace policy |
| monetary/rate budget | provider and retrieval spend | Workspace policy/application |

When a budget is exceeded, policy should reduce optional/old context first,
preserving current authoritative inputs and source labels. It should not trim a
Resource Capsule into uncitable prose or silently drop a contradiction. The
model can be asked for a bounded answer or a stated insufficiency; it should
not receive a hidden arbitrary truncation.

Prompt caching can reduce repeated-input cost but does not reduce context-window
occupancy. Both Anthropic and OpenAI document cacheable prompt prefixes, while
Anthropic further documents that Tool definitions and Tool results occupy the
context window and that active-Tool changes can invalidate a cache prefix. This
supports stable core instructions/Tool surfaces, but cache configuration remains
a provider/disclosure policy choice, not an I&E retention mechanism.

Sources:

- [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Anthropic Tool context management](https://platform.claude.com/docs/en/agents-and-tools/tool-use/manage-tool-context)
- [Pi context preparation research](./pi-context-capability-reuse-audit-2026-07-22.md)

## 5. Later retrieval policy

### 5.1 Non-negotiable stage order

The retrieval pipeline is not merely "embed -> vector search -> paste results".
For a later bounded search request, the architecture's order should stay:

```text
trusted Workspace admission and scope/budget compilation
-> I&E eligibility filtering (principal, use, markings, licence, status)
-> candidate generation over one pinned Index Generation
-> optional fusion / reranking inside I&E
-> exact verification of selected current hits
-> I&E Retrieval Receipt + Resource Capsules
-> Workspace Working Set selection and pre-disclosure revalidation
-> model context
```

Eligibility must occur before relevance. A privileged or stale index must not
leak that a hidden Resource exists through a score, count, title, facet or
snippet. Model query suggestions remain target-neutral Query Candidates until
trusted Workspace policy admits a capability and I&E request.

### 5.2 Retrieval stages and their purpose

| Stage | Candidate role | What it buys | What it cannot establish |
| --- | --- | --- | --- |
| exact selector | active IER1 | correct known resource/version capture | semantic discovery |
| deterministic extraction + segments | later I&E | stable, citable searchable units | relevance or source truth |
| lexical index | first bounded search candidate | identifiers, IOC strings, CVEs, malware names, exact CTI syntax and transparent baseline | paraphrase/synonym recovery |
| dense embeddings | only after measured lexical miss | semantic and multilingual recall | authorization, evidence weight or source independence |
| hybrid rank fusion | candidate combination | resilience when lexical/dense find different material | comparable raw-score semantics |
| cross-encoder/LLM rerank | final ordering of a small eligible candidate set | query-specific ordering before context selection | coverage/completeness or factual truth |
| Workspace adoption | model-input selection | token-aware diversity, conflicts and task fit | an I&E ranking decision or Case conclusion |

The original RRF work gives a well-known rank-based combination method for
separate ranked lists. It is a possible later fusion baseline precisely because
it does not require treating BM25, vector similarity and reranker scores as the
same scale. Its suitability must still be tested on CTI-RAG data.

Sources:

- [Reciprocal Rank Fusion original paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)
- [I&E platform retrieval design](../intelligence-evidence/intelligence-evidence-platform-design.md)

### 5.3 Embeddings and rerankers: selection criteria, not a choice today

An embedding model should be selected only after a versioned Retrieval Segment
profile and an evaluation corpus exist. Candidate criteria are:

- language distribution of sources and analyst queries, including Chinese and
  English cross-lingual cases if they are in scope;
- CTI identifier, code-block, table and structured-field behaviour, not only
  natural-language similarity;
- query/document asymmetry and required query instruction/profile;
- segment length/truncation, vector dimension, batch throughput and hardware or
  external-disclosure constraints;
- licence/deployment/data-transfer fit;
- repeatability: model revision, tokenizer, preprocessing, dimensions,
  normalization and input template must all enter the Derivation Manifest;
- recall at the candidate depth that the next stage can afford; and
- evidence that it improves over the lexical baseline on held-out CTI fixtures.

The same applies to reranking. A reranker evaluates query-document pairs and
therefore has a different latency/context profile from an embedding model. It
should receive only a bounded eligible shortlist, and must be versioned and
evaluated as a ranking derivative. Cohere's public documentation illustrates
the query/document distinction for embeddings and the fact that reranking
combines each query with each candidate document. The BGE project's maintained
model list illustrates that a single family can expose dense, sparse,
multi-vector and cross-encoder variants. These are examples of design space,
not recommended dependencies.

Sources:

- [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings)
- [OpenAI embedding model documentation](https://developers.openai.com/api/docs/models/text-embedding-3-large)
- [Cohere embedding documentation](https://docs.cohere.com/docs/embeddings)
- [Cohere rerank documentation](https://docs.cohere.com/docs/rerank)
- [BGE/FlagEmbedding maintained model catalogue](https://github.com/FlagOpen/FlagEmbedding)

### 5.4 Query transformation and decomposition

Query rewriting, expansion and decomposition are distinct techniques. They may
raise recall, but in CTI they can also introduce invented aliases, dates,
entities or causal claims. The Query2doc paper demonstrates that LLM-generated
query expansion can improve retrieval benchmarks; this is evidence for testing
the technique, not permission to make generated text a source assertion.

**Candidate policy:** retain the current Query Candidate boundary. If a later
search evaluation proves a transformation helps, bind the original task,
transformation method/version, generated query terms, scope/budget and response
to the Retrieval Receipt/Trace. Transformations must be labelled request-local,
cannot become Case facts, cannot select exact backend identifiers, and must
never bypass owner eligibility. Compare them against original-query lexical
search, not only against a chosen vector model.

Source:

- [Query2doc original paper](https://arxiv.org/abs/2303.07678)

## 6. Grounding, citations and safe answers

### 6.1 Citation should bind to I&E material, not model confidence

An answer's citations should refer to the disclosed Resource Capsule / Resource
Version and its Source Span(s), retaining owner, source, version, time and
status. A bare URL, model-generated source name, Retrieval Receipt ID or
similarity score is not sufficient evidence for a proposition.

The Agent should distinguish at least:

- source observation or quoted material;
- a grounded analytic inference;
- a Candidate Finding or competing attribution hypothesis;
- missing/insufficient evidence; and
- an unavailable or excluded source due to policy, without leaking protected
  existence.

The I&E/Workspace contracts already establish the essential parts: Source
Spans, Resource Capsules, Retrieval Receipts, Model Input Receipts and a
publication gate. A later presentation format must consume those existing
objects; it should not make the model manufacture citations from memory.

### 6.2 Safe response rules

**Recommendation:** evaluate and enforce the following at Workspace publication
time, in addition to model prompting:

1. Each factual material claim has one or more compatible disclosed supporting
   spans, or is explicitly labelled analysis/uncertain.
2. Contradicting eligible material is represented or a bounded reason for its
   exclusion is recorded; do not silently select the most fluent source.
3. Retrieval relevance, source reliability, information credibility and Case
   acceptance remain separate labels/assessments.
4. A model refusal, safety block, Tool error, missing citation or unsupported
   output results in a withheld/partial/insufficient-evidence outcome according
   to the Run and publication policy, never a fabricated substitute.
5. Prompt-injected text inside a source is treated as untrusted content, not a
   system instruction, Tool activation or authorization grant.

This is consistent with Anthropic's Tool guidance that external Tool results
are untrusted content and should remain in the Tool-result channel rather than
be promoted to system instructions.

Source:

- [Anthropic Tool-use execution guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)

## 7. Evaluation and observability

### 7.1 Build CTI-RAG evaluation data before choosing the stack

Generic benchmarks are useful smoke tests but cannot validate Access-Principal-scoped CTI
authorization, source lineage, Case context, temporal drift, markings or the
project's definition of citation correctness. The first evaluation asset should
be a versioned, source-permitted CTI fixture set containing:

- exact known-resource requests for IER1;
- analyst questions with accepted relevant and irrelevant Retrieval Segments;
- IOC/CVE/malware/campaign/entity identifiers and controlled aliases;
- lexical and semantic paraphrase pairs;
- Chinese/English cases only if those languages are accepted scope;
- copied-report/source-lineage cases so repeated reporting is not counted as
  corroboration;
- contradictory, superseded, withdrawn, stale and no-result cases;
- authorization/Use-Purpose/marking changes and adversarially similar hidden
  material; and
- expected claim-to-span citations, abstentions, and non-authoritative language.

The fixture's Resource Versions, source profile and relevance labels need their
own governance. It must never copy protected production corpus content merely
to make a benchmark convenient.

### 7.2 Evaluate separate layers

| Layer | Example measures | Mandatory CTI safety checks |
| --- | --- | --- |
| exact retrieval | exact-version match, receipt/capsule integrity, completion/latency | zero wrong-principal/use disclosure; drift/withdrawal invalidates use |
| candidate retrieval | Recall@K, nDCG@K, MRR/precision where labels fit | no hidden-resource/count/score leakage; coverage/omission receipt is correct |
| reranking/fusion | nDCG@K and Recall@K compared to lexical baseline | result order is reproducible from the pinned generation/profile |
| query transformation | change in candidate recall and false-target rate | generated aliases/entities do not become source facts or widen scope |
| context adoption | useful coverage/diversity, token cost, contradiction retention | only current eligible material reaches the model |
| Agent/tool loop | task completion, correct Tool-use/abstention, bounded turns | no unauthorized call, scope expansion or unqualified result use |
| answer/publication | claim support precision/coverage, uncertainty/calibration, human review | no unsupported citation, Case-authority implication or raw withheld candidate disclosure |
| operations | p50/p95 latency, token/cost, error/retry rate, cache effectiveness | safe handling of provider failure, rate limit, overflow and cancellation |

TREC's RAG retrieval task reports nDCG and recall, confirming those as ordinary
retrieval-oriented measures. They should not be collapsed into one product
score, and they do not replace CTI-specific authorization and grounding tests.
Automated RAG evaluators such as RAGAS can be auxiliary diagnostic signals, but
their own authors describe multiple retrieval and generation dimensions; they
cannot certify Case truth or access control.

Sources:

- [NIST TREC RAG Retrieval task results](https://trec.nist.gov/pubs/trec34/appendices/trec2025-rag-retrieval.html)
- [RAGAS original paper](https://arxiv.org/abs/2309.15217)

### 7.3 Observability boundary

The I&E platform already calls for Access-Principal-safe metrics for duration, request
count/bytes, cache result, extraction/segment counts, index lag,
candidate/final count, cost units, terminal code and retries. It retains full
ranking features only as a bounded Retrieval Trace, while the immutable
Retrieval Receipt carries the durable result evidence. Workspace/Pi separately
bind the logical provider invocation and publication decision.

**Recommendation:** correlate, but do not merge, these records by stable run
and receipt references:

```text
Task / Agent Run
  -> Query Candidate and capability-admission outcome
  -> I&E Retrieval Receipt (+ bounded Retrieval Trace)
  -> Working Set / disclosure validation
  -> Pi logical provider invocation
  -> Tool outcomes and Run disposition
  -> Workspace publication decision
```

This supports diagnosis of a poor answer as retrieval miss, lost citation,
context-budget pressure, model reasoning failure, Tool failure or publication
rejection without turning telemetry into a new Memory or evidence store.

## 8. Decisions that should remain open

The following must be chosen by a future accepted product slice, after the
first relevant fixture/evaluation work:

- primary provider and concrete model version(s);
- model deployment, data residency, cache and retention terms;
- model-role split, if any; reasoning/output budget profiles; and fallback
  policy;
- corpus languages and multimodal/file scope;
- Retrieval Segment profile, lexical analyzer and Index Generation profile;
- whether dense retrieval, hybrid fusion and reranking meet a measured need;
- candidate embedding/reranker model, hosting, dimension and upgrade policy;
- query transformation/decomposition profile;
- numeric quality, safety, latency and cost gates; and
- citation rendering and human review controls.

None of these is a prerequisite to the current IER1 exact-retrieval core or the
no-Tool Workspace vertical. They are prerequisites to a future bounded-search
activation, because that is when model choice starts affecting discovery and
disclosure semantics.

## 9. Recommended delivery sequence

1. Complete and verify the authorized IER1 exact resource vertical with its
   zero-model/zero-embedding rule.
2. Complete the gated no-Tool Workspace/Pi context and publication vertical.
3. Establish a source-permitted, versioned CTI evaluation fixture set and a
   model-role qualification harness using fake/provider-safe execution.
4. Qualify one Investigation model configuration against task understanding,
   Tool protocol, grounded answer, token, latency, safety and failure fixtures.
5. Add deterministic file/text extraction and Source Span validation.
6. Add lexical bounded search with pinned Index Generation and Retrieval
   Receipt/Trace evaluation.
7. Only if lexical metrics identify material recall/ranking gaps, run an
   evidence-backed comparison of dense, hybrid and/or reranking candidates.
8. Adopt only the smallest stage that meets the defined improvement and safety
   gate; record the selected method/version in I&E derivation and retrieval
   evidence.

This is a research recommendation. It does not authorize implementation of a
search engine, embedding service, model router, vector database, second Agent,
or a new bounded context.
