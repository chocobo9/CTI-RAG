# CTI-RAG Agent Memory Requirements Audit

Status: primary-source audit and non-normative research input.

Research date: 2026-07-21.

Historical design disposition: **superseded**. The prior audit correctly
identified risks in duplicating Case, Session, Workspace and I&E authority, but
it incorrectly used that storage conclusion to reject a first-class Memory
Management Module. ADR 0021 now establishes Memory Management as a required
Agent capability. This note remains useful only as non-normative input about
provenance, authorization, correction, deletion and cross-scope risk.

This note does not define a Module, Artifact, Skill, database, schema, vector
index, automatic write path, multi-Agent behavior, or implementation Interface.
It does not change a normative contract.

## 1. Audit question

The question is not whether the system has durable state. It is whether CTI
investigation requires persistent, recallable knowledge whose business meaning
cannot be owned by any existing context:

- Case Management for the authoritative investigation record;
- Agent Investigation Workspace for task-scoped working state and versioned
  non-authoritative analytic outputs;
- Pi Session for navigable interaction history, compaction, and branching; or
- Intelligence and Evidence for reusable source material, versions,
  provenance, derivation, and retrieval.

The context map currently defines only these three CTI bounded contexts and
their relationships. It does not define Memory as a fourth context.
[`CONTEXT-MAP.md`](../CONTEXT-MAP.md)

## 2. Evidence classes

This audit keeps four classes separate.

### 2.1 Current documented design

These facts are already owned by current documents:

1. A `Case` is long-lived across user tasks and Agent Runs. `Case State` is the
   authoritative investigation state and explicitly excludes Agent memory and
   transcripts. [`case-management/CONTEXT.md`](../case-management/CONTEXT.md)
2. A `Session` is navigable interaction history, not the Case. A `Workspace` is
   task-scoped; its state includes the task, Case-context receipt, Working Set,
   Session, Artifacts, and synchronization state.
   [`agent-workspace/CONTEXT.md`](../agent-workspace/CONTEXT.md)
3. A `Workspace Artifact` is persistent, versioned, and non-authoritative. Model
   output does not become an Artifact by default, and a Published Workspace
   Output remains non-authoritative.
   [`agent-workspace/CONTEXT.md`](../agent-workspace/CONTEXT.md)
4. I&E owns globally reusable source material, exact Resource Versions,
   Source Captures, derivatives, provenance, lineage, retrieval receipts, and
   actor/purpose-authorized Resource Capsules. It does not own Case evidentiary
   roles or Workspace Working Set selection.
   [`intelligence-evidence/CONTEXT.md`](../intelligence-evidence/CONTEXT.md),
   [`intelligence-evidence-platform-design.md`](../intelligence-evidence/intelligence-evidence-platform-design.md)
5. Workspace State is a composition, not a single persisted object or a fourth
   authority. Model Context is only a rendering. Interaction history belongs to
   Session; task direction and derived analytic state belong to Workspace
   task/Artifact state; Case authority belongs to Case Management; reusable
   source/corpus state belongs to I&E.
   [`context-projection-design.md` section 5.0](../agent-workspace/context-projection-design.md#50-workspace-state-composition)
6. Resume reconstructs current context from durable task/Artifact records,
   Session receipts, a newly authorized Case view, and versioned I&E references.
   It must not restore an old rendered context as authority.
   [`context-projection-design.md` section 5.0](../agent-workspace/context-projection-design.md#50-workspace-state-composition)
7. Compaction summarizes task work, decisions, resource references, tool
   outcomes, pending proposals, and unresolved work. It must not turn a Case
   Projection into permanent memory. Branch navigation rewinds Session work,
   not the Case.
   [`context-projection-design.md` section 11](../agent-workspace/context-projection-design.md#11-session-compaction-and-branching)
8. Small v1 Working Set state is committed only through the owning Pi Session
   save point. It is neutral selected source material, not Evidence, accepted
   fact, Candidate Finding, Case membership, or a copied OpenCTI object.
   [`intelligence-working-set-v1-contract.md` sections 3-4](../agent-workspace/intelligence-working-set-v1-contract.md#3-closed-v1-working-set-records)
9. Current implementation does not yet provide the Pi-native Workspace,
   Task Understanding execution, I&E consumer, Working Set, Assessment, or
   complete Provider Dispatch vertical. Design acceptance must not be read as
   implemented Memory behavior.
   [`agent-workspace/PROGRESS.md`](../agent-workspace/PROGRESS.md),
   [`intelligence-evidence/PROGRESS.md`](../intelligence-evidence/PROGRESS.md)

### 2.2 CTI business deductions

The following conclusions are deductions from the owner model, not accepted
product decisions:

- Same-Case continuity is primarily an authority and re-projection problem, not
  a generic memory problem.
- Historical analysis can remain useful without becoming Case truth, but it
  must retain its task, actor, purpose, Case basis, Resource versions,
  assumptions, contradictions, and validity limits.
- Cross-Case reuse of source content belongs to I&E; cross-Case reuse of an
  analyst's reasoning experience does not automatically belong to I&E.
- A missing search/discovery experience over existing Session or Workspace
  records is not by itself proof of a new owner. It may be a retrieval or
  presentation capability of the owner that already governs those records.
- Cross-task continuity is not automatically cross-Case recall. Tasks may share
  one Case authority while still requiring fresh task admission and current
  authorization.

### 2.3 Research recommendations

Recommendations in this note are conditional and non-normative:

- Keep independent Memory NO-GO until one residual cross-Case or cross-Workspace
  business scenario survives the owner test in section 8.
- For same-Case continuity, first evaluate owner-local discovery and selection
  over authorized Case state, Workspace Artifacts, and Session history rather
  than creating a duplicate store.
- Treat a model-produced retention suggestion as an untrusted candidate only.
  No candidate is recallable until an authorized deterministic or human
  admission decision exists.
- Evaluate recall against a no-recall baseline for task quality, stale-result
  rate, authorization leakage, correction/deletion completeness, latency, and
  abstention. Anecdotal convenience is not sufficient.

### 2.4 Undecided product choices

The current product has not decided:

- whether analyst or Agent experience must follow an actor across Cases;
- whether team working conventions are product policy, user preference, or
  governed analytic experience;
- whether private Workspace analysis may be discovered from another Workspace;
- whether any cross-user derived analysis state should exist before Case
  acceptance;
- who may admit, correct, withdraw, delete, or recall residual experience;
- numeric validity, retention, or deletion-completion requirements; or
- what measured improvement would justify the governance and disclosure risk.

## 3. Direct answers to the research questions

### 3.1 Is there persistent CTI knowledge outside Case, Session, Workspace Artifact, and I&E Resource?

**For the current documented workflow: no required class has been proven.**

Every currently defined persistent meaning routes to an existing owner:

| Persistent meaning | Current owner |
|---|---|
| accepted facts, corrections, findings, directions, decisions, and Case history | Case Management |
| interaction history, tool results, branches, compaction, and execution receipts | Pi Session |
| task interpretation, Working Set state, drafts, Units, provisional task outputs, and derivation edges | Agent Investigation Workspace |
| reusable sources, versions, captures, derivatives, provenance, lineage, and retrieval evidence | I&E |

One **conditional residual class** remains: source-bound, non-authoritative
experience about how an investigation was performed and what outcome followed,
intended for reuse outside the originating Case/Workspace. Examples are a
previously unsuccessful collection path under stated preconditions, a
reproducible analytic technique outcome, or an organizational convention whose
scope crosses Cases. It is not current Case truth, not mere transcript history,
not a task-local Artifact when recalled elsewhere, and not an Intelligence
Resource merely because it cites one.

This residual class is not yet a product requirement. Current documents defer
shared-analysis discovery and cross-user context injection, and no accepted
workflow requires cross-Case experience recall.
[`context-projection-design.md` sections 2 and 5.2](../agent-workspace/context-projection-design.md#2-non-goals)

### 3.2 How much same-Case cross-task continuity is covered?

It is covered in layers:

1. **Case continuity:** stable Case identity, accepted state, corrections,
   history, and revisioned current authority survive tasks and Agent Runs.
2. **Workspace continuity:** a task may span multiple Agent Runs; its admitted
   task state, Working Set references, Artifacts, receipts, and synchronization
   state are durable or reconstructable according to their owners.
3. **Session continuity:** conversation, tool outcomes, branch, and compaction
   preserve one navigable work history, subject to current eligibility and
   authorization checks.
4. **Fresh re-entry:** resume reopens current Case authority and revalidates I&E
   references instead of replaying old rendered context as truth.

The uncovered part is **automatic discovery of relevant private analysis from a
different Workspace or unrelated Session**. That is currently deferred product
scope. Within the same Case it could be resolved in at least two owner-preserving
ways before considering Memory:

- promote validated Case-relevant analysis through the existing controlled Case
  acceptance path; or
- keep it non-authoritative and expose authorized Workspace-owned Artifact
  discovery/selection without changing its owner.

Therefore the older claim that same-Case cross-task continuity alone proves a
new Memory owner is too strong. It proves a possible discovery requirement, not
an ownership gap.

### 3.3 Which historical experience needs cross-Case or cross-Workspace recall?

No such recall is currently accepted as required. The only plausible candidates
that merit product validation are:

- a method whose result is reproducible under declared inputs and method
  version;
- a failed or misleading investigative path with explicit preconditions,
  observed outcome, and later explanation;
- an assumption or heuristic with known support, counterexamples, and expiry
  conditions;
- an analyst-approved working convention that genuinely applies beyond one
  Case; and
- a handoff lesson whose authorized audience spans otherwise separate
  Workspaces.

The following do not justify residual memory:

- source facts or reusable derived intelligence: I&E. The current I&E glossary
  explicitly permits a provenance-bearing `analysis result` to be an
  Intelligence Resource, so Agent participation alone does not exclude I&E;
- accepted Case judgments or corrections: Case Management;
- unresolved Case hypotheses intended to continue within the Case: Workspace
  Artifact or controlled Case candidate/provisional state;
- raw conversation or tool history: Session;
- model hidden reasoning, chain of thought, or unsupported summaries: never a
  recall authority;
- generic product instructions or organization policy: configuration/policy
  ownership must be decided separately, not disguised as analytic memory.

### 3.4 What kind of content is it?

The type determines the owner and recall authority:

| Content kind | Treatment |
|---|---|
| formal fact or accepted judgment | Case Management when Case-specific; I&E only when it is reusable source/derived intelligence under I&E provenance rules |
| historical event | Session for interaction history; Workspace operation/Artifact history for task derivation; Case history for authoritative business events |
| analytic hypothesis or judgment | Workspace Artifact while private/non-authoritative; Case candidate/provisional/accepted state only through controlled acceptance |
| reproducible experience | conditional residual candidate only when intended for authorized reuse beyond the originating owner scope |
| user or team preference | undecided product policy; never silently inferred from model behavior or promoted to CTI fact |

Official intelligence analytic standards reinforce this separation: source
information, assumptions, judgments, uncertainty, and indicators that would
change a judgment should be explicit rather than collapsed into one remembered
statement. [ODNI ICD 203](https://www.dni.gov/files/documents/ICD/ICD-203.pdf)

### 3.5 Who may write, correct, withdraw, delete, and recall it?

For current content, the existing owner governs those actions. A model has no
independent authority:

| Content | Write/admit authority | Correction/withdrawal/deletion | Recall eligibility |
|---|---|---|---|
| Case State | Case Management under its controlled proposal/approval rules | Case Management and authorized human/business process | current actor/purpose-specific Case view |
| Session history | Pi lifecycle plus owning application policy at save points | Session retention and authorization policy; not textual rewriting into Case truth | current eligible branch/history policy |
| Workspace state/Artifact | trusted Workspace admission and publication/Artifact rules | Workspace version/status/retention rules; accepted Case effects remain separate | same authorized Workspace/task scope unless a future sharing decision says otherwise |
| I&E material | I&E deterministic admission and source policy | I&E status, withdrawal, purge, retention, and source-version rules | current actor/purpose/use decision |
| conditional residual experience | **no current authority** | **no current authority** | **not recallable** |

Research recommendation if the residual requirement is later accepted: the
model may propose a candidate; an authorized human or deterministic policy under
an explicitly named business owner must admit it. Source owners can invalidate
dependent eligibility but do not thereby rewrite the experience. The owning
governance authority must control correction, withdrawal, deletion, and recall
scope. Until that authority exists, write and recall must fail closed.

### 3.6 How should Task, Workspace, Case, actor, purpose, versions, and expiry bind?

Current contracts already demonstrate the necessary principle: identity and
eligibility are bound to exact owner-issued references, versions/digests,
actor/purpose, authorization, Context Generations, and current-use decisions;
equal text does not revive an earlier authorization generation.
[`pi-native-workspace-lifecycle-v1-contract.md` sections 7-8](../agent-workspace/pi-native-workspace-lifecycle-v1-contract.md#7-session-eligibility-receipt-trust-and-the-stale-marker-replacement),
[`intelligence-working-set-v1-contract.md` sections 2-5](../agent-workspace/intelligence-working-set-v1-contract.md#2-target-neutral-planning-and-resource-selection)

For the conditional residual requirement, the business qualification would need
to prove, before any storage design is discussed:

- exact origin Task, Workspace, Session/Run, Case, and actor/purpose scope;
- the Case Revision or Orientation/context-generation basis actually used;
- exact Resource Versions, Source Captures, Artifacts, and method/policy versions;
- who admitted the experience and for which audience/tenant;
- whether it records observation, assumption, judgment, preference, or outcome;
- valid-from, review-by/expiry, withdrawal, and retention conditions; and
- which dependency changes make it ineligible, challenged, historical-only, or
  deleted.

This is a requirements checklist, not a proposed schema.

### 3.7 How are hallucination, staleness, overreach, and bad personalization kept out?

The current owner rules provide the baseline:

1. Model output is non-authoritative and cannot directly mutate Case State,
   activate capabilities, create I&E authority, or become durable current state
   from a stream fragment.
2. Only complete, validated outputs at owner-controlled save/publication points
   become durable.
3. Every current use rechecks actor, purpose, authorization, status, version,
   Context Generation, and relevant dependency validity.
4. Source facts, assumptions, analytic judgments, historical interaction, and
   user preferences remain visibly distinct.
5. Withdrawal, revocation, new source versions, Case changes, and authorization
   changes challenge or deny dependent use; equal content does not revive old
   eligibility.
6. Recall must be permitted to abstain. Similarity alone cannot establish scope,
   authority, currency, or applicability.
7. Recalled advisory material cannot directly change Case State, I&E Use
   Disposition, capability activation, authorization, Working Set state, or an
   external effect.
8. Deletion is incomplete until source body, derived summaries, search indexes,
   caches, and other recall paths are no longer eligible, subject to explicit
   legal-hold/audit rules.
9. Pre-deployment and ongoing evaluation must compare against a no-recall
   baseline and measure both task value and negative outcomes.

NIST identifies confabulation, information integrity, information security, and
data privacy as relevant generative-AI risks, recommends provenance tracking,
source/citation verification, grounded retrieval data, consent withdrawal, and
empirical evaluation. [NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)

STIX 2.1 shows the CTI-side discipline: creator, version, revocation, confidence,
external references, and object/granular markings are distinct properties;
revocation is not an informal last-write-wins update. This does not define Agent
Memory, but it rejects source-less and marking-less recall as a CTI default.
[OASIS STIX 2.1 Errata 01](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html)

### 3.8 What is the minimum boundary if an independent capability is needed?

Only the residual concern may justify a new owner:

> Govern admission, correction, withdrawal, deletion, qualification, and
> actor/purpose-scoped recall of non-authoritative analytic experience whose
> intended reuse crosses the originating Case/Workspace scope and which is not
> reusable I&E source/derivative material.

Its minimum negative boundary would be:

- not Session history, compaction, or Harness recovery;
- not Workspace task state, Working Set, or an originating Artifact store;
- not Case fact, accepted judgment, correction, direction, or proposal receipt;
- not I&E source, Resource Version, derivative, provenance, lineage, or
  retrieval authority;
- not product policy, capability activation, tool authorization, or execution;
- not a path for model output to become authority; and
- not automatic cross-user or cross-Case visibility.

This describes an owner test, not a Module Interface. A future Module would be
justified only if deleting it would force these governance rules into several
existing owners and callers. If the capability is only a pass-through search
over Workspace Artifacts, it belongs behind the Workspace owner instead of
creating a shallow Memory Module.

### 3.9 If no independent capability is needed, how do current owners cover it?

Use the current allocation explicitly:

- **same interaction thread:** Pi Session;
- **same task across model/tool turns and Agent Runs:** Workspace plus Session;
- **same Case across tasks:** current Case re-projection, plus only the
  Workspace Artifacts/Session history that their existing owner makes eligible
  for the new task; cross-Workspace discovery is otherwise unsupported;
- **accepted cross-task Case knowledge:** Case Management;
- **reusable cross-Case intelligence:** I&E;
- **private hypotheses and analysis:** versioned Workspace Artifacts until a
  controlled Case proposal changes their authority;
- **old rendered context:** reconstruct, do not restore as truth;
- **cross-Case analytic experience or preferences:** unsupported unless a later
  product decision establishes an owner and governance contract.

This is the recommended current disposition.

## 4. Autonomous design grill

The user delegated product questioning to this audit. The questions and answers
below stress-test the recommendation.

| Grill question | Answer | Consequence |
|---|---|---|
| Are we merely renaming durable state as Memory? | No. Existing owner terms remain canonical. | No umbrella Memory concept. |
| Does persistence alone justify a Module? | No. The owner and business semantics matter. | No new Module for storage convenience. |
| Does same-Case cross-task continuity prove a gap? | No. Case authority, Workspace Artifacts, and Session already carry most continuity; discovery may be owner-local. | Test owner-local discovery first. |
| Does a new Workspace need every prior private analysis? | No. That would create anchoring, authorization, and relevance hazards. | Selection must be explicit and current-purpose-bound. |
| Can a model decide what becomes long-lived? | No. It may only propose a candidate. | Admission requires trusted authority. |
| Can model experience be an I&E Resource? | Not merely because it cites sources. I&E derivatives must retain I&E-defined reproducibility and provenance; an Agent's task outcome is a different meaning. | Do not disguise experience as intelligence. |
| Can a model summary become Case continuity? | Not without Case Management acceptance. | Case remains authoritative. |
| Is cross-Case similarity enough to recall? | No. Scope, authorization, version, validity, and purpose qualify before relevance. | Vector similarity cannot be the eligibility decision. |
| Should a failed path be remembered forever? | No. Its preconditions and validity can expire or be contradicted. | Historical-only or ineligible outcomes must exist conceptually before implementation. |
| Are user preferences harmless? | No. They can reveal identity, cause bad personalization, or conflict with team policy and current purpose. | Preference ownership remains a separate product decision. |
| Can deletion mean hiding one record? | No. Recall paths and derivatives must also cease eligibility, subject to explicit audit/legal rules. | Deletion semantics precede storage selection. |
| Could Workspace own the residual capability? | Same-Case/same-actor Artifact discovery probably can. Cross-Case organizational experience may exceed task-scoped Workspace ownership. | Split the scenarios; do not choose a new owner prematurely. |
| Could Case own it? | Only if the knowledge is about that Case and accepted under Case rules. Cross-Case advice would pollute Case authority. | No generic experience in Case State. |
| Could I&E own it? | Only when it is genuinely reusable source/derived intelligence under I&E provenance and reproducibility rules. Analysis practice is not automatically an Intelligence Resource. | No experience laundering through I&E. |
| Is an independent owner now justified? | No accepted workflow, audience, authority, or evaluation target exists. | Current decision is NO-GO. |

## 5. Owner test and reopen conditions

Reopen independent ownership only when all of these are true:

1. A named CTI workflow requires recall beyond the originating Case/Workspace,
   and current owner-local discovery cannot satisfy it.
2. The recalled item is neither Case authority nor I&E source/derivative
   material nor Session/Workspace history in disguise.
3. The workflow identifies who may admit, correct, withdraw, delete, and recall
   the item.
4. Actor, tenant, purpose, Case/Workspace/Task origin, version basis, validity,
   authorization, retention, and deletion obligations are decidable before
   relevance ranking.
5. Model-generated candidates cannot enter the recallable set without trusted
   admission.
6. A no-recall baseline and failure-oriented evaluation show material benefit
   without unacceptable stale, false, or unauthorized recall.
7. The deletion test for a deep Module passes: removing the candidate owner
   would redistribute substantial governance behavior across multiple existing
   owners, not merely remove one search wrapper.

If any condition is absent, keep the requirement with the existing owner or
leave cross-context recall unsupported.

## 6. Relationship to earlier memory research

The two earlier notes correctly established that persistent state is already
split among Session, Workspace, Case, and I&E, and that automatic source-less
memory would be unsafe:

- [`agent-memory-need-2026-07-21.md`](agent-memory-need-2026-07-21.md)
- [`agent-memory-need-assessment-2026-07-21.md`](agent-memory-need-assessment-2026-07-21.md)

This audit narrows one earlier recommendation. Same-Case cross-task analysis
continuity does not by itself prove an independent owner; it first routes to
Case re-projection, Workspace Artifact selection, and Session eligibility. It
also narrows the statement that Agent experience cannot be I&E: a reproducible,
provenance-bearing analysis result can already fit I&E, while a task episode or
working preference cannot be relabeled as an Intelligence Resource merely to
gain cross-Case recall. The independent-owner candidate is therefore limited to
explicitly required cross-Case or otherwise cross-owner non-authoritative
experience that fails both the Workspace and I&E owner tests. Because that
product choice is not accepted, the current disposition remains no independent
Memory capability.

## 7. Final decision matrix

| Question | Audit decision |
|---|---|
| Is there currently an orphaned required persistent knowledge class? | No. |
| Is same-Case continuity covered? | Yes for authority, task state, interaction history, and reusable resources; cross-Workspace private-analysis discovery is deferred. |
| Is cross-Case experience recall required? | Not established. |
| Who may write residual experience today? | Nobody; no owner or contract exists. |
| May model output become Case authority or long-term recall automatically? | No. |
| May Agent experience be represented as an I&E Resource by default? | No. |
| Should an independent Memory Module be designed now? | No-GO. |
| What would reopen the decision? | A concrete cross-Case/cross-owner workflow that passes all owner, authorization, validity, deletion, and evaluation gates in section 5. |
