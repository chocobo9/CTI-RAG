import { Buffer } from "node:buffer";
import { createHash } from "node:crypto";
import { OpenCtiTransportOrientationAdapter } from "../opencti-transport-orientation-adapter.ts";
import type {
	AccessPrincipalBinding,
	OpenCtiCaseIdentityV1,
	OpenCtiOrientationTransportPort,
	OpenCtiOrientationTransportRequest,
	OpenCtiVisibleObjectMembershipV1,
	OpenCtiVisibleWorkV1,
	OrientationReadPort,
	OrientationSourceIdentityV1,
} from "../types.ts";

type JsonObject = Readonly<Record<string, unknown>>;

const QUALIFICATION_OPERATION = "CtiOrientationQualification";
const ROOT_OPERATION = "CtiOrientationRoot";
const TASKS_OPERATION = "CtiOrientationTasks";
const OBJECTS_OPERATION = "CtiOrientationObjects";

const qualificationDocument = `query ${QUALIFICATION_OPERATION} {
  about { version }
  settings { id platform_url }
  me { id capabilities { name } allowed_marking { id } }
}`;

const typeRefFields = `kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name ofType { kind name } } } } }`;
const selectedTypeFields = `kind fields(includeDeprecated: true) { name args { name type { ${typeRefFields} } } type { ${typeRefFields} } } enumValues(includeDeprecated: true) { name } possibleTypes { name }`;
const selectedInputTypeFields = `kind inputFields { name type { ${typeRefFields} } }`;
const schemaTypeProbes = [
	["queryType", "Query", selectedTypeFields],
	["appInfoType", "AppInfo", selectedTypeFields],
	["settingsType", "Settings", selectedTypeFields],
	["caseType", "Case", selectedTypeFields],
	["taskType", "Task", selectedTypeFields],
	["meType", "MeUser", selectedTypeFields],
	["capabilityType", "Capability", selectedTypeFields],
	["markingDefinitionType", "MarkingDefinition", selectedTypeFields],
	["organizationType", "Organization", selectedTypeFields],
	["statusType", "Status", selectedTypeFields],
	["statusTemplateType", "StatusTemplate", selectedTypeFields],
	["assigneeType", "Assignee", selectedTypeFields],
	["taskConnectionType", "TaskConnection", selectedTypeFields],
	["taskEdgeType", "TaskEdge", selectedTypeFields],
	["objectConnectionType", "StixObjectOrStixRelationshipRefConnection", selectedTypeFields],
	["objectEdgeType", "StixObjectOrStixRelationshipRefEdge", selectedTypeFields],
	["pageInfoType", "PageInfo", selectedTypeFields],
	["stixObjectType", "StixObject", selectedTypeFields],
	["stixRelationshipType", "StixRelationship", selectedTypeFields],
	["representativeType", "Representative", selectedTypeFields],
	["objectUnionType", "StixObjectOrStixRelationship", selectedTypeFields],
	["tasksOrderingType", "TasksOrdering", selectedTypeFields],
	["objectOrderingType", "StixObjectOrStixRelationshipsOrdering", selectedTypeFields],
	["orderingModeType", "OrderingMode", selectedTypeFields],
	["filterModeType", "FilterMode", selectedTypeFields],
	["filterOperatorType", "FilterOperator", selectedTypeFields],
	["filterGroupType", "FilterGroup", selectedInputTypeFields],
	["filterType", "Filter", selectedInputTypeFields],
] as const;
const schemaOperations: Array<{ name: string; document: string; aliases: readonly string[] }> = [];
for (let offset = 0; offset < schemaTypeProbes.length; offset += 2) {
	const probes = schemaTypeProbes.slice(offset, offset + 2);
	const name = `CtiOrientationSchema${String(offset / 2 + 1).padStart(2, "0")}`;
	schemaOperations.push({
		name,
		document: `query ${name} {\n${probes
			.map(([alias, typeName, fields]) => `  ${alias}: __type(name: ${JSON.stringify(typeName)}) { ${fields} }`)
			.join("\n")}\n}`,
		aliases: probes.map(([alias]) => alias),
	});
}

const principalFields = `me { id capabilities { name } allowed_marking { id } }`;
const caseAuthorizationFields = `
  id
  authorized_members_activation_date
  currentUserAccessRight
  objectMarking { id }
  objectOrganization { id }
`;
const rootDocument = `query ${ROOT_OPERATION}($caseId: String!) {
  ${principalFields}
  case(id: $caseId) {
    ${caseAuthorizationFields}
    standard_id
    entity_type
    name
    created_at
    updated_at
    modified
    status { id template { name } }
  }
}`;
const tasksDocument = `query ${TASKS_OPERATION}($caseId: String!, $first: Int!, $after: ID, $filters: FilterGroup!) {
  ${principalFields}
  case(id: $caseId) { ${caseAuthorizationFields} }
  tasks(first: $first, after: $after, orderBy: created_at, orderMode: asc, filters: $filters) {
    pageInfo { endCursor hasNextPage }
    edges {
      cursor
      node {
        id standard_id entity_type name created_at updated_at modified due_date
        status { id template { name } }
        objectAssignee { id }
      }
    }
  }
}`;
const objectsDocument = `query ${OBJECTS_OPERATION}($caseId: String!, $first: Int!, $after: ID) {
  ${principalFields}
  case(id: $caseId) {
    ${caseAuthorizationFields}
    objects(first: $first, after: $after, orderBy: created_at, orderMode: asc) {
      pageInfo { endCursor hasNextPage }
      edges {
        cursor types
        node {
          __typename
          ... on StixObject { id standard_id entity_type representative { main } updated_at }
          ... on StixRelationship { id standard_id entity_type representative { main } updated_at }
        }
      }
    }
  }
}`;

const queryFamily = {
	qualificationDocument,
	schemaOperations,
	rootDocument,
	tasksDocument,
	objectsDocument,
	selection: ["case_identity", "visible_work", "visible_object_membership"],
};

function isObject(value: unknown): value is JsonObject {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function canonicalJson(value: unknown): string {
	if (value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "number") {
		return JSON.stringify(value);
	}
	if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
	if (isObject(value)) {
		return `{${Object.keys(value)
			.filter((key) => value[key] !== undefined)
			.sort()
			.map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
			.join(",")}}`;
	}
	throw new Error("Unsupported JSON value");
}

function digest(value: unknown): string {
	return `sha256:${createHash("sha256").update(canonicalJson(value)).digest("hex")}`;
}

const queryFamilyDigest = digest(queryFamily);

export const OPENCTI_LIVE_ORIENTATION_RECIPE_V1 = Object.freeze({
	recipeId: "opencti-live-orientation-qualification/v1" as const,
	queryFamilyDigest,
	schemaContractVersion: "opencti-orientation-selected-schema/v1" as const,
});

export interface OpenCtiLiveOrientationExpected {
	recipeId: "opencti-live-orientation-qualification/v1";
	queryFamilyDigest: string;
	schemaContractVersion: "opencti-orientation-selected-schema/v1";
	expectedPrincipalRef?: string;
	expectedInstanceId?: string;
	expectedVersion?: string;
	expectedSchemaDigest?: string;
}

export interface OpenCtiLiveCredential {
	credentialSlot: string;
	resolveToken(): Promise<string>;
}

export interface OpenCtiLiveOrientationBudgets {
	requestTimeoutMs: number;
	pageSize: number;
	maxPages: number;
	maxResponseBytes: number;
}

export interface OpenCtiLiveOrientationEvidence {
	recipeId: "opencti-live-orientation-qualification/v1";
	instanceId: string;
	principalRef: string;
	version: string;
	schemaDigest: string;
	queryFamilyDigest: string;
	targetFingerprint: string;
	qualificationId: string;
	qualifiedAt: string;
}

export interface QualifiedOpenCtiLiveOrientation {
	orientation: OrientationReadPort;
	accessPrincipal: AccessPrincipalBinding;
	evidence: OpenCtiLiveOrientationEvidence;
}

function safeFailure(code: string): never {
	const message =
		code === "transport_timeout"
			? "OpenCTI request did not complete within the configured budget"
			: code === "authorization_or_visibility_changed"
				? "OpenCTI authorization could not be proved stable"
				: "OpenCTI response did not match the qualified Orientation contract";
	throw Object.assign(new Error(message), { code });
}

function assertExact(value: unknown, keys: readonly string[]): JsonObject {
	if (!isObject(value)) safeFailure("schema_or_mapping_mismatch");
	const actual = Object.keys(value).sort();
	const expected = [...keys].sort();
	if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
		safeFailure("schema_or_mapping_mismatch");
	}
	return value;
}

function requiredString(value: unknown): string {
	if (typeof value !== "string" || value.length === 0) safeFailure("schema_or_mapping_mismatch");
	return value;
}

function nullableString(value: unknown): string | undefined {
	if (value === null) return undefined;
	return requiredString(value);
}

function stringIdList(value: unknown, itemKeys: readonly string[]): string[] {
	if (value === null) return [];
	if (!Array.isArray(value)) safeFailure("schema_or_mapping_mismatch");
	return value.map((item) => requiredString(assertExact(item, itemKeys).id)).sort();
}

function principalFingerprint(value: unknown, expectedPrincipalRef: string): JsonObject {
	const principal = assertExact(value, ["id", "capabilities", "allowed_marking"]);
	if (requiredString(principal.id) !== expectedPrincipalRef || !Array.isArray(principal.capabilities)) {
		safeFailure("authorization_or_visibility_changed");
	}
	const capabilities = principal.capabilities.map((entry) => requiredString(assertExact(entry, ["name"]).name)).sort();
	return {
		id: expectedPrincipalRef,
		capabilities,
		allowedMarkingRefs: stringIdList(principal.allowed_marking, ["id"]),
	};
}

function caseAuthorizationFingerprint(value: unknown, expectedCaseRef: string): JsonObject {
	if (!isObject(value)) safeFailure("schema_or_mapping_mismatch");
	const expectedKeys = [
		"id",
		"authorized_members_activation_date",
		"currentUserAccessRight",
		"objectMarking",
		"objectOrganization",
	];
	const allowedSupplementalKeys = new Set([
		"objects",
		"standard_id",
		"entity_type",
		"name",
		"created_at",
		"updated_at",
		"modified",
		"status",
	]);
	const actualKeys = Object.keys(value);
	if (
		expectedKeys.some((key) => !actualKeys.includes(key)) ||
		actualKeys.some((key) => !expectedKeys.includes(key) && !allowedSupplementalKeys.has(key))
	) {
		safeFailure("schema_or_mapping_mismatch");
	}
	const root = value;
	if (requiredString(root.id) !== expectedCaseRef) safeFailure("authorization_or_visibility_changed");
	return {
		id: expectedCaseRef,
		authorizedMembersActivationDate: nullableString(root.authorized_members_activation_date),
		currentUserAccessRight: nullableString(root.currentUserAccessRight),
		markingRefs: stringIdList(root.objectMarking, ["id"]),
		organizationRefs: stringIdList(root.objectOrganization, ["id"]),
	};
}

function authorizationVersion(data: JsonObject, principalRef: string, caseRef: string): string {
	if (data.case === null) safeFailure("authorization_or_visibility_changed");
	return digest({
		principal: principalFingerprint(data.me, principalRef),
		case: caseAuthorizationFingerprint(data.case, caseRef),
	});
}

function sourceStatus(value: unknown): { id: string; name: string } | undefined {
	if (value === null) return undefined;
	const status = assertExact(value, ["id", "template"]);
	const template = assertExact(status.template, ["name"]);
	return { id: requiredString(status.id), name: requiredString(template.name) };
}

function decodeCase(value: unknown): OpenCtiCaseIdentityV1 {
	const item = assertExact(value, [
		"id",
		"authorized_members_activation_date",
		"currentUserAccessRight",
		"objectMarking",
		"objectOrganization",
		"standard_id",
		"entity_type",
		"name",
		"created_at",
		"updated_at",
		"modified",
		"status",
	]);
	const entityType = requiredString(item.entity_type);
	if (entityType !== "Case-Incident" && entityType !== "Case-Rfi" && entityType !== "Case-Rft") {
		safeFailure("schema_or_mapping_mismatch");
	}
	const standardId = nullableString(item.standard_id);
	const status = sourceStatus(item.status);
	const createdAt = nullableString(item.created_at);
	const modified = nullableString(item.modified);
	const updatedAt = nullableString(item.updated_at);
	const mapped: OpenCtiCaseIdentityV1 = {
		internalId: requiredString(item.id),
		...(standardId === undefined ? {} : { standardId }),
		entityType,
		displayName: requiredString(item.name),
		...(status === undefined ? {} : { sourceStatus: status }),
		...(createdAt === undefined ? {} : { createdAt }),
		observedVersion: {
			...(modified === undefined ? {} : { modified }),
			...(updatedAt === undefined ? {} : { updatedAt }),
			contentDigest: "",
		},
	};
	return { ...mapped, observedVersion: { ...mapped.observedVersion, contentDigest: digest(mapped) } };
}

function decodeTask(value: unknown): OpenCtiVisibleWorkV1 {
	const item = assertExact(value, [
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
	]);
	if (requiredString(item.entity_type) !== "Task") safeFailure("schema_or_mapping_mismatch");
	const status = sourceStatus(item.status);
	const dueAt = nullableString(item.due_date);
	const modified = nullableString(item.modified);
	const updatedAt = nullableString(item.updated_at);
	const mapped: OpenCtiVisibleWorkV1 = {
		taskRef: requiredString(item.id),
		name: requiredString(item.name),
		...(status === undefined ? {} : { sourceStatus: status }),
		...(dueAt === undefined ? {} : { dueAt }),
		assigneeRefs: stringIdList(item.objectAssignee, ["id"]),
		observedVersion: {
			...(modified === undefined ? {} : { modified }),
			...(updatedAt === undefined ? {} : { updatedAt }),
			contentDigest: "",
		},
	};
	return { ...mapped, observedVersion: { ...mapped.observedVersion, contentDigest: digest(mapped) } };
}

function decodeObject(value: unknown): OpenCtiVisibleObjectMembershipV1 {
	const item = assertExact(value, ["__typename", "id", "standard_id", "entity_type", "representative", "updated_at"]);
	requiredString(item.__typename);
	const representative = assertExact(item.representative, ["main"]);
	const standardId = nullableString(item.standard_id);
	const updatedAt = nullableString(item.updated_at);
	const mapped: OpenCtiVisibleObjectMembershipV1 = {
		objectRef: requiredString(item.id),
		...(standardId === undefined ? {} : { standardId }),
		entityType: requiredString(item.entity_type),
		displayLabel: requiredString(representative.main),
		membership: "visible_case_object_reference" as const,
		observedVersion: { ...(updatedAt === undefined ? {} : { updatedAt }), contentDigest: "" },
	};
	return { ...mapped, observedVersion: { ...mapped.observedVersion, contentDigest: digest(mapped) } };
}

function normalizeEndpoint(endpoint: string): string {
	let url: URL;
	try {
		url = new URL(endpoint);
	} catch {
		safeFailure("schema_or_mapping_mismatch");
	}
	if (
		url.protocol !== "https:" ||
		url.username ||
		url.password ||
		url.search ||
		url.hash ||
		!url.pathname.endsWith("/graphql")
	) {
		safeFailure("schema_or_mapping_mismatch");
	}
	url.pathname = url.pathname.replace(/\/{2,}/g, "/");
	return url.href;
}

function validateBudgets(value: OpenCtiLiveOrientationBudgets): OpenCtiLiveOrientationBudgets {
	if (
		!Number.isSafeInteger(value.requestTimeoutMs) ||
		value.requestTimeoutMs < 1 ||
		value.requestTimeoutMs > 120_000 ||
		!Number.isSafeInteger(value.pageSize) ||
		value.pageSize < 1 ||
		value.pageSize > 500 ||
		!Number.isSafeInteger(value.maxPages) ||
		value.maxPages < 1 ||
		value.maxPages > 100 ||
		!Number.isSafeInteger(value.maxResponseBytes) ||
		value.maxResponseBytes < 1_024 ||
		value.maxResponseBytes > 50_000_000
	) {
		safeFailure("schema_or_mapping_mismatch");
	}
	return { ...value };
}

async function waitWithinSignal<T>(operation: Promise<T>, signal: AbortSignal): Promise<T> {
	if (signal.aborted) safeFailure("transport_timeout");
	return await new Promise<T>((resolve, reject) => {
		const onAbort = () => reject(Object.assign(new Error("OpenCTI request aborted"), { code: "transport_timeout" }));
		signal.addEventListener("abort", onAbort, { once: true });
		operation.then(resolve, reject).finally(() => signal.removeEventListener("abort", onAbort));
	});
}

function errorCode(error: unknown): string | undefined {
	return typeof error === "object" && error !== null && "code" in error && typeof error.code === "string"
		? error.code
		: undefined;
}

async function readResponseText(response: Response, signal: AbortSignal, maxBytes: number): Promise<string> {
	if (response.body === null) return "";
	const reader = response.body.getReader();
	const chunks: Uint8Array[] = [];
	let total = 0;
	try {
		while (true) {
			const chunk = await waitWithinSignal(reader.read(), signal);
			if (chunk.done) break;
			total += chunk.value.byteLength;
			if (total > maxBytes) {
				void reader.cancel().catch(() => undefined);
				safeFailure("schema_or_mapping_mismatch");
			}
			chunks.push(chunk.value);
		}
		return Buffer.concat(chunks, total).toString("utf8");
	} finally {
		if (signal.aborted) void reader.cancel().catch(() => undefined);
		reader.releaseLock();
	}
}

class OpenCtiGraphqlClient {
	private readonly endpoint: string;
	private readonly credential: OpenCtiLiveCredential;
	private readonly fetchImpl: typeof fetch;
	private readonly budgets: OpenCtiLiveOrientationBudgets;

	constructor(input: {
		endpoint: string;
		credential: OpenCtiLiveCredential;
		fetchImpl: typeof fetch;
		budgets: OpenCtiLiveOrientationBudgets;
	}) {
		this.endpoint = input.endpoint;
		this.credential = input.credential;
		this.fetchImpl = input.fetchImpl;
		this.budgets = input.budgets;
	}

	async query(operationName: string, query: string, variables: JsonObject, signal?: AbortSignal): Promise<JsonObject> {
		if (signal?.aborted) safeFailure("transport_timeout");
		const token = await this.credential.resolveToken();
		if (!token || /[\r\n]/.test(token)) safeFailure("authorization_or_visibility_changed");
		const controller = new AbortController();
		const onAbort = () => controller.abort();
		signal?.addEventListener("abort", onAbort, { once: true });
		const timeout = setTimeout(() => controller.abort(), this.budgets.requestTimeoutMs);
		try {
			let response: Response;
			try {
				response = await waitWithinSignal(
					this.fetchImpl(this.endpoint, {
						method: "POST",
						headers: {
							authorization: `Bearer ${token}`,
							"content-type": "application/json",
							accept: "application/json",
						},
						body: JSON.stringify({ operationName, query, variables }),
						signal: controller.signal,
					}),
					controller.signal,
				);
			} catch (error) {
				safeFailure(
					controller.signal.aborted || errorCode(error) === "transport_timeout"
						? "transport_timeout"
						: "schema_or_mapping_mismatch",
				);
			}
			if (response.status === 401 || response.status === 403) safeFailure("authorization_or_visibility_changed");
			if (!response.ok)
				safeFailure(
					response.status === 408 || response.status === 504 ? "transport_timeout" : "schema_or_mapping_mismatch",
				);
			const mediaType = response.headers.get("content-type")?.split(";", 1)[0]?.trim().toLowerCase();
			if (mediaType !== "application/json" && mediaType !== "application/graphql-response+json") {
				safeFailure("schema_or_mapping_mismatch");
			}
			const declaredLength = response.headers.get("content-length");
			if (declaredLength !== null && Number(declaredLength) > this.budgets.maxResponseBytes) {
				safeFailure("schema_or_mapping_mismatch");
			}
			let text: string;
			try {
				text = await readResponseText(response, controller.signal, this.budgets.maxResponseBytes);
			} catch (error) {
				safeFailure(
					controller.signal.aborted || errorCode(error) === "transport_timeout"
						? "transport_timeout"
						: "schema_or_mapping_mismatch",
				);
			}
			if (Buffer.byteLength(text, "utf8") > this.budgets.maxResponseBytes) safeFailure("schema_or_mapping_mismatch");
			let parsed: unknown;
			try {
				parsed = JSON.parse(text);
			} catch {
				safeFailure("schema_or_mapping_mismatch");
			}
			if (!isObject(parsed)) safeFailure("schema_or_mapping_mismatch");
			const keys = Object.keys(parsed).sort();
			if (keys.some((key) => key !== "data" && key !== "errors") || !("data" in parsed)) {
				safeFailure("schema_or_mapping_mismatch");
			}
			if ("errors" in parsed && (!Array.isArray(parsed.errors) || parsed.errors.length > 0)) {
				safeFailure("schema_or_mapping_mismatch");
			}
			if (!isObject(parsed.data)) safeFailure("schema_or_mapping_mismatch");
			return parsed.data;
		} finally {
			clearTimeout(timeout);
			signal?.removeEventListener("abort", onAbort);
		}
	}
}

const expectedTypeKinds: Readonly<Record<string, string>> = {
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
	StixObjectOrStixRelationshipsOrdering: "ENUM",
	String: "SCALAR",
	Task: "OBJECT",
	TaskConnection: "OBJECT",
	TaskEdge: "OBJECT",
	TasksOrdering: "ENUM",
};

function decodeTypeRef(value: unknown): string {
	const type = assertExact(value, ["kind", "name", "ofType"]);
	if (type.kind === "NON_NULL" || type.kind === "LIST") {
		if (type.name !== null || !isObject(type.ofType)) safeFailure("schema_or_mapping_mismatch");
		return `${type.kind}(${decodeTypeRef(type.ofType)})`;
	}
	if (
		(type.kind !== "SCALAR" &&
			type.kind !== "OBJECT" &&
			type.kind !== "INTERFACE" &&
			type.kind !== "UNION" &&
			type.kind !== "ENUM" &&
			type.kind !== "INPUT_OBJECT") ||
		type.ofType !== null
	) {
		safeFailure("schema_or_mapping_mismatch");
	}
	return `${type.kind}:${requiredString(type.name)}`;
}

function expectedTypeRef(signature: string): string {
	if (signature.endsWith("!")) return `NON_NULL(${expectedTypeRef(signature.slice(0, -1))})`;
	if (signature.startsWith("[") && signature.endsWith("]")) {
		return `LIST(${expectedTypeRef(signature.slice(1, -1))})`;
	}
	const kind = expectedTypeKinds[signature];
	if (!kind) throw new Error(`Unsupported expected OpenCTI TypeRef ${signature}`);
	return `${kind}:${signature}`;
}

interface FieldCatalogEntry {
	type: string;
	arguments: ReadonlyMap<string, string>;
}

function fieldCatalog(value: unknown, expectedKind: string): Map<string, FieldCatalogEntry> {
	const type = assertExact(value, ["kind", "fields", "enumValues", "possibleTypes"]);
	if (type.kind !== expectedKind || !Array.isArray(type.fields)) safeFailure("schema_or_mapping_mismatch");
	const fields = new Map<string, FieldCatalogEntry>();
	for (const rawField of type.fields) {
		const field = assertExact(rawField, ["name", "args", "type"]);
		if (!Array.isArray(field.args)) safeFailure("schema_or_mapping_mismatch");
		const argumentsByName = new Map<string, string>();
		for (const rawArgument of field.args) {
			const argument = assertExact(rawArgument, ["name", "type"]);
			const name = requiredString(argument.name);
			if (argumentsByName.has(name)) safeFailure("schema_or_mapping_mismatch");
			argumentsByName.set(name, decodeTypeRef(argument.type));
		}
		const name = requiredString(field.name);
		if (fields.has(name)) safeFailure("schema_or_mapping_mismatch");
		fields.set(name, { type: decodeTypeRef(field.type), arguments: argumentsByName });
	}
	return fields;
}

interface FieldRequirement {
	type: string;
	arguments?: Readonly<Record<string, string>>;
}

function requireFields(
	catalog: ReadonlyMap<string, FieldCatalogEntry>,
	requirements: Readonly<Record<string, FieldRequirement>>,
): void {
	for (const [name, requirement] of Object.entries(requirements)) {
		const actual = catalog.get(name);
		if (!actual || actual.type !== expectedTypeRef(requirement.type)) safeFailure("schema_or_mapping_mismatch");
		for (const [argumentName, signature] of Object.entries(requirement.arguments ?? {})) {
			if (actual.arguments.get(argumentName) !== expectedTypeRef(signature)) {
				safeFailure("schema_or_mapping_mismatch");
			}
		}
	}
}

function requireEnum(value: unknown, names: readonly string[]): void {
	const type = assertExact(value, ["kind", "fields", "enumValues", "possibleTypes"]);
	if (type.kind !== "ENUM" || !Array.isArray(type.enumValues)) safeFailure("schema_or_mapping_mismatch");
	const actual = new Set(type.enumValues.map((entry) => requiredString(assertExact(entry, ["name"]).name)));
	if (names.some((name) => !actual.has(name))) safeFailure("schema_or_mapping_mismatch");
}

function requireInputFields(value: unknown, requirements: Readonly<Record<string, string>>): void {
	const type = assertExact(value, ["kind", "inputFields"]);
	if (type.kind !== "INPUT_OBJECT" || !Array.isArray(type.inputFields)) safeFailure("schema_or_mapping_mismatch");
	const actual = new Map<string, string>();
	for (const entry of type.inputFields) {
		const field = assertExact(entry, ["name", "type"]);
		const name = requiredString(field.name);
		if (actual.has(name)) safeFailure("schema_or_mapping_mismatch");
		actual.set(name, decodeTypeRef(field.type));
	}
	for (const [name, signature] of Object.entries(requirements)) {
		if (actual.get(name) !== expectedTypeRef(signature)) safeFailure("schema_or_mapping_mismatch");
	}
}

function runtimePossibleTypes(value: unknown, expectedKind: "INTERFACE" | "UNION"): ReadonlySet<string> {
	const type = assertExact(value, ["kind", "fields", "enumValues", "possibleTypes"]);
	if (type.kind !== expectedKind || !Array.isArray(type.possibleTypes) || type.possibleTypes.length === 0) {
		safeFailure("schema_or_mapping_mismatch");
	}
	const possibleTypes = new Set<string>();
	for (const possibleType of type.possibleTypes) {
		const name = requiredString(assertExact(possibleType, ["name"]).name);
		if (possibleTypes.has(name)) safeFailure("schema_or_mapping_mismatch");
		possibleTypes.add(name);
	}
	return possibleTypes;
}

function requireRuntimeOverlap(returnTypes: ReadonlySet<string>, fragmentTypes: ReadonlySet<string>): void {
	if (![...fragmentTypes].some((name) => returnTypes.has(name))) safeFailure("schema_or_mapping_mismatch");
}

function validateSelectedSchema(data: JsonObject): void {
	const keys = [
		"queryType",
		"appInfoType",
		"settingsType",
		"caseType",
		"taskType",
		"meType",
		"capabilityType",
		"markingDefinitionType",
		"organizationType",
		"statusType",
		"statusTemplateType",
		"assigneeType",
		"taskConnectionType",
		"taskEdgeType",
		"objectConnectionType",
		"objectEdgeType",
		"pageInfoType",
		"stixObjectType",
		"stixRelationshipType",
		"representativeType",
		"objectUnionType",
		"tasksOrderingType",
		"objectOrderingType",
		"orderingModeType",
		"filterModeType",
		"filterOperatorType",
		"filterGroupType",
		"filterType",
	];
	assertExact(data, keys);
	requireFields(fieldCatalog(data.queryType, "OBJECT"), {
		about: { type: "AppInfo" },
		settings: { type: "Settings!" },
		me: { type: "MeUser!" },
		case: { type: "Case", arguments: { id: "String!" } },
		tasks: {
			type: "TaskConnection",
			arguments: {
				first: "Int",
				after: "ID",
				orderBy: "TasksOrdering",
				orderMode: "OrderingMode",
				filters: "FilterGroup",
			},
		},
	});
	requireFields(fieldCatalog(data.appInfoType, "OBJECT"), { version: { type: "String!" } });
	requireFields(fieldCatalog(data.settingsType, "OBJECT"), {
		id: { type: "ID!" },
		platform_url: { type: "String" },
	});
	requireFields(fieldCatalog(data.caseType, "INTERFACE"), {
		id: { type: "ID!" },
		standard_id: { type: "String!" },
		entity_type: { type: "String!" },
		name: { type: "String!" },
		created_at: { type: "DateTime!" },
		updated_at: { type: "DateTime!" },
		modified: { type: "DateTime" },
		status: { type: "Status" },
		authorized_members_activation_date: { type: "DateTime" },
		currentUserAccessRight: { type: "String" },
		objectMarking: { type: "[MarkingDefinition!]" },
		objectOrganization: { type: "[Organization!]" },
		objects: {
			type: "StixObjectOrStixRelationshipRefConnection",
			arguments: {
				first: "Int",
				after: "ID",
				orderBy: "StixObjectOrStixRelationshipsOrdering",
				orderMode: "OrderingMode",
			},
		},
	});
	requireFields(fieldCatalog(data.taskType, "OBJECT"), {
		id: { type: "ID!" },
		standard_id: { type: "String!" },
		entity_type: { type: "String!" },
		name: { type: "String!" },
		created_at: { type: "DateTime!" },
		updated_at: { type: "DateTime!" },
		modified: { type: "DateTime" },
		due_date: { type: "DateTime" },
		status: { type: "Status" },
		objectAssignee: { type: "[Assignee!]" },
	});
	requireFields(fieldCatalog(data.meType, "OBJECT"), {
		id: { type: "ID!" },
		capabilities: { type: "[Capability!]!" },
		allowed_marking: { type: "[MarkingDefinition!]" },
	});
	requireFields(fieldCatalog(data.capabilityType, "OBJECT"), { name: { type: "String!" } });
	requireFields(fieldCatalog(data.markingDefinitionType, "OBJECT"), { id: { type: "ID!" } });
	requireFields(fieldCatalog(data.organizationType, "OBJECT"), { id: { type: "ID!" } });
	requireFields(fieldCatalog(data.statusType, "OBJECT"), {
		id: { type: "ID!" },
		template: { type: "StatusTemplate" },
	});
	requireFields(fieldCatalog(data.statusTemplateType, "OBJECT"), { name: { type: "String!" } });
	requireFields(fieldCatalog(data.assigneeType, "OBJECT"), { id: { type: "ID!" } });
	requireFields(fieldCatalog(data.taskConnectionType, "OBJECT"), {
		pageInfo: { type: "PageInfo!" },
		edges: { type: "[TaskEdge!]!" },
	});
	requireFields(fieldCatalog(data.taskEdgeType, "OBJECT"), {
		cursor: { type: "String!" },
		node: { type: "Task!" },
	});
	requireFields(fieldCatalog(data.objectConnectionType, "OBJECT"), {
		pageInfo: { type: "PageInfo!" },
		edges: { type: "[StixObjectOrStixRelationshipRefEdge]" },
	});
	requireFields(fieldCatalog(data.objectEdgeType, "OBJECT"), {
		cursor: { type: "String!" },
		types: { type: "[String]!" },
		node: { type: "StixObjectOrStixRelationship!" },
	});
	requireFields(fieldCatalog(data.pageInfoType, "OBJECT"), {
		endCursor: { type: "String!" },
		hasNextPage: { type: "Boolean!" },
	});
	requireFields(fieldCatalog(data.stixObjectType, "INTERFACE"), {
		id: { type: "ID!" },
		standard_id: { type: "String!" },
		entity_type: { type: "String!" },
		representative: { type: "Representative!" },
		updated_at: { type: "DateTime!" },
	});
	requireFields(fieldCatalog(data.stixRelationshipType, "INTERFACE"), {
		id: { type: "ID!" },
		standard_id: { type: "String!" },
		entity_type: { type: "String!" },
		representative: { type: "Representative!" },
		updated_at: { type: "DateTime!" },
	});
	requireFields(fieldCatalog(data.representativeType, "OBJECT"), { main: { type: "String!" } });
	const objectUnionTypes = runtimePossibleTypes(data.objectUnionType, "UNION");
	requireRuntimeOverlap(objectUnionTypes, runtimePossibleTypes(data.stixObjectType, "INTERFACE"));
	requireRuntimeOverlap(objectUnionTypes, runtimePossibleTypes(data.stixRelationshipType, "INTERFACE"));
	requireEnum(data.tasksOrderingType, ["created_at"]);
	requireEnum(data.objectOrderingType, ["created_at"]);
	requireEnum(data.orderingModeType, ["asc"]);
	requireEnum(data.filterModeType, ["and", "or"]);
	requireEnum(data.filterOperatorType, ["eq"]);
	requireInputFields(data.filterGroupType, {
		mode: "FilterMode!",
		filters: "[Filter!]!",
		filterGroups: "[FilterGroup!]!",
	});
	requireInputFields(data.filterType, {
		key: "[String!]!",
		values: "[Any!]!",
		operator: "FilterOperator",
		mode: "FilterMode",
	});
}

interface ObservationState {
	workPageIndex: number;
	objectPageIndex: number;
}

class OpenCtiGraphqlOrientationTransport implements OpenCtiOrientationTransportPort {
	private readonly client: OpenCtiGraphqlClient;
	private readonly principalRef: string;
	private readonly budgets: OpenCtiLiveOrientationBudgets;
	private readonly observations = new Map<string, ObservationState>();

	constructor(client: OpenCtiGraphqlClient, principalRef: string, budgets: OpenCtiLiveOrientationBudgets) {
		this.client = client;
		this.principalRef = principalRef;
		this.budgets = budgets;
	}

	async execute(request: OpenCtiOrientationTransportRequest, options?: { signal?: AbortSignal }): Promise<unknown> {
		if (request.accessPrincipal.principalRef !== this.principalRef) {
			safeFailure("authorization_or_visibility_changed");
		}
		if (request.kind === "case_root") return await this.root(request, options?.signal);
		return await this.page(request, options?.signal);
	}

	private async root(
		request: Extract<OpenCtiOrientationTransportRequest, { kind: "case_root" }>,
		signal?: AbortSignal,
	): Promise<unknown> {
		const data = await this.client.query(ROOT_OPERATION, rootDocument, { caseId: request.caseRef }, signal);
		assertExact(data, ["me", "case"]);
		if (data.case === null) {
			if (request.probe === "end") this.observations.delete(request.observationId);
			return { outcome: "not_visible" };
		}
		principalFingerprint(data.me, this.principalRef);
		caseAuthorizationFingerprint(data.case, request.caseRef);
		const result = {
			outcome: "visible" as const,
			authorizationVersion: authorizationVersion(data, this.principalRef, request.caseRef),
			item: decodeCase(data.case),
		};
		if (request.probe === "start") {
			if (this.observations.has(request.observationId)) safeFailure("observation_drift");
			this.observations.set(request.observationId, { workPageIndex: 0, objectPageIndex: 0 });
		} else {
			if (!this.observations.delete(request.observationId)) safeFailure("observation_drift");
		}
		return result;
	}

	private async page(
		request: Extract<
			OpenCtiOrientationTransportRequest,
			{ kind: "visible_work_page" | "visible_object_membership_page" }
		>,
		signal?: AbortSignal,
	): Promise<unknown> {
		const state = this.observations.get(request.observationId);
		if (!state) safeFailure("observation_drift");
		const work = request.kind === "visible_work_page";
		const pageIndex = work ? state.workPageIndex : state.objectPageIndex;
		if (pageIndex >= this.budgets.maxPages) {
			return { outcome: "incomplete" };
		}
		const data = await this.client.query(
			work ? TASKS_OPERATION : OBJECTS_OPERATION,
			work ? tasksDocument : objectsDocument,
			{
				caseId: request.caseRef,
				first: this.budgets.pageSize,
				after: request.afterCursor,
				...(work
					? {
							filters: {
								mode: "and",
								filters: [
									{ key: ["entity_type"], values: ["Task"], operator: "eq", mode: "or" },
									{ key: ["objects"], values: [request.caseRef], operator: "eq", mode: "or" },
								],
								filterGroups: [],
							},
						}
					: {}),
			},
			signal,
		);
		assertExact(data, work ? ["me", "case", "tasks"] : ["me", "case"]);
		const version = authorizationVersion(data, this.principalRef, request.caseRef);
		const connection = work
			? data.tasks
			: assertExact(data.case, [
					"id",
					"authorized_members_activation_date",
					"currentUserAccessRight",
					"objectMarking",
					"objectOrganization",
					"objects",
				]).objects;
		const decoded = assertExact(connection, ["pageInfo", "edges"]);
		const pageInfo = assertExact(decoded.pageInfo, ["endCursor", "hasNextPage"]);
		if (typeof pageInfo.hasNextPage !== "boolean" || !Array.isArray(decoded.edges)) {
			safeFailure("schema_or_mapping_mismatch");
		}
		if (typeof pageInfo.endCursor !== "string") safeFailure("schema_or_mapping_mismatch");
		const endCursor = pageInfo.endCursor;
		if (
			(pageInfo.hasNextPage && (!endCursor || endCursor === request.afterCursor || decoded.edges.length === 0)) ||
			(decoded.edges.length > 0 &&
				requiredString(
					assertExact(decoded.edges.at(-1), work ? ["cursor", "node"] : ["cursor", "types", "node"]).cursor,
				) !== endCursor)
		) {
			safeFailure("cursor_continuity_lost");
		}
		const items = decoded.edges.map((rawEdge) => {
			const edge = assertExact(rawEdge, work ? ["cursor", "node"] : ["cursor", "types", "node"]);
			requiredString(edge.cursor);
			if (!work && !Array.isArray(edge.types)) safeFailure("schema_or_mapping_mismatch");
			return { authorization: "authorized" as const, value: work ? decodeTask(edge.node) : decodeObject(edge.node) };
		});
		if (work) state.workPageIndex++;
		else state.objectPageIndex++;
		return {
			outcome: "page",
			pageId: digest({
				observationId: request.observationId,
				kind: request.kind,
				pageIndex,
				after: request.afterCursor,
				endCursor,
				items,
			}),
			pageIndex,
			afterCursor: request.afterCursor,
			endCursor,
			hasNextPage: pageInfo.hasNextPage,
			authorizationVersion: version,
			items,
		};
	}
}

export async function qualifyOpenCtiLiveOrientation(input: {
	endpoint: string;
	credential: OpenCtiLiveCredential;
	expected: OpenCtiLiveOrientationExpected;
	budgets: OpenCtiLiveOrientationBudgets;
	fetchImpl?: typeof fetch;
	signal?: AbortSignal;
}): Promise<QualifiedOpenCtiLiveOrientation> {
	if (
		input.expected.recipeId !== OPENCTI_LIVE_ORIENTATION_RECIPE_V1.recipeId ||
		input.expected.queryFamilyDigest !== OPENCTI_LIVE_ORIENTATION_RECIPE_V1.queryFamilyDigest ||
		input.expected.schemaContractVersion !== OPENCTI_LIVE_ORIENTATION_RECIPE_V1.schemaContractVersion ||
		!input.credential.credentialSlot.trim()
	) {
		safeFailure("schema_or_mapping_mismatch");
	}
	const endpoint = normalizeEndpoint(input.endpoint);
	const budgets = validateBudgets(input.budgets);
	const client = new OpenCtiGraphqlClient({
		endpoint,
		credential: input.credential,
		fetchImpl: input.fetchImpl ?? fetch,
		budgets,
	});
	const target = await client.query(QUALIFICATION_OPERATION, qualificationDocument, {}, input.signal);
	assertExact(target, ["about", "settings", "me"]);
	const about = assertExact(target.about, ["version"]);
	const settings = assertExact(target.settings, ["id", "platform_url"]);
	const principal = assertExact(target.me, ["id", "capabilities", "allowed_marking"]);
	const version = requiredString(about.version);
	const instanceId = requiredString(settings.id);
	if (settings.platform_url !== null) requiredString(settings.platform_url);
	const principalRef = requiredString(principal.id);
	principalFingerprint(principal, principalRef);
	const credentialRef = digest({
		binding: "opencti-live-credential/v1",
		endpoint,
		principalRef,
		credentialSlot: input.credential.credentialSlot.trim(),
	});
	const schemaEntries: Array<readonly [string, unknown]> = [];
	for (const operation of schemaOperations) {
		const result = await client.query(operation.name, operation.document, {}, input.signal);
		assertExact(result, operation.aliases);
		for (const alias of operation.aliases) schemaEntries.push([alias, result[alias]]);
	}
	const schema = Object.fromEntries(schemaEntries);
	validateSelectedSchema(schema);
	const schemaDigest = digest(schema);
	if (
		(input.expected.expectedPrincipalRef !== undefined && input.expected.expectedPrincipalRef !== principalRef) ||
		(input.expected.expectedInstanceId !== undefined && input.expected.expectedInstanceId !== instanceId) ||
		(input.expected.expectedVersion !== undefined && input.expected.expectedVersion !== version) ||
		(input.expected.expectedSchemaDigest !== undefined && input.expected.expectedSchemaDigest !== schemaDigest)
	) {
		safeFailure("schema_or_mapping_mismatch");
	}
	const targetFingerprint = digest({
		endpoint,
		instanceId,
		version,
		tlsVerification: "node-default-required",
		budgets,
		queryFamilyDigest,
	});
	const qualifiedAt = new Date().toISOString();
	const qualificationId = digest({
		recipeId: input.expected.recipeId,
		instanceId,
		principalRef,
		version,
		schemaDigest,
		queryFamilyDigest,
		targetFingerprint,
	});
	const source: OrientationSourceIdentityV1 = {
		instanceId: digest({ endpoint, instanceId }),
		adapterArtifactDigest: digest({ mappingVersion: "opencti-live-orientation-mapping/v1", queryFamily }),
		targetFingerprint,
		schemaDigest,
		qualificationId,
		selectionDigest: digest(queryFamily.selection),
	};
	const observedSource = { ...source };
	const transport = new OpenCtiGraphqlOrientationTransport(client, principalRef, budgets);
	return {
		orientation: new OpenCtiTransportOrientationAdapter({ source, observedSource, transport }),
		accessPrincipal: { principalRef, credentialRef },
		evidence: {
			recipeId: input.expected.recipeId,
			instanceId,
			principalRef,
			version,
			schemaDigest,
			queryFamilyDigest,
			targetFingerprint,
			qualificationId,
			qualifiedAt,
		},
	};
}
