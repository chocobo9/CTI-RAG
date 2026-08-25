# Task Context Understanding v1

Status: **Superseded before implementation** by [`pre-investigation-task-understanding/v1`](pre-investigation-task-understanding-v1-contract.md) and [ADR 0017](../adr/0017-understand-the-task-before-the-investigation-agent-run.md). Its earlier independent design PASS remains historical evidence only. The same-Harness/same-Agent-Run planning control action, planning `tool_call/tool_result/save_point`, Query Candidate proposal, and capability-need proposal below are not implementation authorization.

This contract owns how Agent Investigation Workspace preserves a raw User Task, obtains model-assisted task understanding, deterministically admits a Task Context Plan, handles material ambiguity, and records non-executable Query Candidates. It supports the sole current lifecycle contract, [Pi-native Agent Workspace Lifecycle v1](pi-native-workspace-lifecycle-v1-contract.md), and does not start I&E Retrieval, Working Set, Assessment, Case writes, or product investigation-tool decomposition.

## 1. Decision and business problem

`CaseWorkspace.prompt({ task })` remains the only common task entry. Inside the same long-lived Pi `AgentHarness`, a private planning turn exposes one Workspace-internal structured control action. The model proposes task meaning, subquestions, uncertainty, and Query Candidates. A deterministic `TaskContextGate` admits, conservatively limits, requests clarification, falls back to raw-task-only work, or denies the proposal. The admitted decision commits through the normal Pi save-point transaction before a fresh Pi turn performs the response.

The problem is not string rewriting. A natural-language User Task may contain several intents, implied subjects, ambiguous scope, aliases, language variants, and missing constraints. Without one owner, prompts, model prose, context selection, and future Tool Adapters will each reinterpret it differently. A rewritten string may silently replace the user's request, expand disclosure or retrieval scope, revive stale assumptions, or become an accidental authorization input.

The Module earns its place by concentrating task provenance, uncertainty, conservative fallback, clarification, query derivation, context planning, persistence, and recovery behind the unchanged Workspace Interface. Query rewriting alone is too shallow to be a separate Module.

## 2. External Interface

The common Interface does not expose task-understanding mechanics:

```typescript
interface CaseWorkspace {
	prompt(input: {
		task: string;
		images?: readonly ImageContent[];
	}): WorkspaceTurn;

	close(): Promise<void>;
}
```

The raw `task` and image digests are appended unchanged as the User Task source. A Task Context Plan, summary, Query Candidate, compaction result, or later clarification never replaces that source entry.

`WorkspaceTurn` adds one typed terminal outcome for a task that cannot safely proceed:

```typescript
interface TaskClarificationRequiredResult {
	status: "clarification_required";
	taskContextId: string;
	questions: readonly AdmittedClarificationQuestion[];
}
```

It remains a resolved, non-rejecting result with one terminal event. The deterministic questions are safe display data; the Workspace does not leave a suspended Agent Run waiting for the user. A later `prompt` is a new User Task that may refer to the retained clarification chain.

## 3. Deep Module and Pi seam

`TaskContextGate` is a private, in-process deterministic Module. It has one semantic entry:

```typescript
interface TaskContextGate {
	admit(input: {
		rawTask: TrustedUserTaskRef;
		proposal: TaskContextProposalV1;
		basis: TrustedTaskAdmissionBasis;
	}): TaskContextDecision;
}

type TaskContextDecision =
	| { kind: "admitted"; plan: AdmittedTaskContextPlanV1 }
	| { kind: "admitted_conservative"; plan: AdmittedTaskContextPlanV1 }
	| { kind: "clarification_required"; request: AdmittedTaskClarificationV1 }
	| { kind: "raw_task_fallback"; plan: AdmittedTaskContextPlanV1; issues: readonly TaskProposalIssue[] }
	| { kind: "denied"; code: TaskContextFailureCode };
```

The Module hides proposal validation, source-span proof, closed policy lookup, conservative defaults, query budgets, canonical IDs/digests, issue classification, and decision construction. It does not own a provider, Harness, Session, retry loop, tool dispatcher, or persistence transaction.

The carrier is one private Workspace runtime control action using Pi's ordinary sequential `tool_call`, finalized `tool_result`, `turn_end`, and save-point lifecycle. Its protocol identity is closed, but its model-visible name is not a product investigation capability and is not part of the application Interface. The planning turn has no product investigation tools. Pi remains unaware of CTI task semantics.

## 4. Model proposal and deterministic plan

The model may propose only non-authoritative semantics:

```typescript
interface TaskContextProposalV1 {
	protocol: "cti-task-context-proposal/v1";
	sourceClaims: readonly TaskSourceClaim[];
	intents: readonly ProposedTaskIntent[];
	subquestions: readonly ProposedSubquestion[];
	uncertainties: readonly ProposedTaskUncertainty[];
	queryCandidates: readonly ProposedQueryCandidate[];
	capabilityNeeds: readonly ProposedCapabilityNeed[];
}
```

### 4.1 Closed proposal vocabulary

Version 1 is closed rather than an extensible workflow language:

```typescript
type TaskIntentKind =
	| "describe_case_orientation"
	| "summarize_visible_work"
	| "answer_from_visible_context"
	| "continue_prior_task"
	| "request_intelligence_retrieval"
	| "request_specialist_analysis"
	| "request_case_change"
	| "request_external_publication";

type TaskOutcomeKind =
	| "explanation"
	| "summary"
	| "comparison"
	| "list"
	| "next_steps"
	| "retrieval_candidates"
	| "change_request"
	| "publication_request";

type TaskSlot =
	| "subject"
	| "requested_outcome"
	| "time_scope"
	| "source_scope"
	| "entity_scope"
	| "comparison_set"
	| "output_form"
	| "evidence_standard"
	| "effect_intent";

type TaskUncertaintyCode =
	| "missing"
	| "ambiguous"
	| "conflicting"
	| "unsupported"
	| "scope_expansion_required"
	| "external_egress_required";

type TaskCapabilityClass =
	| "orientation_read"
	| "intelligence_retrieval"
	| "specialist_analysis"
	| "case_change"
	| "external_publication";

type TaskSourceClaim =
	| {
			kind: "raw_task_span";
			localId: string;
			startUtf16: number;
			endUtf16: number;
			textDigest: string;
	  }
	| {
			kind: "user_image";
			localId: string;
			imageIndex: number;
			imageDigest: string;
	  }
	| {
			kind: "prior_task_context";
			localId: string;
			taskContextId: string;
			nodeId: string;
			nodeDigest: string;
	  };

interface ProposedTaskIntent {
	localId: string;
	kind: TaskIntentKind;
	outcome: TaskOutcomeKind;
	supportClaimRefs: readonly string[];
}

interface ProposedSubquestion {
	localId: string;
	text: string;
	intentRefs: readonly string[];
	supportClaimRefs: readonly string[];
	materiality: "bounded" | "material";
}

interface ProposedTaskUncertainty {
	localId: string;
	code: TaskUncertaintyCode;
	affectedSlot: TaskSlot;
	affectedNodeRefs: readonly string[];
	alternatives: readonly string[];
	supportClaimRefs: readonly string[];
	materiality: "bounded" | "material";
}

interface ProposedCapabilityNeed {
	localId: string;
	capabilityClass: TaskCapabilityClass;
	subquestionRefs: readonly string[];
	requiredSlots: readonly TaskSlot[];
}
```

All object members are closed. Unknown members or discriminators fail the proposal. Every `localId` is globally unique and matches `[a-z][a-z0-9_-]{0,63}`. References flow only from intents to source claims, subquestions to intents/source claims, and uncertainty/query/capability nodes to earlier source or subquestion nodes; dangling, duplicate, wrong-kind, or self references fail. The shape cannot express conditions, loops, callbacks, retry, dispatch order, arbitrary predicates, or dynamic schemas.

Initial hard bounds are: 32 KiB canonical proposal JSON; 48 source claims; 4 intents; 12 subquestions; 12 uncertainties; 16 Query Candidates; 8 capability needs; 5 alternatives per uncertainty; 4 Query Candidates per subquestion; 512 UTF-16 code units per question/query; and 256 per alternative or assumption. Numeric fields are finite non-negative integers. A raw-task span must be in range, non-empty, lie on UTF-16 boundaries, and match its digest. Image index/digest and prior-plan node/digest must match the trusted basis exactly.

A proposal contains at least one source claim and one intent. Every intent has at least one source claim; every subquestion has at least one intent and source claim; every uncertainty has at least one affected node; every Query Candidate has at least one subquestion and source claim; and every capability need has at least one subquestion. Empty optional lists are allowed only for whole categories such as no uncertainty or no query. Duplicate semantic nodes remain separate proposals but canonical admission deduplicates equal normalized nodes and records one bounded issue.

The current capability catalog is also closed:

| Capability class | Current state | Admission consequence |
|---|---|---|
| `orientation_read` | available | may support an admitted/conservative response with all Orientation dependencies |
| `intelligence_retrieval` | recognized, implementation frozen | need may be recorded, but no tool or request activates |
| `specialist_analysis` | recognized, implementation frozen | need may be recorded, but no tool activates |
| `case_change` | frozen | deny current execution; ambiguity about effect intent requires clarification |
| `external_publication` | frozen | deny current execution; ambiguity about publication requires clarification |

The closed conservative fallback table contains only:

| Missing/bounded slot | Deterministic fallback |
|---|---|
| `output_form` | concise explanation |
| `time_scope` | current actor-visible Orientation only; no historical coverage claim |
| `source_scope` | no source outside current qualified context |
| `evidence_standard` | preserve uncertainty; make no Case-truth upgrade |

There is no fallback for `subject`, `entity_scope`, `comparison_set`, `effect_intent`, another Case/actor/purpose, authorization/disclosure, external egress, or material conflicting requested outcomes.

Clarification text uses this fixed template catalog; admitted alternatives appear only when each is an exact supported raw-task span:

| Reason | Template |
|---|---|
| `subject_required` | `Which subject should this task address?` |
| `entity_required` | `Which entity do you mean?` |
| `scope_required` | `What time or source scope should this task use?` |
| `comparison_set_required` | `Which alternatives should be compared?` |
| `effect_intent_required` | `Do you want analysis only, or are you requesting a Case change?` |
| `egress_required` | `Should this remain within current Case context, or is external-source research intended?` |
| `conflicting_outcome` | `Which requested outcome should take priority?` |

### 4.2 Closed admitted records and failures

```typescript
interface TrustedUserTaskRef {
	sessionEntryId: string;
	textDigest: string;
	imageDigests: readonly string[];
}

interface TrustedTaskAdmissionBasis {
	workspaceBindingDigest: string;
	rawTask: TrustedUserTaskRef;
	branchId: string;
	agentRunId: string;
	planningSavePointId: string;
	planningContextDigest: string;
	contextGenerationDigest: string;
	policyDigest: string;
	capabilityCatalogDigest: string;
	capabilitySnapshotDigest: string;
	budgetPolicyDigest: string;
}

interface AdmittedTaskIntent {
	id: string;
	kind: TaskIntentKind;
	outcome: TaskOutcomeKind;
	sourceClaimDigests: readonly string[];
}

interface AdmittedSubquestion {
	id: string;
	text: string;
	intentIds: readonly string[];
	sourceClaimDigests: readonly string[];
	materiality: "bounded" | "material";
}

interface AdmittedTaskUncertainty {
	id: string;
	code: TaskUncertaintyCode;
	affectedSlot: TaskSlot;
	affectedNodeIds: readonly string[];
	alternatives: readonly string[];
	materiality: "bounded" | "material";
}

interface ConservativeAssumption {
	slot: "output_form" | "time_scope" | "source_scope" | "evidence_standard";
	fallback: "concise_explanation" | "current_orientation_only" | "no_external_sources" | "preserve_uncertainty";
}

interface TaskExclusion {
	code: "no_external_sources" | "no_effect" | "no_publication" | "no_dependency_narrowing";
}

interface AdmittedCapabilityNeed {
	id: string;
	capabilityClass: TaskCapabilityClass;
	subquestionIds: readonly string[];
	state: "available" | "recognized_frozen" | "denied_frozen";
}

interface AdmittedQueryCandidate {
	id: string;
	subquestionIds: readonly string[];
	strategy: "literal" | "translated" | "alias_expanded" | "broadened" | "narrowed";
	text: string;
	language?: string;
	sourceClaimDigests: readonly string[];
	assumptions: readonly string[];
	disposition: "non_executable" | "clarification_alternative";
}

interface AdmittedClarificationQuestion {
	id: string;
	reason: "subject_required" | "entity_required" | "scope_required" | "comparison_set_required" | "effect_intent_required" | "egress_required" | "conflicting_outcome";
	slot: TaskSlot;
	text: string;
	alternatives: readonly string[];
}

interface AdmittedTaskClarificationV1 {
	protocol: "cti-task-clarification/v1";
	taskContextId: string;
	rawTaskRef: TrustedUserTaskRef;
	questions: readonly AdmittedClarificationQuestion[];
	basis: TrustedTaskAdmissionBasis;
	digest: string;
}

type TaskProposalIssueCode =
	| "schema_invalid"
	| "unknown_member"
	| "budget_exceeded"
	| "source_claim_invalid"
	| "reference_invalid"
	| "capability_unavailable"
	| "query_scope_untrusted"
	| "material_slot_missing";

interface TaskProposalIssue {
	code: TaskProposalIssueCode;
	nodeLocalId?: string;
}

type TaskContextFailureCode =
	| "task_control_action_missing"
	| "task_protocol_untrusted"
	| "task_basis_changed"
	| "task_policy_unavailable"
	| "task_class_unsupported"
	| "task_plan_commit_conflict";
```

Canonical durable IDs and digests are generated from list order, normalized values, source-claim digests, protocol version, and trusted basis; model local IDs are never retained as authority. A new vocabulary member, bound, fallback, capability class, clarification reason, issue, or failure code requires a new contract/schema version rather than permissive parsing.

Every proposal node has a candidate-local ID and source support pointing to an exact raw-task span, one user-image index/digest, or an explicitly eligible prior Task Context source. Candidate IDs never become durable IDs. A model observation about image content proves only which user image informed the proposal; without a qualified OCR/entity resolver it does not prove extracted text or identity. The model cannot supply Case, actor, credential, authorization, Session, Context Generation, dependency key, active tool name, budget, freshness proof, commit instruction, retry rule, or terminal status.

Deterministic code produces the admitted plan:

```typescript
interface AdmittedTaskContextPlanV1 {
	protocol: "cti-task-context-plan/v1";
	taskContextId: string;
	version: number;
	rawTaskRef: TrustedUserTaskRef;
	mode: "admitted" | "conservative" | "raw_task_only";
	intents: readonly AdmittedTaskIntent[];
	subquestions: readonly AdmittedSubquestion[];
	uncertainties: readonly AdmittedTaskUncertainty[];
	assumptions: readonly ConservativeAssumption[];
	exclusions: readonly TaskExclusion[];
	queryCandidates: readonly AdmittedQueryCandidate[];
	capabilityNeeds: readonly AdmittedCapabilityNeed[];
	basis: TrustedTaskAdmissionBasis;
	proposalDigest: string;
	planDigest: string;
}
```

`TrustedTaskAdmissionBasis` binds the Workspace, Case/actor/purpose, raw task entry/digest, branch, Agent Run, policy/catalog versions, available capability classes, budget policy, Context Generations, and planning Context Snapshot. Every trusted field comes from code. The plan is a versioned, non-authoritative Workspace derivation persisted by Pi Session; it is not Case truth, an Operation Intent, a Dispatch Permit, a Working Set, or authorization.

## 5. Uncertainty boundary

The model may:

- propose task intents, requested outcomes, subquestions, alternative interpretations, language variants, aliases, and Query Candidates;
- identify uncertainty and suggest which capability class may be useful;
- retain several plausible analytic interpretations.

Deterministic code must:

- preserve the raw User Task and prove proposal provenance;
- validate the closed schema, reference graph, bounds, and protocol version;
- bind Case, actor, purpose, Session, generations, policy, catalog, and budgets;
- select actual Context Dependencies and active capabilities from trusted code;
- classify whether ambiguity permits conservative work or requires clarification;
- admit, reject, persist, recover, and invalidate plans;
- prevent a plan or query from authorizing disclosure, retrieval, effects, retry, or publication.

Semantic equivalence between a User Task and a Query Candidate cannot be proven mechanically. Admission proves provenance and boundedness, not that the model understood perfectly. Therefore the raw task stays visible to later reasoning, uncertainty stays explicit, and Tool Adapters must independently enforce their current operation contract.

## 6. Context dependencies and capabilities

Free-form task interpretation cannot safely narrow a Context Dependency Set. During the Orientation-only cycle, a free-form prompt uses the conservative union of all available Orientation dependencies. The model may request semantic needs but cannot name or omit dependency keys.

A narrower set becomes legal only when a closed trusted operation recipe or caller-selected product workflow mechanically maps its inputs to dependencies and passes dependency-disjoint acceptance. This rule allows removal of the public `orientationDependencies` field without pretending that natural-language classification is trusted provenance.

Capability needs are closed catalog identifiers, not tool names or executable control flow. The compiler intersects proposed needs with the currently qualified capability snapshot and binds trusted operation recipes only after the planning save point. Unknown, disabled, unauthorized, or version-mismatched needs never map to a similar capability. During TQ implementation and acceptance this contract opens only the internal task-context control action; I&E and effectful product capabilities remain frozen. After the separate IWS consumer gate passes, a new planning save point may commit that contract's trusted capability-activation snapshot as `available`; this creates a new configuration/generation basis and never mutates an already admitted Task Context Plan.

After the planning save point commits, Workspace may separately mint opaque Resource Candidate References from the then-current actor-visible Orientation membership for a later product-tool phase. Those references are not Task Context Proposal or Plan fields, are not Query Candidate fields, and are governed by the gated [Intelligence Working Set contract](intelligence-working-set-v1-contract.md). Tool names and decomposition remain Adapter choices.

## 7. Query Candidates

A Query Candidate is a task-scoped, target-neutral formulation for one admitted subquestion. It is not a rewritten User Task and is not executable retrieval.

```typescript
interface ProposedQueryCandidate {
	localId: string;
	subquestionRefs: readonly string[];
	strategy: "literal" | "translated" | "alias_expanded" | "broadened" | "narrowed";
	text: string;
	language?: string;
	supportClaimRefs: readonly string[];
	assumptions: readonly string[];
}
```

Admission enforces bounded count/length, valid references, closed strategy, source claims, language policy, and absence of resource targets or trusted fields. A Query Candidate cannot contain an opaque Resource Candidate Reference, OpenCTI identifier, exact selector, Adapter, credential, or capture identity. Its target neutrality is structural, not a prompt instruction.

An alias may be classified as `user_surface`, `user_image_observation`, `eligible_context_label`, `model_suggested`, or later `trusted_resolver`. A user-image observation or model-suggested alias remains a recall hint and cannot establish extracted text, entity identity, authorization, an exact exclusion, a write target, or independent corroboration.

Candidates that broaden time, sources, entities, or purpose beyond trusted input are rejected or retained only as non-executable clarification alternatives. They do not dispatch a request in this cycle. In a later product-tool phase, the model may select a separately minted opaque Resource Candidate Reference and optionally cite a Query Candidate for semantic provenance. Only trusted Workspace code may bind the resource reference to an exact I&E selector after revalidating current Orientation membership, actor/purpose/task binding, authorization, egress, scope, coverage, cost, and I&E qualification. The Query Candidate never becomes that selector.

## 8. Clarification and conservative execution

The model may report ambiguity, but it cannot force a blocking clarification by itself. Closed policy decides among:

- `admitted`: required material slots have trusted support;
- `admitted_conservative`: every uncertainty is covered by a closed fallback that is narrower, read-only, reversible, and has explicit assumptions/exclusions;
- `clarification_required`: at least one missing material slot has no safe fallback;
- `raw_task_fallback`: a planning control action reached one finalized invalid/incomplete outcome, but closed policy permits an Orientation-only response using the raw task, all Orientation dependencies, no Query Candidate, and no product tool;
- `denied`: the protocol/basis is untrusted or the requested task class is unsupported rather than merely ambiguous.

Conservative defaults may choose concise output, current actor-visible Orientation only, no external source expansion, no effect, and explicit uncertainty. They may never infer another Case/actor/purpose, widen disclosure, select an external source, expand time/entity scope, narrow dependencies, enable a tool, or manufacture an exact conclusion.

Material ambiguity includes indistinguishable target entities, a scope/time difference that changes the conclusion, uncertain write/publication intent, requested exactness without required constraints, or any interpretation that changes Case, actor, purpose, authorization, disclosure, or external egress.

Clarification questions are rendered from closed reason codes, admitted raw spans, and deterministic templates. Arbitrary model prose is not published as the question. The planning save point commits the raw task, proposal outcome, and signed clarification record; the Workspace then emits one `clarification_required` terminal without another provider call.

## 9. Same-Harness lifecycle

```text
CaseWorkspace.prompt(raw task)
-> one Pi Agent Run on the existing long-lived Harness/Session
-> transactional raw user entry
-> planning context: raw task, eligible task chain, closed proposal contract;
   no Orientation body and no product investigation tools
-> provider emits exactly one private task-context control action
-> Pi tool_call
-> TaskContextGate.admit
-> finalized tool_result
-> turn_end
-> save-point group commits user + assistant/tool call + tool result
   + signed Task Context Plan/clarification receipt
   + Context Snapshot receipt last
-> fresh Pi snapshot
-> admitted response context injects raw task, admitted plan,
   assumptions/exclusions, qualified history, and current Orientation
-> pre-provider denial
-> normal Pi response/tool turns under the admitted capability snapshot
-> final save point
-> Agent Run settlement
-> one Workspace terminal
```

Planning assistant text and deltas are internal and never become public response events or Workspace Artifacts. Only turns after admission may stream public model text. The planning action itself is non-effectful and sequential. It cannot call `setActiveTools` or mutate live Harness configuration. After `turn_end`, Workspace derives the next active capability set from the deterministic decision and stages it in the same Pi transaction; Pi applies both durable and in-memory configuration only after the planning save point commits. Rollback, conflict, signing failure, cancel, or close preserves the planning-only snapshot.

The planning phase exposes exactly one active control action, so an admitted clarification or denial may use its finalized result's Pi `terminate` hint to prevent another provider turn. Safety does not rely on `terminate`: the Task Context decision, run-generation fence, transaction outcome, and public terminal reducer remain authoritative. An invalid proposal may be retained only as audit history; the context-entry policy admits the raw task and deterministic fallback/issue record, never the unadmitted proposal as Task Context.

A finalized malformed proposal may produce a policy-approved raw-task fallback and continue naturally because its planning tool result keeps the existing Pi tool loop active. If the assistant emits no planning control action, Pi has no same-Run continuation trigger; the awaited `turn_end` policy therefore records `task_control_action_missing`, admits no plan or product tool, requests no follow-up message, and the Run settles `failed` after `agent_end`. It never starts a second `harness.prompt()` and never fabricates another user message. There is no hidden provider retry, planner Harness, planner Session, or nested loop.

## 10. Persistence, recovery, branch, and compaction

The Task Context decision, next-turn active-tool change, and receipt join the planning turn's atomic save-point group. The single closed [`ContextSnapshotReceiptV1`](pi-native-workspace-lifecycle-v1-contract.md#7-session-eligibility-receipt-trust-and-the-stale-marker-replacement) owned by the lifecycle contract remains physically last; this contract does not redefine it. Before commit, the proposal and configuration are transaction-local. After commit, the immutable plan version is eligible only under its raw task, branch, Workspace binding, Context Generations, policy/catalog, and capability basis.

Every raw planning assistant message, control-action payload, and raw tool-result message is classified as `task_planning_protocol` audit history. The unified context-entry policy excludes that class from every later provider request, compaction input, and branch-summary input, including the immediate response turn. It instead injects only the unchanged raw User Task, the canonical admitted plan or actor-safe fallback/clarification decision, and their signed basis. Proposal text can never regain eligibility through summary, branch navigation, or equal-content return.

A later clarification answer or materially new task creates a new raw entry and new plan version; it may supersede but never rewrites earlier tasks, questions, answers, or plans. Duplicate same-identity/same-digest admission is idempotent; same identity/different digest is an integrity failure. A CAS conflict appends none.

Provider, compaction, and branch-summary context all use the same eligibility policy. A summary cannot replace the raw task identity or manufacture a plan. Branch navigation cannot activate a plan outside its ancestry or bypass a retained generation advance. Reopen restores only committed qualified plans; it never resumes the planning provider or replays the control action.

## 11. Failure, concurrency, and retry

| Scenario | Deterministic result |
|---|---|
| provider partial, timeout, cancel, close, supersession | no Task Context decision commits; run-generation fence rejects late proposal/events |
| missing control action | no follow-up is enqueued; no fallback or product tool is admitted; Run settles one `failed` terminal after `agent_end` |
| invalid, oversized, truncated, or multi-proposal batch | finalized error, no plan-dependent capability, no automatic retry |
| proposal claims trusted fields or dependencies | reject the affected proposal; never sanitize it into authority |
| unsupported task/capability | deny; do not disguise permanent unsupported scope as clarification |
| required material slot missing | commit deterministic clarification state and terminal |
| optional ambiguity | preserve it; it cannot block unrelated admitted subquestions |
| basis/generation changes before save point | rollback the planning group and fail closed |
| save-point conflict or signing failure | append none; no plan-only or message-only state |
| duplicate/late callback | settle once by run generation, assistant/control-action identity, and proposal digest |
| crash before planning save point | no durable plan; do not resume provider |
| crash after planning save point | recover plan once; Agent Run recovery follows the lifecycle contract and does not replay planning |
| authorization revocation | zero stale allowance; intersecting plan/query body leaves provider, compaction, and publication context |
| concurrent new prompt | current read-only supersession rules apply; future effectful behavior remains explicit |

This cycle performs no automatic provider, proposal, or tool retry. A bounded proposal-correction turn may be designed later only if measurement justifies its cost and it remains inside the same Pi run-generation and transaction protocol.

## 12. Cost and observability

The selected design usually adds one planning provider turn and one small save-point group per new User Task. It avoids a second Harness, provider client, transcript, recovery machine, and provider-specific structured-sidecar protocol. Raw-task fallback still costs a planning call; reuse or bypass is deferred until measured data proves a safe deterministic fast path.

Proposal size, node count, query count/length, and planning tokens have hard budgets. Admission is linear in bounded proposal nodes. Telemetry records only IDs/digests, decision/reason codes, counts, byte/token buckets, latency, cost bucket, save-point outcome, and invalidation/abort outcome. It excludes raw task text, Query Candidate text, questions, Orientation content, credentials, prompts, and completions by default.

## 13. Alternatives and decision

- **Optional save-point proposal with an unspecified structured carrier:** minimal Module Interface and no mandatory planning call, but it leaves the most important model-to-runtime seam unresolved. Rejected as the complete design.
- **Assistant structured sidecar plus a new generic `assistant_candidate` Pi seam:** can avoid an extra model turn and supports rich schemas, but requires provider-specific qualified sidecars and introduces a broad Pi seam before evidence shows another consumer. Deferred as a possible later optimization.
- **Separate planner model/Harness/Session:** flexible, but creates the second loop, persistence, abort, retry, and recovery lifecycle this redesign removes. Rejected.
- **Direct model rewrite as retrieval input:** smallest implementation, but loses raw-task provenance and lets model text influence scope and execution without a deterministic admission boundary. Rejected.
- **Public `understand -> approve -> execute`:** explicit but makes every common caller learn internal lifecycle and destroys Interface depth. Rejected.
- **Hidden Task Context Gate using Pi's existing tool/save-point loop:** selected. It keeps the public Interface trivial, makes the uncertain proposal explicit, gives deterministic code the admission decision, and exercises Pi's native lifecycle. The added planning latency is accepted until measurements justify a safe fast path.

## 14. Executable acceptance catalog

- **TQ-01:** the caller uses only `prompt({ task })`; no Task Plan, query, dependency, or approval input is public.
- **TQ-02:** raw task text is byte/digest-identical and user images retain exact index/digest identity in Session and every admitted response context; no plan/query/summary replaces them or upgrades image interpretation into trusted identity.
- **TQ-03:** one Workspace uses one long-lived Harness/Session and one Agent Run; no planner Harness, Session, nested loop, or hidden provider client exists.
- **TQ-04:** a grounded task produces one planning `tool_call`, one finalized `tool_result`, one receipt-last save point, a fresh snapshot, and then the response provider request in that order.
- **TQ-05:** raw planning assistant/control/tool-result messages are audit-only and reach no later provider, compaction, or branch-summary context; only the raw task and canonical admitted decision are projected.
- **TQ-06:** model-supplied actor, Case, authorization, dependency, tool, budget, freshness, retry, commit, and terminal fields cannot enter the admitted plan.
- **TQ-07:** free-form planning cannot narrow the all-Orientation dependency baseline; only a trusted closed recipe may establish a narrower set.
- **TQ-08:** conservative admission injects its assumptions/exclusions into the response context and makes them observable in the final response contract.
- **TQ-09:** material ambiguity commits one actor-safe deterministic clarification and produces exactly one `clarification_required` terminal without an extra rendering model call.
- **TQ-10:** a later answer creates a new raw task and immutable plan version while preserving the original task/question/answer chain.
- **TQ-11:** Query Candidates preserve source support, strategy, assumptions, plan version, and original task reference; their closed Proposed and Admitted shapes contain no resource target, opaque Resource Candidate Reference, OpenCTI identifier, or exact selector.
- **TQ-12:** model-suggested aliases remain recall hints and cannot establish identity, authorization, exclusion, evidence, or write targets.
- **TQ-13:** Query Candidates cause no I&E call, network retrieval, Working Set update, Case write, publication, or product-tool decision; later exact retrieval requires a separately minted current Resource Candidate Reference, trusted recipe compilation, and fresh operation admission.
- **TQ-14:** missing action fails without a follow-up or second prompt; invalid/oversized/truncated/duplicate/conflicting/multi-proposal outcomes cannot use plan-dependent capabilities or leave a partial plan group.
- **TQ-15:** cancel, close, supersession, invalidation, timeout, ignored abort, late callback, conflict, and signing failure leave no eligible uncommitted plan.
- **TQ-16:** crash/reopen restores only committed qualified plans and never resumes a provider, replays the planning control action, or re-emits a terminal.
- **TQ-17:** compaction and branch summary receive only eligible plan/task entries and cannot manufacture provenance or revive an invalidated version.
- **TQ-18:** consecutive User Tasks in one Workspace do not reuse a plan across raw-task, branch, policy, capability, or Context Generation mismatch.
- **TQ-19:** safe telemetry contains counts/digests/reason codes only and no raw task, query, question, Orientation, credential, prompt, or completion body.
- **TQ-20:** all product behavior is accepted through `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn`; focused Pi tests prove lifecycle order without replacing public behavior evidence.
- **TQ-21:** product capability recipes and any Resource Candidate catalog become active only after the planning save point commits; rollback, conflict, signing failure, cancellation, and close retain the planning-only snapshot in memory and Session, and this contract fixes no product-tool name or decomposition.

## 15. Autonomous grill decisions and reopen conditions

| Question | Evidence and recommended answer | Decision | Reopen when |
|---|---|---|---|
| Is query rewrite its own Module? | Its authority, provenance, ambiguity, and lifecycle are all task-understanding concerns. | Keep it inside Task Context Understanding. | A backend-independent query lifecycle gains distinct callers and persistence. |
| Should planning use another model loop? | Pi already owns model/tool continuation, save points, abort, and recovery. | Use the same Agent Run and Harness. | Pi cannot isolate internal planning events or refresh tools/context after its save point. |
| Can the model select dependencies or tools? | Incorrect narrowing can admit stale history; tool visibility is capability policy. | Model proposes semantic needs only; code binds both. | A trusted non-model workflow supplies mechanically complete dependencies. |
| Can rewrite replace the task? | It loses user provenance and hides semantic drift. | Preserve raw task as the permanent source. | Never under this contract. |
| Must every ambiguity ask the user? | Many have safe, narrower read-only defaults; needless questions harm usability. | Use closed conservative fallbacks; clarify only material unsupported ambiguity. | Production evidence shows a fallback is misleading. |
| Can query candidates execute now? | I&E, egress, coverage, and backend contracts are frozen. | Persist as non-executable derivations only. | A separate I&E cycle qualifies its operation recipe and Adapter. |
| Is the extra planning call justified? | It buys a real Pi-native structured admission seam and avoids provider-specific sidecars. | Accept initially and measure. | Measured latency/cost requires a deterministic fast path or qualified sidecar. |
