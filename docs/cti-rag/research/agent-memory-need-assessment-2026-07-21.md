# Agent Memory Need Assessment

Date: 2026-07-21

## Question

Does the CTI-RAG product need an independent Agent Memory capability or Module beyond the existing Harness, Session, Workspace, I&E, and Case boundaries?

## Local design facts

- Agent Investigation Workspace executes a current Original User Task against a Case and owns task-scoped working state. [`agent-workspace/CONTEXT.md`](../agent-workspace/CONTEXT.md)
- Case is a long-lived investigation business instance with continuity across user tasks and Agent Runs. Case State is authoritative business state; it explicitly excludes Agent memory and transcript. [`case-management/CONTEXT.md`](../case-management/CONTEXT.md)
- I&E owns reusable source material, provenance, structured intelligence, and retrieval shared across Cases. An Intelligence Resource is globally reusable and is not prompt content. [`intelligence-evidence/CONTEXT.md`](../intelligence-evidence/CONTEXT.md)
- Session is a navigable interaction history for continuing, compacting, and branching Agent work. It is not the authoritative investigation record. Workspace State is task-scoped and references, rather than copies, other authorities. [`agent-workspace/CONTEXT.md`](../agent-workspace/CONTEXT.md)
- The current Workspace design explicitly avoids a second transcript or small-state database and assigns small v1 Workspace state to the leased Pi Session. [`adr/0012-use-pi-harness-as-workspace-execution-spine.md`](../adr/0012-use-pi-harness-as-workspace-execution-spine.md), [`adr/0015-use-session-authority-and-pre-dispatch-proof-for-workspace-capabilities.md`](../adr/0015-use-session-authority-and-pre-dispatch-proof-for-workspace-capabilities.md)
- The current design has no canonical owner or contract for cross-Workspace user preferences, cross-Case Agent experiences, or generic automatic memory write/recall/delete. This is an audit finding from the owner maps and glossary, not an accepted decision to reject all memory capability.

## External primary-source comparison

LangChain's official documentation defines long-term memory as information stored and recalled across conversations and sessions, distinct from short-term thread state. Its conceptual documentation separates semantic facts, episodic experiences, and procedural instructions, and treats write timing, retrieval mode, scope, and permissions as separate design choices: <https://docs.langchain.com/oss/python/langchain/long-term-memory>, <https://docs.langchain.com/oss/python/deepagents/memory>.

Letta's official documentation likewise separates conversation search, editable agent memory blocks, and archival memory search for larger stores. This shows that an Agent memory capability is primarily a cross-session write/recall policy and ownership problem, not merely persistence of a transcript: <https://docs.letta.com/guides/get-started/for-agents>.

OpenAI's official data-controls documentation demonstrates that application state retention and deletion/retention controls are product-level concerns distinct from model invocation: <https://platform.openai.com/docs/models/default-usage-policies-by-endpoint>.

These sources establish common industry distinctions only. They do not authorize a particular CTI-RAG Module or storage technology.

## Findings for CTI-RAG

### What the existing design already covers

1. Cross-turn and resumable Agent interaction: Pi Session.
2. Continuity of one investigation across user tasks and Agent Runs: Case Management, with Workspace re-projection.
3. Reusable cross-Case intelligence material: I&E Resource and provenance model.
4. Current-task selections and non-authoritative reasoning outputs: Workspace Working Set and Workspace Artifacts.

These are memory-like functions, but they have different authorities, retention rules, and disclosure semantics.

### What is not covered

The design does not currently answer whether the product needs to retain and recall any of the following outside one Case, one Workspace, one Session, or the reusable I&E corpus:

- user preferences or analyst working conventions;
- Agent experiences or reusable investigation procedures;
- cross-Case hypotheses or prior investigative lessons;
- explicit user-approved facts that should follow a user across tasks;
- deletion, correction, versioning, and conflict policy for such information;
- who may read or modify it and whether multiple Agents share it.

### Decision assessment

An independent generic Memory Module is not required merely because the system has persistent state. The current Case, I&E, Session, and Workspace boundaries already cover the documented CTI business flows.

However, a memory capability is required as a separate design decision if the product expects cross-Workspace or cross-Case recall of user/Agent knowledge that is neither authoritative Case state nor reusable I&E material. That requirement is not currently closed.

Therefore the present architecture has a **memory-policy gap**, not evidence that a generic Memory Module has already been designed and not evidence that one must immediately be added.

## Recommended next audit decision

Before choosing a store or Module boundary, the project should answer:

1. Is cross-Case recall of analyst or Agent knowledge a required CTI workflow?
2. Is that knowledge authoritative, advisory, or merely historical?
3. Who owns its write admission and correction: user, Workspace policy, Case Management, I&E, or another owner?
4. What identity and scope isolate it: user, tenant, Case, Workspace, Agent, or Session?
5. How are contradiction, expiry, deletion, authorization revocation, and recall eligibility proven?

If the answer is no, document that existing authorities intentionally cover continuity without a generic memory capability. If the answer is yes, define the smallest owner-specific capability and do not put it into Session, Case, or I&E by implication.
