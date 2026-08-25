# Workspace Output Publication v1 Contract

**Protocol:** `workspace-output-publication/v1`  
**Owner:** CTI-RAG Agent Workspace  
**Status:** Independent design acceptance PASS; implementation NO-GO  
**Depends on:** `pi-native-workspace-lifecycle/v1`,
`pre-investigation-task-understanding/v1`, `opencti-case-orientation/v1`,
`investigation-run-control/v1`, and the independently gated PNW-C Context
Snapshot, PNW settlement, protected-inspection, disclosure-fence, and
SessionRepository recovery amendments described below  
**Default authority:** non-authoritative Workspace output  

Task Outcome amendment status: **Design Gate FAIL.** This accepted baseline
publishes `ModelResponseCandidateV1` directly from the final Investigation
Agent turn. The target workflow first creates the distinct private
[`workspace-task-result/v1`](task-result-v1-contract.md), then Evidence
Assembly, a Report Evidence Packet and a separately composed Task Outcome
Report candidate under
[`workspace-task-outcome-report/v1`](task-outcome-report-v1-contract.md).
`ModelResponseCandidateV1` cannot substitute for any of those products. The
Task Outcome Report contract must version or supersede the
candidate/basis/output/streaming sections below; that target does not inherit
this contract's PASS.

The versioned delivery shape is now defined by
[`workspace-task-outcome-publication-stream/v1`](task-outcome-publication-stream-v1-contract.md).
It preserves this baseline's atomic commit and raw-delta isolation while
allowing deterministic chunks only after the complete report receipt commits.
Its own Design Gate remains FAIL.

This contract depends on public protocol amendments that do not exist in the
accepted Pi/Workspace surface yet: an Agent Run settlement binding that carries
the exact response-candidate proof, a completed Workspace Turn result that
carries `PublishedWorkspaceOutputV1` instead of raw `AssistantMessage`, and a
receipt-aware later-context projection rule. Those are independently gated
targets. Nothing in this document claims they are implemented or weakens their
own ownership and acceptance gates.

## 1. Purpose

This contract defines the only Workspace Module that may turn a completed model
response candidate into caller-visible investigation output:

```text
ModelResponseCandidate
    -> WorkspacePublicationDecision
    -> PublishedWorkspaceOutput | none
```

The Module is a policy boundary, not a renderer around a provider stream. It
owns validation, publication eligibility, citation resolution, authorization
revalidation, and the atomic publish-or-none decision. Pi owns Session and
Harness mechanics, final save points, Agent Run settlement, run generations,
and the control-record commit seam on which publication depends.

The central safety rule is:

> An ordinary caller receives zero content-bearing model delta, candidate text,
> citation text, or provider content before a valid publish decision receipt is
> durably committed.

This rule applies even when the candidate is later cancelled, refused,
malformed, invalidated, superseded, withheld, or lost to a commit conflict.

## 2. Normative language

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative. A value described as
closed rejects unknown members. A digest is lowercase
`sha256:<64 lowercase hexadecimal characters>`.

`ordinary caller` means any caller of the public Workspace Turn Interface that
has not been admitted to a separate privileged diagnostic capability. This v1
contract defines no such diagnostic capability.

`content-bearing` includes answer text, partial answer text, reasoning,
thinking blocks, citation excerpts, source bodies, provider error bodies, tool
arguments or results, and any transformation from which those values can be
recovered. Counts, stable phase names, and actor-safe closed failure codes are
not content-bearing.

## 3. Scope

This contract closes:

1. the internal model-response candidate schema and bounds;
2. the trusted publication basis and its Pi/Workspace seam;
3. the citation catalog and exact citation resolution rules;
4. settlement, save-point, Session, context-generation, capability,
   authorization, Orientation, and optional Projection-overlay validation;
5. secret, partial, stale, unknown, and unauthorized isolation;
6. the closed publication-decision and published-output schemas;
7. the publication linearization point, crash windows, and reopen behavior;
8. public Workspace event and result mapping;
9. the first Pi-native no-tool vertical slice; and
10. independent acceptance obligations.

This contract does not authorize I&E retrieval, a Working Set implementation,
Artifact persistence, Assessment, Case writes, live provider activation, tool
execution, a general task DAG, recursive planning, or sub-Agents.

## 4. Module boundary and ownership

### 4.1 Deep Module

The Workspace owns one deep Module named here as
`WorkspaceOutputPublicationModule`. Its public-to-the-package Interface has one
semantic operation:

```ts
interface WorkspaceOutputPublicationModule {
  decideAndCommit(
    input: WorkspaceModelResponseCandidateInputV1,
  ): Promise<WorkspacePublicationOutcomeV1>;
}

type WorkspaceModelResponseCandidateInputV1 =
  | {
      kind: "candidate_ready";
      candidate: ModelResponseCandidateV1;
      candidateDigest: PiDigestV1;
      basis: TrustedWorkspacePublicationBasisV1;
    }
  | {
      kind: "candidate_failed";
      identity: WorkspacePublicationIdentityV1;
      phase: "provider_terminal";
      reason:
        | "candidate_incomplete"
        | "candidate_unsupported_content"
        | "candidate_refused";
      finalAssistantEntry: PiSessionSlotV1<{
        entryId: string;
        entryDigest: PiDigestV1;
        contentDigest: PiDigestV1;
      }>;
      failureDigest: PiDigestV1;
      policy: PublicationPolicyBindingV1;
    }
  | {
      kind: "candidate_failed";
      identity: WorkspacePublicationIdentityV1;
      phase: "envelope_decode";
      reason:
        | "candidate_incomplete"
        | "candidate_malformed"
        | "candidate_exceeds_bounds"
        | "candidate_unsupported_content";
      finalAssistantEntry: {
        presence: "present";
        value: {
          entryId: string;
          entryDigest: PiDigestV1;
          contentDigest: PiDigestV1;
        };
      };
      failureDigest: PiDigestV1;
      policy: PublicationPolicyBindingV1;
    }
  | {
      kind: "candidate_failed";
      identity: WorkspacePublicationIdentityV1;
      phase: "candidate_binding";
      reason: "candidate_digest_mismatch";
      finalAssistantEntry: {
        presence: "present";
        value: {
          entryId: string;
          entryDigest: PiDigestV1;
          contentDigest: PiDigestV1;
        };
      };
      failureDigest: PiDigestV1;
      withholdControl: WorkspacePublicationFailureCommitControlV1;
    };

interface WorkspacePublicationFailureCommitControlV1 {
  protocol: "workspace-publication-failure-commit-control/v1";
  session: SessionPublicationBindingV1;
  policy: PublicationPolicyBindingV1;
  availableEvidence: WorkspacePublicationCandidateBindingFailureEvidenceV1;
  controlDigest: PiDigestV1;
}
```

The names are contractual; an implementation MAY use different private class
or function names. The Interface MUST remain narrow. Citation resolution,
authorization revalidation, drift checks, secret scanning, canonicalization,
receipt construction, and Session compare-and-append belong behind it and MUST
NOT be distributed among Harness event callbacks or public Turn consumers.

`TrustedWorkspacePublicationBasisV1` is an internal trusted value. It MUST be
assembled from verified Pi and Workspace control records. A provider, model,
extension, public caller, or untrusted adapter MUST NOT construct or amend it.

The tagged input is required because refusal, unsupported provider content,
truncation, malformed envelopes, and binding failures occur before a valid
`ModelResponseCandidateV1` exists. `candidate_failed` is therefore a formal
input, not an exception coerced into a fake candidate. Its closed phase
determines whether durable publication facts may exist. `provider_terminal` and
`envelope_decode` occur before a final save point and before Pi settlement;
they return an in-memory actor-safe withhold decision and prepare no publication
group. Only `candidate_binding` can map to a durable
`candidate_binding_failure` receipt, and only with its exact committed final
save point and Pi completed settlement. `candidate_ready` maps to
`candidate_evaluated`. No phase normalization or fallback is permitted.
`failureDigest = piDigest(the complete candidate_failed input with
failureDigest and policy/withholdControl omitted)`, while `controlDigest`
hashes the complete failure commit control with only `controlDigest` omitted.
Neither
digest includes candidate bytes, provider bodies, or secret values.

### 4.2 Pi-owned seam

Pi owns and supplies verifiable references for:

- the long-lived Session and Harness identities;
- branch, Session head, context generation, run identity, attempt, and run
  generation;
- the final committed save point and exact final assistant entry;
- the accepted Agent Run settlement receipt;
- pending Tool Calls, pending effects, and unknown acknowledgement state;
- the model dispatch and accepted provider-terminal identity; and
- an atomic compare-and-append control-record operation.

Workspace MUST verify those references. Workspace MUST NOT infer settlement
from a final `AssistantMessage`, a provider stop event, an empty tool queue, or
the absence of an observed error.

### 4.3 Workspace-owned seam

Workspace owns and supplies:

- exact Original User Task and admitted Task Context bindings;
- Case and current Orientation binding;
- optional Projection-overlay binding;
- capability, actor, purpose, authorization, disclosure, and policy snapshots;
- the actor-visible citation catalog;
- candidate decoding and validation;
- publication policy and output authority label; and
- the publication decision receipt.

Workspace MUST NOT use a publication decision as evidence that a CTI claim is
true. The decision proves only that the output was eligible to be shown under
this contract and the recorded basis.

## 5. Public confidentiality gate

Raw Harness/provider deltas are private transaction-local input to the
candidate adapter. Before the publication receipt linearization point, the
public Workspace Turn Interface:

- MUST NOT expose `model_text_delta` or an equivalent content event;
- MUST NOT expose a raw or partially decoded `AssistantMessage`;
- MUST NOT expose candidate blocks, citation refs, excerpts, or digests that
  permit content recovery;
- MUST NOT expose provider error bodies, thinking, or Tool content; and
- MAY expose only content-free phase events such as `model_started`.

Buffering followed by later retraction does not satisfy this rule. Redacting a
delta after delivery does not satisfy this rule. A UI preview is an ordinary
caller for v1 and is subject to the same rule.

## 6. Canonical identities and serialization

### 6.1 Required identity tuple

Every candidate, basis, decision, receipt, and published output is bound,
directly or through its authenticated decision reference, to:

```ts
interface WorkspacePublicationIdentityV1 {
  workspaceId: string;
  turnId: string;
  runId: string;
  attemptId: string;
  runGeneration: number;
}
```

Trusted Workspace/Pi identifiers and opaque refs are 1-128 UTF-16 code units
and match `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`. Model-local `claimId` values
are 1-64 ASCII characters and match `^[a-z][a-z0-9_-]{0,63}$`. Workspace-minted
`citationRef` values are 1-128 ASCII characters and match
`^cite:[A-Za-z0-9][A-Za-z0-9._:-]{0,122}$`. Digest fields use only the shared
Pi digest grammar. HMAC `keyId` follows the trusted-ID grammar and
`macBase64Url` is exactly 43 unpadded base64url characters.

`runGeneration`, every generation/revision/ordinal/position/control sequence,
and every byte/count field is an integer from `0` through
`Number.MAX_SAFE_INTEGER`, subject to its smaller bound. Identity members MUST
match exactly across all records. Identity reuse with a different digest is a
publication conflict. Free-text fields never accept a trusted opaque ref merely
because their bytes match its grammar.

### 6.2 Shared Pi canonical JSON and digest

This contract introduces no canonicalizer or digest implementation. It reuses
`PiCanonicalJsonV1`, `PiDigestV1`, `PiSessionSlotV1<T>`, and `piDigest` exactly
as defined by PNW section 6.5.1/6.7. Every field ending in `Digest` is a
`PiDigestV1` and must match `^sha256:[0-9a-f]{64}$`.

`piDigest(basis)` is exactly `"sha256:" + lowercaseHex(SHA-256(UTF8(
RFC8785_JCS(basis))))`. Pi owns that operation and its canonical size/depth
validation. Workspace never hashes descriptive prose, an alternate serializer,
a digest string standing in for a retained basis, or caller/model-supplied
canonical bytes.

Publication protocol bases contain only `PiCanonicalJsonV1`. Named optional
values use the exact tagged `PiSessionSlotV1<T>` presence union; property
omission, `undefined`, and ad hoc `null` do not represent absence. Unknown
members, accessors, functions, symbols, cycles, sparse arrays, unsupported
prototypes, non-finite numbers, and negative zero fail closed.

Publication adds these lower closed limits before calling shared `piDigest`:
canonical depth at most 12, at most 2,048 aggregate object members, at most
4,096 aggregate array items, and at most 1,048,576 UTF-8 bytes per basis. The
smaller type-specific limits in this contract apply first. Published claim
order and per-claim citation order are semantic. Citation-catalog entries are
sorted by `citationRef` before hashing.

The core mappings are exact: `candidateDigest = piDigest(candidate)`;
`catalogDigest = piDigest(the complete catalog with catalogDigest omitted)`;
`observationDigest = piDigest(the complete Orientation publication observation
with observationDigest omitted)`; `outputDigest = piDigest(output)`;
`decisionDigest = piDigest(decision)`; and `permitDigest = piDigest(the complete
disclosure permit with permitDigest omitted)`. No digest basis includes its own
digest member.

### 6.3 Stable time rule

Wall-clock timestamps are metadata only. Ordering is proved by Session/control
sequence and committed receipt references. A clock value MUST NOT make an
otherwise stale or unauthorized basis current.

## 7. ModelResponseCandidate v1

### 7.1 Candidate schema

`ModelResponseCandidateV1` is internal and never directly caller-visible:

```ts
interface ModelResponseCandidateV1 {
  protocol: "workspace-model-response-candidate/v1";
  candidateId: string;
  identity: WorkspacePublicationIdentityV1;
  finalAssistantEntry: {
    entryId: string;
    entryDigest: string;
    contentDigest: string;
  };
  outcome:
    | "completed"
    | "insufficient_evidence"
    | "budget_exhausted"
    | "blocked";
  claims: CandidateClaimV1[];
}

interface CandidateClaimV1 {
  claimId: string;
  goalRef: string;
  text: string;
  citationRefs: string[];
}

interface ModelProposedWorkspaceResponseV1 {
  protocol: "workspace-model-proposed-response/v1";
  outcome: ModelResponseCandidateV1["outcome"];
  claims: CandidateClaimV1[];
}
```

The candidate digest is the digest of the entire canonical candidate record.
It is computed by the Workspace adapter and is not model-authored.

The model authors only `ModelProposedWorkspaceResponseV1`. Workspace assigns
`candidateId`, binds the trusted identity and final assistant entry, and then
constructs `ModelResponseCandidateV1`. The model MUST NOT be asked to assert a
Session, run, generation, entry ID, or digest.

### 7.2 Candidate content rule

All model-authored caller-visible text MUST occur in `claims[].text`. Each claim
MUST have at least one citation reference. There is no free-form preamble,
summary, caveat, footnote, or model-authored limitation field in v1. Outcome
notices and limitations are rendered by Workspace from closed codes after a
successful decision.

This shape makes uncited model output structurally unpublishable. A model cannot
move an unsupported assertion into a nominal metadata field.

For `completed`, `claims` contains at least one claim. For
`insufficient_evidence`, `budget_exhausted`, and `blocked`, `claims` MUST be
empty. Those outcomes publish only a Workspace-authored closed notice; partial
model claims MUST NOT be published with them.

Each completed claim binds exactly one admitted `goalRef`. Every admitted goal
whose final settlement status is addressed MUST have at least one claim, and a
claim cannot name an unadmitted, superseded, or non-addressed goal. A completed
aggregate requires every admitted goal to be addressed. For a non-completion
aggregate, every per-goal final assessment has the exact same status as the
aggregate, every response-segment list is empty, and the publication candidate
has zero claims. It publishes only the matching Workspace notice. A mixed or
partially addressed non-completion Run is invalid rather than partially
published.

### 7.3 Candidate adapter

The private Workspace adapter over Pi's final `AssistantMessage`:

1. buffers raw text deltas without public delivery;
2. waits for the one accepted provider terminal;
3. reads the exact final assistant entry selected by the final save point;
4. accepts exactly one complete `workspace-model-proposed-response/v1`
   envelope;
5. rejects any text outside the envelope;
6. rejects thinking, reasoning, Tool Call, Tool result, image, audio, provider
   diagnostic, or unknown content blocks;
7. canonicalizes and bounds the candidate; and
8. returns either one immutable candidate or a closed candidate failure.

The adapter MUST NOT repair malformed JSON, guess a missing citation, merge two
envelopes, truncate an oversized candidate, or use another model call.

Provider refusal is not a candidate outcome. A refusal is withheld as
`candidate_refused` unless a separately settled `blocked` run produced the
exact empty-claims blocked envelope required above.

### 7.4 Candidate bounds

The following limits are closed:

| Item | Limit |
| --- | ---: |
| Raw final assistant content inspected | 262,144 UTF-8 bytes |
| Canonical candidate | 131,072 UTF-8 bytes |
| Candidate claims | 64 |
| Claim text | 8,192 UTF-8 bytes |
| Total claim text | 65,536 UTF-8 bytes |
| Citation refs per claim | 16 |
| Total citation-ref occurrences | 512 |
| `candidateId` and entry IDs | 128 ASCII characters each |
| `claimId` | 64 ASCII characters |
| `goalRef` | 128 ASCII characters |
| citation refs | 128 ASCII characters |

Claim text MUST be non-empty after rejecting ASCII control characters other
than line feed and tab. NUL, unpaired surrogates, bidi override/isolate control
characters, and noncharacters are invalid. Duplicate `claimId` values and a
duplicate citation ref within one claim are invalid. Exceeding a bound rejects
the whole candidate; no prefix is eligible.

## 8. Trusted publication basis v1

### 8.1 Basis schema

```ts
interface TrustedWorkspacePublicationBasisV1 {
  protocol: "workspace-publication-basis/v1";
  identity: WorkspacePublicationIdentityV1;
  originalUserTask: BoundRecordRefV1;
  admittedTaskContext: BoundRecordRefV1;
  run: SettledAgentRunProofV1;
  session: SessionPublicationBindingV1;
  context: ContextGenerationBindingV1;
  capabilities: BoundRecordRefV1;
  workingSet: { state: "absent" } | BoundRecordRefV1;
  caseContext: BoundRecordRefV1;
  runOrientation: OrientationPublicationBindingV1;
  publicationOrientation: OrientationPublicationObservationV1;
  projection: { state: "absent" } | ProjectionPublicationBindingV1;
  authorization: AuthorizationPublicationBindingV1;
  secretInspection: WorkspaceSecretInspectionBindingV1;
  citationCatalog: WorkspaceCitationCatalogV1;
  policy: PublicationPolicyBindingV1;
  basisDigest: PiDigestV1;
}

interface BoundRecordRefV1 {
  state: "present";
  recordProtocol:
    | "workspace-original-user-task/v1"
    | "workspace-admitted-task-context/v1"
    | "workspace-capability-snapshot/v1"
    | "workspace-working-set-snapshot/v1"
    | "workspace-layered-case-context/v1";
  recordId: string;
  recordDigest: string;
  revision: number;
}
```

Every `revision` is a non-negative safe integer. A bound record is exact, not
“latest enough.” `basisDigest = piDigest(the complete basis with basisDigest
omitted)`.

`originalUserTask`, `admittedTaskContext`, `capabilities`, a present
`workingSet`, and `caseContext` require respectively the five protocol values
in the order listed by `BoundRecordRefV1`; cross-slot protocol substitution is
invalid.

### 8.2 Agent Run settlement proof

```ts
interface SettledAgentRunProofV1 {
  protocol: "workspace-agent-run-publication-settlement-proof/v1";
  runId: string;
  attemptId: string;
  runGeneration: number;
  finalSavePoint: {
    state: "committed";
    controlSequence: number;
    savePointEntryId: string;
    savePointDigest: string;
    finalAssistantEntryId: string;
    finalAssistantEntryDigest: string;
  };
  piSettlement: PiAgentRunSettlementEvidenceV1;
  workspaceTerminal: WorkspaceAgentRunSettlementTerminalV1;
  pendingToolCalls: 0;
  pendingEffects: 0;
  unknownAcknowledgements: 0;
  proofDigest: PiDigestV1;
}
```

`piSettlement` is the exact PNW-owned `PiAgentRunSettlementEvidenceV1` from PNW
section 5.1; Publication does not redeclare or translate that protocol. Its
`runId`, `runGeneration`, `finalSavePointEntryId`, and
`finalSavePointEntryDigest` MUST equal this proof and the Run-owned terminal.
Its Session ID MUST equal the publication Session binding, and its terminal
MUST be `completed`. The candidate's final assistant entry ID and digest MUST
match the save point.
The Workspace Run disposition MUST equal the candidate outcome, and its exact
response-candidate ref/digest MUST match the candidate. Its ordered final-goal
assessment digests, goal-status digest, final ledger digest, accepted provider
terminal ref/digest, final save point, control state, and complete pending-action
set MUST be members of the exact Run-owned, Workspace-signed terminal payload.
`workspaceTerminal` is that exact `WorkspaceAgentRunSettlementTerminalV1`, not
a publication-owned copy or translation. It is the physically last terminal
entry of the one Pi settlement group. The following equality chain is exact:

- `piSettlement.applicationTerminal.entryId` equals
  `workspaceTerminal.terminalEntryId`,
  `workspaceTerminal.resultingSessionLeafId`,
  `piSettlement.batchEvidence.terminalEntryId`, and the last physical
  `orderedEntryIds` item;
- `piSettlement.applicationTerminal.entryDigest` equals
  `piDigest({ protocol: "pi-session-entry-digest-basis/v1", entry: <the
  complete materialized Pi custom entry containing the exact
  workspaceTerminal> })`, and equals the last physical
  `batchEvidence.orderedEntryDigests` item;
- `piSettlement.applicationTerminal.receiptDigest` equals
  `workspaceTerminal.receiptDigest`; and
- `piSettlement.batchEvidence.sessionId` equals `piSettlement.sessionId`, its
  `expectedLeafId` equals `workspaceTerminal.expectedSessionLeafId`, and its
  IDs, digests, terminal ID, physical order, and `batchDigest` verify under the
  accepted PNW-A4 evidence rules.

The application-terminal `customType` MUST be the exact Run-owned custom-entry
discriminator for `WorkspaceAgentRunSettlementTerminalV1`. Any different
custom type, entry body, base entry field, order, digest, receipt, expected
leaf, or batch evidence is `run_terminal_mismatch`; there is no second
Workspace settlement group. The Pi settlement is always one of PNW's four
terminal kinds; publication accepts only Pi
`completed`. `insufficient_evidence`, `budget_exhausted`, and `blocked` are
Workspace Run dispositions bound inside that successful Pi settlement, not new
Pi terminal variants. The accepted provider terminal MUST be unique for the run
attempt and must be the terminal from which the final assistant entry was
saved.

`workspace-agent-run-settlement-terminal/v1` is the single Run-owned terminal
protocol. Publication defines no local terminal schema and MUST NOT accept or
translate an alternate `workspace-investigation-run-terminal/v1` record. PNW
section 5.1 supplies the sole generic materialization-evidence target. Pi does
not sign, authenticate, parse, or reproduce the application terminal;
Publication independently verifies the Run-owned terminal authenticity and all
PNW evidence equalities above. Calling the Pi evidence signed or authenticated
is forbidden. Until PNW section 5.1 is independently accepted and implemented,
no
implementation may synthesize this proof from a Harness completion, an
unsigned record pair, a payload digest without its entry, or current Session
messages.

`piSettlement.evidenceDigest` MUST recompute exactly as PNW section 5.1:
`piDigest({ domain: "pi.agent-run-settlement-evidence/v1", evidence: <the
complete PiAgentRunSettlementEvidenceV1 with evidenceDigest omitted> })`.
`proofDigest = piDigest({ domain:
"workspace.agent-run-publication-settlement-proof/v1", proof: <the complete
SettledAgentRunProofV1 with proofDigest omitted> })`. No nested digest field
other than the named outer `proofDigest` is omitted from that proof basis.

Pi `cancelled`, `failed`, or `discarded`; Workspace
`clarification_required`; an unknown/unrecognized disposition; or an
uncommitted settlement is not publishable.
Clarification before a run is a Task Understanding result and never enters this
Module.

Zero pending counts are affirmative settlement facts, not values inferred by
Workspace from an empty local collection.

For `completed`, every admitted goal is addressed and every claim's `goalRef`
resolves to its exact final assessment. For each of the three non-completion
dispositions, every goal has that same non-completion status, every response-
segment list is empty, and `responseCandidateDigest` binds an empty-claims
aggregate candidate. Mixed addressed/non-addressed or mixed non-completion
statuses are invalid. Publication emits only the matching closed notice; no
subset is partially published in v1.

### 8.3 Session binding

```ts
interface SessionPublicationBindingV1 {
  sessionId: string;
  branchId: string;
  expectedPrePublicationHeadId: string;
  expectedPrePublicationHeadDigest: string;
  expectedPrePublicationSequence: number;
  sessionGeneration: number;
}
```

The publication decision receipt MUST be appended with compare-and-append
against this exact head, generation, and sequence. A different head, branch,
generation, or Session is `session_binding_changed`; Workspace MUST NOT retry
against a newer head using the old basis.

The saved assistant candidate remains permanently protected and ineligible for
later model context. A save point, run settlement, or publication receipt MUST
NOT make raw candidate text model-eligible; the receipt may qualify only the
separate durable output entry defined in section 13.

### 8.4 Context generation binding

```ts
interface ContextGenerationBindingV1 {
  taskContextGeneration: number;
  sessionContextGeneration: number;
  caseContextGeneration: number;
  orientationGeneration: number;
  projectionGeneration: PiSessionSlotV1<number>;
  workingSetGeneration: PiSessionSlotV1<number>;
  systemInstructionDigest: string;
  modelContextDigest: string;
  contextSnapshotReceiptRef: string;
  contextSnapshotReceiptDigest: string;
  contextProjectionDigest: string;
}
```

Every generation and digest MUST equal the generation used by the accepted run
and the current authorized generation at decision time. The tagged absent slot
is required for an absent optional source. A changed generation rejects publication; Workspace
MUST NOT silently rebuild only part of the basis after the run.

### 8.5 Capability and Working Set binding

The capability record states exactly which model, tools, data sources,
projections, and publication policy were admitted for the run. Publication
MUST revalidate its digest and revision.

The first no-tool slice requires `workingSet.state === "absent"`. A present
Working Set is reserved until its own contract is accepted and implemented.
Workspace MUST NOT encode an ad hoc empty Working Set as a present trusted
record.

### 8.6 Orientation baseline

```ts
interface OrientationPublicationBindingV1 {
  protocol: "workspace-orientation-publication-binding/v1";
  caseRef: string;
  orientationRecord: {
    recordRef: string;
    record: OpenCtiCaseOrientationV1;
    recordDigest: PiDigestV1;
    materializedDigest: PiDigestV1;
  };
  orientationBinding: {
    bindingRef: string;
    binding: OrientationBindingV1;
    bindingDigest: PiDigestV1;
    orientationGeneration: number;
    generationControlEntryDigest: PiDigestV1;
    dependencyDigest: PiDigestV1;
  };
  blocks: {
    orderedBlockBindings: OrientationPublicationBlockBindingV1[];
    orderedBlockBindingsDigest: PiDigestV1;
  };
  sourceObservationReceipt: {
    protocol: "workspace-orientation-source-observation-receipt/v1";
    receiptRef: string;
    receiptDigest: PiDigestV1;
    comparisonDigest: PiDigestV1;
  };
  authorizationReceipt: {
    protocol: "workspace-orientation-authorization-receipt/v1";
    receiptRef: string;
    receiptDigest: PiDigestV1;
    authorizationDigest: PiDigestV1;
    visibilityDigest: PiDigestV1;
  };
  state: "current_complete_authorized";
  bindingDigest: PiDigestV1;
}

interface OrientationPublicationBlockBindingV1 {
  ordinal: 0 | 1 | 2;
  blockKey: "case_identity" | "visible_work" | "visible_object_membership";
  blockDigest: PiDigestV1;
  presence: "populated" | "empty" | "unavailable";
  sourceRef: string;
  sourceDigest: PiDigestV1;
  authorizationReceiptDigest: PiDigestV1;
}

interface OrientationPublicationObservationV1 {
  protocol: "workspace-orientation-publication-observation/v1";
  observationRef: string;
  observationDigest: string;
  observedFor: WorkspacePublicationIdentityV1;
  actorRef: string;
  purposeRef: string;
  binding: OrientationPublicationBindingV1;
  authorizationGeneration: number;
  visibilityGeneration: number;
  state: "current_complete_authorized";
}
```

`OrientationPublicationBindingV1` is a Workspace-derived proof protocol; it is
deliberately not named `opencti-case-orientation/v1`. That latter protocol is
reserved for the actual owning Orientation record. The derived proof is valid
only when the record ref/protocol/digest, complete `OrientationBindingV1`
digest, generation control entry, ordered selected block bindings, double-
observation receipt, and actor-scoped authorization receipt all verify against
their owning records. It cannot be reconstructed from only a semantic digest.

Orientation is mandatory for this v1 Workspace publication. Its Case,
semantic, materialized, dependency, authorization, and visibility bindings
MUST match the exact run basis and the current actor-visible state. Missing,
partial, stale, unknown, retired, invalidated, or unauthorized Orientation
rejects the whole candidate.

`runOrientation` is the exact Orientation used by the Agent Run.
`publicationOrientation` is a fresh, independent Workspace observation made
after Pi settlement and before decision-batch preparation through the owning
Orientation Adapter. It is not copied from the Run basis or inferred from a
cached context. Its complete binding MUST equal `runOrientation`, and its
actor/purpose/generation MUST equal the current publication authorization
basis. The observation performs no Case write and is deterministic-fake only in
the first accepted slice; live OpenCTI remains separately gated. The fake must
still emit all record, binding, generation, block, source-observation, and
authorization-receipt facts above and pass the same verifier.

The current Orientation contract exposes the owning record and binding but not
the two signed receipt protocols named above. Adding those exact Adapter-owned
receipts and their verification is an independent Orientation/publication-seam
amendment gate; publication cannot replace them with a cached body, local
timestamp, or public digest. The deterministic fake proves the protocol shape
only and does not authorize live OpenCTI publication.

### 8.7 Optional Projection overlay

```ts
interface ProjectionPublicationBindingV1 {
  state: "present";
  profileId: string;
  profileRevision: number;
  projectionId: string;
  projectionDigest: string;
  projectionGeneration: number;
  sourceOrientationSemanticDigest: string;
  sourceDependencyDigest: string;
  authorizationDigest: string;
  visibilityDigest: string;
  completeness: "complete";
}
```

A Projection is an optional overlay, never a replacement for Orientation. If
present, it MUST be admitted by the capability snapshot and match the same
Orientation semantic and dependency digests, actor authorization, visibility,
profile revision, and context generation. If absent, candidate citations MUST
not name Projection entries. A mismatched, partial, stale, unknown, or
unauthorized overlay rejects publication; it is not silently dropped after a
run that used it.

The type above is a design target only. A present Projection publication basis
is NO-GO until the Projection overlay contract and its publication Adapter pass
independent acceptance. The first no-tool implementation requires
`projection.state === "absent"`, `projectionGeneration` absent, and no
Projection catalog entry. Implementations MUST NOT populate the present
variant from current Orientation dependencies or ad hoc derived text.

### 8.8 Authorization and policy binding

```ts
interface AuthorizationPublicationBindingV1 {
  actorRef: string;
  purposeRef: string;
  credentialRef: string;
  authorizationRevision: number;
  visibilityRevision: number;
  disclosurePolicyDigest: string;
  markingPolicyDigest: string;
  state: "current_authorized";
  authorizationBindingDigest: string;
}

interface WorkspaceSecretInspectionBindingV1 {
  protocol: "workspace-output-secret-inspection/v1";
  guardRef: string;
  policyDigest: string;
  inventoryDigest: string;
  inventoryGeneration: number;
  providerDispatchBindingDigest: string;
  protectedOwnerSetDigest: string;
  bindingDigest: PiDigestV1;
}

interface PublicationPolicyBindingV1 {
  candidateSchema: "workspace-model-response-candidate/v1";
  citationPolicy: "workspace-citation-policy/v1";
  secretPolicy: "workspace-output-secret-policy/v1";
  publicationPolicy: "workspace-output-publication/v1";
  validatorDigest: string;
  receiptAuthenticator: WorkspacePublicationReceiptAuthenticatorBindingV1;
  policyBindingDigest: PiDigestV1;
}

interface WorkspacePublicationReceiptAuthenticatorBindingV1 {
  protocol: "workspace-publication-receipt-authenticator-binding/v1";
  authenticatorRef: string;
  authenticatorId: string;
  keyId: string;
  keyGeneration: number;
  algorithm: "hmac-sha256";
  receiptPolicyDigest: PiDigestV1;
  bindingDigest: PiDigestV1;
}
```

Authorization is revalidated immediately before the publication receipt CAS.
The current actor, purpose, credential slot, visibility, disclosure, marking,
and policy revisions MUST match the run and citation catalog. Credential values
are never stored; `credentialRef` is a non-secret stable reference.
`authorizationBindingDigest = piDigest(the complete authorization binding with
authorizationBindingDigest omitted)`.

The complete receipt-authenticator binding is snapshotted before A4 prepare.
Workspace re-resolves it and requires byte-for-byte equality immediately
before terminal signing, immediately before `sealTerminal`, and immediately
before `commit`. Authenticator ref/ID, key ID/generation, algorithm, policy,
or binding drift abandons the prepared batch and publishes none. No caller-
supplied key ID or verifier chosen only after commit may substitute for this
basis.

## 9. Citation catalog v1

### 9.1 Catalog schema

```ts
interface WorkspaceCitationCatalogV1 {
  protocol: "workspace-citation-catalog/v1";
  catalogId: string;
  catalogDigest: string;
  actorRef: string;
  purposeRef: string;
  contextSnapshotReceiptRef: string;
  contextSnapshotReceiptDigest: string;
  contextProjectionDigest: string;
  contextGenerationDigest: string;
  contextProjectionProof: PublicationContextProjectionProofV1;
  orientationSemanticDigest: string;
  projectionDigest: PiSessionSlotV1<PiDigestV1>;
  completeness: "complete";
  entries: WorkspaceCitationCatalogEntryV1[];
}

type WorkspaceCitationCatalogEntryV1 =
  | OrientationCitationCatalogEntryV1
  | ProjectionCitationCatalogEntryV1;

interface OrientationCitationCatalogEntryV1 {
  kind: "orientation_block";
  citationRef: string;
  blockKey: string;
  blockDigest: string;
  actorVisibleLabel: string;
  contextItemPosition: number;
  contextItemSourceRef: string;
  modelVisibleAlias: string;
  modelVisibleAliasDigest: PiDigestV1;
  renderedContentDigest: string;
  sourceSemanticDigest: string;
  orientationSemanticDigest: string;
  authorizationDigest: string;
  visibilityDigest: string;
  state: "current_complete_authorized";
}

interface ProjectionCitationCatalogEntryV1 {
  kind: "projection_block";
  citationRef: string;
  blockKey: string;
  blockDigest: string;
  actorVisibleLabel: string;
  contextItemPosition: number;
  contextItemSourceRef: string;
  modelVisibleAlias: string;
  modelVisibleAliasDigest: PiDigestV1;
  renderedContentDigest: string;
  sourceSemanticDigest: string;
  projectionDigest: string;
  sourceCitationRefs: string[];
  authorizationDigest: string;
  visibilityDigest: string;
  state: "current_complete_authorized";
}

interface PublicationContextProjectionProofV1 {
  protocol: "workspace-publication-context-projection-proof/v1";
  contextSnapshotReceipt: ContextSnapshotReceiptV1;
  contextSnapshotReceiptRef: string;
  contextSnapshotReceiptDigest: PiDigestV1;
  contextProjectionDigest: PiDigestV1;
  contextGenerationDigest: PiDigestV1;
  savePointRef: string;
  savePointDigest: PiDigestV1;
  projectionBasis: {
    protocol: "workspace-context-projection-digest-basis/v1";
    purpose: "provider";
    systemPromptDigest: PiDigestV1;
    orderedItems: PublicationContextProjectionItemV1[];
    contextPolicyRevision: string;
  };
  generationBasis: {
    protocol: "workspace-context-generation-vector/v1";
    orderedDependencies: PublicationContextDependencyV1[];
  };
  orderedProjectionItemsDigest: PiDigestV1;
  orderedAliasBindings: PublicationContextAliasBindingV1[];
  orderedAliasBindingsDigest: PiDigestV1;
  proofDigest: PiDigestV1;
}

interface PublicationContextProjectionItemV1 {
  position: number;
  kind:
    | "session_entry"
    | "task_context"
    | "orientation"
    | "working_set"
    | "workspace_control";
  sourceRef: string;
  sourceSemanticDigest: PiDigestV1;
  renderedContentDigest: PiDigestV1;
}

interface PublicationContextDependencyV1 {
  dependencyKey: string;
  contextGeneration: string;
  generationControlEntryDigest: PiDigestV1;
  projectedContentDigest: PiDigestV1;
}

interface PublicationContextAliasBindingV1 {
  position: number;
  sourceRef: string;
  sourceSemanticDigest: PiDigestV1;
  renderedContentDigest: PiDigestV1;
  citationRef: string;
  modelVisibleAlias: string;
  modelVisibleAliasDigest: PiDigestV1;
}
```

`catalogDigest` is computed over the canonical catalog with the
`catalogDigest` member omitted. No protocol digest includes itself.

The catalog is a complete allowlist, not a hint. Candidate refs are opaque and
MUST match one entry exactly. The model cannot mint a source identity by using
a syntactically plausible ref. Every `actorVisibleLabel` and `blockKey` in the
catalog is separately admitted for display to the bound actor; hidden block
keys MUST NOT enter the catalog.

### 9.2 Catalog bounds

| Item | Limit |
| --- | ---: |
| Catalog entries | 1,024 |
| Actor-visible label | 512 UTF-8 bytes |
| Block key | 128 ASCII characters |
| Projection source refs | 32 per entry |
| Canonical catalog | 524,288 UTF-8 bytes |

`citationRef`, `(kind, blockKey)`, and `(kind, blockDigest)` are unique within a
catalog. Every Projection source ref resolves to a current authorized
Orientation entry in the same catalog; each Projection entry has one through
thirty-two unique source refs. Cycles and Projection-to-Projection
derivation are invalid in v1.

`blockKey` follows the trusted opaque-ref grammar. Actor-visible labels contain
valid Unicode scalar values and reject NUL, ASCII controls other than line feed
and tab, bidi override/isolate controls, noncharacters, and unpaired
surrogates.

`contextSnapshotReceipt` is the complete closed, authenticated PNW receipt, not
a Workspace lookalike or a digest-only assertion. Its `receiptId` equals the
proof ref, its `receiptDigest` equals the proof digest field, and its
`contextProjectionDigest` plus recomputed ordered dependencies equal the exact
`projectionBasis` and `generationBasis`. The proof's final save point must
contain that exact receipt as the physically last save-point control record.

Catalog positions are unique valid positions in the exact post-policy model
projection bound by the final save point's authenticated
`ContextSnapshotReceiptV1`. Each entry's position, `contextItemSourceRef`,
rendered-content digest, and source-semantic digest MUST equal that receipt's
`ContextSnapshotProjectionItemV1`. The proof recomputes the ordered projection
digest and Context Generation vector from the receipt, binds the same final
save point, and then binds each opaque `citationRef` to the exact alias bytes
actually rendered to the model. Catalog, proof, receipt, and save-point digests
must all agree. A catalog assembled from a different turn, an earlier context,
a display-only alias/body, or material not actually visible to the model is
invalid.

The accepted PNW `ContextSnapshotReceiptV1` currently proves ordered projection
items but has no citation-alias member. Therefore the alias half of this proof
is an explicit **PNW-C amendment gate**: the owning Context Snapshot protocol
must add a closed ordered alias binding containing position, source ref,
source-semantic digest, rendered-content digest, citation ref, alias bytes, and
alias digest, and its signed receipt payload must cover that list. A Workspace-
derived proof or catalog digest alone cannot fill this gap. Until PNW-C is
independently accepted and implemented, publication implementation is NO-GO,
including the no-tool slice. Display-only aliases and aliases added after the
provider projection never qualify.

### 9.3 Citation resolution

For every candidate claim, Workspace MUST:

1. require one through sixteen unique refs;
2. resolve every ref in the exact catalog bound to the run;
3. verify the entry kind is admitted by the capability snapshot;
4. verify complete/current/authorized state, digests, generations, actor,
   purpose, visibility, disclosure, and markings;
5. for Projection entries, verify every declared Orientation source entry;
6. construct caller-visible citations from catalog entries, never from model
   labels; and
7. reject the entire candidate on any failure.

There is no best-effort citation removal. Missing, malformed, fabricated,
unknown, partial, stale, retired, retracted, or unauthorized citations produce
publish-none.

I&E Capsule, Receipt, and Source Span citations are not members of the closed v1
catalog. They require an accepted I&E publication-seam contract and a new
compatible protocol version. Unknown future citation kinds fail closed.

## 10. Secret and protected-content isolation

Candidate validation is deterministic, local, and deny-by-default. It makes no
model call and no network request.

The publication Module never receives provider, OpenCTI, or other dependency
credentials or a secret inventory. It calls one application-owned protected
`WorkspaceOutputSecretInspectionPort`. The Port composes non-extracting guards
from Pi Provider Dispatch and any admitted Workspace dependency Adapter; each
owner retains its resolved values inside its own protection boundary:

```ts
interface WorkspaceOutputSecretInspectionPort {
  inspect(input: {
    candidateDigest: PiDigestV1;
    candidateCanonicalText: string;
    prospectiveOutputCanonicalText: string;
    binding: WorkspaceSecretInspectionBindingV1;
  }): WorkspaceSecretInspectionOutcomeV1;
}

type WorkspaceSecretInspectionOutcomeV1 =
  | { kind: "safe"; proof: WorkspaceSecretInspectionProofV1 }
  | {
      kind: "unsafe";
      code: "secret_match" | "protected_content";
      outcomeDigest: PiDigestV1;
    }
  | { kind: "unavailable" | "stale" | "unknown" };

interface WorkspaceSecretInspectionProofV1 {
  protocol: "workspace-output-secret-inspection-proof/v1";
  candidateDigest: PiDigestV1;
  prospectiveOutputDigest: PiDigestV1;
  guardRef: string;
  policyDigest: PiDigestV1;
  inventoryDigest: PiDigestV1;
  inventoryGeneration: number;
  protectedOwnerSetDigest: PiDigestV1;
  providerDispatchBindingDigest: PiDigestV1;
  authorizationGeneration: number;
  result: "safe";
  proofDigest: PiDigestV1;
}
```

The Port returns no matching value, offset, credential identity, or diagnostic
body. A safe result is a closed proof of the exact candidate and prospective
output under the complete guard/policy/inventory/owner/provider-dispatch and
authorization generations; Workspace binds its `proofDigest` into the decision
and terminal receipt. An unsafe outcome digest proves only the closed unsafe
classification and is never a safe proof.
`unavailable`, `stale`, or `unknown` withholds output. This protected inspection
Port is a separate gated cross-owner seam; until it and every participating
owner Adapter are accepted, production publication is NO-GO and tests may use
only a deterministic non-secret fake.

Workspace MUST reject the entire candidate when any claim text, model-supplied
ID, or decoded envelope contains:

- an exact current or retired secret value from the bound secret inventory;
- an encoded or JSON-escaped representation explicitly listed by that policy;
- credential material, authorization headers, cookies, private keys, access or
  refresh tokens, or provider request/response bodies;
- a protected hidden identifier not present in the actor-visible citation
  catalog;
- thinking, chain-of-thought, hidden reasoning, provider diagnostics, Tool
  arguments/results, or internal policy text; or
- a field not declared by the candidate schema.

Known-secret comparison covers the exact UTF-8 form and the canonical JSON
escaped form. Empty secret values are ignored. Implementations MUST NOT log the
matching value or return it in a failure. The actor-safe failure contains only
`candidate_secret_bearing`.

The protected inventory contains at most 4,096 non-empty values, each at
most 8,192 UTF-8 bytes and at most 1,048,576 UTF-8 bytes in total. Exceeding an
inventory bound fails publication closed as a policy failure; it MUST NOT cause
the scan to skip a suffix of the inventory.

A heuristic content classifier MAY NOT authorize output rejected by the
deterministic policy. v1 defines no semantic redaction or truncation path.

Workspace re-resolves the complete secret-inspection binding immediately
before A4 prepare, before terminal seal, before commit, and at the disclosure
fence. Any change in guard, policy, inventory digest/generation, protected-owner
set, Provider Dispatch binding, or authorization generation makes the safe
proof stale. Before commit it abandons the batch. After commit it denies live
delivery and reopen; v1 does not silently rescan under a new generation and
pretend the already signed receipt covered that proof. A future protocol may
authorize an authenticated superseding inspection record, but this version
requires a new publication decision.

## 11. WorkspacePublicationDecision v1

### 11.1 Closed decision schema

```ts
type WorkspacePublicationDecisionV1 =
  | {
      protocol: "workspace-publication-decision/v1";
      decision: "publish";
      decisionId: string;
      identity: WorkspacePublicationIdentityV1;
      candidateDigest: PiDigestV1;
      basisDigest: PiDigestV1;
      outputId: string;
      publicationRef: string;
      outputDigest: PiDigestV1;
      secretInspectionProofDigest: PiDigestV1;
      policy: PublicationPolicyBindingV1;
    }
  | {
      protocol: "workspace-publication-decision/v1";
      decision: "withhold";
      decisionId: string;
      identity: WorkspacePublicationIdentityV1;
      candidateDigest: PiSessionSlotV1<PiDigestV1>;
      basisDigest: PiSessionSlotV1<PiDigestV1>;
      secretInspectionProofDigest: PiSessionSlotV1<PiDigestV1>;
      reason: WorkspacePublicationWithholdReasonV1;
      policy: PublicationPolicyBindingV1;
    };
```

The decision is immutable. It contains no candidate text, secret, hidden source
identity, provider body, or model reasoning.

### 11.2 Closed withhold vocabulary

```ts
type WorkspacePublicationWithholdReasonV1 =
  | "candidate_incomplete"
  | "candidate_malformed"
  | "candidate_exceeds_bounds"
  | "candidate_unsupported_content"
  | "candidate_refused"
  | "candidate_secret_bearing"
  | "secret_inspection_unavailable"
  | "secret_inspection_stale"
  | "candidate_digest_mismatch"
  | "citation_missing"
  | "citation_malformed"
  | "citation_fabricated"
  | "citation_unknown"
  | "citation_partial"
  | "citation_stale"
  | "citation_unauthorized"
  | "run_unsettled"
  | "run_terminal_mismatch"
  | "run_generation_stale"
  | "save_point_missing"
  | "save_point_mismatch"
  | "provider_terminal_unknown"
  | "pending_operation"
  | "acknowledgement_unknown"
  | "session_binding_changed"
  | "context_generation_changed"
  | "capability_snapshot_changed"
  | "working_set_changed"
  | "orientation_missing"
  | "orientation_partial"
  | "orientation_stale"
  | "orientation_unauthorized"
  | "projection_basis_mismatch"
  | "projection_partial"
  | "projection_stale"
  | "projection_unauthorized"
  | "authorization_or_visibility_changed"
  | "publication_policy_changed"
  | "publication_conflict"
  | "publication_receipt_commit_failed"
  | "publication_internal_failure"
  | "cancelled";
```

Unknown internal failures map to `publication_internal_failure` and fail
closed; they MUST NOT be coerced to publish or mislabeled as a successful
receipt operation.

### 11.3 Decision order

The Module validates in this order:

1. closed input discriminant, failure-phase/presence matrix, shape, and bounds;
2. identity and candidate/save-point digest equality;
3. final save point and committed settlement;
4. pending/unknown operation state;
5. Session and all context generations;
6. capability, Working Set, Case, Orientation, and Projection basis;
7. actor, purpose, authorization, visibility, disclosure, and policy revisions;
8. candidate content and protected-field policy;
9. citation catalog and every citation; and
10. prospective output construction, candidate/output secret inspection,
    digesting, and publication receipt CAS.

The order does not create observable partial success. Implementations MAY
short-circuit internally but expose one safe outcome only.

An early `provider_terminal` or `envelope_decode` candidate failure stops after
validating its phase and policy; it returns only an in-memory withhold decision,
has no Session commit control, and constructs no publication receipt. A legal
`candidate_binding` failure additionally validates its exact save point,
settlement, Session commit control, policy, and authenticator and may construct
one terminal-only withhold receipt. Neither path executes candidate citation or
secret checks or fabricates later-stage basis facts.

## 12. PublishedWorkspaceOutput v1

### 12.1 Public schema

```ts
interface PublishedWorkspaceOutputV1 {
  protocol: "published-workspace-output/v1";
  outputId: string;
  publicationRef: string;
  outcome:
    | "completed"
    | "insufficient_evidence"
    | "budget_exhausted"
    | "blocked";
  claims: PublishedWorkspaceClaimV1[];
  notice: PiSessionSlotV1<PublishedWorkspaceNoticeV1>;
  authority: "non_authoritative_workspace_output";
}

interface PublishedWorkspaceClaimV1 {
  claimId: string;
  text: string;
  citations: PublishedWorkspaceCitationV1[];
}

type PublishedWorkspaceCitationV1 =
  | {
      kind: "orientation_block";
      citationRef: string;
      label: string;
      blockKey: string;
    }
  | {
      kind: "projection_block";
      citationRef: string;
      label: string;
      blockKey: string;
      derivedFrom: string[];
    };

type PublishedWorkspaceNoticeV1 =
  | {
      code: "insufficient_evidence";
      templateId: "workspace.output.insufficient_evidence.en/v1";
      text: "The investigation ended without sufficient evidence to answer the admitted task.";
    }
  | {
      code: "budget_exhausted";
      templateId: "workspace.output.budget_exhausted.en/v1";
      text: "The investigation stopped because its admitted budget was exhausted before the task could be answered.";
    }
  | {
      code: "blocked";
      templateId: "workspace.output.blocked.en/v1";
      text: "The investigation stopped because a required admitted capability or dependency was unavailable.";
    };
```

Notice text is Workspace-authored from the closed code and is not copied from
the candidate. `completed` has an absent notice and one through sixty-four
claims. All other outcomes have zero claims and the matching present exact
template. Localization requires a new separately digest-bound template catalog
version; it cannot substitute free model prose.

The `publicationRef` is an opaque actor-safe reference to the committed publish
receipt. The public output omits Session heads, internal digests, credential
refs, hidden source IDs, provider metadata, raw candidate envelope, and policy
internals.

Published citations retain candidate order. `derivedFrom` is the exact ordered
one-through-thirty-two actor-visible Orientation citation-ref list from the
catalog; Workspace does not copy model labels or source bodies into it.

### 12.2 Non-authority

Every output has the literal authority value
`non_authoritative_workspace_output`. No setting, model text, citation count,
provider confidence, or later Artifact conversion may remove that label from
this output version.

A valid publication decision means the response is current, authorized,
settled, structurally cited, and eligible under the recorded basis. It does not
mean that cited evidence entails the claim, that the claim is verified CTI
truth, or that it is a Case Assessment.

### 12.3 Published bounds

The published output retains candidate claim/text/citation limits. Its
canonical form MUST NOT exceed 131,072 UTF-8 bytes. Workspace-generated notice
text MUST NOT exceed 1,024 UTF-8 bytes. Exceeding a published bound withholds the
whole output; no truncated output is permitted.

## 13. Publication receipt and atomic linearization

### 13.1 Receipt

Publication uses the accepted PNW-A4 `PiSessionControlBatch` without extending
its entry union. A publish decision prepares exactly one prior entry and one
terminal entry:

1. `custom` with `customType = "workspace_published_output_v1"` and the exact
   canonical `PublishedWorkspaceOutputV1` as present `data`;
2. the physically last `custom` terminal with
   `customType = "workspace_publication_commit_v1"` and the exact receipt below
   as present `data`.

A persistable `candidate_binding` or evaluated-candidate withhold decision
prepares zero prior entries and the same terminal custom type with a withhold
receipt. Early provider/envelope failures prepare no batch. No other entry,
message, leaf move,
configuration change, or Artifact is in the batch.

```ts
interface WorkspacePublicationCommitReceiptV1 {
  protocol: "workspace-publication-commit-receipt/v1";
  identity: WorkspacePublicationIdentityV1;
  decision: WorkspacePublicationDecisionV1;
  decisionDigest: PiDigestV1;
  publicationRef: PiSessionSlotV1<string>;
  expectedLeafId: string;
  phaseEvidence: WorkspacePublicationPhaseEvidenceV1;
  secretInspectionProofDigest: PiSessionSlotV1<PiDigestV1>;
  receiptAuthenticatorBinding:
    WorkspacePublicationReceiptAuthenticatorBindingV1;
  a4PreviewBinding: WorkspacePublicationA4PreviewBindingV1;
  outputEntry: PiSessionSlotV1<WorkspacePublishedOutputEntryBindingV1>;
  terminalEntryId: string;
  receiptDigest: PiDigestV1;
  authenticity: WorkspacePublicationReceiptAuthenticityV1;
}

interface WorkspacePublicationCandidateBindingFailureEvidenceV1 {
  phase: "candidate_binding_failure";
  failureDigest: PiDigestV1;
  candidateEntry: {
    presence: "present";
    entryId: string;
    entryDigest: PiDigestV1;
  };
  finalSavePoint: {
    presence: "present";
    value: WorkspacePublicationSavePointRefV1;
  };
  piSettlement: {
    presence: "present";
    value: WorkspacePublicationTerminalRefV1;
  };
  workspaceSettlement: {
    presence: "present";
    value: WorkspacePublicationTerminalRefV1;
  };
}

type WorkspacePublicationPhaseEvidenceV1 =
  | WorkspacePublicationCandidateBindingFailureEvidenceV1
  | {
      phase: "candidate_evaluated";
      basisDigest: PiDigestV1;
      candidateEntry: {
        presence: "present";
        entryId: string;
        entryDigest: PiDigestV1;
      };
      finalSavePoint: { presence: "present"; value: WorkspacePublicationSavePointRefV1 };
      piSettlement: { presence: "present"; value: WorkspacePublicationTerminalRefV1 };
      workspaceSettlement: { presence: "present"; value: WorkspacePublicationTerminalRefV1 };
      contextSnapshotReceipt: WorkspacePublicationTerminalRefV1;
      contextProjectionDigest: PiDigestV1;
      citationCatalog: WorkspacePublicationTerminalRefV1;
      orientationObservation: WorkspacePublicationTerminalRefV1;
      authorizationBindingDigest: PiDigestV1;
    };

interface WorkspacePublicationSavePointRefV1 {
  ref: string;
  digest: PiDigestV1;
}

interface WorkspacePublicationTerminalRefV1 {
  ref: string;
  digest: PiDigestV1;
}

interface WorkspacePublicationA4PreviewBindingV1 {
  protocol: "workspace-publication-a4-preview-binding/v1";
  sessionId: string;
  expectedLeafId: string;
  orderedPriorEntryIds: string[];
  orderedPriorEntryDigests: PiDigestV1[];
  terminalEntryId: string;
  terminalParentId: string;
  terminalTimestamp: string;
  previewDigest: PiDigestV1;
}

interface WorkspacePublishedOutputEntryBindingV1 {
  ordinal: 0;
  entryId: string;
  parentId: string;
  entryDigest: PiDigestV1;
  outputId: string;
  outputDigest: PiDigestV1;
}

interface WorkspacePublicationReceiptAuthenticityV1 {
  protocol: "workspace-publication-receipt-authenticity/v1";
  algorithm: "hmac-sha256";
  authenticatorRef: string;
  authenticatorId: string;
  keyId: string;
  keyGeneration: number;
  authenticatorBindingDigest: PiDigestV1;
  signedPayloadDigest: PiDigestV1;
  macBase64Url: string;
}
```

For publish, `outputEntry` is present and binds A4's exact materialized prior
entry; its ID/digest equal the publish decision and the exact prior-entry data.
For publish, `publicationRef` is present and equals the exact decision and
output value. For a persistable withhold, both `publicationRef` and
`outputEntry` are absent and the batch has no output entry. Early in-memory
withholds have no receipt or batch. The output's `publicationRef` is a
Workspace-minted opaque ref fixed before A4 preparation and bound by the
receipt; it is not an A4 entry ID. `terminalEntryId` is A4's reserved terminal
ID from the immutable preview. Workspace cannot choose any materialized entry
ID, parent, timestamp, generic entry digest, or A4 batch digest.

Because publication follows committed Task Context, save-point, and settlement
groups, `expectedLeafId` equals the exact non-null pre-publication Session
head. For publish, the output entry parent equals that head and the terminal
parents the output entry. For a persistable withhold, the terminal parents that
head. Any
other parent, order, or leaf is `invalid_terminal`/conflict, never an
alternate valid layout.

For `candidate_evaluated`, the context, catalog, Orientation-observation, and
authorization fields equal the trusted basis byte-for-byte and make their
linkage explicit in the durable receipt. The catalog's own context receipt/
projection fields must equal these receipt fields. A matching `basisDigest`
alone never permits substitution of a different unavailable record during
recovery.

Receipt presence is phase-specific and closed:

| Phase | Publication group | Candidate entry | Final save point | Pi settlement | Run terminal | Full basis proof | Safe secret proof |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `provider_terminal` | none; in-memory withhold only | exact input slot | absent | absent | absent | absent | absent |
| `envelope_decode` | none; in-memory withhold only | present | absent | absent | absent | absent | absent |
| `candidate_binding_failure` | one terminal-only publication group | present | present | present completed | present exact Run-owned terminal whose candidate mismatches | absent | absent |
| `candidate_evaluated` | one publication group | present | present | present completed | present Run-owned terminal | present | present iff publish |

The `candidate_binding_failure` row also uses one terminal-only publication
group; its Run terminal is present and is the exact terminal whose candidate
binding failed comparison. Provider-terminal and envelope-decode failures have
no `WorkspacePublicationCommitReceiptV1` at all. Any Pi completed settlement
requires a committed final save point; a purported completed settlement with
an absent save point is an integrity failure, never an early failure receipt.
A withhold decision cannot carry evidence from a later phase. A publish
decision requires `candidate_evaluated`, every full-basis member, and a safe
secret proof. A candidate failure reason/phase mismatch, extra receipt member,
or required-presence mismatch is `publication_internal_failure` and appends
nothing.

`decisionDigest = piDigest(decision)`. `receiptDigest = piDigest(the complete
receipt with receiptDigest and authenticity omitted)`. `signedPayloadDigest =
piDigest(the complete receipt with authenticity omitted)`. `macBase64Url` is
unpadded base64url HMAC-SHA-256 over the exact UTF-8 RFC 8785 JCS bytes of that
same signed-payload basis, not over a digest string. The Workspace receipt
authenticator never exposes its key. Every authenticity member MUST equal the
complete basis-bound authenticator ref/ID, key ID/generation, algorithm, policy,
and binding digest. Recovery verifies the MAC under that exact binding; an
unavailable/retired verifier or one-field drift is untrusted recovery, not
output.

`receiptAuthenticatorBinding` MUST equal
`decision.policy.receiptAuthenticator` byte-for-byte. For publish,
`secretInspectionProofDigest` is present and equals the decision's proof
digest; for every withhold it is absent. The safe proof itself is retained by
the protected verifier/recovery seam under that digest and never exposes its
inventory.

The exact output is mandatory durable data in the prior entry; storing only an
output digest or a pointer to the raw model candidate is invalid. This permits
reopen to reconstruct the exact published output without rerunning the model,
re-decoding the candidate, or consulting an Artifact.

Before sealing, Workspace recomputes `a4PreviewBinding.previewDigest` from A4's
immutable preview: exact Session/leaf, materialized prior-entry IDs and complete
entry digests in physical order, plus reserved terminal ID/parent/timestamp.
For publish it has one prior; for withhold it has zero. The binding is inside
the signed terminal receipt. Workspace rechecks the retained preview,
authenticator binding, secret generation when present, authorization, and
Session head immediately before seal and immediately before commit. Any
preview/seal/commit drift abandons or fails the batch; it is never normalized
into the earlier preview.

Workspace follows A4's closed flow exactly: one `prepareControlBatch`; one
`sealTerminal`; one `commit`. `committed` is success. On
`acknowledgement_unknown`, it performs one authoritative
`lookupControlBatch(evidence)`; only `exact_present` is success. `absent`,
`conflict`, `unsupported`, `invalid_draft`, `invalid_terminal`, and
`unavailable` yield no output and no retry/rematerialization. A4 evidence is
retained for acknowledgement resolution but is not inserted into the
self-referential terminal receipt.

The canonical decision is at most 65,536 UTF-8 bytes, the canonical terminal
receipt is at most 131,072 UTF-8 bytes, and the complete publication batch is at
most 393,216 UTF-8 bytes. A publish batch has exactly two entries and a
persistable withhold batch exactly one. An over-limit value is withheld before A4
preparation; it is never truncated or split across batches.

### 13.2 Linearization point

The single publication linearization point is successful compare-and-append of
the authenticated publish decision receipt against the exact basis Session
head. Before that commit, output is not published. After that commit, the one
bound output identity is durably published. The protected raw assistant
candidate never becomes directly model-eligible; only the exact durable output
entry may later be projected, and only through the receipt-aware gate in
section 13.4.

Public event delivery, promise resolution, console rendering, or transport
flush is not the linearization point.

### 13.3 Atomic publish-or-none

The Module returns:

```ts
type WorkspacePublicationOutcomeV1 =
  | {
      status: "published";
      decision: Extract<WorkspacePublicationDecisionV1, { decision: "publish" }>;
      output: PublishedWorkspaceOutputV1;
    }
  | {
      status: "withheld";
      decision: Extract<WorkspacePublicationDecisionV1, { decision: "withhold" }>;
    };
```

There is no partial published outcome. A receipt conflict, interrupted commit,
unresolved acknowledgement after the one exact lookup, or authenticator
failure returns no output. Unknown acknowledgement is not retried as a fresh
publication; `exact_present` resolves it as the same committed publication and
every other lookup result remains publish-none.

Two different publish receipts for the same identity, candidate, or output are
an integrity conflict and quarantine the affected publication path.

### 13.4 Receipt-aware later-context projection gate

The later-context rule is an independently gated PNW-A2.2 amendment, not a
claim about the current Session projection implementation. Its deny-by-default
rule is:

```text
eligible published history = exact output entry
  + one authenticated matching publish receipt
  + exact settlement/save-point/run/context bindings
  + current actor/purpose/read authorization
```

The projector MUST exclude every raw final assistant candidate, output entry
without its receipt, withhold decision, unsettled candidate, partial batch,
unknown acknowledgement, conflicting receipt, stale generation, and currently
unauthorized output. It renders the exact durable output entry into later
assistant context; it never falls back to candidate text. Compaction and branch
summary inputs apply the same gate and carry the publication ref/output digest.

No implementation may claim publication integrated PASS until this projector
amendment is independently accepted and its Memory/JSONL reopen behavior is
proven at the public Workspace seam.

## 14. Crash, cancellation, and reopen semantics

Runtime acknowledgement resolution and process recovery are different seams:

```ts
interface WorkspacePublicationRecoveryPortV1 {
  recoverPublication(
    identity: WorkspacePublicationIdentityV1,
    session: SessionPublicationBindingV1,
  ): Promise<WorkspacePublicationRecoveryOutcomeV1>;
}

type WorkspacePublicationRecoveryOutcomeV1 =
  | {
      kind: "exact_published";
      output: PublishedWorkspaceOutputV1;
      receipt: WorkspacePublicationCommitReceiptV1;
      recoveryProofDigest: PiDigestV1;
    }
  | {
      kind: "exact_withheld";
      receipt: WorkspacePublicationCommitReceiptV1;
      recoveryProofDigest: PiDigestV1;
    }
  | { kind: "absent" }
  | { kind: "quarantined" | "unavailable" };
```

Inside the same live runtime, `acknowledgement_unknown` retains the complete
opaque `PiSessionControlBatchEvidenceV1` and performs exactly one
`lookupControlBatch(evidence)`. That operation is the only use of A4 lookup.
A digest, terminal ID, or data reloaded after process death is not A4 evidence
and cannot reconstruct this lookup capability.

After process crash/reopen, the separately owned SessionRepository recovery
Port performs an authoritative full-session read under a current fenced lease.
It verifies Session identity and branch, the complete physical group order,
entry IDs/parents/timestamps/digests, terminal-last position, receipt MAC and
full authenticator binding, exact durable output, settlement/save-point/context
links, and current authorization/secret generations. It returns only the
closed outcomes above, never A4 evidence, a reconstructed permit, or raw
candidate content. A partial prefix, conflicting duplicate, later incompatible
leaf, invalid MAC, unavailable authenticator, or malformed repository is
`quarantined`/`unavailable`, never `absent` or exact publication.

This cross-process recovery Port is an explicit PNW SessionRepository/A5
amendment gate. Accepted A4 proves only same-runtime exact lookup with retained
evidence. Until repository recovery, lease fencing, and Memory/JSONL reopen are
independently accepted, crash/reopen publication is NO-GO and cannot be claimed
from A4 tests.

| Observed durable state | Reopen interpretation | Public content |
| --- | --- | --- |
| Partial/private provider stream only | discard private buffer | none |
| Final assistant entry, no final save point | incomplete candidate | none |
| Final save point, no settlement | protected candidate, unsettled | none |
| Settlement, no publication receipt | protected candidate, not published | none |
| Valid withhold receipt | terminal withhold, candidate remains ineligible | none |
| Output entry without its exact terminal receipt | partial publication batch; quarantine | none |
| Unknown acknowledgement in the same live runtime with retained A4 evidence | perform the one A4 exact lookup | none until `exact_present` |
| Process crash after unknown acknowledgement | use only authenticated SessionRepository recovery; never reconstruct A4 evidence | none until `exact_published` |
| One valid committed publish receipt and exact output entry | authenticate both and reconstruct the same immutable output | exact output only after a fresh disclosure permit |
| Invalid, untrusted, or conflicting receipt | quarantine/fail closed | none |

Cancellation before the publish receipt commit produces no public content and
no context eligibility. Cancellation after the commit cannot retract the
already published output; it may only stop delivery work and later replay the
same output identity.

Reopen MUST authenticate the settlement and publication receipts, recheck their
structural linkage, and apply current read authorization before returning
content. Loss of current read authorization hides the output; it does not alter
the historic decision record.

When a crash occurs after receipt commit but before any public terminal, resume
for the same Turn identity may return the same output ID/digest after a fresh
disclosure permit. A Turn that already emitted an authorization failure remains
failed; a later authorized read may expose the durable output through a
separate read seam but cannot rewrite that Turn terminal. A new Turn does not
re-emit an old output as its own terminal result.

## 15. Public Workspace Turn mapping

### 15.1 Non-terminal events

Publication adds no non-terminal event to the PNW Workspace event union.
Existing identity, sequence, and content-free lifecycle events retain PNW
semantics. No public event named `model_text_delta`, `candidate_delta`,
`citation_delta`, `run_settled`, or equivalent is permitted by this contract.

### 15.2 Terminal events and results

The required public amendment preserves PNW's five terminal variants and keeps
the completed event content-free. It replaces only the completed result's raw
`AssistantMessage` with the validated output:

```ts
type WorkspacePublishedCompletionEventV1 = { type: "turn_completed" };

type WorkspacePublishedCompletionResultV1 = {
  operationId: string;
  turnId: string;
  status: "completed";
  output: PublishedWorkspaceOutputV1;
};
```

Clarification-required, cancelled, failed, and discarded retain their exact PNW
terminal event/result shapes. The completed event observes terminality; the
result is the one content-bearing observation of the committed publication.

`turn_completed` is impossible before a committed publish receipt. A withheld
candidate maps to a non-content terminal. No failure terminal includes the
candidate, a citation excerpt, a provider body, or a secret.

This completed-result replacement and the publication failure codes below are
an independent PNW/public-Workspace protocol amendment. The current
`AssistantMessage` completed result and delivered raw-delta behavior do not
satisfy this contract and MUST NOT be reported as focused publication PASS.

### 15.3 Actor-safe failure mapping

Public failures use a smaller closed vocabulary:

```ts
type ActorSafePublicationFailureV1 = {
  code:
    | "output_not_publishable"
    | "workspace_state_changed"
    | "authorization_or_visibility_changed"
    | "publication_failed";
  templateId:
    | "workspace.output.not_publishable.en/v1"
    | "workspace.output.state_changed.en/v1"
    | "workspace.output.authorization_changed.en/v1"
    | "workspace.output.publication_failed.en/v1";
  message: string;
  retryable: false;
};
```

The code/template/message triples are exact:

| Code | Template | Message |
| --- | --- | --- |
| `output_not_publishable` | `workspace.output.not_publishable.en/v1` | `The investigation output could not be published.` |
| `workspace_state_changed` | `workspace.output.state_changed.en/v1` | `The workspace changed before the investigation output could be published.` |
| `authorization_or_visibility_changed` | `workspace.output.authorization_changed.en/v1` | `The investigation output is not available under the current authorization.` |
| `publication_failed` | `workspace.output.publication_failed.en/v1` | `The investigation output could not be committed safely.` |

Candidate, citation, and confirmed secret-content failures map to
`output_not_publishable`; unavailable/unknown secret inspection maps to
`publication_failed`.
Session/context/capability/working-set/policy drift maps to
`workspace_state_changed`. Authorization, visibility, Orientation
authorization, and Projection authorization failures map to
`authorization_or_visibility_changed`. Receipt/authenticator/integrity failures
map to `publication_failed`. Cancellation and explicit discard retain their
exact PNW terminal kinds and `TurnDiscardReason` vocabulary; this contract does
not invent replacement discard strings.

Messages are fixed actor-safe text selected by code. They MUST NOT interpolate
model text, citation refs, hidden IDs, provider data, or secret-policy matches.

### 15.4 Commit-to-delivery authorization fence

Receipt commit proves durable publication eligibility but does not itself
authorize disclosure forever. Immediately before resolving a completed result
or reconstructing output on reopen, the coordinator acquires one single-use
`WorkspacePublicationDisclosurePermitV1` from the owning actor/visibility
invalidation fence. The permit binds actor, purpose, publication receipt,
output digest, authorization generation, and visibility generation.

```ts
interface WorkspacePublicationDisclosurePermitV1 {
  protocol: "workspace-publication-disclosure-permit/v1";
  permitId: string;
  actorRef: string;
  purposeRef: string;
  publicationRef: string;
  receiptDigest: PiDigestV1;
  outputId: string;
  outputDigest: PiDigestV1;
  authorizationGeneration: number;
  visibilityGeneration: number;
  secretInventoryGeneration: number;
  secretInspectionProofDigest: PiDigestV1;
  receiptAuthenticatorBindingDigest: PiDigestV1;
  permitDigest: PiDigestV1;
  use: "single_delivery";
}
```

The permit's secret generation/proof and receipt-authenticator binding MUST
still equal the signed publication receipt. A stale secret proof, inventory
generation drift, or authenticator drift denies delivery even when actor and
visibility generations are unchanged.

The content-free `turn_completed` event and completed result are enqueued/
resolved as one terminal action while that fence is held. An authorization/visibility invalidation serializes either before the
permit, causing the exact authorization failure with no output, or after the
content has been enqueued while valid. Unknown or unavailable fence state is a
denial. A check performed before receipt commit, a cached boolean, or a check
followed by an unbounded asynchronous gap is insufficient.

If authorization changes after commit but before delivery, the durable receipt
remains historical, the live Turn emits one failed terminal and returns no
content. Any later read/reopen path must acquire a fresh permit and never treats
the old live check as authority. This disclosure-permit seam is independently
gated; until accepted, production content delivery is NO-GO.

## 16. First Pi-native no-tool vertical slice

The first implementation accepted against this contract is deliberately small:

1. one Original User Task and one admitted Task Context;
2. one atomic Task Context commit;
3. one seven-section initial model context;
4. one long-lived Pi Session and Harness;
5. one formal Investigation Agent Run with no Tool Calls;
6. one final save point and one committed Agent Run settlement;
7. `pendingToolCalls`, `pendingEffects`, and `unknownAcknowledgements` all
   settled to zero by Pi;
8. current Orientation as the mandatory publication basis;
9. Projection explicitly absent; the present variant remains a separately
   gated later slice;
10. Working Set explicitly absent;
11. citations only to closed actor-visible Orientation entries;
12. private buffering of all provider deltas;
13. one atomic publication receipt before caller-visible content;
14. one disclosure permit after receipt commit and before caller delivery;
15. one non-authoritative Published Workspace Output or none; and
16. no Artifact creation.

The slice MUST use the single existing long-lived Agent/Harness. Candidate
validation MUST NOT create a Harness, Session, Tool loop, model call, second
Agent, or recursive planner.

## 17. Acceptance catalog

Acceptance uses public behavior and durable control evidence, not test names or
private reducer state.

### 17.1 Confidentiality and terminality

- **WOP-01:** During provider streaming, ordinary callers observe no
  content-bearing delta.
- **WOP-02:** Cancellation after one or more private deltas exposes no candidate
  content, commits no publish receipt, and makes no candidate entry
  model-eligible.
- **WOP-03:** Provider failure, refusal, malformed output, invalidation,
  supersession, close, and Session CAS conflict each expose no candidate content
  and settle exactly one non-content terminal.
- **WOP-04:** One successful Turn keeps `turn_completed` content-free and
  exposes content only in its matching completed result, after the publish
  receipt commit and disclosure permit.

### 17.2 Settlement and basis

- **WOP-05:** Missing/uncommitted/mismatched final save point publishes none.
- **WOP-06:** Missing/uncommitted/mismatched Agent Run settlement publishes
  none.
- **WOP-07:** Pending Tool Call/effect or unknown acknowledgement publishes
  none.
- **WOP-08:** Stale run generation, Session head, branch, Session generation, or
  context generation publishes none.
- **WOP-09:** Changed Original Task, admitted Task Context, capability, Working
  Set, Case Context, system instruction, or model-context digest publishes none.
- **WOP-10:** Settlement disposition and candidate outcome mismatch publishes
  none.
- **WOP-10a:** Publication accepts only the one shared
  Run-owned `workspace-agent-run-settlement-terminal/v1` as the physically-last
  entry of the one Pi settlement group; PNW evidence binds its exact entry ID,
  complete entry digest, and receipt digest. One-field drift in decision/
  candidate/goal/ledger/provider-terminal facts publishes none.
- **WOP-10b:** A non-completion Run is eligible only when every goal has the
  same aggregate non-completion status and all response segments/claims are
  empty; mixed statuses publish none. A completed candidate covers every
  admitted goal and each claim binds one addressed goal.

### 17.3 Orientation, Projection, citation, and authorization

- **WOP-11:** Current complete authorized Orientation with exact claim citations
  can publish.
- **WOP-12:** Missing, partial, stale, unknown, invalidated, or unauthorized
  Orientation publishes none.
- **WOP-13:** Projection absent with no Projection citations can publish.
- **WOP-14:** The first no-tool slice rejects a present Projection as gated;
  after its separate acceptance, only an exact admitted overlay with exact
  source binding can publish.
- **WOP-15:** Projection citation while overlay is absent, or a partial/stale/
  unknown/unauthorized/mismatched overlay, publishes none.
- **WOP-16:** Missing, malformed, duplicated, fabricated, unknown, partial,
  stale, or unauthorized citation publishes none for the whole candidate.
- **WOP-17:** Authorization, visibility, purpose, credential slot, disclosure,
  marking, or policy drift before receipt commit publishes none.

### 17.4 Candidate and protected content

- **WOP-18:** A valid `completed` envelope with one or more cited claims can
  publish.
- **WOP-19:** Empty completed claims, extra envelope fields, text outside the
  envelope, multiple envelopes, unsupported blocks, or exceeded bounds publish
  none.
- **WOP-20:** Secret-bearing text, hidden identifiers, thinking, provider
  diagnostics, Tool content, or private source body publishes none and is not
  echoed in events, results, logs, or receipts; safe/unsafe is obtained through
  the protected inspection Port without exposing inventory values.
- **WOP-20a:** A publish receipt contains the complete safe inspection proof
  digest, and guard/policy/inventory generation/owner/provider-dispatch drift at
  prepare, seal, commit, or disclosure denies content.
- **WOP-21:** Insufficient-evidence, budget-exhausted, and blocked Workspace Run
  dispositions bound to a Pi completed settlement publish only the matching
  Workspace-authored notice and never partial model claims.
- **WOP-22:** Every successful output has
  `authority: "non_authoritative_workspace_output"`.

### 17.5 Atomicity, continuity, and recovery

- **WOP-23:** Save point without settlement leaves the candidate protected and
  ineligible after reopen.
- **WOP-24:** Settlement without a publish receipt leaves the candidate
  protected and ineligible after reopen.
- **WOP-25:** Unknown receipt acknowledgement in one live runtime is resolved by
  one exact A4-evidence lookup without recommit/rematerialization; no duplicate
  logical publication occurs.
- **WOP-26:** After process death, only the separately accepted fenced
  SessionRepository recovery Port can reconstruct one authenticated committed
  publish receipt plus its exact durable output entry, without raw candidate,
  Artifact, reconstructed A4 evidence, or reconstructed permit.
- **WOP-27:** Invalid or conflicting receipt quarantines the publication path and
  exposes no content.
- **WOP-28:** A raw assistant candidate is never later-context eligible; only
  the exact durable output entry with its matching receipt is projected, while
  withheld/unsettled/conflicting/unauthorized values remain excluded.
- **WOP-29:** No success or failure path creates an Artifact by default.
- **WOP-30:** The first accepted slice creates no Tool loop, second Agent,
  recursive planner, I&E request, Working Set, Assessment, Case write, or live
  provider activation.
- **WOP-31:** Publication uses shared `piDigest` and the exact closed A4
  one-prior-plus-terminal or terminal-only batch; every unresolved/non-exact A4
  result publishes none.
- **WOP-32:** The citation catalog is bound through the accepted PNW-C signed
  Context Snapshot amendment to the exact projection basis, generation vector,
  model-visible alias bytes/ref/digest, item position/source/digest, and final
  save point; cross-turn or display-only aliases publish none.
- **WOP-33:** A fresh independent Orientation publication observation must
  equal the Run's actual Orientation record, binding, generation-control,
  ordered blocks, source-observation receipt, and authorization receipt; reuse
  of only the cached Run semantic digest publishes none.
- **WOP-34:** Authorization change after receipt commit but before delivery
  produces one safe failed terminal and no content; current authorization under
  a single-use disclosure permit can deliver the exact result.
- **WOP-35:** The PNW public-union amendment preserves all five terminal
  variants, removes raw `AssistantMessage` from completed results, and adds no
  content-bearing progress event.
- **WOP-36:** `provider_terminal` and `envelope_decode` failures have no final
  save point, no Pi settlement, and no publication group; `candidate_binding`
  and `candidate_ready` produce only their legal durable phase-evidence shape.
  Missing or impossible presence appends nothing.
- **WOP-37:** The complete receipt-authenticator binding is equal at basis,
  preview, sign, seal, commit, recovery, and delivery; key generation or policy
  drift publishes/delivers none.
- **WOP-38:** A4 preview proof binds exact prior IDs/digests and reserved
  terminal ID/parent/timestamp; preview/seal/commit drift appends none or is a
  failed commit, never an alternate receipt.

## 18. Acceptance levels

- **Design PASS** requires an independent reviewer to verify this contract is
  closed, owned, compatible with its Pi dependencies, and contains no hidden
  authorization for deferred scope.
- **Focused implementation/public-seam PASS** requires focused tests proving the
  public confidentiality gate, closed schemas, publication receipt ordering,
  one terminal, and the failure matrix at the public Workspace seam.
- **Integrated PASS** additionally requires focused end-to-end evidence for the
  complete no-tool chain from Original User Task through Agent Run settlement
  and validated Published Workspace Output, including crash/reopen windows and
  later-context eligibility.

Focused implementation/public-seam PASS and Integrated PASS are impossible
until the Run terminal and PNW settlement-materialization evidence amendments,
PNW-C alias proof,
Orientation receipts, protected secret-inspection/disclosure seams, and the
applicable SessionRepository recovery gate have each passed their own owner and
independent review. Design PASS for this contract does not imply any of those
passes.

A private helper test, test title, mock call count, or reducer state is not by
itself acceptance evidence.

## 19. Deferred and prohibited scope

The following remain deferred and are not implementation authorization:

- progressive or content-bearing public model streaming;
- privileged diagnostic access to raw model deltas;
- I&E Capsule/Receipt/Source Span citation kinds;
- Intelligence Working Set creation, refresh, or persistence;
- Artifact creation, versioning, or publication;
- Assessment or Case write-back;
- Tool execution and Tool-result citation;
- paid or live provider activation and live OpenCTI execution;
- semantic claim-entailment scoring or a second model validator;
- automatic redaction, partial publication, or best-effort citation removal;
- general task DAGs, recursive planners, or sub-Agent systems; and
- backward compatibility with the pre-contract raw `model_text_delta` public
  behavior.

Any such scope requires its own accepted contract and explicit routing.
