# `workspace-task-result/v1` Contract

Status: **Design candidate; Design Gate FAIL. No implementation is authorized.**

Research basis:
[Task Result, Evidence Assembly and Report Packet Research](../research/task-result-evidence-assembly-report-packet-research-2026-07-22.md).

## 1. Product purpose

A settled Investigation Run proves how execution ended. It does not by itself
state, in a machine-readable form, what the admitted task achieved, which work
remains incomplete, or which statements are source assertions, task-level analysis,
unresolved questions, or status/coverage declarations.

`workspace-task-result/v1` closes that first handoff:

```text
private Task Result Proposal or trusted interruption facts
  -> Workspace / Run Control admission
  -> one atomic settlement group:
       Task Result entry
       Run settlement terminal (physically last)
  -> settled Investigation Run + durable Task Result
  -> later Evidence Assembly
```

The Task Result is private Workspace state. It is not a report, publication
candidate, Case update, Candidate Finding, Evidence Reference, Intelligence
Resource, graph, retrieval result or model context.

This contract defines semantic behavior and lifecycle before fixing a JSON
Schema. No implementation may infer a schema from the illustrative member
names in this document.

## 2. Ownership and seam

The normative owner is **Agent Investigation Workspace / Investigation Run
Control**.

The existing Run Control Module is deepened at its settlement seam. No separate
Task Result Module is created. The public product Interface remains the
`CaseWorkspace.prompt(...) -> WorkspaceTurn` flow; callers do not construct,
commit or amend Task Results.

The private Task Result Interface has one logical operation:

> Finalize exactly one Task Result atomically with one verified Run settlement
> from its exact trusted result proposal or interruption basis.

The operation hides:

- Run, goal and settlement verification;
- Save Point qualification;
- result-proposal admission;
- classification and reference checks;
- partial/incomplete-work handling;
- durable Session commit and exact replay;
- failure closure; and
- the non-authority rules consumed by later Evidence Assembly.

Deletion test: without this seam, Evidence Assembly, report composition,
interruption recovery and publication would each have to reinterpret Run
settlement, goal coverage, Save Points, model claims and incomplete work.
Keeping the behavior in Run Control provides leverage and locality without
creating another long-lived authority.

## 3. Relationship to existing records

### 3.1 Run settlement

Task Result and Run settlement are different records in one atomic Pi Session
control group. The Task Result entry is materialized first and the
Workspace-authenticated Run terminal is physically last. Before commit, both
are transaction-local candidates. Only a committed or authoritatively
exact-present complete group simultaneously establishes the settled Run and
the durable Task Result.

This preserves the logical product dependency `settled Run -> Task Result`:
the earlier physical entry is not a Task Result authority until the later
terminal linearizes the whole group.

An uncommitted stop proposal, Harness completion callback, Provider terminal,
local state, isolated Task Result entry or Session message is insufficient.

One Task Result binds one:

- Original User Task and admitted Task Context;
- Workspace, Case reference and Session/branch;
- Run ID and generation;
- ordered admitted goals;
- final disposition;
- Run basis and control-state digest;
- final trusted Save Point present/absent state;
- settlement reference/digest and resulting Session leaf; and
- Task Result contract/profile version.

The Task Result does not copy or reinterpret Pi settlement evidence as a second
execution authority.

### 3.2 `ModelResponseCandidateV1`

`ModelResponseCandidateV1` is a publication candidate under the current
Workspace Output Publication contract. It is not a Task Result and cannot be
accepted as one by reference, translation or field copying.

For the target report workflow, the main Investigation Agent's final private
structured output is a **Task Result Proposal**, not a public response
candidate. It is produced in the same final Agent turn; this contract adds no
second model call, Harness, Provider lifecycle or report-writing call.

The proposal is non-authoritative. It becomes eligible only after its exact
private entry is committed at the final trusted Save Point, its ref/digest is
admitted by Run Control, and the atomic group containing its Task Result and
Run settlement terminal commits.

This requires an explicit amendment to the current Run Control and Publication
assumptions that bind first-party report claims directly to
`ModelResponseCandidateV1`.

### 3.3 Case and evidence authority

Task Result statements remain task-scoped and non-authoritative:

- a source-assertion statement means that an exact source asserted or represented
  something; it does not mean the assertion is true;
- a task-analysis statement is a Workspace investigation judgment, not an
  accepted Case conclusion;
- a material reference or proposed support/contradiction relationship is a
  candidate for later Evidence Assembly, not a Case Management
  `Evidence Reference`; and
- inclusion never mutates the Case or creates a new Case Revision.

### 3.4 Pi result vocabulary reuse

This contract does not redefine Pi's existing results:

| Existing Pi value | Meaning retained | Why it is not Task Result |
| --- | --- | --- |
| `AgentToolResult` | one Tool execution's model/UI content and structured details | says what one Tool returned, not what the admitted task achieved |
| `turn_end.toolResults` | ordered finalized Tool-result messages for one Agent turn | turn-local transport, not cross-turn task semantics |
| `agent_end.messages` | messages emitted by one completed Agent loop | transcript output, not an admitted business result |
| `prompt(...) -> AssistantMessage` | the final assistant message for the Pi call | model output, not Workspace authority |
| Pi Agent Run settlement result/evidence | operational terminal and exact commit proof | proves how the Run ended, not its CTI conclusions |

Workspace consumes those values through their existing Interfaces. Task Result
stores only Workspace-owned goal/result semantics and exact refs/digests needed
to bind them. It does not copy Tool bodies, replace Tool results, rename the Pi
settlement, or add a generic result type to `packages/agent`.

## 4. Creation lifecycle

### 4.1 Normal and bounded-incomplete settlement

For `completed`, `insufficient_evidence`, `budget_exhausted`, or `blocked`:

1. the final Investigation Agent turn emits one bounded private Task Result
   Proposal;
2. Workspace validates its closed carrier, goal coverage, statement classes,
   references and bounds without deciding semantic evidentiary support;
3. the exact proposal commits with the final trusted Save Point;
4. Run Control admits one Task Result candidate and the Run terminal binds its
   complete digest, proposal ref/digest and exact Save Point;
5. Pi prepares one two-entry control group containing the Task Result followed
   by the physically-last Run terminal;
6. application verification checks both complete materialized entries and
   their shared settlement binding before seal and immediately before commit;
   and
7. commit or authoritative exact-present lookup simultaneously establishes the
   settled Run and durable Task Result.

No Evidence Assembly, report Composer, audit or public content starts before
step 7 proves the complete group.

### 4.2 Failure, cancellation and discard

`failed`, `cancelled`, and `discarded` do not trigger another model call.
Workspace constructs an interruption Task Result candidate only from:

- the exact settled interruption disposition;
- the last trusted Save Point when one exists;
- result/progress material already committed by that Save Point;
- admitted Run Control state and finalized operation outcomes; and
- a closed mechanical blocker/failure description safe for later projection.

Uncommitted assistant text, Tool progress, ignored late callbacks, unknown
remote outcomes and reconstructed transcript summaries cannot enter the Task
Result.

When no trusted Save Point exists, Pi may settle only an interrupted terminal.
The settlement group is anchored to the immutable Run-admission Session leaf
captured before work. Its Task Result is status-only: it states that no
resumable semantic result can be established and contains no reportable factual
or analytical statement. `completed`, `insufficient_evidence`,
`budget_exhausted`, and `blocked` remain impossible without a trusted final
Save Point.

### 4.3 Partial progress

A non-completed Run may contain both trusted completed work and incomplete
work. The aggregate Run disposition remains exact, while every admitted goal
retains its own result state and reason.

This reopens the current Run Control rule that forces every goal to share one
non-completion status and forbids all partial result claims. The replacement
must preserve the distinction between:

- a goal with a committed result;
- a goal stopped for insufficient evidence;
- a goal stopped by budget;
- a goal blocked by a dependency or authorization;
- a goal interrupted before a trustworthy semantic result; and
- work whose remote acknowledgement remains unknown.

The aggregate disposition remains a deterministic Run Control reduction over
trusted limiting facts:

- `completed` requires every goal to have a trusted achieved result;
- otherwise the existing cancellation, discard, failure, blocking, budget and
  insufficient-evidence precedence selects the aggregate disposition;
- a goal already achieved remains achieved even when another goal selects the
  aggregate non-completion disposition;
- an interrupted goal is never relabelled insufficient merely because some
  other goal has evidence; and
- unknown acknowledgement prevents the affected work from being described as
  completed or safely repeatable.

The final Task Result Proposal supplies per-goal semantic content, but it cannot
select or downgrade the aggregate disposition. Run Control derives both the
aggregate disposition and the maximum permissible state of every goal from
trusted facts before admitting proposal content.

No partial result may be presented as aggregate completion.

### 4.4 Save Point Task Result Contributions

Run Control gains one private, optional **Task Result Contribution** carried by
an ordinary Agent turn and committed inside that turn's existing Save Point
group. This is an internal record of the Task Result contract, not a public
progress report, interim assessment Module or additional model call.

Rules:

- at most one contribution may be admitted per committed Save Point;
- a contribution may contain bounded per-goal work status, classified
  statements, conflicts, unresolved questions and candidate material refs
  produced by that same turn;
- mechanically known Tool/Provider/budget/status facts are supplied by
  Workspace, not authored by the model;
- the contribution entry is before the existing physically-last Save Point
  receipt, which binds its complete digest;
- a failed/rolled-back Save Point contributes nothing;
- goals remain operationally `open`; a contribution is recoverable progress,
  not a final goal assessment or completion permission;
- contributions are append-only and ordered by Save Point. A later contribution
  may explicitly supersede an earlier same-statement revision but cannot erase
  its history or silently change its semantic class;
- the final Task Result Proposal references the exact contribution lineage it
  adopts and may add final-Save-Point statements; and
- an interrupted Task Result uses only the contribution lineage proven by its
  last trusted Save Point. When no contribution exists, no semantic partial
  result is reconstructed.

This supplies the minimum durable semantic progress needed for interruption
reports while keeping all recovery inside existing Save Point and Run Control
behavior.

The closed contribution carrier is:

```ts
interface TaskResultContributionV1 {
	protocol: "workspace-task-result-contribution/v1";
	contributionRef: string;
	workspaceRef: string;
	taskRef: string;
	runRef: string;
	runGenerationId: string;
	savePointRef: string;
	previousContributionRef: string | null;
	previousContributionDigest: string | null;
	orderedGoalProgress: readonly TaskResultGoalProgressV1[];
	orderedStatements: readonly TaskResultStatementV1[];
	orderedMaterialAssociations: readonly AdmittedTaskResultMaterialAssociationV1[];
	orderedConflicts: readonly TaskResultConflictV1[];
	orderedCoverageAndGaps: readonly TaskResultCoverageOrGapV1[];
	orderedSupersessions: readonly TaskResultStatementSupersessionV1[];
	contributionDigest: string;
}

interface TaskResultStatementSupersessionV1 {
	statementRef: string;
	priorStatementDigest: string;
	nextStatementDigest: string;
	supersessionDigest: string;
}
```

The first contribution has both previous members `null`; every later
contribution names the exact immediately preceding committed contribution.
Contribution order therefore follows Save Point order without a second
sequence authority.

One contribution contains at most four goal-progress members, 16 new statement
revisions, 64 material associations, 16 conflicts, 16 coverage/gap records and
16 supersessions. Across one Run there are at most 64 statement revisions, 256
material associations, 32 conflicts, 32 coverage/gap records and four revisions
of one `statementRef`. Retirement or supersession refunds no bound.

The complete contribution is at most 128 KiB UTF-8 JCS. At-limit commits;
one-over rejects the entire Save Point group before commit. Its digest is
SHA-256 over exact UTF-8 JCS bytes with `contributionDigest` omitted.

## 5. Task Result information model

The closed carrier below expresses the following semantic groups without
merging their authority.

### 5.1 Identity and basis

- stable Task Result identity and contract/profile version;
- exact task, Workspace, Case, Session/branch, Run/generation and settlement
  bindings;
- ordered goal identities and admitted objective digests;
- aggregate disposition and reason;
- final trusted Save Point present/absent state;
- historical Run basis and Context Generation binding; and
- result digest and durable commit receipt binding.

### 5.2 Per-goal result

Every admitted goal appears exactly once in original ordinal order and records:

- achieved, bounded-incomplete, blocked or interrupted state;
- trusted completed work;
- trusted incomplete work and exact limiting reason;
- statements assigned to that goal;
- material conflicts and unresolved questions;
- coverage/omission declarations;
- candidate next steps; and
- the committed progress/Save Point basis from which these members came.

An extra, missing, duplicate, reordered or cross-goal member rejects the whole
Task Result.

### 5.3 Statement classes

Every Task Result statement has exactly one semantic class:

1. **source assertion** — what an exact qualified source version says or directly
   records;
2. **task analysis** — a task-scoped interpretation, inference, comparison or
   judgment made by the Investigation Agent;
3. **unresolved question** — a material question the Run did not resolve; or
4. **status/coverage declaration** — a trusted statement about execution,
   search/retrieval coverage, missing data, budget, blocking or resumability.

The class is mandatory and immutable. Unknown classes, ambiguous dual classes,
or moving analysis into a status field fail closed.

A source-assertion statement must be phrased as a sourced assertion rather than an
unqualified truth claim. A task-analysis statement must not claim Case
acceptance. An unresolved question cannot be rendered as a finding.
Status/coverage declarations use trusted facts or closed Workspace rendering;
the model cannot invent operational status.

### 5.4 Candidate material associations

A statement may carry bounded references to task-local qualified material and
the model's candidate relationship intent such as support, contradiction,
qualification or unresolved relevance.

The model-visible proposal member is deliberately small:

```ts
interface TaskResultMaterialAssociationProposalV1 {
	statementRef: string;
	workingSetEntryRef: string;
	roleIntent:
		| "candidate_support"
		| "candidate_contradiction"
		| "candidate_qualification"
		| "unresolved_relevance";
}
```

The model can name only an opaque `WorkingSetEntryV1.entryRef` present in the
exact current selection exposed to that Run. It cannot provide an entry digest,
Resource Version, Capture, receipt, lineage, source relationship, score,
evidence role or Case reference.

Workspace admission resolves each proposal into:

```ts
interface AdmittedTaskResultMaterialAssociationV1 {
	associationRef: string;
	statementRef: string;
	workingSetEntryRef: string;
	workingSetEntryDigest: string;
	workingSetVersion: string;
	workingSetSelectionDigest: string;
	admissionWorkingSetReceiptSignedPayloadDigest: string;
	savePointRef: string;
	roleIntent:
		| "candidate_support"
		| "candidate_contradiction"
		| "candidate_qualification"
		| "unresolved_relevance";
	associationDigest: string;
}
```

The admitted association belongs to one statement revision and one Save Point.
Changing the statement, entry, selection, receipt, Save Point or role creates a
different association digest; it never edits the old association.

There are at most 16 associations per statement and 256 in one Task Result.
Duplicate statement/entry/role tuples reject. One-over rejects the complete
proposal/contribution before Save Point commit; no silent priority or
truncation rule exists.

Those members are routing hints for the later Evidence Assembly contract. They
do not prove entailment, independence, contradiction, corroboration or Case
evidentiary role. Vector scores, graph-path length and model confidence are not
admitted support.

The Task Result contains no source body, embedding, vector, unrestricted graph
path, secret identifier or copied Case `Evidence Reference`.

### 5.5 Conflict, gaps and next steps

Material contradiction, repeated reporting, unknown source dependency,
coverage limitation and unresolved work are first-class result content. They
cannot be hidden in prose or omitted merely because a preferred conclusion
exists.

Next steps are non-authoritative proposals. They create no new task, Tool call,
budget, Case update or authorization.

### 5.6 Closed Task Result carrier

```ts
interface WorkspaceTaskResultV1 {
	protocol: "workspace-task-result/v1";
	taskResultRef: string;
	basis: WorkspaceTaskResultBasisV1;
	aggregateDisposition:
		| "completed"
		| "insufficient_evidence"
		| "budget_exhausted"
		| "blocked"
		| "failed"
		| "cancelled"
		| "discarded";
	dispositionReasonCode: string;
	orderedGoals: readonly TaskResultGoalV1[];
	orderedStatements: readonly TaskResultStatementV1[];
	orderedMaterialAssociations: readonly AdmittedTaskResultMaterialAssociationV1[];
	orderedConflicts: readonly TaskResultConflictV1[];
	orderedCoverageAndGaps: readonly TaskResultCoverageOrGapV1[];
	orderedNextSteps: readonly TaskResultNextStepV1[];
	taskResultDigest: string;
}

interface WorkspaceTaskResultBasisV1 {
	workspaceRef: string;
	taskRef: string;
	admittedTaskContextDigest: string;
	caseRef: string;
	caseRevision: string;
	sessionRef: string;
	branchRef: string;
	runRef: string;
	runGenerationId: string;
	runAdmissionLeafRef: string;
	runAdmissionLeafDigest: string;
	runSettlementRef: string;
	runSettlementCandidateDigest: string;
	contextGenerationDigest: string;
	workingSetVersion: string;
	workingSetSelectionDigest: string;
	finalSavePoint:
		| {
				kind: "present";
				savePointRef: string;
				savePointDigest: string;
				finalContributionRef: string | null;
				finalContributionDigest: string | null;
		  }
		| {
				kind: "absent";
				reason: "no_committed_task_save_point";
		  };
	profileRef: string;
	profileVersion: string;
	profileDigest: string;
}

interface TaskResultGoalV1 {
	goalRef: string;
	ordinal: number;
	admittedObjectiveDigest: string;
	state: "achieved" | "bounded_incomplete" | "blocked" | "interrupted";
	orderedProgress: readonly TaskResultGoalProgressV1[];
	orderedStatementRefs: readonly string[];
	orderedConflictRefs: readonly string[];
	orderedCoverageAndGapRefs: readonly string[];
	goalDigest: string;
}

interface TaskResultGoalProgressV1 {
	progressRef: string;
	goalRef: string;
	kind: "completed_work" | "incomplete_work";
	summary: string;
	limitingReasonCode: string | null;
	savePointRef: string;
	progressDigest: string;
}

interface TaskResultStatementV1 {
	statementRef: string;
	revision: number;
	goalRef: string;
	class:
		| "source_assertion"
		| "task_analysis"
		| "unresolved_question"
		| "status_or_coverage";
	text: string;
	origin: "agent_proposal" | "workspace_derived";
	reportRequirement: "required" | "optional";
	savePointRef: string;
	statementDigest: string;
}

interface TaskResultConflictV1 {
	conflictRef: string;
	goalRef: string;
	leftStatementRef: string;
	rightStatementRef: string;
	status: "unresolved" | "bounded_explanation_available";
	savePointRef: string;
	conflictDigest: string;
}

interface TaskResultCoverageOrGapV1 {
	recordRef: string;
	goalRef: string;
	kind:
		| "retrieval_coverage"
		| "missing_material"
		| "unknown_source_dependency"
		| "budget_limit"
		| "external_blocker"
		| "resumability";
	summary: string;
	ownerEvidenceRef: string;
	ownerEvidenceDigest: string;
	savePointRef: string;
	recordDigest: string;
}

interface TaskResultNextStepV1 {
	nextStepRef: string;
	goalRef: string;
	objective: string;
	reason: string;
	authority: "proposal_only";
	nextStepDigest: string;
}
```

The final carrier includes every admitted goal exactly once in goal ordinal
order. Statement and association arrays preserve their first committed
Save Point order and then revision order. Conflicts, coverage/gaps and next
steps are byte-ordered by ref.

`WorkspaceTaskResultBasisV1` repeats refs/digests rather than copying Session,
Case, Working Set or settlement content. `finalSavePoint.kind = "absent"`
permits only `failed`, `cancelled` or `discarded`, all goals `interrupted`, zero
statements, associations, conflicts and next steps, and mechanically rendered
status/coverage only through the goal-progress/coverage records allowed by the
Run-admission basis.

### 5.7 Bounds and canonicalization

| Item | v1 hard maximum |
| --- | ---: |
| goals | exactly admitted count, 1–4 |
| goal progress records | 64 |
| statement revisions retained | 64 |
| statement revisions per `statementRef` | 4 |
| UTF-8 bytes per statement/progress/coverage/next-step text member | 4 KiB |
| total human-readable UTF-8 bytes | 128 KiB |
| material associations per statement | 16 |
| material associations total | 256 |
| conflicts | 32 |
| coverage/gap records | 32 |
| next steps | 16 |
| complete canonical Task Result | 512 KiB |

All refs are 1–512 UTF-8 bytes without C0/C1 controls. Profile identifiers,
reason codes and key IDs are 1–128 ASCII identifier characters. Every digest is
exactly 64 lowercase hexadecimal SHA-256. Revisions and ordinals are positive
safe integers.

Each record digest is SHA-256 over exact UTF-8 RFC 8785 JCS bytes with only its
own digest member omitted. The Task Result digest follows the same rule.
Unknown members, duplicate refs, non-canonical order, dangling references,
revision gaps, class-changing supersession, foreign Save Points or one-over
bounds reject the whole result. No truncation or model-selected priority rule
exists.

## 6. Admission rules

Run Control admits a Task Result only when:

- the Run settlement and terminal verify exactly;
- the result belongs to the same task, goals, Run generation and settlement;
- its proposal, if required, is the exact final-Save-Point-bound proposal;
- every goal and statement reference resolves exactly once;
- only committed finalized work is represented;
- aggregate and per-goal states do not claim more completion than the settled
  facts permit;
- failed/cancelled/discarded paths include no post-interruption model content;
- a missing trusted Save Point produces status-only output;
- claim classes and candidate material references satisfy their closed bounds;
- no Task Result member claims publication or Case acceptance; and
- the result has not already been committed under another digest.

Run Control does not decide whether source material semantically supports a
task-analysis statement. That remains the later task-scoped Evidence Assembly
candidate relationship plus independent Evidence Audit.

## 7. Atomic settlement, durability and recovery

The v1 Task Result is a small durable Workspace derivation stored through the
existing Pi Session control-batch authority. This creates no Task Result
database and no new persistence Module.

The Agent Run settlement batch is amended from terminal-only to exactly two
entries:

```text
1. application Task Result entry
2. application Run settlement terminal (physically last)
```

The terminal binds the complete Task Result entry ID, entry digest and
Task Result digest. Pi's generic settlement evidence proves both materialized
entries, their order, expected leaf and complete A4 batch digest without
interpreting Task Result meaning. The application creates and verifies their
business content and authenticity.

For a Run with a trusted final Save Point, the settlement expected leaf is that
Save Point. For an interrupted Run with no trusted Save Point, the expected
leaf is the immutable Run-admission Session leaf and the terminal explicitly
binds `save-point absent`. Empty strings, null pretending to be a digest, or a
foreign/latest Session head are invalid.

The settlement identity remains one-to-one with the Run. Conflict or
acknowledgement uncertainty permits only the existing exact settlement lookup;
it never permits rebuilding against a later Session head or committing a
different Task Result for the same Run.

### 7.1 Save Point contribution integration

Task Result Contributions use the existing transactional Save Point
application-entry seam. They require no new Pi method or independent commit:

```text
turn/message/tool-result entries
  -> optional Workspace Task Result Contribution
  -> existing final marker when this is the final Save Point
  -> existing application Save Point receipt (physically last)
```

Workspace's Save Point receipt amendment binds the optional contribution entry
ID, complete entry digest and contribution digest. The ordinary Pi save-point
commit evidence continues to prove the physical terminal receipt. A
contribution is eligible only when both proofs refer to the same complete
committed batch. Absence is explicit and does not mean an empty contribution.

### 7.2 Versioned Pi settlement amendment

The target must not overload the accepted
`PiAgentRunSettlementEvidenceV1` by placing empty values in its required final
Save Point fields. A versioned Pi settlement Interface must instead express
one discriminated settlement anchor:

- **trusted Save Point present:** exact final Save Point entry ID/digest and
  final-marker proof; or
- **trusted Save Point absent:** exact Run-admission Session leaf ID/digest and
  a closed reason proving that no committed task Save Point is being claimed.

For either branch, generic Pi evidence proves:

- the one Run/session/generation identity;
- terminal kind;
- exact anchor and expected leaf;
- the two ordered A4 entries;
- Task Result entry ID/digest;
- physically-last application terminal ID/digest/receipt;
- complete batch evidence and evidence digest; and
- committed or exact-present knowledge.

Pi does not parse the Task Result. The application terminal binds its Task
Result digest and verifies the complete business relationship twice under the
existing create/verify discipline.

The absent branch is valid only for `failed`, `cancelled`, or `discarded`.
`completed`, `insufficient_evidence`, `budget_exhausted`, or `blocked` with an
absent Save Point is an application denial before seal and appends nothing.

The private settlement sidecar/journal key and value must be versioned with the
anchor branch and Task Result entry identity. Recovery recognizes only the
complete exact two-entry group. It does not reconstruct an A4 handle, upgrade a
baseline `no_final_save_point` result, or splice this target behavior into an
unconfigured Harness.

A crash:

- before the atomic settlement commit produces neither a settled Run nor a
  durable Task Result;
- after a possibly committed group uses the existing settlement sidecar and
  exact A4 lookup to recover the same two-entry group;
- can never observe a valid Task Result without its exact settlement terminal,
  or a valid settlement terminal without its exact Task Result; and
- never repeats the Investigation Agent, Tool, Provider or report Composer.

The Task Result is an immutable historical record of what the Run concluded
under its basis. Later source withdrawal, re-lineage, authorization change,
Case revision or index drift does not rewrite it. Those changes make an old
Task Result ineligible for a new Report Evidence Packet until Evidence Assembly
revalidates and explicitly represents the changed state.

## 8. Failure closure

| Failure | Required closure |
| --- | --- |
| atomic settlement group absent or proof mismatches | no settled Run, no Task Result and no downstream work |
| normal-path proposal missing, malformed or not bound to final Save Point | fail the normal result handoff; do not translate `ModelResponseCandidateV1` |
| interruption has trusted Save Point | include only committed result/progress material |
| interruption lacks trusted Save Point | status-only Task Result with no factual/analytic statements |
| cross-goal, stale-generation or foreign material ref | reject whole result |
| statement class invalid or authority overstated | reject whole result |
| settlement-group commit conflict | append neither entry; no retry against changed head |
| commit acknowledgement unknown | exact lookup of the complete two-entry group only |
| later source/authorization/Case drift | retain historical result, deny stale packet reuse |

No failure falls back to raw Session text, a Provider completion, graph search,
vector similarity, guessed citation or Case state.

## 9. Public acceptance candidates

The acceptance seam remains the product Workspace turn and its durable Session
evidence; tests do not expose an assembly helper as a public Interface.

1. A completed multi-goal Run produces exactly one durable Task Result with
   every goal and correctly classified source-assertion/task-analysis statements.
2. Insufficient-evidence, budget-exhausted and blocked Runs preserve trusted
   completed goals and exact incomplete goals without claiming aggregate
   completion.
3. A failed/cancelled/discarded Run with a trusted Save Point includes only
   progress committed by that Save Point and performs zero post-interruption
   model calls.
4. The same interruption without a trusted Save Point produces a status-only
   result with zero factual/analytic statements.
5. Uncommitted model text, Tool progress and late callbacks never enter a Task
   Result.
6. `ModelResponseCandidateV1` alone cannot satisfy the Task Result seam.
7. Source assertion, task analysis, unresolved question and status/coverage remain
   distinct; unknown/dual/mislabelled classes fail closed.
8. Candidate support/contradiction material refs remain non-authoritative and
   create no Case `Evidence Reference`.
9. Same-lineage repeated reporting and unknown dependency cannot be described
   as independent corroboration in the Task Result.
10. Exact settlement replay returns the same two-entry group; changed-result
    replay, Session-head conflict and foreign settlement append nothing.
11. Crash around the settlement commit recovers both Run terminal and Task
    Result or neither, without replaying Agent/Tool/Provider work.
12. Later withdrawal, authorization loss or Case drift leaves the historical
    Task Result immutable but prevents stale downstream packet use.
13. Creating or publishing a Task Result changes no Case Revision.
14. No Evidence Assembly, Composer, audit or public report starts before the
    exact Task Result commit is proven.
15. An admitted Task Result Contribution is visible only with its complete
    committed Save Point group; rollback, conflict and post-commit foreign
    contribution substitution produce no eligible progress.
16. Contribution revision/supersession preserves earlier history and semantic
    class; a later Save Point cannot silently turn task analysis into a source
    assertion.
17. A no-Save-Point settlement succeeds only for a status-only
    failed/cancelled/discarded result anchored to the exact Run-admission leaf;
    every completion-like disposition appends nothing.

The matrix remains candidate material until the blockers below close.

## 10. Frozen architecture decisions

- No Task Result or Evidence Assembly Module is added.
- The main Investigation Agent emits one private Task Result Proposal in its
  existing final turn; it does not write the public report.
- Run Control derives aggregate disposition and admits per-goal result content.
- Trusted partial semantic progress uses optional contributions inside existing
  Save Point groups.
- Task Result and Run settlement are separate entries in one atomic two-entry
  settlement group; the terminal is physically last.
- Interruption with no trusted Save Point uses an explicit absent anchor and a
  status-only Task Result.
- `ModelResponseCandidateV1` is not a compatibility alias or fallback.
- Evidence Assembly, report composition, audit and publication remain later
  contracts and start only from the committed Task Result.

## 11. Design Gate

- **Verdict:** FAIL
- **Owner:** Agent Investigation Workspace / Investigation Run Control
- **Interface:** one private Task Result finalization seam inside the atomic Run
  settlement transaction;
  public observation remains `CaseWorkspace.prompt(...) -> WorkspaceTurn`
- **Input authority:** immutable Run identity/admission leaf, final trusted Save
  Point present/absent state, admitted goals/control facts, and one bound
  private Task Result Proposal or trusted interruption facts
- **Output/evidence:** one atomic two-entry settlement group proving one
  immutable private Task Result and one physically-last Run terminal
- **Failure closure:** the group commits both records or neither; interruption
  without a trusted Save Point is status-only; uncertainty uses exact lookup
- **Secret isolation:** no credentials, unrestricted Session history, source
  bodies, embeddings, hidden graph paths or hidden Case identifiers
- **Provider lifecycle count:** zero additional calls; normal proposal uses the
  existing final Investigation Agent turn, interruption uses deterministic
  facts
- **Workspace exposure:** private result identity/status only until later report
  publication
- **Backward compatibility:** none assumed; current direct
  `ModelResponseCandidateV1` settlement/publication handoff is a migration
  baseline to replace, not preserve
- **Public acceptance seam:** Workspace turn, committed Session evidence and
  proof that no downstream report work starts early
- **Remaining blockers:**
  1. **Owner: Workspace Run Control + Publication. Expected:** final formal
     Agent output is a bounded private Task Result Proposal, per-goal mixed
     results are preserved, and later Publication consumes a separately
     composed report. **Actual:** accepted contracts bind goal coverage and
     publication directly to `ModelResponseCandidateV1`, require uniform
     non-completion and forbid partial claims. **Minimal fix:** amend Run
     Control/Publication to consume the now-closed proposal/result carrier and
     mixed per-goal reducer through public acceptance.
  2. **Owner: Workspace Run Control at Pi Save Point seam. Expected:** one
     optional contribution entry is atomically bound by the existing Save Point
     receipt, with stable statement revision/supersession identity. **Actual:**
     the contribution carrier, bounds and digest lineage are now closed, but no
     accepted Save Point receipt amendment commits it. **Minimal fix:** freeze
     and accept only the Save Point receipt members plus rollback/recovery
     behavior without adding a Pi method.
  3. **Owner: Pi Agent Run settlement + Workspace terminal. Expected:** one
     versioned two-entry settlement group with a discriminated trusted
     Save-Point-present/absent anchor and exact sidecar recovery. **Actual:**
     accepted PNW v1 is terminal-only, requires final Save Point strings, and
     returns `not_settled/no_final_save_point`. **Minimal fix:** freeze the
     versioned generic Pi Interface/evidence, Workspace terminal binding and
     focused public-Harness acceptance; do not alter implemented v1 behavior.
