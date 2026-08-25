# `workspace-task-outcome-report/v1` Contract

Status: **Design candidate; Design Gate FAIL. No implementation is authorized.**

Research basis:

- [Task Result, Evidence Assembly and Report Packet Research](../research/task-result-evidence-assembly-report-packet-research-2026-07-22.md)
- [DeepSeek Report Composer Fit](../research/deepseek-report-composer-fit-2026-07-22.md)

## 1. Product purpose

Task Outcome Report is the fourth and first public product in the report chain:

```text
Task Result
  -> Claim-Evidence Subgraph
  -> Report Evidence Packet
  -> private report candidate
  -> deterministic validation
  -> narrow independent Evidence Audit
  -> Publication decision
  -> public Task Outcome Report stream
```

It answers:

> What should the user be told about this task, its result, evidence,
> limitations, interruption state and next steps?

It is non-authoritative Workspace output. Publication does not create a Case
finding, Case Evidence Reference, Artifact or Case Revision.

This contract freezes the field-level semantic carrier, bounds and mappings
before fixing a JSON Schema or implementing a Composer.

## 2. Reuse and seam

Task Outcome Report is a shared product output shape, not a shared lifecycle.
Formal Investigation and Workspace-bound Interruption deepen the existing
Workspace Publication seam. Pre-Workspace Clarification and Unsupported/Policy
reports remain owned by Task Intake; Quick Answer remains owned by the Quick
Response route. They may share this public union but cannot fabricate a
Workspace, Session or A4 receipt merely to publish it.

This contract does not create a Report Module, report Agent loop or report
database.

It reuses:

- Task Intake/route decisions for clarification and unsupported outcomes;
- the bounded Quick Response result for simple tasks;
- Task Result, Evidence Assembly and Report Evidence Packet for formal
  investigation;
- Pi's bounded one-shot Provider Dispatch for report composition and audit;
- Workspace deterministic citation/authorization validation;
- Pi Session A4 control batches for publication;
- existing Save Point progress events; and
- Case Management's separate Case-update proposal/acceptance flow.

The existing `workspace-output-publication/v1` contract remains the accepted
baseline for private-candidate disclosure fencing, exact source/citation checks,
non-authority and atomic publication. Its direct
`ModelResponseCandidateV1 -> PublishedWorkspaceOutputV1` content shape must be
versioned for Workspace-bound reports in this chain; it is not duplicated.
Route-owned non-Workspace publication contracts remain a Design Gate blocker.

## 3. Mandatory report variants

Every accepted product route produces exactly one route-appropriate Task
Outcome Report:

### 3.1 Clarification Report

Contains the admitted understanding, material ambiguity and exact user input
needed next. It creates no Case/Session/Run and contains no investigative
finding.

### 3.2 Quick Answer Report

Contains one bounded answer, its qualified citations when factual material is
used, limitations and next step. It creates no hidden formal investigation and
cannot use Tools, new search or Case mutation.

### 3.3 Investigation Report

Consumes one exact Report Evidence Packet and may contain completed,
insufficient-evidence, budget-exhausted or blocked results. It cannot describe a
bounded-incomplete task as fully completed.

### 3.4 Interruption Report

For failed, cancelled or discarded work:

- with a trusted Save Point, reports only committed completed/incomplete work,
  blocker, resumable basis and safe next step;
- without a trusted Save Point, reports status only and explicitly says that no
  trustworthy semantic result can be recovered.

It never reconstructs claims from raw Session history or invokes another
investigation model after interruption.

### 3.5 Unsupported/Policy Report

States the unsupported capability, authorization or policy reason and safe
alternatives when permitted. It contains no fabricated investigation result.

## 4. Common report information model

Every report variant has:

- public report identity/version;
- task identity safe projection;
- report kind and status;
- concise result/phase summary;
- completed and incomplete work appropriate to the route;
- limitations, uncertainty and coverage;
- next action or clarification when applicable;
- authority label `non_authoritative_workspace_output`;
- publication identity, with receipt binding supplied by the publication
  envelope; and
- explicit absence or separately accepted status of any Case update.

Factual or analytical reports additionally have:

- per-goal results;
- individually addressable findings;
- statement class preserved from Task Result;
- caller-safe citations and evidence aliases;
- source assertion versus Workspace analysis distinction;
- supporting, contradicting and qualifying material;
- lineage/dependency treatment;
- alternative explanations;
- unresolved gaps; and
- confidence expressed only under a trusted report profile and packet basis.

The Composer cannot invent a probability, confidence or source-reliability
score. If the packet supplies no accepted confidence policy, the report uses
qualitative uncertainty and limitations only.

### 4.1 Closed common carrier

The private candidate and published report share the following semantic
carrier. Private bindings and audit evidence are removed, not renamed, at the
public boundary.

```ts
type TaskOutcomeReportKindV1 =
  | "clarification"
  | "quick_answer"
  | "investigation"
  | "interruption"
  | "unsupported_policy";

type TaskOutcomeReportStatusV1 =
  | "needs_input"
  | "completed"
  | "bounded_incomplete"
  | "interrupted"
  | "unsupported";

interface TaskOutcomeReportCommonV1 {
  protocol: "workspace-task-outcome-report/v1";
  reportRef: string;
  taskRef: string;
  kind: TaskOutcomeReportKindV1;
  status: TaskOutcomeReportStatusV1;
  title: string;
  summary: string;
  limitations: readonly string[];
  nextSteps: readonly string[];
  caseUpdateStatusAtPublication:
    | "not_part_of_report_publication"
    | "pending_separate_decision"
    | "accepted_before_publication"
    | "rejected_before_publication";
  authority: "non_authoritative_workspace_output";
}
```

`taskRef` and `reportRef` are caller-safe public references. They are not raw
Session, Workspace, Provider, Case, Resource or credential identifiers.
`caseUpdateStatusAtPublication` is a snapshot at publication and does not
predict a later Case decision.

Every digest in this contract is lowercase
`sha256:<64 lowercase hexadecimal characters>`. A carrier's digest is computed
over its canonical form with that digest member omitted.

### 4.2 Closed variant payloads

`TaskOutcomeReportV1` is a discriminated union of the common carrier and exactly
one payload:

| Kind | Required payload | Forbidden payload |
| --- | --- | --- |
| `clarification` | admitted task summary, ordered material ambiguities, ordered questions | findings, citations, Case/Run claims |
| `quick_answer` | answer blocks, qualified public citations when used, limitations | hidden Investigation Run, Tool result, Case mutation |
| `investigation` | disposition, per-goal results, findings, contradictions, coverage gaps, citations | uncited factual finding, aggregate completion stronger than Task Result |
| `interruption` | interruption code, completed/incomplete work, blocker, trusted Save Point basis or explicit absence, resume guidance | reconstructed uncommitted claim, invented resume state |
| `unsupported_policy` | closed reason code, safe explanation, permitted alternatives | investigative finding, hidden policy detail, unauthorized workaround |

The Investigation and evidence-bearing Interruption payloads use these closed
statement carriers:

```ts
type ReportStatementClassV1 =
  | "source_assertion"
  | "workspace_analysis"
  | "unresolved_question"
  | "status_or_coverage";

interface ReportFindingCandidateV1 {
  findingAlias: string;
  goalAlias: string;
  statementClass: ReportStatementClassV1;
  text: string;
  citationAliases: readonly string[];
  contradictionAliases: readonly string[];
  qualification:
    | "supported_with_limits"
    | "contested"
    | "limited"
    | "unresolved";
}

interface ReportCitationProjectionV1 {
  citationAlias: string;
  sourceLabel: string;
  sourceVersionLabel: string;
  locator: string;
  exactExcerpt: string | null;
}
```

`qualification` is not probability or truth scoring. It is derived from the
packet's admitted relation, contradiction, lineage and coverage state. Repeated
or similar material may increase reported prevalence, but shared or unknown
lineage never increases independent corroboration.

### 4.3 Private candidate binding

`PrivateTaskOutcomeReportCandidateV1` adds:

- exact Task Result, subgraph and packet digests when the route uses them;
- report-profile, Composer invocation, logical model, attempt and candidate
  digests;
- ordered section aliases and ordered finding/citation projections;
- composition attempt `1 | 2`; and
- a candidate canonical-form digest.

The candidate contains no publication identity and is never caller-visible.
Composition attempt 2 must bind the same packet/profile and only the first
audit's closed findings. It cannot bind a new source, search result or Task
Result.

### 4.4 Deterministic validation result

Workspace produces one
`TaskOutcomeReportDeterministicValidationResultV1`:

```ts
interface TaskOutcomeReportDeterministicValidationResultV1 {
  protocol: "workspace-task-outcome-report-validation/v1";
  candidateDigest: string;
  packetDigest: string | null;
  result: "passed" | "failed";
  issueCodes: readonly TaskOutcomeValidationIssueCodeV1[];
  validationDigest: string;
}
```

The closed issue catalog covers identity mismatch, unknown or missing alias,
literal/span/version mismatch, stale or unauthorized material, strengthened
disposition, omitted contradiction/coverage, invalid section ordering,
out-of-bounds content, hidden identifier, secret-like value, Case-authority
claim and malformed canonical form. It carries codes and aliases only, never
source bodies or Provider error text.

### 4.5 Evidence Audit result

Evidence-bearing reports produce one fresh-context
`TaskOutcomeEvidenceAuditResultV1` per composition attempt:

```ts
type EvidenceAuditFindingClassV1 =
  | "supported"
  | "unsupported"
  | "contradicted"
  | "citation_mismatch"
  | "overstated"
  | "not_verifiable";

interface EvidenceAuditClaimFindingV1 {
  findingAlias: string;
  classification: EvidenceAuditFindingClassV1;
  citedAliasBasis: readonly string[];
  reasonCode: string;
  boundedRationale: string;
}

interface TaskOutcomeEvidenceAuditResultV1 {
  protocol: "workspace-task-outcome-evidence-audit/v1";
  candidateDigest: string;
  packetDigest: string;
  auditProfileRef: string;
  auditInvocationDigest: string;
  findings: readonly EvidenceAuditClaimFindingV1[];
  result: "passed" | "failed";
  auditDigest: string;
}
```

The Auditor must return exactly one finding for every factual or analytical
report finding and none for status-only statements. Workspace validates aliases
and completeness deterministically. `boundedRationale` is private repair
evidence, not a new fact or public report content.

### 4.6 Qualified publication candidate and rendering

A `QualifiedTaskOutcomeReportCandidateV1` exists only when deterministic
validation passed and every required audit finding is `supported`. It binds the
candidate, validation and audit digests and freezes the public projection.

One deterministic renderer then maps the public projection to UTF-8 Markdown:

- fixed section order is selected by report kind/profile;
- headings, citation syntax and limitation labels are system-owned;
- finding and citation order follows canonical aliases;
- no model-generated HTML, link target, footnote identifier or hidden metadata
  is accepted; and
- the exact rendered text, byte length and digest are frozen before
  publication.

The durable published report carrier adds `publicationRef` and:

```ts
interface PublishedTaskOutcomeDocumentV1 {
  mediaType: "text/markdown; charset=utf-8";
  text: string;
  byteLength: number;
  textDigest: string;
}
```

The renderer does not summarize, correct or reinterpret the candidate.
The report record does not contain its later receipt digest. Publication stores
the report first and the physically-last receipt second; the terminal delivery
envelope binds both digests after commit. This avoids a circular digest.

### 4.7 Profiles and bounds

Formal packets select exactly one existing report profile:

- `investigation_complete/v1`;
- `investigation_limited/v1`; or
- `interruption_recovery/v1`.

Clarification, Quick Answer and Unsupported/Policy use their route-owned
profile and do not fabricate a formal packet. The public carrier is bounded by:

- at most 13 sections, 64 findings and 256 distinct citation projections;
- at most 16 citations or contradictions per finding;
- title 256 UTF-8 bytes, summary 8 KiB, each finding/answer block 16 KiB;
- each limitation/next step/question 4 KiB and at most 32 of each;
- each private audit rationale 2 KiB;
- private candidate canonical form 256 KiB;
- public rendered Markdown 256 KiB; and
- exactly one initial composition plus at most one same-packet recomposition.

Over-bound input is a closed failure. Workspace does not truncate evidence,
claims or citations into a misleading report.

## 5. Formal report composition

Formal Investigation Report composition is one bounded no-tool model call after
the Report Evidence Packet is committed and admitted.

Candidate profile:

```text
logical profile: report_composer/deepseek-v1
provider model candidate: deepseek-v4-pro
mode: non-thinking
output: private closed structured report candidate
tools: none
```

This is a candidate profile, not model qualification or activation.

The Composer:

- receives only trusted report instructions and the exact packet;
- may select wording and organization allowed by the report profile;
- must preserve disposition, statement classes, citations, contradictions,
  lineage status, uncertainty and coverage;
- may omit only profile-optional material recorded by the packet;
- cannot query sources, use Tools/Memory, add evidence, create aliases, change
  Case state or publish; and
- returns one complete private candidate bound to packet/profile/invocation.

Malformed, empty, truncated, uncited, out-of-profile or refused output is a
candidate failure. Workspace does not repair it by guessing.

## 6. Deterministic validation

Before audit, Workspace proves:

- candidate/report/packet/profile/Provider-attempt identity equality;
- every claim and citation alias exists in the exact packet;
- Resource Version, Source Span/excerpt, literal, identifier, date and number
  equality where mechanically checkable;
- no stale, hidden, withdrawn, unqualified or foreign source appears;
- task disposition, per-goal state, statement class, contradiction, lineage and
  coverage are not strengthened or omitted;
- report bounds and required sections hold;
- no secret, hidden identifier, Tool instruction or source-supplied system
  instruction is exposed; and
- no Case acceptance or mutation is claimed.

Deterministic validation proves identity, authorization and mechanical
faithfulness. It does not prove that evidence semantically entails an analysis.

## 7. Narrow independent Evidence Audit

Any report containing factual or analytical claims receives one fresh-context
audit. The auditor sees only:

- the exact report candidate;
- exact packet claims, evidence excerpts/facts and relationship classes; and
- one fixed audit rubric.

It receives no investigation conversation, Composer conversation, Memory,
Tools, credentials, hidden reasoning, graph/vector query capability or Case
write capability.

For each report claim it decides only:

- supported;
- unsupported;
- contradicted;
- citation mismatch;
- overstated; or
- not verifiable.

It may not route the task, investigate, retrieve, rewrite the report, add a
fact, create a citation, select a different source, change confidence, publish
or approve a Case update.

Any non-supported material finding withholds the candidate. At most one
separately budgeted recomposition may receive the exact audit findings plus the
same original packet. It cannot receive new evidence. A second failure stops
with a withheld/human-review-required result.

Clarification, unsupported and mechanically rendered status-only interruption
reports do not call an auditor merely to repeat trusted codes.

The Composer and Auditor must not use the same model family for an
evidence-bearing report. Their qualified profiles carry closed
`modelFamilyRef` values and Workspace proves inequality before dispatch. Exact
auditor/provider qualification remains open.

## 8. Publication and streaming

Provider report deltas are private. They are not the public report stream.

The order is:

```text
private Composer stream
  -> complete report candidate
  -> deterministic validation
  -> Evidence Audit when required
  -> immutable publication candidate
  -> atomic output + publication-receipt commit
  -> public rendering stream
  -> one terminal report result
```

The public stream reads only the committed immutable report output. It may send
sections/chunks incrementally, but cannot change their bytes or order.
Disconnect/resume uses the committed public report identity and output cursor;
it never resumes or splices the Provider stream.

This is partial delivery of an already complete publication, not partial
publication. The committed report exists in full before the first public
content chunk. The versioned delivery behavior is owned by
[`workspace-task-outcome-publication-stream/v1`](task-outcome-publication-stream-v1-contract.md).

That amendment applies only after a Workspace-bound report exists.
Clarification, Unsupported/Policy and any Quick Answer that intentionally
creates no Pi Session require their route owner's own atomic public-result seam.
They reuse the report union and deterministic rendering rules, not Workspace
receipt identities.

Existing Save Point progress events may precede the report, but they contain
only committed safe progress and are not report drafts.

## 9. Case update separation

A published report:

- does not change the Case;
- does not create an Evidence Reference or accepted finding;
- does not imply human acceptance;
- cannot carry a write permit; and
- may only produce a separate Case Update Proposal candidate.

Case Management independently validates identity, Case Revision,
authorization, operation intent and proposal evidence. Report success with no
Case update is a normal accepted outcome.

## 10. Failure closure

| Failure | Required public result |
| --- | --- |
| clarification required | Clarification Report; no Case/Run |
| quick answer cannot satisfy route/profile safely | no downgrade guessing; route must clarify or formalize |
| Task Result/subgraph/packet unavailable | safe withheld/blocked result; no Composer |
| Composer malformed/refused/over-budget | candidate failure; no raw delta |
| deterministic citation/version/auth failure | withhold before audit |
| audit finds unsupported/contradicted/overstated claim | withhold; at most one same-packet recomposition |
| second composition/audit failure | human-review-required/withheld |
| publication commit conflict/unknown | append nothing or exact lookup; no uncommitted stream |
| stream disconnect after publish | resume committed output cursor only |
| Case update rejected/absent | report remains published and non-authoritative; Case unchanged |

No failure publishes a partial private candidate, guesses evidence, reruns the
investigation or silently weakens the report profile.

## 11. Public acceptance candidates

1. Every accepted route produces exactly one correct report variant.
2. Clarification creates no Case/Session/Run and contains no finding.
3. Quick Answer remains one bounded no-tool/no-new-search result.
4. Completed formal investigation produces a cited Investigation Report from
   one exact packet.
5. Insufficient/budget/blocked reports preserve completed and incomplete goals
   without claiming aggregate completion.
6. Interruption with a trusted Save Point reports only committed work.
7. Interruption without a trusted Save Point reports status only.
8. Composer uses one configured DeepSeek candidate profile and zero Tools.
9. Invented citation/alias/literal/version fails deterministic validation.
10. A real citation that does not support the claim fails the independent
    audit.
11. Shared-lineage repetition and unknown dependency cannot be rendered as
    multiple independent confirmations.
12. Material contradiction, uncertainty and coverage limit cannot be omitted.
13. Auditor cannot rewrite, retrieve, publish or authorize Case mutation.
14. At most one same-packet recomposition occurs; second failure stops.
15. No Provider delta is public before publication commit.
16. Committed report bytes stream in fixed order and resume only by public
    output cursor.
17. Published report changes no Case Revision and creates no Evidence Reference.
18. A separately rejected Case update leaves the report intact and explicitly
    non-authoritative.
19. Existing Pi Agent/Tool results, Save Points, settlement, Provider Dispatch
    and Publication evidence are reused rather than redefined.
20. Every closed report variant rejects fields belonging only to another
    variant.
21. Deterministic rendering of the same qualified candidate produces identical
    UTF-8 bytes and digest.
22. An incomplete audit, unknown finding alias or non-supported material
    finding cannot produce a qualified publication candidate.
23. Similar sources with shared or unknown lineage do not become multiple
    independent confirmations.
24. A disconnect can expose only a prefix of an already committed report; resume
    returns the remaining committed bytes without recomposition.

The matrix remains candidate material until the blockers below close.

## 12. Frozen architecture decisions

- Every accepted task route produces a Task Outcome Report.
- Formal investigation reporting consumes only a Report Evidence Packet.
- Formal Composer and Auditor are bounded no-tool one-shot calls.
- DeepSeek V4 Pro non-thinking is the Composer candidate, not yet qualified.
- Deterministic validation precedes semantic audit.
- Evidence Audit is single-purpose and cannot rewrite or investigate.
- Raw model deltas never become public.
- Public streaming reads only an immutable committed report.
- Report publication and Case acceptance are independent.
- Existing Pi and Publication primitives are reused; no report Agent loop or
  report database is added.
- The Composer returns structure; a deterministic Workspace renderer owns the
  exact public Markdown bytes.
- V1 publishes no numeric confidence or source-reliability score.

## 13. Design Gate

- **Verdict:** FAIL
- **Owner:** Agent Investigation Workspace Publication; route, I&E, Pi and Case
  owners retain their authorities
- **Interface:** one route-appropriate private candidate to one published or
  withheld Task Outcome Report stream
- **Input authority:** route-specific trusted outcome; formal reports require
  exact Task Result/subgraph/packet and Provider evidence
- **Output/evidence:** one immutable non-authoritative report or safe withheld
  result plus publication receipt and public stream identity
- **Failure closure:** raw candidate never leaks; validation/audit failure
  withholds; stream resumes only committed output
- **Secret isolation:** Composer/Auditor/public output exclude credentials,
  unrestricted history, hidden graph/IDs and Tools
- **Provider lifecycle count:** formal path one Composer, one Auditor when
  claims exist and at most one same-packet recomposition
- **Workspace exposure:** safe progress, report status and committed report
  content only
- **Backward compatibility:** current `ModelResponseCandidateV1` direct output
  is a migration baseline to version/supersede, not a Task Result/report alias
- **Public acceptance seam:** product task entry through actual publication
  commit and resumable public report stream
- **Remaining blockers:**
  1. **Owner: upstream task/report chain. Expected:** accepted route-specific
     outcome and formal Task Result/subgraph/packet contracts. **Actual:** the
     three formal upstream contracts remain Design Gate FAIL and Quick Response
     result/report input is not frozen. **Minimal fix:** close upstream
     contracts without bypass fixtures.
  2. **Owner: route owners. Expected:** route-owned closed Clarification, Quick
     Answer and Unsupported/Policy inputs that map into the frozen report union.
     **Actual:** the formal report profiles and output mapping are closed here,
     but the non-formal route inputs remain product candidates. **Minimal fix:**
     freeze those three bounded route results and their non-Workspace atomic
     public-result seams without creating Task Result, Report Evidence Packet
     or fake Session substitutes.
  3. **Owner: model qualification. Expected:** measured DeepSeek Composer and
     different-family Auditor profiles with accepted budgets, failure rates and
     human-review threshold. **Actual:** the report, audit and committed-output
     streaming contracts are closed design candidates, but model profiles are
     unqualified. **Minimal fix:** run offline qualification against the frozen
     public matrix and accept or replace the candidates before implementation.
