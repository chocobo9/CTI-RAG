from __future__ import annotations

from rag_cti.preprocess.entity_registry import (
    asn_entity_id,
    location_entity_id,
    resolve_entity_ids,
)
from rag_cti.preprocess.indicator_index import indicator_entity_id
from rag_cti.preprocess.indicators import IndicatorMention
from rag_cti.preprocess.infra_relations import (
    BELONGS_TO,
    HAS_SUBDOMAIN,
    LOCATED_IN,
    RESOLVES_TO,
    USES_NAMESERVER,
    build_infra_relations,
)

# A realistic pDNS-projected record (shape from project_pdns_raw): one A record
# carrying asn+country, one NS record, one subdomain.
_RECORD = {
    "domain": "0-02.net",
    "resolutions": [
        {
            "value": "23.111.191.180",
            "ip": "23.111.191.180",
            "record_type": "A",
            "asn": "AS29802",
            "asn_name": "hivelocity inc.",
            "country": "United States",
        },
        {
            "value": "ns12.1-19.net",
            "ip": "",
            "record_type": "NS",
            "asn": "AS29802",
            "country": "United States",
        },
    ],
    "subdomains": ["www.0-02.net"],
}


def _triples(result: dict[str, list]) -> set[tuple[str, str, str]]:
    return {(r["subject_id"], r["predicate"], r["object_id"]) for r in result["relations"]}


def test_build_infra_relations_emits_all_edge_kinds() -> None:
    result = build_infra_relations(_RECORD)
    triples = _triples(result)

    domain = indicator_entity_id(IndicatorMention("0-02.net", "domain", "domain"))
    ip = indicator_entity_id(IndicatorMention("23.111.191.180", "ipv4", "ipv4"))
    ns = indicator_entity_id(IndicatorMention("ns12.1-19.net", "domain", "domain"))
    sub = indicator_entity_id(IndicatorMention("www.0-02.net", "domain", "domain"))
    asn = asn_entity_id("AS29802")
    country = location_entity_id("United States")

    assert (domain, RESOLVES_TO, ip) in triples
    assert (ip, BELONGS_TO, asn) in triples
    assert (ip, LOCATED_IN, country) in triples
    assert (domain, USES_NAMESERVER, ns) in triples
    assert (domain, HAS_SUBDOMAIN, sub) in triples


def test_every_relation_endpoint_is_in_entity_ids() -> None:
    # The core invariant: relations[] endpoints and entity_ids[] are the same ids.
    result = build_infra_relations(_RECORD)
    endpoints = {r["subject_id"] for r in result["relations"]} | {
        r["object_id"] for r in result["relations"]
    }
    assert endpoints <= set(result["entity_ids"])


def test_located_in_endpoint_matches_otx_location_resolution() -> None:
    # The endpoint-consistency trap: a country reached via pDNS located-in must be
    # the SAME entity as the same country reached via OTX targets→location (which
    # goes through resolve_entity_ids' orphan path). If these diverge, the graph
    # silently splits one country into two nodes.
    otx_location = resolve_entity_ids([("United States", "location")], [])[0]
    assert location_entity_id("United States") == otx_location


def test_asn_id_is_deterministic_and_case_insensitive() -> None:
    assert asn_entity_id("AS29802") == asn_entity_id("as29802  ")
    assert asn_entity_id("AS29802") != asn_entity_id("AS36351")
    assert asn_entity_id("AS29802").startswith("asn_")


def test_no_domain_yields_empty() -> None:
    assert build_infra_relations({"resolutions": [{"value": "1.2.3.4"}]}) == {
        "entity_ids": [],
        "relations": [],
    }


def test_empty_resolutions_yields_only_domain_entity() -> None:
    result = build_infra_relations({"domain": "x.com", "resolutions": [], "subdomains": []})
    assert result["relations"] == []
    assert result["entity_ids"] == [
        indicator_entity_id(IndicatorMention("x.com", "domain", "domain"))
    ]
