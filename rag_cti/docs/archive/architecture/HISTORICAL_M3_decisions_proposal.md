# HISTORICAL — M3 Fact / supports 决策提案

> Archive category: architecture decision proposal.
>
> **Status: HISTORICAL / SUPERSEDED. Do not treat the old “不得开工” gates below
> as current implementation policy.** This file preserves the pre-implementation
> proposal only. Current Knowledge schema authority is
> `docs/knowledge_layer_design.md`; current implementation truth is code and tests.

> 状态:**草案,等用户 confirm/override**。M3(`knowledge_layer_design.md §6 Phase 2`)
> 的门控是 D3 / D4 / D5 + 谓词词表对齐(`docs/archive/architecture/HISTORICAL_knowledge_refactor_roadmap.md:106-113`)。文档要求:这些
> 门控**未答之前不得动 M3 代码**。每条给出:决策 / 选项 / 推荐 / 承诺什么 / 风险或残留问题。

## 0. 先厘清:M3 比想象的小

M3 = **对已有数据做一次聚合**,不是从零建图:
- `data/processed/resolved_relations.jsonl` 已是 `{subject_id, predicate, object_id}` 三元组(M2.6 `resolve_relations` 产出,entity_id 已解析、orphan 保留)。
- 各 chunk payload 已带 per-doc `relations[]`(同样 entity_id 三元组)。
- 受控谓词集已在 `CONTEXT.md §Fact` 定稿且 data-backed。

所以 M3 = 读三元组 → 按 `(subject,predicate,object)` 分组 → 一条 **Fact** + N 条 **supports**
(`evidence_id = chunk_id`)。`construction_pipeline_design.md §4` 的伪码就是全部逻辑。规模:
当前 MITRE rel + OTX 约 6k resolved relation,聚合后 Fact 数更少。**JSONL 落盘即可**
(与 `entity_registry.jsonl` 同级),不需要数据库。

---

## D3 — 聚合可信度:存储+增量 vs 查询时计算

**文档默认**:(a) 每加一条 supports 就重算并存到 Fact 上(读便宜、可被检索过滤、写偏重)。
备选 (b) 查询时从 supports 现算(永远新鲜、读偏重)。

**推荐:确认"物化在 Fact 上",但触发改为「批量构建末尾」而非「逐行增量」。**
- 理由:本项目摄取是**批量重建**(seed → ingest → collection),没有流式/增量在线写入。
  "每加一行就重算"的增量机制是 YAGNI——一个 fact 的全部 supports 在同一次构建里就齐了,
  构建末尾算一次即可。
- 落地:Fact 行带 `aggregate_credibility` + `support_count` + `distinct_origins`(冗余但可过滤),
  **全量重建时重算**。读便宜(=a 的好处),省掉增量机器(=避开 a 的复杂度)。
- **承诺**:可信度成为可过滤的检索信号(将来"只要高可信 fact"能走 payload 过滤);
  改 D4 公式 = 一次全量重建(批量系统可接受)。

---

## D4 — 聚合函数(研究/调参面)

**文档默认**:不指定,**别把任意公式埋进代码**。可用输入(`§5` + `CONTEXT.md`):
源可靠性(mitre > otx > pdf-extracted)、跨源一致(distinct origins)、recency、count。

**推荐:不现在定"那个"公式;落一个透明的 v0 占位,放在单一命名+版本化+可替换的函数后面。**
- 要拍板的不是系数,而是这两条原则:① **v0 是临时基线、明确标注 provisional**;② 调参是独立子任务。
- v0 建议(临时、可改):`agg = base(source_reliability_max) + w1·log(distinct_origins) + w2·recency_decay`,
  系数写进 config、函数带 `version` 字段写进 Fact 行(便于"这批数用的是 v0/v1 哪版")。
- **守住门控精神**:公式是**一个显式命名的函数 + 配置 + 版本号**,不是散落在聚合循环里的魔法数——
  满足"explicit, not buried",同时不阻塞 M3 落地。
- **残留问题(给你)**:v0 系数要不要先拍一组,还是先发"全 1 等权"占位、等有 ground-truth 再调?

---

## D5 — 冲突:表示,不在摄取时裁决

**文档默认**:两源断言互斥事实(如 `campaign attributed-to G0016` vs `G0032`)时,
**不在写入时选赢家**;两条 Fact 各带自己的 supports 并存,冲突**可表示、被surface**。

**推荐:直接确认(强推)。**
- 理由:正合 Rule 0(别廉价+不可逆+静默地毁掉少数派主张);且**几乎零成本**——Fact 按三元组去重,
  object 不同自然就是两条 Fact,本就并存。
- 唯一要补的小决策:**声明哪些谓词是"单值"**(才谈得上"互斥")。建议初版只把 `attributed-to`
  标为软单值(同 subject 多 object = 冲突候选,surface 但不裁),其余谓词多值不报冲突。
  (注:co-attribution 真实存在,所以是"软"——只标记供审,不强制唯一。)
- **承诺**:加一个冲突视图/标记(同 subject + 单值谓词 + 不同 object),不删任何一边。

---

## 谓词词表对齐 —— 这是唯一卡住"开工"的点

**已就绪**:受控谓词集已在 `CONTEXT.md §Fact` 定稿、每个都 data-backed,M3 只聚合现有
`relations[]`,**不发明新谓词**。三组:
- 归因/TTP:`uses` / `attributed-to` / `targets`
- 基础设施(field source):`resolves-to` / `belongs-to` / `located-in` / `uses-nameserver` / `has-subdomain`
- 防御(MITRE):`mitigates` / `detects`

**那条 track 的词表是什么**:`knowledge_layer_design.md:138` 明确写出 = `ASSOCIATED_WITH` /
`PART_OF` / `OBSERVED_IN`(图库式 UPPER_SNAKE 命名,与本项目 kebab-case 不同)。

**文档其实已自答这条门控**:`knowledge_layer:138-139` 原话——这3个谓词"alignment pending;
**在有数据源支撑前不加入**";`00_START_HERE:137-139` 的"不在 scope,别建"清单也点名
`ASSOCIATED_WITH` 无源支撑、别造值。本项目现有源**无一支撑**那3个 → **M3 只聚合已有
data-backed 谓词集、不碰那3个 → "两轨分叉"自然避免**。

**真正剩下的只是一句确认**:attribution-graph track 是否是别处真维护的独立项目?
- (A) 是 → 给我它实际谓词清单,做一次命名对齐(统一 UPPER_SNAKE / kebab-case 其一);
- (B) 否(文档前瞻占位)→ `CONTEXT.md §Fact` 即唯一权威,本门控**视为已答**,M3 可开。

---

## 一页纸总结(待你逐条 confirm / override)

| 门控 | 推荐 | 需你定的 |
|---|---|---|
| D3 | 物化在 Fact + **批量末尾重算**(非逐行增量) | confirm / 改回逐行增量? |
| D4 | v0 透明占位 + 命名+版本化+可替换函数;调参另列 | v0 先拍系数 还是 等权占位? |
| D5 | confirm 表示-不裁决 + `attributed-to` 软单值冲突标记 | confirm / 调整单值谓词清单 |
| 谓词对齐 | 文档已自答(那3个未backed谓词不加);M3 只聚合已有 data-backed 集 | track 是别处真项目(A 给清单做命名对齐)还是文档占位(B CONTEXT.md 即权威)? |

拍板后,M3 落地就是:读 `resolved_relations.jsonl` + chunk `relations[]` → 按三元组聚合成
`facts.jsonl` + `supports.jsonl`(`§4` 伪码)→ 全量重建算 D4 聚合 → 幂等可重跑(`§7` keying)。
