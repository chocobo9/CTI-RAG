"""Analyze MITRE ATT&CK enterprise-attack.json bundle and output object type statistics.

Includes relationship breakdown by (source_type, relationship_type, target_type).
"""

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "mitre"
BUNDLE_PATH = RAW_DIR / "enterprise-attack.json"
STATS_PATH = RAW_DIR / "bundle_stats.md"


def main():
    with open(BUNDLE_PATH, encoding="utf-8") as f:
        bundle = json.load(f)

    objects = bundle.get("objects", [])
    total = len(objects)
    type_counter = Counter(obj.get("type", "<missing>") for obj in objects)

    deprecated_by_type = Counter()
    revoked_by_type = Counter()
    for obj in objects:
        t = obj.get("type", "<missing>")
        if obj.get("x_mitre_deprecated", False):
            deprecated_by_type[t] += 1
        if obj.get("revoked", False):
            revoked_by_type[t] += 1

    sorted_types = type_counter.most_common()

    lines = []
    lines.append("# MITRE ATT&CK Bundle Statistics")
    lines.append("")
    lines.append(f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Source: `{BUNDLE_PATH.name}`")
    lines.append(f"Bundle ID: `{bundle.get('id', 'N/A')}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total objects**: {total}")
    lines.append(f"- **Distinct types**: {len(type_counter)}")
    lines.append(f"- **Total deprecated**: {sum(deprecated_by_type.values())}")
    lines.append(f"- **Total revoked**: {sum(revoked_by_type.values())}")
    lines.append("")
    lines.append("## Object Counts by Type")
    lines.append("")
    lines.append("| Type | Count | Deprecated | Revoked | Active |")
    lines.append("|------|------:|-----------:|--------:|-------:|")
    for obj_type, count in sorted_types:
        dep = deprecated_by_type.get(obj_type, 0)
        rev = revoked_by_type.get(obj_type, 0)
        active = count - dep - rev
        lines.append(f"| `{obj_type}` | {count} | {dep} | {rev} | {active} |")
    lines.append(
        f"| **Total** | **{total}** | **{sum(deprecated_by_type.values())}** | **{sum(revoked_by_type.values())}** | **{total - sum(deprecated_by_type.values()) - sum(revoked_by_type.values())}** |"
    )
    lines.append("")

    # --- Relationship breakdown ---
    def ref_type(ref: str) -> str:
        return ref.rsplit("--", 1)[0] if "--" in ref else ref

    rel_triple = Counter()
    rel_type_counter = Counter()
    for obj in objects:
        if obj.get("type") != "relationship":
            continue
        rtype = obj.get("relationship_type", "<unknown>")
        src = ref_type(obj.get("source_ref", ""))
        tgt = ref_type(obj.get("target_ref", ""))
        rel_triple[(src, rtype, tgt)] += 1
        rel_type_counter[rtype] += 1

    lines.append("## Relationship Types")
    lines.append("")
    lines.append("| relationship_type | Count |")
    lines.append("|-------------------|------:|")
    for rtype, cnt in rel_type_counter.most_common():
        lines.append(f"| `{rtype}` | {cnt} |")
    lines.append("")

    lines.append("## Relationship Breakdown (source → type → target)")
    lines.append("")
    lines.append("| Source Type | relationship_type | Target Type | Count |")
    lines.append("|------------|-------------------|-------------|------:|")
    for (src, rtype, tgt), cnt in rel_triple.most_common():
        lines.append(f"| `{src}` | `{rtype}` | `{tgt}` | {cnt} |")
    lines.append("")

    cti_triples = [
        ("intrusion-set", "uses", "attack-pattern"),
        ("intrusion-set", "uses", "malware"),
        ("intrusion-set", "uses", "tool"),
        ("campaign", "attributed-to", "intrusion-set"),
        ("campaign", "uses", "attack-pattern"),
        ("campaign", "uses", "malware"),
        ("campaign", "uses", "tool"),
    ]
    lines.append("## CTI-Relevant Relationships (attribution signal)")
    lines.append("")
    lines.append("| Triple | Count |")
    lines.append("|--------|------:|")
    cti_total = 0
    for src, rtype, tgt in cti_triples:
        cnt = rel_triple.get((src, rtype, tgt), 0)
        cti_total += cnt
        lines.append(f"| `{src}` → `{rtype}` → `{tgt}` | {cnt} |")
    lines.append(f"| **CTI-relevant total** | **{cti_total}** |")
    lines.append(f"| *All relationships* | *{sum(rel_type_counter.values())}* |")
    lines.append(
        f"| **CTI-relevant %** | **{cti_total / max(sum(rel_type_counter.values()), 1) * 100:.1f}%** |"
    )
    lines.append("")

    lines.append("## Type Descriptions")
    lines.append("")
    type_desc = {
        "attack-pattern": "ATT&CK Techniques and Sub-techniques",
        "campaign": "Named threat campaigns",
        "course-of-action": "Mitigations",
        "identity": "Identity objects (e.g. MITRE org)",
        "intrusion-set": "Threat groups / APTs",
        "malware": "Malware entries",
        "marking-definition": "TLP / copyright markings",
        "relationship": "Links between objects (uses, mitigates, etc.)",
        "tool": "Legitimate tools abused by adversaries",
        "x-mitre-collection": "ATT&CK collection metadata",
        "x-mitre-data-component": "Data components for detection",
        "x-mitre-analytic": "Detection analytics / rules",
        "x-mitre-data-source": "Data sources for detection",
        "x-mitre-detection-strategy": "Detection strategy guidance",
        "x-mitre-matrix": "ATT&CK matrix layout",
        "x-mitre-tactic": "ATT&CK tactics (columns in the matrix)",
    }
    for obj_type, _ in sorted_types:
        desc = type_desc.get(obj_type, "—")
        lines.append(f"- `{obj_type}`: {desc}")

    report = "\n".join(lines) + "\n"

    STATS_PATH.write_text(report, encoding="utf-8")

    print(report)
    print(f"--- Stats written to {STATS_PATH} ---")


if __name__ == "__main__":
    main()
