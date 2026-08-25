---
status: accepted
---

# Compile Case contracts and qualify deployment Adapters separately

Agent Investigation Workspace will compile source-controlled Projection Profiles, Case Write Capabilities, canonical keys, schemas, renderers, and operation recipes into one immutable digest-addressed catalog. A separate qualification step activates catalog entries only for exact Adapter artifacts and deployments with matching conformance evidence. `CaseWorkspace` receives an opaque active contract; `OperationCoordinator.perform` remains the single operation lifecycle machine.

## Considered Options

- Scattered validation in Pi hooks, tool handlers, and Adapters was rejected because contract completeness, dependency scope, and recovery rules would diverge.
- A combined runtime `bind/advance` contract machine was rejected because it duplicates the Operation Coordinator transition protocol.
- An open runtime registry was rejected because callers or model output could widen security-critical schemas, dependencies, effects, or guarantees without a reviewed release.
- A prompt-scoped high-level Module alone was rejected because it couples the contract to one interaction lifecycle and tends toward one method per Capability.
- Pure compilation followed by deployment qualification was selected, with the common prompt path hidden inside `CaseWorkspace`.

## Consequences

Malformed trusted definitions fail build or startup rather than silently becoming optional behavior. A missing deployment guarantee disables only the affected optional Profile or Capability; loss of the core Projection Profile stops the Case prompt. Catalog digest identifies immutable semantic definitions, while activation digest identifies exact Adapter artifacts, deployment, conformance evidence, and active entry set. Historical Effect Intents and receipts remain pinned to archived original definitions and decoders.

The complete `opencti-case-projection/v1` is composed from a qualified actor-scoped OpenCTI data source and facade-owned revisioned semantic overlay. A stock-only orientation Profile, if built, has a different smaller identity. A write-enabled activation accepts only a Projection and Case Revision produced by the same Revision Authority that performs receiver-side CAS; switching authority requires a fresh activation and Projection.

The first strict production R1 Capability is only a neutral Resource Reference added to the Case `object` collection through an owned facade that provides real Case-partition conditional mutation, identity-plus-digest deduplication, durable receipts/status lookup, retention, and effect-in-Projection proof. A facade cannot claim real CAS if other writers bypass it and the underlying owner has no atomic conditional write. Append-note is deferred. None of these decisions fixes the number or decomposition of model-visible tools.
