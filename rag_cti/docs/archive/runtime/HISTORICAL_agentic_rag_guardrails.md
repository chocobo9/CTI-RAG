# HISTORICAL — Agentic RAG Runtime Guardrails and Eval Harness

> Archive category: Runtime north-star framing.
>
> **Status: HISTORICAL NORTH-STAR REFERENCE / NON-AUTHORITATIVE.** General guardrail
> principles remain useful, but the Current Mapping, Current Gaps, and iteration plan
> below are not current implementation truth. Use the Runtime ADR and phase-control
> document for current boundaries and migration status.

Reliability marker: high-trust engineering design. This document is intended as
a boundary and guardrail reference, not a happy-path implementation checklist.
When future sessions conflict with looser generated plans, prefer the principle
here: the runtime harness gives the model context, environment, policy, budgets,
traceability, and stopping boundaries; it should not become a bag for every
retrieval, graph, or knowledge-layer implementation detail.

This document records the architectural direction for CTI-RAG after the
optimization worktree moved the default answer path toward agentic RAG. It is
not a new term or a product category. It is a project-level framing for an
industry pattern:

> agentic RAG = dynamic planning and evidence gathering
> runtime guardrails = code-level constraints on input, tools, retrieval,
> output, memory, and stopping
> eval harness = offline/online evidence that the system did not regress

The important distinction for this project: **guardrails are not workflows**.
The agent keeps the ability to choose a path. The system controls the boundaries
within which that path is allowed to run.

Another useful framing is:

> agent = model + agent harness

In that broad sense, the "harness" is everything outside the model that turns a
token predictor into an agent: prompts, tools, tool execution, memory, state,
policies, retries, fallback, budgets, observability, and evaluation. This
document uses a narrower split so design discussions stay precise:

- **runtime harness**: the infrastructure that participates in a live agent run.
  It includes orchestration, tool execution, state, memory, runtime guardrails,
  provider fallback, and trace emission.
- **eval harness**: the infrastructure that tests the runtime harness and model.
  It includes fixed eval sets, real regression runners, judges, metrics, and
  failure attribution.

Guardrails are part of the runtime harness. The eval harness is how the project
proves those guardrails improved behavior instead of only adding complexity.

---

## 1. Industrial Consensus

Industry practice has not converged on a single product called "guardrailed
agentic RAG". It has converged on combining three mature stacks:

1. **Agentic orchestration**
   - The system can plan, call tools, inspect gaps, gather more evidence, and
     revise its route.
   - Examples of this direction include LangGraph-style explicit state graphs,
     Self-RAG, CRAG, Reflexion-like retrieve/evaluate/revise loops, and
     agent-tool orchestration frameworks.

2. **Runtime guardrails**
   - The system intercepts unsafe or low-value behavior at runtime: invalid
     input, unsafe tool calls, irrelevant or hostile retrieved context,
     unsupported output, citation hallucination, runaway loops, and provider
     failure.
   - Examples of this direction include NVIDIA NeMo Guardrails, Guardrails AI,
     Bedrock Guardrails, Azure AI Content Safety / groundedness checks, and
     Databricks Mosaic AI judges / AI Gateway.

3. **Evaluation harness**
   - The system is measured with repeatable offline and online tests: retrieval
     relevance, groundedness, citation quality, correctness, latency, cost,
     tool-call behavior, and safety.
   - Examples of this direction include RAGAS, DeepEval, Patronus-style
     evaluations, Databricks Agent Evaluation, and custom regression harnesses.

This matches the common "model + scaffolding" view of LLM agents. The model is
not the whole agent. The runtime harness supplies environment, actions, state,
feedback, constraints, and stopping. The eval harness is separate: it drives the
agent system under repeatable conditions and records whether the runtime harness
and model behave well together.

For this project, the implementation goal should be described as:

> CTI-RAG implements agentic RAG with runtime guardrails and an eval harness.

Avoid presenting "bounded agentic RAG" as a formal external concept. It is a
useful internal shorthand, but the more precise framing is:

- agentic RAG
- runtime guardrails
- eval harness

---

## 2. Guardrail Layers

The following layers are a practical checklist. Different vendors name them
differently, but the shape is broadly shared.

| Layer | Blocks or Controls | Typical Mechanisms |
|---|---|---|
| Input rails | Prompt injection, jailbreak, PII, out-of-scope requests, malicious user instructions | Classifiers, policy checks, PII detectors, topic filters |
| Control / planning rails | Runaway loops, invalid state transitions, over-retrieval, premature or delayed stopping | State graphs, deterministic stop rules, budgets, deadlines, no-progress checks |
| Retrieval rails | Malicious retrieved instructions, low relevance, low credibility, poisoned context | Chunk filters, relevance/credibility thresholds, injection detection, source policy |
| Tool-use rails | Invalid parameters, repeated calls, confused-deputy attacks, unauthorized actions | Tool schema validation, authorization, budget checks, dedup/cache, risk tiers |
| Output / grounding rails | Unsupported claims, fake citations, PII leakage, unsafe answers, format drift | Citation guards, claim checks, NLI/LLM judges, structured output validation |
| Memory governance | Memory pollution, cross-user leakage, stale assumptions, over-personalization | Scoped memory, write policies, expiry, audit, retrieval limits |
| Eval rails | Silent regressions in quality, safety, latency, cost, or tool behavior | Fixed eval sets, real regression runs, dashboards, failure attribution |

The CTI setting makes retrieval and tool-use rails especially important. Threat
intelligence content is adversarial by nature: a retrieved report, IOC note, or
malware analysis can contain text that looks like instructions. The system must
not let retrieved content directly steer tool use or override higher-priority
instructions.

---

## 3. Workflow vs Guardrailed Agentic RAG

Workflow RAG pre-decides the route:

```text
rewrite -> retrieve -> rerank -> generate -> cite
```

or:

```text
resolve actor A -> graph query A -> resolve actor B -> graph query B -> compare
```

That is stable and testable, but it is not agentic. It works best when the task
shape is already known.

Unconstrained agentic RAG gives the model broad freedom:

```text
model decides tool -> model decides next gap -> model decides when to stop
```

That is flexible, but it is fragile. It can repeat tools, paste long state into
retrieval queries, miss stopping conditions, drift from evidence, or overreact to
provider errors.

This project should follow the middle path:

```text
agent proposes action
system validates action
tool writes structured evidence to ledger
system checks progress / sufficiency / risk
agent continues only inside those boundaries
system validates citations and output
```

The agent chooses routes. The system enforces boundaries.

Guardrails must answer questions such as:

- Is this tool call allowed?
- Are the parameters valid and small enough?
- Is the same call already cached?
- Does graph coverage already answer this enumeration question?
- Has the loop made progress?
- Is the answer grounded in ledger evidence?
- Are the citations real?

Guardrails should **not** encode a fixed business path for every question. That
would collapse the system back into workflow RAG.

---

## 4. Current Project Mapping

The optimization worktree has already implemented several guardrail ideas in
code.

### Implemented Control Rails

- The agentic answer path uses an outer LangGraph `StateGraph`.
- The inner gather loop is bounded by max iterations, wall-clock deadline,
  token ceilings, and hard tool budgets.
- `decide_next` handles stop reasons such as `sufficient`, `graph_sufficient`,
  `no_progress`, `open_cat_stall`, `timeout`, `budget`, `tool_budget`,
  `parse_fallback`, and `provider_error`.
- `graph_sufficient` deterministically stops graph-heavy comparison/enumeration
  questions when graph coverage is complete, without waiting for the LLM judge.

### Implemented Tool-Use Rails

- Tool calls are recorded in an action log.
- Identical tool calls are deduplicated through a per-run cache.
- Hard tool budgets are enforced at `dispatch`, not only between graph turns.
- Long `retrieve()` queries are normalized and capped.
- `retrieve()` is suppressed when graph facts already cover the comparison
  question.

### Implemented Grounding Rails

- Final citations are intersected with the ledger's real IDs.
- Spurious `chunk_` prefixes can be recovered when they map to a real chunk.
- Markdown-code citations such as ``[`fact_id`]`` are accepted.
- Bare `fact_...` IDs are conservatively recovered only when they exist in the
  ledger.
- Empty generation content is treated as failure rather than a valid answer.
- Synthesis facts are capped so the generator is not fed an unbounded fact dump.

### Implemented State Rail

- `EvidenceLedger` is the structured side channel for gathered state.
- It records chunks, facts, graph outlines, action history, conflicts, and cache
  entries.
- The agent no longer needs to infer the whole environment from transcript text.

### Implemented Reliability Rail

- `close_cached_resources()` closes cached external resources and clears the
  cache, preventing Neo4j driver cleanup warnings at process shutdown.
- LLM limiter and fallback behavior have been strengthened in the generation
  path.

### Implemented Eval Rail

- The recent optimization used TDD: RED tests first, then minimal GREEN fixes.
- The target unit set passed with `144 passed`.
- A real regression set measured stop reason, tool count, token usage, fact
  count, context count, citation count, answer length, and wall time.

Recent real regression outcomes:

| Case | Stop Reason | Tool Calls | Facts | Citations | Notes |
|---|---:|---:|---:|---:|---|
| APT29 vs Turla graph comparison | `graph_sufficient` | 7 | 320 | 118 | No longer stops by `tool_budget` |
| APT29 mixed graph + prose | `sufficient` | 5 | 173 | 126 | Allows necessary prose retrieval |
| APT29 setup question | `sufficient` | 3 | 173 | 109 | Single-entity enumeration |
| Turla follow-up with history | `sufficient` | 9 | 320 | 8 | Uses conversation history |

---

## 5. Current Gaps

The project is no longer prompt-only agentic RAG, but it is not yet production
complete. The main missing categories are:

### Runtime Harness Structure

Current state: the runtime harness has grown real guardrails, but the control
plane is not yet cleanly consolidated. The current architecture decision is
recorded in `docs/adr/0001-runtime-harness-orchestration.md`.

Pain points:

- **Query understanding is still mostly hidden inside retrieval.**
  - `LLMQueryRewriter` already returns rewritten retrieval queries and entities,
    and `QueryRewriteRetriever.understand()` turns them into subqueries plus a
    `PayloadConstraint`.
  - The production runtime harness should run query understanding as the first
    system step, before choosing single-agent versus supervisor orchestration.
  - Its structured output should include the history-resolved task view,
    retrieval search queries, extracted entities, payload constraints, and an
    advisory decomposition proposal.
  - The existing `RewriteOutput` is a retrieval-level result: rewritten queries
    plus extracted entities. It is useful input, but not the complete runtime
    harness contract.
  - The existing `PayloadConstraint` remains a retrieval constraint or boost
    signal. It should not be overloaded into a supervisor admission rule.
  - Retrieval subqueries are search hints, not supervisor branches.
- **Single-agent and supervisor paths are still exposed as parallel mainline
  surfaces.**
  - The single-agent path is the right execution shape for simple or dependent
    questions.
  - The supervisor path is the right execution shape only for independent
    branches that can be gathered separately and composed.
  - Deterministic effort tiering and LLM decomposition proposals are advisory
    signals, not admission. Supervisor admission requires validated independent
    branches.
  - `answer()` should own this orchestration selection; explicit
    `agentic_answer()` and `supervised_answer()` should remain debug/baseline
    surfaces, not the production choice forced onto callers.
- **The supervisor is not yet a full coordinator.**
  - It should coordinate a validated branch plan, dispatch gather-only workers,
    monitor branch reports, repair failed/empty branches, and trigger the
    Composer.
  - It should not rewrite the query, retrieve directly, write the final answer,
    or validate citations.
  - It also should not decide whether a simple question enters the supervisor
    path; that choice belongs to the runtime harness after query understanding.
- **Branch reports are too thin for coordination.**
  - The current report carries the sub-question, focus entity, technique set,
    citations, counts, stop reason, tokens, and iterations.
  - A coordinator also needs stable branch identity, facet, status, gaps,
    suggested follow-up retrievals, suggested graph targets, errors, and richer
    evidence summaries.
  - Minimum status values should distinguish `ok`, `partial`, `empty`, and
    `failed`.
  - The report should remain a compact coordination and composition contract; the
    branch ledger remains the evidence authority and is merged separately for
    citation validation.
- **Stop policy and stall accounting still need consolidation.**
  - `decide_next()` is now an ordered stop-rule table, but the behavior still
    needs golden tests.
  - `open_cat_stall` is still derived inside graph wiring rather than a pure
    tested helper.
- **Policy decisions are not first-class objects yet.**
  - Some guardrails return structured errors, but there is no common
    `PolicyDecision` shape with rail type, reason, severity, and evidence.
  - This makes observability and future eval harness work harder.

Needed:

- make `answer()` the authoritative production runtime harness;
- make query understanding the first runtime harness step, with a structured
  output that includes a history-resolved task view, retrieval queries, entities,
  constraints, a decomposition proposal, and parse/fallback status;
- admit the supervisor path only for validated independent branch plans, with
  parse failures, unclear branches, dependent reasoning chains, and simple
  questions falling back to the single-agent path;
- reject supervisor admission when proposed branches are merely retrieval
  subqueries, require sequential dependency, exceed the branch cap without safe
  reduction, or need a shared exploratory ledger;
- keep the single-agent path as the direct gather/sufficiency/synthesis path for
  simple or dependent questions;
- strengthen `BranchReport` so the supervisor can coordinate rather than merely
  dispatch and wait; the minimum contract includes branch identity, sub-question,
  focus entity, facet, status, evidence summary, key entities, techniques,
  cited IDs, gaps, suggested retrieval queries, suggested graph targets, errors,
  evidence counts, outline counts, stop reason, token usage, and iteration count;
- keep graph/vector choice inside agent tool use, never as a graph-vs-vector
  workflow router;
- add golden tests for stop-rule priority and extract remaining stall accounting
  into pure logic;
- introduce a common policy decision shape for tool-use, retrieval, output, and
  memory rails.

### Memory

Current state: conversation history is passed through the main path. This is not
full memory.

Needed:

- session memory: the active investigation context;
- task memory: confirmed hypotheses, rejected hypotheses, open gaps;
- project memory: project-level terminology and defaults;
- user memory: stable preferences and allowed assumptions;
- memory write/read policy, expiry, isolation, and audit.

Memory must be structured and scoped. Raw history should not be blindly appended
to prompts, especially when small local models are used.

### Input Rails

Current state: not systematically implemented.

Needed:

- prompt-injection detection;
- PII / secret detection;
- topic and scope enforcement;
- request risk classification;
- user permission checks before tools are available.

### Retrieval Rails

Current state: only early functional retrieval rails exist, such as suppressing
unnecessary retrieve when graph evidence is complete.

Needed:

- retrieved chunk injection detection;
- source credibility filtering;
- chunk relevance thresholds;
- chunk-level security labels;
- policy for adversarial CTI content that contains instructions.

### Tool Authorization Rails

Current state: tool budgets, deduplication, and parameter normalization exist.

Needed:

- per-tool risk tiers;
- user/project authorization checks;
- stricter schemas and enum parameters where possible;
- explicit rejection reasons in traces;
- audit logs for side-effecting tools if any are added later.

### Output and Faithfulness Evaluation

Current state: deterministic citation guard exists.

Needed:

- claim decomposition;
- claim-to-evidence mapping;
- NLI or LLM-judge groundedness checks;
- unsupported-claim reporting;
- answer uncertainty and evidence-gap surfacing.

### Observability

Current state: logs and telemetry exist, but not a full agent-run trace product.

Needed:

- per-run trace with tool calls, arguments, rejection reasons, ledger deltas,
  judge verdicts, stop reason, latency breakdown, and token/cost metrics;
- failure replay inputs;
- dashboards for stop-reason distribution, citation drops, tool-call count, and
  provider errors.

### Small-Model Readiness

If the project targets local 1B/2B models, guardrails become more important, not
less. Small models are weaker at planning, schema following, long-context
reasoning, stopping, and citation format compliance.

Needed:

- shorter prompts;
- stronger structured state views;
- task-level tools with narrow schemas;
- programmatic set operations for graph comparisons;
- deterministic stopping where possible;
- template or programmatic synthesis for fact-heavy answers;
- eval sets separated by model size.

---

## 6. Development Principles

Use these principles for future work:

1. **Agentic, not workflow**
   - Do not hardcode a full route for every question.
   - Let the agent choose actions, but enforce runtime boundaries.

2. **Guardrails in code, not only prompt**
   - Critical rules must execute in Python, not just appear in system prompts.

3. **Evidence-first**
   - Answers must be based on ledger evidence: facts, chunks, outlines, and
     citations.

4. **Strict grounding**
   - A statement can be true in the real world and still fail if the retrieved
     evidence does not support it.

5. **Small-model ready**
   - Prefer structured tools, short prompts, deterministic state checks, and
     programmatic operations.

6. **Eval-gated iteration**
   - Every change to agent behavior needs unit tests and real regression evidence.

7. **Defense in depth**
   - Input, retrieval, tools, output, memory, and evaluation need separate rails.

---

## 7. Suggested Iteration Order

Recommended next major workstreams:

1. **Runtime harness consolidation**
   - Make `answer()` the authoritative production runtime harness.
   - Run query understanding as the first system step and carry its structured
     result through the harness.
   - Select between the single-agent path and the supervisor path at the harness
     level; do not expose that choice as a required caller decision.
   - Centralize runtime dependency construction so agent graph and supervisor
     graph receive dependencies rather than building provider clients or provider
     policy.
   - Keep runtime dependencies separate from run state: dependencies carry
     reusable services and provider policy; query-understanding results,
     admission decisions, ledgers, branch reports, and answers are per-run state.
   - Treat the supervisor as a multi-agent coordinator: dispatch gather-only
     workers, monitor branch reports, repair failed/empty branches, and trigger
     the Composer.
   - Strengthen `BranchReport` so coordination decisions are based on status,
     gaps, errors, counts, and evidence summaries rather than only technique
     lists.
   - Define the Composer input/output contract for general CTI synthesis, not
     only technique comparison.
   - Align public API and CLI surfaces so `answer()` is the production entry
     point and explicit single-agent/supervisor calls are debug or baseline
     surfaces.
   - Replace production all-or-nothing supervisor switching with explicit
     semantics for supervisor allowed, disabled, and forced debug/eval modes.
   - Normalize budget, timeout, limiter, retry, stop-reason, and trace contracts
     across query understanding, retrieval rewrite/HyDE, gather, judge,
     supervisor, Composer, and final synthesis calls.
   - Add harness-level tests for query-understanding fallback, supervisor
     admission, simple-query bypass, branch status, compose-once behavior,
     limiter coverage, and public entrypoint behavior.
   - Extract the remaining stop/stall policy into explicit tested rules.
   - Add a common policy decision object for guardrail outcomes.

2. **Evaluation harness**
   - Build a fixed eval set for simple, compound, multi-turn, graph-heavy,
     prose-heavy, missing-evidence, and adversarial cases.
   - Track correctness, groundedness, citation precision/recall, tool count,
     latency, cost, stop reasons, and failure causes.

3. **Observability**
   - Persist per-run traces.
   - Record ledger deltas, tool rejections, judge verdicts, and latency breakdown.

4. **Memory**
   - Add scoped session/task/project/user memory.
   - Define write policy before adding long-term persistence.

5. **Retrieval rails**
   - Detect injected instructions in retrieved chunks.
   - Filter or quarantine low-trust chunks.

6. **Tool-use security**
   - Add authorization, risk tiers, stricter schemas, and audit logs.

7. **Programmatic synthesis**
   - For graph enumeration and comparison answers, compute fact tables and
     intersections in code.
   - Let the model explain, not invent or manually reconstruct the fact set.

---

## 8. Terms to Use

Prefer:

- agentic RAG
- agent harness
- runtime harness
- runtime guardrails
- eval harness
- control rails
- retrieval rails
- tool-use rails
- grounding rails
- memory governance

Avoid presenting these as invented project-specific concepts:

- bounded agentic RAG as a formal term
- guardrailed RAG as a product category

Acceptable internal shorthand:

> guardrailed agentic RAG

Precise external phrasing:

> agentic RAG with runtime guardrails and an eval harness
