---
status: superseded
supersededBy: 0021-make-memory-management-a-first-class-agent-module.md
---

# Keep memory as an owner-local architecture view

> Superseded by [ADR 0021](0021-make-memory-management-a-first-class-agent-module.md).
> The owner-local storage and anti-duplication concerns remain useful
> constraints, but this ADR's conclusion that a first-class Memory Module is
> unnecessary is rejected.

CTI-RAG treats memory as a cognitive view over existing owners, not as a new
shared persistence authority. Pi Session owns interaction history, branches,
compaction, save points, and recovery; Agent Investigation Workspace owns
task-scoped state and non-authoritative Workspace Artifacts; Case Management
owns current and historical Case authority; Intelligence and Evidence owns
reusable source/resource identity, provenance, versions, retrieval evidence,
and retention-qualified material.

Agent Investigation Workspace reconstructs the mandatory context required by
the current task and may later route an optional historical need to the likely
owner. Eligibility is established before relevance. Workspace adopts only a
bounded, labelled, revalidatable view into model context. A search index,
embedding store, cache, MCP Adapter, or model-produced summary is never another
owner and cannot preserve deleted or withdrawn material as shadow authority.

This does not make Memory a documentation-only view. Workspace must provide a
deep Memory Coordination Module that reconstructs current task memory, decides
and routes optional recall, qualifies and adopts owner-local material,
revalidates it before disclosure, and routes settled retention candidates back
to the proper owner. The Module persists no shared content; its durable outputs
are non-content binding, adoption and routing receipts.

The first Pi-native Initial Investigation Context performs mandatory context
reconstruction only. Eligible Pi Session history is part of that base and is
not a semantic memory search. Cross-Case procedure, episodic lessons, and
user/team preferences remain closed because no accepted workflow, authority,
sharing scope, retention policy, or deletion policy owns them. Historical
Workspace Artifact discovery also remains separately gated and does not add an
eighth Initial Investigation Context section.

This decision avoids a global memory database that would duplicate Case,
Workspace, Session, and I&E state and blur correction, authorization, deletion,
and provenance. A separate Memory owner may be proposed only when a concrete
cross-Case or cross-Workspace workflow cannot be represented by any existing
owner and independently closes its authority and lifecycle.
