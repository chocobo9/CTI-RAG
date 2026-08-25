---
status: accepted
---

# Use operation-specific Projection freshness

The Workspace will combine three consistency modes rather than choose one globally: fresh-required for Case writes and external effects, bounded-stale read-only for temporary investigation continuity, and historical read-only for audit or replay. Event-driven invalidation supplies low-latency awareness, while revision validation, delta continuity, and recovery probes provide correctness under concurrency, asynchronous writes, missed events, and transport failure.

## Consequences

Each tool capability must declare its required Freshness Mode. Stale or historical projections cannot authorize Case mutation. Ordinary live authorization, facade policy, Capability Grant, contract lifecycle, and disclosure checks always use current owner state and have zero stale allowance; only explicitly declared data revisions may use bounded-stale or historical modes. An owner-issued, operation/effect-bound `ResourceUsePermitV1` is not a cached authorization exception: its issuance is I&E's access/version decision linearization point, and the reserved decision is irrevocable only for that exact target/use until its short expiry under ADR 0010. It cannot authorize another operation, new disclosure, or use after expiry, while Case Management still evaluates all of its own live fences in the command transaction.
