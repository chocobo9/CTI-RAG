# Raw MITRE OTX Collection Pipeline

This is a separate raw-only pipeline. It does not modify or use
`archive/old_pipeline/collect_otx.py`.

It collects raw OTX evidence for MITRE ATT&CK intrusion-set actors and aliases.
Default date window:

```text
2018-01-01 <= pulse.created < 2023-01-01
```

## 1. Build Query Shards

Run from the project root:

```powershell
python archive\old_pipeline\raw_otx_mitre\build_mitre_query_shards.py
```

This writes:

```text
data/raw_otx_mitre/seeds/mitre_actors.json
data/raw_otx_mitre/seeds/mitre_actor_aliases.json
data/raw_otx_mitre/seeds/query_shard_00.json
data/raw_otx_mitre/seeds/query_shard_01.json
data/raw_otx_mitre/seeds/query_shard_02.json
data/raw_otx_mitre/seeds/query_shard_03.json
data/raw_otx_mitre/seeds/query_manifest.json
```

## 2. Set OTX API Key

Single key:

```powershell
$env:OTX_API_KEY="your_key_here"
```

Multiple keys:

```powershell
$env:OTX_API_KEYS="key1,key2,key3"
```

## 3. Run Four Downloaders In Parallel

Open four terminals and run one command in each:

```powershell
python archive\old_pipeline\raw_otx_mitre\download_otx_raw_mitre_part_00.py
```

```powershell
python archive\old_pipeline\raw_otx_mitre\download_otx_raw_mitre_part_01.py
```

```powershell
python archive\old_pipeline\raw_otx_mitre\download_otx_raw_mitre_part_02.py
```

```powershell
python archive\old_pipeline\raw_otx_mitre\download_otx_raw_mitre_part_03.py
```

To override the date window:

```powershell
python archive\old_pipeline\raw_otx_mitre\download_otx_raw_mitre_part_00.py --since 2018-01-01 --until 2023-01-01
```

Each part writes to:

```text
data/raw_otx_mitre/part_00/
data/raw_otx_mitre/part_01/
data/raw_otx_mitre/part_02/
data/raw_otx_mitre/part_03/
```

Each part has its own:

```text
search/
pulses/
indicators/
metadata/
checkpoint.json
download.log
```

Re-running a part resumes from its checkpoint.

## 4. Merge

After all four parts finish:

```powershell
python archive\old_pipeline\raw_otx_mitre\merge_otx_raw_mitre_parts.py
```

Merged output:

```text
data/raw_otx_mitre/merged/pulses/<pulse_id>.json
data/raw_otx_mitre/merged/indicators/<pulse_id>.json
data/raw_otx_mitre/merged/by_actor/<actor_name>.json
data/raw_otx_mitre/merged/metadata/
```

The `by_actor` files are indexes only. They do not duplicate raw OTX JSON.
