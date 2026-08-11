"""Append Stage-4 five-node source graphs to the paper TRAIL graph."""

from __future__ import annotations

import csv
import importlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import torch

_TYPE = {"ip": "ips", "url": "urls", "domain": "domains", "asn": "ASN", "event": "EVENT"}


def _coerce_numeric_feature_frame(
    dataframe: pd.DataFrame, *, identifier_columns: set[str]
) -> pd.DataFrame:
    normalized = dataframe.copy()
    for column in normalized.columns:
        if column in identifier_columns:
            continue
        if pd.api.types.is_bool_dtype(normalized[column].dtype):
            normalized[column] = normalized[column].astype("int8")
    return normalized


def merge_trail_graphs(
    baseline_dir: Path,
    source_graph_dirs: list[Path],
    output_dir: Path,
    trail_root: Path,
) -> dict[str, Any]:
    baseline_dir, output_dir, trail_root = map(Path, (baseline_dir, output_dir, trail_root))
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    trail_src = trail_root / "src"
    sys.path.insert(0, str(trail_src))
    try:
        importlib.import_module("csr")
        extractors = {
            "ips": importlib.import_module("feature_extraction.ip").extract,
            "domains": importlib.import_module("feature_extraction.domain").extract,
            "urls": importlib.import_module("feature_extraction.url").extract,
        }
        graph = torch.load(
            baseline_dir / "full_graph_csr.pt", weights_only=False, map_location="cpu"
        )
    finally:
        sys.path.pop(0)

    feature_files = {"ips": "ips.csv", "domains": "domains.csv", "urls": "urls.csv"}
    baseline_lookup: dict[tuple[str, str], int] = {}
    feature_counts: dict[str, int] = {}
    for kind, filename in feature_files.items():
        shutil.copy2(baseline_dir / filename, output_dir / filename)
        gids = torch.nonzero(graph.x == graph.type_dict[kind], as_tuple=False).flatten()
        mapped = graph.feat_map[gids]
        count = int(mapped.max().item()) + 1 if mapped.numel() else 0
        feature_counts[kind] = count
        row_to_gid = torch.full((count,), -1, dtype=torch.long)
        row_to_gid[mapped] = gids
        values = pd.read_csv(baseline_dir / filename, sep="\t", usecols=["ioc"])["ioc"]
        for row_index, value in enumerate(values.astype(str)):
            baseline_lookup.setdefault((kind, value.casefold()), int(row_to_gid[row_index]))

    x_append: list[int] = []
    feat_append: list[int] = []
    new_feature_values: dict[str, list[str]] = {kind: [] for kind in feature_files}
    stage_gid: dict[str, int] = {}
    added_edges: set[tuple[int, int]] = set()
    new_events: list[dict[str, Any]] = []
    next_gid = int(graph.x.numel())
    src_map = dict(graph.src_map)

    for source_dir in source_graph_dirs:
        nodes = _read_jsonl(source_dir / "nodes.jsonl")
        edges = _read_jsonl(source_dir / "edges.jsonl")
        events = {row["event_id"]: row for row in _read_jsonl(source_dir / "events.jsonl")}
        for node in nodes:
            node_id, node_type, value = node["node_id"], node["type"], str(node["value"])
            kind = _TYPE[node_type]
            if node_type != "event" and kind in feature_files:
                existing = baseline_lookup.get((kind, value.casefold()))
                if existing is not None:
                    stage_gid[node_id] = existing
                    continue
            if node_id in stage_gid:
                continue
            gid = next_gid
            next_gid += 1
            stage_gid[node_id] = gid
            x_append.append(graph.type_dict[kind])
            if kind in feature_files:
                row_index = feature_counts[kind] + len(new_feature_values[kind])
                feat_append.append(row_index)
                new_feature_values[kind].append(value)
                baseline_lookup[(kind, value.casefold())] = gid
            else:
                feat_append.append(-1)
            graph.node_names[node_id] = gid
            if node_type == "event":
                event = events[node_id]
                source = event.get("source", "unknown")
                if source not in src_map:
                    src_map[source] = len(src_map)
                new_events.append(
                    {
                        "gid": gid,
                        "event_id": node_id,
                        "event_time": event.get("event_time"),
                        "source": source,
                    }
                )
        for edge in edges:
            source, target = stage_gid[edge["source_id"]], stage_gid[edge["target_id"]]
            added_edges.add((source, target))
            added_edges.add((target, source))

    if x_append:
        graph.x = torch.cat([graph.x, torch.tensor(x_append, dtype=graph.x.dtype)])
        graph.feat_map = torch.cat(
            [graph.feat_map, torch.tensor(feat_append, dtype=graph.feat_map.dtype)]
        )
    if new_events:
        graph.event_ids = torch.cat(
            [graph.event_ids, torch.tensor([row["gid"] for row in new_events], dtype=torch.long)]
        )
        graph.y = torch.cat([graph.y, torch.full((len(new_events),), -1, dtype=graph.y.dtype)])
        graph.sources = torch.cat(
            [
                graph.sources,
                torch.tensor([src_map[row["source"]] for row in new_events], dtype=graph.sources.dtype),
            ]
        )
        graph.src_map = src_map

    base_counts = graph.edge_csr.ptr[1:] - graph.edge_csr.ptr[:-1]
    base_src = torch.repeat_interleave(torch.arange(base_counts.numel()), base_counts)
    if added_edges:
        extra = torch.tensor(sorted(added_edges), dtype=torch.long).T
        src = torch.cat([base_src, extra[0]])
        dst = torch.cat([graph.edge_csr.idx, extra[1]])
    else:
        src, dst = base_src, graph.edge_csr.idx
    order = torch.argsort(src)
    src, dst = src[order], dst[order]
    counts = torch.bincount(src, minlength=graph.x.numel())
    graph.edge_csr.idx = dst
    graph.edge_csr.ptr = torch.cat([torch.zeros(1, dtype=torch.long), counts.cumsum(0)])
    torch.save(graph, output_dir / "full_graph_csr.pt")

    for kind, values in new_feature_values.items():
        if not values:
            continue
        dataframe = extractors[kind]([{"ioc": value} for value in values])
        dataframe["ioc"] = values
        if kind == "domains":
            # The released domain feature table represents flags as 0/1,
            # whereas its extractor returns Python booleans.  Mixing both
            # encodings makes pandas load the merged column as strings and the
            # official model then fails to cast the feature matrix to float.
            dataframe = _coerce_numeric_feature_frame(
                dataframe, identifier_columns={"ioc"}
            )
        path = output_dir / feature_files[kind]
        columns = list(pd.read_csv(path, sep="\t", nrows=0).columns)
        if columns and columns[0].startswith("Unnamed:"):
            dataframe.insert(0, columns[0], range(feature_counts[kind], feature_counts[kind] + len(values)))
        dataframe = dataframe.reindex(columns=columns)
        dataframe.to_csv(path, sep="\t", index=False, header=False, mode="a")

    timestamp_path = output_dir / "event_timestamp_map.csv"
    shutil.copy2(baseline_dir / "event_timestamp_map.csv", timestamp_path)
    with timestamp_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        start = int(graph.event_ids.numel()) - len(new_events)
        for offset, event in enumerate(new_events):
            writer.writerow(
                [start + offset, event["gid"], "", event["event_id"], event["event_time"] or "", "", event["source"]]
            )
    manifest = {
        "format": "trail-baseline-incremental-merge",
        "baseline_dir": str(baseline_dir),
        "source_graph_dirs": [str(path) for path in source_graph_dirs],
        "baseline_indices_preserved": True,
        "new_event_count": len(new_events),
        "new_node_count": len(x_append),
        "new_directed_edge_count": len(added_edges),
    }
    (output_dir / "merge_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
