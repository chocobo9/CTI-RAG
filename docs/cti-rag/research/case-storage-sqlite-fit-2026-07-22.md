# Case Storage SQLite Fit

Date: 2026-07-22  
Status: Planner research; non-normative

## Question

Does Case Management lack persistence, and is SQLite a suitable first
implementation for the Case data needed by Memory and Context Assembly?

## Repository facts

- Case Management already owns the durable authoritative Case record, Case
  Revision and proposal receipts in domain language.
- No Case Management implementation package or repository exists.
- The frozen strict-write facade uses PostgreSQL as the production reference
  Adapter because one transaction must serialize the Case head, proposal
  ledger, effect and outbox.
- Workspace and Pi Session must not become substitute Case databases.

Therefore the gap is an implementation owner and storage Adapter, not a missing
concept of persistence.

## Primary-source findings

- SQLite supplies ACID transactions and WAL permits concurrent readers with one
  writer. This fits a local single-process or low-write-concurrency Case store,
  but not a horizontally scaled multi-writer authority.
  Sources:
  [SQLite WAL](https://www.sqlite.org/wal.html),
  [SQLite transactions](https://www.sqlite.org/lang_transaction.html).
- Durability depends on journal and synchronous configuration. WAL with
  `synchronous=NORMAL` may lose a recently committed transaction after power
  loss even though transactions remain atomic; an authoritative Case Adapter
  should require a stronger qualified durability configuration.
  Source:
  [SQLite PRAGMA synchronous](https://www.sqlite.org/pragma.html#pragma_synchronous).
- SQLite supports ordinary structured indexes, JSON functions and FTS5. None of
  those requires vector search, and FTS is optional for later human discovery.
  Sources:
  [SQLite JSON](https://www.sqlite.org/json1.html),
  [SQLite FTS5](https://www.sqlite.org/fts5.html).
- Node's built-in `node:sqlite` exists in Node 24, but official documentation
  records release-candidate status only from Node 24.15. The project's accepted
  test runtime is Node 24.14, so adopting `node:sqlite` now requires an explicit
  runtime/dependency qualification rather than assumption.
  Source:
  [Node 24 SQLite API](https://nodejs.org/download/release/latest-v24.x/docs/api/sqlite.html).

## Decision recommendation

Use a storage-agnostic Case Repository seam with:

1. an in-memory Adapter for public acceptance;
2. a SQLite Adapter for local/single-host first deployment;
3. the existing PostgreSQL reference Adapter for later multi-process strict
   write deployment.

SQLite is the primary local Adapter, not the universal production guarantee.

Do not add a vector database to Case Management. Context Assembly needs exact
current state and exact historical revisions. Optional semantic recall belongs
behind owner-qualified recall and may later use a rebuildable index; that index
is never the Case authority.

## Write/read timing

- Write on Case creation/import and accepted Case-owner transitions.
- Write a new immutable revision when an authorized Case mutation commits.
- Do not write when a prompt is assembled, a model reads the Case, a Memory View
  is constructed, or a model merely proposes a memory.
- A settled Memory candidate changes Case only after Case Management accepts it
  through the Case update workflow.
- Context Assembly reads one current or explicitly historical revision and
  records its reference in adoption/input evidence.

## Remaining implementation gates

- choose and qualify the SQLite Node driver for the pinned runtime;
- freeze the first Case State payload/profile needed by the read-only product;
- define file ownership, backup, corruption recovery and migration behavior;
- decide the deployment limit that requires PostgreSQL;
- implement only after a Case Management owning package/route is accepted.
