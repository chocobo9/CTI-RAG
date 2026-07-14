# OTX Event Discovery Contract Audit

## Conclusion

The smallest safe seam is a candidate-Event manifest between OTX search and
Pulse acquisition. Discovery, Pulse detail, and optional indicator-endpoint
pagination must be independently runnable. Source actor claims should be built
offline from Pulse fields, while embedded indicators remain source-provided
Event-IOC observations.

Every Pulse is retained. Multi-actor, taxonomy-ambiguous, parse-ambiguous,
unmapped, non-attributing, and missing source claims are data states, not drop
conditions.

## Contract Boundaries

| Concept | Meaning in this work | Required action |
|---|---|---|
| Collection provenance | The actor/alias query paths that discovered a Pulse | Preserve every path; never treat it as attribution |
| Source attribution claim | What the OTX `adversary` field states | Preserve raw value and deterministic taxonomy-resolution state |
| Event-IOC observation | An indicator contained in the OTX Pulse | Link it to the Event; do not infer Actor-IOC attribution |
| Attribution assessment | A downstream inference over multiple claims or evidence | Out of scope |
| Support enrichment | Optional evidence acquisition for a specific support gap | Out of scope and excluded from collection completeness |

## Reusable Seams

- MITRE actor/alias seed extraction and deduplicated OTX query construction.
- Stable RawStore identities for search pages, Pulse details, and indicator pages.
- Existing checkpoint and saved-file provenance mechanisms.
- Existing deterministic actor-label parsing and exact MITRE taxonomy resolution
  as semantic prior art for a narrow offline builder.
- Embedded Pulse indicators as the Event-IOC backbone.

## Logic That Must Not Be Reused

- The reference TRAIL `has_unambiguous_apt()` filter, because it drops
  ambiguous and multi-actor Events.
- DST, confidence, belief, uncertainty, or final attribution assessment.
- Actor-IOC flattening or automatic promotion of a source claim to a final
  `AttributedTo` graph assertion.
- pDNS, ASN, VT, WHOIS, or other support enrichment.
- Title-near-duplicate filtering as an Event-retention rule.

## Minimal Integration

1. Discovery writes raw search pages, per-path provenance, and one
   `candidate_events.jsonl` row per Pulse id.
2. Detail consumes the candidate manifest and fetches each selected Pulse once,
   without inspecting actor state.
3. Optional indicator pagination consumes the same manifest and requires an
   explicit page bound.
4. An offline source-claim builder emits Event rows, claim rows, and status
   counts without network access or confidence scoring.
5. Embedded indicators remain usable even when optional endpoint pages are
   absent or incomplete.

## Integration Risks

- Legacy runs predate `candidate_events.jsonl`; the manifest must be rebuildable
  from existing `discovery_metadata.jsonl` without repeating OTX searches.
- Existing downstream graph code can emit `AttributedTo` and pDNS-derived
  infrastructure. The new collection contract must not depend on that full
  projection.
- Shared package exports and documentation should be integrated centrally to
  avoid parallel edits in the dirty worktree.

## Targeted Regression Tests

- Discovery-only makes zero Pulse-detail and indicator-endpoint calls.
- Duplicate discoveries merge into one candidate while preserving every path.
- A legacy discovery log rebuilds the candidate manifest offline.
- Detail fetches each candidate at most once and preserves multi-actor source
  fields unchanged.
- Indicator phase refuses to run without an explicit page bound.
- Source-claim fixtures cover missing, single, alias-collapsed, multi,
  taxonomy-ambiguous, parse-ambiguous, non-attributing, and unmapped states.
- No new output contains confidence, DST, Actor-IOC attribution, or enrichment.
