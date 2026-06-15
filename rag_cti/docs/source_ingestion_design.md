# CTI-RAG Source & Ingestion Design

Spec for the layer *beneath* retrieval and knowledge: **connector → raw record →
normalized objects**. Companion to `docs/retrieval_layer_design.md` and
`docs/knowledge_layer_design.md`, which both assume clean `Chunk` / `Entity` /
`Fact` objects already exist. This document is where those objects are created —
or, today, where source structure is destroyed.

Terms: `docs/CONTEXT.md`. Items tagged **[existing]** / **[change]**.

---

## 1. Why this layer is the foundation

Every downstream guarantee (entity resolution, fact dedup, indicator
attribution, ontology expansion) depends on structure that the source *had* and
ingestion *kept*. Right now each connector's `to_document()` is a hand-written,
lossy projection that renders prose and whitelists a few fields in one step, and
**the raw record is never persisted**. Once a source becomes
`Document(content, metadata)`, the original structure is gone and cannot be
re-extracted.

This layer's single job: **turn a source into typed objects without losing
anything that a future extraction or join might need.**

---

## 2. Current loss mechanisms (audit, all grounded)

**(a) Structured sub-objects flattened to strings.** OTX `_indicator_values`
(`connectors/otx.py:74`) keeps only `ind["indicator"]` and **drops
`ind["type"]`** — so every indicator becomes a bare string and you can no longer
tell a domain from an IP from a hash. That type is the **join discriminator**
for the entire field-source layer (domain → WHOIS/pDNS, hash → VT). Dropping it
is the most damaging single loss in the pipeline.

**(b) Hardcoded caps on joinable fields (silent tail loss).**
- `otx.py`: `_METADATA_INDICATOR_CAP = 50` — indicators truncated per pulse.
- `passive_dns.py`: `ips[:20]`, `asns[:10]`, `subdomains[:20]`, `resolutions[:10]`.
- `virustotal.py`: `yara_results[:5]`.
These caps sit on exactly the fields used for joining/attribution. A cap belongs
on the *embedded content sample*, never on the preserved record or a join index.

**(c) Whitelist-by-dict-literal metadata.** Every connector hand-enumerates a
fixed field set (`otx.pulse_metadata`, `whois_connector` keeps
registrar/iana_id/created/expires/registrant_email/name_servers, etc.). Anything
not literally listed is dropped. With no raw kept, the whitelist is destructive.

**(d) Render-and-discard — *partial* raw store, not unified.** Correction to an
earlier draft of this doc: a raw store **does exist** —
`scripts/refetch_otx_raw.py` saves each pulse's full JSON to
`data/raw/otx/{pulse_id}.json`, and `data/raw/mitre/enterprise-attack.json` is
the MITRE bundle; `scripts/rebuild_otx_jsonl.py` rebuilds processed OTX from
raw. The real problems are narrower and worse-hidden: (i) raw exists only for
OTX and MITRE — **VT / WHOIS / pDNS have none**; (ii) the OTX raw is written with
`write_text` (overwrite), **not append-only/versioned** — a re-fetched modified
pulse destroys its prior state (Rule 0); (iii) it is a side script, **not wired
through the connector pipeline**; (iv) the processed corpus was rebuilt by an
**older** connector, so processed and current code have drifted (see table).

### Full hardcode / drop-risk inventory

Every hardcoded filter, cap, and slice in the connectors, classified by whether
a real source backs the dropped data. **Fix** = drop-risk on data-backed
structure; **keep** = legitimate (stable ids, API paging, embed-only sample).
Counts are intentionally omitted — verify each against `data/raw/` at build time.

| Location | Effect | Data-backed? | Verdict |
|----------|--------|--------------|---------|
| `mitre_relationship.py:18` `_CTI_REL_TYPES={uses,attributed-to}` | STIX relation types cut to 2 | partial — bundle has `uses/mitigates/detects/subtechnique-of/revoked-by/attributed-to`; **no `targets`** | **fix**: widen to the types that exist; do **not** add `targets` (not in bundle) |
| `mitre_relationship.py:17` `_CTI_SOURCE_TYPES={intrusion-set,campaign}` | drops `malware`/`tool` as fact subjects (`malware uses technique`) | yes — core ATT&CK, large volume | **fix**: add malware/tool sources |
| `otx.py:74-75` `_indicator_values` returns only `ind["indicator"]` | indicator → bare string, type dropped (raw has type for every indicator; processed has type for none) | yes | **fix**: preserve `{value,type}` |
| `otx.py:68` `[:_METADATA_INDICATOR_CAP]` (50) | indicators truncated per pulse — and processed jsonl already exceeds 50, proving it was built by older code | yes | **fix**: no cap on the indicator index; reconcile rebuild with current code |
| `passive_dns.py:45-47,66` `ips[:20]`/`asns[:10]`/`subdomains[:20]`/`resolutions[:10]` | infra join fields truncated | yes | **fix**: no cap on join fields |
| `virustotal.py:79-83` renders only `yara_results[:5]`, metadata stores none | YARA beyond 5 is in neither metadata nor content, and there is no VT raw store | yes (signal) | **fix**: preserve full YARA (needs a VT raw store) |
| OTX `targeted_countries` | **already read** into content (`otx.py:45-47`) and metadata (`otx.py:66`) | yes | **fix is NOT "read it"** — it is read; the gap is no location Entity / `targets` Fact (knowledge layer) |
| `otx.py:51` `_CONTENT_INDICATOR_SAMPLE` (20) | samples indicators **into embedded prose** | n/a | **keep** — the one legal place for a cap |
| `*_connector.py …[:16]` | sha256 doc-id truncation | n/a | **keep** length; but see §7 — collision must fail loud, not upsert |
| `otx.py:16` `_PAGE_LIMIT` (20) | API page size (paginates, no loss) | n/a | **keep** |

Not added (no source backs them): `attribution_confidence` (no source populates
it) and the `ASSOCIATED_WITH` predicate (no corresponding relation in any
source) — leave an interface, do not fabricate values.

---

## 3. Core principle — preserve, then project

Every source produces **two separate things**, and they must not be conflated:

1. **Raw record** — the source response, stored **verbatim and append-only,
   versioned by `(source_id, fetched_at)`**. A source that changes (OTX pulses
   carry `last_modified` and are re-fetched via `modified_since`) appends a new
   version; the prior version is **never overwritten**. This is the permanent
   evidence substrate (the "原文不能丢" requirement) and the reason most other
   drops are reversible. ("Immutable, keyed by source id" with overwrite-on-
   re-ingest would silently destroy the prior state of a modified record — a
   Rule 0 fail.)
2. **Projections** — derived, disposable, regenerable:
   - retrieval `Chunk`(s) — see retrieval doc
   - candidate `Entity` / `Fact` / `relations[]` — see knowledge doc

If a projection is wrong or the schema changes, re-run projection over the raw.
Today this works only partially: OTX and MITRE have a raw store
(`scripts/refetch_otx_raw.py`, `data/raw/`), but it is overwrite (not
versioned), VT/WHOIS/pDNS have none, and it is not wired through the connector
pipeline. **[change]** — make raw append-only/versioned, extend to all sources,
and route projection through it.

---

## 4. Per-source ingestion contract **[change]**

Replace the hand-rolled `to_document` with a per-source **declared**
normalization. Each connector declares:

- **source classification** — one of `ontology` (MITRE), `weakly-labeled`
  (OTX), `unlabeled-narrative` (PDF), `infrastructure` (WHOIS/pDNS/VT). This
  decides the normalization path; an infrastructure source never emits TTP
  labels (see §2(a) of the knowledge doc).
- **entity extraction** — which raw fields are entities, with their type
  (actor / technique / family / indicator). Emits entity *mentions*; the Entity
  registry does the resolution (this layer does not mint canonical ids itself,
  it hands mentions up).
- **relation extraction** — for structured sources, the predicate is read
  **directly from structure**, never guessed: MITRE STIX `relationship_type`
  (`uses` / `attributed-to`); OTX adversary×attack_id co-occurrence. Narrative
  sources defer to NLP extraction. The predicate must survive — it is the field
  whose loss caused the 36% miswiring.
- **indicator typing** — see §5.
- **provenance** — `source_type`, `source_id`, `url`, `fetched_at`, and source
  version (e.g. ATT&CK `attack_version`). This is what lets a downstream
  `supports` edge record real provenance instead of just `origin: "otx"`.

Structured sources (MITRE, OTX) carry their structure into typed objects with
**zero inference**. Only narrative sources require probabilistic extraction.

---

## 5. Indicator typing — the highest-value fix

Indicators must be ingested as `{value, type}`, never as a bare value. Type is
preserved from the source (OTX already provides it; it is currently discarded).
Canonical types: `domain`, `ipv4`, `ipv6`, `hash-md5`, `hash-sha1`,
`hash-sha256`, `url`, `email`.

Reason: the type is what routes the field-source join. A `domain` indicator
joins to WHOIS/pDNS; a `hash-sha256` joins to a VT file report. Without type,
indicator attribution (the (b) problem in `docs/CONTEXT.md`) degenerates into
blind string matching across kinds that can never match. This one change
re-enables the entire indicator-mesh half of the system.

---

## 6. Caps, idempotency, incremental

- **Caps** are permitted in exactly one place: the *sample of indicators
  rendered into embedded `content`* (prose doesn't need all 500). They are
  forbidden on the raw record and on any field that feeds entities, relations,
  or joins. **[change]** — move `_METADATA_INDICATOR_CAP` and the
  `passive_dns` slices off the preserved/joinable path.
- **Idempotency** — keyed by stable source id (`pulse_id`, `attack_id`,
  `domain`, …). Re-ingesting **appends a new raw version** (never overwrites the
  prior, per §3) and **upserts projections**, never duplicating Facts. OTX
  already dedups by `pulse_id` (`seen_ids`). **[existing, partial]** —
  generalize to all sources and to the versioned raw store.
- **ID collision is a fail, not an upsert.** Doc/chunk ids are
  `sha256(...)[:16]`. Current processed ids are unique (verify: distinct id
  count == row count across `data/processed/*.jsonl`), so this is a *latent*
  risk, not an observed incident. But the upsert path means that **if** two
  records ever collide, one is silently overwritten. Writes must **assert id
  uniqueness and fail loud** on collision, never silently replace. **[change]**
  (Rule 0.)
- **Incremental growth** — `fetched_at` / source `modified` timestamps let a
  re-fetch ingest only changed records, supporting Knowledge-layer C4 without a
  full rebuild. **[change]**
- **Truncation is logged, never silent.** `QdrantStore` reads content up to a
  byte threshold; no current chunk exceeds it (verify: count chunks over the
  threshold — currently none), so this too is latent. If content ever exceeds
  the embedding model's max it must be re-chunked from raw, not silently cut, and
  any unavoidable truncation emits a flag. (See
  `docs/eval/chunk_truncation_audit.md`.) **[change]** (Rule 0.)

---

## 7. Invariants

1. Raw is preserved verbatim and **append-only/versioned** before any projection
   runs; a re-fetch of a modified source appends, never overwrites. Loss at this
   boundary is unrecoverable, so it is not allowed. (Rule 0.)
2. Indicators carry `type`. Never flatten an indicator to a bare string.
3. No cap on a field that feeds an entity, relation, indicator, or join — caps
   live only on the embedded-content prose sample, and are safe **only because**
   raw is preserved (invariant 1).
4. Predicates come from source structure for structured sources; never inferred
   for MITRE/OTX.
5. This layer emits entity/relation **mentions** and raw provenance; it does not
   resolve canonical ids, compute confidence, or own the ontology — those belong
   to the knowledge layer.
6. "Embed this" and "preserve this" are separate outputs of separate steps.
