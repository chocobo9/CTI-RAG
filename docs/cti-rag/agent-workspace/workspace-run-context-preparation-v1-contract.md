# `workspace-run-context-preparation/v1` Contract

Status: **Design PASS. Implementation readiness remains FAIL on prerequisite
delivery and the active terminology-migration kill switch.**

Evidence:
[Pi Context Capability Reuse Audit](../research/pi-context-capability-reuse-audit-2026-07-22.md).

## 1. Product responsibility

Workspace Run Context Preparation is the missing middle layer between
owner-qualified task/Case/Memory state and Pi.

It does not own Session history, Provider context, Tool schemas, Case storage or
Memory storage. It:

1. obtains already-qualified owner views;
2. validates that they share one Workspace/task/principal/use-purpose/Run basis;
3. creates one ephemeral Workspace Context Contribution;
4. records a non-content Workspace Context Binding;
5. adapts them into existing Pi hooks and Provider application authority; and
6. maps preparation/admission failures to Workspace results.

## 2. Logical inputs versus physical channels

The default first profile has seven logical inputs because the product currently
needs seven distinct meanings:

| Logical input | Owner | Pi channel |
| --- | --- | --- |
| system instructions | trusted application configuration | `systemPrompt` |
| Original User Task | Workspace committed source | current user message |
| Additional Task Context | Task Understanding handoff | Workspace Context envelope |
| Working State | Workspace owner | Workspace Context envelope |
| Case Context | Case/Orientation owner | Workspace Context envelope |
| eligible Session history | Pi Session plus Workspace policy | selected historical messages |
| active Tools | Workspace capability admission plus Pi Harness | `tools` |

The count is not a framework invariant. A future profile may add/remove a
logical input only when its owner, behavior and acceptance are independently
defined. Physical Provider channels remain Pi-owned.

## 3. Private deep Module

```typescript
interface WorkspaceRunContextPreparation {
	prepare(input: WorkspaceRunContextPreparationInputV1): Promise<WorkspaceRunContextPreparationOutcomeV1>;
}
```

The Module is private to `CaseWorkspace`. Tests use the public
`CaseWorkspaceModule.open -> prompt -> WorkspaceTurn` seam.

Preparation input references:

- committed Task Understanding handoff;
- Qualified Memory View and Memory Adoption Receipt;
- trusted instruction revision;
- admitted Tool/capability snapshot;
- current Session/branch/Run attempt;
- Access Principal, Case and Use Purpose binding;
- disclosure/token policy.

The input does not contain auth secrets, prepared Provider values or a copied
Session transcript.

## 4. Output artifacts

### Workspace Context Contribution

Ephemeral data rendered for one Run attempt:

```typescript
interface WorkspaceContextContributionV1 {
	protocol: "workspace-context-contribution/v1";
	blocks: {
		additionalTaskContext: unknown;
		workingState: unknown;
		caseContext: unknown;
		optionalRecall?: unknown;
	};
	rendererRevision: string;
	contributionDigest: string;
}
```

Every block retains owner, authority, status, source/version and omission labels
from its Qualified Memory Item. The envelope explicitly treats its bodies as
data, never system instructions, permission or Tool activation.

The envelope is transient. It is not appended as an ordinary Session message,
Case record, Workspace Artifact or Memory item.

### Workspace Context Binding

Durable non-content evidence:

- Workspace/task/Run attempt;
- principal/Case/Use Purpose binding;
- committed Task Context reference/digest;
- Memory Adoption Receipt reference/digest;
- owner source/version/generation references;
- renderer and policy revisions;
- admitted Tool snapshot reference;
- contribution digest;
- omission/conflict disclosure codes.

It does not copy owner bodies or predict Provider message/tool digests.

## 5. Pi adaptation

Preparation uses existing Pi seams:

1. reconstruct one Workspace-lifetime Harness once per successful `open`
   through the accepted PNW-B composition;
2. install the common `ContextEntryPolicy` for Session history;
3. use the Harness `context` hook to inject one Workspace Context Contribution
   ephemerally for the first no-tool Provider turn;
4. supply system instructions through Harness system-prompt configuration;
5. supply only admitted Tools through Harness active Tool configuration;
6. provide the Workspace Context Binding through Provider Dispatch
   `ApplicationAuthority`;
7. let Provider Dispatch canonicalize and exact-count the actual final
   `AgentContext`;
8. authorize only when actual prepared facts match the binding/profile;
9. commit the resulting application/Provider receipts through the accepted
   Session save-point seam.

No Workspace type aliases or wraps Pi `AgentContext`.

### 5.1 Exact Provider application binding

Workspace maintains one immutable expectation for each claimed Agent Run
attempt. It is created only after the Context Contribution and non-content
Context Binding are frozen, and it is looked up by the exact Pi
`attemptScope`. It contains no Provider message digest and performs no
canonicalization.

At `bindBeforeArtifact`, the application authority:

1. requires the exact expected Run attempt/scope;
2. revalidates the Task, principal/Case/Use Purpose, Memory adoption,
   instruction, Tool activation and disclosure-policy evidence;
3. checks Pi's safe prepared model and budget facts against the configured
   model/budget policy; and
4. returns this canonical binding payload:

```typescript
interface WorkspaceProviderApplicationBindingV1 {
	protocol: "workspace-provider-application-binding/v1";
	workspaceRef: string;
	taskRef: string;
	runAttemptRef: string;
	principalCaseUsePurposeDigest: string;
	taskHandoffDigest: string;
	memoryAdoptionReceiptDigest: string;
	workspaceContextBindingDigest: string;
	instructionBindingDigest: string;
	toolActivationBindingDigest: string;
	providerObservation: {
		modelDigest: string;
		credentialBindingDigest: string;
		systemPromptDigest: string;
		orderedMessageDigests: readonly string[];
		orderedToolDigests: readonly string[];
		optionsDigest: string;
		budgetDigest: string;
	};
}
```

Every member of `providerObservation` is copied byte-for-byte from
`ProviderDispatchSafePreparedFactsV1`; Workspace neither predicts nor recomputes
it. Pi snapshots the complete returned payload and owns
`applicationBindingDigest`. This joins Workspace evidence to what Pi actually
prepared without making Workspace another message/Tool canonicalizer.

At `authorizeAfterArtifact`, Workspace requires the artifact attempt scope and
all observed Pi digests to equal the retained binding, then performs one final
owner/version/generation revalidation. Its disclosure decision contains:

- decision `admitted_for_case_investigation`;
- exact application-binding and artifact digests;
- final revalidation evidence digest;
- omission/conflict codes; and
- policy revision.

The application prior-entry drafts contain only the non-content Memory Adoption
Receipt and Workspace Context Binding. The terminal opaque material contains
their references/digests, the final revalidation evidence digest and the
artifact digest. It contains no prompt, Session transcript, Case body, Memory
body, Tool schema, credential or prepared value.

Failure mapping is fixed:

| Pi application outcome | Workspace result |
| --- | --- |
| `unsupported_model` | `turn_failed(dispatch_unavailable)` |
| `budget_unavailable` | `turn_failed(policy_unavailable)` |
| `policy_denied` | `turn_failed(admission_integrity_failure)` |
| application timeout/temporary unavailable | `turn_failed(dispatch_unavailable)` |
| invalid/unknown/mutated binding or artifact mismatch | `turn_failed(admission_integrity_failure)` |
| Workspace owner/version/generation drift detected before authority return | existing dependency/session discard result, zero Provider start |

The Workspace Turn Adapter retains the exact internal Pi stage/code in
principal-safe evidence but exposes only the closed public failure above.

## 6. Ordering

For the first profile, Provider-visible order is:

```text
trusted system instructions
eligible Pi Session history
one labelled Workspace Context envelope
exact current Original User Task
```

Tools remain outside messages.

The exact Original User Task text/images occur once as the current user input.
Additional Task Context cannot replace or rewrite it.

If the existing `context` hook cannot produce this placement without guessing a
message boundary, the first public RED must stop implementation and trigger a
generic Pi seam design. It may not fall back to staging Session messages or
splicing context into the user task.

## 7. Timing

### After Task Understanding commit, before Run admission

- reconstruct mandatory Memory;
- prepare the contribution and binding;
- reserve no Provider work yet.

### Immediately before each Provider use

- ContextEntryPolicy requalifies Session history;
- Workspace revalidates owner/version/generation evidence;
- the context hook produces the exact transient contribution;
- Provider Dispatch prepares and exact-counts final Pi context;
- ApplicationAuthority compares actual prepared facts with the frozen profile;
- only then may the Adapter start.

### After save point and Run settlement

- commit adoption/model-input evidence;
- do not persist the transient context body as a new Memory copy;
- route any settled Memory candidate through Memory Coordination;
- Case changes only through Case Management acceptance.

## 8. Failure closure

| Failure | Outcome |
| --- | --- |
| mandatory owner view missing | no Agent Run |
| owner/principal/use-purpose/version mismatch | no Provider start |
| Session policy denial/drift | existing Pi context-policy failure mapped to Workspace |
| contribution cannot be placed without guessing | design blocker; no staging fallback |
| final prepared facts do not match profile/binding | Provider application denial |
| exact token budget exceeded | existing Provider Dispatch budget failure |
| optional recall unavailable but nonessential | bounded omission recorded |
| Workspace closes/turn supersedes/dependency changes | invalidate/discard under existing lifecycle |

## 9. Candidate acceptance

1. public prompt uses one leased Session generation, one Workspace-lifetime Harness and one Provider
   lifecycle;
2. exact Original User Task appears once;
3. only eligible Session entries appear and preserve Pi-selected order;
4. Additional Task Context, Working State and Case Context appear once inside
   one labelled transient envelope;
5. absent/empty blocks remain explicit when the profile requires them;
6. transient envelope creates no ordinary Session entry or duplicate owner
   record;
7. Tools appear only through Pi Tool schemas;
8. system instructions contain no untrusted Case/Working/recall body;
9. owner/principal/use-purpose/version drift starts zero Provider;
10. Provider Dispatch is the only final canonical/digest/token-count authority;
11. Workspace application binding joins exact owner/adoption evidence to the
    actual Provider artifact/receipt;
12. cancellation/failure creates no successful adoption or Run receipt;
13. later optional recall can populate its reserved envelope block without
    changing provider channels;
14. current Task Understanding, Session policy, Provider Dispatch and root
    regression remain green.

The PNW-B composition and message placement are closed at design level:
the context hook transforms Pi-selected persisted context, so appending one
Workspace envelope there places it after eligible history and before the exact
current Harness prompt without identifying message boundaries. The public
placement tracer remains required implementation evidence, not a design
blocker. Section 5.1 closes the exact Provider application binding, so this
matrix is frozen before the first implementation RED.

## 10. Design Gate

- **Verdict:** PASS
- **Owner:** Agent Investigation Workspace
- **Interface:** private preparation behind public `CaseWorkspace.prompt`
- **Input authority:** Task handoff, Qualified Memory View, owner evidence,
  principal/Case/Use Purpose, instruction/Tool policy
- **Output/evidence:** ephemeral contribution plus durable non-content binding
- **Failure closure:** specified
- **Secret isolation:** no auth/credential/prepared secret value
- **Provider lifecycle count:** exactly one
- **Workspace exposure:** public Turn behavior only
- **Backward compatibility:** staging Session/Harness is migration debt, not a
  compatibility path
- **Public acceptance seam:** `CaseWorkspaceModule.open -> prompt ->
  WorkspaceTurn`, actual faux Provider and actual Session entries
- **Remaining blockers:** none at design level. Implementation readiness still
  requires the accepted PNW-B runtime composition implementation, delivered
  mandatory owner-read prerequisites, and resolution of the current Workspace
  terminology-migration kill-switch checkpoint.
