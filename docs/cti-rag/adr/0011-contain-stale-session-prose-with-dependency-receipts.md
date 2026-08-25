---
status: accepted
---

# Contain stale Session prose with dependency receipts and a clean active model path

Mechanism update: [ADR 0012](0012-use-pi-harness-as-workspace-execution-spine.md) keeps this safety decision but supersedes the per-Turn private staging-Harness mechanism. The target uses Pi-owned save-point transactions and signed context-generation checkpoints; the delivered v1 receipts and markers remain migration evidence.

Agent Investigation Workspace will retain authorized append-only Session history for audit while deriving the active model path from authenticated operation spans and dependency receipts. Each Turn runs in a private staging Session; a closed declaration selects the Orientation blocks and historical dependency chains the model may read. Only a complete response whose exact dependency set passes the current fence is committed as one expected-head Session append group. Drift, revocation, incomplete spans, or untrusted provenance exclude intersecting prose mechanically and may add only a non-sensitive Stale Capsule. This keeps audit retention separate from current reasoning eligibility without changing Pi's agent loop.

## Considered Options

- Tell the model to ignore old prose. Rejected because prompt compliance cannot establish context exclusion, authorization, or write eligibility.
- Redact or rewrite stale text in place. Rejected because matching free text cannot prove derivation scope, append-only audit evidence would be destroyed, and protected facts could survive in summaries or paraphrases.
- Clear all Session history after any drift. Rejected because it discards dependency-disjoint work and makes ordinary recovery unnecessarily destructive.
- Keep append-only audit history but select a clean active model path from closed CTI spans and dependency receipts. Selected because staleness and protection can be derived mechanically at the affected dependency chain while disjoint qualified context remains usable.

## Consequences

Recoverable Workspaces require a caller `sessionRef`, stable operation/Turn identities, append-only CTI span markers, an expected-head atomic Session append primitive, and dependency receipts authenticated by a trusted signer port. Public hashes are not authenticity. The delivered HMAC signer keeps its secret outside Session; a different key or any receipt/message/dependency alteration fails closed. Legacy messages or compaction summaries without trustworthy provenance remain ineligible, while authentic receipts and stale/protected markers preserved unchanged in branch/compaction ancestry retain their independent meaning. Authorization revocation excludes protected bodies and body-derived prose even when a separately authorized audit view retains them. The atomicity guarantee is local to one Session storage instance and makes a crash prefix dirty by writing the receipt last; it is not a cross-process lock, a durable effect Journal, strict-R1 recovery, or a public Session-reconciliation Interface.
