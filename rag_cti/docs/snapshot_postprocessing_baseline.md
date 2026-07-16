# Current CTI Snapshot Post-processing Baseline

Status: **current post-collection baseline**  
Collection snapshot: **2026-07-12**
Scope: consume the current raw and source-normalized snapshot; do not recollect
or modify the collection logic.

## Processing boundary

The collection phase is closed for this dataset. The post-collection pipeline
starts from the following snapshot inputs:

```text
APT/MITRE seed taxonomy
        ↓
snapshot OTX actor-evidenced Events and source claims
snapshot CIRCL MISP OSINT Events, attributes, objects and actor-like tags
snapshot Malpedia actors, families, aliases and actor-family links
        ↓
source adapters
        ↓
Unified IntermediateRecord + EntityMention + RelationMention + AttributionClaim
        ↓
alias/entity resolution and ambiguity preservation
        ↓
data fusion and evidence aggregation
        ↓
Neo4j-ready projection
```

The pipeline must not:

- issue new OTX, MISP, Malpedia, VT or pDNS requests;
- use a discovery query as an attribution claim;
- collapse multiple actor labels into one actor;
- discard ambiguous, unmapped or deferred records;
- treat Malpedia taxonomy links or infrastructure enrichment as incident attribution;
- calculate final source reliability or attribution confidence during normalization.

## Snapshot source roles

| Source | Current role | Primary post-processing inputs | Attribution interpretation |
|---|---|---|---|
| MITRE ATT&CK | APT seed and ontology reference | groups, aliases, software, campaigns, techniques and STIX relations | authoritative taxonomy/reference, not an incident report |
| OTX | actor-seeded, actor-evidenced Event source | Events, actor source claims, indicators, attack IDs, malware families, countries, references and timestamps | preserve source claims; query provenance is not attribution truth |
| CIRCL MISP OSINT | report/event and observable source | Events, tags, Galaxy labels, attributes, objects, reports and timestamps | explicit source labels are attribution signals, not final labels |
| Malpedia | actor/malware taxonomy bridge | actors, aliases, families, references and actor-family links | taxonomy and alias evidence; not incident attribution by itself |
| VT / pDNS / WHOIS | optional later enrichment | only when an explicit downstream enrichment task is opened | infrastructure evidence; never direct actor attribution |

## Current snapshot populations

- OTX: 5,558 actor-evidenced Events, 5,867 source-claim rows and
  12,155,056 embedded indicator occurrences. Query-only candidates remain
  preserved but are not expanded into Event detail.
- CIRCL MISP: 1,855 successful Events, 741,836 attributes and 43,656 objects;
  241 Events contain actor-like source context and 82 contain multiple
  actor-like labels.
- Malpedia: 1,017 actors, 3,781 malware families, 2,743 aliases and 1,343
  actor-family links.

The authoritative source-specific manifests and reports remain the source of
exact hashes and collection audit details:

- `docs/otx_raw_collection_status.md`
- `data/processed/otx_actor_event_dataset_routeA_20260712/dataset_manifest.json`
- `data/raw/circl_misp/reports/collection_report.json`
- `data/raw/malpedia/reports/collection_report.json`

## Post-collection deliverables

The current Stage 1 delivery is complete only when it contains:

1. a snapshot source manifest and source capability matrix;
2. unified intermediate records with raw references;
3. entity mentions and canonical/candidate alias mappings;
4. candidate relationships and source attribution claims;
5. explicit multi-actor and ambiguity fields;
6. timestamp normalization and temporal split metadata;
7. entity/relation/claim coverage inventories;
8. source-native versus enrichment-derived feature metadata;
9. Neo4j-ready node and relationship projections;
10. a processing report covering missing values, unresolved mappings,
    conflicts, skipped fields and source coverage.

Supporting-source counts, conflicting-source counts and fused confidence are
computed only after these source-backed rows exist. They must not overwrite the
original claims.

## Strict Stage 1 output contract

The current implementation materializes the Stage 1 package at
`data/processed/intermediate_snapshot_v1_20260716/`. The required fields from the
teammate reference are present in the corresponding JSONL artifacts, including
when the source does not provide a value:

- `intermediate_records.jsonl`: record identity, `source_name`, `source_type`,
  `report_identifier`, `raw_object_reference`, `timestamps`/`timestamp`, actor
  matches, aliases, tags, references, indicators, attribution metadata,
  ambiguity, extracted entity and candidate relation references, and processing
  status;
- `entity_mentions.jsonl`: raw and canonical values, entity type, source field,
  extraction method, confidence availability, resolution candidates and
  ambiguity;
- `relation_mentions.jsonl`: subject/object, raw and canonical predicate,
  mapping status, extraction/source provenance, label availability and
  ambiguity;
- `attribution_claims.jsonl` and `attribution_signals.jsonl`: label
  availability, source-provided attribution confidence (or `null`), supporting
  and conflicting source counts (currently `null`, deferred to fusion), evidence
  count/types, and ambiguity;
- `record_features.jsonl`, entity/relation inventories, temporal split metadata,
  processing report, and `neo4j/nodes.jsonl` plus `neo4j/relationships.jsonl`.

The current generated counts are 13,554 records, 960,541 entity mentions,
944,244 relation mentions, 6,436 attribution claims/signals, and 13,787 alias
mappings. The relation inventory is source-backed and currently contains
`uses`, `attributed-to`, `targets`, `associated-with`, `has-indicator`,
`has-tag`, `mentions`, and `references`. Cross-source synonym collapse and
support/conflict aggregation remain the subsequent data-fusion stage.
