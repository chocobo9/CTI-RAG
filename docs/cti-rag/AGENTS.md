# CTI-RAG Documentation Rules

## Purpose

This directory owns CTI-RAG product language, current-cycle contracts, architecture, decisions, external research, and delivery tracking. It is not a source-code directory.

## Must Read

- Read `README.md` first; its normative precedence and rule-ownership table govern all documents here.
- Read `CONTEXT-MAP.md` and the affected bounded context's `CONTEXT.md` before introducing or changing domain terms.
- For Agent Workspace work, read `agent-workspace/PROGRESS.md` and the active current-cycle contract before target-architecture documents.

`CONTEXT-MAP.md` maps bounded contexts and their relationships. It is not the repository Code Map; code routing belongs in the root `AGENTS.md` and local `AGENTS.md` files.

## Document Ownership

- Current-cycle contracts own exact schemas, invariants, failures, and acceptance cases.
- `agent-workspace/context-projection-design.md` owns architecture relationships and links to exact contracts; it must not copy closed field lists or transition tables.
- Bounded-context `CONTEXT.md` files own stable canonical language, not implementation plans.
- `agent-workspace/PROGRESS.md` owns delivered/current/next/deferred state, not normative behavior.
- `adr/` owns accepted cross-module or hard-to-reverse decisions and their consequences.
- `research/` owns sourced external facts and candidate conclusions; recommendations remain non-normative until adopted.

## Synchronization Discipline

- Put a discussed candidate only in `PROGRESS.md` under the current cycle.
- Put confirmed behavior in its owning normative contract and add the corresponding behavioral acceptance case.
- Put a stable, repeatedly used term in the relevant `CONTEXT.md` without implementation detail.
- Add or supersede an ADR for a long-lived cross-module constraint or difficult-to-reverse decision.
- Record external investigation in `research/` with primary sources and an explicit design disposition.
- When work finishes, move it from current work to confirmed/delivered or deferred in `PROGRESS.md`.

## Duplication and Scope

- Link to the single owner instead of repeating exact rules across overview, progress, glossary, ADR, and research.
- Preserve frozen strict-R1 contracts and ADRs 0007 through 0010 as target architecture; they are not current-cycle dependencies.
- Do not infer implementation completion from a documentation acceptance catalog. Record only executable evidence in `PROGRESS.md`.
- Do not prematurely fix model-visible LLM tool count or decomposition.

## Escalation

A change to authority, dependency direction, cross-context ownership, or a normative protocol must update all directly affected owners and use an ADR when the decision is durable or hard to reverse.
