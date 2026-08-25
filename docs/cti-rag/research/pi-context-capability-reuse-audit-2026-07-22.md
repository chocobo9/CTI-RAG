# Pi Context Capability Reuse Audit

Date: 2026-07-22  
Status: Planner source audit; non-normative

## Question

Can PNW-C reuse Pi's existing Agent Context, Session qualification and Provider
Dispatch, and what CTI-specific middle layer is still missing?

## Existing Pi capability

| Need | Existing Pi owner/seam | Coverage |
| --- | --- | --- |
| final runtime context container | `AgentContext { systemPrompt, messages, tools }` | complete transport shape; must not be duplicated by Workspace |
| persisted conversation and branch history | Pi Session | complete persistence owner |
| compaction-aware history selection | `AgentHarnessContextEntryPolicy` | complete generic selection/revalidation seam for provider, compaction and branch summary |
| transient model-context transformation | Harness `context` event/result | usable for ephemeral Workspace messages; it persists no owner content |
| initial transient message/system adjustment | `before_agent_start` | available, but untrusted CTI data must not be promoted into system instructions |
| active Tool transport | Harness config/turn snapshot | complete generic Tool channel; Workspace still owns capability admission |
| final message/Tool/system canonicalization | Provider Dispatch | complete sole canonical/digest authority |
| exact token count and model/auth-resolved evidence | Provider Dispatch prepared runtime | complete; Workspace must bind to the actual outcome rather than estimate |
| application policy/evidence binding | `ProviderDispatchApplicationAuthority` | generic seam can bind Workspace receipts to actual prepared facts/artifact |
| durable turn/application receipt group | transactional save point/Session control | generic persistence mechanism; Workspace owns receipt meaning |

## What Pi deliberately does not cover

Pi cannot decide:

- which Case, Working State or recalled material is current and authorized;
- whether data is eligible for the Access Principal and Use Purpose;
- whether historical material is current, challenged, withdrawn or deleted;
- how current authority differs from non-authoritative analysis;
- whether optional recall is needed;
- which CTI conflicts or omissions must be disclosed;
- which admitted owner references belong in a Workspace receipt.

These are Workspace/owner semantics, not missing Agent-loop features.

## Duplicate-design findings

Workspace should not introduce:

- a second `AgentContext` type;
- a second Session transcript or history selector;
- a second message/Tool canonical format;
- per-section message digests that compete with Provider Dispatch;
- a staging Session/Harness used only to manufacture context;
- a separate token estimator.

Workspace does need:

- one owner-qualified Memory View;
- one ephemeral CTI context contribution;
- one non-content binding/adoption receipt;
- deterministic revalidation and failure mapping;
- one Adapter from those products to existing Pi seams.

## Seven logical inputs

The current seven categories are defensible as a business checklist:

1. system instructions;
2. Original User Task;
3. Additional Task Context;
4. Working Set/current working state;
5. Case Context;
6. eligible Session history;
7. active Tools.

They are not seven Provider channels. Pi has three physical channels:
`systemPrompt`, ordered `messages`, and `tools`.

The recommended first profile maps:

- system instructions to `systemPrompt`;
- Session history through `ContextEntryPolicy`;
- Additional Task Context, Working State and Case Context into one labelled
  transient Workspace Context envelope;
- Original User Task as the current exact user message;
- active Tools through the Tool channel.

Optional recall, when later enabled, is another block inside the qualified
Workspace Context envelope, not another authority or database.

This mapping keeps all needed business categories while avoiding three
synthetic user messages and duplicate canonicalization.

## Is a new Pi seam required?

Not for the first bounded no-tool Run.

The current Harness `context` hook can inject one ephemeral Workspace Context
envelope before Provider conversion. The common context-entry policy qualifies
persisted history. Provider Dispatch's application authority can bind the
Workspace adoption receipt to the actual final system/message/Tool digests and
deny drift before Adapter start.

A new generic Pi seam should be proposed only if public acceptance proves that
the existing `context` hook cannot:

- preserve the required placement relative to selected history and current
  user input;
- re-run qualification for every later Provider turn;
- bind the same prepared contribution to application authority without mutable
  side state; or
- support compaction/branch-summary consumers consistently.

Those are later multi-turn/PNW-D questions. They do not justify a speculative
parallel context system now.

## Current implementation drift

The Workspace implementation still:

1. projects caller history;
2. copies it into a new in-memory staging Session;
3. creates a new Harness per Workspace Turn;
4. prepends rendered Orientation through the context hook; and
5. copies the completed result back to the caller Session.

The context hook itself is reusable. The staging Session/Harness and transcript
copy are the migration debt. PNW-B must replace them with one leased Session and
one long-lived Harness.

## Recommendation

Add one private Workspace Run Context Preparation Module. It prepares owner
views and receipts, then configures/adapts existing Pi seams. It returns no
parallel Provider context object and stores no context body.

No Pi change is authorized for the first no-tool profile. Reassess only from a
failing public acceptance case.
