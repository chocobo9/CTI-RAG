# CTI-RAG Design Documentation

This directory separates current delivery contracts from target architecture, domain language, decisions, research, and work tracking. Read this file before treating repeated wording elsewhere as an implementation requirement.

## Normative precedence

When documents disagree, use this order:

1. **Current-cycle contract**: the exact schema, invariants, failures, and acceptance cases for the slice being implemented.
2. **Accepted ADR**: a cross-module or hard-to-reverse decision and its rationale.
3. **Architecture overview**: system shape, seams, ownership, and long-term constraints.
4. **Domain language**: canonical meanings only; `CONTEXT.md` is not a specification.
5. **Progress**: delivery state and next work; it does not restate normative rules.
6. **Research**: primary-source facts and design input; recommendations are non-normative unless adopted above.

More specific current-cycle contracts override coarse representative types in the architecture overview. A frozen target-architecture contract does not become a current-cycle dependency merely because it is more detailed.

## Navigation

### Current delivery cycle

- [Pi-native Agent Workspace Lifecycle v1](agent-workspace/pi-native-workspace-lifecycle-v1-contract.md) - PNW-A1, the narrower PNW-A2.1 restricted-facade/configuration subset, PNW-A2.2's persisted-entry context-policy subset, PNW-A3.1's AI-owned auth-resolved deferred-start `prepareSimple` seam, and PNW-A4's generic Session control-batch Interface have each passed independent implementation acceptance. The closed Agent Run settlement evidence target in section 5.1 now has independent design PASS only. A3.2, settlement implementation, PNW-A overall, Pi-native Workspace migration, Workspace I&E consumption/Working Set, and real-provider activation remain NO-GO.
- [Pre-Investigation Task Understanding v1](agent-workspace/pre-investigation-task-understanding-v1-contract.md) — independent design and focused implementation/public-seam PASS for one bounded no-tool model call, immutable Original User Task, deterministic admission/clarification, atomic committed handoff, exact-count evidence, and 1–4 Run goal seeds. PNW-C and Integrated PASS remain NO. The earlier [Task Context Understanding v1](agent-workspace/task-context-understanding-v1-contract.md) same-Agent-Run planning design is superseded before implementation.
- [Initial Investigation Context v1](agent-workspace/initial-investigation-context-v1-contract.md) — superseded seven-section serialized candidate retained as reference-only; its duplicate record/digest/projection design is not authorized.
- [Workspace Run Context Preparation v1](agent-workspace/workspace-run-context-preparation-v1-contract.md) — Design PASS for the middle layer that maps the currently needed logical inputs into Pi-owned system, message, Session-history, Tool, and Provider Dispatch seams without creating a second Agent Context. It binds Workspace evidence to Pi's actual prepared digests through the existing application-authority Interface; implementation readiness remains gated by prerequisite delivery and the active Workspace kill-switch checkpoint.
- [Workspace Runtime Composition v1](agent-workspace/workspace-runtime-composition-v1-contract.md) — Design PASS for the distinction between a durable/reopenable Pi Session and one non-durable Workspace-lifetime Harness reconstructed per successful `open`. It freezes acquisition, reconstruction, reuse, close/release and staging-path deletion behavior; implementation remains NO.
- [Workspace Memory Coordination v1](agent-workspace/workspace-memory-coordination-v1-contract.md) — superseded design input. Its qualification, revalidation, routing and adoption behavior will be incorporated into the first-class Agent Memory Management contract under [ADR 0021](adr/0021-make-memory-management-a-first-class-agent-module.md).
- [Agent Memory Management v1](agent-workspace/agent-memory-management-v1-contract.md) - first-class Memory design candidate; implementation is not authorized until the contract and E2E gates are accepted.
- [CTI Agent E2E Validation Research](research/cti-agent-e2e-validation-2026-07-26.md) - layered deterministic, trajectory, LLM-as-judge, and CTI expert validation input.
- [Case Persistence v1](case-management/case-persistence-v1-contract.md) — candidate storage-agnostic Case Repository design. SQLite is the recommended local/single-host Adapter; PostgreSQL remains the later multi-writer production Adapter, and no vector database is required for authoritative Case state or revision reads. Implementation is not authorized until Case Management has a code owner, its first State profile is frozen, and the SQLite runtime/driver is qualified.
- [Access Principal and Use Purpose terminology revision](agent-workspace/access-principal-use-purpose-terminology-revision.md) — accepted naming decision that replaces access-domain `actor`/`purpose` with `AccessPrincipalBinding`, `principalRef`, and `usePurpose`, while separating Case mandate, task objective, context consumer, and operation intent. Cross-contract and persisted-receipt migration remains gated.
- [Investigation Run Control v1](agent-workspace/investigation-run-control-v1-contract.md) — independent design PASS for multi-goal Run control, target-neutral Query Candidates, local adjustment, capability admission, five-dimensional budgets, and closed settlement dispositions. Implementation remains NO-GO.
- [Task Result v1](agent-workspace/task-result-v1-contract.md) — Design Gate FAIL candidate for the first post-settlement handoff: one private durable Workspace result with per-goal achieved/incomplete work, classified source-fact/analysis/question/status statements, trusted Save Point basis and no Case/evidence/publication authority. It requires Run Control/Publication and PNW settlement amendments before implementation.
- [Evidence Assembly v1](agent-workspace/evidence-assembly-v1-contract.md) — Design Gate FAIL candidate for the second report handoff: one private Workspace seam that revalidates already admitted Working Set material through I&E and assembles a bounded Claim-Evidence Subgraph while keeping vector hits, graph paths, task-candidate relationships and Case Evidence References distinct.
- [Report Evidence Packet v1](agent-workspace/report-evidence-packet-v1-contract.md) — Design Gate FAIL candidate for the third report handoff: one ephemeral, consumer/profile/attempt-bound Workspace projection with a non-content receipt, exact owner revalidation and reuse of Pi's bounded one-shot Provider Dispatch frontend for a no-tool Composer.
- [Task Outcome Report v1](agent-workspace/task-outcome-report-v1-contract.md) — Design Gate FAIL candidate for the fourth/public handoff: five closed route-specific report variants, bounded structured composition, deterministic rendering, narrow independent evidence audit and strict separation from Case acceptance.
- [Task Outcome Publication Stream v1](agent-workspace/task-outcome-publication-stream-v1-contract.md) — Design Gate FAIL versioned amendment that atomically commits the complete qualified report and deterministic chunk manifest before any public content, then supports freshly authorized delivery/resume without replaying a Provider or Composer.
- [Workspace Output Publication v1](agent-workspace/workspace-output-publication-v1-contract.md) — independent design PASS for private response candidates, publish-or-withhold decisions, validated non-authoritative output, and zero raw candidate disclosure before the publication gate. Implementation remains NO-GO.
- [Agent Investigation Product Workflow v1](agent-workspace/agent-investigation-product-workflow-v1-contract.md) — design candidate for the product-level path from small-model task understanding and structured route classification through Quick Response or Formal Investigation, Save Point-backed progress, mandatory route-appropriate Task Outcome Reports, deterministic validation, narrow evidence audit and admitted output streaming. Its Design Gate remains FAIL pending intake/admission/model thresholds, Case bootstrap ownership, report/auditor qualification and the Publication streaming amendment.

- [`opencti-case-orientation/v1` Contract](agent-workspace/opencti-case-orientation-v1-contract.md) — delivered stock-OpenCTI actor-scoped data/safety baseline and OR acceptance catalog, incorporated by the sole current lifecycle contract above.
- [Design progress](agent-workspace/PROGRESS.md) — current cycle, confirmed decisions, frozen work, and exit criteria.
- [Private implementation package](../../packages/cti-rag-agent-workspace/package.json) — current `CaseWorkspace` and Orientation foundation; implemented coverage is tracked in PROGRESS rather than inferred from the full OR catalog.

### I&E core and gated integration

- [I&E Platform Design](intelligence-evidence/intelligence-evidence-platform-design.md) — OpenCTI-first derived Module, authority allocation, state, failure model, validation, trade-offs, and delivery order.
- [`opencti-exact-resource-retrieval/v1`](intelligence-evidence/opencti-exact-resource-retrieval-v1-contract.md) — active I&E core contract; isolated package TDD is ready but not started. It authorizes no Workspace import, live OpenCTI activation, provider disclosure or deferred capability.
- [`evidence-assembly-exact-revalidation/v1`](intelligence-evidence/evidence-assembly-exact-revalidation-v1-contract.md) — Design PASS, implementation-readiness-NO I&E profile behind the existing `retrieve(...)` Interface. It revalidates up to 32 exact Working Set-derived subjects and returns signed assertion/relationship/lineage/coverage qualification without search, model calls, source substitution or a new root method.
- [`intelligence-working-set/v1`](agent-workspace/intelligence-working-set-v1-contract.md) — frozen design input for its non-provider exact-resource admission, Working Set, render, and future application-disclosure semantics. Cross-context coordination has accepted deterministic Workspace admission, distinct Workspace/I&E candidate authorities, and an application Adapter into Pi-owned Provider Dispatch. Its earlier provider-proof candidate remains reference-only and superseded pending a new independent cross-owner review; consumer implementation and real-provider disclosure remain NO-GO.
- [I&E progress](intelligence-evidence/PROGRESS.md) — core readiness, integration gates, and deferred platform scope.

The Pi-native lifecycle contract is the sole current-cycle authority for generic provider proof. The frozen Working Set contract's `prepare/commit/lookup`, `preparedRef`, credential-revision assumptions, provider canonicalization/receipt schemas, and related acceptance wording are reference-only and superseded; future activation requires a generic Adapter mapping and independent cross-owner re-review. I&E retains its separate 365-day Source Capture/Resource Capsule/Retrieval Receipt replay-material rule. Complete-prompt replay remains deferred.

### Architecture overview

- [Agent Investigation Workspace Case Context Projection](agent-workspace/context-projection-design.md) — overview of the Workspace, Pi seams, context authority, operation dependencies, and target delivery sequence.

The overview owns architectural relationships. It must link to exact contracts rather than copy their closed field lists, failure codes, transition tables, or acceptance cases.

### Frozen strict-R1 target contracts

These contracts preserve the reviewed design for a later write-enabled cycle. They are not prerequisites for the Orientation-first cycle and should change only when executable evidence disproves an invariant or the product deliberately reopens strict R1.

- [`opencti-case-projection/v1` Contract](agent-workspace/projection-profile-v1-contract.md)
- [Case Management Facade Command and Receipt Contract](agent-workspace/case-management-facade-contract.md)
- [Durable Operation Journal Contract](agent-workspace/durable-operation-journal-contract.md)

### Domain language

- [Context map](CONTEXT-MAP.md)
- [Agent Investigation Workspace](agent-workspace/CONTEXT.md)
- [Case Management](case-management/CONTEXT.md)
- [Intelligence and Evidence](intelligence-evidence/CONTEXT.md)

### Decisions

- [`adr/`](adr/) records accepted architectural decisions. ADR 0002 establishes OpenCTI-first Orientation; ADR 0011 retains stale-history safety; ADR 0012 selects Pi as the Workspace execution spine; ADR 0013 establishes OpenCTI-first I&E derivation; ADR 0014's same-Agent-Run Task Context design is superseded by ADR 0017's bounded pre-Investigation Task Understanding workflow; ADR 0015 selects Session authority for small v1 Workspace state and requires pre-invocation proof; ADR 0016 keeps RAG ownership local, gives Workspace deterministic retrieval admission, and routes generic Provider Dispatch proof exclusively through Pi; ADR 0018 keeps memory as an owner-local architecture view rather than a shared authority. ADRs 0007–0010 are retained for the later strict-R1 target.

ADR 0019 reserves Threat Actor for CTI meaning and names access identity/use
authorization explicitly as Access Principal and Use Purpose.

ADR 0020 keeps Provider/report-candidate deltas private and permits progressive
delivery only from a complete immutable Task Outcome Report whose publication
receipt is already committed.

[ADR 0022](adr/0022-select-sqlite-store-and-git-markdown-memory-source.md)
selects SQLite as the first local-host Memory Store and Git-backed Markdown as
the user-editable Memory Source; the actual SQLite Adapter remains
qualification-gated.

### Research

- [`research/`](research/) contains primary-source findings and candidate designs. Research is retained even when a recommendation is superseded.
- [Pi context capability reuse audit](research/pi-context-capability-reuse-audit-2026-07-22.md) records which Agent Context, Session, history-policy, Tool and Provider Dispatch capabilities must be reused.
- [Case storage SQLite fit](research/case-storage-sqlite-fit-2026-07-22.md) records the local-storage fit, durability limits and pinned-runtime qualification gap.
- [DeepSeek report-composer fit](research/deepseek-report-composer-fit-2026-07-22.md) records current official model capabilities, alias retirement, structured-output caveats and the candidate `deepseek-v4-pro` non-thinking report-composition profile.
- A research note's explicit `Design disposition` controls its candidate recommendations. Without one, its source facts remain usable but its recommendations are non-normative.
- The OpenCTI read, authorization, pagination, stream, and history findings support the current Orientation contract. Direct-write recommendations in research are not active; the accepted strict-R1 contracts and ADRs govern any future write-enabled activation.

## Rule ownership

| Rule | Single owner | Other documents may contain |
|---|---|---|
| Pi-native Workspace lifecycle, seam migration, generic Provider Dispatch proof, and PNW acceptance | Pi-native lifecycle contract | Orientation/Working Set safety links and architectural rationale |
| Original User Task, Task Understanding Proposal, Admitted Task Context, clarification, committed handoff, and Task Understanding acceptance | Pre-Investigation Task Understanding contract | lifecycle integration and PNW-C handoff links |
| Initial Investigation Context concrete sections, mandatory owner-local reconstruction, channel mapping, rendering, failure closure, and IIC acceptance | Initial Investigation Context contract | lifecycle sequencing, Run binding, and architecture rationale |
| Investigation goals, subquestions, target-neutral Query Candidates, capabilities, Run budgets, stop dispositions, and Run Control acceptance | Investigation Run Control contract | lifecycle and publication links |
| Model Response Candidate, Workspace Publication Decision, Published Workspace Output, disclosure gate, and publication acceptance | Workspace Output Publication contract | lifecycle and citation-owner links |
| Qualified Task Outcome Report atomic commit, deterministic chunk delivery, authorization-fenced resume, and terminal report mapping | Task Outcome Publication Stream contract | baseline Publication safety links and product-workflow rationale |
| Orientation fields, presence, observation proof, failures, acceptance | Orientation contract | link and purpose summary |
| I&E internal Module shape, state allocation, and delivery sequence | I&E Platform Design | cross-context relationship links |
| Exact OpenCTI Resource retrieval fields, budgets, failures, acceptance | I&E exact-resource contract | architecture rationale |
| Retrieval-to-Working-Set admission, Working Set state/render, and future application disclosure semantics | Intelligence Working Set contract | generic provider-proof Adapter links to the Pi-native lifecycle contract |
| Full composed Projection schema | Projection Profile contract | architectural rationale |
| Strict command/receipt semantics | Facade contract | ownership summary |
| Durable effect/recovery transitions | Journal contract | operation-dependency rationale |
| Cross-module decision and trade-off | ADR | link and consequence summary |
| Canonical term meaning | context glossary | exact term usage |
| Access Principal/Use Purpose naming and semantic migration | terminology revision plus ADR 0019 | owner-contract field revisions and compatibility evidence |
| Current/next/deferred work | `PROGRESS.md` | no duplicated contract rules |
| External fact and source citation | research note | adopted decision link |

## Change discipline

- Candidate work goes only in `PROGRESS.md` under Current cycle.
- Confirmed behavior goes in the owning normative contract with an acceptance case.
- Stable domain-specific language goes in the relevant `CONTEXT.md` without implementation detail.
- Hard-to-reverse cross-module decisions use an ADR.
- Research keeps its original evidence and gains a disposition instead of being rewritten as current design.
- Model-visible LLM tool count and decomposition remain deliberately unfixed.
