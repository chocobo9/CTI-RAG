# HISTORICAL — CTI-RAG Consumption-Layer Design (M4 / LangGraph era)

> Archive category: Runtime / LangGraph-era design.
>
> **Status: HISTORICAL / NON-AUTHORITATIVE. Do not implement from this document.**
> Its graph×vector division of labour, EvidenceLedger, grounding, sufficiency, and
> citation principles remain useful rationale. Its LangGraph topology, runtime ownership,
> public-entrypoint descriptions, completion labels, and milestone status are superseded.
> Current Runtime boundaries are governed by
> `docs/adr/0001-runtime-harness-orchestration.md`; migration state is governed by
> `docs/runtime_harness_phase_control.md`; production implementation truth is code/tests.

Spec for **Layer 3 (consumption / agentic graph×vector orchestration)**. Sits on
top of M0–M3: it *consumes* the knowledge layer (M3 Fact/supports) and the
retrieval layer (M1/M2 chunks + vector pipeline); it adds no new system of
record. Companion to `docs/knowledge_layer_design.md` (L2) and
`docs/retrieval_layer_design.md` (L1).

This document is the formal answer to the open point left in
`retrieval_layer_design.md §6`: *"Routing (deciding whether a query is
structured/exact vs semantic) is noted as an open design point, not specified
here."* M4 answers it — and reframes it: the question is **not** "route to graph
*or* vector", it is "how does an agent use graph *and* vector together".

Terms: `docs/CONTEXT.md`. Each item is tagged **[existing]** (already in the
repo) or **[change]** (this layer adds it). M4 is almost entirely **[change]**;
the vector pipeline and the Fact/supports tables it builds on are **[existing]**.

---

## 1. Responsibility boundary (read this first)

The consumption layer answers one question: **"given a user/agent question,
produce an answer that is grounded — cited, credibility-weighted, and
conflict-aware — by orchestrating the knowledge graph and the vector store."**

It is **not** the system of record. Concretely, the consumption layer:

- does **not** mint `entity_id`s, resolve aliases, or version the ontology — it
  reads what M1 produced.
- does **not** store or recompute `confidence` — confidence lives on `supports`
  (CONTEXT.md); a Fact's `aggregate_credibility` is materialized by M3. M4
  *reads* and *surfaces* it, never authors it.
- does **not** change the dense/sparse/RRF/rerank machinery — it *calls* the
  M2 pipeline as one of its tools.
- does **not** own query rewrite. Rewrite is a **separate small-model
  component** with a single responsibility; M4 does not touch it (DM4-6).

**What it consumes:**

- M3 `Fact` / `supports` tables (`data/processed/v5_staging/{facts,supports}.jsonl`).
- The bridge `chunk.id == supports.evidence_id` (retrieval §1, §7-2). One Chunk
  = one Evidence (CONTEXT.md). This is the *only* join between graph and vector;
  do not invent a second.
- The M2 retrieval pipeline (vector search over the live Qdrant collection).

**The two object kinds it must keep straight** (knowledge §4): a **fact edge**
(a Fact, evidence-derived, carries supports/credibility) vs an **ontology edge**
(definitional, axiomatic, no supports). M4 reasons over *fact edges*; ontology
edges are used only for expansion (parent/child technique), exactly as M2
already does.

---

## 2. Graph vs vector — the division of labour (core decision)

The two stores answer different *kinds* of question. M4's whole design rests on
not confusing them.

- **Graph (Fact/supports) = one exact retriever, strong at enumeration.** Because
  the facts are **controlled hard triples** (entity-ids + a closed predicate set +
  deterministic `fact_id`), the graph can be **enumerated exactly and
  exhaustively** — completeness a vector top-k cannot give, *for the slice the
  graph covers*. It is strong for entity-anchored enumeration ("all techniques X
  uses"), IOC/infra pivots, and credibility annotation of retrieved prose.
- **Vector (chunks) = the content layer.** *"What does the source actually say?"*
  — prose, semantics, detail; the home of the data itself, including the PDF
  reports the graph never sees.

**The graph is one retriever, NOT the completeness oracle (revised).** The earlier
draft made the graph "the coverage gauge / map" that governs the loop and judges
sufficiency. That does **not** hold, for three data-backed reasons (verified
against the live corpus):
- *PDF-blind*: facts are built only from MITRE/OTX/pDNS/VT — **zero** PDF facts —
  yet PDFs carry the richest analysis. The graph's "N" silently excludes them.
- *Enumeration-only*: ~10 controlled predicates can gauge "how many techniques does
  X use" but not "compare X vs Y" or "is this incident likely Z".
- *Extraction ≠ answer completeness*: `uses` dominates (~23k) over infra plumbing
  (~17k) with `attributed-to` at ~25 — enumerating all graph facts is not answering
  the question; for a focused query it is noise.

So the graph is **auxiliary navigation**, used where it is strong; it is **not**
what decides "done" (that is the v1 sufficiency judge, §9). It cannot carry the
*content* of an answer either. (This corrects the original "graph says 30, answer
covered 5 → incomplete" gauge — that signal is PDF-blind and enumeration-shaped.)

**We do not follow the LightRAG route** (verified against LightRAG's design):
LightRAG embeds *entity/relation descriptions* as vectors and retrieves graph
elements by similarity precisely because its graph is **fuzzily extracted** from
free text (uncontrolled predicates, no entity ids). Our graph is **controlled
and hard**, so the graph path can be **deterministic exact enumeration** — no
need to vectorize graph elements. Our split is cleaner; keep it.

---

## 3. Cooperation model — agent alternation, not pipeline routing

The recurring wrong instinct is to **split by task** ("this question goes to the
graph, that one to vector") and hardwire a router. That is the **workflow**
failure mode, and it is rejected here.

Graph and vector are **not separable as parallel pipelines**. They are separable
only **by responsibility**, and an agent **alternates** between them within one
reasoning loop:

1. **Agent gathers.** It freely calls graph (enumerate / pivot) and vector (prose)
   for whatever the question needs — no fixed order, no task→store router.
2. **A sufficiency gate judges.** A dedicated LLM judge decides whether the
   gathered evidence answers the question (recall) and whether the draft is
   supported by it (grounding). This is the stop decision.
3. **On a gap, the agent re-retrieves.** The judge emits the concrete next query /
   graph target; the loop re-enters until the gate is satisfied or the budget cap.

The split between graph and vector never appears as a routing decision on a
pipeline; it is role division inside the agent loop (v1).

**Corrected from the earlier draft:** convergence is **not** "graph says 30, answer
covered 5 → loop" (graph M-vs-N). The graph is PDF-blind and enumerable-question-
shaped (§2), so it cannot be the universal completeness signal. Convergence is the
**sufficiency judge** (§9.3); the graph counts are one of its inputs, never the
sole gate. Likewise **grounding (is the draft supported)** and **sufficiency (did
we gather enough)** are two distinct axes — the design no longer conflates them.

---

## 4. Phasing — tools first, agent second

M4 deliberately splits into two milestones. The phase boundary is **"who
decides"**: in v0 the caller decides (deterministic, structured params); in v1
the LLM decides (autonomous orchestration).

- **M4.v0 — Tooling foundation [change].** Build the graph tools, the
  evidence-fetch bridge, and the output types as **deterministic, independently
  callable, unit-testable** functions. Each tool emits **objective facts**
  (the graph emits structure + coverage *numbers*; the vector emits content).
  **No LLM orchestration, no NL→intent routing, no prose synthesis.** This is
  the necessary precondition for v1, and it stands alone (a CLI exercises it with
  structured params). Determinism here is what keeps the layer testable under the
  project's certification/coverage culture.
- **M4.v1 — Agent loop [built].** Wrap the v0 tools in an outer hard-rail
  StateGraph around an inner ReAct burst (§9): the LLM gathers via graph+vector, a
  **sufficiency judge** decides enough/grounded, the loop re-retrieves on gaps,
  then synthesizes a cited answer. The *sufficiency judgement lives in a dedicated
  judge node* (not in a graph-count comparison); the tools only ever return
  objective evidence (invariant 2). Gated by DM4-4.

---

## 5. v0 tool contract [change]

These signatures are the deterministic seam. They are *also* the tool set the
v1 agent will call — designing them now means v1 adds only the orchestration
layer, not new plumbing.

- `graph_outline(entity_id) -> Outline` — the **map / coverage gauge**. Returns,
  for the entity, each predicate category present, the object_type it points to,
  the **count** per category, and a credibility summary. (e.g. `actor_G0016:
  uses→{technique:24, family:6}, targets→{location:5}, attributed-to←{campaign:3}`.)
  *New in this design* — the navigation primitive §2/§3 depend on.
- `graph_query(*, subject_id, predicate=None, object_type=None, object_id=None,
  min_credibility=0.0) -> FactQueryResult` — exact enumeration of one category.
  **Not truncated** (completeness is the point). Each row carries its `supports`
  citations, `aggregate_credibility`, and `conflict` flag.
- `facts_for_evidence(chunk_id) -> tuple[Fact, ...]` — the **reverse bridge**.
  Given a vector-retrieved chunk, which facts does it support — so content
  fetched by vector can be anchored back onto the map (coverage update,
  credibility annotation).
- `get_by_chunk_ids(chunk_ids) -> dict[str, Chunk]` — evidence fetch
  ([change] on `store/qdrant_store.py`, reusing `chunk_to_point_id` +
  `_payload_to_chunk`). Turns `supports.evidence_id` back into chunk content so a
  citation can be *expanded*. Missing ids are skipped, never faked.
- `FactStore` — loads facts/supports into queryable indexes behind a
  **Protocol** (`FactStoreProto`), so the backend (in-memory / NetworkX / KuzuDB
  / Neo4j — DM4-1) is swappable without touching any consumer. Forward index
  (subject[+predicate]→facts), reverse index (evidence_id→supports), fact_id
  lookups. `verify_bridge(fact_store, qdrant_store, sample)` is a health probe
  on the evidence_id↔collection join (DM4-2).

---

## 5.1 Neo4j schema (DM4-1 landing)

Reified so supports/evidence are first-class — the reverse bridge is an indexed
one-hop, not an edge-property scan:

```
(:Entity   {entity_id, type, name})
(:Fact     {fact_id, predicate, group, aggregate_credibility,
            aggregate_version, conflict, support_count, distinct_origins})
(:Evidence {evidence_id})                     # == chunk.id; content stays in Qdrant
(subject:Entity)-[:SUBJECT]->(:Fact)
(:Fact)-[:OBJECT]->(object:Entity)
(:Evidence)-[:SUPPORTS {origin, confidence, label_availability,
                        observed_first, observed_last}]->(:Fact)
```

Idempotent load (MERGE on the M3 identity keys: `entity_id` / `fact_id` /
`(evidence_id, fact_id, origin)`). Names are materialized on `Entity.name` from
the entity registry at load (best-effort; indicators/asns fall back to the id).
The CTI-RAG Neo4j is a **dedicated instance** (`bolt://localhost:7689`), isolated
from the cti-agent graph; `scripts/load_facts_neo4j.py` is the loader. Evidence
content is never copied into Neo4j — it stays in Qdrant and is fetched by id.

## 6. Output data structures [change]

Frozen pydantic, mirroring `types.py` style. Machine-readable so the v1 agent
and the CLI consume the same objects.

- `FactCitation(evidence_id, origin, confidence, label_availability, content="",
  observed_first, observed_last)` — one `supports` edge, with chunk content
  filled from `get_by_chunk_ids` (empty string when the chunk is absent, never
  fabricated).
- `FactRow(fact_id, subject_id, subject_name, predicate, object_id, object_name,
  object_type, aggregate_credibility, conflict, distinct_origins, support_count,
  citations)` — one Fact ready to render; `*_name` best-effort via entity
  registry / ontology, falling back to the id.
- `FactQueryResult(query_repr, intent{subject_id,predicate,object_type}, facts,
  conflicts, fact_query_ms)` — `conflicts` is the convenience view of
  `conflict=True` rows; **both members of a conflict are kept side by side**,
  never resolved (knowledge §6, DECISION-5).

---

## 7. Invariants (things that must never happen)

1. **One bridge only.** `chunk.id == supports.evidence_id` (retrieval §7-2). Do
   not invent a second graph↔vector join.
2. **Judgement is the agent's; tools emit objective facts only.** No
   "is-this-enough" heuristic is baked into a tool. The graph returns structure
   and counts; the LLM decides sufficiency. This keeps v0 deterministic and v1's
   behaviour located in one place.
3. **The graph is auxiliary navigation, not the system of record and not the
   content trunk.** Credibility/confidence are read from M3, never authored here
   (CONTEXT.md: confidence lives on `supports`).
4. **Facts and retrieval must share one chunk-id space.** A citation can only be
   expanded if the live collection holds the `evidence_id`. M4 runs against the
   collection the facts were built from (DM4-2); `verify_bridge` guards drift.
5. **Cooperation is role division in the agent loop, never a routing split on a
   pipeline** (§3). No "graph-vs-vector" branch precedes retrieval.
6. **Conflicts are surfaced, never auto-resolved** (knowledge §6 / DECISION-5).
   Both facts, both supports, both shown.

---

## 8. Open decisions (answer the gate before its phase)

Defaults are *proposed*, not adopted — each needs an explicit yes/override
(00_START_HERE Rule 0: a cheap + irreversible + silent default is a FAIL).

| ID | Decision | Blocks | Proposed / status |
|----|----------|--------|-------------------|
| DM4-1 | Graph backend = **Neo4j**, on a **separate CTI-RAG-only instance** (NOT shared with the cti-agent graph; isolate now, ETL-align ontologies later). Protocol-isolated so consumer logic + unit tests stay backend-free. | v0 | **Confirmed: Neo4j, isolated instance.** |
| DM4-2 | Unify the live collection to `cti_chunks_v5` (the corpus the facts were built from) + `verify_bridge` health probe. | v0 | yes. **Confirmed by user.** |
| DM4-3 | v0 output = structured `FactQueryResult`; LLM prose synthesis is a v1 agent responsibility. | v0/v1 | yes (structure first). |
| DM4-4 | Agent loop on **LangGraph** (outer hard-rail StateGraph + inner create_react_agent + LangSmith tracing, see §9); **sufficiency-judge** convergence (NOT graph-count), step/token budget. | v1 | **Confirmed + built: LangGraph.** |
| DM4-5 | Data breadth: are ten controlled predicates enough for *auxiliary navigation*; is predicate/relation-extraction expansion a separate track? | v1 | enough as auxiliary; expansion inherits M3's predicate-vocab alignment with the attribution-graph track. |
| DM4-6 | Rewrite stays a separate small-model component; M4 does not touch it. | — | yes. |

---

## Done when

- **v0:** `FactStore` (Protocol) + `graph_outline` + `graph_query` + reverse
  bridge + `get_by_chunk_ids` land with deterministic unit tests passing; the CLI
  enumerates "all objects of one (subject, predicate)" with citations,
  credibility, and conflicts from structured params; the live collection is
  unified to v5 and `verify_bridge` passes. No LLM, no routing, no prose.
- **v1 [done]:** the agent loop gathers via graph+vector, a **sufficiency judge**
  decides enough/grounded (not graph M-vs-N), the loop re-retrieves on gaps and
  synthesizes a cited answer within a budget ceiling; citations are validated
  against the gathered evidence. `agentic_answer()` + CLI `agentic`; `answer()`
  routes on `agentic_enabled` (default off until eval proves the win).

---

## 9. v1 — agentic loop (LangGraph) [built]

**Revised from the original §9**, which described a prompt-steered
`create_react_agent` whose convergence leaned on the graph as a "coverage gauge".
Acceptance testing showed that approach was unstable: it oscillated between a
de-facto workflow (over-prescribed prompt) and unreliable free planning, and the
"graph M-vs-N" convergence is PDF-blind / enumeration-only (§2). The built design
relocates the reliability guarantees from the prompt into LangGraph structure —
**structure the guarantees, not the steps.**

### 9.1 Topology — outer hard-rail StateGraph + inner ReAct + EvidenceLedger
An outer `StateGraph` wraps an inner prebuilt `create_react_agent` (the free ReAct
burst — tool choice and multi-hop stay autonomous in the LLM). The outer nodes are
the hard rails. The bridge between them is a side-effect **`EvidenceLedger`**: each
tool closure appends its *full structured result* to the ledger before returning a
bounded LLM-facing summary, so the rail nodes read structured evidence (chunks,
facts, outlines) instead of `create_react_agent`'s stringified `ToolMessage`
transcript.

```
START → agent_turn → sufficiency_gate → (router) → agent_turn | synthesize
                                                       synthesize → citation_assembly → END
```

### 9.2 Tools (in-process, ledger-aware)
- `resolve_entity(name)` — NL name → entity_id candidates (strict, exact-only).
- `graph_outline` / `graph_query` / `facts_for_evidence` — wrap the v0 FactStore;
  append full rows / outlines to the ledger.
- `retrieve(query, top_k)` — wrap the existing single-shot pipeline; append the
  QueryResult to the ledger.
When Neo4j is disabled (empty password) the graph tools degrade to no-ops and the
loop runs vector-only — the architecture is **orthogonal to whether facts exist**
(PDF→graph stays a separate, deferred labelling track).

### 9.3 The stop decision — a sufficiency judge, NOT a graph gauge (the crux)
`sufficiency_gate` is a dedicated LLM-judge node that triangulates, all read from
the ledger (never the transcript):
- **Grounding (faithfulness)** — decompose the draft into claims; is each supported
  by gathered evidence? → `grounded`, `faithfulness_estimate`.
- **Sufficiency (recall)** — decompose the question into sub-questions; which are
  not yet answerable? → `sufficient`, `coverage_gaps`. The judge **owns** this — it
  covers the PDF / prose / comparison cases the graph cannot. Graph outline counts
  are one input, never the sole gate.
- **Budget** — the only *hard* stop.
On insufficient, the judge emits the concrete next step (`suggested_queries`,
`suggested_graph_targets`) and the loop re-enters. The router is a pure function:
`stop`+grounded → synthesize; budget exceeded → synthesize (`stop_reason=budget`);
unparseable verdict → fail closed (`parse_fallback`). Grounding ≠ sufficiency is
kept as two axes; the design no longer conflates faithfulness with recall.

### 9.4 The three pitfalls — structural countermeasures
- **#1 context blow-up**: tools return bounded summaries; the ledger holds the full
  evidence by id. Synthesis is over the top-K chunks **plus** top-N facts (rendered
  as citable pseudo-chunks so graph facts reach the answer), not an unbounded dump
  — an unbounded dump made the reasoning model spend its budget and return an empty
  answer (fixed: `agentic_synthesis_top_k`).
- **#2 convergence**: hard budget ceiling (`agentic_max_iterations` / token cap) +
  the sufficiency judge. Never the model's "feel done", never graph M-vs-N. The
  ceiling is a runaway guard; the operating point is **measured** from LangSmith
  spans, not pinned.
- **#3 grounding guarantee**: `citation_assembly` intersects the model's cited ids
  with `ledger.real_id_set` and drops/counts hallucinated ones — truth is the
  ledger, not the regex. Conflicts are surfaced from `FactRow.conflict`, never
  resolved.

### 9.5 Budget / model / observability
- Model: inner agent + judge on DeepSeek (`agentic_verifier_model=deepseek-chat`);
  synthesis on the certified `["deepseek-v4-flash","deepseek-chat"]` chain.
- Budget: `agentic_max_iterations` (3) + `agentic_token_ceiling` (runaway guard).
- Observability: LangSmith spans per node carry `iteration_count` / `tokens_used` /
  the per-iteration sufficiency verdict — the data to tune the operating point.

### 9.6 Surface / tests / eval
- `agentic_answer(text) -> AgenticAnswer` + CLI `agentic`; `answer()` routes on
  `settings.agentic_enabled` (default **off** until eval proves the win) →
  `answer_single_shot`.
- Tests: pure node logic (ledger, judge-parse, router branches, citation guard,
  synthesize) unit-tested with fakes; `agentic_graph.py` is coverage-omitted,
  verified by a key-guarded e2e (`RAG_CTI_E2E=1`).
- Eval (`scripts/eval_agentic.py`, capability-split, never averaged): sufficiency
  (technique-recall vs gold on `relationship_direct`), grounding (RAGAS
  faithfulness), cost (iterations / tokens / stop_reason). **Measured
  (relationship_direct):** agentic recall **0.79** vs single-shot **0.125** (the
  graph's enumeration completeness), at a **precision cost** (0.086 vs 0.20) —
  over-enumeration: it lists an actor's *full* technique set, not the queried
  subset (partly because graph facts carry no tactic label).

### 9.7 Known open items (measured, not yet tuned)
- **Judge over-eager**: at `max_iterations=3` it tends to keep returning
  `retrieve_more` and hit the budget cap — it sees only the bounded top-N facts
  while the agent gathered many more, so it cannot confirm sufficiency. Fix
  direction: feed the judge the gathered *counts* (per-predicate `n_facts`,
  `n_chunks`), not raw items, and nudge toward "default sufficient unless a clear
  gap".
- **Over-enumeration hurts precision**: the answer needs query / tactic focusing,
  but the graph facts lack tactic labels — a structural limit tied to the labelling
  track, not the loop.

---

## Hard rules inherited from `docs/archive/architecture/HISTORICAL_knowledge_refactor_roadmap.md`

Rule 0 (no cheap+irreversible+silent defaults), CONTEXT.md as term authority,
build by milestone, do not start a phase whose gates are unanswered. M4 is
**deferred until M3 tables are in place and DM4-1 / DM4-2 are answered.**
