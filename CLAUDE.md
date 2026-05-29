# CLAUDE.md — CTI-RAG 能力分项评测 行为宪法

任务规格见 `PROJECT_SPEC.md`。

## Section 0 — 核心原则
- **产出是"可信的数字",不是"绿色对勾"。** 本任务存在的唯一理由:现有 eval 不可信(gold 假低假高、指标错配)。一个跑通但不可信的数字,比不跑更有害。
- **核心机制 = 标注器认证。** 用户无法手工标注/审计 gold,只能让 LLM 标、用户验收。所以"LLM 自建 gold"要可信,**唯一不自证的办法是:先用 LLM 标注器去标有人工 gold 的外部集(CTI-ATE/CTI-TAA),证明它能复现人工标注,再让它标用户自己的 corpus。** 认证不过,就不准用它生成/扩充 gold。这条是本任务的命门,任何绕过它的实现直接判 FAIL。
- **Scope lock**:只动 `PROJECT_SPEC.md` File Structure 列出的文件。**禁止动 chunking/ingest/retrieval/rerank 管线**——chunk 策略已由用户拍板不改。
- **开工前 MUST 先读 `PROJECT_SPEC.md` 对应 Phase 全部小节**,不从记忆写。
- **事实源 = 磁盘。** 任何"这函数返回 X""这字段叫 Y"的声明,当场 grep/cat 贴证据。

## Section 1 — 工作流(RIE)

| Step 类型 | RIE | 本任务实例 |
|---|---|---|
| 新模块(含计算逻辑) | R-I-E | `set_metrics.py`、`taa_metrics.py`、输出头 |
| 移植已有实现 | R-I-E(R=逐行核对源) | 从 cti-bench 仓库移植 TAA 评分器 |
| 数据探查 | R | 确认 attack_id 粒度、CTIBench 列结构 |
| 跑分 / 认证 | I(执行+记录) | 在 CTI-ATE/TAA 上跑认证、能力分项跑分 |
| 测试 | I-E | 手算样例单测 |

每步在 SPEC 里有 `[RIE: X]` 标签。**认证 Phase(Phase C)是一道硬 gate:不过就停,不准进 Phase D。**

**Evaluator gate(每 Phase 一次)**:独立子 agent 评审,prompt MUST 含 SPEC 对应 Phase 原文 + 下面审查清单。禁止自评自己写的指标/认证代码。

**失败上限**:同一 Phase 连续 FAIL 3 次 → 停,贴三次 FAIL 原因给用户。

## Section 2 — 硬禁(二元判定,针对本任务最可能的偷懒解)

1. **禁止把 hit@k/MRR 当 F1/Micro-F1。** 指标定义见 SPEC §M。若报出的"F1"在代码里实为 `hit_count/n`,FAIL。
2. **禁止任何新 scorer 复用 `retrieval_metrics.py` 的 `_is_match`**(父子双向通配虚高)。technique 级 MUST 用 `normalize_id` 归一到 `T####` 再精确比。
3. **禁止跳过认证直接拿"自建 gold"跑分。** Phase D 的任何跑分,前置条件是 Phase C 认证通过且记录在案。无认证记录的 Phase D 结果一律作废。
4. **禁止用 LLM 自己生成的数据去认证 LLM 标注器(自证循环)。** 认证 MUST 对 CTI-ATE/CTI-TAA 的**人工 GT**,绝不对任何 LLM 生成的 gold。违反=直接 FAIL,这是命门。
5. **禁止把多个能力的分数平均成一个总分。** 四个能力分数永远分开报。
6. **禁止 mock LLM 充当认证/跑分。** 认证和能力跑分 MUST 调真 Groq;不可用就 FAIL 并报告,不准伪造分数。
7. **禁止手工编造 gold 标签。** 用户不手标;CC 也不准 hand-write gold。gold 扩充 MUST 由"已认证的标注器"程序化产出,不是 CC 现编几条塞进去。
8. **TAA 评分器 MUST 忠实移植** cti-bench 仓库的 `threat_actor_connection`(别名链=C / 相关组链=P / 否则 I)+ `compute_taa_accuracy`,**禁止自己发明更松的 actor 匹配**(如"名字子串包含")。
9. **禁止改动 File Structure 未列出的文件**,尤其 chunking/ingest/retrieval/`_is_match` 本体。

## Section 3 — 执行约束(MANDATORY)

### 测试完整性
- "跑全部测试" = 实际执行 `pytest tests/` 并粘贴 summary 行(collected/passed/failed/skipped)。禁止"应该通过"。
- 有 skipped/xfailed → 逐条列原因;未经用户批准的 skip 一律 FAIL。

### 禁止的捷径
- 无 `skip`/`xfail`/`try:...except:pass` 包断言(除非用户对该条显式批准)。
- 认证/跑分(标 E2E/integration)禁止 mock LLM;LLM 不可用就 FAIL。
- 断言验证行为属性(含某 ID、值在区间、类型对),非冻结快照。

### 测试数据质量
- 输入 MUST 真实 CTI:真实 technique ID、真实 actor 名、真实 ATT&CK 描述。禁止 `"test"`/`"hello"`。
- Fixture MUST 触发被测路径:测多标签 recall 的,gold 真含多 ID;测父子归一的,真含 `T1059` 与 `T1059.001`;测 TAA plausible 的,真用 alias/related dict 里连通的一对。
- 评判逻辑与测试数据分离;被测函数不得生成自己的期望值。

### 阈值
- 认证通过线、各能力验收线**由用户定**(见 SPEC §A 的占位)。CC 不得自设一个宽松线蒙混;用户没给线就停下来问。

## Section 4 — 报告格式(能力分项,绝不平均)

```
## <Phase> 结果
环境: collection=<名>, generator=<model 或 N/A>, n=<N>

### 能力分项表(每行一个能力,独立)
能力              | 指标            | 数据/split        | 分数        | 外部锚(若有)
technique 抽取    | Micro-F1(tech)  | CTI-ATE 59       | ..          | 论文 RAG-no-ft 65–79
actor 归因        | correct/plaus   | CTI-TAA 50       | ../..       | (CTIBench 公开数)
异构检索          | nDCG@k/Recall@k | 自建 query-set    | ..          | 无
生成 grounding    | faithfulness    | 自建 + ref_answer | ..          | 无

### 认证结论(仅 Phase C)
标注器在 CTI-ATE Micro-F1 = ..  (阈值 <用户线>) → 通过/不通过
attributor 在 CTI-TAA correct/plaus = ../.. (阈值 <用户线>) → 通过/不通过
→ 是否准许用于生成自建 gold: 是/否

### 小样本警示
CTI-ATE n=59 / CTI-TAA n=50,置信区间宽,仅作校准锚,不支撑强声明。

### 测试报告 + 改动文件清单(对照 File Structure)
```
