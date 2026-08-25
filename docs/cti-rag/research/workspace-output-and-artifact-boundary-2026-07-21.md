# Workspace Output and Durable Artifact Boundary

Status: primary-source research and non-normative design input.

Research date: 2026-07-21.

## Question and verdict

Should Agent Investigation Workspace distinguish a model-produced response, a
Workspace-validated user output, and an optional persistent, versioned,
non-authoritative Workspace Artifact?

**Yes.** The distinction solves a real product problem: a Session answer is useful
for immediate interaction, but selected investigation work must survive Session
compaction and branching, remain reviewable against exact source and context
versions, and evolve without silently rewriting earlier analysis. It must also
remain clearly below Case authority.

The term needs one important correction: an Agent Run is not evidence that its CTI
claims are true. Run receipts are **audit/provenance evidence that a particular
process occurred**. Source material and its provenance support CTI claims; a
Workspace Artifact is a derived investigation work product; Case Management alone
can accept a conclusion as Case state.

Do not create an Artifact for every response. Immediate answers may end as a
validated user-visible Workspace Output. Materialize a durable Artifact only when
the product needs later review, reuse, revision, comparison, or Case proposal.

## Repository facts

- The glossary already defines a [Workspace Artifact](../agent-workspace/CONTEXT.md#workspace-artifact)
  as persistent, versioned, and non-authoritative, distinct from Case fact,
  Intelligence Resource, and Session message. It separately defines an
  [Assessment Draft](../agent-workspace/CONTEXT.md#assessment-draft) as structured
  candidate judgment and an [Assessment Evidence Unit](../agent-workspace/CONTEXT.md#assessment-evidence-unit)
  as a versioned grouping that retains underlying Intelligence Resource references.
- The architecture already requires complete candidates, explicit dependency
  edges, end-of-operation fencing, and atomic publication; partial or stale
  candidates publish nothing. It also requires immutable Artifact versions to
  survive Session compaction, retain derivation references without copying Case or
  corpus state, and remain non-authoritative until Case Management acceptance.
  [Workspace architecture](../agent-workspace/context-projection-design.md)
- The implementation package has no Artifact, Assessment, Output Candidate, or
  publication Module. Current delivery tracking explicitly says the general CTI
  investigation Agent and Assessment behavior are not implemented and defers full
  Assessment behavior. [Workspace progress](../agent-workspace/PROGRESS.md)

Therefore the concept is designed at glossary/target-architecture level, but it
does not yet have an accepted current-cycle contract or product implementation.

## Primary-source findings

### 1. Provenance supports a durable derived work product, not a truth claim

W3C PROV defines provenance as a record of the entities, activities, and agents
involved in producing or influencing a thing. It models derivation between used
and generated entities and supports revisions, invalidation, attribution, and
responsibility. Provenance helps a consumer make a trust judgment; it does not
itself declare the derived content correct. [W3C PROV-DM](https://www.w3.org/TR/prov-dm/Overview.html),
[W3C PROV Primer](https://www.w3.org/TR/prov-primer/)

**Inference:** represent each Artifact version as a generated entity, the Agent
Run/publication activity as its generation activity, exact task/context/resource
versions as used entities, and the actor/model/runtime as attributed or associated
agents. A new version derives from or revises an earlier version. Supersession or
withdrawal changes eligibility; it must not rewrite the old entity.

### 2. Version identity and withdrawal are mature CTI concepts

STIX 2.1 identifies versions with the same object `id` plus a distinct `modified`
timestamp, permits only the object creator to issue a new version, requires a
particular version's serialized properties to remain stable, and defines permanent
revocation separately from ordinary versioning. [OASIS STIX 2.1, versioning](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_Toc16070555)

**Inference:** a Workspace Artifact needs stable logical identity plus immutable
version identity, an explicit predecessor/supersession relationship, and a
separate eligibility state. Do not mutate old content in place. Workspace
`challenged`, `superseded`, and `withdrawn` need not copy STIX revocation semantics;
in particular, a challenge may preserve historical use without claiming permanent
revocation.

### 3. A Workspace draft should not be silently written as OpenCTI knowledge

STIX defines Note for additional analysis, Opinion for an assessment of another
object's correctness, and Report for publishing a comprehensive CTI story.
[OASIS STIX Note](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_Toc16070618),
[OASIS STIX Report](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_Toc16070636).
OpenCTI treats Report, Note, Opinion, Case, and Task as knowledge containers, and
its Case workflow uses Notes and Opinions to record analysis and work performed.
[OpenCTI containers](https://docs.opencti.io/latest/usage/containers/),
[OpenCTI case management](https://docs.opencti.io/latest/usage/case-management/)

**Inference:** OpenCTI already provides suitable *eventual publication targets*,
but writing a model draft there immediately would cross from private task-scoped
work into shared CTI/Case state. A Workspace Artifact should remain local. Any
conversion to an OpenCTI Note, Opinion, Report, or Case update is a separate
Case-Management-owned proposal and acceptance operation.

### 4. Generated output requires validation, traceability, and review

NIST recommends comparing GAI outputs against predefined organizational rules,
reviewing and testing generated content, analyzing outputs for misinformation,
tracking and validating lineage/authenticity, and using additional human review,
tracking, and documentation where appropriate. It also notes that provenance
metadata can record creator, creation time, modifications, and sources.
[NIST AI 600-1, pp. 43-55](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)

**Inference:** deterministic validation should prove protocol shape, authorized
dependency identity, completion, current eligibility, citation existence, and
atomic persistence. It cannot prove that an analytic claim is true or that a
citation semantically entails every sentence. Analytic correctness still needs
domain review, structured comparison, or later Case acceptance.

### 5. Artifact retention inherits source handling constraints

STIX data markings express restrictions and guidance for use, sharing, and
storage, and can apply to an entire object or selected fields. Marking changes are
versioned rather than silently changing the meaning of an existing reference.
[OASIS STIX data markings](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#_Toc16070891)

**Inference:** an Artifact cannot receive a broader audience or longer retention
horizon than its admitted inputs. Its body, citations, rendered excerpts, and
derived claims require an owner-computed handling envelope. Authorization loss may
make even a historical body unavailable to model/user views while retaining a
minimal protected audit record. Never retain hidden chain of thought.

## Recommended concept boundaries

| Concept | What it proves or contains | Authority |
|---|---|---|
| Source evidence | Exact captured source spans, resource versions, provenance, and use status supporting a claim | I&E/source owner |
| Agent Run audit evidence | That a bound invocation/run/tool sequence reached a recorded state | Pi/runtime; not CTI truth |
| Model Response Candidate | Complete model-produced content before Workspace publication checks | Model proposal only |
| Published Workspace Output | Candidate accepted for delivery under the current run and dependency fence | Workspace-valid delivery; still non-authoritative |
| Workspace Artifact Version | Optional durable structured work product with immutable content, provenance, status, and supersession | Workspace; non-authoritative |
| Case fact or accepted judgment | State accepted under Case policy and revision authority | Case Management |

`Output` is too broad to own a schema by itself. A future contract should use
specific names such as `ModelResponseCandidate`, `WorkspacePublicationDecision`,
`PublishedWorkspaceOutput`, and `WorkspaceArtifactVersion`.

## Publication gate

The user's proposed checks are directionally correct, with two refinements.

First, "no working token" should be defined as **settled execution**, not a token
count: the provider stream has one accepted terminal, no tool call/result or
effect needed by the candidate is pending or acknowledgement-unknown, the active
run generation is current, and the final owning save point is committed.

Second, Orientation and Projection are layered rather than alternatives. The gate
always checks the Orientation safety basis used by the output and, when present,
the bound Projection overlay and revision semantics.

A minimum publication decision should verify:

1. current Workspace/Turn/Run/generation and exactly one terminal settlement;
2. complete candidate only, with no partial stream, pending tool, unresolved
   operation, cancellation, timeout, or unknown provider acknowledgement;
3. immutable Original User Task and admitted Task Context identities;
4. exact Session branch/head, compaction generation, System Instruction, model,
   prompt, active Tool schemas, and capability snapshot used;
5. current Orientation safety basis and, if present, current compatible Projection
   overlay;
6. exact Working Set version and every cited I&E Resource Capsule/Retrieval Receipt,
   span, use disposition, marking, and disclosure decision;
7. closed output schema, content digest, citation/reference integrity, policy and
   secret/unsafe-content checks;
8. one atomic publication decision: publish the whole eligible output and receipt,
   or publish none.

Passing this gate means "eligible Workspace output under this bound basis," not
"verified true." A statement that is not mechanically supported must remain an
explicit hypothesis, uncertainty, or candidate judgment.

## Minimum Artifact record and lifecycle

The first contract should be smaller than the full Assessment architecture. One
immutable Artifact version needs at least:

- stable `artifactId`, immutable `versionId`, type/schema version, content digest,
  creation time, predecessor and optional supersession relation;
- Workspace/Case/task/actor/purpose binding and visibility/retention/marking
  envelope;
- originating Published Workspace Output, Turn, Run, provider-dispatch receipt,
  and final Session save-point references;
- exact Original User Task, Admitted Task Context, Orientation receipt and optional
  Projection overlay, Session/context generations, Working Set and selected
  Artifact versions;
- exact cited Resource Capsules, Retrieval Receipts, spans, tool results, and their
  use/disclosure decisions;
- validator/policy versions, publication decision, explicit non-authoritative
  label, uncertainty/limitations, and current eligibility status.

Keep immutable content separate from mutable eligibility metadata. Suggested
eligibility states are `current`, `challenged`, `superseded`, and `withdrawn`, each
with a reason and dependency change. A new analysis produces a new version or a
sibling Artifact; it never edits an old basis. Artifact creation and its
derivation/publication receipt must commit atomically.

## Failure and recovery requirements

- Partial stream, provider error, cancellation, timeout, malformed output, or
  missing citation: no Published Workspace Output and no Artifact.
- Dependency or authorization drift before the publication commit: reject current
  publication; retain only policy-permitted historical/audit evidence.
- Crash after model completion but before commit: lookup by stable output/run
  identity; never infer success from text or resend automatically.
- Duplicate publication/materialization request: return the already committed
  same-digest result; same identity with a different digest is an integrity error.
- Concurrent new Artifact versions: compare the expected current version; preserve
  both immutable candidates or reject the stale replace claim, never last-writer
  overwrite.
- Later source withdrawal, marking change, or Projection rebase: challenge or hide
  only dependent Artifact versions; unrelated versions remain usable.
- Retention expiry: remove protected bodies according to policy while preserving
  only the minimal permitted tombstone/provenance record.

## Alternatives and cost

| Alternative | Benefit | Why it is insufficient or when to use it |
|---|---|---|
| Session message only | Simplest and already native to Pi | Good for ordinary answers; weak identity across compaction/branches, no structured version/supersession or Case proposal basis |
| Store every final response as an Artifact | Uniform | Creates retention, review, storage, and stale-dependency noise; most chat answers do not merit durable work-product identity |
| Immediately create OpenCTI Note/Opinion/Report | Reuses the CTI platform | Crosses authority and sharing boundaries; requires explicit Case/write admission and makes drafts look accepted |
| Store an unversioned response blob | Cheap persistence | Cannot safely revise, compare, invalidate, or reproduce the basis |
| Optional versioned Workspace Artifact | Clear authority boundary and reproducible evolution | Adds schema, storage, lifecycle, dependency-index, retention, and review cost; justified only for reusable investigation work |

## Acceptance evidence required

Before implementation, the owning current-cycle contract should include public-
seam tests for:

- valid current response publishes once while remaining explicitly
  non-authoritative;
- partial, failed, cancelled, stale, unauthorized, malformed, uncited, or
  acknowledgement-unknown candidates publish neither output nor Artifact;
- Orientation remains the safety baseline and a Projection overlay cannot erase
  its evidence binding;
- citation references are exact and actor-visible; fabricated or changed
  references fail closed;
- response publication without Artifact materialization is valid;
- explicit Artifact materialization commits immutable content, version identity,
  receipt, and dependency edges atomically;
- duplicate same-digest materialization is idempotent; identity/digest mismatch
  fails; concurrent replacement does not overwrite;
- compaction, branching, reopen, supersession, source withdrawal, and authorization
  loss preserve the correct history while excluding ineligible bodies;
- no Artifact or audit record contains credentials, hidden source metadata,
  partial model text, or chain of thought;
- a Case update occurs only through a separately accepted Case Management
  proposal, never through Artifact persistence.

## Design disposition

Retain `Workspace Artifact`; it solves a real need and is correctly located in
Agent Workspace. Tighten the next design as follows:

1. Define the immediate model result as a candidate and the delivered response as
   a separate Workspace publication decision.
2. Treat run records as process/provenance evidence only, never evidence of CTI
   truth.
3. Make Artifact materialization optional and explicit for durable investigation
   work, not an automatic consequence of every successful Turn.
4. Use immutable Artifact versions, exact derivation bindings, atomic publication,
   separate eligibility/supersession state, and inherited handling/retention.
5. Keep Orientation as the safety basis and Projection as an optional authority
   overlay bound to it; do not model them as alternatives.
6. Require a separate Case Management proposal before any Artifact becomes a Case
   Note, Report, Opinion, finding, or accepted judgment.
7. Start with one small generic Artifact/version/publication contract. Keep full
   Assessment Draft, Evidence Unit, and Provisional Assessment behavior deferred
   until the general CTI investigation Agent and Working Set vertical provide
   executable evidence.

This note authorizes no implementation or normative contract change.
