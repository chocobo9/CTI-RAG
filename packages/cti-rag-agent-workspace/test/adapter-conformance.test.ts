import { InMemorySessionStorage, Session } from "@earendil-works/pi-agent-core";
import { NodeExecutionEnv } from "@earendil-works/pi-agent-core/node";
import { fauxAssistantMessage, fauxProvider, type Message } from "@earendil-works/pi-ai";
import {
	type CaseWorkspaceModuleDependencies,
	createCaseWorkspaceModule as createCaseWorkspaceModuleBase,
	OpenCtiTransportOrientationAdapter,
	type OrientationReadPort,
	type WorkspaceEvent,
} from "@earendil-works/pi-cti-rag-agent-workspace";
import {
	HmacSessionReceiptAuthenticator,
	InMemoryOrientationAdapter,
	InMemoryOrientationInvalidationPort,
	type InMemoryOrientationPass,
	ScriptedOpenCtiOrientationTransport,
	type ScriptedTransportPass,
} from "@earendil-works/pi-cti-rag-agent-workspace/testing";
import { expect, it } from "vitest";
import type { OpenCtiCaseIdentityV1, OpenCtiVisibleObjectMembershipV1, OpenCtiVisibleWorkV1 } from "../src/types.ts";
import {
	createTaskUnderstandingModels,
	providerDispatchSecretBinder,
	withTaskUnderstandingResponses,
} from "./task-understanding-fixtures.ts";

const source = {
	instanceId: "opencti-conformance",
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

const caseIdentity = {
	internalId: "case--conformance",
	entityType: "Case-Incident" as const,
	displayName: "Conformance Case",
	observedVersion: { contentDigest: "sha256:case-conformance" },
};

const workOne = {
	taskRef: "task--one",
	name: "First task",
	assigneeRefs: [],
	observedVersion: { contentDigest: "sha256:task-one" },
};

const workTwo = {
	taskRef: "task--two",
	name: "Second task",
	assigneeRefs: [],
	observedVersion: { contentDigest: "sha256:task-two" },
};

interface SemanticPage<T> {
	pageId: string;
	pageIndex: number;
	afterCursor: string | null;
	endCursor: string | null;
	hasNextPage: boolean;
	authorization: "valid" | "revoked";
	items: readonly ({ authorization: "authorized"; value: T } | { authorization: "denied"; value: T })[];
}

interface SemanticAdapterPass {
	caseIdentity: OpenCtiCaseIdentityV1;
	endCaseIdentity?: OpenCtiCaseIdentityV1;
	endAuthorization?: "valid" | "revoked";
	failure?: "transport_timeout" | "case_root_not_found_or_not_visible";
	workPages: readonly SemanticPage<OpenCtiVisibleWorkV1>[];
	objectPages: readonly SemanticPage<OpenCtiVisibleObjectMembershipV1>[];
}

function memoryFixture(fixture: SemanticAdapterPass): InMemoryOrientationPass {
	return {
		caseIdentity: fixture.caseIdentity,
		endCaseIdentity: fixture.endCaseIdentity,
		endAuthorization: fixture.endAuthorization,
		failureCode: fixture.failure,
		workPages: fixture.workPages.map((page) => ({
			items: page.items.map((item) => item.value),
			itemAuthorizations: page.items.map((item) => item.authorization),
			pageId: page.pageId,
			pageIndex: page.pageIndex,
			afterCursor: page.afterCursor,
			endCursor: page.endCursor ?? undefined,
			hasNextPage: page.hasNextPage,
			authorization: page.authorization,
		})),
		objectPages: fixture.objectPages.map((page) => ({
			items: page.items.map((item) => item.value),
			itemAuthorizations: page.items.map((item) => item.authorization),
			pageId: page.pageId,
			pageIndex: page.pageIndex,
			afterCursor: page.afterCursor,
			endCursor: page.endCursor ?? undefined,
			hasNextPage: page.hasNextPage,
			authorization: page.authorization,
		})),
	};
}

function transportFixture(fixture: SemanticAdapterPass): ScriptedTransportPass {
	const root = fixture.failure
		? fixture.failure === "transport_timeout"
			? { outcome: "timeout" }
			: { outcome: "not_visible" as const }
		: { outcome: "visible" as const, authorizationVersion: "auth-1", item: fixture.caseIdentity };
	return {
		root,
		endRoot:
			fixture.endAuthorization === "revoked"
				? { outcome: "not_visible" }
				: fixture.endCaseIdentity
					? { outcome: "visible", authorizationVersion: "auth-1", item: fixture.endCaseIdentity }
					: undefined,
		workPages: fixture.workPages.map((page) => ({
			outcome: "page" as const,
			pageId: page.pageId,
			pageIndex: page.pageIndex,
			afterCursor: page.afterCursor,
			endCursor: page.endCursor,
			hasNextPage: page.hasNextPage,
			authorizationVersion: page.authorization === "valid" ? "auth-1" : "auth-revoked",
			items: page.items.map((item) =>
				item.authorization === "authorized"
					? { authorization: "authorized" as const, value: item.value }
					: { authorization: "denied" as const },
			),
		})),
		objectPages: fixture.objectPages.map((page) => ({
			outcome: "page" as const,
			pageId: page.pageId,
			pageIndex: page.pageIndex,
			afterCursor: page.afterCursor,
			endCursor: page.endCursor,
			hasNextPage: page.hasNextPage,
			authorizationVersion: page.authorization === "valid" ? "auth-1" : "auth-revoked",
			items: page.items.map((item) =>
				item.authorization === "authorized"
					? { authorization: "authorized" as const, value: item.value }
					: { authorization: "denied" as const },
			),
		})),
	};
}

const completeSemanticFixture: SemanticAdapterPass = {
	caseIdentity,
	workPages: [
		{
			pageId: "work-page-1",
			pageIndex: 0,
			afterCursor: null,
			endCursor: "work-1",
			hasNextPage: true,
			authorization: "valid",
			items: [{ authorization: "authorized", value: workOne }],
		},
		{
			pageId: "work-page-2",
			pageIndex: 1,
			afterCursor: "work-1",
			endCursor: "work-2",
			hasNextPage: false,
			authorization: "valid",
			items: [{ authorization: "authorized", value: workTwo }],
		},
	],
	objectPages: [
		{
			pageId: "object-page-1",
			pageIndex: 0,
			afterCursor: null,
			endCursor: null,
			hasNextPage: false,
			authorization: "valid",
			items: [],
		},
	],
};

const memoryPass = memoryFixture(completeSemanticFixture);
const transportPass = transportFixture(completeSemanticFixture);

function messageText(message: Message): string {
	if (message.role === "user") {
		return typeof message.content === "string"
			? message.content
			: message.content.flatMap((part) => (part.type === "text" ? [part.text] : [])).join("");
	}
	return "";
}

async function run(
	adapter: OrientationReadPort,
	sessionId: string,
): Promise<{ context: string; status: string; events: readonly string[] }> {
	let context = "";
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: `conformance-${sessionId}`, tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(modelContext) => {
				context = modelContext.messages.map(messageText).join("\n");
				return fauxAssistantMessage("done");
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: adapter,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--conformance",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: new Session(
			new InMemorySessionStorage({ metadata: { id: sessionId, createdAt: "2026-07-20T00:00:00.000Z" } }),
		),
	});
	const turn = workspace.prompt({ task: "orient" });
	const events: WorkspaceEvent[] = [];
	for await (const event of turn) events.push(event);
	const result = await turn.result;
	await workspace.close();
	return { context, status: result.status, events: events.map((event) => event.type) };
}

function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
	let resolve: ((value: T) => void) | undefined;
	const promise = new Promise<T>((settle) => {
		resolve = settle;
	});
	return { promise, resolve: resolve! };
}

async function failOpen(
	adapter: OrientationReadPort,
	sessionId: string,
): Promise<{ code: string | undefined; retryable: boolean | undefined; providerCalls: number; text: string }> {
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: `conformance-failure-${sessionId}` });
	models.setProvider(faux.provider);
	const module = createCaseWorkspaceModule({
		orientation: adapter,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	let failure: unknown;
	try {
		await module.open({
			caseRef: "case--conformance",
			accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
			sessionRef: new Session(
				new InMemorySessionStorage({
					metadata: { id: sessionId, createdAt: "2026-07-20T00:00:00.000Z" },
				}),
			),
		});
	} catch (error) {
		failure = error;
	}
	return {
		code:
			typeof failure === "object" && failure !== null && "code" in failure && typeof failure.code === "string"
				? failure.code
				: undefined,
		retryable:
			typeof failure === "object" &&
			failure !== null &&
			"retryable" in failure &&
			typeof failure.retryable === "boolean"
				? failure.retryable
				: undefined,
		providerCalls: faux.state.callCount,
		text: String(failure),
	};
}

it("OR0B-AD-01 gives both Adapter shapes the same complete multi-page public result", async () => {
	const memory = await run(
		new InMemoryOrientationAdapter({ source, passes: [memoryPass, memoryPass] }),
		"session-memory-complete",
	);
	const transport = await run(
		new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({ passes: [transportPass, transportPass] }),
		}),
		"session-transport-complete",
	);
	expect(memory.status).toBe("completed");
	expect(transport.status).toBe("completed");
	expect(transport.context).toBe(memory.context);
	expect(transport.context).toContain("task--one");
	expect(transport.context).toContain("task--two");
});

const conformanceCatalog = [
	{ name: "complete_multi_page", expected: "completed", fixture: completeSemanticFixture },
	{
		name: "missing_final_work_page",
		expected: "completed",
		fixture: { ...completeSemanticFixture, workPages: [completeSemanticFixture.workPages[0]!] },
	},
	{
		name: "root_drift_at_end",
		expected: "observation_drift",
		fixture: {
			...completeSemanticFixture,
			endCaseIdentity: { ...caseIdentity, displayName: "Changed During Traversal" },
		},
	},
	{
		name: "page_authorization_revoked",
		expected: "authorization_or_visibility_changed",
		fixture: {
			...completeSemanticFixture,
			workPages: [
				completeSemanticFixture.workPages[0]!,
				{ ...completeSemanticFixture.workPages[1]!, authorization: "revoked" },
			],
		},
	},
	{
		name: "item_authorization_denied",
		expected: "authorization_or_visibility_changed",
		fixture: {
			...completeSemanticFixture,
			workPages: [
				{
					...completeSemanticFixture.workPages[0]!,
					hasNextPage: false,
					endCursor: null,
					items: [{ authorization: "denied", value: workOne }],
				},
			],
		},
	},
	{
		name: "transport_timeout",
		expected: "transport_timeout",
		fixture: { ...completeSemanticFixture, failure: "transport_timeout" },
	},
] as const satisfies readonly {
	name: string;
	expected: "completed" | "observation_drift" | "authorization_or_visibility_changed" | "transport_timeout";
	fixture: SemanticAdapterPass;
}[];

it("OR0B-AD-13 generates matching success and failure behavior from one closed semantic fixture catalog", async () => {
	for (const catalogEntry of conformanceCatalog) {
		const memoryAdapter = new InMemoryOrientationAdapter({
			source,
			passes:
				catalogEntry.expected === "completed"
					? [memoryFixture(catalogEntry.fixture), memoryFixture(catalogEntry.fixture)]
					: [memoryFixture(catalogEntry.fixture)],
		});
		const transportAdapter = new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({
				passes:
					catalogEntry.expected === "completed"
						? [transportFixture(catalogEntry.fixture), transportFixture(catalogEntry.fixture)]
						: [transportFixture(catalogEntry.fixture)],
			}),
		});
		if (catalogEntry.expected === "completed") {
			const memory = await run(memoryAdapter, `catalog-memory-${catalogEntry.name}`);
			const transport = await run(transportAdapter, `catalog-transport-${catalogEntry.name}`);
			expect(transport, catalogEntry.name).toEqual(memory);
		} else {
			const memory = await failOpen(memoryAdapter, `catalog-memory-${catalogEntry.name}`);
			const transport = await failOpen(transportAdapter, `catalog-transport-${catalogEntry.name}`);
			expect(transport, catalogEntry.name).toEqual(memory);
			expect(memory.code, catalogEntry.name).toBe(catalogEntry.expected);
			expect(memory.providerCalls, catalogEntry.name).toBe(0);
		}
	}
});

it("OR0B-AD-02/AD-11 makes an incomplete page unavailable without leaking its prefix", async () => {
	const incompleteMemory: InMemoryOrientationPass = {
		...memoryPass,
		workPages: [{ items: [workOne], hasNextPage: true, endCursor: "work-more", authorization: "valid" }],
	};
	const incompleteTransport: ScriptedTransportPass = {
		...transportPass,
		workPages: [{ outcome: "incomplete" }],
	};
	const memory = await run(
		new InMemoryOrientationAdapter({ source, passes: [incompleteMemory, incompleteMemory] }),
		"session-memory-incomplete",
	);
	const transport = await run(
		new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({ passes: [incompleteTransport, incompleteTransport] }),
		}),
		"session-transport-incomplete",
	);
	expect(transport).toEqual(memory);
	expect(memory.context).toContain("incomplete_task_traversal");
	expect(memory.context).not.toContain("task--one");

	const objectPrefix = {
		objectRef: "indicator--PROTECTED",
		entityType: "Indicator",
		displayLabel: "PROTECTED OBJECT BODY",
		membership: "visible_case_object_reference" as const,
		observedVersion: { contentDigest: "sha256:protected-object" },
	};
	const objectIncompleteMemory: InMemoryOrientationPass = {
		...memoryPass,
		objectPages: [{ items: [objectPrefix], hasNextPage: true, endCursor: "object-more", authorization: "valid" }],
	};
	const objectIncompleteTransport: ScriptedTransportPass = {
		...transportPass,
		workPages: transportPass.workPages,
		objectPages: [{ outcome: "incomplete" }],
	};
	const memoryObject = await run(
		new InMemoryOrientationAdapter({ source, passes: [objectIncompleteMemory, objectIncompleteMemory] }),
		"session-memory-object-incomplete",
	);
	const transportObject = await run(
		new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({
				passes: [objectIncompleteTransport, objectIncompleteTransport],
			}),
		}),
		"session-transport-object-incomplete",
	);
	expect(transportObject).toEqual(memoryObject);
	expect(memoryObject.context).toContain("incomplete_object_traversal");
	expect(memoryObject.context).not.toContain("PROTECTED OBJECT BODY");
});

it("OR0B-AD-11 makes wholly unprovable selected traversal fail before any provider call", async () => {
	const unusableMemory: InMemoryOrientationPass = {
		...memoryPass,
		workPages: [{ items: [workOne], hasNextPage: true, endCursor: "work-more", authorization: "valid" }],
		objectPages: [{ items: [], hasNextPage: true, endCursor: "object-more", authorization: "valid" }],
	};
	const unusableTransport: ScriptedTransportPass = {
		...transportPass,
		workPages: [{ outcome: "incomplete" }],
		objectPages: [{ outcome: "incomplete" }],
	};
	const failures = await Promise.all([
		failOpen(
			new InMemoryOrientationAdapter({ source, passes: [unusableMemory, unusableMemory] }),
			"session-memory-unusable",
		),
		failOpen(
			new OpenCtiTransportOrientationAdapter({
				source,
				transport: new ScriptedOpenCtiOrientationTransport({ passes: [unusableTransport, unusableTransport] }),
			}),
			"session-transport-unusable",
		),
	]);
	expect(failures[1]).toEqual(failures[0]);
	expect(failures[0]).toMatchObject({ code: "orientation_not_usable", providerCalls: 0 });
	expect(failures[0]?.text).not.toContain("task--one");
});

it("OR0B-AD-03 de-duplicates equal pages and rejects inconsistent duplicates in both Adapters", async () => {
	const memoryPageOne = {
		items: [workOne],
		hasNextPage: true,
		endCursor: "work-1",
		afterCursor: null,
		pageId: "work-page-1",
		pageIndex: 0,
		authorization: "valid" as const,
	};
	const memoryPageTwo = {
		items: [workTwo],
		hasNextPage: false,
		endCursor: "work-2",
		afterCursor: "work-1",
		pageId: "work-page-2",
		pageIndex: 1,
		authorization: "valid" as const,
	};
	const equalMemory: InMemoryOrientationPass = {
		...memoryPass,
		workPages: [memoryPageOne, memoryPageOne, memoryPageTwo],
	};
	const transportPageOne = transportPass.workPages[0]!;
	const transportPageTwo = transportPass.workPages[1]!;
	const equalTransport: ScriptedTransportPass = {
		...transportPass,
		workPages: [transportPageOne, transportPageOne, transportPageTwo],
	};
	const memorySuccess = await run(
		new InMemoryOrientationAdapter({ source, passes: [equalMemory, equalMemory] }),
		"session-memory-duplicate",
	);
	const transportSuccess = await run(
		new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({ passes: [equalTransport, equalTransport] }),
		}),
		"session-transport-duplicate",
	);
	expect(transportSuccess).toEqual(memorySuccess);
	expect(memorySuccess.context.match(/task--one/g)).toHaveLength(1);

	const inconsistentMemory: InMemoryOrientationPass = {
		...memoryPass,
		workPages: [memoryPageOne, { ...memoryPageOne, items: [{ ...workOne, name: "changed duplicate" }] }],
	};
	const inconsistentTransport: ScriptedTransportPass = {
		...transportPass,
		workPages: [
			transportPageOne,
			{
				...(transportPageOne as Exclude<typeof transportPageOne, undefined>),
				items: [{ authorization: "authorized", value: { ...workOne, name: "changed duplicate" } }],
			},
		],
	};
	const memoryFailure = await failOpen(
		new InMemoryOrientationAdapter({ source, passes: [inconsistentMemory] }),
		"session-memory-inconsistent-duplicate",
	);
	const transportFailure = await failOpen(
		new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({ passes: [inconsistentTransport] }),
		}),
		"session-transport-inconsistent-duplicate",
	);
	expect(transportFailure).toEqual(memoryFailure);
	expect(memoryFailure).toMatchObject({ code: "observation_drift", providerCalls: 0 });
});

it("OR0B-AD-04 rejects unexplained page order in both Adapters", async () => {
	const memoryOutOfOrder: InMemoryOrientationPass = {
		...memoryPass,
		workPages: [{ items: [workOne], hasNextPage: false, pageIndex: 1, afterCursor: null, authorization: "valid" }],
	};
	const transportOutOfOrder: ScriptedTransportPass = {
		...transportPass,
		workPages: [
			{
				outcome: "page",
				pageId: "wrong-order",
				pageIndex: 1,
				afterCursor: null,
				endCursor: null,
				hasNextPage: false,
				authorizationVersion: "auth-1",
				items: [{ authorization: "authorized", value: workOne }],
			},
		],
	};
	const memoryFailure = await failOpen(
		new InMemoryOrientationAdapter({ source, passes: [memoryOutOfOrder] }),
		"session-memory-order",
	);
	const transportFailure = await failOpen(
		new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({ passes: [transportOutOfOrder] }),
		}),
		"session-transport-order",
	);
	expect(transportFailure).toEqual(memoryFailure);
	expect(memoryFailure.code).toBe("cursor_continuity_lost");
});

it("OR0B-AD-05/AD-06 fails page and item authorization changes without disclosure", async () => {
	const protectedWork = { ...workTwo, taskRef: "task--PROTECTED", name: "PROTECTED BODY" };
	const memoryRevoked: InMemoryOrientationPass = {
		...memoryPass,
		workPages: [
			{ items: [workOne], hasNextPage: true, endCursor: "work-1", authorization: "valid" },
			{ items: [protectedWork], hasNextPage: false, authorization: "revoked" },
		],
	};
	const transportRevoked: ScriptedTransportPass = {
		...transportPass,
		workPages: [
			transportPass.workPages[0]!,
			{
				outcome: "page",
				pageId: "protected-page",
				pageIndex: 1,
				afterCursor: "work-1",
				endCursor: null,
				hasNextPage: false,
				authorizationVersion: "auth-revoked",
				items: [{ authorization: "authorized", value: protectedWork }],
			},
		],
	};
	const pageFailures = await Promise.all([
		failOpen(new InMemoryOrientationAdapter({ source, passes: [memoryRevoked] }), "session-memory-revoked"),
		failOpen(
			new OpenCtiTransportOrientationAdapter({
				source,
				transport: new ScriptedOpenCtiOrientationTransport({ passes: [transportRevoked] }),
			}),
			"session-transport-revoked",
		),
	]);
	expect(pageFailures[1]).toEqual(pageFailures[0]);
	expect(pageFailures[0]).toMatchObject({ code: "authorization_or_visibility_changed", providerCalls: 0 });
	expect(pageFailures[0]?.text).not.toContain("PROTECTED");

	const memoryDenied: InMemoryOrientationPass = {
		...memoryPass,
		workPages: [
			{ items: [protectedWork], itemAuthorizations: ["denied"], hasNextPage: false, authorization: "valid" },
		],
	};
	const transportDenied: ScriptedTransportPass = {
		...transportPass,
		workPages: [
			{
				outcome: "page",
				pageId: "denied-page",
				pageIndex: 0,
				afterCursor: null,
				endCursor: null,
				hasNextPage: false,
				authorizationVersion: "auth-1",
				items: [{ authorization: "denied" }],
			},
		],
	};
	const itemFailures = await Promise.all([
		failOpen(new InMemoryOrientationAdapter({ source, passes: [memoryDenied] }), "session-memory-denied"),
		failOpen(
			new OpenCtiTransportOrientationAdapter({
				source,
				transport: new ScriptedOpenCtiOrientationTransport({ passes: [transportDenied] }),
			}),
			"session-transport-denied",
		),
	]);
	expect(itemFailures[1]).toEqual(itemFailures[0]);
	expect(itemFailures[0]?.text).not.toContain("PROTECTED");
});

it("OR0B-AD-07 rejects unequal complete observations in both Adapters", async () => {
	const changedMemory = { ...memoryPass, caseIdentity: { ...caseIdentity, displayName: "Changed Case" } };
	const changedTransport = {
		...transportPass,
		root: {
			outcome: "visible" as const,
			authorizationVersion: "auth-1",
			item: { ...caseIdentity, displayName: "Changed Case" },
		},
	};
	const failures = await Promise.all([
		failOpen(new InMemoryOrientationAdapter({ source, passes: [memoryPass, changedMemory] }), "session-memory-drift"),
		failOpen(
			new OpenCtiTransportOrientationAdapter({
				source,
				transport: new ScriptedOpenCtiOrientationTransport({ passes: [transportPass, changedTransport] }),
			}),
			"session-transport-drift",
		),
	]);
	expect(failures[1]).toEqual(failures[0]);
	expect(failures[0]?.code).toBe("observation_drift");
});

it("OR0B-AD-07 rejects root drift during one transport observation after the final page", async () => {
	const driftDuringTraversal: ScriptedTransportPass = {
		...transportPass,
		endRoot: {
			outcome: "visible",
			authorizationVersion: "auth-1",
			item: { ...caseIdentity, displayName: "Changed During Pagination" },
		},
	};
	const failure = await failOpen(
		new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({ passes: [driftDuringTraversal] }),
		}),
		"session-transport-end-root-drift",
	);
	expect(failure).toMatchObject({ code: "observation_drift", providerCalls: 0 });
	expect(failure.text).not.toContain("Changed During Pagination");
});

it("OR0B-AD-08 rejects qualification identity mismatch in both Adapters", async () => {
	const observedSource = { ...source, targetFingerprint: "sha256:unexpected-target" };
	const failures = await Promise.all([
		failOpen(
			new InMemoryOrientationAdapter({ source, observedSource, passes: [memoryPass] }),
			"session-memory-target",
		),
		failOpen(
			new OpenCtiTransportOrientationAdapter({
				source,
				observedSource,
				transport: new ScriptedOpenCtiOrientationTransport({ passes: [transportPass] }),
			}),
			"session-transport-target",
		),
	]);
	expect(failures[1]).toEqual(failures[0]);
	expect(failures[0]?.code).toBe("schema_or_mapping_mismatch");
});

it("OR0B-AD-09 maps timeout to the same retryable accessPrincipal-safe failure", async () => {
	const memoryTimeout = { ...memoryPass, failureCode: "transport_timeout" as const };
	const transportTimeout = { ...transportPass, root: { outcome: "timeout" } };
	const failures = await Promise.all([
		failOpen(new InMemoryOrientationAdapter({ source, passes: [memoryTimeout] }), "session-memory-timeout"),
		failOpen(
			new OpenCtiTransportOrientationAdapter({
				source,
				transport: new ScriptedOpenCtiOrientationTransport({ passes: [transportTimeout] }),
			}),
			"session-transport-timeout",
		),
	]);
	expect(failures[1]).toEqual(failures[0]);
	expect(failures[0]).toMatchObject({ code: "transport_timeout", retryable: true, providerCalls: 0 });
});

async function ignoredCancellation(
	adapter: OrientationReadPort,
	sessionId: string,
): Promise<{
	firstStatus: string;
	secondStatus: string;
	secondContext: string;
}> {
	const started = deferred<void>();
	const late = deferred<ReturnType<typeof fauxAssistantMessage>>();
	let secondContext = "";
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: `conformance-cancel-${sessionId}`, tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			async () => {
				started.resolve();
				return late.promise;
			},
			(context) => {
				secondContext = context.messages.map(messageText).join("\n");
				return fauxAssistantMessage("clean response");
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: adapter,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--conformance",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: new Session(
			new InMemorySessionStorage({ metadata: { id: sessionId, createdAt: "2026-07-20T00:00:00.000Z" } }),
		),
	});
	const first = workspace.prompt({ task: "CANCELLED TRANSPORT-SHAPE TASK" });
	await started.promise;
	first.cancel();
	const firstResult = await first.result;
	late.resolve(fauxAssistantMessage("LATE TRANSPORT-SHAPE RESPONSE"));
	const secondResult = await workspace.prompt({ task: "clean task" }).result;
	await workspace.close();
	return { firstStatus: firstResult.status, secondStatus: secondResult.status, secondContext };
}

it("contains ignored provider cancellation identically for both Adapter shapes", async () => {
	const memory = await ignoredCancellation(
		new InMemoryOrientationAdapter({ source, passes: [memoryPass, memoryPass] }),
		"session-memory-cancel",
	);
	const transport = await ignoredCancellation(
		new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({ passes: [transportPass, transportPass] }),
		}),
		"session-transport-cancel",
	);
	expect(transport).toEqual(memory);
	expect(memory).toMatchObject({ firstStatus: "cancelled", secondStatus: "completed" });
	expect(memory.secondContext).not.toContain("CANCELLED TRANSPORT-SHAPE TASK");
	expect(memory.secondContext).not.toContain("LATE TRANSPORT-SHAPE RESPONSE");
});

async function ignoredAdapterCancellation(
	adapter: OrientationReadPort,
	invalidation: InMemoryOrientationInvalidationPort,
	started: Promise<void>,
	release: () => void,
	sessionId: string,
): Promise<{ resultStatus: string; providerCalls: number }> {
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: `conformance-adapter-cancel-${sessionId}` });
	models.setProvider(faux.provider);
	const module = createCaseWorkspaceModule({
		orientation: adapter,
		invalidation,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const workspace = await module.open({
		caseRef: "case--conformance",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: new Session(
			new InMemorySessionStorage({ metadata: { id: sessionId, createdAt: "2026-07-20T00:00:00.000Z" } }),
		),
	});
	invalidation.emit({
		caseRef: "case--conformance",
		principalRef: "identity--analyst",
		receiptSequence: 1,
		reason: "case_change_hint",
	});
	const turn = workspace.prompt({ task: "must not reach provider" });
	await started;
	await workspace.close();
	const result = await turn.result;
	release();
	await Promise.resolve();
	return { resultStatus: result.status, providerCalls: faux.state.callCount };
}

it("OR0B-AD-10 fences an OpenCTI transport that ignores abort during reread", async () => {
	const memoryStarted = deferred<void>();
	const memoryRelease = deferred<void>();
	const memoryInvalidation = new InMemoryOrientationInvalidationPort();
	const memory = await ignoredAdapterCancellation(
		new InMemoryOrientationAdapter({
			source,
			passes: [
				memoryPass,
				memoryPass,
				{
					...memoryPass,
					onObserve: () => memoryStarted.resolve(),
					waitUntilReleased: memoryRelease.promise,
					ignoreAbort: true,
				},
				memoryPass,
			],
		}),
		memoryInvalidation,
		memoryStarted.promise,
		() => memoryRelease.resolve(),
		"session-memory-adapter-cancel",
	);

	const transportStarted = deferred<void>();
	const transportRelease = deferred<void>();
	const transportInvalidation = new InMemoryOrientationInvalidationPort();
	const transport = await ignoredAdapterCancellation(
		new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({
				passes: [
					transportPass,
					transportPass,
					{
						...transportPass,
						onStart: () => transportStarted.resolve(),
						waitUntilReleased: transportRelease.promise,
						ignoreAbort: true,
					},
					transportPass,
				],
			}),
		}),
		transportInvalidation,
		transportStarted.promise,
		() => transportRelease.resolve(),
		"session-transport-adapter-cancel",
	);
	expect(transport).toEqual(memory);
	expect(memory).toEqual({ resultStatus: "cancelled", providerCalls: 0 });
});

async function processReopen(adapter: OrientationReadPort, sessionId: string): Promise<readonly string[]> {
	const contexts: string[] = [];
	const models = createTaskUnderstandingModels();
	const faux = fauxProvider({ provider: `conformance-reopen-${sessionId}`, tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(messageText).join("\n"));
				return fauxAssistantMessage("old answer");
			},
			(context) => {
				contexts.push(context.messages.map(messageText).join("\n"));
				return fauxAssistantMessage("new answer");
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: adapter,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const callerSession = new Session(
		new InMemorySessionStorage({ metadata: { id: sessionId, createdAt: "2026-07-20T00:00:00.000Z" } }),
	);
	const first = await module.open({
		caseRef: "case--conformance",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await first.prompt({ task: "old task" }).result).toMatchObject({ status: "completed" });
	await first.close();
	const second = await module.open({
		caseRef: "case--conformance",
		accessPrincipal: { principalRef: "identity--analyst", credentialRef: "credential--analyst" },
		sessionRef: callerSession,
	});
	expect(await second.prompt({ task: "new task" }).result).toMatchObject({ status: "completed" });
	await second.close();
	return contexts;
}

it("OR0B-AD-12 process reopen rereads both Adapter shapes instead of resuming cached pages", async () => {
	const newMemoryPass: InMemoryOrientationPass = {
		...memoryPass,
		caseIdentity: { ...caseIdentity, displayName: "Reopened Case" },
	};
	const newTransportPass: ScriptedTransportPass = {
		...transportPass,
		root: {
			outcome: "visible",
			authorizationVersion: "auth-1",
			item: { ...caseIdentity, displayName: "Reopened Case" },
		},
	};
	const memory = await processReopen(
		new InMemoryOrientationAdapter({
			source,
			passes: [memoryPass, memoryPass, newMemoryPass, newMemoryPass],
		}),
		"session-memory-reopen",
	);
	const transport = await processReopen(
		new OpenCtiTransportOrientationAdapter({
			source,
			transport: new ScriptedOpenCtiOrientationTransport({
				passes: [transportPass, transportPass, newTransportPass, newTransportPass],
			}),
		}),
		"session-transport-reopen",
	);
	expect(transport).toEqual(memory);
	expect(memory[1]).toContain("Reopened Case");
	expect(memory[1]).not.toContain("old answer");
});
