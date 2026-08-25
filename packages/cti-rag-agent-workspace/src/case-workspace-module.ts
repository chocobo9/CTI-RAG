import { createHash, randomUUID } from "node:crypto";
import type { AgentHarnessEvent, AgentMessage, Session } from "@earendil-works/pi-agent-core";
import { AgentHarness, InMemorySessionStorage, Session as PiSession } from "@earendil-works/pi-agent-core";
import type { AssistantMessage, ImageContent, Models, SimpleStreamOptions, UserMessage } from "@earendil-works/pi-ai";
import { validatesMaterializedOrientation, validatesOrientationObservation } from "./orientation-schema-validator.ts";
import type { ModelDependencyReceipt, SessionProjection } from "./session-projection.ts";
import {
	appendCompletedSpan,
	appendExclusionMarker,
	projectCallerSession,
	staleCapsuleMessages,
} from "./session-projection.ts";
import { snapshotTaskUnderstandingExactCounterConfiguration, understandTaskAndCommit } from "./task-understanding.ts";
import type {
	AccessPrincipalBinding,
	CaseWorkspace,
	CaseWorkspaceModule,
	CaseWorkspaceModuleDependencies,
	OrientationCollection,
	OrientationDependencyKey,
	OrientationInvalidationReason,
	OrientationObservationV1,
	OrientationSourceIdentityV1,
	TurnDiscardReason,
	WorkspaceEvent,
	WorkspaceFailure,
	WorkspaceFailureCode,
	WorkspaceTaskClarification,
	WorkspaceTurn,
	WorkspaceTurnResult,
} from "./types.ts";
import { CaseWorkspaceOpenError } from "./types.ts";

interface OrientationPresence<T> {
	kind: "populated" | "empty" | "unavailable";
	value?: T;
	selectedScopeDigest?: string;
	reasonCode?: string;
	retryable?: boolean;
}

interface OrientationBlock<T> {
	presence: OrientationPresence<T>;
	semanticDigest: string;
}

interface MaterializedOrientation {
	protocol: "opencti-case-orientation/v2";
	schemaVersion: "opencti-case-orientation-v2";
	caseRef: string;
	principalRef: string;
	usePurpose: "case_investigation";
	selectionDigest: string;
	source: {
		instanceId: string;
		adapterArtifactDigest: string;
		targetFingerprint: string;
		schemaDigest: string;
		qualificationId: string;
		observationStartedAt: string;
		observationFinishedAt: string;
		materialization: "bounded_double_observation";
		comparisonDigest: string;
	};
	blocks: {
		case_identity: OrientationBlock<OrientationObservationV1["caseIdentity"]>;
		visible_work: OrientationBlock<readonly unknown[]>;
		visible_object_membership: OrientationBlock<readonly unknown[]>;
	};
	semanticDigest: string;
}

interface OrientationSlot {
	orientation: MaterializedOrientation;
	bindingDigest: string;
	targetGeneration: number;
}

function modelDependencies(orientation: MaterializedOrientation): readonly ModelDependencyReceipt[] {
	return [
		{ key: "case_identity", semanticDigest: orientation.blocks.case_identity.semanticDigest },
		{ key: "visible_work", semanticDigest: orientation.blocks.visible_work.semanticDigest },
		{
			key: "visible_object_membership",
			semanticDigest: orientation.blocks.visible_object_membership.semanticDigest,
		},
	];
}

const allOrientationDependencies: readonly OrientationDependencyKey[] = [
	"case_identity",
	"visible_work",
	"visible_object_membership",
];

function selectedDependencies(
	orientation: MaterializedOrientation,
	requested: readonly OrientationDependencyKey[] | undefined,
): readonly ModelDependencyReceipt[] {
	const selected = new Set(requested ?? allOrientationDependencies);
	return modelDependencies(orientation).filter((dependency) => selected.has(dependency.key));
}

function changedDependencies(
	previous: OrientationSlot,
	candidate: { orientation: MaterializedOrientation; bindingDigest: string },
): readonly ModelDependencyReceipt[] {
	const previousDependencies = modelDependencies(previous.orientation);
	if (previous.bindingDigest !== candidate.bindingDigest) return previousDependencies;
	const candidateByKey = new Map(
		modelDependencies(candidate.orientation).map((dependency) => [dependency.key, dependency.semanticDigest]),
	);
	return previousDependencies.filter((dependency) => candidateByKey.get(dependency.key) !== dependency.semanticDigest);
}

function renderOrientation(
	orientation: MaterializedOrientation,
	selected: readonly ModelDependencyReceipt[],
): { rendered: string; semanticDigest: string } {
	const keys = new Set(selected.map((dependency) => dependency.key));
	const semanticDigest =
		selected.length === allOrientationDependencies.length
			? orientation.semanticDigest
			: digest({ dependencies: selected });
	const {
		observationStartedAt: _startedAt,
		observationFinishedAt: _finishedAt,
		comparisonDigest: _comparison,
		...source
	} = orientation.source;
	const rendered = {
		protocol: orientation.protocol,
		schemaVersion: orientation.schemaVersion,
		caseRef: orientation.caseRef,
		principalRef: orientation.principalRef,
		usePurpose: orientation.usePurpose,
		selectionDigest: orientation.selectionDigest,
		source,
		blocks: {
			...(keys.has("case_identity") ? { case_identity: orientation.blocks.case_identity } : {}),
			...(keys.has("visible_work") ? { visible_work: orientation.blocks.visible_work } : {}),
			...(keys.has("visible_object_membership")
				? { visible_object_membership: orientation.blocks.visible_object_membership }
				: {}),
		},
		semanticDigest,
	};
	return {
		rendered: `<case_orientation protocol="${orientation.protocol}" semantic_digest="${semanticDigest}">${canonicalJson(rendered)}</case_orientation>`,
		semanticDigest,
	};
}

type WorkspaceEventBody =
	| { type: "turn_started" }
	| { type: "context_bound"; protocol: "opencti-case-orientation/v2"; semanticDigest: string }
	| { type: "model_started" }
	| { type: "model_text_delta"; delta: string }
	| { type: "turn_completed" }
	| { type: "turn_clarification_required"; clarification: WorkspaceTaskClarification }
	| { type: "turn_cancelled" }
	| { type: "turn_failed"; failure: WorkspaceFailure }
	| { type: "turn_discarded"; reason: TurnDiscardReason };

type WithoutTurnIds<T> = T extends unknown ? Omit<T, "operationId" | "turnId"> : never;
type WorkspaceTurnResultBody = WithoutTurnIds<WorkspaceTurnResult>;

function canonicalJson(value: unknown): string {
	if (value === null) return "null";
	if (typeof value === "string" || typeof value === "boolean") return JSON.stringify(value);
	if (typeof value === "number") {
		if (!Number.isFinite(value) || !Number.isSafeInteger(value)) throw new Error("Unsafe JSON number");
		return JSON.stringify(value);
	}
	if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
	if (typeof value === "object") {
		return `{${Object.entries(value)
			.filter((entry) => entry[1] !== undefined)
			.sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
			.map(([key, child]) => `${JSON.stringify(key)}:${canonicalJson(child)}`)
			.join(",")}}`;
	}
	throw new Error("Unsupported JSON value");
}

function digest(value: unknown): string {
	return `sha256:${createHash("sha256").update(canonicalJson(value)).digest("hex")}`;
}

function modelsWithoutUndefinedSimpleOptions(models: Models): Models {
	return new Proxy(models, {
		get(target, property, receiver) {
			if (property === "streamSimple") {
				return (
					model: Parameters<Models["streamSimple"]>[0],
					context: Parameters<Models["streamSimple"]>[1],
					options: SimpleStreamOptions | undefined,
				) => {
					const sanitized =
						options === undefined
							? undefined
							: (Object.fromEntries(
									Object.entries(options).filter((entry) => entry[1] !== undefined),
								) as SimpleStreamOptions);
					return target.streamSimple(model, context, sanitized);
				};
			}
			const value: unknown = Reflect.get(target, property, receiver);
			return typeof value === "function" ? value.bind(target) : value;
		},
	});
}

function compareCodeUnits(left: string, right: string): number {
	return left < right ? -1 : left > right ? 1 : 0;
}

function normalizeObservation(observation: OrientationObservationV1): OrientationObservationV1 {
	const visibleWork =
		observation.visibleWork.kind === "complete"
			? {
					kind: "complete" as const,
					items: observation.visibleWork.items
						.map((item) => ({ ...item, assigneeRefs: [...item.assigneeRefs].sort(compareCodeUnits) }))
						.sort((left, right) => compareCodeUnits(left.taskRef, right.taskRef)),
				}
			: observation.visibleWork;
	const visibleObjectMembership =
		observation.visibleObjectMembership.kind === "complete"
			? {
					kind: "complete" as const,
					items: [...observation.visibleObjectMembership.items].sort((left, right) =>
						compareCodeUnits(left.objectRef, right.objectRef),
					),
				}
			: observation.visibleObjectMembership;
	return { caseIdentity: observation.caseIdentity, visibleWork, visibleObjectMembership };
}

function collectionBlock<T>(
	blockKey: string,
	collection: OrientationCollection<T>,
	selectionDigest: string,
): OrientationBlock<readonly T[]> {
	let presence: OrientationPresence<readonly T[]>;
	if (collection.kind === "unavailable") {
		presence = { kind: "unavailable", reasonCode: collection.reasonCode, retryable: true };
	} else if (collection.items.length === 0) {
		presence = { kind: "empty", selectedScopeDigest: selectionDigest };
	} else {
		presence = { kind: "populated", value: collection.items };
	}
	return { presence, semanticDigest: digest({ blockKey, normalizedPresence: presence }) };
}

function safeFailure(code: WorkspaceFailureCode): WorkspaceFailure {
	const retryable =
		code === "observation_drift" ||
		code === "transport_timeout" ||
		code === "materialization_budget_exhausted" ||
		code === "incomplete_task_traversal" ||
		code === "incomplete_object_traversal" ||
		code === "orientation_not_usable" ||
		code === "dispatch_unavailable" ||
		code === "provider_failed" ||
		code === "provider_timeout" ||
		code === "session_control_unavailable" ||
		code === "session_acknowledgement_unresolved" ||
		code === "model_failed";
	const messages: Partial<Record<WorkspaceFailureCode, string>> = {
		orientation_not_usable: "The Case orientation is not usable for this access principal.",
		case_root_not_found_or_not_visible: "The Case root was not found or is not visible.",
		authorization_or_visibility_changed:
			"Authorization or visibility changed while the Case orientation was being read.",
		observation_drift: "The Case changed while its orientation was being read.",
		cursor_continuity_lost: "Orientation traversal continuity could not be proved.",
		transport_timeout: "The Case orientation read timed out.",
		schema_or_mapping_mismatch: "The Case orientation does not match the qualified contract.",
		recovery_provenance_untrusted: "The Workspace recovery provenance is not trusted.",
		workspace_closed: "The Case Workspace is closed.",
		input_invalid: "The task input is invalid.",
		input_budget_exceeded: "The task exceeds the supported understanding budget.",
		continuity_ineligible: "The referenced prior investigation is not eligible for continuation.",
		task_class_unsupported: "This task class is not supported by the investigation Workspace.",
		policy_unavailable: "Task Understanding policy is unavailable.",
		dispatch_unavailable: "Task Understanding is temporarily unavailable.",
		provider_failed: "Task Understanding could not be completed.",
		provider_timeout: "Task Understanding timed out.",
		task_basis_changed: "The task basis changed before admission.",
		attempt_identity_mismatch: "Task Understanding identity validation failed.",
		authenticator_basis_changed: "Task Understanding receipt authority changed.",
		admission_integrity_failure: "The task could not be admitted safely.",
		session_control_unavailable: "The Session control boundary is unavailable.",
		session_commit_conflict: "The Session changed before task admission committed.",
		session_acknowledgement_resolved_absent: "Task admission was not committed.",
		session_acknowledgement_unresolved: "Task admission acknowledgement could not be resolved.",
		model_failed: "The model request failed.",
	};
	return { code, message: messages[code] ?? "The Workspace operation failed safely.", retryable };
}

function openError(code: WorkspaceFailureCode): CaseWorkspaceOpenError {
	return new CaseWorkspaceOpenError(safeFailure(code));
}

function assertUsable(observation: OrientationObservationV1): void {
	if (!observation.caseIdentity.internalId || !observation.caseIdentity.displayName) {
		throw openError("orientation_not_usable");
	}
	if (observation.visibleWork.kind === "unavailable" && observation.visibleObjectMembership.kind === "unavailable") {
		throw openError("orientation_not_usable");
	}
}

function materializeOrientation(
	source: OrientationSourceIdentityV1,
	caseRef: string,
	principalRef: string,
	first: OrientationObservationV1,
	second: OrientationObservationV1,
	startedAt: string,
): MaterializedOrientation {
	const normalizedFirst = normalizeObservation(first);
	const normalizedSecond = normalizeObservation(second);
	assertUsable(normalizedFirst);
	assertUsable(normalizedSecond);
	const comparisonDigest = digest(normalizedFirst);
	if (comparisonDigest !== digest(normalizedSecond)) throw openError("observation_drift");
	const caseIdentityPresence = { kind: "populated" as const, value: normalizedSecond.caseIdentity };
	const caseIdentity = {
		presence: caseIdentityPresence,
		semanticDigest: digest({ blockKey: "case_identity", normalizedPresence: caseIdentityPresence }),
	};
	const visibleWork = collectionBlock("visible_work", normalizedSecond.visibleWork, source.selectionDigest);
	const visibleObjectMembership = collectionBlock(
		"visible_object_membership",
		normalizedSecond.visibleObjectMembership,
		source.selectionDigest,
	);
	const semanticDigest = digest({
		protocol: "opencti-case-orientation/v2",
		schemaVersion: "opencti-case-orientation-v2",
		instanceId: source.instanceId,
		principalRef,
		usePurpose: "case_investigation",
		selectionDigest: source.selectionDigest,
		caseRef,
		blockDigests: [caseIdentity.semanticDigest, visibleWork.semanticDigest, visibleObjectMembership.semanticDigest],
	});
	const orientation: MaterializedOrientation = {
		protocol: "opencti-case-orientation/v2",
		schemaVersion: "opencti-case-orientation-v2",
		caseRef,
		principalRef,
		usePurpose: "case_investigation",
		selectionDigest: source.selectionDigest,
		source: {
			instanceId: source.instanceId,
			adapterArtifactDigest: source.adapterArtifactDigest,
			targetFingerprint: source.targetFingerprint,
			schemaDigest: source.schemaDigest,
			qualificationId: source.qualificationId,
			observationStartedAt: startedAt,
			observationFinishedAt: new Date().toISOString(),
			materialization: "bounded_double_observation",
			comparisonDigest,
		},
		blocks: {
			case_identity: caseIdentity,
			visible_work: visibleWork,
			visible_object_membership: visibleObjectMembership,
		},
		semanticDigest,
	};
	if (!validatesMaterializedOrientation(orientation)) throw openError("schema_or_mapping_mismatch");
	return orientation;
}

function sourceSnapshot(source: OrientationSourceIdentityV1): OrientationSourceIdentityV1 {
	return { ...source };
}

function orientationBindingDigest(
	source: OrientationSourceIdentityV1,
	caseRef: string,
	accessPrincipal: AccessPrincipalBinding,
): string {
	return digest({
		caseRef,
		principalRef: accessPrincipal.principalRef,
		usePurpose: "case_investigation",
		selectionDigest: source.selectionDigest,
		instanceId: source.instanceId,
		adapterArtifactDigest: source.adapterArtifactDigest,
		qualificationId: source.qualificationId,
		schemaDigest: source.schemaDigest,
		targetFingerprint: source.targetFingerprint,
	});
}

function errorCode(error: unknown): string | undefined {
	return typeof error === "object" && error !== null && "code" in error && typeof error.code === "string"
		? error.code
		: undefined;
}

function mapReadError(error: unknown): CaseWorkspaceOpenError {
	if (error instanceof CaseWorkspaceOpenError) return error;
	const code = errorCode(error);
	if (code === "authorization_revoked") return openError("authorization_or_visibility_changed");
	if (code === "authorization_or_visibility_changed") return openError("authorization_or_visibility_changed");
	if (code === "case_root_not_found_or_not_visible") return openError("case_root_not_found_or_not_visible");
	if (code === "cursor_continuity_lost") return openError("cursor_continuity_lost");
	if (code === "transport_timeout") return openError("transport_timeout");
	if (code === "schema_or_mapping_mismatch") return openError("schema_or_mapping_mismatch");
	if (code === "observation_drift") return openError("observation_drift");
	if (code === "incomplete_task_traversal") return openError("incomplete_task_traversal");
	if (code === "incomplete_object_traversal") return openError("incomplete_object_traversal");
	return openError("schema_or_mapping_mismatch");
}

async function readOrientation(
	dependencies: CaseWorkspaceModuleDependencies,
	caseRef: string,
	accessPrincipal: AccessPrincipalBinding,
	signal?: AbortSignal,
): Promise<{ orientation: MaterializedOrientation; bindingDigest: string }> {
	const startedAt = new Date().toISOString();
	const source = sourceSnapshot(dependencies.orientation.source);
	try {
		const first = await dependencies.orientation.observe({ caseRef, accessPrincipal }, { signal });
		const second = await dependencies.orientation.observe({ caseRef, accessPrincipal }, { signal });
		if (!validatesOrientationObservation(first) || !validatesOrientationObservation(second)) {
			throw openError("schema_or_mapping_mismatch");
		}
		if (canonicalJson(source) !== canonicalJson(sourceSnapshot(dependencies.orientation.source))) {
			throw openError("schema_or_mapping_mismatch");
		}
		return {
			orientation: materializeOrientation(source, caseRef, accessPrincipal.principalRef, first, second, startedAt),
			bindingDigest: orientationBindingDigest(source, caseRef, accessPrincipal),
		};
	} catch (error) {
		throw mapReadError(error);
	}
}

class TurnEventStream implements WorkspaceTurn {
	readonly id: string;
	readonly operationId: string;
	readonly result: Promise<WorkspaceTurnResult>;
	private readonly events: WorkspaceEvent[] = [];
	private readonly waiters: Array<(result: IteratorResult<WorkspaceEvent>) => void> = [];
	private readonly resolveResult: (result: WorkspaceTurnResult) => void;
	private sequence = 0;
	private terminal = false;
	private completing = false;
	private stage: "pre_run" | "run" = "pre_run";
	private abort: (() => void) | undefined;

	constructor() {
		this.id = randomUUID();
		this.operationId = randomUUID();
		let resolveResult: ((result: WorkspaceTurnResult) => void) | undefined;
		this.result = new Promise((resolve) => {
			resolveResult = resolve;
		});
		this.resolveResult = resolveResult!;
	}

	get isTerminal(): boolean {
		return this.terminal;
	}

	get isCompleting(): boolean {
		return this.completing;
	}

	get isPreRun(): boolean {
		return this.stage === "pre_run";
	}

	beginRun(): void {
		if (!this.terminal) this.stage = "run";
	}

	beginCompletion(): boolean {
		if (this.terminal || this.completing) return false;
		this.completing = true;
		return true;
	}

	setAbort(abort: () => void): void {
		this.abort = abort;
		if (this.terminal) abort();
	}

	push(body: WorkspaceEventBody): void {
		if (this.terminal) return;
		const event = {
			...body,
			operationId: this.operationId,
			turnId: this.id,
			eventSequence: ++this.sequence,
		} as WorkspaceEvent;
		const waiter = this.waiters.shift();
		if (waiter) waiter({ done: false, value: event });
		else this.events.push(event);
	}

	private settle(body: WorkspaceEventBody, result: WorkspaceTurnResultBody): void {
		if (this.terminal) return;
		this.push(body);
		this.terminal = true;
		this.resolveResult({ ...result, operationId: this.operationId, turnId: this.id } as WorkspaceTurnResult);
		for (const waiter of this.waiters.splice(0)) waiter({ done: true, value: undefined });
	}

	complete(message: AssistantMessage): void {
		if (!this.completing) return;
		this.completing = false;
		this.settle({ type: "turn_completed" }, { status: "completed", message });
	}

	clarify(clarification: WorkspaceTaskClarification): void {
		this.completing = false;
		this.settle(
			{ type: "turn_clarification_required", clarification },
			{ status: "clarification_required", clarification },
		);
	}

	fail(failure: WorkspaceFailure): void {
		this.completing = false;
		this.settle({ type: "turn_failed", failure }, { status: "failed", failure });
	}

	discard(reason: TurnDiscardReason): void {
		if (this.completing) return;
		this.settle({ type: "turn_discarded", reason }, { status: "discarded", reason });
		this.abort?.();
	}

	discardCompletion(reason: TurnDiscardReason): void {
		if (!this.completing) return;
		this.completing = false;
		this.settle({ type: "turn_discarded", reason }, { status: "discarded", reason });
	}

	cancel(): void {
		if (this.completing) return;
		this.settle({ type: "turn_cancelled" }, { status: "cancelled" });
		this.abort?.();
	}

	[Symbol.asyncIterator](): AsyncIterator<WorkspaceEvent> {
		return {
			next: async () => {
				const event = this.events.shift();
				if (event) return { done: false, value: event };
				if (this.terminal) return { done: true, value: undefined };
				return await new Promise<IteratorResult<WorkspaceEvent>>((resolve) => this.waiters.push(resolve));
			},
		};
	}
}

function textDelta(event: AgentHarnessEvent): string | undefined {
	if (event.type !== "message_update" || event.assistantMessageEvent.type !== "text_delta") return undefined;
	return event.assistantMessageEvent.delta;
}

function isAssistantMessage(message: AgentMessage): message is AssistantMessage {
	return message.role === "assistant";
}

function invalidationDiscardReason(reasons: ReadonlyMap<number, OrientationInvalidationReason>): TurnDiscardReason {
	for (const reason of reasons.values()) {
		if (reason === "authorization_revoked" || reason === "authorization_uncertain") return "authorization_changed";
	}
	return "orientation_invalidated";
}

function userMessage(input: { task: string; images?: readonly ImageContent[] }): UserMessage {
	return {
		role: "user",
		content: input.images ? [{ type: "text", text: input.task }, ...input.images] : input.task,
		timestamp: Date.now(),
	};
}

function createWorkspace(
	dependencies: CaseWorkspaceModuleDependencies,
	caseRef: string,
	accessPrincipal: AccessPrincipalBinding,
	session: Session,
	initial: { orientation: MaterializedOrientation; bindingDigest: string },
): CaseWorkspace {
	let closed = false;
	let activeTurn: TurnEventStream | undefined;
	let slot: OrientationSlot | undefined = { ...initial, targetGeneration: 1 };
	let targetGeneration = 1;
	let latestInvalidationSequence = 0;
	const invalidations = new Map<number, OrientationInvalidationReason>();
	let reopen: Promise<void> | undefined;
	let reopenAbort: AbortController | undefined;
	let markerWrites = Promise.resolve();

	const removeInvalidation = dependencies.invalidation?.subscribe(
		{ caseRef, principalRef: accessPrincipal.principalRef },
		(invalidation) => {
			if (
				closed ||
				invalidation.caseRef !== caseRef ||
				invalidation.principalRef !== accessPrincipal.principalRef ||
				invalidation.receiptSequence <= latestInvalidationSequence
			) {
				return;
			}
			latestInvalidationSequence = invalidation.receiptSequence;
			invalidations.set(invalidation.receiptSequence, invalidation.reason);
			if (invalidation.reason === "authorization_revoked" && slot) {
				const current = slot;
				markerWrites = markerWrites.then(() =>
					appendExclusionMarker(
						session,
						{
							bindingDigest: current.bindingDigest,
							orientationDigest: current.orientation.semanticDigest,
							dependencies: modelDependencies(current.orientation),
							reason: "authorization_changed",
						},
						dependencies.receiptAuthenticator,
					),
				);
				void markerWrites.catch(() => undefined);
			}
		},
	);

	const refreshAtSafePoint = async (): Promise<void> => {
		if (closed || invalidations.size === 0) return;
		if (reopen) return reopen;
		reopen = (async () => {
			while (!closed && invalidations.size > 0) {
				const coveredSequence = latestInvalidationSequence;
				const previous = slot;
				const claimGeneration = ++targetGeneration;
				slot = undefined;
				const controller = new AbortController();
				reopenAbort = controller;
				let candidate: { orientation: MaterializedOrientation; bindingDigest: string };
				try {
					candidate = await readOrientation(dependencies, caseRef, accessPrincipal, controller.signal);
				} catch (error) {
					if (claimGeneration === targetGeneration) slot = undefined;
					throw error;
				}
				if (closed || claimGeneration !== targetGeneration) return;
				slot = { ...candidate, targetGeneration: claimGeneration };
				if (
					previous &&
					(previous.bindingDigest !== candidate.bindingDigest ||
						previous.orientation.semanticDigest !== candidate.orientation.semanticDigest)
				) {
					await appendExclusionMarker(
						session,
						{
							bindingDigest: previous.bindingDigest,
							orientationDigest: previous.orientation.semanticDigest,
							dependencies: changedDependencies(previous, candidate),
							reason: "orientation_changed",
						},
						dependencies.receiptAuthenticator,
					);
				}
				for (const sequence of [...invalidations.keys()]) {
					if (sequence <= coveredSequence) invalidations.delete(sequence);
				}
			}
		})().finally(() => {
			reopen = undefined;
			reopenAbort = undefined;
		});
		return reopen;
	};

	const runTurn = async (
		turn: TurnEventStream,
		input: {
			task: string;
			images?: readonly ImageContent[];
			orientationDependencies?: readonly OrientationDependencyKey[];
		},
	): Promise<void> => {
		try {
			if (turn.isTerminal || closed) return;
			await markerWrites;
			if (turn.isTerminal || closed) return;
			await refreshAtSafePoint();
			if (turn.isTerminal || closed) return;
			const admittedSlot = slot;
			if (!admittedSlot) {
				turn.fail(safeFailure("orientation_not_usable"));
				return;
			}
			const sessionMetadata = await session.getMetadata();
			const sessionId = sessionMetadata.id;
			let sessionHead = await session.getLeafId();
			const admittedInvalidationSequence = latestInvalidationSequence;
			const admittedDependencies = selectedDependencies(admittedSlot.orientation, input.orientationDependencies);
			if (admittedDependencies.length === 0) {
				turn.fail(safeFailure("orientation_not_usable"));
				return;
			}
			const taskController = new AbortController();
			turn.setAbort(() => taskController.abort());
			const taskUnderstanding = await understandTaskAndCommit({
				task: input.task,
				images: input.images,
				workspaceBindingDigest: admittedSlot.bindingDigest,
				contextGenerationDigest: digest({
					protocol: "workspace-task-understanding-context-generation/v1",
					targetGeneration: admittedSlot.targetGeneration,
					orientationDigest: admittedSlot.orientation.semanticDigest,
				}),
				workspaceTurnId: turn.id,
				taskRequestId: turn.operationId,
				taskGenerationId: `${turn.id}:task:1`,
				session,
				sessionId,
				expectedSessionLeafId: sessionHead,
				models: dependencies.models,
				model: dependencies.model,
				providerDispatchSecretBinder: dependencies.providerDispatchSecretBinder,
				receiptAuthenticator: dependencies.receiptAuthenticator,
				exactCounterConfiguration: snapshotTaskUnderstandingExactCounterConfiguration(
					dependencies.taskUnderstandingExactCounter,
				),
				signal: taskController.signal,
			});
			if (turn.isTerminal || closed) return;
			if (taskUnderstanding.kind === "cancelled") {
				turn.cancel();
				return;
			}
			if (taskUnderstanding.kind === "discarded") {
				turn.discard("session_binding_changed");
				return;
			}
			if (taskUnderstanding.kind === "committed_clarification") {
				turn.clarify({
					clarificationId: taskUnderstanding.clarification.clarificationId,
					questions: taskUnderstanding.clarification.questions.map(
						({ sourceBindingDigests: _sourceBindingDigests, ...question }) => question,
					),
				});
				return;
			}
			if (
				taskUnderstanding.kind !== "committed_admitted" &&
				taskUnderstanding.kind !== "committed_raw_task_fallback"
			) {
				turn.fail(safeFailure(taskUnderstanding.code));
				return;
			}
			turn.beginRun();
			sessionHead = await session.getLeafId();
			let projection: SessionProjection;
			try {
				projection = await projectCallerSession(
					session,
					{
						sessionId,
						bindingDigest: admittedSlot.bindingDigest,
						orientationDigest: admittedSlot.orientation.semanticDigest,
						dependencies: modelDependencies(admittedSlot.orientation),
						requestedDependencyKeys: admittedDependencies.map((dependency) => dependency.key),
					},
					dependencies.receiptAuthenticator,
				);
			} catch {
				turn.discard("recovery_provenance_untrusted");
				return;
			}
			const staging = new PiSession(new InMemorySessionStorage());
			for (const message of projection.messages) await staging.appendMessage(message);
			const harness = new AgentHarness({
				session: staging,
				models: modelsWithoutUndefinedSimpleOptions(dependencies.models),
				model: dependencies.model,
				env: dependencies.env,
			});
			const renderedOrientation = renderOrientation(admittedSlot.orientation, admittedDependencies);
			const capsules = staleCapsuleMessages(projection.capsuleReasons);
			const removeContext = harness.on("context", (event) => ({
				messages: [
					{ role: "user", content: renderedOrientation.rendered, timestamp: Date.now() },
					...capsules,
					...event.messages,
				],
			}));
			let modelStarted = false;
			const unsubscribe = harness.subscribe((event) => {
				if (turn.isTerminal) return;
				if (event.type === "message_start" && isAssistantMessage(event.message) && !modelStarted) {
					modelStarted = true;
					turn.push({ type: "model_started" });
				}
				const delta = textDelta(event);
				if (delta !== undefined) turn.push({ type: "model_text_delta", delta });
			});
			turn.setAbort(() => {
				taskController.abort();
				void harness.abort();
			});
			turn.push({
				type: "context_bound",
				protocol: admittedSlot.orientation.protocol,
				semanticDigest: renderedOrientation.semanticDigest,
			});
			try {
				const message = await harness.prompt(input.task, {
					images: input.images ? [...input.images] : undefined,
				});
				if (turn.isTerminal) return;
				if (message.stopReason === "aborted") {
					turn.cancel();
					return;
				}
				if (message.stopReason === "error") {
					turn.fail(safeFailure("model_failed"));
					return;
				}
				if (closed) {
					turn.discard("workspace_closed");
					return;
				}
				if (activeTurn !== turn) {
					turn.discard("turn_superseded");
					return;
				}
				if (latestInvalidationSequence !== admittedInvalidationSequence) {
					turn.discard(invalidationDiscardReason(invalidations));
					return;
				}
				if (!slot || slot.targetGeneration !== admittedSlot.targetGeneration) {
					turn.discard("orientation_binding_changed");
					return;
				}
				if (slot.bindingDigest !== admittedSlot.bindingDigest) {
					turn.discard("orientation_binding_changed");
					return;
				}
				if (slot.orientation.semanticDigest !== admittedSlot.orientation.semanticDigest) {
					turn.discard("dependency_version_changed");
					return;
				}
				if ((await session.getMetadata()).id !== sessionId || (await session.getLeafId()) !== sessionHead) {
					turn.discard("session_binding_changed");
					return;
				}
				const spanCommit = await appendCompletedSpan(
					session,
					{
						protocol: "cti-orientation-span/v1",
						operationId: turn.operationId,
						turnId: turn.id,
						sessionId,
						bindingDigest: admittedSlot.bindingDigest,
						targetGeneration: admittedSlot.targetGeneration,
						dependencies: admittedDependencies,
						orientationDigest: admittedSlot.orientation.semanticDigest,
						user: userMessage(input),
						assistant: message,
					},
					sessionHead,
					dependencies.receiptAuthenticator,
					() =>
						!turn.isTerminal &&
						!closed &&
						activeTurn === turn &&
						latestInvalidationSequence === admittedInvalidationSequence &&
						slot?.targetGeneration === admittedSlot.targetGeneration &&
						slot.bindingDigest === admittedSlot.bindingDigest &&
						slot.orientation.semanticDigest === admittedSlot.orientation.semanticDigest &&
						turn.beginCompletion(),
				);
				if (spanCommit !== "committed") {
					if (spanCommit === "session_conflict") turn.discardCompletion("session_binding_changed");
					else if (closed) turn.discard("workspace_closed");
					else if (latestInvalidationSequence !== admittedInvalidationSequence) {
						turn.discard(invalidationDiscardReason(invalidations));
					} else turn.discard("session_binding_changed");
					return;
				}
				turn.complete(message);
			} finally {
				unsubscribe();
				removeContext();
			}
		} catch (error) {
			if (!turn.isTerminal) {
				turn.fail(error instanceof CaseWorkspaceOpenError ? safeFailure(error.code) : safeFailure("model_failed"));
			}
		} finally {
			if (activeTurn === turn && turn.isTerminal) activeTurn = undefined;
			if (!closed && invalidations.size > 0) void refreshAtSafePoint().catch(() => undefined);
		}
	};

	return {
		prompt(input) {
			const predecessor = activeTurn;
			if (predecessor && !predecessor.isTerminal && !predecessor.isCompleting) {
				predecessor.discard("turn_superseded");
			}
			const turn = new TurnEventStream();
			activeTurn = turn;
			turn.push({ type: "turn_started" });
			if (closed) {
				turn.discard("workspace_closed");
				return turn;
			}
			void (async () => {
				if (predecessor?.isCompleting) await predecessor.result;
				await runTurn(turn, input);
			})();
			return turn;
		},
		async close() {
			if (closed) return;
			closed = true;
			if (activeTurn?.isCompleting) await activeTurn.result;
			else if (activeTurn?.isPreRun) activeTurn.cancel();
			else activeTurn?.discard("workspace_closed");
			reopenAbort?.abort();
			removeInvalidation?.();
		},
	};
}

export function createCaseWorkspaceModule(dependencies: CaseWorkspaceModuleDependencies): CaseWorkspaceModule {
	const taskUnderstandingExactCounter = snapshotTaskUnderstandingExactCounterConfiguration(
		dependencies.taskUnderstandingExactCounter,
	);
	const snapshottedDependencies = { ...dependencies, taskUnderstandingExactCounter };
	return {
		async open(input, options) {
			const initial = await readOrientation(
				snapshottedDependencies,
				input.caseRef,
				input.accessPrincipal,
				options?.signal,
			);
			try {
				const projection = await projectCallerSession(
					input.sessionRef,
					{
						sessionId: (await input.sessionRef.getMetadata()).id,
						bindingDigest: initial.bindingDigest,
						orientationDigest: initial.orientation.semanticDigest,
						dependencies: modelDependencies(initial.orientation),
						requestedDependencyKeys: allOrientationDependencies,
					},
					snapshottedDependencies.receiptAuthenticator,
				);
				for (const exclusion of projection.exclusions) {
					await appendExclusionMarker(input.sessionRef, exclusion, snapshottedDependencies.receiptAuthenticator);
				}
			} catch {
				throw openError("recovery_provenance_untrusted");
			}
			return createWorkspace(
				snapshottedDependencies,
				input.caseRef,
				input.accessPrincipal,
				input.sessionRef,
				initial,
			);
		},
	};
}
