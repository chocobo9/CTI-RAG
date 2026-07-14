# Intermediate Dataset Deferred Questions

Date: 2026-06-28

Location category: active Intermediate decision backlog.

Status: deferred questions for after intermediate dataset v0.1.

These questions are intentionally not blockers for v0.1. The first implementation
should preserve enough information to answer them later without reshaping the
base contract.

Current boundary (2026-06-28): v0.1 is an independent intermediate module and
validated delivery package. It is not connected to production RAG ingestion,
Qdrant indexing, RAG runtime retrieval, Neo4j import, or a production teammate
GNN training export. Consumer integration is deferred.

## Downstream Modelling

1. How should the teammate's labelling/GNN workflow weight
   `weak_direct_attribution`, especially OTX `adversary`?

2. Which non-core metadata should become graph nodes in a teammate projection:
   tags, references, sectors, organizations, source contributors, timestamps, or
   publisher/source nodes?

3. Does the teammate need logical Report/Event nodes, or are raw source records
   plus relation mentions sufficient for the first GNN/labelling workflow?

4. Which projection should be productionized first after v0.1: GNN, RAG, Neo4j,
   or a lightweight tabular labelling export?

5. What should the later actor alias / actor mapping policy be? V0.1 preserves
   source-backed attribution cues, but it does not merge actor names across
   sources or decide that two aliases are the same actor.

6. Should a later layer add report/event clustering with an
   `occurrence_count` across source records? The v0.1 package keeps repeated
   reports and overlapping source records as separate records so this can be
   decided later without losing provenance.

7. If two source records appear to describe the same event but name different
   actors, should that become a downstream soft-label input, a conflict signal,
   or both?

## Temporal Splits

8. What timestamp priority policy should be used for train/test splitting:
   publication time, source modified time, observed first/last, fetched time, or
   source-specific priority order?

9. Should temporal split assignment be global, source-specific, or task-specific?

## PDF / Report Handling

10. Which PDF/report metadata fields should be extracted later:
   `published_at`, `source_name`, `report_identifier`, `author`, organization, or
   text spans?

11. Should PDF sections be represented as extracted text units, projection rows,
   or base IntermediateRecords in a later schema version?

## Corpus Expansion

12. Should the next delivery run full local OTX, pDNS, and VirusTotal inventory
    instead of the sampled v0.1 acceptance package? If yes, what skip/failure
    policy is acceptable for malformed or unsupported raw records?

13. Should WHOIS be added once local raw coverage is available, and should it be
    modelled only as infrastructure evidence unless it contains explicit
    attribution cues?

14. Which pDNS / VirusTotal fields should be promoted from deferred/open issues
    into confirmed relation predicates in the next contract revision?

## Portability

15. Do downstream consumers need embedded raw snippets for portability, or is
   `raw_ref` plus included raw files enough?

16. Should future delivery packages include full production projections, or only
    intermediate artifacts and projection smoke-check examples?

17. Which downstream adapter should connect to `rag_cti.intermediate` first, and
    what acceptance test should prove it: RAG index rebuild, GNN training export,
    Neo4j import, or a lightweight tabular labelling package?
