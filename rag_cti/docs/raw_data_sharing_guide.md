# CTI-RAG Raw Data Sharing Guide

This package contains the raw collection layer for the CTI-RAG project. It can be
used independently from the RAG runtime. Consumers do not need Qdrant, Neo4j, or
LLM API keys if they only want to inspect or reuse the original collected data.

## What Is Included

Place the shared archive at the repository root so the directory layout is:

```text
data/raw/
```

The raw data directory currently contains these source groups:

```text
data/raw/mitre       MITRE ATT&CK raw STIX bundle and versioned raw records
data/raw/otx         AlienVault OTX pulse JSON records
data/raw/pdns        Passive DNS raw snapshots
data/raw/vt          VirusTotal raw snapshots
data/raw/whois       WHOIS raw snapshots, if collected
data/raw/pdfs        Raw PDF report files
data/raw/pdfs_bench  Additional PDF benchmark/report files
data/raw/pdf         PDF blob manifests
data/raw/blobs       Content-addressed PDF blobs, named by SHA-256
```

`data/raw/pdf` and `data/raw/blobs` belong together. The JSON files under
`data/raw/pdf` are manifests that point to binary PDF blobs by SHA-256. The blob
files have no extension because their filenames are content hashes.

## Current Local Inventory

At the time this guide was written, the local raw package had this approximate
size:

```text
data/raw total, including raw.zip: 732.76 MB
raw.zip inside data/raw:          233.10 MB
raw data excluding raw.zip:       499.66 MB
```

OTX:

```text
unique pulse_id:                    2,056
legacy root JSON:                   2,056 files
versioned RawStore JSON:            2,056 files
legacy and versioned ids:           exact same pulse_id set
indicator rows total:               413,512
modified range:                     2016-10-05 to 2026-05-27
checkpoint:                         2,056 ok, 1 error
processed/v5_staging/otx.jsonl:     2,072 chunks from 2,056 pulse_id values
```

This means the OTX raw directory contains two storage shapes for the same 2,056
pulses:

```text
data/raw/otx/<pulse_id>.json
data/raw/otx/<pulse_id>/<fetched_at>.json
```

The package is complete for the project's selected OTX pulse set. It is not a
complete dump of all AlienVault OTX.

VirusTotal:

```text
raw JSON files:                     1,097
unique VT keys:                     1,097
raw size:                           17.09 MB
bad JSON files:                     0
VT object type:                     domain: 1,097
VT data records:                    1,097
date range from VT attributes:      2018-09-07 to 2026-06-19
processed/v5_staging/vt.jsonl:      473 chunks
processed records with relations:   366
projected relations:                1,083
```

The VT collection is a selected domain-report set derived from the project's
indicator index, not a complete VirusTotal dump.

Passive DNS:

```text
raw JSON files:                     693
unique lookup keys:                 693
raw size:                           3.83 MB
bad JSON files:                     0
passive_dns rows total:             11,798
observed time range:                2013-03-31 to 2026-06-15
processed/v5_staging/pdns.jsonl:    693 chunks
processed records with relations:   542
projected relations:                18,851
```

The pDNS collection is a selected domain lookup set from the project's indicator
index using the OTX passive-DNS endpoint. It is not a complete passive-DNS feed.

## Important Notes

- Do not manually rename or delete files under `data/raw/blobs`; PDF manifests
  refer to those hashes.

## Packaging Command

Optional SHA-256 manifest:

```powershell
Get-ChildItem data\raw -Recurse -File |
  Get-FileHash -Algorithm SHA256 |
  Select-Object Path,Hash |
  Export-Csv raw_sha256_manifest.csv -NoTypeInformation
```

## How To Use The Raw Data Directly

The raw data is organized by source. Typical direct-use patterns:

- MITRE: parse the STIX bundle from `data/raw/mitre`.
- OTX: read pulse JSON records from `data/raw/otx`.
- pDNS: read passive DNS snapshots from `data/raw/pdns`.
- VirusTotal: read raw VT snapshots from `data/raw/vt`.
- WHOIS: read raw WHOIS snapshots from `data/raw/whois`, if present.
- PDFs: read PDF files from `data/raw/pdfs` or resolve manifests in
  `data/raw/pdf` to binary blobs in `data/raw/blobs`.

No project runtime is required for direct parsing. Python, jq, PowerShell, or any
JSON/PDF tooling is enough.

## Raw Collection And Refresh Scripts

The scripts below are the main raw-data collection or projection entry points.
Run them from the repository root with:

Some scripts require API keys in `.env` or environment variables.

### MITRE ATT&CK

```text
scripts/migrate_raw_store.py
```

Migrates older raw files into the versioned `data/raw/{source}/{source_id}/{fetched_at}.json`
layout.

```text
scripts/build_ontology_nodes.py
scripts/build_ontology_edges.py
```

Read the raw MITRE bundle and create ontology JSONL outputs. These are processed
artifacts, but they depend directly on `data/raw/mitre`.

```text
scripts/seed_mitre.py
scripts/seed_mitre_relationships.py
```

Read the raw MITRE bundle and create processed JSONL chunks. Use these only if
processed data is needed.

### AlienVault OTX

```text
scripts/refetch_otx_raw.py
```

Fetches or refreshes OTX raw pulse JSON into `data/raw/otx`. Requires an OTX API
key if the source endpoint is contacted.

```text
scripts/rebuild_otx_jsonl.py
```

Rebuilds processed OTX JSONL from the raw OTX store. This is optional unless a
consumer needs normalized chunks.

### Passive DNS

```text
scripts/refetch_pdns_raw.py
```

Fetches passive DNS raw snapshots into `data/raw/pdns`. Requires the configured
provider credentials.

```text
scripts/project_pdns.py
```

Projects raw pDNS snapshots into processed JSONL. Optional unless processed
chunks or relation-bearing records are needed.

### VirusTotal

```text
scripts/refetch_vt_raw.py
```

Fetches VirusTotal raw snapshots into `data/raw/vt`. Requires a VirusTotal API
key.

```text
scripts/project_vt.py
```

Projects raw VT snapshots into processed JSONL. Optional unless processed chunks
or relation-bearing records are needed.

### WHOIS

```text
scripts/refetch_whois_raw.py
```

Fetches WHOIS raw snapshots into `data/raw/whois`. Requires a Whoxy API key.

### PDFs

```text
scripts/fetch_pdfs.py
```

Downloads public CTI PDF reports into `data/raw/pdfs`.

```text
scripts/seed_pdfs.py
```

Reads PDF files and creates processed JSONL chunks. Optional unless a consumer
needs normalized text chunks.

The project also has a blob-backed PDF raw store:

```text
data/raw/pdf      manifest JSON
data/raw/blobs    binary PDF blobs by SHA-256
```

Those files should be copied together.

## Optional Processed Data Rebuild

If a teammate wants processed JSONL, run only the relevant source scripts. A full
local rebuild usually follows this shape:

```powershell
$env:PYTHONPATH="$PWD\src"

python scripts/build_ontology_nodes.py
python scripts/build_ontology_edges.py
python scripts/build_indicator_index.py
python scripts/rebuild_otx_jsonl.py
python scripts/seed_mitre.py
python scripts/seed_mitre_relationships.py
python scripts/seed_pdfs.py
python scripts/project_pdns.py
python scripts/project_vt.py
```

Graph facts are optional:

```powershell
python scripts/build_facts.py --processed-dir data/processed/v5_staging
```

This creates:

```text
data/processed/v5_staging/facts.jsonl
data/processed/v5_staging/supports.jsonl
```
