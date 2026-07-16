# REFERENCE — Teammate Output Data Representation

> Intermediate category: external consumer reference.
>
> **Status: EXTERNAL/TEAMMATE REFERENCE, NOT A PROJECT CONTRACT.** Use it as consumer
> input when revising the adjustable Intermediate draft; do not treat it as current
> Runtime, RAG, or storage authority.

> **Current boundary:** collection is represented by a current snapshot. This
> document specifies the post-collection transformation of the APT
> reverse-enrichment snapshot. The current source scope and counts are
> maintained in `docs/snapshot_postprocessing_baseline.md`.

## **Stage 1: Data Collection and Graph-Ready Preparation**

The goal of Stage 1 is to build a reusable CTI dataset before Neo4j graph construction and model training. Instead of directly writing collected data into Neo4j, raw CTI records are first preserved in JSON format. Then entities, relationships, aliases, metadata, and features are extracted in a separate processing step. This makes the dataset reusable and allows the graph schema to be revised without recollecting the original data.

### **1\. Source Selection**

The current snapshot source set should be described by role rather than by a new
collection plan. Sources should be separated into:

* **APT/taxonomy references:** MITRE ATT\&CK and Malpedia.
* **Attribution-aware/event sources:** actor-evidenced OTX Events and CIRCL MISP OSINT Events.
* **Enrichment-only sources:** passive DNS, ASN, WHOIS, GeoIP, URL parsing, and domain/IP metadata sources when a later enrichment task explicitly enables them.

For each source, the pipeline should record whether it provides labels, enrichment, timestamps, actor aliases, campaign names, malware names, tools, techniques, or only indicators.

### **2\. Temporal Scope and Data Split**

The dataset must define a clear temporal window. Publication timestamps, modification timestamps, indicator timestamps, and report timestamps should be standardized. A temporal train/test split should be defined to avoid leakage, for example by training on older reports and testing on newer reports.

Records without reliable timestamps should be marked rather than silently discarded.

### **3\. Raw Data Collection**

All selected CTI data should first be stored as raw or near-raw JSON. At this stage, the pipeline should not remove ambiguous records, should not perform graph construction, and should not decide final training labels.

For the current OTX snapshot, the post-processing layer must consume and reference:

* raw search responses;  
* raw pulse detail responses;  
* raw indicator responses;  
* query aliases and discovery paths that discovered each pulse;
* source metadata;  
* publication and collection timestamps;  
* source-claim status, multi-actor labels, ambiguity metadata and deferred-query status;
* duplicate discovery metadata.

The goal is to preserve evidence first and decide later which records are used for training, analysis, enrichment, or graph construction. No new
network collection is part of this stage.

### **4\. Unified Intermediate JSON Schema**

After raw collection, records should be converted into a common intermediate JSON schema. This schema should preserve the original raw object while adding normalized metadata.

Each intermediate record should include:

* record ID;  
* source name and source type;  
* raw object reference;  
* publication and modification timestamps;  
* matched actors and aliases;  
* tags;  
* references;  
* indicators;  
* attribution label availability;  
* ambiguity flag;  
* extracted entities;  
* candidate relationships;  
* processing status.

This intermediate format should be ready for later conversion into Neo4j, but
Neo4j projection must not be the place where source claims are collapsed.

### **5\. Entity Resolution and Alias Mapping**

Because CTI sources use different names for the same actors, malware, campaigns, and tools, alias resolution is required.

The pipeline should build mappings for:

* actor aliases;  
* campaign aliases;  
* malware aliases;  
* tool aliases;  
* ATT\&CK techniques;  
* MISP tags.

MITRE ATT\&CK and MISP Galaxy should be used as reference vocabularies. Ambiguous mappings should be preserved and marked, not automatically deleted.

### **6\. Entity Extraction**

The pipeline should extract all candidate entities that may become graph nodes. These should not be limited to the current baseline node types.

Candidate entities include:

* Event or Report;  
* Threat Actor;  
* Actor Alias;  
* Campaign;  
* Malware;  
* Tool;  
* Technique;  
* Tactic;  
* Domain;  
* IP;  
* URL;  
* File Hash;  
* Email;  
* ASN;  
* Country;  
* Sector;  
* Organization;  
* CVE;  
* Tag;  
* External Reference;  
* Source;  
* Author;  
* Timestamp.

Each extracted entity should store its raw value, canonical value, entity type, source field, extraction method, and confidence or ambiguity flag.

### **7\. Relationship Extraction**

The current graph already includes a small number of relationships, such as `InReport`, `ResolvesTo`, `HostedOn`, and `InGroup`. Stage 1 should extract a broader relationship inventory before deciding the final Neo4j schema.

Candidate relationships include:

* Event `HAS_INDICATOR` Domain/IP/URL/FileHash;  
* Event `ATTRIBUTED_TO` Actor;  
* Event `MENTIONS_ACTOR` Actor;  
* Event `HAS_TAG` Tag;  
* Event `REFERENCES` ExternalReference;  
* Event `USES_MALWARE` Malware;  
* Event `USES_TOOL` Tool;  
* Event `USES_TECHNIQUE` Technique;  
* Event `PART_OF_CAMPAIGN` Campaign;  
* Event `EXPLOITS` CVE;  
* Event `TARGETS_SECTOR` Sector;  
* Event `TARGETS_COUNTRY` Country;  
* URL `HOSTED_ON` Domain;  
* Domain `RESOLVES_TO` IP;  
* IP `BELONGS_TO_ASN` ASN;  
* IP `LOCATED_IN` Country.

Similar relationship names should be mapped into canonical forms. For example, `uses`, `leverages`, and `employs` should map to `USES`.

### **8\. Feature Extraction and Enrichment Plan**

Feature extraction should happen after raw collection. The pipeline should extract and store:

* timestamp features;  
* source and source type;  
* label availability;  
* attribution confidence;  
* Source reliability;  
* ambiguity flag;  
* actor aliases;  
* campaign aliases;  
* malware aliases;  
* indicator counts;  
* indicator type distribution;  
* tag count;  
* reference count;  
* temporal split assignment.

Optional enrichment can later add ASN, passive DNS, reverse DNS, GeoIP, WHOIS, domain age, URL host, and malware/hash metadata. Enriched fields should be clearly marked as enrichment, not raw data.

### **9\. Graph-Ready Output**

The final output of Stage 1 should be ready for Neo4j import. Recommended outputs include:

* raw JSON records;  
* unified intermediate JSON records;  
* extracted entities;  
* extracted relationships;  
* alias mappings;  
* relationship vocabulary;  
* entity and relationship summaries;  
* temporal split metadata;  
* processing report;  
* Neo4j import-ready files.

This allows multiple graph variants to be built later, such as a baseline IOC graph, an enriched IOC graph, a behavior-aware graph, or a full heterogeneous CTI graph.

### **Stage 1 Deliverables**

By the end of Stage 1, the project should produce:

1. A selected source list.  
2. A temporal split policy.  
3. Raw JSON CTI records.  
4. A unified intermediate JSON schema.  
5. Alias mappings for actors, campaigns, malware, and tools.  
6. Extracted entity inventory.  
7. Extracted relationship inventory.  
8. Feature and enrichment plan.  
9. Graph-ready files for Neo4j.  
10. A processing report covering missing values, ambiguity, and source coverage.

The key principle is: preserve raw CTI first, extract entities and relationships second, and build the Neo4j graph only after the schema is reviewed.

# Output format

**Structured CTI Representation**

This represents the expected output of the data collection, preprocessing, and normalization stage. The goal is to transform heterogeneous CTI sources into a consistent representation containing entities, relationships, attribution claims, and supporting metadata. This structured output will serve as the foundation for graph construction, feature extraction, confidence estimation, and downstream attribution tasks.

**Additional Relationships (This part should be refined, considering what relations can be mapped to others when having the same meaning)**

* USES  
* ATTRIBUTED\_TO  
* TARGETS  
* ASSOCIATED\_WITH  
* PART\_OF  
* OBSERVED\_IN

#### **Metadata and Attribution Signals other than what we already have**

**Timestamp**

* Report publication date  
* First seen / last seen  
* Campaign time period

**Source**

* Source name  
* Report identifier

**Source Type**

* Government  
* Vendor  
* Community  
* Knowledge Base  
* Threat Intelligence Platform  
* others

**Label Availability**

* Direct Attribution  
* Indirect Attribution  
* No Attribution

This distinguishes sources that explicitly provide actor labels from those that only provide supporting evidence.

**Attribution Confidence (if available)**

* High  
* Medium  
* Low

Some reports explicitly provide confidence assessments that can be preserved.

**Supporting Sources Count**

* Number of sources supporting the same attribution claim.

**Conflicting Sources Count**

* Number of sources supporting competing attribution claims.

**Evidence Count**

* Number of supporting evidence items associated with an attribution claim.  
* Possible evidence types include malware, infrastructure, domains, IPs, TTPs, campaigns, victimology, and reports.

**Alias Information**

* Threat actor aliases  
* Campaign aliases  
* Malware aliases

Used for entity resolution and graph normalization.

#### **Objective**

The goal is not to calculate reliability or confidence during preprocessing, but to extract and preserve signals that can later be used for source reliability assessment, confidence estimation, disagreement analysis, probabilistic labels, and ground-truth construction. 
