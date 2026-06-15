"""Chunk payload projection — entity_id filter keys + relation triples (retrieval §4).

Projects a :class:`NormalizedRecord`'s typed mentions into the retrieval payload's
filter fields: ``source_type``, ``attack_ids``, ``entity_ids``, and ``relations``
(entity_id triples). Reuses the M1 registry so the payload carries **stable ids,
never strings** — which is what makes payload-index pre-filtering (M2 §4/§6) and
the bridge to the knowledge layer possible. Pure projection: no embedding, no
Qdrant. entity_ids hold only the chunk's *own* mentions (actor/family/technique/
location), never the full indicator set (the vector store is not the system of
record — knowledge §3 invariant 6 / decision 2026-06).
"""

from __future__ import annotations

from typing import Any

from rag_cti.ingest.normalize import NormalizedRecord
from rag_cti.preprocess.entity_registry import resolve_entity_ids, resolve_relations


def project_chunk(record: NormalizedRecord, ontology_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Project one normalized record into payload filter fields.

    Returns ``{source_type, attack_ids, entity_ids, relations}`` with entity_ids
    and relations resolved to stable ids via the M1 registry (orphans included —
    a chunk's edges are never dropped). ``attack_ids`` is the technique-mention
    projection kept verbatim for direct ``attack_id`` filtering.
    """
    entity_mentions = [(m.name, m.type) for m in record.entity_mentions]
    attack_ids = sorted(
        {m.name for m in record.entity_mentions if m.type == "technique" and m.name}
    )
    return {
        "source_type": record.provenance.source_type,
        "attack_ids": attack_ids,
        "entity_ids": resolve_entity_ids(entity_mentions, ontology_nodes),
        "relations": resolve_relations(record.relation_mentions, ontology_nodes),
    }
