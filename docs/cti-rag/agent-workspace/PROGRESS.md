# Agent Investigation Workspace Progress

## Agent Memory first SQLite vertical slice

The independent `packages/agent-memory/` module now has an executable first
vertical slice: typed `prepare`/`revalidate`/`settle`/`manage` seams; deterministic
settled-Run admission; scoped exact recall; provenance, owner-reference and
temporal eligibility; append-only SQLite events with materialized entries,
idempotency and revision checks; correction, contradiction and content-free
forget tombstones; and fail-closed revalidation. `memory_events` is the
append-only revision/history authority, while `memory_entries` is only the
current materialized projection. Request idempotency stores the complete
receipt/result once, and each entry revision has a stable event identity.
Each operation also stores a canonical request digest; reusing a key with a
different candidate, Run proof, scope, purpose, or management mutation returns
an integrity conflict without replaying or applying an effect.
Focused public-seam tests cover
failed Run closure, replay, scope/purpose isolation, expiry, deletion and
prompt-injection-as-data. Model extraction, hybrid/vector retrieval, provider
integration, Case/Workspace/I&E adapters, restore/challenge/explain operations,
and full CTI E2E remain `NOT_IMPLEMENTED` or deferred. This executable evidence
does not change the Agent Memory contract's design-candidate status. Its
`settle` Interface and `working` category are probe-only and do not define the
candidate contract. The project names the runtime composition Context Assembly:
it combines current
instructions, skills, user input, history, owner-qualified context, and selected
durable Memory contributions. The Memory module supplies qualified
contributions; Context Assembly owns the final Provider input. The current
probe's `working` durable category is therefore provisional and must not be
treated as the formal domain model.

## Product workflow from task entry to report: Design Gate FAIL

The
[Agent Investigation Product Workflow v1](agent-investigation-product-workflow-v1-contract.md)
is now the primary product narrative above the Harness and evidence mechanics.
It separates Task Intake from the current Case-bound Task Understanding step.
The bounded intake model performs semantic intent understanding and emits one
closed structured route to clarification, Quick Response, Formal Investigation
or rejection. Deterministic code validates schema and hard safety constraints,
then executes the admitted route; it does not attempt exhaustive intent
classification. This exposes a real placement gap: the implemented Task
Understanding path begins only after `CaseWorkspace.open`, so it cannot decide
whether a new Case and Session should exist.

Formal Investigation reuses the existing Investigation Run Control authority.
Its Investigation Work Plan is a projection of admitted goals, subquestions,
pending actions, budgets and disposition; there is no second TODO engine,
planner Agent or workflow DAG. Every route now ends in a mandatory
route-appropriate Task Outcome Report. Formal Investigation uses a separate
bounded post-settlement report call over an exact evidence packet; Quick
Response is its own concise report, and failure/cancellation/discard produces
an Interruption Report from the last valid Save Point instead of pretending
completion. Current research recommends qualifying `deepseek-v4-pro` in
non-thinking JSON mode with no Tools as the formal report-composer candidate;
legacy `deepseek-chat` and `deepseek-reasoner` aliases are not selected.

The caller-visible Task Outcome Stream contains only committed progress derived
from Pi Save Points and one admitted report. Report Provider deltas remain
private; after the complete report passes deterministic validation, the narrow
Evidence Audit and a committed publication decision, the immutable report may
be streamed to the caller with a resumable output cursor. This deliberately
reopens the current whole-candidate Publication design for a transport-level
  streaming amendment without allowing raw candidate leakage. ADR 0020 freezes
  the distinction: publication is complete and atomic before transport delivers
  any deterministic chunk.

The former handoff gap between Run settlement and report composition is now
split into Task Result, task-scoped Claim-Evidence Subgraph and bounded Report
Evidence Packet contracts. Their product shapes are closed, while their
upstream owner seams remain gated. The old
`SettledInvestigationEvidencePacket` name is non-normative. Vector similarity
may retrieve candidate Segments but cannot itself establish evidence,
corroboration or claim relationships.

The first contract in that sequence now has a
[Task Result v1 design candidate](task-result-v1-contract.md). It deepens the
existing Run Control settlement seam rather than creating a Task Result Module.
It separates the private machine-readable result from
`ModelResponseCandidateV1`, classifies every statement as source assertion, task
analysis, unresolved question or status/coverage, preserves partial/incomplete
goal state, and requires interruption output to come only from a trusted Save
Point. Its Design Gate remains **FAIL** because current Run Control/Publication
bind goal coverage directly to the response candidate, prohibit mixed partial
non-completion, have no committed interim semantic-progress record, and do not
represent a settled interruption with no trusted Save Point. No implementation
is authorized.

The Task Result candidate now has closed contribution and final-result carriers:
one to four goals, classified source-assertion/analysis/question/status
statements, bounded progress/conflict/gap/next-step records, opaque Working Set
associations, revision/supersession lineage, hard byte/count limits, canonical
ordering and SHA-256 digests. The remaining Design Gate failures are the
Run-Control/Publication migration, the Save Point receipt amendment and Pi's
versioned two-entry settlement anchor—not the product shape.

The selected recovery shape is now narrower than the initial candidate:
Task Result and Run settlement are separate application records in one atomic
Pi control group, ordered `Task Result -> physically-last settlement terminal`.
There is no post-settlement Task Result transaction or crash gap. Trusted
interim semantic progress is an optional Workspace contribution inside an
existing Save Point group. A Run interrupted before any trusted Save Point may
settle only through a versioned status-only absent-anchor path against the
captured Run-admission leaf. These architecture decisions are frozen, but exact
carriers/bounds/digests and the required Run Control/Publication/PNW Interface
amendments remain Design Gate blockers.

The second contract now has an
[Evidence Assembly v1 design candidate](evidence-assembly-v1-contract.md).
It creates no Module or database: Workspace revalidates only task-admitted
Working Set refs through I&E and commits one bounded private Claim-Evidence
Subgraph. OpenCTI relationship paths and lexical/vector hits remain source or
material candidates; neither becomes semantic support. I&E retains exact
Resource/Span, provenance, lineage, receipt and qualification authority;
Workspace owns only task-candidate relationships; Case Management alone owns
formal Evidence References.

This candidate now also freezes RAG placement and prevalence semantics. RAG is
an admitted typed Tool during the Investigation Agent Run and follows the
normal request admission, I&E invocation, result qualification, Working Set and
Save Point path; Evidence Assembly performs no search. Source assertions,
occurrence frequency, distinct channel/resource count, independent lineage
groups and unknown dependency remain separate. Repeated relay from one lineage
increases reporting prevalence but never multiplies corroboration or truth
confidence.

The I&E exact-revalidation dependency now has separate **Design PASS /
implementation readiness NO** behind the existing `retrieve(...)` Interface.
Evidence Assembly now has a closed semantic carrier with statement/material/
assertion/relationship/lineage/prevalence/omission records, hard bounds,
canonical ordering, digests, authenticated receipt and ready/limited/blocked
reducer. Task Result material associations and the Working Set consumer basis
are also closed without adding a catalog. Evidence Assembly remains Design Gate
FAIL only because the owning Task Result contribution/result carrier is not yet
accepted and the Working Set consumer remains frozen/reference-only.

The third contract now has a
[Report Evidence Packet v1 design candidate](report-evidence-packet-v1-contract.md).
It adds no Module or model lifecycle: Workspace projects one committed Task
Result/subgraph into one ephemeral report-profile/consumer/attempt packet,
persists only a non-content binding receipt, and reuses Pi's existing bounded
one-shot Provider Dispatch frontend with prepared exact counting. It performs
no search, carries no Tools and cannot be rebound after source, authorization,
Case, Working Set, lineage or profile drift. The Design Gate remains **FAIL**
until the two upstream contracts pass.

Its detailed carrier is now closed: three formal investigation/interruption
profiles, deterministic statement/source/excerpt aliases, exact bounded I&E
span content, coverage/omission records, hard byte/token limits, packet and
non-content receipt digests, and the application mapping to one existing Pi
`exact_required` no-tool one-shot attempt. Clarification, unsupported, Quick
Response and status-only interruption remain outside this formal packet rather
than fabricating Task Result/evidence inputs.

The fourth/public contract now has a
[Task Outcome Report v1 design candidate](task-outcome-report-v1-contract.md).
Every accepted route produces a report variant; formal investigation uses the
packet, a no-tool DeepSeek Composer candidate, deterministic validation and one
narrow fresh-context Evidence Audit. Raw Provider deltas remain private;
streaming reads only immutable committed report bytes and resumes by public
output cursor. Report publication never changes Case state. The Design Gate
remains **FAIL** pending accepted upstream products, route-owned non-formal
inputs and Composer/Auditor qualification.

The report carrier is now field-level closed: five discriminated variants,
bounded findings/citations/limitations, no numeric confidence, exact private
candidate/validation/audit bindings, at most one same-packet recomposition and
one deterministic Markdown renderer. The renderer, not either model, owns
public section order, citation syntax and exact UTF-8 bytes.

The report union is shared product output, not a shared lifecycle. Formal
Investigation and Workspace-bound Interruption use Workspace Publication.
Pre-Workspace Clarification and Unsupported/Policy, plus any Session-free Quick
Answer, cannot fabricate a Workspace/A4 receipt; their route-owned atomic
public-result seams remain a bounded Design Gate blocker.

The
[Task Outcome Publication Stream v1 amendment](task-outcome-publication-stream-v1-contract.md)
now closes the previously missing transport shape. One A4 group commits the
complete report, deterministic chunk manifest and physically-last receipt
before the first public content event. First delivery and resume read only that
authenticated output, require fresh disclosure authority, and perform zero
Composer/Auditor/Provider/Tool calls. Revocation can stop future chunks but does
not turn the already complete publication into a partial report. Its Design
Gate remains **FAIL** on the report-chain prerequisites, the Pi public
event/result amendment and per-chunk disclosure-fence carrier review.

Deterministic validation remains authoritative for source identity, exact
version, access, citations and forbidden data. A fresh-context Evidence Auditor
does only semantic entailment, contradiction, fabrication and overstatement
reasoning; it cannot route, investigate, use Tools or Memory, rewrite, establish
truth, invent evidence or authorize a Case write.

The product workflow Design Gate remains **FAIL** on three bounded decisions:
Task Intake and route/model thresholds; the Case Management new-Case/bootstrap
Interface; and accepted upstream report-chain owner seams plus measured
report-composer/auditor qualification and the Pi/disclosure protocol amendments.
No implementation task is authorized.

## Access Principal / Use Purpose terminology: decision PASS, migration FAIL

[ADR 0019](../adr/0019-name-access-principal-and-use-purpose-explicitly.md)
accepts `AccessPrincipalBinding`, `principalRef`, and `usePurpose` for trusted
access identity and data-use authorization. It explicitly preserves Threat Actor
and separates Case mandate, Task Objective, Context Consumer, and Operation
Intent. `usePurpose` is trusted hidden workflow state, not model input and not
output validation.

The
[terminology revision](access-principal-use-purpose-terminology-revision.md)
records semantic rename rules, digest/protocol migration, visibility and
ordering. Cross-contract migration remains **Design Gate FAIL**: current
authority contains both access `"case_investigation"` and Run
`"cti_investigation"` values plus unrelated Pi/context and goal meanings named
`purpose`; persisted-receipt compatibility, exhaustive occurrence
classification, and owner-specific acceptance are not frozen. No implementation
task is authorized for the whole-repository migration.

The bounded current Workspace Orientation vertical
`WS-ACCESS-PRINCIPAL r2` has **Design PASS / implementation FAIL / kill switch
active**. It migrates
only the implemented `CaseWorkspace.open` access binding, materialized
Orientation, invalidation and fake/live qualification to
`AccessPrincipalBinding`, `principalRef`,
`usePurpose: "case_investigation"`, and
`opencti-case-orientation/v2`. It provides no v1 alias or dual reader and does
not touch Threat Actor, Pi runtime, I&E, Case writes or deferred scope.
Revision 1 stopped before product edits because the schema loader was omitted
from its allowed-file list. Revision 2 made the v2 public tracer green, but its
first complete six-file focused run finished **121 passed / 8 failed**: two
Case Workspace expectations, five fake-live/smoke paths returning
`model_failed`, and one credential-rotation reopen expectation. The one repair
allowance is exhausted. Related regression and root check were not run after
the failure. Partial product changes remain at that exact checkpoint; no r3,
focused implementation PASS or Integrated PASS is authorized.

## PNW-C Initial Investigation Context: Design Gate FAIL

[`workspace-initial-investigation-context/v1`](initial-investigation-context-v1-contract.md)
is now a superseded reference-only candidate. Its fixed seven-section record,
three synthetic context messages, per-section digests and compiler-owned
Provider projection are rejected duplicate design and are not implementable
authority.
[ADR 0018](../adr/0018-keep-memory-as-an-owner-local-architecture-view.md) is
superseded by [ADR 0021](../adr/0021-make-memory-management-a-first-class-agent-module.md).
The old owner-local Memory disposition is retained only as historical context;
the current consensus is the first-class Memory Management redesign recorded
below.

Implementation remains **NO-GO** under the replacement Run Context Preparation
candidate. Duplicate shape/digest ownership is closed by reusing Pi; the open
blockers are PNW-B long-lived composition, a public placement tracer for the
existing context hook, and the exact Provider application-authority binding.
The current per-Turn staging implementation cannot pass the one-spine
acceptance requirement. The Memory direction in the preceding historical
paragraph is superseded by ADR 0021 and the Memory redesign section below.

The
[industry and Pi reuse audit](../research/initial-context-industry-reuse-audit-2026-07-22.md)
confirms that owner-local memory, thread/cross-thread separation, application
qualification, and separate Tool transport follow mature patterns. It also
confirms that the seven-section serialized record, three synthetic user
messages, duplicate section digests, serialized empty slots, and timestamp
binding are project-local proposals, not established standards. The audit adds
unclosed prompt-injection/authority, provider-role portability, multimodal
chronology, exact-count/final-context binding, invalidation/reconstruction, and
Tool-capability-change decisions to the gate.

The focused
[Pi capability reuse audit](../research/pi-context-capability-reuse-audit-2026-07-22.md)
closes the ownership direction: Pi retains the final `AgentContext`, Session
history selection, Tool transport, Provider canonicalization/digests and exact
count. Workspace adds one private
[Run Context Preparation](workspace-run-context-preparation-v1-contract.md)
Module that produces one ephemeral CTI data envelope and one non-content
binding. The seven items are currently needed logical inputs, not seven
Provider channels and not a fixed framework count.

[`workspace-runtime-composition/v1`](workspace-runtime-composition-v1-contract.md)
now has **Design PASS** and corrects the earlier conflation: Pi Session is
durable and reopenable; AgentHarness is non-durable, reconstructed once per
successful Workspace `open`, reused by that Workspace's prompts, and discarded
after close/lease release. Session lifetime is not a remaining PNW-B design
problem. The context hook can append the transient envelope after selected
history and before the current Harness prompt without guessing a message
boundary. Run Context Preparation now has **Design PASS**: its application
authority copies Pi's actual safe prepared digests into the Workspace binding,
joins them to Task/Case/Memory evidence, revalidates after artifact creation,
and does not independently canonicalize Provider input. The placement tracer is
required implementation evidence. Implementation readiness remains FAIL on
prerequisite delivery and the active Workspace kill-switch checkpoint.

Case persistence is now explicit in the candidate
[Case Persistence v1 contract](../case-management/case-persistence-v1-contract.md).
The recommended first deployment is a storage-independent Case Management
Module with an in-memory acceptance Adapter and SQLite local/single-host
Adapter. Context Assembly only reads an exact Case revision and writes zero;
settled model memory can change Case only after Case Management accepts a
transition. No vector store is required. Its Design Gate remains FAIL because
there is no Case Management code route, the first Case State profile is not
frozen, and the pinned Node 24.14 SQLite driver/runtime choice is unqualified.

## Agent Memory Management redesign: consensus reset

The earlier owner-local Memory conclusion is superseded by
[ADR 0021](../adr/0021-make-memory-management-a-first-class-agent-module.md).
The project now treats Memory Management as a required first-class Agent
capability alongside Runtime/Harness, State/Session, Tools/Capabilities and
Validation/Evidence. The previous `workspace-memory-coordination/v1` document
is historical design input, not the current top-level Memory authority.

The new design must start from the complete Memory capability rather than from
the current scattered owner records. Its durable foundation includes Semantic
Memory, Episodic Memory, Procedural Memory, retrieval gating,
consolidation, candidate admission, persistence, retrieval, update, conflict,
correction, invalidation, deletion and evaluation. Session, Case, Workspace and
I&E are explicit business Adapters and sources; they do not replace the Memory
Module. Context Assembly is reconstructed for a Provider use and may consume
qualified durable Memory contributions, but is not a durable category or Memory
Entry.

The current status is **redesign in progress; implementation not authorized**.
Two independent design/research tracks are active: a complete Memory Module
and implementation proposal, and a full Agent end-to-end validation study
covering deterministic evaluation, LLM-as-judge, trajectory/tool evaluation,
memory correctness, security gates and release criteria. No implementation PASS
or end-to-end PASS is inferred from the existing documents.

Both tracks have now returned. Their outputs are recorded as the [Agent Memory
Management v1 Contract](agent-memory-management-v1-contract.md), defining the
`prepare` / `revalidate` / `admit` / `manage` seam, typed candidate/entry
lifecycles, owner references, scoped retrieval, versioning, correction,
deletion, adapters, and failure behavior; and [CTI Agent E2E Validation
Research](../research/cti-agent-e2e-validation-2026-07-26.md), defining the L0-L4
oracle hierarchy, the limited role of LLM-as-judge, deterministic and
trajectory checks, Memory negative cases, traces, datasets, and release gates.

The Waku primary-source check is recorded in
[Waku Agent: runtime context and durable memory boundary](../research/waku-agent-context-and-durable-memory-2026-07-27.md).
It supports only the runtime-context versus durable-memory boundary. The
candidate contract maps that boundary to Pi Session/Harness, Workspace Context
Preparation and Provider Dispatch, and records the present Interface/Adapter
sharing conditions. The project deliberately does not introduce `Working
Memory` as a term.

The active candidate now limits the first Memory release to exact-reference
qualification: `prepare` accepts an ordered explicit selection and never
discovers, ranks or substitutes Memory. It closes the `prepare` / `revalidate`
/ `admit` / `manage` lifecycle; Candidate, Entry, Revision, Operation, Source
and Use identities; source-proof union; correction/deletion/replay closure; and
the AM-01 through AM-23 deterministic acceptance catalogue. General retrieval,
candidate-information location, ranking, reranking and SearchIndex design are
explicitly deferred to the separate discussion rather than being inferred from
this contract.

The first accepted profile selects SQLite as the local-host authoritative
Memory Store and Git-backed Markdown as the user-editable source surface. Git
commits are verified source inputs, never a second Memory store or a target for
Memory writes. The actual SQLite driver/runtime remains unqualified: it must
publish its deployment, writer, acknowledgement, CAS, recovery, purge and
retention profile and pass SP-01 through SP-06 against AM-01 through AM-23.
The existing `sql.js` probe and Waku's `state.db` remain reference evidence,
not qualification evidence.

The immediate cross-cutting implementation risk identified by validation
research is that a `beforeToolCall` hook may mutate parameters after initial
validation. CTI side-effecting tools must freeze or revalidate final parameters
and bind the actual executed parameters to the receipt.

The next Memory contract must define the public deep-module seam, typed memory
records, scope and provenance binding, lifecycle state, Adapter Interfaces,
failure closure and the complete context/settlement path. The next validation
contract must define the executable evidence chain from task intake through
Run, Tools, Session, Memory, Case/I&E context, Provider input, output
publication and Memory mutation.

PNW-B composition is no longer a Memory design blocker, but its current
implementation and the Workspace integration remain separately gated.

Post-context design-gap ledger, in required order:

1. **PNW-B Workspace runtime composition — Design PASS, implementation NO:**
   exact acquisition, Harness reconstruction, reuse, close/release, lease-loss
   and staging-path deletion behavior is frozen.
2. **PNW-C Run Context Preparation — Design PASS, implementation NO:** the
   Workspace-evidence-to-Provider-artifact authority mapping and public failure
   closure are frozen; prerequisites and current Workspace kill-switch state
   still block implementation dispatch.
3. **First no-tool Run integration — partial design:** Run Control schemas are
   accepted, but the concrete Workspace Adapter from committed handoff + initial
   context + Harness run identity into the first no-tool Run is not frozen as an
   implementation task.
4. **Later in-Run planning — explicit gap:** the Pi-native carrier for
   subquestion, Query Candidate, and capability proposals remains
   implementation-gated; it is not needed by the first no-tool vertical.
5. **PNW-D context memory — blocking for compaction/tree:** the owner-qualified
   provider policy exists, but exact Workspace compaction/branch-summary input,
   summary receipt, generation rebinding, and public recovery matrix are not
   frozen.
6. **Output publication integration — gated:** the publication business schema
   is accepted, but the exact response-candidate settlement proof, completed
   public result replacement, and receipt-aware later-context projection seam
   still require their integration gate.
7. **Optional historical recall — deferred:** same-Case Artifact discovery and
   adoption has no normative owner-local Interface yet; cross-Case experience
   and user/team preferences have no accepted owner. Neither blocks mandatory
   initial context reconstruction.

Working Set population, product Tool activation, I&E consumption, Artifact
persistence, Assessment, Case writes, real Provider activation, and live
OpenCTI remain deferred exactly as before.

## Task Understanding / exact count: focused implementation/public-seam PASS

`pre-investigation-task-understanding/v1` now has independent **focused implementation/public-seam PASS** through the existing `CaseWorkspaceModule -> CaseWorkspace.prompt -> WorkspaceTurn` seam. Under Node `v24.14.0`, the Task Understanding file passes **42/42**, including TU-22 **3/3** public exact-count scenarios; the related non-live Workspace files pass **55/55**. Continuity receipt/actor/purpose/branch/context-generation hardening remains covered.

The generic Pi prepared exact-input-counter/A3.2 seam retains independent **focused implementation/public-seam PASS**. Current combined acceptance passes AI exact/related **46/46** and Agent Provider Dispatch/Session related **147/147**. The final root `npm run check` passed all gates, including Biome over **820 files**, TypeScript, and browser smoke.

The Workspace character heuristic is removed. TU now pre-binds only `modelRef`, a snapshotted counter/tokenizer/wrapper configuration identity, and the deterministic minimum-output-probe digest; it uses A3.2 `exact_required`, validates sealed non-secret actual model/counter/count/logical/budget/receipt evidence before semantic admission, and maps every exact-count unavailable/mismatch/over-limit class to `input_budget_exceeded` with zero Provider start and zero TU decision write. Public tests cover at-limit input/output, tokenizer-vs-character discrepancy, output one-over, counter failures, all identity/version mismatches, evidence drift/result mutation, and configuration-dependent expectation/logical digests. One shared Provider lifecycle remains in use. **PNW-C Integration PASS: NO. Integrated PASS: NO.** Real-provider counter registration/activation and all I&E, Working Set, Artifact, Assessment, Case-write, and live OpenCTI scope remain deferred.

## PNW-E crash recovery: Design PASS, focused implementation/public-seam PASS

The frozen ordinary-settlement repair is implemented in `packages/agent` without a new public Harness-to-Repository seam. Repository-created Memory and JSONL Sessions privately publish the complete existing settlement/A4 evidence under the exact six-field logical key: durable `prepared` journal before sealed A4 commit, no-replace final publication after committed or authoritative exact-present knowledge, then cleanup tombstone before exact prepared removal. Recovery validates the physical journal/final/tombstone/source and repeats exact A4 lookup before application validation; copied public terminal data with no exact sidecar fails closed. Terra's independent acceptance returned **focused implementation/public-seam PASS**. Node `v24.14.0` acceptance passed the fixed recovery file **7/7** and the related seven files **93/93**; the developer root check passed over **817 files**. PNW-E remains **Integrated NO** and does not complete the Workspace vertical.

Readiness found that accepted A5 deliberately has no TTL, PID-liveness test, stale-claim deletion, or crash takeover, while the prior PNW-E migration line and recovery table did not define a public recovery Interface, explicit orphan-claim authority, physical JSONL classifier, atomic recovery-discard transition, or idempotent closed outcomes. Terra's first PNW-E delta found three blockers. Lifecycle sections 5.1/6.10 repaired them with complete constructor-owned recovery application callbacks and recovery-discard schema; one Pi-owned durable final-Run marker in A1's receipt-last atomic group; and a repository-owned no-replace recovery-owner/commit journal with fixed crash cutpoints and roll-forward semantics rather than a false multi-file atomicity claim. Independent Terra delta review returned **Design PASS**. Developer TDD reached **7/7** in the fixed public recovery file; the A1/A4/A5/A6/settlement-related set passed **93/93** across seven files; and the explicit Node `v24.14.0` root check passed over **816 files**. A targeted blocker repair then added Memory recovery parity, physical JSONL integrity checks before application callbacks, transaction-scoped committed records, and journaled A4 evidence with authoritative lookup. The final ordinary-settlement sidecar/crash-recovery delta subsequently received Terra's independent **focused implementation/public-seam PASS** with the current evidence recorded above. PNW-E remains **Integrated NO**, A5's ordinary acquisition behavior remains unchanged, and no Workspace vertical is complete.

Updated: 2026-07-22

`PROGRESS.md` records delivery state only. Exact behavior belongs to the owning contract, architectural relationships to the [overview](context-projection-design.md), terms to `CONTEXT.md`, decisions to ADRs, and external evidence to research. Documentation precedence is in [`docs/cti-rag/README.md`](../README.md).

## Design and focused implementation/public-seam PASS: PNW-A6 AgentHarness run-generation fencing

Independent Terra review returned Design PASS for the frozen sections 6.3/6.9 amendment and focused implementation/public-seam PASS for A6. Under explicit Node `v24.14.0`, Terra's six-file acceptance passed **147/147** tests, including the exactly six public `AgentHarness` run-generation scenarios. The developer root check passed over **815 files**. The accepted implementation provides opt-in generation ownership, bounded local retirement/detachment, private `agent_end` buffering, winner-only sink fences, immutable shared completion/retirement claim, settlement ordering, actual Session append-boundary admission through the existing lease mutation queue, and next-Run admission while ignored work remains resident. The accepted order is `save point -> settlement -> publish buffered agent_end -> idle -> settled -> resolve`; the ordinary opt-out path remains unchanged. A6 remains **Integrated NO**: it does not deliver crash recovery, Pi-native Workspace implementation or migration, I&E, retry, provider-stream resume, or real-provider activation.

## Design accepted: Task Understanding, Run Control, and Output Publication

The 2026-07-21 Workspace design cycle independently accepted three active contracts after repeated cross-review FAIL/repair rounds:

- [`pre-investigation-task-understanding/v1`](pre-investigation-task-understanding-v1-contract.md): immutable Original User Task, zero-or-one bounded pre-run invocation, deterministic continuity/admission/clarification/failure, 1–4 source-bound outcomes, atomic A4 committed handoff, and no Harness, Session creation, Tool loop, retry Agent, or second Agent;
- [`investigation-run-control/v1`](investigation-run-control-v1-contract.md): multi-goal Run seeds, flat bounded subquestions, literal target-neutral Query Candidates, append-only local adjustment, capability admission, model-turn/tool/token/time/cost budgets, and closed Run settlement dispositions without a general DAG or sub-Agent system;
- [`workspace-output-publication/v1`](workspace-output-publication-v1-contract.md): private Model Response Candidate, deterministic publish-or-withhold decision, zero content-bearing public delta before the gate, exact Run/Session/context/Orientation/citation/authorization validation, durable non-authoritative Published Workspace Output, and no default Artifact.

The generic `PiAgentRunSettlementEvidenceV1` shape previously passed independent design acceptance. Lifecycle section 5.1 now adds an unreviewed Interface amendment for application terminal construction, Harness invocation/result observation, A1 final-save-point evidence, resident Run identity, and A4 knowledge outcomes. Its first repair removes unreachable public duplicate/identity-conflict cases in favor of a real `promptWithSettlement`/`abort` race and freezes one final-save-point terminal-claim cutpoint across every settlement await. A second minimal repair references the existing asynchronous `abort(): Promise<AbortResult>` Interface exactly, including its synchronous signal prefix and awaited idle/result behavior; it adds no cancellation method. Pi still owns one terminal-only A4 settlement group and integrity evidence; Workspace owns the authenticated terminal meaning; Publication consumes both without redefining either schema.

TU, Run Control, Publication, and the amended settlement Interface have **design PASS**. Agent Run settlement now also has **independent focused implementation/public-seam PASS**. Node `v24.14.0` settlement acceptance passed **7/7**; Terra's direct A1/A4 regressions passed **65/65**; and the developer root check passed over **811 files** with no fixes. Settlement remains **Integrated NO**: this acceptance delivers neither A5 cross-process fencing nor A6 bounded retirement/late-sink fencing, and it does not deliver Pi-native Workspace migration. The current Workspace package still uses the delivered per-Turn staging Session/Harness and still exposes the historical raw-delta behavior. Workspace implementation remains NO-GO until the reopened shared Provider Dispatch design, remaining PNW run-generation/repository/context/public-result amendments, and each contract's focused public-seam gate are independently accepted. I&E, Working Set, Artifact persistence, Assessment, Case writes, live OpenCTI, and real Provider activation remain out of scope.

## Delivered: Orientation foundation

The first implementation cycle passed independent acceptance. It establishes the private [`@earendil-works/pi-cti-rag-agent-workspace`](../../../packages/cti-rag-agent-workspace/package.json) package and the real `CaseWorkspace` seam without starting the later I&E or strict-R1 work.

Delivered scope:

- public construction through `createCaseWorkspaceModule`, with `open`, `prompt`, streamed `WorkspaceTurn` events, cancellation, terminal result, and `close`;
- `open` as the linearization point: both Orientation observations are obtained, closed-schema validated, normalized, compared, materialized, and validated again before a Workspace can be returned;
- ephemeral Orientation injection through the real Pi Harness rather than persistence as ordinary Session authority;
- two closed Orientation JSON Schemas loaded by the validator, JCS-compatible canonical hashing with UTF-16 property ordering, and safe rejection of invalid JSON-domain input;
- a production-shaped `OrientationReadPort` seam and a package testing export containing the in-memory Adapter;
- T1–T5 acceptance groups covering seven tests: successful open/prompt, unusable pagination, authorization revocation, partial-stream cancellation, and three hostile schema/JSON-domain cases.

Independent validation passed on Node 24.14. Root `npm run check` also passed over 783 files with no fixes, including pinned dependencies, TypeScript import rules, shrinkwrap/install-lock checks, types, and browser smoke.

### Acceptance boundary

The foundation checkpoint covered only the OR behaviors exercised by the accepted T1–T5 tests. It did **not** claim that OR-01 through OR-30 were complete. At that checkpoint, late response fencing, dirty/full reopen, stale Session treatment, and production/in-memory conformance remained open; Slice 0b below records their later delivery evidence.

Exact executable baseline retained from the last independent acceptance:

| Group | Executable behavior | Test count |
|---|---|---:|
| T1 | complete Orientation opens and binds ephemerally to one real Pi prompt | 1 |
| T2 | two incomplete selected traversals reject before a provider request | 1 |
| T3 | authorization revocation between pages rejects without protected task disclosure | 1 |
| T4 | cancellation after a partial model stream leaves the next Turn clean | 1 |
| T5 | unknown member, lone surrogate, and non-finite number each reject before publication | 3 |

These seven tests are the baseline evidence only. They are not evidence for the new Slice 0b catalog below.

## Delivered: Orientation Slice 0b

The owning [Orientation contract](opencti-case-orientation-v1-contract.md) closes the required late/out-of-order isolation, stale Session containment, dirty/full reopen, and shared Adapter conformance behavior. [ADR 0011](../adr/0011-contain-stale-session-prose-with-dependency-receipts.md) records the durable stale-Session decision. After the prior independent FAIL, the integrated repair added expected-head atomic Session completion, HMAC-authenticated receipts and exclusion markers, dependency-scoped Session projection, sticky append-order exclusion across binding reversion, and a final root probe. A different Agent then independently accepted the repaired public seam with no blocking issue.

Delivered scope remains limited to the read lifecycle:

1. deepen `CaseWorkspace` behind the `open/prompt/close` Interface with stable Turn identity, private staging, one terminal result, response fencing, and an optional closed Orientation block dependency declaration on `prompt`;
2. reconstruct Orientation by complete double observation at each open/reopen and contain dirty or unknown recovery evidence;
3. qualify caller-Session model entry by HMAC-authenticated dependency receipts, expected-head atomic append groups, and dependency-subset projection while retaining authorized audit history;
4. run one closed semantic fixture catalog against the in-memory and transport-backed production-shaped Adapters through the public Workspace seam.

No item above fixes the number, names, or decomposition of model-visible LLM tools.

### Independent acceptance evidence

| Risk area | Normative IDs | Accepted evidence |
|---|---|---|
| Late/out-of-order response isolation | OR0B-LR-01–OR0B-LR-09 | accepted through the public Turn seam: cancel/close/supersede, late success/error, terminal uniqueness and ordering, Session-head and completion-commit races, and old-success/new-failure reopen ordering |
| Stale Session containment | OR0B-SS-01–OR0B-SS-07 | accepted through actual model contexts and retained Session evidence: drift/revocation/partial/legacy exclusion, same-Workspace dependency-disjoint chains, authenticated receipt/marker attacks, branch and compaction ancestry, and `A -> B -> A` non-revival |
| Dirty/full Orientation reopen | OR0B-RO-01–OR0B-RO-08 | accepted for clean/full reopen, zero/one/two-message incomplete atomic prefixes, corrupt provenance, invalidation during reopen, ignored cancellation, and staging-only initial open/materialization |
| Adapter conformance | OR0B-AD-01–OR0B-AD-13 | accepted using the shared six-case semantic catalog plus pagination/schema/reopen paths, start/final root probes, and transport ignored-abort containment |
| Public Interface and dependency scope | OR0B-IF-01–OR0B-IF-03 | accepted from `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn`; dependency declarations scope rendering, eligible history, receipts, and exclusion without a Workspace-wide freeze |

Independent validation used explicit Node `v24.14.0`. The four public-seam CTI files passed 55/55 (`case-workspace` 7, `orientation-lifecycle` 11, `orientation-reopen` 23, `adapter-conformance` 14); the focused Pi Session file passed 30/30; and the offline live-Orientation file passed 31/31. These are 116/116 unique focused tests. Root `npm run check` passed over 798 files with no fixes. A separate public-seam `A -> B -> A` probe also passed: three model contexts were observed, and the returned-A context contained only the actor-safe stale capsule, not the pre-marker `OLD_A_TASK` or `OLD_A_RESPONSE`.

Normal, clean-reopen, and returned-A Turns each emitted `turn_started -> context_bound -> model_started -> model_text_delta -> turn_completed`, with sequence `1..5`, stable identities, and one terminal. Partial cancellation ended in `turn_cancelled`; provider-pending cancel, close, and supersede ended in their one cancelled/discarded terminal; close during reopen emitted `turn_started -> turn_discarded`; and model error, post-response invalidation, and Session-head conflict each emitted one failed/discarded terminal. The completion-claim-before-close race committed the complete four-entry Session group before close settled. Partial, stale, unknown, and unauthorized content remained outside the current model context and Artifact path.

This executable evidence is not a claim that OR-01 through OR-30 are all complete. OR-25 and OR-26 remain explicitly deferred because executing them would introduce the frozen write compiler and remote-effect recipe platform; the prohibition against using Orientation as a write basis remains normative. The Session atomicity claim is local to one storage instance, not a cross-process lock or Durable Operation Journal.

### Live OpenCTI diagnostic vertical observed on one real Case

A Node-only live vertical now exists behind the unchanged public Workspace Interface. It includes fixed OpenCTI GraphQL documents, bearer-token isolation, `me` actor derivation, target/version/selected-schema preflight, closed DTO mapping, start/end root probes, exhaustive Task and Case-object pagination, request/response budgets, a supported HMAC Session receipt authenticator, a JSONL close-to-reopen composition, and a thin actor-safe CLI. The [operator runbook](opencti-live-smoke.md) owns the command and evidence boundary.

Offline developer evidence includes 31 focused tests through the public Workspace seam and thin Node entry. In addition to the prior cases, a deployed OpenCTI limit is executable: every selected-schema introspection operation contains at most two `__type` calls, expected aliases are closed-merged, and recursive TypeRef validation remains unchanged. The new case failed before implementation and passed after deterministic batching. The existing coverage includes multi-page and actor-visible empty traversal, GraphQL errors with partial data, HTTP 401/403, non-JSON responses, token-subject and page-authorization drift, malformed DTOs, repeated cursors, final-root and double-observation drift, request and response-body timeout with ignored abort, streaming byte-budget enforcement, missing or incompatible recursive TypeRef qualification proof including nested selected-field nullability, union/inline-fragment runtime-overlap proof, stable endpoint/actor/credential-slot binding, 32-byte HMAC enforcement, secret redaction, mechanical validation of the actual model Orientation envelope and its digests, JSONL close-to-reopen rereads, changed receipt-key rejection, unique terminals, CLI configuration safety, and discoverable Session paths on success and post-creation failure. At that earlier diagnostic checkpoint, the live-focused file passed 31/31, the then-current four CTI behavior files passed 49/49, and root `npm run check` passed over 798 files with no fixes under Node 24.14. Final independent counts are recorded above. The opt-in live Vitest wrapper remained skipped; the successful CLI run is the live evidence.

The CLI smoke has now called one local OpenCTI `7.260715.0` deployment through verified HTTPS and the faux provider. It opened Case Incident `d2d9f2a7-abf2-4f70-9c06-dff8cc26d031`, whose public OpenCTI reads proved one linked Task and one linked imported ATT&CK object (`T1566.001`). Initial and JSONL reopen each produced the closed event sequence ending in exactly one `turn_completed`; both actual faux-model contexts returned `validated=true`, and the equal reconstructed Orientation semantic digest was `sha256:78e1507c32a505f3546c83f2aa3eda391b6485440902b9c8106065e026d49a5f`. The opt-in live Vitest wrapper was not run; the CLI exercised the same `runOpenCtiCaseSmoke` function. Exact deployment and import evidence is in [the real-Case smoke research note](../research/opencti-real-case-live-orientation-smoke-2026-07-20.md).

This is diagnostic evidence for one endpoint, actor, Case, and time, not production qualification. Controlled marking and Authorized Members transitions, hidden-membership races, schema upgrades, cross-process Session concurrency, and a real model provider remain outside the claim. The MITRE import completed with six known `revoked-by` relationship losses after OpenCTI deduplication collapsed distinct intrusion-set source identities; the frontend also could not render the statement-marking Workbench detail. Neither issue was hidden by the smoke. This diagnostic evidence remains separate from, and did not substitute for, the independent Slice 0b acceptance above.

### Slice 0b delivery gate

- Independent public-seam acceptance: PASS, with no blocking or non-blocking product issue.
- Focused verification: 116/116 unique tests under Node 24.14; root check passed over 798 files with no fixes.
- Content isolation: partial, stale, unknown, and unauthorized bodies did not reach current model context or Artifact state.
- Dependency locality: intersecting chains failed closed while dependency-disjoint history remained eligible.

## Current

PNW-A5 has independent **Design PASS** and final Terra **focused implementation/public-seam PASS**. Explicit Node `v24.14.0` acceptance passed the fixed public-seam file **8/8** and the related Session/A4/repository set **70/70**. The developer root check passed Biome over **814 files**, dependency/lock checks, TypeScript, and browser smoke. The accepted repair closes every current public Session writer, serializes lease-local writes/A4 commit against release with first-claim-wins ordering, and denies legacy raw-repository containment into `.leased`. The accepted implementation adds closed JSON/IPC opaque refs, Memory shared-catalog and JSONL private digest-catalog repositories, atomic filesystem exclusive-create, guarded Session/A4 authority, release/generation fencing, independent-instance and real-child-process single-writer exclusion, and explicit-release authoritative reopen. A5 remains **Integrated NO**: it does not deliver TTL, renewal, crash takeover, A6, Workspace integration, or provider behavior.

The serializable opaque-ref repair received independent Terra **Design PASS**. Focused A5 implementation is now in progress under the fixed public `provision/acquire -> SessionLease` seam; no implementation/public-seam acceptance is claimed yet.

The A5 issuance re-review found one transport contradiction: the first candidate represented the opaque ref as a process-local symbol-branded value while acceptance requires two real child processes to acquire the same Session. The docs-only repair now freezes a repository-issued, unguessable closed JSON/IPC capability value (`protocol` plus a 256-bit unpadded-base64url bearer token). Opaque now means retain/transmit unchanged without parsing, construction, derivation, or logging; it does not mean non-serializable. Repository-owned syntax validation plus private authenticity/catalog lookup resolves it without exposing metadata or paths. Child competition receives the same ref only through controlled IPC/stdin, never argv, environment, filenames, or logs. This repair awaits independent Terra re-verification; no code or test changed and A5 implementation remains stopped.

A5 implementation exposed one issuance gap after Design PASS and stopped before code or tests. The minimal docs-only repair now freezes one deep `provision(options) -> { sessionRef, lease }` operation: first creation returns only an opaque repository-issued ref plus an already-active guarded lease; later access uses `acquire(ref)`. Memory and JSONL share the same `SessionError` failure behavior and all-or-none provisioning guarantee. Existing raw `SessionRepo.create/open/list/delete/fork` is explicitly legacy/migration-only, cannot address the provisioned namespace, and cannot bypass a lease. Tests must obtain refs through `provision` with no registration or metadata-conversion helper. This repair awaits independent Terra re-review; implementation remains stopped and has no implementation/public-seam acceptance.

PNW-A5 readiness on 2026-07-22 found that the lifecycle contract named repository leasing but did not close acquisition failures, opaque-reference authority, token/generation ownership, release/loss guards, raw Session/storage bypass prevention, or Memory/JSONL multi-instance and cross-process behavior. A docs-only candidate `SessionRepository.acquire(opaqueRef) -> SessionLease` contract now owns those semantics and the focused acceptance seam. Terra then identified one remaining design blocker: the production JSONL claim depended on an unnamed atomic exclusive-create primitive absent from `FileSystem`. The minimal docs-only repair added a generic `createFileExclusive(path, content)` capability with closed `created | already_exists | unavailable` outcomes, assigned production conformance to `NodeExecutionEnv` and structural-fake conformance to their owning tests, forbade `exists + write`, and made the complete exclusively published record the sole live-ownership authority. Independent Terra re-review returned **Design PASS**; focused A5 implementation is now in progress and has no implementation/public-seam acceptance yet.

The three-option architecture grill converged on the Pi-native Workspace: retain the delivered per-Turn staging path only as a migration rollback until its replacement passes, reject a permanent Workspace-owned transaction/lifecycle layer, and deepen Pi so one durable leased Session plus one Workspace-lifetime Harness remain the sole execution spine. [ADR 0015](../adr/0015-use-session-authority-and-pre-dispatch-proof-for-workspace-capabilities.md) records Session authority for small v1 Workspace state and pre-invocation proof over Pi's logical provider invocation artifact.

The first independent architecture review result on 2026-07-21 was **FAIL** with five blocking findings: Query Candidates were not structurally target-neutral; Working Set schemas/atomic ownership were incomplete and conflicted with the overview; provider proof incorrectly claimed transport bytes instead of the `packages/agent` logical invocation; a mandatory whole-input envelope/365-day retention profile lacked owner authority; and the I&E development gate had an unsafe early exception. The first repair revised all five.

The second independent review also returned **FAIL**, with three blockers: the I&E Platform Design still contradicted the Workspace owner on exact provider-input bytes/reconstructable envelope/365-day provider replay and its design-readiness PASS could be mistaken for activation; the agent-owned logical invocation projection did not close real Harness stream fields, nested mutation, auth/header identity, payload callbacks, canonicalization, receipt matching, or permit consumption; and PNW/IWS acceptance omitted those behaviors. The second repair gave the Workspace contract explicit priority, closed the preparation/projection/commit Interface against the real Harness/provider path, and added public-seam/focused Pi acceptance.

The third independent review returned **FAIL** with two remaining blockers: `CanonicalModelIdentityV1` invented a nonexistent registry field instead of binding the actual resolved `requestModel`, and the header projection incorrectly collapsed model/auth/options headers into one cross-layer collection even though `Models.applyAuth` leaves `requestModel.headers` separate and only combines auth then explicit `requestOptions.headers`. The third repair removed every registry requirement, bound every current resolved `Model` field, rejected future unknown Model fields, and modeled the two real header layers with value-versus-null-suppression tagged unions, exact domain/length-prefixed HMAC bindings, within-layer collision rejection, auth/explicit override behavior, and separately snapshotted API-key/environment/base-URL/auth bindings.

The fourth independent design review returned **PASS**. Its read-only focused baseline passed **107/107**. That checkpoint accepted the revised Workspace design and authorized only starting PNW-A; it was not Pi-native implementation evidence, a prototype, or authorization to activate I&E, Working Set, or real-provider disclosure. PNW-A1 implementation and acceptance occurred afterward as recorded below.

PNW-A1 then implemented only the generic opt-in transactional no-tool save point in `packages/agent`. Its first independent implementation review returned **FAIL** with three blockers: the Session leaf had to be captured before context/system-prompt construction so the context basis and commit CAS could not diverge; tool-use rollback had to stop the Pi turn without a follow-on provider request; and a post-commit `save_point` observer failure had to preserve the committed group, settle the Harness, and reject only after settlement rather than attempting rollback or failure-transcript persistence. The repair closed all three and the same independent reviewer returned **PASS**.

The accepted A1 boundary is exact: user/assistant turn entries remain pending and unmaterialized through `turn_end`; policy receives a read-only pending view; admitted application custom entries precede one required physically last terminal receipt; one `appendBatchIfLeaf` call owns expected-leaf CAS and materialization; explicit rollback, policy failure, provider error/abort, and CAS conflict append none of the staged group; tool use is blocked at `beforeToolCall`, rolls back, and uses Pi turn-stop; transactional `save_point` observation occurs only after commit/rollback; post-commit observer failure cannot undo committed state; the captured pre-context leaf binds the context basis; and the default non-transactional path remains unchanged. Raw Session writes and legacy configuration pending writes remain outside this narrow group.

Independent verification used explicit Node `v24.14.0`: three focused files passed **55/55**. The developer root `npm run check` passed over **799 files** with no fixes. These counts prove only PNW-A1's transactional no-tool boundary and the retained focused baseline.

PNW-A2.1 then added only the ordered restricted Session facade and the transactional model/thinking/active-tools configuration subset in `packages/agent`. Its first independent implementation review returned **FAIL** with two blockers: nested caller aliases still reached staged application entries, policy output, terminal receipts, and Model state; and the public TSDoc overstated which configuration and recovery behaviors the slice delivered. The repair introduced recursive ownership snapshots and fail-closed validation at every ownership transfer, isolated staged Model values across durable/runtime/getter/event/hook/provider paths, and narrowed the public documentation to the implemented subset. The same independent reviewer then returned **PASS**.

The accepted A2.1 boundary is exact: `HarnessSessionFacade` exposes only committed deep snapshots and source-ordered custom enqueue during an open transaction; turn, application, configuration, and terminal-receipt entries retain physical source order and materialized ordinal/id evidence; policy inputs, decisions, receipts, custom data, and staged Models are recursively isolated from later caller mutation; unsupported values fail before commit; and model, thinking level, and active tools become durably and in-memory visible only after the receipt-last CAS. Rollback, policy/signing failure, conflict, blocked tool attempt, abort, late mutation, and unsupported data leak none of that staged state. Post-commit observer failure preserves both Session and in-memory configuration and still settles once. Memory and JSONL reopen reconstruct only the committed `Session.buildContext()` model/thinking/active-tool projection; constructing or restoring a new Harness remains application-owned.

Independent A2.1 verification used explicit Node `v24.14.0`: five focused files passed **84/84** (`agent-harness-transaction` 25, `agent-harness-save-point` 12, `agent-harness` 13, `agent-harness-stream` 4, and Session memory/JSONL 30). The developer root `npm run check` passed over **800 files**. These counts prove only PNW-A1 plus the A2.1 subset; they do not prove full PNW-A2 or any later lifecycle slice.

PNW-A2.2 then added only the persisted-entry context-policy subset in `packages/agent`. The opt-in policy receives coherent isolated committed Session evidence for `provider`, `compaction`, and `branch_summary`, may admit only a source-ordered subset of Pi's default selection, and retains append-order evidence needed to observe off-branch invalidation. Denial, unsupported data, cancellation, leaf drift, or changed selection fails closed before the selected entries are used. Provider qualification is rechecked after context/system-prompt and pre-provider policy work; compaction and branch-summary qualification are rechecked after model work and before structural mutation. Policy state and sensitive Harness configuration are not persisted, and the legacy path remains unchanged when the policy is absent.

The first independent A2.2 review returned **FAIL** because post-model policy drift could reach structural use. The TDD repair closed that path, and the original independent reviewer then returned **PASS** with no blocker. Explicit Node `v24.14.0` verification passed seven focused files and **132/132** tests; the developer root `npm run check` passed over **802 files**. This evidence proves only the persisted-entry policy subset. It does not deliver full PNW-A2, application CTI eligibility semantics, or any A3-A6 capability.

PNW-A3.1 then delivered only the AI-owned auth-resolved deferred-start preparation seam in `packages/ai`. The accepted implementation adds `Models.prepareSimple(...)`, which captures one Provider and one auth resolution, retains detached resolved request-model/context/request-options views, preserves the explicit `AbortSignal` and callback capability references, defers Provider Adapter and lazy API entry until one single-use `start()`, isolates later caller mutation, and keeps legacy `streamSimple()` synchronous with its auth/lazy/error/payload-hook behavior. Preparation rejects before Adapter work on invalid ownership data or auth failure; start-time synchronous and lazy failures remain standard error streams.

The later A3.1 tool-projection audit found that structural runtime tool subtype fields could cross the public provider Tool seam. The TDD repair projected only `name`, `description`, and `parameters` while retaining valid schema metadata: its focused tracer ran RED **1/10** to GREEN **11/11**. Explicit Node `v24.14.0` verification passed **44/44** across five focused AI files (`models-prepared-stream`, `models-runtime`, `lazy-module-load`, `oauth-auth`, and `env-api-keys`); independent acceptance passed eight focused files and **81/81** tests; and the developer root `npm run check` passed over **802 files**. This evidence proves only the `packages/ai` preparation seam. It adds no Session receipt, HMAC or canonical logical-invocation artifact, permit, dispatch commit/lookup, current-generation retirement, protected Harness path, or A3.2 behavior; it is not full PNW-A3, full PNW-A, or a Pi-native Workspace prototype.

The first and second independent A3.2 reviews returned **FAIL** on transaction/application/secret/ownership/schema closure and then exact bytes, once-only identity, closed knowledge outcomes, staged budgets, and executable A4 semantics. The third combined A3.2/A4 review also returned **FAIL** on shared canonical ownership, exact bytes, token ownership, authoritative absence, A4 state closure, and storage scope. The separately completed fourth A3.2 independent design review returned **PASS**. The fourth A4 review rejected same-batch leaf targets. The fifth A4 re-review returned **FAIL** on one remaining closed-result gap: when the private capability existed but prepare's authoritative read/parse/version validation failed, `prepareControlBatch` could neither return a legal result nor throw/misclassify safely. The sixth minimal docs-only repair added `unavailable(io|invalid_or_truncated|unsupported)` to prepare, preserved capability-missing `unsupported`, guaranteed zero reservation/append/event and no partial cache replacement, and mapped both through A3.2 as `control_unavailable`; the sixth independent A4 design re-review returned **PASS**.

PNW-A4 then implemented the generic pre-materialized Session control-batch Interface in `packages/agent`. Developer TDD ran RED **1 failing test** to GREEN **28/28**. Six focused files passed **117/117**, and the developer root check passed. The first independent implementation review returned **FAIL** because a slot-shaped business object could collide with the internal optional-slot sentinel interpretation. The TDD repair made slot normalization schema-directed and restricted it to named optional positions, so arbitrary canonical business JSON shaped like `{ presence: ... }` remains ordinary data.

Final independent implementation acceptance returned **PASS**. The focused A4 file passed **28/28**, five regression files passed **89/89**, and public probes passed **4 + 1**. The final root check passed Biome over **805 files** with no fixes. The accepted public operation order was `prepare -> preview -> sealTerminal -> commit -> lookup`: two IDs were reserved; append-call counts across prepare/seal/commit/lookup were **0/0/1/0**, with the sole append containing two entries; Session events were **0**, and provider/network calls were **0**. This evidence accepts only PNW-A4. It supplies no provider permit, application verification, Adapter start, A5 fencing, A3.2 implementation, full PNW-A3, PNW-A, or Workspace migration.

The frozen Working Set contract now records the accepted ownership correction. Its exact-resource admission, Working Set, render, and future disclosure semantics remain frozen design input, while its legacy provider `prepare/commit/lookup`, `preparedRef`, credential-revision assumptions, canonical provider schemas, Model Input Receipt shape, and related provider acceptance are explicitly reference-only/superseded by the lifecycle contract. Before future activation, its owner must replace those sections with a narrow application Adapter mapping and obtain a new independent cross-owner review. I&E's 365-day exact Source Capture/Resource Capsule/Retrieval Receipt replay-material requirement remains unchanged and does not grant complete-prompt retention.

IWS1 passed independent cross-owner design re-review after adding a trusted capability-activation snapshot, closed Resource Candidate identities, distinct admission/disclosure-validation receipt identities, closed Session/context projection digest bases, render manifests and split activation gates. This restores design acceptance only; IWS1 consumer implementation remains NO-GO behind PNW/TQ.

Implementation state: **PNW-A1, the narrower PNW-A2.1 and persisted-entry-policy PNW-A2.2 subsets, the AI-owned PNW-A3.1 preparation seam, and PNW-A4 are delivered and independently accepted; the remainder of PNW-A2, PNW-A3, PNW-A5, and PNW-A6 remain NO-GO**. PNW-A overall is incomplete. A2.1/A2.2 do not deliver transactional tool execution/results, tool-registry/resources/stream-options/system-prompt configuration, application CTI eligibility semantics, Agent Run settlement, Provider Dispatch transactions, repository lease/recovery, run-generation retirement, retry transactions, or automatic Harness runtime restore. A3.1 plus A4 does not add a Session receipt/permit/canonical-dispatch authority or connect the protected dispatch seam to Harness. A3.2 remains unimplemented, paused, and NO-GO in this cycle. No Pi-native Workspace, Task Context, logical Provider Dispatch Transaction, I&E, or Working Set prototype exists in the repository; every later slice and activation remains gated by its owning focused tests, public-seam acceptance, and repository check.

A4 status is now explicitly classified as **design PASS**, **focused implementation/public-seam PASS**, and **not integrated PASS**. Integrated acceptance cannot exist before the Provider Dispatch transaction, Pi-native Workspace migration, I&E consumer, Working Set, disclosure revalidation, and composed fake-provider vertical pass through their owning public Interfaces.

The read-only Workspace/I&E RAG protocol coordination is closed. It accepts one cross-context Agent RAG capability with local Module/schema ownership; distinct Workspace Resource Candidate and I&E Retrieval Candidate authorities/namespaces; model suggestion followed by deterministic Workspace admission; I&E exact materialization before Workspace Receipt/Capsule verification and Working Set CAS; Workspace compilation of Scope/Budget and minimum-coverage policy versus I&E proof of actual Declared Retrieval Coverage/Lag/Omissions; request-local score meaning; an IWS application Adapter into Pi-owned Provider Dispatch; shared scenario identifiers without a fourth schema owner; and any legacy RAG implementation only behind an I&E-internal Adapter. [ADR 0016](../adr/0016-keep-rag-ownership-local-and-admit-retrieval-deterministically.md) records the durable ownership decision.

No general CTI investigation Agent is implemented. The repository has the delivered Orientation safety baseline and accepted generic Pi seams, but it lacks admitted Task Context execution, long-lived Workspace Session/Harness migration, CTI capability/tool admission, I&E package consumption, Working Set mutation/rendering, complete Provider Dispatch, and Assessment behavior. These missing product Modules must not be inferred from design acceptance or generic Pi tests.

The revised [Pi-native Agent Workspace Lifecycle v1](pi-native-workspace-lifecycle-v1-contract.md) remains the sole current-cycle and generic provider-proof contract. The fourth A3.2 and sixth A4 independent design reviews passed, and A4 implementation has now independently passed. PNW-A1, the A2.1/A2.2 subsets, the AI-owned A3.1 preparation seam, and A4 are delivered. A3.2 implementation remains paused and NO-GO; full PNW-A2, full PNW-A3, PNW-A overall, Workspace migration, and every later slice have not been accepted. Slice 0b remains delivered as the behavioral safety baseline, but its per-Turn staging Session/Harness is a transition implementation rather than Pi-native architecture acceptance.

The previously accepted [Task Context Understanding v1](task-context-understanding-v1-contract.md) same-Agent-Run planning design was superseded before implementation. [Pre-Investigation Task Understanding v1](pre-investigation-task-understanding-v1-contract.md) is now the independently accepted replacement design: one bounded no-tool model call occurs before any Investigation Agent Run; deterministic code admits Additional Task Context, falls back, clarifies, or fails; Query Candidates and capability/investigation planning move into the formal Run. [ADR 0017](../adr/0017-understand-the-task-before-the-investigation-agent-run.md) records the decision. Implementation remains NO-GO behind the explicit Pi and public-seam gates above.

This reopen also narrows the earlier A3.2 design PASS: it remains evidence for the Harness-only dispatch use case, but the generic Pi Provider Dispatch Implementation must now support a second bounded one-shot frontend without creating a second provider lifecycle. A3.2 requires revised independent design acceptance before implementation. A4 implementation/public-seam acceptance is unaffected.

Before this redesign, the current implementation, Orientation contract, and overview were consistent with each other: all three specified or implemented private staging for every public Turn. The implementation remains at that delivered transition mechanism; the Orientation document is now labeled as its behavioral baseline, and the overview now points to the newly adopted target. This is a deliberately reopened architecture decision, not an undocumented code deviation. [ADR 0012](../adr/0012-use-pi-harness-as-workspace-execution-spine.md) owns it.

The earlier implementation cycle stopped at the independently accepted A4 boundary. The prior settlement evidence shape had independent design PASS, but its lifecycle contract now has an unreviewed docs-only Interface amendment closing application construction, Harness invocation/result observation, A1 final-save-point evidence, resident Run identity, and A4 knowledge outcomes. That amendment must not inherit the prior PASS and remains implementation NO-GO. A3.2 also remains unimplemented, paused, and NO-GO. A later implementation cycle may deliberately resume either slice only after independent design acceptance and must obtain its own focused tests, public-seam acceptance, and root check. Remaining PNW-A work still includes transactional tool/result coverage; unsupported tool-registry/resources/stream-options/system-prompt configuration decisions; the logical Provider Dispatch Transaction; opaque-reference repository/lease; pre-provider denial; finalized tool outcomes; Agent Run settlement; and run-generation retirement. Workspace migration may rely only on independently accepted implementation boundaries and remains NO-GO.

## Next implementation cycle: Pi-native Workspace migration

Task Understanding, Run Control, and Publication retain independent design PASS. The amended generic settlement Interface and reopened shared-dispatch A3.2 design both await independent re-review. Next, independently accept those amendments and the remaining lifecycle/context/public-result amendments, then implement them with focused Pi tests before any Workspace migration. The migration replaces per-Turn staging with one durable Pi-repository-leased Session and one Workspace-lifetime Harness, proves the pre-run task/admission control group, profile-driven Run Context Preparation through Pi-owned channels, save-point/control/Run-settlement boundaries, compaction/branch context views, signed context-generation protocol, opaque public Session reference, and publication-gated output.

Workspace Retrieval/Working Set consumption and real-provider Working Set disclosure remain frozen until PNW-A through PNW-E and TU-01 through TU-15 independently pass through the public seam. Independent IER1 core-package TDD is governed by the I&E owner and may not import Workspace, call a provider, activate live OpenCTI or claim the integrated vertical. The frozen [Workspace consumer contract](intelligence-working-set-v1-contract.md) remains design input only for its non-provider Working Set semantics; its provider-proof candidate is superseded and requires a future generic Adapter mapping/re-review. Task Understanding does not produce Query Candidates, capabilities, tools, retrieval requests, Working Set state, or an investigation plan.

The next Workspace session should preserve this order: accept the reopened shared-dispatch and remaining PNW/context/public-result designs; implement and independently accept the generic Pi seams; implement Task Understanding and its atomic committed handoff; migrate to the durable leased Session plus Workspace-lifetime Harness; implement the no-tool Run settlement and publication gate; then obtain one composed fake-provider public-seam PASS. Do not enter the later IWS/I&E consumer sequence until that complete no-tool Workspace vertical passes. Bounded search remains contract-gated and must not be implemented.

## Confirmed architecture

- Pi remains the only agent/model-tool loop; `CaseWorkspace` is the deep product Module around it.
- One open Workspace targets one Pi-repository-leased Session and one long-lived AgentHarness. Pi owns the generic repository/lease, save-point/control/Run-settlement transactions, Session ordering/context views, compaction/tree, and run-generation settlement; Workspace owns CTI binding and policy at those seams.
- `prompt({ task })` remains the common Interface. The Original User Task is immutable source input; a pre-run Task Understanding Proposal is non-authoritative; deterministic code owns admission, conservative fallback, clarification, dependencies, capabilities, and budgets.
- Task Understanding owns only minimal normalization, intent/requested-outcome classification, and ambiguity. It uses one off-the-shelf structured-output model call with no fine-tuning prerequisite, Tool, Agent loop, Session, investigation plan, Query Candidate, capability need, or autonomous retry.
- The first Investigation context is logically ordered as System Instructions, Original User Task, Additional Task Context, Working Set, layered Case Context, eligible Session History, and activated Tools. Case Context always retains the Orientation safety baseline and may add a Projection overlay bound to that evidence; it is not an Orientation-or-Projection choice. A new task has an explicit empty Working Set; Tools remain provider schemas rather than prompt prose.
- Free-form investigation uses all Orientation dependencies. Only a trusted closed workflow or operation recipe may narrow them; the model never supplies dependency provenance.
- Query Candidates preserve source support and uncertainty but remain non-executable until the gated I&E cycle separately qualifies retrieval, egress, scope, coverage, and cost.
- Workspace Resource Candidate References are minted only after planning commit from current actor-visible Orientation membership; they remain separate from Query Candidate local/durable identity and from I&E Retrieval Candidate References, and only trusted recipes bind exact I&E selectors.
- A future bounded search returns only actor-safe I&E Retrieval Candidate References plus I&E-owned ranking and Declared Retrieval Coverage evidence. The model may suggest a candidate, but deterministic Workspace admission alone may trigger exact materialization; search never commits a Capsule or Working Set entry directly.
- Workspace owns trusted Scope/Budget compilation and minimum-coverage policy evaluation. I&E owns actual coverage, lag, omissions, Index Generation, Ranking Profile, and corpus ranking; raw scores are not comparable across retrieval requests or Receipts.
- Pi Session is the only v1 authority for small Working Set entry/selection/edge/receipt/outcome records, committed with source-ordered finalized tool results in one save point.
- The lifecycle contract alone owns generic provider proof. A4 prepare closes capability absence separately from authoritative-load unavailability; neither failure reserves, appends, emits, or partially replaces cache, and the future A3.2 mapping treats both as `control_unavailable`. The fourth A3.2 and sixth A4 independent design reviews passed, and A4 implementation is independently accepted. A3.2 remains unimplemented, paused, and NO-GO; no Provider Dispatch Transaction or protected Harness path is delivered.
- The delivered per-Turn staging Harness, four-entry caller-Session copy, and standalone stale-marker scan are transition mechanisms, not the target. Receipts remain; context invalidation becomes signed per-dependency generations.
- The first delivered Case read is the distinct, read-only `opencti-case-orientation/v1` Profile.
- Orientation contains only stock OpenCTI facts the qualified actor-scoped Adapter can prove. It is observation evidence, not Case business authority or a write basis.
- Full `opencti-case-projection/v1` requires the Case Management semantic overlay and one Revision Authority shared with write CAS.
- Session history, model output, Working Set material, and I&E Resources do not become Case authority through rendering or compaction.
- Authorization, partial transfer, concurrency, and late-result validation are explicit operation dependencies; failure affects only intersecting dependency chains.
- Events reduce invalidation latency but do not establish current state. The current correctness path is full Orientation reopen; closed delta semantics remain deferred until measured need.
- Product investigation-tool count remains a product decision derived from executable workflows. Pre-Investigation Task Understanding exposes no Tool and is not an I&E tool decision.

## Frozen strict-R1 target architecture

The following accepted work is preserved and intentionally not expanded during the read-only cycles:

- [`opencti-case-projection/v1`](projection-profile-v1-contract.md)
- [Case Management Facade Command and Receipt](case-management-facade-contract.md)
- [Durable Operation Journal](durable-operation-journal-contract.md)
- ADR 0007: same Revision Authority for read basis and write CAS
- ADR 0008: owned command state and OpenCTI materialization
- ADR 0009: constrained relational operation journal
- ADR 0010: operation-bound I&E Resource-use decision reservation
- target-architecture behavior catalog 1–220 in the main overview

These contracts reopen only when the read-only cycles produce contradictory executable evidence, or when full composed Projection/R1 enters the active delivery plan. They are not current-cycle dependencies.

## Deferred

- Workspace consumption of I&E Retrieval and Working Set implementation until the Pi-native lifecycle acceptance gate passes; isolated IER1 core-package work is owned separately.
- Executable OR-25/OR-26 enforcement until the frozen write compiler and remote-effect recipe platform are deliberately reopened; the current Orientation write-basis prohibition remains in force.
- Full Case Management semantic overlay and composed Projection activation.
- Strict R1 Resource Reference write, facade, Resource Use Permit, PostgreSQL journal, outbox, receipt reconciliation, and accepted-but-unsynchronized UI.
- A closed `CaseProjectionChangeSet` delta contract; full reopen is the current correctness path.
- Append-investigation-note until distinct-intent identity and authoritative receipt semantics are proven.
- R2/R3/R4 proposal workflows, full ACH/Assessment contract, entity merge, and external publication.
- Multi-user shared-analysis discovery, co-editing, notifications, and cross-user context injection.
- Protected historical Projection artifact store and exact as-of reconstruction.
- Protected exact provider-input replay and whole-prompt retention profile.

## Delivery order

1. Orientation late-response, dirty/full-reopen, stale-Session, and Adapter-conformance lifecycle: delivered.
2. Independently accept TU-01 through TU-15 and the shared one-shot/Harness Provider Dispatch design; then deepen Pi lifecycle seams and migrate Agent Workspace through PNW-A through PNW-E with public-seam acceptance.
3. After that gate and IWS1 reacceptance, activate Workspace consumption of the independently developed I&E exact-resource Module and the atomic Working Set contract.
4. Deepen Coverage Boundary, Candidate Finding, and minimum Assessment behavior from observed product use.
5. Add a delta contract only if production measurement shows full Orientation reopen is inadequate.
6. Activate the full composed Case Projection after the Case Management overlay is executable.
7. Reopen the frozen Facade/Permit/Journal contracts and implement the first strict R1 neutral Resource Reference.
