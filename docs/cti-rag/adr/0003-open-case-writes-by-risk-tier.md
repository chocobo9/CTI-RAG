---
status: accepted
---

# Open Case writes progressively by risk tier

Case Write Capabilities will be enabled from low to high risk according to reversibility, authority change, investigation scope, external effect, and propagation. Pi hooks provide runtime interception, while a CTI-owned capability registry and lint rules define approval, freshness, and output-impact requirements. The first write slice is limited to reversible additive R1 operations.

## Consequences

No Case mutation tool may be registered without policy metadata. Security-critical binding values come from the trusted Workspace Tool Adapter rather than model arguments. The owned Case Management command authority performs final facade authorization, business validation, expected-revision comparison, and terminal decision; I&E owns the operation-bound Resource-use decision represented by its qualified permit. OpenCTI enforces its actor/item access and materialization-target constraints but is neither the command receipt authority nor the final validator of the Case proposal.
