# CTI Agent End-to-End Validation Research

Date: 2026-07-26  
Status: **Research input; validation contract not yet accepted.**

## Current finding

The repository has local deterministic pieces around tool validation/events/errors, Harness save points and Run settlement, provider dispatch receipts, and Workspace task understanding/orientation. It does not yet close the CTI lifecycle:

```text
Task -> Run admission -> tools -> Session -> Memory recall/mutation
-> Case/I&E retrieval -> provider context -> output publication
-> later-run Memory recall
```

No current conclusion should therefore be treated as end-to-end evidence.

## Oracle hierarchy

LLM-as-judge is one layer, not the foundation:

1. **L0 structure/security**: scope, authorization, schema, provenance, version, digest, receipt, forbidden transition, and no leakage.
2. **L1 final state/side effects**: Session/CAS/settlement, tool effects, Case/I&E revisions, publication, Memory mutation and deletion.
3. **L2 trajectory/policy**: allowed tool selection, exact executed parameters, prerequisites, retries, budgets, and failure closure.
4. **L3 semantic judge**: completeness, evidence consistency, citations, uncertainty, and rubric quality.
5. **L4 CTI expert review**: high-impact publication, attribution disputes, novel attacks, judge disagreement, and consequential Memory/Case changes.

Any hard L0/L1 failure blocks release; a judge score cannot compensate for it.

## LLM-as-judge boundary

Use pointwise, reference-based, reference-free, pairwise, or multi-judge scoring only for semantic properties that deterministic oracles cannot decide. The judge has no tools or write authority, treats retrieved text as untrusted content, and cannot trigger publication, Case mutation, or Memory mutation.

For high-risk evaluation, fix model/prompt/temperature/schema, mask candidate identity, swap pairwise order, use multiple judges, calibrate against CTI expert labels, and escalate disagreement or low confidence. Track judge-human agreement; never use a single judge score as a security or state-correctness gate.

## Deterministic and trajectory checks

The harness must assert Principal, Purpose, Case, Session, Run, policy, model, tool, and dataset identities; actual executed tool arguments; authorization, idempotency, receipts; Session CAS and terminal settlement; Memory scope/source/version/deletion; I&E lineage and revocation; exact provider context; and the distinction between output candidate and published output.

The trajectory oracle must permit multiple legal paths while rejecting forbidden transitions, unauthorized calls, duplicate side effects, gate bypasses, untrusted tool-result instructions, and capability escalation.

High-priority current gap: a `beforeToolCall` hook may mutate parameters after initial validation. CTI side-effecting tools must freeze or revalidate final parameters after all hooks and bind those actual parameters to the execution receipt.

## Memory acceptance surface

Every Memory E2E scenario must cover extraction, admission, persistence, retrieval, qualification, consolidation, correction, invalidation, deletion, scope, source/version/time/confidence/auth, conflicts, and the binding between mutation and a successfully settled Run. Negative cases include failed/cancelled/discarded/uncertain Runs producing no durable Memory; cross-case or cross-purpose denial; corrected/revoked/expired/deleted records not being recalled; source drift invalidation without A-to-B-to-A revival; replay/crash/acknowledgement uncertainty/index lag/CAS conflict; prompt-injection isolation; and procedural-memory capability escalation denial.

## Trace, corpus, and release gates

Traces carry trace/span IDs, principal/purpose/case/session/run hashes, policy/model/tool/dataset versions, decisions and reasons, receipts, state leaves and resource versions, tokens/latency/retries/cost, mutation summaries, and terminal status. Protect raw sensitive payloads; prefer hashes and minimized evidence.

The corpus needs deterministic fixtures, scenario E2E cases, longitudinal Memory, adversarial, fault-injection, judge-calibration, production-replay, and secret-holdout sets. Each fixture records task/principal/purpose/case/session, initial Memory/Case/I&E state, tool policy, allowed/forbidden actions, milestones, expected state/output/evidence/mutations, failure closure, rubric, and provenance.

Release gates are `G0` contract, `G1` deterministic invariants, `G2` public seam, `G3` faults/concurrency, `G4` model/trajectory, `G5` security, `G6` judge calibration, `G7` shadow/canary, and `G8` release authority. `NOT_IMPLEMENTED` or `BLOCKED` cannot be hidden by weighted scoring or a claim that a capability is unnecessary.

The first runnable harness should use production-shaped controlled adapters for Run Control, Tools, durable Session, Memory, Case, I&E, Provider, publication, and mutation. Start with a deterministic closed loop, then add model/trajectory evaluation, then shadow/canary execution.
