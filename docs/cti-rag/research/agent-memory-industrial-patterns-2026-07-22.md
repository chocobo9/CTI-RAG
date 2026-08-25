# Agent Memory Industrial Patterns for CTI-RAG

Status: primary-source review and non-normative research input.

Research date: 2026-07-22.

Design disposition: **use mature systems as a pattern library, not as a single
reference architecture.** Keep Case Management, Agent Investigation Workspace,
Pi Session, and Intelligence and Evidence as separate owners. Improve the
clarity of the existing design by separating memory content kind, scope,
lifecycle, write policy, retrieval trigger, qualification, and context use.

This note does not define a Memory Module, schema, database, vector index,
automatic write path, or implementation Interface. It does not change a
normative contract and does not design the broader context compiler or
multi-Agent topology.

## 1. Research question

The useful question is not which product CTI-RAG should copy. It is which
industrial patterns answer the product questions raised in the design
discussion:

- what information should persist;
- how the system decides that it is worth retaining;
- when extraction and consolidation occur;
- whether every query should retrieve memory;
- how search scope, ranking, time, and conflicts are handled;
- what is placed back into model context;
- who can inspect, correct, withdraw, and delete retained material; and
- which controls remain outside model-visible memory.

The compared systems are Mem0, Claude and Claude Code, LangGraph/LangMem,
Letta, Zep/Graphiti, Amazon Bedrock AgentCore Memory, and Google ADK.

## 2. Current CTI-RAG baseline

Current documented design already assigns different persistent meanings:

| Meaning | Current owner |
|---|---|
| authoritative investigation state and revision history | Case Management |
| interaction history, branches, compaction, and Agent Run recovery | Pi Session |
| task-scoped Working Set and persistent non-authoritative analysis | Agent Investigation Workspace |
| reusable sources, versions, provenance, derivatives, and retrieval evidence | Intelligence and Evidence |

The comparison therefore tests mechanisms, not whether these owners should be
renamed or replaced.

## 3. Industrial patterns

### 3.1 Mem0: extraction and retrieval layer between application and model

Mem0 receives conversation turns through `add`, extracts or directly stores
memory records, and exposes `search`; the application decides which returned
records enter the model prompt. Current retrieval combines scoped filters with
semantic, keyword, entity, temporal, and optional reranking signals. Current v3
automatic extraction is additive rather than automatic last-write-wins.

Useful patterns:

- candidate extraction separate from model response generation;
- identity and metadata filters before relevance ranking;
- explicit update, delete, feedback, and history operations;
- multi-signal retrieval and measurable token/latency trade-offs.

Limits for CTI:

- extraction is LLM-driven and can convert speculation into a fact;
- identity partitions are not actor/purpose authorization;
- relevance scores are not factual confidence or authority;
- assistant-produced research and recommendations may be retained;
- additive temporal ranking is not Case correction or Resource withdrawal.

Sources: [how Mem0 works](https://docs.mem0.ai/core-concepts/how-it-works),
[memory operations](https://docs.mem0.ai/core-concepts/memory-operations/add),
[search](https://docs.mem0.ai/core-concepts/memory-operations/search), and the
[CTI-RAG Mem0 audit](./mem0-primary-source-audit-2026-07-22.md).

### 3.2 Claude: separate explicit instructions, automatic notes, and history search

Claude exposes several distinct mechanisms rather than one undifferentiated
memory:

- Claude chat memory uses categorized entries derived from chats;
- project memory is isolated from non-project memory;
- previous-chat search is an explicit RAG tool action with source-chat
  citations;
- Claude Code `CLAUDE.md` files contain human-maintained persistent
  instructions at organization, user, project, local, and path-specific scope;
- Claude Code automatic memory contains model-written project learning and
  preferences;
- a small `MEMORY.md` index is loaded at startup while detailed topic files are
  read on demand; and
- users can inspect, edit, delete, pause, reset, or bypass memory.

Claude Code explicitly says these memory files are context, not enforced
configuration. Hooks, settings, sandboxing, and permissions remain separate
enforcement mechanisms.

Useful patterns:

- separate human-controlled rules from model-learned experience;
- explicit scope hierarchy and project isolation;
- small always-loaded index plus lazy detailed recall;
- user-visible and editable memory;
- no-read/no-write mode for sensitive or temporary work;
- source-chat citations for historical retrieval;
- keep hard policy outside advisory model context.

Limits for CTI:

- model judgment that a note will be useful later is not sufficient admission;
- project scope does not express Case Revision, Resource Version, marking, or
  purpose;
- current Claude help says deleting an originating conversation does not
  automatically remove derived memory entries;
- model-written Markdown remains advisory and can be stale or wrong.

Sources: [Claude Code memory](https://code.claude.com/docs/en/memory),
[Claude chat search and memory](https://support.claude.com/en/articles/11817273-use-chat-search-and-memory-to-build-on-previous-context),
and [Claude projects](https://support.claude.com/en/articles/9519177-how-can-i-create-and-manage-projects).

### 3.3 LangGraph and LangMem: orthogonal memory type and write timing

LangGraph distinguishes thread-scoped short-term state from long-term records
stored under custom namespaces. Its documentation classifies long-term memory
as semantic facts, episodic experiences, and procedural instructions. It also
treats hot-path writes and background writes as separate choices rather than a
single required lifecycle.

Useful patterns:

- type, scope, and write timing are independent dimensions;
- hot-path memory provides immediate availability but adds latency and puts
  extraction in the user request path;
- background consolidation reduces latency but introduces eventual
  consistency and delayed correction;
- namespace design belongs to the application;
- long-term memory has no one-size-fits-all policy.

CTI implication: a settled Run may generate candidates immediately while
qualification or consolidation occurs later, but neither timing grants
authority. Session save points and owner admission remain distinct.

Sources: [LangGraph memory overview](https://docs.langchain.com/oss/python/concepts/memory)
and [LangChain long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory).

### 3.4 Letta: model-visible working memory with explicit archival search

Letta treats memory as part of the Agent runtime. Small persistent memory blocks
are kept in the Agent's active context and may be edited by the Agent; larger
archival memory and conversation history are searched on demand.

Useful patterns:

- reserve scarce active context for a small, structured working set;
- keep large historical material outside the context window;
- allow explicit memory read/write actions rather than hiding all mutation;
- separate conversation search from archival knowledge search.

Limits for CTI:

- an Agent editing its own core memory is acceptable for a persona or working
  note, not for Case authority, I&E truth, authorization, or compliance rules;
- active blocks can create strong anchoring if stale content is always present;
- the runtime-centered owner model does not match CTI's business authorities.

Sources: [Letta memory overview](https://docs.letta.com/guides/agents/memory)
and [Letta memory blocks](https://docs.letta.com/guides/agents/memory-blocks).

### 3.5 Zep and Graphiti: temporal graph with preserved history

Zep uses Graphiti to build temporal graphs from episodes. Facts are represented
with entities and relationships plus validity intervals; when relationships
change, older facts can be invalidated while remaining available as history.
Retrieval combines semantic, full-text, and graph signals.

Useful patterns:

- distinguish when a fact was observed from when it was valid in the world;
- preserve superseded history without presenting it as current;
- represent contradiction and invalidation explicitly;
- use graph structure as a retrieval aid for multi-hop questions.

Limits for CTI:

- LLM-extracted graph edges are not accepted CTI entities or relationships;
- temporal invalidation does not replace Case Revision or I&E source status;
- graph connectivity is not authorization or evidentiary weight;
- CTI already has OpenCTI/I&E graph ownership, so a second extracted truth
  graph risks duplication.

Sources: [Zep graph overview](https://help.getzep.com/graph-overview),
[Graphiti documentation](https://help.getzep.com/graphiti/getting-started/welcome),
and the [Zep/Graphiti paper](https://arxiv.org/abs/2501.13956).

### 3.6 Amazon Bedrock AgentCore Memory: distinct extraction strategies

AgentCore separates raw session events from long-term records and supplies
different long-term strategies: semantic facts, session summaries, user
preferences, episodic experience, and custom strategies. Strategy prompts have
separate extraction, consolidation, and reflection stages. Actor, session, and
namespace scope organize records.

Useful patterns:

- do not force facts, preferences, summaries, and experience through one
  extraction policy;
- treat extraction, consolidation, and reflection as distinct decisions;
- expose `Add`, `Update`, and `Skip` outcomes during consolidation;
- preserve a raw event basis separately from derived long-term records;
- allow application-specific strategies rather than a universal extractor.

Limits for CTI:

- built-in strategies are optimized for conversational personalization;
- actor and namespace isolation still do not prove CTI authorization;
- episodic prompts include thoughts and reasoning processes, which CTI-RAG
  must not preserve as authoritative memory or expose as chain of thought;
- managed extraction remains model-generated and requires owner qualification.

Sources: [AgentCore memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-memory.html),
[built-in strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/built-in-strategies.html),
and [strategy configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-configuring-built-in-strategies.html).

### 3.7 Google ADK: preload versus Agent-triggered recall

Google ADK separates Session/State from a `MemoryService`. It supports adding a
completed Session, incremental events, or explicit entries to long-term memory.
For recall it exposes both preload-at-turn-start and an Agent-invoked
`load_memory` tool.

Useful patterns:

- retrieval trigger is an explicit product choice;
- deterministic preload suits small, always-needed material;
- tool-triggered recall suits optional historical dependencies;
- session ingestion, event ingestion, and curated entry ingestion are
  different write paths.

Limits for CTI:

- automatically ingesting a completed Session may retain unsupported model
  statements and sensitive tool material;
- allowing the Agent alone to decide recall can miss required history or widen
  scope;
- CTI needs Workspace qualification before either preload or tool use.

Source: [Google ADK MemoryService](https://google.github.io/adk-docs/sessions/memory/).

## 4. Comparative answers to the product questions

| Product question | Mature-system answer | CTI-RAG research direction |
|---|---|---|
| What should be retained? | Separate facts, preferences, episodes, summaries, rules, and raw history | Route by business meaning to Case, I&E, Workspace, or Session; leave residual experience/preferences unowned until accepted |
| How is worth judged? | Model extraction, explicit user instruction, strategy prompts, feedback, or application rules | Model may propose; owner policy or authorized human admits |
| When is extraction run? | Per turn, after response, at session end, incrementally, or asynchronously | Prefer settled owner-controlled points; timing does not change authority |
| Does every query retrieve? | Mem0 examples often do; Claude/ADK also support explicit search or tools | Use deterministic task/history-need routing plus optional Agent query proposal; allow no recall |
| How is recall scoped? | User/project/actor/session/namespace plus metadata | Qualify tenant, actor, purpose, Case/Workspace, authorization, versions, markings, validity before relevance |
| How is it ranked? | Semantic, keyword, entity, graph, temporal, recency, reranking | Ranking selects among already eligible candidates; score never means truth |
| What enters context? | Small memory blocks, summaries, top-K records, or lazy topic files | Workspace chooses a bounded, labelled, provenance-bearing view; do not inject raw stores or entire transcripts |
| How are changes handled? | Update/delete, additive history, temporal invalidation, feedback | The owning business context controls correction/withdrawal; downstream recall follows dependency invalidation |
| How is control exposed? | Inspect/edit/delete, pause/reset, incognito, visible citations | Require inspectability, correction, deletion, no-memory mode, and traceable origin for any residual memory |
| Are rules memory? | Claude separates advisory instructions from enforced settings/hooks | Keep product policy and authorization outside model memory |

## 5. Research recommendation for a clearer CTI-RAG direction

Do not organize the design as one short-term/long-term hierarchy. Describe each
retained item along four independent axes:

1. **business meaning and owner** — Case authority, I&E material, Workspace
   analysis, Session history, or a still-undecided residual;
2. **scope and audience** — Run, Session, Workspace, Case, actor, team, tenant,
   or broader reuse;
3. **lifecycle and validity** — ephemeral, current, superseded, challenged,
   withdrawn, expired, retained only for history, or deleted; and
4. **context behavior** — always present, deterministically preloaded,
   retrieved on demand, or never model-visible.

This yields a clear memory workflow without inventing one owner:

1. an event or settled Run produces a possible retention candidate;
2. its business meaning determines the existing owner or exposes a real routing
   gap;
3. the owner admits, versions, corrects, withdraws, retains, and deletes it;
4. a new task produces a recall-need decision;
5. owner-local retrieval returns only currently authorized and valid candidates;
6. relevance ranking operates after eligibility;
7. Workspace selects a bounded, labelled view for the current Agent context;
8. recalled advisory material never changes Case or I&E authority by itself.

The strongest combined lesson from Claude and the other systems is:

> Keep a small, explicit, inspectable set of frequently applicable guidance;
> keep detailed history and experience outside the active context; retrieve it
> only when the current task justifies it; and keep hard authority and policy
> outside model-maintained memory.

## 6. Undecided product choices

The industrial survey does not decide:

- whether CTI-RAG needs user preferences beyond a current Workspace Lens;
- whether procedural or episodic experience must cross Cases;
- whether team-shared memory is required before shared-analysis scope is
  reopened;
- whether recall is deterministic preload, Agent-proposed tool use, or a hybrid;
- whether derived experience is immediately available or background-qualified;
- who may admit or correct residual cross-owner experience; or
- what improvement and error thresholds justify the additional governance.

These choices need a concrete CTI workflow and acceptance criteria before any
new owner, Module, store, or Interface is designed.
