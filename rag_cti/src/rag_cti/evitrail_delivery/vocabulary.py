"""Build one global actor vocabulary with the current EviTRAIL policy."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def build_global_vocabulary(
    *,
    claim_paths: Iterable[Path],
    evitrail_root: Path,
    initial_actors: list[str],
    mitre_path: Path | None,
    malpedia_path: Path | None,
    min_events: int = 5,
    min_sources: int = 2,
    mode: str = "update",
) -> dict[str, Any]:
    """Apply EviTRAIL's own alias and support policy across all claim files."""

    return _build_vocabulary(
        claim_paths=claim_paths,
        evitrail_root=evitrail_root,
        initial_actors=initial_actors,
        vocabulary_version="1",
        mitre_path=mitre_path,
        malpedia_path=malpedia_path,
        min_events=min_events,
        min_sources=min_sources,
        mode=mode,
    )


def build_incremental_vocabulary(
    *,
    frozen_vocabulary_path: Path,
    frozen_claim_paths: Iterable[Path],
    delta_claim_paths: Iterable[Path],
    evitrail_root: Path,
    mitre_path: Path | None,
    malpedia_path: Path | None,
    min_events: int = 5,
    min_sources: int = 2,
    mode: str = "update",
) -> dict[str, Any]:
    """Update a frozen vocabulary from cumulative actor-claim files only.

    The frozen claims remain in the support calculation so that a later delta
    can satisfy the existing distinct-event and distinct-source thresholds.
    Callers provide exact claim files; this function does not discover or read
    handoff indicators or enrichment data.
    """

    payload = json.loads(Path(frozen_vocabulary_path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        actors = payload
        version = "1"
    elif isinstance(payload, dict) and isinstance(payload.get("actors"), list):
        actors = payload["actors"]
        version = str(payload.get("version", "1"))
    else:
        raise ValueError("frozen vocabulary must be a list or contain an actors list")

    return _build_vocabulary(
        claim_paths=[*frozen_claim_paths, *delta_claim_paths],
        evitrail_root=evitrail_root,
        initial_actors=[str(actor) for actor in actors],
        vocabulary_version=version,
        mitre_path=mitre_path,
        malpedia_path=malpedia_path,
        min_events=min_events,
        min_sources=min_sources,
        mode=mode,
    )


def _build_vocabulary(
    *,
    claim_paths: Iterable[Path],
    evitrail_root: Path,
    initial_actors: list[str],
    vocabulary_version: str,
    mitre_path: Path | None,
    malpedia_path: Path | None,
    min_events: int,
    min_sources: int,
    mode: str,
) -> dict[str, Any]:
    root_text = str(Path(evitrail_root).resolve())
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    from evitrail.data.aliases import AliasMap
    from evitrail.data.schema import ActorClaim, Provenance
    from evitrail.data.vocabulary import ActorVocabulary

    claims: list[ActorClaim] = []
    for claim_path in claim_paths:
        with Path(claim_path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                raw_name = str(row.get("raw_value") or row.get("raw_name") or "").strip()
                event_id = str(row.get("event_id") or "").strip()
                source = str(row.get("source") or "").strip()
                if not raw_name or not event_id or not source:
                    continue
                record_path = str(
                    row.get("source_field")
                    or row.get("record_path")
                    or f"line[{line_number}]"
                )
                provenance = Provenance(
                    source=source,
                    raw_ref=str(
                        row.get("raw_ref")
                        or f"source_claims.jsonl:line[{line_number}]"
                    ),
                    record_path=record_path,
                    source_record_id=str(row.get("source_record_id") or event_id),
                    collected_at=row.get("fetched_at") or row.get("collected_at"),
                )
                claims.append(
                    ActorClaim(
                        claim_id=str(
                            row.get("claim_id")
                            or f"claim:{source}:{event_id}:{line_number}"
                        ),
                        event_id=event_id,
                        source=source,
                        raw_name=raw_name,
                        provenance=provenance,
                        scope=str(row.get("claim_scope") or row.get("scope") or "attribution"),
                        set_semantics=str(row.get("set_semantics") or "singleton"),
                        usage=str(row.get("usage") or "candidate"),
                    )
                )

    vocabulary = ActorVocabulary(
        list(initial_actors),
        version=vocabulary_version,
    )
    aliases = AliasMap.from_files(
        list(initial_actors),
        str(malpedia_path) if malpedia_path else None,
        str(mitre_path) if mitre_path else None,
    )
    if malpedia_path:
        _add_malpedia_meta_synonyms(aliases, malpedia_path)
    changes = vocabulary.process_claims(
        claims,
        aliases,
        mode=mode,
        min_events=min_events,
        min_sources=min_sources,
    )
    return {
        "actors": list(vocabulary.actors),
        "vocabulary": vocabulary.to_dict(),
        "changes": changes,
    }


def _add_malpedia_meta_synonyms(aliases: Any, path: Path) -> None:
    """Add aliases stored in Malpedia's native ``meta.synonyms`` field.

    The pinned EviTRAIL consumer reads only top-level alias fields.  Current
    Malpedia actor snapshots keep their synonyms one level deeper, so bridge
    that schema gap while retaining EviTRAIL's own collision handling.
    """

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("actors"), (dict, list)):
        payload = payload["actors"]
    items = payload.values() if isinstance(payload, dict) else payload
    if not isinstance(items, list) and not hasattr(items, "__iter__"):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        canonical = str(
            item.get("value")
            or item.get("common_name")
            or item.get("name")
            or ""
        ).strip()
        meta = item.get("meta")
        synonyms = meta.get("synonyms") if isinstance(meta, dict) else None
        if canonical and isinstance(synonyms, list):
            aliases.add_actor(
                canonical,
                [str(name) for name in synonyms if name],
                "malpedia",
            )


def write_global_vocabulary(
    *,
    result: dict[str, Any],
    output_dir: Path,
    consumer_revision: str,
    claim_refs: Iterable[str],
    min_events: int,
    min_sources: int,
) -> Path:
    """Write the shared vocabulary and its reproducible policy contract."""

    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")

    portable_refs = sorted({str(ref).replace("\\", "/") for ref in claim_refs})
    absolute_refs = [ref for ref in portable_refs if Path(ref).is_absolute()]
    if absolute_refs:
        raise ValueError(f"claim_refs must be portable: {absolute_refs[0]}")

    output_dir.mkdir(parents=True)
    _write_json(output_dir / "actor_vocabulary.json", result["vocabulary"])
    _write_json(output_dir / "vocabulary_changes.json", result["changes"])
    _write_json(
        output_dir / "manifest.json",
        {
            "format": "evitrail-global-actor-vocabulary",
            "format_version": 1,
            "consumer": "Mitraaaaa/Evitrial",
            "consumer_revision": consumer_revision,
            "actor_count": len(result["actors"]),
            "claim_refs": portable_refs,
            "policy": {
                "claim_scope": "attribution",
                "usage_excluded": "provenance_only",
                "min_distinct_events": min_events,
                "min_distinct_sources": min_sources,
            },
        },
    )
    return output_dir


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
