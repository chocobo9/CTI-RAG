# `pre-investigation-task-understanding/v1` Contract

Status: **Independent design acceptance PASS; focused implementation/public-seam PASS.** It supersedes the unimplemented same-Agent-Run planning design in [`task-context-understanding/v1`](task-context-understanding-v1-contract.md). This PASS closes the Workspace-owned Task Understanding Module and committed handoff only; it does not claim Initial Investigation Context, Agent Run, publication, PNW-C Integration PASS, or Integrated PASS.

Exact-input-count amendment status: **Design PASS and focused implementation/public-seam PASS on 2026-07-22**. The generic Pi prepared-counter/A3.2 seam and Workspace Task Understanding consumer both passed focused public acceptance. The closed amendment pre-binds only the Workspace-known model reference and counter/tokenizer/wrapper configuration identity; the actual auth-resolved Model digest and exact-count evidence are produced after A3.1 preparation, returned as sealed non-secret invocation evidence, and verified before semantic admission. No PNW-C Integration PASS, Integrated PASS, real-provider registration, or real-provider activation is claimed.

## 1. Decision, authority, and ownership

`CaseWorkspace.prompt({ task })` remains the common Interface and creates one caller-visible `WorkspaceTurn`. Before any formal Pi model-tool loop begins, a private `TaskUnderstandingModule` may perform exactly one bounded model invocation and then applies deterministic admission. It corrects only superficial expression, classifies a closed task intent/requested outcome, and exposes ambiguity. It is a fixed pre-run workflow stage, not an Agent.

The immutable **Original User Task** remains the user's authority. A normalized reading and every admitted interpretation are **Additional Task Context**: derived, non-authoritative material that can never replace the original task, answer it, authorize a capability, narrow trusted dependencies, select a resource, or direct an effect.

Task Understanding owns:

- exact capture and integrity binding of the Original User Task;
- eligible continuity projection, protected-literal pre-scan, one structured proposal, deterministic validation/admission, actor-safe clarification, and raw-task fallback;
- one atomic Original-Task/decision Session control group after a decision that is eligible to persist.

It owns no Query Candidate, Resource Candidate, retrieval scope, investigation plan, capability need, Tool choice, Working Set operation, Case conclusion, provider selection, retry policy, Case mutation, publication, or Artifact. Those remain with the formal Investigation Agent Run and their owning deterministic seams.

## 2. Canonical primitives and bounds

All objects in this contract are closed: an unknown property, unknown discriminant, duplicate identifier, sparse array, non-finite number, or value outside its bound rejects the containing value. Optional properties are absent rather than `null`. Strings contain valid Unicode scalar values; no implicit Unicode normalization, trimming, case folding, or line-ending rewrite is allowed.

Every numeric field is a non-negative safe integer in `[0, Number.MAX_SAFE_INTEGER]` unless a smaller range is stated. UTF-16 offsets and lengths, decoded byte lengths, token counts, timestamps, timeout/cost values, generations, revisions, ordinals, and array positions all follow this rule. Negative zero, fractional values, numeric strings, and unsafe integers reject.

Every array has exact source order and rejects sparse positions. An array of scalar IDs, refs, digests, codes, slots, or alternatives rejects duplicates within that array. Object arrays reject duplicate primary keys: images by `ordinal`; continuity excerpts by both `excerptId` and `(sourceKind, sourceEntryId)`; continuity options by `priorTaskContextId`; corrections by `(startUtf16, endUtf16)`; proposed outcomes by `proposalOutcomeId`; ambiguities and uncertainties by `slot`; source claims by `claimId` and exact source span; admitted outcomes by `outcomeId` and `ordinal`; source bindings by `bindingId` and `bindingDigest`; bootstrap outcomes by `outcomeId` and `ordinal`; assumptions/exclusions by `code`; clarification questions by `questionId`, `reason`, and `slot`; and materialized entries by `entryId` and `ordinal`. The same admitted source binding may support different outcomes, but cannot repeat within one outcome's source list. Code never silently de-duplicates or reorders model output; the only permitted deterministic ordering steps are explicitly named below.

All fields named `*Digest` are `PiDigestV1`. Per the normative PNW canonical primitive, `piDigest(basis)` is exactly `"sha256:" + lowercaseHex(SHA-256(UTF8(RFC8785_JCS(basis))))`; UTF-8 has no BOM, prefix, delimiter, trailing newline, Unicode normalization, or alternate serialization. A digest must match `^sha256:[0-9a-f]{64}$`. This contract introduces no second canonicalizer.

Trusted runtime identifiers (`taskId`, `workspaceTurnId`, `taskRequestId`, `taskGenerationId`, `attemptId`, `sessionId`, `branchRef`, entry IDs, decision IDs, admitted outcome IDs, question IDs, and source-binding IDs) are minted outside the model, are 1-128 ASCII characters, and match `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`. Configuration identifiers (`instructionId`, `instructionVersion`, `modelRef`, `templateId`, `authenticatorId`, and `keyId`) are 1-128 ASCII characters and match `^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$`. Model-local identifiers (`claimId` and `proposalOutcomeId`) are 1-64 ASCII characters and match `^[a-z][a-z0-9_-]{0,63}$`. Currency is exactly three uppercase ASCII letters matching `^[A-Z]{3}$`; v1 treats it as an opaque configured billing currency and never performs exchange-rate conversion. Padded base64 and unpadded base64url fields use their named RFC 4648 alphabets and reject non-canonical encodings.

V1 applies each inclusive bound as soon as the bounded value exists and rechecks every retained value before its next trust-boundary crossing:

| Value | Bound |
|---|---:|
| Original task text | 1-4,096 UTF-16 code units and at most 16,384 UTF-8 bytes |
| Original images | at most 4 images, 262,144 bytes each, 524,288 aggregate decoded bytes |
| Canonical Original User Task and its complete A4 prior-entry draft | at most 1,048,576 UTF-8 bytes each under the shared Pi canonicalizer |
| Eligible continuity excerpts | at most 8 excerpts, 1,024 UTF-16 code units each, 8,192 aggregate |
| Task Understanding candidate JSON | 65,536 UTF-8 bytes; canonical depth at most 8; at most 2,048 aggregate object members and 2,048 aggregate array items |
| `normalizedReading` | at most 4,608 UTF-16 code units and 18,432 UTF-8 bytes |
| source claims | at most 64 |
| corrections | at most 32; replacement at most 256 UTF-16 code units; replacements at most 2,048 aggregate |
| ambiguities | at most 8 |
| alternatives per ambiguity | at most 5; each at most 256 UTF-16 code units; 1,024 aggregate per ambiguity |
| proposed/admitted outcomes | 1-4; objective at most 4,096 UTF-16 code units and 16,384 UTF-8 bytes; 4,096 UTF-16 and 16,384 UTF-8 aggregate |
| admitted source bindings | 1-64 |
| Investigation goal bootstrap | 1-4 outcome seeds; one seed per admitted outcome; canonical value at most 32,768 UTF-8 bytes |
| admitted assumptions, uncertainties, exclusions | at most 8 of each |
| clarification questions | 1-3; at most 5 admitted alternatives per question |
| invocation input/output tokens | at most 8,192 input and 8,192 output tokens |
| invocation timeout | 1-30,000 milliseconds |
| invocation cost bound | integer micros in `[0, 100000]` in configured billing currency |

Every at-limit value is valid when all aggregate bounds also hold, and every over-limit value fails closed. The production configuration may choose lower bounds, but the chosen values, currency, exact-counter identity, tokenizer/wrapper versions, and minimum-output-probe digest must be present in the trusted basis and may not change during an attempt. TU uses A3.2's `exact_required` budget request: only after A3.1 has detached the finalized logical provider input does the configured Pi counter count that exact input and separately count a minimum valid proposal containing the exact normalized-reading echo plus one outcome and its required source anchor. No character, byte-ratio, family-default, or caller-supplied estimate is admissible. `unsupported`, `unavailable`, `invalid`, identity/evidence/revalidation mismatch, input over limit, minimum output over limit, or candidate-byte over limit maps to exact `input_budget_exceeded` with zero Provider Adapter start and zero Task Understanding decision write. The 1,048,576-byte bounds are TU-owned application bounds: before Phase A, trusted TU code checks the canonical `OriginalUserTaskV1`; before Phase B, it rechecks that value and checks each complete A4 prior-entry draft that Phase B would submit. A4 remains a generic canonical/control implementation and is not used as TU's input validator.

## 3. Immutable Original User Task and continuity

```typescript
interface OriginalUserTaskV1 {
	protocol: "workspace-original-user-task/v1";
	taskId: string;
	text: string;
	textDigest: string;
	images: readonly OriginalUserTaskImageV1[];
	taskDigest: string;
}

interface OriginalUserTaskImageV1 {
	ordinal: number;
	mediaType: "image/png" | "image/jpeg" | "image/webp" | "image/gif";
	dataBase64: string;
	byteLength: number;
	contentDigest: string;
}

type EligibleTaskContinuityV1 =
	| {
			kind: "new_task";
			continuityDigest: string;
	  }
	| {
			kind: "continuation";
			mode: "explicit_continuation" | "clarification_answer";
			priorTaskContextId: string;
			priorDecisionDigest: string;
			branchRef: string;
			excerpts: readonly EligibleTaskContinuityExcerptV1[];
			continuityDigest: string;
	  };

interface EligibleTaskContinuityExcerptV1 {
	excerptId: string;
	sourceKind: "original_user_task" | "admitted_task_context" | "task_clarification";
	sourceEntryId: string;
	text: string;
	textDigest: string;
}

type TaskContinuityPreflightV1 =
	| {
			kind: "ready";
			continuity: EligibleTaskContinuityV1;
			preflightDigest: string;
	  }
	| {
			kind: "clarification_required";
			reason: "zero_eligible_referent" | "multiple_eligible_referents";
			actorVisibleOptions: readonly ActorVisibleContinuityOptionV1[];
			preflightDigest: string;
	  }
	| {
			kind: "failed";
			code: "continuity_ineligible" | "input_invalid";
			preflightDigest: string;
	  };

interface ActorVisibleContinuityOptionV1 {
	priorTaskContextId: string;
	label: string;
	labelDigest: string;
}
```

Image ordinals are unique, contiguous, and zero-based. `dataBase64` is canonical padded RFC 4648 base64 with no whitespace; decoding must yield exactly `byteLength` bytes. `contentDigest = piDigest({ protocol: "workspace-original-user-image-basis/v1", ordinal, mediaType, byteLength, dataBase64 })`. `textDigest = piDigest({ protocol: "workspace-original-user-task-text-basis/v1", text })`. `taskDigest = piDigest(the complete OriginalUserTaskV1 with taskDigest omitted)`. The same immutable record, including exact text and image bytes, is the source for persistence and PNW-C rendering; a reconstructed or re-encoded image is not equivalent.

V1 Task Understanding does not inspect image bytes. The model receives only each image's ordinal, media type, byte length, and `contentDigest`; image source claims are structurally inexpressible. An image remains available to the later Investigation context through the Original User Task. Task Understanding may classify intent from the text but may not invent an interpretation of image contents.

Trusted Workspace code constructs continuity from Session material already eligible for the same actor, purpose, Workspace, Session, branch, task continuity, and Context Generations. It never exposes unrestricted Session history. Excerpt IDs are trusted identifiers; text digests use `piDigest({ protocol: "workspace-task-continuity-excerpt-text-basis/v1", sourceKind, sourceEntryId, text })`. Each excerpt must correspond byte-for-byte to the eligible source entry. `continuityDigest = piDigest(the complete continuity variant with continuityDigest omitted)`.

`TaskContinuityPreflightV1` is constructed by trusted code before `TaskUnderstandingModule` may invoke a model. Its digest is `piDigest(the complete selected variant with preflightDigest omitted)`. An actor-visible option is present only when that exact prior Task Context is currently eligible for the same actor, purpose, Workspace, Session, branch, and Context Generations; labels contain 1-256 UTF-8 bytes, and `labelDigest = piDigest({ protocol: "workspace-continuity-option-label-basis/v1", priorTaskContextId, label })`. There are zero options for `zero_eligible_referent`. `multiple_eligible_referents` contains all 2-5 unique eligible options when they fit; if more than five exist, it contains zero options and reveals neither identities nor the hidden count while still asking the fixed continuity question.

Continuity selection is deterministic and produces exactly one preflight variant:

1. a standalone request with no continuity reference is `new_task`;
2. one explicit reference resolving to exactly one eligible prior decision is `explicit_continuation`;
3. an answer bound to exactly one current clarification is `clarification_answer`; the answer is still a new immutable Original User Task and never mutates the prior task;
4. a deictic continuation with zero or multiple eligible referents produces `clarification_required` before model dispatch;
5. an explicit foreign, unauthorized, stale-generation, wrong-branch, or otherwise ineligible reference produces `failed(continuity_ineligible)` before model dispatch without revealing whether a hidden referent exists;
6. a repeated excerpt ID, source mismatch, digest mismatch, missing prior decision, or over-limit projection produces `failed(input_invalid)` before model dispatch;
7. only `ready` contains `EligibleTaskContinuityV1` and may reach the invocation Port.

`clarification_required` maps to one preflight-bound clarification candidate with exactly one `continuity_reference_required` question. `zero_eligible_referent` yields no alternatives; `multiple_eligible_referents` yields the option labels in their trusted source order and no hidden count or omitted identity. `failed` maps to the same closed failure code and a preflight decision binding. Neither path calls the invocation Port. No later model result can replace a selected preflight terminal.

## 4. Deep Module and one-shot invocation seam

```typescript
interface TaskUnderstandingModule {
	understandAndCommit(input: PreInvestigationTaskInputV1): Promise<TaskUnderstandingDurableOutcomeV1>;
}

interface TaskUnderstandingInvocationPort {
	invoke(input: TaskUnderstandingInvocationV1): Promise<TaskUnderstandingInvocationOutcomeV1>;
}

interface PreInvestigationTaskInputV1 {
	originalTask: OriginalUserTaskV1;
	continuityPreflight: TaskContinuityPreflightV1;
	basis: TrustedTaskUnderstandingBasisV1;
	signal: AbortSignal;
}

interface TrustedTaskUnderstandingBasisV1 {
	protocol: "workspace-task-understanding-basis/v1";
	workspaceBindingDigest: string;
	sessionId: string;
	sessionRefBindingDigest: string;
	branchRef: string;
	expectedSessionLeafId: string | null;
	workspaceTurnId: string;
	taskRequestId: string;
	taskGenerationId: string;
	originalTaskDigest: string;
	continuityPreflightDigest: string;
	contextGenerationDigest: string;
	policyDigest: string;
	protectedLiteralPolicyDigest: string;
	instructionId: string;
	instructionVersion: string;
	instructionDigest: string;
	outputSchemaDigest: string;
	modelRef: string;
	exactCounterExpectation: TaskUnderstandingExactCounterExpectationV1;
	minimumOutputProbeDigest: string;
	inputTokenLimit: number;
	outputTokenLimit: number;
	timeoutMs: number;
	costLimitMicros: number;
	costCurrency: string;
	receiptAuthenticator: TaskUnderstandingAuthenticatorBindingV1;
	basisDigest: string;
}

interface TaskUnderstandingExactCounterExpectationV1 {
	protocol: "workspace-task-understanding-exact-counter-expectation/v1";
	counterId: string;
	counterVersion: string;
	tokenizerId: string;
	tokenizerVersion: string;
	wrapperPolicyId: string;
	wrapperPolicyVersion: string;
	expectationDigest: string;
}

interface TaskUnderstandingExactCounterConfigurationV1 {
	protocol: "workspace-task-understanding-exact-counter-configuration/v1";
	counterId: string;
	counterVersion: string;
	tokenizerId: string;
	tokenizerVersion: string;
	wrapperPolicyId: string;
	wrapperPolicyVersion: string;
}

interface TaskUnderstandingAuthenticatorBindingV1 {
	protocol: "workspace-task-understanding-authenticator-binding/v1";
	authenticatorId: string;
	algorithm: "hmac-sha256";
	keyId: string;
	policyRevision: number;
	verificationPolicyDigest: string;
	bindingDigest: string;
}

interface TaskUnderstandingInvocationV1 {
	protocol: "workspace-task-understanding-invocation/v1";
	attemptId: string;
	workspaceTurnId: string;
	taskRequestId: string;
	taskGenerationId: string;
	originalTask: TaskUnderstandingInvocationTaskV1;
	continuity: EligibleTaskContinuityV1;
	instructionId: string;
	instructionVersion: string;
	instructionDigest: string;
	outputSchemaDigest: string;
	modelRef: string;
	exactCounterExpectation: TaskUnderstandingExactCounterExpectationV1;
	minimumOutputProbeDigest: string;
	inputTokenLimit: number;
	outputTokenLimit: number;
	timeoutMs: number;
	costLimitMicros: number;
	costCurrency: string;
	basisDigest: string;
	invocationDigest: string;
	signal: AbortSignal;
}

interface TaskUnderstandingInvocationTaskV1 {
	taskId: string;
	text: string;
	textDigest: string;
	images: readonly TaskUnderstandingInvocationImageBindingV1[];
	taskDigest: string;
}

interface TaskUnderstandingInvocationImageBindingV1 {
	ordinal: number;
	mediaType: "image/png" | "image/jpeg" | "image/webp" | "image/gif";
	byteLength: number;
	contentDigest: string;
}
```

The basis is wholly trusted code, snapshots the current leased Session leaf, and is internally consistent: every duplicated identity/digest/budget equals the corresponding input/configuration value, and `continuityPreflightDigest` equals the selected preflight variant. `CaseWorkspaceModuleDependencies.taskUnderstandingExactCounter` is the sole Workspace configuration seam and carries exactly one snapshotted `TaskUnderstandingExactCounterConfigurationV1`; it carries no resolver, counter capability, Model, prepared value, auth value, secret, Adapter, Session, or callback. The six configuration identity/version fields are copied into `TaskUnderstandingExactCounterExpectationV1`; Workspace recomputes `expectationDigest = piDigest(the complete expectation with expectationDigest omitted)`. The dependency is source-optional only for the migration interval: absence selects the versioned identity `{ counterId: "workspace.task-understanding.exact-input", counterVersion: "v1", tokenizerId: "workspace.task-understanding.unconfigured", tokenizerVersion: "v1", wrapperPolicyId: "pi.prepared-simple", wrapperPolicyVersion: "v1" }`; because no counter is thereby registered, an unmatched/absent Pi resolver still fails closed as exact-count unsupported. Production activation requires an explicitly configured identity and a separately configured matching Pi resolver.

The expectation contains no `modelDigest` and is completely knowable before invocation: `modelRef` selects the configured application model, while the six identity/version fields select the configured counter/tokenizer/wrapper policy. A3.2 compares that identity byte-for-byte with the counter capability attached to the actual detached prepared Model, then computes the actual `modelDigest` and `counterBindingDigest` privately after `Models.prepareSimple`. No model-version field exists or is inferred. `receiptAuthenticator.bindingDigest = piDigest(the complete TaskUnderstandingAuthenticatorBindingV1 with bindingDigest omitted)`.

The minimum-output probe is one exact deterministic RFC 8785 JCS text, constructed transiently from the immutable invocation task and never retained in basis, evidence, receipt, or Session. Its complete object is `{ protocol: "workspace-task-understanding-proposal/v1", normalizedReading: originalTask.text, corrections: [], intent: { kind: "case_analysis", sourceClaimRefs: ["minimum_claim"] }, outcomes: [{ proposalOutcomeId: "minimum_outcome", requestedOutcome: "summary", objective: originalTask.text, sourceClaimRefs: ["minimum_claim"] }], ambiguities: [], sourceClaims: [{ claimId: "minimum_claim", kind: "original_task_text_span", startUtf16: 0, endUtf16: originalTask.text.length, textDigest: piDigest({ protocol: "workspace-task-source-span-basis/v1", sourceKind: "original_user_task", taskId: originalTask.taskId, startUtf16: 0, endUtf16: originalTask.text.length, text: originalTask.text }) }] }`. `candidateJsonText` is exactly the RFC 8785 JCS serialization of that object. `minimumOutputProbeDigest = piDigest({ protocol: "workspace-task-understanding-minimum-output-probe-basis/v1", candidateJsonText })`. The production invocation Adapter passes that transient text and digest to A3.2 and then drops the text. A3.2 returns only the digest and exact output count.

`basisDigest = piDigest(the complete TrustedTaskUnderstandingBasisV1 with basisDigest omitted)`. `invocationDigest = piDigest(the complete TaskUnderstandingInvocationV1 with invocationDigest and signal omitted)`. The model cannot supply or modify any basis or invocation field.

Only after a `ready` preflight, `understandAndCommit` copies its exact `continuity` into the invocation and calls `TaskUnderstandingInvocationPort.invoke` exactly once. The Port is the only model seam. Its production Adapter reuses the Pi-owned prepared-invocation and generic Provider Dispatch Implementation with an `exact_required` budget request whose expected counter binding and minimum-output-probe digest equal the invocation. Workspace never handles credentials, prepared secret-bearing values, counter capability, provider permits, or Adapter `start()`.

Preflight cancellation, invalid input, deterministic continuity clarification, and continuity/policy denial perform zero calls. Every other outcome performs one logical invocation and no retry, evaluator, repair, runtime model fallback, or second call.

No Task Understanding call creates an `AgentHarness`, creates or opens a `Session`, creates a second transcript, starts an Agent Run, registers Tools, enters compaction/branch-summary flow, or creates a steering/follow-up queue. Phase A is the decision-engine phase: it alone performs preflight and, when eligible, the single invocation; its input contains the immutable task, qualified continuity, trusted basis, and cancellation signal, but no Session, Harness, A4 capability, storage, or repository Interface. The shared Pi dispatcher may privately bind the already leased Session through its own accepted PNW protocol; that implementation detail is not exported to Phase A or the invocation Port.

### 4.1 Closed invocation outcomes

```typescript
interface TaskUnderstandingInvocationBindingBaseV1 {
	attemptId: string;
	invocationDigest: string;
	providerAttemptRef: string;
	decisionExpectedLeafId: string | null;
	startedAtMs: number;
	finishedAtMs: number;
	costCurrency: string;
}

interface TaskUnderstandingExactInputEvidenceV1 {
	protocol: "workspace-task-understanding-exact-input-evidence/v1";
	attemptId: string;
	invocationDigest: string;
	providerAttemptRef: string;
	modelRef: string;
	modelDigest: string;
	counterIdentity: {
		protocol: "pi-prepared-simple-exact-input-counter-identity/v1";
		counterId: string;
		counterVersion: string;
		tokenizerId: string;
		tokenizerVersion: string;
		wrapperPolicyId: string;
		wrapperPolicyVersion: string;
	};
	counterBindingDigest: string;
	logicalInvocationDigest: string;
	inputTokenCount: number;
	minimumOutput: {
		candidateTextDigest: string;
		outputTokenCount: number;
	};
	exactCountEvidenceDigest: string;
	budgetDigest: string;
	providerDispatchReceiptDigest: string;
	evidenceBindingDigest: string;
}

type TaskUnderstandingInvocationBindingV1 =
	| TaskUnderstandingNotDispatchedBindingV1
	| TaskUnderstandingStartedBindingV1
	| TaskUnderstandingDispatchAcknowledgementUnresolvedBindingV1;

type TaskUnderstandingNotDispatchedBindingV1 = TaskUnderstandingInvocationBindingBaseV1 & {
	dispatchState: "not_dispatched";
	charge: { kind: "known"; costMicros: 0; costCurrency: string };
};

type TaskUnderstandingStartedBindingV1 = TaskUnderstandingInvocationBindingBaseV1 & {
	dispatchState: "receipt_committed" | "receipt_exact_present";
	providerDispatchReceiptDigest: string;
	providerDispatchTerminalEntryId: string;
	exactInputEvidence: TaskUnderstandingExactInputEvidenceV1;
	charge: TaskUnderstandingStartedChargeV1;
};

type TaskUnderstandingDispatchAcknowledgementUnresolvedBindingV1 = TaskUnderstandingInvocationBindingBaseV1 & {
	dispatchState: "acknowledgement_unresolved";
	providerDispatchReceiptDigest: string;
	providerDispatchTerminalEntryId: string;
	charge: {
		kind: "unknown";
		costCurrency: string;
		reason: "dispatch_acknowledgement_unresolved";
	};
};

type TaskUnderstandingStartedChargeV1 =
	| { kind: "known"; costMicros: number; costCurrency: string }
	| {
			kind: "unknown";
			costCurrency: string;
			reason: "provider_usage_unavailable" | "provider_terminal_missing";
	  };

type TaskUnderstandingAttemptChargeV1 =
	| TaskUnderstandingStartedChargeV1
	| TaskUnderstandingDispatchAcknowledgementUnresolvedBindingV1["charge"];

interface TaskUnderstandingUsageV1 {
	inputTokens: number;
	outputTokens: number;
}

type TaskUnderstandingInvocationOutcomeV1 =
	| {
			kind: "completed";
			binding: TaskUnderstandingStartedBindingV1;
			candidateJsonText: string;
			candidateTextDigest: string;
			usage: TaskUnderstandingUsageV1;
	  }
	| {
			kind: "refused";
			binding: TaskUnderstandingStartedBindingV1;
			usage: TaskUnderstandingUsageV1;
	  }
	| {
			kind: "truncated";
			binding: TaskUnderstandingStartedBindingV1;
			usage: TaskUnderstandingUsageV1;
	  }
	| {
			kind: "malformed";
			binding: TaskUnderstandingStartedBindingV1;
			code: "multiple_candidates" | "non_text_candidate" | "extra_content" | "invalid_encoding" | "output_oversized";
			usage: TaskUnderstandingUsageV1;
	  }
	| {
			kind: "timed_out";
			binding: TaskUnderstandingStartedBindingV1;
	  }
	| {
			kind: "provider_failed";
			binding: TaskUnderstandingStartedBindingV1;
			code: "provider_error" | "provider_protocol_error";
	  }
	| {
			kind: "cancelled";
			binding: TaskUnderstandingNotDispatchedBindingV1 | TaskUnderstandingStartedBindingV1;
	  }
	| {
			kind: "failed";
			binding: TaskUnderstandingNotDispatchedBindingV1;
			code:
				| "input_budget_exceeded"
				| "dispatch_unavailable"
				| "unsupported_model"
				| "budget_unavailable"
				| "pre_dispatch_protocol_error";
	  }
	| {
			kind: "failed";
			binding: TaskUnderstandingDispatchAcknowledgementUnresolvedBindingV1;
			code: "dispatch_acknowledgement_unresolved";
	  };
```

Times satisfy `0 <= startedAtMs <= finishedAtMs`. Every binding's top-level `costCurrency`, charge currency, and invocation currency are byte-identical. `known.costMicros` does not exceed the bound. A started attempt may report only a known charge or unknown `provider_usage_unavailable|provider_terminal_missing`; acknowledgement-unresolved uses only its exact unknown reason. Unknown charge is retained in the candidate/receipt and permits no retry or second charged call. A currency mismatch is `attempt_identity_mismatch`. `candidateTextDigest = piDigest({ protocol: "workspace-task-understanding-candidate-text-basis/v1", candidateJsonText })`. `completed` carries exactly one untrusted JSON text candidate; it is not a typed or trusted proposal until the Module parses and validates it. The Adapter never returns provider prose, hidden reasoning, alternate choices, or deltas through a public Workspace event.

For a returned invocation outcome, `invocationOutcomeDigest = piDigest({ protocol: "workspace-task-understanding-invocation-outcome-basis/v1", outcome })`, where `outcome` is the complete closed `TaskUnderstandingInvocationOutcomeV1`. The Module computes it from its retained snapshot; neither the model nor Adapter supplies this digest.

Every started binding carries one `TaskUnderstandingExactInputEvidenceV1`, projected by the production invocation Adapter from A3.2's trusted started budget evidence. TU recomputes `evidenceBindingDigest` from the complete evidence with that field omitted and admits no semantics until all of the following hold: `attemptId`, `invocationDigest`, and `providerAttemptRef` equal the current invocation; `modelRef` equals the basis value; the six counter/tokenizer/wrapper identity/version fields equal `exactCounterExpectation` and reproduce its `expectationDigest`; `counterBindingDigest` recomputes from the returned actual `modelDigest` plus that exact identity; the logical invocation, exact-count evidence, final budget, and Provider Dispatch receipt bindings are internally identical; `candidateTextDigest` equals `minimumOutputProbeDigest`; both counts are safe integers within the basis limits; and `providerDispatchReceiptDigest` equals the started binding's trusted receipt digest. The actual `modelDigest` is outcome evidence, never an input expectation and never used to rewrite the already sealed TU basis or invocation. Any missing field or mismatch is `attempt_identity_mismatch`, appends no TU decision group, and is never fallback-eligible.

The type union makes dispatch state authoritative. This matrix is exhaustive; every unlisted pairing is `attempt_identity_mismatch`, appends no Task Understanding decision group, and is never fallback-eligible:

| Invocation outcome variant | Only legal `dispatchState` | Exact candidate/failure/retirement class |
|---|---|---|
| `completed` | `receipt_committed|receipt_exact_present` | validate the one candidate under section 6.3 |
| `refused|truncated|malformed` | `receipt_committed|receipt_exact_present` | deterministic fallback-or-integrity mapping under section 6.3 |
| `timed_out` | `receipt_committed|receipt_exact_present` | deterministic fallback or exact `provider_timeout` |
| `provider_failed` | `receipt_committed|receipt_exact_present` | deterministic fallback or exact `provider_failed` |
| `cancelled` | `not_dispatched|receipt_committed|receipt_exact_present` | lifecycle `cancelled`; no decision group |
| `failed(input_budget_exceeded)` | `not_dispatched` | exact `input_budget_exceeded`; never fallback |
| `failed(dispatch_unavailable|unsupported_model|budget_unavailable|pre_dispatch_protocol_error)` | `not_dispatched` | deterministic fallback or exact `dispatch_unavailable` |
| `failed(dispatch_acknowledgement_unresolved)` | `acknowledgement_unresolved` | exact `session_acknowledgement_unresolved`; no decision group |

Completed/refused/truncated/malformed/timeout/provider-failure therefore require a committed or exact-present dispatch receipt. A started outcome makes its exact post-dispatch Session leaf `decisionExpectedLeafId`; a not-dispatched outcome uses the unchanged basis leaf. Acknowledgement uncertainty can never be completed, timed out, provider-failed, cancelled, or fallback-eligible. Identity, generation, currency, dispatch receipt, or expected-leaf mismatch is `attempt_identity_mismatch` or `task_basis_changed`, never usable output. `completed` alone may admit model semantics. Any later provider callback after a terminal outcome is discarded and cannot change charge, candidate, Session state, or terminal kind.

## 5. Proposal schema and validation

```typescript
interface TaskUnderstandingProposalV1 {
	protocol: "workspace-task-understanding-proposal/v1";
	normalizedReading: string;
	corrections: readonly ProposedTaskCorrectionV1[];
	intent: ProposedTaskIntentV1;
	outcomes: readonly ProposedTaskOutcomeV1[];
	ambiguities: readonly ProposedTaskAmbiguityV1[];
	sourceClaims: readonly TaskUnderstandingSourceClaimV1[];
}

interface ProposedTaskCorrectionV1 {
	startUtf16: number;
	endUtf16: number;
	originalTextDigest: string;
	replacement: string;
	kind: "spelling" | "punctuation" | "grammar" | "language_normalization";
}

interface ProposedTaskIntentV1 {
	kind:
		| "orientation_question"
		| "case_analysis"
		| "continue_investigation"
		| "intelligence_need"
		| "case_change_request"
		| "external_publication_request"
		| "unclear";
	sourceClaimRefs: readonly string[];
}

interface ProposedTaskOutcomeV1 {
	proposalOutcomeId: string;
	requestedOutcome:
		| "explanation"
		| "summary"
		| "comparison"
		| "list"
		| "assessment"
		| "next_steps"
		| "change_request"
		| "publication_request"
		| "unspecified";
	objective: string;
	sourceClaimRefs: readonly string[];
}

interface ProposedTaskAmbiguityV1 {
	slot:
		| "subject"
		| "entity"
		| "time_scope"
		| "source_scope"
		| "requested_outcome"
		| "effect_intent"
		| "continuity_reference"
		| "success_criteria";
	materiality: "bounded" | "material";
	alternatives: readonly string[];
	sourceClaimRefs: readonly string[];
}

type TaskUnderstandingSourceClaimV1 =
	| {
			claimId: string;
			kind: "original_task_text_span";
			startUtf16: number;
			endUtf16: number;
			textDigest: string;
	  }
	| {
			claimId: string;
			kind: "continuity_excerpt_text_span";
			continuityExcerptId: string;
			startUtf16: number;
			endUtf16: number;
			textDigest: string;
	  };
```

Source spans are finite safe integers, non-empty, in range, and cannot split a UTF-16 surrogate pair. Claim and proposal-outcome IDs are unique. An original claim's digest is `piDigest({ protocol: "workspace-task-source-span-basis/v1", sourceKind: "original_user_task", taskId, startUtf16, endUtf16, text: exactSubstring })`; a continuity claim uses the same basis with `sourceKind: "eligible_continuity_excerpt"`, `excerptId`, and its exact substring. Every intent, outcome, and ambiguity has at least one unique valid `sourceClaimRef`; no ref may point to the wrong source kind or an absent excerpt. There are one through four outcomes in source order. Each objective is a concise restatement supported by all its source refs, introduces no entity/scope/effect/capability, and is not a subquestion, plan step, Query Candidate, or answer. The digest of an admitted claim is `piDigest(the complete validated TaskUnderstandingSourceClaimV1)`.

Corrections are strictly ascending by `(startUtf16, endUtf16)`, non-overlapping, in the Original User Task text, and cannot target continuity. A replacement differs byte-for-byte from its exact source span; no-op corrections reject. `originalTextDigest = piDigest({ protocol: "workspace-task-correction-source-basis/v1", startUtf16, endUtf16, text: exactOriginalSubstring })`. Starting with the exact original text, deterministic code applies replacements from the highest `startUtf16` to the lowest. The result must equal `normalizedReading` byte-for-byte. No other insertion, deletion, translation, semantic rewrite, Unicode normalization, trimming, case folding, whitespace rewrite, or punctuation rewrite is admitted. Corrections are empty if and only if `normalizedReading` equals the Original User Task text. Durable `normalizedReading` is absent exactly in that equal/empty case and otherwise is present with the exact validated value.

Ambiguities are unique by slot and appear in this canonical order: `subject`, `entity`, `time_scope`, `source_scope`, `requested_outcome`, `effect_intent`, `continuity_reference`, `success_criteria`. Alternatives retain model source order and are unique. Zero material ambiguities is required for admission. With one through three material slots, clarification asks all of them in canonical order. With four through eight, the same clarification asks the first three and records the remaining ordered slots in `remainingMaterialSlots`; no omitted slot is admitted as bounded uncertainty, and no Run starts. A clarification answer is a new task and may produce another clarification until no material slot remains.

Intent/outcome compatibility is exact:

| Intent | Admissible requested outcomes |
|---|---|
| `orientation_question` | `explanation`, `summary`, `comparison`, `list`, `unspecified` |
| `case_analysis` | `explanation`, `summary`, `comparison`, `list`, `next_steps`, `unspecified` |
| `continue_investigation` | `explanation`, `summary`, `comparison`, `list`, `next_steps`, `unspecified` |
| `intelligence_need` | `explanation`, `summary`, `comparison`, `list`, `next_steps`, `unspecified` |
| `unclear` | `unspecified` only |
| `case_change_request` | `change_request` only; always `task_class_unsupported` in this slice |
| `external_publication_request` | `publication_request` only; always `task_class_unsupported` in this slice |

`assessment` is always `task_class_unsupported` in this Workspace slice. A proposal has exactly one intent, and every outcome inherits that same intent; effect and read-only outcomes cannot be mixed. An absent allowed pair, a mixed intent, an effect outcome under a read-only intent, or an analysis outcome under an effect intent rejects model semantics and never falls back into permission. A valid read-only proposal deterministically maps to exactly one admitted intent and one-through-four compatible admitted outcomes.

Durable code/slot arrays are canonical subsequences of these orders: assumptions use `current_orientation_only`, `qualified_context_only`, `analysis_only`, `preserve_uncertainty`, `concise_explanation`; uncertainties use the ambiguity slot order above; exclusions use `no_external_sources`, `no_case_change`, `no_external_publication`, `no_dependency_narrowing`, `no_continuity_assumed`; issues use the declaration order in section 6.2. Duplicates or out-of-order members reject; deterministic code does not sort an already invalid model array. Trusted fallback construction emits the canonical order directly.

The deterministic, versioned protected-literal scanner inventories paths, URLs, hashes, IP addresses, domains, CVE identifiers, ATT&CK identifiers, versions, code spans, quoted text, and configured qualified CTI labels. Its version/configuration is bound by `protectedLiteralPolicyDigest`. A correction cannot overlap a protected span and the normalized reading must contain every protected byte sequence at the corresponding correction-adjusted position. V1 has no trusted-resolver exception: any mutation rejects the proposal.

The Task Understanding System Instruction is trusted, versioned configuration bound to the attempt. It requires exactly one closed proposal with one through four requested outcomes and forbids answering the task, decomposing outcomes into subquestions, Case-truth reasoning, plans, Query Candidates, capability/Tool/resource selection, retrieval, credentials, authorization/scope changes, effects, role/schema overrides in user data, and hidden reasoning. The model receives no Tool schemas, Working Set, I&E bodies, unrestricted history, credential material, or effect Interface. Prompt constraints are not authority; absent fields and deterministic validation are.

## 6. Deterministic outcomes and durable Additional Task Context

`understandAndCommit` is a private Workspace composition over two internal phases separated by an authority boundary; it is not one authority-bearing component. Phase A is the Session-free decision engine defined in section 4 and returns one private `TaskUnderstandingCandidateOutcomeV1`; it is not durable, cannot start a Run, cannot be handed to PNW-C, and cannot produce a public admission/clarification terminal. Phase B is a commit coordinator: it accepts only an admission or clarification candidate plus the retained trusted basis and the narrow existing-Session A4 capability defined in section 7, performs no model invocation, and returns one `TaskUnderstandingDurableOutcomeV1`. It receives no raw Session, Harness, storage, allocator, append, repository, or lease Interface. Only a `committed_*` outcome is authoritative evidence that the Original User Task and its paired decision are durable.

```typescript
type TaskUnderstandingCandidateOutcomeV1 =
	| { kind: "admission_candidate"; decision: "admitted"; binding: TaskUnderstandingDecisionBindingV1; context: AdmittedTaskContextV1 }
	| {
			kind: "admission_candidate";
			decision: "raw_task_fallback";
			binding: TaskUnderstandingDecisionBindingV1;
			context: AdmittedTaskContextV1;
			issues: readonly TaskUnderstandingIssueV1[];
	  }
	| {
			kind: "clarification_candidate";
			binding: TaskUnderstandingDecisionBindingV1;
			clarification: AdmittedTaskClarificationV1;
	  }
	| { kind: "failed"; binding: TaskUnderstandingDecisionBindingV1; code: TaskUnderstandingFailureCodeV1 }
	| {
			kind: "cancelled";
			binding: TaskUnderstandingDecisionBindingV1;
			reason: "caller_cancelled" | "workspace_closed";
	  }
	| {
			kind: "discarded";
			binding: TaskUnderstandingDecisionBindingV1;
			reason: "superseded" | "late_attempt" | "basis_stale";
	  };

type TaskUnderstandingDurableOutcomeV1 =
	| { kind: "committed_admitted"; handoff: CommittedTaskUnderstandingHandoffV1 }
	| { kind: "committed_raw_task_fallback"; handoff: CommittedTaskUnderstandingHandoffV1; issues: readonly TaskUnderstandingIssueV1[] }
	| {
			kind: "committed_clarification";
			binding: TaskUnderstandingDecisionBindingV1;
			clarification: AdmittedTaskClarificationV1;
			commit: TaskUnderstandingCommitEvidenceV1;
	  }
	| { kind: "failed"; binding: TaskUnderstandingDecisionBindingV1; code: TaskUnderstandingFailureCodeV1 }
	| {
			kind: "cancelled";
			binding: TaskUnderstandingDecisionBindingV1;
			reason: "caller_cancelled" | "workspace_closed";
	  }
	| {
			kind: "discarded";
			binding: TaskUnderstandingDecisionBindingV1;
			reason: "superseded" | "late_attempt" | "basis_stale";
	  };

type TaskUnderstandingDecisionBindingV1 =
	| {
			kind: "preflight";
			basisDigest: string;
			decisionExpectedLeafId: string | null;
	  }
	| {
			kind: "invoked";
			basisDigest: string;
			attemptId: string;
			invocationDigest: string;
			invocationOutcomeDigest: string;
			providerAttemptRef: string;
			decisionExpectedLeafId: string | null;
			providerDispatchReceiptDigest?: string;
			charge: TaskUnderstandingAttemptChargeV1;
	  };

interface TaskUnderstandingCommitEvidenceV1 {
	protocol: "workspace-task-understanding-commit-evidence/v1";
	resolution: "committed" | "exact_present";
	sessionId: string;
	expectedLeafId: string | null;
	orderedEntryIds: readonly [string, string, string];
	orderedEntryDigests: readonly [string, string, string];
	terminalEntryId: string;
	batchDigest: string;
	receiptDigest: string;
}

interface CommittedTaskUnderstandingHandoffV1 {
	protocol: "workspace-committed-task-understanding-handoff/v1";
	originalTask: OriginalUserTaskV1;
	additionalTaskContext: AdmittedTaskContextV1;
	goalBootstrap: InvestigationGoalBootstrapV1;
	decisionBinding: TaskUnderstandingDecisionBindingV1;
	commit: TaskUnderstandingCommitEvidenceV1;
	handoffDigest: string;
}

```

A zero-call preflight terminal uses only the `preflight` decision binding. Once `TaskUnderstandingInvocationPort.invoke` is called, every Phase-A and durable outcome, including semantic failure, timeout, cancellation, discard, A4 failure, clarification, and admission, uses the same `invoked` binding with its exact charge/currency; it can never fall back to a preflight binding or omit the attempt. The binding is retained through the terminal receipt or the non-committed failure result.

```typescript

interface AdmittedTaskContextV1 {
	protocol: "workspace-admitted-task-context/v1";
	taskContextId: string;
	originalTaskId: string;
	originalTaskDigest: string;
	continuity: AdmittedTaskContinuityV1;
	normalizedReading?: string;
	intent: AdmittedTaskIntentV1;
	outcomes: readonly AdmittedTaskOutcomeV1[];
	sourceBindings: AdmittedTaskSourceBindingCatalogV1;
	assumptions: readonly AdmittedTaskAssumptionV1[];
	uncertainties: readonly AdmittedTaskUncertaintyV1[];
	exclusions: readonly AdmittedTaskExclusionV1[];
	basisDigest: string;
	contextDigest: string;
}

type AdmittedTaskContinuityV1 =
	| { kind: "new_task"; continuityDigest: string }
	| {
			kind: "continuation";
			mode: "explicit_continuation" | "clarification_answer";
			priorTaskContextId: string;
			priorDecisionDigest: string;
			continuityDigest: string;
	  };

interface AdmittedTaskIntentV1 {
	kind: ProposedTaskIntentV1["kind"];
	sourceBindingDigests: readonly string[];
}

interface AdmittedTaskOutcomeV1 {
	outcomeId: string;
	ordinal: 0 | 1 | 2 | 3;
	intentKind: ProposedTaskIntentV1["kind"];
	requestedOutcome: ProposedTaskOutcomeV1["requestedOutcome"];
	objective: string;
	sourceBindingDigests: readonly string[];
	outcomeDigest: string;
}

interface AdmittedTaskSourceBindingCatalogV1 {
	protocol: "workspace-admitted-task-source-binding-catalog/v1";
	originalTaskId: string;
	bindings: readonly AdmittedTaskSourceBindingV1[];
	catalogDigest: string;
}

type AdmittedTaskSourceBindingV1 =
	| {
			bindingId: string;
			kind: "original_task_text_span";
			startUtf16: number;
			endUtf16: number;
			textDigest: string;
			bindingDigest: string;
	  }
	| {
			bindingId: string;
			kind: "continuity_excerpt_text_span";
			continuityExcerptId: string;
			startUtf16: number;
			endUtf16: number;
			textDigest: string;
			bindingDigest: string;
	  };

interface InvestigationGoalBootstrapV1 {
	protocol: "workspace-investigation-goal-bootstrap/v1";
	admittedTaskContextRef: string;
	admittedTaskContextDigest: string;
	outcomes: readonly InvestigationGoalBootstrapOutcomeV1[];
	bootstrapDigest: string;
}

interface InvestigationGoalBootstrapOutcomeV1 {
	outcomeId: string;
	outcomeDigest: string;
	ordinal: 0 | 1 | 2 | 3;
	intentKind: ProposedTaskIntentV1["kind"];
	requestedOutcome: ProposedTaskOutcomeV1["requestedOutcome"];
	objective: string;
	sourceBindingDigests: readonly string[];
}

interface AdmittedTaskAssumptionV1 {
	code:
		| "current_orientation_only"
		| "qualified_context_only"
		| "analysis_only"
		| "preserve_uncertainty"
		| "concise_explanation";
	slot: "time_scope" | "source_scope" | "effect_intent" | "requested_outcome";
	sourceBindingDigests: readonly string[];
}

interface AdmittedTaskUncertaintyV1 {
	slot: "time_scope" | "source_scope" | "requested_outcome" | "success_criteria";
	alternatives: readonly string[];
	sourceBindingDigests: readonly string[];
}

interface AdmittedTaskExclusionV1 {
	code:
		| "no_external_sources"
		| "no_case_change"
		| "no_external_publication"
		| "no_dependency_narrowing"
		| "no_continuity_assumed";
}
```

`AdmittedTaskIntentV1` deliberately does not retain proposal-local claim IDs. Deterministic admission converts each used validated source claim, in first-use source order, into one unique `AdmittedTaskSourceBindingV1`; `bindingDigest = piDigest(the complete binding with bindingDigest omitted)` and `catalogDigest = piDigest(the complete catalog with catalogDigest omitted)`. Every source-binding digest list is non-empty, unique, in catalog order, and resolves exactly once. No durable admitted field may refer directly to `claimId`.

There are one through four admitted outcomes, with trusted unique IDs and contiguous zero-based ordinals. Deterministic admission discards every model-local `proposalOutcomeId`; no durable value refers to it. Each admitted outcome repeats the one admitted intent kind, carries the exact validated requested outcome/objective/source-binding digests, and has `outcomeDigest = piDigest(the complete outcome with outcomeDigest omitted)`.

`contextDigest = piDigest(the complete AdmittedTaskContextV1 with contextDigest omitted)`. Only after that digest exists does trusted code construct `InvestigationGoalBootstrapV1`. It uses the shared Run protocol `workspace-investigation-goal-bootstrap/v1`, binds the exact Task Context ID/digest, and contains a one-to-one ordered copy of each admitted outcome's `outcomeId`, `outcomeDigest`, `intentKind`, `ordinal`, `requestedOutcome`, `objective`, and source-binding digests. `bootstrapDigest = piDigest(the complete bootstrap with bootstrapDigest omitted)`. TU does not mint a Run `goalId`, Run generation, goal status, or outcome catalog ref; Run Control creates its own Run-scoped goals only after verifying this bootstrap. The bootstrap contains no subquestion, edge, dependency, priority, Query Candidate, capability need, Tool, resource, budget, stop decision, or scheduling instruction, and therefore is not a DAG or planner. The continuity projection contains no unrestricted excerpt text.

Only a valid proposal with no material ambiguity may be `admitted`. A bounded ambiguity may become an explicit uncertainty only when it cannot change subject, entity, continuity, authorization/disclosure, effect intent, required source class, or success semantics. Unsupported `case_change_request` and `external_publication_request` are policy failures in this Workspace slice; their presence can never create permission.

Raw fallback is a canonical context, not a partially trusted proposal: `normalizedReading` is absent; intent is exactly `{ kind: "unclear", sourceBindingDigests: [fullTextBindingDigest] }`; there is exactly one admitted outcome `{ outcomeId: trustedOutcomeId, ordinal: 0, intentKind: "unclear", requestedOutcome: "unspecified", objective: exact original task text, sourceBindingDigests: [fullTextBindingDigest], outcomeDigest }`, and the shared goal bootstrap is its exact one-to-one projection. The per-outcome and aggregate objective bounds both equal the Original User Task text bound, so the at-limit fallback remains representable. No model-produced assumption, uncertainty, exclusion, or wording survives. Trusted code adds only applicable closed assumptions/exclusions and actor-safe issue codes. Fallback preserves the exact Original User Task for the Investigation Agent.

The fallback full-text binding has kind `original_task_text_span`, the exact full range and text digest, a trusted binding ID, and `bindingDigest = piDigest(the complete binding with bindingDigest omitted)`; it is not copied from a rejected proposal.

### 6.1 Clarification schema

```typescript
type AdmittedTaskClarificationV1 = AdmittedTaskClarificationCoreV1 &
	(
		| { source: "preflight" }
		| {
				source: "invoked";
				attemptId: string;
				invocationDigest: string;
				invocationOutcomeDigest: string;
		  }
	);

interface AdmittedTaskClarificationCoreV1 {
	protocol: "workspace-task-clarification/v1";
	clarificationId: string;
	taskContextId: string;
	originalTaskId: string;
	originalTaskDigest: string;
	continuityPreflightDigest: string;
	sourceBindings: AdmittedTaskSourceBindingCatalogV1;
	questions: readonly AdmittedTaskClarificationQuestionV1[];
	remainingMaterialSlots: readonly ProposedTaskAmbiguityV1["slot"][];
	basisDigest: string;
	clarificationDigest: string;
}

interface AdmittedTaskClarificationQuestionV1 {
	questionId: string;
	reason:
		| "subject_required"
		| "entity_required"
		| "time_scope_required"
		| "source_scope_required"
		| "outcome_required"
		| "effect_intent_required"
		| "continuity_reference_required"
		| "success_criteria_required";
	slot:
		| "subject"
		| "entity"
		| "time_scope"
		| "source_scope"
		| "requested_outcome"
		| "effect_intent"
		| "continuity_reference"
		| "success_criteria";
	templateId: string;
	text: string;
	alternatives: readonly string[];
	sourceBindingDigests: readonly string[];
}
```

`reason` has one fixed matching `slot` and trusted template:

| Reason | Exact `templateId` | Exact English template |
|---|---|---|
| `subject_required` | `workspace.clarification.subject_required.en/v1` | `What should the investigation focus on?` |
| `entity_required` | `workspace.clarification.entity_required.en/v1` | `Which entity should the investigation examine?` |
| `time_scope_required` | `workspace.clarification.time_scope_required.en/v1` | `What time range should the investigation use?` |
| `source_scope_required` | `workspace.clarification.source_scope_required.en/v1` | `Which source scope should the investigation use?` |
| `outcome_required` | `workspace.clarification.outcome_required.en/v1` | `What result should the investigation produce?` |
| `effect_intent_required` | `workspace.clarification.effect_intent_required.en/v1` | `Are you asking for analysis only, or for an external change?` |
| `continuity_reference_required` | `workspace.clarification.continuity_reference_required.en/v1` | `Which prior investigation should this request continue?` |
| `success_criteria_required` | `workspace.clarification.success_criteria_required.en/v1` | `What would count as a sufficient answer?` |

`templateId` is the trusted catalog ID/version for that exact text. A localized product may render a separately versioned trusted catalog, but the selected catalog digest belongs in `policyDigest`. Alternatives are either exact actor-visible source quotations or fixed trusted vocabulary; free model alternative prose is never published. Questions are ordered by the slot order in the table, have unique IDs, and are never generated from provider prose. Every question source-binding digest resolves in the clarification catalog. `remainingMaterialSlots` is the exact canonical suffix after the first three material question slots and is empty otherwise; it is durable control context, not public model prose. A continuity preflight question may use the exact full-original-task binding when no narrower safe source span exists; it never exposes an ineligible prior-task binding and has no remaining material slot. `clarificationDigest = piDigest(the complete AdmittedTaskClarificationV1 with clarificationDigest omitted)`. `source: "preflight"` has no attempt fields; `source: "invoked"` requires all three attempt/outcome fields and they exactly match the invoked decision binding.

Clarification commits and emits one terminal; it starts no Agent Run. A response is a new task linked through `clarification_answer` continuity.

### 6.2 Actor-safe issues and failures

```typescript
type TaskUnderstandingIssueV1 =
	| "schema_invalid"
	| "unknown_member"
	| "proposal_oversized"
	| "source_claim_invalid"
	| "correction_invalid"
	| "normalized_reading_mismatch"
	| "protected_literal_changed"
	| "forbidden_semantics"
	| "model_refused"
	| "model_truncated"
	| "model_timeout"
	| "provider_failed";

type TaskUnderstandingFailureCodeV1 =
	| "input_invalid"
	| "input_budget_exceeded"
	| "continuity_ineligible"
	| "task_class_unsupported"
	| "policy_unavailable"
	| "dispatch_unavailable"
	| "provider_failed"
	| "provider_timeout"
	| "task_basis_changed"
	| "attempt_identity_mismatch"
	| "authenticator_basis_changed"
	| "admission_integrity_failure"
	| "session_control_unavailable"
	| "session_commit_conflict"
	| "session_acknowledgement_resolved_absent"
	| "session_acknowledgement_unresolved";
```

Issues and public failures contain no candidate text, provider error body, secret, foreign identity, protected literal, hidden policy detail, or authorization explanation. Cancellation, close, supersession, and late retirement use their lifecycle terminal and do not masquerade as semantic failure.

### 6.3 Closed admission and fallback matrix

Trusted pre-scan marks a task `fallback_eligible` only when all are true: standalone `new_task`; syntactically valid and in bounds; analysis/read-only class; no deictic reference; no Case change, external publication, authorization/disclosure, source-scope, effect-intent, continuity, subject/entity, or success-criteria ambiguity; and a full-original-text source claim can be constructed deterministically.

| Input or invocation result | Deterministic outcome |
|---|---|
| valid minimal proposal; every check passes; no material ambiguity | one `admission_candidate(admitted)` |
| material ambiguity with a trusted template | one `clarification_candidate` |
| unsupported Case-change/publication class | `failed(task_class_unsupported)`; never fallback |
| completed candidate is malformed/oversized/unanchored/forbidden/protected-literal-mutating, or invocation is `refused|truncated|malformed` | one `admission_candidate(raw_task_fallback)` if and only if pre-scan marked `fallback_eligible`; otherwise one trusted clarification candidate if and only if deterministic pre-scan selected an applicable material-ambiguity template, else exact `failed(admission_integrity_failure)` |
| invocation is `timed_out` | one `admission_candidate(raw_task_fallback)` if and only if pre-scan marked `fallback_eligible`; otherwise exact `failed(provider_timeout)` |
| invocation is `provider_failed(provider_error|provider_protocol_error)` | one `admission_candidate(raw_task_fallback)` if and only if pre-scan marked `fallback_eligible`; otherwise exact `failed(provider_failed)` |
| invocation is pre-dispatch `failed(input_budget_exceeded)` | exact `failed(input_budget_exceeded)`; never fallback and zero Provider Adapter start |
| invocation is pre-dispatch `failed(dispatch_unavailable|unsupported_model|budget_unavailable|pre_dispatch_protocol_error)` | one `admission_candidate(raw_task_fallback)` if and only if pre-scan marked `fallback_eligible`; otherwise exact `failed(dispatch_unavailable)` |
| input/schema/bound failure before invocation | exact `input_invalid` or `input_budget_exceeded`; zero invocation |
| explicit ineligible continuity | `continuity_ineligible`; zero invocation |
| deictic zero/multiple continuity referents | deterministic clarification; zero invocation |
| cancellation or Workspace close | `cancelled`; no decision control group; late result ignored |
| supersession or retired late attempt | `discarded`; no decision control group; late result ignored |
| basis/generation/attempt/dispatch identity mismatch | append none; exact `discarded(basis_stale)` or failure code; never fallback |
| provider-dispatch acknowledgement unresolved | exact `failed(session_acknowledgement_unresolved)`; no decision group and no provider start |

No row permits a second model call, autonomous retry, model-selected fallback, or partial admission.

One settle-once transition owns `(workspaceTurnId, taskRequestId, taskGenerationId)`. Its only legal graph is:

```text
preflight
  -> failed | cancelled | discarded
  -> clarification_candidate -> A4 commit -> committed_clarification
  -> ready -> exactly one invocation -> exactly one candidate outcome
       -> failed | cancelled | discarded
       -> admission_candidate -> A4 commit -> committed_admitted | committed_raw_task_fallback
       -> clarification_candidate -> A4 commit -> committed_clarification
```

An admission candidate and clarification candidate can never both exist for one transition. Material ambiguity is evaluated before bounded uncertainty/admission. The first winning cancellation, close, supersession, basis retirement, or A4 commit claim retires every competing transition. Before A4 commit, cancellation/retirement appends no decision group. After `committed` or `exact_present`, the durable outcome cannot be changed to clarification, admission, failure, cancellation, or discard; the surrounding lifecycle may still cancel before starting the Run without erasing the committed record. Duplicate/late callbacks cannot create another candidate, commit, event, or call.

## 7. Atomic Session control group

An admitted, fallback, or clarification decision is durable only after one PNW-A4 receipt-last control group commits to the already leased Workspace Session. Phase A and the invocation Port receive no Session or A4 Interface. Runtime composition gives only the Phase-B commit coordinator an object exposing exactly the existing Pi `prepareControlBatch` and `lookupControlBatch` operations, already bound to that leased Session. The object exposes no Session handle and cannot open, create, select, or lease a Session. Neither phase receives storage, allocator, raw-entry append, repository, lease, or Harness authority. The 1,048,576-byte canonical Original-Task check before Phase A, and its recheck plus each complete-prior-entry-draft check before Phase B, remain TU-owned; A4 does not validate or define those application bounds.

The group contains exactly three entries in this order:

1. one prior `custom` entry with `customType = "workspace_original_user_task_v1"` and exact `OriginalUserTaskV1` data;
2. one prior `custom` entry with `customType = "workspace_admitted_task_context_v1"` and exact `AdmittedTaskContextV1`, or `customType = "workspace_task_clarification_v1"` and exact `AdmittedTaskClarificationV1`;
3. the physically last terminal `custom` entry with `customType = "workspace_task_understanding_commit_v1"` and exact `TaskUnderstandingCommitReceiptV1` data.

```typescript
interface TaskUnderstandingCommitReceiptV1 {
	protocol: "workspace-task-understanding-commit-receipt/v1";
	decision: "admitted" | "raw_task_fallback" | "clarification_required";
	workspaceTurnId: string;
	taskRequestId: string;
	taskGenerationId: string;
	sessionId: string;
	branchRef: string;
	expectedLeafId: string | null;
	basisDigest: string;
	attemptId?: string;
	invocationDigest?: string;
	invocationOutcomeDigest?: string;
	providerAttemptRef?: string;
	providerDispatchReceiptDigest?: string;
	attemptCharge?: TaskUnderstandingAttemptChargeV1;
	originalTaskId: string;
	originalTaskDigest: string;
	decisionId: string;
	decisionDigest: string;
	goalBootstrapDigest?: string;
	authenticatorBindingDigest: string;
	materializedPriorEntries: readonly TaskUnderstandingMaterializedEntryBindingV1[];
	terminalEntryId: string;
	receiptDigest: string;
	authenticity: TaskUnderstandingReceiptAuthenticityV1;
}

interface TaskUnderstandingMaterializedEntryBindingV1 {
	ordinal: 0 | 1;
	entryId: string;
	parentId: string | null;
	customType: "workspace_original_user_task_v1" | "workspace_admitted_task_context_v1" | "workspace_task_clarification_v1";
	entryDigest: string;
}

interface TaskUnderstandingReceiptAuthenticityV1 {
	protocol: "workspace-task-understanding-receipt-authenticity/v1";
	authenticatorId: string;
	algorithm: "hmac-sha256";
	keyId: string;
	policyRevision: number;
	verificationPolicyDigest: string;
	authenticatorBindingDigest: string;
	signedPayloadDigest: string;
	macBase64Url: string;
}
```

The materialized list is exactly two entries with ordinals `[0, 1]`; ordinal 0 is the original task and ordinal 1 is the decision. `decisionId`/`decisionDigest` are the admitted context ID/digest or clarification ID/digest. `goalBootstrapDigest` is present and exact only for admitted/fallback decisions and absent for clarification; the full bootstrap is deterministically reconstructable from the committed admitted outcomes and is returned in the committed handoff. The expected leaf is exactly the selected `TaskUnderstandingDecisionBindingV1.decisionExpectedLeafId`; a `preflight` binding uses the basis leaf. Attempt/provider receipt/charge fields are all absent for `preflight`. For `invoked`, attempt/outcome/charge fields are all present, while `providerDispatchReceiptDigest` is present only for `receipt_committed`/`receipt_exact_present` dispatch.

Each `entryDigest` is the generic A4 `piDigest({ protocol: "pi-session-entry-digest-basis/v1", entry: completeMaterializedEntry })`. `receiptDigest = piDigest(the complete TaskUnderstandingCommitReceiptV1 with receiptDigest and authenticity omitted)`. `signedPayloadDigest = piDigest(the complete receipt with authenticity omitted)`. `macBase64Url` is the exact 43-character unpadded base64url encoding of HMAC-SHA-256 over the exact UTF-8 RFC 8785 JCS bytes of that same payload. Receipt authenticator fields and `authenticatorBindingDigest` must equal the basis binding exactly. A4 owns final IDs, timestamps, parent chain, generic batch digest, sealing, CAS append, and exact lookup; Workspace cannot override them.

The Module snapshots the authenticator binding at basis creation, compares it again after A4 preview and immediately before seal and commit, and verifies the produced MAC under that exact binding before seal. Any ID, key, algorithm, policy revision, verification policy, or binding-digest drift abandons the prepared/sealed batch, appends none, and returns `authenticator_basis_changed`. Reopen verification may use a retained verifier for that exact historic key binding, but a current configuration must never reinterpret a receipt under a different binding.

The exact A4 mapping is closed:

| A4 phase/result | Task Understanding result and work |
|---|---|
| prepare `unsupported` | `failed(session_control_unavailable)`; zero reservation/append/event |
| prepare `unavailable(io|invalid_or_truncated|unsupported)` | `failed(session_control_unavailable)`; zero reservation/append/event and no use of cached state |
| prepare `conflict` | `failed(session_commit_conflict)`; zero reservation/append/event |
| prepare `invalid_draft` | `failed(admission_integrity_failure)`; zero reservation/append/event |
| prepared preview has wrong Session, expected leaf, order, custom type, parent chain, reserved terminal, or materialized prior data | `abandon`; `failed(admission_integrity_failure)`; zero append |
| candidate/basis/generation/cancellation/authenticator changes after preview | `abandon`; exact failed/cancelled/discarded outcome; zero append |
| `sealTerminal` returns `invalid_terminal` | `failed(admission_integrity_failure)`; preparation is terminal and appends zero |
| sealed evidence differs from preview, receipt, ordered IDs/digests, terminal-last rule, or recomputed batch digest | `abandon`; `failed(admission_integrity_failure)`; zero append |
| pre-commit basis/cancellation/authenticator check changes | sealed `abandon`; exact failed/cancelled/discarded outcome; zero append |
| commit `committed` with identical evidence | durable `TaskUnderstandingCommitEvidenceV1.resolution = "committed"` |
| commit `conflict` | `failed(session_commit_conflict)`; A4 appended no group prefix |
| commit `acknowledgement_unknown` | perform exactly one `lookupControlBatch(the same evidence)`; never recommit, reseal, or rematerialize |
| lookup `exact_present` with the same terminal ID | durable evidence with `resolution = "exact_present"` |
| lookup `absent` | `failed(session_acknowledgement_resolved_absent)`; no retry or replacement group |
| lookup `conflict` | `failed(session_acknowledgement_unresolved)`; quarantine this decision identity |
| lookup `unavailable(io|invalid_or_truncated|unsupported)` | `failed(session_acknowledgement_unresolved)`; no cached-state inference |

Only `committed` and `exact_present` construct `TaskUnderstandingCommitEvidenceV1` and a `committed_*` outcome. Its Session ID, expected leaf, ordered three IDs/digests, terminal ID, and batch digest are copied from the exact immutable A4 evidence; its receipt digest is recomputed from the sealed terminal data. A duplicate request with the same request identity and exact decision/receipt/batch digests may return the exact durable outcome after lookup; the same identity with any different field is `admission_integrity_failure` and appends none. Raw proposal text, provider completion/deltas, rejected normalization, model reasoning, and provider error bodies are never persisted or eligible history.

The provider-dispatch receipt group, when present, is a separate earlier PNW group. Its entries are not silently folded into this three-entry decision group. Failure/cancellation/discard may therefore leave an already valid provider-dispatch receipt, but never a partial Task Understanding decision group.

## 8. Handoff to PNW-C, not ownership of initial context

After an admitted/fallback decision commits, Task Understanding constructs exactly one `CommittedTaskUnderstandingHandoffV1`. `handoffDigest = piDigest(the complete handoff with handoffDigest omitted)`. PNW-C and Run Control accept no Phase-A candidate or uncommitted context. The handoff contains:

1. the exact immutable `OriginalUserTaskV1`;
2. the exact canonical `AdmittedTaskContextV1` as non-authoritative Additional Task Context;
3. its exact shared `InvestigationGoalBootstrapV1`; and
4. exact committed/exact-present A4 evidence.

PNW-C consumes only items 1 and 2 for initial-context compilation. Run Control may consume item 3 only as its initial one-through-four outcome seeds. After verifying `bootstrapDigest`, `admittedTaskContextRef`, `admittedTaskContextDigest`, and the exact ordered one-to-one equality of `outcomeId`, `outcomeDigest`, `ordinal`, `intentKind`, `requestedOutcome`, `objective`, and `sourceBindingDigests`, Run Control mints its own Run-generation goal IDs and independently owns subquestions, Query Candidates, capability admission, budgets, local adjustment, and stop semantics. Both consumers verify item 4 and the handoff digest first. Task Understanding defines no `InitialInvestigationContextV1`, provider message layout, Working Set snapshot, Orientation/Projection layering, eligible-history projection, Tool activation, or seven-section renderer. Those concrete types, dependency qualification, channel mapping, rendering, and acceptance cases are owned by [`workspace-initial-investigation-context/v1`](initial-investigation-context-v1-contract.md). That contract preserves Original User Task user-message identity and images, places Additional Task Context in a separate trusted derived-context position, and prevents the latter from replacing or authorizing the former.

No Query Candidate or Working Set entry is produced here. A TU design or focused implementation PASS proves only this handoff data and ordering preconditions. It cannot claim seven-section initial-context, Harness, Agent Run, save-point, settlement, publication, or end-to-end integrated PASS.

## 9. Public terminal and event catalog

Task Understanding emits no public model delta, proposal, provider completion, issue detail, or intermediate semantic event. Public Workspace sequencing remains PNW-owned and starts with `turn_started`.

| TU result | Public behavior |
|---|---|
| admitted/fallback and control group durable | no TU terminal; only then may context compilation and the Investigation Agent Run begin |
| clarification durable | exactly `turn_clarification_required`, then `result.status = "clarification_required"`; exact deterministic questions only |
| failed before/during admission | exactly `turn_failed`, then `result.status = "failed"` with an actor-safe mapped failure |
| caller cancellation or close | exactly `turn_cancelled`, then `result.status = "cancelled"` |
| superseded/late/basis-stale retirement | exactly `turn_discarded`, then `result.status = "discarded"` |

Every public Turn has exactly one terminal event; `result` resolves once and never rejects. Clarification/failure/cancellation/discard starts no Agent Run and emits no `context_bound`, `model_started`, Tool, save-point, settlement, or publication event. After cancellation, close, supersession, or terminal decision, late provider output and raw deltas are fenced from public sinks and persistence.

## 10. Failure and concurrency matrix

| Scenario | Deterministic result |
|---|---|
| protected literal changed | reject proposal; never repair the repair |
| material ambiguity | trusted clarification terminal; no Agent Run |
| duplicate same request/exact decision | exact lookup may return the existing durable decision |
| same request identity/different digest | integrity failure; append none |
| continuity, generation, Session leaf, or basis changes | stale; append none and do not start the Run |
| cancellation races model completion before decision commit | cancellation retires the attempt; append none; late completion ignored |
| decision commit wins before later cancellation | exact committed decision remains durable; lifecycle may cancel before Run start, but cannot erase/rewrite it |
| crash after model result before decision commit | no admitted state; proposal is discardable |
| commit acknowledgement unknown | one authoritative exact lookup; no guessed replay |
| dispatch acknowledgement unresolved | no provider start and no decision persistence |
| close/supersession after terminal | terminal is immutable; later output ignored |
| raw model delta before formal publication | never exposed to an ordinary Workspace caller |

## 11. Model and cost policy

V1 uses one configured off-the-shelf model invocation with strict structured output. Fine-tuning is not required. Model, instruction, schema, token, latency, currency, and cost bounds are trusted configuration and are all basis-bound. If a small model fails conformance fixtures, configuration may choose a more capable model for a future attempt; the active attempt never falls back to another model or adds a self-correction call.

Splitting correction and understanding into a prompt chain, adding a resolver model, or adding retry/evaluator behavior requires a new contract version. Direct `Models.completeSimple()` is not production acceptance; production must use the independently accepted shared Pi dispatcher frontend.

## 12. Acceptance catalog

- **TU-01:** public behavior starts only through `CaseWorkspaceModule -> CaseWorkspace.prompt -> WorkspaceTurn`; no public planning or Task Understanding Interface is added.
- **TU-02:** every model-eligible task performs exactly one bounded Task Understanding invocation before any Harness prompt, Agent Run, Tool event, Working Set action, or investigation provider request; preflight terminal cases perform zero.
- **TU-03:** no planner Harness, Session, transcript, Tool loop, queue, compaction, branch summary, retry loop, provider client, or second Agent is created.
- **TU-04:** Original User Task text and exact decoded image bytes retain their digests through admission, clarification, fallback, reopen, and PNW-C handoff; Task Understanding never reconstructs image bytes.
- **TU-05:** every admitted correction, intent, and one-through-four outcome is source-anchored through the durable source-binding catalog; corrections are non-noop, deterministically reproduce the exact normalized reading, durable normalized-reading presence follows its exact empty-correction rule, and protected CTI literals survive exactly or the proposal is rejected.
- **TU-06:** malformed, refused, truncated, oversized, unanchored, late, cancelled, timed-out, stale-basis, prompt-injection, role-override, and schema-override outputs admit no model semantics.
- **TU-07:** Query Candidate, capability need, Tool, retrieval, Working Set, investigation plan, provider, credential, retry, permission, and effect fields are structurally inexpressible.
- **TU-08:** deterministic policy alone chooses admit, fallback, clarification, failure, cancellation, or discard; confidence/model requests cannot force a decision.
- **TU-09:** the settle-once state machine chooses exactly one admission or clarification candidate; zero material slots is required for admission, one-through-three asks all in canonical order, and four-through-eight asks the first three while durably retaining the exact ordered suffix; every clarification emits only trusted actor-safe questions and starts no Agent Run.
- **TU-10:** admitted/fallback original task and Additional Task Context, or original task and clarification, commit atomically to the existing Session with receipt last; every A4 prepare/preview/seal/commit/lookup result follows section 7, conflict appends none, and unknown acknowledgement performs one exact lookup.
- **TU-11:** raw proposal/provider data and rejected normalization are absent from public events, persisted entries, eligible Session history, and PNW-C inputs.
- **TU-12:** continuity preflight returns exactly ready, clarification, or failure; only ready is bounded and actor/purpose/branch/generation qualified for invocation, while invalid, foreign, stale, ambiguous, and clarification-answer references follow the exact closed rules.
- **TU-13:** a deterministic fake and production-shaped invocation Adapter pass identical semantic fixtures and exact call-count/event-count assertions without paid credentials.
- **TU-14:** fixtures cover spelling, multilingual awkwardness, CVE/ATT&CK/hash/domain/IP/version/path/code/quoted-text preservation, aliases, pronouns, new/explicit/invalid/ambiguous/clarification continuity, scope/effect ambiguity, prompt/role/schema injection, forbidden answer/plan/Tool attempts, malformed JSON, refusal, truncation, timeout, cancellation, close, supersession, late output, stale basis, raw fallback, control conflict, and acknowledgement unknown.
- **TU-15:** public probes inspect actual Session entries/digests, committed/exact-present evidence, final PNW-C handoff values, and the shared one-through-four outcome bootstrap with exact outcome/context digests; they prove TU minted no Run goal ID and also inspect event/result order, terminal count, provider-call count, and absence of investigation events. Phase-A candidates, internal reducer state, and test names are not acceptance evidence.
- **TU-16:** TU design PASS, focused implementation/public-seam PASS, PNW-C integration PASS, and full integrated PASS are reported separately; none implies another.
- **TU-17:** every post-invocation result retains one exact attempt/dispatch/charge/currency binding; each invocation outcome accepts only its section-4.1 dispatch state, timeout and provider failure retain their distinct exact failure codes when fallback is ineligible, and unknown charge never causes retry or a second call.
- **TU-18:** authenticator binding is basis-bound and revalidated at preview, seal, and pre-commit; drift appends none, while reopen verifies the exact historic binding.
- **TU-19:** every numeric field rejects negative zero, fractions, strings, unsafe integers, and over-bound values; every array rejects sparse positions and the exact duplicate identities defined in section 2, with no silent sort or de-duplication.
- **TU-20:** every admitted intent/outcome pair follows the closed compatibility table; effect/read-only mixing, unsupported classes, and invalid pairs admit no model semantics and create no permission.
- **TU-21:** Phase A has no Session, Harness, or A4 capability; Phase B receives only the already-bound two-operation A4 capability and performs no model call. TU itself checks the 1,048,576-byte canonical Original Task before Phase A, then rechecks it and each complete prior-entry draft before Phase B.
- **TU-22:** the public Workspace seam exercises deterministic fake and production-shaped local counters through the same A3.2 fixtures. A tokenizer-vs-character discrepancy proves no character heuristic; exact input and separately counted minimum output pass at limit and fail one token over. `unsupported|unavailable|invalid|stale|unknown`, wrong complete model basis, wrong counter/tokenizer/wrapper identity or version, stale evidence, and post-prepare mutation all yield exact `input_budget_exceeded`, zero Provider Adapter start, and zero Task Understanding decision write. Changing only a counter, tokenizer, or wrapper-policy identity/version changes the TU pre-bound expectation and A3.2 logical invocation digest. The TU basis/invocation retain only `modelRef`, the counter/tokenizer/wrapper expectation, and minimum-output-probe digest; the started invocation outcome returns the actual model/counter/count/logical/budget/receipt evidence, which TU validates before semantic admission without rewriting its basis. The provider receipt's budget digest binds the same actual evidence without retaining the probe text.

## 13. Gates and deferred work

The exact-input-count amendment and generic Pi seam have Design PASS and focused Pi implementation/public-seam PASS. Workspace production implementation now requires the frozen public Workspace acceptance matrix below; the exact PNW-C handoff/control-group mapping remains a separate integration gate. This authorizes deterministic fake/local-counter Workspace TDD but does not authorize real-provider counter registration or activation.

Query Candidate generation, run control/capability planning, Working Set, I&E retrieval, bounded search, Assessment, Case writes, Artifact persistence, output publication, real-provider counter registration, and real-provider activation remain outside this contract.
