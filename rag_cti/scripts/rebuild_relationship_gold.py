#!/usr/bin/env python3
"""Deterministically rebuild relationship_direct gold from the project's ATT&CK bundle.

Why this exists
---------------
Phase D expanded ``relationship_direct`` gold with the certified LLM annotator.
That introduced cross-tactic false labels (techniques the actor uses, but under a
*different* tactic than the query asked for) and recall was only ~0.27. The
remedy is to stop guessing: for an "actor X, tactic Y" query the set of direct
techniques is fully determined by the ATT&CK graph, so we traverse it instead.

NO LLM. NO hand-written gold. NO guessing. Pure, deterministic STIX graph
traversal over the project's own bundle (``data/raw/mitre/enterprise-attack.json``).

Paths that contribute to gold (union):
  1. direct:        intrusion-set --uses--> attack-pattern
  2. via_software:  intrusion-set --uses--> (malware|tool) --uses--> attack-pattern

Each reached attack-pattern is kept only if:
  - it is not revoked and not deprecated, AND
  - one of its ``mitre-attack`` kill_chain_phases == the query's tactic.
Survivors are normalised to their base technique (``T1218.013`` -> ``T1218``).

Campaign attribution is computed SEPARATELY into ``campaign_path_extra`` (for
human audit) and is never merged into gold:
  campaign --attributed-to--> intrusion-set ; campaign --uses--> attack-pattern
(same tactic filter / normalisation applied so the extras are directly comparable).

Run:  python3 scripts/rebuild_relationship_gold.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# --- paths (project-relative; only the project bundle, never a download) -----
ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "data" / "raw" / "mitre" / "enterprise-attack.json"
V2_PATH = ROOT / "data" / "eval" / "query_set_v2.jsonl"
V3_SAMPLE_PATH = ROOT / "data" / "eval" / "query_set_v3_sample.jsonl"  # annotator trace, R001-R005
OUT_PATH = ROOT / "data" / "eval" / "query_set_v3.jsonl"

CATEGORY = "relationship_direct"
MITRE = "mitre-attack"
_TID_RE = re.compile(r"^T\d{4}(\.\d{3})?$", re.IGNORECASE)
_TACTIC_RE = re.compile(r"tactic\s*=\s*([a-z\-]+)", re.IGNORECASE)
_NOTES_ACTOR_RE = re.compile(r"Direct:\s*(.+?)\s*->", re.IGNORECASE)


# --- helpers -----------------------------------------------------------------
def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def base_technique(external_id: str) -> str:
    """T1218.013 -> T1218 ; T1059 -> T1059 (upper-cased)."""
    return external_id.split(".")[0].upper()


def attack_pattern_external_id(obj: dict) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == MITRE:
            return ref.get("external_id")
    return None


def is_active(obj: dict) -> bool:
    return not obj.get("revoked", False) and not obj.get("x_mitre_deprecated", False)


def matches_tactic(ap: dict, tactic: str) -> bool:
    tactic = _norm(tactic)
    for ph in ap.get("kill_chain_phases", []):
        if ph.get("kill_chain_name") == MITRE and _norm(ph.get("phase_name")) == tactic:
            return True
    return False


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# --- bundle indexing ---------------------------------------------------------
class AttackGraph:
    def __init__(self, bundle_path: Path):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        self.objects = bundle["objects"]
        self.by_id = {o["id"]: o for o in self.objects}

        # ATT&CK version (from the collection object) for provenance.
        coll = next((o for o in self.objects if o.get("type") == "x-mitre-collection"), {})
        self.attack_version = coll.get("x_mitre_version")
        self.attack_spec = coll.get("x_mitre_attack_spec_version")
        self.spec_label = (
            f"ATT&CK Enterprise v{self.attack_version} "
            f"(attack-spec {self.attack_spec}, STIX 2.1)"
        )

        self.tactics = sorted(
            {
                o.get("x_mitre_shortname")
                for o in self.objects
                if o.get("type") == "x-mitre-tactic"
            }
        )

        # uses: source_ref -> [target_ref, ...]
        self.uses: dict[str, list[str]] = {}
        # attributed-to (campaign -> intrusion-set): intrusion_set_id -> [campaign_id]
        self.attributed_campaigns: dict[str, list[str]] = {}
        for o in self.objects:
            if o.get("type") != "relationship":
                continue
            rtype = o.get("relationship_type")
            src, tgt = o.get("source_ref"), o.get("target_ref")
            if not src or not tgt:
                continue
            if rtype == "uses":
                self.uses.setdefault(src, []).append(tgt)
            elif rtype == "attributed-to":
                # source = campaign, target = intrusion-set
                if (self.by_id.get(src, {}).get("type") == "campaign"
                        and self.by_id.get(tgt, {}).get("type") == "intrusion-set"):
                    self.attributed_campaigns.setdefault(tgt, []).append(src)

        self.intrusion_sets = [o for o in self.objects if o.get("type") == "intrusion-set"]

    # -- actor resolution: exact name, then exact alias, then alias-substring --
    def match_intrusion_set(self, actor: str) -> tuple[dict | None, str]:
        active = [o for o in self.intrusion_sets if is_active(o)]
        q = _norm(actor)
        exact = [o for o in active if _norm(o.get("name")) == q]
        if exact:
            return exact[0], "exact_name"
        alias_exact = [
            o for o in active if any(q == _norm(a) for a in o.get("aliases", []))
        ]
        if alias_exact:
            return alias_exact[0], "exact_alias"
        # alias contains the actor string; require a UNIQUE intrusion-set to stay deterministic.
        contains = [
            o for o in active if any(q in _norm(a) for a in o.get("aliases", []))
        ]
        uniq = {o["id"]: o for o in contains}
        if len(uniq) == 1:
            return next(iter(uniq.values())), "alias_contains"
        if len(uniq) > 1:
            return None, "alias_ambiguous:" + ",".join(o.get("name", "?") for o in uniq.values())
        return None, "no_match"

    def _ap_ids_used_by(self, source_id: str) -> set[str]:
        """attack-pattern ids directly reached by `source --uses--> attack-pattern`."""
        out = set()
        for tgt in self.uses.get(source_id, []):
            if self.by_id.get(tgt, {}).get("type") == "attack-pattern":
                out.add(tgt)
        return out

    def _software_ids_used_by(self, source_id: str) -> set[str]:
        out = set()
        for tgt in self.uses.get(source_id, []):
            if self.by_id.get(tgt, {}).get("type") in ("malware", "tool"):
                out.add(tgt)
        return out

    def _filter_normalise(self, ap_ids: set[str], tactic: str) -> set[str]:
        """Apply revoked/deprecated + tactic filter, then normalise to base technique."""
        out = set()
        for ap_id in ap_ids:
            ap = self.by_id.get(ap_id)
            if not ap or not is_active(ap):
                continue
            if not matches_tactic(ap, tactic):
                continue
            ext = attack_pattern_external_id(ap)
            if ext and _TID_RE.match(ext):
                out.add(base_technique(ext))
        return out

    def gold_for(self, is_obj: dict, tactic: str) -> dict:
        is_id = is_obj["id"]
        # path 1: direct
        direct_aps = self._ap_ids_used_by(is_id)
        # path 2: via software
        software = self._software_ids_used_by(is_id)
        via_aps: set[str] = set()
        for sw in software:
            via_aps |= self._ap_ids_used_by(sw)

        direct_gold = self._filter_normalise(direct_aps, tactic)
        via_gold = self._filter_normalise(via_aps, tactic)
        gold = sorted(direct_gold | via_gold)

        # campaign path (separate, not merged)
        campaign_ids = self.attributed_campaigns.get(is_id, [])
        camp_aps: set[str] = set()
        for cid in campaign_ids:
            camp_aps |= self._ap_ids_used_by(cid)
        campaign_extra = sorted(self._filter_normalise(camp_aps, tactic) - set(gold))

        return {
            "gold": gold,
            "direct_only": sorted(direct_gold),
            "via_software_only": sorted(via_gold - direct_gold),
            "n_software": len(software),
            "n_campaigns": len(campaign_ids),
            "campaign_extra": campaign_extra,
        }


# --- row parsing -------------------------------------------------------------
def parse_actor(row: dict) -> str | None:
    actor = (row.get("gold_actor") or "").strip()
    if actor:
        return actor
    m = _NOTES_ACTOR_RE.search(row.get("notes", "") or "")
    return m.group(1).strip() if m else None


def parse_tactic(row: dict) -> str | None:
    m = _TACTIC_RE.search(row.get("notes", "") or "")
    return m.group(1).strip().lower() if m else None


# --- main --------------------------------------------------------------------
def main() -> int:
    if not BUNDLE_PATH.exists():
        print(f"FATAL: bundle not found at {BUNDLE_PATH}", file=sys.stderr)
        return 2

    graph = AttackGraph(BUNDLE_PATH)

    print("=" * 72)
    print(f"BUNDLE: {graph.spec_label}")
    print(f"TACTICS ({len(graph.tactics)}): {', '.join(graph.tactics)}")
    print("=" * 72)

    # GATE: defense-evasion must exist under its standard shortname.
    if "defense-evasion" not in graph.tactics:
        print(
            "GATE FAILED: 'defense-evasion' absent from bundle tactics "
            "(possibly renamed). STOPPING — not guessing a mapping, not downloading "
            "another bundle version.",
            file=sys.stderr,
        )
        return 3

    v2_rows = load_jsonl(V2_PATH)
    # annotator trace, keyed by query_id (only R001-R005 were ever expanded)
    annotator = {r["query_id"]: r for r in load_jsonl(V3_SAMPLE_PATH)}

    out_rows: list[dict] = []
    table: list[dict] = []
    skipped: list[tuple[str, str]] = []

    for row in v2_rows:
        if row.get("category") != CATEGORY:
            out_rows.append(row)  # verbatim copy; v3 = v2 with relationship_direct gold rebuilt
            continue

        qid = row.get("query_id")
        actor = parse_actor(row)
        tactic = parse_tactic(row)
        prev_row = annotator.get(qid)
        prev_gold = prev_row.get("gold_attack_ids") if prev_row else None
        original_gold = row.get("gold_attack_ids", [])

        if not actor or not tactic:
            reason = f"unresolved (actor={actor!r}, tactic={tactic!r})"
            skipped.append((qid, reason))
            new_row = dict(row)
            new_row["gold_status"] = "unresolved"
            new_row["prev_annotator_gold"] = prev_gold
            out_rows.append(new_row)
            continue

        is_obj, how = graph.match_intrusion_set(actor)
        if is_obj is None:
            reason = f"actor_unmatched (actor={actor!r}, detail={how})"
            skipped.append((qid, reason))
            new_row = dict(row)
            new_row["gold_status"] = "actor_unmatched"
            new_row["prev_annotator_gold"] = prev_gold
            out_rows.append(new_row)
            continue

        res = graph.gold_for(is_obj, tactic)
        new_gold = res["gold"]

        # removed-as-false-positive = items in the prior (annotator) gold that the
        # graph does NOT support for this actor x tactic, compared at base level.
        prev_base = sorted({base_technique(t) for t in (prev_gold or [])})
        removed = sorted(set(prev_base) - set(new_gold))
        # seed survival: the v2 hand-seed should be a real direct technique.
        orig_base = sorted({base_technique(t) for t in original_gold})
        seed_survived = all(t in new_gold for t in orig_base)

        new_row = dict(row)
        new_row["gold_attack_ids"] = new_gold
        new_row["original_gold_attack_ids"] = original_gold
        new_row["prev_annotator_gold"] = prev_gold
        if prev_row is not None and prev_row.get("annotator_pred") is not None:
            new_row["annotator_pred"] = prev_row.get("annotator_pred")
        new_row["campaign_path_extra"] = res["campaign_extra"]
        new_row["gold_status"] = "resolved"
        new_row["gold_provenance"] = {
            "method": "attack_graph_traversal",
            "paths": ["direct", "via_software"],
            "bundle": graph.spec_label,
            "tactic_filter": tactic,
            "actor_query": actor,
            "actor_matched_name": is_obj.get("name"),
            "actor_stix_id": is_obj["id"],
            "actor_match_mode": how,
            "n_direct": len(res["direct_only"]),
            "n_via_software": len(res["via_software_only"]),
            "n_software_pivots": res["n_software"],
            "n_campaigns_attributed": res["n_campaigns"],
            "seed_survived": seed_survived,
        }
        out_rows.append(new_row)

        table.append(
            {
                "qid": qid,
                "actor": f"{actor} -> {is_obj.get('name')}",
                "tactic": tactic,
                "old_n": len(prev_gold) if prev_gold is not None else len(original_gold),
                "old_src": "annotator" if prev_gold is not None else "v2-seed",
                "new_n": len(new_gold),
                "removed": removed,
                "camp_n": len(res["campaign_extra"]),
                "seed_ok": seed_survived,
            }
        )

    # write artifact
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for r in out_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # --- report ---
    print()
    print("REBUILT relationship_direct gold (deterministic ATT&CK traversal)")
    print("-" * 110)
    hdr = (
        f"{'qid':5} | {'actor (query -> matched)':30} | {'tactic':22} | "
        f"{'old#':>4} | {'new#':>4} | {'camp':>4} | {'seed':>4} | removed-old-false-labels"
    )
    print(hdr)
    print("-" * 110)
    for t in table:
        removed_str = ",".join(t["removed"]) if t["removed"] else "-"
        print(
            f"{t['qid']:5} | {t['actor']:30} | {t['tactic']:22} | "
            f"{t['old_n']:>4} | {t['new_n']:>4} | {t['camp_n']:>4} | "
            f"{('OK' if t['seed_ok'] else 'MISS'):>4} | {removed_str}"
        )
    print("-" * 110)
    print(f"  (old# source per row: {', '.join(t['qid']+'='+t['old_src'] for t in table)})")

    print()
    if skipped:
        print(f"SKIPPED rows ({len(skipped)}):")
        for qid, reason in skipped:
            print(f"  - {qid}: {reason}")
    else:
        print("SKIPPED rows: NONE (all relationship_direct rows resolved)")

    n_rel = len(table) + len(skipped)
    print()
    print(f"ARTIFACT: {OUT_PATH}  ({len(out_rows)} rows total, {n_rel} relationship_direct)")
    print(f"SCRIPT:   {Path(__file__).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
