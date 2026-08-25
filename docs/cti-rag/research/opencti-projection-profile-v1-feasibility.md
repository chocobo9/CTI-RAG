# OpenCTI Projection Profile v1 Feasibility

Status: primary-source feasibility research for `opencti-case-projection/v1`.

Design disposition (2026-07-20): the full Profile feasibility analysis now supports the frozen strict-R1 target, not the current delivery cycle. The current cycle adopts only the smaller stock-OpenCTI subset in [`opencti-case-orientation/v1`](../agent-workspace/opencti-case-orientation-v1-contract.md). The normative first-slice facade has terminal-only business receipts and an independent opaque `proposalLedgerRevision`; earlier research wording about facade `pending`, a pending-to-terminal transition, or a monotonic receipt sequence is superseded.

Research date: 2026-07-20.

Source baseline: official OpenCTI documentation and official repository commit [`3fe1ce3c1f87e2ad33f370fe358454ffb682ae12`](https://github.com/OpenCTI-Platform/opencti/tree/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12). The production Adapter must additionally pin and introspect its deployed OpenCTI release; this note does not qualify a deployment.

This note refines, rather than replaces, the findings in [OpenCTI Case Read/Write Guarantees](opencti-case-read-write-guarantees.md) and [OpenCTI Projection Authorization, History, and Change Detection](opencti-projection-authorization-history.md).

## Conclusion

Stock OpenCTI can supply useful, actor-authorized source material for the first Projection Profile, but it cannot safely materialize the full semantics of `opencti-case-projection/v1` by itself.

The dividing line is not whether OpenCTI has a text field. It is whether the authority exposes a typed fact with stable identity, current authorization, exhaustive traversal, and a meaning strong enough for the Profile obligation:

- `case_spine`: stock OpenCTI can supply Case identity, kind, name, workflow status, priority/severity, assignees/participants, and timestamps. Investigation purpose and current mandate need a trusted Case Management overlay unless a deployment-specific, conformance-tested policy owns their meaning.
- `scope_and_controls`: markings, Authorized Members, and current access rights are security inputs, but stock OpenCTI has no typed included/excluded investigative scope, time boundary, handling constraint, or prohibited-action model. This block needs Case Management metadata.
- `human_direction`: Notes can carry prose, but stock OpenCTI does not type a Note as a current analyst correction or direction, nor expose its supersession and decision status. This block needs Case Management metadata; arbitrary Note classification is unsafe.
- `accepted_state`: contained knowledge, relationships, Notes, and Opinions are not a typed list of Case-accepted findings, decisions, or negative findings. Acceptance and negative-finding semantics need Case Management metadata.
- `open_work`: Tasks provide the strongest stock mapping: identity, description, workflow status, assignees/participants, and due date. A deployment must still qualify complete Case-to-Task traversal and map configurable workflow statuses. Open question, blocker, and contradiction subtypes need trusted metadata when required.
- `resource_index`: Case `object` membership and contained entities/relationships can supply neutral resource candidates. Exact Case role, Evidence assessment, and availability semantics need Case Management metadata. Membership identity should be the canonical tuple `(instance, case, "object", resource)`, not a reference-relation ID.
- `recent_change`: streams and History can supply bounded hints and audit references, but not a gap-free Case revision or native as-of state. Case Management must own semantic block-key attribution and any stronger continuity claim.
- `proposal_status`: stock GraphQL has no caller-intent receipt or status lookup. This block must come from the Case Management operation ledger/facade.

Consequently, the exact Profile can qualify only when an actor-scoped OpenCTI read Adapter is composed with the required facade-owned semantic overlay. A stock-only orientation profile may be useful, but it must have a different Profile identity and obligations. It must not silently reinterpret missing v1 semantics.

## Evidence boundary

Sections labeled **Source facts** report official documentation or source behavior at the pinned commit. Sections labeled **CTI-RAG inference** describe the contract needed by this project.

OpenCTI's public GraphQL schema is instance-local and active development can change fields and behavior. Official documentation directs API consumers to the deployed GraphQL Playground/schema and source because public mutation examples and a complete static API reference are not provided. [OpenCTI GraphQL API documentation](https://docs.opencti.io/latest/reference/api/)

Negative findings are scoped to the pinned stock public API. They are not claims about a private extension, Enterprise deployment, or future release.

## 1. Source primitives available at the pinned commit

### Source facts

The common `Case` interface exposes:

- internal `id`, `standard_id`, `entity_type`, `name`, `description`, and `content`;
- platform and STIX timestamps including `created_at`, `updated_at`, `x_opencti_modified_at`, `created`, and `modified`;
- markings, organizations, labels, creator, assignees, and participants;
- `authorized_members`, `currentUserAccessRight`, `status`, and `workflowEnabled`;
- paginated `objects(first, after, ...)` and `stixCoreRelationships(first, after, ...)`;
- nested `tasks: TaskConnection!` with no pagination arguments and `notes(first: Int)` with no `after`; and
- files, jobs, Opinions, and other graph-linked material. [Pinned Case schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case.graphql#L1-L169)

Case subtypes add operational fields:

- Incident Response adds `rating`, `response_types`, `severity`, and `priority`. [Pinned Case Incident schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-incident/case-incident.graphql#L164-L175)
- Request for Information adds `information_types`, `severity`, `priority`, request-access fields, and a workflow ID. [Pinned Case RFI schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-rfi/case-rfi.graphql#L168-L181)
- Request for Takedown adds `takedown_types`, `severity`, and `priority`. [Pinned Case RFT schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-rft/case-rft.graphql#L163-L173)

OpenCTI describes Cases as containers for entities and relationships, Tasks as assignable work in a Case, Notes as unstructured analysis/comments, Opinions as handling feedback, and Status as the mechanism for resolution workflows. Status templates and Case templates are configurable taxonomies, not universal CTI-RAG semantics. [Case management documentation](https://docs.opencti.io/latest/usage/case-management/), [workflows and assignment documentation](https://docs.opencti.io/latest/usage/workflows/), [taxonomy administration](https://docs.opencti.io/latest/administration/ontologies/)

A Task exposes IDs, timestamps, markings, authorization-related fields, status, `name`, `description`, `due_date`, assignees, and participants. The top-level `tasks` query is paginated, while the Case field itself has no pagination parameters. Internally, the Case Task resolver traverses the `object` reference relation through `pageRegardingEntitiesConnection`. [Pinned Task schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/task/task.graphql#L1-L208), [pinned Case Task traversal](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/task/task-domain.ts#L22-L44), [pinned Case resolver](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-resolvers.ts#L20-L28)

A Note exposes IDs, timestamps, markings, creator, `attribute_abstract`, `content`, free-text `authors`, `note_types`, and likelihood. The top-level `notes(first, after, filters, ...)` query is pageable, while nested `notes(first)` is not. [Pinned Note type](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L3732-L3900), [pinned Note query](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L15235-L15264). The published OpenCTI taxonomy lists Note types such as `analysis`, `assessment`, `external`, `feedback`, and `internal`; none means “current human direction” or encodes supersession. [OpenCTI taxonomy reference](https://docs.opencti.io/latest/reference/taxonomy/)

An Opinion exposes `opinion`, `explanation`, and free-text `authors`, plus the common object, authorization, and timestamp fields. It does not expose CTI-RAG acceptance, decision, negative-finding, or supersession fields. [Pinned Opinion schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L4196-L4361)

`Status` points to a configurable `StatusTemplate` and exposes type/order/disabled/scope. The template has a name and color. Those fields establish workflow configuration identity, but the schema does not assign a universal “open”, “blocked”, “accepted”, or “terminal” meaning to every template. [Pinned Status schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L600-L646)

Container `objects` returns paginated nodes plus edge `types`; OpenCTI also exposes a pageable `stixRefRelationships` query with source, target, and relationship-type filters. A `StixRefRelationship` has source, target, type, markings, and timestamps. [Pinned object connection](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L13979-L13995), [pinned reference-relationship type](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L14631-L14681), [pinned reference-relationship query](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L15888-L15909)

OpenCTI uses stateless Elasticsearch `search_after` pagination. Cursors contain sort values, a stable-ID tie-breaker is added, and the implementation describes `hasNextPage`/`hasPreviousPage` as approximate. It does not expose a caller-owned point-in-time handle on this path. [Pinned search-after construction](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/engine.ts#L3099-L3105), [pinned sorting and search-after](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/engine.ts#L3155-L3217), [pinned cursor/page implementation](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/utils.ts#L226-L300)

Identifiers do not supply a Case-wide version. Internal IDs are UUIDv4; many STIX standard IDs use type-specific UUIDv5 inputs, while reference relationships get random standard IDs. ID-contributing field changes can lead to a new standard ID and merge handling. [Pinned identifier generation](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/schema/identifier.js#L481-L519), [pinned standard-ID update handling](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/middleware.ts#L2506-L2539)

### CTI-RAG inference

The Adapter must treat all OpenCTI timestamps, IDs, page cursors, and stream positions as observation evidence. None is a native `CaseRevision`. Each projected item needs an Adapter-scoped logical reference, all source IDs needed for later canonicalization, a canonical digest of the fields actually used, and the authorization/fence evidence under which it was observed.

## 2. Block-by-block feasibility

| Block | Stock material safely available | Mandatory qualification or facade contribution | Stock-only verdict |
|---|---|---|---|
| `case_spine` | Case IDs, kind, name, status identity, priority/severity, assignees/participants, timestamps | status-template semantics; investigation purpose; current mandate; identity canonicalization after merge | partial |
| `scope_and_controls` | current Case markings, organizations, Authorized Members/access right, RFI access configuration | typed include/exclude scope, time bounds, handling constraints, prohibited actions, authorized control limitations | insufficient |
| `human_direction` | candidate Note/Task/Case prose with provenance | explicit direction/correction kind, current/superseded status, supersedes reference, author role, effective time | insufficient |
| `accepted_state` | candidate Case objects, semantic relationships, Notes, Opinions, workflow status | explicit acceptance authority, finding/decision/negative-finding kind, scope, status, supersession | insufficient |
| `open_work` | Tasks with identity, text, status, assignees/participants, due date | exhaustive Case membership traversal; workflow semantic map; typed question/blocker/contradiction where needed | conditionally feasible |
| `resource_index` | Case `object` members, graph objects/relationships, markings, source metadata | Case role, Resource version contract, Evidence assessment, availability, provenance summary policy | conditionally feasible |
| `recent_change` | actor-filtered stream events; optional History/log records; object timestamps | semantic affected-block mapping; continuity classification; Case revision; durable archive if stronger history is claimed | hints only |
| `proposal_status` | current membership predicate and ordinary entity history at best | operation ID/request digest ledger, expected revision, disposition, receipt revision, terminality and proof retention | unavailable |

The corresponding identity/version/authorization/traversal evidence is:

| Block | Stable Profile identity | Version evidence | Authorization evidence | Traversal/completeness evidence |
|---|---|---|---|---|
| `case_spine` | instance-scoped Case logical reference retaining internal and standard IDs | canonical selected-field digest + all observed timestamps + facade Case/overlay revision | actor-scoped root read, Case markings/organizations/Authorized Members/access right, end re-read | one root plus identical bounded end/stability probes; no native snapshot claim |
| `scope_and_controls` | facade control ID/version; referenced OpenCTI security-object IDs where applicable | facade control-set revision and per-record semantic digest | current actor/purpose policy plus referenced marking/member/control visibility | exhaustive facade control query at one overlay revision; security revalidation at end |
| `human_direction` | facade direction ID with stable source Note/Task reference | facade record revision, effective status, supersession edge, source object digest | direction record and source independently authorized; author/role disclosed only when allowed | exhaustive overlay query; every selected source reference resolves under the same fence |
| `accepted_state` | facade accepted-record ID and stable cited Resource/Evidence references | acceptance revision/status/supersession plus cited exact Resource versions | accepting authority and cited bodies independently authorized | exhaustive overlay query; all required citations resolve; no acceptance inferred from stock lists |
| `open_work` | scoped Task ID plus Case-membership tuple, or facade work-item ID | Task canonical digest/timestamps, status-template identity, optional facade work revision | Task, membership, owner, dependencies, and referenced bodies independently authorized | qualified top-level Case-related Task pagination with terminal-page and repeated-set evidence |
| `resource_index` | scoped Resource ID and `(case, "object", resource)` membership tuple; separate assessment ID | separate Resource, membership, role, and Evidence-assessment digests/revisions | membership, Resource/relation, endpoints, provenance, and assessment independently authorized | exhaustive `objects`/reference-relation traversal with de-duplication and repeated membership fingerprint |
| `recent_change` | facade change ID or scoped OpenCTI stream/log reference | facade change revision; source event ID/schema/digest as bounded corroboration | event/log read is principal/filter scoped; actor/time fields independently disclosure-checked | cursor/filter continuity and retained range recorded; gap yields `continuity_lost`, never silent completeness |
| `proposal_status` | facade operation/proposal ID bound to request digest | independent proposal-ledger revision and terminal disposition | current proposal-disclosure authority or narrow recovery authority | exhaustive ledger lookup for the exact operation key; OpenCTI predicate/history is corroboration only |

### 2.1 `case_spine`

**Problem solved:** orient the model and analyst to the authoritative Case without exposing storage-specific objects.

**Required semantic obligations:** a stable Case reference scoped to the OpenCTI instance; Case kind; display reference; current lifecycle state; bound investigation purpose; current mandate; and provenance/version evidence for every value.

**Stock inputs:** `id`, `standard_id`, `entity_type`, `name`, common timestamps, `status`, subtype fields, assignees, and participants.

**Boundary:** `description` or `content` may be preserved as authorized source narrative, but their mere presence does not prove that the text is the current mandate or investigation purpose. A renderer or LLM may not promote prose to authoritative typed fields.

**Facade-owned inputs:** a purpose binding and mandate record with its own stable identity, revision, status, and effective interval. A deployment-specific convention may supply these instead only if the convention is versioned, closed, and passes fixtures proving that all writers maintain it.

**Identity/version evidence:** `{instanceId, internalId, standardId, entityType}` plus canonicalized observed fields, source timestamps, Case Management revision when present, and alias/merge resolution. Equal timestamps are not sufficient; the semantic digest covers every projected field.

**Failure behavior:** unresolved Case identity, unknown subtype, unknown status mapping, missing mandatory overlay, or drift during the fence makes the block `unavailable`; the Adapter must not fabricate a generic mandate from the Case name.

### 2.2 `scope_and_controls`

**Problem solved:** prevent the Agent from operating outside the Case's declared investigative and handling boundaries.

**Required semantic obligations:** explicitly included and excluded scope, time bounds, handling constraints, prohibited actions, and authorized control limitations, each with source authority and effective status.

**Stock inputs:** markings, organizations, Authorized Members, `currentUserAccessRight`, and RFI request-access configuration can constrain what the current principal may read or do. OpenCTI specifies that access to a multiply marked object requires access to every marking and that Authorized Members restrictions on a container do not cascade to contained entities. [Marking restriction documentation](https://docs.opencti.io/latest/administration/segregation/), [Authorized Members documentation](https://docs.opencti.io/latest/administration/authorized-members/)

**Boundary:** security controls are authorization dependencies, not substitutes for investigative scope. An allowed marking does not mean an entity is in scope; Case membership does not mean an action is permitted; absence from the actor's result does not prove global exclusion.

**Facade-owned inputs:** typed scope/control statements and their revision/supersession metadata. The overlay may reference OpenCTI objects, marking definitions, organizations, or time intervals, but it owns the Case-specific meaning.

**Failure behavior:** missing overlay makes this required block `unavailable`. Authorization loss immediately invalidates and hides affected protected values; there is no stale allowance.

### 2.3 `human_direction`

**Problem solved:** give current human corrections and directions precedence over model inference and obsolete instructions.

**Required semantic obligations:** direction/correction kind; authoritative body or protected reference; current/superseded/withdrawn state; explicit supersedes target when applicable; stable decision reference; author role; effective time; and scope.

**Stock inputs:** Notes, Tasks, Case description/content, creators, authors, and timestamps are candidate source material. OpenCTI itself describes Notes as unstructured comments/analysis. The Note schema and vocabulary do not encode direction authority or supersession.

**Boundary:** `note_types = internal`, a Note author name, recent modification time, a Task assignment, or imperative prose is not a trusted direction classifier. An LLM cannot decide which Note overrides another and then feed that decision back as Case authority.

**Facade-owned inputs:** an explicit human-direction record or an owner-qualified metadata convention bound to the source Note/Task and to a stable actor/role identity. Supersession must be a typed edge, not inferred from chronology or text similarity.

**Failure behavior:** no declared directions after an exhaustive overlay query yields `empty`; inability to query or validate the overlay yields `unavailable`. Unclassified Notes remain Resource or narrative references and do not enter this block.

### 2.4 `accepted_state`

**Problem solved:** distinguish authoritative Case outcomes from raw intelligence, candidate findings, opinions, and model proposals.

**Required semantic obligations:** finding/decision/negative-finding type; statement or protected reference; acceptance authority; scope; current/superseded/rejected state; effective time; stable reference; and provenance.

**Stock inputs:** Case-contained entities and relationships, Notes, Opinions, status, and provenance may be cited by an accepted record. They do not establish acceptance. OpenCTI's Case documentation says containers accumulate intelligence context and Opinions collect feedback/lessons learned; it does not state that container membership or an Opinion is an accepted finding. [Case management documentation](https://docs.opencti.io/latest/usage/case-management/)

**Boundary:** graph presence is not truth acceptance. Workflow completion is not finding acceptance. Absence of an object, event, or match is not a negative finding. An imported object is knowledge-base state, not proof that an analyst accepted a Case conclusion.

**Facade-owned inputs:** typed acceptance/decision records. Negative findings require their searched scope, method/evidence basis, time, and accepting authority; they cannot be synthesized from an empty OpenCTI query.

**Failure behavior:** exhaustive overlay with no accepted records yields `empty`; missing overlay or an unresolved accepted-record source yields `unavailable` for this required block. The Adapter must never fall back to “all Case objects are accepted.”

### 2.5 `open_work`

**Problem solved:** expose current work, ownership, deadlines, open questions, blockers, and contradictions without mistaking completed or hidden Tasks for active work.

**Required semantic obligations:** stable work-item identity; kind; current lifecycle state; title/body or protected reference; owner; deadline; blockers/dependencies; and provenance.

**Stock inputs:** Task IDs, name, description, status/template, assignees/participants, due date, markings, creator, and timestamps provide a viable generic `task` work-item mapping.

**Qualification requirement:** the Adapter must demonstrate an exhaustive actor-scoped Case Task traversal. `case.tasks` has no `first`/`after` arguments even though its resolver uses a paginated domain function. A top-level filtered `tasks(first, after, filters)` traversal is plausible, but the exact Case-membership filter and its completeness must be proven against the selected deployment. OpenCTI documents that query filter keys include registered relation input names; filter behavior and schema validation are version-dependent. [Filter documentation](https://docs.opencti.io/latest/reference/filters/)

The deployment must also bind every relevant Status template ID/revision to CTI-RAG states such as active, blocked, completed, or unknown. Names and ordering alone are configuration, not stable semantics.

**Facade-owned inputs:** explicit `question`, `blocker`, or `contradiction` kinds; inter-work-item dependencies; and any state not represented by a qualified Task/status convention.

**Identity/version evidence:** scoped Task IDs, Case-membership tuple, status/template identity, canonical Task digest, source timestamps, and authorization evidence. A Task that remains independently visible after Case access loss may remain an I&E Resource, but its old Case role is removed.

**Failure behavior:** a failed or truncated traversal is `unavailable`, not `empty`. One inaccessible Task must not leak its identifier, type, or count. Unknown workflow semantics keep that item unavailable or explicitly `unknown`; they are not treated as open.

### 2.6 `resource_index`

**Problem solved:** expose compact references to Case-relevant Intelligence Resources and assessed Evidence without injecting entire graph bodies.

**Required semantic obligations:** stable Resource reference and exact Resource version; Case role; resource/evidence distinction; provenance summary; current availability; and the source membership/assessment reference.

**Stock inputs:** exhaustive `objects` traversal and, where needed, `stixRefRelationships(fromId: case, relationship_type: ["object"])` can observe neutral membership. Each entity/relationship exposes independent IDs, markings, timestamps, and provenance fields. Semantic `StixCoreRelationship` edges are distinct from neutral `object` membership.

**Boundary:** a Case's `object` reference says the object is contained/referenced. It does not establish a CTI semantic edge, an Evidence assessment, an accepted finding, or a purpose-specific role. The Adapter must independently authorize the membership relationship, member, relationship endpoints, and any provenance it projects.

**Facade-owned inputs:** Case role, Evidence Reference assessment, exact Resource-version contract, provenance-summary disclosure policy, and availability/revocation status when these are stronger than current OpenCTI visibility.

**Identity/version evidence:** use `{instanceId, caseCanonicalId, "object", resourceCanonicalId}` as the membership key and retain both endpoint ID sets. Reference-relationship IDs are unsuitable as durable semantic membership identities because their standard IDs are randomly generated at creation. The Resource digest is separate from the membership digest.

**Failure behavior:** concurrent membership drift, pagination uncertainty, inaccessible endpoint, merge ambiguity, or missing role overlay prevents a complete selected block. A hidden member does not appear as a count or placeholder unless OpenCTI explicitly authorizes disclosure of that metadata.

### 2.7 `recent_change`

**Problem solved:** orient the user to authoritative recent changes and drive invalidation without replaying an entire Case.

**Required semantic obligations:** stable change reference; affected semantic block keys; actor/time only when authorized; change class; continuity classification; and an explicit statement that current state remains authoritative.

**Stock inputs:** authenticated stream events contain create/update/delete/merge data and stream IDs; History/logs may contain knowledge changes. Streams are rights-filtered, resumable from a position, and subject to configurable trimming. History is asynchronously materialized, can be disabled, and can be removed by retention. [Streaming documentation](https://docs.opencti.io/latest/reference/streaming/), [pinned History manager](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/manager/historyManager.ts#L143-L346), [retention documentation](https://docs.opencti.io/latest/administration/retentions/)

**Boundary:** a stream ID is not a Case revision; filtered event absence is not no-change proof; `recover` is current-state recovery, not as-of replay; a deletion-like notification can mean deletion or visibility loss. [Notifications documentation](https://docs.opencti.io/latest/usage/notifications/)

**Facade-owned inputs:** mapping from authoritative operations/change records to Profile block keys, continuity over the facade ledger, and durable change references. Stock events can be attached as corroborating source evidence.

**Failure behavior:** cursor gaps, `no-recover`, unknown schemas, authorization/filter changes, incomplete cascade/merge context, or History loss force a current rebase of the affected authority partition. The block may be `unavailable` or contain only a truthful `continuity_lost` record; it must not imply a complete recent history.

### 2.8 `proposal_status`

**Problem solved:** expose authoritative terminal proposal status while representing timeout or missing response as local transport knowledge, without leaking request bodies or mistaking graph state for operation identity.

**Required semantic obligations:** immutable operation/proposal identity; request digest; actor/Case scope; capability identity; expected Case revision; disposition; terminality; receipt revision; remote effect reference; synchronization state; and proof-retention metadata.

**Stock inputs:** ordinary entity/relation state and optional History can corroborate that an effect currently exists. They cannot attribute the effect to a CTI-RAG request.

**Source limitation:** the reviewed public mutations return an entity, relationship, ID, or Boolean. The schema/source audit found no durable caller-intent ledger or status query keyed by `clientMutationId` or equivalent. `clientMutationId` appears in some inputs, but no stock persistence/replay/status contract was found. [Pinned Container mutations](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql#L16193-L16203), [pinned inert form metadata handling](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/form/form-bundle-builder.ts#L20-L39)

**Facade-owned inputs:** the entire authoritative proposal/receipt record.

**Failure behavior:** absence of a receipt is not rejection or no effect. If the facade ledger is unavailable, the block is `unavailable`; a prior terminal receipt may be rendered only from retained, integrity-checked receipt data and under current disclosure policy.

## 3. Exact schema obligations without freezing a transport DTO

The Profile manifest should define closed semantic schemas while allowing the OpenCTI Adapter to change GraphQL query composition. The obligations below describe what must validate, not TypeScript field names or a wire layout.

### Projection-wide obligations

Every candidate must bind:

1. exact Profile ID, version, and manifest digest;
2. catalog and deployment activation digests;
3. OpenCTI instance identity, pinned API/version evidence, and introspected schema digest;
4. actor, tenant, purpose, and authorized-view scope through non-model-controlled references;
5. Case logical identity and Case Management revision, when available;
6. selected optional blocks and a deterministic selection digest;
7. one envelope for every Profile-declared block, including unselected and unavailable blocks;
8. start/end fence evidence and each traversed collection's page evidence;
9. projection semantic digest distinct from renderer/output digest; and
10. an observation time and explicit freshness/continuity classification.

Unknown top-level or block fields, duplicate semantic identities, unsupported presence states, mixed source/facade revisions, invalid digests, and omitted block envelopes fail closed.

### Block-envelope obligations

Each block envelope must provide:

- the exact block type and semantic role;
- one allowed presence state;
- a source revision/reference appropriate to the owning authority;
- deterministic semantic digest, including the presence state;
- security-label references or a non-disclosing authorization fingerprint outside model-visible content;
- zero or more typed Resource references; and
- block-local completeness and continuity evidence.

Every populated list item must have a stable Profile identity, semantic kind, current status, authoritative source reference, source version/digest, deterministic ordering key, and provenance sufficient to reproduce the mapping. Raw OpenCTI GraphQL objects are not valid Profile payloads because their incidental fields, nullability, and nested authorization behavior are not the Profile contract.

### Block-specific obligations

| Block | Closed payload must distinguish at minimum |
|---|---|
| `case_spine` | scoped Case reference, kind, display reference, lifecycle, purpose, mandate, ownership, source origin per field |
| `scope_and_controls` | include/exclude scope, time bounds, handling constraint, prohibited action, control limitation, effective/superseded status |
| `human_direction` | correction/direction, body/reference, author role, effective time, current/superseded/withdrawn state, supersedes edge |
| `accepted_state` | finding/decision/negative finding, statement/reference, accepting authority, scope, current/superseded/rejected state, evidence references |
| `open_work` | task/question/blocker/contradiction, lifecycle, owner, deadline, dependency/blocker references |
| `resource_index` | Intelligence Resource/Evidence Reference, Case role, exact Resource version, membership/assessment reference, provenance summary, availability |
| `recent_change` | change reference/class, affected block keys, authorized actor/time, continuity status, source evidence |
| `proposal_status` | proposal/operation reference, capability, request digest reference, disposition, terminality, receipt revision, effect/sync status |

No schema may infer omitted values using “safe defaults.” In particular, missing `accepted_state` is not empty, missing scope is not unrestricted, missing status is not active, and missing proposal receipt is not rejected.

## 4. Trusted binder inputs

The model may request a task and optional semantic blocks, but it must not supply or override the following binder values:

- OpenCTI instance/tenant and canonical Case identity resolution;
- actor credential or verified impersonation, actor status, purpose, and policy scope;
- Profile, catalog, activation, Adapter qualification, and renderer identities/digests;
- required-block set and the allowed optional-block selection policy;
- Case Management revision and facade-overlay revision;
- source schema digest and permitted GraphQL traversal recipes;
- page size/max-page/byte/time budgets and deterministic ordering;
- read-attempt identity, start cursor, dirty-event interval, and fence policy;
- authorization fingerprint inputs and non-disclosure policy;
- canonicalization/digest profile and dependency-key templates; and
- previous Projection receipt used only as a comparison basis.

The Adapter may accept a model-produced search phrase or focus after trusted validation, but that value cannot redefine completeness. A focused query produces `not_selected` material outside its declared selection; it cannot produce an “empty complete Case” claim.

## 5. Start/end fence and materialization protocol

### Problem solved

OpenCTI's independently resolved, statelessly paged queries can span concurrent data and authorization changes. The fence prevents a known mixed observation from being installed as the active Projection.

### Required input

Pinned Adapter/schema qualification, actor/purpose binding, resolved Case identity, Profile/selection, facade overlay revision, current stream/filter cursor when available, budgets, and previous receipt.

### Protocol

1. **Admission:** verify the exact Profile and Adapter activation, schema digest, lifecycle, actor account/purpose, and required facade overlay availability.
2. **Start authorization probe:** read the Case root under the investigating actor; capture current access right, markings/organizations, Authorized Members activation/reference state when authorized, object identity/timestamps, and an authorization fingerprint. Do not render member lists merely because the Adapter needs them for fencing.
3. **Start data probe:** canonicalize all projected Case root fields and capture the facade Case/overlay revision. Record the authenticated stream cursor or an explicit `no_cursor_guarantee` classification.
4. **Stage traversals:** execute each Profile-declared collection traversal with fixed filters/order/page size. Record every cursor, item identity/digest, page count, duplicates, and terminal page evidence. Independently authorize each returned object, relationship, endpoint, Task, Note, author, and reference.
5. **Build blocks:** join only typed owner-qualified overlay records to current authorized OpenCTI references. Validate closed schemas and compute item/block semantic digests outside active state.
6. **End authorization probe:** re-read the Case root and current actor access; reject on any access, marking, organization, Authorized Member, account, policy, or purpose change. A deletion-like/unauthorized result is `deleted_or_visibility_lost`, not a tombstone.
7. **End data probe:** repeat the root canonicalization, facade revision check, and every collection fingerprint required by the qualified recipe. Reject if any source identity/digest, membership set, overlay revision, or intersecting dirty event changed.
8. **Bounded stability pass:** because one repeated head cannot prove independently paged collection stability, a qualified stock Adapter should require two complete, identical authorized observations within budget, or a facade-provided stronger snapshot fence. Any drift restarts only the affected Projection target/partition.
9. **Atomic publish:** install all block envelopes, derivation edges, semantic/render receipts, and evidence together. A candidate never partially updates the active Projection.

### Output and boundary

The output is evidence of a bounded current authorized observation for the exact actor/purpose/Profile. It is not a native OpenCTI snapshot, transaction, Case-wide monotonic revision, global completeness claim, or historical reconstruction.

Even two identical passes cannot exclude an unobserved change-and-revert between probes. Without a cooperating facade or underlying snapshot primitive, the Adapter must label the strength accurately and must not activate capabilities whose risk contract requires stronger point-in-time proof.

### Failure behavior

- timeout/page error/truncation: publish nothing; selected affected block is `unavailable` only in a new complete candidate if the Profile permits it;
- data drift: discard staging and retry the affected target within budget;
- authorization drift/revocation: discard staging, purge protected cached/rendered content, and reopen under current authority;
- cursor gap or unknown event schema: mark continuity lost and perform a current full rebase;
- facade revision drift: discard the joined candidate; never combine old overlay semantics with new OpenCTI state;
- repeated instability: return an explicit retryable unavailable result, preserving the previous Projection only under its separate freshness policy.

## 6. Presence and completeness decisions

Presence is an explicit result of the selected Profile contract; it is not inferred from nulls or missing GraphQL fields.

### `populated`

Use only when the selected block's schema validates and it contains at least one semantic value/item. All required joins, authorization checks, pagination, digests, and fences must have completed.

### `empty`

Use only when:

1. the block was selected/required;
2. every declared source and facade query completed exhaustively;
3. the end fence passed; and
4. zero authorized semantic items remain.

`empty` means “empty in this actor/purpose/Profile authorized view.” It never means no globally hidden material exists. A filtered or failed query, missing overlay, nested unpageable connection, or lost cursor cannot produce `empty`.

### `redacted`

Use only when the current actor is authorized to know that this semantic block exists but not to receive its body, and the disclosure code itself is allowed by policy. The envelope must not reveal hidden identifiers, names, types, counts, labels, topology, provenance, markings, or actor identities.

Stock OpenCTI generally filters inaccessible results rather than supplying a non-leaking, positive redaction receipt. Therefore query absence alone cannot produce `redacted`. When visibility loss cannot be distinguished from deletion, purge the body and retain the operational reason `deleted_or_visibility_lost`; expose a redacted block only if the owner policy separately authorizes that disclosure.

### `not_applicable`

Use only when the exact Profile schema declares a closed Case-kind or lifecycle rule making the block semantically inapplicable, and the binder—not the model or renderer—proved that rule. Do not use it for missing data or missing Adapter support.

### `not_selected`

Use only for a Profile-optional block that the trusted selection plan omitted before dispatch. It is not a failure and makes no statement about content. A model may request selection, but the binder owns the final allowed selection and its digest.

### `unavailable`

Use when a selected/required block cannot be safely materialized because a required source, overlay, schema, authorization-safe traversal, fence, or Adapter guarantee is absent or failed. Include only a closed non-sensitive reason code and retryability. Never include leaked remote errors or partial payloads.

### Projection completeness

`complete` means that every Profile-declared envelope is present, every selected/required block is in a manifest-allowed state, and all current authorization/data fences passed. It is completeness of the current authorized semantic view, not closure of the global OpenCTI graph.

## 7. Conformance fixtures

Production and in-memory Adapters should run the same fixtures. A fixture records the pinned source schema, actor/purpose, facade overlay, page/event schedule, expected envelopes/digests, and expected evidence; it must not depend on a real paid service during ordinary tests.

| ID | Setup/fault | Required outcome |
|---|---|---|
| PF-01 | Incident Response with stock identity/status/priority and valid mandate/purpose overlay | populated `case_spine`; every field records stock or facade origin |
| PF-02 | RFI and RFT with subtype fields | kind-specific fields map without treating request access or takedown type as universal purpose/scope |
| PF-03 | Case name/content present, mandate overlay missing | `case_spine` unavailable; narrative is not promoted to mandate |
| PF-04 | markings and Authorized Members present, scope overlay missing | `scope_and_controls` unavailable; security inputs still fence all blocks |
| PF-05 | internal Note containing imperative prose but no direction metadata | Note excluded from `human_direction`; exhaustive overlay yields empty |
| PF-06 | two directions with an explicit supersedes edge | only current direction is authoritative; superseded record remains provenance, with deterministic digest |
| PF-07 | Case contains entity, relationship, Note, and Opinion but no acceptance record | `accepted_state` empty, never populated from containment/opinion alone |
| PF-08 | accepted negative finding lacks searched scope or accepting authority | block validation fails/unavailable; empty query is not a negative finding |
| PF-09 | multiple paginated Tasks with qualified status mapping | exhaustive, deterministic `open_work` with owners/deadlines and page evidence |
| PF-10 | nested `case.tasks` returns fewer Tasks than exist | Adapter does not claim empty/complete; qualification fails until an exhaustive traversal is proven |
| PF-11 | unknown or renamed Status template | affected Task state is unknown/unavailable, not guessed from name/order |
| PF-12 | member remains visible but Case membership is removed mid-pagination | staged `resource_index` is rejected and affected target restarts |
| PF-13 | duplicate member across page drift | de-duplicate by canonical identity, detect fingerprint drift, publish no mixed candidate |
| PF-14 | member visible but membership relationship marking is inaccessible | no member role/edge is projected and no hidden-edge metadata leaks |
| PF-15 | member standard ID changes through merge | alias resolution updates scoped reference; old/new IDs do not create two resources |
| PF-16 | stream cursor is trimmed or recovery says `no-recover` | `recent_change` records continuity loss or is unavailable; current affected partition rebases |
| PF-17 | deletion-like event followed by unauthorized read | purge protected body; classify operationally as `deleted_or_visibility_lost`, not confirmed deletion |
| PF-18 | History manager disabled/lagging | absence does not imply no recent change; current Projection correctness remains read-based |
| PF-19 | facade commits one new terminal proposal ledger row and returns its resulting `proposalLedgerRevision` | `proposal_status` changes only in a complete Profile carrying that exact ledger revision; duplicate replay does not advance it and no request body is rendered |
| PF-20 | OpenCTI membership exists but facade receipt is absent after timeout | do not attribute effect to proposal; proposal status remains unknown/unavailable |
| PF-21 | actor loses one required marking between pages | end authorization fence fails; no candidate or partial block enters active state |
| PF-22 | actor removed from Case Authorized Members after all pages return | end fence rejects late candidate and purges old Case-derived model context |
| PF-23 | contained Resource remains independently authorized after Case revocation | old Case role is removed; disjoint Resource capsule may remain usable outside this Case chain |
| PF-24 | selected optional block times out | only if Profile permits `unavailable`, publish a complete candidate with that explicit envelope; dependents requiring it stay unavailable |
| PF-25 | optional block omitted by selection | emit `not_selected`; do not issue source query and do not imply emptiness |
| PF-26 | hidden objects are silently filtered by OpenCTI | authorized visible set may be empty, but payload and UI disclose no hidden count/type/topology |
| PF-27 | renderer changes with identical semantics | semantic digests remain equal; render digest changes |
| PF-28 | facade overlay revision changes during OpenCTI traversal | reject joined candidate even when OpenCTI root/timestamps are unchanged |
| PF-29 | two full passes match, but no native snapshot exists | receipt states bounded stable observation, not OpenCTI snapshot/as-of guarantee |
| PF-30 | GraphQL schema digest differs from qualified deployment | exact Profile activation fails closed; no opportunistic field fallback |

## 8. Activation requirements

An Adapter activation for the exact Profile must demonstrate:

1. actor-equivalent authentication or verified owner-supported impersonation;
2. closed field selections for every OpenCTI source type used;
3. complete Case Task, Note, object-membership, and relationship traversal recipes actually required by selected blocks;
4. item-level authorization and non-disclosure behavior, including relationship endpoints;
5. deterministic canonicalization and identity/merge handling;
6. bounded start/end fence behavior under concurrent changes;
7. facade-overlay revision fencing and join behavior;
8. stream/history limitations and cursor-gap recovery;
9. all block presence-state fixtures; and
10. exact expected schema/version/feature evidence.

Qualification is per guarantee and per block. Failure of `proposal_status` or `recent_change` support must not disable a separately qualified read of `case_spine`; failure of a required core block prevents opening the exact Profile but does not freeze unrelated Workspace or I&E partitions.

A source-controlled Profile definition that is structurally or semantically invalid is a build/start failure. A deployment that lacks an optional remote guarantee disables only the affected block/capability. These two failure classes must not be conflated.

## 9. Unknowns that require a deployment spike

The following are not established by the pinned schema or official documentation:

- whether a single GraphQL operation observes one stable backend snapshot across all Case fields and resolvers;
- a public actor-visible authorization revision or lease;
- an authoritative, complete fingerprint of the actor's effective capabilities, group/role membership, organizations, markings, and Authorized Members state;
- the exact public top-level filter that exhaustively returns every Task/Note related to one Case, including behavior at high cardinality;
- whether every Case `object` membership relationship and its markings can be enumerated without a visibility gap while endpoints are independently filtered;
- how the selected deployment reports authorization loss for an edge whose endpoint remains visible;
- whether status-template IDs and meanings are stable under administration/import across environments;
- whether any local convention already gives Notes or custom fields typed direction/acceptance/scope semantics;
- whether the selected stream/filter emits all policy, Authorized Member, organization, merge, and membership changes needed by the fence;
- whether a retained archive stronger than Redis stream/History retention exists;
- whether exact historical actor-authorized reads are supported by a private/Enterprise extension; and
- whether the Case Management facade can issue one revision covering both overlay state and all OpenCTI writers, or must expose separate fenced revisions.

Until these are proven, the conservative behavior in this note is mandatory.

## 10. Guarantees the Profile must not claim

The exact Profile must not claim:

- that Case container access authorizes contained objects or relationships;
- that an authorized view is the global Case graph;
- that an empty authorized result proves global absence;
- that Case `description`, `content`, a Note, Task, or Opinion has a CTI-RAG semantic role without typed owner metadata;
- that membership means accepted truth, Evidence assessment, or a semantic STIX relationship;
- that status name/order universally means open, blocked, accepted, or terminal;
- that `updated_at`, `modified`, a cursor, stream ID, or canonical digest is a native Case revision;
- that two matching reads are an OpenCTI MVCC snapshot;
- that event or History absence proves no change or no remote effect;
- that a deletion-like signal proves deletion rather than visibility loss;
- that reference-relation identity is stable across delete/re-add or merge;
- that current predicate presence identifies the request that caused it;
- that stock OpenCTI supports exact proposal status, request idempotency, or expected-revision writes; or
- that previously authorized content remains model-usable after current authorization is revoked.

## 11. Recommended design decision

Keep `opencti-case-projection/v1` as a semantic Case Management contract, not an OpenCTI-shaped DTO.

For the first vertical slice:

1. qualify stock OpenCTI only as the actor-scoped current-data source for the specific fields and traversals proven by fixtures;
2. require facade-owned, revisioned metadata for purpose/mandate, scope/controls, human direction, accepted state, Case roles/assessments, semantic recent-change attribution, and proposal status;
3. allow a Task-backed generic work-item mapping only after complete Case Task traversal and status semantics pass deployment conformance;
4. identify neutral Case membership by the canonical endpoint/type tuple and keep membership, Resource, Evidence assessment, and accepted finding as separate facts;
5. publish only atomically fenced, explicit block envelopes and label the read as a bounded current authorized observation; and
6. if a stock-only read-only experience is needed before the overlay exists, define a separate smaller Profile rather than weakening or ambiguously populating v1.

This keeps the profile implementable and testable while preserving the main safety rule: failure, timeout, or uncertainty freezes only the dependency chains that actually consume the unavailable block or unresolved authority partition.

## Primary sources reviewed

- [OpenCTI GraphQL API](https://docs.opencti.io/latest/reference/api/)
- [OpenCTI Case management](https://docs.opencti.io/latest/usage/case-management/)
- [OpenCTI Workflows and assignment](https://docs.opencti.io/latest/usage/workflows/)
- [OpenCTI Taxonomies](https://docs.opencti.io/latest/administration/ontologies/)
- [OpenCTI Taxonomy reference](https://docs.opencti.io/latest/reference/taxonomy/)
- [OpenCTI Filters](https://docs.opencti.io/latest/reference/filters/)
- [OpenCTI Marking restriction](https://docs.opencti.io/latest/administration/segregation/)
- [OpenCTI Authorized Members](https://docs.opencti.io/latest/administration/authorized-members/)
- [OpenCTI Data Streaming](https://docs.opencti.io/latest/reference/streaming/)
- [OpenCTI Notifications and alerting](https://docs.opencti.io/latest/usage/notifications/)
- [OpenCTI Retention policies](https://docs.opencti.io/latest/administration/retentions/)
- [Pinned OpenCTI Case interface](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case.graphql)
- [Pinned Incident Response Case schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-incident/case-incident.graphql)
- [Pinned RFI Case schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-rfi/case-rfi.graphql)
- [Pinned RFT Case schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/case/case-rft/case-rft.graphql)
- [Pinned OpenCTI Task schema/domain](https://github.com/OpenCTI-Platform/opencti/tree/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/modules/task)
- [Pinned generated Note, Opinion, Status, relation, and Query schema](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/config/schema/opencti.graphql)
- [Pinned OpenCTI pagination engine](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/engine.ts)
- [Pinned OpenCTI pagination utilities](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/database/utils.ts)
- [Pinned OpenCTI identifier implementation](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/schema/identifier.js)
- [Pinned OpenCTI History manager](https://github.com/OpenCTI-Platform/opencti/blob/3fe1ce3c1f87e2ad33f370fe358454ffb682ae12/opencti-platform/opencti-graphql/src/manager/historyManager.ts)
