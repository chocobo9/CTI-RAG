# `opencti-exact-resource-retrieval/v1` Contract

Status: Accepted active I&E core contract. Core package TDD is ready under [`PROGRESS.md`](PROGRESS.md); Workspace consumption and provider disclosure remain separately gated.

## 1. Purpose and scope

This contract proves the smallest OpenCTI-first I&E vertical: retrieve one existing OpenCTI object as one immutable Resource Version and reproducible Resource Capsule without importing, enriching, searching, embedding, or assigning Case meaning.

The source fixture is one already imported MITRE ATT&CK object. The contract does not repeat the MITRE import. It introduces no OpenCTI mutation, file/PDF parser, OCR, model call, vector store, production Connector, ResourceUsePermit, Evidence Reference, or fixed model-visible tool.

## 2. Public Interface

The owning package exposes one `IntelligenceEvidenceModule` method for this slice:

```ts
interface IntelligenceEvidenceModule {
	retrieve(
		request: ExactResourceRetrievalRequestV1,
		options?: { signal?: AbortSignal },
	): Promise<ExactResourceRetrievalOutcomeV1>;
}
```

The Interface includes every invariant, budget, failure and ordering rule below. Adapter DTOs, GraphQL, credentials, storage and canonicalization remain private.

## 3. Closed request

```ts
interface ExactResourceRetrievalRequestV1 {
	protocol: "opencti-exact-resource-retrieval/v1";
	requestId: string;
	use: {
		actorRef: string;
		credentialRef: string;
		purpose: "case_investigation";
		workspaceRef: string;
		caseRef: string;
		taskRef: string;
	};
	selector: {
		instanceId: string;
		internalId: string;
		standardId?: string;
		capture: { kind: "current" } | { kind: "exact"; captureId: string };
	};
	intent:
		| { kind: "workspace_material_admission" }
		| {
				kind: "workspace_model_disclosure_revalidation";
				admissionRetrievalId: string;
				admissionKeyId: string;
				admissionReceiptSignedPayloadDigest: string;
				admissionCapsuleSemanticDigest: string;
		  };
}
```

`credentialRef` is an opaque trusted-runtime reference, never a token. `caseRef` participates in authorization/audit only and creates no Case membership or authority. `intent` is compiled by a qualified trusted Workspace recipe and cannot be supplied or changed by the model. Unknown members reject before remote I/O.

`workspace_material_admission` requires `capture.kind = "current"`. `workspace_model_disclosure_revalidation` requires `capture.kind = "exact"`, a new request identity for the provider attempt, and the exact signed admission receipt/capsule digests. It returns only that immutable capture after current actor/purpose authorization to use the historical material is re-established; it never upgrades to a newer capture. Revalidation cannot silently change Resource Version, Source Capture, capsule digest or Use Disposition revision.

The two public identity digests are independently recomputable:

```ts
interface ActorPurposeBindingDigestBasisV1 {
	protocol: "opencti-exact-resource-retrieval/actor-purpose-basis-v1";
	actorRef: string;
	credentialRef: string;
	purpose: "case_investigation";
	workspaceRef: string;
	caseRef: string;
	taskRef: string;
}
```

`requestDigest` is SHA-256 over the exact UTF-8 bytes of the JCS canonical JSON of the complete closed `ExactResourceRetrievalRequestV1`, including `requestId`. `actorPurposeBindingDigest` is SHA-256 over the exact UTF-8 JCS bytes of `ActorPurposeBindingDigestBasisV1` built field-for-field from `request.use`. Unknown members, non-JCS values, invalid Unicode or a digest mismatch reject before remote I/O. The opaque credential reference participates in equality and authority binding but neither a token nor a resolved secret enters the basis. Both Adapters and Workspace use the same fixture vectors; no Adapter-specific serialization is accepted.

Every ID/ref field is 1–512 UTF-8 bytes, contains no C0/C1 control character, and is compared byte-for-byte after JSON decoding; `keyId` is limited to 1–128 UTF-8 bytes. Every SHA-256 digest field is exactly 64 lowercase hexadecimal characters and every base64url signature/MAC is unpadded canonical base64url. Timestamp fields are canonical UTC RFC 3339 strings with seconds plus exactly three fractional digits and trailing `Z`. The complete canonical request is at most 8 KiB. Violations are `request_not_admitted` before remote I/O.

## 4. Closed outcome

```ts
type ExactResourceRetrievalOutcomeV1 =
	| { kind: "completed"; receipt: RetrievalReceiptV1; capsule: ResourceCapsuleV1 }
	| { kind: "cancelled" }
	| { kind: "failed"; failure: RetrievalFailureV1 };

interface RetrievalReceiptV1 {
	protocol: "opencti-exact-resource-retrieval/receipt-v1";
	retrievalId: string;
	requestId: string;
	requestDigest: string;
	actorPurposeBindingDigest: string;
	intentKind: "workspace_material_admission" | "workspace_model_disclosure_revalidation";
	resourceVersionRef: string;
	sourceCaptureId: string;
	catalogRevision: string;
	adapterQualificationId: string;
	orderedSegmentRefs: readonly string[];
	processingVersionVectorDigest: string;
	useDecisionRevision: string;
	useDecisionObservedAt: string;
	retentionUntil: string;
	coverage: { kind: "exact_requested_resource"; requested: 1; returned: 1 };
	resultSemanticDigest: string;
	authenticity: {
		algorithm: "Ed25519";
		keyId: string;
		signedPayloadDigest: string;
		signatureBase64Url: string;
	};
}

interface ResourceCapsuleV1 {
	protocol: "opencti-resource-capsule/v1";
	resource: {
		resourceId: string;
		version: string;
		contentDigest: string;
		openCti: { instanceId: string; internalId: string; standardId?: string; entityType: string };
	};
	sourceCapture: {
		captureId: string;
		selectedJsonDigest: string;
		observedSourceVersion?: string;
	};
	segments: readonly {
		segmentId: string;
		ordinal: number;
		text: string;
		textDigest: string;
		spans: readonly { kind: "structured_path"; path: string; valueDigest: string }[];
	}[];
	provenance: {
		originRef: string;
		acquisitionMethod: "opencti_graphql_selected_object";
		transformationManifestRefs: readonly string[];
	};
	sourceLineage: {
		assessmentRevision: string;
		dependency: "known_dependency" | "unknown_source_dependency";
		lineageRefs: readonly string[];
	};
	useDisposition: {
		decisionRevision: string;
		modelDisclosure: "allowed";
		retentionUntil: string;
	};
	status: "active";
	semanticDigest: string;
}
```

The capsule contains source-scoped material, not Evidence, a Candidate Finding, or an accepted fact. V1 has no comparison basis and therefore cannot declare lineage independence. It records only a known derivation/relay dependency or Unknown Source Dependency.

The signed receipt binds the retrieval intent and current use decision. A material-admission receipt and a later provider-disclosure-validation receipt are different evidence even when they return byte-identical capsules. Workspace retains both digests; only the latter can support that provider attempt's Disclosure Decision.

The capsule `semanticDigest` is SHA-256 over the exact UTF-8 bytes of the JCS canonical JSON of the complete capsule with only its top-level `semanticDigest` member omitted. Workspace recomputes this value from the received capsule before any use.

`resultSemanticDigest` equals that recomputed capsule `semanticDigest`. The Ed25519 signed payload is the JCS canonical JSON of the complete receipt with `authenticity` omitted. `signedPayloadDigest` is SHA-256 over those exact UTF-8 bytes; `signatureBase64Url` is Ed25519 over the same bytes. The Workspace qualifies the expected `keyId` and public-key fingerprint at activation, recomputes the capsule digest, rejects unknown/changed keys, verifies the receipt digest and signature, and then verifies equality with the signed result digest. No receipt field or capsule member can change without invalidating consumption.

Key rotation creates a new `keyId` and Adapter qualification. The qualified public key and canonicalization verifier needed for an old receipt remain available through that receipt's maximum retention horizon; rotation never makes retained audit evidence unverifiable. Private signing material is never exposed through this Interface, logs, or fixtures.

## 5. Source observation and derivation

The production-shaped Adapter is activated only for an exact instance, target fingerprint, selected GraphQL document, recursive selected-field schema digest, Adapter artifact digest, canonicalization profile and qualification ID.

For `current`:

1. Read and authorize the selected object at observation start.
2. Decode a closed selected field set and canonicalize it as JSON-domain data.
3. Read the same root/selected object again after materialization.
4. Require equal actor, authorization fingerprint, selected semantic digest and source identity across both observations.
5. Commit Source Capture, Resource Version, structured Source Spans, Retrieval Segments, Derivation Manifest and terminal receipt atomically, or publish none.

For `exact` provider-disclosure revalidation:

1. Resolve the retained admission operation by exact `admissionRetrievalId`, `admissionKeyId`, signed-payload digest and capsule digest; verify its signature, Resource Version, Source Capture and actor/purpose binding. No partial or key-substituted identity matches.
2. Load and digest-verify the named immutable Source Capture and retained decoder/canonicalization artifacts. Do not read a newer capture as a substitute.
3. Perform a bounded current OpenCTI access/marking/source-identity observation under the investigating actor, then evaluate the historical capture's current Use Disposition, license and retention through the qualified source profile.
4. Require `active` status, allowed model disclosure, unexpired retention, and exact equality with the admission capsule's Use Disposition revision and `retentionUntil`. Current OpenCTI content may have changed; that does not rewrite or upgrade the historical capture. Hidden/deleted, access/marking drift, policy revision or retention-horizon change fails closed.
5. Repeat the current access/marking/source-identity and policy fence after receipt materialization. Both observations must agree on effective access, markings, source identity, Use Disposition revision/decision and retention horizon.
6. Atomically publish only the new validation operation/receipt and the byte-identical verified capsule reference. Do not rewrite Source Capture, Resource Version, segments, manifests or the admission terminal.

The same 4-call, per-call byte/timeout, one internal transport retry and 30-second whole-operation budgets apply. A revalidation success is a distinct signed receipt whose `intentKind`, request identity and `useDecisionObservedAt` bind that provider attempt.

The Source Capture stores the exact canonical selected JSON bytes used by the derivative. It does not claim to be a complete OpenCTI object export or an OpenCTI revision. Volatile observation times do not affect semantic identity.

The v1 deterministic normalizer emits structured-path spans and bounded text segments only. Segment identity binds Source Capture, ordered spans, normalizer/chunker artifacts/configuration and text digest. Equal segment text from another resource may share blob storage but retains a distinct occurrence and lineage.

## 6. Authorization, license and retention

- Start and final fences use the investigating actor's effective OpenCTI access, not the Connector principal.
- All attached markings must be authorized. Hidden/deleted remain indistinguishable.
- Source marking does not decide copyright/license. A versioned source-profile decision must allow retention, derivation and model disclosure.
- Unknown or denied model disclosure fails before a capsule is published; v1 has no metadata-only success.
- V1 source-profile activation must prove that exact source bytes, derivatives, receipt/capsule replay material, and required decoder/canonicalization artifacts may be retained for at least 365 days, derived for this purpose, and disclosed to the qualified model path. A profile that cannot prove all three is not served by v1.
- The source profile supplies an absolute maximum retention horizon. A Working Set or audit reference cannot extend storage beyond it. Before expiry, dependent entries lose current model eligibility; content is purged on schedule while the minimum actor-safe digest receipt is retained only when policy permits.
- Retrieval diagnostics are retained 30 days. Unpublished staging is removed after 24 hours. Retention never preserves active eligibility after withdrawal or access loss.

## 7. Budgets

These values are normative for v1:

| Budget | Limit |
| --- | ---: |
| Resources per request | 1 |
| OpenCTI calls per attempt | 4 |
| OpenCTI response bytes per call | 1 MiB |
| Canonical selected Source Capture | 256 KiB |
| Retrieval Segments | 128 |
| UTF-8 bytes per segment | 8 KiB |
| Total capsule segment text | 64 KiB |
| Per-call timeout | 10 seconds |
| Whole retrieval wall time | 30 seconds |
| Transport retries | 1, within the same whole-operation budget |
| Caller-visible cancel settle | 250 milliseconds |
| Model/embedding calls | 0 |

A budget violation publishes no receipt/capsule and returns a specific actor-safe failure. No silent truncation is allowed.

## 8. Failures

```ts
type RetrievalFailureCodeV1 =
	| "request_not_admitted"
	| "not_found_or_not_visible"
	| "authorization_or_marking_changed"
	| "use_not_permitted"
	| "source_observation_drift"
	| "schema_or_mapping_mismatch"
	| "digest_or_integrity_mismatch"
	| "derivation_incomplete"
	| "qualification_changed"
	| "transport_timeout"
	| "transient_dependency_unavailable"
	| "budget_exhausted"
	| "operation_identity_conflict"
	| "recovery_provenance_untrusted";

interface RetrievalFailureV1 {
	code: RetrievalFailureCodeV1;
	retryable: boolean;
	message: string;
}
```

`retryable` is a deterministic protocol value, not an Adapter opinion:

| Failure code | `retryable` | Meaning |
| --- | --- | --- |
| `source_observation_drift` | `true` | trusted code may issue a new request ID after a fresh source observation basis |
| `transport_timeout` | `true` | trusted code may issue a new request ID after this request's one internal transport retry is exhausted |
| `derivation_incomplete` | `true` | trusted code may issue a new request ID only after the incomplete producer/store condition is repaired |
| `transient_dependency_unavailable` | `true` | trusted code may issue a new request ID after a store, signer, clock or policy service is restored without qualification drift |
| every other v1 code | `false` | a blind caller retry cannot change the authoritative or qualification failure |

`true` never reruns or resumes the same request identity. I&E may perform at most the one transport retry in section 7 inside one attempt and wall-time budget; it publishes no intermediate outcome. Any caller retry is an explicit newly admitted operation with a new `requestId`. Same-ID replay only reads the existing operation state and follows section 9.

Messages contain no token, hidden identifier, protected body, marking topology, source count, GraphQL error body or credential detail.

## 9. Retry, crash and concurrency

- Same `requestId` plus canonical request digest reuses the same computation/terminal receipt or resumes its in-flight operation; it never reruns the source read merely to replay. Before any successful terminal replay returns a capsule, I&E revalidates current actor/purpose access, active status, Use Disposition revision and decision, and the exact signed `retentionUntil`. Replay is allowed only when all values exactly equal the committed receipt/capsule and remain currently eligible. Any revision/horizon/status/access change, even if a new policy decision would still be `allowed`, returns only an actor-safe denial and no retained receipt, capsule, identifier, count or body; the original terminal is not rewritten. A caller that needs the new allowed basis must obtain a new material-admission request identity. Same ID with another digest is `operation_identity_conflict`.
- A retry is a new attempt; no observations or segments are spliced across attempts.
- Cancellation settles locally within 250 ms. An Adapter that ignores abort may finish, but its late result cannot publish.
- Crash before the atomic publication leaves no retrievable capture/derivative/receipt. Crash after commit/before reply recovers the original terminal receipt.
- Publication uses a current operation generation/fencing token. First terminal wins; late/older workers are diagnostics only.
- Concurrent identical input/method derivations converge on one immutable identity. Same source identity/version with a different digest is an integrity failure, never last-write-wins.
- Authorization/qualification drift wins over a racing success. Failure of one resource/actor partition does not block another.
- A disclosure revalidation uses a new stable request ID bound to its provider attempt and prior admission digests. It never reuses the material-admission request ID, and replay of either operation cannot stand in for the other intent.

No OpenCTI business effect is dispatched, so v1 does not require the frozen Durable Operation Journal.

### 9.1 Private operation and trust Ports

The Implementation hides these private Port semantics behind the public Module Interface:

| Port operation | Required behavior |
| --- | --- |
| claim request identity | atomically create or recover one `(requestId, requestDigest)` operation; another digest conflicts |
| read terminal | return the one committed terminal identity without repeating OpenCTI observation; disclosure still revalidates current use |
| publish retrieval | atomically commit Source Capture, Resource Version, Derivation Manifest, segments, signed receipt and capsule, or publish none |
| claim generation/fence | only the current worker generation may publish; late generations are diagnostics |
| exact-capture lookup | return the named immutable capture and retained decoder/canonicalization artifacts, never a newer substitute |
| purge | remove staged data after 24 hours and policy-expired content without extending eligibility through references |

Activation also qualifies an injectable trusted clock, Ed25519 signer/key catalog, JCS/SHA-256 implementation, source profile, Adapter target/schema and retention scheduler. Tests use deterministic clock and signing fixtures. Clock rollback, unknown signing key, expired verification material or qualification drift fails closed.

One operation identity follows this closed store state machine:

| State | Transition and visibility |
| --- | --- |
| `in_flight(generation, leaseId, ownerEpoch, leaseExpiresAt)` | one current leased/fenced worker may publish; duplicate callers attach as independent waiters while the lease is current |
| `completed` | immutable successful receipt/capsule terminal; same-ID replay may disclose only after the current replay fence above |
| `failed` | immutable actor-safe failure terminal; same ID returns the same failure and never starts a worker |
| `abandoned(generation)` | no terminal outcome was published after the last waiter detached; the generation is permanently fenced, and a later same-ID/same-digest caller may atomically claim a strictly newer generation |

Cancellation is waiter-scoped. It detaches and settles that caller as `cancelled` within 250 ms without cancelling other waiters. When the last waiter detaches, the store atomically fences the current generation and marks it `abandoned` before best-effort Adapter abort; a late result from that generation cannot publish. A retryable attempt failure CASes the current generation to `failed`; an older or concurrent worker cannot overwrite it. Retrying a published failure requires a new request ID. `cancelled` is never a durable operation terminal, and a later generation can start only from `abandoned`, never from `completed` or `failed`.

Every worker lease is store-issued and binds operation identity, strictly increasing generation, random `leaseId`, process-start `ownerEpoch`, and `leaseExpiresAt` from the qualified store/monotonic clock. Renewal is a CAS by the same tuple and never extends beyond the whole-operation deadline. A process restart always obtains a new owner epoch. A caller that finds `in_flight` with an expired lease does not attach: it atomically CASes that exact old tuple to `abandoned`, which permanently fences the old generation, then separately claims the next generation as `in_flight` with a new lease. If either CAS loses, it rereads the winner; it never guesses ownership. A worker must verify its current lease/generation in the same transaction that publishes a terminal, so expiration or takeover before publication wins even if the old process later resumes.

Only the qualified store clock decides expiry. Clock rollback or inability to prove monotonicity makes that operation partition unavailable and permits no takeover or publication until requalification; local process wall clocks never reclaim work. Production-shaped and in-memory fixtures cover crash without waiter detach, expiry-before/after-renewal, restart owner epoch, two reclaimers, slow old worker after takeover, acknowledgement loss and disjoint-partition progress.

## 10. Observability

For every attempt record actor-safe request/operation IDs, terminal code, qualification ID, duration, OpenCTI call/byte counts, retry count, cache outcome, selected payload bytes, segment count and result digest. Protected content and credentials are excluded from ordinary logs.

## 11. Acceptance catalog

### Authority and disclosure

- **IER1-AU-01:** the capsule is labeled source material and cannot encode Evidence role, Case acceptance, support or contradiction.
- **IER1-AU-02:** Case membership is only a retrieval seed; retrieval creates no OpenCTI/Case mutation.
- **IER1-AU-03:** a model-supplied actor, credential, Connector, GraphQL, parser or policy field is rejected.
- **IER1-AU-04:** marking/license denial publishes no body, segment, score, count or protected identifier.
- **IER1-AU-05:** v1 exposes only known dependency or Unknown Source Dependency; neither can be interpreted as independent corroboration.
- **IER1-AU-06:** model output and Query Candidates cannot supply `intent`, selector, prior admission digests, actor, credential or request identity; only the trusted qualified recipe may compile them.

### Capture and derivation

- **IER1-CD-01:** equal selected content under the same source/qualification produces the same Resource and capsule semantic digests despite observation time.
- **IER1-CD-02:** changed content or access between observations publishes nothing.
- **IER1-CD-03:** invalid JSON-domain input, unknown member, lone surrogate, non-finite number or schema mismatch fails before publication.
- **IER1-CD-04:** Source Capture bytes, manifest digest, structured spans, segments and capsule can be recomputed byte-for-byte with retained artifacts.
- **IER1-CD-05:** segment identity changes when any capture, span, normalizer, chunker/config or text digest changes.
- **IER1-CD-06:** equal text from two sources preserves both occurrences and Source Lineages.

### Exact retrieval

- **IER1-RT-01:** current returns one complete receipt/capsule or a terminal failure; no partial success exists.
- **IER1-RT-02:** exact capture returns only the named capture after current use authorization; it never upgrades to current.
- **IER1-RT-03:** an unknown/hidden/deleted target returns the same non-distinguishing failure.
- **IER1-RT-04:** every output binds exact Resource Version, Source Capture, processing vector, ordered segments, qualification and actor/purpose digest.
- **IER1-RT-05:** any budget overflow fails explicitly and never truncates a successful capsule.
- **IER1-RT-06:** Workspace recomputes the capsule JCS/SHA-256 digest; an unknown/changed Ed25519 key, non-canonical signed payload, digest/signature failure, capsule-digest mismatch, or tampered member/segment order is detected by the consumer.
- **IER1-RT-07:** key rotation selects a new qualification while old retained receipts remain verifiable through their policy horizon without authorizing new use under the old key.
- **IER1-RT-08:** material admission uses `current`; provider disclosure validation uses `exact`, a distinct provider-attempt-bound request identity and the exact prior admission receipt/capsule digests. Their signed receipts cannot substitute for one another.
- **IER1-RT-09:** published fixture vectors independently recompute `requestDigest` from the complete closed request and `actorPurposeBindingDigest` from the closed actor-purpose basis; field omission, addition, reordering, encoding drift or Adapter-specific serialization cannot verify.
- **IER1-RT-10:** disclosure revalidation verifies admission retrieval ID, signing key ID, signed-payload digest, capsule digest, Resource Version and Source Capture as one identity; key rotation or partial identity equality cannot substitute another admission.

### Failure and concurrency

- **IER1-FC-01:** timeout and cancellation expose no staged or late result; ignored abort is fenced.
- **IER1-FC-02:** same-ID/same-digest replay reuses the original terminal only after current disclosure revalidation; revocation/expiry returns actor-safe denial with no capsule, while same-ID/different-digest conflicts.
- **IER1-FC-07:** authorization, marking, Use Disposition or retention loss after a successful retrieval prevents every later replay from disclosing the retained capsule or protected receipt fields.
- **IER1-FC-03:** every before/after-commit crash window produces either no visible output or exactly the original committed receipt.
- **IER1-FC-04:** two workers finishing in reverse order publish only the current generation; newer failure cannot be backfilled by older success.
- **IER1-FC-05:** authorization/qualification change racing success prevents publication.
- **IER1-FC-06:** disjoint actor/resource operations continue when one partition fails.
- **IER1-FC-08:** clock rollback, unavailable/expired verification material and signer or retention-scheduler qualification drift fail closed without publishing a terminal success.
- **IER1-FC-09:** the `retryable` table is exact across both Adapters; an internal transport retry remains inside one attempt, same-ID replay performs no new source read, and any permitted caller retry uses a new request identity.
- **IER1-FC-10:** same-ID successful replay discloses only when access, active status, Use Disposition revision/decision and `retentionUntil` exactly match the committed terminal. Any change returns actor-safe denial without rewriting the terminal; a new allowed basis requires a new admission request.
- **IER1-FC-11:** duplicate waiters share one generation; cancelling one does not cancel another. Last-waiter cancellation fences then abandons the generation before best-effort abort, and a late worker cannot publish. Only `abandoned` may start a newer same-ID generation; completed/failed identities never rerun.
- **IER1-FC-12:** a crashed worker's expired store lease is atomically fenced and abandoned before one newer generation is claimed. Two reclaimers yield one winner, an old resumed worker cannot publish, owner-epoch/clock rollback fails closed, and disjoint partitions continue.

### Adapter and performance

Every conformance fixture is one closed `IER1FixtureV1` document containing: fixture/protocol ID; canonical request; initial operation-store state; ordered OpenCTI observation results or transport faults; source-profile/use decisions; deterministic clock ticks; signer/key qualification; injected publication/acknowledgement fault; caller attach/cancel schedule; and one exact expected public outcome, durable operation state, committed artifact digests, call/byte counts and actor-safe metrics. Unknown fixture members reject. The same fixture bytes run unchanged through the production-shaped and in-memory compositions.

- **IER1-AD-01:** production-shaped and in-memory Adapters produce identical outcome, failure, retryability, digests and disclosure for the same fixture catalog.
- **IER1-AD-02:** deployed schema/target/Adapter/qualification drift disables activation until requalification.
- **IER1-PF-01:** fixtures enforce every numeric call, byte, segment, timeout, retry and settle budget.
- **IER1-PF-02:** metrics reconcile with the receipt while revealing no protected content.
- **IER1-RP-01:** activation fails unless the source profile permits at least 365 days of exact replay; retained artifacts reproduce exact capsule bytes during that qualified horizon and digest-only evidence is never described as replay.
- **IER1-RP-02:** diagnostic expiry after 30 days does not remove the durable receipt or final ordered results.
- **IER1-RP-03:** a source-policy maximum cannot be extended by a reference; dependent model eligibility ends before content purge and the post-expiry receipt makes no replay claim.

## 12. Exit criteria

The I&E core is delivered when every IER1 case passes through the public I&E Interface for both Adapters and I&E `PROGRESS.md` records independent core acceptance. This does not deliver the integrated vertical. Workspace consumption requires its own PNW/TQ gate and IWS1 public-seam acceptance; real-provider disclosure additionally requires the Pi provider-dispatch proof. A live OpenCTI diagnostic may supplement but never replace core fixtures.
