"""Data-only export from the stage-four JSONL graph to TRAIL's TKG layout.

This deliberately stops at the old pipeline's *data* boundary.  It does not
load weights, create labels, or invoke training/inference.  In particular,
the local data sources do not supply the APT labels used by the research
model, so every exported event has ``y == -1``.
"""

from __future__ import annotations

import builtins
import csv
import importlib
import json
import os
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import torch

TRAIL_TYPES = {"ips": 0, "urls": 1, "domains": 2, "ASN": 3, "EVENT": 4}
_NODE_TO_TRAIL = {"ip": "ips", "url": "urls", "domain": "domains", "asn": "ASN", "event": "EVENT"}
_FEATURE_TYPES = {"ips", "urls", "domains"}
_ALLOWED = {
    "event_contains_domain", "event_contains_ip", "event_contains_url", "domain_resolves_to_ip",
    "url_hosted_on_domain", "url_resolves_to_ip", "ip_in_asn",
}

# This is deliberately stored alongside each export.  It captures the actual
# old reader contract without asking a caller to infer it from the research
# pipeline's training scripts.
_LOADER_CONTRACT = {
    "consumer_source": "src/feature_extraction/neo_to_features.py and src/models/gnn.py",
    "graph_file": "full_graph_csr.pt",
    "graph_fields": {
        "x": "long node-type ID per homogeneous graph node",
        "edge_csr": "csr.CSR adjacency; relations are materialized in both directions",
        "feat_map": "feature-row ID for ips/urls/domains; -1 for ASN/EVENT",
        "ntypes": "{'ips': 0, 'urls': 1, 'domains': 2, 'ASN': 3, 'EVENT': 4}",
        "event_ids": "homogeneous node IDs whose x value is EVENT",
        "y": "event-aligned labels; this data-only export uses -1 for every event",
        "sources": "event-aligned source IDs with src_map reverse mapping",
        "node_names": "Stage-4 node ID to homogeneous graph node ID",
    },
    "feature_files": ["ips.csv", "domains.csv", "urls.csv"],
    "stage4_node_mapping": _NODE_TO_TRAIL,
    "accepted_stage4_relations": sorted(_ALLOWED),
    "label_policy": "No labels are manufactured from source, actor, or adversary claims.",
    "scope": "data export and loader smoke only; no weights, training, inference, or evaluation",
}


def export_trail_tkg(stage4_dir: Path, output_dir: Path, trail_root: Path) -> dict[str, Any]:
    """Export one Stage-4 JSONL package to files consumed by old TRAIL.

    ``trail_root`` is the checked-out TRAIL directory containing ``src``.  It
    is explicit so that the exact feature rules and CSR implementation are
    those shipped with the old pipeline, rather than a reimplementation.
    """
    stage4_dir, output_dir, trail_root = map(Path, (stage4_dir, output_dir, trail_root))
    if output_dir.exists():
        raise FileExistsError(f"refusing to mix export runs in existing directory: {output_dir}")
    nodes = _read_jsonl(stage4_dir / "nodes.jsonl")
    edges = _read_jsonl(stage4_dir / "edges.jsonl")
    events = {row["event_id"]: row for row in _read_jsonl(stage4_dir / "events.jsonl")}
    node_by_id = {row["node_id"]: row for row in nodes}
    if len(node_by_id) != len(nodes):
        raise ValueError("stage-four nodes.jsonl contains duplicate node_id values")

    trail_src = trail_root / "src"
    if not (trail_src / "csr.py").is_file():
        raise FileNotFoundError(f"not a TRAIL source directory: {trail_src}")
    # The original code serializes csr.CSR.  Keep that module name so an old
    # pipeline run from TRAIL/src can unpickle this data object.
    sys.path.insert(0, str(trail_src))
    try:
        csr_class = importlib.import_module("csr").CSR
        ip = importlib.import_module("feature_extraction.ip")
        domain = importlib.import_module("feature_extraction.domain")
        url = importlib.import_module("feature_extraction.url")
    finally:
        sys.path.pop(0)

    ordered = sorted(nodes, key=lambda row: (TRAIL_TYPES[_NODE_TO_TRAIL[row["type"]]], row["node_id"]))
    gid = {row["node_id"]: index for index, row in enumerate(ordered)}
    x = torch.tensor([TRAIL_TYPES[_NODE_TO_TRAIL[row["type"]]] for row in ordered], dtype=torch.long)
    feat_map = torch.full((len(ordered),), -1, dtype=torch.long)
    feature_rows: dict[str, list[dict[str, Any]]] = {kind: [] for kind in _FEATURE_TYPES}
    for index, row in enumerate(ordered):
        kind = _NODE_TO_TRAIL[row["type"]]
        if kind in _FEATURE_TYPES:
            feat_map[index] = len(feature_rows[kind])
            feature_rows[kind].append(row)

    output_dir.mkdir(parents=True)
    _write_features(output_dir / "ips.csv", feature_rows["ips"], ip.extract)
    _write_features(output_dir / "domains.csv", feature_rows["domains"], domain.extract)
    _write_features(output_dir / "urls.csv", feature_rows["urls"], url.extract)

    edge_pairs: set[tuple[int, int]] = set()
    excluded = Counter()
    for edge in edges:
        relation = edge.get("relation")
        source, target = edge.get("source_id"), edge.get("target_id")
        if relation not in _ALLOWED:
            excluded[str(relation)] += 1
            continue
        if source not in gid or target not in gid:
            raise ValueError(f"edge refers to unknown node: {edge.get('edge_id')}")
        # TRAIL's graph construction makes every permitted relation undirected.
        edge_pairs.add((gid[source], gid[target]))
        edge_pairs.add((gid[target], gid[source]))
    edge_index = torch.tensor(sorted(edge_pairs), dtype=torch.long).T if edge_pairs else torch.empty((2, 0), dtype=torch.long)
    event_ids = torch.tensor([gid[row["node_id"]] for row in ordered if row["type"] == "event"], dtype=torch.long)
    event_id_by_gid = {gid[row["node_id"]]: row["node_id"] for row in ordered if row["type"] == "event"}
    source_names = sorted({events[event_id_by_gid[event_gid]].get("source", "unknown") for event_gid in event_ids.tolist()})
    src_map = {name: index for index, name in enumerate(source_names)}
    sources = torch.tensor([src_map[events[event_id_by_gid[event_gid]].get("source", "unknown")] for event_gid in event_ids.tolist()], dtype=torch.long)
    graph = SimpleNamespace(
        x=x, edge_csr=csr_class(edge_index), feat_map=feat_map, ntypes=TRAIL_TYPES,
        type_dict=TRAIL_TYPES, event_ids=event_ids,
        # No source attribution is converted into a model target.
        y=torch.full((len(event_ids),), -1, dtype=torch.long), label_map={},
        sources=sources, src_map=src_map,
        node_names={row["node_id"]: gid[row["node_id"]] for row in ordered},
    )
    torch.save(graph, output_dir / "full_graph_csr.pt")
    (output_dir / "legacy_loader_contract.json").write_text(
        json.dumps(_LOADER_CONTRACT, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / "event_timestamp_map.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_node_id", "event_id", "event_time"])
        writer.writeheader()
        for event_gid in event_ids.tolist():
            event_id = event_id_by_gid[event_gid]
            writer.writerow({"event_node_id": event_gid, "event_id": event_id, "event_time": events[event_id].get("event_time") or ""})
    report = {
        "format": "trail-data-export", "format_version": 1,
        "input_stage4_dir": str(stage4_dir), "old_trail_root": str(trail_root),
        "node_count": len(ordered), "edge_count_directed": len(edge_pairs),
        "event_count": len(event_ids), "feature_row_counts": {key: len(value) for key, value in feature_rows.items()},
        "excluded_stage4_relations": dict(sorted(excluded.items())),
        "labels": "all -1; no source attribution was turned into an APT label",
    }
    (output_dir / "export_manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def validate_trail_tkg(export_dir: Path, trail_root: Path) -> dict[str, Any]:
    """Check the old TRAIL data contract in a fresh process, without models.

    The probe deliberately reuses the old feature CSV parser, column order,
    and dense-feature conversion rules, but does not construct
    ``FeatureSampler``: that class creates trainable ``nn.Linear`` layers and
    would exceed this exporter's data-only boundary.
    """
    export_dir, trail_root = Path(export_dir), Path(trail_root)
    trail_src = trail_root / "src"
    probe = """
import csv, json
import pandas as pd
import torch
from feature_extraction import ip, domain, url
from feature_extraction.utils import order_df_cols

g = torch.load(r'''{graph}''', weights_only=False)
feature_dir = r'''{features}'''
if g.x.numel() != g.feat_map.numel() or g.edge_csr.ptr.numel() != g.x.numel() + 1:
    raise ValueError('TRAIL graph cardinalities are inconsistent')
if g.edge_csr.ptr[0].item() != 0 or g.edge_csr.ptr[-1].item() != g.edge_csr.idx.numel():
    raise ValueError('TRAIL CSR pointers do not cover the adjacency index')
if not torch.all(g.edge_csr.ptr[1:] >= g.edge_csr.ptr[:-1]):
    raise ValueError('TRAIL CSR pointers are not monotonic')
if not torch.all(g.y == -1):
    raise ValueError('export must not manufacture APT labels')
if g.y.numel() != g.event_ids.numel() or g.label_map:
    raise ValueError('event label fields do not represent an unlabeled export')

specs = {{
    'ips': (ip, ip.COL_ORDER),
    'domains': (domain, domain.COL_ORDER),
    'urls': (url, url.COL_ORDER),
}}
feature_rows = {{}}
feature_sizes = {{}}
for name, (module, col_order) in specs.items():
    dataframe = order_df_cols(pd.read_csv(feature_dir + '/' + name + '.csv', sep='\\t'), col_order)
    gids = torch.nonzero(g.x == g.ntypes[name], as_tuple=False).flatten()
    mapped = g.feat_map[gids]
    if dataframe.shape[0] != gids.numel() or mapped.numel() != gids.numel():
        raise ValueError('feature CSV row count does not match ' + name + ' nodes')
    if sorted(mapped.tolist()) != list(range(dataframe.shape[0])):
        raise ValueError('feat_map is not a contiguous row mapping for ' + name)
    # This invokes TRAIL's existing feature converter only; no neural module
    # or parameters are constructed.
    feature_sizes[name] = int(module.to_dense_gnn(dataframe.iloc[:1])[0].shape[1])
    feature_rows[name] = int(dataframe.shape[0])

non_feature = (g.x == g.ntypes['ASN']) | (g.x == g.ntypes['EVENT'])
if not torch.all(g.feat_map[non_feature] == -1):
    raise ValueError('ASN or EVENT node unexpectedly points at an IOC feature row')
expected_events = torch.nonzero(g.x == g.ntypes['EVENT'], as_tuple=False).flatten()
if not torch.equal(g.event_ids, expected_events):
    raise ValueError('event_ids does not exactly enumerate EVENT node IDs')
inverse_names = {{value: key for key, value in g.node_names.items()}}
with open(feature_dir + '/event_timestamp_map.csv', newline='', encoding='utf-8') as handle:
    timestamps = list(csv.DictReader(handle))
if len(timestamps) != g.event_ids.numel():
    raise ValueError('event timestamp map row count does not match event_ids')
timestamp_ids = set()
for row in timestamps:
    node_id = int(row['event_node_id'])
    if node_id in timestamp_ids or node_id not in inverse_names or row['event_id'] != inverse_names[node_id]:
        raise ValueError('event timestamp map does not reproduce graph event IDs')
    timestamp_ids.add(node_id)
if timestamp_ids != set(g.event_ids.tolist()):
    raise ValueError('event timestamp map does not cover every event node')
print(json.dumps({{'status': 'passed', 'node_count': int(g.x.numel()), 'edge_count_directed': int(g.edge_csr.idx.numel()), 'event_count': int(g.event_ids.numel()), 'feature_row_counts': feature_rows, 'feature_sizes': feature_sizes}}))
""".format(graph=(export_dir / "full_graph_csr.pt").resolve(), features=export_dir.resolve())
    env = os.environ.copy()
    # The pinned TRAIL helper files are UTF-8 but its source omits encoding.
    # This is a launch setting for the unmodified old reader, not a data change.
    env["PYTHONUTF8"] = "1"
    result = subprocess.run([sys.executable, "-c", probe], cwd=trail_src, env=env, text=True, capture_output=True, check=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_features(path: Path, rows: list[dict[str, Any]], extractor: Any) -> None:
    # The source snapshots have no enrichment fields (geo, WHOIS, HTTP, ...).
    # Calling TRAIL's own lexical/sparse extractors creates only those features
    # derivable from the IOC string; unavailable enrichment remains null/zero.
    import pandas as pd
    if rows:
        # TRAIL's helper files are UTF-8, while its original ``open`` calls do
        # not specify an encoding.  On Windows that otherwise depends on the
        # active ANSI code page and can fail before feature extraction starts.
        with _utf8_default_open():
            dataframe = extractor([{"ioc": row["value"]} for row in rows])
    else:
        dataframe = pd.DataFrame()
    dataframe.to_csv(path, sep="\t", index=False)


@contextmanager
def _utf8_default_open():
    original = builtins.open

    def open_utf8(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if "b" not in mode and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
        return original(file, mode, *args, **kwargs)

    builtins.open = open_utf8
    try:
        yield
    finally:
        builtins.open = original
