# Intelligence and Evidence

Intelligence and Evidence owns reusable source material, provenance, structured intelligence, retrieval access, and specialist analysis capabilities shared across Cases.

## Language

**Intelligence Resource**:
A globally reusable source, report, observable, entity, relationship, or analysis result with stable identity and provenance.
_Avoid_: Case attachment, prompt content

**OpenCTI Source Resource**:
An object or file made available by one OpenCTI instance with OpenCTI identity, content, markings, and actor-visible access semantics.
_Avoid_: Intelligence Resource version, Case evidence

**Resource Version**:
An immutable realization of an Intelligence Resource bound to exact source content and provenance; correction or changed source content creates another version rather than overwriting it.
_Avoid_: Current database row, OpenCTI timestamp

**Source Capture**:
An immutable, digest-addressed record of the exact bytes and metadata I&E obtained from one bounded observation of an OpenCTI Source Resource.
_Avoid_: OpenCTI revision, mutable cache

**Resource Derivative**:
A reproducible artifact produced from exact Resource Versions by a declared method version and configuration, such as an extraction, Retrieval Segment, or embedding.
_Avoid_: New source, independent corroboration

**Source Span**:
A reference from a Resource Derivative to an exact location in its Source Capture using one declared coordinate system.
_Avoid_: Unqualified offset, citation prose

**Retrieval Segment**:
A bounded text or structured fragment prepared for retrieval while retaining its exact Resource Version and Source Spans.
_Avoid_: Evidence, independent source, arbitrary chunk

**Derivation Manifest**:
An immutable record binding a Resource Derivative to its exact inputs, producing method and configuration, schemas, outputs, and digests.
_Avoid_: Build log, model rationale

**Index Generation**:
A complete, immutable retrieval view that becomes active atomically; readers observe one complete generation rather than a mixture of an old and new build.
_Avoid_: Mutable index, global corpus revision

**Retrieval Receipt**:
An immutable record of one completed retrieval binding its actor and purpose, query or exact selector, processing versions, declared coverage, ordered results, and result digest.
_Avoid_: Search log, Case evidence, Working Set update

**Retrieval Trace**:
A retention-bounded diagnostic record of the full candidate set and intermediate ranking features for a Retrieval Receipt.
_Avoid_: Permanent Case record, Retrieval Receipt

**Resource Capsule**:
An actor- and purpose-authorized projection of exact Resource Versions, selected Retrieval Segments, provenance, lineage, status, and use constraints returned to a Workspace.
_Avoid_: Prompt, Working Set, Evidence Reference

**Enrichment Profile**:
A prequalified, versioned, bounded kind of collection or analysis outcome that trusted code may admit for an Agent request without exposing Connector or infrastructure controls.
_Avoid_: Connector configuration, arbitrary workflow, model tool

**Use Disposition**:
I&E's current deterministic decision about which uses of a Resource Version are allowed, restricted, denied, or unknown under its markings, license, retention, actor, and purpose.
_Avoid_: Resource Use Permit, API permission, source reliability

**Provenance**:
The traceable origin and transformation history that allows an Intelligence Resource to be evaluated and cited.
_Avoid_: Model rationale

**Source Assertion**:
A proposition exactly stated or represented by one source under an exact Resource Version and Source Span; it records what the source claims, not that the proposition is true.
_Avoid_: Verified fact, accepted conclusion, proof

**Source Lineage**:
The derivation and relay relationship among Intelligence Resources used to determine whether apparently separate reports provide independent corroboration.
_Avoid_: Feed count, citation count

**Reporting Prevalence**:
The number and variety of Intelligence Resources or channels carrying the same assertion before source dependency is resolved; it measures visibility, not truth or corroboration.
_Avoid_: Confidence, source reliability, independent corroboration

**Independent Corroboration**:
Support for the same assertion from materially independent Source Lineages; it may increase Information Credibility but never makes the assertion certain.
_Avoid_: Feed count, source diversity, repeated reporting

**Unknown Source Dependency**:
A state in which the system cannot establish whether two Intelligence Resources are independent. Their content remains usable, but they do not count as separate corroboration until independence is established.
_Avoid_: Independent source, duplicate resource

**Resource Reference**:
A semantically neutral Case link to an Intelligence Resource; it records relevance or investigation interest without asserting that the resource proves or disproves a finding.
_Avoid_: Evidence, accepted fact

**Resource Use Permit**:
An I&E-owned, signed single-operation decision reservation binding one actor, purpose, Case, target authority, operation/effect, intended use, and exact Resource version; it is irrevocable for that exact binding until expiry, while the consuming authority atomically records local consumption with its command decision.
_Avoid_: Cached authorization, Capability Grant, Resource Reference, API token

**Evidence Reference**:
A Case-assessed relationship between an Intelligence Resource and a specific finding, including whether it supports, contradicts, or otherwise qualifies that finding. It is still fallible and does not mean the referenced content is true.
_Avoid_: Resource copy, neutral resource link, proof

**Source Reliability**:
An assessment of the producer or channel based on identity, capability, and track record; it does not determine whether a particular item is correct.
_Avoid_: Information credibility, connector confidence

**Information Credibility**:
An assessment of a particular assertion based on corroboration, plausibility, currency, and contradiction, independent of the source's general reliability.
_Avoid_: Source reputation, analytic likelihood

**Candidate Finding**:
A proposition retrieved, extracted, or generated for a Case that has not yet been accepted as part of its authoritative investigation record. Competing Candidate Findings may coexist and retain separate supporting and contradicting Resource References.
_Avoid_: Evidence, fact

**Extraction Ambiguity**:
A state in which source content admits more than one plausible parse, entity resolution, or structured assertion and therefore must retain alternatives rather than silently selecting one.
_Avoid_: Low source reliability, analytic disagreement

**Source-local Identity**:
The name, type, and identifier for an entity exactly as asserted by one producer, retained independently until any cross-source identity decision is accepted.
_Avoid_: Canonical entity, accepted alias

**Entity Resolution Hypothesis**:
A reversible proposition that two Source-local Identities refer to the same entity, distinct entities, or an unresolved relationship; behavioral similarity alone does not resolve it.
_Avoid_: Alias, entity merge, attribution

**Activity Clustering Hypothesis**:
A reversible proposition that a set of observations, behaviors, tools, or infrastructure belongs to the same Campaign or Intrusion Set without identifying the real Threat Actor behind it.
_Avoid_: Threat Actor identity, accepted attribution

**Attribution Candidate**:
A provisional association between investigated activity or an Intrusion Set and one possible Threat Actor, maintained independently from competing candidates until an authoritative Case decision is made.
_Avoid_: Accepted attribution, actor alias
