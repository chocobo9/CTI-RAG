---
status: accepted
---

# Use OpenCTI as the I&E primary infrastructure

OpenCTI remains authoritative for its STIX/OpenCTI graph, files, Connectors, Workbenches, enrichment jobs, markings, actor-visible access, and current source state. Intelligence and Evidence is a derived deep Module: it adds immutable Source Captures, versioned extraction/span/segment/embedding/index artifacts, supplemental Provenance and Source Lineage, bounded request receipts, and reproducible retrieval without creating a second editable CTI platform. Workspace owns Working Set selection and the final Model Input Receipt; Case Management alone owns Case evidentiary roles and accepted conclusions.

This keeps general CTI ingestion, graph processing, and operations in the mature platform while accepting a smaller sidecar needed for exact Agent input provenance. The alternatives were to make OpenCTI alone satisfy an undocumented parser/index/replay contract, or to build a parallel CTI platform; the first cannot prove exact Agent inputs and the second duplicates Connector, graph, authorization, and operations complexity.
