# OpenCTI Projection Authorization, History, and Change Detection

Status: research note for the purpose-specific authorized Case Projection Adapter.

Design disposition (2026-07-20): the item-authorization, non-leaking completeness, double-observation, invalidation, and current-read findings are adopted by the current [`opencti-case-orientation/v1` Contract](../agent-workspace/opencti-case-orientation-v1-contract.md). Claims specific to the complete composed Projection remain input to the frozen strict-R1 target and are not current-cycle requirements.

Reviewed: 2026-07-20 against the current OpenCTI documentation. OpenCTI is under active development, and several behaviors discussed below are edition- and configuration-dependent. The production Adapter must verify them against the deployed OpenCTI version and license profile.

## Conclusion

OpenCTI provides the necessary raw mechanisms for an authorized current Case view: API calls execute with the access privileges of the API-key user; capabilities, markings, organization segregation, and Authorized Members constrain access; Cases are containers of independently modeled entities and relationships; authenticated streams expose create, update, delete, and merge events; and history, activity, and trash aid audit and recovery.

Those mechanisms do not establish a transactionally consistent, replayable, point-in-time Case Projection contract by themselves:

- container authorization does not cascade to contained entities;
- an object with multiple markings requires access to every marking;
- an apparent deletion notification can mean either real deletion or loss of visibility;
- streams are user-rights-filtered and have finite retention;
- history, activity, trash, workbenches, and knowledge can all be removed under their respective retention or permanent-deletion behavior; and
- the reviewed public API documentation does not specify a platform-wide revision, authorization revision, multi-query snapshot, or general as-of query.

The OpenCTI Case Adapter must therefore produce a new contract above the native API. It must authorize every projected object and relationship under the investigating actor, stage a complete projection before publishing it, treat events as dirty hints, use authoritative current reads after cursor or authorization uncertainty, expose redaction/completeness semantics without leaking hidden identities, and refuse to claim exact historical reconstruction unless a separately verified archive can supply it.

## Evidence boundary

Sections labeled **Source facts** summarize official OpenCTI documentation or primary specifications. Sections labeled **CTI-RAG inference** are architectural conclusions for this project. The cited sources do not prescribe the CTI-RAG Projection Profile, Case Revision, or operation-dependency contract.

## Primary-source findings

### 1. API access is the access of the authenticated principal

**Source facts**

- OpenCTI's GraphQL API requires authentication, and the data rights of an API request are determined by the privileges of the user associated with the API key. [OpenCTI, *GraphQL API*](https://docs.opencti.io/latest/reference/api/)
- OpenCTI separates capabilities from data segregation. Roles grant capabilities; groups are the main mechanism for permissions and data segregation and carry allowed markings; organizations add another segregation layer. User accounts can be active, inactive, locked, or expired, and only active accounts can log in. [OpenCTI, *Users and Role Based Access Control*](https://docs.opencti.io/latest/administration/users/)
- Connectors authenticate through OpenCTI users and tokens. OpenCTI recommends a dedicated user for each connector. Import and enrichment operate with the connector user's permissions, while internal export connectors use an administrator because they impersonate the requesting user to avoid leakage. Token connections use short-period JWTs and do not create persistent user sessions. [OpenCTI, *Connectors*](https://docs.opencti.io/latest/deployment/connectors/)

**CTI-RAG inference**

- The Case Projection read must execute under a principal whose effective access is the investigating actor's access, not a general `Bypass` account followed by best-effort redaction. A privileged technical account may operate the Adapter, but it must use an OpenCTI-supported impersonation or equivalent owner-verified authorization path before production; locally reproducing OpenCTI's security rules is not sufficient.
- Connector identities are provenance and ingestion identities, not substitutes for the investigating actor. Data visible to an import connector can still be unauthorized to the Workspace user.
- A successful request proves only that the request was authorized when OpenCTI evaluated it. The reviewed API documentation does not expose an authorization revision or a lease guaranteeing that the same access remains valid until the Workspace installs a multi-call result. The Adapter therefore needs an end-of-read authorization fence of its own and must reject a late result after known actor, group, role, marking, organization, Authorized Member, account-status, or purpose changes.

### 2. Markings are conjunctive access controls and can change independently of content

**Source facts**

- OpenCTI segregates knowledge by markings. A user can access a marking through an explicitly allowed marking or an equal-or-higher marking in the same ordered type. An object with several markings requires access to all attached markings. [OpenCTI, *Marking restriction*](https://docs.opencti.io/latest/administration/segregation/)
- When several markings of one type are applied, OpenCTI retains the marking with the highest order for that type. This consolidation can occur on create, update, connector import, and merge. A connector cannot downgrade an existing entity's marking when a higher marking of the same type is already present. [OpenCTI, *Marking restriction*](https://docs.opencti.io/latest/administration/segregation/)
- STIX 2.1 Marking Definition objects cannot be versioned, and changing `object_marking_refs` creates a new version of the marked object rather than a new version of the marking definition. [OASIS, *STIX 2.1*, section 7.2](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html#_k5fndj2c7c1k)

**CTI-RAG inference**

- Projection authorization must bind the exact effective marking set and the actor's effective allowed-marking state separately from the semantic content digest. Equal body text is not proof of equal visibility.
- A marking change is security-significant even when no task-relevant prose changed. Any event or probe showing a marking change must invalidate the affected projection block and every model-visible derivative.
- If the Adapter cannot establish the complete marking set for a projected object or relationship, it must omit that item and mark the relevant Projection block incomplete; it must not infer access from the Case container's marking alone.

### 3. Case/container access and contained-object access are independent

**Source facts**

- OpenCTI Cases are containers that can contain entities and relationships. The platform models Incident Response, Request for Information, and Request for Takedown as Case types, and Cases may contain any entities and relationships needed for their intelligence context. [OpenCTI, *Case management*](https://docs.opencti.io/latest/usage/case-management/), [OpenCTI, *Containers*](https://docs.opencti.io/latest/usage/containers/)
- Authorized Members can restrict selected entities, including Case types, to named users, groups, or organizations with View, Edit, Manage, or Can-use levels. Once configured, only those members have access. [OpenCTI, *Authorized members*](https://docs.opencti.io/latest/administration/authorized-members/)
- For Report, Grouping, Incident Response, Case RFI, and Case RFT containers, an Authorized Members restriction applies to the container and explicitly does not cascade to entities contained by it. Enabling Authorized Members on such an entity also changes how organization segregation applies to that entity. [OpenCTI, *Authorized members*](https://docs.opencti.io/latest/administration/authorized-members/)
- Creating an object from inside a container pre-populates its marking field from the container, but the contained object remains an independently modeled object. [OpenCTI, *Containers*](https://docs.opencti.io/latest/usage/containers/)

**CTI-RAG inference**

- Projection closure must be authorized item by item: Case root, Tasks, Notes, contained entities, contained relationships, relationship endpoints, authors, attachments, and reference targets. “The user can view the Case” does not authorize the full graph reachable from the Case.
- Conversely, hiding the Case does not imply that every globally reusable entity formerly contained in it has become unauthorized. Revocation scope follows each item's actual access controls and the derivation edges recorded by the Workspace.
- The Projection should distinguish `authorized view is complete for this profile` from `the global Case graph contains no other material`. A non-privileged Adapter generally cannot safely reveal the number, identifiers, types, labels, or topology of hidden objects. Redaction markers should report semantic incompleteness at the block/profile level without leaking hidden-object metadata.

### 4. A visibility loss can look like deletion

**Source facts**

- OpenCTI instance triggers monitor updates and deletions of the selected object, creation/deletion of relationships, related entities, and reference membership changes. OpenCTI explicitly warns that an entity-deletion notification can mean either real entity deletion or a modification that caused the user to lose visibility. [OpenCTI, *Notifications and alerting*](https://docs.opencti.io/latest/usage/notifications/)
- Triggers are filtered by object properties such as markings and can be configured for creation, modification, and deletion. Notifications and digests are delivery features for users, groups, and organizations, not described as durable synchronization journals. [OpenCTI, *Notifications and alerting*](https://docs.opencti.io/latest/usage/notifications/)

**CTI-RAG inference**

- A deletion-like notification must be classified as `deleted_or_visibility_lost`, immediately stop use of the affected body, and trigger an actor-scoped authoritative re-read. It is not sufficient proof for a Case tombstone and must never disclose that an inaccessible object still exists.
- If the re-read returns unauthorized/not visible, the Workspace must apply authorization-revocation behavior: clear protected cached bodies, hide dependent current outputs, and resume only in a clean authorized context. It must not retain the old body as historical model context.
- A separate privileged audit path may later distinguish real deletion from visibility loss for operators, but that fact cannot be returned to an actor who is no longer authorized to learn it.

### 5. Deletion is graph-affecting and recovery is partial and time-bounded

**Source facts**

- Deleting an OpenCTI knowledge object also deletes all relationships and references to other objects. A deletion event is written to the stream. [OpenCTI, *Delete and restore knowledge*](https://docs.opencti.io/latest/usage/delete-restore/)
- Stream delete events contain the STIX data immediately before deletion and may include automated dependency deletions in event context. Merge combines an update of the target with deletion of the sources. [OpenCTI, *Data Streaming*](https://docs.opencti.io/latest/reference/streaming/)
- Deleted objects are normally retained in Trash for a configurable period, seven days by default, but Trash can be disabled. Trash entries inherit the deleted main object's marking. Restore has no partial or cascading mode, can fail when a related dependency is missing, and cannot recover permanently deleted dependencies. OpenCTI states that Trash is not a backup system. [OpenCTI, *Delete and restore knowledge*](https://docs.opencti.io/latest/usage/delete-restore/)
- An active Knowledge retention policy permanently deletes matching objects without placing them in Trash. [OpenCTI, *Retention policies*](https://docs.opencti.io/latest/administration/retentions/)

**CTI-RAG inference**

- A deleted Case relationship is a material dependency change even when both endpoint entities remain visible. The Adapter must project explicit removal/tombstone semantics or perform a full rebase; silently omitting the edge can leave an old relationship authoritative in Workspace state.
- Cascade deletion and merge are multi-object changes. A delta is safe only when the complete deletion/source set, event continuity, authorization, and resulting digest validate. Otherwise the Adapter must discard the partial delta and rebuild the entire affected Case Projection partition.
- Trash must not be used as the Projection's authoritative history store. Its availability, retention, dependency closure, and access are insufficient for guaranteed audit replay.

### 6. Streams support resumption but have finite history and actor-relative content

**Source facts**

- OpenCTI uses Redis Streams and exposes authenticated Server-Sent Events. Events carry a stream ID and create/update/delete type; update events contain complete STIX data plus forward and reverse JSON patches. [OpenCTI, *Data Streaming*](https://docs.opencti.io/latest/reference/streaming/)
- The base stream is filtered by the user's rights, described by the documentation as marking-based. It supports a `from` timestamp or event ID for catch-up. Its retention is configured by Redis trimming; OpenCTI recommends roughly one month as a common sizing choice, not an indefinite record. [OpenCTI, *Data Streaming*](https://docs.opencti.io/latest/reference/streaming/)
- Live streams can emit an initial current set from the main database through `recover`, resolve dependencies, and translate events according to element segregation. `from` identifies the stream start point; `recover` reads initial instances from the current main database. [OpenCTI, *Data Streaming*](https://docs.opencti.io/latest/reference/streaming/)
- The SSE standard defines reconnection using the last event ID. It does not turn a server's finite backing store into permanent history. [WHATWG, *Server-sent events*](https://html.spec.whatwg.org/multipage/server-sent-events.html#server-sent-events)
- Redis `XTRIM` removes the oldest entries below a length or minimum-ID threshold. [Redis, `XTRIM`](https://redis.io/docs/latest/commands/xtrim/)

**CTI-RAG inference**

- Persist one cursor per authenticated authority partition and treat every event as a dirty hint. Deduplicate equal IDs. An apparent rewind, unknown predecessor, cursor older than retention, reconnect without provable continuity, schema change, or digest mismatch invalidates incremental processing and requires a current authoritative re-open.
- The Adapter must not assume that two principals receive the same stream. A cursor and event digest are meaningful only with the stream/filter/principal configuration that produced them.
- `recover` is a current-state recovery mechanism, not an as-of read. It can rebuild today's authorized view after a gap, but it cannot establish what the actor could see at an arbitrary earlier revision.
- Reverse patches permit reconstruction of an immediately previous value only when the Adapter has a complete, authenticated, retained event chain with compatible schemas. They do not provide a general historical Projection guarantee.
- The documentation does not promise exactly-once notification delivery or a transactional relationship between a multi-query GraphQL read and a stream cursor. The Adapter must tolerate duplicate, delayed, and operationally reordered observations and validate the final materialization independently.

### 7. History and activity aid audit but are not an immutable as-of store

**Source facts**

- OpenCTI history records create, update, and delete actions on STIX knowledge, and the history manager tracks user/connector interactions on entities. Enterprise Activity adds a unified view, extended activity for configured principals, and audit events for administration and security actions. [OpenCTI, *Activity overview*](https://docs.opencti.io/latest/administration/audit/overview/), [OpenCTI, *Platform managers*](https://docs.opencti.io/latest/deployment/advanced/managers/)
- Extended activity is recorded only for explicitly configured users, groups, or organizations because it is expensive. [OpenCTI, *Activity overview*](https://docs.opencti.io/latest/administration/audit/overview/)
- Retention policies can permanently delete all History or Activity entries older than a configured duration. These scopes do not support object-level filters. [OpenCTI, *Retention policies*](https://docs.opencti.io/latest/administration/retentions/)

**CTI-RAG inference**

- History may explain recent changes and support operator audit, but availability depends on edition, configuration, authorization, and retention. The Adapter cannot use “history exists” as proof that any old Case Projection can be reconstructed.
- The reviewed public GraphQL documentation describes current authenticated queries but does not document a platform-wide revision token, a multi-query snapshot transaction, an authorization revision, or a general as-of Case query. Until a deployed-version spike proves stronger behavior, `opencti-case-projection/v1` must promise current authorized materialization plus receipts/digests, not native OpenCTI point-in-time replay.
- If exact historical audit is required, Case Management must either verify a complete retained event/history archive and its authorization semantics or store an encrypted immutable Projection artifact outside the ordinary Session. That artifact must retain its original access classification and cannot be made visible after later revocation merely because it was once authorized.

### 8. Connectors and workbenches do not make imported claims authoritative

**Source facts**

- Import connectors retrieve external information, convert it to STIX bundles, and import it through OpenCTI workers; enrichment connectors can add knowledge around an object. Connector behavior and imported scope vary by connector implementation. [OpenCTI, *Connectors*](https://docs.opencti.io/latest/deployment/connectors/), [OpenCTI, *Automated import connectors*](https://docs.opencti.io/latest/usage/import/external-connectors/)
- File-import connectors place identified objects in an analyst workbench. Workbench content is draft material and is not in the knowledge base until an analyst validates it. Import connectors may identify wrong types or unknown entities. CSV mappers are an explicit exception: they import directly without a workbench. [OpenCTI, *Import from files*](https://docs.opencti.io/latest/usage/import-files/), [OpenCTI, *Analyst workbench*](https://docs.opencti.io/latest/usage/workbench/)
- Importing from a Case/container data tab can automatically add contained-object links after workbench validation. [OpenCTI, *Import from files*](https://docs.opencti.io/latest/usage/import-files/)
- Workbench retention can permanently delete old global workbenches. [OpenCTI, *Retention policies*](https://docs.opencti.io/latest/administration/retentions/)

**CTI-RAG inference**

- The Case Projection must not treat unvalidated workbench content as Case knowledge. If pending import review is relevant, project only a clearly labeled proposal/work status with a stable reference; do not project the proposed entities as authoritative Case blocks.
- Validated import establishes that data entered the OpenCTI knowledge base, not that an external assertion is true or that an extracted entity resolution is correct. Imported material remains an Intelligence Resource or Candidate Finding until Case Management accepts the appropriate Case judgment.
- The CSV direct-import exception means the Adapter cannot infer “human reviewed” from connector provenance. It must preserve ingestion method, connector identity, source provenance, markings, and validation path separately.
- A connector-triggered automatic containment relationship is still a relationship with its own version, markings, provenance, and authorization. It requires the same projection and deletion handling as a manually created relationship.

### 9. Draft workspaces have snapshot-like security and concurrency caveats

**Source facts**

- OpenCTI Drafts are separate from the main knowledge base. They track Create, Update, Delete, and linked-impact operations and can be approved into the main knowledge base. [OpenCTI, *Draft workspaces*](https://docs.opencti.io/latest/usage/draftWorkspaces/)
- Draft approval is allowed while connector or background processes are still running; changes those processes would later produce are lost. Approval applies direct Create, Update, and Delete operations with operation-specific behavior. [OpenCTI, *Draft workspaces*](https://docs.opencti.io/latest/usage/draftWorkspaces/)
- Capabilities, confidence, markings, and segregation apply in Drafts. An entity hidden when the Draft was created remains hidden in that Draft even if it is shared with the user later. [OpenCTI, *Draft workspaces*](https://docs.opencti.io/latest/usage/draftWorkspaces/)

**CTI-RAG inference**

- A Draft is not a suitable source for the current authoritative Case Projection. Its data and security view can intentionally diverge from current main knowledge, and approval can race unfinished processes.
- If a later capability deliberately investigates a Draft, its Draft identity, creation-time access basis, current approval state, pending-process set, and main-knowledge comparison must form a separate dependency partition. Draft results cannot silently enter the normal current-Case partition.

## Conservative Adapter contract

The source facts imply the following minimum behavior for `opencti-case-projection/v1`.

### Authorized read

1. Authenticate as, or through a verified impersonation of, the investigating actor.
2. Resolve the Case root and verify Case-level capability, markings, organization segregation, Authorized Members, and account state.
3. Read only the Projection Profile's required semantic material.
4. Authorize every returned entity, relationship, endpoint, Task, Note, author, reference, and attachment independently; never inherit authorization from containment.
5. Stage all pages and blocks outside the active Projection. Record item versions, markings, security labels, profile/schema version, actor/purpose binding, and a deterministic content digest.
6. Perform an end fence. At minimum, revalidate the Case root and effective actor access and ensure that no observed security/data event intersects the read interval. If the deployed API cannot provide a sufficient fence, retry a bounded read or fail closed rather than publish a mixed authorization epoch.
7. Atomically replace the prior Projection only after every required block, relationship deletion, cursor, schema, completeness marker, and digest validates.

### Hidden or redacted material

- Omit unauthorized bodies, identifiers, names, types, topology, counts, and provenance details unless OpenCTI explicitly authorizes those metadata.
- Mark the semantic block as an `authorized_view` and expose only a non-leaking completeness/redaction category that the actor is allowed to know.
- Do not convert “not returned” into “does not exist,” “was deleted,” or “the Case contains no additional material.”
- On visibility loss, clear cached bodies and all rendered context derived from them. Retain only non-content operational receipts required for audit and recovery.

### Change handling

- Use an authenticated stream/trigger to reduce invalidation latency, but treat its payload as a hint rather than the new Projection.
- Classify deletion-like notification as real deletion or visibility loss only through a current actor-scoped read; if distinction is unauthorized or impossible, retain the conservative `deleted_or_visibility_lost` reason.
- Maintain and validate cursor continuity. On a gap, expired cursor, filter/principal change, merge, cascade deletion, or digest mismatch, discard incremental state and perform a full rebase.
- Use update/reverse patches only when the entire compatible, authorized chain is present. Never splice blocks from different reads or security epochs.

### Historical behavior

- Promise current authorized Projection receipts and version-bounded artifacts, not native OpenCTI as-of replay.
- Treat stream retention, History, Activity, and Trash as independent, configurable aids. Loss of any one must not corrupt current Projection correctness.
- Historical Session prose may refer to an old Projection receipt only while policy still permits it. Authorization revocation removes the underlying body from future model use even if a digest or old receipt remains.

### Connector and workbench behavior

- Project only main-knowledge state as current Case authority.
- Represent workbench or Draft material, if needed, as separately labeled pending operational state.
- Preserve connector user, connector type, source, ingestion method, workbench/Draft validation path, markings, and resource provenance; none is a truth guarantee.

## Failure-oriented acceptance implications

1. Removing one allowed marking during a paginated Projection read prevents atomic installation even if all network calls returned successfully.
2. Adding an inaccessible marking to a contained relationship removes that edge and challenges only outputs that depended on it; it does not reveal the edge's continued existence.
3. Removing the actor from the Case's Authorized Members invalidates the full Case Projection even when the Case body and contained resources did not change.
4. Restricting only the Case container does not purge globally reusable Intelligence Resources that remain independently authorized, but it prevents using their former Case role.
5. A deletion notification followed by an unauthorized read is handled as visibility revocation, not as a confirmed tombstone and not as historical-readable content.
6. A real relationship deletion removes the edge from the next complete Projection and challenges dependent artifacts while leaving unrelated endpoint material usable.
7. A merge or cascade deletion with incomplete event context forces a full rebase; no partial graph is published.
8. A reconnect from a cursor older than stream retention performs current recovery/full rebase and records that historical continuity was lost.
9. Missing History or Trash records do not prevent current recovery and do not prove that an object never existed.
10. A connector workbench result is absent from current Case authority until validation; a direct CSV import is visible as imported knowledge but carries no human-review claim.
11. A Draft approved while a process remains active does not make the lost process output part of the Case Projection.
12. A result returned after account lock, group/role change, organization change, Authorized Member change, or marking change fails the end authorization fence and never enters model context.

## Open deployment questions requiring verification

These are not answered by the reviewed public documentation and must be resolved against the selected OpenCTI release and production configuration before claiming stronger guarantees:

- whether one GraphQL operation observes a stable backend snapshot across all fields and resolvers;
- whether the selected Case queries expose stable per-object versions sufficient for optimistic validation;
- whether an API can return an actor's complete effective authorization state or a monotonic policy revision;
- whether the production stream represents organization and Authorized Member visibility changes with enough continuity and non-leaking semantics for the chosen principal;
- how the stream reports an inaccessible relationship when one endpoint remains visible;
- whether the deployment retains a complete event/history archive outside Redis trimming and History retention;
- whether any supported API can perform an authorized as-of read; and
- how a trusted technical Adapter can impersonate the actor without receiving broader readable output.

Absent affirmative, tested answers, the conservative behavior above remains required.

## Primary sources reviewed

- [OpenCTI: GraphQL API](https://docs.opencti.io/latest/reference/api/)
- [OpenCTI: Users and Role Based Access Control](https://docs.opencti.io/latest/administration/users/)
- [OpenCTI: Marking restriction](https://docs.opencti.io/latest/administration/segregation/)
- [OpenCTI: Authorized members](https://docs.opencti.io/latest/administration/authorized-members/)
- [OpenCTI: Case management](https://docs.opencti.io/latest/usage/case-management/)
- [OpenCTI: Containers](https://docs.opencti.io/latest/usage/containers/)
- [OpenCTI: Data Streaming](https://docs.opencti.io/latest/reference/streaming/)
- [OpenCTI: Notifications and alerting](https://docs.opencti.io/latest/usage/notifications/)
- [OpenCTI: Delete and restore knowledge](https://docs.opencti.io/latest/usage/delete-restore/)
- [OpenCTI: Activity overview](https://docs.opencti.io/latest/administration/audit/overview/)
- [OpenCTI: Platform managers](https://docs.opencti.io/latest/deployment/advanced/managers/)
- [OpenCTI: Retention policies](https://docs.opencti.io/latest/administration/retentions/)
- [OpenCTI: Connectors](https://docs.opencti.io/latest/deployment/connectors/)
- [OpenCTI: Automated import connectors](https://docs.opencti.io/latest/usage/import/external-connectors/)
- [OpenCTI: Import from files](https://docs.opencti.io/latest/usage/import-files/)
- [OpenCTI: Analyst workbench](https://docs.opencti.io/latest/usage/workbench/)
- [OpenCTI: Draft workspaces](https://docs.opencti.io/latest/usage/draftWorkspaces/)
- [OASIS: STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html)
- [WHATWG: Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html#server-sent-events)
- [Redis: `XTRIM`](https://redis.io/docs/latest/commands/xtrim/)
