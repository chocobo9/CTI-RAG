# RESEARCH — Intermediate GNN Alignment Notes (2026-07-02)

> Intermediate category: consumer-alignment research.
>
> **Status: NON-AUTHORITATIVE RESEARCH / ALIGNMENT NOTES.** No implementation
> decisions are finalized here. References below to older OTX v2 “source of truth”
> documents are historical; current OTX authority starts at `docs/OTX_DOC_STATUS.md`.

Date: 2026-07-02

Status: audit and alignment notes. No implementation decisions are finalized in
this document unless marked as an existing code fact.

OTX projection status note, 2026-07-06: this document is background alignment
material for the OTX/Neo4j/GNN conversation. For the current scoped OTX mapper,
`docs/archive/otx/HISTORICAL_otx_downstream_projection_v2_4160_grill.md` was the design source
of truth for that historical snapshot; it is no longer current authority.
Older language here about actor mapping, ambiguity, occurrence counts, and
disagreement should be read through that newer contract: v2 preserves
multi-actor and ambiguous OTX `adversary` claims, keeps `sample_code.py` only as
a graph-shape reference, uses the latest 4,160-pulse run snapshot, and defers
disagreement calculation to a later derived projection.

## Purpose Of The Next Data Iteration

The next data iteration is to align the reusable intermediate layer with the
teammate's GNN / Neo4j consumption needs.

The current direction is not to replace or collapse the intermediate layer. The
intermediate package should remain the more general, source-backed contract that
can feed multiple consumers:

```text
raw source data
  -> reusable intermediate layer
  -> consumer-specific projections
       -> RAG chunks / doc ids / vector payloads
       -> GNN / Neo4j graph outputs
       -> later labelling or clustering exports
```

The teammate-facing output should be treated as a GNN / Neo4j-ready projection
over the intermediate data, not as the base intermediate contract itself.

Clarified boundary: the intermediate layer is an initial source-backed
preprocessing layer for downstream consumers. It should preserve raw provenance,
source fields, normalized mentions, candidate relations, timestamps, and
modelling signals, but it should not couple itself to the full downstream flow.
RAG chunking, Neo4j node/edge shaping, pDNS expansion policy, actor alias
mapping, occurrence aggregation, and graph noise filtering belong in downstream
projections or later processing stages unless a field is needed to preserve
source-backed evidence.

## Problem Categories To Resolve

The remaining work should be organized into six categories. These categories
separate terminology, contract design, projection design, implementation,
data-quality risk, and delivery ownership so the discussion does not collapse
everything into one large "make the output match sample code" task.

| Category | What it covers | Why it matters now |
| --- | --- | --- |
| A. Terminology and domain model | Align terms across source data, teammate language, sample code, and current intermediate vocabulary. Start with what each raw source actually contains and what role that source plays; then align overloaded terms such as Event, Report, Pulse, IntermediateRecord, IOC, Indicator, ASN, Actor label, Adversary, Ambiguity, Conflict, Disagreement, and Occurrence. | Several words are overloaded across OTX, TRAIL-style Neo4j output, current intermediate artifacts, and older project language. If these are not pinned down against the raw source structures first, the projection will encode accidental meanings. |
| B. Intermediate contract and data preservation | Audit whether the current intermediate layer remains general enough while preserving the fields needed by RAG and GNN/Neo4j projections. | The goal is to keep the intermediate layer reusable, not to turn it into the teammate's graph schema. Missing source-backed fields should be identified without overfitting the base contract. |
| C. Teammate GNN / Neo4j projection contract | Define the actual graph-ready output expected by the teammate: nodes, edges, ids, properties, timestamp placement, source/provenance fields, and file/Neo4j delivery format. | The teammate asked for output matching `docs/sample_code.py`, whose key contract is graph shape, not just JSON shape. This projection needs its own explicit contract. |
| D. Processing code and implementation alignment | Identify code changes needed after A-C are settled: graph projection generation, URL decomposition, enrichment joins, edge-level timestamps, occurrence aggregation, disagreement output, and tests. | Implementation should follow the aligned model. Some items belong in projection code, not in the base intermediate transformer. |
| E. Data quality, noise, and evaluation strategy | Record risks and acceptance criteria for noisy graph expansions: reverse pDNS, shared hosting, CDN IPs, large ASNs, duplicate reports, multi-actor labels, and source disagreement. | GNN-ready data can become worse if enrichment edges are treated as strong facts. Noise policy should be explicit before graph expansion is trusted. |
| F. Delivery scope and ownership boundary | Define what this data iteration will deliver, what is deferred, who owns which layer, and how completion will be demonstrated. Actor mapping belongs here as a later-stage task once the data foundation is aligned. | The project owner is responsible for data gathering and preprocessing, while downstream GNN modelling and some mapping-policy choices may be separate. The iteration needs an explicit boundary so implementation does not absorb every future modelling question. |

Actor mapping is intentionally not treated as the hardest current problem. Once
the event/IOC/source/time/disagreement foundation is aligned, actor alias mapping
can use existing approaches and datasets such as MITRE aliases, MISP galaxies,
manual overrides, and standard normalization / matching algorithms. It should be
tracked under delivery scope and staged after the base data model and graph
projection contract are clear.

Important sequencing correction for A: do not start by asking what `Event`
means. `Event` is prominent in the teammate's OTX-only sample graph, but that
does not make it the first domain-model question for multi-source data. Start by
inventorying the current raw sources and their native roles:

- OTX: pulse text, source-provided actor cues, typed indicators, references,
  contributor metadata, and pulse / indicator timestamps;
- MITRE: ATT&CK ontology objects, aliases, external ids, and source-backed
  relationships;
- pDNS: domain lookup snapshots with DNS answers, ASN / country fields, and
  observed first / last times;
- VT: domain report snapshots with DNS records, reputation / category signals,
  WHOIS / RDAP / registrar metadata, certificates, and VT timestamps.

Current A work should then analyze where the added sources overlap with or
supplement OTX semantically. The question is not whether MITRE, pDNS, and VT
must be forced into the teammate's OTX sample format. That format is relevant
for OTX because the teammate already has an OTX-only pipeline and model that
consume it. For non-OTX sources, first determine what the source natively
contains and whether it is:

- semantically overlapping with an OTX field or object type;
- a lookup / enrichment result derived from OTX indicators;
- source-only metadata;
- or a later mapping / projection concern.

OTX-only delivery can use `Event = OTX pulse`; that is a scoped projection
decision, not the multi-source starting point.

## Teammate-Requested Output

The teammate asked for data in the same output format as `docs/sample_code.py`.
That sample code is an OTX-focused collector for a TRAIL-style Neo4j graph.
This requirement should be treated as an OTX delivery requirement, not as a
hard requirement that MITRE, pDNS, and VT must all be transformed into the same
OTX sample graph shape.

Original teammate feedback, provided by the user:

```text
I want the data in the same format of the output of this [code](https://github.com/Mitraaaaa/GNN_APT/blob/main/archive/old_pipeline/collect_otx.py), this is OTX only of course we have more data and I think  a pre stage of raw data is good so we don't have to curl the data every time. But as you can see we extract Event , IP, URL, domain, ASN, actor label. In our extended version I want timestamp data to be extracted as well (last seen, first seen, duration), and the source of the data. 
note: for time info please try to extract the features I said but not all data have this info so please take a look and let me know what features are there to extract so we can decide differently.
2. The mapping: I want the mapping to be done for the actors sharing the same name but reported differently.
there are some reports that have multiple actors, in the current code they are call ambiguous and are deleted, but we want to keep them. first we do the mapping (we may also create a list of actors sharing the same names), then we keep all labels for each event.
for mapping we could use MITRE attack, MISP datasets, ...
please take a look at them and other approaches others have done for mapping and the points they take into account. (This is a basic problem and I have seen it in the beginning of many papers so that should be accessible and we can discuss over the method.
3. There is another thing we want to do and that is to calculate the number of occurrence of report in our dataset. For example for the same IOCs and report, two report in different dataset output different actor, so here we say the number of occurrence of this pulse or iocs are 2, for the label we keep two lists, one is the for the initial label for an event, another is a list we call disagreement where we keep the names that are attributed rather than what we already have and we keep the numbers, it is somewhat what I have in my mind.

An event  ---> 5 occurrence.
list ---->  [APT28]
disagreement list ----> [APT29[2 times] , X, Y ]

Some challenges:

To calculate the occurrence of a data we need to compare reports, that could be through basic word matching or and LLM which we need to decide here.
when we decide to keep ambiguous labels that can be a few labels for a report we must decide here what will be count as disagreement.
[下午 4:22]All in all I need a code from you that reads the raw data and does this list and it is ready to be entered to Neoj4 format, also I saw you raw data with different file's name each for a different purpose but I need these data for each event in the event itself, I don't want it in different files unless we have an exact mapping that each  data in the files refers to what event.
```

This source text is the direct requirement for the OTX-only downstream alignment
work. It asks for OTX/sample-code-compatible Neo4j-ready event output, plus
extracted time features, source information, actor mapping, retained
multi-actor labels, occurrence counts, and disagreement labels. It should be
used only for further OTX operations: starting from the existing intermediate
OTX material, align the downstream OTX output to the teammate format. It is not
a requirement that every non-OTX source natively become an OTX event.

OTX should therefore not consume much more A-stage discussion. The remaining
A-stage value is mainly in clarifying how MITRE, pDNS, and VT relate to OTX and
which parts belong to later mapping, occurrence, or projection stages.

The sample graph schema is:

```text
Event  -[:InReport]->  Domain
Event  -[:InReport]->  IP
Event  -[:InReport]->  URL
URL    -[:HostedOn]->   Domain
URL    -[:ResolvesTo]-> IP
Domain -[:ResolvesTo]-> IP
IP     -[:InGroup]->    ASN
```

The sample code also writes event-level actor / label features:

- `apt`
- `pulse_created`
- `pulse_modified`
- `label_confidence`
- `belief_named_actor`
- `belief_nation_state`
- `uncertainty`
- `tag_exclusivity`
- `evidence_weight`
- `nation_coherence`
- `activity_cluster`
- `nation`
- `source = "otx"`

The teammate also requested extensions beyond the sample code:

- preserve multi-actor reports instead of dropping ambiguous labels;
- map actor names / aliases later, using sources such as MITRE ATT&CK, MISP, and
  possibly literature-backed approaches;
- extract timestamp features such as first seen, last seen, and duration where
  available;
- preserve data source information;
- calculate occurrence counts for repeated or overlapping reports / IOC sets;
- preserve initial labels and disagreement labels with counts.

## Current Code Facts

### Base Unit

The current intermediate layer does not materialize an `Event` artifact.

The current base unit is `IntermediateRecord`: one raw source record version.
For example:

- OTX: one pulse raw snapshot becomes one intermediate record;
- MITRE: one STIX object or relationship becomes one intermediate record;
- pDNS / VT: one infrastructure raw snapshot or payload becomes one intermediate
  record.

The existing contract draft explicitly says not to make Report/Event the base
artifact in v0.1. Report/Event grouping is deferred to a projection or grouping
layer.

### Multi-Actor / Ambiguity

The current intermediate code does not implement the sample code's
`ambiguous_labels` skip policy.

However, it also does not currently implement full multi-actor conflict or
disagreement modelling.

Current OTX behavior:

- reads `raw["adversary"]` as the actor-like source field;
- emits one actor `EntityMention` when that field is present;
- emits one `weak_direct_attribution` signal for that actor;
- does not parse actor aliases from tags or description;
- does not emit `conflicting_attribution`;
- does not compute a disagreement list.

The intermediate contract contains vocabulary for ambiguity and conflicting
attribution, but the current source transformers do not yet produce
teammate-style actor disagreement rows.

### Timestamps

The current intermediate layer preserves record-level timestamp candidates:

- `published_at`
- `modified_at`
- `observed_first`
- `observed_last`
- `fetched_at`
- `timestamp_basis`

Source-specific behavior:

- OTX maps `created` to `published_at` and `modified` to `modified_at`.
- MITRE maps STIX `created` to `published_at` and `modified` to `modified_at`.
- pDNS aggregates per-answer `first` / `last` into record-level
  `observed_first` / `observed_last`.
- VT maps `last_modification_date` to `modified_at`; other VT dates are
  preserved as metadata / features rather than graph time edges.

The current layer does not yet emit sample-code-style edge-level temporal
properties:

- `Event -[:InReport]-> IOC.indicator_created`
- `Domain -[:ResolvesTo]-> IP.first_seen`
- `Domain -[:ResolvesTo]-> IP.last_seen`
- duration derived from first / last seen

The pDNS transformer notes that relation-level temporal qualifiers are deferred.

## What Is Missing Or Partially Implemented

Missing relative to the sample code:

- Neo4j-ready `Event`, `Domain`, `IP`, `URL`, and `ASN` node outputs.
- `Event -[:InReport]-> Domain/IP/URL` projection.
- URL host decomposition into `HostedOn` or URL-to-IP `ResolvesTo`.
- Event-local enrichment graph connecting OTX pulse IOCs to pDNS / ASN results.
- Reverse pDNS enrichment from IP to historical domains.
- Uniform ASN lookup and `IP -[:InGroup]-> ASN` projection.
- Edge-level timestamp properties and duration.
- TRAIL-style DST confidence fields.
- Title near-duplicate handling as occurrence rather than skip.
- Actor alias mapping pipeline.
- Multi-actor conflict / disagreement output.
- Occurrence counting across repeated reports, overlapping IOCs, or related
  source records.

Partially implemented:

- raw preservation and raw hash validation;
- OTX pulse-level source and timestamp fields;
- OTX actor-like attribution cue as `weak_direct_attribution`;
- OTX indicator mentions, including indicator type preservation;
- pDNS / VT infrastructure relations such as `resolves-to`;
- pDNS ASN when already present in the pDNS raw data;
- record-level observed first / last for pDNS;
- source metadata and processing reports.

Implemented beyond the sample code:

- multi-source intermediate scope: OTX, MITRE, pDNS, and VT;
- MITRE ontology and relationship preservation;
- source manifests and validation harness;
- controlled vocabularies;
- raw reference and SHA-256 integrity checks;
- RAG and GNN smoke projections;
- separation of base intermediate data from consumer-specific projections.

## Output Method Implied By The Sample Code

The sample code builds the graph through these steps:

1. Search OTX by APT name and MITRE aliases.
2. Fetch full OTX pulse details.
3. Filter out ambiguous labels, using MITRE alias mapping over tags.
4. Skip near-duplicate titles with high Jaccard similarity.
5. Create one `Event` node per accepted OTX pulse.
6. Write primary IOC nodes from pulse indicators:
   - Domain
   - IP
   - URL
7. Create `Event -[:InReport]-> IOC` edges.
8. Decompose URL host:
   - URL host domain creates `URL -[:HostedOn]-> Domain`;
   - URL host IP creates `URL -[:ResolvesTo]-> IP`.
9. Enrich primary IPs with ASN and reverse pDNS.
10. Enrich primary domains with forward pDNS.
11. Write `Domain -[:ResolvesTo]-> IP` and `IP -[:InGroup]-> ASN`.

For the project, the likely production equivalent is not to rerun this collector
as-is, but to derive the same graph semantics from the preserved raw and
intermediate artifacts, then decide which enrichment calls are raw-backed and
which require new fetching.

## Data Gaps To Align

These gaps need explicit agreement before implementation. They should be
addressed after the source-level inventory above, not by forcing every source
into the sample-code graph vocabulary first:

1. How should non-OTX sources participate?
   - MITRE as alias / ontology only;
   - MITRE relationships as graph facts;
   - pDNS / VT / WHOIS as enrichment-only sources;
   - PDF reports as narrative events.

2. What exactly counts as an `Event` in the teammate output?
   - one OTX pulse;
   - one narrative source record;
   - one clustered event across multiple reports;
   - something else.

3. What is the first acceptable Neo4j-ready format?
   - direct Neo4j writes;
   - node / edge JSONL tables;
   - Cypher import CSV;
   - another graph interchange format.

4. How should ambiguous or multi-actor labels be represented?
   - multiple equal labels;
   - primary label plus disagreement labels;
   - all labels as attribution evidence;
   - unresolved labels awaiting mapping.

5. What makes a label a disagreement?
   - different raw actor strings;
   - different canonical actor ids after mapping;
   - conflicting labels on the same report;
   - conflicting labels across an event cluster.

6. What counts as occurrence?
   - duplicate title / report;
   - same pulse id across datasets;
   - overlapping IOC set;
   - shared infrastructure neighborhood;
   - source count supporting a logical event.

7. Which timestamp should be used for temporal features and splits?
   - pulse/report creation;
   - source modification;
   - indicator creation;
   - DNS first / last seen;
   - fetched time as fallback only.

8. Which enrichments are required for the next iteration?
   - use only already-collected pDNS / VT / WHOIS data;
   - add reverse pDNS queries;
   - add ASN lookups for all IPs;
   - add Whoxy live or history lookups.

## Additional Things To Record

Besides the required items above, the next discussion should also record:

- a glossary of source-specific meanings for terms like Event, Report, Pulse,
  Indicator, IOC, Occurrence, Attribution, Ambiguity, and Disagreement;
- the identity grain for every graph node and edge id;
- provenance requirements for every projected node and edge;
- which sample-code filters should be preserved, removed, or converted into
  features;
- which fields are source-backed, derived deterministically, inferred by join,
  or model-assisted;
- which outputs are stable contract artifacts versus disposable projections;
- acceptance checks for the teammate-facing graph output;
- known noise risks, especially shared hosting, CDN IPs, large ASNs, and reverse
  pDNS over-expansion.

## Working Terminology Crosswalk

This table is intentionally a working crosswalk, not a finalized glossary. It
maps source/sample-code terms to current intermediate terms and highlights where
the teammate-facing vocabulary still needs alignment.

| Concept / Term | Teammate / sample-code meaning | Current intermediate meaning | Current status | Gap / alignment question |
| --- | --- | --- | --- | --- |
| Event | In `sample_code.py`, one accepted OTX pulse becomes `(:Event {id: pulse["id"]})`. The Event is the central node for IOC edges and actor-label features. | No base `Event` artifact. The closest object is an OTX `IntermediateRecord`, which represents one raw pulse snapshot/version. | Partially representable: OTX records preserve pulse id, name, source, timestamps, indicators, and actor cue. | Decide whether teammate `Event` should mean one OTX pulse, one narrative source record, or a later cluster across reports/sources. |
| Report / Pulse | Sample code treats OTX pulse as the event/report-like source object. It searches, fetches, filters, and writes accepted pulses. | OTX pulse is a raw source record. It becomes one `IntermediateRecord`; raw payload is preserved under `raw_ref`. | Implemented as source record, not graph node. | Decide whether graph `Event` should keep `pulse_id` identity or get a projection id derived from `record_id`. |
| InReport | `Event -[:InReport]-> Domain/IP/URL`; edge carries `indicator_created`. | OTX indicators are `EntityMention` rows with entity_type `indicator` and typed `value_type`; no `InReport` edge. | Partially implemented as mentions, not as Neo4j edges. | Need projection rule from OTX indicator mentions to `Event -[:InReport]-> IOC` edges. |
| Domain | Neo4j node `(:Domain {value})`; appears as primary IOC, URL host, pDNS historical domain, or VT/pDNS domain. | Can appear as an `EntityMention` with entity_type `domain`, or as an indicator mention with canonical type `domain`. | Partially implemented. | Need node identity rule: should all source domains merge by normalized domain value in graph projection? |
| IP | Neo4j node `(:IP {value})`; appears as primary IOC, URL host IP, DNS answer, or reverse pDNS enrichment target. | Can appear as an `EntityMention` with entity_type `ip`, or as an indicator mention with canonical type IP if source type maps correctly. | Partially implemented. | Need projection rule from indicator types and infra mentions into `IP` nodes. |
| URL | Neo4j node `(:URL {value})`; sample code decomposes host into Domain or IP. | OTX URL/URI is preserved as an indicator mention if canonicalized by indicator typing. No URL host decomposition in intermediate. | Partially implemented. | Need deterministic URL parsing projection and edge rules. |
| ASN | Neo4j node `(:ASN {number})`; sample code enriches every IP via OTX IP general lookup and writes `IP -[:InGroup]-> ASN`. | pDNS can produce ASN mentions and `belongs-to` relations when ASN is already present in pDNS raw. VT does not add ASN. | Partially implemented only when source raw contains ASN. | Need decide whether to add graph edge name `InGroup`, whether ASN lookup is required, and whether pDNS-derived ASN is sufficient for v1. |
| ResolvesTo | Sample code has `Domain -[:ResolvesTo]-> IP` and `URL -[:ResolvesTo]-> IP`; DNS edge has `first_seen` / `last_seen`. | Infra relation predicate is `resolves-to`; pDNS/VT relation rows do not currently carry edge-level first/last seen. | Partially implemented at relation level. | Need edge-level temporal qualifiers and mapping from `resolves-to` to Neo4j `ResolvesTo`. |
| HostedOn | Sample code creates `URL -[:HostedOn]-> Domain` from URL hostname. | Not represented in current intermediate relation vocabulary. | Missing. | Need decide whether `HostedOn` is projection-only, or whether a base relation vocabulary value is required. |
| InGroup | Sample code creates `IP -[:InGroup]-> ASN`. | Current infra predicate is `belongs-to` for IP-to-ASN. | Semantically close, output name differs. | Decide whether projection maps `belongs-to` to `InGroup`, or keeps project predicate names. |
| Actor label / apt | Sample code writes Event property `apt`, after filtering candidate pulses by target APT and MITRE alias tags. | OTX `adversary` becomes an actor `EntityMention` and a `weak_direct_attribution` signal. MITRE `attributed-to` becomes `direct_attribution`. | Partially implemented. | Need decide how graph output represents actor labels: Event property, Actor node, attribution edge, signal table, or combination. |
| Adversary | In OTX raw/sample context, actor-like attribution cue. Sample code does not use raw `adversary` as the main filter; it relies heavily on tags and target APT search. | Current OTX transformer uses `raw["adversary"]` as the actor cue and emits `weak_direct_attribution`. | Implemented for raw adversary only. | Need decide whether tags and description should also generate actor-label candidates. |
| Ambiguous labels | Sample code drops pulses whose tags map to more than one target APT: reason `ambiguous_labels`. | Current intermediate does not run this filter. It also does not emit a multi-actor conflict/disagreement structure. `ambiguity` mainly describes mention/relation resolution state. | Not dropped, but not explicitly modelled as disagreement. | Need distinguish `ambiguity` from `conflict/disagreement`: multi-label evidence should likely be preserved separately. |
| Conflict / disagreement | Teammate wants competing actor labels preserved with counts. | Vocabulary contains `conflicting_attribution`, and record features include placeholder `conflicting_sources_count`, but transformers do not emit them. | Missing. | Need define when labels conflict: same report, same event cluster, same IOC set, or same canonical actor after mapping. |
| Occurrence | Teammate wants count of repeated/overlapping report or IOC occurrences. Sample code currently skips near-duplicate titles instead of counting them. | Entity mentions have `occurrence_count` within one record/value, but no cross-record event occurrence count. | Different meaning already exists. | Need define occurrence grain separately from mention occurrence count. |
| Source | Sample code sets Event `source = "otx"`. | Intermediate has `connector_source`, `source_class`, `publisher_category`, `source_name`, and raw refs. | Implemented more richly. | Graph projection must decide which source fields to expose on Event/nodes/edges. |
| Raw/pre-stage | Teammate accepts pre-stage raw data to avoid repeated API calls. | Raw payloads are preserved with package-relative `raw_ref.raw_path` and full `raw_sha256`. | Implemented. | Need decide whether teammate output needs raw refs on every node/edge or only source/evidence links. |

## Timestamp Crosswalk

The timestamp gap is not just missing fields; it is a grain mismatch. Current
intermediate timestamps are mostly record-level. The sample code also uses
edge-level timestamps.

| Timestamp concept | Teammate request | Sample-code handling | Current intermediate handling | Gap / next alignment |
| --- | --- | --- | --- | --- |
| Event creation / report date | Wants timestamp data and source of data; likely expects report or event time. | Event property `pulse_created = pulse.get("created", "")`. | OTX `created` becomes `timestamps.published_at`; MITRE `created` also becomes `published_at`. | Naming differs: sample says `pulse_created`; intermediate says `published_at`. Need projection mapping. |
| Event modified time | Wants available time features, not necessarily all data has them. | Event property `pulse_modified = pulse.get("modified", "")`. | OTX/MITRE `modified` becomes `timestamps.modified_at`; VT `last_modification_date` becomes `modified_at`. | Mostly available, but source semantics differ by connector. Need expose `timestamp_basis`. |
| Indicator created time | Useful to know when an IOC was first listed in a pulse/report. | `Event -[:InReport]-> IOC` edge property `indicator_created`; preserves earliest value on repeated edge. | OTX indicator `created` is not currently emitted into entity mentions or relations. Raw still contains it if present. | Missing in intermediate artifact rows; can be recovered from raw or added to projection extraction. |
| DNS first seen | Teammate specifically asks for first seen. | `Domain -[:ResolvesTo]-> IP` edge property `first_seen`, from pDNS enrichment records. | pDNS aggregates all answer first times into record-level `observed_first`; per-answer first_seen remains in raw/projected structured data but not relation rows. | Need edge-level first_seen on graph `ResolvesTo`. |
| DNS last seen | Teammate specifically asks for last seen. | `Domain -[:ResolvesTo]-> IP` edge property `last_seen`. | pDNS aggregates all answer last times into record-level `observed_last`; relation-level last_seen deferred. | Need edge-level last_seen on graph `ResolvesTo`. |
| Duration | Teammate explicitly asks for duration. | Not explicitly computed in sample code, but derivable from `first_seen` and `last_seen`. | Not computed. `age_days_at_collection` is currently `null`. | Need define where duration lives: DNS edge, Event, Event-IOC edge, or feature table. |
| Fetched / collected time | Needed for provenance and weak fallback. | Sample code uses checkpoint time internally but does not expose fetched_at on Event. | `raw_ref.fetched_at` and `timestamps.fetched_at` are preserved. | Intermediate is stronger here; graph projection should decide whether to expose it. |
| Timestamp quality / basis | Teammate asks to inspect what features exist because not all data has time info. | Sample code does not expose a timestamp quality field. | `timestamp_basis` records whether time is `source_modified`, `observed_range`, `fetched_only`, etc. | Intermediate is stronger here; should likely be included in graph/export metadata. |
| Temporal split field | Not directly requested in sample code, but relevant for model evaluation. | Not present. | Explicitly deferred; intermediate preserves candidates but does not assign split. | Need later split policy after graph/event grain is settled. |

## A-Stage Source-Level Raw Inventory

This section continues A. It inventories the current raw source roles before
forcing any source into the teammate's OTX-only sample graph shape.

Scope note from local raw inspection and user correction: `data/raw/otx`
currently has both 2,056 legacy root pulse JSON files and 6k+ newly added OTX
records under the versioned RawStore layout. These belong to the same OTX
corpus for this alignment work and should be considered together as the 8k+
OTX population. VT currently has 2,054 domain snapshot JSON files. pDNS
currently has 693 lookup snapshot JSON files.

### OTX

Raw object grain:

- One OTX pulse is the logical raw object for A.
- One pulse contains narrative text, contributor metadata, source-provided
  actor-like and campaign/malware/TTP cues, references, tags, and typed
  indicators.
- In the OTX-only teammate projection, one accepted OTX pulse can become one
  `Event`; that is a projection decision, not the base multi-source unit.

Main raw field groups:

- Pulse identity and text: `id`, `name`, `description`.
- Source-provided attribution-like fields: `adversary`, `malware_families`,
  `attack_ids`, `targeted_countries`, `industries`, `tags`.
- Indicators: `indicators[]` with `id`, `indicator`, `type`, `created`,
  `content`, `title`, `description`, `expiration`, `is_active`.
- References: `references[]`.
- Contributor and publication metadata: `author`, `author_name`, `public`,
  `TLP`, `revision`, `groups`, `in_group`, `is_subscribing`.
- Pulse timestamps: `created`, `modified`.

Native data types:

- Weakly-labelled narrative pulse.
- Typed IOC container: domains, hostnames, URLs, IPv4/IPv6, file hashes, CVEs,
  email, YARA, mutex, and other OTX indicator types.
- Source-provided TTP references via `attack_ids`.
- Source-provided malware/family, target geography, industry, tag, and
  reference metadata.

Key timestamp fields:

- `created`: pulse/report creation candidate.
- `modified`: pulse update candidate.
- `indicators[].created`: indicator-in-pulse timestamp; important for
  `Event -[:InReport]-> IOC.indicator_created`.
- `fetched_at`: collection/storage timestamp when using RawStore or delivery
  metadata.

Provenance/source metadata:

- `author` / `author_name` are source contributor metadata.
- `TLP`, `public`, `revision`, `references`, and collection `fetched_at` are
  provenance or handling context.
- `id` is the OTX pulse id and is the natural OTX-only projection id candidate.

Current fields not to misread:

- `author_name` is not an actor label. It is the pulse contributor.
- `adversary` is an actor-like source cue, but it is weak and not verified
  ground truth by itself.
- `attack_ids` overlap MITRE technique ids semantically, but they are OTX
  source fields that need validation/mapping against MITRE before ontology use.
- `tags` may contain actor aliases, malware names, sectors, techniques,
  marketing/noise, or generic descriptors; tags are not a typed actor-label
  field.
- `indicators[]` are reported IOCs in a pulse, not proof that every IOC belongs
  uniquely to the actor named in the same pulse.

### MITRE ATT&CK

Raw object grain:

- Physical raw storage is an ATT&CK STIX bundle.
- Logical raw objects are STIX domain objects and STIX relationships inside the
  bundle: `attack-pattern`, `intrusion-set`, `malware`, `tool`, `campaign`,
  `course-of-action`, `x-mitre-tactic`, `x-mitre-detection-strategy`,
  `x-mitre-analytic`, data source/component objects, and `relationship`.
- Current intermediate treatment of one STIX object or relationship as one
  source-level record is aligned with this logical grain.

Main raw field groups:

- Object identity and definition: `type`, `id`, `name`, `description`.
- Versioning and lifecycle: `created`, `modified`, `x_mitre_version`,
  `x_mitre_attack_spec_version`, `x_mitre_deprecated`, `revoked`.
- Ontology identifiers and references: `external_references`, including ATT&CK
  external ids such as T/G/S/M/TA/DET-style ids where present.
- Alias fields: `aliases` on intrusion sets/campaigns, `x_mitre_aliases` on
  malware/tools.
- Technique/tactic structure: `kill_chain_phases`,
  `x_mitre_is_subtechnique`, tactic refs, data sources/components.
- Relationship rows: `relationship_type`, `source_ref`, `target_ref`,
  relationship `description`, `external_references`.

Native data types:

- Ontology definitions for actors/groups, techniques, software, campaigns,
  mitigations, detection strategies, tactics, and data sources/components.
- Source-backed ATT&CK relationship assertions such as `uses`,
  `attributed-to`, `mitigates`, and `detects`.
- Alias lists and external ids useful for later mapping.

Key timestamp fields:

- STIX `created` and `modified` on objects and relationships.
- Campaign objects can also carry `first_seen` and `last_seen` with citation
  fields.
- ATT&CK version fields describe ontology-definition versioning, not event
  observation time.

Provenance/source metadata:

- `created_by_ref`, `object_marking_refs`, `external_references`,
  `x_mitre_contributors`, ATT&CK spec/version fields, deprecated/revoked flags.
- MITRE as connector source has publisher category `knowledge_base` and source
  class `ontology`.

Current fields not to misread:

- MITRE is not an enrichment lookup derived from OTX. It is an independent
  ontology/knowledge-base source.
- MITRE aliases do not solve actor alias mapping automatically; they provide
  source-backed candidate aliases for a later mapping layer.
- MITRE `uses`, `mitigates`, and `detects` are source-backed relations, but not
  actor labels.
- MITRE `attributed-to` is a direct attribution assertion in ATT&CK's ontology,
  but it is still a source assertion, not final ground truth.
- ATT&CK external ids are ontology ids; they are not the same thing as OTX pulse
  ids, raw document ids, or graph projection ids.

Source-level MITRE object classification:

- `attack-pattern`: ATT&CK technique / sub-technique definition. OTX
  `attack_ids` can be mapped or validated against these ids. This does not make
  the OTX pulse itself MITRE evidence.
- `intrusion-set`: MITRE threat actor / group ontology object with aliases.
  Useful for later OTX actor label canonicalization, but actor mapping is not
  completed in A.
- `malware` / `tool`: ATT&CK software/family/tool definitions with aliases.
  Useful for later OTX `malware_families` normalization; not actor labels.
- `campaign`: MITRE campaign object, potentially with aliases and first/last
  seen fields. Campaign grain is not the same as an OTX pulse or projected
  event.
- `relationship`: independent ATT&CK source-backed relationship assertion,
  such as `uses`, `attributed-to`, `mitigates`, or `detects`. These
  relationships are not OTX-derived enrichment. They may later be projected as
  ontology/supporting graph material with MITRE provenance.

MITRE A-stage decision:

- MITRE should provide multiple source-backed values: technique-id validation
  for OTX, actor/software/campaign alias support for later mapping, and
  independent ATT&CK ontology objects and relationships for later projections.
- Alias mapping and final graph projection are later stages, not A-stage
  deliverables.

### Passive DNS

Raw object grain:

- One pDNS raw object is one domain lookup snapshot.
- The local pDNS collection is derived from OTX domain / URL-host indicators,
  not a complete passive-DNS feed.
- The payload shape is `count` plus `passive_dns[]` answer rows.

Main raw field groups:

- Lookup/storage wrapper: `source`, `source_id`, `fetched_at`, `payload`.
- Lookup result summary: `count`.
- Answer rows: `hostname`, `address`, `record_type`, `asset_type`, `first`,
  `last`, `asn`, `flag_title`, `flag_url`, `indicator_link`.

Native data types:

- Infrastructure observations for DNS records keyed by a lookup domain.
- DNS answer rows covering record types such as A, NS, SOA and possibly other
  provider-returned record types.
- ASN and country-like metadata when present on answer rows.
- Observed first/last timestamps for answer rows.

Key timestamp fields:

- `passive_dns[].first`: first observed time for that DNS answer row.
- `passive_dns[].last`: last observed time for that DNS answer row.
- `fetched_at`: when the project collected the lookup snapshot.

Provenance/source metadata:

- `source_id` is the lookup key used by the project.
- `indicator_link` points to the provider-side indicator path.
- `flag_title` / `flag_url` are provider country display metadata, not victim
  or targeting fields.
- `asn` is provider-returned infrastructure metadata, sometimes null.

Current fields not to misread:

- pDNS provides no actor attribution. Any attribution attached to pDNS must be
  inherited later through a join to an already-labelled OTX pulse or other
  labelled record.
- Current local pDNS raw is domain-keyed forward pDNS. The teammate sample's
  reverse pDNS pattern is IP-keyed lookup and is not automatically covered by
  the existing 693 domain lookup snapshots.
- `hostname -> address` should not always be projected as domain-to-IP
  `resolves-to`; record type matters. A records are different from NS/SOA rows.
- `asn` text is not a canonical ASN entity id until normalized.
- A pDNS lookup snapshot can be empty; an empty result is still a collected raw
  observation.
- pDNS edges are infrastructure facts with time qualifiers, not report/event
  facts.

Reverse pDNS status:

- The sample code's reverse pDNS step is relevant as a design reference, but it
  is not part of the current A-stage source role decision.
- Current pDNS remains domain-keyed forward pDNS collected from OTX domain /
  URL-host indicators.
- IP-keyed reverse pDNS is deferred pending teammate discussion. If adopted
  later, it should be treated as a separate enrichment expansion with its own
  raw lookup population, provenance, lookup direction, primary/secondary IOC
  distinction, and noise policy.

### VirusTotal

Raw object grain:

- One VT raw object is one domain report snapshot keyed by a domain.
- Current VT collection is derived from OTX domain / URL-host indicators, not a
  complete VirusTotal corpus.
- The payload shape is `data`, where `data.type = "domain"` and `data.id` is
  the domain.

Main raw field groups:

- Lookup/storage wrapper: `source`, `source_id`, `fetched_at`, `payload`.
- VT object identity: `data.id`, `data.type`, `data.links`.
- Reputation/scanner signals: `last_analysis_results`,
  `last_analysis_stats`, `reputation`, `total_votes`, `tags`, `categories`.
- DNS and infrastructure fields: `last_dns_records`,
  `last_dns_records_date`, `tld`, nameserver/A/TXT/SOA records when present.
- Registration / ownership-like fields: `creation_date`, `expiration_date`,
  `last_update_date`, `registrar`, `whois`, `whois_date`, `rdap`. Current raw
  inspection shows `whois` is usually VT-provided WHOIS text, not only a hash,
  but it remains embedded VT metadata for A-stage purposes.
- Certificate / service metadata: `last_https_certificate`,
  `last_https_certificate_date`, `jarm`.
- Popularity/context fields: `popularity_ranks`, `crowdsourced_context`.

Native data types:

- Domain reputation and vendor-analysis snapshot.
- Domain DNS records as seen by VT at/near the snapshot.
- Registration/RDAP/WHOIS-like metadata embedded in the VT domain report.
- Certificate/JARM metadata where VT has it.

Key timestamp fields:

- `last_modification_date`: VT domain object modification time.
- `last_analysis_date`: analysis timestamp.
- `last_dns_records_date`: timestamp for last DNS records.
- `creation_date`, `expiration_date`, `last_update_date`: domain registration
  lifecycle timestamps when present.
- `whois_date`: timestamp for WHOIS data in the VT report.
- `last_https_certificate_date`: certificate observation/update timestamp.
- `fetched_at`: project collection timestamp.

Timestamp interpretation:

- VT timestamps have limited connection to OTX pulse time or pDNS observed
  first/last time. Treat them as VT source metadata / freshness and lifecycle
  candidates, not as attack, event, campaign, or cross-source temporal anchors
  unless a later projection explicitly chooses one with provenance.

Provenance/source metadata:

- `source_id` / `data.id` is the domain lookup key.
- `data.links` links to VT-side object context.
- Vendor names inside `last_analysis_results`, category providers inside
  `categories`, and vote/stat fields are VT-provided metadata.

Current fields not to misread:

- VT provides no actor attribution for these domain snapshots.
- `last_analysis_stats`, `reputation`, `categories`, `tags`, and votes are
  reputation/context signals, not campaign or actor labels.
- VT `whois` / `rdap` fields are embedded VT report attributes. They are not a
  separate WHOIS source population in the current A scope, and should not be
  promoted to graph relations without a later parsing/mapping decision.
- `last_modification_date` is a VT object timestamp, not a pulse/report/event
  time.
- `last_dns_records` is not the same as pDNS observed history; it should not be
  treated as a passive-DNS time range unless VT supplies the needed observation
  semantics.

## A-Stage Relationship To OTX

| Source | Semantic overlap with OTX | OTX-derived enrichment | Source-only metadata | Later mapping / projection concern |
| --- | --- | --- | --- | --- |
| OTX | Native center for this iteration: pulse text, actor-like cue, malware/family names, ATT&CK-like `attack_ids`, typed indicators, tags, references, pulse and indicator timestamps. | Not applicable; OTX is the seed source for current pDNS/VT enrichment. | Contributor (`author`, `author_name`), TLP/public/revision/groups, source references, raw ids, fetched time. | OTX-only projection may map pulse to `Event`; actor-label disagreement, occurrence, URL decomposition, `InReport` edges, indicator-created edge timestamps, and sample-code filter policy are projection/later alignment tasks. |
| MITRE | Strong overlap with OTX `attack_ids` and partial overlap with OTX `adversary` / `malware_families` through ATT&CK group/software aliases. | Not OTX-derived. MITRE is independent ontology and relationship source. | ATT&CK version/spec metadata, deprecated/revoked flags, contributors, external references, object markings, data source/component definitions. | Decision: use MITRE's multiple values when source-backed. Near-term it can validate OTX `attack_ids` and support later alias mapping; later projections may also export ATT&CK ontology objects and relationships. |
| pDNS | Overlaps OTX domain/hostname/URL-host indicators and produces domain/IP/ASN infrastructure facts that can attach to OTX IOCs. | Current pDNS is an OTX-derived lookup population: OTX determines the domain/URL-host lookup keys, while pDNS returns source-backed enrichment facts. Reverse pDNS is deferred and not part of the current path. | Provider `indicator_link`, country flag display fields, raw lookup key, fetched time, empty lookup observations. | Record-type-aware treatment (`A` rows as DNS resolution evidence; NS/SOA handled separately or deferred), edge-level first/last timestamps, ASN normalization, graph edge strength/noise policy, inherited attribution policy. |
| VT | Overlaps OTX domain/URL-host indicators and supplements them with reputation, DNS, registrar/RDAP/WHOIS-like, certificate, and analysis metadata. | Current VT is an OTX-derived lookup population: OTX determines the domain/URL-host lookup keys, while VT returns source-backed enrichment facts. | VT scanner/vendor results, categories, votes, popularity ranks, registrar, embedded WHOIS/RDAP, certificate/JARM fields, VT links, fetched time. | Preserve VT DNS/reputation/registration/certificate facts with VT provenance; avoid treating VT reputation as actor label; inherited attribution policy remains downstream. |

## A-Stage Source-Level Judgments

OTX:

- Native role: weakly-labelled narrative plus typed IOC bundle.
- Relationship to OTX: it is the seed narrative/IOC source for the current
  teammate-aligned OTX-only projection and for pDNS/VT lookup selection.
- Must not be mistaken for: final ground-truth attribution, canonical actor
  ontology, or a fully normalized graph schema.

MITRE:

- Native role: ATT&CK ontology, aliases, external ids, versioned definitions,
  and source-backed ATT&CK relationships.
- Relationship to OTX: independent reference/ontology source that overlaps OTX
  `attack_ids` strongly and OTX actor/software names partially.
- Decision: MITRE should be allowed to provide multiple source-backed values:
  technique-id validation for OTX, alias support for later mapping, and
  independent ATT&CK ontology/relationship material for later projections.
- Must not be mistaken for: OTX-derived enrichment, a replacement for OTX
  pulse evidence, or a complete actor alias mapping solution.

pDNS:

- Native role: infrastructure lookup snapshots with DNS answer rows and
  observed first/last times.
- Relationship to OTX: OTX-derived enrichment keyed by OTX domain / URL-host
  indicators. More precisely: OTX defines the lookup population; pDNS returns
  source-backed enrichment facts.
- Decision: do not include reverse pDNS in the current path. Treat it as a
  deferred candidate method pending teammate discussion.
- Must not be mistaken for: actor attribution, narrative report content, or
  one uniform `Domain -[:ResolvesTo]-> IP` relation without checking
  `record_type`.

VT:

- Native role: domain report snapshots with reputation/scanner results, DNS
  records, registration/RDAP/WHOIS-like metadata, certificates, and VT
  timestamps.
- Relationship to OTX: OTX-derived enrichment keyed by OTX domain / URL-host
  indicators. More precisely: OTX defines the lookup population; VT returns
  source-backed enrichment facts.
- Must not be mistaken for: actor attribution, passive-DNS history, standalone
  WHOIS source coverage, or final graph projection schema.

## A-Stage Deferred Discussion

These are not implementation tasks yet.

1. Reverse pDNS is not in the current path. It remains a candidate method to
   discuss with teammates before any collection or projection decision.
