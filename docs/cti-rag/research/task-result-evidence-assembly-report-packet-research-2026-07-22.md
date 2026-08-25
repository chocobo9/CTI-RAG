# Task Result, Evidence Assembly and Report Packet Research

Date: 2026-07-22  
Status: Research only. This note creates no contract, schema, Module, database,
or implementation authorization.

## Question

After an Investigation Run settles, what distinct product results must exist
before a no-tool Report Agent can safely compose and publication can validate a
user-facing report?

## Sources

### Current CTI-RAG design authority

- [Agent Investigation Product Workflow v1](../agent-workspace/agent-investigation-product-workflow-v1-contract.md), especially stages E--I. Its status is **Design candidate; Design Gate FAIL**.
- [I&E Platform Design](../intelligence-evidence/intelligence-evidence-platform-design.md).
- [I&E Context](../intelligence-evidence/CONTEXT.md).
- [Case Management Context](../case-management/CONTEXT.md).
- [Workspace Output Publication v1](../agent-workspace/workspace-output-publication-v1-contract.md).
- [Case Persistence v1](../case-management/case-persistence-v1-contract.md).

### External primary sources

- [STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html): a STIX Relationship Object represents an edge between SDOs/SCOs, and carries a relationship type, endpoints and optional context. A STIX Report refers to objects, but that reference set alone does not establish analytical support or contradiction.
- [W3C PROV overview](https://www.w3.org/TR/prov-overview/): provenance concerns entities, activities and agents involved in producing a thing; it supports quality/trust assessment but is not itself a truth judgment.

## Determined current design

1. A settled Agent Run and its final Save Point are necessary operational
   evidence, but they do not define the semantic result for a report writer.
   The workflow contract explicitly identifies the missing Stage F.
2. The workflow already requires three *different* products before formal
   report composition: **Task Result**, **Claim-Evidence Subgraph**, and
   **Report Evidence Packet**. They are requirements, not accepted schemas or
   completed contracts.
3. I&E owns immutable Resource Versions, Source Captures, Retrieval Segments,
   derivative manifests, Source Lineage, Retrieval Receipts and current use
   qualification. Its graph/index/embedding derivatives are retrievable,
   rebuildable projections; they are not Case evidence roles or Case truth.
4. Case Management owns the durable Case record, Case Revisions, accepted
   findings, and the formal Resource/Evidence References. An Evidence Reference
   is Case-assessed and fallible; it is not a raw resource or a proof.
5. Workspace owns the task-scoped Working Set, task/result selection and
   assembly, Run-context bindings, report composition orchestration and
   publication gate. It cannot turn a retrieval score, model assertion or
   graph path into an accepted Case conclusion.
6. The Report Agent is a bounded no-tool composer. It cannot query a graph or
   vector index, repair lineage, create citations, add evidence, publish, or
   write a Case. Publication's deterministic check proves identity, current
   authorization and mechanically checkable literal/span matching; its narrow
   audit evaluates support/contradiction/overstatement without creating
   authority.
7. The present I&E active core is exact-resource retrieval only. Bounded
   search, graph traversal, embeddings, reranking and production Index
   Generation are deferred. Consequently, no current contract licenses a live
   graph-plus-vector assembly path.

## Deduction from those boundaries

### Three products should remain separate contracts

They answer different questions and have different invalidation conditions:

| Product | Question it answers | Why it cannot be merged |
| --- | --- | --- |
| Task Result | What did this admitted task achieve or fail to achieve? | It binds goals, terminal disposition, Save Point and remaining work. It does not decide whether evidence supports a claim. |
| Claim-Evidence Subgraph | Which exact, currently qualified material bears which stated relationship to each task-scoped claim? | It preserves provenance, counterevidence and dependence. It cannot determine presentation, route outcome, or Case acceptance. |
| Report Evidence Packet | What bounded, disclosure-authorized evidence/result projection may this report profile consume? | It is an input projection for one composer/audit/publication pass, not a durable source graph, Case revision, or generic retrieval result. |

Calling all three an "evidence packet" would conceal authority differences and
make invalidation ambiguous. Calling the subgraph a Case Evidence Reference
would be equally wrong until Case Management separately assesses/accepts the
relationship.

### Ownership and seam placement

No independent Evidence Assembly Module is justified by the current design.
The complex operation is one **Workspace-owned task-scoped assembly seam**,
with I&E and Case Management as authority-owning inputs:

| Concern | Owner | Consequence |
| --- | --- | --- |
| Run goals, terminal disposition, valid Save Point, incomplete/blocked state, task-local next-step proposals | Workspace / Run Control | Forms the operational basis of Task Result. |
| Exact source, source span, derivative, graph relation provenance, lineage, retrieval/index receipt, status and current use decision | I&E | Workspace must consume qualifying references/receipts; it cannot recreate or amend them. |
| Case revision/mandate and later formal Candidate Finding, Resource Reference, Evidence Reference or accepted conclusion | Case Management | A report packet cannot silently write or upgrade Case state. |
| Selection of which qualified material answers this task, claim-to-material candidate relationships, bounded report projection and post-settlement refresh check | Workspace | This is assembly, and is necessarily scoped to one task and consumer. |
| Narrative expression | Report Agent | Receives only the packet; no retrieval or evidence repair. |
| Publication proof, audit decision and disclosure | Workspace Publication plus its owners | Happens after composition and cannot be delegated to the composer. |

This preserves a deep Workspace seam: callers ask for a report-ready,
task-scoped, qualified projection, without learning index mechanics, graph
storage, lineage calculation, disclosure checks or report-model details.

The subgraph itself need not become a new globally shared artifact. It is a
bounded Workspace projection whose nodes/edges reference I&E and Case-owned
identities. Persisting any of it beyond the task, sharing it, or letting it
become Case state is a separate product choice requiring a Case contract.

### What a claim edge means

The product needs to distinguish at least four *semantic classes* in the
future contract, rather than treating every edge as proof:

- source or graph assertion: an exact source version says or represents a
  relationship;
- derivation/provenance: one capture, segment, extraction or embedding derives
  from another item;
- task-scoped analytic relationship: qualified material supports, contradicts,
  qualifies or fails to resolve a reported claim;
- Case-assessed evidentiary role: a later Case Management Evidence Reference.

STIX's relationship edge supplies useful CTI relation semantics, but it does
not model report-claim entailment. Likewise, W3C provenance supports tracing
how material was produced, not deciding whether an analyst's conclusion is
true. These distinctions prevent a vector similarity, repeated upstream report
or model-generated assertion from being misrepresented as independent support.

## Research recommendations

### 1. Contract sequence and minimum handoff

Do not begin with JSON Schema. Close the contracts in this order:

1. **Task Result Contract** under Workspace/Run Control: defines the
   post-settlement, machine-readable task outcome and its one-to-one binding to
   admitted task/goals, terminal disposition and final trusted Save Point.
2. **Evidence Assembly Contract**, jointly reviewed across Workspace, I&E and
   Case Management: defines how Workspace requests/rechecks qualified material
   and creates a task-scoped claim/evidence projection without claiming Case
   authority. It must name the cross-owner inputs, but should not copy their
   schemas.
3. **Report Evidence Packet Contract** under Workspace/report composition:
   defines the bounded, consumer-specific projection from those first two
   products, its exact packet-to-report binding, and the pre-compose/validation
   checks.
4. **Task Outcome Report Contract** under Workspace Publication: defines the
   public report variants and report-profile requirements. It should consume
   the packet, not duplicate the Task Result or evidence graph contracts.

This is a contract sequence, not four proposed Modules. The first three have
different interfaces and lifecycle controls; the last is the presentation
contract already partially anticipated by publication.

### 2. Required lifecycle/authority rules

An accepted design should require, at minimum:

- Task Result is produced only from one settled Run and final valid Save Point;
  no raw model delta or uncommitted Tool result enters it.
- Every reportable claim declares whether it is source fact, task-scoped
  analytical judgment, unresolved question, or status/coverage statement.
  Generated analysis never becomes an I&E Resource or Case conclusion merely
  through inclusion.
- Every cited evidence item remains resolvable to a Resource Version and, where
  applicable, Source Capture/Source Span, Derivation Manifest, lineage and
  Retrieval Receipt. A graph relationship must identify its versioned source
  basis; an index hit alone is not a support edge.
- The assembly step performs current status/use/authorization revalidation and
  records the relevant observation/generation basis. A withdrawn, stale,
  restricted, missing or unresolvable item cannot be silently retained in a
  new packet.
- Independence is an I&E lineage result. Multiple items from one upstream
  lineage remain repeated reporting, not independent corroboration. Unknown
  dependency stays unknown.
- Counterevidence, contradictions, material omissions and coverage limits are
  first-class packet content. Absence of a graph path or semantic hit is not a
  proof of absence unless I&E's declared coverage says so.
- A report packet is bound to one task, Workspace, Case reference/revision
  basis where present, Access Principal, Use Purpose, Context Consumer, report
  profile, final Save Point and source/index/qualification basis. It expires or
  is rejected on any binding drift that would make disclosure or source status
  unsafe.
- The composer may only use supplied aliases and material. Deterministic
  validation verifies the candidate against that packet; the independent audit
  judges semantic grounding and fails closed as the existing workflow says.
- Report publication remains non-authoritative Workspace output. Case update is
  an explicit, separately validated proposal; a published report must not
  imply Case acceptance.

### 3. Minimal acceptance matrix

The eventual contracts should prove public behavior over at least these cases:

| Scenario | Required result |
| --- | --- |
| completed Run, each reportable claim has current qualified material | packet may reach composition; report still requires validation/audit/publication. |
| Run settles insufficient evidence, budget exhausted or blocked | Task Result and bounded-incomplete report represent the state; no invented partial claim or success presentation. |
| interrupted Run with trusted Save Point | only trusted completed work/status can form the interruption packet; no reconstruction from private history. |
| interrupted Run without trusted Save Point | safe interruption status only; no reconstructed claims. |
| retrieval score/graph path lacks exact source/version/span qualification | cannot form a cited support edge or report claim. |
| supporting and contradicting evidence coexist | both and their lineage/uncertainty are supplied; composer cannot omit a material conflict. |
| apparently independent evidence shares a lineage, or lineage is unknown | packet represents repeated/unknown dependency rather than multiplying corroboration. |
| source/version/use/visibility changes after assembly | packet is rejected or reassembled; stale material is not disclosed. |
| report candidate invents alias, citation, literal, relation, or certainty | deterministic validation/audit withholds it; no best-effort repair by guessed evidence. |
| publication succeeds but Case update is absent/rejected | report remains non-authoritative and Case Revision remains unchanged. |

## Undecided product choices

The research does **not** decide:

- the canonical claim/edge vocabulary, identifier scheme or JSON shape;
- whether task-scoped subgraphs/packets are durably retained and for how long;
- the graph owner/Adapter and whether it is OpenCTI-only or includes qualified
  I&E supplemental lineage projections;
- the exact bounded-search/vector/reranking pipeline, once I&E activates it;
- source independence heuristic, confidence policy or contradiction thresholds;
- report profiles/templates, composer/auditor model qualification and whether
  a human-review lane is required for particular impact tiers;
- public report retention, artifact publication, or Case write-back policy;
- exact refresh, expiry, recovery and cross-Case reuse rules.

Those are meaningful product choices. They must be closed in their owning
contracts (and an ADR if a durable cross-context authority decision is made),
not inferred from this note or implemented from a generic RAG pattern.

## Design disposition

Adopt for the next design review only the conclusion that the gap is real and
that the four-contract sequence above is the smallest coherent route. Do not
authorize report implementation, graph/vector activation, packet persistence,
or Case write-back until the relevant owner contracts and acceptance matrix are
accepted.
