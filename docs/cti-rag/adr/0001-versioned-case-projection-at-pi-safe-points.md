---
status: accepted
---

# Use a versioned Case Projection at Pi safe points

Agent Investigation Workspace will not read the Case aggregate or persist Case state in the Pi Session. Case Management will provide an authorized, purpose-specific, revisioned Case Projection, and the Workspace will inject one ephemeral current projection into model context. The Workspace will reconcile at task admission and Pi safe points, validate freshness before consequential actions, and submit all writes as revision-checked Case Update Proposals. This keeps the Pi agent loop unchanged while preventing stale Session memory from becoming Case authority.

## Considered Options

- Re-read the full Case before every provider request: rejected because it introduces hidden context drift, latency, token churn, and poor reproducibility.
- Freeze one Case snapshot for an entire Agent Run: rejected because long tasks and collaborative Cases can use outdated human corrections, permissions, or evidence relationships.
- Persist Case projection bodies as Session messages: rejected because old truth would accumulate, survive compaction, and risk authorization leakage on resume.
- Use turn-stable projections with signal-driven delta/full reconciliation: selected because it gives a clear consistency boundary while using existing Pi hooks.

## Consequences

Case Management must provide Projection revision and controlled proposal semantics under an explicit Revision Authority. A write-enabled activation uses the same authority tuple for its Projection basis and receiver-side CAS; source Adapter observations or digests are not interchangeable revisions. Workspace must maintain Projection receipts, freshness state, deterministic rendering, and conflict handling. Exact offline replay requires either Case as-of revision reads or a separately protected Projection artifact; the normal Session alone is intentionally insufficient.

The earlier read-only Orientation cycle does not claim this Revision Authority contract. It injects a separately labeled stock-OpenCTI observation and mechanically forbids using any Orientation value as a write basis.
