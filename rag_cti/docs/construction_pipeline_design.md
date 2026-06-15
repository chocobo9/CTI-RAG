# CTI-RAG Knowledge Construction Pipeline

The **vertical** process that turns a source into `Entity` / `Fact` / `supports`
/ `Chunk`, across all three layers. The three layer docs are **horizontal** —
they define what each layer's objects *look like*. This doc defines *when and how
they come into existence and change*.

It does **not** replace `docs/source_ingestion_design.md` (that owns Layer-0 raw
preservation and loss prevention). This doc owns **sequencing and decision
rules**. Where a rule is a genuine policy fork, it is marked **DECISION** and left
for an explicit call, not silently chosen.

Terms: `docs/CONTEXT.md`. Tags: **[existing]** / **[change]**.

---

## 1. Why the decision rules, not the stage list, are the point

The stages are obvious:

```
Fetch → Normalize → Resolve → Extract → Generate → Project → Persist
 L0       L0          L2(reg)   L0/L2     L2          L1+L2    all
```

(`reg` = Entity registry.) Any pipeline has these. What determines whether the
knowledge base stays correct over 1,000 ingests is the **decision at each
transition**: create vs reuse, merge vs hold, new fact vs new evidence,
recompute vs keep. Those are specified below. Everything a connector does to
preserve raw structure is in the ingestion doc; this doc starts from
*normalized mentions* and ends at *persisted knowledge*.

---

## 2. Stage responsibilities (brief)

| Stage | Layer it writes | What it does |
|-------|-----------------|--------------|
| Fetch | L0 | pull + persist raw verbatim (ingestion doc) |
| Normalize | L0 | per-source field → typed *mentions* (`entity_name`, indicator `{value,type}`, predicate from structure). Emits mentions, not ids. |
| Resolve | L2 registry | mention string → canonical `entity_id` (or orphan). §3. |
| Extract | L0/L2 | structured sources: read relations from structure; narrative: NLP relation extraction → relation candidates |
| Generate | L2 | relation candidate → Fact (+ supports). §4–5. |
| Project | L1 + L2 | write retrieval chunk payload (`labels[]/entities[]/relations[]`) + knowledge rows. §6. |
| Persist | all | idempotent writes keyed by stable ids. §7. |

---

## 3. Entity resolution — create vs reuse vs merge vs hold

Input: a normalized entity mention (`"apt 29"`, type `actor`).
Resolver order — note that the existing `match_intrusion_set`
(`scripts/rebuild_relationship_gold.py`) matches **intrusion-set objects only**.
It is a starting point for `actor` mentions; resolving `family`/`tool` against
Software (S####) or matching across types is a **new resolver**, not a reuse of
this function. **[existing for actors only]**:

| Match | Action | Confidence in the link |
|-------|--------|------------------------|
| exact canonical name | reuse `entity_id` | certain |
| exact alias | reuse `entity_id` | certain |
| **substring / fuzzy** | **DECISION** (see below) | uncertain |
| no match | **create orphan** Entity, `ontology_id: null`, `canonical_name` = the mention | n/a |

**DECISION-1 — substring/fuzzy matches must NOT auto-merge.** Grounding: a
high-frequency OTX adversary string like `Cobalt` is ambiguous between *Cobalt
Strike* (tool, S0154) and *Cobalt Group* (actor, G0080) — and note these live in
**different object types**, so resolving the ambiguity at all requires a
cross-type resolver that does not exist yet (it is *not* something
`match_intrusion_set` can do). Auto-merging on substring silently fuses two real
entities and corrupts every fact attached to them — unrecoverable drift.
Proposed rule: exact name/alias → auto-reuse; substring/fuzzy → emit a **merge
candidate** (held, not applied) for review or a later high-precision resolver;
never auto-merge. Confirm or override.

**DECISION-2 — orphan policy.** No-match today returns `None` and the relation
is dropped (`match_intrusion_set` falls through). Proposed rule, consistent with
the orphan principle already in `docs/CONTEXT.md`: create an orphan Entity and keep
the fact, flagged low-trust, so nothing is silently lost and it can be linked
later. Confirm.

Note: alias knowledge comes from the OntologyNode mirror (Group/Software objects
with their `aliases`), which is why the ingestion doc loads `software + group`,
not techniques alone. The resolver reads aliases from there.

---

## 4. Fact generation — new fact vs new evidence

Input: a resolved relation `(subject_id, predicate, object_id)` from one
evidence.

```
key = (subject_id, predicate, object_id)
fact = facts.get(key)
if fact is None:        create Fact(key) → fact_id        # first time this claim is seen
add supports(fact_id, evidence_id, origin, confidence, observed_at)
```

So a claim seen N times → **one** Fact, **N** supports rows. This is the
mechanism behind "one claim asserted by MITRE plus many OTX pulses." The Fact is created
once; every later assertion is an *evidence* event, never a duplicate fact.

**Predicate must be controlled before this stage.** Map extracted verbs
(`leverages`/`employs`) into the controlled set; unmapped → candidate, not
auto-added (knowledge doc §7.3). A free-text predicate here splits one fact into
synonyms.

---

## 5. supports & confidence — when it is (re)computed

**supports identity** = `(fact_id, evidence_id, origin)`. Re-ingesting the same
evidence **upserts** the same row (updates `observed_at`/`confidence`), never
appends a duplicate. This is what makes re-runs safe.

**Per-supports confidence** is set at generation time from *how the fact was
derived* (knowledge doc §3): MITRE explicit edge → high; OTX co-occurrence →
medium; PDF extraction → low (model score); infra match → by match type. It is a
property of the edge, fixed when the edge is written.

**Fact aggregate credibility** is always a *function of all its supports*. It may
be **materialized** on the Fact (stored and incrementally updated — DECISION-3's
proposed default) or computed at read; either way it is derived from supports and
never a hand-set constant. (This is the single consistent stance across all docs:
"derived from supports, may be cached on the Fact" — earlier wording that said
"never stored" meant "never an authoritative constant," not "never materialized.")

**DECISION-3 — recompute trigger.** Two options: (a) recompute and store the
aggregate on the Fact every time a supports row is added/changed (incremental,
read-cheap, write-heavier); (b) compute at query time from the supports rows
(always fresh, read-heavier). Proposed: (a) for a product (reads dominate, and
it lets retrieval filter on credibility). Confirm.

**DECISION-4 — aggregate function.** Inputs available per `docs/CONTEXT.md` and the
A2 list: source reliability (mitre > otx > pdf-extracted), cross-source
agreement (distinct origins), recency, count. Exact form is unspecified — this
is a research/tuning surface, not derivable from code. Flag it as an explicit
sub-task; do not bury an arbitrary formula in code.

---

## 6. Conflict — represent, do not silently resolve

**DECISION-5 — C3.** When two sources assert mutually exclusive facts (e.g.
`campaign attributed-to G0016` vs `attributed-to G0032`), the pipeline does
**not** pick a winner at write time. Both Facts exist, each with its own supports
and aggregate credibility; the conflict is *representable* (same subject,
incompatible object on a single-valued predicate) and surfaced. Truth discovery
/ automated resolution is a later capability, explicitly out of scope for the
first build. Confirm this stance (the alternative — last-writer-wins or
highest-confidence-wins at ingest — destroys the minority claim and its
evidence).

---

## 7. Idempotency & incremental (re-run safety)

The whole pipeline must be safe to re-run. Keying:
- raw record: source id (`pulse_id`/`attack_id`/`domain`/…) **[existing]**
- Entity: canonical `entity_id`
- Fact: `(subject_id, predicate, object_id)`
- supports: `(fact_id, evidence_id, origin)`

Every write is an upsert on its key. Re-ingesting a source on a schedule
re-derives projections from raw and upserts; it never duplicates Facts or
inflates supports counts. Incremental fetch uses source `modified`/`fetched_at`
to touch only changed records (ingestion doc §6). This is the concrete substrate
for Knowledge-layer C4 (incremental growth) and C1 (confidence update).

---

## 8. Invariants

1. Resolve before Generate. A Fact is never written with a string subject/object
   — only `entity_id`s (orphans included).
2. One claim = one Fact + many supports. Re-assertion adds a supports row, never
   a Fact.
3. No auto-merge of entities on fuzzy/substring matches. (DECISION-1.)
4. Nothing is silently dropped: an unresolved entity becomes an orphan, a
   conflicting fact is kept, an unmapped predicate becomes a candidate.
5. Every stage is idempotent on its key; the pipeline is re-runnable.
6. confidence is never a stored constant on a Fact or a label; it is per-supports
   plus a derived aggregate. (DECISION-3/4 fix *how*, not *whether*.)

---

## Open decisions (collected)

- **DECISION-1** fuzzy/substring → merge-candidate, never auto-merge.
- **DECISION-2** unresolved → orphan entity (keep, flag), not drop.
- **DECISION-3** aggregate confidence stored & incrementally updated vs computed
  at query.
- **DECISION-4** the aggregate confidence function (research/tuning surface).
- **DECISION-5** conflicts represented, not auto-resolved at ingest.
