# Case Management Facade Concurrency and Receipt Protocol

Status: primary-source research note and implementable protocol recommendation for the first CTI-RAG Agent Investigation Workspace vertical slice.

Design disposition (2026-07-20): the normative first-slice contract in [`case-management-facade-contract.md`](../agent-workspace/case-management-facade-contract.md) narrows this research candidate to a synchronous terminal command transaction. Its former pending-to-terminal state, `receiptSequence`, HTTP 202 pending receipt, and `cancelled_before_dispatch` candidate are superseded and are not implementation obligations. The primary-source findings, transaction ownership analysis, durability requirements, terminal receipt/idempotency rules, outbox separation, and alternative comparison remain applicable. Where this note's candidate DTO/state machine differs, the normative contract governs.

Research date: 2026-07-20.

Source baseline: HTTP standards, PostgreSQL 18 documentation, current Kubernetes API documentation, AWS EC2's first-party idempotency contract, and the official OpenCTI repository at commit [`3fe1ce3c1f87e2ad33f370fe358454ffb682ae12`](https://github.com/OpenCTI-Platform/opencti/tree/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12).

## Conclusion

The smallest strict facade is not an HTTP proxy around stock OpenCTI. It is a **transaction owner** with five inseparable responsibilities:

1. issue the authoritative `CaseRevision` used for Case-partition compare-and-swap;
2. admit one immutable `(operation identity, request digest)` pair before any effect can be dispatched;
3. preserve a monotonic pending-to-terminal receipt and an authoritative status lookup;
4. evaluate current authorization, policy, capability Grant, and contract lifecycle at the effect's linearization boundary; and
5. prove separately whether an accepted Case effect is present in a currently authorized Case Projection.

There are two implementable ownership arrangements:

- **Recommended — database-owned Case command state plus outbox materialization.** Case Management owns the authoritative Case head, neutral Resource References, idempotency ledger, receipt, and outbox in one PostgreSQL transaction. OpenCTI is a materialized/read model for this slice. A committed facade receipt is outcome-authoritative even if OpenCTI materialization is still pending.
- **Constrained fallback — exclusive all-writer coordinator over OpenCTI.** OpenCTI remains the Case state owner, while the facade durably serializes every writer and permits only one unresolved mutation in the relevant Case partition. Because stock OpenCTI lacks caller-visible CAS and request receipts, this can qualify only for effects whose unique current predicate is safely reconcilable, initially the additive neutral Case `object` reference. It is invalid if any UI, integration, administrator, or other service can bypass the facade.

A future underlying store that natively provides atomic expected-revision writes plus an identity/digest receipt can support a thin facade. The inspected stock OpenCTI interface does not provide those guarantees.

The recommendation does not determine how many model-facing LLM tools exist. It defines a remote Case semantic-operation protocol below that seam.

## Evidence boundary

Sections labeled **Source facts** report behavior owned by the cited specification, documentation, or source tree. Sections labeled **Protocol conclusion** are CTI-RAG design conclusions derived from those facts. The concrete schema in this note is a recommended `case-write-facade/v1` candidate; it is not claimed to be an existing standard.

## 1. What the source systems actually guarantee

### 1.1 HTTP conditions and retries

#### Source facts

- RFC 9110 defines a method as idempotent when multiple identical requests have the same intended server effect as one request. It says an idempotent request can be repeated after a communication failure, but a client should not automatically retry a non-idempotent request unless it knows the semantics are idempotent or can establish that the original request was not applied. [RFC 9110, section 9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#name-idempotent-methods)
- `If-Match` uses strong entity-tag comparison and must be evaluated before performing the method. A false condition prevents the requested method and normally yields `412 Precondition Failed`. Its primary use is preventing lost updates. [RFC 9110, section 13.1.1](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match)
- `428 Precondition Required` lets an origin require a conditional request to avoid lost updates, but RFC 6585 also warns that clients cannot rely on every server using 428. [RFC 6585, sections 3 and 7.1](https://www.rfc-editor.org/rfc/rfc6585.html#section-3)
- `202 Accepted` is explicitly noncommittal: processing is incomplete and the request might or might not eventually be acted upon. Its representation ought to link to a status monitor. [RFC 9110, section 15.3.3](https://www.rfc-editor.org/rfc/rfc9110.html#name-accepted)
- `409 Conflict` reports a conflict with current target-resource state; `412` specifically reports a false request precondition. [RFC 9110, sections 15.5.10 and 15.5.13](https://www.rfc-editor.org/rfc/rfc9110.html#name-conflict)
- RFC 9457 supplies `application/problem+json` for machine-readable HTTP errors and warns that problem details can leak implementation or private information. [RFC 9457, sections 3 and 5](https://www.rfc-editor.org/rfc/rfc9457.html)
- AWS EC2's official client-token contract demonstrates a useful identity rule: retrying the same token with the same parameters performs no additional action, while reusing the token with different parameters returns `IdempotentParameterMismatch`. [EC2 idempotency documentation](https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html)

#### Protocol conclusion

HTTP method choice, `If-Match`, and status codes are not an operation ledger. The facade needs application-level identity, digest, receipt, retention, and status semantics even if its HTTP mapping uses `PUT`, conditional requests, 202, 409, and Problem Details. A Case revision placed in `If-Match` is valid only when the HTTP target's selected representation is the Case authority resource; `If-Match` on an operation-resource URI would condition the wrong resource. The protocol therefore carries `expectedCaseRevision` explicitly and gives it authority-owned semantics.

A transport timeout has no effect semantics. Once dispatch might have occurred, the only safe next action is status/reconciliation under the original identity. A client-generated new identity is a new logical effect and is forbidden as a timeout retry.

### 1.2 PostgreSQL transaction and concurrency primitives

#### Source facts

- PostgreSQL transactions group multiple changes into one all-or-nothing operation; incomplete states are not visible, committed changes become visible together, and acknowledged commits are recorded in permanent storage. [PostgreSQL transaction tutorial](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- Successfully committed `SERIALIZABLE` transactions have an effect equivalent to some serial execution. Applications must handle `SQLSTATE 40001` serialization failures, and the documentation recommends keeping transactions no larger than integrity requires. [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html#XACT-SERIALIZABLE)
- `SELECT ... FOR UPDATE` prevents other transactions from modifying, deleting, or taking conflicting locks on the selected row until transaction end. Row locks block writers/lockers, not ordinary readers. [PostgreSQL explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS)
- Unique constraints are enforced by unique indexes. `INSERT ... ON CONFLICT DO UPDATE` guarantees one atomic insert-or-update outcome under concurrency. [PostgreSQL unique indexes](https://www.postgresql.org/docs/current/indexes-unique.html), [PostgreSQL `INSERT`](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)
- PostgreSQL advisory locks are advisory: the database does not force all applications to take them. Transaction-level advisory locks are released at transaction end; session-level locks do not follow rollback semantics. [PostgreSQL advisory locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)

#### Protocol conclusion

A single PostgreSQL transaction can atomically bind a Case head, effect predicate, operation identity/digest, terminal receipt, and outbox entry. A unique constraint on `(tenant_id, operation_id)` is the final arbiter for identity races; an application pre-check alone is insufficient.

Normal row locks or serializable transactions are preferable to session advisory locks for the authoritative Case transaction. An advisory lock can optimize coordination only when every writer is already governed by the same protocol; it cannot establish the all-writer condition by itself.

### 1.3 Kubernetes as a version/watch precedent

#### Source facts

- Every Kubernetes object has a `resourceVersion` representing its version in the persistence layer. A stale version on update is rejected with `409 Conflict`, and clients requiring lost-update detection are told to make writes conditional on the existing `resourceVersion`. [Kubernetes API concepts: resource updates](https://kubernetes.io/docs/reference/using-api/api-concepts/#resource-versions)
- A list's `resourceVersion` can start a watch without missing intervening changes. A disconnected client can resume from the last returned version or relist. [Kubernetes change detection](https://kubernetes.io/docs/reference/using-api/api-concepts/#efficient-detection-of-changes)
- Watch history is finite. When a requested version is no longer available, Kubernetes returns `410 Gone`; clients clear the derived cache, relist, and resume from the new list revision. [Kubernetes watch history](https://kubernetes.io/docs/reference/using-api/api-concepts/#efficient-detection-of-changes)
- Kubernetes distinguishes `Exact`, `NotOlderThan`, `Most Recent`, and `Any` read semantics. A collection version does not imply that every item has that same item version. [Kubernetes resource-version semantics](https://kubernetes.io/docs/reference/using-api/api-concepts/#resource-version-semantics)

#### Protocol conclusion

`CaseRevision` should be opaque, authority-issued, and meaningful only for its Case partition. It supports equality preconditions and resume/freshness proofs, not client arithmetic or cross-Case ordering.

A cursor or event stream cannot substitute for durable receipt retention. If a change cursor is trimmed, the caller must rebuild the affected projection partition; it must not infer that an operation did not occur.

### 1.4 Stock OpenCTI boundary

#### Source facts

- The inspected Case schema exposes timestamps and paginated connections, not a documented Case-wide revision or expected-revision mutation precondition. [OpenCTI Case schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case.graphql)
- Container relation mutations return a Container or `StixRefRelationship`, not a durable operation receipt keyed by caller identity. [OpenCTI container mutations](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L16193-L16203)
- Adding a Container reference patches the source reference field, constructs a relationship representation, and then notifies. A response can therefore be lost after the primary state change. [OpenCTI reference-relation add flow](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/domain/stixObjectOrStixRelationship.ts#L51-L71)
- OpenCTI's `object` relation is the neutral Container membership/reference mechanism. It is distinct from a STIX Core Relationship, which asserts CTI semantics. [OpenCTI reference relationship schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L14631-L14681)

#### Protocol conclusion

An OpenCTI timestamp, GraphQL cursor, stream offset, response entity, or locally computed projection digest must not be labeled authoritative `CaseRevision`. A facade that merely stores a receipt beside an unfenced OpenCTI mutation still has an atomicity gap.

The constrained remote-owner arrangement can reconcile R1's unique predicate `(case, "object", resource)` only because the first effect is additive and neutral. Predicate presence alone does not identify which request caused it; attribution additionally requires the facade's durable single-writer ledger and absence of bypass writers.

## 2. Minimal protocol concepts

### 2.1 Authoritative CaseRevision

**Problem.** A proposal based on Case state must not silently apply after that state changes.

**Input.** One Case authority partition and its current committed semantic state.

**Output.** An opaque token, unique for successive committed changes within that Case partition.

**Boundary.** It orders/equality-fences one Case only. Authorization, policy, capability Grant, and contract lifecycle have independent revisions and are always checked current.

**Failure behavior.** An expected/current mismatch produces a terminal no-effect conflict. The facade never guesses equivalence from timestamps, digests, cursors, or similar values.

Rules:

- a semantic Case mutation advances revision exactly once in the same authority transaction as the effect and receipt;
- a replay or `satisfied_without_change` result does not advance it;
- the token is compared for exact equality and treated as opaque by clients;
- every writer that can change the declared Case partition must participate in the same revision discipline; and
- a bypass write is an integrity event that disables strict writes until the Case head is rebuilt or re-anchored.

### 2.2 Operation identity and request digest ledger

**Problem.** A timeout or duplicate request must not create a second logical effect, while an identity reused for different intent must not be silently accepted.

**Input.** Authenticated tenant/principal, stable operation identity, canonical semantic request, and digest profile.

**Output.** Exactly one durable ledger row for `(tenant, operationId)` bound immutably to one digest and one receipt history.

**Boundary.** Transport deadlines, tracing IDs, connection metadata, polling cadence, and human-readable descriptions are not semantic request fields. Model output never supplies identity, digest, authority revisions, or effect domains.

**Failure behavior.** Same identity/same digest returns the current or terminal stored receipt without a second effect. Same identity/different digest is a permanent integrity error and never changes the original row.

### 2.3 Monotonic receipt

**Problem.** Late, duplicated, or out-of-order responses must not turn a known result back into an unknown result or change one terminal fact into another.

**Input.** The admitted ledger identity plus authority-owned processing and reconciliation evidence.

**Output.** A receipt with monotonically increasing `receiptSequence` and one allowed pending-to-terminal transition.

**Boundary.** A receipt proves facade operation outcome. It does not by itself prove that the latest actor-authorized model Projection contains the effect.

**Failure behavior.** A stale sequence is ignored. Contradictory terminal evidence quarantines the affected operation/effect domain and raises an integrity incident; it is never merged as a normal business rejection.

### 2.4 Projection inclusion proof

**Problem.** A write can be authoritative while the read model or current Workspace Projection has not caught up, or the actor can lose permission before observing it.

**Input.** A terminal applied receipt, the requested Projection Profile, and a fresh actor/tenant/purpose authorization decision.

**Output.** A proof binding an authorized Projection revision/digest to the stable effect reference and its inclusion state.

**Boundary.** It proves inclusion in that exact authorized Projection. It is not global graph visibility, ongoing permission, or proof that the effect still exists after later revisions.

**Failure behavior.** Missing proof yields `accepted_but_unsynchronized`; authorization loss yields a non-leaking denial and purges previously materialized content. Neither changes the applied receipt to rejected.

### 2.5 Current fence set

**Problem.** Authority to execute can change independently of Case data while an operation is queued or in flight.

**Input.** Current authenticated principal and purpose plus expected Case, authorization, policy, Grant, and contract-lifecycle revisions.

**Output.** Either a validated fence set at the effect linearization boundary or a terminal pre-effect no-effect disposition.

**Boundary.** A successful check authorizes the linearization point only. Later revocation controls disclosure and future operations; it cannot retroactively prove an already linearized effect did not happen.

**Failure behavior.** Before possible dispatch, mismatch prevents dispatch. After dispatch may have happened, mismatch stops new work but reconciliation continues under the original identity without repeating the effect.

The word "current" requires an ownership mechanism, not just a recent read. One of these must be qualified for every fence:

1. the fence record and its updates participate in the same authority transaction/lock order as the Case effect;
2. the fence authority atomically issues and consumes a single-operation decision reservation whose linearization order relative to revocation is explicit; or
3. an underlying effect API atomically validates the fence revision with the write.

A linearizable authorization read followed by an unrelated database commit still has a time-of-check/time-of-use window. It cannot claim that revocation before effect commit was fenced unless the authority contract defines the authorization decision itself as the earlier operation linearization point and guarantees the resulting reservation through commit. Stock OpenCTI does not expose such a write reservation in the inspected API.

## 3. Recommended `case-write-facade/v1` semantic interface

This is transport-neutral. An HTTP Adapter can map submit to `PUT /v1/cases/{caseId}/operations/{operationId}` and lookup to `GET` on the same URI. The operation resource URI makes HTTP retries convenient, but the application ledger remains authoritative.

### 3.1 Submit request

```typescript
interface SubmitCaseOperationV1 {
	protocol: "case-write-facade/v1";
	operationId: string;
	requestDigest: string;
	digestProfileId: "cti-jcs-sha256/v1";
	principal: {
		tenantId: string;
		subjectId: string;
		delegationId?: string;
		purpose: string;
	};
	contract: {
		capabilityId: "case.resource-reference.add-neutral";
		contractVersion: string;
		contractDigest: string;
		inputSchemaId: string;
	};
	target: {
		caseId: string;
		expectedCaseRevision: string;
	};
	expectedFences: {
		authorizationRevision: string;
		policyRevision: string;
		grantRevision: string;
		lifecycleRevision: string;
	};
	payload: {
		resourceId: string;
		resourceVersion: string;
		relationKind: "object";
	};
}
```

Submission rules:

1. `principal` is a trusted envelope bound by the Workspace and must match the authenticated channel or verifiable delegation. It is not accepted from model business payload.
2. The server reconstructs the canonical semantic request and recomputes `requestDigest`. The digest covers every field shown above except `protocol`, `operationId`, and `requestDigest` itself. It also binds the normalized authority partition and effect predicate derived by the closed contract.
3. Connection deadline, cancellation token, trace/correlation ID, locale, and response preference are excluded from the digest and cannot cancel a possibly dispatched effect.
4. Unknown fields, capability IDs, contract digests, schema IDs, relation kinds, or digest profiles fail closed before dispatch.
5. A well-formed authenticated identity is durably admitted before any external effect call. Authentication or structural failures that occur before admission have a mechanically provable no-dispatch path but no receipt.

### 3.2 Receipt response

```typescript
interface CaseOperationReceiptV1 {
	protocol: "case-write-receipt/v1";
	operationId: string;
	requestDigest: string;
	receiptSequence: string;
	outcome: "pending" | "terminal";
	phase?: "admitted" | "materializing" | "reconciling" | "quarantined";
	disposition?:
		| "applied"
		| "satisfied_without_change"
		| "conflict"
		| "rejected"
		| "not_authorized"
		| "grant_unavailable"
		| "contract_not_served"
		| "cancelled_before_dispatch";
	caseId: string;
	expectedCaseRevision: string;
	observedCaseRevision?: string;
	resultingCaseRevision?: string;
	fenceEvidence?: {
		authorizationRevision: string;
		policyRevision: string;
		grantRevision: string;
		lifecycleRevision: string;
		evaluatedAt: string;
	};
	effect?: {
		effectReference: string;
		relationKind: "object";
		resourceId: string;
	};
	projectionProof?: ProjectionInclusionProofV1;
	createdAt: string;
	updatedAt: string;
	statusRetainedUntil?: string;
	statusLookup: string;
}
```

`receiptSequence` is a canonical unsigned base-10 integer string, with no leading zero except the value `"0"`. Receivers compare it numerically with arbitrary precision, never lexicographically or through an IEEE-754 JSON number. `statusRetainedUntil` is absent for unresolved receipts because they cannot expire.

The submit transport returns:

- `200 OK` with the existing current/terminal receipt for an admitted operation;
- `201 Created` when the operation resource and a terminal result are created synchronously;
- `202 Accepted` only with a durable pending receipt and status URI;
- `400`/`422` Problem Details for malformed or semantically invalid envelopes that provably did not dispatch;
- `401` when the channel is not authenticated;
- `403` when the caller may not submit or view the named operation, without leaking Case or effect existence. A principal allowed to see the operation but denied the capability can instead receive its admitted terminal `not_authorized` receipt;
- `409` for `identity_digest_mismatch` or other integrity conflict; this is distinct from a terminal Case-revision `conflict` receipt already bound to the admitted identity;
- `503`/`504` only as transport/service status. After a request might have reached admission, the client treats these as outcome-unknown and uses the original identity.

All problem bodies use stable RFC 9457 `type` URIs and machine fields. Human `detail` is never parsed for behavior and must not reveal hidden resources, current revisions, policy rules, or membership.

### 3.3 Receipt state machine

Allowed transitions are closed:

```text
absent
  -> pending/admitted

pending/admitted
  -> pending/materializing
  -> pending/reconciling
  -> pending/quarantined
  -> terminal/*

pending/materializing
  -> pending/reconciling
  -> pending/quarantined
  -> terminal/*

pending/reconciling
  -> pending/quarantined
  -> terminal/*

pending/quarantined
  -> terminal/* only after authoritative or human-audited proof

terminal/X
  -> terminal/X only
```

Additional invariants:

- `phase` is present only when `outcome` is `pending`; `disposition` is present only when `outcome` is `terminal`;
- every stored transition atomically increments `receiptSequence`;
- terminal receipts are immutable except for separately versioned, non-semantic disclosure metadata;
- `applied` carries `resultingCaseRevision` and stable `effectReference`;
- `satisfied_without_change` reports the unchanged observed/resulting revision and the already-existing stable predicate;
- every other terminal disposition is authoritative no-effect proof for this operation identity;
- `quarantined` remains pending/outcome-unresolved and retains its Effect Reservation; it is not a disguised terminal failure;
- a late transport response is evidence submitted to the facade state machine, not a client-owned state transition; and
- a terminal receipt can remain terminal even if a later Case operation removes or supersedes the effect.

An exact replay does not re-evaluate the historical effect or rewrite its fences. It returns the stored receipt only if the caller is currently allowed to see it. Current authorization can hide a receipt or Projection proof, but it cannot change an `applied` disposition to `not_authorized` or a terminal receipt back to pending.

### 3.4 Status lookup and negative results

`GetCaseOperationStatus(tenant, caseId, operationId)` must be linearizable with the ledger authority and reauthorize the caller for the current purpose. An internal reconciliation principal can resolve an operation after end-user access is revoked, but user-visible status remains current-authorized and non-leaking.

Status results are:

- current receipt;
- `403 status_not_visible`, which discloses no effect details;
- `404 unknown_identity`, meaning only that no retained/tombstoned identity is visible at that lookup boundary; it is **not** no-effect proof for a concurrently arriving or never-admitted request;
- `410 receipt_details_expired` with a retained identity/digest/terminal summary tombstone when full details have expired; or
- integrity failure if storage returns duplicate identities, a changed digest, regressing sequence, or contradictory terminal state.

After a timeout, the coordinator should re-submit the exact request under the original identity rather than interpret 404. The unique ledger row arbitrates a race between the original attempt and retry. Re-submission must not manufacture a fresh expected revision or new identity; if the original request never admitted and the bound fences are now stale, it terminates with the appropriate no-effect receipt.

### 3.5 Retention obligations

Retention is a correctness contract, not merely an operations setting:

1. **Unresolved receipts, original request bytes/digest inputs, Effect Reservation, and reconciliation evidence are retained without automatic expiry until terminal resolution or an explicit audited migration.**
2. Full terminal receipts are retained until at least:

   ```text
   max(
     Workspace operation-journal replay horizon,
     maximum client retry/offline horizon,
     Case audit and legal-retention horizon,
     Projection/event reconciliation horizon,
     maximum supported old-contract decoder horizon
   ) + clock/skew/operations safety margin
   ```

3. Every response publishes the absolute `statusRetainedUntil` derived from the active policy. An Adapter cannot qualify with an unspecified or shorter retention window.
4. After full-detail expiry, a minimal tombstone retains tenant, operation identity, request digest, terminal disposition, resulting Case revision/effect reference hashes as disclosure policy permits, contract decoder identity, and expiry reason. The tombstone must outlive every permitted replay of the operation identity.
5. Operation identities are never reused. If the deployment cannot guarantee the tombstone/replay relationship, it must retain the identity/digest binding for the Case audit lifetime.
6. Purge must not turn a known terminal receipt into 404. `410 receipt_details_expired` is explicit, and never authorizes a new effect identity for the old intent.

This formula is intentionally stricter than Kubernetes watch retention: a trimmed watch can be rebuilt by relisting, whereas a lost idempotency record can cause a duplicate effect. The deployment still must choose and publish concrete durations before qualification; source facts do not justify inventing one universal number here.

## 4. Transaction ownership arrangements

### 4.1 Option A — database-owned Case command state and outbox

#### Ownership

Case Management PostgreSQL is authoritative for the first-slice Case coordination head and neutral Resource Reference membership. For one `CaseRevision` to fence the whole admitted Case Projection, every mutable Case semantic block covered by that revision must also advance the same coordination head. OpenCTI is an asynchronously materialized/read view for this capability, not a second independently writable authority. All human and automated writers whose effects fall inside that Case partition use the same facade or the same underlying authority transaction.

If the deployment leaves a Case field independently writable in OpenCTI, it must either exclude that field from the declared `CaseRevision` dependency domain and give it a separate authoritative version, or provide an underlying atomic integration that advances the Case head with the write. Eventual event ingestion or a later digest comparison cannot close the commit-time CAS gap. Option A is not qualified while an admitted Case Projection block can change without participating in one of those mechanisms.

Minimum logical tables:

```text
case_head(
  tenant_id, case_id, revision,
  primary key (tenant_id, case_id)
)

case_resource_reference(
  tenant_id, case_id, resource_id, resource_version,
  created_by_operation_id,
  unique (tenant_id, case_id, resource_id)
)

case_operation(
  tenant_id, operation_id, request_digest,
  contract_id, contract_version, original_request,
  outcome, phase, disposition, receipt_sequence,
  expected_revision, observed_revision, resulting_revision,
  effect_reference, fence_evidence,
  created_at, updated_at, retained_until,
  primary key (tenant_id, operation_id)
)

case_outbox(
  tenant_id, event_id, case_id, case_revision,
  operation_id, event_kind, canonical_payload,
  delivery_state, attempt_evidence,
  unique (tenant_id, event_id),
  unique (tenant_id, operation_id, event_kind)
)
```

#### Authority transaction

Within one short PostgreSQL transaction:

1. insert or retrieve the unique operation identity;
2. reject a stored digest mismatch without changing the row;
3. lock the `case_head` row or execute the equivalent serializable protocol;
4. load and validate current authorization, policy, Grant, and lifecycle fence records from the same transactional authority, or atomically consume a qualification-approved single-operation decision reservation;
5. compare exact expected/current CaseRevision;
6. validate the neutral reference and current resource version/access;
7. insert the reference, or classify the exact predicate as `satisfied_without_change`;
8. for a new effect, advance CaseRevision exactly once;
9. store the terminal receipt and an outbox event; and
10. commit all changes together.

Serialization/deadlock failures abort the transaction and are retried internally under the same identity/digest. They are not reported as a Case conflict unless a new committed transaction observes a true revision mismatch.

If a fence authority is remote, a plain current read is insufficient. Qualification must prove a reservation/conditional-write protocol that orders the effect against concurrent revocation. Otherwise the capability remains disabled even though CaseRevision and idempotency are locally correct.

#### Crash windows

| Crash/timeout point | Durable fact | Recovery |
|---|---|---|
| before transaction begins | no ledger, no effect | exact resubmission may admit |
| after identity insert but before commit | transaction invisible/rolled back | exact resubmission arbitrates normally |
| after commit before response | terminal receipt, Case effect, revision, outbox all durable | status/re-submit returns same terminal receipt |
| after outbox claim before OpenCTI call | authoritative effect already applied; materialization pending | reclaim outbox item and retry materialization |
| OpenCTI applied, acknowledgement lost | authoritative effect remains applied; read model outcome uncertain | reconcile the neutral predicate and mark outbox delivery without changing Case receipt |
| projection refresh before read model catches up | terminal applied receipt but no inclusion proof | return `accepted_but_unsynchronized`; retry read only |
| process crashes after proof generation but before Workspace install | proof/Projection candidate not locally installed | recover receipt, obtain a fresh currently authorized Projection, reinstall atomically |

#### Strengths and costs

- It gives a real linearization point and atomic receipt without distributed two-phase commit with OpenCTI.
- It cleanly distinguishes authoritative acceptance from read-model synchronization.
- It needs ownership and migration of the first-slice Case mutation path; OpenCTI UI/integrations must route through Case Management or become read-only for this partition.
- OpenCTI materialization can lag, so the Workspace must preserve `accepted_but_unsynchronized` as a first-class state.

### 4.2 Option B — exclusive all-writer coordinator over OpenCTI

#### Ownership

OpenCTI remains the semantic Case owner. The facade owns a durable shadow CaseRevision, identity/digest ledger, per-Case Effect Reservation, and receipt. Every path capable of changing the relevant Case partition is forced through the facade. The first version permits only the additive neutral `(case, "object", resource)` predicate.

#### Coordinated flow

1. In a local transaction, admit identity/digest, lock the shadow Case head, validate current fences and expected shadow revision, create `pending/admitted`, and reserve the Case/effect domain.
2. A durable worker claims the reservation. Claims use a monotonically increasing fencing generation in local storage; a worker never blindly re-dispatches merely because an older lease elapsed.
3. Immediately before remote dispatch, revalidate authorization, policy, Grant, lifecycle, resource access/version, shadow revision, and absence of bypass-writer evidence.
4. Inspect the current neutral predicate. If it already exists before dispatch, terminate `satisfied_without_change` without mutation.
5. Dispatch exactly one OpenCTI `relationAdd` attempt while the reservation excludes other Case mutation attempts.
6. On a complete valid response, re-read the authorized predicate, then atomically advance shadow CaseRevision and store terminal `applied`.
7. On timeout, connection loss, malformed response, or process crash, move forward to `pending/reconciling`; retain the reservation and do not send a second mutation.
8. Reconciliation uses current authorized reads, stream/history evidence when available, the exclusive ledger, and the unique predicate. Presence can resolve `applied` only if the facade can prove no earlier/bypass writer created it after preflight. Absence can resolve no-effect only after the qualified remote consistency window and proof that the original request cannot still commit.
9. If attribution or absence cannot be proven, remain pending or quarantine. Do not advance the shadow revision, release the effect reservation, or label failure.

#### Crash windows and limitations

| Window | Required behavior |
|---|---|
| crash after pending commit, before dispatch | claimant proves no dispatch, revalidates all fences, then may dispatch once |
| crash while request can still be in flight | successor reconciles; it cannot use lease expiry as no-effect proof |
| remote commit, lost response | presence plus exclusive single-writer evidence can resolve applied |
| remote response, local terminal commit fails | reconcile under same identity; never create a second identity |
| bypass writer changes Case | shadow revision loses authority; quarantine affected Case-head chain and disable strict writes |
| authorization revoked after dispatch | internal reconciliation continues; end-user status/projection follows current disclosure policy |
| history/stream cursor trimmed | full current predicate rebase; event absence is not no-effect proof |

This arrangement cannot support arbitrary Note creation, non-idempotent edits, semantic relationship creation, or multi-object mutations merely by reusing the same wrapper. Those effects can be indistinguishable after an unknown outcome. Each would need its own proven effect identity/predicate or an upgraded underlying atomic API.

### 4.3 Comparison and recommendation

| Property | Option A: DB command authority | Option B: exclusive remote coordinator |
|---|---|---|
| authoritative CaseRevision | native Case transaction | facade shadow, valid only while no bypass exists |
| identity/receipt atomic with authority effect | yes | no; reconciled across local/remote boundary |
| timeout after remote commit | receipt already terminal; only materialization unknown | operation outcome unknown until reconciliation |
| write concurrency | serialized only for short Case transaction | relevant Case writes can remain blocked for entire unknown window |
| effect attribution | operation row and Case row commit together | relies on unique predicate plus exclusive all-writer history |
| OpenCTI UI/integration constraint | must use facade for owned mutation partition | must use facade for every relevant writer, with stricter runtime enforcement |
| supported first effect | neutral Resource Reference; extensible transactionally | only qualified uniquely reconcilable effects |
| operational failure mode | read-model lag | long-lived reservation/quarantine and shadow-authority loss |

**Recommendation:** implement Option A for the production first vertical slice. It makes Case Management's promised `CaseRevision`, receipt, and no-effect dispositions true by construction. Use Option B only as an explicitly capability-scoped transitional Adapter for neutral Resource Reference addition after proving all-writer enforcement and remote reconciliation. Never advertise Option B as a general Case-write contract.

## 5. Effect-in-Projection proof

The facade exposes an actor-authorized read such as:

```typescript
interface ProjectionInclusionProofV1 {
	protocol: "case-projection-inclusion-proof/v1";
	caseId: string;
	profileId: string;
	profileVersion: string;
	profileDigest: string;
	caseRevision: string;
	authorizationRevision: string;
	policyRevision: string;
	semanticProjectionDigest: string;
	effectReference: string;
	inclusion: "present" | "superseded_or_removed";
	observedAt: string;
}
```

Proof obligations:

1. It is generated from one complete, current actor/tenant/purpose-authorized Projection under a qualified Profile; it is not copied from mutation response data.
2. `caseRevision` is equal to or newer than the receipt's `resultingCaseRevision` under authority-owned comparison. Clients do not compare opaque revisions themselves; the facade validates `atLeastRevision`.
3. The semantic Projection digest binds the explicit Resource Reference block/envelope and all required Profile block states.
4. `effectReference` is the stable facade identity for the neutral membership, not an inferred text match.
5. A current proof can report `superseded_or_removed` after a later authoritative change. That does not rewrite the historical applied receipt.
6. A proof is withheld if current authorization no longer permits the Case/effect. An internal worker can still finish materialization and receipt reconciliation without disclosing content to the former user.
7. Option A distinguishes three states: authoritative `applied`, OpenCTI materialization delivered, and current Projection inclusion proven. Only the last permits the Workspace to publish a synchronized updated Case Projection.

## 6. Error taxonomy

| Code | Point | Effect meaning | Retry rule |
|---|---|---|---|
| `request_invalid` | before admission | definitely not dispatched | correct request; new semantic intent gets new identity |
| `authentication_failed` | before admission | definitely not dispatched | reauthenticate; do not claim original identity was admitted |
| `identity_digest_mismatch` | admission | original identity unchanged; second intent not dispatched | permanent integrity error; never alter/reuse identity |
| `contract_unsupported` | before dispatch | no effect | deploy compatible contract; old intent remains pinned |
| `case_revision_conflict` | fenced authority transaction | terminal no-effect receipt | refresh/rebase; any newly approved intent gets a new identity |
| `not_authorized` | fenced authority transaction | terminal no-effect receipt | no automatic retry; current policy controls disclosure |
| `grant_unavailable` | fenced authority transaction | terminal no-effect receipt | no automatic retry under altered semantics |
| `contract_not_served` | lifecycle fence | terminal no-effect receipt | do not reinterpret under replacement contract |
| `serialization_retry` | internal DB attempt | transaction aborted; no newly committed effect | facade retries internally under same identity/digest |
| `transport_timeout` | transport | unknown unless pre-admission is proven | status/exact resubmit under original identity only |
| `remote_outcome_unknown` | after possible remote dispatch | pending, effect reservation retained | reconcile; never blind retry or return rejected |
| `receipt_integrity_failure` | any merge/recovery | unknown or contradictory | quarantine only intersecting effect/dependency chain |
| `projection_not_synchronized` | after applied receipt | authoritative effect applied, current Projection not proven | retry authorized Projection read; never repeat write |
| `status_not_visible` | lookup | no disclosed outcome meaning | internal reconciliation may continue |
| `receipt_details_expired` | lookup after full retention | terminal summary/tombstone remains | never reuse identity or infer permission to repeat effect |

Domain dispositions are carried by the receipt, not inferred solely from HTTP status. In particular, a lost `200`, `201`, or `202` response is still an unknown transport outcome until the receipt is recovered.

## 7. Qualification and conformance obligations

An Adapter can advertise strict R1 only if all applicable cases pass against the production arrangement and the in-memory implementation:

### Identity and atomicity

1. Concurrent same-identity/same-digest submissions produce one logical effect and one monotonic receipt.
2. Same identity/different digest is always rejected without changing the original ledger row or effect.
3. A crash before ledger commit cannot dispatch an effect.
4. A crash after authority commit but before response recovers the same terminal receipt.
5. Unique constraints, not only application checks or advisory locks, arbitrate identity races.
6. Database serialization/deadlock retries remain internal and do not create a second operation identity.

### Revision and writer ownership

7. Two writers using the same expected CaseRevision cannot both commit distinct Case changes.
8. A successful semantic mutation advances CaseRevision exactly once; replay/no-op does not.
9. Human UI, bulk import, integration, administrator, and migration writers all participate in the same Case head or are denied write access.
10. Simulated bypass writes are detected and disable/quarantine the strict capability rather than silently re-anchoring the shadow revision.
11. A timestamp, OpenCTI cursor, stream offset, entity ID, or projection digest is rejected as CaseRevision evidence.

### Fences

12. Authorization, policy, Grant, or lifecycle change before the linearization fence prevents dispatch/commit and produces the correct no-effect receipt.
13. Change after possible dispatch does not cause a new identity or blind retry; the original operation is reconciled.
14. The authenticated principal/delegation must match the digest-bound principal and purpose.
15. A resource version/access change before commit blocks the stale neutral reference intent.
16. Current authorization controls every status and Projection-proof disclosure, including after a terminal applied receipt.
17. A concurrent revocation race is serialized by co-transactional fence state, a single-operation decision reservation, or underlying atomic validation; a preflight read alone fails conformance.

### Receipts and recovery

18. Duplicate and out-of-order evidence cannot regress a receipt sequence or pending phase.
19. A terminal receipt never changes disposition; contradictory evidence triggers integrity quarantine.
20. Every 202 response references a durable status resource; process restart does not lose it.
21. Timeout at every enumerated crash window resolves through status/reconciliation under the same identity.
22. A 404 lookup is never treated as proof that an in-flight submit had no effect.
23. Unresolved records do not expire, release their Effect Reservation, or become ordinary failures.
24. Full-receipt expiry yields an explicit tombstone/410 path; it cannot permit identity reuse.
25. Old contract versions and decoders can still validate retained original requests and receipts.

### Remote materialization and Projection

26. Option A retries OpenCTI materialization without changing the authoritative receipt or CaseRevision.
27. Lost OpenCTI acknowledgement after materialization is reconciled using the neutral predicate; it does not duplicate the relationship.
28. `applied` without a current inclusion proof returns `accepted_but_unsynchronized` to the Workspace.
29. Projection inclusion proof binds exact profile/digest, current authorization/policy, CaseRevision, semantic Projection digest, and stable effect reference.
30. Later removal/supersession changes current Projection proof but not the historical applied receipt.
31. Stream/history gaps force an affected-partition rebase; absence of an event never proves no effect.

### Option B additional gates

32. At most one possibly dispatched mutation can intersect the reserved first-slice Case/effect domain.
33. Worker lease expiry alone never authorizes redispatch.
34. Predicate presence is attributed to the operation only when exclusive preflight/history evidence rules out a pre-existing or bypass effect.
35. Predicate absence becomes terminal no-effect only after the qualified consistency/in-flight window and authoritative proof; a single read is insufficient.
36. Losing all-writer enforcement immediately removes R1 from Adapter qualification while leaving independent read-only capabilities available.
37. No capability other than the explicitly proven neutral Resource Reference is inferred conformant from this predicate-based reconciliation.

## 8. Rejected shortcuts

### "Use `If-Match` and no ledger"

Rejected. The precondition prevents an effect against the wrong current representation, but it does not remember caller identity, return a durable asynchronous receipt, or resolve a lost response.

### "A local receipt table around stock OpenCTI is enough"

Rejected. The local receipt and remote mutation do not commit atomically. Other OpenCTI writers can change the Case without advancing the facade revision, and a crash between remote commit and receipt commit remains unattributed.

### "A process/distributed lock establishes all-writer serialization"

Rejected. Locks coordinate only participants that honor them. PostgreSQL explicitly describes advisory locks as application-enforced. Qualification needs enforced writer routing plus a durable ledger, not a convention.

### "A 202 or successful GraphQL response is the terminal receipt"

Rejected. RFC 9110 makes 202 noncommittal, and stock OpenCTI returns an entity/relation rather than a retained identity-bound status resource.

### "If the relation is present, this request created it"

Rejected. Presence proves current predicate existence, not causal identity. Causal attribution needs Option A's authority transaction or Option B's preflight plus exclusive all-writer ledger.

### "If the relation is absent, retry with a new identity"

Rejected. The original call might still commit, the read might be stale/unauthorized, or the relation might have been created then removed. Preserve the original identity and reconcile.

### "Expire unresolved receipts on the normal cache TTL"

Rejected. Expiry destroys the information needed to prevent a duplicate effect. Unresolved records and reservations need indefinite retention until authoritative resolution or audited migration.

### "Freeze the Workspace while a write is unknown"

Rejected. The facade reports the exact Case-head/effect partition and operation identity. The Workspace freezes only operations whose declared inputs, outputs, or possible effects intersect that partition. Independent I&E reads and unrelated Case/resource chains continue subject to their own authority and freshness fences.

## 9. Direct design implications

1. `CaseRevision` must be owned by the Case Management authority and must not be reverse-engineered from stock OpenCTI.
2. The first production R1 should remain the neutral Resource Reference mapped to OpenCTI Container `object` membership. Note creation stays disabled until it has an equally strong identity/effect protocol.
3. Production should prefer database-owned command authority plus outbox. It minimizes unknown write outcomes and keeps OpenCTI lag out of the authority transaction.
4. The operation identity/digest record, Case effect, revision advance, terminal receipt, and outbox event belong to one transaction in Option A.
5. Authorization, policy, Grant, and lifecycle are independent current fences. Historical/bounded-stale data modes never relax them.
6. Receipt acceptance and Projection synchronization remain separate facts. The Workspace publishes a new Case context only after a current authorized inclusion proof.
7. Adapter qualification must advertise writer-ownership arrangement, revision authority, transaction isolation/locking strategy, digest profile, receipt state machine/version, lookup consistency, retention/tombstone policy, projection-proof version, and conformance-suite result.
8. A deployment lacking either Option A authority ownership or Option B enforceable all-writer/reconciliation guarantees exposes read-only Case Projection and disables strict R1 without freezing the rest of the Workspace.

## Primary sources

- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)
- [RFC 6585: Additional HTTP Status Codes](https://www.rfc-editor.org/rfc/rfc6585.html)
- [RFC 9457: Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html)
- [PostgreSQL: Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [PostgreSQL: Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [PostgreSQL: Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [PostgreSQL: Unique Indexes](https://www.postgresql.org/docs/current/indexes-unique.html)
- [PostgreSQL: `INSERT ... ON CONFLICT`](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)
- [Kubernetes API Concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/)
- [Amazon EC2 API idempotency](https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html)
- [OpenCTI Case schema at audited commit](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case.graphql)
- [OpenCTI Container mutations at audited commit](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L16193-L16203)
- [OpenCTI reference-relation add flow at audited commit](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/domain/stixObjectOrStixRelationship.ts#L51-L71)
