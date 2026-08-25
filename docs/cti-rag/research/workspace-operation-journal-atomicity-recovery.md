# Workspace Operation Journal Atomicity and Recovery

Status: research note for the first CTI-RAG Agent Investigation Workspace vertical slice. This note recommends a private durable persistence seam; it does not select a public package interface or an LLM tool decomposition.

Design disposition (2026-07-20): canonical Case-head dependency examples are authority-scoped as `case-head/v1(authorityId, caseId)`. Any shorter `case-head/v1(caseId)` notation below is superseded shorthand; the normative [Durable Operation Journal Contract](../agent-workspace/durable-operation-journal-contract.md) governs implementable keys and transitions.

Verified: 2026-07-20 against the primary sources linked below.

## Conclusion

Use one **private deep `DurableOperationJournal` Module** with a PostgreSQL Adapter in production and a fault-injectable in-memory Adapter in acceptance tests. Its authoritative representation should be normalized relational facts and immutable observations, not a generic CRUD repository and not a full event-sourced application.

The minimum correctness boundary is:

1. archive and activate the exact catalog, activation, schema, and decoder identities before an operation can bind them;
2. commit one immutable Operation Intent, its input versions, Output Claim declarations, derivation origins, and any Effect Intent plus all Effect Reservations before execution or remote dispatch;
3. install local outputs, their current-target compare-and-swap, the local receipt, and derivation edges in one database transaction;
4. merge remote receipt observations through an explicit monotonic transition relation, never through arrival order or a numeric `max(state)`;
5. keep accepted effects reserved until a receipt-linked Projection proves synchronization; release only on authoritative no-effect proof or governed resolution;
6. treat a lost local database acknowledgement as unknown until lookup by the same stable identity and digest proves committed or absent;
7. rebuild the Dependency Index from authoritative intents, claims, edges, reservations, and receipts into a new generation, then activate that generation atomically; and
8. retain identity/digest tombstones and every archive artifact reachable from unresolved operations, retained outputs, receipts, or audit policy.

The database transaction is the atomicity boundary for local facts only. It must never include a model request, OpenCTI request, Case Management request, message publication, or arbitrary caller callback. A transactional-outbox-style dispatcher claims already-durable work after commit. This deliberately accepts an ambiguous “dispatch may have started” window and resolves it with the remote operation's original identity and qualified receipt/status contract.

For production R1 dispatch, PostgreSQL asynchronous commit and an HA topology capable of losing an acknowledged journal commit are disqualifying. The deployment must preserve an acknowledged Effect Intent across the failover modes it claims to survive; otherwise a remote effect could outlive its only local recovery identity.

## Evidence boundary

Sections labeled **Source facts** summarize PostgreSQL official documentation, standards, or first-party architecture guidance. Sections labeled **CTI-RAG inference** are recommendations for this project. PostgreSQL does not define CTI-RAG's Operation Intent, Effect Reservation, Output Claim, dependency semantics, receipt hierarchy, or retention policy.

## Primary-source findings

### 1. One local transaction can make several journal facts all-or-nothing

**Source facts**

- PostgreSQL transactions bundle several steps into one all-or-nothing operation. Intermediate states are not visible to concurrent transactions, and an incomplete transaction has no database effect. [PostgreSQL, Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- A normal synchronous commit waits for WAL to be flushed to durable storage before reporting success. With asynchronous commit, success can be reported before WAL reaches disk, and recent allegedly committed transactions can be lost after a crash. PostgreSQL explicitly warns against asynchronous commit when an external action relies on the database remembering the transaction. [PostgreSQL, Asynchronous Commit](https://www.postgresql.org/docs/current/wal-async-commit.html)
- PostgreSQL can return `PQTRANS_UNKNOWN` when a connection is bad. Its protocol documentation also notes that a non-read query can finish and commit before the backend notices a disconnect. Therefore connection loss is not a no-commit proof. [PostgreSQL, Connection Status Functions](https://www.postgresql.org/docs/current/libpq-status.html), [PostgreSQL, Message Flow](https://www.postgresql.org/docs/current/protocol-flow.html#PROTOCOL-FLOW-TERMINATION)

**CTI-RAG inference**

The local atomic boundary should include every fact whose partial visibility would make recovery unsound. For admission, that is the immutable operation binding plus all declared dependency/effect scope. For local output publication, it is the output, receipt, target-head CAS, and derivation edges. For remote outcome observation, it is the receipt transition, synchronization requirement, reservation transition, and dependent dirty/challenge facts.

An Adapter may report three commit classes, not a boolean:

- `committed`: success was acknowledged and the returned decision belongs to the committed transaction;
- `not_committed`: a known rollback, constraint/CAS rejection, or pre-transaction failure proves no journal change;
- `acknowledgement_unknown`: the connection or process failed where commit outcome cannot be proved locally.

After `acknowledgement_unknown`, the Module reopens the authoritative database and looks up the same identity and digest. It does not allocate another Operation ID, output version, effect identity, or request key.

### 2. Uniqueness and compare-and-swap must be database invariants

**Source facts**

- PostgreSQL unique constraints enforce uniqueness over one or more columns and create a unique B-tree index. Primary keys additionally require non-null values. PostgreSQL treats nulls as distinct by default, so nullable identity columns can accidentally admit duplicates unless the schema uses `NOT NULL` or `NULLS NOT DISTINCT`. Foreign keys maintain referential integrity. [PostgreSQL, Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
- `INSERT ... ON CONFLICT DO UPDATE` guarantees an atomic insert-or-update outcome under concurrency. It is a deterministic statement and can use a unique constraint or unique index as its arbiter. [PostgreSQL, INSERT](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)
- Row-level `FOR UPDATE` locks prevent concurrent writers and lockers from changing the selected row until the transaction ends. [PostgreSQL, Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS)
- Serializable transactions commit only when PostgreSQL can establish an equivalent serial execution, but they can abort with `40001`; applications must retry the entire transaction. Unique violations and deadlocks can also represent retryable concurrency races when the application can prove that from its design. [PostgreSQL, Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html#XACT-SERIALIZABLE), [PostgreSQL, Serialization Failure Handling](https://www.postgresql.org/docs/current/mvcc-serialization-failure-handling.html)

**CTI-RAG inference**

Do not implement “check then insert” in application memory. Stable identities, digest agreement, one active reservation per canonical domain, current output heads, and receipt-head transitions need database constraints or a row lock plus a conditional update.

All security- and identity-bearing columns are `NOT NULL`. A conflict is then classified by reading the existing row inside the same transaction:

- same identity and same canonical digest: idempotent replay;
- same identity and different digest or binding: integrity failure;
- same current target and wrong expected version: local concurrency conflict;
- same active Effect Domain held by another unresolved effect: dependency-scoped suspension, not a generic database error.

The production Adapter may run semantic transitions at `SERIALIZABLE`, or use an equivalent rigorously tested locking protocol. Because the command contains immutable data and no external callback, the Adapter can retry a complete `40001`/recognized deadlock transaction. Exhaustion returns a known-not-committed transient result only if PostgreSQL proves rollback; connection loss remains acknowledgement-unknown.

Canonical Effect Domain rows must be acquired in sorted canonical-byte order to reduce deadlocks. A unique partial index over unreleased reservations is useful, but its predicate and transition semantics must be exercised in conformance tests rather than assumed from an application-side query.

### 3. A transactional outbox solves the local-write/remote-send dual write, not remote exactly-once execution

**Source facts**

- AWS's transactional outbox guidance identifies the dual-write failure: a database update can commit while an external notification fails, or the external action can occur while the database update fails. The outbox stores the notification with the business update and processes it after commit. It also warns that duplicate messages are possible and consumers should be idempotent. [AWS Prescriptive Guidance, Transactional Outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
- PostgreSQL `SKIP LOCKED` gives an inconsistent view and is unsuitable for general-purpose reads, but is explicitly suitable for avoiding contention among consumers of a queue-like table. [PostgreSQL, SELECT locking clause](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)

**CTI-RAG inference**

An Effect Intent is the outbox work item. The admission transaction persists it and its reservations; a dispatcher later leases it. `SKIP LOCKED` is permitted only to divide due dispatcher/recovery work among workers. It is not permitted to decide that the recovery set is complete, that no effect exists, or that an Effect Reservation can be released.

The dispatcher must persist `dispatch_started` before crossing the remote seam. A crash can then produce both conservative cases:

- marker persisted, request never left the process;
- marker persisted, request committed remotely, response never returned.

Both are handled as “may have dispatched.” The lease coordinates workers but proves nothing about the remote effect. Recovery queries the target-owned status/receipt and replays the exact same request only when the qualified target contract expressly permits same-key, same-digest replay.

No distributed two-phase commit is introduced between Workspace PostgreSQL and Case Management. The qualified remote receipt/idempotency protocol is the cross-system recovery mechanism.

### 4. Full event sourcing is possible but adds obligations the first slice does not need

**Source facts**

- AWS describes event sourcing as an immutable, append-only, ordered event store from which current or point-in-time state can be reconstructed. It is useful when full history, multiple projections, replay, and audit are primary requirements, but it requires event ordering, optimistic concurrency, event-store scaling, and projection handling. [AWS Prescriptive Guidance, Event Sourcing](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/event-sourcing-pattern.html)

**CTI-RAG inference**

A full event store would make every state transition an indefinitely replayable public fact. That would require permanent decoder compatibility, deterministic reducers, projection checkpointing, event correction policy, protected-content redaction rules, and careful replay of historical authorization semantics before the first Resource Reference can be attached.

The first slice needs immutable intent, immutable receipt observations, audit lineage, and a rebuildable Dependency Index. It does not require reconstructing every Workspace view solely from generic events. Normalized authority tables plus append-only observations provide those properties with fewer failure modes. A future migration to full event sourcing would be a separate decision, not an implementation detail of this seam.

### 5. Production durability includes the claimed failover topology

**Source facts**

- PostgreSQL synchronous replication can wait until changes are transferred to synchronous standbys. With `synchronous_commit=on`, configured synchronous standbys flush the commit record to durable storage; `remote_write` is weaker, while `remote_apply` additionally waits for replay and query visibility. [PostgreSQL, Synchronous Replication](https://www.postgresql.org/docs/current/warm-standby.html#SYNCHRONOUS-REPLICATION), [PostgreSQL, WAL settings](https://www.postgresql.org/docs/current/runtime-config-wal.html#RUNTIME-CONFIG-WAL-SETTINGS)
- Asynchronous replication can lose transactions during failover even if they were committed on the former primary. Synchronous replication extends the durability of a local commit to the configured synchronous standby set. [PostgreSQL, Log-Shipping Standby Servers](https://www.postgresql.org/docs/current/warm-standby.html)

**CTI-RAG inference**

The production Adapter's qualification evidence must state the crash/failover envelope it claims. Minimum conditions for strict effect dispatch are:

- synchronous local commit; `synchronous_commit=off` is rejected for every admission, output publication, receipt merge, and archive activation transaction;
- no acknowledged journal commit can be discarded by an automatic failover within the claimed recovery envelope;
- backups and restore tests preserve operation/effect identities, reservations, receipts, and referenced archives together; and
- recovery reads use the current authoritative writer or a replica with an explicit causal-visibility guarantee.

`synchronous_commit=on` plus an actually configured synchronous standby is a reasonable PostgreSQL basis for a zero-data-loss failover claim. `remote_apply` is needed only when the design requires the committed row to be immediately query-visible on a standby; it is not a universal default. If a deployment intentionally accepts nonzero RPO, effectful capabilities must stop before dispatch whenever loss of an acknowledged intent could occur. Read-only operations can have a different qualification.

## Recommended private Module

### Why this is a deep Module

The persistence seam belongs inside `OperationCoordinator`; `CaseWorkspace`, Pi hooks, tools, and model-visible code never see tables, SQL, transaction retries, leases, receipt ranks, or GC joins. A representative Interface is:

```typescript
interface DurableOperationJournal {
	resume(input: WorkspaceResume): Promise<WorkspaceRecovery>;
	admit(input: BoundOperationPlan): Promise<AdmissionDecision>;
	observe(input: OperationObservation): Promise<ObservationDecision>;
	claimRecovery(input: RecoveryClaim): Promise<RecoveryBatch>;
}
```

The names are provisional; the semantic shape is the recommendation. `admit` owns idempotent operation creation and pre-execution reservations. `observe` owns all monotonic facts, output fencing/publication, dispatch markers, receipts, and synchronization evidence. `resume` verifies the durable Workspace binding and returns the derived recovery/suspension view. `claimRecovery` leases due work without claiming the scan is authoritative truth.

This Interface is deliberately not:

```typescript
insertIntent();
updateOperationState();
saveReceipt();
deleteReservation();
listEdges();
```

Those calls would expose transaction ordering to every caller and permit partial commits. Adapter-specific transaction objects, SQLSTATE values, table rows, and test failpoints remain private to implementations.

The PostgreSQL and in-memory implementations are two Adapters at this private Seam. This is a real seam because production durability and deterministic test fault injection genuinely vary. Tests use the same Module Interface as production code.

### Workspace Binding

**Problem solved:** a durable Operation ID or output must never be reopened under another Case, tenant, actor scope, or purpose after a Session is copied, rewound, or misconfigured.

**Inputs:** Workspace ID, tenant/authority partition, Case ID, stable actor scope ID, purpose, binding schema version, and the active contract identity requested for new work.

**Outputs:** one immutable binding plus a monotonically CAS-updated binding generation for mutable lifecycle fields such as active contract and active Dependency Index generation.

**Boundary:** authorization revision and credentials are current runtime inputs, not an immutable claim that the actor remains authorized. Session branch/head belongs to individual operation dependencies, not the Workspace identity. Closing a Workspace does not delete unresolved effects.

**Failure behavior:** reopening the same Workspace ID with different immutable binding dimensions is an integrity error. Missing current authorization may allow narrow recovery of already-durable effects but cannot admit new user work. An acknowledgement-unknown bind is resolved by lookup before opening.

### Operation Intent and declared claims

**Problem solved:** recovery needs the exact original operation and complete dependency/effect declaration before any execution result can exist.

**Inputs:** stable Operation ID; recipe/capability kind and version; canonical request digest; actor/Case/task/run binding; catalog, activation, manifest, schema, and decoder digests; exact authorize/current/basis/historical input bindings; declared Output Claims and atomic groups; local write targets; retry class; and optional Effect Intent.

**Outputs:** one immutable admitted operation with a durable journal revision. If the plan is effectful, every declared Effect Domain is reserved in the same transaction.

**Boundary:** admission does not prove execution started. It does not persist partial model streams or remote responses. Model text cannot choose dependency keys, effect domains, identity, digests, or retry class.

**Failure behavior:** missing archives, an inactive contract for new work, stale expected binding, incomplete dependency/effect declarations, or a conflicting active reservation rejects before execution. Same Operation ID plus same plan digest returns the existing admission. Same ID plus different digest quarantines that identity and dispatches nothing.

### Output Claim and derivation edges

**Problem solved:** a valid candidate can otherwise become visible without the dependencies needed to challenge, hide, or rebuild it.

**Inputs:** admitted operation/output identity, publication class, atomic group, immutable payload or content-addressed payload reference, payload digest, current dependency observations, replacement target and expected target version, and the exact derivation edges compiled from the operation recipe.

**Outputs:** one immutable output version, a local operation receipt, current-target head update when applicable, and all derivation edges in one transaction.

**Boundary:** large encrypted blobs may be written before the transaction to content-addressed storage, but they are unreachable until a committed claim references their verified digest. The database transaction never depends on deleting an unreferenced blob. Historical output and current output are distinct claims even when their body bytes match.

**Failure behavior:** stale authorization/current dependencies, a changed expected output head, a missing blob/digest, an incomplete atomic group, or a derivation mismatch publishes nothing. An acknowledgement-unknown publication is looked up by Operation ID plus Output ID/digest; replay never creates a second output version. Supersession appends a new claim and updates a head; it does not rewrite lineage.

### Effect Intent and Effect Reservation

**Problem solved:** after dispatch may have started, a timeout or process crash cannot reveal whether the authority committed the effect.

**Inputs:** stable effect identity and idempotency key, request digest and reconstructable canonical request, target and receipt namespace, original expected revisions and authority bindings, retry/status contract, proof-retention deadline, and sorted owner-approved canonical Effect Domains.

**Outputs:** immutable Effect Intent, one active reservation per declared domain, and an eligible dispatcher work item, all committed with the parent Operation Intent.

**Boundary:** a reservation is a local safety fact, not a remote lock and not proof that the effect occurred. Exact-equality overlap is safe only because every manifest co-declares any owner-mandated broad domain such as `case-head/v1(caseId)`.

**Failure behavior:** any admission uncertainty forbids dispatch. A different effect holding an intersecting domain returns a scoped suspension path. Once `dispatch_started` is durable, lack of a response leaves the reservation active. A lease expiry permits another worker to reconcile; it does not prove no send occurred.

### Monotonic remote receipt

**Problem solved:** duplicate, delayed, and reordered status observations must not regress stronger authority proof or invent a winner between contradictory terminal outcomes.

**Inputs:** target authority, caller scope, effect identity, request digest, receipt/status identity, canonical receipt digest, target schema/decoder identity, observed outcome, proof timestamps/expiry, effect references, and resulting Case Revision when accepted.

**Outputs:** an immutable receipt observation plus one materialized receipt head and effect synchronization state.

**Boundary:** authority outcome and local knowledge are separate axes:

- authority head: `none`, `pending`, or one terminal `accepted`, `rejected_no_effect`, `conflict_no_effect`, or target-declared terminal indeterminate outcome;
- local recovery knowledge: `dispatch_not_started`, `may_have_dispatched`, `queryable_unknown`, or `proof_expired`;
- synchronization: `not_applicable`, `accepted_unsynchronized`, or `projection_proved`.

`outcome_unknown` and `indeterminate_effect` are not weak target receipts. They describe local knowledge and do not outrank or overwrite later matching authority proof.

**Failure behavior:** duplicate identical observations are idempotent. `none -> pending -> terminal` and `none -> terminal` are valid. Pending after terminal is retained for audit but does not change the head. The same terminal proof repeated is idempotent. Different terminal outcomes, a receipt identity reused with different bytes/digest, an accepted result missing its stable effect reference/resulting revision, or a decoder mismatch creates an integrity incident; it does not choose whichever arrived last. Reservations remain active while the incident is unresolved.

For `accepted`, the reservation transitions from unknown remote outcome to accepted-unsynchronized. It is released only after a receipt-linked Projection proves the effect is contained at the resulting revision or a contract-approved later state. `rejected_no_effect` and `conflict_no_effect` may release after their terminal record is committed, because the qualified target promises the same key cannot later apply.

### Catalog, activation, schema, and decoder archive

**Problem solved:** an unfinished operation cannot safely be decoded or reconciled under whichever manifest happens to be active after restart.

**Inputs:** canonical artifact bytes or trusted content-addressed package reference; artifact kind and semantic identity/version; digest profile and digest; schema dialect; compiler/renderer/decoder set identities; signed build provenance where available; Adapter artifact/deployment/conformance evidence; and lifecycle metadata.

**Outputs:** immutable archive records, an immutable catalog identity, an immutable activation identity, and one CAS-selected active activation for admitting new work.

**Boundary:** mutable `served`, `deprecated`, or revoked lifecycle state is separately revisioned. Activation of new work does not reinterpret old operations. The database never loads executable code solely because a row contains a URI: decoder artifacts must also be present in the trusted deployment allowlist and match their archived digest/signature. Archiving a schema is not authorization to admit it.

**Failure behavior:** one semantic identity/revision mapping to different bytes/digests is an integrity error. An operation cannot be admitted until every referenced archive row exists. Missing or corrupt historical material on recovery keeps the already-recorded domains suspended and raises an archive-integrity incident; the current catalog is not substituted.

### Dependency Index rebuild

**Problem solved:** the fast index can be lost, corrupt, or based on an old schema, but missing index rows must never turn into permission.

**Inputs:** immutable/current Output Claims, authoritative derivation edges, current dependency heads, active Effect Reservations, receipt/synchronization heads, operation requirements, and a Workspace journal revision.

**Outputs:** a new index generation containing dependency-to-output, output-to-output, reservation-root, and admission-explanation paths; a validation digest/count; and an atomic active-generation switch.

**Boundary:** the index is never the source of Operation Intents, output lineage, receipts, reservations, or contract pins. Its generation number is a storage/materialization coordinate, not a dependency version and not a global invalidation epoch.

**Failure behavior:** recovery treats a missing/corrupt generation as unknown dependency coverage. The previous valid generation stays readable while a replacement builds. Operations proven disjoint from unresolved roots can continue only when that proof comes from an intact authoritative/index generation; absence of an edge in an incomplete build proves nothing.

A scalable rebuild can avoid a long Workspace freeze:

1. allocate inactive generation `G` and capture source journal revision `R`;
2. populate `G` from a repeatable snapshot of authoritative rows through `R`;
3. take the short per-Workspace journal writer lock, capture current revision `H`, and replay authoritative changes `(R, H]` into `G`;
4. validate referential closure and generation digest/count;
5. atomically switch the binding's active index generation to `G`; and
6. release the lock, retaining the former generation until readers drain and GC proves it unreachable.

A crash before step 5 leaves the old generation active. A crash after step 5 exposes the complete new generation. The first slice may rebuild a small Workspace in one bounded transaction, but it must preserve the same old-or-new activation property.

## Minimum relational authority model

These are logical records, not a requirement for one table per row below. Physical normalization may change without changing the Module Interface.

| Authority record | Minimum invariant |
|---|---|
| `workspace_binding` | Workspace ID uniquely maps to immutable tenant/Case/actor-scope/purpose; mutable generation is updated by CAS |
| `contract_archive` | artifact digest is primary identity; semantic kind/ID/version maps to exactly one digest; referenced rows cannot be deleted |
| `activation_archive` | activation digest binds catalog, Adapter/deployment/conformance evidence, schemas, and decoder set |
| `operation_intent` | `(workspace_id, operation_id)` is unique; immutable plan digest, bindings, retry class, and contract pins are non-null |
| `operation_input` | unique `(operation_id, input_slot, canonical_key)`; usage and exact version/digest are immutable |
| `output_declaration` | unique `(operation_id, output_id)` with target, publication class, atomic group, and dependency slots |
| `output_claim` | one immutable claim per declared output; payload digest/reference and publication decision are atomic with edges |
| `current_output_head` | one row per canonical local target; conditional update requires expected version/claim |
| `derivation_edge` | unique origin-to-output edge; foreign keys reject missing operation, input, output, or archive |
| `effect_intent` | target caller scope plus effect identity uniquely maps to one request digest and receipt namespace |
| `effect_reservation` | at most one unreleased reservation per canonical authority domain; released rows remain audit facts |
| `dispatch_attempt` | stable attempt identity; lease owner/expiry coordinates workers; durable `dispatch_started` precedes network I/O |
| `receipt_observation` | authority receipt/status ID maps to one canonical digest; duplicate observation is idempotent |
| `receipt_head` | transition relation is validated under row lock/CAS; contradictory terminal outcomes quarantine instead of overwrite |
| `effect_sync_head` | accepted remains unsynchronized until receipt-linked Projection proof is committed |
| `dependency_index_generation` | only a validated complete generation can be active; source revision/digest make rebuild auditable |

Every authoritative mutation receives a per-Workspace `journal_revision` allocated while holding the Workspace binding row. This gives rebuild and audit a committed sequencing coordinate. It serializes only short local transactions for one Workspace; it is never held across remote I/O and never becomes a correctness claim that unrelated outputs are stale. Cross-Workspace Effect Domain exclusion is supplied by the authority-wide canonical reservation uniqueness, not by the Workspace row.

## Minimum atomic transaction aggregates

The following aggregates are the smallest useful atomic units. Splitting any row group reintroduces a crash state with an unsafe partial fact.

### A. Contract archive and activation

Atomically install verified archive rows and immutable catalog/activation references. A separate CAS selects the activation for new operations. Existing operations keep their pinned digests regardless of the selected activation.

### B. Workspace resume/binding

Atomically verify immutable binding dimensions, record the current binding/lifecycle generation, select the active validated Dependency Index generation, and return unresolved recovery roots. It does not refresh remote content inside the transaction.

### C. Operation admission

Atomically create or replay:

- Operation Intent and plan digest;
- exact input bindings;
- Output Claim declarations and dependency origins;
- local target expectations;
- Effect Intent, receipt/status key, and canonical request reference when effectful;
- every possible Effect Reservation; and
- initial recovery/dispatcher eligibility.

If this transaction is not proven committed, no model/tool execution that can produce a current claim and no remote dispatch begins.

### D. Local output publication

Atomically validate the current authority/dependency fence and expected target versions, then install the complete atomic output group, local receipt, current target heads, derivation edges, and journal facts. Either the entire group is visible or none of it is.

### E. Dispatch/receipt/synchronization transition

Each transition is a short transaction:

- persist `dispatch_started` before the network call;
- append a transport or target observation;
- validate and update the monotonic receipt head;
- create accepted Projection synchronization requirements or release no-effect reservations; and
- update derived dirty/challenge facts.

The network call occurs between transactions, never inside one. Accepted receipt and Projection synchronization may therefore require separate transactions; the accepted reservation remains active between them.

### F. Dependency Index generation activation

Atomically validate rebuild coverage through the locked current journal revision and switch the active generation. Building rows is not itself an availability or authority change.

### G. Retention/GC batch

Atomically mark candidate roots against one retention/authorization policy revision, recheck reachability under lock, delete only safe bodies/derived generations, and append/retain required tombstones. GC never races a new reference merely because a previous scan saw zero references.

## Crash-window truth table

| Crash or lost-ack window | Durable truth after recovery | Required action | Forbidden inference/action |
|---|---|---|---|
| Before admission transaction starts | no intent | a caller may start admission with the same planned Operation ID | assuming an operation existed |
| During admission before commit | no visible partial aggregate | lookup the Operation ID; retry the identical admission only after absence is authoritative | dispatching from in-memory intent |
| Admission committed, success response lost | intent and any reservations exist | lookup same ID/digest and return existing admission | create a new Operation/effect identity |
| Admission acknowledged, crash before dispatcher claim | eligible durable intent | recovery worker may claim it | treating unclaimed as cancelled |
| Dispatcher lease committed, crash before `dispatch_started` | leased but no possible-send marker | after lease expiry, claim and continue under same identity | use a new key; treat lease as remote proof |
| `dispatch_started` committed, crash before socket send | may-have-dispatched locally, though remote actually did not | status query; same-intent replay only if target contract permits | asserting no effect from local timing |
| Request bytes sent, local marker/transport update lost | intent plus possible dispatch | reconcile original target identity | blind retry or inverse mutation |
| Remote returns pending, local receipt transaction lost | possible dispatch; target may be pending | query target and merge pending/terminal monotonically | release reservation because no local receipt exists |
| Remote commits, response lost | possible dispatch; target receipt/effect exists | recover target-owned accepted proof | send a new mutation |
| Response received, crash before receipt merge | same as response lost | query/merge by same receipt/effect identity | trust Session transcript as receipt |
| Accepted receipt committed, crash before Projection sync | accepted-unsynchronized | fetch a receipt-linked Projection/resulting revision; never resend | classify as unknown remote outcome |
| Projection contains effect, crash before sync transaction commit | accepted-unsynchronized remains locally | repeat Projection proof and idempotently commit sync | release based only on uncommitted memory |
| Rejected/no-effect receipt committed, caller acknowledgement lost | terminal no-effect; reservation released atomically | lookup and return existing result | rebase/retry old operation automatically |
| Local Working Set output transaction committed, caller acknowledgement lost | exactly one output/receipt/edge group | lookup same operation/output digest | create another entry/version |
| Dependency Index rebuild crashes before activation | old generation remains active | discard/resume inactive generation | query incomplete generation as authority |
| Dependency Index activation commits, acknowledgement lost | new complete generation is active | lookup active generation | activate another generation without verification |
| Catalog archive writes commit but activation does not | artifacts exist but new work still uses old activation | safely retry activation CAS | reinterpret existing operations |
| Activation commits, process crashes before Workspace sees it | new operations use selected activation; old intents retain old pins | reopen and read binding generation | rewrite old operation contract pins |
| GC marks candidates, crashes before sweep | no authoritative fact lost | re-evaluate before sweep | delete from stale mark result |

The table intentionally has no “prepared but definitely not sent” state after `dispatch_started`. A local process cannot close that window; only a receiver-side idempotency/status contract can.

## Unknown local acknowledgement protocol

For every mutating Module call:

1. the caller supplies a stable semantic identity and canonical digest before the transaction;
2. the Adapter executes only deterministic database work derived from that immutable command;
3. a known rollback returns `not_committed` with a structured conflict/retry reason;
4. a connection/process failure near commit returns or recovers as `acknowledgement_unknown`;
5. the Module reconnects to the authoritative writer and looks up the identity;
6. matching row and digest means the original transaction committed and its stored decision is returned;
7. same identity with a different digest/binding is an integrity incident;
8. authoritative absence permits replay of the exact same command, not allocation of a new semantic identity; and
9. if the HA topology cannot establish whether the acknowledged row survived failover, effect dispatch remains disabled until storage authority is restored.

This protocol works only because each aggregate has a stable identity and all dependent rows commit together. A generated database sequence alone is insufficient for recovery because the caller would not know the allocated value after a lost acknowledgement.

## Retention and GC safety

### Retention roots

An archive, intent, edge, receipt, or identity tombstone remains reachable while any of these apply:

- active Workspace binding or active catalog/activation;
- unresolved, pending, possibly dispatched, accepted-unsynchronized, indeterminate, or quarantined effect;
- target proof/idempotency lookup guarantee and local automatic recovery window, including safety margin;
- retained current/historical output, Working Set entry, Session receipt reference, audit record, appeal, or operator resolution;
- Case proposal/effect record retained by governed Case policy;
- Dependency Index generation still serving readers or needed to diagnose a rebuild; or
- legal, security, provenance, or incident-retention hold.

For an effect identity, the local retention lower bound is at least the greater of the local recovery/audit requirement and the target's effective proof horizon. Target proof expiry does not make deletion safe when the effect remains unknown; it changes local knowledge to `indeterminate_effect` and preserves the identity, digest, domains, target, archive pins, and resolution state.

### What may be compacted

Protected request/output bodies may be encrypted separately and purged or crypto-erased under authorization/retention policy while retaining a minimum non-sensitive tombstone. The tombstone must still prevent identity reuse and carry enough canonical Effect Domains and contract pins to keep suspension sound. Whether even domain keys leak protected Case topology is a security-policy decision; such tombstones remain actor/tenant isolated and are not model-visible.

Receipt observation duplicates and old inactive Dependency Index generations may be compacted after the authoritative receipt head, audit policy, and reader reachability are proven. An immutable output body may move to colder content-addressed storage, but its digest/reference and derivation lineage remain.

### Safe sweep

- Prefer foreign keys with restrictive deletion from operations/receipts to archive rows; do not rely only on an application reference count.
- GC is mark, recheck, then sweep. The final delete checks `NOT EXISTS`/foreign-key reachability in the same transaction that prevents a concurrent new reference.
- Never cascade-delete from Workspace/Session close into Effect Intents, receipts, archives, or lineage.
- Keep stable identity/digest tombstones beyond body deletion so an old key cannot be reused with new semantics.
- A corrupt or missing archive is an incident, not a cue to delete its referring operations.
- Backup/restore and disaster-recovery tests must cover archive rows and journal authority rows as one consistency set.

Exact durations are product/compliance and Adapter-qualification values, not consequences of PostgreSQL. The invariant is that GC cannot end the proof mechanism before every operation that relies on it is terminally safe.

## Adapter conformance contract

The conformance suite is shared by the production PostgreSQL Adapter and the in-memory Adapter. Passing unit tests against a `Map` does not qualify PostgreSQL, and passing PostgreSQL integration tests does not permit the in-memory Adapter to omit failures callers rely on.

### Common semantic requirements

Both Adapters must demonstrate:

1. all admission rows become visible atomically or none do;
2. stable identity plus same digest is idempotent, while different digest is an integrity failure;
3. concurrent admission of intersecting Effect Domains yields at most one active holder;
4. disjoint domains and disjoint Working Set targets can proceed without a logical global suspension;
5. output, current-head CAS, local receipt, and derivation edges commit atomically;
6. wrong expected output/dependency version publishes nothing;
7. a simulated post-commit lost acknowledgement is resolved by lookup without duplication;
8. `dispatch_started` survives Adapter/process recreation before any simulated remote send;
9. leases expire under an injected clock but never release Effect Reservations or prove no dispatch;
10. duplicate and reordered pending/terminal observations preserve the valid monotonic head;
11. contradictory terminal receipts quarantine and keep reservations;
12. accepted retains reservation until Projection synchronization proof; authoritative no-effect releases atomically;
13. crash before Dependency Index activation leaves the old generation; crash after activation exposes the complete new one;
14. index loss rebuilds the same admission/explanation results from authority rows;
15. old operations decode through pinned archives after a new activation; missing archive fails conservatively;
16. GC cannot delete a newly referenced archive/output or any unresolved-effect tombstone; and
17. recovery results are scoped by Workspace/authority partition and do not manufacture one global suspended flag.

### In-memory Adapter obligations

The in-memory Adapter is a semantic simulator, not a simplistic fake. It must provide:

- one atomic mutation lock/version and copy-on-write commit so partial aggregates are unobservable;
- the same unique, non-null, foreign-key, digest, transition, and CAS behavior as production;
- deterministic injected clock, lease owner, retry schedule, and ID source;
- failpoints immediately before commit, immediately after commit but before acknowledgement, after dispatch marker, during receipt merge, during index build, and before/after generation activation;
- a durable image that can instantiate a fresh Adapter after simulated process death; recreating an empty `Map` is not a restart test;
- deliberate duplicate, reorder, and contradiction injection for receipt observations; and
- no test-only public methods on the Module Interface. Fault control belongs to Adapter construction/test harness internals.

### PostgreSQL Adapter obligations

Production conformance runs against a real supported PostgreSQL version and schema, not a mocked client. It must verify:

- actual unique/partial unique and foreign-key constraints;
- chosen isolation/locking protocol under concurrent connections, including multi-domain lock ordering;
- whole-command retry for `40001` and approved deadlock cases without repeating external callbacks;
- connection termination before commit, during commit acknowledgement, and after commit, with identity lookup;
- `synchronous_commit` enforcement on strict journal transactions and deployment evidence for claimed failover RPO;
- worker contention using `FOR UPDATE SKIP LOCKED` only on due queue work;
- migration compatibility for retained old rows and archives;
- backup/restore or failover recovery of intent, reservations, receipts, and archives together; and
- metrics/diagnostics for acknowledgement-unknown, serialization retries, active reservations, proof-retention margin, receipt contradiction, archive failure, and index rebuild generation.

Adapter qualification records the database/server version, schema migration digest, configuration evidence, HA/failover assumptions, conformance suite version, and test result in the activation digest/evidence. A code artifact passing on one topology does not qualify every deployment.

## Implementable alternatives

### Alternative A — normalized relational journal plus immutable observations (recommended)

Store current authority facts in constrained relational records, append transport/receipt/audit observations, and materialize only the Dependency Index and receipt head. Use short atomic transactions and an outbox dispatcher.

**Advantages**

- atomic invariants map directly to PostgreSQL constraints, row locks, and transactions;
- current recovery queries do not require replaying an unbounded event history;
- old receipt observations remain auditable without making every cache/lifecycle change an eternal event schema;
- Dependency Index remains explicitly disposable and rebuildable;
- GC and protected-body erasure can preserve identity/lineage tombstones without rewriting an event stream; and
- the private Interface can stay semantic and small.

**Costs and risks**

- schema migrations must preserve retained operation/receipt rows;
- current heads and immutable observations must be updated atomically to avoid divergence;
- journal-revision allocation and multi-domain locking need concurrency tests; and
- reconstructing arbitrary point-in-time Workspace UI is not automatic.

### Alternative B — full append-only event store with replayed projections

Persist every Workspace operation transition as an event under a per-Workspace expected stream version. Rebuild operation state, receipt heads, reservations, output heads, and Dependency Index entirely from replay.

**Advantages**

- strongest built-in chronological audit and point-in-time reconstruction;
- all materialized views are conceptually rebuildable from one source; and
- optimistic stream-version append can give a clear concurrency model.

**Costs and risks**

- every historical event schema and reducer/decoder becomes a long-lived recovery dependency;
- authorization revocation and protected-body erasure are difficult in an immutable stream;
- projection checkpoint lag becomes another admission/suspension condition;
- snapshot validity, replay determinism, poison events, event correction, and cross-stream Effect Domain reservations require additional protocols;
- a generic `appendEvent` Interface tends to move domain transition validation into callers; and
- it adds substantial machinery before the first R1 Resource Reference.

### Decision

Choose Alternative A for the first vertical slice. Preserve append-only facts where arrival order and audit matter—dispatch attempts, receipt observations, archive/lifecycle revisions, and operator resolutions—but keep validated current authority rows for operation, reservation, receipt, synchronization, and output heads.

Do not add a separate durable-workflow engine, generic event bus, or public repository layer now. The design leaves those as future implementation substitutions behind the private Module if production scale or audit requirements later justify them.

## Rejected shortcuts

- **One mutable `operation.status` column:** loses contradictory observations and lets arrival order define truth.
- **One transaction per table/repository call:** admits intent without reservations, output without edges, or receipt without release/sync state.
- **Database sequence as caller recovery identity:** the caller may not learn it after a lost commit acknowledgement.
- **Dispatch before intent commit:** permits a remote effect with no durable recovery identity.
- **Holding a database transaction open across remote I/O:** couples locks and transaction outcome to an unbounded external call and still does not create cross-system atomicity.
- **Lease expiry as no-send proof:** a worker can send before dying; the lease is only local coordination.
- **`SKIP LOCKED` as complete recovery scan:** its view is intentionally inconsistent.
- **Blind database transaction retry after connection loss:** the first transaction may have committed; lookup must precede semantic replay.
- **Numeric receipt-state rank:** terminal outcomes are mutually exclusive, not ordered; contradiction must quarantine.
- **Release accepted reservation immediately:** downstream Case work can run before Projection proves the accepted effect is visible.
- **Dependency Index as source of truth:** index loss would incorrectly remove dependencies and reservations.
- **Delete journal on Session rewind/close:** remote effects and recovery identity outlive Session history.
- **Use current decoder for old intent:** silently changes identity, receipt, and Effect Domain semantics.
- **Asynchronous PostgreSQL commit for Effect Intent:** an acknowledged intent can disappear after the external effect is sent.
- **In-memory `Map` with no restart/fault model:** exercises the happy path but not the persistence contract.
- **Full event sourcing by default:** introduces permanent event/decoder/projection obligations without a first-slice requirement.

## Open values that require deployment or product policy

The mechanism is determined; these numeric/policy values still need qualification:

- maximum automatic database and remote-reconciliation retry duration;
- dispatcher lease duration and clock-skew budget;
- Case Management idempotency/status proof retention and safety margin;
- local operation, receipt, output, tombstone, and archive retention;
- PostgreSQL HA topology, synchronous standby quorum, and claimed disaster envelope;
- maximum per-Workspace index rebuild size before generation/catch-up is mandatory;
- protected-body encryption and crypto-erasure policy after authorization revocation;
- operator resolution and governed compensation policy for `indeterminate_effect`; and
- whether multiple Workspaces for one Case share all authority-domain reservations or a narrower owner-proven partition.

None may default to “permission.” Missing durability/proof qualification disables the affected effect capability while leaving provably disjoint read-only work available.

## Primary sources reviewed

- [PostgreSQL: Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [PostgreSQL: Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
- [PostgreSQL: `INSERT ... ON CONFLICT`](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)
- [PostgreSQL: Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [PostgreSQL: Serialization Failure Handling](https://www.postgresql.org/docs/current/mvcc-serialization-failure-handling.html)
- [PostgreSQL: Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [PostgreSQL: `SELECT` locking clause and `SKIP LOCKED`](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)
- [PostgreSQL: Asynchronous Commit](https://www.postgresql.org/docs/current/wal-async-commit.html)
- [PostgreSQL: WAL settings and `synchronous_commit`](https://www.postgresql.org/docs/current/runtime-config-wal.html#RUNTIME-CONFIG-WAL-SETTINGS)
- [PostgreSQL: Synchronous Replication](https://www.postgresql.org/docs/current/warm-standby.html#SYNCHRONOUS-REPLICATION)
- [PostgreSQL: Connection Status Functions](https://www.postgresql.org/docs/current/libpq-status.html)
- [PostgreSQL: Frontend/backend protocol termination](https://www.postgresql.org/docs/current/protocol-flow.html#PROTOCOL-FLOW-TERMINATION)
- [AWS Prescriptive Guidance: Transactional Outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
- [AWS Prescriptive Guidance: Event Sourcing](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/event-sourcing-pattern.html)
