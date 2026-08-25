# `workspace-report-evidence-packet/v1` Contract

Status: **Design candidate; Design Gate FAIL. No implementation is authorized.**

Research basis:
[Task Result, Evidence Assembly and Report Packet Research](../research/task-result-evidence-assembly-report-packet-research-2026-07-22.md).

## 1. Product purpose

The Report Evidence Packet is the third handoff:

```text
committed Task Result
  + committed Claim-Evidence Subgraph
  + current owner revalidation
  + one report profile
  -> one bounded Report Evidence Packet
  -> one no-tool report Composer attempt
```

It answers:

> What exact result/evidence projection may this report-writing attempt see and
> express?

It is not a Task Result, evidence graph, prompt transcript, report, publication
decision, Case record or reusable Memory object.

This contract freezes ownership, lifecycle and the closed semantic carrier.

## 2. Seam and reuse

Report packet construction is one private Workspace projection seam inside
report-composition orchestration. It is not a Report Packet Module.

The seam has one logical operation:

> Project one current Task Result and Claim-Evidence Subgraph into one bounded,
> disclosure-qualified packet for one exact report profile and consumer.

It reuses:

- the committed Task Result rather than interpreting `agent_end.messages`;
- the committed Claim-Evidence Subgraph rather than querying graph/vector
  stores;
- I&E `retrieve(...)` exact-revalidation profile for current material status;
- Case Management's current revision/reference projection;
- Pi Session control batches for one non-content packet receipt;
- Pi's existing bounded one-shot Provider Dispatch frontend;
- Pi-owned Provider preparation, exact token count, model/auth binding, budget,
  A4 receipt, permit and Adapter start; and
- the later Publication contract for public output.

It adds no Harness, Session, Tool, search, retrieval Agent, provider client,
auth flow or report-specific dispatch transaction.

## 3. Input authority

One packet attempt binds:

- Original User Task and admitted task identity;
- Workspace, task, Session/branch and Run generation;
- exact committed Task Result and Run settlement;
- final trusted Save Point present/absent state;
- exact committed Claim-Evidence Subgraph and assembly receipt;
- Case reference/revision basis when present;
- Access Principal and Use Purpose;
- `contextConsumer = report_composer`;
- one report profile/version;
- Working Set selection/generation;
- exact I&E Resource/Span/lineage/retrieval/index/status observations;
- exact alias/catalog and projection-policy versions; and
- one logical Composer model profile and report budget request.

The packet constructor does not accept raw model-selected resources, OpenCTI
IDs, graph queries, vector queries, credentials, Provider options or arbitrary
prompt instructions.

## 4. Packet contents

The closed carrier preserves these groups:

### 4.1 Task/result projection

- exact user objective safe projection;
- aggregate task disposition;
- every per-goal achieved/incomplete/interrupted state;
- classified Task Result statements;
- completed and incomplete work;
- conflicts, gaps, uncertainty, coverage and next-step proposals; and
- Save Point/resume status appropriate to the report profile.

The packet cannot relabel task analysis as a source assertion, an unresolved question
as a finding, or partial completion as aggregate success.

### 4.2 Claim/evidence projection

For each reportable Task Result statement:

- stable packet-local claim alias;
- semantic statement class;
- eligible supporting, contradicting, qualifying and unresolved candidate
  relationships;
- exact actor-disclosable source aliases;
- exact bounded Source Span/excerpt or structured source assertion;
- Resource Version/Source Capture/derivation/lineage bindings;
- retrieval/graph/index observation refs;
- independence/shared-lineage/unknown-dependency status;
- contradictions and material omissions; and
- coverage statement or explicit absence of proven coverage.

Aliases are created by trusted Workspace projection. The Composer may cite only
those aliases and cannot supply an owner ID or invent another alias.

### 4.3 Report profile

The packet includes one trusted closed report profile defining:

- report kind and audience;
- required sections;
- allowed optional sections;
- tone/length/language;
- required uncertainty and contradiction treatment;
- citation placement rules;
- whether next steps and interruption/resume guidance are required;
- impact/review tier; and
- byte/token/cost/time bounds.

The model cannot change the profile or request a broader packet.

### 4.4 Closed report-profile catalog

V1 has three formal packet profiles:

| Profile | Admitted Task Result | Required sections | Minimum / maximum output tokens |
| --- | --- | --- | ---: |
| `investigation_complete/v1` | `completed` | summary, task outcome, completed work, findings, contradictions and limits, sources, unresolved work, next steps | 1,024 / 4,096 |
| `investigation_limited/v1` | `insufficient_evidence`, `budget_exhausted`, `blocked` | summary, task outcome, completed work, bounded findings, contradictions and limits, sources, unresolved work, next steps | 768 / 3,072 |
| `interruption_recovery/v1` | `failed`, `cancelled`, `discarded` with trusted Save Point statements | interruption status, completed work, uncompleted work, sources, blocker, recovery basis, next step | 512 / 2,048 |

Clarification, unsupported/policy, Quick Response and an interruption with no
trusted Save Point do not create this packet. Their route-specific report input
is owned separately and cannot fabricate a Task Result/subgraph.

```ts
interface ReportEvidenceProfileV1 {
	protocol: "workspace-report-evidence-profile/v1";
	profileRef:
		| "investigation_complete/v1"
		| "investigation_limited/v1"
		| "interruption_recovery/v1";
	profileVersion: string;
	languageTag: string;
	audience: "requesting_principal";
	tone: "neutral_analytical";
	orderedRequiredSections: readonly ReportSectionKindV1[];
	orderedOptionalSections: readonly ReportSectionKindV1[];
	citationStyle: "inline_packet_source_alias";
	contradictionPolicy: "required";
	uncertaintyPolicy: "required";
	nextStepPolicy: "required";
	maxStatementProjections: number;
	maxSourceAliases: number;
	maxExcerptBytes: number;
	maxPacketBytes: number;
	minimumOutputTokens: number;
	maximumOutputTokens: number;
	composerLogicalProfileRef: string;
	composerLogicalProfileDigest: string;
	profileDigest: string;
}

type ReportSectionKindV1 =
	| "summary"
	| "task_outcome"
	| "interruption_status"
	| "completed_work"
	| "uncompleted_work"
	| "findings"
	| "bounded_findings"
	| "contradictions_and_limits"
	| "sources"
	| "unresolved_work"
	| "blocker"
	| "recovery_basis"
	| "next_steps";
```

The profile catalog is trusted configuration. `languageTag` is a validated
1–35 ASCII BCP 47 tag selected from the user/requesting-product language, not
model output. Required-section order is exactly the table order. Optional
sections may not duplicate or reorder required sections.

### 4.5 Closed packet carrier

```ts
interface ReportEvidencePacketV1 {
	protocol: "workspace-report-evidence-packet/v1";
	packetRef: string;
	basis: ReportEvidencePacketBasisV1;
	profile: ReportEvidenceProfileV1;
	task: ReportPacketTaskProjectionV1;
	orderedStatements: readonly ReportPacketStatementProjectionV1[];
	orderedSources: readonly ReportPacketSourceProjectionV1[];
	orderedExcerpts: readonly ReportPacketExcerptV1[];
	orderedCoverageAndLimits: readonly ReportPacketCoverageOrLimitV1[];
	orderedOmissions: readonly ReportPacketOmissionV1[];
	packetDigest: string;
}

interface ReportEvidencePacketBasisV1 {
	composerAttemptRef: string;
	workspaceRef: string;
	taskRef: string;
	caseRef: string;
	caseRevision: string;
	sessionRef: string;
	branchRef: string;
	runGenerationId: string;
	taskResultRef: string;
	taskResultDigest: string;
	runSettlementRef: string;
	runSettlementDigest: string;
	claimEvidenceSubgraphRef: string;
	claimEvidenceSubgraphDigest: string;
	assemblyReceiptSignedPayloadDigest: string;
	accessPrincipalBindingDigest: string;
	usePurpose: "case_investigation";
	contextConsumer: "report_composer";
	workingSetVersion: string;
	workingSetSelectionDigest: string;
	revalidationReceiptSignedPayloadDigest: string;
	qualifiedViewSemanticDigest: string;
	aliasPolicyDigest: string;
	disclosurePolicyDigest: string;
}

interface ReportPacketTaskProjectionV1 {
	originalUserTaskDigest: string;
	taskObjective: string;
	aggregateDisposition:
		| "completed"
		| "insufficient_evidence"
		| "budget_exhausted"
		| "blocked"
		| "failed"
		| "cancelled"
		| "discarded";
	orderedGoals: readonly {
		goalRef: string;
		state: "achieved" | "bounded_incomplete" | "blocked" | "interrupted";
		orderedCompletedWork: readonly string[];
		orderedIncompleteWork: readonly string[];
	}[];
	savePoint:
		| { kind: "present"; savePointRef: string; savePointDigest: string }
		| { kind: "absent"; reason: "no_committed_task_save_point" };
	projectionDigest: string;
}
```

### 4.6 Statement, source and excerpt projections

```ts
interface ReportPacketStatementProjectionV1 {
	statementAlias: string;
	statementRef: string;
	statementDigest: string;
	goalRef: string;
	class:
		| "source_assertion"
		| "task_analysis"
		| "unresolved_question"
		| "status_or_coverage";
	text: string;
	reportRequirement: "required" | "optional";
	orderedCandidateRelations: readonly ReportPacketCandidateRelationV1[];
	projectionDigest: string;
}

interface ReportPacketCandidateRelationV1 {
	role:
		| "candidate_support"
		| "candidate_contradiction"
		| "candidate_qualification"
		| "unresolved_relevance";
	sourceAlias: string;
	assertionRef: string | null;
	orderedExcerptRefs: readonly string[];
	lineageGroupRef: string;
	semanticAuditRequired: true;
	relationDigest: string;
}

interface ReportPacketSourceProjectionV1 {
	sourceAlias: string;
	materialRef: string;
	resourceVersionRef: string;
	sourceCaptureId: string;
	displayTitle: string;
	sourceType: string;
	versionLabel: string | null;
	publishedAt: string | null;
	actorSafeLocator: string | null;
	sourceChannelDigest: string;
	lineageGroupRef: string;
	orderedIndependentFromAliases: readonly string[];
	orderedUnknownDependencyAliases: readonly string[];
	projectionDigest: string;
}

type ReportPacketCanonicalJsonValueV1 =
	| null
	| boolean
	| number
	| string
	| readonly ReportPacketCanonicalJsonValueV1[]
	| { readonly [key: string]: ReportPacketCanonicalJsonValueV1 };

type ReportPacketExcerptV1 =
	| {
			kind: "bounded_text";
			excerptRef: string;
			sourceAlias: string;
			sourceSpanRef: string;
			text: string;
			textDigest: string;
			excerptDigest: string;
	  }
	| {
			kind: "structured_json";
			excerptRef: string;
			sourceAlias: string;
			sourceSpanRef: string;
			value: ReportPacketCanonicalJsonValueV1;
			valueDigest: string;
			excerptDigest: string;
	  };
```

Statement aliases are `CL1` through `CL64` in Task Result statement order.
Source aliases are `SRC1` through `SRC32` in first-use order while walking
statements and their candidate edges. Excerpt aliases are `EX1` through `EX256`
in source-alias then Source Span order. Aliases are packet-local and never
accepted from the model or source.

An excerpt is byte-for-byte the currently qualified I&E span content. Workspace
may apply an explicitly profiled deterministic redaction before aliasing only
when the redacted bytes, original span digest, redaction profile and redacted
digest are all bound by a future profile. No such redaction profile exists in
v1, so a span is either included exactly or omitted with a closed reason.

### 4.7 Coverage, limits and omissions

```ts
interface ReportPacketCoverageOrLimitV1 {
	recordRef: string;
	kind:
		| "retrieval_coverage"
		| "reporting_prevalence"
		| "shared_lineage"
		| "unknown_source_dependency"
		| "material_contradiction"
		| "unresolved_statement"
		| "budget_or_scope_limit"
		| "recovery_limit";
	orderedStatementAliases: readonly string[];
	summary: string;
	ownerEvidenceRef: string;
	ownerEvidenceDigest: string;
	recordDigest: string;
}

interface ReportPacketOmissionV1 {
	omissionRef: string;
	kind:
		| "optional_statement"
		| "optional_source_detail"
		| "same_lineage_render_duplicate"
		| "profile_excluded_next_step";
	ownerRef: string;
	ownerDigest: string;
	profileRuleRef: string;
	omissionDigest: string;
}
```

An omission can affect optional detail only. Required statements, material
contradictions, unknown dependencies, coverage limits, source aliases needed by
a required candidate relation and exact citation spans cannot be omitted.

### 4.8 Bounds, canonicalization and durable receipt

| Item | v1 hard maximum |
| --- | ---: |
| statement projections | 64 |
| source aliases | 32 |
| candidate relations | 256 |
| excerpts | 256 |
| UTF-8/JCS bytes per excerpt | 8 KiB |
| excerpt content total | 256 KiB |
| coverage/limit records | 128 |
| omission records | 128 |
| task/result human-readable text | 128 KiB |
| complete canonical packet | 512 KiB |

All refs are 1–512 UTF-8 bytes without C0/C1 controls. Display members are
individually at most 512 UTF-8 bytes. Every digest is exactly 64 lowercase
hexadecimal SHA-256. At-limit succeeds; required one-over rejects the packet.
Optional one-over may omit only under an exact omission rule.

Record and packet digests are SHA-256 over exact UTF-8 RFC 8785 JCS bytes with
only the record's own digest member omitted. Arrays use the alias/order rules
above; duplicate refs, aliases or non-canonical order reject.

The durable non-content receipt is:

```ts
interface ReportEvidencePacketReceiptV1 {
	protocol: "workspace-report-evidence-packet-receipt/v1";
	packetRef: string;
	packetDigest: string;
	composerAttemptRef: string;
	basisDigest: string;
	profileDigest: string;
	orderedStatementBindings: readonly {
		alias: string;
		statementRef: string;
		statementDigest: string;
	}[];
	orderedSourceBindings: readonly {
		alias: string;
		materialRef: string;
		projectionDigest: string;
	}[];
	orderedExcerptDigests: readonly string[];
	orderedCoverageAndLimitDigests: readonly string[];
	orderedOmissionDigests: readonly string[];
	createdAt: string;
	authenticity: {
		algorithm: "HMAC-SHA-256";
		keyId: string;
		signedPayloadDigest: string;
		macBase64Url: string;
	};
}
```

The receipt HMAC covers exact UTF-8 JCS bytes of the complete receipt with
`authenticity` omitted. It contains no task text, statement text, excerpt,
source title or complete packet bytes.

## 5. Excluded content

The packet contains no:

- credential, auth source or secret;
- unrestricted Session history or hidden reasoning;
- uncommitted Agent/Tool output;
- raw embedding/vector;
- unrestricted graph neighborhood;
- hidden OpenCTI/Case identifier not approved for the consumer;
- stale, withdrawn, unauthorized or unqualified source material;
- rejected Evidence Assembly node/edge;
- Tool definition or Tool-use permission;
- system instruction supplied by a source;
- Case write capability; or
- report/publication decision.

Source text is data. It cannot supply system instructions or report policy.

## 6. Construction lifecycle

The order is:

1. verify Task Result settlement/commit;
2. verify Claim-Evidence Subgraph assembly/commit;
3. revalidate Case, Access Principal, Use Purpose, Working Set and every exact
   I&E material/lineage/status basis;
4. apply the trusted report profile and deterministic disclosure policy;
5. assign packet-local aliases and project bounded excerpts/facts;
6. include every material contradiction, dependency and coverage limit required
   by the profile;
7. validate canonical ordering, bounds and complete packet digest;
8. commit one non-content packet receipt binding identity, ordered refs/digests,
   aliases, inclusions, omissions, policy/profile and packet digest;
9. construct the provider-neutral no-tool Composer context from the retained
   packet;
10. use the existing Pi bounded one-shot frontend to prepare, exact-count,
    authorize, commit and start one Composer invocation; and
11. bind the Composer candidate and Provider Dispatch evidence to the exact
    packet receipt/digest.

The packet body is ephemeral protected application state. Large source excerpts
are not copied into ordinary Session entries. The durable receipt contains
refs/digests and qualification evidence, not unrestricted evidence bodies or
the complete provider prompt.

If the process loses the resident packet before Composer completion, it does
not reconstruct a Provider request or resume the old stream. A later attempt
must revalidate and create a new packet/attempt identity.

## 7. Budget and completeness

Packet selection is deterministic under one report profile:

- every report-required Task Result statement must be represented;
- every material contradiction, shared/unknown lineage and coverage limit must
  be represented;
- required source aliases/excerpts cannot be silently dropped;
- repeated same-lineage occurrences may be collapsed for rendering only while
  retaining their occurrence/lineage counts and refs;
- optional detail may be omitted only under an explicit profile rule and must
  appear in the receipt's omission record; and
- no content is truncated to force admission.

Workspace does not estimate tokens by characters. Pi's prepared exact counter
is authoritative. If the complete required packet and minimum report output do
not fit the selected model/profile budget, the attempt fails before Adapter
start. V1 does not silently split one report across independent Composer calls.

## 8. Invalidation

The packet is single-consumer and single-attempt. Any drift before Provider
start or before later report validation invalidates it:

- Task Result, settlement or Save Point;
- Claim-Evidence Subgraph or assembly receipt;
- Case Revision/basis;
- Access Principal or Use Purpose;
- report profile/consumer;
- Working Set generation;
- Resource/Span/source status/use qualification;
- lineage, retrieval/index or graph observation;
- alias/projection/disclosure policy;
- Composer logical profile; or
- packet/Provider Dispatch identity.

An invalid packet cannot be patched, rebound to a newer basis or used for a
different report profile. Reprojection creates a new packet identity after
current revalidation.

## 9. Composer restrictions

The report Composer:

- has no Tools;
- receives only the packet plus trusted report instructions;
- cannot query I&E, OpenCTI, Case, graph, vector or Memory;
- cannot add facts, evidence, aliases or source versions;
- cannot change task disposition, statement class, contradiction or coverage;
- cannot publish or update a Case; and
- returns one private structured report candidate bound to the packet.

Composer output remains non-authoritative and private until deterministic
validation, independent Evidence Audit and Publication succeed.

### 9.1 Existing Pi one-shot mapping

```ts
interface ReportComposerInvocationBasisV1 {
	protocol: "workspace-report-composer-invocation-basis/v1";
	composerAttemptRef: string;
	packetRef: string;
	packetDigest: string;
	packetReceiptSignedPayloadDigest: string;
	reportProfileRef: string;
	reportProfileDigest: string;
	composerLogicalProfileRef: string;
	composerLogicalProfileDigest: string;
	systemInstructionDigest: string;
	messageProjectionDigest: string;
	toolSchemaDigest: string;
	invocationBasisDigest: string;
}
```

The Workspace application Adapter maps one resident packet to:

- one trusted system instruction selected only by the report profile;
- one provider-neutral user-role data message containing the exact canonical
  packet projection and an instruction that source text is untrusted data;
- an empty Tool array whose canonical digest is bound above;
- the profile-selected logical model reference and output-token bounds; and
- `exact_required` preparation through the existing Pi bounded one-shot
  frontend.

The Adapter supplies no credential, provider header, prepared Model, secret,
character token estimate or direct Adapter call. Pi owns `prepareSimple`,
auth-resolved model sealing, exact input/minimum-output counting, budget
reservation, A4 commit, permit consumption and the single Provider Adapter
start.

The prepared invocation must return actual sealed model/count/logical/receipt
evidence matching `composerAttemptRef`, packet receipt/digest, report profile,
empty Tool digest and the exact message projection. Any mismatch starts zero
Adapters. The resident packet is single-use for that attempt and is discarded
after a terminal candidate or failed preparation; it is never reconstructed
from the non-content receipt.

## 10. Failure closure

| Failure | Required closure |
| --- | --- |
| Task Result or subgraph not committed/exact | no packet |
| owner basis drift or revalidation failure | reject packet; no Composer start |
| required contradiction/coverage/source omitted | reject packet |
| alias collision or unresolved source alias | reject packet |
| required content exceeds byte/token budget | fail before Adapter start |
| packet receipt commit conflict/unknown | append nothing or exact lookup only; no start without exact receipt |
| Pi prepared Model/count/budget differs | deny before Adapter start |
| process loses resident packet/prepared value | no reconstruction, resume or resend |
| Composer requests Tool/retrieval or invents alias | candidate failure; no publication |

No failure falls back to full Session history, a smaller similar resource,
character token estimates, unqualified source text or another Provider
lifecycle.

## 11. Public acceptance candidates

1. One current Task Result/subgraph/profile produces one packet receipt and one
   bounded no-tool Composer attempt through Pi's existing one-shot frontend.
2. Complete-investigation, limited-investigation and trusted-interruption
   profiles receive different bounded projections without changing source
   authority.
3. Every Task Result goal/state and material contradiction appears when required
   by the profile.
4. Same-lineage duplicates may render compactly but retain exact dependency
   evidence; unknown dependency remains unknown.
5. Withdrawn, stale, unauthorized or version-drifted material prevents
   Composer start.
6. A vector/graph candidate without exact admitted Source Span/relationship
   basis never enters the packet.
7. Packet aliases are trusted and closed; invented/colliding/cross-packet aliases
   fail.
8. Source text cannot inject system instructions, Tools or report policy.
9. At-limit exact token count plus minimum output starts one Adapter;
   over-limit starts zero.
10. Character length never authorizes the packet.
11. Packet receipt conflict/unknown acknowledgement uses exact lookup and never
    starts twice.
12. Lost resident packet/prepared value produces no resume/reconstruction.
13. Composer receives zero credentials, hidden IDs, unrestricted history,
    embeddings or raw graph neighborhood.
14. Packet construction performs zero search, zero Tool calls and no second
    Harness/Session/Provider transaction.
15. A report candidate can be created while Case Revision remains unchanged and
    no Case Evidence Reference is added.
16. `CL1..CL64`, `SRC1..SRC32` and `EX1..EX256` aliases follow exact owner order;
    duplicate, skipped, reordered or cross-packet aliases reject.
17. Statement/source/relation/excerpt/coverage/omission and packet digest fixture
    vectors recompute independently from exact UTF-8 JCS bytes.
18. The durable receipt binds every alias and included/omitted digest but
    contains no task text, statement, excerpt, source title or packet body.
19. Every count/byte/output-token bound passes at limit and rejects one-over
    without required-content truncation or Adapter start.
20. The Workspace mapping supplies one trusted system message, one exact packet
    data message, zero Tools and one `exact_required` Pi one-shot attempt; any
    packet/profile/message/tool/model/count mismatch starts zero Adapters.

The matrix remains candidate material until the blockers below close.

## 12. Frozen architecture decisions

- Report Evidence Packet is a Workspace projection seam, not a Module.
- It consumes only committed Task Result and Claim-Evidence Subgraph.
- It performs current owner revalidation but no search or investigation.
- It is one report-profile/consumer/attempt-specific protected packet.
- Bodies remain ephemeral; Session retains one non-content binding receipt.
- Composer uses Pi's existing bounded one-shot Provider Dispatch frontend.
- Exact prepared token counting is authoritative; character estimates are
  forbidden.
- Composer has no Tools and cannot repair/retrieve evidence.
- Any drift creates a new packet; old packet mutation/rebinding is forbidden.

## 13. Design Gate

- **Verdict:** FAIL
- **Owner:** Agent Investigation Workspace report projection; I&E/Case/Pi retain
  their existing authorities
- **Interface:** one private projection from exact Task Result/subgraph/profile
  to one packet decision and bounded one-shot Composer capability
- **Input authority:** exact committed upstream products plus current
  Case/access/use/Working Set/I&E/report-profile bases
- **Output/evidence:** one ephemeral protected packet, non-content receipt and
  exact Pi Provider Dispatch evidence
- **Failure closure:** any missing/drift/over-budget basis prevents Adapter
  start; no reconstruction or fallback
- **Secret isolation:** packet/receipt/Composer exclude credentials,
  unrestricted history, embeddings, hidden graph and unapproved IDs
- **Provider lifecycle count:** exactly one existing bounded one-shot attempt
  when admitted; no Harness or second transaction
- **Workspace exposure:** safe packet/composition status only
- **Backward compatibility:** `SettledInvestigationEvidencePacket` is not an
  alias; `ModelResponseCandidateV1` cannot substitute
- **Public acceptance seam:** product task/report flow through actual packet
  receipt, Pi one-shot Adapter entry/no-entry and later report candidate
- **Remaining blockers:**
  1. **Owner: Task Result + Evidence Assembly. Expected:** exact committed
     upstream products with accepted bindings and invalidation. **Actual:** both
     contracts remain Design Gate FAIL. **Minimal fix:** close them first; do
     not create packet fixtures that bypass owner evidence.
