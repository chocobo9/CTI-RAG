# Agent Memory Management v1 Contract

Status: **Design candidate; implementation not authorized.**

This contract is the detailed design input produced after [ADR 0021](../adr/0021-make-memory-management-a-first-class-agent-module.md). It is the proposed foundation for a first-class Agent Memory Management Module; it does not claim that the current repository already provides this module.

## Product boundary

Memory Management is an independent Agent capability, parallel to Runtime/Harness, State/Session, Tools/Capabilities, and Validation/Evidence. It manages durable semantic, episodic, and procedural memory; candidate extraction and admission; persistence, exact-reference qualification, and qualified memory contributions for Context Assembly; consolidation, versioned update, conflict, correction, invalidation, deletion; and provenance, authorization, audit, and evaluation. The final assembled runtime context remains a Context Assembly responsibility and is not a durable Memory category.

Memory does not replace Session, Case, Workspace, or Intelligence & Evidence (I&E) authority. Those authorities are integrated through explicit adapters. A memory record must not become authoritative merely because a model wrote it.

## V1 problem, outcome, and exclusion

The first design target is a closed durable-memory lifecycle. It solves these
problems without making a Session transcript, an owner record, or a model
completion itself recallable Memory:

| Problem | Required outcome | Evidence that decides it |
| --- | --- | --- |
| An untrusted, incomplete, cancelled, discarded, or acknowledgement-unknown Run proposes retention. | It creates no durable entry or mutation. | An exact, committed Run-settlement proof or an explicit-command proof. |
| A valid candidate duplicates, corrects, supersedes, or contradicts prior Memory. | One idempotent, revision-checked mutation makes the relationship explicit; no silent overwrite occurs. | Candidate identity, expected revision, operation identity, and committed mutation receipt. |
| A selected contribution has changed owner authorization, source version, validity, or deletion status before Provider use. | The contribution is excluded and Context Assembly receives no stale replacement. | A fresh owner qualification/revalidation result bound to the selected revision. |
| An explicit correction or forget request races an earlier operation or is replayed. | Exactly one compatible operation may take effect; conflicts and unknown completion stay observable. | Operation idempotency binding, compare-and-set revision, and authoritative operation lookup. |
| A removed entry remains in an index, cache, or old runtime view. | It is ineligible before physical purge completes and cannot be reintroduced by equal content. | Deletion state/tombstone plus a new qualification binding; no prior binding revives. |
| Owner material or recalled text contains instructions. | It remains labelled data and cannot activate a Tool, change policy, or acquire authority. | Contribution rendering policy and the Provider-application binding. |

The V1 product is therefore: an exact-input durable Memory Module that admits
qualified candidates, retains revisions and mutation evidence, and qualifies
explicitly supplied entry references for Context Assembly. Its public
acceptance result is a contribution or a closed failure, never a prompt,
Provider message, Tool schema, owner record, or search result.

**Excluded from this contract revision:** general semantic/vector retrieval,
candidate-information location, ranking, reranking, and a SearchIndex Adapter.
The current Module does not discover entries. A caller may supply only exact
`MemoryEntryRef` values already obtained through another owner-authorized
workflow. An empty explicit selection is valid. Any later discovery capability
requires its own problem statement, scope/non-disclosure semantics, Interface,
Adapter decision, and acceptance catalog; it may not be smuggled into
`prepare`.

## Terminology and responsibility map

The following map is the candidate contract's terminology baseline. The Waku
evidence is limited to its runtime-context boundary: its architecture places a
per-turn runtime composition separately from semantic, episodic, and procedural
stores behind retrieval. It does not establish CTI-RAG authorization, retention,
or mutation policy. Pi source evidence establishes
that `Session.buildContext()` selects persisted Session entries, while the
Harness produces the `AgentContext` handed to the provider; the Workspace Run
Context Preparation contract assigns final Provider canonicalization and
digest/count authority to Pi.

| Term | Owner and responsibility | Concrete problem solved | Sharing status and split condition |
| --- | --- | --- | --- |
| **Durable Memory Management** | This Module owns candidate admission, durable `MemoryEntry` identity/revisions, exact-reference eligibility, mutation and deletion. | A Session transcript or owner record cannot provide cross-run admission, correction, idempotency, or contribution policy. | Semantic and public Interface split from Context Assembly now. One storage Adapter is sufficient while durable state has one concurrency/durability model; split when a second such model is required. Discovery/SearchIndex is excluded. |
| **Context Assembly** | Pi Harness/Session plus Workspace Context Preparation assemble the runtime Provider input from trusted instructions, the current user input, selected Session history, owner-qualified context, selected Memory contributions, and active Tools. | Prevents treating the transient prompt as a durable authority or durable Memory Entry. | Semantic and Interface split from Memory now. No new durable storage or public Memory Adapter follows from this term. It would need a separate Adapter only if a second runtime-context assembler must vary independently from Pi. |
| **Session** | Pi owns persisted conversation/tree history and selects eligible entries for one context consumer. | Preserves chronology, compaction and recovery without reclassifying history as Memory. | Memory reads Session only through an owner Adapter/reference. A Memory-owned transcript projection is prohibited; reconsider only if a separately admitted durable episodic derivation is required. |
| **Workspace Memory Coordination** | Workspace binds the current task, Case, Access Principal, Use Purpose, Context Consumer and disclosure policy to Memory requests and revalidation. | Durable eligibility alone cannot prove this run may disclose a contribution. | Semantic integration capability, not a second Memory owner or prompt renderer. It becomes a public Interface only when a second Workspace-like consumer needs the same binding contract. |
| **Qualified Memory View** | Memory returns an ephemeral, consumer-bound contribution plus non-content evidence. Context Assembly consumes it. | Keeps exact-reference qualification separate from prompt ordering, Tool activation and Provider canonicalization. | Public Memory output, but not a Provider or Session type. Split a renderer Adapter only if two consumers require materially different safe renderings from the same qualified view. |
| **Provider input / invocation artifact** | Pi Provider Dispatch owns final message/tool canonicalization, count and invocation evidence; Workspace joins owner evidence through its application binding. | Prevents duplicate prompt digests and a Memory Module becoming a Provider transport authority. | Interface remains Pi-owned. Memory may carry contribution/binding references only; it must split no Provider Adapter unless it starts owning provider transport, which this contract forbids. |

A checkpointed Task or Run-local projection remains owned by Session or
Workspace recovery semantics and does not become durable Memory merely because
it contributed to a Provider call.

## Ownership and value forms

Memory owns `MemoryCandidate` lifecycle, `MemoryEntry` identity and revisions, scope/category policy, consolidation, exact-reference qualification, mutation receipts, and invalidation/deletion behavior. It does not own Session transcripts/branches, Case acceptance/revisions, Workspace task/working-set state, I&E source versions/use disposition, tool registration/execution, provider dispatch, or published output.

Values have two forms:

1. `owned_content`: Agent-owned preferences, validated experience, or reversible procedural advice.
2. `owner_reference`: a versioned reference to Session, Case, Workspace, or
   I&E content. It is revalidated and re-fetched at use time, not copied as a
   second authority.

## External module seam

```ts
interface AgentMemoryModule {
  prepare(request: MemoryPreparationRequest): Promise<MemoryPreparationOutcome>;
  revalidate(request: MemoryRevalidationRequest): Promise<MemoryRevalidationOutcome>;
  admit(request: MemoryAdmissionRequest): Promise<MemoryAdmissionOutcome>;
  manage(request: MemoryManagementCommand): Promise<MemoryManagementOutcome>;
}
```

`prepare` qualifies only the exact entry references supplied in its request. It
does not search, rank, infer a subject, or replace one reference with a similar
entry. It returns a `QualifiedMemoryView` for Context Assembly plus a
content-free receipt. It does not assemble the final system prompt, skills,
chat history, user prompt, tools, or Provider messages. `revalidate` checks
that exact prepared view immediately before Provider use and returns only
`valid_unchanged`, `invalidated`, or `unavailable`; it never silently repairs
or reselects a stale reference. `admit` consumes an already verified source,
including an exact successfully settled Run proof or an explicit-command proof;
it neither settles a Run nor writes a Workspace/Session settlement. It commits
an idempotent revision mutation and emits a mutation receipt. Failed,
cancelled, discarded, acknowledgement-unknown, or unsaved Runs provide no
admissible proof and create no durable entry. `manage` is the same lifecycle
under an explicit, authorized human or trusted-system command; it does not
become a model write path.

The Interface is intentionally four operations rather than separate public
methods for matching, conflict resolution, persistence, index maintenance, or
purge. Those behaviours are internal to the Module: callers learn one lifecycle
seam and tests cross the same seam. The Module accepts its storage,
authorization, owner-qualification, and audit dependencies; it does not create
or expose them.

### Minimum V1 carriers

The exact serialization, digest grammar, byte limits, and error-code names are
not yet frozen; these field responsibilities are. No carrier may accept an
opaque `any`-shaped owner object, prompt body, credential, or Provider value.

| Carrier | Required fields | Result and closure |
| --- | --- | --- |
| `MemoryPreparationRequest` | `principalRef`, `usePurpose`, `contextConsumer`, `scope`, owner-issued `ExactSelectionProof`, ordered exact `MemoryEntryRef`/expected-revision selections, required/optional designation, contribution budget, policy revision | Produces one `QualifiedMemoryView` or a closed preparation failure. It contains no search expression. |
| `QualifiedMemoryView` | `MemoryUseRef`, ordered qualified revisions and safe projections, omissions/conflicts, policy/budget evidence, instruction-safety labels | Ephemeral and consumer-bound. It is not a prompt, Session entry, durable Memory Entry, or Provider artifact. |
| `MemoryRevalidationRequest` | exact `MemoryUseRef` and current Provider-attempt binding | Returns only `valid_unchanged`, `invalidated(reason)`, or `unavailable(reason)`; no repair or reselection. |
| `MemoryAdmissionRequest` | `MemoryOperationRef`, one verifier-issued source proof, one deterministic/explicit candidate, exact target and expected revision where mutation needs one | Produces one committed mutation receipt, a closed rejection/conflict, or acknowledgement-unknown pending exact lookup. |
| `MemoryManagementCommand` | trusted requester identity/authorization, `MemoryOperationRef`, command kind, exact target/revision or explicit candidate | Uses the same admission/mutation rules. `inspect_entry` and `inspect_operation` return only authorized non-secret evidence and have no-existence-leak closure. |
| `MemoryMutationReceipt` | operation, source proof, candidate refs, resulting entry/revision refs, mutation outcome, policy/auth evidence, committed/unknown status | Durable audit evidence, never a recallable contribution. |

The source-proof union is closed in V1:

```text
VerifiedMemorySourceProof
  = ExactSettledRunProof
  | ExplicitAuthorizedCommandProof
  | OwnerVersionedReferenceProof
  | GitMarkdownSourceProof
```

`ExactSettledRunProof` binds the exact Pi/Workspace settlement evidence,
committed save-point or terminal basis, Run identity, disposition, source digest
and verified status. `ExplicitAuthorizedCommandProof` binds the requester,
authorization decision, command text/digest, time and scope. An
`OwnerVersionedReferenceProof` may support an owner-reference candidate only
when that owner confirms its authority/version. No model output, raw tool
result, uncommitted stream fragment, or source-looking text is a source proof.
`GitMarkdownSourceProof` binds the configured repository identity, allowed path,
immutable commit ID, blob digest, source-policy revision, author/committer
evidence and the independent authorization decision for the requested scope.
A moving branch name, uncommitted worktree body, path escape, missing blob or
merge-conflict text is not a GitMarkdownSourceProof.
The source-proof verifier, not a structural TypeScript shape, issues the
verified proof. A forged Run-shaped or command-shaped value fails before
candidate validation, storage access, or audit disclosure.

Two unknown states are deliberately distinct. An unknown or uncommitted **Run
settlement** is not a `VerifiedMemorySourceProof` and is inadmissible. An
unknown **Memory operation acknowledgement** follows a request that may already
have committed; it is resolved only through the authorized exact
`inspect_operation` outcome of `committed`, `absent`, or `unresolved`.

Each `MemoryAdmissionRequest` carries exactly one candidate and exactly one
requested mutation. It is one atomic operation: it either commits its revision,
operation outcome and receipt together, or commits none. A caller with several
candidates submits several operations and observes each outcome; this contract
does not invent a cross-candidate transaction without a product requirement for
its partial-failure semantics.

### Closed operation outcomes

These outcomes are the V1 public failure vocabulary. Adapters may retain more
diagnostic detail privately, but callers and receipts use only these closed
results:

| Operation | Success | Closed non-success outcomes |
| --- | --- | --- |
| `prepare` | `qualified(view)` or `qualified_empty(view)` | `selection_unverified`, `required_ineligible`, `required_unavailable`, `budget_exceeded`, `policy_denied`, `storage_unavailable` |
| `revalidate` | `valid_unchanged` | `invalidated(reason)`, `unavailable(reason)` |
| `admit` | `committed(receipt)` or `replayed(receipt)` | `source_unverified`, `candidate_invalid`, `target_ineligible`, `policy_denied`, `operation_conflict`, `revision_conflict`, `storage_unavailable`, `acknowledgement_unknown` |
| `manage` mutation | `committed(receipt)` or `replayed(receipt)` | the same mutation outcomes as `admit` plus `command_unauthorized` |
| `manage.inspect_entry` / `manage.inspect_operation` | `authorized_entry(evidence)` / `committed(receipt)` / `absent` / `unresolved` | `not_authorized_or_not_found`, `storage_unavailable` |

`not_authorized_or_not_found` intentionally combines denied and absent states
at the caller-visible Interface, preventing entry/operation existence leakage.
`acknowledgement_unknown` is terminal for the current call but not an operation
outcome claim; a later authorized `inspect_operation` may classify it.

## Domain records

The following identities are distinct and must never alias. Their separation is
semantic and belongs in the public Interface/receipt vocabulary; it does not by
itself require a separate database table or Adapter.

| Identity | Meaning | Why it cannot be merged | Required binding |
| --- | --- | --- | --- |
| `MemoryCandidateRef` | One proposed, not-yet-admitted assertion or reference. | A candidate may be rejected, merged, or produce no mutation; an Entry may not. | Source proof, proposed scope/value/category, extraction evidence. |
| `MemoryEntryRef` | Stable identity of one durable logical Memory item. | Corrections retain or relate to this identity across revisions. | Scope root and entry identity. |
| `MemoryRevisionRef` | One immutable realized version of an Entry. | `EntryRef` alone cannot prove which content/status was used or compared. | Entry, revision number, state, value/reference digest. |
| `MemoryOperationRef` | One idempotent requested lifecycle effect. | Retries must not become duplicate admissions or corrections. | Idempotency key, request digest, expected revision, terminal outcome. |
| `MemorySourceRef` | The external fact, explicit command, or exact settled Run that supports a candidate. | A source can support several candidates; candidate identity cannot establish source authority. | Owner/source version, digest, authority and temporal evidence. |
| `MemoryUseRef` | One consumer-bound prepared contribution. | A selected revision can later become ineligible without changing its revision. | Consumer, principal, use purpose, policy, order, budget, owner-qualification generation, safe-projection digest and revalidation basis. |

`MemoryScope` contains tenant, visibility principal/team/case/org, and optional
case/workspace/session/task references. There is no implicit global scope; a
write cannot exceed source authorization, and case memory is not shared without
explicit admission. V1 defines no scope inheritance or visibility lattice:
`private`, `team`, `case`, and `organization` are opaque policy inputs. The
authorization Adapter must return an exact allow/deny result for the bound
Principal, Purpose and Consumer; Memory must not infer membership from the
shape of a scope.

`MemoryCandidate` contains identity, category, proposed value form, subject, scope, provenance, temporal bounds, relations, extraction evidence, and an exact settled-run or explicit-command reference. It is not recallable until admitted and committed.

`MemoryEntry` contains stable identity, revision, category, state (`active`, `challenged`, `superseded`, `invalidated`, `deletion_pending`, or `deleted`), scope, value/reference, provenance, temporal bounds, relations, and policy timestamps. Provenance records source references, derivation kind, extractor/revision, and source digest. Temporal fields distinguish observed, recorded, valid, and expiry time. Relations include derived-from, duplicate, update, supersedes, contradicts, supports, and invalidates.

Every relation binds an exact source revision and exact target revision. Before
the relation is committed, the Module verifies that both revisions are visible
to the operation's Principal/Purpose, are in a legally comparable scope, and
are not deletion-pending/deleted. A relation cannot name an arbitrary hidden
entry, widen scope, or turn a hidden target's existence into an error detail.

Authority, provenance, confidence, retention, temporal validity, owner version,
and use permission are separate facts. Provenance answers *where this came
from*; authority answers *who may assert or change it*; confidence is an
advisory assessment and cannot grant authority; retention controls lifecycle;
temporal bounds say when content was observed/valid; an owner version says
which owner state was referenced; and a use permission binds one principal,
purpose and consumer at a time. No field substitutes for another.

## Durable categories and lifecycle

- **Semantic**: facts, preferences, subject attributes, and references. CTI facts default to `owner_reference`; analysis remains a hypothesis unless admitted by an authority.
- **Episodic**: settled objectives, actions, tool outcomes, investigation paths, and results, represented as structured summaries with Session/Run/save-point and tool receipts rather than transcript copies.
- **Procedural**: strategies, approved flows, failure avoidance, and human-approved playbooks. Model-derived procedures begin challenged/candidate and cannot register tools, expand capability, or authorize side effects.

Context Assembly is the runtime composition of trusted system instructions,
skills/tools, current user input, eligible Session history, Workspace/Case/I&E
context, and selected durable Memory contributions. Memory may provide a
qualified contribution to that assembly; Context Assembly owns the final
Provider context. A Task/Run-local context projection may be checkpointed by
Session or Workspace for its own recovery semantics, but it is not admitted as
a durable `MemoryEntry`.

```text
Verified settled Run proof / explicit-command proof
  -> candidate extraction
  -> schema + settlement + provenance validation
  -> scope and subject resolution
  -> exact mutation target, when required
  -> policy/auth admission
  -> atomic revision commit
  -> mutation receipt and audit
```

V1 performs no similarity matching. Mutations are `add`, `update`, `supersede`, `contradict`, `invalidate`, `delete`, or `no_op`.

## Lifecycle and qualification invariants

### Admission and mutation

The admission order is fixed:

```text
verified source proof
  -> candidate schema/provenance/scope validation
  -> explicit policy and authorization admission
  -> exact duplicate/target decision
  -> compare-and-set revision mutation
  -> durable operation outcome and mutation receipt
```

`add`, `update`, `supersede`, `contradict`, `invalidate`, `delete`, and `no_op`
are closed mutation outcomes. Similarity may not decide any of them in V1,
because discovery/matching is excluded. The caller or trusted admission policy
must name an exact target for every non-`add` mutation. A duplicate request with
the same `MemoryOperationRef` returns its original terminal outcome; the same
idempotency key with different request evidence fails with an integrity
conflict; a different operation against a stale revision fails with a revision
conflict. An acknowledgement-unknown commit is not upgraded to success without
one authoritative exact-operation lookup.

### Preparation and revalidation

`prepare` receives an ordered exact selection and an `ExactSelectionProof`
issued by the owner-authorized workflow that produced it. The proof binds the
caller, scope, Purpose, Consumer, selection order and policy revision; it does
not disclose or locate alternatives. For each requested revision it
checks, in order: scope partition; Access Principal; Use Purpose; Context
Consumer; entry state/tombstone/retention/expiry; owner-reference version and
authority; then the contribution rendering policy. It does not rank. It returns
the selected ordered revisions, labelled conflicts and omissions, and a
`MemoryUseRef` binding. A required selected entry that is unavailable or
ineligible closes preparation; an optional selected entry may be omitted with a
non-content reason. Neither branch may widen scope or substitute a different
entry.

`revalidate` repeats the current eligibility checks against the exact
`MemoryUseRef` immediately before Provider admission. Owner qualification
returns a monotonic generation plus safe-projection digest; both must equal the
values bound at preparation. Revalidation returns status only and never returns
or stages replacement content. Any change produces `invalidated`; owner
unavailability produces `unavailable`; neither result may reuse an older
qualification. Returning to equal content after an intervening change does not
revive an older use binding.

### Correction, invalidation, and deletion

Correction creates a new revision and records its relation to the corrected
revision; it does not overwrite history. Contradiction preserves both entries
and the relation until policy resolves their state. Invalidation makes an entry
ineligible without asserting that its historical source never existed.
Deletion first records `deletion_pending` and immediately excludes the entry
from preparation/revalidation; only then may an Implementation purge retained
content and projections. After purge, the minimum durable tombstone contains
entry identity, last revision/state, operation reference/digest, deletion time,
retention/legal-hold disposition and no content body. Authorized audit may see
only the non-secret tombstone facts. `deleted` and its content-free tombstone
remain enough to reject resurrection. Restore is excluded until a retention and
legal-hold policy defines whether the tombstone permits it.

## Persistence and Adapter obligations

The authoritative durable state is an append-only revision/operation history
plus a current-entry materialization. Compare-and-set, idempotency, operation
lookup, and deletion tombstones belong to the SQLite Memory Store Adapter. The
first deployment profile is **SQLite on one local host**, because this lifecycle
requires one transactionally coupled durable authority for revisions,
operations, receipts and tombstones. The existing `sql.js` SQLite probe is
provisional evidence only: it does not qualify the selected profile until its
actual driver, acknowledgement, restart and writer model satisfy AM-01 through
AM-23 and SP-01 through SP-06. [ADR 0022](../adr/0022-select-sqlite-store-and-git-markdown-memory-source.md)
owns this storage/source decision.

Owner qualification is a separate Adapter role because Session, Workspace,
Case, and I&E have different authority meanings. It returns only an exact
versioned reference's eligibility and safe projection; it does not locate
similar owner material. Authorization and audit are Adapter roles, not durable
Memory authority. Missing Case/I&E support returns `unavailable`, never a fake
qualified read.

### Selected storage and user-editable source profiles

SQLite is the sole authoritative store for admitted `MemoryEntry` revisions,
operations, receipts and tombstones. A **Git-backed Markdown Memory Source**
is the selected user-editable input surface: users edit and commit Markdown;
the Source Adapter reads an exact committed blob and produces a candidate source
proof. Git/Markdown is not a second Memory store, is not a SQLite mirror, and
is never written, merged or committed by Memory.

One user edit therefore has this path:

```text
user edits Markdown -> Git commit -> Source Adapter verifies commit/blob/path/policy
  -> explicit candidate -> Memory admission -> SQLite Memory revision
```

The commit does not directly mutate Memory. It becomes effective only after the
same source-proof, authorization and admission rules as any other candidate.
This preserves direct user control over the file while preserving CAS, deletion,
receipt and recovery semantics in SQLite. A removed or changed source file
cannot cause Memory to write it back; it invalidates only the reference derived
from that exact source version. A future read-only Markdown export is a separate
projection decision and must not share a path with the editable source.

Storage is an internal Adapter role, but it cannot be qualified by convenience
or by a passing local probe. Before the selected SQLite Adapter becomes eligible
for G1/G3, its owner publishes one `MemoryStorageProfile` that declares:

- deployment and writer model, including process/host boundaries;
- durability acknowledgement model and the exact lookup used after an unknown
  acknowledgement;
- atomic unit containing revision/event, current materialization, tombstone and
  terminal idempotent operation outcome;
- expected-revision/CAS behaviour and conflict result;
- restart, backup/recovery, purge/cache, retention and operational limits; and
- the exact public conformance fixtures used to prove those claims.

A profile passes only when it proves all of the following through the public
`AgentMemoryModule` Interface:

| ID | Storage qualification scenario | Required result |
| --- | --- | --- |
| SP-01 | Admit/correct/delete while injecting failure before durable commit, after durable commit but before acknowledgement, and during deletion purge. | Restart plus authoritative exact-operation lookup distinguishes committed, absent and unresolved outcomes; no effect is inferred. |
| SP-02 | Race two different expected-revision mutations and replay one exact operation. | At most one compatible terminal mutation succeeds; stale operations conflict and exact replay returns its original outcome. |
| SP-03 | Reopen after `deletion_pending`/`deleted`, then prepare an old binding and attempt equal-content re-admission. | Deleted content is ineligible; old use bindings do not revive; any permitted new admission has a new source/operation/revision identity. |
| SP-04 | Revalidate while authorization, owner version, validity, policy or deletion changes. | No stale contribution becomes `valid_unchanged`; the declared concurrent-reader/writer model is exercised, not assumed. |
| SP-05 | Run AM-01 through AM-23 against the actual carrier across its declared restart and writer topology. | The carrier supplies the same observable public outcomes as the deterministic reference fixtures. |
| SP-06 | Inspect dependency graph and stored projections. | Storage remains internal to `packages/agent-memory`; it does not make copied owner content authoritative or add discovery/index semantics. |

The existing `sql.js` SQLite probe is evidence only for its declared
single-process, single-writer clean-path behaviour. It cannot qualify the
selected SQLite profile's actual durable-acknowledgement or production-recovery
behaviour without SP-01 through SP-06 evidence. Waku supports the general
database-plus-readable-memory-file pattern, but it does not establish this
project's user-edit or authorization semantics.

### Invocation timing without discovery

The Module's call timing is fixed even though reference selection is deferred:

1. **Before Context Assembly:** Workspace may call `prepare` only with an
   already-authorized ordered exact selection. With no selection it either makes
   no Memory call or records a valid empty preparation; it must not invent a
   discovery query.
2. **Immediately before Provider admission:** Context Assembly calls
   `revalidate` for the exact `MemoryUseRef`. Failure starts zero Provider
   calls and requires a new selection/preparation, not repair in place.
3. **After an exact settled Run:** the Run/Workspace owner may submit explicit
   deterministic candidates to `admit`. There is no automatic model extraction
   or background candidate search in V1.
This gives Context Assembly a bounded contribution seam now, while leaving the
future question “which references should this task use?” to the separate
discovery design.

Memory does not issue a Provider permit. For the integrated path, Workspace
passes the exact `MemoryUseRef`, owner-qualification generation,
safe-projection digest and `revalidate` status into the existing Pi/Workspace
application binding defined by
[Workspace Run Context Preparation](workspace-run-context-preparation-v1-contract.md).
Pi remains the final Provider-start authority. Any mismatch in that binding,
or any status other than `valid_unchanged`, denies the attempt before Provider
start; Workspace may not treat a prior successful revalidation as a permit.

### Safe contribution projection

Each qualified item has a closed projection shape: `untrusted_data` label,
bounded body or owner-reference rendering, entry/revision/source references,
authority/status/temporal labels, safe-projection digest, and rendering
constraints. It has no instruction role, Tool definition, capability, policy,
authorization or Provider option field. Context Assembly may render only this
shape as data. Revalidation compares its digest and returns status only; it may
not return a changed projection under the old `MemoryUseRef`.

## Acceptance catalog and release gates

The following catalogue is the V1 design oracle. An Implementation may add
tests, but it may not weaken, combine away, or score around these cases. Each
scenario crosses the public `AgentMemoryModule` Interface with deterministic
source/owner/authorization/storage adapters; private storage calls are not the
acceptance seam.

| ID | Scenario | Required observable result |
| --- | --- | --- |
| AM-01 | A verified exact settled Run admits one deterministic semantic, episodic, or procedural candidate. | One committed entry/revision and mutation receipt bind the same Run/source proof and operation. |
| AM-02 | Failed, cancelled, discarded, unsaved, or acknowledgement-unknown Run submits the same candidate. | No entry, revision, operation success, or owner mutation is created. |
| AM-03 | The same admission operation is replayed unchanged. | The original terminal receipt is returned; entry count and revision do not change. |
| AM-04 | The same idempotency key is reused with a changed source, candidate, scope, purpose, or target. | Integrity conflict; zero mutation. |
| AM-05 | Correction, supersession, contradiction, invalidation, and delete target an exact current revision. | Each legal mutation records its explicit relation/state; a stale expected revision conflicts and overwrites nothing. |
| AM-06 | An explicitly selected active entry is prepared under matching scope, Principal, Purpose, Consumer, budget, owner version, and retention. | One ordered qualified contribution with `MemoryUseRef`; no Provider message or Tool activation is produced. |
| AM-07 | An explicitly selected entry is cross-scope, cross-principal, cross-purpose, expired, challenged/invalidated/deleted, or owner-version-drifted. | It is omitted or preparation fails according to required/optional designation; no alternate/similar entry is selected and no existence-sensitive body leaks. |
| AM-08 | A qualified entry's authorization, owner version, validity, policy, or deletion status changes before Provider admission. | Revalidation returns `invalidated` or `unavailable`; the old `MemoryUseRef` cannot be used, including after A-to-B-to-A content return. |
| AM-09 | Forget/delete is acknowledged while physical purge, cache eviction, or restart is incomplete. | `deletion_pending` is immediately ineligible; after restart neither old entry/revision nor equal content can qualify from the old binding. |
| AM-10 | Commit acknowledgement is unknown during admission/correction/delete. | No automatic re-commit or success claim; exactly one authoritative operation lookup distinguishes committed, absent, or unresolved. |
| AM-11 | An owner reference or owned content contains model-directed instructions. | The qualified projection is labelled untrusted data; it cannot alter system instructions, Tools, scope, policy, or operation authority. |
| AM-12 | An empty explicit selection is prepared. | Valid empty contribution and receipt; the Module performs zero discovery, ranking, or general retrieval calls. |
| AM-13 | A Memory commit acknowledgement is unknown; the caller uses `manage.inspect_operation` after restart. | Exactly one authorized lookup returns `committed`, `absent`, or `unresolved`; only `committed` exposes the original non-secret receipt. |
| AM-14 | A structurally valid Run-shaped, command-shaped, or owner-reference-shaped value is forged. | It fails without a verifier-issued source proof; zero candidate validation, storage mutation, or audit disclosure occurs. |
| AM-15 | A correction/supersession/contradiction/invalidation relation names a hidden, cross-scope, deleted, or wrong-revision target. | The operation closes without mutation or target-existence disclosure. |
| AM-16 | Context Assembly attempts to start a Provider after a `valid_unchanged` result with a changed attempt, use reference, owner generation, projection digest, or application binding. | Pi/Workspace application binding denies the attempt and starts zero Provider calls. |
| AM-17 | Owner eligibility changes A→B→A while an old `MemoryUseRef` exists. | The old use remains invalid because its owner-qualification generation differs, even if the body/digest returns to the original value. |
| AM-18 | Delete completes physical purge, then an authorized caller inspects audit state. | Only the minimum non-content tombstone facts are visible; prepare/revalidate remain ineligible. |
| AM-19 | A caller supplies an exact entry list without a matching owner-issued selection proof. | Preparation denies without enumerating, locating, or disclosing alternatives. |
| AM-20 | An authorized user commits one allowed Markdown source blob and requests its explicit admission. | The Source Adapter emits one GitMarkdownSourceProof; admission creates one SQLite-backed Memory revision with commit/blob provenance and no Git write. |
| AM-21 | A Git source uses a moving branch, uncommitted worktree, disallowed/escaping path, missing blob, or merge-conflict body. | Source verification fails before candidate creation; SQLite and Git receive zero mutation. |
| AM-22 | A previously admitted Git/Markdown source changes, is removed, or no longer satisfies source policy before use. | The exact owner reference invalidates or is unavailable; no replacement blob is selected and Memory does not restore or modify the file. |
| AM-23 | SQLite admission, correction, invalidation and deletion run for a Git/Markdown-derived Memory revision. | All lifecycle state changes occur in SQLite; the Git repository has zero writes, merges, commits or history rewrites. |

### Layered evidence

`AM-01` through `AM-23` are the L0/L1 hard deterministic gate for this Module:
schema, identity, authorization, state transition, receipt, leakage and durable
side effects must all pass. L2 trajectory evaluation applies later to the
Workspace workflow that decides which exact references to supply. L3 semantic
judging is not a Memory admission or security gate. L4 CTI expert review is
required only when a future policy admits consequential CTI content or changes
the authority/retention rules. A qualitative score cannot compensate for an
AM-01 through AM-23 failure.

The first integrated Provider case additionally proves that a
`valid_unchanged` view is joined to Pi's actual Provider application binding,
while an `invalidated` or `unavailable` view starts zero Provider calls. That
case depends on the accepted-but-not-yet-integrated Pi/Workspace Context
Preparation seam; its absence blocks integration acceptance, not the core
Module's deterministic acceptance.

Release is staged:

1. **G0 — contract:** records, identity distinctions, source-proof union,
   failure closure and AM-01 through AM-23 are accepted.
2. **G1 — core deterministic:** AM-01 through AM-23 run against the public
   Module Interface with restart/replay and concurrent CAS fixtures.
3. **G2 — context integration:** exact `MemoryUseRef` binds to one actual Pi
   Provider application; pre-provider revalidation denial starts zero Provider.
4. **G3 — storage fault/concurrency:** acknowledgement-unknown, replay,
   crash/reopen, deletion pending and competing revision operations satisfy the
   same public catalogue on the qualified storage Adapter.
5. **G5 — security:** scope/purpose isolation and untrusted-data rendering pass
   in the integrated path. There is no G4 model/trajectory gate for V1 because
   it does not discover, rank, or model-extract Memory.

`NOT_IMPLEMENTED`, `BLOCKED`, or an unavailable owner Adapter is a closed
result, never a passing weighted score.

## Decision audit and reopen conditions

The design was challenged in batches against lifecycle, ownership, recovery,
Context Assembly, and future-extension risks. The following answers remain
candidate design decisions until G0 acceptance.

| Question | Decision and reason | Reopen when |
| --- | --- | --- |
| Does Memory own runtime context? | No. Pi/Workspace Context Assembly already owns runtime composition and Provider evidence; making Memory own it would duplicate message/Tool/digest authority. | Pi exposes no adequate Context Assembly seam, or a second runtime assembler needs a different stable Interface. |
| Does V1 discover or rank Memory? | No. Discovery has different non-disclosure, scope, ranking and index-recovery problems; mixing it into `prepare` would make the Module's Interface shallow and unauditable. | A product workflow names an owner-authorized discovery need and supplies its own acceptance catalogue. |
| Is a generic owner repository sufficient? | No. Session, Workspace, Case and I&E have different authority semantics; a generic repository would erase that distinction. | Two owners demonstrate the same qualification contract and conformance tests prove it. |
| Is an entry identity enough? | No. Revision, operation, source and use identities answer different retry, lineage and disclosure questions. | A concrete lifecycle removes one question without moving its proof into callers. |
| May model output directly write Memory? | No. A model proposal is not a source proof or authority. | An accepted policy creates a separately verified model-output evidence source; it still must pass admission. |
| May correction overwrite content? | No. Correction without revision lineage makes a past use/audit unverifiable. | A retention policy explicitly permits irreversible erasure and preserves the required tombstone/audit semantics. |
| Is SQLite the first Memory Store? | Yes, for the local-host profile. SQLite supplies the single authoritative transactional lifecycle store; the existing `sql.js` work remains an unqualified probe, not the selected Adapter. | A second deployment profile has its own accepted storage decision and SP evidence. |
| Is Git-backed Markdown a second Memory Store? | No. It is the user-editable versioned source that enters Memory only through verified candidate admission; Memory never writes it. | A separately accepted export/mirror contract defines conflict, deletion and authority semantics. |
| Can a local probe prove the complete capability? | No. It may prove only G1/G3 facts it actually executes; G2/G5 remain blocked until Pi/Workspace integration exists. | The relevant integrated public seam is implemented and independently accepted. |

## Implementation order

The module requires ports for record storage, source-proof verification,
owner qualification, authorization, and audit. Session, Workspace, Case, and
I&E are owner adapters only; missing Case/I&E support yields `unavailable`, not
a fake qualified read. Candidate extraction is a future proposal stage, not a
required V1 Adapter: V1 accepts deterministic or explicit candidates.

The planned package owner is `packages/agent-memory/`, with no dependency on Workspace, Case, or I&E. The Code Map route and local package instructions must be established before product code is added.

Implementation order: (1) freeze records, states, failure codes, receipts, and Run-settlement-proof binding; (2) qualify a storage Adapter against deterministic candidate-to-entry lifecycle, exact-reference qualification, correction, deletion, replay, and conformance tests; (3) Session/Run settlement-proof and provider-time revalidation integration; (4) Workspace task-context revisions; (5) Case/I&E adapters; (6) discovery/retrieval and model-assisted extraction only under separate accepted contracts.

The first vertical slice must prove: exact settled Run -> candidate -> admission -> durable entry -> exact-reference qualification -> pre-provider revalidation -> context binding -> correction -> deletion -> crash/replay. This contract's acceptance catalog supplies the formal oracle and release gates.
