# HISTORICAL — OTX Downstream Projection v2 Direction (4,160 snapshot)

> Archive category: OTX 4,160-population design.
>
> **Status: HISTORICAL / SUPERSEDED. This is not current and is not a source of
> truth.** It describes the earlier 4,160-Pulse calibration. Current OTX authority,
> population, and teammate-facing contract start at `docs/OTX_DOC_STATUS.md`.

Created: 2026-07-06

This is the current source-of-truth design direction for OTX mapping work. It
is intentionally shorter than the exploratory grill notes so another agent can
use it to identify stale docs and plan implementation.

## Core Goal

Build a run-scoped, local-raw OTX projection that keeps the sample-code graph
backbone while preserving multi-actor and ambiguous adversary information.

The projection should support Neo4j and GNN consumers without repeating
`sample_code.py`'s live OTX collection flow or its unambiguous-tag filtering.

## Current Data Boundary

Use the latest OTX run snapshot:

```text
data/raw/otx_collection_runs/routeA_20260704_policy_small_first
```

The input pulse population is exactly:

```text
checkpoint.json.completed_pulse_details
```

Current count: 4,160 pulse ids.

Do not scan all of `data/raw/otx` as the projection population. Existing
`data/processed/otx_downstream_neo4j` was built that way and is content-stale
for this task.

Discovery metadata such as `query` and `query_actors` is collection provenance.
It must not create actor attribution.

## Existing Output To Keep

Keep the sample-code-like graph backbone currently produced by
`otx_downstream_projection`:

- `nodes_events.jsonl`
- `nodes_iocs.jsonl`
- `edges.jsonl`
- `projection_manifest.json`
- `time_feature_coverage.json`
- `actor_label_summary.json`
- `acceptance_lint.json`

The graph vocabulary remains close to `sample_code.py`:

- nodes: `Event`, `Domain`, `IP`, `URL`, `ASN`
- edges: `InReport`, `HostedOn`, `ResolvesTo`, `InGroup`

`sample_code.py` writes directly to Neo4j. It does not produce a separate GNN
file package. The JSONL files above are this repo's Neo4j/GNN-ready projection
format that mirrors the sample-code graph shape.

## Actor Preservation Additions

Add two artifacts:

```text
nodes_actors.jsonl
actor_label_claims.jsonl
```

Extend `edges.jsonl` only with confirmed attribution edges:

```text
Event -[:AttributedTo]-> Actor
```

Do not add ambiguous candidate edges in v2 unless a later decision explicitly
requires them.

## What Goes In nodes_actors.jsonl

`nodes_actors.jsonl` contains actor nodes that the projection is willing to put
in the graph as actor identities.

For v2, include only actor identities that are resolved from OTX `adversary`
labels through the selected taxonomy/alias map.

Minimum fields:

```json
{
  "node_id": "actor:intrusion-set--247cb30b-955f-42eb-97a5-a89fef69341e",
  "node_kind": "actor",
  "labels": ["Actor"],
  "actor_id": "intrusion-set--247cb30b-955f-42eb-97a5-a89fef69341e",
  "name": "APT32",
  "taxonomy": "mitre_attack",
  "mitre_attack_id": "G0050",
  "aliases": ["APT32", "APT-C-00", "OceanLotus"],
  "raw_refs": []
}
```

Open decision: whether v2 should also create orphan Actor nodes for unmapped
but actor-like labels. The safer default is claim-only until alias augmentation
is designed.

## What Goes In actor_label_claims.jsonl

`actor_label_claims.jsonl` is the audit and preservation table for OTX
`adversary`. It records what was found in the raw field and how it was parsed
and resolved.

It is not a GNN label table by itself. It lets downstream code audit, debug, or
derive extra projections without losing raw actor/adversary information.

Minimum fields:

```json
{
  "event_id": "otx:pulse:667283e9c7683221cd83e3ac",
  "source_record_id": "667283e9c7683221cd83e3ac",
  "source_field": "adversary",
  "raw_field_value": "Kimsuky and Andariel",
  "raw_label": "Kimsuky",
  "normalized_label": "kimsuky",
  "label_index": 0,
  "parse_status": "parsed_label",
  "resolution_status": "resolved_single",
  "resolved_actor_ids": [
    "intrusion-set--0ec2f388-bf0f-4b5c-97b1-fc736d26c25f"
  ],
  "candidate_actor_ids": [],
  "contributes_to_attribution": true,
  "raw_refs": []
}
```

## Ambiguous Means What

In this design, ambiguous means taxonomy-resolution ambiguity:

```text
one parsed actor label -> more than one possible canonical actor
```

Example from MITRE seed:

```text
Thrip -> Lotus Blossom / G0030 OR Thrip / G0076
```

For an ambiguous label, v2 writes a claim row like:

```json
{
  "event_id": "otx:pulse:<pulse_id>",
  "source_field": "adversary",
  "raw_field_value": "Thrip",
  "raw_label": "Thrip",
  "normalized_label": "thrip",
  "parse_status": "parsed_label",
  "resolution_status": "ambiguous_taxonomy",
  "resolved_actor_ids": [],
  "candidate_actor_ids": [
    "intrusion-set--88b7dbc2-32d3-4e31-af2f-3fc24e1582d7",
    "intrusion-set--d69e568e-9ac8-4c08-b32c-d93b43ba9172"
  ],
  "contributes_to_attribution": false
}
```

For v2, ambiguous labels do not create:

- `Event -[:AttributedTo]-> Actor`
- `nodes_actors.jsonl` rows solely because they are candidates
- GNN label edges

They are preserved in `actor_label_claims.jsonl` so a later review or
disagreement/weak-evidence projection can use them.

## Multi-Actor Means What

Multi-actor attribution means one OTX `adversary` field names more than one
distinct resolved actor.

Example:

```text
Kimsuky and Andariel
```

v2 writes two resolved claim rows, two Actor nodes, and two `AttributedTo`
edges.

`Event.apt` remains `null` because it is a sample-code-compatible single-value
convenience field.

## Alias Collapse Means What

Alias collapse means multiple raw labels resolve to the same canonical actor.

Example:

```text
APT32, APT-C-00
```

Both labels resolve to APT32/G0050. v2 writes two claim rows, one Actor node,
and one `AttributedTo` edge with edge properties preserving both raw labels.

`Event.apt` can be `APT32` because the final resolved actor set has one actor.

## Non-Actor Values

Some `adversary` values are URLs, categories, prose fragments, malware names,
or other non-actor values.

For v2, preserve them in `actor_label_claims.jsonl` with:

```text
resolution_status = "non_actor_value"
contributes_to_attribution = false
```

They should not produce Actor nodes or `AttributedTo` edges.

## Event.apt Policy

`Event.apt` remains a legacy/sample-code-compatible convenience field:

- one resolved actor after alias collapse: actor name;
- multiple distinct resolved actors: `null`;
- ambiguous taxonomy only: `null`;
- unmapped/non-actor only: `null`;
- no adversary: `null`.

Downstream code should use `AttributedTo` edges for graph-native actor
relationships.

## GNN / Neo4j Use

`edges.jsonl` is still the graph edge input for Neo4j/GNN import.

For v2:

- `AttributedTo` edges are safe actor attribution edges.
- ambiguous candidates are not graph edges by default.
- `actor_label_claims.jsonl` is an audit/provenance side table, not a GNN label
  edge table.

This avoids giving GNN consumers a new ambiguous edge type that they might
accidentally treat as a training label.

## Deferred

Disagreement is deferred.

A later projection can compute IOC-level or report-level occurrence counts from:

- `Event -[:InReport]-> IOC`
- `Event -[:AttributedTo]-> Actor`
- `actor_label_claims.jsonl`

Do not implement disagreement inside the first v2 mapper.

## Docs Cleanup Guidance

Docs that describe `otx_paper_mapping` as the main approach are stale for the
current task.

Docs that describe `data/processed/otx_downstream_neo4j` counts as current are
stale because that artifact was built from all of `data/raw/otx`, not the 4,160
run-scoped population.

Keep or update docs about raw collection status and run-scoped completeness.
