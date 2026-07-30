# EviTRAIL non-OTX source alignment

Status: real-sample audit and reproducible adapter  
Consumer: `Mitraaaaa/Evitrial@da4a29e8ce25cff8cbddebb444b069296f949511`  
Audit date: 2026-07-30

## Result

The already published `evitrail_complete_handoff_20260727/handoff` remains
usable through the current `read_handoff()`. That does **not** mean the four
underlying raw roots can all be passed directly to the current source readers.
The direct raw/normalized routes have the compatibility gaps below.

| Source | Real sample | Exact current-reader smoke | Decision | Adapter claim policy |
|---|---|---|---|---|
| ORKL | `data/raw/orkl/raw/reports/00007130-a1ca-4f6e-af36-44f78a8fdd8c/afc840d6c51ad3d1bdd517787b4e15ccb3d4cab93c2d75d8a4811b8437d7903c.json` | 1 Event, 2 URL observations, 3 claims, 0 rejections | narrow adapter | `report_context` / `provenance_only` |
| CIRCL MISP | `data/raw/circl_misp/raw/events/dbc619e5-1b69-44c6-81d0-7fb79390bde4.json` | 1 Event, 56 IOC observations, 1 claim, 96 explicit unsupported-IOC rejections | narrow adapter | structured galaxy relations are `attribution` / `candidate` |
| APTnotes | `data/raw/aptnotes/raw/repository/APTnotes.json` and normalized report `aptnotes:report:25e44…` | raw index: 0 Events; normalized reports: 686 Events but 0 IOC/claims and title-based identity | narrow adapter | extracted/structured narrative actor evidence stays `report_context` / `provenance_only` |
| CISA | `data/raw/cisa/raw/html/AA23-108.html` | `read_source("cisa", ...)` raises `unsupported source: cisa` | handoff adapter required | text actor candidates stay `report_context` / `provenance_only` |

CISA attachments and APTnotes document artifacts are evidence belonging to
their advisory/report. They are not separate Events.

## Observed gaps

- ORKL's raw report is readable, but `fetched_at` lives in the normalized
  sidecar. The current reader's `Provenance.collected_at` is null. The sidecar
  contains four raw actor relations for the sample, including two distinct
  APT33 occurrences; `read_orkl` collapses them to three unique raw names.
- CIRCL MISP's raw reader correctly retains supported IOCs and explicit
  rejections, but the sample's six structured actor-tag occurrences become
  only the `Sofacy` claim. APT28 intrusion-set tags and duplicate source-field
  occurrences are lost. Collection time again lives in the normalized sidecar.
- APTnotes' raw index field names do not match `read_aptnotes`. Passing
  normalized reports creates Events, but uses title as `source_record_id`,
  misses the listed source date, and has no document IOC/claim join.
- CISA has no current raw-reader dispatch entry.

The adapters preserve every raw claim occurrence and source field. EviTRAIL's
vocabulary support calculation counts distinct Event IDs, so repeated aliases
inside one Event do not create duplicate Event-support votes.

`ActorClaim`'s schema defaults are `attribution` / `candidate`, but both
`read_orkl` and `read_aptnotes` explicitly override those defaults with
`report_context` / `provenance_only`. This implementation follows the reader
override and does not change consumer policy. The previous complete builder's
APTnotes training-source promotion is therefore not reused in this route.

## Timestamp and provenance route

- ORKL: normalized `fetched_at`, `modified_at`, and valid source dates are
  copied to the Event; sentinel year `0001` is rejected explicitly.
- CIRCL MISP: normalized `fetched_at` is joined to the raw Event identity;
  event, modified, and published times remain distinct.
- APTnotes: `listed_date` is normalized only to its stated day precision and
  `fetched_at` remains collection time.
- CISA: published, updated, and fetched times remain separate.
- IOC evidence retains its own raw reference, source field or character span,
  extraction method, and available first/last-seen clocks.

## Reproducible commands

Unit contract:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python -m pytest tests/unit/test_evitrail_source_alignment.py -q --no-cov
```

Real-sample compatibility audit:

```powershell
python scripts/audit_evitrail_source_alignment.py `
  --raw-root <cti-rag>/data/raw `
  --processed-root <cti-rag>/data/processed/trail_multisource_part1_v1_20260724 `
  --evitrail-root <Evitrial checkout at da4a29e> `
  --out F:\DATA_COLLECTION\evitrail_source_alignment_<version>\audit.json
```

Strict five-file handoff build:

```powershell
python scripts/build_evitrail_source_handoff.py `
  --raw-root <cti-rag>/data/raw `
  --processed-root <cti-rag>/data/processed/trail_multisource_part1_v1_20260724 `
  --output-dir F:\DATA_COLLECTION\evitrail_source_alignment_<version>\handoff `
  --work-dir F:\DATA_COLLECTION\evitrail_source_alignment_<version>\work
```

The builder writes exactly:

- `nodes.jsonl`
- `edges.jsonl`
- `events.jsonl`
- `source_claims.jsonl`
- `rejected_records.jsonl`

It streams records and outputs, and uses a disk-backed evidence/node index in
the caller-supplied work directory. Large runs must place both output and work
directories under `F:\DATA_COLLECTION`; the CLI rejects other destinations.

## Complete handoff validation

The final non-OTX handoff is:

`F:\DATA_COLLECTION\evitrail_source_alignment_20260730\handoff_v5`

The strict handoff directory contains only the five required JSONL files.
`validation.json` is deliberately outside it, at the package root:

`F:\DATA_COLLECTION\evitrail_source_alignment_20260730\validation_v5_agent.json`

| File | Lines | Bytes | SHA-256 |
|---|---:|---:|---|
| `events.jsonl` | 32,056 | 533,595,180 | `d47156a34d0ca58b63ce787672e0d929ab76b47177ccf8b8412f16e9c72ea40e` |
| `nodes.jsonl` | 493,734 | 69,964,436 | `870b5a89204149aa1883be7e6da6daef92d92c2ebb3455f7bb6a1fba5094f97c` |
| `edges.jsonl` | 603,602 | 321,465,317 | `b2d8f7f0b8453b4646f2800c7afe21b1b790f66a6d0031341e97bf10e77b1254` |
| `source_claims.jsonl` | 126,181 | 74,911,100 | `88073e0f56bec978f1fc677b5982af8b33a9ec8fd622af06e561ff78afbf9c19` |
| `rejected_records.jsonl` | 25,794 | 8,879,121 | `7f13f5cdc352ffe208801b40ad4a8707d141c82354a1fb8e201f855cf3e5c5fc` |

The exact current consumer at commit
`da4a29e8ce25cff8cbddebb444b069296f949511` read the complete handoff in
33.016 seconds:

- 32,056 Events: 29,340 ORKL, 1,855 CIRCL MISP, 689 APTnotes, 172 CISA;
- 520,489 indicator observations;
- 83,113 non-Event relations, including 18 MISP Object IP-to-ASN relations;
- 126,181 actor claims;
- 25,794 explicit rejected records.

The reader produced 520,489 + 83,113 = 603,602 edge observations, exactly the
number of input edge rows. Peak resident memory was 2,347,196,416 bytes
(2.186 GiB), from a 29,667,328-byte baseline. This complete non-OTX handoff was
therefore validated all at once; hosts with a tighter memory limit should run
source-separated packages sequentially rather than assuming a lower peak.

A real four-source, seven-stage current-pipeline smoke also passed using one
Event from each source. The portable-reference scan checked 787,633 reference
fields and found zero absolute filesystem paths.

## TDD record

Red failures were recorded before implementation for:

1. missing ORKL adapter;
2. unsupported MISP route;
3. unsupported APTnotes route;
4. unsupported CISA route and incorrect attachment promotion;
5. silent malformed-JSONL loss;
6. invalid URL ports aborting a source record;
7. consumer-invalid URL hostnames being admitted;
8. missing executable five-file orchestrator;
9. large-output CLI paths not constrained to `F:\DATA_COLLECTION`.

The green command above passes all ten source-alignment cases.

## Remaining boundaries

- This route deliberately does not add Malware, FileHash, Payload, or actor
  nodes.
- MITRE and Malpedia are not read as attribution sources.
- ORKL/APTnotes/CISA narrative actor candidates cannot vote on vocabulary
  unless the shared consumer policy is changed explicitly.
- MISP IP-to-ASN relations embedded in Object structure are produced by the
  dedicated raw MISP relation pass because the generic IOC-evidence sidecar
  does not encode that object pairing. The final handoff contains all 18 such
  relations found in the collected raw MISP objects.
- The generated handoff is the factual non-OTX base. ThreatFox, URLhaus, pDNS,
  VirusTotal, and OTX infrastructure remain separate enrichment inputs.
