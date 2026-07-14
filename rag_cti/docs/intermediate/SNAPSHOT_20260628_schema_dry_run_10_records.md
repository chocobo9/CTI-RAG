# SNAPSHOT — Intermediate Schema Dry Run, 10 Records (2026-06-28)

> Intermediate category: schema experiment.
>
> **Status: HISTORICAL SCHEMA EXPERIMENT.** This is validation evidence, not a
> frozen Intermediate contract or current implementation plan.

Date: 2026-06-28

Status: schema validation note. This is not an implementation plan.

## Input

This dry run uses records from `data/processed/v5_staging` as a proxy for source
records:

- `otx.jsonl`
- `mitre.jsonl`
- `mitre_relationships.jsonl`
- `pdns.jsonl`
- `vt.jsonl`
- `pdfs.jsonl`

Important limitation: these files are already RAG-oriented processed records.
They are useful for schema stress testing, but they are not the final raw delivery
package. Any issue below that comes from RAG chunking should be treated as a
contract warning, not as a reason to shape the intermediate contract around
chunks.

Implementation note: this dry run is historical schema-design evidence. The
current concrete v0.1 delivery package is
`data/deliveries/intermediate_v0_1_2026-06-28/`, with the zipped handoff at
`data/deliveries/intermediate_v0_1_2026-06-28.zip`. Use the delivery README and
`acceptance_audit.json` for current package status; use this dry run for why the
schema decisions were made.

## Sample Set

| # | Source | Proxy file:line | Source key | Scenario | Dry-run result |
| --- | --- | --- | --- | --- | --- |
| 1 | OTX | `otx.jsonl:1` | `547e0a9511d4080d5a98d83f` | Direct actor attribution, many indicators, no relation | Fits schema; tests attribution signal without relation mentions. |
| 2 | OTX | `otx.jsonl:309` | `5d89e04cea5c55ee87a6aa05` | Orphan actor plus technique and target relation | Fits schema; tests orphan resolution and source-backed relations. |
| 3 | OTX | `otx.jsonl:36` | `57f45774322d8700c530e56c` | Resolved actor plus multiple target countries | Fits schema; tests repeated target relations and multiple locations. |
| 4 | MITRE object | `mitre.jsonl:1` | `attack-pattern--0042a9f5-f053-4769-b3ef-9ad018dfa298` | Technique ontology object | Fits schema; but processed chunks duplicate the same technique across chunk rows. |
| 5 | MITRE relationship | `mitre_relationships.jsonl:1` | `relationship--00038d0e-7fc7-41c3-9055-edb4d87ea912` | Software/family `uses` technique | Fits schema. |
| 6 | MITRE relationship | `mitre_relationships.jsonl:797` | `relationship--0a69d74a-7662-4d18-99b4-bc1a574b35b4` | Campaign `attributed-to` actor | Fits schema; creates direct attribution signal. |
| 7 | MITRE relationship | `mitre_relationships.jsonl:52` | `relationship--00b2d214-7126-4b80-866c-4321d6ace9b0` | Detection strategy `detects` technique | Fits schema; validates defensive relation vocabulary. |
| 8 | pDNS | `pdns.jsonl:5` | `0-02.net` | Infrastructure observed range and DNS relations | Mostly fits; exposes value-to-entity-id mapping issue. |
| 9 | VirusTotal | `vt.jsonl:1` | `0-02.net` | Enrichment overlapping with pDNS | Mostly fits; tests cross-source overlap and repeated relation support. |
| 10 | PDF | `pdfs.jsonl:3` | `a59146f7ff9e5a45:2` | Narrative section with weak report metadata | Exposes PDF chunk/section boundary issue. |

## Dry-Run Expansions

### 1. OTX: Operation Cleaver

Intermediate record:

```json
{
  "record_id": "record_otx_547e0a9511d4080d5a98d83f_2017-08-24T09-26-22.235000",
  "connector_source": "otx",
  "source_class": "weakly_labeled_narrative",
  "publisher_category": "threat_intelligence_platform",
  "source_record_id": "547e0a9511d4080d5a98d83f",
  "timestamp_basis": "source_modified"
}
```

Derived rows:

- entity mentions: actor `Cleaver` -> `actor_G0003`, 50 indicator values, tag
  `Iran`, one reference URL.
- relation mentions: none, because this record has no `attack_ids`,
  `malware_families`, or `targeted_countries`.
- attribution signals: one `weak_direct_attribution` from `adversary=Cleaver`.

Schema note: this validates that attribution cues can exist without relation
mentions. It also shows that processed OTX rows have lost indicator type details;
the final intermediate builder should read raw OTX indicator objects when
available.

### 2. OTX: Tibetan Groups Targeted with 1-Click Mobile Exploits

Intermediate record:

```json
{
  "record_id": "record_otx_5d89e04cea5c55ee87a6aa05_2019-09-26T11-48-30.366000",
  "connector_source": "otx",
  "source_record_id": "5d89e04cea5c55ee87a6aa05",
  "timestamp_basis": "source_modified"
}
```

Derived rows:

- entity mentions: actor `POISON CARP` -> `actor_orphan_d74345e21cdcef68`,
  technique `T1203` -> `technique_T1203`, location `China` ->
  `location_orphan_259ff18535dc409e`, 50 indicators, 5 tags, 2 references.
- relation mentions:
  - `actor_orphan_d74345e21cdcef68 uses technique_T1203`
  - `actor_orphan_d74345e21cdcef68 targets location_orphan_259ff18535dc409e`
- attribution signals: one `weak_direct_attribution` from `adversary=POISON CARP`.

Schema note: this is a good test for preserving orphan actors instead of forcing
entity resolution.

### 3. OTX: OilRig Malware Campaign Updates Toolset and Expands Targets

Intermediate record:

```json
{
  "record_id": "record_otx_57f45774322d8700c530e56c_2016-10-05T01-30-31.935000",
  "connector_source": "otx",
  "source_record_id": "57f45774322d8700c530e56c",
  "timestamp_basis": "source_modified"
}
```

Derived rows:

- entity mentions: actor `OilRig` -> `actor_G0049`, target countries including
  Turkey, Saudi Arabia, Israel, Qatar, and United States, plus indicators, tags,
  and references.
- relation mentions: five `targets` relations from `actor_G0049` to location
  orphan entities.
- attribution signals: one `weak_direct_attribution` from `adversary=OilRig`.

Schema note: multiple target countries fit the current relation mention design.
The exact order of `targeted_countries[]` should not matter for identity except
where occurrence-level provenance is required.

### 4. MITRE Object: T1055.011 Extra Window Memory Injection

Intermediate record:

```json
{
  "record_id": "record_mitre_attack-pattern--0042a9f5-f053-4769-b3ef-9ad018dfa298_2025-10-24T17-48-19.059Z",
  "connector_source": "mitre",
  "source_class": "ontology",
  "publisher_category": "knowledge_base",
  "source_record_id": "attack-pattern--0042a9f5-f053-4769-b3ef-9ad018dfa298",
  "timestamp_basis": "source_modified"
}
```

Derived rows:

- entity mentions: technique `T1055.011` -> `technique_T1055.011`, tactics
  `defense-evasion` and `privilege-escalation`.
- relation mentions: none in this object row.
- attribution signals: none.

Schema note: the processed MITRE object file contains multiple chunks for the
same technique. The intermediate contract should create one IntermediateRecord
for the MITRE STIX object version, not one record per RAG chunk.

### 5. MITRE Relationship: Explosive uses T1016

Intermediate record:

```json
{
  "record_id": "record_mitre_relationship--00038d0e-7fc7-41c3-9055-edb4d87ea912_2025-04-28T15-31-30.051Z",
  "connector_source": "mitre",
  "source_class": "ontology",
  "source_record_id": "relationship--00038d0e-7fc7-41c3-9055-edb4d87ea912"
}
```

Derived rows:

- entity mentions: `Explosive` -> `family_S0569`, `System Network Configuration
  Discovery` -> `technique_T1016`.
- relation mentions: `family_S0569 uses technique_T1016`.
- attribution signals: none.

Schema note: this validates the `family` vocabulary choice for MITRE software
objects. If the teammate needs malware/tool distinction, preserve raw MITRE type
alongside normalized `family`.

### 6. MITRE Relationship: HomeLand Justice attributed-to HEXANE

Intermediate record:

```json
{
  "record_id": "record_mitre_relationship--0a69d74a-7662-4d18-99b4-bc1a574b35b4_2025-04-16T21-55-34.508Z",
  "connector_source": "mitre",
  "source_record_id": "relationship--0a69d74a-7662-4d18-99b4-bc1a574b35b4"
}
```

Derived rows:

- entity mentions: `HomeLand Justice` -> `campaign_C0038`, `HEXANE` ->
  `actor_G1001`.
- relation mentions: `campaign_C0038 attributed-to actor_G1001`.
- attribution signals: one `direct_attribution` for actor `HEXANE`.

Schema note: this is the cleanest example where relation mention and attribution
signal both exist. They are related but not identical: the relation is graph
structure, while the attribution signal is a labelling cue.

### 7. MITRE Relationship: DET0237 detects T1037.004

Intermediate record:

```json
{
  "record_id": "record_mitre_relationship--00b2d214-7126-4b80-866c-4321d6ace9b0_2025-10-21T15-10-28.402Z",
  "connector_source": "mitre",
  "source_record_id": "relationship--00b2d214-7126-4b80-866c-4321d6ace9b0"
}
```

Derived rows:

- entity mentions: detection strategy
  `Detection Strategy for Boot or Logon Initialization Scripts: RC Scripts` ->
  `detection-strategy_DET0237`, technique `RC Scripts` ->
  `technique_T1037.004`.
- relation mentions: `detection-strategy_DET0237 detects technique_T1037.004`.
- attribution signals: none.

Schema note: keep `detection-strategy` with the existing hyphenated spelling to
match current RAG entity ids.

### 8. pDNS: 0-02.net

Intermediate record:

```json
{
  "record_id": "record_pdns_0-02.net_2026-06-15T23-33-16.707732-00-00",
  "connector_source": "pdns",
  "source_class": "infrastructure",
  "publisher_category": "unknown",
  "source_record_id": "0-02.net",
  "timestamp_basis": "observed_range",
  "observed_first": "2014-11-17T21:45:10",
  "observed_last": "2025-12-09T21:50:55"
}
```

Derived rows:

- entity mentions: domain `0-02.net`, IPs including `23.111.191.180` and
  `75.126.23.192`, ASNs including `AS29802` and `AS36351`.
- relation mentions include:
  - `resolves-to`
  - `belongs-to`
  - `located-in`
  - `uses-nameserver`
  - `has-subdomain`
- attribution signals: one `no_attribution`.

Schema note: this exposes an important gap. The processed row stores
`entity_ids[]` and `relations[]`, but it does not preserve a direct
value-to-entity-id mapping for every raw infrastructure value. The intermediate
builder should emit EntityMention rows at extraction time, not reconstruct them
from a flat `entity_ids[]` list.

### 9. VirusTotal: 0-02.net

Intermediate record:

```json
{
  "record_id": "record_vt_0-02.net_2026-06-02T11-18-12-00-00",
  "connector_source": "vt",
  "source_class": "infrastructure",
  "publisher_category": "vendor",
  "source_record_id": "0-02.net",
  "timestamp_basis": "source_modified"
}
```

Derived rows:

- entity mentions: domain `0-02.net`, nameservers `ns1.1-17.net` and
  `ns12.1-19.net`, registrar metadata as features/metadata rather than core CTI
  entities by default.
- relation mentions:
  - `0-02.net uses-nameserver ns1.1-17.net`
  - `0-02.net resolves-to 23.111.191.180`
  - `0-02.net uses-nameserver ns12.1-19.net`
- attribution signals: one `no_attribution`.

Schema note: this overlaps with pDNS on the same domain and at least one
`resolves-to` claim. The intermediate layer should keep both source-specific
relation mentions. A later Fact/support or GNN projection can collapse them into
one relation with multiple supports.

### 10. PDF: ClickFix Section

Intermediate record candidate:

```json
{
  "record_id": "record_pdf_a59146f7ff9e5a45-2_2026-04-25T22-14-36.620663",
  "connector_source": "pdf",
  "source_class": "unlabeled_narrative",
  "source_record_id": "a59146f7ff9e5a45:2",
  "timestamp_basis": "missing"
}
```

Derived rows:

- entity mentions from current metadata only: source file
  `2026 Cyber Security Report.pdf`, section title
  `ClickFix: Social Engineering That Shifts Execution to the User`.
- relation mentions: none without a PDF entity/relation extractor.
- attribution signals: none.

Schema note: this remains deferred rather than a first-pass blocker. The
current PDF row is a processed section/chunk, not the raw PDF report. The first
schema can keep a PDF/report interface and preserve raw blobs, while deferring
whether PDF sections become extracted text units, projection rows, or
IntermediateRecords in a later pass.

## Findings

The schema handles the 10 samples well enough to proceed, but the dry run found
several contract issues.

### 1. Processed Chunks Are Not Safe Base Records

MITRE object rows and PDF rows show that `data/processed/v5_staging` is already
chunked for RAG. If those rows are used directly as IntermediateRecords, the
contract will inherit RAG chunking. The intermediate builder should operate
before chunking when possible:

- MITRE technique object: one IntermediateRecord per STIX object version, not per
  chunk.
- PDF report: one IntermediateRecord per PDF/report version, with sections/spans
  handled as extracted evidence/projection rows if needed.

### 2. Value-To-Entity-ID Mapping Must Be Preserved During Extraction

pDNS and VT demonstrate that a flat `entity_ids[]` list is not enough. The
intermediate contract needs EntityMention rows that tie each raw value to:

- `source_field`;
- `raw_value`;
- normalized value;
- `entity_type`;
- resolved `entity_id` when available.

This should be emitted while extracting, not reconstructed later from relation
endpoints.

### 3. Repeated Values Need A Clear Policy

pDNS can contain repeated IP values across observations. Two policies are
possible:

- preserve each observation as a separate mention or observation row;
- deduplicate mentions by value and add `occurrence_count` / observed range.

For the first contract, deduplicated mentions plus counts may be simpler, while
raw observations remain preserved in raw files.

### 4. OTX Indicator Type Is Missing From Processed Rows

The processed OTX rows preserve indicator values but not always the raw indicator
type. The intermediate builder should prefer raw OTX indicator objects so that
`entity_type`, canonical indicator type, and value normalization are reproducible.

### 5. Attribution Signal Separation Still Looks Useful

OTX and MITRE attributed-to examples show why `attribution_signals.jsonl` is not
just duplicate graph structure:

- OTX `adversary` can be preserved as a weak direct source cue even when no
  relation is emitted.
- MITRE `attributed-to` can create both a relation mention and a direct
  attribution signal.
- pDNS/VT can explicitly carry `no_attribution`, which is useful for labelling
  pipelines.

### 6. Cross-Source Overlap Works Better As Source-Specific Mentions First

pDNS and VT both mention `0-02.net` and overlapping DNS relations. The
intermediate contract should keep source-specific relation mentions. A projection
can later aggregate them into Facts/supports or GNN edges with support counts.

## Schema Adjustments Suggested By This Dry Run

1. Keep the current base artifact set. No new base id type is required yet.
2. Add or document `occurrence_count` for deduplicated EntityMention rows.
3. Keep `attribution_signals.jsonl` separate for now.
4. Keep PDF/report handling as an open interface for now. Preserve raw PDF
   blobs and current RAG metadata, but do not force a section/chunk base-record
   decision in schema v0.1.
5. Require the implementation to build EntityMention rows from raw/source fields,
   not from already flattened `entity_ids[]`.
