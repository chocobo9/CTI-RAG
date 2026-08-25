---
status: accepted
---

# Bind a write activation to one Revision Authority

A write-enabled Workspace activation must obtain its Case Projection basis and `CaseRevision` from the same Revision Authority that performs receiver-side expected-revision validation. The concurrency identity is the tuple of authority ID, revision-contract version, Case ID, and opaque token; matching token text from another authority is irrelevant.

## Considered Options

- Accept any Adapter revision token and let the write facade reinterpret it. Rejected because two authorities can cover different semantic blocks and writer sets, making the comparison fictitious.
- Read stock OpenCTI directly, compute a synthetic digest/revision, and pass it to a separate command facade. Rejected because the facade cannot atomically exclude OpenCTI changes that occur outside its revision domain.
- Let the active Case Management authority compose the qualified OpenCTI observations with its revisioned semantic overlay and issue both the Projection basis and write CAS token. Selected.

## Consequences

Stock OpenCTI can remain a qualified Projection data source, but it is not an interchangeable revision issuer for strict writes. Changing authority, revision contract, or Case creates a new activation and requires a fresh Projection. Old tool intents become stale; unfinished effects remain pinned to their original archived authority contract and are reconciled rather than rebased. Independently writable semantic state must be excluded from the authority revision domain or atomically advance the same Case head.

