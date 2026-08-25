# OpenCTI 对旧 Raw 数据、Connector、Data Fuser 与现有平台的适用性

Status: primary-source research and non-normative POC recommendation.

Research date: 2026-07-23.

## 结论

建议采用 OpenCTI，但不是把现有系统整体替换成一个“大一统平台”：

- **让 OpenCTI 成为 CTI 当前知识图谱、Connector、Workbench、标记/访问控制、人工浏览和图查询的主平台。**
- **保留旧 raw 数据为不可变原始资料和可回放迁移源。** 不要在验收前删除、改写或只保留 OpenCTI 中的规范化对象。
- **保留 I&E/RAG sidecar。** 它负责精确 Source Capture、内容摘要、解析/分段/嵌入版本、Source Span、Lineage、Retrieval Receipt 和可复现实证；OpenCTI 不应被假定为已经提供这些 Agent/RAG 证明。
- **不要部署一个与 OpenCTI 并列的第二套可编辑图谱。** 如果旧项目的 “Data Fuser” 是自研组件，应把它收窄为导入前的确定性映射、可逆候选消歧和 lineage 生成器，通过 `EXTERNAL_IMPORT` Connector 向 OpenCTI 发布 STIX 2.1；它不能自动决定不可逆 merge、归因结论或 Case 证据角色。
- **先做隔离 POC，再决定迁移。** POC 通过后才逐源迁移；不做一次性全量切换。

这与仓库已接受的 [ADR 0013](../adr/0013-use-opencti-as-ie-primary-infrastructure.md) 和 [ADR 0016](../adr/0016-keep-rag-ownership-local-and-admit-retrieval-deterministically.md) 一致：OpenCTI 是主 CTI 基础设施，I&E 是派生深模块，Workspace/Case Management 继续拥有任务选择和正式判断。

## 1. Connector 应该怎样使用

### 1.1 官方 Connector 类型

OpenCTI 官方把 Connector 定义为平台旁运行的长期服务。开发文档列出六种类型：[官方 Connector 开发文档](https://docs.opencti.io/latest/development/connectors/)。

| 类型 | 官方用途 | 对旧 raw 数据的适用性 |
| --- | --- | --- |
| `EXTERNAL_IMPORT` | 周期性读取外部情报源/平台，转换为 STIX 2.1 并导入 | **长期和批量迁移的首选。** 适合数据库、目录、对象存储、专有 JSON/API，以及需要 checkpoint、重试和持续增量的旧数据 |
| `INTERNAL_IMPORT_FILE` | 从文件批量导入知识 | 适合用户上传 STIX、MISP、YARA、PDF/文本等文件；适合抽样和人工审核，不是任意旧数据库的通用 ETL |
| `INTERNAL_ANALYSIS` | 把文件或实体字段中的非结构化内容映射到已有实体 | 适合文档解析/实体识别，不是源数据搬迁控制面 |
| `INTERNAL_ENRICHMENT` | 对已有对象查询外部服务并增加知识 | 只用于对象已进入 OpenCTI 后的补充，不应用来做初始全量导入 |
| `INTERNAL_EXPORT_FILE` | 批量导出为 STIX/CSV 等 | 用于迁出/备份/交换，不用于旧数据入库 |
| `STREAM` | 消费 OpenCTI live stream 并推送到 SIEM/XDR 等；部分实现可双向 | 适合持续下游分发或双向同步，不适合作为一次性 raw 迁移的默认选择 |

官方部署文档将用户视角归纳为 Import、Enrichment、Stream、Import files、Export files，并说明 Import Connector 从外部服务取数、生成 STIX 2.1 bundle，再由 workers 导入：[官方 Connector 部署文档](https://docs.opencti.io/latest/deployment/connectors/)。

### 1.2 旧 raw 数据的路由

| 旧数据形态 | 推荐路径 | 关键限制 |
| --- | --- | --- |
| 已是 STIX 2.1 JSON/XML | 先用 `ImportFileStix` 做小样；大批量/反复增量改用 `EXTERNAL_IMPORT` | `ImportFileStix` 不替你做实体识别，输入 bundle 定义什么就导什么 |
| MISP JSON | `ImportFileMISP`；持续 MISP 实例用官方 MISP external-import Connector | 需要保留原 MISP event/source 身份，不能把重复 feed 数当独立佐证 |
| CSV/TSV | 建立版本化 CSV Mapper，小样验证后再批量；持续 URL feed 可用 CSV Feed | CSV Mapper **直接写入知识库，不经过 Workbench**，因此错误映射风险更高 |
| PDF、TXT、HTML、Markdown | `ImportDocument` -> Analyst Workbench -> 人工验证 | 官方明确解析可能错误或产生 unknown entities；它不是可信的精确引用/页码/Span 证明 |
| YARA | `ImportFileYARA` | 只适合对应规则文件 |
| 任意 JSON、关系数据库、目录树、对象存储 | 自研 `EXTERNAL_IMPORT` Connector：读取 -> 验证 -> 映射为 STIX 2.1 -> `send_stix2_bundle` | 不应让 Connector 直接调用 API 创建对象；官方推荐通过 worker 发送 STIX bundle |
| 只需定期读取的公开 JSON/CSV/RSS/TAXII URL | 优先评估 OpenCTI 内建 Feed/TAXII Push，而不是先写 Connector | Feed 有自己的调度和格式边界；不能代替专有 schema 转换 |

文件导入的官方清单、Workbench 行为和 CSV 例外见 [Import from files](https://docs.opencti.io/latest/usage/import-files/)；Workbench 在验证前只保存草稿，验证后才写知识库，见 [Analyst workbench](https://docs.opencti.io/latest/usage/workbench/)；自动导入还支持 Connector、Stream、TAXII、RSS、CSV、JSON，见 [Automated import](https://docs.opencti.io/latest/usage/import/getting-started/)。

### 1.3 自研导入 Connector 的边界

官方开发文档要求/建议：

- Connector 是独立长期进程，当前便利 SDK 是 Python `pycti`。
- 写入应使用 `OpenCTIConnectorHelper.send_stix2_bundle`，不要用 `helper.api` 直接创建对象。
- External import 和 Stream 自主按周期/持续运行；内部 analysis/enrichment/import/export 由平台请求触发。
- 每个 Connector 都需要 `OPENCTI_URL`、`OPENCTI_TOKEN`、唯一 `CONNECTOR_ID`、类型、名称、scope 和日志级别。

每个 Connector 应使用独立服务用户/token；普通 import/enrichment/stream 使用 Connector 角色，而 internal export 因用户模拟和防止数据泄漏需要管理员 bypass。来源：[官方 Connector 部署文档](https://docs.opencti.io/latest/deployment/connectors/)。

对旧 raw 导入，建议 Connector 的自有配置至少包括：

```text
sourceProfileId
mappingProfileVersion
sourceRoot / sourceEndpoint
checkpointStore
batchSize
allowedObjectTypes[]
defaultCreatedBy
defaultMarkings[]
confidenceCeiling
dryRun
deadLetterPath
maxAttempts
wholeRunBudget
```

这些是本项目的 POC 建议，不是 OpenCTI 官方已定义的统一 Connector 配置。每个官方 Connector 的额外参数由其自身实现决定。

## 2. “Data Fuser” 的事实核验和建议边界

### 2.1 当前没有可核实的官方 OpenCTI “Data Fuser” 组件

截至研究日：

- OpenCTI 官方 Connector 分类只有 `EXTERNAL_IMPORT`、`INTERNAL_ANALYSIS`、`INTERNAL_ENRICHMENT`、`INTERNAL_IMPORT_FILE`、`INTERNAL_EXPORT_FILE` 和 `STREAM`；没有 `DATA_FUSER` 类型：[官方 Connector 开发文档](https://docs.opencti.io/latest/development/connectors/)。
- 官方平台文档将数据处理能力描述为 workers、Connectors、Workbench、dedup/upsert、manual merge 和 inference rules，没有给出名为 “Data Fuser” 的部署或配置合同。
- 对官方 OpenCTI master `011ace9ce03edaf97e18a0039e8fe89f58e38b8d` 的 docs/frontend/backend 检查，以及官方 Connectors master `7c371f742cd0832f7b07ba35f00308e8c2a79ade` 的源码检查，没有找到一个名为 `Data Fuser`/`data-fusion` 的产品组件。官方仓库入口：[OpenCTI](https://github.com/OpenCTI-Platform/opencti/tree/011ace9ce03edaf97e18a0039e8fe89f58e38b8d)、[Connectors](https://github.com/OpenCTI-Platform/connectors/tree/7c371f742cd0832f7b07ba35f00308e8c2a79ade)。

因此，不能给出“官方 Data Fuser”的镜像、环境变量或部署步骤。这个名称更可能是旧项目的自研模块或对 data fusion 能力的泛称。若要确认其**当前**作用、配置和运行状态，下一项必要输入是旧项目仓库路径、镜像名或 compose/service 名。

### 2.2 如果它是旧项目自研模块，应保留什么

可以保留：

- raw schema 校验、格式规范化和确定性 STIX 映射；
- source-local identity、外部引用、来源对象、采集时间、原始哈希和 mapping version；
- 可逆的 `same-as`/alias/相似性/聚类候选；
- Source Lineage 和疑似转载/依赖关系；
- checkpoint、dead-letter、重放和逐源对账；
- 生成 STIX 2.1 bundle 并通过一个受控 `EXTERNAL_IMPORT` Connector 发布。

不能让它拥有：

- 第二套可编辑 CTI 图谱或 Connector 控制面；
- 自动、不可逆 OpenCTI merge；
- 把名称相同、行为相似或重复报道直接提升为同一 Threat Actor；
- 把图边数量当成独立佐证；
- 决定 Case 的 Evidence Reference、正式归因或被接受的结论；
- 直接选择凭据、生产队列、OpenCTI 管理策略或绕过 actor/marking。

### 2.3 OpenCTI 内建“融合”能力的真实限制

OpenCTI 会为实体和关系计算确定性 ID，在创建时 deduplicate/upsert；实体的 contributing properties 经常包含 `name OR alias`，关系则按 type/source/target 和时间窗口去重：[Deduplication](https://docs.opencti.io/latest/usage/deduplication/)。这很有用，但它是平台一致性规则，不是可靠的跨来源实体解析判决。

手工 merge：

- 只允许相同类型；
- 一次最多四个实体；
- 不可逆；
- 非主实体的 description 等字段可能丢失；
- 关系会迁移到主实体。

来源：[Merging and de-duplication](https://docs.opencti.io/latest/administration/merging/)。

Inference engine 只运行预定义规则，从已有关系推导新关系；推理边可在 UI 中识别。管理员启用规则会先扫描全库，然后持续运行；停用会删除规则生成的对象/关系。官方也警告规则可能生成大量对象，而且用户不能自行添加任意规则：[Inferences](https://docs.opencti.io/latest/usage/inferences/)、[Rules engine](https://docs.opencti.io/latest/administration/reasoning/)。

因此 POC 初期应：

- 关闭非必要 inference rules；
- 禁止自动 merge；
- 将 ambiguity 输出为候选或 review queue；
- 先验证 source-local identity 和 provenance，再谈跨源统一。

## 3. OpenCTI 是否应该替代现有平台

### 3.1 应该替代/统一的部分

OpenCTI 适合成为以下能力的主平台：

- STIX/OpenCTI 当前实体、关系和图查询；
- Connector/Feed 导入和 worker 异步写入；
- analyst Workbench 和人工图谱维护；
- markings、RBAC、confidence 和来源作者展示；
- dedup/upsert、受控 merge、预定义 inference；
- CTI 浏览、可视化、Dashboard、GraphQL 和外部 stream/export。

官方项目目标就是用 STIX 2 schema 结构化、存储、组织和可视化技术及非技术 CTI，并保留 primary source、关系、first/last seen、confidence 等信息：[OpenCTI 官方仓库](https://github.com/OpenCTI-Platform/opencti/tree/011ace9ce03edaf97e18a0039e8fe89f58e38b8d)。

### 3.2 不应该替代的部分

OpenCTI 不应被当成以下能力的唯一实现：

- 不可变 raw archive、原始字节哈希和法律/许可留存；
- 精确 Resource Version、parser/chunker/embedding/index generation；
- PDF 页码/坐标、Source Span 和可重复引用；
- RAG 候选集、排序版本、完整覆盖声明和 Retrieval Receipt；
- 完整 prompt/model 输入证明；
- source independence/lineage 的可审计判定；
- Case 的正式证据角色、竞争性假设和接受/拒绝历史；
- 旧系统业务流程在未逐项核验前的全部替代。

OpenCTI 的文件全文搜索在当前官方文档中属于 Enterprise Edition；即使启用，它也只是平台搜索能力，不等于本项目要求的版本化 RAG 和精确检索证明：[Search for knowledge](https://docs.opencti.io/7.260529.0/usage/search/)。

### 3.3 推荐目标形态

```text
旧 raw（只读、带 manifest/hash）
  -> source profile + mapping/fusion adapter
  -> EXTERNAL_IMPORT / file import
  -> OpenCTI 当前 STIX 图、文件、访问控制、Connector/work
  -> I&E exact capture / derivation / lineage / retrieval receipt
  -> Workspace Working Set
  -> Case 中的正式 Evidence/Assessment
```

这是渐进替代：

1. OpenCTI 先替代现有“可编辑 CTI 图谱与导入控制面”。
2. 原 raw 和现有系统保持只读并行，直到对账和回放验收完成。
3. I&E/RAG 通过 OpenCTI exact resource 逐步切换，不让模型直接读取任意 raw 或操作 Connector。
4. 最后按能力而不是按服务器决定哪些旧服务可以退役。

## 4. 可执行 POC

### Phase 0：两天内完成迁移清单

对旧 raw 生成不可变 inventory：

- 相对路径/源记录 ID、格式、字节数、SHA-256；
- 来源、采集时间、许可/保留/模型披露许可；
- schema/version、预计对象类型、现有主键和关系键；
- 是否为原始来源、转载、派生或未知依赖；
- 敏感标记和预期读者；
- 预期迁移路径：STIX/MISP/CSV/document/custom Connector。

输出一张按 source profile 汇总的 count/bytes/hash manifest。没有这一步，不启动全量导入。

### Phase 1：隔离环境

1. 使用官方 Docker 仓库部署固定版本的 OpenCTI CE；不要使用浮动 `latest` 作为可重复 POC 基线：[官方安装文档](https://docs.opencti.io/latest/deployment/installation/)、[官方 Docker 仓库](https://github.com/OpenCTI-Platform/docker)。
2. 部署 OpenCTI、至少一个 worker，以及 Elasticsearch/OpenSearch、Redis、RabbitMQ、S3/MinIO。官方生产最小资源基线包括 OpenCTI Core 2 CPU/8 GB RAM、Elasticsearch/OpenSearch 2 CPU/8 GB RAM，并为各持久依赖准备独立磁盘；POC 应记录实际配置，不把最小值当容量保证：[Deployment overview](https://docs.opencti.io/latest/deployment/overview/)。
3. 启用 `ImportFileStix`、`ImportFileMISP`、`ImportFileYARA` 和 `ImportDocument` 中实际需要的子集。
4. 每个 Connector 创建独立服务用户/token，只给 Connector 角色；记录 token owner、scope、创建时间和轮换方法。
5. 备份 persistent volumes，保留一键清空重建的 POC 环境。
6. Integration Manager 不是 POC 必需项。它从 OpenCTI 6.8.17 开始提供，部署/管理 Connector 需要 Enterprise Edition；没有 EE 时 catalog 只读：[Integration Manager](https://docs.opencti.io/latest/deployment/integration-manager/)。

### Phase 2：代表性样本，不做全量

从 inventory 选择：

- 每种主要格式至少一组；
- 至少两个可能重复/转载的来源；
- 至少一个名称冲突或 alias 场景；
- 至少一个 marking/不可见场景；
- 至少一个失败/损坏输入；
- 总量先控制在 500–2,000 个源记录或 1–5 GB 文件内，以较小者为准。

对映射先做 dry-run，输出：

- 预计 STIX object/relationship 数；
- source-local ID -> STIX/OpenCTI identity 映射；
- 丢弃、降级、unknown 和 ambiguity 清单；
- 原始 hash、mapping version 和 created-by/marking/confidence 分配。

### Phase 3：两条导入路径

**路径 A：现成格式**

1. STIX/MISP/document 文件上传到 Data import。
2. STIX/MISP/document 生成 Workbench 后逐项抽样、修订并验证。
3. CSV 使用版本化 CSV Mapper；因为它绕过 Workbench，只先导入隔离租户/实例的小样。

**路径 B：专有 raw**

1. 建立一个最小 `EXTERNAL_IMPORT` Connector。
2. 按 source profile 顺序读数，用 checkpoint 保证可恢复。
3. 每批产生确定性 STIX 2.1 bundle，通过 `send_stix2_bundle` 进入 worker。
4. 将不合法/超预算/无法映射的项目写入 dead-letter，不静默丢弃。
5. work 完成后核对源计数、bundle 计数、成功/失败和平台对象/关系数。
6. 用相同 mapping version 重跑完全相同样本，验证幂等性。

### Phase 4：图谱、融合和 RAG 验证

1. 验证 10–20 个真实分析查询：source -> report -> observable/indicator -> malware/tool/attack-pattern -> actor/campaign。
2. 检查每个结论是否能回到 Report/External Reference/created-by，而不是只看到“悬空”实体。
3. 检查名称/alias 冲突没有错误合并；所有 ambiguity 留在 review 状态。
4. 保持 merge 和非必要 inference 关闭，记录若启用某规则会新增多少边。
5. 从一个 OpenCTI exact resource 执行本项目 I&E 目标路径：capture -> span/segment -> receipt/capsule；验证 OpenCTI 当前图与不可变 RAG 证据分工。
6. 对一个不可见/marking 不满足的用户执行相同查询，确认不泄露对象、计数、正文或图拓扑。

### Phase 5：并行运行和退出决定

1. 旧系统只读并行 2–4 周；每日对账新增、修改、失败和延迟。
2. 记录 Connector queue 深度、worker 吞吐、work terminal、重试和 dead-letter。
3. 完成一次 Connector/worker 重启和一次 OpenCTI 恢复演练。
4. 只在所有验收项通过后，将该 source profile 的 OpenCTI 路径设为主读。
5. 旧 raw 永不因 POC 通过而删除；旧图/ETL 服务按能力清单逐项退役。

## 5. POC 验收指标

以下是建议的项目门槛，不是 OpenCTI 官方 SLA：

| 维度 | 通过条件 |
| --- | --- |
| Inventory | 样本 100% 有 source ID、格式、大小、SHA-256、来源、采集时间、许可/marking 和 mapping profile |
| 导入对账 | 输入、成功、拒绝、dead-letter 数 100% 闭合；无静默丢弃 |
| 映射正确性 | 金标样本的实体类型/关键字段/关系 precision ≥ 98%；严重错误（错误 Actor 合并、错误归因）为 0 |
| 幂等 | 同一源、同一 mapping version 重跑后新增逻辑实体/关系为 0；允许 work/observation 日志增加 |
| Provenance | 100% 被抽样的知识可追到 source resource/Report/External Reference 和 raw hash |
| 消歧 | 冲突样本 100% 不自动不可逆 merge；候选、依据和人工处置可导出 |
| 图查询 | 预先冻结的 10–20 条真实查询中 ≥ 90% 在约定响应时间内得到正确、可溯源结果 |
| 访问控制 | 正向和反向 marking/RBAC 用例 100% 通过；隐藏资源不泄漏正文、ID、计数或关系拓扑 |
| 可恢复性 | Connector/worker 重启后从 checkpoint 恢复，无重复逻辑对象；失败批可定向重放 |
| 性能 | 在 POC 硬件上达到事先约定的持续 records/s 和 queue-drain 时间；记录 P50/P95，不使用未经测量的官方容量假设 |
| RAG 证据 | 选定 exact resource 的 capture/hash/span/segment/receipt 可重复验证；OpenCTI 更新后历史 capture 不被静默改写 |
| 回滚 | 能从快照重建 POC，旧 raw manifest/hash 保持不变 |

## 6. Go / No-Go

**Go：**

- 专有 raw 可以稳定映射为 STIX/OpenCTI 对象且 provenance 完整；
- 幂等、访问控制、重启恢复和对账通过；
- 图查询明显减少现有重复图/ETL 维护；
- I&E sidecar 能补足精确 capture、lineage 和 RAG receipt；
- Data Fuser 被收窄成 Adapter/候选生成器，而非第二图谱或不可逆判断者。

**No-Go 或继续并行：**

- 主要价值依赖全文/语义检索，但没有 EE 文件搜索或合格 I&E/RAG；
- 许可不允许把 raw 留存、派生或披露给模型；
- 旧 schema 无法保留 source-local identity、时间和来源；
- dedup 导致不可接受的错误汇聚；
- 需要 OpenCTI stock contract 未提供的强 Case revision、不可变审计或跨系统事务保证；
- 无法证明 Connector checkpoint、失败对账和恢复。

## Design disposition

采纳“OpenCTI 主图谱 + I&E/RAG sidecar + raw 不可变保留”的 POC。OpenCTI 可以替代现有 CTI 图谱和 Connector 控制面，但不能整体替代 raw evidence、可复现 RAG、正式 Case 判断或旧系统尚未盘点的业务能力。

下一步不是部署所谓官方 Data Fuser，而是取得旧项目的 Data Fuser 仓库/镜像/compose service，完成只读代码和配置审计；随后选一个 source profile，实现或改造一个受控 `EXTERNAL_IMPORT` Connector，按上述指标完成小规模 POC。
