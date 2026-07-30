from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rag_cti.evitrail_delivery.enrichment import normalize_otx_enrichment_ledger
from scripts.normalize_evitrail_otx_enrichment import validate_output_paths


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_ip_general_indicator_is_normalized_to_ip_for_ip_in_asn_relation(
    tmp_path: Path,
) -> None:
    collection_root = tmp_path / "paper_model_22"
    raw_ref = "portable_raw/ip-general-task/response.json"
    _write_json(
        collection_root / raw_ref,
        {
            "fetched_at": "2026-07-29T13:02:06.667227+00:00",
            "source": "otx_ip_general",
            "source_id": "1.0.0.0",
            "payload": {
                "indicator": "1.0.0.0",
                "asn": "AS13335 cloudflare",
                "country_code": "AU",
            },
        },
    )
    ledger = collection_root / "enrichment_terminal_states.jsonl"
    _write_json(
        ledger,
        {
            "task_id": "ip-general-task",
            "endpoint": "ip_general",
            "seed_type": "ip",
            "value": "1.0.0.0",
            "status": "written",
            "raw_ref": raw_ref,
            "finished_at": "2026-07-29T15:26:31.672484+00:00",
        },
    )
    output = tmp_path / "normalized" / "otx_enrichment.jsonl"
    manifest = tmp_path / "normalized" / "manifest.json"

    result = normalize_otx_enrichment_ledger(
        ledger_path=ledger,
        output_path=output,
        manifest_path=manifest,
        subset_pulse_count=4_505,
    )

    assert _read_jsonl(output) == [
        {
            "asn": "AS13335 cloudflare",
            "asn_name": "cloudflare",
            "collected_at": "2026-07-29T13:02:06.667227+00:00",
            "collection_status": "written",
            "country_code": "AU",
            "endpoint": "ip_general",
            "finished_at": "2026-07-29T15:26:31.672484+00:00",
            "ioc": "1.0.0.0",
            "ioc_type": "ip",
            "ip": "1.0.0.0",
            "raw_ref": raw_ref,
            "source": "otx_ip_general",
            "task_id": "ip-general-task",
        }
    ]
    assert result["status_counts"] == {"written": 1}
    assert result["input"]["ledger_portable_ref"] == ledger.name
    assert result["input"]["ledger_sha256"] == hashlib.sha256(
        ledger.read_bytes()
    ).hexdigest()
    assert result["normalized_output"]["portable_ref"] == output.name
    assert result["normalized_output"]["sha256"] == hashlib.sha256(
        output.read_bytes()
    ).hexdigest()
    assert result["consumer_validation"] == {
        "reader": "evitrail.data.readers.read_cached_infrastructure",
        "revision": "da4a29e8ce25cff8cbddebb444b069296f949511",
        "scope": "not_run",
        "status": "not_run",
    }


def test_pdns_and_terminal_outcomes_remain_attachable_collection_evidence(
    tmp_path: Path,
) -> None:
    collection_root = tmp_path / "paper_model_22"
    reused_ref = "portable_raw/reused-task/response.json"
    empty_ref = "portable_raw/empty-task/response.json"
    _write_json(
        collection_root / reused_ref,
        {
            "fetched_at": "2026-06-15T23:49:35.731203+00:00",
            "source": "pdns",
            "source_id": "0141koppepan.com",
            "payload": {
                "count": 1,
                "passive_dns": [
                    {
                        "address": "172.67.147.85",
                        "asn": "AS13335 cloudflare",
                        "first": "2024-10-09T02:56:33",
                        "hostname": "0141koppepan.com",
                        "last": "2026-05-29T08:07:19",
                        "record_type": "A",
                    }
                ],
            },
        },
    )
    _write_json(
        collection_root / empty_ref,
        {
            "fetched_at": "2026-07-29T08:01:17.135674+00:00",
            "source": "otx_domain_pdns",
            "source_id": "252fwww.smartmatic.com",
            "payload": {"count": 0, "passive_dns": []},
        },
    )
    ledger = collection_root / "enrichment_terminal_states.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "attempts": 0,
            "endpoint": "domain_pdns",
            "finished_at": "2026-07-29T08:01:17.141064+00:00",
            "raw_ref": reused_ref,
            "seed_type": "domain",
            "source": "existing_local_pdns",
            "status": "reused",
            "task_id": "reused-task",
            "value": "0141koppepan.com",
        },
        {
            "attempts": 1,
            "endpoint": "domain_pdns",
            "finished_at": "2026-07-29T08:11:36.714302+00:00",
            "http_status": 200,
            "raw_ref": empty_ref,
            "seed_type": "domain",
            "source": "otx_domain_pdns",
            "status": "empty",
            "task_id": "empty-task",
            "value": "252fwww.smartmatic.com",
        },
        {
            "attempts": 7,
            "elapsed_seconds": 361.26908739999635,
            "endpoint": "domain_pdns",
            "error": {
                "kind": "ReadTimeout",
                "message": "The read operation timed out",
            },
            "finished_at": "2026-07-29T19:45:22.317933+00:00",
            "http_status": 0,
            "seed_type": "domain",
            "status": "retry_exhausted",
            "task_id": "retry-task",
            "value": "adobe.io",
        },
    ]
    ledger.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    output = tmp_path / "normalized" / "otx_enrichment.jsonl"
    manifest_path = tmp_path / "normalized" / "manifest.json"

    manifest = normalize_otx_enrichment_ledger(
        ledger_path=ledger,
        output_path=output,
        manifest_path=manifest_path,
        subset_pulse_count=4_505,
    )

    normalized = _read_jsonl(output)
    assert normalized[0]["domain"] == "0141koppepan.com"
    assert normalized[0]["ip"] == "172.67.147.85"
    assert normalized[0]["asn"] == "AS13335 cloudflare"
    assert normalized[0]["collection_status"] == "reused"
    assert normalized[1]["ioc"] == "252fwww.smartmatic.com"
    assert normalized[1]["ioc_type"] == "domain"
    assert normalized[1]["collection_status"] == "empty"
    assert normalized[1]["raw_ref"] == empty_ref
    assert normalized[2]["ioc"] == "adobe.io"
    assert normalized[2]["ioc_type"] == "domain"
    assert normalized[2]["collection_status"] == "retry_exhausted"
    assert normalized[2]["collection_error"] == {
        "kind": "ReadTimeout",
        "message": "The read operation timed out",
    }
    assert manifest["status_counts"] == {
        "empty": 1,
        "retry_exhausted": 1,
        "reused": 1,
    }
    assert manifest["coverage"] == {
        "full_snapshot_coverage": False,
        "scope": "partial",
        "subset_pulse_count": 4_505,
        "snapshot_pulse_count": 17_454,
    }


def test_normalizer_refuses_to_overwrite_versioned_artifacts(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "enrichment_terminal_states.jsonl"
    _write_json(
        ledger,
        {
            "endpoint": "domain_pdns",
            "seed_type": "domain",
            "status": "retry_exhausted",
            "task_id": "retry-task",
            "value": "adobe.io",
        },
    )
    output = tmp_path / "normalized.jsonl"
    manifest = tmp_path / "manifest.json"
    output.write_text("do not replace\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="versioned artifact"):
        normalize_otx_enrichment_ledger(
            ledger_path=ledger,
            output_path=output,
            manifest_path=manifest,
            subset_pulse_count=4_505,
        )

    assert output.read_text(encoding="utf-8") == "do not replace\n"
    assert not manifest.exists()


def test_cli_rejects_large_outputs_outside_f_data_collection(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match=r"F:\\DATA_COLLECTION"):
        validate_output_paths(
            tmp_path / "normalized.jsonl",
            tmp_path / "manifest.json",
        )
