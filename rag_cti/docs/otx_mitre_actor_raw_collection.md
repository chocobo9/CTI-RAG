# OTX MITRE Actor Raw Collection

This is the canonical OTX raw collection path for actor-centric datasets.

Current data snapshot:

```text
docs/otx_raw_collection_status.md
data/raw/otx_collection_runs/routeA_20260704_policy_small_first/RUN_STATUS.md
```

The current phase is complete for actor/name/alias discovery and
actor-evidenced Pulse-detail gathering: 577 queries have terminal states,
31,390 unique Pulse candidates remain auditable, and all 5,558 routed Events
have valid detail. Current counts are authoritative in
`docs/otx_raw_collection_status.md`.

## Goal

Layer 0 must preserve OTX source responses before any projection or graph
construction. The collector therefore stores raw endpoint responses first, then
lets processed artifacts be rebuilt from those raw records.

The MITRE actor list is used only as the discovery input. A search hit is not
an actor label by itself.

## Source Inputs

- MITRE ATT&CK STIX bundle: `data/raw/mitre/enterprise-attack.json`
- OTX API key: `OTX_API_KEY`, or `OTX_API_KEYS` as a comma-separated list

The collector extracts non-revoked MITRE `intrusion-set` objects, builds a
deduplicated actor-name/alias query list, and preserves every MITRE actor
association for each query.

## Raw Outputs

The collector writes three OTX endpoint populations:

```text
RawStore source "otx_search"
  Raw OTX /api/v1/search/pulses response pages.

RawStore source "otx"
  Raw OTX /api/v1/pulses/{pulse_id} detail responses.
  This keeps existing OTX rebuild scripts compatible.

RawStore source "otx_indicator_page"
  Raw OTX /api/v1/pulses/{pulse_id}/indicators response pages.
```

It also writes collection run artifacts:

```text
data/raw/otx_collection_runs/<run_id>/mitre_actor_query_list.json
data/raw/otx_collection_runs/<run_id>/collection_manifest.json
data/raw/otx_collection_runs/<run_id>/collection_invocations.jsonl
data/raw/otx_collection_runs/<run_id>/search_pages.jsonl
data/raw/otx_collection_runs/<run_id>/discovery_metadata.jsonl
data/raw/otx_collection_runs/<run_id>/saved_files.jsonl
data/raw/otx_collection_runs/<run_id>/skipped_pulses.jsonl
data/raw/otx_collection_runs/<run_id>/skipped_indicator_pages.jsonl
data/raw/otx_collection_runs/<run_id>/checkpoint.json
data/raw/otx_collection_runs/<run_id>/raw_completeness_report.json
data/raw/otx_collection_runs/<run_id>/collection_summary.json
```

These files record the query input list, initial collection plan, resume-time
invocation parameters, search pages, discovery paths, saved raw files, skipped
pulses, skipped indicator endpoints, resume checkpoint state, completeness
report, and summary counts. This is collection provenance only. It must not be
used as an actor label or graph fact.

## Usage

Discover candidates for all MITRE actors without fetching detail or indicators:

```powershell
python scripts/fetch_otx_mitre_actor_raw.py --phase discovery --discovery-workers 2 --search-page-limit 100
```

Collect one actor by name or MITRE id:

```powershell
python scripts/fetch_otx_mitre_actor_raw.py --phase discovery --actor APT28
python scripts/fetch_otx_mitre_actor_raw.py --phase discovery --actor G0007
```

Small smoke run:

```powershell
python scripts/fetch_otx_mitre_actor_raw.py --phase discovery --max-actors 1 --max-search-pages 1 --max-pulses 3
```

Run discovery independently:

```powershell
# Search only; writes candidate_events.jsonl and never requests Pulse detail or indicators.
python scripts/fetch_otx_mitre_actor_raw.py --phase discovery --run-dir data/raw/otx_collection_runs/<run_id> --run-id <run_id>

# Optional and explicitly bounded indicator endpoint pagination.
python scripts/fetch_otx_mitre_actor_raw.py --phase indicators --max-indicator-pages 1 --run-dir data/raw/otx_collection_runs/<run_id> --run-id <run_id>
```

Do not use the compatibility `--phase detail` path on a high-recall candidate
manifest: it expands every candidate, including query-only matches. Route detail
first from source evidence:

```powershell
python scripts/build_otx_detail_acquisition_manifest.py `
  --candidate-manifest data/raw/otx_collection_runs/<discovery-run>/candidate_events.jsonl `
  --raw-root data/raw `
  --mitre-taxonomy data/raw/mitre/enterprise-attack.json `
  --output-dir data/processed/otx_detail_acquisition_<run>

python scripts/fetch_otx_routed_pulse_details.py `
  --manifest data/processed/otx_detail_acquisition_<run>/detail_acquisition_manifest.jsonl `
  --expected-sha256 <frozen-routing-manifest-sha256> `
  --run-dir data/raw/otx_collection_runs/<detail-run> `
  --workers 2
```

The routed downloader accepts only `acquire_*` Pulse IDs, reuses valid RawStore
detail, and never requests deferred query-only candidates or indicator pages.
Its manifest hash and expected populations are fail-closed launch gates.

Legacy run directories without `candidate_events.jsonl` rebuild it locally from
`discovery_metadata.jsonl`; they do not need to repeat completed searches.

Build the final routed Event dataset in one RawStore pass:

```powershell
python scripts/build_otx_routed_dataset.py `
  --routing-manifest data/processed/otx_detail_acquisition_<run>/detail_acquisition_manifest.jsonl `
  --raw-root data/raw `
  --mitre-taxonomy data/raw/mitre/enterprise-attack.json `
  --discovery-run-dir data/raw/otx_collection_runs/<discovery-run> `
  --detail-audit data/raw/otx_collection_runs/<detail-run>/final_audit.json `
  --output-dir data/processed/otx_actor_event_dataset_<run>
```

This emits Events, source claims, Event-level indicator summaries, a temporal
profile, and a hashed dataset manifest. It does not flatten IOC occurrences,
compute confidence/final attribution, or perform infrastructure enrichment.

Limit query count for a connectivity or resume test:

```powershell
python scripts/fetch_otx_mitre_actor_raw.py --phase discovery --actor G0007 --max-queries 1 --max-search-pages 1
```

Indicator endpoint pages are outside the current raw-gathering scope. Embedded
Pulse `indicators[]` are the preserved source evidence; endpoint backfill is not
a prerequisite for actor-seeded discovery or routed-detail completion.

Run a completeness audit without calling OTX:

```powershell
python scripts/audit_otx_raw_completeness.py --raw-root data/raw --run-dir data/raw/otx_collection_runs/<run_id>
```

Check long-run query progress without reading large pulse payloads:

```powershell
python scripts/audit_otx_raw_completeness.py --mode progress --raw-root data/raw --run-dir data/raw/otx_collection_runs/<run_id>
```

With `--run-dir`, the audit is run-scoped. It uses the run's query list,
search pages, and discovery metadata as the universe, rather than treating the
entire historical RawStore as proof that this run is complete.

## Audit Gates

The collector is complete only when the audit gates pass:

```text
Gate A - Query coverage
  All MITRE-derived queries are touched and either complete or have classified
  permanent failures.

Gate B - Routing coverage
  Every discovery candidate has one acquire/defer decision with source evidence
  and reason; query provenance alone never becomes attribution.

Gate C - Selected pulse detail
  Every acquire_* Pulse has valid /api/v1/pulses/{pulse_id} raw detail or a
  classified terminal failure; deferred candidates remain preserved.
```

Support enrichment and indicator-endpoint coverage are separate optional gates,
opened only for an explicit downstream evidence need. They do not prevent the
current OTX collection phase from completing.

## Boundary

OTX source metadata is data returned by OTX, such as `author`, `created`,
`modified`, `tags`, `references`, `adversary`, `malware_families`,
`targeted_countries`, `industries`, `attack_ids`, `TLP`, and `indicators`.

Collection provenance is data created by the collector, such as `query`,
`query_actors`, `search_page`, `search_rank`, saved file refs, skipped reasons,
and checkpoint state. Keep it out of actor labels and training features unless
a later experiment intentionally studies collection bias.
