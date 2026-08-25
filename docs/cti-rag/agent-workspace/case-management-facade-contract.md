# Case Management Facade Command and Receipt Contract

Status: Accepted and frozen strict-R1 target contract; not a current Orientation-cycle dependency.

This document defines the remote-owned port that gives Case proposals real concurrency, authorization, idempotency, receipt, and Projection-inclusion semantics. It does not fix model-visible tool count, HTTP framework, or physical table names.

`RevisionAuthorityRef` and `AuthorityRevision` are the canonical shared types from [`opencti-case-projection/v1` Contract](projection-profile-v1-contract.md); generated artifacts reference their schema IDs rather than duplicating structurally similar definitions.

## 1. Decision and ownership

The production design is an owned Case Management command authority backed by a transactional system of record. For the first vertical slice, one transaction owns:

- the Case head and its Revision Authority;
- neutral Case-to-Resource membership;
- immutable operation identity and request digest;
- one immutable terminal receipt per committed operation identity;
- the independent proposal-ledger head;
- current authorization, policy, Grant, contract-lifecycle decision evidence; and
- an outbox record that materializes the accepted state into OpenCTI.

OpenCTI remains the graph/search/read integration target, but for this slice the accepted neutral membership is materialized into its Case `object` collection after the authoritative Case transaction. OpenCTI entity presence is not the receipt authority.

A shadow coordinator around stock OpenCTI is permitted only as a separately qualified transitional Adapter when every writer for the exact Case partition routes through it and the underlying mutation is a neutral, uniquely testable predicate. It cannot claim the production contract for Notes, arbitrary graph mutations, bypassable writers, or effects whose identity cannot be proved.

PostgreSQL is the reference production Adapter because the contract requires unique constraints, row or serializable concurrency, atomic ledger/head/effect/outbox commit, durable acknowledgment, and restart-safe reconciliation. The public Module remains storage-agnostic.

### Case Command Authority

**Problem solved:** a proxy that forwards unrelated reads and writes cannot make one authoritative concurrency and receipt decision.

**Inputs:** one stable Revision Authority/Case partition, all mutation paths in its declared revision domain, current decision fences, and exact operation identities.

**Output:** one serialized Case head plus durable authoritative membership, decision, receipt, and materialization work.

**Boundary:** the authority owns command semantics and the state in its declared revision domain. It does not own OpenCTI's general graph model, I&E source truth, Workspace artifacts, or model-tool decomposition.

**Failure behavior:** if any covered writer bypasses its serialization point, if a covered block changes without advancing its head, or if acknowledged command state can be lost, the activation is quarantined and strict writes stop for that authority partition.

## 2. Revision Authority coverage

**Problem solved:** expected-revision checks are fictitious if a mutable semantic block can change without advancing the checked head.

**Inputs:** authority identity, Case partition, declared covered blocks, and all mutation paths.

**Output:** a Case head whose revision advances exactly once for each newly applied semantic change in its domain.

**Boundary:** any state independently writable in OpenCTI is excluded from this head unless its write path atomically advances the same authority. Event ingestion or digest comparison after an external write can detect drift but cannot retroactively close the compare-and-set window.

**Failure behavior:** discovery of a bypass writer, uncovered semantic state, or possible acknowledged-commit loss quarantines the write activation. It widens suspension to the smallest authority partition whose concurrency is no longer trustworthy, not the whole Workspace.

The facade accepts only a Projection basis produced by its own `RevisionAuthorityRef`. A direct or synthetic OpenCTI revision, even with the same token text, is rejected.

### Proposal Ledger Revision

**Problem solved:** terminal no-effect and already-satisfied decisions change actor-visible proposal history without changing Case semantics, so using only Case Revision would either leave proposal status unfenced or falsely report a Case change.

**Inputs:** one Revision Authority/Case partition, its current proposal-ledger head, and a newly committed terminal operation identity and receipt.

**Output:** one opaque `proposalLedgerRevision` that advances exactly once for each new terminal ledger row and is returned in that row's receipt and recovery proof.

**Boundary:** the token versions proposal identity/disposition visibility, not Case semantic state or OpenCTI materialization. It is meaningful only in its authority, ledger-contract, and Case tuple; no ordering or equality is inferred across authorities. Duplicate identity/digest lookup returns the original token and does not advance the head.

**Failure behavior:** inability to commit the ledger row, head advancement, receipt, and any Case/effect/outbox changes atomically returns no acknowledged decision. A duplicate that advances again, a receipt missing its resulting ledger revision, or a bypass writer is a conformance failure and quarantines the affected command authority partition.

## 3. Command request

**Problem solved:** retries, late replies, and crashes need a stable identity for one exact intent, with every security and concurrency fence chosen by trusted code.

**Inputs:** trusted Workspace/activation binding, current authority revision, current authorization/policy/Grant/lifecycle revisions, the neutral Resource/version selected by the user/model workflow, and a new operation identity.

**Output:** one immutable `SubmitCaseOperationV1` request and its canonical request digest.

**Boundary:** the model supplies only the business choice of an already-authorized Working Set Resource. It cannot choose authority, expected revision, actor, purpose, policy, Grant, effect domain, operation identity, digest, or relation kind. The first Capability creates only neutral membership.

**Failure behavior:** unknown fields, unserved contracts, invalid canonical JSON, digest mismatch, reused identity with another digest, or an untrusted field supplied by model payload fail before effect dispatch.

```typescript
interface FacadeEffectBindingV1 {
	operationId: string;
	effectId: string;
	idempotencyKey: string;
	requestDigest: string;
	authority: RevisionAuthorityRef;
}

interface ResourceUsePermitV1 {
	protocol: "ie-resource-use-permit/v1";
	issuerAuthorityId: string;
	verifierContractDigest: string;
	signingKeyId: string;
	permitId: string;
	permitDigest: string;
	signature: string;
	operationId: string;
	effectId: string;
	actorId: string;
	purpose: string;
	caseId: string;
	targetAuthorityId: string;
	resourceRef: string;
	resourceVersion: string;
	use: "neutral_case_reference";
	decision: "reserved_for_operation";
	issuedAt: string;
	expiresAt: string;
}

interface SubmitCaseOperationV1 {
	protocol: "case-write-facade/v1";
	operationId: string;
	effectId: string;
	idempotencyKey: string;
	requestDigest: string;
	principal: {
		actorId: string;
		purpose: string;
		authenticationContextId: string;
	};
	contract: {
		capabilityId: "link_intelligence_resource";
		capabilityVersion: "1";
		capabilityManifestDigest: string;
		catalogDigest: string;
		activationDigest: string;
	};
	target: {
		authority: RevisionAuthorityRef;
		expectedRevision: string;
		expectedAuthorizationRevision: string;
		expectedPolicyRevision: string;
		expectedGrantRevision: string;
		expectedLifecycleRevision: string;
	};
	payload: {
		resourceRef: string;
		resourceVersion: string;
		relation: "neutral_case_object_membership";
		membershipKey: string;
		resourceUsePermit: ResourceUsePermitV1;
	};
}
```

`requestDigest` uses `cti-jcs-sha256/v1` over all normalized semantic request fields except `requestDigest` itself. It includes `protocol`, operation/effect/idempotency identity, principal, contract, target authority and fences, and payload. A replay must be byte-semantically identical after closed-schema normalization.

### Facade Effect Binding

**Problem solved:** different local and remote names for operation, effect, lookup, and digest make it impossible to prove a receipt belongs to the dispatched intent.

**Inputs:** Workspace operation ID, its one first-slice remote effect ID, facade idempotency key, canonical request digest, and Revision Authority.

**Output:** one closed `FacadeEffectBindingV1` persisted unchanged in local Effect Intent, facade ledger, lookup, receipt, protected recovery proof, and Projection inclusion proof.

**Boundary:** `operationId` identifies the whole Workspace operation, `effectId` its one first-slice remote effect, and `idempotencyKey` the facade deduplication namespace. The first slice admits exactly one remote effect per R1 operation. The binding does not carry mutable receipt or synchronization state.

**Failure behavior:** any field mismatch, same identity with another digest, missing authority, or regenerated identity rejects merge/dispatch and raises an integrity incident. Retry and recovery use the exact original binding.

### Resource-use decision reservation

**Problem solved:** Case Management cannot atomically re-read I&E authorization and Resource version inside its own database transaction, so an ordinary preflight leaves a cross-system TOCTOU gap.

**Inputs:** I&E current actor permission, Resource identity/version/status, Case/purpose, operation/effect identity, intended neutral-reference use, and bounded expiry.

**Output:** one I&E-owned `ResourceUsePermitV1` bound to the exact operation/effect and consumable once by the Case command decision.

**Boundary:** permit issuance is the I&E Resource access/version linearization point. The permit is irrevocable for its exact binding until `expiresAt`; revocation prevents new permits but does not cancel one already issued. `permitDigest` is SHA-256 over JCS of every normalized permit field except `permitDigest` and `signature`; `signature` authenticates that digest under the qualified issuer/verifier contract and signing key. The target authority validates authenticity and time, then inserts the unique `(issuerAuthorityId, permitId, permitDigest, operationId, effectId)` consumption binding in the same PostgreSQL transaction as the Case decision. I&E performs no remote consume/cancel call, so there is no cross-database commit gap. A bearer token, cached permission, revocable assertion, or read-before-write check is not a permit.

**Failure behavior:** invalid signature/verifier, field or target mismatch, first decision after expiry, or the same permit ID/digest bound to another operation/effect produces terminal no-effect or an integrity conflict. Same permit and same effect binding is idempotent. Case transaction rollback rolls back the local consumption binding; unknown commit acknowledgment is resolved through the facade operation/permit ledger. It never falls back to the stale Working Set observation.

## 4. Admission and atomic decision

**Problem solved:** a successful authorization preflight followed by a later write leaves a permission-revocation and concurrency TOCTOU gap.

**Inputs:** a valid request, current facade state, and a transaction capable of serializing the Case head.

**Output:** an existing matching receipt, a new terminal no-effect receipt, or one atomic applied/satisfied result with outbox work. Every newly committed terminal ledger row advances `proposalLedgerRevision` exactly once; duplicate lookup/replay does not.

**Boundary:** facade-owned authorization, policy, Grant, lifecycle, expected revision, and membership predicate are evaluated in the Case transaction. I&E-owned Resource access/version is represented by the operation-bound `ResourceUsePermitV1`, whose issuance/reservation is its owner's linearization point and whose identity/digest/expiry/consumption are validated in the transaction. A read-only preflight, cached token, or external observation without a qualified reservation is insufficient.

**Failure behavior:** serialization failure retries only inside the facade using the same identity/digest. Any fence failure records a terminal no-effect disposition. Loss of the transaction acknowledgment is resolved by authoritative identity/digest lookup before any replay.

Reference transaction:

1. Parse closed schema and recompute the digest.
2. Look up the immutable `(authorityId, caseId, operationId, idempotencyKey)` ledger identity.
3. If it exists with another digest, return an integrity error and quarantine that identity; never execute.
4. If it exists with the same digest, do not re-execute or change disposition. Separately evaluate current receipt-disclosure authority: return the full receipt only to a currently authorized business caller, the minimum protected proof only to the recovery principal, or a safe denial that reveals no newly forbidden fields.
5. Lock the Case head or run at a qualified serializable isolation level.
6. Evaluate current facade-owned authorization, policy, Grant, Capability lifecycle, and expected revision; validate and consume the exact I&E Resource-use reservation for this operation/effect.
7. If the canonical membership already exists, record terminal `satisfied_without_change`; keep the same Case revision and create no new effect/outbox record.
8. Otherwise insert the authoritative neutral membership, advance the Case revision exactly once, record terminal `applied`, and insert the materialization outbox record.
9. For every new terminal disposition, advance the independent proposal-ledger revision once and place the resulting value in the receipt; a duplicate existing identity returns its original value without advancing.
10. Commit ledger/receipt and any Case/effect/outbox change together with durability strong enough to survive the declared failover envelope.

A committed command does not remain in a facade pending state during remote OpenCTI materialization. The Case Management transaction returns one terminal disposition; materialization state is a separate synchronization axis.

Current-fence ownership is fixed for the first slice:

| Fence | Linearization mechanism |
|---|---|
| Case Revision, facade authorization/policy, Capability Grant/lifecycle, canonical membership | facade PostgreSQL transaction under the locked Case head |
| I&E Resource identity/version/status and actor permission to use it for this operation | irrevocable-until-expiry I&E-issued `ResourceUsePermitV1`; facade validates signature/time and binds consumption locally in the Case transaction |
| OpenCTI object/materialization observations | Projection read dependency only; never used as facade CAS or as a substitute for the Resource permit |

If either owner cannot provide the stated mechanism, R1 is not served. The implementation cannot replace it with a preflight query.

## 5. Receipt and status

**Problem solved:** transport success/failure cannot distinguish remote commit, authoritative no effect, or a lost response.

**Inputs:** authoritative operation ledger, decision evidence, Case head, effect record, and materialization/proof state.

**Output:** one terminal `CaseOperationReceiptV1` for a currently authorized business caller, one `ReceiptRecoveryProofV1` for the protected recovery principal, or a retained `gone` tombstone after proof retention. An unknown/missing transport response is not a facade business status.

**Boundary:** a receipt proves command disposition. It does not by itself prove that the current actor still has permission or that the current OpenCTI-backed Projection contains the effect. Those are separate live authorization and Projection-inclusion proofs.

**Failure behavior:** timeout, disconnect, 404, missing event, or missing OpenCTI entity never becomes no-effect proof. The caller retains `queryable_unknown` and retries lookup/replay with the identical binding. Contradictory terminal data is an integrity incident.

```typescript
type TerminalDispositionV1 =
	| "applied"
	| "satisfied_without_change"
	| "conflict"
	| "rejected"
	| "not_authorized"
	| "grant_unavailable"
	| "contract_not_served";

type ReceiptIssueCodeV1 =
	| "payload_invalid"
	| "resource_permit_invalid"
	| "resource_permit_expired"
	| "resource_permit_mismatch"
	| "business_rule_failed"
	| "approval_missing";

interface ReceiptIssueV1 {
	code: ReceiptIssueCodeV1;
	field?: string;
}

interface ReceiptEvidenceV1 {
	evaluatedAuthorizationRevision: string;
	evaluatedPolicyRevision: string;
	evaluatedGrantRevision: string;
	evaluatedLifecycleRevision: string;
	evaluatedAt: string;
}

interface CaseOperationReceiptV1 {
	protocol: "case-write-receipt/v1";
	receiptId: string;
	operationId: string;
	effectId: string;
	idempotencyKey: string;
	requestDigest: string;
	authority: RevisionAuthorityRef;
	baseRevision: string;
	disposition: TerminalDispositionV1;
	resultingProposalLedgerRevision: string;
	resultingRevision?: string;
	effectReference?: string;
	membershipKey?: string;
	issues: readonly ReceiptIssueV1[];
	evidence: ReceiptEvidenceV1;
	recordedAt: string;
	fullReceiptRetainedUntil: string;
	identityTombstoneRetainedUntil?: string;
	statusUri: string;
}

interface ReceiptRecoveryProofV1 {
	protocol: "case-write-recovery-proof/v1";
	binding: FacadeEffectBindingV1;
	receiptId: string;
	disposition: TerminalDispositionV1;
	resultingProposalLedgerRevision: string;
	resultingRevision?: string;
	effectReference?: string;
	membershipKey?: string;
	proofDigest: string;
	fullReceiptRetainedUntil: string;
}

type CaseOperationStatusV1 =
	| { state: "terminal"; receipt: CaseOperationReceiptV1 }
	| { state: "protected_terminal"; proof: ReceiptRecoveryProofV1 }
	| { state: "gone"; identityDigest: string; identityTombstoneRetainedUntil: string };
```

`ReceiptRecoveryProofV1` is returned only to the protected recovery principal and stored in protected journal fields. It contains the minimum identity/outcome material needed for monotonic merge and Projection reconciliation; it is never injected into a revoked actor's Session, model context, logs, or ordinary error response. `proofDigest` uses `cti-jcs-sha256/v1` over every normalized proof field except `proofDigest`. The protected proof must match the Journal's original binding and expected base-revision invariants exactly; it is an authority outcome, not a reduced-disclosure business receipt.

Normative receipt invariants:

- `applied` has a new `resultingRevision`, stable `effectReference`, and `membershipKey`; the resulting revision differs from base.
- `satisfied_without_change` has `resultingRevision` equal to base, the existing `membershipKey`, and no new effect reference.
- every other terminal disposition is authoritative no-effect and has no effect reference or new Case revision.
- every newly committed terminal receipt has the one resulting proposal-ledger revision created in the same transaction; duplicate identity/digest returns it unchanged and does not advance the ledger again.
- `issues` is empty except for `rejected`; rejected issues use only closed actor-safe codes and optional schema field names.
- same `FacadeEffectBindingV1` always returns the same terminal logical receipt; terminal disposition cannot change.
- same identity with another digest is an integrity conflict, not a second operation.
- 404 is not a protocol outcome. After full-receipt retention, an explicit `gone`/HTTP 410 tombstone prevents identity reuse without pretending the full proof still exists.

## 6. Projection inclusion proof

**Problem solved:** an authoritative `applied` receipt can precede OpenCTI materialization or a newly authorized composed Projection.

**Inputs:** terminal `applied` receipt or matching protected recovery proof, outbox/materialization state, and a freshly materialized Projection from the same authority.

**Output:** a proof binding the exact receipt/effect to the Projection's Case Revision, Proposal Ledger Revision, complete observation evidence, Resource Index block, and Proposal Status block.

**Boundary:** proof is not inferred from display-text equality or a generic Resource search. It must bind the stable membership key and receipt identity to the `resource_index` materialization and matching terminal `proposal_status` entry under one complete currently authorized Projection. `authorityRevision` and `proposalLedgerRevision` must equal the receipt/proof results; block digests must equal that Projection's envelopes.

**Failure behavior:** accepted without proof is `accepted_but_unsynchronized`. Reads or proposals requiring synchronized Case state remain suspended on that receipt/effect domain, while disjoint work proceeds. Visibility revocation may prevent user disclosure but does not erase protected recovery evidence.

```typescript
interface ProjectionInclusionProofV1 {
	protocol: "projection-inclusion-proof/v1";
	receiptId: string;
	binding: FacadeEffectBindingV1;
	authorityRevision: AuthorityRevision;
	proposalLedgerRevision: string;
	projectionObservationEvidenceDigest: string;
	block: "resource_index";
	blockSemanticDigest: string;
	proposalStatusBlockSemanticDigest: string;
	membershipKey: string;
	provedAt: string;
}
```

The outbox consumer may run more than once. Materialization is idempotent by canonical membership key. It records remote observations but never creates another authoritative Case revision. A pre-existing equivalent OpenCTI membership can satisfy materialization only after it is bound to the authority-owned membership and receipt.

### Materialization Outbox

**Problem solved:** the Case command may commit while OpenCTI is unavailable, and a crash must not lose or duplicate the required graph update.

**Inputs:** the co-transactionally committed authority membership, terminal `applied` receipt, canonical membership key, target deployment, and qualified source/materialization contract.

**Output:** retryable idempotent work that makes OpenCTI reflect the authority-owned membership and records enough evidence to request an exact Projection inclusion proof.

**Boundary:** the outbox is synchronization state, not a second business command, Case revision, or receipt authority. It may retry transport delivery under narrow system recovery authority after user revocation, but cannot change actor intent, payload, Case head, membership role, disposition, or disclose protected content.

**Failure behavior:** target timeout, duplicate delivery, or process crash leaves the outbox pending/reconciling and the receipt `applied`. Only synchronization-dependent chains wait. An observation inconsistent with the canonical membership or declared target quarantines materialization for the smallest affected authority partition.

## 7. Status lookup and recovery

**Problem solved:** the caller may crash after dispatch, after authority commit, or after receiving a response but before local persistence.

**Inputs:** authority, Case, operation ID, idempotency key, and request digest from the durable Effect Intent.

**Output:** the matching full terminal receipt, protected terminal proof, or gone status according to the caller's disclosure authority. A concurrent not-yet-committed request, unavailable service, unsafe disclosure, or missing route remains transport-level unknown at the caller.

**Boundary:** lookup is scoped to an already-issued intent. It cannot create, cancel, rebase, or alter a proposal. Disposition idempotency and response disclosure are separate decisions: a duplicate never re-executes, but a revoked business caller does not regain effect references, membership keys, revisions, or issues merely by replaying the old digest. A protected recovery credential may retrieve and store only the minimum matching proof after revocation and may not display it in the revoked Session.

**Failure behavior:** unavailable lookup retains `queryable_unknown` and the local Effect Reservation. Proof-retention expiry without terminal `applied` or authoritative no-effect proof becomes local `indeterminate_effect`; it does not authorize a new key, changed payload, automatic rebase, or inverse write.

Recovery rules:

- an authoritatively absent dispatch-permit transition proves the qualified dispatcher did not send and requires fresh fence validation before another permit;
- an unknown permit-transition acknowledgment returns no permit and remains reserved until lookup;
- a present permit means another process may have sent, never that the facade committed;
- retry is allowed only when the facade contract defines same-identity replay and the request digest is identical;
- a local timeout or lease expiry cannot override facade terminal state;
- a later stronger matching receipt may resolve a local `indeterminate_effect`;
- authorization revocation stops new business operations but preserves narrowly scoped receipt reconciliation.

## 8. Retention and durability

**Problem solved:** idempotency is unsafe when the server forgets identity before every retry/recovery path ends.

**Inputs:** maximum client recovery duration, queue delay, retry/backoff envelope, clock-skew margin, archive policy, and legal retention constraints.

**Output:** published `fullReceiptRetainedUntil` and identity-tombstone retention guaranteed by the service.

**Boundary:** numeric values are deployment policy, but the ordering constraint is architectural: automatic reconciliation must finish before full proof expires with an operational margin, and identity reuse must remain impossible afterward.

**Failure behavior:** a deployment unable to guarantee the advertised duration, synchronous durable commit, or failover envelope cannot activate R1. An unresolved operation is retained; it is not garbage-collected because it is old.

Production effect dispatch forbids database acknowledgment settings or HA modes that can lose an acknowledged ledger/head/effect/outbox transaction. Qualification records the exact commit and failover configuration, not merely the database product name.

## 9. Error surface

The transport maps protocol outcomes without changing their meaning:

| Condition | Protocol behavior | Illustrative HTTP |
|---|---|---|
| malformed closed request or digest | no ledger/effect | 400 |
| same identity, different digest | integrity conflict | 409 |
| expected revision mismatch | terminal `conflict` | 409 with receipt |
| current auth/Grant denied | terminal `not_authorized` or `grant_unavailable` | 403 with receipt-safe body |
| contract not active | terminal `contract_not_served` | 409 or 422 with receipt |
| accepted new effect | terminal `applied` | 200/201 with receipt |
| predicate already true | terminal `satisfied_without_change` | 200 with receipt |
| retained tombstone only | `gone` | 410 |
| unknown route/unsafe disclosure | transport 404 | never no-effect proof |

Problem Details may describe transport errors, but business receipts retain their typed protocol schema and digest identity.

## 10. Dependency-scoped suspension

An admitted R1 operation reserves at least:

- `case-head/v1(authorityId, caseId)`;
- `case-resource-membership/v1(authorityId, caseId, membershipKey)`;
- `projection-block-head/v1(authorityId, caseId, resource_index)`;
- `proposal-status/v1(authorityId, caseId, operationId)`;
- `proposal-ledger-head/v1(authorityId, caseId)`; and
- `projection-block-head/v1(authorityId, caseId, proposal_status)`.

Authorization, policy, Grant, lifecycle, Resource permit, and contract activation are `fenceDependencies`: they can deny admission/dispatch but R1 does not claim it may change them, so they do not become unknown-effect reservations. The entries above are `mayEffectDomains` and alone derive unknown-outcome suspension. Proposal-ledger and proposal-status block heads are independent from Case head because terminal no-effect receipts update them without advancing `CaseRevision`.

While outcome is unknown, only overlapping operations and downstream outputs are suspended. I&E reads for unrelated Resources, model work not requiring the affected Case head, other Cases, and disjoint Working Set entries remain available. If an observed effect escapes declared domains, quarantine the Capability and widen to the smallest safe authority partition.

After `applied`, the head reservation remains relevant until a current Projection inclusion proof is installed. After `satisfied_without_change` or another terminal no-effect disposition, reservations release atomically with receipt merge. `indeterminate_effect` retains possible effect domains until stronger proof or a governed authority fence proves the original can no longer commit.

Contradictory target-owned terminal receipts retain the operation's domains, disable new dispatch for the same receipt-authority/Capability partition, and audit other unresolved operations in that partition. They do not automatically freeze unrelated authorities, Cases, Capabilities, I&E reads, or Workspaces.

## 11. Conformance

The production and in-memory facade Adapters run the same suite. At minimum it proves:

1. same identity/digest produces one logical receipt and at most one new membership;
2. same identity/different digest never executes;
3. facade-owned expected revision/authorization/policy/Grant/lifecycle are evaluated in the Case transaction and an authentic, unexpired, exact-target I&E permit is uniquely bound there;
4. `applied` advances the Case head exactly once;
5. `satisfied_without_change` advances no Case head and creates no new effect, while its new terminal ledger row advances only the proposal-ledger head;
6. every rejection/conflict is terminal authoritative no-effect;
7. commit-before-response crash returns the original receipt after restart;
8. outbox delivery is restart-safe and idempotent;
9. OpenCTI lag does not change command disposition;
10. inclusion proof binds the exact receipt and canonical membership to matching Case/proposal-ledger revisions, Projection observation evidence, and Resource Index/Proposal Status block digests;
11. the terminal receipt never changes under duplicate or out-of-order transport observations;
12. 404, event absence, and search absence never become no-effect;
13. unresolved operations do not expire into retryable failure;
14. tombstones prevent identity reuse;
15. bypass-writer or durability-envelope violations disable activation;
16. permission revocation blocks new commands and full receipt disclosure, while a minimum protected terminal proof produces the same durable outcome transition without user-visible publication and survives restart;
17. only `mayEffectDomains`, not fence dependencies, drive unknown-outcome reservations;
18. receipt/outbox/Projection recovery can cross only its own matching reservation;
19. every new terminal ledger row advances and returns one proposal-ledger revision while duplicate replay does not; and
20. overlapping dependencies suspend while disjoint dependencies continue.

The primary-source evidence, ownership alternatives, and durability analysis are in [Case Management facade concurrency and receipt protocol research](../research/case-management-facade-concurrency-receipt-protocol.md). Its earlier pending/sequence candidate is explicitly superseded by this normative terminal-only first-slice contract.
