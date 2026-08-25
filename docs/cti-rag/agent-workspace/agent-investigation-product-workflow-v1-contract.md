# `agent-investigation-product-workflow/v1` Contract

Status: **Design candidate; Design Gate FAIL. No implementation is authorized.**

Research basis:
[DeepSeek Report Composer Fit](../research/deepseek-report-composer-fit-2026-07-22.md).

## 1. Product outcome

This contract describes what the CTI Agent does for the user. Pi Session,
Harness and Provider Dispatch are supporting infrastructure, not the product
workflow.

```text
User Task
  -> Small-model Task Intake and structured route
       -> Clarification
       -> Quick Response
       -> Formal Investigation
       -> Unsupported/forbidden request

Formal Investigation
  -> Case + Session + Workspace bootstrap
  -> Investigation Work Plan
  -> Evidence-gathering Agent Loop
  -> committed Save Points and progress stream
  -> completion / interruption / continuation decision
  -> Task Outcome Report Composition
  -> Deterministic Validation
  -> narrow Independent Evidence Audit
  -> committed Publication Decision
  -> public Outcome Stream
  -> Optional Case Update Proposal

Every route
  -> Task Outcome Report
  -> exactly one public terminal outcome
```

The model may propose intent, actions, completion, report text and Case update
candidates. Deterministic Workspace/owner Modules admit every transition.

The product is experienced as one `TaskOutcomeStream`: admitted progress
updates, followed by one completed, interrupted, clarification, unsupported or
withheld Task Outcome Report. A report is therefore mandatory product feedback,
not an optional document produced only by a successful formal investigation.

## 2. Stage A: Task Intake and Routing

Task Intake occurs before a new Case or Workspace is created. This differs from
the currently implemented Task Understanding path, which runs inside an already
opened Case Workspace. Supporting a global user entry point therefore requires
a new upstream product seam.

The intake model is a bounded small-model call. It may:

- preserve and lightly normalize the Original User Task under the existing
  protected-literal rules;
- identify intent and requested outcomes;
- identify material ambiguities;
- classify the task into exactly one structured route and provide route reasons;
  and
- produce one through four formal-investigation goal seeds when applicable.

It may not answer the task, create a Case, select a Tool, retrieve data, grant
authorization or execute the selected route.

The semantic routing decision belongs to the intake model because open-ended
user intent cannot be exhaustively enumerated in code. Its output is a closed,
machine-readable route:

```text
clarification | quick_response | formal_investigation | unsupported
```

After the model returns, a deterministic route-admission gate performs only
mechanical and safety work:

- validate the closed schema and bind it to the exact Original User Task;
- reject missing, contradictory or out-of-range fields;
- enforce authorization, capability and product-scope restrictions;
- prevent an unsafe downgrade when the declared required behavior itself
  requires evidence acquisition, Tools, Case mutation or formal reporting; and
- execute the admitted route exactly once.

The gate does not interpret arbitrary user language or independently classify
all possible intents. It may reject, request clarification or conservatively
escalate a model route under a closed hard rule; it may not silently downgrade
a formal investigation to a Quick Response.

The intake model's route has four outcomes:

### Clarification

Used when subject, scope, desired outcome, continuity reference, effect intent
or success criteria is materially ambiguous. No Case, Session, Workspace or
Investigation Run is created.

### Quick Response

Allowed only when all are true:

- exactly one bounded read-only outcome;
- answerable from the Original User Task and already qualified entry context;
- no new evidence acquisition, Tool, cross-source corroboration or Case write;
- no formal report or Case update requested;
- no material ambiguity; and
- the quick-response token/time/cost profile can contain the complete request.

Quick Response is a separate one-shot response call after routing. The intake
model itself never answers. Its output still passes the normal publication and
citation rules applicable to the sources it uses.

### Formal Investigation

Required when any requested outcome needs:

- new evidence or a data source;
- multiple-source comparison or corroboration;
- a timeline, attribution, assessment or uncertainty treatment;
- Tool use or iterative questioning;
- more than one investigation goal;
- a formal report; or
- a Case update proposal.

The intake model selects Formal Investigation from the task's required
behavior, rather than from a bare scalar “complexity score.” The admission gate
checks only the closed safety invariants above.

### Unsupported or forbidden

Requests outside the current product capability, authorization or accepted
Case-write/publication scope fail closed. They are not silently downgraded into
Quick Response.

## 3. Stage B: Case, Session and Workspace bootstrap

Bootstrap begins only after `formal_investigation` is admitted.

For a new investigation:

1. Case Management creates or accepts one Case identity and initial mandate;
2. Pi provisions one durable opaque Session;
3. Workspace opens under one Session lease and reconstructs its
   Workspace-lifetime Harness;
4. the admitted intake handoff is committed to that Session; and
5. Run Context Preparation admits the first Investigation Run.

For an existing Case continuation, bootstrap revalidates the supplied Case and
Session references and opens the existing Workspace basis. It does not create a
duplicate Case or Session.

This contract does not define Case database fields or authorize Case writes.
Case creation/update behavior remains a Case Management Interface.

## 4. Stage C: Investigation Work Plan

The user-visible “TODO” is named the **Investigation Work Plan**. It is a
projection of admitted Run Control state, not a second planner, task graph or
authority.

It contains:

- immutable investigation goals from the admitted intake handoff;
- current flat subquestions;
- admitted or pending evidence-gathering actions;
- status and bounded reason for each item;
- unresolved contradictions and evidence gaps; and
- remaining Run budgets.

The Work Plan is initialized immediately after formal Run admission:

1. deterministic code creates one goal per admitted goal seed;
2. the first main-Agent turn proposes bounded subquestions and next actions;
3. Run Control validates and admits only in-scope proposals; and
4. the public Work Plan projection is refreshed.

It is refreshed after an admitted Tool result, evidence observation, local
adjustment or stop decision. Streaming model text does not mutate it.

The Work Plan may display:

```text
open -> in_progress -> addressed
                    -> insufficient_evidence
                    -> blocked
                    -> budget_exhausted
```

These are projections of existing goal/subquestion/pending-action facts.
The model cannot mark an item complete merely by emitting `done`.

## 5. Stage D: Evidence-gathering Agent Loop

The main Investigation Agent Loop starts only when Case/Session/Workspace,
committed task handoff, Run context and budgets are ready.

Each cycle is:

```text
select next open goal/subquestion
  -> propose query/capability action
  -> deterministic admission
  -> Tool/provider execution
  -> qualify and record outcome
  -> update Working State and Work Plan
  -> propose next action or stop
```

RAG is one admitted Tool capability inside this loop, not a hidden retrieval
step and not a database Interface exposed to the model. When retrieval is
needed, the Agent emits a bounded structured RAG Tool request. Trusted code
validates the request and authorization, invokes I&E, qualifies the result, and
atomically records the finalized Tool result, Working Set entries and owner
receipts at a Save Point. Vector similarity, lexical rank and graph proximity
explain why material was returned; they do not establish support, truth or
independent corroboration.

The Agent may locally refine, supersede or retire a subquestion, but cannot add
a new material user outcome, change Access Principal/Use Purpose, expand Case
scope, activate an unauthorized Tool or create a recursive task graph.

## 6. Stage E: Save Points, continuation and interruption

The main model may propose continue, pause or stop; Run Control decides.

Every admitted model/tool outcome and every accepted Work Plan change commits
through the existing Pi save-point mechanism before it can produce a public
progress event. Raw model deltas and uncommitted tool progress remain private.
The public stream may report only safe committed facts such as:

- which admitted goal is active or completed;
- which operation class completed or is blocked;
- current bounded coverage and budget status;
- the latest resumable Save Point reference; and
- whether the task is continuing, waiting, interrupted or settling.

`completed` requires:

- every admitted goal is structurally addressed;
- every reportable claim has at least one resolvable current citation;
- no pending Provider, Tool, reservation, save-point or unknown
  acknowledgement;
- required contradictions and limitations are represented;
- the current Case/Session/authorization basis remains valid; and
- the final save point and Run settlement commit exactly once.

Other terminal dispositions remain valid product outcomes:

- `insufficient_evidence`;
- `budget_exhausted`;
- `blocked`;
- `failed`;
- `cancelled`; or
- `discarded`.

For product presentation, these dispositions divide into:

- **completed outcome:** the admitted task goals are settled;
- **bounded incomplete outcome:** evidence, budget or an external blocker
  prevents further work;
- **interrupted outcome:** failure, cancellation or supersession stops the
  current Run before normal completion.

An interrupted outcome is not presented as if the task were successfully
finished. Workspace first commits or recovers the last valid Save Point and
settles the current Run without replaying uncertain work. It then produces an
Interruption Report containing completed work, uncompleted work, the blocker,
the last resumable basis and the safe next action. If no trustworthy Save Point
exists, the report says that explicitly and contains no reconstructed claims.

## 7. Stage F: Task Result and Evidence Assembly — unresolved

Run settlement does not by itself define the semantic result that a report
writer should receive. Before report composition, the design requires three
distinct products:

1. **Task Result:** one settled result per admitted objective, including its
   disposition, bounded claims, uncertainty, contradictions, unresolved gaps
   and next-step proposals;
2. **Claim-Evidence Subgraph:** exact Task Result statements, source assertions,
   qualified source material, candidate support/contradiction roles,
   reporting-prevalence, source-lineage, derivation and version relationships
   relevant to those results; and
3. **Report Evidence Packet:** a bounded report-consumer projection containing
   the Task Result, qualified subgraph, exact evidence excerpts/facts, citation
   aliases, coverage limits and report profile.

These are distinct contract products, not one schema. The first now has a
[Task Result v1 design candidate](task-result-v1-contract.md); its Design Gate
remains FAIL. The second now has an
[Evidence Assembly v1 design candidate](evidence-assembly-v1-contract.md);
its Design Gate also remains FAIL. The third now has a
[Report Evidence Packet v1 design candidate](report-evidence-packet-v1-contract.md);
its Design Gate remains FAIL. The fourth/public handoff now has a
[Task Outcome Report v1 design candidate](task-outcome-report-v1-contract.md);
its Design Gate remains FAIL. The previously named
`SettledInvestigationEvidencePacket` MUST NOT be treated as normative until
those assembly contracts are accepted.

The known ownership boundary is:

- I&E owns exact Resource Versions, Source Captures, Segments, derivative
  manifests, source assertions, source relationships, lineage facts, retrieval
  receipts/index observations and current qualification;
- OpenCTI supplies the observed source CTI objects and relationships; I&E owns
  their exact qualified, versioned retrieval projection;
- a vector/embedding index may find candidate Segments, but similarity is not
  evidence authority, corroboration weight or a claim-evidence relationship;
- Workspace owns task-scoped selection and assembly of the qualified
  Claim-Evidence Subgraph;
- Run Control owns the settled operational disposition, but does not invent
  evidence relationships; and
- the no-tool report Composer consumes only the sealed Report Evidence Packet
  and cannot query graph/vector stores, repair lineage or add material.

The evidence product should be understood as a task-scoped graph projection,
not necessarily one linear “chain.” RAG lookup occurs earlier through the
normal Tool lifecycle; Evidence Assembly performs no retrieval. The exact JSON
canonical shape, closed field vocabulary, numeric bounds and digest projection
remain open, while ownership, lifecycle, contradiction, prevalence,
independence and invalidation semantics are owned by the linked Evidence
Assembly contract.

Likewise, the Task Result and Task Outcome Report schemas remain open. At
minimum they must distinguish objective disposition, findings, evidence
references, analysis versus source assertion, uncertainty, contradictions,
coverage, unresolved work, Save Point/resume state and proposed next actions.

## 8. Stage G: Universal Task Outcome Report

Every accepted route produces a Task Outcome Report:

- clarification produces a Clarification Report;
- Quick Response produces a concise Answer Report;
- completed or bounded-incomplete Formal Investigation produces an
  Investigation Report;
- failed, cancelled or discarded work produces an Interruption Report from the
  last trusted Save Point; and
- unsupported work produces a Scope/Policy Report.

The report is broad product feedback, not necessarily a long document. It
states what was understood, what was done, the result, evidence/limitations,
current task status and any next step appropriate to that route.

Formal Investigation Report Composition is a separate bounded model call after
Run settlement. It is not another Agent Loop and has no Tools. Clarification,
unsupported and mechanically derived interruption fields do not require a
report-writing model. A Quick Response is itself its concise report.

The first model candidate is:

```text
logical profile: report_composer/deepseek-v1
provider model: deepseek-v4-pro
mode: non-thinking
output: closed JSON
```

After the Stage F assembly contract is accepted, the Composer receives one
bounded Report Evidence Packet. Its candidate contents are:

- Case identity and investigation mandate safe projection;
- Original User Task and admitted outcomes;
- final goal assessments;
- qualified findings and exact citation aliases;
- contradictions, omissions and uncertainty;
- budget/coverage limitations; and
- the required report profile.

It does not receive unrestricted Session history, hidden model reasoning,
credentials, rejected evidence or unqualified source bodies.

The report candidate contains:

- executive summary;
- scope and questions;
- findings as individually cited claims;
- evidence and analysis;
- contradictions and alternative explanations;
- confidence/limitations;
- unresolved gaps; and
- recommended next steps.

The report profile may omit inapplicable sections. Claim/citation structure is
closed before deterministic rendering. Empty, truncated, malformed or uncited
output is a failed candidate; it is not repaired by guessing.

### Private generation stream and public Outcome Stream

The report model may generate incrementally, but its provider deltas form a
private candidate stream. They are never forwarded directly to the user.

The order is:

```text
private report generation stream
  -> complete bounded candidate
  -> bind to settled Run and last valid Save Point
  -> deterministic validation
  -> narrow Evidence Audit when factual claims exist
  -> commit publication decision
  -> stream the admitted report to the user
  -> emit exactly one terminal outcome
```

This preserves streaming UX without allowing an unverified draft to become a
public answer. Public progress can arrive earlier, but it is derived only from
committed Save Points. The final report is streamed only after its complete
content has passed the applicable gates.

## 9. Stage H: Deterministic validation and narrow independent Evidence Audit

Both Report Candidates and Case Update Proposal Candidates use the same
grounded-claim validation pipeline.

### Deterministic validation

Code proves:

- every citation reference exists in the exact evidence packet;
- the referenced source/version was actually admitted and remains authorized;
- quoted spans, hashes, identifiers, dates and numeric literals match their
  source where mechanically checkable;
- no unknown, deleted, stale or fabricated citation identity appears;
- candidate structure, bounds, settlement and report profile match; and
- no secret or hidden identifier is disclosed.

This is the authority for source existence and identity. An LLM is not asked
whether a citation “looks real.”

### Narrow independent Evidence Audit

A fresh-context auditor receives only:

- the closed candidate;
- exact qualified evidence excerpts/facts keyed by citation reference; and
- a fixed review rubric.

It receives no Investigation Agent conversation, Composer conversation,
reasoning content, Workspace Memory, prior review or hidden state.

For each claim it returns one of:

```text
supported
unsupported
contradicted
citation_mismatch
overstated
not_verifiable
```

The auditor performs only audit reasoning: semantic entailment, contradiction,
overstatement, entity/time/source mismatch and omitted uncertainty. It does not
understand or route the user task, continue the investigation, use Tools,
consult Memory, compose or rewrite the report, add facts, create citations,
decide publication policy or approve a Case write.

The auditor does not create authority, but its result is fail-closed:

- every claim `supported` permits publication to continue;
- any other finding withholds the candidate;
- at most one separately budgeted recomposition may consume the exact findings
  and original evidence packet;
- a second failure stops with withheld/human-review-required; and
- high-impact Case changes require Case Management/human acceptance regardless
  of auditor result.

Using the same DeepSeek model family for Composer and Auditor is not considered
independent high-assurance review. The auditor model profile remains a product
selection gate.

Reports with no factual/evidentiary claim, such as a schema-derived
clarification or safe cancellation status, do not invoke the auditor merely to
repeat deterministic facts. Any report containing factual or analytical claims
must pass the audit.

## 10. Stage I: Publication stream and Case update

Publication remains:

```text
ReportCandidate
  -> deterministic proof
  -> EvidenceAudit
  -> WorkspacePublicationDecision
  -> committed publication record
  -> streamed TaskOutcomeReport | withheld report
```

No content-bearing report delta is public before the publication decision.
After the decision commits, the immutable admitted report may be rendered and
transported incrementally. Disconnect and resume use the committed output
identity and cursor; they never resume or splice the original Provider stream.

A Case update is a separate proposal derived from settled, validated evidence.
Report publication does not authorize it. Case Management independently
validates expected Case revision, authorization, operation intent and proposal
evidence before creating a new Case Revision.

The first version does not persist the report as a Workspace Artifact. Artifact
publication remains separately gated.

## 11. Frozen public acceptance candidates

The eventual public seam begins at the product task entry and ends in one
public route/result:

1. an ambiguous task asks clarification and creates no Case/Session;
2. a qualified simple task uses one intake call plus one quick-response call,
   no Harness and no Case creation;
3. a task requiring new evidence is classified as Formal Investigation by the
   intake model; an inconsistent Quick Response classification cannot pass the
   closed route-admission safety gate;
4. Formal Investigation creates/opens exactly one Case, Session and Workspace;
5. the Work Plan is derived from admitted goals/actions and ignores unadmitted
   model TODO mutations;
6. every Agent cycle performs action admission before Tool/provider start;
7. a RAG request uses the normal admitted Tool/result/Working Set Save Point
   path; the Agent never receives a graph/vector database Interface;
8. a model completion proposal cannot complete while goals/actions/citations
   are unresolved;
9. completed/insufficient/budget/blocked settle with exact distinct outcomes;
10. failure/cancellation/discard first settles or recovers the last valid Save
    Point, then emits an Interruption Report without replaying uncertain work;
11. every route produces one route-appropriate Task Outcome Report;
12. formal report composition uses the configured DeepSeek profile once and no
    Tools;
13. the report contains only claims/citations from the settled evidence packet;
14. fabricated citation identity fails deterministic validation before audit;
15. a semantically unsupported real citation is caught by the fresh-context
    auditor and withheld;
16. auditor approval cannot bypass deterministic failure or authorize Case
    mutation;
17. one failed audit permits at most one bounded recomposition; another failure
    stops;
18. public progress refers only to committed Save Points;
19. no private provider/report candidate delta leaks before publication commit;
20. an admitted immutable report is streamed with resumable output identity and
    never resumes the Provider stream;
21. report publication and Case update proposal have independent decisions;
22. existing Task Understanding, Run Control, Publication, Session, Provider
    Dispatch and root regressions remain green.

The matrix is review material until the Design Gate blockers close.

## 12. Design Gate

- **Verdict:** FAIL
- **Owner:** Agent Investigation Workspace orchestrates; Case Management,
  Session, evidence owners and Publication retain their authority
- **Interface:** product task entry to one routed public result
- **Input authority:** immutable user task plus trusted entry context
- **Output/evidence:** committed progress plus exactly one route-appropriate
  Task Outcome Report and independent Case-update proposal status
- **Failure closure:** specified at workflow level
- **Secret isolation:** no auditor/composer access to credentials, hidden
  identities or unrestricted history
- **Provider lifecycle count:** one bounded intake call, optionally one bounded
  Quick Response, formal Investigation calls, one report composition when
  needed, one narrow evidence audit when claims exist, and at most one report
  recomposition
- **Workspace exposure:** product stages and safe Work Plan/report status only
- **Backward compatibility:** current in-Workspace-only Task Understanding is a
  migration baseline, not the global-entry target
- **Public acceptance seam:** product task entry through final routed result
- **Remaining blockers:**
  1. Task Intake structured-output contract, route-admission hard rules,
     small-model profiles and Quick Response quality/cost thresholds are not
     frozen.
  2. Case Management's new-Case bootstrap/mandate Interface is not accepted.
  3. Task Result, Claim-Evidence Subgraph and Report Evidence Packet ownership
     and lifecycle are separated, but their closed schemas, numeric bounds,
     digest projections and assembly acceptance remain unfrozen;
     consequently DeepSeek report benchmarks, auditor qualification,
     human-review policy and the Publication streaming amendment cannot yet
     close.
