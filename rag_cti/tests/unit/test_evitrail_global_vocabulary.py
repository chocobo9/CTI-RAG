from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from rag_cti.evitrail_delivery.vocabulary import (
    build_global_vocabulary,
    build_incremental_vocabulary,
    write_global_vocabulary,
)


def _evitrail_root() -> Path:
    configured = os.environ.get("EVITRAIL_ROOT")
    root = (
        Path(configured).resolve()
        if configured
        else (
            Path(__file__).resolve().parents[2]
            / "tmp"
            / "evitrial-delivery-builder-20260727"
        )
    )
    if not (root / "evitrail").is_dir():
        pytest.skip(
            "set EVITRAIL_ROOT to run exact-current-consumer integration checks"
        )
    return root


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _claim(
    event_id: str,
    source: str,
    actor: str,
    *,
    scope: str = "attribution",
    usage: str = "candidate",
) -> dict[str, object]:
    return {
        "claim_id": f"claim:{source}:{event_id}:{actor}",
        "event_id": event_id,
        "source": source,
        "raw_value": actor,
        "raw_ref": f"raw/{source}/{event_id}.json",
        "source_field": "adversary",
        "claim_scope": scope,
        "set_semantics": "singleton",
        "usage": usage,
    }


def test_global_vocabulary_uses_factual_cross_source_support_only(
    tmp_path: Path,
) -> None:
    claims = tmp_path / "source_claims.jsonl"
    _write_jsonl(
        claims,
        [
            _claim("event:otx:1", "otx", "New Actor"),
            _claim("event:circl_misp:2", "circl_misp", "New Actor"),
            _claim("event:otx:3", "otx", "Single Source"),
            _claim("event:otx:4", "otx", "Single Source"),
            _claim(
                "event:otx:5",
                "otx",
                "Query Only",
                scope="discovery_only",
                usage="provenance_only",
            ),
            _claim(
                "event:circl_misp:6",
                "circl_misp",
                "Query Only",
                scope="discovery_only",
                usage="provenance_only",
            ),
        ],
    )
    mitre = tmp_path / "enterprise-attack.json"
    _write_json(
        mitre,
        {
            "objects": [
                {
                    "type": "intrusion-set",
                    "name": name,
                    "aliases": [],
                    "external_references": [],
                }
                for name in ("New Actor", "Single Source", "Query Only")
            ]
        },
    )

    evitrail_root = _evitrail_root()
    result = build_global_vocabulary(
        claim_paths=[claims],
        evitrail_root=evitrail_root,
        initial_actors=["APT28"],
        mitre_path=mitre,
        malpedia_path=None,
        min_events=2,
        min_sources=2,
    )

    assert result["actors"] == ["APT28", "New Actor"]
    assert result["changes"]["added"] == ["New Actor"]
    assert {
        row["actor"]: row["decision"]
        for row in result["changes"]["decisions"]
    } == {
        "New Actor": "added",
        "Single Source": "insufficient_support",
    }
    assert result["changes"]["context_only_candidates"] == [
        {
            "actor": "Query Only",
            "event_count": 2,
            "source_count": 2,
            "sources": ["circl_misp", "otx"],
        }
    ]


def test_global_vocabulary_reads_native_malpedia_meta_synonyms(
    tmp_path: Path,
) -> None:
    claims = tmp_path / "source_claims.jsonl"
    _write_jsonl(
        claims,
        [
            _claim("event:otx:1", "otx", "Nested Alias"),
            _claim("event:circl_misp:2", "circl_misp", "Nested Alias"),
        ],
    )
    malpedia = tmp_path / "actors.json"
    _write_json(
        malpedia,
        {
            "native-key": {
                "value": "Malpedia Canonical",
                "meta": {"synonyms": ["Nested Alias"]},
            }
        },
    )

    result = build_global_vocabulary(
        claim_paths=[claims],
        evitrail_root=_evitrail_root(),
        initial_actors=["APT28"],
        mitre_path=None,
        malpedia_path=malpedia,
        min_events=2,
        min_sources=2,
    )

    assert result["actors"] == ["APT28", "Malpedia Canonical"]
    assert result["changes"]["added"] == ["Malpedia Canonical"]


def test_incremental_vocabulary_combines_frozen_and_delta_claims_only(
    tmp_path: Path,
) -> None:
    frozen_vocabulary = tmp_path / "actor_vocabulary.json"
    _write_json(
        frozen_vocabulary,
        {
            "version": "7",
            "actors": ["Legacy Actor A", "Legacy Actor B"],
        },
    )
    frozen_claims = tmp_path / "baseline" / "source_claims.jsonl"
    _write_jsonl(
        frozen_claims,
        [
            _claim("event:baseline:1", "baseline", "Incremental Actor"),
            _claim("event:conflict:1", "baseline", "Legacy Actor A"),
            _claim("event:conflict:1", "baseline", "Below Threshold"),
        ],
    )

    delta_claims = []
    for index, source in enumerate(("circl_misp", "d3fend", "malpedia", "mitre")):
        path = tmp_path / source / "source_claims.jsonl"
        rows = []
        if source == "mitre":
            rows.extend(
                [
                    _claim("event:unresolved:1", source, "Unmapped Name"),
                    _claim("event:ambiguous:1", source, "Shared Alias"),
                ]
            )
        else:
            rows.append(
                _claim(f"event:{source}:{index}", source, "Incremental Actor")
            )
        _write_jsonl(path, rows)
        delta_claims.append(path)

    future_otx_delta = tmp_path / "future-otx-delta" / "source_claims.jsonl"
    _write_jsonl(
        future_otx_delta,
        [_claim("event:otx:future", "otx", "Incremental Actor")],
    )
    # Invalid sibling data proves this interface does not scan the handoff.
    (future_otx_delta.parent / "indicators.jsonl").write_text(
        "not-json\n",
        encoding="utf-8",
    )
    (future_otx_delta.parent / "pdns.jsonl").write_text(
        "not-json\n",
        encoding="utf-8",
    )
    (future_otx_delta.parent / "asn.jsonl").write_text(
        "not-json\n",
        encoding="utf-8",
    )

    mitre = tmp_path / "enterprise-attack.json"
    _write_json(
        mitre,
        {
            "objects": [
                {
                    "type": "intrusion-set",
                    "name": "Incremental Actor",
                    "aliases": [],
                    "external_references": [],
                },
                {
                    "type": "intrusion-set",
                    "name": "Below Threshold",
                    "aliases": [],
                    "external_references": [],
                },
                {
                    "type": "intrusion-set",
                    "name": "Ambiguous Actor A",
                    "aliases": ["Shared Alias"],
                    "external_references": [],
                },
                {
                    "type": "intrusion-set",
                    "name": "Ambiguous Actor B",
                    "aliases": ["Shared Alias"],
                    "external_references": [],
                },
            ]
        },
    )
    evitrail_root = _evitrail_root()

    result = build_incremental_vocabulary(
        frozen_vocabulary_path=frozen_vocabulary,
        frozen_claim_paths=[frozen_claims],
        delta_claim_paths=[*delta_claims, future_otx_delta],
        evitrail_root=evitrail_root,
        mitre_path=mitre,
        malpedia_path=None,
    )

    assert result["actors"] == [
        "Legacy Actor A",
        "Legacy Actor B",
        "Incremental Actor",
    ]
    assert result["vocabulary"]["version"] == "7"
    assert result["changes"]["added"] == ["Incremental Actor"]
    assert result["changes"]["unresolved"] == {"Unmapped Name": 1}
    assert result["changes"]["ambiguous_aliases"] == {"Shared Alias": 1}
    assert result["changes"]["insufficient_support"] == [
        {
            "actor": "Below Threshold",
            "event_count": 1,
            "source_count": 1,
            "sources": ["baseline"],
            "decision": "insufficient_support",
        }
    ]
    assert result["changes"]["original_actors"] == [
        "Legacy Actor A",
        "Legacy Actor B",
    ]


def test_global_vocabulary_writes_versioned_portable_artifacts(
    tmp_path: Path,
) -> None:
    result = {
        "actors": ["APT28", "New Actor"],
        "vocabulary": {"actors": ["APT28", "New Actor"]},
        "changes": {"added": ["New Actor"], "decisions": []},
    }

    output = write_global_vocabulary(
        result=result,
        output_dir=tmp_path / "vocabulary",
        consumer_revision="da4a29e8ce25cff8cbddebb444b069296f949511",
        claim_refs=[
            "otx/shard-00000/source_claims.jsonl",
            "other-sources/source_claims.jsonl",
        ],
        min_events=5,
        min_sources=2,
    )

    vocabulary = json.loads(
        (output / "actor_vocabulary.json").read_text(encoding="utf-8")
    )
    changes = json.loads(
        (output / "vocabulary_changes.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (output / "manifest.json").read_text(encoding="utf-8")
    )
    assert vocabulary == {"actors": ["APT28", "New Actor"]}
    assert changes["added"] == ["New Actor"]
    assert manifest["format"] == "evitrail-global-actor-vocabulary"
    assert manifest["policy"] == {
        "claim_scope": "attribution",
        "usage_excluded": "provenance_only",
        "min_distinct_events": 5,
        "min_distinct_sources": 2,
    }
    assert manifest["claim_refs"] == [
        "other-sources/source_claims.jsonl",
        "otx/shard-00000/source_claims.jsonl",
    ]
    assert "D:\\" not in json.dumps(manifest)
