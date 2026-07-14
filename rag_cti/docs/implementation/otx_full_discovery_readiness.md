# OTX 577-query discovery-only readiness audit

Date: 2026-07-11  
Scope: offline, read-only audit of TRAIL pages 3-5, `docs/reference/sample_code.py`, the canonical collector, checkpoint/completeness audit, and the frozen Route A run. No OTX call, test run, full Pulse raw scan, training, GPU work, or Git operation was performed.

## Current decision

**CODE READY; LIVE DISCOVERY BLOCKED BY THE OTX SEARCH SERVICE.**

The four repository-side gates found by the initial audit have now been fixed
and covered by the 75-test OTX regression suite. A live authenticated
`/api/v1/search/pulses` preflight nevertheless returned HTTP 504 from the OTX
gateway after about 60 seconds, while other authenticated OTX endpoints
returned HTTP 200. Do not launch the 577-query run until the one-query,
one-page authenticated search gate succeeds. This is an external availability
gate, not a reason to change the discovery model or substitute subscribed
Pulses for global actor/alias search.

## Initial audit decision (superseded by implemented fixes)

**NOT READY for an unattended 577-query production discovery run.**

The intended collection direction is correct and paper-backed: use known APT names and aliases to search AlienVault OTX Events. The canonical `--phase discovery` path also correctly avoids Pulse detail and indicator endpoints. However, four engineering gates are blocking a defensible full run:

1. a completed cached search page is skipped without replaying its results into the candidate manifest;
2. reaching `--max-search-pages 80` while `next` is still present has no explicit terminal classification;
3. `OTX_API_KEYS` is accepted syntactically but only its first key is ever installed in the HTTP client, so actual rotation is absent;
4. the progress audit treats any historical error row as a current query error, even if a later retry completes the query.

Start only after these gates are fixed and covered by narrow tests. Continuing the existing Route A run is safer than starting a new run only if its run-scoped candidate/discovery artifacts remain authoritative and cached pages are replayed rather than merely skipped.

## Evidence boundary

### Paper-backed statements

TRAIL page 3 describes raw JSON incident reports containing IOCs and the threat actor to whom the report is attributed, followed by IOC analysis/enrichment and graph construction. Page 4, Section IV-A, specifically says TRAIL searches the AlienVault OTX API for Events tagged with APT names and aliases, then obtains Event IDs and associated APTs. It also says the paper discarded multi-alias Events unless all aliases mapped to the same APT. Pages 4-5 describe subsequent IOC analysis, secondary-IOC discovery, and a two-hop enriched graph.

Therefore the paper supports only this discovery backbone:

```text
known APT names/aliases -> OTX Event search -> Event IDs
```

The paper does **not** prescribe this repository's phase flags, RawStore identity, checkpoint format, candidate manifest, retry schedule, page cap, API-key policy, ambiguity-preserving extension, or query-completeness definition. Those are engineering policies.

### Engineering policies in this repository

- All search hits are retained as candidates; multi-actor and ambiguous Events are not filtered during collection.
- Query-to-actor association is collection provenance only. `QueryActor` explicitly says it does not assert that a Pulse is attributed to that actor, and discovery rows repeat: `Collection audit only; not an OTX actor label or graph fact.`
- Candidate rows are keyed by Pulse ID and retain multiple discovery paths.
- Discovery, detail, and indicators are independently resumable phases.
- `since` and `until` may remain null. Pulse `created` and `modified` remain available for later temporal profiling/projection.
- Source attribution must be derived separately from source fields such as OTX `adversary`, never from the search query that happened to retrieve the Pulse.

## Current Route A evidence

Frozen run: `data/raw/otx_collection_runs/routeA_20260704_policy_small_first`.

| Measure | Current evidence |
|---|---:|
| MITRE actor/alias queries | 577 |
| Search-artifact touched queries | 135 |
| Completed queries reported in `RUN_STATUS.md` | 100 |
| Unknown/error queries reported there | 27 |
| Open queries reported there | 8 |
| Untouched queries | 442 |
| Candidate manifest rows | 4,906 unique Pulse IDs |
| Checkpoint discovered Pulse IDs | 4,905 |
| Completed Pulse details | 4,160 |
| Checkpoint completed page keys | 508 |

The older `run_progress_report.json` reports 97 complete, 54 with errors, and 4,724 discovered Pulses; later artifacts and `RUN_STATUS.md` report higher counts. This is a snapshot-timing difference, so readiness decisions must use a newly generated progress audit after collector fixes, not mix these snapshots.

## Preflight gates

| Gate | Required evidence | Current status |
|---|---|---|
| Endpoint isolation | Discovery issues only `GET /api/v1/search/pulses`; zero `/pulses/{id}` and zero `/indicators` calls | **PASS in code** for `--phase discovery` |
| Candidate uniqueness | Exactly one manifest row per Pulse ID | **PASS in implementation and current manifest** |
| Path preservation | Every accepted occurrence `(query, page, rank, search raw ref)` is represented once under that Pulse | **CONDITIONAL FAIL** on cached-page resume; see below |
| Attribution separation | Query actors never become Event attribution | **PASS in the collection contract; must remain an acceptance assertion** |
| Same-run resume | Completed pages can be resumed without network and without losing candidates/paths | **FAIL** |
| New-run behavior | Old global cached pages are either deliberately replayed with new run provenance or deliberately fetched again | **UNSPECIFIED / unsafe to assume reuse** |
| Page-cap terminal state | A query ending at page 80 with `next=true` is classified `truncated_page_cap`, not complete | **FAIL** |
| Retry/429 | Bounded retry with auditable terminal failure | **PARTIAL** |
| Multiple keys | Keys rotate/cool down on 429 | **FAIL** |
| Query completeness | Every one of 577 queries has exactly one defensible terminal state | **FAIL** |
| Stop/resume | SIGINT/termination cannot corrupt checkpoint or silently lose a completed page's discoveries | **PARTIAL** |
| Capacity | Free disk and expected page-call range recorded immediately before launch | **NOT YET RECORDED** |

## Detailed findings

### 1. Discovery-only endpoint gate

`run()` branches early for `detail` and `indicators`. In the main query loop, `phase == "discovery"` continues immediately after writing discovery/candidate artifacts. Thus the intended command can call only `search/pulses`.

Use the explicit phase, not compatibility mode:

```powershell
python scripts/fetch_otx_mitre_actor_raw.py --phase discovery --run-dir <run-dir> --max-search-pages 80
```

`--skip-indicator-pages` is unnecessary in discovery phase and should not be used as the proof of endpoint isolation; `--phase discovery` is the proof.

### 2. Candidate deduplication and path completeness

`candidate_events.jsonl` is loaded into a dictionary keyed by `pulse_id`, then written in sorted Pulse-ID order. `_merge_candidate()` deduplicates a discovery path by `(query_normalized, page, rank, search_raw_ref.source_id)`. This supports one candidate row per Pulse with multiple paths.

The resume path breaks the guarantee. If `query:page` is in `completed_query_pages`, the collector loads the cached payload and immediately `continue`s when it has a next page. It does not re-run `search_results()`, `_merge_candidate()`, or discovery-row emission for that page. Consequences:

- if the candidate manifest and discovery log are intact, same-run resume usually retains earlier paths;
- if either artifact is missing/incomplete while the checkpoint says the page is complete, the cached page is skipped and its candidates cannot be reconstructed by this run;
- the current legacy rebuild uses `discovery_metadata.jsonl`, not raw cached search pages, so it cannot repair a missing discovery row from search raw alone.

**Required gate:** a completed cached page must be replayed idempotently through candidate/path merging, or startup must verify that every cached completed page already has complete run-scoped discovery material before allowing skip.

### 3. Existing cached pages: same run versus new run

Raw search source IDs are stable from normalized query plus page and are global under `data/raw/otx_search`.

- **Same run:** the checkpoint controls reuse. Completed page keys load `store.latest(...)`; however, as above, result replay is absent.
- **New run:** its checkpoint begins empty. Merely finding the same raw page in global RawStore does not cause reuse; the collector fetches and writes a new version. This avoids silently inheriting an old snapshot, but costs API calls and does not define whether the desired dataset is a fresh snapshot or a provenance-preserving replay.

**Policy decision required before launch:** continue Route A as one collection snapshot, or create a fresh run and refetch all search pages. Do not claim that a new run automatically reuses old cached search pages; it does not.

### 4. `max_search_pages=80` risk

At 20 results/page, the cap represents at most 1,600 returned occurrences per query. The loop ends naturally after page 80 even if the response still contains `next`. No `completed`, `truncated`, or failure record is written for this condition. The progress audit will see a touched but incomplete query, but the collector summary does not explain why.

**Required gate:** after the last permitted page, persist a query terminal record such as:

```json
{"status":"truncated_page_cap","last_page":80,"has_next":true}
```

Such a query is not complete. It may be resumed later with a higher explicit cap or classified as a documented bounded-coverage limitation. Raising the cap blindly is not a substitute for terminal-state accounting.

### 5. Errors, 429s, and retries

`_get_json()` performs three attempts. A 429 sleeps 10, 20, then 30 seconds. Other exceptions, including HTTP errors and transport failures, sleep 2, 4, then 6 seconds. The caller records a failure and breaks the current query page loop.

Risks:

- `Retry-After` is ignored;
- all non-429 exceptions share one short policy, including retryable 5xx and non-retryable 4xx;
- there is no jitter;
- a later successful retry appends an `ok` row but old `error` rows remain;
- the progress audit defines `queries_with_errors` as any query with any historical error row, so recovered queries still fail its gate.

**Required gate:** distinguish retryable from permanent HTTP states, honor `Retry-After` when present, persist final attempt classification, and compute current query status from the latest/terminal state rather than historical-error presence.

### 6. API-key rotation

The reference `sample_code.py` has a `KeyPool` design that selects a key per request and cools down a key on 429. The canonical collector does not implement that behavior. `_api_key()` returns `OTX_API_KEY` if present; otherwise it returns only the first non-empty entry from `OTX_API_KEYS`. A single static header is then installed on one `httpx.Client`.

Therefore `OTX_API_KEYS=key1,key2` currently provides **no rotation or throughput increase**. This must be fixed or the run must be explicitly planned as single-key collection. Never describe the present collector as multi-key capable.

### 7. Defensible query-complete definition

A query is complete only when all of the following hold:

1. page 1 was attempted;
2. every page from 1 through terminal page has an `ok` search artifact and raw reference;
3. every accepted result occurrence has been merged into the candidate manifest with its discovery path;
4. the terminal page has `has_next == false` (an empty result page is also terminal only when recorded successfully);
5. no unresolved page error precedes the terminal page;
6. the query did not stop because of `max_search_pages`, `max_pulses`, process interruption, or an unclassified exception.

The full discovery gate passes when all 577 queries are either `complete` or explicitly classified permanent/bounded failures accepted by the dataset manifest. A query match remains discovery provenance regardless of terminal status.

### 8. Capacity estimate

These are planning estimates, not API guarantees:

- Current Route A has 626 search log rows across 135 touched queries, about 4.6 logged pages per touched query.
- Extrapolating that observed average to all 577 queries gives roughly 2,675 page attempts total, or about 2,050 additional attempts beyond the current 626 rows.
- The hard worst case is 577 x 80 = 46,160 search requests.
- The existing global `otx_search` sample contains 567 files totaling about 9.0 MB, averaging about 15.8 KB each. At the observed extrapolation, search raw alone is roughly tens of MB; at the hard cap, roughly 0.7-1.3 GB is a prudent envelope before filesystem/version overhead.
- With only the configured 0.5-second inter-page delay, 2,050 additional pages impose at least about 17 minutes of sleep; 46,160 pages impose at least about 6.4 hours. Network latency, rate limits, retries, and per-query overhead can make wall time several times larger. A practical observed-case budget is hours, while the cap-bound case may run a day or longer on one key.

Before launch, record free space, selected run directory, key count actually usable, and a small dry-run's observed request latency/rate. Search-only disk is not the main risk; silent partial coverage is.

### 9. Safe stop and resume

Checkpoint JSON is written through a temporary file and replace operation, which protects the checkpoint itself from partial writes. Candidate JSONL is rewritten as a whole, while discovery/search/saved logs are append-only. A stop between these writes can leave artifacts at slightly different frontiers; the current 4,906 candidate versus 4,905 checkpoint count demonstrates that such divergence already exists.

Safe operating policy:

1. use a stable, explicitly named run directory;
2. stop with Ctrl+C/SIGINT rather than killing the process where possible;
3. never delete or edit checkpoint, candidate, discovery, search-page, or saved-file artifacts independently;
4. after every stop, run progress-mode audit and compare candidate paths against completed cached pages;
5. resume the same phase and same query list/parameters;
6. do not start detail acquisition until all query terminal states are audited;
7. retain invocation history so changed caps or filters are visible.

The collector currently has no explicit SIGINT transaction boundary across all artifacts, so the replay/idempotence gate is required before unattended operation.

## Required launch sequence after fixes

1. Add cached-page idempotent replay or a strict artifact-consistency verifier.
2. Add `complete`, `error_retryable`, `error_permanent`, `truncated_page_cap`, and `interrupted` query terminal states.
3. Make the progress audit use current terminal state and verify contiguous pages plus candidate-path materialization.
4. Either implement real per-request key rotation/cooldown or document and run single-key.
5. Run narrow collector tests proving discovery calls only `search/pulses`, cached replay preserves all paths, page 80 remains incomplete when `next=true`, and a recovered error can become complete.
6. Record disk/key/latency preflight.
7. Prefer resuming `routeA_20260704_policy_small_first` if preserving its snapshot lineage is the goal; otherwise create a fresh run and explicitly accept refetching all search pages.
8. Run discovery only with `since=null`, `until=null` unless a later research question explicitly requires filtering.
9. Stop and audit periodically; launch detail only after the 577-query terminal-state gate is satisfied.

## Final acceptance checklist

- [ ] Only `/api/v1/search/pulses` was called.
- [ ] Query list hash and count (577) match the frozen manifest.
- [ ] All query pages are contiguous from page 1 to their terminal page.
- [ ] Every complete query ends with `has_next=false`.
- [ ] Every page-cap exit is classified incomplete/truncated.
- [ ] Every search result occurrence is present in one Pulse candidate's discovery paths.
- [ ] Candidate Pulse IDs are unique.
- [ ] Historical recovered errors do not remain falsely active.
- [ ] Actual key behavior matches the recorded single-key or rotating-key policy.
- [ ] `since`/`until` and their null/unfiltered meaning are recorded.
- [ ] No candidate is filtered by ambiguity, multi-actor state, title similarity, or source attribution state.
- [ ] No query actor is emitted as Event attribution.
- [ ] Detail and indicator endpoint counts remain zero for this phase.

## 2026-07-11 implementation and live preflight update

The four code-level blockers identified above were implemented and covered by
offline tests:

- completed cached pages now replay candidate/discovery paths idempotently;
- `query_terminal_states.jsonl` records `complete` and
  `truncated_page_cap` states;
- `OTX_API_KEYS` now rotates per request and cools down only the key receiving
  a 429;
- the progress audit resolves current/latest page and terminal state, so a
  recovered historical error no longer remains active.

The combined OTX regression suite passed 75 tests and Ruff passed.

A live one-query/one-page discovery preflight was then attempted with the one
configured OTX key. DNS resolution and TCP port 443 connectivity succeeded. An
unauthenticated request returned HTTP 403 immediately, but an authenticated
OTX search request timed out while reading the response after 15 seconds. The
collector preflight remained inside its request/retry path for more than three
minutes without producing a search page, candidate, or checkpoint and was
terminated deliberately. No Pulse-detail or indicator endpoint was called.

**Operational status:** code readiness gates pass, but live authenticated OTX
connectivity does not. Do not launch the 577-query background run until a
one-page authenticated search succeeds with bounded latency.

### Authenticated search diagnosis

The failure was minimized and tested across clients, queries, and endpoints:

- `requests` and `httpx` both timed out before receiving search response
  headers;
- `APT28` and a random no-match query behaved the same;
- the configured key is valid: `/api/v1/user/me` returned HTTP 200 in about
  0.35 seconds and `/api/v1/pulses/subscribed` returned HTTP 200 in about
  2.7 seconds;
- a dummy key returned HTTP 403 in about 0.3 seconds;
- a single authenticated `/api/v1/search/pulses` request with a 120-second
  client read timeout returned HTTP 504 from the server gateway after about
  60.36 seconds.

This rules out local DNS/TCP, client-library, key validity, query selectivity,
and response-body size as primary causes. The active blocker is the OTX
authenticated pulse-search backend. Subscribed-pulse APIs are not a substitute
for global actor/alias search coverage.

### 2026-07-11 resumed full discovery

The authenticated one-query gate later recovered: `APT28` page 1 returned
HTTP 200 in 19.08 seconds. Before resuming the frozen 577-query run, two
discovery performance defects were removed:

- candidate events are persisted once per changed search page instead of once
  per result, and an unchanged cached-page replay does not rewrite the
  manifest;
- `--phase discovery` no longer scans or JSON-decodes the approximately
  12.9 GB Pulse-detail RawStore to construct indexes used only by later phases.

The frozen input gates passed: MITRE bundle SHA256
`f857d8f78f2f0c0b7db321a711a39fba98546c1e3076a657684850c83d0962fb`,
query-list SHA256
`2140b5d3575d8f355c1c6099833de36071d55af66d2553c0b2a5f8f0d279f477`,
and 577 deduplicated queries. The original
`routeA_20260704_policy_small_first` run was then resumed in discovery-only
mode with null `since`/`until`, a 20-result page size, and an 80-page cap.

After direct measurement showed that OTX returned 100 results in 14.87 seconds
versus 20 results in 16.80 seconds, the resumed run adopted mixed pagination:
queries already touched by the frozen run retain their original limit of 20,
while previously untouched queries use 100. The page limit is now included in
new search RawStore identities, checkpoint keys, search/discovery provenance,
and query terminal rows. The progress audit rejects a query if it observes more
than one explicit page limit; legacy rows without the field remain compatible
with their frozen manifest limit. Existing evidence and completed-query status
are therefore retained without mixing pagination boundaries within a query.

Discovery now supports bounded query-level concurrency through
`--discovery-workers` (default 2). Each worker owns one query and fetches that
query's pages serially with its frozen page limit. Workers perform network
fetches only; the main thread serializes RawStore writes, JSONL provenance,
candidate compaction, checkpoint updates, and terminal-state records. The API
key pool's rotation and 429 cooldown are lock-protected. Setting
`--discovery-workers 1` preserves the serial path, and runs with
`--max-pulses` also fall back to serial execution so concurrent prefetch cannot
violate the cap. A live two-worker canary resumed the frozen run without stderr
or audit corruption.
