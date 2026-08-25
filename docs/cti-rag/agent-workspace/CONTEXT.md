# Agent Investigation Workspace

Agent Investigation Workspace performs a current Original User Task against a Case. It holds task-scoped working state and uses Pi for execution without redefining Case Management or Intelligence and Evidence.

## Language

**Task Intake**:
The bounded pre-Case interpretation step that preserves the user's exact task and proposes a normalized objective, ambiguity and route-relevant properties. It does not answer the task, create a Case, select Tools or authorize investigation.
_Avoid_: Task Understanding inside an open Workspace, task answer, investigation plan

**Task Route**:
The closed structured classification produced by the Task Intake model that selects clarification, Quick Response, Formal Investigation or unsupported from the task's required behavior. A deterministic admission gate validates and safely executes it but does not replace semantic classification with an exhaustive rule engine.
_Avoid_: Pure rule-engine intent detection, scalar complexity score, Agent plan

**Quick Response**:
A bounded, read-only one-shot response for a task that requires no new evidence, Tool use, Case mutation, formal report or multi-goal investigation. It remains subject to qualified context and publication rules.
_Avoid_: Small investigation, hidden Case, truncated Agent Run

**Formal Investigation**:
The Case-bound product workflow that opens or creates the required Case, Session and Workspace, then executes an Investigation Work Plan through the evidence-gathering Agent loop to a settled disposition and mandatory route-appropriate Task Outcome Report.
_Avoid_: Any model call, Quick Response, Harness lifetime

**Investigation Work Plan**:
The user- and Agent-visible projection of admitted goals, subquestions, pending actions, budgets and terminal state already owned by Investigation Run Control. It is not a second planner, scheduler or durable workflow authority.
_Avoid_: Separate TODO engine, model scratchpad, task DAG

**Task Result**:
The private, immutable, machine-readable Workspace result finalized from one exact settled Investigation Run. It records per-goal achieved and incomplete work, classified statements, conflicts, gaps, Save Point/resume state and proposed next steps without becoming a report, Case conclusion or Evidence Reference.
_Avoid_: ModelResponseCandidate, Report Evidence Packet, Task Outcome Report, Case finding

**Claim-Evidence Subgraph**:
A private, bounded, task-scoped Workspace projection connecting Task Result statements and exact source assertions to qualified I&E material, source/provenance/lineage relationships and explicitly candidate support/contradiction roles. It is not a global graph, semantic proof, Case Evidence Reference or accepted conclusion.
_Avoid_: Evidence database, vector result, Case graph, proof of truth

**Evidence Assembly**:
The Workspace task-scoped seam that revalidates already admitted Working Set references through I&E and assembles one Claim-Evidence Subgraph without performing new search, calling a model or creating a long-lived Module.
_Avoid_: Evidence Assembly Module, retrieval Agent, graph database, Case evidence acceptance

**Report Evidence Packet**:
The private, bounded, single-profile and single-attempt Workspace projection of one committed Task Result and Claim-Evidence Subgraph for a no-tool report Composer. Its bodies are ephemeral, its binding receipt is non-content, and it cannot be rebound after owner drift.
_Avoid_: Prompt transcript, evidence graph, report, Memory object, reusable retrieval result

**Investigation Report Candidate**:
A private structured report composed after a formal Investigation Run settles from the exact admitted evidence packet. It remains non-authoritative and unpublished until deterministic validation and any required Independent Evidence Audit succeed.
_Avoid_: Final answer, verified intelligence, Workspace Artifact

**Task Outcome Report**:
The mandatory route-appropriate feedback that closes or pauses one product task: a clarification, concise answer, investigation result, interruption/recovery status, or unsupported-scope result. It may be short and is not necessarily a formal document.
_Avoid_: Optional final document, raw model completion, Workspace Artifact

**Task Outcome Stream**:
The caller-visible sequence of safe committed progress followed by exactly one admitted Task Outcome Report and terminal status. Provider deltas and uncommitted candidate text are never part of this stream.
The report is atomically published in full before its deterministic chunks are delivered; a disconnect may interrupt delivery, but cannot create a partial publication.
_Avoid_: Raw Provider stream, speculative chain of thought, uncommitted Tool progress

**Interruption Report**:
A Task Outcome Report derived from the last valid Save Point after failure, cancellation or supersession. It states completed and incomplete work, the blocker, resumable basis and safe next action without pretending the task completed.
_Avoid_: Successful report, reconstructed missing work, Provider retry

**Independent Evidence Audit**:
A fresh-context, single-purpose semantic audit of whether every factual or analytical report claim follows from its cited admitted evidence without contradiction, fabrication or overstatement. It cannot route the task, investigate, use Tools or Memory, rewrite the report, create facts, repair citations, override deterministic validation or authorize Case writes.
_Avoid_: Truth oracle, second investigation, report writer, general evaluator

**Access Principal**:
The trusted user, group, or service identity exercising access to CTI-RAG data or capability under one authorization binding.
_Avoid_: Actor, Threat Actor, Agent identity, thread actor, userIdentification

**Use Purpose**:
The trusted reason an Access Principal is authorized to use an exact data version; it isolates data flows and is revalidated before owner access, model disclosure, historical recall, and audited reuse.
_Avoid_: Purpose, task objective, Case mandate, context consumer, operation intent

**Task Objective**:
The bounded outcome the current Workspace task or admitted goal must accomplish; it does not grant data use or operation authority.
_Avoid_: Use Purpose, Case mandate, Operation Intent

**Context Consumer**:
The qualified Pi path for which Session entries or a context view are selected, such as Provider input, compaction, or branch summary.
_Avoid_: Use Purpose, model identity, task objective

**Original User Task**:
The exact text and user-supplied images submitted for current work against a Case; it is immutable source input and remains distinct from every normalized or admitted derivation.
_Avoid_: Normalized task, Admitted Task Context, Case, Agent Run

**Task Understanding Proposal**:
A model-produced, non-authoritative pre-investigation proposal containing minimal normalization, task intent, requested outcome, and ambiguity anchored to the Original User Task. It contains no Query Candidate, capability need, Tool choice, Working Set action, or investigation plan.
_Avoid_: Task Plan, rewritten task, executable plan

**Admitted Task Context**:
A versioned, non-authoritative Workspace derivation that preserves the Original User Task while recording deterministically admitted interpretation, uncertainty, assumptions, and exclusions. It is Additional Task Context for investigation reasoning, not a replacement task or authority.
_Avoid_: User Task, model plan, Operation Intent, authorization

**Initial Investigation Context**:
The first Pi model context admitted for an Investigation Agent Run from trusted instructions, the current user request, a Qualified Memory View, and separately activated Tools; it is an ephemeral rendering rather than another memory authority.
_Avoid_: seven-section database, prompt blob, transcript dump, Task Understanding output

**Mandatory Context Reconstruction**:
Rebuilding the current task's required model context from committed task state and qualified owner-local Case, Working Set, Session, and capability views; it is not semantic memory search.
_Avoid_: Memory retrieval, transcript dump, global recall

**Optional Historical Recall**:
A bounded Workspace decision to seek additional historical material only after routing the need to an existing owner and proving eligibility before relevance.
_Avoid_: Automatic memory injection, global semantic search, cross-Case lesson

**Qualified Recall View**:
A bounded, labelled, revalidatable projection of owner-local historical material admitted by Workspace for one current consumer; it carries no new authority and may be empty.
_Avoid_: Memory record, copied authority, search result dump

**Memory Management Module**:
The first-class Agent capability that manages durable semantic, episodic and procedural memory across admission, persistence, exact-reference qualification, consolidation, correction, invalidation and deletion. It returns qualified memory contributions for Context Assembly; it does not own the final assembled prompt or treat a runtime context projection as a durable Memory Entry. It uses explicit owner Adapters for Session, Case, Workspace and I&E data and does not treat those owners' existing state as a substitute for Memory Management. General discovery and ranking are separate future capabilities.
_Avoid_: transcript-only memory, unrestricted global recall, model-authored authority, context assembler

**Memory Candidate**:
One proposed durable assertion or reference that has a source proof but has not passed admission or become recallable Memory.
_Avoid_: Memory Entry, model completion, source record

**Memory Entry**:
The stable identity of one durable logical Memory item across immutable revisions; it carries no authority beyond its admitted source and current qualification.
_Avoid_: Session message, owner record, current revision, Context Assembly contribution

**Memory Revision**:
One immutable realized version of a Memory Entry, including its state, value/reference, relations and temporal/provenance basis.
_Avoid_: Memory Entry identity, mutable row, use permission

**Memory Operation**:
One idempotent requested admission, correction, invalidation, deletion or other lifecycle effect with one terminal outcome.
_Avoid_: Memory Entry, source proof, retry attempt

**Memory Source**:
The exact settled Run, explicit authorized command or owner-versioned reference that supports one Memory Candidate; it remains distinct from the Candidate and Entry it may support.
_Avoid_: Model text, raw Tool result, Memory revision

**Memory Use**:
One consumer-, principal-, use-purpose- and policy-bound qualification of exact Memory revisions for Context Assembly. It expires or invalidates independently of those revisions.
_Avoid_: Memory Entry, prompt, Provider invocation, persistent permission

**Exact Memory Selection Proof**:
Owner-issued evidence that one caller may request one ordered exact list of Memory Entry revisions for a bound scope, Access Principal, Use Purpose and Context Consumer. It does not locate alternatives or grant broader visibility.
_Avoid_: search query, scope inference, authorization substitute, Memory Use

**Safe Memory Contribution**:
The bounded untrusted-data projection of one qualified Memory revision for Context Assembly, carrying its labels, references and rendering constraints but no instruction, Tool, capability, policy or authorization field.
_Avoid_: prompt role, Provider option, Memory Entry, trusted instruction

**SQLite Memory Store**:
The selected first local-host Adapter that authoritatively stores admitted Memory revisions, operations, receipts and tombstones. It is not qualified until it passes the Memory storage-profile acceptance catalogue.
_Avoid_: current `sql.js` probe, Session store, Git repository

**Git-backed Markdown Memory Source**:
The selected user-editable committed Markdown input surface. An exact allowed commit/blob may become a Memory candidate through source verification and admission; Memory never writes, merges or commits the repository.
_Avoid_: second Memory store, moving branch, uncommitted worktree, generated export


**Workspace Memory Coordination**:
The CTI Workspace integration capability that binds Memory Management to the current task, Case, Access Principal, Use Purpose, Working Set and Session, including owner qualification, pre-disclosure revalidation and task-scoped routing.
_Avoid_: top-level Memory owner, context renderer, owner repository

**Qualified Memory View**:
An ephemeral, consumer-bound composition of current owner-qualified task memory and any admitted optional historical recall, carrying source, authority, status and revalidation evidence but no system instructions or Tool activation.
_Avoid_: prompt, Provider messages, memory store, copied Case

**Memory Adoption Receipt**:
Non-content evidence of the owner routes, qualification outcomes, selected references, ordering, omissions, conflicts and binding admitted for one Agent Run; it does not itself become recallable memory.
_Avoid_: Model Input Receipt, search result, memory item, authority

**Query Candidate**:
A provenance-bound, target-neutral formulation proposed during the formal Investigation Agent Run; it contains no Resource Candidate Reference or exact selector, never replaces the Original User Task, and cannot authorize retrieval.
_Avoid_: Rewritten task, resource target, retrieval request, backend query, entity identity

**Resource Candidate Reference**:
An opaque, Workspace-owned task-scoped reference minted after Admitted Task Context commit from one current principal-visible Case Orientation membership; the model may select it, but only trusted Workspace policy can bind it to an exact I&E selector. It is distinct from an I&E-owned search-result candidate even when both refer to the same Resource.
_Avoid_: Query Candidate, I&E Retrieval Candidate Reference, OpenCTI object ID, authorization, Resource Reference

**Retrieval Candidate Admission**:
A deterministic Workspace decision that accepts or rejects a model suggestion of an opaque I&E Retrieval Candidate Reference under the current task, Access Principal, Use Purpose, capability, policy, budget, and Context Generations. Only an accepted decision may request exact materialization; it does not itself create a Capsule or mutate the Working Set.
_Avoid_: Model choice, search result, exact retrieval, Working Set commit

**Task Clarification**:
A deterministic request for user input when a material Task Understanding ambiguity has no safe conservative interpretation; it ends the current Workspace Turn before any Investigation Agent Run starts.
_Avoid_: Model question, planning failure, background wait

**Agent Run**:
One formal execution of the Pi investigation model-tool loop after Task Understanding admission; it may contain several model turns and tool batches.
_Avoid_: Case, Session, Workspace Turn

**Investigation Run Control**:
The deterministic Workspace policy that binds one Agent Run to admitted goals, target-neutral Query Candidates, current capabilities, hard budgets, local adjustments, and one terminal disposition. It guides the existing Pi loop and is not a planner Agent, scheduler, task DAG, or transcript.
_Avoid_: Agent loop, recursive planner, sub-Agent coordinator, universal workflow engine

**Investigation Run Disposition**:
The closed Workspace-owned reason an Investigation Agent Run ends, derived from settled Run facts rather than model preference. Completion, insufficient evidence, budget exhaustion, blocking, failure, cancellation, and discard remain distinct; the disposition is not permission to publish model content.
_Avoid_: Model stop reason, public result, publication decision, evidence verdict

**Model Response Candidate**:
A private, non-authoritative structured result derived from the final model response and bound to one settled Agent Run. It remains ineligible for ordinary callers and future context until Workspace publication policy accepts an exact output.
_Avoid_: Published Workspace Output, verified fact, public model delta, Artifact

**Workspace Publication Decision**:
The deterministic publish-or-withhold decision over one Model Response Candidate and its current Run, Session, Case-context, citation, authorization, and disclosure basis. It is a content-eligibility decision, not a CTI truth judgment.
_Avoid_: Agent Run settlement, model confidence, Case acceptance, external publication

**Published Workspace Output**:
The caller-visible, non-authoritative output durably admitted by one Workspace Publication Decision. It contains only validated public blocks and citations and does not create a Workspace Artifact by default.
_Avoid_: Model Response Candidate, Case fact, Workspace Artifact, external publication

**Workspace Turn**:
The caller-visible operation created by one Workspace prompt, with stable identity, streamed events, cancellation, and exactly one terminal result; it contains pre-run Task Understanding and, only after admission, an Investigation Agent Run plus Workspace publication decisions.
_Avoid_: Model turn, Session, Agent loop

**Session**:
A navigable interaction history used to continue, compact, or branch Agent work; it is not the authoritative investigation record.
_Avoid_: Case

**Workspace**:
The task-scoped environment that combines an Original User Task, layered Case Context, a Working Set, and available investigation capabilities for one or more Agent Runs.
_Avoid_: Case database, transcript

**Workspace State**:
The coordinated task-scoped state needed to continue a Workspace, including its binding, User Task, Case Projection receipt, Working Set, Session, Workspace Artifacts, and synchronization status; it references but does not copy the authority of other systems.
_Avoid_: Memory blob, Case copy, Session

**Workspace Capability**:
A closed, trusted runtime ability that Workspace policy may make available under the current Access Principal, Case, Use Purpose, task, dependency, qualification, and budget basis; model-visible tool presence or a proposed capability need may request it but never activates or authorizes it.
_Avoid_: Tool name, Capability Grant, model permission, workflow plugin

**Workspace Artifact**:
A persistent, versioned, non-authoritative output derived within a Workspace, such as an Assessment Draft or Assessment Evidence Unit.
_Avoid_: Case fact, Intelligence Resource, Session message

**Operation Intent**:
The durable immutable record of one exact operation, its trusted contract, version-bound inputs, declared outputs, dependencies, and possible effects committed before it can execute; it proves intent admission, not execution or outcome.
_Avoid_: Tool call log, result, receipt, dispatch proof

**Effect Reservation**:
A durable local exclusion over the declared possible effect domains of a remote operation while its outcome or Projection inclusion is unresolved; it blocks only intersecting dependency chains and is not a remote lock.
_Avoid_: Global Workspace freeze, remote transaction lock, failed write

**Fence Dependency**:
A versioned authorization, policy, data, basis, or execution prerequisite that can deny an operation or invalidate its output but that the operation does not declare it may change; it does not become an unknown-effect reservation merely because the operation reads it.
_Avoid_: Possible Effect Domain, global lock, optional context

**Possible Effect Domain**:
An owner-approved canonical authority key that a remote effect may change in the worst case; only these domains and their dependency closure are reserved while the outcome is unknown.
_Avoid_: Fence Dependency, requested payload field, inferred string prefix

**Dispatch Permit**:
A Journal-issued proof that the exact Effect Intent, fences, possible domains, and `may_have_dispatched` marker definitively committed before remote I/O; it authorizes transport of that unchanged request only and is not a remote receipt.
_Avoid_: Capability Grant, network success, Case permission, receipt

**Case Projection**:
A complete authority-enriched representation of one declared Profile within the current Access Principal, Use Purpose, and authorization view. It adds revisioned Case Management semantics over an exact Orientation/source-evidence basis; it does not replace or erase that observational provenance.
_Avoid_: Case snapshot copy, full Case export

**Case Orientation**:
The actor-scoped safety layer for selected stock OpenCTI Case observations. It is the current standalone investigation baseline and remains the observational basis beneath a future Case Projection; it is observation evidence, never Case authority or a write basis.
_Avoid_: Case snapshot, Case Revision, disposable pre-Projection view

**Case Context**:
The model-visible layered composition of the current Case Orientation baseline and, when available, a Case Projection overlay bound to that baseline. It preserves authority and provenance labels and does not duplicate equal source bodies.
_Avoid_: Orientation-or-Projection switch, merged authority blob, Case copy

**Orientation Binding**:
The complete identity of one Case Orientation's Case, Access Principal and credential scope, Use Purpose, selection, source instance, Adapter qualification, schema, and target. Two Orientations with different bindings are not interchangeable even when their rendered content is equal.
_Avoid_: Workspace epoch, Case Revision, cache key

**Context Dependency Set**:
The closed set of Case Orientation blocks and qualified Session chains actually admitted to one provider context and its durable save point. Its authenticated receipt records those actual inputs; it is not a model-supplied claim or a global Workspace epoch. The delivered `orientationDependencies` prompt field is only a migration encoding of this set.
_Avoid_: Turn hint, tool argument, inferred prompt scope, full-Workspace freeze

**Context Generation**:
A signed, monotonically increasing eligibility generation for one Context Dependency. A committed material change or authorization transition advances only affected generations, so returning to equal content cannot revive history admitted under an earlier generation. It is not a Case Revision, content version, timestamp, or standalone stale marker.
_Avoid_: Stale flag, Workspace epoch, Case Revision

**Context Snapshot Receipt**:
Authenticated evidence written with one durable Pi save point that binds the exact admitted entries, actual Context Dependency generations, Session/branch and Agent Run identity, and relevant message/tool-result digests. It proves context eligibility and integrity, not Case truth or model correctness.
_Avoid_: Case receipt, transcript summary, public content digest

**Logical Provider Invocation Artifact**:
The non-secret digest evidence for one Prepared Provider Invocation after final context conversion and ordering, tool schemas, model, credential binding, token policy, and closed provider options; it identifies logical Adapter input, never provider wire bytes.
_Avoid_: Wire payload, provider receipt, prompt summary, model output

**Prepared Provider Invocation**:
Pi's private, recursively snapshotted, generation-scoped resolved request-model/context/tool/request-options/auth value behind one opaque reference. Its model identity comes from the actual resolved Model, not a registry; model headers and post-auth request-options headers remain distinct logical inputs. Caller mutation cannot change it; only one matching committed single-use permit can consume it, and a missing prepared value is never reconstructed.
_Avoid_: Caller request object, replay envelope, provider payload, durable prompt copy

**Model Input Receipt**:
Workspace-owned pre-invocation evidence binding one Logical Provider Invocation Artifact to its ordered Session projection, Orientation, Working Set, Resource Capsules, tool schemas, model, credential identity, and closed options. It proves a possibly invoked logical Adapter input, not HTTP wire bytes, remote receipt, replay, or a reproducible/correct output.
_Avoid_: Retrieval Receipt, wire receipt, prompt summary, replay proof, model-output proof

**Full Orientation Reopen**:
A new complete actor-scoped observation that replaces one affected Orientation rather than patching or resuming an earlier read. It establishes current read evidence, not a historical snapshot or Case Revision.
_Avoid_: Delta, stream resume, Session restore

**Stale Capsule**:
A non-sensitive notice that prior analysis is unusable for current reasoning while the underlying history remains outside the active model context. It contains no summary of the excluded material and is neither evidence nor authority.
_Avoid_: Stale summary, redacted evidence, replacement Orientation

**Projection Profile**:
A stable, versioned, Use-Purpose-specific semantic selection through which a Case system presents Case information to a Workspace without exposing its internal model; every declared block has an explicit presence state rather than disappearing by omission.
_Avoid_: OpenCTI schema mirror, field dump

**Compiled Case Contract Catalog**:
An immutable, digest-addressed set of trusted Projection Profiles, Case Write Capabilities, canonical dependency keys, renderers, schemas, and operation recipes whose definitions have passed structural and semantic validation; deployment-specific Adapter qualification is recorded separately.
_Avoid_: Runtime plugin registry, model tool list, remote guarantee

**Capability Grant**:
Case Management's current Access-Principal-, Case-, Use-Purpose-, policy-, and lifecycle-specific decision that one Case Write Capability is available for consideration; it must be revalidated at execution boundaries and does not replace receiver-side authorization.
_Avoid_: Tool visibility, manifest definition, cached permission

**Working Set**:
The task-relevant subset of Case and intelligence material currently selected for model reasoning.
_Avoid_: Case State, global knowledge base

**Assessment Evidence Unit**:
A versioned, Case- and purpose-bound grouping of semantically compatible observations or assertions used as one comparison row in an Assessment Draft while retaining references to all underlying Intelligence Resources.
_Avoid_: Intelligence Resource, proof, arbitrary data chunk

**Assessment Lens**:
The declared User Task perspective, focus, preferences, and exclusions that shape relevance and grouping for an Assessment Evidence Unit without changing source content, provenance, or authority.
_Avoid_: Case truth, hidden bias, permission scope

**Assessment Unit Version**:
An immutable realization of one Assessment Evidence Unit under a specific Case Revision, Assessment Lens, resource basis, Coverage Boundary, and grouping rule.
_Avoid_: Mutable evidence row, current Case state

**Analytic Divergence**:
A state in which different Assessment Lenses or reasoned interpretations produce different grounded Units or Provisional Assessments for the same Case; it is not by itself a validation error.
_Avoid_: Basis Conflict, system failure, accepted contradiction

**Unit Visibility**:
The audience and discoverability policy for an Assessment Evidence Unit, independent from whether it is eligible for model-context injection or has Case authority.
_Avoid_: Authorization, authority level, context inclusion

**Private Assessment Unit**:
An Assessment Evidence Unit visible only within its originating authorized Workspace and actor scope; it is the default first-release Unit state and is not part of the Case Projection.
_Avoid_: Shared analysis, Case finding, accepted evidence

**Coverage Boundary**:
The declared population, time range, filters, grouping rule, counts, and omissions represented by a Working Set or Assessment Evidence Unit.
_Avoid_: Token truncation, implicit completeness

**Workspace Finding**:
A task-scoped result produced or retrieved during investigation that remains non-authoritative until accepted by the appropriate owning context.
_Avoid_: Evidence, Case fact

**Assessment Draft**:
A structured comparison produced directly by the Agent for validation, containing candidate judgments, grounded rationales, uncertainties, and proposed conclusions; it is not yet a Provisional Assessment or Case state.
_Avoid_: Provisional Assessment, accepted attribution, hidden reasoning

**Provisional Assessment**:
A versioned, non-authoritative comparison of competing Candidate Findings against the same evidence basis, with explicit contradictions, assumptions, source lineages, and conditions that would change the ordering.
_Avoid_: Accepted judgment, confidence score, final attribution

**Leading Hypothesis**:
An optional candidate preference stated in an Assessment Draft and recordable in a validated Provisional Assessment when one candidate provisionally dominates its alternatives within the bound scope and basis.
_Avoid_: Winner, most likely actor, Investigation Priority

**Investigation Priority**:
A relative ordering of collection or analysis actions by their expected ability to reduce decision-relevant uncertainty under current cost, risk, permission, and time constraints; it is separate from hypothesis ordering.
_Avoid_: Leading Hypothesis, confirming search

**Assessment Scope**:
The single investigation question, subject and time boundary within which a Provisional Assessment compares one bounded candidate set.
_Avoid_: Entire Case, unrestricted graph neighborhood

**Assessment Basis**:
The immutable versioned set of candidates, Intelligence Resources, Source Lineages, assumptions, and Case state against which a Provisional Assessment was made.
_Avoid_: Current Case, mutable Working Set

**Basis Conflict**:
A state in which an Assessment Basis is no longer current or valid enough to accept its proposed assessment, requiring re-evaluation from a new basis.
_Avoid_: Low confidence, Case write rejection

**Accepted but Unsynchronized**:
A state in which a terminal `applied` receipt proves that a new Case effect committed, but the Workspace has not yet obtained the exact receipt-linked current Case Projection inclusion proof; `satisfied_without_change` never enters this state.
_Avoid_: Indeterminate Effect, rolled-back write, failed proposal

**Indeterminate Effect**:
A suspended operational state in which no authoritative proof can establish whether a remote mutation committed; only its declared effect domains and downstream dependency chains remain blocked until stronger proof or governed resolution is available.
_Avoid_: Failed write, safe retry, rejected proposal, Accepted but Unsynchronized

**Case Write Capability**:
A named kind of Case change that the Workspace may propose under an explicit risk and approval policy.
_Avoid_: Direct mutation, unrestricted write

**Capability Risk Tier**:
The agreed impact class of a Case Write Capability, based on reversibility, authority change, investigation scope, external effect, and propagation.
_Avoid_: Tool permission

**Freshness Mode**:
The consistency requirement governing whether a Workspace may use a previously confirmed Case Projection for a particular activity.
_Avoid_: Cache timeout
