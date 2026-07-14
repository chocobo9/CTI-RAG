# SNAPSHOT — Data Collection and Preprocessing Gap Analysis (2026-06-27)

> Intermediate category: dated gap analysis.
>
> **Status: HISTORICAL GAP SNAPSHOT.** It records the pre-v0.1 comparison below and
> is not the current Intermediate contract or implementation plan.

Date: 2026-06-27

Scope: compare the current CTI-RAG data collection / preprocessing implementation
against `docs/intermediate/REFERENCE_teammate_output_data_representation.md`, focusing on Stage 1
graph-ready preparation.

Companion contract draft: `docs/intermediate/contract_draft.md`.

Current status note (2026-06-28): the first `rag_cti.intermediate` module now
exists as an independent offline data-preparation layer. It can build a validated
JSON/JSONL intermediate delivery package from raw/source inputs and demonstrate
RAG/GNN-shaped smoke projections. It is not currently connected to the
production RAG ingestion/index/runtime path, and it does not yet produce a
production GNN training export for the teammate workflow.

## Task Framing

This task is not primarily a RAG-cleaning task. It is a dataset-preparation task
for downstream modeling.

The teammate-facing need is: take the already collected CTI raw data and turn it
into a reusable, traceable, graph-ready dataset substrate that can support GNN
training, labelling algorithms, Neo4j import, and future graph-schema changes.
The preprocessing layer should preserve source evidence and modelling signals;
it should not prematurely collapse the data into one RAG chunk format or one
final graph schema.

The current CTI-RAG project already has useful cleaning work, but much of it is
specialized around retrieval and the current Fact/support model. The target
document asks for a more layered representation:

```text
raw source record
  -> reusable intermediate record
  -> entity / relation mentions
  -> resolved graph objects and modelling features
  -> downstream-specific exports
```

The value of the intermediate layer is that a teammate can change the GNN graph
schema or labelling strategy without recollecting raw data or reverse-engineering
RAG-specific metadata.

Implementation boundary: this value is currently realized as a reusable module
and delivery contract, not as a replacement for the existing RAG projection or
indexing pipeline. RAG and GNN consumers should be treated as downstream
adapters to be built after the intermediate contract is accepted.

## Confirmed Design Constraints

These constraints are accepted for the analysis phase:

1. **JSON-family outputs.** Dataset artifacts should use JSON formats. For large
   record tables, JSONL is still considered part of this JSON-family constraint
   because it is easier to stream, diff, and regenerate than one large JSON
   array.

2. **Traceability is required.** Derived records, mentions, relations, features,
   and attribution signals should keep enough provenance to trace back to raw source
   records and, where feasible, source fields.

3. **Temporal split analysis is required.** The dataset layer should preserve
   enough timestamp information to reason about train/test leakage, including
   weak or missing timestamp cases.

The other goals in this document are not currently controversial in principle.
Their tradeoff is mostly scope and verbosity: how much metadata to preserve now,
how detailed the processing report should be, and how much ambiguity to expose
before it becomes inconvenient for downstream consumers. Treat them as quality
goals unless a later concrete schema choice makes a cost visible.

## Why The Extra Layers Matter

The document's extra layers are useful because they answer modelling questions
that a cleaned RAG corpus does not answer cleanly:

| Modelling question | Why raw/chunks alone are insufficient | Layer that should answer it |
| --- | --- | --- |
| Where did this node or edge come from? | A chunk id is citable, but it may not identify the raw object version, source field, or extraction method. | Intermediate record plus mention inventory. |
| Is this actor label source-provided or inferred? | Current metadata may store `adversary`, but it does not uniformly classify direct / indirect / none before Fact generation. | Relation mention or support signal. |
| Can this record be used in train or test without leakage? | Different sources expose publication, modification, first-seen, last-seen, and fetched timestamps with different semantics. | Temporal normalization and split metadata. |
| Was this alias or entity merge ambiguous? | Current entity registry keeps orphans and merge candidates, but ambiguity is not attached uniformly to each extracted mention. | Entity mention inventory. |
| Can the graph schema be changed later? | Current `relations[]` are already resolved triples shaped for the current knowledge model. | Raw-valued candidate relation inventory before final schema projection. |
| What features are preserved for GNN/labelling? | RAG chunks optimize retrievability, not feature completeness. | Feature table / feature section on intermediate records. |

## Conceptual Data Contract

The reusable data-preparation layer should make a clear contract with downstream
consumers:

1. **Evidence is preserved.** Every derived entity, relation, attribution signal, and
   feature must be traceable back to a raw source record or source-field-level
   origin where possible.

2. **Mentions are separated from resolved entities.** A raw string such as
   `APT 29`, `Cozy Bear`, or `Cobalt` should be preserved as a mention before it
   becomes a canonical graph node. This is what lets ambiguity be reviewed
   instead of hidden.

3. **Candidate relations are separated from final graph edges.** A source-field
   co-occurrence, a MITRE explicit relationship, and an NLP-extracted statement
   should not all look identical at preprocessing time. They may later export to
   the same graph predicate, but the derivation path should remain visible.

4. **Source classification is explicit.** The data should distinguish the
   connector/source name (`otx`, `mitre`, `vt`) from source class
   (`weakly-labeled`, `ontology`, `infrastructure`) and publisher category
   (`vendor`, `government`, `community`, etc.).

5. **Timestamps are normalized but not over-trusted.** The layer should preserve
   publication, modified, observed, and fetched times separately, plus a quality
   marker when only weak timing is available.

6. **Preprocessing preserves signals; modelling decides how to use them.**
   Counts, source categories, label availability, conflicts, aliases, and
   ambiguity should be exported as signals. The GNN or labelling algorithm can
   decide how to weight them.

## Current Conceptual Mismatch

The main mismatch is not that the project lacks data. The mismatch is that the
current processed data is split by runtime needs:

- retrieval chunks for RAG;
- indicator index for joinable indicators;
- entity registry for normalized CTI identities;
- facts/supports for the current knowledge layer;
- raw store for source preservation.

Those are valuable pieces, but they are not yet a single teammate-facing dataset
contract. A teammate consuming the data still has to infer how the pieces fit
together and which fields are safe as labels, features, or edges.

The next design phase should therefore focus on the contract, not the exporter:

- What is the canonical intermediate record unit?
- What does each extracted mention need to remember?
- What does each candidate relation need to remember before resolution?
- Which signals must be preserved for GNN/labelling, without deciding the final
  model?
- Which current outputs are reusable as-is, and which are RAG-specific
  projections?

## Resolved Boundary: Chunk Is A Projection

`Chunk` should not be the reusable unit for the teammate-facing dataset. It is a
RAG/retrieval projection derived from a more general data-preparation layer.

The ideal boundary is:

```text
raw data
  -> reusable intermediate layer
  -> consumer-specific projections
       -> RAG chunks / doc ids / vector payloads
       -> GNN nodes, edges, features, attribution signals
       -> Neo4j import tables
       -> labelling-algorithm inputs
```

This is reasonable and feasible because the current project already has many of
the pieces separately: RawStore, connector projections, entity registry,
indicator index, and Fact/support aggregation. The missing piece is not another
consumer-specific output; it is the stable intermediate contract that lets each
consumer derive its own output without entangling RAG choices with GNN/labelling
choices.

## Current Baseline

The strongest current baseline is `data/processed/v5_staging`, not the
top-level `data/processed/*.jsonl` files. The root processed files include older
or less projected artifacts, while `v5_staging` carries the current chunk
payload projection (`source_type`, `attack_ids`, `entity_ids`, `relations`) and
the Fact/support outputs.

Observed local artifacts:

| Artifact | Count | Notes |
| --- | ---: | --- |
| `data/raw/otx` | 2,056 versioned source-id dirs, 4,113 files | OTX has legacy plus versioned shapes. |
| `data/raw/mitre` | 1 versioned bundle dir plus bundle files | MITRE bundle is present. |
| `data/raw/pdns` | 693 versioned source-id dirs/files | pDNS raw snapshots are present. |
| `data/raw/vt` | 1,097 versioned source-id dirs/files | VT raw snapshots are present. |
| `data/raw/whois` | missing locally | WHOIS scripts exist, but no local raw package is present. |
| `data/processed/indicator_index.jsonl` | 229,883 rows | OTX indicators as entity-shaped records. |
| `data/processed/entity_registry.jsonl` | 2,528 rows | OTX actor/family/technique/location mentions resolved or orphaned. |
| `data/processed/entity_merge_candidates.jsonl` | 219 rows | Held near-miss candidates. |
| `data/processed/ontology_nodes.jsonl` | 1,683 rows | MITRE authoritative definitions. |
| `data/processed/ontology_edges.jsonl` | 1,382 rows | MITRE definitional edges. |
| `data/processed/v5_staging/facts.jsonl` | 43,776 rows | Global triples aggregated from chunk `relations[]`. |
| `data/processed/v5_staging/supports.jsonl` | 60,564 rows | Evidence-to-Fact support edges. |

Current v5 relation predicates:

| Predicate | Count | Sources |
| --- | ---: | --- |
| `uses` | 36,058 | OTX, MITRE |
| `resolves-to` | 6,289 | pDNS, VT |
| `belongs-to` | 5,585 | pDNS |
| `located-in` | 5,531 | pDNS |
| `targets` | 2,656 | OTX |
| `uses-nameserver` | 1,474 | pDNS, VT |
| `mitigates` | 1,445 | MITRE |
| `has-subdomain` | 1,055 | pDNS |
| `detects` | 691 | MITRE |
| `attributed-to` | 25 | MITRE |

## What Already Matches The Target Direction

1. Raw preservation is mostly in place for the selected corpus. `RawStore`
   writes append-only, versioned records keyed by source/source-id/fetched-at.
   OTX, MITRE, pDNS, VT, and PDF raw artifacts are present locally.

2. The implementation separates raw preservation from projection. Scripts such
   as `rebuild_otx_jsonl.py`, `project_pdns.py`, `project_vt.py`,
   `build_indicator_index.py`, `build_entity_registry.py`, and `build_facts.py`
   regenerate derived outputs from raw or processed projection inputs.

3. Indicator typing has been rescued for the knowledge path. OTX indicators are
   preserved as typed `IndicatorMention` values and emitted to
   `indicator_index.jsonl` with source type and canonical type.

4. Entity resolution is explicit. Exact matches resolve to MITRE-backed entity
   ids, fuzzy/substring matches become held candidates, and unresolved mentions
   become orphan entities instead of being silently dropped.

5. Relation projection has moved beyond the older IOC-only graph. v5 now emits
   TTP, infrastructure, and defensive predicates, and aggregates them into
   Fact/support rows with support counts, origins, label availability, and
   provisional aggregate credibility.

## Main Gaps Against The Target Document

| Target requirement | Current state | Gap |
| --- | --- | --- |
| Selected source list with source categories | Sources are implicit in connectors and raw folders. `SourceClass` covers ontology, weakly-labeled, unlabeled narrative, and infrastructure. | No machine-readable selected-source manifest. The target `Source Type` means Government/Vendor/Community/etc., while current `source_type` usually means connector/source name such as `otx`, `mitre`, `pdns`, or `vt`. |
| Temporal scope and train/test split | `retrieved_at`, `fetched_at`, `last_modified`, `first_seen`, `last_seen`, and VT date fields exist in places. | No dataset-level temporal window, no temporal split assignment, and no explicit flag for unreliable or missing timestamps. |
| Raw or near-raw JSON for all selected sources | OTX, MITRE, pDNS, VT, and PDFs are present. | WHOIS raw is missing locally. OTX raw is complete for the selected pulse set, not all OTX. The raw package does not itself declare the selected-source population and coverage policy. |
| Unified intermediate JSON schema | `NormalizedRecord` exists in memory and v5 chunks carry projected payload fields. | No materialized `intermediate_records.jsonl` equivalent. Current chunks conflate retrieval content with normalized metadata and omit several target fields. |
| Raw object reference in intermediate records | Some records carry source ids (`pulse_id`, `stix_id`, `domain`, `file_id`). | No uniform `raw_ref` or raw-store coordinate (`source`, `source_id`, `fetched_at`, path/hash) across all projected records. |
| Publication and modification timestamps | Modification/observed/fetched timestamps exist inconsistently by source. | Publication timestamp is often absent. Timestamp semantics are not normalized into a common field set. |
| Matched actors and aliases | OTX `adversary` exists; MITRE aliases exist in ontology nodes; entity registry stores aliases for resolved entities. | No per-record `matched_actors[]` with alias evidence. No standalone alias mapping output for actors, campaigns, malware, and tools beyond MITRE-derived aliases and registry rows. |
| Attribution label availability | `supports.jsonl` stores `label_availability` for generated facts. | It is not present at the intermediate-record or candidate-relation level. Current values are derived by source tier, not preserved from source statements. |
| Ambiguity flag | Entity merge candidates and orphan resolutions exist. | No explicit per-record or per-mention `ambiguity_flag`; ambiguity is split across registry resolution strings and merge-candidate rows. |
| Extracted entities with raw value, canonical value, source field, extraction method, confidence/ambiguity | Entity registry and indicator index store canonical-ish identities and resolution state. | Mentions are not materialized with source field and extraction method. Missing broad target entity types: Event/Report, Actor Alias, Sector, Organization, CVE, Tag, External Reference, Source, Author, Timestamp. |
| Candidate relationships before final schema | `metadata.relations[]` stores resolved entity-id triples in v5 chunks. | There is no materialized relation-candidate inventory that preserves raw values, source fields, extraction method, confidence, ambiguity, and mapping status before resolution. |
| Event/Report-centered graph | Chunks act as Evidence and Documents are provenance. | The target wants Event/Report nodes and relationships such as Event HAS_INDICATOR, HAS_TAG, REFERENCES, USES_MALWARE, USES_TOOL, USES_TECHNIQUE, TARGETS_SECTOR, TARGETS_COUNTRY. Current facts mainly connect actor/family/campaign/domain/ip/asn/location entities, not Event/Report nodes. |
| Feature extraction | Fact/support rows include support count, distinct origins, conflict flag, label availability, confidence, and aggregate credibility. | Missing per-record feature table: timestamp features, source reliability signals, attribution-confidence-as-preserved, indicator counts, indicator type distribution, tag/reference counts, and temporal split assignment. |
| Enrichment marking | pDNS and VT are treated as infrastructure sources; raw/projection paths are separate. | Enriched fields are not uniformly marked as enrichment vs source-native raw fields in intermediate records. |
| Graph-ready outputs | Facts/supports, ontology nodes/edges, entity registry, indicator index, and chunk corpora exist. | No complete Neo4j import-ready package for the target heterogeneous Stage-1 graph variants. |
| Processing report | `raw_data_sharing_guide.md` and `docs/archive/architecture/SNAPSHOT_20260614_M0_implementation_status.md` summarize parts of the state. | No generated processing report covering missing values, ambiguity, timestamp coverage, source coverage, and relation/entity coverage. |

## High-Leverage Next Work

1. Define and materialize a real unified intermediate record.
   Proposed artifact: `data/processed/intermediate_records.jsonl`, one row per
   raw source record version, not one row per chunk. It should include a stable
   raw-store reference, normalized source metadata, extracted mentions, candidate
   relations, feature counters, status, and warning flags.

2. Rename the overloaded source concepts before adding fields.
   Suggested canonical terms to confirm:
   - `connector_source`: `otx`, `mitre`, `pdns`, `vt`, `whois`, `pdf`
   - `source_class`: ontology, weakly-labeled, unlabeled-narrative, infrastructure
   - `publisher_category`: government, vendor, community, knowledge-base, threat-intelligence-platform, other

3. Add temporal policy as data, not prose.
   The intermediate schema should distinguish source publication time, source
   modified time, observed first/last, and project fetched time. It should also
   carry `timestamp_quality` and `temporal_split`.

4. Materialize entity and relation mentions before resolution.
   Current code resolves many things correctly, but the target wants candidate
   inventories. Add mention rows that preserve raw value, normalized value,
   entity/relation type, source field, extraction method, confidence if source
   supplied it, and ambiguity state.

5. Decide whether Event/Report is a first-class entity.
   This is the biggest model fork. If yes, many current facts become
   Event-centered edges first, then evidence-supported aggregate facts second.

6. Build a generated processing report.
   Minimum sections: source coverage, raw coverage, timestamp coverage, entity
   type coverage, relation predicate coverage, ambiguity/orphan counts,
   missing-value counts, and feature coverage.

## Scope Handling For Extra Ideas

The source document is the baseline requirement. Reasonable refinements that are
not explicit in the source document should be tracked as open questions or open
issues, not silently promoted to mandatory scope.

During implementation, these refinements can still be included when they are a
natural consequence of the chosen schema or have low cost. Otherwise they should
remain documented so a later pass can decide whether to refine or implement
them.

This keeps the analysis honest:

- requirements from the teammate document are treated as baseline;
- confirmed design constraints are treated as accepted constraints;
- additional useful ideas are preserved as open questions;
- implementation can opportunistically support them without pretending they were
  already required.

## Grill Questions To Resolve

1. What is the canonical Stage-1 record unit: raw source record version,
   logical report/event, or both with explicit links? Chunk is excluded here
   because it is a RAG projection.

2. Should `Event or Report` become a true Entity in the knowledge layer, or is
   current `Document/Chunk/Evidence` enough and the target wording should be
   mapped onto Evidence?

3. Should `source_type` be retired as a field name because it now collides with
   the target document? If not, which meaning wins?

4. For OTX, is `adversary x attack_id` a direct attribution/usage claim, an
   indirect weak label, or a candidate relation that must remain untrusted until
   corroborated?

5. The target says preprocessing should preserve confidence signals, not
   calculate reliability/confidence. Current `facts.py` assigns confidence tiers
   and aggregate credibility. Should that move out of preprocessing, or is M3
   already considered a later knowledge-construction stage?

6. Which timestamp controls train/test split: report publication, source
   modified time, observed first/last, or project fetch time? What should happen
   when only `fetched_at` exists?

7. Are tags and external references graph entities, filter metadata, or both?

8. Should the first graph-ready output target Neo4j import CSVs, JSONL tables
   consumed by `load_facts_neo4j.py`, or both?

## ADR Status

No ADR was created in this pass. The unresolved questions above are real policy
forks, but no option has been selected yet.
