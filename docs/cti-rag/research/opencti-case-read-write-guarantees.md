# OpenCTI Case Read/Write Guarantees for the First Vertical Slice

Status: primary-source research note for the CTI-RAG Agent Investigation Workspace operation-dependency contract.

Design disposition (2026-07-20): the actor-scoped read, authorization, pagination, observation, stream, and history findings support the current [`opencti-case-orientation/v1` Contract](../agent-workspace/opencti-case-orientation-v1-contract.md). The section 12 recommendation to use an OpenCTI-direct mutation mode is not active: writes are deferred, and any later strict R1 is governed by the accepted facade and journal contracts rather than this research candidate.

Research date: 2026-07-20.

Source baseline: official OpenCTI documentation under `docs.opencti.io/latest` and official repository commit [`3fe1ce3c1f87e2ad33f370fe358454ffb682ae12`](https://github.com/OpenCTI-Platform/opencti/tree/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12). An actual deployment may expose a different schema or behavior; its GraphQL introspection and version must be captured by the Adapter.

## Conclusion

Stock OpenCTI provides useful Case, Task, Note, reference-relation, semantic-relation, history, and event-stream primitives, but it does **not** provide the operation contract CTI-RAG needs by itself. In particular, the public GraphQL mutations do not expose:

- a Case-wide monotonic revision or snapshot token;
- an expected-revision / compare-and-swap precondition;
- a durable request-idempotency receipt;
- a mutation-status lookup keyed by caller intent;
- a response that distinguishes `accepted`, `already_applied`, `conflict`, and `indeterminate`; or
- a documented atomic snapshot-plus-stream handoff.

Therefore CTI-RAG must treat OpenCTI as an authoritative but comparatively weakly coordinated adapter boundary:

1. authoritative reads must capture the exact object set, authorization context, page traversal, and a CTI-RAG-computed projection digest;
2. stream and history records are invalidation/reconciliation evidence, not a native Case revision;
3. a timed-out mutation remains outcome-unknown until authoritative reconciliation or a cooperating receipt narrows the result; predicate presence proves current effect existence but not which request caused it;
4. R1's neutral Case resource attachment should be modeled as a Case `object` reference relation, not invented as a STIX semantic relationship;
5. stock GraphQL cannot make a read-derived proposal conditional on the Case revision it observed, so strict proposal fencing requires a cooperating Case Management facade/sidecar or a deliberately weaker reconcile-before-and-after protocol; and
6. only the dependency chain rooted in the unresolved OpenCTI effect or stale projection must be suspended. Unrelated Workspace operations remain runnable.

## Evidence boundary

Sections labeled **Source facts** report official OpenCTI documentation or source behavior. Sections labeled **CTI-RAG inference** are product and architecture conclusions; OpenCTI does not prescribe CTI-RAG's contract.

Negative findings such as “no idempotency implementation found” are scoped to the inspected official commit and its public GraphQL path. They are not claims about private extensions or future releases.

For those negative findings, the audit procedure was: inspect every first-slice mutation input and result type; search the complete checked-out backend/schema for `clientMutationId`; search the public schema and backend for a receipt/status query or mutation payload keyed by caller intent; and trace the Case/Task/Note/reference/core-relation resolver-to-domain path. The only non-generated, non-schema `clientMutationId` occurrence found treats it as form metadata to omit, cited in section 6.2. No receipt store or status resolver was found.

## 1. Public API and authorization boundary

### Source facts

- OpenCTI describes GraphQL as its comprehensive API and says actions available in the UI are available through the API. API access is authorized with a bearer token, and returned access is determined by the privileges of the user associated with that key. [Official GraphQL API documentation](https://docs.opencti.io/latest/reference/api/)
- The instance-local Playground at `/public/graphql` exposes the deployed schema and supports queries, mutations, and subscriptions. OpenCTI explicitly says the public documentation does not yet contain mutation examples and directs developers to the instance schema, browser traffic, Python client, or source. [Official Playground documentation](https://docs.opencti.io/latest/development/api-usage/)
- Public schema authorization is field/mutation specific. For example, Case reads require `KNOWLEDGE`; Case mutation and relationship operations require update capabilities; deletion requires delete capability. [Case queries and mutations](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case.graphql#L198-L215), [container edit mutations](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L16193-L16203).
- Update middleware also validates current user access before applying an update and raises forbidden access when the operation is not permitted. [Update access validation](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/middleware.ts#L2422-L2451)
- Stream results are filtered by the connected user's rights. The live-stream implementation recomputes user/collection filters while processing. [Streaming documentation](https://docs.opencti.io/latest/reference/streaming/), [live-stream recomputation](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/graphql/sseMiddleware.js#L743-L753).

### CTI-RAG inference

- An API token is not a stable authorization snapshot. A Case read can succeed, then a later page, end probe, mutation, receipt reconciliation, or stream delivery can be denied or filtered after capability, marking, organization, or authorized-member changes.
- `authorization-context` must therefore be a declared dependency of every OpenCTI operation. Permission revocation invalidates only results/effects that depend on that authority scope; it must not freeze unrelated local reasoning or other authority partitions.
- A `403`, filtered page, or suddenly missing object is not evidence of deletion. The Adapter must classify `revoked_or_hidden` separately from `not_found`, and must not leak previously visible content through error details, caches, or model context.
- The deployed version, introspected schema digest, enabled capabilities, and credential identity belong in the Adapter capability manifest. Source-code observations are insufficient to activate a write path on an unknown instance.

## 2. Actual Case projection read shapes

### Source facts

The Case interface exposes two identifiers and several timestamps:

- `id` is documented in the schema as the internal ID;
- `standard_id` is separately exposed;
- `created_at`, `updated_at`, `x_opencti_modified_at`, `created`, and `modified` are timestamps, not declared revision counters;
- `currentUserAccessRight` and `authorized_members` expose some current access state;
- `objects` and `stixCoreRelationships` are Relay-style paginated connections with `first` and `after`; and
- `tasks` is a `TaskConnection`, but the nested Case field itself has no pagination arguments. `notes(first: Int)` also has no `after` argument. [Case interface](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case.graphql#L1-L169)

Top-level Case reads are:

```graphql
case(id: String!): Case
cases(first: Int, after: ID, orderBy: CasesOrdering,
      orderMode: OrderingMode, filters: FilterGroup,
      search: String, toStix: Boolean): CaseConnection
```

[Case query schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case.graphql#L187-L210)

Case Incident has corresponding `caseIncident` / `caseIncidents` queries. [Case Incident queries](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-incident/case-incident.graphql#L206-L219)

Task exposes top-level `task` and paginated `tasks(first, after, orderBy, orderMode, filters, search, toStix)`. The Case `tasks` resolver obtains Tasks related to the Case through the `object` reference relation. [Task query schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/task/task.graphql#L187-L210), [Case-task resolver domain](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/task/task-domain.ts#L42-L47).

Note similarly exposes an individual read and paginated top-level list in the domain layer, while Case's nested `notes` field only takes `first`. [Note read domain](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/domain/note.js#L15-L20).

OpenCTI distinguishes two relation families relevant to the slice:

1. `StixRefRelationship`, used for embedded/reference links such as a Container's `object` membership. It exposes `from`, `to`, `relationship_type`, IDs, and timestamps. [Reference-relationship type](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L14631-L14681)
2. `StixCoreRelationship`, used for semantic CTI graph edges with required `fromId`, `toId`, and `relationship_type`, plus confidence, description, time bounds, markings, and references. [Core-relationship input](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L14470-L14499)

### CTI-RAG inference

A complete `CaseProjection` cannot be one casually nested GraphQL response:

- `objects` and semantic relationships require exhaustive pagination;
- nested `tasks` and `notes` do not expose a continuation cursor at the Case field, so their completeness cannot be inferred from a single nested read;
- the Adapter must use independently pageable top-level Task/Note queries or another instance-verified traversal and must record how each collection was proven complete; and
- each projection component needs an explicit completeness state: `complete`, `truncated_by_contract`, `revoked`, `failed`, or `unknown`.

The minimum projection record should include:

```text
OpenCtiProjectionEvidence {
  instance_id
  api_version
  schema_digest
  credential_subject
  case_internal_id
  case_standard_id
  observed_timestamps
  collection_page_evidence[]
  visible_member_ids[]
  visible_task_ids[]
  visible_note_ids[]
  visible_relation_ids[]
  authorization_fingerprint
  canonical_projection_digest
  observed_at
}
```

`canonical_projection_digest` is a CTI-RAG comparison token, not an OpenCTI revision. It proves only equality of the successfully observed and authorized projection components.

## 3. Pagination does not provide snapshot consistency

### Source facts

- The backend decodes `after` into Elasticsearch `search_after`, adds `standard_id` as a tie-breaker, and sends the resulting sort tuple in the next query. [Elasticsearch query construction](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/engine.ts#L3099-L3105), [ordering and `search_after`](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/engine.ts#L3155-L3217)
- A cursor is base64-encoded JSON containing the sort values. Pagination code explicitly calls its approach stateless and notes that even `hasNextPage` and `hasPreviousPage` are approximations. [Cursor and pagination implementation](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/utils.ts#L226-L300)
- The inspected query path does not expose an Elasticsearch point-in-time or other public snapshot handle to the caller.

### CTI-RAG inference

- Stable sort order prevents arbitrary ordering ties; it does not freeze the result set. Concurrent inserts, deletes, changes to sort/filter fields, merges, or permission changes can cause omissions, duplicates, or membership drift across pages.
- The Adapter must de-duplicate by resolved identity, capture every page cursor/count, and perform an end probe against the Case head and relevant collection digests. A detected change restarts only the affected projection partition. It must not install a mixture as a fresh `CaseProjection`.
- OpenCTI offers no native token that proves “all these independently paged collections came from the same Case snapshot.” If the first slice requires that strength, a cooperating facade must provide it.

## 4. Mutation shapes and response semantics

### Source facts

Relevant public mutation shapes at the inspected commit are:

| Intent | Public mutation | GraphQL result |
|---|---|---|
| Create Incident Response Case | `caseIncidentAdd(input)` | `CaseIncident` |
| Patch a Container/Case | `containerEdit(id).fieldPatch(input, ...)` | `Container` |
| Attach a referenced object to a Case | `containerEdit(id).relationAdd(input, ...)` | `StixRefRelationship` |
| Remove a referenced object | `containerEdit(id).relationDelete(toId, relationship_type, ...)` | `Container` |
| Create Note | `noteAdd(input)` | `Note` |
| Create / patch Task | `taskAdd(input)` / `taskFieldPatch(id, input, ...)` | `Task` |
| Create semantic graph edge | `stixCoreRelationshipAdd(input)` | `StixCoreRelationship` |
| Delete semantic graph edge | `stixCoreRelationshipDelete(fromId, toId, relationship_type)` | `Boolean!` |

Sources: [Case Incident input/result](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-incident/case-incident.graphql#L221-L263), [Container mutations](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L16193-L16203), [Note input/result](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L3901-L3931), [Note mutation](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L16573-L16577), [Task mutations](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/task/task.graphql#L212-L243), [Core relationship mutations](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L16688-L16698).

These mutations return the affected entity/relation, ID, or Boolean. None of these result types is a durable operation receipt containing caller operation identity, immutable request digest, expected/observed revision, disposition, or later status URL.

The inspected public `Query` schema also has no operation-status lookup keyed by `clientMutationId` or another caller mutation identity, and the mutation results do not echo such an identity in a receipt wrapper. This is an explicit negative result from the audit procedure above, not an inference from naming alone.

The source control flow also exposes important post-write windows:

- Case Incident creation awaits `createEntity`, then applies zero or more templates, then notifies. [Case Incident creation flow](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-incident/case-incident-domain.ts#L28-L40)
- Task and Note creation await `createEntity`, then notify. [Task creation flow](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/task/task-domain.ts#L50-L64), [Note creation flow](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/domain/note.js#L23-L28)
- Reference-relation add first patches the source object's reference field, constructs a relation representation, then notifies. [Reference-relation add flow](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/domain/stixObjectOrStixRelationship.ts#L51-L71)
- Core relationship creation similarly awaits `createRelation`, then notifies. [Core relationship creation flow](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/domain/stixCoreRelationship.js#L96-L125)

### CTI-RAG inference

- A successful GraphQL response is evidence that the returned operation path completed, but it is not a replayable operation receipt.
- A timeout, connection loss, process crash, or GraphQL error after dispatch cannot be mapped mechanically to “not committed.” The visible flows have steps after the primary write, and Case template application is explicitly multi-step. The authoritative effect may exist even when no response reached CTI-RAG.
- For R1, the neutral “this resource belongs in this Case Working Set” link maps to `containerEdit(caseId).relationAdd({toId: resourceId, relationship_type: "object"})`. A `StixCoreRelationship` should be used only when the analyst is asserting a real CTI semantic edge. This avoids fabricating intelligence semantics merely to obtain a link.
- The reference-add effect is reconcilable by the authoritative predicate `(case, "object", resource)`. Predicate presence proves that the effect currently exists, but stock OpenCTI cannot attribute it to this request. Predicate absence is conclusive only after the Adapter has established current authorization, completed the authority's supported consistency/recheck window, and ruled out merge/canonical-ID movement.

## 5. No public optimistic-concurrency precondition

### Source facts

- `fieldPatch`, `relationAdd`, `relationDelete`, Task patches, Note edits, Case creates, and relationship creates accept object IDs and mutation inputs, but no `expectedRevision`, ETag, `If-Match`, generation, or compare-and-swap value. The schemas cited in section 4 are the public contract.
- Internal update code loads the current object, validates it, and later obtains Redis locks for participant IDs before applying the update. It emits a stream update event when attributes actually change. [Load/update flow](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/middleware.ts#L2881-L2902), [internal lock acquisition](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/middleware.ts#L2486-L2526), [event emission and unlock](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/middleware.ts#L2788-L2838)

### CTI-RAG inference

- Internal serialization/locking is not caller-visible optimistic concurrency. It does not let CTI-RAG say “apply this only if the Case still equals the projection used by R1.”
- A preflight read followed by mutation has a time-of-check/time-of-use window. A postflight read can detect some interference but cannot retroactively prevent an effect based on stale evidence.
- Strict first-slice acceptance requires one of:

  1. a cooperating Case Management facade that atomically checks CTI-RAG's expected Case revision and records an effect receipt with the OpenCTI mutation; or
  2. an explicitly weaker OpenCTI-direct mode limited to monotonic, predicate-reconcilable effects such as set-like neutral attachment, with before/after authoritative checks and visible `concurrency_unfenced` provenance.

The second mode must not be generalized to destructive updates, replacement patches, analyst-decision state, or semantic relationships.

## 6. Identifiers, deduplication, and request idempotency

### 6.1 Identifiers

**Source facts**

- OpenCTI exposes internal `id` and `standard_id`. In the inspected source, internal IDs are UUIDv4. Standard IDs for STIX objects and core relationships are generated with deterministic UUIDv5 rules; reference relationships receive a random `relationship-meta` standard ID. [Identifier generation](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/schema/identifier.js#L481-L519)
- Object resolution considers internal ID, standard ID, additional STIX IDs, aliases, and—in applicable types—hash IDs. Create inputs can include `stix_id` and additional STIX IDs. [Instance/input ID sets](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/schema/identifier.js#L572-L605)
- Updating an ID-contributing field can calculate a new standard ID and can lead into duplicate/merge handling. [Standard-ID-impact handling](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/middleware.ts#L2506-L2539)

**CTI-RAG inference**

- Neither exposed ID is a Case revision. `standard_id` is content-derived for many entity types and may change or collide into merge behavior when contributing fields change; `id` can cease to be the canonical object after merge/delete.
- Persist both IDs plus instance identity and maintain an alias/canonicalization map updated by authoritative reads and merge events. Never use a bare OpenCTI ID across instances/tenants.
- A `StixRefRelationship` ID is not suitable as the stable R1 effect identity. Reconcile the relation by its source/type/target predicate.

### 6.2 Semantic deduplication is not request idempotency

**Source facts**

- OpenCTI documents creation as an upsert: if an object already exists according to type-specific ID-contributing properties, creation returns the existing object and may also update it. Relationship deduplication uses type, source, target, and start/stop time windows. Incoming creation can update an existing object's attributes according to consolidation rules. [Official deduplication documentation](https://docs.opencti.io/latest/usage/deduplication/)
- The documentation currently lists Incident Response Case as `name OR alias`, RFI/RFT as `name AND created`, and Note/Task as having no contributing properties. [Official entity table](https://docs.opencti.io/latest/usage/deduplication/)
- The inspected newer source conflicts with part of that table: Case Incident registers `name` and `created`; Task registers `name` and `created`; Note's base identifier definition uses content plus created/abstract dependencies. [Case Incident identifier](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-incident/case-incident.ts#L10-L26), [Task identifier](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/task/task.ts#L10-L25), [Note identifier contribution](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/schema/identifier.js#L204-L211)
- Several add inputs contain `clientMutationId`, but Task add does not. In a repository-wide search of the inspected backend commit, non-generated/non-schema use of `clientMutationId` was limited to excluding it as GraphQL metadata from form-bundle data; no mutation ledger, stored result, request-digest comparison, replay response, or status lookup was found. [Form bundle metadata exclusion](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/form/form-bundle-builder.ts#L20-L39)

**CTI-RAG inference**

- `clientMutationId` must be treated as inert metadata unless the deployed instance proves stronger behavior. Its mere presence in an input is not an idempotency contract.
- `update: Boolean` is an upsert/consolidation control, not expected-revision concurrency.
- Semantic deduplication can collapse two legitimately distinct caller intents or update an existing object. It cannot prove that one CTI-RAG operation was applied exactly once.
- The documentation/source disagreement is itself a version-skew hazard. The Adapter must run non-destructive conformance tests against a dedicated test tenant/version before declaring create operations `retryable` or `reconcilable`.
- CTI-RAG must persist its own immutable `operationId` and `requestDigest` before dispatch. For strict effectively-once writes, a cooperating remote receipt store must atomically bind that identity to the OpenCTI effect. Stock OpenCTI GraphQL provides no such binding.

## 7. History and audit are derived, configurable, and retainable

### Source facts

- OpenCTI says every create/update/delete of STIX knowledge is accessible through entity history and handled by the history manager. The broader unified Activity interface is an Enterprise feature; administration/security audit is a different category from basic knowledge history. [Official Activity overview](https://docs.opencti.io/latest/administration/audit/overview/)
- The public GraphQL schema exposes `logs`/`log` for knowledge history and more privileged `audits`/`audit` queries for security activity. [Log schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L490-L543), [log/audit queries](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L14730-L14770)
- History is materialized asynchronously from stream events into a history index. The manager filters some events, buffers processing, and resumes from the latest indexed history timestamp. It starts only when `history_manager:enabled` is true; the code fallback is false. [History event materialization](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/manager/historyManager.ts#L143-L277), [manager resume/configuration](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/manager/historyManager.ts#L281-L346), [manager startup gate](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/managers.js#L109-L115)
- History retention rules can permanently delete old knowledge-history entries. Such rules are inactive by default when created, but administrators may enable them. [Official retention documentation](https://docs.opencti.io/latest/administration/retentions/)

### CTI-RAG inference

- History is useful corroboration and analyst-facing provenance, but it is not an authoritative, gap-free Case operation ledger.
- It may lag the main database, may be disabled, filters out some event categories, and may be truncated by retention. A missing history record does not disprove a write.
- History timestamps/event IDs must not be promoted into a native Case revision. They can participate in dirty detection and reconciliation evidence only.
- The Adapter capability manifest must report history availability, manager health if observable, caller access, and configured retention horizon. If any is unknown, history-dependent operations must declare degraded evidence rather than silently assuming completeness.

## 8. Stream behavior and its limits

### Source facts

- OpenCTI emits a Redis Stream event whenever the database is modified and exposes events through SSE. Event IDs resemble Redis stream positions; events cover create/update/delete/merge and include STIX data plus context. Update and merge events include JSON Patch and reverse patch. [Official streaming format](https://docs.opencti.io/latest/reference/streaming/)
- The base `/stream` is rights-filtered. `from` accepts a timestamp or event ID for catch-up. Stream retention is configurable via `redis:trimming`; the documentation recommends roughly one month / two million events as sizing guidance, not as a protocol guarantee. [Official base-stream documentation](https://docs.opencti.io/latest/reference/streaming/)
- A live `/stream/{id}` can recover an initial list from the main database, resolve dependencies, and then continue from a stream position. `from` selects the initial point; `recover` requests database-backed recovery even beyond stream retention. [Official live-stream documentation](https://docs.opencti.io/latest/reference/streaming/)
- The implementation performs database recovery for an `after`/`before` time window and starts the live stream at the recovery cursor afterward. Streams using origin filters explicitly skip database recovery and emit `no-recover`. [Recovery implementation](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/graphql/sseMiddleware.js#L756-L816)
- Redis trimming is a deployment configuration read by the stream implementation. A live processor uses `$` when starting “now” and an explicit event ID when resuming. [Stream trimming/configuration](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/redis-stream.ts#L22-L37), [processor start cursor](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/redis-stream.ts#L155-L174)

### CTI-RAG inference

- An event ID is a stream position, not a Case generation. Events for unrelated objects interleave; filtered consumers do not observe a per-Case contiguous sequence.
- The official docs do not promise exactly-once delivery, infinite retention, or an atomic MVCC snapshot tied to a stream cursor. The source recovery scan is a bounded current-database query followed by a cursor handoff; it is not a public snapshot-isolation token.
- Consumers must persist the last fully processed cursor, tolerate duplicate and out-of-order delivery, and validate object-local ordering/timestamps before using an event as a dirty hint.
- Disconnect, trimmed cursor, `no-recover`, unrecognized event version, authorization change, dependency-resolution failure, or digest mismatch requires authoritative re-read of the affected OpenCTI projection partition. It does not require freezing the whole Workspace.
- Event absence never resolves a mutation's unknown result. Reconciliation must read the authoritative effect predicate or a cooperating receipt store.

## 9. Explicit non-guarantees

The reviewed OpenCTI public contract does **not** guarantee the following:

| Needed property | OpenCTI evidence | Result for CTI-RAG |
|---|---|---|
| Case-wide monotonic revision | Only timestamps, IDs, object events | Compute observation digest; do not label it native revision |
| Multi-collection snapshot | Stateless `search_after`; independent resolvers | Page/recheck each partition; restart affected partition on drift |
| Read-your-snapshot after concurrent edit | No snapshot token | End-fence and surface `concurrent_change` |
| Conditional mutation on observed Case state | No expected revision / ETag | Requires facade for strict fencing |
| Request idempotency | No durable `clientMutationId` handling found | Local intent ledger plus cooperating remote receipt, or effect-specific reconciliation |
| Mutation-status lookup | Mutation returns object/ID/Boolean only | Timeout remains `outcome_unknown` |
| Atomic Case-create plus templates | Source shows sequential stages | Reconcile Case and each template-derived effect independently |
| Gap-free history | Async/configurable/retained | History is corroboration, not authority |
| Infinite/replay-complete stream | Configurable trimming and filter-dependent recovery | Persist cursor; full partition rebase on discontinuity |
| Stable visibility during operation | Rights evaluated from current credential/context | Authorization is a dependency and an end fence |
| Universal identifier immutability | Standard IDs depend on fields; merges exist | Store aliases and resolve canonical identity |
| Note/Task create dedup across versions | Official docs and current source disagree | Versioned conformance probe required |

## 10. First-slice Adapter contract implied by the evidence

### 10.1 Case projection read

**Problem solved:** prevent a partial, mixed-version, or no-longer-authorized OpenCTI read from becoming the Working Set authority.

**Input:** instance/caller identity, Case identity, projection manifest listing required fields and collection traversals, start authorization fingerprint, timeout/budget.

**Output:** projection data plus `OpenCtiProjectionEvidence`; never bare data.

**Boundary:** only fields and collections declared by the projection manifest. Retrieval/model outputs are not part of this read.

**Failure behavior:**

- page failure/timeout -> affected projection partition `unknown`, not silently truncated;
- concurrent drift -> discard or retain only as stale evidence, then restart affected partition;
- permission loss -> redact affected data and mark `revoked_or_hidden`;
- schema/version mismatch -> fail closed for writes, possibly permit labeled read-only degraded mode.

### 10.2 R1 neutral resource attachment

**Problem solved:** add an already-authoritative resource to the Case without asserting a fabricated CTI semantic relationship.

**Input:** Case identity, resource identity, expected CTI-RAG projection digest, current authorization evidence, trusted `operationId`, immutable request digest.

**Intended OpenCTI effect:** Case reference predicate `(case, relationship_type = "object", resource)`.

**Output:** one of CTI-RAG's dispositions:

```text
applied | already_present | rejected_authorization |
rejected_validation | concurrency_unfenced | outcome_unknown
```

OpenCTI itself does not return these dispositions; the Adapter derives them from response plus authoritative probes, or receives them from a cooperating facade.

**Boundary:** one neutral reference membership only. It does not patch resource content, Case narrative, Tasks, Notes, status, markings, or semantic relations.

**Failure behavior:**

- response arrives after input digest/auth changed -> record remote evidence, do not install dependent local success;
- timeout/write result unknown -> suspend only operations depending on this membership effect, query the predicate, and do not infer failure from missing events;
- predicate present -> converge to `applied_or_already_present`, preserving that stock OpenCTI cannot attribute which request caused it;
- predicate absent with current authorization proven -> retry only if the deployed Adapter has validated set-add retry safety; otherwise keep `outcome_unknown` for analyst/facade reconciliation;
- permission revoked -> stop probing with old authority, redact cached protected data, and mark the effect unresolved rather than absent;
- local crash after remote commit -> recover durable local intent, probe the same predicate/receipt, then continue the same operation identity.

### 10.3 Notes, Tasks, and semantic relationships

For the first slice, these should remain outside R1 unless explicitly needed:

- Note/Task creates are not safely attributable to a CTI-RAG operation by stock request receipt.
- Human-readable equality (`same content`, `same task name`) is not a safe idempotency identity and can collapse distinct analyst intent.
- Core-relationship dedup is semantic upsert/consolidation, not caller-intent deduplication.
- Any future create path must first prove a durable unique marker or deploy a receipt-owning facade. Optional `stix_id` support is promising for correlation but is not, from the public contract alone, a stored request receipt or immutable operation binding.

## 11. Behavioral acceptance scenarios derived from OpenCTI facts

The main design should cover at least these behaviors:

1. **Concurrent Case membership change during paginated read:** affected projection partition restarts; unrelated Workspace chains continue.
2. **Task/Note nested connection cannot prove completeness:** projection is not marked complete merely because nested edges returned.
3. **Permission revoked between pages:** protected data is removed/redacted, result becomes `revoked_or_hidden`, and deletion is not inferred.
4. **Mutation response arrives after proposal inputs changed:** remote evidence is recorded, but stale result cannot advance Working Set/R1 dependents.
5. **Reference-add timeout, predicate later present:** crash recovery converges without issuing a new semantic intent.
6. **Reference-add timeout, predicate absent, authorization uncertain:** outcome remains unknown; only its effect dependency chain is suspended.
7. **Duplicate/out-of-order stream events:** projection is dirtied idempotently; no duplicate Working Set effect is installed.
8. **Trimmed cursor or `no-recover`:** affected OpenCTI authority partition is fully rebased.
9. **History manager disabled or history retained away:** absence of history does not disprove the mutation.
10. **Case create succeeds but template application/response fails:** Case and template-derived effects reconcile independently; the operation is not flattened to simple failure.
11. **OpenCTI docs/source dedup mismatch:** Adapter write capability remains disabled until the deployed version passes conformance probes.
12. **Unrelated Workspace operation while R1 receipt is unknown:** it proceeds when its declared inputs do not depend on the unresolved Case membership.

## 12. Recommended decision

For the first vertical slice, use OpenCTI direct GraphQL for authoritative reads and for the narrow, monotonic, predicate-reconcilable R1 `object` attachment only. Label this integration mode `opencti-direct-unfenced` and make its weaker concurrency attribution visible in provenance.

Do not claim strict effectively-once, conditional Case mutation, or exact request attribution in this mode. If behavioral acceptance requires those guarantees, place a small Case Management facade in front of OpenCTI that owns:

- monotonic Case revision;
- expected-revision and authorization fencing;
- `operationId` + request-digest uniqueness;
- durable effect receipt/status lookup; and
- atomic binding between the receipt and the accepted mutation protocol.

This is a boundary decision, not a reason to expand the LLM tool surface. The model should continue to propose typed intent; trusted orchestration and the OpenCTI Adapter/facade own identity, dependency declarations, fencing, dispatch, reconciliation, and receipt interpretation.
