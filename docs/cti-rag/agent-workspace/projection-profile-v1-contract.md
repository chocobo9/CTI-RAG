# `opencti-case-projection/v1` Contract

Status: Accepted and frozen strict-R1 target contract; not a current Orientation-cycle dependency.

This document is normative for Profile compilation, Adapter qualification, Projection publication, dependency binding, and behavior acceptance. It defines Workspace semantics, not OpenCTI GraphQL DTOs or model-visible tool decomposition.

## 1. Decision

`opencti-case-projection/v1` is a composed Case Management Profile. A complete instance requires:

- actor-scoped, item-authorized facts read from a qualified OpenCTI Adapter;
- revisioned Case semantic metadata owned by the Case Management facade; and
- one Revision Authority that fences both the composed Projection and every write enabled by that activation.

Stock OpenCTI is a qualified data source for parts of the Profile, not the authority for the complete Profile. It does not natively carry the investigation purpose and mandate, controls, classified human direction, accepted/negative findings, Case-specific evidence roles, semantic change attribution, proposal ledger, or an aggregate Case revision. Arbitrary Notes, Opinions, labels, statuses, or containment edges must not be promoted into those meanings.

The current stock-only experience uses the smaller [`opencti-case-orientation/v1`](opencti-case-orientation-v1-contract.md). It has a different identity and does not claim the completeness, revision, or write basis of this Profile.

## 2. Revision Authority

**Problem solved:** an opaque revision is unsafe when the reader and writer attach different meaning or serialization domains to the same token.

**Inputs:** authority identity, revision-contract version, Case identity, actor/purpose view, and the mutable semantic blocks covered by the authority.

**Output:** a `RevisionAuthorityRef` and an opaque `CaseRevision` that are comparable only inside that authority, contract version, and Case.

**Boundary:** Revision Authority is not an Adapter, database, timestamp, OpenCTI cursor, Projection digest, or deployment name. It must serialize every mutation to the semantic blocks it declares covered. Independently writable state is either excluded from the revision domain and separately versioned, or its owner must atomically advance this authority's Case head.

**Failure behavior:** a revision with a different authority, contract version, or Case is incomparable. It cannot open a write-enabled activation or satisfy expected-revision validation. Changing authority requires a fresh activation and fresh Projection; outstanding operations remain pinned to the old archived contract and cannot be rebased automatically.

```typescript
interface RevisionAuthorityRef {
	authorityId: string;
	revisionContract: "case-revision/v1";
	caseId: string;
}

interface AuthorityRevision {
	authority: RevisionAuthorityRef;
	revision: string;
}
```

The pair, not the token string alone, is the concurrency identity.

For this Profile, the Case Revision covers facade-owned purpose/mandate, scope/controls, classified Human Direction, accepted state, facade work metadata, canonical neutral membership/Case roles, semantic change attribution, and Case command head. The proposal ledger is deliberately outside that domain because terminal no-effect and `satisfied_without_change` receipts change ledger state without changing Case semantics; `proposalLedgerRevision` fences it independently. Case Revision also does not claim to version independently writable OpenCTI technical facts. Those facts are fenced by each block's typed `SourceVersionEvidenceV1`, and the complete multi-source observation evidence is identified by `observationEvidenceDigest`.

R1 admission consumes the facade Case head plus current facade authorization/policy/Grant/lifecycle fences and an I&E-owned operation-bound Resource-use permit. OpenCTI object versions/materialization evidence are Projection read dependencies; they are not reinterpreted as part of the facade Case Revision. A future Capability that mutates an OpenCTI-owned fact directly must declare and atomically validate that source's own precondition or remain disabled.

## 3. Projection Snapshot

**Problem solved:** a bag of graph objects cannot prove which Case meaning was selected, authorized, complete, version-consistent, or safe to use as a write basis.

**Inputs:** active compiled Profile, actor/purpose/selection, authority revision and fences, qualified OpenCTI source observations, facade semantic overlay, and current Capability Grants.

**Output:** one closed, digest-addressed `CaseProjectionV1` whose eight block slots occur exactly once.

**Boundary:** the Projection contains bounded semantic state and stable references. Large bodies and arbitrary graph neighborhoods remain in I&E or source systems. A Projection is not a remote snapshot lease, historical reconstruction guarantee, or permission to mutate.

**Failure behavior:** unknown members, missing block slots, mixed authorities, stale fences, incomplete traversal, unsafe redaction, digest mismatch, or an unavailable required semantic block publish no Projection. An unavailable optional block disables only dependent operations.

```typescript
type ProjectionPresence<T> =
	| { kind: "populated"; value: T; evidence: PopulatedEvidenceV1 }
	| { kind: "empty"; evidence: EmptyEvidenceV1 }
	| { kind: "redacted"; disclosureCode: string; evidence: RedactionEvidenceV1 }
	| { kind: "not_applicable"; reasonCode: string; evidence: AuthorityDecisionEvidenceV1 }
	| { kind: "not_selected"; selectionReason: string; selectionDigest: string }
	| { kind: "unavailable"; reasonCode: string; retryable: boolean; failedQualifierId: string };

interface PopulatedEvidenceV1 {
	qualifierId: string;
	selectedScopeDigest: string;
	completionEvidenceDigest: string;
	authorizationFilterEvidenceDigest: string;
}

interface EmptyEvidenceV1 {
	qualifierId: string;
	selectedScopeDigest: string;
	authorityAbsenceEvidenceDigest: string;
	authorizationFilterEvidenceDigest: string;
}

interface RedactionEvidenceV1 {
	disclosureDecisionRevision: string;
	disclosureEvidenceDigest: string;
}

interface AuthorityDecisionEvidenceV1 {
	authorityId: string;
	decisionRevision: string;
	decisionEvidenceDigest: string;
}

type SourceMaterializationEvidenceV1 =
	| {
		kind: "authority_snapshot";
		snapshotAuthorityId: string;
		snapshotDomainId: string;
		snapshotToken: string;
		qualifierId: string;
	  }
	| {
		kind: "bounded_double_observation";
		qualifierId: string;
		firstPassComparisonDigest: string;
		secondPassComparisonDigest: string;
		completionEvidenceDigest: string;
	  };

type SourceFenceV1 =
	| { kind: "object_version"; objectRef: string; version: string }
	| { kind: "traversal_completion"; qualifierId: string; scopeDigest: string; evidenceDigest: string }
	| { kind: "authorization_filter"; authorizationRevision: string; evidenceDigest: string }
	| { kind: "cursor_continuity"; cursorStart: string; cursorEnd: string; continuity: "continuous" | "gap_detected" };

interface SourceVersionEvidenceV1 {
	sourceId: string;
	adapterArtifactDigest: string;
	targetFingerprint: string;
	observationStart: string;
	observationEnd: string;
	materialization: SourceMaterializationEvidenceV1;
	fences: readonly SourceFenceV1[];
}

interface ProjectionBlock<T> {
	presence: ProjectionPresence<T>;
	semanticDigest: string;
	authority: "case_authoritative" | "human_direction" | "accepted_outcome" | "open_question";
	sourceEvidence: readonly SourceVersionEvidenceV1[];
	securityLabels: readonly string[];
}

interface CaseCapabilityGrantV1 {
	capabilityId: string;
	capabilityVersion: string;
	manifestDigest: string;
	grantRevision: string;
	lifecycleRevision: string;
	state: "available" | "approval_required" | "unavailable";
}

interface CaseProjectionV1 {
	protocol: "opencti-case-projection/v1";
	caseId: string;
	authorityRevision: AuthorityRevision;
	authorizationRevision: string;
	policyRevision: string;
	proposalLedgerRevision: string;
	profileManifestDigest: string;
	catalogDigest: string;
	activationDigest: string;
	schemaVersion: "case-projection-v1";
	actorId: string;
	purpose: string;
	selectionDigest: string;
	projectedAt: string;
	viewScope: "actor_authorized_profile_view";
	materializationStrength: "authority_snapshot" | "bounded_double_observation";
	blocks: {
		case_spine: ProjectionBlock<CaseSpineV1>;
		scope_and_controls: ProjectionBlock<ScopeAndControlsV1>;
		human_direction: ProjectionBlock<readonly HumanDirectionV1[]>;
		accepted_state: ProjectionBlock<readonly AcceptedStateV1[]>;
		open_work: ProjectionBlock<readonly OpenWorkV1[]>;
		resource_index: ProjectionBlock<readonly ResourceIndexEntryV1[]>;
		recent_change: ProjectionBlock<readonly RecentChangeV1[]>;
		proposal_status: ProjectionBlock<readonly ProposalStatusSummaryV1[]>;
	};
	capabilityGrants: readonly CaseCapabilityGrantV1[];
	semanticDigest: string;
	observationEvidenceDigest: string;
}
```

The JSON representation is closed at every object boundary. Compiler-generated JSON Schema must reject unknown members, duplicate JSON names, invalid Unicode, non-finite numbers, unsafe numeric integers, and unrecognized discriminants before canonicalization under `cti-jcs-sha256/v1`.

### Presence, source evidence, and digests

**Problem solved:** free-form `empty`, completeness, version, or snapshot claims let production and in-memory Adapters attach different meaning to the same strings.

**Inputs:** one Profile-qualified traversal/overlay qualifier, actor-safe selected-scope digest, owner-issued revision/fence evidence, and closed presence reason.

**Output:** a machine-verifiable presence envelope and typed source evidence for each block, plus two distinct canonical digests.

**Boundary:** `authority_snapshot` may be asserted only by a qualified owner that controls every write in the named snapshot domain. Stock OpenCTI does not qualify for an aggregate Case snapshot and contributes `bounded_double_observation` by default. A facade transaction snapshot covers only facade-owned state; it never extends to independently writable OpenCTI facts. Evidence digests and scopes expose no hidden item count, identifier, type, marking, or topology.

**Failure behavior:** unknown qualifier, missing completion/authorization evidence, inconsistent two-pass digests, gap-detected required traversal, unsupported snapshot domain, or unverifiable evidence digest makes the block unavailable or rejects the required Profile. It is never converted to `empty`.

`ProjectionBlock.semanticDigest` is SHA-256 over JCS of exactly `{ blockKey, normalizedPresenceSemanticValue, authority, securityLabels }`. The normalized presence value is closed: populated includes `{ kind, value }`; empty includes `{ kind, selectedScopeDigest }`; redacted includes `{ kind, disclosureCode, disclosureDecisionRevision }`; not-applicable includes `{ kind, reasonCode, authorityId, decisionRevision }`; not-selected includes `{ kind, selectionReason, selectionDigest }`; unavailable includes `{ kind, reasonCode, retryable, failedQualifierId }`. It excludes source evidence, observation times, target fingerprints, and completion-proof renewal data. Hidden values never enter it.

`CaseProjectionV1.semanticDigest` covers protocol/schema/Profile identity, actor/purpose/selection, and the ordered eight `(blockKey, block.semanticDigest)` pairs. It excludes projected time, source observations, Revision token, Grants, catalog/activation deployment identity, and rendering. Those remain separate fences.

Each complete materialization pass computes `passComparisonDigest` over the authority tuple/revision, authorization/policy/proposal-ledger revisions, Profile/catalog/activation, selection, all block semantic digests, normalized non-temporal source fences, completion/authorization evidence digests, and Capability Grants. It excludes observation timestamps and the entire `SourceMaterializationEvidenceV1` envelope, so it is not self-referential. Double observation requires equal first/second pass digests. The final `observationEvidenceDigest` then covers those pass digests plus the installed source-materialization evidence. Equality of rendered text or block semantic digests alone is insufficient.

Projection `materializationStrength` is `authority_snapshot` only when every selected populated/empty required source is covered by one qualified snapshot domain or by explicitly composed snapshot domains whose cross-domain consistency contract is qualified. If any selected OpenCTI contribution uses double observation, the whole Projection strength is `bounded_double_observation`.

## 4. Block contracts

### 4.1 Case Spine

**Problem solved:** the Agent needs stable Case orientation without treating OpenCTI display fields as a complete mandate.

**Inputs:** qualified Case root facts plus facade-owned purpose and mandate metadata.

**Output:** stable identity, supported Case kind, lifecycle, purpose, mandate, and ownership/source origins.

**Boundary:** the first Profile supports `incident_response`, `request_for_information`, and `request_for_takedown`. A configured OpenCTI status is not a lifecycle meaning until the Adapter maps and qualifies it.

**Failure behavior:** missing purpose/mandate overlay, unsupported Case kind, ambiguous lifecycle mapping, or inaccessible root makes the block `unavailable`; it is never guessed from prose.

```typescript
interface CaseSpineV1 {
	caseRef: string;
	displayName: string;
	caseKind: "incident_response" | "request_for_information" | "request_for_takedown";
	lifecycle: "open" | "held" | "closed" | "cancelled";
	purpose: string;
	mandate: string;
	owners: readonly string[];
	origins: readonly { field: string; owner: "opencti" | "case_management"; sourceRef: string }[];
}
```

The schema reserves all three official OpenCTI Case kinds, but the first production activation serves only `incident_response`. RFI and takedown Cases return `profile_contract_not_served` until their purpose, lifecycle, scope/control, work, and authorization fixtures are independently qualified. This limits the first vertical slice without requiring a future incompatible schema change.

### 4.2 Scope and Controls

**Problem solved:** retrieval and proposals are unsafe when the permitted investigation scope and prohibited actions are implicit.

**Inputs:** facade-owned, revisioned scope/control declarations and current policy interpretation.

**Output:** included and excluded scope, time boundaries, handling constraints, prohibited actions, and control limitations.

**Boundary:** this block describes Case direction; current authorization, policy, Grant, and Capability lifecycle remain separate live fences.

**Failure behavior:** absent or contradictory overlay makes the full Profile unavailable. It cannot be reconstructed from OpenCTI markings alone.

```typescript
interface ScopeAndControlsV1 {
	includedScope: readonly string[];
	excludedScope: readonly string[];
	timeBounds?: { from?: string; through?: string };
	handlingConstraints: readonly string[];
	prohibitedActions: readonly string[];
	controlLimitations: readonly string[];
}
```

### 4.3 Human Direction

**Problem solved:** current analyst corrections must override stale Agent context without promoting every Note to an instruction.

**Inputs:** facade-classified direction records with author role, effective time, status, and supersession chain.

**Output:** only current or historically referenced `direction` and `correction` records with explicit lifecycle.

**Boundary:** ordinary Notes, comments, Opinions, or free text are excluded unless an authorized workflow classifies them as Human Direction.

**Failure behavior:** broken supersession, unknown status, missing author authority, or ambiguous classification makes the affected record unavailable; required-block incompleteness rejects publication.

```typescript
interface HumanDirectionV1 {
	directionId: string;
	kind: "direction" | "correction";
	text: string;
	status: "current" | "superseded" | "withdrawn";
	supersedes: readonly string[];
	authorRole: string;
	effectiveAt: string;
	scope: readonly string[];
}
```

### 4.4 Accepted State

**Problem solved:** accepted Case conclusions must be distinguishable from source reporting, Agent drafts, and graph containment.

**Inputs:** facade-owned accepted finding, decision, and negative-finding records with authority and evidence references.

**Output:** scoped, stable accepted records.

**Boundary:** OpenCTI Opinions, inferred relations, labels, containment, or high scores are not accepted Case state. Negative findings require the searched scope, method, and basis; absence of a match is insufficient.

**Failure behavior:** missing acceptance authority, scope, status, or required negative-finding basis excludes the item and makes completeness fail if the authority reports an unmaterializable current item.

```typescript
interface AcceptedStateV1 {
	stateId: string;
	kind: "finding" | "decision" | "negative_finding";
	proposition: string;
	status: "accepted" | "accepted_but_challenged" | "revoked" | "superseded";
	scope: readonly string[];
	authorityRef: string;
	evidenceRefs: readonly string[];
	negativeBasis?: { searchedScope: string; method: string; basisDigest: string };
}
```

### 4.5 Open Work

**Problem solved:** unresolved tasks and contradictions must remain visible without interpreting every OpenCTI Task status by name.

**Inputs:** exhaustive actor-authorized Task/work traversal plus qualified status mapping and facade-owned question/blocker/contradiction metadata.

**Output:** active tasks, questions, blockers, and contradictions with lifecycle, owners, deadlines, and dependency references.

**Boundary:** nested Case Task lists are not assumed exhaustive. Deployment qualification must prove the top-level traversal, filtering, pagination, item authorization, and Case association used.

**Failure behavior:** truncated traversal, unknown status template, inaccessible required item, or continuity loss makes the block unavailable rather than silently partial.

```typescript
interface OpenWorkV1 {
	workId: string;
	kind: "task" | "question" | "blocker" | "contradiction";
	summary: string;
	lifecycle: "open" | "blocked" | "completed" | "cancelled";
	owners: readonly string[];
	deadline?: string;
	blockedBy: readonly string[];
}
```

### 4.6 Resource Index

**Problem solved:** the Workspace needs stable Resource versions and Case roles without confusing neutral membership with evidentiary judgment.

**Inputs:** facade-owned canonical authoritative membership, actor-authorized OpenCTI materialization observation, I&E Resource identity/version, and facade-owned Case-role/evidence assessment.

**Output:** neutral Resource References and separately classified evidence roles.

**Boundary:** neutral membership identity is the canonical tuple `(openctiInstanceId, caseId, "object", resourceId)`, not an unstable OpenCTI reference-relation record ID. Membership is not support, contradiction, acceptance, or provenance.

**Failure behavior:** missing Resource version, unsafe endpoint authorization, ambiguous membership, or role without overlay makes the selected whole block `unavailable`; an entry is never silently omitted and no per-entry unavailable marker reveals hidden cardinality. Recipes that did not select or depend on `resource_index` may continue. It does not infer a STIX semantic relationship.

```typescript
interface ResourceIndexEntryV1 {
	resourceRef: string;
	resourceVersion: string;
	membershipKey: string;
	caseRole: "neutral_reference" | "supporting_evidence" | "contradicting_evidence" | "context_only";
	evidenceAssessmentRef?: string;
	provenanceSummary: string;
	availability: "available" | "withdrawn" | "visibility_lost";
}
```

### 4.7 Recent Change

**Problem solved:** signals can target revalidation without pretending an event feed reconstructs current or historical Case truth.

**Inputs:** authority-owned change attribution plus bounded OpenCTI stream/history hints.

**Output:** authorized change references, affected block keys, and explicit continuity strength.

**Boundary:** this block never replaces current state, CaseRevision, or as-of reconstruction.

**Failure behavior:** gaps, retention loss, or ambiguous visibility widen reconciliation to the smallest safe authority partition and record continuity as unavailable; they never prove no change.

```typescript
interface RecentChangeV1 {
	changeRef: string;
	affectedBlocks: readonly (keyof CaseProjectionV1["blocks"])[];
	changedAt?: string;
	actorRef?: string;
	continuity: "continuous" | "bounded" | "gap_detected";
}
```

### 4.8 Proposal Status

**Problem solved:** crash recovery and user explanation need authoritative proposal state without exposing request bodies or treating local logs as Case truth.

**Inputs:** Case Management facade operation ledger and current actor disclosure decision.

**Output:** terminal receipt or retained tombstone summaries for the current actor/Workspace scope.

**Boundary:** OpenCTI entity presence, history, or transport responses cannot populate this block. Full receipts remain in the durable journal/facade ledger.

**Failure behavior:** ledger unavailability is `unavailable`, not empty or rejected. A hidden proposal reveals no identifier or existence unless disclosure policy explicitly permits a redacted envelope.

```typescript
type ProposalStatusSummaryV1 =
	| { state: "terminal"; operationId: string; effectId: string; disposition: "applied"; resultingRevision: string }
	| { state: "terminal"; operationId: string; effectId: string; disposition: "satisfied_without_change"; resultingRevision: string }
	| {
		state: "terminal";
		operationId: string;
		effectId: string;
		disposition: "conflict" | "rejected" | "not_authorized" | "grant_unavailable" | "contract_not_served";
	  }
	| { state: "gone"; identityDigest: string; identityTombstoneRetainedUntil: string };
```

`accepted_but_unsynchronized` is Workspace-local synchronization state and is not inferred from this summary alone. It requires a full `applied` receipt without the exact Projection inclusion proof.

## 5. Presence and usability rules

All eight slots are mandatory. The slot envelope may express absence; omission is invalid.

| Block | Allowed for a usable full Profile |
|---|---|
| `case_spine` | `populated` only |
| `scope_and_controls` | `populated` only |
| `human_direction` | `populated` or authority-confirmed `empty` |
| `accepted_state` | `populated` or authority-confirmed `empty` |
| `open_work` | `populated` or authority-confirmed `empty` |
| `resource_index` | `populated`, `empty`, `not_selected`, or `unavailable`; selected incompleteness makes the whole block unavailable and disables only dependent recipes |
| `recent_change` | `populated`, `empty`, `not_selected`, or `unavailable`; it never supplies current truth |
| `proposal_status` | `populated`, `empty`, or `unavailable`; unavailability disables actor/model-visible proposal summaries but never the private identity-scoped receipt-reconciliation path |

`redacted` and `not_applicable` are allowed only for a block and Case-kind combination explicitly declared in the compiled Profile. They never satisfy an operation input requiring actual content. A Profile can be published for orientation when `resource_index`, `recent_change`, or `proposal_status` is unavailable, but the active contract marks only actor/model recipes that require those blocks unavailable. Protected receipt reconciliation is not a Projection recipe. The Profile is not published when any of the first five semantic obligations is unavailable.

## 6. Trusted binder

**Problem solved:** model or caller data must not choose security, concurrency, dependency, or contract fields.

**Inputs:** verified Workspace binding, active contract, current Projection candidate, qualified source evidence, and authority responses.

**Output:** the exact snapshot fields, typed dependency references, and render inputs used by `OperationCoordinator`.

**Boundary:** the model may choose investigation intent and task-selected business references only. It cannot choose authority identity, revision, actor, purpose, Profile/catalog/activation digest, authorization/policy revision, block digest, source version, Grant, or dependency key.

**Failure behavior:** a model payload containing trusted fields is rejected and audited. Missing trusted data disables the dependent recipe; no fallback is inferred from display text.

## 7. Materialization protocol

Without a stronger authority snapshot, qualification must implement this bounded protocol:

1. Read and validate the Workspace binding, activation, Case authority head, independent proposal-ledger revision, authorization, policy, and overlay revision.
2. Capture OpenCTI root/version evidence and selection inputs.
3. Traverse every required collection through a deployment-qualified exhaustive path, applying item-level markings and Authorized Members checks before staging.
4. Resolve references/endpoints and I&E Resource versions; never cache unauthorized hidden structure.
5. Read facade semantic overlay at the captured Case head and proposal ledger at the separately captured `proposalLedgerRevision`.
6. Re-read root, Case head, proposal-ledger revision, authorization, policy, overlay, and traversal continuity fences.
7. Repeat the complete materialization when the Adapter offers no single snapshot, not merely the final page or root.
8. Require two complete authorized passes with identical `passComparisonDigest` within the operation budget.
9. Atomically publish the composed Projection and derivation records, or publish nothing.

`bounded_double_observation` proves only bounded stability of two complete observations. It must not be described as a remote snapshot or historical as-of view. Any drift, visibility ambiguity, page/traversal limit, or fence mismatch restarts within budget or returns unavailable.

## 8. Dependency origins

The Profile emits closed typed references for at least:

- `authorization-scope/v1(actorId, caseId, purpose)`;
- `case-head/v1(authorityId, caseId)`;
- `projection-block-head/v1(authorityId, caseId, blockKey)` for current use of every selected block;
- `projection-block-version/v1(authorityId, caseId, blockKey, semanticDigest)` for semantic derivation/audit of that exact block value;
- `proposal-ledger-head/v1(authorityId, caseId)` plus `proposal-ledger-version/v1(authorityId, caseId, proposalLedgerRevision)` for actor-visible proposal state;
- `capability-policy/v1(authorityId, caseId, capabilityId, grantRevision)`;
- `intelligence-resource/v1(ownerId, resourceId, resourceVersion)` for each selected Resource;
- `execution-config/v1(catalogDigest, activationDigest, rendererVersion)`.

Equality requires identical owner, kind, key version, and canonical tuple bytes. Runtime prefix matching or semantic-overlap guessing is forbidden. Recipes must explicitly declare broad `case-head/v1` input or effect domains when the authority's granularity requires it.

The head and version keys are deliberately separate. A possible R1 effect reserves `projection-block-head/v1(..., resource_index)`, and every current consumer of the Resource Index explicitly reads that same head key plus its exact version key. This creates mechanical intersection without inventing wildcard or prefix overlap; historical consumers of only the exact version need not wait.

## 9. Qualification and failure codes

Qualification binds exact Adapter artifact digest, OpenCTI release/deployment fingerprint, facade release, GraphQL selections, page limits, status templates, marking/Authorized Members rules, traversal proofs, start/end probes, overlay schema, conformance-suite version, and evidence expiry.

Minimum closed failure codes are:

- `profile_contract_not_served`;
- `revision_authority_mismatch`;
- `case_root_unavailable`;
- `semantic_overlay_unavailable`;
- `required_block_unavailable`;
- `unsupported_case_kind`;
- `unmapped_lifecycle`;
- `incomplete_traversal`;
- `authorization_drift`;
- `policy_drift`;
- `authority_revision_drift`;
- `source_observation_drift`;
- `visibility_or_deletion_ambiguous`;
- `digest_mismatch`;
- `materialization_budget_exhausted`.

Errors expose only actor-safe identifiers and reason codes. They contain no hidden counts, types, topology, or source bodies.

## 10. Acceptance

The Profile must pass the normative behavior tests in the main design and fixtures PF-01 through PF-30 in [OpenCTI Projection Profile v1 feasibility research](../research/opencti-projection-profile-v1-feasibility.md). Production activation additionally requires deployment-specific traversal and authorization evidence; fixture success alone cannot activate a deployment.
