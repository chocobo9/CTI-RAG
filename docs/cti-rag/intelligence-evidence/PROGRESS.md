# Intelligence and Evidence Progress

Updated: 2026-07-22

This file records delivery state only. Exact behavior belongs to the owning contract, architecture to the [platform design](intelligence-evidence-platform-design.md), terms to `CONTEXT.md`, cross-context decisions to ADRs, and external facts to research.

## Confirmed design

- [ADR 0013](../adr/0013-use-opencti-as-ie-primary-infrastructure.md) establishes OpenCTI as primary CTI infrastructure and I&E as a derived deep Module.
- The root Code Map routes I&E implementation to `packages/cti-rag-intelligence-evidence/`; that package does not yet exist.
- OpenCTI owns current source graph/files/markings/access and infrastructure operations. I&E owns immutable captures, derivatives, supplemental lineage, bounded request admission and retrieval evidence.
- Workspace owns Working Set, Disclosure Decision and Model Input Receipt. Pi owns the logical provider invocation transaction; neither claims provider-specific wire bytes or complete-prompt replay. Case Management owns evidentiary roles and accepted conclusions.
- The Agent can request typed bounded outcomes but has no Connector, schedule, queue, credential, parser, retry or publication control.
- The raw corpus is candidate input only. Local OpenCTI currently supplies a MITRE ATT&CK seed; no repeated import is required.

## Accepted active core slice

- I&E core: [`opencti-exact-resource-retrieval/v1`](opencti-exact-resource-retrieval-v1-contract.md).
- Core vertical: one existing ATT&CK object -> capture -> structured span/segment -> signed exact receipt/capsule, exercised through production-shaped and in-memory Adapters.
- Gated Workspace consumer: [`intelligence-working-set/v1`](../agent-workspace/intelligence-working-set-v1-contract.md).
- Integrated vertical: trusted Resource Candidate binding -> IER1 -> Pi Session atomic Working Set entry -> exact-capture disclosure revalidation -> Model Input Receipt/logical invocation proof.
- The contract intentionally excludes file/OCR, semantic search, embeddings, Connector dispatch and model-based extraction.

## Implementation gates

I&E core design readiness: **Independent review PASS**. The Code Map route, local rules, active IER1 Interface, private operation-store/lease semantics, exact/replay/cancellation paths, budgets, failure semantics, retention, trust dependencies, acceptance IDs and first core vertical are closed.

IER1 core package TDD: **READY, not started in this design session**. It may create only `packages/cti-rag-intelligence-evidence/`, depend on no Workspace implementation, use no live OpenCTI in ordinary tests, and expose only the active core Interface. This readiness is not authorization for ingestion, production activation or any deferred capability.

The report-chain
[`evidence-assembly-exact-revalidation/v1`](evidence-assembly-exact-revalidation-v1-contract.md)
profile now has **Design PASS / implementation readiness NO**. It adds one
closed request/outcome union member behind the existing `retrieve(...)`
Interface for at most 32 exact Working Set-derived subjects. It returns signed
current material, Source Span/assertion, source-relationship, lineage-pair and
coverage qualification without search, substitution, model calls, source
bodies or Case meaning. It does not authorize implementation before IER1/core
and Workspace consumer prerequisites pass.

Workspace consumer/Working Set implementation: **NO-GO** until PNW-A through PNW-E and TQ-01 through TQ-21 independently pass through the public Workspace seam, focused Pi/Workspace verification passes under Node 24.14, and the root repository check passes. Current moving PNW code is not acceptance evidence until its owning session records independent PASS.

Real-provider Working Set disclosure: **NO-GO** until the preceding gate plus complete IER1/IWS1 and Pi provider-dispatch public-seam acceptance pass. Exact full-prompt replay remains deferred.

## Validation required during implementation

- Production-shaped and in-memory OpenCTI Adapters pass the same IER1 fixture catalog.
- Core acceptance runs every IER1 fixture through the public I&E Interface without importing Workspace.
- Later Workspace integration passes the same receipt through its public `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn` seam.
- Focused tests cover timeout/ignored abort, drift/revocation, duplicate/conflict, commit crash windows, late results, tampering, retention and disjoint concurrency.
- Numeric budgets and actor-safe failures match the accepted contracts.
- Root `npm run check` passes after code changes; no live OpenCTI or paid model is used in ordinary tests.

## Deferred

- OpenCTI files, PDFs, OCR and page/text coordinate contract.
- Lexical/semantic/vector search, embeddings, reranking and production Index Generation.
- Agent-requested native OpenCTI enrichment and any Connector job reconciliation.
- Source-by-source raw corpus qualification, production Connector activation and bulk ingestion.
- Generic capability/workflow engine, recursive enrichment and production multi-worker deployment.
- Entity merge, automated attribution/corroboration, Assessment/ACH, Case writes, ResourceUsePermit, Durable Journal, strict R1 and external publication.
- Concrete model-visible tool count and decomposition.
