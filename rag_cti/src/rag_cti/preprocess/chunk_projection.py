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

from rag_cti.ingest.normalize import NormalizedRecord, SourceClass
from rag_cti.preprocess.entity_registry import resolve_entity_ids, resolve_relations
from rag_cti.preprocess.indicator_index import indicator_entity_id
from rag_cti.preprocess.infra_relations import build_infra_relations


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
    entity_ids = resolve_entity_ids(entity_mentions, ontology_nodes)
    relations = resolve_relations(record.relation_mentions, ontology_nodes)
    # Field sources (1 record = 1 chunk = 1 keying indicator): that indicator IS the
    # chunk's entity and belongs in entity_ids so the chunk is joinable by it
    # (retrieval §4/§5). Narrative sources keep their *bulk* indicators OUT of the
    # payload (decision 2026-06 / knowledge §3 invariant 6) — only field sources here.
    if record.classification == SourceClass.INFRASTRUCTURE:
        indicator_ids = {indicator_entity_id(m) for m in record.indicator_mentions}
        # Infrastructure facts (domain→ip resolves-to, ip→asn belongs-to, …) come
        # from the structured field-source record carried in metadata. Endpoint ids
        # are minted directly (infra_relations), so entity_ids and relations[]
        # endpoints stay equal — never via the generic resolver's orphan scheme.
        infra = build_infra_relations(record.metadata)
        entity_ids = sorted(set(entity_ids) | indicator_ids | set(infra["entity_ids"]))
        relations = relations + infra["relations"]
    return {
        "source_type": record.provenance.source_type,
        "attack_ids": attack_ids,
        "entity_ids": entity_ids,
        "relations": relations,
    }
