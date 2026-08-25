import { createHash, createHmac, randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { JsonlSessionStorage, type ProviderDispatchSecretBinder, Session } from "@earendil-works/pi-agent-core";
import { NodeExecutionEnv } from "@earendil-works/pi-agent-core/node";
import { createModels, fauxAssistantMessage, fauxProvider, type Message } from "@earendil-works/pi-ai";
import { createCaseWorkspaceModule } from "../case-workspace-module.ts";
import { validatesMaterializedOrientation } from "../orientation-schema-validator.ts";
import type { CaseWorkspace, WorkspaceEvent } from "../types.ts";
import {
	OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
	type OpenCtiLiveOrientationBudgets,
	type OpenCtiLiveOrientationEvidence,
	qualifyOpenCtiLiveOrientation,
} from "./opencti-live-orientation.ts";
import { createNodeHmacSessionReceiptAuthenticator } from "./session-receipt-authenticator.ts";

export interface OpenCtiCaseSmokeInput {
	endpoint: string;
	token: string;
	credentialSlot?: string;
	caseRef: string;
	sessionPath: string;
	receiptKey: Uint8Array;
	budgets: OpenCtiLiveOrientationBudgets;
	task?: string;
	fetchImpl?: typeof fetch;
	signal?: AbortSignal;
}

interface SmokeTurnEvidence {
	eventTypes: WorkspaceEvent["type"][];
	terminalEvent: "turn_completed";
	contextValidation: {
		validated: true;
		orientationSemanticDigest: string;
	};
}

export interface OpenCtiCaseSmokeResult {
	status: "passed";
	caseRef: string;
	principalRef: string;
	sessionId: string;
	sessionPath: string;
	qualification: OpenCtiLiveOrientationEvidence;
	initial: SmokeTurnEvidence;
	reopen: SmokeTurnEvidence;
}

function smokeFailure(code: "model_failed" | "transport_timeout" | "schema_or_mapping_mismatch"): never {
	throw Object.assign(new Error("OpenCTI live smoke failed safely"), { code });
}

function smokeFailureWithSessionPath(
	error: unknown,
	sessionPath: string,
): Error & { code: string; sessionPath: string } {
	const safeCodes = new Set([
		"authorization_or_visibility_changed",
		"case_root_not_found_or_not_visible",
		"cursor_continuity_lost",
		"model_failed",
		"observation_drift",
		"recovery_provenance_untrusted",
		"schema_or_mapping_mismatch",
		"transport_timeout",
	]);
	const candidate =
		typeof error === "object" && error !== null && "code" in error && typeof error.code === "string"
			? error.code
			: "model_failed";
	return Object.assign(new Error("OpenCTI live smoke failed safely"), {
		code: safeCodes.has(candidate) ? candidate : "model_failed",
		sessionPath,
	});
}

function messageText(message: Message): string {
	if (message.role === "user") {
		return typeof message.content === "string"
			? message.content
			: message.content.flatMap((part) => (part.type === "text" ? [part.text] : [])).join("");
	}
	if (message.role === "assistant") {
		return message.content.flatMap((part) => (part.type === "text" ? [part.text] : [])).join("");
	}
	return "";
}

function isObject(value: unknown): value is Readonly<Record<string, unknown>> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function canonicalJson(value: unknown): string {
	if (value === null) return "null";
	if (typeof value === "string" || typeof value === "boolean") return JSON.stringify(value);
	if (typeof value === "number" && Number.isFinite(value)) return JSON.stringify(value);
	if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
	if (isObject(value)) {
		return `{${Object.keys(value)
			.sort()
			.map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
			.join(",")}}`;
	}
	throw new Error("Unsupported JSON value");
}

function digest(value: unknown): string {
	return `sha256:${createHash("sha256").update(canonicalJson(value)).digest("hex")}`;
}

function taskUnderstandingProposal(messages: readonly Message[]): string {
	const serialized = messages
		.map(messageText)
		.find((text) => text.includes('"protocol":"workspace-task-understanding-invocation/v1"'));
	if (!serialized) smokeFailure("model_failed");
	const invocation = JSON.parse(serialized) as { originalTask: { taskId: string; text: string } };
	const { taskId, text } = invocation.originalTask;
	return JSON.stringify({
		protocol: "workspace-task-understanding-proposal/v1",
		normalizedReading: text,
		corrections: [],
		intent: { kind: "case_analysis", sourceClaimRefs: ["smoke_claim"] },
		outcomes: [
			{
				proposalOutcomeId: "smoke_outcome",
				requestedOutcome: "summary",
				objective: text,
				sourceClaimRefs: ["smoke_claim"],
			},
		],
		ambiguities: [],
		sourceClaims: [
			{
				claimId: "smoke_claim",
				kind: "original_task_text_span",
				startUtf16: 0,
				endUtf16: text.length,
				textDigest: digest({
					protocol: "workspace-task-source-span-basis/v1",
					sourceKind: "original_user_task",
					taskId,
					startUtf16: 0,
					endUtf16: text.length,
					text,
				}),
			},
		],
	});
}

function verifyModelContext(messages: readonly Message[], caseRef: string): string {
	const joined = messages.map(messageText).join("\n");
	if (joined.split("<case_orientation").length !== 2) smokeFailure("model_failed");
	const match = joined.match(
		/<case_orientation protocol="opencti-case-orientation\/v1" semantic_digest="(sha256:[0-9a-f]{64})">([\s\S]*?)<\/case_orientation>/u,
	);
	if (!match || match[1] === undefined || match[2] === undefined) smokeFailure("model_failed");
	let orientation: unknown;
	try {
		orientation = JSON.parse(match[2]);
	} catch {
		smokeFailure("model_failed");
	}
	if (!isObject(orientation) || !isObject(orientation.source)) smokeFailure("model_failed");
	const schemaCandidate = {
		...orientation,
		source: {
			...orientation.source,
			observationStartedAt: "model-context-omitted",
			observationFinishedAt: "model-context-omitted",
			comparisonDigest: `sha256:${"0".repeat(64)}`,
		},
	};
	if (!validatesMaterializedOrientation(schemaCandidate)) smokeFailure("model_failed");
	if (
		orientation.protocol !== "opencti-case-orientation/v2" ||
		orientation.caseRef !== caseRef ||
		orientation.semanticDigest !== match[1] ||
		!isObject(orientation.blocks) ||
		Object.keys(orientation.blocks).sort().join("|") !== "case_identity|visible_object_membership|visible_work" ||
		!isObject(orientation.blocks.case_identity) ||
		!isObject(orientation.blocks.visible_work) ||
		!isObject(orientation.blocks.visible_object_membership) ||
		!isObject(orientation.blocks.case_identity.presence) ||
		!isObject(orientation.blocks.visible_work.presence) ||
		!isObject(orientation.blocks.visible_object_membership.presence) ||
		orientation.blocks.case_identity.presence.kind !== "populated" ||
		(orientation.blocks.visible_work.presence.kind !== "populated" &&
			orientation.blocks.visible_work.presence.kind !== "empty") ||
		(orientation.blocks.visible_object_membership.presence.kind !== "populated" &&
			orientation.blocks.visible_object_membership.presence.kind !== "empty")
	) {
		smokeFailure("model_failed");
	}
	const expectedBlockDigests = [
		["case_identity", orientation.blocks.case_identity],
		["visible_work", orientation.blocks.visible_work],
		["visible_object_membership", orientation.blocks.visible_object_membership],
	] as const;
	for (const [blockKey, block] of expectedBlockDigests) {
		if (block.semanticDigest !== digest({ blockKey, normalizedPresence: block.presence })) {
			smokeFailure("model_failed");
		}
	}
	const expectedOrientationDigest = digest({
		protocol: orientation.protocol,
		schemaVersion: orientation.schemaVersion,
		instanceId: orientation.source.instanceId,
		principalRef: orientation.principalRef,
		usePurpose: orientation.usePurpose,
		selectionDigest: orientation.selectionDigest,
		caseRef: orientation.caseRef,
		blockDigests: expectedBlockDigests.map(([, block]) => block.semanticDigest),
	});
	if (orientation.semanticDigest !== expectedOrientationDigest) smokeFailure("model_failed");
	return match[1];
}

async function openOrCreateSession(env: NodeExecutionEnv, path: string): Promise<Session> {
	const exists = await env.exists(path);
	if (!exists.ok) smokeFailure("schema_or_mapping_mismatch");
	const storage = exists.value
		? await JsonlSessionStorage.open(env, path)
		: await JsonlSessionStorage.create(env, path, {
				cwd: env.cwd,
				sessionId: `cti-opencti-live-${randomUUID()}`,
			});
	return new Session(storage);
}

async function runTurn(
	workspace: CaseWorkspace,
	signal: AbortSignal,
	task: string,
	contextProof: () => string | undefined,
): Promise<SmokeTurnEvidence> {
	const onAbort = () => {
		void workspace.close();
	};
	if (signal.aborted) {
		await workspace.close();
		smokeFailure("transport_timeout");
	}
	signal.addEventListener("abort", onAbort, { once: true });
	const turn = workspace.prompt({ task });
	const eventTypes: WorkspaceEvent["type"][] = [];
	try {
		for await (const event of turn) eventTypes.push(event.type);
		const result = await turn.result;
		if (signal.aborted) smokeFailure("transport_timeout");
		const terminals = eventTypes.filter(
			(type) =>
				type === "turn_completed" ||
				type === "turn_cancelled" ||
				type === "turn_failed" ||
				type === "turn_discarded",
		);
		if (result.status !== "completed" || terminals.length !== 1 || terminals[0] !== "turn_completed") {
			smokeFailure("model_failed");
		}
		const orientationSemanticDigest = contextProof();
		if (orientationSemanticDigest === undefined) smokeFailure("model_failed");
		return {
			eventTypes,
			terminalEvent: "turn_completed",
			contextValidation: { validated: true, orientationSemanticDigest },
		};
	} finally {
		signal.removeEventListener("abort", onAbort);
	}
}

export async function runOpenCtiCaseSmoke(input: OpenCtiCaseSmokeInput): Promise<OpenCtiCaseSmokeResult> {
	const credentialSlot = input.credentialSlot ?? "OPENCTI_TOKEN";
	if (
		!input.caseRef.trim() ||
		!input.sessionPath.trim() ||
		!input.token ||
		!credentialSlot.trim() ||
		input.receiptKey.byteLength < 32
	) {
		smokeFailure("schema_or_mapping_mismatch");
	}
	const sessionPath = resolve(input.sessionPath);
	const controller = new AbortController();
	const onAbort = () => controller.abort();
	input.signal?.addEventListener("abort", onAbort, { once: true });
	const timeout = setTimeout(() => controller.abort(), Math.max(input.budgets.requestTimeoutMs * 50, 30_000));
	const env = new NodeExecutionEnv({ cwd: process.cwd() });
	let workspace: CaseWorkspace | undefined;
	try {
		const qualified = await qualifyOpenCtiLiveOrientation({
			endpoint: input.endpoint,
			credential: { credentialSlot, resolveToken: async () => input.token },
			expected: OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
			budgets: input.budgets,
			fetchImpl: input.fetchImpl,
			signal: controller.signal,
		});
		const models = createModels();
		const faux = fauxProvider({ provider: `opencti-live-smoke-${randomUUID()}`, tokenSize: { min: 100, max: 100 } });
		models.setProvider(faux.provider);
		const contextProofs: Array<string | undefined> = [undefined, undefined];
		faux.setResponses([
			(context) => fauxAssistantMessage(taskUnderstandingProposal(context.messages)),
			(context) => {
				contextProofs[0] = verifyModelContext(context.messages, input.caseRef);
				return fauxAssistantMessage("OpenCTI Orientation smoke completed.");
			},
			(context) => fauxAssistantMessage(taskUnderstandingProposal(context.messages)),
			(context) => {
				contextProofs[1] = verifyModelContext(context.messages, input.caseRef);
				return fauxAssistantMessage("OpenCTI Orientation reopen smoke completed.");
			},
		]);
		const receiptAuthenticator = createNodeHmacSessionReceiptAuthenticator({
			authenticatorId: "cti-opencti-live-smoke-hmac-sha256/v1",
			key: input.receiptKey,
		});
		const providerDispatchSecretBinder: ProviderDispatchSecretBinder = {
			bind: ({ domain, fieldName, valueUtf8 }) =>
				Promise.resolve({
					protocol: "pi-provider-secret-binding/v1",
					algorithm: "HMAC-SHA-256",
					keyId: "cti-opencti-live-smoke-provider-binding/v1",
					domain,
					fieldName,
					utf8Length: valueUtf8.byteLength,
					macBase64Url: createHmac("sha256", input.receiptKey)
						.update(domain)
						.update("\0")
						.update(fieldName)
						.update("\0")
						.update(valueUtf8)
						.digest("base64url"),
				}),
		};
		const module = createCaseWorkspaceModule({
			orientation: qualified.orientation,
			receiptAuthenticator,
			providerDispatchSecretBinder,
			models,
			model: faux.getModel(),
			env,
		});
		const initialSession = await openOrCreateSession(env, sessionPath);
		workspace = await module.open(
			{ caseRef: input.caseRef, accessPrincipal: qualified.accessPrincipal, sessionRef: initialSession },
			{ signal: controller.signal },
		);
		const task = input.task ?? "Summarize the visible Case orientation for this diagnostic smoke.";
		const initial = await runTurn(workspace, controller.signal, task, () => contextProofs[0]);
		await workspace.close();
		workspace = undefined;

		const reopenedSession = new Session(await JsonlSessionStorage.open(env, sessionPath));
		workspace = await module.open(
			{ caseRef: input.caseRef, accessPrincipal: qualified.accessPrincipal, sessionRef: reopenedSession },
			{ signal: controller.signal },
		);
		const reopen = await runTurn(workspace, controller.signal, task, () => contextProofs[1]);
		const sessionId = (await reopenedSession.getMetadata()).id;
		return {
			status: "passed",
			caseRef: input.caseRef,
			principalRef: qualified.accessPrincipal.principalRef,
			sessionId,
			sessionPath,
			qualification: qualified.evidence,
			initial,
			reopen,
		};
	} catch (error) {
		throw smokeFailureWithSessionPath(error, sessionPath);
	} finally {
		clearTimeout(timeout);
		input.signal?.removeEventListener("abort", onAbort);
		await workspace?.close();
		await env.cleanup();
	}
}
