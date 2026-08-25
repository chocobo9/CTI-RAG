# Intelligence and Evidence Documentation Rules

## Purpose

This directory owns I&E domain language, internal architecture, current or gated delivery contracts, and I&E progress. It does not own OpenCTI infrastructure, Workspace state, Case authority, or product code outside the I&E Code Map route.

## Must Read, in Order

1. `../AGENTS.md`
2. `../README.md`
3. `../CONTEXT-MAP.md`
4. `CONTEXT.md`
5. `PROGRESS.md`
6. `intelligence-evidence-platform-design.md`
7. The active or gated contract named by `PROGRESS.md`
8. `../agent-workspace/CONTEXT.md`, `../agent-workspace/pi-native-workspace-lifecycle-v1-contract.md`, `../agent-workspace/task-context-understanding-v1-contract.md`, and `../agent-workspace/intelligence-working-set-v1-contract.md` for a Workspace consumer or activation change
9. `../case-management/CONTEXT.md` and `../agent-workspace/PROGRESS.md` for cross-context work
10. Relevant notes under `../research/` for external facts

## Rule Ownership

- `intelligence-evidence-platform-design.md` owns I&E internal Module shape, Adapters, state allocation, delivery sequence, and trade-offs.
- A delivery contract owns exact Interface fields, budgets, failures, invariants, and acceptance IDs for its slice.
- `CONTEXT.md` owns stable I&E language only.
- `PROGRESS.md` owns delivered, gated, current, and deferred state only.
- External OpenCTI or source facts remain in `../research/` and are non-normative until adopted.

## Non-negotiable Boundaries

- OpenCTI is the primary CTI infrastructure and current source-resource authority. Do not build a second editable CTI graph, Connector control plane, or Case store.
- I&E owns only reusable Resource identity/version mapping, Source Captures, derivatives, supplemental Provenance/Source Lineage, retrieval evidence, and bounded enrichment admission.
- The Agent may request typed bounded outcomes. It may not choose credentials, Connector deployment, schedule, reset, queue, parser, index, retry, or publication policy.
- I&E never writes a Working Set or assigns a Case evidentiary role. Workspace owns selection and model-input assembly; Case Management owns Resource/Evidence References and formal conclusions.
- `ResourceUsePermit` remains frozen strict-R1 target architecture and is not a read-path prerequisite.
- Model-visible tool count and decomposition remain unfixed.
- A Task Context Query Candidate is non-executable. Only trusted Workspace code may compile a current Resource Candidate Reference and qualified capability activation into an exact I&E request.

## Activation Gates

- IER1 core package TDD is independent from PNW/TQ implementation. It may exercise only the public I&E Interface, private store/signing/clock Ports, and production-shaped plus in-memory OpenCTI Adapters.
- Workspace retrieval consumption and Working Set mutation remain gated by PNW-A through PNW-E and TQ-01 through TQ-21 public-seam acceptance.
- Real-provider disclosure remains gated by the complete IER1/IWS1 vertical and the Pi provider-dispatch proof.
- A core-package gate never authorizes a Workspace import, provider call, live OpenCTI activation, ingestion, Connector change, or production publication.

## Verification Discipline

- Test a Module only through its public Interface and run the same semantic fixtures through production-shaped and in-memory Adapters.
- A partial capture, derivative, index generation, retrieval, or enrichment result is not publishable unless the owning contract predeclares independently complete slots.
- OpenCTI `work`, Stream, History, timestamps, and semantic de-duplication are evidence, not I&E operation identity, snapshot, or replay proof.
- Do not call live OpenCTI, import data, alter Connector state, or read credentials in ordinary tests.
- Frozen/deferred scope does not become implementation authorization through detail in the architecture.
