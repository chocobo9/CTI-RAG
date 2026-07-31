# EviTRAIL delivery status — 2026-07-31

Consumer revision:
`Mitraaaaa/Evitrial@da4a29e8ce25cff8cbddebb444b069296f949511`

Published branch:
`codex/evitrail-delivery-20260730`

## Completed artifacts

- Non-OTX strict handoff: 32,056 Events from APTnotes, CIRCL MISP, CISA, and
  ORKL.
- OTX strict handoff: 17,454 Events in 91 immutable shards, balanced into four
  upload parts.
- Frozen actor vocabulary: 33 actors, built from the exact 11-actor baseline
  plus 22 actors admitted with at least five distinct Events and two distinct
  factual sources.
- Existing cached pDNS/ASN enrichment: 529,782 normalized observations from a
  25,985-task ledger, explicitly declared partial coverage for 4,505 of 17,454
  Pulses.

OTX actor-search matches and tags remain discovery/provenance evidence and do
not become actor labels. OTX attribution votes come only from source-provided
adversary claims. MITRE ATT&CK and Malpedia provide identity and alias
resolution only.

## Acceptance

- Both source build partitions exited successfully and together contain exactly
  17,454 Events with no partition overlap.
- The final four-part mapping contains every one of the 91 source shards exactly
  once.
- A representative exact-reader smoke matched Events, edges, claims, and
  rejected counts.
- A representative enriched pipeline preserved 50 Events and added 35,075
  relations plus 95,686 cached-infrastructure records.
- Full raw rescans and full 91-shard pipeline validation were intentionally not
  repeated.

The detailed machine-readable counts and lineage are under
`rag_cti/data/evitrail_delivery_20260730/`.
