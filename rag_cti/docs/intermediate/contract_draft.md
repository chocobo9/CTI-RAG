# Intermediate Dataset Contract Draft

Date: 2026-06-27

Location category: active Intermediate draft.

Status: draft for discussion, with v0.1 implementation notes. This document
designs the teammate-facing data contract and records the current implementation
boundary.

Current integration boundary: the v0.1 `rag_cti.intermediate` package is an
independent offline data-preparation module. It builds and validates
intermediate delivery packages, and includes smoke-level RAG/GNN consumer
projections. It is not wired into the production RAG ingestion, indexing,
retrieval/runtime path, Neo4j import path, or a teammate GNN training pipeline.

## V0.1 Implementation And Delivery Status

As of 2026-06-28, the v0.1 intermediate data-processing package has been
implemented and acceptance-audited for the current Stage 1 scope.

Delivery package:

- `data/deliveries/intermediate_v0_1_2026-06-28/`
- `data/deliveries/intermediate_v0_1_2026-06-28.zip`

Repro/audit runner:

- `scripts/build_intermediate_v0_1_delivery.py`

Delivered source scope:

- OTX: 20 real `data/raw/otx` samples.
- pDNS: 20 real `data/raw/pdns` RawStore wrapper samples.
- VirusTotal: 20 real `data/raw/vt` RawStore wrapper samples.
- MITRE: full local ATT&CK bundle records supported by the v0.1 exporter.

Delivered source counts: `{"mitre": 22125, "otx": 20, "pdns": 20, "vt": 20}`.
Delivered artifact counts: `intermediate_records=22185`,
`entity_mentions=45981`, `relation_mentions=24751`,
`attribution_signals=45`, `record_features=22185`.

The final acceptance audit passed. `validate_delivery(...)` passed with 0
failures and 54 pDNS publisher-category warnings.

This is not a full OTX/pDNS/VT corpus export, not a production RAG/GNN/Neo4j
exporter, and not final labelling/confidence/source-reliability output.

As of this v0.1 checkpoint, no existing RAG index is rebuilt from the
intermediate package. Existing RAG chunk ids, vector payloads, Qdrant writes,
and runtime retrieval behaviour remain on the current RAG pipeline. Downstream
integration is intentionally deferred so the reusable intermediate contract can
be reviewed independently before consumer-specific adapters are productionized.

## Purpose

The intermediate dataset is a reusable CTI modelling substrate between raw data
and downstream consumers.

```text
raw source records
  -> intermediate dataset contract
  -> consumer-specific projections
       -> RAG chunks and vector payloads
       -> GNN nodes, edges, features, attribution signals
       -> Neo4j import tables
       -> labelling algorithm inputs
```

The contract must let a teammate consume cleaned CTI data without inheriting
RAG-specific choices such as chunking, vector payload shape, or retrieval doc ids.
The current v0.1 implementation stops at the intermediate delivery and
smoke-level projection proof; production consumer integration remains a later
task.

## Non-Goals

The intermediate dataset should not:

- compute final ground truth labels;
- choose the final GNN architecture or graph schema;
- collapse all evidence into one final Fact table;
- make RAG chunks the base unit of the data;
- discard ambiguity just because a downstream consumer may prefer clean labels.

## Confirmed Constraints

- Outputs use JSON-family formats. Large tables should be JSONL.
- The delivery package must include preserved raw data. Intermediate tables may
  reference raw records instead of duplicating full raw payloads inline.
- Derived rows must trace back to raw source records and, where feasible, source
  fields.
- Timestamp information must be preserved well enough for temporal split and
  leakage analysis.
- Extra refinements not explicit in the teammate document should be preserved as
  deferred questions or deferred issues, not silently promoted to mandatory
  scope.

## Naming Boundary

Avoid using `source_type` without qualification. It currently means too many
things.

Use these names instead:

| Name | Meaning | Examples |
| --- | --- | --- |
| `connector_source` | Which collection/connector produced the record | `otx`, `mitre`, `pdns`, `vt`, `whois`, `pdf` |
| `source_class` | Modelling role of the source | `ontology`, `weakly_labeled_narrative`, `unlabeled_narrative`, `infrastructure` |
| `publisher_category` | External publisher category | `vendor`, `government`, `community`, `knowledge_base`, `threat_intelligence_platform`, `other` |

## Alignment With Source Output Format

The source document's `Output format` section describes a "Structured CTI
Representation". It is not a strict file schema, but it does specify the
information the cleaned dataset should preserve:

- entities, relationships, attribution claims, and supporting metadata;
- relationship families such as `USES`, `ATTRIBUTED_TO`, `TARGETS`,
  `ASSOCIATED_WITH`, `PART_OF`, and `OBSERVED_IN`;
- timestamp signals: report publication date, first seen / last seen, campaign
  time period;
- source metadata: source name and report identifier;
- source type in the document's sense: government, vendor, community, knowledge
  base, threat intelligence platform, or other;
- label availability: direct attribution, indirect attribution, no attribution;
- attribution confidence only if the source provides it;
- supporting source count, conflicting source count, and evidence count;
- alias information for threat actors, campaigns, and malware.

This contract maps those requirements onto JSON-family artifacts. It should not
invent source reliability or attribution confidence when the raw data does not
provide it.

## Source Scope Stance

For the first contract, source scope only needs to state what was collected and
how many records are present per source. It does not need to claim that a source
is globally complete.

Minimum source scope fields:

- `connector_source`
- `raw_collection`
- `record_count`
- optional `notes`

This matches the current project reality: the RAG system already records local
raw/processed counts, and the dataset may grow later with more records or new
sources through the same intermediate layer.

## Source Field Mapping Draft

This draft maps current local raw/processed fields to the teammate document's
structured CTI representation. It is source-backed only; fields not present in
current raw data should remain null or deferred rather than fabricated.

| Source | Source-backed fields available now | Contract mapping | Notes / deferred |
| --- | --- | --- | --- |
| OTX | `id`, `name`, `description`, `created`, `modified`, `author`, `author_name`, `adversary`, `attack_ids`, `malware_families`, `targeted_countries`, `industries`, `indicators`, `references`, `tags`, `TLP` | IntermediateRecord source/timestamps; EntityMention for actor, technique, malware/family, country, industry/sector if used, indicators, tags, references; source contributor metadata for `author` / `author_name`; RelationMention for source-backed adversary-to-technique/family/country candidate relations; AttributionSignal for `adversary`. | `author` stays metadata-first; OTX `adversary` maps to `weak_direct_attribution`; exact downstream use of `industries` as sector remains deferred. |
| MITRE ATT&CK | STIX object `id`, `type`, `name`, `description`, `created`, `modified`, aliases, external references, kill-chain phases, relationship `relationship_type`, `source_ref`, `target_ref` | Ontology/source metadata; EntityMention for groups, software, campaigns, techniques, tactics, mitigations, detection strategies; RelationMention for source-backed STIX relationships (`uses`, `attributed-to`, `mitigates`, `detects`) and ontology edges. | Publisher category is `knowledge_base`; do not fabricate target relationships absent from ATT&CK bundle. Only `attributed-to` is a direct attribution/labelling cue; `uses`, `mitigates`, and `detects` remain source-backed relations with `label_availability=none`. |
| pDNS | Raw `passive_dns` records; projected `domain`, `first_seen`, `last_seen`, `resolutions`, `subdomains`, `ip_addresses`, `asns` | Infrastructure EntityMention for domain, IP, ASN, country, subdomain; RelationMention for `resolves-to`, `belongs-to`, `located-in`, `uses-nameserver`, `has-subdomain`; timestamps from observed first/last. | No direct attribution; any attribution is later inherited via joins, not source-provided. |
| VirusTotal | Raw domain response `data.id`, attributes such as `creation_date`, `expiration_date`, `last_modification_date`, `last_dns_records`, `last_analysis_stats`, `categories`, `tags`, `registrar`, `whois`, `rdap`, certificate fields | Infrastructure/enrichment metadata; EntityMention for domain, nameservers, IPs if extracted, tags/categories if used; RelationMention for DNS-derived `resolves-to` and `uses-nameserver`; timestamp candidates from VT attributes. | Treat as enrichment/source evidence, not attribution; preserve VT fields as metadata/features first, graph-node promotion deferred. |
| PDF reports | Raw PDF blob manifests: filename, sha256, size, content type; processed chunks have filename/page/section fields | Raw preservation and RAG text source; possible EntityMention/RelationMention only if a parser extracts entities/relations from text with provenance. | Publication date, author, organization, report identifier, and section identity are deferred unless extracted with provenance. |
| WHOIS | Script support exists, local raw missing in current package | If collected, likely infrastructure metadata for domain, registrar, dates, registrant, nameservers. | Local raw missing; cannot map coverage until collected/present. |

This mapping should be refined before implementation, but it already sets the
important boundary: source fields drive extraction. The schema should tolerate
nulls and missing source-specific fields rather than forcing all sources into the
same populated shape.

## Author / Contributor Field Stance

OTX `author` and `author_name` are useful, but they should not be confused with
threat actors or final source reliability. In OTX they usually identify the
account or contributor that created/submitted the pulse, not necessarily the
original organization that first observed the intrusion.

For the first contract, preserve these fields as provenance metadata:

- source contributor identity or handle;
- source population and coverage analysis;
- possible source-bias or duplicate-source analysis later;
- optional downstream feature, if the labelling pipeline chooses to use it.

Do not use OTX author as a ground-truth label, reliability score, or core graph
entity by default. It can become an author/source node only in a projection that
explicitly needs provenance graph structure.

## Relationship Mapping Stance

Relationship extraction should use source-provided structure when available. The
contract should not invent relations just because the source document lists them.

For example, if current sources provide `uses`, `attributed-to`, `targets`,
`resolves-to`, `belongs-to`, or `located-in`, those can be preserved and mapped.
If the source document lists `ASSOCIATED_WITH`, `PART_OF`, or `OBSERVED_IN` but
the current raw data does not provide a backed relation, those predicates should
remain open vocabulary candidates, not fabricated edges.

The first relationship vocabulary should therefore distinguish:

- source-backed mapped predicates;
- source-backed unmapped predicates;
- document-proposed predicates with no current source backing.

`label_availability` is not how the contract records whether a relation is
source-backed. A source-backed relation is represented by a `RelationMention`
whose `predicate.mapping_status` and `derivation.extraction_method` describe how
the relation came from source structure or text. `label_availability` only
describes whether the record or relation carries an attribution/labelling cue
for downstream labelling.

Consequences for v0.1:

- MITRE `attributed-to` has `label_availability=direct` and emits a
  `direct_attribution` signal.
- MITRE `uses`, `mitigates`, and `detects` have `label_availability=none`, while
  still being source-backed `RelationMention` rows.
- OTX `adversary` emits a `weak_direct_attribution` signal. Related OTX
  co-occurrence relations are source-backed relation evidence, not the label
  carrier.

## Overlap And Identity Resolution Stance

Overlapping data should be preserved in a way that supports multiple downstream
uses. The intermediate layer should not collapse all overlap into one final
answer too early.

There are at least three overlap cases:

- the same real-world entity appears under different names or aliases;
- the same indicator appears in multiple records or sources;
- the same relation or claim appears with multiple pieces of support, or with
  conflicting support.

The current RAG/knowledge pipeline already handles part of this conservatively:

- actor, malware/family, campaign, technique, mitigation, and detection-strategy
  mentions can resolve to canonical entities when an exact source-backed id,
  name, or alias match exists;
- fuzzy, substring, ambiguous, or unsupported matches are kept as merge
  candidates or orphan entities instead of being auto-merged;
- typed indicators are deduplicated by normalized indicator type and value, while
  retaining the source records that mentioned them;
- repeated relation triples become one Fact with multiple supports;
- conflicting single-valued claims are flagged, not resolved away.

This is useful but not complete entity disambiguation. Non-MITRE aliases, vendor
synonyms, spelling variants, and actor names absent from the ontology may remain
separate. The contract should therefore preserve raw mention text, normalized
value, resolution method, canonical entity id when available, merge candidates,
and support/source counts. A projection may choose to collapse these later, but
the reusable dataset should retain the ambiguity.

## Publisher Category Stance

The source document's `Source Type` means publisher category, such as government,
vendor, community, knowledge base, threat intelligence platform, or other. The
first contract can include `publisher_category`, but unknown or unclear cases
should be marked `unknown` rather than guessed.

V0.1 publisher category defaults:

- `otx`: `threat_intelligence_platform`
- `mitre`: `knowledge_base`
- `vt`: `vendor`
- `pdns`: `unknown`
- `whois`: `unknown`
- `pdf`: `unknown` unless a report publisher is extracted with provenance

## Record Unit

Recommended base unit: one `IntermediateRecord` per raw source record version.

Why this default:

- it aligns with raw preservation and append-only RawStore;
- it keeps provenance precise;
- it lets later projections decide whether to group records into events,
  reports, campaigns, or chunks;
- it avoids making RAG chunking decisions part of the reusable dataset.

V0.1 decision: do not materialize Report/Event as a base artifact. If added
later, it should link to one or more IntermediateRecords rather than replace
them.

## Core Artifact Set

The artifact names below prioritize the source document's terminology. In
particular, "Metadata and Attribution Signals" is represented as
`attribution_signals.jsonl`, not a generic label table.

## Schema Contract v0.1

This section defines the first schema pass. It is intentionally conservative:
required fields are the fields needed for joins, traceability, validation, and
consumer projections. Required means the key must exist; it does not mean the
value is always known. Unknown source-backed values should be `null`, `unknown`,
or `unmapped` according to the field type.

Schema v0.1 was stress-tested with 10 representative processed records in
`docs/intermediate/SNAPSHOT_20260628_schema_dry_run_10_records.md`. That dry run should be treated
as evidence for schema refinement, not as an implementation output.

## Schema v0.1 Decision Close-Out

Dry-run follow-up decisions:

- `EntityMention` rows should default to one row per distinct source-field value
  within an IntermediateRecord, not one row per repeated observation. Preserve
  repeated observations with `occurrence_count` and optional observed ranges.
  True occurrence-level rows can be added later for narrative extraction with
  text spans.
- Entity mentions must be built from raw/source fields during extraction. A flat
  processed `entity_ids[]` list can validate or enrich output, but it is not
  enough to reconstruct source-field provenance.
- Indicator mentions should preserve source-provided value type when available:
  raw OTX indicator type, canonical indicator type, and normalized value. Missing
  indicator type is a warning, not a schema failure, for legacy processed rows.
- `attribution_signals.jsonl` remains a separate v0.1 artifact. Relation
  mentions may carry `label_availability`, but attribution signals are the
  teammate-facing labelling/provenance cues.
- OTX `adversary` defaults to `weak_direct_attribution`, not final ground truth.
  A downstream labelling algorithm may later promote, reject, or weight it.
- ID generation should use one deterministic helper with documented input tuples
  and collision validation. Do not hand-maintain ids.
- PDF/report handling remains an open interface for v0.1. Preserve raw blobs and
  existing metadata, but defer section/chunk identity decisions.

Global row rules:

- every JSONL row must include a stable id field for its artifact;
- every derived row must include `record_id`;
- every source-derived value should preserve either `raw_value`, `source_field`,
  or both;
- controlled fields should use the vocabulary below, while raw source wording
  remains in raw fields;
- arrays should be present as empty arrays when no values exist;
- timestamps should be ISO 8601 strings when known, else `null`;
- no row should embed a full raw payload unless a later delivery explicitly opts
  into a portable embedded-raw package.

### ID Construction Rules v0.1

IDs should be deterministic and reproducible. Re-running preprocessing over the
same raw snapshot and schema version should produce the same ids. Random UUIDs
and global auto-increment counters should not be used for contract ids.

General rules:

- use source-provided ids when they are authoritative identities, but keep them
  in explicit source fields such as `source_record_id` or `ontology_id`;
- use contract ids as join keys, not as replacements for raw source ids;
- hash composite keys with a clear delimiter, such as `\x1f`, so slot boundaries
  cannot collide;
- use lowercase hex SHA-256 prefixes for derived ids; the current RAG pipeline
  commonly uses 16 hex characters. For the intermediate delivery, prefer 24 hex
  characters for newly minted ids unless readability or compatibility requires
  16;
- keep projection ids separate: RAG chunk ids, GNN node ids, and Neo4j import ids
  are downstream projection ids, not base intermediate ids.

Collision stance:

- cryptographic hash collisions are possible in theory but should be negligible
  at this dataset scale, especially with 24 hex characters;
- semantic collisions are the larger practical risk. For example, using only an
  OTX pulse id without `connector_source`, or using source id without a version
  key, can collapse records that should remain distinct;
- validation should fail if the same contract id is produced by two different
  source keys or id input tuples;
- if an id collision is detected, the fix is to extend the hash prefix or correct
  the id input tuple, not to switch to random ids.

ID roles:

- join key: connect records, mentions, relations, attribution signals, features,
  and projections;
- deduplication key: intentionally collapse identical identities or relation
  claims when the id rule defines them as the same thing;
- traceability key: return from a derived row to the raw record and source field;
- version comparison key: compare two deliveries and identify added, removed, or
  changed rows;
- caching/indexing key: let downstream systems build indexes without inventing
  their own unstable row ids.

Recommended id rules:

| ID | Rule | Example |
| --- | --- | --- |
| `dataset_id` | Human-chosen stable dataset slug. Does not change for a new version of the same dataset family. | `cti_rag_stage1` |
| `dataset_version` | Delivery version or snapshot label. Changes when source scope, raw snapshot, or extraction rules change. | `2026-06-27-draft` |
| `record_id` | One id per raw source record version: `record_{connector_source}_{source_record_key}_{version_key}`. `source_record_key` is a safe source id when available, otherwise a hash of source identity. `version_key` should prefer raw payload hash; if absent, use fetched/version timestamp. | `record_otx_547e0a9511d4080d5a98d83f_2026-06-15T00-00-00Z` |
| `entity_mention_id` | Hash of `record_id`, `source_field`, `entity_type`, normalized/raw value, and value type. Add occurrence index only for true occurrence-level rows. | `em_3f2a91c0d87e42aa9c4b72e1` |
| `relation_mention_id` | Hash of `record_id`, subject mention key, mapped/raw predicate, object mention key, source field, and occurrence index. | `rm_6b8d14f3a2c019ef75a4d230` |
| `attribution_signal_id` | Hash of `record_id`, `signal_type`, `target_entity_type`, `raw_label`, `source_field`, and linked relation/mention id when available. | `as_a47d9f22c0018b4e91d6ae30` |
| `entity_id` | Canonical identity id when resolution is available. MITRE-backed entities use `{entity_type}_{ontology_id}`. Orphans use `{entity_type}_orphan_{hash(entity_type, normalized_name)}`. Indicators use `indicator_{hash(canonical_indicator_type, value)}`. | `actor_G0003`, `actor_orphan_f35a...`, `indicator_0028...` |
| `raw_sha256` | Full SHA-256 of the delivered raw payload when possible. This is content integrity, not a human join key. | `b0...` |

Important distinction:

- `source_record_id` answers "what did the source call this record?"
- `record_id` answers "which version of that raw record is this row about?"
- `entity_mention_id` answers "where did this source record mention a value?"
- `entity_id` answers "which canonical entity do we think this mention refers to?"

Do not add ids just because a new table exists. Add an id only when the table
has a distinct identity grain that other rows may reference.

The v0.1 id set is close to minimal:

- dataset/delivery ids identify the package;
- `record_id` identifies the raw source record version;
- mention ids identify source occurrences;
- relation mention ids identify source-backed candidate edges;
- attribution signal ids identify labelling/provenance cues that may exist
  without becoming graph edges;
- `entity_id` identifies resolved canonical entities;
- `raw_sha256` identifies raw payload bytes for integrity.

IDs that should stay out of the base intermediate contract by default:

- RAG `chunk_id`;
- final `fact_id` / `support_id`;
- GNN node or edge ids;
- Neo4j import ids;
- train/test split assignment ids.

Those ids can be created inside projection artifacts if needed. They should link
back to base ids instead of replacing them.

V0.1 decision: require full `raw_sha256` for raw files included in a new
intermediate delivery package. Legacy processed fixtures may use fetched/version
timestamps as compatibility keys, but package validation should warn when
`raw_sha256` is missing.

### Required Fields By Artifact

| Artifact | Required fields | Nullable required fields | Must not contain |
| --- | --- | --- | --- |
| `source_manifest.json` | `dataset_id`, `dataset_version`, `schema_version`, `generated_at`, `sources[]` | none except optional source notes | per-record extracted entities or relations |
| `source_manifest.json.sources[]` | `connector_source`, `source_class`, `publisher_category`, `record_count`, `raw_collection`, `provides` | `publisher_category` may be `unknown` | raw payloads |
| `intermediate_records.jsonl` | `record_id`, `raw_ref`, `source`, `timestamps`, `record_signals`, `counts`, `processing_status` | timestamp values, `raw_sha256`, signal details | RAG chunk ids, embedding/vector fields, final graph labels |
| `entity_mentions.jsonl` | `entity_mention_id`, `record_id`, `raw_value`, `normalized_value`, `entity_type`, `source_field`, `extraction_method`, `occurrence_count`, `value_type`, `resolution`, `ambiguity`, `merge_candidates` | `normalized_value`, `source_field`, `value_type.raw`, `value_type.canonical`, all unresolved `resolution` values | final GNN node ids unless they are explicit projection ids |
| `relation_mentions.jsonl` | `relation_mention_id`, `record_id`, `subject`, `predicate`, `object`, `derivation`, `ambiguity` | unresolved subject/object ids, `attribution_confidence` | fabricated document-proposed relations with no source backing |
| `attribution_signals.jsonl` | `attribution_signal_id`, `record_id`, `signal_type`, `target_entity_type`, `raw_label`, `source_field`, `derivation_method` | `raw_label`, `resolved_entity_id`, `source_provided_confidence` | final ground-truth labels or reliability scores |
| `record_features.jsonl` | `record_id`, `source_features`, `timestamp_features`, `content_features`, `label_features`, `ambiguity_features` | feature values not computable from current data | model-specific learned embeddings or train/test split labels |
| `processing_report.json` | `dataset_id`, `dataset_version`, `schema_version`, `generated_at`, `counts`, `coverage`, `warnings`, `open_issues` | none; missing sections should be empty objects/arrays | per-row raw data |

### Controlled Vocabulary v0.1

These are contract-level controlled values. They should stay small in the first
delivery. New values can be added by schema version, but source-specific raw
values should not silently become new contract values.

| Field | Values |
| --- | --- |
| `connector_source` | `otx`, `mitre`, `pdns`, `vt`, `whois`, `pdf`, `unknown` |
| `source_class` | `ontology`, `weakly_labeled_narrative`, `unlabeled_narrative`, `infrastructure`, `unknown` |
| `publisher_category` | `vendor`, `government`, `community`, `knowledge_base`, `threat_intelligence_platform`, `other`, `unknown` |
| `entity_type` | `actor`, `campaign`, `family`, `technique`, `tactic`, `indicator`, `domain`, `ip`, `url`, `file_hash`, `email`, `asn`, `location`, `sector`, `organization`, `cve`, `tag`, `external_reference`, `source`, `source_contributor`, `timestamp`, `mitigation`, `detection-strategy`, `unknown` |
| `predicate.mapped_value` | `uses`, `attributed-to`, `targets`, `resolves-to`, `belongs-to`, `located-in`, `uses-nameserver`, `has-subdomain`, `mitigates`, `detects`, `unmapped` |
| `predicate.mapping_status` | `mapped`, `source_backed_unmapped`, `document_proposed_unsupported`, `unknown` |
| `extraction_method` / `derivation_method` | `source_field`, `structured_relation`, `structured_cooccurrence`, `text_extraction`, `inferred_join`, `manual_review`, `unknown` |
| `resolution_method` | `exact_id`, `exact_name`, `exact_alias`, `embedded_id`, `orphan`, `unresolved`, `not_applicable` |
| `merge_candidate_reason` | `ambiguous_name`, `ambiguous_alias`, `substring`, `unknown` |
| `ambiguity.status` | `resolved`, `unambiguous`, `ambiguous`, `candidate`, `unresolved`, `not_applicable` |
| `timestamp_basis` | `published`, `source_modified`, `observed_range`, `fetched_only`, `missing`, `mixed` |
| `label_availability` | `direct`, `indirect`, `none`, `unknown` |
| `signal_type` | `direct_attribution`, `weak_direct_attribution`, `indirect_attribution`, `supporting_evidence`, `conflicting_attribution`, `no_attribution` |
| `processing_status.status` | `ok`, `partial`, `failed`, `skipped` |

Vocabulary notes:

- `family` is kept because the current RAG pipeline maps MITRE malware and tools
  into a shared software/family identity class. Preserve source-specific raw
  object type separately when malware/tool distinction matters.
- `source_contributor` covers OTX `author` / `author_name` and similar fields.
  It is provenance metadata by default, not a threat actor.
- `unmapped` is allowed only as a mapped predicate placeholder on a
  source-backed relation. Document-proposed but unsupported predicates should be
  reported, not emitted as real relations.
- `label_availability` means attribution/labelling cue availability. It does not
  mean a relation is or is not source-backed; use `relation_mentions`,
  `predicate.mapping_status`, and `extraction_method` for that.
- `unknown` is for missing or not-yet-classified values. It should be counted in
  `processing_report.json` so it does not quietly disappear.

### `source_manifest.json`

Dataset-level source inventory.

Purpose:

- declare selected sources;
- describe collection scope at least as collected record counts;
- distinguish connector source, source class, and publisher category;
- document whether a source can provide labels, enrichment, timestamps, aliases,
  campaign names, malware names, tools, techniques, or only indicators.

Suggested shape:

```json
{
  "dataset_id": "cti_rag_stage1",
  "schema_version": "draft-0",
  "sources": [
    {
      "connector_source": "otx",
      "source_class": "weakly_labeled_narrative",
      "publisher_category": "threat_intelligence_platform",
      "selected_scope": "selected pulse set",
      "record_count": 2056,
      "raw_collection": "raw/otx",
      "provides": {
        "labels": true,
        "enrichment": false,
        "timestamps": true,
        "actor_aliases": false,
        "campaign_names": true,
        "malware_names": true,
        "tools": false,
        "techniques": true,
        "indicators": true
      }
    }
  ]
}
```

### `intermediate_records.jsonl`

One row per raw source record version.

Purpose:

- normalize record-level metadata;
- preserve raw-store coordinates;
- summarize extraction status and available signals;
- provide the join point for mentions, features, and projections.

Suggested row shape:

```json
{
  "record_id": "record_otx_547e0a9511d4080d5a98d83f_2026-06-15T00-00-00Z",
  "raw_ref": {
    "connector_source": "otx",
    "source_id": "547e0a9511d4080d5a98d83f",
    "fetched_at": "2026-06-15T00:00:00Z",
    "raw_path": "raw/otx/547e0a9511d4080d5a98d83f/2026-06-15T00-00-00Z.json",
    "raw_sha256": "b09f2c1b5d35f1c7f2f6e7e3d37d8c42bc8df7d1e61c4e36c9d21821e4f6a6cb"
  },
  "source": {
    "connector_source": "otx",
    "source_class": "weakly_labeled_narrative",
    "publisher_category": "threat_intelligence_platform",
    "source_name": "AlienVault OTX",
    "source_record_id": "547e0a9511d4080d5a98d83f"
  },
  "timestamps": {
    "published_at": null,
    "modified_at": "2017-08-24T09:26:22.235000Z",
    "observed_first": null,
    "observed_last": null,
    "fetched_at": "2026-06-15T00:00:00Z",
    "timestamp_basis": "source_modified"
  },
  "record_signals": {
    "label_availability": "direct",
    "has_attribution_confidence": false,
    "ambiguity_flag": false
  },
  "counts": {
    "entity_mentions": 3,
    "relation_mentions": 2,
    "indicators": 50,
    "tags": 1,
    "references": 1
  },
  "processing_status": {
    "status": "ok",
    "warnings": []
  }
}
```

Notes:

- `raw_ref` is the contract's raw-object preservation mechanism. The raw object
  itself stays in raw storage unless a later consumer needs embedded raw payloads.
- This is a contract reference, not necessarily a new index. The existing raw
  directory / RawStore layout can satisfy it. A separate `raw_index.jsonl` is an
  optional portability artifact if the dataset must be shipped without the full
  repository layout.
- `timestamp_basis` is descriptive, not a reliability score. It says which
  timestamp kind is available for later split analysis.
- Temporal split assignment should be derived later, after a split policy is
  chosen.

### `entity_mentions.jsonl`

One row per extracted entity occurrence or source-field entity value.

Purpose:

- preserve source wording before entity resolution;
- support alias review and ambiguity handling;
- provide candidate nodes for GNN/Neo4j projections.

Suggested row shape:

```json
{
  "entity_mention_id": "em_3f2a91c0d87e42aa9c4b72e1",
  "record_id": "record_otx_547e0a9511d4080d5a98d83f_2026-06-15T00-00-00Z",
  "raw_value": "Cleaver",
  "normalized_value": "Cleaver",
  "entity_type": "actor",
  "source_field": "adversary",
  "extraction_method": "source_field",
  "occurrence_count": 1,
  "value_type": {
    "raw": null,
    "canonical": null
  },
  "confidence": null,
  "ambiguity": {
    "status": "resolved",
    "reason": null,
    "candidate_entity_ids": []
  },
  "merge_candidates": [],
  "resolution": {
    "entity_id": "actor_G0003",
    "canonical_name": "Cleaver",
    "ontology_id": "G0003",
    "resolution_method": "exact_alias"
  }
}
```

Candidate entity types should cover the teammate document's inventory where
source-backed. In the first contract, malware and tool mentions may normalize to
`family` to match the current RAG identity layer, while preserving their raw
source type. Author-like fields should normalize to `source_contributor`, not
`actor`.

Deferred: deciding which tags, references, sectors, organizations, timestamps,
or source contributors become first-class graph nodes belongs to the downstream
projection design. Schema v0.1 preserves them as source-backed mentions,
features, or metadata without requiring graph promotion.

### `relation_mentions.jsonl`

One row per candidate relationship extracted before final graph projection.

Purpose:

- preserve raw endpoints and raw/mapped relation semantics;
- distinguish direct source relationships from co-occurrence and enrichment;
- support multiple downstream graph schemas.

Suggested row shape:

```json
{
  "relation_mention_id": "rm_6b8d14f3a2c019ef75a4d230",
  "record_id": "record_otx_547e0a9511d4080d5a98d83f_2026-06-15T00-00-00Z",
  "subject": {
    "raw_value": "Cleaver",
    "entity_mention_id": "em_3f2a91c0d87e42aa9c4b72e1",
    "entity_type": "actor"
  },
  "predicate": {
    "raw_value": "adversary+attack_ids co-occurrence",
    "mapped_value": "uses",
    "mapping_status": "mapped"
  },
  "object": {
    "raw_value": "T1016",
    "entity_mention_id": "em_8a15e9df341270bc291fd8e4",
    "entity_type": "technique"
  },
  "derivation": {
    "source_field": "adversary,attack_ids",
    "extraction_method": "structured_cooccurrence",
    "evidence_type": "ttp",
    "label_availability": "none",
    "attribution_confidence": null
  },
  "ambiguity": {
    "status": "unambiguous",
    "notes": []
  }
}
```

V0.1 decision: preserve OTX `adversary x attack_ids` as a source-backed
`RelationMention` with `derivation_method=structured_cooccurrence`. Keep its
label use separate: OTX `adversary` contributes `weak_direct_attribution`, not a
verified training label.

This distinction is intentional: the relation is source-backed because it comes
from source fields, but `label_availability` remains about attribution/labelling
cues. Relation backing is expressed by the `RelationMention`, mapped predicate,
and structured derivation method.

### `attribution_signals.jsonl`

One row per attribution or labelling cue that may be useful to a downstream
labelling algorithm.

Purpose:

- represent the source document's "Metadata and Attribution Signals" explicitly;
- avoid conflating source-provided attribution with final ground truth;
- separate direct labels, indirect labels, enrichment-only evidence, and absence
  of attribution;
- let downstream labelling choose how to weight each signal.

Suggested row shape:

```json
{
  "attribution_signal_id": "as_a47d9f22c0018b4e91d6ae30",
  "record_id": "record_otx_547e0a9511d4080d5a98d83f_2026-06-15T00-00-00Z",
  "signal_type": "weak_direct_attribution",
  "target_entity_type": "actor",
  "raw_label": "Cleaver",
  "resolved_entity_id": "actor_G0003",
  "source_field": "adversary",
  "source_provided_confidence": null,
  "derivation_method": "source_field",
  "notes": []
}
```

Suggested `signal_type` values:

- `direct_attribution`
- `weak_direct_attribution`
- `indirect_attribution`
- `supporting_evidence`
- `conflicting_attribution`
- `no_attribution`

Decision: keep `attribution_signals.jsonl` separate in schema v0.1. It is the
teammate-facing labelling/provenance cue table. Relation mentions may still carry
`label_availability` for graph/projection convenience.

### `record_features.jsonl`

One row per IntermediateRecord with modelling-oriented features.

Purpose:

- preserve feature signals without deciding a model;
- support GNN/labelling input construction;
- make missingness visible.

Suggested row shape:

```json
{
  "record_id": "record_otx_547e0a9511d4080d5a98d83f_2026-06-15T00-00-00Z",
  "source_features": {
    "connector_source": "otx",
    "source_class": "weakly_labeled_narrative",
    "publisher_category": "threat_intelligence_platform"
  },
  "timestamp_features": {
    "has_published_at": false,
    "has_modified_at": true,
    "has_observed_range": false,
    "age_days_at_collection": null,
    "timestamp_basis": "source_modified"
  },
  "content_features": {
    "indicator_count": 50,
    "indicator_type_distribution": {
      "domain": 30,
      "ipv4": 10,
      "url": 10
    },
    "tag_count": 1,
    "reference_count": 1
  },
  "label_features": {
    "label_availability": "direct",
    "has_confidence": false,
    "supporting_sources_count": null,
    "conflicting_sources_count": null
  },
  "ambiguity_features": {
    "ambiguous_entity_mentions": 0,
    "ambiguous_relation_mentions": 0
  }
}
```

V0.1 decision: compute only cheap descriptive features in preprocessing: counts,
timestamp availability, source class/category, label availability, and ambiguity
counts. Do not compute learned features, final source reliability, or final
ground-truth confidence.

### `processing_report.json`

Dataset-level coverage and quality summary.

Purpose:

- tell consumers what the dataset does and does not cover;
- expose missing values and ambiguity;
- make source scope and timestamp quality explicit.

Suggested sections:

```json
{
  "schema_version": "draft-0",
  "source_coverage": {},
  "raw_coverage": {},
  "timestamp_coverage": {},
  "entity_type_coverage": {},
  "relation_predicate_coverage": {},
  "attribution_signal_coverage": {},
  "ambiguity_summary": {},
  "missingness_summary": {},
  "open_questions": []
}
```

## Projection Artifacts

Projection artifacts are not the reusable intermediate contract, but the contract
should make them easy to generate.

Candidate GNN projection artifacts:

- `gnn_nodes.jsonl`
- `gnn_edges.jsonl`
- `gnn_node_features.jsonl`
- `gnn_edge_features.jsonl`
- `gnn_attribution_signals.jsonl`
- `gnn_splits.jsonl`

Candidate RAG projection artifacts:

- chunk JSONL;
- vector payload fields;
- doc ids and parent doc ids.

Candidate Neo4j projection artifacts:

- node import JSONL or CSV-equivalent JSONL;
- edge import JSONL;
- optional import manifest.

Projection artifacts can be delivered together with the intermediate dataset, as
long as they are documented as downstream views rather than the canonical data
contract. This means the same intermediate layer can serve both the current RAG
system and the teammate's modelling workflow:

- RAG consumes a retrieval projection;
- GNN/labelling consumes graph/features/attribution projections;
- Neo4j consumes an import projection.

V0.1 decision: include projection smoke checks, not full production projections.
Any RAG/GNN/Neo4j projection files delivered with v0.1 should be documented as
downstream views, not as the canonical contract.

## Delivery Package Boundary

The delivery package should include both raw data and derived JSON/JSONL
artifacts.

Recommended package shape:

```text
data_delivery/
  raw/
    otx/
    mitre/
    pdns/
    vt/
    whois/
    pdf/
    blobs/
  intermediate/
    source_manifest.json
    intermediate_records.jsonl
    entity_mentions.jsonl
    relation_mentions.jsonl
    attribution_signals.jsonl
    record_features.jsonl
    processing_report.json
  projections/
    gnn/
    neo4j/
    rag/
```

`raw_ref` in `intermediate_records.jsonl` should point to files inside the
delivered `raw/` directory. This keeps raw data preserved and portable while
avoiding duplication of full raw payloads inside every intermediate JSONL row.
`source_manifest.json.sources[].raw_collection` and
`intermediate_records.jsonl.raw_ref.raw_path` are package-relative paths that
begin with `raw/`; repository-relative paths such as `data/raw/...` and absolute
paths are invalid for v0.1 delivery packages.

## Validation And Acceptance Checks

This area needs further discussion, but the first contract should include basic
checks so the delivery is not just a collection of files.

Recommended severity levels:

- **fail**: the package is structurally unusable or provenance is broken;
- **warn**: the package is usable, but expected source-specific data is missing
  or incomplete;
- **report**: coverage/missingness information for downstream interpretation.

Minimum checks:

| Check | Severity | Why |
| --- | --- | --- |
| Every JSON/JSONL artifact parses successfully. | fail | Consumers cannot safely load the package otherwise. |
| Every `IntermediateRecord.record_id` is unique. | fail | Joins across artifacts depend on this key. |
| Every `raw_ref` points to an existing delivered raw file. | fail | Raw preservation and traceability are required. |
| Every derived row with `record_id` points to an existing IntermediateRecord. | fail | Mentions/features/signals must be joinable. |
| Every required field is present, even if the value is `null`. | fail | Schema stability matters more than completeness. |
| Record counts in `source_manifest.json` match delivered raw/intermediate rows. | fail or warn | Fail for intermediate counts; warn for raw variants where legacy/versioned layouts coexist. |
| Source-backed relationship predicates are listed in the relationship vocabulary. | fail | Prevents accidental predicate drift. |
| Document-proposed but unsupported predicates are called out separately. | report | Makes gaps visible without fabricating edges. |
| Optional source-specific fields are missing. | warn | Missingness is expected across heterogeneous sources. |
| Processing report includes source, record, mention, relation, attribution signal, and warning counts. | warn | The data may still be usable, but consumers lose coverage context. |

V0.1 decision: validation should enforce the required field list above. The
10-record dry run is the design check; implementation should add fixture tests
for OTX, MITRE, pDNS/VT, and PDF interface coverage.

## Processing Report Granularity

The processing report is not meant to be a complex analytics product in the
first delivery. Its first purpose is to make coverage and missingness visible.

Recommended first-pass granularity:

- source-level record counts;
- raw coverage counts;
- timestamp field availability counts;
- entity mention counts by entity type;
- relation mention counts by predicate;
- attribution signal counts by signal type;
- warnings for missing raw, invalid records, unsupported relation types, and
  unimplemented source fields.

Field-level coverage can be added later if needed. It is useful, but not required
to understand the first delivery.

## Versioning And Evolution

This first contract is a draft and the dataset will evolve. Source scope is not
fixed: later deliveries may add more records from existing sources or introduce
new sources.

Each delivery should include:

- `dataset_id`
- `dataset_version`
- `schema_version`
- `generated_at`
- source record counts
- notes about added sources or changed extraction rules

Raw data remains the stable preservation layer; intermediate artifacts and
projections are regenerable views over a particular raw snapshot and schema
version.

## Recommended Defaults For First Contract

These are v0.1 defaults after the 10-record dry run. Items in the last column are
deferred concerns, not blockers for the first implementation.

| Topic | V0.1 default | Rationale | Deferred |
| --- | --- | --- | --- |
| Base unit | `IntermediateRecord` = one raw source record version. | This gives stable provenance and avoids binding the contract to RAG chunking or a future graph schema. | Logical Report/Event grouping can be added later as a projection. |
| Raw payload | Store `raw_ref` and full `raw_sha256`; do not embed full raw payload in every row. | Avoids duplicating large raw data while preserving traceability to RawStore. | Embedded raw snippets only if a portable package requires them. |
| Traceability granularity | Use source-field traceability for structured fields; raw-record traceability is acceptable for unstructured text until offsets are needed. | Structured fields make source-field provenance cheap; narrative text extraction may require spans later. | PDF/text spans are later work. |
| Report/Event | Do not make Report/Event the base unit. Preserve enough fields to add it as a projection or grouping layer. | "Event" is a modelling interpretation; source records are more concrete and easier to reproduce. | Teammate-specific event/report nodes belong in projection design. |
| Attribution signals | Keep `attribution_signals.jsonl` separate, while also allowing relation mentions to carry `label_availability`. | Labelling algorithms can consume attribution cues directly without treating every cue as a graph edge. | Weighting/filtering each signal type is downstream model policy. |
| Temporal split | Preserve all candidate timestamps and defer split assignment to a later projection. | Different sources expose different time semantics; a premature split rule risks leakage or data loss. | Choose timestamp priority when building split assignments. |
| Feature computation | Compute cheap descriptive features; do not compute final reliability or confidence. | Counts and distributions are reproducible signals; reliability/confidence belongs to downstream modelling unless source-provided. | Learned/model-specific features stay downstream. |
| Ambiguity | Preserve ambiguity at mention/relation level when available; summarize it in processing report. | Ambiguity is useful for debugging and weak supervision, but consumers may filter it out. | Consumer-specific ambiguity filtering. |
| Projection delivery | Include projection smoke checks; defer full production projections. | The reusable contract should not be shaped around one consumer. | Ready-to-train GNN/RAG/Neo4j exports can follow after v0.1 package validation. |

## Temporal Semantics Draft

Temporal fields should distinguish what happened in the world, what the source
published or modified, and when this project collected the record. The base
contract should preserve timestamp candidates; it should not pretend to know the
correct train/test split timestamp before a split policy is chosen.

Suggested timestamp fields:

| Field | Meaning | Example source |
| --- | --- | --- |
| `published_at` | When the source explicitly provides a publication date, or when a parser extracts one with provenance. Null otherwise. | vendor reports, OTX pulses if source provides it, PDF metadata/text only if extractable |
| `modified_at` | When the source object says it was last modified. | MITRE STIX `modified`, OTX `modified`, VT last modification |
| `observed_first` | Earliest observation time for an indicator or infrastructure fact. | pDNS first seen |
| `observed_last` | Latest observation time for an indicator or infrastructure fact. | pDNS last seen |
| `fetched_at` | When this project collected or stored the raw record. | RawStore fetched_at |
| `timestamp_basis` | Describes which timestamp kind is available for later split analysis. It is not a trust score. | `published`, `source_modified`, `observed_range`, `fetched_only`, `missing` |

`split_time` should not be part of the base IntermediateRecord by default. It is
a derived value produced by a later split policy, for example in a
`split_assignments.jsonl` projection.

Recommended split policy stance for now:

- do not assign train/test split inside the base contract until the teammate
  confirms the policy;
- preserve enough timestamp candidates to compute several split variants later;
- treat `fetched_at` as a weak fallback, not as evidence publication time;
- make records with only weak timestamps visible instead of dropping them.

Deferred: source-specific split policy belongs to the later modelling split
design. Schema v0.1 only preserves timestamp candidates such as `published_at`,
`source_created_at`, `source_modified_at`, `observed_first`, `observed_last`,
and `fetched_at`.

## Attribution Signal Semantics Draft

The contract should preserve labelling cues without deciding ground truth or
source reliability. This matches the current RAG stance: the system can record
whether evidence carries an attribution label, but it cannot prove that OTX or
another source is correct.

Suggested interpretation:

| Signal | Meaning | Example |
| --- | --- | --- |
| `direct_attribution` | Source explicitly names an actor or attribution target. This means "directly asserted", not "verified true". | MITRE `attributed-to` |
| `weak_direct_attribution` | Source field appears attribution-like but is known to be noisy or weak. | OTX adversary when source trust is uncertain |
| `indirect_attribution` | Attribution inherited through a join to an already labelled record. | pDNS domain joined to an attributed OTX pulse |
| `supporting_evidence` | Non-label evidence useful for attribution or graph context. | malware, infrastructure, TTP, victimology |
| `conflicting_attribution` | A competing actor label for the same subject or event. | two sources attribute same campaign differently |
| `no_attribution` | Source provides no attribution label. | raw enrichment record only |

Important boundary: an `AttributionSignal` is not a final label. It is a preserved cue
that a downstream labelling algorithm may accept, reject, weight, or combine.
`direct_attribution` is about how the cue was obtained, not about source
confidence.

`label_availability` follows the same boundary. It describes whether an
attribution/labelling cue is available, not whether a relation is source-backed.
For example, MITRE `attributed-to` is `direct` and emits a
`direct_attribution` signal; MITRE `uses`, `mitigates`, and `detects` are
source-backed relations but have `label_availability=none`.

Relationship to the current RAG system:

- the RAG/knowledge layer already uses a similar idea as
  `label_availability = direct / indirect / none` on supports;
- the intermediate dataset can expose the same kind of signal earlier, before it
  becomes a Fact/support row;
- neither layer should treat source-provided attribution as ground truth unless
  a separate labelling process decides to do so.

Decision: represent OTX `adversary` as `weak_direct_attribution` by default.
This preserves the source cue without treating it as verified ground truth.

## Traceability Semantics Draft

Every derived row should have two levels of provenance where possible:

1. `record_id`: links to the IntermediateRecord.
2. `source_field`: identifies where the value came from inside the raw object.

For structured sources, `source_field` should be explicit:

```json
{
  "record_id": "record_otx_...",
  "source_field": "indicators[].indicator",
  "raw_value": "example.com"
}
```

For unstructured narrative extraction, the first version may use a coarse field
such as `description` or `pdf_text`. A later version can add text spans:

```json
{
  "source_field": "description",
  "text_span": {
    "start": 128,
    "end": 164
  }
}
```

Decision: field-level provenance is enough for the first structured-source
delivery. Text spans for PDF/report extraction remain deferred until a parser
extracts narrative entities or relations with usable offsets.

## PDF / Report Metadata Boundary

The current RAG pipeline extracts the PDF/report fields needed for retrieval and
overlap with the existing data model. Rich report metadata such as publication
date, author, organization, and report identifier has not been fully extracted.

For the first contract, PDF/report metadata beyond already extracted fields
should be treated as deferred. If a parser can extract these fields with
clear provenance, they can populate `published_at`, `source_name`,
`report_identifier`, `author`, or `organization`. Otherwise they should remain
null and be reported as missing/unimplemented.

PDF section/chunk identity is also deferred. Schema v0.1 should keep a stable
interface for preserved PDF blobs and existing RAG metadata, but it does not need
to decide whether report sections are base IntermediateRecords, extracted text
units, or projection rows.

## Deferred Questions

Remaining questions are tracked in
`docs/intermediate/deferred_questions.md`. They are not blockers for
schema v0.1. The first implementation should preserve enough raw/source-field
information to answer them later.
