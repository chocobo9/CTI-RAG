# Initial Context Industry and Pi Reuse Audit

Date: 2026-07-22  
Status: Planner research; non-normative

## Question

Does the current PNW-C Initial Investigation Context candidate reuse mature
context/memory architecture and Pi's existing seams, or does it introduce a
parallel project-local product?

## Finding

The candidate combines a sound architectural direction with an unjustified
concrete product shape.

The sound direction is:

- keep conversation history, current business state, retrieved knowledge, and
  executable tools under separate owners;
- distinguish thread-scoped conversation continuity from cross-thread
  long-term recall;
- let the application qualify and assemble context while the model runtime owns
  provider message and Tool transport;
- authorize and qualify data/capabilities before exposing them to the model.

The exact seven-section record, three synthetic user messages, per-section
digest catalog, explicit serialized empty slots, and timestamp-bearing
projection are not an industry standard. They are project-local proposals and
must not be treated as accepted merely because their fields are precise.

## Primary-source industry evidence

### Stable patterns

1. OpenAI's Conversations API models context as ordered input items with
   instruction roles, user messages, prior assistant output, and separately
   supplied Tools. It does not prescribe a seven-section application record.
   Sources:
   [Conversations API](https://platform.openai.com/docs/api-reference/conversations),
   [Responses tools](https://platform.openai.com/docs/api-reference/responses).
2. LangGraph distinguishes thread-scoped short-term memory, persisted as graph
   state/checkpoints, from cross-thread long-term memory held in a Store. Its
   documentation explicitly says long-term memory has no one-size-fits-all
   solution.
   Sources:
   [Memory overview](https://langchain-ai.github.io/langgraphjs/how-tos/manage-conversation-history/),
   [Persistence](https://langchain-ai.github.io/langgraph/concepts/time-travel/).
3. Model Context Protocol separates Tools, Resources, and Prompts, leaves the
   host application responsible for aggregation and security, and explicitly
   does not dictate how an application uses model context.
   Sources:
   [MCP architecture overview](https://modelcontextprotocol.io/docs/learn/architecture),
   [MCP server concepts](https://modelcontextprotocol.io/docs/learn/server-concepts).
4. MCP keeps authorization in the transport/resource boundary and recommends
   least-privilege capability scopes. This supports qualification before model
   exposure, but does not define CTI eligibility, Case authority, or context
   serialization.
   Source:
   [MCP authorization](https://modelcontextprotocol.io/docs/tutorials/security/authorization).
5. Semantic Kernel keeps system/developer instructions, chat history, and
   function definitions/results as different runtime concepts. It also treats
   inserted external content as unsafe by default in its prompt templating
   boundary.
   Sources:
   [Chat history](https://learn.microsoft.com/en-us/semantic-kernel/concepts/ai-services/chat-completion/chat-history),
   [Prompt injection protection](https://learn.microsoft.com/en-us/semantic-kernel/concepts/prompts/prompt-injection-attacks).

### What the sources do not establish

None of these primary sources establishes:

- seven mandatory logical sections;
- one serialized record containing all owner values;
- three synthetic `user` messages for task context, Working Set, and Case;
- a digest per logical section in addition to the runtime's canonical context
  digest;
- a requirement to emit empty Working Set or Tool placeholders to the model;
- provider-message timestamps as part of semantic context identity.

Those choices require project evidence or removal.

## Pi reuse audit

| Candidate responsibility | Existing owner/seam | Audit result |
|---|---|---|
| Provider-visible system prompt, messages, Tools | `packages/agent/src/types.ts` `AgentContext` | Reuse. A parallel provider projection type is duplicate transport ownership. |
| Eligible Session history selection | `AgentHarnessContextEntryPolicy` | Reuse. Workspace supplies CTI eligibility policy; it should not create a second transcript selector. |
| Message/Tool canonical snapshots and digests | Provider Dispatch canonicalization | Reuse. PNW-C must not mint a competing canonical message or Tool digest authority. |
| Thread continuity and retained branch | Pi Session/Harness | Reuse by reference/evidence, not by copying the transcript into a second product record. |
| Original task and admitted task context | Task Understanding committed handoff | Reuse owner evidence. Do not normalize or restate it into a new authority. |
| Current Case and Working Set eligibility | Workspace/Case/Working Set owners | Project-specific qualification is required; render only an admitted projection. |
| Model-facing CTI labeling and injection isolation | No complete public seam identified | Genuine PNW-C design work remains. |
| One leased Session and long-lived Harness lifecycle | PNW-B | Blocking prerequisite; not owned by the context compiler. |

## Corrected design direction

The seven items may remain a planning checklist of logical input authorities.
They must not become seven new authoritative stored records or a second
provider-context model.

The smallest credible PNW-C product is:

1. owner-local qualification results for the project-specific inputs;
2. a minimal non-secret binding manifest that references the exact owner
   evidence used for this Run;
3. one ephemeral transformation into Pi's existing `AgentContext`;
4. Provider Dispatch as the sole canonicalizer of the actual system prompt,
   ordered messages, images, and Tools.

The audit has not yet proved the exact minimal manifest or message-role mapping.
Therefore the PNW-C Design Gate remains FAIL.

## Known open decisions before Design PASS

1. Which CTI inputs need a Workspace binding reference beyond their existing
   owner receipt, and which would be duplicate evidence?
2. How are untrusted Case, Working Set, Artifact, and recalled text delimited so
   they cannot become higher-priority instructions?
3. Does Pi need one generic structured context-envelope seam, or can Workspace
   render through the existing context hook without a new public type?
4. How does the same projection reproduce after compaction, branch change,
   reopen, lease loss, or context-generation invalidation?
5. Which identity is semantic and stable, and which runtime metadata
   (especially timestamps) must stay outside digests?
6. How are multimodal history and Tool call/result chronology preserved without
   lossy conversion?
7. How are token budgeting, provider prompt caching, and exact-count evidence
   bound to the final Pi context rather than the candidate's intermediate
   record?
8. How are Tool capability changes re-qualified between Runs?
9. What public failure is returned for each owner-read, qualification,
   rendering, invalidation, and runtime-admission failure?
10. What exact migration deletes the per-Turn staging Session/Harness without a
    second execution spine?

## Gate

- Memory owner-local architecture: supported.
- Seven logical input authorities as a requirements checklist: plausible.
- Seven-section serialized product: unproven.
- Synthetic provider-message projection: unproven.
- Duplicate digest/product ownership: present in the candidate.
- PNW-C Design Gate: FAIL.
- Development dispatch: forbidden.
