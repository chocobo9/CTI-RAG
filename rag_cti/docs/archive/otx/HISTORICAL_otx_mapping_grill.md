# HISTORICAL — OTX Mapping Grill

> Archive category: OTX mapping exploration.
>
> **Status: HISTORICAL / SUPERSEDED.** Current OTX authority starts at
> `docs/OTX_DOC_STATUS.md`; the older v2 document referenced below is also historical.

Status note: historical design review, superseded for current implementation by
`docs/archive/otx/HISTORICAL_otx_downstream_projection_v2_4160_grill.md` (also historical).

Use this document only as background on earlier open questions and prototype
observations. It is not the current design source. The current direction is to
revise `otx_downstream_projection`, not continue the `otx_paper_mapping`
route. `sample_code.py` is now a graph-shape reference only; do not inherit its
live collection flow or ambiguous-label filtering policy. Multi-actor and
taxonomy-ambiguous OTX `adversary` content must be preserved, and disagreement
is deferred to a later derived projection.

Snapshot: 2026-07-05

Status: open design review. No final mapping ADR has been accepted.

## Core Goal

Use the existing OTX raw snapshot to build a defensible actor/IOC mapping layer,
then compare the resulting OTX-side data with the paper method and, later, with
paper/vendor-style data.

## Decisions That Are Not Settled

### 1. What is the actor taxonomy?

Option A: MITRE-backed only.

- Uses `docs/reference/seeds/mitre_actors.json`.
- Available locally now.
- Matches our collection seed source.
- Does not reproduce the paper exactly because the paper uses MISP Threat Actor
  Galaxy and country fields.

Option B: MISP TAG-backed.

- Closer to the paper.
- Needed for actor-country comparison.
- Requires adding a MISP Galaxy snapshot as a raw/reference input.
- Needs ambiguity policy because MISP TAG has ambiguous names.

Option C: dual taxonomy.

- Keep MITRE mapping for collection provenance compatibility.
- Add MISP TAG mapping for paper comparison.
- More complete, but more moving parts and more audit requirements.

Open grill question: Do we need exact paper-method comparability now, or is
MITRE-backed OTX-side mapping acceptable as an intermediate step?

### 2. What counts as actor attribution?

Candidate direct attribution sources:

- OTX `adversary`
- OTX `tags`
- MITRE actor alias search provenance

Current prototype decision:

- `adversary` is direct attribution.
- `tags` are candidate evidence only.
- MITRE search query provenance is collection audit only.

Why this needs grilling:

- Reference `sample_code.py` accepts/rejects pulses using tags.
- But our earlier domain boundary says collection provenance is not knowledge.
- OTX tags can contain actor names, vendors, malware, generic topics, and noisy
  labels.

Open grill question: Should OTX `tags` be allowed to create actor attribution,
or only validate/filter attribution already present in `adversary`?

### 3. What do we do with unmapped actor labels?

Current prototype behavior:

- Unmapped direct labels are preserved in `pulse_actor_mappings.jsonl`.
- They do not enter `ioc_attributions_paper_style.jsonl.gz`.

Observed unmapped examples include:

- `BlindEagle`
- `Lazarus`
- `APT 28`
- `Gamaredon`
- `Transparenttribe`

Why this matters:

- Some are real actors missing only because of normalization style.
- Some are not actors at all, such as `Informational` or `Malware Advisory`.
- Dropping them from the main table improves precision but hurts recall.

Open grill question: Do we need an alias augmentation pass before mapping, or is
preserving unmapped labels enough for this stage?

### 4. What is the output table contract?

Candidate core row:

```text
source/vendor
pulse_id
indicator_value_normalized
indicator_type_canonical
source_actor_label
normalized_actor_id
actor_name
actor_country
observed_start
observed_end
mapping_status
raw/provenance refs
```

Current prototype emits this for rows with unambiguous direct actor mapping.

Open grill question: Is this the table we want downstream mapping/comparison to
consume, or should downstream consume a more general IntermediateRecord first?

### 5. What does "compare to paper data" mean?

Computable now:

- OTX-side actor-attributed IOC counts.
- OTX-side actor coverage.
- OTX-side indicator type distribution.
- OTX-side timestamp basis coverage.

Not computable with current inputs:

- cross-vendor overlap coefficient;
- Krippendorff alpha;
- actor-country agreement;
- MISP TAG coverage.

Open grill question: Is the next target an OTX-side descriptive comparison, or
a true paper-method replication requiring MISP TAG and another vendor/source
dataset?

## Current Prototype Output

The current prototype output is useful evidence for the grill, not the final
decision:

- completed input pulses: 4,160
- paper-style IOC attribution rows: 40,065
- unique indicator/type pairs: 21,111
- normalized MITRE actors: 43
- pulses with paper-style IOC rows: 204

## Proposed Next Step

Do not create an ADR yet. First resolve these decisions:

1. Actor taxonomy: MITRE only, MISP TAG, or dual.
2. Attribution source policy: `adversary` only, tags as validation, or tags as
   attribution.
3. Unmapped label policy: preserve only, normalize heuristically, or augment
   alias map.
4. Paper comparison target: OTX-side summary now versus full paper-method
   replication later.
