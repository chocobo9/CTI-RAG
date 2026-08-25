# Hybrid graph + vector evidence-chain retrieval research

Status: non-normative research.  
Review date: 2026-07-22.

## 1. Question and disposition

This note investigates the requested future CTI retrieval route: a
deterministic, source-backed relation graph used together with lexical/vector
retrieval, so an investigation can receive both relation paths and the source
material that supports them. It does **not** select an embedding model, a
reranker, a vector database, chunk sizes, a graph database, a Tool shape, or a
new Module. It does not authorize bounded search before its own I&E slice is
accepted.

**Design disposition:** retain this as the leading *candidate architecture* for
future relationship-oriented CTI search. It fits the existing owner boundary if
the graph and the indexes are I&E-local, rebuildable derivations; every path
edge and retrieved segment can be traced to an immutable Resource Version,
Source Capture and Source Span; and Workspace continues to decide whether a
query is admitted and whether results enter the Working Set. A graph path and a
retrieval score are not Case facts, evidence references, or conclusions.

The right formulation is not “the graph is truth plus vectors are evidence.”
Rather:

```text
source-backed relation-path candidates     -> explain possible CTI relations
source-backed retrieval-segment candidates -> supply citable source material
qualified composition                      -> an evidence bundle for analysis
Case Management                            -> only later owns a formal conclusion
```

This preserves the user's desired graph-plus-vector route without turning the
derived graph into a second editable CTI graph or treating a generated answer
as a Case assertion.

## 2. What is already determined

The following are current design facts, not recommendations from this note:

1. I&E owns Source Captures, Resource Versions, derivatives, retrieval,
   corpus ranking, declared retrieval coverage, receipts, capsules and
   I&E-issued retrieval candidates. Workspace owns task/run policy,
   deterministic retrieval admission, Working Set selection, rendering and
   disclosure. Pi owns the generic Session and provider-dispatch lifecycle.
   RAG is not a fourth bounded context. [ADR 0016](../adr/0016-keep-rag-ownership-local-and-admit-retrieval-deterministically.md)
2. The active IER1 slice is exact retrieval of one known OpenCTI object. It
   deliberately performs zero model, embedding, reranking or search calls.
   [IER1 contract](../intelligence-evidence/opencti-exact-resource-retrieval-v1-contract.md)
3. IER1 already defines the important provenance primitive for later search:
   a segment is bound to the Source Capture, ordered structured-path spans,
   normalizer/chunker artifacts/configuration and text digest. Equal text from
   another resource remains a different occurrence with its own lineage.
   [IER1 source observation and derivation](../intelligence-evidence/opencti-exact-resource-retrieval-v1-contract.md#5-source-observation-and-derivation)
4. A future bounded search must bind its candidate to its request/receipt,
   Access Principal, Use Purpose, Index Generation and Ranking Profile.
   Scores are meaningful only within that exact combination. Search cannot
   directly create a Capsule or Working Set entry.
   [Working Set cross-context protocol](../agent-workspace/intelligence-working-set-v1-contract.md#12-accepted-cross-context-retrieval-protocol)
5. Access eligibility is checked before relevance; hidden or ineligible
   candidates must not leak through titles, counts, snippets or scores. A later
   model disclosure must be revalidated rather than relying on an old search
   result. [I&E platform design](../intelligence-evidence/intelligence-evidence-platform-design.md)

The current design therefore has a clear home for the desired route. Its gap is
not owner allocation. The gap is the future I&E bounded-search/segment/index
profile and its evaluation contract.

## 3. Terminology correction: Segment is not Context chunk

The already designed Workspace context is a model-input composition. A future
**Retrieval Segment** is a durable, source-derived I&E unit used to find and
cite source material. They must not be made the same object.

| Concern | Retrieval Segment | Workspace context material |
| --- | --- | --- |
| Owner | I&E | Workspace, composed into Pi seams |
| Stable basis | Resource Version, Source Capture, spans, derivation profile | current task/run, Working Set, eligibility and provider attempt |
| Purpose | retrieval, reranking, provenance and replay material | help the model perform this turn |
| Lifetime | source policy / retention controlled by I&E | Session/Run policy and current disclosure eligibility |
| Can be raw source text? | Yes, if source policy permits | Only after Working Set and pre-disclosure revalidation |

Thus chunking must optimize a source-derived retrieval and citation unit, not
try to preassemble the seven context sections. The model-input token budget is
a later rendering constraint; it must not silently corrupt or redefine the
segment source span.

## 4. Retrieval Segment / chunk design hypothesis

### 4.1 Common requirements

A later segment profile should be deterministic, versioned and source-type
aware. Each segment needs a recoverable parent Resource Version/Capture,
ordered Source Spans, text digest, transformation/normalizer/chunker version,
language/content-type and the Index Generation(s) that contain its derived
representation. A re-chunk creates a new derivative/index generation; it does
not mutate history in place.

The profile must additionally keep identifiers in a separately searchable,
normalised lexical form. Do not depend on a prose embedding to find a CVE,
ATT&CK ID, malware hash, IP, domain, URL, ASN or other IOC. This is an
evaluation requirement, not a schema decision.

No fixed token number is recommended here. The old corpus shows why: an
embedding model accepting a long input did not protect later reranking, whose
512-token limit silently truncated 11.4% of one dated collection and 42% of its
OTX pulse chunks. The segment profile must be tested against the *shortest
model stage that consumes its text*, especially the reranker, not merely the
embedding context limit. [Legacy chunk audit](D:/proj/CTI-RAG/.claude/worktrees/optimization/rag_cti/docs/archive/eval/SNAPSHOT_cti_chunks_v2_chunk_truncation_audit.md)

### 4.2 Source-class hypotheses to test

| Source class | Segment boundary hypothesis | What must remain exact | Why |
| --- | --- | --- | --- |
| Narrative report, advisory, ATT&CK prose | heading/section then paragraph/sentence-aware units; bounded overlap only when a claim crosses the boundary | page/section/paragraph spans, heading hierarchy, source ordering | preserves a statement with its local qualifier and citation location |
| PDF extraction | parse pages, headings, prose and tables before segmentation; reject or mark non-text extraction failures | page/coordinate or structured extraction spans and parser artifact | an extracted paragraph without page provenance is weak evidence |
| CTI object / structured JSON | semantic field groups rather than an arbitrary serialised blob | structured paths, field values, object/version identity | exact filters and citations need the original field meaning |
| IOC list, table row, pDNS/WHOIS/VT record | one atomic record/row or typed list block; keep identifier lookup separate from surrounding prose | canonical identifier value, row/path/time span, parent object | prevents large hash lists from swallowing narrative or being lost to reranker truncation |
| Explicit relationship | one source-derived relationship occurrence for traversal; separately segment any procedure/description prose | endpoints, predicate, relation source span, source/version | a relation can be traversed deterministically while prose remains retrievable as evidence |
| ATT&CK ontology / definitions | a versioned definitional projection, separate from observed/asserted source relations | ATT&CK release/object/relationship identity | definitional parent-child traversal is not the same as a source assertion |

The legacy project reached the same source-shape distinction: narrative text was
sentence-aware, field records were atomic, and a MITRE relationship's
description was worth retaining while its templated triple was not the thing to
embed. That is a useful hypothesis, not a current contract.
[Legacy retrieval design](D:/proj/CTI-RAG/.claude/worktrees/optimization/rag_cti/docs/retrieval_layer_design.md)

### 4.3 What not to do

- Do not use one blind fixed-size splitter for PDF prose, JSON, IOCs and
  relationship records.
- Do not make a segment ID or vector point the source of truth for a relation.
- Do not flatten a multi-entity report into every possible entity pair.
- Do not silently trim a segment to make it fit a reranker or model context.
  Select a shorter segment, render less material, or return a bounded failure.
- Do not add model-extracted entity/relation triples as graph facts merely to
  improve recall. They require a distinct qualified derivation/review path.

## 5. Dense, lexical and reranking candidates

### 5.1 BM25 and BGE-M3 are different things

The user is directionally right that both are common choices, but the precise
terminology matters:

- **BM25** is a lexical ranking function over an inverted index; it is not an
  encoder. It is a strong, inspectable baseline for exact identifiers and
  token-level CTI terms when the analyzer preserves IOC forms.
- **BGE-M3** is a candidate embedding model. Its authors state that one model
  can produce dense, learned sparse lexical and ColBERT-style multi-vector
  representations, for more than 100 languages and inputs up to 8192 tokens.
  Its learned sparse output is similar in role to lexical matching but is **not
  BM25**. [BGE-M3 paper](https://arxiv.org/abs/2402.03216), [official model card](https://huggingface.co/BAAI/bge-m3)

BGE-M3 is therefore a credible comparison candidate, not an adopted current
model. The paper's own fusion weights vary by benchmark, says real-world
generalizability still needs investigation, and uses its heavier multi-vector
representation as a later candidate/reranking stage rather than a free
whole-corpus default. CTI-specific identifiers, source populations, languages,
latency, hosting and permitted retention still need qualification.

### 5.2 Candidate-processing route

The industrially conventional and current-design-compatible sequence is:

```text
trusted Scope/Budget + eligibility fence
  -> independent candidate lists
       A. exact field/identifier + BM25 lexical
       B. dense semantic retrieval
       C. optional graph-constrained segment retrieval
  -> rank-based fusion of eligible candidates
  -> optional bounded late rerank
  -> source-span/provenance validation and declared coverage/omissions
  -> I&E Retrieval Candidate / Receipt
```

Rank-based fusion such as Reciprocal Rank Fusion (RRF) is preferable as a first
candidate over a raw weighted sum of BM25 and dense scores because the score
scales differ. Qdrant's primary documentation makes the same point and exposes
RRF/DBSF for dense+sparse hybrid queries; its advice is to tune a weighted
fusion only on an evaluation split. [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)

Reranking is a later candidate stage over a bounded, already eligible union; it
does not authorize a result and it must not see a raw unavailable candidate.
Whether it uses a cross-encoder or BGE-M3 multi-vector mode is an open model/
cost decision. Every output needs to retain its Ranking Profile and Index
Generation so a score does not escape its request-local interpretation.

### 5.3 Why the old results matter, but do not decide the model

The old project has more useful evidence than the earlier audit found. Its
committed `query_set_v3.jsonl` and `attribution_v3_results.json` include a dated
42-query hybrid run against `cti_chunks_v3`: overall Hit@1/5/10 of
0.5238/0.7619/0.8095 and MRR 0.6314. The relationship-direct subset had
Hit@1/5/10 of 0.5/0.8/0.8; the OTX-actor subset had 0.0/0.1429/0.2857. These
are useful failure categories for the new evaluation fixture, especially the
clear need to test relation paths and heterogeneous source coverage.
[legacy result](D:/proj/CTI-RAG/.claude/worktrees/optimization/rag_cti/data/eval/attribution_v3_results.json)

They are not current-model selection proof: it is a dated corpus/configuration;
some categories are explicitly self-gold/directional; the old project records
that `relationship_direct` gold was deterministic ATT&CK traversal but other
categories retained LLM-produced labels. The old embedding decision also
acknowledges that its formal bakeoff was never filled in. [legacy capability
summary](D:/proj/CTI-RAG/.claude/worktrees/optimization/rag_cti/data/eval/capabilities_summary.json),
[legacy embedding decision](D:/proj/CTI-RAG/.claude/worktrees/optimization/rag_cti/docs/rag/EMBEDDING_DECISION.md)

## 6. Storage and Index Generation requirements

There is no need to pick Qdrant now. A vector database is an I&E-internal
retrieval projection store, not an I&E authority, a Case store, a graph source
of truth or a Workspace Tool registry. A viable store/adapter must support:

1. dense vectors and, if the evaluated profile needs them, sparse and/or
   multi-vector representations;
2. pre-ranking filters and indexes for admitted source/version/content-class
   constraints, without exposing non-eligible items;
3. immutable or effectively pinned Index Generations with an atomically
   qualified active generation, coexistence during rebuild and rollback;
4. mapping every point back to the exact I&E segment/derivation identity rather
   than using the point ID as evidence identity;
5. deletion/expiry/retraction propagation and a way to prove index lag and
   omissions; and
6. bounded candidate retrieval, deterministic profile/version observation and
   a trace that supports a later Retrieval Receipt.

Qdrant is a technically plausible candidate because its official documents
describe named vector representations, sparse+dense prefetch/fusion, late
interaction reranking, payload filters and payload indexes. Its WAL and point
versioning protect storage operation, however, not I&E provenance, access,
retention, Source Capture identity or Case Revision. [Qdrant hybrid/rerank
tutorial](https://qdrant.tech/documentation/advanced-tutorials/reranking-hybrid-search/),
[payload and filtering](https://qdrant.tech/documentation/concepts/payload/),
[storage](https://qdrant.tech/documentation/manage-data/storage/)

The recommended persistence *shape* is therefore:

```text
I&E Source Capture / Resource Version         authoritative source-derived record
  -> Derivation Manifest + Retrieval Segments versioned, reproducible derivatives
  -> lexical / vector / graph index generation rebuildable retrieval projections
  -> Retrieval Receipt / Trace                a bounded observed retrieval event
```

No raw vector embedding, graph path, retrieval score or model-generated summary
becomes a Case fact merely because it has been stored.

## 7. Deterministic graph plus vector route

### 7.1 Assessment of the proposed route

The requested lightweight approach is sound in principle:

- use a deterministic source-backed relation projection for entities and
  explicit relationships;
- use lexical/dense retrieval for source segments and narrative evidence;
- compose them into an inspectable relation-and-source bundle.

This gets LightRAG's useful idea—local entity relations plus global relation
chains—without adopting its product as a truth system. LightRAG itself exposes
local, global, hybrid and vector-only query modes, and its paper integrates
graph structures with retrieval. [LightRAG paper](https://arxiv.org/abs/2410.05779),
[official repository](https://github.com/HKUDS/LightRAG)

It cannot mean “always accept a graph result and a vector result as mutually
confirming.” They answer different questions and can fail independently. A
formal relationship-oriented investigation may run both paths, but the receipt
must report, separately, whether each was applicable, complete, empty, omitted
by scope, or failed. A vector hit cannot manufacture a missing edge; a graph
edge without a qualified source span cannot be cited as evidence.

### 7.2 Future request flow

This is a research recommendation, not a new protocol:

```text
1. Task/run creates a non-authoritative query candidate.
2. Workspace deterministically admits a bounded search scope and budget.
3. I&E verifies eligibility before all relevance operations.
4. I&E derives controlled entity/identifier constraints where possible.
5. In parallel, I&E:
   - traverses the qualified graph projection with declared predicate/hop rules;
   - performs lexical/dense retrieval over the same eligible Index Generation.
6. I&E returns a bounded relation-path candidate set and segment candidate set,
   with coverage/omissions and source bindings.
7. I&E assembles only paths whose edges and segments retain qualified lineage.
8. Workspace verifies the receipt/capsule, selects Working Set material, and
   performs the later disclosure revalidation before any model use.
```

Query rewriting, LLM entity extraction or model-suggested traversal can help
produce a candidate query, but cannot alter exact selectors, authorization,
graph facts, source bindings or the admitted Scope. This is consistent with the
existing rule that query candidates are non-executable.

### 7.3 Evidence-chain composition rule

An evidence-chain bundle should show the following links explicitly, rather
than a free-form model summary:

```text
candidate claim / question
  -> path node and explicit predicate
  -> relation occurrence(s), each with Resource Version + Source Span
  -> retrieved narrative/record segment(s), each with Resource Version + Source Span
  -> Retrieval Receipt / Index Generation / Ranking Profile
```

The resulting bundle means “these source-versioned materials and relation
occurrences are relevant to this question.” It does **not** mean the Case has
accepted the relationship or that the analysis is correct. Contradictions,
retractions, source dependence and incomplete coverage remain visible inputs to
assessment, not data to be averaged into one confidence field.

This is the minimal boundary between a useful evidence chain and an accidental
second Case/knowledge authority.

## 8. Evaluation plan derived from the old project

The old fixtures should be imported only after licence, provenance, source
version and access permissions are checked. Their useful mapping is:

| Legacy category | Current future I&E qualification question |
| --- | --- |
| precise / IOC / ATT&CK identifier | Is lexical/exact retrieval correct and IOC-preserving? |
| semantic / fuzzy | Does dense retrieval improve recall over lexical without widening false targets? |
| relationship_direct | Does deterministic traversal return source-backed path edges and evidence segments? |
| OTX actor / malware | Does cross-source identity/alias coverage work, and does absence remain honest? |
| Technique extraction / attribution evaluation | Separate downstream analysis quality; never use it to certify retrieval or Case truth |

For every fixture, retain query class, relevance labels, source/version and
provenance, expected relation paths where applicable, and which labels are
human-reviewed versus deterministic versus weak/directional. Evaluate at least:

- lexical-only, dense-only, and the proposed hybrid/graph route separately;
- Recall@K, MRR and nDCG@K for segment results where labels support them;
- relation-path precision/recall and exact source-span support for graph paths;
- fusion/reranker ablations, latency/cost and index-generation reproducibility;
- authorization, expiry/retraction, incomplete coverage, no-result and
  wrong-Access-Principal/Use-Purpose non-disclosure; and
- claim-to-source-span support after model use, separate from retrieval rank.

Do not average these into one “RAG score.” In particular, a high retrieval
metric cannot certify attribution or Case truth, and a high model faithfulness
score cannot prove that the retriever had complete coverage.

## 9. Decisions still open

The following must be decided only in the future bounded-search I&E slice:

1. source populations, languages and licences that may become a searchable
   corpus;
2. segment profiles by source class, extraction quality policy and numeric
   segment/reranker/context budgets;
3. graph projection source(s), allowed relation types/hops and treatment of
   aliases, revocation and conflicting assertions;
4. lexical analyzer/token normalisation and whether BM25 remains independent
   beside an evaluated learned sparse representation;
5. BGE-M3 or another embedding candidate, hosting, model revision, dimensions,
   update/re-embedding policy and multilingual qualification;
6. whether dense/hybrid/reranking materially improves the authorised lexical
   baseline, and the quality/latency/cost thresholds required to keep it;
7. vector/graph storage engine and its operational qualification; and
8. exact retrieval coverage, fusion/reranker profile, result rendering and
   evidence-chain citation semantics.

## 10. Bottom line

Keep the intended route: deterministic relation paths plus retrieval of
versioned source evidence. The current I&E/Workspace split supports it cleanly.
Start its future design with Retrieval Segment and derivation/index-generation
contracts, then qualify lexical and graph baselines using the old fixture
categories, and only then decide whether BGE-M3 dense/sparse/multi-vector and a
reranker earn their additional cost and complexity. Do not make the graph, a
vector store, a score or an LLM-generated chain into Case authority.

