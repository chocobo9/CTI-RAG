# Source Confidence, Ambiguity, and Multi-Actor Attribution in Mature CTI Systems

Design disposition (2026-07-20): the authority and provenance distinctions remain architectural guidance; detailed ambiguity, multi-Actor attribution, and assessment behavior is deferred until the read-only Orientation/Working Set cycle is executable.

## Scope and method

This note examines how OpenCTI, STIX 2.1, MISP, OTX, and ODNI ICD 203 treat source quality, information credibility, observations, entity resolution, conflicting claims, and alternative attribution. It uses only official documentation, standards, and project-owned repositories.

Each section separates:

- **Source fact**: behavior or semantics explicitly stated by the owning standard or platform.
- **Architecture inference**: a design conclusion for CTI-RAG. It is not a claim that the cited system already implements that design.

The research question is not whether community CTI is useful. It is whether a community report, pulse, indicator, correlation, or inferred graph edge can safely become an authoritative fact or evidentiary conclusion in a Case.

## Executive conclusions

1. Community intelligence is a source of claims and investigative leads, not self-authenticating evidence. OTX describes Pulses as community-reported IOC collections, MISP is an information-sharing model, and STIX distinguishes raw `Observed Data` from a `Sighting` intelligence assertion. None of those facts makes a community assertion true in the Case merely because it was ingested.
2. Source reliability, information credibility, analytic confidence, and event likelihood are different dimensions. MISP's Admiralty taxonomy explicitly separates source reliability from information credibility. OpenCTI also distinguishes reliability from confidence, but deliberately fuses credibility into confidence for usability. ICD 203 separately discusses source quality, uncertainty, likelihood, and analyst confidence.
3. A normalized observable is not an actor identity. STIX permits an Indicator to indicate multiple threat-domain objects, models shared or rented infrastructure, and explicitly warns that `originates-from` should not define attribution. Observable-to-actor links must remain many-to-many, time-scoped claims.
4. Mature platforms provide useful parsing, deterministic observable IDs, aliases, deduplication, merging, analyst workbenches, graph relations, opinions, and warning lists. These mechanisms help organize data; they do not replace entity-resolution decisions or attribution analysis.
5. Conflicting reports must be preserved as separate sourced assertions. Upserting them into one canonical object or one confidence number destroys dissent, chronology, and provenance needed by ICD 203's analysis-of-alternatives standard.
6. CTI-RAG needs an explicit assertion and judgment layer above STIX/MISP/OpenCTI interoperability objects. The system should distinguish source artifacts, extracted claims, observations, evidence references, entity-resolution decisions, hypotheses, analytic judgments, and Case acceptance.

## 1. Community intelligence is not automatically fact or evidence

### Source facts

- LevelBlue describes OTX Pulses as collections of IOCs reported by the OTX community, which other members review and comment on. OTX feeds raw Pulse data to USM for correlation with local events. [LevelBlue: About OTX](https://docs.levelblue.com/documentation/usm-anywhere/user-guide/otx/about-otx)
- The OTX User Guide says a Pulse contains one or more IOCs and can include reliability, reporter, investigation details, comments, votes, edit suggestions, and external references. These are collaborative intelligence-sharing affordances, not a chain-of-custody model. [OTX User Guide](https://cybersecurity.att.com/documentation/resources/pdf/otx-user-guide.pdf)
- LevelBlue documents that noisy OTX Pulses can generate false-positive alarms and may be unsubscribed. [LevelBlue: Using OTX in USM Anywhere](https://docs.levelblue.com/documentation/usm-anywhere/user-guide/otx/using-otx-in-anywhere)
- STIX 2.1 explicitly states that `Observed Data` is raw information without an intelligence assertion. A `Sighting`, by contrast, denotes the belief that an SDO was seen; linking a Sighting to Observed Data expresses that raw data caused the producer to believe it saw the intelligence entity. [STIX 2.1: Observed Data](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_p49j1fwoxldc), [STIX 2.1: Sighting](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_a795guqsap3r)
- MISP describes itself as a threat-intelligence sharing platform supporting atomic attributes, complex objects, reports, taxonomies, galaxies, sightings, and external feeds. Its warning lists identify well-known values associated with potential false positives, errors, or mistakes. [MISP core repository](https://github.com/MISP/MISP), [MISP Best Practices](https://www.misp-project.org/best-practices-in-threat-intelligence.html)

### Architecture inference

Treat each imported OTX Pulse, MISP Event, STIX Report, blog, or community feed item as a `SourceArtifact`. Its contained statements become sourced `Claim` records. An IOC becomes a detection or investigation candidate, not a Case fact and not evidence merely because a feed labels it malicious.

Promote information only through explicit stages:

```text
SourceArtifact
  -> ExtractedClaim
  -> NormalizedObservable / EntityCandidate
  -> LocalObservation or EvidenceReference
  -> AnalyticJudgment
  -> accepted Case state
```

The stage must remain visible. Retrieval rank, connector trust, graph centrality, community votes, and feed popularity must not silently perform Case acceptance.

## 2. Reliability, credibility, confidence, and likelihood

### Source facts

#### MISP

- The official MISP Admiralty taxonomy states that the scale ranks both source reliability and information credibility, and exposes separate predicates: `admiralty-scale:source-reliability="a"..."f"` and `admiralty-scale:information-credibility="1"..."6"`. [MISP taxonomies repository](https://github.com/MISP/misp-taxonomies), [Admiralty taxonomy source](https://github.com/MISP/misp-taxonomies/tree/main/admiralty-scale)
- MISP taxonomies are machine tags. They can be applied locally or distributed, which makes the vocabulary reusable but does not itself enforce a judgment workflow. [MISP taxonomies](https://www.misp-project.org/taxonomies.html)

#### OpenCTI

- OpenCTI defines source reliability as trust in the source based on capabilities or history, normally assessed at organizational level. It defines information confidence as the credibility or quality of the information based on subject knowledge and corroboration. [OpenCTI: Reliability and confidence](https://docs.opencti.io/latest/usage/reliability-confidence/)
- OpenCTI attaches reliability to knowledge authors such as Organizations, Individuals, Systems, and Reports. Its default reliability vocabulary follows the Admiralty source scale but is customizable. [OpenCTI: Reliability and confidence](https://docs.opencti.io/latest/usage/reliability-confidence/)
- OpenCTI deliberately fuses the notion of information credibility into its 0-100 confidence field for most users, while allowing organizations to use both reliability and confidence. Its confidence templates include Admiralty, Low/Medium/High, and an Objective scale such as Told, Induced, Deduced, and Witnessed. [OpenCTI: Reliability and confidence](https://docs.opencti.io/latest/usage/reliability-confidence/)
- OpenCTI's maximum-confidence mechanism is also an authorization and data-governance control: users or connectors below an entity's confidence may be unable to update or delete it, and the conservative rule takes the lower of two applicable confidence levels. [OpenCTI: Reliability and confidence](https://docs.opencti.io/latest/usage/reliability-confidence/)

#### STIX 2.1

- The STIX `confidence` common property is the object creator's confidence in the correctness of the data, from 0 to 100. It is optional on SDOs and SROs, including Relationships and Sightings. [STIX 2.1: Common properties](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_q5ytzmajn6re)
- STIX Appendix A maps the same numeric field to several presentation scales, including Low/Medium/High, Admiralty credibility, words of estimative probability, and a DNI likelihood scale. [STIX 2.1: Confidence scales](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_1v6elyto0uqg)
- A STIX `Opinion` is one producer's assessment of the correctness of STIX objects produced by another entity. It supports disagreement/ agreement, explanation, authors, and references to the assessed objects. [STIX 2.1: Opinion](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_ht1vtzfbtzda)

#### ICD 203

- ICD 203 requires analytic products to describe source and methodology quality, including accuracy, completeness, denial and deception, currency, collection method, access, validation, motivation, bias, and expertise. It encourages a holistic source-summary statement. [ODNI ICD 203, tradecraft standard 1](https://www.odni.gov/files/documents/ICD/ICD-203_TA_Analytic_Standards_21_Dec_2022.pdf)
- ICD 203 treats likelihood of an event and an analyst's confidence in the basis for a judgment as different concepts. Confidence depends on the logic and evidentiary base, quantity and quality of source material, topic understanding, gaps, and assumptions. It warns against combining a confidence level and likelihood in the same sentence. [ODNI ICD 203, tradecraft standard 2](https://www.odni.gov/files/documents/ICD/ICD-203_TA_Analytic_Standards_21_Dec_2022.pdf)

### Architecture inference

Do not store a single generic `confidence` field as the complete epistemic state. Use independent dimensions:

| Dimension | Attaches to | Meaning |
|---|---|---|
| `sourceReliability` | source identity in a particular role/time period | Historical and technical trustworthiness of the source |
| `informationCredibility` | individual claim | Plausibility/corroboration of that specific information |
| `observationQuality` | collection event or evidence item | Integrity, completeness, collection method, custody, and freshness |
| `analyticConfidence` | analytic judgment | Confidence in the logic and evidentiary basis of the judgment |
| `likelihood` | proposition about an event/outcome | Estimated probability, distinct from confidence |

The architecture should preserve both native values and normalized values. A MISP `A2`, OpenCTI confidence 70, STIX confidence 70, and ICD 203 “likely” are not interchangeable without recording the scale, subject, assessor, time, and conversion rule.

STIX's mapping of DNI likelihood words into its generic `confidence` property is useful for interchange but semantically dangerous for an analytic system because ICD 203 explicitly separates likelihood from confidence. CTI-RAG should not inherit that collapse.

## 3. Parsing, normalization, and entity disambiguation

### Source facts

- OpenCTI separates connectors by role: external import, enrichment, internal file import, export, and streams. Import connectors convert external information to STIX 2.1; enrichment connectors add knowledge about existing objects. [OpenCTI: Connectors](https://docs.opencti.io/latest/deployment/connectors/)
- OpenCTI's document import can scan PDF, text, HTML, and Markdown, identify existing entities, and use regex for IP addresses and domains. Connector output is placed in an Analyst Workbench for review because import can misidentify object types or create unknown entities. [OpenCTI: Import from files](https://docs.opencti.io/latest/usage/import-files/), [OpenCTI: Analyst workbench](https://docs.opencti.io/latest/usage/workbench/)
- OpenCTI deduplicates entities with type-specific ID-contributing properties. Names and aliases participate in entity identity; STIX Cyber-observable Objects receive deterministic IDs based on STIX ID-contributing properties. Relationship deduplication uses type, source, target, and a time-window comparison. [OpenCTI: Deduplication](https://docs.opencti.io/latest/usage/deduplication/)
- OpenCTI can merge same-type entities, make non-primary names aliases, and preserve/re-anchor relationships. The operation is irreversible and some fields from non-primary entities, such as descriptions, are lost. [OpenCTI: Merging](https://docs.opencti.io/latest/administration/merging/)
- MISP Objects group contextually related attributes according to shareable templates, and object relations are extensible. MISP Galaxies provide threat-actor and other clusters with aliases/synonyms. [MISP Objects](https://www.misp-project.org/objects.html), [MISP object relations](https://www.misp-project.org/2021/03/17/misp-objects-101.html), [MISP Galaxy repository](https://github.com/MISP/misp-galaxy)
- MISP Galaxy added `threat-actor-classification` metadata because producers disagree whether a name denotes an operation, campaign, threat actor, or activity group. The metadata is an array specifically to retain disagreement. [MISP Galaxy release history](https://github.com/MISP/misp-galaxy/releases)
- STIX gives many SDOs an `aliases` property, uses exact ID references for object resolution, and permits `duplicate-of` and `derived-from` relationships. For SCOs, deterministic IDs can identify equivalent observables when producers follow the ID rules. [STIX 2.1: IDs and references](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_64yvzeku5a5c)

### Architecture inference

Parsing and entity resolution should be separate decisions:

1. `ParseCandidate`: exact span, parser/version, source artifact, page/offset, extracted type/value.
2. `NormalizedObservable`: syntax-level canonicalization for values whose identity rules are deterministic.
3. `EntityCandidate`: possible actor, campaign, malware, organization, or infrastructure identity.
4. `ResolutionProposal`: same-as, alias-of, related-to, or distinct-from, with supporting and contrary features.
5. `ResolutionDecision`: accepted/rejected/deferred by rule or analyst, attributable and reversible.

Deterministic IDs are strong for exact observables such as normalized hashes or addresses; they do not solve whether two vendor actor names denote the same organization, an overlapping activity cluster, a campaign, or a temporary operation.

Do not perform irreversible graph merge as the first disambiguation action. Maintain a canonical entity plus reversible alias mappings and retained source-local identities. A later analyst decision may redirect graph views without deleting source descriptions, claims, or alternative mappings.

## 4. One observable, multiple actors, shared infrastructure, and false flags

### Source facts

- STIX is a graph model in which generic Relationship objects connect SDOs and SCOs. The standard permits relationships beyond its predefined tables and permits user-defined relationship types. Relationships can carry creator, time range, confidence, external references, and markings. [STIX 2.1: Relationships](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_e2e1szrqfoan)
- An Indicator can `indicate` an attack pattern, campaign, infrastructure, intrusion set, malware, threat actor, or tool. The model does not impose an exclusive target. [STIX 2.1: Relationship summary](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_cqhkqvhnlgfh)
- STIX models Infrastructure separately and permits actors, campaigns, and intrusion sets to use, compromise, host, own, or communicate through infrastructure. The Intrusion Set section gives rented botnets as an example of hosted/owned infrastructure and notes that an Intrusion Set can be attributed before the underlying Threat Actor is known. [STIX 2.1: Infrastructure](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_jo3k1o6lr9), [STIX 2.1: Intrusion Set](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_5ol9xlbbnrdn)
- STIX explicitly says an Intrusion Set's `originates-from` Location relationship should not be used to define attribution. [STIX 2.1: Intrusion Set relationships](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_5ol9xlbbnrdn)
- MISP warning lists and the `false-positive` taxonomy are intended to flag values commonly associated with false positives. MISP workflows can retain such attributes while disabling the `to_ids` flag and applying false-positive tags. [MISP Best Practices](https://www.misp-project.org/best-practices-in-threat-intelligence.html), [MISP 2.4.174 curation workflows](https://www.misp-project.org/2023/07/31/misp.2.4.174.released.html/)
- OTX's own USM documentation acknowledges that a Pulse can create excessive noise and false-positive alarms. [LevelBlue: Using OTX in USM Anywhere](https://docs.levelblue.com/documentation/usm-anywhere/user-guide/otx/using-otx-in-anywhere)
- ICD 203 requires consideration of contrary information, possible denial and deception, key assumptions, indicators that would change judgments, and plausible alternative hypotheses. [ODNI ICD 203](https://www.odni.gov/files/documents/ICD/ICD-203_TA_Analytic_Standards_21_Dec_2022.pdf)

### Architecture inference

Observable correlation should never directly set `actorId`. Model attribution as separate claims:

```text
Observable <-observed-in- Observation
Observable <-used-by- InfrastructureUsageClaim
Infrastructure <-associated-with- ActivityClusterHypothesis
ActivityClusterHypothesis <-attributed-to- ActorHypothesis
```

Each claim should carry:

- source artifact and exact supporting passage or observation;
- source reliability and claim credibility;
- temporal scope;
- relationship semantics such as owns, rents, compromises, hosts, uses, or merely communicates-with;
- supporting, contrary, and ambiguous evidence references;
- deception/false-flag possibility;
- analyst confidence, likelihood, and assumptions;
- status: proposed, active, superseded, rejected, or unresolved.

The same IP, certificate, domain, malware family, or TTP may support several active actor hypotheses. Shared hosting, commodity tooling, compromised infrastructure, reseller access, actor handoff, and deliberate imitation are normal explanations, not exceptional data errors.

`falsePositive` and `falseFlag` must remain distinct:

- false positive: a detector/correlation incorrectly labels benign or unrelated activity;
- false flag: adversarial activity deliberately presents indicators intended to cause a wrong attribution;
- shared infrastructure: the observation is real, but actor exclusivity is unsupported;
- stale indicator: the historical claim may have been correct, but it is no longer operationally current.

## 5. Conflicting sources and alternative attribution

### Source facts

- A STIX `Opinion` can disagree with or explain disagreement about one or more STIX objects, including Relationship objects. The original object remains distinct from the Opinion. [STIX 2.1: Opinion](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_ht1vtzfbtzda)
- STIX permits multiple independently created Relationship objects and attaches `created_by_ref`, `confidence`, time range, and external references to each relationship. [STIX 2.1: Relationship](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_e2e1szrqfoan)
- MISP 2.4.186 added shareable Analyst Notes, Opinions, and Relationships that can attach to Events, Reports, Objects, Attributes, and Galaxy Clusters. [MISP 2.4.186 Analyst Data](https://www.misp-project.org/2024/03/06/misp.2.4.186.released.html/)
- OpenCTI's inference engine creates new graph relationships from predefined logical rules and visually distinguishes inferred relationships. Rules are reversible when deactivated. [OpenCTI: Inferences and reasoning](https://docs.opencti.io/latest/usage/inferences/), [OpenCTI: Rules engine](https://docs.opencti.io/latest/administration/reasoning/)
- ICD 203 requires systematic evaluation of plausible alternatives, explicit assumptions, contrary information, indicators that would change each alternative, and disclosure of significant differences in analytic judgment. [ODNI ICD 203, tradecraft standards 3, 4, 6, and 7](https://www.odni.gov/files/documents/ICD/ICD-203_TA_Analytic_Standards_21_Dec_2022.pdf)

### Architecture inference

Use an append-only claim graph rather than last-write-wins facts:

```ts
interface AttributionHypothesis {
	id: string;
	proposition: string;
	candidateActorRefs: readonly string[];
	competingHypothesisRefs: readonly string[];
	supportingClaimRefs: readonly string[];
	contraryClaimRefs: readonly string[];
	assumptions: readonly string[];
	changeIndicators: readonly string[];
	likelihood?: CalibratedLikelihood;
	analyticConfidence?: AnalyticConfidence;
	status: "active" | "superseded" | "rejected" | "unresolved";
}
```

Canonical graph entities are indexing anchors, not truth containers. Source-specific assertions should remain independently addressable even when they refer to the same canonical actor or observable. Conflicting claims should not average into one score; the Case projection should show the leading judgment, alternatives, decisive evidence, contrary evidence, and unresolved gaps.

Inference-generated relationships must retain derivation rule, input edges, engine/version, and inferred status. An inferred edge is a candidate analytic result, not primary evidence.

## 6. Reusable objects and logic, with gaps

| Source | Reusable objects or logic | Important gap for CTI-RAG |
|---|---|---|
| STIX 2.1 | `Observed Data`, SCOs, `Sighting`, `Indicator`, `Infrastructure`, `Intrusion Set`, `Threat Actor`, `Campaign`, `Relationship`, `Opinion`, `Note`, `Report`, `Grouping`, aliases, external references, markings, versioning | No first-class sourced Claim, Evidence, Hypothesis, competing-attribution, source-reliability, or Case-acceptance object. Generic `confidence` can conflate correctness, credibility, likelihood, and analytic confidence. |
| OpenCTI | STIX knowledge graph, connectors, workbench review, deterministic observable IDs, aliases, deduplication, merge, reliability vocabulary, confidence, inferred-edge marking and reversible inference rules | Upsert/merge can collapse source-local descriptions and disagreement; merge is irreversible. Credibility is intentionally fused into confidence. Entity confidence also participates in update authorization, which is not the same as epistemic confidence. |
| MISP | Events, Attributes, Objects, Object Relations, Galaxy Clusters, Sightings, Analyst Notes/Opinions/Relationships, Admiralty reliability/credibility tags, false-positive taxonomies and warning lists | Tags are flexible but weakly typed; they do not guarantee which claim, source version, relationship, or judgment a score assesses. Galaxy aliases/classifications retain some disagreement but do not provide a complete competing-hypothesis model. |
| OTX | Pulse, IOC, reporter, references, TLP, comments, votes, edit suggestions, subscriptions, IP reputation and local-event correlation | Community Pulse membership and reputation are not evidence of attribution. Public documentation does not expose a rigorous claim-level provenance, alternative-hypothesis, or analytic-confidence model suitable for Case authority. |
| ICD 203 | Source-quality factors, uncertainty explanation, likelihood lexicon, analytic confidence, facts/assumptions/judgments separation, alternatives, contrary information, judgment-change tracking | It is a tradecraft and product standard, not a machine-readable CTI graph or persistence model. CTI-RAG must encode these requirements explicitly. |

## 7. Recommended CTI-RAG epistemic model

The Intelligence and Evidence context should own reusable source artifacts, observations, provenance, normalized observables, and source-specific assertions. Case Management should own which judgments and references are accepted for a Case. Agent Workspace should generate only proposals and task-scoped findings.

Minimum distinct records:

| Record | Owner | Purpose |
|---|---|---|
| `SourceIdentity` | Intelligence and Evidence | Organization, person, system, connector, or anonymous community author, with contextual reliability history |
| `SourceArtifact` | Intelligence and Evidence | Immutable report, Pulse, MISP Event, STIX object/version, post, file, or feed item |
| `ExtractionRecord` | Intelligence and Evidence | Parser/version, exact source span, normalized output, parse uncertainty |
| `Claim` | Intelligence and Evidence | What a source asserts; separate from whether CTI-RAG accepts it |
| `Observation` | Intelligence and Evidence | What was directly collected, with collection context and provenance |
| `EvidenceReference` | Case Management | Case-scoped role assigned to an Intelligence Resource without copying it |
| `EntityResolutionDecision` | Intelligence and Evidence | Reversible same-as/alias/distinct/deferred decision with rationale |
| `Hypothesis` | Case Management | A plausible explanation or attribution alternative under evaluation |
| `AnalyticJudgment` | Case Management | A conclusion with likelihood, analytic confidence, assumptions, and supporting/contrary references |
| `WorkspaceFinding` | Agent Workspace | Non-authoritative task result awaiting acceptance |
| `CaseUpdateProposal` | Agent Workspace -> Case Management | Attributable proposal to accept/reject/change authoritative Case state |

### Non-negotiable invariants

1. `SourceArtifact != EvidenceReference != Case fact`.
2. `Observed Data != Sighting != Attribution Judgment`.
3. `sourceReliability != informationCredibility != analyticConfidence != likelihood`.
4. Entity resolution does not imply attribution.
5. Observable reuse does not imply actor identity.
6. A contradiction is preserved; it is not overwritten by the newest or highest-scored feed.
7. Inference outputs cite their input claims and rule/version.
8. Case acceptance is explicit and attributable; connector ingestion cannot perform it implicitly.
9. Historical scores remain immutable assessments with timestamps; recalculation creates a new assessment.
10. The model context always labels whether content is observation, source claim, inference, hypothesis, accepted judgment, or rejected/superseded material.

## 8. Consequences for Agent Workspace context projection

The model should receive a compact epistemic projection, not a flattened intelligence dump:

- accepted Case judgments and their current status;
- leading and plausible alternative hypotheses;
- supporting and contrary Evidence References;
- source reliability, claim credibility, analytic confidence, and likelihood as separate labeled values;
- unresolved entity mappings and attribution ambiguities;
- assumptions, collection gaps, and indicators that would change the judgment;
- change history explaining why the current judgment differs from a prior one;
- stable IDs for on-demand retrieval of source artifacts and provenance.

Raw community feeds, full reports, and all graph neighbors stay outside the default context. The agent retrieves them through tools when a hypothesis or contradiction requires inspection.

## 9. Boundary scenarios for continued grill

1. **Shared cloud IP, three actor reports**: the same IP appears in three OTX/MISP reports attributed to different actors; passive DNS shows shared hosting, and only one local Sighting exists. Decide what becomes an observable, claim, Evidence Reference, and attribution hypothesis, and what the model sees by default.
2. **Trusted source, weak claim**: a historically reliable provider publishes a high-confidence attribution based only on a commodity malware family and language artifacts. A less reliable source provides verifiable infrastructure-registration evidence pointing elsewhere. Determine how the four confidence dimensions interact without averaging them.
3. **False flag discovered after Case acceptance**: an accepted actor attribution is later challenged by evidence that the TTP and certificate naming were deliberately copied. Decide whether Case Management supersedes, retracts, or branches the judgment; how contrary evidence is preserved; and how running Agent Workspaces are reprojected.
4. **Irreversible merge hazard**: two actor aliases were merged in OpenCTI, but later reporting shows they are an operation and a sponsoring organization rather than one entity. Define what the adapter must preserve so CTI-RAG can reverse the resolution even if the upstream platform cannot undo the merge.
5. **Inference laundering**: an OpenCTI inferred relationship is exported as STIX, re-ingested through MISP, and returned as an apparently independent community source. Define lineage-based source independence so circular corroboration does not inflate credibility or analytic confidence.

## Primary sources

- [OASIS STIX 2.1 Errata 01](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html)
- [OpenCTI data model](https://docs.opencti.io/latest/usage/data-model/)
- [OpenCTI reliability and confidence](https://docs.opencti.io/latest/usage/reliability-confidence/)
- [OpenCTI deduplication](https://docs.opencti.io/latest/usage/deduplication/)
- [OpenCTI merging](https://docs.opencti.io/latest/administration/merging/)
- [OpenCTI import and workbench](https://docs.opencti.io/latest/usage/import-files/)
- [OpenCTI inferences](https://docs.opencti.io/latest/usage/inferences/)
- [MISP core repository](https://github.com/MISP/MISP)
- [MISP taxonomies repository](https://github.com/MISP/misp-taxonomies)
- [MISP Galaxy repository](https://github.com/MISP/misp-galaxy)
- [MISP Objects](https://www.misp-project.org/objects.html)
- [MISP Best Practices](https://www.misp-project.org/best-practices-in-threat-intelligence.html)
- [LevelBlue OTX documentation](https://docs.levelblue.com/documentation/usm-anywhere/user-guide/otx/about-otx)
- [OTX User Guide](https://cybersecurity.att.com/documentation/resources/pdf/otx-user-guide.pdf)
- [ODNI ICD 203: Analytic Standards](https://www.odni.gov/files/documents/ICD/ICD-203_TA_Analytic_Standards_21_Dec_2022.pdf)
