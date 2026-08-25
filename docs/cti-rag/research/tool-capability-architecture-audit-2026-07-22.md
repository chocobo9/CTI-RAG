# CTI-RAG Tool and Capability Architecture Audit

Status: non-normative current-design audit and candidate architecture view.

Audit date: 2026-07-22.

This document does not define a Tool Module, product tool count, tool names,
JSON Schema, MCP server, Connector, parser, database, or implementation
Interface. It does not amend a contract, ADR, `CONTEXT.md`, or `PROGRESS.md`.

## 1. Disposition

CTI-RAG has not ignored tools, but its design is distributed across four
owners:

1. Pi defines the generic model-tool protocol and execution loop.
2. Agent Investigation Workspace qualifies task-specific capabilities and
   decides which model-visible tools are activated.
3. I&E and future Case capabilities own their business operations and outcomes.
4. Workspace qualifies finalized results before they affect the Working Set,
   later context, or public output.

There is no need for an independent cross-cutting Tool owner. The missing
artifact is an architecture view that explains how these owners compose and
where input, output, authority, validation, retry, and context responsibilities
live.

The deletion test for a new Tool Module does not pass. Deleting it would not
remove a coherent business responsibility: generic execution remains Pi,
capability admission remains Workspace, source/retrieval operations remain
I&E, and Case changes remain Case Management. A unified Tool Module would
mostly relay between existing authorities.

## 2. Context clarification

The current accepted Initial Investigation Context is exactly:

1. System Instructions;
2. Original User Task;
3. Additional Task Context;
4. Working Set;
5. layered Case Context;
6. eligible Session History; and
7. activated Tools.

Several useful ideas in the wider context discussion are not currently separate
members of this seven-part contract:

- a user profile has no accepted cross-task owner;
- long-term memory is reconstructed from Case, I&E, Workspace, and Session
  owners rather than inserted as one “long-term memory” section;
- query rewriting is represented by admitted Task Context and, later in the
  Run, target-neutral Query Candidates; it does not replace the Original User
  Task;
- final answer format belongs to the model-response/publication design rather
  than the activated-Tools section; and
- tool-result format is a separate result-contract concern, not the same thing
  as final answer format.

Current Workspace architecture also states that Tools remain provider tool
schemas, not duplicated prompt prose. The separate context-design work may
choose a more explicit authoring artifact, but it should preserve these current
meanings.

## 3. Canonical distinctions

The following terms must not be collapsed.

### Workspace Capability

A trusted, task-scoped ability that Workspace policy may activate for the
current actor, Case, purpose, dependencies, authorization, and budget. A model
may request use but cannot activate or authorize it.

### Model-visible Tool

The provider-facing projection of one activated capability: a name,
description, and input schema presented to the model through Pi. It is a model
interaction shape, not the business authority or infrastructure implementation.

### Operation recipe

Trusted Workspace policy that maps an admitted model request to an exact owner
operation. It binds hidden actor, purpose, Case, resource, authorization,
version, budget, and idempotency facts that the model cannot supply.

### Owner operation

The business operation executed by the owning Module, for example I&E exact
retrieval. Its Interface, result, failure, retention, and consistency semantics
belong to that owner, not to Pi's generic tool type.

### Adapter

An implementation at an owner seam, such as an OpenCTI read Adapter, browser
automation Adapter, or a future MCP-backed Adapter. An Adapter is not
automatically a model-visible Tool.

### Connector

OpenCTI/operator-managed ingestion or enrichment infrastructure. Connector
deployment, credentials, scheduling, queues, retries, and health are not model
choices and must not be exposed merely because a Tool can request a business
outcome.

### Finalized tool result

The Pi result message produced after execution and hooks settle. It is an
observation candidate for Workspace policy, not a Case fact, I&E Resource,
Working Set mutation, Workspace Artifact, or caller-visible publication.

## 4. Current documented and implemented facts

### 4.1 Pi generic Tool protocol

The generic provider-facing Tool contract currently contains:

- `name`;
- `description`; and
- a TypeBox/JSON-compatible input parameter schema.

The Agent runtime adds:

- a UI label;
- an execution function;
- optional argument compatibility preparation;
- sequential or parallel execution mode;
- progress updates;
- structured details for application/UI use;
- text/image content returned to the model; and
- an optional terminate hint.

Pi currently performs this lifecycle:

1. find the named active Tool;
2. prepare and validate model arguments against the input schema;
3. run the `beforeToolCall` policy, which may block;
4. execute sequentially or in parallel;
5. emit progress as display-only updates;
6. run the `afterToolCall` policy, which may replace result fields;
7. finalize one success/error result per call;
8. emit final tool-result messages in assistant source order; and
9. continue the model loop when appropriate.

Unknown Tools, malformed arguments, truncation, thrown execution failures, and
policy rejection already become error results observable by the next model
turn. Parallel completion may be out of order, but final transcript order
remains the assistant's call order.

### 4.2 Pi result limitation

Pi's generic result has model-visible text/image `content`, application `details`,
an error flag, and optional runtime hints. `details` is intentionally generic and
there is no generic output schema paired with every Tool definition.

The `afterToolCall` hook can validate or replace a result, but Pi does not know
the business meaning of an I&E receipt, Working Set action, Case proposal, or
browser observation. This is correct generic ownership, but it means CTI needs
owner-specific result qualification before a result is trusted or rendered.

### 4.3 Workspace capability admission

The accepted Run Control design defines a trusted capability snapshot. Each
entry binds:

- an opaque capability reference;
- a model-visible name, description, and input schema;
- schema, descriptor, and configuration digests;
- read-only versus future effectful classification;
- qualified dependencies and allowed goals;
- maximum uses and Run budgets; and
- whether the capability is model-visible.

Workspace constructs this snapshot from trusted actor, Case, purpose, task,
authorization, dependency, and budget facts. A proposed Tool input is admitted
only when it validates against the exact active schema and every trusted binding
still matches. The model cannot activate, configure, rename, retry,
parallelize, delegate, or widen a capability.

Specific product Tool number, name, and payload decomposition are deliberately
unfixed. The first accepted Run Control implementation slice is no-tool.

### 4.4 Product tool lifecycle design

The Pi-native Workspace lifecycle already requires:

- deterministic admission after input-schema parsing;
- trusted Adapter binding of actor, Case, authorization, versions, and hidden
  non-model fields;
- display-only progress updates;
- finalized results treated as candidates;
- complete batch validation at the save point;
- signed context-dependency evidence;
- source-ordered result persistence;
- new context construction before another provider request; and
- sequential execution plus durable-effect contracts for future effectful
  tools.

These are design facts. The complete CTI product Tool vertical is not
implemented.

### 4.5 I&E operations are not a Tool registry

I&E's architecture exposes owner operations such as retrieval, bounded
enrichment request, and observation of an existing enrichment operation. I&E
owns source/resource identity, versions, captures, derivatives, provenance,
lineage, use decisions, receipts, completeness, and retention.

The model cannot choose a Connector, parser, browser, URL, credential, queue,
schedule, retry, index, embedding model, reranker, or publication rule. A
trusted operation recipe may map an admitted Workspace capability to an I&E
operation while keeping these choices private.

Current active I&E scope is narrower still: one exact OpenCTI resource retrieval
contract. The I&E package does not yet exist. File/PDF parsing, OCR, semantic or
vector search, browser acquisition, production Connector activation, and model
enrichment are deferred.

### 4.6 The first designed CTI capability

The frozen Working Set design describes the first intended read-only vertical:

1. the model selects an opaque Workspace Resource Candidate Reference;
2. Workspace validates the capability snapshot and resolves hidden bindings;
3. a trusted recipe compiles an exact I&E retrieval request;
4. I&E returns a signed exact Retrieval Receipt and Resource Capsule;
5. Workspace verifies binding, version, status, use decision, provenance,
   authorization, and budgets;
6. the model-visible finalized Tool result contains only an actor-safe canonical
   action outcome and stable references/digests;
7. the raw Resource Capsule stays out of the ordinary transcript;
8. the Working Set mutation and result evidence commit atomically at a Pi save
   point; and
9. current material is revalidated before later model disclosure.

The semantic operation is exact-resource retrieval. Whether the model sees one
Tool or several Tool shapes remains an Adapter decision.

## 5. Four different output contracts

“Output format” is overloaded. CTI-RAG needs to keep four outputs separate.

| Output | Producer | Consumer | Current status |
| --- | --- | --- | --- |
| Tool-call arguments | model | Pi and Workspace admission | generic schema validation implemented; CTI capability admission designed |
| Owner operation outcome | I&E, Case Management, or another owning Module | trusted Workspace Adapter | exact I&E outcome designed; broader capability outcomes incomplete |
| Model-visible tool result | Workspace Tool Adapter | next model turn and Session | generic Pi envelope implemented; one exact-resource canonical outcome designed; no general CTI result contract |
| Final investigation response | model, then Workspace publication policy | caller | closed candidate/publication design exists; implementation remains gated |

The result returned by a Connector or parser is not necessarily any of these
four. It may be private intermediate owner state.

## 6. Deterministic validation and repair

The proposed “lint” idea is compatible with the current architecture if it is
placed at the owning seams rather than treated as one universal prompt rule.

### 6.1 Validation ladder

1. **Provider Tool-call syntax:** Pi parses the call and identifies the active
   Tool.
2. **Input schema:** Pi validates and may safely coerce arguments under the
   Tool's declared input schema.
3. **Capability admission:** Workspace verifies the exact capability snapshot,
   schema/configuration digests, task, goal, actor, Case, purpose, dependencies,
   authorization, and budgets.
4. **Operation binding:** a trusted recipe adds hidden owner inputs and prevents
   the model from supplying infrastructure authority.
5. **Owner outcome:** the owning Module validates the external response,
   identity, status, completeness, version, provenance, signature/receipt, and
   failure semantics.
6. **Tool-result projection:** Workspace constructs a bounded actor-safe result
   for the model and validates it against that capability's result contract.
7. **Save-point admission:** Workspace validates the complete finalized batch
   and commits permitted state atomically with its receipts.
8. **Next-context eligibility:** Workspace revalidates dependencies before the
   result or derived Working Set material enters another provider context.
9. **Final-response publication:** Workspace validates the final structured
   response independently from Tool results and publishes or withholds it.

Each validator owns one meaning. A single generic linter cannot establish CTI
authorization, provenance, Case authority, or I&E completeness.

### 6.2 What happens after invalid output

An invalid Tool result should not be silently repaired into apparent success.
The safe default is:

1. preserve the protected raw diagnostic only where its owner permits;
2. produce one bounded, actor-safe error observation for the model;
3. commit no owner-derived Workspace state from the invalid result;
4. let the next Pi model turn observe that failure;
5. allow a corrected Tool call only when the same capability remains active and
   Run Control admits another use and budget reservation; and
6. stop or return an insufficient/blocked disposition when retry is not
   authorized or the basis changed.

The validator does not itself call the model. Pi's existing loop provides the
next observation/decision point. This avoids a hidden self-repair loop.

Automatic unlimited retries are not acceptable. A repeated malformed call,
owner schema mismatch, authorization failure, non-retryable operation failure,
or budget exhaustion must terminate or change disposition according to the
owning policy.

Final response validation is different. The current Output Publication design
rejects malformed model output and does not make a second repair model call.
Adding one would require a separate bounded lifecycle decision and is not
implied by Tool-result correction.

## 7. Where common CTI functions belong

| Function commonly called a “tool” | Correct architectural placement | Possible model-visible capability |
| --- | --- | --- |
| retrieve an already identified CTI resource | I&E owner operation | read-only exact-resource retrieval after Workspace admission |
| search the CTI corpus | future I&E bounded-search operation | target-neutral bounded search returning opaque candidates; currently unaccepted |
| fetch/search the public web | source acquisition/retrieval policy plus a qualified Adapter; owner not yet accepted | possible bounded research capability only after source, egress, authorization, retention, and citation rules are designed |
| parse a PDF, OCR an image, chunk text | I&E private derivation pipeline | normally not a separate model-visible Tool; model asks for a business outcome, not parser choice |
| run an OpenCTI Connector | OpenCTI/operator infrastructure | not a model-visible Tool; future enrichment capability may request a closed outcome without selecting the Connector |
| enrich an observable | future I&E enrichment operation | possible typed bounded enrichment capability after its contract is accepted |
| update a Case | Case Management command/proposal workflow | future effectful capability only with accepted Case and durable-effect contracts |
| remember or recall history | existing owner retrieval coordinated by Workspace | context reconstruction or bounded owner-local recall, not automatically a Tool |
| delegate to another Agent | future orchestration design | not a Tool merely because Pi can execute a function |

This placement keeps business requests stable while allowing Adapter technology
to change. A browser, HTTP client, MCP server, OpenCTI Connector, or parser can
be replaced without changing the model's investigation vocabulary when the
business capability remains the same.

## 8. Candidate tool architecture view

The candidate end-to-end flow is:

```text
Current task and qualified context
  -> Workspace Capability Snapshot
  -> model-visible Tool projection
  -> model Tool call
  -> Pi input-schema validation
  -> Workspace capability-use admission
  -> trusted operation recipe binds hidden facts
  -> owning Module operation through an Adapter
  -> owner outcome validation
  -> Workspace actor-safe Tool Result projection
  -> Pi finalized result
  -> Workspace save-point admission
  -> next qualified context or Run settlement
  -> separate final-response publication gate
```

The deep public product Interface remains `CaseWorkspace.prompt({ task })`.
Callers should not need to construct Tool registries, credentials, owner
requests, retry rules, or result validators. Pi's Tool Interface and each owner
operation remain internal seams used by the Workspace implementation.

## 9. Schema ownership rules

This audit recommends the following ownership without defining schemas yet:

- Pi owns the generic provider Tool and finalized ToolResult message grammar.
- Workspace owns the model-visible capability descriptor, activation snapshot,
  admitted-use binding, and actor-safe Tool-result projection for each product
  capability.
- Each business owner owns its operation request, outcome, failure, receipt,
  version, and retention rules.
- Operation recipes own the deterministic mapping between Workspace capability
  use and owner operation; they do not redefine either schema.
- Provider-specific schema conversion belongs to Pi/AI Adapters.
- UI-specific `details` and progress rendering are not model authority and do
  not replace a result contract.
- Schema identity and version must be digest-bound to capability activation and
  rechecked before execution and result admission.

An input and output schema should be designed together for each accepted
capability, but they need not be represented by one shared cross-owner schema.
The model-visible result should be smaller and safer than the owner outcome.

## 10. Gaps

### 10.1 Real design gaps

1. There is no single current document explaining the complete Tool/capability
   composition across Pi, Workspace, I&E, and Case Management.
2. No general CTI product Tool-result contract defines validation, actor-safe
   projection, retryability, provenance references, and next-context behavior.
3. Product Tool activation has a capability design but no accepted concrete
   first Tool descriptor/result pair.
4. The relationship between Tool-result validation and bounded model correction
   is not stated as one lifecycle rule.
5. Browser/web acquisition has no accepted owner, source policy, citation,
   egress, retention, or failure contract.
6. PDF/OCR/derivation is deferred and has no active source-profile contract.
7. Bounded corpus search and enrichment remain deferred.
8. Effectful Case tools remain frozen behind Case Management and durable-effect
   contracts.
9. Transactional tool registry/configuration and complete tool-result save-point
   behavior are not yet fully delivered in the Pi-native Workspace migration.

### 10.2 Not gaps

- The absence of a unified Tool database is not a gap.
- The absence of a Tool bounded context is not a gap.
- Not exposing Connector/parser/credential choices to the model is deliberate.
- Not fixing the number and names of Tools before executable workflows exist is
  deliberate.
- I&E not being a generic plugin platform is deliberate.
- MCP not being designed is not a Tool-architecture blocker; it is an optional
  Adapter technology.

## 11. Recommended design sequence

1. Use this architecture view to align the separate context-design work: Tool
   schemas are one context input; Tool results are observations with their own
   admission lifecycle; final answer format remains separate.
2. Complete the already chosen first workflow as the reference capability:
   exact retrieval of one actor-visible Case resource into the Working Set.
3. For that workflow, later accept one concrete capability descriptor,
   input/output contract, recipe mapping, failure vocabulary, result projection,
   and save-point behavior through the existing owners.
4. Validate that production-shaped and in-memory owner Adapters pass the same
   public Workspace scenarios.
5. Measure the next real investigation need before deciding between bounded CTI
   search, public-web research, PDF acquisition/derivation, or enrichment.
6. Design each new capability as a vertical owner-composed workflow. Do not
   begin with a catalog of technologies or a universal Tool SDK.
7. Reopen effectful tools only after the Case and durable-effect architecture is
   active.

## 12. Reopen conditions for an independent Tool capability

An additional Module becomes justified only if an accepted responsibility
cannot remain local to Pi, Workspace, or a business owner and deleting that
Module would duplicate substantial policy across several real capabilities.
Possible future evidence could include a shared, stable, owner-neutral
capability catalog/qualification lifecycle used by multiple products. No such
requirement is currently documented.

Until then, the recommended architecture is:

> Pi executes generic Tools; Workspace admits product capabilities and binds
> their use; business owners execute and validate operations; Workspace projects
> bounded results into the next context.

## 13. Local evidence

- [CTI-RAG document authority](../README.md)
- [Context map](../CONTEXT-MAP.md)
- [Agent Workspace language](../agent-workspace/CONTEXT.md)
- [Pi-native Workspace lifecycle](../agent-workspace/pi-native-workspace-lifecycle-v1-contract.md)
- [Investigation Run Control](../agent-workspace/investigation-run-control-v1-contract.md)
- [Intelligence Working Set](../agent-workspace/intelligence-working-set-v1-contract.md)
- [Workspace Output Publication](../agent-workspace/workspace-output-publication-v1-contract.md)
- [I&E platform design](../intelligence-evidence/intelligence-evidence-platform-design.md)
- [Exact OpenCTI resource retrieval](../intelligence-evidence/opencti-exact-resource-retrieval-v1-contract.md)
- [Pi Agent runtime documentation](../../../packages/agent/README.md)
- [Pi AgentHarness lifecycle](../../../packages/agent/docs/agent-harness.md)

