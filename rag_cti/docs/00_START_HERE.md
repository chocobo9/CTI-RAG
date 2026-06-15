# START HERE — Implementation Guide for the Knowledge-Layer Refactor

You (the implementing agent) are refactoring CTI-RAG's knowledge layer. This
file tells you which document governs what, what order to build in, and which
decisions must be answered **before** you touch certain code. Read this fully
before reading any other doc or writing any code.
整个 5 个 DECISION 的"proposed default" 不是从代码/数据来的。只作为参考。
---

## Rule 0 — above every other rule and decision

**A decision that is cheap AND irreversible AND silent is a FAIL.** Not a
trade-off to weigh — a defect to reject. It is the worst class because it is
never reviewed: nothing signals that it happened, and by the time the loss is
noticed the data is gone (CTI sources are historical and cannot be re-fetched).

Whenever you are about to drop, truncate, flatten, merge, overwrite, or
auto-resolve anything, break the conjunction — make it **at least one** of:

- **not silent** — log it, flag it, emit a candidate/review record, or fail loud.
- **not irreversible** — preserve the raw input so the step can be re-run.
- **expensive on purpose** — require an explicit decision, not a default.

Every DECISION below (D1–D5) and every drop-risk in the ingestion audit is just
an instance of this rule. You do not need them enumerated to obey it: if a choice
is cheap + irreversible + silent, you stop and surface it, regardless of whether
it appears in a list.

---

## The documents

| Doc | Layer | Governs | Answers |
|-----|-------|---------|---------|
| `docs/CONTEXT.md` | — | **Glossary. The authority for every term.** | What a word means (Entity, Fact, supports, …) |
| `docs/source_ingestion_design.md` | L0 (horizontal) | connector → raw → typed mentions | How a source enters **without losing data** |
| `docs/knowledge_layer_design.md` | L2 (horizontal) | Entity / OntologyNode / Fact / supports | What knowledge **looks like** |
| `docs/retrieval_layer_design.md` | L1 (horizontal) | chunk / Qdrant / payload index / expansion | How it is **retrieved** |
| `docs/construction_pipeline_design.md` | vertical (spans L0→L2) | sequencing + decision rules | **When** to create / merge / generate / update |

Horizontal docs define static shape. The pipeline doc is vertical: it is not a
milestone of its own — it is the rulebook applied *during* every milestone
below. The three layer docs tag each item **[existing]** (already in the repo)
or **[change]** (this refactor). Do not rewrite `[existing]` items.

If a term in any design doc seems ambiguous, `docs/CONTEXT.md` wins. If a design doc
and this file disagree on order, this file wins.

---

## Build order (each milestone is a precondition for the next)

### M0 — Ingestion: stop losing data  `source_ingestion_design.md`
Deterministic, additive, touches no retrieval. Do this first because every
downstream object is rebuilt from this layer; building on flattened data means
rework.
- Raw store **already exists for OTX + MITRE** (`scripts/refetch_otx_raw.py`,
  `data/raw/`) but is overwrite-not-versioned and missing for VT/WHOIS/pDNS. Make
  it **append-only/versioned**, extend to all sources, and route projection
  through it. (Not "build from zero" — see ingestion §2(d).)
- Apply the §2 **fix** rows: preserve indicator `{value,type}`; remove caps on
  join fields (`otx` indicator cap, `passive_dns` slices, `vt` YARA — needs a VT
  raw store); widen `mitre_relationship` `_CTI_SOURCE_TYPES` (add malware/tool)
  and `_CTI_REL_TYPES` to the types that exist in the bundle — **do not add
  `targets`, it is not a MITRE relationship type**; reconcile the rebuild script
  with current connector code (processed corpus drifted from current code).
- OTX `targeted_countries` is **already read** — the M0 gap is not reading it;
  the modeling (location Entity / `targets` Fact) is M1/knowledge-layer work.
- Keep the §2 **keep** rows untouched (content sample, doc-id hash, page limit).
- **Gates:** none. No open decision blocks M0 — build it now.
- **Done when:** raw is versioned and covers all sources; indicators carry type;
  re-running rebuild reproduces processed deterministically; the existing
  pipeline still runs.

### M1 — Entity registry + Ontology  `knowledge_layer_design.md` §1/§3 ontology + `construction_pipeline_design.md` §3
- Load OntologyNode + ontology edges from MITRE STIX (technique / sub-technique
  / tactic / software / group).
- Build the Entity registry: mint `entity_id`, resolve aliases. `match_intrusion_set`
  resolves **intrusion-set (actor) mentions only** — reuse it for actors;
  resolving family/tool against Software or matching across types is a **new
  resolver**, not a reuse.
- **Gates (must be answered before writing registry code): DECISION-1, DECISION-2.**
  Without them you will write entity-merge behaviour by guesswork — the specific
  failure being prevented (e.g. fusing the tool *Cobalt Strike* with the actor
  *Cobalt Group*, which also requires cross-type resolution that does not exist
  yet).
- **Done when:** the distinct OTX `adversary` strings (compute the count from
  `data/processed/otx.jsonl`) resolve against MITRE intrusion-set names (from
  `data/raw/mitre/enterprise-attack.json`); exact-match reuse ids, the rest
  become orphans (per DECISION-2), nothing dropped. Do not hardcode the
  exact/orphan split — derive it; the processed source_names are a lossy
  substitute for the raw intrusion-set list.

### M2 — Retrieval layer  `retrieval_layer_design.md`
The actual RAG deliverable. Depends on M1's `entity_id`s and ontology edges.
Does **not** depend on M3.
- Payload indexes on `attack_ids` / `entity_ids` / `source_type`.
- `relations[]` in chunk payload store **entity_ids**, not strings.
- Query-time ontology expansion (`T1056.001` filter also matches `T1056`).
- Relationship-edge chunks: embed the description, drop the redundant template
  first line.
- **Gates:** none beyond M1.
- **Done when:** `attack_id = T1566 AND source_type = otx` filters before vector
  search; sub-technique query hits parent.

### M3 — Fact / supports tables (DEFERRED)  `knowledge_layer_design.md` §6 Phase 2
Promote per-doc `relations[]` into global Facts + supports edges. Deferred on
purpose: scale does not yet require standalone fact stores, and this layer is
**shared with the attribution-graph track** — align the controlled-predicate
vocabulary with that track before building, or the two will fork.
- **Gates: DECISION-3, DECISION-4, DECISION-5** + predicate-vocab alignment.
- **Done when:** one Fact per `(subject_id, predicate, object_id)`; re-ingest
  adds supports rows, never duplicate Facts.

```
M0 ingestion (no gates)
  → M1 Entity + Ontology   (gates: D1, D2)
    → M2 retrieval          (no extra gates)   ← the RAG increment
    ⇢ M3 Fact/supports      (gates: D3, D4, D5 + vocab alignment)   [deferred]
```

---

## Open decisions — answer the gate before its milestone

Defaults are proposed in `construction_pipeline_design.md`; they need an explicit
yes/override, not silent adoption.

| ID | Decision | Blocks | Default proposed |
|----|----------|--------|------------------|
| D1 | fuzzy/substring entity match → merge-candidate, never auto-merge | M1 | yes, never auto-merge |
| D2 | unresolved entity → orphan (kept, flagged), not dropped | M1 | yes, orphan |
| D3 | aggregate confidence stored+incremental vs computed at query | M3 | stored + incremental |
| D4 | the aggregate-confidence function (research/tuning surface) | M3 | unspecified — do not hardcode a formula |
| D5 | conflicting facts represented, not auto-resolved at ingest | M3 | yes, represent only |

**Not in scope, do not build:** `attribution_confidence` field (no source
populates it, OTX 0/2072) and the `ASSOCIATED_WITH` predicate (no source backs
it). Leave the interface; do not fabricate values.

---

## Hard rules

1. Do not implement all four docs at once. Build by milestone; each doc is the
   spec for its milestone.
2. Do not start a milestone whose gates are unanswered. Stop and ask.
3. `docs/CONTEXT.md` is the term authority. Do not invent or redefine terms in code.
4. Do not touch `[existing]` items except where a `[change]` explicitly modifies
   them.
5. M0 before anything. Never build knowledge/retrieval objects on un-fixed
   (flattened) ingestion output.
