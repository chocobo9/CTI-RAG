# OTX Raw Collection Status

Updated: 2026-07-12 America/Vancouver  
Status: **actor-seeded discovery and actor-evidenced Pulse detail gathering are phase-complete**

## Authoritative artifacts

- Discovery run: `data/raw/otx_collection_runs/routeA_20260704_policy_small_first`
- Detail routing: `data/processed/otx_detail_acquisition_routeA_20260704`
- Routed detail run: `data/raw/otx_collection_runs/actor_evidenced_detail_20260711`
- Final dataset: `data/processed/otx_actor_event_dataset_routeA_20260712`
- Consumer contract: `docs/implementation/otx_actor_event_dataset_contract.md`

## Final counts

| Item | Count |
|---|---:|
| MITRE actor/name/alias queries | 577 |
| Queries complete (`has_next=false`) | 575 |
| Queries truncated at OTX service page cap | 2 |
| Unique discovery candidate Pulse IDs | 31,390 |
| Discovery paths after deduplication | 60,685 |
| Actor-evidenced Events selected for detail | 5,558 |
| Query-only candidates retained and deferred | 25,832 |
| Actor-evidenced details reused | 3,171 |
| Actor-evidenced details downloaded | 2,387 |
| Valid selected Pulse details | 5,558 / 5,558 |
| Final source-claim rows | 5,867 |
| Embedded indicator occurrences in selected Pulses | 12,155,056 |

The two deterministic truncations are `CHROMIUM` and `Play`. OTX accepts pages
through 50, returns `next`, then returns HTTP 400 for page 51. They are recorded
as `truncated_page_cap`, not hidden as complete queries or left as retryable
errors.

## Population semantics

`31,390` is the number of unique Pulse IDs returned by actor/name/alias search.
It is a high-recall candidate population, not an attributed Event population.
One Pulse may have many discovery paths, all of which remain collection
provenance only.

Detail routing is driven by source-level actor evidence:

| Decision | Count |
|---|---:|
| `acquire_actor_evidenced` | 2,753 |
| `acquire_multi_actor` | 14 |
| `acquire_ambiguous_actor` | 115 |
| `acquire_unmapped_actor_label` | 2,676 |
| `deferred_query_only` | 25,832 |

In the collected OTX search payloads, `tags` were empty. The structured routing
cue was the OTX `adversary` source field. Query actor, title, description,
references, and `attack_ids` were not promoted into source attribution.
Multi-actor and ambiguous claims were retained rather than filtered.

## Raw gathering boundary

Phase-complete means:

- raw search pages and all discovery paths are preserved;
- all discovery candidates remain auditable, including deferred query-only hits;
- every selected actor-evidenced Event has valid Pulse detail in RawStore;
- embedded `indicators[]`, source timestamps, actor labels, references, and raw
  provenance are preserved;
- collection/detail terminal states and input/output hashes are recorded.

It does **not** include Event-to-IOC flattening, graph construction, attribution
confidence, fusion, pDNS/ASN/WHOIS/VT enrichment, or indicator-endpoint backfill.
Those are downstream projections or support-evidence workflows.

## Final dataset

`data/processed/otx_actor_event_dataset_routeA_20260712/dataset_manifest.json`
is the authoritative machine-readable summary. It records:

- 5,558 unique Events and indicator summaries;
- 5,867 source claims;
- 575 complete and 2 page-cap discovery terminal states;
- 100% selected-detail coverage;
- routing decisions and all input/output SHA256 values;
- `summary_only` indicator materialization.

The routed-detail run briefly had overlapping downloader processes. This
created 313 duplicate RawStore versions and journal rows. Final audit proved all
313 payload pairs semantically identical, with zero evidence conflicts. They
remain in the append-only raw store and are excluded by latest-state projection.

## Next boundary

OTX collection is closed for this phase. Future work should consume the final
dataset and raw references. Reopening collection requires a new explicit goal,
such as refreshing modified Pulses, revisiting the 25,832 deferred candidates,
or acquiring support enrichment for a named evidence gap.
