# Operation Effects, Idempotency, and Authoritative Reconciliation

Status: research note for the Agent Investigation Workspace operation-dependency contract.

Design disposition (2026-07-20): the dependency-scoped failure and late-result principles remain architectural constraints for reads, Working Set updates, and model requests. Remote-effect protocol recommendations are frozen input to the later strict-R1 contracts and are not current Orientation-cycle implementation scope.

## Conclusion

CTI-RAG should not claim end-to-end exactly-once execution. The relevant systems cannot share one transaction across the Workspace store, Case Management, Intelligence and Evidence, the model provider, and OpenCTI. A remote operation can execute, commit, and then lose its response; a worker can crash after producing an effect but before recording completion; an event can be duplicated, delayed, reordered, or lost.

The achievable contract is **effectively-once effect handling**:

1. persist one caller-declared operation identity and immutable request digest before dispatch;
2. deliver or retry at least once when the target operation is safe to retry;
3. require the effect owner to atomically bind that operation identity to the mutation and a durable result/effect receipt;
4. reuse the same identity and the same semantic request for every retry;
5. validate current revision, authorization, and operation fences at the target and again before applying returned output locally;
6. reconcile unknown outcomes against authoritative target state rather than inferring failure from a timeout or event absence; and
7. suspend only the transitive dependency closure of the operation's possible effect set while proof is unavailable.

This gives at-most-one accepted semantic effect for one declared operation intent, plus recovery after duplicate delivery and local crashes. It does not imply that code executed once, that transport delivered once, that provider billing or logging occurred once, or that effects outside the target's idempotency boundary were deduplicated.

## Evidence boundary

Sections labeled **Source facts** summarize official specifications, project documentation, or first-party engineering publications. Sections labeled **CTI-RAG inference** are architectural conclusions derived for this project; the cited sources do not prescribe CTI-RAG's schema or domain behavior.

## Primary-source findings

### 1. HTTP distinguishes idempotent intent, transport completion, and asynchronous acceptance

**Source facts**

- RFC 9110 defines an idempotent method by the intended server effect of multiple identical requests, not by identical executions or identical responses. It permits retry after a connection failure for idempotent methods, but says a client should not automatically retry a non-idempotent method unless it knows the request semantics are idempotent or can determine that the original request was not applied. [RFC 9110, section 9.2.2](https://www.rfc-editor.org/rfc/rfc9110#section-9.2.2)
- HTTP `202 Accepted` means processing is not complete and may never be performed. RFC 9110 recommends that its representation describe current status and identify a status monitor. A transport-level acceptance is therefore not an effect receipt. [RFC 9110, section 15.3.3](https://www.rfc-editor.org/rfc/rfc9110#section-15.3.3)
- `If-Match` is intended to prevent lost updates. The origin server must evaluate the current validator before performing the method and normally returns `412 Precondition Failed` when it does not match. RFC 9110 also recognizes the lost-response case: a server may return success if it can determine that the requested state change already succeeded. [RFC 9110, section 13.1.1](https://www.rfc-editor.org/rfc/rfc9110#section-13.1.1)

**CTI-RAG inference**

- A timeout, closed connection, `202`, or client cancellation is not proof that a Case proposal did not run.
- `CaseRevision`, policy/authorization revision, and resource versions are semantic preconditions analogous to strong validators. They must be evaluated by the authority that owns the effect, not only checked by the Workspace before sending.
- A read may be retried at the transport layer, but its result is not safe to install merely because the request itself was safe. Returned data still needs an end fence against the dependency versions and authorization state captured at start.

### 2. Stable idempotency identity must express caller intent

**Source facts**

- Amazon's preferred API design uses a unique caller-provided client request identifier. A hash of request parameters is insufficient because a caller can legitimately request two identical resources. Amazon also records the identifier on created resources so a request can later be correlated with its effect. [AWS Builders' Library, *Making retries safe with idempotent APIs*](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
- AWS describes the server-side recording of the token and all related mutations as one ACID operation. Otherwise the service can record the token without creating the resource, or create the resource without recording the token. The service stores original request parameters and rejects reuse of the identifier with different parameters. The retained idempotency knowledge has a bounded lifetime, and that lifetime is part of the operation's practical retry contract. [AWS Builders' Library, same source](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
- Stripe stores the status code and response body of the first request that begins execution for an idempotency key, including `500` responses, and rejects reuse with mismatched parameters. It documents that pruned keys can be treated as new requests. [Stripe API, *Idempotent requests*](https://docs.stripe.com/api/idempotent_requests)
- Stripe treats a network error as an unknown outcome and directs the client to retry the same request with the same key. It warns against using a new key after a server error because the original request may have caused side effects, and calls `500` outcomes indeterminate even though Stripe later attempts reconciliation. It recommends carrying a local identifier in remote object metadata so later objects and webhooks can be correlated with local state. [Stripe, *Advanced error handling*](https://docs.stripe.com/error-low-level)

**CTI-RAG inference**

- `operationId` and `requestDigest` solve different problems. `operationId` declares “this is the same intent”; `requestDigest` proves that a replay did not silently change that intent. Neither may be substituted for the other.
- The idempotency namespace must include the authoritative caller/tenant boundary and operation kind. A bare UUID with no ownership scope is insufficient for lookup and authorization.
- The idempotency key for a Case proposal must be generated by trusted Workspace code, persisted before dispatch, and unavailable for model editing.
- The target's deduplication retention must cover the maximum automated retry, crash-resume, and reconciliation interval. Once the target can no longer prove what a key meant, automatically resending the mutation is unsafe even if the local record still exists.

### 3. Durable execution observes completion once, but external work can execute more than once

**Source facts**

- Temporal recommends idempotent Activities because an Activity can complete and then its Worker can crash before reporting completion. The Event History will not show completion, so the Activity is retried. Temporal explicitly distinguishes an Activity being observed as completed once from the Activity executing, or partially completing, more than once. It recommends stable identifiers enforced by the called service. [Temporal, *Activity Definition — Idempotency*](https://docs.temporal.io/activity-definition#idempotency)
- Kafka documents the same uncertainty for message publication: after a network error, a producer cannot know whether the error occurred before or after the message committed. Kafka's idempotent producer uses a producer ID and sequence number to deduplicate resends. [Apache Kafka, *Design — Message Delivery Semantics*](https://kafka.apache.org/41/design/design/#message-delivery-semantics)
- Kafka limits its exactly-once guarantee to a transactional boundary it controls. Reading, updating offsets, and writing Kafka topics can be atomic, but exactly-once delivery to another destination generally requires that destination's cooperation. [Apache Kafka, same source](https://kafka.apache.org/41/design/design/#message-delivery-semantics)
- Kafka's producer API says a transaction commit timeout does not mean the commit request failed to reach the broker. Retrying that same commit is safe, but attempting a different operation such as abort is not safe because commit may already be in progress. [Apache Kafka `KafkaProducer.commitTransaction`](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/producer/KafkaProducer.html#commitTransaction())

**CTI-RAG inference**

- Pi or a later durable orchestrator can make an operation's observation and continuation durable, but it cannot by itself deduplicate a Case Management or OpenCTI mutation. Deduplication must be enforced where the authoritative effect commits.
- “Retry” after an unknown mutation outcome means continue the same protocol instance. It does not mean issue a semantically similar mutation, generate a new key, submit an inverse operation, or rebase the payload to a newer Case Revision.
- The Workspace should use “effectively-once effect handling” rather than “exactly once.” The former names a composition of duplicate delivery, target-side effect deduplication, fencing, and reconciliation without extending the guarantee beyond its actual boundaries.

### 4. Durable intent and receipt records close different crash windows

**Source facts**

- The AWS transactional outbox guidance identifies the dual-write failure: a service can commit business state and fail before publishing the corresponding event, or publish an event and then roll back the state. The outbox stores business state and the event in one transaction; relay can still deliver duplicates, so consumers remain idempotent. [AWS Prescriptive Guidance, *Transactional outbox pattern*](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
- AWS's asynchronous “claim check” pattern returns an identifier that a client later uses to query operation status and result, and says the service should define how long that claim remains valid. [AWS Prescriptive Guidance, *Asynchronous communication — Claim check*](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-integrating-microservices/asynchronous.html#claim-check)
- PostgreSQL's two-phase transaction support demonstrates a stronger coordinated alternative: after `PREPARE TRANSACTION`, transaction state is stored independently of the client session and can later be inspected and committed or rolled back from another session. PostgreSQL cautions that this is intended for external transaction managers and that prepared transactions must not be left unresolved because they retain locks and impede maintenance. [PostgreSQL, `PREPARE TRANSACTION`](https://www.postgresql.org/docs/current/sql-prepare-transaction.html), [`pg_prepared_xacts`](https://www.postgresql.org/docs/current/view-pg-prepared-xacts.html)

**CTI-RAG inference**

CTI-RAG does not need distributed two-phase commit for the first vertical slice. It needs two durable records with different authority:

1. **Operation Intent** in the Workspace, committed before dispatch. It proves what the Workspace meant to request and which dependencies/effects can be affected; it does not prove the remote outcome.
2. **Effect Receipt** in Case Management, committed atomically with the proposal decision and any Case change. It proves the authoritative outcome and supplies a stable reconciliation handle.

Writing an Effect Receipt only in the Workspace leaves the remote-commit/local-crash window open. Writing only a remote receipt leaves the local process unable to know after a crash which request, dependencies, and suspension scope it must recover. The two records are joined by the same stable operation identity and immutable request digest.

### 5. Events accelerate awareness; they do not replace authoritative state

**Source facts**

- Stripe does not guarantee webhook delivery order and says endpoints may receive duplicates. It recommends recording processed event identifiers and using the API to retrieve missing objects when an event arrives before related objects. [Stripe, *Receive events in your webhook endpoint*](https://docs.stripe.com/webhooks#event-ordering)
- Kubernetes list/watch starts from a resource version. If history needed by a watch has expired, the API returns `410 Gone`; clients must clear their local cache, perform a new authoritative get/list, and start a new watch from the returned resource version. Kubernetes also documents that some read modes can return an apparently older version and that clients unable to tolerate rewinding must not use them. [Kubernetes, *API Concepts — Efficient detection of changes*](https://kubernetes.io/docs/reference/using-api/api-concepts/#efficient-detection-of-changes), [resource version semantics](https://kubernetes.io/docs/reference/using-api/api-concepts/#resource-versions)
- Chubby reports a master-failover event specifically to warn clients that other events may have been lost and data must be rescanned. Its events occur after the corresponding action, so a subsequent authoritative read sees that state or something newer. [Google, *The Chubby lock service for loosely-coupled distributed systems*, sections 2.4–2.5](https://research.google.com/archive/chubby-osdi06.pdf)

**CTI-RAG inference**

- A Case change signal or remote webhook is a dirty hint, not Case truth and not proof that all prior signals were observed.
- Every event stream used by the Workspace needs a continuity token or cursor. Duplicate or older events are harmless hints; a gap, expired cursor, failover indication, unrecognized revision, or digest mismatch makes the affected authority partition dirty and requires an authoritative snapshot or supported delta reconciliation.
- Reconciliation replaces the local projection for that authority partition and then re-evaluates downstream dependencies. It must not “apply missing events” speculatively when continuity cannot be proven.
- Absence of an event is never proof that a proposal had no effect. Only an authoritative receipt/status lookup, or an authoritative object query that unambiguously carries the operation identity, can prove the outcome.

### 6. Fencing rejects stale actors and late requests at the effect boundary

**Source facts**

- Chubby describes a stale request that arrives after its lock is no longer valid. Its sequencer includes the lock generation; the client passes it with protected operations, and the recipient rejects the request if the sequencer is no longer valid or has the wrong mode. Chubby also supports compare-and-swap using a content generation number. [Google, *The Chubby lock service*, sections 2.4 and 2.6](https://research.google.com/archive/chubby-osdi06.pdf)
- Kafka fences a producer when another producer with the same transactional identity is active, and rejects an old producer epoch. Its current transaction protocol bumps producer epoch per transaction to keep duplicates from entering a later transaction. [Apache Kafka `KafkaProducer.beginTransaction`](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/producer/KafkaProducer.html#beginTransaction()), [Kafka transaction protocol](https://kafka.apache.org/41/operations/transaction-protocol/)
- Kubernetes requires the current `resourceVersion` on conditional updates so the API server can detect and reject stale lost updates. [Kubernetes, *API Concepts — Updates to existing resources*](https://kubernetes.io/docs/reference/using-api/api-concepts/#updates-to-existing-resources)

**CTI-RAG inference**

- Cancellation and leases are insufficient if a delayed request can still reach the effect owner. The effect owner must validate a fence: expected Case Revision, current authorization/policy revision, capability identity, and operation identity/request digest as applicable.
- Workspace-local outputs require a second fence at installation time. A model response, retrieval result, or remote receipt can be transport-valid but must not update the Working Set or create an artifact when its declared input versions no longer match current state.
- A local `operationEpoch` can reject late responses within one Workspace, but it cannot replace Case Management's own expected-revision and authorization checks.

### 7. Failure isolation follows explicit partitions and dependency boundaries

**Source facts**

- The bulkhead pattern isolates resources so failure in one partition does not prevent unrelated services or consumers from functioning. Official AWS and Microsoft guidance says the partition key should align with the workload's natural grain and minimize cross-partition interaction. [AWS Well-Architected, *Use bulkhead architectures to limit scope of impact*](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_fault_isolation_use_bulkhead.html), [Microsoft, *Bulkhead pattern*](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead)
- Chubby introduces sequence validation only into interactions protected by locks instead of imposing it on every interaction in a complex system. [Google, *The Chubby lock service*, section 2.4](https://research.google.com/archive/chubby-osdi06.pdf)

**CTI-RAG inference**

- The Workspace should not have one global “remote health” or “suspended” bit. Suspension should be a derived query over declared dependencies and possible effect sets.
- A dependency key must be as narrow as authoritative versioning permits, but never narrower than correctness permits. If the remote authority can only prove a whole-Case revision, the safe Case dependency is whole-Case even if a finer block-level scope would be more available.
- Authorization is its own dependency boundary. A permission revocation is not ordinary data staleness: every output that exposes or advances work from the revoked scope must be hidden or blocked, even when the underlying content version did not change.

## Recommended CTI-RAG effect protocol

This section is an architecture recommendation, not an external standard.

### Durable Operation Intent

**Problem solved:** A process can crash before it records what it sent, or after the remote target commits but before the response is persisted. Recovery needs the exact original intent and its dependency/effect scope.

**Minimum fields:**

| Field | Purpose |
|---|---|
| `operationId` | Stable caller-declared identity reused across attempts |
| `operationKind` and target authority | Names the semantics and idempotency namespace |
| actor, Case, task, and run binding | Prevents cross-actor or cross-Case key reuse |
| canonical `requestDigest` | Detects changed parameters under the same identity |
| immutable request or reconstructable request reference | Allows byte/semantic-equivalent replay |
| declared read/dependency set with exact versions | Defines validity and challenge edges |
| declared output set | Defines what can become available after success |
| declared possible effect set | Defines conflict and suspension scope while outcome is unknown |
| expected revision and authorization/policy bindings | Supplies remote fences |
| retry class and target dedupe expiry | Prevents unsafe automatic retry |
| attempt ledger | Records dispatch times and transport observations without treating them as outcome proof |
| reconciliation state and deadline | Makes recovery deterministic and operable |

**Boundary and failure behavior:** The intent is committed before network dispatch. Failure to persist it means the operation must not be sent. Its state may say `dispatch_not_started`, `in_flight`, or `outcome_unknown`, but only an authoritative remote proof may say whether an effect committed.

### Authoritative Effect Receipt

**Problem solved:** A response can be lost after commit, and a local record cannot prove remote state.

**Minimum fields:**

| Field | Purpose |
|---|---|
| authoritative receipt/status ID | Stable lookup and audit handle |
| caller scope plus `operationId` | Correlates with the durable intent |
| `requestDigest` and operation kind | Proves semantic identity of a retry |
| terminal or nonterminal outcome | Distinguishes accepted, rejected, conflict, pending, and target-declared indeterminate |
| effect reference(s) | Identifies the exact Case proposal/note/resource link affected |
| base and resulting Case Revision when applicable | Proves the concurrency boundary and synchronization target |
| evaluated actor/capability/policy binding | Proves which authority decision governed acceptance |
| target timestamps and retention/expiry metadata | Defines replay and reconciliation limits |

**Boundary and failure behavior:** Case Management commits the idempotency record, proposal decision, Case mutation, and receipt atomically. A receipt response may be lost; the receipt remains queryable by the original caller scope and `operationId`. Reusing the same identity with a different digest is a terminal contract error, not a new attempt.

### Outcome proof hierarchy

From strongest to weakest:

1. A target-owned terminal receipt matching caller scope, `operationId`, operation kind, and `requestDigest`.
2. A target-owned authoritative effect read whose persisted metadata contains the same operation identity and exact effect reference/digest.
3. A target-owned terminal `not_started`/`not_applied` record that guarantees the key was reserved and no effect can later appear.
4. A search that merely finds semantically similar Case content, a matching author/timestamp, or no current object. This is not proof: another actor can create similar content; a completed effect can later be deleted; indexing can lag; and an asynchronous operation can still complete.

If levels 1–3 are unavailable, outcome remains unknown. Human inspection can choose a compensating or superseding action, but it must not retroactively convert weak correlation into a machine-proven receipt.

### Outcome states

- `outcome_unknown`: transport ended without authoritative proof, but automated same-key reconciliation is still possible within the target contract and deadline.
- `accepted_but_unsynchronized`: the authoritative receipt proves acceptance and resulting Case Revision, but the Workspace has not yet reconciled its Case Projection to that revision or newer.
- `indeterminate_effect`: the target cannot provide a conclusive receipt/status proof, the idempotency/reconciliation guarantee expired, or the target itself declares an indeterminate terminal result. Automatic mutation retry and dependent finalization stop here.

This boundary keeps a transient timeout from becoming prematurely permanent while ensuring that expiry of the proof mechanism never silently becomes permission to duplicate an effect.

## Retry decision matrix

| Situation | Safe action | Key rule | Prohibited action |
|---|---|---|---|
| Side-effect-free read fails before a usable response | Retry, subject to backoff and deadline | No mutation key required; preserve the logical operation/dependency epoch if the result belongs to the same attempt | Installing a late result without current dependency and authorization validation |
| Read completes after its input version changed | Preserve only as explicitly historical if authorization still permits and the exact old versions remain identifiable; otherwise discard | New current read is a new attempt against new versions | Promoting the old result into current Working Set state |
| Model request fails or partial stream ends | Partial stream stays display-only; a replacement request is a new model attempt bound to a fresh dependency snapshot | Do not treat nondeterministic model output as an idempotent authoritative effect | Combining partial output from one attempt with final output from another |
| Local atomic Working Set mutation has uncertain client acknowledgement | Query the local operation ledger; replay the same local operation identity if the store contract supports it | Same identity and same request digest | Creating a second version because acknowledgement was lost |
| Remote mutation times out or connection closes | Query status/receipt; if the target contract explicitly guarantees same-key replay, retry the identical request | Must reuse the same key and digest | New key, changed payload, inverse mutation, or rebased Case Revision while original may still commit |
| Remote returns `202`/pending | Poll the supplied status monitor/claim check and retain dependency suspension | Same operation/status identity | Treating acceptance as committed effect |
| Remote returns concurrency conflict before execution and guarantees no effect started | Reconcile current authoritative state; any revised proposal is a new operation intent | New key only after terminal no-effect proof and explicit re-evaluation | Reusing the old key with changed revision/payload |
| Authorization is revoked or cannot be revalidated | Stop retries, cancel best-effort, reject late outputs, purge/hide protected bodies according to policy | Old authority binding cannot authorize continuation | Treating revocation as ordinary bounded staleness |
| Idempotency record expired while outcome is unknown | Mark `indeterminate_effect`; require authoritative correlation proof or explicit operator resolution | Old key is no longer automatically safe; a new key is a new effect | Blind retry with either old or new key |
| Receipt proves accepted, local process crashed before synchronization | Reconcile Projection to the receipt's resulting revision or newer; do not resubmit | Original key remains complete | Replaying proposal merely because local Session lacks the response |

## Authoritative reconciliation for missed, duplicate, and reordered events

1. Persist the last proven stream cursor/revision separately for each authority partition.
2. Treat events as dirty hints. Deduplicate by event identity when available; ignore an older cursor only after confirming it does not indicate a fork or failover.
3. On a contiguous event, mark only declared affected dependency keys dirty. Do not treat the event body as the new authoritative projection unless the owning API explicitly makes it so.
4. On a cursor gap, expired cursor, failover/loss signal, unrecognized revision, digest mismatch, or apparent rewind, stop incremental application for that partition.
5. Fetch an authoritative snapshot or supported delta anchored at a proven revision. Replace the local materialization atomically and obtain a new cursor.
6. Re-evaluate dependency edges from old to new versions. Challenge or hide only downstream artifacts whose declared inputs intersect changed or revoked keys.
7. Process any events that arrived during reconciliation only if they are continuous from the new cursor; otherwise reconcile again.

For Case Management, the first-release safe partition may be the whole Case Projection because `CaseRevision` is currently an opaque equality token. For Intelligence and Evidence, immutable resource-version keys can permit much narrower invalidation. A future block-level Case change contract may narrow the Case partition, but the Workspace must not infer that granularity from text diffs alone.

## Dependency-scoped suspension and fencing

### Mechanical rule

For an operation `O`, declare:

- `reads(O)`: exact authoritative and local version keys consumed;
- `produces(O)`: output keys that become usable only after validation;
- `mayEffect(O)`: authoritative state keys the operation may change, including receipt/status keys;
- `requires(O)`: explicit output/effect proofs needed before `O` can start or finalize; and
- `authority(O)`: actor/policy bindings that permit the read or effect.

If `O` has an unknown mutation outcome, let `U = mayEffect(O) ∪ producesReceipt(O)`. Suspend a later operation or artifact only when its `reads`, `requires`, expected revision, write/effect set, or promotion/finalization basis intersects `U`, then take the transitive closure through generated outputs. Unrelated operations remain available.

This is conservative about what the unknown operation might have changed, not about the entire Workspace. The contract must reject underdeclared effects at capability registration because an omitted effect key would make the derived suspension unsound.

### Important widening cases

- If the remote authority exposes only a whole-Case revision, an unknown Case proposal can suspend all fresh-required Case writes and current-Case finalization, even when the intended R1 payload is narrow. Read-only I&E exploration that does not claim current Case validity may continue.
- If a Case event cursor gap means any Case block might have changed, the dirty scope widens to the whole Case Projection until re-snapshot.
- If authorization for a Case or resource scope is revoked, every body and dependent output in that scope is affected; this can be broader than one semantic dependency chain.
- If a capability has undeclared external effects, safe dependency-scoped suspension is impossible. The capability must remain disabled until its effect set and reconciliation mechanism are specified.

### Vertical-slice implications

| Operation | Retry/recovery | Smallest safe challenge or suspension scope |
|---|---|---|
| Case Projection read | Retry as a read; install only if Case/actor/authorization epoch still matches. Cursor uncertainty causes authoritative re-open/delta reconciliation. | Outputs bound to the old Case Projection; whole Case partition if finer authoritative change keys are unavailable |
| I&E resource retrieval | Retry read; returned capsules bind immutable resource versions and access revision. Late authorized results may remain historical but cannot silently become current. | The retrieved resource/version chain and consumers; revocation widens to all material authorized by that scope |
| Model request | A failed/aborted attempt has no Workspace artifact output. Retry is a new attempt against a current dependency snapshot; partial stream is display-only. | Only prospective outputs of that model attempt and their downstream promotions |
| Working Set update | Commit selection/version and local operation receipt atomically with compare-and-swap over current Working Set/basis versions. Recover by local receipt lookup. | The affected Working Set version and artifacts that consume it, not unrelated tasks or historical artifacts |
| R1 Case proposal | Persist intent, send stable key/digest/base revision, require atomic remote receipt. Unknown outcome permits only same-key reconciliation/retry. | Fresh Case writes and finalization that depend on the proposal's possible effect/resulting revision; unrelated read-only exploration continues |
| Receipt reconciliation | Query by caller scope plus operation identity; a proven acceptance transitions to projection synchronization, not proposal replay. | The proposal chain until receipt proof, then the Case-dependent chain until Projection reaches the receipt revision or newer |
| Crash resume | Load unresolved intents before admitting dependent writes; revalidate authorization; query receipts; retry only under the original target contract. | Reconstruct suspension from persisted declared dependencies/effects rather than freezing the Session or entire Workspace |

## Rejected shortcuts

- **Request hash as idempotency identity:** conflates two legitimate identical intents and cannot express caller intent.
- **New key on timeout:** can create a second effect after the first committed.
- **Timeout or cancellation as no-effect proof:** neither proves where execution stopped.
- **Webhook/event as the only receipt:** events can be delayed, duplicated, reordered, or lost.
- **Semantic content search as proof:** similar content may have another cause and completed content may later disappear.
- **Local-only receipt:** cannot prove remote commit after local crash.
- **Global Workspace suspension bit:** discards availability that can be derived safely from nonintersecting dependency/effect sets.
- **Lease without receiver validation:** a late holder can still act after lease loss unless the effect owner checks a generation/revision fence.
- **Exactly-once label:** overstates the guarantee across systems that do not share one atomic transaction.

## Design questions left to policy rather than distributed-systems theory

The sources support the mechanism but do not determine these product values:

- maximum automated reconciliation duration and backoff;
- target idempotency and receipt retention period;
- when an unresolved but still queryable outcome escalates operationally;
- operator actions allowed for `indeterminate_effect` by capability risk tier;
- whether authorized stale read outputs remain visible as historical or are hidden from future model context;
- storage and purge policy after access revocation; and
- whether Case Management can expose block-level change/effect keys safely enough to narrow whole-Case invalidation.

These values should be explicit capability and authority policies. They must not be inferred from generic HTTP status codes or client timeout settings.

## Primary sources reviewed

- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110)
- [AWS Builders' Library: Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
- [Stripe API: Idempotent requests](https://docs.stripe.com/api/idempotent_requests)
- [Stripe: Advanced error handling](https://docs.stripe.com/error-low-level)
- [Stripe: Receive events in your webhook endpoint](https://docs.stripe.com/webhooks)
- [Temporal: Activity Definition — Idempotency](https://docs.temporal.io/activity-definition#idempotency)
- [Apache Kafka: Design — Message Delivery Semantics](https://kafka.apache.org/41/design/design/#message-delivery-semantics)
- [Apache Kafka: `KafkaProducer` API](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/producer/KafkaProducer.html)
- [Apache Kafka: Transaction Protocol](https://kafka.apache.org/41/operations/transaction-protocol/)
- [Kubernetes: API Concepts](https://kubernetes.io/docs/reference/using-api/api-concepts/)
- [Google: The Chubby lock service for loosely-coupled distributed systems](https://research.google.com/archive/chubby-osdi06.pdf)
- [AWS Prescriptive Guidance: Transactional outbox pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
- [AWS Prescriptive Guidance: Asynchronous communication](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-integrating-microservices/asynchronous.html)
- [PostgreSQL: `PREPARE TRANSACTION`](https://www.postgresql.org/docs/current/sql-prepare-transaction.html)
- [AWS Well-Architected: Bulkhead architectures](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_fault_isolation_use_bulkhead.html)
- [Microsoft Azure Architecture Center: Bulkhead pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead)
