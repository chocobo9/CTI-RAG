# OTX actor-evidenced Event dataset contract

Final dataset: `data/processed/otx_actor_event_dataset_routeA_20260712`.

## Population

- 31,390 OTX discovery candidates are retained in the discovery evidence layer.
- 5,558 Events have source-level actor evidence and valid Pulse detail.
- 25,832 query-only candidates remain deferred; they were not deleted or expanded.
- Multi-actor, taxonomy-ambiguous, parse-ambiguous, and unmapped source claims are retained.

The MITRE actor or alias used to find a Pulse is collection provenance only. It
is never copied into Event attribution.

## Files

### `events.jsonl`

One row per selected OTX Pulse. `event_id` is `otx:pulse:{source_record_id}`.
`resolved_actor_ids` and `candidate_actor_ids` are deterministic resolutions of
the OTX `adversary` source field, not confidence-scored attribution results.
`raw_provenance` identifies and hashes the exact RawStore wrapper used.

### `source_attribution_claims.jsonl`

One row per parsed label from the OTX `adversary` field. Claims may resolve to
one actor, multiple actors, ambiguous candidates, or no MITRE actor. Consumers
must not collapse multi/ambiguous rows into a single actor.

### `event_indicator_summaries.jsonl`

One summary per Event. It contains indicator counts, type counts, active-state
coverage, explicit first/last-seen coverage when supplied, and source
created/expiration ranges. It deliberately contains no IOC values.

### `dataset_temporal_profile.json`

Describes actual Pulse, indicator, and fetch timestamps. Null `since`/`until`
means the collection was unfiltered; observed minima and maxima are not a
selection window. Indicator `created`/`expiration` must not be relabelled as
activity `first_seen`/`last_seen`.

### `dataset_manifest.json`

Records population decisions, discovery terminal states, detail coverage,
source-claim counts, indicator-occurrence counts, input hashes, and output
hashes.

## Event-to-IOC consumption

The reusable relation is:

```text
Event --InReport--> IOC
```

IOC occurrences remain inside the Pulse JSON referenced by
`events.raw_provenance.raw_path`. A graph builder should stream one selected
Pulse at a time and project only supported indicator types:

| OTX type | Node type |
|---|---|
| `domain`, `hostname` | Domain |
| `IPv4`, `IPv6` | IP |
| `URL`, `URI` | URL |

The edge means only that the IOC occurs in the Event/Pulse. It does not assert
Actor-to-IOC attribution. Indicator endpoint backfill, pDNS, ASN, WHOIS, VT,
confidence, DST, and enrichment are outside this dataset.
