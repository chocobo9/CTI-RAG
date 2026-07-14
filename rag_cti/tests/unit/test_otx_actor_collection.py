from __future__ import annotations

from rag_cti.connectors.otx_actor_collection import (
    indicator_page_source_id,
    mitre_actor_seeds_from_bundle,
    normalize_query,
    otx_queries_from_mitre_actor_seeds,
    search_raw_source_id,
    search_raw_source_id_for_query,
    search_results,
)


def test_mitre_actor_seeds_from_bundle_extracts_intrusion_sets_only() -> None:
    bundle = {
        "objects": [
            {"type": "x-mitre-collection", "x_mitre_version": "18.1"},
            {
                "type": "intrusion-set",
                "id": "intrusion-set--apt28",
                "name": "APT28",
                "aliases": ["APT28", "Fancy Bear", "Sofacy", "sofacy", ""],
                "external_references": [{"source_name": "mitre-attack", "external_id": "G0007"}],
            },
            {
                "type": "intrusion-set",
                "id": "intrusion-set--revoked",
                "name": "Old Actor",
                "revoked": True,
                "external_references": [{"source_name": "mitre-attack", "external_id": "G9999"}],
            },
            {
                "type": "malware",
                "id": "malware--x",
                "name": "Not An Actor",
                "external_references": [{"source_name": "mitre-attack", "external_id": "S0001"}],
            },
        ]
    }

    seeds = mitre_actor_seeds_from_bundle(bundle)

    assert len(seeds) == 1
    seed = seeds[0]
    assert seed.name == "APT28"
    assert seed.mitre_id == "G0007"
    assert seed.stix_id == "intrusion-set--apt28"
    assert seed.aliases == ("Fancy Bear", "Sofacy")
    assert seed.attack_version == "18.1"
    assert seed.queries == ("APT28", "Fancy Bear", "Sofacy")


def test_raw_source_ids_are_stable_and_separate_endpoint_grains() -> None:
    seed = mitre_actor_seeds_from_bundle(
        {
            "objects": [
                {
                    "type": "intrusion-set",
                    "id": "intrusion-set--apt28",
                    "name": "APT28",
                    "aliases": ["Fancy Bear"],
                    "external_references": [
                        {"source_name": "mitre-attack", "external_id": "G0007"}
                    ],
                }
            ]
        }
    )[0]

    assert search_raw_source_id(seed, "Fancy Bear", 1) == search_raw_source_id(
        seed, "Fancy Bear", 1
    )
    assert search_raw_source_id(seed, "Fancy Bear", 1) != search_raw_source_id(seed, "APT28", 1)
    assert search_raw_source_id_for_query("fancy bear", 1) == search_raw_source_id_for_query(
        "fancy bear", 1
    )
    assert search_raw_source_id_for_query("fancy bear", 1) != search_raw_source_id_for_query(
        "fancy bear", 2
    )
    assert search_raw_source_id_for_query(
        "fancy bear", 1, 20
    ) != search_raw_source_id_for_query("fancy bear", 1, 100)
    assert indicator_page_source_id("pulse-1", 1) == indicator_page_source_id("pulse-1", 1)
    assert indicator_page_source_id("pulse-1", 1) != indicator_page_source_id("pulse-1", 2)


def test_otx_queries_dedupe_aliases_and_preserve_actor_associations() -> None:
    seeds = mitre_actor_seeds_from_bundle(
        {
            "objects": [
                {
                    "type": "intrusion-set",
                    "id": "intrusion-set--one",
                    "name": "Actor One",
                    "aliases": ["Shared Alias", "Unique One"],
                    "external_references": [
                        {"source_name": "mitre-attack", "external_id": "G0001"}
                    ],
                },
                {
                    "type": "intrusion-set",
                    "id": "intrusion-set--two",
                    "name": "Actor Two",
                    "aliases": ["shared  alias", "Unique Two"],
                    "external_references": [
                        {"source_name": "mitre-attack", "external_id": "G0002"}
                    ],
                },
            ]
        }
    )

    queries = otx_queries_from_mitre_actor_seeds(seeds)
    by_norm = {query.query_normalized: query for query in queries}

    assert normalize_query(" Shared   Alias ") == "shared alias"
    assert set(by_norm) == {
        "actor one",
        "actor two",
        "shared alias",
        "unique one",
        "unique two",
    }
    shared = by_norm["shared alias"]
    assert shared.query == "Shared Alias"
    assert [actor.mitre_attack_id for actor in shared.actors] == ["G0001", "G0002"]
    assert [actor.matched_from for actor in shared.actors] == ["alias", "alias"]


def test_search_results_returns_only_rows_with_pulse_ids() -> None:
    payload = {
        "results": [
            {"id": "pulse-1", "name": "one"},
            {"name": "missing id"},
            "bad row",
            {"id": "pulse-2", "name": "two"},
        ]
    }

    rows = search_results(payload)

    assert [row["id"] for row in rows] == ["pulse-1", "pulse-2"]
