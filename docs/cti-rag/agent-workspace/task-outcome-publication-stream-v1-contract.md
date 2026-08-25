# `workspace-task-outcome-publication-stream/v1` Contract

Status: **Design candidate; Design Gate FAIL. No implementation is authorized.**

Supersedes only the candidate/output/delivery shape of
[`workspace-output-publication/v1`](workspace-output-publication-v1-contract.md)
for Task Outcome Reports. Its disclosure isolation, source validation,
non-authority, A4 atomic commit, crash recovery and Case separation remain
normative.

This amendment applies only to Workspace-bound Investigation and Interruption
reports. It does not create a Session/A4 lifecycle for pre-Workspace
Clarification, Unsupported/Policy or Session-free Quick Answer routes.

## 1. Purpose

This amendment distinguishes two events that must never be confused:

```text
complete qualified report
  -> atomic durable publication
  -> optional incremental network delivery
```

The report is published in full or not at all. A client may receive only a
prefix before disconnect, but that is partial delivery of one immutable
publication, not a partial report decision.

Provider/Composer deltas, audit output and uncommitted candidate bytes remain
private.

## 2. Module seam

The existing deep `WorkspaceOutputPublicationModule` gains a versioned report
input and committed-output read operation. No Report Stream Module, report
database or second publication authority is created.

```ts
interface WorkspaceOutputPublicationModuleV2 {
  decideAndCommit(
    input: QualifiedTaskOutcomePublicationInputV1,
  ): Promise<TaskOutcomePublicationDecisionV1>;

  openCommittedReport(
    input: OpenCommittedTaskOutcomeReportInputV1,
  ): Promise<CommittedTaskOutcomeReportDeliveryV1>;
}
```

`decideAndCommit` validates and atomically records one qualified report.
`openCommittedReport` can only read that exact authenticated record for first
delivery or resume. It cannot render, recompose, repair, search or mutate it.

## 3. Publication input and decision

`QualifiedTaskOutcomePublicationInputV1` binds:

- exact qualified report candidate, deterministic validation and required audit
  digests;
- rendered-document bytes, byte length and digest;
- task/route, Workspace and optional Case Revision basis;
- Access Principal, Use Purpose and disclosure-policy generations;
- final Run settlement and Save Point basis where present;
- report kind/profile and composition-attempt count; and
- Pi A4 expected Session tail and idempotency key.

The closed decision is:

```ts
type TaskOutcomePublicationDecisionV1 =
  | {
      status: "published";
      output: PublishedTaskOutcomeReportV1;
      receipt: TaskOutcomePublicationCommitReceiptV1;
    }
  | {
      status: "withheld";
      reasonCode: TaskOutcomePublicationFailureCodeV1;
    };
```

Unknown, conflict, stale, unauthorized, malformed, unqualified or mismatched
inputs append nothing and disclose no content.

## 4. Atomic durable state

One Pi A4 control group appends exactly:

1. the complete `PublishedTaskOutcomeReportV1`, including exact structured
   report, rendered document and deterministic chunk manifest; then
2. the physically last
   `TaskOutcomePublicationCommitReceiptV1`.

The receipt commit is the publication linearization point. Before that point,
zero report content is public. The receipt binds the output entry, report,
document, manifest, validation, audit, settlement, authorization generation,
Session tail and idempotency key digests. The preceding report does not contain
the receipt digest; the post-commit delivery envelope binds both, avoiding a
circular digest.

Commit conflict or unknown outcome uses the accepted A4 exact lookup/recovery
rules. Workspace never appends a replacement report merely because delivery
state is unknown.

## 5. Deterministic chunk manifest

The manifest is computed from the final rendered UTF-8 bytes before commit:

```ts
interface TaskOutcomeReportChunkV1 {
  ordinal: number;
  byteStart: number;
  byteEndExclusive: number;
  text: string;
  chunkDigest: string;
}

interface TaskOutcomeReportChunkManifestV1 {
  algorithm: "workspace-report-utf8-chunks/v1";
  documentDigest: string;
  chunks: readonly TaskOutcomeReportChunkV1[];
  manifestDigest: string;
}
```

Every digest is lowercase `sha256:<64 lowercase hexadecimal characters>` and is
computed over its carrier's canonical form with that digest member omitted.

Rules:

- chunks are contiguous, non-overlapping and cover the document exactly;
- each chunk is at most 16 KiB UTF-8;
- a split never occurs inside a UTF-8 scalar;
- the algorithm prefers section, paragraph and line boundaries, in that order;
- empty documents are invalid; and
- recombining chunk text must reproduce the exact committed document bytes and
  digest.

The manifest contains no Provider boundary, token boundary or private candidate
delta.

## 6. First delivery and resume

`OpenCommittedTaskOutcomeReportInputV1` binds the caller-safe publication
reference, optional opaque cursor, current Access Principal, Use Purpose and
fresh disclosure authority.

The public cursor denotes only:

- committed publication/stream identity;
- next chunk ordinal;
- exact document/manifest digest; and
- cursor integrity/version.

It contains no raw Session, Case, Provider, credential or source identifier.
It is not a bearer authorization: every first delivery and resume requires a
fresh disclosure decision.

The delivery coordinator serializes each chunk emission against current
authorization/visibility invalidation. Revocation may stop later chunks but
cannot retract bytes already delivered. A later authorized resume continues
from the same committed manifest; an unauthorized resume returns a safe closed
failure and no content.

No resume path invokes Composer, Auditor, renderer, Evidence Assembly, Tool or
Provider.

## 7. Public event and result mapping

After publication commit and fresh disclosure admission, a delivery session
emits:

```text
report_stream_started
  -> report_stream_chunk{0..n}
  -> report_stream_completed
  -> one terminal Workspace result
```

For resume, `report_stream_started` carries the admitted next ordinal. Every
chunk carries caller-safe report/stream references, ordinal, text, chunk digest
and next opaque cursor. Started/completed events contain metadata only.

The terminal Workspace result carries the complete structured
`PublishedTaskOutcomeReportV1` for request/response consumers and the same
report/document/manifest digests. Stream chunks are an incremental rendering
transport, not a second report product. A caller that observes both must obtain
byte-identical content.

Save Point-derived progress may precede report delivery under its own contract.
It is not part of the report chunk manifest.

## 8. Failure closure

| Failure | Result |
| --- | --- |
| candidate/validation/audit mismatch | withhold; append nothing |
| stale authorization before commit | withhold; append nothing |
| A4 conflict/unknown | exact lookup/recovery; no duplicate output |
| disclosure revoked before first chunk | no content |
| disclosure revoked between chunks | stop; return safe delivery-interrupted state and cursor for a future freshly authorized resume |
| disconnect | committed output unchanged; resume by cursor |
| cursor/report/manifest mismatch | reject cursor; no content |
| durable output/receipt authentication failure | safe unavailable; no reconstruction |
| chunk recombination/digest mismatch | integrity failure; no further content |
| later Case update rejected | report remains non-authoritative and unchanged |

No failure exposes a private delta, publishes a newly truncated report, skips a
chunk, changes ordering or silently restarts from a new composition.

## 9. Frozen public acceptance matrix

1. No content event occurs before the physically-last publication receipt
   commits.
2. Provider/Composer deltas never equal or enter public chunk events.
3. One committed output plus receipt is appended atomically; no Artifact or
   Case Revision is created.
4. Chunk recombination exactly equals the committed UTF-8 document and digest.
5. Chunk boundaries respect 16 KiB and UTF-8 scalar rules.
6. First delivery and every resume require fresh Access Principal/Use Purpose
   authorization.
7. Revocation before a chunk prevents that and later chunks without altering
   the committed report.
8. Disconnect after any ordinal resumes at exactly the next ordinal.
9. Replayed/foreign/stale/malformed cursor discloses zero content.
10. Resume performs zero Provider, Tool, renderer, Auditor and Evidence
    Assembly calls.
11. Terminal structured result and streamed rendering bind the same immutable
    report.
12. Crash after output append but before receipt is not public and follows A4
    recovery.
13. Crash after receipt commit reopens the exact authenticated report without
    recomposition.
14. Report publication succeeds even when no Case update occurs.

## 10. Frozen architecture decisions

- Publication is atomic; transport delivery may be incremental.
- Only committed report bytes are streamable.
- The existing Publication Module owns both commit and authenticated replay.
- Chunking is deterministic and committed with the report.
- A cursor is position and integrity evidence, never authorization.
- Revocation fences future chunks; delivered bytes are not retractable.
- The final Workspace result remains complete for non-stream consumers.
- No Report Stream Module, Artifact or second Provider lifecycle is created.

## 11. Design Gate

- **Verdict:** FAIL
- **Owner:** Agent Investigation Workspace Publication; Pi owns A4 mechanics
- **Interface:** versioned report `decideAndCommit` plus authenticated
  `openCommittedReport`
- **Input authority:** qualified Task Outcome Report plus current disclosure
  authority
- **Output/evidence:** immutable published report, terminal commit receipt,
  deterministic manifest and resumable public delivery
- **Failure closure:** append none before qualification; disclose only committed
  authenticated bytes
- **Secret isolation:** no Provider delta, credential, hidden identifier,
  unrestricted history or private audit rationale crosses the seam
- **Provider lifecycle count:** zero during Publication/delivery/resume
- **Workspace exposure:** committed report chunks and complete terminal result
  only
- **Backward compatibility:** preserves `workspace-output-publication/v1`
  safety; versions its whole-output event/result shape for reports
- **Public acceptance seam:** actual Workspace publication commit through
  disconnect/revocation/resume and terminal result
- **Remaining blockers:**
  1. **Owner: Task Outcome Report. Expected:** one qualified report carrier and
     deterministic rendered document. **Actual:** its design is closed but its
     upstream contracts and model profiles remain Design Gate FAIL. **Minimal
     fix:** accept the report chain without bypass inputs.
  2. **Owner: Pi Session/public result. Expected:** exact A4 entry/receipt and
     Workspace event/result extension points for committed report delivery.
     **Actual:** the accepted baseline exposes whole output and prohibits
     content-bearing nonterminal events. **Minimal fix:** review and accept the
     versioned Pi/Workspace protocol amendment before implementation.
  3. **Owner: product disclosure policy. Expected:** current-generation
     per-chunk invalidation ordering and caller-safe resume-token integrity.
     **Actual:** the baseline has commit-to-delivery admission but no
     multi-chunk revocation/resume carrier. **Minimal fix:** freeze those
     protocol fields against the existing disclosure-fence Interface.
