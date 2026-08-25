import type {
	AccessPrincipalBinding,
	OpenCtiCaseIdentityV1,
	OpenCtiVisibleObjectMembershipV1,
	OpenCtiVisibleWorkV1,
	OrientationCollection,
	OrientationObservationV1,
	OrientationReadPort,
	OrientationSourceIdentityV1,
} from "../types.ts";

export interface InMemoryPage<T> {
	items: readonly T[];
	hasNextPage: boolean;
	endCursor?: string;
	afterCursor?: string | null;
	pageId?: string;
	pageIndex?: number;
	authorization: "valid" | "revoked";
	itemAuthorizations?: readonly ("authorized" | "denied")[];
}

export interface InMemoryOrientationPass {
	caseIdentity: OpenCtiCaseIdentityV1;
	endCaseIdentity?: OpenCtiCaseIdentityV1;
	endAuthorization?: "valid" | "revoked";
	workPages: readonly InMemoryPage<OpenCtiVisibleWorkV1>[];
	objectPages: readonly InMemoryPage<OpenCtiVisibleObjectMembershipV1>[];
	unsafeCaseIdentityOverrides?: Readonly<Record<string, unknown>>;
	unsafeObservationFields?: Readonly<Record<string, unknown>>;
	failureCode?: "transport_timeout" | "case_root_not_found_or_not_visible";
	onObserve?: () => void;
	waitUntilReleased?: Promise<void>;
	ignoreAbort?: boolean;
}

function stableJson(value: unknown): string {
	if (value === null || typeof value === "boolean" || typeof value === "number" || typeof value === "string") {
		return JSON.stringify(value);
	}
	if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
	if (typeof value === "object") {
		return `{${Object.entries(value)
			.sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
			.map(([key, child]) => `${JSON.stringify(key)}:${stableJson(child)}`)
			.join(",")}}`;
	}
	return "invalid";
}

function collectPages<T>(
	pages: readonly InMemoryPage<T>[],
	reasonCode: "incomplete_task_traversal" | "incomplete_object_traversal",
	identity: (item: T) => string,
): OrientationCollection<T> {
	const items = new Map<string, { encoded: string; value: T }>();
	const seenPages = new Map<string, string>();
	let expectedCursor: string | null = null;
	let expectedPageIndex = 0;
	for (let index = 0; index < pages.length; index++) {
		const page = pages[index]!;
		if (page.authorization === "revoked") {
			throw Object.assign(new Error("Authorization was revoked during Orientation traversal."), {
				code: "authorization_or_visibility_changed" as const,
			});
		}
		const pageId = page.pageId ?? `page-${index}`;
		const encodedPage = stableJson(page);
		const priorPage = seenPages.get(pageId);
		if (priorPage !== undefined) {
			if (priorPage !== encodedPage) {
				throw Object.assign(new Error("Inconsistent duplicate page."), { code: "observation_drift" as const });
			}
			continue;
		}
		const actualPageIndex = page.pageIndex === undefined ? expectedPageIndex : page.pageIndex;
		const actualAfterCursor = page.afterCursor === undefined ? expectedCursor : page.afterCursor;
		if (actualPageIndex !== expectedPageIndex || actualAfterCursor !== expectedCursor) {
			throw Object.assign(new Error("Page order or cursor continuity was lost."), {
				code: "cursor_continuity_lost" as const,
			});
		}
		seenPages.set(pageId, encodedPage);
		if (page.itemAuthorizations && page.itemAuthorizations.length !== page.items.length) {
			throw Object.assign(new Error("Invalid item authorization fixture."), {
				code: "schema_or_mapping_mismatch" as const,
			});
		}
		for (let itemIndex = 0; itemIndex < page.items.length; itemIndex++) {
			if (page.itemAuthorizations?.[itemIndex] === "denied") {
				throw Object.assign(new Error("Item authorization changed."), {
					code: "authorization_or_visibility_changed" as const,
				});
			}
			const item = page.items[itemIndex]!;
			const itemIdentity = identity(item);
			const encoded = stableJson(item);
			const prior = items.get(itemIdentity);
			if (prior && prior.encoded !== encoded) {
				throw Object.assign(new Error("Inconsistent duplicate item."), { code: "observation_drift" as const });
			}
			if (!prior) items.set(itemIdentity, { encoded, value: item });
		}
		if (!page.hasNextPage) {
			return { kind: "complete", items: [...items.values()].map((entry) => entry.value) };
		}
		if (!page.endCursor || index === pages.length - 1) {
			return { kind: "unavailable", reasonCode };
		}
		expectedCursor = page.endCursor;
		expectedPageIndex++;
	}
	return { kind: "unavailable", reasonCode };
}

export class InMemoryOrientationAdapter implements OrientationReadPort {
	readonly source: OrientationSourceIdentityV1;
	private readonly observedSource: OrientationSourceIdentityV1;
	private readonly passes: readonly InMemoryOrientationPass[];
	private nextPass = 0;

	constructor(input: {
		source: OrientationSourceIdentityV1;
		observedSource?: OrientationSourceIdentityV1;
		passes: readonly InMemoryOrientationPass[];
	}) {
		this.source = input.source;
		this.observedSource = input.observedSource ?? input.source;
		this.passes = input.passes;
	}

	async observe(
		_input: { caseRef: string; accessPrincipal: AccessPrincipalBinding },
		_options?: { signal?: AbortSignal },
	): Promise<OrientationObservationV1> {
		const pass = this.passes[this.nextPass++];
		if (!pass) throw new Error("No in-memory Orientation pass remains");
		pass.onObserve?.();
		if (pass.waitUntilReleased) await pass.waitUntilReleased;
		if (_options?.signal?.aborted && !pass.ignoreAbort) {
			throw Object.assign(new Error("Orientation read aborted."), { code: "transport_timeout" as const });
		}
		if (stableJson(this.source) !== stableJson(this.observedSource)) {
			throw Object.assign(new Error("Orientation source identity does not match qualification."), {
				code: "schema_or_mapping_mismatch" as const,
			});
		}
		if (pass.failureCode) throw Object.assign(new Error("Orientation read failed."), { code: pass.failureCode });
		if (pass.endAuthorization === "revoked") {
			throw Object.assign(new Error("Case root visibility changed during traversal."), {
				code: "authorization_or_visibility_changed" as const,
			});
		}
		if (pass.endCaseIdentity && stableJson(pass.endCaseIdentity) !== stableJson(pass.caseIdentity)) {
			throw Object.assign(new Error("Case root changed during traversal."), {
				code: "observation_drift" as const,
			});
		}
		return {
			caseIdentity: { ...pass.caseIdentity, ...pass.unsafeCaseIdentityOverrides },
			visibleWork: collectPages(pass.workPages, "incomplete_task_traversal", (item) => item.taskRef),
			visibleObjectMembership: collectPages(
				pass.objectPages,
				"incomplete_object_traversal",
				(item) => item.objectRef,
			),
			...pass.unsafeObservationFields,
		} as OrientationObservationV1;
	}
}
