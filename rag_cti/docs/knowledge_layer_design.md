# CTI-RAG Knowledge-Layer Design

Single source of truth for the labelling / knowledge refactor. Supersedes the
scattered "问题3" schema drafts. Decisions here are grounded in the current
corpus (verified counts in §2), not in the abstract.

Terms used here are defined in `docs/CONTEXT.md`. This document is the schema spec;
the glossary is the vocabulary.

---

## 1. Three layers (and why they are separate)

```
Retrieval Layer   doc-centric    "which documents are relevant?"
   Document / Chunk / Embedding + per-doc projections for filtering

Knowledge Layer   fact-centric   "what is actually known?"
   Entity / Fact / supports — global, deduplicated, not owned by any document

Ontology Layer    definitional   "what is the controlled vocabulary?"
   OntologyNode (authoritative definitions) + ontology edges; controlled predicates
```

**Entity vs OntologyNode — separated on purpose.** An `Entity` is an *identity*:
a stable handle that Facts reference and that never changes. An `OntologyNode`
is a *definition*: name, tactics, description, ATT&CK version — all of which
drift across ATT&CK releases. They are 1:1, joined by ATT&CK id. An entity that
does **not** resolve to an authoritative ATT&CK object (an orphan actor, a
free-text malware family) has an Entity but **no** OntologyNode. On an ATT&CK
version bump, only the OntologyNode table is reloaded; Entities and every Fact
referencing them are untouched. This is the whole point of the split.

The retrieval layer and the knowledge layer are **two schemas joined by one
bridge** (`supports.evidence_id`). They are not one document with extra fields.
The reason is structural, not stylistic: a document and a fact are
**many-to-many** (§2). Collapsing that into a per-document record reintroduces
the exact ambiguity this refactor exists to remove.

---

## 2. The data facts that force this design

Each claim below is a **reproducible query, not a frozen number** — counts drift
as code and data change (this already happened: the processed corpus was rebuilt
by an older connector, see ingestion doc). Compute against **raw**
(`data/raw/`), not the lossy processed jsonl. Where a number appears it is an
illustration, not an asserted fact.

- Relations dominate the corpus: count `data/processed/*.jsonl` by source —
  MITRE relationship edges vs technique/OTX/PDF docs. The relationship edges are
  the largest share. (Shape claim, not a fixed ratio.)
- Evidence↔Fact is many-to-many: a single `(actor, technique)` pair is asserted
  by both a MITRE edge and multiple OTX pulses. Reproduce: build the set of
  `(source_name, attack_id)` from `mitre_relationships.jsonl` and the set of
  `(adversary, attack_id)` from `otx.jsonl`; their intersection is non-empty and
  many pulses back each shared pair. (The exact co-asserted count depends on the
  resolver: exact-name-only is a floor; alias/substring resolution raises it. The
  many-to-many property holds at any resolver setting — do not quote a single
  number as if resolver-independent.)
- Entity identity is not free: distinct OTX `adversary` strings vs MITRE
  intrusion-set names (from `data/raw/mitre/enterprise-attack.json`, not the
  processed source_names). A large fraction do **not** exact-match and need alias
  resolution or become orphans (`apt 29` → APT29, `[unnamed group]` → no MITRE
  node). Compute exact/alias/unresolved counts at M1 from raw. Note: the existing
  `match_intrusion_set` (`scripts/rebuild_relationship_gold.py`) resolves
  **intrusion-set objects only** — it does not see software/tool, so it is a
  starting point for actors, **not** a drop-in cross-type resolver (see §3
  family / DECISION-1).
- Ontology edges are real and currently unstored: sub-techniques (`T####.###`)
  point at parents (`T####`). Count them from the MITRE bundle. Today these
  parent links live **only** in eval-side `set_metrics.py`, not in any store.
- Dropping the predicate is lossy at scale: with a `labels[] + entities[]`
  record and no predicate, a document mentioning *k* actors and *m* techniques
  admits *k×m* candidate pairs while only the true edges are correct, and the
  flat record has no field to reject the rest. (Illustration: two actors with
  large technique sets in one report produce a cartesian set far larger than the
  true edge set — a constructed example, not a corpus-extracted report. The point
  is structural; verify the multiplier on any real multi-actor PDF.)
- Infrastructure sources carry no TTP: the VT connector emits
  `{domain, tags, last_modified, analysis_stats}` — zero ATT&CK field. VT / WHOIS
  / pDNS join the graph through the **indicator string**, never through TTP
  prediction.

---

## 3. Object schemas

### Knowledge layer (global, deduplicated)

```json
// Entity — a canonical node. One per real-world thing, shared across all docs.
{
  "entity_id": "actor_0016",
  "type": "actor",                       // actor|campaign|technique|family|indicator|location|asn|mitigation|detection-strategy
  "canonical_name": "APT29",
  "aliases": ["Cozy Bear", "NOBELIUM"],
  "ontology_id": "G0016"                 // → OntologyNode if MITRE-backed; null for orphans
}

// Fact — a triple. All three slots are controlled references, never strings.
{
  "fact_id": "fact_...",
  "subject_id": "actor_0016",            // entity_id
  "predicate": "uses",                   // controlled vocab — see §3 predicate set (attribution + infrastructure + defensive)
  "object_id":  "technique_T1003.002"    // entity_id
}

// supports — Evidence → Fact bridge. This is where confidence/provenance live.
{
  "fact_id": "fact_...",
  "evidence_id": "pulse_123",            // a retrieval-layer doc/chunk id
  "origin": "otx",                       // mitre | otx | pdf | vt | whois | pdns
  "label_availability": "direct",        // direct | indirect | none — how the fact was attributed
  "confidence": 0.83,
  "observed_first": "2025-09-01T...",    // range, not a point, where the source gives one
  "observed_last": "2025-11-20T..."
}
```

Controlled predicate set (data-backed today): `uses`, `attributed-to`,
`targets`. `targets` is fed by **OTX `targeted_countries` only** — the current
ATT&CK STIX bundle has **no `targets` relationship type** (it has
uses/mitigates/detects/subtechnique-of/revoked-by/attributed-to; verify with a
relationship-type count over `data/raw/mitre/enterprise-attack.json`). Do not
claim MITRE backs `targets`.

**Infrastructure predicates** (field sources, data-backed): `resolves-to`
(domain→ip), `belongs-to` (ip→asn), `located-in` (ip→location), `uses-nameserver`
(domain→ns-domain), `has-subdomain` (domain→subdomain) — sourced from passive DNS
and VT DNS records. Endpoints are indicator / asn / location entities; these are
structural infrastructure facts, never TTP predictions (invariant 4).
**Defensive predicates** (MITRE, read directly from STIX `relationship_type`):
`mitigates` (mitigation M####→technique, ~1445 edges), `detects`
(detection-strategy DET####→technique, ~691 edges).

The shared-vocabulary alignment with the
attribution-graph track (`ASSOCIATED_WITH` / `PART_OF` / `OBSERVED_IN`) is
pending; those are not added until a data source backs them.
`attribution_confidence` (high/med/low) is **not** a field — no current source
populates it; add only if a source provides it.

Identity rules:
- A Fact's identity **is** `(subject_id, predicate, object_id)`. Same triple →
  same `fact_id` → multiple `supports` rows. This is how one fact asserted by
  MITRE and many pulses attaches to one node.
- Per-supports confidence is a property of **how a fact was derived from one
  evidence**; it lives on the `supports` row, **never** on the Fact and never on
  a label. A Fact's **aggregate credibility** is a *derived value over its
  supports rows* (cross-source agreement, source reliability, recency). Whether
  that aggregate is **materialized** on the Fact (stored, incrementally updated)
  or computed at read is DECISION-3 in the pipeline doc — the proposed default is
  to materialize it as a derived cache. "Not a single authoritative constant" and
  "materialized derived cache" are consistent: it may be stored, but it is always
  a function of supports, never hand-set.

### Ontology layer (authoritative MITRE definitions)

```json
// OntologyNode — a mirror of one MITRE object. Reloaded wholesale on ATT&CK bump.
{
  "ontology_id": "T1003.002",            // attack id: T####(.###) / S#### / G#### / TA####
  "type": "technique",                   // technique | tactic | software | group | mitigation | detection-strategy
  "name": "LSASS Memory",
  "tactics": ["credential-access"],
  "attack_version": "15.1"               // the definition drifts with this
}

// ontology edge — definitional, axiomatic, NO confidence/supports (see §4).
{ "child": "T1003.002", "parent": "T1003", "edge": "subtechnique-of" }
```

Rules:
- One loader builds this table directly from the MITRE STIX bundle. No
  extraction, no inference — MITRE is authoritative.
- **Scope is not just techniques.** Today the corpus mirrors only the 766
  technique objects; Software (S####) and Group (G####) objects sit unused in
  the same bundle. A product needs an authoritative name/alias/definition source
  for actors and malware too, so the OntologyNode table mirrors **technique +
  sub-technique + tactic + software + group**. Same loader, cheap; skipping it
  forces ad-hoc entity resolution and later rework.
- `family` follows the same rule as every other entity type: a family that
  resolves to a MITRE Software object gets an OntologyNode (`type: software`);
  the ~1,700 free-text community families do not — they stay Entity-only with
  `ontology_id: null`. No separate family-ontology subsystem is built.
- Parent/child is an **edge**, never a field on the node. (`"parent": "T1003"`
  written onto node `T1003` is self-referential and wrong.)

### Retrieval layer (per document / chunk)

```json
{
  "id": "pulse_123",
  "source": { "type": "otx", "source_id": "...", "url": "..." },
  "content": "...",                      // raw text — preserved permanently
  "labels":   ["T1566", "T1027"],        // attack_id projection, for filtering
  "entities": ["actor_0042", "indicator_..."],   // entity_ids mentioned, for filtering
  "relations": [                         // in-doc triples — entity_ids, not strings
    { "subject_id": "actor_0042", "predicate": "uses", "object_id": "technique_T1566", "origin": "otx" }
  ],
  "metadata": { "author": "...", "published": "...", "language": "en" },
  "created_at": "...",
  "updated_at": "..."
}
```

`labels[]` and `entities[]` are **filtering projections** (denormalized for fast
`attack_id = T1566` / `entity = X` queries). `relations[]` is the load-bearing
field: it preserves the predicate. Without `relations[]`, the 36% miswiring in
§2 is unavoidable.

### Vector store (Qdrant) — retrieval projection only

```json
{ "id": "...", "content": "...", "embedding": [...],
  "source_type": "otx", "attack_ids": ["T1566"], "entity_ids": ["actor_0042"] }
```

The vector store does **semantic retrieval and payload filtering only**. It does
not hold the knowledge graph, the ontology, or version history. `attack_ids` and
`entity_ids` exist here purely as payload-index filter keys.

---

## 4. Two kinds of edge between entities — never mixed

| Edge | Example | Source | confidence / supports? |
|------|---------|--------|------------------------|
| **ontology edge** | `T1003.002 belongs-to T1003`, `technique belongs-to tactic` | ATT&CK definition (axiom) | **No.** It is not asserted by evidence. |
| **fact edge** (a Fact) | `APT29 uses T1003.002` | derived from evidence | **Yes.** Carries supports/confidence. |

Consequence: an ATT&CK version bump moves only ontology edges; the
evidence-derived fact edges are untouched. "Ontology expansion" (a query for
`T1056.001` also matching `T1056`) is a traversal of ontology edges at
retrieval/recall time — not a one-off normalization in the eval harness.

---

## 5. Source → layer mapping

| Source | Retrieval doc | Produces facts? | How |
|--------|---------------|-----------------|-----|
| MITRE relationships | yes (edge as evidence) | **yes, directly** | STIX edge → Fact, high-confidence supports. Predicate explicit (`uses` / `attributed-to`; **not** `targets` — absent from the bundle). Subject may be actor, **campaign**, or **malware/tool** — widen the connector's source-type and relation-type filters (ingestion doc §2). No extraction. |
| MITRE techniques | yes | — | technique Entities + ontology edges |
| OTX pulse | Document → one or more **Chunks** (each Chunk = one Evidence) | yes, derived | adversary × attack_id → `uses` Fact (medium conf, `label_availability=direct`); adversary × `targeted_countries` → `targets` Fact (location Entities); indicators → indicator Entities + inherited attribution. Supports attach per asserting chunk, not one blanket per pulse. |
| PDF report | Document → Chunk → evidence | yes, extracted | relation extraction → Fact, low confidence, `label_availability` per extraction (direct/indirect) |
| VT / WHOIS / pDNS | one record = one Document = one Chunk = one Evidence | **no TTP facts** | infrastructure facts only `(domain, resolves-to, ip)` etc. with first/last-seen range; actor attribution is *inherited* via a shared indicator entity (`label_availability=indirect`), never predicted |

---

## 6. Phasing — the boundary is `entity_id`, not the Fact table

The earlier draft drew the phase boundary at "store a Fact table or not," and
let Phase 1 keep `relations[]` as **strings**. That is wrong: it defers entity
normalization to Phase 2, and every string written in Phase 1 must then be
back-filled with an `entity_id`. The boundary is in the wrong place.

Correct split — defer the expensive thing, not the cheap thing:

**Phase 1 — Retrieval layer + Entity registry + Ontology (no Fact/supports tables yet)**
- Entity registry: mint canonical `entity_id`s with alias resolution (reuse
  `match_intrusion_set`). This is cheap and must exist from day one.
- OntologyNode + ontology edges loaded directly from MITRE STIX (authoritative,
  no extraction). Mirror **technique + sub-technique + tactic + software +
  group**, not techniques alone — this is the authoritative alias/definition
  source the Entity registry resolves against.
- Retrieval docs with `relations[]` storing **entity_ids**.
- Outcome: every relation is written with stable ids from the first ingest.

**Phase 2 — Knowledge layer (when relation extraction is stable / scale demands)**
- Promote `relations[]` across all docs into a global Fact table by grouping on
  `(subject_id, predicate, object_id)`.
- Emit `supports` rows: each doc that asserted a fact becomes one supports edge,
  `evidence_id = doc_id`.
- Outcome: **zero back-fill**, because entity_ids already exist. Phase 2 is a
  pure aggregation of Phase 1 data.

What is correctly deferred (the other AI was right here): standalone
Entity/Fact/Support/Ontology stores, fact versioning, and large-scale fact
dedup. Scale does not yet demand them.

What is **not** deferred: entity_id. Deferring it is the one move that
guarantees rework.

---

## 7. Invariants (things that must never happen again)

1. No confidence on a label or a bare technique id. `T1055` is certain; only a
   *derivation* has confidence. Confidence lives on `supports`.
2. No string subjects/objects in `relations[]` or facts. Three controlled slots.
3. No free-text predicates. Map extracted verbs (`leverages`, `employs`) into
   the controlled set; unmapped ones are candidates for human review, not
   auto-added.
4. No TTP prediction for VT/WHOIS/pDNS. They attach by indicator, not by guess.
5. No collapsing a multi-subject document into `labels[]+entities[]` without
   `relations[]`. (The 36% rule.)
6. Vector store never becomes the system of record for knowledge or ontology.
