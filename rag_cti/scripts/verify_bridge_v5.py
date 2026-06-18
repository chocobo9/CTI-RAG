"""Phase-0 bridge probe: do supports.evidence_id values resolve to live v5 chunks?

Standalone (stdlib uuid + qdrant_client only): samples evidence_ids evenly from
supports.jsonl, maps each via chunk_to_point_id's uuid5 scheme, retrieves from
cti_chunks_v5, and reports (a) point-present rate and (b) payload.id round-trip
match. Deterministic sampling (no RNG). Precursor to FactStore.verify_bridge.
"""

from __future__ import annotations

import json
import uuid

from qdrant_client import QdrantClient

NS = uuid.UUID("d7b3a5a6-4f72-4e86-9b88-2e5f5d8a1c3e")  # qdrant_store._QDRANT_ID_NAMESPACE
SUPPORTS = (
    "/mnt/d/proj/CTI-RAG/.claude/worktrees/optimization/rag_cti/"
    "data/processed/v5_staging/supports.jsonl"
)
COLLECTION = "cti_chunks_v5"
SAMPLE = 300


def main() -> None:
    with open(SUPPORTS, encoding="utf-8") as fh:
        lines = fh.readlines()
    total = len(lines)
    step = max(1, total // SAMPLE)

    eids: list[str] = []
    seen: set[str] = set()
    for i in range(0, total, step):
        eid = json.loads(lines[i])["evidence_id"]
        if eid not in seen:
            seen.add(eid)
            eids.append(eid)
        if len(eids) >= SAMPLE:
            break

    pid_to_eid = {str(uuid.uuid5(NS, e)): e for e in eids}
    client = QdrantClient(url="http://localhost:6333")
    records = client.retrieve(collection_name=COLLECTION, ids=list(pid_to_eid), with_payload=["id"])

    present = len(records)
    correct = sum(1 for r in records if (r.payload or {}).get("id") == pid_to_eid.get(str(r.id)))
    n = len(eids)
    print(f"supports.jsonl rows           : {total}")
    print(f"sampled distinct evidence_ids : {n}")
    print(f"point present in v5           : {present}  ({100 * present / n:.1f}%)")
    print(f"payload.id round-trip matches : {correct}  ({100 * correct / n:.1f}%)")


if __name__ == "__main__":
    main()
