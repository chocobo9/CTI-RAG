---
status: accepted
---

# Select SQLite as the first Memory Store and Git-backed Markdown as the user-editable source

The Memory lifecycle needs one local authority that can atomically couple an
entry revision, idempotent operation outcome, receipt and deletion tombstone.
It also needs a direct user-edit surface without allowing Memory mutations to
silently overwrite user-authored content. The existing `sql.js` probe and Waku
architecture are useful evidence, but neither alone qualifies a production
profile: the probe is single-process evidence, and Waku is a reference
blueprint.

## Decision

For the first local-host Memory profile:

- **SQLite** is the authoritative Memory Store for admitted Entry revisions,
  operations, receipts and tombstones.
- **Git-backed Markdown** is the user-editable Memory Source. A user edit
  becomes a candidate only through an exact allowed commit/blob, source-policy
  verification and normal Memory admission.
- Memory never writes, merges, commits or restores the Git repository. Git
  Markdown is neither a second Memory Store nor a mirror of SQLite Memory.
- A later read-only Markdown export, another database profile, a second host or
  a search/index capability requires its own accepted contract/profile; none is
  implied by this decision.

The selected SQLite Adapter is not implementation-qualified merely because the
probe uses SQLite. It must declare and pass the storage profile's writer,
durability acknowledgement, CAS, restart/recovery, purge and retention
acceptance catalogue before it supports the Module.

## Consequences

- The Memory Module retains one authoritative lifecycle state, avoiding
  divergent user file/database copies.
- Users can directly author and version Markdown without giving a file edit
  direct authority to mutate Memory or Provider context.
- Git source changes are versioned provenance inputs; changed, missing,
  uncommitted, moving-branch or conflicted sources fail closed.
- The first implementation must prove AM-01 through AM-23 and SP-01 through
  SP-06 in the Memory contract, including zero Git writes from every Memory
  lifecycle operation.

## Non-decisions

This ADR does not select a SQLite driver/runtime, a multi-host concurrency
profile, a Markdown export format, an automatic import schedule, a model
extraction policy, or a general retrieval/search/index design.
