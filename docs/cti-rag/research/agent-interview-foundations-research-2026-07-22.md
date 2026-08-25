# Agent 前沿技术研究：面试基础与可验证表达

研究日期：2026-07-22  
范围：system prompt、few-shot、JSON Schema/structured outputs、推理服务 KV cache。  
证据等级：优先官方产品文档、标准、原始论文与一方项目文档；未使用二手博客。  
Design disposition：本文全部建议均为候选建议、非规范；只有被现行 contract/ADR 正式采纳后才成为产品约束。

## 结论先行

1. System prompt 是高优先级的行为与边界说明，不是安全授权、业务真值或后端校验的替代品。应把稳定规则、角色、任务目标、工具使用边界和失败行为分层写清，并用评测验证冲突场景。
2. Few-shot 不是“越多越好”：示例应覆盖真实输入分布、边界和负例，且每个示例都必须与目标行为一致。放置上，把稳定指令和示例放在可复用的前缀，动态任务放在后部，有利于 prompt/prefix cache；示例本身仍需通过质量与回归评测筛选。
3. Structured outputs 的可靠边界是“结构约束”，不是业务语义正确性。即使 provider 具备 strict schema，也仍需处理 schema 不支持、拒答、截断、传输错误、解析/验证失败和业务规则失败。
4. 面试中应把 KV cache 说成一组不同层次的优化：prompt/prefix caching 复用共同前缀的预填充计算；PagedAttention 管理 KV 的物理内存布局；continuous batching/iteration-level scheduling 管理请求调度；prefix sharing 是跨请求共享前缀 KV 的更一般概念，RadixAttention/APC 是实现路径之一。它们可以组合，但不是同义词。

## 1. System prompt 设计原则

### 1.1 高优先级不等于绝对可信

OpenAI 的 instruction hierarchy 研究把 system、developer、user、tool 等输入区分为不同优先级，并指出系统提示与不可信用户/工具内容发生冲突时需要按优先级处理；该工作同时将 prompt injection 视为模型可能把不同来源当作同等指令的问题。[OpenAI 原始研究](https://openai.com/index/the-instruction-hierarchy/)

候选设计原则：system prompt 只承载模型可理解的行为框架，例如职责、输出目标、证据使用方式、工具调用条件和遇到不确定性时的处置；身份认证、Case/Resource 授权、写入许可、事实真值和结果完整性必须由可信 host/owner 校验。这个区分是由“模型遵循指令”推导出的系统边界，不是 provider 对业务授权的保证。

### 1.2 可执行、少歧义、正向描述，并为失败规定动作

Anthropic 官方提示工程文档建议明确、直接地描述任务和期望输出，给出上下文/动机，并指出示例与细节会影响行为；其格式建议倾向于描述“应该做什么”，而非只堆叠禁止事项。[Anthropic 提示工程总览](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview)；[Anthropic 提示最佳实践](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

候选分层：

- 稳定角色与目标：模型是谁、当前任务成功标准是什么。
- 约束与优先级：哪些输入是指令、哪些是数据；冲突时如何处理。
- 工作协议：何时直接回答、何时请求澄清、何时调用工具、何时停止。
- 输出协议：字段/格式/引用/不确定性表达。
- 失败协议：缺证据、工具失败、拒答、截断、冲突输入时返回何种可处理状态。

不要把 system prompt 写成没有终点的流程图或隐含授权清单。对于高风险行为，提示只能提出模型应遵守的候选行为；host 仍应在调用前后做独立 admission、校验和发布门控。

### 1.3 把抗注入作为评测维度，而不是一句口号

OpenAI 的 instruction-hierarchy 研究以及后续官方挑战说明都将工具输出中的恶意指令列为需要隔离的场景，并强调高优先级指令应压过低优先级内容。[Instruction hierarchy challenge](https://openai.com/index/instruction-hierarchy-challenge/)

候选评测集至少应包含：用户与 system 冲突、工具结果带有伪指令、引用材料要求模型泄露系统提示、缺失证据却要求确定结论、以及结构化格式与安全拒答冲突。研究证据也提醒，层级遵循并不可靠；因此“写了 system prompt”不能被表述为“安全边界已建立”。[IHEval 原始评测论文](https://aclanthology.org/2025.naacl-long.425/)

## 2. Few-shot 示例选择与放置

### 2.1 示例的作用与选择

Anthropic 官方文档建议使用多个、相关、清晰且相互一致的示例来展示期望行为，并指出示例会直接影响模型对细节和格式的学习。[Anthropic 使用示例](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#use-examples-effectively)

候选选择流程：先按目标任务的真实输入分布分层，再选能代表主路径、边界、歧义、拒绝/澄清和错误恢复的最小集合；每个示例都应有可检查的 expected output。优先“能消除歧义”的示例，而不是仅增加相似样本。示例不能包含与生产目标相反的措辞、过时字段、未授权工具调用或未验证事实。

一个实用的候选示例矩阵：

| 类别 | 应展示什么 | 失败风险 |
| --- | --- | --- |
| 正常样例 | 输入到目标输出的完整映射 | 只覆盖 happy path |
| 边界样例 | 空值、长输入、多个实体、低置信度 | 模型学到异常格式 |
| 负例 | 应拒绝、澄清或不调用工具的输入 | 负例写得像可执行指令 |
| 纠错样例 | 工具错误、无证据、schema/业务校验失败后的动作 | 把 retry 误教成无限重试 |
| 变体样例 | 同一意图的不同表述/语言/顺序 | 示例数量膨胀、前缀变动 |

### 2.2 放置、隔离与 cache 影响

示例应与任务指令清晰分隔；Anthropic 文档推荐用 XML 标签等结构化分隔符来区分指令、上下文和示例，并展示 user/assistant 交替格式。[Anthropic XML/示例实践](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

候选布局：稳定 system instructions → 固定工具/输出说明 → 固定 few-shot → 动态任务与证据 → 当前请求。OpenAI prompt caching 文档说明，缓存依赖请求前缀的复用，并建议把静态内容放前面、动态内容放后面；这优化的是 provider 侧已处理的 prompt 前缀，不改变 few-shot 的语义。[OpenAI Prompt Caching](https://developers.openai.com/api/docs/guides/prompt-caching)

重要边界：示例放在 system message、developer message 或 user/assistant 对话模板，实际效果取决于模型与 API 的消息模板；不能把某一 provider 的位置经验宣称为跨模型定律。应通过代表性评测比较“无示例、少量精选示例、更多示例、不同顺序/位置”，同时记录准确率、拒绝正确率、token、延迟和 cache 命中。

## 3. JSON Schema / structured outputs

### 3.1 三层约束模型

JSON Schema 2020-12 是用于描述和验证 JSON 数据的标准；规范本身定义的是数据模型、schema 关键字和验证语义，不是 LLM 生成器，也不保证语义真实。[JSON Schema Specification](https://json-schema.org/specification)；[Validation vocabulary](https://json-schema.org/draft/2020-12/json-schema-validation)

Agent 中应区分三层：

1. **生成层**：provider 的 structured output、function/tool schema 或本地 grammar/constrained decoding，限制模型输出的语法/结构。
2. **解析验证层**：JSON parse、schema validation、字段类型/必填/枚举/额外字段等确定性检查。
3. **业务层**：授权、版本、引用存在性、跨字段不变量、证据支持、操作副作用和发布资格。

OpenAI Structured Outputs 文档说明，strict schema 使用动态 constrained decoding；同时 API 只支持 JSON Schema 的一个子集，且拒答和不完整响应需要按专门状态处理。[OpenAI Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)；其原始说明也明确描述了把 schema 转成 CFG 并在生成过程中约束有效 token 的实现思路。[OpenAI 原始发布说明](https://openai.com/index/introducing-structured-outputs-in-the-api/)

### 3.2 实现候选

- 云 API：优先使用 provider 原生 strict structured outputs；启动时静态检查 schema 是否在 provider 支持子集内。
- Tool/function calling：把模型可提出的参数 schema 与 host 绑定的身份、授权、Case、版本和幂等信息分离；模型不应提供 host 已知的安全关键字段。
- 自托管：使用 grammar/CFG/有限状态机等 constrained decoding；例如 Outlines 的一方文档说明其可从 JSON Schema/Pydantic 生成结构化输出约束。[Outlines JSON structured generation](https://dottxt-ai.github.io/outlines/reference/generation/json/)
- 所有路径：生成前编译/检查 schema，生成后仍执行 parse + schema validation + 业务 validation；不要因 provider 宣称“guaranteed”而省略后置检查。

### 3.3 失败处理与边界

候选状态机：

- schema 不被 provider 接受/编译失败：在调用前失败，记录 provider/schema capability，不盲目重试。
- 安全拒答：保留拒答状态和安全说明；不要把拒答文本强行当作业务对象，也不要用 retry 绕过安全边界。
- incomplete/truncated：标记为不完整；可在预算允许且原因是可恢复的情况下重新生成，但不能把截断 JSON 当作部分成功。
- JSON parse/schema failure：返回结构化 validation failure，带字段路径和可重试性；有界地重试或转人工/澄清。
- schema-valid 但业务-invalid：拒绝进入 Case、Working Set、Tool side effect 或发布路径；这不是“模型输出成功”。
- 网络/服务错误：按错误类别区分瞬时失败、认证/权限失败、限流和未知效果；重试策略由 host 决定，不由模型自行声明。

“严格 schema = 业务正确”是错误表达；准确说法是：“strict constrained decoding 可把输出限制在 provider 支持的结构语言内，但拒答、不完整、provider 子集、语义正确性和业务授权仍需独立处理。”

## 4. KV cache 优化：四个容易混淆的层次

### 4.1 先区分 prefill 与 decode

自回归 Transformer 通常先对输入做 prefill，产生各层 token 的 K/V；随后 decode 每轮只为新 token 追加 K/V 并读取历史 K/V。因而共享长前缀主要降低 prefill/TTFT，而不会自动降低新输出 token 的 decode 成本。vLLM 官方文档明确指出 Automatic Prefix Caching 复用已有查询的 KV、跳过共享前缀计算，但不减少生成新 token 的阶段。[vLLM Automatic Prefix Caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/)

### 4.2 Prompt caching / prefix caching

**Prompt caching（API/产品层）**通常指服务商在请求之间缓存已处理的 prompt 前缀，目标是降低输入处理延迟和成本；OpenAI 文档要求稳定内容形成相同前缀，并提供缓存命中相关机制。[OpenAI Prompt Caching](https://developers.openai.com/api/docs/guides/prompt-caching)

**Prefix caching（推理引擎层）**是复用共同 token 前缀对应的 KV。vLLM APC 文档给出两个典型 workload：同一长文档的多次查询、同一多轮会话的后续轮次；若没有共同前缀或生成阶段占主要成本，则收益有限。[vLLM APC feature documentation](https://docs.vllm.ai/en/v0.9.0/features/automatic_prefix_caching.html)

面试准确表达：两者都可能复用前缀处理结果，但前者是 provider/API 的缓存产品语义，后者是 serving engine 的 KV 复用机制；具体命中键、TTL、租户隔离、模型/适配器边界和是否跨请求，必须以实现文档为准，不能混称成“把整个上下文缓存了”。

### 4.3 Paged KV cache / PagedAttention

PagedAttention 把每个请求的 KV cache 分成固定大小 block，使物理存储可以非连续分配，减少碎片和动态长度带来的浪费；vLLM 原始论文还讨论了请求内/请求间的 KV sharing。[PagedAttention 原始论文](https://arxiv.org/abs/2309.06180)；[vLLM APC 设计文档](https://docs.vllm.ai/en/v0.9.1/design/automatic_prefix_caching.html)

它回答的是“KV 放在哪里、如何高效管理和映射”，不是“哪些请求共享前缀”的全部策略。Paged layout 可以作为 prefix caching、prefix sharing、调度和抢占的底座，但 PagedAttention 本身不等于 continuous batching，也不等于 prompt cache 命中。

### 4.4 Batching 与 continuous batching

普通静态 batching 等待一组请求组成 batch，常被长短不一的 decode 请求互相拖住。Orca 原始 OSDI 论文提出 iteration-level scheduling：调度粒度从完整 request 改为单次 iteration，并配合 selective batching，让已完成请求退出、新请求在运行中加入。[Orca OSDI 2022 原始论文](https://www.usenix.org/conference/osdi22/presentation/yu)

因此 **continuous batching** 主要是请求调度/执行组织方式，目标是提高 GPU 利用率、吞吐和到达请求的响应性；它不必然复用 prompt KV，也不解决 KV 内存碎片。它通常与 paged KV cache、prefix caching 同时使用，但概念正交。

### 4.5 Prefix sharing

Prefix sharing 是目标/能力：多个请求拥有相同 token 前缀时共享其 KV，而不是每个请求各自存一份。vLLM 论文将 flexible sharing 作为 KV 内存优化的一部分；SGLang 原始论文讨论了 RadixAttention，并给出 cache-aware scheduling 与 continuous batching 的组合。[vLLM PagedAttention 论文](https://arxiv.org/abs/2309.06180)；[SGLang 原始论文](https://papers.nips.cc/paper_files/paper/2024/file/724be4472168f31ba1c9ac630afc15dec8-Paper-Conference.pdf)

实现上可以是 block hash/APC，也可以是 radix tree/RadixAttention；共享通常要求 token 序列、模型权重、相关运行条件和缓存隔离键匹配。共享前缀越长、请求越多、输出相对越短，通常越值得；但这属于 workload-dependent 的性能推断，应以 benchmark 验证。

## 5. 面试表达模板

### 5.1 一句话版

“我把 agent 的可靠性拆成提示层、生成约束层、host 校验层和推理服务层：system prompt 负责可理解的行为边界，JSON Schema 负责结构，业务代码负责授权与语义，KV 优化负责重复前缀和推理调度。KV 方面，prefix/prompt caching 是复用前缀计算，PagedAttention 是内存分页，continuous batching 是运行时调度，prefix sharing 是跨请求共享 KV 的能力；它们可以组合但不是同一个技术。”

### 5.2 被追问“怎么保证 JSON 一定正确”

“我不会说一定正确。provider strict mode 或 constrained decoding 能显著加强语法/结构约束，但支持的是 provider 子集；我还会处理拒答、截断、解析失败、schema validation 和业务不变量。只有通过 host 的业务校验，结果才有资格进入后续 agent 状态或副作用路径。”

### 5.3 被追问“怎么选 few-shot”

“我按真实分布、边界、负例和失败恢复做覆盖，选最小但有区分度的示例集；每个示例都有可评测的 expected output。我把稳定示例放在动态输入前以利于 prefix cache，但用回归评测验证顺序、位置、token 成本和行为变化，而不是把 cache 命中当成质量证据。”

### 5.4 被追问“PagedAttention 是不是 prefix cache”

“不是。PagedAttention 是 KV block 的物理内存管理与 attention 映射机制；prefix cache 是跨请求复用共同前缀 KV 的策略。前者可以支持后者，但两者优化目标不同。”

## 6. 当前 CTI-RAG 的候选 Design disposition

以下不修改任何现行 contract，仅作为候选设计输入：

1. 将 system prompt 视为模型行为协议，不把它当授权或真值层；工具结果、检索证据和用户内容默认按不可信数据处理。
2. 为 system prompt、few-shot、schema、tool definitions 维护稳定版本和评测集；优先保持稳定前缀，动态 Case/Working Set/当前任务靠后。
3. 对结构化输出采用“provider 约束 + 本地 parse/schema validation + owner 业务 validation + publication/admission gate”的分层链路。
4. 研究 KV 性能时分别报告 prefix-cache hit、prefill/TTFT、decode/ITL、GPU KV 使用、吞吐、P50/P99 和失败/驱逐，不用单一“KV cache 命中率”代替全部指标。
5. 在面试或设计评审中明确标注：哪些是 provider 保证，哪些是开源实现行为，哪些只是从论文/文档推导出的候选建议。

## 7. 来源与研究边界

主要来源：

- [OpenAI Instruction Hierarchy](https://openai.com/index/the-instruction-hierarchy/)
- [OpenAI Instruction Hierarchy Challenge](https://openai.com/index/instruction-hierarchy-challenge/)
- [OpenAI Prompt Engineering](https://developers.openai.com/api/docs/guides/prompt-engineering)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI Prompt Caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Anthropic Prompt Engineering Overview](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview)
- [Anthropic Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [JSON Schema 2020-12 Specification](https://json-schema.org/specification)
- [OpenAI Structured Outputs 原始说明](https://openai.com/index/introducing-structured-outputs-in-the-api/)
- [Outlines structured generation 文档](https://dottxt-ai.github.io/outlines/reference/generation/json/)
- [PagedAttention 原始论文](https://arxiv.org/abs/2309.06180)
- [vLLM Automatic Prefix Caching 文档](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/)
- [Orca OSDI 2022 原始论文](https://www.usenix.org/conference/osdi22/presentation/yu)
- [SGLang NeurIPS 原始论文](https://papers.nips.cc/paper_files/paper/2024/file/724be4472168f31ba1c9ac630afc15dec8-Paper-Conference.pdf)
- [IHEval 原始评测论文](https://aclanthology.org/2025.naacl-long.425/)

未覆盖：特定云厂商的私有 cache 实现、硬件厂商内部 kernel、未公开的模型训练配方，以及任何无法由上述一手资料直接支持的性能数字。本文不构成规范、SLA、授权模型或现行 CTI-RAG contract 的修改。
