# Tool Registration and Delivery Research

Status: non-normative primary-source research.

Research date: 2026-07-22.

This note examines what an industrial Tool design normally needs between an
accepted product workflow and a running Agent loop. It uses current official
Pydantic AI documentation as the main additional reference, with the official
OpenAI Agents SDK and Anthropic documentation already recorded in
[Agent Tool Industrial Design Research](agent-tool-industrial-design-research-2026-07-22.md).
It compares those sources with the current CTI-RAG design. It neither defines
a unified CTI schema nor introduces a Tool Module, registry service, database,
MCP Module, capability count, or implementation work.

## 1. Design disposition

The user's “Pandetic” is understood as **Pydantic AI**. It is a Python Agent
framework, not a shared Tool-registration platform. Its `Toolset` is an
in-process grouping/composition abstraction. It does not provide a reason to
replace Pi or to add a CTI Tool registry.

The useful common industrial pattern is four separate concerns:

1. a **registered implementation** that a trusted host can execute;
2. a **per-run/per-step callable projection** made visible to the model;
3. a **trusted execution binding** that supplies host-known identity,
   authorization, and owner inputs; and
4. a **model-visible result projection** that is smaller than the internal
   operation outcome and audit material.

Pydantic AI, OpenAI Agents SDK, Anthropic's Tool loop, and the current Pi
runtime all support variants of this separation. The existing CTI-RAG
Workspace Capability design already supplies the product-level meaning of
per-run availability and trusted admission. A general “Tool platform” would
duplicate that responsibility before a real shared requirement exists.

## 2. Official facts: Pydantic AI

### 2.1 Registration is not current availability

Pydantic AI can register a function through decorators, a direct `tools`
argument, or a `Tool` object. A Tool that needs host context receives a
`RunContext`; a plain Tool does not. `Toolset` is a reusable collection that
may be composed, swapped in tests, filtered, modified, or have its execution
wrapped. All registered tools and toolsets are combined before the model-facing
tool list is built.

Sources:

- [Function Tools](https://pydantic.dev/docs/ai/tools-toolsets/tools/)
- [Toolsets](https://pydantic.dev/docs/ai/tools-toolsets/toolsets/)

For each step, a `prepare` function may return a modified Tool definition or
`None`, which hides that Tool for the step. An agent-wide `prepare_tools`
function can filter or modify the whole definition list using `RunContext`.
`tool_choice` separately controls whether the model may choose automatically,
must use a Tool, may use only named Tools, or may use none.

Sources:

- [Advanced Tool Features — dynamic Tools and Tool choice](https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/)

### 2.2 Trusted context is separate from model arguments

Pydantic AI passes host dependencies through `RunContext` to tools, system
prompts, and output validators. Function parameters other than `RunContext`
become model-call parameters. This means an application can make an access
principal, Case binding, authorization decision, service client, or credential
reference available to the trusted handler without asking the model to provide
those values.

Sources:

- [Dependencies](https://pydantic.dev/docs/ai/core-concepts/dependencies/)
- [Function Tools — `RunContext`](https://pydantic.dev/docs/ai/tools-toolsets/tools/)

### 2.3 Tool input and output contracts

Pydantic AI normally derives a JSON Schema from typed function parameters and
their docstrings. It can require parameter descriptions. A custom
`Tool.from_schema` accepts a manually supplied name, description, and JSON
Schema, but the documentation explicitly warns that its tool arguments are not
Pydantic-validated before being passed as keyword arguments.

Tools may return JSON-serializable or supported multimodal values. Its
`ToolReturn` separates the value sent to the model from application-only
metadata. The latter is useful for logging and downstream processing but is
not sent to the LLM.

Sources:

- [Function Tools — schema generation](https://pydantic.dev/docs/ai/tools-toolsets/tools/)
- [Advanced Tool Features — custom schemas and returns](https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/)

### 2.4 Reliability controls are distinct decisions

Pydantic AI distinguishes a request for a corrected model call (`ModelRetry`)
from a completed-but-unsuccessful Tool result (`ToolFailed`). It supports
argument validation before execution, custom validators, Tool and run retry
limits, Tool timeouts, parallel calls, and sequential execution. Its
documentation treats parallelism and the retry limit as configuration rather
than evidence that a particular business operation is safe to repeat or run
concurrently.

`ApprovalRequiredToolset` can require a decision for each call, using the run
context, Tool definition, and validated arguments. Toolsets also have per-run
and per-step lifecycle hooks.

Sources:

- [Advanced Tool Features — execution, retries, failures and concurrency](https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/)
- [Toolsets — approval and lifecycle](https://pydantic.dev/docs/ai/tools-toolsets/toolsets/)

### 2.5 Large catalogs, testing, and observability

Pydantic AI supports deferred Tool loading and Tool search. Its documentation
warns that model selection quality can deteriorate when roughly 30–50 Tools
are visible, and supports provider-native discovery for OpenAI/Anthropic where
available with a local fallback.

The official test examples use deterministic test models to inspect the exact
Tool definitions sent in a run, without a live LLM. Its instrumentation
capability emits OpenTelemetry spans for Agent runs, model requests, and Tool
executions; content capture is configurable.

Sources:

- [Advanced Tool Features — Tool Search](https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/)
- [Testing](https://pydantic.dev/docs/ai/guides/testing/)
- [Instrumentation](https://pydantic.dev/docs/ai/capabilities/instrumentation/)

### 2.6 MCP position

Pydantic AI describes MCP as a standard protocol for connecting an AI
application to external tools/services. An agent may consume MCP-server tools,
or an agent may be exposed within an MCP server. This is an interoperability
transport choice. It does not make MCP a domain owner, a business-operation
contract, or a replacement for host authorization and result validation.

Source: [Pydantic AI MCP overview](https://pydantic.dev/docs/ai/mcp/overview/).

## 3. Comparison with OpenAI and Anthropic facts

| Concern | Pydantic AI | OpenAI / Anthropic | Stable lesson |
| --- | --- | --- | --- |
| Definition | typed function/docstring or explicit definition | name, description, input JSON Schema | The model needs a precise call declaration. |
| Registration vs exposure | Toolsets plus per-step `prepare` | supplied/allowed/deferred Tool surface | Registration does not mean callable now. |
| Hidden host data | `RunContext.deps` | application/SDK context and handler closure | Trusted bindings stay outside model-filled arguments. |
| Input validity | generated validation; manual schema has caveat | strict schema options plus host validation | Shape validation is necessary but not authorization. |
| Result separation | `ToolReturn` value vs private metadata | call-correlated model result; host-side state remains private | The model result is not the owner outcome or audit record. |
| Failure | correction request vs failed Tool outcome | error result and continued host loop | Model continuation is not retry permission. |
| Approval / guardrails | Toolset-level approval and hooks | Agents SDK approvals/guards; host-controlled manual loops | Approval and validation are explicit host stages. |
| Catalog scale | Toolset composition, deferred search | deferred Tools/tool search | Keep the ordinary visible surface task-relevant. |
| MCP | external Tool transport | external Tool/service transport | MCP is optional Adapter technology. |

Official comparison sources:

- [OpenAI Agents SDK — Tools](https://openai.github.io/openai-agents-python/tools/)
- [OpenAI Agents SDK — Guardrails](https://openai.github.io/openai-agents-python/guardrails/)
- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Claude Tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Claude Tool Runner](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)

## 4. Current local CTI-RAG facts

### 4.1 Existing ownership and seams

The current design already separates the relevant concerns:

- Pi owns the generic model/Tool protocol and loop.
- Workspace owns the trusted per-Run `Workspace Capability` view and the
  admission of a proposed capability use under Access Principal, Case, Use
  Purpose, task, dependency, qualification, and budget basis.
- I&E and Case Management own their respective business operations and their
  domain outcome/receipt/version semantics.
- Workspace projects a bounded model-visible Tool result and separately
  controls Working Set and later disclosure.

This is recorded in the current domain language and the Tool/capability audit;
the active I&E core scope is still only exact OpenCTI Resource retrieval.
I&E does not yet have an implementation package. Product Tool count and
decomposition remain intentionally unfixed.

Sources:

- [Agent Workspace context](../agent-workspace/CONTEXT.md)
- [I&E context](../intelligence-evidence/CONTEXT.md)
- [I&E Platform Design](../intelligence-evidence/intelligence-evidence-platform-design.md)
- [Tool Capability Architecture Audit](tool-capability-architecture-audit-2026-07-22.md)

### 4.2 Pi already supplies the generic runtime registry

Pi extensions use `pi.registerTool()` to register a Tool, and active Tools can
be changed independently of that registration. Pi sends active provider-facing
descriptions and input schemas to the model, validates calls, executes the
registered handler, and returns a call-correlated result. It also has generic
pre/post Tool hooks, error observations, and parallel-execution support.

These are generic runtime features. They do not deliver the CTI product
workflow, capability admission, owner operation, authoritative receipt, or
model-result qualification.

Sources:

- [Agent Tool Industrial Design Research — current Pi facts](agent-tool-industrial-design-research-2026-07-22.md)
- [Tool Capability Architecture Audit — Pi protocol and CTI gaps](tool-capability-architecture-audit-2026-07-22.md)

### 4.3 What remains incomplete

The following are not complete product behavior merely because their
architecture exists:

1. The first end-to-end CTI capability has no implemented Workspace-to-I&E
   vertical.
2. No concrete accepted model-visible descriptor currently closes one CTI
   Tool's description, input contract, result projection, failure vocabulary,
   and save-point behavior together.
3. The I&E exact-retrieval core is ready for its isolated implementation cycle
   but has not started; Workspace consumption and provider disclosure remain
   gated.
4. There is no accepted public-web, PDF/OCR, bounded CTI search, enrichment,
   or Case-write Tool workflow.
5. Runtime registry/configuration and complete finalized CTI Tool-result
   transaction handling remain later Pi-native Workspace work.

This is a delivery gap list, not evidence for an independent Tool Module.

Sources:

- [Agent Workspace Progress](../agent-workspace/PROGRESS.md)
- [I&E Progress](../intelligence-evidence/PROGRESS.md)
- [Tool Capability Architecture Audit — gaps](tool-capability-architecture-audit-2026-07-22.md)

## 5. Deductions for CTI-RAG

### 5.1 There is no one “Tool schema”

The question of a unified schema contains several different contracts:

| Contract | Owner | Purpose |
| --- | --- | --- |
| Provider Tool-call input | Pi/provider Adapter | Shape of model-proposed arguments. |
| Activated capability descriptor | Workspace | What is callable in this Run and on what trusted policy basis. |
| Owner-operation request/outcome | I&E, Case Management, or another owner | Business validity, version, provenance, failures, and receipts. |
| Model-visible result projection | Workspace | The safe, bounded observation returned to the next model turn. |

These contracts must bind together for one workflow, but they should not be
collapsed into a universal cross-owner record. Pydantic AI's separation between
Tool input and private `ToolReturn.metadata` reinforces the existing
CTI-RAG distinction between a model-visible Tool result and protected owner or
audit material.

### 5.2 “Register” needs two layers, not a new platform

An industrial system normally needs an internal implementation registry so the
host can route a model call, and a current callable set so the model sees only
the allowed subset. Pi already has the former at its runtime layer. The current
Workspace Capability snapshot is the designed product-level answer to the
latter.

Therefore, Pydantic AI is not a candidate registry service for CTI-RAG. Its
Toolset pattern supports this direction conceptually: compose implementations
locally, then expose only a context-qualified subset. CTI-RAG should not adopt
Pydantic AI itself because this repository's execution spine is TypeScript/Pi.

### 5.3 Description is part of a capability's delivery package

The model needs a description to make the proposal decision. It is not only
documentation. It should be developed together with one capability's input
contract and bounded result meaning, after the business workflow is accepted.
It must not be treated as policy: the same capability still needs deterministic
Workspace admission and owner validation.

### 5.4 Runtime mechanics are insufficient for CTI truth and authorization

Input schema validation, Tool approval, timeout, retry, correlation IDs,
telemetry, and parallelism are generic runtime mechanics. They cannot verify
that a Resource Version, Case Revision, Use Purpose, provenance, resource
status, or disclosure decision is valid. That validation remains with the
current CTI owners and their explicit boundaries.

### 5.5 MCP remains optional

MCP becomes relevant only if a chosen external service actually needs an
interoperable Tool transport. It can be hidden behind an Adapter, subject to
the same Workspace capability admission and owner-result qualification as a
direct API Adapter. It is neither the Tool registry nor a justification to
create one.

## 6. Research recommendations

The following are recommendations, not accepted contract changes.

1. Treat the first accepted CTI workflow as one **vertical capability
   package**: business owner operation, model intent, description, model-call
   input, hidden trusted bindings, outcome qualification, model-result
   projection, retry/timeout/approval/concurrency policy, and save-point
   behavior should be reviewed together.
2. Use a short authoring checklist, rather than a generic Tool SDK, when that
   workflow is selected:

   - What user/business intent does it serve, and when should it not be used?
   - Which owner operation is it invoking?
   - Which model-proposed inputs are necessary, and which facts must remain
     trusted Workspace bindings?
   - What conditions admit, deny, defer, or require approval for a call?
   - Which outcomes can be returned to the model, which remain protected, and
     which must not mutate Case or Working Set state?
   - Which failures are observed, retryable, terminal, or effect-uncertain?
   - Is parallel execution safe according to the owner operation rather than
     the Agent runtime default?
   - What deterministic fixtures prove availability, rejection, owner-result
     validation, safe result projection, and absence of state change on failure?

3. Keep Access Principal, credential reference, Case, Use Purpose, resource or
   revision bindings, budgets, and idempotency facts out of model-fillable
   arguments. The Pydantic AI `RunContext` pattern is an external precedent,
   not an implementation prescription.
4. Use deterministic tests to inspect the active Tool declaration and exercise
   the complete proposed-call-to-owner-outcome-to-projection path. Emit
   actor-safe, content-minimized operational telemetry; do not make generic
   tracing a substitute for a CTI receipt.
5. Reconsider deferred Tool discovery only if a measured, accepted product
   capability set becomes too large to keep the active model-facing set clear.
   Do not pre-build a broad catalog or Tool search mechanism.

## 7. Choices deliberately unresolved

This research does not decide:

- the first product Tool's name, description, or number of Tool shapes;
- whether exact retrieval becomes one model-visible Tool or several projections;
- handwritten versus generated provider input schemas;
- exact approval, retry, timeout, parallelism, or context budgets;
- use of MCP for a particular external service;
- a general CTI Tool result schema or a separate Tool database/service; or
- implementation sequence beyond the existing Workspace and I&E gates.

Those choices require an accepted workflow and must be adopted by their
existing normative owners before implementation.

## 8. Source access record

External sources were accessed on 2026-07-22. Only official Pydantic, OpenAI,
and Anthropic documentation was used. Local documents remain authoritative
under [CTI-RAG document precedence](../README.md).

