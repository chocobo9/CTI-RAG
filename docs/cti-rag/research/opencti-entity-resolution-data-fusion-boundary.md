# OpenCTI / STIX 实体解析与数据融合边界

## 研究问题与结论

本研究只使用 OpenCTI 官方文档、OASIS STIX 2.1 规范和 MISP 官方资料，回答以下问题：Threat Actor 同义异名、相似行为、观测活动、歧义、来源谱系和数据融合，成熟平台已经解决到哪一层，哪些仍应由 Intelligence & Evidence、Case Management 和 Agent Workspace 判断。

核心结论是：**成熟方案不是把“名称相似、行为相似、活动归因”合并成一个自动实体解析问题，而是把它们分成三个不同问题。**

1. **名称身份解析**：两个名称是否指向同一个对象。STIX 提供 `aliases`、`duplicate-of`；OpenCTI 用名称/别名做精确去重，并支持人工 merge。
2. **活动聚类**：一组 TTP、工具、恶意软件和基础设施是否构成同一个活动簇。STIX/OpenCTI 用 `Intrusion Set` 表示这一层，即使背后的真实 Threat Actor 尚不明确。
3. **行为主体归因**：某 Intrusion Set、Campaign 或活动是否由某个实际个人、组织或群体实施。STIX 用独立的 `attributed-to` Relationship 表示；OpenCTI 可以传播已有归因，但没有根据相似行为自动证明 Actor 身份的能力。

因此，OpenCTI 可以高度复用为规范化知识图谱和候选关系来源，但不能被当成自动 Actor attribution 裁判器。名称解析假设与归因假设也必须分开：

```text
Entity Resolution Hypothesis:
  Vendor Actor Name A 与 Vendor Actor Name B 是否是同一对象？

Activity Clustering Hypothesis:
  Observation Set X 与 Intrusion Set Y 是否属于同一活动簇？

Attribution Hypothesis:
  Intrusion Set Y 是否由 Threat Actor Z 实施？
```

## 能力分层

| 层级 | OpenCTI / STIX 已提供的能力 | 自动化程度 | CTI-RAG 边界 |
|---|---|---|---|
| 语法规范化 | STIX SCO ID-contributing properties；OpenCTI 对 Observables 生成确定性 ID | 高 | 可直接复用，但仍保留原始值和来源 |
| 精确实体去重 | OpenCTI 按类型特定的名称、别名或模式生成确定性 ID 并 upsert | 高 | 只视为精确键解析，不能扩展成行为相似解析 |
| 同义异名 | STIX `aliases`；OpenCTI 名称/别名唯一集合；MISP Galaxy `synonyms` | 中 | 只有已确认同一对象时才进入 canonical alias |
| 语义重复 | STIX `duplicate-of`；OpenCTI 人工 merge | 人工决策 | 未确认时保留两个实体和 Resolution Hypothesis；不要直接 merge |
| 活动聚类 | `Intrusion Set`、Campaign、Observed Data、Sighting、`uses` / `targets` 等图关系 | 数据模型成熟，判断非自动 | I&E 保存活动簇候选；Case/Workspace 分析是否属于同一活动 |
| Actor 归因 | `attributed-to` Relationship、relationship confidence、Opinion | 表达能力成熟，结论非自动 | 保留竞争性 Attribution Hypotheses；R2/R3 决策不交给 OpenCTI dedup |
| 歧义与异议 | 多条关系、confidence、Opinion、Grouping、MISP `similar` | 可表达，未规定求解方法 | Workspace/Case 使用 ACH、来源依赖和人工复核管理 |
| 来源谱系 | `created_by_ref`、Report、External Reference、`derived-from`、容器和历史 | 部分成熟 | 不能把 graph edge 数量当独立佐证；需额外 lineage/dependency 计算 |
| 自动推理 | OpenCTI 预定义关系传播规则、inferred 标记、可撤销规则结果 | 高，但仅限规则蕴含 | 作为派生关系，不作为新的独立证据或自动归因证明 |

## 1. 同义异名：`aliases` 是已作出的身份断言，不是歧义容器

STIX Threat Actor 的 `aliases` 定义为该 Threat Actor “被认为使用”的其他名称；Threat Actor 本身代表实际的个人、群体或组织。STIX 同时明确 Threat Actor 不等于 Intrusion Set。换言之，把名称写入同一个 `aliases` 数组，语义上已经在断言这些名称属于同一 Threat Actor，而不是仅仅表示“可能相同”。[OASIS STIX 2.1：Threat Actor](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#threat-actor)

OpenCTI 对 `Threat Actor` 使用 `name OR alias` 作为 ID-contributing properties，并规定名称和别名共同构成唯一值集合：别名不能与另一实体的名称或别名重叠。创建或导入对象时，如果这些属性解析到现有对象，OpenCTI 返回并可能更新该对象。[OpenCTI：Deduplication](https://docs.opencti.io/latest/usage/deduplication/)

这解决的是**已知同义异名的规范化和精确 upsert**，不解决以下问题：

- 两家厂商是否以不同名称跟踪同一个实际群体；
- 一个名称是 Threat Actor、Intrusion Set、Campaign 还是一次 Operation；
- 两个活动簇高度相似是同一主体、共享工具、人员流动，还是模仿/false flag；
- 同一个厂商标签在不同时间是否发生语义漂移。

OpenCTI 自己也警告，外部 feeds 常把攻击者群体建模为 Intrusion Set，行业中这两个概念经常混用。其官方说明把 Threat Actor 定义为实际人员/群体，把 Intrusion Set 定义为可以在不知道行为主体时仍用于关联恶意活动的技术/行动集合。[OpenCTI：Threats](https://docs.opencti.io/latest/usage/exploring-threats/)

MISP Galaxy 同样支持 threat-actor cluster 的 `synonyms`，并可按名称、同义词或 UUID 检索；但它也能用独立的 `similar` 关系和估计语言连接两个 cluster。这正说明“同义”与“相似”应是不同语义，不能都折叠为 alias。[MISP Threat Actor Intelligence Server](https://misp.github.io/threat-actor-intelligence-server/)

### 架构含义

OpenCTI Adapter 至少应区分：

- `canonicalAlias`：上游已经确认是同一实体的名称；
- `sourceLocalName`：某个来源使用的原始名称；
- `possibleSameAs`：尚未接受的实体解析候选；
- `similarTo`：行为或资料相似，但没有 same-as 语义；
- `distinctFrom`：已确认不能合并；
- `classificationAmbiguity`：该名称可能代表 Actor、Intrusion Set、Campaign 或 Operation。

只有 `canonicalAlias` 可直接用于 OpenCTI 精确 upsert。其他状态需要保持为可逆的 Resolution Hypothesis 或关系。

## 2. 自动 dedup 的真实边界

OpenCTI 自动去重是**基于明确字段的确定性匹配**，不是通用相似度或行为归因算法：

- Threat Actor、Intrusion Set、Campaign 等多类实体按 `name OR alias`；
- Relationship 按类型、source、target 和 start/stop time 窗口；
- STIX Cyber Observables 按 STIX ID-contributing properties；
- 命中现有实体后，incoming creation 可能更新现有字段，更新策略受 confidence 和 quality 影响。[OpenCTI：Deduplication](https://docs.opencti.io/latest/usage/deduplication/), [OpenCTI：Data processing](https://docs.opencti.io/latest/reference/data-processing/)

STIX 2.1 的跨生产者确定性 ID 规范主要针对 SCO。其他 STIX Domain Objects 和 Relationships 通常使用 UUIDv4；因此 STIX 标准本身并不会让两个生产者创建的 Threat Actor 自动获得同一 ID。[OASIS STIX 2.1：Object IDs and References](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#object-ids-and-references)

STIX 的 `duplicate-of` 允许两个同类型对象保留各自身份，同时声明它们在语义上重复；规范明确不规定谁是副本，也不规定 consumer 必须采取什么合并动作。这比立即 merge 更适合承载尚需治理的跨来源重复判断。[OASIS STIX 2.1：Common Relationships](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#common-relationships)

### 风险

`name OR alias` 对已治理词表很有效，但如果低质量来源错误地声明一个 alias，它可能触发过早融合。OpenCTI 的故障排查文档也承认：一个 incoming entity 解析到太多实体时，平台无法自动决定，需要检查 bundle 或平台数据。[OpenCTI：Troubleshooting](https://docs.opencti.io/latest/deployment/advanced/troubleshooting/)

因此，对高歧义 Actor / Intrusion Set 数据，自动 dedup 应只处理稳定键；新增 alias、跨来源 same-as 和分类变更应先经过 Analyst Workbench、Draft 或 CTI-RAG 的受控提案。OpenCTI Workbench 本身就是在正式入库前让分析员检查 connector 识别出的实体，验证前内容不会写入知识库。[OpenCTI：Analyst workbench](https://docs.opencti.io/latest/usage/workbench/)

## 3. 人工 merge：支持关系连续性，但不是可逆实体解析

OpenCTI manual merge 只允许同类型实体，每次最多四个。操作者选择主实体；主实体保留关键字段，其他实体的名称成为 alias，原有关系被重新锚定到合并实体，未来信息也进入合并后的实体。[OpenCTI：Merging and de-duplication](https://docs.opencti.io/latest/administration/merging/)

但官方文档同时明确：

- merge **不可逆**；
- 非主实体的 description 等字段可能丢失；
- 必须在执行前谨慎验证。[OpenCTI：Merging and de-duplication](https://docs.opencti.io/latest/administration/merging/)

所以，“关系不丢失”只表示图连接会被重建到主实体，并不等于：

- 所有源字段都可恢复；
- 原来的竞争性身份解释仍然存在；
- 后续发现误合并时可以拆分；
- merge 本身证明了同一行为主体。

### 架构含义

在 CTI-RAG 风险层级中，OpenCTI merge 应属于高风险、人工授权的不可逆操作，而不是 Agent 的普通写工具。Agent 可以生成 `EntityResolutionProposal`，包含支持、反证、来源名称、分类差异和预计影响；真正 merge 只能在明确复核后执行。即使上游已经 merge，I&E 也应尽量保留 source-local identifiers、原始名称、来源文档、历史映射和 merge receipt，避免 Adapter 只输出一个无法解释的 canonical Actor。

## 4. 高度相似行为与观测活动：先建 Intrusion Set，不直接统一 Actor

STIX 的成熟建模选择是把技术/行动聚类与真实行为主体分开：

- `Observed Data` 只表示原始观测，没有关于其意义的 intelligence assertion；
- `Sighting` 表示某 intelligence entity 被观察到，并可引用导致该判断的 Observed Data；
- `Intrusion Set` 是一组具有共同属性的对抗行为和资源，可在真实 Threat Actor 未知时承载新活动；
- `Threat Actor` 是实际个人、群体或组织；
- Intrusion Set 通过独立的 `attributed-to` Relationship 连接 Threat Actor。[OASIS STIX 2.1：Observed Data](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#observed-data), [OASIS STIX 2.1：Intrusion Set](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#intrusion-set), [OASIS STIX 2.1：Threat Actor](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#threat-actor)

STIX 还明确说明，分析员对 Intrusion Set 背后 Threat Actor 的归因精度可能不同；`originates-from` Location 不应被用来定义归因。Intrusion Set 可以 `uses` 相同 malware、tool、infrastructure 或 attack pattern，但这些关系描述活动特征，不自动证明两个 Intrusion Set 或 Threat Actor 相同。[OASIS STIX 2.1：Intrusion Set relationships](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#intrusion-set)

OpenCTI 官方 Threats 文档采用同样区分，并承认如何依据差异与演化划分 Intrusion Sets 在 CTI 社区仍有争议。因此，“行为高度相似”有成熟的数据形状，但没有成熟到可由平台无条件自动合并的判定规则。[OpenCTI：Threats](https://docs.opencti.io/latest/usage/exploring-threats/)

### 推荐的问题分解

遇到 Actor 同名异义或异名同义时，不应直接询问“是不是同一个 Actor”，而应分别评估：

1. 这些 observables 是否是同一个技术对象或同一次 observation；
2. 这些 observations 是否属于同一 Campaign；
3. 多个 Campaign 是否属于同一 Intrusion Set；
4. 多个 source-local actor labels 是否只是同一 Intrusion Set 的不同名称；
5. 该 Intrusion Set 是否 attributed-to 某 Threat Actor；
6. 多个 Threat Actors 是否是协作、承包、赞助、共享基础设施，还是 same-as。

每一步的候选、依据和反证都可能不同。不能因为第 2 或第 3 步成立，就机械推出第 5 或第 6 步。

## 5. Ambiguity：标准支持保留分歧，但不替分析员求解

STIX 已提供以下可复用表达能力：

- Relationship 本身是可版本化对象，带 `created_by_ref`、confidence、external references、description 和时间范围；`attributed-to` 可以成为一个独立、可溯源的断言。[OASIS STIX 2.1：Relationship](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#relationship)
- `confidence` 表示对象创建者对其数据正确性的信心，范围 0–100；没有该字段表示 confidence 未指定。它不是多个候选之间的概率分布。[OASIS STIX 2.1：Common Properties](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#common-properties)
- `Opinion` 允许另一生产者对现有 STIX Object 表达同意或反对并解释原因；规范明确 Opinion 是主观的，也不规定 consumer 应如何解释和合并这些意见。[OASIS STIX 2.1：Opinion](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#opinion)
- `Grouping` 可以把共享上下文的对象放入持续分析或正在进行的调查中，而不宣称它们已经成熟为正式 intelligence product。[OASIS STIX 2.1：Grouping](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#grouping)
- `duplicate-of`、`derived-from` 和 `related-to` 分别表达语义重复、派生谱系和非特定关联；它们不要求物理合并。[OASIS STIX 2.1：Common Relationships](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#common-relationships)

这些对象足以让 OpenCTI / Adapter 保存多个竞争性 `attributed-to` 关系、反对意见、来源和置信度，但标准没有定义：

- 哪些候选是互斥、可并存或角色互补；
- 如何比较同一证据对多个候选的支持或反证；
- 如何处理 shared infrastructure、compromised infrastructure、contractor、actor handoff 和 false flag；
- 如何按来源独立性折叠循环转载；
- 何时选出 Leading Hypothesis，何时必须 `no_leading_hypothesis`。

这些正是 Case/Workspace 的 ACH 与判断层，而不是 OpenCTI schema 或 dedup 层。

## 6. Source lineage 和 data fusion：部分成熟，不能从图数量推断独立佐证

### 已有能力

STIX 的 `created_by_ref` 指向创建 STIX Object 的 Identity；`external_references` 指向 STIX 外部材料；`Report` 包含一组有共同叙事上下文的对象；`derived-from` 表示一个对象的信息基于另一个对象。[OASIS STIX 2.1：Object Creator](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#object-creator), [OASIS STIX 2.1：Common Relationships](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html#common-relationships)

OpenCTI 把 Report 视为外部文档或 intelligence production 的容器，并建议通过 Report 和 External Reference 把结构化知识追溯到来源。它还把 author、external reference 等嵌套 STIX 属性建模为图中的节点和关系，便于 pivot。[OpenCTI：Analysis](https://docs.opencti.io/latest/usage/exploring-analysis/), [OpenCTI：Nested references and objects](https://docs.opencti.io/latest/usage/nested/)

OpenCTI 将 Source Reliability 与 Information Confidence 区分：Reliability 评价来源的历史/能力，Confidence 评价具体信息的可信度和质量；但为了易用性，OpenCTI 也明确选择把 information credibility 融合进通用 confidence 概念。[OpenCTI：Reliability and Confidence](https://docs.opencti.io/latest/usage/reliability-confidence/)

### 尚未自动解决的部分

`created_by_ref` 是对象创建者，不必然是最初信息来源。代理、connector、TAXII 转发者或二次报告可能创建新对象。Report membership 和 External Reference 能保留来源指针，但不能自动证明两个报告相互独立。

OpenCTI 对 Relationship 的去重默认按 type/source/target/time；配置中的 `relations_deduplication:created_by_based` 默认是 `false`，只有显式启用才把 author 纳入重复判断。[OpenCTI：Configuration](https://docs.opencti.io/latest/deployment/configuration/)

因此：

- 相同 graph edge 的数量不等于独立 source 数量；
- 一个 deduplicated edge 可能汇聚多个输入路径；
- 多个独立对象也可能都引用同一个上游报告；
- inference、导出、MISP 转换、再次导入可能制造表面上的“多来源”；
- confidence 高低不能替代 source dependency 分析。

### Adapter 至少应保留的 lineage 数据

- OpenCTI internal ID、standard/STIX ID 和 source-local ID；
- object/relationship 的 `created_by_ref`、technical creator / connector identity；
- 所属 Report、Grouping、Case 和原始 source artifact；
- External References；
- `derived-from`、`duplicate-of` 和 imported-from / re-export 路径；
- inferred 标记、推理 rule、输入 edges；
- merge receipt、原实体 IDs 和 aliases；
- confidence、source reliability、时间和版本；
- lineage dependency 状态：independent、shared-root、derived、cycle、unknown。

OpenCTI 可以提供大部分原始指针，但 `independent/shared-root/cycle/unknown` 仍需要 I&E 的 lineage 分析产生，不能让 LLM 或 edge count 自由判断。

## 7. OpenCTI inference 不是真正的自动 Actor attribution

OpenCTI inference engine 持续扫描已有关系，并根据预定义逻辑规则创建新的关系。推断关系在图中有明显的 inferred 标记；关闭规则会删除该规则创建的对象和关系。[OpenCTI：Inferences and reasoning](https://docs.opencti.io/latest/usage/inferences/), [OpenCTI：Rules engine](https://docs.opencti.io/latest/administration/reasoning/)

与归因有关的官方规则包括：

- **Attribution propagation**：A attributed-to B 且 B attributed-to C，则推导 A attributed-to C；
- **Usage propagation via attribution**：A uses B 且 A attributed-to C，则推导 C uses B；
- **Targeting propagation via attribution**：A attributed-to C 且 A targets B，则推导 C targets B；
- **Relation propagation via an observable**：同一 observable 关联两个实体时，只创建通用 `related-to` 关系。[OpenCTI：Rules engine](https://docs.opencti.io/latest/administration/reasoning/)

这些规则都以**已有 attribution 或 relation**为前提。它们不会从“两个 Actor 使用相似 TTP”“两个活动共享 IP”“恶意软件代码相似”等原始证据自主判定同一 Actor。准确说，OpenCTI 支持的是：

> 自动传播已经进入知识图谱的归因命题，而不是自动发现或证明行为主体归因。

推断关系也不是新的独立证据；它是输入关系和规则的派生产物。Adapter 必须把 inferred relationship、规则标识和输入 basis 投影出来，ACH lineage reducer 应将其与上游输入归为同一依赖链。

## 8. 对三个系统边界的建议

### Intelligence & Evidence Platform

负责：

- 保存 source-local Actor / Intrusion Set / Campaign 名称和类型；
- 保留 Reports、External References、connectors、STIX IDs、版本和 provenance；
- 提供精确 observable 规范化；
- 输出 alias、duplicate、similar、related、merge history 和 lineage dependency；
- 保存可逆 `EntityResolutionHypothesis` 与 `ActivityClusteringHypothesis`；
- 将 OpenCTI inferred edge 明确标记为 derived，而非 primary evidence。

### Case Management Domain

负责：

- 决定哪些 Resolution Decision、Activity Cluster 和 Attribution Assessment 被 Case 接受；
- 保存竞争候选、角色、多 Actor 结构、反证、推翻条件和人工修正；
- 将不可逆 OpenCTI merge 视为需人工授权的高风险外部动作；
- 保存 accepted、challenged、superseded 和 rejected 的不可变判断历史。

### Agent Investigation Workspace

负责：

- 在任务范围内提出结构化 Resolution / Clustering / Attribution Hypotheses；
- 使用同一 Evidence Basis 比较候选；
- 明确区分 alias/same-as、behavioral similarity、activity membership 和 actor attribution；
- 生成 R2 Provisional Assessment 与 change indicators；
- 不把 OpenCTI canonical entity、merge 或 inferred edge当成已证实归因；
- 不直接执行 merge，不自行声明 source independence。

## 9. 需要进入 Workspace Projection 的最小边界信息

为了让 LLM 正确推理，但不复制完整 OpenCTI schema，Actor 或 Intrusion Set 相关 projection 至少应提供：

```text
EntityCandidate
  stableRef
  modeledType                  # ThreatActor | IntrusionSet | Campaign | Unknown
  canonicalName
  sourceLocalNames[]
  acceptedAliases[]
  possibleSameAs[]
  similarTo[]
  distinctFrom[]
  classificationAmbiguities[]
  mergeHistory[]

RelationshipAssertion
  relationshipRef
  type                         # attributed-to | uses | targets | related-to | ...
  sourceRef
  targetRef
  sourceArtifactRefs[]
  createdBy
  confidence
  timeRange
  inferred
  inferenceBasisRefs[]
  lineageGroup
  dependencyStatus
  status                       # asserted | challenged | superseded | rejected
```

这些字段是 Workspace 稳定语义，不要求 Adapter 暴露 OpenCTI 全部内部 DTO。具体 OpenCTI schema 选择、字段映射和 API 调用仍属于 CTI Domain / Adapter 详细设计。

## 10. 对当前 grill 的直接回答

用户的判断部分正确：OpenCTI、STIX 和 MISP 已有成熟方案处理 aliases、结构化活动、图关系、来源、confidence、异议和人工合并。但“解决”分两个层次：

- **成熟的数据表示与治理机制**：已经有，可以高度复用，不应重新设计 STIX/OpenCTI 的基本对象。
- **自动判定两个 Actor 名称是否相同、两个活动是否同簇、谁实施了活动**：没有被平台普遍解决，且不应由 dedup、merge 或 inference 偷偷完成。

对 CTI-RAG 最重要的复用不是“相信 OpenCTI 已完成 actor fusion”，而是沿用成熟模型的分层：

```text
source-local identity
  -> reversible entity resolution
  -> activity / intrusion-set clustering
  -> sourced attributed-to assertions
  -> competing attribution hypotheses
  -> provisional assessment
  -> human-accepted Case judgment
```

这条边界同时解释了为什么 Leading Hypothesis 不能只有一个不分类的 Actor 名称：它至少必须绑定到明确的 hypothesis kind（entity resolution、activity clustering 或 actor attribution）和 assessment scope。否则 LLM 可能把“名称可能相同”“行为很像”和“由同一 Actor 实施”错误地压成同一个结论。

## 官方一手资料

- [OpenCTI Deduplication](https://docs.opencti.io/latest/usage/deduplication/)
- [OpenCTI Merging and de-duplication](https://docs.opencti.io/latest/administration/merging/)
- [OpenCTI Threats](https://docs.opencti.io/latest/usage/exploring-threats/)
- [OpenCTI Reliability and Confidence](https://docs.opencti.io/latest/usage/reliability-confidence/)
- [OpenCTI Analyst Workbench](https://docs.opencti.io/latest/usage/workbench/)
- [OpenCTI Analysis and source containers](https://docs.opencti.io/latest/usage/exploring-analysis/)
- [OpenCTI Inferences and reasoning](https://docs.opencti.io/latest/usage/inferences/)
- [OpenCTI Rules engine](https://docs.opencti.io/latest/administration/reasoning/)
- [OpenCTI Configuration](https://docs.opencti.io/latest/deployment/configuration/)
- [OASIS STIX 2.1 Errata 01](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html)
- [MISP Threat Actor Intelligence Server](https://misp.github.io/threat-actor-intelligence-server/)
- [MISP Galaxies to STIX mapping](https://misp.github.io/misp-stix/documentation/misp_galaxies_to_stix20.html)
