# OpenCTI Live Orientation Smoke

This runbook executes one real OpenCTI Case through the read-only `CaseWorkspaceModule -> CaseWorkspace -> WorkspaceTurn` seam. It uses the Pi faux provider, so it proves live OpenCTI qualification, Orientation mapping, model-context delivery, JSONL Session commit, close, and clean reopen without requiring or charging a model provider.

This is diagnostic deployment evidence for one endpoint, actor, Case, and time. It is not full production qualification, a native OpenCTI snapshot claim, or evidence for every Orientation acceptance case.

## Prerequisites

- Node 24.14 at the repository runtime path below.
- An exact HTTPS OpenCTI GraphQL POST endpoint ending in `/graphql`.
- A token for the investigating user. The user must be able to query `me`, `about`, `settings`, schema introspection, the selected Case, top-level Tasks, and Case objects.
- One actor-visible `Case-Incident`, `Case-Rfi`, or `Case-Rft` internal ID.
- Normal Node TLS verification. For a private CA, configure Node trust, for example with `NODE_EXTRA_CA_CERTS`; do not disable certificate validation.

The smoke owns fixed GraphQL documents. It derives the actor from `me.id`, checks recursive return/input `TypeRef` compatibility for the selected deployed schema surface, and proves that each fixed `StixObject`/`StixRelationship` inline fragment has at least one runtime possible type in common with the returned union. Selected-schema introspection is issued in deterministic operations containing at most two `__type` calls because the observed OpenCTI `7.260715.0` target enforces that per-operation bound; the expected aliases are then closed-merged and validated as one schema proof. It then reads the Case root at the start and end of each observation, exhausts Task and object pages, and performs two complete observations for both the initial open and the JSONL reopen. Qualification itself performs only target and schema reads; it does not fetch a Case body as a validation probe.

## Required target bundle

Set exactly these three required inputs in the process environment. Do not put the token on the command line or in a checked-in file.

```powershell
$env:OPENCTI_GRAPHQL_URL = 'https://opencti.example/graphql'
$env:OPENCTI_TOKEN = '<secret token from a secure source>'
$env:OPENCTI_CASE_ID = '<actor-visible Case internal ID>'
```

Optional controls:

- `CTI_RAG_SESSION_PATH`: persistent JSONL Session path. Without it, the smoke creates a new temporary path.
- `CTI_RAG_CREDENTIAL_SLOT`: stable non-secret name for the token source; default `OPENCTI_TOKEN`. The Workspace credential binding is derived from normalized endpoint, `me.id`, and this slot, never from token bytes. Use another slot name when the credential's authority scope changes.
- `CTI_RAG_SESSION_RECEIPT_KEY`: stable base64url HMAC key of at least 32 decoded bytes. It is required when reusing an existing `CTI_RAG_SESSION_PATH` across processes. Keep it secret. A new temporary Session receives an ephemeral 32-byte key that remains stable for both opens in the same smoke process.
- `CTI_RAG_REQUEST_TIMEOUT_MS`: per-request timeout; default `15000`.
- `CTI_RAG_PAGE_SIZE`: GraphQL page size; default `100`.
- `CTI_RAG_MAX_PAGES`: maximum pages per selected collection; default `100`.
- `CTI_RAG_MAX_RESPONSE_BYTES`: maximum bytes per GraphQL response; default `5000000`.

The JSONL Session contains investigation prompts and model prose. Treat it as sensitive local data even though it is not Case authority.

## Run

From `D:\proj\pi-main`:

```powershell
$node24 = 'C:\Users\zihan\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin'
$npmCli = 'C:\Users\zihan\AppData\Roaming\JetBrains\IntelliJIdea2024.2\node\versions\20.16.0\node_modules\npm\bin\npm-cli.js'
$env:PATH = "$node24;$env:PATH"

& "$node24\node.exe" $npmCli `
  --workspace @earendil-works/pi-cti-rag-agent-workspace `
  run smoke:opencti
```

The command prints one JSON result. Success returns process status zero and includes safe identifiers, event types, qualification digests, mechanical model-context proofs, and the resolved `sessionPath`. Both `initial.terminalEvent` and `reopen.terminalEvent` must be `turn_completed`, and both `contextValidation.validated` values must be `true`. Treat `sessionPath` as sensitive operational metadata; when the default temporary path is used, retain or remove that file deliberately. A failure result also includes the resolved path whenever a Session file may already exist, so operators can retain or remove partial audit history. Failure otherwise returns only a closed actor-safe code and message; it does not print the token, remote GraphQL body, partial Case items, or model context. `SIGINT` and `SIGTERM` both abort the bounded run and close an open Workspace.

For an explicitly opt-in Vitest smoke with the same three target inputs:

```powershell
$env:CTI_RAG_RUN_LIVE_OPENCTI = '1'
& "$node24\node.exe" `
  '.\node_modules\vitest\dist\cli.js' `
  --run `
  'packages/cti-rag-agent-workspace/test/opencti-live.smoke.test.ts'
```

Without `CTI_RAG_RUN_LIVE_OPENCTI=1`, that test is skipped and performs no network request.

### Local CTI-RAG lab target

The isolated lab at `D:\proj\opencti-cti-rag-lab` keeps OpenCTI's own loopback HTTP listener and exposes a separate verified TLS endpoint at `https://localhost:18443/graphql`. Start the pinned `caddy` service with the approved lab services, export only its public root certificate as described in the lab README, and set this before launching Node:

```powershell
$env:NODE_EXTRA_CA_CERTS = 'D:\proj\opencti-cti-rag-lab\tls-ca\opencti-local-root.crt'
$env:OPENCTI_GRAPHQL_URL = 'https://localhost:18443/graphql'
$env:OPENCTI_CASE_ID = 'd2d9f2a7-abf2-4f70-9c06-dff8cc26d031'
```

Load `OPENCTI_TOKEN` privately from the lab's protected `.env`; never print or copy it into a command transcript. The pinned diagnostic Case is `CTI-RAG local orientation smoke - T1566.001`, with one linked Task and the imported ATT&CK `T1566.001` object. This local fixture is deployment evidence, not a production seed or Case authority.

## Evidence boundary

A successful run proves that, for the observed target and actor:

- bearer authentication resolved to the reported `me.id`;
- target/version/schema/query-recipe preflight passed;
- every selected field, argument, input field, nullability/list wrapper, interface/union kind, required enum value, and inline-fragment runtime overlap matched the fixed recipe;
- both selected collections completed under equal start/end actor and Case authorization fingerprints;
- initial open and JSONL reopen each performed two fresh observations;
- each actual faux-model input contained exactly one schema-valid Orientation envelope whose block and Orientation digests were recomputed successfully;
- each faux-model Turn emitted exactly one completed terminal event;
- the Session receipt authenticator accepted the close-to-reopen history.

It does not prove that stock OpenCTI exposes a monotonic authorization revision, that hidden membership did not change and revert between observations, that every marking or Authorized Members transition behaves correctly, or that another deployment/version is compatible. GraphQL provides no validation-only endpoint here: the preflight proves the fixed documents' selected schema types statically, while the first Case execution occurs only inside `open` and still fails closed. `qualifiedAt` is observation metadata and is deliberately excluded from `qualificationId`. Those claims and deployment races require controlled fixtures. The smoke also does not exercise a real model provider, I&E Retrieval, Working Set, Case writes, strict R1, or cross-process Session concurrency.

The first local run on 2026-07-20 passed against OpenCTI `7.260715.0` through normal Node TLS verification. Initial and reopen each emitted one `turn_completed`, each actual faux-model context validated mechanically, and public OpenCTI reads proved the Case's Task and object-membership collections non-empty. Exact evidence and the known MITRE import losses are recorded in [the real-Case smoke research note](../research/opencti-real-case-live-orientation-smoke-2026-07-20.md). This observation does not change the independent-acceptance status of Orientation Slice 0b.

## Failure guidance

- `authorization_or_visibility_changed`: confirm the token user, Case access, markings, and organization/Authorized Members scope. Do not retry with a more privileged token merely to hide the mismatch.
- `case_root_not_found_or_not_visible`: the contract intentionally does not distinguish deletion from lost visibility.
- `schema_or_mapping_mismatch`: verify the exact `/graphql` endpoint and deployed OpenCTI schema/version. The fixed query recipe may require a qualified Adapter update.
- `cursor_continuity_lost` or `observation_drift`: retry only after the Case is stable; no partial Orientation was published.
- `transport_timeout`: adjust the bounded timeout only after checking endpoint health and page size.
- `recovery_provenance_untrusted`: use the same receipt key for the existing Session, or start a new Session path. Never bypass receipt verification.
