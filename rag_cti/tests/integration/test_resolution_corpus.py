"""Corpus ground-truth assertions for the campaign-mirror + embedded-id resolution.

These pin the numbers independently reproduced over the real raw corpus:
  - every campaign relationship mention recovers: 1193 / 1193 (structural, zero fuzzy)
  - clean embedded-id family recoveries: 216
  - the dirty embedded ids (mobile-namespace collisions, absent ids) DO orphan,
    never silently mis-attribute.

White-box on purpose: it drives the same private resolver the projection uses, over
real raw data. Skipped automatically when data/raw is absent (e.g. CI), so it is a
local ground-truth gate, not a portability blocker.
"""

from __future__ import annotations

import json
import re
from glob import glob
from pathlib import Path

import pytest

from rag_cti.ingest.normalize import normalize_mitre_relationship, normalize_otx_pulse
from rag_cti.preprocess.entity_registry import _build_indexes, _resolve_one
from rag_cti.preprocess.ontology_nodes import ontology_nodes_from_bundle

_ROOT = Path(__file__).resolve().parents[2]
_BUNDLE = _ROOT / "data" / "raw" / "mitre" / "enterprise-attack.json"
_OTX = _ROOT / "data" / "raw" / "otx"

pytestmark = pytest.mark.skipif(
    not _BUNDLE.exists() or not _OTX.exists(),
    reason="real raw corpus (data/raw) not present",
)

_ID_RE = re.compile(r"\b[SGT]\d{4}(?:\.\d{3})?\b")


def _indexes() -> tuple[dict, dict]:
    nodes = ontology_nodes_from_bundle(json.loads(_BUNDLE.read_text(encoding="utf-8")))
    return _build_indexes(nodes)


def test_campaign_recovery_is_1193_over_real_bundle() -> None:
    name_nodes, oid_nodes = _indexes()
    bundle = json.loads(_BUNDLE.read_text(encoding="utf-8"))
    stix = {o["id"]: o for o in bundle["objects"] if "id" in o}
    total = resolved = 0
    for o in bundle["objects"]:
        if o.get("type") != "relationship":
            continue
        try:
            rec = normalize_mitre_relationship(o, stix)
        except Exception:
            continue
        for m in rec.entity_mentions:
            if m.type == "campaign":
                total += 1
                if _resolve_one(m.name, "campaign", name_nodes, oid_nodes).resolution != "orphan":
                    resolved += 1
    assert total == 1193
    assert resolved == 1193  # structural STIX-id-backed names: all recover, zero fuzzy


def test_embedded_id_clean_is_216_and_dirty_orphans_over_real_otx() -> None:
    name_nodes, oid_nodes = _indexes()
    clean = 0
    # the dirty trio (2 mobile-namespace collisions + 1 absent id) MUST orphan
    dirty: dict[str, str | None] = {
        "SpyNote RAT - MOB-S0021": None,  # grabs enterprise S0021 (Derusbi)
        "Pegasus - MOB-S0005": None,  # grabs enterprise S0005 (Win Credential Editor)
        "SpyNote RAT - S0305": None,  # S0305 absent from enterprise bundle
    }
    for rf in glob(str(_OTX / "**" / "*.json"), recursive=True):
        try:
            raw = json.loads(Path(rf).read_text(encoding="utf-8"))
        except Exception:
            continue
        for p in raw if isinstance(raw, list) else [raw]:
            try:
                rec = normalize_otx_pulse(p)
            except Exception:
                continue
            for m in rec.entity_mentions:
                if m.type == "family" and _ID_RE.search(m.name):
                    res = _resolve_one(m.name, "family", name_nodes, oid_nodes).resolution
                    if res == "embedded_id":
                        clean += 1
                    if m.name in dirty:
                        dirty[m.name] = res
    assert clean == 216
    for name, res in dirty.items():
        assert res == "orphan", f"dirty embedded id {name!r} must orphan, got {res!r}"
