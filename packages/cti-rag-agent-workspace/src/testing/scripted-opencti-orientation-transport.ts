import type {
	OpenCtiCaseIdentityV1,
	OpenCtiOrientationTransportPort,
	OpenCtiOrientationTransportRequest,
	OpenCtiVisibleObjectMembershipV1,
	OpenCtiVisibleWorkV1,
} from "../types.ts";

export type ScriptedTransportItem<T> = { authorization: "authorized"; value: T } | { authorization: "denied" };

export interface ScriptedTransportPage<T> {
	outcome: "page";
	pageId: string;
	pageIndex: number;
	afterCursor: string | null;
	endCursor: string | null;
	hasNextPage: boolean;
	authorizationVersion: string;
	items: readonly ScriptedTransportItem<T>[];
}

export type ScriptedTransportPageOutcome<T> = ScriptedTransportPage<T> | { outcome: "incomplete" } | unknown;

export interface ScriptedTransportPass {
	root:
		| { outcome: "visible"; authorizationVersion: string; item: OpenCtiCaseIdentityV1 }
		| { outcome: "not_visible" }
		| unknown;
	endRoot?:
		| { outcome: "visible"; authorizationVersion: string; item: OpenCtiCaseIdentityV1 }
		| { outcome: "not_visible" }
		| unknown;
	workPages: readonly ScriptedTransportPageOutcome<OpenCtiVisibleWorkV1>[];
	objectPages: readonly ScriptedTransportPageOutcome<OpenCtiVisibleObjectMembershipV1>[];
	onStart?: () => void;
	waitUntilReleased?: Promise<void>;
	ignoreAbort?: boolean;
}

export class ScriptedOpenCtiOrientationTransport implements OpenCtiOrientationTransportPort {
	private readonly passes: readonly ScriptedTransportPass[];
	private nextPass = 0;
	private active:
		| { observationId: string; pass: ScriptedTransportPass; workIndex: number; objectIndex: number }
		| undefined;

	constructor(input: { passes: readonly ScriptedTransportPass[] }) {
		this.passes = input.passes;
	}

	async execute(request: OpenCtiOrientationTransportRequest, options?: { signal?: AbortSignal }): Promise<unknown> {
		if (request.kind === "case_root" && request.probe === "start") {
			const pass = this.passes[this.nextPass++];
			if (!pass) throw new Error("No scripted transport pass remains");
			this.active = { observationId: request.observationId, pass, workIndex: 0, objectIndex: 0 };
			pass.onStart?.();
			if (pass.waitUntilReleased) {
				if (pass.ignoreAbort || options?.signal === undefined) {
					await pass.waitUntilReleased;
				} else {
					await Promise.race([
						pass.waitUntilReleased,
						new Promise<never>((_resolve, reject) => {
							if (options.signal?.aborted) {
								reject(Object.assign(new Error("Scripted transport aborted"), { code: "transport_timeout" }));
								return;
							}
							options.signal?.addEventListener(
								"abort",
								() =>
									reject(
										Object.assign(new Error("Scripted transport aborted"), { code: "transport_timeout" }),
									),
								{ once: true },
							);
						}),
					]);
				}
			}
			return this.resolve(pass.root);
		}
		if (!this.active || this.active.observationId !== request.observationId) {
			throw new Error("Scripted transport observation does not match the active pass");
		}
		if (request.kind === "case_root") {
			const response = this.active.pass.endRoot ?? this.active.pass.root;
			this.active = undefined;
			return this.resolve(response);
		}
		if (request.kind === "visible_work_page") {
			const response = this.active.pass.workPages[this.active.workIndex++];
			return this.resolve(response ?? { outcome: "incomplete" });
		}
		const response = this.active.pass.objectPages[this.active.objectIndex++];
		return this.resolve(response ?? { outcome: "incomplete" });
	}

	private resolve(response: unknown): unknown {
		if (
			typeof response === "object" &&
			response !== null &&
			"outcome" in response &&
			response.outcome === "timeout"
		) {
			throw Object.assign(new Error("Scripted transport timeout"), { code: "transport_timeout" as const });
		}
		return response;
	}
}
