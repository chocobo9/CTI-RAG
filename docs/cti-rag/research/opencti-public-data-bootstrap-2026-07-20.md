# OpenCTI Public Data Bootstrap Without a Filigran Account

Status: primary-source research for a local diagnostic bootstrap.

Research date: 2026-07-20.

## Question and short answer

A locally deployed OpenCTI instance can ingest useful public CTI without a Filigran/OpenCTI cloud account. OpenCTI is the platform and integration layer; external-import Connectors fetch data from source-owned feeds or repositories and write it into the local instance. Every Connector still needs a token issued by that local OpenCTI instance, but several sources require no third-party account, API key, or subscription.

There is no supported path that makes another organization's existing OpenCTI Cases available to a local instance merely because OpenCTI was installed. The official public bootstrap sources below provide reference knowledge, ATT&CK content, vulnerabilities, and indicators. They do not provide a shared corpus of populated investigation Cases. A diagnostic Case must therefore be created in the local instance and populated with imported public objects.

## Platform, service, and data are different things

- The OpenCTI repository describes OpenCTI as an open-source platform for structuring, storing, organizing, and visualizing CTI. It also says integrations such as MITRE ATT&CK are supplied through Connectors; this is not a claim that the platform image embeds a shared investigation database. [OpenCTI platform repository](https://github.com/OpenCTI-Platform/opencti)
- OpenCTI's Connector documentation defines import Connectors as processes that retrieve information from an external organization, application, or service, convert it to STIX 2.1, and import it through workers. It also requires `OPENCTI_URL` and `OPENCTI_TOKEN` for every Connector. That token authenticates to the operator's own OpenCTI instance. [Official Connector documentation](https://docs.opencti.io/latest/deployment/connectors/)
- XTM Hub is identified by the same documentation as the Integrations Library where available Connectors are catalogued. The catalog is not itself evidence of entitlement to every provider's data. Each Connector's own configuration and the source provider's terms determine whether a separate credential or subscription is needed. [Official external-Connector guide](https://docs.opencti.io/latest/usage/import/external-connectors/)
- Filigran-hosted SaaS or Enterprise capabilities are not required for the public local bootstrap described here. They also should not be conflated with access to third-party commercial intelligence feeds.

## Public sources that do not require a source account

All rows require outbound network access and a token for the **local** OpenCTI instance. "No source credential" means no additional credential for the upstream data source.

| Source / official Connector | Source credential | Imported content | Bootstrap assessment |
| --- | --- | --- | --- |
| OpenCTI Datasets | None | OpenCTI-maintained sectors, geography, and companies reference entities | Small foundational catalog, but not threat reports or Cases. The official Connector defaults to public files in the OpenCTI datasets repository. [Connector README](https://github.com/OpenCTI-Platform/connectors/blob/c15d3ee11f58b6d9b302127926ac95e37df1eb8d/external-import/opencti/README.md), [datasets repository](https://github.com/OpenCTI-Platform/datasets/tree/709e73e4d28688fe89df94daf99d4204a83d7404) |
| MITRE ATT&CK | None | Enterprise, Mobile, and ICS ATT&CK plus CAPEC, from official public GitHub content | Best first knowledge bootstrap: official, stable, and included as "default data" in the official Docker composition. It creates techniques, groups, malware, tools, campaigns, mitigations, and relationships, not Cases. [Connector README](https://github.com/OpenCTI-Platform/connectors/blob/c15d3ee11f58b6d9b302127926ac95e37df1eb8d/external-import/mitre/README.md), [MITRE ATT&CK STIX data](https://github.com/mitre-attack/attack-stix-data), [official Docker composition](https://github.com/OpenCTI-Platform/docker/blob/d3aa93833fe16bfd272e76b2876f0a6a81e90/docker-compose.yml) |
| CISA Known Exploited Vulnerabilities | None | KEV Vulnerabilities and optionally Software/vendor context | Good small second source. The Connector documents the CISA JSON catalog as publicly available without authentication. [Connector README](https://github.com/OpenCTI-Platform/connectors/blob/c15d3ee11f58b6d9b302127926ac95e37df1eb8d/external-import/cisa-known-exploited-vulnerabilities/README.md), [CISA KEV catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) |
| CVEProject cvelistV5 | None | CVE v5 records, Notes, and optional Software/vendor objects | Avoid for the very first smoke unless needed: it clones a repository of several GB and performs a historical import. It is a no-key alternative to the NVD Connector. [Connector README](https://github.com/OpenCTI-Platform/connectors/blob/c15d3ee11f58b6d9b302127926ac95e37df1eb8d/external-import/cvelistv5/README.md), [CVEProject repository](https://github.com/CVEProject/cvelistV5) |
| URLhaus / ThreatFox recent CSV | None according to the current official Connector contracts | Recent malicious URLs or IOCs, with observables/indicators and selected relationships | Useful for a more operational test Case after the basic smoke. Restrict the first import to the recent feeds to control volume. [URLhaus Connector](https://github.com/OpenCTI-Platform/connectors/blob/c15d3ee11f58b6d9b302127926ac95e37df1eb8d/external-import/urlhaus/README.md), [ThreatFox Connector](https://github.com/OpenCTI-Platform/connectors/blob/c15d3ee11f58b6d9b302127926ac95e37df1eb8d/external-import/threatfox/README.md), [URLhaus](https://urlhaus.abuse.ch/), [ThreatFox](https://threatfox.abuse.ch/) |

The official Docker composition currently declares the OpenCTI Datasets and MITRE Connectors under "OPENCTI DEFAULT DATA". This means the standard local deployment already has a supported zero-source-account bootstrap path when those services are enabled and can reach their public GitHub endpoints. It does not eliminate the local `OPENCTI_TOKEN` requirement. [Official Docker composition](https://github.com/OpenCTI-Platform/docker/blob/d3aa93833fe16f06bfd272e76b2876f0a6a81e90/docker-compose.yml)

## Sources that do require another credential or entitlement

- The current official NVD CVE Connector declares an NVD API key mandatory. For a no-account bootstrap, use CISA KEV or CVEProject cvelistV5 instead. [NVD CVE Connector](https://github.com/OpenCTI-Platform/connectors/blob/c15d3ee11f58b6d9b302127926ac95e37df1eb8d/external-import/cve/README.md)
- The official MISP deployment example requires both a MISP URL and `MISP_KEY`; running OpenCTI does not grant access to a MISP instance. [Official Connector documentation](https://docs.opencti.io/latest/deployment/connectors/)
- Commercial-provider Connectors do not confer provider entitlement. A Connector being listed or its source code being available does not make the vendor's feed public. Its provider token, licensed endpoint, or subscription must be obtained separately and evaluated Connector by Connector.

## File import is another no-provider-account path

OpenCTI officially supports importing STIX JSON/XML, MISP JSON, YARA, documents, and mapped CSV through import Connectors and analyst workbenches. This can load a source-owned or locally prepared fixture without any remote feed account, subject to the local user's upload capability. Imported items remain local OpenCTI knowledge after workbench review/validation. [Official file-import documentation](https://docs.opencti.io/latest/usage/import-files/)

## Fastest diagnostic Case bootstrap

For the CTI-RAG live smoke, the goal is to exercise a real OpenCTI deployment and its GraphQL Case traversal, not to pretend that a locally authored Case is an external production incident.

1. Run or enable the official OpenCTI Datasets and MITRE Connector services already present in the official Docker composition. They need the local OpenCTI administrator/service token, but no Filigran or MITRE account.
2. Wait for the MITRE Connector's first successful work and confirm imported ATT&CK objects are visible.
3. In the local OpenCTI UI, create one Incident Response Case. Add one or more imported ATT&CK objects to the Case and add one Task. OpenCTI officially supports Cases containing arbitrary entities/relationships and associated Tasks. [Official Case-management documentation](https://docs.opencti.io/latest/usage/case-management/), [official manual-creation documentation](https://docs.opencti.io/latest/usage/manual-creation/)
4. Use a local read-capable user/token and the new Case's internal ID as the existing live-smoke bundle. This exercises real authentication, schema introspection, root probes, Task traversal, object pagination, double observation, `prompt`, close, and reopen against the actual local deployment.
5. If a vulnerability-focused Case is preferred, add CISA KEV after the MITRE smoke and attach a small number of imported KEV objects. Do not start with the full NVD/CPE history path.

This result is accurately described as a **real local OpenCTI Case backed by public source data**. It is not an existing real-world customer investigation, a production tenant qualification, or access to Filigran/customer private data.

## Design disposition

Adopt the public local bootstrap as the immediate live target path:

- prefer OpenCTI Datasets + MITRE for the first smoke;
- create the minimal Case/Task/object membership locally because the current Orientation contract reads Cases and public Connectors do not supply a shared investigation Case;
- optionally add CISA KEV for a second source without a third-party credential;
- retain deployment qualification and actor-scoped completeness exactly as specified by the current Orientation contract;
- label the evidence "local live smoke with public-source data", not "production qualification" or "external real-case validation";
- do not add SaaS, commercial-feed, I&E Retrieval, or write-path scope merely to obtain test data.

No normative contract change follows from these source facts. The existing live-smoke input remains correct: exact local GraphQL endpoint, a token issued by the local instance, and the internal ID of the locally created Case.
