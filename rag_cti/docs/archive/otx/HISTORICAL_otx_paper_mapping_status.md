# HISTORICAL — OTX Paper-Style Mapping Prototype Status

> Archive category: OTX prototype status.
>
> **Status: HISTORICAL / SUPERSEDED.** Retained only as prototype evidence. Current
> OTX authority starts at `docs/OTX_DOC_STATUS.md`.

Status note: historical prototype record, superseded for current implementation
by the now-historical `docs/archive/otx/HISTORICAL_otx_downstream_projection_v2_4160_grill.md`.

Use this document only to understand what the earlier `otx_paper_mapping`
prototype produced. It is not the design source for the current OTX work. The
active path is the run-scoped `otx_downstream_projection` v2 mapper over
`data/raw/otx_collection_runs/routeA_20260704_policy_small_first/checkpoint.json`
`completed_pulse_details` (4,160 pulses). Do not treat this prototype's
paper-style flat table, MITRE-only mapping output, or unambiguous-row focus as
the current projection contract.

Snapshot: 2026-07-05

Status: prototype output, not an accepted final mapping decision.

This document records what the current prototype produced. It is not an ADR and
does not mean the project has accepted the MITRE-backed mapping route as the
final design.

## Prototype Purpose

This step converts the current completed OTX pulse-detail snapshot into the flat
actor/IOC attribution shape needed for comparison with the paper
`APT to Disagree: A Comparative Analysis of Attribution in Commercial TI`.

The paper method is:

1. Normalize heterogeneous IOC feeds into a flat schema.
2. Normalize source-provided actor names through an actor alias taxonomy.
3. Compare attributed IOCs by normalized indicator value, indicator type, actor
   id, and observation time.

The paper used an evaluated and augmented MISP Threat Actor Galaxy snapshot. This
repo does not currently contain that MISP TAG snapshot, so the current mapping is
MITRE-backed, using `docs/reference/seeds/mitre_actors.json`.

## Reference Code Check

`docs/reference/sample_code.py` contains graph-building logic:

- search OTX with APT name plus MITRE aliases;
- drop pulses whose tags map to multiple target APTs;
- write `Event -[:InReport]-> IOC`;
- map `domain/hostname`, `IPv4/IPv6`, and `URL/URI`;
- optionally enrich with pDNS and ASN.

`docs/reference/raw_otx_mitre/*` contains raw collection/provenance logic:

- build MITRE actor/alias query shards;
- download OTX search/pulse/indicator raw files;
- merge parts and preserve `query_actors` as discovery provenance.

For the current mapping, `query_actors` remains provenance only. It is not used
as actor attribution.

## Implemented Artifacts

Code:

- `src/rag_cti/intermediate/otx_paper_mapping.py`
- `scripts/build_otx_paper_mapping.py`
- `tests/unit/test_otx_paper_mapping.py`

Generated output:

- `data/processed/otx_paper_mapping/pulse_actor_mappings.jsonl`
- `data/processed/otx_paper_mapping/ioc_attributions_paper_style.jsonl.gz`
- `data/processed/otx_paper_mapping/mapping_summary.json`
- `data/processed/otx_paper_mapping/mapping_manifest.json`
- `data/processed/otx_paper_mapping/paper_comparison_summary.json`

The all-pulse `indicators_flat` artifact is intentionally not emitted by the
default script run because it is very large. The raw pulse files remain the
complete indicator source. Use `--emit-indicators-flat` only for a separate
large-output pass.

## Current Counts

- completed input pulses: 4,160
- pulse mapping rows: 4,160
- direct OTX adversary labels seen: 776
- paper-style IOC attribution rows: 40,065
- unique indicator/type pairs in attribution rows: 21,111
- normalized MITRE actors in attribution rows: 43
- pulses with paper-style IOC rows: 204

Pulse direct actor mapping status:

- `mapped_single_actor`: 392
- `mapped_multi_actor`: 2
- `partial_actor_mapping`: 9
- `unmapped_direct_actor_label`: 310
- `missing_direct_actor_label`: 3,447

Indicator type counts in the paper-style IOC attribution table:

- `url`: 18,135
- `domain`: 12,451
- `hash-sha256`: 5,542
- `hash-md5`: 1,937
- `hash-sha1`: 1,500
- `email`: 193
- `ipv4`: 49
- unmapped canonical type: 258

Timestamp basis:

- `indicator_created_point`: 39,990
- `indicator_created_to_expiration`: 75

## What Can Be Compared Now

Current OTX-only outputs can support:

- OTX actor coverage against the MITRE actor seed;
- OTX actor-attributed IOC counts by canonical indicator type;
- unique actor and unique IOC counts;
- timestamp basis coverage for active-window fields.

Current outputs cannot yet support:

- cross-vendor overlap coefficient;
- Krippendorff alpha actor/country agreement;
- MISP TAG country coverage;
- country attribution agreement.

Those require at least one additional vendor/source table in the same flat schema
and a MISP TAG or equivalent actor-country taxonomy.
