---
status: accepted
---

# Make Memory Management a first-class Agent Module

The earlier Memory decision in [ADR 0018](0018-keep-memory-as-an-owner-local-architecture-view.md)
is superseded. It correctly rejected careless duplication of Case, Session and
Intelligence authority, but it incorrectly treated that storage decision as
evidence that the Agent does not need an independent Memory Management Module.

Pi is an Agent system, not only a collection of domain repositories. Memory
Management is a required foundational capability alongside Runtime/Harness,
State/Session, Tools/Capabilities and Validation/Evidence. It owns the memory
lifecycle and coordination logic even when domain facts, session history and
source evidence are supplied by adapters owned elsewhere.

## Decision

Introduce an independent, general-purpose Memory Management Module as a first-
class Agent capability. The Module provides the lifecycle and policy seam for:

- semantic, episodic and procedural durable memory;
- candidate extraction and admission;
- retrieval gating, qualification and context projection;
- consolidation and versioned updates;
- conflict, correction, invalidation and deletion; and
- memory-specific evaluation and evidence.

Session, Case Management, Workspace and Intelligence and Evidence remain
domain owners of their own records. They integrate through explicit Adapters;
their existing state is not a substitute for Memory Management.

The first implementation design must cover the complete lifecycle. No memory
category or lifecycle operation may be omitted merely because the current
product workflow has not yet demonstrated a use case for it. Product-specific
activation, policy and storage choices may be staged, but the foundational
Interface and failure semantics must remain explicit.

## Consequences

- The owner-local `WorkspaceMemoryCoordinator` candidate is no longer the
  top-level Memory design. Its useful qualification, revalidation and routing
  behavior becomes an integration capability behind the Memory Module seam.
- The old `workspace-memory-coordination/v1` candidate is retained only as
  historical design input until it is replaced by the Memory Management
  contract.
- The new Module needs a code owner and package route before implementation.
- End-to-end acceptance must prove extraction, admission, persistence,
  recall, context binding, correction and deletion rather than relying on
  document-level design acceptance.

## Non-decisions

This ADR does not select SQLite, PostgreSQL, a vector database, a graph store,
or a specific embedding/reranking implementation. It also does not make
model-produced content authoritative. Those choices belong to the new Memory
Management contract and its adapters. [ADR 0022](0022-select-sqlite-store-and-git-markdown-memory-source.md)
later selects the first local-host SQLite/Git-Markdown profile.
