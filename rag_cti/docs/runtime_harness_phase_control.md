# Runtime Harness Phase Control

This is the control document for long-running Codex work on the CTI-RAG runtime
harness. It is the first file an agent should read before continuing runtime
harness phases, choosing the next task, or declaring a phase complete.

This is not a glossary and not an ADR. It is an operational progress ledger:
architecture boundaries, phase status, open work, acceptance criteria, and
verification evidence live here.

## Document Authority

Use documents in this order when they disagree:

1. This file: current runtime harness phase progress, open issues, acceptance
   criteria, and verification evidence.
2. `docs/adr/0001-runtime-harness-orchestration.md`: accepted runtime harness
   orchestration boundaries.
3. Current code and tests: implementation truth for what actually exists.
4. Temporary handoff files: useful context only, never authoritative after this
   control document exists.
5. `docs/agentic_rag_guardrails.md`: historical/north-star guardrail framing
   only. Do not use it as the current phase status, implementation map, or
   completion checklist for Phase 4.

`docs/CONTEXT.md` remains glossary-only. Do not put phase progress, checklists,
or implementation decisions there.

## How Codex Should Use This Document

1. Read this document before starting runtime harness work.
2. Pick the first issue with `Status: Ready`.
3. Use TDD for implementation: write or tighten the boundary test first.
4. Update the issue status, verification evidence, and residual risks before
   ending the session.
5. If implementation contradicts an invariant here, stop coding and resolve the
   design with a grilling/design pass first.
6. If context is getting full, produce a handoff that references this document
   and the exact issue id.

## North Star

CTI-RAG is moving toward agentic RAG investigation with one runtime-owned
production investigation loop.

The desired production shape is:

```text
agent proposes next action
runtime validates action
runtime executes tools through a tool boundary
runtime records observation/event/state update
runtime applies stop policy
runtime synthesizes from structured evidence
```

The model may propose an action. Runtime decides whether and how it executes.
Tool results become structured runtime observations. `ToolMessage` and provider
message objects are protocol artifacts, not the source of runtime truth.

## Architecture Invariants

- Production/public single-agent investigation loop is owned by
  `src/rag_cti/runtime_harness.py`.
- `src/rag_cti/knowledge/agentic_graph.py` is legacy/debug/baseline wiring, not
  production single-agent loop ownership.
- Query understanding and supervisor admission are runtime boundary concerns.
- Supervisor/coordinator is a run-level boundary, not the owner of ordinary
  single-agent investigation reasoning.
- Tool execution crosses a runtime/tool executor boundary.
- Tool/provider/no-action/deadline outcomes produce `RuntimeObservation` and
  derived `RuntimeEvent`.
- `ToolMessage.content` may carry runtime-rendered observation text back to the
  provider protocol, but it is not the factual source.
- Agent stop suggestions are advisory; runtime stop policy decides.
- Legacy ledger mutation may remain temporarily only when surfaced through
  observation/state accounting and called out as partial.

## Current Phase Status

| Phase | Name | Status | Current truth |
|---|---|---|---|
| 1 | Loop ownership cleanup | Done | Public single-agent paths call `run_agentic_investigation()` rather than legacy graph ownership. |
| 2 | Runtime boundary hardening | Done | Runtime validates tool calls, records boundary events, and handles provider/tool rejection/error accounting. |
| 3 | State / observation normalization | Partial | Compatibility layer is done: boundary outcomes are normalized into `RuntimeObservation` / `RuntimeEvent`; deadline-skipped tool calls, parallel observation ids, and setup-progress stop-policy accounting are covered. Reducer-owned ledger mutation and replayable state transitions are still open. |
| 4 | Agent next-action contract | Done | `RuntimeTurnAdapter.run_turn()` now owns the model turn, extracts provider tool calls into a `RuntimeActionProposal` batch, executes that batch, and renders provider protocol messages from observations. |
| 5 | Supervisor boundary correction | Done | Production `answer()` admits supervisor only through validated runtime branch plans; validated plans skip autonomous supervisor routing; `branch_plan=None` autonomous supervisor remains explicitly marked debug/eval/manual compatibility. |

## Next Session Handoff

Purpose: continue from this document after clearing context. Do not create a
separate handoff document unless the user explicitly asks for one.

Next-session focus:

1. Continue Phase 3 reducer/state ownership work, starting with `P3-2`.
2. Keep Phase 5 as closed unless new production supervisor routing evidence appears.
3. Keep all progress, status changes, verification evidence, and residual risks
   in this file.

Suggested skills:

- `$tdd` for each implementation issue.
- `$diagnose` if a runtime behavior or test failure does not match the intended
  boundary.
- `$grill-with-docs` only if Phase 5 boundaries prove ambiguous enough to need
  design clarification before code.

Current worktree caveats:

- `docs/codebase_consolidation_debt.md` is deleted in the worktree and is
  unrelated to the runtime harness handoff. Do not restore or remove it unless
  the user explicitly asks.
- `docs/runtime_harness_phase_control.md` is the active progress/control file.
  It may be untracked if not yet staged by the user.

Recommended next command sequence:

```powershell
git status --short
Get-Content -LiteralPath docs\runtime_harness_phase_control.md
python -m pytest tests\unit\test_runtime_harness.py -q -o addopts=""
```

Then implement `P3-2` with TDD.

## Phase 3 Control Addendum

Current Phase 3 truth:

- `RuntimeObservation`, `RuntimeEvent`, and runtime turn observation/event
  accounting exist.
- `apply_observation_to_state(...)` appends observations/events to runtime
  state, but it does not apply observations to `EvidenceLedger`.
- Tool execution still mutates `EvidenceLedger` through legacy
  `agent_tools.*_to_ledger(...)` helpers and `ledger.add_action(...)`.
- `ledger_delta` is inferred from before/after snapshots around legacy side
  effects; it is not produced by a reducer.
- Real-LLM validation exposed a stop-policy risk: successful setup actions such
  as `resolve_entity` can produce `tool_result` observations without new
  evidence, causing `no_progress` to stop the investigation too early.

Completion wording:

- Phase 3 compatibility layer: Done.
- Phase 3 reducer/state ownership: Not done.
- Phase 3 should not be declared fully complete until observations can drive
  ledger/state updates through a runtime reducer, or the remaining work is
  explicitly moved to a later named phase.

## Phase 3 Carry-Forward Issues

### P3-1: Preserve setup progress in runtime stop policy

Status: Done

Blocked by: None - can start immediately

Goal: Prevent the runtime loop from treating successful setup-only actions as
global `no_progress`.

User story covered: A real LLM may first resolve entities, inspect outlines, or
perform other setup actions before retrieving evidence; successful setup should
allow the investigation to continue when budget/deadline permits.

Acceptance:

- Successful setup observations such as entity resolution are counted as
  progress distinct from evidence/fact growth.
- `no_progress` does not fire immediately after a turn with successful setup
  observations and zero new evidence.
- True no-action, rejected-only, invalid-only, provider-error, and exhausted
  turns can still stop through runtime stop policy.
- A real or integration-style test covers the previously observed
  `resolve_entity`-only first turn.

Verification:

- Focused runtime stop-policy tests pass.
- Real-LLM or recorded-tool-call validation no longer stops the APT29/Lazarus
  comparison query at the entity-resolution turn with `stop_reason="no_progress"`.

2026-06-24 evidence:

- Added `setup_progress` as a stop-policy signal distinct from `new_evidence`.
- Runtime counts successful setup-only observations from `resolve_entity` and
  `graph_outline` when they are non-duplicate successful tool results without
  chunk/fact growth.
- Added regression coverage for a `resolve_entity`-only first turn; the runtime
  now continues to a second turn rather than stopping immediately with
  `no_progress`.
- `python -m pytest tests\unit\test_agentic_nodes.py::test_decide_next_setup_progress_continues_without_evidence -q -o addopts=""`
  passed.
- `python -m pytest tests\unit\test_runtime_harness.py::test_runtime_loop_continues_after_resolve_entity_setup_only_turn -q -o addopts=""`
  passed.

2026-06-24 diagnostic downgrade:

- Live E2E validation still fails after two successful setup-only turns:
  `tool_call_count=4`, `n_chunks=0`, `n_facts=0`,
  `stop_reason="no_progress"`.
- Recorded reproduction shows first-turn `resolve_entity` results are not
  persisted into the next turn's model-visible state; the next turn sees the
  action log but not the resolved ids needed to call `graph_outline`.
- Existing tests prove one-turn stop-policy deferral, but not cross-turn setup
  result visibility through the real `RuntimeTurnAdapter.run_turn()` prompt/state
  rebuild path.

2026-06-24 repair evidence:

- Runtime now carries resolved entity setup state in
  `RuntimeInvestigationState.observations`; this is runtime observation state,
  not `EvidenceLedger` facts/chunks and not citable evidence.
- The next `RuntimeTurnAdapter.run_turn()` rebuild renders prior non-empty
  `resolve_entity` observations as resolved ids for `graph_outline` /
  `graph_query`, preventing duplicate resolve loops.
- Empty `resolve_entity` results no longer count as setup progress.
- `tests/unit/test_runtime_harness.py::test_runtime_turn_exposes_resolved_entity_ids_to_next_real_turn`
  passed through the real `RuntimeTurnAdapter.run_turn()` prompt/state rebuild path.
- `tests/unit/test_runtime_harness.py::test_runtime_loop_does_not_count_empty_resolve_as_setup_progress`
  passed.
- Live E2E validation passed:
  `python -m pytest --no-cov -q tests/integration/test_agentic_answer.py`.

### P3-2: Introduce one reducer-owned ledger update tracer bullet

Status: Ready

Blocked by: P3-1

Goal: Migrate one narrow tool path from legacy ledger side effect to
observation-driven ledger update without changing the whole tool system.

User story covered: Runtime can replay at least one action result from a
`RuntimeObservation` into `EvidenceLedger`, proving the reducer boundary before
larger migration.

Acceptance:

- One selected tool path returns structured data that can be represented in a
  `RuntimeObservation` without directly mutating `EvidenceLedger`.
- A runtime reducer applies that observation to `EvidenceLedger`.
- The reducer returns or records the resulting ledger delta.
- Existing public answer shape and citation guard behavior remain compatible.
- Legacy side-effecting tool paths remain explicitly classified as
  compatibility paths.

Verification:

- A unit test proves observation replay reconstructs the expected ledger change
  for the migrated path.
- Existing runtime harness focused tests pass.

### P3-3: Make ledger deltas atomic for parallel proposal execution

Status: Blocked

Blocked by: P3-2

Goal: Ensure each observation's ledger delta belongs only to that observation,
even when runtime executes proposals in parallel.

User story covered: Trajectory eval can trust per-action deltas when the model
proposes multiple actions in one turn.

Acceptance:

- Per-observation delta is produced by the reducer or another atomic update
  boundary, not by shared before/after snapshots around parallel side effects.
- Parallel proposal execution preserves unique action ids, observation ids, and
  uncontaminated per-action deltas.
- Tests cover at least two parallel successful actions with distinct deltas.

Verification:

- Parallel runtime harness regression tests pass.
- No test relies on cross-action snapshot leakage.

### P3-4: Add replay-oriented trajectory test

Status: Blocked

Blocked by: P3-2

Goal: Prove that stored runtime observations can reconstruct the relevant
runtime state for at least one completed investigation slice.

User story covered: Future evaluation and debugging can inspect or replay the
investigation trajectory without depending on hidden tool side effects.

Acceptance:

- A test records a minimal proposal/observation sequence.
- Replaying the observations through the reducer reconstructs expected ledger
  facts/chunks/actions for the migrated slice.
- Provider `ToolMessage` content is not used as the source of truth.

Verification:

- Replay test passes alongside runtime harness focused tests.

## Phase 5 Starting Point

Phase 5 target: supervisor/coordinator is limited to run-level coordination.
It should not own ordinary investigation reasoning, directly gather evidence, or
blur debug/baseline surfaces with production runtime behavior.

Current known facts:

- Production `answer()` owns supervisor admission through runtime query
  understanding and `evaluate_supervisor_admission(...)`.
- Validated branch plans skip the supervisor routing loop and dispatch branch
  workers directly.
- `run_agentic_gather_investigation(...)` is the runtime-owned worker gather
  path used by branch workers.
- Forced/debug supervisor surfaces still exist and still use shared ReAct
  dispatch compatibility, but `branch_plan=None` is explicitly traced as
  `legacy_autonomous_debug_eval`.
- Supervisor branch ledger merge still mutates ledgers through
  `merge_branch_ledgers(...)`, which is not reducer-owned.

### P5-1: Re-audit production vs debug supervisor entry points

Status: Done

Goal: Make the current supervisor boundary explicit and test-proven before
changing behavior.

Acceptance:

- Public `answer()` path remains the production entry point.
- Forced `supervised_answer(...)` remains classified as debug/baseline.
- Validated branch plan path does not invoke the supervisor routing loop.
- Simple/fallback/dependent tasks remain on the single-agent runtime path.
- Tests fail if production simple/single-agent tasks enter supervisor routing.

Verification:

- `python -m pytest tests\unit\test_runtime_harness.py tests\unit\test_supervisor_graph.py -q -o addopts=""`
- `rg -n "supervised_answer|run_supervised_answer|run_supervisor_loop|evaluate_supervisor_admission|validated branch" src\rag_cti tests\unit`

2026-06-24 evidence:

- Added production-entry regression coverage proving `answer()` with validated
  branch plan does not call `run_supervisor_loop()`.
- Existing and retained tests prove supervisor-disabled and simple/fallback paths
  remain on single-agent runtime path.
- Validated branch plan path passes branch plan into `run_supervised_answer(...)`.

### P5-2: Classify and narrow supervisor responsibilities

Status: Done

Goal: Keep supervisor logic as coordination only: accept validated branch plans,
dispatch gather-only workers, monitor reports, and trigger Composer.

Acceptance:

- Supervisor does not directly retrieve, rewrite, or synthesize final answers.
- Composer remains the sole synthesis role on supervised answers.
- Worker gather uses runtime-owned gather investigation.
- Branch report status/errors are preserved enough for coordination decisions.

Verification:

- Focused supervisor graph/nodes tests pass.
- Add or tighten tests for "no supervisor self-synthesis" and "worker gather
  path uses runtime gather."

2026-06-24 evidence:

- Existing tests prove Composer output is the supervised answer output and worker
  reports remain gather-only.
- Tests prove validated branch plans gather every branch through
  `run_agentic_gather_investigation(...)`, the runtime-owned gather worker path.
- Corrected stale supervisor docstring wording from gather+synth worker to
  runtime-owned gather-only worker.

### P5-3: Decide what remains compatibility vs migration

Status: Done

Goal: Decide whether shared `react_loop` supervisor routing remains an accepted
debug/eval compatibility path or should migrate to runtime-owned proposal
contracts.

Acceptance:

- Remaining direct `dispatch(name,args)` paths are listed and classified.
- Production path has no hidden dependency on supervisor ReAct routing.
- Any migration work is split into follow-up issues rather than mixed with
  Phase 5 boundary clarification.

Verification:

- `rg -n "dispatch\\(|run_react_tool_loop|run_supervisor_loop|RuntimeActionProposal" src\rag_cti tests`

2026-06-24 evidence:

- `run_supervised_answer(branch_plan=None)` now emits
  `supervisor_entrypoint="legacy_autonomous_debug_eval"` trace metadata.
- `run_supervised_answer(branch_plan=...)` emits
  `supervisor_entrypoint="runtime_validated_branch_plan"` and skips autonomous
  supervisor routing.
- Remaining direct `dispatch(name,args)` paths are classified as shared
  `react_loop`, legacy/debug graph wiring, or supervisor debug/eval/manual
  compatibility; production `answer()` has no hidden dependency on autonomous
  supervisor routing.

## Phase 4 Boundary Model

Current implementation:

```text
model turn
  -> explicit proposal extraction boundary
  -> RuntimeActionProposal batch
  -> runtime validates and executes proposal batch
  -> RuntimeObservation / RuntimeEvent batch
  -> provider protocol messages rendered from observations
```

The important difference from the earlier partial state is ownership:
`RuntimeTurnAdapter.run_turn()` no longer routes production gather execution
through the shared `react_loop` callback path. The shared `react_loop` remains
for legacy/debug/supervisor compatibility.

## Phase 4 Done Criteria

Phase 4 is complete only when all of these are true:

- `RuntimeActionProposal` is the runtime-owned next-action boundary.
- Provider-specific tool-call shape is isolated behind a proposal extractor or
  adapter boundary.
- `RuntimeTurnAdapter.run_turn()` has an explicit proposal handling step rather
  than relying on callback-shaped execution as the primary control flow.
- Runtime execution accepts `RuntimeActionProposal` objects, not bare
  `name,args`, on the production gather path.
- Observation/event metadata preserves proposal identity, including runtime
  `action_id` and external/provider `tool_call_id` when available.
- Invalid, rejected, deadline-skipped, duplicate, successful, and errored tool
  outcomes all retain proposal identity.
- `ToolMessage` remains only a provider protocol pairing artifact.
- Tests directly prove `_execute_action_proposal()` receives a
  `RuntimeActionProposal`.
- Tests directly prove proposal extraction can be exercised without treating
  `ToolMessage` content as the source of truth.
- Focused runtime harness tests, shared `react_loop` tests, supervisor tests, and
  ruff pass.

## Open Issues

### P4-1: Make proposal extraction explicit

Status: Done

Goal: Extract provider tool-call objects into `RuntimeActionProposal` objects as
an explicit runtime adapter step, instead of doing it only inside the
`dispatch_tool_call` callback.

Acceptance:

- A named extractor function or method returns a tuple/list of
  `RuntimeActionProposal`.
- It preserves provider `tool_call_id`, tool name, args, source, turn index, and
  runtime `action_id`.
- Non-dict args are normalized deterministically.
- Unit tests cover normal, missing id, missing name, and non-dict args.
- Existing runtime turn behavior remains compatible.

Verification:

- `python -m pytest tests\unit\test_runtime_harness.py -q -o addopts=""`
- `python -m ruff check src\rag_cti\runtime_harness.py tests\unit\test_runtime_harness.py`

2026-06-24 evidence:

- Added/verified `RuntimeTurnAdapter.extract_action_proposals(...)`.
- Covered normal provider id/name/args, missing id, missing name, and non-dict
  args.

### P4-2: Move production turn flow to proposal batch execution

Status: Done

Goal: Make `RuntimeTurnAdapter.run_turn()` execute a batch of
`RuntimeActionProposal` objects as a visible runtime step.

Acceptance:

- Production gather path has a visible `proposal batch -> observation batch`
  transition.
- Callback-based dispatch remains only a compatibility adapter if still needed
  for provider protocol pairing.
- Parallel dispatch preserves unique action ids and observation ids.
- Deadline-skipped tool proposals become rejected observations with proposal
  identity.

Verification:

- `python -m pytest tests\unit\test_runtime_harness.py tests\unit\test_agentic_nodes.py -q -o addopts=""`
- `python -m ruff check src\rag_cti\runtime_harness.py src\rag_cti\knowledge\react_loop.py tests\unit\test_runtime_harness.py`

2026-06-24 evidence:

- `RuntimeTurnAdapter.run_turn()` directly invokes one model turn, extracts the
  proposal batch, executes the proposal batch, and appends ToolMessages rendered
  from observations.
- Tests capture `_execute_action_proposals(...)` receiving the proposal batch.
- Parallel dispatch and deadline-skipped proposals retain unique proposal and
  observation identity.

### P4-3: Strengthen proposal trace accounting

Status: Done

Goal: Trace proposal counts and proposal outcomes so trajectory eval can compare
model proposed actions, runtime accepted executions, rejections, and errors.

Acceptance:

- Trace metadata includes per-turn proposal count.
- Trace metadata includes proposal outcome counts by event kind/status.
- Rejected/invalid/deadline outcomes include reason and proposal source.
- Tests assert trace metadata for at least accepted, invalid, and deadline
  proposal outcomes.

Verification:

- `python -m pytest tests\unit\test_runtime_harness.py -q -o addopts=""`

2026-06-24 evidence:

- Per-turn trace metadata includes `runtime_turn_proposal_count`.
- Per-turn trace metadata includes proposal status counts and proposal event
  counts.
- Deadline-skipped proposal outcomes are counted.

### P4-4: Re-audit legacy action paths

Status: Done

Goal: Confirm production runtime path no longer has a hidden direct tool-action
execution path that bypasses `RuntimeActionProposal`.

Acceptance:

- Search/audit lists remaining direct `dispatch(name,args)` paths.
- Remaining direct paths are classified as legacy/debug/supervisor compatibility
  or migrated.
- Production single-agent path is covered by tests that fail if proposal
  execution is bypassed.

Verification:

- `rg -n "dispatch\\(|tool_calls|RuntimeActionProposal|run_react_tool_loop" src\rag_cti tests`
- Focused runtime and supervisor tests pass.

2026-06-24 audit:

- Production single-agent gather path is `runtime_harness.py::RuntimeTurnAdapter.run_turn()`;
  it no longer calls `run_react_tool_loop`.
- `runtime_harness.py::_dispatch` remains a compatibility helper, but production
  runtime turn tests fail if `_dispatch` or `_dispatch_tool_call` is used.
- `knowledge/react_loop.py` still supports `dispatch(name,args)` for legacy
  shared use.
- `knowledge/agentic_graph.py` direct dispatch remains legacy/debug/baseline.
- `knowledge/supervisor_nodes.py` and `knowledge/supervisor_graph.py` direct
  dispatch are supervisor debug/eval/manual compatibility paths after Phase 5.

## Current Implementation Snapshot

Current code facts:

- `RuntimeActionProposal` exists in `src/rag_cti/runtime_harness.py`.
- `RuntimeTurnAdapter.extract_action_proposals()` maps current provider
  tool-call shape into a `RuntimeActionProposal` batch.
- `RuntimeTurnAdapter._execute_action_proposal()` is the runtime execution
  boundary for proposals.
- `RuntimeTurnAdapter._execute_action_proposals()` is the runtime batch
  execution boundary.
- `RuntimeTurnAdapter.run_turn()` directly owns the production model turn and
  proposal batch handling.
- `src/rag_cti/knowledge/react_loop.py` remains a shared compatibility loop for
  legacy/debug/supervisor paths.
- Tests directly capture `_execute_action_proposal()` receiving a
  `RuntimeActionProposal`.
- Tests directly capture `_execute_action_proposals()` receiving a proposal
  batch.

Residual risks / later-phase facts:

- Ledger mutation still happens inside legacy tool adapters and dispatch
  compatibility. This is acceptable after Phase 4 only because it is surfaced
  through observation/event/state accounting; reducer-owned ledger mutation is a
  later phase.
- Supervisor and legacy graph action paths still use shared ReAct dispatch
  shapes. Supervisor production boundaries are now closed; any future migration
  from supervisor debug/eval/manual compatibility to runtime proposal contracts
  should be a new named issue.

## Verification Ledger

Latest known local verification:

- `python -m pytest tests\unit\test_runtime_harness.py -q -o addopts=""`
  - 2026-06-24 result: `32 passed, 30 warnings in 0.85s`.
- `python -m ruff check src\rag_cti\runtime_harness.py src\rag_cti\knowledge\react_loop.py tests\unit\test_runtime_harness.py`
  - 2026-06-24 result: `All checks passed!`.
- `python -m pytest tests\unit\test_runtime_harness.py tests\unit\test_agentic_nodes.py tests\unit\test_supervisor_graph.py tests\unit\test_supervisor_nodes.py tests\unit\test_agentic_graph_degradation.py -q -o addopts=""`
  - 2026-06-24 result: `131 passed, 90 warnings in 1.33s`.
- `python -m ruff check src\rag_cti\runtime_harness.py src\rag_cti\knowledge\react_loop.py tests\unit\test_runtime_harness.py`
  - 2026-06-24 result: `All checks passed!`.
- `rg -n "dispatch\\(|tool_calls|RuntimeActionProposal|run_react_tool_loop" src\rag_cti tests`
  - 2026-06-24 result: remaining direct dispatch paths are legacy/debug,
    shared `react_loop`, or supervisor compatibility; production single-agent
    runtime gather path is proposal-batch owned.
- `python -m pytest tests\unit\test_runtime_harness.py tests\unit\test_agentic_nodes.py tests\unit\test_supervisor_graph.py tests\unit\test_supervisor_nodes.py -q -o addopts=""`
  - 2026-06-24 result: `131 passed, 82 warnings in 1.10s`.
- `python -m pytest tests\unit\test_runtime_harness.py tests\unit\test_agentic_nodes.py tests\unit\test_supervisor_graph.py tests\unit\test_supervisor_nodes.py -q -o addopts=""`
  - 2026-06-24 result: `132 passed, 82 warnings in 1.07s`; includes direct
    validated-branch-plan coverage for runtime-owned gather on every branch.
- `python -m ruff check src\rag_cti\runtime_harness.py src\rag_cti\knowledge\agentic_nodes.py src\rag_cti\knowledge\supervisor_graph.py tests\unit\test_runtime_harness.py tests\unit\test_agentic_nodes.py tests\unit\test_supervisor_graph.py`
  - 2026-06-24 result: `All checks passed!`; ruff reported Windows access
    warnings while writing `.ruff_cache`, but lint checks succeeded.
- `rg -n "dispatch\\(|run_react_tool_loop|run_supervisor_loop|RuntimeActionProposal|branch_plan|supervised_answer|run_supervised_answer|evaluate_supervisor_admission" src\rag_cti tests\unit`
  - 2026-06-24 result: production `answer()` passes validated `branch_plan`;
    validated plan tests fail if `run_supervisor_loop()` is called; remaining
    direct dispatch / ReAct loop paths are shared `react_loop`, legacy graph,
    supervisor nodes tests, or supervisor debug/eval/manual compatibility.
- `python -m pytest tests\unit\test_runtime_harness.py tests\unit\test_agentic_nodes.py -q -o addopts=""`
  - 2026-06-24 result: `112 passed, 80 warnings in 0.97s`.
- `python -m pytest --no-cov -q tests\integration\test_agentic_answer.py`
  - 2026-06-24 result: `1 passed, 596 warnings in 53.16s`.
- `python -m ruff check src\rag_cti\runtime_harness.py tests\unit\test_runtime_harness.py tests\unit\test_agentic_nodes.py`
  - 2026-06-24 result: `All checks passed!`.

Agents must append their own current-session verification results here after
running the commands relevant to their issue.

## Completion Rules

An issue may be marked Done only when:

- Its acceptance criteria are met.
- Its verification commands have been run in the current session.
- Any residual risk is listed.
- This document is updated.

A phase may be marked Done only when:

- Every done criterion for the phase is satisfied.
- Focused tests and ruff pass.
- Remaining partial implementation details are either eliminated or explicitly
  moved to a later phase.

If evidence is mixed, mark the work Partial, not Done.
