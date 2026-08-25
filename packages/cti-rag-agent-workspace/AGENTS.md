# CTI-RAG Agent Workspace Rules

## Ownership

This private package owns the Agent Investigation Workspace Module: `CaseWorkspace`, `WorkspaceTurn`, actor-scoped OpenCTI Orientation materialization, Workspace context injection, and the Adapter ports needed by the active CTI-RAG delivery slice.

## Must Read, in Order

1. `../../docs/cti-rag/AGENTS.md`
2. `../../docs/cti-rag/README.md`
3. `../../docs/cti-rag/CONTEXT-MAP.md`
4. `../../docs/cti-rag/agent-workspace/CONTEXT.md`
5. `../../docs/cti-rag/agent-workspace/PROGRESS.md`
6. The current lifecycle target: `../../docs/cti-rag/agent-workspace/pi-native-workspace-lifecycle-v1-contract.md`
7. The Task Understanding contract: `../../docs/cti-rag/agent-workspace/pre-investigation-task-understanding-v1-contract.md`
8. The Run Control contract: `../../docs/cti-rag/agent-workspace/investigation-run-control-v1-contract.md`
9. The Output Publication contract: `../../docs/cti-rag/agent-workspace/workspace-output-publication-v1-contract.md`
10. The retained behavioral baseline: `../../docs/cti-rag/agent-workspace/opencti-case-orientation-v1-contract.md`
11. If changing the Pi seam: `../../docs/cti-rag/agent-workspace/context-projection-design.md`, `../agent/AGENTS.md`, `../agent/README.md`, the relevant file under `../agent/docs/`, and the focused Harness/Session tests that prove the affected seam.

`task-context-understanding-v1-contract.md` is superseded reference-only and never implementation authorization.

Frozen or deferred documents do not authorize implementation merely because they are detailed.

## Placement

- Keep the public deep-module seam in `src/case-workspace-module.ts`, public types in `src/types.ts`, and supported exports in `src/index.ts`.
- Put closed wire/materialization schemas in `src/schemas/` and validation/canonicalization behind the package boundary.
- Put reusable test Adapters only under `src/testing/` and export them only through the `./testing` package entrypoint.
- Keep OpenCTI transport DTOs and deployment-specific mapping behind an Adapter. They must not leak through `CaseWorkspace`.

## Dependency Boundary

- Allowed Pi dependencies are only `@earendil-works/pi-agent-core` and `@earendil-works/pi-ai`.
- Do not depend on `pi-coding-agent`, `pi-tui`, `pi-orchestrator`, Case Management internals, or Intelligence and Evidence internals.
- Integrate another bounded context through an explicit port and its owning contract, not shared database objects or internal imports.

## Active and Frozen Scope

- Active scope is the Pi-native lifecycle and accepted Task Understanding, Investigation Run Control, and Workspace Output Publication designs recorded in `PROGRESS.md`: deepen the required generic Pi seams first, then migrate the read-only Orientation Workspace without weakening accepted safety behavior.
- Full `opencti-case-projection/v1`, the Case Management Facade, `ResourceUsePermitV1`, Durable Operation Journal, strict R1 writes, and ADRs 0007 through 0010 are frozen target architecture.
- I&E Retrieval, executable Query Candidate dispatch, Working Set, Assessment, and concrete model-visible product investigation-tool decomposition remain frozen until the Pi-native lifecycle and the three Workspace contract implementation gates pass.
- Do not expand frozen work, invent Case authority, or use Orientation as a write basis during the read-only cycle.
- Model-visible LLM tool count and decomposition remain unfixed.

## Tests

- Test behavior only through the public `CaseWorkspace`/`WorkspaceTurn` seam; do not assert private implementation calls.
- Production-shaped and in-memory Adapters must run the same contract fixtures and yield the same public results.
- Use the faux provider and in-memory infrastructure; never call a paid model API or live OpenCTI deployment in the ordinary suite.
- Map executable tests to the owning contract's acceptance identifiers and do not claim unexecuted OR cases as delivered.

## Escalation

Stop and update the owning design before changing a normative schema, authority boundary, Pi Harness seam, dependency direction, or frozen/deferred scope. Cross-context decisions require the relevant contract and, when hard to reverse, an ADR.
