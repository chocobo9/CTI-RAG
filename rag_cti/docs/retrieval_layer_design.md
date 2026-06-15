# CTI-RAG Retrieval-Layer Design

Spec for **Layer 1 (retrieval)**. Companion to `docs/knowledge_layer_design.md`
(Layer 2/3). This document exists to remove the ambiguity that caused the
earlier drafts to keep collapsing the two layers into one.

Terms: `docs/CONTEXT.md`. Each item is tagged **[existing]** (already in the repo)
or **[change]** (this refactor adds it).

---

## 1. Responsibility boundary (read this first)

The retrieval layer answers one question: **"which chunks are relevant to this
query?"** — by semantic similarity and metadata filtering. Nothing else.

It is **not** the system of record. The knowledge layer is. Concretely, the
retrieval layer:

- does **not** mint `entity_id`s — it consumes ids the Entity registry produced.
- does **not** resolve aliases — `apt 29 → actor_0016` already happened upstream.
- does **not** store confidence as truth — confidence lives on `supports`.
- does **not** version the ontology — it reads ontology edges, never owns them.

The fields `labels[]`, `entities[]`, `relations[]` appear in *both* layers. In
the retrieval layer they are **denormalized projections** in the chunk payload so
Qdrant can filter fast. Their system-of-record depends on the milestone: **until
the knowledge layer's Fact/supports tables exist (M3), the per-doc `relations[]`
projection IS the only source** — it is built directly from normalized mentions
at ingest, and "rebuild from the knowledge layer" / "knowledge layer wins" has no
referent yet. **Once M3 exists**, the knowledge layer becomes the system of
record and the payload becomes a cache rebuilt from it. Do not write M2 code that
reads from a Fact/supports table that M2 does not build.

**The bridge:** a retrieval chunk's `id` equals `supports.evidence_id` — but
`supports` is an M3 object. At M2 the chunk id is just the stable chunk id; the
bridge becomes meaningful when M3 emits supports rows keyed by it. One chunk =
one Evidence (this is the evidence unit in both layers — a Document that splits
into N chunks yields N evidences, not one).

---

## 2. Unit and store

- The indexed unit is the **Chunk**, not the Document. A Document (a PDF, a
  pulse) is provenance; the Chunk is what gets embedded and retrieved.
  **[existing]** — `preprocess/chunking.py`, `types.Chunk`.
- Store is **Qdrant**, one collection, per point: a dense vector, a sparse
  vector, and a payload. **[existing]** — `store/qdrant_store.py`.
- The vector store holds **only** what retrieval needs. It is never the home of
  the Fact/Entity/ontology tables. **[existing intent, enforced here]**

---

## 3. Current retrieval pipeline **[existing]**

Grounded in the repo as-is:

- **Dense**: BGE-M3 (`BAAI/bge-m3`) via sentence-transformers → dense vector.
  `embeddings/embedder.py`, `retrieval/dense_retriever.py`.
- **Sparse**: a separate BM25 encoder with an **IOC-preserving tokenizer**
  (does not shatter hashes/domains/IPs), IDF persisted to
  `data/sparse_vocab.json`. `retrieval/bm25.py`, `retrieval/sparse_retriever.py`.
  Note: the sparse vector is BM25, **not** BGE-M3's native sparse/colbert head.
- **Fusion**: weighted Reciprocal Rank Fusion, dense weight `alpha`, sparse
  `1 - alpha`. `retrieval/fusion.py`, `retrieval/hybrid_retriever.py`.
- **Rerank**: cross-encoder over the fused candidates → final top-k.
  `retrieval/reranker.py`.
- **HyDE**: optional hypothetical-document expansion on the query side.
  `retrieval/hyde.py`.
- Pipeline order: retrieve (`fetch_k`) → rerank → truncate to `k`.
  `retrieval/pipeline.py`.

This pipeline stays. The refactor changes **what is indexed** and **how it is
filtered**, not the dense/sparse/RRF/rerank machinery.

---

## 4. Chunk payload schema **[change]**

```json
{
  "id": "pulse_123#0",                 // chunk id == supports.evidence_id
  "parent_doc_id": "pulse_123",
  "source_type": "otx",                // mitre | otx | pdf | vt | whois | pdns
  "content": "...",                    // the embedded text (raw, preserved)

  // --- denormalized projections from the knowledge layer (filter keys only) ---
  "attack_ids": ["T1566", "T1027"],    // technique ids touched by this chunk
  "entity_ids": ["actor_0042", "indicator_..."],
  "relations": [                       // entity-id triples, not strings
    { "subject_id": "actor_0042", "predicate": "uses", "object_id": "technique_T1566" }
  ]
}
```

Payload indexes **[change]** — today `search()` filters on `source` only
(`store/qdrant_store.py`, no `create_payload_index` anywhere). Add keyword
payload indexes on `source_type`, `attack_ids`, `entity_ids` so a query can
pre-filter (`attack_id = T1566 AND source_type = otx`) before vector scoring.
This is the concrete fix for "facts are stored but can't be queried."

The vector itself (dense + sparse) is unchanged. `attack_ids`/`entity_ids`/
`relations` are filter metadata; they are never embedded.

---

## 5. Chunking rules by source population **[change]**

Driven by the two source shapes in `docs/CONTEXT.md`:

- **Narrative source (PDF, pulse text, MITRE technique descriptions)**:
  sentence-aware semantic chunking with overlap (already implemented). One
  Document → many Chunks.
- **Field source (WHOIS / pDNS / VT)**: one record = one Chunk. No splitting;
  the record is atomic. Chunk carries the indicator in `entity_ids`.
- **Relationship edge (MITRE)**: verified — nearly every edge carries a real
  procedure **description** (a non-empty body after the templated first line;
  reproduce by splitting `content` on the first blank line over
  `mitre_relationships.jsonl`), not a bare template. So the description has
  genuine semantic value and **stays as a chunk**. The
  change is narrow: embed the **description text only**, drop the redundant
  templated first line (`"X uses Y (Tnnnn)"`), because that line duplicates the
  Fact and the Fact already lives in the knowledge layer + in `relations[]`.
  Net effect: the collection keeps the useful prose, loses the redundant
  restated triples, and the exact `(actor, uses, technique)` answer is served by
  filter/graph, not by hoping vector similarity lands on the right substring.

(This corrects the earlier "edges are template junk diluting the collection"
claim — the data does not support it. Only the first line is redundant.)

---

## 6. Query path **[change]**

Two additions to the existing retrieve→rerank flow:

- **Payload pre-filter**: when a query carries a structured constraint
  (`attack_id`, `source`, an entity), apply it as a Qdrant filter before vector
  search, using the §4 indexes. Deterministic constraints stop going through the
  similarity channel.
- **Ontology expansion at query time**: a filter on `T1056.001` also matches
  `T1056` (and vice-versa for parent→children) by traversing the ontology edges
  defined in the knowledge/ontology layer. This is the forward-time version of
  the parent/child normalization that currently lives only in eval
  `set_metrics.py`.

Routing (deciding *whether* a query is structured/exact vs semantic) is noted as
an open design point, not specified here.

---

## 7. Invariants

1. The retrieval payload is a projection. On conflict, rebuild it from the
   knowledge layer. Never edit truth here.
2. `chunk.id == supports.evidence_id`. Do not invent a second join scheme.
3. No `entity_id` minting, no alias resolution, no ontology versioning in this
   layer.
4. `attack_ids` / `entity_ids` / `relations` are filter metadata — never
   embedded, never the system of record.
5. The vector store holds retrieval data only — no Fact/Entity/Ontology tables.
