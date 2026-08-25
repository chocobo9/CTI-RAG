# Durable Operation Journal Contract

Status: Accepted and frozen strict-R1 target contract; not a current Orientation-cycle dependency.

This document defines the private persistence Module beneath `OperationCoordinator`. It specifies semantic atomic transitions and recovery evidence, not table CRUD. PostgreSQL is the reference production Adapter; a fault-injectable in-memory Adapter runs the same conformance suite.

`FacadeEffectBindingV1`, `CaseOperationStatusV1`, and `ProjectionInclusionProofV1` are canonical shared types from the [Case Management Facade Contract](case-management-facade-contract.md). The Journal stores and validates those envelopes unchanged rather than defining lookalike receipt identities.

## 1. Decision

Use a constrained relational journal with normalized current facts and immutable observations. Do not use a generic repository collection and do not require full Event Sourcing for the first slice.

The journal is local authority for:

- exact Operation Intents and input/dependency bindings;
- declared Output Claims and effect domains;
- local output publication and derivation edges;
- remote Effect Intents, dispatch knowledge, receipts, and Projection inclusion proofs;
- reservations that exclude overlapping work while an effect may still commit;
- archived catalog/schema/decoder references needed to recover old operations; and
- the durable Workspace image needed to resume.

It is not authority for current Case or I&E truth. Those values remain versioned remote inputs whose references and observations are recorded.

## 2. Deep Module Interface

**Problem solved:** exposing tables or repositories makes callers reconstruct admission, publish, receipt, reservation, and crash invariants differently.

**Inputs:** trusted compiled operation plans and typed observations from qualified Adapters.

**Output:** admission decisions, atomic observation decisions, recovery claims, and a complete Workspace recovery image.

**Boundary:** callers never decide transaction grouping, mutate receipt strength, release reservations, rebuild dependency indexes, or garbage-collect archives directly. The Module does not perform remote I/O.

**Failure behavior:** ambiguous local commit acknowledgment is resolved internally by stable transition identity/digest lookup. Constraint or evidence contradiction fails closed, keeps the smallest safe reservation, and raises an integrity incident.

```typescript
interface DurableOperationJournal {
	resume(input: WorkspaceResume): Promise<WorkspaceRecovery>;
	admit(input: BoundOperationPlan): Promise<AdmissionDecision>;
	observe(input: OperationObservation): Promise<ObservationDecision>;
	claimRecovery(input: RecoveryClaim): Promise<RecoveryClaimDecision>;
}

interface WorkspaceResume {
	workspaceBindingId: string;
	expectedBindingDigest: string;
	requestedAt: string;
}

interface WorkspaceRecovery {
	journalRevision: string;
	bindingState: "current" | "migration_required" | "integrity_blocked";
	runnableOperationIds: readonly string[];
	effectsRequiringStatusLookup: readonly FacadeEffectBindingV1[];
	effectsRequiringProjectionProof: readonly FacadeEffectBindingV1[];
	ownerHeads: readonly { dependencyRef: DependencyReferenceV1; version: string }[];
	activeReservationRefs: readonly string[];
	quarantinedPartitions: readonly ReceiptAuthorityQuarantineV1[];
	blockedArchiveRefs: readonly string[];
}

type AdmissionDecision =
	| { kind: "admitted"; operationId: string; journalRevision: string; runnable: boolean }
	| { kind: "duplicate"; operationId: string; journalRevision: string; state: "admitted" | "running" | "completed" | "recovering" }
	| { kind: "blocked"; operationId: string; blockingReservationRefs: readonly string[] }
	| { kind: "rejected"; code: "binding_mismatch" | "contract_archive_missing" | "target_conflict" | "integrity_conflict" }
	| { kind: "indeterminate_local_commit"; transitionId: string; transitionDigest: string; externalActionAllowed: false };

interface DispatchPermit {
	protocol: "journal-dispatch-permit/v1";
	operationId: string;
	effectBinding: FacadeEffectBindingV1;
	markerTransitionId: string;
	markerDigest: string;
	issuedAt: string;
}

interface AppliedObservationDecision {
	kind: "applied";
	journalRevision: string;
	operationState: "admitted" | "running" | "completed" | "failed" | "recovering" | "integrity_blocked";
	publishedOutputIds: readonly string[];
	releasedReservationRefs: readonly string[];
	runnableOperationIds: readonly string[];
	quarantinedPartitions: readonly ReceiptAuthorityQuarantineV1[];
	dispatchPermit?: DispatchPermit;
}

type ObservationDecision =
	| AppliedObservationDecision
	| { kind: "rejected"; code: "fence_rejected" | "invalid_observation" | "identity_digest_mismatch" | "impossible_transition" | "stale_recovery_fence" | "target_conflict"; operationId: string; journalRevision: string }
	| { kind: "indeterminate_local_commit"; transitionId: string; transitionDigest: string; externalActionAllowed: false };

interface RecoveryClaim {
	workerId: string;
	expectedJournalRevision: string;
	maxItems: number;
	leaseUntil: string;
}

interface RecoveryBatch {
	claimId: string;
	fencingToken: string;
	journalRevision: string;
	leaseUntil: string;
	items: readonly {
		operationId: string;
		kind: "resume_execution" | "status_lookup" | "projection_sync" | "authorization_cleanup";
		effectBinding?: FacadeEffectBindingV1;
	}[];
}

type RecoveryClaimDecision =
	| { kind: "claimed"; batch: RecoveryBatch }
	| { kind: "stale_journal_revision"; currentJournalRevision: string }
	| { kind: "none_available"; journalRevision: string };
```

These closed outcomes are the shared black-box conformance surface. An implementation may split private helpers but must not leak row-level coordination to operation recipes. The persistence Adapter first attempts authoritative transition lookup after acknowledgment loss. When lookup still cannot resolve the commit, it returns `indeterminate_local_commit`; the caller may only resume/lookup that same transition and receives no `DispatchPermit` or publication IDs.

### Dispatch Permit

**Problem solved:** committing Effect Intent before send is insufficient if a process can perform remote I/O without definitive proof that the durable dispatch marker and reservations committed.

**Inputs:** exact `FacadeEffectBindingV1`, current finalization/fence evidence, and a stable marker transition identity/digest.

**Output:** one `DispatchPermit` returned only after the Journal definitively commits `may_have_dispatched` for that binding.

**Boundary:** the permit authorizes transport of the already-bound request only. It is not Case permission, a remote receipt, proof that bytes were sent, or authority to change/rebase/re-key the effect.

**Failure behavior:** before-commit failure or unknown acknowledgment returns no permit and prohibits remote I/O. Recovery looks up the transition; authoritative absence permits a new fence evaluation, while committed presence means another process may have sent and only same-binding lookup/replay is safe.

## 3. Durable concepts

### 3.1 Workspace Binding

**Problem solved:** recovery must not attach an unfinished Case operation to another actor, purpose, Case, Session branch, catalog, or Revision Authority.

**Inputs:** Workspace ID, actor, purpose, Case, authority, Session branch/compaction generation, catalog and activation digests.

**Output:** immutable binding identity plus current durable heads for task, Lens, Working Set, Projection receipt, and Session reference.

**Boundary:** Session transcript bodies and current remote Projection bodies are not authoritative durable memory; they are referenced or reconstructable according to retention policy.

**Failure behavior:** binding mismatch opens a separate Workspace or requires explicit migration. It never reinterprets existing operations under a new actor, authority, catalog, or branch.

### 3.2 Operation Intent

**Problem solved:** a late or recovered result is unsafe without a durable record of the exact request, inputs, dependencies, outputs, and contract that existed before execution.

**Inputs:** compiled recipe, normalized request, trusted bindings, input versions/digests, output claims, effect declaration, archive references, and transition identity/digest.

**Output:** immutable admitted operation and its initial reservations/dispatcher eligibility.

**Boundary:** an Operation Intent is evidence of planned work, not proof that local or remote execution began or succeeded.

**Failure behavior:** same operation/transition identity with another digest is an integrity incident. Missing archive/schema references reject admission. A failed atomic admission creates no partial operation and no dispatcher eligibility.

### 3.3 Output Claim

**Problem solved:** completed results must publish only to declared local targets and dependency chains.

**Inputs:** output type/publication class, target identity, expected local head, exact derivation references, and validation contract.

**Output:** a pending claim that can be fulfilled once by an atomic publication group or terminated without output.

**Boundary:** partial streams and progress observations cannot fulfill claims. Model-originated current output conservatively binds every actual model-visible input unless trusted deterministic code proves a narrower derivation.

**Failure behavior:** target CAS conflict, stale input, missing dependency, invalid output, or authorization loss publishes nothing for that predeclared `atomicGroupId`. Claims in another group remain eligible only when their own `dependencyInputIds` and validation contract are disjoint and valid; grouping cannot be invented after execution.

### 3.4 Effect Intent

**Problem solved:** remote I/O may commit after timeout or local crash, so its exact identity and possible impact must exist durably before dispatch.

**Inputs:** stable operation/idempotency identity, canonical request digest, exact payload/fences, target contract, receipt lookup key, possible Effect Domains, and archive decoder.

**Output:** immutable effect record and dispatcher eligibility committed with its reservations.

**Boundary:** Effect Intent is not dispatch proof, receipt, or permission to generate a new identity during recovery.

**Failure behavior:** no remote dispatch is allowed until the effect record and reservations are durably committed. Unknown local commit acknowledgment is looked up by transition identity; replay uses the identical digest only after authoritative local absence.

### 3.5 Effect Reservation

**Problem solved:** overlapping work must not proceed while a remote effect may have committed but its outcome or Projection inclusion remains unknown.

**Inputs:** declared typed Effect Domains and authority-mandated broad concurrency domains.

**Output:** a durable exclusion over only intersecting dependency chains.

**Boundary:** this is a local scheduling/recovery exclusion, not a lock held in the remote authority. Exact owner/kind/key-version/canonical-tuple equality defines intersection; prefix or semantic guessing is forbidden.

**Failure behavior:** an uncertain dispatch retains reservations. A receipt proving terminal no-effect releases them atomically. `applied` retains synchronization-sensitive reservations until Projection inclusion proof. Undeclared observed impact quarantines the Capability and widens only to the smallest safe authority partition.

### 3.6 Receipt State

**Problem solved:** command authority, local transport knowledge, and Projection synchronization advance independently.

**Inputs:** immutable local observations and target-owned receipt/proof documents.

**Output:** three monotonic axes:

```typescript
interface DurableEffectState {
	authority: "none" | "terminal";
	localKnowledge: "dispatch_not_started" | "may_have_dispatched" | "queryable_unknown" | "proof_expired";
	synchronization: "not_applicable" | "accepted_but_unsynchronized" | "projection_proved";
	terminalReceiptRef?: string;
}
```

**Boundary:** local transport evidence cannot invent terminal authority. An `applied` receipt is not the same as Projection inclusion. A lease expiry is not no-effect.

**Failure behavior:** weaker, duplicate, or out-of-order observations cannot regress stronger state. Contradictory terminal receipts quarantine the operation and retain declared domains.

Legal combinations are closed:

| Authority | Local knowledge | Synchronization | Meaning |
|---|---|---|---|
| `none` | `dispatch_not_started` | `not_applicable` | no remote I/O permit has been issued |
| `none` | `may_have_dispatched` or `queryable_unknown` | `not_applicable` | exact effect may commit; reserve declared effect domains |
| `none` | `proof_expired` | `not_applicable` | local `indeterminate_effect`; reservations remain |
| `terminal` with `applied` receipt | `may_have_dispatched`, `queryable_unknown`, or `proof_expired` | `accepted_but_unsynchronized` | authority committed; exact Projection proof absent |
| `terminal` with `applied` receipt | `may_have_dispatched`, `queryable_unknown`, or `proof_expired` | `projection_proved` | exact receipt-linked Projection proof installed |
| `terminal` with `satisfied_without_change` or terminal no-effect | `may_have_dispatched`, `queryable_unknown`, or `proof_expired` | `not_applicable` | release effect reservations atomically |

All other combinations are rejected as integrity errors. In particular, `satisfied_without_change` never enters `accepted_but_unsynchronized`, and a terminal receipt with authoritatively absent dispatch permission is quarantined rather than normally merged.

`localKnowledge` has the closed dominance order `dispatch_not_started < may_have_dispatched < queryable_unknown < proof_expired`; it never regresses. Observations map mechanically:

| Observation | Local-knowledge transition |
|---|---|
| dispatch-permit transition authoritatively absent | remain `dispatch_not_started`; no send occurred through the qualified dispatcher |
| `prepare_dispatch` definitively committed | advance to `may_have_dispatched` before returning the permit |
| timeout, response loss, unavailable/404 lookup, or response without a valid matching terminal receipt | advance to `queryable_unknown` |
| lookup guarantee expires while `authority == none` | advance to `proof_expired` |
| valid matching terminal receipt | set `authority = terminal`; keep the current local-knowledge value, which no longer decides command disposition |
| any late transport observation after terminal | no axis changes and no new recovery work |
| later valid terminal after `proof_expired` | set `authority = terminal`; disposition then determines synchronization/reservation state |

An unknown local permit-transition acknowledgment is an `indeterminate_local_commit` call result, not a durable axis regression or advancement; authoritative lookup decides whether the stored state is still `dispatch_not_started` or already `may_have_dispatched`.

### 3.7 Archive Reference

**Problem solved:** unfinished operations must be decoded and validated under the contract that admitted them, not the current release.

**Inputs:** digest-addressed catalog, Profile, Capability, schema, canonicalizer, renderer, and receipt decoder artifacts.

**Output:** immutable references pinned by every operation that needs them.

**Boundary:** the first slice supports fixed v1 validators/decoders in the deployed binary and stores their canonical contract/schema bytes and digests. It prohibits unloading that support while a live reference exists; it does not dynamically load arbitrary historical executable code. Archives never contain hidden chain of thought.

**Failure behavior:** missing/corrupt archive prevents reinterpretation, retains reservations, and raises an integrity incident. Foreign-key/restrict behavior prevents deletion while referenced.

### 3.8 Dependency Index Generation

**Problem solved:** dependency-scoped challenge and scheduling need fast reverse lookup, but an index cannot become a second source of truth.

**Inputs:** operation intents, output derivation records, reservations, receipts, and a source journal revision.

**Output:** one active rebuildable generation.

**Boundary:** the journal/derivation facts are authoritative. Index rows are derived and disposable.

**Failure behavior:** build an inactive generation, catch up under a short source-revision fence, validate it, and atomically flip the active generation. Readers see the old complete generation or the new complete generation, never a partial hybrid. Missing index state falls back to conservative journal evaluation.

### 3.9 Receipt Authority Partition Quarantine

**Problem solved:** contradictory terminal receipts or a terminal receipt without possible dispatch invalidate a shared receipt guarantee, not only one row, and the safety stop must survive restart.

**Inputs:** receipt authority, Capability identity/version, target fingerprint, triggering operation/evidence digests, reason code, and smallest partition proven to share the failed guarantee.

**Output:** a durable active `ReceiptAuthorityQuarantineV1` checked by admission and dispatch-permit transitions.

**Boundary:** quarantine retains the triggering operation's Effect Domains, stops new dispatch for the same receipt-authority/Capability/target partition, and schedules audit of its other unresolved operations. It does not automatically reserve or freeze unrelated Case authorities, Capabilities, targets, I&E work, or Workspaces.

**Failure behavior:** crash/restart preserves quarantine. It clears only through a governed transition citing repaired qualification evidence and audit disposition; age, lease expiry, process restart, or one later good receipt cannot clear it.

```typescript
interface ReceiptAuthorityQuarantineV1 {
	quarantineId: string;
	receiptAuthorityId: string;
	capabilityId: string;
	capabilityVersion: string;
	targetFingerprint: string;
	reason: "contradictory_terminal" | "terminal_without_dispatch_permission" | "effect_outside_domain" | "durability_guarantee_failed";
	triggerOperationId: string;
	triggerEvidenceDigest: string;
	state: "active";
	recordedAt: string;
}
```

## 4. Bound operation plan

`BoundOperationPlan` is created only by the compiled trusted recipe/binder. Its minimum semantic content is:

```typescript
type DependencyKindV1 =
	| "authorization_scope"
	| "case_head"
	| "projection_block_head"
	| "projection_block_version"
	| "proposal_ledger_head"
	| "proposal_ledger_version"
	| "proposal_status"
	| "case_resource_membership"
	| "task_lens"
	| "session_branch"
	| "working_set_entry"
	| "working_set_selection"
	| "intelligence_resource"
	| "capability_policy"
	| "execution_config";

interface DependencyReferenceV1 {
	ownerId: string;
	kind: DependencyKindV1;
	keyVersion: "v1";
	canonicalTupleBase64: string;
	canonicalTupleDigest: string;
}

type PublicationClassV1 =
	| "historical_session_prose"
	| "working_set_entry"
	| "workspace_artifact"
	| "tool_intent"
	| "local_receipt"
	| "projection_materialization";

type CanonicalJsonValueV1 =
	| null
	| boolean
	| number
	| string
	| readonly CanonicalJsonValueV1[]
	| { readonly [key: string]: CanonicalJsonValueV1 };

interface BoundOperationPlan {
	workspaceBindingId: string;
	operationId: string;
	transitionId: string;
	transitionDigest: string;
	recipeId: string;
	recipeVersion: string;
	catalogDigest: string;
	activationDigest: string;
	archiveRefs: readonly string[];
	normalizedRequest: CanonicalJsonValueV1;
	inputs: readonly {
		inputId: string;
		dependencyRef: DependencyReferenceV1;
		versionOrDigest: string;
		fence: "authorization" | "current" | "basis" | "historical";
	}[];
	outputClaims: readonly {
		claimId: string;
		atomicGroupId: string;
		targetRef: string;
		expectedTargetVersion: string;
		publicationClass: PublicationClassV1;
		dependencyInputIds: readonly string[];
		replacementMode: "create" | "compare_and_replace" | "append_version";
		validationContractRef: string;
	}[];
	effect?: {
		binding: FacadeEffectBindingV1;
		fenceDependencyInputIds: readonly string[];
		mayEffectDomains: readonly DependencyReferenceV1[];
	};
}

interface OutputCandidateV1 {
	claimId: string;
	schemaRef: string;
	payload: CanonicalJsonValueV1;
	payloadDigest: string;
}
```

`FacadeEffectBindingV1` is the exact closed binding from the facade contract and is persisted without renaming `operationId`, `effectId`, `idempotencyKey`, `requestDigest`, or authority. `fenceDependencyInputIds` are prerequisites that can deny admission/dispatch but are not presumed changed by the effect. Only `mayEffectDomains` create unknown-outcome reservations.

`CanonicalJsonValueV1` is the closed transport value domain, not the business schema: numbers must satisfy `cti-jcs-sha256/v1`, while the archived recipe and referenced JSON Schema constrain the exact request and output shapes. Admission atomically commits the immutable operation, normalized exact inputs, output claims, effect intent, receipt/status key, every reservation, archive pins, and dispatcher eligibility. It rejects duplicate input/claim/group IDs, missing referenced input IDs, unrecognized kinds/classes, invalid canonical tuple encodings/digests, a request that fails the recipe schema, or an Effect Domain not constructed by the compiled binder. A crash exposes all or none of this aggregate.

## 5. Observation protocol

**Problem solved:** completion events arrive late, duplicated, out of order, partially, or after restart and need one mechanical merge path.

**Inputs:** stable operation and observation identities, closed typed evidence, and expected observation digest. `OperationCoordinator` obtains owner-current fence observations after execution; the Journal owns only local durable-head/CAS validation and evidence binding.

**Output:** atomic state transition, publication decision, newly runnable work, or an integrity/quarantine result.

**Boundary:** observations report facts; they do not choose dependencies, target rows, retry identity, or reservation release policy. Remote owner probes cannot be made atomic with the local transaction: they prove end-validation at `observedAt`, while the Journal atomically compares all Workspace-owned heads and exact expected owner evidence. A later remote change is caught by signals/probes and challenges dependents; only the remote Case command requires target-side atomic effect fencing.

**Failure behavior:** unknown variants, identity/digest mismatch, impossible transitions, or contradictory authority proof fail closed without partial publication.

```typescript
interface FinalizationEvidenceV1 {
	localHeads: readonly { inputId: string; expectedVersion: string; verificationEvidenceDigest: string }[];
	ownerFences: readonly {
		inputId: string;
		ownerId: string;
		observedVersion: string;
		authorizationRevision: string;
		status: "current" | "historical_exact";
		observedAt: string;
		verifierContractDigest: string;
		verificationEvidenceDigest: string;
	}[];
}

interface ObservationIdentityV1 {
	operationId: string;
	observationId: string;
	recoveryFencingToken?: string;
}

type OperationObservation = ObservationIdentityV1 &
	(
		| { kind: "execution_started" }
		| { kind: "execution_completed"; resultDigest: string; candidates: readonly OutputCandidateV1[]; finalizationEvidence: FinalizationEvidenceV1 }
		| { kind: "execution_failed_before_effect"; reasonCode: string }
		| { kind: "prepare_dispatch"; effectBinding: FacadeEffectBindingV1; finalizationEvidence: FinalizationEvidenceV1 }
		| { kind: "transport_observed"; effectBinding: FacadeEffectBindingV1; transportClass: "response_lost" | "timeout" | "unavailable" | "response_received" }
		| { kind: "authority_status_observed"; effectBinding: FacadeEffectBindingV1; status: CaseOperationStatusV1 }
		| { kind: "projection_sync_proved"; effectBinding: FacadeEffectBindingV1; proof: ProjectionInclusionProofV1 }
		| { kind: "recovery_proof_expired"; effectBinding: FacadeEffectBindingV1 }
	);
```

`prepare_dispatch` atomically revalidates its fences, commits `may_have_dispatched`, and returns `DispatchPermit` only after the Journal has definitively resolved the commit. The dispatcher is prohibited from remote I/O without that exact permit. A lost marker acknowledgment returns no permit until lookup resolves it; meanwhile recovery conservatively treats the effect as possibly dispatchable/dispatched.

For `execution_completed`, candidate `claimId` values must be unique and belong to the admitted plan. The Journal validates each payload against that claim's `validationContractRef`/`schemaRef`, checks its canonical digest, and requires exactly one candidate for every claim in an atomic group before that group can publish. `FinalizationEvidenceV1` must contain exactly one evidence item for every required `inputId` of the groups being published or the effect being prepared, with no duplicate, missing, or extra IDs; each item is checked against the admitted reference, use, expected version, and verifier contract. Failure returns a closed `rejected` decision and publishes no member of the affected group.

For `authority_status_observed`, both `terminal` and `protected_terminal` validate the exact archived `FacadeEffectBindingV1`, disposition-specific shape, resulting proposal-ledger revision, and the admitted expected-revision invariants, then enter the same monotonic authority/synchronization/reservation transition. `protected_terminal` persists only the minimum proof in protected fields and returns no published output ID. `gone` prevents identity reuse but is not `applied` or no-effect proof: without an already stored terminal outcome it advances local knowledge only according to the qualified proof-retention rule and retains reservations; after a stored terminal outcome it cannot regress or erase that outcome.

Progress and partial model/tool streams are deliberately absent. They may update ephemeral UI telemetry, never durable output or effect state.

## 6. Atomic transition groups

The Adapter must provide these seven semantic transaction aggregates:

1. **Workspace bind/rebind:** install one binding/head set without mixing actor, authority, branch, catalog, or activation.
2. **Operation admission:** Operation Intent, exact input bindings, Output Claims, Effect Intent, reservations, archive pins, and dispatch eligibility all-or-nothing.
3. **Local output publication:** revalidate current fences and target CAS, then commit the whole output group, local receipt, current target heads, derivation edges, and claim fulfillment all-or-nothing.
4. **Effect dispatch permission:** revalidate fence dependencies, commit `may_have_dispatched`, and return one exact `DispatchPermit` only after definitive commit; never record definitely-sent or no-send from transport uncertainty.
5. **Authority outcome merge:** validate the complete `FacadeEffectBindingV1`, dispatch-permit evidence, and either one full terminal receipt or one protected terminal recovery proof from `CaseOperationStatusV1`; install its resulting proposal-ledger head/version and dirty the proposal-status block head, update effect state, release `satisfied_without_change`/terminal no-effect reservations or retain `applied` synchronization reservations, enqueue follow-up work, and install any required receipt-authority partition quarantine atomically. A protected proof writes only protected journal fields and never creates a user-visible output.
6. **Projection inclusion merge:** bind the exact receipt/effect/membership to one current Projection whose Case Revision, Proposal Ledger Revision, observation evidence digest, Resource Index digest, and Proposal Status digest all match the proof; mark `projection_proved`, update Case/proposal dependencies, and release synchronization reservations atomically.
7. **Recovery/index/archive maintenance:** lease/claim recovery work without transferring authority; flip complete index generations and perform archive/operation GC only after mark/recheck/sweep proves no live reference or unresolved effect.

These aggregates are the minimum behavior. Physical schemas may combine or split tables but may not weaken transaction boundaries.

## 7. Logical records and constraints

The relational model needs at least these logical records:

- `workspace_binding` and durable Workspace heads;
- immutable `operation_intent` keyed by Workspace/operation and unique transition identity;
- normalized `operation_input` dependency/version/fence rows;
- `output_claim`, `published_output`, and immutable `derivation_edge` rows;
- immutable `effect_intent`, `fence_dependency`, and `may_effect_domain` rows;
- current `effect_state` plus append-only `operation_observation` rows;
- authoritative receipt/proof documents by exact effect binding and receipt/proof digest;
- current `effect_reservation` rows;
- durable receipt-authority/Capability/target partition quarantine and audit rows;
- digest-addressed `contract_archive` and operation/archive references;
- rebuildable dependency-index generations; and
- recovery work claims/leases.

Required constraints include:

- one immutable digest per operation, transition, effect, and observation identity;
- one fulfillment or terminal no-output outcome per Output Claim;
- at most one target-owned terminal receipt per Effect Intent;
- `applied`, `satisfied_without_change`, and terminal no-effect receipt shapes enforced at write time;
- no reservation release inconsistent with receipt/synchronization axes;
- no dispatch eligibility without committed effect, domain, lookup, and archive rows;
- archive deletion restricted while referenced;
- derivation edges committed with their output group; and
- active dependency-index generation references a fully validated source revision.

Admission and `prepare_dispatch` reject an active matching quarantine before creating a new remote permit. Recovery surfaces the partition in `WorkspaceRecovery`, retains affected unresolved operations for audit, and continues to schedule disjoint partitions.

Append-only observations support audit and rebuild, but current constrained facts remain first-class. Reconstructing every current state by replaying a universal event stream is intentionally not required.

## 8. Crash and acknowledgment behavior

The journal distinguishes three local transaction results:

- `committed`: authoritative lookup confirms the transition/digest exists;
- `not_committed`: authoritative lookup confirms absence and the exact transition may be attempted;
- `ack_unknown`: neither is yet proved; retry by a new identity or proceed as absent is forbidden.

Every transition has a stable identity and digest so acknowledgment loss is resolved by lookup. Same identity/different digest is always an integrity incident.

| Crash window | Required recovery behavior |
|---|---|
| before admission commit | no operation or reservation is visible |
| admission commit acknowledgment lost | look up transition identity/digest; do not duplicate |
| after admission, before execution | claim the admitted operation after restart |
| during read/model execution | abandon partial stream; rerun only under recipe freshness rules |
| after execution, before local publish | recovered completion must pass current fences again |
| during output transaction | all output/edges/receipt publish or none |
| after output commit, before response | return/reconstruct the committed local receipt |
| before dispatch-permit transition commit | no remote I/O is permitted |
| permit transition acknowledgment lost | return no permit, look up the transition, and conservatively reserve the effect until known |
| marker authoritatively absent | no send occurred through the qualified dispatcher; revalidate fences before a later permit or local cancellation |
| after permit commit, before send | recovery queries/replays only under the original same-identity contract because another process may have received the permit |
| during remote send/timeout | retain Effect Reservation; transport outcome is not semantic outcome |
| remote no-effect committed, local crash | recover matching terminal receipt and release atomically |
| remote applied, local crash before response | recover applied receipt; retain sync reservation |
| remote `applied`, outbox pending | show `accepted_but_unsynchronized`; disjoint work continues |
| OpenCTI materialized, proof not stored | rebuild proof from authority/outbox and fresh Projection, not generic search |
| proof commit acknowledgment lost | look up proof transition; do not release twice |
| dependency index rebuild crash | retain old active generation; discard/restart inactive generation |
| permission revoked during recovery | purge/hide protected business content; allow minimal receipt lookup only |
| contract archive missing/corrupt | retain suspension and raise integrity incident; never decode with current schema |

## 9. Recovery claims and leases

**Problem solved:** multiple processes may resume the same Workspace after failover.

**Inputs:** worker identity, operation/effect selection, lease deadline, and journal source revision.

**Output:** a bounded `RecoveryBatch` of immutable intents plus an exclusive execution lease.

**Boundary:** leases coordinate local workers only. Lease expiry does not prove a remote effect failed and does not release Effect Reservations. A recovery item carries its fencing token into every observation; a stale claimant may submit an idempotent already-known observation but cannot acquire a new dispatch permit or replace a current recovery claim.

**Failure behavior:** a late worker may submit observations because observations are identity/digest idempotent, but it cannot overwrite a stronger state. Recovery prioritizes possible remote effects, accepted-unsynchronized effects, and authorization cleanup before abandonable reads/models.

## 10. PostgreSQL production Adapter

Qualification must prove:

- transaction isolation/locking prevents lost head, Output Claim, and reservation updates;
- unique and check constraints enforce identity/digest and receipt shapes;
- acknowledged admission/effect/receipt/outbox commits survive the declared crash/failover envelope;
- the configuration does not acknowledge commits that may be lost for strict effects;
- worker claims use fencing that prevents concurrent non-idempotent local execution;
- backups/restores preserve identity, archive, receipt, and reservation integrity; and
- schema migrations preserve unfinished old operations and their decoder/archive pins.

Synchronous commit requirements apply to transactions that make strict remote dispatch eligible and to authoritative local knowledge/reservations. A deployment may choose different durability for disposable telemetry, but telemetry must not share a transaction whose apparent success is used for effect safety.

## 11. In-memory conformance Adapter

The in-memory Adapter is not a simplified fake. It must implement the same observable constraints and transitions using:

- atomic copy-on-write state replacement;
- a serializable durable restart image;
- injected clock and ID sources;
- failpoints before and after each transaction commit/ack boundary;
- duplicate, lost, and out-of-order observation injection;
- configurable authorization and authority drift; and
- rebuildable dependency-index generations.

Named failpoints shared by the differential suite are `before_commit`, `after_commit_before_ack`, `after_ack`, and `before_restart` for every semantic transition. Facade simulation additionally exposes authority-commit response loss, duplicate outbox delivery, OpenCTI materialization lag/failure, and Projection-proof commit acknowledgment loss. Deterministic trace fixtures inject clock, IDs, canonicalization vectors, worker schedules, receipt order, and failpoint occurrence.

Tests may inspect diagnostic snapshots, but production callers use only `DurableOperationJournal`.

## 12. Retention and garbage collection

**Problem solved:** deletion of evidence or decoders can make an unresolved effect unsafe or an accepted output unauditable.

**Inputs:** output retention class, facade proof horizon, legal/policy retention, archive reference graph, unresolved-effect state, and dependency-index source revision.

**Output:** a governed mark/recheck/sweep decision.

**Boundary:** rendered context and reconstructable remote bodies may expire independently. Stable operation identity/digest, unresolved Effect Intent, possible domains, authoritative receipt/proof, derivation edges for retained outputs, and referenced contract archives obey the longest relevant safety/audit horizon.

**Failure behavior:** unresolved, indeterminate, accepted-unsynchronized, referenced, or recovery-claimed records are not collected. Recheck under a current transaction immediately before sweep. A failed deletion leaves records intact.

Closing a Workspace cancels abandonable work but never deletes or releases a possibly dispatched effect, creates a compensating write, or turns unknown into failure.

## 13. Dependency-scoped availability

Admission checks active reservations using exact typed dependency equality. When one remote R1 outcome is unknown:

- fresh Case Projection reads and writes sharing that authority Case head wait;
- the matching membership and proposal-status chain waits;
- outputs derived from those references are suspended or challenged according to publication class;
- disjoint Working Set entries, unrelated I&E Resources, another Case/authority, and tasks whose recipes do not require the affected head continue;
- Session UI may report the scoped pending/unknown state without injecting unproved outcome as Case truth.

Three registered recovery recipes may cross their own matching reservation: identity-scoped facade status lookup, outbox reconciliation observation, and receipt-bound Projection-sync read. They must carry the same `FacadeEffectBindingV1` and recovery fencing token, may consume only the reserved effect's proof inputs, and cannot create a new business effect or satisfy unrelated reads. Without this exception, `applied` would deadlock waiting for the Projection proof needed to release its own Case-head reservation.

If dependency data is incomplete, widen to the recipe-declared authority partition, never automatically to the whole Workspace. Missing Dependency Index data uses journal scanning or conservative partition reservation; it never means safe.

## 14. Conformance

The shared Adapter suite must prove at least:

1. atomic admission and no partial dispatcher eligibility;
2. stable transition lookup after lost commit acknowledgment;
3. same identity/different digest quarantine;
4. all-or-nothing output group, derivation, receipt, and head publication;
5. partial streams create no durable output;
6. no remote I/O occurs without a definitively committed `DispatchPermit` for the exact binding;
7. possible dispatch retains exact Effect Domains;
8. `applied` retains reservations until Projection inclusion proof, while `satisfied_without_change` never enters the synchronization wait;
9. terminal no-effect releases reservations atomically;
10. duplicate/out-of-order observations never regress state;
11. contradictory terminal receipts or terminal-without-permit evidence durably quarantine the shared receipt-authority/Capability/target partition and survive restart;
12. recovery lease expiry is not remote no-effect proof;
13. index rebuild exposes old or new complete generation only;
14. missing index causes conservative journal-based behavior;
15. archive references prevent deletion and missing archive fails closed;
16. unresolved/indeterminate effects survive close, restart, retention scans, and GC;
17. in-memory restart/failpoint outcomes match production semantics;
18. unsafe asynchronous commit/failover configuration cannot qualify strict effect dispatch;
19. overlapping dependencies wait while disjoint dependencies proceed;
20. registered receipt/outbox/Projection recovery for one effect crosses only its own reservation and cannot create a new business effect;
21. after actor revocation, full terminal receipt and protected terminal proof drive identical authority/synchronization/reservation state, while the protected path publishes no user-visible fields and survives restart; and
22. Projection inclusion releases synchronization reservations only when the receipt-result Case/proposal-ledger revisions, observation evidence, Resource Index digest, and Proposal Status digest all match one complete proof.

The conformance runner executes the same deterministic trace against PostgreSQL and in-memory Adapters and compares only Interface decisions, `resume` recovery image, runnable/recovery work, published outputs, and active reservations. It does not compare table or object layout.

The detailed fault matrix and persistence research are in [Workspace operation journal atomicity and recovery](../research/workspace-operation-journal-atomicity-recovery.md).
