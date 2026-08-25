import { Buffer } from "node:buffer";
import { randomBytes, randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { runOpenCtiCaseSmoke } from "./opencti-case-smoke.ts";

interface OpenCtiCaseSmokeCliInput {
	env: Readonly<Record<string, string | undefined>>;
	write(line: string): void;
	fetchImpl?: typeof fetch;
	signal?: AbortSignal;
}

function parseInteger(value: string | undefined, fallback: number, minimum: number, maximum: number): number {
	if (value === undefined) return fallback;
	const parsed = Number(value);
	if (!Number.isSafeInteger(parsed) || parsed < minimum || parsed > maximum) {
		throw Object.assign(new Error("Invalid smoke budget"), { code: "invalid_configuration" });
	}
	return parsed;
}

function safeError(error: unknown, fallbackSessionPath?: string) {
	const code =
		typeof error === "object" && error !== null && "code" in error && typeof error.code === "string"
			? error.code
			: "smoke_failed";
	const safeCodes = new Set([
		"authorization_or_visibility_changed",
		"case_root_not_found_or_not_visible",
		"cursor_continuity_lost",
		"model_failed",
		"observation_drift",
		"recovery_provenance_untrusted",
		"schema_or_mapping_mismatch",
		"transport_timeout",
		"invalid_configuration",
	]);
	const safeCode = safeCodes.has(code) ? code : "smoke_failed";
	const messages: Readonly<Record<string, string>> = {
		authorization_or_visibility_changed: "OpenCTI authorization could not be proved stable.",
		case_root_not_found_or_not_visible: "The selected Case was not found or is not visible.",
		cursor_continuity_lost: "OpenCTI pagination continuity could not be proved.",
		observation_drift: "The selected Case changed during the bounded smoke observation.",
		recovery_provenance_untrusted: "The JSONL Session recovery provenance is not trusted.",
		schema_or_mapping_mismatch: "The target does not match the live Orientation recipe.",
		transport_timeout: "The OpenCTI smoke timed out.",
		invalid_configuration: "The smoke configuration is invalid.",
		model_failed: "The diagnostic model context could not be proved valid.",
		smoke_failed: "The OpenCTI smoke failed safely.",
	};
	const errorSessionPath =
		typeof error === "object" && error !== null && "sessionPath" in error && typeof error.sessionPath === "string"
			? error.sessionPath
			: undefined;
	const sessionPath =
		errorSessionPath ??
		(fallbackSessionPath && existsSync(resolve(fallbackSessionPath)) ? resolve(fallbackSessionPath) : undefined);
	return {
		status: "failed" as const,
		code: safeCode,
		message: messages[safeCode]!,
		...(sessionPath === undefined ? {} : { sessionPath }),
	};
}

export async function runOpenCtiCaseSmokeCli(input: OpenCtiCaseSmokeCliInput): Promise<number> {
	const endpoint = input.env.OPENCTI_GRAPHQL_URL;
	const token = input.env.OPENCTI_TOKEN;
	const caseRef = input.env.OPENCTI_CASE_ID;
	if (!endpoint || !token || !caseRef) {
		input.write(
			JSON.stringify({
				status: "failed",
				code: "invalid_configuration",
				message: "OPENCTI_GRAPHQL_URL, OPENCTI_TOKEN, and OPENCTI_CASE_ID are required.",
			}),
		);
		return 2;
	}
	let sessionPath: string | undefined;
	try {
		const configuredPath = input.env.CTI_RAG_SESSION_PATH;
		sessionPath = configuredPath ?? join(tmpdir(), `cti-opencti-live-smoke-${randomUUID()}.jsonl`);
		const configuredKey = input.env.CTI_RAG_SESSION_RECEIPT_KEY;
		if (configuredPath && existsSync(resolve(configuredPath)) && !configuredKey) {
			throw Object.assign(new Error("Receipt key is required for an existing Session"), {
				code: "invalid_configuration",
			});
		}
		let receiptKey: Uint8Array;
		try {
			receiptKey = configuredKey ? new Uint8Array(Buffer.from(configuredKey, "base64url")) : randomBytes(32);
		} catch {
			throw Object.assign(new Error("Invalid receipt key"), { code: "invalid_configuration" });
		}
		if (receiptKey.byteLength < 32) {
			throw Object.assign(new Error("Invalid receipt key"), { code: "invalid_configuration" });
		}
		const result = await runOpenCtiCaseSmoke({
			endpoint,
			token,
			caseRef,
			credentialSlot: input.env.CTI_RAG_CREDENTIAL_SLOT ?? "OPENCTI_TOKEN",
			sessionPath,
			receiptKey,
			fetchImpl: input.fetchImpl,
			signal: input.signal,
			budgets: {
				requestTimeoutMs: parseInteger(input.env.CTI_RAG_REQUEST_TIMEOUT_MS, 15_000, 1, 120_000),
				pageSize: parseInteger(input.env.CTI_RAG_PAGE_SIZE, 100, 1, 500),
				maxPages: parseInteger(input.env.CTI_RAG_MAX_PAGES, 100, 1, 100),
				maxResponseBytes: parseInteger(input.env.CTI_RAG_MAX_RESPONSE_BYTES, 5_000_000, 1_024, 50_000_000),
			},
		});
		input.write(JSON.stringify(result));
		return 0;
	} catch (error) {
		input.write(JSON.stringify(safeError(error, sessionPath)));
		return 2;
	}
}

async function main(): Promise<void> {
	const controller = new AbortController();
	const onSignal = () => controller.abort();
	process.once("SIGINT", onSignal);
	process.once("SIGTERM", onSignal);
	try {
		process.exitCode = await runOpenCtiCaseSmokeCli({
			env: process.env,
			write: (line) => process.stdout.write(`${line}\n`),
			signal: controller.signal,
		});
	} finally {
		process.removeListener("SIGINT", onSignal);
		process.removeListener("SIGTERM", onSignal);
	}
}

const executedPath = process.argv[1];
if (executedPath && pathToFileURL(resolve(executedPath)).href === import.meta.url) {
	void main();
}
