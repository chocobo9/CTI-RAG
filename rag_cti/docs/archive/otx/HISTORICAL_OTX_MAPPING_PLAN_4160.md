# HISTORICAL — OTX actor-mapping 执行计划与数据核验（4,160 snapshot）

> Archive category: OTX actor-mapping audit plan.
>
> **Status: HISTORICAL / SUPERSEDED.** This audit plan does not describe the current
> OTX event-driven dataset. Current OTX authority starts at `docs/OTX_DOC_STATUS.md`.

本文件是 P0 审计结论，不是正式 mapping。它不生成 4,160 条最终 actor/IOC mapping，不修改现有 Fact/Support、RAG、Neo4j 或 GNN 行为。

## 1. Current evidence

实际检查范围如下：

- 论文 `docs/sp.pdf` 全文，重点核对方法、MISP TAG、人工 validation/augmentation 与后续 agreement analysis。
- 固定 run `data/raw/otx_collection_runs/routeA_20260704_policy_small_first`；人口只取 `checkpoint.json.completed_pulse_details`，并只通过同 run 的 `saved_files.jsonl` 解析 raw。
- `src/rag_cti/intermediate/otx_paper_mapping.py`、`src/rag_cti/intermediate/otx_downstream.py`、两个 build script、对应 tests/fixtures。
- 组员 `Mitraaaaa/GNN_APT` 固定 commit `8e82a6381c9555ba4e6ef05783e40eb6c7bd7770` 的 collector、graph exporter、trainer、config，以及本仓库已有 projection。
- 论文指定 MISP commit `42b5d56` 的公开 `clusters/threat-actor.json`。

执行了可重放审计脚本、Python compile、JSON assertions、仓库引用搜索、远端固定文件 hash 核验。机器事实见 `otx_mapping_audit.json`。

### “222 个结果”到底是什么

**VERIFIED：222 不是 actor 数、mapping 数、resolved 数或 parser 输出数。**它是 713 个非空 `payload.adversary` 字段出现值，按“文件中原始字符串、trim/大小写/Unicode 规范化之前”精确去重后的 distinct 数。

| 口径 | 数量 | 含义 |
|---|---:|---|
| 非空 adversary occurrences | 713 | Pulse 级字段出现次数 |
| raw-exact distinct | 222 | 这就是此前提到的 222 |
| trimmed distinct | 222 | trim 没有造成 collision；只有 1 个值本身受 trim 影响 |
| NFKC + trim + whitespace collapse + casefold distinct | 214 | 8 组大小写/空白归一 collision |
| 旧 prototype segment occurrences | 776 | 对 713 次字符串拆分后的片段出现次数，不是 distinct actor |
| 旧 prototype distinct segments | 253 | 拆分片段精确去重，不是 canonical actor |

96 个 raw-exact 值重复出现，126 个只出现一次；最高频值是 `APT41` 和 `BlindEagle`，各 42 次。重复值中，77 个对应多个 title，82 个对应多个 description，64 个对应多个 tag 集合，66 个对应多个 reference 集合。**UNRESOLVED：相同 raw string 在所有上下文中是否具有相同语义。**因此 P1 可立即开始，但安全主键必须先是 occurrence（`pulse_id + raw_ref + source_path`），不能未经审核把一条 raw-value decision 全局复用。

## 2. Reproduction boundary

| Paper step | Status | Current input | Semantic difference | Decision |
|---|---|---|---|---|
| 已带 vendor actor attribution 的 feed IOC 展平 | adapted | OTX Pulse、`adversary`、`indicators[]` | OTX claim 在 Pulse 级，不在每个 IOC 上 | 保留 event–actor claim 和 event–indicator observation，不生成强 actor–IOC edge |
| IOC normalization | adapted | 19 种 OTX raw indicator type | 当前不是七 feed agreement 分析 | 不作为 actor resolver 前置条件；需要时只做独立 projection |
| 固定 MISP TAG snapshot | reproducible | commit `42b5d56` 可公开取得 | repo 尚未 vendor 本地副本 | B1 必须固定原文件与 SHA-256 |
| actor object 的 value/name + synonyms 索引 | reproducible | 固定 MISP JSON | 工程可保留 UUID，论文使用内部编号 | 以 MISP UUID 为稳定 object key |
| exact unique / multiple objects / unmapped | reproducible | 经 P1 审核的同一 claim 输入 | 论文输入已是 actor label；OTX 先需 extraction | B1 只替换 resolver，不混入 extraction 差异 |
| shared alias 不级联 merge objects | reproducible | name→object 反向索引 | 无 | multiple objects 保持 ambiguous，不取第一个 |
| WIP 分类 | adapted | 单一 OTX snapshot | 论文还要求“只在七 feed 中一个出现”等条件 | 仅保留 WIP candidate/reason，不声称复现论文 WIP 结果 |
| CS/MS 84 对 validation | blocked_by_missing_input | 无版本化对照表 | 论文对冲突采取保守排除 | 不暗中并入 B1 |
| 50 actor 人工报告抽样验证 | not_reproducible | 缺抽样清单和逐条 annotation | 无法重放人工判断 | 只能复述方法，不能复现结果 |
| 对 unmapped actor 阅读最新 3–5 篇报告并增强 TAG | not_reproducible | 缺七 feed population、报告选择和人工决策 | augmented TAG 未完整公开 | 不猜测、不用 LLM 代替人工 augmentation |
| country 推导、agreement、VT disagreement | out_of_scope | 当前 OTX mapping 审计 | 属于 reconciliation 后分析 | 本任务不做 |

可以声称复现的是固定 MISP snapshot 上的 object/name/synonym exact reconciliation、unique/ambiguous/unmapped 和禁止 alias 级联 merge。不能声称复现 augmented TAG、论文最终 actor 总数或七 vendor agreement 结果。MISP 是 B1 必要输入。

**版本核验修正：**论文文字报告初始 TAG 有 855 actors；当前从指定 commit 路径取得的 JSON 实际有 856 个 `values` object，且 856 个都有 UUID/value。该差异原因目前 **UNRESOLVED**，所以可执行 B1 应记录实际 856 与文件 hash，不能硬编码 855。

## 3. OTX and prototype findings

### OTX 输入

- **VERIFIED：**4,160 个 completed Pulse 均有 raw，`missing_raw=0`；唯一 actor/adversary 相关 path 是 `payload.adversary`。类型为 4,144 string、16 null；3,431 个 string 为空，713 个非空。
- 字段是自由字符串，不是 actor object/list，也没有 per-indicator actor relation。它是当前 snapshot 最强的 source attribution-claim 输入，但不是事实正确性证明。
- `payload.indicators[]` 共 55,659,022 个 mapping-object observations，3,525 个 Pulse 有 indicators；actor 与 IOC 同 Pulse 只证明共同属于 report，不证明 actor uses/owns IOC。
- title/description/tags/references 中有大量 actor mention；这些不能自动回填 attribution。`query/query_actors` 只保留 discovery provenance，不能进入 resolver。

### 拆分规则核验

**VERIFIED：旧 prototype 的 `_split_actor_labels` 对 comma、slash、pipe、semicolon、单词 `and`、plus 做统一 regex split，然后使用 `set` 去重并排序。**它在 resolver 之前就会改变输入、丢失顺序和重复项。713 次非空原值由此成为 776 个 segment occurrences；该 776 只能重放历史 B0，不能作为 clean B1 或正式 mapping 输入。

当前 snapshot 中 delimiter raw-distinct counts 为 comma 16、slash 6、pipe 3、semicolon 0、plus 0、word `and` 2；对应 occurrence counts 为 17、6、7、0、0、3。这里的 delimiter 出现不等于可拆 actor list。

已对指定风险例实际调用两个 parser/resolver：

- `Shenzhen Haimaiyunxiang Media Co., Ltd.` 是 test fixture，不在 snapshot；旧 parser 拆成两段，v2 保持整体并标 non-actor。
- `TrojanDownloader:Win32/Nemucod` 在 snapshot 1 次；旧 parser 拆成两段，v2 标 `parse_ambiguous`，不进 resolver。
- `Kimsuky and Andariel` 在 snapshot 2 次；v2 得到两个 resolved actors，生成两个 actor claim relation，但 `Event.apt=null`。
- `APT32/OceanLotus` 是 fixture，不在 snapshot；v2 两个 alias collapse 到同一 APT32 object。
- `Cobalt Strike + campaign` 是 synthetic example，不在 snapshot；不能用它声称 snapshot error count。

**VERIFIED 下界：**至少 1 个 snapshot raw value（URL）被旧 parser 错拆成 6 个 unmapped resolver inputs。另有 5 个旧 parser 已拆开的真实值被 v2 标为 `parse_ambiguous`。**UNRESOLVED：完整误拆数以及修正后 retained/revoked/added/changed mapping 数**，因为还没有 occurrence-level reviewed extraction decisions。

### 当前 prototype / v2 的真实边界

- B0 resolver 使用 MITRE seed 的 casefold + whitespace-normalized exact name/alias；无 fuzzy，不自动创建 actor。423 个 segment occurrences exact-resolved，353 unmapped；40,065 个 flat IOC rows 是“resolved label × Pulse indicators”的共现展开，不是经验证的 actor-uses-IOC facts。
- v2 已能保存 raw claim、parse/resolution status、candidate IDs 和 raw refs，并能表达 multi/ambiguous/unmapped/non-actor；但其 parser 仍只是 preparation rules，不是 gold extraction。
- 旧 v2 `_actor_label_status` 会遮蔽 mixed case。重新按互斥 group 计算为：missing 3447、resolved_single 339、alias_collapsed 2、resolved_multi_actor 2、mixed_resolved_unresolved 6、taxonomy_ambiguous 31、unmapped 283、non_actor 45、parse_ambiguous 5。
- `resolved actor ≠ attribution 正确`；`mapping coverage ≠ accuracy`。`AttributedTo` 最多表达“OTX source 在 adversary 字段提出、随后被解析的 claim”，不得与 `InReport` 联结后自动推导强 `actor uses IOC`。

## 4. Consumer contract

组员训练入口不是 mapping 文件 loader，而是已填充的 Neo4j。固定代码读取 `Event`、`Domain`、`IP`、`URL`、`ASN` 节点和 `InReport`、`HostedOn`、`ResolvesTo`、`InGroup` 关系；监督标签来自单值 `Event.apt`，并要求该 string 在固定 `APT_TO_IDX` 中。Neo4j 主键/merge key 是 Pulse `Event.id`、IOC normalized `value`、ASN `number`。

当前合同结论：

- 没有 Actor node、AttributedTo 或 `actor_label_claims.jsonl` 的消费逻辑；本仓库也没有现成 JSONL→该 Neo4j schema 的 loader。
- `Event.apt` 不能表示 multi、ambiguous 或 unmapped。它们只能先作为 unlabeled Event context；强塞单 actor 会破坏语义。
- 当前 v2 精确得到一个 actor name 的 Event 有 346 个，其中 132 个在 active vocabulary，214 个不在；multi resolved-set 3 个；其余 3,811 个不能成为当前单标签监督 truth。
- 现有 staging JSONL 能保留 raw refs/provenance，但组员 trainer 不消费。loader 能读并不等于 mapping 语义正确。
- 仓库中还存在绕过新 mapping 的旧路径：`intermediate/otx.py`、`ingest/normalize.py`、`build_entity_registry.py`、`connectors/otx.py`。P4 必须加入口 guard/选择，不在 P0/P1 中重构它们。

最小连接方式是 consumer-specific projection：保留全部 Event/IOC observation；仅 exactly-one、resolved、且 vocabulary-compatible 时填旧 `Event.apt`。multi/ambiguous/unmapped/provenance 留在 claim side table。若目标是让 GNN 真正学习 multi-actor，必须另列 trainer/schema 扩展，不能宣称当前单标签 trainer 已支持。

## 5. Recommended minimal design

### Plan validation

| Phase | 目标 | 精确输入 | 精确输出 | 代码入口 | 验收条件 | 前置依赖 | 明确不包含 |
|---|---|---|---|---|---|---|---|
| P1 Extraction decision audit | 在 resolver 前形成可审核、支持 multi/ambiguous 的 extraction decisions | 固定 run 的 713 个非空 occurrence；每行带 Pulse id、raw ref、`payload.adversary` 和上下文字段 | `actor_claim_extraction.jsonl`（一行一个 occurrence/decision，可含有序 claim list）+ parser impact summary；这是 audit/preparation，不是最终 mapping | 复用 `otx_downstream.py::_parse_adversary_actor_claims` 的执行路径，并在现有 build/audit script 加 version/hash；不得改 B0 历史函数 | 713 occurrence 全覆盖且 key 唯一；状态互斥；raw/order/provenance 无损；222 groups 均审阅；测试覆盖已知公司、URL、malware/campaign、slash、and、multi 例；报告旧/v2 retained/revoked/added/changed | 无 MISP 依赖；需 review protocol 和 decision version | resolver、canonical actor、Actor/IOC edge、Neo4j/GNN |
| P2 Resolver comparison | 在同一 approved claim rows 上隔离比较 resolver | P1 中 `candidate_single/list` 的有序 claim rows；另保留旧 776 供 historical B0 replay；固定 MITRE seed/bundle；MISP `42b5d56` | versioned B0/B1/B2 comparison rows + summary（resolved/ambiguous/unmapped/WIP/conflict、source/version/hash） | 旧 `otx_paper_mapping.py` 仅重放 B0；v2 resolution path 承载独立 exact resolver adapter；不得把 parser 藏入 resolver | 输入 row hash 相同；B1 exact unique/multiple/none 正确；无 fuzzy/cascade/first-candidate；所有 conflict/candidate 可回放 | P1 complete；MISP 原文件与 hash 固定 | 人工 TAG augmentation、最终 gold mapping、IOC attribution |
| P3 Consumer projection + smoke | 证明安全 projection 能被真实组员 pipeline 消费 | P2 resolution rows + 所有 Event/IOC observations + 固定组员 commit/config | 组员 Neo4j 所需 Event/IOC/四类关系投影；only-safe `Event.apt`；loader/smoke report；multi/ambiguous/unmapped 保留为 audit rows/unlabeled | `build_otx_downstream_projection.py` + 一个最薄 JSONL→Neo4j adapter（当前不存在）+ 组员 `graph_export.py`/trainer smoke entry | Event/IOC 数不受 actor 状态影响；仅 exactly-one + vocabulary-compatible 成为 label；multi 未被压单值；真实 exporter 可读；最小 GNN smoke 通过 | P2；可用测试 Neo4j；固定 consumer commit | trainer multi-label 改造、模型效果评估、canonical decision 修改 |
| P4 Deliverable | 冻结给组员的最小交付合同并封住 bypass | P3 已通过 smoke 的实际文件/loader/config | consumer files + manifest/version/hash + 明确分离的 internal audit/provenance 清单；物理格式以 P3 实际 loader 为准 | 现有 build entrypoint、manifest 与组员运行脚本；检查四条旧 OTX bypass path 的显式入口选择 | 从干净环境按 manifest 重放；hash 一致；组员命令可运行；旧入口不会静默绕过新 mapping | P3 smoke complete | 新 schema 家族、RAG/Fact/Support、正式全量 gold 数据包 |

### P1 — Extraction decision audit（可以立即实施）

输入冻结为 713 个 occurrence，初始 key 为 `pulse_id + raw_ref + source_path`，同时记录 raw-exact/normalized grouping。逐 occurrence 给出互斥 extraction status：

- `no_claim`
- `candidate_single`
- `candidate_list`
- `non_actor`
- `review_required`（reason 可为 ambiguous syntax、prose、malware/campaign mix 等）

保留 raw string、输出 label 顺序、span/拆分依据、review note、decision version。先审核 222 个 exact group，但不得在证明 context-equivalent 前自动把 group decision 传播到所有 occurrence。P1 不调用 MISP/MITRE resolver，不生成 Actor/IOC attribution。

### P2 — Resolver comparison

- B0：冻结并重放旧 parser + 旧 MITRE resolver，776 只作为 historical baseline。
- clean B1：使用 P1 的同一 approved claim rows；MISP `42b5d56` exact value/synonym；unique→resolved、multiple objects→ambiguous、none→unmapped、WIP 单列；无 augmentation、fuzzy、first-candidate 或 cascade merge。
- B2：MISP 保持 paper-primary，固定 MITRE bundle 只作单独 exact resolver/corroborator。仅 unique exact 可自动 resolved；taxonomy 内 ambiguity 或跨 taxonomy 冲突保留 candidate/review，不静默 union。

比较必须报告相同 claim-row population、resolved/ambiguous/unmapped/WIP、canonical disagreement、prototype-only/paper-only、疑似 over-split/over-merge、source/version/hash 和 consumer compatibility。B0 的 776 与 clean B1 不直接声称“同 extraction”；若做 resolver-only 对照，必须另有相同 P1 claim inputs 的 B0-resolver run。

### P3 — Consumer projection validation

先做 backward-compatible projection：Event/IOC/InReport 不依赖 actor parser；仅 exactly-one resolved actor 且在 vocabulary 中填 `Event.apt`；其他状态保留但 unlabeled。P3 包括最薄 loader 和真实 Neo4j/exporter/GNN smoke，因为不跑 loader 就不能证明 consumer compatibility。然后单独决定 multi-label GNN 扩展：其输入应是 resolved actor set/claim relations，而不是把 multi 随机压成一个 actor。P3 不修改 canonical mapping 决策。

### P4 — Deliverable / entrypoint validation

冻结 P3 已验证的实际 loader 输入与组员交付清单，并显式选择新 projection，阻止旧 OTX 路径绕过 mapping。具体物理格式在 P3 的 loader 实现后冻结；当前 JSONL 只是候选 staging，不能把它误称为组员已经接受的合同。P4 不提前重构 Neo4j/GNN/RAG。

最小逻辑语义仍需区分 source event、raw actor claim、actor resolution、indicator observation、event–actor claim、event–indicator observation 和 consumer projection。它们不要求七套物理文件或新数据库。

## 6. Decision

**READY_TO_IMPLEMENT_P1**

P1 已有完整、固定、可复核的 occurrence population，可在不依赖 MISP、不触碰 downstream 的情况下开始。必须先解决的是 extraction gold/review decisions，以及 raw-value decision 能否跨上下文复用；这会阻塞 clean B1/P2，但不阻塞 P1。

下一实现任务应只包含 occurrence 冻结、extraction decision/status、上下文审核、parser retained/revoked/added/changed 统计、可重放 tests/hash。明确不包含 MISP resolver、完整 mapping、actor–IOC strong edge、Neo4j loader、GNN multi-label 修改、Fact/Support/RAG 或论文人工 augmented TAG 重建。
