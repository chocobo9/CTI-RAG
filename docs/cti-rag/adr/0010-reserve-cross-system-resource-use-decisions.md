---
status: accepted
---

# Reserve I&E Resource-use decisions for cross-system Case commands

The first R1 Case command will not use an ordinary I&E authorization/version preflight as proof at the later Case transaction. I&E must issue an operation-bound `ResourceUsePermitV1` that reserves one decision for the exact actor, purpose, Case, operation/effect, intended neutral-reference use, and Resource version. Case Management validates and consumes that permit while atomically deciding the Case command.

## Considered Options

- Query I&E immediately before the Case transaction. Rejected because permission, Resource version, or status may change between the response and effect commit.
- Copy I&E permission/version state into Case Management asynchronously. Rejected because replication lag cannot establish current cross-system authorization at the command boundary.
- Let Case Management link any stable Resource ID and rely on later cleanup after revocation. Rejected because it allows unauthorized or stale Resource use and changes the meaning of R1.
- Use an I&E-owned single-operation decision reservation. Selected because it gives the external owner an explicit linearization point without pretending the two databases share a transaction.

## Consequences

Revocation prevents new permits, but a permit is irrevocable for its exact binding until expiry. It carries a canonical digest, qualified issuer/verifier contract and signing-key identity, signature, target authority, and intended use. The facade validates it and atomically binds unique consumption in the same transaction as the Case decision; there is no remote I&E consume/cancel call. Case rollback also rolls back that local binding, while unknown acknowledgment is resolved through the facade ledger. The permit is a Fence Dependency, not a Possible Effect Domain, so an unknown R1 does not freeze unrelated work merely because it uses the same policy or I&E authority. An ordinary token, revocable assertion, or cached Working Set authorization cannot activate R1.
