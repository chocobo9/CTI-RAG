# Runtime Harness Orchestration

Status: accepted

Reliability marker: high-trust engineering design. This ADR was written to
counter happy-path drift: treat it as a boundary contract for runtime harness
work, not as an aspirational demo plan. Later sessions should prefer this ADR
over loose handoff notes when deciding what belongs in `answer()`,
`runtime_harness.py`, the agentic loop, or the supervisor path.

CTI-RAG's default `answer()` path is a runtime harness, not a workflow pipeline: it first performs query understanding, then selects between the single-agent path and the multi-agent supervisor path without hardcoding graph/vector retrieval steps. Query understanding is the system entry step and should produce a history-resolved task view, retrieval search queries, entities/constraints, and a decomposition proposal; the runtime harness admits the supervisor path only when the proposal represents independent branches suitable for parallel worker execution.

The single-agent path remains the direct gather/sufficiency/synthesis path for simple or dependent questions. The supervisor path is reserved for multi-agent coordination: the supervisor coordinates validated branch plans, dispatches gather-only workers, monitors branch reports, handles retries or repair branches, and triggers the Composer. Workers gather evidence for one assigned sub-question into a local ledger; the Composer synthesizes only over branch reports; citation validity remains a deterministic grounding guard over the merged ledger. Retrieval subqueries are search hints, not supervisor branches.

## Runtime Query Understanding Contract

Query understanding is the first runtime harness step, before choosing between the single-agent path and the supervisor path. It is distinct from the supervisor and distinct from retrieval execution.

The structured result should carry at least:

- the original user query;
- a history-resolved task view, such as a standalone query for the current turn;
- retrieval search queries or subqueries;
- extracted entities;
- extracted payload constraints, including source, ATT&CK, and entity constraints where available;
- a decomposition proposal for possible multi-agent execution;
- parse or fallback status for the query-understanding step.

The decomposition proposal is advisory. It may include whether the task appears suitable for supervisor execution, proposed branches, each branch's sub-question, optional focus entity, optional facet, and the reason that branch is independently gatherable. Retrieval subqueries remain search hints and must not be treated as supervisor branches by default.

Existing retrieval-level structures remain useful but are not the full runtime contract. `RewriteOutput` currently represents rewritten retrieval queries plus extracted entities, and `PayloadConstraint` represents retrieval constraint or boost signals. The runtime query-understanding result may reuse those structures, but it must also carry the history-resolved task view, decomposition proposal, and parse/fallback status needed by `answer()` to choose an execution path.

## Supervisor Admission

`answer()` owns the choice between the single-agent path and the supervisor path. This choice should use the query-understanding result and conservative validation, without introducing another named router component.

The supervisor path is admitted only when the proposed branches are independently gatherable and can be composed after evidence collection. Parse failures, low-confidence decomposition, unclear branch boundaries, dependent reasoning chains, or simple questions should fall back to the single-agent path.

Admission requires all of the following:

- query understanding completed without fallback, parse error, or LLM error;
- the decomposition proposal marks the task as suitable for supervisor execution;
- the branch count is at least two and no more than the configured supervisor branch cap;
- every branch has a concrete sub-question;
- branches can gather evidence independently without requiring another branch's answer as input;
- the original task requires final composition across branches rather than one branch answering the whole question.

Admission must be rejected when any of the following is true:

- query understanding fell back or failed to parse;
- there is no decomposition proposal or fewer than two branches;
- the task is a simple factual question;
- the task is a sequential or dependent multi-hop question;
- branch boundaries are unclear;
- branch count exceeds the configured cap and cannot be safely reduced;
- the proposed branches are merely retrieval search queries rather than independent worker tasks;
- the task needs a shared exploratory ledger instead of isolated branch ledgers.

The deterministic effort tier is an advisory signal, not admission. `simple` should default to the single-agent path; `comparison` and `complex` may be considered for the supervisor path only when validated independent branches exist. The LLM decomposition proposal is also advisory: invalid, ambiguous, dependent, or fallback understanding must use the single-agent path.

## Supervisor Responsibilities

The supervisor is the multi-agent coordinator. It should:

- accept a validated branch plan;
- dispatch one gather-only worker per branch;
- monitor branch reports;
- handle empty, failed, or partial branches with retry, repair, or additional branch creation when justified;
- trigger the Composer after branch evidence is sufficient or the budget is exhausted.

The supervisor should not perform query rewrite, retrieve directly, write the final answer, validate citations, or decide whether a simple question should enter the supervisor path. Those responsibilities belong to query understanding, worker agents, Composer, deterministic grounding guards, and the runtime harness respectively.

## Branch Report Contract

Worker reports must be strong enough for coordinator decisions, not only final answer composition. A branch report should include at least stable branch identity, assigned sub-question, optional focus entity, optional facet, status, evidence summary, key entities, techniques, cited IDs, gaps, suggested follow-up retrieval queries, suggested graph targets, errors, evidence counts, outline counts where available, stop reason, token usage, and iteration count.

The status should distinguish successful, partial, empty, and failed branches so the supervisor can decide whether to retry, repair, add a branch, or proceed to composition.

Minimum fields:

- `branch_id`: stable identity for the assigned branch;
- `sub_question`: the exact task assigned to the worker;
- `focus_entity`: optional entity the branch centers on;
- `facet`: optional aspect such as techniques, infrastructure, malware, targets, attribution, or timeline;
- `status`: one of `ok`, `partial`, `empty`, or `failed`;
- `evidence_summary`: bounded prose summary of gathered evidence, grounded in the branch ledger;
- `key_entities`: important entities found or resolved during the branch;
- `techniques`: structured ATT&CK technique triples where relevant;
- `cited_ids`: evidence IDs the Composer may cite, validated later against the merged ledger;
- `gaps`: explicit missing evidence or unanswered sub-parts;
- `suggested_queries`: follow-up retrieval queries the supervisor may use for retry or repair;
- `suggested_graph_targets`: follow-up graph targets the supervisor may use for retry or repair;
- `errors`: provider, tool, parse, timeout, or other branch execution errors;
- `n_facts`, `n_chunks`, and `n_outlines`: evidence volume counters;
- `stop_reason`, `tokens_used`, and `iteration_count`: branch execution telemetry.

Status semantics:

- `ok`: enough evidence was gathered for this branch to enter composition;
- `partial`: some evidence was gathered, but known gaps remain;
- `empty`: the branch ran but found no useful evidence;
- `failed`: the branch did not complete normally because of tool, provider, parse, timeout, or other execution failure.

The branch report must not store the full branch ledger. The branch ledger remains branch-local during worker execution and is merged separately for citation validation. The report is the compact coordination and composition contract; the ledger remains the evidence authority.

`evidence_summary` is allowed because CTI questions are not limited to technique set operations. Infrastructure, campaign, targeting, attribution, timeline, and tooling questions often need a compact natural-language summary. That summary does not create new evidence: facts must still be backed by `cited_ids` and validated against the merged ledger.

## Open Runtime Harness Work Items

The following implementation details are acknowledged but not fully resolved in this ADR yet:

### Runtime Dependency Construction

`answer()` should own construction or retrieval of shared runtime dependencies, while agent graph and supervisor graph receive dependencies rather than building provider clients or provider policy. The dependency object should carry reusable runtime services and provider policy, not per-run reasoning state.

Expected dependency categories:

- settings;
- retrieval pipeline and the `run_retrieve` callable bound to history;
- fact store and ontology nodes;
- query-understanding callable;
- gather tool-calling model;
- generator for single-agent synthesis;
- verifier client and sufficiency judge;
- Composer callable;
- provider limiters, retry policy, timeout policy, and shared provider clients where applicable.

The dependency object must not carry branch reports, ledgers, query-understanding results, admission decisions, final answers, or other per-run reasoning state.

Provider construction should be centralized so DeepSeek, Qwen, Groq, Ollama, and Anthropic clients are built under one provider policy. Execution units should not hardcode provider base URLs, retry behavior, limiter use, or timeout semantics.

### Query-Understanding Schema Details

The runtime query-understanding result should be a higher-level contract than existing retrieval rewrite output. It should include:

- original query;
- history-resolved task view, such as `standalone_query`;
- retrieval queries;
- extracted entities;
- payload constraints;
- decomposition proposal;
- parse or fallback status;
- optional confidence and reason fields.

`RewriteOutput` may remain the retrieval-level result for rewritten retrieval queries and extracted entities. `PayloadConstraint` may remain the retrieval constraint or boost signal. The runtime result may reuse both, but it must not collapse into either one.

The decomposition proposal should represent possible worker branches, not retrieval search hints. Branches should carry sub-question, optional focus entity, optional facet, and a reason the branch is independently gatherable.

### Supervisor Coordination Policy

The supervisor coordinates only after runtime admission has accepted a validated branch plan. Coordination policy still needs exact implementation, but the intended boundaries are:

- retry failed branches only within an explicit retry cap;
- distinguish `empty`, `partial`, and `failed` branch reports;
- allow repair branches only when the report contains concrete gaps or suggested follow-up queries/graph targets;
- allow partial branches to enter composition only when retry/repair is exhausted or not justified;
- trigger composition only after branch evidence is sufficient, all useful repair paths are exhausted, or the global budget/deadline requires stopping;
- hard stop after composition so no later dispatch mutates the evidence set after the final answer is produced.

The supervisor should surface unresolved gaps to the Composer rather than hiding them or silently treating failed branches as negative evidence.

### Composer Contract

The Composer remains a no-tool synthesis role. It should receive:

- original query and history-resolved task view;
- relevant query-understanding context such as entities, constraints, and accepted branch plan;
- branch reports;
- supervisor coordination summary, including branch statuses and exhausted gaps;
- citation IDs and enough evidence summary to write a grounded answer.

The Composer should not retrieve, rewrite, dispatch workers, create repair branches, validate citations, or introduce facts not present in branch reports and ledgers.

The Composer prompt and payload must support general CTI synthesis, not only technique comparison. It should handle techniques, infrastructure, malware/tooling, targeting, attribution, campaign timelines, and missing-evidence cases. When evidence is incomplete, it should produce a grounded incomplete answer with explicit gaps.

### Public API and CLI Surface

`answer()` is the production entry point for grounded CTI answers. It should run query understanding, choose the single-agent path or supervisor path, and return the final answer shape.

Explicit single-agent and supervisor entry points may remain as debug or baseline surfaces, but callers should not be required to choose them in production. CLI commands should reflect the same boundary: the default command should use `answer()`, while force-single-agent or force-supervisor commands should be clearly marked as debug, eval, or baseline modes.

The current `supervisor_enabled` setting should not remain a production all-or-nothing mode switch. Its final replacement semantics should distinguish at least:

- supervisor allowed for admitted tasks;
- supervisor disabled;
- supervisor forced for debug/eval.

### Budget, Timeout, Limiter, and Retry Policy

The runtime harness should own global budget and deadline propagation. Query understanding, retrieval rewrite/HyDE calls, gather model calls, judge calls, supervisor calls, Composer calls, and final synthesis calls should all be covered by explicit timeout and provider admission policy.

Provider retry authority should be single and inspectable. SDK retries, tenacity wrappers, fallback model chains, and limiter cooldowns must not multiply unexpectedly. Daily quota failures should fail fast; recoverable rate limits may retry or cooldown under the centralized provider policy.

Branch-level budgets should inherit from the global run budget. Supervisor fan-out must not multiply provider concurrency beyond the configured limiter. Stop reasons should be normalized enough that single-agent and supervisor paths can be compared in traces and tests.

### State and Trace Contract

The final answer and trace should expose enough runtime state to explain what happened without dumping full prompt context. At minimum, traces should record:

- query-understanding status;
- execution path selected: single-agent or supervisor;
- supervisor admission decision and reason;
- branch count and branch statuses;
- stop reasons;
- tool-call counts;
- provider errors or fallback events;
- citation drops;
- unresolved gaps.

Full ledgers remain internal evidence authority, but trace summaries should be sufficient for debugging, regression tests, and later eval harness analysis.

### Harness-Level Tests

Before memory or eval harness work, the runtime harness needs focused tests for its own contracts:

- query-understanding fallback uses the single-agent path;
- simple questions bypass supervisor;
- validated independent comparison branches admit supervisor;
- dependent multi-hop questions reject supervisor;
- retrieval subqueries are not treated as supervisor branches;
- branch report status drives retry/repair/compose behavior;
- Composer is invoked at most once per supervised answer and no dispatch happens after composition;
- invalid Composer citations are dropped by the deterministic citation guard;
- limiter coverage includes query understanding, gather, judge, supervisor, Composer, and synthesis calls;
- `answer()` is the production entry point while explicit single-agent/supervisor calls remain debug or baseline surfaces.

Considered alternatives: routing all answers through the supervisor would make simple questions pay an unnecessary coordination and Composer cost, and would let a supervisor LLM decide a problem shape that the runtime harness can often reject conservatively. Keeping `agentic_answer()` and `supervised_answer()` as parallel mainline entry points preserves implementation history but leaves callers responsible for choosing the agent topology. The accepted shape keeps explicit single-agent and supervisor entry points only as debug/baseline surfaces while making `answer()` the production runtime harness.
