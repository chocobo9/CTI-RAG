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

## Object model

**Entity** — A canonical, normalized node. Type is one of: actor, campaign,
technique, family, indicator, location. Carries aliases and a nullable
`ontology_id`. Identity normalization is a precondition, not post-processing. An
entity with no counterpart in the ontology (e.g. an actor MITRE does not track,
a free-text malware family with no S-number) is an *orphan entity* — kept as its
own node with `ontology_id: null`, never force-merged.

**OntologyNode** — The authoritative MITRE *definition* mirrored for one object
(technique / sub-technique / tactic / software / group), versioned by
`attack_version`. Distinct from Entity: **Entity is identity** (stable, what
Facts point at), **OntologyNode is definition** (drifts with ATT&CK). Linked
1:1 by `ontology_id` where it exists. A version bump reloads OntologyNodes only;
Entities and Facts are untouched.

**Fact** — A triple (subject Entity, predicate, object Entity). All three slots
are controlled: subject/object are entity ids, predicate is a controlled
vocabulary (`uses` / `attributed-to` / `targets`). Identity equals the triple,
so facts deduplicate exactly.

**Evidence** — A citable piece of source content. Many-to-many with Fact.

**supports** — The edge from an Evidence to a Fact. Carries `origin`,
`label_availability` (direct / indirect / none), `confidence`, and an observed
range (`observed_first` / `observed_last`). Confidence is a property of how the
fact was derived and lives on this edge, never on the Fact itself. A Fact's
aggregate credibility is the aggregation over its supports edges.

**Chunk / Document** — The indexed unit is the Chunk; a Document is its
provenance. Narrative sources split one Document into many Chunks. Field sources
are degenerate: one record = one Document = one Chunk = one Evidence (they still
enter the Chunk pipeline, just 1:1:1). One Chunk = one Evidence in all cases.

**ontology edge** — A definitional Entity-to-Entity edge from ATT&CK itself
(sub-technique belongs-to technique; technique belongs-to tactic). Axiomatic:
no confidence, no supports. Distinct from a *fact edge* (a Fact), which is
evidence-derived and carries supports/confidence.
