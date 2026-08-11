"""Select actor-relevant source Events using the local MITRE ATT&CK taxonomy.

Selection is discovery control, not attribution truth. A source record is
eligible only when its explicit actor context resolves by exact name/alias to
one MITRE intrusion-set. Records resolving to multiple actors are retained in
the audit but excluded from the single-actor TRAIL compatibility path.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ClaimSource:
    name: str
    path: Path
    event_field: str
    label_field: str
    event_prefix: str | None = None


_MITRE_SUFFIX = re.compile(r"\s*-\s*G\d{4}\s*$", re.I)


def actor_key(value: Any) -> str:
    text = _MITRE_SUFFIX.sub("", str(value or "").strip())
    return " ".join(text.casefold().split())


def load_mitre_actor_index(bundle_path: Path) -> tuple[dict[str, set[tuple[str, str]]], int]:
    document = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    index: dict[str, set[tuple[str, str]]] = defaultdict(set)
    actor_count = 0
    for obj in document.get("objects", []):
        if (
            not isinstance(obj, dict)
            or obj.get("type") != "intrusion-set"
            or obj.get("revoked")
            or obj.get("x_mitre_deprecated")
        ):
            continue
        actor_count += 1
        actor_id = str(obj.get("id") or "")
        canonical = str(obj.get("name") or "").strip()
        for label in [canonical, *(obj.get("aliases") or [])]:
            key = actor_key(label)
            if key:
                index[key].add((actor_id, canonical))
    return dict(index), actor_count


def build_seed_selection(
    bundle_path: Path,
    sources: list[ClaimSource],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to mix selection runs: {output_dir}")
    actor_index, actor_count = load_mitre_actor_index(bundle_path)
    claims_by_event: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    source_counts: dict[str, dict[str, int]] = {}

    for source in sources:
        counts = {"claims": 0, "events": 0, "selected": 0, "multi_actor": 0, "unresolved": 0}
        seen_events: set[str] = set()
        with Path(source.path).open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                event_id = str(row.get(source.event_field) or "").strip()
                label = str(row.get(source.label_field) or "").strip()
                if not event_id or not label:
                    continue
                if source.event_prefix and not event_id.startswith(source.event_prefix):
                    continue
                seen_events.add(event_id)
                matches = sorted(actor_index.get(actor_key(label), set()))
                claims_by_event[(source.name, event_id)].append(
                    {
                        "line": line_number,
                        "raw_label": label,
                        "matches": [
                            {"mitre_id": actor_id, "canonical_name": name}
                            for actor_id, name in matches
                        ],
                    }
                )
                counts["claims"] += 1
        counts["events"] = len(seen_events)
        source_counts[source.name] = counts

    rows: list[dict[str, Any]] = []
    allowlist: dict[str, list[str]] = defaultdict(list)
    for (source, event_id), claims in sorted(claims_by_event.items()):
        resolved = {
            (match["mitre_id"], match["canonical_name"])
            for claim in claims
            for match in claim["matches"]
        }
        if len(resolved) == 1:
            status = "selected_unique_actor"
            allowlist[source].append(event_id)
            source_counts[source]["selected"] += 1
        elif len(resolved) > 1:
            status = "excluded_multi_actor"
            source_counts[source]["multi_actor"] += 1
        else:
            status = "excluded_unresolved"
            source_counts[source]["unresolved"] += 1
        rows.append(
            {
                "source": source,
                "source_event_id": event_id,
                "status": status,
                "resolved_actors": [
                    {"mitre_id": actor_id, "canonical_name": name}
                    for actor_id, name in sorted(resolved)
                ],
                "claims": claims,
                "usage": "event_discovery_only_not_model_label",
            }
        )

    output_dir.mkdir(parents=True)
    with (output_dir / "selection_audit.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    allowlist_value = {source: sorted(ids) for source, ids in sorted(allowlist.items())}
    (output_dir / "event_allowlist.json").write_text(
        json.dumps(allowlist_value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "format": "trail-mitre-seeded-event-selection",
        "format_version": 1,
        "mitre_bundle": str(bundle_path),
        "mitre_actor_count": actor_count,
        "selection_rule": "exact MITRE name/alias; exactly one resolved intrusion-set per source Event",
        "query_or_seed_is_attribution_label": False,
        "source_counts": source_counts,
        "files": ["event_allowlist.json", "selection_audit.jsonl"],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
