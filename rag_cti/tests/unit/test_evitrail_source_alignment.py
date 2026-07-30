from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_cti.evitrail_delivery.source_handoff import build_source_handoff
from rag_cti.evitrail_delivery.sources import (
    align_source_record,
    iter_jsonl_evidence,
)
from scripts.build_evitrail_source_handoff import (
    resolve_storage_path,
)


def test_orkl_alignment_preserves_collection_time_iocs_and_each_actor_relation() -> None:
    record = {
        "normalization_version": "orkl-v1",
        "report_id": "orkl:report:00007130-a1ca-4f6e-af36-44f78a8fdd8c",
        "source_record_id": "00007130-a1ca-4f6e-af36-44f78a8fdd8c",
        "title": "US Cyber Command issues alert about hackers exploiting Outlook vulnerability",
        "description": "Archived report body",
        "fetched_at": "2026-07-16T22:42:57.075440Z",
        "modified_at": "2026-07-16T02:18:58.174164Z",
        "published_at": "0001-01-01T00:00:00Z",
        "raw_ref": (
            "raw/reports/00007130-a1ca-4f6e-af36-44f78a8fdd8c/"
            "afc840d6c51ad3d1bdd517787b4e15ccb3d4cab93c2d75d8a4811b8437d7903c.json"
        ),
    }
    iocs = [
        {
            "ioc_type": "URL",
            "ioc_value": "hxxps://customermgmt[.]net/page/macrocosm",
            "ioc_value_raw": "hxxps://customermgmt[.]net/page/macrocosm",
            "source_field": "plain_text[1:48]",
            "raw_ref": record["raw_ref"],
            "extraction_method": "deterministic_regex",
        }
    ]
    claims = [
        {
            "raw_label": "APT33",
            "source_location": "threat_actors[1]",
            "raw_ref": record["raw_ref"],
        },
        {
            "raw_label": "APT33",
            "source_location": "threat_actors[2]",
            "raw_ref": record["raw_ref"],
        },
        {
            "raw_label": "APT 33",
            "source_location": "threat_actors[3]",
            "raw_ref": record["raw_ref"],
        },
    ]

    aligned = align_source_record("orkl", record, ioc_rows=iocs, claim_rows=claims)

    assert aligned.event == {
        "event_id": "event:orkl:00007130-a1ca-4f6e-af36-44f78a8fdd8c",
        "source": "orkl",
        "source_record_id": "00007130-a1ca-4f6e-af36-44f78a8fdd8c",
        "title": record["title"],
        "description": record["description"],
        "raw_ref": record["raw_ref"],
        "modified": "2026-07-16T02:18:58.174164Z",
        "fetched_at": "2026-07-16T22:42:57.075440Z",
    }
    assert aligned.indicators == (
        {
            "type": "url",
            "value": "https://customermgmt.net/page/macrocosm",
            "raw_value": "hxxps://customermgmt[.]net/page/macrocosm",
            "raw_ref": record["raw_ref"],
            "record_path": "plain_text[1:48]",
            "derivation": "deterministic_regex",
        },
    )
    assert [claim["raw_value"] for claim in aligned.claims] == [
        "APT33",
        "APT33",
        "APT 33",
    ]
    assert [claim["source_field"] for claim in aligned.claims] == [
        "threat_actors[1]",
        "threat_actors[2]",
        "threat_actors[3]",
    ]
    assert {claim["claim_scope"] for claim in aligned.claims} == {"report_context"}
    assert {claim["usage"] for claim in aligned.claims} == {"provenance_only"}
    assert {claim["set_semantics"] for claim in aligned.claims} == {"set"}
    assert [row["reason"] for row in aligned.rejections] == ["invalid_source_timestamp"]


def test_misp_alignment_restores_sidecar_time_and_all_structured_actor_claims() -> None:
    record = {
        "normalization_version": "circl-misp-v1",
        "event_id": "circl-misp:event:dbc619e5-1b69-44c6-81d0-7fb79390bde4",
        "source_uuid": "dbc619e5-1b69-44c6-81d0-7fb79390bde4",
        "title": '"Hanger Bulletin": UAC-0001 (APT28)',
        "event_date": "2026-02-01",
        "modified_at": "2026-02-04T13:23:10Z",
        "published_at": "2026-02-04T13:23:47Z",
        "fetched_at": "2026-07-11T20:33:30.275513Z",
        "raw_ref": "raw/events/dbc619e5-1b69-44c6-81d0-7fb79390bde4.json",
    }
    iocs = [
        {
            "ioc_type": "Domain",
            "ioc_value": "wellnesscaremed.com",
            "ioc_value_raw": "wellnesscaremed[.]com",
            "source_field": "Event.Attribute[14]",
            "last_seen": "2026-02-02T13:17:02Z",
        },
        {
            "ioc_type": "FileHash-SHA256",
            "ioc_value": "a" * 64,
            "source_field": "Event.Attribute[15]",
        },
    ]
    claims = [
        {
            "raw_label": "APT28 - G0007",
            "source_field": "Event.Tag[1].name",
            "raw_ref": record["raw_ref"],
            "claim_kind": "galaxy_actor_context",
        },
        {
            "raw_label": "APT28",
            "source_field": "Event.Tag[3].name",
            "raw_ref": record["raw_ref"],
            "claim_kind": "galaxy_actor_context",
        },
        {
            "raw_label": "Sofacy",
            "source_field": "Event.Tag[6].name",
            "raw_ref": record["raw_ref"],
            "claim_kind": "galaxy_actor_context",
        },
    ]

    aligned = align_source_record("circl_misp", record, ioc_rows=iocs, claim_rows=claims)

    assert aligned.event == {
        "event_id": "event:circl_misp:dbc619e5-1b69-44c6-81d0-7fb79390bde4",
        "source": "circl_misp",
        "source_record_id": "dbc619e5-1b69-44c6-81d0-7fb79390bde4",
        "title": record["title"],
        "description": "",
        "raw_ref": record["raw_ref"],
        "event_time": "2026-02-01",
        "modified": "2026-02-04T13:23:10Z",
        "published": "2026-02-04T13:23:47Z",
        "fetched_at": "2026-07-11T20:33:30.275513Z",
    }
    assert aligned.indicators == (
        {
            "type": "domain",
            "value": "wellnesscaremed.com",
            "raw_value": "wellnesscaremed[.]com",
            "raw_ref": record["raw_ref"],
            "record_path": "Event.Attribute[14]",
            "derivation": "source_asserted",
            "timestamps": {"last_seen": "2026-02-02T13:17:02Z"},
        },
    )
    assert [claim["raw_value"] for claim in aligned.claims] == [
        "APT28 - G0007",
        "APT28",
        "Sofacy",
    ]
    assert {claim["claim_scope"] for claim in aligned.claims} == {"attribution"}
    assert {claim["usage"] for claim in aligned.claims} == {"candidate"}
    assert {claim["set_semantics"] for claim in aligned.claims} == {"set"}
    assert aligned.rejections[0]["reason"] == "unsupported_or_invalid_indicator"
    assert aligned.rejections[0]["record_path"] == "Event.Attribute[15]"


def test_aptnotes_alignment_uses_stable_report_identity_and_explicit_text_evidence() -> None:
    report_id = "aptnotes:report:25e44caab7943e7c51c6c2b68797d41608088c4675e75684a314b21146ce0f18"
    record = {
        "normalization_version": "aptnotes-v1",
        "report_id": report_id,
        "title": '"Wicked Rose" And The Ncph Hacking Group',
        "publisher": "iDefense",
        "listed_date": "12/01/2006",
        "fetched_at": "2026-07-12T08:00:27.164737Z",
        "original_url": "https://app.box.com/s/0cp8nyd339dnbak96x2klgz1kxm36xd2",
        "raw_metadata_ref": "raw/repository/APTnotes.json",
    }
    iocs = [
        {
            "ioc_type": "URL",
            "ioc_value": "http://www.study-in-china.org/school/Sichuan/suse/",
            "ioc_value_raw": "http://www.study-in-china.org/school/Sichuan/suse/",
            "raw_ref": (
                "extracted/text/"
                "25e44caab7943e7c51c6c2b68797d41608088c4675e75684a314b21146ce0f18.txt"
            ),
            "character_start": 2708,
            "character_end": 2758,
            "extraction_method": "deterministic_regex",
        }
    ]
    claims = [
        {
            "raw_actor_text": "Wicked Rose",
            "raw_ref": (
                "extracted/text/"
                "25e44caab7943e7c51c6c2b68797d41608088c4675e75684a314b21146ce0f18.txt"
            ),
            "character_start": 6596,
            "character_end": 6607,
            "extraction_method": "explicit_pattern",
            "resolution_status": "unresolved",
            "claim_excerpt": "attacks linked to Wicked Rose and the NCPH hacking group",
        }
    ]

    aligned = align_source_record("aptnotes", record, ioc_rows=iocs, claim_rows=claims)

    assert aligned.event == {
        "event_id": f"event:aptnotes:{report_id}",
        "source": "aptnotes",
        "source_record_id": report_id,
        "title": record["title"],
        "description": "",
        "raw_ref": "raw/repository/APTnotes.json",
        "published": "2006-12-01",
        "fetched_at": "2026-07-12T08:00:27.164737Z",
        "publisher": "iDefense",
        "references": [record["original_url"]],
    }
    assert aligned.indicators[0]["record_path"] == "characters[2708:2758]"
    assert aligned.claims[0]["source_field"] == "characters[6596:6607]"
    assert aligned.claims[0]["raw_value"] == "Wicked Rose"
    assert aligned.claims[0]["claim_scope"] == "report_context"
    assert aligned.claims[0]["usage"] == "provenance_only"
    assert aligned.claims[0]["properties"] == {
        "claim_excerpt": "attacks linked to Wicked Rose and the NCPH hacking group",
        "extraction_method": "explicit_pattern",
        "resolution_status": "unresolved",
    }
    assert aligned.rejections == ()


def test_cisa_alignment_keeps_text_actor_candidates_context_only() -> None:
    record = {
        "normalization_version": "cisa-v1",
        "report_id": "cisa:advisory:AA23-108",
        "source_record_id": "AA23-108",
        "title": "People's Republic of China State-Sponsored Cyber Actor",
        "summary": "Joint cybersecurity advisory.",
        "canonical_url": ("https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-108"),
        "raw_html_ref": "raw/html/AA23-108.html",
        "published_at": "2023-04-18T00:00:00Z",
        "updated_at": "2023-04-18T00:00:00Z",
        "fetched_at": "2026-07-12T08:04:12.205836Z",
        "issuing_organizations": ["CISA", "NSA"],
        "reference_urls": ["https://example.test/source"],
    }
    iocs = [
        {
            "ioc_type": "IP",
            "ioc_value": "198.51.100.9",
            "ioc_value_raw": "198[.]51[.]100[.]9",
            "raw_ref": "extracted/text/AA23-108.txt",
            "source_field": "characters[800:812]",
            "extraction_method": "deterministic_regex",
        }
    ]
    claims = [
        {
            "raw_actor_text": "Nation-State Actor",
            "raw_ref": "raw/html/AA23-108.html",
            "section_heading": "Tags",
            "claim_modality": "explicit",
            "claim_excerpt": "Nation-State Actor: Russia",
            "resolution_status": "unresolved",
        }
    ]

    aligned = align_source_record("cisa", record, ioc_rows=iocs, claim_rows=claims)

    assert aligned.event == {
        "event_id": "event:cisa:cisa:advisory:AA23-108",
        "source": "cisa",
        "source_record_id": "cisa:advisory:AA23-108",
        "title": record["title"],
        "description": "Joint cybersecurity advisory.",
        "raw_ref": "raw/html/AA23-108.html",
        "published": "2023-04-18T00:00:00Z",
        "modified": "2023-04-18T00:00:00Z",
        "fetched_at": "2026-07-12T08:04:12.205836Z",
        "issuing_organizations": ["CISA", "NSA"],
        "references": ["https://example.test/source"],
    }
    assert aligned.indicators[0]["type"] == "ip"
    assert aligned.indicators[0]["value"] == "198.51.100.9"
    assert aligned.claims[0]["claim_scope"] == "report_context"
    assert aligned.claims[0]["usage"] == "provenance_only"
    assert aligned.claims[0]["properties"]["claim_modality"] == "explicit"


def test_cisa_attachment_is_evidence_for_an_advisory_not_an_event() -> None:
    attachment = {
        "attachment_id": "cisa:attachment:0014c42855af99ec",
        "report_id": "cisa:advisory:AA20-106A",
        "fetch_status": "failed",
        "fetched_at": "2026-07-12T08:04:26.063838Z",
        "source_url": "https://www.us-cert.gov/advisory.pdf",
    }

    aligned = align_source_record("cisa", attachment)

    assert aligned.event is None
    assert aligned.rejections == (
        {
            "source": "cisa",
            "raw_ref": "https://www.us-cert.gov/advisory.pdf",
            "record_path": "record",
            "reason": "not_report_event",
            "raw_type": "cisa_attachment_or_non_advisory",
        },
    )


def test_invalid_jsonl_evidence_becomes_an_explicit_rejection(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source_actor_claim_candidates.jsonl"
    path.write_text(
        json.dumps({"report_id": "aptnotes:report:one"}) + "\n"
        '{"report_id":"aptnotes:report:broken","claim_excerpt":"unterminated}\n',
        encoding="utf-8",
    )

    evidence = list(iter_jsonl_evidence(path, source="aptnotes"))

    assert evidence[0].record == {"report_id": "aptnotes:report:one"}
    assert evidence[0].rejection is None
    assert evidence[1].record is None
    assert evidence[1].rejection == {
        "source": "aptnotes",
        "raw_ref": str(path),
        "record_path": "line[2]",
        "reason": "invalid_json",
        "raw_type": "jsonl",
    }


def test_invalid_url_port_is_rejected_without_aborting_the_source_record() -> None:
    aligned = align_source_record(
        "orkl",
        {
            "source_record_id": "bad-url",
            "title": "Bad URL evidence",
            "raw_ref": "raw/reports/bad-url.json",
        },
        ioc_rows=[
            {
                "ioc_type": "URL",
                "ioc_value": "http://example.test:not-a-port/path",
                "source_field": "plain_text[0:40]",
            }
        ],
    )

    assert aligned.event is not None
    assert aligned.indicators == ()
    assert [row["reason"] for row in aligned.rejections] == ["unsupported_or_invalid_indicator"]


def test_url_with_non_domain_hostname_is_rejected_by_consumer_rules() -> None:
    aligned = align_source_record(
        "orkl",
        {
            "source_record_id": "bad-host",
            "title": "Bad hostname evidence",
            "raw_ref": "raw/reports/bad-host.json",
        },
        ioc_rows=[
            {
                "ioc_type": "URL",
                "ioc_value": "https://not_a_domain/path",
                "source_field": "plain_text[0:25]",
            }
        ],
    )

    assert aligned.indicators == ()
    assert aligned.rejections[0]["reason"] == "unsupported_or_invalid_indicator"


def test_source_roots_build_a_strict_five_file_handoff(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    processed_root = tmp_path / "processed"
    output = tmp_path / "handoff"
    fixtures = {
        "orkl": {
            "record_file": "reports.jsonl",
            "record": {
                "normalization_version": "orkl-v1",
                "source_record_id": "orkl-one",
                "title": "ORKL report",
                "fetched_at": "2026-01-02T00:00:00Z",
                "raw_ref": "raw/reports/orkl-one.json",
            },
            "claim_file": "source_actor_claims.jsonl",
            "claim": {
                "subject_record_id": "orkl:report:orkl-one",
                "raw_label": "Context Actor",
                "source_location": "threat_actors[0]",
            },
            "processed_source": "orkl",
            "ioc_id": "orkl-one",
        },
        "circl_misp": {
            "record_file": "events.jsonl",
            "record": {
                "normalization_version": "circl-misp-v1",
                "source_uuid": "misp-one",
                "title": "MISP event",
                "event_date": "2026-01-01",
                "fetched_at": "2026-01-02T00:00:00Z",
                "raw_ref": "raw/events/misp-one.json",
            },
            "claim_file": "source_actor_claims.jsonl",
            "claim": {
                "event_id": "circl-misp:event:misp-one",
                "raw_label": "Direct Actor",
                "source_field": "Event.Tag[0].name",
            },
            "processed_source": "misp",
            "ioc_id": "circl-misp:event:misp-one",
        },
        "aptnotes": {
            "record_file": "reports.jsonl",
            "record": {
                "normalization_version": "aptnotes-v1",
                "report_id": "aptnotes:report:one",
                "title": "APTnotes report",
                "listed_date": "01/03/2026",
                "fetched_at": "2026-01-04T00:00:00Z",
                "raw_metadata_ref": "raw/repository/APTnotes.json",
            },
            "claim_file": "source_actor_claim_candidates.jsonl",
            "claim": {
                "report_id": "aptnotes:report:one",
                "raw_actor_text": "Narrative Actor",
                "extraction_method": "explicit_pattern",
            },
            "processed_source": "aptnotes",
            "ioc_id": "aptnotes:report:one",
        },
        "cisa": {
            "record_file": "advisories.jsonl",
            "record": {
                "normalization_version": "cisa-v1",
                "report_id": "cisa:advisory:one",
                "title": "CISA advisory",
                "published_at": "2026-01-05T00:00:00Z",
                "fetched_at": "2026-01-06T00:00:00Z",
                "raw_html_ref": "raw/html/one.html",
            },
            "claim_file": "source_actor_claim_candidates.jsonl",
            "claim": {
                "report_id": "cisa:advisory:one",
                "raw_actor_text": "Generic threat actor",
            },
            "processed_source": "cisa",
            "ioc_id": "cisa:advisory:one",
        },
    }
    for source, fixture in fixtures.items():
        normalized = raw_root / source / "normalized"
        normalized.mkdir(parents=True)
        (normalized / fixture["record_file"]).write_text(
            json.dumps(fixture["record"]) + "\n", encoding="utf-8"
        )
        (normalized / fixture["claim_file"]).write_text(
            json.dumps(fixture["claim"]) + "\n", encoding="utf-8"
        )
        evidence = (
            processed_root / "normalized" / fixture["processed_source"] / "ioc_evidence.jsonl"
        )
        evidence.parent.mkdir(parents=True)
        evidence.write_text(
            json.dumps(
                {
                    "source_record_id": fixture["ioc_id"],
                    "ioc_type": "Domain",
                    "ioc_value": f"{source.replace('_', '-')}.example",
                    "source_field": "body[0:10]",
                }
            )
            + "\n",
            encoding="utf-8",
        )

    misp_raw = raw_root / "circl_misp" / "raw" / "events" / "misp-one.json"
    misp_raw.parent.mkdir(parents=True)
    misp_raw.write_text(
        json.dumps(
            {
                "Event": {
                    "uuid": "misp-one",
                    "Object": [
                        {
                            "Attribute": [
                                {"type": "ip-dst", "value": "198.51.100.8"},
                                {"type": "AS", "value": "13335"},
                            ]
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    result = build_source_handoff(
        raw_root=raw_root,
        processed_root=processed_root,
        output_dir=output,
        work_dir=tmp_path / "work",
    )

    assert {path.name for path in output.iterdir()} == {
        "nodes.jsonl",
        "edges.jsonl",
        "events.jsonl",
        "source_claims.jsonl",
        "rejected_records.jsonl",
    }

    def rows(name: str) -> list[dict[str, object]]:
        return [
            json.loads(line) for line in (output / name).read_text(encoding="utf-8").splitlines()
        ]

    assert result["events"] == 4
    assert len(rows("events.jsonl")) == 4
    assert {row["type"] for row in rows("nodes.jsonl")} == {
        "event",
        "domain",
        "ip",
        "asn",
    }
    edges = rows("edges.jsonl")
    assert len(edges) == 5
    assert next(
        row for row in edges if row["relation"] == "ip_in_asn"
    )["evidence"][0] == {
        "derivation": "source_asserted_object_relation",
        "raw_ref": "raw/events/misp-one.json",
        "record_path": "Event.Object[0]",
        "source": "circl_misp",
    }
    claims = rows("source_claims.jsonl")
    assert {(row["source"], row["claim_scope"], row["usage"]) for row in claims} == {
        ("orkl", "report_context", "provenance_only"),
        ("circl_misp", "attribution", "candidate"),
        ("aptnotes", "report_context", "provenance_only"),
        ("cisa", "report_context", "provenance_only"),
    }


def test_large_build_cli_allows_any_storage_root_by_default(tmp_path: Path) -> None:
    handoff_dir = tmp_path / "handoff"

    assert resolve_storage_path(handoff_dir) == handoff_dir.resolve()


def test_large_build_cli_enforces_explicit_storage_root(tmp_path: Path) -> None:
    storage_root = tmp_path / "data_collection"
    handoff_dir = storage_root / "evitrail" / "handoff"

    assert resolve_storage_path(handoff_dir, storage_root) == handoff_dir.resolve()

    with pytest.raises(ValueError, match="large handoff output/work must be under"):
        resolve_storage_path(tmp_path / "outside" / "handoff", storage_root)
