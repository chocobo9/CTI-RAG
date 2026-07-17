#!/usr/bin/env python3
"""
predict_paper_server.py
=======================

FastAPI server that serves predictions from the *TRAIL paper's* GNN
(the one trained by trail/src/train_gnn.py on TRAIL's original dataset).

Two endpoints:

  POST /predict_event
    Body: {"event_id": <node_id>}
    Predicts on an event already present in the loaded TKG.
    (Validates the pipeline end-to-end, no enrichment needed.)

  POST /attribute
    Body: {"iocs": [{"type":"domain","value":"..."}, ...]}
    Enriches each IOC, inserts a temporary event node connected to those
    IOCs, runs GNN inference, returns:
      - predicted_apt + confidence
      - per-APT scores (22-way softmax)
      - tiered: tier3 (named actor), tier2 (nation state), tier1 (assessment)

Caveats
-------
* Domain/URL enrichment uses `dig` + lexical features only. No passive-DNS
  expansion (would require an OTX call per IOC).
* IP enrichment skips GeoIP/ASN — the paper's `ips.csv` is mostly empty
  one-hots with no lat/long anyway.
* Each /attribute call grows the in-memory graph slightly; restart server
  to reset.

Run:
    python3 -m uvicorn predict_paper_server:app --host 0.0.0.0 --port 47823
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys
from typing import Optional
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# All paths are anchored to this script's directory so the server runs the
# same regardless of the caller's CWD. Override individual paths with env
# vars (TRAIL_DIR, GRAPH_PATH, WEIGHTS_DIR) if your layout differs.
ROOT = os.path.dirname(os.path.abspath(__file__))

TRAIL_DIR = os.environ.get("TRAIL_DIR", os.path.join(ROOT, "trail"))
TRAIL_SRC = os.path.join(TRAIL_DIR, "src")
sys.path.insert(0, TRAIL_SRC)

# Both inference modes run over the timestamped TKG (same graph structure
# the paper baseline was trained on, plus timestamp annotations the model
# ignores). This means USE_PAPER_BASELINE=1 works without needing to ship
# the second 680MB un-timestamped graph. The same pattern used in
# sandbox/year_drop/infer_neo4j.py.
USE_PAPER_BASELINE = os.environ.get("USE_PAPER_BASELINE", "0") == "1"

# Try the timestamped TKG first; if it isn't there but the original is, use
# that. Either works for both inference modes.
_DATA_TS = os.path.join(TRAIL_DIR, "TKG_data", "otx_dataset_timestamped")
_DATA_ORIG = os.path.join(TRAIL_DIR, "TKG_data", "otx_dataset")
DATA_DIR = _DATA_TS if os.path.isdir(_DATA_TS) else _DATA_ORIG
GRAPH_PATH = os.environ.get(
    "GRAPH_PATH", os.path.join(DATA_DIR, "full_graph_csr.pt")
)

if USE_PAPER_BASELINE:
    WEIGHTS_DIR = os.environ.get(
        "WEIGHTS_DIR", os.path.join(TRAIL_DIR, "src", "weights", "2-layer")
    )
    WEIGHTS_PATHS = [os.path.join(
        WEIGHTS_DIR, "gnn_train-0.777_max_lprop+feats+ae-new-data.pt",
    )]
else:
    WEIGHTS_DIR = os.environ.get(
        "WEIGHTS_DIR", os.path.join(ROOT, "sandbox", "year_drop", "B", "weights")
    )
    WEIGHTS_PATHS = [os.path.join(WEIGHTS_DIR, f"fold{i}.pt") for i in range(5)]


def _preflight() -> None:
    """Fail fast at import time with a precise, actionable message."""
    problems = []
    if not os.path.isdir(TRAIL_SRC):
        problems.append(
            f"  - TRAIL source not found at {TRAIL_SRC}\n"
            f"    Fix: clone https://github.com/cybermonic/trail into\n"
            f"    {TRAIL_DIR}, or set TRAIL_DIR=<path> in your environment.\n"
            f"    Or run ./setup.sh from the project root."
        )
    if not os.path.exists(GRAPH_PATH):
        problems.append(
            f"  - TKG graph not found at {GRAPH_PATH}\n"
            f"    Fix: download TKG.zip from the TRAIL repo README and unpack\n"
            f"    into {os.path.dirname(GRAPH_PATH)}/, or set GRAPH_PATH=<path>.\n"
            f"    Or run ./setup.sh."
        )
    missing_w = [p for p in WEIGHTS_PATHS if not os.path.exists(p)]
    if missing_w and len(missing_w) == len(WEIGHTS_PATHS):
        problems.append(
            f"  - No model checkpoints found in {WEIGHTS_DIR}\n"
            f"    Expected: " + ", ".join(os.path.basename(p) for p in WEIGHTS_PATHS) + "\n"
            f"    Fix: place fold0.pt..fold4.pt in {WEIGHTS_DIR},\n"
            f"    set WEIGHTS_DIR=<path>, or set USE_PAPER_BASELINE=1 to use the\n"
            f"    paper authors' single-fold checkpoint instead."
        )
    if problems:
        sys.stderr.write(
            "\n[predict_paper_server] cannot start — missing required files:\n\n"
            + "\n\n".join(problems)
            + "\n\nSee README.md → 'Serve Single-IOC Attribution' for setup.\n\n"
        )
        raise SystemExit(2)


_preflight()

from models.gnn import SageClassifier  # noqa: E402
from feature_extraction import domain as fdomain  # noqa: E402
from feature_extraction import url as furl  # noqa: E402

# APT -> nation-state attribution (public consensus)
APT_TO_NATION = {
    "APT28": "Russia", "APT29": "Russia", "TURLA": "Russia", "BLACKENERGY": "Russia",
    "APT34": "Iran", "APT35": "Iran", "MUDDYWATER": "Iran",
    "APT37": "North Korea", "APT38": "North Korea", "KIMSUKY": "North Korea",
    "APT41": "China", "APT27": "China", "MUSTANG PANDA": "China",
    "TA511": "Criminal", "TA551": "Criminal", "COBALT GROUP": "Criminal",
    "FIN7": "Criminal", "FIN11": "Criminal", "GOLD WATERFALL": "Criminal",
    "TEAMTNT": "Criminal", "MAGECART": "Criminal",
    "MOLERATS": "Palestine",
}


# ------------------------------------------------------------------ #
#  Lightweight in-process state                                      #
# ------------------------------------------------------------------ #
state: dict = {}


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def dig_record_counts(domain: str, timeout: float = 3.0) -> dict[str, int]:
    """Return {record_type: count} for a domain via local `dig`."""
    counts = {r: 0 for r in fdomain.RECORD_TYPES}
    nxdomain = False
    for rtype in counts:
        try:
            out = subprocess.run(
                ["dig", "+short", "+time=2", "+tries=1", domain, rtype],
                capture_output=True, text=True, timeout=timeout,
            )
            if out.returncode == 0:
                lines = [ln for ln in out.stdout.strip().split("\n") if ln]
                counts[rtype] = len(lines)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    # NXDOMAIN: if A and AAAA both empty and SOA exists at parent, treat as 0
    # (dig returns nothing for both happens for live-but-empty too, so this is
    # a heuristic, not authoritative)
    try:
        out = subprocess.run(
            ["dig", "+short", domain, "A"],
            capture_output=True, text=True, timeout=timeout,
        )
        if "NXDOMAIN" in (out.stderr or "") + (out.stdout or ""):
            nxdomain = True
    except Exception:
        pass
    counts["has_nxdomain"] = int(nxdomain)
    return counts


def build_domain_row(domain_str: str) -> dict:
    """Build a single domain row matching trail/src/feature_extraction/domain.COL_ORDER."""
    counts = dig_record_counts(domain_str)
    parts = domain_str.split(".")
    tld = parts[-1].upper() if parts else ""
    row = {col: 0 for col in fdomain.COL_ORDER if col not in ("apt",)}
    row["ioc"] = domain_str
    row["domain_entropy"] = shannon_entropy(domain_str)
    row["domain_length"] = len(domain_str)
    row["num_digits"] = sum(c.isdigit() for c in domain_str)
    row["subdomains"] = max(len(parts) - 2, 0)
    row["has_nxdomain"] = counts.get("has_nxdomain", 0)
    if tld in row:
        row[tld] = 1.0
    for r in fdomain.RECORD_TYPES:
        row[r] = float(counts.get(r, 0))
    row["first_seen"] = 0.0
    row["last_seen"] = 0.0
    return row


def build_ip_row(ip_str: str) -> dict:
    """ips.csv columns: ['one_hot', 'ioc', 'latitude', 'longitude'] (+ 'apt')."""
    return {"one_hot": "[]", "ioc": ip_str, "latitude": np.nan, "longitude": np.nan}


def build_url_row(url_str: str) -> dict:
    """urls.csv columns from furl.COL_ORDER, plus 'ioc'."""
    parsed = urlparse(url_str)
    host = parsed.hostname or ""
    parts = host.split(".") if host else []
    tld = parts[-1].upper() if parts else ""

    row = {col: False for col in furl.COL_ORDER if col != "apt"}
    row["one_hot"] = "[]"
    row["ioc"] = url_str
    row["url_entropy"] = shannon_entropy(url_str)
    row["url_path_entropy"] = shannon_entropy(parsed.path or "")
    row["url_length"] = len(url_str)
    row["num_periods"] = url_str.count(".")
    row["num_subdir"] = parsed.path.count("/") if parsed.path else 0
    row["num_digits"] = sum(c.isdigit() for c in url_str)
    row["num_frag"] = 1 if parsed.fragment else 0
    row["num_params"] = url_str.count("&") + (1 if parsed.query else 0)
    row["url_path_length"] = len(parsed.path or "")
    row["url_host_length"] = len(host)
    row["has_port"] = bool(parsed.port)
    row["expiration"] = ""
    if tld in row:
        row[tld] = True
    return row


# ------------------------------------------------------------------ #
#  Graph + model load                                                #
# ------------------------------------------------------------------ #
def load_everything():
    print(f"[load] graph: {GRAPH_PATH}")
    g = torch.load(GRAPH_PATH, weights_only=False)
    print(f"        events={g.event_ids.size(0)}  nodes={g.x.size(0)}  classes={int(g.y.max())+1}")

    models = []
    for wp in WEIGHTS_PATHS:
        if not os.path.exists(wp):
            print(f"  [skip] missing checkpoint: {wp}")
            continue
        print(f"[load] checkpoint: {wp}")
        sd, args, kwargs = torch.load(wp, weights_only=False)
        # The model's data_dir is path-relative-to-`models/`. Use absolute.
        args = (os.path.abspath(DATA_DIR),) + args[1:]
        kwargs = dict(kwargs)
        kwargs["class_weights"] = None
        sd.pop("criterion.weight", None)
        m = SageClassifier(*args, **kwargs)
        missing, unexpected = m.load_state_dict(sd, strict=False)
        if unexpected:
            print(f"  [warn] unexpected keys: {unexpected[:5]}{'...' if len(unexpected)>5 else ''}")
        m.eval()
        models.append(m)
    if not models:
        raise RuntimeError(f"no checkpoints loaded; tried {WEIGHTS_PATHS}")
    print(f"[load] loaded {len(models)} model(s) for ensemble")

    # FeatureSampler/Autoencoder loaded the CSVs; grab references from the
    # first model (all folds share the same DATA_DIR / CSVs).
    model = models[0]
    fs = model.net.feature_sampler
    print(f"        domains={len(fs.domains)}  ips={len(fs.ips)}  urls={len(fs.urls)}")

    # FeatureSampler drops the 'ioc' column during order_df_cols, so re-read
    # only that column from disk for the name->nid index.
    print("[load] building name->nid index ...")
    name_to_nid = {}
    type_dict = g.type_dict
    ioc_col_by_type = {}
    for ntype, fname in (("domains", "domains.csv"), ("ips", "ips.csv"), ("urls", "urls.csv")):
        col = pd.read_csv(os.path.join(DATA_DIR, fname),
                          sep="\t", usecols=["ioc"])["ioc"].astype(str).str.lower().values
        ioc_col_by_type[ntype] = col
        type_id = type_dict[ntype]
        node_mask = (g.x == type_id).nonzero(as_tuple=True)[0]
        feat_idx = g.feat_map[node_mask].tolist()
        for nid, ridx in zip(node_mask.tolist(), feat_idx):
            if 0 <= ridx < len(col):
                name_to_nid.setdefault((ntype, col[ridx]), nid)
    print(f"        indexed {len(name_to_nid):,} nodes")

    label_map = dict(g.label_map)
    label_map_inv = {v: k for k, v in label_map.items()}

    return {"g": g, "model": model, "models": models, "fs": fs,
            "name_to_nid": name_to_nid,
            "label_map": label_map, "label_map_inv": label_map_inv}


def ensemble_softmax(node_ids: torch.Tensor) -> torch.Tensor:
    """Average softmax across all loaded fold models. Returns [N, C]."""
    g = state["g"]; models = state["models"]
    requested = node_ids.size(0)
    inference_ids = node_ids
    # The paper model uses events.nonzero().squeeze(), which becomes a scalar
    # when a recursive feature batch contains exactly one EVENT.  A second,
    # existing event keeps that operation one-dimensional.  GraphSAGE computes
    # each requested root independently, so the sentinel output is discarded.
    if requested == 1:
        sentinel = g.event_ids[0]
        if sentinel.item() == node_ids[0].item() and g.event_ids.size(0) > 1:
            sentinel = g.event_ids[1]
        inference_ids = torch.cat([node_ids, sentinel.reshape(1)])
    accum = None
    for m in models:
        with torch.no_grad():
            logits = m.inference(g, inference_ids)[:requested]
            sm = logits.softmax(dim=1)
        accum = sm if accum is None else accum + sm
    return accum / len(models)


# ------------------------------------------------------------------ #
#  Mutation helpers (append-only, no rollback)                       #
# ------------------------------------------------------------------ #
def get_or_create_ioc_node(ioc_type: str, value: str) -> int:
    g = state["g"]; fs = state["fs"]
    name_idx = state["name_to_nid"]
    key = (ioc_type, value.lower())

    if key in name_idx:
        return name_idx[key]

    # Build feature row, append to DataFrame, register node
    if ioc_type == "domains":
        row = build_domain_row(value); df_attr = "domains"
    elif ioc_type == "ips":
        row = build_ip_row(value); df_attr = "ips"
    elif ioc_type == "urls":
        row = build_url_row(value); df_attr = "urls"
    else:
        raise ValueError(f"unknown ioc_type {ioc_type}")

    df = getattr(fs, df_attr)
    new_row_idx = len(df)
    df.loc[new_row_idx] = row
    setattr(fs, df_attr, df)

    # Append node
    type_id = g.type_dict[ioc_type]
    new_nid = g.x.size(0)
    g.x = torch.cat([g.x, torch.tensor([type_id], dtype=g.x.dtype)])
    g.feat_map = torch.cat(
        [g.feat_map, torch.tensor([new_row_idx], dtype=g.feat_map.dtype)]
    )
    if isinstance(g.node_names, dict):
        g.node_names[new_nid] = value

    name_idx[key] = new_nid
    return new_nid


def add_temp_event(neighbors: list[int]) -> int:
    """Append a fresh EVENT node, wire CSR edges to neighbors, return its nid."""
    g = state["g"]
    type_id = g.type_dict["EVENT"]
    new_nid = g.x.size(0)
    g.x = torch.cat([g.x, torch.tensor([type_id], dtype=g.x.dtype)])
    # event nodes also have a feat_map slot — set -1 (no row)
    g.feat_map = torch.cat([g.feat_map, torch.tensor([-1], dtype=g.feat_map.dtype)])
    if isinstance(g.node_names, dict):
        g.node_names[new_nid] = f"_tmp_event_{new_nid}"

    # Extend CSR ptr by however many nodes are missing entries (should be 1 step
    # behind because we just added IOC nodes too, which need empty neighbor lists).
    csr = g.edge_csr
    # Pad ptr so every node up to and including new_nid has an entry.
    # ptr[i+1] - ptr[i] = num neighbors of node i.
    while csr.ptr.size(0) < new_nid + 2:
        csr.ptr = torch.cat([csr.ptr, csr.ptr[-1:].clone()])
    # Now append neighbors for new_nid
    if neighbors:
        nb = torch.tensor(neighbors, dtype=csr.idx.dtype)
        csr.idx = torch.cat([csr.idx, nb])
        csr.ptr = torch.cat([csr.ptr, csr.ptr[-1:] + len(neighbors)])
    else:
        csr.ptr = torch.cat([csr.ptr, csr.ptr[-1:].clone()])
    return new_nid


# ------------------------------------------------------------------ #
#  Tier output                                                       #
# ------------------------------------------------------------------ #
def assess(p: float) -> str:
    if p >= 0.70:
        return "high_confidence"
    if p >= 0.40:
        return "moderate_confidence"
    return "low_confidence"


def tiered_from_softmax(scores_by_apt: dict[str, float]) -> dict:
    # Tier 3: top APT
    top_apt, top_p = max(scores_by_apt.items(), key=lambda kv: kv[1])

    # Tier 2: aggregate by nation
    nation_scores: dict[str, float] = {}
    for apt, p in scores_by_apt.items():
        nation = APT_TO_NATION.get(apt.upper(), "Unknown")
        nation_scores[nation] = nation_scores.get(nation, 0.0) + p
    top_nation, top_nation_p = max(nation_scores.items(), key=lambda kv: kv[1])

    # Tier 1: confidence-banded coarse cluster
    if top_nation in {"Russia", "China", "North Korea", "Iran"}:
        cluster = f"State-sponsored ({top_nation})"
    elif top_nation == "Criminal":
        cluster = "Financially-motivated criminal group"
    else:
        cluster = "Other / unattributed"
    cluster_p = top_nation_p

    rec_tier = 3 if top_p >= 0.70 else (2 if top_nation_p >= 0.60 else 1)
    summary = (
        f"Tier-3 actor: {top_apt} ({top_p:.2f}); "
        f"Tier-2 nation: {top_nation} ({top_nation_p:.2f}); "
        f"Tier-1 cluster: {cluster}. Recommended tier: {rec_tier}."
    )
    return {
        "tier3_named_actor":      {"prediction": top_apt,    "confidence": top_p,        "assessment": assess(top_p)},
        "tier2_nation_state":     {"prediction": top_nation, "confidence": top_nation_p, "assessment": assess(top_nation_p)},
        "tier1_activity_cluster": {"prediction": cluster,    "confidence": cluster_p,    "assessment": assess(cluster_p)},
        "recommended_tier": rec_tier,
        "summary": summary,
    }


# ------------------------------------------------------------------ #
#  FastAPI app                                                       #
# ------------------------------------------------------------------ #
app = FastAPI(title="TRAIL Paper GNN Predictor", version="1.0")


@app.on_event("startup")
def _on_start():
    state.update(load_everything())
    print("[ready] server up.")


class PredictEventReq(BaseModel):
    event_id: int


@app.post("/predict_event")
def predict_event(req: PredictEventReq):
    g = state["g"]; lm = state["label_map"]
    if not (0 <= req.event_id < g.x.size(0)):
        raise HTTPException(400, f"event_id out of range")
    if g.x[req.event_id].item() != g.type_dict["EVENT"]:
        raise HTTPException(400, f"node {req.event_id} is not an EVENT node")

    probs = ensemble_softmax(torch.tensor([req.event_id]))[0]

    scores = {lm[i]: float(probs[i]) for i in range(probs.size(0))}
    top = max(scores.items(), key=lambda kv: kv[1])
    # If event_id is a known labeled event, surface its true label
    is_known = (g.event_ids == req.event_id).any().item()
    true_apt = None
    if is_known:
        loc = (g.event_ids == req.event_id).nonzero(as_tuple=True)[0].item()
        ylab = int(g.y[loc].item())
        if ylab >= 0:
            true_apt = lm[ylab]
    return {
        "event_id": req.event_id,
        "true_apt": true_apt,
        "predicted_apt": top[0],
        "confidence": top[1],
        "scores": scores,
        "tiered": tiered_from_softmax(scores),
    }


class IOC(BaseModel):
    type: str  # "domain" | "ip" | "url"
    value: str


class AttributeReq(BaseModel):
    iocs: list[IOC]


TYPE_MAP = {"domain": "domains", "ip": "ips", "url": "urls"}


@app.post("/attribute")
def attribute(req: AttributeReq):
    if not req.iocs:
        raise HTTPException(400, "no IOCs provided")

    ioc_node_ids: list[int] = []
    matched_existing = 0
    enriched_new = 0
    for ioc in req.iocs:
        ntype = TYPE_MAP.get(ioc.type.lower())
        if ntype is None:
            raise HTTPException(400, f"unknown ioc.type={ioc.type!r}")
        was_known = (ntype, ioc.value.lower()) in state["name_to_nid"]
        nid = get_or_create_ioc_node(ntype, ioc.value)
        ioc_node_ids.append(nid)
        if was_known:
            matched_existing += 1
        else:
            enriched_new += 1

    temp_event_nid = add_temp_event(ioc_node_ids)

    g = state["g"]; lm = state["label_map"]
    probs = ensemble_softmax(torch.tensor([temp_event_nid]))[0]

    scores = {lm[i]: float(probs[i]) for i in range(probs.size(0))}
    top = max(scores.items(), key=lambda kv: kv[1])

    return {
        "status": "success",
        "predicted_apt": top[0],
        "confidence": top[1],
        "scores": scores,
        "iocs_processed": len(req.iocs),
        "matched_existing_in_graph": matched_existing,
        "newly_enriched": enriched_new,
        "temp_event_node_id": temp_event_nid,
        "tiered": tiered_from_softmax(scores),
    }


@app.get("/status")
def status():
    if not state:
        return {"ready": False}
    g = state["g"]
    return {
        "ready": True,
        "graph_nodes": int(g.x.size(0)),
        "events": int(g.event_ids.size(0)),
        "classes": list(state["label_map"].values()),
        "weights": WEIGHTS_PATHS,
        "ensemble_size": len(state.get("models", [])),
        "graph": GRAPH_PATH,
    }
