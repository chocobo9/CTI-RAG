# Agentic RAG Engineering Glossary

This is the working vocabulary for learning CTI-RAG's Agentic RAG architecture. Definitions are intentionally project-facing: the goal is to read and evaluate this codebase.

> Scope note: this file describes the current code-reading/learning vocabulary.
> The canonical CTI investigator domain language is `docs/CONTEXT.md`, and the
> canonical target behavior and architecture are defined by
> `docs/architecture/CTI_INVESTIGATOR_TARGET_DESIGN.md`. Where they differ, this
> file is evidence about the current implementation, not target product truth.

## System Shape

**Agentic RAG**:
RAG where the system can plan, call tools, inspect evidence gaps, gather more evidence, and then synthesize an answer inside runtime guardrails.
_Avoid_: a fixed `rewrite -> retrieve -> generate` workflow.

**Agent loop**:
The minimal repeated mechanism that calls a model, validates and executes proposed tools, returns observations, and calls the model again until the run terminates. It does not by itself own CTI evidence authority, domain sufficiency policy, attribution semantics, or product session behavior.
_Avoid_: runtime harness, complete Agentic RAG framework.

**Runtime harness**:
The live control layer around the model: query understanding, path selection, tool validation/execution, state updates, budgets, stop policy, trace metadata, and final assembly.
_Avoid_: retrieval pipeline, prompt only.

**Eval harness**:
The offline or online measurement layer that tests retrieval, gathered evidence, answer quality, faithfulness, citations, cost, latency, and regressions.
_Avoid_: runtime judge.

**Control plane**:
The code that decides what may happen next: routing, validation, budgets, stop reasons, retries, and trace events.
_Avoid_: data plane.

**Data plane**:
The code and stores that provide evidence: corpus, chunks, vector/BM25 indexes, graph facts, fact store, and retrieval results.
_Avoid_: control plane.

## Runtime Entry And Routing

**Runtime query understanding**:
The first runtime step that turns the user question plus history into a standalone task, retrieval queries, entities, constraints, and an optional decomposition proposal.
_Avoid_: query rewrite alone.

**Retrieval query**:
A search hint for vector, keyword, or hybrid retrieval.
_Avoid_: supervisor branch.

**Decomposition proposal**:
An advisory plan that may contain independent worker branches for a compound task.
_Avoid_: route decision.

**Supervisor admission**:
The deterministic runtime decision that accepts or rejects a proposed branch plan for multi-agent execution.
In CTI-RAG production, this belongs to `answer()` / the runtime harness, not to the supervisor loop itself.
_Avoid_: letting retrieval subqueries become workers.

**Single-agent path**:
The direct gather, sufficiency, synthesize path used for simple, fallback, unclear, or dependent questions.
_Avoid_: baseline-only path.

**Supervisor path**:
The multi-agent path where validated independent branches gather evidence separately and a Composer produces one final answer.
Production path means a validated branch plan has already been admitted; legacy autonomous supervisor mode is for debug, eval, or manual baselines.
_Avoid_: supervisor does everything.

**Validated plan path**:
The production supervisor entrypoint where the runtime has already admitted a branch plan and the supervisor only coordinates its execution.
_Avoid_: supervisor decides from scratch whether the original query should be multi-agent.

**Legacy autonomous supervisor**:
A retained supervisor mode for debug, eval, or manual baselines where the supervisor loop may plan more autonomously.
_Avoid_: production default path.

## State And Tool Boundary

**RuntimeDeps**:
Reusable dependencies and provider policy shared by runtime paths: settings, retrieval, fact store, models, judge, generator, and composer.
_Avoid_: per-run reasoning state.

**Runtime state**:
Per-run control variables such as iteration count, tokens, new evidence, sufficiency verdict, open categories, stop reason, observations, and events.
_Avoid_: long-term memory.

**Evidence ledger**:
The per-run structured side channel holding full chunks, facts, graph outlines, action history, conflicts, and the citable ID set.
_Avoid_: transcript text as evidence authority.

**Per-run evidence authority**:
The rule that final synthesis and citation validation may rely only on evidence collected into the current run's ledger, not on the global corpus or model memory in the abstract.
_Avoid_: "the knowledge base contains it, so this answer may cite it."

**External evidence acquisition**:
The umbrella capability for obtaining evidence from an allowed source outside the currently indexed CTI corpus. Scheduled refresh, user-directed source acquisition, and gap-driven lookup have different lifecycle and write semantics and must not share one undifferentiated tool path.
_Avoid_: treating open-web text as trusted context, one generic web-search tool.

**Scheduled source refresh**:
A deterministic recurring ingestion process for a source that has already been admitted into the system. It updates source coverage under the source's existing collection, normalization, provenance, and validation contract; it is not an Agent loop decision.
_Avoid_: autonomous investigation, gap-driven lookup.

**Source acquisition job**:
An explicit bounded job, usually initiated by a user, that gathers a newly requested source, normalizes it, evaluates fusion candidates, and proposes or performs governed durable writes. An Agent may assist with the job, but the job owns checkpoints, validation, and write policy.
_Avoid_: unrestricted Agent browsing, one-turn tool call.

**Gap-driven source lookup**:
A runtime lookup triggered by a declared evidence gap during an investigation. Results enter the per-run Evidence Ledger with provenance and are temporary by default; they do not enter the durable corpus merely because they improved the answer.
_Avoid_: scheduled ingestion, automatic corpus mutation.

**Evidence promotion**:
The governed transition from useful per-run external evidence into the durable CTI corpus after source, provenance, duplication, schema, and review requirements are satisfied.
_Avoid_: caching a tool result as ingestion.

**Action proposal**:
A model-proposed tool call before the runtime validates it.
_Avoid_: executed action.

**Tool boundary**:
The trust boundary where a probabilistic model proposal is validated, admitted, executed or rejected, and converted into a structured runtime observation.
_Avoid_: provider tool-calling protocol only.

**Tool validation**:
Code-level checking of tool name, required args, allowed args, arg types, budgets, deadlines, and duplicate calls.
_Avoid_: prompt instruction.

**Tool admission**:
The runtime policy decision that a valid tool proposal is allowed to execute under the current path, budget, deadline, and suppression rules.
_Avoid_: argument schema validation.

**Observation**:
The structured result of a tool boundary outcome, including status, result summary, ledger delta, structured payload, and model-visible content.
_Avoid_: raw tool output only.

**Observation status**:
The typed outcome of a tool boundary: `ok` for successful execution, `invalid` for bad proposals, `rejected` for runtime policy refusal, `error` for execution failures, and `no_action` when the model did not propose a tool.
_Avoid_: one generic failure flag.

**RuntimeEvent**:
A compact event envelope derived from an observation for trace, counters, and debugging.
_Avoid_: full evidence store.

**Ledger delta**:
The structured change to chunks, facts, outlines, or actions caused by applying one observation.
_Avoid_: parsing display text to infer state changes.

**Model-visible content**:
The text rendered back to the model or provider protocol from a runtime observation.
_Avoid_: system truth source.

**Setup progress**:
Progress that prepares later evidence gathering, such as resolving an entity or inspecting an outline, without adding citable chunks or facts.
_Avoid_: treating zero new evidence as always no progress.

**Reducer**:
Deterministic logic that merges an observation into runtime state and the evidence ledger.
_Avoid_: model memory update.

**Working-set context**:
A fresh per-turn prompt view rendered from state and ledger so the model sees what is done and what remains.
_Avoid_: carrying the entire old transcript as durable state.

**Stop policy**:
Rules deciding whether to continue gathering or synthesize, based on sufficiency, progress, budgets, tool count, wall-clock time, and provider errors.
_Avoid_: model decides forever.

## Evidence And Grounding

**Provenance**:
Where evidence came from: source, chunk ID, fact ID, document metadata, supports edges, and credibility signals.
_Avoid_: vague citation.

**Citation**:
An answer-visible ID reference to a chunk or fact.
_Avoid_: proof of truth.

**Citation validation**:
The deterministic intersection of model-cited IDs with the ledger's real citable IDs.
_Avoid_: LLM judging whether citations look plausible.

**Grounding**:
The answer is generated from collected evidence rather than unsupported model memory.
_Avoid_: citation exists.

**Faithfulness**:
Each answer claim is actually supported by the cited or available evidence.
_Avoid_: answer seems correct.

**Sufficiency**:
The gathered evidence covers enough of the user question to answer responsibly.
_Avoid_: answer is grounded but incomplete.

## Supervisor

**Branch plan**:
A validated set of independent sub-questions suitable for parallel evidence gathering.
_Avoid_: arbitrary subqueries.

**Worker**:
A gather-only agent assigned one branch. It collects evidence into a branch-local ledger and returns a branch report.
_Avoid_: mini final-answer agent.

**Supervisor**:
The coordinator for admitted multi-branch work. It dispatches gather-only workers, monitors branch reports, and triggers composition.
_Avoid_: production route decider, retriever, final-answer writer.

**Branch report**:
A compact coordination and composition record: status, sub-question, evidence summary, citations, gaps, errors, counts, and telemetry.
_Avoid_: full ledger dump.

**Branch-local ledger**:
The per-worker evidence ledger. It remains evidence authority for that branch until merged.
_Avoid_: shared mutable supervisor scratchpad.

**Ledger merge**:
The deterministic union of branch ledgers into one master ledger for final citation validation.
_Avoid_: prose summary merge.

**Composer**:
The no-tool synthesizer that writes one final answer from branch reports and accepted evidence context.
_Avoid_: retriever, supervisor, citation validator.

## Evaluation

**Retrieval eval**:
Measures whether retrieval returns expected chunks, sources, or ATT&CK IDs, commonly via Hit@K, MRR, precision, recall, or F1.
_Avoid_: answer eval.

**Gathered evidence eval**:
Measures what the agent actually collected after planning and tool use, not what the retriever could have returned in isolation.
_Avoid_: retrieval-only score.

**Answer eval**:
Measures final answer correctness, completeness, readability, and task satisfaction.
_Avoid_: faithfulness eval only.

**Faithfulness eval**:
Measures whether the answer is supported by retrieved or ledger evidence.
_Avoid_: correctness in the external world.

**Citation eval**:
Measures whether citations exist, are valid ledger IDs, and are relevant to the claims they support.
_Avoid_: citation ID existence only.

**Regression test**:
A repeatable test that protects behavior from drifting during refactors.
_Avoid_: one-off demo.

**Golden set**:
A fixed set of questions and expected evidence or answers used to compare system changes.
_Avoid_: ad hoc manual prompt list.

**Runtime contract**:
The observable behavior the runtime promises to callers and maintainers: production entrypoint, output shape, trace fields, fallback reasons, stop reasons, citation behavior, and telemetry.
_Avoid_: implementation detail only.

**Architecture review**:
An evaluation of design intent, runtime contract, code evidence, test/eval evidence, and residual risks.
_Avoid_: code style review only.

## Cross-Cutting Distinctions

**State vs Memory**:
State is the current run's control variables; memory is an information source selected into context.
_Avoid_: using memory to mean every stored value.

**Context vs Prompt**:
Context is material selected for a model call; prompt is the final serialized input/messages.
_Avoid_: calling all inputs prompts.

**Action vs Observation**:
Action is what the system attempts; observation is what came back from the attempt.
_Avoid_: treating proposed tool calls as completed work.

**Plan vs Trace**:
Plan is the intended route; trace is the actual recorded execution.
_Avoid_: trusting the plan as evidence.

**Ledger vs Trace**:
Ledger is the evidence authority; trace is the execution explanation and observability record.
_Avoid_: storing full evidence in trace or treating event logs as citable proof.

**Control Plane vs Data Plane**:
The control plane decides what may happen next; the data plane provides evidence content and retrieval results.
_Avoid_: mixing runtime policy with evidence storage.

**Deterministic guard vs LLM judge**:
A deterministic guard is code-enforced; an LLM judge is probabilistic evaluation or routing advice.
_Avoid_: using a judge where code can decide.

**Runtime object responsibility boundary**:
The distinction between runtime capabilities, per-run process state, evidence authority, and tool-boundary results. In this workspace, Deps provide capabilities, State records run progress, Ledger holds evidence authority, and Observation records what happened at a tool boundary.
_Avoid_: storing every run-related value in one generic context object.
