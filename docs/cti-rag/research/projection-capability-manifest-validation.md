# Projection and Capability Manifest Validation Patterns

Status: research note for `opencti-case-projection/v1`, `case-capability-risk-registry/v1`, and the Agent Investigation Workspace operation-dependency contract.

Design disposition (2026-07-20): closed schema, semantic lint, qualification, and production/in-memory conformance patterns apply to the current Orientation contract. Full Projection and write-capability manifest recommendations remain frozen strict-R1 target input.

## Conclusion

The two manifests should be treated as **versioned executable contracts**, not documentation and not model-visible configuration. A safe implementation needs four independent validation layers:

1. a closed structural schema that rejects unknown or malformed fields;
2. a semantic linter that checks cross-references and CTI-specific safety invariants that a general schema language cannot prove;
3. runtime admission that binds current authority and versions, validates the selected manifest digest, and fails closed before any operation or effect; and
4. one shared Adapter conformance suite run against both the production Adapter and its in-memory test Adapter.

The manifests should declare stable operation/capability identity, exact input and output slots, output-specific dependency edges, possible remote effect domains, risk and approval policy, schema and policy versions, idempotency/reconciliation support, and required proof in returned receipts. Model-generated values must remain limited to the business payload permitted by a capability's input schema. Case Revision, authorization/policy revision, dependency keys, effect domains, idempotency identity, and request digests are trusted runtime bindings.

JSON Schema or OpenAPI can supply the structural vocabulary and machine-readable schemas, but choosing either does not eliminate the semantic linter or runtime admission. This report therefore recommends invariants, not a specific schema implementation.

## Evidence boundary

Sections labeled **Source facts** summarize official specifications, official project documentation, or first-party engineering material. Sections labeled **CTI-RAG inference** are project recommendations derived from those sources. The sources do not prescribe CTI-RAG's manifest shape, risk tiers, dependency graph, or Case semantics.

## Primary-source findings

### 1. A schema must identify its dialect and its own stable identity

**Source facts**

- JSON Schema Draft 2020-12 uses `$schema` both as a dialect identifier and as the identifier of the meta-schema against which a schema must be valid. Omitting `$schema` from a document root leaves behavior implementation-defined. Its `$id` keyword assigns a canonical URI to a schema resource; that URI is an identifier and need not be a network location. Required vocabularies can force an implementation that does not understand them to refuse processing. [JSON Schema Core, sections 8.1.1, 8.1.2, and 8.2.1](https://json-schema.org/draft/2020-12/json-schema-core)
- OpenAPI separates the OpenAPI Specification version from the version of the description and from the described API's version. It also allows a document to declare the JSON Schema dialect used by its Schema Objects. [OpenAPI 3.2.0, sections 2.1 and 4.1.1](https://spec.openapis.org/oas/v3.2.0.html)
- OpenAPI requires an `operationId`, when present, to be unique across all operations in the description. [OpenAPI 3.2.0, Operation Object](https://spec.openapis.org/oas/v3.2.0.html#operation-object)

**CTI-RAG inference**

Each manifest must keep the following version dimensions separate:

| Dimension | Example | Meaning |
|---|---|---|
| Manifest family and semantic major | `opencti-case-projection/v1` | Stable contract identity and compatibility boundary |
| Manifest schema dialect | a pinned JSON Schema/OpenAPI dialect identifier | How the manifest and its referenced payload schemas are interpreted |
| Manifest revision | immutable content digest or release revision | Which exact manifest content was admitted |
| Projection/profile schema version | projection result schema identifier | Which Case Projection representation an Adapter returns |
| Capability input/output schema version | immutable schema identifiers | Which payload and receipt shapes apply |
| Policy revision | current Case Management authorization/risk policy revision | Which runtime policy decision was used |
| Adapter conformance version | conformance suite/profile revision | Which behavioral obligations the Adapter passed |

Changing a policy revision must not masquerade as a schema change. Correcting documentation must not silently alter a capability's effect domain. A schema dialect upgrade must not implicitly upgrade stored manifests or runtime payloads.

### 2. Closed structural validation and semantic lint solve different problems

**Source facts**

- JSON Schema assertions can reject only constraints that the schema actually states. Draft 2020-12 provides `required`, `dependentRequired`, conditional applicators, and `unevaluatedProperties`; it also treats unknown schema keywords as annotations unless a required vocabulary says otherwise. The standard `format` behavior is annotation-oriented by default, and full format assertion support is optional unless explicitly required by the dialect. [JSON Schema Core, sections 6.5, 7.6, 8.1.2, and 11.3](https://json-schema.org/draft/2020-12/json-schema-core), [JSON Schema Validation, sections 6.5 and 7.2](https://json-schema.org/draft/2020-12/json-schema-validation)
- The OpenAPI Initiative publishes schemas for OpenAPI descriptions but explicitly warns that those schemas cannot catch every specification violation; normative specification text remains authoritative. [OpenAPI published schemas](https://spec.openapis.org/oas/)
- Cedar validates policies against an application schema containing known actions and the principal, resource, and context types applicable to each action. Cedar's documentation still treats request validation and policy validation as separate activities and notes that schema validation cannot prove that referenced entities actually exist. [Cedar policy validation](https://docs.cedarpolicy.com/policies/validation.html), [Cedar schema](https://docs.cedarpolicy.com/schema/schema.html)

**CTI-RAG inference**

A manifest validator must have two build-time stages:

1. **Structural validation** checks types, required fields, enum values, array uniqueness, closed object shapes, and referenced payload schemas.
2. **Semantic lint** resolves all IDs and slots and checks rules whose meaning spans several fields or external registries.

Structural validity must never be reported as “safe capability” or “conformant projection.” The semantic linter is mandatory because a general schema cannot prove, for example, that every output's dependency slot exists, that an R1 capability's effect domains are additive and reversible, or that a production Adapter really implements idempotent lookup.

The root manifest schema and every security-relevant nested object should reject unevaluated properties. If the chosen validator does not implement the required dialect or format assertions, manifest installation fails. A free-form `extensions` object may be allowed only for namespaced, non-enforcement annotations; runtime policy and dependency calculations must ignore it.

### 3. Unknown fields should be rejected, not silently preserved or pruned

**Source facts**

- Kubernetes CRDs require structural schemas in the `apiextensions.k8s.io/v1` API. Kubernetes normally prunes fields not recognized by a CRD's schema before persistence; opting out allows arbitrary data. [Kubernetes CRD structural schemas and field pruning](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/#field-pruning)
- OAuth Rich Authorization Requests require a `type` that determines the allowed contents of an authorization object. An authorization server must reject an unknown type, an unknown field for a known type, a wrong type or value, or a missing required field. The RFC also notes that machine-readable type schemas can support validation. [RFC 9396, sections 2.1, 5, and 11.3](https://www.rfc-editor.org/rfc/rfc9396.html)
- RFC 8259 recommends unique object member names because duplicate names produce unpredictable behavior across implementations. [RFC 8259, section 4](https://www.rfc-editor.org/rfc/rfc8259.html#section-4)

**CTI-RAG inference**

Kubernetes pruning is useful for ordinary extensible resources but unsafe for CTI-RAG enforcement manifests. A misspelled `mayEffectDomains` or `freshCaseRevisionRequired` field must not disappear while leaving a weaker capability installed.

Manifest parsing must therefore:

- reject duplicate object member names before ordinary JSON decoding can collapse them;
- reject unknown fields rather than prune them;
- reject unknown manifest families, versions, capability IDs, dependency-key kinds, effect-domain kinds, risk tiers, approval modes, and publication classes;
- reject unknown schema dialects or required vocabularies;
- reject unresolved local or external schema references;
- reject a manifest whose declared ID does not match its installation location/registry key; and
- reject any runtime request that contains fields outside the capability's admitted business-payload schema.

Schema-reference closure must be resolved from an allowlisted, immutable registry during build or installation, then stored with verified digests. Runtime payload validation must not fetch a `$ref` from the network, and a mutable discovery URL must not select different schema bytes for an already admitted manifest revision.

Forward compatibility is achieved by explicitly serving multiple manifest versions, not by silently accepting unknown enforcement fields.

### 4. Defaults are useful for ordinary data but dangerous for risk and effect policy

**Source facts**

- Kubernetes structural schemas can specify default values. Defaulting and pruning participate in the API processing pipeline. [Kubernetes CRD defaulting](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/#defaulting)
- Kubernetes admission webhooks declare whether they have side effects and whether they suppress them for dry-run requests. Webhooks that cause out-of-band effects need a reconciliation mechanism because successful admission does not prove the admitted object was ultimately persisted. [Kubernetes dynamic admission control, Side effects](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#side-effects)
- Mutating admission webhooks must be idempotent because they may be invoked again and may see changes they previously made. [Kubernetes dynamic admission control, Reinvocation policy](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#reinvocation-policy)

**CTI-RAG inference**

The following manifest fields must be explicit and must have no default:

- risk tier;
- approval policy;
- reversibility;
- output authority/publication class;
- whether fresh Case Revision is required;
- input dependency usage;
- possible remote effect domains;
- execution concurrency/serialization class for effects;
- idempotency support and retention guarantee;
- status/reconciliation operation and proof schema;
- timeout/unknown-outcome behavior; and
- authorization dimensions and trusted-bound fields.

Defaults may be used for non-security metadata such as display text or observability labels, but they must be applied deterministically before canonical digest calculation and must produce the same admitted form in all validators. Prefer omitting such defaults from the first release rather than maintaining two digest representations.

An effectful capability cannot declare `sideEffects: none`. A dry-run declaration must say whether it performs only validation or can still create external work. If the owning system cannot suppress effects during dry-run, the capability must not advertise dry-run support.

### 5. Admission failure and an explicit denial are different outcomes

**Source facts**

- Kubernetes admission has an explicit `failurePolicy`: network, timeout, malformed-response, and similar call failures either fail closed or are ignored. The default is `Fail`. An explicit webhook rejection is a denial, not a webhook failure, and always denies the request. [Kubernetes dynamic admission control, Failure policy](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#failure-policy)
- Admission webhook versions are negotiated from a declared supported-version list. Kubernetes rejects creation or update of a webhook configuration when none of its declared `admissionReviewVersions` are supported by the API server. For a configuration that was accepted, invocation/call failures are handled by its failure policy. [Kubernetes dynamic admission control, AdmissionReview request and response](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#request)
- Cedar represents an authorization request as principal, action, resource, and context. It returns deny if no permit policy applies, and a matching forbid overrides permits. Policy evaluation errors are reported separately in diagnostics. [Cedar authorization](https://docs.cedarpolicy.com/auth/authorization.html)

**CTI-RAG inference**

Manifest/runtime outcomes must preserve at least these distinctions:

| Outcome | Meaning | Required behavior |
|---|---|---|
| `invalid_manifest` | Registry entry failed structural or semantic validation | Do not install or expose the capability/profile |
| `unsupported_contract_version` | Caller, Adapter, or runtime has no mutually supported version | Fail closed before remote work |
| `unauthorized` | Authoritative policy explicitly denied the bound actor/action/resource/context | Do not retry as a transport failure |
| `rejected` | Owning domain accepted request processing and rejected its business semantics | Return structured issues; no failure-policy bypass |
| `admission_unavailable` | Required authorization/policy/admission decision could not be obtained | Fail closed for current work; no effect dispatch |
| `transport_failure` | A no-effect operation failed before a valid result | Safe retry only under the operation contract |
| `indeterminate_effect` | An effectful request may have committed but lacks authoritative proof | Reconcile under the original identity; suspend matching effect domains |

Every runtime authorization decision must bind the current principal/actor, capability action, Case/resource, request context, and authorization/policy revision. A manifest that was valid at build time cannot authorize an operation at runtime.

### 6. Idempotency identity requires stable request semantics and a scope

**Source facts**

- HTTP defines idempotency by intended server effect, not by a request merely being repeated. A client should not automatically retry a non-idempotent request unless it knows the semantics are idempotent or can prove the original was not applied. [RFC 9110, section 9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)
- Amazon EC2 accepts client tokens for idempotent operations. Reuse of a token with different parameters fails with `IdempotentParameterMismatch`; the token's scope can be regional or zonal depending on the operation. [Amazon EC2 API idempotency](https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html)
- JSON Canonicalization Scheme produces deterministic, hashable JSON by constraining input to I-JSON, using deterministic primitive serialization, recursively sorting object members, and preserving array order. It requires Unicode-valid strings, rejects lone surrogate code points, and relies on IEEE 754 binary64/ECMAScript number serialization; applications needing values outside that number domain need another representation, commonly strings. [RFC 8785, sections 3.1, 3.2.2.2, and 3.2.2.3](https://www.rfc-editor.org/rfc/rfc8785.html)

**CTI-RAG inference**

Every effectful capability manifest must declare:

- the idempotency namespace and scope dimensions;
- which trusted runtime creates the operation/effect identity;
- the allowlisted `digestProfileId`; request-digest coverage is fixed by that trusted profile rather than an ad hoc capability field;
- whether the owner atomically establishes the identity, request digest, one logical effect, and a durable initial status, and how a later terminal receipt becomes stable;
- how status is queried by the same identity;
- retention duration for dedupe/status proof;
- response behavior for same identity/same digest and same identity/different digest; and
- which remote effect domains remain reserved while the outcome is unknown.

The request-digest projection is runtime-defined, not capability-selected. It must include capability ID/version and manifest digest, the complete admitted business payload, trusted actor/tenant/purpose/Case/policy/revision bindings, approval identity, bound effect domains, idempotency namespace/scope/identity, and every field that can alter authorization, target, effect, or receipt meaning. It may exclude only enumerated transport metadata that cannot alter semantics. The manifest digest similarly covers the admitted manifest after deterministic normalization, excluding only its self-referential digest/signature container.

Canonicalization and digest algorithm combinations come from a trusted runtime allowlist identified by a fixed `digestProfileId`; a manifest cannot introduce an algorithm used to verify itself. The first implementation may allow only RFC 8785 plus one fixed cryptographic hash. Before canonicalization, validators reject duplicate names, lone Unicode surrogates, non-finite numbers, and numeric values not safely representable under the chosen JCS/I-JSON profile. Exact or large integers use a schema-constrained canonical string representation. Cross-language conformance vectors cover these rejection boundaries as well as successful digests.

Idempotency scope must be explicit. A token unique only inside one Case Management tenant must not be looked up as though it were globally unique. Reusing an identity with a different digest is an integrity failure, not a new attempt.

The existing detailed effect research remains applicable: [Operation Effects, Idempotency, and Authoritative Reconciliation](./operation-effects-idempotency-reconciliation.md).

### 7. Version evolution needs coexistence, conversion, and retirement evidence

**Source facts**

- Kubernetes CRDs can serve several versions while storing one designated version. Every multi-version CRD selects a conversion strategy. The `None` strategy changes only `apiVersion` and otherwise leaves fields unchanged; a webhook strategy is used when representation changes need custom conversion logic. Stored objects are not automatically rewritten merely because the preferred storage version changes. Kubernetes records prior storage versions until migration completes. [Kubernetes CRD versioning](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definition-versioning/)
- Kubernetes' API deprecation policy requires a version increment to remove an API element or significantly change its behavior, requires lossless round trips among supported versions in a release, and overlaps old and new versions before advancing the preferred/storage version. [Kubernetes deprecation policy](https://kubernetes.io/docs/reference/using-api/deprecation-policy/)
- Kubernetes warns that conversion failures can disrupt reads and writes and should not be used to enforce validation constraints; validation belongs in schemas or admission. [Kubernetes CRD conversion](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definition-versioning/#webhook-conversion)

**CTI-RAG inference**

Compatibility rules for the manifest families should be:

1. Within `/v1`, a change is compatible only if every previously valid manifest/request/receipt keeps the same safety meaning and every existing Adapter remains conformant.
2. Adding an optional descriptive field is compatible only when its absence has no security or effect meaning.
3. Adding a new capability is compatible because capability IDs are closed and independently admitted; widening an existing capability's inputs, outputs, authority, risk, or effects is not.
4. Adding an optional output is incompatible if a caller could mistake its absence for a complete result, or if it alters dependency/challenge behavior.
5. Adding, removing, or broadening an effect domain is incompatible and requires a new capability or manifest major.
6. Changing trusted-bound fields, authorization dimensions, approval, reversibility, idempotency, reconciliation, or receipt proof is incompatible.
7. Renaming a dependency key, output slot, semantic role, or enum value is incompatible unless an explicit lossless conversion preserves both identity and behavior.
8. Conversion must be deterministic, side-effect free, and authorization neutral. It cannot “repair” an unsafe manifest into admission.
9. Old and new readers/Adapters must overlap during rollout. A manifest version cannot be retired until persisted journal entries, receipts, Workspace Artifacts, and Adapters no longer require it or a tested lossless conversion exists.
10. Installed manifest revisions are immutable. A corrected revision gets a new digest; historical operation receipts continue to resolve the original admitted revision.

Kubernetes validation ratcheting allows unchanged legacy invalid fields during some CRD updates. CTI-RAG should not ratchet safety-critical manifest violations: an older manifest may remain readable for audit or conversion, but it cannot authorize a new operation once it fails the currently required admission contract. [Kubernetes CRD validation ratcheting](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/#validation-ratcheting)

## Recommended common manifest envelope

This is a CTI-RAG recommendation, not an external standard and not a commitment to JSON Schema or OpenAPI syntax.

```typescript
interface ManifestEnvelope<Body> {
	manifestFamily: "opencti-case-projection" | "case-capability-risk-registry";
	manifestApiVersion: "v1";
	manifestId: string;
	manifestRevision: string;
	schemaDialect: string;
	manifestSchemaId: string;
	digestProfileId: string;
	manifestDigest: string;
	body: Body;
}

interface ManifestLifecycleRecord {
	manifestFamily: ManifestEnvelope<unknown>["manifestFamily"];
	manifestId: string;
	manifestRevision: string;
	manifestDigest: string;
	registryRevision: string;
	served: boolean;
	deprecated: boolean;
	replacedBy?: {
		manifestId: string;
		manifestRevision: string;
	};
}
```

Non-type invariants:

- `manifestFamily`, `manifestApiVersion`, and `manifestId` are stable ASCII identifiers and case-sensitive.
- `manifestRevision` is immutable. Updating any enforcement-relevant field creates a new revision/digest.
- `digestProfileId` must resolve in the runtime's closed allowlist before the manifest digest is verified; the resolved profile pins canonicalization, digest algorithm, rejection rules, and digest projection.
- `manifestDigest` is verified after parsing, duplicate-name rejection, structural validation, and deterministic canonicalization. It excludes only the digest/signature container itself.
- `manifestSchemaId` and every referenced payload schema use immutable identifiers. A mutable “latest” URL may be used for discovery but never in a receipt or digest.
- mutable lifecycle state is not part of the immutable manifest body. An authoritative, revisioned registry record binds lifecycle state to the exact family, ID, revision, and digest.
- `served:false` in the current lifecycle record prevents new runtime use but does not make old receipts undecodable.
- `deprecated:true` emits build/runtime diagnostics and usage metrics; it does not silently select `replacedBy`.
- the runtime pins a manifest digest for each admitted operation and records it in the operation receipt.
- runtime admission also reads the current lifecycle record. A cached manifest body cannot bypass later revocation of `served` status.

The **manifest lifecycle fence** solves the race between admission and later unserving. Its inputs are the operation's pinned `registryRevision` and the current lifecycle record; its output is permission to continue, stale-discard before an effect, or post-dispatch reconciliation. Its boundary is distribution control: `served:false` prevents new admissions and new remote effect dispatches but cannot undo an effect already sent. A no-effect result rechecks lifecycle at its end fence. An effectful operation rechecks immediately before dispatch; if lifecycle changes after dispatch, it keeps the original manifest/identity for authoritative status lookup and reconciliation, reserves the declared effect domains, and admits no new effect dispatch. Unavailable lifecycle state fails closed at admission/end fence and becomes reconciliation—not cancellation—after possible dispatch.

## Stable dependency and effect keys

Dependency and effect keys should be typed canonical tuples, not caller-built strings and not prefix-matched paths:

```typescript
type CanonicalScalarType = "ascii_id" | "opaque_id" | "revision" | "digest";

interface CanonicalKeyParameter {
	name: string;
	scalarType: CanonicalScalarType;
	binderId: string;
	encoding: "utf8_length_prefixed";
	normalization: "none";
}

interface CanonicalKeyTemplate {
	owner: "workspace" | "case" | "intelligence-evidence" | "authorization";
	kind: string;
	keyVersion: 1;
	parameters: readonly CanonicalKeyParameter[];
}

interface BoundCanonicalKey {
	owner: CanonicalKeyTemplate["owner"];
	kind: string;
	keyVersion: 1;
	parts: readonly {
		name: string;
		scalarType: CanonicalScalarType;
		canonicalValue: string;
	}[];
}
```

Required behavior:

- `owner` and `kind` come from a closed registry; `kind` is lower-case ASCII with one canonical spelling.
- parameter name, arity, order, scalar type, binder, byte encoding, and normalization are part of `keyVersion`.
- semantic lint resolves every `binderId`, proves that its output scalar type matches the parameter, and rejects missing, extra, reordered, or duplicate parameter names.
- runtime parts are filled positionally only by trusted binders from authoritative IDs; the model cannot submit bound keys.
- equality is over the registry-defined encoded tuple bytes, including owner/kind/version and length-framed parts; Unicode display similarity is irrelevant.
- effect-domain overlap is declared by the key registry over typed tuples, not inferred from string prefixes.
- changing part order, normalization, overlap, or owner semantics requires a new `keyVersion`.
- aliases can aid migration/discovery but never participate in equality, digest, dependency lookup, or idempotency scope.

First-release key kinds required by the vertical slice are authorization scope, Case head, active projection/profile, projected block digest, task/Lens, Session head/compaction generation, Working Set aggregate and entry, Intelligence Resource version and access status, capability policy, and the Case-head plus capability-specific effect domains.

## Closed semantic-lint model

**Problem:** prose fields such as “security-critical input,” “depends on the Case,” or “R1-safe output” cannot be checked consistently. **Inputs:** a structurally valid manifest plus closed, versioned registries of schemas, binders, canonical keys, risk combinations, publication classes, and receipt states. **Output:** either one normalized admitted contract and its digest, or a deterministic set of rule IDs and failures. **Boundary:** this stage proves declaration consistency only; it does not prove current authorization, target behavior, or Adapter conformance. **Failure behavior:** any unknown class, unresolved reference, incomplete dependency, or unavailable rule-registry version rejects installation.

The schema representation may differ, but it must express at least these closed concepts:

```typescript
type InputSecurityClass = "business_payload" | "trusted_binding" | "verified_remote_output";
type PublicationClass =
	| "projection_authoritative"
	| "workspace_derived"
	| "case_proposal"
	| "case_receipt"
	| "external_publication";
type OperationClass =
	| "read"
	| "workspace_local"
	| "case_additive"
	| "case_authority_change"
	| "identity_merge"
	| "scope_or_lifecycle_change"
	| "external_publish";
type DependencyOrigin =
	| { kind: "input_slot"; slot: string }
	| { kind: "result_version"; originId: string };

interface InputSlotManifest {
	name: string;
	schemaId: string;
	securityClass: InputSecurityClass;
	binderId?: string;
	dependencyKeyTemplateIds: readonly string[];
}

interface OutputSlotManifest {
	name: string;
	schemaId: string;
	publicationClass: PublicationClass;
	dependencies: readonly DependencyOrigin[];
	outputKeyTemplateIds: readonly string[];
}

interface AuthorizationManifest {
	principalBinderId: string;
	resourceBinderId: string;
	contextBinderIds: readonly string[];
	requireCurrentAtAdmission: true;
	requireCurrentAtEndFence: boolean;
}

interface FreshnessManifest {
	dataRevisionMode: "current" | "bounded_stale" | "historical_exact";
	authorizationRevision: "current";
	policyRevision: "current";
	recheckDataAtEndFence: boolean;
}

interface IdempotencyManifest {
	namespace: string;
	scopeBinderIds: readonly string[];
	identityBinderId: string;
	digestProfileId: string;
	minimumProofRetentionSeconds: number;
}

type OwnerReceiptStatus = "pending" | "accepted" | "rejected" | "conflict" | "not_applied";

interface ReceiptManifest {
	receiptSchemaId: string;
	intermediateStatuses: readonly ["pending"];
	terminalStatuses: readonly ["accepted", "rejected", "conflict", "not_applied"];
	allowedTransitions: readonly [
		readonly ["pending", "accepted"],
		readonly ["pending", "rejected"],
		readonly ["pending", "conflict"],
		readonly ["pending", "not_applied"],
	];
}

interface ReconciliationManifest {
	statusLookupId: string;
	lookupConsistency: "linearizable_for_identity";
	notFoundMeaning: "unknown" | "authoritative_not_applied_after_fence";
}
```

`binderId`, key-template ID, schema ID, `originId`, and `statusLookupId` resolve only through trusted registries. `binderId` is required for trusted bindings and forbidden for model business payload. The linter resolves every dependency origin, requires every output to name its complete dependency closure, and rejects a publication class or receipt state not represented by the pinned rule registry.

Data freshness and authorization freshness are independent. `bounded_stale` or `historical_exact` may relax only the Case/data revision consumed by a read; authorization, policy, revocation, and manifest lifecycle state remain current at admission and at every contract-required end fence. Failure to obtain a current authority decision never falls back to an older projection.

The versioned `RiskCompatibilityMatrix` is also trusted registry data, not manifest-authored policy. It provides a complete allowed-combination row for every risk tier over operation class, reversibility, approval mode, publication class, and effect-domain kind. For the accepted first-slice definition, R1 permits only reversible additive Case records such as a neutral resource link or investigation note, forbids Case-authority changes, identity merge, scope/lifecycle change, and external publication, and permits automatic approval only when current Case policy authorizes that exact capability. An unclassified combination is invalid rather than “closest tier” matched.

## `opencti-case-projection/v1` invariants

The projection manifest should declare a closed projection contract, not an OpenCTI DTO map.

```typescript
interface ProjectionBlockManifest {
	semanticRole: string;
	requirement: "required" | "optional";
	blockSchemaId: string;
	rendererRuleId: string;
	outputSlot: string;
}

interface ProjectionProfileManifest {
	profileId: string;
	contractVersion: string;
	inputs: readonly InputSlotManifest[];
	outputs: readonly OutputSlotManifest[];
	blocks: readonly ProjectionBlockManifest[];
	snapshotSchemaId: string;
	deltaSchemaId: string;
	receiptSchemaId: string;
	authorization: AuthorizationManifest;
	freshness: readonly FreshnessManifest[];
	mayEffectDomains: readonly [];
}
```

`semanticRole` and `rendererRuleId` are strings in transport but resolve through closed registries; the linter rejects an unknown value. This shape makes requiredness, rendering, output slots, and output-specific dependency origins data that can be checked rather than prose promises.

### Minimum declarations

| Declaration | Required meaning |
|---|---|
| stable profile ID and manifest digest | Exact semantic profile admitted by the Workspace |
| input slots | Case binding, actor/tenant/purpose authorization, task/Lens, requested freshness/base revision/cursor, profile/schema/renderer versions |
| trusted-bound inputs | authorization revision, Case ID/head/base revision, purpose, security scope, cursor |
| output schema | complete projection snapshot/delta and receipt schemas |
| required and optional semantic block kinds | Closed list with explicit requiredness |
| block output keys | active projection and block-level dependency key templates |
| output-specific dependencies | Which inputs/version origins make each block/current projection valid |
| completeness and integrity proof | revision, policy revision, schema/profile version, cursor continuity, block/body digest, completeness/redaction marker |
| authorization behavior | no stale fallback after revocation; security labels retained |
| freshness modes | operations permitted under current, bounded-stale, and historical reads |
| may-effect domains | empty; projection read is non-mutating |
| failure classes | unsupported required block, malformed/partial body, cursor gap, digest mismatch, unauthorized, unavailable |

### Projection lint rules

- Every required semantic role has a schema and deterministic rendering rule.
- Optional unavailable material is represented as unavailable, not absent evidence.
- The projection receipt and snapshot envelope bind exactly one Case Revision and authorization/policy revision. Every block carries its source revision, security labels, and digest; its source revision must equal the enclosing snapshot revision, so a snapshot cannot mix revisions.
- All block resource references resolve to the declared neutral reference schema and retain resource versions.
- A delta declares base and result revisions, cursor continuity, operation kind (`add`, `replace`, `tombstone`), and completeness proof.
- `mayEffectDomains` must be exactly empty.
- A projection Adapter cannot emit a semantic role, authority label, requiredness value, or dependency-key kind absent from the admitted manifest revision.
- A result using an unsupported profile/schema/renderer version is rejected before materialization.
- Unknown or partially parsed required blocks fail the whole candidate; no partial active projection is installed.

## `case-capability-risk-registry/v1` invariants

### Minimum capability declaration

```typescript
interface CaseCapabilityManifest {
	capabilityId: string;
	contractVersion: string;
	riskTier: "R1" | "R2" | "R3" | "R4";
	operationClass: OperationClass;
	reversibility: "reversible" | "conditionally_reversible" | "irreversible";
	approval: "policy_automatic" | "human" | "two_person";
	execution: "read_parallel" | "effect_sequential";
	inputSchemaId: string;
	outputSchemaId: string;
	inputs: readonly InputSlotManifest[];
	outputs: readonly OutputSlotManifest[];
	mayEffectDomains: readonly CanonicalKeyTemplate[];
	authorization: AuthorizationManifest;
	freshness: FreshnessManifest;
	receipt: ReceiptManifest;
	idempotency?: IdempotencyManifest;
	reconciliation?: ReconciliationManifest;
}
```

### Capability lint rules

- `capabilityId` is unique and stable. Reusing it for different semantics is forbidden.
- Every input/output slot name is unique, ASCII, and stable within the contract version.
- Every output dependency reference resolves to a declared input or authoritative result-version origin.
- Every model-supplied input is allowed by `inputSchemaId`; every non-`business_payload` input is either `trusted_binding` or `verified_remote_output` and resolves to its declared binder/version proof.
- A capability with non-empty `mayEffectDomains` must be `effect_sequential`, fresh-required, and declare idempotency plus reconciliation.
- All effect domains must be bindable before dispatch. A capability that discovers an undeclared effect at runtime is nonconformant and disabled.
- Case mutations include the Case-head effect domain even when a finer semantic target is also declared.
- A Case write binds expected Case Revision, current authorization and policy revision, actor/tenant/purpose, capability ID/version, and stable effect identity.
- The same idempotency identity and digest always denotes the same logical effect. It may advance only through the declared monotonic intermediate-to-terminal transition table; once terminal, the authoritative terminal receipt is stable. The same identity with a different digest is rejected.
- Risk, approval, reversibility, and effect declarations must agree. R1 cannot be irreversible, change accepted finding authority, merge entities, change scope/lifecycle, or publish externally.
- `policy_automatic` is allowed only when the owning Case policy explicitly authorizes that exact capability and risk tier for the bound actor/resource/context.
- Output publication cannot claim Case authority. Only an accepted Case receipt followed by an authorized current Case Projection can make the change authoritative in Workspace context.
- A receipt schema enumerates pending/accepted-for-processing and all terminal statuses plus their allowed transitions. Transport success or `202` is not a terminal effect receipt.
- A capability that cannot supply an authoritative status lookup and retention guarantee cannot automatically retry an unknown mutation and must not be enabled for unattended effect execution.

## Runtime admission pipeline

The runtime path should be deterministic and ordered:

1. Resolve the exact manifest family/version/revision by trusted capability/profile ID and read the current lifecycle record.
2. Verify manifest digest and that the exact revision/digest is served and supported by the runtime and target Adapter; pin its `registryRevision`.
3. Validate the untrusted business payload against the pinned input schema; reject unknown fields.
4. Bind trusted actor, tenant, purpose, Case/resource, authorization/policy revision, current Case Revision, manifest-registry revision, dependency keys, and output/effect templates.
5. Evaluate authoritative authorization and capability policy for principal/action/resource/context.
6. Run semantic preconditions: risk/approval receipt, freshness, batch shape, conflict/suspension, output fence, and effect-domain availability.
7. Canonicalize the semantic request and calculate `requestDigest`.
8. For effects, durably store the original operation/effect identity, digest, bindings, output claims, and effect domains before dispatch.
9. For an effect, immediately re-read the lifecycle record and reject if the pinned manifest is no longer served. Then send the operation through the conformant Adapter, including expected revision and stable idempotency identity when effectful.
10. Validate the complete response schema, receipt identity/digest, authority, and version proof.
11. Apply local outputs and dependency edges atomically only after their authorization, policy, manifest-lifecycle, data-version, and dependency end fences pass.
12. Reconcile accepted or unknown effects using the original identity; never turn admission unavailability, timeout, or malformed response into a rejection.

Any failure through the pre-dispatch check in step 9 prevents remote dispatch. Failure after effect dispatch is evaluated using the declared idempotency/reconciliation contract and can become `indeterminate_effect`; it is not safely collapsed into `failed`.

### Rule ownership and failure codes

The **enforcement-phase rule catalog** prevents a successful schema/lint pass from being misreported as proof of runtime or Adapter behavior. Its input is every normative invariant in the two contract families; its output assigns one stable rule ID, owning phase, and failure code to each invariant. Its boundary is classification—it does not replace the actual validator, admission hook, or conformance test. An invariant with no owner, more than one authoritative owner, or an unknown rule-catalog version fails the build.

| Owning phase | What it can prove | Failure-code family |
|---|---|---|
| raw parse | duplicate names, valid Unicode/number domain | `manifest_parse_*` |
| structural schema | closed shape, types, required fields, enums | `manifest_schema_*` |
| semantic lint | resolved IDs/slots/keys, dependency closure, risk matrix, declared receipt transitions | `manifest_lint_*` |
| runtime admission | current authority/policy/lifecycle, payload validity, freshness, approval | `operation_admission_*` |
| pre-dispatch fence | current revisions and effect-domain availability immediately before send | `operation_dispatch_fence_*` |
| response/end fence | complete proof, digest/version match, non-stale output publication | `operation_result_*` |
| reconciliation | monotonic receipt transitions, authoritative lookup, unknown-effect handling | `effect_reconciliation_*` |
| Adapter conformance | the target actually exhibits the declared behavior | `adapter_conformance_*` |

Generated documentation and test names carry the same rule IDs. Static lint must not claim that an idempotent replay, policy decision, status lookup, or mixed-revision response rejection has been behaviorally proven; those belong to their runtime or conformance owner.

## Production and in-memory Adapter conformance

The manifest is credible only if each Adapter passes the same behavior suite. A mock that merely returns fixture objects is not conformant.

### Discovery handshake

Each production and in-memory Adapter must report:

- supported manifest family/API versions;
- supported exact profile/capability contract versions;
- supported input/output/receipt schema IDs;
- supported canonical key versions;
- idempotency and status-lookup semantics, including retention;
- supported authorization/policy proof versions; and
- Adapter conformance-suite version.

No mutual version means fail closed. Discovery metadata is not itself authorization; each operation still receives a current authoritative decision/proof.

### Shared conformance cases

Both Adapter classes must pass at least these tests:

1. a valid fixture produces the same normalized semantic result and canonical digest;
2. duplicate JSON names, unknown fields, unknown enums, unsupported schema dialects, and unresolved references are rejected;
3. all required projection blocks, revisions, security labels, completeness markers, and digests are present;
4. malformed, partial, mixed-revision, or digest-invalid projection responses never partially replace the active projection;
5. unknown required projection roles fail closed; declared optional unavailable roles remain explicit;
6. every capability binds the same trusted input slots and effect-domain templates in both Adapters;
7. model attempts to supply Case Revision, authorization/policy revision, dependency keys, risk tier, effect domains, or idempotency identity are rejected and audited before digest construction; trusted transport-envelope parsing, if needed, is a separate closed stage and never silently strips these fields from business payload;
8. unauthorized and explicit domain rejection remain distinct from timeout/unavailable/malformed response;
9. same idempotency identity and same digest yields one accepted semantic effect and the same terminal receipt;
10. same identity with a different digest produces a permanent mismatch/integrity error;
11. timeout after remote commit can be recovered through authoritative status lookup by the original identity;
12. a status lookup miss is not accepted as `no_effect` unless the Adapter's declared linearizability and retention contract makes it authoritative;
13. accepted receipt plus failed projection refresh yields `accepted_but_unsynchronized`, not rejection or unknown effect;
14. out-of-order or duplicate receipts merge monotonically; contradictory terminal receipts cause an integrity suspension;
15. an authorization/policy revision change fences an in-flight response even when transport succeeds;
16. Adapter-reported capability/profile support is rejected when its actual response violates the pinned manifest;
17. conversion fixtures round-trip without losing security, dependency, effect, approval, or receipt meaning; and
18. old manifest receipts remain decodable after a newer revision is installed.

Production conformance should run against an isolated OpenCTI/Case Management and I&E staging target. Destructive or externally publishing capabilities require dedicated test tenants and must not be inferred conformant from lower-risk capabilities. The in-memory Adapter runs the same suite in normal CI and additionally supplies deterministic fault injection for crash windows, lost/late responses, cursor gaps, and authorization revocation.

## Build and release gates

A manifest revision is releasable only when:

- its own schema validates against the pinned dialect/meta-schema;
- all referenced payload and receipt schemas resolve immutably and validate;
- semantic lint has no errors, warnings requiring acknowledgement, or unknown rule versions;
- the canonicalization implementation passes published and project cross-language vectors;
- the in-memory Adapter passes the full conformance suite;
- every production Adapter advertising the revision passes the applicable conformance suite in staging;
- compatibility analysis classifies the change and proves a valid rollout/conversion path;
- all deprecated/served/storage support metadata is internally consistent;
- generated capability/tool registration cannot bypass the registry; and
- the runtime has a deny-by-default path for unsupported or missing manifests.

Changing only generated model-facing tool descriptions does not update the authoritative manifest. Conversely, installing a manifest does not automatically expose a model tool; tool availability still depends on the current actor/Case policy and Workspace state.

## Explicit follow-on contract work

This research fixes the invariants but does not claim that the concrete manifest artifacts already exist. Implementation still must:

- choose and pin the actual schema dialect/validator, then publish closed schemas for the envelope, lifecycle record, Projection Profile, capability entries, and every referenced payload/receipt;
- publish the first closed binder, canonical-key, renderer, publication, receipt-state, and rule-ID registries, plus the complete risk matrix for every enabled tier; R2–R4 remain disabled until their rows and behavioral tests exist;
- select the exact first `digestProfileId`, cryptographic hash, canonical string encodings, and cross-language acceptance/rejection vectors; and
- prove the production Adapter's current-authorization fence, lifecycle fence, idempotency/status consistency, retention, and receipt behavior in the shared conformance suite.

An absent artifact is a release blocker, not an implementation-selected default. This preserves the fail-closed contract while leaving the specific JSON Schema/OpenAPI tooling and the eventual number of model-facing tools open.

## Rejected shortcuts

### “The TypeScript type is the manifest”

Rejected because runtime Adapters, persisted receipts, cross-version conversion, non-TypeScript implementations, and untrusted JSON payloads need a language-independent admitted contract and exact revision identity.

### “JSON Schema validation proves safety”

Rejected because schema assertions cannot infer CTI risk, dependency closure, authorization ownership, Adapter behavior, or effect reconciliation. General schemas validate structure; semantic lint and conformance validate meaning and behavior.

### “Unknown fields are forward compatible”

Rejected for enforcement objects. An older runtime might ignore a new effect, approval, or authority field and execute a weaker interpretation. Forward compatibility uses explicit served versions and conversion.

### “Default missing risk/effect fields to the safest value”

Rejected because different validators/defaulting stages can hash or interpret different objects, and a later default change silently changes behavior. Safety-critical declarations must be explicit.

### “A successful HTTP response proves the write”

Rejected because transport completion, accepted-for-processing, domain rejection, authoritative acceptance, local synchronization, and unknown effect are distinct outcomes.

### “The in-memory Adapter may implement a simpler contract”

Rejected because tests would then verify a different system. The in-memory Adapter may replace transport and storage, but not authorization, version, digest, idempotency, receipt, effect-domain, or failure semantics.

## Direct design implications

1. `opencti-case-projection/v1` should be a closed semantic profile with no remote effects and explicit complete-result proof.
2. `case-capability-risk-registry/v1` should be a closed action registry analogous to a typed authorization/action schema, with effect and recovery metadata that OpenAPI alone does not express.
3. Both should use stable manifest IDs plus immutable admitted revisions/digests; runtime receipts pin the exact revision.
4. The operation-dependency Module should consume only linted registry entries and typed canonical-key templates.
5. The model supplies business payload only. Trusted code supplies bindings, versions, dependencies, effects, idempotency identity, and digest.
6. Unknown types, fields, versions, required vocabularies, semantic roles, key kinds, or effects fail closed.
7. No production Adapter is enabled because it compiles. It is enabled only for the exact contracts it reports and passes in the shared conformance suite.
8. Version evolution preserves historical receipt decoding and performs side-effect-free, authorization-neutral conversion; incompatible safety meaning gets a new major/capability identity.

## Primary sources

- [JSON Schema Draft 2020-12 Core](https://json-schema.org/draft/2020-12/json-schema-core)
- [JSON Schema Draft 2020-12 Validation](https://json-schema.org/draft/2020-12/json-schema-validation)
- [OpenAPI Specification 3.2.0](https://spec.openapis.org/oas/v3.2.0.html)
- [OpenAPI published schemas](https://spec.openapis.org/oas/)
- [RFC 8259: JSON](https://www.rfc-editor.org/rfc/rfc8259.html)
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)
- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)
- [RFC 9396: OAuth 2.0 Rich Authorization Requests](https://www.rfc-editor.org/rfc/rfc9396.html)
- [Kubernetes: Extend the API with CustomResourceDefinitions](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/)
- [Kubernetes: Versions in CustomResourceDefinitions](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definition-versioning/)
- [Kubernetes: Dynamic Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
- [Kubernetes Deprecation Policy](https://kubernetes.io/docs/reference/using-api/deprecation-policy/)
- [Cedar authorization](https://docs.cedarpolicy.com/auth/authorization.html)
- [Cedar policy validation](https://docs.cedarpolicy.com/policies/validation.html)
- [Cedar schema](https://docs.cedarpolicy.com/schema/schema.html)
- [Amazon EC2 API idempotency](https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html)
