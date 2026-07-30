# EviTRAIL Data Delivery Coordination

Status: implementation coordination record  
Consumer revision: `Mitraaaaa/Evitrial@da4a29e8ce25cff8cbddebb444b069296f949511`  
Publication revision inspected: `chocobo9/CTI-RAG@bfed4ae2127ffefcdb05576a4a540d653af54827`

## Shared interface

All source routes produce or validate the current EviTRAIL five-file handoff:

- `nodes.jsonl`
- `edges.jsonl`
- `events.jsonl`
- `source_claims.jsonl`
- `rejected_records.jsonl`

The factual graph contains only Event, Domain, IP, URL, and ASN nodes. Raw
inputs are immutable. Large inputs, staging databases, shards, and generated
datasets belong under `F:\DATA_COLLECTION`; the repository contains only code,
small fixtures, contracts, manifests, and documentation.

## Evidence and vocabulary rules

- A source-provided actor assertion such as OTX `adversary` is an
  `attribution` claim with candidate usage.
- Actor-like tags are `report_context` with `provenance_only` usage.
- Collection query matches are `discovery_only` with `provenance_only` usage.
- Multi-actor, ambiguous, unresolved, conflicting, and out-of-vocabulary
  claims remain separate records.
- MITRE and Malpedia resolve identity and aliases; they do not create Event
  attribution.
- Vocabulary updates use resolved factual attribution claims and the current
  EviTRAIL support policy. Context and discovery evidence do not contribute.

## Parallel ownership

- OTX route: bounded-memory latest-snapshot handoff and validation.
- Other-source route: real-sample compatibility audit and narrowly scoped
  adapters for ORKL, CIRCL MISP, APTnotes, and CISA.
- Enrichment route: OTX pDNS/ASN normalization with explicit subset coverage
  and terminal outcome preservation.
- Primary session: shared contract, global vocabulary, integration, full-run
  orchestration, manifests, and publication.

No route may change the shared node model, claim semantics, vocabulary policy,
or raw inputs independently.

## Acceptance scenarios

1. Wrapper collection time and source Pulse times survive into the handoff and
   EviTRAIL base output.
2. A discovery-only actor match never becomes an attribution or vocabulary
   vote.
3. Direct, multi-actor, ambiguous, unresolved, and conflicting claims remain
   auditable.
4. The full OTX route has measured bounded memory and deterministic shards.
5. IP-general enrichment produces IP-to-ASN relations after normalization.
6. Empty and retry-exhausted enrichment results remain explicit evidence.
7. Every source decision is demonstrated on a real collected sample.
