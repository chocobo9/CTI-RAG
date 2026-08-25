# Pi-native Agent Workspace Lifecycle v1

PNW-A5 status: **Design PASS and focused implementation/public-seam PASS for
opaque Session repository leasing; Workspace integration remains NO**.

Exact-input-count status: **Design PASS and focused implementation/public-seam PASS on 2026-07-22 for the generic Pi seam and Workspace Task Understanding consumer; PNW-C integration, real-provider registration, and real-provider activation remain NO**.

Task Result settlement amendment status: **Design Gate FAIL; no implementation
authorization.** The accepted section 5.1 target remains terminal-only and
requires one final Save Point. The target
[`workspace-task-result/v1`](task-result-v1-contract.md) requires a versioned
generic amendment that atomically materializes one application Task Result
entry followed by the physically-last application settlement terminal, and
that supports status-only failed/cancelled/discarded settlement from the
captured Run-admission leaf when no trusted Save Point exists. This does not
change the implemented A4 Interface or inherit any earlier PNW PASS.

Status: **PNW-A4 implemented and independently accepted; the revised dual-frontend PNW-A3.2 plus exact-count seam and its Workspace Task Understanding consumer have Design PASS and focused implementation/public-seam PASS**. Callers bind only `modelRef` and counter/tokenizer/wrapper identity; Pi computes the actual Model/counter binding after A3.1 preparation and returns trusted non-secret evidence without exposing prepared/auth material. Independent Node `v24.14.0` acceptance passed Workspace Task Understanding **42/42**, Workspace related **55/55**, AI exact/related **46/46**, Agent Provider Dispatch/Session related **147/147**, and the root check over **820 files** including TypeScript and browser smoke. This does not constitute PNW-C Integration PASS, Integrated PASS, or real-provider activation. A3.1 and A4 acceptance remain unchanged. PNW-A overall, later PNW integration slices, Pi-native Workspace migration, Workspace I&E consumption, Working Set, and real-provider activation remain NO-GO. The current Workspace still uses the per-Turn transition baseline.

This contract owns the optimization from the delivered Orientation lifecycle to a Pi-native Agent Workspace. The delivered [`opencti-case-orientation/v1`](opencti-case-orientation-v1-contract.md) contract remains the behavioral safety baseline for actor-scoped reads. This contract supersedes its per-`WorkspaceTurn` staging-Harness mechanism, not its disclosure, freshness, terminal, or recovery guarantees.

[Pre-Investigation Task Understanding v1](pre-investigation-task-understanding-v1-contract.md) is the independently accepted replacement design for immutable-task preservation, one bounded model-assisted understanding call, deterministic admission/clarification, and committed handoff before this lifecycle starts an Agent Run. [Investigation Run Control v1](investigation-run-control-v1-contract.md) and [Workspace Output Publication v1](workspace-output-publication-v1-contract.md) are also independently accepted designs. Their implementation and composed lifecycle gates remain NO-GO. The earlier same-Agent-Run [Task Context Understanding v1](task-context-understanding-v1-contract.md) is superseded before implementation.

[`workspace-run-context-preparation/v1`](workspace-run-context-preparation-v1-contract.md)
owns the PNW-C owner-qualified context contribution, Pi channel adaptation and
acceptance matrix. The superseded fixed seven-section serialized candidate is
reference-only. This lifecycle owns ordering and integration into the single
leased Session plus Workspace-lifetime Harness execution spine.

[Intelligence Working Set v1](intelligence-working-set-v1-contract.md) owns the frozen future Workspace-side capability, exact-resource admission, atomic Working Set state, and application-specific disclosure semantics after this lifecycle passes. This lifecycle alone owns the generic Pi Provider Dispatch Transaction and its persisted generic envelope. [ADR 0015](../adr/0015-use-session-authority-and-pre-dispatch-proof-for-workspace-capabilities.md) records the long-lived Session/pre-dispatch decision; its coarse provider-proof wording is interpreted by this more specific current-cycle contract.

The I&E owner retains its Source Capture/Resource Capsule/Retrieval Receipt replay retention. That retention grants no complete-prompt retention. I&E core-package readiness is not this lifecycle's acceptance and cannot bypass PNW-A through PNW-E plus TU-01 through TU-15 for Workspace consumption or real-provider disclosure.

### 0.1 Provider-proof supersession ledger

This current-cycle lifecycle contract is the sole normative authority for the generic Pi Provider Dispatch Transaction, resolved-request canonicalization, secret bindings, application-authority flow, A4 control batch, terminal persisted envelope, permit, protected start, and PNW provider-proof acceptance.

The frozen Working Set contract remains authoritative for Resource Candidate, exact-resource admission/revalidation, Working Set, render-manifest, and future application disclosure semantics. Its sections 6-8 and IWS1-PD/PC/HB/PM/PH/PI/MI contain an earlier provider-proof candidate. Their `prepare/commit/lookup` Interface, `preparedRef`, credential record/revision assumptions, canonical model/options/message/tool schemas, permit/result unions, Model Input Receipt transport shape, provider-dispatch failure table, and provider-proof acceptance wording are **reference-only and superseded** by this lifecycle contract. They are neither an alternative Pi Interface nor implementation authorization.

Before Working Set activation, its owner must provide a generic Adapter mapping from current Workspace binding/disclosure authority into the lifecycle bases, prior-entry drafts, terminal opaque receipt material, retention decision, and verifier. That mapping and all affected IWS acceptance require a new independent cross-owner review. The frozen Working Set document is not edited during PNW-A repair, and none of its provider-proof field names enter `packages/agent`.

## 1. Decision and business problem

One open `CaseWorkspace` will use one durable Pi `Session` under one live lease
and one non-durable Workspace-lifetime `AgentHarness`. Session persists across
close/reopen; Harness is reconstructed once per successful `open` and reused by
that Workspace's prompts. Pi owns the repository/lease, agent loop, transcript,
tool execution, turn snapshots, transactional boundaries, queues, compaction,
branch navigation, run fencing and generic provider-dispatch transaction.
Agent Workspace supplies CTI policy at Pi seams: Case context admission,
Orientation reopen, trusted identity binding, context eligibility, closed
capability recipes, Working Set admission, provider-input authorization,
output publication, and the public `WorkspaceTurn` Adapter.

The real product problem is continuity of one investigation task across model and tool turns while Case visibility, authorization, Session history, and asynchronous results can change. Without `CaseWorkspace`, every caller would have to coordinate OpenCTI observation, Pi lifecycle, disclosure, stale-result fencing, recovery, and terminal behavior. Without Pi owning the execution spine, the Workspace grows a second transcript and lifecycle that diverges as soon as tools, save points, compaction, or branching are used.

The current implementation is a safe transition point, not the target: each public Turn creates an in-memory Pi Session and Harness, projects qualified caller-Session prose into it, then separately commits a four-entry caller-Session group. That design passed Slice 0b behavior acceptance, but it does not validate a Workspace-lifetime Harness, Pi tool events, Pi save-point commit, or real Pi compaction/tree behavior.

## 2. Scope and non-goals

This cycle may change the generic Pi seam in `packages/agent/` and then migrate the Orientation-only Workspace. It must expose one Pi-owned prepared-invocation/Provider Dispatch Implementation through two internal frontends: the Workspace-lifetime Harness and the bounded pre-Investigation Task Understanding invocation Port. The latter has no Harness, Session, tool, loop, or investigation semantics. PNW-A includes the generic logical provider-invocation transaction required by both frontends and the later I&E consumer, but no CTI/I&E meaning enters Pi. This cycle does not start or import I&E from Workspace, consume I&E Retrieval, implement Working Set, Assessment, full Case Projection, Case Management Facade, `ResourceUsePermitV1`, Durable Operation Journal, strict R1, or ADRs 0007-0010 implementation. Independent IER1 core work, if started by its owner, remains outside this cycle.

Planned Pi facilities are not current facts. The public pending-write Session facade, generic typed hook pipeline, semi-durable Harness restore, auto-compaction/retry, final abort barrier, and common observability implementation remain incomplete until their own code and focused tests land.

## 3. Application Interface

The target common Interface remains deep:

```typescript
interface CaseWorkspaceModule {
	open(
		input: {
			caseRef: string;
			actor: TrustedActorBinding;
			sessionRef: WorkspaceSessionRef;
		},
		options?: { signal?: AbortSignal },
	): Promise<CaseWorkspace>;
}

interface CaseWorkspace {
	prompt(input: { task: string; images?: readonly ImageContent[] }): WorkspaceTurn;
	close(): Promise<void>;
}

interface WorkspaceTurn extends AsyncIterable<WorkspaceEvent> {
	readonly id: string;
	readonly result: Promise<WorkspaceTurnResult>;
	cancel(): void;
}
```

The target closed terminal union contains five variants:

```typescript
type WorkspaceTerminalEvent =
	| { type: "turn_completed" }
	| { type: "turn_clarification_required"; taskContextId: string; questions: readonly AdmittedClarificationQuestion[] }
	| { type: "turn_cancelled" }
	| { type: "turn_failed"; failure: WorkspaceFailure }
	| { type: "turn_discarded"; reason: TurnDiscardReason };

type WorkspaceTurnResult = { operationId: string; turnId: string } &
	(
		| { status: "completed"; message: AssistantMessage }
		| { status: "clarification_required"; taskContextId: string; questions: readonly AdmittedClarificationQuestion[] }
		| { status: "cancelled" }
		| { status: "failed"; failure: WorkspaceFailure }
		| { status: "discarded"; reason: TurnDiscardReason }
	);
```

An Investigation Agent Run terminal receipt uses `completed`, `cancelled`, `failed`, or `discarded`. `turn_clarification_required` is a pre-run Workspace terminal: after the immutable task and deterministic clarification record commit through their owning Session control group, no Agent Run starts, the event is emitted once, and `result` resolves once. It contains only deterministic actor-safe questions and no model clarification prose. The delivered four-variant Orientation union remains historical Slice 0b evidence rather than the target union.

`WorkspaceSessionRef` becomes an opaque immutable reference. A generic Pi `SessionRepository` in `packages/agent/` resolves it, acquires one fenced single-writer lease, opens or recovers the Pi Session, and releases the lease. Workspace supplies only the Case/actor/session binding policy and never implements a parallel repository. The caller does not receive storage or signing authority through this Interface.

The delivered `orientationDependencies` input remains only during migration and is not part of the target common Interface. [Pre-Investigation Task Understanding v1](pre-investigation-task-understanding-v1-contract.md) cannot choose dependencies. The initial context compiler conservatively selects all Orientation dependencies for free-form tasks. Only a trusted closed workflow or operation recipe may establish a narrower dependency set and preserve dependency-disjoint acceptance. Free text and model output never infer or narrow trusted dependencies.

Non-type Interface rules:

- `open` completes Session recovery, a fresh bounded Orientation read, and Harness construction before returning.
- one Workspace admits at most one active public Turn; current read-only supersession remains a compatibility behavior, but effectful work must later use explicit cancellation, steering/follow-up, or a busy result rather than implicit replacement;
- `WorkspaceTurn.result` resolves exactly once and never rejects;
- public event identity is stable, sequence starts at one and strictly increases, and exactly one terminal event closes the stream;
- `turn_completed` occurs only after the final Pi save-point and the receipt-last Agent Run settlement group commit;
- `cancel` and `close` are idempotent and locally bounded; neither claims that an uncooperative remote computation stopped;
- Orientation bodies remain reconstructable context, not ordinary Session or Case authority;
- atomic append guarantees remain scoped to a qualified storage instance unless a stronger Adapter is separately proven.

## 4. Module ownership and seams

| Module | Owns | Must not own |
|---|---|---|
| Pi `AgentHarness` | agent/tool loop, run generation, event order, turn snapshots, queues, save-point and Agent Run settlement transactions, bounded local abort, late-event fence | CTI authorization, Orientation semantics, Case authority |
| Pi `Session` and `SessionRepository` | persisted transcript, tool results, configuration/control entries, v1 small Workspace-state references, compaction, branch, opaque-reference resolution, fenced lease, release, and generic recovery | current Case truth, CTI binding policy, I&E bodies, or authoritative external state |
| Pi private `ProviderDispatchTransaction` core | behind the Harness-private and bounded-one-shot frontends, call A3.1 preparation, privately bind every resolved secret, canonicalize the complete safe request, drive the staged application authority flow, coordinate A4, advance the private cursor, and consume one current-generation permit | credential-store records/revisions, CTI/I&E meaning, application rebuilding/mutating provider input, HTTP/wire serialization, payload replacement callbacks, or protected replay storage |
| Pi Provider Dispatch runtime composition | construct exactly one core with one `Models`/Provider/Auth path, one secret binder, one already-leased Session A4/cursor binding, one application authority/authenticator pair, and one generation registry; issue both frontend capabilities from that core | expose the private core/token, open/create/select a Session, create a second provider transaction, or let either frontend substitute dependencies |
| Pi Provider Dispatch frontends | Harness mints one private post-hook attempt; the bounded one-shot frontend exposes one already-bound no-argument `dispatch()` capability to its production invocation Adapter | give Task Understanding a Harness, Session, Tool, queue, prepared value, credential, permit, or caller-supplied identity/leaf replacement |
| Pi runtime-composition `ProviderDispatchSecretBinder` | receive raw prepared API key, environment values, model/request-option header values, session ID, and resolved base URL; return domain-separated HMAC bindings under current key policy | expose raw values to Workspace/application authority, persist them, interpret CTI, or authorize disclosure |
| application `ProviderDispatchApplicationAuthority` and receipt verifier | before artifact, supply the closed application binding; after artifact, decide disclosure/prior entries; after A4 preview, create and verify the terminal opaque material under application policy | see raw prepared secrets, canonicalize Pi request facts, commit Session, mint a permit, call the Adapter, or override Pi digests |
| Workspace `TaskUnderstandingModule` | immutable-task pre-scan, one structured proposal, deterministic admission/clarification, and Additional Task Context | Harness, Session, tools, Query Candidates, capabilities, investigation plan, provider client, or autonomous retry |
| `CaseWorkspace` | Case/actor binding, trusted Session/Task identity binder, Orientation slot, invalidation state, closed capability recipes, Working Set/context/provider/publication policy, public Turn Adapter | a second agent loop, second transcript, raw I&E store, or model-supplied authority |
| Orientation Adapter | actor-scoped bounded observations and qualified external mapping | Harness lifecycle or Session recovery |
| model | investigation reasoning and selection among currently exposed opaque candidate references/capabilities | object IDs, authorization, trusted bindings, dependency claims, commit, retry, terminal, or authority |

Pi additions must be generic. CTI supplies policy results and signed entries; Pi never learns Orientation block names or Case semantics.

## 5. Required Pi lifecycle depth

Before Workspace migration, Pi must provide these generic capabilities:

1. **Pre-save-point Session transaction.** In opt-in mode, one complete Pi turn's user, assistant, and source-ordered tool-result entries remain in a Harness-owned transaction view. After `turn_end`, an application policy may append custom receipts and choose commit or rollback. Commit uses expected-leaf all-or-none append with the receipt physically last. Default Harness behavior need not change for other applications.
2. **Ordered Harness Session facade.** Hooks and subscribers can read committed state and enqueue custom entries into the current save-point group without closing over the raw Session or bypassing pending-write ordering.
3. **One context-entry policy for every consumer.** An asynchronous policy receives the active branch, retained append order, default compaction selection, metadata/head, and purpose (`provider`, `compaction`, or `branch_summary`). It may select entries or deny use. Pi provides evidence; the policy interprets CTI receipts.
4. **Pre-provider denial.** A late local invalidation can stop a request after context construction but before provider dispatch without relying on a thrown hook or prompt instruction.
5. **Run-generation settlement.** Local cancel retires the current generation, closes its event/Session/tool-dispatch sinks, and restores a usable Harness state without waiting indefinitely for an uncooperative provider. Late remote work may consume resources, but cannot write or dispatch a new tool through the retired generation.
6. **Finalized tool outcome coverage.** Every executed, blocked, unknown, invalid, or truncated tool call reaches one finalized outcome seam before its tool-result message becomes a save-point candidate.
7. **Agent Run settlement transaction.** After the final Pi save point, Pi opens one expected-leaf settlement group. On the ordinary non-A6 path the loop-internal `agent_end` has already occurred; on the A6 opt-in path it is only a private buffered candidate and is not published until settlement closes. Workspace supplies one authenticated terminal receipt; it is physically last. Only that commit makes a public `completed` terminal eligible. Pre-run `clarification_required` never enters an Agent Run settlement. Cancelled, failed, or discarded Runs use the same settlement seam when local state permits; a conflict appends nothing and yields a Session-binding failure.
8. **Independent control transaction.** A context-generation advance is an ordered Pi Session control group, independent of the active model/tool transaction. Pi serializes it through the Session facade; Workspace supplies the signed dependency-scoped payload and validation policy.
9. **Transactional Harness configuration.** Active-tool/model/resource/context changes requested during a Pi turn are staged with that turn and become both durably and in-memory visible only after its save-point commit. Rollback or conflict restores the prior snapshot. Applications cannot mutate the live next-turn configuration from inside an uncommitted tool execution.
10. **Provider Dispatch Transaction.** After final frontend-specific conversion/order, budget-request admission, and any Harness `before_provider_request` policy, one shared private core calls A3.1 `Models.prepareSimple(...)` exactly once for either a Harness-private or bounded one-shot attempt. The transaction recursively qualifies only its detached `requestModel`, provider-neutral `context`, post-auth `requestOptions`, non-secret `authSource`, neutral attempt scope, and closed budget request; after any required exact count it constructs the final closed budget basis. It never reads a credential-store record, invents a credential revision, or resolves ambient auth again. It computes the generic artifact and safe secret bindings defined in section 6.6, obtains and independently compares an application-verified receipt, and commits one receipt-last control group through the A4 Session Interface. A committed or authoritatively exact-present group may advance the private cursor and yield one resident current-generation permit; only the transaction can consume that permit with the retained A3.1 value. Protected mode rejects payload mutation, unknown Model/options fields, invalid canonical data, header collisions, identity/budget/counter drift, and cross-composition substitution. The seam does not claim provider Adapter header merging, HTTP wire bytes, actual billing, or complete ignored-abort fencing.

The designed typed hook reducers, restore, retry, and observability work support this direction but are not all migration gates. Until typed reducers exist, Workspace registers exactly one aggregate policy handler for each result-producing hook because current last-non-undefined handler semantics are not safe composition.

### 5.1 Closed Agent Run settlement evidence target

Pi owns the generic settlement group and its materialization evidence; the application owns the meaning and authenticity of the physically last terminal custom entry. Pi does not sign, parse, or reproduce application terminal data. The target seam is:

```typescript
interface PiAgentRunSettlementEvidenceV1 {
	protocol: "pi-agent-run-settlement/v1";
	sessionId: string;
	runId: string;
	runGeneration: number;
	terminal: "completed" | "cancelled" | "failed" | "discarded";
	finalSavePointEntryId: string;
	finalSavePointEntryDigest: PiDigestV1;
	applicationTerminal: {
		customType: string;
		entryId: string;
		entryDigest: PiDigestV1;
		receiptDigest: PiDigestV1;
	};
	batchEvidence: PiSessionControlBatchEvidenceV1;
	evidenceDigest: PiDigestV1;
}

interface PiAgentRunSettlementApplicationVerifierV1 {
	verify(input: {
		piFacts: {
			sessionId: string;
			runId: string;
			runGeneration: number;
			terminal: "completed" | "cancelled" | "failed" | "discarded";
			finalSavePointEntryId: string;
			finalSavePointEntryDigest: PiDigestV1;
		};
		preview: {
			sessionId: string;
			expectedLeafId: string;
			terminalEntryId: string;
			terminalParentId: string;
			terminalTimestamp: string;
		};
		applicationTerminal: {
			customType: string;
			data: PiCanonicalJsonV1;
			receiptDigest: PiDigestV1;
		};
	}): Promise<
		| { kind: "verified"; verificationBindingDigest: PiDigestV1 }
		| { kind: "denied"; code: string }
		| { kind: "unavailable"; code: string }
	>;
}
```

Pi also owns one private, non-secret ordinary-settlement evidence sidecar. Its
deterministic key is exactly `(sessionId, runId, runGeneration,
finalSavePointEntryId, finalSavePointEntryDigest, terminalEntryId)`. Its value is
the existing complete `PiAgentRunSettlementEvidenceV1`, including the existing
`PiSessionControlBatchEvidenceV1`; it defines no second evidence or digest
format. The sidecar belongs to the Harness/leased `SessionRepository`
composition, is unavailable to Workspace and public Session callers, and never
contains application secrets or resident A4/Provider/Tool authority.

After `sealTerminal`, Pi has fixed the terminal bytes and existing A4 evidence.
Before A4 commit, the repository atomically no-replace publishes one private
durable `prepared` sidecar-journal record at the deterministic key. That record
contains the complete existing `PiAgentRunSettlementEvidenceV1`, its fixed
materialized terminal/batch bytes, their existing validation/evidence digest,
and literal status `prepared`; it defines no new A4 digest. Only after that
record is durable may Pi invoke the one sealed A4 commit. A committed or
authoritatively `exact_present` batch then atomically no-replace publishes the
complete final sidecar from those exact journal bytes. Byte-identical replay is
success; any different value at the same prepared or final key is conflict.

On reopen, `prepared` plus authoritative lookup `absent` is precommit and is not
recognized as settlement. The repository may safely remove that exact prepared
record or allow the original resident settlement attempt to retry its already
sealed commit; recovery itself never commits or rematerializes A4. `prepared`
plus `exact_present` rolls forward only by publishing the final sidecar from the
journal's fixed bytes. Partial, conflicting, unreadable, wrong-key, or
non-exact/non-absent lookup evidence fails closed. After final publication, the
repository first publishes a deterministic cleanup/tombstone status and only
then removes the matching prepared name; a crash resumes that order. A final
sidecar without its matching prepared record or cleanup tombstone is
source-less and invalid. Memory simulates the same states in its shared catalog;
JSONL persists them durably. No path reconstructs an A4 prepared/sealed handle.

The application terminal is produced through this second and only application
Interface. It is constructor-owned configuration of a settlement-enabled
`AgentHarness`; it is not a method on `Session`, an A4 Adapter, or a capability
returned to application code.

```typescript
interface PiAgentRunSettlementApplicationV1 {
	readonly customType: string;
	createTerminal(input: {
		piFacts: PiAgentRunSettlementPiFactsV1;
		preview: PiAgentRunSettlementPreviewV1;
	}): Promise<
		| {
				kind: "created";
				data: PiCanonicalJsonV1;
				receiptDigest: PiDigestV1;
		  }
		| { kind: "denied"; code: string }
		| { kind: "unavailable"; code: string }
	>;
	verify: PiAgentRunSettlementApplicationVerifierV1["verify"];
}

interface PiAgentRunSettlementPiFactsV1 {
	readonly sessionId: string;
	readonly runId: string;
	readonly runGeneration: number;
	readonly terminal: "completed" | "cancelled" | "failed" | "discarded";
	readonly finalSavePointEntryId: string;
	readonly finalSavePointEntryDigest: PiDigestV1;
}

interface PiAgentRunSettlementPreviewV1 {
	readonly sessionId: string;
	readonly expectedLeafId: string;
	readonly terminalEntryId: string;
	readonly terminalParentId: string;
	readonly terminalTimestamp: string;
}
```

`createTerminal` is invoked exactly once and only after successful A4 prepare.
Its input is an isolated recursive snapshot of the same Pi facts and projected
preview later supplied to both verifier calls. Its `created` result is
recursively snapshotted once at return. The application never receives the A4
prepared/sealed capability, prior-entry array, commit method, lookup method,
raw `Session`, entry-digest helper, or batch canonicalizer. `denied`,
`unavailable`, a thrown callback, an invalid closed result, invalid canonical
data, or a verifier failure abandons the preparation and appends zero
settlement entries. Pi does not retry `createTerminal`.

Application `denied|unavailable` codes are preserved exactly after validation.
A thrown creator maps to `application_unavailable` with Pi-reserved code
`callback_threw`; a thrown verifier maps to `verification_unavailable` with
that same code. An unknown or malformed creator result, invalid `created` data,
or receipt-digest mismatch maps to `invalid_application_terminal`. An unknown
or malformed verifier result maps to `verification_unavailable` with
Pi-reserved code `invalid_result`. Unequal first/second verified binding
digests map to `verification_drift`. Every one of these branches has
`knowledge: "absent"`, returns no evidence, and appends zero settlement
entries. Pi-reserved codes obey the same denial-code grammar and cannot collide
with application provenance because their owning result is produced by Pi.

The Harness external seam is deliberately smaller than the implementation it
hides:

```typescript
interface PiAgentRunSettlementOptionsV1 {
	readonly application: PiAgentRunSettlementApplicationV1;
}

interface AgentHarnessOptions {
	readonly runSettlement?: PiAgentRunSettlementOptionsV1;
}

type PiAgentRunSettlementKnowledgeV1 = "exact" | "absent" | "conflict" | "unavailable";

type PiAgentRunSettlementTerminalResultV1 =
	| {
			readonly kind: "settled";
			readonly knowledge: "exact";
			readonly source: "committed" | "exact_present";
			readonly evidence: PiAgentRunSettlementEvidenceV1;
	  }
	| {
			readonly kind: "not_settled";
			readonly knowledge: "absent";
			readonly reason:
				| "no_final_save_point"
				| "invalid_application_terminal"
				| "verification_drift"
				| "ack_absent";
	  }
	| {
			readonly kind: "not_settled";
			readonly knowledge: "absent";
			readonly reason:
				| "application_denied"
				| "application_unavailable"
				| "verification_denied"
				| "verification_unavailable";
			readonly code: string;
	  }
	| {
			readonly kind: "not_settled";
			readonly knowledge: "conflict";
			readonly reason: "cas_conflict" | "ack_conflict";
	  }
	| {
			readonly kind: "not_settled";
			readonly knowledge: "unavailable";
			readonly reason: "control_unavailable" | "ack_unavailable";
			readonly code: PiSessionControlUnavailableReasonV1;
	  };

type PiAgentRunSettlementResultV1 = PiAgentRunSettlementTerminalResultV1;

interface AgentHarness {
	prompt(text: string, options?: { images?: ImageContent[] }): Promise<AssistantMessage>;
	promptWithSettlement(
		text: string,
		options?: { images?: ImageContent[] },
	): Promise<{ readonly message: AssistantMessage; readonly settlement: PiAgentRunSettlementResultV1 }>;
	abort(): Promise<AbortResult>;
}

type AgentRunSettlementEventV1 = {
	readonly type: "agent_run_settlement";
	readonly runId: string;
	readonly runGeneration: number;
	readonly result: PiAgentRunSettlementResultV1;
};
```

The existing `prompt() -> AssistantMessage` Interface and every Harness without
`runSettlement` remain unchanged. `promptWithSettlement` is available only when
`runSettlement` was configured; otherwise it rejects synchronously with the
existing Harness `invalid_state` classification before starting a Run. It owns
one ordinary Harness Run and returns only after `agent_end`, final save-point
closure, settlement commit/lookup, one `agent_run_settlement` event, and all
awaited subscribers to that event. The event is emitted exactly once after the
result is frozen and before the existing `settled` event. It contains no
terminal data, A4 capability, or raw Session entry. The Interface never exposes
a separate public `settle`, retry, lookup, registry, reducer, or A4 method. A
settlement-enabled `prompt()` still follows the legacy return shape
and performs no settlement; applications requiring evidence must call
`promptWithSettlement`. This avoids changing existing callers while keeping the
settlement path explicit rather than making evidence discoverable through a
last-result side channel.

The `abort()` declaration above is the existing public Harness Interface, not a
new settlement method. On invocation its current implementation synchronously,
before its first `await`, clears steer/follow-up queues, marks an open
transactional save point failed, and aborts the active Run signal. Its returned
`Promise<AbortResult>` then awaits queue notification and `waitForIdle()`, emits
the existing `abort` event, and resolves with `{ clearedSteer,
clearedFollowUp }`; hook failures reject only after those settlement waits.
Each call retains its existing queue-result/event behavior, so this contract
does not relabel `abort()` itself as idempotent and does not make it return
settlement evidence. The terminal race is decided by the synchronous signal
observation; the one settlement result is observed by awaiting
`promptWithSettlement()`. Public acceptance invokes `abort()` externally and
must not await its Promise from an in-Run subscriber that settlement itself
must await.

The existing Harness `save_point` committed event gains one Pi-owned field:

```typescript
interface PiAgentSavePointCommitEvidenceV1 {
	readonly protocol: "pi-agent-save-point-commit-evidence/v1";
	readonly sessionId: string;
	readonly expectedLeafId: string | null;
	readonly finalEntryId: string;
	readonly finalEntryDigest: PiDigestV1;
}

interface PiAgentRunFinalMarkerV1 {
	readonly protocol: "pi-agent-run-final-marker/v1";
	readonly sessionId: string;
	readonly runId: string;
	readonly runGeneration: number;
	readonly finalSavePointEntryId: string;
	readonly finalSavePointEntryDigest: PiDigestV1;
	readonly settlementExpected: true;
	readonly markerDigest: PiDigestV1;
}

type CommittedSavePointEventV1 = ExistingCommittedSavePointEvent & {
	readonly commitEvidence: PiAgentSavePointCommitEvidenceV1;
};
```

After A1's successful `appendBatchIfLeaf`, Pi authoritatively reads the exact
materialized final entry, requires its ID to equal the last committed ID, and
recomputes `finalEntryDigest` with the existing A4
`pi-session-entry-digest-basis/v1` canonicalizer. It does not accept a digest
from the save-point policy. A missing, changed, non-final, or noncanonical entry
turns the Run into a save-point failure and cannot enter settlement. The
complete evidence is snapshotted into the active-Run registry before the
committed event is emitted. Each later committed save point replaces only that
Run's previous final-save-point evidence; settlement consumes the last one.

For the final save point only, A1 also materializes one Pi-owned durable
`pi_agent_run_final_marker` custom entry in that same all-or-none append. The
physical order is turn entries, source-ordered application entries, the marker,
then the application save-point terminal receipt; the receipt remains physically
last. Before append, Pi fixes every ID and byte, computes the physically last
receipt's entry digest, and puts that ID/digest in the marker. `markerDigest =
piDigest({ domain: "pi.agent-run-final-marker/v1", marker: <the complete marker
with markerDigest omitted> })`. Marker Session/Run/generation come only from the
resident Run owner and `settlementExpected` is literally `true`. The referenced
receipt is the same final entry exposed by `PiAgentSavePointCommitEvidenceV1`.
Marker and receipt are committed or absent together. Settlement must use that
exact marker identity and expected leaf; another Run or generation cannot settle
it. Ordinary non-final save points have no final marker. This marker is integrity
and recovery evidence only, never Provider/Tool/permit or replay authority.

At synchronous Run admission, before the first await, Pi mints one opaque
`runId` and registers it under the Harness-owned `sessionId`. `runId` uses the
identifier grammar above and is never application-supplied. The Harness owns a
non-negative safe-integer `runGeneration`, starting at `0` for its first
admitted Run and increasing exactly once for each later admitted Run; overflow
rejects admission before work. A generation is immutable after admission and
is never reset by branch navigation or ordinary configuration change. This is
resident single-Harness ownership only; it is not an A5 lease or reopen claim.

The settlement identity is exactly `(sessionId, runId, runGeneration)`. One
identity has one once-only settlement promise. Repeated completion, abort
signal, or low-level terminal observations for that same active Run join that
promise and return its one frozen terminal result; they perform zero repeated creator,
verifier, A4 prepare/seal/commit/lookup, Session append, or observer work. There
is no public `duplicate` result because a legal public caller cannot create a
second settlement attempt or resupply identity. Associating an occupied
`runId` with a different Session or generation is likewise impossible through
the public Interface. It is a Pi-internal typed invariant violation, throws
`AgentRunSettlementInvariantError`, and is reviewed statically rather than
fabricated through a registry, identity-input, A4, reducer, or test-only seam.
Neither case remints identity or starts a second settlement.

Every object and result in this subsection is closed; unknown members and omitted required members are invalid. Identifiers match `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`. `customType` matches `[a-z][a-z0-9_]{0,127}`. Denial codes match `[a-z][a-z0-9_]{0,63}`. Digests use `PiDigestV1`. `runGeneration` is a non-negative safe integer and `-0` is invalid. The complete evidence has canonical depth at most 8, at most 64 object members, and at most 32,768 UTF-8 bytes; application terminal data has canonical depth at most 6, at most 48 object members, and at most 24,576 UTF-8 bytes. These are Pi settlement-seam bounds, not application payload recommendations.

`sessionId`, `runId`, `runGeneration`, `terminal`, `finalSavePointEntryId`, and `finalSavePointEntryDigest` come only from the recursively snapshotted Pi-owned active-Run registry and committed final-save-point evidence. Pi recomputes the final save-point entry digest from that exact committed Session entry. Application input cannot supply or override those facts. The application may supply only terminal `customType`, canonical data, its receipt digest, and the verifier result.

Before A4 prepare, Pi recursively snapshots only its authoritative Run/final-save-point facts, the application verifier/authenticator binding, and the terminal `customType`. It then prepares the terminal-only A4 batch and obtains one immutable preview. The preview fields above equal the A4 preview's Session ID, expected leaf, reserved terminal ID, parent ID, and timestamp; they use the same identifier/time bounds and cannot be supplied by application code.

Only after preview does the application construct and authenticate the complete terminal data that contains those reserved materialization fields. Pi then calls the application verifier with the exact Pi-facts, preview, terminal data, and receipt-digest snapshots. `verified` means the application checked the complete terminal data, receipt digest, authenticator binding, Run/generation/disposition, final-save-point fields, and preview fields against that exact immutable input. Verification occurs before `sealTerminal`. After seal, Pi requires the materialized terminal to equal the preview, `customType`, and canonical data, and recomputes its entry and batch digests. Immediately before commit, Pi calls the verifier again with the identical snapshots and requires the same verification-binding digest; denial, unavailability, mutation, or drift abandons the batch and appends none. No phase rebuilds or rewrites terminal data. Pi never receives the application key, parses application business meaning, or treats a valid MAC for another Run, preview, or save point as verification for this group.

V1 uses a terminal-only settlement batch: `batchEvidence.orderedEntryIds` and `orderedEntryDigests` each have length exactly one, contain no duplicate, and their sole entry is the application terminal. `sessionId === batchEvidence.sessionId`; `batchEvidence.expectedLeafId === finalSavePointEntryId`; `applicationTerminal.entryId === batchEvidence.terminalEntryId === batchEvidence.orderedEntryIds[0]`; and `applicationTerminal.entryDigest === batchEvidence.orderedEntryDigests[0]`. The terminal `customType` and canonical data must equal the exact sealed, physically last materialized custom entry. Pi recomputes every entry digest and the A4 `batchDigest` from that materialized entry and the expected-leaf/session basis before constructing settlement evidence. Any mismatch yields no evidence.

`evidenceDigest = piDigest({ domain: "pi.agent-run-settlement-evidence/v1", evidence: <the complete closed evidence with evidenceDigest omitted> })`. Array order is physical Session order and is never resorted. `applicationTerminal.receiptDigest` is opaque to Pi but is bound into this evidence; the verifier establishes the terminal entry's application-owned authenticity and exact receipt binding at the declared fences. Calling this evidence signed or authenticated by Pi is forbidden unless a later Pi-owned key contract is separately accepted.

The implementation uses one A4 `prepare -> preview -> sealTerminal -> commit` group. `committed` returns `settled/exact/committed`. A4 prepare `conflict` and commit `conflict` return `not_settled/conflict/cas_conflict`; prepare `unsupported|unavailable` returns `not_settled/unavailable/control_unavailable`. `acknowledgement_unknown` permits exactly one `lookupControlBatch` using the retained A4 evidence: `exact_present` returns the identical evidence as `settled/exact/exact_present`; `absent` returns `not_settled/absent/ack_absent`; `conflict` returns `not_settled/conflict/ack_conflict`; and `unavailable` returns `not_settled/unavailable/ack_unavailable`. Only the two `settled/exact` branches contain settlement evidence. Every `not_settled` branch contains none. No path reconstructs, reseals, recommits, translates the application terminal, or upgrades `absent`, `conflict`, or `unavailable` to trusted presence. Process-crash discovery remains PNW-E repository/recovery work and cannot recreate resident A4 evidence.

Successful provider completion selects terminal `completed`; provider error
selects `failed`; and an admitted local cancellation selects `cancelled`.
Pi opens one synchronous terminal-claim CAS immediately after a final save
point's commit evidence enters the active-Run registry and before the first
settlement await. The first eligible completion, provider failure, or public
`abort()` observation wins that claim. The winner fixes `completed`, `failed`,
or `cancelled` in Pi facts; every later observation joins the same settlement
promise and cannot change or restart it. This claim is the sole
completion-versus-cancel cutpoint. No creator, verifier, or A4 settlement work
starts until one claimant wins.

If `abort()` wins after the final save point is committed, Pi continues the
same terminal-only A4 path with terminal `cancelled`; the already-aborted Run
signal does not abandon settlement. Cancellation observed while awaiting A4
prepare, `createTerminal`, either verifier call, commit, or the one
acknowledgement lookup, or immediately before/after immutable preview
inspection or synchronous `sealTerminal`, therefore loses the terminal claim
and has no effect on the frozen terminal or result. If completion or failure won first,
the path remains respectively `completed` or `failed`. If cancellation won
first, the path remains `cancelled`. In all three cases the existing creator,
verification, CAS, and acknowledgement result mapping determines the returned
`settled` or `not_settled` branch; cancellation never converts one of those
failures into a second result and never causes resend, reseal, recommit, or a
second lookup.

An `abort()` observation before final-save-point evidence records the pending
cancel claimant but starts zero settlement work. If A1 subsequently commits a
final save point for that Run, the pending cancel claimant wins synchronously
when the claim CAS opens and the `cancelled` settlement path proceeds. If the
Run closes without final-save-point evidence, there is no settlement basis: Pi
performs zero creator/verifier/A4 work and `promptWithSettlement` returns the
Run's aborted assistant message plus
`not_settled/absent/no_final_save_point`. Cancel does not erase an already
committed final save point. This slice does not make abort bounded, fence all
late sinks, or wait for an uncooperative provider; those remain A6.

`discarded` remains a reserved evidence value for the later Pi lifecycle that
owns an admitted discard transition. This focused Interface defines no such
transition, does not accept terminal selection from application code, and
cannot produce `discarded`. Adding its trigger requires a separately accepted
Harness lifecycle amendment; the evidence schema need not change.

Focused public-Harness acceptance is frozen to these seven scenarios and must
not be expanded into an implementation-detail matrix:

1. A settlement-enabled successful no-tool Run commits an A1 final save point,
   calls `createTerminal` only after the immutable A4 preview, verifies the
   identical snapshots twice, commits one physically-last terminal, and returns
   `settled/exact/committed` with recomputable save-point, entry, batch, and
   evidence digests.
2. Through only public `promptWithSettlement()` and `abort()`, deterministic
   completion-before-cancel and cancel-before-completion races each produce one
   terminal claim, one settlement promise, one settlement event, and one
   result from `promptWithSettlement()`. Repeated/concurrent `abort()` calls
   retain their existing individual `Promise<AbortResult>` queue/event
   behavior, but their synchronous signal observations cause zero repeated
   application/A4/Session settlement work. Foreign identity association is an
   internal typed invariant covered by static review, not a fabricated public
   test case.
3. Creator denial/unavailability/throw, invalid created data, verifier
   denial/unavailability/throw, or verification-binding drift is represented by
   one table-driven public scenario: the result is the corresponding closed
   `not_settled/absent` reason and the settlement append count is zero.
4. A4 prepare or commit CAS conflict returns
   `not_settled/conflict/cas_conflict`, appends no settlement entry, and leaves
   the final save point as the Session leaf.
5. A table-driven public cancellation scenario invokes public `abort()`
   externally, without awaiting it inside a Harness subscriber, while A4
   prepare, creator, either verify, commit, or lookup is awaited, and
   immediately around preview inspection and synchronous seal. After a final
   save point and terminal claim it preserves the winner and executes exactly
   one settlement path; before final-save-point evidence it returns
   `not_settled/absent/no_final_save_point` and performs zero settlement work.
6. `acknowledgement_unknown` followed by `exact_present` performs one lookup,
   no recommit, and returns the byte-identical
   `settled/exact/exact_present` evidence.
7. `acknowledgement_unknown` followed by `absent`, `conflict`, or `unavailable`
   is one table-driven public scenario returning the matching closed
   `not_settled` knowledge/reason, no evidence, no recommit, and no second
   terminal.

This exact type is the sole `pi-agent-run-settlement/v1` target. Application contracts may reference it but must not redeclare it with different field names or add a second settlement group. The Workspace Run Control contract owns its terminal custom-entry schema; Workspace Output Publication only consumes that schema plus this Pi evidence.

**PNW-A3.1 delivered boundary:** `packages/ai` now exposes `Models.prepareSimple(...)` as the low-level auth-resolved deferred-start seam required before the generic transaction can be integrated. It captures one Provider and one auth resolution, owns detached request-model/context/request-options snapshots, projects structural runtime tool subtypes to only the public provider Tool fields while retaining valid schema metadata, retains `AbortSignal` and callback capability identity under explicit rules, enters no Provider Adapter or lazy API before its single-use `start()`, and preserves legacy synchronous `streamSimple()` behavior. The later tool-projection repair ran RED **1/10** to GREEN **11/11**; explicit Node `v24.14.0` verification passed five focused AI files and **44/44** tests, independent acceptance passed eight files and **81/81** tests, and the developer root check passed **802 files**.

A3.1 delivers none of the Session-side artifact canonicalization, HMAC receipt, disclosure comparison, expected-leaf commit/lookup, single-use permit authority, Harness protected path, run-generation binding, or A3.2 integration required by capability 10 and PNW-21 through PNW-29. It therefore does not complete PNW-A3, PNW-A, or a Workspace prototype.

## 6. Normal lifecycle

### 6.1 Open

1. Ask the Pi `SessionRepository` to resolve and exclusively lease the opaque Workspace Session.
2. Verify retained CTI protocol entries, rebuild the context-eligibility index, and classify unfinished legacy v1 spans as audit-only.
3. Perform a fresh complete Orientation double observation and install no body on failure.
4. Establish or advance signed per-dependency context generations.
5. Acquire one durable Pi Session lease, reconstruct one Workspace-lifetime Harness, install one aggregate Workspace policy, and create one Pi-event-to-WorkspaceTurn Adapter.

### 6.2 Pre-Investigation Task Understanding and admission

Every new free-form Original User Task first enters the private Module defined by [`pre-investigation-task-understanding/v1`](pre-investigation-task-understanding-v1-contract.md), before any Harness prompt or Agent Run. One bounded tool-free model call produces a structured proposal; deterministic code admits Additional Task Context, requests clarification, applies the closed raw-task fallback, or fails. It creates no planning assistant/tool messages and no Query Candidate or capability plan.

Clarification commits the immutable task and actor-safe clarification record through an independent Session control group and terminates the Workspace Turn without an Agent Run. Admission commits the immutable task and admitted context atomically to the existing leased Session, then constructs the first qualified Investigation context. The one-shot model frontend and Harness frontend reuse the same Pi-owned Provider Dispatch Implementation; neither Workspace nor Task Understanding owns a provider client.

### 6.3 Response without product tools

```text
Workspace turn_started
-> prompt safe point and optional Full Orientation Reopen
-> pre-Investigation Task Understanding and deterministic admission
-> Original User Task + Admitted Task Context commit to the existing Session
-> initial context compiler renders System Instructions, Original User Task,
   Additional Task Context, empty/current Working Set, layered Case Context,
   eligible Session History, and activated provider Tool schemas
-> formal Pi Investigation Agent Run starts on the Workspace-lifetime Harness
-> pre-provider local guard
-> provider stream and transactional assistant entry
-> Pi turn_end
-> CTI completion fence and signed save-point receipt
-> expected-leaf atomic commit
-> Pi save_point
-> [ordinary non-A6] loop-internal agent_end delivery, then optional settlement,
   then the existing idle / settled / public-result behavior
-> [A6 opt-in] loop produces a Pi-private buffered terminal candidate (not a
   published event); the synchronous Run-owner claim selects normal or retired
-> [A6 opt-in] settlement closes (one normal settlement or retired zero-work result)
-> [A6 opt-in] publish the selected buffered agent_end exactly once
-> [A6 opt-in] phase idle -> Harness settled -> public result resolves
-> Workspace turn_completed
```

In A6-enabled Harnesses the loop's original `agent_end` is never itself a public
event. Pi buffers it as private data, not an emitted, observable, or already
published event, carrying the captured
Run owner. It cannot invoke a subscriber, hook, publication callback, Session
write, or settlement action. Normal completion and retirement compete at the one
synchronous owner claim defined in section 6.9; only the winner's frozen terminal
candidate is later published. This buffering changes no ordinary Harness for
which A6 is omitted.

### 6.4 Product tool loop

`tool_call` performs fast deterministic admission after schema parsing. The trusted Tool Adapter binds actor, Case, authorization, versions, and other non-model fields. `tool_execution_update` is display-only. The finalized `tool_result` is a candidate, not a Workspace publication.

After the complete assistant/tool-result batch, the awaited save-point policy validates the batch, commits its signed Context Snapshot receipt, performs permitted local publication, and runs cancellable remote Orientation reconciliation if dirty. Pi then creates a fresh snapshot before the next provider request. Parallel read tools may finish out of order, while persisted tool results remain in assistant source order. Future effectful tools require sequential execution and their frozen durable-effect contracts; this cycle adds no such tool.

A public Workspace Turn may contain several Pi turns. Each durable Pi save point records its actual Context Snapshot dependencies. A distinct Agent Run settlement group links the ordered save points and writes the signed terminal receipt last. On the ordinary non-A6 path it follows the loop-internal `agent_end`; on the A6 opt-in path it precedes publication of the private buffered `agent_end` candidate. Its expected-leaf commit is the linearization point for a public `completed` terminal; it cannot pretend the final Orientation alone was the basis of earlier provider requests or tool results.

Product behavior is exposed through a closed Workspace capability catalog and trusted operation recipes. The model-visible tool name, number, and payload decomposition are Adapter details. After the formal Investigation Agent Run begins, the model may propose target-neutral Query Candidates under a separately accepted investigation-planning contract. Workspace mints opaque Resource Candidate References only from current actor-visible Orientation membership and renders the tool-enabled membership view without underlying source IDs. For the first later exact-resource recipe, the model may select only one `resourceCandidateRef` and an optional separately admitted non-executable `queryCandidateRef`. Workspace deterministically binds `WorkspaceSessionRef -> workspaceRef`, Original User Task/Admitted Task Context -> `taskRef`, and resource candidate membership -> exact source object before dispatch. Query Candidates remain target-neutral and these bindings never come from model fields.

When a recipe yields small Working Set state, its refs/version/edges/local receipt/canonical action outcome join the source-ordered finalized Pi tool results in the same expected-leaf save-point group, with the Context Snapshot receipt last. The leased Pi Session is the v1 state authority. Raw I&E capsules stay out of ordinary tool transcript; later context re-renders them from current Working Set references under the [Working Set contract](intelligence-working-set-v1-contract.md).

If the final save point commits but the process crashes before Agent Run settlement, reopen classifies the Run as interrupted. It never resumes the provider stream or re-executes tools. Before admitting a new prompt, Pi commits one recovery-discard settlement group against the current leaf; no event is re-emitted to the dead caller. A settlement conflict appends nothing and leaves the Session unavailable until reopened under an exclusive lease.

### 6.5 Provider dispatch

For every provider request that consumes Working Set/I&E material, Workspace first builds the final eligible projection, revalidates each exact I&E capture, performs deterministic rendering/token checks and finishes the aggregate `before_provider_request` policy. Pi then calls A3.1 preparation and qualifies the resulting detached `requestModel`, provider-neutral `context`, post-auth `requestOptions`, and non-secret `authSource`. The credential store and ambient auth sources are no longer inputs: only resolved API-key/environment/header/base-URL material present in those request facts is bound, and v1 defines no credential revision. Model headers and request-options headers remain separate; Pi neither pre-merges them nor resolves auth again. The original caller objects cease to be dispatch sources. The transaction verifies every application receipt/Disclosure Decision identity against the prepared artifact and commits the authenticated `may_have_dispatched` receipt before protected invocation. Only a current-generation unconsumed permit over that exact resident prepared value may invoke.

Protected v1 rejects `before_provider_payload`, caller `onPayload`, other function/custom-transport options, unknown/new options, invalid JCS data, non-finite/undefined/cyclic values, unsafe metadata/headers, receipt mismatch, and credential drift before receipt append or Adapter call. `AbortSignal` and Pi's non-mutating `onResponse` observer remain same-generation lifecycle capabilities outside the digest. Caller mutation after preparation changes neither the canonical digest nor eventual Adapter arguments.

The receipt proves the logical Adapter input, not HTTP wire bytes, socket write, remote receipt, billing, execution, or output reproducibility. A committed receipt remains `may_have_dispatched` across cancellation or crash; recovery never auto-resends or splices provider work. Digest-only evidence is never called replay. Protected exact-input replay and whole-prompt retention are disabled and deferred to a separate contract; the I&E capsule's own retention permission does not extend to User Task, Session, Orientation, tool, model-option, or complete logical-input content.

#### 6.5.1 Session-owned canonical primitives

Canonical JSON and digest representation are generic Pi Session primitives, owned independently of provider dispatch. A4 and every other Session protocol depend only on these types:

```typescript
type PiCanonicalJsonV1 =
	| null
	| boolean
	| number
	| string
	| readonly PiCanonicalJsonV1[]
	| { readonly [key: string]: PiCanonicalJsonV1 };

type PiDigestV1 = `sha256:${string}`;

interface PiSessionEntryDigestBasisV1 {
	protocol: "pi-session-entry-digest-basis/v1";
	entry: { readonly [key: string]: PiCanonicalJsonV1 };
}
```

`piDigest(basis)` is exactly the string `sha256:` plus 64 lowercase hexadecimal characters obtained from `SHA-256(UTF8(RFC8785_JCS(basis)))`. The UTF-8 input has no BOM, prefix, delimiter, trailing newline, Unicode normalization, or alternate serialization. `PiDigestV1` values that do not satisfy that exact lexical form reject. Pi Session owns this function and validates canonical depth/size before hashing.

### 6.6 Generic Provider Dispatch Transaction v1

This is the Design-PASS dual-frontend A3.2 contract opened by [ADR 0017](../adr/0017-understand-the-task-before-the-investigation-agent-run.md). One Pi-owned private transaction core serves both a Harness-private frontend and an already-bound bounded one-shot frontend. The second frontend neither exports prepared secrets nor creates a second provider transaction. The exact-input-count amendment pre-binds only facts available before prepare and returns actual auth-resolved evidence afterward. Section 6.6 now authorizes only its frozen deterministic focused implementation task; A3.1 and A4 acceptance remain unchanged, and real-provider counter registration/activation remains forbidden.

This protocol is generic Pi infrastructure. Names below describe Pi request facts and application ports; they do not import CTI, I&E, Case, Orientation, or Working Set types into `packages/agent`. Every object is a closed object. Optional values use the tagged slot, never property omission. Unknown members, accessors, functions, symbols, `undefined`, cycles, non-finite numbers, unsupported message/content/tool/schema/compat variants, or limits exceeded by the application policy fail before Session append.

```typescript
type ProviderDispatchCanonicalJsonV1 = PiCanonicalJsonV1;
type ProviderDispatchDigestV1 = PiDigestV1;

type ProviderDispatchSlotV1<T> =
	| { presence: "absent" }
	| { presence: "present"; value: T };

type ProviderDispatchSecretDomainV1 =
	| "request.api_key"
	| "request.environment_value"
	| "model.header_value"
	| "request_options.header_value"
	| "request.session_id"
	| "model.resolved_base_url";

interface ProviderDispatchSecretBindingV1 {
	protocol: "pi-provider-secret-binding/v1";
	algorithm: "HMAC-SHA-256";
	keyId: string;
	domain: ProviderDispatchSecretDomainV1;
	fieldName: string;
	utf8Length: number;
	macBase64Url: string;
}

interface ProviderDispatchModelHeaderBindingV1 {
	originalName: string;
	asciiLowerName: string;
	binding: ProviderDispatchSecretBindingV1;
}

interface ProviderDispatchRequestOptionsHeaderBindingV1 {
	originalName: string;
	asciiLowerName: string;
	value:
		| { disposition: "suppress" }
		| { disposition: "value"; binding: ProviderDispatchSecretBindingV1 };
}

interface ProviderDispatchModelBasisV1 {
	protocol: "pi-provider-model-basis/v1";
	id: string;
	name: string;
	api: string;
	provider: string;
	resolvedBaseUrlBinding: ProviderDispatchSecretBindingV1;
	reasoning: boolean;
	thinkingLevelMap: ProviderDispatchSlotV1<{
		off: ProviderDispatchSlotV1<string | null>;
		minimal: ProviderDispatchSlotV1<string | null>;
		low: ProviderDispatchSlotV1<string | null>;
		medium: ProviderDispatchSlotV1<string | null>;
		high: ProviderDispatchSlotV1<string | null>;
		xhigh: ProviderDispatchSlotV1<string | null>;
		max: ProviderDispatchSlotV1<string | null>;
	}>;
	input: readonly ("text" | "image")[];
	cost: {
		input: number;
		output: number;
		cacheRead: number;
		cacheWrite: number;
		tiers: ProviderDispatchSlotV1<readonly {
			input: number;
			output: number;
			cacheRead: number;
			cacheWrite: number;
			inputTokensAbove: number;
		}[]>;
	};
	contextWindow: number;
	maxTokens: number;
	headers: ProviderDispatchSlotV1<readonly ProviderDispatchModelHeaderBindingV1[]>;
	compat: ProviderDispatchSlotV1<ProviderDispatchCanonicalJsonV1>;
}

interface ProviderDispatchAuthSourceBasisV1 {
	protocol: "pi-provider-auth-source-basis/v1";
	authSource: string;
}

interface ProviderDispatchCredentialBasisV1 {
	protocol: "pi-provider-credential-basis/v1";
	authSourceDigest: ProviderDispatchSlotV1<string>;
	apiKey: ProviderDispatchSlotV1<ProviderDispatchSecretBindingV1>;
	environment: ProviderDispatchSlotV1<readonly {
		name: string;
		binding: ProviderDispatchSecretBindingV1;
	}[]>;
}

interface ProviderDispatchSystemPromptBasisV1 {
	protocol: "pi-provider-system-prompt-basis/v1";
	systemPrompt: ProviderDispatchSlotV1<string>;
}

interface ProviderDispatchMessageBasisV1 {
	protocol: "pi-provider-message-basis/v1";
	position: number;
	message: ProviderDispatchCanonicalJsonV1;
}

interface ProviderDispatchToolBasisV1 {
	protocol: "pi-provider-tool-basis/v1";
	position: number;
	name: string;
	description: string;
	parameters: ProviderDispatchCanonicalJsonV1;
}

interface ProviderDispatchMetadataBasisV1 {
	protocol: "pi-provider-metadata-basis/v1";
	metadata: { readonly [key: string]: ProviderDispatchCanonicalJsonV1 };
}

interface ProviderDispatchOptionsBasisV1 {
	protocol: "pi-provider-options-basis/v1";
	temperature: ProviderDispatchSlotV1<number>;
	maxTokens: ProviderDispatchSlotV1<number>;
	transport: ProviderDispatchSlotV1<"sse" | "websocket" | "websocket-cached" | "auto">;
	cacheRetention: ProviderDispatchSlotV1<"none" | "short" | "long">;
	sessionId: ProviderDispatchSlotV1<ProviderDispatchSecretBindingV1>;
	headers: ProviderDispatchSlotV1<readonly ProviderDispatchRequestOptionsHeaderBindingV1[]>;
	timeoutMs: ProviderDispatchSlotV1<number>;
	websocketConnectTimeoutMs: ProviderDispatchSlotV1<number>;
	maxRetries: ProviderDispatchSlotV1<number>;
	maxRetryDelayMs: ProviderDispatchSlotV1<number>;
	metadataDigest: ProviderDispatchSlotV1<string>;
	reasoning: ProviderDispatchSlotV1<"minimal" | "low" | "medium" | "high" | "xhigh" | "max">;
	thinkingBudgets: ProviderDispatchSlotV1<{
		minimal: ProviderDispatchSlotV1<number>;
		low: ProviderDispatchSlotV1<number>;
		medium: ProviderDispatchSlotV1<number>;
		high: ProviderDispatchSlotV1<number>;
	}>;
	credentialBindingDigest: string;
}

interface ProviderDispatchLogicalInvocationBasisV1 {
	protocol: "pi-provider-logical-invocation-basis/v1";
	modelDigest: string;
	credentialBindingDigest: string;
	systemPromptDigest: string;
	orderedMessageDigests: readonly string[];
	orderedToolDigests: readonly string[];
	optionsDigest: string;
	exactCounterBindingDigest: ProviderDispatchSlotV1<string>;
}

type ProviderDispatchAttemptScopeV1 =
	| {
			protocol: "pi-provider-dispatch-attempt-scope/v1";
			kind: "agent_run";
			operationId: string;
			requestId: string;
			attemptId: string;
			generationId: string;
	  }
	| {
			protocol: "pi-provider-dispatch-attempt-scope/v1";
			kind: "bounded_one_shot";
			operationId: string;
			requestId: string;
			attemptId: string;
			generationId: string;
	  };

interface ProviderDispatchBudgetPolicyBasisV1 {
	protocol: "pi-provider-dispatch-budget-policy-basis/v1";
	modelRef: string;
	inputTokenLimit: number;
	outputTokenLimit: number;
	timeoutMs: number;
	costLimitMicros: number;
	costCurrency: string;
}

interface PreparedSimpleExactInputCounterIdentityV1 {
	protocol: "pi-prepared-simple-exact-input-counter-identity/v1";
	counterId: string;
	counterVersion: string;
	tokenizerId: string;
	tokenizerVersion: string;
	wrapperPolicyId: string;
	wrapperPolicyVersion: string;
}

interface PreparedSimpleExactInputProjectionV1 {
	protocol: "pi-prepared-simple-exact-input-projection/v1";
	model: {
		id: string;
		name: string;
		api: string;
		provider: string;
		reasoning: boolean;
		thinkingLevelMap: PreparedSimpleExactCountSlotV1<Readonly<Record<string, string | null>>>;
		input: readonly ("text" | "image")[];
		contextWindow: number;
		maxTokens: number;
		compat: PreparedSimpleExactCountSlotV1<Readonly<Record<string, unknown>>>;
	};
	context: Context;
	options: {
		temperature: PreparedSimpleExactCountSlotV1<number>;
		maxTokens: PreparedSimpleExactCountSlotV1<number>;
		cacheRetention: PreparedSimpleExactCountSlotV1<"none" | "short" | "long">;
		metadata: PreparedSimpleExactCountSlotV1<Readonly<Record<string, unknown>>>;
		reasoning: PreparedSimpleExactCountSlotV1<"minimal" | "low" | "medium" | "high" | "xhigh" | "max">;
		thinkingBudgets: PreparedSimpleExactCountSlotV1<Readonly<Record<string, number>>>;
	};
}

interface PreparedSimpleExactInputCounterResolverV1 {
	create(
		projection: PreparedSimpleExactInputProjectionV1,
	): PreparedSimpleExactCountSlotV1<PreparedSimpleExactInputCounterV1>;
}

interface ProviderDispatchExactInputCounterBindingBasisV1 {
	protocol: "pi-provider-dispatch-exact-input-counter-binding-basis/v1";
	modelDigest: string;
	counterIdentity: PreparedSimpleExactInputCounterIdentityV1;
}

/** A3.2-private frozen projection constructed from one detached prepared value. */
interface ProviderDispatchPreparedExactInputCounterProjectionV1 {
	protocol: "pi-provider-dispatch-prepared-exact-input-counter-projection/v1";
	modelBasis: ProviderDispatchModelBasisV1;
	modelDigest: string;
	counterIdentity: PreparedSimpleExactInputCounterIdentityV1;
	counterBindingDigest: string;
}

type PreparedSimpleExactCountSlotV1<T> =
	| { presence: "absent" }
	| { presence: "present"; value: T };

interface PreparedSimpleExactInputCountRequestV1 {
	protocol: "pi-prepared-simple-exact-input-count-request/v1";
	logicalInvocationDigest: string;
	modelDigest: string;
	counterBindingDigest: string;
	minimumOutputProbe: PreparedSimpleExactCountSlotV1<{
		candidateJsonText: string;
		candidateTextDigest: string;
	}>;
}

interface PreparedSimpleExactInputCountV1 {
	protocol: "pi-prepared-simple-exact-input-count/v1";
	logicalInvocationDigest: string;
	modelDigest: string;
	counterBindingDigest: string;
	counterIdentity: PreparedSimpleExactInputCounterIdentityV1;
	inputTokenCount: number;
	minimumOutput: PreparedSimpleExactCountSlotV1<{
		candidateTextDigest: string;
		outputTokenCount: number;
	}>;
}

type PreparedSimpleExactInputCountResultV1 =
	| { kind: "exact"; count: PreparedSimpleExactInputCountV1 }
	| { kind: "unsupported" }
	| { kind: "unavailable"; code: "counter_unavailable" }
	| { kind: "invalid"; code: "counter_input_invalid" };

type PreparedSimpleExactInputCountRevalidationV1 =
	| { kind: "exact" }
	| { kind: "stale" }
	| { kind: "unknown" }
	| { kind: "invalid" };

interface PreparedSimpleExactInputCounterV1 {
	readonly identity: PreparedSimpleExactInputCounterIdentityV1;
	count(
		request: PreparedSimpleExactInputCountRequestV1,
	): Promise<PreparedSimpleExactInputCountResultV1>;
	revalidate(
		count: PreparedSimpleExactInputCountV1,
	): Promise<PreparedSimpleExactInputCountRevalidationV1>;
}

interface PreparedSimpleInvocation {
	/** Pi-owned capability over this invocation's detached resolved snapshot. */
	readonly exactInputCounter: PreparedSimpleExactCountSlotV1<PreparedSimpleExactInputCounterV1>;
}

interface CreateModelsOptions {
	/** Optional local resolver; absence produces an unsupported exact-counter slot. */
	exactInputCounterResolver?: PreparedSimpleExactInputCounterResolverV1;
}

interface ProviderDispatchExactInputCountEvidenceV1 {
	protocol: "pi-provider-dispatch-exact-input-count-evidence/v1";
	logicalInvocationDigest: string;
	modelDigest: string;
	counterIdentity: PreparedSimpleExactInputCounterIdentityV1;
	counterBindingDigest: string;
	inputTokenCount: number;
	minimumOutput: ProviderDispatchSlotV1<{
		candidateTextDigest: string;
		outputTokenCount: number;
	}>;
	evidenceDigest: string;
}

type ProviderDispatchBudgetRequestV1 =
	| {
			protocol: "pi-provider-dispatch-budget-request/v1";
			mode: "trusted_count";
			budgetBasis: ProviderDispatchBudgetBasisV1;
	  }
	| {
			protocol: "pi-provider-dispatch-budget-request/v1";
			mode: "exact_required";
			policyBasis: ProviderDispatchBudgetPolicyBasisV1;
			expectedCounterIdentity: PreparedSimpleExactInputCounterIdentityV1;
			minimumOutputProbe: ProviderDispatchSlotV1<{
				candidateJsonText: string;
				candidateTextDigest: string;
			}>;
	  };

interface ProviderDispatchBudgetBasisV1 {
	protocol: "pi-provider-dispatch-budget-basis/v1";
	modelRef: string;
	inputTokenCount: number;
	inputTokenLimit: number;
	outputTokenLimit: number;
	timeoutMs: number;
	costLimitMicros: number;
	costCurrency: string;
	exactInputCountEvidence: ProviderDispatchSlotV1<ProviderDispatchExactInputCountEvidenceV1>;
}

interface ProviderDispatchApplicationBindingBasisV1 {
	protocol: "pi-provider-application-binding-basis/v1";
	binding: ProviderDispatchCanonicalJsonV1;
}

interface ProviderDispatchDisclosureDecisionBasisV1 {
	protocol: "pi-provider-disclosure-decision-basis/v1";
	decision: ProviderDispatchCanonicalJsonV1;
}

interface ProviderDispatchArtifactV1 {
	protocol: "pi-provider-dispatch-artifact/v1";
	dispatchId: string;
	attemptScope: ProviderDispatchAttemptScopeV1;
	expectedLeafId: string | null;
	applicationBindingDigest: string;
	modelDigest: string;
	credentialBindingDigest: string;
	systemPromptDigest: string;
	orderedMessageDigests: readonly string[];
	orderedToolDigests: readonly string[];
	optionsDigest: string;
	budgetDigest: string;
	logicalInvocationDigest: string;
}

interface ProviderDispatchReceiptV1 {
	protocol: "pi-provider-dispatch-receipt/v1";
	receiptId: string;
	dispatchId: string;
	attemptScope: ProviderDispatchAttemptScopeV1;
	expectedLeafId: string | null;
	applicationBindingDigest: string;
	artifactDigest: string;
	modelDigest: string;
	credentialBindingDigest: string;
	systemPromptDigest: string;
	orderedMessageDigests: readonly string[];
	orderedToolDigests: readonly string[];
	optionsDigest: string;
	budgetDigest: string;
	logicalInvocationDigest: string;
	disclosureDecisionDigest: string;
	orderedPriorControlEntryDigests: readonly string[];
	terminalEntryId: string;
	applicationReceiptMaterialDigest: string;
	opaqueMaterialRetention: "retained" | "digest_only";
	dispatchKnowledge: "may_have_dispatched";
	receiptDigest: string;
	authenticity: ProviderDispatchAuthenticityV1;
}

interface ProviderDispatchAuthenticityV1 {
	algorithm: "HMAC-SHA-256";
	keyId: string;
	signedPayloadDigest: string;
	macBase64Url: string;
}

interface ProviderDispatchSecretBinder {
	bind(input: {
		readonly domain: ProviderDispatchSecretDomainV1;
		readonly fieldName: string;
		readonly valueUtf8: Uint8Array;
	}): Promise<ProviderDispatchSecretBindingV1>;
}

interface ProviderDispatchSafePreparedFactsV1 {
	protocol: "pi-provider-dispatch-safe-prepared-facts/v1";
	attemptScope: ProviderDispatchAttemptScopeV1;
	model: {
		id: string;
		name: string;
		api: string;
		provider: string;
		reasoning: boolean;
		input: readonly ("text" | "image")[];
		cost: {
			input: number;
			output: number;
			cacheRead: number;
			cacheWrite: number;
			tiers: ProviderDispatchSlotV1<readonly {
				input: number;
				output: number;
				cacheRead: number;
				cacheWrite: number;
				inputTokensAbove: number;
			}[]>;
		};
		contextWindow: number;
		maxTokens: number;
	};
	budgetBasis: ProviderDispatchBudgetBasisV1;
	budgetDigest: string;
	effectiveProviderMaxOutputTokens: number;
	effectiveProviderTimeoutMs: number;
	modelDigest: string;
	credentialBindingDigest: string;
	systemPromptDigest: string;
	orderedMessageDigests: readonly string[];
	orderedToolDigests: readonly string[];
	optionsDigest: string;
}

interface ProviderDispatchApplicationAuthorizationV1 {
	disclosureDecisionBasis: ProviderDispatchDisclosureDecisionBasisV1;
	priorEntryDrafts: readonly {
		customType: string;
		data: ProviderDispatchCanonicalJsonV1;
	}[];
	opaqueMaterialRetention: "retained" | "digest_only";
}

type ProviderDispatchApplicationDenialCodeV1 =
	| "policy_denied"
	| "unsupported_model"
	| "budget_unavailable";

type ProviderDispatchApplicationUnavailableCodeV1 =
	| "timeout"
	| "temporarily_unavailable";

type ProviderDispatchApplicationPortFailureV1 =
	| {
			kind: "denied";
			code: ProviderDispatchApplicationDenialCodeV1;
	  }
	| {
			kind: "unavailable";
			code: ProviderDispatchApplicationUnavailableCodeV1;
	  };

type ProviderDispatchApplicationBindingResultV1 =
	| {
			kind: "bound";
			applicationBindingBasis: ProviderDispatchApplicationBindingBasisV1;
	  }
	| ProviderDispatchApplicationPortFailureV1;

type ProviderDispatchApplicationAuthorizationResultV1 =
	| {
			kind: "authorized";
			authorization: ProviderDispatchApplicationAuthorizationV1;
	  }
	| ProviderDispatchApplicationPortFailureV1;

type ProviderDispatchApplicationTerminalMaterialResultV1 =
	| {
			kind: "created";
			material: ProviderDispatchCanonicalJsonV1;
	  }
	| ProviderDispatchApplicationPortFailureV1;

interface ProviderDispatchApplicationAuthority {
	bindBeforeArtifact(input: {
		readonly dispatchId: string;
		readonly attemptScope: ProviderDispatchAttemptScopeV1;
		readonly safePreparedFacts: ProviderDispatchSafePreparedFactsV1;
	}): Promise<ProviderDispatchApplicationBindingResultV1>;
	authorizeAfterArtifact(input: {
		readonly artifact: ProviderDispatchArtifactV1;
		readonly artifactDigest: string;
		readonly applicationBindingBasis: ProviderDispatchApplicationBindingBasisV1;
	}): Promise<ProviderDispatchApplicationAuthorizationResultV1>;
	createTerminalMaterialAfterPreview(input: {
		readonly artifact: ProviderDispatchArtifactV1;
		readonly artifactDigest: string;
		readonly applicationBindingBasis: ProviderDispatchApplicationBindingBasisV1;
		readonly disclosureDecisionBasis: ProviderDispatchDisclosureDecisionBasisV1;
		readonly orderedPriorControlEntryDigests: readonly string[];
		readonly terminalEntryId: string;
	}): Promise<ProviderDispatchApplicationTerminalMaterialResultV1>;
}

interface ProviderDispatchApplicationReceiptAuthenticator {
	sign(input: {
		readonly receiptWithoutAuthenticity: Omit<ProviderDispatchReceiptV1, "authenticity">;
	}): Promise<ProviderDispatchAuthenticityV1>;
	verify(input: {
		readonly receipt: ProviderDispatchReceiptV1;
		readonly opaqueReceiptMaterial?: ProviderDispatchCanonicalJsonV1;
	}): Promise<void>;
}

interface ProviderDispatchTerminalEntryDataV1 {
	protocol: "pi-provider-dispatch-terminal-entry/v1";
	receipt: ProviderDispatchReceiptV1;
	opaqueMaterial:
		| {
				retention: "retained";
				materialDigest: string;
				material: ProviderDispatchCanonicalJsonV1;
		  }
		| { retention: "digest_only"; materialDigest: string };
}

/** Core-private and not exported from packages/agent. */
declare const providerDispatchPrivateAttemptTokenBrand: unique symbol;
type ProviderDispatchPrivateAttemptTokenV1 = {
	readonly [providerDispatchPrivateAttemptTokenBrand]: never;
};

interface ProviderDispatchReceiptReferenceV1 {
	protocol: "pi-provider-dispatch-receipt-reference/v1";
	dispatchId: string;
	attemptScope: ProviderDispatchAttemptScopeV1;
	expectedLeafId: string | null;
	decisionExpectedLeafId: string;
	receiptDigest: string;
	terminalEntryId: string;
	receiptDisposition: "committed" | "exact_present" | "acknowledgement_unknown";
}

type ProviderDispatchPresentReceiptReferenceV1 = Omit<
	ProviderDispatchReceiptReferenceV1,
	"receiptDisposition"
> & {
	receiptDisposition: "committed" | "exact_present";
};

type ProviderDispatchAcknowledgementUnknownReferenceV1 = Omit<
	ProviderDispatchReceiptReferenceV1,
	"receiptDisposition"
> & {
	receiptDisposition: "acknowledgement_unknown";
};

interface ProviderDispatchStartedBudgetEvidenceV1 {
	protocol: "pi-provider-dispatch-started-budget-evidence/v1";
	modelRef: string;
	modelDigest: string;
	logicalInvocationDigest: string;
	budgetDigest: string;
	exactInputCountEvidence: ProviderDispatchSlotV1<ProviderDispatchExactInputCountEvidenceV1>;
}

type ProviderDispatchStartedEvidenceV1 = ProviderDispatchPresentReceiptReferenceV1 & {
	/** Closed non-secret facts copied from the exact retained receipt basis. */
	budgetEvidence: ProviderDispatchStartedBudgetEvidenceV1;
};

type ProviderDispatchPreReceiptCodeV1 =
	| "invalid_request"
	| "exact_input_count_unsupported"
	| "exact_input_count_unavailable"
	| "exact_input_count_invalid"
	| "exact_input_budget_exceeded"
	| "application_denied"
	| "application_invalid"
	| "application_unavailable"
	| "unsupported_model"
	| "budget_unavailable"
	| "control_conflict"
	| "control_unavailable"
	| "cancelled"
	| "generation_retired"
	| "dispatch_registry_exhausted"
	| "identity_conflict";

type ProviderDispatchPostReceiptCodeV1 =
	| "cancelled"
	| "generation_retired"
	| "cursor_changed";

type ProviderDispatchNotStartedV1 =
	| {
			kind: "not_started";
			stage: "pre_receipt";
			code: ProviderDispatchPreReceiptCodeV1;
			receiptState: "none";
			durableKnowledge: "not_dispatched";
	  }
	| {
			kind: "not_started";
			stage: "ack_unknown";
			code: "acknowledgement_unresolved";
			receiptState: "unknown";
			durableKnowledge: "unknown";
			receiptReference: ProviderDispatchAcknowledgementUnknownReferenceV1;
	  }
	| {
			kind: "not_started";
			stage: "ack_absent";
			code: "acknowledgement_resolved_absent";
			receiptState: "none";
			durableKnowledge: "not_dispatched";
	  }
	| {
			kind: "not_started";
			stage: "untrusted_present";
			code: "receipt_untrusted";
			receiptState: "untrusted";
			durableKnowledge: "unknown";
			receiptReference: ProviderDispatchPresentReceiptReferenceV1;
	  }
	| {
			kind: "not_started";
			stage: "post_receipt";
			code: ProviderDispatchPostReceiptCodeV1;
			receiptState: "trusted_present";
			durableKnowledge: "may_have_dispatched";
			receiptReference: ProviderDispatchStartedEvidenceV1;
	  }
	| {
			kind: "not_started";
			stage: "duplicate_in_flight";
			code: "duplicate_in_flight";
			receiptState: "none";
			durableKnowledge: "not_dispatched";
	  }
	| {
			kind: "not_started";
			stage: "duplicate_in_flight";
			code: "duplicate_in_flight";
			receiptState: "unknown";
			durableKnowledge: "unknown";
			receiptReference: ProviderDispatchAcknowledgementUnknownReferenceV1;
	  }
	| {
			kind: "not_started";
			stage: "duplicate_in_flight";
			code: "duplicate_in_flight";
			receiptState: "untrusted";
			durableKnowledge: "unknown";
			receiptReference: ProviderDispatchPresentReceiptReferenceV1;
	  }
	| {
			kind: "not_started";
			stage: "duplicate_in_flight";
			code: "duplicate_in_flight";
			receiptState: "trusted_present";
			durableKnowledge: "may_have_dispatched";
			receiptReference: ProviderDispatchStartedEvidenceV1;
	  }
	| {
			kind: "not_started";
			stage: "duplicate_terminal";
			code: "duplicate_terminal";
			receiptState: "none";
			durableKnowledge: "not_dispatched";
	  }
	| {
			kind: "not_started";
			stage: "duplicate_terminal";
			code: "duplicate_terminal";
			receiptState: "unknown";
			durableKnowledge: "unknown";
			receiptReference: ProviderDispatchAcknowledgementUnknownReferenceV1;
	  }
	| {
			kind: "not_started";
			stage: "duplicate_terminal";
			code: "duplicate_terminal";
			receiptState: "untrusted";
			durableKnowledge: "unknown";
			receiptReference: ProviderDispatchPresentReceiptReferenceV1;
	  }
	| {
			kind: "not_started";
			stage: "duplicate_terminal";
			code: "duplicate_terminal";
			receiptState: "trusted_present";
			durableKnowledge: "may_have_dispatched";
			receiptReference: ProviderDispatchStartedEvidenceV1;
	  };

type ProviderDispatchResultV1 =
	| {
			kind: "started";
			stream: AssistantMessageEventStream;
			evidence: ProviderDispatchStartedEvidenceV1;
	  }
	| ProviderDispatchNotStartedV1;

interface ProviderDispatchBoundedOneShotAttemptBindingV1 {
	protocol: "pi-provider-dispatch-bounded-one-shot-attempt-binding/v1";
	dispatchId: string;
	attemptScope: Extract<ProviderDispatchAttemptScopeV1, { kind: "bounded_one_shot" }>;
	expectedLeafId: string | null;
	model: Model<Api>;
	context: Context;
	options: SimpleStreamOptions;
	budgetRequest: ProviderDispatchBudgetRequestV1;
	signal: AbortSignal;
}

/** Public Pi capability returned already bound to one immutable one-shot attempt. */
interface ProviderDispatchBoundedOneShotAttemptV1 {
	dispatch(): Promise<ProviderDispatchResultV1>;
}

/** Public Pi frontend used only by a production-shaped bounded one-shot Adapter. */
interface ProviderDispatchBoundedOneShotFrontendV1 {
	bindAttempt(input: ProviderDispatchBoundedOneShotAttemptBindingV1): ProviderDispatchBoundedOneShotAttemptV1;
}

interface ProviderDispatchHarnessAttemptBindingV1 {
	protocol: "pi-provider-dispatch-harness-attempt-binding/v1";
	dispatchId: string;
	attemptScope: Extract<ProviderDispatchAttemptScopeV1, { kind: "agent_run" }>;
	budgetRequest: ProviderDispatchBudgetRequestV1;
}

interface ProviderDispatchHarnessAttemptSourceV1 {
	/** Claim exactly one immutable identity/budget request for the next final provider request. */
	claim(): Promise<ProviderDispatchHarnessAttemptBindingV1>;
}

interface ProviderDispatchHarnessOptionsV1 {
	runtime: ProviderDispatchRuntimeV1;
	attemptSource: ProviderDispatchHarnessAttemptSourceV1;
}

interface ProviderDispatchRuntimeOptionsV1 {
	models: Models;
	/** Already-leased existing Session; the runtime neither opens nor creates one. */
	session: Session;
	secretBinder: ProviderDispatchSecretBinder;
	applicationAuthority: ProviderDispatchApplicationAuthority;
	applicationReceiptAuthenticator: ProviderDispatchApplicationReceiptAuthenticator;
}

declare const providerDispatchRuntimeBrand: unique symbol;

/** Opaque public composition capability. Its private core is held in module-owned state. */
interface ProviderDispatchRuntimeV1 {
	readonly [providerDispatchRuntimeBrand]: never;
	readonly boundedOneShot: ProviderDispatchBoundedOneShotFrontendV1;
}

type ProviderDispatchRuntimeOpenResultV1 =
	| {
			kind: "opened";
			runtime: ProviderDispatchRuntimeV1;
	  }
	| {
			kind: "invalid_options";
	  }
	| {
			kind: "control_unavailable";
			code: "session_unavailable";
	  };

declare function openProviderDispatchRuntime(
	options: ProviderDispatchRuntimeOptionsV1,
): Promise<ProviderDispatchRuntimeOpenResultV1>;

interface AgentHarnessOptions {
	/** Opt into the protected Provider Dispatch path; absence retains ordinary Harness behavior. */
	providerDispatch?: ProviderDispatchHarnessOptionsV1;
}

/** Private core; both frontends mint its token and no caller receives it. */
interface ProviderDispatchPrivateTransactionV1 {
	dispatch(token: ProviderDispatchPrivateAttemptTokenV1): Promise<ProviderDispatchResultV1>;
}
```

Every provider-dispatch digest is the shared `piDigest` from 6.5.1; A3.2 introduces no second canonicalizer. The mapping is exhaustive: `modelDigest = piDigest(ProviderDispatchModelBasisV1)`; `authSourceDigest = piDigest(ProviderDispatchAuthSourceBasisV1)` when present; `credentialBindingDigest = piDigest(ProviderDispatchCredentialBasisV1)`; `systemPromptDigest = piDigest(ProviderDispatchSystemPromptBasisV1)`; each ordered message/tool digest hashes its complete indexed `ProviderDispatchMessageBasisV1`/`ProviderDispatchToolBasisV1`; `metadataDigest = piDigest(ProviderDispatchMetadataBasisV1)` when metadata is present; `optionsDigest = piDigest(ProviderDispatchOptionsBasisV1)`; `counterBindingDigest = piDigest(ProviderDispatchExactInputCounterBindingBasisV1)`; `logicalInvocationDigest = piDigest(ProviderDispatchLogicalInvocationBasisV1)`; `evidenceDigest = piDigest(the complete ProviderDispatchExactInputCountEvidenceV1 with evidenceDigest omitted)`; `budgetDigest = piDigest(ProviderDispatchBudgetBasisV1)`; `applicationBindingDigest = piDigest(ProviderDispatchApplicationBindingBasisV1)`; `artifactDigest = piDigest(ProviderDispatchArtifactV1)`; `disclosureDecisionDigest = piDigest(ProviderDispatchDisclosureDecisionBasisV1)`; each prior-control-entry digest is `piDigest(PiSessionEntryDigestBasisV1)`; `applicationReceiptMaterialDigest = piDigest({ protocol: "pi-provider-application-receipt-material-basis/v1", material })`; `receiptDigest = piDigest(the complete ProviderDispatchReceiptV1 with receiptDigest and authenticity omitted)`; `signedPayloadDigest = piDigest(the complete ProviderDispatchReceiptV1 with authenticity omitted)`; and A4 `batchDigest = piDigest({ protocol: "pi-session-control-batch-basis/v1", sessionId, expectedLeafId, orderedEntryDigests, terminalEntryId })`. For `trusted_count`, `exactCounterBindingDigest` is absent. For `exact_required`, A3.2 first hashes the complete actual detached `ProviderDispatchModelBasisV1`, combines that `modelDigest` with the prepared counter projection's complete identity in `ProviderDispatchExactInputCounterBindingBasisV1`, and places the resulting present `counterBindingDigest` in `ProviderDispatchLogicalInvocationBasisV1`. The logical digest therefore changes when any counter, tokenizer, or wrapper-policy identity/version changes. It remains budget-independent: the counter binding does not contain the logical digest or count, so the logical digest exists before counting and the final budget can bind it without a digest cycle. These are exact RFC 8785 JCS bytes under 6.5.1, not descriptive pseudo-digests. Pi snapshots every frontend- and application-returned basis immediately, holds the basis value until terminal sealing, and recomputes its digest itself. A caller-supplied digest never substitutes for the basis.

The shared canonical helper takes an explicit caller-owned input limit without changing its JCS or SHA-256 semantics. A3.2 may use the section-6.6 transient request-basis limit while hashing Model/Context inputs that never enter A4. A4 preparation, prior-entry hashing, terminal sealing, receipt-envelope persistence, and lookup retain A4's default 1 MiB canonical-entry limit; A3.2 does not widen a persisted Session entry or route a raw provider body into A4.

`ProviderDispatchAttemptScopeV1` is the only provider-dispatch attempt identity. `operationId` means Agent Run ID for `agent_run` and Workspace Turn ID for `bounded_one_shot`; `requestId` means Agent Turn/request ID for `agent_run` and Task Understanding request ID for `bounded_one_shot`. Every identifier is non-empty, 1-128 ASCII characters, and matches `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`. The two variants are semantically disjoint even when every string is byte-identical. No artifact, receipt, registry key, cursor, permit, result, or application call may carry a second run-only identity tuple.

`ProviderDispatchBudgetRequestV1` separates the pre-prepare policy request from the final closed `ProviderDispatchBudgetBasisV1`, avoiding a count/budget digest cycle. Existing protected Harness behavior uses `trusted_count` and supplies its current complete basis with `exactInputCountEvidence = absent`; no exact counter is invoked and ordinary unprotected Harness behavior is unchanged. `exact_required` is opt-in and supplies only the policy basis, the complete expected counter/tokenizer/wrapper identity, and a transient minimum-output probe. It does not and cannot supply `modelDigest` or `counterBindingDigest`. The private core constructs those actual digests and the final basis only after A3.1 preparation and exact counting; that basis carries `exactInputCountEvidence = present` and the same limits. Neither branch changes the public `AgentHarness` prompt/result behavior.

`packages/ai` owns `PreparedSimpleExactInputCounterV1` at the shared `PreparedSimpleInvocation` seam. A present prepared counter capability exposes its immutable counter/tokenizer/wrapper-policy identity and versions before `count`; absence is `unsupported`. A3.2 combines that identity with its retained complete model basis in one private frozen `ProviderDispatchPreparedExactInputCounterProjectionV1` before logical-invocation hashing. Exact model identity is not a new version string: it is the projection's `modelDigest` of the complete actual detached `ProviderDispatchModelBasisV1`, including every existing model coordinate and field defined above. The configured Adapter is selected for that detached model and its own counter/tokenizer/wrapper identities. It counts the same detached finalized logical provider input used by `PreparedSimpleInvocation.start()`: system placement, ordered messages and every content variant, ordered public tools and their complete JSON-visible schemas, token-affecting options, image accounting, and every implicit role/content/tool wrapper named by the wrapper policy. An unknown model-visible field, option, content variant, image rule, or wrapper is `invalid`; no approximation or character heuristic is permitted. The minimum valid output candidate is counted separately under the same tokenizer/output-wrapper policy rather than subtracted from the input count.

`packages/ai` constructs a separate recursively detached `PreparedSimpleExactInputProjectionV1` from A3.1's auth-resolved prepared model/context/options snapshot. `CreateModelsOptions.exactInputCounterResolver` is the sole configuration seam: after auth resolution, `Models.prepareSimple` passes the resolver only that projection and snapshots the returned counter identity/capability into `PreparedSimpleInvocation`; absence of the resolver or an absent slot is `unsupported`. The projection contains the detached model coordinates/wrapper inputs, exact provider-neutral Context with the already-projected public Tools, and only the listed token-affecting safe options. It structurally excludes Model base URL/headers/cost, request API key/environment/headers/session ID, transport/timeouts/retries, signal, callbacks, credential store, auth source, Provider Adapter, and `start()` handle. Unknown projection members or unsupported current content/options make the counter result `invalid`; neither resolver nor counter may infer omitted request fields.

The resident counter closes only over that isolated projection. Its later `count` call receives the public logical/model/binding digests and transient minimum-output text, but no API key, environment value, header value, base URL, credential store, auth callback, Session, Harness, repository, signal, provider `start()` handle, or application authority. The AI-owned types do not import A3.2, Session, or Harness types. Resolver creation, `count`, and `revalidate` perform no network operation, Provider Adapter/lazy API entry, Session/Harness creation, retry, or second lifecycle. Caller mutation after preparation cannot change projection, identity, count, or revalidation. Real-provider counter registration and activation are deferred; design and focused acceptance use deterministic fake and production-shaped local resolver/counter Adapters over the same fixtures.

The exact result is closed as `exact | unsupported | unavailable | invalid`. For `exact`, A3.2 recomputes one `counterBindingDigest` from the private prepared projection's retained complete model basis plus resident counter identity before logical-invocation hashing. The projection, count request, exact count, A3.2 evidence, application-safe budget facts, and revalidation all carry that byte-identical value; A3.2 rejects any echo or identity mismatch. It verifies the logical/model/probe digests and safe-integer counts, compares input and separately counted minimum output against their limits, and constructs the evidence itself. It then calls the same resident counter's `revalidate` before application authority or A4 and recomputes the projection, binding basis, and logical invocation again before permit consumption. `unsupported` maps to `exact_input_count_unsupported`; unavailable or unknown maps to `exact_input_count_unavailable`; invalid, mismatch, or stale maps to `exact_input_count_invalid`; either over-limit count maps to `exact_input_budget_exceeded`. Every case has zero A4 append and zero Provider Adapter start. No caller-supplied count, identity, binding, or evidence digest can substitute for Pi's retained values.

`ProviderDispatchBudgetBasisV1` is closed non-secret policy evidence, not a billing claim. `inputTokenCount` is an integer in `[0, 10_000_000]`; input/output limits are integers in `[1, 10_000_000]`; timeout is an integer in `[1, 86_400_000]`; and cost limit is integer micros in `[0, 1_000_000_000_000]`. Input count does not exceed input limit; currency is exactly three uppercase ASCII letters; and `modelRef` is 1-128 ASCII characters matching `^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$`. A frontend may impose lower owning-contract limits, and Task Understanding retains its exact 8,192-token/30,000-ms/100,000-micro maxima. The prepared request's effective output cap is `requestOptions.maxTokens` when present and otherwise the prepared Model `maxTokens`; it must not exceed either the prepared Model `maxTokens` or `budgetBasis.outputTokenLimit`. Prepared `requestOptions.timeoutMs` must be present, equal `budgetBasis.timeoutMs`, and be the exact timeout sent to the Adapter. The application authority receives the complete basis plus non-secret prepared Model identity/rates/capacity and independently checks `modelRef`, counter/tokenizer/wrapper provenance when evidence is present, currency, and worst-case cost policy. A mismatch is `application_denied` before A4. The generic receipt proves the bound budget, exact-count evidence when requested, and model facts, not actual provider usage or final charge.

Each `ProviderDispatchMessageBasisV1.position` and `ProviderDispatchToolBasisV1.position` is unique, contiguous, zero-based, and equals the element's index in the corresponding prepared ordered array. The ordered digest arrays contain those digests at the same indices. A duplicate, gap, negative position, reordered basis, or mismatch between position and array order is `invalid_request` before application authority.

`ProviderDispatchSecretBinder` is Pi/runtime-composition-owned infrastructure, not an application or Workspace port. Only the transaction and this binder may see prepared raw API key, environment values, header values, session ID, or resolved base URL. For each value it receives the transient tuple `(domain, fieldName, UTF8(value))` and returns `ProviderDispatchSecretBindingV1`. The MAC input is exactly `UTF8("pi-provider-secret-binding/v1") || 0x00 || UTF8(domain) || 0x00 || uint64be(UTF8(fieldName).length) || UTF8(fieldName) || uint64be(UTF8(value).length) || UTF8(value)`. `uint64be` is an unsigned 64-bit big-endian byte length. `macBase64Url` is unpadded base64url of HMAC-SHA-256 under `keyId`; Pi checks domain, field name, byte length, and key policy. The binder never returns or persists the value.

Field names are fixed, not caller-selected: API key uses domain `request.api_key` and field name `apiKey`; session ID uses `request.session_id` and `sessionId`; resolved base URL uses `model.resolved_base_url` and `baseUrl`; each environment value uses `request.environment_value` and its exact environment key; each model/request-options header value uses its layer domain and exact `originalName`. Header bases separately include `asciiLowerName`, computed only by ASCII `A-Z -> a-z`. Each header layer rejects two names with the same `asciiLowerName`, then sorts by `asciiLowerName` ascending. Environment rejects duplicate exact keys and sorts names by the RFC 8785/ECMAScript UTF-16 code-unit comparison used for object property sorting. Base URL never appears in `ProviderDispatchModelBasisV1` as plaintext. `authSource` is a non-secret diagnostic label, but the transaction exposes and persists only `authSourceDigest`; it is neither credential authority nor a revision. Application authority sees only `ProviderDispatchSafePreparedFactsV1` and the non-secret artifact.

A3.1 auth resolution precedes canonicalization. Its current merge rule is normative for v1: explicit `options.apiKey` wins over auth-produced `apiKey`; auth headers are merged first and explicit option headers replace the same exact case-sensitive key; resolved-auth environment is merged first and explicit option environment replaces the same exact key; an auth-produced base URL replaces the requested model base URL. The final prepared layers are then collision-checked and sorted as above. Exact-case replacement is not permission for an ASCII-case alias: aliases that collide after `asciiLowerName` fail. Acceptance must cover auth-only, explicit-only, exact-key override, case-collision rejection, and absence versus present-null header suppression without exposing raw values.

Application authority is staged. Before artifact construction, `bindBeforeArtifact` receives the exact neutral scope and a recursively immutable `ProviderDispatchSafePreparedFactsV1`. That value contains no base URL, API key, environment value, header value, Session ID, system prompt, message, tool schema, metadata body, or prepared/start handle; it contains the complete non-secret prepared Model coordinates/rates/capacities, closed budget basis/effective output/timeout, and Pi-computed request digests. The authority must compare its configured `modelRef`, tokenizer/policy binding, timeout, token bounds, cost currency, and cost bound before returning `bound` with the canonical application binding basis. Pi snapshots that basis and computes `applicationBindingDigest`. After the artifact exists, `authorizeAfterArtifact` receives only the artifact and retained binding basis and returns `authorized` with one canonical Disclosure Decision basis, zero or more canonical prior-entry drafts, and the exact opaque-material retention choice. Pi snapshots the decision/drafts and computes their digests. Only after A4 exposes final materialized prior entries and the reserved terminal ID may `createTerminalMaterialAfterPreview` return `created` with the opaque application receipt material. Pi computes its digest, constructs the generic receipt/envelope itself, and asks the separately configured application authenticator to sign and verify the exact generic receipt. At every authority stage, `denied(unsupported_model)` maps to the same pre-receipt code, `denied(budget_unavailable)` maps to the same pre-receipt code, `denied(policy_denied)` maps to `application_denied`, and either closed `unavailable` code maps to `application_unavailable`. A thrown/rejected call, an unknown result kind/member/code, or an invalid/over-bound success body maps to `application_invalid`. None appends or starts, and no stage is retried. Neither application port supplies Pi-computed digests, Session identity, commit outcome, permit, or Adapter authority.

The application authenticator payload bytes are exactly `UTF8(RFC8785_JCS(the complete ProviderDispatchReceiptV1 with authenticity omitted))`. `signedPayloadDigest` is `piDigest` of that same basis. `macBase64Url` is the unpadded base64url encoding of `HMAC-SHA-256(application-authenticator key, those exact payload bytes)`; it is not an HMAC over the digest string or decoded digest bytes. Pi independently recomputes every generic field, basis digest, material digest, complete prior-entry digest, receipt digest, signed-payload digest, and MAC comparison before sealing. `ProviderDispatchTerminalEntryDataV1` is the exact `data` of the physically last Session `custom` entry with `customType = "pi_provider_dispatch_terminal_v1"`.

Runtime composition is once per already-leased Session runtime through asynchronous `openProviderDispatchRuntime`. It receives one `Models` object (and therefore one selected Provider/Auth resolver path), one existing `Session` whose A4 and current-leaf operations remain module-private, one `ProviderDispatchSecretBinder`, one `ProviderDispatchApplicationAuthority`, and one `ProviderDispatchApplicationReceiptAuthenticator`. Before returning `opened`, it validates the closed options, awaits the actual `Session.getLeafId()`, validates that leaf, and initializes its private cursor to that exact value. Invalid options return `invalid_options`; an expected Session read failure returns `control_unavailable(session_unavailable)`; neither creates a runtime, core, registry, permit, or frontend, and only an impossible programmer invariant throws. On success it snapshots the dependency references, creates the generation registry/prepared-value store/cursor/permit issuer itself, constructs exactly one `ProviderDispatchPrivateTransactionV1`, stores the core in module-owned state keyed by the unforgeable runtime object, and issues the Harness-private frontend plus `ProviderDispatchBoundedOneShotFrontendV1` from that core. The runtime exposes no Session or dependency getter. Protected `AgentHarnessOptions` receives this opaque runtime and must compare its captured `models` and `session` object identities with the Harness options before accepting it; mismatch is `invalid_argument` before a Turn. Dependency identity is captured once and immutable: neither frontend nor an attempt can replace `Models`, Provider/Auth, binder, authority/authenticator, Session/control/cursor, registry, prepared-value store, or permit issuer. A runtime cannot combine frontends from different compositions. Same-`dispatchId` attempts presented through different frontends therefore meet the same registry and conflict rules; that public collision is the executable proof that the two frontends do not hide two transactions.

Protected Harness mode is enabled only by `AgentHarnessOptions.providerDispatch`. After the final `before_provider_request` hook and requalification, Harness calls `attemptSource.claim()` exactly once for that provider request. The source receives no Model, Context, options, Session, leaf, prepared facts, credential, or callback and can return only the closed Agent-Run scope/dispatch ID/budget basis. Harness snapshots that return, captures `expectedLeafId` and the loop signal itself, binds its final owned model/context/options, and mints the private token. Empty/unknown/drifting fields or source rejection map to pre-receipt `application_invalid`; cancellation maps to `cancelled`; a runtime/Models/Session identity mismatch is constructor-time `invalid_argument`; and a budget basis that the application cannot admit against later safe prepared facts maps to pre-receipt `budget_unavailable`. Each fails before Adapter start, and every case except the later prepared-fact comparison occurs before A3.1 preparation. No second claim or implicit retry occurs. When `providerDispatch` is absent, the current ordinary `Models.streamSimple()` path and payload hook semantics remain unchanged.

`ProviderDispatchBoundedOneShotFrontendV1.bindAttempt` is synchronous. Before returning, it snapshots and validates every enumerable input field, compares `expectedLeafId` with the initialized private leased-Session cursor, binds the exact neutral scope to one resident generation object, and creates one unique owned model/context/options/budget-request group. Every expected bind failure still returns a no-getter, already-terminated capability: invalid/unknown/over-bound input returns pre-receipt `application_invalid`, stale `expectedLeafId` returns `control_conflict`, and a pre-aborted signal returns `cancelled`. Its first and every later `dispatch()` returns that same frozen closed result with zero registry, prepare, counter, binder, authority, A4, permit, or Adapter work. `bindAttempt` throws only for an impossible Pi-owned programmer invariant. A successful returned capability likewise exposes only no-argument `dispatch()`; it has no getter, prepared handle, counter, Session/control handle, lifecycle mutator, or replacement input. The production Task Understanding invocation Adapter alone holds this capability. Phase A and `TaskUnderstandingInvocationPort` see only their Workspace invocation/result types and never receive this frontend, its binding input, or any Pi Session authority. The Adapter selects Model/context/options from trusted configuration and the validated invocation; Workspace input cannot provide a credential, Provider, auth override, header, base URL, `Models`, counter, or `start()` handle.

The one-shot binding's `options.signal` must be present and object-identical to `binding.signal`; Harness likewise binds its loop signal by identity. A pre-aborted signal follows the already-terminated-capability rule above, including identical repeated `cancelled` results without registry insertion. An abort after a successful bind permanently retires that resident one-shot generation; the core checks it before preparation, after every await, before commit, before cursor advance, and atomically with permit consumption. If abort wins after trusted receipt presence, the result is the corresponding trusted post-receipt cancellation reference. The non-mutating `onResponse` observer is retained by identity and generation-fenced; `onPayload`, custom transports/functions, or a different signal identity reject before application authority.

When `opaqueMaterial.retention` is `retained`, reopen may recompute its digest and the application verifier may re-evaluate receipt trust/eligibility under its current key and policy. When it is `digest_only`, the omitted body cannot be reconstructed, semantically revalidated, or used for later application eligibility; the remaining authenticated generic envelope is only `may_have_dispatched` audit evidence. A digest is not authenticity and is never called a re-verifiable application receipt. If reopen or later application eligibility requires the opaque body, the application decision must select `retained`; loss of a required retained body fails closed.

The call order is strict:

1. The selected frontend completes its final request work. Harness completes context policy, system-prompt rendering, message conversion/order, public tool projection/order, aggregate request policy, and the final aggregate `before_provider_request` hook. The bounded one-shot Adapter completes trusted invocation validation, exact one-shot prompt/message construction, zero-tool projection, and exact budget-policy/minimum-output-probe construction without creating a Harness, Session, Tool registry, queue, or Agent Run. A `trusted_count` Harness request retains its existing caller-supplied count; neither frontend performs an `exact_required` count before preparation.
2. Only after step 1, the frontend mints one core-private attempt token. Harness binds the Agent Run generation object identity, private cursor at Session leaf `L`, active-save-point/provider-qualification leaves, selected/default entry identities, and its unique owned request group. `bindAttempt` binds the one-shot generation object identity, same private Session leaf `L`, exact trusted invocation/budget-request identity, and its unique owned request group. Both bind the complete `dispatchId`, neutral `attemptScope`, `expectedLeafId`, signal identity, budget request, and `(model, context, options)` values. No later call can supply replacement fields.
3. The private core `dispatch(token)` registers token object identity and the complete dispatch/scope/receipt identity. The leader synchronously invokes the A3.1 snapshot path before its first await, so later caller mutation cannot race the ownership transfer. `Models.prepareSimple(...)` runs exactly once through the composition's one `Models`/Provider/Auth path and returns detached resolved request facts plus resident `start()` without Adapter/lazy API entry.
4. Protected qualification rejects mutators/unsupported values and invokes only the runtime-owned secret binder for raw resolved values. Pi computes the complete actual model basis/digest; for `exact_required`, it snapshots the prepared counter identity, compares that identity byte-for-byte with the pre-bound expected identity, combines the actual `modelDigest` and matching identity into `counterBindingDigest`, inserts that actual digest into the budget-independent logical invocation basis, and only then computes `logicalInvocationDigest`. For `trusted_count`, the logical basis carries an absent counter-binding slot and Pi validates the supplied final basis exactly as before. For `exact_required`, it passes the same binding/logical/model digests to the local exact counter, validates and revalidates the result, separately checks the minimum-output count, and constructs the final budget/evidence. Only then does Pi compute the budget digest. Raw values and the transient output probe never cross to application authority.
5. Application authority returns closed `bound`, `denied`, or `unavailable`. Only `bound` supplies the pre-artifact binding basis; Pi snapshots it, recomputes its digest, and only then constructs the artifact and `artifactDigest`.
6. Application authority returns closed `authorized`, `denied`, or `unavailable`. Only `authorized` supplies the post-artifact Disclosure Decision basis, prior-entry drafts, and retention choice; Pi snapshots them, validates identity against the artifact, and recomputes all digests.
7. A4 prepares against `L`, fixing final prior-entry IDs/parents/timestamps and reserving the last terminal ID. Pi hashes each complete materialized prior entry. Application authority then returns closed `created`, `denied`, or `unavailable` against those final digests. Only `created` supplies opaque material; Pi hashes it, builds the generic receipt and terminal envelope, and the application authenticator signs/verifies it. A4 seals the terminal slot once and freezes the complete batch. Nothing has appended yet.
8. A4 records every final entry ID and complete entry digest, then commits unchanged by expected-leaf CAS. `committed` or authoritative `exact_present` identifies terminal entry `D`; every other result starts nothing.
9. Before Adapter start, the core recomputes the retained exact-count evidence when present and atomically requires the same counter identity/result, the frontend's resident current generation, active bound signal, resident unused permit, all bound frontend guards still at their step-2 values, and authoritative Session leaf exactly `D`. Any evidence mismatch starts no Adapter. Harness advances both of its private cursor leaves `L -> D` without changing selected/default identities, prepared Context, or artifact. The one-shot frontend advances its one private leased-Session cursor `L -> D` without adding a Harness cursor, transcript, queue, or Run identity. The receipt is not retroactively added to the request.
10. The transaction atomically consumes the private permit and calls only retained A3.1 `start()`. `dispatch(...)` returns `started` with the stream or a closed `not_started` result; it never returns a prepared reference or permit.

The shared runtime owns one generation-bounded in-memory dispatch registry. Its key is the token-bound `dispatchId`; the opaque token is compared only by object identity and is never persisted or hashed. Harness and one-shot tokens register in this same registry. Registration happens before `prepareSimple`, and the leader enters the A3.1 ownership snapshot synchronously before yielding. A concurrent same-token follower can present only the same already-bound input because both token-backed dispatch methods have no replacement parameter. It observes the leader's internal settlement Promise solely to classify durable knowledge, then returns closed `duplicate_in_flight`; only the leader can receive the `started` stream. The follower never receives or shares the stream, prepares, commits, mints/consumes a permit, starts, or emits provider events. A different token from either frontend carrying the same dispatch ID returns pre-receipt `identity_conflict`; same-token identity cannot drift because minting bound the complete identity and object group. Once a record reaches `receipt_committed`, `started`, or any terminal `not_started` state, no later call may prepare, mint a permit, commit, or start. A call made after terminal settlement returns `duplicate_terminal` with the recorded receipt-state/knowledge projection; it never replays a stream. An `exact_present` lookup may continue only in the original leader record that still owns the resident A3.1 value and unused permit. Process crash/reopen has no such record and therefore never starts from a receipt.

The registry holds at most 4,096 records per resident generation for either scope kind. Its neutral generation key is exactly `(attemptScope.kind, operationId, generationId)` and its request identity additionally binds `requestId`, `attemptId`, and `dispatchId`. It never evicts an in-flight, receipt-committed, started, or terminal record while that generation can still receive a call. Capacity exhaustion returns pre-receipt `dispatch_registry_exhausted`. One one-shot `bindAttempt` creates one resident generation object and one attempt capability; the production Adapter may bind exactly once for its already validated invocation, and every repeated/concurrent `dispatch()` uses that same no-argument capability. Cancellation, supersession, Adapter close, or owner settlement retires that resident generation permanently. Retirement aborts/settles its still-local attempt, retires every unused permit, and prevents its existing token from registering or starting. Records are removed only after the generation is permanently settled or retired and every local start/event sink is fenced. A late existing capability retains the retired resident object and therefore observes `generation_retired`; it cannot recreate the generation registry or register again. The runtime separately retains at most 4,096 retired neutral-key tombstones and evicts only retired tombstones. That bounded tombstone index rejects accidental trusted-source rebinding while resident, but is not a durable replay cache; after eviction, rebinding remains forbidden by the frontend's exactly-once ownership contract rather than claimed as cross-process replay protection. Thus the registry is bounded by active/unsettled generations plus bounded retired tombstones. Rebinding a completed Task Understanding invocation is forbidden by its exactly-once Adapter contract and is not a recovery or retry operation.

Expected failures are values, not exceptions. Only an impossible internal invariant violation, such as a sealed batch whose retained bytes no longer match its own evidence inside Pi-owned immutable memory, throws a typed internal error and forces Harness settlement. The exact failure projection is:

| Stage | Expected failure or observation | Closed result; Adapter start |
|---|---|---|
| frontend bind/claim | invalid/unknown identity or budget, source rejection, stale expected leaf, pre-aborted signal | `pre_receipt` / `application_invalid`, `control_conflict`, or `cancelled` / `none` / `not_dispatched`; never; Harness claims once and one-shot bind never prepares |
| registry, before prepare | capacity exhausted, different token/identity, already-terminal record with no receipt | `pre_receipt` / exact code / `none` / `not_dispatched`; never |
| registry, leader still in flight | same-token follower waits only for knowledge classification | `duplicate_in_flight` with final `none/not_dispatched`, `unknown/unknown`, `untrusted/unknown`, or `trusted_present/may_have_dispatched`; never returns a stream and never starts |
| A3.1 prepare | invalid request, auth/preparation rejection | `pre_receipt` / `invalid_request` / `none` / `not_dispatched`; never |
| binder/canonicalization | binding failure, collision, unsupported or over-budget prepared value | `pre_receipt` / `invalid_request` / `none` / `not_dispatched`; never |
| safe model/budget comparison or application binding/authorization/opaque return | closed deny => `unsupported_model`, `budget_unavailable`, or `application_denied`; closed unavailable => `application_unavailable`; thrown/unknown/invalid/mutated/over-budget result => `application_invalid` | `pre_receipt` / exact code / `none` / `not_dispatched`; never |
| A4 prepare/preview/seal | stale expected leaf => `control_conflict`; capability-missing `unsupported` or authoritative-load `unavailable(reason)` => `control_unavailable`; invalid draft/preview/terminal => `application_invalid` | `pre_receipt` / exact code / `none` / `not_dispatched`; zero reservation/append/event; never |
| sign or pre-commit verify | signer/verifier rejection, mismatch, or timeout | `pre_receipt` / `application_invalid` or `receipt_untrusted` is not used because nothing is present / `none` / `not_dispatched`; never |
| A4 commit | `conflict` | `pre_receipt` / `control_conflict` / `none` / `not_dispatched`; never |
| A4 commit | `acknowledgement_unknown` | registry remains in-flight and performs one lookup; no recommit |
| lookup after unknown | authoritative same-Session state remains at `expectedLeafId` and contains zero reserved IDs | `ack_absent` / `acknowledgement_resolved_absent` / `none` / `not_dispatched`; never |
| lookup after unknown | partial/conflicting/later-leaf batch or storage unavailable | `ack_unknown` / `acknowledgement_unresolved` / `unknown` / `unknown` plus the locally sealed receipt reference; never |
| lookup after unknown | exact batch present but envelope/material/authenticity is untrusted | `untrusted_present` / `receipt_untrusted` / `untrusted` / `unknown` plus the locally sealed receipt reference; never |
| cancellation/retirement | wins before trusted receipt presence | `pre_receipt` / `cancelled` or `generation_retired` / `none` / `not_dispatched`; never |
| cancellation/retirement | wins after trusted committed/exact-present receipt | `post_receipt` / exact code / `trusted_present` / `may_have_dispatched` plus entry ID; never |
| cursor validation | leaf/generation/context cursor changed after trusted receipt | `post_receipt` / `cursor_changed` / `trusted_present` / `may_have_dispatched` plus entry ID; never |
| permit validation/consume | resident value missing, retained `start()` failure, or the private unused-to-consumed/retired invariant fails | typed internal `ProviderDispatchInvariantError`; no public Provider Dispatch result and never start; Harness settles the internal failure without inventing a protocol code |
| terminal duplicate | original record already terminal | `duplicate_terminal` with final `none/not_dispatched`, `unknown/unknown`, `untrusted/unknown`, or `trusted_present/may_have_dispatched`; never returns/replays a stream |

After `committed` or `exact_present`, Pi recomputes and verifies the complete generic envelope before marking `trusted_present`; only then may cursor and permit checks continue. There is no expected failure branch that throws, returns an ambiguous `none`, retries prepare/commit, or reconstructs a permit.

`ProviderDispatchReceiptReferenceV1` is always built by Pi from the retained sealed receipt and A4 preview, never from a lookup payload or application return. `decisionExpectedLeafId` and `terminalEntryId` are byte-identical and name `D`; `expectedLeafId` names `L`; `receiptDigest` is recomputed from the retained complete generic receipt. `receiptDisposition = committed` follows only A4 `committed`; `exact_present` follows only one acknowledgement-unknown lookup that finds the exact same batch; and `acknowledgement_unknown` means no authoritative exact/absent conclusion. Type structure enforces the pairing: started, trusted post-receipt, and trusted-present duplicates use only `ProviderDispatchStartedEvidenceV1`; `ack_unknown` and unknown duplicates use only `ProviderDispatchAcknowledgementUnknownReferenceV1`; `untrusted_present` and untrusted duplicates use only `ProviderDispatchPresentReceiptReferenceV1`. The latter two durable states remain `unknown` even with a local reference and do not claim eligible receipt trust. `ack_absent` proves the reserved IDs absent at unchanged `L` and therefore returns no receipt reference. Pre-receipt results leave the decision expected leaf at `L` in their frontend mapping.

`ProviderDispatchStartedEvidenceV1.budgetEvidence` is a closed non-secret projection copied from Pi's retained receipt bases only after the complete envelope is trusted. Its `modelRef`, actual `modelDigest`, `logicalInvocationDigest`, `budgetDigest`, and exact-count slot must recompute byte-for-byte against the retained artifact, budget basis, and receipt. `exact_required` started results require a present exact-count slot; `trusted_count` started results require it absent. This projection exposes no Model body, prompt, message, Tool schema, transient minimum-output text, prepared value, auth source, secret binding, Session capability, permit, or Adapter handle. A bounded one-shot Adapter may copy these fields into its owning invocation-outcome evidence; neither the frontend nor Workspace may replace or mutate them.

The bounded one-shot production Adapter maps this generic result without exposing a stream or delta to Workspace callers:

| Provider Dispatch result | Task Understanding dispatch binding and terminal class |
|---|---|
| `started` after `committed` | `receipt_committed`, exact receipt digest/terminal `D`, and `decisionExpectedLeafId = D`; the Adapter privately consumes exactly this stream into one terminal candidate/refusal/truncation/timeout/provider-failure/cancellation outcome |
| `started` after `exact_present` | `receipt_exact_present` with the same exact evidence and private single stream consumption |
| pre-receipt `exact_input_count_unsupported|exact_input_count_unavailable|exact_input_count_invalid|exact_input_budget_exceeded` | `not_dispatched`, zero charge, `decisionExpectedLeafId = L`, and exact `failed(input_budget_exceeded)`; no fallback |
| pre-receipt `cancelled|generation_retired` | `not_dispatched`, zero charge, `decisionExpectedLeafId = L`, and `cancelled` |
| pre-receipt `unsupported_model` | `not_dispatched`, zero charge, `decisionExpectedLeafId = L`, and `failed(unsupported_model)` |
| pre-receipt `budget_unavailable` | `not_dispatched`, zero charge, `decisionExpectedLeafId = L`, and `failed(budget_unavailable)` |
| pre-receipt `application_denied|application_unavailable|control_unavailable|dispatch_registry_exhausted` | `not_dispatched`, zero charge, `decisionExpectedLeafId = L`, and `failed(dispatch_unavailable)` |
| pre-receipt `invalid_request|application_invalid|control_conflict|identity_conflict` | `not_dispatched`, zero charge, `decisionExpectedLeafId = L`, and `failed(pre_dispatch_protocol_error)` |
| `ack_absent` | `not_dispatched`, zero charge, `decisionExpectedLeafId = L`, and `failed(pre_dispatch_protocol_error)`; the exact absence remains available to the enclosing Module for its owning lifecycle classification |
| `ack_unknown` or `untrusted_present` | `acknowledgement_unresolved`, exact local receipt digest/terminal `D`, unknown charge, and no provider start/candidate |
| unknown/untrusted `duplicate_in_flight|duplicate_terminal` observed despite the invocation Port's exactly-once rule | `acknowledgement_unresolved` using its structurally matching exact local receipt reference, unknown charge, and no retry/start/candidate |
| post-receipt `cancelled|generation_retired` | started binding using the trusted receipt disposition/reference and one `cancelled` terminal; no provider output is accepted |
| post-receipt `cursor_changed`, or a trusted-present duplicate observed despite the invocation Port's exactly-once rule | started binding using the trusted receipt disposition/reference and `provider_failed(provider_protocol_error)`; no retry, candidate, or second call |
| receipt-absent duplicate observed despite the invocation Port's exactly-once rule | `not_dispatched` plus `failed(pre_dispatch_protocol_error)`; no retry |

`providerAttemptRef` is the exact `dispatchId`. Adapter start/finish timestamps and final usage/charge are owned by the Task Understanding Adapter and its closed outcome contract; they cannot alter provider-dispatch evidence. The Adapter may return a Task Understanding result only after the stream reaches one terminal event, must discard every later callback, and must never emit raw model deltas, provider prose, hidden reasoning, or alternate candidates through a Workspace event. A provider-dispatch result/evidence mismatch is `attempt_identity_mismatch`, not a fallback or repaired call.

The cursor is private runtime coordination, not a second transcript or durable state model. If either cursor has moved, if the Session is before `D` or beyond `D`, or if cancellation/retirement wins before step 9, the receipt remains durable as `may_have_dispatched` but no Adapter starts. A present receipt never reconstructs a prepared value or permit after crash/reopen. A permit is non-serializable, bound by object identity to one resident prepared value and generation, and has terminal states `consumed` or `retired`; a second consume fails closed. Protected mode is opt-in and leaves the ordinary Harness `before_provider_payload`/`onPayload` path unchanged.

A4 is a prerequisite, not part of A3.2: its generic Session Interface must reserve and expose a pre-materialized control batch with final IDs/timestamps/parent chain and one terminal slot, seal that terminal receipt exactly once, freeze receipt-last order, classify commit acknowledgement, authoritatively refresh the current leaf, and perform exact lookup by the recorded entry IDs plus complete entry digests. Abandoning an uncommitted preparation appends nothing and reuses none of its reserved identities. An acknowledgement timeout is `unknown`, never `absent`; A3.2 may continue only after A4 refresh proves the one exact batch present at leaf `D`. `appendBatchIfLeaf` plus a stale process-local JSONL cache is insufficient for that claim.

#### 6.6.1 Closed current Pi request schema

`ProviderDispatchSlotV1` is permitted only on fields explicitly declared with that type in a named provider-dispatch basis. It distinguishes source-property absence from a present value, including `null`; it is not a general wrapper for arbitrary JSON or Session entries. Optional runtime Interface capabilities such as `signal` are not canonical slots.

The message canonicalizer accepts only these current closed variants and fields:

| Variant | Exact fields |
|---|---|
| user message | `role = "user"`, `content`, `timestamp`; content is one string or an ordered array of text/image content |
| assistant message | `role = "assistant"`, ordered `content`, `api`, `provider`, `model`, slots for `responseModel`, `responseId`, `diagnostics`, complete `usage`, `stopReason = stop|length|toolUse|error|aborted`, slot for `errorMessage`, `timestamp` |
| tool-result message | `role = "toolResult"`, `toolCallId`, `toolName`, ordered text/image `content`, slot for canonical `details`, slot for ordered `addedToolNames`, `isError`, `timestamp` |
| text content | `type = "text"`, `text`, slot for `textSignature` |
| thinking content | `type = "thinking"`, `thinking`, slots for `thinkingSignature` and `redacted` |
| image content | `type = "image"`, canonical base64 `data`, `mimeType` |
| tool-call content | `type = "toolCall"`, `id`, `name`, canonical-object `arguments`, slot for `thoughtSignature` |
| usage | `input`, `output`, `cacheRead`, `cacheWrite`, slots for `cacheWrite1h` and `reasoning`, `totalTokens`, and cost fields `input`, `output`, `cacheRead`, `cacheWrite`, `total` |
| diagnostic | `type`, `timestamp`, slot for error `{ message, name, stack, code }` where `message` is required, `name`/`stack` are named string slots, and `code` is a named `string|number` slot; plus a named slot for canonical-object `details` |

Message/content arrays preserve source order. The system prompt is its named slot. Tools preserve source order and contain exactly `name`, `description`, and one JSON-visible TypeBox/JSON-Schema `parameters` object. A3.1 accepts structural AgentTool subtypes but projects `label`, `execute`, `executionMode`, callbacks, and every other runtime subtype member out before A3.2; if the resulting prepared public Tool still has any extra enumerable member, A3.2 rejects. Known non-enumerable TypeBox runtime metadata is retained only in the resident A3.1 value and is not JSON-visible logical input. Tool schema keywords and extension keys are intentionally arbitrary strings under the canonical-object grammar and schema budgets; values must be canonical JSON, so the complete JSON-visible schema is hashed without Pi interpreting its keywords.

Metadata likewise has an intentionally open key vocabulary but a closed structural schema: one canonical JSON object, no prototype/accessor semantics, whose values are only null, boolean, finite number, string, canonical array, or canonical object. This is not permission for secrets; secret-classified values must use the runtime binder path.

Model `compat` is absent unless `api` selects one of these exact closed variants. Every listed member is a named slot; an unlisted member rejects:

| API variant | Exact members and value domains |
|---|---|
| `openai-completions` | booleans `supportsStore`, `supportsDeveloperRole`, `supportsReasoningEffort`, `supportsUsageInStreaming`, `requiresToolResultName`, `requiresAssistantAfterToolResult`, `requiresThinkingAsText`, `requiresReasoningContentOnAssistantMessages`, `zaiToolStream`, `supportsStrictMode`, `sendSessionAffinityHeaders`, `supportsLongCacheRetention`; `maxTokensField` = `max_completion_tokens|max_tokens`; `thinkingFormat` = `openai|openrouter|deepseek|together|zai|qwen|chat-template|qwen-chat-template|string-thinking|ant-ling`; canonical `chatTemplateKwargs`; closed `openRouterRouting`; closed `vercelGatewayRouting`; `cacheControlFormat = anthropic`; closed `sessionAffinityFormat` |
| `openai-responses` or `openai-codex-responses` | booleans `supportsDeveloperRole`, `supportsLongCacheRetention`, `supportsToolSearch`; closed `sessionAffinityFormat` |
| `anthropic-messages` | booleans `supportsEagerToolInputStreaming`, `supportsLongCacheRetention`, `sendSessionAffinityHeaders`, `supportsCacheControlOnTools`, `supportsTemperature`, `forceAdaptiveThinking`, `allowEmptySignature`, `supportsToolReferences` |
| every other current API | `compat` must be absent |

`sessionAffinityFormat` is `openai|openai-nosession|openrouter`. `chatTemplateKwargs` values are string, finite number, boolean, null, or exactly `{ $var: "thinking.enabled" | "thinking.effort", omitWhenOff: <named boolean slot> }`. `vercelGatewayRouting` contains only ordered string arrays `only` and `order`. `openRouterRouting` contains only: boolean slots `allow_fallbacks`, `require_parameters`, `zdr`, `enforce_distillable_text`; `data_collection = deny|allow`; ordered string-array slots `order`, `only`, `ignore`, `quantizations`; `sort` as string or exactly `{ by: <string slot>, partition: <string|null slot> }`; `max_price` with only `prompt`, `completion`, `image`, `audio`, and `request`, each a number|string slot; and `preferred_min_throughput`/`preferred_max_latency`, each a finite number or exactly `{ p50, p75, p90, p99 }` with each member a finite-number slot. Adding any public compat member or nested routing member requires a protocol revision and fails v1 until then.

#### 6.6.2 Complete materialized control-entry basis

`PiSessionEntryDigestBasisV1.entry` is not application custom data alone. It is the complete A4 materialized `SessionTreeEntry`, including exact `type`, `id`, `parentId`, ISO timestamp, and every type-specific field. Its closed current union is:

- `message`: complete canonical `message` object;
- `thinking_level_change`: `thinkingLevel`;
- `model_change`: `provider`, `modelId`;
- `active_tools_change`: ordered `activeToolNames`;
- `compaction`: `summary`, `firstKeptEntryId`, `tokensBefore`, named slots for canonical `details` and `fromHook`;
- `branch_summary`: `fromId`, `summary`, named slots for canonical `details` and `fromHook`;
- `custom`: `customType`, named slot for canonical `data`;
- `custom_message`: `customType`, string or ordered text/image `content`, named slot for canonical `details`, `display`;
- `label`: `targetId`, named slot for `label`;
- `session_info`: named slot for `name`;
- `leaf`: `targetId` as string or null.

Unknown entry types or fields reject. For provider dispatch, application prior drafts materialize only as `custom` entries. The terminal entry is one `custom` entry whose `customType` and `data` are exactly the terminal envelope defined above. Its materialized ID equals both `receipt.terminalEntryId` and committed leaf `D`. The digest covers the complete terminal entry for A4 exact lookup, while `orderedPriorControlEntryDigests` excludes it and covers every preceding entry in physical order.

#### 6.6.3 Canonicalization and cost limits

Limits are charged and checked at the first stage that owns the complete value. Prepared model/context/options limits are checked after A3.1 preparation and before `bindBeforeArtifact`; application-binding limits are checked immediately on the binding return and before artifact construction; disclosure-decision and prior-draft limits are checked immediately on authorization return and before A4 preparation; complete materialized-entry/envelope limits are checked on A4 preview/seal; opaque-material limits are checked immediately on its post-preview return and before signing/sealing. Every limit is checked before the value can be appended or the Adapter can start. Exceeding a prepared-request limit is `invalid_request`; exceeding an application-returned or terminal-stage limit is `application_invalid`; partial digests are discarded.

| Resource | v1 hard limit and charging rule |
|---|---|
| canonical nesting | depth 32; 100,000 aggregate object members plus array elements |
| aggregate canonical request | 64 MiB of UTF-8 JCS across system prompt, messages, tools, model, metadata, and options before digest bases; shared values are charged at every logical occurrence |
| messages/content | 4,096 messages; 1,024 content items per message; 8 MiB UTF-8 JCS per message; 32 MiB aggregate message JCS |
| strings | 4 MiB UTF-8 per general string; system prompt 4 MiB; identifiers/names 1,024 UTF-8 bytes unless a tighter rule below applies |
| images | canonical base64 alphabet/padding only; 16 MiB encoded and 12 MiB decoded per image; 32 MiB decoded aggregate; both encoded JCS bytes and decoded bytes are charged before allocation/decoding |
| tool calls/details | arguments or details depth 32, 20,000 members/elements, and 2 MiB UTF-8 JCS per value |
| tools/schemas | 256 tools; name 256 bytes; description 64 KiB; schema depth 32, 20,000 members/elements, 1 MiB UTF-8 JCS per schema and 8 MiB aggregate schema JCS |
| metadata | depth 8; 256 members/elements; key 128 bytes; string 4,096 bytes; 16,384 UTF-8 JCS bytes total |
| headers | 64 per layer; valid non-empty ASCII HTTP token name at most 128 bytes; value at most 8,192 UTF-8 bytes; within-layer ASCII-case collisions reject |
| environment | 128 entries; key at most 128 UTF-8 bytes; value at most 8,192 UTF-8 bytes |
| application binding | depth 16; 10,000 members/elements; 1 MiB UTF-8 JCS for the complete `ProviderDispatchApplicationBindingBasisV1` |
| disclosure decision | depth 16; 10,000 members/elements; 1 MiB UTF-8 JCS for the complete `ProviderDispatchDisclosureDecisionBasisV1` |
| application prior entries | 256 prior drafts; 1 MiB UTF-8 JCS per complete materialized prior entry; 4 MiB aggregate complete prior entries |
| opaque terminal material | depth 16; 10,000 members/elements; 1 MiB UTF-8 JCS for the complete material basis |
| receipt/envelope | 1 MiB complete UTF-8 JCS; digest arrays at most the corresponding message/tool/prior-entry counts |

Sparse arrays, lone UTF-16 surrogates, invalid base64, bigint, non-finite numbers, functions, symbols, accessors, cycles, unsupported prototypes, and invalid UTF-8/JCS domains reject. JCS preserves array order, sorts object keys per RFC 8785, and performs no Unicode normalization.

### 6.7 PNW-A4 executable Session control-batch contract

A4 is an independently accepted Pi Session deep Module. It knows nothing about providers, credentials, CTI, application disclosure, permits, or Adapter start. Its small public Interface owns final materialization, one terminal slot, immutable evidence, expected-leaf CAS, acknowledgement classification, authoritative refresh, and exact lookup:

```typescript
type PiSessionSlotV1<T> =
	| { presence: "absent" }
	| { presence: "present"; value: T };

type PiSessionTextContentV1 = { type: "text"; text: string; textSignature?: string };
type PiSessionImageContentV1 = { type: "image"; data: string; mimeType: string };
type PiSessionThinkingContentV1 = {
	type: "thinking";
	thinking: string;
	thinkingSignature?: string;
	redacted?: boolean;
};
type PiSessionToolCallV1 = {
	type: "toolCall";
	id: string;
	name: string;
	arguments: { readonly [key: string]: PiCanonicalJsonV1 };
	thoughtSignature?: string;
};
type PiSessionUsageV1 = {
	input: number;
	output: number;
	cacheRead: number;
	cacheWrite: number;
	cacheWrite1h?: number;
	reasoning?: number;
	totalTokens: number;
	cost: { input: number; output: number; cacheRead: number; cacheWrite: number; total: number };
};
type PiSessionDiagnosticV1 = {
	type: string;
	timestamp: number;
	error?: { message: string; name?: string; stack?: string; code?: string | number };
	details?: { readonly [key: string]: PiCanonicalJsonV1 };
};

type PiSessionAgentMessageV1 =
	| {
			role: "user";
			content: string | readonly (PiSessionTextContentV1 | PiSessionImageContentV1)[];
			timestamp: number;
	  }
	| {
			role: "assistant";
			content: readonly (PiSessionTextContentV1 | PiSessionThinkingContentV1 | PiSessionToolCallV1)[];
			api: string;
			provider: string;
			model: string;
			responseModel?: string;
			responseId?: string;
			diagnostics?: readonly PiSessionDiagnosticV1[];
			usage: PiSessionUsageV1;
			stopReason: "stop" | "length" | "toolUse" | "error" | "aborted";
			errorMessage?: string;
			timestamp: number;
	  }
	| {
			role: "toolResult";
			toolCallId: string;
			toolName: string;
			content: readonly (PiSessionTextContentV1 | PiSessionImageContentV1)[];
			details?: PiCanonicalJsonV1;
			addedToolNames?: readonly string[];
			isError: boolean;
			timestamp: number;
	  }
	| {
			role: "bashExecution";
			command: string;
			output: string;
			exitCode: number | undefined;
			cancelled: boolean;
			truncated: boolean;
			fullOutputPath?: string;
			timestamp: number;
			excludeFromContext?: boolean;
	  }
	| {
			role: "custom";
			customType: string;
			content: string | readonly (PiSessionTextContentV1 | PiSessionImageContentV1)[];
			display: boolean;
			details?: PiCanonicalJsonV1;
			timestamp: number;
	  }
	| { role: "branchSummary"; summary: string; fromId: string; timestamp: number }
	| { role: "compactionSummary"; summary: string; tokensBefore: number; timestamp: number };

type PiSessionControlEntryDraftV1 =
	| { type: "message"; message: PiSessionAgentMessageV1 }
	| { type: "thinking_level_change"; thinkingLevel: string }
	| { type: "model_change"; provider: string; modelId: string }
	| { type: "active_tools_change"; activeToolNames: readonly string[] }
	| {
			type: "compaction";
			summary: string;
			firstKeptEntryId: string;
			tokensBefore: number;
			details?: PiCanonicalJsonV1;
			fromHook?: boolean;
	  }
	| {
			type: "branch_summary";
			fromId: string;
			summary: string;
			details?: PiCanonicalJsonV1;
			fromHook?: boolean;
	  }
	| { type: "custom"; customType: string; data?: PiCanonicalJsonV1 }
	| {
			type: "custom_message";
			customType: string;
			content: string | readonly (PiSessionTextContentV1 | PiSessionImageContentV1)[];
			details?: PiCanonicalJsonV1;
			display: boolean;
	  }
	| { type: "label"; targetId: string; label?: string }
	| { type: "session_info"; name?: string }
	| { type: "leaf"; targetId: string | null };

type PiSessionMaterializedEntryV1 = PiSessionControlEntryDraftV1 & {
	readonly id: string;
	readonly parentId: string | null;
	readonly timestamp: string;
};

interface PiSessionControlBatchEvidenceV1 {
	readonly protocol: "pi-session-control-batch-evidence/v1";
	readonly sessionId: string;
	readonly expectedLeafId: string | null;
	readonly orderedEntryIds: readonly string[];
	readonly orderedEntryDigests: readonly PiDigestV1[];
	readonly terminalEntryId: string;
	readonly batchDigest: PiDigestV1;
}

interface PiSessionPreparedControlBatchV1 {
	readonly kind: "prepared";
	readonly preview: {
		readonly sessionId: string;
		readonly expectedLeafId: string | null;
		readonly priorEntries: readonly PiSessionMaterializedEntryV1[];
		readonly terminal: {
			readonly type: "custom";
			readonly customType: string;
			readonly id: string;
			readonly parentId: string | null;
			readonly timestamp: string;
		};
	};
	sealTerminal(data: PiCanonicalJsonV1): PiSessionSealTerminalResultV1;
	abandon(): void;
}

interface PiSessionSealedControlBatchV1 {
	readonly kind: "sealed";
	readonly entries: readonly PiSessionMaterializedEntryV1[];
	readonly evidence: PiSessionControlBatchEvidenceV1;
	abandon(): void;
	commit(): Promise<
		| { kind: "committed"; evidence: PiSessionControlBatchEvidenceV1 }
		| { kind: "conflict" }
		| { kind: "acknowledgement_unknown"; evidence: PiSessionControlBatchEvidenceV1 }
	>;
}

type PiSessionSealTerminalResultV1 =
	| { kind: "sealed"; sealed: PiSessionSealedControlBatchV1 }
	| { kind: "invalid_terminal" };

interface PiSessionControlBatch {
	prepareControlBatch(input: {
		readonly expectedLeafId: string | null;
		readonly priorEntries: readonly PiSessionControlEntryDraftV1[];
		readonly terminal: { readonly customType: string };
	}): Promise<
		| PiSessionPreparedControlBatchV1
		| { kind: "conflict" }
		| { kind: "invalid_draft" }
		| { kind: "unsupported" }
		| { kind: "unavailable"; reason: "io" | "invalid_or_truncated" | "unsupported" }
	>;
	lookupControlBatch(
		evidence: PiSessionControlBatchEvidenceV1,
	): Promise<
		| { kind: "exact_present"; terminalEntryId: string }
		| { kind: "absent" }
		| { kind: "conflict" }
		| { kind: "unavailable"; reason: "io" | "invalid_or_truncated" | "unsupported" }
	>;
}
```

The structural types above are the Session-owned closed current 11-entry union. `PiSessionControlEntryDraftV1` omits only `id`, `parentId`, and `timestamp`; `PiSessionMaterializedEntryV1` adds those base fields to the same exact type-specific fields. The terminal is always the `custom` variant, has exactly the reserved `customType`, and receives `data` only through `sealTerminal`. A3.2 depends on this Session union; A4 does not depend on any provider type. Unknown types, fields, or values return `invalid_draft` before reservation.

For the `message` entry, A4's closed `AgentMessage` union contains the three exact AI messages from section 6.6.1 (`user`, `assistant`, `toolResult`) plus these built-in Agent roles:

| Agent role | Exact fields |
|---|---|
| `bashExecution` | `role`, `command`, `output`, named slot for `exitCode`, `cancelled`, `truncated`, named slots for `fullOutputPath` and `excludeFromContext`, `timestamp` |
| `custom` | `role`, `customType`, string or ordered text/image `content`, `display`, named slot for canonical `details`, `timestamp` |
| `branchSummary` | `role`, `summary`, `fromId`, `timestamp` |
| `compactionSummary` | `role`, `summary`, `tokensBefore`, `timestamp` |

`exitCode` is a present finite integer or the absent slot. Declaration-merged application roles are intentionally unsupported in opt-in A4 v1 and fail closed; legacy Session methods retain their current behavior. Adding one to A4 requires a protocol revision. Text/image content uses section 6.6.1 exactly.

Every optional Session or AgentMessage property has one named `PiSessionSlotV1` position in `PiSessionEntryDigestBasisV1`; runtime `undefined` normalizes to `{ presence: "absent" }`, and a present value normalizes to `{ presence: "present", value }`. Property omission and `undefined` therefore hash identically across Memory objects and JSONL, while present `null` remains distinct wherever the underlying field permits null. Unknown values, unsupported prototypes, accessors, sparse arrays, or `undefined` outside a named optional position fail. Entry digests and `batchDigest` use the exact Session-owned `piDigest` mappings in 6.5.1/6.6.

`prepareControlBatch` first checks for the private A4 storage capability. Missing capability returns `unsupported`. When it exists, preparation asynchronously performs the same full authoritative load/validation used by lookup before it validates `expectedLeafId` or retained leaf targets. I/O, malformed/truncated bytes, or unsupported stored version returns `unavailable(io|invalid_or_truncated|unsupported)` respectively; this is neither a thrown expected error, `invalid_draft`, nor capability-missing `unsupported`. Every such failure occurs before reservation and produces zero append and zero Session event. The prior cache is not partially replaced or treated as authoritative. After a successful load, A4 derives immutable `sessionId` and current history/logical leaf, returns `conflict` before reservation when the leaf differs from `expectedLeafId`, and returns `invalid_draft` for an invalid draft. In A4 v1, every draft `leaf.targetId` must be either `null` or the ID of an entry already retained in that authoritative Session history before preparation. Any other target is `invalid_draft` before reservation. A draft cannot refer to an ID generated for another draft in the same batch; A4 v1 introduces no symbolic or ordinal target reference because provider dispatch does not need one. On success A4 takes an owned recursive snapshot and reserves non-empty unique IDs and canonical UTC timestamps. Materialization tracks a logical leaf starting at `expectedLeafId`. Every entry's physical `parentId` is the current logical leaf. A non-`leaf` entry then makes its own `id` the next logical leaf. A valid `leaf` entry is still physically appended and digested, but makes its retained-existing or null `targetId` the next logical leaf, so the following entry parents that target rather than the leaf-entry ID. After all prior entries, the reserved terminal parents the resulting logical leaf and then becomes the final logical leaf. A timestamp is valid only when `new Date(timestamp).toISOString() === timestamp`. The preview is recursively immutable and contains `sessionId`, final prior entries, and the final terminal ID/parent/timestamp; preparation appends zero bytes and emits no Session event. Mutation of input aliases cannot change it.

Within one active Session runtime, every reserved ID is burned immediately and never reused after seal, abandon, conflict, unknown acknowledgement, or expected failure. This non-reuse guarantee does not survive process death and is not a cross-process allocator claim. `sealTerminal(data)` is attempted exactly once. Valid data returns `sealed`, snapshots/materializes the terminal physically last, computes every complete entry digest/evidence, and freezes the exact entries. Invalid data returns `invalid_terminal`, atomically abandons the preparation, burns every reservation, appends zero, and cannot be retried. Prepared `abandon()` succeeds only before the seal attempt and appends nothing. A sealed-but-uncommitted handle also exposes `abandon()`; it retires the frozen batch, appends zero, and makes commit impossible. `commit()` may be called exactly once on a non-abandoned sealed handle and sends exactly its frozen entries; it never rematerializes IDs, timestamps, parents, slots, or data. Commit terminalizes the handle for `committed`, `conflict`, and `acknowledgement_unknown`. Any repeated method or transition after a terminal state is programmer misuse and performs zero storage operations.

The commit/lookup truth table is normative:

| Observation | Result |
|---|---|
| prepare finds no private A4 storage capability | `unsupported`; zero reservation/append/event |
| prepare authoritative load fails on I/O, malformed/truncated bytes, or stored version | `unavailable(io|invalid_or_truncated|unsupported)`; zero reservation/append/event and no partial cache replacement |
| expected leaf matches and storage acknowledges the exact frozen append | `committed` |
| expected leaf does not match before any append | `conflict`; zero prefix entries |
| storage may have accepted bytes but no trustworthy acknowledgement is available | `acknowledgement_unknown`; never recommit this evidence |
| current Session identity differs from evidence `sessionId` | `conflict` before entry comparison |
| authoritative validated state contains every recorded ID, digest, parent and order, and current leaf is the recorded terminal | `exact_present` with only the terminal ID; materialized entries remain private |
| authoritative validated state retains `expectedLeafId` as current leaf and contains none of the reserved IDs | `absent` |
| validated state contains a partial prefix, any reserved-ID/digest/parent/order mismatch, a same-batch identity mismatch, a changed competing leaf, or a later leaf after the terminal | `conflict` |
| authoritative storage cannot be fully read and validated because bytes are malformed/truncated, version unsupported, or I/O failed | `unavailable(invalid_or_truncated|unsupported|io)`; no false distinction between malformed and truncated bytes |

`absent` is never inferred from timeout, cache miss, parse failure, partial prefix, or stale process-local state. Lookup first compares the evidence `sessionId` with immutable current Session identity, then performs authoritative refresh. Memory validates the current instance's complete entry list and indexes; JSONL bypasses the cached Session, re-reads the whole file, validates every record/version/identity/parent relation before constructing a replacement state, and swaps that replacement into the Session only after full validation. Invalid refresh leaves the previous cache unusable for this lookup and returns `unavailable`; it does not partially replace it. Exact lookup returns only the closed status and terminal ID, never Session entries; the sealed resident handle retains the snapshot needed by A3.2. Commit and authoritative refresh/lookup are serialized on the same Session mutation queue. These guarantees cover exactly one live `SessionStorage` instance at a time, with sequential close then reopen in one process; Memory means its current live instance. Two simultaneously live JSONL/Memory instances, even in one process, are an A5 fencing case and are not authoritative under A4. A4 also does not promise `fsync`, power-loss durability, torn-sector recovery, cross-process fencing, or cross-process reservation uniqueness.

The existing `Session` directly implements `prepareControlBatch` and `lookupControlBatch`; A3.2 and product callers never receive a storage, allocator, refresh, or materialized-append Interface. Memory and JSONL satisfy a private optional storage capability whose append returns only `applied`, `conflict`, or `acknowledgement_unknown` and whose authoritative load returns one fully validated raw history or `unavailable(io|invalid_or_truncated|unsupported)`. A third-party legacy storage without that capability remains usable through existing Session methods, but A4 prepare returns capability-missing `unsupported` with zero reservation/append/event. When the capability exists but authoritative load fails, prepare returns `unavailable(reason)` with the same zero-work guarantee and no partial cache replacement. A CAS miss is `conflict`, an interrupted/ambiguous write acknowledgement is `acknowledgement_unknown`, and read/parse/version failures are `unavailable`; none are thrown as expected errors. Only implementation invariant violations throw. Existing `appendBatchIfLeaf`, A1 save-point materialization timing, and ordinary Session append methods are not redirected or changed by A4; A4 acceptance alone changes no Workspace migration gate.

A4 passed and must continue to pass these focused public-Interface oracles before any A3.2 implementation starts:

- **PNW-A4-F01:** existing `Session` directly exposes only `prepareControlBatch` and `lookupControlBatch`; no private storage capability, ID allocator, mutable Session array, refresh control, or provider concern leaks.
- **PNW-A4-F02:** preparation snapshots caller drafts, appends/emits zero, and later nested mutation changes neither preview nor seal.
- **PNW-A4-F03:** preview fixes unique IDs, ISO timestamps, expected logical leaf, exact logical parent transitions, and one reserved terminal identity.
- **PNW-A4-F04:** zero, one, and many prior entries always place the terminal physically last; ordinary entries advance logical leaf to their ID, while valid `leaf` entries advance it to `targetId` and the next entry/terminal parents that target.
- **PNW-A4-F05:** reserved IDs are not reused within the active runtime after abandon, seal, conflict, unknown acknowledgement, or any post-reservation validation failure.
- **PNW-A4-F06:** valid seal succeeds once and freezes complete entries/evidence; `invalid_terminal` abandons/burns with zero append and no retry; repeated seal is programmer misuse, while a sealed handle retains only commit-or-abandon transitions.
- **PNW-A4-F07:** abandon before seal or after seal-before-commit appends nothing, retires the handle, and makes later seal/commit impossible; repeated transitions perform no storage operation.
- **PNW-A4-F08:** commit succeeds once with the exact sealed bytes; a second call performs no storage operation.
- **PNW-A4-F09:** acknowledged CAS append returns `committed` and the current leaf is the terminal ID.
- **PNW-A4-F10:** prepare performs authoritative load before expected-leaf/retained-target validation; stale expected leaf returns `conflict`, while load I/O/invalid-or-truncated/unsupported-version returns exact `unavailable(reason)`, all with zero reservation/append/event.
- **PNW-A4-F11:** ambiguous storage acknowledgement returns `acknowledgement_unknown` plus the original evidence and cannot be recommitted.
- **PNW-A4-F12:** authoritative lookup returns `exact_present` plus only terminal ID for every exact complete entry/digest/order/parent and terminal current leaf; it never returns entries.
- **PNW-A4-F13:** lookup returns `absent` only when the validated current leaf is the expected leaf and every reserved ID is absent.
- **PNW-A4-F14:** a partial prefix or missing terminal is `conflict`, never `absent` or `exact_present`.
- **PNW-A4-F15:** a foreign `sessionId` or any changed ID, timestamp, parent, type-specific field, optional slot, order, terminal type/data, digest, or batch identity is `conflict`.
- **PNW-A4-F16:** a competing or later leaf after the terminal is `conflict`; A4 never rewinds it.
- **PNW-A4-F17:** prepare and lookup both classify malformed/truncated JSONL as `unavailable(invalid_or_truncated)` and unsupported stored format or I/O with their exact reasons; neither path partially replaces cache or claims an unreliable malformed-versus-truncated distinction.
- **PNW-A4-F18:** on one live storage instance, JSONL lookup bypasses stale cache and validates/replaces from the full file while Memory validates its current instance; commit and refresh serialize on one mutation queue. A second live instance is outside A4.
- **PNW-A4-F19:** all 11 current entry variants round-trip with complete base/type fields and identical Memory/JSONL digests; `leaf.targetId = null` and prepare-before authoritative retained-existing targets validate, while unknown or same-batch-generated targets return `invalid_draft` before reservation.
- **PNW-A4-F20:** all three AI roles and four built-in Agent roles round-trip; named absent slots normalize `undefined`, while unknown declaration-merged roles fail only in opt-in A4.
- **PNW-A4-F21:** sequential close/reopen after committed, conflict, acknowledgement-unknown exact write, partial prefix, and later leaf preserves the truth-table classification without claiming simultaneous-live-instance, crash/power-loss, or A5 durability/fencing.
- **PNW-A4-F22:** Memory/JSONL exercise the private capability; third-party storage without it returns capability-missing `unsupported`, while present-capability read/parse/version failure returns `unavailable(reason)`. Both occur before reservation/append/event, all legacy methods remain usable, and A3.2 maps both to `control_unavailable` without provider start.

### 6.8 PNW-A5 executable Session repository lease contract

This section is the sole normative owner of A5. It is a docs-only candidate until an independent Terra reviewer returns an explicit design PASS. A5 implementation is forbidden before that review.

The public seam is exactly one issuance operation and one later-acquisition operation:

```typescript
interface SessionRepositoryOpaqueRef {
	readonly protocol: "pi-session-repository-ref/v1";
	readonly token: string;
}

interface SessionRepository<
	TMetadata extends SessionMetadata = SessionMetadata,
	TProvisionOptions extends SessionCreateOptions = SessionCreateOptions,
> {
	provision(options: TProvisionOptions): Promise<ProvisionedSession<TMetadata>>;
	acquire(opaqueRef: SessionRepositoryOpaqueRef): Promise<SessionLease<TMetadata>>;
}

interface ProvisionedSession<TMetadata extends SessionMetadata = SessionMetadata> {
	readonly sessionRef: SessionRepositoryOpaqueRef;
	readonly lease: SessionLease<TMetadata>;
}

interface SessionLease<TMetadata extends SessionMetadata = SessionMetadata> {
	readonly sessionId: string;
	readonly generation: number;
	readonly session: Session<TMetadata>;
	release(): Promise<void>;
}
```

`provision` is the only public issuance seam. It creates one new repository-owned Session, mints its opaque immutable reference, acquires generation one, and resolves only with the paired `sessionRef` and already-active guarded `lease`. The reference is a closed JSON value: exactly `protocol` plus an unpadded base64url `token` carrying 256 bits of cryptographically secure repository-issued entropy. Unknown members, protocol, alphabet, padding, or decoded length are invalid. The token is a bearer capability, not a Session ID, path, metadata digest, lease token, or caller-selected name.

Opaque means that callers may only recursively snapshot, retain, JSON-serialize, and transmit the complete value unchanged; it does not mean non-serializable or process-local object identity. Callers must not destructure it for decisions, interpret or normalize the token, construct a replacement, compare token internals, derive it from path/metadata, or log it. Workspace may retain and later return the exact complete value only to its configured repository; it never receives path, metadata, lease token, storage, or an unleased Session. No public parser, token constructor, metadata conversion, registration operation, raw open, or storage getter exists. Tests obtain references through `provision` exactly as production callers do and have no fixture-only ref mint/registration seam.

`acquire` first validates the closed syntax, then performs repository-owned authenticity/catalog lookup using the exact token. Memory uses its shared private catalog; JSONL uses a domain-separated cryptographic digest of the token as its private catalog key and path-safe lookup name. The catalog binds that digest to the internal Session identity and storage path; neither the catalog record, digest, identity, nor path crosses the repository Interface. A syntactically valid random, altered, foreign-repository, missing, or mismatched token is not authenticated by syntax and rejects without revealing which lookup step failed.

Memory and JSONL provisioning have the same high-level failure behavior: expected failure rejects with the existing closed `SessionError` classification and returns neither ref nor lease. Provisioning publishes the new Session identity/data, opaque-ref resolution record, generation-one ownership claim, and guarded lease all-or-none. ID collision, invalid options, storage failure, abort, or claim failure leaves no resolvable ref, live claim, or caller-addressable half Session. No failure advances a generation. An unknown, malformed, foreign-repository, missing, corrupt, or unsupported reference rejects `acquire` with `SessionError`; no Session or lease is returned.

`acquire` either resolves one live `SessionLease` or rejects. A currently owned reference rejects with `SessionError` code `lease_conflict`; storage/open/validation failures retain the existing Session error classifications. A5 adds `lease_conflict`, `lease_lost`, and `lease_released` to `SessionErrorCode`. These are expected high-level repository failures and reject rather than introduce a second result union. Acquisition has no wait, timeout, queue, steal, retry, or takeover behavior.

Each successful acquisition mints one unguessable lease token held only by the Adapter and one positive safe-integer generation. Generation is durable per opaque Session and strictly increases on every successful acquisition, including the first reacquisition after explicit release; a failed acquisition does not advance it. Token and generation jointly fence authority. Neither is accepted from the caller. The public lease exposes generation only for diagnostics and downstream generation binding; it never exposes the token.

The leased `session` is a Pi-owned guarded `Session`, not the repository's raw storage-backed Session. Every public Session read, mutation, branch/compaction operation, raw `appendBatchIfLeaf`, A4 prepare/lookup, and storage access first passes the same live token/generation guard. `getStorage()` on a repository-leased Session rejects `lease_lost` while live as well as after loss or release; callers cannot obtain raw `SessionStorage` and bypass the guard. Internal A4 preparation captures the lease generation, and preview/seal remain append-free. Its commit rechecks token/generation immediately within the serialized mutation step before authoritative refresh/CAS/append. Lease loss or release makes an old prepared or sealed handle's commit reject `lease_lost` or `lease_released` and append zero entries. No previously returned raw Session/storage reference exists to bypass these checks.

`release()` is idempotent for the owning lease. Its first call serializes behind already-entered Session mutations, permanently retires that lease generation, and relinquishes ownership only when the Adapter's stored token/generation still match authoritative ownership. It resolves only after later calls through the old lease are fenced. A repeated call resolves without changing state. If authoritative ownership no longer matches, release rejects `lease_lost`, does not remove another owner's claim, and the old lease remains fenced. Loss is permanent for that lease; no method refreshes, renews, or reacquires it. Reacquisition is a new repository call and a new lease object.

The new Adapters follow current repository naming while remaining distinct from the legacy raw interface: `InMemorySessionRepository` and `JsonlSessionRepository` implement `SessionRepository`; existing `InMemorySessionRepo` and `JsonlSessionRepo` continue to implement only legacy `SessionRepo`. The legacy `create/open/list/delete/fork` and raw `Session.getStorage()` surface is migration-only and is not extended onto the leased repositories. Provisioned Sessions live in a distinct repository-owned catalog/JSONL namespace that legacy metadata/path discovery and `open` cannot address. New Workspace/runtime composition accepts only `SessionRepository` and `SessionLease`; it cannot accept `SessionRepo`, raw `Session`, metadata, or storage. Backward compatibility is not promised by default: callers migrate explicitly from the legacy repository to provisioning, and no legacy handle can open or mutate a provisioned Session.

Memory and JSONL Adapters implement the same public behavior. Two Memory repositories contend only when constructed over the same explicit repository state/catalog; that shared state owns opaque-reference resolution, Session data, generation, and the atomic owner slot. A Memory repository instance is not implicitly process-global. Its provision, acquire compare-and-set, guarded operation, and release execute under one catalog-owned serialization queue. Failed Memory provisioning rolls back the catalog entry and claim before rejection.

The JSONL Adapter requires one new generic filesystem capability at the existing `FileSystem` seam in `packages/agent/src/harness/types.ts`; it is not a Session-repository-only callback:

```typescript
type ExclusiveFileCreateResult =
	| { readonly kind: "created" }
	| { readonly kind: "already_exists" }
	| { readonly kind: "unavailable"; readonly error: FileError };

interface FileSystem {
	createFileExclusive(
		path: string,
		content: string | Uint8Array,
		abortSignal?: AbortSignal,
	): Promise<ExclusiveFileCreateResult>;
}
```

Like every `FileSystem` operation, `createFileExclusive` never throws or rejects. `created` means this call atomically published the complete supplied bytes at a previously absent destination. `already_exists` means this call published no bytes because an object already owned the destination name. `unavailable` contains the existing closed `FileError`; this call published no destination object and did not alter an existing one. In particular, implementations may not implement it as `exists()` followed by `writeFile()`, may not report an empty or partial destination as `created`, and must not overwrite, append to, truncate, or remove a pre-existing destination.

`NodeExecutionEnv` is the production Adapter owner. It must finish writing a unique temporary file in the destination directory and then use one same-filesystem atomic no-replace publication operation, such as a hard-link create, to bind that complete file to the destination name. Destination-exists maps to `already_exists`; abort, permission, directory, space, temporary-write, or publication failure maps to `unavailable` with the existing `FileError` classification. A failure before publication removes only this call's temporary file. After successful publication the result is `created`; removing the now-unlinked or orphaned temporary name is best-effort and cannot downgrade the authoritative complete destination into `unavailable`. The production implementation and `nodejs-env.test.ts` own platform conformance, including two independent callers producing exactly one `created`, one `already_exists`, and one complete winning value. Any structural test `FileSystem` used by JSONL Session tests must implement this capability directly with the same closed outcomes; it may not fake exclusivity with a preflight existence check.

The production JSONL Adapter resolves an opaque reference beneath its configured repository root and never accepts a caller path. It canonicalizes and validates the resolved Session and lease paths as descendants of that root before mutation. Cross-repository-instance and cross-process ownership uses `createFileExclusive` to publish one complete lease record adjacent to the Session. The record contains protocol version, opaque Session identity digest, proposed generation, and token. Before publication, the contender authoritatively reads the last retired generation, validates it, and proposes exactly `lastRetiredGeneration + 1`; only `created` makes that proposed generation live. `already_exists` rejects acquisition with `SessionError` code `lease_conflict`, advances no generation, opens no writable Session, and appends nothing. `unavailable` rejects acquisition with `SessionError` code `storage` and the `FileError` as cause, returns no lease or Session, advances no generation, and leaves no destination claim from that call.

The complete exclusively created lease record is the only live-ownership authority. A generation metadata file, an in-memory cache, PID, timestamp, existence preflight, or successfully opened JSONL Session cannot independently establish ownership. Every guarded operation and A4 commit re-reads and validates the complete claim record's protocol, Session digest, generation, and token before touching Session bytes. Explicit release first validates that exact claim, then durably records its generation as the last retired generation. If that retirement write fails, release returns `lease_lost`/storage failure as applicable and does not remove the claim. Only after successful retirement may release remove that exact claim. Reopen after explicit release reads the retired generation and performs a full authoritative JSONL validation before a new exclusive-create attempt can return a guarded Session. This ordering makes successful reacquisition strictly advance generation without a second live ownership authority.

A5 does not define TTL, renewal, heartbeat, PID liveness, stale-lock deletion, process-crash takeover, administrator recovery, power-loss recovery, network-filesystem locking, or automatic retry. A process crash may therefore leave the Session unavailable. Those capabilities require a later contract. A5 also does not reconstruct an A3.2 prepared value, token, registry record, or provider permit after reopen.

Focused acceptance is fixed at `packages/agent/test/harness/session-repository-lease.test.ts` and tests only the public repository/lease/Session seam, with shared Memory/JSONL fixtures and no private reducer:

- one lease reads and writes through its guarded Session for both Adapters;
- a second live writer is rejected for both Adapters and appends nothing;
- explicit release permits reacquisition with a greater generation;
- every old-lease read/write and raw `appendBatchIfLeaf` rejects after release or loss and appends nothing;
- an A4 sealed before release/loss cannot commit afterward and appends nothing;
- two independent JSONL repository instances competing for one opaque Session yield exactly one writer;
- after parent-process `provision`, the parent sends the same complete ref through controlled child IPC or child stdin to two real Node child processes; each child constructs an independent JSONL repository instance and calls `acquire`, yielding exactly one writer;
- after explicit JSONL release, an independent repository instance authoritatively reopens and reacquires the Session.

The focused file targets approximately six to eight scenarios by sharing fixtures and combining equivalent guard assertions. Passing it attributes only A5's PNW-16 and PNW-22 concurrency/reopen portion. It does not claim crash takeover, ignored-abort fencing, A6, complete A3.2, full PNW-A, or Workspace integration.

The child-process acceptance must not place the ref in command-line arguments, environment variables, filenames, process titles, diagnostics, snapshots, or logs. IPC/stdin payload handling treats it as secret capability material and does not echo it. Child results report only acquired/conflict/failure classification and test-owned non-secret synchronization data. No bootstrap, registration, raw-open, or path exchange is permitted.

### 6.9 PNW-A6 executable AgentHarness run-generation contract

A6 is an opt-in `AgentHarness` capability. Construction accepts
`runGenerationFencing: { retirementTimeoutMs: number }`; omission preserves the
ordinary Harness Interface exactly, including `prompt`, `abort`, incremental
persistence, event ordering, and its existing cooperative-abort wait. The timeout
is a positive safe integer fixed for the Harness lifetime. A6 adds one public
operation and one closed result:

```typescript
type AgentHarnessRunRetirementResultV1 =
	| { readonly kind: "no_active_run" }
	| {
			readonly kind: "retired";
			readonly runId: string;
			readonly runGeneration: number;
			readonly localOutcome: "cancelled" | "failed";
	  };

interface AgentHarnessRunGenerationInterfaceV1 {
	retireRun(): Promise<AgentHarnessRunRetirementResultV1>;
}
```

`retireRun()` never accepts a caller generation, timeout, signal, Session,
settlement, or provider value. It is non-throwing for `no_active_run`, an already
claimed retirement, an ignored abort, and late provider/tool completion. The
first concurrent caller for one active generation owns retirement; followers
join that same operation and receive the same frozen object. Hook, Session,
save-point, or settlement failures before the local terminal is published close
that generation as `failed`; invariant misuse may still reject with the existing
typed Harness failure. `retirementTimeoutMs` bounds waiting for already-entered
local callbacks only. Once the bound expires, the Harness detaches them and
returns `retired`; it never waits for provider or tool cooperation. A detached
callback retains the retired owner and can reach no sink.

The Harness exclusively mints `runId` and a monotonically increasing safe-integer
`runGeneration` synchronously after the idle-to-turn claim and before the first
await of each A6-enabled public Run. One private owner object binds that identity,
its abort controller, terminal claim, save point, Provider Dispatch generation,
tool admission/execution, settlement, and every sink below. It is never exported
or reconstructible from the numeric generation. A new Run receives a fresh owner
and may start immediately after the prior local retirement publishes `settled`,
even while the retired provider or tool remains unresolved. An old continuation
cannot consult mutable "current Run" state and thereby acquire the new owner.

Retirement has one synchronous linearization prefix: claim the owner's terminal
as `retired`, abort its signal, permanently close provider/tool admission and all
generation sinks, and detach the Harness's current-owner slot. From that point,
the following old-generation activity is a no-op before touching application or
Session state:

- provider stream start, delta, partial/final assistant message, provider result,
  and `after_provider_response` observer;
- tool-call proposal/preflight, `beforeToolCall`, tool Adapter start, update,
  `afterToolCall`, final result, tool-result message, and follow-up provider turn;
- every ordinary or transactional Session append, pending write, save-point
  policy call/commit/event, final-save-point evidence mutation, and Agent Run
  settlement prepare/application/verify/commit/lookup/event;
- every public Agent/Harness event, subscriber/hook, publication callback, queue
  callback, and returned-message mutation not explicitly named as the local
  retirement terminal sequence below.

Tool execution that entered its Adapter before the claim may continue remotely,
but its updates and result are discarded. A proposal or preflight that has not
entered the Adapter at the claim starts zero tools. Provider Dispatch retirement
uses the same owner and precedes any later permit consumption. The ordinary
unprotected provider path applies the identical generation checks immediately
before Adapter entry and at every stream callback; `AbortSignal` alone is not the
fence.

The loop's original `agent_end` enters a Pi-private buffer as the normal terminal
candidate. Buffering performs zero public/subscriber/publication/Session or
settlement work. Exactly one synchronous owner cutpoint chooses between normal
completion, failure, and retirement and freezes either that buffered normal
candidate or one synthetic retired candidate. Normal completion may claim only
after the final save-point commit has produced its evidence and immediately
before Agent Run settlement begins. It may not publish the buffered candidate
before claiming. Once completion owns the claim, `retireRun()` joins the bounded
local completion and cannot relabel or recommit it. If retirement claims first,
the open save point rolls back, no final-save-point evidence or settlement work
can begin, and a late commit acknowledgement cannot upgrade the retired outcome.
If completion has claimed, settlement alone may finish once; retirement cannot
create a second terminal. The losing terminal candidate and every callback whose
captured owner is no longer current reach zero sinks. Thus a retirement-versus-
final-save-point/settlement race has one winner, at most one save-point commit,
at most one settlement commit, and exactly one published `agent_end`.

After the claim, both normal and retired winners use the single A6 awaited order
`save point -> settlement -> publish buffered agent_end -> idle -> settled -> resolve`.
The retirement branch's settlement step is the frozen zero-work
`no_final_save_point`/local-retirement result where no committed basis exists; it
never invents a settlement commit. Expanded:

1. finish the claimed save point, or rollback/close it and pending writes without
   accepting old-generation application callbacks;
2. finish exactly one already-claimed normal settlement or the retired zero-work
   settlement result;
3. publish exactly the selected `agent_end`: the buffered normal candidate for a
   normal winner, or the synthetic old-generation candidate carrying only the
   local cancelled/failed terminal message for a retirement winner;
4. clear the current owner and set Harness phase to `idle`;
5. emit exactly one Harness `settled` event;
6. resolve the active prompt and every joining `retireRun()` caller with their
   frozen local terminal/result.

Each selected `agent_end` subscriber and `settled` subscriber is awaited in
registration order. A thrown hook/subscriber error is captured as the winner's
single `failed` local outcome, does not select or publish another terminal, and
does not skip the phase-to-idle and `settled` steps; the public prompt/retirement
operation then rejects only through the existing normalized Harness hook failure.
The next Run cannot start before step 4 and must be accepted after it. These
terminal callbacks run at most until the configured local bound; a still-pending
or late-resolving callback after detachment has no owner authority and reaches no
additional sink. With A6 omitted, the existing ordinary loop event delivery,
awaited subscriber errors, phase/idle ordering, `abort()` behavior, and public
results remain byte-for-byte/interface-for-interface unchanged. A6 does not
promise cancellation of remote
cost, provider-stream resumption, retry, crash recovery, Workspace publication
implementation, or I&E behavior.

Focused acceptance is fixed at
`packages/agent/test/harness/agent-harness-run-generation.test.ts` and exercises
only public construction options, `prompt`, `promptWithSettlement`, `retireRun`,
`subscribe`, `on`, and deterministic fake provider/tool/Session/application
ports. It must not import, expose, or fabricate the private owner, terminal
reducer, event buffer, registry, or settlement reducer. It contains exactly these
six named scenarios and assertions:

1. **`retires an ignored provider within the bound and admits the next Run`**:
   before retirement the first Run publishes exactly `agent_start`, `turn_start`,
   user `message_start`, user `message_end`; retirement then publishes exactly
   synthetic `agent_end`, `settled` in that order, returns one frozen `retired`
   result to all callers, resolves the first prompt with one cancelled/failed
   assistant result, and admits a second prompt whose ordinary normal terminal is
   exactly one buffered-normal `agent_end` followed by one `settled`; provider
   starts are exactly two while the first provider remains unresolved.
2. **`fences every late provider and application sink after retirement`**: after
   the retirement claim, injected provider delta/final/result/response-observer
   callbacks produce exactly zero message/update/response events, zero Session
   appends, zero save-point or settlement calls/events, and zero publication
   callbacks; the only post-claim public events are one synthetic `agent_end` and
   one `settled`, in that order, and the prompt/retirement expose one local
   terminal each.
3. **`fences late tool proposal and entered-tool update/result independently`**:
   a proposal released after retirement causes exactly zero tool Adapter starts,
   tool events, tool-result messages, Session appends, and follow-up provider
   starts; in a second Run an Adapter entered exactly once before retirement, but
   its late update and result cause exactly zero update/end/tool-result events,
   Session appends, and follow-up starts. Each Run publishes exactly one
   `agent_end` then one `settled` and one local terminal result.
4. **`retirement wins before final save-point commit`**: with the public
   save-point policy paused before commit, retirement wins once; the Session has
   exactly zero staged/receipt appends, settlement create/verify/commit calls are
   zero, the late policy resolution produces zero events, and public order is one
   synthetic `agent_end`, one `settled`, then prompt/retirement resolution.
5. **`completion and retirement share one settlement terminal claim`**: the
   public fake ports deterministically exercise both sides of the cutpoint. A
   retirement winner has zero final-save-point and settlement commits; a
   completion winner has exactly one final-save-point commit, one create, one
   verify, one settlement commit, one `agent_run_settlement`, one buffered-normal
   `agent_end`, and one `settled` in that order. The loser adds zero event, commit,
   callback, or second terminal in either branch.
6. **`preserves ordinary Harness behavior when run-generation fencing is omitted`**:
   `retireRun` is absent from the ordinary public Interface, existing `prompt`,
   `promptWithSettlement`, and cooperative `abort` results are unchanged, and a
   deterministic normal prompt retains its exact historical event order and
   incremental/transactional Session counts from the existing focused tests.

Passing attributes only A6's
ignored-abort/local-sink portions of PNW-04, PNW-17, PNW-22, and PNW-27.

### 6.10 PNW-E crash-recovery contract candidate

This section is the sole normative candidate for PNW-E crash recovery. It has
not received independent design review. Implementation and focused tests are
forbidden until an independent Terra reviewer returns an explicit design PASS.
It extends A5 only through an explicit administrative recovery operation; it
does not add TTL, heartbeat, PID liveness, automatic stale-lock detection, or
ordinary `acquire` takeover.

The public repository Interface adds exactly one operation. Recovery-capable
repository construction requires one closed `PiSessionRecoveryOptionsV1`;
callers cannot supply or replace either port per call.

```typescript
interface SessionRepository<TMetadata, TProvisionOptions> {
	provision(options: TProvisionOptions): Promise<ProvisionedSession<TMetadata>>;
	acquire(opaqueRef: SessionRepositoryOpaqueRef): Promise<SessionLease<TMetadata>>;
	recover(opaqueRef: SessionRepositoryOpaqueRef): Promise<SessionRecoveryResultV1<TMetadata>>;
}

interface SessionRecoveryAuthorityV1 {
	authorize(input: {
		readonly protocol: "pi-session-recovery-authorization/v1";
		readonly sessionId: string;
		readonly abandonedGeneration: number;
	}): Promise<
		| { readonly kind: "authorized"; readonly bindingDigest: PiDigestV1 }
		| { readonly kind: "denied"; readonly code: string }
		| { readonly kind: "unavailable"; readonly code: string }
	>;
}

interface PiSessionRecoveryOptionsV1 {
	readonly authority: SessionRecoveryAuthorityV1;
	readonly application: PiAgentRunRecoveryApplicationV1;
}

interface PiAgentRunRecoveryClassifierProofV1 {
	readonly protocol: "pi-agent-run-recovery-classifier-proof/v1";
	readonly sessionId: string;
	readonly abandonedLeaseGeneration: number;
	readonly runId: string;
	readonly runGeneration: number;
	readonly finalMarkerEntryId: string;
	readonly finalMarkerEntryDigest: PiDigestV1;
	readonly finalMarkerDigest: PiDigestV1;
	readonly finalSavePointEntryId: string;
	readonly finalSavePointEntryDigest: PiDigestV1;
	readonly settlementExpectation: "required";
	readonly authorityBindingDigest: PiDigestV1;
	readonly proofDigest: PiDigestV1;
}

interface PiAgentRunRecoveryPreviewV1 {
	readonly sessionId: string;
	readonly expectedLeafId: string;
	readonly terminalEntryId: string;
	readonly terminalParentId: string;
	readonly terminalTimestamp: string;
}

interface PiAgentRunRecoveryDiscardTerminalV1 {
	readonly protocol: "pi-agent-run-recovery-discard/v1";
	readonly classifierProofDigest: PiDigestV1;
	readonly sessionId: string;
	readonly runId: string;
	readonly runGeneration: number;
	readonly abandonedLeaseGeneration: number;
	readonly finalMarkerEntryId: string;
	readonly finalMarkerDigest: PiDigestV1;
	readonly finalSavePointEntryId: string;
	readonly finalSavePointEntryDigest: PiDigestV1;
	readonly terminal: "discarded";
	readonly authorityBindingDigest: PiDigestV1;
	readonly recoveryTransactionId: string;
	readonly applicationData: PiCanonicalJsonV1;
	readonly applicationReceiptDigest: PiDigestV1;
}

type PiAgentRunRecoveryApplicationResultV1<T> =
	| { readonly kind: "accepted"; readonly value: T }
	| { readonly kind: "denied"; readonly code: string }
	| { readonly kind: "unavailable"; readonly code: string };

interface PiAgentRunRecoveryApplicationV1 {
	readonly customType: string;
	validateSettled(input: {
		readonly classifierProof: PiAgentRunRecoveryClassifierProofV1;
		readonly terminal: { readonly customType: string; readonly data: PiCanonicalJsonV1 };
	}): Promise<PiAgentRunRecoveryApplicationResultV1<{ readonly verificationBindingDigest: PiDigestV1 }>>;
	createDiscard(input: {
		readonly classifierProof: PiAgentRunRecoveryClassifierProofV1;
		readonly preview: PiAgentRunRecoveryPreviewV1;
		readonly recoveryTransactionId: string;
	}): Promise<
		PiAgentRunRecoveryApplicationResultV1<{
			readonly applicationData: PiCanonicalJsonV1;
			readonly applicationReceiptDigest: PiDigestV1;
		}>
	>;
	verifyDiscard(input: {
		readonly classifierProof: PiAgentRunRecoveryClassifierProofV1;
		readonly preview: PiAgentRunRecoveryPreviewV1;
		readonly terminal: PiAgentRunRecoveryDiscardTerminalV1;
	}): Promise<PiAgentRunRecoveryApplicationResultV1<{ readonly verificationBindingDigest: PiDigestV1 }>>;
}

type SessionRecoveryResultV1<TMetadata> =
	| {
			readonly kind: "recovered";
			readonly source:
				| "no_final_save_point"
				| "recovery_discard_committed"
				| "settlement_exact_present";
			readonly lease: SessionLease<TMetadata>;
	  }
	| { readonly kind: "denied"; readonly code: string }
	| {
			readonly kind: "unavailable";
			readonly reason: "authorization_unavailable";
			readonly code: string;
	  }
	| {
			readonly kind: "unavailable";
			readonly reason:
				| "no_recovery_authority"
				| "claim_changed"
				| "io"
				| "invalid_or_truncated"
				| "unsupported";
	  }
	| { readonly kind: "conflict" };
```

`recover` is never an automatic or evidentiary judgment that a process died.
Invoking it is an explicit administrative request to abandon the currently
published A5 claim. Pi snapshots the complete authoritative claim, supplies
only its non-secret Session identity and generation to the configured
authority, requires one closed `authorized` result, then rechecks that the
complete claim is byte-identical before any recovery write. Denial, callback
failure, malformed result, changed/missing claim, or unavailable storage
returns a closed non-success result and changes nothing. The authority binding
digest is retained in the recovery-discard terminal. It is not a lease token,
does not attest process death, and grants no Session, Provider, Tool, permit, or
A4 prepared-handle authority.

All recovery options, callback inputs, and callback results are closed,
recursively snapshotted, canonical-data bounded, and use the identifier/digest
grammars in sections 5.1 and 6.7. `validateSettled` is called once only for a
physically complete ordinary or recovery settlement. For a missing settlement,
Pi fixes the recovery transaction and terminal preview, calls `createDiscard`
once, constructs the complete Pi-owned
`PiAgentRunRecoveryDiscardTerminalV1`, then calls `verifyDiscard` twice with
identical snapshots before recovery-owner publication, with the second call
immediately before that publication. Both accepted verification-binding digests
must match; the owner freezes that proof so roll-forward performs no callback.
Application code owns only `applicationData`, its receipt digest, and business
validation meaning; Pi owns the envelope, classifier proof, preview, transaction
identity, materialization, and ordering. The application receives no raw
storage/JSONL line, claim, lease, token, A4 capability/handle, Provider/Tool
value, or resident Run object.

A callback `denied` maps to recovery `denied` with its validated code. Callback
`unavailable`, throw, malformed/unknown result, unsupported canonical value,
receipt mismatch, or verification drift maps to `unavailable` reason
`authorization_unavailable`, with Pi-reserved diagnostic code
`callback_threw`, `invalid_result`, `invalid_application_terminal`, or
`verification_drift`. Every such branch changes nothing and Pi never retries a
callback. `validateSettled` acceptance recognizes a terminal only after its
Run/generation/final-marker/final-save-point fields already exactly match the
physical classifier proof.

After authorization, JSONL recovery uses one physical classifier over the
authoritative bytes. It parses the header and every newline-terminated record
without dropping blank, malformed, or duplicate records. A nonempty final byte
sequence without a terminating newline, invalid JSON, unsupported record,
duplicate entry ID, broken parent chain, noncanonical protected entry, partial
settlement group, more than one terminal for one Run identity, or settlement
whose materialized fields/digests/signature do not match its final save point is
`invalid_or_truncated` or `conflict` as applicable. Recovery never truncates,
repairs, skips, reorders, or guesses through such bytes.

The classifier physically recomputes every marker, save-point entry, settlement
entry, and batch digest. It pairs a settlement only with the most recent
unmatched final marker carrying the same Session, `runId`,
`runGeneration`, final entry ID/digest, and settlement expectation. It never
uses custom-type coincidence, leaf position alone, or an application callback to
bridge a Run/generation mismatch. The classifier has only these successful
histories:

For an ordinary settlement, matching custom type or application data is never
physical proof. Recovery must load the private sidecar at the exact deterministic
key, validate its complete existing settlement/A4 evidence against the marker
and materialized terminal, and obtain authoritative `lookupControlBatch ==
exact_present` before calling `validateSettled`. Missing, partial, duplicate,
conflicting, corrupt, wrong-key, wrong-Run/generation/final binding, or
non-exact lookup evidence fails closed with zero application callback. Memory
uses the same catalog/result semantics; JSONL durably publishes and reopens the
sidecar. Recovery never reconstructs or replays the sealed A4 handle.

The physical classifier also validates the prepared-journal/final-sidecar/
cleanup-tombstone transition above. It cannot accept a final sidecar whose
source journal was neither retained nor recoverably tombstoned, and it cannot
turn a prepared-plus-absent state into settlement evidence.

- no committed final save point for the unfinished Run: the abandoned claim is
  retired and a new lease may be acquired without a recovery terminal;
- one final save point with no settlement: exactly one authenticated
  `discarded` recovery settlement must be appended;
- one complete valid settlement: it is recognized as exact-present and no
  terminal is appended.

The recovery-discard is one terminal-only A4-canonical control batch whose
expected leaf is the classified final-save-point entry. PNW-E does not claim an
instantaneous atomic write across the Session JSONL, retired-generation file,
and claim file. Instead the repository owns one recoverable transaction journal.
Preparation fixes one unguessable `recoveryTransactionId`, old-claim digest,
abandoned and next generations, classifier proof, deterministic terminal ID and
bytes, complete A4 evidence/digests, and authority/application verification
bindings. Preparation changes no authoritative file.

The linearization point is atomic no-replace publication of one complete
`pi-session-recovery-owner/v1` record adjacent to the Session. Every A5 guard is
extended to require both its exact claim and absence of a recovery-owner record;
publication therefore permanently fences the abandoned lease before any Session
or generation mutation. Before publication the old A5 claim is sole authority.
From publication through cleanup the recovery record is sole authority, and no
`acquire`, second `recover`, old lease, or partial recovery may independently
write.

The immutable owner contains deterministic identities and digests, not claim
tokens, application plaintext, or Provider/Tool values. Its apply protocol is:

1. **prepare:** classify and verify all fixed intended bytes; a crash leaves only
   the old claim and original history;
2. **publish owner:** exclusive-create the complete owner; on reopen the one
   matching owner resumes, while a different owner is `conflict`;
3. **apply discard:** if required, authoritative lookup must find exact A4-batch
   absence at its expected leaf or the one exact batch; absence appends the fixed
   bytes once, exact presence advances, and partial/different/later-leaf evidence
   is `conflict` without append;
4. **retire generation:** durably write the exact abandoned generation and fixed
   next-generation basis idempotently; lower, higher, or different data is
   `conflict`;
5. **commit:** atomic no-replace publication of a complete
   `pi-session-recovery-committed/v1` record binds owner digest, classified
   settlement/discard evidence, retired generation, and next generation; its
   presence is the sole committed-recovery classification;
6. **cleanup:** remove the old claim only when its complete digest matches the
   owner, then retire/remove the owner name. Cleanup failure cannot undo commit;
   reopen repeats cleanup before acquisition.

Every repository open, `recover`, and `acquire` checks this journal first. A
matching owner without commit rolls forward steps 3-6 from its fixed bytes; it
never rolls back a published owner or rematerializes an ID. A claim with no owner
is old authority. A valid commit is committed recovery even if old-claim or
owner cleanup remains. Missing, partial, corrupt, or mutually inconsistent
owner/commit/Session/generation data is unavailable/conflict and admits no
writer. Thus every crash cutpoint is either old authority or one committed
recovery, never two writers or a repeated discard. Only after commit, cleanup,
full authoritative reload, and a new exclusive A5 claim may `recover` return a
guarded lease with a strictly greater generation.

Recovery reconstructs no Harness and replays no Provider request/stream, Tool
proposal/call/result, queue, pending callback, permit, A4 prepared/sealed handle,
event, public terminal, or publication callback. The returned lease is idle;
only a later explicit public Turn may create a new Run identity. Memory uses the
same result semantics with its shared catalog; crash-orphan behavior itself is
proved by production JSONL and a real child process.

Focused acceptance is fixed at
`packages/agent/test/harness/session-recovery.test.ts` and contains exactly seven
scenarios through only `SessionRepository.provision`, `acquire`,
`recover`, returned guarded `Session`, and deterministic application/authority
ports: crash before final save point; final save point without settlement
produces one recovery discard across repeated recovery; valid settlement is
recognized without duplication; partial/conflicting settlement fails closed;
corrupt/truncated JSONL is unavailable; an explicitly authorized crashed-child
orphan claim permits authoritative reopen with a greater generation; and every
scenario observes zero Provider/Tool replay. Tests must not import a classifier,
claim path, lease token, settlement reducer, or A4 prepared handle.

The existing partial/conflicting-settlement scenario also copies a legal
ordinary terminal's public protocol/Session/Run/generation/final/custom type and
application data while omitting or forging its private sidecar/A4 evidence. A
permissive fake `validateSettled` is called zero times and recovery conflicts.
This remains one of the exactly seven named scenarios; it adds no eighth case.

## 7. Session eligibility, receipt trust, and the stale-marker replacement

Workspace owns the CTI meaning of one save-point receipt while Pi owns the generic expected-leaf transaction envelope. The closed v1 semantic payload is:

```typescript
interface ContextSnapshotReceiptV1 {
	protocol: "workspace-context-snapshot-receipt/v1";
	receiptId: string;
	workspaceRef: string;
	sessionRefBindingDigest: string;
	branchRef: string;
	agentRunId: string;
	piTurnId: string;
	savePointSequence: number;
	purpose: "task_context_planning" | "response" | "product_tool" | "final_response";
	expectedSessionLeaf: string;
	previousContextSnapshotReceiptDigest: string | null;
	orderedGroupEntryDigests: readonly string[];
	contextProjectionDigest: string;
	contextDependencies: readonly ContextSnapshotDependencyV1[];
	task: ContextSnapshotSlotV1;
	taskContext: ContextSnapshotSlotV1;
	orientation: ContextSnapshotSlotV1;
	workingSet: ContextSnapshotSlotV1;
	configurationSnapshotDigest: string;
	receiptDigest: string;
	authenticity: ContextSnapshotAuthenticityV1;
}

interface ContextSnapshotDependencyV1 {
	dependencyKey: string;
	contextGeneration: string;
	generationControlEntryDigest: string;
	projectedContentDigest: string;
}

type ContextSnapshotSlotV1 =
	| { presence: "absent" }
	| { presence: "present"; ref: string; semanticDigest: string };

interface ContextSnapshotAuthenticityV1 {
	algorithm: "HMAC-SHA-256";
	keyId: string;
	signedPayloadDigest: string;
	macBase64Url: string;
}

type ContextSnapshotCanonicalJsonV1 =
	| null
	| boolean
	| number
	| string
	| readonly ContextSnapshotCanonicalJsonV1[]
	| { readonly [key: string]: ContextSnapshotCanonicalJsonV1 };

interface ContextSnapshotGroupEntryDigestBasisV1 {
	protocol: "pi-session-entry-digest-basis/v1";
	entry: { readonly [key: string]: ContextSnapshotCanonicalJsonV1 };
}

interface ContextSnapshotProjectionItemV1 {
	position: number;
	kind: "session_entry" | "task_context" | "orientation" | "working_set" | "workspace_control";
	sourceRef: string;
	sourceSemanticDigest: string;
	renderedContentDigest: string;
}

interface ContextSnapshotProjectionDigestBasisV1 {
	protocol: "workspace-context-projection-digest-basis/v1";
	purpose: "provider" | "compaction" | "branch_summary";
	systemPromptDigest: string;
	orderedItems: readonly ContextSnapshotProjectionItemV1[];
	contextPolicyRevision: string;
}

interface ContextGenerationVectorDigestBasisV1 {
	protocol: "workspace-context-generation-vector/v1";
	orderedDependencies: readonly ContextSnapshotDependencyV1[];
}
```

Each group-entry digest is SHA-256 over UTF-8 JCS of `ContextSnapshotGroupEntryDigestBasisV1`. Its `entry` is the complete materialized current Pi `SessionTreeEntry`, including `type`, `id`, `parentId`, `timestamp` and every type-specific field. Before Workspace policy signs the receipt, Pi pre-materializes the immutable candidate group exactly once with final IDs, parent chain and timestamps and exposes that read-only preview through the save-point facade; commit may append only those unchanged entries at the captured expected leaf. Rollback discards the preview, and acknowledgement recovery looks up those exact IDs rather than rematerializing. V1 admits only the current closed entry types `message`, `thinking_level_change`, `model_change`, `active_tools_change`, `compaction`, `branch_summary`, `custom`, `custom_message`, `label`, `session_info`, and `leaf`; unknown entry types/members, functions, symbols, `undefined`, cycles, non-finite numbers or non-JCS nested message/custom/details values fail before commit. Thus `orderedGroupEntryDigests` covers every entry earlier in the same save-point group in physical append order and excludes the receipt itself.

`contextProjectionDigest` is SHA-256 over UTF-8 JCS of `ContextSnapshotProjectionDigestBasisV1`. `orderedItems` is the actual post-policy projection order before provider/compaction/branch-summary conversion; positions are unique contiguous zero-based integers. `renderedContentDigest` covers the exact UTF-8 JCS-valid rendered content item, while `sourceRef`/`sourceSemanticDigest` explain its origin. The system prompt and policy revision are always bound, including when there are zero items.

`contextDependencies` is the exact dependency set actually projected for that turn, sorted by qualified canonical dependency key; it cannot include a dependency that was not rendered or omit one that was. `contextGenerationDigest` wherever used by a consumer is SHA-256 over UTF-8 JCS of `ContextGenerationVectorDigestBasisV1` built from this same ordered list. Duplicate keys, noncanonical order or any digest/list mismatch fails closed. Each slot uses explicit presence and binds the exact admitted identity/digest used by that save point.

`receiptDigest` is SHA-256 over UTF-8 JCS of the complete receipt without `receiptDigest` and `authenticity`. The authenticity payload is UTF-8 JCS of the complete receipt without `authenticity`; `signedPayloadDigest` is its SHA-256 and the HMAC covers those exact bytes. `savePointSequence` is a positive monotonic integer within one Agent Run. The predecessor is the latest valid Context Snapshot receipt on the committed branch basis, or `null` only for the first receipt admitted for that Workspace/branch. Unknown members, duplicate dependency keys, noncanonical order, predecessor mismatch, generation mismatch, slot inconsistency, group-entry mismatch, unknown key, digest/MAC failure or expected-leaf conflict rolls back the complete save-point group.

Task Context and IWS contracts add their records before this receipt but do not redefine it. A planning receipt has no Working Set slot; a product-tool receipt binds the resulting Working Set selection when one is committed. Pi may expose a generic application-receipt slot, but it never interprets these CTI fields.

A signed save-point receipt proves the exact committed entries, actual model-visible dependency generations, Session binding, Workspace/Agent Run identity, and message/tool-result digests. HMAC remains the current integrity Adapter; a public digest is not authentication. HMAC does not prove that a storage administrator did not truncate the append-only tail, so anti-rollback requires a separately trusted head anchor if that threat enters scope.

The business need behind the current stale marker remains: equality alone would revive old A prose after `A -> B -> A`. The standalone marker is not retained as a long-lived domain concept. Protocol v2 records signed per-dependency `context_generation` checkpoints and revocations:

- a material change or authorization transition monotonically advances only affected dependency generations;
- a save-point receipt binds the generations actually rendered;
- returning to equal content never reuses an earlier generation;
- the eligibility reducer reads all retained append order, not only the current branch, so navigation cannot remove a revocation;
- new post-checkpoint work can use the new generation while dependency-disjoint qualified history remains eligible.

A generation advance becomes authoritative only when its independent Pi control group commits. Detection first advances the in-memory fence and denies or rolls back every intersecting active group; before any later provider request, the ordered Session facade must commit a signed `context_generation_advanced` entry against the expected leaf. Until that succeeds, the Workspace is unavailable for intersecting work. A crash before this commit did not admit the newly observed binding; reopen performs a fresh Orientation observation. A binding admitted after reopen must first commit any required advance.

Each dependency counter is allocated from the last valid retained control entry, includes its predecessor control-entry identity and observation identity, and increases monotonically. Repeating the same authentic observation is idempotent; a missing predecessor, reused counter for different content, duplicate identity with another digest, gap, forged signature, or unknown control type fails closed. The control log is evaluated across retained append order rather than only the active branch. Thus every *committed* `A -> B -> A` admission records two advances, and neither crash nor navigation can turn the first A receipt current again.

`Stale Capsule` stays an optional actor-safe rendering derived from the reducer. It is not persisted evidence, a summary, authority, or a replacement Orientation.

Migration uses dual-read/single-write stages: first read v1 receipts/markers and v2 checkpoints while writing v1, then write v2 while retaining both readers, and remove v1 only after mixed-Session reopen tests and a rollback-safe release boundary.

## 8. Failure, cancellation, concurrency, and recovery

| Scenario | Deterministic result |
|---|---|
| provider or tool partial | remains transaction-local/display-only; no durable Output Claim |
| caller cancellation before commit claim | rollback current save-point group; one `cancelled` terminal |
| close/supersession before commit claim | rollback, retire run generation, and fence all late events/writes/tool dispatch |
| completion claim wins before close | finish the bounded expected-leaf commit, then publish `completed`; do not wait for remote work already outside the generation |
| expected-leaf conflict | append none and discard with Session-binding failure |
| invalidation during provider/tool | deny or roll back the intersecting group; reconcile before another provider request |
| invalidation during reopen | an older read cannot clear the newer receipt sequence; repeat full reopen |
| tool error | Pi records one finalized error outcome; Workspace policy decides whether the complete batch may continue |
| crash before save-point commit | transaction is not durable and the provider/tool attempt is not resumed or spliced |
| crash after final save point but before Run settlement | recover the save point once, append a recovery-discard settlement before new work, and do not re-emit an old public terminal |
| crash after Run settlement | recover the signed terminal once and do not re-emit it or append another terminal receipt |
| generation advance detected | fence/rollback intersecting work, then commit its independent signed control group before another intersecting provider request |
| generation control conflict or signing failure | append none, keep the dependency unavailable, and require reopen/recovery; never fall back to an unsigned counter |
| provider/tool timeout | retire or fail the current generation and apply normal rollback/settlement; this cycle performs no automatic provider or tool retry |
| duplicate or late callback | generation identity and settle-once reducers ignore it; it creates no event, Session entry, tool dispatch, publication, or cost-bearing retry |
| hook, receipt validation, or local publication failure | roll back the affected save-point group and fail closed; dependency-disjoint committed groups remain usable |
| post-tool Orientation reconciliation failure | retain only already committed qualified save points, mark affected dependencies unavailable, and deny the next provider request until reopen succeeds |
| compaction/branch summary | use the same eligible entry policy; stale/protected/legacy bodies never enter its provider input |
| branch behind a revocation | retained generation evidence still excludes earlier intersecting prose |
| concurrent process opens one Session | the Pi repository/lease Adapter must reject or serialize; JSONL expected-leaf alone is not a cross-process claim |
| authorization revocation | zero stale allowance for disclosure; protected recovery may retain only actor-safe integrity facts |
| provider-dispatch receipt commit fails or conflicts | invoke no provider Adapter |
| invalid canonical data, secret binding, application verification, HMAC, identity comparison, or receipt-last order | append zero provider-control entries and invoke no provider Adapter |
| provider-dispatch CAS conflict | A4 performs authoritative refresh and exact lookup; only the one complete matching batch at current leaf `D` is `exact_present`, while the same dispatch ID with any differing field is conflict; duplicates, corrupt entries, missing entries, or a later leaf invoke nothing |
| provider-dispatch acknowledgement is unknown | A4 authoritatively refreshes and looks up the recorded entry IDs plus complete entry digests; never guess absence, never rematerialize, and never create a second receipt |
| receipt committed/present but prepared value, generation, cursor, or permit is not current and resident | retain `may_have_dispatched`; invoke no Adapter and never reconstruct authority from Session evidence |
| cancellation after receipt but before Adapter start | retire the resident permit, retain `may_have_dispatched`, and invoke no Adapter |
| retained A3.1 `start()` returns an error stream or Adapter start fails | retain `may_have_dispatched`; do not retry automatically and settle through the normal generation path |
| crash after provider-dispatch receipt | retain `may_have_dispatched`; never auto-resend, resume, or splice the provider stream |

Provider streams are not resumable. Recovery starts from the last committed Pi save point and a fresh Orientation observation. Session replay never re-executes a tool. The migration performs no automatic provider/tool retry; an explicit later public Turn obtains a new Agent Run identity. A3.2 proves only resident single-runtime pre-start exclusion. Cross-process at-most-one invocation requires the A5 fenced lease, while output/event/Session/tool sinks after an Adapter that ignores abort require the A6 run-generation fence. Future effectful tools require their frozen durable idempotency and reconciliation contracts before any retry can be enabled.

## 9. Cost, performance, and observability

- Normal prompts reuse one Session/Harness and one hook graph rather than constructing them per Turn.
- `open` may scan `O(Session entries)` to verify legacy evidence; subsequent save points update an indexed eligibility reducer in `O(new entries)`.
- Context construction should use head/dependency-generation caches and remain linear in the selected branch, not the full retained log on every provider request.
- Each Pi turn adds one bounded save-point transaction and authenticated receipt; each Agent Run adds one small settlement group, each admitted dependency transition adds one small independent control group, and each provider attempt adds one pre-I/O dispatch group. Oversized batches fail safely; large tool bodies remain in their owning system and Session carries versioned references rather than raw I&E capsules.
- Detached remote work may continue consuming provider resources. Record retired generation count, age, cost, and late callbacks; cap outstanding retired generations per Workspace.
- Safe telemetry covers Workspace/Agent Run/turn/save-point/dispatch IDs, phase, durations, capability recipe, entry counts, token counts, dependency-generation and logical-invocation digests, commit/lookup outcomes, reopen reasons, and terminal code. It excludes prompts, completions, credentials, tool bodies, logical invocation bodies, and Orientation content by default.

## 10. Alternatives and decision

- **Keep per-Turn staging Harness:** preserves delivered safety but keeps two Session/lifecycle models and makes tool/save-point/compaction integration shallow. Rejected as target.
- **Long-lived Harness writing the current caller Session directly:** simplest, but current `message_end` persistence exposes cancelled, invalidated, or conflicted prefixes before the Workspace fence. Rejected.
- **Workspace-owned transactional SessionStorage as the permanent answer:** useful migration bridge, but duplicates generic Harness transaction/pending-write semantics and preserves a mixed ownership model. Rejected as target.
- **Call `runAgentLoop` directly:** recreates persistence, tool, queue, save-point, and tree orchestration in the product. Rejected.
- **Expose Harness/Session to application callers:** makes the common Interface shallow and permits unsynchronized writers. Rejected.
- **Return a retrieval capsule directly into ordinary tool transcript:** is simple but bypasses Working Set admission, current exact-capture revalidation, and provider-input proof. Rejected.
- **Commit a digest after provider transport:** cannot distinguish crash-before-send from crash-after-send and permits unproved retry. Rejected.
- **Persist raw auth/config or a credential-record revision:** exceeds the A3.1 request seam, leaks authority-bearing material, and still does not prove the resolved request actually retained for start. Rejected; bind only resolved request facts with application HMAC ports.
- **Treat `appendBatchIfLeaf` success/timeout plus the process-local cache as acknowledgement:** is smaller but cannot distinguish an unobserved committed batch from absence after JSONL or process failure. Rejected; A4 pre-materialization, authoritative refresh, and exact lookup are prerequisites.
- **Serialize or recreate a permit from a receipt:** appears recoverable but turns `may_have_dispatched` evidence into resend authority. Rejected; permits remain resident, object-bound, current-generation, and single-use.
- **Deepen Pi and keep CTI policy in Workspace:** selected for maximum leverage and locality.

## 11. Migration slices and rollback

1. **PNW-A — Pi lifecycle depth.** Add the generic save-point, Agent Run settlement, control, and Provider Dispatch transactions; transactional Harness configuration; ordered Session facade/context policy; opaque-reference `SessionRepository` and fenced-lease contract; pre-provider denial; finalized tool outcome; and run-generation fence with focused Pi tests. Rollback: opt-in remains unused by Workspace.

   **PNW-A1 delivered boundary:** only the opt-in transactional no-tool save point is implemented and independently accepted. User/assistant turn entries remain pending and unmaterialized through `turn_end`; policy sees a read-only pending view and may admit application custom entries plus one required terminal receipt. Harness captures the expected Session leaf before context construction/system-prompt evaluation, then commits ordered turn entries, application entries, and the physically last receipt with one `appendBatchIfLeaf` CAS. Explicit rollback, policy failure, provider error/abort, or stale-leaf conflict appends none of that staged group. A tool call is blocked at `beforeToolCall`, the staged group rolls back, Pi's turn-stop seam prevents a follow-on provider request, and the prompt rejects once. The transactional `save_point` observer runs only after commit/rollback; a post-commit observer failure cannot undo the committed group or append a failure transcript, settlement still occurs, and the prompt rejects after settlement. The default non-transactional Harness path is unchanged. Direct raw-Session writes remain outside this group and can only make its captured context leaf stale.

   PNW-A1 does not deliver transactional tool results, configuration/queue mutations, Agent Run settlement, control or Provider Dispatch transactions, ordered Session facade/context policy, lease/recovery, compaction, retry, or run-generation fencing. Those capabilities are assigned across PNW-A2 through PNW-A6; A2.1 and A2.2 now deliver only the subsets below, so PNW-A overall is not complete.

   **PNW-A2.1 delivered boundary:** the independently accepted subset adds a stable `HarnessSessionFacade` with committed deep snapshots and source-ordered custom enqueue during an open transaction; recursively isolates facade data, policy views/decisions, receipts, and staged Models; records source/ordinal/materialized-id mapping with the terminal receipt physically last; and stages model, thinking-level, and active-tool changes until the same CAS commits. Rollback, policy/signing failure, conflict, blocked tool attempt, abort, late mutation, or unsupported data exposes none of the staged configuration. Post-commit observer failure preserves the committed Session and published in-memory configuration. Memory and JSONL reopen reconstruct the committed `Session.buildContext()` projection only; they do not automatically construct or restore a Harness runtime.

   A2.1 does not deliver transactional tool execution/results, `setTools` registry/resources/stream-options configuration, context-entry policy or system-prompt mutation, Agent Run settlement, independent control or Provider Dispatch transactions, repository lease/recovery, run-generation retirement, retry/compaction transactions, or automatic Harness restore. The first independent A2.1 review failed on nested ownership aliases and overstated public TSDoc; the repair closed both and the same reviewer passed the whole slice. Explicit Node `v24.14.0` verification passed five focused files and **84/84** tests; the developer root check passed **800 files**. Full PNW-A2 and PNW-A remain incomplete.

   **PNW-A2.2 delivered boundary:** the independently accepted persisted-entry policy subset adds one opt-in application-owned policy over coherent isolated committed Session evidence for `provider`, `compaction`, and `branch_summary`; admits only a source-ordered subset of Pi's default selection; retains append-order evidence needed to observe off-branch invalidation; and fails closed before use on denial, unsupported values, cancellation, leaf drift, or changed selection. Provider qualification is rechecked after context/system-prompt and pre-provider policy work; compaction and branch-summary qualification are rechecked after model work and before structural mutation. Policy state and sensitive configuration are not persisted, and the ordinary path remains unchanged when no policy is configured. The first independent review failed because post-model policy drift could reach structural use; the TDD repair closed that path and the original reviewer passed the entire slice. Seven focused files passed **132/132** under explicit Node `v24.14.0`; the developer root check passed **802 files**.

   A2.2 does not deliver transactional tool execution/results, tool-registry/resources/stream-options/system-prompt configuration, Agent Run settlement, independent control or Provider Dispatch transactions, repository lease/recovery, run-generation retirement, retry transactions, automatic Harness restore, or application CTI eligibility semantics. Full PNW-A2 and PNW-A remain incomplete.

   **PNW-A3.1 delivered boundary:** the independently accepted `packages/ai` subset adds `Models.prepareSimple(...)` with one captured Provider/auth resolution, detached resolved request ownership, projection of structural runtime tool subtypes to the public provider Tool contract, deferred single-use Adapter start, lazy-load isolation, and standard stream errors after start while retaining legacy `streamSimple()` behavior. Its later tool-projection tracer ran RED **1/10** to GREEN **11/11**; five focused AI files passed **44/44**, independent acceptance passed eight files and **81/81**, and the developer root check passed **802 files** under explicit Node `v24.14.0`.

   A3.1 does not deliver Session receipt, canonical logical-invocation artifact, permit, commit/lookup, protected Harness dispatch, run-generation enforcement, or A3.2. Full PNW-A3 and PNW-A remain incomplete.

   **PNW-A4 delivered boundary:** the independently accepted generic pre-materialized Session control-batch Interface is implemented for Memory and JSONL. One preparation authoritatively loads before validation, fixes the expected leaf plus all entry IDs, timestamps, parent links, and a terminal-receipt-last slot; one seal supplies terminal data and freezes complete entry bytes/digests; commit cannot rematerialize. Results distinguish `committed`, `conflict`, and `acknowledgement_unknown`; authoritative refresh plus exact lookup uses the recorded IDs and complete digests and reports only `exact_present`, `absent`, `conflict`, or `unavailable`. Capability absence and authoritative-load failure remain closed zero-work results.

   Developer TDD ran RED **1 failing test** to GREEN **28/28**, then six focused files passed **117/117** and the root check passed. The first independent implementation review returned **FAIL** on a slot-sentinel collision: business JSON shaped like `{ presence: ... }` could be confused with optional-field normalization. The TDD repair made slot interpretation schema-directed and limited it to named optional positions, preserving slot-shaped business JSON in arbitrary canonical-data positions. Final independent acceptance returned **PASS**: the focused A4 file passed **28/28**, five regression files passed **89/89**, public probes passed **4 + 1**, and the root check passed Biome over **805 files** with no fixes. The accepted public operation trace was `prepare -> preview -> sealTerminal -> commit -> lookup`: two IDs were reserved; append-call counts across prepare/seal/commit/lookup were **0/0/1/0**, with the sole append containing two entries; Session events were **0** and provider/network calls were **0**.

   A4 grants no provider permit, performs no application verification, starts no Adapter, and makes no A5 cross-process fencing claim. It therefore does not implement A3.2, full PNW-A3, PNW-A, or Workspace migration.

   **PNW-A3.2 independent boundary — Design PASS; focused implementation/public-seam PASS pending:** after the accepted A3.1 and A4 prerequisites, section 6.6 owns one Pi-private transaction core with a Harness-private frontend and one public already-bound bounded one-shot capability. Both use the same one-time runtime composition, `Models`/Provider/Auth path, binder, authority/authenticator, Session A4/cursor binding, neutral generation registry, prepared-value store, and permit issuer. They retain exact closed canonical bases/budgets, terminal persisted envelope, independent receipt comparison, private `L -> D` cursor advance, resident current-generation single-use permit, and post-prepare exact-count evidence. The one-shot frontend adds no Session, Harness, tools, queues, retry lifecycle, or second transaction. Focused acceptance uses no real paid provider and proves Adapter entry/no-entry plus cross-frontend registry collision through deterministic fakes at the Pi public seam. A3.2 may satisfy PNW-21, PNW-23, PNW-25, PNW-26, PNW-28, PNW-29, the resident single-runtime/pre-start subset of PNW-22, and the pre-start subset of PNW-27. It must not claim complete PNW-22, complete PNW-27, full PNW-A3, PNW-C, or PNW-A.

   **PNW-A5 independent boundary:** add opaque `SessionRepository` acquisition, a fenced single-writer lease shared by memory and production JSONL Adapters, lease-loss denial, authoritative reopen/reload, and cross-process exact-lookup behavior. A5 extends the A3.2 receipt/permit proof to cross-process at-most-one start while the prepared value remains resident; it never reconstructs a permit after crash. A5 acceptance owns the concurrency and recovery portions of PNW-16 and PNW-22, not ignored-abort output fencing.

   **PNW-A6 independent boundary:** add bounded local abort and run-generation retirement across every event, Session, tool-dispatch, response-observer, publication, and settlement sink. A provider that ignores abort may consume remote resources, but cannot start after retirement or splice any late output into the current generation. A6 acceptance completes the ignored-abort/late-output portion of PNW-04, PNW-17, PNW-22, and PNW-27; it does not add retry or provider-stream resume.
2. **PNW-B — Workspace runtime composition.** The
   [`workspace-runtime-composition/v1`](workspace-runtime-composition-v1-contract.md)
   contract has Design PASS. The durable/reopenable Session and its lease are
   accepted Pi facilities, not an unresolved PNW-B design. `open` recovers one
   lease, reconstructs one non-durable Workspace-lifetime Harness, and installs
   one hook graph; every `prompt` reuses it; `close` settles/retire-runs before
   releasing the lease. The delivered staging Session/per-Turn Harness path is
   deleted when this slice passes independent implementation acceptance.
3. **PNW-C — pre-Investigation Task Understanding and Run Context proof.** Preserve the Original User Task, use one bounded one-shot frontend over the shared Pi dispatcher, deterministically admit its outcome, atomically commit original plus Additional Task Context to the existing Session, and start the Harness only with the profile-driven [`workspace-run-context-preparation/v1`](workspace-run-context-preparation-v1-contract.md) contribution through Pi-owned channels. Its Case Context always contains the Orientation safety baseline and may add only a Projection overlay bound to that basis. It creates no Query Candidate or product I&E tool. Rollback uses the closed raw-task fallback, not another model call or planner.
4. **PNW-D — compaction/tree and protocol v2.** Use qualified entry views for real Pi compaction and branch summary; dual-read/migrate context-generation checkpoints. Rollback follows the dual-reader release boundary; never fall back to raw summaries.
5. **PNW-E — opaque Session lease and recovery/performance.** Remove raw Session authority from the caller, qualify Pi-owned production/in-memory `SessionRepository` lease Adapters, and prove JSONL close/reopen from committed save points and Run settlements. Section 6.10 is an unreviewed crash-recovery candidate only; it authorizes no implementation until independent design PASS.

Each slice uses TDD and replaces implementation-shaped tests with public Interface behavior once the deeper Module covers them. Workspace I&E consumption and Working Set remain frozen until PNW-A through PNW-E and TU-01 through TU-15 pass independent public-seam acceptance, all focused Pi/CTI tests pass under explicit Node 24.14, and root `npm run check` passes. This gate does not apply to an isolated IER1 core package that imports no Workspace and performs no provider disclosure.

## 12. Executable acceptance catalog

- **PNW-01:** two ordinary successful Workspace Turns use one durable Session
  lease generation and one Workspace-lifetime Harness, producing one
  non-duplicated Pi transcript.
- **PNW-02:** a no-tool Turn commits one receipt-last save-point group and then one receipt-last Agent Run settlement group before `turn_completed`; a conflict in either group appends zero entries for that group and never reports completion.
- **PNW-03:** cancel, failure, invalidation, and close before the commit claim leave no model-eligible save-point group.
- **PNW-04:** an ignored-abort provider cannot keep local settlement pending or write events/Session entries after run-generation retirement.
- **PNW-05:** completion-claim-before-close commits exactly one terminal settlement; close-claim-before-completion rolls back the pending save point and commits at most one non-completed settlement.
- **PNW-06:** one bounded Task Understanding invocation completes and its deterministic Original-Task/Admitted-Context control group commits before the first Harness prompt, Agent Run, tool event, or investigation provider request; clarification starts no Agent Run.
- **PNW-07:** parallel tool completion may be out of order while the committed transcript and receipt remain in assistant source order.
- **PNW-08:** blocked, unknown, invalid, truncated, failed, and successful tool calls each produce one finalized outcome and no progress-only publication.
- **PNW-09:** active tool/resource/model/context changes made in one Pi turn affect only the next snapshot after successful save-point commit; rollback, conflict, signing failure, cancel, and close leave both durable and in-memory configuration at the prior snapshot.
- **PNW-10:** a late invalidation denies provider dispatch or rolls back the intersecting group without remote I/O in the context policy.
- **PNW-11:** real Pi compaction and branch summary receive only dependency-qualified entries; their summaries cannot contain stale, protected, legacy, or incomplete bodies.
- **PNW-12:** branch navigation cannot remove a retained context-generation revocation or revive an earlier span.
- **PNW-13:** every admitted `A -> B -> A` transition commits an independent signed generation-control group before intersecting provider work; counters advance monotonically, pre-B prose never revives, and dependency-disjoint history remains eligible.
- **PNW-14:** v1/v2 mixed Sessions reopen safely; forged, foreign-key, altered, missing-parent, gapped, reused, duplicate, or unknown receipts/control entries fail closed, while an authentic repeated observation is idempotent.
- **PNW-15:** clean, dirty, full-binding, crash-before-save-point, crash-after-save-point-before-settlement, crash-after-settlement, and crash-during-generation-control reopen start from a fresh Orientation and the last committed boundaries without provider/tool replay or terminal re-emission.
- **PNW-16:** Pi-owned opaque Session acquisition prevents a second concurrent writer; production and in-memory repository/lease Adapters produce the same public failure/result.
- **PNW-17:** every Workspace Turn retains stable identities, strictly increasing events, one terminal, and a non-rejecting result through success, clarification, timeout, duplicate callback, hook/signing/reconciliation failure, and every completion/cancel/close race.
- **PNW-18:** partial, stale, unknown, unauthorized, retired-generation, and unqualified-compaction content reaches neither provider context nor Workspace Artifact publication.
- **PNW-19:** focused acceptance proves behavior only through `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn`, including exact event counts/order and actual model contexts.
- **PNW-20:** the migration introduces no I&E Retrieval, executable Query Candidate, non-empty new-task Working Set, Case write, durable effect, or fixed product investigation-tool decomposition; pre-Investigation Task Understanding has no Tool or Agent lifecycle.
- **PNW-21:** after its final frontend-specific validation, Harness or bounded one-shot mint one core-private opaque token binding the neutral scope, resident generation, dispatch identity, expected leaf, signal, closed budget request, and one unique owned model/context/options group. Harness callers reach only its private token path; the one-shot production Adapter receives one already-bound no-argument `dispatch()` capability. The leader registers in the shared core and enters A3.1 ownership snapshot before its first await, then qualifies the resolved request, constructs the final budget after any required exact count, and hides all preparation, counting, application staging, A4, registry, cursor, permit, and Adapter entry.
- **PNW-22:** one token-bound dispatch is once-only; same-token concurrent followers never receive the leader stream, and a different token from either frontend with the same dispatch ID or any different scope/receipt identity conflicts in the one shared registry. Same-token scope/generation/request/budget identity cannot drift because minting bound it and `dispatch` accepts no replacement fields. Cancellation or permanent retirement of a one-shot generation before permit consumption prevents Adapter start and cannot re-register under another token. A3.2 proves resident generation-bounded single-runtime pre-start exclusion. A4 proves exact committed/present/absent classification after unknown acknowledgement, A5 proves fenced multi-instance/cross-process exclusion/reopen behavior, and A6 proves ignored-abort late-output/sink exclusion. PNW-22 is complete only when all four attributed parts pass; commit conflict/failure, receipt mismatch, unavailable/conflicting lookup, internal terminal-permit state, missing prepared value, cancellation, ignored abort, or crash permits no automatic resend or spliced output.
- **PNW-23:** exact section 6.6 RFC 8785 JCS/UTF-8/SHA-256 basis bytes and staged budgets bind the neutral attempt scope, budget-independent logical invocation, complete final budget basis, and every current resolved Model/message/content/compat/metadata/tool-schema/option field without a registry of model families. Before prepare, `exact_required` binds only `modelRef` plus the complete expected counter/tokenizer/wrapper identity and real versions. After prepare, Pi requires that identity to equal the resident counter, hashes the complete actual detached Model basis plus that identity, and invents no model-version field. The resulting actual binding digest is present inside the logical invocation before counting, so changing any counter, tokenizer, or wrapper-policy identity/version changes `logicalInvocationDigest`. The count request/result, evidence, application-safe facts, trusted started evidence, and revalidation carry the same value; dispatch recomputes it before A4 and Adapter start. Input count, separately counted minimum output, and evidence digest enter the final budget. Application authority sees enough non-secret prepared Model/rate/capacity and effective request-budget facts to validate `modelRef`, counter provenance, timeout, currency, and worst-case cost. Base URL, API key, environment, headers, and session ID persist only as fixed-domain/fixed-field bindings; auth source persists only as its exact basis digest. Header/env ordering and A3.1 auth precedence are exact. A new/unknown field fails v1. The seam proves logical Adapter input rather than HTTP wire bytes, actual charge, or remote receipt; protected exact-input replay remains disabled.
- **PNW-24:** trusted identity binding derives Workspace and Task identity from the leased Session/Original User Task/Admitted Task Context and never accepts model-supplied Case, actor, task, object, authorization, request, budget, commit, or retry authority.
- **PNW-25:** nested caller mutation of model, messages, content, tools, schemas, stream options, metadata, or headers after preparation changes neither digest nor Adapter input; the original caller object is never a dispatch source.
- **PNW-26:** protected mode rejects `before_provider_payload`, caller `onPayload`, function/custom-transport options, unknown/new prepared public Tool/option fields, undefined, non-finite, symbol, cycle, unsupported variants, and every over-budget value before receipt append; ordinary unprotected Harness hook behavior and A3.1's AgentTool-to-public-Tool projection remain unchanged.
- **PNW-27:** `AbortSignal` and Pi's non-payload-mutating `onResponse` observer are excluded from canonical data but bound by identity to the same neutral resident generation. A3.2 proves for both scope kinds that cancellation or permanent retirement observed before permit consumption prevents Adapter start; A6 proves that retirement fences late output and every local sink after an Adapter ignores abort. PNW-27 is complete only after both slices pass.
- **PNW-28:** Pi directly retains and recomputes the pre-artifact application binding basis, post-artifact Disclosure Decision basis/prior drafts, post-preview opaque material digest, complete materialized entry digests, generic receipt, and authenticity payload. Each single-field/order/retention/authenticity mismatch appends zero entries, or if an exact batch already exists, invokes no Adapter.
- **PNW-29:** model headers and post-`applyAuth` request-options headers remain separate collections sorted by ASCII-lower name; exact original names remain in bindings, within-layer ASCII-case collisions reject, and model-vs-options same-name values remain separate. Explicit A3.1 API-key/env/header exact-key precedence and `null` suppression versus literal `"null"` produce distinct bindings and receipt identities.
- **PNW-30:** every save point recomputes the closed `ContextSnapshotReceiptV1`; entry order, actual dependency generations, projection, task/Task Context/Orientation/Working Set slots, configuration, predecessor, branch, run/turn and expected leaf are exact. A single mismatch, unknown member/key, duplicate/noncanonical dependency or authenticity failure appends none of the group.

A3.2 must additionally pass this focused generic catalog. These cases do not require or authorize Working Set implementation or a real provider:

- **PNW-A3.2-F01:** the private core/token and Harness frontend are not exported. The bounded one-shot public seam is exactly synchronous `bindAttempt(closed binding) -> already-bound capability` followed by no-argument `dispatch()`; the capability exposes no getter or replacement field. Every expected bind failure returns one already-terminated capability whose first/repeated dispatch returns the same frozen pre-receipt value and performs zero core work; only an invariant throws. No prepared reference, resolved secret, Session/control/cursor handle, permit, binder, authority/authenticator, registry record, or Adapter `start()` leaks through either frontend.
- **PNW-A3.2-F02:** each application-authority phase returns its exact closed success, denial-code, or unavailable-code union. Only `bound` is Pi-digested before artifact construction; only post-artifact `authorized` supplies the Disclosure Decision/prior drafts; only post-A4-preview `created` supplies terminal opaque material. Every denial/unavailable/invalid/thrown variant has the exact section-6.6 pre-receipt mapping and zero retry.
- **PNW-A3.2-F03:** every neutral scope, budget request/final basis, exact-counter binding/evidence, named provider, logical invocation, receipt, signed-payload, Session-entry, and A4-batch digest recomputes from the exact `piDigest` basis/bytes. Exact mode proves the logical invocation contains the recomputed counter-binding digest and changes when only a counter/tokenizer/wrapper identity or version changes; trusted-count mode proves the slot is absent. Message/tool positions are unique contiguous zero-based array indices; mutation or a supplied digest/count cannot override Pi's retained basis/recomputation.
- **PNW-A3.2-F04:** only the private core and Pi/runtime binder observe raw API key, environment, both header layers, session ID, and resolved base URL; application authority/verifier receives only the closed non-secret prepared Model/rate/capacity plus budget/digest facts, artifact, retained application bases, final entry digests, and opaque application data. Secret fields or request bodies in safe facts fail before authority invocation.
- **PNW-A3.2-F05:** every secret uses its fixed domain/field name; headers reject ASCII-case aliases and sort per layer by `asciiLowerName`; environment rejects duplicates and sorts by RFC 8785 UTF-16 name order; resolved base URL never persists plaintext; `authSource` persists/exposes only its exact basis digest; auth-only, explicit-only, and explicit exact-key API-key/env/header precedence match A3.1 without a credential revision.
- **PNW-A3.2-F06:** every current user/assistant/tool-result, text/thinking/image/tool-call, usage, diagnostic, details, and added-tool-name field recomputes through the section 6.6.1 schema; diagnostic error message is required, diagnostic code is only string/number, stop reason is closed, and each unknown role/member/variant rejects before application authority or append.
- **PNW-A3.2-F07:** every current Model field and each exact OpenAI-completions/OpenAI-responses/OpenAI-Codex-responses/Anthropic compat member and nested routing shape recomputes; a new/unknown field or compat-on-wrong-API rejects.
- **PNW-A3.2-F08:** metadata and JSON-visible tool schemas accept arbitrary keys only through their closed canonical-value grammar and budgets; runtime tool fields/non-enumerable metadata never become provider-proof data.
- **PNW-A3.2-F09:** every depth/count/UTF-8/JCS/header/environment/schema/image/base64/attempt-identity/token/timeout/cost/application-binding/disclosure/prior-entry/opaque/aggregate budget has at-limit and over-limit cases at its owning bind, prepared, authority-return, A4-preview, or opaque-return stage; over-limit or invalid data appends nothing and starts nothing. Where several budgets apply to the same value, `at-limit` means the jointly reachable effective frontier. A nominal ceiling shadowed by a tighter applicable JCS or aggregate ceiling retains its numerical contract value but instead requires over-limit, precedence, and zero-side-effect evidence; tests must not fabricate an impossible nominal at-limit value.
- **PNW-A3.2-F10:** shared Pi `piDigest` hashes A4's complete materialized Session entries and logical-leaf parent transitions; changing one type/id/parentId/timestamp/type-specific field/order/leaf target/terminal-last position is not exact-present, and A4 imports no provider canonical type.
- **PNW-A3.2-F11:** the terminal custom entry contains the generic receipt plus retained opaque body/digest or digest-only marker. Retained body can be recomputed and passed to application verification; digest-only reopen is classified solely as generic `may_have_dispatched` audit and cannot establish application eligibility or full receipt re-verification.
- **PNW-A3.2-F12:** application authenticator HMAC is unpadded base64url of HMAC-SHA-256 over the exact UTF-8 JCS receipt-without-authenticity bytes; digest-string/decoded-digest signing, key failure, material/basis/prior/terminal mismatch, or any artifact/receipt single-field mismatch yields zero append or, after an already committed exact batch, no Adapter start.
- **PNW-A3.2-F13:** commit acknowledgement `unknown` triggers exactly one same-Session authoritative refresh/lookup and never recommits. Exact expected-leaf plus zero reserved IDs returns `ack_absent/not_dispatched`; unavailable, partial, corrupt, foreign-Session, later-leaf, or different-identity stays `ack_unknown`/`untrusted_present`. `ack_unknown`/`untrusted_present` return the exact locally sealed digest/terminal/leaf reference without upgrading durable knowledge; `ack_absent` returns none. None creates a second receipt or starts.
- **PNW-A3.2-F14:** Harness mints after the final hook and one-shot binds only after its trusted validation and budget-request admission. Exact counting occurs only from the detached A3.1 value inside the registered leader. The shared registry insertion precedes a synchronous leader ownership snapshot; a different token from either frontend with the same dispatch ID conflicts; a same-token follower submits no alternate input and returns `duplicate_in_flight` without a stream; a terminal duplicate returns `duplicate_terminal`; settled/retired generations cannot re-register. Only the leader with exact committed/present terminal leaf `D` may consume one resident permit and enter A3.1 `start()` once.
- **PNW-A3.2-F15:** nested mutation, `before_provider_payload`, caller `onPayload`, custom/function option, header collision, unknown option, signal-generation mismatch, or observer replacement cannot alter or bypass the protected request; ordinary unprotected Harness behavior remains unchanged.
- **PNW-A3.2-F16:** prepare/binder/authority/A4/sign/verify/commit/lookup/cancel/cursor failures return the exact `pre_receipt`, `ack_absent`, `ack_unknown`, `untrusted_present`, or `post_receipt` union and knowledge. A resident-value, retained-start, or permit-state invariant failure has no public protocol code and throws only the module-internal typed `ProviderDispatchInvariantError`; it is reviewed statically because no public caller can corrupt that private state, and acceptance must not add a private reducer/test seam to fabricate it. A4 prepare capability-missing `unsupported` and authoritative-load `unavailable(reason)` both map to `control_unavailable`; process crash has no resident registry start path; no branch automatically retries, reconstructs, resumes, shares a stream, or splices output.
- **PNW-A3.2-F17:** a generic fake application Adapter can map canonical business binding/disclosure/opaque receipt data without importing CTI types into `packages/agent`; the frozen IWS legacy `prepare/commit/lookup`, preparedRef, credential revision, and receipt schemas are not callable alternatives.
- **PNW-A3.2-F18:** focused acceptance uses deterministic fake Models, memory plus JSONL A4 Adapters, exact event/Adapter-call counts, and no paid/real model. It exercises both frontends through public behavior, including one cross-frontend same-dispatch collision, and reports A3.2 only; full PNW-22 still requires A4/A5/A6 attribution and full PNW-27 still requires A6.
- **PNW-A3.2-F19:** `agent_run` and `bounded_one_shot` use the closed neutral scope and never persist a second run-only identity tuple. Byte-identical operation/request/attempt/generation strings under different scope kinds produce different scope/artifact/receipt identities; unknown kinds/members and drift reject before prepare/append/start.
- **PNW-A3.2-F20 (Workspace-owned integration gate after generic A3.2 PASS):** started `committed|exact_present`, every individual pre-receipt code, ack-absent, acknowledgement-unresolved/untrusted, trusted post-receipt, and duplicate results map one-to-one to the exact section-6.6 Task Understanding binding/outcome. The result union structurally forbids acknowledgement-unknown references on trusted branches and present references on acknowledgement-unknown branches. Receipt digest, terminal ID, `L`, `D`, provider attempt ref, charge class, and legal invocation-outcome pairing cannot be guessed or omitted; raw stream/deltas never cross the Workspace port. This gate is implemented and tested only through the Workspace-owned public lifecycle after the generic A3.2 implementation independently passes; it is not required for the earlier focused Pi public-seam PASS, and that earlier PASS must not be reported as integrated PASS.
- **PNW-A3.2-F21:** one-shot bind/dispatch creates no Harness, Session, transcript, Tool registry, Agent Run, compaction/tree path, steering/follow-up queue, retry/evaluator/fallback call, or second transaction. Pre-abort and retirement at every boundary before permit consumption start zero Adapters; the attempt remains once-only and late callbacks cannot create a second terminal.
- **PNW-A3.2-F22:** safe facts expose the complete non-secret prepared Model identity/rates/capacity, closed final budget basis/digest, exact-counter evidence when requested, and effective output/timeout while excluding every resolved secret, request body, and transient minimum-output text. Actual model mismatch, missing counter/tokenizer/wrapper provenance, input/minimum-output/timeout/currency/cost mismatch, overflow, absent timeout, and worst-case cost over the application limit deny before A4; exact at-limit facts pass.
- **PNW-A3.2-F23:** asynchronous runtime open awaits and validates the actual initial Session leaf before constructing its private cursor and returns only `opened|invalid_options|control_unavailable`; failure constructs no runtime. One opened composition supplies one dependency identity set and one private core to both frontends. Replacing `Models`/Provider/Auth, binder, authority/authenticator, Session A4/cursor, registry, prepared store, or permit issuer per frontend/attempt is impossible; public same-dispatch collision and exact dependency call counts prove sharing without testing private fields.
- **PNW-A3.2-F24:** deterministic fake and production-shaped local resolver/counter Adapters run the same Harness and bounded-one-shot fixtures. They prove the exact `CreateModelsOptions.exactInputCounterResolver -> PreparedSimpleInvocation.exactInputCounter` seam, absence-as-unsupported, recursively detached safe projection, exact counting of finalized system/message/content/image/tool-schema/token-affecting-option/wrapper input, separate minimum-output counting, exact at-limit success, one-token-over failure, and `unsupported|unavailable|invalid|stale|unknown` plus complete-model-basis, counter/tokenizer/wrapper identity/version, binding/logical/evidence, and mutation mismatch with zero Provider Adapter start. They also prove the pre-prepare TU expectation contains only `modelRef` plus the counter/tokenizer/wrapper identity, while the prepared projection, count request/result, exact evidence, trusted started budget evidence, revalidation, and TU invocation outcome use one byte-identical actual counter-binding digest computed after prepare with no digest cycle and no model-version field. The trusted-count Harness branch retains its prior behavior and invokes no counter. These fixtures use no credentials, network, paid model, Provider Adapter start, Session/Harness creation by the counter, or real-provider counter registration.

## 13. Autonomous grill decisions and reopen conditions

| Question | Evidence and recommended answer | Decision | Reopen when |
|---|---|---|---|
| Why does Workspace exist? | Callers otherwise coordinate CTI authority and Pi lifecycle themselves. | Keep one deep `CaseWorkspace`. | A simpler owner can hide both concerns without leaking either contract. |
| Who owns execution persistence? | Pi already owns Session, tools, save points, compaction, and tree operations. | Pi owns the execution spine. | Pi cannot provide atomic/fenced lifecycle semantics without CTI-specific knowledge. |
| Is direct Session persistence enough? | Current `message_end` precedes the CTI completion fence. | Require an opt-in save-point transaction. | Eligibility-only retention is deliberately accepted as the product behavior. |
| Is the stale marker a domain Module? | Its necessary fact is monotonic dependency invalidation, not stale prose itself. | Replace it with signed context generations; derive capsules. | Equal-version revival can be prevented with a simpler durable proof. |
| Should dependency selection stay public? | Free-form task interpretation cannot prove safe narrowing, while Orientation block names leak the source contract. | Remove it for ordinary callers; use all Orientation dependencies unless a trusted closed recipe proves a narrower set. | A real caller requires explicit source-block control as a stable product need. |
| Can Workspace implement the transaction permanently? | It would duplicate generic pending-write, abort, and context-view semantics. | Allow only as a temporary bridge; target Pi depth. | A second independent Pi consumer cannot use the proposed core seam or the seam becomes product-specific. |
| What validates the design? | Names and unit calls do not prove public behavior. | Use public-seam failure-oriented acceptance plus focused Pi tests. | Production evidence exposes an untested external guarantee. |
