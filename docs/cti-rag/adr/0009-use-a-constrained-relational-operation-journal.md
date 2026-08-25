---
status: accepted
---

# Use a constrained relational Durable Operation Journal

Agent Investigation Workspace will persist first-slice operation coordination through a private deep `DurableOperationJournal`. The reference production Adapter uses constrained relational current facts plus immutable observations; the in-memory Adapter implements the same atomic transitions and failure behavior with restart images and failpoints.

## Considered Options

- Expose repositories for operations, outputs, receipts, reservations, and dependencies. Rejected because every caller would need to reproduce transaction grouping, monotonic receipt, and crash rules.
- Store only a universal append-only event stream and reconstruct every current fact by replay. Rejected for the first slice because critical uniqueness, receipt-shape, dispatcher-eligibility, reservation, and foreign-key invariants need direct database enforcement and simpler recovery queries.
- Keep only current rows without immutable observations. Rejected because duplicate/out-of-order evidence, acknowledgment loss, audit, and index rebuild require stable observation identities.
- Combine normalized constrained current facts with immutable observations behind semantic atomic methods. Selected.

## Consequences

Admission atomically commits intent, exact inputs, Output Claims, Effect Intent, receipt lookup, all reservations, archive pins, and dispatcher eligibility. Local output publication, authority receipt merge, and Projection-inclusion merge each have explicit atomic aggregates. A dispatch-permit transition commits `may_have_dispatched` before remote I/O and returns a permit only after definitive commit; an unknown acknowledgment returns no permit until lookup. The Dependency Index is rebuildable and flips complete generations atomically. Unresolved effects and referenced contract archives are not removed by age-based garbage collection. PostgreSQL is the reference production Adapter, but callers do not learn tables or storage technology.
