# HISTORICAL — OTX Raw Collection PRD

> Archive category: superseded OTX collection plan.
>
> **Status: HISTORICAL / SUPERSEDED. Do not use this PRD for current OTX scope or
> completeness semantics.** Current OTX authority starts at `docs/OTX_DOC_STATUS.md`.

## Problem Statement

The OTX collection layer is not yet reliable enough to serve as the project's source of truth for OTX raw data. The project needs complete OTX endpoint responses and enough collection audit data to explain why each pulse was collected, where each raw response was saved, and what was skipped or failed.

MITRE ATT&CK is already available locally as static raw data. The current focus is OTX, which is fetched dynamically and therefore needs stronger reproducibility, resume behavior, and completeness checks.

Collection metadata must not be confused with OTX source metadata or knowledge-layer labels. For example, a pulse found by searching a MITRE actor alias is not automatically attributed to that actor.

## Solution

Build an actor-centric OTX raw collection contract. The collector will derive a full OTX query input list from local MITRE ATT&CK intrusion-set records, using actor canonical names and aliases. Queries will be normalized and deduplicated, while preserving every MITRE actor association for a query.

The collector will preserve three OTX raw endpoint response types:

- OTX pulse search pages
- OTX pulse detail records
- OTX pulse indicator pages

Each collection run will also write audit artifacts that describe the input list, run plan, resume-time invocations, search pages, discovery paths, saved raw files, skipped pulses, checkpoint state, completeness report, and final summary. These audit artifacts are for collection reproducibility and validation only.

## User Stories

1. As a CTI data maintainer, I want OTX raw pulse data to preserve the original endpoint response, so that downstream processing can always return to source-level evidence.
2. As a CTI data maintainer, I want OTX indicator lists to be collected from the dedicated indicator endpoint, so that IOC fields not embedded in pulse detail are not lost.
3. As a CTI data maintainer, I want OTX search result pages to be saved raw, so that I can prove which query found which pulse at collection time.
4. As a CTI data maintainer, I want MITRE actor names and aliases to be extracted into a fixed query input list, so that the OTX collection input is reproducible.
5. As a CTI data maintainer, I want the query input list to be deduplicated, so that the same alias is not searched repeatedly for multiple actors.
6. As a CTI data maintainer, I want each query to preserve all MITRE actors it came from, so that shared aliases do not erase actor associations.
7. As a CTI data maintainer, I want discovery metadata for each found pulse, so that I can explain why the pulse entered the dataset.
8. As a CTI data maintainer, I want discovery metadata to be marked as collection audit only, so that it is not mistaken for an OTX-provided actor label.
9. As a CTI data maintainer, I want skipped pulses to be recorded with reasons, so that date-window filtering does not silently remove records.
10. As a CTI data maintainer, I want saved raw files to be indexed in an audit artifact, so that I can verify which endpoint responses were actually persisted.
11. As a CTI data maintainer, I want a real checkpoint state, so that interrupted OTX collection can resume without repeating completed work.
12. As a CTI data maintainer, I want a collection manifest, so that each run records its input, parameters, endpoints, and collection intent.
13. As a CTI data maintainer, I want a collection summary, so that I can quickly inspect how many queries, pages, pulses, indicators, skips, and failures occurred.
14. As a downstream pipeline developer, I want raw endpoint data separated from audit metadata, so that knowledge extraction does not accidentally train on collection mechanics.
15. As a downstream pipeline developer, I want pulse detail and indicator endpoint data both preserved, so that later normalization can choose the richer source when needed.
16. As a data reviewer, I want to compare raw search results against saved pulse details, so that I can detect missing or failed detail fetches.
17. As a data reviewer, I want to compare pulse detail indicator counts against indicator endpoint pages, so that I can smoke-test IOC completeness.
18. As a data reviewer, I want failed requests to be structured, so that network/API problems can be distinguished from empty OTX results.
19. As a data reviewer, I want actor queries with no OTX results to remain visible in audit output, so that absence of OTX coverage is not confused with missing MITRE actors.
20. As a future maintainer, I want one canonical OTX collector, so that old pulse-id or subscribed-feed collection scripts do not compete with the actor-centric approach.

## Implementation Decisions

- OTX collection will be actor-centric and query-driven.
- The input query list will be derived from all MITRE intrusion-set records in the local MITRE raw bundle.
- The input query list will include actor canonical names and aliases.
- The input query list will be deduplicated by normalized query text.
- A single normalized query may map to multiple MITRE actors.
- Query-to-actor association is collection provenance only. It does not assert that an OTX pulse belongs to those actors.
- The collector will preserve search pages, pulse details, and indicator pages as raw OTX endpoint responses.
- OTX pulse detail raw and OTX indicator endpoint raw are both required for full raw completeness.
- `--skip-indicator-pages` is allowed only as a Phase 1 collection mode. It can establish core completeness for search plus pulse detail, but it cannot be reported as full raw completeness.
- The run output will include `mitre_actor_query_list.json`, `collection_manifest.json`, `collection_invocations.jsonl`, `search_pages.jsonl`, `discovery_metadata.jsonl`, `saved_files.jsonl`, `skipped_pulses.jsonl`, `skipped_indicator_pages.jsonl`, `checkpoint.json`, `raw_completeness_report.json`, and `collection_summary.json`.
- Existing RawStore wrapping is acceptable because it preserves `source`, `source_id`, `fetched_at`, and the original `payload`.
- Audit metadata must remain separate from OTX raw payloads.
- Derived merge views are deferred. They may be useful later but should not block raw collection reliability.

## Output Contract

Raw endpoint artifacts:

```text
data/raw/otx_search/
data/raw/otx/
data/raw/otx_indicator_page/
```

Run and audit artifacts:

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

`mitre_actor_query_list.json` contains the deduplicated MITRE-derived OTX query input list:

```json
{
  "generated_at": "...",
  "mitre_bundle": {
    "sha256": "...",
    "source": "local_mitre_raw"
  },
  "actor_count": 0,
  "alias_record_count": 0,
  "deduplicated_query_count": 0,
  "queries": [
    {
      "query": "...",
      "query_normalized": "...",
      "actors": [
        {
          "actor_name": "...",
          "mitre_attack_id": "...",
          "stix_id": "...",
          "matched_from": "name"
        }
      ]
    }
  ]
}
```

`collection_manifest.json` records the collection plan:

```json
{
  "run_id": "...",
  "started_at": "...",
  "collector": "otx_mitre_actor_raw_collector",
  "input_query_list": "mitre_actor_query_list.json",
  "otx_endpoints": [
    "/api/v1/search/pulses",
    "/api/v1/pulses/{pulse_id}",
    "/api/v1/pulses/{pulse_id}/indicators"
  ],
  "params": {
    "since": null,
    "until": null,
    "search_page_limit": 20,
    "max_search_pages": 80,
    "indicator_page_limit": 1000,
    "max_indicator_pages": 0
  }
}
```

`discovery_metadata.jsonl` records why a pulse entered the collection:

```json
{
  "run_id": "...",
  "method": "mitre_actor_alias_search",
  "query": "...",
  "query_normalized": "...",
  "query_actors": [],
  "search_page": 1,
  "search_rank": 1,
  "pulse_id": "...",
  "pulse_name": "...",
  "pulse_created": "...",
  "pulse_modified": "...",
  "in_date_window": true,
  "search_raw_ref": {}
}
```

## Completeness Report Contract

After a collection run, the repository should be able to audit the raw store
without calling OTX again. The audit output is a derived validation artifact,
not source raw and not knowledge-layer data.

When `--run-dir` is provided, the report is run-scoped: it uses
`mitre_actor_query_list.json`, `search_pages.jsonl`, and
`discovery_metadata.jsonl` as the audit universe. It must not silently use the
entire historical `data/raw/otx` population to prove that a specific MITRE
actor/alias run is complete.

Default output:

```text
data/raw/otx_collection_runs/<run_id>/raw_completeness_report.json
```

Progress-only output:

```text
data/raw/otx_collection_runs/<run_id>/run_progress_report.json
```

`--mode progress` reads only run artifacts and is intended for Gate A/query
coverage checks during long OTX runs. `--mode full` reads RawStore pulse and
indicator payloads and is intended for Gate B/Gate C completeness checks.

The report contains:

```json
{
  "generated_at": "...",
  "raw_root": "data/raw",
  "run_dir": "data/raw/otx_collection_runs/<run_id>",
  "scope": "run",
  "run_scope": {
    "query_total": 0,
    "queries_touched": 0,
    "queries_completed": 0,
    "queries_with_errors": 0,
    "queries_untouched": 0,
    "search_pages_total": 0,
    "search_pages_ok": 0,
    "search_pages_error": 0,
    "discovered_pulse_ids": 0,
    "saved_pulse_detail_ids": 0,
    "latest_invocation_params": {},
    "manifest_params": {}
  },
  "counts": {
    "otx_search_records": 0,
    "pulse_detail_records": 0,
    "indicator_page_records": 0,
    "run_discovered_pulses": 0,
    "pulses_missing_pulse_detail": 0,
    "pulses_with_indicator_pages": 0,
    "pulses_endpoint_deferred_by_policy": 0,
    "pulses_endpoint_pending_by_phase": 0,
    "pulses_endpoint_partial_skipped_by_policy": 0,
    "pulses_missing_indicator_pages": 0,
    "pulses_with_indicator_count_mismatch": 0,
    "pulses_missing_required_detail_fields": 0
  },
  "pulses": [
    {
      "pulse_id": "...",
      "pulse_fetched_at": "...",
      "indicator_page_count": 0,
      "detail_indicator_count": 0,
      "indicator_endpoint_count": 0,
      "indicator_endpoint_results_total": 0,
      "indicator_counts_match": true,
      "missing_required_detail_fields": [],
      "indicator_endpoint_policy": null,
      "status": "ok"
    }
  ]
}
```

The required detail fields are the OTX pulse-detail fields observed in smoke
validation: `id`, `name`, `description`, `author_name`, `modified`, `created`,
`tags`, `references`, `public`, `adversary`, `targeted_countries`,
`malware_families`, `attack_ids`, `industries`, `TLP`, `indicators`,
`revision`, `groups`, `in_group`, `author`, and `is_subscribing`.

## Downstream Indicator View Contract

Downstream rebuilds must prefer the dedicated OTX indicator endpoint when it is
available. This does not mutate the raw pulse. It creates an in-memory derived
view:

```text
raw pulse detail + latest otx_indicator_page pages -> pulse view with full indicators
```

Rules:

- If `otx_indicator_page` pages exist for a pulse, use their `results[]` as the
  pulse view's `indicators`.
- If no indicator pages exist, fall back to the pulse detail's embedded
  `indicators`.
- Indicator page identity includes the requested page limit. A page fetched with
  `limit=1000` is not the same page as one fetched with `limit=10000`.
- Very large indicator endpoints may be deferred instead of fetched in the
  first pass when the collector policy says the endpoint is too expensive. The
  pulse detail raw remains the core IOC source, and the endpoint deferral must
  be written to `skipped_indicator_pages.jsonl`.
- The derived view is used for processed OTX rebuilds and the standalone
  indicator index.
- The derived view must not be written back into `data/raw/otx/`.

Oversized endpoint policy:

```text
indicator_count <= indicator_endpoint_full_threshold:
  fetch all indicator endpoint pages

indicator_count > indicator_endpoint_full_threshold:
  default: fetch 0 endpoint pages
  write skipped_indicator_pages.jsonl as a later-collection backlog
  report status core_complete_endpoint_deferred_by_policy

indicator_count > indicator_endpoint_full_threshold and oversized_indicator_sample_pages > 0:
  fetch only that many endpoint pages
  write skipped_indicator_pages.jsonl for the remainder
  report status core_complete_endpoint_partial_skipped_by_policy
```

This is not silent data loss: the pulse detail raw still preserves IOC values,
types, timestamps, and active/expiration fields, while endpoint-only enrichment
fields such as `false_positive`, `pulse_key`, and `slug` are explicitly marked
as deferred or partial for that pulse. A later large-pulse run can set
`--indicator-endpoint-full-threshold 0` to fetch those endpoints strictly.

Audit gates:

```text
Gate A - Query coverage
  Input: mitre_actor_query_list.json, search_pages.jsonl, checkpoint.json
  Pass: queries_untouched == 0, queries_with_errors == 0, or each error has a
        documented retry/permanent-failure classification.
  Output: raw_completeness_report.json run_scope section.

Gate B - Core pulse detail completeness
  Input: discovery_metadata.jsonl, RawStore source "otx"
  Pass: pulses_missing_pulse_detail == 0 and
        pulses_missing_required_detail_fields == 0.
  Output status: core complete for search plus pulse detail.

Gate C - Indicator endpoint completeness
  Input: RawStore source "otx_indicator_page", skipped_indicator_pages.jsonl
  Pass: pulses_missing_indicator_pages == 0,
        pulses_with_indicator_count_mismatch == 0, and no
        core_complete_endpoint_pending_by_phase rows remain.
  Allowed pending: core_complete_endpoint_deferred_by_policy for explicitly
        oversized endpoints that are listed as a later backfill backlog.
  Output status: full raw endpoint completeness only after this gate passes.
```

## Testing Decisions

The main test seam is the collector run boundary. Tests should assert externally visible behavior: produced raw records, run artifacts, skipped records, and resume behavior.

Tests should cover:

- Query list generation from a small MITRE bundle fixture.
- Query deduplication while preserving multiple actor associations.
- Raw search page persistence.
- Pulse detail raw persistence.
- Indicator page raw persistence.
- Date-window skip audit.
- Checkpoint-based resume behavior.
- A 5-pulse smoke run that verifies raw and audit artifact completeness.

Existing RawStore behavior and OTX actor collection helper tests should be reused as prior art.

## Out of Scope

- Changing MITRE raw download behavior.
- Treating MITRE-derived query associations as actor attribution ground truth.
- Training model data from collection audit metadata.
- Building final knowledge graph merge logic.
- Building by-actor derived views in this phase.
- Inferring threat active intervals from pulse publication dates.
- Replacing RawStore.
- Supporting non-OTX sources in this PRD.

## Further Notes

The core separation is:

- OTX raw payloads are source data.
- MITRE query list is collection input.
- Discovery, saved files, skipped pulses, checkpoint, and summary are collection audit.
- Merge and by-actor views are derived convenience artifacts and should be handled later.
