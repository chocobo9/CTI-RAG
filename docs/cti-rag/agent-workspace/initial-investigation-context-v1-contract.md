# `workspace-initial-investigation-context/v1` Contract

Status: **Superseded design candidate; reference-only. No implementation is
authorized from this document.**

## Design disposition

The concrete seven-section product record, per-section digests, three synthetic
context messages and compiler-owned Provider projection below are rejected as
duplicate design. They remain only as history of the evaluated candidate.

The active candidate is
[`workspace-run-context-preparation/v1`](workspace-run-context-preparation-v1-contract.md).
It preserves the currently required business meanings without fixing their
count as a framework invariant. It maps them into Pi-owned `systemPrompt`,
ordered `messages` and `tools`, uses one ephemeral Workspace Context envelope,
and leaves final canonicalization, digests and exact counting to Provider
Dispatch. Its Design Gate remains FAIL pending the stated PNW-B, placement and
application-authority blockers.

The current reuse and maturity assessment is recorded in
[`initial-context-industry-reuse-audit-2026-07-22.md`](../research/initial-context-industry-reuse-audit-2026-07-22.md).

The superseded candidate below explored PNW-C Initial Investigation Context compilation. Its
seven logical authorities, concrete records, Pi channel mapping, digest
boundaries, and acceptance matrix are under reuse and industry-pattern audit;
none is frozen. It does not implement Investigation Run Control,
Working Set mutation, product Tools, optional historical recall, Artifact
persistence, output publication, I&E consumption, Case writes, a real Provider,
or live OpenCTI.

## 1. Decision and ownership

`InitialInvestigationContextCompiler` is one Workspace-private in-process deep
Module. Its only semantic operation is:

```typescript
interface InitialInvestigationContextCompiler {
	compile(input: InitialInvestigationContextCompilationInputV1): InitialInvestigationContextCompilationOutcomeV1;
}
```

It hides section validation, dependency qualification, deterministic rendering,
token-independent canonicalization, digest construction, Pi channel mapping,
and failure precedence. It performs no model call, Session mutation, remote I/O,
Artifact lookup, semantic search, Tool execution, or Run start.

Ownership is fixed:

| Module | Owns | Must not own |
|---|---|---|
| Task Understanding | immutable Original User Task, admitted Additional Task Context, committed handoff | Initial context type, history selection, Case rendering, Working Set, Tools |
| Workspace compiler | seven-section manifest, owner-local inputs, rendering, channel mapping, context identity | Session storage, Case truth, I&E truth, provider auth, Agent loop |
| Pi Session/Harness | retained entries, branch/head, compaction ancestry, context-policy selection, provider message execution, active Tool transport | CTI eligibility meaning, Case authority, Working Set admission |
| Case owner / Orientation Adapter | current principal/use-purpose-authorized Case material and evidence | Session history, task interpretation, Tool activation |
| Working Set owner | selected task material, exact resource/version/render evidence | Case authority, Session transcript |
| Capability owner | deterministic Tool activation snapshot | model-supplied authorization |

There is no unified Memory Module. Mandatory context is reconstructed from the
existing owners. Optional historical recall is outside this v1 compiler.

## 2. Common primitives and canonical rules

All records are recursively snapshotted before validation. Unknown members,
`undefined`, non-finite numbers, cycles, functions, symbols, accessors, duplicate
identities, invalid UTF-16, or non-canonical ordered collections reject.

`piDigest(value)` means `sha256:` plus lowercase SHA-256 of the RFC 8785 JCS
UTF-8 bytes of `value`. A record digest is computed over the complete record
with only that digest field omitted. Arrays are order-sensitive and are never
sorted after receipt from an owner. Empty arrays are meaningful values, never
equivalent to absent fields.

```typescript
type InitialInvestigationContextSectionV1 =
	| "system_instructions"
	| "original_user_task"
	| "additional_task_context"
	| "working_set"
	| "layered_case_context"
	| "eligible_session_history"
	| "activated_tools";

const INITIAL_INVESTIGATION_CONTEXT_SECTION_ORDER_V1 = [
	"system_instructions",
	"original_user_task",
	"additional_task_context",
	"working_set",
	"layered_case_context",
	"eligible_session_history",
	"activated_tools",
] as const;
```

This tuple is the logical authority/manifest order. It is not a claim that
provider transcript messages are physically reordered out of chronology.
The candidate section-to-channel mapping appears in section 6; it is not
accepted.

## 3. Trusted compilation input

```typescript
interface InitialInvestigationContextCompilationInputV1 {
	protocol: "workspace-initial-investigation-context-compilation/v1";
	contextId: string;
	workspaceRef: string;
	principalCaseUsePurposeDigest: string;
	providerMessageTimestampMs: number;
	taskUnderstandingHandoff: CommittedTaskUnderstandingHandoffV1;
	systemInstructions: TrustedSystemInstructionsV1;
	workingSet: InitialWorkingSetSnapshotV1;
	caseContext: InitialLayeredCaseContextV1;
	sessionHistory: EligibleSessionHistorySnapshotV1;
	tools: ActivatedToolSnapshotV1;
	compilationProfile: "new_task_no_tool/v1";
	inputDigest: string;
}
```

The compiler first recomputes the complete Task Understanding handoff, its A4
commit evidence, Original User Task digest, and Admitted Task Context digest.
It then proves that every other input binds the same Workspace, Access
Principal, Case, Use Purpose, task, Session branch/head, and Context Generation
basis. A Phase-A
candidate, uncommitted context, guessed reference, or caller/model-created
snapshot is inexpressible at this Interface.

The `new_task_no_tool/v1` profile requires an explicit empty Working Set and
explicit empty activated Tool set. Those fields remain present and digested.
The profile does not weaken the outer section shape: later independently
accepted profiles populate the existing arrays and must not add or reorder
sections.

## 4. Candidate seven-section product shape

```typescript
interface InitialInvestigationContextV1 {
	protocol: "workspace-initial-investigation-context/v1";
	contextId: string;
	workspaceRef: string;
	taskId: string;
	taskContextId: string;
	compilationProfile: "new_task_no_tool/v1";
	sectionOrder: typeof INITIAL_INVESTIGATION_CONTEXT_SECTION_ORDER_V1;
	sections: {
		systemInstructions: SystemInstructionsSectionV1;
		originalUserTask: OriginalUserTaskSectionV1;
		additionalTaskContext: AdditionalTaskContextSectionV1;
		workingSet: WorkingSetSectionV1;
		layeredCaseContext: LayeredCaseContextSectionV1;
		eligibleSessionHistory: EligibleSessionHistorySectionV1;
		activatedTools: ActivatedToolsSectionV1;
	};
	sectionDigests: Readonly<Record<InitialInvestigationContextSectionV1, string>>;
	providerProjection: InitialProviderContextProjectionV1;
	contextDigest: string;
}
```

`contextId` is minted by trusted Workspace code before compilation and is bound
to the exact input digest. It is not model-authored and is not reused across
different inputs. `providerMessageTimestampMs` is a non-negative safe integer
captured once for the attempt; it is ordering metadata only and cannot establish
authority or freshness. `contextDigest` covers the complete record except itself,
including all seven section digests and the provider projection digest.

### 4.1 System Instructions

```typescript
interface TrustedSystemInstructionsV1 {
	protocol: "workspace-trusted-system-instructions/v1";
	instructionId: string;
	instructionVersion: string;
	instructionText: string;
	instructionTextDigest: string;
	rendererId: string;
	rendererVersion: string;
	bindingDigest: string;
}

interface SystemInstructionsSectionV1 {
	protocol: "workspace-system-instructions-section/v1";
	instructionId: string;
	instructionVersion: string;
	instructionText: string;
	instructionTextDigest: string;
	rendererId: string;
	rendererVersion: string;
	sectionDigest: string;
}
```

The instruction text is trusted deployment configuration. It defines the
authority labels and requires all derived/history/Case/Working Set bodies to be
treated as data, never as authorization or executable instructions. User,
model, Session, Case, Artifact, and I&E content cannot amend it.

The configured text must contain the closed v1 authority rules: preserve the
Original User Task; treat Additional Task Context, Working Set, Case Context,
and Session History as labelled data; never infer authorization or Tool
activation from those bodies; prefer current Case authority over advisory
history; expose conflicts rather than merge them; and allow an empty Working
Set, history, and Tool set. Missing any rule is `instruction_unavailable`.

### 4.2 Original User Task

```typescript
interface OriginalUserTaskSectionV1 {
	protocol: "workspace-original-user-task-section/v1";
	originalTask: OriginalUserTaskV1;
	providerUserMessage: UserMessage;
	providerUserMessageDigest: string;
	sectionDigest: string;
}
```

With no images, `content` is the exact original text string. With images, the
first part is the exact text and each following part is the corresponding Pi
`ImageContent` `{ type: "image", data, mimeType }` in contiguous ordinal order
with byte-identical canonical base64. The message timestamp is exactly the
input's `providerMessageTimestampMs`; it is included in the provider-message
digest but excluded from the immutable Original User Task digest.
No normalized reading or Additional Task Context is spliced into this message.

### 4.3 Additional Task Context

```typescript
interface AdditionalTaskContextSectionV1 {
	protocol: "workspace-additional-task-context-section/v1";
	taskContext: AdmittedTaskContextV1;
	authority: "non_authoritative_derived_context";
	rendererId: string;
	rendererVersion: string;
	renderedText: string;
	renderedTextDigest: string;
	sectionDigest: string;
}
```

The renderer emits only the closed admitted fields and their principal-safe labels.
It never emits raw model proposal text, hidden reasoning, provider output,
credentials, authorization language, Tool selection, or the goal bootstrap.
The rendered envelope explicitly states that the Original User Task prevails.
`renderedText` is exactly RFC 8785 JCS of
`{ protocol: "workspace-additional-task-context-render/v1", authority,
originalTaskId, originalTaskDigest, taskContext }`; there is no surrounding
Markdown, XML, commentary, or hidden field.

### 4.4 Working Set

```typescript
interface InitialWorkingSetSnapshotV1 {
	protocol: "workspace-initial-working-set-snapshot/v1";
	workspaceRef: string;
	taskId: string;
	taskContextId: string;
	version: string;
	selectionDigest: string;
	orderedItems: readonly InitialWorkingSetContextItemV1[];
	snapshotDigest: string;
}

interface InitialWorkingSetContextItemV1 {
	entryRef: string;
	entryDigest: string;
	resourceVersionRef: string;
	renderManifestDigest: string;
	renderedContentDigest: string;
	renderedText: string;
}

interface WorkingSetSectionV1 {
	protocol: "workspace-working-set-section/v1";
	snapshot: InitialWorkingSetSnapshotV1;
	authority: "selected_source_material_not_case_truth";
	rendererId: string;
	rendererVersion: string;
	renderedText: string;
	renderedTextDigest: string;
	sectionDigest: string;
}
```

For `new_task_no_tool/v1`, `orderedItems` is exactly `[]` and the deterministic
render is the fixed explicit empty-state envelope. Absence, omitted rendering,
an empty string, or a fabricated item is invalid. A later Working Set profile
may populate the same array only with records admitted by the owning Working
Set contract and current disclosure revalidation; it does not change this outer
Interface.

For that profile, `version` is exactly `"initial-empty/v1"` and
`selectionDigest = piDigest({ protocol:
"workspace-empty-working-set-selection/v1", workspaceRef, taskId,
taskContextId, orderedItems: [] })`. `renderedText` is exactly RFC 8785 JCS of
`{ protocol: "workspace-working-set-render/v1", authority, version,
selectionDigest, items: [] }`.

### 4.5 Layered Case Context

```typescript
interface InitialLayeredCaseContextV1 {
	protocol: "workspace-initial-layered-case-context/v1";
	workspaceRef: string;
	principalCaseUsePurposeDigest: string;
	orientation: {
		orientationRef: string;
		bindingDigest: string;
		semanticDigest: string;
		contextGenerationDigest: string;
		renderedText: string;
		renderedTextDigest: string;
	};
	projection:
		| { kind: "absent" }
		| {
				kind: "present";
				projectionRef: string;
				projectionDigest: string;
				orientationBasisDigest: string;
				contextGenerationDigest: string;
				renderedOverlayText: string;
				renderedOverlayDigest: string;
		  };
	caseContextDigest: string;
}

interface LayeredCaseContextSectionV1 {
	protocol: "workspace-layered-case-context-section/v1";
	caseContext: InitialLayeredCaseContextV1;
	authority: "orientation_evidence_with_optional_bound_projection";
	rendererId: string;
	rendererVersion: string;
	renderedText: string;
	renderedTextDigest: string;
	sectionDigest: string;
}
```

Orientation is mandatory. Projection is an overlay and cannot replace the
Orientation basis. The current read-only profile requires `projection.kind =
"absent"`. Equal displayed text with different binding, source, Access Principal, Use Purpose,
or Context Generation is not interchangeable.

`renderedText` is exactly RFC 8785 JCS of
`{ protocol: "workspace-layered-case-context-render/v1", authority,
orientation, projection }`, using the validated Orientation render and, only
when present, the validated bound Projection overlay. Equal prose with a
different evidence field is a different section.

### 4.6 Eligible Session History

```typescript
interface EligibleSessionHistorySnapshotV1 {
	protocol: "workspace-eligible-session-history-snapshot/v1";
	sessionRef: string;
	branchRef: string;
	headEntryRef: string | null;
	compactionBasisDigest: string | null;
	contextGenerationDigest: string;
	eligibilityPolicyRevision: string;
	orderedEntries: readonly EligibleSessionHistoryEntryV1[];
	selectionDigest: string;
	snapshotDigest: string;
}

interface EligibleSessionHistoryEntryV1 {
	entryRef: string;
	entryDigest: string;
	parentEntryRef: string | null;
	entryKind: "user" | "assistant" | "tool_result" | "compaction_summary" | "branch_summary";
	dependencyGenerationDigest: string;
	providerMessageDigests: readonly string[];
	providerMessages: readonly ProviderHistoryMessageV1[];
}

type ProviderHistoryMessageV1 = UserMessage | AssistantMessage | ToolResultMessage;

interface EligibleSessionHistorySectionV1 {
	protocol: "workspace-eligible-session-history-section/v1";
	snapshot: EligibleSessionHistorySnapshotV1;
	authority: "historical_interaction_not_case_truth";
	sectionDigest: string;
}
```

This section is mandatory base reconstruction, not optional semantic memory
search. Pi supplies the retained branch/compaction evidence and Workspace
policy interprets CTI eligibility. Selection must preserve source order and may
be empty. Partial, stale, withdrawn, wrong-principal, wrong-use-purpose, wrong-Case,
wrong-task, wrong-branch, old-generation, uncommitted, raw candidate, and
receipt-invalid entries are excluded without revealing hidden identities or
counts. The compiler performs no relevance search and never substitutes history
for unavailable current Case context.

`UserMessage`, `AssistantMessage`, and `ToolResultMessage` are the exact current
Pi AI message types. Their complete closed content variants are validated and
digested by the lifecycle contract's section 6.6.1 schema; this contract does
not introduce a looser message grammar or a second canonicalization owner.

### 4.7 Activated Tools

```typescript
interface ActivatedToolSnapshotV1 {
	protocol: "workspace-activated-tool-snapshot/v1";
	workspaceRef: string;
	taskId: string;
	taskContextId: string;
	activationSnapshotRef: string | null;
	activationSnapshotDigest: string | null;
	orderedTools: readonly ActivatedProviderToolV1[];
	snapshotDigest: string;
}

interface ActivatedProviderToolV1 {
	name: string;
	description: string;
	parameters: { readonly [key: string]: PiCanonicalJsonV1 };
	schemaDigest: string;
}

interface ActivatedToolsSectionV1 {
	protocol: "workspace-activated-tools-section/v1";
	snapshot: ActivatedToolSnapshotV1;
	authority: "deterministically_activated_capabilities";
	sectionDigest: string;
}
```

For `new_task_no_tool/v1`, both activation fields are `null` and `orderedTools`
is exactly `[]`. The Provider context still contains an explicit empty Tool
array. A missing field, model-proposed Tool, prose Tool description inserted as
a message, or unbound schema is invalid. Later profiles populate this same slot
through an accepted capability-activation contract; Tool number and product
decomposition remain deliberately unfixed.

`PiCanonicalJsonV1` is the shared closed JSON grammar owned by the
Pi-native lifecycle contract. Tool names, descriptions, parameters, order, and
schema digests must equal the final Pi Provider Dispatch projection exactly.
For the empty profile, `snapshotDigest = piDigest({ protocol:
"workspace-activated-tool-snapshot/v1", workspaceRef, taskId, taskContextId,
activationSnapshotRef: null, activationSnapshotDigest: null, orderedTools: []
})`.

## 5. Memory reconstruction and recall boundary

The compiler consumes owner-qualified snapshots; it does not retrieve them.
The mandatory base consists of current instructions, committed task/handoff,
explicit Working Set state, current Case Context, eligible Pi Session history,
and activated Tools. This base is rebuilt for the current task and is not called
"memory search".

Optional historical recall is a later Workspace decision with the fixed order:

```text
need decision -> owner routing -> hard eligibility -> relevance ranking
-> bounded Workspace adoption -> final pre-disclosure revalidation
```

No global search may precede owner and eligibility selection. Cross-Case
procedure/experience/preferences have no accepted owner and return no result.
Historical Workspace Artifact discovery is not part of this v1 compiler. An
Artifact never appears automatically merely because it belongs to the Case;
future adoption requires a separate owner-local contract and must map into an
existing qualified context position without adding hidden authority.

Deletion, withdrawal, expiry, authorization loss, marking drift, Case revision
drift, Resource Version drift, branch change, or Context Generation change must
make affected material ineligible before provider disclosure. Re-ranking is not
requalification.

## 6. Exact Pi and Provider channel mapping

```typescript
interface InitialProviderContextProjectionV1 {
	protocol: "workspace-initial-provider-context-projection/v1";
	systemPrompt: string;
	systemPromptDigest: string;
	orderedHistoryMessages: readonly ProviderHistoryMessageV1[];
	orderedHistoryMessageDigests: readonly string[];
	originalUserMessage: OriginalUserTaskSectionV1["providerUserMessage"];
	originalUserMessageDigest: string;
	derivedContextSectionOrder: readonly [
		"additional_task_context",
		"working_set",
		"layered_case_context",
	];
	derivedContextMessages: readonly [UserMessage, UserMessage, UserMessage];
	derivedContextMessageDigests: readonly [string, string, string];
	orderedTools: readonly ActivatedProviderToolV1[];
	orderedToolSchemaDigests: readonly string[];
	projectionDigest: string;
}

```

The logical seven-section manifest maps to Pi as follows:

| Logical section | Pi/Provider channel |
|---|---|
| System Instructions | `AgentContext.systemPrompt` only |
| Original User Task | exact Harness prompt user message with exact images |
| Additional Task Context | first ephemeral derived-context message |
| Working Set | second ephemeral derived-context message, including explicit empty envelope |
| Layered Case Context | third ephemeral derived-context message |
| Eligible Session History | context-policy-selected chronological messages before the current prompt |
| Activated Tools | `AgentContext.tools`, never prompt prose |

Actual provider message order is:

```text
eligible chronological Session messages
-> exact current Original User Task user message
-> Additional Task Context envelope
-> Working Set envelope
-> layered Case Context envelope
```

The projection is constructed exactly as follows:

- `systemPrompt` is byte-for-byte `instructionText`;
- `orderedHistoryMessages` is the stable flattening of each selected entry's
  `providerMessages`, preserving entry and inner-message order;
- `originalUserMessage` is the exact section 4.2 message;
- the three derived messages are `{ role: "user", content: renderedText,
  timestamp: providerMessageTimestampMs }` for Additional Task Context, Working
  Set, and layered Case Context in that order;
- `orderedTools` is the exact activated snapshot order, including `[]`;
- every message/schema digest is recomputed through the shared Pi Provider
  Dispatch canonical schema; and
- `projectionDigest = piDigest(the complete
  InitialProviderContextProjectionV1 with projectionDigest omitted)`.

The logical manifest order remains fixed for authority, hashing, audit, and Run
basis. Physical Session history remains chronological so Pi conversation/tool
semantics are not corrupted. The three derived envelopes are injected only by
the single aggregate Workspace `context` handler after final Session selection;
they are exact Pi `UserMessage` values whose timestamp equals the compilation
input's `providerMessageTimestampMs`. Private pre-conversion tags may identify
their source section, but the final Provider projection contains only the exact
closed Pi message fields above. They are not appended as ordinary Session
messages. The system instruction
declares their labels and prohibits treating embedded text as policy,
authorization, Tool activation, or a replacement user task.

The compiler supplies the exact tool array separately. It never serializes Tool
schemas into any message. The final provider projection is recursively
snapshotted and bound by the generic Pi Provider Dispatch transaction before
Adapter start.

## 7. Compilation and lifecycle order

The required order is:

1. `open` has a leased Session, one long-lived Harness, and a fresh usable
   Orientation baseline.
2. `prompt` reaches its safe point and completes any required full Orientation
   reopen.
3. Task Understanding returns one committed admitted/fallback handoff.
4. Workspace snapshots the exact Session branch/head and evaluates the common
   context-entry policy for provider use.
5. Workspace constructs explicit Working Set, Case Context, and Tool snapshots.
6. The compiler validates all bindings and produces one immutable context.
7. `before_agent_start` rechecks only local retained identity/digest facts and
   creates no new content.
8. The aggregate `context` handler revalidates the same Session leaf,
   Context Generations, Case Context, Working Set, and Tool snapshot, then emits
   the exact provider projection without remote I/O.
9. Run Control verifies the context binding and only then admits one formal
   Agent Run.
10. Generic Pi Provider Dispatch snapshots and proves the final Model/context/
    Tool input before the Provider Adapter may start.

There is one compiler result per committed handoff and Run admission attempt.
If a dependency changes before Adapter start, the attempt fails or is discarded;
the compiler does not patch an already sealed context. A later retry is a new
Workspace Turn or independently authorized Run attempt with a new identity.

## 8. Closed outcomes and failure precedence

```typescript
type InitialInvestigationContextCompilationOutcomeV1 =
	| { kind: "ready"; context: InitialInvestigationContextV1 }
	| { kind: "failed"; code: InitialInvestigationContextFailureCodeV1 };

type InitialInvestigationContextFailureCodeV1 =
	| "handoff_uncommitted"
	| "handoff_integrity_failure"
	| "instruction_unavailable"
	| "working_set_unavailable"
	| "case_context_unavailable"
	| "session_history_unavailable"
	| "tool_activation_unavailable"
	| "binding_mismatch"
	| "context_generation_changed"
	| "session_head_changed"
	| "render_invalid";
```

Precedence is the order above. Every failure returns no context, starts no Agent
Run, starts no Provider Adapter, appends no Run entry, and emits no model delta.
Failure metadata is principal-safe and contains no hidden history, Artifact,
resource, auth, Case member, or Tool identity.

Mandatory current instructions, committed task, current Case Context, or exact
Session qualification unavailable is closed failure; history cannot substitute
for it. Empty eligible history is valid. Empty Working Set and Tools are valid
only for a profile that requires them. Optional recall failure cannot affect
this profile because optional recall is not invoked.

Public mapping is exact:

| Compilation code | Workspace terminal |
|---|---|
| `handoff_uncommitted`, `handoff_integrity_failure`, `binding_mismatch` | `turn_failed(admission_integrity_failure)` |
| `instruction_unavailable`, `working_set_unavailable`, `tool_activation_unavailable` | `turn_failed(policy_unavailable)` |
| `case_context_unavailable` | `turn_failed(orientation_not_usable)` |
| `session_history_unavailable` | `turn_discarded(recovery_provenance_untrusted)` |
| `context_generation_changed` | `turn_discarded(dependency_version_changed)` |
| `session_head_changed` | `turn_discarded(session_binding_changed)` |
| `render_invalid` | `turn_failed(schema_or_mapping_mismatch)` |

The compiler applies the shared Pi canonical depth/count/JCS/UTF-8 budgets.
Exact model token and output reservation limits are evaluated later from the
final prepared context by the generic Provider Dispatch and Run budget seams;
the compiler never estimates tokens from characters or bytes.

## 9. Candidate public Interface and review matrix

The product Interface remains:

```text
CaseWorkspaceModule -> CaseWorkspace.prompt -> WorkspaceTurn
```

The compiler is private. Acceptance observes the actual fake Provider context,
actual Pi Session entries, Workspace events/results, and Provider/Tool start
counts. It does not expose a compiler test Interface or accept tests that only
assert private function calls.

- **IIC-01 Exact shape:** one admitted public prompt produces exactly the fixed
  seven-section manifest, all seven section digests, one provider projection,
  and one context digest before the first Investigation Provider start.
- **IIC-02 Original authority:** exact task text and image bytes appear once as
  the current user message; normalized/derived text remains in the separate
  Additional Task Context envelope and cannot replace it.
- **IIC-03 Explicit empty slots:** new-task no-tool context contains a present,
  digest-bound empty Working Set envelope and present empty Provider Tool array;
  omitted, `undefined`, prose-only, or fabricated alternatives fail before Run.
- **IIC-04 Case layering:** Orientation is always present; absent Projection is
  explicit. A mismatched Projection basis, principal/use-purpose, binding, semantic
  digest, or generation starts no Run or Provider.
- **IIC-05 Eligible history:** only exact source-ordered current-branch entries
  selected by the common policy reach the fake Provider. Partial, stale,
  unauthorized, wrong-task, old-generation, uncommitted, withheld candidate,
  and hidden alternatives do not leak identities, counts, or bodies.
- **IIC-06 Memory boundary:** initial compilation performs zero Artifact, I&E,
  Case-history, vector, embedding, semantic-search, preference, or cross-Case
  recall calls. Eligible Session history remains available through its owner.
- **IIC-07 Channel mapping:** system rules use only system prompt; the three
  derived envelopes are ephemeral context messages and create no Session
  entries; Tools use only Provider Tool schemas. The actual provider projection
  matches its recorded ordered digests.
- **IIC-08 Mutation isolation:** mutation of any source object, rendered text,
  image, history message, schema, or nested value after snapshot changes neither
  the sealed context nor Adapter input; a supplied digest cannot override a
  recomputation mismatch.
- **IIC-09 Revalidation:** Session leaf, branch, Context Generation, Case
  Context, Working Set, instruction, or Tool drift at each pre-start seam fails
  with zero Provider start and zero Run write. `A -> B -> A` never revives old
  history.
- **IIC-10 Lifecycle:** Task Understanding commit precedes context compilation;
  context readiness precedes Run admission; Run admission precedes Provider
  start. Clarification and every compilation failure start no Agent Run.
- **IIC-11 One execution spine:** one open Workspace uses one leased Session,
  one long-lived Harness, and the shared Provider Dispatch core. No staging
  Session/Harness, copied transcript, second Agent, or second Provider lifecycle
  appears.
- **IIC-12 Public behavior:** success, cancellation, failure, invalidation, and
  close retain stable Turn identity, strictly increasing events, one terminal,
  and a non-rejecting result; raw derived envelopes or failure details are not
  public events.
- **IIC-13 Regression:** Task Understanding focused acceptance, Workspace
  Orientation behavior, Pi context policy, Provider Dispatch, Session control,
  repository/lease, run-generation, settlement, and root check remain green.

## 10. Gates and deferred work

The Design Gate is FAIL. Before this candidate can become normative, the Planner
must prove which parts reuse Pi's existing `AgentContext`, context-entry policy,
Provider Dispatch canonicalization, and owner records; remove duplicate product
shapes and digest authorities; validate the remaining additions against
primary-source industry practice; and freeze PNW-B's long-lived Workspace
composition seam used by IIC-11. The matrix above is review material, not frozen
acceptance, and no implementation task may use it.

Separately gated:

- optional same-Case Workspace Artifact discovery and adoption;
- cross-Case procedure/experience and user/team preferences;
- non-empty Working Set and I&E disclosure;
- non-empty product Tool activation and model-visible Tool decomposition;
- in-Run subquestion/Query Candidate/capability carrier;
- compaction/tree and context-generation v2 integration;
- output publication and later-context eligibility;
- Artifact persistence, Assessment, Case writes, real Provider, and live
  OpenCTI.
