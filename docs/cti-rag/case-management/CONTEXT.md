# Case Management

Case Management owns the durable business record of an investigation. Its internal Case model remains independent of the Agent framework and of the storage technology used by other contexts.

## Language

**Case**:
A long-lived investigation business instance with a stable identity, investigation purpose, evolving state, history, and continuity across user tasks and Agent Runs.
_Avoid_: Session, conversation, agent thread

**Case State**:
The authoritative current business state of a Case, including human corrections and accepted investigation outcomes.
_Avoid_: Agent memory, transcript

**Case Revision**:
An opaque token issued by one Revision Authority under one revision contract for one Case, used for equality and conditional coordination between a Workspace observation and later changes; the token is meaningful only with that authority/contract/Case tuple and is not synthesized from an OpenCTI timestamp, entity ID, event cursor, or local content hash.
_Avoid_: Session version, prompt version, OpenCTI timestamp, event cursor

**Revision Authority**:
The Case Management owner that issues and compares Case Revisions and serializes every mutation in its declared Case revision domain; mutable semantic state outside that serialization point is not covered by its revision.
_Avoid_: Adapter, database, OpenCTI cursor, Projection digest

**Case Update Proposal**:
A requested, attributable change to a Case that Case Management must validate and accept or reject through its controlled update rules.
_Avoid_: Direct write, agent memory update

**Case Update Proposal Receipt**:
An authoritative record of Case Management's decision for one stable proposal identity, including whether no effect occurred or which Case Revision and effect resulted from acceptance.
_Avoid_: HTTP response, Workspace log, change event

**Protected Receipt Recovery Proof**:
The minimum authority-owned terminal outcome envelope retrievable by a narrow recovery principal after business disclosure is revoked; it can advance durable recovery state for the exact original effect but cannot be shown to the revoked Session or authorize another operation.
_Avoid_: redacted business receipt, user-visible status, retry authorization

**Proposal Ledger Revision**:
An opaque Case Management head for the proposal/receipt ledger of one Case; it advances once for each newly committed terminal proposal identity, including no-effect decisions, without implying that Case semantic state changed.
_Avoid_: Case Revision, receipt sequence, event cursor, OpenCTI revision

**Projection Inclusion Proof**:
An authority-owned proof that the exact effect identified by a terminal receipt is present in one complete current authorized Case Projection whose Case Revision, Proposal Ledger Revision, observation evidence, Resource Index, and Proposal Status all match that receipt; it is separate from proposal acceptance and current permission.
_Avoid_: Receipt, search match, event observation, current authorization
