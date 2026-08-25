import { InMemorySessionStorage, type PendingSessionWrite, Session } from "@earendil-works/pi-agent-core";
import { NodeExecutionEnv } from "@earendil-works/pi-agent-core/node";
import { fauxAssistantMessage, fauxProvider, type Message } from "@earendil-works/pi-ai";
import {
	type CaseWorkspace,
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
	instanceId: "opencti-lifecycle",
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

const completePass: InMemoryOrientationPass = {
	caseIdentity: {
		internalId: "case--lifecycle",
		entityType: "Case-Incident",
		displayName: "Lifecycle Case",
		observedVersion: { contentDigest: "sha256:case-lifecycle" },
	},
	workPages: [{ items: [], hasNextPage: false, authorization: "valid" }],
	objectPages: [{ items: [], hasNextPage: false, authorization: "valid" }],
};

function createSession(id: string): Session {
	return new Session(new InMemorySessionStorage({ metadata: { id, createdAt: "2026-07-20T00:00:00.000Z" } }));
}

function messageText(message: Message): string {
	if (message.role === "user") {
		if (typeof message.content === "string") return message.content;
		return message.content.flatMap((part) => (part.type === "text" ? [part.text] : [])).join("");
	}
	if (message.role === "assistant") {
		return message.content.flatMap((part) => (part.type === "text" ? [part.text] : [])).join("");
	}
	return "";
}

function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
	let resolve: ((value: T) => void) | undefined;
	const promise = new Promise<T>((settle) => {
		resolve = settle;
	});
	return { promise, resolve: resolve! };
}

class ReceiptRaceSession extends Session {
	onBeforeBatchAppend: (() => void) | undefined;

	override async appendBatchIfLeaf(
		expectedLeafId: string | null,
		entries: readonly PendingSessionWrite[],
	): Promise<readonly string[] | undefined> {
		if (this.onBeforeBatchAppend && entries.some((entry) => entry.type === "message")) {
			const callback = this.onBeforeBatchAppend;
			this.onBeforeBatchAppend = undefined;
			callback();
		}
		return super.appendBatchIfLeaf(expectedLeafId, entries);
	}
}

it("OR0B-LR-08 gives every event stable identities and one increasing sequence", async () => {
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-lr-08", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(withTaskUnderstandingResponses([fauxAssistantMessage("done")]));
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [completePass, completePass] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: createSession("session-lr-08"),
	});

	const turn = workspace.prompt({ task: "complete" });
	const events: WorkspaceEvent[] = [];
	for await (const event of turn) events.push(event);
	const result = await turn.result;

	expect(turn.id).toBe(result.turnId);
	expect(events.map((event) => event.eventSequence)).toEqual([1, 2, 3, 4, 5]);
	expect(new Set(events.map((event) => event.operationId))).toEqual(new Set([result.operationId]));
	expect(new Set(events.map((event) => event.turnId))).toEqual(new Set([turn.id]));
	expect(events.at(-1)?.type).toBe("turn_completed");
	expect(result.status).toBe("completed");
	turn.cancel();
	expect(await turn.result).toEqual(result);
	await workspace.close();
});

it("OR0B-LR-03 supersedes an older Turn and excludes its late response from the next context", async () => {
	const contexts: string[][] = [];
	const firstStarted = deferred<void>();
	const firstResponse = deferred<ReturnType<typeof fauxAssistantMessage>>();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-lr-03", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(messageText));
				firstStarted.resolve();
				return firstResponse.promise;
			},
			(context) => {
				contexts.push(context.messages.map(messageText));
				return fauxAssistantMessage("second complete");
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [completePass, completePass] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: createSession("session-lr-03"),
	});
	const oldTurn = workspace.prompt({ task: "old task must not survive" });
	await firstStarted.promise;
	const newTurn = workspace.prompt({ task: "new task" });

	expect(await oldTurn.result).toMatchObject({ status: "discarded", reason: "turn_superseded" });
	expect(await newTurn.result).toMatchObject({ status: "completed" });
	firstResponse.resolve(fauxAssistantMessage("late old secret"));
	await Promise.resolve();
	expect(contexts[1]?.join("\n")).not.toContain("old task must not survive");
	expect(contexts[1]?.join("\n")).not.toContain("late old secret");
	const oldEvents: WorkspaceEvent[] = [];
	for await (const event of oldTurn) oldEvents.push(event);
	expect(oldEvents.filter((event) => event.type.startsWith("turn_")).map((event) => event.type)).toEqual([
		"turn_started",
		"turn_discarded",
	]);
	await workspace.close();
});

it("OR0B-LR-04 close settles without waiting for a provider that ignores cancellation", async () => {
	const started = deferred<void>();
	const response = deferred<ReturnType<typeof fauxAssistantMessage>>();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-lr-04" });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			async () => {
				started.resolve();
				return response.promise;
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [completePass, completePass] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: createSession("session-lr-04"),
	});
	const turn = workspace.prompt({ task: "hang" });
	await started.promise;
	await workspace.close();
	expect(await turn.result).toMatchObject({ status: "discarded", reason: "workspace_closed" });
	response.resolve(fauxAssistantMessage("late close response"));
	await Promise.resolve();
	const events: WorkspaceEvent[] = [];
	for await (const event of turn) events.push(event);
	expect(events.filter((event) => event.type.startsWith("turn_")).map((event) => event.type)).toEqual([
		"turn_started",
		"turn_discarded",
	]);
});

it("OR0B-LR-01/LR-02 cancellation settles once and late success remains audit-only", async () => {
	const started = deferred<void>();
	const response = deferred<ReturnType<typeof fauxAssistantMessage>>();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-lr-01" });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			async () => {
				started.resolve();
				return response.promise;
			},
		]),
	);
	const session = createSession("session-lr-01");
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [completePass, completePass] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: session,
	});
	const turn = workspace.prompt({ task: "cancel me" });
	await started.promise;
	turn.cancel();
	expect(await turn.result).toMatchObject({ status: "cancelled" });
	response.resolve(fauxAssistantMessage("late cancelled secret"));
	await Promise.resolve();
	const events: WorkspaceEvent[] = [];
	for await (const event of turn) events.push(event);
	expect(events.filter((event) => event.type.startsWith("turn_")).map((event) => event.type)).toEqual([
		"turn_started",
		"turn_cancelled",
	]);
	expect((await session.getEntries()).filter((entry) => entry.type === "message")).toHaveLength(0);
	await workspace.close();
});

it("OR0B-LR-06 discards a completed candidate after Orientation invalidation and keeps the next context clean", async () => {
	const contexts: string[][] = [];
	const started = deferred<void>();
	const response = deferred<ReturnType<typeof fauxAssistantMessage>>();
	const invalidation = new InMemoryOrientationInvalidationPort();
	const changedPass: InMemoryOrientationPass = {
		...completePass,
		caseIdentity: { ...completePass.caseIdentity, displayName: "Changed Lifecycle Case" },
	};
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-lr-06", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(messageText));
				started.resolve();
				return response.promise;
			},
			(context) => {
				contexts.push(context.messages.map(messageText));
				return fauxAssistantMessage("clean after invalidation");
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [completePass, completePass, changedPass, changedPass],
		}),
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: createSession("session-lr-06"),
	});
	const staleTurn = workspace.prompt({ task: "STALE IN-FLIGHT TASK" });
	await started.promise;
	invalidation.emit({
		caseRef: "case--lifecycle",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	response.resolve(fauxAssistantMessage("STALE COMPLETED RESPONSE"));
	expect(await staleTurn.result).toMatchObject({ status: "discarded", reason: "orientation_invalidated" });
	const nextTurn = workspace.prompt({ task: "fresh task" });
	expect(await nextTurn.result).toMatchObject({ status: "completed" });
	const nextContext = contexts[1]?.join("\n") ?? "";
	expect(nextContext).toContain("Changed Lifecycle Case");
	expect(nextContext).not.toContain("STALE IN-FLIGHT TASK");
	expect(nextContext).not.toContain("STALE COMPLETED RESPONSE");
	await workspace.close();
});

it("OR0B-LR-06 rejects a candidate when the caller Session head changes before completion", async () => {
	const started = deferred<void>();
	const response = deferred<ReturnType<typeof fauxAssistantMessage>>();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-lr-session" });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			async () => {
				started.resolve();
				return response.promise;
			},
		]),
	);
	const callerSession = createSession("session-lr-session");
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [completePass, completePass] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	const turn = workspace.prompt({ task: "candidate with old head" });
	await started.promise;
	await callerSession.appendCustomEntry("external.audit", { changed: true });
	response.resolve(fauxAssistantMessage("candidate must be fenced"));
	expect(await turn.result).toMatchObject({ status: "discarded", reason: "session_binding_changed" });
	await workspace.close();
});

it("OR0B-LR-07/IF-03 keeps a disjoint Workspace and its qualified prose usable", async () => {
	const staleStarted = deferred<void>();
	const staleResponse = deferred<ReturnType<typeof fauxAssistantMessage>>();
	const invalidation = new InMemoryOrientationInvalidationPort();
	const modelsA = createTaskUnderstandingModels();
	const fauxA = fauxProvider({ provider: "orientation-disjoint-a" });
	modelsA.setProvider(fauxA.provider);
	fauxA.setResponses(
		withTaskUnderstandingResponses([
			async () => {
				staleStarted.resolve();
				return staleResponse.promise;
			},
		]),
	);
	const moduleA = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [completePass, completePass, completePass, completePass],
		}),
		invalidation,
		models: modelsA,
		model: fauxA.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspaceA = await moduleA.open({
		caseRef: "case--a",
		accessPrincipal: { principalRef: "identity--a", credentialRef: "credential--a" },
		sessionRef: createSession("session-disjoint-a"),
	});

	const contextsB: string[][] = [];
	const modelsB = createTaskUnderstandingModels();
	const fauxB = fauxProvider({ provider: "orientation-disjoint-b", tokenSize: { min: 100, max: 100 } });
	modelsB.setProvider(fauxB.provider);
	fauxB.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contextsB.push(context.messages.map(messageText));
				return fauxAssistantMessage("B QUALIFIED HISTORY");
			},
			(context) => {
				contextsB.push(context.messages.map(messageText));
				return fauxAssistantMessage("B remains usable");
			},
		]),
	);
	const moduleB = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [completePass, completePass] }),
		models: modelsB,
		model: fauxB.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspaceB = await moduleB.open({
		caseRef: "case--b",
		accessPrincipal: { principalRef: "identity--b", credentialRef: "credential--b" },
		sessionRef: createSession("session-disjoint-b"),
	});
	expect(await workspaceB.prompt({ task: "B QUALIFIED TASK" }).result).toMatchObject({ status: "completed" });

	const staleTurn = workspaceA.prompt({ task: "A stale task" });
	await staleStarted.promise;
	invalidation.emit({
		caseRef: "case--a",
		principalRef: "identity--a",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	staleResponse.resolve(fauxAssistantMessage("A stale response"));
	expect(await staleTurn.result).toMatchObject({ status: "discarded" });
	expect(await workspaceB.prompt({ task: "B next task" }).result).toMatchObject({ status: "completed" });
	expect(contextsB[1]?.join("\n")).toContain("B QUALIFIED TASK");
	expect(contextsB[1]?.join("\n")).toContain("B QUALIFIED HISTORY");

	await workspaceA.close();
	await workspaceB.close();
});

it("OR0B-LR-05/LR-08 settles a model error once and ignores a later cancel", async () => {
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-lr-05" });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([fauxAssistantMessage("safe provider error", { stopReason: "error" })]),
	);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [completePass, completePass] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: createSession("session-lr-05"),
	});
	const turn = workspace.prompt({ task: "error once" });
	const events: WorkspaceEvent[] = [];
	for await (const event of turn) events.push(event);
	const beforeCancel = await turn.result;
	turn.cancel();
	const afterCancel = await turn.result;
	expect(beforeCancel).toMatchObject({ status: "failed", failure: { code: "model_failed" } });
	expect(afterCancel).toEqual(beforeCancel);
	expect(events.filter((event) => event.type.startsWith("turn_")).map((event) => event.type)).toEqual([
		"turn_started",
		"turn_failed",
	]);
	await workspace.close();
});

it("OR0B-LR-05 settles cancellation once and ignores a later model error", async () => {
	const started = deferred<void>();
	const response = deferred<ReturnType<typeof fauxAssistantMessage>>();
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-lr-05-late-error" });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			async () => {
				started.resolve();
				return response.promise;
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [completePass, completePass] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: createSession("session-lr-05-late-error"),
	});
	const turn = workspace.prompt({ task: "cancel before provider error" });
	await started.promise;
	turn.cancel();
	const cancelled = await turn.result;
	response.resolve(fauxAssistantMessage("late error body", { stopReason: "error" }));
	await Promise.resolve();
	expect(await turn.result).toEqual(cancelled);
	const events: WorkspaceEvent[] = [];
	for await (const event of turn) events.push(event);
	expect(events.filter((event) => event.type.startsWith("turn_")).map((event) => event.type)).toEqual([
		"turn_started",
		"turn_cancelled",
	]);
	await workspace.close();
});

it("OR0B-IF-01 keeps refresh, reconcile, and status out of the public Workspace Interface", async () => {
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-if-01" });
	models.setProvider(faux.provider);
	faux.setResponses(withTaskUnderstandingResponses([fauxAssistantMessage("done")]));
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({ source, passes: [completePass, completePass] }),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: createSession("session-if-01"),
	});
	expect("prompt" in workspace).toBe(true);
	expect("close" in workspace).toBe(true);
	expect("refresh" in workspace).toBe(false);
	expect("reconcile" in workspace).toBe(false);
	expect("status" in workspace).toBe(false);
	const turn = workspace.prompt({ task: "public shape" });
	expect(turn.id).toEqual(expect.any(String));
	expect(await turn.result).toMatchObject({ status: "completed", turnId: turn.id });
	await workspace.close();
});

it("linearizes a complete span before a close racing the atomic Session commit", async () => {
	const contexts: string[][] = [];
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: "orientation-completion-race", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			fauxAssistantMessage("RACED ASSISTANT BODY"),
			(context) => {
				contexts.push(context.messages.map(messageText));
				return fauxAssistantMessage("reopened safely");
			},
		]),
	);
	const callerSession = new ReceiptRaceSession(
		new InMemorySessionStorage({
			metadata: { id: "session-completion-race", createdAt: "2026-07-20T00:00:00.000Z" },
		}),
	);
	const module = createCaseWorkspaceModule({
		orientation: new InMemoryOrientationAdapter({
			source,
			passes: [completePass, completePass, completePass, completePass],
		}),
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	let workspace: CaseWorkspace | undefined;
	let closePromise: Promise<void> | undefined;
	workspace = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	callerSession.onBeforeBatchAppend = () => {
		closePromise = workspace?.close();
	};

	const racedTurn = workspace.prompt({ task: "RACED USER BODY" });
	expect(await racedTurn.result).toMatchObject({ status: "completed" });
	await closePromise;

	const reopened = await module.open({
		caseRef: "case--lifecycle",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await reopened.prompt({ task: "continue after raced close" }).result).toMatchObject({ status: "completed" });
	const reopenedContext = contexts[0]?.join("\n") ?? "";
	expect(reopenedContext).toContain("RACED USER BODY");
	expect(reopenedContext).toContain("RACED ASSISTANT BODY");
	await reopened.close();
});
