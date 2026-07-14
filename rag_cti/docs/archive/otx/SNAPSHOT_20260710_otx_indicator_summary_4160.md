# SNAPSHOT — OTX Indicator Summary Assessment (2026-07-10 / 4,160 calibration)

> Archive category: OTX indicator-profile snapshot.
>
> **Status: HISTORICAL ASSESSMENT SNAPSHOT.** The reasoning may remain useful, but
> current population and authority start at `docs/OTX_DOC_STATUS.md`.

## Decision

`EventIndicatorOccurrence` must not be a standard fully materialized product for
the current population. The reusable result is an Event-level indicator summary
plus the raw Pulse reference. Occurrence rows may be generated later only for a
consumer-defined, bounded Event/time/type population.

The occurrence relation remains conceptually useful for Event-to-IOC provenance,
indicator-driven reverse lookup, temporal analysis when a source supplies real
activity bounds, and attaching later support evidence. It does not improve the
initial actor-seeded Event discovery enough to justify unconditional
materialization.

## Input and Runtime

- Frozen completed Pulse details: 4,160.
- Collection time filter: none (`since=null`, `until=null`).
- Dataset coverage status: unbounded historical population.
- Raw records read: approximately 12.92 GB.
- Largest raw record: approximately 218.54 MB.
- Streaming summary runtime: approximately 181.9 seconds.
- Summary output: approximately 2.92 MB.
- Network, endpoint backfill, enrichment, training, and GPU work: none.

The current run cannot truthfully be labelled as a 2023–2026 dataset because its
collection manifest contains no such filter and includes older Events. A future
2023–2026 projection must select Events by a declared field such as
`pulse.created`; that interval belongs to its dataset manifest, not to every IOC.

## Indicator Scale

- Total source-provided indicator occurrences: 55,659,022.
- Events with no embedded indicators: 635.
- Median indicators per Event: 152.
- 90th percentile: approximately 15,309.
- 95th percentile: approximately 31,004.
- 99th percentile: approximately 600,393.
- Maximum: 915,774.
- Largest 10 Events contain approximately 12.94% of all occurrences.

Threshold implications:

| Per-Event threshold | Events above threshold | Occurrences at or below threshold |
|---:|---:|---:|
| 100 | 2,158 | 35,905 |
| 1,000 | 1,577 | 212,180 |
| 10,000 | 597 | 3,036,107 |
| 50,000 | 140 | 12,506,762 |

Even a 50,000-per-Event policy would materialize approximately 12.5 million
rows while omitting the largest 140 Events. A threshold alone therefore does
not define a meaningful data product; a consumer must also specify Event
population, indicator types, time selection, and purpose.

## Dominant Indicator Types

| Type | Occurrences |
|---|---:|
| domain | 29,402,513 |
| URL | 11,839,772 |
| hostname | 8,711,997 |
| FileHash-SHA256 | 4,007,287 |
| FileHash-MD5 | 656,243 |
| FileHash-SHA1 | 424,539 |
| IPv4 | 260,794 |
| CIDR | 259,498 |
| email | 39,230 |
| CVE | 27,440 |
| IPv6 | 25,434 |

## Time Semantics and Coverage

- Events with at least one `indicator.created`: 3,525 / 4,160.
- Events with at least one `indicator.expiration`: 175 / 4,160.
- Events with explicit `first_seen`: 0.
- Events with explicit `last_seen`: 0.
- Indicators with `is_active=true`: 0.
- Indicators with `is_active=false`: 0.
- Indicators with missing/unknown `is_active`: 55,659,022.

Consequences:

- `indicator.created` is retained only as a source-created timestamp range.
- `indicator.expiration` is retained only as a source-expiration range.
- No activity duration can be calculated from this embedded OTX population.
- `created` must not be copied into both `first_seen` and `last_seen`.
- The dataset coverage window must remain manifest-level metadata.

## Result Product

The produced `event_indicator_summaries.jsonl` contains one row per Event:

- indicator count and type counts;
- source-created minimum and maximum;
- source-expiration minimum and maximum;
- active true/false/unknown counts;
- explicit activity-bound coverage, when actually supplied;
- raw record bytes;
- `none` or `summary_only` materialization status.

It contains no indicator values and no Event-Indicator occurrence rows. The raw
Pulse remains the evidence authority for deferred indicators.

## Acceptance

- Event summaries: 4,160.
- Dataset window appears only in the manifest.
- No fabricated activity interval or duration.
- No Actor-IOC relation, confidence, attribution assessment, or enrichment.
- OTX-related unit tests: 59 passed.
- Ruff: passed.
