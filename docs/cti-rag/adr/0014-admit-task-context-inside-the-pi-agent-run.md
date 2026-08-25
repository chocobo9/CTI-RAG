---
status: superseded by ADR-0017
---

# Admit Task Context inside the Pi Agent Run

Superseded by [ADR 0017](0017-understand-the-task-before-the-investigation-agent-run.md). Retained only as the rationale for the earlier same-Agent-Run planning-control design.

Agent Investigation Workspace keeps `prompt({ task })` as its common Interface. It preserves the raw User Task and uses one private structured control action inside the existing long-lived Pi Agent Run to obtain a model Task Context Proposal. A deterministic Workspace `TaskContextGate` admits a versioned Task Context Plan, conservative fallback, clarification, raw-task fallback, or denial. The decision commits through Pi's normal save-point transaction before later response or product-tool work.

## Considered Options

- Parse or rewrite free-form model prose. Rejected because provenance, ambiguity, and trusted fields cannot be validated reliably.
- Run a separate planner provider/Harness/Session. Rejected because it introduces a second loop, transcript, transaction, abort, retry, and recovery lifecycle.
- Add a provider structured sidecar and generic Pi `assistant_candidate` seam. Deferred because it can save one planning turn but requires provider qualification and a new broad seam with no second proven consumer.
- Expose `understand`, `approve`, and `execute` to callers. Rejected because it makes the application Interface shallow.
- Use a private Pi control action and deterministic Task Context Gate. Selected because it preserves one Harness/Session/Agent Run, exercises real `tool_call -> tool_result -> save_point` behavior, and keeps authorization and execution decisions in trusted code.

## Consequences

The raw User Task remains the permanent source and is never replaced by a plan or Query Candidate. The model may propose semantics, uncertainty, aliases, query variants, and capability needs, but it cannot bind Case/actor/authorization, Context Dependencies, tools, budgets, freshness, retry, commit, or terminal state.

Free-form planning uses the conservative union of Orientation dependencies. Narrower dependency sets require a trusted closed workflow or operation recipe; natural-language classification is not sufficient provenance. Query Candidates are non-authoritative and non-executable until a later I&E contract qualifies retrieval scope, egress, coverage, cost, and backend compilation.

The selected design normally adds one planning provider turn and delays public streaming until admission. That cost is accepted initially. A deterministic fast path or qualified provider sidecar may be reconsidered only from measured latency/cost evidence without weakening raw-task provenance or deterministic admission.
