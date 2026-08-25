# Mem0 Primary-Source Audit for CTI-RAG Memory

Status: primary-source audit and non-normative research input.

Research date: 2026-07-22.

Code basis: Mem0 official repository commit
[`ca2abca2b884e038d3e525070e79d3057ef2012c`](https://github.com/mem0ai/mem0/tree/ca2abca2b884e038d3e525070e79d3057ef2012c),
observed on 2026-07-22. Mem0 Platform and OSS behavior are not identical, and
Mem0's v2 paper, older concept pages, current v3 migration guide, and current
source do not describe one stable algorithm. Claims below identify the version
or surface to which they apply.

Design disposition: **use Mem0 as a reference for candidate extraction,
identity-scoped retrieval, explicit lifecycle operations, and retrieval
evaluation; do not adopt Mem0's word “memory” as an umbrella owner for CTI-RAG
state, and do not treat Mem0 recall as an authority or authorization system.**
Mem0 does not remove the need for the existing Case Management, Agent
Investigation Workspace, Pi Session, and Intelligence and Evidence owners. It
also does not by itself prove that CTI-RAG needs a new Memory Module.

This note does not define a schema, database, vector index, automatic write
path, Module, or implementation Interface. It does not change a normative
contract and does not address context assembly or multi-Agent coordination.

## 1. Executive findings

1. Mem0 is primarily an application-facing long-term conversational memory
   layer. Its documentation uses both lifecycle layers—conversation, session,
   user, organization—and cognitive content labels—factual, episodic, semantic.
   These are useful product vocabulary, but the current implementation does not
   enforce them as a closed business taxonomy.
2. Mem0's current v3 algorithm is materially different from the architecture in
   its 2025 paper. The paper describes LLM-selected `ADD`, `UPDATE`, `DELETE`,
   and `NOOP`; current v3 extraction is single-pass, `ADD`-only, preserves old
   and new memories, and shifts temporal conflict handling toward retrieval.
3. Mem0 does not decide whether an application query should consult memory. The
   caller invokes `search`; official examples commonly search before each model
   answer. Therefore retrieval triggering remains an application policy.
4. Mem0 scopes writes and reads with `user_id`, `agent_id`, `app_id`, and
   `run_id`, plus metadata filters. These are useful partitions, not proof of
   current actor authorization, purpose eligibility, Case membership, Case
   Revision, Resource Version, or provenance.
5. Current retrieval combines semantic similarity, keyword/BM25, entity
   matching, and, on the Platform, temporal signals and optional reranking or
   decay. Relevance scores express retrieval fit, not factual confidence or
   authority.
6. Mem0 includes useful safeguards—source-role attribution, prompt rules against
   context contamination, exact-hash deduplication, immutable identity fields in
   OSS updates, expiry hiding, explicit update/delete, and feedback. They do not
   make LLM extraction fact-safe. Mem0's own ingestion cookbook demonstrates
   that an unqualified “I think I might be allergic” can be stored as a confirmed
   allergy unless application-specific instructions intervene.
7. Mem0's current extractor deliberately treats agent-generated information as
   first-class and instructs extraction broadly, including researched facts,
   recommendations, shared documents, and implicit preferences. That default is
   unsuitable for CTI, where model output must remain non-authoritative and
   source material, analytic hypotheses, Case judgments, and preferences have
   different owners and eligibility rules.
8. Mem0's published benchmark evidence is evidence for conversational recall
   quality, latency, and token efficiency—not for CTI provenance, access
   control, correction semantics, or safe use of contradictory intelligence.

## 2. What Mem0 calls memory

### 2.1 Documented layers

Mem0's current memory-types page distinguishes:

- conversation memory: in-flight turn material;
- session memory: short-lived facts for a task or channel;
- user memory: long-lived knowledge tied to a person, account, or workspace;
- organizational memory: shared context for agents or teams; and
- within long-term memory, factual, episodic, and semantic memory.

It maps `run_id` to short-lived session scope and `user_id` to lasting
personalization. It also warns that user and organizational memory require
consent/governance and that secrets or unredacted PII should not be stored in a
system designed for retrieval.
[Mem0 memory types](https://docs.mem0.ai/core-concepts/memory-types)

These labels mix three different dimensions:

| Dimension | Mem0 examples |
|---|---|
| lifetime | conversation, session, long-term |
| audience/identity | user, agent, application, organization |
| information shape | factual, episodic, semantic, procedural |

The current OSS code only gives special creation behavior to
`procedural_memory`; ordinary extracted memories are natural-language records
whose meaning is carried by text, identity fields, timestamps, and arbitrary
metadata. Consequently, the documentation's classification is a conceptual
guide rather than a closed, enforced ontology.
[OSS `Memory.add`](https://github.com/mem0ai/mem0/blob/ca2abca2b884e038d3e525070e79d3057ef2012c/mem0/memory/main.py#L735-L847),
[procedural-memory path](https://github.com/mem0ai/mem0/blob/ca2abca2b884e038d3e525070e79d3057ef2012c/mem0/memory/main.py#L1949-L1986)

### 2.2 CTI interpretation

The documented layers must not be copied onto CTI owners by name:

- Mem0 “session memory” is not Pi Session authority.
- Mem0 “user memory” is not Case State or an actor's authorization state.
- Mem0 “organizational memory” is not an I&E Resource collection.
- Mem0 “episodic memory” does not automatically authorize cross-Case recall of
  Workspace Artifacts or Agent experience.
- Mem0 graph entities are retrieval links extracted from text, not typed CTI
  entities, source provenance, or accepted Case relationships.

The useful idea is to keep lifetime, audience, and content kind separate. The
unacceptable move is to make those labels a new umbrella ownership hierarchy.

## 3. Write, extraction, change, and deletion

### 3.1 Current v3 extraction

Current Platform documentation and current OSS source describe a pipeline that:

1. receives messages after an Agent response;
2. looks up recent messages and related existing memories;
3. uses one LLM call to distill new natural-language memories;
4. performs exact-hash deduplication and embedding;
5. links extracted entities; and
6. records add history.

The v3 extractor is `ADD`-only. Existing memories are supplied to the LLM for
deduplication and linking, not as permission to overwrite or delete them. The
source maps database UUIDs to short numeric identifiers before showing them to
the model, described in code as an anti-hallucination measure. With
`infer=False`, messages other than system messages are stored directly and
automatic extraction/deduplication is bypassed.
[Mem0 evaluation architecture](https://docs.mem0.ai/core-concepts/memory-evaluation),
[current OSS add pipeline](https://github.com/mem0ai/mem0/blob/ca2abca2b884e038d3e525070e79d3057ef2012c/mem0/memory/main.py#L849-L1054)

The extraction prompt is intentionally recall-maximizing. It asks the model to
extract broadly from both user and assistant messages, including preferences,
plans, emotional states, shared documents, researched information,
recommendations, and implicit preferences; when uncertain it favors extraction.
It does include useful constraints: user statements are primary when the
assistant merely echoes them, vague characterizations should be skipped,
relative time should be grounded to an observation date, and details from old
context must not contaminate a new extraction.
[current additive extraction prompt](https://github.com/mem0ai/mem0/blob/ca2abca2b884e038d3e525070e79d3057ef2012c/mem0/configs/prompts.py#L468-L920)

### 3.2 Explicit update and deletion still exist

`ADD`-only describes automatic extraction, not the complete management API.
Mem0 still exposes explicit update and delete operations:

- update replaces stored text or metadata by memory ID and adjusts indexes;
- current OSS preserves creation time, changes update time, records history,
  and prevents update metadata from changing `user_id`, `agent_id`, `run_id`,
  or `actor_id`;
- delete removes one memory by ID;
- filtered/bulk deletion removes memories in a selected identity or metadata
  scope; and
- history returns recorded changes for a memory.

[Mem0 update](https://docs.mem0.ai/core-concepts/memory-operations/update),
[Mem0 delete](https://docs.mem0.ai/core-concepts/memory-operations/delete),
[current OSS lifecycle operations](https://github.com/mem0ai/mem0/blob/ca2abca2b884e038d3e525070e79d3057ef2012c/mem0/memory/main.py#L1785-L1915)

### 3.3 Version conflict in official material

The 2025 Mem0 paper describes a different two-pass design. After candidate fact
extraction, an LLM compares each fact with similar memories and chooses
`ADD`, `UPDATE`, `DELETE`, or `NOOP`. The current v3 migration guide explicitly
replaces that mutation model with single-pass `ADD`-only extraction, preserving
both old and new facts and resolving which is current during retrieval.
[Mem0 paper](https://arxiv.org/abs/2504.19413),
[Platform v2-to-v3 migration](https://docs.mem0.ai/migration/platform-v2-to-v3)

Some general operation pages still say automatic conflict resolution makes the
latest truth win, while the v3 migration and current source say memories
accumulate. The safe research conclusion is not to infer a stable semantic
contract from “Mem0” generally; any future experiment would have to pin the
exact Platform API generation or OSS commit.

## 4. Retrieval trigger and recall behavior

### 4.1 Who decides to retrieve?

Mem0 provides `search`; it does not determine whether the current application
query needs memory. The official repository's minimal chat example calls
`search(query=user_message, user_id=...)` on every turn, inserts the returned
memories into a system prompt, then sends the completed exchange to `add`.
[official repository example](https://github.com/mem0ai/mem0/blob/ca2abca2b884e038d3e525070e79d3057ef2012c/README.md#L460-L494)

Therefore “retrieve on every query” is an integration example, not a Mem0
requirement or a proven product policy. Query routing, abstention, authorization,
and whether recalled material is useful for the task remain the application's
responsibility.

### 4.2 How candidates are recalled

Current OSS search requires at least one of `user_id`, `agent_id`, or `run_id`
inside filters. It then:

1. validates query, `top_k`, threshold, and identity filters;
2. embeds the query and performs semantic search;
3. optionally obtains keyword/BM25 results;
4. extracts query entities and computes entity boosts;
5. filters expired records unless explicitly requested;
6. fuses signals, applies a threshold, and returns top-K; and
7. optionally reranks when a reranker is configured.

[Mem0 search guide](https://docs.mem0.ai/core-concepts/memory-operations/search),
[current OSS search](https://github.com/mem0ai/mem0/blob/ca2abca2b884e038d3e525070e79d3057ef2012c/mem0/memory/main.py#L1349-L1492),
[current OSS multi-signal ranking](https://github.com/mem0ai/mem0/blob/ca2abca2b884e038d3e525070e79d3057ef2012c/mem0/memory/main.py#L1598-L1701)

The Platform adds richer metadata filters, built-in entity linking, temporal
reasoning, managed rerankers, and optional memory decay. None of these signals
establishes that a returned statement is true, authorized for the present
purpose, or applicable to the current Case.

## 5. Scope and identity

Mem0 Platform distinguishes four application identifiers:

| Identifier | Documented intent |
|---|---|
| `user_id` | persistent person/account memory |
| `agent_id` | distinct Agent persona or tool |
| `app_id` | application/product surface |
| `run_id` | short-lived ticket, session, experiment, or flow |

Writes and reads use these identifiers plus metadata. Current Platform
documentation also describes null scoping and separate per-entity records;
current OSS requires one or more of user/agent/run for operations and treats
identity fields as immutable after creation.
[Mem0 entity-scoped memory](https://docs.mem0.ai/platform/features/entity-scoped-memory),
[current OSS scope construction](https://github.com/mem0ai/mem0/blob/ca2abca2b884e038d3e525070e79d3057ef2012c/mem0/memory/main.py#L298-L397)

This is useful partitioning, but it is not a complete CTI eligibility decision.
The cited Mem0 records do not natively prove:

- the currently authenticated actor and tenant;
- the permitted investigation purpose;
- Case and Task membership;
- the Case Revision or Workspace generation used when the statement arose;
- exact I&E Resource Version or source capture;
- current source withdrawal, use disposition, or marking;
- the authority that admitted or corrected the claim; or
- whether the current caller may see the source material.

Research inference: CTI-RAG could use Mem0-like identity filtering as one input
to eligibility, but never as the authorization decision itself.

## 6. Time, conflicts, expiry, and correction

### 6.1 Current facts versus history

V3 preserves old and new memories instead of automatically mutating an old
record. Platform temporal reasoning adds event/state/plan/preference-style time
metadata and nudges ranking toward the dated instance that matches the query.
The documentation itself reports that knowledge updates remain the hardest
category for an additive architecture because prior facts may still surface.
[Mem0 evaluation](https://docs.mem0.ai/core-concepts/memory-evaluation),
[v3 migration](https://docs.mem0.ai/migration/platform-v2-to-v3)

This preserves conversational history, but ranking is not equivalent to CTI
correction or revision semantics. A superseded fact that remains retrievable
must not silently compete with a current Case view or current I&E version.

### 6.2 Expiry and decay

Current operation documentation and OSS source support an expiration date that
hides expired memories from search and bulk reads by default while allowing an
explicit request to show them. Platform v3 migration documentation, however,
lists `expiration_date` among removed client parameters, which is further
evidence that version-specific behavior must be pinned.
[Mem0 add](https://docs.mem0.ai/core-concepts/memory-operations/add),
[Platform migration](https://docs.mem0.ai/migration/platform-v2-to-v3),
[current OSS expiry check](https://github.com/mem0ai/mem0/blob/ca2abca2b884e038d3e525070e79d3057ef2012c/mem0/memory/main.py#L402-L426)

Platform memory decay is an optional search-time popularity/recency bias. A
returned memory is reinforced; old unused memories are dampened but never
filtered out, with the documented scaling bounded between `0.3x` and `1.5x`.
[Mem0 memory decay](https://docs.mem0.ai/platform/features/memory-decay)

That behavior is unsuitable as a CTI validity policy: frequent retrieval can
reinforce a mistaken or merely popular memory, and lack of recent access does
not make a threat fact, analytic method, or legal restriction obsolete.

## 7. Factuality and hallucination control

### 7.1 Controls Mem0 actually provides

Verified controls in official material include:

- extraction instructions intended to remain faithful to new messages;
- role/source attribution such as `attributed_to`;
- temporal grounding to an observation date;
- exact-hash deduplication and entity linking;
- UUID aliasing before LLM extraction;
- metadata filters, thresholds, top-K, optional reranking, and explainable OSS
  score components;
- explicit update, delete, feedback, and history operations; and
- custom instructions that can restrict what the extractor stores.

Platform feedback records positive or negative judgments on a memory and says
feedback is used to improve generation and search. It does not by itself change
the underlying statement's business authority.
[Mem0 feedback](https://docs.mem0.ai/platform/features/feedback-mechanism)

### 7.2 What these controls do not prove

Mem0's own controlled-ingestion cookbook shows the baseline failure directly:
without custom instructions, “I think I might be allergic to penicillin” can be
stored as “Patient is allergic to penicillin.” The recommended mitigation is a
project-specific extraction instruction and application-managed confidence
gate, not an intrinsic provenance proof.
[Mem0 controlling ingestion](https://docs.mem0.ai/cookbooks/essentials/controlling-memory-ingestion)

Further limits established by the sources:

- the extractor is an LLM, and current v3 intentionally stores assistant-
  generated recommendations, researched information, actions, and agreements;
- the normal memory text does not carry an exact source span, I&E Resource
  Version, Case Revision, evidence status, or independent verification result;
- retrieval `score` is relevance/ranking, not confidence that the text is true;
- exact-hash deduplication cannot detect paraphrased contradictions or establish
  which statement is authoritative;
- custom instructions are prompt policy and may fail; and
- explicit correction/deletion requires the application or user to identify
  the affected memory and possess the right management authority.

The 2025 paper evaluates long multi-session personal conversations on LoCoMo.
It reports recall, latency, and token improvements, but excludes LoCoMo's
adversarial/unanswerable category because ground-truth answers were unavailable.
It does not evaluate actor/purpose authorization, CTI source provenance,
classification markings, Case correction, or malicious memory admission.
[Mem0 paper](https://arxiv.org/abs/2504.19413)

## 8. Relationship to existing CTI-RAG owners

### 8.1 Useful ideas by owner

| Existing owner | Mem0 idea worth studying | Required CTI qualification |
|---|---|---|
| Pi Session | bounded recent-message continuity and compaction inputs | Pi Session remains interaction/recovery history, not truth or cross-Case memory |
| Agent Workspace | caller-controlled decision to retrieve; top-K/threshold/budget; explicit abstention; non-destructive candidate history | Workspace must qualify actor, purpose, Case, versions, validity, and authority before relevance ranking or model rendering |
| Case Management | explicit correction and visible history are important | Case correction must use Case-owned revision/acceptance semantics, not memory overwrite or latest-ranked text |
| I&E | hybrid retrieval and entity-assisted recall can improve discovery | I&E retains exact Resource identity, versions, provenance, markings, withdrawal, and use authority; Mem0 graph links are not substitutes |
| conditional residual experience/preference capability | candidate extraction, origin attribution, explicit feedback/update/delete, scope filters | only relevant if a real cross-Case/cross-Workspace requirement passes the existing owner test; model extraction cannot self-admit |

### 8.2 Defaults that should not be imported into CTI

Do not import these Mem0 defaults as CTI behavior:

1. **Store after every response.** CTI persistence must occur only at an
   owner-controlled qualification or save point.
2. **When in doubt, extract.** CTI should prefer non-admission or abstention when
   source, authority, sensitivity, or applicability is unresolved.
3. **Assistant facts have equal weight.** A model statement, recommendation, or
   claimed tool action cannot become Case authority, I&E Resource, or durable
   experience merely because the assistant emitted it.
4. **User/agent/run identity is authorization.** Those identifiers are useful
   scope keys only.
5. **Newest or most relevant statement is current truth.** Case Revision,
   source-version status, and explicit correction/withdrawal govern current use.
6. **Shared documents become memories.** Source material belongs under I&E
   provenance or remains task input; extracted summaries cannot replace it.
7. **Organizational memory is shared policy or intelligence.** Product policy
   and I&E knowledge retain their own owners and review paths.
8. **Graph links are domain relationships.** Extracted text entities and shared
   mentions are retrieval aids, not accepted CTI objects or analytic findings.
9. **Decay is validity.** Access frequency must not decide whether CTI content is
   valid, permitted, or current.
10. **Every query searches all memory.** The application must decide whether
    memory is needed, which owner/scope is eligible, and whether zero recall is
    safer.

## 9. Direct answers for the Memory requirements study

| Question | Primary-source conclusion and CTI disposition |
|---|---|
| What does Mem0 store? | Extracted conversational statements plus metadata and identity scope; conceptually conversation/session/user/org and factual/episodic/semantic. This is not a closed CTI content taxonomy. |
| How is worth-saving information judged? | Primarily by an LLM extraction prompt, optional custom instructions, direct-import choice, and later feedback. That is a candidate-generation mechanism, not sufficient CTI admission authority. |
| When is it written? | Platform describes asynchronous post-response extraction; OSS writes when the caller invokes `add`. CTI should not infer an automatic every-turn policy. |
| How are conflicts handled? | Paper/v2 used LLM-selected CRUD; v3 preserves both statements and relies more on temporal/multi-signal retrieval. Explicit update/delete remain management operations. Neither approach equals Case correction. |
| How is it retrieved? | Caller-issued search, identity/metadata filters, semantic + keyword + entity signals, optional temporal scoring/reranking/decay, threshold and top-K. Eligibility and authorization remain outside Mem0. |
| Does Mem0 decide whether to retrieve? | No. The application calls search; examples commonly do so every turn. CTI needs its own retrieval trigger and abstention policy. |
| Does a result prove truth? | No. Score is relevance; extraction can turn speculation into fact, and assistant output is intentionally extractable. |
| Does scope prove access? | No. `user_id`/`agent_id`/`app_id`/`run_id` partition records but do not model CTI actor-purpose authorization or source markings. |
| Does Mem0 cover Case/Session/Workspace/I&E? | No. It overlaps some persistence and retrieval mechanics but does not own their business meanings. Replacing them would erase authority boundaries. |
| Does Mem0 prove an independent CTI Memory Module is needed? | No. It proves that a reusable extraction/recall product can exist, not that CTI-RAG currently has an orphan business owner. |

## 10. Research recommendations

These recommendations are non-normative:

1. Treat Mem0 as a **reference algorithm and evaluation baseline**, not as the
   CTI domain model.
2. If a future memory experiment is authorized, pin one Mem0 version/surface and
   test it on CTI-specific admission, correction, authorization, staleness,
   contradiction, and source-provenance cases; do not rely on LoCoMo scores.
3. Separate three decisions that Mem0's vocabulary tends to blend:
   information kind, authorized audience/scope, and lifecycle/validity.
4. Let models propose memory candidates only. Existing business owners—or a
   later proven residual owner—must decide admission, correction, withdrawal,
   deletion, and current-use eligibility.
5. Apply hard scope, authorization, source-version, Case-revision, marking, and
   expiry/withdrawal qualification before semantic relevance ranking.
6. Make “no eligible memory” a valid outcome. Compare any memory-assisted path
   with a no-memory baseline and measure false, stale, unauthorized, and
   anchoring outcomes in addition to recall accuracy, latency, and token use.
7. Keep the current owner test unchanged: same-Case continuity and search over
   existing Session/Workspace records do not alone justify an independent
   Memory owner. Reopen that decision only for a proven, governed residual
   cross-Case or cross-Workspace need.

## 11. Evidence classification

To prevent research recommendations from being mistaken for current design:

- **Mem0 implemented/documented facts:** sections 2 through 7, where each claim
  is tied to the named Platform generation, OSS commit, official documentation,
  or paper.
- **CTI deductions:** the negative mappings and owner relationships in sections
  2.2, 5, 6, 7.2, and 8.
- **Research recommendations:** section 10.
- **Undecided product choices:** whether CTI-RAG will support cross-Case analytic
  experience, cross-Workspace preferences, or any independent residual Memory
  capability; who would own it; and when recall would be activated.

## 12. Primary sources

- [Mem0 official documentation index](https://docs.mem0.ai/llms.txt)
- [Mem0 memory types](https://docs.mem0.ai/core-concepts/memory-types)
- [Mem0 add](https://docs.mem0.ai/core-concepts/memory-operations/add)
- [Mem0 search](https://docs.mem0.ai/core-concepts/memory-operations/search)
- [Mem0 update](https://docs.mem0.ai/core-concepts/memory-operations/update)
- [Mem0 delete](https://docs.mem0.ai/core-concepts/memory-operations/delete)
- [Mem0 entity-scoped memory](https://docs.mem0.ai/platform/features/entity-scoped-memory)
- [Mem0 memory decay](https://docs.mem0.ai/platform/features/memory-decay)
- [Mem0 feedback](https://docs.mem0.ai/platform/features/feedback-mechanism)
- [Mem0 memory evaluation](https://docs.mem0.ai/core-concepts/memory-evaluation)
- [Mem0 Platform v2-to-v3 migration](https://docs.mem0.ai/migration/platform-v2-to-v3)
- [Mem0 controlled-ingestion cookbook](https://docs.mem0.ai/cookbooks/essentials/controlling-memory-ingestion)
- [Mem0 official repository, pinned commit](https://github.com/mem0ai/mem0/tree/ca2abca2b884e038d3e525070e79d3057ef2012c)
- [Mem0 paper, arXiv:2504.19413](https://arxiv.org/abs/2504.19413)
