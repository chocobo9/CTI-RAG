---
status: accepted
---

# Own Case command state and materialize accepted membership into OpenCTI

The production first-slice Case Management facade will own the authoritative Case head, neutral Resource membership, immutable operation/digest ledger, independent proposal-ledger head, terminal receipt, and materialization outbox in one durable transaction. OpenCTI remains the graph/search/read integration target and receives the accepted membership through an idempotent outbox consumer; its mutation response or entity presence is not the command receipt.

## Considered Options

- Write stock OpenCTI directly and infer success from the response, history, stream, or later search. Rejected because these do not establish caller-intent identity, atomic expected-revision validation, terminal no-effect, or durable receipt lookup.
- Put only a receipt table and process lock in front of OpenCTI. Rejected as a production contract because bypass writers and non-atomic downstream mutation leave the Case head and effect inconsistent.
- Use an exclusive all-writer coordinator with a shadow revision and uniquely testable neutral predicate. Retained only as a separately qualified transitional Adapter for deployments where every writer is provably routed through it; it does not generalize to Notes or non-idempotent effects.
- Own command state transactionally and materialize OpenCTI. Selected.

## Consequences

Every new terminal proposal identity advances the independent proposal-ledger revision once; duplicate replay does not. `applied` additionally advances the authoritative Case head once and commits an outbox item in the same transaction. `satisfied_without_change` is a terminal already-satisfied disposition, advances no Case Revision, creates no effect, and never enters synchronization wait. Only `applied` is `accepted_but_unsynchronized` until an exact Projection inclusion proof exists. Production qualification includes commit durability and failover settings; a deployment that can lose an acknowledged Effect Intent/receipt/outbox transaction cannot activate strict R1.
