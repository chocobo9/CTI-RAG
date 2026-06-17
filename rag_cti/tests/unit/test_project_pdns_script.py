from __future__ import annotations

import json
from pathlib import Path

from scripts.project_pdns import project_pdns


def test_project_pdns_writes_processed_chunks(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "pdns"
    domain_dir = raw_dir / "example.com"
    domain_dir.mkdir(parents=True)
    (domain_dir / "snapshot.json").write_text(
        json.dumps(
            {
                "fetched_at": "2026-06-15T23:33:16.707732+00:00",
                "source_id": "example.com",
                "payload": {
                    "passive_dns": [
                        {
                            "address": "1.2.3.4",
                            "asn": "AS12345 BadISP",
                            "hostname": "example.com",
                            "record_type": "A",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    out_path = tmp_path / "processed" / "pdns.jsonl"

    stats = project_pdns(raw_dir=raw_dir, out_path=out_path)

    assert stats.documents == 1
    assert stats.chunks == 1
    row = json.loads(out_path.read_text(encoding="utf-8"))
    assert row["source"] == "pdns"
    assert row["metadata"]["domain"] == "example.com"
    assert row["metadata"]["ip_addresses"] == ["1.2.3.4"]
    assert "Passive DNS history for domain example.com." in row["content"]
    # The projection now rides along: infra edges in the payload, not just prose.
    assert row["metadata"]["source_type"] == "pdns"
    rels = row["metadata"]["relations"]
    preds = {r["predicate"] for r in rels}
    assert "resolves-to" in preds  # domain -> ip
    assert "belongs-to" in preds  # ip -> asn
    # every relation endpoint is also an entity_id (the consistency invariant)
    endpoints = {r["subject_id"] for r in rels} | {r["object_id"] for r in rels}
    assert endpoints <= set(row["metadata"]["entity_ids"])
