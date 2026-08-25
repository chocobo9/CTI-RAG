import type { ExecutionEnv, ProviderDispatchSecretBinder, Session } from "@earendil-works/pi-agent-core";
import type { AssistantMessage, ImageContent, Model, Models } from "@earendil-works/pi-ai";

export interface AccessPrincipalBinding {
	principalRef: string;
	credentialRef: string;
}

export type WorkspaceSessionRef = Session;

export interface SessionReceiptAuthenticatorBinding {
	authenticatorId: string;
	algorithm: "hmac-sha256";
	keyId: string;
	policyRevision: number;
	verificationPolicyDigest: string;
}

export interface SessionReceiptAuthenticator {
	readonly authenticatorId: string;
	readonly binding: SessionReceiptAuthenticatorBinding;
	sign(payload: string): Promise<string>;
	verify(payload: string, signature: string): Promise<boolean>;
}

export type WorkspaceFailureCode =
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
	| "materialization_budget_exhausted"
	| "recovery_provenance_untrusted"
	| "workspace_closed"
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
	| "session_acknowledgement_unresolved"
	| "model_failed";

export interface WorkspaceFailure {
	code: WorkspaceFailureCode;
	message: string;
	retryable: boolean;
}

export class CaseWorkspaceOpenError extends Error {
	readonly code: WorkspaceFailureCode;
	readonly retryable: boolean;

	constructor(failure: WorkspaceFailure) {
		super(failure.message);
		this.name = "CaseWorkspaceOpenError";
		this.code = failure.code;
		this.retryable = failure.retryable;
	}
}

export type TurnDiscardReason =
	| "turn_superseded"
	| "workspace_closed"
	| "orientation_binding_changed"
	| "orientation_invalidated"
	| "authorization_changed"
	| "dependency_version_changed"
	| "session_binding_changed"
	| "recovery_provenance_untrusted";

export interface WorkspaceEventEnvelope {
	operationId: string;
	turnId: string;
	eventSequence: number;
}

export interface WorkspaceTaskClarificationQuestion {
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
}

export interface WorkspaceTaskClarification {
	clarificationId: string;
	questions: readonly WorkspaceTaskClarificationQuestion[];
}

export type WorkspaceEvent = WorkspaceEventEnvelope &
	(
		| { type: "turn_started" }
		| { type: "context_bound"; protocol: "opencti-case-orientation/v2"; semanticDigest: string }
		| { type: "model_started" }
		| { type: "model_text_delta"; delta: string }
		| { type: "turn_completed" }
		| { type: "turn_clarification_required"; clarification: WorkspaceTaskClarification }
		| { type: "turn_cancelled" }
		| { type: "turn_failed"; failure: WorkspaceFailure }
		| { type: "turn_discarded"; reason: TurnDiscardReason }
	);

export type WorkspaceTurnResult = { operationId: string; turnId: string } & (
	| { status: "completed"; message: AssistantMessage }
	| { status: "clarification_required"; clarification: WorkspaceTaskClarification }
	| { status: "cancelled" }
	| { status: "failed"; failure: WorkspaceFailure }
	| { status: "discarded"; reason: TurnDiscardReason }
);

export interface WorkspaceTurn extends AsyncIterable<WorkspaceEvent> {
	readonly id: string;
	readonly result: Promise<WorkspaceTurnResult>;
	cancel(): void;
}

export type OrientationDependencyKey = "case_identity" | "visible_work" | "visible_object_membership";

export interface CaseWorkspace {
	prompt(input: {
		task: string;
		images?: readonly ImageContent[];
		orientationDependencies?: readonly OrientationDependencyKey[];
	}): WorkspaceTurn;
	close(): Promise<void>;
}

export interface CaseWorkspaceModule {
	open(
		input: { caseRef: string; accessPrincipal: AccessPrincipalBinding; sessionRef: WorkspaceSessionRef },
		options?: { signal?: AbortSignal },
	): Promise<CaseWorkspace>;
}

export interface OpenCtiObservedVersionV1 {
	modified?: string;
	updatedAt?: string;
	contentDigest: string;
}

export interface OpenCtiCaseIdentityV1 {
	internalId: string;
	standardId?: string;
	entityType: "Case-Incident" | "Case-Rfi" | "Case-Rft";
	displayName: string;
	sourceStatus?: { id: string; name: string };
	createdAt?: string;
	observedVersion: OpenCtiObservedVersionV1;
}

export interface OpenCtiVisibleWorkV1 {
	taskRef: string;
	name: string;
	sourceStatus?: { id: string; name: string };
	dueAt?: string;
	assigneeRefs: readonly string[];
	observedVersion: OpenCtiObservedVersionV1;
}

export interface OpenCtiVisibleObjectMembershipV1 {
	objectRef: string;
	standardId?: string;
	entityType: string;
	displayLabel: string;
	membership: "visible_case_object_reference";
	observedVersion: OpenCtiObservedVersionV1;
}

export type OrientationCollection<T> =
	| { kind: "complete"; items: readonly T[] }
	| { kind: "unavailable"; reasonCode: "incomplete_task_traversal" | "incomplete_object_traversal" };

export interface OrientationObservationV1 {
	caseIdentity: OpenCtiCaseIdentityV1;
	visibleWork: OrientationCollection<OpenCtiVisibleWorkV1>;
	visibleObjectMembership: OrientationCollection<OpenCtiVisibleObjectMembershipV1>;
}

export interface OrientationSourceIdentityV1 {
	instanceId: string;
	adapterArtifactDigest: string;
	targetFingerprint: string;
	schemaDigest: string;
	qualificationId: string;
	selectionDigest: string;
}

export interface OrientationReadPort {
	readonly source: OrientationSourceIdentityV1;
	observe(
		input: { caseRef: string; accessPrincipal: AccessPrincipalBinding },
		options?: { signal?: AbortSignal },
	): Promise<OrientationObservationV1>;
}

export type OpenCtiOrientationTransportRequest =
	| {
			kind: "case_root";
			probe: "start" | "end";
			observationId: string;
			caseRef: string;
			accessPrincipal: AccessPrincipalBinding;
	  }
	| {
			kind: "visible_work_page" | "visible_object_membership_page";
			observationId: string;
			caseRef: string;
			accessPrincipal: AccessPrincipalBinding;
			afterCursor: string | null;
	  };

export interface OpenCtiOrientationTransportPort {
	execute(request: OpenCtiOrientationTransportRequest, options?: { signal?: AbortSignal }): Promise<unknown>;
}

export type OrientationInvalidationReason =
	| "case_change_hint"
	| "authorization_uncertain"
	| "authorization_revoked"
	| "cursor_continuity_lost"
	| "schema_changed"
	| "qualification_changed"
	| "target_changed"
	| "unknown_change";

export interface OrientationInvalidation {
	caseRef: string;
	principalRef: string;
	receiptSequence: number;
	reason: OrientationInvalidationReason;
}

export interface OrientationInvalidationPort {
	subscribe(
		input: { caseRef: string; principalRef: string },
		listener: (invalidation: OrientationInvalidation) => void,
	): () => void;
}

export interface TaskUnderstandingExactCounterConfigurationV1 {
	readonly protocol: "workspace-task-understanding-exact-counter-configuration/v1";
	readonly counterId: string;
	readonly counterVersion: string;
	readonly tokenizerId: string;
	readonly tokenizerVersion: string;
	readonly wrapperPolicyId: string;
	readonly wrapperPolicyVersion: string;
}

export interface CaseWorkspaceModuleDependencies {
	orientation: OrientationReadPort;
	receiptAuthenticator: SessionReceiptAuthenticator;
	providerDispatchSecretBinder: ProviderDispatchSecretBinder;
	models: Models;
	model: Model<string>;
	env: ExecutionEnv;
	invalidation?: OrientationInvalidationPort;
	taskUnderstandingExactCounter?: TaskUnderstandingExactCounterConfigurationV1;
}
