# Access Principal and Use Purpose Terminology Revision

Status: **Accepted terminology decision; contract and implementation migration
pending.**

Owning decision:
[ADR 0019](../adr/0019-name-access-principal-and-use-purpose-explicitly.md).

## 1. Normative language

```typescript
interface AccessPrincipalBinding {
	principalRef: string;
	credentialRef: string;
}

type UsePurposeV1 = "case_investigation";
```

`AccessPrincipalBinding` identifies the trusted principal exercising access. A
principal may be a user, group or future service identity. It is not a CTI
Threat Actor, Agent, Session, thread or model identity.

`usePurpose` records why that principal is authorized to use an exact data
version. It governs execution-time use authorization, purpose-flow isolation,
historical-material revalidation and audit. Trusted Workspace workflow supplies
it. It is not a user choice, model field, prompt instruction or output-quality
test.

The first version has one value, `"case_investigation"`. This is a future
isolation and audit binding point, not a current multi-choice product feature.
Adding another value requires an owner authorization decision and explicit
flow/acceptance rules; callers cannot invent strings.

## 2. Distinct concepts

| Meaning | Canonical name | Examples |
| --- | --- | --- |
| who is exercising access | `accessPrincipal`, `AccessPrincipalBinding`, `principalRef` | analyst user, authorized group, service identity |
| what the data is authorized to be used for | `usePurpose` | `case_investigation` |
| why the Case exists | `investigationObjective` or `caseMandate` | Case-level mandate owned by Case Management |
| what the current task must accomplish | `taskObjective` | investigate, validate, corroborate one task goal |
| which model-context path consumes entries | `contextConsumer` | provider, compaction, branch summary |
| what a Tool operation will do | `operationIntent` | exact admitted read/write/effect |

None of these names is interchangeable.

## 3. Normative renames

Only fields whose meaning is access identity or data-use authorization migrate:

| Existing access meaning | Required name |
| --- | --- |
| `TrustedActorBinding` | `AccessPrincipalBinding` |
| `actor: TrustedActorBinding` | `accessPrincipal: AccessPrincipalBinding` |
| `actorRef` | `principalRef` |
| access `purpose` | `usePurpose` |
| `actorCasePurposeDigest` | `principalCaseUsePurposeDigest` |
| `actorPurposeBindingDigest` | `principalUsePurposeBindingDigest` |
| protocol fragments containing `actor-purpose` | equivalent `principal-use-purpose` protocol in a versioned revision |
| prose `actor/purpose authorization` | `principal/use-purpose authorization` |

The following do not migrate through this rule:

- Threat Actor, intrusion-set attribution, Campaign actor or other CTI domain
  entities;
- Agent, Harness, Session, thread or lifecycle actors;
- audit event initiator/approver roles where a more specific existing name is
  already correct;
- grammatical uses of “actor” unrelated to access identity.

## 4. Purpose disambiguation

Existing `purpose` occurrences require semantic classification:

- access authorization becomes `usePurpose`;
- Pi `provider | compaction | branch_summary` becomes `contextConsumer`;
- Run goal/capability `investigate | validate | corroborate` becomes
  `taskObjective`;
- `task_context_planning | response | product_tool | final_response` requires a
  separate invocation/consumer review and must not be renamed to
  `usePurpose`;
- Case mandate remains `investigationObjective` or `caseMandate`;
- Tool effect semantics remain `operationIntent`.

The repository currently contains both access-style
`"case_investigation"` and Run-style `"cti_investigation"`. They are not
automatically aliases. Access authorization standardizes on
`usePurpose: "case_investigation"`; Run Control must remove or reclassify its
`"cti_investigation"` field during migration.

## 5. Digest and protocol migration

This is a semantic protocol revision, not a TypeScript-only rename.

- Digests must be recomputed over the renamed closed records.
- Protocol strings that name the old semantics receive a new version.
- Old and new digest bases must never verify interchangeably.
- Existing committed receipts remain interpretable under their original
  protocol; they are not rewritten.
- A Workspace reopened across the migration must either use an explicitly
  accepted legacy reader or require a new qualified binding. It cannot silently
  reinterpret old bytes as the new schema.
- Credentials and secrets remain excluded from public evidence and digests
  exactly as before.

## 6. Visibility and authority

`accessPrincipal` and `usePurpose` are trusted hidden bindings. The model may
receive an actor-safe statement that material is authorized for the current
investigation, but it does not receive mutable identity/purpose fields and
cannot request another value.

`usePurpose` is checked:

1. before an owner read or operation;
2. before qualified material enters model context;
3. when historical material is recalled;
4. before Provider or Tool dispatch when the bound data is consumed; and
5. when replaying or reopening retained evidence.

It does not validate whether model or Tool output satisfies `taskObjective`.

## 7. Migration ownership and ordering

The migration is one cross-contract vertical and must not be performed as
unreviewed bulk replacement.

1. Revise normative Workspace access binding and Orientation public Interface.
2. Revise dependent Task Understanding, Memory, Context and Run bindings.
3. Revise I&E access/revalidation contracts at their owned seam.
4. Revise publication and Case-write authorization bindings.
5. Freeze one compatibility decision for existing persisted receipts.
6. Only then issue an implementation task covering product types, Adapters and
   public tests together.

Research notes may retain historical terminology when quoting or describing old
protocols, but must carry a migration note if used as current design evidence.

## 8. Readiness

- Terminology decision: **PASS**
- Cross-contract migration design: **FAIL**
- Current Workspace Orientation naming vertical: **Design PASS**
- Whole-repository implementation readiness: **FAIL**

### 8.1 Authorized current implementation vertical

The first implementation vertical is limited to the currently implemented
`packages/cti-rag-agent-workspace` Orientation/Workspace public seam:

```typescript
CaseWorkspaceModule.open({
	caseRef,
	accessPrincipal: {
		principalRef,
		credentialRef,
	},
	sessionRef,
});
```

It revises the complete materialized Orientation protocol together:

```typescript
protocol: "opencti-case-orientation/v2";
schemaVersion: "opencti-case-orientation-v2";
principalRef: string;
usePurpose: "case_investigation";
```

The v2 semantic digest contains `principalRef` and `usePurpose`. The old
`actorRef`, `TrustedActorBinding`, input `actor`, and
`usePurpose: "investigation_orientation"` are absent from the v2 public,
materialized, invalidation, live-qualification and test surfaces.

No backward-compatibility alias or dual reader is required. Existing v1
materialized evidence is not rewritten or silently interpreted as v2. If it is
encountered during reopen/qualification, it is ineligible and follows the
existing safe recovery-provenance failure path with zero Provider start.

This vertical does not rename:

- OpenCTI/GraphQL schema fields owned by the external source;
- CTI Threat Actor concepts;
- Pi Agent/Harness/Session/runtime actor concepts;
- audit initiator/approver concepts;
- I&E, Case Management, publication or deferred contracts.

### 8.2 Frozen public acceptance matrix

1. `CaseWorkspaceModule.open` accepts only `accessPrincipal:
   AccessPrincipalBinding`; `TrustedActorBinding` and input `actor` are absent
   from supported exports and public types.
2. The first public Workspace prompt succeeds through the v2 Orientation and
   emits `context_bound` with protocol `opencti-case-orientation/v2`.
3. Materialized v2 Orientation contains `principalRef` and
   `usePurpose: "case_investigation"` and contains no `actorRef`.
4. The v2 schema rejects missing/empty `principalRef`, old `actorRef`, any
   unknown field and any other Use Purpose.
5. Live qualification derives `principalRef` from the authenticated OpenCTI
   principal and rejects caller/expected-principal mismatch without leaking
   identity.
6. Invalidation is keyed by exact `caseRef + principalRef`; another principal
   cannot invalidate or continue this Workspace.
7. Semantic/evidence digests change when `principalRef` or `usePurpose` changes;
   `credentialRef` and secret material remain excluded.
8. Old v1 materialized evidence cannot be admitted as v2 or start a Provider.
9. Orientation lifecycle, reopen, Task Understanding, adapter conformance and
   ordinary fake-live behavior remain green through their public seams.
10. Repository search confirms no access-domain `TrustedActorBinding`,
    `actorRef`, input `actor`, or `investigation_orientation` remains in the
    allowed current Workspace source, schema and tests. Unrelated external/CTI
    meanings are not changed.
11. Root check passes under Node v24.14.0.

### 8.3 Current vertical gate

- **Verdict:** PASS
- **Owner:** Agent Investigation Workspace
- **Interface:** `CaseWorkspaceModule.open -> CaseWorkspace.prompt ->
  WorkspaceTurn`
- **Input authority:** trusted `AccessPrincipalBinding`
- **Output/evidence:** v2 Orientation, events, Session evidence and public result
- **Failure closure:** invalid/mismatched/legacy bindings start no Provider
- **Secret isolation:** `credentialRef` remains non-secret; credentials remain
  outside materialized evidence/digests
- **Provider lifecycle count:** unchanged, at most one
- **Workspace exposure:** principal and Use Purpose remain hidden bindings
- **Backward compatibility:** none; v1 evidence is ineligible, never reinterpreted
- **Public acceptance seam:** public Workspace open/prompt plus supported exports
- **Remaining blockers:** none for this bounded implementation vertical

Remaining blockers:

1. exhaustive semantic occurrence classification is not complete;
2. persisted receipt compatibility and reopen behavior are not frozen;
3. owner-by-owner public acceptance matrix is not frozen.

No development task is authorized by this terminology decision alone.
