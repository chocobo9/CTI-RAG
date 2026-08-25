---
status: accepted
---

# Use Session authority and pre-dispatch proof for Workspace capabilities

Provider-proof ownership in this ADR is partially superseded by [ADR 0016](0016-keep-rag-ownership-local-and-admit-retrieval-deterministically.md): Pi owns the generic Provider Dispatch transaction, while Workspace contributes only application binding, disclosure, and terminal material through an Adapter. The one-Session authority and pre-dispatch-proof requirement below remain accepted.

The first Pi-native Workspace keeps its small task-scoped runtime state inside the one leased Pi Session and requires a durable Provider Dispatch Transaction before a logical provider invocation that discloses Working Set/I&E content. Typed Session entries and their authenticated save-point receipts own raw User Task identity, admitted Task Context decisions, Workspace Capability snapshots, bounded Working Set entry/reference state, and the dependencies needed to reconstruct eligibility. Workspace policy owns their CTI meaning; Pi owns ordering, atomic save-point commit, compaction/tree evidence, recovery, the non-secret Logical Provider Invocation Artifact, and the private Prepared Provider Invocation handed to its provider Adapter. No second Workspace transcript, Working Set transaction, or small-state database is introduced for v1.

A Task Context Query Candidate remains model-produced, target-neutral, and non-executable. Only after its planning save point commits may Workspace mint separate opaque Resource Candidate References from current actor-visible Orientation membership. A later model-visible tool may select one such reference and cite a Query Candidate for semantic provenance, but trusted code alone binds the current actor, Case, purpose, task, Context Generations, qualification, budget, and exact I&E selector. Tool name and decomposition remain separate Adapter decisions.

Raw I&E Resource Capsule bodies do not enter ordinary tool-result transcript messages. A finalized tool outcome records only an actor-safe bounded status/reference; the unified Workspace context policy renders currently revalidated Working Set material from its owning state. Large reusable bodies remain I&E-owned.

After final context conversion/order, rendering, tool schemas, token policy, aggregate request policy and auth preparation, Pi recursively snapshots the actual resolved `requestModel`, context, ordered tools, closed post-auth `requestOptions`, API key/environment/auth/config, and separate model-header/request-options-header layers. Model identity binds every current resolved Model field without a registry; unknown future fields reject v1. Header value and null-suppression semantics use tagged safe bindings, and `Models.applyAuth` auth-then-explicit override is represented only inside the options layer rather than by inventing a cross-layer merge. The original caller objects cease to be dispatch sources. Workspace supplies a matching `may_have_dispatched` receipt and Disclosure Decision; only a resident current-generation single-use prepared value can invoke. Payload replacement, invalid canonical data, credential drift, receipt mismatch, missing state, or unknown acknowledgement not resolved as present invokes nothing. The proof does not claim Adapter header merging, HTTP wire bytes, or remote receipt.

At this ADR's original acceptance, the Workspace Working Set contract was expected to own provider proof and Model Input Receipt. [ADR 0016](0016-keep-rag-ownership-local-and-admit-retrieval-deterministically.md) and the current Pi-native lifecycle contract supersede that allocation: IWS owns only Workspace application binding, disclosure/revalidation, and terminal material mapped into Pi-owned generic Provider Dispatch. I&E remains authoritative for its own 365-day exact Source Capture, Resource Capsule, Retrieval Receipt, and replay material. I&E core-package readiness does not activate Workspace consumption or bypass the Pi-native Workspace and provider-disclosure gates.

## Considered options

- Keep small Workspace state in a separate database from the beginning. Rejected for v1 because it creates cross-store coordination and recovery before state size or a second caller justifies the Seam.
- Persist raw capsules as ordinary Session/tool messages. Rejected because transcript projection, compaction, and branching would become disclosure paths and would blur I&E ownership.
- Write the Model Input Receipt after provider invocation. Rejected because a crash cannot then distinguish no send from possible send.
- Make protected whole-input replay mandatory in v1. Rejected because the I&E capsule's retention permission cannot authorize retention of User Task, Session, Orientation, tools, model options, or the complete prompt; digest-only proof deliberately makes no replay claim.

## Consequences

- Pi must provide generic save-point, ordered Session, context-policy, logical Provider Dispatch Transaction, Run settlement, lease, and recovery semantics before Workspace migration is accepted.
- Protected dispatch must deepen the current shallow Harness snapshot: recursively copy canonical data, finish request-option policy before preparation, disable payload mutation for protected calls, coordinate trusted auth identity, and never dispatch caller-owned mutable objects.
- Small v1 Workspace state follows Session branch and compaction evidence; the same eligibility policy must serve provider, compaction, and branch-summary consumers.
- Protected exact-input replay is disabled by default and requires a separate future contract plus every input owner's retention permission and a qualified protected store; v1 requires only the pre-invocation receipt and logical-artifact digest.
- Working Set state that exceeds the bounded Session-native profile requires a new owned storage contract; it must not silently expand Session entries.
- Gates are split by dependency: isolated IER1 core-package TDD may proceed under its owner; Workspace consumer implementation waits for independent PNW-A through PNW-E and TU-01 through TU-15 public-seam acceptance; real-provider disclosure additionally waits for complete IER1/IWS1 and Pi provider-dispatch acceptance.
