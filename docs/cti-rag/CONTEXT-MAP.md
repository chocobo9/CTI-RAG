# CTI-RAG Context Map

## Contexts

- [Case Management](./case-management/CONTEXT.md) - owns the long-lived investigation record and controlled changes to it.
- [Intelligence and Evidence](./intelligence-evidence/CONTEXT.md) - owns reusable sources, provenance, intelligence objects, retrieval, and enrichment.
- [Agent Investigation Workspace](./agent-workspace/CONTEXT.md) - executes a user task against a Case by assembling a task-specific working context and using investigation tools.

## Relationships

- **OpenCTI -> Intelligence and Evidence**: supplies actor-visible source objects/files, graph queries, Connector/work and enrichment outcomes through deployment-qualified Adapters. OpenCTI remains the current source authority; I&E adds immutable captures and Agent-specific derivatives rather than copying the graph.
- **OpenCTI -> Agent Investigation Workspace**: for the first read-only cycle, a qualified direct Adapter supplies an actor-scoped Case Orientation containing only OpenCTI facts it can prove. Orientation is not a Case Projection or write basis.
- **Case Management -> Agent Investigation Workspace**: in the later write-enabled architecture, supplies an item-authorized, Profile-complete, versioned Case Projection plus current Capability Grants without exposing the internal Case model. Strict writes require Case Management guarantees that stock OpenCTI does not claim.
- **Agent Investigation Workspace -> Case Management**: submits explicit Case Update Proposals; it does not mutate the Case record directly. Case Management returns an authoritative Case Update Proposal Receipt that can be reconciled by the proposal's stable identity.
- **Intelligence and Evidence -> Agent Investigation Workspace**: supplies exact Resource Capsules and complete Retrieval Receipts or bounded, actor-safe I&E Retrieval Candidate References with I&E-owned ranking and Declared Retrieval Coverage evidence. I&E never writes the Working Set, assigns a Case evidentiary role, or treats a search candidate as a committed Capsule.
- **Agent Investigation Workspace -> Intelligence and Evidence**: submits actor/purpose-bound exact or bounded retrieval only after deterministic Workspace admission. A Workspace Query Candidate is a task-derived hint, a Workspace Resource Candidate Reference is an Orientation-derived exact-selection authority, and an I&E Retrieval Candidate Reference is a separate search-result authority; none may alias or be converted through a backend identifier. Workspace compiles trusted Scope and Budget and evaluates minimum-coverage policy, while I&E proves actual coverage, lag, omissions, and index/ranking evidence. Workspace cannot select Connector, credential, parser, queue, schedule, retry, index, embedding, reranker, or publication mechanics.
- **Case Management -> Intelligence and Evidence**: Case Management owns and records Case use by referencing I&E identities rather than copying the global corpus; I&E does not record Case evidentiary roles.
