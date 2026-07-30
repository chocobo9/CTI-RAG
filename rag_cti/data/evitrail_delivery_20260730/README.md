# EviTRAIL runnable delivery — ready subset

Consumer revision:
`Mitraaaaa/Evitrial@da4a29e8ce25cff8cbddebb444b069296f949511`

This directory contains the currently completed data artifacts. The generation
and validation code is in `src/rag_cti/evitrail_delivery/` and `scripts/`.

## Non-OTX factual base

`non_otx_handoff/` is a strict five-file handoff for APTnotes, CIRCL MISP,
CISA, and ORKL. It contains 32,056 Events and is directly accepted by the
current `read_handoff()`. Exact-reader and four-source pipeline results are in
`non_otx_validation.json`.

Run from the EviTRAIL checkout:

```powershell
python -m evitrail.data.pipeline `
  --handoff <CTI-RAG>\rag_cti\data\evitrail_delivery_20260730\non_otx_handoff `
  --raw-root __disabled__ `
  --enrichment none `
  --out <output>\non_otx_base
```

Rebuild from collected CTI-RAG inputs:

```powershell
python scripts/build_evitrail_source_handoff.py `
  --raw-root <CTI-RAG>\rag_cti\data\raw `
  --processed-root <CTI-RAG>\rag_cti\data\processed\trail_multisource_part1_v1_20260724 `
  --output-dir F:\DATA_COLLECTION\<version>\handoff `
  --work-dir F:\DATA_COLLECTION\<version>\work
```

Validate the rebuilt handoff:

```powershell
python scripts/validate_evitrail_source_handoff.py `
  --handoff F:\DATA_COLLECTION\<version>\handoff `
  --evitrail-root <EviTRAIL checkout at da4a29e> `
  --out F:\DATA_COLLECTION\<version>\validation.json
```

## Existing OTX enrichment inventory

`otx_enrichment_4505_v1/otx_enrichment.jsonl` contains 529,782 normalized
cached-infrastructure observations. Its exact current-reader validation is in
the same directory.

The inventory is complete for the existing 25,985-task terminal ledger derived
from the previously selected 4,505-Pulse population. It is not enrichment
coverage of the latest 17,454-Pulse snapshot. See `manifest.json` for the
explicit partial-scope declaration.

The normalization command is:

```powershell
python scripts/normalize_evitrail_otx_enrichment.py `
  --ledger <terminal-state-ledger.jsonl> `
  --output F:\DATA_COLLECTION\<version>\otx_enrichment.jsonl `
  --manifest F:\DATA_COLLECTION\<version>\manifest.json `
  --evitrail-root <EviTRAIL checkout at da4a29e> `
  --subset-pulse-count 4505 `
  --snapshot-pulse-count 17454
```

The latest 17,454-Pulse OTX factual base and its final global vocabulary are
separate in-progress deliverables.

