export type MemoryCategory = "working" | "semantic" | "episodic" | "procedural";
export type MemoryState = "active" | "challenged" | "superseded" | "invalidated" | "deletion_pending" | "deleted";
export type MemoryMutation = "add" | "update" | "supersede" | "contradict" | "invalidate" | "delete" | "no_op";
export type MemoryValue = OwnedContent | OwnerReference;

export interface MemoryScope {
	tenantRef: string;
	visibility: "private" | "team" | "case" | "organization";
	principalRef: string;
	teamRef?: string;
	caseRef?: string;
	workspaceRef?: string;
	sessionRef?: string;
	taskRef?: string;
}

export interface TemporalBounds {
	observedAt?: string;
	recordedAt: string;
	validFrom?: string;
	validUntil?: string;
	expiresAt?: string;
}

export interface MemoryProvenance {
	sourceKind: "settled_run" | "explicit_command" | "owner_reference";
	sourceRef: string;
	sourceVersion: string;
	sourceDigest: string;
	derivation: "deterministic_candidate" | "human_authored" | "owner_projection";
	extractor?: { name: string; revision: string };
}

export interface MemoryRelation {
	kind: "derived_from" | "duplicate" | "updates" | "supersedes" | "contradicts" | "supports" | "invalidates";
	targetEntryId: string;
}

export interface OwnedContent {
	form: "owned_content";
	content: string;
}

export interface OwnerReference {
	form: "owner_reference";
	owner: "session" | "case" | "workspace" | "intelligence_evidence";
	ownerRef: string;
	ownerVersion: string;
}

export interface MemoryCandidate {
	candidateId: string;
	category: MemoryCategory;
	subject: string;
	value: MemoryValue;
	scope: MemoryScope;
	provenance: MemoryProvenance;
	temporal: TemporalBounds;
	relations: readonly MemoryRelation[];
	extractionEvidence: string;
	usePurpose: string;
}

export interface MemoryEntry {
	entryId: string;
	revision: number;
	state: MemoryState;
	category: MemoryCategory;
	subject: string;
	value: MemoryValue;
	scope: MemoryScope;
	provenance: MemoryProvenance;
	temporal: TemporalBounds;
	relations: readonly MemoryRelation[];
	createdAt: string;
	updatedAt: string;
	usePurpose: string;
}

export interface MemoryReceipt {
	receiptId: string;
	entryIds: readonly string[];
	revisions: readonly number[];
	mutation: MemoryMutation;
	createdAt: string;
}

export interface QualifiedMemoryView {
	entries: readonly MemoryEntry[];
	omitted: readonly {
		entryId: string;
		reason:
			| "out_of_scope"
			| "authorization_denied"
			| "purpose_denied"
			| "source_drift"
			| "state_ineligible"
			| "expired"
			| "deleted";
	}[];
	receipt: MemoryReceipt;
}

export interface MemoryPreparationRequest {
	scope: MemoryScope;
	usePurpose: string;
	principalRef: string;
	subject: string;
	required: boolean;
	sourceVersion?: string;
	now?: string;
}

export interface MemoryRevalidationRequest {
	entryId: string;
	revision: number;
	scope: MemoryScope;
	usePurpose: string;
	principalRef: string;
	sourceVersion: string;
	now?: string;
}

export type RunDisposition = "settled" | "failed" | "cancelled" | "discarded" | "uncertain";
export interface RunProof {
	runId: string;
	disposition: RunDisposition;
	savePointId?: string;
	outcomeDigest?: string;
	settledAt: string;
	sourceVersion: string;
}
export interface SettledRunMemoryRequest {
	run: RunProof;
	candidates: readonly MemoryCandidate[];
	idempotencyKey: string;
	/** When present, every candidate must already have this current revision. */
	expectedRevision?: number;
}

export type MemoryManagementCommand =
	| { kind: "remember"; candidate: MemoryCandidate; idempotencyKey: string }
	| { kind: "correct"; entryId: string; expectedRevision: number; candidate: MemoryCandidate; idempotencyKey: string }
	| { kind: "forget"; entryId: string; expectedRevision: number; idempotencyKey: string }
	| { kind: "supersede" | "invalidate"; entryId: string; expectedRevision: number; idempotencyKey: string }
	| { kind: "inspect"; entryId: string };

export type MemoryPreparationOutcome = { ok: true; view: QualifiedMemoryView } | MemoryFailure;
export type MemoryRevalidationOutcome =
	| { status: "valid_unchanged"; entry: MemoryEntry }
	| { status: "invalidated" | "unavailable"; error: MemoryError };
export type MemorySettlementOutcome =
	| { ok: true; receipt: MemoryReceipt; entries: readonly MemoryEntry[] }
	| MemoryFailure;
export type MemoryManagementOutcome =
	| { ok: true; receipt?: MemoryReceipt; entry?: MemoryEntry; entries?: readonly MemoryEntry[] }
	| MemoryFailure;

export type MemoryErrorCode =
	| "NOT_IMPLEMENTED"
	| "UNAVAILABLE"
	| "IDEMPOTENCY_CONFLICT"
	| "INVALID_RUN"
	| "INVALID_CANDIDATE"
	| "EXPECTED_REVISION_CONFLICT"
	| "NOT_FOUND"
	| "NOT_ELIGIBLE"
	| "DELETION_PENDING"
	| "SCOPE_DENIED"
	| "PURPOSE_DENIED";
export interface MemoryError {
	code: MemoryErrorCode;
	message: string;
	retryable: boolean;
}
export interface MemoryFailure {
	ok: false;
	error: MemoryError;
}

export interface AgentMemoryModule {
	prepare(request: MemoryPreparationRequest): Promise<MemoryPreparationOutcome>;
	revalidate(request: MemoryRevalidationRequest): Promise<MemoryRevalidationOutcome>;
	settle(request: SettledRunMemoryRequest): Promise<MemorySettlementOutcome>;
	manage(request: MemoryManagementCommand): Promise<MemoryManagementOutcome>;
}
