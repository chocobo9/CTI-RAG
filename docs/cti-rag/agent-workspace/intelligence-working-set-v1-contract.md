# `intelligence-working-set/v1` Workspace Integration Contract

Status: **Historical independent Workspace-consumer design acceptance PASS** for the non-provider exact-resource, Working Set, render, and disclosure-admission design. Later cross-context coordination additionally accepted deterministic Workspace retrieval admission, distinct Workspace/I&E candidate authorities, and a Workspace application Adapter into Pi-owned Provider Dispatch. The new pre-Investigation Task Understanding contract supersedes this file's Task Context Plan/planning-save-point field mappings, which are now reference-only pending an IWS revision and reacceptance. Sections 6–8 retain the earlier provider-proof candidate for traceability only and are **reference-only/superseded**. Workspace consumer implementation and real-provider disclosure remain **NO-GO** under section 9; this is not a prototype claim.

Evidence Assembly amendment status: **Design Gate FAIL.** The target
[`workspace-evidence-assembly/v1`](evidence-assembly-v1-contract.md) reuses
`WorkingSetEntryV1`, `WorkingSetSelectionV1`,
`WorkingSetDerivationEdgeV1` and `WorkingSetLocalReceiptV1`; it does not create
another material-ref catalog. Task Result candidate material refs must resolve
only through those records and their Save Point basis. The required Task Result
Contribution and superseding consumer revision are not accepted or authorized.

## 1. Business problem and ownership

Workspace must let the model select useful actor-visible Case material without allowing model text to become an exact backend selector, authorization, durable state, or provider-disclosure proof. It must also survive timeout, duplicate completion, out-of-order tools, cancellation, crash, unknown commit acknowledgement, and concurrent Session writers without admitting a partial Working Set or automatically resending a possibly invoked model request.

This contract owns the Workspace side of the first exact-resource vertical:

- minting task-scoped opaque Resource Candidate References from current actor-visible Orientation membership after Task Context planning commits;
- admitting one closed Workspace Capability operation through a trusted recipe;
- consuming one authentic completed [`opencti-exact-resource-retrieval/v1`](../intelligence-evidence/opencti-exact-resource-retrieval-v1-contract.md) result;
- atomically committing source-ordered finalized Pi tool results and the reference-only Working Set state in one Pi save-point group; and
- supplying Workspace-owned binding, revalidation, render, and disclosure material through an application Adapter when a Pi-owned Provider Dispatch transaction discloses Working Set/I&E content.

I&E owns retrieval, Resource Capsule semantics, current Use Disposition, exact-capture identity, Ed25519 receipt, reusable bodies, corpus ranking, Declared Retrieval Coverage, and any I&E Retrieval Candidate Reference. Pi owns tool-result order, expected-leaf save-point/control transactions, the leased Session, run fencing, and the generic Provider Dispatch transaction and proof. Workspace owns Orientation-derived Resource Candidate minting, trusted identity binding, deterministic retrieval admission, capability admission, Working Set policy, I&E receipt verification, context rendering, disclosure admission, the application mapping into Pi, and public publication. Case Management receives no write.

### 1.1 Normative priority and synchronized owner boundary

This contract is the Workspace authority for exact-resource admission, Working Set state/render, disclosure policy, and the application material mapped into the generic lifecycle. [`pi-native-workspace-lifecycle/v1`](pi-native-workspace-lifecycle-v1-contract.md) is the sole authority for generic Provider Dispatch preparation, canonical artifact, control batch, permit/start, acknowledgement, lookup, and recovery. The provider-specific schemas and acceptance candidates retained in sections 6–8 do not override that owner and cannot be implemented as a second transaction.

The I&E owner remains authoritative for its own exact Source Capture, Resource Capsule, Retrieval Receipt, and replay-material retention. Its 365-day IER1 source-profile requirement is unchanged. That permission does not extend to User Task, Session history, Orientation, provider-neutral messages, tools, model/options, credentials, or a complete provider prompt. I&E core-package readiness is separate from Workspace consumer acceptance and does not bypass the consumer or provider gates in section 9.

### 1.2 Accepted cross-context retrieval protocol

Agent RAG is a vertical capability across I&E, Workspace, and Pi rather than a fourth bounded context. Each Module keeps schema and behavior ownership local, and shared acceptance reuses only scenario identifiers and cross-seam expectations.

Two candidate authorities are intentionally distinct:

- a Workspace Resource Candidate Reference is minted from current Orientation membership after planning commits and may be compiled by trusted Workspace code into an exact I&E request;
- an I&E Retrieval Candidate Reference is minted by a future bounded search, remains bound to its search request/Receipt, actor, purpose, Index Generation, and Ranking Profile, and may be proposed by the model only for deterministic Workspace admission.

The namespaces never alias, and neither candidate can be converted through an OpenCTI/internal/backend identifier. The fixed search-to-Working-Set sequence is model suggestion, Workspace admission, I&E exact materialization, Workspace Receipt/Capsule verification, then atomic Working Set CAS commit. Search cannot directly create a Capsule or Working Set entry.

Workspace compiles trusted Retrieval Scope and Budget from its own task/capability policy and evaluates a minimum-coverage policy without claiming actual coverage. I&E alone proves Declared Retrieval Coverage, Index Generation, Lag, and Omissions. There is no successful interrupted or backend-partial retrieval, and a score is meaningful only inside one query/request, Retrieval Receipt, Index Generation, and Ranking Profile. The future bounded-search contract remains unaccepted and unimplemented; these ownership invariants do not authorize it.

## 2. Target-neutral planning and resource selection

A Task Context Query Candidate is model-produced, target-neutral, and non-executable. It contains no Resource Candidate Reference, OpenCTI identifier, exact selector, credential, Adapter, request ID, or capture ID.

Only after the planning save point commits does Workspace derive a `ResourceCandidateCatalogV1` from the current actor-visible Orientation `visible_object_membership`. Each opaque reference is scoped to the exact Workspace, raw User Task, admitted Task Context, Orientation binding, membership semantic digest, and Context Generations. In a tool-enabled context, Workspace renders membership through this catalog: the model sees the opaque `resourceCandidateRef`, display-safe membership fields, and any separately admitted `queryCandidateRef`, while the underlying `objectRef`/`standardId` binding is omitted and remains trusted runtime state.

```typescript
interface ResourceCandidateCatalogV1 {
	protocol: "workspace-resource-candidate-catalog/v1";
	workspaceRef: string;
	taskRef: string;
	taskContextId: string;
	taskContextPlanDigest: string;
	orientationBindingDigest: string;
	orientationSemanticDigest: string;
	contextGenerationDigest: string;
	entries: readonly ResourceCandidateEntryV1[];
	catalogDigest: string;
}

interface ResourceCandidateEntryV1 {
	resourceCandidateRef: string;
	membershipSemanticDigest: string;
	entityType: string;
	displayLabel: string;
	entryDigest: string;
}

interface ExactResourceOperationChoiceV1 {
	resourceCandidateRef: string;
	queryCandidateRef?: string;
}

interface ResourceCandidateMembershipDigestBasisV1 {
	protocol: "workspace-resource-candidate-membership-basis/v1";
	orientationBindingDigest: string;
	orientationSemanticDigest: string;
	selectionDigest: string;
	membershipBlockSemanticDigest: string;
	membership: OpenCtiVisibleObjectMembershipV1;
}

interface ResourceCandidatePrivateBindingV1 {
	protocol: "workspace-resource-candidate-private-binding/v1";
	resourceCandidateRef: string;
	workspaceRef: string;
	taskRef: string;
	taskContextId: string;
	taskContextPlanDigest: string;
	orientationBindingDigest: string;
	orientationSemanticDigest: string;
	contextGenerationDigest: string;
	catalogDigest: string;
	entryDigest: string;
	membershipSemanticDigest: string;
	instanceId: string;
	objectRef: string;
	standardId?: string;
	entityType: string;
	bindingDigest: string;
	authenticity: WorkspaceHmacAuthenticityV1;
}
```

`resourceCandidateRef` is separate from both a model-local Query Candidate `localId` and its admitted durable `queryCandidateRef`. Those namespaces never alias. `queryCandidateRef` records semantic provenance only; it cannot change the exact selector.

`membershipSemanticDigest` is SHA-256 over UTF-8 JCS of `ResourceCandidateMembershipDigestBasisV1`, which contains the complete closed Orientation membership item including `objectRef`, optional `standardId`, `entityType`, display label, membership kind and observed version, plus the Orientation binding/semantic/selection/block digests. `entryDigest` is SHA-256 over UTF-8 JCS of the complete public entry without `entryDigest`. Entries preserve the exact admitted Orientation membership array order; order and duplicates are significant. `catalogDigest` is SHA-256 over UTF-8 JCS of the complete catalog without `catalogDigest`.

Each `resourceCandidateRef` is a fresh unguessable 128-bit value encoded as unpadded base64url and maps only to one authenticated private binding. `bindingDigest` is SHA-256 over UTF-8 JCS of the private binding without `bindingDigest` and `authenticity`; authenticity uses the same closed HMAC rule as other Workspace local receipts. The private binding, never the opaque string alone, carries Workspace/task/Admitted Task Context/Orientation/generation/catalog/entry/member and exact OpenCTI identity authority. Lookup recomputes every digest and requires byte-for-byte equality with the current catalog, current Orientation membership and current Context Generations before compiling a selector.

The reference expires when its task/plan is superseded, its catalog is replaced, the Orientation binding or membership disappears/changes, or any bound generation advances. Returning `A -> B -> A` cannot revive an old reference because the generation digest differs. Equal display labels, equal content or equal standard IDs do not merge distinct `objectRef` occurrences. Tamper, missing mapping, wrong Workspace/task/plan, removed membership, generation mismatch or catalog-order mismatch fails before I&E I/O and has no similar-candidate fallback.

The trusted binder resolves these relationships before I&E I/O:

```text
WorkspaceSessionRef -> workspaceRef
raw User Task Session entry + admitted Task Context -> taskRef
resourceCandidateRef -> current Orientation membership -> exact OpenCTI selector
workspaceRef + taskRef + actor/purpose/credential -> I&E use binding
```

The model cannot supply or override Workspace, Session, Task, Task Context, Case, actor, purpose, credential, OpenCTI instance/object ID, request/retrieval/operation ID, budgets, capture selector, authorization, freshness, retry, commit, receipt, or terminal fields. Unknown, expired, wrong-task, wrong-Workspace, generation-mismatched, removed, or no-longer-visible references fail before I&E I/O. There is no similar-resource fallback.

The application Interface remains `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn`. The first semantic operation is `retrieve_exact_resource`, but model-visible tool count, names, and payload decomposition remain Adapter choices.

The operation is available only through one trusted activation snapshot committed with the planning save point:

```typescript
interface WorkspaceCapabilityActivationSnapshotV1 {
	protocol: "workspace-capability-activation/v1";
	capabilityId: "intelligence_exact_resource_retrieval";
	catalogRevision: string;
	recipeDigest: string;
	intelligenceEvidenceQualificationId: string;
	activation: "available" | "unavailable";
	actorPurposePolicyDigest: string;
	budgetPolicyDigest: string;
	snapshotDigest: string;
}
```

Only `available` may stage the exact-resource capability for the next Pi snapshot. The model cannot create or change this record. Any catalog, recipe, I&E qualification, policy, budget or activation change advances the affected Context Generation; it cannot mutate an already admitted plan in place. Task Context may recognize the need while the capability is frozen or unavailable, but recognition never activates it.

`snapshotDigest` is SHA-256 over UTF-8 JCS of the complete activation snapshot without `snapshotDigest`. When IWS is later activated, a superseding revision must map one trusted activation snapshot after the Admitted Task Context commit and before any product Tool exposure in the Investigation Agent Run. The old same-planning-save-point mapping is superseded. Every later provider projection and Disclosure Decision binds the accepted activation snapshot digest; mismatch or a changed generation denies use.

## 3. Closed v1 Working Set records

The leased Pi Session is the only v1 authority for small task-scoped Working Set state. Workspace may use a private reducer to stage records, but no private store or separate local transaction may commit them. The I&E architecture's coarse phrase "Workspace performs a separate atomic Working Set transaction" means separate from the I&E commit; in v1 that Workspace transaction is exactly the owning Pi save-point CAS defined here.

```typescript
interface WorkingSetEntryV1 {
	protocol: "workspace-working-set-entry/v1";
	entryRef: string;
	workspaceRef: string;
	taskRef: string;
	taskContextId: string;
	resourceCandidateRef: string;
	resourceVersionRef: string;
	sourceCaptureId: string;
	resourceCapsuleSemanticDigest: string;
	admissionRetrievalId: string;
	admissionRetrievalReceiptSignedPayloadDigest: string;
	admissionRetrievalKeyId: string;
	createdByActionId: string;
	entryDigest: string;
}

interface WorkingSetSelectionV1 {
	protocol: "workspace-working-set-selection/v1";
	workspaceRef: string;
	taskRef: string;
	version: string;
	previousVersion?: string;
	orderedEntries: readonly { entryRef: string; entryDigest: string }[];
	selectionDigest: string;
}

interface WorkingSetDerivationEdgeV1 {
	protocol: "workspace-working-set-edge/v1";
	edgeId: string;
	actionId: string;
	inputKind: "resource_candidate" | "query_candidate" | "retrieval_receipt" | "resource_capsule";
	inputRef: string;
	inputDigest: string;
	outputEntryRef: string;
	edgeDigest: string;
}

type CanonicalWorkspaceActionOutcomeV1 =
	| {
			protocol: "workspace-action-outcome/v1";
			kind: "applied";
			actionId: string;
			entryRef: string;
			workingSetVersion: string;
			outcomeDigest: string;
	  }
	| {
			protocol: "workspace-action-outcome/v1";
			kind: "idempotent";
			actionId: string;
			entryRef: string;
			workingSetVersion: string;
			outcomeDigest: string;
	  }
	| {
			protocol: "workspace-action-outcome/v1";
			kind: "conflict";
			actionId: string;
			currentWorkingSetVersion: string;
			outcomeDigest: string;
	  }
	| {
			protocol: "workspace-action-outcome/v1";
			kind: "rejected";
			actionId: string;
			code: WorkingSetRejectionCodeV1;
			outcomeDigest: string;
	  };

type WorkingSetRejectionCodeV1 =
	| "candidate_not_current"
	| "task_binding_changed"
	| "retrieval_incomplete"
	| "retrieval_receipt_untrusted"
	| "resource_capsule_tampered"
	| "resource_use_not_current"
	| "working_set_budget_exceeded"
	| "operation_identity_conflict";

interface AppliedWorkingSetLocalReceiptV1 {
	protocol: "workspace-working-set-receipt/v1";
	outcomeKind: "applied" | "idempotent";
	actionId: string;
	actionRequestDigest: string;
	expectedWorkingSetVersion: string;
	outcomeDigest: string;
	entryDigest: string;
	selectionDigest: string;
	orderedEdgeDigests: readonly string[];
	authenticity: WorkspaceHmacAuthenticityV1;
}

interface NonAppliedWorkingSetLocalReceiptV1 {
	protocol: "workspace-working-set-receipt/v1";
	outcomeKind: "conflict" | "rejected";
	actionId: string;
	actionRequestDigest: string;
	expectedWorkingSetVersion: string;
	outcomeDigest: string;
	orderedEdgeDigests: readonly [];
	authenticity: WorkspaceHmacAuthenticityV1;
}

type WorkingSetLocalReceiptV1 = AppliedWorkingSetLocalReceiptV1 | NonAppliedWorkingSetLocalReceiptV1;

interface WorkspaceHmacAuthenticityV1 {
	algorithm: "HMAC-SHA-256";
	keyId: string;
	signedPayloadDigest: string;
	macBase64Url: string;
}

interface EvidenceAssemblyWorkingSetBasisV1 {
	protocol: "workspace-evidence-assembly-working-set-basis/v1";
	workspaceRef: string;
	taskRef: string;
	workingSetVersion: string;
	workingSetSelectionDigest: string;
	orderedEntries: readonly {
		entryRef: string;
		entryDigest: string;
		admissionReceiptSignedPayloadDigest: string;
	}[];
	savePointRef: string;
	savePointDigest: string;
	basisDigest: string;
}
```

All records are closed. The entry digest is SHA-256 over UTF-8 JCS of the entry without `entryDigest`. The selection digest is SHA-256 over UTF-8 JCS of the selection without `selectionDigest`; order is significant. An edge digest is SHA-256 over UTF-8 JCS of the edge without `edgeDigest`. An outcome digest is SHA-256 over UTF-8 JCS of that exact union member without `outcomeDigest`. The local receipt signed payload is UTF-8 JCS of the complete receipt without `authenticity`; `signedPayloadDigest` is its SHA-256 and the MAC covers those bytes. `actionRequestDigest` covers the closed operation kind, trusted binding, exact model choice, expected Working Set version, qualified recipe/catalog digest, and I&E request digest.

The raw Resource Capsule is never an ordinary assistant/tool-result Session body. A finalized product tool result contains only the canonical actor-safe action outcome and stable refs/digests. Large reusable bodies remain I&E-owned and are fetched by exact capture for a specific provider disclosure.

`EvidenceAssemblyWorkingSetBasisV1` is a consumer projection over the existing
selection, applied local receipts and owning Save Point. It creates no second
Working Set, material catalog or transaction. Its ordered entries must be an
exact subsequence of the named `WorkingSetSelectionV1` in selection order; every
entry/receipt must belong to the same committed Save Point history and resolve
byte-for-byte. The basis digest is SHA-256 over UTF-8 JCS with `basisDigest`
omitted. Missing, reordered, foreign, stale or uncommitted entries reject before
I&E revalidation.

## 4. Save-point admission and atomicity

The private Working Set policy accepts a finalized tool batch and returns one closed staging result:

```typescript
type WorkingSetActionStageV1 =
	| {
			kind: "apply";
			sourceCallIndex: number;
			entry: WorkingSetEntryV1;
			edges: readonly WorkingSetDerivationEdgeV1[];
			receipt: AppliedWorkingSetLocalReceiptV1;
			outcome: Extract<CanonicalWorkspaceActionOutcomeV1, { kind: "applied" }>;
	  }
	| {
			kind: "idempotent";
			sourceCallIndex: number;
			receipt: AppliedWorkingSetLocalReceiptV1;
			outcome: Extract<CanonicalWorkspaceActionOutcomeV1, { kind: "idempotent" }>;
	  }
	| {
			kind: "no_apply";
			sourceCallIndex: number;
			receipt: NonAppliedWorkingSetLocalReceiptV1;
			outcome: Extract<CanonicalWorkspaceActionOutcomeV1, { kind: "conflict" | "rejected" }>;
	  };

type WorkingSetStageOutcomeV1 =
	| {
			kind: "stage_mutation";
			expectedSessionLeaf: string;
			expectedWorkingSetVersion: string;
			actions: readonly WorkingSetActionStageV1[];
			selection: WorkingSetSelectionV1;
	  }
	| {
			kind: "stage_no_mutation";
			expectedSessionLeaf: string;
			expectedWorkingSetVersion: string;
			actions: readonly Exclude<WorkingSetActionStageV1, { kind: "apply" }>[];
	  }
	| {
			kind: "rollback";
			code: "session_basis_changed" | "batch_shape_invalid" | "receipt_authenticator_unavailable";
	  };
```

Before staging, Workspace recomputes the Resource Capsule digest, verifies the qualified I&E Ed25519 signature and signed payload digest, and validates protocol, current Workspace/task/Case/actor/purpose binding, exact Resource Version/Source Capture/capsule digests, retrieval-time active status/Use Disposition, operation identity, expected Working Set version, and budgets.

One expected-leaf Pi save-point group contains, in this order; its final receipt is the single closed [`ContextSnapshotReceiptV1`](pi-native-workspace-lifecycle-v1-contract.md#7-session-eligibility-receipt-trust-and-the-stale-marker-replacement) owned by the lifecycle contract:

1. the complete assistant message/tool calls;
2. one finalized Pi tool-result entry per call in assistant source order, regardless of completion order;
3. entries from `apply` action stages in source-call order;
4. the one resulting Working Set selection when at least one action applies;
5. derivation edges from `apply` stages in canonical `(outputEntryRef, edgeId)` order;
6. one local receipt per action in source-call order;
7. one canonical action outcome per action in source-call order; and
8. the authenticated Context Snapshot receipt physically last.

Pi commits the complete group or appends none. Only this save-point CAS turns `applied` records into durable truth. A tool completion, private reducer result, I&E receipt, or blob write cannot independently mutate the Working Set. Same action ID/request digest returns the existing entry/selection/outcome; same ID with another digest is an integrity rejection. Same-entry races have one winner. Disjoint entry additions may both survive serialized later save points, each based on the current selection version.

`actions` contains exactly one stage for every finalized exact-resource call and is strictly ordered by unique contiguous `sourceCallIndex`. `stage_mutation` contains at least one `apply`; its selection version advances exactly once from `expectedWorkingSetVersion` and contains every prior retained entry plus the applied entries according to closed selection policy. `stage_no_mutation` contains no `apply` and appends no selection. Receipt `outcomeKind`, outcome union member, entry/selection digests, and edge list must agree exactly; mismatch returns `rollback` and appends none.

Crash before commit leaves no Working Set state. Crash or unknown acknowledgement after commit is resolved from the exact Session group and returns its existing receipt; the I&E operation is never replayed from Session. A Context Snapshot receipt failure or Session-leaf conflict appends none of the group.

The entry is neutral selected source material. It is not Evidence, an accepted fact, Candidate Finding, Case membership, or an OpenCTI object copy.

## 5. Unified context and exact-capture revalidation

Provider, compaction, and branch-summary consumers use the same Workspace eligibility policy. Raw planning protocol, raw Resource Capsules, partial/stale/unknown/unauthorized tool data, uncommitted Working Set state, and entries for another task are audit-only.

A provider request may select only qualified current Working Set entries. Immediately before a provider invocation that would disclose any Working Set/I&E content, Workspace calls I&E with `intent.kind = "workspace_model_disclosure_revalidation"` and `selector.capture = { kind: "exact", captureId }` under the same trusted use binding. It uses a new provider-attempt-bound request identity and supplies the exact material-admission retrieval ID, signing key ID, signed-payload digest and capsule digest. The completed signed result must reproduce Resource Version, Source Capture ID, capsule semantic digest, active status, current model disclosure, unexpired retention and the expected Use Disposition revision. Any difference denies the invocation; it never substitutes a newer capture or edits/truncates a signed capsule. Required capsule content that cannot fit the declared token/byte budget fails before provider invocation.

The exact retrieval completion is the disclosure-decision linearization point for I&E status. A later source change cannot retract an invocation already authorized and possibly begun, but it invalidates future use and fences intersecting late output.

## 6. Reference-only provider-proof candidate: Logical Provider Invocation Artifact

Sections 6–8 preserve the earlier provider-proof design to show the requirements that motivated the generic Pi lifecycle. Their `prepare/commit/lookup`, canonical provider schemas, prepared reference, permit, Model Input Receipt, and acknowledgement behavior are superseded by [`pi-native-workspace-lifecycle/v1`](pi-native-workspace-lifecycle-v1-contract.md). Future IWS activation must replace these definitions with a narrow application Adapter that contributes Workspace binding, disclosure/revalidation decision, prior Session custom-entry drafts, and opaque terminal material; it must not copy the generic PNW transaction.

The proof seam is owned by `packages/agent`. `packages/ai` remains the provider/auth Adapter owner, but it may participate through a private preparation seam that returns trusted credential/config bindings and the retained raw values needed for one invocation. The artifact records the provider-neutral logical invocation after final context conversion/order, tool schema selection, token policy, model identity, credential resolution, and stream options are fixed, immediately before the protected `models.streamSimple` path. It does not claim the HTTP request bytes emitted by a provider implementation. Providers may still serialize, sign, clamp, batch, or transform transport data privately.

Current `AgentHarness` behavior is not sufficient: its turn snapshot shallow-copies stream options and nested metadata values, `before_provider_request` may patch options, `before_provider_payload`/`onPayload` may replace the downstream payload, and `Models.streamSimple` resolves and merges auth internally. Protected v1 therefore uses the following stricter opt-in path; it does not infer immutability from the current shallow snapshot.

```typescript
type CanonicalJsonValueV1 =
	| null
	| boolean
	| number
	| string
	| readonly CanonicalJsonValueV1[]
	| CanonicalJsonObjectV1;

interface CanonicalJsonObjectV1 {
	readonly [key: string]: CanonicalJsonValueV1;
}

interface CanonicalValueHeaderBindingV1 {
	name: string;
	disposition: "value";
	valueHmac: string;
}

interface CanonicalSuppressedHeaderBindingV1 {
	name: string;
	disposition: "suppress_default";
}

type CanonicalRequestOptionHeaderBindingV1 =
	| CanonicalValueHeaderBindingV1
	| CanonicalSuppressedHeaderBindingV1;

interface CanonicalProviderOptionsV1 {
	protocol: "pi-provider-options/v1";
	transport: "sse" | "websocket" | "websocket-cached" | "auto" | null;
	cacheRetention: "none" | "short" | "long" | null;
	timeoutMs: number | null;
	maxRetries: number | null;
	maxRetryDelayMs: number | null;
	reasoning: "minimal" | "low" | "medium" | "high" | "xhigh" | "max" | null;
	sessionId: string | null;
	metadata: CanonicalJsonObjectV1 | null;
	requestOptionHeaders: readonly CanonicalRequestOptionHeaderBindingV1[];
	resolvedApiKeyBindingDigest: string | null;
	resolvedProviderEnvBindingDigest: string | null;
	credentialBindingDigest: string;
}

interface CanonicalModelIdentityV1 {
	protocol: "pi-provider-model-identity/v1";
	provider: string;
	api: string;
	modelId: string;
	modelName: string;
	resolvedBaseUrlBindingDigest: string;
	reasoningCapable: boolean;
	thinkingLevelMap: CanonicalJsonObjectV1 | null;
	inputModalities: readonly ("text" | "image")[];
	cost: CanonicalJsonObjectV1;
	contextWindow: number;
	maxTokens: number;
	modelHeaders: readonly CanonicalValueHeaderBindingV1[];
	compat: CanonicalJsonObjectV1 | null;
}

interface LogicalProviderInvocationDigestBasisV1 {
	protocol: "pi-logical-provider-invocation-digest-basis/v1";
	dispatchId: string;
	agentRunId: string;
	piTurnId: string;
	providerAttemptId: string;
	runGenerationId: string;
	modelIdentityDigest: string;
	credentialBindingDigest: string;
	orderedMessageDigest: string;
	toolSchemaDigest: string;
	providerOptionsDigest: string;
}

interface LogicalProviderInvocationArtifactV1 {
	protocol: "pi-logical-provider-invocation/v1";
	digestBasis: LogicalProviderInvocationDigestBasisV1;
	logicalInvocationDigest: string;
}

interface PreparedProviderInvocationV1 {
	preparedRef: string;
	artifact: LogicalProviderInvocationArtifactV1;
}

type ProviderPreparationRejectionCodeV1 =
	| "unsupported_model_projection"
	| "unsupported_context_variant"
	| "invalid_canonical_value"
	| "metadata_budget_exceeded"
	| "invalid_or_oversized_header"
	| "unknown_stream_option"
	| "payload_mutator_forbidden"
	| "credential_unavailable"
	| "credential_drift"
	| "retired_generation";

type ProviderPrepareOutcomeV1 =
	| { kind: "prepared"; value: PreparedProviderInvocationV1 }
	| { kind: "rejected"; code: ProviderPreparationRejectionCodeV1 };

type ProviderReceiptMismatchCodeV1 =
	| "dispatch_id"
	| "agent_run_id"
	| "pi_turn_id"
	| "provider_attempt_id"
	| "run_generation_id"
	| "model_identity"
	| "credential_identity"
	| "ordered_messages"
	| "tool_schema"
	| "provider_options"
	| "logical_invocation"
	| "disclosure_decision"
	| "receipt_digest"
	| "receipt_authenticity";

interface ProviderInvocationPermitV1 {
	permitId: string;
	preparedRef: string;
	dispatchId: string;
	runGenerationId: string;
	logicalInvocationDigest: string;
	modelInputReceiptDigest: string;
	disclosureDecisionDigest: string;
	committedLeaf: string;
	singleUse: true;
}

interface ProviderDispatchTransaction {
	prepare(finalInvocation: FinalProviderInvocation): Promise<ProviderPrepareOutcomeV1>;

	commit(input: {
		expectedSessionLeaf: string;
		preparedRef: string;
		disclosureBasis: DisclosureDecisionBasisV1;
		applicationEntry: ModelInputReceiptV1;
	}): Promise<ProviderDispatchCommitOutcomeV1>;

	lookup(input: {
		dispatchId: string;
		logicalInvocationDigest: string;
		modelInputReceiptDigest: string;
		disclosureDecisionDigest: string;
	}): Promise<ProviderDispatchLookupOutcomeV1>;
}

type ProviderDispatchCommitOutcomeV1 =
	| { kind: "committed"; permit: ProviderInvocationPermitV1 }
	| { kind: "already_committed"; permit: ProviderInvocationPermitV1 }
	| { kind: "already_consumed"; committedLeaf: string }
	| { kind: "committed_without_prepared_value"; committedLeaf: string }
	| { kind: "conflict"; currentLeaf: string }
	| { kind: "identity_conflict" }
	| {
			kind: "invalid_prepared_invocation";
			code: "unknown_prepared_ref" | "retired_generation" | "credential_drift";
	  }
	| { kind: "receipt_mismatch"; code: ProviderReceiptMismatchCodeV1 }
	| { kind: "failed"; retryable: boolean }
	| { kind: "acknowledgement_unknown" };

type ProviderDispatchLookupOutcomeV1 =
	| { kind: "present"; permit: ProviderInvocationPermitV1 }
	| { kind: "present_consumed"; committedLeaf: string }
	| { kind: "present_without_prepared_value"; committedLeaf: string }
	| { kind: "absent" }
	| { kind: "identity_conflict" }
	| { kind: "unavailable"; retryable: boolean };
```

### 6.1 Preparation and canonical projection

`FinalProviderInvocation` is an internal Pi value. `prepare` recursively snapshots the resolved model invocation, complete provider-neutral `Context` messages, ordered tool definitions/schemas, final stable options, raw custom/auth/model headers, and raw resolved auth/config required for one call. It does not retain caller arrays, objects, maps, schemas, metadata, headers, or model objects as the dispatch source. Mutating any caller-owned object after `prepare` cannot alter either a digest or the eventual Adapter arguments. The application receives only `preparedRef` plus the non-secret artifact; the full snapshot remains private, memory-only, generation-scoped Pi state.

Canonicalization is exact:

- every canonical projection uses RFC 8785 JCS, encoded as UTF-8, then SHA-256 with lowercase `sha256:<hex>` representation;
- `orderedMessageDigest` hashes `{ protocol: "pi-ordered-messages/v1", systemPrompt: string | null, messages: [...] }` using the complete recursively snapshotted provider-neutral `Context` system prompt and messages in their existing order;
- `toolSchemaDigest` hashes `{ protocol: "pi-ordered-tools/v1", tools: [...] }` using the complete provider-visible name, description, and schema of each tool in existing order; executable functions never enter the projection;
- `providerOptionsDigest` hashes the exact `CanonicalProviderOptionsV1`; `modelIdentityDigest` hashes the exact `CanonicalModelIdentityV1`; and `logicalInvocationDigest` hashes the exact `LogicalProviderInvocationDigestBasisV1` as declared;
- arrays, including messages, content blocks, tools, enum arrays, and schema arrays, retain source order and are never sorted; object/map keys use JCS key order; JCS performs no additional Unicode normalization;
- `undefined`, non-finite numbers, bigint, functions, symbols, cycles, accessors with side effects, unsupported message/content/schema variants, and unknown fields in any protected projection fail closed before receipt append.

The v1 context canonicalizer accepts exactly the current provider-neutral `Context` union: optional `systemPrompt`; ordered `user`, `assistant`, and `toolResult` messages; their complete declared identity/status/usage/timestamp fields; ordered text, thinking, image, and tool-call content variants where allowed by the message role; tool-call arguments; tool-result details and added-tool names; and ordered `Tool` name/description/parameters. All nested arguments, details, diagnostics, signatures, compatibility data, and TypeBox/JSON schemas must reduce to admitted canonical JSON. Optional absent message fields remain absent; an explicitly present `undefined` value is invalid. Unknown message roles, message/tool top-level fields, or content variants are rejected until the canonicalizer protocol is revised. The proof does not interpret JSON Schema keywords: it snapshots and digests the complete JCS-valid parameters object, including extension keywords, so none can bypass proof. The digest covers even fields a particular provider may ignore because they are still part of Pi's logical Adapter input.

`CanonicalModelIdentityV1` is derived from the actual resolved `requestModel` returned by auth preparation, not from a registry or the pre-auth caller model. It binds every current `Model` field: `id`, `name`, `api`, `provider`, resolved `baseUrl`, `reasoning`, complete optional `thinkingLevelMap`, ordered `input`, complete `cost` including ordered tiers, `contextWindow`, `maxTokens`, the independent model-header layer, and complete optional `compat`. Raw `baseUrl` is retained only in the private prepared snapshot; its durable field is a domain-separated keyed binding digest. `name` and `cost` are included even though current Adapters use them for display/accounting rather than request construction, because the logical proof claims the exact full `requestModel` object. No invented model registry or registry revision participates. Any unknown or newly added enumerable `Model` field fails protected v1 preparation until this closed protocol and acceptance catalog are revised.

The only stable v1 stream option data fields are `transport`, `cacheRetention`, `timeoutMs`, `maxRetries`, `maxRetryDelayMs`, `reasoning`, `sessionId`, `metadata`, and normalized headers. Optional absence is represented by `null`, never by omitted/`undefined` data. Numeric values must be finite, non-negative safe integers. `sessionId` is at most 512 UTF-8 bytes. Metadata must be classified non-secret, JCS-valid JSON with maximum depth 8, at most 256 total members/elements, keys at most 128 UTF-8 bytes, strings at most 4096 UTF-8 bytes, and complete JCS encoding at most 16,384 bytes. Anything outside those bounds fails closed.

Header proof follows the two actual `Models.applyAuth` layers and never collapses them into one cross-layer collection:

1. `requestModel.headers` is the resolved `Model.headers?: Record<string, string>` layer and canonicalizes to `CanonicalModelIdentityV1.modelHeaders`; it permits only `disposition: "value"`.
2. `requestOptions.headers` is the `ProviderHeaders = Record<string, string | null>` produced after `applyAuth` spreads `auth.headers` and then explicit request headers, so an exact explicit key overrides the same auth key. It canonicalizes separately to `CanonicalProviderOptionsV1.requestOptionHeaders`; string values use `disposition: "value"`, while `null` uses `disposition: "suppress_default"` with no value HMAC.

Within each layer, raw names must already be valid ASCII HTTP field-name tokens; they are ASCII-lowercased without trimming, rejected on collisions after normalization, and sorted by canonical name. At most 64 entries are allowed per layer; a name is at most 128 ASCII bytes and a raw value at most 8192 UTF-8 bytes. The two layers are not cross-merged or collision-deduplicated by the proof because provider Adapters decide how `requestModel.headers` and `requestOptions.headers` interact; both complete ordered collections are nevertheless covered by `modelIdentityDigest` and `providerOptionsDigest`. Thus model-vs-options same-name values remain two bound inputs. Within the options layer, same-spelling explicit input overrides auth exactly as `applyAuth` does; differently cased auth/explicit names that collide only after canonicalization fail protected preparation rather than guessing precedence.

For every `disposition: "value"`, `valueHmac` is `HMAC-SHA-256(bindingKey, UTF8("pi-header-value/v1") || u32be(nameBytes.length) || nameBytes || u64be(valueBytes.length) || valueBytes)`, where `nameBytes` is the canonical ASCII-lowercase name and `valueBytes` is the exact raw UTF-8 value. A `null` suppression is represented only by the tagged `suppress_default` member; it is never encoded as the string `"null"`. Raw header values are deep-copied into the private prepared snapshot but never written to durable evidence or ordinary logs.

The trusted auth Adapter supplies `credentialBindingDigest`, binding provider/credential slot, credential revision/source, resolved auth result and source identity. `resolvedApiKeyBindingDigest`, `resolvedProviderEnvBindingDigest`, and `resolvedBaseUrlBindingDigest` are separate HMAC-SHA-256 values over `UTF8("pi-api-key/v1")`, `UTF8("pi-provider-env/v1")`, or `UTF8("pi-base-url/v1")`, respectively, followed by a big-endian byte length and the exact raw UTF-8 value; the environment value is UTF-8 JCS of its complete key-sorted string map. Absence is `null`. `credentialBindingDigest` is a separate domain-tagged HMAC over the non-secret credential identity plus those resolved binding digests and the auth-source header binding digest. The request-options header collection binds the post-`applyAuth` auth/explicit result, while credential identity additionally binds the auth source without exposing it. Raw API key, environment, base URL, credentials, and auth config are recursively snapshotted only in private prepared state. The protected Adapter path must consume that retained resolution; it cannot run ambient auth resolution again after `prepare`. Any resolution drift retires the prepared value and invokes nothing. Secret-bearing metadata is invalid and must use this trusted auth/header path.

`AbortSignal` and `onResponse` are lifecycle capabilities, not canonical data. Pi binds them to the same `runGenerationId`, excludes them from all digests, and installs only its own non-payload-mutating response observer. No other function, custom transport callback, `onPayload`, API key, provider environment, temperature, max-token override, thinking-budget object, websocket-only option, or unknown option is admitted as application-controlled protected v1 data. The current `before_provider_request` chain must finish before `prepare`; its result then passes the closed validation above. For a protected request, any registered `before_provider_payload` handler or caller-supplied `onPayload` is rejected before receipt append, and Pi installs no payload-replacement callback. This deliberately disables the existing payload-mutation seam only for IWS-protected dispatches so it cannot bypass proof.

### 6.2 Commit, lookup, and single-use invocation

Before appending, `commit` recomputes the Disclosure Decision and receipt digests, verifies Workspace HMAC authenticity, and compares every application identity with the prepared artifact: dispatch, Agent Run, Pi Turn, provider attempt, run generation, model, credential, ordered messages, tools, provider options, logical invocation, and disclosure decision. `disclosureBasis` must itself reproduce all shared prepared identities and its digest must equal `applicationEntry.disclosureDecisionDigest`. Any mismatch returns `receipt_mismatch`, appends zero entries, issues no permit, and invokes no Adapter. Reusing a `dispatchId` with a different artifact, receipt, disclosure, credential, or other identity digest returns `identity_conflict` with the same zero-effect behavior.

Pi's invocation path accepts only `(preparedRef, ProviderInvocationPermitV1)`. It atomically consumes the current-generation, single-use permit and hands the exact retained frozen model/context/options/auth snapshot to the Adapter. The original caller objects and a reconstructed value are never accepted. A second consume, retired generation, missing prepared value, mismatched permit, or post-prepare mutation invokes nothing. `already_committed`/`present` can return a permit only while the original unconsumed prepared value is resident and current; otherwise the explicit consumed or without-prepared-value outcomes preserve `may_have_dispatched` evidence without enabling replay.

Same complete identity is idempotent. A Session-leaf conflict, validation failure, absent/unavailable lookup, identity conflict, consumed permit, or missing prepared value invokes no provider. `acknowledgement_unknown` requires exact lookup; only `present` may return the original permit, and no second receipt is written. Crash recovery never reconstructs a missing prepared value or automatically resends.

The proof ends at the immutable logical input handed through the protected `models.streamSimple` Adapter path. It does not prove provider-specific payload bytes, HTTP/wire serialization, local socket write, remote receipt, billing, provider execution, or output reproducibility.

V1 requires this transaction only for provider requests that disclose Working Set/I&E content. Task Context planning and Orientation-only provider requests remain outside IWS v1, while still using the lifecycle contract's ordinary current-context and disclosure denial.

## 7. Reference-only Model Input Receipt and disclosure digest candidate

```typescript
interface ModelInputReceiptV1 {
	protocol: "workspace-model-input/receipt-v1";
	dispatchId: string;
	workspaceRef: string;
	taskRef: string;
	taskContextId: string;
	taskContextPlanDigest: string;
	capabilityActivationSnapshotDigest: string;
	agentRunId: string;
	piTurnId: string;
	providerAttemptId: string;
	runGenerationId: string;
	orientationSemanticDigest: string;
	contextGenerationDigest: string;
	workingSetVersion: string;
	workingSetSelectionDigest: string;
	orderedWorkingSetEntryDigests: readonly string[];
	orderedResourceCapsuleDigests: readonly string[];
	orderedResourceCapsuleRenderManifestDigests: readonly string[];
	sessionProjectionDigest: string;
	orderedMessageDigest: string;
	toolSchemaDigest: string;
	modelIdentityDigest: string;
	credentialBindingDigest: string;
	providerOptionsDigest: string;
	logicalInvocationDigest: string;
	disclosureDecisionDigest: string;
	dispatchKnowledge: "may_have_dispatched";
	receiptDigest: string;
	authenticity: WorkspaceHmacAuthenticityV1;
}

interface DisclosureResourceBasisV1 {
	workingSetEntryRef: string;
	workingSetEntryDigest: string;
	resourceVersionRef: string;
	sourceCaptureId: string;
	resourceCapsuleSemanticDigest: string;
	admissionRetrievalId: string;
	admissionRetrievalReceiptSignedPayloadDigest: string;
	disclosureValidationRetrievalId: string;
	disclosureValidationReceiptSignedPayloadDigest: string;
	admissionRetrievalKeyId: string;
	disclosureValidationKeyId: string;
	useDecisionRevision: string;
	useDecisionObservedAt: string;
	retentionUntil: string;
	actorPurposeBindingDigest: string;
}

interface ResourceCapsuleRenderManifestV1 {
	protocol: "workspace-resource-capsule-render/v1";
	workingSetEntryRef: string;
	resourceVersionRef: string;
	sourceCaptureId: string;
	resourceCapsuleSemanticDigest: string;
	renderingProfileDigest: string;
	orderedDisclosedSegmentRefs: readonly string[];
	renderedContentDigest: string;
	manifestDigest: string;
}

interface SessionProjectionDigestBasisV1 {
	protocol: "workspace-session-projection-digest-basis/v1";
	workspaceRef: string;
	taskRef: string;
	taskContextId: string;
	taskContextPlanDigest: string;
	capabilityActivationSnapshotDigest: string;
	sessionRefBindingDigest: string;
	branchRef: string;
	expectedSessionLeaf: string;
	orderedProjectedEntryDigests: readonly string[];
	compactionGeneration: string | null;
	orientationSemanticDigest: string;
	orderedContextDependencies: readonly {
		dependencyKey: string;
		contextGeneration: string;
		generationControlEntryDigest: string;
		projectedContentDigest: string;
	}[];
	contextGenerationDigest: string;
	contextProjectionDigest: string;
	workingSetSelectionDigest: string;
	orderedResourceCapsuleRenderManifestDigests: readonly string[];
	eligibilityPolicyRevision: string;
}

interface DisclosureDecisionBasisV1 {
	protocol: "workspace-disclosure-decision/v1";
	dispatchId: string;
	workspaceRef: string;
	taskRef: string;
	taskContextId: string;
	taskContextPlanDigest: string;
	capabilityActivationSnapshotDigest: string;
	agentRunId: string;
	piTurnId: string;
	providerAttemptId: string;
	runGenerationId: string;
	orientationSemanticDigest: string;
	contextGenerationDigest: string;
	workingSetVersion: string;
	workingSetSelectionDigest: string;
	resources: readonly DisclosureResourceBasisV1[];
	sessionProjectionDigest: string;
	orderedMessageDigest: string;
	toolSchemaDigest: string;
	modelIdentityDigest: string;
	credentialBindingDigest: string;
	providerOptionsDigest: string;
	logicalInvocationDigest: string;
}
```

`DisclosureDecisionBasisV1.resources` is ordered exactly as capsules appear in the logical provider context. `disclosureDecisionDigest` is SHA-256 over UTF-8 JCS of the complete basis. `receiptDigest` is SHA-256 over UTF-8 JCS of the receipt without `receiptDigest` and `authenticity`. The authenticity signed payload is UTF-8 JCS of the complete receipt without `authenticity`; its SHA-256 is `signedPayloadDigest`, and the MAC covers those exact bytes. Every digest array is closed and order-sensitive; duplicate entry/capsule identity is invalid.

Each capsule rendered into the logical provider context has one `ResourceCapsuleRenderManifestV1`. Its `manifestDigest` is SHA-256 over UTF-8 JCS of the manifest without `manifestDigest`; segment order is disclosure order. `sessionProjectionDigest` is SHA-256 over UTF-8 JCS of the complete `SessionProjectionDigestBasisV1`.

`orderedProjectedEntryDigests` covers only the eligible Pi Session entries actually projected, in actual projection order, using the lifecycle contract's `ContextSnapshotGroupEntryDigestBasisV1`; it never means every retained entry. `contextProjectionDigest` uses the lifecycle-owned `ContextSnapshotProjectionDigestBasisV1`. `orderedContextDependencies` uses the same fields and canonical order as the lifecycle receipt, and `contextGenerationDigest` uses its `ContextGenerationVectorDigestBasisV1`. The branch/head, compaction generation, Admitted Task Context, capability activation, Orientation/generations, Working Set selection, render manifests and eligibility-policy revision are therefore independently recomputable. `orderedResourceCapsuleRenderManifestDigests` in the receipt, basis and logical message construction must be identical.

The mandatory v1 record is the pre-I/O receipt plus the exact canonical logical invocation digest. A digest is equality evidence, not replay.

Protected exact-input replay is disabled by default and deferred to a separate contract. It may activate only when every input owner independently permits the complete logical input's retention and a qualified protected store defines stage/commit/abort/lookup/access/GC behavior. The I&E Resource Capsule's own 365-day permission does not authorize retention of the User Task, Session content, Orientation, tool schemas, model options, or the complete provider prompt. This contract makes no exact-input reconstruction or 365-day full-prompt retention claim.

## 8. Failure and recovery

| Scenario | Deterministic result |
|---|---|
| invalid/tampered/wrong-binding I&E result | zero Working Set mutation and no capsule disclosure |
| cancel/close/supersede/context drift before save point | rollback the complete tool/Working Set group; retired generation rejects late completion |
| crash after I&E completion before save point | no Working Set state; source-side I&E receipt remains harmless audit |
| save-point acknowledgement unknown | inspect the exact Session leaf/group; never replay the I&E operation from Session |
| parallel tools finish out of order | finalized results and all dependent records persist in assistant source order |
| same action ID/same digest | return the existing outcome |
| same action ID/different digest | append none; integrity rejection |
| exact-capture drift/revocation or token failure | no Model Input Receipt and no provider invocation |
| dispatch commit conflict/failure | no provider invocation |
| dispatch acknowledgement unknown | exact lookup; only `present` permits the original immutable invocation |
| same dispatch ID/different digest | `identity_conflict`; no provider invocation |
| caller mutates messages/tools/options/metadata/headers/model after `prepare` | prepared digests and Adapter arguments remain unchanged because only the recursive snapshot is dispatchable |
| resolved `requestModel` contains a new field not in v1 | preparation rejects; there is no registry fallback or partial model digest |
| options header is `null` versus literal string `"null"` | canonical suppression member versus value member/HMAC; digests differ |
| auth header is overridden by the exact same explicit options key | bind the post-`applyAuth` explicit value in the options layer and retain auth-source identity in credential binding |
| model header and request-options header share a name | keep two separately ordered bound entries; proof does not pre-merge Adapter layers |
| two names in one layer differ only by ASCII case | normalized collision; preparation rejects before receipt append |
| protected request has `before_provider_payload`, `onPayload`, function-valued, cyclic, non-finite, `undefined`, or unknown option data | fail before receipt append; no provider invocation |
| receipt or Disclosure Decision differs from any prepared dispatch/run/turn/attempt/model/credential/message/tool/options/logical identity | `receipt_mismatch`; zero append and no provider invocation |
| permit is consumed twice, belongs to another generation, or its prepared value is missing | no second invocation and no reconstruction |
| crash after dispatch receipt, before or after Adapter call | retain `may_have_dispatched`; never auto-resend, resume, or splice |
| cancel/close after dispatch receipt | retain receipt, retire generation, discard late output/tool dispatch |
| partial provider output | no Working Set/I&E mutation; normal save-point/publication rules decide output eligibility |
| second Session writer | lease or expected-leaf conflict; no guessed-head retry |

## 9. Verification and activation gates

Acceptance is behavioral through `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn` plus focused generic Pi tests. Test names and private reducers are not substitute evidence. `IWS1-PD`, `IWS1-PC`, `IWS1-HB`, `IWS1-PM`, `IWS1-PH`, `IWS1-PI`, and `IWS1-MI` below are retained reference-only provider candidates and cannot satisfy future acceptance; their generic concerns are now owned by PNW, while a future IWS revision must replace them with application-Adapter acceptance.

- **IWS1-TN:** Query Candidates are proposed only during the formal Investigation Agent Run and contain no resource reference or selector; Resource Candidate References are minted only after current task/context admission and bind only current actor-visible Orientation membership.
- **IWS1-ID:** the trusted binder closes Session-to-Workspace, task-entry/Task-Context-to-task, Resource-Candidate-to-selector, and actor/purpose/credential identity; underlying source IDs are absent from tool-enabled model context and model-supplied trusted fields fail before I/O.
- **IWS1-AT:** exact closed entry/selection/edge/receipt/outcome digests and source-ordered finalized tool results commit in one Context-Snapshot-last Pi save point or not at all.
- **IWS1-CC:** same-entry winner/conflict/idempotence, disjoint later commits, duplicate callbacks, unknown acknowledgement, and lease conflicts preserve one Session authority.
- **IWS1-IS:** raw capsule, partial, stale, unknown, unauthorized, uncommitted, and old-task material reaches no provider, compaction, branch summary, or Artifact.
- **IWS1-PD:** logical artifact creation occurs after final conversion/order/schema/token/model/credential/options and before the protected `models.streamSimple` path; the Adapter receives only the retained immutable prepared snapshot, never caller objects or an application reconstruction.
- **IWS1-PC:** the actual resolved `requestModel` identity binds all current Model fields (`id`, `name`, `api`, `provider`, resolved `baseUrl`, `reasoning`, `thinkingLevelMap`, ordered `input`, complete `cost`, `contextWindow`, `maxTokens`, model headers, `compat`) with no registry or registry revision; any new/unknown Model field rejects. Credential identity, system prompt plus ordered complete messages, ordered tools/schemas, and every closed stable option recompute with exact JCS/UTF-8/SHA-256 rules.
- **IWS1-HB:** model `Record<string,string>` headers and post-`applyAuth` request-options `Record<string,string|null>` headers remain two separate canonical collections. Cases prove exact auth-key override by explicit options, model-vs-options same name without pre-merge, ASCII-case collision rejection within each layer, `null` suppression distinct from literal `"null"`, exact domain/length-prefixed value HMAC, and no raw secret persistence.
- **IWS1-PM:** recursive mutation of every caller-owned nested model/context/tool/schema/options/metadata/header object after `prepare` changes neither digest nor Adapter input; cyclic, non-finite, `undefined`, function, symbol, unknown/new option, invalid metadata/header, credential drift, and unsupported variants all fail closed.
- **IWS1-PH:** `AbortSignal` and `onResponse` remain same-generation lifecycle capabilities outside the digest; protected dispatch rejects `before_provider_payload`, caller `onPayload`, and any payload/custom-transport callback before receipt append, while ordinary non-IWS Harness behavior remains unchanged.
- **IWS1-PI:** commit/lookup and permit-consume result unions, single-use/current-generation binding, same-ID/different-any-digest, leaf conflict, unknown acknowledgement, missing prepared value, crash before/after Adapter call, cancel, ignored abort, and no automatic resend are exercised.
- **IWS1-MI:** every Model Input Receipt and Disclosure Decision digest projection recomputes exactly; commit changes zero state and makes zero Adapter calls when any dispatch/run/turn/attempt/model/credential/message/tool/options/logical/disclosure identity or authenticity differs from the prepared artifact. It proves logical Adapter input only, and digest-only evidence is never described as replay.
- **IWS1-SP:** `sessionProjectionDigest` recomputes from the lifecycle-owned entry/projection/generation bases plus closed branch/head, actual projected-entry order, compaction generation, Admitted Task Context, capability activation, Orientation/generations, Working Set selection, render manifests and eligibility-policy revision; changing any one field changes or invalidates the receipt.
- **IWS1-RV:** each provider attempt binds a distinct IER1 disclosure-validation receipt to the original admission receipt/capsule. Admission proof cannot substitute for current disclosure validation, and changed Use Disposition revision fails closed.
- **IWS1-CA:** only a committed `available` capability activation snapshot can stage the exact-resource recipe; activation or qualification change advances the affected Context Generation and never edits an admitted plan in place.
- **IWS1-RC:** membership, entry, catalog and private-binding digests recompute exactly; candidate order matches the admitted Orientation array; opaque refs are unguessable and resolve only under the same Workspace/task/plan/Orientation/generation/catalog. Tamper, wrong-task, `A -> B -> A`, removed membership and equal-label/different-object fixtures fail or remain distinct before I&E I/O.
- **IWS1-PB:** public events have exact count/order, one terminal, and non-rejecting result across success and every race.
- **IWS1-IR:** every paired IER1 conformance case passes through both qualified I&E Adapters and then the public Workspace seam.

Three gates keep independent Module work parallel without weakening disclosure evidence:

1. **I&E core package:** its owning route/local rules, active IER1 contract, operation-store/trust Port semantics and two-Adapter fixture catalog are closed. IER1 core TDD may proceed without importing Workspace, calling a provider or activating live OpenCTI.
2. **Workspace consumer:** PNW-A through PNW-E and TU-01 through TU-15 independently pass through the public Workspace seam; all focused Pi/Workspace tests and root `npm run check` pass under explicit Node 24.14; a superseding IWS revision then closes the Admitted Task Context/capability mapping and receives independent reacceptance with the Working Set and disclosure-validation semantics.
3. **Real-provider disclosure:** the complete IER1 + IWS1 vertical, the superseding IWS-to-PNW application Adapter, and the Pi-owned Provider Dispatch Transaction pass independent public-seam/focused acceptance before any real-provider use or delivered/prototype claim.

The current per-Turn Harness implementation is not this prototype and satisfies neither the consumer nor provider gate.
