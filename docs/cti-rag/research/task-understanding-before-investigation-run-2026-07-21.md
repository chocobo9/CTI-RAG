# Task Understanding Before the Investigation Agent Run

Status: primary-source research and non-normative design input.

Research date: 2026-07-21.

## Question and verdict

Should Agent Investigation Workspace use a small model to normalize a user's
Original User Task, classify its intent, and identify ambiguity before starting
the Pi Investigation Agent Run?

**Yes, as one bounded model workflow stage, not as an Agent.** The strongest
initial design is one model invocation with no tool, no autonomous continuation,
no planner Harness, and no planner Session. It returns a closed proposal;
deterministic Workspace code alone admits the proposal, falls back to the
unchanged task, rejects the output, or requests clarification.

This conclusion does not establish that a particular small model is adequate for
CTI tasks. Model choice must pass task-specific fidelity, ambiguity, protected-
literal, latency, and cost evaluations.

## Repository facts and current contract conflict

- Pi already exposes provider-neutral one-shot completion through
  `Models.completeSimple(...)`. Its lower-level `prepareSimple(...)` resolves the
  Provider and authentication once, snapshots the request, defers Adapter entry,
  and permits one `start()`. These APIs do not require the Agent loop or an
  `AgentHarness`. [Pi AI prepared invocation documentation](../../../packages/ai/README.md#prepared-simple-invocations),
  [Pi AI implementation](../../../packages/ai/src/models.ts)
- `AgentHarness` is the orchestration layer for Session persistence, runtime
  configuration, operation locking, save points, tools, and the multi-turn model-
  tool loop. Using it only to perform this one fixed preprocessing call would
  introduce lifecycle responsibilities that the stage does not need.
  [AgentHarness lifecycle](../../../packages/agent/docs/agent-harness.md)
- The currently accepted supporting TQ contract says the opposite of the newly
  discussed direction: it runs a private planning `tool_call` and `tool_result`
  inside the same Harness, Session, and Agent Run, then commits a planning save
  point. It also lets the proposal contain Query Candidates and capability needs.
  [Current TQ lifecycle](../agent-workspace/task-context-understanding-v1-contract.md#9-same-harness-lifecycle),
  [current TQ proposal](../agent-workspace/task-context-understanding-v1-contract.md#4-model-proposal-and-deterministic-plan)
- The current PNW contract repeats that lifecycle and has executable acceptance
  cases for the private planning tool call. [Current PNW task-context planning](../agent-workspace/pi-native-workspace-lifecycle-v1-contract.md#62-task-context-planning)

**Conflict disposition:** the new pre-Investigation direction is a deliberate
contract reopen, not a compatible clarification of TQ v1. Before implementation,
the TQ owner must supersede or revise the same-Agent-Run/tool-call requirements,
and the PNW owner must update the linked lifecycle and acceptance cases. This
research note does not perform that normative change.

## Primary-source findings

### 1. A small-model preprocessing stage is an established workflow pattern

- Anthropic distinguishes workflows, where code defines the path through model
  calls, from agents, where the model dynamically controls its process and tool
  use. Its routing workflow classifies an input and directs it to a specialized
  follow-up; it explicitly lists routing common inputs to smaller models as a
  cost/performance technique. [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Azure AI Search sends the original query to a fine-tuned Small Language Model
  to generate synthetic queries. It then combines those queries with the original
  instead of replacing the original. [Azure AI Search transparency note](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/search/transparency-note)

**Inference:** one fixed, schema-bounded call for normalization, intent, and
ambiguity is a workflow stage. It becomes a second Agent only if it gains dynamic
tool choice, autonomous iteration, independent memory, or its own recovery and
planning lifecycle.

### 2. The Original User Task must remain a separate immutable source

- W3C PROV models spelling correction as a revision activity that uses an
  original entity and generates a new entity. A revision is related to, rather
  than overwriting, its source. [W3C PROV Primer: usage, generation, and revision](https://www.w3.org/TR/prov-primer/#activities)
- Azure warns that generated rewrites may omit exact terms and damage searches
  that depend on unique identifiers or product codes. Its retrieval therefore
  retains the original query alongside rewrites. [Azure query rewrite documentation](https://learn.microsoft.com/en-us/azure/search/semantic-how-to-query-rewrite)
- Controlled experiments found that small question-formulation changes can
  change passage ranking dramatically. [Vakulenko et al., 2020](https://aclanthology.org/2020.scai-1.2/)

**Inference:** `normalizedTask` is a derived proposal with provenance, never the
User Task identity. The Investigation Agent must receive both the unchanged task
and the admitted interpretation. Audit, recovery, clarification, and later
semantic-fidelity evaluation all depend on preserving that distinction.

### 3. Structured output closes shape, not meaning

- OpenAI Structured Outputs can constrain output to a supplied JSON Schema, but
  the official limitations state that values can still be wrong; refusal and
  output truncation also need explicit handling. [OpenAI Structured Outputs limitations](https://openai.com/index/introducing-structured-outputs-in-the-api/#limitations-and-restrictions)
- Anthropic recommends prompt chaining only when a task can be cleanly decomposed
  into fixed subtasks and the latency-for-accuracy trade is worthwhile.
  [Anthropic prompt chaining](https://www.anthropic.com/engineering/building-effective-agents)

**Inference:** schema validation can prove protocol version, closed members,
bounds, and reference integrity. It cannot prove that a correction preserves
intent, that a selected intent is right, or that an ambiguity list is complete.
Those remain model claims subject to deterministic policy and empirical tests.

### 4. Context is necessary for references, but it must be bounded

- CANARD formalizes conversational rewriting as using conversation history to
  convert a context-dependent question into a self-contained question with the
  same answer; its motivating cases include coreference and ellipsis.
  [Elgohary et al., 2019](https://aclanthology.org/D19-1605/)

**Inference:** tasks such as "continue that analysis" cannot be safely understood
from the current string alone. The pre-stage may receive a deterministic,
read-only continuity summary containing only eligible task references. It must
not receive unrestricted Session history. If the bounded context cannot resolve
the reference, the proposal must report ambiguity rather than invent continuity.

### 5. Clarification should be based on consequence, not confidence alone

- The OpenAI Model Spec recommends weighing the cost of an incorrect assumption
  against the cost of clarification. It favors stated assumptions for low-cost
  ambiguity and clarification when a wrong assumption is too costly, the task is
  too ambiguous, or side effects may be irreversible. [OpenAI Model Spec: uncertainty and clarification](https://model-spec.openai.com/2025-10-27)

**Inference:** a scalar model confidence is not an admission rule. Workspace
should classify materiality deterministically: ambiguity is material when
plausible readings change the investigation subject, Case, actor/purpose,
authorization/disclosure, time or source boundary, requested effect, or success
criteria.

## Recommended non-normative design

### Scope of the pre-stage

The pre-stage may propose only:

- minimal spelling, punctuation, language, and grammar normalization;
- a closed task-intent and requested-outcome classification;
- anchored corrections and their original spans;
- unresolved references and plausible interpretations;
- material versus bounded ambiguity evidence;
- a concise normalized reading used alongside the original, never in its place.

It should not propose Query Candidates, Resource Candidates, capability needs,
tool choice, retrieval scope, Working Set operations, investigation subplans,
provider selection, credentials, retry, or Case effects. Those decisions belong
to the formal Investigation Agent Run and its deterministic Workspace admission
seams. This narrowing removes the most important conceptual overlap with a
planning Agent.

### Suggested flow

```text
Original User Task (immutable)
  -> deterministic pre-scan and protected-literal inventory
  -> one Task Understanding model invocation
     - no tools
     - no continuation or retry loop
     - closed structured proposal
  -> deterministic Task Understanding Gate
     -> admit as-is
     -> admit with bounded normalization/assumptions
     -> clarification_required
     -> raw-task fallback or failure
  -> atomic admission record in the existing leased Workspace Session
  -> first Pi Investigation Agent Run provider request
```

"No Session" should mean no additional planner Session. After admission, the
unchanged task and admitted record should be committed to the already leased
Workspace Session before the first Investigation provider request. The exact
atomic mapping belongs to the reopened TQ/PNW contracts.

### Avoiding semantic drift

1. Detect paths, URLs, hashes, IP addresses, domains, CVEs, versions, code,
   quoted text, OpenCTI-visible labels, and other CTI literals deterministically;
   mark them protected unless a trusted resolver says otherwise.
2. Require every correction and interpretation to cite exact original spans or
   one eligible continuity reference.
3. Prefer minimal edits; do not allow free replacement of the full task.
4. Preserve multiple plausible readings when deterministic evidence cannot choose.
5. Never let normalized text independently authorize context selection,
   retrieval, disclosure, capability activation, or effects.
6. Give the Investigation model the original and the admitted interpretation so
   it can detect tension rather than inheriting a hidden rewrite.

### Deterministic decisions

The gate may accept only when the schema, protocol, bounds, source anchors,
protected literals, and trusted basis validate. A bounded spelling or grammar
repair may be admitted when it does not change subject, scope, authority,
requested outcome, or exact CTI literals.

It should require clarification when plausible readings materially change any of
those fields. It should reject the model output or use an explicitly limited
raw-task fallback on malformed schema, unsupported members, refusal, truncation,
timeout, cancellation, missing anchors, protected-literal mutation, or changed
admission basis. Unsupported or effectful scope is a policy denial, not something
the model may repair into authorization.

### One call versus two

Use one call in v1. Correction, intent classification, and ambiguity detection
share the same original evidence, and one result avoids a second derived-text
handoff, extra latency, and disagreement between stages. Split into a fixed
two-call prompt chain only if representative evaluation shows a material fidelity
gain that exceeds its latency/cost and added failure surface. Never introduce an
evaluator-optimizer loop for this stage.

## Pi seam disposition

The provider-backed Adapter should reuse the configured `packages/ai` Models,
Provider, authentication, cancellation, and prepared-invocation implementation;
it must not implement a provider client. `Models.prepareSimple(...)` is the
current source-level fit for a no-Agent-loop call.

However, starting it directly would bypass the still-unimplemented generic PNW
Provider Dispatch proof. The reopened PNW design should factor the A3.1/A3.2
prepared-invocation transaction into one Pi-owned internal dispatcher usable by:

1. the long-lived Harness for Investigation Agent requests; and
2. a bounded one-shot Task Understanding invocation frontend.

Workspace should expose only a small `TaskUnderstandingInvocationPort`; it should
never receive a prepared secret-bearing request or call `start()` itself. Both
frontends should share Pi's model/provider/auth selection, pre-dispatch proof,
attempt identity, cancellation, telemetry, and acknowledgement-unknown semantics.
The one-shot frontend adds no transcript, tool dispatcher, compaction, branch,
queue, or autonomous retry state. This avoids both a second Agent lifecycle and a
second provider transaction.

Until that seam is accepted and implemented, production Task Understanding is
gated. Direct `completeSimple()` is suitable for a deterministic fake or an
explicit prototype only; it is not integrated provider-proof acceptance.

## Effect on the first Investigation Agent Run

If admission succeeds, the first Investigation model context should contain:

1. the immutable Original User Task;
2. the canonical admitted Task Context, including explicit assumptions,
   uncertainties, and exclusions;
3. the current authorized Case Orientation, later Case Projection;
4. only Session history that passes actor/purpose, branch, task-continuity, and
   current Context Generation policy;
5. a trusted Workspace capability snapshot selected by deterministic code; and
6. only tools admitted by that capability snapshot.

There is no Task-Understanding-created Query Candidate or Working Set. A new task
starts with an empty Working Set unless the formal Workspace contract explicitly
continues and revalidates an existing task-bound set. The Investigation Agent may
later suggest Query Candidates, retrieval candidates, or tool calls, but each
remains subject to its owning deterministic Workspace admission boundary.

If admission requires clarification, no Investigation Agent Run starts. The
Workspace Turn terminates with deterministic actor-safe questions.

## Evaluation and acceptance evidence required

Before selecting a small model, build a CTI-specific golden and adversarial set
covering at least:

- ordinary typos and awkward multilingual phrasing;
- CVE, ATT&CK, malware, campaign, actor, hash, URL/domain/IP, version, and code
  literal preservation;
- ambiguous aliases and homonyms;
- pronouns, ellipsis, and valid/invalid continuation history;
- time/source/scope ambiguity;
- analysis-versus-change/publication ambiguity;
- injection attempts that request tools, credentials, authorization, or retries;
- refusal, malformed output, truncation, timeout, cancellation, and late result;
- identical inputs under model/prompt/schema version change.

Measure exact protected-literal preservation, intent accuracy, material-ambiguity
recall, unnecessary-clarification rate, semantic-equivalence judgments, raw-task
fallback safety, latency, tokens, and cost. Compare at least deterministic-only,
one small-model call, and one larger-model baseline. A model-size preference is
not acceptance evidence.

## Design disposition

Adopt as the candidate direction for the next Workspace design session:

1. Task Understanding occurs before the formal Pi Investigation Agent Run.
2. It is one bounded, no-tool model workflow stage, not an Agent or planner.
3. Original User Task is immutable; normalization is a provenance-bound proposal.
4. The stage owns normalization, intent, and ambiguity only. Query Candidates and
   capability/investigation planning move into the formal Agent Run.
5. Deterministic Workspace code alone admits, limits, clarifies, falls back, or
   rejects; structured output is not semantic proof.
6. V1 uses one call. A fixed second call requires measured benefit and a new
   acceptance case.
7. No planner Harness or Session is created. Admitted records later commit into
   the existing leased Workspace Session before Investigation disclosure.
8. Pi must provide one shared prepared-invocation/provider-dispatch implementation
   for the one-shot stage and Harness requests; Workspace must not create a hidden
   provider lifecycle.
9. The current TQ and PNW same-Agent-Run/tool-call design must be explicitly
   superseded before implementation.

This disposition authorizes no code, provider call, normative contract change,
Query Candidate implementation, Working Set work, or investigation-tool design.
