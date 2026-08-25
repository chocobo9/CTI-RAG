# CTI-RAG 是否需要独立的 Agent Memory 能力

Status: primary-source research and non-normative design input.

Research date: 2026-07-21.

## 研究问题和结论

问题不是“项目是否已经有持久化状态”，而是：

> CTI-RAG 是否需要把一个调查任务或 Agent Run 中形成的、经过治理的经验和分析连续性，跨任务、跨 Workspace 或跨 Case 重新召回？

结论分两层：

1. 当前设计已经覆盖了任务连续性和业务权威所需的多种持久状态，因此不需要把 Session、Workspace、I&E、Case 再统一改名为 Memory。
2. 如果 CTI-RAG 的产品目标包含跨任务、跨 Workspace 或跨 Case 复用 Agent 经验、分析过程或用户/团队工作偏好，则当前设计缺少一个独立的 Memory 能力边界。这个需求不是 Session、Case、I&E 或 Workspace 任一现有 owner 可以完整承担的。

研究建议：为跨任务复用预留独立的 Memory 能力/owner，并在实现前建立单独的契约。这里的“独立”是研究建议，不是对当前规范新增 Module 或 Artifact 定义。

如果产品明确只需要：

- 同一 Case 的正式状态连续性；
- 同一 Workspace 的任务上下文连续性；
- OpenCTI/I&E 资源的可复用检索；
- Pi Session 的会话恢复、分支和压缩；

则现有边界可以工作，不必新增通用 Memory 能力。

## 一、当前本地设计已经确定的持久状态与 owner

以下是当前文档已确定的设计事实，不是本研究新增的定义。

| 内容 | 当前 owner | 可解决的连续性 | 明确不能替代的东西 |
|---|---|---|---|
| Pi Session | Pi Session；Harness 协调 Save Point 生命周期 | 继续、压缩、分支和恢复一条 Agent 工作历史 | 跨任务语义召回、Case 权威、通用长期记忆 |
| User Task、Admitted Task Context、Capability、v1 Working Set 记录 | Workspace 语义，v1 由 Pi Session 作为提交权威 | 当前 Workspace/任务的恢复和下一轮 context 重建 | 跨 Workspace 的 Agent 经验库 |
| Workspace Artifact 和 Assessment 相关版本 | Agent Investigation Workspace | 任务内结果复查、版本演化、后续发布或 Case Proposal 的输入 | Case State、Session transcript、自动长期记忆 |
| Source Capture、Resource Version、Derivative、Retrieval Receipt、Resource Capsule | Intelligence and Evidence | 跨 Case 复用有来源、有版本的情报材料 | Agent 的个人/团队经验、任务决策历史 |
| Case State、Case Revision、Proposal Receipt | Case Management | 跨用户任务和 Agent Run 的正式调查业务连续性 | Agent memory、transcript、未经接受的分析判断 |

当前 architecture overview 明确写出：Model Context 只是一次同步状态的 rendering，不是 durable memory store；交互历史属于 Session，持久任务方向和 derived analytic memory 属于 Workspace task/artifact state，正式 Case state 属于 Case Management，可复用 source/corpus state 属于 I&E。[Workspace State composition](../agent-workspace/context-projection-design.md#50-workspace-state-composition)

Case Management 的 domain language 还明确把 `Agent memory` 排除在 `Case State` 之外；I&E 则把 Intelligence Resource 定义为可跨 Case 复用、带 provenance 的来源材料。[Case Management language](../case-management/CONTEXT.md)，[I&E language](../intelligence-evidence/CONTEXT.md)

这说明设计并非没有考虑“记忆”问题。更准确的判断是：设计已经把不同类型的持久性拆给现有 owner，但没有完成跨 owner 的 Agent Memory 语义。

## 二、从 CTI-RAG 业务推导出的记忆需求

以下是基于当前业务边界的推导，不是当前文档已经批准的设计。

### 1. 同一 Case 的连续性：已有能力基本足够

Case 被定义为跨用户任务和 Agent Run 的长期调查业务实例。正式 Case State、Workspace task/artifact state 和 Session history 已经分别承担：

- 正式接受过的调查状态；
- 当前任务的工作方向、Working Set 和分析产物；
- Agent 的交互历史和恢复依据。

这里不需要另造 Memory 来保存 Case 真相。若新增一层把 Case State 再复制成“记忆”，会产生两个问题：权威重复和撤销/版本不同步。

### 2. 同一 Case 的跨任务分析连续性：有明确缺口

一个真实调查会出现多个任务：初始定位、补充检索、时间线重建、假设比较、复核和交接。后一个任务通常需要知道前一个任务：

- 已经验证过哪些路径；
- 哪些假设被排除、依据是什么；
- 哪些检索路线失败或不完整；
- 哪些结论只是暂时假设；
- 哪些分析产物可以继续复核。

Session 可以保存一条工作历史，Workspace Artifact 可以保存被定义和接纳的产物，Case 可以保存正式接受的状态；但当前文档没有定义一个面向新任务的统一“从历史分析中发现并召回相关经验”的机制。

这是 Memory 能力的第一个强需求来源，但不要求把未接受的分析直接升级为 Case State。

### 3. 跨 Workspace 复用：取决于产品是否支持任务迁移或团队协作

当前文档将 Workspace 绑定到任务、Case、actor/purpose 和 Session。它还明确把多用户 shared-analysis discovery、co-editing、notifications 和 cross-user context injection 列为 deferred。

因此，跨 Workspace 复用不是当前已批准的业务行为。它是一个研究建议上的条件需求：如果同一组织需要把已验证的调查方法、失败路径或团队偏好带到另一个 Workspace，Session 和 Workspace task state 都不适合作为跨 Workspace owner。

### 4. 跨 Case 复用：情报材料已有，Agent 经验没有

I&E 已经负责跨 Case 复用的 source material、provenance、resource version 和 retrieval。OpenCTI 也提供全局知识、关系、外部引用和历史。

但“某个调查中采用过什么判断路径”与“某个情报资源是什么”不是同一类数据。前者涉及：

- 适用的任务/范围；
- 使用者和披露目的；
- 当时的 Case/Orientation/Resource Version；
- 证据支持和反证；
- 时间有效性；
- 是否只是分析建议，还是已经被 Case Management 接受。

如果产品需要跨 Case 复用这些经验，不能把它们直接写入 I&E Resource，也不能把它们伪装成 Case State。它需要另一个受治理的持久能力。

### 5. CTI 业务不适合“自动记住一切”

CTI 里的旧判断可能因新来源、撤销、授权变化或 Case 修订而失效。因而需要记住的不是一段无来源的模型摘要，而是可追溯的分析经验：它引用哪些 Session/Task/Artifact/Resource/Case 版本，适用范围是什么，何时失效，谁可以看到。

这使 CTI-RAG 的 Memory 需求不同于普通聊天偏好记忆：核心不是个性化，而是受 provenance、authorization、version、validity 和 retention 约束的分析连续性。

## 三、外部一手资料的支持与限制

### 1. Agent memory 是独立的架构关注点，但不是自动必需

CoALA 将语言 Agent 描述为包含 memory components、内部 memory actions 和外部环境 actions 的架构；其中 retrieval 读取长期 memory，learning 写入长期 memory，reasoning 更新短期 working memory。[CoALA 原文](https://arxiv.org/abs/2309.02427)

这支持一个判断：当 Agent 需要跨当前 context 使用过去经验时，memory 应被视为独立的架构关注点，而不是把所有内容塞进 prompt 或 Session。

但 CoALA 是概念框架，不证明每个 Agent 产品都需要一个独立存储 Module。是否需要，仍取决于 CTI-RAG 是否真的要跨任务/跨 Workspace/跨 Case 复用经验。

### 2. 长期交互需要外部持久化和主动检索

Generative Agents 使用完整经验记录、随时间形成的高层 reflection 和动态 retrieval 来支持后续行为规划；论文的消融实验显示 observation、planning、reflection 对其行为质量都有影响。[Generative Agents 原文](https://arxiv.org/abs/2304.03442)

MemGPT 将 context window 视为受限资源，通过层级 memory 管理超出当前窗口的内容，并在长文档分析和多 session 对话中验证这种方向。[MemGPT 原文](https://arxiv.org/abs/2310.08560)

这支持 CTI-RAG 的一个具体推导：Session 压缩和 branch 只能解决一条工作历史的上下文管理；如果要跨任务重新找到旧分析，就需要独立的持久化和召回语义。

### 3. 召回不是简单的向量相似度

LangGraph 官方文档明确区分：short-term memory 是 thread-scoped state，long-term memory 跨 conversations/sessions，并按 namespace 保存；其文档还明确说 long-term memory 没有 one-size-fits-all 方案，写入可以在请求热路径进行，也可以异步后台进行。[LangGraph memory overview](https://docs.langchain.com/oss/python/concepts/memory)

LongMemEval 将长期 memory 的核心能力拆成 information extraction、cross-session reasoning、temporal reasoning、knowledge updates 和 abstention，并报告长上下文模型和商业系统在持续交互记忆上出现显著性能下降。[LongMemEval 原文](https://arxiv.org/abs/2410.10813)

对 CTI-RAG 的直接含义是：Memory 召回至少要先经过确定性范围、actor/purpose、授权、时间/版本和有效性过滤，再做相关性排序。只按 embedding 相似度召回，会把旧 Case、无关 actor、已撤销材料或不适用的分析带入当前任务。

### 4. CTI 一手标准要求版本、来源和撤销，不支持“最后写入获胜”

STIX 2.1 将对象的 creator、created/modified、revoked、confidence、external references 和 markings 纳入通用模型；其版本规则要求同一对象的后续版本使用新的 `modified`，撤销是永久性的，不能再创建该对象的后续版本。[OASIS STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html)

OpenCTI 官方文档也把实体的关系、外部引用和历史作为知识查看的一部分，并说明知识中的 create/update/delete 活动可以通过 history 追溯。[OpenCTI entity overview](https://docs.opencti.io/latest/usage/overview/)，[OpenCTI audit overview](https://docs.opencti.io/latest/administration/audit/overview/)

这不能直接规定 Agent Memory 的 schema，但足以支持 CTI 侧的约束：Memory 只能是有来源、有版本、可撤销/失效、受 marking 和授权过滤的衍生材料；它不能成为 OpenCTI 或 Case 的替代权威。

### 5. 记忆会引入新的安全风险

NIST 的 Generative AI Profile 将 confabulation、data privacy、information integrity 和 information security 列为生成式 AI 风险类别。[NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)

对 CTI-RAG 的推导是：自动写入的 Memory 可能把模型幻觉固化；跨 Case 召回可能产生越权披露；过期记忆可能污染当前判断；删除要求还必须覆盖派生摘要、索引和缓存。Memory 因而必须增加治理成本，而不是简单地增加一个向量库。

## 四、为什么当前设计看起来“已经指向 Memory”，但没有独立设计

当前文档给出的信号是一致的：

1. 它明确写了 `derived analytic memory` 属于 Workspace task/artifact state；
2. 它同时写明 Model Context 不是 durable memory store；
3. 它把 Session、Case、I&E 的持久性分别交给各自 owner；
4. Case language 明确禁止把 Case State 叫作 Agent memory；
5. I&E 负责可复用 source/corpus state，而不是 Agent 的历史经验。

因此，客观解释不是“设计完全没考虑 Memory”，也不是“已经有一个完整 Memory Module”。更准确的是：

> 当前设计已经识别了不同持久内容的归属，并明确防止它们被混成一个 memory blob；但对跨任务/跨 Workspace/跨 Case 的 Agent 经验写入、召回、冲突、失效和删除，还没有闭合的 owner 与契约。

## 五、研究建议：需要什么，不应做什么

以下全部是非规范研究建议，不能视为当前项目已批准的 Module/Artifact。

### 建议的最小独立能力

如果产品确认跨任务经验复用，独立能力至少要能回答：

- 什么内容允许从已完成 Run 或 Workspace Artifact 进入长期复用集合；
- 写入者是模型提出候选，还是确定性规则/人工确认；
- 每条内容绑定哪些 Task、Workspace、Case、actor、purpose、Resource Version 和 Artifact 版本；
- 当前用户是否有权看到它；
- 它是事实、历史事件、分析假设、失败经验还是流程偏好；
- 新信息如何形成新版本、撤销旧版本或保留冲突；
- 如何按精确范围和时间过滤，再做相关性召回；
- 如何删除原文、摘要、索引、embedding、缓存和派生关系；
- 如何证明召回提升了任务效果，而不是制造错误个性化或旧结论污染。

### 模型与确定性代码的建议分工

- 模型可以提出“值得保留的候选经验”和相关说明；
- 确定性代码验证来源、范围、版本、授权、敏感性、状态和重复身份；
- 未经接纳的模型候选不能进入长期复用集合；
- 召回结果必须先通过业务资格过滤，模型只能在已准入材料上推理；
- Memory 结果不能直接改变 Case State、Capability、Tool authorization 或 I&E Use Disposition。

### 推荐的写入与召回时机

研究上更适合把候选写入放在 settled Run、Workspace Save Point 和 Publication/Case admission 之后，或作为异步候选生成再经过确定性接纳。不能在每个 streaming delta 或未完成 Tool Call 后直接写入。

召回也不应每轮无条件发生。应由当前任务类型、已有 context 是否不足、历史依赖是否存在和确定性范围策略触发；否则旧记忆会增加 token、延迟和污染面。

### 替代方案

在没有跨任务经验复用需求时，继续使用现有分层：

- Session 负责交互历史；
- Workspace 负责任务和分析产物；
- I&E 负责可复用情报；
- Case 负责正式调查状态。

这是成本最低、权威边界最清楚的方案。它只是不提供通用的跨任务 Agent 经验召回。

## 六、最终审计判断

| 问题 | 判断 |
|---|---|
| 当前设计是否已有持久状态？ | 是，而且 owner 划分清楚。 |
| 当前设计是否已有完整的跨任务 Agent Memory？ | 否。没有闭合写入、召回、冲突、失效、删除和效果验证语义。 |
| CTI-RAG 是否需要 Memory 能力？ | 若产品要复用跨任务/跨 Workspace/跨 Case 的 Agent 经验，答案是是；从 CTI 调查连续性看，这是有业务依据的需求。 |
| 是否应把 Session/Workspace/I&E/Case 合并成 Memory？ | 否。那会破坏现有 authority 和 retention 边界。 |
| 是否应立即实现独立 Memory Module？ | 否。本研究只证明需求缺口和建议的 owner 边界，不授权实现。 |
| 下一步最重要的设计工作是什么？ | 先确定跨任务经验复用的首个业务场景、允许的 scope、接纳门槛和删除/失效规则，再决定独立能力的契约和存储。 |

## 参考的当前本地设计文件

- [CTI-RAG 文档规则与导航](../README.md)
- [Agent Workspace context language](../agent-workspace/CONTEXT.md)
- [Agent Workspace State composition](../agent-workspace/context-projection-design.md#50-workspace-state-composition)
- [Pi-native Workspace lifecycle](../agent-workspace/pi-native-workspace-lifecycle-v1-contract.md)
- [Case Management context](../case-management/CONTEXT.md)
- [Intelligence and Evidence context](../intelligence-evidence/CONTEXT.md)
- [ADR 0012: Pi Harness as Workspace execution spine](../adr/0012-use-pi-harness-as-workspace-execution-spine.md)
- [ADR 0015: Session authority and pre-dispatch proof](../adr/0015-use-session-authority-and-pre-dispatch-proof-for-workspace-capabilities.md)

