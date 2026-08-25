---
status: accepted
---

# Derive asynchronous impact from declared operation dependencies

Agent Investigation Workspace will coordinate asynchronous reads, model requests, local updates, and remote effects through a private deep Operation Coordinator backed by a closed trusted recipe catalog. Every current output declares version-bound inputs and derivation edges; every remote mutation durably records its stable identity, request digest, and possible effect domains before dispatch, then relies on an authority-owned receipt and reconciliation. Staleness, challenge, authorization loss, and suspension are derived from those declarations and their transitive dependency closure rather than from a global Workspace epoch or one suspended bit.

## Considered Options

- Tool-specific state machines were rejected because fencing, retry, receipt ordering, and crash rules would be repeated across Pi hooks and Adapters.
- A global Workspace epoch or suspension bit was rejected because an unrelated operation would invalidate or freeze valid read-only work.
- An open runtime dependency-rule engine was rejected because the first release needs only a small reviewed catalog and cannot safely let models or callers declare security-critical bindings and effect scope.
- A closed recipe catalog with one common execution path was selected because it keeps the normal caller Interface small while concentrating concurrency and recovery behavior behind one testable Seam.

## Consequences

Effect scope can be no narrower than the owning authority can prove; a whole-Case revision therefore remains a Case-head effect domain until Case Management supplies stronger block-level guarantees. Remote mutation capabilities are disabled unless their Adapter supports stable same-intent deduplication, authoritative receipt lookup, and retention longer than automatic reconciliation. The system promises effectively-once effect handling under that contract, not exactly-once execution or delivery.

Dependency references are constructed only by trusted typed templates and intersect in the first release only when owner, key kind, key version, and canonical length-framed tuple bytes are exactly equal. Recipes must explicitly declare authority-mandated broad concurrency references such as `case-head/v1(authorityId, caseId)` alongside narrower semantic references; the runtime does not infer overlap from string prefixes, Unicode similarity, or content. Compilation rejects missing, unknown, ambiguous, or caller-built references.
