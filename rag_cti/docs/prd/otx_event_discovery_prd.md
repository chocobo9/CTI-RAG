# PRD: OTX APT-Seeded Event Discovery

## Problem Statement

The current OTX collector uses MITRE actor names and aliases for discovery but
couples search pagination, Pulse-detail acquisition, and indicator-endpoint
pagination in one loop. This makes broad weak-label recall trigger expensive
IOC expansion before the source Event population is known. The repository also
contains a reference TRAIL pipeline that drops ambiguous and multi-actor Pulses,
computes confidence, writes a clean graph, and enriches infrastructure in the
same script. Those behaviors are not the objective of this collection task.

The project needs a bounded, resumable, provenance-preserving Event discovery
chain. Every discovered Pulse must remain available, including multi-actor,
ambiguous, unresolved, and missing-source-claim records.

## Solution

Separate OTX work into independently runnable discovery, Pulse-detail, and
optional indicator-endpoint phases. Use one deduplicated candidate-Event
manifest as the phase boundary. Normalize source-provided actor claims offline
without confidence scoring or final attribution inference. Preserve embedded
Pulse indicators as Event-IOC observations.

The reusable population is one Event-centered evidence representation, not a
clean-only projection. Infrastructure enrichment remains an optional future
support-evidence workflow and is not part of collection completeness.

## User Stories

1. As a CTI researcher, I want every actor-seeded OTX Pulse retained so that ambiguous and multi-actor cases remain available for research.
2. As a collector operator, I want completing actor-query coverage not to trigger indicator-endpoint requests so that recall cost is bounded.
3. As a collector operator, I want each Pulse id deduplicated across actor names and aliases so that it is fetched once.
4. As a data consumer, I want every candidate Event to retain all discovery paths so that weak-label provenance is auditable.
5. As a data consumer, I want OTX source actor fields preserved separately from query provenance so that discovery is not mistaken for attribution.
6. As a data consumer, I want source claims classified as single, multi, ambiguous, unresolved, non-attributing, or missing without confidence scoring.
7. As a graph consumer, I want embedded indicators represented as Event-IOC observations so that actor-IOC attribution is not fabricated.
8. As an operator, I want each phase resumable and auditable independently so that failures do not force a full restart.
9. As an operator, I want endpoint pagination to be opt-in and bounded so that oversized Pulses do not dominate collection.
10. As a maintainer, I want the existing raw store and raw evidence preserved so that prior data remains usable.
11. As a maintainer, I want offline tests that make no network calls so that behavior is deterministic.
12. As a researcher, I want enrichment excluded from this chain so that Event discovery completeness does not depend on support-evidence acquisition.

## Implementation Decisions

- The highest test seam is the collector phase interface plus offline artifact builders.
- Search responses produce a candidate-Event manifest keyed by Pulse id and containing merged discovery provenance.
- Pulse detail is acquired in a separately selectable phase and remains the raw Event evidence.
- Indicator endpoint pagination is an optional phase; embedded indicators remain valid Event-IOC observations without endpoint backfill.
- Source actor claims come only from source fields such as OTX `adversary`; actor/alias query matches remain collection provenance.
- Source-claim normalization is deterministic taxonomy resolution, not attribution confidence or fusion.
- Multi-actor, ambiguous, unresolved, non-attributing, and missing claims are terminal preserved states, never drop conditions.
- No clean-only projection is produced.
- No confidence, DST, final attribution assessment, Actor-IOC flattening, pDNS, ASN, VT, WHOIS, model training, or GPU work is included.
- Existing user changes and unrelated dirty-worktree files must be preserved.

## Testing Decisions

- Tests exercise public phase and artifact-builder interfaces with small local fixtures.
- Discovery tests prove that search-only execution makes no Pulse-detail or indicator requests and merges duplicate discovery paths.
- Detail tests prove that only selected unique Pulse ids are fetched and ambiguous/multi-actor data is not filtered.
- Source-claim tests cover missing, single, alias-collapsed, multi, taxonomy-ambiguous, parse-ambiguous, non-attributing, and unmapped values.
- Tests assert Event-IOC observations do not create Actor-IOC claims.
- Existing OTX actor-collection and intermediate OTX tests are prior art.
- Agents run only their targeted test files; the main agent runs the combined OTX unit subset and final suite as appropriate.

## Out of Scope

- Clean training projection or eligibility filtering.
- Attribution confidence, DST, evidence fusion, or final actor assessment.
- Dropping ambiguous, multi-actor, unresolved, or missing-claim Events.
- Infrastructure enrichment of any kind.
- Graph-model training, embedding generation, GPU/CUDA use, or performance benchmarking.
- Live OTX calls during implementation or verification.
- Full historical raw-data migration.

## Further Notes

The 4,160 completed Pulse details were the implementation calibration
population. The final integration population supersedes it: 31,390 unique
discovery candidates, 5,558 actor-evidenced Events with valid Pulse detail, and
25,832 retained query-only candidates deferred from detail expansion. Current
statistics and hashes are recorded in `docs/otx_raw_collection_status.md` and
the final dataset manifest.
