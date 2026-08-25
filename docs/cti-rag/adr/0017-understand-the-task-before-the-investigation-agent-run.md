---
status: accepted
---

# Understand the task before the Investigation Agent Run

Agent Investigation Workspace performs Task Understanding before the formal Pi Investigation Agent Run. One bounded, tool-free model invocation may minimally normalize the immutable Original User Task, classify intent and requested outcome, and identify material ambiguity; deterministic Workspace code alone admits an Additional Task Context, falls back to the original, rejects the output, or returns clarification. This workflow stage creates no planner Harness, Session, tool loop, Query Candidate, capability plan, Working Set action, or investigation plan.

This decision supersedes ADR 0014 and the same-Agent-Run planning-control design in `task-context-understanding/v1`. The one-shot frontend and the long-lived Harness must reuse one Pi-owned prepared-invocation/Provider Dispatch Implementation; Workspace may not create a second provider lifecycle. After admission, Workspace commits the immutable task and admitted context into the existing leased Workspace Session before starting the Investigation Agent Run. The initial investigation context has this logical precedence: System Instructions, Original User Task, Additional Task Context, Working Set, layered Case Context, eligible Session History, and activated Tools. Case Context always retains the actor-scoped Orientation baseline and may add a Projection overlay bound to that evidence; Tools remain provider tool schemas rather than copied prompt prose.

“Long-lived Harness” is interpreted as the non-durable Harness reused only for
one open Workspace lifetime. Session alone persists across close/reopen; the
next open reconstructs a new Harness.

An off-the-shelf schema-capable model is used initially; fine-tuning is not a prerequisite. Model adequacy is established with bounded CTI literal-preservation and ambiguity fixtures, not by assuming that a smaller model is sufficient.
