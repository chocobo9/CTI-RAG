import { Buffer } from "node:buffer";
import { randomUUID } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { InMemorySessionStorage, Session } from "@earendil-works/pi-agent-core";
import { NodeExecutionEnv } from "@earendil-works/pi-agent-core/node";
import { createModels, fauxAssistantMessage, fauxProvider, type Message } from "@earendil-works/pi-ai";
import { createCaseWorkspaceModule } from "@earendil-works/pi-cti-rag-agent-workspace";
import { expect, it } from "vitest";
import {
	createNodeHmacSessionReceiptAuthenticator,
	OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
	qualifyOpenCtiLiveOrientation,
	runOpenCtiCaseSmoke,
	runOpenCtiCaseSmokeCli,
} from "../src/node.ts";
import { providerDispatchSecretBinder, withTaskUnderstandingResponses } from "./task-understanding-fixtures.ts";

type JsonRecord = Readonly<Record<string, unknown>>;

function jsonResponse(data: unknown, init?: ResponseInit): Response {
	return new Response(JSON.stringify(data), {
		status: init?.status ?? 200,
		headers: { "content-type": "application/json" },
	});
}

function operation(
	request: Parameters<typeof fetch>[0],
	init?: RequestInit,
): { name: string; query: string; variables: JsonRecord } {
	if (typeof request !== "string" || request !== "https://opencti.example/graphql") {
		throw new Error("Unexpected endpoint");
	}
	const body = JSON.parse(String(init?.body)) as { operationName?: unknown; query?: unknown; variables?: unknown };
	if (typeof body.operationName !== "string" || typeof body.query !== "string") {
		throw new Error("Missing operation name or query");
	}
	return {
		name: body.operationName,
		query: body.query,
		variables: typeof body.variables === "object" && body.variables !== null ? (body.variables as JsonRecord) : {},
	};
}

const me = {
	id: "identity--analyst",
	capabilities: [{ name: "KNOWLEDGE" }],
	allowed_marking: [{ id: "marking--tlp-green" }],
};

const caseAuthorization = {
	id: "case--alpha",
	authorized_members_activation_date: null,
	currentUserAccessRight: "admin",
	objectMarking: [{ id: "marking--tlp-green" }],
	objectOrganization: [{ id: "organization--blue" }],
};

const caseIdentity = {
	...caseAuthorization,
	standard_id: "case-incident--alpha",
	entity_type: "Case-Incident",
	name: "Operation Alpha",
	created_at: "2026-07-20T00:00:00.000Z",
	updated_at: "2026-07-20T01:00:00.000Z",
	modified: "2026-07-20T01:00:00.000Z",
	status: { id: "status--open", template: { name: "Open" } },
};

function selectedType(
	kind: string,
	fields: readonly string[] = [],
	args: Readonly<Record<string, readonly string[]>> = {},
) {
	return {
		kind,
		fields: fields.map((name) => ({ name, args: (args[name] ?? []).map((argument) => ({ name: argument })) })),
		enumValues: null,
		possibleTypes: null,
	};
}

const qualificationData = {
	about: { version: "6.8.1" },
	settings: { id: "settings--instance", platform_url: "https://opencti.example" },
	me,
};

const nameOnlySchemaData = {
	queryType: selectedType("OBJECT", ["about", "settings", "me", "case", "tasks"], {
		case: ["id"],
		tasks: ["first", "after", "orderBy", "orderMode", "filters"],
	}),
	appInfoType: selectedType("OBJECT", ["version"]),
	settingsType: selectedType("OBJECT", ["id", "platform_url"]),
	caseType: selectedType(
		"INTERFACE",
		[
			"id",
			"standard_id",
			"entity_type",
			"name",
			"created_at",
			"updated_at",
			"modified",
			"status",
			"authorized_members_activation_date",
			"currentUserAccessRight",
			"objectMarking",
			"objectOrganization",
			"objects",
		],
		{ objects: ["first", "after", "orderBy", "orderMode"] },
	),
	taskType: selectedType("OBJECT", [
		"id",
		"standard_id",
		"entity_type",
		"name",
		"created_at",
		"updated_at",
		"modified",
		"due_date",
		"status",
		"objectAssignee",
	]),
	meType: selectedType("OBJECT", ["id", "capabilities", "allowed_marking"]),
	capabilityType: selectedType("OBJECT", ["name"]),
	markingDefinitionType: selectedType("OBJECT", ["id"]),
	organizationType: selectedType("OBJECT", ["id"]),
	statusType: selectedType("OBJECT", ["id", "template"]),
	statusTemplateType: selectedType("OBJECT", ["name"]),
	assigneeType: selectedType("OBJECT", ["id"]),
	taskConnectionType: selectedType("OBJECT", ["pageInfo", "edges"]),
	taskEdgeType: selectedType("OBJECT", ["cursor", "node"]),
	objectConnectionType: selectedType("OBJECT", ["pageInfo", "edges"]),
	objectEdgeType: selectedType("OBJECT", ["cursor", "types", "node"]),
	pageInfoType: selectedType("OBJECT", ["endCursor", "hasNextPage"]),
	stixObjectType: {
		...selectedType("INTERFACE", ["id", "standard_id", "entity_type", "representative", "updated_at"]),
		possibleTypes: [{ name: "Indicator" }],
	},
	stixRelationshipType: {
		...selectedType("INTERFACE", ["id", "standard_id", "entity_type", "representative", "updated_at"]),
		possibleTypes: [{ name: "StixCoreRelationship" }],
	},
	representativeType: selectedType("OBJECT", ["main"]),
	objectUnionType: {
		kind: "UNION",
		fields: null,
		enumValues: null,
		possibleTypes: [{ name: "Indicator" }, { name: "StixCoreRelationship" }],
	},
	tasksOrderingType: { kind: "ENUM", fields: null, enumValues: [{ name: "created_at" }], possibleTypes: null },
	objectOrderingType: { kind: "ENUM", fields: null, enumValues: [{ name: "created_at" }], possibleTypes: null },
	orderingModeType: { kind: "ENUM", fields: null, enumValues: [{ name: "asc" }], possibleTypes: null },
	filterModeType: {
		kind: "ENUM",
		fields: null,
		enumValues: [{ name: "and" }, { name: "or" }],
		possibleTypes: null,
	},
	filterOperatorType: { kind: "ENUM", fields: null, enumValues: [{ name: "eq" }], possibleTypes: null },
	filterGroupType: {
		kind: "INPUT_OBJECT",
		inputFields: [{ name: "mode" }, { name: "filters" }, { name: "filterGroups" }],
	},
	filterType: {
		kind: "INPUT_OBJECT",
		inputFields: [{ name: "key" }, { name: "values" }, { name: "operator" }, { name: "mode" }],
	},
};

const testTypeKinds: Readonly<Record<string, string>> = {
	Any: "SCALAR",
	AppInfo: "OBJECT",
	Assignee: "OBJECT",
	Boolean: "SCALAR",
	Capability: "OBJECT",
	Case: "INTERFACE",
	DateTime: "SCALAR",
	Filter: "INPUT_OBJECT",
	FilterGroup: "INPUT_OBJECT",
	FilterMode: "ENUM",
	FilterOperator: "ENUM",
	ID: "SCALAR",
	Int: "SCALAR",
	MarkingDefinition: "OBJECT",
	MeUser: "OBJECT",
	OrderingMode: "ENUM",
	Organization: "OBJECT",
	PageInfo: "OBJECT",
	Representative: "OBJECT",
	Settings: "OBJECT",
	Status: "OBJECT",
	StatusTemplate: "OBJECT",
	StixObjectOrStixRelationship: "UNION",
	StixObjectOrStixRelationshipRefConnection: "OBJECT",
	StixObjectOrStixRelationshipRefEdge: "OBJECT",
	String: "SCALAR",
	Task: "OBJECT",
	TaskConnection: "OBJECT",
	TaskEdge: "OBJECT",
	TasksOrdering: "ENUM",
	StixObjectOrStixRelationshipsOrdering: "ENUM",
};

function testTypeRef(signature: string): JsonRecord {
	if (signature.endsWith("!")) {
		return { kind: "NON_NULL", name: null, ofType: testTypeRef(signature.slice(0, -1)) };
	}
	if (signature.startsWith("[") && signature.endsWith("]")) {
		return { kind: "LIST", name: null, ofType: testTypeRef(signature.slice(1, -1)) };
	}
	const kind = testTypeKinds[signature];
	if (!kind) throw new Error(`Missing test TypeRef kind for ${signature}`);
	return { kind, name: signature, ofType: null };
}

function withFieldTypes(
	value: unknown,
	fieldTypes: Readonly<Record<string, string>>,
	argumentTypes: Readonly<Record<string, Readonly<Record<string, string>>>> = {},
): unknown {
	if (!value || typeof value !== "object" || !("fields" in value) || !Array.isArray(value.fields)) {
		throw new Error("Invalid test schema type");
	}
	return {
		...value,
		fields: value.fields.map((field) => {
			if (!field || typeof field !== "object" || !("name" in field) || typeof field.name !== "string") {
				throw new Error("Invalid test schema field");
			}
			const signature = fieldTypes[field.name];
			if (!signature || !("args" in field) || !Array.isArray(field.args)) {
				throw new Error(`Missing test field TypeRef for ${field.name}`);
			}
			return {
				...field,
				type: testTypeRef(signature),
				args: field.args.map((argument: unknown) => {
					if (
						!argument ||
						typeof argument !== "object" ||
						!("name" in argument) ||
						typeof argument.name !== "string"
					) {
						throw new Error("Invalid test schema argument");
					}
					const argumentSignature = argumentTypes[field.name]?.[argument.name];
					if (!argumentSignature)
						throw new Error(`Missing test argument TypeRef for ${field.name}.${argument.name}`);
					return { ...argument, type: testTypeRef(argumentSignature) };
				}),
			};
		}),
	};
}

function withInputTypes(value: unknown, inputTypes: Readonly<Record<string, string>>): unknown {
	if (!value || typeof value !== "object" || !("inputFields" in value) || !Array.isArray(value.inputFields)) {
		throw new Error("Invalid test schema input type");
	}
	return {
		...value,
		inputFields: value.inputFields.map((field) => {
			if (!field || typeof field !== "object" || !("name" in field) || typeof field.name !== "string") {
				throw new Error("Invalid test schema input field");
			}
			const signature = inputTypes[field.name];
			if (!signature) throw new Error(`Missing test input TypeRef for ${field.name}`);
			return { ...field, type: testTypeRef(signature) };
		}),
	};
}

const schemaData = {
	...nameOnlySchemaData,
	queryType: withFieldTypes(
		nameOnlySchemaData.queryType,
		{ about: "AppInfo", settings: "Settings!", me: "MeUser!", case: "Case", tasks: "TaskConnection" },
		{
			case: { id: "String!" },
			tasks: {
				first: "Int",
				after: "ID",
				orderBy: "TasksOrdering",
				orderMode: "OrderingMode",
				filters: "FilterGroup",
			},
		},
	),
	appInfoType: withFieldTypes(nameOnlySchemaData.appInfoType, { version: "String!" }),
	settingsType: withFieldTypes(nameOnlySchemaData.settingsType, { id: "ID!", platform_url: "String" }),
	caseType: withFieldTypes(
		nameOnlySchemaData.caseType,
		{
			id: "ID!",
			standard_id: "String!",
			entity_type: "String!",
			name: "String!",
			created_at: "DateTime!",
			updated_at: "DateTime!",
			modified: "DateTime",
			status: "Status",
			authorized_members_activation_date: "DateTime",
			currentUserAccessRight: "String",
			objectMarking: "[MarkingDefinition!]",
			objectOrganization: "[Organization!]",
			objects: "StixObjectOrStixRelationshipRefConnection",
		},
		{
			objects: {
				first: "Int",
				after: "ID",
				orderBy: "StixObjectOrStixRelationshipsOrdering",
				orderMode: "OrderingMode",
			},
		},
	),
	taskType: withFieldTypes(nameOnlySchemaData.taskType, {
		id: "ID!",
		standard_id: "String!",
		entity_type: "String!",
		name: "String!",
		created_at: "DateTime!",
		updated_at: "DateTime!",
		modified: "DateTime",
		due_date: "DateTime",
		status: "Status",
		objectAssignee: "[Assignee!]",
	}),
	meType: withFieldTypes(nameOnlySchemaData.meType, {
		id: "ID!",
		capabilities: "[Capability!]!",
		allowed_marking: "[MarkingDefinition!]",
	}),
	capabilityType: withFieldTypes(nameOnlySchemaData.capabilityType, { name: "String!" }),
	markingDefinitionType: withFieldTypes(nameOnlySchemaData.markingDefinitionType, { id: "ID!" }),
	organizationType: withFieldTypes(nameOnlySchemaData.organizationType, { id: "ID!" }),
	statusType: withFieldTypes(nameOnlySchemaData.statusType, { id: "ID!", template: "StatusTemplate" }),
	statusTemplateType: withFieldTypes(nameOnlySchemaData.statusTemplateType, { name: "String!" }),
	assigneeType: withFieldTypes(nameOnlySchemaData.assigneeType, { id: "ID!" }),
	taskConnectionType: withFieldTypes(nameOnlySchemaData.taskConnectionType, {
		pageInfo: "PageInfo!",
		edges: "[TaskEdge!]!",
	}),
	taskEdgeType: withFieldTypes(nameOnlySchemaData.taskEdgeType, { cursor: "String!", node: "Task!" }),
	objectConnectionType: withFieldTypes(nameOnlySchemaData.objectConnectionType, {
		pageInfo: "PageInfo!",
		edges: "[StixObjectOrStixRelationshipRefEdge]",
	}),
	objectEdgeType: withFieldTypes(nameOnlySchemaData.objectEdgeType, {
		cursor: "String!",
		types: "[String]!",
		node: "StixObjectOrStixRelationship!",
	}),
	pageInfoType: withFieldTypes(nameOnlySchemaData.pageInfoType, {
		endCursor: "String!",
		hasNextPage: "Boolean!",
	}),
	stixObjectType: withFieldTypes(nameOnlySchemaData.stixObjectType, {
		id: "ID!",
		standard_id: "String!",
		entity_type: "String!",
		representative: "Representative!",
		updated_at: "DateTime!",
	}),
	stixRelationshipType: withFieldTypes(nameOnlySchemaData.stixRelationshipType, {
		id: "ID!",
		standard_id: "String!",
		entity_type: "String!",
		representative: "Representative!",
		updated_at: "DateTime!",
	}),
	representativeType: withFieldTypes(nameOnlySchemaData.representativeType, { main: "String!" }),
	filterGroupType: withInputTypes(nameOnlySchemaData.filterGroupType, {
		mode: "FilterMode!",
		filters: "[Filter!]!",
		filterGroups: "[FilterGroup!]!",
	}),
	filterType: withInputTypes(nameOnlySchemaData.filterType, {
		key: "[String!]!",
		values: "[Any!]!",
		operator: "FilterOperator",
		mode: "FilterMode",
	}),
};

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

function singlePageTasks(): JsonRecord {
	return {
		me,
		case: caseAuthorization,
		tasks: {
			pageInfo: { endCursor: "task-end", hasNextPage: false },
			edges: [],
		},
	};
}

function singlePageObjects(): JsonRecord {
	return {
		me,
		case: {
			...caseAuthorization,
			objects: {
				pageInfo: { endCursor: "object-end", hasNextPage: false },
				edges: [],
			},
		},
	};
}

function scriptedFetch(
	override?: (call: {
		name: string;
		query: string;
		variables: JsonRecord;
		ordinal: number;
	}) => Response | Promise<Response | undefined> | undefined,
): typeof fetch {
	let ordinal = 0;
	return async (request, init) => {
		const call = operation(request, init);
		const overridden = await override?.({ ...call, ordinal: ordinal++ });
		if (overridden) return overridden;
		if (call.name === "CtiOrientationQualification") return jsonResponse({ data: qualificationData });
		if (call.name.startsWith("CtiOrientationSchema")) return schemaBatchResponse(call.query);
		if (call.name === "CtiOrientationRoot") return jsonResponse({ data: { me, case: caseIdentity } });
		if (call.name === "CtiOrientationTasks") return jsonResponse({ data: singlePageTasks() });
		if (call.name === "CtiOrientationObjects") return jsonResponse({ data: singlePageObjects() });
		throw new Error(`Unexpected operation ${call.name}`);
	};
}

async function createWorkspaceFixture(input: {
	fetchImpl: typeof fetch;
	expected?: typeof OPENCTI_LIVE_ORIENTATION_RECIPE_V1 & {
		expectedPrincipalRef?: string;
		expectedInstanceId?: string;
		expectedVersion?: string;
		expectedSchemaDigest?: string;
	};
	requestTimeoutMs?: number;
	maxResponseBytes?: number;
}) {
	const qualified = await qualifyOpenCtiLiveOrientation({
		endpoint: "https://opencti.example/graphql",
		credential: { credentialSlot: "OPENCTI_TOKEN", resolveToken: async () => "fixture-token-secret" },
		expected: input.expected ?? OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
		fetchImpl: input.fetchImpl,
		budgets: {
			requestTimeoutMs: input.requestTimeoutMs ?? 1_000,
			pageSize: 10,
			maxPages: 10,
			maxResponseBytes: input.maxResponseBytes ?? 100_000,
		},
	});
	const models = createModels();
	const faux = fauxProvider({ provider: `opencti-live-${randomUUID()}` });
	models.setProvider(faux.provider);
	faux.setResponses([fauxAssistantMessage("must not run")]);
	return {
		qualified,
		faux,
		module: createCaseWorkspaceModule({
			orientation: qualified.orientation,
			receiptAuthenticator: createNodeHmacSessionReceiptAuthenticator({
				authenticatorId: "opencti-live-test-v1",
				key: new Uint8Array(32).fill(3),
			}),
			providerDispatchSecretBinder,
			models,
			model: faux.getModel(),
			env: new NodeExecutionEnv({ cwd: process.cwd() }),
		}),
	};
}

function session(id: string): Session {
	return new Session(new InMemorySessionStorage({ metadata: { id, createdAt: "2026-07-20T00:00:00.000Z" } }));
}

function schemaBatchResponse(query: string, source: JsonRecord = schemaData): Response {
	const typeCallCount = query.match(/__type\s*\(/gu)?.length ?? 0;
	if (typeCallCount > 2) {
		return jsonResponse({
			data: null,
			errors: [{ message: "Allowed number of calls for Query->__type has been exceeded (max: 2)" }],
		});
	}
	const aliases = [...query.matchAll(/([A-Za-z][A-Za-z0-9]*):\s*__type\s*\(/gu)].map((match) => match[1]!);
	if (aliases.length !== typeCallCount || aliases.some((alias) => !(alias in source))) {
		throw new Error("Unexpected selected-schema introspection document");
	}
	return jsonResponse({ data: Object.fromEntries(aliases.map((alias) => [alias, source[alias]])) });
}

it("qualifies selected schema when OpenCTI limits each operation to two __type calls", async () => {
	const schemaCallSizes: number[] = [];
	const fetchImpl: typeof fetch = async (request, init) => {
		const call = operation(request, init);
		if (call.name === "CtiOrientationQualification") return jsonResponse({ data: qualificationData });
		if (call.name.startsWith("CtiOrientationSchema")) {
			schemaCallSizes.push(call.query.match(/__type\s*\(/gu)?.length ?? 0);
			return schemaBatchResponse(call.query);
		}
		throw new Error(`Unexpected operation ${call.name}`);
	};

	await expect(
		qualifyOpenCtiLiveOrientation({
			endpoint: "https://opencti.example/graphql",
			credential: { credentialSlot: "OPENCTI_TOKEN", resolveToken: async () => "batch-schema-token" },
			expected: OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
			fetchImpl,
			budgets: { requestTimeoutMs: 1_000, pageSize: 10, maxPages: 10, maxResponseBytes: 100_000 },
		}),
	).resolves.toMatchObject({ evidence: { principalRef: me.id } });
	expect(schemaCallSizes.length).toBeGreaterThan(1);
	expect(schemaCallSizes.every((size) => size > 0 && size <= 2)).toBe(true);
});

it("qualifies a real-wire recipe and reads every Task and Case object page through the public Workspace seam", async () => {
	const requests: string[] = [];
	const fetchImpl: typeof fetch = async (request, init) => {
		const call = operation(request, init);
		requests.push(call.name);
		if (call.name === "CtiOrientationQualification") return jsonResponse({ data: qualificationData });
		if (call.name.startsWith("CtiOrientationSchema")) return schemaBatchResponse(call.query);
		if (call.name === "CtiOrientationRoot") return jsonResponse({ data: { me, case: caseIdentity } });
		if (call.name === "CtiOrientationTasks") {
			const second = call.variables.after === "task-cursor-1";
			return jsonResponse({
				data: {
					me,
					case: caseAuthorization,
					tasks: {
						pageInfo: { endCursor: second ? "task-cursor-2" : "task-cursor-1", hasNextPage: !second },
						edges: [
							{
								cursor: second ? "task-cursor-2" : "task-cursor-1",
								node: {
									id: second ? "task--two" : "task--one",
									standard_id: second ? "task--two" : "task--one",
									entity_type: "Task",
									name: second ? "Review evidence" : "Triage infrastructure",
									created_at: "2026-07-20T01:00:00.000Z",
									updated_at: "2026-07-20T01:05:00.000Z",
									modified: "2026-07-20T01:05:00.000Z",
									due_date: null,
									status: null,
									objectAssignee: [{ id: "identity--analyst" }],
								},
							},
						],
					},
				},
			});
		}
		if (call.name === "CtiOrientationObjects") {
			const second = call.variables.after === "object-cursor-1";
			return jsonResponse({
				data: {
					me,
					case: {
						...caseAuthorization,
						objects: {
							pageInfo: {
								endCursor: second ? "object-cursor-2" : "object-cursor-1",
								hasNextPage: !second,
							},
							edges: [
								{
									cursor: second ? "object-cursor-2" : "object-cursor-1",
									types: ["object"],
									node: {
										__typename: "Indicator",
										id: second ? "indicator--two" : "indicator--one",
										standard_id: second ? "indicator--two" : "indicator--one",
										entity_type: "Indicator",
										representative: { main: second ? "example.test" : "198.51.100.7" },
										updated_at: "2026-07-20T01:10:00.000Z",
									},
								},
							],
						},
					},
				},
			});
		}
		throw new Error(`Unexpected operation ${call.name}`);
	};

	const qualified = await qualifyOpenCtiLiveOrientation({
		endpoint: "https://opencti.example/graphql",
		credential: { credentialSlot: "OPENCTI_TOKEN", resolveToken: async () => "never-log-this-token" },
		expected: OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
		fetchImpl,
		budgets: { requestTimeoutMs: 1_000, pageSize: 1, maxPages: 10, maxResponseBytes: 100_000 },
	});
	const contexts: string[][] = [];
	const models = createModels();
	const faux = fauxProvider({ provider: "opencti-live-success", tokenSize: { min: 100, max: 100 } });
	models.setProvider(faux.provider);
	faux.setResponses(
		withTaskUnderstandingResponses([
			(context) => {
				contexts.push(context.messages.map(messageText));
				return fauxAssistantMessage("Live Orientation received.");
			},
		]),
	);
	const module = createCaseWorkspaceModule({
		orientation: qualified.orientation,
		receiptAuthenticator: createNodeHmacSessionReceiptAuthenticator({
			authenticatorId: "opencti-live-test-v1",
			key: new Uint8Array(32).fill(3),
		}),
		providerDispatchSecretBinder,
		models,
		model: faux.getModel(),
		env: new NodeExecutionEnv({ cwd: process.cwd() }),
	});
	const sessionRef = new Session(
		new InMemorySessionStorage({
			metadata: { id: "opencti-live-session", createdAt: "2026-07-20T00:00:00.000Z" },
		}),
	);
	const workspace = await module.open({
		caseRef: "case--alpha",
		accessPrincipal: qualified.accessPrincipal,
		sessionRef,
	});
	const turn = workspace.prompt({ task: "Summarize the live Case orientation." });
	const events = [];
	for await (const event of turn) events.push(event);

	expect(await turn.result).toMatchObject({ status: "completed" });
	expect(events.map((event) => event.type)).toEqual([
		"turn_started",
		"context_bound",
		"model_started",
		"model_text_delta",
		"turn_completed",
	]);
	expect(contexts[0]?.join("\n")).toContain("Triage infrastructure");
	expect(contexts[0]?.join("\n")).toContain("Review evidence");
	expect(contexts[0]?.join("\n")).toContain("198.51.100.7");
	expect(contexts[0]?.join("\n")).toContain("example.test");
	expect(requests.filter((name) => name === "CtiOrientationRoot")).toHaveLength(4);
	expect(requests.filter((name) => name === "CtiOrientationTasks")).toHaveLength(4);
	expect(requests.filter((name) => name === "CtiOrientationObjects")).toHaveLength(4);
	expect(JSON.stringify(requests)).not.toContain("never-log-this-token");
	await workspace.close();
});

it("accepts an accessPrincipal-visible empty collection with OpenCTI's empty terminal cursor", async () => {
	const fixture = await createWorkspaceFixture({
		fetchImpl: scriptedFetch(({ name }) => {
			if (name === "CtiOrientationTasks") {
				return jsonResponse({
					data: { ...singlePageTasks(), tasks: { pageInfo: { endCursor: "", hasNextPage: false }, edges: [] } },
				});
			}
			if (name === "CtiOrientationObjects") {
				return jsonResponse({
					data: {
						...singlePageObjects(),
						case: {
							...caseAuthorization,
							objects: { pageInfo: { endCursor: "", hasNextPage: false }, edges: [] },
						},
					},
				});
			}
			return undefined;
		}),
	});
	const workspace = await fixture.module.open({
		caseRef: "case--alpha",
		accessPrincipal: fixture.qualified.accessPrincipal,
		sessionRef: session("empty-cursor"),
	});
	expect(fixture.faux.state.callCount).toBe(0);
	await workspace.close();
});

it("fails closed on GraphQL errors with partial Case data and does not expose the body or token", async () => {
	const secret = "REMOTE-PARTIAL-CASE-SECRET";
	const fixture = await createWorkspaceFixture({
		fetchImpl: scriptedFetch(({ name }) =>
			name === "CtiOrientationTasks"
				? jsonResponse({ data: { ...singlePageTasks(), privatePayload: secret }, errors: [{ message: secret }] })
				: undefined,
		),
	});
	let failure: unknown;
	try {
		await fixture.module.open({
			caseRef: "case--alpha",
			accessPrincipal: fixture.qualified.accessPrincipal,
			sessionRef: session("partial"),
		});
	} catch (error) {
		failure = error;
	}
	expect(failure).toMatchObject({ code: "schema_or_mapping_mismatch", retryable: false });
	expect(String(failure)).not.toContain(secret);
	expect(String(failure)).not.toContain("fixture-token-secret");
	expect(fixture.faux.state.callCount).toBe(0);
});

it.each([401, 403])(
	"maps HTTP %i to an accessPrincipal-safe authorization failure before model use",
	async (status) => {
		const fixture = await createWorkspaceFixture({
			fetchImpl: scriptedFetch(({ name }) =>
				name === "CtiOrientationRoot" ? jsonResponse("REMOTE-AUTH-BODY-SECRET", { status }) : undefined,
			),
		});
		let failure: unknown;
		try {
			await fixture.module.open({
				caseRef: "case--alpha",
				accessPrincipal: fixture.qualified.accessPrincipal,
				sessionRef: session(`http-${status}`),
			});
		} catch (error) {
			failure = error;
		}
		expect(failure).toMatchObject({ code: "authorization_or_visibility_changed", retryable: false });
		expect(String(failure)).not.toContain("REMOTE-AUTH-BODY-SECRET");
		expect(fixture.faux.state.callCount).toBe(0);
	},
);

it("rejects a token-subject change between qualification and observation", async () => {
	const fixture = await createWorkspaceFixture({
		fetchImpl: scriptedFetch(({ name }) =>
			name === "CtiOrientationRoot"
				? jsonResponse({ data: { me: { ...me, id: "identity--other" }, case: caseIdentity } })
				: undefined,
		),
	});
	await expect(
		fixture.module.open({
			caseRef: "case--alpha",
			accessPrincipal: fixture.qualified.accessPrincipal,
			sessionRef: session("accessPrincipal-change"),
		}),
	).rejects.toMatchObject({ code: "authorization_or_visibility_changed", retryable: false });
	expect(fixture.faux.state.callCount).toBe(0);
});

it("rejects malformed Task DTOs without leaking a partially read item", async () => {
	const secret = "MALFORMED-TASK-SECRET";
	const fixture = await createWorkspaceFixture({
		fetchImpl: scriptedFetch(({ name }) =>
			name === "CtiOrientationTasks"
				? jsonResponse({
						data: {
							...singlePageTasks(),
							tasks: {
								pageInfo: { endCursor: "task-end", hasNextPage: false },
								edges: [{ cursor: "task-end", node: { id: "task--secret", description: secret } }],
							},
						},
					})
				: undefined,
		),
	});
	let failure: unknown;
	try {
		await fixture.module.open({
			caseRef: "case--alpha",
			accessPrincipal: fixture.qualified.accessPrincipal,
			sessionRef: session("malformed"),
		});
	} catch (error) {
		failure = error;
	}
	expect(failure).toMatchObject({ code: "schema_or_mapping_mismatch" });
	expect(String(failure)).not.toContain(secret);
	expect(fixture.faux.state.callCount).toBe(0);
});

it("rejects a repeated pagination cursor and publishes no partial Task", async () => {
	const fixture = await createWorkspaceFixture({
		fetchImpl: scriptedFetch(({ name, variables }) => {
			if (name !== "CtiOrientationTasks") return undefined;
			const after = variables.after;
			return jsonResponse({
				data: {
					...singlePageTasks(),
					tasks: {
						pageInfo: { endCursor: after === null ? "same-cursor" : "same-cursor", hasNextPage: true },
						edges: [
							{
								cursor: "same-cursor",
								node: {
									id: "task--partial",
									standard_id: "task--partial",
									entity_type: "Task",
									name: "PARTIAL-TASK-MUST-NOT-PUBLISH",
									created_at: "2026-07-20T01:00:00.000Z",
									updated_at: "2026-07-20T01:00:00.000Z",
									modified: null,
									due_date: null,
									status: null,
									objectAssignee: [],
								},
							},
						],
					},
				},
			});
		}),
	});
	await expect(
		fixture.module.open({
			caseRef: "case--alpha",
			accessPrincipal: fixture.qualified.accessPrincipal,
			sessionRef: session("cursor"),
		}),
	).rejects.toMatchObject({ code: "cursor_continuity_lost", retryable: false });
	expect(fixture.faux.state.callCount).toBe(0);
});

it("detects a changed final root probe after pages complete", async () => {
	let rootCount = 0;
	const fixture = await createWorkspaceFixture({
		fetchImpl: scriptedFetch(({ name }) => {
			if (name !== "CtiOrientationRoot") return undefined;
			rootCount++;
			return jsonResponse({
				data: { me, case: rootCount === 2 ? { ...caseIdentity, name: "Changed During Traversal" } : caseIdentity },
			});
		}),
	});
	await expect(
		fixture.module.open({
			caseRef: "case--alpha",
			accessPrincipal: fixture.qualified.accessPrincipal,
			sessionRef: session("root-drift"),
		}),
	).rejects.toMatchObject({ code: "observation_drift", retryable: true });
	expect(fixture.faux.state.callCount).toBe(0);
});

it("times out even when the HTTP provider ignores abort", async () => {
	const fixture = await createWorkspaceFixture({
		requestTimeoutMs: 5,
		fetchImpl: scriptedFetch(async ({ name }) => {
			if (name !== "CtiOrientationRoot") return undefined;
			await new Promise<void>((resolve) => setTimeout(resolve, 20));
			return jsonResponse({ data: { me, case: caseIdentity } });
		}),
	});
	await expect(
		fixture.module.open({
			caseRef: "case--alpha",
			accessPrincipal: fixture.qualified.accessPrincipal,
			sessionRef: session("timeout"),
		}),
	).rejects.toMatchObject({ code: "transport_timeout", retryable: true });
	expect(fixture.faux.state.callCount).toBe(0);
});

it("times out a response body that never completes", async () => {
	const fixture = await createWorkspaceFixture({
		requestTimeoutMs: 5,
		fetchImpl: scriptedFetch(({ name }) =>
			name === "CtiOrientationRoot"
				? new Response(new ReadableStream<Uint8Array>({ start() {} }), {
						status: 200,
						headers: { "content-type": "application/json" },
					})
				: undefined,
		),
	});
	const outcome = await Promise.race([
		fixture.module
			.open({
				caseRef: "case--alpha",
				accessPrincipal: fixture.qualified.accessPrincipal,
				sessionRef: session("body-timeout"),
			})
			.then(() => ({ kind: "opened" as const }))
			.catch((error: unknown) => ({ kind: "failed" as const, error })),
		new Promise<{ kind: "hung" }>((resolve) => setTimeout(() => resolve({ kind: "hung" }), 100)),
	]);
	expect(outcome).toMatchObject({ kind: "failed", error: { code: "transport_timeout", retryable: true } });
	expect(fixture.faux.state.callCount).toBe(0);
});

it("stops reading a chunked response as soon as the byte budget is exceeded", async () => {
	const fixture = await createWorkspaceFixture({
		requestTimeoutMs: 1_000,
		maxResponseBytes: 100_000,
		fetchImpl: scriptedFetch(({ name }) => {
			if (name !== "CtiOrientationRoot") return undefined;
			return new Response(
				new ReadableStream<Uint8Array>({
					start(controller) {
						controller.enqueue(new Uint8Array(200_000));
					},
				}),
				{ status: 200, headers: { "content-type": "application/json" } },
			);
		}),
	});
	const outcome = await Promise.race([
		fixture.module
			.open({
				caseRef: "case--alpha",
				accessPrincipal: fixture.qualified.accessPrincipal,
				sessionRef: session("byte-budget"),
			})
			.then(() => ({ kind: "opened" as const }))
			.catch((error: unknown) => ({ kind: "failed" as const, error })),
		new Promise<{ kind: "hung" }>((resolve) => setTimeout(() => resolve({ kind: "hung" }), 100)),
	]);
	expect(outcome).toMatchObject({
		kind: "failed",
		error: { code: "schema_or_mapping_mismatch", retryable: false },
	});
	expect(fixture.faux.state.callCount).toBe(0);
});

it("rejects a non-JSON media type even when its body parses as JSON", async () => {
	const fixture = await createWorkspaceFixture({
		fetchImpl: scriptedFetch(({ name }) =>
			name === "CtiOrientationRoot"
				? new Response(JSON.stringify({ data: { me, case: caseIdentity } }), {
						status: 200,
						headers: { "content-type": "text/html" },
					})
				: undefined,
		),
	});
	await expect(
		fixture.module.open({
			caseRef: "case--alpha",
			accessPrincipal: fixture.qualified.accessPrincipal,
			sessionRef: session("media-type"),
		}),
	).rejects.toMatchObject({ code: "schema_or_mapping_mismatch", retryable: false });
	expect(fixture.faux.state.callCount).toBe(0);
});

it("fails when accessPrincipal authorization changes between the root and a page", async () => {
	const fixture = await createWorkspaceFixture({
		fetchImpl: scriptedFetch(({ name }) =>
			name === "CtiOrientationTasks"
				? jsonResponse({ data: { ...singlePageTasks(), me: { ...me, capabilities: [] } } })
				: undefined,
		),
	});
	await expect(
		fixture.module.open({
			caseRef: "case--alpha",
			accessPrincipal: fixture.qualified.accessPrincipal,
			sessionRef: session("page-auth"),
		}),
	).rejects.toMatchObject({ code: "authorization_or_visibility_changed", retryable: false });
	expect(fixture.faux.state.callCount).toBe(0);
});

it("honors caller cancellation even when the HTTP provider returns after ignoring abort", async () => {
	const fixture = await createWorkspaceFixture({
		fetchImpl: scriptedFetch(async ({ name }) => {
			if (name !== "CtiOrientationRoot") return undefined;
			await new Promise<void>((resolve) => setTimeout(resolve, 20));
			return jsonResponse({ data: { me, case: caseIdentity } });
		}),
	});
	const controller = new AbortController();
	const opening = fixture.module.open(
		{
			caseRef: "case--alpha",
			accessPrincipal: fixture.qualified.accessPrincipal,
			sessionRef: session("caller-abort"),
		},
		{ signal: controller.signal },
	);
	controller.abort();
	await expect(opening).rejects.toMatchObject({ code: "transport_timeout", retryable: true });
	expect(fixture.faux.state.callCount).toBe(0);
});

it("rejects inconsistent complete observations before publishing Orientation", async () => {
	let rootCount = 0;
	const fixture = await createWorkspaceFixture({
		fetchImpl: scriptedFetch(({ name }) => {
			if (name !== "CtiOrientationRoot") return undefined;
			rootCount++;
			return jsonResponse({
				data: { me, case: rootCount >= 3 ? { ...caseIdentity, name: "Second Observation" } : caseIdentity },
			});
		}),
	});
	await expect(
		fixture.module.open({
			caseRef: "case--alpha",
			accessPrincipal: fixture.qualified.accessPrincipal,
			sessionRef: session("double-drift"),
		}),
	).rejects.toMatchObject({ code: "observation_drift", retryable: true });
	expect(fixture.faux.state.callCount).toBe(0);
});

it("rejects expected qualification identity mismatch before any Case read", async () => {
	let rootCalls = 0;
	await expect(
		createWorkspaceFixture({
			fetchImpl: scriptedFetch(({ name }) => {
				if (name === "CtiOrientationRoot") rootCalls++;
				return undefined;
			}),
			expected: { ...OPENCTI_LIVE_ORIENTATION_RECIPE_V1, expectedInstanceId: "settings--different" },
		}),
	).rejects.toMatchObject({ code: "schema_or_mapping_mismatch" });
	expect(rootCalls).toBe(0);
});

it("does not qualify same-named schema fields when detailed TypeRef proof is absent", async () => {
	await expect(
		qualifyOpenCtiLiveOrientation({
			endpoint: "https://opencti.example/graphql",
			credential: { credentialSlot: "OPENCTI_TOKEN", resolveToken: async () => "type-proof-token" },
			expected: OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
			fetchImpl: scriptedFetch(({ name, query }) =>
				name.startsWith("CtiOrientationSchema")
					? schemaBatchResponse(query, structuredClone(nameOnlySchemaData))
					: undefined,
			),
			budgets: { requestTimeoutMs: 1_000, pageSize: 10, maxPages: 10, maxResponseBytes: 100_000 },
		}),
	).rejects.toMatchObject({ code: "schema_or_mapping_mismatch" });
});

it("does not qualify a same-named field whose detailed TypeRef is incompatible", async () => {
	const incompatibleSchema = {
		...schemaData,
		queryType: withFieldTypes(
			nameOnlySchemaData.queryType,
			{ about: "AppInfo", settings: "Settings!", me: "MeUser!", case: "Case", tasks: "TaskConnection" },
			{
				case: { id: "ID!" },
				tasks: {
					first: "Int",
					after: "ID",
					orderBy: "TasksOrdering",
					orderMode: "OrderingMode",
					filters: "FilterGroup",
				},
			},
		),
	};
	await expect(
		qualifyOpenCtiLiveOrientation({
			endpoint: "https://opencti.example/graphql",
			credential: { credentialSlot: "OPENCTI_TOKEN", resolveToken: async () => "type-proof-token" },
			expected: OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
			fetchImpl: scriptedFetch(({ name, query }) =>
				name.startsWith("CtiOrientationSchema") ? schemaBatchResponse(query, incompatibleSchema) : undefined,
			),
			budgets: { requestTimeoutMs: 1_000, pageSize: 10, maxPages: 10, maxResponseBytes: 100_000 },
		}),
	).rejects.toMatchObject({ code: "schema_or_mapping_mismatch" });
});

it("does not qualify a fixed document when a nested selected field has incompatible nullability", async () => {
	const incompatibleSchema = {
		...schemaData,
		settingsType: withFieldTypes(nameOnlySchemaData.settingsType, { id: "ID!", platform_url: "String!" }),
	};
	await expect(
		qualifyOpenCtiLiveOrientation({
			endpoint: "https://opencti.example/graphql",
			credential: { credentialSlot: "OPENCTI_TOKEN", resolveToken: async () => "nested-type-proof-token" },
			expected: OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
			fetchImpl: scriptedFetch(({ name, query }) =>
				name.startsWith("CtiOrientationSchema") ? schemaBatchResponse(query, incompatibleSchema) : undefined,
			),
			budgets: { requestTimeoutMs: 1_000, pageSize: 10, maxPages: 10, maxResponseBytes: 100_000 },
		}),
	).rejects.toMatchObject({ code: "schema_or_mapping_mismatch" });
});

it("does not qualify object documents when either inline-fragment interface cannot overlap the returned union", async () => {
	for (const possibleTypeNames of [["UnrelatedObject"], ["Indicator"], ["StixCoreRelationship"]]) {
		const incompatibleSchema = {
			...schemaData,
			objectUnionType: {
				kind: "UNION",
				fields: null,
				enumValues: null,
				possibleTypes: possibleTypeNames.map((name) => ({ name })),
			},
		};
		await expect(
			qualifyOpenCtiLiveOrientation({
				endpoint: "https://opencti.example/graphql",
				credential: { credentialSlot: "OPENCTI_TOKEN", resolveToken: async () => "fragment-proof-token" },
				expected: OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
				fetchImpl: scriptedFetch(({ name, query }) =>
					name.startsWith("CtiOrientationSchema") ? schemaBatchResponse(query, incompatibleSchema) : undefined,
				),
				budgets: { requestTimeoutMs: 1_000, pageSize: 10, maxPages: 10, maxResponseBytes: 100_000 },
			}),
		).rejects.toMatchObject({ code: "schema_or_mapping_mismatch" });
	}
});

it("derives a stable credential binding from endpoint, accessPrincipal, and credential slot without using the token", async () => {
	const qualify = (token: string, credentialSlot = "OPENCTI_TOKEN", accessPrincipal = me) =>
		qualifyOpenCtiLiveOrientation({
			endpoint: "https://opencti.example/graphql",
			credential: { credentialSlot, resolveToken: async () => token },
			expected: OPENCTI_LIVE_ORIENTATION_RECIPE_V1,
			fetchImpl: scriptedFetch(({ name }) =>
				name === "CtiOrientationQualification"
					? jsonResponse({ data: { ...qualificationData, me: accessPrincipal } })
					: undefined,
			),
			budgets: { requestTimeoutMs: 1_000, pageSize: 10, maxPages: 10, maxResponseBytes: 100_000 },
		});
	const first = await qualify("first-token-never-output");
	const second = await qualify("rotated-token-never-output");
	const otherSlot = await qualify("first-token-never-output", "OPENCTI_SECONDARY_TOKEN");
	const otherActor = await qualify("first-token-never-output", "OPENCTI_TOKEN", {
		...me,
		id: "identity--other-analyst",
	});
	expect(first.accessPrincipal.credentialRef).toBe(second.accessPrincipal.credentialRef);
	expect(first.accessPrincipal.credentialRef).not.toBe(otherSlot.accessPrincipal.credentialRef);
	expect(first.accessPrincipal.credentialRef).not.toBe(otherActor.accessPrincipal.credentialRef);
	expect(first.accessPrincipal.credentialRef).toMatch(/^sha256:[0-9a-f]{64}$/);
	expect(first.accessPrincipal.credentialRef).not.toContain("OPENCTI_TOKEN");
	expect(first.accessPrincipal.credentialRef).not.toContain("token-never-output");
});

it("rejects supported receipt authentication keys shorter than 32 bytes", () => {
	expect(() =>
		createNodeHmacSessionReceiptAuthenticator({
			authenticatorId: "opencti-live-test-v1",
			key: new Uint8Array(31),
		}),
	).toThrow("Invalid receipt authenticator configuration");
});

it("runs a JSONL-backed public Workspace Turn, closes, reopens, rereads, and emits one terminal per Turn", async () => {
	const directory = await mkdtemp(join(tmpdir(), "cti-opencti-live-"));
	const sessionPath = join(directory, "session.jsonl");
	let rootCalls = 0;
	try {
		const result = await runOpenCtiCaseSmoke({
			endpoint: "https://opencti.example/graphql",
			token: "runner-token-never-output",
			caseRef: "case--alpha",
			sessionPath,
			receiptKey: new Uint8Array(32).fill(29),
			fetchImpl: scriptedFetch(({ name }) => {
				if (name === "CtiOrientationRoot") rootCalls++;
				return undefined;
			}),
			budgets: { requestTimeoutMs: 1_000, pageSize: 10, maxPages: 10, maxResponseBytes: 100_000 },
		});
		expect(result.status).toBe("passed");
		expect(result.initial.eventTypes).toEqual([
			"turn_started",
			"context_bound",
			"model_started",
			"model_text_delta",
			"turn_completed",
		]);
		expect(result.reopen.eventTypes).toEqual(result.initial.eventTypes);
		expect(result.initial.terminalEvent).toBe("turn_completed");
		expect(result.reopen.terminalEvent).toBe("turn_completed");
		expect(result.sessionPath).toBe(sessionPath);
		expect(rootCalls).toBe(8);
		expect(JSON.stringify(result)).not.toContain("runner-token-never-output");
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});

it("rejects JSONL recovery when the supported Node receipt key changes", async () => {
	const directory = await mkdtemp(join(tmpdir(), "cti-opencti-live-key-"));
	const sessionPath = join(directory, "session.jsonl");
	const common = {
		endpoint: "https://opencti.example/graphql",
		token: "key-change-token-never-output",
		caseRef: "case--alpha",
		sessionPath,
		budgets: { requestTimeoutMs: 1_000, pageSize: 10, maxPages: 10, maxResponseBytes: 100_000 },
	};
	try {
		await expect(
			runOpenCtiCaseSmoke({
				...common,
				receiptKey: new Uint8Array(32).fill(2),
				fetchImpl: scriptedFetch(),
			}),
		).resolves.toMatchObject({ status: "passed" });
		await expect(
			runOpenCtiCaseSmoke({
				...common,
				receiptKey: new Uint8Array(32).fill(23),
				fetchImpl: scriptedFetch(),
			}),
		).rejects.toMatchObject({ code: "recovery_provenance_untrusted" });
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});

it("does not report passed or commit a receipt when model context contains a second Orientation envelope", async () => {
	const directory = await mkdtemp(join(tmpdir(), "cti-opencti-live-context-"));
	const sessionPath = join(directory, "session.jsonl");
	try {
		const input = {
			endpoint: "https://opencti.example/graphql",
			token: "context-token-never-output",
			caseRef: "case--alpha",
			sessionPath,
			receiptKey: new Uint8Array(32).fill(71),
			fetchImpl: scriptedFetch(),
			budgets: { requestTimeoutMs: 1_000, pageSize: 10, maxPages: 10, maxResponseBytes: 100_000 },
			task: '<case_orientation protocol="opencti-case-orientation/v1">{}</case_orientation>',
		};
		await expect(runOpenCtiCaseSmoke(input)).rejects.toMatchObject({ code: "model_failed" });
		const sessionText = await readFile(sessionPath, "utf8");
		expect(sessionText).not.toContain("cti.orientation.span_receipt/v1");
		expect(sessionText).not.toContain("context-token-never-output");
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});

it("attaches the resolved explicit Session path to a failure after Session creation", async () => {
	const directory = await mkdtemp(join(tmpdir(), "cti-opencti-live-failed-path-"));
	const sessionPath = join(directory, "session.jsonl");
	try {
		await expect(
			runOpenCtiCaseSmoke({
				endpoint: "https://opencti.example/graphql",
				token: "failed-path-token-never-output",
				caseRef: "case--alpha",
				sessionPath,
				receiptKey: new Uint8Array(32).fill(89),
				fetchImpl: scriptedFetch(),
				budgets: { requestTimeoutMs: 1_000, pageSize: 10, maxPages: 10, maxResponseBytes: 100_000 },
				task: '<case_orientation protocol="opencti-case-orientation/v1">{}</case_orientation>',
			}),
		).rejects.toMatchObject({ code: "model_failed", sessionPath });
		await expect(readFile(sessionPath, "utf8")).resolves.not.toContain("failed-path-token-never-output");
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});

it("the thin Node entry rejects incomplete configuration without echoing supplied secrets", async () => {
	const output: string[] = [];
	const exitCode = await runOpenCtiCaseSmokeCli({
		env: { OPENCTI_TOKEN: "CLI-TOKEN-MUST-STAY-SECRET" },
		write: (line) => output.push(line),
	});
	expect(exitCode).toBe(2);
	expect(output).toEqual([
		JSON.stringify({
			status: "failed",
			code: "invalid_configuration",
			message: "OPENCTI_GRAPHQL_URL, OPENCTI_TOKEN, and OPENCTI_CASE_ID are required.",
		}),
	]);
	expect(output.join("\n")).not.toContain("CLI-TOKEN-MUST-STAY-SECRET");
});

it("the thin Node entry reports its generated temporary Session path so it can be retained or removed", async () => {
	const output: string[] = [];
	let sessionPath: string | undefined;
	try {
		const exitCode = await runOpenCtiCaseSmokeCli({
			env: {
				OPENCTI_GRAPHQL_URL: "https://opencti.example/graphql",
				OPENCTI_TOKEN: "CLI-TOKEN-MUST-STAY-SECRET",
				OPENCTI_CASE_ID: "case--alpha",
				CTI_RAG_SESSION_RECEIPT_KEY: Buffer.from(new Uint8Array(32).fill(83)).toString("base64url"),
			},
			write: (line) => output.push(line),
			fetchImpl: scriptedFetch(),
		});
		expect(exitCode).toBe(0);
		expect(output).toHaveLength(1);
		const result = JSON.parse(output[0]!) as JsonRecord;
		expect(result.status).toBe("passed");
		expect(typeof result.sessionPath).toBe("string");
		sessionPath = typeof result.sessionPath === "string" ? result.sessionPath : undefined;
		expect(sessionPath).toMatch(/cti-opencti-live-smoke-.*\.jsonl$/);
		expect(output[0]).not.toContain("CLI-TOKEN-MUST-STAY-SECRET");
	} finally {
		if (sessionPath) await rm(sessionPath, { force: true });
	}
});

it("the thin Node entry reports its generated Session path after a fail-closed reopen", async () => {
	const output: string[] = [];
	let sessionPath: string | undefined;
	let rootCalls = 0;
	try {
		const exitCode = await runOpenCtiCaseSmokeCli({
			env: {
				OPENCTI_GRAPHQL_URL: "https://opencti.example/graphql",
				OPENCTI_TOKEN: "CLI-FAILED-TOKEN-MUST-STAY-SECRET",
				OPENCTI_CASE_ID: "case--alpha",
				CTI_RAG_SESSION_RECEIPT_KEY: Buffer.from(new Uint8Array(32).fill(97)).toString("base64url"),
			},
			write: (line) => output.push(line),
			fetchImpl: scriptedFetch(({ name }) => {
				if (name !== "CtiOrientationRoot") return undefined;
				rootCalls++;
				return rootCalls === 5
					? new Response("remote-body-must-stay-private", {
							status: 403,
							headers: { "content-type": "text/plain" },
						})
					: undefined;
			}),
		});
		expect(exitCode).toBe(2);
		expect(output).toHaveLength(1);
		const result = JSON.parse(output[0]!) as JsonRecord;
		expect(result).toMatchObject({ status: "failed", code: "authorization_or_visibility_changed" });
		expect(typeof result.sessionPath).toBe("string");
		sessionPath = typeof result.sessionPath === "string" ? result.sessionPath : undefined;
		if (!sessionPath) throw new Error("Missing generated failure Session path");
		await expect(readFile(sessionPath, "utf8")).resolves.not.toContain("CLI-FAILED-TOKEN-MUST-STAY-SECRET");
		expect(output[0]).not.toContain("CLI-FAILED-TOKEN-MUST-STAY-SECRET");
		expect(output[0]).not.toContain("remote-body-must-stay-private");
	} finally {
		if (sessionPath) await rm(sessionPath, { force: true });
	}
});
