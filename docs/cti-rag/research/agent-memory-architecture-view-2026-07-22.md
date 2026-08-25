# CTI-RAG Agent Memory Architecture View

Status: non-normative candidate design and research synthesis.

Research date: 2026-07-22.

Design adoption: the owner-local persistence decision is adopted by
[ADR 0018](../adr/0018-keep-memory-as-an-owner-local-architecture-view.md).
The behavior needed to turn this view into a Memory capability is now explored
by the
[`workspace-memory-coordination/v1`](../agent-workspace/workspace-memory-coordination-v1-contract.md)
design candidate. Neither that candidate nor the Initial Investigation Context
candidate is normative while its Design Gate is FAIL.

This document does not define a Memory Module, database, schema, vector index,
automatic write path, Skill, MCP capability, multi-Agent topology, or public
Interface. It does not amend any current contract, ADR, `CONTEXT.md`, or
`PROGRESS.md`.

## 1. Design disposition

CTI-RAG should describe memory at two different levels without merging them:

1. **Agent-cognitive view:** temporary, short-term, task, and long-term material
   used to continue work and construct a bounded model context.
2. **Business-ownership view:** Case Management, Agent Investigation Workspace,
   Pi Session, and Intelligence and Evidence retain their current, distinct
   authority and lifecycle responsibilities.

The recommended direction is therefore a **Memory Architecture View over
existing owners**, not a unified Memory owner.

The current design has not proven a persistent business need that none of the
existing owners can carry. The only plausible residual is governed procedural
or episodic experience and user/team preferences that must cross Cases or
Workspaces. That behavior is not currently accepted product scope. An
independent Memory capability remains conditional on a concrete workflow that
proves this owner gap.

Mem0 is the primary technical reference for candidate extraction, controlled
retention, search, update/delete, feedback, and evaluation. Claude is the
product-governance reference for separating explicit rules from learned notes,
keeping only a small stable set continuously visible, loading details on demand,
and making retained notes inspectable and controllable. Neither system supplies
CTI authority, authorization, provenance, Case Revision, or Resource Version
semantics.

The broader industrial survey remains an evidence catalog. This design does not
assemble one mechanism from every surveyed product.

## 2. Evidence classification

To prevent this research note from being read as a contract, each statement
belongs to one of four classes.

### 2.1 Current documented design

- Case Management owns long-lived authoritative investigation state and its
  controlled revisions. Case State excludes Agent memory and transcript.
- Pi Session owns navigable interaction history, save points, compaction,
  branches, and recovery. It is not Case authority.
- Agent Investigation Workspace owns task-scoped state, Working Set selection,
  context qualification and rendering, and persistent non-authoritative
  Workspace Artifacts.
- I&E owns reusable source/resource identity, versions, provenance, derivatives,
  retrieval evidence, use status, and retention-qualified material.
- Model Context is a synchronized rendering, not a durable memory store.
- Model outputs, Session entries, Workspace material, and I&E Resources do not
  become Case authority through rendering, retrieval, or compaction.
- Workspace admits model proposals deterministically and is the existing owner
  of final model-context selection.

### 2.2 CTI business deductions

- Same-Case continuity is mainly an owner-local discovery and projection
  problem, not proof of a new Memory owner.
- Recall must establish eligibility before relevance because semantically
  similar material can be unauthorized, stale, withdrawn, or based on another
  Case/Resource version.
- Retained model analysis must remain labelled as non-authoritative and tied to
  its basis; otherwise memory converts a transient hallucination into durable
  pseudo-fact.
- Deletion and withdrawal must reach every recall path, including rebuildable
  projections, or removed material can re-enter context.

### 2.3 Research recommendations

- Use the lifecycle and recall policies in sections 5 through 11 as the
  candidate direction for later owner-local contracts.
- Treat Mem0 mechanisms as replaceable implementation references rather than
  domain authority.
- Evaluate memory-assisted behavior against a no-optional-recall baseline before
  accepting additional persistence or orchestration.

### 2.4 Undecided product choices

- Whether procedural or episodic experience must cross Cases or Workspaces.
- Whether user or team preferences exist beyond current Workspace Lens and
  explicit application configuration.
- Whether any residual material is private to an actor, shared with a team, or
  reusable across a tenant.
- Which qualified roles may admit, correct, withdraw, or delete such residual
  material.
- Numeric retention horizons, recall budgets, quality thresholds, and user
  controls.

## 3. Memory layers without owner renaming

The terms in this table are a cognitive view only. They neither rename an owner
nor define new stored object types.

| Cognitive layer | Current material | Current owner | Context behavior |
| --- | --- | --- | --- |
| Temporary working material | uncommitted Turn state, in-flight tool results, private model candidate, transient planning | Pi runtime and Workspace lifecycle at their existing seams | usable only within the current qualified Run; discarded or settled by the owning lifecycle |
| Short-term continuity | committed interaction history, branch, compaction, save points, current task control state | Pi Session, with CTI meaning supplied by Workspace | eligible history is projected when the current task needs it |
| Current task memory | Original User Task, admitted task context, Working Set, task decisions, persistent non-authoritative outputs | Workspace; small v1 committed state may use Pi Session as its authority | required task state is loaded; larger Artifacts are discovered and selected on demand |
| Long-term investigation memory | accepted Case State, Case history, corrections, conclusions, milestones | Case Management | current authorized Case view is required; older revisions are historical, not competing current truth |
| Long-term intelligence memory | reusable resources, versions, source captures, provenance, derivatives and retrieval evidence | I&E | exact or bounded retrieval followed by Workspace admission and disclosure revalidation |
| Residual experience/preferences | cross-Case procedure, episodic lesson, stable user/team convention | no accepted owner | excluded until a product workflow and owner are accepted |

“Temporary”, “short-term”, and “long-term” describe expected use and lifetime;
they do not decide business meaning, authority, access, or storage location.

### 3.1 Candidate scenarios that test the boundaries

**Same Case, later task.** An analyst asks what prior investigation work already
tested a hypothesis. Workspace may discover eligible Session history and
Workspace Artifacts bound to that Case, actor, and purpose; Case Management
supplies accepted current conclusions; I&E supplies reusable source material.
The prior analysis remains non-authoritative. This scenario needs owner-local
discovery, not a new owner.

**Different Case, similar technique.** An analyst asks for investigation paths
that worked on unrelated Cases. Case facts cannot cross the boundary as an
Agent lesson, and I&E Resources cannot be relabelled as experience. Until the
product accepts governed procedural/episodic reuse, optional recall returns no
cross-Case lesson. This is the scenario that could eventually prove a residual
owner gap.

**Explicit preference.** A user asks the Agent to remember a reporting style for
future investigations. The request creates a candidate, not a durable fact. If
the preference is merely current-task presentation, Workspace can own it; if it
must span Workspaces or Cases, the owner and sharing policy remain undecided.

## 4. Content classification and routing

Every retention candidate must first be classified by business meaning. The
classification routes it to an existing owner or demonstrates an actual gap.

| Candidate meaning | Normal destination | Admission consequence |
| --- | --- | --- |
| accepted investigation fact, decision, conclusion, correction, or formal event | Case Management | only the Case owner may make it authoritative |
| reusable source material or a reproducible analysis result with stable identity and provenance | I&E | remains governed by Resource Version, source/use status, markings, lineage, and retention |
| task-scoped hypothesis, draft, comparison, analysis trail, or derived analytic output | Workspace Artifact or task state | remains non-authoritative and scoped to its task/Workspace unless another owner later admits it |
| interaction, tool, save-point, branch, compaction, or Run history | Pi Session | supports continuity and audit; does not become investigation truth |
| user/team working convention or cross-Case procedural/episodic lesson | unresolved | reject durable cross-scope admission until the product accepts the need and assigns an owner |

The producer does not determine the owner. An Agent-assisted analysis result may
qualify as an I&E Resource only if it meets I&E identity, provenance,
reproducibility, version, and admission rules. Calling Agent experience a
“resource” is not sufficient. Conversely, an item is not disqualified merely
because an Agent participated in producing it.

## 5. Deciding what is worth retaining

Persistence by an existing owner and promotion to broader reuse are separate
decisions. A Session may retain an event for continuity while the same event is
rejected as a reusable lesson.

### 5.1 Candidate sources

A retention candidate may arise from:

- an explicit user instruction, correction, withdrawal, or deletion request;
- a deterministic lifecycle event such as a settled Run, accepted Case change,
  published Workspace Artifact, or qualified Resource Version;
- a model proposal identifying a potentially reusable fact, preference,
  experience, or procedure; or
- a reviewed bad case that suggests a rule or process improvement.

A candidate is not yet retained knowledge. In particular, model proposals and
bad-case explanations have no authority of their own.

### 5.2 Qualification questions

The receiving owner should admit a candidate only when all applicable questions
have satisfactory answers:

1. **Meaning:** What kind of business content is this, and which existing owner
   governs that meaning?
2. **Source:** Can the exact message, event, Artifact, Case Revision, Resource
   Version, or other basis be identified and revalidated?
3. **Scope:** Is it applicable only to this Run, Session, Workspace, Case, actor,
   purpose, team, or tenant?
4. **Authority:** Is it asserted, observed, inferred, accepted, challenged, or
   withdrawn? Who is qualified to change that status?
5. **Utility:** Is there a credible future consumer for which retaining it is
   more useful than rediscovering it from the authoritative source?
6. **Stability:** Is it likely to remain applicable long enough to justify the
   staleness, privacy, and deletion burden?
7. **Safety:** Do markings, authorization, privacy, licensing, or sensitive
   reasoning content prohibit broader retention or model visibility?
8. **Lifecycle:** Can correction, withdrawal, expiry, deletion, and dependency
   invalidation be applied completely?
9. **Conflict:** Does an equivalent, newer, contrary, or more authoritative item
   already exist?

If the item already belongs to and is discoverable from an existing owner, no
duplicate “memory copy” should be created. A rebuildable index or pointer may
accelerate discovery, but it is not another authority.

### 5.3 Practical admission defaults

- Explicit user statements may create immediate candidates, but they do not
  bypass scope, authorization, or owner admission.
- Case facts and corrections follow Case workflows rather than automatic memory
  extraction.
- I&E material follows I&E admission rather than conversation extraction.
- Task hypotheses and model summaries remain in Workspace/Session scope unless
  explicitly accepted elsewhere.
- Bad cases create evaluation evidence or proposed rule changes. They do not
  automatically alter the system prompt or become procedural memory.
- Unsupported or source-less model assertions are rejected from durable reuse.

## 6. When retention work occurs

Retention decisions should occur at stable owner-controlled points:

- after a Run has settled and its final save point is known;
- after a Workspace Artifact has been deliberately persisted or published;
- after a Case proposal has been accepted, corrected, or rejected by Case
  Management; or
- after I&E has published or changed the status of a qualified Resource Version.

Candidate extraction may be synchronous when the user explicitly asks to
remember, correct, or delete something. Ordinary consolidation may occur after
settlement. This is a latency choice, not an authority choice: both paths require
the same owner qualification.

The system should not form reusable memory from streaming deltas, incomplete
tool calls, uncommitted save-point state, private response candidates, or work
that was later cancelled, failed, discarded, superseded, or withheld.

## 7. Recall decision and owner routing

Every user query receives a cheap recall-need decision. This does not mean every
query performs historical retrieval.

### 7.1 Mandatory base context

Workspace first reconstructs the context required by current contracts:

- current system instructions and enforced policy references;
- immutable Original User Task and admitted Additional Task Context;
- current Working Set;
- current authorized Case context;
- eligible Session history; and
- activated tools/capabilities through their existing admission rules.

This base is not “memory search”. It is current task reconstruction from known
owners.

### 7.2 Optional-history triggers

Additional recall is justified when at least one of these conditions holds:

- the user explicitly refers to prior work, a previous decision, correction,
  preference, failure, handoff, or unfinished investigation;
- the task type inherently depends on history, comparison, change over time,
  provenance, prior attempts, or previous conclusions;
- the current context has an identifiable gap that an eligible owner may fill;
  or
- during the Run, the model proposes a bounded historical dependency that
  Workspace can independently qualify.

Simple self-contained questions, formatting requests, and tasks fully answered
by the mandatory base may select **no optional recall**.

### 7.3 Route before search

The recall planner determines the likely owner before relevance search:

| Need expressed by the current task | Owner-local source |
| --- | --- |
| prior dialogue, tool outcome, branch, compaction ancestry | Pi Session |
| task decision, prior task analysis, Working Set selection, Workspace Artifact | Workspace |
| accepted investigation state, correction, conclusion, Case history | Case Management |
| reusable source, Resource Version, provenance, derivative, retrieval evidence | I&E |
| cross-Case lesson or user/team preference | closed: no owner currently accepted |

This routing prevents a global semantic search from making unrelated content
appear equivalent merely because its wording is similar.

## 8. Eligibility, ranking, and context adoption

Recall is a three-stage funnel.

### 8.1 Hard eligibility

Each owner returns or permits only material that passes current checks for:

- tenant and authenticated actor;
- current purpose and task/Workspace/Case binding;
- Session branch, compaction ancestry, and context generation where applicable;
- authorization, membership, markings, license, and disclosure policy;
- exact Case Revision, Artifact basis, Resource Version, Source Capture, or
  other dependency version;
- current publication/use status;
- correction, challenge, supersession, withdrawal, expiry, retention, and
  deletion state; and
- applicability to the current consumer and model disclosure path.

Failure to establish eligibility excludes the item. Semantic similarity never
repairs missing authorization or provenance.

### 8.2 Relevance within the eligible set

Mem0-style multi-signal retrieval is useful only after eligibility. Depending
on the owner and task, ranking may consider:

- exact identifiers and structured filters;
- lexical and semantic match;
- named entities and relationships;
- temporal relation and recency;
- task and purpose fit;
- provenance completeness and basis quality;
- prior use or feedback; and
- coverage, duplication, contradiction, and diversity.

Scores mean retrieval relevance within one request. They do not mean factual
confidence, authority, evidentiary weight, or comparability across requests.

### 8.3 Workspace adoption

Workspace owns the final bounded selection for the current Agent context. It
should:

1. prefer current authoritative material over advisory history;
2. preserve explicit labels for owner, authority, time, scope, and status;
3. collapse duplicates without erasing distinct provenance;
4. expose conflicts rather than silently choosing the most similar item;
5. satisfy token and disclosure budgets;
6. retain the source reference needed for revalidation; and
7. allow an empty optional-recall result.

Only the selected view enters context. Raw stores, entire transcripts, search
traces, unqualified candidates, and hidden alternatives do not.

Older versions may be included when the task asks for history, but must be
labelled historical and must not compete with the current version as current
authority.

## 9. Correction, withdrawal, deletion, and expiry

There is no unified Memory mutation authority. The owner of the retained
business meaning controls its lifecycle.

- Case Management controls correction and revision of Case authority.
- I&E controls Resource Version publication/use status, withdrawal, derivative
  dependencies, and retention qualification.
- Workspace controls its task state and non-authoritative Artifacts.
- Pi Session controls its persisted interaction structure; Workspace supplies
  CTI eligibility meaning at projection time.

A correction normally creates or selects a new current owner state while
preserving eligible history. It must not rewrite old material so that a past
analysis falsely appears to have used the new facts.

Withdrawal, expiry, authorization loss, marking change, or dependency drift
must immediately remove the affected material from current recall eligibility,
even if audit or legal-retention policy delays physical deletion.

Deletion is complete only when the item can no longer be returned through any
active recall path. Owner records, derived summaries, search projections,
embeddings if any are later authorized, caches, attached context views, and
pending candidates must either be removed or made provably ineligible. An
index is rebuildable from the surviving owner state and cannot preserve a
deleted item as shadow authority.

If a source conversation or Artifact can be deleted independently of a derived
candidate, the product must explicitly decide whether deletion cascades,
withdraws the derivative, or retains a separately justified record. Silent
survival is not an acceptable default for CTI-sensitive material.

## 10. Binding and invalidation model

The design needs dependency binding, not a single global “memory scope”. The
applicable owner must be able to associate retained or recalled material with:

- the originating Task, Workspace, Session, branch, Run, actor, and purpose;
- the relevant Case and Case Revision or observed Case context;
- the relevant Workspace Artifact version;
- the relevant I&E Resource Version, Source Capture, status, and use decision;
- the policy, method, extraction, or ranking version that shaped a derivative;
- observed time, applicable/valid time, review time, and expiry where relevant;
  and
- the actor or process that proposed, admitted, corrected, withdrew, or deleted
  the material.

This is a semantic requirement, not a proposed schema.

When a dependency changes, the dependent material must be requalified. Possible
results include current, historical-only, challenged, superseded, withdrawn,
expired, deleted, or not eligible for the present actor/purpose. Re-ranking a
stale item is not requalification.

## 11. Failure behavior

Recall must fail safely and must not invent continuity.

| Failure | Required behavior |
| --- | --- |
| current mandatory Case/authorization/context basis unavailable | fail or request clarification according to the owning Workspace contract; do not substitute history |
| optional historical retrieval unavailable or times out | continue only when the task is still valid without it, and make the omission observable |
| authorization, marking, purpose, status, or version cannot be proved | exclude the material without leaking its existence or metadata |
| current and historical items conflict | present a bounded labelled conflict when relevant; never silently merge them |
| no eligible result | return no optional memory and allow abstention |
| model asks for a wider scope than admitted | deny or narrow deterministically; the request does not create authority |
| owner changes after retrieval but before model disclosure | invalidate the selection and requalify or deny before disclosure |
| recalled content appears to be a rule or permission | treat it as advisory text; enforced policy and capability admission remain outside memory |

The model may propose another bounded retrieval during the Run. Workspace still
owns scope compilation, qualification, budgeting, and adoption. A failure must
not be hidden by asking the model to fabricate a summary of unavailable history.

## 12. Model, deterministic policy, and human responsibilities

### Model may

- propose retention candidates and their apparent meaning;
- propose a bounded need for additional historical material;
- summarize already qualified material with source references;
- identify apparent duplication, conflict, or possible staleness; and
- use recalled advisory material in analysis while preserving its labels.

### Model may not

- make a candidate durable merely by mentioning it;
- turn its own output into Case authority or an I&E Resource;
- decide actor/purpose authorization, markings, retention, or deletion
  completeness;
- silently convert a hypothesis into a fact or a bad case into an enforced
  system rule; or
- widen recall from the current Case/Workspace to cross-Case/team scope.

### Deterministic owner policy and qualified humans

They admit business meaning, prove scope and authorization, bind versions,
apply lifecycle changes, resolve identity, and decide which corrections or
conclusions become authoritative. Human visibility, edit, and deletion controls
are desirable for retained advisory material, but they do not bypass Case or
I&E governance.

## 13. Context boundary

This design stops at the handoff to context construction. It recommends that
qualified recalled material be delivered as a bounded, labelled view containing
enough origin, scope, authority, time, and status information for the model to
interpret it safely.

The exact prompt sections, ordering, serialization, token allocation, and tool
presentation belong to the separate context-design work. Memory retrieval must
not redefine the current seven-section Investigation context or place
authorization and enforcement rules inside model-maintained notes.

The same principle applies to future multi-Agent work: a coordinator or worker
may receive a qualified view for its Run, but another Agent's output does not
automatically become shared or long-term memory. Agent topology does not create
an owner.

MCP is likewise an integration protocol, not a memory owner. An MCP server may
eventually expose an existing owner through an Adapter, but the need for MCP is
independent of the memory requirement and is not established by this design.

## 14. Evaluation before expansion

Memory quality cannot be accepted from retrieval recall alone. Evaluation
should compare the same CTI tasks with and without optional history and cover:

- correctness of the recall-needed decision;
- owner-routing accuracy;
- eligible-result precision and useful coverage;
- zero unauthorized or marking-incompatible disclosure;
- stale, withdrawn, deleted, or wrong-version inclusion;
- contradiction handling and abstention;
- correction and deletion propagation to every active recall path;
- source/provenance preservation;
- downstream task correctness, not merely whether a remembered phrase was
  found;
- anchoring, hallucination, and erroneous personalization caused by recall;
- token, latency, and operational cost; and
- user ability to understand why material was retained or recalled.

The benchmark must include no-result, adversarial-similarity, authorization
drift, Case Revision drift, Resource Version withdrawal, `A -> B -> A` scope
return, deletion, and conflicting-history scenarios. Numeric gates remain an
undecided product choice.

## 15. Deep-module and owner decision

The useful deep seam is the existing Workspace boundary:

- upstream callers provide a task, not memory-store instructions;
- Workspace reconstructs mandatory context and decides whether optional history
  is needed;
- owner-local retrieval hides each owner's persistence, revision, retention,
  and authorization mechanisms;
- Workspace admits a bounded view into context; and
- the model receives qualified material without gaining mutation authority.

This keeps the common flow small while hiding substantial policy complexity.
The adapter boundary belongs at each existing owner, not around a shared memory
database.

An independent owner should be reconsidered only when all of the following are
true:

1. a concrete accepted workflow requires procedural, episodic, preference, or
   other durable knowledge across Cases or Workspaces;
2. the content cannot correctly be represented by Case, I&E, Workspace
   Artifact/task state, Pi Session, or application configuration;
3. its consumer, authority status, sharing scope, retention, correction,
   withdrawal, deletion, and evaluation rules are known; and
4. deleting the proposed owner would force those responsibilities to leak into
   multiple existing callers or owners.

That deletion test does not currently pass. The default design is therefore:

> Existing owners persist their own meanings; Workspace provides recall-needed
> routing, cross-owner qualification, bounded selection, and context adoption.

## 16. What remains open after this research

The research classifies the Memory problem but does not close a product
Interface. The Workspace Memory Coordination candidate must close the
owner-specific seams and the following product choices:

1. accept or reject cross-Case/cross-Workspace procedural and episodic recall;
2. accept or reject user/team preferences beyond explicit configuration and
   current Workspace Lens;
3. select the first same-Case historical Artifact discovery scenario and define
   its owner-local acceptance behavior;
4. set retention, review, recall-budget, and evaluation thresholds; and
5. decide the user control surface for inspecting, correcting, forgetting, or
   temporarily disabling optional advisory memory.

None of these choices is required to add a Memory Module now. The next design
topic may proceed to context assembly using this document's handoff boundary.

## 17. Local evidence

- [CTI-RAG documentation authority and navigation](../README.md)
- [Bounded-context map](../CONTEXT-MAP.md)
- [Agent Workspace language](../agent-workspace/CONTEXT.md)
- [Case Management language](../case-management/CONTEXT.md)
- [I&E language](../intelligence-evidence/CONTEXT.md)
- [Workspace architecture and state composition](../agent-workspace/context-projection-design.md)
- [Pi-native Workspace lifecycle](../agent-workspace/pi-native-workspace-lifecycle-v1-contract.md)
- [Intelligence Working Set](../agent-workspace/intelligence-working-set-v1-contract.md)
- [I&E platform design](../intelligence-evidence/intelligence-evidence-platform-design.md)
- [Memory requirement audit](./agent-memory-requirements-audit-2026-07-21.md)
- [Mem0 primary-source audit](./mem0-primary-source-audit-2026-07-22.md)
- [Industrial memory pattern survey](./agent-memory-industrial-patterns-2026-07-22.md)
