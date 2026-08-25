# OpenCTI real-Case live Orientation smoke

Date: 2026-07-20  
Target: local OpenCTI `7.260715.0` at the CTI-RAG lab  
Disposition: adopted as diagnostic deployment evidence only

## Question

Can the current read-only `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn` Interface read a real actor-visible Incident Response Case from a stock OpenCTI deployment, preserve normal TLS verification, and complete a JSONL close/reopen smoke without a paid model?

## Primary-source facts

- OpenCTI documents Incident Response as a Case kind that can contain knowledge objects and associated Tasks. The documentation distinguishes the Case from the incident and describes Tasks as work performed in the Case context. [OpenCTI Case management](https://docs.opencti.io/latest/usage/case-management/)
- OpenCTI's GraphQL API uses bearer authentication and applies the API key user's access rights. The official API reference states that UI actions are also available through GraphQL and directs integrators to the platform schema, browser requests, or official client source for concrete mutations. [OpenCTI GraphQL API](https://docs.opencti.io/latest/reference/api/)
- At the pinned `7.260715.0` tag, the official Python client creates a Case Incident through `caseIncidentAdd`, accepts `objects` and `objectMarking`, and adds Case object membership through `stixDomainObjectEdit(...).relationAdd` with relationship type `object`. [Pinned Case Incident client source](https://github.com/OpenCTI-Platform/opencti/blob/7.260715.0/client-python/pycti/entities/opencti_case_incident.py)
- At the same tag, the official client creates a Task through `taskAdd` and accepts `objects`, which is the supported way used here to associate the Task with the Case. [Pinned Task client source](https://github.com/OpenCTI-Platform/opencti/blob/7.260715.0/client-python/pycti/entities/opencti_task.py)
- Caddy's local HTTPS uses an internal CA for local names, persists the CA under its data directory, and requires clients to trust the root explicitly when automatic trust installation is unavailable or intentionally skipped. [Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https), [Caddy global TLS options](https://caddyserver.com/docs/caddyfile/options#skip-install-trust)
- Node extends its normal CA set from a PEM file named by `NODE_EXTRA_CA_CERTS`; the variable is read only when the Node process starts. [Node 24 CLI documentation](https://nodejs.org/docs/latest-v24.x/api/cli.html#node_extra_ca_certsfile)

## Deployment observations

The local lab retained OpenCTI's HTTP listener on loopback and added a separate Caddy `2.10.2-alpine` reverse-proxy Adapter pinned to the linux/amd64 manifest digest `sha256:d8c17a862962def15cde69863a3a463f25a2664942eafd7bdbf050e9c3116b83`. Caddy exposes only `https://localhost:18443`; its CA private material stays in the Docker named volume. The ignored host `tls-ca/` directory contains only the exported public root certificate. Its observed SHA-256 was `743CB91E92F1851D8240361A07C7804458292E180E74303B1381D153AD28B53E`.

Node 24.14 rejected that endpoint without the root (`UNABLE_TO_GET_ISSUER_CERT_LOCALLY`) and completed a request after the same public root was supplied through `NODE_EXTRA_CA_CERTS`. No TLS validation switch was disabled, and the product's HTTPS-only endpoint rule was unchanged.

The imported official MITRE Enterprise ATT&CK bundle completed `21635/21635` processing actions. The Workbench detail UI could not render because the bundle's statement marking definition triggered React error #31 in this deployed frontend. The platform's own `askJobImport` mutation was therefore used with `bypassValidation=true` to start the already validated pending file. The completed import reported six errors. All six had the same actor-safe category: distinct MITRE intrusion-set `revoked-by` relationships were deduplicated by OpenCTI to an identical source and target, and OpenCTI rejected the resulting self-relationship. No other error category was observed. This is six known relationship losses, not a claim of lossless MITRE import.

The following actor-visible objects were then created or verified through supported GraphQL mutations and public reads:

- Case Incident: `d2d9f2a7-abf2-4f70-9c06-dff8cc26d031`, `CTI-RAG local orientation smoke - T1566.001`, marked `TLP:CLEAR`;
- imported ATT&CK object: `fb05b68d-2233-4971-afc0-888fb219cca5`, `Spearphishing Attachment`, with external ID `T1566.001`;
- Task: `4b12a2b8-05b3-4377-916e-db28b9f6a386`, `Review T1566.001 orientation context`, marked `TLP:CLEAR` and associated with the Case.

An exhaustive public read of this small Case returned one Task and one Case object, including the target ATT&CK object. Repeating the bootstrap verification returned the same Case and Task identities and did not create duplicates.

The first live qualification failed closed before Case materialization because OpenCTI `7.260715.0` rejected the selected-schema document: one GraphQL operation may invoke `Query.__type` at most twice, while the offline implementation attempted 28 calls. A new public live-smoke behavior test reproduced that deployed limit and failed before implementation. Qualification now sends the same closed selected-schema probes in deterministic batches of at most two `__type` calls, merges only the expected aliases, validates the same recursive `TypeRef` contract, and includes the changed query family in its digest. The focused live test file then passed 31/31.

The corrected faux-provider smoke passed with:

- OpenCTI version `7.260715.0` and HTTPS target `https://localhost:18443/graphql`;
- initial event sequence `turn_started`, `context_bound`, `model_started`, `model_text_delta`, `turn_completed`;
- reopen event sequence identical to initial;
- exactly one `turn_completed` terminal in each Turn;
- `contextValidation.validated=true` for both actual faux-model inputs;
- equal initial/reopen Orientation semantic digest `sha256:78e1507c32a505f3546c83f2aa3eda391b6485440902b9c8106065e026d49a5f`;
- schema digest `sha256:8caa358f8ff758ce9540a3705bdcac61913a46d0a5798e02bc2a63635e975abc`.

The JSONL Session remains ignored local operational data. No token, HMAC key, CA private key, remote body, or model context was printed or added to documentation.

## Design disposition

- Keep the HTTPS-only product Interface and normal Node certificate validation. Local TLS belongs to the external lab deployment seam, not to `normalizeEndpoint` and not to a test-only insecure transport path.
- Retain bounded selected-schema introspection batching as deployment Adapter implementation. The public Workspace Interface and Orientation contract do not change.
- Treat this run as one diagnostic endpoint/actor/Case/time observation. It does not establish production qualification, native snapshot semantics, hidden-membership stability, controlled authorization/marking transition behavior, or independent Slice 0b acceptance.
- Do not add a domain term or ADR for the Caddy setup. It is a reversible local deployment mechanism, not a stable Agent Investigation Workspace concept or a hard-to-reverse cross-module choice.
