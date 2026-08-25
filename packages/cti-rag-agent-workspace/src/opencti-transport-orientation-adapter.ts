import { randomUUID } from "node:crypto";
import type {
	AccessPrincipalBinding,
	OpenCtiCaseIdentityV1,
	OpenCtiOrientationTransportPort,
	OpenCtiVisibleObjectMembershipV1,
	OpenCtiVisibleWorkV1,
	OrientationCollection,
	OrientationObservationV1,
	OrientationReadPort,
	OrientationSourceIdentityV1,
} from "./types.ts";

type JsonObject = Readonly<Record<string, unknown>>;

function isObject(value: unknown): value is JsonObject {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exactKeys(value: JsonObject, keys: readonly string[]): boolean {
	const actual = Object.keys(value).sort();
	const expected = [...keys].sort();
	return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function fail(code: string, message: string): never {
	throw Object.assign(new Error(message), { code });
}

function decodeRoot(value: unknown): { item: OpenCtiCaseIdentityV1; authorizationVersion: string } {
	if (!isObject(value)) fail("schema_or_mapping_mismatch", "Invalid root response");
	if (value.outcome === "not_visible" && exactKeys(value, ["outcome"])) {
		fail("case_root_not_found_or_not_visible", "Case root unavailable");
	}
	if (
		value.outcome !== "visible" ||
		!exactKeys(value, ["outcome", "authorizationVersion", "item"]) ||
		typeof value.authorizationVersion !== "string" ||
		!isObject(value.item)
	) {
		fail("schema_or_mapping_mismatch", "Invalid root response");
	}
	return { item: value.item as unknown as OpenCtiCaseIdentityV1, authorizationVersion: value.authorizationVersion };
}

interface DecodedPage<T> {
	pageId: string;
	pageIndex: number;
	afterCursor: string | null;
	endCursor: string | null;
	hasNextPage: boolean;
	authorizationVersion: string;
	items: readonly { authorization: "authorized" | "denied"; value?: T }[];
}

function decodePage<T>(value: unknown): DecodedPage<T> | "incomplete" {
	if (!isObject(value)) fail("schema_or_mapping_mismatch", "Invalid page response");
	if (value.outcome === "incomplete" && exactKeys(value, ["outcome"])) return "incomplete";
	if (
		value.outcome !== "page" ||
		!exactKeys(value, [
			"outcome",
			"pageId",
			"pageIndex",
			"afterCursor",
			"endCursor",
			"hasNextPage",
			"authorizationVersion",
			"items",
		]) ||
		typeof value.pageId !== "string" ||
		!Number.isSafeInteger(value.pageIndex) ||
		(typeof value.afterCursor !== "string" && value.afterCursor !== null) ||
		(typeof value.endCursor !== "string" && value.endCursor !== null) ||
		typeof value.hasNextPage !== "boolean" ||
		typeof value.authorizationVersion !== "string" ||
		!Array.isArray(value.items)
	) {
		fail("schema_or_mapping_mismatch", "Invalid page response");
	}
	const items: { authorization: "authorized" | "denied"; value?: T }[] = [];
	for (const item of value.items) {
		if (!isObject(item) || typeof item.authorization !== "string") {
			fail("schema_or_mapping_mismatch", "Invalid item response");
		}
		if (item.authorization === "denied" && exactKeys(item, ["authorization"])) {
			items.push({ authorization: "denied" });
			continue;
		}
		if (
			item.authorization !== "authorized" ||
			!exactKeys(item, ["authorization", "value"]) ||
			!isObject(item.value)
		) {
			fail("schema_or_mapping_mismatch", "Invalid item response");
		}
		items.push({ authorization: "authorized", value: item.value as T });
	}
	return {
		pageId: value.pageId,
		pageIndex: value.pageIndex as number,
		afterCursor: value.afterCursor,
		endCursor: value.endCursor,
		hasNextPage: value.hasNextPage,
		authorizationVersion: value.authorizationVersion,
		items,
	};
}

function stableJson(value: unknown): string {
	if (value === null || typeof value === "boolean" || typeof value === "number" || typeof value === "string") {
		return JSON.stringify(value);
	}
	if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
	if (isObject(value)) {
		return `{${Object.keys(value)
			.sort()
			.map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`)
			.join(",")}}`;
	}
	return "invalid";
}

async function collectPages<T>(input: {
	transport: OpenCtiOrientationTransportPort;
	kind: "visible_work_page" | "visible_object_membership_page";
	observationId: string;
	caseRef: string;
	accessPrincipal: AccessPrincipalBinding;
	authorizationVersion: string;
	identity: (item: T) => string;
	reasonCode: "incomplete_task_traversal" | "incomplete_object_traversal";
	signal?: AbortSignal;
}): Promise<OrientationCollection<T>> {
	const pages = new Map<string, string>();
	const items = new Map<string, { encoded: string; value: T }>();
	let afterCursor: string | null = null;
	let pageIndex = 0;
	for (let requestCount = 0; requestCount < 100; requestCount++) {
		const raw = await input.transport.execute(
			{
				kind: input.kind,
				observationId: input.observationId,
				caseRef: input.caseRef,
				accessPrincipal: input.accessPrincipal,
				afterCursor,
			},
			{ signal: input.signal },
		);
		if (input.signal?.aborted) fail("transport_timeout", "Orientation read aborted");
		const page = decodePage<T>(raw);
		if (page === "incomplete") return { kind: "unavailable", reasonCode: input.reasonCode };
		const encodedPage = stableJson(page);
		const priorPage = pages.get(page.pageId);
		if (priorPage !== undefined) {
			if (priorPage !== encodedPage) fail("observation_drift", "Inconsistent duplicate page");
			continue;
		}
		if (page.pageIndex !== pageIndex || page.afterCursor !== afterCursor) {
			fail("cursor_continuity_lost", "Page order or cursor continuity was lost");
		}
		if (page.authorizationVersion !== input.authorizationVersion) {
			fail("authorization_or_visibility_changed", "Authorization changed between pages");
		}
		pages.set(page.pageId, encodedPage);
		for (const item of page.items) {
			if (item.authorization === "denied" || item.value === undefined) {
				fail("authorization_or_visibility_changed", "Item authorization changed");
			}
			const identity = input.identity(item.value);
			const encoded = stableJson(item.value);
			const prior = items.get(identity);
			if (prior && prior.encoded !== encoded) fail("observation_drift", "Inconsistent duplicate item");
			if (!prior) items.set(identity, { encoded, value: item.value });
		}
		if (!page.hasNextPage) return { kind: "complete", items: [...items.values()].map((entry) => entry.value) };
		if (page.endCursor === null || page.endCursor === afterCursor) {
			return { kind: "unavailable", reasonCode: input.reasonCode };
		}
		afterCursor = page.endCursor;
		pageIndex++;
	}
	return { kind: "unavailable", reasonCode: input.reasonCode };
}

export class OpenCtiTransportOrientationAdapter implements OrientationReadPort {
	readonly source: OrientationSourceIdentityV1;
	private readonly observedSource: OrientationSourceIdentityV1;
	private readonly transport: OpenCtiOrientationTransportPort;

	constructor(input: {
		source: OrientationSourceIdentityV1;
		observedSource?: OrientationSourceIdentityV1;
		transport: OpenCtiOrientationTransportPort;
	}) {
		this.source = input.source;
		this.observedSource = input.observedSource ?? input.source;
		this.transport = input.transport;
	}

	async observe(
		input: { caseRef: string; accessPrincipal: AccessPrincipalBinding },
		options?: { signal?: AbortSignal },
	): Promise<OrientationObservationV1> {
		if (stableJson(this.source) !== stableJson(this.observedSource)) {
			fail("schema_or_mapping_mismatch", "Orientation source identity does not match qualification");
		}
		const observationId = randomUUID();
		const root = decodeRoot(
			await this.transport.execute(
				{
					kind: "case_root",
					probe: "start",
					observationId,
					caseRef: input.caseRef,
					accessPrincipal: input.accessPrincipal,
				},
				{ signal: options?.signal },
			),
		);
		const visibleWork = await collectPages<OpenCtiVisibleWorkV1>({
			transport: this.transport,
			kind: "visible_work_page",
			observationId,
			caseRef: input.caseRef,
			accessPrincipal: input.accessPrincipal,
			authorizationVersion: root.authorizationVersion,
			identity: (item) => item.taskRef,
			reasonCode: "incomplete_task_traversal",
			signal: options?.signal,
		});
		const visibleObjectMembership = await collectPages<OpenCtiVisibleObjectMembershipV1>({
			transport: this.transport,
			kind: "visible_object_membership_page",
			observationId,
			caseRef: input.caseRef,
			accessPrincipal: input.accessPrincipal,
			authorizationVersion: root.authorizationVersion,
			identity: (item) => item.objectRef,
			reasonCode: "incomplete_object_traversal",
			signal: options?.signal,
		});
		const endRootRaw = await this.transport.execute(
			{
				kind: "case_root",
				probe: "end",
				observationId,
				caseRef: input.caseRef,
				accessPrincipal: input.accessPrincipal,
			},
			{ signal: options?.signal },
		);
		if (options?.signal?.aborted) fail("transport_timeout", "Orientation read aborted");
		if (isObject(endRootRaw) && endRootRaw.outcome === "not_visible" && exactKeys(endRootRaw, ["outcome"])) {
			fail("authorization_or_visibility_changed", "Case root visibility changed during traversal");
		}
		const endRoot = decodeRoot(endRootRaw);
		if (
			endRoot.authorizationVersion !== root.authorizationVersion ||
			stableJson(endRoot.item) !== stableJson(root.item)
		) {
			fail(
				endRoot.authorizationVersion === root.authorizationVersion
					? "observation_drift"
					: "authorization_or_visibility_changed",
				"Case root changed during traversal",
			);
		}
		return { caseIdentity: root.item, visibleWork, visibleObjectMembership };
	}
}
