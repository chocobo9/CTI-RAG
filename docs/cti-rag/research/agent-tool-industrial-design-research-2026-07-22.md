# Agent Tool Industrial Design Research

Status: non-normative primary-source research.

Research date: 2026-07-22.

This note studies the public Tool Use designs of Anthropic/Claude and OpenAI,
including the OpenAI Responses API, OpenAI Agents SDK, and selected Codex
source. It records candidate implications for CTI-RAG, but does not define a
CTI Tool schema, Tool Module, MCP Module, database, product Tool count,
Connector contract, implementation Interface, or delivery scope. It does not
amend any contract, ADR, `CONTEXT.md`, or `PROGRESS.md`.

## 1. Design disposition

Anthropic and OpenAI converge on the same core separation:

1. the host presents a model-visible Tool declaration;
2. the model may emit a structured Tool call;
3. the host, or an explicitly provider-hosted service, executes the operation;
4. the host returns a call-correlated result;
5. the model observes that result in a later reasoning step.

The model does not acquire execution authority merely by producing
schema-valid arguments. JSON Schema constrains the shape of an input. It does
not prove authorization, business validity, provenance, current resource
status, side-effect safety, or truth of the returned content.

This supports the current CTI-RAG direction rather than replacing it:

- Pi remains the generic model-tool loop and provider protocol owner;
- Workspace decides which product capabilities are activated for the current
  task and whether a proposed use is admissible;
- I&E, Case Management, or another existing business owner executes and
  validates its operation; and
- Workspace projects a bounded result into later model context.

No evidence in these industrial designs requires a separate CTI Tool bounded
context. The useful reusable pattern is a host-owned Tool runtime around
owner-specific operations, not a new authority that absorbs those operations.

## 2. Official facts: Anthropic/Claude

### 2.1 Tool declaration

For a user-defined client Tool, Claude's required public definition consists
of:

- `name`;
- `description`; and
- `input_schema`, expressed as JSON Schema.

Anthropic documents `input_examples` as optional. Its current Tool reference
also describes optional definition properties including `strict`,
`defer_loading`, `allowed_callers`, and `cache_control`. These are provider
features, not a universal Tool domain model.

Anthropic places unusual weight on the description. It recommends explaining
what the Tool does, when it should and should not be used, parameter meanings,
and important limitations. It also recommends high-signal results rather than
returning unnecessary fields. The Tool definitions are incorporated into a
special Tool-use system prompt, so their names, descriptions, schemas, and
examples consume context tokens.

Sources:

- [Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [Tool reference](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference)

### 2.2 What decides whether a Tool is called

With the default `tool_choice` of `auto`, Claude decides per turn whether to
call a Tool or answer directly. Anthropic says the decision is influenced by
whether the request maps to the described capability and whether the answer is
already present in context.

Claude exposes four Tool-choice modes:

- `auto`: the model may call a Tool or answer directly;
- `any`: the model must call one of the provided Tools;
- `tool`: the model must call one named Tool; and
- `none`: the model may not call a Tool.

System and user instructions can steer Tool use, but Anthropic distinguishes
that prompting from the deterministic `tool_choice` control. Model and feature
compatibility can constrain forced modes.

Sources:

- [Tool use overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [Define tools — forcing Tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#forcing-tool-use)

### 2.3 Strict input conformance

Setting `strict: true` constrains Claude's Tool name and input to the supported
JSON Schema subset using grammar-constrained sampling. This prevents classes of
syntactic failures such as a missing required field or an incompatible scalar
type.

The documented guarantee is limited to Tool name and input-schema conformance.
It says nothing about whether:

- the caller is authorized;
- the operation should run now;
- the supplied value names an eligible business object;
- the implementation performed the operation correctly; or
- the returned content is current or trustworthy.

Source:

- [Strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)

### 2.4 Execution ownership and the Tool loop

Anthropic distinguishes three execution locations:

1. user-defined client Tools: the application defines and executes them;
2. Anthropic-schema client Tools: Anthropic defines a trained-in schema, but
   the application still executes them; and
3. server Tools: Anthropic executes them.

For a client Tool, Claude emits a `tool_use` block with a unique `id`, `name`,
and schema-conforming `input`. The application executes it and returns a
`tool_result` whose `tool_use_id` correlates with that call. The result may
contain text, image, document, or search-result content and may set
`is_error: true`.

The ordinary client loop continues while the response stop reason is
`tool_use`. The host preserves the assistant Tool-call turn, appends all
corresponding results in the next user message, and invokes the model again.
Tool results must immediately follow their calls; all result blocks must
precede any additional text in that message.

Anthropic explicitly warns that Tool results may contain untrusted external
content and recommends keeping that material in `tool_result` blocks rather
than moving it into system instructions or plain user text.

Sources:

- [How Tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Handle Tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)

### 2.5 Parallel calls

Claude may emit several `tool_use` blocks in one assistant turn. Anthropic does
not prescribe the host's execution order. It explicitly recommends choosing
based on semantics:

- independent read-only operations are normally suitable for parallel
  execution; and
- operations with effects, shared state, or ordering requirements may need
  sequential execution.

The host must return one correlated result for every call, including an error
result for a call intentionally not executed. `disable_parallel_tool_use`
limits a response to at most one call with `auto`, or exactly one with `any` or
forced `tool`.

Source:

- [Parallel Tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use)

### 2.6 Errors, retry, and Tool Runner

The manual protocol represents execution failure with `is_error: true`. The
Claude SDK Tool Runner can automate call execution, message-history
management, type validation, and result return. It catches a Tool exception
and returns a model-visible error result; callers may intercept that result or
take over the loop. The runner supports a `max_iterations` bound.

Anthropic's parallel-call guidance says Claude may reissue a failed dependent
call on a later turn. That is observed model behavior, not a business retry
policy. The host still decides whether execution, retry, or continued looping
is allowed.

Source:

- [Tool Runner](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)

## 3. Official facts: OpenAI Responses and function calling

### 3.1 Function declaration

In the Responses API, a callable function definition contains:

- `type: "function"`;
- `name`;
- `description`;
- `parameters`, expressed as JSON Schema; and
- `strict`.

OpenAI recommends detailed names, descriptions, parameter formats, expected
return meaning, edge cases, and explicit instructions about when and when not
to use a function. It recommends removing arguments already known by
application code, combining functions that are always called in sequence, and
keeping the initially visible function set small. The current guidance gives
fewer than 20 initially available functions as a soft target, not a protocol
limit, and supports namespaces and deferred Tool search for larger surfaces.

Sources:

- [Function calling — defining functions](https://developers.openai.com/api/docs/guides/function-calling#defining-functions)
- [Function calling — best practices](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)

### 3.2 Call selection

OpenAI's `tool_choice` supports:

- `auto`: zero, one, or multiple calls;
- `required`: one or more calls;
- one forced named function;
- `allowed_tools`: an eligible subset of the otherwise supplied Tool set; and
- `none`: no Tool call.

`allowed_tools` is particularly relevant to a host that wants a stable
cacheable registry while changing the subset callable in the current turn.
The provider control is still only call-surface selection. It is not a
substitute for runtime authorization or business admission.

Source:

- [Function calling — Tool choice](https://developers.openai.com/api/docs/guides/function-calling#tool-choice)

### 3.3 Strict input conformance

OpenAI recommends `strict: true`. For strict function calling, every object
must disallow additional properties and every declared property must be
required; optionality is represented with a nullable type. Strict mode uses
Structured Outputs to constrain arguments to the supported schema.

The Responses API may attempt to normalize an omitted strict setting and can
fall back to non-strict behavior when normalization is not possible. This
provider-specific fallback is a reason for the host to bind and verify the
effective Tool descriptor rather than assuming all provider calls used an
identical strictness contract.

As with Claude, strictness covers the model-produced call shape. It does not
validate CTI authorization, current Case/Resource binding, provenance, owner
outcome, or truth.

Source:

- [Function calling — strict mode](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)

### 3.4 Responses call and result correlation

A Responses function call is an output item with:

- `type: "function_call"`;
- a `call_id`;
- `name`; and
- JSON-encoded `arguments`.

The application parses the arguments, routes the named function, executes it,
and supplies a later `function_call_output` item with the same `call_id`.
Reasoning items returned with a reasoning model's Tool-call response must also
be preserved for the continuation.

OpenAI says the `function_call_output.output` is normally a string whose
internal format is chosen by the application, such as JSON, an error code, or
plain text. Image and file results have separate supported forms. Therefore
the base Responses function declaration is an input contract and call
correlation protocol; it is not a universal business output contract.

Source:

- [Function calling — executing calls and formatting results](https://developers.openai.com/api/docs/guides/function-calling#executing-function-calls)

### 3.5 Parallel calls

The model may emit multiple function calls in one turn.
`parallel_tool_calls: false` constrains a turn to zero or one function call.
OpenAI documents provider/model qualifications, including that built-in Tools
do not use this parallel function-calling mechanism.

The API control limits call cardinality. The host still owns the semantic
decision to run a returned batch concurrently, sequentially, partially, or not
at all.

Source:

- [Function calling — parallel function calling](https://developers.openai.com/api/docs/guides/function-calling#parallel-function-calling)

## 4. Official facts: OpenAI Agents SDK

The Agents SDK adds a host runtime above Responses:

- a Python function can be converted into a Tool;
- name and description can come from the function and docstring;
- an input schema is generated from type annotations with Pydantic;
- a custom `FunctionTool` separates `name`, `description`,
  `params_json_schema`, and `on_invoke_tool`;
- enablement may be computed from the current Run context;
- a particular call may require approval before execution;
- optional input and output guardrails surround the handler;
- per-call timeouts may become a model-visible error or fail the Run; and
- handler exceptions may be converted into model-visible errors or re-raised.

The SDK's default Agent behavior runs the model again after a Tool result. It
also supports stopping on a Tool result or using a host function to decide
whether the result is final. It resets a forced Tool choice after a call by
default to reduce infinite Tool-call loops.

The current SDK source includes an optional `output_json_schema` for
programmatic callers and a corresponding output adapter. That is an SDK
capability, not evidence that every Responses function result has a universal
validated output schema.

Sources:

- [OpenAI Agents SDK — Tools](https://openai.github.io/openai-agents-python/tools/)
- [OpenAI Agents SDK — forcing Tool use and Tool-use behavior](https://openai.github.io/openai-agents-python/agents/#forcing-tool-use)
- [Pinned `FunctionTool` source, commit `1e8d506`](https://github.com/openai/openai-agents-python/blob/1e8d506a32ea7b84f3a5a811e101378c0b1bc137/src/agents/tool.py#L2773-L2917)

## 5. Official facts: Codex public source

Codex is a product-specific host built on the same underlying pattern; it is
not merely a collection of JSON schemas.

At the reviewed source revision:

- Codex has a Tool registry mapping names to runtime handlers;
- duplicate registrations are rejected;
- runtime dispatch carries the originating call identity;
- Tool-specific output is converted back to a Responses input item using that
  call identity;
- runtime Tool capability includes whether parallel calls are supported;
- pre- and post-Tool payloads expose call/input/result facts to hooks; and
- the post-Tool path can distinguish the original runtime result from the
  model-visible result.

Codex app-server also exposes an experimental dynamic-Tool protocol. The
client supplies Tool declarations, receives an `item/tool/call` request with a
`callId`, executes it, and returns content items plus success state. This is
additional evidence that Tool declaration, host execution, call lifecycle,
and model-visible result are distinct responsibilities.

These source facts are implementation examples, not APIs CTI-RAG should copy.
The public Codex source changes rapidly, so the links below are pinned to the
reviewed commit.

Sources:

- [Codex Tool registry, commit `44d76c6`](https://github.com/openai/codex/blob/44d76c6a6dd04fa2efc302b906ac8774267a1272/codex-rs/core/src/tools/registry.rs)
- [Codex Tool specification assembly, commit `44d76c6`](https://github.com/openai/codex/blob/44d76c6a6dd04fa2efc302b906ac8774267a1272/codex-rs/core/src/tools/spec.rs)
- [Codex app-server dynamic Tools, commit `44d76c6`](https://github.com/openai/codex/blob/44d76c6a6dd04fa2efc302b906ac8774267a1272/codex-rs/app-server/README.md#dynamic-tool-calls-experimental)

## 6. Current local facts: Pi

This section describes the repository state reviewed on 2026-07-22. It is not
an external industry recommendation.

### 6.1 Default and optional Tools

The Pi coding-agent default Tool set contains four Tools:

- `read`;
- `bash`;
- `edit`; and
- `write`.

The same package also provides `grep`, `find`, and `ls`, but they are not in
the default four-Tool set. Extensions may register additional Tools.

Sources:

- [Built-in Tool assembly](../../../packages/coding-agent/src/core/tools/index.ts)
- [Default system-prompt Tool selection](../../../packages/coding-agent/src/core/system-prompt.ts)

### 6.2 Extension Tool declaration

An extension registers a Tool with `pi.registerTool()`. The documented
declaration includes:

- `name`, `label`, and `description`;
- `parameters`, written as a TypeBox schema;
- `execute`, which receives the call identity, validated parameters, abort
  signal, and optional update callback;
- optional `promptSnippet` and `promptGuidelines`;
- optional argument preparation for compatibility with older persisted calls;
  and
- optional UI renderers.

`promptSnippet` and `promptGuidelines` influence the default system prompt only
while the Tool is active. The Tool description and parameter schema remain the
provider-facing semantic call contract. Pi documentation recommends throwing
on failure rather than returning error text as if execution succeeded.

Sources:

- [Extension custom-Tool documentation](../../../packages/coding-agent/docs/extensions.md)
- [Agent Tool runtime types](../../../packages/agent/src/types.ts)

### 6.3 Activation and deferred loading

Registration and activation are separate. An extension may register a larger
catalog and use `pi.setActiveTools()` to replace the active set. A loader may
activate additional Tools and report their names through `addedToolNames`.

For supported provider/model combinations, Pi can use native deferred Tool
loading and Tool search. Otherwise it sends the complete active Tool list on
the following request. Activation also affects prompt snippets and guidelines,
so changing the active set can change the system-prompt prefix.

Source:

- [Extension dynamic-Tool documentation](../../../packages/coding-agent/docs/extensions.md)

### 6.4 Selection, validation, execution, and observation

Pi does not use a keyword dispatcher to decide when a normal Tool should run.
It sends the active Tool declarations to the selected model provider. Under
the normal automatic provider mode, the model may answer directly or return
one or more structured Tool calls.

Before execution, the agent loop resolves the named Tool and validates the
arguments against its TypeBox schema. A missing Tool, invalid arguments, a
truncated Tool call, or an execution exception becomes a correlated
model-visible error result. A successful execution returns model-visible
`content` plus host/UI-oriented `details`; an `afterToolCall` hook may replace
the projected content, details, error state, or termination hint before the
next model turn observes the result.

The loop supports parallel calls. Completion may occur out of order, while
transcript results remain associated with their source calls. Parallel
capability in the generic runtime does not establish that a CTI owner
operation is semantically safe to run concurrently.

Sources:

- [Agent loop](../../../packages/agent/src/agent-loop.ts)
- [Generic Tool and Tool-result protocol](../../../packages/ai/src/types.ts)
- [Agent Tool runtime types](../../../packages/agent/src/types.ts)
- [OpenAI Responses provider mapping](../../../packages/ai/src/api/openai-responses-shared.ts)
- [Anthropic provider mapping](../../../packages/ai/src/api/anthropic-messages.ts)

### 6.5 What Pi does not decide

Pi's schema and loop do not decide:

- whether a capability is authorized for the current actor, Case, or purpose;
- which business owner may perform the requested operation;
- whether an I&E Resource Version or Case Revision is eligible;
- whether a side effect is admissible;
- whether an owner result is authoritative or current; or
- which subset of a result may enter the CTI model context.

Those remain product responsibilities above the generic agent loop.

## 7. Cross-vendor and Pi comparison

| Concern | Claude | OpenAI | Current Pi | Stable conclusion |
| --- | --- | --- | --- | --- |
| Model-visible definition | name, description, `input_schema`; optional strict/examples/loading controls | function type, name, description, `parameters`, strict; optional namespace/loading controls | name, description, TypeBox parameters mapped to provider schema | Tool declaration is a model interaction contract |
| Automatic trigger | model decides under `auto`, description and context | model decides under `auto`, description and instructions | active declarations are sent to the provider; the model returns a call or answers | Trigger quality depends on semantic descriptions, but host policy remains separate |
| Deterministic selection control | `auto`, `any`, named `tool`, `none` | `auto`, `required`, named function, `allowed_tools`, `none` | active Tool set and provider mapping constrain the surface | Host can constrain the visible/callable surface per turn |
| Strictness | schema-constrained Tool name and input | Structured-Outputs-constrained arguments | host validates arguments before execution; provider strictness varies by mapping | Strict input is not business authorization or outcome validation |
| Call identity | `tool_use.id` / `tool_use_id` | `call_id` / `function_call_output.call_id` | `toolCallId` is carried through execution and result | Every result must bind to one exact call |
| Client execution | application executes and returns `tool_result` | application routes and returns `function_call_output` | registered host implementation executes | The model requests; trusted host code executes |
| Result shape | text/image/document/search-result blocks and `is_error` | application-chosen string/JSON/error text, or supported file/image forms | model-visible content plus host-oriented details and error state | Base protocols do not define CTI business outcomes |
| Parallelism | several calls; host chooses execution order | several calls; host controls cardinality and execution | generic loop supports parallel execution and ordered transcript results | Parallelism is an operation semantic, not a model entitlement |
| Error continuation | error Tool result, then model may recover | error result or host exception; Agent runtime may continue | validation and execution failures are returned for another model observation | Error observation and retry authorization are separate |
| Large Tool sets | deferred loading and Tool search | namespaces, deferred loading, Tool search | active-set replacement plus native deferred loading where supported | Keep the initial callable surface task-relevant |

## 8. CTI-RAG deductions

This section is a deduction from the official facts and current CTI-RAG
design. It is not current contract behavior.

### 8.1 “When to call” has three different answers

The industrial APIs show that Tool triggering is not one decision:

1. **Availability:** trusted host policy decides which capability declarations
   enter the current model context.
2. **Proposal:** under automatic Tool choice, the model uses the task,
   context, name, description, and schema to decide whether to propose a call.
3. **Admission:** trusted host policy decides whether that exact proposed call
   may execute under the current actor, Case, purpose, dependencies, and
   budget.

Only the second decision belongs to the model. A good description improves
proposal quality; it cannot safely implement the first or third decision.

### 8.2 Tool schema and business operation contract are different

The provider schema describes arguments the model is allowed to propose. A
trusted Adapter may then add actor, purpose, Case identity, credential,
Resource version, idempotency identity, and other host-known bindings that the
model should not supply.

The business owner must validate those bound inputs and its result using its
own contract. Provider strict mode cannot establish an I&E Retrieval Receipt,
Resource status, Case Revision, provenance chain, completeness claim, or
write-effect outcome.

### 8.3 Tool result is a new untrusted observation boundary

Both providers return Tool outputs to the model as content. Anthropic
explicitly treats external result content as a prompt-injection boundary.
Therefore a CTI result should not be copied indiscriminately into system
instructions, Case authority, or Working Set state.

The owner outcome, Workspace state change, model-visible Tool result, and
caller-visible final response remain separate products with separate
validators.

### 8.4 Runtime looping is not retry policy

Claude Tool Runner and OpenAI Agents SDK can continue the model loop after an
error. That only creates a new model decision point. Whether another call is
permitted depends on capability status, error class, changed dependencies,
remaining budget, effect uncertainty, and owner policy.

For CTI-RAG, “the model saw an error and tried again” cannot be the sole retry
rule.

### 8.5 Tool inventory should follow accepted workflows

Both vendors advise reducing the initially visible Tool surface and offer
deferred discovery for larger catalogs. This supports the current decision not
to fix the CTI product Tool count prematurely.

It does not prove that related CTI operations should always be combined or
always split. A Tool boundary should follow one understandable model intent,
one admission policy, one owner operation, and one coherent result/failure
contract.

## 9. Research recommendations

These recommendations are non-normative and deliberately stop before a
concrete schema or Interface.

1. Retain the current four-owner composition: Pi protocol/runtime, Workspace
   activation and admission, business-owner execution, Workspace result
   projection.
2. Treat Tool descriptions as semantic routing material. Each should eventually
   state purpose, use/non-use conditions, expected result meaning, and material
   limitations.
3. Prefer strict model-input schemas where the selected provider and schema
   subset support them, while preserving independent host validation.
4. Keep host-known authority and infrastructure facts out of model arguments.
5. Give every call a stable correlation identity through execution, result
   validation, save-point handling, and later observation.
6. Define result qualification per accepted capability rather than inventing
   one universal CTI Tool-output schema.
7. Return only the minimum actor-safe, high-signal result needed for the next
   reasoning step; keep protected diagnostics and owner-internal outcomes out
   of ordinary model context.
8. Allow parallel execution only for capabilities whose owner semantics prove
   independence and read-only safety. Do not infer safety from a provider's
   ability to emit parallel calls.
9. Separate retryable observation, retry admission, and Run termination. Put a
   deterministic bound around repeated Tool/model iterations.
10. Evaluate Tool choice, argument correctness, unauthorized-call rejection,
    owner-result validation, error recovery, result usefulness, context cost,
    and prompt-injection containment as separate properties.

## 10. Product choices not decided by this research

This research does not decide:

- the number or names of CTI product Tools;
- whether one workflow appears as one Tool or several Tool shapes;
- whether Tool schemas are handwritten or generated from TypeScript types;
- which capabilities should initially be visible versus deferred;
- whether public-web acquisition, PDF processing, bounded I&E search, or
  enrichment is the next accepted workflow;
- whether MCP is used behind any Adapter;
- a general CTI Tool-result schema;
- numeric timeout, retry, concurrency, or Tool-call budgets; or
- implementation placement for any still-unowned business capability.

Those choices should follow an accepted CTI workflow and its existing business
owner, not precede it.

## 11. Local design context

The deductions above were checked against the current local documentation:

- [CTI-RAG document authority](../README.md)
- [Context map](../CONTEXT-MAP.md)
- [Agent Workspace language](../agent-workspace/CONTEXT.md)
- [Case Management language](../case-management/CONTEXT.md)
- [I&E language](../intelligence-evidence/CONTEXT.md)
- [Current Tool/capability architecture audit](tool-capability-architecture-audit-2026-07-22.md)

The local design remains authoritative according to the precedence in
`README.md`. External facts become project requirements only after adoption by
the appropriate normative owner.

## 12. Source access record

All external sources were accessed on 2026-07-22. Only official Anthropic,
OpenAI, and first-party GitHub sources were used.

- Anthropic Claude Platform documentation:
  [overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview),
  [how Tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works),
  [define Tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools),
  [handle calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls),
  [parallel calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use),
  [strict Tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use),
  [Tool Runner](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner), and
  [Tool reference](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference).
- OpenAI developer documentation:
  [function calling](https://developers.openai.com/api/docs/guides/function-calling).
- OpenAI Agents SDK documentation:
  [Tools](https://openai.github.io/openai-agents-python/tools/) and
  [Agents](https://openai.github.io/openai-agents-python/agents/).
- OpenAI Agents SDK source at
  [`1e8d506a32ea7b84f3a5a811e101378c0b1bc137`](https://github.com/openai/openai-agents-python/tree/1e8d506a32ea7b84f3a5a811e101378c0b1bc137).
- OpenAI Codex source at
  [`44d76c6a6dd04fa2efc302b906ac8774267a1272`](https://github.com/openai/codex/tree/44d76c6a6dd04fa2efc302b906ac8774267a1272).
