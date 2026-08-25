# `case-persistence/v1` Contract

Status: **Design candidate; Design Gate FAIL. No implementation is authorized.**

Research basis:
[Case Storage SQLite Fit](../research/case-storage-sqlite-fit-2026-07-22.md).

## 1. Outcome and ownership

Case Management requires a durable Case Repository. It stores authoritative
Case identity, current state, immutable revision history and owner decisions.
It is independent of Pi Session, Workspace Memory, Context Assembly and
Provider execution.

SQLite is the first local Adapter. PostgreSQL remains the later production
Adapter when deployment requires multiple writers, remote availability or the
strict proposal/effect/outbox transaction.

No vector database is part of Case authority.

## 2. Deep Module

Case Management exposes business operations, not SQL:

```text
openCase(caseRef, AccessPrincipalBinding, usePurpose)
readProjection(caseRef, profile, expected/current revision)
submitCaseUpdate(proposal, expectedRevision)
lookupProposal(proposalId)
```

The private Case Repository seam supplies atomic persistence to that Module.
Workspace never receives a database connection, table name, SQL query or raw
Case object graph.

## 3. Required persisted records

### Case head

- stable `caseRef`;
- current opaque `caseRevision`;
- current State digest;
- current lifecycle status;
- created/updated owner evidence.

### Immutable Case revision

- revision identity and previous revision;
- canonical Case State payload/profile version;
- State digest;
- Access Principal and Use Purpose decision references;
- accepted transition/proposal reference;
- commit time and schema version.

### Proposal ledger

- stable proposal identity and request digest;
- expected revision;
- terminal accepted/no-effect/rejected/conflict disposition;
- resulting revision/effect reference where applicable.

### Outbox/reconciliation

- durable work created in the same transaction as an accepted Case effect;
- idempotent dispatch/materialization identity;
- attempt and terminal reconciliation state.

The first read-only implementation may omit proposal/effect/outbox behavior,
but its schema migration plan must reserve their ownership and must not place
them in Workspace Session.

## 4. SQLite Adapter profile

The local Adapter uses one database file owned exclusively by one Case
Management deployment.

Required qualification:

- foreign keys enabled;
- WAL mode only on a supported local filesystem;
- power-safe synchronous policy appropriate for authoritative commits;
- bounded busy timeout;
- write transactions acquire authority before reading the expected head;
- one transaction commits the new revision and head;
- unique proposal/revision identities;
- integrity check, schema migration table and tested backup/restore;
- prepared statements with bound values;
- no dynamic SQL from model or Workspace content.

SQLite's single-writer behavior is an accepted local deployment constraint.
Contention exhaustion returns a closed unavailable/conflict outcome; it is not
reported as authoritative no effect unless the repository proves rollback.

## 5. Context and Memory behavior

Context Assembly never writes Case storage.

Before a Run:

1. Workspace requests one principal/use-purpose-qualified Case view.
2. Case Management reads the current head and exact revision.
3. It returns a bounded projection plus revision/evidence.
4. Memory Coordination may include that projection in a Qualified Memory View.
5. Context Assembly renders the qualified view for Pi.

After a Run:

1. model output remains non-authoritative;
2. Workspace settles and classifies any retention/update candidate;
3. a Case-shaped candidate is routed to Case Management;
4. only Case Management validation/approval may commit a new revision;
5. later context reads the new current revision.

Historical recall reads immutable revisions by exact reference, time/range or
structured status indexes. Semantic/vector search is neither required nor
authorized for v1.

## 6. Adapter independence

Public Case behavior must run unchanged against:

- in-memory acceptance Adapter;
- SQLite local Adapter;
- future PostgreSQL production Adapter.

The Interface and Case Revision semantics cannot expose SQLite row IDs,
transaction IDs, WAL offsets or filesystem paths.

## 7. Candidate acceptance

1. provision/read returns the same Case State and opaque revision through
   in-memory and SQLite Adapters;
2. reopen after process restart returns the committed head;
3. expected-revision conflict commits no partial state;
4. concurrent writers produce at most one accepted next revision;
5. revision and head commit atomically;
6. failed/unknown commit is never reported as authoritative no effect without
   proof;
7. immutable history remains readable and current state is unambiguous;
8. Workspace/Memory/Context reads cause zero Case writes;
9. model output alone causes zero Case writes;
10. accepted owner transition creates exactly one new revision;
11. backup/restore preserves heads, revisions and digests;
12. corruption/schema mismatch fails closed;
13. no Case body, credential or hidden authorization evidence leaks into logs;
14. no vector/embedding index is required for current projection or revision
   reads.

The matrix is not frozen until the first Case State/profile and driver are
selected.

## 8. Design Gate

- **Verdict:** FAIL
- **Owner:** Case Management
- **Interface:** Case business operations over a private repository seam
- **Input authority:** Access Principal, Use Purpose, Case proposal/profile
- **Output/evidence:** Case State/Projection, opaque revision and receipts
- **Failure closure:** candidate defined; exact driver outcomes pending
- **Secret isolation:** required
- **Provider lifecycle count:** not applicable
- **Workspace exposure:** projections/receipts only; never SQL/storage handles
- **Backward compatibility:** not yet applicable; no implementation exists
- **Public acceptance seam:** Case Management business Interface across
  in-memory and SQLite Adapters
- **Remaining blockers:**
  1. no accepted Case Management package/code route;
  2. first Case State/profile payload is not frozen;
  3. SQLite driver/runtime, durability and deployment qualification are not
     selected.
