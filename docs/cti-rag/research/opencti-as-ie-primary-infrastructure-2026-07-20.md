# OpenCTI as the Primary Infrastructure for Intelligence and Evidence

Status: primary-source research and non-normative design input.

Research date: 2026-07-20.

Source baseline: current OpenCTI documentation and the synchronized OpenCTI
Platform and Connector releases `7.260715.0`. A deployed instance's reported
version, edition, enabled managers, Connector configuration, and introspected
schema remain decisive.

## Question and verdict

Can OpenCTI be the main intelligence-data infrastructure while Intelligence and
Evidence (I&E) remains a smaller Agent-specialized Module instead of rebuilding a
second CTI platform?

**Yes, with a strict authority split.** OpenCTI already owns the hard general CTI
infrastructure: STIX-oriented graph data, ingestion Connectors, worker-based STIX
processing, files, analyst Workbenches, enrichment, identity consolidation,
marking-aware authorization, GraphQL/filter access, and change streams. I&E should
reuse those capabilities through qualified Adapters.

I&E still needs a sidecar for reproducibility and Agent-specific derivations that
the reviewed OpenCTI public contracts do not define: parser/extraction identity,
page and source offsets, immutable chunks, embedding/index versions, resource-to-
derivative mappings, supplemental source-dependency lineage, bounded collection
request receipts, retrieval traces, and exact Resource Capsule digests. The final
model-input receipt belongs to Workspace because it also binds Orientation,
Working Set, Session projection, rendering, tool schemas, and token policy. This sidecar is
not a second CTI graph, Connector control plane, Case store, or inference authority.

## External facts

### 1. OpenCTI is a STIX-oriented knowledge graph with a comprehensive API

- OpenCTI models CTI as graph nodes (entities) and edges (relationships). Its data
  model is based on STIX 2.1 and extends STIX for additional cybercrime,
  disinformation, observable, and relationship types. The deployment's GraphQL
  Playground is the authority for the complete fields on each type. [OpenCTI data
  model](https://docs.opencti.io/latest/usage/data-model/)
- OpenCTI describes GraphQL as its comprehensive programmatic API and states that
  API access has the rights of the user associated with the bearer API key. The
  public documentation directs clients to the deployed Playground/schema for
  queryable fields and filters. [OpenCTI GraphQL
  API](https://docs.opencti.io/latest/reference/api/)
- OpenCTI exposes recursive `FilterGroup` filters through its API. These filters
  apply across lists, knowledge graphs, feeds, streams, triggers, playbooks, and
  background tasks; supported keys include schema attributes and relation-derived
  keys. [OpenCTI filter
  contract](https://docs.opencti.io/latest/reference/filters/)

**Design implication:** OpenCTI, not I&E, should remain authoritative for STIX and
OpenCTI entity/relationship state, graph traversal, and current actor-visible
resource metadata. An I&E Adapter must pin exact GraphQL documents and validate
the selected deployment schema instead of depending on a timeless DTO.

### 2. Connector classes already cover import, enrichment, files, export, and streams

- The official deployment contract distinguishes external import, internal
  enrichment, stream, file import, and file export Connectors. Import Connectors
  fetch external data, convert it to STIX 2.1 bundles, and send it through OpenCTI
  workers. Enrichment Connectors can run when an object is created or when a user
  requests enrichment. [OpenCTI Connector
  deployment](https://docs.opencti.io/latest/deployment/connectors/)
- The Connector development contract additionally identifies
  `INTERNAL_ANALYSIS`, `INTERNAL_IMPORT_FILE`, and `INTERNAL_EXPORT_FILE` types.
  External-import and stream Connectors are self-triggered; analysis, enrichment,
  file import, and file export listen for jobs initiated by OpenCTI. [OpenCTI
  Connector development](https://docs.opencti.io/latest/development/connectors/)
- OpenCTI recommends that Connectors create/update knowledge by sending STIX
  bundles through workers rather than calling create APIs directly. The stated
  purpose is to let the worker chain handle ingestion ordering, performance, and
  errors. [OpenCTI Connector development](https://docs.opencti.io/latest/development/connectors/)
- Self-triggered Connectors own their polling interval and persistent `last_run`
  state. They register a `work`, attach its ID to one or more submitted bundles,
  and mark the work processed or in error. Multipart work must be declared when
  one work submits several bundles. [OpenCTI Connector work and interval
  lifecycle](https://docs.opencti.io/latest/development/connectors/)
- Resetting a Connector state restarts its ingestion from the beginning and also
  purges that Connector's RabbitMQ queue. The operation requires the dedicated
  `Manage connector state` capability. [OpenCTI automated import
  Connectors](https://docs.opencti.io/latest/usage/import/external-connectors/)

**Design implication:** Connector deployment, configuration, scheduling, state
reset, queue management, and ordinary feed synchronization remain infrastructure
operations. An Agent-facing I&E request may ask for a bounded enrichment or
collection outcome, but trusted deterministic code must decide whether and how to
reuse an existing OpenCTI job path. The Agent must not start, stop, configure, or
reset a Connector.

### 3. OpenCTI supports both automatic and requested enrichment

- Enrichment can run automatically when data arrives (`auto: true`) or be targeted
  through a playbook. The documentation warns that automatic enrichment can
  exhaust paid-source quotas and substantially increase data volume. [OpenCTI
  enrichment Connectors](https://docs.opencti.io/latest/usage/enrichment/)
- A user may manually request enrichment for one entity by selecting an available
  Connector scoped to that entity type. The RBAC capability list separates
  `Ask for knowledge enrichment` from ordinary read access. [OpenCTI enrichment
  Connectors](https://docs.opencti.io/latest/usage/enrichment/), [OpenCTI users and
  RBAC](https://docs.opencti.io/latest/administration/users/)
- For an internal enrichment job the documented callback carries the target
  entity ID. Internal file-import callbacks carry a file ID, MIME type, storage
  fetch path, and optional contextual entity ID. [OpenCTI Connector development](https://docs.opencti.io/latest/development/connectors/)

**Design implication:** bounded Agent-requested enrichment is compatible with
OpenCTI's native job model. I&E should add admission, actor/purpose authorization,
request de-duplication, quota/rate budgets, and a stable request receipt outside
the model. It should not create a competing scheduler.

### 4. File storage/import and search are useful but are not a RAG provenance contract

- OpenCTI supports file import through `ImportFileStix`, `ImportFileMISP`,
  `ImportFileYARA`, and `ImportDocument`; the last recognizes entities in PDF,
  text, HTML, and Markdown. Connector-identified entities enter an analyst
  Workbench and do not enter the main knowledge base until validation. CSV mappers
  are an explicit exception and import directly without a Workbench. [OpenCTI file
  import](https://docs.opencti.io/latest/usage/import-files/)
- Upload and import are separately permissioned as `Upload knowledge files` and
  `Import knowledge`. [OpenCTI users and
  RBAC](https://docs.opencti.io/latest/administration/users/)
- OpenCTI can extract and index text from selected uploaded file types. The
  operator chooses included files and a maximum file size (5 MB by default); the
  file indexer runs periodically, and reset deletes the indexed file content from
  the search database. [OpenCTI file
  indexing](https://docs.opencti.io/latest/administration/file-indexing/)
- Full-text search inside file content is listed as an Enterprise capability;
  classic search is based on metadata such as title, description, and type.
  [OpenCTI Enterprise features](https://docs.opencti.io/latest/administration/enterprise/)
- OpenCTI's storage configuration uses an S3-compatible bucket (MinIO by default)
  for files. [OpenCTI dependency
  configuration](https://docs.opencti.io/latest/deployment/configuration/)
- The official file/import/index documentation does not define a public contract
  for page coordinates, original-text offsets, parser version, immutable chunk
  identity, embedding model/version, vector-index generation, ranker features, or
  exact model-input assembly. A keyword audit of the pinned generated GraphQL
  schema also found no `embedding`, `chunk`, `offset`, or `parser` field names.
  [Pinned `7.260715.0` generated GraphQL
  schema](https://raw.githubusercontent.com/OpenCTI-Platform/opencti/7.260715.0/opencti-platform/opencti-graphql/config/schema/opencti.graphql)

**Design implication:** use OpenCTI's file object and object storage as the primary
document anchor when permitted, but keep Agent-grade extraction coordinates,
chunks, embeddings, retrieval indexes, and I&E retrieval receipts in a versioned
sidecar. Workspace separately owns the final model-input receipt. OpenCTI full-text search may be a candidate generator or fallback; it
cannot by itself satisfy exact prompt reproduction.

### 5. OpenCTI de-duplication is semantic consolidation, not request idempotency

- On create, OpenCTI checks type-specific ID-contributing properties. A hit returns
  the existing object and can update it. Entity identity can depend on names and
  aliases; relationship de-duplication uses relationship type, source, target, and
  time windows; observable IDs use STIX ID-contributing properties. [OpenCTI
  de-duplication](https://docs.opencti.io/latest/usage/deduplication/)
- OpenCTI describes this behavior as consolidation/upsert toward higher confidence
  and quality, not as replay of a caller-owned request receipt. [OpenCTI
  de-duplication](https://docs.opencti.io/latest/usage/deduplication/)

**Design implication:** an I&E operation key cannot be inferred from OpenCTI's
resource de-duplication. Preserve instance ID, OpenCTI internal and standard IDs,
source-local identity, source/file version or digest, Connector/work identity,
and I&E operation identity separately. Content de-duplication must not collapse
different source observations or make them independent corroboration.

### 6. Authorization is principal- and marking-scoped

- Roles grant capabilities through groups, while groups and organizations also
  participate in data segregation. Relevant capabilities separately cover read,
  create/update, upload, import, enrichment requests, Connector-state management,
  API token use, and file-index administration. [OpenCTI users and
  RBAC](https://docs.opencti.io/latest/administration/users/)
- Connector imports/enrichment run with the Connector user's permissions, and the
  official deployment guide recommends a dedicated user/token for each Connector.
  [OpenCTI Connector deployment](https://docs.opencti.io/latest/deployment/connectors/)
- A user's groups determine allowed markings. Access to an object carrying several
  markings requires access to every attached marking. [OpenCTI marking
  restriction](https://docs.opencti.io/latest/administration/segregation/)
- GraphQL responses are authorized as the API-key user, not as an abstract I&E
  service identity. [OpenCTI GraphQL API](https://docs.opencti.io/latest/reference/api/)

**Design implication:** the Connector principal proves ingestion authority, not
the investigating user's read authority. I&E retrieval and byte access must be
re-authorized for the consuming actor/purpose, and caches/indexes must retain an
authorization/marking partition or enforce an equivalent late disclosure fence.
No privileged index may leak a hidden resource's existence, count, text, score,
or provenance.

### 7. Streams and History support invalidation and audit, not permanent replay

- OpenCTI writes create/update/delete/merge events to a Redis Stream and exposes
  authenticated SSE streams. Events contain STIX data; updates include forward
  and reverse JSON patches; merge combines target update with source deletions.
  [OpenCTI data streaming](https://docs.opencti.io/latest/reference/streaming/)
- The base stream is filtered by user rights and can resume from an event ID or
  timestamp. Retention is configurable; the documentation presents roughly one
  month/two million events as common guidance, not permanent history. Live-stream
  `recover` reads an initial matching set from the main database, including data
  older than stream retention. [OpenCTI data
  streaming](https://docs.opencti.io/latest/reference/streaming/)
- Basic knowledge create/update/delete activity is exposed through History;
  extended activity is expensive and recorded only for configured principals,
  while the unified Activity interface is Enterprise functionality. [OpenCTI
  activity overview](https://docs.opencti.io/latest/administration/audit/overview/)
- Retention policies can permanently delete files, Workbenches, History, Activity,
  and filtered knowledge. History and Activity retention applies globally by age
  and has no per-object filter. [OpenCTI retention
  policies](https://docs.opencti.io/latest/administration/retentions/)

**Design implication:** use an actor/marking-qualified stream as a dirty hint and
History/work evidence as operational corroboration. They are not a durable I&E
retrieval ledger, a snapshot token, or proof that an absent event/effect never
existed. A cursor gap, schema change, principal change, or retention loss forces
an authoritative re-read/rebuild of the affected derivative partition.

### 8. Release compatibility must be qualified, not assumed

- OpenCTI uses date-based continuous-delivery versions; non-LTS releases can be
  daily to weekly. LTS lines stabilize features and receive critical/security
  fixes under a separate program. [OpenCTI product life
  cycle](https://docs.opencti.io/latest/administration/product-life-cycle/)
- The official breaking-change index records API, filter, token, cryptography, and
  related-component changes, including a 2026 token/JWT migration. [OpenCTI
  breaking changes](https://docs.opencti.io/latest/deployment/breaking-changes/)
- OpenCTI Platform and Connectors both publish a `7.260715.0` release, but the
  reviewed official documentation does not publish a general Connector-to-
  Platform compatibility matrix. [Platform `7.260715.0`
  release](https://github.com/OpenCTI-Platform/opencti/releases/tag/7.260715.0),
  [Connectors `7.260715.0`
  release](https://github.com/OpenCTI-Platform/connectors/releases/tag/7.260715.0)

**Design implication:** pin Platform, worker, Connector SDK, and each activated
Connector artifact; capture their versions/digests in qualification evidence; and
run deployment-specific conformance probes. Matching release labels are a good
candidate baseline, not proof that an I&E mapping remains compatible.

## Confirmed limits

| OpenCTI capability | Confirmed public-contract limit | I&E response |
| --- | --- | --- |
| GraphQL and filters | Schema is deployment-local and evolves | Pin documents; introspect exact selected surface; fail closed on drift |
| External Connector interval | Connector owns interval and `last_run` state | Do not create an Agent scheduler or silently rewrite Connector state |
| Connector `work` | Tracks submitted work and processed/error state; no documented caller-idempotency or exact prompt-reproduction contract | Treat as operational evidence; bind it to a separate I&E request receipt |
| State reset | Restarts ingestion and purges the Connector queue | Operator-only, never an Agent tool |
| Native enrichment | Automatic or requested, and can consume paid quotas/create volume | Deterministic admission, authorization, quota, rate, and duplicate guards |
| File Workbench | Connector results await validation, but CSV mapping bypasses Workbench | Preserve ingestion and validation path; never infer review from presence |
| File index/search | Edition/configuration/size/type dependent; no documented chunk/offset/embedding contract | Sidecar owns exact derivations and retrieval evidence |
| De-dup/upsert | Can return and update an existing semantic object | Keep source observation and operation identity outside semantic de-dup |
| Marking/RBAC | Visibility depends on current principal and all attached markings | Actor/purpose authorization fence at retrieval and disclosure |
| Stream | Rights-filtered and retention-bounded | Dirty hint plus cursor evidence; rebuild on gaps |
| History/Activity | Configurable, edition-dependent, and retainable | Corroboration only, not durable retrieval or operation authority |
| Release train | Frequent releases and documented breaking changes; no universal compatibility matrix | Version pinning, schema digest, and conformance suite per deployment |

These limits do not show that OpenCTI is unsuitable. They show where a small
derived Module is necessary to give the Agent a stronger reproducibility contract
without forking OpenCTI's infrastructure responsibilities.

## Design implications

### Authority allocation

| Concern | Authority | Rationale |
| --- | --- | --- |
| STIX/OpenCTI entities, relationships, markings, files, Connector state, Workbench validation, graph search/filtering | OpenCTI | Native platform responsibility and current-data authority |
| Connector deployment, schedule, credentials, queue reset, infrastructure health | Operator/OpenCTI | Privileged infrastructure control; never delegated to the Agent |
| Bounded collect/enrich request admission, actor/purpose binding, quota/rate/duplicate control | I&E deterministic service | Stronger request contract above native jobs without replacing them |
| Parser/extraction version, page/offset map, chunks, embeddings, index versions | I&E sidecar | Agent-specific, reproducibility-critical, and rebuildable from an exact resource version |
| Resource-to-derivative map and supplemental source dependency lineage | I&E sidecar linked to OpenCTI IDs | Preserves exact derivation and cross-source dependence without forcing it into STIX semantics |
| Query/filter/Top-K, selected chunks, scores, all I&E processing versions, Resource Capsule and retrieval-result digests | I&E retrieval receipt store | Required to reproduce the I&E contribution to Agent input |
| Full candidate set and intermediate rank features | I&E bounded-retention diagnostics | High-volume debugging data, not permanent Case/CTI authority |
| Working Set selection, exact assembled model-input bytes/digest, and Case reasoning | Agent Workspace | Task-specific selection and final provider-input boundary |
| Formal Case findings and Evidence role | Case Management | Long-lived Case authority |

### Minimal interaction protocol

1. A caller supplies an actor/purpose-bound I&E request, never a Connector
   configuration or arbitrary GraphQL document.
2. Deterministic admission checks capability, markings/policy, source/Connector
   allowlist, quota, rate, timeout, and stable request identity.
3. I&E reads current resources or requests one bounded native OpenCTI enrichment/
   import job through a qualified Adapter. It records OpenCTI instance, resource,
   file/source version, Connector artifact, and work/job identities.
4. Only current authorized, successfully qualified resource versions enter the
   derivation pipeline. Workbench candidates stay candidates until OpenCTI
   validation; CSV direct-import provenance remains explicitly different.
5. Extraction and indexing publish a complete derivative generation atomically.
   A generation is addressable by resource version plus parser/extraction/chunk/
   embedding/index versions. A failed or partial generation is not queryable.
6. Retrieval uses a pinned generation and current authorization fence, then emits
   selected chunks plus a durable retrieval receipt. The receipt proves what was
   supplied, not that it was true, relevant to a Case, or accepted as Evidence.
7. Workspace decides which returned resources enter its task-bound Working Set.
   Case Management alone records formal Case use and conclusions.

### Failure and concurrency consequences

- **Timeout after requesting OpenCTI work:** retain one outcome-unknown I&E request
  identity and reconcile the native work/resource predicate. Do not create a new
  semantic request merely because the response was lost.
- **Duplicate request:** identical actor/purpose/target/request digest converges on
  the existing receipt or in-flight operation. A different digest under the same
  operation ID is a conflict.
- **Connector crash or partial bundle:** OpenCTI work/error/queue state is useful
  evidence, but I&E publishes no derivative generation until the exact target
  resource version is authoritatively readable and complete under its contract.
- **I&E crash:** staged derivatives remain unreachable; recovery resumes or
  discards them by generation identity. Publication uses one atomic generation
  pointer rather than making chunks visible incrementally.
- **Concurrent resource update:** the old immutable generation remains labeled to
  its old version; a new source/file/resource version produces a new generation.
  A retrieval validates that the selected generation and authorization are still
  permitted before disclosure.
- **Stream/history gap:** mark only the affected resource/index partition dirty and
  re-read/rebuild it. Do not freeze unrelated resources or claim historical
  continuity.
- **Marking or permission loss:** stop serving bodies, chunks, scores, hit counts,
  and provenance for the affected authority partition. Operational receipts may
  retain only non-content fields allowed by policy.

### What belongs in the sidecar

The sidecar should contain only data that is derived, reproducibility-critical,
or unsafe/awkward to express as CTI knowledge:

- exact content/file digest and OpenCTI resource/version mapping;
- parser, OCR, normalization, and extraction artifact versions;
- page geometry and original-byte/text offset maps;
- immutable chunk IDs and ordered chunk manifests;
- embedding model/configuration identity, vector digest, and index generation;
- supplemental `derived-from`, relay, and unknown-dependency observations used for
  source-lineage analysis, while retaining the underlying OpenCTI references;
- bounded collect/enrich request identity, admission decision, native work/job
  correlation, terminal disposition, and safe failure evidence;
- durable retrieval query, closed filters, Top-K, selected chunks, returned scores,
  reranker/version chain, and Resource Capsule/retrieval-result digests;
- retention-bounded complete candidate sets and intermediate rank features.

It should not contain an independently editable copy of the OpenCTI graph, a
parallel Connector schedule/configuration, Case conclusions, Working Set state, or
merged canonical CTI entities. A rebuild must be possible from an authorized exact
OpenCTI resource/source version plus versioned derivation artifacts.

### Qualification and validation gates

Before activating an OpenCTI-backed I&E Adapter for a deployment, prove at least:

1. exact Platform, worker, Connector SDK, Connector artifact, edition, and selected
   GraphQL schema identities;
2. actor-equivalent reads and negative fixtures for marking/capability revocation;
3. exhaustive resource/file lookup and exact digest/version binding;
4. Connector job correlation, timeout, duplicate request, crash, and partial-work
   reconciliation without Agent control of infrastructure;
5. Workbench-versus-direct-import provenance behavior;
6. atomic derivative-generation publication and rebuild after resource updates;
7. stream cursor continuity and forced rebase after trimming or principal change;
8. retrieval reproduction from receipt to exact selected chunk text and exact
   Resource Capsule digest, plus Workspace reproduction of the final model-input digest;
9. no hidden resource metadata leakage through indexes, scores, counts, errors, or
   diagnostics; and
10. version-upgrade conformance before enabling the new deployment/schema mapping.

## Design disposition

Adopt the following candidate direction in the I&E architecture, subject to its
own normative contract and acceptance cases:

1. **OpenCTI is the primary CTI infrastructure and current resource authority.**
   Reuse its Connectors, worker ingestion, STIX/OpenCTI graph, files, Workbenches,
   enrichment, authorization, de-duplication, search/filter, and change streams.
2. **I&E is a derived deep Module, not a second threat-intelligence platform.** Its
   public Interface exposes qualified resource reads, bounded collect/enrich
   requests, reproducible retrieval, and derivative status. Connector, parser,
   queue, vector store, and storage mechanics stay hidden behind Adapters.
3. **The Agent has no infrastructure control authority.** It can request typed,
   bounded outcomes. Deterministic code owns authorization, de-duplication, queue/
   rate/quota control, dispatch, retry, reconciliation, and publication.
4. **OpenCTI `work`, Stream, History, and semantic de-duplication are evidence, not
   the I&E operation/retrieval contract.** I&E owns stable request and retrieval
   receipts required for replay and explanation.
5. **Sidecar state is versioned, immutable by generation, and rebuildable.** It is
   always linked to exact OpenCTI/resource/source versions and is never promoted to
   Case truth or independent CTI authority.
6. **Search is layered.** OpenCTI GraphQL/filter and optional file search provide
   authoritative resource discovery/candidate generation; I&E chunk/vector/rerank
   retrieval provides Agent-specific evidence spans with exact reproduction.
7. **Upgrade qualification is mandatory.** Pin synchronized artifacts where
   possible, but rely on deployed schema/capability/conformance evidence rather
   than matching names or release labels.

This disposition does not authorize implementation, Connector activation, data
import, OpenCTI mutation, or a fixed model-visible tool decomposition. It supplies
external facts and a bounded platform/sidecar seam for the I&E design owner.
