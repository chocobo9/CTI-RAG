# HISTORICAL — OTX Collection Chain Gap and Correction

> Archive category: OTX event-driven design rationale.
>
> **Status: HISTORICAL DESIGN RATIONALE.** The correction described here informed the
> event-driven chain but is no longer its operational authority. Current OTX authority
> starts at `docs/OTX_DOC_STATUS.md`.

## Conclusion

The current direction is semantically close but operationally mis-seamed.
Actor names and aliases are correctly described as discovery provenance, yet
the collector immediately turns every search hit into a fully expanded Pulse
collection job. Search, Pulse-detail acquisition, indicator pagination, and
cost policy execute in one nested loop. This makes a weak-label discovery hit
carry the cost of an accepted event before event relevance or attribution has
been assessed.

The corrected backbone should be **APT seed -> candidate OTX event -> raw event
evidence -> source attribution claims -> source-provided IOC observations**.
This aligns with an APT-group/event-driven approach without dropping ambiguous
or multi-actor events. Confidence assessment, clean-only projections, and
infrastructure enrichment are outside this collection task.

## Confirmed Current Behaviour

1. MITRE actor names and aliases become 577 deduplicated OTX queries. The
   current snapshot has touched only 135 queries but already discovered 4,905
   Pulse ids and completed 4,160 Pulse details.
2. Search hits are correctly recorded as collection provenance and explicitly
   not treated as actor labels.
3. In the same search-result loop, each newly discovered Pulse is immediately
   fetched through `/pulses/{id}` and then considered for
   `/pulses/{id}/indicators` pagination.
4. The only expansion brake is primarily an absolute indicator-count threshold
   after Pulse detail has already been fetched. Oversized endpoints are either
   sampled or deferred; smaller endpoints are expanded regardless of event
   attribution/relevance.
5. The downstream projection already has a useful event-centered shape:
   Pulse -> Event, embedded indicator -> Event-IOC observation, and OTX
   `adversary` -> actor-label claim. It preserves unresolved and ambiguous
   claims, while only resolved claims produce `AttributedTo` edges.
6. A separate paper-mapping projection still emits flattened actor-IOC rows for
   each unambiguous actor mapping. That output is a derived experiment view and
   must not become the collection contract or the authoritative attribution
   graph.

## Where the Chain Deviates

| Boundary | Intended meaning | Current operational meaning | Consequence |
|---|---|---|---|
| Actor/alias query | Discovery seed | Work generator for all matching Pulses | Broad aliases create unbounded fan-out |
| Search hit | Collection candidate | Immediate Pulse-detail and IOC-expansion job | No cheap candidate gate |
| OTX Pulse | Source event/report | Implicit complete collection unit | Event metadata and IOC payload cannot be budgeted separately |
| Indicator count | Cost signal | Main post-detail skip rule | Relevance and attribution do not affect expansion |
| Multi-actor/ambiguous | Evidence state to preserve | Preserved in some projections, but not a first-class collection state | Policies remain implicit and projection-specific |
| Completeness | Coverage of an explicitly selected population | Tends toward all search pages + all discovered details + all non-deferred endpoints | “Complete” becomes unnecessarily expensive and unclear |

The principal cause of the complexity is therefore not OTX itself. It is the
absence of a **candidate manifest and an explicit event-expansion boundary**.
Checkpointing, three raw populations, skip ledgers, endpoint backfill, and
large completeness audits compensate for a collector whose unit of work is too
large.

## Corrected Domain Model

```text
APTGroup / Alias
    -> discovers -> CollectionCandidate (OTX search hit)
    -> fetches minimal -> SourceEvent (OTX Pulse detail)
    -> yields -> SourceAttributionClaim(s)
    -> contains -> EventIndicatorObservation(s)
```

Important semantics:

- Query-to-actor association is provenance only.
- OTX `adversary` is a source-backed actor claim, not ground truth.
- Tags/title/description/query matches are candidate evidence, not direct
  attribution by default.
- Event-IOC means the IOC occurred in the Pulse. It does not by itself mean the
  actor owns or used that IOC.
- Multi-actor, ambiguous, unresolved, and missing source claims are preserved
  source states; none requires dropping the event.

## Proposed Lightweight Chain

### Stage 1: Discover and deduplicate candidates

Run all actor/name alias queries, but persist only a compact candidate manifest
keyed by `pulse_id`. Merge every discovery path into that row. Do not fetch
indicator endpoints here.

Candidate fields should stay small: Pulse id, search metadata, matched queries,
candidate APT ids, first/last discovery time, and discovery count.

### Stage 2: Fetch source-event detail once

Fetch each unique Pulse detail once. Treat the embedded indicator list/count as
part of the source response already returned, not as a reason to immediately
page a second endpoint. Materialize event metadata and attribution signals.

This stage is enough for title/description/tags/references/adversary-based
triage and for preserving raw ambiguous evidence.

### Stage 3: Normalize source claims without assessing confidence

Write source-claim rows that preserve the OTX field and deterministic taxonomy
resolution state:

- `single_actor`
- `multi_actor`
- `ambiguous`
- `unresolved`
- `missing_source_claim`

These are source-normalization states, not confidence scores or final
attribution assessments. They do not decide Event retention.

### Stage 4: Expand IOC data selectively

For most accepted events, use embedded Pulse indicators as the Event-IOC
backbone; the existing downstream projection already follows this policy.
Call `/pulses/{id}/indicators` only when the endpoint provides required fields
missing from embedded indicators, when an audit sample is needed, or when a
named experiment explicitly requires endpoint completeness.

## Default Policy

| Event state | Keep raw event | Keep source claims | Keep embedded indicators |
|---|---:|---:|---:|
| Single actor | yes | yes | yes |
| Multi-actor | yes | yes | yes |
| Ambiguous/unresolved | yes | yes | yes |
| Query hit with no source actor claim | yes | yes | yes |
| Oversized event | yes | yes | yes; endpoint pagination may defer |

There is no clean-only projection in this task. Infrastructure enrichment is a
separate, optional support-evidence workflow and is not part of this policy.

## Minimal Implementation Change

Do not rewrite the existing raw store or event projection. Introduce one seam
and split orchestration around it:

1. Make discovery output a deduplicated `candidate_events.jsonl` manifest.
2. Stop the discovery command after search pages, or make Pulse detail a
   separately resumable phase.
3. Generate `source_attribution_claims.jsonl` from Pulse details without
   confidence scoring or final attribution inference.
4. Treat embedded Pulse indicators as source Event-IOC observations; endpoint
   pagination remains an explicitly bounded collection option.
5. Define completeness per phase: query coverage, selected Pulse-detail
   coverage, decision coverage, selected endpoint coverage. Do not use “full
   OTX completeness” as the normal goal.
6. Keep Events, source actor claims, and Event-IOC observations as the reusable
   event-centered representation. Do not require a clean-only projection or an
   actor-IOC flattened table.

## Acceptance Criteria

- One Pulse is fetched once even when many actor aliases discover it.
- Completing actor-query coverage does not trigger indicator endpoint calls.
- Every candidate Pulse has a traceable discovery set and a terminal triage
  state.
- Every fetched event preserves its source attribution-claim state, including
  missing, ambiguous, unresolved, and multi-actor states.
- Multi-actor and ambiguous events remain queryable in the raw evidence layer.
- No actor-IOC attribution edge is created merely because an IOC appears in an
  actor-attributed Pulse; the graph retains Event-Actor and Event-IOC edges.
- Endpoint cost is bounded independently from actor alias search recall.
- No infrastructure enrichment is required for collection completeness.

## Recommended First Iteration

Use the existing 4,160 completed Pulse details as a fixed calibration set. Do
not resume broad indicator endpoint backfill yet. First generate decision-state
counts and measure how many events fall into single, multi, ambiguous,
unresolved, no-evidence, duplicate, and oversized buckets. Then choose the
smallest expansion policy that supports the graph experiment. This turns the
current backlog into a policy question instead of an assumed collection debt.
