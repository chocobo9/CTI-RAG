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
	type InMemoryOrientationPass,
} from "@earendil-works/pi-cti-rag-agent-workspace/testing";
import { describe, expect, it } from "vitest";
import {
	createTaskUnderstandingModels,
	providerDispatchSecretBinder,
	withTaskUnderstandingResponses,
} from "./task-understanding-fixtures.ts";

const source = {
	instanceId: "opencti-test",
	adapterArtifactDigest: "sha256:adapter-v1",
	targetFingerprint: "sha256:target-v1",
	schemaDigest: "sha256:schema-v1",
	qualificationId: "qualification-test-v1",
	selectionDigest: "sha256:orientation-selection-v1",
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

const expectedOrientationSemanticDigest = "sha256:4103de4388e1e5e7cede0510cbd625df8fecd722d26cb4f45ed2e1841bb5b3cc";

const completePass: InMemoryOrientationPass = {
	caseIdentity: {
		internalId: "case--alpha",
		standardId: "case-incident--alpha",
		entityType: "Case-Incident",
		displayName: "Operation Alpha",
		sourceStatus: { id: "status--open", name: "Open" },
		createdAt: "2026-07-20T00:00:00.000Z",
		observedVersion: { updatedAt: "2026-07-20T01:00:00.000Z", contentDigest: "sha256:case-alpha" },
	},
	workPages: [
		{
			items: [
				{
					taskRef: "task--triage",
					name: "Triage infrastructure",
					sourceStatus: { id: "status--todo", name: "To do" },
					assigneeRefs: ["identity--analyst"],
					observedVersion: { modified: "2026-07-20T01:05:00.000Z", contentDigest: "sha256:task-triage" },
				},
			],
			hasNextPage: false,
			endCursor: "work-end",
			authorization: "valid",
		},
	],
	objectPages: [
		{
			items: [
				{
					objectRef: "indicator--one",
					standardId: "indicator--one",
					entityType: "Indicator",
					displayLabel: "198.51.100.7",
					membership: "visible_case_object_reference",
					observedVersion: { modified: "2026-07-20T01:10:00.000Z", contentDigest: "sha256:indicator-one" },
				},
			],
			hasNextPage: false,
			endCursor: "object-end",
			authorization: "valid",
		},
	],
};

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

function createSession(id: string): Session {
	return new Session(new InMemorySessionStorage({ metadata: { id, createdAt: "2026-07-20T00:00:00.000Z" } }));
}

describe("CaseWorkspaceModule", () => {
	it("WS-PRINCIPAL-01 opens and prompts through the v2 Access Principal Orientation", async () => {
		const models = createTaskUnderstandingModels();
		const faux = fauxProvider({ provider: "orientation-access-principal-v2" });
		models.setProvider(faux.provider);
		faux.setResponses(
			withTaskUnderstandingResponses([fauxAssistantMessage("Access Principal Orientation acknowledged.")]),
		);
		const workspace = await createCaseWorkspaceModule({
			orientation: new InMemoryOrientationAdapter({ source, passes: [completePass, completePass] }),
			models,
			model: faux.getModel(),
			env: new NodeExecutionEnv({ cwd: process.cwd() }),
		}).open({
			caseRef: "case--alpha",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: createSession("session-access-principal-v2"),
		});
		const turn = workspace.prompt({ task: "Summarize the visible Case orientation." });
		const events: WorkspaceEvent[] = [];
		for await (const event of turn) events.push(event);

		expect(await turn.result).toMatchObject({ status: "completed" });
		expect(events).toEqual(
			expect.arrayContaining([
				expect.objectContaining({
					type: "context_bound",
					protocol: "opencti-case-orientation/v2",
				}),
			]),
		);
		await workspace.close();
	});

	it("opens a complete Orientation and binds it temporarily to a real Pi prompt", async () => {
		const capturedModelContexts: string[][] = [];
		const models = createTaskUnderstandingModels();
		const faux = fauxProvider({ provider: "orientation-t1", tokenSize: { min: 100, max: 100 } });
		models.setProvider(faux.provider);
		faux.setResponses(
			withTaskUnderstandingResponses([
				(context) => {
					capturedModelContexts.push(context.messages.map(messageText));
					return fauxAssistantMessage("Orientation acknowledged.");
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
			caseRef: "case--alpha",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: createSession("session-t1"),
		});
		const turn = workspace.prompt({ task: "Summarize the visible Case orientation." });
		const events: WorkspaceEvent[] = [];
		for await (const event of turn) events.push(event);

		expect(events.map((event) => event.type)).toEqual([
			"turn_started",
			"context_bound",
			"model_started",
			"model_text_delta",
			"turn_completed",
		]);
		expect(events[1]).toMatchObject({
			type: "context_bound",
			protocol: "opencti-case-orientation/v2",
			semanticDigest: expectedOrientationSemanticDigest,
		});
		expect(await turn.result).toMatchObject({ status: "completed", message: { stopReason: "stop" } });
		expect(capturedModelContexts).toHaveLength(1);
		expect(capturedModelContexts[0]).toHaveLength(2);
		expect(capturedModelContexts[0][0]).toContain('<case_orientation protocol="opencti-case-orientation/v2"');
		expect(capturedModelContexts[0][0]).toContain(`semantic_digest="${expectedOrientationSemanticDigest}"`);
		expect(capturedModelContexts[0][0]).toContain('"displayName":"Operation Alpha"');
		expect(capturedModelContexts[0][0]).toContain('"membership":"visible_case_object_reference"');
		expect(capturedModelContexts[0][1]).toBe("Summarize the visible Case orientation.");
		await workspace.close();
	});

	it("rejects an Orientation when every selected collection has incomplete pagination", async () => {
		const models = createTaskUnderstandingModels();
		const faux = fauxProvider({ provider: "orientation-t2" });
		models.setProvider(faux.provider);
		const incompletePass: InMemoryOrientationPass = {
			...completePass,
			workPages: [
				{
					items: completePass.workPages[0]?.items ?? [],
					hasNextPage: true,
					endCursor: "work-more",
					authorization: "valid",
				},
			],
			objectPages: [
				{
					items: completePass.objectPages[0]?.items ?? [],
					hasNextPage: true,
					endCursor: "object-more",
					authorization: "valid",
				},
			],
		};
		const module = createCaseWorkspaceModule({
			orientation: new InMemoryOrientationAdapter({ source, passes: [incompletePass, incompletePass] }),
			models,
			model: faux.getModel(),
			env: new NodeExecutionEnv({ cwd: process.cwd() }),
		});

		await expect(
			module.open({
				caseRef: "case--alpha",
				accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
				sessionRef: createSession("session-t2"),
			}),
		).rejects.toMatchObject({
			name: "CaseWorkspaceOpenError",
			code: "orientation_not_usable",
			retryable: true,
			message: "The Case orientation is not usable for this accessPrincipal.",
		});
		expect(faux.state.callCount).toBe(0);
	});

	it("rejects safely when authorization is revoked between pages", async () => {
		const models = createTaskUnderstandingModels();
		const faux = fauxProvider({ provider: "orientation-t3" });
		models.setProvider(faux.provider);
		const revokedPass: InMemoryOrientationPass = {
			...completePass,
			workPages: [
				{
					items: completePass.workPages[0]?.items ?? [],
					hasNextPage: true,
					endCursor: "work-page-1",
					authorization: "valid",
				},
				{
					items: [
						{
							taskRef: "task--protected",
							name: "Protected task must not leak",
							assigneeRefs: [],
							observedVersion: { contentDigest: "sha256:protected-task" },
						},
					],
					hasNextPage: false,
					endCursor: "work-page-2",
					authorization: "revoked",
				},
			],
		};
		const module = createCaseWorkspaceModule({
			orientation: new InMemoryOrientationAdapter({ source, passes: [revokedPass] }),
			models,
			model: faux.getModel(),
			env: new NodeExecutionEnv({ cwd: process.cwd() }),
		});

		let failure: unknown;
		try {
			await module.open({
				caseRef: "case--alpha",
				accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
				sessionRef: createSession("session-t3"),
			});
		} catch (error) {
			failure = error;
		}
		expect(failure).toMatchObject({
			name: "CaseWorkspaceOpenError",
			code: "authorization_or_visibility_changed",
			retryable: false,
			message: "Authorization or visibility changed while the Case orientation was being read.",
		});
		expect(String(failure)).not.toContain("Protected task must not leak");
		expect(String(failure)).not.toContain("task--protected");
		expect(faux.state.callCount).toBe(0);
	});

	it("cancels a partial model stream without contaminating the next Turn", async () => {
		const capturedModelContexts: string[][] = [];
		const models = createTaskUnderstandingModels();
		const faux = fauxProvider({
			provider: "orientation-t4",
			tokensPerSecond: 100,
			tokenSize: { min: 1, max: 1 },
		});
		models.setProvider(faux.provider);
		faux.setResponses(
			withTaskUnderstandingResponses([
				(context) => {
					capturedModelContexts.push(context.messages.map(messageText));
					return fauxAssistantMessage("PARTIAL SECRET RESPONSE THAT MUST NOT SURVIVE CANCELLATION");
				},
				(context) => {
					capturedModelContexts.push(context.messages.map(messageText));
					return fauxAssistantMessage("Clean second response.");
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
			caseRef: "case--alpha",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: createSession("session-t4"),
		});

		const cancelledTurn = workspace.prompt({ task: "First cancelled task must not survive." });
		const cancelledEvents: WorkspaceEvent[] = [];
		for await (const event of cancelledTurn) {
			cancelledEvents.push(event);
			if (event.type === "model_text_delta") cancelledTurn.cancel();
		}
		expect(await cancelledTurn.result).toMatchObject({ status: "cancelled" });
		expect(cancelledEvents.filter((event) => event.type.startsWith("turn_")).map((event) => event.type)).toEqual([
			"turn_started",
			"turn_cancelled",
		]);

		const secondTurn = workspace.prompt({ task: "Second clean task." });
		const secondEvents: WorkspaceEvent[] = [];
		for await (const event of secondTurn) secondEvents.push(event);
		expect(await secondTurn.result).toMatchObject({ status: "completed" });
		expect(secondEvents.at(-1)).toMatchObject({ type: "turn_completed" });
		expect(capturedModelContexts).toHaveLength(2);
		expect(capturedModelContexts[1]).toHaveLength(2);
		expect(capturedModelContexts[1]?.join("\n")).not.toContain("First cancelled task must not survive.");
		expect(capturedModelContexts[1]?.join("\n")).not.toContain("PARTIAL SECRET RESPONSE");
		expect(capturedModelContexts[1]?.at(-1)).toBe("Second clean task.");
		await workspace.close();
	});

	it.each([
		{
			name: "unknown member",
			pass: { ...completePass, unsafeObservationFields: { internalDebug: "protected-shape-secret" } },
			secret: "protected-shape-secret",
		},
		{
			name: "lone surrogate",
			pass: { ...completePass, unsafeCaseIdentityOverrides: { displayName: "\ud800protected-unicode-secret" } },
			secret: "protected-unicode-secret",
		},
		{
			name: "non-finite number",
			pass: { ...completePass, unsafeCaseIdentityOverrides: { displayName: Number.POSITIVE_INFINITY } },
			secret: "Infinity",
		},
	])("rejects a schema mismatch before publication: $name", async ({ pass, secret }) => {
		const models = createTaskUnderstandingModels();
		const faux = fauxProvider({ provider: `orientation-t5-${secret}` });
		models.setProvider(faux.provider);
		faux.setResponses([fauxAssistantMessage("poison response must not run")]);
		const module = createCaseWorkspaceModule({
			orientation: new InMemoryOrientationAdapter({ source, passes: [pass, pass] }),
			models,
			model: faux.getModel(),
			env: new NodeExecutionEnv({ cwd: process.cwd() }),
		});

		let failure: unknown;
		try {
			await module.open({
				caseRef: "case--alpha",
				accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
				sessionRef: createSession(`session-t5-${secret}`),
			});
		} catch (error) {
			failure = error;
		}
		expect(failure).toMatchObject({
			name: "CaseWorkspaceOpenError",
			code: "schema_or_mapping_mismatch",
			retryable: false,
			message: "The Case orientation does not match the qualified contract.",
		});
		expect(String(failure)).not.toContain(secret);
		expect(faux.state.callCount).toBe(0);
	});
});
