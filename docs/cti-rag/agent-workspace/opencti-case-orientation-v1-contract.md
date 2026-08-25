# `opencti-case-orientation/v1` Contract

Status: Delivered read-only behavioral baseline; its actor-scoped data and safety rules remain normative when referenced by the current lifecycle contract.

This document was normative for the first executable delivery cycle. It defines the retained small actor-scoped orientation read that stock OpenCTI can support after deployment qualification. The sole current-cycle lifecycle owner is [Pi-native Agent Workspace Lifecycle v1](pi-native-workspace-lifecycle-v1-contract.md), which incorporates this document's data, disclosure, and accepted safety baseline without retaining its staging-Harness mechanism. This document does not define OpenCTI GraphQL DTOs, a Case Management Projection, a Case write basis, or model-visible tool decomposition.

**Lifecycle mechanism update:** the disclosure, freshness, recovery, dependency-isolation, and terminal guarantees in this contract remain the accepted Slice 0b behavioral baseline. Its delivered per-`WorkspaceTurn` staging Harness, four-entry caller-Session completion group, standalone stale/protected marker mechanism, and public `orientationDependencies` field are transition mechanisms, not the next implementation target. The accepted [Pi-native Agent Workspace Lifecycle v1](pi-native-workspace-lifecycle-v1-contract.md), [Task Context Understanding v1](task-context-understanding-v1-contract.md), and [ADR 0012](../adr/0012-use-pi-harness-as-workspace-execution-spine.md) own their incremental replacement. This note does not retroactively claim that either new acceptance catalog has passed.

## 1. Decision

The first usable Workspace opens directly from a qualified OpenCTI read Adapter. The Adapter converts current actor-visible OpenCTI Case facts into `opencti-case-orientation/v1`; it does not infer the missing business semantics of the later composed `opencti-case-projection/v1`.

**Problem solved:** requiring the full Case Management overlay before any investigation makes the first read-only product depend on the later write platform.

**Inputs:** one OpenCTI deployment, investigating actor credential or verified impersonation, one Case identity, a fixed orientation selection, and a qualified traversal contract.

**Output:** one complete actor-scoped Orientation containing Case identity plus selected visible work and neutral object-membership references.

**Boundary:** the output says what the qualified read observed for this actor. It does not state the Case's formal purpose, mandate, scope, Human Direction, accepted findings, evidence roles, proposal status, or write capabilities. It contains no `CaseRevision` and is never a conditional-write basis.

**Failure behavior:** a missing root, authorization loss, incomplete selected traversal, mixed observation, unsafe visibility distinction, schema mismatch, or failed end fence publishes no new Orientation. The last body is not silently reused as current.

## 2. Closed snapshot

```typescript
type OrientationPresence<T> =
	| { kind: "populated"; value: T }
	| { kind: "empty"; selectedScopeDigest: string }
	| { kind: "not_selected"; selectionDigest: string }
	| { kind: "unavailable"; reasonCode: OrientationFailureCode; retryable: boolean };

interface OpenCtiObservedVersionV1 {
	modified?: string;
	updatedAt?: string;
	contentDigest: string;
}

interface OpenCtiCaseIdentityV1 {
	internalId: string;
	standardId?: string;
	entityType: "Case-Incident" | "Case-Rfi" | "Case-Rft";
	displayName: string;
	sourceStatus?: { id: string; name: string };
	createdAt?: string;
	observedVersion: OpenCtiObservedVersionV1;
}

interface OpenCtiVisibleWorkV1 {
	taskRef: string;
	name: string;
	sourceStatus?: { id: string; name: string };
	dueAt?: string;
	assigneeRefs: readonly string[];
	observedVersion: OpenCtiObservedVersionV1;
}

interface OpenCtiVisibleObjectMembershipV1 {
	objectRef: string;
	standardId?: string;
	entityType: string;
	displayLabel: string;
	membership: "visible_case_object_reference";
	observedVersion: OpenCtiObservedVersionV1;
}

interface OrientationBlock<T> {
	presence: OrientationPresence<T>;
	semanticDigest: string;
}

interface OpenCtiOrientationSourceV1 {
	instanceId: string;
	adapterArtifactDigest: string;
	targetFingerprint: string;
	schemaDigest: string;
	qualificationId: string;
	observationStartedAt: string;
	observationFinishedAt: string;
	materialization: "bounded_double_observation";
	comparisonDigest: string;
}

interface OpenCtiCaseOrientationV1 {
	protocol: "opencti-case-orientation/v1";
	schemaVersion: "opencti-case-orientation-v1";
	caseRef: string;
	actorRef: string;
	usePurpose: "investigation_orientation";
	selectionDigest: string;
	source: OpenCtiOrientationSourceV1;
	blocks: {
		case_identity: OrientationBlock<OpenCtiCaseIdentityV1>;
		visible_work: OrientationBlock<readonly OpenCtiVisibleWorkV1[]>;
		visible_object_membership: OrientationBlock<readonly OpenCtiVisibleObjectMembershipV1[]>;
	};
	semanticDigest: string;
}
```

Every JSON object is closed. Generated JSON Schema must reject unknown members, unknown discriminants, duplicate JSON names, invalid Unicode, non-finite numbers, and unsafe integer representations before canonical hashing.

### Why these three blocks

- `case_identity` answers which OpenCTI Case the user opened. OpenCTI-native status is preserved as source vocabulary, not normalized into a formal Case lifecycle or mandate.
- `visible_work` exposes the current actor-visible Tasks needed to orient investigation. It does not promote a Task into Case Management's complete work model.
- `visible_object_membership` exposes neutral Case containment references that can seed later I&E retrieval. Membership does not mean evidence, support, contradiction, acceptance, or truth.

Notes, Opinions, labels, semantic relationships, history, proposal state, and arbitrary graph neighborhoods are deliberately outside this contract. They may be retrieved later as versioned source material, but cannot be reclassified as formal direction or accepted Case state by this Adapter.

## 3. Actor-scoped completeness

**Problem solved:** OpenCTI container access does not authorize every contained item, and paginated queries do not provide a native multi-collection snapshot.

**Inputs:** the actor credential, exact selection, exhaustive deployment-qualified root/Task/object traversals, item-level marking and Authorized Members enforcement, page evidence, and start/end probes.

**Output:** each selected block is `populated`, actor-view `empty`, or `unavailable`; an intentionally excluded block is `not_selected` only when permitted by a different compiled selection.

**Boundary:** complete means complete for the current actor, this selection, and the qualified query paths. It never means the global Case contains no hidden material. The Adapter must not reveal hidden item count, identifier, type, marking, topology, or whether non-return means deletion rather than lost visibility.

**Failure behavior:** partial pagination, a page limit, duplicate identity with inconsistent content, unresolved endpoint authorization, actor drift, or inability to prove traversal completion makes the entire affected block `unavailable`. No visible subset is published as if complete.

`case_identity` must be `populated`. Both collection blocks may be `populated`, `empty`, or `unavailable`. The Orientation is usable when identity is populated and at least one selected collection is complete; a Workspace operation that requires an unavailable collection remains unavailable. A totally unavailable collection set returns `orientation_not_usable` rather than an identity-only prompt that implies investigation context exists.

## 4. Observation and digest rules

**Problem solved:** OpenCTI exposes timestamps, cursors, and object IDs but no aggregate Case revision or snapshot token.

**Inputs:** two complete actor-authorized passes, normalized source fields, sorted stable identities, per-item observed versions, traversal evidence, and equal start/end actor/root probes.

**Output:** one `comparisonDigest` proving that the two complete observations were semantically equal within the bounded read, block semantic digests, and an Orientation semantic digest.

**Boundary:** these digests are equality evidence for observed content. They are not `CaseRevision`, an authorization lease, an as-of reconstruction token, or a writer precondition. A cursor is continuity evidence only.

**Failure behavior:** different pass digests, authorization or visibility change, cursor gap, root version drift, or exhausted retry budget returns `observation_drift` or the narrower safe failure. The Adapter publishes neither pass.

Block `semanticDigest` is SHA-256 over JCS of `{ blockKey, normalizedPresence }`. Populated collection values are sorted by stable source reference before hashing. Orientation `semanticDigest` covers protocol, schema, instance, actor, purpose, selection, Case reference, and the ordered three block digests. Observation times and Adapter deployment identity remain separate evidence and do not create semantic drift.

## 5. Read protocol

1. Bind the actor, OpenCTI instance, Case reference, selected contract, Adapter artifact, and deployment qualification.
2. Read the Case root under the actor and validate the root's item-level access.
3. Traverse selected Tasks through the qualified exhaustive top-level path; do not infer completeness from the nested Case field.
4. Traverse Case `object` membership exhaustively and authorize every returned object independently.
5. Normalize only contract fields, de-duplicate by resolved source identity, and stage outside the active Orientation.
6. Repeat root, authorization-sensitive probes, and each complete selected traversal.
7. Require equal normalized pass digests and continuous traversal evidence.
8. Validate the closed schema and digests, then atomically replace the active Orientation or publish nothing.

Events and notifications only mark the Orientation dirty. A lost, expired, filtered, or reordered event does not patch current state; the first cycle performs a full Orientation reopen. This intentionally defers a closed delta contract until production evidence shows full reopen is inadequate.

## 6. Prohibited use as write basis

No field, timestamp, cursor, version tuple, content digest, block digest, or Orientation digest may populate:

- `CaseRevision` or expected revision;
- a Case Management Capability Grant;
- a write authorization or approval;
- an idempotency receipt or effect status;
- `ResourceUsePermitV1`; or
- a claim that a later OpenCTI mutation was based on unchanged Case semantics.

Any recipe declaring a remote Case effect and an Orientation dependency fails compilation with `orientation_cannot_authorize_write`. The later composed Profile and strict-R1 contracts remain the only accepted write-enabled target architecture.

## 7. Failure codes

```typescript
type OrientationFailureCode =
	| "orientation_contract_not_served"
	| "orientation_not_usable"
	| "case_root_not_found_or_not_visible"
	| "authorization_or_visibility_changed"
	| "incomplete_task_traversal"
	| "incomplete_object_traversal"
	| "observation_drift"
	| "cursor_continuity_lost"
	| "schema_or_mapping_mismatch"
	| "digest_mismatch"
	| "transport_timeout"
	| "materialization_budget_exhausted";
```

Errors expose only actor-safe Case and qualifier references. `case_root_not_found_or_not_visible` deliberately does not distinguish deletion from visibility loss.

## 8. Deployment qualification

Activation binds a pinned OpenCTI release and deployment, introspected schema digest, exact GraphQL selections, exhaustive Task and object traversal queries, pagination limits, actor-authentication or impersonation behavior, marking and Authorized Members behavior, Case-kind/status mapping, normalization rules, and start/end probe behavior.

The production Adapter and an in-memory Adapter run the same contract fixtures. Qualification does not claim native snapshot, authorization revision, historical replay, or write coordination. A schema or deployment fingerprint change disables this Profile until requalified.

## 9. Slice 0b lifecycle contract

Slice 0b completes the read-only Orientation lifecycle. It changes neither the Pi agent package nor the public application flow: callers still use only `CaseWorkspaceModule.open`, `CaseWorkspace.prompt`, `WorkspaceTurn`, and `CaseWorkspace.close`. Refresh, reconciliation, invalidation status, staging Session management, and transport control remain private to this Module.

### 9.1 Public Interface and stable operation identity

```typescript
interface CaseWorkspaceModule {
	open(
		input: {
			caseRef: string;
			actor: TrustedActorBinding;
			sessionRef: WorkspaceSessionRef;
		},
		options?: { signal?: AbortSignal },
	): Promise<CaseWorkspace>;
}

interface CaseWorkspace {
	prompt(input: {
		task: string;
		images?: readonly ImageContent[];
		orientationDependencies?: readonly (
			| "case_identity"
			| "visible_work"
			| "visible_object_membership"
		)[];
	}): WorkspaceTurn;
	close(): Promise<void>;
}

interface WorkspaceTurn extends AsyncIterable<WorkspaceEvent> {
	readonly id: string;
	readonly result: Promise<WorkspaceTurnResult>;
	cancel(): void;
}

interface WorkspaceEventEnvelope {
	operationId: string;
	turnId: string;
	eventSequence: number;
}

type WorkspaceEvent = WorkspaceEventEnvelope &
	(
		| { type: "turn_started" }
		| { type: "context_bound"; protocol: "opencti-case-orientation/v1"; semanticDigest: string }
		| { type: "model_started" }
		| { type: "model_text_delta"; delta: string }
		| { type: "turn_completed" }
		| { type: "turn_cancelled" }
		| { type: "turn_failed"; failure: WorkspaceFailure }
		| { type: "turn_discarded"; reason: TurnDiscardReason }
	);

type WorkspaceTurnResult = { operationId: string; turnId: string } &
	(
		| { status: "completed"; message: AssistantMessage }
		| { status: "cancelled" }
		| { status: "failed"; failure: WorkspaceFailure }
		| { status: "discarded"; reason: TurnDiscardReason }
	);
```

`sessionRef` is required because recovery, stale-prose exclusion, and duplicate-terminal containment require one caller-owned Session identity. The Orientation body remains reconstructable and is not ordinary Session authority. Every `module.open` performs a complete double observation; no reopen trusts a cached Orientation body.

Each `prompt` allocates one opaque, stable `operationId` and one opaque, stable `turnId`; `WorkspaceTurn.id` equals `turnId`. These identities do not change when cancellation is requested or a provider ignores it. Every public event for that Turn carries the same identities and a strictly increasing `eventSequence` starting at one. A provider callback belongs to the Turn only through the trusted closure that captured these identities; provider-supplied IDs do not establish ownership.

The delivered Slice 0b event union has exactly four terminal variants: `turn_completed`, `turn_cancelled`, `turn_failed`, and `turn_discarded`. Each is an event with the common identity and sequence fields. `WorkspaceTurnResult.status` is respectively `completed`, `cancelled`, `failed`, or `discarded`. A serialized settle-once reducer emits at most one terminal event and resolves `result` exactly once. An unexpected internal exception becomes one actor-safe `failed` result; `result` never rejects and never remains pending merely because transport ignores cancellation. The target lifecycle adds a fifth, equally settle-once `turn_clarification_required` variant through [Task Context Understanding v1](task-context-understanding-v1-contract.md); that extension is not part of delivered Slice 0b evidence.

Explicit caller cancellation settles `cancelled`. A newer Turn supersedes any older non-terminal Turn in the same Workspace and settles the older Turn `discarded` with reason `turn_superseded`. `close` settles a non-terminal Turn `discarded` with reason `workspace_closed`, aborts cooperative work, unregisters hooks, and returns without awaiting a provider that ignores cancellation. A valid completion that wins the serialized fence settles `completed`; all other safe failures settle `failed` or `discarded` according to the closed reason below.

```typescript
type TurnDiscardReason =
	| "turn_superseded"
	| "workspace_closed"
	| "orientation_binding_changed"
	| "orientation_invalidated"
	| "authorization_changed"
	| "dependency_version_changed"
	| "session_binding_changed"
	| "recovery_provenance_untrusted";

type LateResponseDiscardReason =
	| "operation_cancelled"
	| "turn_superseded"
	| "workspace_closed"
	| "terminal_already_settled"
	| "orientation_binding_changed"
	| "target_generation_changed"
	| "orientation_invalidated"
	| "authorization_changed"
	| "dependency_version_changed"
	| "session_binding_changed";
```

The public terminal failure/discard contains only its safe code, retryability when applicable, and operation/Turn identities. A late provider partial, success, error, or duplicate terminal after local settlement emits no further `WorkspaceEvent`, changes no result, writes no Session message, and publishes no Artifact. It may append one actor-safe operational audit marker containing the operation/Turn identities, callback kind, discard reason, and local time; it contains no response payload, body-derived digest, hidden identifier, count, type, topology, or prior Orientation body.

### 9.2 Orientation Binding and response fence

An **Orientation Binding** is the exact current-read identity:

```typescript
interface OrientationBindingV1 {
	caseRef: string;
	actorRef: string;
	credentialScopeDigest: string;
	usePurpose: "investigation_orientation";
	selectionDigest: string;
	instanceId: string;
	adapterArtifactDigest: string;
	qualificationId: string;
	schemaDigest: string;
	targetFingerprint: string;
}
```

`credentialScopeDigest` is a non-reversible digest of the trusted credential/tenant/authorization scope, not a credential. `targetGeneration` is a monotonically increasing local fence for one active Orientation output slot. It is not part of `OrientationBindingV1`, an OpenCTI revision, a Session generation, or a Workspace-wide epoch. Another Case, actor partition, or dependency-disjoint operation has a different output slot and is not invalidated by this counter.

At operation admission, the Module captures the Orientation Binding, target generation, Turn and operation identities, caller Session binding/head, active invalidation sequence, and every model-visible dependency version. `orientationDependencies` is the closed set of Orientation blocks the Turn may render and read; omission selects all three blocks, while an empty set is unusable. The Module, not the model, turns that declaration into the rendered block set, the eligible historical chains, and the terminal dependency receipt. Historical prose enters the request only when all dependencies in its receipt are a subset of this Turn's declaration, so the new response cannot silently acquire a dependency that its receipt omits.

A partial callback is display-eligible only while this capture remains current. Before any completed response can enter the caller Session, current model path, Workspace Artifact, or dependent output, one local completion claim compares every captured value with current state and requires that the Workspace is open, the Turn is still active, no cancellation or supersession won, and no terminal was settled. The winning claim is followed by one caller-Session `appendBatchIfLeaf(expectedHead, entries)` containing `span_open`, the complete user message, the complete assistant message, and the signed receipt. The Session storage implementation linearizes the head comparison and the whole logical append group within that storage instance; a conflict appends none. The receipt is physically last in append-only storage, so a crash prefix is dirty rather than successful. This is not a cross-process file lock, distributed transaction, or durable effect Journal. A mismatch discards the whole candidate; unchanged text or a successful transport status never overrides the fence.

A newer refresh claim owns the Orientation output slot even if it later fails. An older late success cannot replace it. Two refreshes completing in reverse order therefore install at most the current generation, and a failed newer read followed by an older success leaves no old publication. Drift affects only outputs whose declared inputs intersect the changed Orientation binding/block/dependency; it never creates a global Workspace freeze.

### 9.3 Private staging Session and caller Session qualification

Each Turn runs Pi in a CTI-private staging Session and Harness. The staging model input is built from the current Orientation plus a mechanically qualified projection of the caller Session. Partial provider state can exist only in staging. The caller Session receives complete user and assistant messages only after the completion fence succeeds; cancellation, failure, discard, close, or stale completion writes no such message and contributes nothing to later model context or Artifact creation.

The caller Session is append-only for Slice 0b. It records CTI operation/span markers and dependency receipts around committed messages. A closed span proves that both complete messages and one terminal dependency receipt belong to the same operation, Turn, Session binding, Orientation Binding, target generation, and exact rendered Orientation block versions. The receipt also authenticates the complete user/assistant message digests. An open, malformed, duplicated, or undecodable span is audit-only and never model-eligible. A terminal receipt closes at most one span; replaying or recovering the same receipt is idempotent and emits no public terminal event.

Receipt authenticity is supplied through a trusted `SessionReceiptAuthenticator` dependency port. The delivered testing implementation uses HMAC-SHA-256 with a caller-held secret and stable authenticator identity; neither the key nor a signing capability is stored in Session. A plain public hash, a signature from another key, a changed dependency/member/message digest, or an unknown authenticator fails provenance. This contract assumes the Module and authenticator configuration are in the trusted process boundary; it does not claim that arbitrary code holding the signing port is untrusted.

The model-entry projection includes a caller Session entry only when all of these are mechanically true:

1. it is inside one uniquely closed successful CTI span;
2. its dependency receipt is authentic, decodable, and belongs to the active Session binding;
3. every `authorize` dependency is currently authorized;
4. every `current` dependency matches the current Orientation Binding and version;
5. no stale/protected marker intersects its dependency chain; and
6. branch and compaction ancestry preserve the same receipt without alteration.

Every authenticated stale/protected marker records the exact affected Orientation dependency receipts. It excludes only intersecting completed spans whose terminal receipts occur earlier in the append-only Session order. It does not permanently deny the binding or dependency version: a new qualified span committed after the marker remains eligible, including after the same semantic binding is re-established. Consequently, an `A -> B -> A` sequence cannot revive the pre-marker A span, while dependency-disjoint history and a new post-marker A span remain eligible. Marker verification uses retained append-only Session evidence rather than only the currently selected branch path, so branch navigation cannot remove a marker and revive an earlier span.

Legacy messages, summaries, or compactions with absent or ambiguous CTI provenance fail closed for future model entry. Prompt text cannot override this exclusion. A compaction or branch entry may leave authentic CTI spans and stale/protected markers in its Session ancestry; those unchanged records retain their independently verified eligibility, while the summary itself remains excluded. If navigation or storage removes or alters a required receipt/marker, the affected prose loses eligibility. Branching or compaction cannot manufacture a dependency receipt, remove a stale/protected marker, or make an excluded entry current.

When ordinary revision drift invalidates an intersecting chain, its completed prose remains in authorized audit history but leaves the active model path. Dependency-disjoint completed prose remains eligible. Authorization revocation marks the intersecting history protected and excludes both source bodies and body-derived prose even when the append-only audit entries remain retained under a separate authorized audit policy. Resumption uses a clean active model path; it never edits old text in place or clears audit history to obtain safety.

A **Stale Capsule** may replace one or more excluded chains in model input. It says only that prior analysis is unusable and names an actor-safe category such as `orientation_changed`, `authorization_changed`, `incomplete_operation`, or `provenance_untrusted`. It is not a summary, evidence, authority, or a source of identifiers. An authorization capsule contains no Case/item ID, count, type, topology, body-derived statement, prior digest, or indication of whether an item was deleted rather than hidden.

### 9.4 Clean, dirty, and Full Orientation Reopen

Every `module.open` begins with a Full Orientation Reopen and then classifies caller Session evidence:

- **clean reopen:** all CTI spans are uniquely terminal and decodable. After the fresh double observation, only completed prose whose receipts still match the new Orientation Binding and dependency versions may continue on the active model path;
- **dirty reopen:** at least one open, malformed, or interrupted span exists from open, materialization, model streaming, cancellation, or terminal publication. The suspect span is isolated as audit-only; no user/assistant fragment in it is treated as a complete answer. Earlier independently closed matching spans may remain eligible;
- **full binding reopen:** revision drift, authorization change/revocation, credential-scope change, selection change, instance/Adapter/qualification/schema/target-fingerprint change, contract incompatibility, or unknown provenance creates a new Orientation binding/output slot and a clean active model path. Before a new completed span can commit, the Module persists authenticated dependency-scoped exclusion markers for prior intersecting spans that lack one. Prior intersecting prose becomes stale or protected and cannot satisfy current context or write eligibility even if a later reopen returns to the same binding and dependency digests.

A **Full Orientation Reopen** is a fresh bounded double observation and atomic replacement of one affected Orientation output slot. Each transport observation probes the actor-scoped Case root at the start and again after the final selected page; root content or authorization drift makes that observation unusable before the bounded second observation is considered. It never resumes an interrupted page, splices an old and new pass, treats an event as a patch, or restores a rendered Orientation body from Session. If completeness cannot be proved, it installs nothing and returns an actor-safe failure. The previous body is audit/reconstruction input only where still authorized; it is not silently reused as current.

After a crash during initial open/materialization, no Workspace is recovered from partial observation; a later `module.open` starts two new observations. After a crash during a Turn or terminal append, dirty reopen isolates the unclosed span and does not replay nondeterministic provider work. A recovered terminal marker may close audit evidence idempotently but does not recreate a public `WorkspaceTurn` or emit a second terminal event. Unknown/corrupt provenance fails closed without exposing the suspect content.

### 9.5 Live invalidation and safe points

Live invalidation enters through a private `OrientationInvalidationPort`; it is a dependency port, not a public `refresh`, `reconcile`, or `status` method. Its closed actor-safe reason categories are `case_change_hint`, `authorization_uncertain`, `authorization_revoked`, `cursor_continuity_lost`, `schema_changed`, `qualification_changed`, `target_changed`, and `unknown_change`. An invalidation supplies the affected Orientation Binding/output slot and a local receipt sequence. It is only a hint: no payload is applied as a delta and no event order proves current state.

Safe points are immediately before admitting a prompt and after a complete Turn settles. Remote Full Orientation Reopen occurs only at a safe point. The Harness `context` hook performs local projection and fence checks only; it performs no remote I/O. If invalidation arrives during a provider request, it marks only the intersecting Orientation dependency chain dirty, causes the response completion fence to discard a now-stale candidate, and schedules Full Orientation Reopen at the post-Turn safe point. Unrelated dependency chains remain usable.

Each reopen captures the highest local invalidation sequence it intends to cover. Success clears only covered reasons at or below that sequence. An invalidation arriving during the reopen remains dirty and causes another reopen at the current or next safe point; an older refresh can never clear it. Cancellation or close prevents publication. `close` aborts cooperative reopen/transport work but does not wait for an Adapter that ignores cancellation; its late completion is fenced and audited without publication.

### 9.6 Shared Adapter conformance fixtures

One closed fixture catalog drives both the package's in-memory Adapter and a transport-backed production-shaped Adapter. Tests instantiate the same fixture twice and exercise it only through `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn`. They do not inspect Adapter calls, private generation counters, staging Sessions, or internal reducer state.

The fixture grammar describes semantic observations rather than a GraphQL DTO: source identity and qualification; ordered first/second observation scripts; root outcome; collection page identity/order/cursor/continuity; item authorization outcome; optional delay/timeout/ignored-abort behavior; invalidation receipts; restart boundary; and the expected public Orientation, failure, Turn events/result, model-input disclosure, and reread count. Exact GraphQL selections and deployment DTOs remain behind the production Adapter and require separate primary-source qualification.

For equivalent fixtures both Adapters must produce identical public success/failure code, retryability, event order/count, terminal result, disclosure, Session/model eligibility, reopen behavior, and late-response behavior. Complete pagination must return the complete canonical block. Missing pages, unexplained page reorder, inconsistent duplicate identity/content, lost cursor continuity, page-to-page permission loss, item authorization change, double-observation drift, schema/target mismatch, timeout, ignored cancellation, or any partially read result whose completeness cannot be proved publishes no partial Orientation and leaks no staged item through messages, errors, events, capsules, or audit payloads. Equal duplicate pages may de-duplicate only when identity and normalized content agree.

### 9.7 Slice 0b executable acceptance catalog

The following IDs are normative executable cases. Their presence in this contract does not claim implementation.

#### Late and out-of-order isolation

- **OR0B-LR-01:** after caller cancellation settles, a provider partial callback emits no new Turn event and enters neither caller Session nor the next model context.
- **OR0B-LR-02:** after caller cancellation settles, provider success or error is audit-only; `result` remains `cancelled` and exactly one terminal event exists.
- **OR0B-LR-03:** starting a new Turn discards the older non-terminal Turn; late old partial/success/error cannot enter the new Turn's context or Artifact path.
- **OR0B-LR-04:** close returns without an uncooperative provider; every later callback is audit-only and no second terminal event appears.
- **OR0B-LR-05:** competing terminal attempts from provider success/error, caller cancellation, close, or supersession settle exactly once according to serialized local observation order. Success-then-cancel, error-then-cancel, cancel-then-late-success, and cancel-then-late-error never regress the settled result; duplicate provider terminal signals normalized below the Workspace seam cannot create another Workspace terminal event.
- **OR0B-LR-06:** Orientation, authorization, credential scope, Session binding, target generation, or declared dependency version drift before completion discards the whole candidate.
- **OR0B-LR-07:** a discarded late result cannot contaminate later model input or an Artifact, while a dependency-disjoint operation remains usable.
- **OR0B-LR-08:** every event carries stable operation/Turn IDs and strictly increasing sequence; every Turn resolves one of the four closed result statuses.
- **OR0B-LR-09:** reverse-order refresh completion installs only the current target generation; a failed newer refresh followed by an older late success installs neither old response.

#### Stale Session containment

- **OR0B-SS-01:** relevant revision drift removes intersecting completed prose from the next model request and inserts only an actor-safe Stale Capsule; returning through `A -> B -> A` never revives the pre-marker A prose.
- **OR0B-SS-02:** authorization revocation excludes old Orientation bodies and all dependent prose; its capsule contains no ID, count, type, topology, digest, or body-derived summary.
- **OR0B-SS-03:** a previous Turn with only a partial stream contributes no user/assistant message or summary to a later prompt.
- **OR0B-SS-04:** reopen with a legacy message or compaction lacking trusted dependency provenance excludes it mechanically rather than relying on an ignore instruction.
- **OR0B-SS-05:** stale/protected prose remains available only to an authorized audit view and can never become current evidence, Artifact input, or write basis.
- **OR0B-SS-06:** drift in one declared dependency excludes only its downstream Session chains; disjoint qualified prose remains model-eligible, and a new qualified span committed after the marker may use the re-established dependency version.
- **OR0B-SS-07:** branch and compaction preserve dependency receipts and stale/protected markers; navigating behind a retained marker cannot revive an earlier span, and missing or altered evidence fails closed.

#### Dirty and Full Orientation Reopen

- **OR0B-RO-01:** clean reopen performs two new observations and continues only closed prose whose receipt matches the reconstructed Orientation Binding.
- **OR0B-RO-02:** interrupted open, materialization, stream, cancellation, or terminal publication is dirty; its unclosed span is audit-only and never a complete answer.
- **OR0B-RO-03:** drift/revocation or instance, credential scope, selection, Adapter, qualification, schema, or target-fingerprint change creates a full binding reopen and clean active model path; credential, selection, or target `A -> B -> A` reversion cannot revive the first A span.
- **OR0B-RO-04:** restart with an interrupted response or stale completed callback emits no duplicate terminal event and never resumes/splices the old provider stream.
- **OR0B-RO-05:** missing/corrupt/unknown recovery provenance installs no current output and returns an actor-safe failure without suspect payload.
- **OR0B-RO-06:** invalidation arriving during reopen remains dirty after the older refresh and forces another complete reopen at a safe point.
- **OR0B-RO-07:** every reopen rereads both complete observations; no cached Orientation body or event patch satisfies current publication.
- **OR0B-RO-08:** close during reopen returns without an ignored cancellation response and fences all later read completion.

#### Adapter conformance

- **OR0B-AD-01:** both Adapters return the same canonical Orientation for complete multi-page traversal.
- **OR0B-AD-02:** a missing page or cursor discontinuity makes the affected block unavailable and never leaks the partial prefix.
- **OR0B-AD-03:** equal duplicate pages de-duplicate identically; an inconsistent duplicate fails the observation.
- **OR0B-AD-04:** an unexplained out-of-order page fails completeness in both Adapters.
- **OR0B-AD-05:** permission revocation between pages fails actor-safely and publishes no staged item.
- **OR0B-AD-06:** item authorization/marking change cannot be represented as omission or actor-view empty.
- **OR0B-AD-07:** root/authorization drift between the start and end probe of either observation, or unequal complete first/second observations, fails before publication.
- **OR0B-AD-08:** schema, Adapter artifact, qualification, or target fingerprint mismatch disables publication until requalified.
- **OR0B-AD-09:** transport timeout returns the same actor-safe retryable failure and no partial result from either Adapter.
- **OR0B-AD-10:** ignored abort/cancel is contained by the same response fence in both Adapters.
- **OR0B-AD-11:** partial data without proof of whole selected traversal yields no successful Orientation or provider call.
- **OR0B-AD-12:** reopen reconstructs by rereading both Adapter shapes; neither resumes cached page state.
- **OR0B-AD-13:** every shared fixture has identical public event count/order, terminal result, retryability, disclosure, and next-Turn model context across both Adapters.

#### Interface and scope

- **OR0B-IF-01:** the common public Interface remains `open/prompt/close`, `sessionRef` is required, `WorkspaceTurn.id` is stable, and no public refresh/reconcile/status method is introduced.
- **OR0B-IF-02:** invalidation and production transport remain dependency ports; tests prove behavior through the public Workspace seam.
- **OR0B-IF-03:** dirtying or failing one Orientation output slot does not freeze another Case/actor partition or a dependency-disjoint operation.

OR-27 is closed by OR0B-LR-06/LR-09; OR-28 by OR0B-SS-02/SS-05; OR-29 by OR0B-LR-07/IF-03; and OR-30 by OR0B-AD-01 through AD-13. OR-14 through OR-16 and OR-24 additionally require the applicable OR0B-RO/AD cases. OR-25 and OR-26 remain explicitly deferred because executable enforcement would introduce the frozen write compiler and remote-effect recipe platform. Their normative prohibition in section 6 remains active; deferral is not permission to use Orientation as a write basis.

## 10. Baseline behavioral acceptance

1. **OR-01:** an authorized Case with complete Tasks and object traversal publishes exactly one Orientation containing all three block slots.
2. **OR-02:** the model receives OpenCTI source status as source vocabulary, never a synthesized mandate or formal lifecycle.
3. **OR-03:** an empty visible Task result becomes actor-view `empty`, not a claim that no hidden Task exists.
4. **OR-04:** an empty visible object result becomes actor-view `empty`, not global Case emptiness.
5. **OR-05:** the same normalized actor-visible content produces the same block and Orientation semantic digests despite different observation times.
6. **OR-06:** changed content between the two passes publishes neither pass and returns `observation_drift` after bounded retries.
7. **OR-07:** permission revocation between pages clears staged bodies and publishes no Orientation.
8. **OR-08:** removal from Case Authorized Members returns the non-distinguishing root visibility failure and never exposes the prior body.
9. **OR-09:** a newly inaccessible marking on one object makes the selected object block unavailable; it does not silently omit the object.
10. **OR-10:** an inaccessible object never leaks count, ID, type, marking, or topology through payload, digest input, error, or log.
11. **OR-11:** a nested Case Task list is not accepted as complete unless the qualified deployment proves it exhaustive; the default Adapter uses the top-level pageable traversal.
12. **OR-12:** page failure or page-limit exhaustion makes the affected collection unavailable and does not publish a partial list.
13. **OR-13:** duplicate pages de-duplicate equal versions but inconsistent duplicate content fails the observation.
14. **OR-14:** a deleted-or-hidden notification only dirties the Orientation; it never installs a tombstone from the event.
15. **OR-15:** a missing, duplicated, or out-of-order event is recovered by full reopen and cannot override the authoritative read.
16. **OR-16:** an expired stream cursor causes full reopen, not delta application or Workspace-wide freeze.
17. **OR-17:** a complete `visible_work` block remains usable when object traversal is unavailable, while object-dependent operations are unavailable.
18. **OR-18:** a complete object block remains usable when Task traversal is unavailable, while Task-dependent operations are unavailable.
19. **OR-19:** identity plus two unavailable collection blocks returns `orientation_not_usable` before a provider request.
20. **OR-20:** an unknown Case kind or unmapped source status remains explicit source vocabulary or fails qualification; it is never guessed into Case Management semantics.
21. **OR-21:** object membership is rendered as a neutral visible reference and never as supporting evidence, contradiction, accepted fact, or semantic relationship.
22. **OR-22:** Notes and Opinions cannot enter Human Direction or Accepted State because those blocks do not exist in the contract.
23. **OR-23:** workbench and Draft content does not enter the Orientation as current main-knowledge state.
24. **OR-24:** a schema or target fingerprint change disables activation until qualification is rerun.
25. **OR-25:** an Orientation timestamp, cursor, object version, or digest supplied as `CaseRevision` is rejected mechanically.
26. **OR-26:** a remote-effect recipe depending on Orientation fails compilation with `orientation_cannot_authorize_write` before dispatch.
27. **OR-27:** a stale completed Orientation response cannot replace a newer active target generation.
28. **OR-28:** authorization loss prevents both current publication and future model use of a formerly historical Orientation body.
29. **OR-29:** failure of this Case's Orientation does not block disjoint I&E retrieval or another Case/actor authority partition.
30. **OR-30:** production and in-memory Adapters produce identical public results for every success, unavailable block, drift, revocation, and pagination fixture.

## 11. Research basis

This contract adopts the primary-source findings in [OpenCTI Case Read/Write Guarantees](../research/opencti-case-read-write-guarantees.md), [Projection Authorization, History, and Change Detection](../research/opencti-projection-authorization-history.md), and [Projection Profile Feasibility](../research/opencti-projection-profile-v1-feasibility.md). Where those notes recommend a larger composed Profile or direct mutation mode, this current-cycle contract deliberately selects the smaller read-only subset.
