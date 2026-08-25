# Local OpenCTI Lab Deployment for CTI-RAG

Status: primary-source deployment research with an offline-prepared lab; runtime activation is blocked by the current Docker memory ceiling. Host storage is sufficient only for an initial bounded lab/import trial and requires active free-space monitoring.

Research date: 2026-07-20.

## Decision

Prepare an isolated local OpenCTI lab at `D:\proj\opencti-cti-rag-lab` from the official OpenCTI Docker repository, pinned to repository commit `d3aa93833fe16f06bfd272e76b2876f0a6a81e90`. Deploy only Redis, Elasticsearch, MinIO, RabbitMQ, OpenCTI, one Worker, and ImportFileStix. Do not start default-data or external-import Connectors and do not ingest data during platform bring-up.

OpenCTI Platform, Worker, and ImportFileStix are fixed at the synchronized official release `7.260715.0`, published on 2026-07-15. The lab overlay also pins every started container image to an observed manifest digest, including dependencies whose official Docker composition uses a moving tag. [OpenCTI release](https://github.com/OpenCTI-Platform/opencti/releases/tag/7.260715.0), [Connectors release](https://github.com/OpenCTI-Platform/connectors/releases/tag/7.260715.0), [official Docker source](https://github.com/OpenCTI-Platform/docker/tree/d3aa93833fe16f06bfd272e76b2876f0a6a81e90)

This release is the latest complete tagged release preceding the Workspace live-Adapter source baseline inspected on 2026-07-20. That makes it the nearest traceable release candidate, not proof of schema compatibility. The live Adapter's target/version/schema introspection remains the deciding compatibility check after startup.

## Official deployment facts

- OpenCTI's official installation guide supports Docker Compose deployment from the OpenCTI Docker repository, requires a valid UUIDv4 administrator token, requires persistent Elasticsearch/MinIO/Redis/RabbitMQ volumes, and requires `vm.max_map_count` to be set to `1048575`. [Official installation guide](https://docs.opencti.io/latest/deployment/installation/)
- The official architecture and infrastructure table assigns minimum RAM of at least 8 GB to Elasticsearch/OpenSearch, 1 GB to Redis, 512 MB to RabbitMQ, 128 MB to MinIO, 8 GB to OpenCTI Core, 128 MB to a Worker, and 128 MB to a Connector. [Official deployment overview](https://docs.opencti.io/latest/deployment/overview/)
- ImportFileStix `7.260715.0` is a Filigran-verified internal import Connector for STIX 2.1 JSON and STIX 1.2 XML. It supports validation, manual or automatic import, and contextual import into Cases and other containers. Its required runtime Interface is the local OpenCTI URL/token, one UUIDv4 Connector ID, name, scope, and import controls. [Official ImportFileStix contract](https://github.com/OpenCTI-Platform/connectors/blob/7.260715.0/internal-import-file/import-file-stix/README.md)
- OpenCTI's file-import guide places imported knowledge in an analyst workbench for review and validation rather than treating upload alone as accepted main knowledge. [Official file-import guide](https://docs.opencti.io/latest/usage/import-files/)
- OpenCTI's supported dependency configuration includes explicit Elasticsearch username/password and Redis username/password fields. The lab therefore authenticates both internal dependencies rather than inheriting the official development composition's unauthenticated defaults. Neither dependency has a host-published port. [Official dependency configuration](https://docs.opencti.io/latest/deployment/configuration/#dependencies)

## Resource gate

The observed Docker engine and `docker-desktop` WSL VM both report `16,678,240,256` bytes, about `15.53 GiB`, of memory and `4 GiB` of swap at `/dev/sdc`. `%USERPROFILE%\.wslconfig` does not exist, and Docker's local settings store records `D:\WSL_Storage\Docker_Engine\DockerDesktopWSL` as the engine location but contains no explicit memory value. The effective limit is therefore observable at the WSL VM/Docker engine, but no existing user configuration file was found that can be safely edited in place.

The official per-process minima above total about `17.9 GB` before container-runtime overhead and before any import workload. The current 15.53 GiB ceiling is therefore below the documented floor. Starting under this ceiling would risk an OOM/restart loop, so no container, network, or volume has been created.

Raising Docker/WSL to **24 GB** is a local conservative recommendation derived from the approximately 17.9 GB official component sum plus startup/indexing/runtime margin while retaining about 8 GB for the 32 GB Windows host. It is not an OpenCTI-published minimum or guarantee. `memory=24GB` is a maximum for the shared WSL 2 utility VM, not an eagerly reserved 24 GB allocation: WSL 2 and Docker Desktop allocate memory dynamically according to demand. A **22 GB** cap is the host-friendlier fallback, leaving about 10 GB for Windows, but it gives the lab roughly 2 GB less margin during Elasticsearch startup and MITRE indexing. Prefer 24 GB for the bounded import trial; use 22 GB only if Windows shows sustained memory pressure, and treat an OOM/restart at 22 GB as evidence to stop rather than reduce component safety limits. [Microsoft WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config), [Docker Desktop WSL 2 backend](https://docs.docker.com/desktop/features/wsl/)

The change is not scoped to Docker. Microsoft defines `%USERPROFILE%\.wslconfig` as global configuration for all installed WSL 2 distributions, which means the memory and swap ceiling also applies to Ubuntu and any other running WSL 2 distribution. Docker recommends configuring memory and swap for its WSL 2 backend through this shared WSL 2 utility VM. Applying the file requires stopping all WSL workloads with `wsl --shutdown`; Docker Desktop must then be restarted. This is an operator-controlled, disruptive action and was not performed during preparation. [Microsoft WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config), [Docker WSL resource guidance](https://docs.docker.com/desktop/features/wsl/best-practices/)

Minimal reversible adjustment:

1. Exit Docker Desktop.
2. Ensure the parent directory `D:\WSL_Storage\WSL_Swap` exists, then create `%USERPROFILE%\.wslconfig` with only:

   ```ini
   [wsl2]
   memory=24GB
   swap=4GB
   swapFile=D:\\WSL_Storage\\WSL_Swap\\wsl-swap.vhdx
   ```

   Microsoft requires escaped backslashes for Windows path values. The explicit `swapFile` avoids the default `%Temp%\swap.vhdx`; on this host `%TEMP%` and `%TMP%` are on C:. The 4 GB size preserves the currently observed swap capacity and uses swap only as an emergency disk-backed buffer, not as planned OpenCTI working memory. [Microsoft WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)

3. Run `wsl --shutdown`, then start Docker Desktop. This stops Ubuntu and every other running WSL 2 distribution as well as Docker's WSL VM; save their work first.
4. Verify `docker info --format 'MemoryBytes={{.MemTotal}}'` and `wsl -d docker-desktop -- sh -lc "free -h; swapon --show; cat /proc/sys/vm/max_map_count"` before starting the lab. Confirm that swap is 4 GB and that the host-side VHD exists under `D:\WSL_Storage\WSL_Swap`.
5. To revert, exit Docker Desktop, remove only the three added keys (or the file if it contains nothing else), run `wsl --shutdown`, and restart Docker Desktop. Do not delete the D: swap VHD while WSL is running.

The current `vm.max_map_count` is `1048576`, which satisfies the official `1048575` setting. It does not need modification.

### Host storage disposition

The read-only host check reports approximately **7.09 GiB free on C:** and **57.53 GiB free on D:**. The Windows page file is already `D:\pagefile.sys` at about 4.25 GiB, Docker's WSL engine VHD is under `D:\WSL_Storage\Docker_Engine`, and the proposed 4 GB WSL swap VHD is also placed on D:. Consequently, C: is **not an immediate mechanical blocker** to starting the bounded OpenCTI lab or importing a small, source-pinned MITRE STIX bundle. It is nevertheless already in a local warning state because `%TEMP%` and `%TMP%` remain on C:; installers, downloads, decompression, Docker Desktop updates, crash dumps, and other host processes can still consume transient C: space.

D: is **adequate but tight for the initial lab and one bounded MITRE import**, not for unrestricted ATT&CK synchronization, long retention, production use, or a claim of durable capacity. The official OpenCTI component table assigns about 50 GB of aggregate minimum disk across Elasticsearch, Redis, MinIO, and RabbitMQ. The current 57.53 GiB free is measured after pulling the seven images and after allocating the Windows page file, but before creating the proposed 4 GB WSL swap file and before Elasticsearch/volume growth. After that swap is created, the nominal free-space margin over the component sum is only a few GiB. This is sufficient to attempt startup and a deliberately small import while measuring actual usage; it is not sufficient to activate broad feeds or proceed without a stop rule. [OpenCTI deployment overview](https://docs.opencti.io/latest/deployment/overview/), [Docker Desktop settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/)

The following thresholds are local operational policy, not Microsoft, Docker, or OpenCTI published limits:

- C: warning below 10 GiB (already true); do not begin a new image update or import below 5 GiB. Prefer freeing at least another 5-10 GiB before the trial, but do not move `%TEMP%`/`%TMP%` as part of this lab task.
- D: warning below 30 GiB; do not begin another import below 20 GiB; stop the current import and preserve evidence if free space approaches 15 GiB or falls rapidly.
- Record C:/D: free space plus `docker system df` before startup, after services stabilize, immediately before import, and after indexing stabilizes. These checks are observational only; do not use automatic prune or delete unrelated Docker data.

## Prepared deployment

The target directory was verified absent before cloning. It now contains:

- the official Docker repository at exact commit `d3aa93833fe16f06bfd272e76b2876f0a6a81e90`;
- `docker-compose.cti-rag-lab.yml`, a narrow override that pins the seven approved images, binds only OpenCTI to `127.0.0.1:18080`, removes MinIO host exposure, reduces the official three-Worker development replica count to one, and disables XTM One integration;
- `.env`, containing system-cryptographic random OpenCTI, MinIO, RabbitMQ, Redis, and Elasticsearch credentials, ignored by Git, and protected by an ACL for the current Windows identity plus SYSTEM; no secret value was printed;
- `Initialize-LabConfig.ps1`, which refuses to overwrite an existing `.env`;
- an updated deployment-directory `README.md` with exact start, stop, status, log, secret, volume, and later import instructions;
- ignored `lab-evidence/` and `import-staging/` paths for later non-secret evidence and explicitly authorized bundles.

The Compose merge passes `docker compose ... config -q`. Port `127.0.0.1:18080` is free. `vm.max_map_count` is sufficient. All seven pinned images have been pulled successfully; their summed logical image size is about 1.35 GiB and D: has about 57.53 GiB free after the pull. C: has about 7.09 GiB free and is below the local warning threshold. No lab container, network, or named volume exists yet.

Expected persistent names after first start are:

- `cti-rag-opencti-lab_esdata`
- `cti-rag-opencti-lab_s3data`
- `cti-rag-opencti-lab_redisdata`
- `cti-rag-opencti-lab_amqpdata`
- network `cti-rag-opencti-lab_default`

The existing unrelated Docker containers, images, volumes, and networks were neither modified nor removed.

## Start and verification after the resource gate

From `D:\proj\opencti-cti-rag-lab`:

```powershell
$compose = @('-f', 'docker-compose.yml', '-f', 'docker-compose.cti-rag-lab.yml', '--project-name', 'cti-rag-opencti-lab')
docker compose @compose up -d opencti worker connector-import-file-stix
docker compose @compose ps
```

The explicit service list allows Compose to bring only the selected services and their dependencies; it does not activate XTM One, XTM Composer, default data, MITRE, CISA, OTX, document analysis, or export Connectors.

Runtime acceptance remains pending and must establish all of the following without logging a token or response body:

1. Redis, Elasticsearch, MinIO, RabbitMQ, OpenCTI, Worker, and ImportFileStix are running; services with health checks are healthy.
2. `http://127.0.0.1:18080` and POST `http://127.0.0.1:18080/graphql` are reachable only on loopback.
3. The local administrator token executes actor-safe `me`, `about.version`, `settings.id`, and bounded introspection queries; raw response bodies remain local and are reduced to pass/fail plus safe version/type evidence.
4. OpenCTI reports ImportFileStix registered/ready with STIX JSON/XML scope, validation enabled, and automatic import disabled.
5. Runtime memory and disk usage are recorded after idle stabilization.

Stop without deleting data:

```powershell
docker compose @compose stop
```

Normal operation must not use `down -v`, `docker system prune`, or delete non-project resources.

## Import preparation boundary

ImportFileStix is present to support a later small, source-pinned MITRE STIX bundle. No bundle has been downloaded or imported. The later import step must record its MITRE source commit and file digest, upload through the supported OpenCTI import flow, explicitly trigger the Connector because automatic import is disabled, review the workbench, and validate only the intended objects.

This lab task does not create a Case, access user `raw` data, run the CTI-RAG live smoke, activate full MITRE/CISA/OTX synchronization, or claim production qualification.

## Design disposition

Keep the lab as an external operational Module behind the existing live GraphQL Adapter seam. Its operator Interface is the small Compose command set, loopback URL, protected secret file, and persistent project identity. Dependency topology, image provenance, storage, and Connector setup stay inside that Module. No Pi product Interface or implementation changes are justified by deployment mechanics.

Activation remains blocked until the Docker memory gate is changed and reverified. After that one external prerequisite is satisfied, continue in this same lab directory with startup, health/API/Connector acceptance, and resource measurement before any data import.
