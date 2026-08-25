# `workspace-evidence-assembly/v1` Contract

Status: **Design candidate; Design Gate FAIL. No implementation is authorized.**

Research basis:
[Task Result, Evidence Assembly and Report Packet Research](../research/task-result-evidence-assembly-report-packet-research-2026-07-22.md).

## 1. Product purpose

Evidence Assembly is the second handoff in the report chain:

```text
committed Task Result
  + task Working Set
  + current I&E qualification
  + current Case basis
  -> task-scoped Claim-Evidence Subgraph
  -> later Report Evidence Packet
```

It answers:

> Which exact, currently qualified materials and provenance relationships are
> relevant to each Task Result statement, what does each source actually
> assert, and what candidate role may each material have?

It does not answer:

> Is the task analysis true, should the Case accept it, or how should the
> report describe it?

This contract freezes ownership, lifecycle and semantics before fixing a JSON
Schema.

## 2. No new Module or graph authority

Evidence Assembly is one private **Workspace task-scoped assembly seam**. It is
not:

- a new Evidence Assembly Module;
- a persistent global evidence graph;
- a vector database;
- an I&E replacement;
- a Case evidence repository;
- another Agent, model call or investigation loop; or
- a generic graph-query Interface exposed to report composition.

The existing Workspace Module is deepened with one logical operation:

> Assemble one bounded, qualified Claim-Evidence Subgraph for one committed
> Task Result from already admitted task material.

Callers and the Report Agent never learn graph storage, vector-index,
OpenCTI-query, lineage-reducer or qualification mechanics.

Deletion test: without this seam, every report profile, Composer and auditor
would independently resolve source versions, spans, retrieval receipts,
lineage, authorization and Case authority. Keeping the behavior in Workspace
provides leverage and locality without creating another owner.

## 3. Owner responsibilities

### 3.1 OpenCTI

OpenCTI remains the current source of CTI objects and source relationship
objects. An OpenCTI relationship says that one versioned source represents a
relationship. It does not prove that a report claim is true or that the
relationship is an independent corroboration.

Workspace does not query OpenCTI directly at this seam. It consumes an I&E
qualified projection of the exact source relationship and observation basis.

### 3.2 Intelligence and Evidence

I&E owns:

- Intelligence Resource and Resource Version;
- Source Capture and Source Span;
- Retrieval Segment and Derivation Manifest;
- source/derivation lineage and independence/unknown-dependency result;
- Retrieval Receipt, search/index generation and ranking profile;
- current source status, marking, use qualification and disclosure eligibility;
  and
- rebuildable OpenCTI relationship and retrieval projections.

I&E may report that material was retrieved, connected, derived, repeated,
independent or of unknown dependency under an exact versioned basis. It does
not decide that the material semantically entails a Workspace claim.

I&E also keeps four observations separate:

- reporting prevalence: how many qualified occurrences carry the same or
  materially similar source assertion;
- source variety: how many distinct resources or channels carry it;
- lineage grouping: which occurrences derive from or relay the same upstream
  source; and
- unknown dependency: which apparently separate occurrences cannot yet be
  proven independent.

Occurrence frequency and channel variety describe visibility. Only materially
independent lineage groups may count as independent corroboration, and even
that never turns a source assertion into a verified fact.

Evidence Assembly reuses the existing deep
`IntelligenceEvidenceModule.retrieve(...)` Interface. It does not add a sibling
`qualifyForAssembly`, graph client or vector client.

The I&E
[`evidence-assembly-exact-revalidation/v1`](../intelligence-evidence/evidence-assembly-exact-revalidation-v1-contract.md)
contract has Design PASS for one bounded profile behind that same method:

- input is an ordered set of opaque exact refs already admitted into the
  Working Set;
- query text, similarity query, neighbor expansion and substitute resources are
  forbidden;
- every input ref receives one complete eligible/ineligible outcome;
- eligible outcomes use the existing Retrieval Receipt and Resource Capsule
  ownership, extended only where necessary with exact relationship-version,
  Source Span, derivation and lineage qualification;
- partial transport success is not a complete outcome; and
- the profile performs current use/status qualification without activating a
  new search or model dependency.

This keeps source/index/storage mechanics hidden inside the existing I&E Module
and preserves its production plus in-memory Adapter conformance seam.

### 3.3 Agent Investigation Workspace

Workspace owns:

- verifying the exact committed Task Result;
- selecting only task-admitted Working Set material;
- requesting current qualification of those exact references from I&E;
- assembling bounded claim/material/provenance nodes and candidate
  relationships;
- preserving supporting, contradicting, qualifying and unresolved candidates;
- recording omissions, conflicts, unknown dependency and coverage limits;
- binding the subgraph to Task, Run, Save Point, Case and access basis; and
- committing one private task-scoped subgraph and assembly receipt.

Workspace cannot invent source identity, lineage, retrieval coverage or formal
Case evidentiary roles.

Evidence Assembly reuses the existing Working Set records:

- `WorkingSetEntryV1` is the task-local material identity;
- `WorkingSetSelectionV1` supplies the exact ordered current selection and
  generation;
- `WorkingSetDerivationEdgeV1` traces how retrieval/capsule inputs created an
  entry; and
- `WorkingSetLocalReceiptV1` plus the owning Save Point proves admission.

A Task Result Proposal may name only opaque Working Set `entryRef` values.
Workspace, not the model, resolves their entry/resource/capture/receipt
digests. Existing Working Set derivation edges remain provenance; they are not
relabelled as claim-support edges.

### 3.4 Case Management

Case Management owns:

- the Case and Case Revision;
- accepted Case findings/conclusions;
- neutral Resource References;
- formal `Evidence Reference` relationships; and
- acceptance/rejection of any later Case update proposal.

A Workspace candidate-support or candidate-contradiction edge never becomes a
Case `Evidence Reference` through assembly, reporting or publication.

## 4. Input authority and scope

One assembly attempt binds:

- one exact committed `workspace-task-result/v1`;
- its Run settlement and trusted Save Point/absent-anchor basis;
- one Workspace, task, Session/branch and Run generation;
- one Case reference/revision basis when a Case exists;
- one Access Principal and Use Purpose;
- one current Working Set generation containing only task-admitted material;
- exact I&E Resource/Span/lineage/retrieval/index observation bases; and
- one Evidence Assembly contract/profile version.

Evidence Assembly performs **no new search**. During the Investigation Agent
Run, RAG is an ordinary typed Tool capability:

```text
Agent emits bounded RAG Tool request
  -> deterministic capability/request admission
  -> I&E retrieval through its owned Interface
  -> Tool result qualification
  -> atomic Tool result + Working Set admission + owner receipt Save Point
```

The model may supply only the schema-valid query intent and bounded request
parameters allowed by the admitted Tool. It cannot select a database, index,
credential, hidden source identifier, authorization basis or trusted receipt.
The returned vector, lexical, graph or exact retrieval results remain candidate
material until qualification and Working Set admission complete.

Assembly later consumes only those admitted entries. It may re-read or
revalidate their exact references through I&E; it cannot broaden the query,
retrieve a similar item, substitute a newer resource or invoke the RAG Tool
again.

If required task material is absent, stale or unqualified, assembly records a
bounded gap or returns a blocked/limited decision. It does not restart the
Agent Run.

## 5. Claim-Evidence Subgraph semantics

The output is one private, bounded, immutable task projection. It contains
references and safe metadata, not unrestricted source bodies, embeddings or a
copied OpenCTI graph.

### 5.1 Node classes

The future schema must distinguish:

- Task Result statement;
- exact source assertion carried by one Resource Version and Source Span;
- exact I&E Resource Version;
- exact Source Capture/Source Span or Retrieval Segment;
- versioned source relationship assertion;
- Derivation Manifest or lineage group;
- Retrieval Receipt/index observation;
- current qualification/status observation; and
- existing Case-assessed reference when Case Management supplies one.

A node from one class cannot be silently retyped as another.

### 5.2 Relationship classes

Relationships have separate authority classes:

1. **source assertion** — an exact source or OpenCTI relationship version
   asserts/represents a relation;
2. **derivation/provenance** — one capture, segment, extraction, embedding or
   indexed occurrence derives from another item;
3. **lineage/dependency** — materials are independent, share a lineage, or have
   unknown dependency according to I&E;
4. **task candidate relationship** — qualified material is proposed as
   supporting, contradicting, qualifying or not resolving a Task Result
   statement; and
5. **Case-assessed relationship** — an existing formal Case Management
   reference, included only by exact Case-owned identity.

Only class 4 is created by Workspace assembly. It remains explicitly
`candidate` and non-authoritative. Deterministic validation can prove its
endpoints and provenance, but only the later independent Evidence Audit judges
semantic support, contradiction or overstatement for publication.

### 5.3 Vector and lexical retrieval

A vector or lexical hit contributes:

- exact Retrieval Receipt;
- query/request and Index Generation binding;
- rank/score only within that receipt;
- exact Resource Version and Source Span/Segment; and
- I&E current qualification.

It may contribute one or more exact source assertions carried by the qualified
Span. It does not by itself contribute a support edge, confidence, evidence
weight, lineage independence or Case fact. Similarity says why the material was
retrieved, not whether its assertion is true or whether it supports the task
statement. Missing exact source/span/receipt binding makes the hit ineligible.

### 5.4 Graph relationships

A graph path contributes only the individually versioned, source-traceable
relationship assertions that I&E qualifies. Path existence, path length or
shared entity proximity does not prove a Task Result statement.

Each admitted source relationship must resolve to its exact source/version and
observation basis. A path with an unresolved, hidden, stale or synthesized edge
is ineligible as report material.

### 5.5 Contradiction, duplication and coverage

Supporting and contradicting candidates coexist. Assembly cannot remove a
material contradiction merely because more supporting items were retrieved.

Assembly records occurrence count, distinct-resource/channel count, resolved
lineage-group count and unknown-dependency count separately for materially
similar source assertions. Repeated reports sharing one upstream lineage
increase reporting prevalence but remain one corroboration group. Unknown
dependency remains unknown and cannot count as independent support.

No reducer may turn rank, similarity, raw occurrence count or channel count into
truth probability. A later report may say that an assertion is widely reported
or independently corroborated only when the exact prevalence and lineage basis
permits that wording, and must preserve material contradictions.

Absence of a graph path or retrieval hit is not evidence of absence unless I&E
supplies a bounded coverage statement proving what corpus, time, relationship
types, filters and completeness were observed.

### 5.6 Closed subgraph carrier

The v1 subgraph is a closed semantic carrier rather than a copied graph-store
format:

```ts
interface ClaimEvidenceSubgraphV1 {
	protocol: "workspace-claim-evidence-subgraph/v1";
	subgraphRef: string;
	basis: ClaimEvidenceSubgraphBasisV1;
	decision: "ready" | "limited";
	orderedStatementNodes: readonly ClaimEvidenceStatementNodeV1[];
	orderedMaterialNodes: readonly ClaimEvidenceMaterialNodeV1[];
	orderedAssertionNodes: readonly ClaimEvidenceAssertionNodeV1[];
	orderedSourceRelationshipNodes: readonly ClaimEvidenceSourceRelationshipNodeV1[];
	orderedLineageGroups: readonly ClaimEvidenceLineageGroupV1[];
	orderedLineagePairs: readonly ClaimEvidenceLineagePairV1[];
	orderedCandidateEdges: readonly ClaimEvidenceCandidateEdgeV1[];
	orderedPrevalenceObservations: readonly ClaimEvidencePrevalenceObservationV1[];
	orderedCoverageAndOmissions: readonly ClaimEvidenceCoverageOrOmissionV1[];
	subgraphDigest: string;
}

interface ClaimEvidenceSubgraphBasisV1 {
	taskResultRef: string;
	taskResultDigest: string;
	runSettlementRef: string;
	runSettlementDigest: string;
	finalSavePointRef: string | null;
	workspaceRef: string;
	taskRef: string;
	caseRef: string;
	caseRevision: string;
	sessionRef: string;
	branchRef: string;
	runGenerationId: string;
	accessPrincipalBindingDigest: string;
	usePurpose: "case_investigation";
	workingSetVersion: string;
	workingSetSelectionDigest: string;
	revalidationReceiptSignedPayloadDigest: string;
	qualifiedViewSemanticDigest: string;
	assemblyProfileRef: string;
	assemblyProfileVersion: string;
	assemblyProfileDigest: string;
}
```

The subgraph copies no Task Result prose or source body. It binds exact
statement, Working Set, I&E and Case-owned refs/digests and leaves those owners
authoritative for their content.

### 5.7 Node and candidate-edge carriers

```ts
interface ClaimEvidenceStatementNodeV1 {
	statementRef: string;
	statementDigest: string;
	goalRef: string;
	class:
		| "source_assertion"
		| "task_analysis"
		| "unresolved_question"
		| "status_or_coverage";
	reportRequirement: "required" | "optional";
	nodeDigest: string;
}

interface ClaimEvidenceMaterialNodeV1 {
	materialRef: string;
	workingSetEntryRef: string;
	workingSetEntryDigest: string;
	resourceVersionRef: string;
	sourceCaptureId: string;
	resourceCapsuleSemanticDigest: string;
	sourceChannelRef: string;
	sourceChannelDigest: string;
	citationProjectionDigest: string;
	orderedQualifiedSpanRefs: readonly string[];
	qualificationSubjectDigest: string;
	nodeDigest: string;
}

interface ClaimEvidenceAssertionNodeV1 {
	assertionRef: string;
	assertionDigest: string;
	kind:
		| "structured_value"
		| "source_relationship"
		| "bounded_text_span";
	materialRef: string;
	orderedSourceSpanRefs: readonly string[];
	nodeDigest: string;
}

interface ClaimEvidenceSourceRelationshipNodeV1 {
	relationshipRef: string;
	relationshipVersionRef: string;
	relationshipType: string;
	fromResourceVersionRef: string;
	toResourceVersionRef: string;
	orderedSourceSpanRefs: readonly string[];
	relationshipDigest: string;
	nodeDigest: string;
}

interface ClaimEvidenceCandidateEdgeV1 {
	edgeRef: string;
	statementRef: string;
	target:
		| { kind: "source_assertion"; assertionRef: string }
		| { kind: "qualified_material"; materialRef: string };
	role:
		| "candidate_support"
		| "candidate_contradiction"
		| "candidate_qualification"
		| "unresolved_relevance";
	origin: "task_result_association";
	semanticAuditRequired: true;
	edgeDigest: string;
}
```

Only Task Result associations already committed under the exact Working Set
selection can create candidate edges. Workspace may discard an invalid or
ineligible association but cannot invent a new semantic role.

A material-level edge is allowed only when I&E has no exact assertion
projection. It must use `unresolved_relevance`; it cannot be labeled support,
contradiction or qualification.

### 5.8 Lineage and reporting-prevalence carriers

```ts
interface ClaimEvidenceLineageGroupV1 {
	lineageGroupRef: string;
	orderedMaterialRefs: readonly string[];
	assessmentRevision: string;
	groupDigest: string;
}

interface ClaimEvidenceLineagePairV1 {
	leftLineageGroupRef: string;
	rightLineageGroupRef: string;
	relation: "materially_independent" | "unknown_source_dependency";
	assessmentRevision: string;
	pairDigest: string;
}

interface ClaimEvidencePrevalenceObservationV1 {
	statementRef: string;
	candidateAssociatedOccurrenceCount: number;
	distinctResourceCount: number;
	distinctChannelCount: number;
	lineageGroupCount: number;
	independentLineagePairCount: number;
	unknownDependencyPairCount: number;
	orderedExactAssertionOccurrences: readonly {
		assertionDigest: string;
		occurrenceCount: number;
	}[];
	observationDigest: string;
}
```

Prevalence is calculated only over eligible candidate associations for one
statement. Exact assertion occurrences group only equal assertion digests.
Unequal assertions associated with the same statement contribute to candidate
occurrence/resource/channel counts but are not declared semantically equal.

`independentLineagePairCount` counts exact pair observations, not independent
sources. No scalar truth, reliability, confidence or corroboration score is
derived. Report wording such as “independently corroborated” remains subject to
the later semantic audit of the exact candidate edges.

### 5.9 Coverage, omission and reducer

```ts
interface ClaimEvidenceCoverageOrOmissionV1 {
	observationRef: string;
	kind:
		| "material_ineligible"
		| "required_material_missing"
		| "assertion_projection_unavailable"
		| "relationship_unavailable"
		| "unknown_source_dependency"
		| "material_contradiction"
		| "retrieval_coverage_limit"
		| "assembly_bound_exceeded";
	orderedStatementRefs: readonly string[];
	requiredForReport: boolean;
	ownerEvidenceRef: string;
	ownerEvidenceDigest: string;
	observationDigest: string;
}
```

The deterministic reducer returns:

- `ready` when every required statement is either non-evidentiary
  status/coverage/unresolved content or has at least one eligible assertion
  candidate, and every required contradiction/limit is represented;
- `limited` when a valid bounded subgraph exists but one or more required
  statements remain unresolved, dependent, contradicted or outside proven
  coverage; or
- `blocked` with no subgraph when identity, authorization, Task Result, Working
  Set, Case, qualification or bounds prevent a safe complete carrier.

The reducer never chooses a preferred claim, removes a contradiction, converts
frequency into confidence or calls a model.

### 5.10 Bounds, canonical order and receipt

| Item | v1 hard maximum |
| --- | ---: |
| Task Result statement nodes | 64 |
| eligible material nodes | 32 |
| source assertion nodes | 256 |
| source relationship nodes | 256 |
| candidate edges total | 256 |
| candidate edges per statement | 16 |
| lineage groups | 32 |
| lineage pairs | 496 |
| prevalence observations | 64 |
| coverage/omission observations | 128 |
| canonical subgraph | 2 MiB |

At-limit succeeds. One-over is `assembly_bound_exceeded`; required overflow is
`blocked`, while optional overflow may produce `limited` only when the exact
omission is recorded and every required statement/contradiction remains
represented. There is no silent truncation or multi-packet continuation in v1.

All refs are 1–512 UTF-8 bytes without C0/C1 controls. Profile identifiers are
1–128 ASCII identifier characters. Every digest is exactly 64 lowercase
hexadecimal SHA-256.

Each record digest is SHA-256 over exact UTF-8 RFC 8785 JCS bytes with only its
own digest member omitted. Arrays use Task Result order for statements, Working
Set selection order for materials, and byte-order by stable ref for every other
node/edge/observation class. Duplicate refs or non-canonical order reject the
whole carrier.

The authenticated assembly receipt is:

```ts
interface ClaimEvidenceAssemblyReceiptV1 {
	protocol: "workspace-claim-evidence-assembly-receipt/v1";
	assemblyAttemptRef: string;
	basisDigest: string;
	decision: "ready" | "limited" | "blocked";
	subgraphRef: string | null;
	subgraphDigest: string | null;
	orderedCoverageAndOmissionDigests: readonly string[];
	createdAt: string;
	authenticity: {
		algorithm: "HMAC-SHA-256";
		keyId: string;
		signedPayloadDigest: string;
		macBase64Url: string;
	};
}
```

For `ready` or `limited`, one subgraph entry precedes one physically-last
receipt in the same A4 control group. For `blocked`, only the safe non-content
receipt is committed. The receipt HMAC covers exact UTF-8 JCS bytes of the
complete receipt with `authenticity` omitted. Commit conflict appends none;
unknown acknowledgement permits exact lookup only.

## 6. Assembly lifecycle

The order is:

1. verify the Task Result and atomic Run settlement;
2. verify Case, Access Principal, Use Purpose, Session/branch and Working Set
   bindings;
3. collect only exact task-admitted material refs and candidate relation intents;
4. ask I&E to revalidate exact Resource/Span/lineage/retrieval/relationship
   references under the current use binding;
5. exclude or explicitly classify stale, withdrawn, hidden, missing and
   unresolvable material;
6. group materially similar source assertions and record occurrence, channel,
   lineage-group and unknown-dependency counts without deleting occurrences;
7. assemble all eligible source/provenance/lineage and task-candidate
   relationships;
8. record contradictions, unknown dependency, gaps and coverage;
9. deterministically validate bounds and complete digests; and
10. commit one private subgraph entry followed by one physically-last
    authenticated assembly receipt through the existing Pi Session
    control-batch Interface.

Commit conflict appends neither entry. Acknowledgement uncertainty permits
exact lookup only. No report packet is produced before committed or exact-
present assembly evidence exists.

## 7. Output and authority

One assembly decision is:

- **ready:** all report-required Task Result statements have at least one
  qualified candidate relationship or are explicitly non-evidentiary
  status/coverage statements;
- **limited:** a valid subgraph exists, but one or more findings remain
  unresolved, contradicted, dependent or outside proven coverage; or
- **blocked:** required identity, authorization, source/version/span,
  Working Set, Case or qualification evidence cannot be established safely.

`limited` is a legitimate input to a later bounded-incomplete report. It cannot
be rendered as completed certainty. `blocked` creates no Report Evidence
Packet from that assembly attempt.

The committed subgraph is:

- private and task-scoped;
- non-authoritative;
- not automatically model context;
- not globally searchable or reusable across Cases;
- not a Case write or Case evidence ledger; and
- eligible only for the next bounded Report Evidence Packet projection.

## 8. Invalidation and recovery

The subgraph is immutable historical assembly evidence. It becomes ineligible
for a new Report Evidence Packet when any bound member drifts, including:

- Task Result or settlement identity;
- Case Revision/basis;
- Access Principal or Use Purpose;
- Working Set generation;
- Resource Version, Source Capture/Span or source status;
- marking, visibility or disclosure eligibility;
- lineage/independence classification;
- Retrieval Receipt, Index Generation or ranking profile;
- graph relationship version/observation; or
- assembly contract/profile.

Drift causes revalidation/reassembly from exact owner references. It never
patches an existing subgraph, substitutes a similar vector hit or edits the
Task Result.

A crash before commit leaves no subgraph. A crash after possible commit uses
the retained control-batch evidence for exact lookup and never repeats search,
the Agent Run, Tool calls or model calls.

## 9. Failure closure

| Failure | Required closure |
| --- | --- |
| Task Result/settlement mismatch | no assembly |
| Working Set ref not task-admitted | reject the ref; required ref makes the attempt blocked |
| graph/vector result lacks exact Resource Version/Span/Receipt | ineligible; never form candidate support |
| source withdrawn, hidden or use denied | exclude and mark drift/gap; never disclose |
| lineage shared | retain occurrences but collapse corroboration group |
| lineage unknown | preserve unknown; never treat as independent |
| high occurrence count from one lineage | report prevalence only; never multiply corroboration or confidence |
| support and contradiction coexist | preserve both and mark conflict |
| source relation edge cannot be traced/versioned | exclude edge; required relation makes attempt limited/blocked |
| Case `Evidence Reference` absent | remain task-candidate relation; do not synthesize one |
| commit conflict/unknown | append nothing or exact lookup only |

No failure falls back to raw source text, unqualified OpenCTI data, direct
vector-store output, model confidence, graph proximity or a guessed citation.

## 10. Public acceptance candidates

The eventual public test seam remains the Workspace task/report flow. Tests
observe owner-call counts, actual Working Set/I&E receipts, Session entries,
report eligibility and Case non-mutation; they do not expose a graph helper.

1. A committed Task Result plus current qualified material produces one
   task-scoped subgraph and assembly receipt.
2. An interrupted result with a trusted Save Point uses only material admitted
   by that Save Point.
3. An interruption without a trusted Save Point has no factual/analytic
   statements and performs no evidence assembly search.
4. Supporting and contradicting materials are both retained.
5. Same-upstream repeated reporting remains multiple occurrences in one lineage
   group, not multiplied corroboration.
6. Occurrence count, distinct channel/resource count, independent lineage-group
   count and unknown-dependency count remain distinct and deterministic.
7. Unknown dependency remains unknown.
8. A lexical/vector hit without exact Resource Version, Span and Retrieval
   Receipt cannot form a candidate relationship.
9. A graph path with an unqualified or untraceable edge cannot form report
   material.
10. Source withdrawal, version drift, authorization loss or marking change after
   assembly prevents old-subgraph packet use.
11. A task-candidate support/contradiction edge creates no Case
    `Evidence Reference` and changes no Case Revision.
12. An existing Case-assessed relationship is included only by exact
    Case-owned reference and is not recreated by Workspace.
13. RAG retrieval occurs only as an admitted typed Tool call during the Agent
    Run; its qualified result and Working Set mutation commit atomically before
    later assembly can see it.
14. Assembly performs zero model calls, zero new searches and zero direct
    graph/vector database calls.
15. `limited` preserves conflicts/gaps for later reporting; `blocked` creates no
    packet.
16. Commit replay returns the exact same subgraph; conflict, changed digest and
    foreign Task Result append nothing.

The matrix remains candidate material until the blockers below close.

## 11. Frozen architecture decisions

- Evidence Assembly is a Workspace seam, not a Module or database.
- It consumes only already admitted task material and performs no new search.
- RAG is an admitted typed Tool during the Agent Run and uses the normal Tool
  request, validation, result qualification and Save Point path.
- Workspace reaches graph/vector capabilities only through I&E Interfaces.
- Vector/lexical hits are material candidates, never support proof.
- Graph paths are source relationship candidates, never entailment proof.
- Source assertions, reporting prevalence and independent corroboration remain
  separate; repetition from one lineage never multiplies truth confidence.
- I&E owns exact material, provenance, lineage, retrieval and qualification.
- Workspace owns the task-scoped candidate relationship projection.
- Case Management alone owns formal Evidence References and accepted Case
  conclusions.
- The subgraph is a bounded private task projection with a durable receipt, not
  a reusable global graph.
- Evidence Audit, not deterministic assembly, judges semantic support for
  publication.

## 12. Design Gate

- **Verdict:** FAIL
- **Owner:** Agent Investigation Workspace assembly seam; I&E and Case
  Management retain their source/evidence authorities
- **Interface:** one private assemble operation from committed Task Result and
  task-admitted owner refs to one Claim-Evidence Subgraph decision
- **Input authority:** Task Result/settlement, Working Set, Case basis,
  Access Principal/Use Purpose and exact I&E qualification/receipt projections
- **Output/evidence:** ready/limited/blocked decision; ready/limited includes one
  immutable private subgraph plus authenticated Session commit evidence
- **Failure closure:** unqualified material never forms an edge; blocked creates
  no packet; commit uncertainty uses exact lookup
- **Secret isolation:** no credentials, unrestricted source bodies, raw
  embeddings, hidden graph data or direct database handles
- **Provider lifecycle count:** zero model/Provider calls and zero new search
  operations
- **Workspace exposure:** private assembly status and safe counts only
- **Backward compatibility:** no existing graph/vector result is accepted
  without the exact owner qualification required here
- **Public acceptance seam:** Workspace task/report flow with actual owner
  receipts, Session evidence and Case non-mutation
- **Remaining blockers:**
  1. **Owner: Workspace Working Set + Run Control. Expected:** every Task Result
     candidate material ref is an opaque `WorkingSetEntryV1.entryRef` resolved
     under the exact `WorkingSetSelectionV1`, local receipt and contribution/
     Save Point basis; existing derivation edges remain provenance. **Actual:**
     the closed association and consumer-basis carriers are now defined, but
     the owning Task Result contract remains Design Gate FAIL and the Working
     Set consumer remains frozen/reference-only. **Minimal fix:** accept the
     Task Result contribution/result carrier and activate the narrow Working Set
     consumer revision through its existing public seam; do not introduce
     another material-ref catalog or edge authority.
