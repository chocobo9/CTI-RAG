# `investigation-run-control/v1` Contract

Status: **Independent design acceptance PASS; implementation NO-GO.** This PASS closes the Workspace-owned Run Control design only. It authorizes no product implementation, I&E activation, Working Set operation, Artifact creation, Assessment, Case write, or real Provider activation until its required Pi settlement, dispatch, context, publication, Session-repository, and public-seam gates pass separately.

Task Result amendment status: **Design Gate FAIL.** The accepted baseline still
describes the earlier direct `ModelResponseCandidateV1` publication path. The
target report workflow in
[`workspace-task-result/v1`](task-result-v1-contract.md) reopens final goal
coverage, non-completion uniformity, Save Point progress and settlement
payloads. It replaces the formal Investigation Run's public-response candidate
handoff with one private Task Result Proposal, allows trusted mixed partial
goal results, and adds optional Save Point Task Result Contributions. None of
those amendments inherits this contract's prior PASS or authorizes
implementation.

## 1. Decision and business problem

One formal Investigation Agent Run may address several requested outcomes and may refine bounded subquestions while evidence arrives. The model may propose subquestions, target-neutral Query Candidates, local adjustments, capability uses, and one terminal structural-coverage/stop envelope. None of those proposals is authority.

Agent Workspace owns one deterministic Run Control Module which admits or rejects those proposals against the immutable Original User Task, the admitted Task Context, the current actor/Case/purpose binding, the current Session and Context Generation, the qualified Case context, an exact Workspace Capability snapshot, and hard Run budgets. Pi remains the only owner of the Agent loop, model turns, tool scheduling, tool-result finalization, save points, Session state, cancellation, and Agent Run settlement.

The Module solves a policy problem, not a general planning problem. It does not create a task DAG, recursive planner, sub-Agent, second `AgentHarness`, second `Session`, private transcript, retry loop, or scheduler. A simple no-tool task requires no subquestion or Query Candidate at all.

The immutable Original User Task remains the user's authority. Goals, subquestions, Query Candidates, assumptions, and local adjustments are non-authoritative Additional Task Context. They never replace the Original User Task, activate a capability, select an exact resource, authorize retrieval, authorize an effect, or establish CTI truth.

## 2. Ownership, Module, and seams

```typescript
interface InvestigationRunPolicy {
	evaluate(input: InvestigationRunEvaluationV1): InvestigationRunControlDecisionV1;
}

interface InvestigationRunEvaluationV1 {
	basis: TrustedInvestigationRunBasisV1;
	state: AdmittedInvestigationRunStateV1 | null;
	observation: InvestigationRunObservationV1;
}
```

`InvestigationRunPolicy` is one Workspace-private, in-process deep Module. Its small Interface hides closed-schema validation, source-reference validation, target-neutrality checks, bounds, canonical identifiers and digests, append-only local adjustment policy, capability admission, budget reservation and reconciliation, stop precedence, continuity fencing, and actor-safe failure mapping.

The Module is pure with respect to external systems. It creates no Provider request, tool call, clock read, Session entry, or public event. Trusted callers supply an elapsed monotonic time and Pi-authoritative finalized facts. A production integration Adapter maps its decisions into existing Pi Agent Run, tool, save-point, and settlement seams. Tests observe behavior through `CaseWorkspaceModule -> CaseWorkspace.prompt -> WorkspaceTurn` and the real Pi integration seams; they do not expose or test this private Interface as a product API.

Pi owns:

- the single long-lived `Session` and `AgentHarness`;
- model invocation, provider dispatch, tool execution, and parallel read scheduling;
- authoritative token usage, provider acknowledgement, and finalized tool outcomes;
- turn snapshots, Context Generations, save points, recovery, and Agent Run settlement;
- cancellation, close, supersession fencing, and late-result disposal.

Agent Workspace owns:

- exact consumption of bounded TU outcome seeds from the committed handoff and
  minting of Run-scoped goal IDs;
- deterministic admission of model-proposed subquestions and Query Candidates;
- local append-only adjustment and scope-expansion rejection;
- exact Workspace Capability snapshot admission;
- Run budget policy and its authoritative ledger;
- Run stop disposition and the Workspace facts submitted for settlement.

This contract does not choose the number or names of product tools. A future Adapter may carry a closed Run Control proposal through a Pi tool call or another accepted Pi-native structured seam, but the carrier cannot change these semantics. There is no pre-run planning turn, planning control tool, planning save point, or same-task second model loop.

## 3. Trusted Run basis and continuity

```typescript
interface TrustedInvestigationRunBasisV1 {
	protocol: "workspace-investigation-run-basis/v1";
	workspaceRef: string;
	runId: string;
	runGeneration: number;
	actorCasePurpose: ActorCasePurposeBindingV1;
	originalTask: BoundRecordRefV1;
	admittedTaskContext: BoundRecordRefV1;
	goalBootstrap: InvestigationGoalBootstrapV1;
	initialContext: InitialInvestigationContextBindingV1;
	session: SessionContinuityBindingV1;
	caseContext: LayeredCaseContextBindingV1;
	capabilities: TrustedWorkspaceCapabilitySnapshotV1;
	budgetPolicy: InvestigationRunBudgetPolicyV1;
	pricing: TrustedRunPricingSnapshotV1;
	targetNeutralityPolicy: TargetNeutralityPolicyBindingV1;
	receiptAuthenticator: BoundRecordRefV1;
	systemInstruction: BoundRecordRefV1;
	basisDigest: string;
}

interface BoundRecordRefV1 {
	ref: string;
	protocol: string;
	digest: string;
}

interface TargetNeutralityPolicyBindingV1 {
	protocol: "workspace-target-neutrality-policy-binding/v1";
	policyRef: string;
	policyVersion: string;
	protectedLiteralPolicyDigest: string;
	forbiddenGrammarPolicyDigest: string;
	policyDigest: string;
}

interface ActorCasePurposeBindingV1 {
	actorBindingDigest: string;
	caseRef: string;
	purpose: "cti_investigation";
	credentialBindingRef: string;
	authorizationRevision: string;
}

interface SessionContinuityBindingV1 {
	sessionRef: string;
	branchRef: string;
	headEntryRef: string | null;
	contextGeneration: number;
	contextGenerationDigest: string;
	compactionBasisDigest: string | null;
	leaseGeneration: number;
}

interface InitialInvestigationContextBindingV1 {
	protocol: "workspace-initial-investigation-context/v1";
	sectionOrder: readonly [
		"system_instructions",
		"original_user_task",
		"additional_task_context",
		"working_set",
		"layered_case_context",
		"eligible_session_history",
		"activated_tools",
	];
	sectionDigests: Readonly<Record<InitialInvestigationContextSectionV1, string>>;
	contextDigest: string;
}

type InitialInvestigationContextSectionV1 =
	| "system_instructions"
	| "original_user_task"
	| "additional_task_context"
	| "working_set"
	| "layered_case_context"
	| "eligible_session_history"
	| "activated_tools";

interface LayeredCaseContextBindingV1 {
	orientation: BoundRecordRefV1;
	projectionOverlay: BoundRecordRefV1 | null;
	layeredContextDigest: string;
}
```

`InitialInvestigationContextBindingV1` is the Run-owned binding projection, not
the concrete context product. The exact seven section records, owner-local
memory reconstruction, Pi channel mapping, rendering, provider projection,
failures, and public acceptance cases are owned by
[`workspace-initial-investigation-context/v1`](initial-investigation-context-v1-contract.md).
Run Control accepts only a context produced under that contract and recomputes
this binding from its complete section and context digests.

The Workspace constructs the basis only after `pre-investigation-task-understanding/v1` has atomically committed the immutable Original User Task and admitted Task Context. The Task Understanding proposal, rejected normalization, model reasoning, and provider completion are not eligible basis material.

`goalBootstrap` is the exact `InvestigationGoalBootstrapV1` value owned by
`pre-investigation-task-understanding/v1`; this contract does not define a
parallel bootstrap, outcome, intent, or requested-outcome type. Its protocol is
exactly `workspace-investigation-goal-bootstrap/v1`; its
`admittedTaskContextRef`/`admittedTaskContextDigest` match the committed
`AdmittedTaskContextV1`; and its one through four `outcomes` are byte-for-byte
the same value carried by `CommittedTaskUnderstandingHandoffV1`. Each outcome
seed repeats the corresponding admitted outcome's exact `outcomeId`,
`outcomeDigest`, contiguous ordinal, `intentKind`, `requestedOutcome`,
`objective`, and ordered `sourceBindingDigests`. Run Control converts no source
binding into a local claim vocabulary. Any mismatch among the handoff, Task
Context, bootstrap, ordered outcome seeds, or a fresh digest recomputation fails
`invalid_run_basis` before Provider dispatch. Implementation of this consumption
seam remains dependency-gated until the unified TU goal-seed contract is
independently accepted; an Adapter with a changed name, protocol, shape, or ID
owner cannot satisfy that gate.

The seven initial-context sections and their logical precedence are inherited from `pre-investigation-task-understanding/v1`. V1 requires an explicit empty Working Set section and an exact activated-tools section; this is context shape, not authorization to implement Working Set operations. Orientation is mandatory. A Projection overlay is optional and can only add semantics when bound to the exact Orientation/source basis; it never replaces Orientation provenance.

Every observation and decision is bound to `runId`, `runGeneration`, `basisDigest`, `contextGeneration`, `leaseGeneration`, and an expected control sequence. Any mismatch is stale or concurrent input, not a request to repair history. The Module never rebases a proposal onto a newer basis, guesses continuity, or copies a decision across branches.

The basis remains fixed for one Run. If actor authorization, Case visibility, purpose, Original User Task, admitted Task Context, System Instruction, Orientation basis, Projection basis, capability snapshot, budget/pricing policy, target-neutrality policy, receipt authenticator, branch, Context Generation, compaction basis, or lease generation changes, the current Run is fenced before another Provider or tool dispatch. A new qualified basis requires a new Run generation; uncommitted proposals do not migrate.

## 4. Closed source-reference catalog

The model may refer only to source aliases present in the model-visible, Workspace-minted catalog for the current basis. It cannot invent opaque Session IDs, receipt IDs, resource IDs, tool-result IDs, or authority references.

```typescript
interface RunSourceCatalogV1 {
	protocol: "workspace-run-source-catalog/v1";
	catalogRef: string;
	entries: readonly RunSourceCatalogEntryV1[];
	sourceSpans: readonly RunSourceSpanBindingV1[];
	catalogDigest: string;
}

interface RunSourceCatalogEntryV1 {
	sourceRef: string;
	kind: RunSourceKindV1;
	boundRecordRef: string;
	contentDigest: string;
	visibility: "model_visible" | "workspace_only";
	goalRefs: readonly string[];
}

interface RunSourceSpanBindingV1 {
	spanRef: string;
	parentSourceRef: string;
	startUtf16: number;
	endUtf16: number;
	textDigest: string;
	classification:
		| "ordinary_text"
		| "cve"
		| "attack_id"
		| "hash"
		| "domain"
		| "ip_address"
		| "case_label"
		| "quoted_text"
		| "code_or_query_syntax";
	spanDigest: string;
}

type RunSourceKindV1 =
	| "original_user_task"
	| "admitted_outcome"
	| "admitted_constraint"
	| "admitted_assumption"
	| "admitted_uncertainty"
	| "orientation_fact"
	| "projection_fact"
	| "eligible_history"
	| "finalized_tool_outcome";
```

The closed, Workspace-minted `sourceSpans` collection is bound into `catalogDigest`. A span resolves to exact retained source text, uses non-empty safe-integer UTF-16 offsets that do not split a surrogate pair, and hashes the exact substring. The model sees opaque span refs next to the eligible source, not foreign Session or backend identifiers.

Only `model_visible` entries may appear in a proposal. Every reference must resolve exactly once, match the current catalog digest, and be permitted for the referenced goal. `finalized_tool_outcome` exists for later accepted tool slices only; no I&E or Working Set source is activated by this contract.

Source references express provenance, not truth. A source may support why a subquestion or Query Candidate is in scope; it cannot make a claim authoritative or bypass later citation/publication validation.

## 5. Goals, subquestions, and proposals

### 5.1 Admitted goals

```typescript
interface InvestigationGoalV1 {
	goalId: string;
	ordinal: InvestigationGoalBootstrapOutcomeV1["ordinal"];
	outcomeId: string;
	outcomeDigest: string;
	outcomeSourceRef: string;
	statement: string;
}

type InvestigationGoalStatusV1 =
	| "open"
	| "addressed"
	| "insufficient_evidence"
	| "budget_exhausted"
	| "blocked";
```

The Workspace deterministically creates exactly one Run-scoped goal for each TU
bootstrap outcome seed, in ordinal order. Run Control mints `goalId` from trusted
Run identity/generation plus the exact outcome ID/digest/ordinal under its fixed
ID policy; TU and the model never supply a Run goal ID. The goal repeats the
seed's exact `outcomeId`/`outcomeDigest`; `outcomeSourceRef` is the unique
`admitted_outcome` catalog entry bound to that same outcome; and `statement` is
byte-identical to the seed `objective`. A replay of the same admitted Run basis
reuses the same IDs, while another Run generation receives different IDs. There
may be one through four goals. Goals are immutable after Run admission. A later
material outcome is new work and cannot be appended to the current Run.

A goal statement is Additional Task Context. The Original User Task is rendered separately and remains byte/digest identical. A goal cannot narrow or discard user constraints, exclusions, protected literals, or material uncertainty.

Goals remain `open` throughout active Run control. There is no interim goal
assessment protocol and no semantic contradiction, sufficiency, confidence, or
reopen reducer in v1. Exactly one `agent_run_ended.finalGoalAssessments` item
creates the sole admitted final assessment for each goal.

`addressed` is deliberately a structural coverage fact, not a truth or evidence
sufficiency judgment. It is valid only when the bound
`ModelResponseCandidateV1` has at least one distinct claim reference assigned to
that goal, every referenced claim and citation resolves under the same candidate
and source catalog, and the goal has no pending Provider invocation, capability
use, reservation, permit, or unknown acknowledgement. Run Control does not
interpret whether the claim is correct, persuasive, contradicted, or sufficient;
publication performs its own citation and authority validation. A non-completion
status is assigned only from the closed hard facts in section 11. Once the Run
enters `stopping`, every later assessment proposal is discarded and no goal is
reopened.

### 5.2 Non-authoritative model proposal

```typescript
interface InvestigationControlProposalV1 {
	protocol: "workspace-investigation-control-proposal/v1";
	proposalId: string;
	expectedControlSequence: number;
	subquestions: readonly ProposedSubquestionV1[];
	queryCandidates: readonly ProposedQueryCandidateV1[];
	capabilityRequests: readonly ProposedCapabilityRequestV1[];
	adjustments: readonly ProposedLocalAdjustmentV1[];
	stop: ProposedRunStopV1 | null;
}

interface FinalGoalAssessmentCandidateV1 {
	goalRef: string;
	status:
		| "addressed"
		| "insufficient_evidence"
		| "budget_exhausted"
		| "blocked";
	supportSourceRefs: readonly string[];
	responseSegmentRefs: readonly string[];
	uncertainty: string | null;
}

interface ProposedSubquestionV1 {
	localId: string;
	goalRef: string;
	question: string;
	supportSourceRefs: readonly string[];
	assumptions: readonly string[];
}

interface ProposedQueryCandidateV1 {
	localId: string;
	subquestionRef: string;
	strategy: "literal";
	text: string;
	language: string | null;
	supportSourceRefs: readonly string[];
	construction: ProposedLiteralQueryConstructionV1;
	scopeDelta: "none";
	assumptions: readonly [];
}

interface ProposedLiteralQueryConstructionV1 {
	template: LiteralQueryTemplateV1;
	bindings: readonly ProposedQueryOutputSourceBindingV1[];
}

interface ProposedQueryOutputSourceBindingV1 {
	outputStartUtf16: number;
	outputEndUtf16: number;
	sourceSpanRef: string;
}

type LiteralQueryTemplateV1 = "exact_phrase" | "all_terms" | "any_terms";

interface ProposedCapabilityRequestV1 {
	localId: string;
	capabilityRef: string;
	goalRef: string;
	subquestionRef: string | null;
	queryCandidateRefs: readonly string[];
	purpose: "investigate" | "validate" | "corroborate";
	supportSourceRefs: readonly string[];
	input: RunCanonicalJsonV1;
}

type RunCanonicalJsonV1 =
	| null
	| boolean
	| number
	| string
	| readonly RunCanonicalJsonV1[]
	| { readonly [key: string]: RunCanonicalJsonV1 };
```

The proposal schema is closed. Unknown fields, duplicate keys, duplicate IDs, duplicate array entries, invalid Unicode, NUL, non-integer numbers, non-canonical encodings, unresolved references, or a protocol mismatch reject the whole proposal. Partial admission of a structurally invalid proposal is forbidden.

Subquestions are a bounded, flat set linked to exactly one existing goal. They have no child list, dependency list, condition, callback, loop, retry, scheduler, or delegation field. Evidence obtained for one subquestion may become a later `finalized_tool_outcome` source, but that sequential provenance does not create a task graph.

The Workspace mints admitted IDs after validation. Model-local IDs are scoped to one proposal and never become durable authority. Replaying the same proposal at the same control sequence is idempotent only when its canonical digest matches the already committed decision; a different digest is a concurrency failure.

Within one proposal, `subquestionRef` and `queryCandidateRefs` may name an already admitted active ref or an earlier model-local ID in the same source-ordered proposal. A local reference resolves only after its target passes admission. A rejected target makes every dependent item rejected; it is never rebound to a similarly named committed record.

## 6. Target-neutral Query Candidate

An admitted Query Candidate is a provenance-bound formulation for a question. It is not a Resource Candidate, exact selector, query plan, retrieval request, connector request, tool call, authorization, or evidence.

```typescript
interface AdmittedQueryCandidateV1 {
	queryCandidateId: string;
	version: number;
	goalRef: string;
	subquestionRef: string;
	strategy: "literal";
	text: string;
	language: string | null;
	supportSourceRefs: readonly string[];
	constructionReceipt: AdmittedLiteralQueryConstructionReceiptV1;
	scopeDelta: "none";
	assumptions: readonly [];
	supersedesQueryCandidateRef: string | null;
	proposalDigest: string;
}

interface AdmittedLiteralQueryConstructionReceiptV1 {
	protocol: "workspace-literal-query-construction-receipt/v1";
	template: LiteralQueryTemplateV1;
	bindings: readonly AdmittedQueryOutputSourceBindingV1[];
	renderedTextDigest: string;
	receiptDigest: string;
}

interface AdmittedQueryOutputSourceBindingV1 {
	outputStartUtf16: number;
	outputEndUtf16: number;
	sourceSpanRef: string;
	spanDigest: string;
	textDigest: string;
}
```

V1 admits only literal construction. The renderer is closed and deterministic:

| Template | Required bindings | Exact rendered text |
| --- | ---: | --- |
| `exact_phrase` | exactly 1 | `"` + exact source-span text + `"` |
| `all_terms` | 1-16 | exact source-span texts in binding order joined by ` AND ` |
| `any_terms` | 1-16 | `(` + exact source-span texts in binding order joined by ` OR ` + `)` |

For `exact_phrase`, the output binding covers only the text inside the two quote
characters. For the other templates, each output binding covers exactly its term
and no separator. Bindings are in ascending, non-overlapping output order and
cover every non-separator code unit. Each source span resolves to one retained
catalog span; the output substring is byte-for-byte equal to that source span.
The Workspace rerenders the text, compares it byte-for-byte, recomputes every
span/text digest, and commits the closed construction receipt. A source ref
without this output-to-source transformation proof does not admit a candidate.

Target neutrality is then both structural and syntactic:

- the schema contains no Resource Candidate Reference, OpenCTI object reference, backend identifier slot, exact selector, query language, filter tree, collection/index name, endpoint, Adapter, credential, authorization, pagination, ranking, retry, timeout, parallelism, mutation, commit, or effect field;
- `text` is a human-level information need, not GraphQL, SQL, Lucene, OpenSearch, STIX pattern, connector syntax, or another executable backend expression;
- target-specific instructions introduced only by the model are rejected;
- every literal classified as a CVE, ATT&CK identifier, hash, domain, IP address,
  case label, quoted value, code, or query-like syntax is wholly covered by one
  construction binding. Unbound target-looking text, mismatched offsets/digests,
  split surrogate pairs, overlapping bindings, and a model-created selector are
  rejected;
- a literal present in an eligible source may therefore be preserved verbatim as source-anchored text. It remains a search term, never an exact-resource selector or authorization. Source-anchored query/code syntax may be quoted as the subject of investigation but cannot be the candidate's executable form;
- `scopeDelta` is always `none` and `assumptions` is the exact empty tuple.
  `translated`, `alias_expanded`, `broadened`, `narrowed`, paraphrased, or any
  other changed-term strategy is outside v1 and rejected as an unknown closed
  discriminant. A changed-term protocol would require its own closed
  output-span-to-source-span transformation, assumption and scope-delta rules,
  receipt, and independent acceptance before activation.

No admitted Query Candidate is executable. A later owning retrieval contract must convert it, together with current trusted dependencies and policy, into its own admitted request. That future conversion is out of scope here.

The trusted `targetNeutralityPolicy` defines the versioned scanner, protected-literal classes, forbidden executable grammars, and actor-safe rejection codes. It is fixed for the Run and validated before proposal admission. The scanner operates on the candidate plus exact retained source spans; a source ref alone does not bless arbitrary model text. Policy drift fences the Run instead of reclassifying a committed candidate.

## 7. Local append-only adjustment

```typescript
interface ProposedLocalAdjustmentV1 {
	localId: string;
	kind: LocalAdjustmentKindV1;
	goalRef: string;
	targetRef: string;
	replacementSubquestion: ProposedSubquestionV1 | null;
	replacementQueryCandidate: ProposedQueryCandidateV1 | null;
	reasonSourceRefs: readonly string[];
}

type LocalAdjustmentKindV1 =
	| "supersede_subquestion"
	| "supersede_query_candidate"
	| "retire_subquestion"
	| "retire_query_candidate";

interface AdmittedLocalAdjustmentV1 {
	adjustmentId: string;
	controlSequence: number;
	kind: LocalAdjustmentKindV1;
	goalRef: string;
	targetRef: string;
	replacementRef: string | null;
	reasonSourceRefs: readonly string[];
	decisionDigest: string;
}
```

An adjustment is local only when all of the following remain unchanged:

- actor, Case, purpose, Original User Task, admitted Task Context, and goal;
- requested outcome, effect class, disclosure class, and trusted dependency set;
- current branch, Context Generation, Case context basis, and capability snapshot;
- the meaning of unaffected goals, subquestions, and Query Candidates.

Admission appends a new version and an immutable supersession edge. It never edits or deletes a committed record. A superseded record remains available for audit and is no longer eligible for new action. At most one active successor may exist for a record. A target must be active, belong to the same goal, and have been admitted at a lower control sequence.

The four kinds have this exact closed target/nullability matrix:

| Kind | `targetRef` | `replacementSubquestion` | `replacementQueryCandidate` | `replacementRef` |
| --- | --- | --- | --- | --- |
| `supersede_subquestion` | one active same-goal subquestion with no active Query Candidate or pending capability use | required; same `goalRef`; its model-local `localId` is fresh | `null` | admitted replacement subquestion ID |
| `supersede_query_candidate` | one active same-goal Query Candidate | `null` | required; same target subquestion, literal construction only, fresh model-local `localId` | admitted replacement Query Candidate ID |
| `retire_subquestion` | one active same-goal subquestion with no active Query Candidate or pending capability use | `null` | `null` | `null` |
| `retire_query_candidate` | one active same-goal Query Candidate with no pending capability use referencing it | `null` | `null` | `null` |

Every cell is exact: a required value cannot be `null`, a `null` cell cannot be
present, and a replacement of the wrong entity kind rejects the adjustment.
`replacementSubquestion.goalRef` must equal both the adjustment goal and the
target goal. `replacementQueryCandidate.subquestionRef` must equal the target
candidate's still-active subquestion and cannot move the candidate to another
subquestion. A subquestion cannot be retired or superseded while active child
Query Candidates remain; those candidates must first be retired or superseded
through their own explicit adjustments. A replacement is admitted atomically
with its edge; if it fails any ordinary source, neutrality, bound, or dependency
rule, neither the replacement nor adjustment is admitted.

Run-wide cumulative bounds count every record ever admitted, including retired and superseded records: at most 12 subquestion versions, 16 Query Candidate versions, 32 local adjustments, and 4 versions in any one supersession lineage. Each goal has at most 8 adjustments. Per-proposal bounds are additional, not replacements for these totals. Retirement never refunds a structural bound, and a proposal whose atomic admission would cross any cumulative bound rejects the overflowing item and every dependent item before state commit.

A proposed new goal, cross-goal move, purpose change, effect escalation, newly introduced data source, dependency expansion, actor/Case change, or material reinterpretation is not a local adjustment. The Run stops `blocked` with `new_task_required` when an actor choice or new authorization is needed, or with the applicable dependency/capability reason otherwise. A later user prompt may start a new Run after Task Understanding and continuity admission. The current Run is never suspended as a hidden resumable planner.

Control decisions are staged with the normal Pi save point that owns the model turn or finalized tool outcome which caused them. There is no special planning save point.

## 8. Workspace Capability admission

```typescript
interface TrustedWorkspaceCapabilitySnapshotV1 {
	protocol: "workspace-capability-snapshot/v1";
	snapshotRef: string;
	snapshotRevision: number;
	entries: readonly TrustedWorkspaceCapabilityEntryV1[];
	snapshotDigest: string;
}

interface TrustedWorkspaceCapabilityEntryV1 {
	capabilityRef: string;
	descriptor: ModelVisibleCapabilityDescriptorV1;
	schemaDigest: string;
	configurationDigest: string;
	effectClass: "read_only" | "effectful";
	qualifiedDependencyRefs: readonly string[];
	allowedGoalRefs: readonly string[];
	maxUses: number;
	modelVisible: boolean;
}

interface ModelVisibleCapabilityDescriptorV1 {
	name: string;
	description: string;
	inputSchema: RunCanonicalJsonV1;
	descriptorDigest: string;
}

interface AdmittedCapabilityUseV1 {
	capabilityUseId: string;
	capabilityRef: string;
	capabilitySnapshotRef: string;
	capabilitySnapshotDigest: string;
	goalRef: string;
	subquestionRef: string | null;
	queryCandidateRefs: readonly string[];
	purpose: "investigate" | "validate" | "corroborate";
	input: RunCanonicalJsonV1;
	inputDigest: string;
	decisionDigest: string;
}
```

The trusted Workspace constructs the snapshot from current actor, Case, purpose, task, dependency qualification, authorization, and budget facts. The model sees only entries with `modelVisible: true`; hidden capabilities cannot be requested by guessing their refs.

The model-visible capability catalog exposes only a Workspace-minted `capabilityRef` and its exact `descriptor`. Configuration digests, dependency refs, authorization revisions, credentials, and backend details remain Workspace-only even when the corresponding entry is model-visible. The descriptor name is 1-128 ASCII characters, the description is 1-1,024 UTF-8 bytes, and its closed JSON Schema is at most depth 12, 2,048 members/items, and 64 KiB RFC 8785 JCS. A snapshot has at most 32 entries; each entry has at most 8 dependency refs, 4 allowed goal refs, and `maxUses` in `[0, 64]`.

A request is admitted only when its exact ref exists, all referenced entities are active and same-goal, the capability permits that goal and purpose, its recursively owned `input` is closed canonical JSON and validates against the exact descriptor schema, its schema/configuration/descriptor digests match the activated Pi tool schema, all dependencies remain qualified, `maxUses` and Run budgets permit another use, and current authorization still matches the basis. Proposed input is at most depth 12, 2,048 members/items, and 64 KiB JCS. Admission snapshots the input, computes `inputDigest`, and produces a use candidate bound to the exact snapshot; it does not modify the snapshot or tool registry.

Capability memory is bounded cumulatively, not merely per entry:

- at most 64 capability uses may ever be admitted in one Run;
- UTF-8 JCS bytes of all admitted capability inputs ever recorded in the Run
  sum to at most 1,048,576;
- UTF-8 JCS bytes of all model-visible descriptors and schemas in the trusted
  snapshot sum to at most 1,048,576; and
- UTF-8 JCS bytes of the complete `AdmittedInvestigationRunStateV1` sum to at
  most 4,194,304 after any proposed transition.

The counters use the canonical stored values and checked integer addition.
Retirement, supersession, settlement, or a later smaller snapshot never refunds
an ever-admitted use/input byte. A proposal whose atomic result would cross any
limit rejects the overflowing capability request and every dependent item before
state commit; it cannot truncate inputs, schemas, or prior state.

Actor, Case, purpose, credentials, dependency handles, resource selectors, backend options, retry, timeout, commit, and effect authority are not legal model-input fields unless a future accepted capability contract explicitly exposes a safe value. Trusted Tool Adapters bind every non-model field after admission and revalidate the capability-use digest before execution. No model input can override a trusted binding.

The model cannot activate, configure, rename, retry, parallelize, or delegate a capability. A prompt, Query Candidate, tool result, or previously admitted use cannot authorize another use. `effectful` entries are reserved for a future accepted contract and are rejected by the first no-tool slice.

Capability configuration may change only at an accepted Pi save-point boundary. Drift before dispatch fences the Run; drift while an operation is in flight prevents its result from becoming eligible until the owning contract revalidates it. V1 performs no I&E retrieval and no Case write.

## 9. Run budgets and ledger

### 9.1 Trusted hard limits

```typescript
interface InvestigationRunBudgetPolicyV1 {
	protocol: "workspace-investigation-run-budget/v1";
	policyRef: string;
	maxModelTurns: number;
	maxToolCalls: number;
	maxInputTokens: number;
	maxOutputTokens: number;
	maxTotalTokens: number;
	maxElapsedMs: number;
	maxCostMicros: number;
	costCurrency: string;
	pricingRef: string;
	pricingRevision: string;
	pricingDigest: string;
	policyDigest: string;
}

interface TrustedRunPricingSnapshotV1 {
	protocol: "workspace-run-pricing-snapshot/v1";
	pricingRef: string;
	pricingRevision: string;
	costCurrency: string;
	entries: readonly TrustedRunPricingEntryV1[];
	pricingDigest: string;
}

type TrustedRunPricingEntryV1 =
	| {
			kind: "provider";
			modelRef: string;
			fixedCostMicros: number;
			maxInputMicrosPerMillionTokens: number;
			maxOutputMicrosPerMillionTokens: number;
	  }
	| {
			kind: "capability";
			capabilityRef: string;
			maxCostMicrosPerCall: number;
	  };

interface InvestigationRunBudgetAmountsV1 {
	modelTurns: number;
	toolCalls: number;
	inputTokens: number;
	outputTokens: number;
	totalTokens: number;
	elapsedMs: number;
	costMicros: number;
}

interface InvestigationRunBudgetLedgerV1 {
	limits: InvestigationRunBudgetAmountsV1;
	committed: InvestigationRunBudgetAmountsV1;
	reserved: InvestigationRunBudgetAmountsV1;
	unknown: InvestigationRunBudgetAmountsV1;
	costCurrency: string;
	pricingDigest: string;
	ledgerSequence: number;
	ledgerDigest: string;
}

interface RunBudgetReservationCandidateV1 {
	protocol: "workspace-run-budget-reservation-candidate/v1";
	reservationRef: string;
	actionKind: "provider" | "tool_batch";
	actionRef: string;
	runId: string;
	runGeneration: number;
	basisDigest: string;
	priorControlStateDigest: string;
	reservedControlStateDigest: string;
	priorLedgerDigest: string;
	amounts: InvestigationRunBudgetAmountsV1;
	costCurrency: string;
	pricingDigest: string;
	expectedSessionLeafId: string;
	candidateDigest: string;
}

interface DurableRunBudgetReservationReceiptV1 {
	protocol: "workspace-run-budget-reservation-receipt/v1";
	candidateDigest: string;
	reservationRef: string;
	actionKind: "provider" | "tool_batch";
	actionRef: string;
	runId: string;
	runGeneration: number;
	basisDigest: string;
	priorControlStateDigest: string;
	reservedControlStateDigest: string;
	priorLedgerDigest: string;
	reservedLedgerDigest: string;
	amounts: InvestigationRunBudgetAmountsV1;
	costCurrency: string;
	pricingDigest: string;
	expectedSessionLeafId: string;
	terminalEntryId: string;
	resultingSessionLeafId: string;
	receiptDigest: string;
	authenticity: RunControlReceiptAuthenticityV1;
}

interface RunControlReceiptAuthenticityV1 {
	protocol: "workspace-run-control-receipt-authenticity/v1";
	algorithm: "hmac-sha256";
	keyId: string;
	signedPayloadDigest: string;
	macBase64Url: string;
}

interface RunDispatchPermitBindingV1 {
	permitRef: string;
	reservationRef: string;
	reservationReceiptDigest: string;
	reservationTerminalEntryId: string;
	resultingSessionLeafId: string;
	actionRef: string;
	runGeneration: number;
	controlStateDigest: string;
	permitBindingDigest: string;
}
```

The five budget categories are turns, tools, tokens, elapsed time, and cost. Tokens have input, output, and total ceilings. All values are non-negative safe integers. Cost is integer micros, never floating point. `costCurrency` is exactly three uppercase ASCII letters and is constant for the Run. `pricingRef`, revision, and digest identify one trusted immutable pricing table for every activated model and capability. `maxCostMicros: 0` permits only entries whose trusted maximum and final cost are both zero. The trusted application supplies policy and pricing; model text cannot change either.

V1 configuration bounds are:

| Field | Minimum | Maximum |
| --- | ---: | ---: |
| `maxModelTurns` | 1 | 64 |
| `maxToolCalls` | 0 | 256 |
| `maxInputTokens` | 1 | 10,000,000 |
| `maxOutputTokens` | 1 | 10,000,000 |
| `maxTotalTokens` | 1 | 20,000,000 |
| `maxElapsedMs` | 1 | 86,400,000 |
| `maxCostMicros` | 0 | 1,000,000,000,000 |

The configured total-token ceiling must be no greater than input plus output ceilings. Product defaults must be materially smaller than these schema maxima and are versioned trusted configuration.

The pricing snapshot has exactly one entry for every activated model/capability and no duplicate key. It has at most 33 entries, and every rate/cost is a non-negative safe integer no greater than `1,000,000,000,000`. Provider maximum cost is `fixedCostMicros + ceil(inputTokens * maxInputMicrosPerMillionTokens / 1,000,000) + ceil(outputTokens * maxOutputMicrosPerMillionTokens / 1,000,000)`, using checked integer arithmetic. The maximum input/output rates conservatively cover every configured cache, reasoning, service-tier, and other token billing mode for that prepared invocation; an unrepresented billing mode denies dispatch. Capability maximum cost is its exact `maxCostMicrosPerCall`. No discount, optimistic cache assumption, floating-point rounding, runtime price discovery, or model-provided price is permitted. The policy and pricing snapshot refs/revisions/currency/digests must match byte-for-byte. The first fake no-tool slice uses a trusted zero-cost entry and does not activate a paid Provider.

For each of `committed`, `reserved`, and `unknown`, `totalTokens` equals `inputTokens + outputTokens`. Their component-wise sum never exceeds `limits`; `limits.totalTokens` is an independent ceiling and need not equal the sum of its input/output ceilings. `committed.elapsedMs` equals the greatest admitted monotonic observation, while reserved/unknown elapsed values are zero. Ledger and pricing digests, currency, and sequence are included in every reservation, reconciliation, save point, and settlement candidate. Arithmetic overflow, currency mismatch, pricing drift, sequence reuse, a negative delta, or an amount moving between dimensions is `budget_reconciliation_invalid`.

### 9.2 Reservation before dispatch

Before each Provider dispatch, Pi supplies a trusted conservative reservation containing one model turn, the authorized input-token bound, maximum output tokens, total-token bound, and maximum cost derived from the exact prepared invocation and the basis-bound pricing table. Before each tool batch, Pi supplies the complete source-ordered set of tool-count and trusted cost reservations. Every reservation repeats and matches the exact currency and pricing digest. The Workspace admits the reservation atomically only when:

```text
committed + reserved + unknown + proposed <= limits
```

for turns, tools, input/output/total tokens, and cost. Elapsed time is not additive: `committed.elapsedMs` is the greatest trusted elapsed observation, every reserved/unknown elapsed amount is zero, and a dispatch is allowed only while the current elapsed time is strictly below `maxElapsedMs`. Pi gives the started action the remaining monotonic deadline and fences it when that deadline expires. A missing token bound, missing applicable price, overflow, negative value, non-monotonic time, or unknown charge that could exceed the limit denies dispatch. No optimistic expected usage is used as a hard-budget reservation.

A Provider reservation has `modelTurns: 1`, `toolCalls: 0`, `totalTokens` equal to input plus output tokens, and zero elapsed amount. Each tool reservation has `modelTurns: 0`, `toolCalls: 1`, zero token amounts unless a future owning contract proves a token-bearing tool charge, zero elapsed amount, and its trusted maximum cost. Fields that do not apply must be zero; they cannot carry spare budget between dimensions.

Parallel tool calls are reserved as one batch before Pi starts any member. The policy does not race per-call checks. If the whole batch does not fit, none starts; a later model turn may propose a smaller batch if a turn itself still fits.

A numerically fitting reservation is not yet dispatch authority. `reservation_required` is a pre-commit candidate: it leaves the current state/control sequence unchanged and supplies the exact reserved-state digest that would result. The coordinator commits one A4 receipt-last control group with zero prior entries and one physically last custom entry `workspace_run_budget_reservation_v1` containing exact `DurableRunBudgetReservationReceiptV1` data. Its expected leaf, prior/reserved ledger digests, prior/reserved control-state digests, candidate digest, reservation amounts, currency, pricing digest, Run generation, terminal ID, and resulting leaf must all match the prepared A4 preview. No Provider or tool Adapter starts before this group is `committed` or one authoritative lookup proves the complete batch `exact_present` at its terminal leaf.

`acknowledgement_unknown` performs exactly one same-Session authoritative A4 lookup with the retained batch evidence. `exact_present` may proceed; `absent`, `conflict`, or `unavailable` starts nothing, creates no permit, never recommits, and stops with the exact reservation persistence failure. Preparation conflict/invalid/unavailable and invalid terminal likewise start nothing. A later process cannot reconstruct a permit merely from a persisted receipt.

Before sealing the budget reservation, Workspace verifies the exact basis-bound receipt authenticator. `receiptDigest = piDigest(the complete reservation receipt with receiptDigest and authenticity omitted)`; `signedPayloadDigest = piDigest(the complete reservation receipt with authenticity omitted)`; `macBase64Url` is unpadded base64url HMAC-SHA-256 over the exact UTF-8 RFC 8785 JCS bytes of that same receipt-without-authenticity payload. Key material never enters the basis or receipt. Authenticator/key revision drift, signing failure, or one-field verification mismatch abandons the A4 preparation and appends nothing. The Run-owned Workspace settlement terminal uses this same HMAC authenticity shape and canonical formula. PNW supplies generic materialization evidence for the exact terminal entry and does not sign or authenticate the application payload.

After committed/exact presence, Pi mints one non-serializable object-identity permit whose safe binding is `RunDispatchPermitBindingV1`. The permit is usable only for the exact action, reservation receipt, resulting Session leaf, state digest, Run generation, and resident prepared Provider/tool value. Permit consumption is synchronous and once-only immediately before Adapter entry. Cancellation, leaf/state/generation drift, a duplicate consume, missing resident value, or retirement burns it and starts nothing. A durable reservation with an unused/burned permit moves to `unknown` unless authoritative facts prove the action never started; it is never silently released or reused.

### 9.3 Reconciliation and uncertainty

Only Pi-authoritative provider usage/acknowledgement and finalized tool outcomes in the same currency/pricing revision reconcile a reservation. Reconciliation moves amounts from `reserved` to `committed` exactly once. A lower actual charge releases only the proven difference. A higher actual charge is an integrity failure and the excess remains charged; it never creates negative remaining budget. A duplicate exact reconciliation is idempotent; a different second reconciliation fails without changing the ledger.

If a started action loses acknowledgement, times out after dispatch, is cancelled in flight, returns late, or has incomplete usage/cost data, its conservative reservation moves to `unknown`. Unknown amounts count as consumed for this Run and are never reused by another generation. Later authoritative reconciliation may reduce them only in the retired Run ledger; it cannot authorize new work after terminal settlement.

Elapsed time is the trusted monotonic duration from formal Run admission through the current observation. It never decreases and does not pause for model, tool, cancellation, or settlement waits. Crossing the deadline fences new dispatch immediately. Time spent by a detached late operation is recorded for diagnostics but cannot reopen the Run.

Budget exhaustion never triggers automatic retry, model fallback, smaller-model substitution, tool substitution, silent goal dropping, or a new Agent Run.

## 10. Observations, decisions, and admitted state

```typescript
type InvestigationRunObservationV1 =
	| RunStartObservationV1
	| ModelProposalObservationV1
	| PreProviderDispatchObservationV1
	| RunReservationDurabilityObservationV1
	| RunDispatchStartedObservationV1
	| ProviderUsageFinalizedObservationV1
	| PreToolBatchDispatchObservationV1
	| ToolBatchFinalizedObservationV1
	| AgentRunEndedObservationV1
	| RunBasisInvalidatedObservationV1
	| RunCancellationObservationV1
	| RunSettlementPreparationObservationV1
	| RunSettlementCommittedObservationV1;

interface RunObservationHeaderV1 {
	runId: string;
	runGeneration: number;
	basisDigest: string;
	expectedControlSequence: number;
	elapsedMs: number;
}

interface RunStartObservationV1 extends RunObservationHeaderV1 {
	kind: "run_start";
	sourceCatalog: RunSourceCatalogV1;
}

interface ModelProposalObservationV1 extends RunObservationHeaderV1 {
	kind: "model_proposal";
	proposal: InvestigationControlProposalV1;
}

interface PreProviderDispatchObservationV1 extends RunObservationHeaderV1 {
	kind: "pre_provider_dispatch";
	invocationRef: string;
	reservation: InvestigationRunBudgetAmountsV1;
}

interface RunReservationDurabilityObservationV1 extends RunObservationHeaderV1 {
	kind: "reservation_durability";
	candidate: RunBudgetReservationCandidateV1;
	commitOutcome: RunControlA4WriteOutcomeV1;
	lookupOutcome: RunControlA4LookupOutcomeV1 | null;
	receipt: DurableRunBudgetReservationReceiptV1 | null;
	a4EvidenceDigest: string | null;
}

interface RunDispatchStartedObservationV1 extends RunObservationHeaderV1 {
	kind: "dispatch_started";
	dispatchKind: "provider" | "tool_batch";
	permit: RunDispatchPermitBindingV1;
	actionRef: string;
	providerDispatchReceipt: BoundRecordRefV1 | null;
	resultingSessionLeafId: string;
}

interface ProviderUsageFinalizedObservationV1 extends RunObservationHeaderV1 {
	kind: "provider_usage_finalized";
	invocationRef: string;
	acknowledgement: "acknowledged" | "unknown";
	actual: InvestigationRunBudgetAmountsV1 | null;
	costCurrency: string;
	pricingDigest: string;
}

interface PreToolBatchDispatchObservationV1 extends RunObservationHeaderV1 {
	kind: "pre_tool_batch_dispatch";
	uses: readonly AdmittedCapabilityUseV1[];
	reservations: readonly InvestigationRunBudgetAmountsV1[];
}

interface ToolBatchFinalizedObservationV1 extends RunObservationHeaderV1 {
	kind: "tool_batch_finalized";
	outcomes: readonly FinalizedToolOutcomeFactV1[];
	costCurrency: string;
	pricingDigest: string;
}

interface AgentRunEndedObservationV1 extends RunObservationHeaderV1 {
	kind: "agent_run_ended";
	responseCandidateRef: string;
	responseCandidateDigest: string;
	finalGoalAssessments: readonly FinalGoalAssessmentCandidateV1[];
	stop: ProposedRunStopV1;
}

interface FinalizedToolOutcomeFactV1 {
	capabilityUseId: string;
	status: "completed" | "failed" | "cancelled" | "unknown";
	actualCostMicros: number | null;
	outcomeDigest: string | null;
}

interface RunBasisInvalidatedObservationV1 extends RunObservationHeaderV1 {
	kind: "basis_invalidated";
	reason: RunInvalidationReasonV1;
}

type RunInvalidationReasonV1 =
	| "actor_authorization_changed"
	| "case_visibility_changed"
	| "purpose_changed"
	| "session_continuity_changed"
	| "context_generation_changed"
	| "case_context_changed"
	| "capability_snapshot_changed"
	| "lease_generation_changed";

interface RunCancellationObservationV1 extends RunObservationHeaderV1 {
	kind: "cancel_requested";
	source: "caller" | "workspace_close" | "pi_supersession";
}

interface RunSettlementPreparationObservationV1 extends RunObservationHeaderV1 {
	kind: "settlement_prepare";
	finalSavePointRef: string;
	finalSavePointDigest: string;
	expectedSessionLeafId: string;
	pendingActions: RunPendingActionSetV1;
	piRunState: "ready_to_settle" | "interrupted";
}

interface RunSettlementCommittedObservationV1 extends RunObservationHeaderV1 {
	kind: "settlement_committed";
	candidateDigest: string;
	commitOutcome: RunControlA4WriteOutcomeV1;
	lookupOutcome: RunControlA4LookupOutcomeV1 | null;
	settlement: SettledAgentRunBindingV1 | null;
	a4EvidenceDigest: string | null;
}

type RunControlA4WriteOutcomeV1 =
	| "committed"
	| "acknowledgement_unknown"
	| "prepare_conflict"
	| "prepare_invalid_draft"
	| "prepare_unsupported"
	| "prepare_unavailable_io"
	| "prepare_unavailable_invalid_or_truncated"
	| "prepare_unavailable_unsupported"
	| "seal_invalid_terminal"
	| "commit_conflict";

type RunControlA4LookupOutcomeV1 =
	| "exact_present"
	| "absent"
	| "conflict"
	| "unavailable_io"
	| "unavailable_invalid_or_truncated"
	| "unavailable_unsupported";

interface RunPendingActionSetV1 {
	providerInvocationRefs: readonly string[];
	capabilityUseRefs: readonly string[];
	reservationRefs: readonly string[];
	unusedPermitRefs: readonly string[];
	unknownAcknowledgementRefs: readonly string[];
	setDigest: string;
}

type InvestigationRunControlDecisionV1 =
	| RunContinueDecisionV1
	| RunReservationRequiredDecisionV1
	| RunDispatchAdmittedDecisionV1
	| RunDispatchDeniedDecisionV1
	| RunStopDecisionV1
	| RunSettlementPreparedDecisionV1
	| RunSettlementCommittedDecisionV1
	| RunObservationDiscardedDecisionV1;

interface RunDecisionHeaderV1 {
	protocol: "workspace-investigation-run-control-decision/v1";
	runId: string;
	runGeneration: number;
	basisDigest: string;
	previousControlSequence: number;
	nextControlSequence: number;
	decisionDigest: string;
}

interface RunContinueDecisionV1 extends RunDecisionHeaderV1 {
	kind: "continue";
	admissions: readonly ControlItemAdmissionV1[];
	state: AdmittedInvestigationRunStateV1;
}

interface RunReservationRequiredDecisionV1 extends RunDecisionHeaderV1 {
	kind: "reservation_required";
	reservation: RunBudgetReservationCandidateV1;
	candidateStateDigest: string;
	state: AdmittedInvestigationRunStateV1;
}

interface RunDispatchAdmittedDecisionV1 extends RunDecisionHeaderV1 {
	kind: "dispatch_admitted";
	dispatchKind: "provider" | "tool_batch";
	dispatchRef: string;
	reservation: InvestigationRunBudgetAmountsV1;
	durableReservation: DurableRunBudgetReservationReceiptV1;
	permit: RunDispatchPermitBindingV1;
	state: AdmittedInvestigationRunStateV1;
}

interface RunDispatchDeniedDecisionV1 extends RunDecisionHeaderV1 {
	kind: "dispatch_denied";
	dispatchKind: "provider" | "tool_batch";
	dispatchRef: string;
	reason:
		| "cancelled"
		| "stale_basis"
		| "capability_denied"
		| "budget_denied"
		| "run_stopping"
		| "run_settled";
	failure: InvestigationRunFailureV1 | null;
	state: AdmittedInvestigationRunStateV1;
}

interface RunStopDecisionV1 extends RunDecisionHeaderV1 {
	kind: "stop";
	disposition: InvestigationRunDispositionV1;
	reasonCode: InvestigationRunStopReasonV1;
	goalStatuses: Readonly<Record<string, InvestigationGoalStatusV1>>;
	failure: InvestigationRunFailureV1 | null;
	admissions: readonly ControlItemAdmissionV1[];
	state: AdmittedInvestigationRunStateV1;
}

interface ControlItemAdmissionV1 {
	itemKind: "subquestion" | "query_candidate" | "capability_use" | "local_adjustment";
	proposalLocalRef: string;
	decision: "admitted" | "rejected";
	reason: ControlItemAdmissionReasonV1;
	admittedRef: string | null;
}

type ControlItemAdmissionReasonV1 =
	| "admitted"
	| "source_reference_invalid"
	| "out_of_scope"
	| "bound_exceeded"
	| "target_not_neutral"
	| "dependent_item_rejected"
	| "adjustment_not_local"
	| "capability_unavailable"
	| "capability_unauthorized"
	| "capability_input_invalid"
	| "capability_budget_denied";

interface RunSettlementPreparedDecisionV1 extends RunDecisionHeaderV1 {
	kind: "settlement_prepared";
	settlement: AgentRunSettlementCandidateV1;
	state: AdmittedInvestigationRunStateV1;
}

interface AgentRunSettlementCandidateV1 {
	protocol: "workspace-investigation-run-settlement-candidate/v1";
	runId: string;
	runGeneration: number;
	disposition: InvestigationRunDispositionV1;
	basisDigest: string;
	finalSavePointRef: string;
	finalSavePointDigest: string;
	controlStateDigest: string;
	budgetLedgerDigest: string;
	finalGoalAssessmentDigests: readonly string[];
	goalStatusDigest: string;
	providerTerminal: AcceptedProviderTerminalCandidateSlotV1;
	workspaceDecisionRef: string;
	workspaceDecisionDigest: string;
	responseCandidate: ResponseCandidateBindingSlotV1;
	pendingActions: RunPendingActionSetV1;
	failure: InvestigationRunFailureV1 | null;
	expectedSessionLeafId: string;
	digest: string;
}

type AcceptedProviderTerminalCandidateSlotV1 =
	| {
		presence: "present";
		acceptedProviderTerminalRef: string;
		acceptedProviderTerminalDigest: string;
	  }
	| { presence: "absent" };

type ResponseCandidateBindingSlotV1 =
	| {
		presence: "present";
		responseCandidateRef: string;
		responseCandidateDigest: string;
	  }
	| { presence: "absent" };

interface WorkspaceAgentRunSettlementTerminalV1 {
	protocol: "workspace-agent-run-settlement-terminal/v1";
	settlementRef: string;
	receiptDigest: string;
	candidateDigest: string;
	runId: string;
	runGeneration: number;
	disposition: InvestigationRunDispositionV1;
	basisDigest: string;
	finalSavePointRef: string;
	finalSavePointDigest: string;
	controlStateDigest: string;
	budgetLedgerDigest: string;
	finalGoalAssessmentDigests: readonly string[];
	goalStatusDigest: string;
	responseCandidateRef: string | null;
	responseCandidateDigest: string | null;
	acceptedProviderTerminalRef: string | null;
	acceptedProviderTerminalDigest: string | null;
	pendingActions: RunPendingActionSetV1;
	failure: InvestigationRunFailureV1 | null;
	expectedSessionLeafId: string;
	terminalEntryId: string;
	resultingSessionLeafId: string;
	authenticity: RunControlReceiptAuthenticityV1;
}

interface SettledAgentRunBindingV1 {
	piSettlement: PiAgentRunSettlementEvidenceV1;
	workspaceTerminal: WorkspaceAgentRunSettlementTerminalV1;
}

interface RunSettlementCommittedDecisionV1 extends RunDecisionHeaderV1 {
	kind: "settlement_committed";
	settlement: SettledAgentRunBindingV1;
	state: AdmittedInvestigationRunStateV1;
}

interface RunObservationDiscardedDecisionV1 extends RunDecisionHeaderV1 {
	kind: "observation_discarded";
	reason: "stale_generation" | "stale_basis" | "already_settled" | "exact_replay";
	state: AdmittedInvestigationRunStateV1;
}

interface AdmittedInvestigationRunStateV1 {
	protocol: "workspace-admitted-investigation-run-state/v1";
	runId: string;
	runGeneration: number;
	basisDigest: string;
	controlSequence: number;
	status: "active" | "stopping" | "settled" | "retired";
	currentSessionLeafId: string;
	goals: readonly InvestigationGoalV1[];
	goalAssessments: readonly AdmittedGoalAssessmentV1[];
	subquestions: readonly AdmittedSubquestionV1[];
	queryCandidates: readonly AdmittedQueryCandidateV1[];
	adjustments: readonly AdmittedLocalAdjustmentV1[];
	capabilityUses: readonly AdmittedCapabilityUseV1[];
	sourceCatalogRef: string;
	sourceCatalogDigest: string;
	budgetLedger: InvestigationRunBudgetLedgerV1;
	pendingProviderRefs: readonly string[];
	pendingCapabilityUseRefs: readonly string[];
	pendingReservationRefs: readonly string[];
	unusedPermitRefs: readonly string[];
	unknownAcknowledgementRefs: readonly string[];
	disposition: InvestigationRunDispositionV1 | null;
	settlementRef: string | null;
	settlementDigest: string | null;
	stateDigest: string;
}

interface AdmittedGoalAssessmentV1 {
	assessmentId: string;
	controlSequence: number;
	goalRef: string;
	status: InvestigationGoalStatusV1;
	supportSourceRefs: readonly string[];
	responseSegmentRefs: readonly string[];
	uncertainty: string | null;
	assessmentDigest: string;
}

interface AdmittedSubquestionV1 {
	subquestionId: string;
	version: number;
	goalRef: string;
	question: string;
	supportSourceRefs: readonly string[];
	assumptions: readonly string[];
	supersedesSubquestionRef: string | null;
	status: "active" | "addressed" | "retired" | "superseded";
	proposalDigest: string;
}
```

Every admitted decision returns a new immutable `AdmittedInvestigationRunStateV1` with a strictly incremented control sequence and canonical digest. `reservation_required` and `settlement_prepared` are the two pre-commit exceptions: `nextControlSequence` equals `previousControlSequence`, their returned state is the unchanged prior state, and their candidate records the exact would-be transition. Only committed/exact-present reservation durability produces `dispatch_admitted`, advances the sequence, installs the reserved ledger/state, and mints the single-use permit. Only committed/exact-present settlement produces `settlement_committed` and the terminal state. State contains only admitted goals, active and superseded subquestions/Query Candidates, capability-use decisions, source catalog ref/digest, budget ledger, pending-action refs, stop disposition, and settlement ref/digest. It does not duplicate model messages, tool bodies, CTI evidence, or the Pi transcript.

In a settled state, `settlementRef` and `settlementDigest` are respectively the
exact `WorkspaceAgentRunSettlementTerminalV1.settlementRef` and `receiptDigest`.
They are both `null` before settlement and all-present after it; they never point
to an unsigned candidate or to the separate PNW materialization-evidence record.

`nextControlSequence` equals `previousControlSequence + 1` for a new committed decision. An exact replay returns the prior immutable decision and does not increment the sequence, reserve budget again, or create another Session entry. `dispatch_admitted` is a single-use Pi permit bound to the exact dispatch ref, state digest, reservation, and generation; it is not reusable after any state transition.

`run_start` is the only observation allowed with `state: null`; every other observation requires the exact preceding state. Structural validation is all-or-nothing. After it passes, semantic item decisions are evaluated in source order and the complete admission/rejection set commits atomically as one state transition. Independent valid items may be admitted while invalid items are rejected, but no dependent item may survive a rejected dependency. A denial that proves the Run must stop returns `stop`, not a transient `dispatch_denied` followed by another race-prone decision.

`currentSessionLeafId` begins at the basis head and advances only through exact Run-owned control groups, the PNW Provider Dispatch receipt, normal Pi save points, and settlement. These internal advances do not change the fixed semantic basis or Context Generation. Any external/unrecognized leaf advance fences the Run. A provider `dispatch_started` requires an exact current-generation PNW dispatch receipt and its resulting leaf; a tool batch has `providerDispatchReceipt: null` and retains the reservation leaf until its owning Pi save point.

For both durability observations, `lookupOutcome` is non-null if and only if `commitOutcome` is `acknowledgement_unknown`. `committed` and `acknowledgement_unknown` carry the retained A4 evidence and exact preview-built receipt; other commit outcomes carry neither. `acknowledgement_unknown + exact_present` may advance; the other lookup results cannot. Any impossible combination is a protocol failure. Receipt, evidence, candidate, state, leaf, currency/pricing, pending-ref, or digest mismatch is never normalized into success.

Every negative reservation write/lookup result maps to `budget_reservation_persistence_failed`; every negative settlement write/lookup result maps to `agent_run_settlement_failed`. The internal stage/outcome remains safe telemetry but does not become provider authority or invite retry. `prepare_invalid_draft`, `seal_invalid_terminal`, receipt/authentication mismatch, and an impossible outcome combination additionally use failure stage `reservation` or `settlement` with reason `protocol_or_integrity_failure`; no second write is attempted.

## 11. Stop semantics and precedence

```typescript
type InvestigationRunDispositionV1 =
	| "completed"
	| "insufficient_evidence"
	| "budget_exhausted"
	| "blocked"
	| "failed"
	| "cancelled"
	| "discarded";

interface ProposedRunStopV1 {
	disposition:
		| "completed"
		| "insufficient_evidence"
		| "budget_exhausted"
		| "blocked";
	goalRefs: readonly string[];
	reasonCode: ProposedStopReasonV1;
	supportSourceRefs: readonly string[];
}

type ProposedStopReasonV1 =
	| "requested_outcomes_addressed"
	| "no_admitted_action_can_improve_evidence"
	| "necessary_action_exceeds_budget"
	| "required_capability_or_dependency_unavailable"
	| "new_task_required";

type InvestigationRunStopReasonV1 =
	| ProposedStopReasonV1
	| "caller_cancelled"
	| "workspace_closed"
	| "run_superseded"
	| "recovery_discarded"
	| "protocol_or_integrity_failure"
	| "provider_failure"
	| "tool_failure"
	| "save_point_failure"
	| "settlement_failure"
	| "authorization_unavailable"
	| "dependency_unavailable"
	| "capability_unavailable"
	| "scope_or_task_conflict"
	| "model_turn_budget_exhausted"
	| "tool_budget_exhausted"
	| "token_budget_exhausted"
	| "time_budget_exhausted"
	| "cost_budget_exhausted";
```

A model stop is a proposal. The Workspace derives exactly one Run disposition from trusted state and facts, using this precedence:

`goalRefs` contains every goal whose final assessment has the proposed
disposition, in goal order. Empty, duplicate, extra, or omitted affected goals
reject the stop proposal.

1. `cancelled` when caller cancellation or Workspace close wins before settlement commit;
2. `discarded` when Pi supersession or recovery retirement wins before another substantive disposition commits;
3. `failed` for integrity, protocol, impossible reconciliation, Provider, tool, save-point, or settlement failure that is not a normal evidence limitation;
4. `blocked` when the current task is still meaningful but current authorization,
   qualified dependency, capability, or basis required for a necessary action is
   unavailable, or when an actor choice/new authorization would require a new
   Task Understanding turn;
5. `budget_exhausted` when a necessary otherwise-admissible next action cannot
   fit at least one hard budget and no already-admitted result can structurally
   cover all goals;
6. `insufficient_evidence` when the basis is valid and budgets are not the
   limiting cause, but no currently admitted action can materially improve the
   available evidence for one or more goals; and
7. `completed` only when every admitted goal is structurally addressed and the
   completion fence below passes.

The higher applicable disposition wins. A model cannot relabel an authorization failure as insufficient evidence, a budget failure as completion, or an internal failure as blocked. PNW v1 permits clarification only before a Run, so Run Control v1 emits no `clarification_required` disposition, question, or public terminal. A new actor choice is `blocked/new_task_required`; any later answer is a new public prompt processed by Task Understanding. Adding Run-time clarification would require explicit PNW and WOP amendments and independent acceptance first.

A stale or late observation normally returns `observation_discarded` and does not change the current Run's disposition. It records `discarded` only for the retired Run to which it belongs when that Run has no earlier terminal disposition. This prevents an old callback from terminating a newer Run.

An `agent_run_ended` observation is the no-tool slice's terminal proposal carrier. It binds one `ModelResponseCandidateV1` ref/digest and one stop proposal from the same final model turn; it is not a product tool, second call, or public output. The Workspace admits a final disposition only when all of the following pre-settlement facts hold:

- `finalGoalAssessments` contains exactly one item per admitted goal in goal ordinal order, with no extra or duplicate goal ref;
- every `responseSegmentRef` is a distinct claim ID that resolves exactly once
  inside that bound `ModelResponseCandidateV1`, and every citation of that claim
  resolves to a current source-catalog entry assigned to the same goal;
- `addressed` has 1-16 response segment refs and at least one current support
  ref, while every non-addressed status has zero response segment refs; no claim,
  citation, or source can be borrowed from another goal;
- final assessment statuses and the proposed aggregate stop agree with deterministic precedence; one unresolved goal prevents aggregate `completed`;
- `completed` requires every goal to be `addressed` and the candidate outcome to
  be `completed`; the candidate has one or more claims as WOP requires;
- `insufficient_evidence`, `budget_exhausted`, and `blocked` require every final
  goal status to equal the aggregate disposition, every response-segment list to
  be empty, the candidate outcome to equal the disposition, and candidate
  `claims` to be empty as WOP requires. A mixed addressed/non-addressed terminal
  candidate is rejected rather than publishing partial claims under a
  non-completed notice;
- no active subquestion, capability use, Provider invocation, tool call, reservation, unknown acknowledgement, or local adjustment is pending;
- the Original User Task, admitted Task Context, actor/Case/purpose, branch, Context Generation, layered Case context, capability snapshot, and Run generation still match the trusted basis;
- the final response candidate is bound to the same Run, generation, basis, and goal set and has not been exposed to the caller.

That stop decision moves the state to `stopping`; it is not yet a terminal completion. `settlement_prepare` then requires the final Pi save point containing all admitted Run Control decisions and finalized outcomes. Only `settlement_committed`, bound to that exact save point and the prepared settlement digest, makes `completed` or any other intended disposition terminal. Missing or duplicate settlement prevents terminal completion.

Settlement preparation recomputes `RunPendingActionSetV1` independently from Pi's finalized Run registry and the Workspace state. Every ordered ref and `setDigest` must match. For every WOP-eligible Workspace disposition (`completed`, `insufficient_evidence`, `budget_exhausted`, or `blocked`), all five arrays are empty. For cancellation, failure, or recovery discard, unresolved refs may remain only in `unknownAcknowledgementRefs`; they are also present in the budget ledger's `unknown` amounts and can never become eligible context or reusable budget. A ref cannot appear in more than one array.

There is one Pi Agent Run settlement group. Run Control owns its one
Workspace-HMAC-authenticated, physically-last terminal payload:
`WorkspaceAgentRunSettlementTerminalV1` with protocol
`workspace-agent-run-settlement-terminal/v1`. This terminal is data inside the
PNW-owned settlement group, not a second group, sibling append, or unsigned
Workspace decision record. PNW owns preparation/commit/lookup and exposes the
result as `pi-agent-run-settlement/v1` evidence.

The Workspace terminal repeats the exact settlement candidate digest, Run and
basis, final save point, control state, budget ledger, ordered final-goal
assessment digests, goal-status digest, response candidate, accepted Provider
terminal, pending set, failure, expected leaf, A4-reserved terminal ID, and
resulting leaf. A present response-candidate or Provider-terminal pair is
all-present; a nullable half-pair is invalid. `receiptDigest = piDigest(the
complete WorkspaceAgentRunSettlementTerminalV1 with receiptDigest and
authenticity omitted)`. Its authenticity uses the exact section 9.2
Run-Control authenticator rules and covers that receipt digest and every terminal
field. Preview, terminal data, sealed evidence, and committed/exact-present A4
evidence must match byte-for-byte.

The future PNW amendment must return the exact PNW-owned
`PiAgentRunSettlementEvidenceV1` from PNW section 5.1. Its
`applicationTerminal.entryId` equals the Workspace terminal's A4
`terminalEntryId`; `applicationTerminal.entryDigest` equals the physically-last
complete materialized Session-entry digest in `batchEvidence`; and
`applicationTerminal.receiptDigest` equals the Workspace terminal
`receiptDigest`. `applicationTerminal.customType` is exactly
`workspace_agent_run_settlement_v1`. The Session ID, expected leaf, ordered
entry IDs/digests, terminal ID, and batch digest come from the same committed or
authoritatively exact-present `batchEvidence`. Pi treats the application receipt
digest as opaque and does not sign, authenticate, parse, reproduce, or translate
the terminal payload. Publication consumes the Run-owned terminal plus this
PNW-owned evidence by exact reference; it does not redeclare either schema.
Until that PNW amendment and its independent acceptance exist, settlement and
the no-tool implementation remain NO-GO.

The terminal mapping is closed:

| Run Control disposition | Pi terminal | Provider terminal | Workspace terminal binding | Response candidate |
| --- | --- | --- | --- | --- |
| `completed` | `completed` | required exact ref/digest | required shared terminal | required; outcome `completed`; one or more claims |
| `insufficient_evidence` | `completed` | required exact ref/digest | required shared terminal | required; matching outcome; zero claims |
| `budget_exhausted` | `completed` | required exact ref/digest | required shared terminal | required; matching outcome; zero claims |
| `blocked` | `completed` | required exact ref/digest | required shared terminal | required; matching outcome; zero claims |
| `failed` | `failed` | exact pair or both `null` | required shared terminal | both fields `null` |
| `cancelled` | `cancelled` | exact pair or both `null` | required shared terminal | both fields `null` |
| `discarded` | `discarded` | exact pair or both `null` | required shared terminal | both fields `null` |

`workspaceDecisionRef`/`workspaceDecisionDigest` in the settlement candidate are
the exact admitted `RunStopDecisionV1`; `candidateDigest` binds them into the
terminal without copying them as a second authority. Every terminal disposition,
candidate ref/digest, Provider-terminal ref/digest, `goalStatusDigest`, ledger,
assessment list, pending set, and failure must match that candidate and admitted
state exactly. The first four rows require `failure: null`; `failed` requires the
exact non-null Run failure; `cancelled` and `discarded` require `failure: null`.
The last three rows never manufacture a response candidate. WOP can consume
only the first four rows after the separately bound Pi terminal is `completed`.

`goalStatusDigest = piDigest({ protocol:
"workspace-investigation-run-goal-statuses/v1", orderedGoals })`, where
`orderedGoals` contains every admitted goal exactly once in ordinal order with
only its trusted `goalId`, final status, final assessment digest, and ordered
response-segment refs. The accepted Provider terminal ref/digest must be the
unique terminal that produced the final assistant entry bound by the response
candidate and final save point; a Provider terminal, Workspace decision, or
candidate ref from another attempt/generation is a terminal mismatch.

`committed` is durable success. `acknowledgement_unknown` performs exactly one authoritative lookup using the retained complete PNW/A4 evidence; only `exact_present` at that terminal leaf is success. `absent`, `conflict`, `unavailable`, prepare conflict/invalid/unavailable, and invalid terminal produce the exact settlement failure, append no replacement, and never report a terminal Run disposition. Exact replay of the same committed candidate returns the same Pi settlement; a different candidate for the same Run generation is `agent_run_settlement_failed`.

A settlement persistence failure returns one typed failed decision to the Workspace lifecycle but does not prepare a second settlement group; the lifecycle may emit its actor-safe failed public terminal without claiming a durable Agent Run settlement. The next reopen treats the unsatisfied candidate as interrupted/recovery-discard work. This is the only `failed` path whose failure cannot be copied into a successful settlement receipt, because the receipt seam itself failed.

`insufficient_evidence`, `budget_exhausted`, and `blocked` retain one final status
for every goal but carry no addressed goal and no partial model claim. They do
not fabricate a conclusion or silently drop a goal. WOP may publish only its
matching Workspace-authored closed notice after validating the single Pi
settlement and empty-claims candidate. Run settlement itself is never permission
to publish model text or a replacement for the public `WorkspaceTurn` terminal
contract.

## 12. Schema bounds and canonical validation

All schema bounds are hard and checked before semantic admission:

| Item | Bound |
| --- | ---: |
| UTF-8 serialized model proposal | 32 KiB |
| trusted bootstrap outcomes/goals | 1-4 |
| admitted goals | 4 |
| subquestion versions ever admitted per Run | 12 |
| active Query Candidates per subquestion | 4 |
| Query Candidate versions ever admitted per Run | 16 |
| literal construction bindings per Query Candidate | 16 |
| capability requests per proposal | 8 |
| local adjustments per proposal | 8 |
| local adjustments ever admitted per Run | 32 |
| local adjustments per goal | 8 |
| versions per subquestion/Query Candidate lineage | 4 |
| source references per entity | 8 |
| source-span bindings per catalog | 256 |
| response segment refs per final goal assessment | 16 |
| assumptions per subquestion | 4 |
| Query Candidate assumptions/scope delta | exactly `[]` / `none` |
| goal, question, or Query Candidate text | 512 UTF-16 code units |
| assumption or uncertainty text | 256 UTF-16 code units |
| language tag | 35 ASCII characters |
| local or admitted identifier | 64 ASCII characters |
| source catalog entries | 128 |
| Workspace Capability snapshot entries | 32 |
| capability uses ever admitted per Run | 64 |
| cumulative admitted capability-input JCS per Run | 1,048,576 UTF-8 bytes |
| cumulative snapshot descriptor/schema JCS | 1,048,576 UTF-8 bytes |
| complete admitted Run-state JCS | 4,194,304 UTF-8 bytes |
| pricing snapshot entries | 33 |
| pricing rate/cost scalar | 0-1,000,000,000,000 micros |
| capability dependency refs per entry | 8 |
| capability descriptor name | 1-128 ASCII characters |
| capability descriptor description | 1-1,024 UTF-8 bytes |
| capability descriptor/input schema | depth 12; 2,048 members/items; 64 KiB JCS |
| capability proposed/admitted input | depth 12; 2,048 members/items; 64 KiB JCS |
| safe failure related-ref digests | 8 |
| receipt authenticator key ID | 1-128 ASCII identifier characters |
| HMAC-SHA-256 base64url MAC | exactly 43 unpadded characters |

Local IDs match `[a-z][a-z0-9_-]{0,63}`. Trusted opaque refs and digests use their owning contract's canonical grammar and are never accepted from a free-text slot. Strings must be non-empty after validation where required; normalization cannot alter protected source literals. Arrays retain source order and contain unique elements.

Every numeric value is a finite safe integer; counts, ordinals, offsets, versions, sequences, tokens, durations, and costs are non-negative, and a field-specific positive minimum still applies. Capability JSON numbers are also finite safe integers in v1. `safeMessageId`, pricing refs/revisions, policy refs/versions, and template IDs are 1-128 ASCII characters matching `^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$`. All digest arrays contain canonical unique `sha256:` digests. All bounds are cumulative where section 7 says so; a per-proposal or active-record count never refunds an ever-admitted bound.

Canonical JSON and `piDigest` are the shared PNW primitives: RFC 8785 JCS encoded as UTF-8 and hashed as `sha256:` plus lowercase hexadecimal SHA-256. It uses sorted object keys, original array order, integers only, and no insignificant representation variants. Digests cover protocol, all admitted fields, referenced basis/catalog digests, control sequence, and supersession refs. A digest mismatch is a failure; it is never repaired from model text.

`candidateDigest` for a budget reservation and `digest` for an Agent Run settlement candidate are `piDigest` of the complete respective candidate with only that digest field omitted. `receiptDigest` and authenticity follow section 9.2 exactly. `stateDigest`, ledger/assessment/pending-set/input/descriptor/bootstrap/catalog/policy/pricing/failure digests are each `piDigest` of the complete closed value with only their own digest field omitted. No caller-supplied digest substitutes for retained basis recomputation.

## 13. Failure, cancellation, recovery, and concurrency

### 13.1 Closed failure codes

```typescript
type InvestigationRunFailureCodeV1 =
	| "invalid_run_basis"
	| "invalid_control_proposal"
	| "proposal_bounds_exceeded"
	| "source_reference_invalid"
	| "query_candidate_not_target_neutral"
	| "local_adjustment_not_local"
	| "capability_unavailable"
	| "capability_unauthorized"
	| "capability_snapshot_stale"
	| "budget_reservation_denied"
	| "budget_reservation_persistence_failed"
	| "budget_pricing_mismatch"
	| "budget_reconciliation_invalid"
	| "dispatch_permit_invalid"
	| "continuity_mismatch"
	| "concurrent_control_observation"
	| "provider_failed"
	| "tool_failed"
	| "save_point_failed"
	| "agent_run_settlement_failed"
	| "recovery_state_untrusted";

interface InvestigationRunFailureV1 {
	protocol: "workspace-investigation-run-failure/v1";
	code: InvestigationRunFailureCodeV1;
	stage:
		| "basis"
		| "proposal"
		| "capability"
		| "reservation"
		| "dispatch"
		| "reconciliation"
		| "save_point"
		| "settlement"
		| "recovery";
	retryable: false;
	safeMessageId: string;
	relatedRefDigests: readonly string[];
	failureDigest: string;
}
```

Every `failed` stop carries exactly one `InvestigationRunFailureV1`; every non-failed stop carries `failure: null`. A non-terminal `dispatch_denied` may carry only a capability/budget denial failure that leaves another admitted action possible; if the failure determines the Run outcome, policy returns `stop` atomically instead. The settlement candidate, Workspace terminal, and Pi binding carry the exact applicable pre-settlement failure or `null`; a code, stage, safe-message, related-ref, or digest mismatch prevents settlement. A failure of the settlement persistence seam follows section 11's no-second-settlement exception. Raw exception/provider/tool text is never a failure field.

Malformed or adversarial model control payloads fail closed as `invalid_control_proposal`, `proposal_bounds_exceeded`, `source_reference_invalid`, or `query_candidate_not_target_neutral`. There is no automatic correction call. A semantic request that is well formed but expands scope follows the local-adjustment stop policy instead of being mislabeled as malformed.

Actor-visible failures use closed safe messages. Raw proposal bodies, model reasoning, provider bodies, tool bodies, credentials, opaque backend IDs, stack traces, prices, and internal authorization detail are not emitted. Telemetry may record protocol/version, safe code, run/generation, control sequence, decision digest, dimension names, bounded counts, elapsed duration, and hashed refs.

### 13.2 One mutable generation

At most one Run generation may accept mutable observations for a Workspace Turn. Admission uses compare-and-swap on the expected control sequence. Two observations with the same expected sequence cannot both commit. An exact replay of an already committed canonical digest returns the prior decision; a different replay fails `concurrent_control_observation`.

An observation for an older run/generation/basis/Context Generation/lease is discarded without changing current state. Its already-started cost remains in the retired ledger. An observation for a future unknown generation is `recovery_state_untrusted`.

### 13.3 Cancellation and late work

Cancellation/retirement is checked before proposal admission, before each Provider dispatch, before each tool batch, before each save point, and before Agent Run settlement. Caller or Workspace-close cancellation yields `cancelled`; `pi_supersession` retires the generation as `discarded`. Once either wins, no new Provider or tool work starts.

A Provider or tool that ignores abort may finish later. Pi finalizes or marks its acknowledgement for accounting, but Workspace does not expose its delta, admit its proposal, add its outcome to eligible context, publish it, or reopen the Run. Its reservation becomes committed or unknown under section 9. A late callback cannot change the terminal disposition or write into a newer generation.

For a parallel read batch, Pi may complete calls out of order but persists finalized outcomes in source-call order. Cancellation or invalidation between completions fences every not-yet-eligible outcome. The policy never interprets completion order as plan order.

### 13.4 Crash and settlement recovery

The final save point and Agent Run settlement are separate facts. A crash after the final save point but before settlement is not completion. Reopen verifies the exact save point, pending/unknown actions, budget ledger, and basis; it then commits one recovery-discard settlement before admitting new work. It never repeats a Provider/tool action or guesses whether it was charged.

A crash before a control decision's owning save point leaves that decision uncommitted. Recovery ignores the proposal and rebuilds only from authenticated Session state. A crash or acknowledgement uncertainty after settlement is resolved from the unique settlement record, not by writing a duplicate terminal.

Exactly one Run settlement may commit. Exactly one caller-visible Workspace Turn terminal may follow, subject to the separate publication contract. A Run settlement cannot by itself leak raw model output.

## 14. First Pi-native no-tool vertical slice

The first implementation slice is intentionally narrower than the full design:

```text
Original User Task
-> admitted pre-investigation Task Understanding
-> atomic Task Context commit
-> seven-section initial context
-> one long-lived Session and AgentHarness
-> one formal Investigation Agent Run
-> no product tools and an empty capability snapshot
-> one durable no-tool Provider budget reservation and single-use permit
-> one final assessment for every admitted goal
-> final save point
-> Agent Run settlement
-> candidate handed to workspace-output-publication/v1
```

The slice must permit a simple task to complete with zero subquestions, zero Query Candidates, zero capability requests, and zero local adjustments. It exercises Run basis/continuity, a trusted no-tool budget reservation and reconciliation, cancellation fencing, final save point, and settlement. It does not fake a tool, planner, Working Set, evidence retrieval, Artifact, Assessment, Case write, or Provider activation.

The simple path uses only the final `agent_run_ended` stop envelope adjacent to the `ModelResponseCandidate`; it has no in-Run control tool. The exact carrier for later in-Run subquestion/Query Candidate/capability proposals remains implementation-gated until its Pi-native Interface and public-seam behavior receive independent acceptance.

## 15. Acceptance catalog

Design acceptance and later implementation acceptance are separate. Every implementation fixture is exercised through the common public Workspace seam and real Pi lifecycle integration, with deterministic fake Provider/tool boundaries only where external systems would otherwise be contacted. Tests do not assert private reducer names, private method calls, or internal call counts as the behavioral proof.

- **IRC-01 Ownership:** one public prompt creates one formal Investigation Agent Run on the Workspace-lifetime Harness bound to the durable leased Session; no second Agent, Harness, Session, transcript, planner loop, or sub-Agent appears.
- **IRC-02 Original Task:** exact Original User Task text/images and digest remain distinct and unchanged beside all goals, subquestions, adjustments, stops, and outputs.
- **IRC-03 Initial continuity:** Run admission fails before Provider dispatch when any actor/Case/purpose, Task Context, seven-section context, Session branch/head, Context Generation, Case context, capability, budget, or instruction binding mismatches.
- **IRC-04 Simple path:** a supported simple no-tool task completes with no forced decomposition or Query Candidate, one durable Provider reservation/permit, one exact final assessment per goal, a final save point, and one Agent Run settlement.
- **IRC-05 Multiple goals:** one through four committed TU outcomes map source-order one-to-one into the exact shared bootstrap outcome seeds; Run Control alone mints stable generation-scoped goal IDs. Incomplete/singularized seed sets, a TU/model-supplied Run goal ID, or any outcome-field mismatch fails before Provider dispatch, and addressing one goal cannot complete, rewrite, or silently drop another.
- **IRC-06 Subquestion bounds:** flat same-goal subquestions pass; overflow, duplicate/local-invalid IDs, cross-goal refs, graph/dependency/recursion/delegation fields, and unresolved refs fail closed.
- **IRC-07 Query Candidate neutrality:** each of the three literal templates passes only with an exact rerendered output-span-to-source-span receipt, `scopeDelta: none`, and empty assumptions. Translation, alias, broadening, narrowing, paraphrase, Resource refs, exact selectors, OpenCTI/GraphQL/SQL/Lucene/STIX execution syntax, backend/index/endpoint/credential/authorization/retry/commit fields, policy drift, and unanchored target instructions fail.
- **IRC-08 Protected literals:** source-span-bound CVE, ATT&CK, hash, domain, IP, and user-supplied case labels survive byte-for-byte as terms without becoming exact selectors; wrong/overlapping/surrogate-splitting offsets and source refs alone fail.
- **IRC-09 Local adjustment:** every supersede/retire kind passes only at its exact target/nullability matrix; a valid same-goal replacement leaves unrelated goals byte/digest identical, while child/pending-use conflicts and cross-scope, cross-goal, effect, dependency, actor, Case, or purpose expansion end `blocked` without mutation.
- **IRC-10 Supersession:** committed records are immutable, one active successor is allowed, stale targets and forks fail, cumulative/lineage bounds count retired versions, and recovery reconstructs the same active versions from Session state.
- **IRC-11 Capability:** only an exact current model-visible descriptor and schema-valid recursively snapshotted input can be admitted. Guessed, hidden, stale, unauthorized, dependency-invalid, wrong-goal, over-use, oversized/deep/unknown input, trusted-field injection, effectful-first-slice, and descriptor/schema/config mismatch never dispatch.
- **IRC-12 Model-turn budget:** the last fitting turn produces a reservation candidate; only a durable exact-present receipt plus one resident single-use permit reaches Provider dispatch, while numeric overflow or persistence/lookup/permit failure starts nothing.
- **IRC-13 Tool budget:** an entire source-ordered batch is atomically reserved; a batch that does not fit starts no member.
- **IRC-14 Token budget:** input, output, and total reservations are independently enforced; actual usage reconciles proven differences and over-reporting fails without negative balance.
- **IRC-15 Time budget:** pinned monotonic time reaches the deadline deterministically, starts no additional action, and cannot be moved backward or paused.
- **IRC-16 Cost budget:** one basis-bound currency/pricing revision produces integer-micro reservations; missing price, currency/pricing drift, overflow, zero-cap paid work, and a cost beyond the ceiling deny dispatch.
- **IRC-17 Unknown charges:** cancel, timeout, or lost acknowledgement moves the reservation to unknown, never makes it reusable, and does not authorize work in a later generation.
- **IRC-18 Stop precedence:** fixtures with overlapping causes prove the exact precedence from cancellation through completion; model-requested labels cannot override trusted facts.
- **IRC-19 Completion fence:** pending reservation/provider/capability/permit/unknown refs, stale basis, a missing or duplicate per-goal final assessment, an unaddressed goal, missing final save point, or missing/duplicate settlement prevents completed status.
- **IRC-20 No Run clarification:** a model attempt to emit Run `clarification_required`, questions, alternatives, or a suspended loop fails the closed schema. A material actor choice settles `blocked/new_task_required`; only a new public prompt may enter TU's pre-run clarification/continuity path.
- **IRC-21 Insufficient evidence:** a valid basis with no useful admitted action preserves unsupported goals and cannot claim completion.
- **IRC-22 Budget exhausted:** an otherwise useful action that cannot fit reports the exhausted dimensions and performs no extra model/tool call.
- **IRC-23 Blocked:** missing authorization, qualified dependency, required capability, or new-task choice is distinct from insufficient evidence and each maps to its closed reason.
- **IRC-24 Failure:** malformed proposal, impossible budget reconciliation, reservation/permit, Provider/tool/save-point/settlement failure produces exactly one typed failure wired through stop and settlement, with no leaked body or secret.
- **IRC-25 Cancellation race:** cancellation at every pre-dispatch/save-point/settlement boundary wins deterministically; ignored abort and late callbacks cannot enter context or publication.
- **IRC-26 Generation isolation:** stale, concurrent, replayed, and future-generation observations follow the exact discard/idempotency/failure rules and cannot corrupt current state.
- **IRC-27 Parallel outcomes:** out-of-order completion is finalized in source order; invalidation between completions isolates every ineligible outcome.
- **IRC-28 Recovery:** crash before save point ignores uncommitted control; crash after final save point but before settlement writes one recovery discard and never repeats external work.
- **IRC-29 Publication boundary:** no raw model delta or ModelResponseCandidate is caller-visible because of a Run Control decision; only the separately validated publication path can yield output.
- **IRC-30 No forbidden scope:** fixtures and dependency inspection prove no I&E, Working Set mutation, Artifact, Assessment, Case write, live OpenCTI, paid Provider, recursive planner, general task DAG, or sub-Agent activation.
- **IRC-31 Goal finalization:** goals stay open during the active Run; exactly one final assessment per goal is admitted at `agent_run_ended`, `addressed` proves only exact candidate-claim/citation structural coverage with no pending goal action, and no contradiction/sufficiency/reopen semantics exist.
- **IRC-32 Reservation durability:** A4 prepare/seal/commit and acknowledgement-unknown lookup cover committed, exact-present, absent, conflict, invalid, and unavailable; only the first two mint one permit, never recommit, and exact replay cannot reserve twice.
- **IRC-33 Ledger invariants:** every charge has `total = input + output`, component sums fit independent limits, elapsed is monotonic rather than additive, and duplicate/different reconciliation follows exact idempotent/failure behavior.
- **IRC-34 Settlement protocol:** one Pi settlement group commits one physically-last, Workspace-HMAC-authenticated `workspace-agent-run-settlement-terminal/v1` containing the exact candidate, Run/basis/save point, control state, ledger, assessments, goal statuses, response candidate, accepted Provider terminal, pending set, failure, leaves, and authenticity. The directly referenced PNW `PiAgentRunSettlementEvidenceV1.applicationTerminal` repeats its exact entry ID, complete entry digest, and receipt digest, all proven by the same `batchEvidence`; Pi does not sign or authenticate the payload. Publishable Workspace dispositions map only to Pi `completed`; failed/cancelled/discarded map to the like-named Pi terminal with the same Workspace terminal but no response candidate. Every mismatch and negative A4 outcome prevents settlement.
- **IRC-35 Cumulative adjustment bounds:** proposal, Run, goal, and lineage boundaries pass at limit and reject over limit without retirement refunds or partial dependent admission.
- **IRC-36 Capability bounds:** descriptor, schema, snapshot-entry/dependency/goal/use counts, per-input size, cumulative input bytes, cumulative descriptor/schema bytes, and complete Run-state bytes pass at limit and reject over limit before reservation without retirement refunds.
- **IRC-37 Final goal coverage:** the no-tool response candidate contains exactly one assessment per Run goal minted from a TU outcome seed and every segment/support ref resolves. Completed requires every goal structurally addressed; any noncompleted aggregate requires the same noncompleted status for every goal plus zero segments and zero candidate claims, so mixed partial claims cannot bypass WOP.

An independent design reviewer must return PASS before tests or implementation start. Later focused implementation/public-seam PASS requires the focused Run Control tests plus any modified Pi seam tests under Node 24.14. Integrated PASS additionally requires the complete no-tool chain, publication validation, root `npm run check`, and every separately owned contract gate; a focused PASS is not integrated PASS.

## 16. Deferred scope and explicit non-authorization

This contract deliberately defers:

- the model-visible carrier and product-tool decomposition for in-Run proposals;
- I&E retrieval, enrichment, Resource Candidates, exact selectors, source capture, and evidence admission;
- Working Set creation, reuse, mutation, persistence, and disclosure;
- Artifact creation or persistence;
- Assessment, Case Management Facade behavior, and every Case write/effect;
- general task graphs, recursive planning, conditional workflows, autonomous retries, delegation, and sub-Agents;
- background or cross-Run continuation;
- pricing discovery, model fallback, provider activation, and live OpenCTI activation;
- public output validation, citation validation, and publication, which belong to `workspace-output-publication/v1`.

Future work may add an Adapter at an accepted seam, but it may not weaken immutable-task preservation, basis binding, target neutrality, deterministic capability admission, hard budgets, stop precedence, generation isolation, or one-Run/one-Harness/one-Session ownership without a new contract version and independent review.
