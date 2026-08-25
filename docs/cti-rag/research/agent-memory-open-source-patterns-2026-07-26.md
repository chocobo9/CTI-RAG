# Agent Memory 开源实现模式调研

状态：Research input，非规范设计。本文用于重新启动 Pi Agent Memory 的架构讨论；不继承此前“当前不需要 Memory Module”的结论。

## 结论摘要

成熟 Agent 框架普遍把 Memory 作为一等能力，并明确区分：

1. 当前线程/运行的短期状态；
2. 跨线程、跨会话或跨任务的长期记忆；
3. 记忆的提取、写入、召回、更新、删除和评估流程。

因此，Pi 应设计独立的 Memory Management Module。这个 Module 不必复制 Case、Session 或 I&E 的权威对象，但必须拥有记忆生命周期、scope、召回策略、写入策略和验证接口。此前把“没有新的统一持久化 owner”推导成“没有 Memory 能力需求”，证据不足，应视为已推翻的设计结论。

## 开源项目对比

### Waku Agent

`waku-agent` 是目前与本项目讨论最接近的参考实现。它把 Agent 明确拆成 Harness、Loop、Memory 和 Eval/LLM-Ops 四个支柱，并在 Memory 内进一步拆成 procedural、semantic 和 episodic 三类。它使用一个本地 SQLite 文件作为可查询来源，而不是只维护一个 `MEMORY.md`；`MEMORY.md` 只是由数据库重新生成的人类可读镜像。

Waku 的每轮运行会重建 Working Memory，组合 system prompt、持久化 facts/episodes、当前聊天历史和当前用户消息。它先运行 retrieval gate，只有判断当前问题确实需要用户记忆时才查询 semantic/episodic store；对话达到阈值后，consolidation 在主回复路径之外把聊天提炼为 facts 和 episode。它还提供 `manage_memory`，让用户或 Agent 修改、纠正和遗忘事实，并将 deterministic eval 与 LLM-as-judge eval 分开。

这与本项目当前图的对应关系是：

| 当前图 | Waku 对应 | 结论 |
| --- | --- | --- |
| Pi Session | `runtime/session.py` 的当前 chat history | 都是短期 Working Memory 输入，不等于长期 Memory |
| Memory Coordination | `retrieval_gate.py` + consolidation + memory tools | Waku 已把召回决策和记忆维护集中起来 |
| Qualified Memory View | `build_system()` 组装后的 durable facts/episodes | Waku 有上下文投影，但没有 CTI 所需的 qualification receipt |
| Context Assembly | `runtime/session.py` 的 Working Memory 构建 | 这是通用且合理的术语/职责 |
| Memory Settlement | consolidation 与 `manage_memory` | Waku 是“提炼后写入”，本项目还需要 settled-run 和安全 admission |
| Evaluation | deterministic eval + LLM judge + release gate | 与本项目需要的端到端验证方向一致 |

Waku 采用的 semantic / episodic / procedural 是有业界来源的分类，但不是某一个统一标准的完整规范。它们分别近似表示“知道什么”“发生过什么”“如何行动”。`Memory Coordination`、`Qualified Memory View` 和 `Memory Adoption Receipt` 则是本项目为了把记忆管理与 CTI 权限、来源和 Provider disclosure 连接起来而使用的架构术语；其中前两个容易与通用术语对齐，后一个属于本项目的治理证据设计。

Waku 不能直接作为 CTI 实现：它的 retrieval gate 在出错时 fail-open；facts store 的 schema 主要是 subject/content/source；episodic store 主要是日期和摘要；其本地单用户 scope 也没有 Case、Access Principal、Use Purpose、版本撤销和跨主体授权。因此它适合作为 Memory 模块的生命周期和数据流参考，不适合作为安全策略本身。

来源：

- [Waku Agent README](https://github.com/ShenSeanChen/waku-agent)
- [Waku architecture](https://github.com/ShenSeanChen/waku-agent/blob/main/docs/architecture.md)
- [Waku semantic store](https://github.com/ShenSeanChen/waku-agent/blob/main/waku/memory/semantic/store.py)
- [Waku episodic store](https://github.com/ShenSeanChen/waku-agent/blob/main/waku/memory/episodic/store.py)
- [Waku retrieval gate](https://github.com/ShenSeanChen/waku-agent/blob/main/waku/memory/retrieval_gate.py)
- [Waku consolidation](https://github.com/ShenSeanChen/waku-agent/blob/main/waku/memory/consolidation.py)

### LangGraph

LangGraph 将短期记忆定义为 thread-scoped state，由 checkpointer 持久化；长期记忆由跨 thread 的 store 管理。两者通常同时存在：checkpointer 负责恢复当前线程，store 负责跨线程的用户偏好、事实和共享知识。

它还区分 semantic、episodic 和 procedural memory，并明确讨论 hot-path 写入与 background 写入的延迟、质量和一致性权衡。长期记忆可以采用单 profile 或 collection；collection 更容易增量生成，但会把更新、删除和搜索复杂度转移到 Memory Module。

对 Pi 的启发：短期状态与长期记忆不能继续混在 Session 或 Workspace State 中；Memory Module 需要独立的 Store seam，并明确写入时机和记忆类型。

来源：

- [LangGraph Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

### Letta / MemGPT

Letta 将记忆组织为 subject、memory blocks 和 messages。Memory block 是带名称和语义的持久化区段，例如 profile、policy、history 或 preference；消息进入后由专门的 memory agent 更新相关 block。另有 archival memory 用于外部长期存储和语义召回。

这个模型强调“记忆不是一堆无标签文本”，而是按主体和用途组织的可管理区段。它适合直接暴露给 Agent 的核心上下文，但对于 CTI 场景还需要加入来源、权限、有效期和证据等级。

对 Pi 的启发：Memory 应有明确的 `subject/scope` 和 typed block，而不是将所有内容压成一个 summary；核心记忆和可搜索归档也应分离。

来源：

- [Letta AI Memory SDK](https://github.com/letta-ai/ai-memory-sdk)
- [Letta memory blocks](https://docs.letta.com/v1-sdk/memory/memory-blocks)

### Mem0

Mem0 将 Memory 明确实现成一组生命周期操作。其更新提示要求对新信息执行 `ADD`、`UPDATE`、`DELETE` 或 `NONE`，并要求更新保持原有 ID。其检索实现还结合实体链接、语义、关键词和时间信号。

它展示了一个重要事实：Memory 的难点不是把文本写进向量库，而是判断新信息与已有记忆的关系，以及在冲突、重复和删除时保持稳定身份。

需要注意的是，Mem0 的通用个性化假设不能直接用于 CTI。CTI 还需要来源绑定、版本、授权范围、可信度和人工/确定性 admission；模型输出不能直接变成可召回事实。

对 Pi 的启发：Memory Interface 至少应覆盖候选提取、身份匹配、add/update/delete/no-op、冲突和审计结果；写入应是经过验证的 Memory Candidate，而不是模型直接写库。

来源：

- [Mem0 repository](https://github.com/mem0ai/mem0)
- [Mem0 memory update operations](https://github.com/mem0ai/mem0/blob/main/mem0/configs/prompts.py)

### Graphiti / Zep

Graphiti 将 Agent Memory 建模成带时间的 context graph：实体、事实/关系和产生它们的 episodes。事实有有效时间窗口，旧事实通常被标记为失效而不是物理删除；派生事实必须可以追溯到原始 episode。

这对安全分析场景尤其有价值，因为“当前成立”和“历史上曾成立”不能混为一谈，修正也不能抹掉历史证据。Graphiti 还支持语义、关键词和图遍历的混合检索。

但 Graphiti 的图谱并不等于 Pi 的完整 Memory Module。它解决的是一种长期语义记忆存储和检索形态，仍需要外围的权限、租户 scope、写入 admission、删除传播、召回绑定和 Agent 验证。

对 Pi 的启发：长期 CTI 记忆应考虑 valid-time、observed-time、supersedes/contradicts、source episode 和 lineage，而不是只有文本与 embedding。

来源：

- [Graphiti repository](https://github.com/getzep/graphiti)

## 对 Pi 的设计取舍

不建议直接复制以下方案：

- 只用 Session transcript 作为 Memory；它无法支持跨任务召回、结构化更新和有效期管理。
- 只用向量库；它无法表达授权、时间有效性、冲突、删除和证据来源。
- 让模型直接维护长期 summary；它会把幻觉、过期结论和未验证判断固化。
- 把所有记忆做成一个全局图；CTI 的 Case、Access Principal、Use Purpose 和数据分区要求更严格的 scope。

建议采用组合架构：

```text
Agent Runtime / Harness
        |
        v
Memory Management Module
  classify -> extract -> admit -> persist -> retrieve -> qualify -> render
        |
        +-- Short-term State Adapter
        +-- Episodic Memory Adapter
        +-- Semantic Memory Adapter
        +-- Procedural Memory Adapter
        +-- Validation / Evidence Adapter
```

第一版不应从向量检索开始，而应先完成可验证的生命周期闭环：

```text
settled Agent Run
 -> candidate extraction
 -> deterministic/schema validation
 -> scope and provenance binding
 -> admission
 -> versioned persistence
 -> scoped recall
 -> pre-disclosure validation
 -> Agent context
 -> correction/deletion
 -> recall exclusion verification
```

## 必须形成的端到端验收

至少需要验证：

1. 一次 Run 能产生可追溯的 Memory Candidate；
2. 未结算、失败、取消和越权结果不能进入长期 Memory；
3. 新任务能按 scope 召回正确记忆；
4. 过期、撤销、冲突和删除后的记忆不能重新进入 context；
5. 同一事实的重复写入不会无限膨胀；
6. 新事实能明确触发 add、update、delete 或 no-op；
7. Agent 能区分当前事实、历史事实、假设和程序性经验；
8. Memory 召回结果能绑定到实际 Provider context 和最终输出；
9. 召回失败、空结果和存储不可用都有可观察且安全的闭合结果；
10. 关闭 Memory Recall 后，系统仍能运行并作为质量对照组。

## 设计方向

这次调研支持的方向是：新增独立的通用 Memory Management Module，并由 CTI Workspace 提供领域 Adapter。Memory Module 拥有记忆生命周期和协调逻辑；Case、I&E 和 Session 继续拥有各自领域对象，但不能再被视为 Memory Module 的替代品。
