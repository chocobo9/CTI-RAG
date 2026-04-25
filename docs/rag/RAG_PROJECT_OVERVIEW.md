# RAG-Powered Cyber Threat Intelligence System
## Project Overview

---

## 1. Motivation & Business Context

### 1.1 The SOC Analyst Bottleneck

Security Operations Centers (SOCs) face a compounding crisis of scale. According to the **2025 Pulse of AI-Powered SOC Report** (739 cybersecurity leaders surveyed), alert volume has increased for 77% of organizations, with 46% reporting a spike of over 25% in the past year. A typical SOC processes an average of **3,832 alerts per day** — a volume that far exceeds human analytical capacity.

The human cost is severe. The **SANS 2024 SOC Survey** found that 66% of SOC teams cannot keep pace with alert volume, while 70% of analysts with five years of experience or less leave their role within three years. Investigations themselves are slow: it takes an average of **70 minutes to fully investigate a single alert**, with 56 minutes passing before anyone acts on it at all (*State of AI in the SOC 2025*). With 62% of alerts ignored altogether and 55% of teams admitting to regularly missing critical alerts, the bottleneck is not a tools problem — it is a **knowledge access and context problem**.

At the core of this bottleneck is the heterogeneity and volume of Cyber Threat Intelligence (CTI) data that analysts must process. Threat reports arrive from dozens of sources — AlienVault OTX, VirusTotal, Unit42, Mandiant, CISA advisories — in inconsistent formats: natural language PDF reports, structured JSON feeds, STIX bundles, WHOIS records, and passive DNS data. Normalizing, contextualizing, and querying across these sources manually is unsustainable at the pace of modern attacks.

### 1.2 The LLM Knowledge Gap

Large Language Models (LLMs) offer a promising path to automating CTI analysis. However, they face a fundamental limitation in this domain: **parametric knowledge staleness**. LLMs are trained at a fixed point in time, while the threat landscape evolves continuously. The **LLM-Assisted Proactive Threat Intelligence** study (arxiv:2504.00428, 2025) demonstrated this gap directly — GPT-4o was unable to answer questions about CVE-2024-39471, a vulnerability disclosed after its training cutoff, while a RAG-augmented system retrieved and correctly answered the same query from a live feed.

This is not an edge case. The **Flashpoint 2024 Cyber Threat Intelligence Index** disclosed 17,518 new vulnerabilities in H1 2024 alone, with 45% rated high to critical. Attackers adapt faster than LLM retraining cycles allow. As the **CrowdStrike 2026 Global Threat Report** notes, the average eCrime breakout time has dropped to 29 minutes — a 65% speed increase from 2024 — while AI-enabled adversary attacks surged 89%.

The implication is clear: LLMs relying solely on parametric knowledge cannot be trusted for real-time CTI tasks. **Retrieval-Augmented Generation (RAG)** addresses this by coupling LLM reasoning with a continuously updated external knowledge base, grounding outputs in verifiable, up-to-date sources rather than potentially stale training data.

### 1.3 Validated by Related Work

Several recent systems validate the RAG approach for CTI:

- **RAGIntel** (Alhuzali, *PeerJ Computer Science*, 2025): A RAG-based LLM system evaluated on 339 attack investigation queries. Employs hybrid retrieval with reranking and compression, outperforming standalone LLMs on CTI benchmarks (CTIBench, CTI-ATTACK datasets).

- **AgCyRAG** (CEUR Workshop, 2024): Explicitly identifies that standard RAG approaches "overlook symbolic representations and conceptual relations essential in cybersecurity — including network structures, IT asset hierarchies, and attack patterns." Proposes combining structured and unstructured CTI sources via specialized retrieval agents.

- **LLM-Assisted Proactive Threat Intelligence** (arxiv:2504.00428, 2025): Demonstrates RAG with continuous threat intelligence feeds significantly outperforms vanilla GPT-4o on recently disclosed vulnerabilities, validating the real-time private data hypothesis.

- **LocalIntel** (Mitra et al., cited in arxiv:2505.12786): Fuses public OSINT feeds with internal private reports, achieving 93% accurate contextualization across 58 zero-day triggers while substantially reducing analyst workload — directly analogous to the architecture proposed here.

---

## 2. Project Definition

### 2.1 Problem Statement

Security analysts need to query and synthesize threat intelligence from heterogeneous, continuously updated sources. Current LLMs cannot reliably answer questions about recent threats, private enrichment data, or organization-specific context because this knowledge is absent from their training. Manual cross-source analysis does not scale.

### 2.2 Proposed Solution

A production-grade RAG system that ingests heterogeneous CTI data sources into a queryable knowledge base, enabling LLMs to retrieve contextually relevant, up-to-date intelligence at inference time. The system is designed as a standalone module with a well-defined interface, intended for future integration as the knowledge layer of a DNS-based threat intelligence agent.

### 2.3 System Boundaries

**In scope:**
- Multi-source CTI ingestion pipeline (structured and unstructured)
- Document preprocessing and chunking for heterogeneous formats
- Embedding and vector store management with incremental updates
- Hybrid retrieval (semantic + keyword) with reranking
- Query translation and optimization
- Evaluation framework (recall, MRR, faithfulness, context precision)
- Observability and tracing

**Out of scope:**
- Agentic orchestration layer (future DNS project)
- Fine-tuning of LLMs
- Frontend UI
- Multi-tenancy

---

## 3. Data Sources

### 3.1 Tier 1 — Real-Time Dynamic Feeds (Primary RAG Value)

These sources contain data that LLMs have never seen, satisfying the core RAG prerequisite of non-parametric private/real-time knowledge:

| Source | Format | Content | Update Frequency |
|--------|--------|---------|-----------------|
| **AlienVault OTX Pulses** | JSON + natural language | Threat summaries, IOCs, ATT&CK mappings, malware families, threat actor descriptions | Continuous (19M+ indicators/day) |
| **VirusTotal** | JSON | File/URL/domain reputation, behavioral analysis, community comments | Real-time |
| **WHOIS / Historical WHOIS** | Semi-structured text | Registrar, registrant email, creation date, name servers | Per-query |
| **Passive DNS** | Key-value + JSON | Subdomain history, IP resolution history, ASN data | Per-query |

**Key justification**: OTX Pulses in particular are semantically rich documents — each pulse contains a natural language description, contextual tags, ATT&CK technique IDs, and related IOCs. This is not a URL list; it is a continuously updated corpus of analyst-written threat reports, exactly the kind of non-parametric knowledge RAG is designed to leverage.

### 3.2 Tier 2 — Static Knowledge Base (Semantic Grounding)

These sources provide stable, authoritative knowledge that enriches retrieval context:

| Source | Format | Content |
|--------|--------|---------|
| **MITRE ATT&CK** | STIX 2.1 JSON | 500+ technique descriptions, procedure examples, detection guidance, mitigation strategies |
| **Public CTI Reports** | PDF | Unit42, Mandiant, CISA advisories — campaign analyses, APT profiles, infrastructure patterns |

**Note on MITRE ATT&CK**: The dataset is available at `https://attack.mitre.org/resources/attack-data-and-tools/` and `https://github.com/mitre-attack/attack-stix-data`. Each technique entry contains rich natural language descriptions and real-world procedure examples that are semantically distinct and suitable for embedding.

### 3.3 Data Architecture Decision

Raw feeds from PhishTank and OpenPhish are **not** included in the RAG knowledge base — their data is URL lists with no semantic text content. They remain useful as enrichment query targets (lookup tools), not as knowledge base documents.

---

## 4. Technical Architecture

### 4.1 Core Components

**Ingestion & Preprocessing Layer**
- Source-specific connectors for OTX API, VirusTotal API, WHOIS services, passive DNS
- Format normalization: PDF parsing, JSON field extraction, semi-structured text templating
- Chunking strategy: semantic chunking for natural language documents; structured field preservation for JSON records

**Embedding & Vector Store**
- Embedding model: selected based on MTEB leaderboard, evaluated against security-domain text
- Vector store: Qdrant (production-ready, single-container deployment, enterprise features)
- Incremental update mechanism: time-windowed refresh (aligned with ARES '24 finding that 95% of DNS patterns expire within 3 months)

**Retrieval Layer**
- Hybrid retrieval: dense (semantic) + sparse (BM25 keyword) search
- Query translation: HyDE (Hypothetical Document Embeddings) for sparse input queries
- Reranking: LLM-based reranking (per TechniqueRAG approach) to improve domain-specific precision

**Generation Layer**
- Tiered LLM strategy: lightweight models for routing, mid-tier for analysis, heavy models for report generation
- Context injection via tool_result pattern (dynamic, not hardcoded in system prompt)

**Observability**
- LangSmith tracing for retrieval and generation steps
- RAGAS-based evaluation: faithfulness, answer relevancy, context recall, context precision
- MRR tracking per query type

### 4.2 Key Design Decisions

- **Qdrant over FAISS**: FAISS is an algorithm library requiring manual persistence management; Qdrant is a production-ready service with payload filtering, incremental updates, and a clean Python SDK.
- **HyDE for sparse queries**: Security text (domain names, WHOIS fields) is semantically distant from ATT&CK technique descriptions. HyDE bridges this gap by generating a hypothetical matching document before retrieval, improving recall on short/technical inputs (validated in Stanford TTP attribution study, R²=0.81 frequency correlation).
- **Hybrid retrieval**: Pure semantic search misses exact IOC matches (IP addresses, CVE IDs, domain names); pure keyword search misses semantic synonyms. Hybrid combines both.

---

## 5. Evaluation & Success Criteria

### 5.1 Evaluation Philosophy

This system is evaluated as an engineering retrieval system, not a benchmark QA model. Due to the absence of standardized ground truth datasets in CTI workflows, evaluation focuses on three dimensions: retrieval relevance, context usefulness for downstream LLM reasoning, and measurable reduction of hallucination compared to a no-RAG baseline.

### 5.2 Query-Based Evaluation Design

A curated query set is constructed to simulate real SOC analyst workflows across three categories:

**IOC Enrichment Queries** — e.g., "What is known about domain X?" Expected retrieval: OTX pulses, WHOIS/DNS context, related indicators.

**Technique Mapping Queries** — e.g., "Which ATT&CK technique relates to this behavior?" Expected retrieval: MITRE ATT&CK entries, supporting CTI report chunks.

**Threat Report Understanding** — e.g., "Summarize threat activity associated with this campaign." Expected retrieval: relevant report segments, high-information sections.

### 5.3 Retrieval Metrics

**Top-k Relevance (Primary)**: For each query, does the top-k retrieved set contain at least one relevant document? Scored binary per query, averaged across the query set. Target: ≥ 70%.

**MRR (Mean Reciprocal Rank)**: Measures the rank position of the first relevant document. Directly comparable to Stanford TTP attribution baseline (average rank 7.55/29).

**Context Usefulness**: Human or LLM-as-judge evaluation of whether retrieved documents are sufficient to support downstream reasoning. Scored on a 3-point scale (insufficient / partial / sufficient).

### 5.4 RAG vs. Baseline Comparison

Two configurations are compared to validate RAG's contribution:

**Baseline (No RAG)**: LLM answers using parametric knowledge only.

**RAG-augmented**: LLM answers with retrieved context injected.

Evaluation dimensions: hallucination frequency on post-cutoff threat data, answer specificity (grounded in retrieved evidence vs. generic), and correctness on queries involving OTX pulses and WHOIS data that LLMs have not been trained on.

The LLM-Assisted Proactive Threat Intelligence study (arxiv:2504.00428) provides a direct methodological reference: the same GPT-4o query about CVE-2024-39471 returned no useful answer without RAG and a correct, grounded answer with RAG.

### 5.5 Ablation Study

To isolate which components drive performance gains:

- Semantic-only vs. hybrid retrieval (semantic + BM25)
- With vs. without HyDE query translation
- Chunking strategy variations (fixed-size vs. semantic chunking)

### 5.6 Success Criteria

The system is considered effective if:

- Top-k relevance ≥ 70% across the query set
- RAG-augmented responses show measurably lower hallucination than baseline on post-cutoff CTI queries
- Hybrid retrieval improves IOC-level matching over semantic-only retrieval
- Retrieved context is rated sufficient for downstream reasoning in ≥ 60% of cases

---

## 6. System Role & Boundaries

This system is a **knowledge retrieval layer**, not a decision-making system.

It does not classify threats, perform incident response, or replace analyst judgment. It aggregates heterogeneous CTI data into a queryable knowledge base, provides grounded context to LLMs at inference time, and improves information accessibility across sources that would otherwise require manual cross-platform lookup.

The interface is intentionally minimal: `query(text) → [Document]`. This keeps the system composable and testable independently of any downstream agent or application.

---

## 7. Relation to Future Work

This RAG system is designed as the **knowledge layer** of a larger DNS-based threat intelligence agent (currently scoped separately). The interface is intentionally clean:

- RAG exposes a retrieval API: `query(text) → [Document]`
- The future agent calls this API as a tool within its LangGraph orchestration
- MITRE ATT&CK mapping in the analysis agent directly uses this knowledge base

This separation allows the RAG system to be developed, evaluated, and iterated independently before integration, while ensuring architectural compatibility with the agent layer.

---

## 6. References

- Alhuzali, A. (2025). LLM-powered threat intelligence: a RAG approach for cyber attack investigation. *PeerJ Computer Science*. DOI: 10.7717/peerj-cs.3371
- AgCyRAG: Agentic Knowledge Graph based RAG for Cybersecurity. CEUR Workshop Proceedings Vol-4079.
- LLM-Assisted Proactive Threat Intelligence for Automated Reasoning. arXiv:2504.00428 (2025).
- Lekssays et al. TechniqueRAG: RAG for Adversarial Technique Annotation in CTI Text. arXiv:2505.11988 (2025).
- Leite, C., den Hartog, J., & dos Santos, D. R. (2024). Using DNS Patterns for Automated Cyber Threat Attribution. *ARES 2024*. DOI: 10.1145/3664476.3670870
- Guru, K., Moss, R. J., & Kochenderfer, M. J. (2025). On Technique Identification and Threat-Actor Attribution using LLMs and Embedding Models. arXiv:2505.11547
- SANS 2024 SOC Survey. Escal Institute of Advanced Technologies.
- 2025 Pulse of AI-Powered SOC Report. Cybersecurity Insiders / Gurucul. (739 respondents)
- Flashpoint (2024). Cyber Threat Intelligence Index: 2024 Midyear Edition.
- CrowdStrike (2026). Global Threat Report.
