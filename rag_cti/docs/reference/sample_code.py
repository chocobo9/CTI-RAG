#!/usr/bin/env python3
"""
Canonical OTX collection pipeline for the TRAIL knowledge graph.

Produces a graph whose schema and enrichment depth match the TRAIL paper
(King et al., ICDE 2025), including the two enrichments our earlier
scripts missed and which cost us ~27 accuracy points vs. the paper:

    1. Reverse passive DNS (IP  → historical Domains, paper §IV-A)
    2. ASN nodes          (IP -[InGroup]-> ASN,     paper §IV-C, Table I)

Schema produced:
    Event  -[:InReport]->  Domain
    Event  -[:InReport]->  IP
    Event  -[:InReport]->  URL
    URL    -[:HostedOn]->  Domain
    URL    -[:ResolvesTo]-> IP
    Domain -[:ResolvesTo]-> IP           (forward + reverse pDNS)
    IP     -[:InGroup]->   ASN

Run:
    export OTX_API_KEYS=key1,key2                # preferred: comma-separated for ~2x speed
    # OR: export OTX_API_KEY=single_key          # single-key fallback
    eval "$(pyenv init -)"
    python3 collect_otx.py                 # collect all 11 APTs, all history
    python3 collect_otx.py --apt APT28     # single APT
    python3 collect_otx.py --since 2023-01-01 --until 2024-12-31
    python3 collect_otx.py --skip-enrichment  # dry, pulse-only (no pDNS/ASN calls)

Checkpointing: every pulse's ID is saved to otx_checkpoint.json on success.
Re-running resumes from the last processed pulse. Delete the checkpoint
file to start over.

Design notes for "collect from scratch" correctness:
    - We query OTX using the APT *name* AND its MITRE aliases, then drop
      pulses whose tag set maps to more than one of our target APTs
      (paper §IV-A: "ignored unless the tags all map to the same APT").
    - pDNS is enriched BOTH directions so new primary-IP nodes pull in
      their historical domains (secondary IOCs). The paper reports that
      after this step, 75% of graph nodes are secondary IOCs.
    - ASN lookup happens once per IP, cached across pulses in-memory so
      a single APT run stays well under OTX rate limits.
    - Title-near-dup pulses (e.g. "Operation Artemis" re-indexed daily)
      are detected and skipped before any writes.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from neo4j import GraphDatabase

# Local imports — config is the single source of truth for APT list
from trail_gnn import config
from trail_gnn.otx_enrichment import (
    KeyPool,
    OTXTransientError,
    key_pool_from_env,
    get_ip_general,
    get_forward_pdns,
    get_reverse_pdns,
)

# ─── Configuration ───────────────────────────────────────────────────

# Populated in collect(); used by the legacy _request_json helper below
# for the non-enrichment OTX endpoints (search, pulse detail, etc.).
_KEYPOOL: KeyPool | None = None
OTX_BASE = "https://otx.alienvault.com/api/v1"

NEO4J_URI = os.environ.get("NEO4J_URI", config.NEO4J_URI)
NEO4J_USER = os.environ.get("NEO4J_USER", config.NEO4J_USER)
NEO4J_PASS = os.environ.get("NEO4J_PASSWORD", config.NEO4J_PASSWORD)

ROOT = Path(__file__).parent
CHECKPOINT_FILE = ROOT / "otx_checkpoint.json"
LOG_FILE = ROOT / "otx_collector.log"
SKIP_LOG = ROOT / "otx_skipped.log"

# Collection controls
MAX_PULSES_PER_APT = 400       # safety ceiling per APT per run
MAX_SEARCH_PAGES = 80
PULSE_DELAY = 1.5              # seconds between OTX pulse fetches
RETRY_MAX = 5
RETRY_BASE_DELAY = 20
REQUEST_TIMEOUT = 60

# Enrichment caps (per pulse, to keep walltime finite)
FORWARD_PDNS_PER_DOMAIN = 20   # IPs we pull per domain via forward pDNS
REVERSE_PDNS_PER_IP = 30       # domains we pull per IP via reverse pDNS
ASN_CACHE_TTL = 60 * 60 * 24   # re-query an IP's ASN at most once per day

# Title-dedup: two pulses whose normalized titles have ≥0.92 Jaccard (token)
# similarity are treated as the same report. OTX frequently re-indexes the
# same writeup for days, and near-dupes inflate CV via leakage.
TITLE_DEDUP_JACCARD = 0.92

# ─── Logging (unbuffered, survives SIGKILL) ──────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE)],
    force=True,
)
log = logging.getLogger("collect_otx")
for h in logging.root.handlers:
    h.flush = (lambda orig: lambda: orig())(h.flush)  # no-op but keeps pattern

skip_log = logging.getLogger("otx_skipped")
skip_log.setLevel(logging.INFO)
skip_log.addHandler(logging.FileHandler(SKIP_LOG))

# ─── MITRE alias map (populated lazily) ──────────────────────────────

_MITRE_ALIASES: dict[str, str] | None = None


def _request_json(url: str, params: dict | None = None, timeout: int = REQUEST_TIMEOUT) -> dict | None:
    """
    GET json with exponential backoff on 5xx/transport errors and per-key
    rotation on 429s (via the module-level _KEYPOOL). Returns parsed JSON
    or None.
    """
    assert _KEYPOOL is not None, "collect() must initialize _KEYPOOL first"
    for attempt in range(RETRY_MAX):
        key = _KEYPOOL.next_key()
        headers = {"X-OTX-API-KEY": key}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (404, 403):
                return None
            if resp.status_code == 429:
                # Park this key and try the next one immediately
                _KEYPOOL.cooldown(key)
                continue
            if resp.status_code in (502, 503, 504):
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                log.warning("HTTP %s on %s — sleeping %ss", resp.status_code, url, delay)
                time.sleep(delay)
                continue
            log.warning("HTTP %s on %s", resp.status_code, url)
            return None
        except (requests.Timeout, requests.ConnectionError) as e:
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            log.warning("Transport error: %s — sleeping %ss", e, delay)
            time.sleep(delay)
    return None


def get_mitre_aliases() -> dict[str, str]:
    """Alias-lowercase → canonical MITRE group name."""
    global _MITRE_ALIASES
    if _MITRE_ALIASES is not None:
        return _MITRE_ALIASES

    log.info("Fetching MITRE ATT&CK intrusion-set aliases…")
    data = _request_json(
        "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json",
        timeout=30,
    )
    alias_map: dict[str, str] = {}
    if data:
        for obj in data.get("objects", []):
            if obj.get("type") == "intrusion-set":
                name = obj.get("name", "")
                for alias in obj.get("aliases", [name]):
                    alias_map[alias.lower()] = name
        log.info("  Loaded %d MITRE aliases", len(alias_map))
    else:
        log.warning("  MITRE fetch failed — proceeding without aliases")
    _MITRE_ALIASES = alias_map
    return alias_map


# ─── Pulse filtering: dedup + unambiguous labeling ──────────────────

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _title_tokens(title: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(title or "") if len(t) >= 3}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def has_unambiguous_apt(pulse: dict, target_apt: str, aliases: dict[str, str]) -> bool:
    """
    True iff the pulse's tags resolve to exactly one of our target APTs
    AND that APT is `target_apt`. Implements paper §IV-A:
    "ignored unless the tags all map to the same APT".
    """
    tags = pulse.get("tags", []) or []
    tag_strings = [t.lower() if isinstance(t, str) else (t.get("name") or "").lower() for t in tags]

    resolved_apts: set[str] = set()
    for t in tag_strings:
        group = aliases.get(t)
        if group and group in config.APT_GROUPS:
            resolved_apts.add(group)

    if len(resolved_apts) == 0:
        # No alias match — accept if the queried APT name itself is in a tag
        return target_apt.lower() in tag_strings
    if len(resolved_apts) == 1:
        return target_apt in resolved_apts
    return False


# ─── Independent DST (unchanged from v5 — per-pulse confidence) ─────

def compute_dst(pulse: dict, apt_name: str, aliases: dict[str, str]) -> dict:
    tags = pulse.get("tags", []) or []
    tag_strings = [t.lower() if isinstance(t, str) else (t.get("name") or "").lower() for t in tags]
    indicators = pulse.get("indicators", []) or []
    ioc_count = len(indicators)
    pulse_text = ((pulse.get("name") or "") + " " + (pulse.get("description") or "")).lower()

    apt_tag_counts: dict[str, int] = {}
    for t in tag_strings:
        g = aliases.get(t)
        if g:
            apt_tag_counts[g] = apt_tag_counts.get(g, 0) + 1

    target_count = apt_tag_counts.get(apt_name, 0)
    total_apt_tags = sum(apt_tag_counts.values())
    if total_apt_tags > 0:
        tag_exclusivity = (target_count / total_apt_tags) ** 2
    else:
        distinct = {g for a, g in aliases.items() if len(a) > 3 and a in pulse_text}
        tag_exclusivity = 1.0 / (1.0 + max(len(distinct), 1))

    evidence_weight = min(1.0, math.log2(1 + ioc_count) / math.log2(51)) if ioc_count else 0.0

    apt_nation = config.APT_TO_NATION.get(apt_name, "").lower()
    nation_kw = {
        "russia": "russia", "russian": "russia",
        "north korea": "north korea", "dprk": "north korea",
        "china": "china", "chinese": "china",
        "iran": "iran", "iranian": "iran",
    }
    pulse_nations: set[str] = set()
    for t in tag_strings + [pulse_text]:
        for kw, nation in nation_kw.items():
            if kw in t:
                pulse_nations.add(nation)
    if not pulse_nations:
        nation_coherence = 0.5
    elif apt_nation in pulse_nations:
        nation_coherence = 1.0
    else:
        nation_coherence = 0.0

    m_named = tag_exclusivity * evidence_weight * nation_coherence
    m_nation = (1.0 - tag_exclusivity) * evidence_weight * nation_coherence * 0.5
    uncertainty = 1.0 - m_named - m_nation
    nation = config.APT_TO_NATION.get(apt_name, "")

    return {
        "label_confidence": round(m_named, 4),
        "belief_named_actor": round(m_named, 4),
        "belief_nation_state": round(m_named + m_nation, 4),
        "uncertainty": round(uncertainty, 4),
        "tag_exclusivity": round(tag_exclusivity, 4),
        "evidence_weight": round(evidence_weight, 4),
        "nation_coherence": round(nation_coherence, 4),
        "activity_cluster": "State-Sponsored" if nation and nation != "Cybercrime" else "Cybercrime",
    }


# ─── Neo4j writer ────────────────────────────────────────────────────

class Neo4jWriter:
    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        stmts = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Domain) REQUIRE d.value IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ip:IP) REQUIRE ip.value IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:URL) REQUIRE u.value IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:ASN) REQUIRE a.number IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.apt)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.pulse_created)",
        ]
        with self.driver.session() as s:
            for q in stmts:
                s.run(q)

    def close(self) -> None:
        self.driver.close()

    # --- Event / IOC writes ---

    def write_event(self, pulse: dict, apt_name: str, dst: dict) -> None:
        with self.driver.session() as s:
            s.run(
                """
                MERGE (e:Event {id: $id})
                SET e.name = $name,
                    e.apt = $apt,
                    e.pulse_created = $pulse_created,
                    e.pulse_modified = $pulse_modified,
                    e.label_confidence = $label_confidence,
                    e.belief_named_actor = $belief_named_actor,
                    e.belief_nation_state = $belief_nation_state,
                    e.uncertainty = $uncertainty,
                    e.tag_exclusivity = $tag_exclusivity,
                    e.evidence_weight = $evidence_weight,
                    e.nation_coherence = $nation_coherence,
                    e.activity_cluster = $activity_cluster,
                    e.nation = $nation,
                    e.source = 'otx'
                """,
                id=pulse["id"],
                name=pulse.get("name", ""),
                apt=apt_name,
                pulse_created=pulse.get("created", ""),
                pulse_modified=pulse.get("modified", ""),
                nation=config.APT_TO_NATION.get(apt_name, "Unknown"),
                **dst,
            )

    def write_ioc_edge(self, kind: str, ioc: str, event_id: str, indicator_created: str) -> None:
        """Create Event-[:InReport]->IOC. `kind` is 'Domain', 'IP', or 'URL'."""
        q = f"""
            MERGE (n:{kind} {{value: $val}})
            WITH n
            MATCH (e:Event {{id: $eid}})
            MERGE (e)-[r:InReport]->(n)
            SET r.indicator_created = CASE
              WHEN r.indicator_created IS NULL OR $ic < r.indicator_created
              THEN $ic ELSE r.indicator_created END
        """
        with self.driver.session() as s:
            s.run(q, val=ioc, eid=event_id, ic=indicator_created or "")

    def write_resolves_to(self, domain: str, ip: str, first: str, last: str) -> None:
        with self.driver.session() as s:
            s.run(
                """
                MERGE (d:Domain {value: $d})
                MERGE (i:IP {value: $ip})
                MERGE (d)-[r:ResolvesTo]->(i)
                SET r.first_seen = CASE
                      WHEN r.first_seen IS NULL OR ($first <> '' AND $first < r.first_seen)
                      THEN $first ELSE r.first_seen END,
                    r.last_seen  = CASE
                      WHEN r.last_seen IS NULL OR ($last <> '' AND $last > r.last_seen)
                      THEN $last ELSE r.last_seen END
                """,
                d=domain, ip=ip, first=first or "", last=last or "",
            )

    def write_hosted_on(self, url_val: str, domain: str) -> None:
        with self.driver.session() as s:
            s.run(
                """
                MERGE (d:Domain {value: $d})
                WITH d
                MATCH (u:URL {value: $u})
                MERGE (u)-[:HostedOn]->(d)
                """,
                u=url_val, d=domain,
            )

    def write_url_resolves_to(self, url_val: str, ip: str) -> None:
        with self.driver.session() as s:
            s.run(
                """
                MERGE (i:IP {value: $ip})
                WITH i
                MATCH (u:URL {value: $u})
                MERGE (u)-[:ResolvesTo]->(i)
                """,
                u=url_val, ip=ip,
            )

    # --- ASN writes ---

    def write_asn(self, ip: str, asn_number: int, asn_name: str, country: str) -> None:
        """Create ASN node + IP-[:InGroup]->ASN edge, and stamp country on the IP."""
        with self.driver.session() as s:
            s.run(
                """
                MERGE (a:ASN {number: $num})
                SET a.name = CASE WHEN $name <> '' THEN $name ELSE a.name END
                WITH a
                MATCH (i:IP {value: $ip})
                SET i.country = CASE WHEN $country <> '' THEN $country ELSE i.country END,
                    i.asn_number = $num,
                    i.asn_description = $name
                MERGE (i)-[:InGroup]->(a)
                """,
                num=asn_number, name=asn_name or "", ip=ip, country=country or "",
            )

    # --- Queries used by the collector ---

    def recent_titles_for_apt(self, apt_name: str, limit: int = 200) -> list[str]:
        """Fetch recent Event titles for an APT — used for near-dup detection."""
        with self.driver.session() as s:
            rs = s.run(
                "MATCH (e:Event {apt: $apt}) RETURN e.name AS n "
                "ORDER BY e.pulse_created DESC LIMIT $lim",
                apt=apt_name, lim=limit,
            )
            return [r["n"] or "" for r in rs]


# ─── Checkpoint ──────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text())
        except json.JSONDecodeError:
            log.warning("Corrupt checkpoint — starting fresh")
    return {
        "completed_apts": [],
        "completed_pulse_ids": [],
        "asn_cache": {},   # ip → {ts, asn_number, asn_name, country}
        "dns_cache": {},   # ip → last reverse-pDNS timestamp (epoch)
    }


def save_checkpoint(ckpt: dict) -> None:
    ckpt["last_update"] = datetime.now(timezone.utc).isoformat()
    CHECKPOINT_FILE.write_text(json.dumps(ckpt, indent=2))


# ─── OTX API wrappers ───────────────────────────────────────────────

def search_pulses(query: str, page: int) -> list[dict]:
    data = _request_json(
        f"{OTX_BASE}/search/pulses",
        params={"q": query, "page": page, "limit": 20, "sort": "-modified"},
    )
    return (data or {}).get("results", [])


def fetch_pulse(pulse_id: str) -> dict | None:
    return _request_json(f"{OTX_BASE}/pulses/{pulse_id}")


def fetch_indicators(pulse_id: str) -> list[dict]:
    data = _request_json(f"{OTX_BASE}/pulses/{pulse_id}/indicators", params={"limit": 1000})
    return (data or {}).get("results", [])


# ─── Enrichment orchestration ───────────────────────────────────────

def enrich_ip(ip: str, writer: Neo4jWriter, ckpt: dict,
              do_asn: bool = True, do_reverse: bool = True) -> None:
    """
    Pull ASN + reverse pDNS for a single IP. Cached per run so an IP
    that appears in multiple pulses is hit once. Safe to call many times.
    """
    now = time.time()

    # ASN (cached for 1 day). Transient OTX failures skip this IP for now.
    if do_asn:
        cached = ckpt["asn_cache"].get(ip)
        if not cached or (now - cached.get("ts", 0)) > ASN_CACHE_TTL:
            try:
                info = get_ip_general(ip, _KEYPOOL)
            except OTXTransientError as e:
                log.warning("enrich_ip ASN transient-fail %s: %s", ip, e)
                info = None
            if info is not None:
                ckpt["asn_cache"][ip] = {"ts": now, **info}
                cached = ckpt["asn_cache"][ip]
        if cached and cached.get("asn_number"):
            writer.write_asn(
                ip=ip,
                asn_number=cached["asn_number"],
                asn_name=cached.get("asn_name", ""),
                country=cached.get("country", ""),
            )

    # Reverse pDNS (cached per run — don't re-query IPs we've already enriched)
    if do_reverse and ip not in ckpt["dns_cache"]:
        try:
            records = get_reverse_pdns(ip, _KEYPOOL, limit=REVERSE_PDNS_PER_IP)
        except OTXTransientError as e:
            log.warning("enrich_ip pDNS transient-fail %s: %s", ip, e)
            records = []
        for rec in records:
            writer.write_resolves_to(rec["domain"], ip, rec["first"], rec["last"])
        ckpt["dns_cache"][ip] = now


def enrich_domain(domain: str, writer: Neo4jWriter, ckpt: dict,
                  do_forward: bool = True, do_asn_on_ips: bool = True,
                  do_reverse_on_ips: bool = True) -> None:
    """Forward pDNS (domain→IPs) + recursive ASN/reverse enrichment on each IP."""
    if not do_forward:
        return
    try:
        records = get_forward_pdns(domain, _KEYPOOL, limit=FORWARD_PDNS_PER_DOMAIN)
    except OTXTransientError as e:
        log.warning("enrich_domain forward-pDNS transient-fail %s: %s", domain, e)
        records = []
    for rec in records:
        ip = rec["ip"]
        writer.write_resolves_to(domain, ip, rec["first"], rec["last"])
        enrich_ip(ip, writer, ckpt, do_asn=do_asn_on_ips, do_reverse=do_reverse_on_ips)


# ─── Pulse processing ────────────────────────────────────────────────

def process_pulse(pulse: dict, apt_name: str, writer: Neo4jWriter,
                  ckpt: dict, aliases: dict[str, str],
                  do_enrich: bool = True) -> tuple[bool, str]:
    """
    Write one pulse to Neo4j. Returns (wrote, reason_if_skipped).

    Applies paper-level filters BEFORE touching Neo4j so we don't
    pollute the graph with ambiguously-labeled or duplicate events.
    """
    pulse_id = pulse.get("id", "")

    # 1. Unambiguous-label filter (paper §IV-A)
    if not has_unambiguous_apt(pulse, apt_name, aliases):
        return False, "ambiguous_labels"

    # 2. Title-near-dup filter
    new_tokens = _title_tokens(pulse.get("name", ""))
    if new_tokens:
        for existing in writer.recent_titles_for_apt(apt_name, limit=500):
            if _jaccard(new_tokens, _title_tokens(existing)) >= TITLE_DEDUP_JACCARD:
                return False, f"near_dup_of[{existing[:60]}]"

    # 3. Compute DST + write Event
    indicators = pulse.get("indicators") or fetch_indicators(pulse_id)
    pulse["indicators"] = indicators
    dst = compute_dst(pulse, apt_name, aliases)
    writer.write_event(pulse, apt_name, dst)

    # 4. Write IOCs + buffer hosts for downstream enrichment
    domains, ips, urls = [], [], []
    for ind in indicators:
        val = ind.get("indicator", "").strip()
        if not val:
            continue
        itype = ind.get("type", "")
        ic = ind.get("created", "") or ""
        if itype in ("domain", "hostname"):
            writer.write_ioc_edge("Domain", val.lower(), pulse_id, ic)
            domains.append(val.lower())
        elif itype in ("IPv4", "IPv6"):
            writer.write_ioc_edge("IP", val, pulse_id, ic)
            ips.append(val)
        elif itype in ("URL", "URI"):
            writer.write_ioc_edge("URL", val, pulse_id, ic)
            urls.append(val)

    # 5. URL decomposition: URL → host → (HostedOn Domain, ResolvesTo IP)
    for url_val in urls:
        try:
            parsed = urlparse(url_val if "://" in url_val else f"http://{url_val}")
            host = (parsed.hostname or "").lower()
            if not host:
                continue
            if host.replace(".", "").isdigit():
                writer.write_url_resolves_to(url_val, host)
                if host not in ips:
                    ips.append(host)
            else:
                writer.write_hosted_on(url_val, host)
                if host not in domains:
                    domains.append(host)
        except Exception:
            continue

    # 6. Tier-1 enrichment — the part our earlier scripts skipped
    if do_enrich:
        # Primary IPs: ASN + reverse pDNS
        for ip in ips:
            enrich_ip(ip, writer, ckpt, do_asn=True, do_reverse=True)
        # Primary Domains: forward pDNS (pulls in more IPs, each chains ASN)
        for dom in domains[:40]:  # cap to avoid pathological pulses
            enrich_domain(dom, writer, ckpt,
                          do_forward=True, do_asn_on_ips=True, do_reverse_on_ips=True)

    return True, ""


# ─── Main loop ───────────────────────────────────────────────────────

def collect(apt_filter: list[str] | None,
            since: str | None, until: str | None,
            do_enrich: bool) -> None:
    global _KEYPOOL
    try:
        _KEYPOOL = key_pool_from_env()
    except ValueError as e:
        log.error(str(e))
        sys.exit(1)
    log.info("OTX key pool initialized with %d key(s)", len(_KEYPOOL))

    aliases = get_mitre_aliases()
    ckpt = load_checkpoint()
    # Make sure checkpoint has new keys even if loaded from older format
    ckpt.setdefault("asn_cache", {})
    ckpt.setdefault("dns_cache", {})
    save_checkpoint(ckpt)

    writer = Neo4jWriter()
    completed_apts = set(ckpt["completed_apts"])
    completed_pulses = set(ckpt["completed_pulse_ids"])

    targets = apt_filter or config.APT_GROUPS
    log.info("Collecting for APTs: %s", ", ".join(targets))
    log.info("Date window: since=%s until=%s  enrich=%s", since, until, do_enrich)

    for apt_name in targets:
        if apt_name in completed_apts:
            log.info("[SKIP] %s already fully processed", apt_name)
            continue

        log.info("\n=== %s ===", apt_name)

        # Search using APT name and all its MITRE aliases
        all_aliases = [apt_name] + [
            a for a, g in aliases.items() if g == apt_name
        ]
        seen_pulse_ids: set[str] = set()
        candidates: list[dict] = []
        for alias in sorted(set(all_aliases), key=str.lower):
            log.info("  searching: %r", alias)
            for page in range(1, MAX_SEARCH_PAGES + 1):
                batch = search_pulses(alias, page)
                if not batch:
                    break
                for r in batch:
                    pid = r.get("id", "")
                    if not pid or pid in seen_pulse_ids:
                        continue
                    created = r.get("created", "")
                    if since and created < since:
                        continue
                    if until and created >= until:
                        continue
                    seen_pulse_ids.add(pid)
                    candidates.append(r)
                time.sleep(0.5)

        log.info("  %d unique candidate pulses", len(candidates))

        processed_this_apt = 0
        for pulse_meta in candidates:
            if processed_this_apt >= MAX_PULSES_PER_APT:
                break
            pid = pulse_meta["id"]
            if pid in completed_pulses:
                continue

            log.info("  [%d] pulse %s — %s",
                     processed_this_apt + 1, pid[:10], (pulse_meta.get("name") or "")[:80])
            pulse = fetch_pulse(pid)
            if not pulse:
                skip_log.info("apt=%s pid=%s reason=fetch_failed", apt_name, pid)
                completed_pulses.add(pid)
                ckpt["completed_pulse_ids"] = list(completed_pulses)
                save_checkpoint(ckpt)
                time.sleep(PULSE_DELAY)
                continue

            try:
                wrote, reason = process_pulse(pulse, apt_name, writer, ckpt,
                                              aliases, do_enrich=do_enrich)
                if not wrote:
                    log.info("    skipped: %s", reason)
                    skip_log.info("apt=%s pid=%s reason=%s", apt_name, pid, reason)
            except Exception as e:
                log.exception("    ERROR on pulse %s: %s", pid, e)
                skip_log.info("apt=%s pid=%s reason=exception:%s", apt_name, pid, e)

            completed_pulses.add(pid)
            ckpt["completed_pulse_ids"] = list(completed_pulses)
            save_checkpoint(ckpt)
            processed_this_apt += 1
            time.sleep(PULSE_DELAY)

        completed_apts.add(apt_name)
        ckpt["completed_apts"] = list(completed_apts)
        save_checkpoint(ckpt)
        log.info("  %s done — processed %d pulses this run", apt_name, processed_this_apt)

    writer.close()
    log.info("\nALL TARGETS COMPLETE")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apt", action="append",
                   help="Restrict to this APT (can repeat). Default: config.APT_GROUPS.")
    p.add_argument("--since", default=None, help="Drop pulses created before this ISO date.")
    p.add_argument("--until", default=None, help="Drop pulses created on/after this ISO date.")
    p.add_argument("--skip-enrichment", action="store_true",
                   help="Skip ASN + pDNS lookups (pulse + indicators only).")
    args = p.parse_args()

    if args.apt:
        bad = [a for a in args.apt if a not in config.APT_GROUPS]
        if bad:
            log.error("Unknown APTs (not in config.APT_GROUPS): %s", bad)
            sys.exit(2)

    collect(
        apt_filter=args.apt,
        since=args.since,
        until=args.until,
        do_enrich=not args.skip_enrichment,
    )


if __name__ == "__main__":
    main()