import { createHash } from "node:crypto";
import { InMemorySessionStorage, Session } from "@earendil-works/pi-agent-core";
import { NodeExecutionEnv } from "@earendil-works/pi-agent-core/node";
import { fauxAssistantMessage, fauxProvider, type Message } from "@earendil-works/pi-ai";
import {
	type CaseWorkspaceModuleDependencies,
	createCaseWorkspaceModule as createCaseWorkspaceModuleBase,
	type WorkspaceEvent,
} from "@earendil-works/pi-cti-rag-agent-workspace";
import {
	HmacSessionReceiptAuthenticator,
	InMemoryOrientationAdapter,
	InMemoryOrientationInvalidationPort,
	type InMemoryOrientationPass,
} from "@earendil-works/pi-cti-rag-agent-workspace/testing";
import { expect, it } from "vitest";
import {
	createTaskUnderstandingModels,
	providerDispatchSecretBinder,
	withTaskUnderstandingResponses,
} from "./task-understanding-fixtures.ts";

const source = {
	instanceId: "opencti-reopen",
	adapterArtifactDigest: "sha256:adapter-v1",
	targetFingerprint: "sha256:target-v1",
	schemaDigest: "sha256:schema-v1",
	qualificationId: "qualification-v1",
	selectionDigest: "sha256:selection-v1",
} as const;

const receiptAuthenticator = new HmacSessionReceiptAuthenticator({
	authenticatorId: "test-hmac-v1",
	key: new Uint8Array([11, 29, 47, 83, 101, 127, 149, 173]),
});

function createCaseWorkspaceModule(
	dependencies: Omit<CaseWorkspaceModuleDependencies, "providerDispatchSecretBinder" | "receiptAuthenticator">,
) {
	return createCaseWorkspaceModuleBase({ ...dependencies, providerDispatchSecretBinder, receiptAuthenticator });
}

function pass(displayName: string): InMemoryOrientationPass {
	return {
		caseIdentity: {
			internalId: "case--reopen",
			entityType: "Case-Incident",
			displayName,
			observedVersion: { contentDigest: `sha256:${displayName}` },
		},
		workPages: [{ items: [], hasNextPage: false, authorization: "valid" }],
		objectPages: [{ items: [], hasNextPage: false, authorization: "valid" }],
	};
}

function session(): Session {
	return new Session(
		new InMemorySessionStorage({
			metadata: { id: "session-reopen", createdAt: "2026-07-20T00:00:00.000Z" },
		}),
	);
}

function text(message: Message): string {
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

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function canonicalJson(value: unknown): string {
	if (value === null || typeof value === "boolean" || typeof value === "number" || typeof value === "string") {
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
	throw new Error("Unsupported test JSON value");
}

function sha256(value: unknown): string {
	return `sha256:${createHash("sha256").update(canonicalJson(value)).digest("hex")}`;
}

function deferred(): { promise: Promise<void>; resolve: () => void } {
	let resolve: (() => void) | undefined;
	const promise = new Promise<void>((settle) => {
		resolve = settle;
	});
	return { promise, resolve: resolve! };
}

it("OR0B-SS-01/RO-07 fully reopens after drift and excludes the intersecting old prose", async () => {
	const contexts: string[][] = [];
	const invalidation = new InMemoryOrientationInvalidationPort();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ss-01", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("old analysis body");
			},
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("new analysis body");
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [pass("Old Orientation"), pass("Old Orientation"), pass("New Orientation"), pass("New Orientation")],
		}),
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const callerSession = session();
	const workspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await workspace.prompt({ task: "old task body" }).result).toMatchObject({ status: "completed" });
	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	expect(await workspace.prompt({ task: "new task" }).result).toMatchObject({ status: "completed" });

	const nextContext = contexts[1]?.join("\n") ?? "";
	expect(nextContext).toContain("New Orientation");
	expect(nextContext).toContain('<stale_capsule category="orientation_changed">');
	expect(nextContext).not.toContain("old task body");
	expect(nextContext).not.toContain("old analysis body");
	await workspace.close();
});

it("OR0B-SS-01/SS-06 keeps an invalidated A chain stale after A to B to A while retaining disjoint history", async () => {
	const contexts: string[][] = [];
	const invalidation = new InMemoryOrientationInvalidationPort();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ss-sticky-a-b-a", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("OLD A IDENTITY RESPONSE");
			},
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("STABLE WORK RESPONSE");
			},
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("B IDENTITY RESPONSE");
			},
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("NEW A IDENTITY RESPONSE");
			},
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("WORK CONTINUATION RESPONSE");
			},
		]),
	);
	const orientationPass = (displayName: string): InMemoryOrientationPass => ({
		...pass(displayName),
		workPages: [
			{
				items: [
					{
						taskRef: "task--stable",
						name: "Stable Work",
						assigneeRefs: [],
						observedVersion: { contentDigest: "sha256:stable-work" },
					},
				],
				hasNextPage: false,
				authorization: "valid",
			},
		],
	});
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [
				orientationPass("Identity A"),
				orientationPass("Identity A"),
				orientationPass("Identity B"),
				orientationPass("Identity B"),
				orientationPass("Identity A"),
				orientationPass("Identity A"),
			],
		}),
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: session(),
	});
	expect(
		await workspace.prompt({ task: "OLD A IDENTITY TASK", orientationDependencies: ["case_identity"] }).result,
	).toMatchObject({ status: "completed" });
	expect(
		await workspace.prompt({ task: "STABLE WORK TASK", orientationDependencies: ["visible_work"] }).result,
	).toMatchObject({ status: "completed" });

	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	expect(
		await workspace.prompt({ task: "B IDENTITY TASK", orientationDependencies: ["case_identity"] }).result,
	).toMatchObject({ status: "completed" });

	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 2,
		reason: "case_change_hint",
	});
	const returnedATurn = workspace.prompt({
		task: "NEW A IDENTITY TASK",
		orientationDependencies: ["case_identity"],
	});
	const returnedAEvents: WorkspaceEvent[] = [];
	for await (const event of returnedATurn) returnedAEvents.push(event);
	expect(await returnedATurn.result).toMatchObject({ status: "completed" });
	expect(returnedAEvents.map((event) => event.type)).toEqual([
		"turn_started",
		"context_bound",
		"model_started",
		"model_text_delta",
		"turn_completed",
	]);
	expect(
		await workspace.prompt({ task: "WORK CONTINUATION TASK", orientationDependencies: ["visible_work"] }).result,
	).toMatchObject({ status: "completed" });

	const returnedAContext = contexts[3]?.join("\n") ?? "";
	expect(returnedAContext).toContain("Identity A");
	expect(returnedAContext).toContain('<stale_capsule category="orientation_changed">');
	expect(returnedAContext).not.toContain("OLD A IDENTITY TASK");
	expect(returnedAContext).not.toContain("OLD A IDENTITY RESPONSE");
	expect(returnedAContext).not.toContain("B IDENTITY TASK");
	expect(returnedAContext).not.toContain("B IDENTITY RESPONSE");

	const disjointContext = contexts[4]?.join("\n") ?? "";
	expect(disjointContext).toContain("Stable Work");
	expect(disjointContext).toContain("STABLE WORK TASK");
	expect(disjointContext).toContain("STABLE WORK RESPONSE");
	expect(disjointContext).not.toContain("OLD A IDENTITY TASK");
	expect(disjointContext).not.toContain("B IDENTITY TASK");
	await workspace.close();
});

it("OR0B-SS-06 keeps dependency-disjoint prose usable inside one Workspace", async () => {
	const contexts: string[][] = [];
	const invalidation = new InMemoryOrientationInvalidationPort();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ss-06-disjoint", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("IDENTITY ONLY RESPONSE");
			},
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("WORK ONLY RESPONSE");
			},
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("IDENTITY AFTER WORK DRIFT");
			},
		]),
	);
	const orientationPass = (workName: string): InMemoryOrientationPass => ({
		...pass("Stable Identity"),
		workPages: [
			{
				items: [
					{
						taskRef: "task--disjoint",
						name: workName,
						assigneeRefs: [],
						observedVersion: { contentDigest: `sha256:${workName}` },
					},
				],
				hasNextPage: false,
				authorization: "valid",
			},
		],
	});
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [
				orientationPass("Old Work"),
				orientationPass("Old Work"),
				orientationPass("New Work"),
				orientationPass("New Work"),
			],
		}),
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: session(),
	});
	expect(
		await workspace.prompt({ task: "IDENTITY ONLY TASK", orientationDependencies: ["case_identity"] }).result,
	).toMatchObject({ status: "completed" });
	const workResult = await workspace.prompt({
		task: "WORK ONLY TASK",
		orientationDependencies: ["visible_work"],
	}).result;
	expect(workResult.status, JSON.stringify(workResult)).toBe("completed");
	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	expect(
		await workspace.prompt({ task: "IDENTITY CONTINUATION", orientationDependencies: ["case_identity"] }).result,
	).toMatchObject({ status: "completed" });

	const workContext = contexts[1]?.join("\n") ?? "";
	expect(workContext).toContain("Old Work");
	expect(workContext).not.toContain("Stable Identity");
	expect(workContext).not.toContain("IDENTITY ONLY TASK");
	expect(workContext).not.toContain("IDENTITY ONLY RESPONSE");
	const continuedIdentityContext = contexts[2]?.join("\n") ?? "";
	expect(continuedIdentityContext).toContain("Stable Identity");
	expect(continuedIdentityContext).toContain("IDENTITY ONLY TASK");
	expect(continuedIdentityContext).toContain("IDENTITY ONLY RESPONSE");
	expect(continuedIdentityContext).not.toContain("Old Work");
	expect(continuedIdentityContext).not.toContain("WORK ONLY TASK");
	expect(continuedIdentityContext).not.toContain("WORK ONLY RESPONSE");
	expect(continuedIdentityContext).not.toContain("stale_capsule");
	await workspace.close();
});

it("OR0B-RO-01 clean process reopen rereads twice and retains a matching closed span", async () => {
	const contexts: string[][] = [];
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ro-01", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("retained closed answer");
			},
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("after reopen");
			},
		]),
	);
	const adapter = new InMemoryOrientationAdapter({
		source,
		passes: [
			pass("Stable Orientation"),
			pass("Stable Orientation"),
			pass("Stable Orientation"),
			pass("Stable Orientation"),
		],
	});
	const module = createCaseWorkspaceModule({
		orientation: adapter,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const callerSession = session();
	const firstWorkspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await firstWorkspace.prompt({ task: "retained closed task" }).result).toMatchObject({ status: "completed" });
	await firstWorkspace.close();
	const reopenedWorkspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await reopenedWorkspace.prompt({ task: "after reopen task" }).result).toMatchObject({ status: "completed" });
	expect(contexts[1]?.join("\n")).toContain("retained closed task");
	expect(contexts[1]?.join("\n")).toContain("retained closed answer");
	await reopenedWorkspace.close();
});

it("OR0B-RO-02/RO-04/SS-03 dirty reopen isolates an interrupted span without replay or duplicate terminal", async () => {
	const callerSession = session();
	await callerSession.appendCustomEntry("cti.orientation.span_open/v1", {
		protocol: "cti-orientation-span/v1",
		operationId: "operation-interrupted",
		turnId: "turn-interrupted",
		sessionId: "session-reopen",
		bindingDigest: "sha256:old-binding",
		targetGeneration: 1,
		dependencies: [
			{ key: "case_identity", semanticDigest: "sha256:old-case" },
			{ key: "visible_work", semanticDigest: "sha256:old-work" },
			{ key: "visible_object_membership", semanticDigest: "sha256:old-objects" },
		],
	});
	await callerSession.appendMessage({
		role: "user",
		content: "INTERRUPTED PRIVATE BODY",
		timestamp: Date.now(),
	});
	const contexts: string[][] = [];
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ro-02", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("safe answer");
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Fresh"), pass("Fresh")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	const turn = workspace.prompt({ task: "continue safely" });
	const events: WorkspaceEvent[] = [];
	for await (const event of turn) events.push(event);
	expect(await turn.result).toMatchObject({ status: "completed" });
	expect(events.filter((event) => event.type.startsWith("turn_")).map((event) => event.type)).toEqual([
		"turn_started",
		"turn_completed",
	]);
	const nextContext = contexts[0]?.join("\n") ?? "";
	expect(nextContext).toContain('<stale_capsule category="incomplete_operation">');
	expect(nextContext).not.toContain("INTERRUPTED PRIVATE BODY");
	await workspace.close();
});

it("OR0B-RO-02/RO-04 treats every incomplete atomic completion prefix as audit-only", async () => {
	for (const persistedMessageCount of [0, 1, 2] as const) {
		const callerSession = session();
		await callerSession.appendCustomEntry("cti.orientation.span_open/v1", {
			protocol: "cti-orientation-span/v1",
			operationId: `operation-prefix-${persistedMessageCount}`,
			turnId: `turn-prefix-${persistedMessageCount}`,
			sessionId: "session-reopen",
			bindingDigest: "sha256:interrupted-binding",
			targetGeneration: 1,
			dependencies: [
				{ key: "case_identity", semanticDigest: "sha256:interrupted-case" },
				{ key: "visible_work", semanticDigest: "sha256:interrupted-work" },
				{ key: "visible_object_membership", semanticDigest: "sha256:interrupted-objects" },
			],
		});
		if (persistedMessageCount >= 1) {
			await callerSession.appendMessage({
				role: "user",
				content: `INTERRUPTED PREFIX USER ${persistedMessageCount}`,
				timestamp: Date.now(),
			});
		}
		if (persistedMessageCount >= 2) {
			await callerSession.appendMessage(fauxAssistantMessage("INTERRUPTED PREFIX ASSISTANT 2"));
		}
		let context = "";
		const models = createTaskUnderstandingModels();
		const faux = fauxProvider({
			provider: `orientation-ro-prefix-${persistedMessageCount}`,
			tokenSize: { min: 100, max: 100 },
		});
		models.setProvider(faux.provider);
		faux.setResponses(
			withTaskUnderstandingResponses([
				(modelContext) => {
					context = modelContext.messages.map(text).join("\n");
					return fauxAssistantMessage("safe after prefix");
				},
			]),
		);
		const module = createCaseWorkspaceModule({
			orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Fresh"), pass("Fresh")] }),
			models,
			model: faux.getModel(),
			env: new NodeExecutionEnv({ cwd: process.cwd() }),
		});
		const workspace = await module.open({
			caseRef: "case--reopen",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: callerSession,
		});
		expect(await workspace.prompt({ task: "recover prefix" }).result).toMatchObject({ status: "completed" });
		expect(context).toContain('<stale_capsule category="incomplete_operation">');
		expect(context).not.toContain("INTERRUPTED PREFIX USER");
		expect(context).not.toContain("INTERRUPTED PREFIX ASSISTANT");
		await workspace.close();
	}
});

it("OR0B-RO-02 restarts cleanly after initial read or materialization failure writes no Session span", async () => {
	const failingPassSets: readonly (readonly InMemoryOrientationPass[])[] = [
		[{ ...pass("Open Failure"), failureCode: "transport_timeout" }],
		[pass("Materialization Before"), pass("Materialization After")],
	];
	for (let index = 0; index < failingPassSets.length; index++) {
		const callerSession = session();
		const models = createTaskUnderstandingModels();
		const faux = fauxProvider({
			provider: `orientation-ro-initial-failure-${index}`,
			tokenSize: { min: 100, max: 100 },
		});
		models.setProvider(faux.provider);
		const failingModule = createCaseWorkspaceModule({
			orientation: new InMemoryOrientationAdapter({ source, passes: failingPassSets[index]! }),
			models,
			model: faux.getModel(),
			env: new NodeExecutionEnv({ cwd: process.cwd() }),
		});
		await expect(
			failingModule.open({
				caseRef: "case--reopen",
				accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
				sessionRef: callerSession,
			}),
		).rejects.toMatchObject({ code: index === 0 ? "transport_timeout" : "observation_drift" });
		expect(await callerSession.getEntries()).toHaveLength(0);

		faux.setResponses(withTaskUnderstandingResponses([fauxAssistantMessage("safe after initial failure")]));
		const freshModule = createCaseWorkspaceModule({
			orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Fresh"), pass("Fresh")] }),
			models,
			model: faux.getModel(),
			env: new NodeExecutionEnv({ cwd: process.cwd() }),
		});
		const freshWorkspace = await freshModule.open({
			caseRef: "case--reopen",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: callerSession,
		});
		expect(await freshWorkspace.prompt({ task: "fresh after failure" }).result).toMatchObject({
			status: "completed",
		});
		await freshWorkspace.close();
	}
});

it("OR0B-SS-04 excludes legacy and untrusted compaction prose mechanically", async () => {
	const callerSession = session();
	const legacyId = await callerSession.appendMessage({
		role: "user",
		content: "LEGACY UNTRUSTED BODY",
		timestamp: Date.now(),
	});
	await callerSession.appendCompaction("COMPACTION UNTRUSTED BODY", legacyId, 10);
	const contexts: string[][] = [];
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ss-04", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("safe answer");
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Fresh"), pass("Fresh")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await workspace.prompt({ task: "continue" }).result).toMatchObject({ status: "completed" });
	const nextContext = contexts[0]?.join("\n") ?? "";
	expect(nextContext).toContain('<stale_capsule category="provenance_untrusted">');
	expect(nextContext).not.toContain("LEGACY UNTRUSTED BODY");
	expect(nextContext).not.toContain("COMPACTION UNTRUSTED BODY");
	await workspace.close();
});

it("OR0B-SS-07 preserves authentic span receipts across compaction ancestry", async () => {
	const contexts: string[][] = [];
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ss-07-receipt", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			fauxAssistantMessage("TRUSTED PRE-COMPACTION RESPONSE"),
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("after compaction");
			},
		]),
	);
	const callerSession = session();
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [pass("Stable"), pass("Stable"), pass("Stable"), pass("Stable")],
		}),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const first = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await first.prompt({ task: "TRUSTED PRE-COMPACTION TASK" }).result).toMatchObject({ status: "completed" });
	await first.close();
	const firstEntry = (await callerSession.getEntries())[0];
	if (!firstEntry) throw new Error("Expected a committed CTI span");
	await callerSession.appendCompaction("UNTRUSTED COMPACTION SUMMARY", firstEntry.id, 100);
	const reopened = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await reopened.prompt({ task: "continue after compaction" }).result).toMatchObject({ status: "completed" });
	const context = contexts[0]?.join("\n") ?? "";
	expect(context).toContain("TRUSTED PRE-COMPACTION TASK");
	expect(context).toContain("TRUSTED PRE-COMPACTION RESPONSE");
	expect(context).not.toContain("UNTRUSTED COMPACTION SUMMARY");
	await reopened.close();
});

it("OR0B-SS-02/SS-05/SS-07 preserves a protected marker across compaction ancestry", async () => {
	const contexts: string[][] = [];
	const invalidation = new InMemoryOrientationInvalidationPort();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ss-02", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			fauxAssistantMessage("REVOKED DERIVED PROSE"),
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("reauthorized answer");
			},
		]),
	);
	const callerSession = session();
	const firstModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [pass("Protected Orientation"), pass("Protected Orientation")],
		}),
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const firstWorkspace = await firstModule.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await firstWorkspace.prompt({ task: "REVOKED SOURCE PROMPT" }).result).toMatchObject({ status: "completed" });
	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "authorization_revoked",
	});
	await new Promise<void>((resolve) => setImmediate(resolve));
	await firstWorkspace.close();
	const firstEntry = (await callerSession.getEntries())[0];
	if (!firstEntry) throw new Error("Expected protected CTI history");
	await callerSession.appendCompaction("UNTRUSTED PROTECTED SUMMARY", firstEntry.id, 100);

	const secondModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [pass("Protected Orientation"), pass("Protected Orientation")],
		}),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const secondWorkspace = await secondModule.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await secondWorkspace.prompt({ task: "reauthorized task" }).result).toMatchObject({ status: "completed" });
	const nextContext = contexts[0]?.join("\n") ?? "";
	expect(nextContext).toContain('<stale_capsule category="authorization_changed">');
	expect(nextContext).not.toContain("REVOKED SOURCE PROMPT");
	expect(nextContext).not.toContain("REVOKED DERIVED PROSE");
	expect(nextContext).not.toContain("UNTRUSTED PROTECTED SUMMARY");
	await secondWorkspace.close();
});

it("OR0B-SS-07 branch navigation cannot remove a stale marker and revive its earlier span", async () => {
	const contexts: string[][] = [];
	const invalidation = new InMemoryOrientationInvalidationPort();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ss-07-branch", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			fauxAssistantMessage("STALE BRANCH RESPONSE"),
			fauxAssistantMessage("changed response"),
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("safe branch response");
			},
		]),
	);
	const callerSession = session();
	const firstModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [pass("Branch A"), pass("Branch A"), pass("Branch B"), pass("Branch B")],
		}),
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const firstWorkspace = await firstModule.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await firstWorkspace.prompt({ task: "STALE BRANCH TASK" }).result).toMatchObject({ status: "completed" });
	const staleReceipt = (await callerSession.getEntries()).find(
		(entry) => entry.type === "custom" && entry.customType === "cti.orientation.span_receipt/v1",
	);
	if (!staleReceipt) throw new Error("Expected stale span receipt");
	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	expect(await firstWorkspace.prompt({ task: "analyze branch basis" }).result).toMatchObject({ status: "completed" });
	await firstWorkspace.close();

	await callerSession.moveTo(staleReceipt.id);
	const reopenedModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Branch A"), pass("Branch A")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const reopenedWorkspace = await reopenedModule.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await reopenedWorkspace.prompt({ task: "continue from branch" }).result).toMatchObject({
		status: "completed",
	});
	const context = contexts[0]?.join("\n") ?? "";
	expect(context).toContain('<stale_capsule category="orientation_changed">');
	expect(context).not.toContain("STALE BRANCH TASK");
	expect(context).not.toContain("STALE BRANCH RESPONSE");
	await reopenedWorkspace.close();
});

it("OR0B-SS-07 rejects a stale marker whose affected dependencies were altered after signing", async () => {
	const invalidation = new InMemoryOrientationInvalidationPort();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ss-07-marker-tamper", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([fauxAssistantMessage("old response"), fauxAssistantMessage("changed response")]),
	);
	const callerSession = session();
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [pass("Tamper A"), pass("Tamper A"), pass("Tamper B"), pass("Tamper B")],
		}),
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await workspace.prompt({ task: "tamper basis" }).result).toMatchObject({ status: "completed" });
	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	expect(await workspace.prompt({ task: "install stale marker" }).result).toMatchObject({ status: "completed" });
	await workspace.close();

	const tamperedEntries = (await callerSession.getEntries()).map((entry) => {
		if (
			entry.type !== "custom" ||
			entry.customType !== "cti.orientation.stale/v1" ||
			!isRecord(entry.data) ||
			!Array.isArray(entry.data.dependencies)
		) {
			return entry;
		}
		return {
			...entry,
			data: {
				...entry.data,
				dependencies: entry.data.dependencies.map((dependency, index) =>
					index === 0 && isRecord(dependency)
						? { ...dependency, semanticDigest: "sha256:tampered-marker-dependency" }
						: dependency,
				),
			},
		};
	});
	const tamperedSession = new Session(
		new InMemorySessionStorage({
			metadata: { id: "session-reopen", createdAt: "2026-07-20T00:00:00.000Z" },
			entries: tamperedEntries,
		}),
	);
	const reopenModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Tamper B"), pass("Tamper B")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	await expect(
		reopenModule.open({
			caseRef: "case--reopen",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: tamperedSession,
		}),
	).rejects.toMatchObject({ code: "recovery_provenance_untrusted", retryable: false });
});

it("OR0B-RO-05 rejects corrupt CTI recovery provenance without exposing its payload", async () => {
	const callerSession = session();
	await callerSession.appendCustomEntry("cti.orientation.span_receipt/v1", {
		payload: "SUSPECT RECOVERY SECRET",
	});
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ro-05" });
	models.setProvider(faux.provider);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Fresh"), pass("Fresh")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	let failure: unknown;
	try {
		await module.open({
			caseRef: "case--reopen",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: callerSession,
		});
	} catch (error) {
		failure = error;
	}
	expect(failure).toMatchObject({ code: "recovery_provenance_untrusted", retryable: false });
	expect(String(failure)).not.toContain("SUSPECT RECOVERY SECRET");
	expect(faux.state.callCount).toBe(0);
});

it("OR0B-RO-05 rejects a structurally valid receipt forged with a public SHA-256 digest", async () => {
	const callerSession = session();
	const dependencies = [
		{ key: "case_identity", semanticDigest: "sha256:forged-case" },
		{ key: "visible_work", semanticDigest: "sha256:forged-work" },
		{ key: "visible_object_membership", semanticDigest: "sha256:forged-objects" },
	] as const;
	const open = {
		protocol: "cti-orientation-span/v1",
		operationId: "operation-forged",
		turnId: "turn-forged",
		sessionId: "session-reopen",
		bindingDigest: "sha256:forged-binding",
		targetGeneration: 1,
		dependencies,
	} as const;
	const user = { role: "user" as const, content: "FORGED PRIVATE USER BODY", timestamp: Date.now() };
	const assistant = fauxAssistantMessage("FORGED PRIVATE ASSISTANT BODY");
	const unsigned = {
		...open,
		kind: "completed" as const,
		orientationDigest: "sha256:forged-orientation",
		userMessageDigest: sha256(user),
		assistantMessageDigest: sha256(assistant),
		authenticatorId: receiptAuthenticator.authenticatorId,
	};
	await callerSession.appendCustomEntry("cti.orientation.span_open/v1", open);
	await callerSession.appendMessage(user);
	await callerSession.appendMessage(assistant);
	await callerSession.appendCustomEntry("cti.orientation.span_receipt/v1", {
		...unsigned,
		signature: createHash("sha256").update(canonicalJson(unsigned)).digest("hex"),
	});

	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ro-05-forged" });
	models.setProvider(faux.provider);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Fresh"), pass("Fresh")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	await expect(
		module.open({
			caseRef: "case--reopen",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: callerSession,
		}),
	).rejects.toMatchObject({ code: "recovery_provenance_untrusted", retryable: false });
	expect(faux.state.callCount).toBe(0);
});

it("OR0B-RO-05 rejects an intact receipt authenticated by a different trust key", async () => {
	const callerSession = session();
	const foreignAuthenticator = new HmacSessionReceiptAuthenticator({
		authenticatorId: receiptAuthenticator.authenticatorId,
		key: new Uint8Array([2, 3, 5, 7, 11, 13, 17, 19]),
	});
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ro-05-foreign", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(withTaskUnderstandingResponses([fauxAssistantMessage("FOREIGN AUTHENTICATED BODY")]));
	const foreignModule = createCaseWorkspaceModuleBase({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Stable"), pass("Stable")] }),
		receiptAuthenticator: foreignAuthenticator,
		providerDispatchSecretBinder,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const foreignWorkspace = await foreignModule.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await foreignWorkspace.prompt({ task: "foreign task" }).result).toMatchObject({ status: "completed" });
	await foreignWorkspace.close();

	const trustedModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Stable"), pass("Stable")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	await expect(
		trustedModule.open({
			caseRef: "case--reopen",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: callerSession,
		}),
	).rejects.toMatchObject({ code: "recovery_provenance_untrusted", retryable: false });
});

it("OR0B-SS-06 authenticates every rendered Orientation dependency and rejects receipt tampering", async () => {
	const callerSession = session();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ss-06-receipt", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(withTaskUnderstandingResponses([fauxAssistantMessage("DEPENDENCY BOUND BODY")]));
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Stable"), pass("Stable")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await workspace.prompt({ task: "dependency-bound task" }).result).toMatchObject({ status: "completed" });
	await workspace.close();

	const tamperedEntries = (await callerSession.getEntries()).map((entry) => {
		if (
			entry.type !== "custom" ||
			entry.customType !== "cti.orientation.span_receipt/v1" ||
			!isRecord(entry.data) ||
			!Array.isArray(entry.data.dependencies)
		) {
			return entry;
		}
		expect(entry.data.dependencies.map((dependency) => (isRecord(dependency) ? dependency.key : undefined))).toEqual([
			"case_identity",
			"visible_work",
			"visible_object_membership",
		]);
		return {
			...entry,
			data: {
				...entry.data,
				dependencies: entry.data.dependencies.map((dependency, index) =>
					index === 1 && isRecord(dependency)
						? { ...dependency, semanticDigest: "sha256:attacker-recomputed-work" }
						: dependency,
				),
			},
		};
	});
	const tamperedSession = new Session(
		new InMemorySessionStorage({
			metadata: { id: "session-reopen", createdAt: "2026-07-20T00:00:00.000Z" },
			entries: tamperedEntries,
		}),
	);
	const reopenModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Stable"), pass("Stable")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	await expect(
		reopenModule.open({
			caseRef: "case--reopen",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: tamperedSession,
		}),
	).rejects.toMatchObject({ code: "recovery_provenance_untrusted", retryable: false });
});

it("OR0B-RO-06/LR-09 preserves invalidation arriving during reopen and installs only the newer read", async () => {
	const reopenStarted = deferred();
	const releaseFirstReopen = deferred();
	const invalidation = new InMemoryOrientationInvalidationPort();
	const contexts: string[][] = [];
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ro-06", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("newest answer");
			},
		]),
	);
	const firstCandidate = {
		...pass("Intermediate Orientation"),
		onObserve: reopenStarted.resolve,
		waitUntilReleased: releaseFirstReopen.promise,
	};
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [
				pass("Initial Orientation"),
				pass("Initial Orientation"),
				firstCandidate,
				pass("Intermediate Orientation"),
				pass("Newest Orientation"),
				pass("Newest Orientation"),
			],
		}),
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: session(),
	});
	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	const turn = workspace.prompt({ task: "use the newest read" });
	await reopenStarted.promise;
	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 2,
		reason: "case_change_hint",
	});
	releaseFirstReopen.resolve();
	expect(await turn.result).toMatchObject({ status: "completed" });
	expect(contexts[0]?.join("\n")).toContain("Newest Orientation");
	expect(contexts[0]?.join("\n")).not.toContain("Intermediate Orientation");
	await workspace.close();
});

it("OR0B-RO-08 close during an uncooperative reopen returns and fences the late read", async () => {
	const reopenStarted = deferred();
	const releaseReopen = deferred();
	const invalidation = new InMemoryOrientationInvalidationPort();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ro-08" });
	models.setProvider(faux.provider);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [
				pass("Initial Orientation"),
				pass("Initial Orientation"),
				{
					...pass("Late Orientation"),
					onObserve: reopenStarted.resolve,
					waitUntilReleased: releaseReopen.promise,
					ignoreAbort: true,
				},
				pass("Late Orientation"),
			],
		}),
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: session(),
	});
	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	const turn = workspace.prompt({ task: "close during reopen" });
	await reopenStarted.promise;
	await workspace.close();
	expect(await turn.result).toMatchObject({ status: "cancelled" });
	releaseReopen.resolve();
	await Promise.resolve();
	expect(faux.state.callCount).toBe(0);
});

it("OR0B-LR-09 fences an older late reopen success after a newer open has failed", async () => {
	const oldReopenStarted = deferred();
	const releaseOldReopen = deferred();
	const invalidation = new InMemoryOrientationInvalidationPort();
	const contexts: string[][] = [];
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-lr-09", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("fresh answer");
			},
		]),
	);
	const callerSession = session();
	const oldModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [
				pass("Initial"),
				pass("Initial"),
				{
					...pass("LATE OLD ORIENTATION"),
					onObserve: oldReopenStarted.resolve,
					waitUntilReleased: releaseOldReopen.promise,
					ignoreAbort: true,
				},
				pass("LATE OLD ORIENTATION"),
			],
		}),
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const oldWorkspace = await oldModule.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	invalidation.emit({
		caseRef: "case--reopen",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	const oldTurn = oldWorkspace.prompt({ task: "OLD LATE REQUEST" });
	await oldReopenStarted.promise;
	await oldWorkspace.close();
	expect(await oldTurn.result).toMatchObject({ status: "cancelled" });

	const failingModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [{ ...pass("NEW FAILED REQUEST"), failureCode: "transport_timeout" }],
		}),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	await expect(
		failingModule.open({
			caseRef: "case--reopen",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: callerSession,
		}),
	).rejects.toMatchObject({ code: "transport_timeout" });
	releaseOldReopen.resolve();
	await new Promise<void>((resolve) => setImmediate(resolve));

	const freshModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Fresh Final"), pass("Fresh Final")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const freshWorkspace = await freshModule.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await freshWorkspace.prompt({ task: "fresh request" }).result).toMatchObject({ status: "completed" });
	const context = contexts[0]?.join("\n") ?? "";
	expect(context).toContain("Fresh Final");
	expect(context).not.toContain("LATE OLD ORIENTATION");
	expect(context).not.toContain("OLD LATE REQUEST");
	expect(faux.state.callCount).toBe(2);
	await freshWorkspace.close();
});

it("OR0B-RO-03 full binding reopen excludes prose from a different credential scope and target", async () => {
	const contexts: string[][] = [];
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-ro-03", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			fauxAssistantMessage("OLD BINDING ANSWER"),
			(context) => {
				contexts.push(context.messages.map(text));
				return fauxAssistantMessage("new binding answer");
			},
		]),
	);
	const callerSession = session();
	const oldModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [pass("Same Body"), pass("Same Body")] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const oldWorkspace = await oldModule.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--old" },
		sessionRef: callerSession,
	});
	expect(await oldWorkspace.prompt({ task: "OLD BINDING TASK" }).result).toMatchObject({ status: "completed" });
	await oldWorkspace.close();

	const newSource = { ...source, targetFingerprint: "sha256:target-v2" };
	const newModule = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source: newSource,
			passes: [pass("Same Body"), pass("Same Body")],
		}),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const newWorkspace = await newModule.open({
		caseRef: "case--reopen",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--new" },
		sessionRef: callerSession,
	});
	expect(await newWorkspace.prompt({ task: "new binding task" }).result).toMatchObject({ status: "completed" });
	const newContext = contexts[0]?.join("\n") ?? "";
	expect(newContext).toContain('<stale_capsule category="orientation_changed">');
	expect(newContext).not.toContain("OLD BINDING TASK");
	expect(newContext).not.toContain("OLD BINDING ANSWER");
	await newWorkspace.close();
});

it.each([
	{
		name: "credential scope",
		middleSource: source,
		middleCredentialRef: "credential--middle",
	},
	{
		name: "target",
		middleSource: { ...source, targetFingerprint: "sha256:target-middle" },
		middleCredentialRef: "credential--analyst",
	},
	{
		name: "selection",
		middleSource: { ...source, selectionDigest: "sha256:selection-middle" },
		middleCredentialRef: "credential--analyst",
	},
])(
	"OR0B-RO-03 keeps old A prose excluded after clean $name binding A to B to A",
	async ({ middleSource, middleCredentialRef }) => {
		const contexts: string[][] = [];
		const models = createTaskUnderstandingModels();
		const faux = fauxProvider({
			provider: `orientation-ro-sticky-${middleSource.selectionDigest}-${middleCredentialRef}`,
			tokenSize: { min: 100, max: 100 },
		});
		models.setProvider(faux.provider);
		faux.setResponses(
			withTaskUnderstandingResponses([
				fauxAssistantMessage("OLD A PROCESS RESPONSE"),
				fauxAssistantMessage("MIDDLE B PROCESS RESPONSE"),
				(context) => {
					contexts.push(context.messages.map(text));
					return fauxAssistantMessage("NEW A PROCESS RESPONSE");
				},
				(context) => {
					contexts.push(context.messages.map(text));
					return fauxAssistantMessage("NEW A FOLLOWUP RESPONSE");
				},
			]),
		);
		const callerSession = session();
		const openAndComplete = async (
			orientationSource: CaseWorkspaceModuleDependencies["orientation"]["source"],
			credentialRef: string,
			task: string,
		) => {
			const module = createCaseWorkspaceModule({
				orientation: new InMemoryOrientationAdapter({
					source: orientationSource,
					passes: [pass("Same Semantic Body"), pass("Same Semantic Body")],
				}),
				models,
				model: faux.getModel(),
				env: new NodeExecutionEnv({ cwd: process.cwd() }),
			});
			const workspace = await module.open({
				caseRef: "case--reopen",
				accessPrincipal: { principalRef: "identity--analyst", credentialRef },
				sessionRef: callerSession,
			});
			const turn = workspace.prompt({ task });
			const events: WorkspaceEvent[] = [];
			for await (const event of turn) events.push(event);
			expect(await turn.result).toMatchObject({ status: "completed" });
			expect(events.map((event) => event.type)).toEqual([
				"turn_started",
				"context_bound",
				"model_started",
				"model_text_delta",
				"turn_completed",
			]);
			await workspace.close();
		};

		await openAndComplete(source, "credential--analyst", "OLD A PROCESS TASK");
		await openAndComplete(middleSource, middleCredentialRef, "MIDDLE B PROCESS TASK");
		await openAndComplete(source, "credential--analyst", "NEW A PROCESS TASK");
		await openAndComplete(source, "credential--analyst", "NEW A FOLLOWUP TASK");

		const returnedAContext = contexts[0]?.join("\n") ?? "";
		expect(returnedAContext).toContain('<stale_capsule category="orientation_changed">');
		expect(returnedAContext).not.toContain("OLD A PROCESS TASK");
		expect(returnedAContext).not.toContain("OLD A PROCESS RESPONSE");
		expect(returnedAContext).not.toContain("MIDDLE B PROCESS TASK");
		expect(returnedAContext).not.toContain("MIDDLE B PROCESS RESPONSE");
		const followupContext = contexts[1]?.join("\n") ?? "";
		expect(followupContext).toContain("NEW A PROCESS TASK");
		expect(followupContext).toContain("NEW A PROCESS RESPONSE");
		expect(followupContext).not.toContain("OLD A PROCESS TASK");
		expect(followupContext).not.toContain("MIDDLE B PROCESS TASK");
	},
);
