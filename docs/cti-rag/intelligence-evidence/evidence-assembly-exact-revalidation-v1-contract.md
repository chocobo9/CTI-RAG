# `evidence-assembly-exact-revalidation/v1` Contract

Status: **Design PASS; implementation readiness NO.**

This contract adds one request profile behind the existing
`IntelligenceEvidenceModule.retrieve(...)` Interface. It does not add a Module,
root method, graph client, vector client, model call or Workspace dependency.

## 1. Purpose

Evidence Assembly must know whether material already admitted to a task Working
Set is still usable and exactly what provenance, source-assertion, relationship
and lineage observations I&E can currently prove.

This profile performs that exact revalidation. It does not:

- run lexical, vector or graph search;
- expand a query or discover neighboring resources;
- substitute a newer Resource Version or Source Capture;
- decide whether material supports a Task Result statement;
- assign a Case evidentiary role; or
- return unrestricted source bodies.

## 2. Public Interface amendment

The existing root method remains:

```ts
interface IntelligenceEvidenceModule {
	retrieve(
		request: RetrievalRequest,
		options?: { signal?: AbortSignal },
	): Promise<RetrievalOutcome>;
}
```

`RetrievalRequest` and `RetrievalOutcome` gain one closed versioned union
member. Existing exact-resource request and outcome behavior is unchanged.

Workspace maps its Working Set records into this I&E-owned request. I&E imports
no Workspace, Pi, Agent or Case Management type.

## 3. Closed request

```ts
interface EvidenceAssemblyRevalidationRequestV1 {
	protocol: "evidence-assembly-exact-revalidation/v1";
	requestId: string;
	access: {
		principalRef: string;
		credentialRef: string;
		usePurpose: "case_investigation";
		workspaceRef: string;
		caseRef: string;
		taskRef: string;
	};
	assemblyBasis: {
		assemblyAttemptRef: string;
		taskResultRef: string;
		taskResultDigest: string;
		workingSetSelectionDigest: string;
	};
	profile: {
		profileRef: string;
		profileVersion: string;
		profileDigest: string;
	};
	orderedSubjects: readonly EvidenceAssemblyRevalidationSubjectV1[];
}

interface EvidenceAssemblyRevalidationSubjectV1 {
	correlationRef: string;
	resourceVersionRef: string;
	sourceCaptureId: string;
	resourceCapsuleSemanticDigest: string;
	admissionReceipt: {
		retrievalId: string;
		keyId: string;
		signedPayloadDigest: string;
	};
	expectedUseDecisionRevision: string;
	orderedSourceSpanRefs: readonly string[];
	orderedSourceRelationshipRefs: readonly string[];
}
```

`correlationRef` is a request-local opaque caller correlation value. It carries
no source authority and is returned unchanged. Every other subject member is
resolved from the exact retained I&E operation and independently verified.

The model cannot construct or change this request. Trusted Workspace code
derives it from one committed Task Result, one exact Working Set selection and
the authenticated admission receipts of those entries.

Unknown members, duplicate subjects, duplicate refs within one subject,
non-canonical order, missing admission evidence or a cross-task/access/profile
binding reject the complete request before source I/O.

## 4. Closed outcome

```ts
type EvidenceAssemblyRevalidationOutcomeV1 =
	| {
			kind: "completed";
			receipt: EvidenceAssemblyRevalidationReceiptV1;
			view: EvidenceAssemblyQualifiedViewV1;
	  }
	| { kind: "cancelled" }
	| { kind: "failed"; failure: EvidenceAssemblyRevalidationFailureV1 };

interface EvidenceAssemblyQualifiedViewV1 {
	protocol: "evidence-assembly-qualified-view/v1";
	requestId: string;
	orderedSubjects: readonly EvidenceAssemblySubjectQualificationV1[];
	orderedLineageGroups: readonly EvidenceAssemblyLineageGroupV1[];
	orderedLineagePairs: readonly EvidenceAssemblyLineagePairV1[];
	coverage: EvidenceAssemblyQualificationCoverageV1;
	semanticDigest: string;
}

type EvidenceAssemblySubjectQualificationV1 =
	| EvidenceAssemblyEligibleSubjectV1
	| EvidenceAssemblyIneligibleSubjectV1;
```

A `completed` request contains exactly one outcome in request order for every
subject. Subject ineligibility is a complete qualification result, not partial
transport success. Infrastructure, integrity, cancellation or incomplete
observation fails/cancels the whole request and publishes no view.

### 4.1 Eligible subject

```ts
interface EvidenceAssemblyEligibleSubjectV1 {
	kind: "eligible";
	correlationRef: string;
	resourceVersionRef: string;
	sourceCaptureId: string;
	resourceCapsuleSemanticDigest: string;
	sourceChannelRef: string;
	sourceChannelDigest: string;
	citationProjection: {
		displayTitle: string;
		sourceType: string;
		versionLabel: string | null;
		publishedAt: string | null;
		actorSafeLocator: string | null;
		projectionDigest: string;
	};
	useDecisionRevision: string;
	useDecisionObservedAt: string;
	retentionUntil: string;
	orderedQualifiedSpans: readonly QualifiedSourceSpanV1[];
	orderedSourceAssertions: readonly SourceAssertionObservationV1[];
	orderedSourceRelationships: readonly SourceRelationshipObservationV1[];
	lineageGroupRef: string;
	subjectDigest: string;
}

type EvidenceAssemblyCanonicalJsonValueV1 =
	| null
	| boolean
	| number
	| string
	| readonly EvidenceAssemblyCanonicalJsonValueV1[]
	| { readonly [key: string]: EvidenceAssemblyCanonicalJsonValueV1 };

type QualifiedSourceSpanV1 =
	| {
			kind: "bounded_text";
			sourceSpanRef: string;
			text: string;
			textDigest: string;
			spanDigest: string;
	  }
	| {
			kind: "structured_json";
			sourceSpanRef: string;
			value: EvidenceAssemblyCanonicalJsonValueV1;
			valueDigest: string;
			spanDigest: string;
	  };

interface SourceAssertionObservationV1 {
	assertionRef: string;
	kind:
		| "structured_value"
		| "source_relationship"
		| "bounded_text_span";
	orderedSourceSpanRefs: readonly string[];
	assertionDigest: string;
}

interface SourceRelationshipObservationV1 {
	relationshipRef: string;
	relationshipVersionRef: string;
	relationshipType: string;
	fromResourceVersionRef: string;
	toResourceVersionRef: string;
	orderedSourceSpanRefs: readonly string[];
	relationshipDigest: string;
}
```

Qualified spans contain only the exact requested bounded span content needed
for downstream citation projection. They are protected response data, not
unrestricted source bodies, Session entries or globally reusable excerpts.
Structured values must be closed RFC 8785 JSON-domain values; `undefined`,
non-finite numbers, functions and cyclic values reject the whole result.

An assertion observation means only that the exact source version/span states
or represents that proposition. I&E does not return a semantic-support score or
claim that two differently worded assertions have the same meaning.

`assertionDigest` identifies the exact source assertion projection. Equal
digests permit deterministic exact-occurrence grouping. Unequal digests are
never merged by this profile merely because vector similarity, graph proximity
or model text says they are similar.

A source relationship is returned only when its exact version, endpoints and
source spans are qualified. An endpoint not represented by a qualified Resource
Version makes that relationship ineligible; hidden endpoint identity is not
returned.

### 4.2 Ineligible subject

```ts
interface EvidenceAssemblyIneligibleSubjectV1 {
	kind: "ineligible";
	correlationRef: string;
	code:
		| "not_found_or_not_visible"
		| "use_not_permitted"
		| "retention_expired"
		| "qualification_changed"
		| "identity_or_receipt_mismatch"
		| "required_span_unavailable"
		| "required_relationship_unavailable";
	subjectDigest: string;
}
```

The code is private Workspace evidence and remains actor-safe. It contains no
hidden identifier, marking topology, credential detail, backend error or source
body.

### 4.3 Lineage view

```ts
interface EvidenceAssemblyLineageGroupV1 {
	lineageGroupRef: string;
	orderedCorrelationRefs: readonly string[];
	assessmentRevision: string;
	groupDigest: string;
}

interface EvidenceAssemblyLineagePairV1 {
	leftLineageGroupRef: string;
	rightLineageGroupRef: string;
	relation:
		| "materially_independent"
		| "unknown_source_dependency";
	assessmentRevision: string;
	pairDigest: string;
}
```

Eligible subjects sharing a known upstream derivation or relay lineage appear
in the same group. Every unordered pair of distinct groups appears exactly once
in canonical group order as materially independent or unknown. Known
dependency between two subjects therefore changes group membership rather than
appearing as a pair edge. Only `materially_independent` may count as an
independent corroboration relationship. Unknown remains unknown.

The pair matrix is relative to this exact ordered subject set, assessment
revision and observation. It is not a global lineage truth and cannot be reused
after drift.

### 4.4 Coverage

```ts
interface EvidenceAssemblyQualificationCoverageV1 {
	requestedSubjects: number;
	eligibleSubjects: number;
	ineligibleSubjects: number;
	requestedSpans: number;
	qualifiedSpans: number;
	requestedRelationships: number;
	qualifiedRelationships: number;
	sourceAssertionObservation:
		| "complete_for_requested_spans"
		| "structured_only"
		| "not_available";
	lineagePairObservation: "complete";
	coverageDigest: string;
}
```

`complete_for_requested_spans` is not corpus completeness. It means every
requested qualified span was inspected under this profile. `structured_only`
means unstructured text was not interpreted into additional assertions.
`not_available` means the source material remains eligible but no assertion
projection is available. Neither state authorizes an absence claim.

## 5. Receipt, canonicalization and authenticity

```ts
interface EvidenceAssemblyRevalidationReceiptV1 {
	protocol: "evidence-assembly-exact-revalidation/receipt-v1";
	revalidationId: string;
	requestId: string;
	requestDigest: string;
	accessBindingDigest: string;
	assemblyBasisDigest: string;
	profileDigest: string;
	orderedSubjectDigests: readonly string[];
	viewSemanticDigest: string;
	observedAt: string;
	authenticity: {
		algorithm: "Ed25519";
		keyId: string;
		signedPayloadDigest: string;
		signatureBase64Url: string;
	};
}
```

All records are closed RFC 8785 JSON-domain values. Digests are lowercase
SHA-256 over exact UTF-8 JCS bytes of the complete record with only its own
digest member omitted. The receipt signed payload is the complete receipt with
`authenticity` omitted. Its `signedPayloadDigest` and Ed25519 signature cover
the same exact bytes.

`accessBindingDigest` covers all six `access` members. It contains the opaque
credential reference but never the resolved credential or secret.
`assemblyBasisDigest` covers the complete `assemblyBasis`.

Array order is significant. Canonical order is:

- subjects: request order;
- spans and relationships: byte-order by ref after duplicate rejection;
- assertions: byte-order by `assertionRef`;
- lineage groups: byte-order by group ref;
- members inside a group: request subject order; and
- lineage pairs: ascending left group then ascending right group.

## 6. Numeric and size bounds

| Item | v1 bound |
| --- | ---: |
| subjects per request | 1–32 |
| requested spans per subject | 0–32 |
| requested spans total | 256 |
| UTF-8/JCS bytes per qualified span | 8 KiB |
| qualified span content total | 256 KiB |
| requested relationships per subject | 0–32 |
| unique requested relationships total | 256 |
| assertion observations total | 256 |
| lineage groups | 0–32 eligible groups |
| lineage pair observations | exactly `n × (n - 1) / 2`, maximum 496 |
| canonical request | 256 KiB |
| canonical qualified view | 1 MiB |
| source/model/embedding calls | 0 model/embedding; bounded source observations only |
| whole operation wall time | 60 seconds |
| caller-visible cancellation settle | 250 milliseconds |

Every ref is 1–512 UTF-8 bytes without C0/C1 controls. Profile refs/versions and
signing key IDs are 1–128 ASCII identifier characters. Every SHA-256 digest is
exactly 64 lowercase hexadecimal characters. Timestamps are canonical UTC RFC
3339 with exactly three fractional digits and trailing `Z`.
Citation display title/type/version/locator members are individually at most
512 UTF-8 bytes and contain no controls. `actorSafeLocator` is display data
qualified for this Access Principal and Use Purpose, never a hidden backend ID.

At-limit succeeds. One-over fails before source I/O with
`request_not_admitted`. No truncation, pagination, multi-request continuation
or priority dropping exists in v1. Workspace must produce `limited` or
`blocked` assembly when required material exceeds the bound.

The production Adapter may batch or parallelize source observations internally,
but Adapter call shape and concurrency are not part of the Interface. It must
respect the whole-operation deadline and return exactly the same semantic view
as the in-memory Adapter for the fixture catalog.

## 7. Failure closure

```ts
type EvidenceAssemblyRevalidationFailureCodeV1 =
	| "request_not_admitted"
	| "authorization_binding_changed"
	| "qualification_incomplete"
	| "digest_or_integrity_mismatch"
	| "source_observation_drift"
	| "transport_timeout"
	| "transient_dependency_unavailable"
	| "budget_exhausted"
	| "operation_identity_conflict"
	| "recovery_provenance_untrusted";

interface EvidenceAssemblyRevalidationFailureV1 {
	code: EvidenceAssemblyRevalidationFailureCodeV1;
	retryable: boolean;
	message: string;
}
```

Only `source_observation_drift`, `transport_timeout` and
`transient_dependency_unavailable` are retryable, and only under a newly
admitted request identity. Same-ID replay returns the exact existing terminal
or observes the existing in-flight generation; it never restarts work.

Failure publishes no receipt or qualified view. Cancellation is waiter-scoped
and follows the existing I&E operation-generation fencing semantics. No failure
falls back to old qualification, admission-time access, a newer capture,
unqualified relationship metadata or raw source content.

## 8. Frozen acceptance matrix

The I&E public acceptance seam is
`IntelligenceEvidenceModule.retrieve(...)`. Production-shaped and in-memory
Adapters run the same literal fixtures.

1. One eligible exact subject returns one signed receipt and one eligible
   subject in request order with matching Resource Version, Capture, capsule,
   use-decision and requested-span evidence.
2. Thirty-two subjects, 256 spans, 256 relationships and 496 lineage pairs pass
   at limit; each one-over request fails before source I/O.
3. Output contains only requested bounded qualified spans and no unrestricted
   source body, vector, embedding, similarity, model confidence, credential or
   hidden source identifier.
4. Equal assertion digests group as exact repeated occurrences; unequal
   assertions are not semantically merged.
5. Same-lineage subjects share one lineage group; every distinct group pair is
   exactly one independent/unknown observation.
6. Unknown dependency never becomes independent corroboration.
7. One invisible, denied, expired, drifted or missing-span subject produces its
   exact ineligible member while every other subject still receives a complete
   qualification member.
8. Transport, integrity or incomplete-observation failure produces no completed
   view, even if some subjects were already observed.
9. Source withdrawal, Use Purpose/access change, receipt tampering, Resource
   Version/Capture/capsule mismatch and relationship-endpoint mismatch fail
   closed without substitution.
10. Same request ID and digest replays the same terminal; same ID with any
    changed member is an identity conflict.
11. Cancellation, last-waiter retirement and late completion preserve existing
    I&E generation fencing.
12. Request, subject, assertion, relationship, lineage, coverage, view and
    receipt digest fixture vectors recompute independently.
13. Existing exact-resource retrieval fixtures remain byte-for-byte unchanged.
14. I&E imports no Workspace/Pi/Agent/Case implementation and exposes no new
    root method or construction Port.

## 9. Design Gate

- **Verdict:** PASS
- **Owner:** Intelligence and Evidence
- **Interface:** one new closed request/outcome member behind existing
  `IntelligenceEvidenceModule.retrieve(...)`
- **Input authority:** trusted Workspace mapping from committed Task Result,
  Working Set selection and exact admission receipts
- **Output/evidence:** one signed complete qualified view or closed
  failed/cancelled outcome
- **Failure closure:** no partial view, substitution, stale fallback or raw-body
  disclosure
- **Secret isolation:** opaque credential ref participates only in access
  binding; no secret enters request evidence or outcome
- **Provider lifecycle count:** zero
- **Workspace exposure:** exact current qualification, assertion refs,
  relationship refs, lineage and coverage only
- **Backward compatibility:** existing exact-resource request/outcome remains a
  separate unchanged union member
- **Public acceptance seam:** I&E `retrieve(...)` production-shaped and
  in-memory Adapter conformance
- **Remaining blockers:** none in this contract

Implementation readiness remains **NO** because the I&E package/core is not yet
implemented, bounded search/relationship/lineage producers remain separately
gated, and the Workspace consumer contracts are not accepted. Design PASS does
not activate any deferred producer or authorize implementation.
