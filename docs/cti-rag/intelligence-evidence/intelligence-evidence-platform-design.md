# Intelligence and Evidence Platform Design

Status: Accepted architecture direction. Exact first-slice core behavior belongs to the active [`opencti-exact-resource-retrieval/v1`](opencti-exact-resource-retrieval-v1-contract.md) contract. Workspace consumption and provider disclosure remain separately gated.

## 1. Business problem and decision

I&E turns actor-authorized OpenCTI resources into reusable, exactly attributable material an Agent can retrieve and cite without confusing ingestion with evidence or rebuilding a CTI platform.

Without this Module, every Workspace would repeat source versioning, parser identity, offsets, chunking, indexing, license checks, lineage, de-duplication, retries, and retrieval logging. The same report could acquire different identities in different Cases, copied reporting could be miscounted as corroboration, and a model input could not be reconstructed after an OpenCTI object, parser, or index changed.

Adopt [ADR 0013](../adr/0013-use-opencti-as-ie-primary-infrastructure.md):

- OpenCTI is the primary CTI infrastructure and owns its current graph, files, Connectors, Workbenches, enrichment jobs, markings, actor-visible access, and source state.
- I&E is a derived deep Module. It owns Resource identity/version mapping, immutable Source Captures, derivatives, supplemental Provenance and Source Lineage, bounded enrichment admission, retrieval evidence, and optional Sidecar storage.
- Workspace owns Working Set selection, Case-scoped reasoning, final rendering, and the Model Input Receipt.
- Case Management owns formal Resource/Evidence References and accepted Case conclusions.

Independence is a bounded-context and code-ownership decision, not a requirement for a separate deployment. Start as a private package and introduce a network Seam only if a second process becomes real.

## 2. Authority map

| Concern | Authority |
| --- | --- |
| Current OpenCTI object/file, graph relation, marking, Connector/work and actor-visible access | OpenCTI through a qualified Adapter |
| Connector deployment, schedule, credential, queue, reset and infrastructure health | Operator/OpenCTI |
| Resource identity/version mapping and Source Capture | I&E |
| Extraction, Source Span, Retrieval Segment, embedding, Index Generation and Derivation Manifest | I&E |
| Supplemental Provenance, Source Lineage and Unknown Source Dependency | I&E |
| Query completeness, Resource Capsule and Retrieval Receipt | I&E |
| Working Set entry/version, selection and Coverage Boundary | Workspace |
| Logical provider invocation, disclosure decision and pre-invocation digest proof | Pi plus Workspace under `intelligence-working-set/v1` |
| Provider-specific HTTP/wire bytes or remote receipt | Provider Adapter/provider; not claimed by v1 |
| Resource/Evidence Reference and accepted finding | Case Management |

An OpenCTI ID anchors a Source Resource; it is not alone an immutable Resource Version. An OpenCTI timestamp, Connector work, import count, Stream event, History row, or Sidecar capture digest is not a Case Revision.

## 3. Module and Interfaces

The external Seam is one `IntelligenceEvidenceModule`. The following is architectural shape; a delivery contract closes its fields.

```ts
interface IntelligenceEvidenceModule {
	retrieve(request: RetrievalRequest, options?: { signal?: AbortSignal }): Promise<RetrievalOutcome>;
	requestEnrichment(request: EnrichmentRequest, options?: { signal?: AbortSignal }): Promise<EnrichmentOperationReceipt>;
	observeOperation(operationRef: string, options?: { signal?: AbortSignal }): Promise<EnrichmentOperationOutcome>;
}
```

`retrieve` accepts a trusted exact-resource or bounded-search intent and returns only a complete Retrieval Receipt plus Resource Capsules. A model never constructs that request: Workspace first admits a Task Context Plan, mints an opaque Resource Candidate Reference from current Orientation membership, and a trusted qualified recipe compiles the exact selector. `requestEnrichment` accepts one closed `EnrichmentProfile` and business target; the caller cannot name a Connector, parser, worker, URL, credential, queue, schedule, retry, or publication rule. `observeOperation` recovers the same stable operation after timeout or crash; it does not dispatch again.

The first contract exposes only exact retrieval. Bounded search and enrichment activate under later contracts without changing ownership. Model-visible tool number, names, and decomposition are independent from these internal operations.

The report-chain
[`workspace-evidence-assembly/v1`](../agent-workspace/evidence-assembly-v1-contract.md)
uses the Design-PASS
[`evidence-assembly-exact-revalidation/v1`](evidence-assembly-exact-revalidation-v1-contract.md)
profile behind this same `retrieve(...)` Interface. It accepts only exact
owner refs and receipts mapped from an admitted Workspace Working Set, performs
no query expansion or substitute retrieval, and returns complete current
Resource/Span/assertion/relationship/lineage qualification. It is not a fourth
root method or activation of deferred graph/vector search; implementation
readiness remains NO.

The first package keeps one deep public Module and two initial export surfaces:

| Export | Purpose |
| --- | --- |
| `@earendil-works/pi-cti-rag-intelligence-evidence` | public request/outcome/receipt/capsule types and the `IntelligenceEvidenceModule` Interface; no construction Port |
| `@earendil-works/pi-cti-rag-intelligence-evidence/testing` | deterministic fixture catalog, in-memory Module factory and conformance runner; no credentials or live source calls |

The package must not depend on `cti-rag-agent-workspace`, `agent`, Case Management or a provider SDK. Workspace later receives an already composed `IntelligenceEvidenceModule` from the application composition root and depends only on the root Interface; it never constructs I&E. The first core has no model/embedding dependency. A transport or storage library is added only when the selected Adapter demonstrates that need; package creation must not speculate a connector framework.

A `/node` composition export is deferred until a production deployment contract closes its configuration, credential-reference, storage, clock and signing-key inputs. The first TDD cycle may keep its production-shaped Adapter composition private and exercise it through the `/testing` conformance runner. Root must not expose private Ports merely to make construction convenient.

Internally, the exact-retrieval Implementation composes private OpenCTI read, operation store, source-use policy, trusted clock, canonicalization and receipt-signing Ports. These remain private Seams so the public Interface hides retries, atomic publication, key rotation, storage layout and target qualification. A second public Module is not introduced for those mechanics.

### What the Implementation hides

- OpenCTI GraphQL documents, file download and deployment qualification;
- actor/purpose authorization and marking revalidation;
- source capture, canonicalization, hashes, versions, schema evolution and de-duplication;
- parser, OCR, span coordinates, chunker, embedding and index selection;
- license/use/retention decisions;
- source routing, pagination, continuity, timeouts, retries and rate/cost budgets;
- operation identity, worker leases, fencing, receipts, outbox and recovery;
- index generations, exact-hit verification, result ordering and diagnostics retention.

Deleting this Module would redistribute those rules across every Workspace and tool Adapter, so the Module earns Depth and Locality.

## 4. Dependencies and Adapters

| Dependency | Category | Strategy |
| --- | --- | --- |
| OpenCTI GraphQL/files/jobs/streams | True external | qualified production Adapter plus contract mock |
| I&E catalog/blob/index when in-process | Local-substitutable | transactional/local test implementation behind private Seams |
| Future remote I&E deployment | Remote but owned | transport Adapter plus in-memory Adapter at the same owning Interface |
| parser/normalizer/lineage reducer | In-process initially | keep private until two real implementations justify a Seam |
| Workspace consumer | Separate bounded context | depends only on the owning I&E Interface and receipt contract |

OpenCTI search may generate candidates, but the I&E Adapter must exact-verify every selected current hit before publication. A privileged index may not disclose hidden existence, counts, scores, text, or provenance.

## 5. Data and state

```text
OpenCTI Source Resource/File
  -> immutable Source Capture
  -> Extraction + Source Spans
  -> Retrieval Segments
  -> optional Embeddings
  -> staged then atomically active Index Generation
  -> Retrieval Receipt + Resource Capsules
  -> Workspace Pi Session save-point CAS for Working Set apply
  -> Workspace Model Input Receipt + Pi logical invocation artifact
```

Every derivative has a Derivation Manifest binding exact inputs, producer artifact/version, configuration, schema/canonicalization profile, output digest, policy binding, and derivation edges. A segment, embedding, or index hit remains in its upstream Source Lineage and never creates Independent Corroboration.

Resource state is not one overloaded status. Keep independent axes:

- immutable Resource Version and Source Capture;
- publication: staged, published, withdrawn, quarantined;
- Use Disposition: allowed, restricted, denied, unknown;
- availability: available, temporarily unavailable, purged;
- current Source Lineage assessment revision.

Changed content creates another version. Withdrawal, license change, visibility loss, or lineage reassessment changes status/dependencies without rewriting old bytes. If an actor-scoped read cannot distinguish deletion from visibility loss, expose only `not_found_or_not_visible`.

## 6. Commit and consistency model

Long work never spans one transaction. Each stage writes private staging, verifies exact inputs/schema/digests/policy/completeness, commits an immutable manifest plus blob reference, then uses expected-head compare-and-swap to activate a generation.

- Source Capture manifest and content pointer publish together.
- Extraction publishes only with its declared complete Source Span set.
- Segment and embedding manifests bind exact parent digests.
- Index builds are build-new-then-swap; readers see the old complete generation or the new complete generation.
- Search indexes are rebuildable projections, never authority. Catalog commit includes an outbox entry.
- Retrieval pins one catalog/index generation and publishes one complete receipt. Attempts are never spliced.
- Workspace commits its Working Set records in the owning Pi Session save-point CAS; this is separate from I&E publication, and I&E never writes it.

Exact-current operations perform a final OpenCTI/status/access fence. Exact historical material may be used only when current policy authorizes that historical use. Bounded search declares its actor-scoped generation, filters, Top-K, ranking versions, observation time/watermark, omissions, and lag; it never claims global corpus completeness.

## 7. Model and deterministic-code boundary

The model may propose target-neutral Query Candidates, select among currently exposed opaque Resource Candidate References, request a named bounded enrichment outcome, draft summaries, and propose extraction/entity/attribution hypotheses.

Deterministic code owns schema, identity, versions, digests, authorization, markings, license/use, retention, budgets, Connector/profile selection, de-duplication, queueing, retries, completeness, lineage independence, receipts, publication, and current-status fences.

The model cannot compile an exact selector, activate a capability, admit a Resource, choose infrastructure, declare source independence, merge entities, assign Evidence role, accept a Case conclusion, or publish externally. Model/OCR outputs are versioned derivatives with exact model/prompt/config/input/output digests and remain non-authoritative.

## 8. Normal paths

### Retrieval

1. After Task Context admission, trusted Workspace code revalidates its capability activation, actor/purpose/task binding and current Resource Candidate membership, then compiles an exact or bounded selector. A Query Candidate alone causes no I&E call.
2. I&E validates contract, authorization, budgets, policy and stable request identity.
3. The Adapter reads a qualified OpenCTI surface; exact-current reads are fenced for content and access drift.
4. I&E resolves or creates only complete published derivatives.
5. Search, when enabled, pins one Index Generation; selected hits are exact-verified.
6. I&E final-validates status/use, then atomically publishes a Retrieval Receipt and ordered Resource Capsules.
7. Workspace separately selects and atomically applies entries, then revalidates before model disclosure.

### Bounded enrichment

1. The Agent requests a business outcome named by an active Enrichment Profile.
2. Deterministic admission binds actor, purpose, exact inputs, profile version, operation ID, fan-out, time, bytes, concurrency and cost.
3. I&E reuses an existing terminal/in-flight operation or dispatches through a qualified Adapter.
4. OpenCTI work/job evidence is correlated to the I&E operation; it never replaces the I&E receipt.
5. Complete outputs publish under immutable manifests. Workspace sees only a terminal outcome, never progress as intelligence.

## 9. Failure, retry and concurrency

- Timeout/cancellation settles the caller locally; ignored abort cannot publish late output.
- Same operation ID and request digest reuses the terminal receipt/computation, but every material disclosure is reauthorized. Same ID with another digest is an integrity conflict.
- A retry is a new attempt under the same binding; pages and nondeterministic outputs from attempts are never combined.
- Crash before a stage transaction produces no visible artifact. Crash after commit/before acknowledgement recovers the committed receipt.
- Worker leases use fencing tokens; first terminal publication wins and older workers become actor-safe diagnostics.
- OpenCTI resource/access drift before publication rejects the candidate. Revocation observed before the final disclosure-decision/dispatch marker has zero allowance; change after that linearization cannot retract possibly dispatched bytes, but it blocks future use and fences late output.
- Independent item success is publishable only when a contract predeclares independently complete slots; otherwise the batch is all-or-none.
- Concurrent identical derivations converge by input/method digest. Different method versions coexist. Active-head conflict never overwrites the winner.
- Exact byte de-duplication may share storage but never collapses Source Resource identity, Provenance, collection occurrence, or Source Lineage.
- A stream/history gap dirties only the affected partition and forces re-read/rebuild; unrelated work continues.
- If a native enrichment dispatch may have occurred but no stable OpenCTI work/resource reconciliation is available, that profile fails deployment qualification. Blind redispatch is forbidden.

This bounded I&E operation record is not the frozen strict-R1 Durable Operation Journal. Any future operation with a non-idempotent external business effect requires a separate contract.

## 10. Reproducibility, retention and observability

Long-lived Retrieval Receipts store query/selector, closed filters, Top-K, final ordered segments and scores, every processing version, catalog/index generation, policy decision digest, and result digest. Retrieval Traces store full candidates and intermediate ranking features only for a bounded diagnostic period.

Workspace and Pi store the pre-invocation evidence defined by `intelligence-working-set/v1`: a Model Input Receipt, Disclosure Decision and logical invocation digest over the prepared provider-neutral Adapter input. V1 does not claim provider-specific HTTP/wire bytes, a remote receipt, exact-input reconstruction or complete-prompt retention. Protected exact-input replay is a separate deferred contract. A digest proves equality only and never reproducible model output.

Every operation emits actor-safe metrics: duration, OpenCTI request count/bytes, cache outcome, extraction units, segment count, index lag, candidate/final count, cost units, terminal code and retry count. Credentials, hidden identifiers, protected bodies and raw external errors never enter ordinary logs.

Retention is policy- and source-qualified. A derivative inherits at least the source's strictest marking, license and retention. `unknown` never means allowed. External embedding/model disclosure is a separate use decision. Legal hold may delay physical deletion but cannot preserve retrieval eligibility.

The first contract requires its source profile to permit at least 365 days of I&E-owned exact Source Capture, Resource Capsule, Retrieval Receipt and decoder/canonicalization replay material, with 30-day diagnostics and 24-hour staging. That permission does not extend to User Task, Session, Orientation, tools, model/options, credentials or a complete provider prompt. Every profile also declares an absolute policy maximum that references cannot extend; model eligibility ends before required purge. Later source profiles must set their own numeric horizons before activation.

## 11. Raw corpus and OpenCTI baseline

The user-declared snapshot includes MITRE ATT&CK, Malpedia, OTX, CIRCL MISP OSINT, ORKL, URLhaus, ThreatFox and 14 PDFs. It is accepted as a collection inventory, not as admitted I&E Resources. Existing source manifests remain the count/hash authority. Every source still requires an explicit source profile for license, stable identity, version/window, schema, duplicate, lineage, retention and permitted-model-use behavior.

Local OpenCTI currently contains MITRE ATT&CK. It proves one useful exact-resource seed and the delivered Orientation path; it does not prove production Connector qualification, the rest of the corpus, I&E derivation, query completeness, or source independence. No repeat MITRE import is required.

## 12. Validation and trade-offs

The Interface is the test surface. Production-shaped and in-memory Adapters run the same contract fixtures. Acceptance must cover success, zero/hidden result, schema drift, marking loss, timeout/ignored abort, duplicate replay/conflict, every commit crash window, late worker, current-version drift, index lag, lineage dependency, retention, tampering and cross-partition concurrency.

Selected approach: OpenCTI plus a small transactional Sidecar. It reuses mature CTI infrastructure while paying only for immutable derivation and retrieval evidence.

Rejected:

- OpenCTI alone: smallest deployment, but its public contract does not supply parser/span/chunk/index/model-input provenance or caller-idempotent receipts.
- Parallel full CTI graph: maximal control, but duplicates Connector, STIX, graph, authorization and operations and creates two source authorities.
- Per-Workspace raw access: quick prototype, but spreads license, identity, parsing, lineage and failure rules across callers.
- Generic workflow/plugin engine: flexible before use cases exist, but exposes a shallow DSL and freezes unsafe extension semantics.
- Full graph/vector/LLM pipeline in the first slice: high cost and poor fault isolation; exact ID solves the first measured path.

## 13. Delivery sequence and gates

1. **Active IER1 core:** one existing OpenCTI ATT&CK object -> immutable capture -> structured Source Span/segment -> exact Retrieval Receipt/Resource Capsule, tested only through the public I&E Interface and two Adapter shapes.
2. **Gated Workspace consumer:** trusted Resource Candidate binding -> exact IER1 call -> Pi Session save-point Working Set apply -> provider-disclosure revalidation.
3. **Gated provider disclosure:** Model Input Receipt + logical invocation artifact -> pre-I/O marker -> single-use prepared invocation.
4. File capture and deterministic document extraction with page/text coordinates.
5. Lexical bounded search and explicit Index Generation.
6. Embeddings/vector/reranking only after measured retrieval failure justifies them.
7. One side-effect-free bounded enrichment profile; native OpenCTI enrichment only after job reconciliation qualification.
8. Additional source profiles one at a time; no bulk corpus activation by inference.

The IER1 core does not import Workspace and is not technically dependent on PNW/TQ. Its package TDD may start under the owning Code Map route and active contract. Workspace consumption remains NO-GO until PNW-A through PNW-E and TQ-01 through TQ-21 pass independently through the public Workspace seam. Real-provider disclosure additionally requires complete IER1/IWS1 and Pi provider-dispatch acceptance. These gates deliberately separate Module development from integration and activation.

## 14. Frozen and deferred

Frozen/deferred: production Connector control or fleet changes; bulk ingestion; PDF/OCR/vector production rollout; recursive enrichment; generic workflow engine; entity merge; automatic attribution or corroboration promotion; Case Management implementation; ResourceUsePermit; strict R1 and Durable Journal; Assessment/ACH; external publication; multi-user shared analysis; and concrete model-visible tool decomposition.

## 15. Evidence basis

- [OpenCTI as I&E primary infrastructure](../research/opencti-as-ie-primary-infrastructure-2026-07-20.md)
- [OpenCTI public data bootstrap](../research/opencti-public-data-bootstrap-2026-07-20.md)
- [OpenCTI entity resolution and fusion boundary](../research/opencti-entity-resolution-data-fusion-boundary.md)
- [Source confidence, ambiguity, and multi-actor evidence](../research/source-confidence-ambiguity-multi-actor.md)
