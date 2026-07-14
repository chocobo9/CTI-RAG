# Agent-Ready Issues: OTX Event Discovery

Parent: `docs/prd/otx_event_discovery_prd.md`

Status: completed 2026-07-12. Final acceptance is recorded in
`docs/otx_raw_collection_status.md` and
`data/processed/otx_actor_event_dataset_routeA_20260712/dataset_manifest.json`.

## Issue 1: Audit the Event-discovery contract

### What to build

Produce a read-only integration report mapping the current collector, raw-store
artifacts, source-claim normalization, Event-IOC projection, and reference TRAIL
pipeline to the PRD. Identify exact reusable public seams and contradictions.

### Acceptance criteria

- [x] Report distinguishes collection provenance, source claims, Event-IOC observations, attribution assessment, and support enrichment.
- [x] Report identifies code that must not be reused: ambiguous filtering, DST/confidence, Actor-IOC flattening, and enrichment.
- [x] Report recommends the smallest integration seam and targeted regression tests.
- [x] Audit work remained read-only when performed.

### Blocked by

None.

## Issue 2: Build offline source-claim artifacts

### What to build

Add a narrow public offline builder that consumes local OTX Pulse details plus a
MITRE actor taxonomy and emits one Event row plus preserved source-attribution
claim rows. It must retain all source states and must not calculate confidence,
filter Events, create Actor-IOC claims, or call the network.

### Acceptance criteria

- [x] Every selected input Pulse emits an Event row, including ambiguous, multi-actor, and unmapped claims.
- [x] Claim rows preserve raw values, source field, resolution state, candidate/resolved actor ids, and raw provenance.
- [x] Output distinguishes single, alias-collapsed, multi, taxonomy-ambiguous, parse-ambiguous, and unmapped states.
- [x] Public-interface tests were written test-first and pass offline.
- [x] Final integration reconciled shared exports and documentation.

### Blocked by

None; main-agent integration will reconcile the audit.

## Issue 3: Split collector phases at the candidate-Event seam

### What to build

Refactor the actor-seeded collector so discovery can complete independently,
producing a deduplicated candidate-Event manifest with merged query provenance.
Pulse-detail acquisition and optional indicator-endpoint pagination must be
separately selectable and resumable without changing existing raw-store identity.

### Acceptance criteria

- [x] Discovery-only mode calls search endpoints but never Pulse-detail or indicator endpoints.
- [x] Candidate manifest contains one row per Pulse id with every discovery path retained.
- [x] Routed detail acquisition consumes source-evidenced decisions and preserves multi/ambiguous states.
- [x] Endpoint mode remains optional, explicitly bounded, and separate from discovery completeness.
- [x] Existing serial behavior remains available while mixed pagination and bounded concurrency are explicit.
- [x] Public CLI/collector tests were written test-first and pass offline.
- [x] Final integration reconciled shared exports and documentation.

### Blocked by

None; main-agent integration owns shared exports and documentation.
