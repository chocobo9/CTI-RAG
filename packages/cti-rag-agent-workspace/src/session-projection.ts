import { createHash } from "node:crypto";
import type { AgentMessage, Session, SessionTreeEntry } from "@earendil-works/pi-agent-core";
import type { AssistantMessage, UserMessage } from "@earendil-works/pi-ai";
import type { SessionReceiptAuthenticator } from "./types.ts";

const SPAN_OPEN = "cti.orientation.span_open/v1";
const SPAN_RECEIPT = "cti.orientation.span_receipt/v1";
const STALE_MARKER = "cti.orientation.stale/v1";
const PROTECTED_MARKER = "cti.orientation.protected/v1";

export interface ModelDependencyReceipt {
	key: "case_identity" | "visible_work" | "visible_object_membership";
	semanticDigest: string;
}

interface SpanOpenData {
	protocol: "cti-orientation-span/v1";
	operationId: string;
	turnId: string;
	sessionId: string;
	bindingDigest: string;
	targetGeneration: number;
	dependencies: readonly ModelDependencyReceipt[];
}

interface SpanReceiptData extends SpanOpenData {
	kind: "completed";
	orientationDigest: string;
	userMessageDigest: string;
	assistantMessageDigest: string;
	authenticatorId: string;
	signature: string;
}

interface ExclusionMarkerData {
	protocol: "cti-orientation-exclusion/v1";
	bindingDigest: string;
	orientationDigest: string;
	dependencies: readonly ModelDependencyReceipt[];
	reason: "orientation_changed" | "authorization_changed";
	authenticatorId: string;
	signature: string;
}

export interface SessionProjectionBinding {
	sessionId: string;
	bindingDigest: string;
	orientationDigest: string;
	dependencies: readonly ModelDependencyReceipt[];
	requestedDependencyKeys: readonly ModelDependencyReceipt["key"][];
}

export interface SessionProjection {
	messages: readonly AgentMessage[];
	capsuleReasons: readonly (
		| "orientation_changed"
		| "authorization_changed"
		| "incomplete_operation"
		| "provenance_untrusted"
	)[];
	exclusions: readonly {
		bindingDigest: string;
		orientationDigest: string;
		dependencies: readonly ModelDependencyReceipt[];
		reason: "orientation_changed";
	}[];
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(value: Readonly<Record<string, unknown>>, keys: readonly string[]): boolean {
	const actual = Object.keys(value).sort();
	const expected = [...keys].sort();
	return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function canonicalJson(value: unknown): string {
	if (value === null || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);
	if (typeof value === "number") {
		if (!Number.isFinite(value) || !Number.isSafeInteger(value)) throw new Error("Invalid signed JSON number");
		return JSON.stringify(value);
	}
	if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
	if (isRecord(value)) {
		return `{${Object.keys(value)
			.filter((key) => value[key] !== undefined)
			.sort()
			.map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
			.join(",")}}`;
	}
	throw new Error("Invalid signed JSON value");
}

function isDependencyReceiptSet(value: unknown): value is readonly ModelDependencyReceipt[] {
	if (!Array.isArray(value) || value.length < 1 || value.length > 3) return false;
	const keys = new Set<string>();
	for (const dependency of value) {
		if (
			!isRecord(dependency) ||
			!hasExactKeys(dependency, ["key", "semanticDigest"]) ||
			(dependency.key !== "case_identity" &&
				dependency.key !== "visible_work" &&
				dependency.key !== "visible_object_membership") ||
			typeof dependency.semanticDigest !== "string" ||
			keys.has(dependency.key)
		) {
			return false;
		}
		keys.add(dependency.key);
	}
	return keys.size === value.length;
}

function isSpanOpenData(value: unknown): value is SpanOpenData {
	return (
		isRecord(value) &&
		hasExactKeys(value, [
			"protocol",
			"operationId",
			"turnId",
			"sessionId",
			"bindingDigest",
			"targetGeneration",
			"dependencies",
		]) &&
		value.protocol === "cti-orientation-span/v1" &&
		typeof value.operationId === "string" &&
		typeof value.turnId === "string" &&
		typeof value.sessionId === "string" &&
		typeof value.bindingDigest === "string" &&
		Number.isSafeInteger(value.targetGeneration) &&
		(value.targetGeneration as number) > 0 &&
		isDependencyReceiptSet(value.dependencies)
	);
}

function isSpanReceiptData(value: unknown): value is SpanReceiptData {
	return (
		isRecord(value) &&
		hasExactKeys(value, [
			"protocol",
			"operationId",
			"turnId",
			"sessionId",
			"bindingDigest",
			"targetGeneration",
			"dependencies",
			"kind",
			"orientationDigest",
			"userMessageDigest",
			"assistantMessageDigest",
			"authenticatorId",
			"signature",
		]) &&
		value.protocol === "cti-orientation-span/v1" &&
		value.kind === "completed" &&
		typeof value.operationId === "string" &&
		typeof value.turnId === "string" &&
		typeof value.sessionId === "string" &&
		typeof value.bindingDigest === "string" &&
		Number.isSafeInteger(value.targetGeneration) &&
		(value.targetGeneration as number) > 0 &&
		isDependencyReceiptSet(value.dependencies) &&
		typeof value.orientationDigest === "string" &&
		typeof value.userMessageDigest === "string" &&
		typeof value.assistantMessageDigest === "string" &&
		typeof value.authenticatorId === "string" &&
		typeof value.signature === "string"
	);
}

function isExclusionMarkerData(value: unknown): value is ExclusionMarkerData {
	return (
		isRecord(value) &&
		hasExactKeys(value, [
			"protocol",
			"bindingDigest",
			"orientationDigest",
			"dependencies",
			"reason",
			"authenticatorId",
			"signature",
		]) &&
		value.protocol === "cti-orientation-exclusion/v1" &&
		typeof value.bindingDigest === "string" &&
		typeof value.orientationDigest === "string" &&
		isDependencyReceiptSet(value.dependencies) &&
		(value.reason === "orientation_changed" || value.reason === "authorization_changed") &&
		typeof value.authenticatorId === "string" &&
		typeof value.signature === "string"
	);
}

function sameOpen(receipt: SpanReceiptData, open: SpanOpenData): boolean {
	return (
		receipt.operationId === open.operationId &&
		receipt.turnId === open.turnId &&
		receipt.sessionId === open.sessionId &&
		receipt.bindingDigest === open.bindingDigest &&
		receipt.targetGeneration === open.targetGeneration &&
		canonicalJson(receipt.dependencies) === canonicalJson(open.dependencies)
	);
}

function sameDependencies(
	receipt: readonly ModelDependencyReceipt[],
	current: readonly ModelDependencyReceipt[],
): boolean {
	const currentByKey = new Map(current.map((dependency) => [dependency.key, dependency.semanticDigest]));
	return receipt.every((dependency) => currentByKey.get(dependency.key) === dependency.semanticDigest);
}

function changedReceiptDependencies(
	receipt: SpanReceiptData,
	current: SessionProjectionBinding,
): readonly ModelDependencyReceipt[] {
	if (receipt.bindingDigest !== current.bindingDigest) return receipt.dependencies;
	const currentByKey = new Map(current.dependencies.map((dependency) => [dependency.key, dependency.semanticDigest]));
	return receipt.dependencies.filter((dependency) => currentByKey.get(dependency.key) !== dependency.semanticDigest);
}

function markerIntersectsReceipt(marker: ExclusionMarkerData, receipt: SpanReceiptData): boolean {
	if (marker.bindingDigest !== receipt.bindingDigest || marker.orientationDigest !== receipt.orientationDigest) {
		return false;
	}
	const receiptDependencies = new Map(
		receipt.dependencies.map((dependency) => [dependency.key, dependency.semanticDigest]),
	);
	return marker.dependencies.some(
		(dependency) => receiptDependencies.get(dependency.key) === dependency.semanticDigest,
	);
}

function messageDigest(message: UserMessage | AssistantMessage): string {
	return `sha256:${createHash("sha256").update(canonicalJson(message)).digest("hex")}`;
}

async function authenticates(
	authenticator: SessionReceiptAuthenticator,
	value: SpanReceiptData | ExclusionMarkerData,
): Promise<boolean> {
	if (value.authenticatorId !== authenticator.authenticatorId) return false;
	const { signature, ...signed } = value;
	return authenticator.verify(canonicalJson(signed), signature);
}

export async function projectCallerSession(
	session: Session,
	current: SessionProjectionBinding,
	authenticator: SessionReceiptAuthenticator,
): Promise<SessionProjection> {
	const branch = await session.getBranch();
	const allEntries = await session.getEntries();
	const entryIndices = new Map(allEntries.map((entry, entryIndex) => [entry.id, entryIndex]));
	const exclusionMarkers: Array<{
		entryIndex: number;
		customType: typeof STALE_MARKER | typeof PROTECTED_MARKER;
		data: ExclusionMarkerData;
	}> = [];
	for (const [entryIndex, entry] of allEntries.entries()) {
		if (entry.type !== "custom") continue;
		if (entry.customType !== STALE_MARKER && entry.customType !== PROTECTED_MARKER) continue;
		if (!isExclusionMarkerData(entry.data) || !(await authenticates(authenticator, entry.data))) {
			throw new Error("recovery_provenance_untrusted");
		}
		exclusionMarkers.push({ entryIndex, customType: entry.customType, data: entry.data });
	}

	const messages: AgentMessage[] = [];
	const reasons = new Set<SessionProjection["capsuleReasons"][number]>();
	const exclusions = new Map<
		string,
		{
			bindingDigest: string;
			orientationDigest: string;
			dependencies: readonly ModelDependencyReceipt[];
			reason: "orientation_changed";
		}
	>();
	const closedReceipts = new Map<string, string>();
	let active: { data: SpanOpenData; messages: SessionTreeEntry[] } | undefined;
	for (const entry of branch) {
		const entryIndex = entryIndices.get(entry.id);
		if (entryIndex === undefined) throw new Error("recovery_provenance_untrusted");
		if (entry.type === "custom" && entry.customType === SPAN_OPEN) {
			if (active) reasons.add("incomplete_operation");
			if (!isSpanOpenData(entry.data)) throw new Error("recovery_provenance_untrusted");
			active = { data: entry.data, messages: [] };
			continue;
		}
		if (entry.type === "custom" && entry.customType === SPAN_RECEIPT) {
			if (!isSpanReceiptData(entry.data) || !(await authenticates(authenticator, entry.data))) {
				throw new Error("recovery_provenance_untrusted");
			}
			const receiptIdentity = `${entry.data.operationId}\u0000${entry.data.turnId}`;
			const encodedReceipt = canonicalJson(entry.data);
			if (!active) {
				if (closedReceipts.get(receiptIdentity) === encodedReceipt) continue;
				throw new Error("recovery_provenance_untrusted");
			}
			const receipt = entry.data;
			const spanMessages = active.messages;
			const validMessages =
				spanMessages.length === 2 &&
				spanMessages[0]?.type === "message" &&
				spanMessages[0].message.role === "user" &&
				spanMessages[1]?.type === "message" &&
				spanMessages[1].message.role === "assistant";
			if (!sameOpen(receipt, active.data) || !validMessages) {
				throw new Error("recovery_provenance_untrusted");
			}
			const user = (spanMessages[0] as Extract<SessionTreeEntry, { type: "message" }>).message as UserMessage;
			const assistant = (spanMessages[1] as Extract<SessionTreeEntry, { type: "message" }>)
				.message as AssistantMessage;
			if (
				messageDigest(user) !== receipt.userMessageDigest ||
				messageDigest(assistant) !== receipt.assistantMessageDigest
			) {
				throw new Error("recovery_provenance_untrusted");
			}
			const priorReceipt = closedReceipts.get(receiptIdentity);
			if (priorReceipt !== undefined) {
				if (priorReceipt !== encodedReceipt) throw new Error("recovery_provenance_untrusted");
				active = undefined;
				continue;
			}
			const requestedKeys = new Set(current.requestedDependencyKeys);
			if (!receipt.dependencies.every((dependency) => requestedKeys.has(dependency.key))) {
				closedReceipts.set(receiptIdentity, encodedReceipt);
				active = undefined;
				continue;
			}
			const laterMarkers = exclusionMarkers.filter(
				(marker) => marker.entryIndex > entryIndex && markerIntersectsReceipt(marker.data, receipt),
			);
			if (laterMarkers.some((marker) => marker.customType === PROTECTED_MARKER)) {
				reasons.add("authorization_changed");
			} else if (laterMarkers.some((marker) => marker.customType === STALE_MARKER)) {
				reasons.add("orientation_changed");
			} else if (
				receipt.bindingDigest !== current.bindingDigest ||
				!sameDependencies(receipt.dependencies, current.dependencies)
			) {
				reasons.add("orientation_changed");
				const dependencies = changedReceiptDependencies(receipt, current);
				const exclusion = {
					bindingDigest: receipt.bindingDigest,
					orientationDigest: receipt.orientationDigest,
					dependencies,
					reason: "orientation_changed" as const,
				};
				exclusions.set(canonicalJson(exclusion), exclusion);
			} else if (receipt.sessionId !== current.sessionId) {
				reasons.add("provenance_untrusted");
			} else {
				messages.push(user, assistant);
			}
			closedReceipts.set(receiptIdentity, encodedReceipt);
			active = undefined;
			continue;
		}
		if (entry.type === "custom" && (entry.customType === STALE_MARKER || entry.customType === PROTECTED_MARKER)) {
			continue;
		}
		if (entry.type === "custom" && entry.customType.startsWith("cti.orientation.")) {
			throw new Error("recovery_provenance_untrusted");
		}
		if (active) {
			active.messages.push(entry);
		} else if (entry.type === "message" || entry.type === "compaction" || entry.type === "branch_summary") {
			reasons.add("provenance_untrusted");
		}
	}
	if (active) reasons.add("incomplete_operation");
	return { messages, capsuleReasons: [...reasons], exclusions: [...exclusions.values()] };
}

export async function appendCompletedSpan(
	session: Session,
	input: SpanOpenData & { orientationDigest: string; user: UserMessage; assistant: AssistantMessage },
	expectedLeafId: string | null,
	authenticator: SessionReceiptAuthenticator,
	claimCompletion: () => boolean,
): Promise<"committed" | "not_claimed" | "session_conflict"> {
	const open: SpanOpenData = {
		protocol: "cti-orientation-span/v1",
		operationId: input.operationId,
		turnId: input.turnId,
		sessionId: input.sessionId,
		bindingDigest: input.bindingDigest,
		targetGeneration: input.targetGeneration,
		dependencies: input.dependencies,
	};
	const unsigned: Omit<SpanReceiptData, "signature"> = {
		...open,
		kind: "completed",
		orientationDigest: input.orientationDigest,
		userMessageDigest: messageDigest(input.user),
		assistantMessageDigest: messageDigest(input.assistant),
		authenticatorId: authenticator.authenticatorId,
	};
	const receipt: SpanReceiptData = { ...unsigned, signature: await authenticator.sign(canonicalJson(unsigned)) };
	if (!claimCompletion()) return "not_claimed";
	return (await session.appendBatchIfLeaf(expectedLeafId, [
		{ type: "custom", customType: SPAN_OPEN, data: open },
		{ type: "message", message: input.user },
		{ type: "message", message: input.assistant },
		{ type: "custom", customType: SPAN_RECEIPT, data: receipt },
	])) === undefined
		? "session_conflict"
		: "committed";
}

export async function appendExclusionMarker(
	session: Session,
	input: {
		bindingDigest: string;
		orientationDigest: string;
		dependencies: readonly ModelDependencyReceipt[];
		reason: "orientation_changed" | "authorization_changed";
	},
	authenticator: SessionReceiptAuthenticator,
): Promise<void> {
	const unsigned: Omit<ExclusionMarkerData, "signature"> = {
		protocol: "cti-orientation-exclusion/v1",
		...input,
		authenticatorId: authenticator.authenticatorId,
	};
	await session.appendCustomEntry(input.reason === "authorization_changed" ? PROTECTED_MARKER : STALE_MARKER, {
		...unsigned,
		signature: await authenticator.sign(canonicalJson(unsigned)),
	} satisfies ExclusionMarkerData);
}

export function staleCapsuleMessages(reasons: SessionProjection["capsuleReasons"]): UserMessage[] {
	return reasons.map((reason) => ({
		role: "user",
		content: `<stale_capsule category="${reason}">Prior analysis in this dependency chain is unusable.</stale_capsule>`,
		timestamp: Date.now(),
	}));
}
