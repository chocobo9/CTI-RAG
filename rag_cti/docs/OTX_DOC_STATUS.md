# OTX Document Status

Updated: 2026-07-12

## Current authority

Read these in order:

1. `docs/otx_raw_collection_status.md` — final collection statistics and scope.
2. `docs/implementation/otx_actor_event_dataset_contract.md` — teammate-facing
   data contract and Event/claim/indicator-summary semantics.
3. `data/processed/otx_actor_event_dataset_routeA_20260712/dataset_manifest.json`
   — machine-readable population, coverage, and hashes.
4. `docs/CONTEXT.md` — ubiquitous language and layer boundaries.
5. `docs/source_ingestion_design.md` — cross-source raw collection strategy.

## Supporting implementation evidence

- `docs/prd/otx_event_discovery_prd.md`
- `docs/implementation/otx_event_discovery_contract_audit.md`
- `docs/implementation/otx_full_discovery_readiness.md`
- `docs/implementation/otx_plan_evidence_trace.md`
- `data/raw/otx_collection_runs/actor_evidenced_detail_20260711/final_audit.json`

## Historical snapshots

The following record earlier calibration/snapshot states and must not be used
for current counts:

- `docs/archive/otx/SNAPSHOT_20260710_otx_event_discovery_acceptance_4160.md` — 4,160-detail calibration.
- `docs/archive/otx/SNAPSHOT_20260710_otx_indicator_summary_4160.md` — 4,160-detail indicator profile.
- the initial/failure sections of `docs/implementation/otx_full_discovery_readiness.md`.
- `docs/archive/otx/HISTORICAL_otx_paper_mapping_status.md` and
  `docs/archive/otx/HISTORICAL_otx_mapping_grill.md`.

## Reading rules

- A query match is discovery provenance, not actor attribution.
- A discovery candidate is one unique Pulse ID, not an attributed Event.
- Current detail population is the 5,558 `acquire_*` rows in the routing
  manifest, not every candidate and not an old checkpoint population.
- Preserve multi-actor, ambiguous, unmapped, and deferred evidence.
- `sample_code.py` and TRAIL define a useful Event-centered graph shape, but
  their pre-graph ambiguity filtering is not inherited by this project.
- IOC flattening and enrichment are downstream, not OTX raw gathering.
