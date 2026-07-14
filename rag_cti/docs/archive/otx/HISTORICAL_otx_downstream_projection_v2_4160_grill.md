# HISTORICAL — OTX Downstream Projection v2 Grill (4,160 snapshot)

> Archive category: OTX 4,160-population design review.
>
> **Status: HISTORICAL / SUPERSEDED. Do not use this as the current planning
> reference.** Current OTX authority starts at `docs/OTX_DOC_STATUS.md`.

Created: 2026-07-06

This document records the current design premises for revising
`otx_downstream_projection`. It supersedes the earlier paper-mapping prototype
as the planning reference for this work.

## Settled Premises

1. The current implementation direction is `otx_downstream_projection`, not
   `otx_paper_mapping`.

2. `otx_paper_mapping` is treated only as a low-confidence prior artifact from
   an earlier outbound thread. It is not the design source of truth.

3. `sample_code.py` is useful for its output shape and graph vocabulary, not
   for its live collection method or actor attribution policy.

4. The mapper must read local raw OTX data. It must not curl OTX or rebuild a
   live collection pipeline.

5. The input population is the latest OTX run snapshot described in the handoff
   and status docs: the 4,160 pulse ids in
   `data/raw/otx_collection_runs/routeA_20260704_policy_small_first/checkpoint.json`
   under `completed_pulse_details`.

6. Raw OTX pulse detail files are the authoritative source for the first
   projection pass. Discovery query metadata is collection provenance, not actor
   attribution.

7. The existing `data/processed/otx_downstream_neo4j` artifact is structurally
   informative but content-stale for the current task. It was built from the
   wider `data/raw/otx` directory and reports 9,698 events, not the current
   4,160-pulse run population.

8. The graph backbone should stay close to the sample-code output vocabulary:
   `Event`, `Domain`, `IP`, `URL`, `ASN`, and edges such as `InReport`,
   `HostedOn`, `ResolvesTo`, and `InGroup`.

9. Field names can initially remain close to existing
   `otx_downstream_projection` output. Later naming polish can move fields
   closer to sample-code conventions without changing semantics.

10. Multi-actor and ambiguous actor/adversary information must not be dropped.
    Filtering ambiguous actor labels the way `sample_code.py` does is not
    acceptable for this project.

11. OTX `adversary` is the direct actor attribution cue for the first actor
    preservation pass, subject to parsing and non-actor detection. OTX `tags`
    remain event metadata and candidate evidence unless a later decision
    promotes them.

12. Disagreement calculation is a later derived projection. The first v2
    projection should preserve enough event, IOC, and actor-attribution material
    to compute disagreement later, but should not define disagreement itself.

## Current Product Shape

Keep the existing graph-ready backbone:

- `nodes_events.jsonl`
- `nodes_iocs.jsonl`
- `edges.jsonl`
- `projection_manifest.json`
- `time_feature_coverage.json`
- `actor_label_summary.json`
- `acceptance_lint.json`

Add actor-preservation artifacts:

- `nodes_actors.jsonl`
- `actor_label_claims.jsonl`

Extend `edges.jsonl` with actor-related edges only when semantics are clear:

- `Event -[:AttributedTo]-> Actor` for resolved direct actor attribution.

Do not emit taxonomy-ambiguous candidate edges in the first v2 projection.
Candidate edges would be a new weak-signal training input, not part of the old
sample-code/GNN contract.

The existing `Event.apt` field remains a legacy/sample-code-compatible
convenience field:

- exactly one resolved canonical actor: fill with that actor name;
- multiple raw aliases resolving to the same actor: fill with that actor name;
- multiple distinct resolved actors: `null`;
- ambiguous, unmapped, or non-actor labels: `null`.

## Core Goal

Build a run-scoped OTX graph projection from the latest local raw OTX pulse
snapshot. The projection should keep the sample-code-compatible graph backbone
for Neo4j/GNN use while preserving OTX adversary labels, multi-actor
attribution, alias collapse, taxonomy ambiguity, and non-actor dirty values
without silently dropping them or converting uncertainty into a single
`Event.apt`.

The first v2 delivery is not a disagreement calculator. It is the actor-aware
projection that makes later disagreement calculation possible.

## Verified GNN Consumption Constraint

The teammate's older pipeline writes directly to Neo4j. The verified training
entrypoint is `train_gnn_hierarchical.py` in
`https://github.com/Mitraaaaa/GNN_APT`, which calls
`train_pipeline_hierarchical(...)`. It reads the populated Neo4j graph to train
per-type IOC autoencoders and a cross-validated GraphSAGE classifier. The
training target is hierarchical: Tier-3 named actor and Tier-2 nation.

This means the primary compatibility target is the Neo4j graph schema populated
by the sample pipeline, not a standalone JSONL shape by itself. JSONL artifacts
are acceptable as a staging/import format only if they can populate the same
Neo4j labels, properties, and relationships expected by the trainer.

Verified Neo4j labels consumed by the trainer:

- `Event`
- `Domain`
- `IP`
- `URL`
- `ASN`

Verified relationship types consumed by the trainer:

- `InReport`
- `HostedOn`
- `ResolvesTo`
- `InGroup`

Verified Event properties with training impact:

- `id`: node identity and index mapping.
- `apt`: Tier-3 single-label named actor supervision source.
- `label_confidence`, falling back to `belief_named_actor`: sample/loss weight.
- `pulse_created`: temporal weighting when recency weighting is enabled.

Verified Event properties read or written by the old pipeline but not directly
used as training labels/features:

- `nation`: not used as Tier-2 truth.
- `pulse_modified`
- `belief_nation_state`
- `uncertainty`
- `tag_exclusivity`
- `evidence_weight`
- `nation_coherence`
- `activity_cluster`

Tier-2 nation truth is derived from the true or predicted Tier-3 APT through the
old training config's `APT_TO_NATION`, not from `Event.nation`.

The old trainer has no multi-label or multi-actor support. `Event.apt` is a
single string; if it is missing or not in the active `APT_TO_IDX`, the Event
label becomes `-1` and the Event is excluded from the supervised train mask.
The Event can still remain in the graph as unlabeled context.

Multi-actor events and taxonomy-ambiguous labels therefore cannot safely be
forced into `Event.apt`. They must either:

- remain preserved outside the single-label training target; or
- require a later trainer change for multi-label or weak-label learning.

For v2, the conservative compatibility rule is:

- `Event.apt` remains the single-label training compatibility field;
- only events with exactly one resolved canonical actor populate `Event.apt`;
- multi-actor events preserve resolved actor information in claims and optional
  graph edges, but do not populate `Event.apt`;
- ambiguous/unmapped/non-actor values do not populate `Event.apt`.

For old-trainer compatibility, v2 should also emit the Event confidence fields
the trainer expects. When no source-provided confidence exists, the projection
must use a documented constant or null/fallback policy rather than inventing a
paper-like confidence score.

IOC feature completeness matters separately from graph shape. The old trainer
can run with missing IOC enrichment properties because feature extraction uses
defaults, but missing `Domain`, `IP`, and `URL` properties silently degrade
features toward zero or `other`.

The exact Neo4j loader/import path remains to be designed in this repo. The
loader must populate the verified Neo4j labels, properties, and relationships
above.

## Design Direction

The main module remains `otx_downstream_projection`. It should become a deeper
run-scoped projection module:

- external interface: one build function/script call that takes the run
  directory and output directory;
- hidden implementation: checkpoint filtering, raw-ref lookup, pulse loading,
  IOC projection, actor-label parsing, actor taxonomy resolution, alias
  collapse, and output writing;
- test surface: generated JSONL/JSON artifacts, not internal helper state.

The projection should distinguish three grains:

- `Event`: the OTX pulse/report-like record.
- `Actor`: a resolved canonical actor identity from the selected taxonomy.
- `actor label claim`: the source-field label occurrence before and during
  resolution.

`Actor` nodes and `AttributedTo` edges are only for resolved attribution.
Ambiguous, unmapped, and non-actor values remain visible through
`actor_label_claims.jsonl`; they must not be forced into `Event.apt`.

## Artifact Contracts

### `nodes_events.jsonl`

One row per completed pulse in the run-scoped population.

Existing fields stay valid unless a later naming pass changes them:

- `node_id`
- `labels`
- `source_record_id`
- `name`
- `description`
- `pulse_created`
- `pulse_modified`
- `apt`
- `actor_label_raw`
- `actor_labels`
- `actor_label_status`
- `tags`
- `references`
- `source_contributor`
- `raw_refs`

`apt` is a compatibility field. It is populated only when actor resolution
produces exactly one canonical actor for the event.

Resolver-aware event field semantics:

- `initial_labels`: parsed raw `adversary` labels in source order.
- `actor_labels`: distinct resolved canonical actor names. Empty when no actor
  is resolved.
- `actor_label_status`: event-level resolver state, such as
  `resolved_single`, `resolved_alias_collapsed`, `resolved_multi_actor`,
  `partial_resolved`, `ambiguous_taxonomy`, `unmapped_actor_like`,
  `non_attributing`, `parse_ambiguous`, or `missing`.

### `nodes_iocs.jsonl`

IOC and infrastructure nodes, preserving the existing backbone:

- `Domain`
- `IP`
- `URL`
- `ASN`

This artifact is not responsible for actor attribution.

### `nodes_actors.jsonl`

One row per resolved actor that appears in resolved event attribution.
Unmapped actor-like labels do not create Actor rows in v2.

Minimum fields:

- `node_id`
- `node_kind`: `actor`
- `labels`: `["Actor"]`
- `actor_id`
- `actor_name`
- `taxonomy`
- `taxonomy_id`
- `stix_id`
- `aliases`
- `taxonomy_ref`
- `modified`
- `revoked`
- `deprecated`

`actor_id` is the stable join id used by claims and edges. For MITRE-backed
actors, it should be deterministic from the selected taxonomy and STIX id or
ATT&CK external id. `actor_name`, `aliases`, lifecycle flags, and taxonomy refs
come from the MITRE intrusion-set object.

No row is required for non-actor dirty values, taxonomy-ambiguous labels, or
unmapped actor-like labels.

### `actor_label_claims.jsonl`

One row per parsed source-field label claim from actor-relevant fields. For v2,
the primary field is OTX `adversary`.

Minimum fields:

- `claim_id`
- `event_id`
- `source`
- `source_record_id`
- `source_field`
- `raw_field_value`
- `raw_label`
- `normalized_label`
- `label_index`
- `parse_status`
- `resolution_status`
- `resolved_actor_ids`
- `candidate_actor_ids`
- `match_method`
- `matched_taxonomy_labels`
- `resolution_taxonomy`
- `taxonomy_version`
- `contributes_to_attribution`
- `raw_refs`
- `notes`

`contributes_to_attribution` is resolver-final. It is true only when the claim
contributes to a resolved direct `AttributedTo` edge. Parser-level
actor-likeness is not enough.

This is the artifact that preserves ambiguous content. Examples:

- alias collapse:
  `APT32` and `APT-C-00` become two claims whose `resolved_actor_ids` point to
  the same actor.
- multi-actor attribution:
  `Kimsuky and Andariel` becomes two claims, each resolved to a different actor.
- taxonomy ambiguity:
  `Thrip` becomes one claim with `resolution_status=ambiguous_taxonomy` and
  multiple `candidate_actor_ids`.
- non-actor dirty value:
  a URL in `adversary` becomes one claim with
  `resolution_status=non_actor_value` and
  `contributes_to_attribution=false`.

### `edges.jsonl`

Existing backbone edge types remain:

- `InReport`
- `HostedOn`
- `ResolvesTo`
- `InGroup`

Add actor attribution edges:

- `AttributedTo`: Event to Actor, emitted only for resolved direct actor
  attribution.

Mandatory `AttributedTo` edge fields and properties:

- `edge_id`
- `type`: `AttributedTo`
- `start_node_id`
- `end_node_id`
- `start_label`: `Event`
- `end_label`: `Actor`
- `properties.source`: `otx`
- `properties.source_field`: `adversary`
- `properties.attribution_kind`: `direct_actor_attribution`
- `properties.claim_ids`
- `properties.raw_labels`
- `properties.resolution_taxonomy`
- `properties.resolver_policy_version`
- `properties.raw_refs`

`edge_id` identity is `(event_id, AttributedTo, actor_id, source_field)`, not
the claim id. This lets alias collapse produce multiple claims but only one
actor attribution edge.

Do not emit `AttributedTo` for taxonomy ambiguity, unmapped labels, or non-actor
values.

Candidate edges are deferred. If added later, they must use a separate edge
type, not `AttributedTo`, and should be treated as a new weak-signal input that
old `train_gnn_hierarchical.py` does not consume.

## Ambiguity Handling

Ambiguous content is written into `actor_label_claims.jsonl`.

For v2, ambiguity does not create a new GNN input by itself. It is an audit and
future-analysis artifact. The GNN/Neo4j backbone can consume old-compatible
single-label `Event.apt` and resolved `AttributedTo` edges while ignoring
unresolved claims. If a later GNN experiment wants weak candidate signals, it
can opt into a separate candidate-edge projection after the trainer supports or
explicitly ignores that edge type.

Therefore the first implementation should default to:

- resolved actor: `nodes_actors.jsonl` row plus `AttributedTo` edge;
- alias collapse: multiple claims, one actor row, one `AttributedTo` edge;
- multi-actor attribution: multiple actor rows and multiple `AttributedTo`
  edges;
- taxonomy ambiguity: claim-only, no actor edge;
- unmapped actor-like label: claim-only unless orphan actor policy is accepted;
- non-actor dirty value: claim-only with no actor edge.

The selected v2 option is minimal resolved Actor artifacts only:

- resolved claims create Actor nodes and `AttributedTo` edges;
- ambiguous, unmapped, and non-actor claims remain visible in
  `actor_label_claims.jsonl`;
- orphan/unmapped Actor nodes are not created in v2;
- claim-only-only output is too conservative because resolved multi-actor
  attribution would not be visible in the graph.

This balances old GNN compatibility with the project requirement to preserve
multi-actor and ambiguous attribution material.

## Known Data Problems To Handle

Existing `actor_label_summary.json` shows that current label splitting is too
coarse. Examples include:

- `MOIS (Ministry of Intelligence and Security)` splitting into
  `MOIS (Ministry of Intelligence` and `Security)`.
- `APT 28/29 - too much time too many problems` splitting into `APT 28` and
  `29 - too much time too many problems`.
- URLs in `adversary` being split as if path pieces were actor labels.

Therefore the v2 projection needs an auditable actor-label claim layer rather
than relying on `actor_labels[]` as final truth.

## Adversary Parser Contract

The OTX `adversary` parser is a claim generator, not the final actor truth
engine. It produces `actor_label_claims.jsonl` rows from the raw source field.
Actor taxonomy resolution and `Event.apt` population happen after parsing.

The parser should be conservative and auditable:

- Normalize the raw field with trimming and whitespace collapse. Empty values
  produce no claims and keep the event actor status as missing.
- Detect obvious non-actor values before splitting. URL-like values,
  advisory/category values such as `Informational` or `Malware Advisory`, and
  similar dirty values become one preserved claim with
  `contributes_to_attribution=false`.
- Do not split inside balanced parentheses. For example,
  `MOIS (Ministry of Intelligence and Security)` stays one claim.
- Split only top-level separators outside parentheses. Comma, pipe, semicolon,
  and plus are valid split points when they produce non-empty labels.
- Split top-level `and` only when both sides look like actor labels. This
  allows `Kimsuky and Andariel` but avoids splitting names inside
  parenthetical text.
- Treat slash as high-risk. Split clean actor-pair forms such as
  `APT32/OceanLotus`, but do not split URL paths, prose fragments, or shorthand
  values such as `APT 28/29 - too much time too many problems`.
- Preserve source order with `label_index`; do not sort parsed labels.
- Deduplicate exact normalized duplicates within a source field only after
  preserving enough claim-level provenance to explain what was observed.
- Suspicious labels are still written as claims, but they do not contribute to
  attribution unless resolution later proves they are actor labels.

Examples:

- `APT32, APT-C-00` becomes two claims. If both resolve to the same canonical
  actor, v2 emits one actor node, one `AttributedTo` edge, and
  `Event.apt=APT32`.
- `Kimsuky and Andariel` becomes two claims. If they resolve to distinct
  actors, v2 emits two `AttributedTo` edges and leaves `Event.apt=null`.
- `UAC-0056` can remain claim-only with
  `resolution_status=ambiguous_taxonomy` if the selected taxonomy maps it to
  multiple actors.
- URL-like `adversary` values become non-attributing dirty claims and never
  actor edges.
- Shorthand/prose values such as `APT 28/29 - too much time too many problems`
  should be marked as parse-ambiguous rather than auto-expanded.

## Working Semantics

`actor_label_claims.jsonl` should preserve one parsed label claim per source
field label. It should make visible:

- the raw field value;
- the parsed raw label;
- parse status;
- resolution status;
- resolved actor ids, if any;
- candidate actor ids, if taxonomy ambiguity exists;
- whether the claim contributes to direct attribution.

Alias collapse is required: multiple labels that resolve to the same actor
should produce one actor attribution edge while preserving every raw label claim.

Multi-actor attribution is required: one event can have multiple distinct
resolved actor attribution edges.

Taxonomy ambiguity must be preserved without pretending it is resolved
attribution.

Non-actor values must be preserved in claims but must not create actor
attribution edges.

## Tags Handling

OTX `tags` are event metadata and support/confidence evidence, not direct actor
attribution claims in v2.

The sample-code pipeline uses tags in two ways:

- It filters pulses for one queried `apt_name` by accepting only pulses whose
  tags map unambiguously to that target actor.
- It computes sample-compatible Event properties such as `tag_exclusivity`,
  `label_confidence`, `belief_named_actor`, `belief_nation_state`,
  `uncertainty`, `nation_coherence`, and `activity_cluster`.

The v2 projection should not copy the sample-code filtering policy because this
project must preserve multi-actor and ambiguous attribution. However, tags can
still provide useful Event attributes and support signals.

For v2:

- keep raw OTX tags on `Event.tags`;
- do not write tags into `actor_label_claims.jsonl`;
- do not let tags alone populate `Event.apt`;
- do not let tags alone create `Actor` nodes or `AttributedTo` edges;
- optionally derive sample-compatible support/confidence fields from tags after
  direct `adversary` attribution is resolved.

## Indicator Source Policy

For v2, embedded OTX pulse-detail indicators are the primary IOC source.
Endpoint indicator pages are optional enrichment and coverage-audit material.

Facts from the current 4,160 completed-pulse run:

- every completed pulse has a pulse-detail raw record;
- 3,736 completed pulses have endpoint indicator pages;
- 424 completed pulses do not have endpoint indicator pages;
- among endpoint-covered completed pulses, 3,733 have endpoint counts matching
  embedded indicator counts;
- 3 endpoint-covered pulses have fewer endpoint results than embedded
  indicators;
- no endpoint-covered pulse currently has more endpoint results than embedded
  indicators;
- embedded pulse details contain 55,659,022 indicator observations, while
  endpoint pages contain 11,265,131 endpoint observations in this run;
- `skipped_indicator_pages.jsonl` records oversized endpoint deferrals and
  states that endpoint enrichment was intentionally partial and pulse-detail raw
  remains the core IOC source.

The sample-code pipeline follows the same priority:

```python
indicators = pulse.get("indicators") or fetch_indicators(pulse_id)
```

It uses embedded pulse indicators first and calls the endpoint only as a
fallback when embedded indicators are absent.

Therefore v2 should:

- build the Event-IOC backbone from embedded `pulse_detail.indicators`;
- not replace embedded indicators with endpoint page results;
- use endpoint pages only to add indicator-level enrichment/provenance when an
  endpoint result can be matched to an embedded indicator;
- keep endpoint missing or endpoint count mismatch as manifest/lint/coverage
  facts, not as reasons to drop embedded indicators;
- treat future endpoint-only indicators as audit evidence until endpoint
  collection completeness is proven.

Benefits:

- maximizes IOC recall for the current collected dataset;
- respects the collection policy that intentionally made endpoint enrichment
  partial for oversized pulses;
- stays aligned with the sample-code source priority;
- preserves endpoint-only fields such as `false_positive`, `slug`, `pulse_key`,
  and endpoint raw refs without letting incomplete endpoint collection reshape
  the graph;
- keeps the Neo4j/GNN Event-IOC backbone stable even when endpoint coverage is
  missing or partial;
- makes coverage gaps auditable for later endpoint backfill.

## Neo4j Loader Open Issue

The old GNN trainer reads from Neo4j, while v2 projection produces auditable
JSONL staging artifacts. The remaining compatibility step is a JSONL-to-Neo4j
loader that writes the old trainer-compatible labels, properties, and
relationships.

This is an open issue until the team confirms the desired Neo4j write path.

The loader would need to map:

- `nodes_events.jsonl` to `Event` nodes;
- `nodes_iocs.jsonl` to `Domain`, `IP`, `URL`, and `ASN` nodes;
- `edges.jsonl` to `InReport`, `HostedOn`, `ResolvesTo`, and `InGroup`
  relationships;
- sample-compatible Event properties such as `id`, `apt`, `pulse_created`,
  `label_confidence`, and `belief_named_actor`;
- constraints/indexes expected by the old sample/trainer pipeline.

It must not force multi-actor, ambiguous, non-actor, or unmapped claim material
into the old single-label `Event.apt` training target.

## Confidence Field Open Issue

The old trainer reads `Event.label_confidence`, falling back to
`belief_named_actor`, as sample/loss weight. The sample-code pipeline computes
these values from tag exclusivity, IOC evidence weight, and nation coherence.

v2 does not yet define an equivalent confidence policy because direct
attribution comes from OTX `adversary`, while OTX `tags` are treated as
support/confidence evidence rather than direct actor claims.

This remains open until the team decides whether v2 should:

- use a documented constant for resolved direct `adversary` attribution;
- derive a simple sample-compatible support score from tags and IOC counts;
- leave confidence null for JSONL staging and require the Neo4j loader/trainer
  path to define fallback behavior.

The projection must not invent a paper-like confidence score without a
documented policy.

## Unmapped Actor-Like Open Issue

`unmapped_actor_like` is a resolver outcome, not a parser source category. The
raw labels come from OTX pulse-detail `adversary` fields. MITRE actor names and
aliases are used only as resolver taxonomy material and collection query
provenance.

Observed current-run examples from OTX `adversary` include:

- `BlindEagle`, while MITRE has `Blind Eagle` as an alias of `APT-C-36`.
- `APT 28`, while MITRE has `APT28`.
- `Transparenttribe`, while MITRE has `Transparent Tribe`.
- `Lazarus`, while MITRE has `Lazarus Group` but not necessarily the shortened
  label as an exact alias.
- `Gamaredon`, while MITRE has `Gamaredon Group`.
- `Akira Ransomware`, `wiper`, and `phishing`, which show that not every
  parsed `adversary` value should become an actor identity.

This remains an open issue because normalization rules can easily over-merge
unrelated names or promote non-actor values into actor nodes. Until a
data-backed normalization/resolution policy is designed and tested, unmapped
actor-like labels should remain claim-only:

- keep the `actor_label_claims.jsonl` row;
- set resolver status to an unmapped claim state;
- leave `resolved_actor_ids` empty;
- do not create `nodes_actors.jsonl` rows;
- do not emit `AttributedTo` edges;
- do not populate `Event.apt`.

## Open Issues

1. Open issue: design a data-backed actor-label normalization/resolution policy
   for OTX `adversary` labels such as `BlindEagle`, `APT 28`,
   `Transparenttribe`, `Lazarus`, and `Gamaredon`. Until this is resolved,
   unmapped actor-like labels remain claim-only and do not create orphan Actor
   nodes.

2. Open issue: confirm the Neo4j write path with the team, then build a
   JSONL-to-Neo4j loader for the old trainer-compatible schema.

3. Open issue: decide the confidence field policy for `label_confidence` and
   `belief_named_actor`.

## Deferred

Disagreement calculation is explicitly deferred. A later projection can compute
occurrence groups and attribution disagreement after actor resolution and event
identity/comparable-grouping rules are stable. Different sources or repeated
occurrences are not disagreement by themselves; disagreement requires comparable
events whose resolved actor attribution sets conflict.
