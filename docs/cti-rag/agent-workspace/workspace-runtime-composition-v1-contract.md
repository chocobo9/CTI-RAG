# `workspace-runtime-composition/v1` Contract

Status: **Design PASS. Implementation/public-seam PASS is NO.**

## 1. Decision

Session lifetime and Harness lifetime are deliberately different:

| Runtime object | Lifetime | Durable | Reopen behavior |
| --- | --- | --- | --- |
| Pi Session | across Workspace close, process restart and later reopen | yes, through `SessionRepository` | the same opaque Session reference is recovered/acquired with a new lease generation |
| Session lease | one successful Workspace open | no | released on close; a later open obtains a greater generation |
| AgentHarness | one successful Workspace open | no | reconstructed once from committed Session configuration plus current trusted application configuration |
| Agent Run state | one admitted Run | no | settled or discarded; never resumed from a serialized Harness |

“Long-lived Harness” means **Workspace-lifetime Harness**, not a persisted or
process-lifetime object. Pi Session persistence and lease behavior are already
owned and accepted by `SessionRepository`; they are not a PNW-B design blocker.

## 2. Ownership and seam

No new public Runtime Manager Interface is introduced. Composition belongs
inside the existing deep public seam:

```text
CaseWorkspaceModule.open -> CaseWorkspace.prompt / close
```

`CaseWorkspaceModule` receives a Pi `SessionRepository` through trusted module
composition. Its public `open` input carries the opaque repository-issued
Session reference, never a raw `Session`, storage, path, metadata value or
lease.

Internally, one successful `open` owns:

- one recovered/acquired `SessionLease`;
- the guarded Session exposed by that lease;
- one Provider Dispatch runtime opened against that exact Models/Session pair;
- one AgentHarness constructed against the same pair;
- one fixed hook graph and Workspace Turn Adapter; and
- one idempotent close operation.

The Session Repository remains the only owner of provisioning, opaque-reference
resolution, recovery, lease generation and release fencing. Harness remains
Pi-owned execution machinery. Workspace owns their composition and CTI policy.

## 3. Open sequence

A normal reopen performs these steps in order:

1. snapshot and validate the public Case, Access Principal and opaque Session
   reference;
2. ask the configured repository to recover the Session;
3. require one live guarded lease or fail `open`;
4. read the committed Session context/configuration through the guarded
   Session;
5. reconstruct current Orientation and Workspace eligibility under that lease;
6. resolve committed model/thinking/active-Tool identifiers against current
   trusted registries;
7. open one Provider Dispatch runtime with the exact Models and guarded Session;
8. construct one AgentHarness with that same Models/Session identity;
9. install the fixed context, event, save-point, settlement and run-generation
   policies once; and
10. return `CaseWorkspace`.

Any failure after lease acquisition aborts local setup, removes installed
handlers, releases the lease, returns no Workspace and starts no Provider.

New Session issuance remains the already accepted
`SessionRepository.provision(...) -> { sessionRef, lease }` responsibility.
Product bootstrap may retain the opaque `sessionRef`; PNW-B neither invents a
second Session identity nor changes repository semantics.

## 4. Harness reconstruction

The new Harness is reconstructed, not restored byte-for-byte.

Durable Session configuration supplies only committed:

- model reference;
- thinking level;
- active Tool names;
- transcript/tree/compaction state; and
- Pi/application receipts.

Current trusted application composition supplies:

- Models and Provider/Auth registry;
- Tool implementations and resources;
- system-instruction resolver;
- context-entry policy;
- save-point policy;
- Provider Dispatch application authority/authenticator;
- Run settlement application; and
- run-generation fencing options.

Runtime-only queues, handlers, AbortControllers, prepared Provider values,
permits, in-flight Tools, event subscribers and active Run objects are never
serialized. Recovery resolves durable Session truth, then creates a fresh
Harness. It never resumes a Provider stream or replays a Tool.

If a committed model or active Tool name is unavailable under current trusted
configuration, `open` fails closed. It does not silently select a replacement.

## 5. Prompt behavior

Every `prompt` on one open Workspace uses the same Harness and guarded Session.
Task Understanding may use the existing bounded one-shot Provider Dispatch
frontend, but it creates no Session or Harness.

For the Investigation Run:

- Session context qualification runs against the guarded Session;
- the Workspace context hook appends one ephemeral Workspace Context envelope
  after selected historical messages;
- `AgentHarness.prompt` supplies the exact current Original User Task after
  that context;
- Tools remain in the Pi Tool channel;
- Provider Dispatch remains the only final canonical/digest/count owner; and
- save point and settlement commit directly to the guarded Session.

The current staging Session, transcript copy, per-Turn Harness and copy-back
span are deleted when this vertical passes. They are not retained as a fallback
or compatibility path.

## 6. Close sequence

`CaseWorkspace.close()` is idempotent and owns this order:

1. stop admitting new Turns;
2. settle an already-claimed completion, otherwise cancel/retire the active Run;
3. await the Harness abort/settlement barrier;
4. prevent all late event, Session, Tool and publication sinks through the
   accepted run-generation fence;
5. remove Workspace-owned handlers/subscriptions;
6. complete pending Orientation cleanup that is safe before release; and
7. release the Session lease.

Lease release occurs last. After it resolves, the old guarded Session and every
prepared A4 handle are fenced. The discarded Harness has no authority to regain
the lease.

## 7. Failure closure

| Failure | Closed result |
| --- | --- |
| malformed/unknown/foreign Session reference | `open` fails; no Session body or existence leakage |
| recovery unavailable/conflict | `open` fails; no Harness or Provider runtime |
| live competing lease | `open` fails with safe Session-in-use classification |
| committed configuration cannot be resolved | release lease; no Harness returned |
| Orientation/authorization fails during open | release lease; no Harness returned |
| Provider runtime or Harness construction fails | release lease; no Provider start |
| lease lost while open | retire active Run, close Workspace, deny all later Session/Provider work |
| close races prompt | accepted completion claim settles once; otherwise Run is retired and cannot write late |
| process crash | Harness is lost; repository recovery classifies Session truth before a fresh Harness is built |

No failure falls back to a raw Session, staging Session or second Harness.

## 8. Frozen public acceptance matrix

The public seam is
`CaseWorkspaceModule.open -> prompt/close -> WorkspaceTurn`, using real Pi
Memory/JSONL repository Adapters and deterministic fake Providers.

1. Two successful prompts on one open Workspace use one Harness, one guarded
   Session lease generation and one non-duplicated transcript.
2. Task Understanding uses the bounded one-shot frontend and creates zero
   Harnesses/Sessions; the Investigation Runs use the one Workspace Harness.
3. The context hook is installed once, preserves selected Session history,
   appends one transient Workspace envelope, and leaves the exact current task
   once as the Harness prompt.
4. Save-point, Provider receipt and Run-settlement entries commit directly to
   the guarded Session; no staging/copy-back entries exist.
5. A second concurrent open for the same opaque reference fails and starts zero
   Provider work.
6. Failure at every post-acquisition open cutpoint releases the lease and
   returns no partial Workspace.
7. Close during pre-Run, Provider work and completion claim produces one
   terminal public result and no late Session/event writes.
8. Close releases the lease only after the Harness settlement/retirement
   barrier; all old-lease reads/writes then fail.
9. Reopen after close obtains a greater lease generation, reconstructs one new
   Harness, sees committed history/configuration and does not restore runtime
   queues/handlers/prepared values.
10. Crash recovery creates a fresh Harness only after repository recovery;
    incomplete Provider/Tool work is never resumed or replayed.
11. Missing committed model/Tool configuration fails open rather than choosing
    a substitute.
12. Public cancellation, invalidation, supersession and Orientation behavior
    retain their existing safe terminal semantics.
13. Repository lease/recovery, Harness save-point/context-policy/dispatch/run
    generation/settlement and Workspace focused regressions remain green.
14. Root check passes under the accepted Node runtime.

The first public RED must demonstrate two prompts currently create two staging
Sessions/Harnesses. Tests may count factory construction at the trusted
composition seam, but must verify transcript, events, Session entries and
Provider starts through the public Workspace Interface rather than testing a
private helper.

## 9. Design Gate

- **Verdict:** PASS
- **Owner:** Agent Investigation Workspace composition over Pi-owned runtime
- **Interface:** existing `CaseWorkspaceModule.open -> prompt/close`
- **Input authority:** opaque repository-issued Session reference plus trusted
  application configuration
- **Output/evidence:** one Workspace bound to one lease generation and one
  reconstructed Harness
- **Failure closure:** specified
- **Secret isolation:** no storage path, lease token, credentials or prepared
  Provider value crosses the public Interface
- **Provider lifecycle count:** one shared Provider Dispatch runtime per open
  Workspace
- **Workspace exposure:** opaque Session reference only; no raw Session/Harness
- **Backward compatibility:** raw caller Session and staging path are removed
- **Public acceptance seam:** public Workspace open/prompt/close
- **Remaining blockers:** none at design level; implementation remains NO
