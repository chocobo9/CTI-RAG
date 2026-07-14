# SNAPSHOT — OTX Event Discovery Acceptance (2026-07-10 / 4,160 calibration)

> Archive category: OTX acceptance snapshot.
>
> **Status: HISTORICAL ACCEPTANCE SNAPSHOT.** Current OTX population and authority
> start at `docs/OTX_DOC_STATUS.md`; do not reuse these counts as current.

## Scope

Frozen collection run:
`data/raw/otx_collection_runs/routeA_20260704_policy_small_first`.

This acceptance was fully offline. It made no OTX, indicator-endpoint,
enrichment, model-training, or GPU calls.

## Candidate Events

- Candidate manifest rows: 4,906 unique Pulse ids.
- Checkpoint discovered ids: 4,905.
- Manifest-only id: `69ae4cd6d5fd4f95eda29a25`.
- Checkpoint-only ids: none.
- Completed Pulse ids missing from the manifest: none.
- Manifest size: 6,530,464 bytes.

The manifest count is one higher than the checkpoint because the preserved
discovery log contains one valid discovery row that was not added to the
checkpoint. The manifest intentionally follows the evidence-bearing discovery
log rather than deleting that candidate.

## Source-Claim Artifacts

Output directory: `data/processed/otx_source_claims_routeA_20260704`.

| Artifact | Rows | Bytes |
|---|---:|---:|
| `events.jsonl` | 4,160 | 3,386,399 |
| `source_attribution_claims.jsonl` | 757 | 676,569 |
| `summary.json` | 1 object | 467 |

Status counts:

| Source-claim state | Events |
|---|---:|
| missing | 3,447 |
| resolved single | 342 |
| resolved multi-actor | 3 |
| resolved alias-collapsed | 4 |
| taxonomy ambiguous | 31 |
| parse ambiguous | 4 |
| unmapped actor-like | 284 |
| non-attributing | 45 |

## Contract Checks

- Event rows: 4,160.
- Unique Event source ids: 4,160.
- Summary counts match streamed Event rows.
- All claim rows reference retained Events.
- Multi-actor Events retained: 3.
- Ambiguous Events retained: 35.
- No confidence, belief, uncertainty, DST, Actor-IOC attribution,
  `AttributedTo`, pDNS, ASN, WHOIS, or VirusTotal fields were emitted.
- The builder loads the MITRE taxonomy once and processes one RawStore Pulse
  wrapper at a time.

## Verification

- OTX-related unit tests: 56 passed.
- Ruff on modified Python files: passed.
- BLAS/OpenMP thread counts were fixed to one during tests and construction.

The existing embedded-indicator Event-IOC path remains unchanged. Indicator
endpoint pagination and support enrichment are not required for this acceptance.
