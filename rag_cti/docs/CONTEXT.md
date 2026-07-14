# CONTEXT — CTI-RAG Glossary

> Glossary only. No implementation details, no plans. Terms are added here
> as they are resolved during design discussion.

## Source populations

**narrative source** — A source whose records are prose describing TTPs,
actors, or campaigns. A reader (human or LLM) can read the text and infer what
it is about. Members: MITRE descriptions, OTX pulse text, PDF reports.

**field source** — A source whose records are structured fields keyed on an
indicator (domain / IP / hash), carrying infrastructure facts (resolutions,
ASNs, registration, certificates). The record contains no readable TTP content;
its meaning is not inferable from the record alone. Members: WHOIS, passive DNS,
VirusTotal.

## Labelling operations (these are two distinct problems)

**content labelling** — Assigning a label to a *narrative source* record by
reading its text and inferring the label. A prediction problem.

**indicator attribution** — Assigning meaning to a *field source* record by
matching its indicator against an already-labelled record and borrowing that
record's attribution. A lookup problem, not a prediction problem. (Field sources
also emit their own infrastructure facts directly, e.g. `domain resolves-to ip`;
attribution is the *inherited* part, not the only output.)

**OTX-derived lookup population** — A set of field-source lookup keys selected
from OTX indicators or URL hosts. OTX determines which keys are queried, but the
returned enrichment facts belong to the source that returned them, such as pDNS
or VirusTotal.

**source-backed enrichment fact** — An infrastructure or metadata fact returned
by an enrichment source for a looked-up indicator. It is source-backed by the
enrichment source, even when the lookup key was selected from another source
such as OTX.

**support enrichment** - An optional evidence-gathering operation used to fill
a specific support gap for an existing event, claim, or indicator. It is not a
stage of APT event discovery and does not determine collection completeness.

## Object model

**IntermediateRecord** - A reusable, source-level representation derived from a
raw source record before any consumer-specific projection. It preserves
provenance, timestamps, source classification, extracted mentions, candidate
relations, and modelling signals without committing to a RAG chunk shape or a
final graph schema.

**Projection** - A consumer-specific view derived from IntermediateRecords.
Examples include retrieval chunks for RAG, graph nodes/edges for GNN or Neo4j,
and feature tables for labelling algorithms. Projections are disposable and
regenerable; IntermediateRecords are the reusable contract.

**connector source** - The collection or connector identity that produced a
record, such as OTX, MITRE, passive DNS, VirusTotal, WHOIS, or PDF reports.
_Avoid_: source type

**source class** - The modelling role of a source population: ontology,
weakly-labelled narrative, unlabelled narrative, or infrastructure.
_Avoid_: source type

**publisher category** - The external publisher category of a source, such as
vendor, government, community, knowledge base, or threat-intelligence platform.
_Avoid_: source type

**controlled vocabulary** - A deliberately limited set of allowed values for a
field that downstream systems use for branching, joining, validation, training,
or querying. It constrains contract-level semantics such as entity type,
predicate, source class, and resolution method. It should not replace raw source
text or metadata that should remain open-ended.

**source contributor** - The account, handle, person, or organization recorded
by a source as the creator, submitter, or author of a record. A source
contributor is provenance metadata, not a threat actor and not a reliability
score by itself.

**threat actor** - A malicious or adversarial actor, intrusion set, group, or
cluster being described or attributed in CTI data. In this project, the
controlled `actor` entity type means threat actor.

**EntityMention** - A raw or normalized entity occurrence extracted from a
source record before canonical entity resolution. It preserves what the source
said and where it was found.

**entity resolution** - Mapping one or more EntityMentions to a canonical
Entity when the identity is known well enough. Ambiguous or unsupported matches
remain as unresolved mentions, orphan entities, or merge candidates rather than
being silently collapsed.

**identity grain** - The level at which an id says two things are the same.
Examples: a raw source record version, a source-field mention, a candidate
relation, an attribution signal, or a canonical entity. Different identity
grains need different ids when they are referenced independently.

**RelationMention** - A candidate relationship extracted from a source record
before final graph projection. It preserves raw endpoints, mapped predicate,
derivation method, and provenance.

**AttributionSignal** - A preserved attribution-related cue from the source
record, such as label availability, a direct actor claim, attribution confidence
if source-provided, supporting evidence count, conflicting source count, or no
attribution. An AttributionSignal is not itself ground truth.

**direct actor attribution** - A source-backed statement that a narrative source
record is attributed to one or more threat actors. In OTX pulse data, the
`adversary` field is treated as a direct actor attribution cue when its value is
actor-like.

**candidate actor evidence** - A weaker cue that may mention or suggest a threat
actor but is not itself a direct attribution. OTX tags and collection query
matches are candidate or provenance evidence unless a later decision promotes a
specific source field.

**collection candidate** - A source record discovered by a seed query and kept
for event-level triage. It is a recall result, not an actor attribution and not
yet authorization to expand all indicators or enrichment.

**discovery candidate** - A deduplicated source-record identity returned by one
or more discovery queries, together with every query path that found it. For
OTX, one discovery candidate is one unique Pulse ID. Candidate count measures
recall, not attributed Event count.

**actor-evidenced Event** - A source Event whose own structured fields contain
an actor attribution claim that passes the declared source-evidence routing
rule. For OTX in the current dataset, the cue is the `adversary` source field.
The term authorizes Pulse-detail acquisition; it does not mean final attribution
or ground truth.

**query-only candidate** - A discovery candidate for which the collected search
record contains no qualifying source-level actor claim. It remains preserved
with discovery provenance but is deferred from expensive detail expansion. The
absence of a search-level cue does not prove that the full source record has no
actor evidence.

**source event** - A source-native report-like record that groups narrative,
metadata, and indicator observations. An OTX Pulse is treated as a source event;
it is not assumed to be a real-world incident or a single-actor event.

**EventIndicatorOccurrence** - A source-backed occurrence stating that one
indicator appears in one source event, with relationship-specific timestamps
and provenance. It does not assert that an actor used or controlled the
indicator.
_Avoid_: observation when the Event-Indicator relationship is intended

**indicator source interval** - The time interval explicitly supplied by the
indicator source for that indicator occurrence. A single source timestamp is a
point observation, not an interval; missing bounds remain null rather than being
inferred from publication or collection time.

**dataset coverage window** - The declared time range used to select the
dataset population, such as 2023 through 2026. It belongs to the dataset or run
manifest and is not an individual Event's or indicator's activity interval.

**dataset temporal profile** - A descriptive summary of the actual source-time
and collection-time values present in a dataset, including coverage, minimum,
and maximum per field. It does not imply that the dataset was selected by those
bounds; an unfiltered dataset may have a temporal profile without a coverage
window.

**event expansion decision** - A cost and relevance decision that determines
whether a collection candidate's source-provided indicators may be
materialized. It is distinct from actor attribution and support enrichment:
ambiguous and multi-actor events remain retained when expansion is deferred.

**detail acquisition routing** - The deterministic decision that selects which
discovery candidates receive full source-record acquisition. It must cite
source-level evidence and a reason code, preserve deferred candidates, and
remain separate from attribution confidence. Query provenance alone cannot
authorize detail acquisition.

**phase-complete collection** - A collection state in which every in-scope
input has an auditable terminal state and every selected record has the required
raw coverage. It is always qualified by scope; it does not imply that an entire
external service, every candidate, enrichment, or downstream projection has
been collected.

**source attribution claim** - An actor label asserted by one source field on a
source event, preserved with its raw value and canonical-resolution state. It
belongs to source normalization, not cross-source fusion or ground truth.

**attribution assessment** - A versioned downstream inference that combines one
or more attribution claims and other evidence to assess which actors are
responsible for an event. It belongs to attribution/fusion, not data gathering.
_Avoid_: attribution decision when referring only to a parsed source field

**actor label claim** - One source-field label preserved from a record before
entity resolution, including the raw label, source field, and whether it can
contribute to attribution. It may resolve to one actor, multiple candidate
actors, no actor, or a non-actor value.

**multi-actor attribution** - A direct actor attribution cue that names more
than one distinct threat actor for the same source record. It is not the same as
disagreement; it is one source making a multi-actor assertion.

**actor alias collapse** - Resolving multiple actor labels from the same source
record to the same canonical actor identity. This preserves the raw labels while
preventing duplicate actor attribution.

**taxonomy ambiguity** - A resolution state where one actor label can map to
more than one canonical actor under the selected taxonomy. It remains ambiguous
until additional evidence resolves the identity.

**attribution disagreement** - A derived comparison result where multiple
independent occurrences for the same comparable object assign different actor
attributions. It is downstream analysis, not a property of one source field by
itself.

**Entity** — A canonical, normalized node. Type is one of: actor, campaign,
technique, family, indicator, location, asn, mitigation, detection-strategy.
Carries aliases and a nullable `ontology_id`. Identity normalization is a
precondition, not post-processing. An entity with no counterpart in the ontology
(e.g. an actor MITRE does not track, a free-text malware family with no S-number)
is an *orphan entity* — kept as its own node with `ontology_id: null`, never
force-merged. `asn` is an autonomous-system node sourced from passive DNS (no
MITRE counterpart, always orphan); `mitigation` and `detection-strategy` mirror
the MITRE M#### and DET#### objects (their authoritative-definition half is an
OntologyNode).

**OntologyNode** — The authoritative MITRE *definition* mirrored for one object
(technique / sub-technique / tactic / software / group / mitigation /
detection-strategy), versioned by `attack_version`. Distinct from Entity: **Entity is identity** (stable, what
Facts point at), **OntologyNode is definition** (drifts with ATT&CK). Linked
1:1 by `ontology_id` where it exists. A version bump reloads OntologyNodes only;
Entities and Facts are untouched.

**Fact** — A triple (subject Entity, predicate, object Entity). All three slots
are controlled: subject/object are entity ids, predicate is a controlled
vocabulary. The controlled predicates, each data-backed, are grouped by source:
*attribution / TTP* — `uses` / `attributed-to` / `targets`; *infrastructure*
(field sources) — `resolves-to` / `belongs-to` / `located-in` /
`uses-nameserver` / `has-subdomain`; *defensive* (MITRE) — `mitigates` /
`detects`. A predicate enters this set only when a source backs it; an extracted
verb with no mapping is a human-review candidate, never auto-added. Identity
equals the triple, so facts deduplicate exactly.

**Corpus Evidence** — A citable piece of source content admitted to the durable
knowledge corpus. It is many-to-many with Fact and may later be referenced by a
Case Evidence Item.
_Avoid_: Evidence Item when specifically referring to durable corpus membership

**supports** — The edge from an Evidence to a Fact. Carries `origin`,
`label_availability` (direct / indirect / none), `confidence`, and an observed
range (`observed_first` / `observed_last`). Confidence is a property of how the
fact was derived and lives on this edge, never on the Fact itself. A Fact's
aggregate credibility is the aggregation over its supports edges.

**Chunk / Document** — The indexed unit is the Chunk; a Document is its
provenance. Narrative sources split one Document into many Chunks. Field sources
are degenerate: one record = one Document = one Chunk = one Evidence (they still
enter the Chunk pipeline, just 1:1:1). One Chunk = one Evidence in all cases.
Chunk is a RAG Projection, not the reusable dataset unit for external modelling
consumers.

**ontology edge** — A definitional Entity-to-Entity edge from ATT&CK itself
(sub-technique belongs-to technique; technique belongs-to tactic). Axiomatic:
no confidence, no supports. Distinct from a *fact edge* (a Fact), which is
evidence-derived and carries supports/confidence.

## Investigation

**Investigation Case**:
A persistent, revisable CTI investigation with a declared question, scope,
participants, policy, lifecycle state, Ledger, and analytic outcomes.
_Avoid_: run, chat, agent session

**Ledger**:
The authoritative structured analytic record inside one Investigation Case. It
contains the Case's Claims, Evidence Items, links, hypotheses, gaps, strategies,
actions, observations, Verdicts, and revision history.
_Avoid_: transcript, trace, corpus, tool cache

**Claim**:
An atomic, entity-, time-, and scope-qualified statement that Evidence Items can
support or contradict. A source's claim and CTI-RAG's analytic judgment remain
distinct.
_Avoid_: Fact, answer sentence, source label

**Evidence Item**:
An immutable source span or artifact reference admitted to an Investigation
Case with provenance, time, integrity, handling, and dependency information.
_Avoid_: tool output, model summary, citation ID alone

**Claim-Evidence Link**:
The assessed relationship of an Evidence Item to a Claim in a declared scope:
supports, contradicts, contextual, irrelevant, or unresolved.
_Avoid_: supports edge, citation

**Dependency Cluster**:
Evidence Items that derive from the same upstream observation lineage and
therefore do not constitute independent corroboration merely by being separate
documents.
_Avoid_: source count, document count

**Hypothesis**:
A testable explanation considered by an Investigation Case. Attribution
hypotheses include reasonable alternatives and an unknown actor where relevant.
_Avoid_: answer candidate, model guess

**Gap**:
A specific missing discriminator, evidence property, permission, or unresolved
conflict that prevents a responsible judgment or separates competing
hypotheses.
_Avoid_: need more information

**Strategy**:
A bounded investigative method intended to resolve one or more Gaps. It may
produce several actions and has explicit applicability and exhaustion state.
_Avoid_: tool call, search query

**Action Proposal**:
A requested next investigative action that has not yet received execution
authority.
_Avoid_: executed action

**Admitted Action**:
An Action Proposal authorized under the Case's policy, permission, budget,
deadline, and idempotency constraints.
_Avoid_: valid tool call

**Observation**:
The structured outcome of an Admitted Action, including non-success outcomes
and its validated effect on the Ledger.
_Avoid_: raw tool output, ToolMessage

**Verdict**:
A versioned analytic judgment over Claims that states judgment, confidence in
the evidence basis, contradictions, alternatives, gaps, assumptions, and
Revision Triggers.
_Avoid_: source attribution claim, final answer text

**Revision Trigger**:
A detectable future condition whose occurrence requires a Verdict to be
reassessed without rewriting its historical revision.
_Avoid_: retry condition

**Abstention**:
A deliberate Case outcome in which policy refuses to publish a requested
judgment because the evidence basis or release conditions are inadequate.
_Avoid_: failure, empty answer, unresolved Claim

## Evidence lifecycle

**Temporary Evidence**:
An Evidence Item available to one Investigation Case but not admitted to the
durable knowledge corpus.
_Avoid_: cached corpus evidence

**Evidence Promotion**:
The governed admission of reviewed Temporary Evidence into a new durable corpus
revision.
_Avoid_: caching, retrieval indexing

**Source Acquisition Job**:
A persistent, bounded job that obtains and validates a user-requested source
under an explicit collection and publication scope.
_Avoid_: external lookup, tool call

**Scheduled Source Refresh**:
A recurring update of an already managed source under its existing governance
and collection contract.
_Avoid_: autonomous investigation, source acquisition
