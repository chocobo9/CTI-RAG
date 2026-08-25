import { randomBytes } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, it } from "vitest";
import { runOpenCtiCaseSmoke } from "../src/node.ts";

const enabled = process.env.CTI_RAG_RUN_LIVE_OPENCTI === "1";

it.skipIf(!enabled)("reads one real OpenCTI Case through open, prompt, close, and clean reopen", async () => {
	const endpoint = process.env.OPENCTI_GRAPHQL_URL;
	const token = process.env.OPENCTI_TOKEN;
	const caseRef = process.env.OPENCTI_CASE_ID;
	if (!endpoint || !token || !caseRef) {
		throw new Error("OPENCTI_GRAPHQL_URL, OPENCTI_TOKEN, and OPENCTI_CASE_ID are required");
	}
	const directory = await mkdtemp(join(tmpdir(), "cti-opencti-live-smoke-"));
	try {
		const result = await runOpenCtiCaseSmoke({
			endpoint,
			token,
			caseRef,
			sessionPath: join(directory, "session.jsonl"),
			receiptKey: randomBytes(32),
			budgets: {
				requestTimeoutMs: 15_000,
				pageSize: 100,
				maxPages: 100,
				maxResponseBytes: 5_000_000,
			},
		});
		expect(result.status).toBe("passed");
		expect(result.caseRef).toBe(caseRef);
		expect(result.initial.terminalEvent).toBe("turn_completed");
		expect(result.reopen.terminalEvent).toBe("turn_completed");
		expect(result.initial.eventTypes.filter((type) => type === "turn_completed")).toHaveLength(1);
		expect(result.reopen.eventTypes.filter((type) => type === "turn_completed")).toHaveLength(1);
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});
