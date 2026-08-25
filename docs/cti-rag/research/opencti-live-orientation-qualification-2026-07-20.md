# Live OpenCTI Orientation Qualification

Status: primary-source research with an implemented offline-qualified live `opencti-case-orientation/v1` smoke vertical; real target evidence remains pending.

Research date: 2026-07-20.

Design disposition: adopt the minimal live GraphQL transport and qualification slice described below so one real Case can pass through `CaseWorkspaceModule.open -> CaseWorkspace.prompt` today. A successful smoke run is deployment evidence for that Case and actor only. It is not production qualification, an OpenCTI snapshot claim, or evidence that every OR/OR0B acceptance case holds on the deployment.

Source baseline: current OpenCTI documentation and official repository commit [`6f81b62b2dd95bf77bd3796ccefeb297f99ee73d`](https://github.com/OpenCTI-Platform/opencti/tree/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d). The selected deployment's reported version and introspected schema take precedence over this source snapshot.

Implementation outcome: the package now owns the live Node factory, fixed documents, supported HMAC receipt authenticator, JSONL smoke composition, and CLI under `src/node/`. Thirty offline focused tests pass, including same-name/wrong-TypeRef, nested-nullability, and union/inline-fragment runtime-overlap rejection; mechanical inspection of the actual faux-model context; and discoverable Session paths on success and post-creation failure. The pre-existing 49 CTI lifecycle/conformance tests also pass. No real OpenCTI target was called because the sealed target bundle was not available; the runbook owns that final diagnostic step.

## Verdict

**AGREE:** the repository's `OpenCtiTransportOrientationAdapter` is production-shaped, not a live OpenCTI Adapter.

It consumes an already normalized `OpenCtiOrientationTransportPort` response. The package has no HTTP client, GraphQL documents, bearer-token handling, credential resolver, schema introspection, deployment qualifier, or opt-in live smoke runner. Its only transport implementation is the scripted testing Adapter. The constructor's `source` versus `observedSource` comparison compares two caller-supplied values; it does not obtain qualification evidence from an OpenCTI target.

The existing Module above this seam is useful and should remain unchanged: it already performs two complete observations, schema validation, materialization, Session projection, and `open/prompt/close` lifecycle fencing. The missing Module is a live GraphQL Adapter behind `OpenCtiOrientationTransportPort`, plus a qualification factory that is the only supported way to construct its `OrientationSourceIdentityV1`.

## Primary-source facts and dispositions

### HTTP and actor identity

- OpenCTI's GraphQL API uses an API key in `Authorization: Bearer ...`; the returned access is the access of the user associated with that key. The deployed Playground/schema is the documentation authority for the instance. [OpenCTI GraphQL API](https://docs.opencti.io/latest/reference/api/)
  - **Design disposition:** accept an exact GraphQL endpoint and an opaque credential resolver. Never put a token in `TrustedActorBinding.credentialRef`, Session, events, failures, digests, or qualification output.
- The current server mounts POST GraphQL at the configured base path plus `/graphql` and redirects the browser root to `/public/graphql`. [Official server source](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/src/http/httpServer.js#L117-L169)
  - **Design disposition:** require the caller to provide the exact POST endpoint; do not guess a base path from the Playground URL.
- The current schema exposes authenticated `me`, `settings`, and `about.version`; `settings.id` is an instance-local identifier. [Official generated schema](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L14840-L14850)
  - **Design disposition:** qualification derives `actorRef` from `me.id`, rejects a caller-supplied mismatch, and binds the target to normalized endpoint, `settings.id`, reported version, and schema digest.

### Case root

- `case(id: String!): Case` is authorized for `KNOWLEDGE`. The Case interface exposes internal/standard IDs, type, representative/name, timestamps, status, markings, organizations, Authorized Members metadata, current-user access right, and pageable objects. [Official Case schema](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/src/modules/case/case.graphql#L1-L124), [Case query](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/src/modules/case/case.graphql#L199-L212)
  - **Design disposition:** one root query maps only the Orientation identity fields. A separate, non-rendered authorization fingerprint covers `me.id`, effective actor marking references and capabilities, Case markings/organizations, `authorized_members_activation_date`, and `currentUserAccessRight`. The actor organization connection and Case member list are not selected for this diagnostic smoke because their identities are unnecessary and more sensitive; their controlled transition behavior remains production-qualification work.
- Authorized Members can restrict a Case to selected users/groups/organizations, and the restriction on supported containers does not cascade to contained entities. [OpenCTI Authorized Members](https://docs.opencti.io/latest/administration/authorized-members/)
  - **Design disposition:** root visibility never authorizes Tasks or members. A null/inaccessible root has the single actor-safe outcome `case_root_not_found_or_not_visible`. The root is queried at both the start and end of each transport observation.
- An object with several markings requires the actor to have access to every marking. [OpenCTI marking restriction](https://docs.opencti.io/latest/administration/segregation/)
  - **Design disposition:** marking identities participate only in local authorization/content fingerprints. They are not rendered as Orientation content and never appear in an error.

### Tasks

- The current schema exposes pageable top-level `tasks(first, after, orderBy, orderMode, filters, ...)`; nested `Case.tasks` has no pagination arguments. [Official Task schema](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/src/modules/task/task.graphql#L187-L211)
- The official UI obtains Case Tasks with a top-level Task query and a closed filter containing `entity_type = Task` and `objects = <case internal id>`. [Official Case UI query construction](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-front/src/private/components/cases/case_incidents/CaseIncident.tsx#L48-L59). The backend's Case Task resolver traverses the `object` reference relation. [Official Task domain](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/src/modules/task/task-domain.ts#L42-L44)
  - **Design disposition:** qualify and pin that exact filter against the deployment, use a fixed page size and deterministic order, follow `pageInfo.endCursor` until `hasNextPage` is false, and map only Task ID/name/status/due date/assignee IDs/version fields. A GraphQL error, missing page data, null required field, repeated cursor, page budget, timeout, or actor fingerprint change makes the whole block unavailable/fails safely; no partial Task is returned.

### Object membership

- `Case.objects(first, after, orderBy, orderMode, filters, search, types, all)` is a pageable connection. Its edge carries membership `types`, and its node is a `StixObjectOrStixRelationship`. [Official Case schema](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/src/modules/case/case.graphql#L116-L126)
- The official UI pages this connection and consumes `endCursor`, `hasNextPage`, and `globalCount`. [Official container query](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-front/src/private/components/common/containers/ContainerStixObjectsOrStixRelationshipsLines.tsx#L105-L135)
- Both `StixObject` and `StixRelationship` expose a stable display `representative`, source IDs, type, and timestamps appropriate for the neutral Orientation reference. `Representative` is an object; the live selection must request `representative { main }` rather than treating `representative` as a scalar. [Official object interface](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L2359-L2376), [official relationship interface](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L14308-L14338), [official generated `Representative` type](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/src/generated/graphql.ts#L28781-L28785)
  - **Design disposition:** page `case.objects` directly, map only `representative.main`, preserve membership as `visible_case_object_reference`, and never infer evidence/support/acceptance semantics. Decode object and relationship variants explicitly; unknown variants or missing representative/version data fail mapping rather than falling back to `__typename` or an ID as prose.

### Version sensitivity and pagination strength

- OpenCTI directs consumers to the deployment's Playground/schema because the GraphQL surface is instance-local and evolves. [OpenCTI GraphQL API](https://docs.opencti.io/latest/reference/api/)
  - **Design disposition:** perform introspection before construction, recursively verify the exact return/input `TypeRef` including list and nullability wrappers, and derive runtime possible-type sets for the returned union and both inline-fragment interfaces. Each fragment set must intersect the union set. Canonicalize and hash the selected schema surface and compare it with the expected qualification manifest. A different reported version or incompatible selected type/field/argument/input/enum/union/interface shape fails `schema_or_mapping_mismatch` before any Case body is requested.
- OpenCTI's pagination is stateless `search_after`; the implementation adds a stable-ID tie-breaker, while page-direction booleans are described as approximations. [Official pagination engine](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/src/database/engine.ts#L3181-L3295), [official cursor implementation](https://github.com/OpenCTI-Platform/opencti/blob/6f81b62b2dd95bf77bd3796ccefeb297f99ee73d/opencti-platform/opencti-graphql/src/database/utils.ts#L236-L316)
  - **Design disposition:** cursors prove only traversal continuity. The existing Adapter's start/end root probe and the Workspace's two full observations remain mandatory. The result is a bounded stable actor-view observation, not a native snapshot.

## Exact live query family to qualify

The implementation should own fixed GraphQL documents rather than accept caller-provided query text.

1. **Target/schema qualification:** query `about { version }`, `settings { id platform_url }`, `me { id ...authorization fingerprint fields }`, then the selected introspection surface. Validate recursive return/input `TypeRef`, Case/Task/page shapes, enum values, union/interface kinds, and non-empty runtime overlap between the returned object union and each fixed interface fragment without fetching a Case body. OpenCTI GraphQL has no validation-only endpoint, so the fixed documents are proven statically against introspection and their first execution remains a fail-closed `open` operation.
2. **Root start/end probe:** query `me` plus `case(id)` for the selected identity fields and non-rendered authorization fingerprint. A start root returns either a closed visible result or `not_visible`; an end root additionally must equal the start identity and authorization fingerprint.
3. **Task page:** query top-level `tasks` with the qualified `entity_type` and `objects` filters, fixed order/page size, exact cursor, `pageInfo`, and only Orientation Task plus authorization-fingerprint fields.
4. **Object page:** query `case(id) { objects(...) }`, require the same Case ID, page `pageInfo`, edge cursor/types, and explicit `StixObject`/`StixRelationship` fragments.

Every GraphQL response is a closed wire DTO. Any non-empty `errors` array fails the request even when `data` is also present. Raw HTTP status/body, GraphQL message/path/extensions, token, Case payload, partial page, and authorization fingerprint never cross the Adapter as a public error.

The live transport translates only into the existing closed transport outcomes:

- root: `visible` with normalized Case identity and a local authorization-version digest, or `not_visible`;
- page: one contiguous page with local page identity/index, exact input/output cursor, authorization-version digest, and normalized authorized items; or `incomplete`;
- failures: one existing actor-safe Orientation code.

## Qualification identities

The values in `OrientationSourceIdentityV1` must be derived, not copied from environment labels:

- `instanceId`: qualified `settings.id`, scoped by normalized endpoint origin/base path;
- `adapterArtifactDigest`: digest of the live Adapter mapping version and exact GraphQL documents;
- `targetFingerprint`: digest of normalized endpoint, instance ID, reported OpenCTI version, TLS policy, page/time budgets, and selected query family;
- `schemaDigest`: digest of canonical deployed introspection for every selected type, field, argument, enum, union/interface relationship, and scalar used by the mapping;
- `qualificationId`: digest-addressed qualification identity containing the preceding stable evidence; `qualifiedAt` is separate observation metadata and does not change identity;
- `selectionDigest`: the already closed three-block Orientation selection.

The token and its hashes are not part of these public source identities. `actorRef` comes from `me.id`. The live factory derives `credentialRef` from normalized endpoint, actor, and a stable non-secret credential-slot name. Token rotation within that slot preserves the binding; a change of authority scope requires a new slot name.

## Today's minimal vertical slice

### Must implement

1. A live GraphQL transport Adapter in the CTI Workspace package using Node's built-in `fetch`, an exact endpoint, a credential-provider port, a timeout budget, caller cancellation, strict HTTP/JSON/GraphQL decoding, and no token logging.
2. An async qualification factory that validates target identity, token subject, selected introspection, exact documents, and budgets before returning the existing transport-backed Orientation Adapter and derived actor/source binding.
3. Case, Task, and object mapping with start/end root probes, complete cursor traversal, closed DTO validation, deterministic normalization, and actor-safe errors.
4. Public-seam TDD tests using a local fake GraphQL server/fetch seam; the tests enter only through `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn` and assert no provider call or disclosure on partial/error/drift paths.
5. One explicitly opt-in live smoke test that uses a real OpenCTI Case but a faux Pi model. It must execute `open`, then `prompt`, observe exactly one completed terminal event, confirm that the faux model received a schema-valid Orientation derived from the selected Case, close, and perform a clean reopen. It must not print the token, raw GraphQL body, Case body, or model context.
6. A short operator runbook and final PROGRESS update that label the result `live smoke`, not `production qualified`.

No external GraphQL/HTTP dependency is required; the package already targets Node versions with standards-based `fetch` and `AbortSignal`. TLS verification stays enabled. A private CA must be supplied through normal Node trust configuration; the Adapter must not add an `insecure` certificate switch.

### Can defer

- authenticated OpenCTI stream/notification invalidation;
- a secrets vault or multi-tenant credential registry beyond the small credential-provider Interface;
- real paid-model execution (the faux provider proves the real Pi prompt seam without adding another credential/failure source);
- production qualification of marking/Authorized Members changes, schema upgrades, proxies, HA nodes, and all Case subtypes;
- write paths, strict R1, I&E Retrieval, Working Set, Assessment, and OpenCTI mutation support.

## The one external input

The only user-supplied external input should be one sealed **OpenCTI smoke target bundle**:

```text
OPENCTI_GRAPHQL_URL=<exact POST /graphql endpoint>
OPENCTI_TOKEN=<token for the investigating user>
OPENCTI_CASE_ID=<internal ID of one Case visible to that user>
```

The token user must have `KNOWLEDGE` access and item visibility appropriate for the Case. The smoke derives `actorRef`, instance ID, platform version, schema fingerprint, and Case kind from the deployment. If the target uses a private CA, the process also needs its already-installed Node CA trust; disabling TLS validation is not an accepted input.

No OpenCTI credential is currently present in the repository, and no live target was called during this research.

## Expected file ownership for implementation

Product and tests remain owned entirely by `packages/cti-rag-agent-workspace/`:

- add `src/opencti-graphql-orientation-transport.ts` for HTTP, GraphQL documents, DTO validation/mapping, credential resolution, and qualification;
- modify `src/types.ts` only for the small credential/qualification Interfaces needed by callers;
- modify `src/index.ts` to export the supported live factory and its public input/evidence types;
- add `test/opencti-live-orientation-adapter.test.ts` for deterministic public-seam behavior;
- add one opt-in `test/opencti-live-orientation.smoke.test.ts` (or an equivalently isolated package script) that is skipped unless the explicit live flag and bundle are present;
- modify `package.json` only if an explicit live-smoke script is needed; add no dependency.

Documentation remains owned by `docs/cti-rag/`:

- add an operator runbook under `agent-workspace/`;
- update `agent-workspace/PROGRESS.md` after executable evidence exists;
- change the normative Orientation contract only if implementation evidence requires a different qualification/failure rule. This research does not currently require such a change;
- no ADR is needed for the HTTP Adapter itself because the accepted Orientation contract already owns the Adapter/qualification decision.

## TDD and acceptance plan

The pre-agreed test seam remains `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn`; no test should assert private Adapter maps or calls as proof of Workspace behavior.

### Deterministic red-green slices

1. Qualified single-page real-wire fixture opens and prompts; the model sees only the three normalized Orientation blocks.
2. Multi-page Tasks and objects traverse to terminal pages and normalize deterministically.
3. HTTP 401/403, null root, token-subject mismatch, GraphQL `errors + partial data`, invalid JSON, and schema mismatch invoke no model and disclose no partial body.
4. Repeated cursor, missing page data, page/byte budget, timeout, and aborted/ignored-abort transport invoke no model and emit one safe terminal outcome.
5. Root or actor fingerprint changes between start/end fail; first/second complete observation drift fails.
6. Reopen issues two new observations and does not reuse live payload from Session.

### Opt-in live smoke acceptance

- qualification reports the target version/schema/query digests without secrets;
- the token subject is the Workspace actor;
- `open` completes two full observations of the selected real Case;
- one faux-model `prompt` completes with the expected stable event sequence and one terminal event;
- the captured model input contains a valid `opencti-case-orientation/v1`, but the runner emits only safe identifiers/digests and PASS/FAIL;
- `close` followed by a new `open` rereads the target and completes cleanly;
- invalid token and inaccessible Case are tested only when the user supplies safe negative fixtures; they are not fabricated by modifying the real Case.

## Risks and non-claims

1. **Item-authorization observability remains the largest production risk.** OpenCTI filters by current actor rights, but stock actor-scoped reads do not provide a monotonic authorization revision or a privileged hidden-membership oracle. A successful double read proves a bounded stable actor-visible result, not that no invisible member exists or no change-and-revert occurred. Production qualification of OR-09/OR0B-AD-05/AD-06 requires a dedicated deployment fixture that changes markings/Authorized Members between controlled pages. The live smoke cannot close those cases on an arbitrary real Case.
2. **The official `objects` Task filter is version-sensitive.** It is official UI behavior at the pinned commit, not a timeless API promise. Recursive TypeRef introspection qualifies the fixed filter inputs on the selected deployment; there is no separate validation-only GraphQL probe, so execution failure remains fail closed before Orientation publication.
3. **GraphQL HTTP success is not semantic success.** Partial `data` with `errors` must fail closed.
4. **`globalCount` is not a hidden-item oracle.** It may be useful for actor-view continuity only after deployment qualification; it must not be rendered or used to infer globally hidden counts.
5. **No snapshot claim.** Root probes plus two equal traversals remain bounded-observation evidence only.
6. **No continuous freshness claim.** Without the later live invalidation port, the smoke proves open/reopen reads, not indefinite authorization freshness during a long-lived Workspace.
7. **No real-model claim.** A faux provider intentionally proves the Pi prompt integration without calling a paid provider. A later real-model smoke is separate.
8. **No production qualification claim.** Passing one real Case establishes only that the selected queries, mapping, and public Workspace seam work for that target/actor/Case at that time.

## Delivery decision

The live smoke vertical is feasible today after the single smoke-target bundle is available. It should be the next implementation item before I&E Retrieval. The existing production-shaped Adapter remains the reusable deep Module for pagination/fencing; the new live GraphQL Module supplies the deployment-specific transport and qualification evidence behind that seam.
