---
status: accepted
---

# Use Pi Harness as the Agent Workspace execution spine

One open `CaseWorkspace` uses one fenced lease from a Pi-owned opaque-reference `SessionRepository`, one Pi Session, and one long-lived `AgentHarness`. Pi owns the model-tool loop, transcript, save-point/control/Agent-Run-settlement transactions, repository/lease lifecycle, compaction, branch navigation, run-generation fencing, and ordered Session mutation; Agent Workspace supplies CTI binding, context, authorization, eligibility, tool, receipt, and publication policy through Pi seams. This replaces the delivered per-`WorkspaceTurn` staging Harness as the target because that mechanism preserves read safety but duplicates lifecycle and prevents natural use of Pi tools and save points.

## Considered Options

- Keep one private Session/Harness per public Turn. Rejected as the target because every new Pi capability would need a parallel Workspace protocol.
- Let one Harness write the current caller Session directly. Rejected because Pi currently persists at `message_end`, before the CTI completion fence.
- Permanently implement transaction, pending-write, context-view, and abort fencing inside the CTI package. Rejected because these are generic Harness responsibilities and would preserve mixed ownership.
- Deepen Pi with opt-in save-point, independent control, and Agent Run settlement transactions; an opaque-reference repository/fenced lease; ordered Session facade/context policy; and bounded run-generation settlement. Selected because Pi retains lifecycle locality while Workspace policy remains product-specific.

## Consequences

Slice 0b remains the required safety baseline, but its PASS is not Pi-native acceptance. Migration starts in `packages/agent/`, including repository/lease and exact save-point/control/Run-settlement boundaries; then it moves Workspace to one long-lived Harness, proves a real deterministic tool/save-point path, qualifies compaction/tree views, migrates signed context-generation checkpoints, and finally removes raw caller `Session` authority. Planned Pi designs are not treated as implemented.

Here “long-lived Harness” means one non-durable Workspace-lifetime Harness per
successful `open`. The Pi Session is the durable/reopenable object; a later
Workspace open reconstructs a new Harness under a new Session lease generation.

ADR 0011's decision to retain audit history and mechanically exclude ineligible prose remains accepted. This ADR supersedes its per-Turn private staging-Harness mechanism and refines the standalone stale/protected marker into the signed context-eligibility protocol described by the current-cycle contract.
