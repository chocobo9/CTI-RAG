"""Unit tests for the entity-shaped indicator index (decision 2026-06)."""

from __future__ import annotations

from rag_cti.preprocess.indicator_index import build_indicator_index, indicator_entity_id
from rag_cti.preprocess.indicators import IndicatorMention


def test_entity_id_deterministic_and_kind_keyed():
    m1 = IndicatorMention("evil.com", "domain", "domain")
    assert indicator_entity_id(m1) == indicator_entity_id(
        IndicatorMention("evil.com", "domain", "domain")
    )
    assert indicator_entity_id(m1).startswith("indicator_")
    # same value, different kind => different entity (never silently merged)
    m2 = IndicatorMention("evil.com", "hostname", None)
    assert indicator_entity_id(m1) != indicator_entity_id(m2)


def test_build_index_dedups_and_collects_source_ids():
    per_source = [
        (
            "pulseA",
            [
                IndicatorMention("evil.com", "domain", "domain"),
                IndicatorMention("h1", "FileHash-SHA256", "hash-sha256"),
            ],
        ),
        ("pulseB", [IndicatorMention("evil.com", "domain", "domain")]),
    ]
    by_val = {r["value"]: r for r in build_indicator_index(per_source)}
    assert by_val["evil.com"]["source_ids"] == ["pulseA", "pulseB"]
    assert by_val["evil.com"]["type"] == "indicator"
    assert by_val["evil.com"]["indicator_type"] == "domain"
    assert by_val["evil.com"]["canonical_type"] == "domain"
    assert by_val["evil.com"]["ontology_id"] is None
    assert by_val["h1"]["source_ids"] == ["pulseA"]


def test_unmapped_type_preserved_in_index():
    rec = build_indicator_index([("p", [IndicatorMention("host.x", "hostname", None)])])[0]
    assert rec["indicator_type"] == "hostname"
    assert rec["canonical_type"] is None


def test_actor_ids_not_fabricated():
    rec = build_indicator_index([("p", [IndicatorMention("evil.com", "domain", "domain")])])[0]
    assert "actor_ids" not in rec  # interface deferred to M1, not fabricated


def test_output_is_deterministically_ordered():
    per_source = [
        (
            "p",
            [IndicatorMention("b", "domain", "domain"), IndicatorMention("a", "domain", "domain")],
        )
    ]
    eids = [r["entity_id"] for r in build_indicator_index(per_source)]
    assert eids == sorted(eids)
