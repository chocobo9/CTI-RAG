# `workspace-memory-coordination/v1` Contract

Status: **Superseded design candidate.** This document is retained as
historical input for the new Agent Memory Management contract. It is no longer
the top-level Memory architecture or implementation authority. Its
qualification, revalidation, routing and adoption behavior must be re-evaluated
as part of the first-class Memory Management design adopted by ADR 0021.

## 1. Product outcome

CTI-RAG must provide a complete Memory capability without creating a shared
Memory persistence authority.

Existing owners continue to store and govern their own meanings. Agent
Investigation Workspace provides the missing coordination behavior:

1. reconstruct current task memory from known owners;
2. decide whether additional historical recall is needed;
3. route each need to the owner that governs that meaning;
4. establish eligibility before relevance;
5. select a bounded, labelled and revalidatable view;
6. admit that view into one Agent Run;
7. route settled retention candidates back to their correct owner; and
8. prevent corrected, withdrawn, deleted or stale material from re-entering
   context.

This Module is not a database, vector store, transcript, Case copy, global
search engine, prompt renderer, Tool registry, or Provider Adapter.

## 2. Architecture

```text
Owner records
  Pi Session | Workspace task state | Case | Intelligence
        |
        v
Workspace Memory Coordination
  reconstruct -> decide -> route -> qualify -> rank -> adopt -> revalidate
        |
        v
Qualified Memory View + Memory Adoption Receipt
        |
        v
Initial/Later Context Assembly
  + system instructions + active Tools
        |
        v
Pi AgentContext -> Provider Dispatch -> Model
```

Memory Coordination and Context Assembly are different Modules:

- Memory Coordination decides which remembered material is safe and useful for
  one consumer.
- Context Assembly decides how already-qualified material, current system
  instructions and active Tools are represented through Pi.
- Provider Dispatch remains the only canonical owner of actual model messages,
  Tool schemas and invocation digests.

The previous seven items may remain a requirements checklist. They are not a
Memory schema and are not seven new stored records.

## 3. Owning Module and external Interface

The deep Module is Workspace-owned `WorkspaceMemoryCoordinator`. It hides owner
routing, eligibility, ranking, conflict handling, budgeting, revalidation and
candidate routing behind three operations:

```typescript
interface WorkspaceMemoryCoordinator {
	prepare(input: MemoryPreparationInputV1): Promise<MemoryPreparationOutcomeV1>;
	revalidate(input: MemoryRevalidationInputV1): Promise<MemoryRevalidationOutcomeV1>;
	settle(input: MemorySettlementInputV1): Promise<MemorySettlementOutcomeV1>;
}
```

### `prepare`

Used before an Agent Run and for an admitted bounded in-Run recall request.
It reconstructs mandatory memory, decides and executes optional recall when
needed, and returns an ephemeral qualified view plus durable non-content
adoption evidence.

### `revalidate`

Used immediately before disclosure to the model and again at Provider-start
admission. It checks the exact owner evidence and Context Generations used by
the prepared view. It either confirms the unchanged view or invalidates it; it
never silently patches a prepared view.

### `settle`

Used only after the Run and Workspace save point have settled. It classifies
explicit user requests and model-proposed retention candidates, routes them to
their owning workflow, and records accepted/rejected/deferred routing outcomes.
It does not make Case facts, Intelligence Resources or cross-Case lessons
authoritative.

## 4. Owner-local seams

Memory Coordination consumes owner-qualified reads. It does not define one
generic Memory Repository.

| Meaning | Owner used | Memory Coordination responsibility |
| --- | --- | --- |
| committed dialogue, Tool results, branch and compaction ancestry | Pi Session | request the current qualified Session projection and preserve chronology |
| current task state and task-scoped non-authoritative work | Workspace | load the current committed task basis and owner evidence |
| current or historical investigation authority | Case owner | request a principal/use-purpose-qualified view and preserve revision/status labels |
| reusable sourced material and provenance | Intelligence owner | request qualified material and preserve version/provenance/use status |
| cross-Case experience or durable user/team preference | no accepted owner | return `unsupported_scope`; do not persist or recall it |

Every owner seam must provide:

- an opaque source reference;
- current Access Principal, Case, Use Purpose and Context Consumer eligibility;
- authority/status labels;
- exact version or generation evidence;
- a bounded renderable projection;
- correction, withdrawal, expiry and deletion status; and
- a way to revalidate the evidence without semantic search.

Owner-specific public Interfaces remain owned by their packages/contracts.
Memory Coordination may use internal Adapters but cannot standardize away their
different authority meanings.

## 5. Product artifacts

### 5.1 Qualified Memory View

`QualifiedMemoryViewV1` is ephemeral and exists for one consumer, one task, one
Run attempt and one disclosure budget.

```typescript
interface QualifiedMemoryViewV1 {
	protocol: "workspace-qualified-memory-view/v1";
	viewId: string;
	workspaceRef: string;
	taskRef: string;
	runAttemptRef: string;
	mandatory: {
		task: readonly QualifiedMemoryItemV1[];
		case: readonly QualifiedMemoryItemV1[];
		workingState: readonly QualifiedMemoryItemV1[];
		continuity: readonly QualifiedMemoryItemV1[];
	};
	optionalRecall:
		| { kind: "not_needed"; reasonCode: string }
		| { kind: "empty"; route: MemoryOwnerRouteV1; reasonCode: string }
		| { kind: "selected"; route: MemoryOwnerRouteV1; items: readonly QualifiedMemoryItemV1[] };
	conflicts: readonly QualifiedMemoryConflictV1[];
	disclosureBudget: MemoryDisclosureBudgetV1;
	binding: MemoryBindingV1;
}
```

It does not contain system instructions or active Tool definitions. Those are
not Memory and remain inputs to Context Assembly.

### 5.2 Qualified Memory Item

Each item contains only the bounded model-visible projection plus the labels
needed to interpret and revalidate it:

```typescript
interface QualifiedMemoryItemV1 {
	itemRef: string;
	owner: "session" | "workspace" | "case" | "intelligence";
	meaning: string;
	authority: "current_authority" | "historical_authority" | "non_authoritative" | "interaction";
	status: "current" | "historical" | "challenged";
	sourceRef: string;
	sourceVersionRef: string;
	observedAt?: string;
	validAt?: string;
	modelVisibleProjection: unknown;
	projectionDigest: string;
	eligibilityEvidenceRef: string;
}
```

`modelVisibleProjection` is data, never an instruction role, permission,
authorization or Tool activation. Context Assembly must delimit it as untrusted
owner material.

### 5.3 Memory Binding

`MemoryBindingV1` is durable, non-secret evidence containing owner references,
versions/generations, projection digests, selection order, policy revision and
budget evidence. It contains no copied transcript, Case body, Resource body,
credential or hidden search result.

It proves which owner material was selected. It does not compete with Provider
Dispatch's digest of the actual final model context.

### 5.4 Memory Adoption Receipt

`MemoryAdoptionReceiptV1` records:

- whether optional recall was needed;
- which owner routes were attempted;
- qualification and exclusion counts using non-sensitive reason codes;
- selected item references and order;
- conflict and omission disclosures;
- final Memory Binding digest; and
- the Run attempt for which the view was admitted.

The receipt is committed with the Run admission/save-point lifecycle. It is not
a memory item and cannot itself be recalled as task content.

### 5.5 Memory Candidate Routing Receipt

`MemoryCandidateRoutingReceiptV1` records how each post-settlement retention
candidate was classified and routed:

- `routed_to_existing_owner`;
- `already_owned_no_copy`;
- `rejected_unsettled`;
- `rejected_unsupported_scope`;
- `rejected_missing_source`;
- `rejected_unauthorized`;
- `rejected_non_reusable`;
- `deferred_owner_workflow`.

Routing does not mean the destination owner admitted the candidate.

## 6. Preparation lifecycle

### 6.1 Mandatory reconstruction

Before every new Agent Run, `prepare` reconstructs:

- committed Original User Task and Admitted Task Context;
- current task-scoped Workspace state;
- current authorized Case view;
- eligible Session continuity;
- any other mandatory owner view required by the selected Run profile.

This uses exact owner references and qualified reads. It performs no global
semantic search and creates no duplicate owner records.

Failure to obtain a mandatory input fails preparation. Historical material
cannot substitute for missing current authority.

### 6.2 Optional recall decision

Optional recall is evaluated after mandatory reconstruction. It is selected only
for:

- an explicit reference to prior work, correction, preference or unfinished
  investigation;
- a task whose meaning requires comparison or change over time;
- an identified gap that a known eligible owner may fill; or
- an admitted bounded historical dependency proposed during a Run.

The decision may be `not_needed`. Every Run does not search memory.

### 6.3 Route before search

The coordinator first selects the owner route from the requested meaning.
Unsupported cross-Case experience or preference scope stops with
`unsupported_scope`. It is never widened into global semantic search.

### 6.4 Eligibility before relevance

An owner candidate is excluded before ranking when current Access Principal,
Case, Use Purpose, authorization, markings, status, version, retention,
deletion or Context Consumer eligibility cannot be proved.

The coordinator receives no content or metadata that would disclose the
existence of an ineligible item to the caller or model.

### 6.5 Relevance and bounded adoption

Ranking occurs only inside one eligible owner result set. The coordinator:

- prefers current authority to advisory history;
- preserves chronology where the content is conversational;
- collapses duplicate projections without erasing distinct provenance;
- exposes material conflicts instead of silently merging them;
- observes disclosure and token budgets;
- permits an empty result; and
- retains the exact evidence needed for revalidation.

## 7. Context adoption

Context Assembly consumes `QualifiedMemoryViewV1`, not owner repositories and
not raw search results.

It combines the qualified view with:

- trusted system/developer instructions;
- the current user request according to Pi conversation semantics; and
- the separately admitted active Tool set.

It then produces one Pi `AgentContext`. Pi context-entry policy remains the
owner of Session entry selection, and Provider Dispatch remains the sole owner
of final message/Tool snapshots and invocation digests.

The Memory Binding and final Provider invocation evidence are joined in the
Run's Model Input Receipt. Neither side predicts or recomputes the other's
digest.

## 8. Revalidation and invalidation

The coordinator revalidates before model disclosure and Provider-start
admission. Any change in an admitted dependency invalidates the complete view:

- Access Principal, Case or Use Purpose;
- authorization or markings;
- Case revision/status;
- Session branch, compaction ancestry or generation;
- Workspace task or working-state version;
- Intelligence resource version/use status;
- correction, withdrawal, expiry or deletion;
- policy/ranking/rendering revision; or
- disclosure budget.

The result is either `valid_unchanged` or `invalidated(reasonCode)`. A caller
must run `prepare` again to obtain a new view. Returning from state A to equal
content after state B does not revive the old binding.

## 9. Retention lifecycle

Retention work occurs only at an owner-controlled stable point:

- explicit remember/correct/delete requests may create an immediate candidate;
- ordinary candidates wait for settled Run and committed save point;
- incomplete streaming output, private candidates, cancelled/failed/discarded
  work and rolled-back Tool results are rejected.

The coordinator classifies meaning before routing. If an item is already held
and discoverable by its owner, the result is `already_owned_no_copy`.

The first version creates no cross-owner index, embedding store or persistent
recall cache. Therefore correction, withdrawal and deletion take effect through
owner revalidation without a shadow copy. Any later index/caching proposal must
add owner-triggered invalidation and a deletion-completion receipt before it can
pass its own gate.

## 10. Failure closure

| Failure | Closed outcome |
| --- | --- |
| mandatory owner view unavailable or unprovable | preparation fails; no Agent Run starts |
| optional owner unavailable and task remains valid without it | continue with observable `optional_recall_omitted` |
| optional owner unavailable and task depends on it | fail or request clarification under the task contract |
| ineligible or deleted item | exclude without existence leakage |
| no eligible/relevant result | empty optional recall; model may abstain |
| conflicting eligible history | bounded labelled conflict |
| owner drift after preparation | invalidate; no disclosure or Provider start |
| model requests wider scope | deny/narrow deterministically |
| retention candidate lacks settled source | reject; no owner mutation |
| destination owner rejects candidate | record routing outcome; do not retry as another meaning |

## 11. Evaluation

Memory is evaluated against the same task with optional recall disabled.
Acceptance must cover:

- recall-needed and owner-routing accuracy;
- eligible-result precision and useful coverage;
- zero unauthorized, deleted, withdrawn or wrong-version disclosure;
- correction/deletion propagation;
- contradiction labelling and abstention;
- provenance preservation;
- downstream task correctness;
- anchoring and hallucination regressions;
- token, latency and operational cost; and
- user-visible explanation of why optional material was used or omitted.

The benchmark includes no-result, adversarial similarity, authorization drift,
version drift, A-to-B-to-A return, deletion, conflicting history and optional
owner outage.

Numeric quality thresholds are a product decision that must be frozen before
optional recall implementation.

## 12. Candidate public acceptance matrix

The eventual public seam is the Workspace operation that prepares and admits one
Agent Run, not private ranking helpers.

1. Mandatory reconstruction reads each required owner once from a coherent
   basis and starts no Run on failure.
2. A self-contained task selects `not_needed` and performs zero optional owner
   searches.
3. Each history-dependent need routes to the correct owner before search.
4. Eligibility failures occur before ranking and leak no item existence.
5. Empty eligible recall is a valid observable outcome.
6. Current authority, historical authority and advisory material remain
   distinguishable.
7. Conflicts are labelled and never silently merged.
8. Selected items obey disclosure/token budgets with declared omissions.
9. Owner drift before disclosure invalidates the view and starts no Provider.
10. A-to-B-to-A content return cannot revive an earlier binding.
11. Correction, withdrawal and deletion remove the item from every current
    recall path.
12. Cancelled, failed, discarded or uncommitted work creates no retention
    routing.
13. Settled candidates route by meaning and never create duplicate owner data.
14. Final Model Input Receipt binds the Memory Adoption Receipt to Pi's actual
    Provider invocation evidence without duplicate canonicalization.
15. One Workspace uses one leased Session generation, one Workspace-lifetime
    Harness and one Provider lifecycle.

This matrix is review material until all blockers below close.

## 13. Design Gate

- **Verdict:** FAIL
- **Owner:** Workspace owns coordination; source meanings remain owner-local.
- **Interface:** `prepare`, `revalidate`, `settle` candidate.
- **Input authority:** existing owner receipts and qualified views.
- **Output/evidence:** ephemeral Qualified Memory View plus non-content binding,
  adoption and routing receipts.
- **Failure closure:** specified at capability level.
- **Secret isolation:** no credentials or secret-bearing prepared values.
- **Provider lifecycle count:** exactly one.
- **Workspace exposure:** only through Run preparation/admission and settlement.
- **Backward compatibility:** no implementation exists; current staging path
  remains migration-only.
- **Public acceptance seam:** Workspace Run admission/settlement.
- **Remaining blockers:**
  1. owner-specific qualified-read/revalidation Interfaces have not been mapped
     to existing accepted public seams;
  2. first optional-recall workflow, numeric budgets/quality gates and user
     inspect/correct/forget behavior remain product choices.

No development task may be dispatched while this gate is FAIL.
