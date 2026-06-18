# CTI-RAG Consumption-Layer Design (M4)

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

- **Graph (Fact/supports) = the meta layer / map / coverage gauge.** It answers
  *"what categories of relation exist for this entity, how many, organized how —
  and what is missing?"* Because the facts are **controlled hard triples**
  (entity-ids + a closed predicate set + deterministic `fact_id`), the graph can
  be **enumerated exactly and exhaustively**. This is what a vector top-k can
  never give: completeness. The graph is the agent's basis for *planning* and
  for *judging sufficiency*.
- **Vector (chunks) = the content layer.** It answers *"what does the source
  actually say?"* — prose, semantics, detail. It is the home of the data itself.

**The graph is auxiliary, not the trunk.** It is bounded by data breadth (ten
controlled predicates today; DM4-5). It cannot carry the *content* of an answer.
But it supplies the one thing vector retrieval structurally cannot: a
**completeness gauge** ("the graph says 30 `uses` edges exist; the answer
covered 5 → incomplete").

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

1. **Graph gives the map.** For the entity in play, what relation categories
   exist and how many (the coverage gauge).
2. **Agent plans + judges sufficiency against the map.** "To answer this, which
   categories do I need? Which do I not yet have content for?" — this is the
   "does it need more categories / more organized data" judgement.
3. **Vector fetches content.** For the parts the map says must be expanded,
   retrieve the actual chunks.
4. **Agent re-checks coverage against the graph.** Graph says 30 `uses`; answer
   covers 5 → not done → loop.

So "it can't be split" is correct: graph and vector are **interleaved** — graph
governs *what to fetch and whether it's complete*, vector governs *what the
content is*. This is exactly the original intent — *"the agent decides based on
the completeness of the graph collection and the vector evidence"* — made
precise: the graph, being exhaustively enumerable, **is** the objective
completeness gauge; the vector supplies the evidence content.

The split between graph and vector therefore never appears as a routing decision
on a pipeline. It appears only as role division inside the agent loop (v1).

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
- **M4.v1 — Agent loop [change, deferred].** Wrap the v0 tools in a ReAct-style
  loop where the LLM does the §3 alternation: plan from the map → fetch content
  → re-check coverage → converge, then synthesize a cited prose answer. The
  *sufficiency judgement lives in the LLM*; the tools only ever return objective
  numbers (invariant 2). Gated by DM4-4.

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
| DM4-4 | Agent loop on **LangGraph** (state machine + LangSmith tracing, see §9); multi-hop, coverage-gauge convergence, step/token budget. | v1 | **Confirmed: LangGraph** (system trajectory + LangSmith already wired). |
| DM4-5 | Data breadth: are ten controlled predicates enough for *auxiliary navigation*; is predicate/relation-extraction expansion a separate track? | v1 | enough as auxiliary; expansion inherits M3's predicate-vocab alignment with the attribution-graph track. |
| DM4-6 | Rewrite stays a separate small-model component; M4 does not touch it. | — | yes. |

---

## Done when

- **v0:** `FactStore` (Protocol) + `graph_outline` + `graph_query` + reverse
  bridge + `get_by_chunk_ids` land with deterministic unit tests passing; the CLI
  enumerates "all objects of one (subject, predicate)" with citations,
  credibility, and conflicts from structured params; the live collection is
  unified to v5 and `verify_bridge` passes. No LLM, no routing, no prose.
- **v1:** the agent loop performs the §3 alternation (plan from map → fetch
  content → re-check coverage → converge) and returns a cited answer, within a
  budget ceiling, with the sufficiency judgement in the LLM.

---

## 9. v1 — agentic loop (LangGraph) [design]

In-process LangGraph state machine letting an LLM orchestrate the v0 tools (§3).
Chosen (DM4-1/DM4-4) for the system trajectory — durable execution, multi-agent
headroom, audit-grade tracing — and because LangSmith is already wired
(`config.py`). Tools are **in-process LangChain tools, NOT MCP** (MCP is a later,
optional cross-app concern, §1).

### 9.1 Tools (in-process)
- `resolve_entity(name) -> entity_id[]` — NL name → entity_id (reuse ontology
  aliases / `understand()`); must handle 0 / multiple candidates. **v1-new.**
- `graph_outline` / `graph_query` / `facts_for_evidence` — wrap the v0 FactStore.
- `vector_search(query, top_k)` — wrap the existing retrieval pipeline.

### 9.2 AgentState (the only inter-node channel)
`query` · `entity_ids` · `outline` (coverage **numbers** only) · `collected_facts`
· `retrieved_chunks` · `step` · `tokens_used` · `done`.

### 9.3 Graph
Nodes: `resolve` → `map` (outline → coverage numbers) → `plan` (LLM reads outline
+ collected, picks next tool or stops) → `act` (run chosen tool) → `check`
(coverage: outline says N, collected covers M) → `synthesize` (cited answer).
Conditional edges: `plan`→`act` | `synthesize`; `check`→`plan` (loop) | `synthesize`.

### 9.4 The three real pitfalls — explicit countermeasures (not an MVP afterthought)
- **#1 context blow-up**: `outline` holds only `predicate→count`, never the 223
  facts. `graph_query` results do NOT all enter the LLM context — only the category
  the agent named, summarised (object-name list); full citations sit beside the
  state and are fetched by id only at `synthesize`.
- **#2 convergence**: hard-bounded — LangGraph `recursion_limit` + a coverage gauge
  (the `plan` prompt is forced to compare collected M vs outline N) + a step cap.
  Never trust the model to "feel done".
- **#3 error recovery**: tool errors (entity unresolved / 0 / many) are fed back for
  the LLM to clarify or reroute; LangGraph checkpointing resumes a crashed run.

### 9.5 Budget / model / observability
- Model: DeepSeek (via langchain) or Anthropic — **measured on real queries in the
  loop**, not chosen on paper.
- Budget: `max_steps` + token ceiling.
- Observability: LangSmith auto-traces every node/edge/state; custom span metadata
  carries `iteration_count` / `coverage_ratio` / `tokens_used`.

### 9.6 Surface / tests
- `ask(query)` public fn + CLI `ask` (NL in, cited prose out).
- Tests: node logic with mock LLM + mock tools (plan/check/convergence/error
  branches); a few e2e with real LLM + tools.

---

## Hard rules inherited from `00_START_HERE.md`

Rule 0 (no cheap+irreversible+silent defaults), CONTEXT.md as term authority,
build by milestone, do not start a phase whose gates are unanswered. M4 is
**deferred until M3 tables are in place and DM4-1 / DM4-2 are answered.**
