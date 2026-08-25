# Agent Memory Rules

## Ownership

This package owns the independent Agent Memory module: candidate admission, memory
entry revisions, scoped qualification, recall, revalidation, and deletion state.

## Dependency Boundary

This package must not depend on Workspace, Case Management, Intelligence and
Evidence, provider integrations, or model extraction. Owner data is represented
only as explicit versioned references; Memory never becomes owner authority.

## Placement

Keep the public seam and domain types in `src/`. SQLite persistence is an internal
Adapter. Tests must cross the public `AgentMemoryModule` Interface.

## Tests

Use the in-process SQLite Adapter and deterministic candidates. Do not call models,
providers, OpenCTI, Workspace, or Case services.
