# Waku Agent: runtime context and durable memory boundary

Status: primary-source research input; non-normative.

Research date: 2026-07-27.

Design disposition: **use the Waku agent architecture only as evidence for the
runtime-context boundary.** It shows that Waku's Working Memory is a runtime
composition, not a durable `MemoryEntry` category. CTI-RAG calls the
corresponding concept Context Assembly; it does not adopt `Working Memory` as a
project term. The source does not define CTI-RAG
ownership, authorization, retention, or persistence semantics.

## Question

Does the Waku agent source distinguish runtime Working Memory from durable
semantic, episodic, and procedural memory, and what does it say about their
relationship?

## Primary-source findings

The project-owned architecture document places **Working Memory** in an
**"Ephemeral Agent Run — everything here is rebuilt per turn"**.  It identifies
that runtime value as `SOUL.md + memory context + chat history`, with Working
Memory supplying the LLM call.  This is a runtime composition, rather than one
of the durable memory stores.

Source: [Architecture — the whiteboard, refreshed, Ephemeral Agent Run]
(https://github.com/ShenSeanChen/waku-agent/blob/5f638cfb5de957c14f056027833d8a9df5bbe558/docs/architecture.md#L14-L22).

The same document places a separate **Memory** area outside the ephemeral run.
It identifies `procedural/` (`SKILL.md`, “how to act”), `semantic/` (facts,
using FTS5 or Supabase pgvector), and `episodic/` (dated events), backed by
`state.db`.  A retrieval gate decides whether the current turn needs memory;
semantic and episodic retrieval happens only when needed, while procedural
material reaches Working Memory on a keyword match.

Source: [Architecture — the whiteboard, refreshed, Memory]
(https://github.com/ShenSeanChen/waku-agent/blob/5f638cfb5de957c14f056027833d8a9df5bbe558/docs/architecture.md#L28-L43).

The document further says consolidation is batched after a configured number
of chats, asynchronous to the reply path, and loss-safe in the limited sense
that a summarizer failure leaves the chat log unconsolidated.  It characterizes
these as design choices, and expressly describes the repository as a readable
blueprint rather than a production system.

Sources: [Architecture — design decisions]
(https://github.com/ShenSeanChen/waku-agent/blob/5f638cfb5de957c14f056027833d8a9df5bbe558/docs/architecture.md#L56-L62) and
[What this deliberately is not]
(https://github.com/ShenSeanChen/waku-agent/blob/5f638cfb5de957c14f056027833d8a9df5bbe558/docs/architecture.md#L70-L73).

## Bounded implication for CTI-RAG

This source supports only the following terminology mapping:

```text
Waku Working Memory
  = per-turn runtime composition (SOUL/system context + selected memory context
    + chat history)

CTI-RAG Context Assembly
  = Context Assembly/runtime Provider context (trusted instructions, skills and
    tools, current user input, eligible Session history, qualified owner context,
    and selected durable Memory contributions)
```

Accordingly, selected durable semantic, episodic, and procedural contributions
may enter a runtime context, but that context is not itself evidence that they
are durable entries.  CTI-RAG-specific decisions about owners, admission,
Access Principal, Use Purpose, revalidation, correction, invalidation, deletion,
and recovery require CTI-RAG contracts and are not established by Waku.

## Source pin

The GitHub `main` branch resolved to commit
`5f638cfb5de957c14f056027833d8a9df5bbe558` on 2026-07-27.  Citations above pin
that revision so future branch changes do not silently alter the evidence.
