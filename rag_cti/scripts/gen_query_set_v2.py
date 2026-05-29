"""Generate query_set_v2.jsonl per eval/CLAUDE.md spec.

Step 1: Clean 21 existing queries with gold_attack_ids
Step 2: Generate relationship queries from mitre.jsonl
Step 3: Generate OTX actor/malware queries from otx.jsonl
Step 4: (eval script update is separate)
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
EVAL_DIR = BASE / "data" / "eval"
PROCESSED = BASE / "data" / "processed"
OUTPUT = EVAL_DIR / "query_set_v2.jsonl"


def step1_clean_existing():
    """Keep only queries with non-empty gold_attack_ids, drop expected_chunk_ids."""
    src = EVAL_DIR / "query_set_hybrid.jsonl"
    kept = []
    with open(src, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            if obj.get("gold_attack_ids"):
                obj.pop("expected_chunk_ids", None)
                obj.pop("reference_answer", None)
                kept.append(obj)
    assert len(kept) == 21, f"Expected 21, got {len(kept)}"
    return kept


def step2_relationship_queries():
    """Generate relationship queries from MITRE technique chunks that mention actors."""
    import re

    actor_pattern = re.compile(
        r"(APT\s?29|APT\s?28|APT\s?38|APT\s?1(?!\d)|APT\s?41|Lazarus|Turla|"
        r"Kimsuky|FIN7|OilRig|Sandworm|MuddyWater)"
    )

    pairs = []
    with open(PROCESSED / "mitre.jsonl", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            content = obj.get("content", "")
            meta = obj.get("metadata", {})
            actors = actor_pattern.findall(content)
            if actors:
                attack_id = meta.get("attack_id", "")
                name = meta.get("name", "")
                tactics = meta.get("tactics", [])
                if isinstance(tactics, str):
                    tactics = [t.strip() for t in tactics.split(",")]
                pairs.append({
                    "actor": actors[0].replace(" ", ""),
                    "attack_id": attack_id,
                    "technique_name": name,
                    "tactics": tactics,
                })

    tactic_map = {
        "collection": [],
        "command-and-control": [],
        "credential-access": [],
        "defense-evasion": [],
        "discovery": [],
        "execution": [],
        "exfiltration": [],
        "impact": [],
        "initial-access": [],
        "lateral-movement": [],
        "persistence": [],
        "privilege-escalation": [],
        "reconnaissance": [],
        "resource-development": [],
    }
    for p in pairs:
        for t in p["tactics"]:
            if t in tactic_map:
                tactic_map[t].append(p)

    selected = []
    seen_attack_ids = set()

    for tactic, items in tactic_map.items():
        for item in items:
            if item["attack_id"] not in seen_attack_ids and len(selected) < 18:
                selected.append((tactic, item))
                seen_attack_ids.add(item["attack_id"])
                break

    tactic_friendly = {
        "collection": "collect data",
        "command-and-control": "establish command and control",
        "credential-access": "steal credentials",
        "defense-evasion": "evade defenses",
        "discovery": "discover systems and networks",
        "execution": "execute code",
        "exfiltration": "exfiltrate data",
        "impact": "cause damage",
        "initial-access": "gain initial access",
        "lateral-movement": "move laterally",
        "persistence": "maintain persistence",
        "privilege-escalation": "escalate privileges",
        "reconnaissance": "perform reconnaissance",
        "resource-development": "prepare attack infrastructure",
    }

    direct_templates = [
        "What techniques does {actor} use to {tactic_desc}?",
        "How does {actor} {tactic_desc} in targeted operations?",
        "What methods has {actor} employed for {tactic_desc_noun}?",
    ]

    reverse_templates = [
        "Which threat actors have been observed using {technique}?",
        "What groups are known to leverage {technique} in their campaigns?",
        "Which APT groups employ {technique} during attacks?",
    ]

    tactic_desc_noun = {
        "collection": "intelligence collection",
        "command-and-control": "command-and-control communication",
        "credential-access": "credential theft",
        "defense-evasion": "defense evasion",
        "discovery": "network discovery",
        "execution": "code execution",
        "exfiltration": "data exfiltration",
        "impact": "destructive impact",
        "initial-access": "initial access",
        "lateral-movement": "lateral movement",
        "persistence": "establishing persistence",
        "privilege-escalation": "privilege escalation",
        "reconnaissance": "reconnaissance",
        "resource-development": "infrastructure preparation",
    }

    queries = []
    counter = 1

    for tactic, item in selected:
        actor = item["actor"]
        technique = item["technique_name"]
        attack_id = item["attack_id"]
        t_desc = tactic_friendly.get(tactic, tactic)
        t_noun = tactic_desc_noun.get(tactic, tactic)

        template_idx = (counter - 1) % len(direct_templates)
        direct_q = direct_templates[template_idx].format(
            actor=actor, tactic_desc=t_desc, tactic_desc_noun=t_noun
        )
        queries.append({
            "query_id": f"R{counter:03d}",
            "query": direct_q,
            "category": "relationship_direct",
            "gold_attack_ids": [attack_id],
            "gold_sources": ["mitre"],
            "gold_actor": actor,
            "gold_pulse_id": None,
            "gold_malware": None,
            "notes": f"Direct: {actor} -> {attack_id} ({technique}), tactic={tactic}",
        })
        counter += 1

    reverse_pairs = [
        ("APT29", "T1649", "Steal or Forge Authentication Certificates", "credential-access"),
        ("Turla", "T1205.002", "Socket Filters", "defense-evasion"),
        ("Lazarus", "T1218.013", "Mavinject", "defense-evasion"),
        ("Kimsuky", "T1056.001", "Keylogging", "credential-access"),
        ("APT29", "T1098.005", "Device Registration", "persistence"),
    ]

    for actor, attack_id, technique, tactic in reverse_pairs:
        template_idx = (counter - 1) % len(reverse_templates)
        reverse_q = reverse_templates[template_idx].format(technique=technique)
        queries.append({
            "query_id": f"R{counter:03d}",
            "query": reverse_q,
            "category": "relationship_reverse",
            "gold_attack_ids": [attack_id],
            "gold_sources": ["mitre"],
            "gold_actor": actor,
            "gold_pulse_id": None,
            "gold_malware": None,
            "notes": f"Reverse: {technique} ({attack_id}) <- {actor}, tactic={tactic}",
        })
        counter += 1

    return queries


def step3_otx_queries():
    """Generate OTX actor and malware queries from otx.jsonl."""
    import re

    actor_pulses = {}
    malware_pulses = {}

    with open(PROCESSED / "otx.jsonl", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            content = obj.get("content", "")
            meta = obj.get("metadata", {})
            pulse_id = meta.get("pulse_id", "")

            m = re.search(r"Attributed to ([^.]+)\.", content)
            if m:
                actor = m.group(1).strip()
                if actor and actor != "[Unnamed group]":
                    actor_pulses.setdefault(actor, []).append(pulse_id)

            m = re.search(r"Associated malware: ([^.]+)\.", content)
            if m:
                for name in m.group(1).split(", "):
                    name = name.strip()
                    if name and name not in ("Windows", "Win", "Android", "JavaScript", "Remote Access"):
                        malware_pulses.setdefault(name, []).append(pulse_id)

    top_actors = sorted(actor_pulses.items(), key=lambda x: -len(x[1]))[:8]
    top_malware = sorted(malware_pulses.items(), key=lambda x: -len(x[1]))[:8]

    actor_templates = [
        "threat intelligence on {actor} campaigns and TTPs",
        "recent {actor} cyber espionage operations",
        "indicators of compromise associated with {actor}",
        "How has {actor} targeted organizations in recent campaigns?",
        "{actor} attack infrastructure and tooling",
        "What sectors does {actor} typically target?",
        "Overview of {actor} operations and attributed attacks",
        "{actor} known command-and-control infrastructure",
    ]

    malware_templates = [
        "{malware} malware indicators and attribution",
        "How is {malware} deployed in targeted attacks?",
        "detection and analysis of {malware} payloads",
        "{malware} capabilities and associated threat actors",
        "indicators of compromise for {malware} infections",
        "What campaigns have used {malware} as a payload?",
        "{malware} technical analysis and behavioral indicators",
        "How does {malware} establish persistence on victim systems?",
    ]

    queries = []
    counter = 1

    for i, (actor, pulses) in enumerate(top_actors[:7]):
        q_text = actor_templates[i].format(actor=actor)
        queries.append({
            "query_id": f"O{counter:03d}",
            "query": q_text,
            "category": "otx_actor",
            "gold_attack_ids": [],
            "gold_sources": ["otx"],
            "gold_actor": actor,
            "gold_pulse_id": pulses[0],
            "gold_malware": None,
            "notes": f"Actor appears in {len(pulses)} OTX pulses",
        })
        counter += 1

    for i, (malware, pulses) in enumerate(top_malware[:7]):
        if malware in ("Kimsuky",):
            continue
        q_text = malware_templates[i].format(malware=malware)
        queries.append({
            "query_id": f"O{counter:03d}",
            "query": q_text,
            "category": "otx_malware",
            "gold_attack_ids": [],
            "gold_sources": ["otx"],
            "gold_actor": None,
            "gold_pulse_id": pulses[0],
            "gold_malware": malware,
            "notes": f"Malware appears in {len(pulses)} OTX pulses",
        })
        counter += 1

    return queries


def main():
    existing = step1_clean_existing()
    print(f"Step 1: {len(existing)} cleaned existing queries")

    relationship = step2_relationship_queries()
    print(f"Step 2: {len(relationship)} relationship queries")

    otx = step3_otx_queries()
    print(f"Step 3: {len(otx)} OTX queries")

    all_queries = existing + relationship + otx
    print(f"Total: {len(all_queries)} queries")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        for q in all_queries:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"Written to {OUTPUT}")

    # Verify
    categories = {}
    for q in all_queries:
        cat = q["category"]
        categories[cat] = categories.get(cat, 0) + 1
    print("\nCategory breakdown:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
