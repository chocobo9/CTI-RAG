import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import initSqlJs, { type SqlDatabase } from "sql.js";
import type {
	AgentMemoryModule,
	MemoryCandidate,
	MemoryEntry,
	MemoryError,
	MemoryManagementCommand,
	MemoryManagementOutcome,
	MemoryMutation,
	MemoryPreparationOutcome,
	MemoryPreparationRequest,
	MemoryReceipt,
	MemoryRevalidationOutcome,
	MemoryRevalidationRequest,
	MemoryScope,
	MemorySettlementOutcome,
	MemoryState,
	QualifiedMemoryView,
	SettledRunMemoryRequest,
} from "./types.ts";

const require = createRequire(import.meta.url);
// memory_events is the append-only revision/history authority. memory_entries is
// only its current materialized projection; indexes never establish authority.
const schema = `
CREATE TABLE IF NOT EXISTS memory_operations (
  operation_key TEXT PRIMARY KEY, request_digest TEXT NOT NULL, receipt_json TEXT NOT NULL, entries_json TEXT NOT NULL,
  outcome_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_entries (
  entry_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, state TEXT NOT NULL,
  category TEXT NOT NULL, subject TEXT NOT NULL, value_json TEXT, scope_json TEXT NOT NULL,
  provenance_json TEXT NOT NULL, temporal_json TEXT NOT NULL, relations_json TEXT NOT NULL,
  use_purpose TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
  operation_key TEXT NOT NULL, entry_id TEXT NOT NULL, revision INTEGER NOT NULL,
  mutation TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_tombstones (
  entry_id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL, reason TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS memory_scope_subject ON memory_entries(subject, state, use_purpose);
`;

interface StoredOperation {
	requestDigest: string;
	receipt: MemoryReceipt;
	entries: readonly MemoryEntry[];
	outcome: MemoryManagementOutcome;
}

function canonical(value: unknown): string {
	if (value === null || typeof value !== "object") return JSON.stringify(value);
	if (Array.isArray(value)) return `[${value.map((item) => canonical(item)).join(",")}]`;
	const record = value as Record<string, unknown>;
	return `{${Object.keys(record)
		.filter((key) => record[key] !== undefined)
		.sort()
		.map((key) => `${JSON.stringify(key)}:${canonical(record[key])}`)
		.join(",")}}`;
}
function requestDigest(value: unknown): string {
	return createHash("sha256").update(canonical(value)).digest("hex");
}
function idempotencyConflict() {
	return failure("IDEMPOTENCY_CONFLICT", "idempotency key is already bound to a different request");
}

function failure(code: MemoryError["code"], message: string, retryable = false) {
	return { ok: false as const, error: { code, message, retryable } };
}
function json(value: unknown): string {
	return JSON.stringify(value);
}
function parse<T>(value: unknown): T {
	return JSON.parse(String(value)) as T;
}
function now(): string {
	return new Date().toISOString();
}
function scopeMatches(actual: MemoryScope, requested: MemoryScope): boolean {
	return (
		actual.tenantRef === requested.tenantRef &&
		actual.visibility === requested.visibility &&
		actual.principalRef === requested.principalRef &&
		actual.teamRef === requested.teamRef &&
		actual.caseRef === requested.caseRef &&
		actual.workspaceRef === requested.workspaceRef &&
		actual.sessionRef === requested.sessionRef &&
		actual.taskRef === requested.taskRef
	);
}
function eligible(
	entry: MemoryEntry,
	request: MemoryPreparationRequest | MemoryRevalidationRequest,
	timestamp: string,
): boolean {
	return (
		entry.state === "active" &&
		entry.usePurpose === request.usePurpose &&
		entry.scope.principalRef === request.principalRef &&
		scopeMatches(entry.scope, request.scope) &&
		(!request.sourceVersion || entry.provenance.sourceVersion === request.sourceVersion) &&
		(!entry.temporal.expiresAt || entry.temporal.expiresAt > timestamp)
	);
}
function eventKey(operationKey: string, entryId: string, revision: number): string {
	return `${operationKey}:${entryId}:${revision}`;
}
function mutationFor(candidate: MemoryCandidate): MemoryMutation {
	return candidate.relations.some((relation) => relation.kind === "contradicts") ? "contradict" : "add";
}

export interface SqliteAgentMemoryOptions {
	path?: string;
}

export class SqliteAgentMemoryModule implements AgentMemoryModule {
	private readonly db: SqlDatabase;
	private readonly path?: string;

	private constructor(db: SqlDatabase, path?: string) {
		this.db = db;
		this.path = path;
	}

	static async open(options: SqliteAgentMemoryOptions = {}): Promise<SqliteAgentMemoryModule> {
		const SQL = await initSqlJs({ locateFile: (file) => resolve(require.resolve("sql.js"), "..", file) });
		let data: Uint8Array | undefined;
		if (options.path) {
			try {
				data = new Uint8Array(await readFile(options.path));
			} catch (error) {
				if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
			}
		}
		const db = new SQL.Database(data);
		db.exec(schema);
		try {
			db.exec("ALTER TABLE memory_operations ADD COLUMN request_digest TEXT");
		} catch {
			// The column already exists; schema initialization is intentionally repeatable.
		}
		return new SqliteAgentMemoryModule(db, options.path);
	}

	private async persist(): Promise<void> {
		if (!this.path) return;
		await mkdir(dirname(this.path), { recursive: true });
		await writeFile(this.path, this.db.export());
	}

	private operation(operationKey: string): StoredOperation | undefined {
		const statement = this.db.prepare(
			"SELECT request_digest, receipt_json, entries_json, outcome_json FROM memory_operations WHERE operation_key = ?",
		);
		statement.bind([operationKey]);
		const found = statement.step();
		const row = found ? statement.getAsObject() : undefined;
		statement.free();
		if (!row) return undefined;
		return {
			requestDigest: String(row.request_digest ?? ""),
			receipt: parse<MemoryReceipt>(row.receipt_json),
			entries: parse<readonly MemoryEntry[]>(row.entries_json),
			outcome: parse<MemoryManagementOutcome>(row.outcome_json),
		};
	}

	private row(entryId: string): MemoryEntry | undefined {
		const statement = this.db.prepare("SELECT * FROM memory_entries WHERE entry_id = ?");
		statement.bind([entryId]);
		const found = statement.step();
		const row = found ? statement.getAsObject() : undefined;
		statement.free();
		if (!row || row.value_json === null || row.value_json === undefined) return undefined;
		return {
			entryId: String(row.entry_id),
			revision: Number(row.revision),
			state: row.state as MemoryState,
			category: row.category as MemoryEntry["category"],
			subject: String(row.subject),
			value: parse<MemoryEntry["value"]>(row.value_json),
			scope: parse<MemoryScope>(row.scope_json),
			provenance: parse<MemoryEntry["provenance"]>(row.provenance_json),
			temporal: parse<MemoryEntry["temporal"]>(row.temporal_json),
			relations: parse<MemoryEntry["relations"]>(row.relations_json),
			usePurpose: String(row.use_purpose),
			createdAt: String(row.created_at),
			updatedAt: String(row.updated_at),
		};
	}

	private insertProjection(entry: MemoryEntry): void {
		const statement = this.db.prepare("INSERT INTO memory_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)");
		statement.bind([
			entry.entryId,
			entry.revision,
			entry.state,
			entry.category,
			entry.subject,
			json(entry.value),
			json(entry.scope),
			json(entry.provenance),
			json(entry.temporal),
			json(entry.relations),
			entry.usePurpose,
			entry.createdAt,
			entry.updatedAt,
		]);
		statement.step();
		statement.free();
	}

	private updateProjection(entry: MemoryEntry): void {
		const statement = this.db.prepare(
			"UPDATE memory_entries SET revision = ?, state = ?, category = ?, subject = ?, value_json = ?, scope_json = ?, provenance_json = ?, temporal_json = ?, relations_json = ?, use_purpose = ?, updated_at = ? WHERE entry_id = ?",
		);
		statement.bind([
			entry.revision,
			entry.state,
			entry.category,
			entry.subject,
			json(entry.value),
			json(entry.scope),
			json(entry.provenance),
			json(entry.temporal),
			json(entry.relations),
			entry.usePurpose,
			entry.updatedAt,
			entry.entryId,
		]);
		statement.step();
		statement.free();
	}

	private insertEvent(operationKey: string, entry: MemoryEntry, mutation: MemoryMutation): void {
		const statement = this.db.prepare(
			"INSERT INTO memory_events(event_key, operation_key, entry_id, revision, mutation, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
		);
		statement.bind([
			eventKey(operationKey, entry.entryId, entry.revision),
			operationKey,
			entry.entryId,
			entry.revision,
			mutation,
			json(entry),
			now(),
		]);
		statement.step();
		statement.free();
	}

	private insertOperation(
		operationKey: string,
		digest: string,
		receipt: MemoryReceipt,
		entries: readonly MemoryEntry[],
		outcome: MemoryManagementOutcome,
	): void {
		const statement = this.db.prepare(
			"INSERT INTO memory_operations(operation_key, request_digest, receipt_json, entries_json, outcome_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
		);
		statement.bind([operationKey, digest, json(receipt), json(entries), json(outcome), now()]);
		statement.step();
		statement.free();
	}

	private candidateError(candidate: MemoryCandidate): MemoryError | undefined {
		if (
			!candidate.candidateId ||
			!candidate.subject ||
			!candidate.usePurpose ||
			!candidate.provenance.sourceRef ||
			!candidate.provenance.sourceVersion ||
			!candidate.provenance.sourceDigest
		)
			return {
				code: "INVALID_CANDIDATE",
				message: "candidate schema or provenance is incomplete",
				retryable: false,
			};
		if (candidate.value.form === "owned_content" && candidate.value.content.length === 0)
			return { code: "INVALID_CANDIDATE", message: "owned content must not be empty", retryable: false };
		if (candidate.value.form === "owner_reference" && !candidate.value.ownerVersion)
			return { code: "INVALID_CANDIDATE", message: "owner reference must be versioned", retryable: false };
		return undefined;
	}

	private expectedRevisionError(
		request: SettledRunMemoryRequest,
		candidates: readonly MemoryCandidate[],
	): MemoryError | undefined {
		if (request.expectedRevision === undefined) return undefined;
		for (const candidate of candidates) {
			const current = this.row(candidate.candidateId);
			if (!current || current.revision !== request.expectedRevision)
				return {
					code: "EXPECTED_REVISION_CONFLICT",
					message: `expected revision ${request.expectedRevision} does not match current entry ${candidate.candidateId}`,
					retryable: true,
				};
		}
		return undefined;
	}

	async settle(request: SettledRunMemoryRequest): Promise<MemorySettlementOutcome> {
		return this.settleWithDigest(
			request,
			requestDigest({
				operation: "settle",
				run: request.run,
				candidates: request.candidates,
				expectedRevision: request.expectedRevision,
			}),
		);
	}

	private async settleWithDigest(request: SettledRunMemoryRequest, digest: string): Promise<MemorySettlementOutcome> {
		const replay = this.operation(request.idempotencyKey);
		if (replay)
			return replay.requestDigest === digest
				? { ok: true, receipt: replay.receipt, entries: replay.entries }
				: idempotencyConflict();
		if (request.run.disposition !== "settled" || !request.run.savePointId || !request.run.outcomeDigest)
			return failure("INVALID_RUN", "only a settled Run with save point and outcome digest may write memory");
		for (const candidate of request.candidates) {
			const error = this.candidateError(candidate);
			if (error) return { ok: false, error };
		}
		const expectedError = this.expectedRevisionError(request, request.candidates);
		if (expectedError) return { ok: false, error: expectedError };
		for (const candidate of request.candidates) {
			const current = this.row(candidate.candidateId);
			if (current && current.provenance.sourceDigest !== candidate.provenance.sourceDigest)
				return failure(
					"EXPECTED_REVISION_CONFLICT",
					`candidate identity ${candidate.candidateId} already has a different source`,
				);
		}
		const entries: MemoryEntry[] = [];
		const mutations: MemoryMutation[] = [];
		this.db.exec("BEGIN");
		try {
			for (const candidate of request.candidates) {
				const current = this.row(candidate.candidateId);
				if (current) continue;
				const entry: MemoryEntry = {
					entryId: candidate.candidateId,
					revision: 1,
					state: "active",
					category: candidate.category,
					subject: candidate.subject,
					value: candidate.value,
					scope: candidate.scope,
					provenance: candidate.provenance,
					temporal: candidate.temporal,
					relations: candidate.relations,
					usePurpose: candidate.usePurpose,
					createdAt: now(),
					updatedAt: now(),
				};
				this.insertProjection(entry);
				const mutation = mutationFor(candidate);
				this.insertEvent(request.idempotencyKey, entry, mutation);
				entries.push(entry);
				mutations.push(mutation);
			}
			const receipt: MemoryReceipt = {
				receiptId: `${request.idempotencyKey}:1`,
				entryIds: request.candidates.map((candidate) => candidate.candidateId),
				revisions: request.candidates.map((candidate) => this.row(candidate.candidateId)?.revision ?? 1),
				mutation: mutations.length === 1 ? mutations[0] : mutations.length === 0 ? "no_op" : "add",
				createdAt: now(),
			};
			const outcome: MemorySettlementOutcome = {
				ok: true,
				receipt,
				entries: request.candidates
					.map((candidate) => this.row(candidate.candidateId))
					.filter((entry): entry is MemoryEntry => entry !== undefined),
			};
			this.insertOperation(request.idempotencyKey, digest, receipt, outcome.entries, outcome);
			this.db.exec("COMMIT");
			await this.persist();
			return outcome;
		} catch (error) {
			this.db.exec("ROLLBACK");
			throw error;
		}
	}

	async prepare(request: MemoryPreparationRequest): Promise<MemoryPreparationOutcome> {
		const timestamp = request.now ?? now();
		const statement = this.db.prepare("SELECT entry_id FROM memory_entries WHERE subject = ?");
		statement.bind([request.subject]);
		const entries: MemoryEntry[] = [];
		const omitted: Array<QualifiedMemoryView["omitted"][number]> = [];
		while (statement.step()) {
			const entryId = String(statement.getAsObject().entry_id);
			const entry = this.row(entryId);
			if (!entry) {
				omitted.push({ entryId, reason: "deleted" });
				continue;
			}
			if (eligible(entry, request, timestamp)) {
				entries.push(entry);
				continue;
			}
			const reason =
				entry.state === "deletion_pending"
					? "state_ineligible"
					: entry.state !== "active"
						? "state_ineligible"
						: entry.scope.principalRef !== request.principalRef
							? "authorization_denied"
							: !scopeMatches(entry.scope, request.scope)
								? "out_of_scope"
								: entry.usePurpose !== request.usePurpose
									? "purpose_denied"
									: request.sourceVersion && entry.provenance.sourceVersion !== request.sourceVersion
										? "source_drift"
										: entry.temporal.expiresAt
											? "expired"
											: "state_ineligible";
			omitted.push({ entryId, reason });
		}
		statement.free();
		if (request.required && entries.length === 0)
			return failure("UNAVAILABLE", "required memory is unavailable after scope and purpose qualification");
		const receipt: MemoryReceipt = {
			receiptId: `prepare:${now()}`,
			entryIds: entries.map((entry) => entry.entryId),
			revisions: entries.map((entry) => entry.revision),
			mutation: "no_op",
			createdAt: now(),
		};
		return { ok: true, view: { entries, omitted, receipt } };
	}

	async revalidate(request: MemoryRevalidationRequest): Promise<MemoryRevalidationOutcome> {
		const entry = this.row(request.entryId);
		if (!entry)
			return {
				status: "unavailable",
				error: failure("NOT_ELIGIBLE", "memory is absent, deleted, or content-free").error,
			};
		if (
			entry.revision !== request.revision ||
			entry.provenance.sourceVersion !== request.sourceVersion ||
			!eligible(entry, request, request.now ?? now())
		)
			return {
				status: "invalidated",
				error: failure("NOT_ELIGIBLE", "memory revision, source version, or eligibility changed").error,
			};
		return { status: "valid_unchanged", entry };
	}

	async manage(command: MemoryManagementCommand): Promise<MemoryManagementOutcome> {
		const digest = command.kind === "inspect" ? undefined : requestDigest({ operation: "manage", command });
		const stored = command.kind === "inspect" ? undefined : this.operation(command.idempotencyKey);
		if (stored && stored.requestDigest !== digest) return idempotencyConflict();
		const replay = stored?.outcome;
		if (replay) return replay;
		if (command.kind === "inspect") {
			const entry = this.row(command.entryId);
			return entry ? { ok: true, entry } : failure("NOT_FOUND", "memory entry not found");
		}
		if (command.kind === "remember") {
			const settled = await this.settleWithDigest(
				{
					run: {
						runId: `command:${command.idempotencyKey}`,
						disposition: "settled",
						savePointId: command.idempotencyKey,
						outcomeDigest: command.idempotencyKey,
						settledAt: now(),
						sourceVersion: "explicit-command",
					},
					candidates: [command.candidate],
					idempotencyKey: command.idempotencyKey,
				},
				digest ?? "",
			);
			return settled;
		}
		const current = this.row(command.entryId);
		if (!current) return failure("NOT_FOUND", "memory entry not found");
		if (current.revision !== command.expectedRevision)
			return failure("EXPECTED_REVISION_CONFLICT", "expected revision does not match current revision");
		if (command.kind === "supersede" || command.kind === "invalidate")
			return failure("NOT_IMPLEMENTED", `${command.kind} is reserved for a later Memory slice`);
		if (command.kind === "correct") {
			const error = this.candidateError(command.candidate);
			if (error) return { ok: false, error };
			const corrected: MemoryEntry = {
				...current,
				revision: current.revision + 1,
				state: "active",
				subject: command.candidate.subject,
				category: command.candidate.category,
				value: command.candidate.value,
				provenance: command.candidate.provenance,
				temporal: command.candidate.temporal,
				relations: [
					...current.relations,
					{ kind: "updates", targetEntryId: current.entryId },
					...command.candidate.relations,
				],
				updatedAt: now(),
				usePurpose: command.candidate.usePurpose,
			};
			return this.commitManagement(command.idempotencyKey, digest ?? "", corrected, "update");
		}
		return this.forget(command.idempotencyKey, digest ?? "", current);
	}

	private async commitManagement(
		operationKey: string,
		digest: string,
		entry: MemoryEntry,
		mutation: MemoryMutation,
	): Promise<MemoryManagementOutcome> {
		this.db.exec("BEGIN");
		try {
			this.updateProjection(entry);
			this.insertEvent(operationKey, entry, mutation);
			const receipt: MemoryReceipt = {
				receiptId: `${operationKey}:${entry.revision}`,
				entryIds: [entry.entryId],
				revisions: [entry.revision],
				mutation,
				createdAt: now(),
			};
			const outcome: MemoryManagementOutcome = { ok: true, receipt, entry };
			this.insertOperation(operationKey, digest, receipt, [entry], outcome);
			this.db.exec("COMMIT");
			await this.persist();
			return outcome;
		} catch (error) {
			this.db.exec("ROLLBACK");
			throw error;
		}
	}

	private async forget(operationKey: string, digest: string, current: MemoryEntry): Promise<MemoryManagementOutcome> {
		this.db.exec("BEGIN");
		try {
			const pending = { ...current, state: "deletion_pending" as const, updatedAt: now() };
			this.updateProjection(pending);
			this.db.exec("COMMIT");
			await this.persist();
		} catch (error) {
			this.db.exec("ROLLBACK");
			throw error;
		}
		this.db.exec("BEGIN");
		try {
			const deleteStatement = this.db.prepare("DELETE FROM memory_entries WHERE entry_id = ? AND state = ?");
			deleteStatement.bind([current.entryId, "deletion_pending"]);
			deleteStatement.step();
			deleteStatement.free();
			const tombstone = this.db.prepare("INSERT OR REPLACE INTO memory_tombstones VALUES (?, ?, ?)");
			tombstone.bind([current.entryId, now(), "explicit forget"]);
			tombstone.step();
			tombstone.free();
			const deleted = {
				...current,
				revision: current.revision + 1,
				state: "deleted" as const,
				value: { form: "owned_content" as const, content: "" },
			};
			const receipt: MemoryReceipt = {
				receiptId: `${operationKey}:${current.revision + 1}`,
				entryIds: [current.entryId],
				revisions: [current.revision + 1],
				mutation: "delete",
				createdAt: now(),
			};
			this.insertEvent(operationKey, deleted, "delete");
			const outcome: MemoryManagementOutcome = { ok: true, receipt };
			this.insertOperation(operationKey, digest, receipt, [], outcome);
			this.db.exec("COMMIT");
			await this.persist();
			return outcome;
		} catch (error) {
			this.db.exec("ROLLBACK");
			throw error;
		}
	}
}

export async function openSqliteAgentMemory(options: SqliteAgentMemoryOptions = {}): Promise<SqliteAgentMemoryModule> {
	return SqliteAgentMemoryModule.open(options);
}
