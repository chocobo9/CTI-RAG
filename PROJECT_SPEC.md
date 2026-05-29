# PROJECT_SPEC.md — CTI-RAG 能力分项评测 + 标注器认证

工作流约束见 `CLAUDE.md`。开工前读完对应 Phase 全部小节。

---

## Section 1 — 项目上下文(已从磁盘验证)

仓库 `rag_cti/`(Python, pydantic, Qdrant, bge-m3, bge-reranker-v2-m3, Groq)。

已验证接口(file:line):
- 检索:`pipeline.run(text, top_k) -> QueryResult(.results: list[RetrievalResult])`;`_PipelineRetriever` 适配器在 `scripts/eval_techniquerag.py:31-39`。
- `RetrievalResult.document` 是 `Chunk`,匹配键 `chunk.metadata["attack_id"]`(`retrieval_metrics.py:29-31`);`Chunk` 有 `id/source/content/metadata`(`types.py:21-29`)。
- 生成:`Generator.generate()` 当前只吐散文 + `[chunk_id]` 引用(`generator.py:24-52`, `prompts.py:3-11`, `context_builder.py:43-52`)。model 走 `LLMRouter.model_for(TaskType.ANALYSIS)` = `groq_analysis_model`(`config.py:31` = `llama-3.3-70b-versatile`),调 `client.chat.completions.create(model, max_tokens=generation_max_tokens=1024, messages)`(`generator.py:54-61`)。**系统当前不吐 technique-ID 集合、不吐 actor 名。**
- 解析复用 `techniquerag.parse_gold_ids(output)`(= `_TECHNIQUE_RE.findall`,公开、已测,`techniquerag.py:22-30`)。
- 自建 eval 现状:`scripts/eval_attribution.py` 读 `data/eval/query_set_v2.jsonl`,按 attack_id/pulse_id/actor_in_content/malware/source 多信号匹配,报 hit@k/MRR/nDCG 分类(7 类:precise/semantic/fuzzy/otx_actor/otx_malware/relationship_direct/relationship_reverse,共 47 条)。
- RAGAS:`ragas_eval.py` 已有 faithfulness + answer_relevancy(DeepSeek judge,bge-m3 embed),可扩 context_precision/recall。
- **已知 eval 病(本任务要绕开/修,不碰 `_is_match` 本体)**:`_is_match` 父子双向通配虚高(`retrieval_metrics.py:34-46`);多标签 any-hit 不管 recall;`otx_actor` 的 `actor_in_content` 判据是后门(任何提到该 actor 的 chunk 都命中 → 1.000 虚高);`relationship_direct` gold 只标 1 个 attack_id → 0.100 假低;query_set_v2 全 LLM 生成、无人工验证。

外部锚(已 clone `maveryn/cti-bench` 验证,License CC BY-NC-SA 4.0,研究可用):
- **CTI-ATE**:`data/cti-ate.tsv`,59 条,列 `URL/Platform/Description/Prompt/GT`,输入=技术描述散文,**GT=逗号分隔 technique-ID、technique 级、多标签**(例 `T1071, T1573, T1083, T1070`)。**仓库未提供 ATE 评分器**,Micro-F1 按 §M 标准实现。
- **CTI-TAA**:`data/cti-taa.tsv`(50 条,actor 名已 `[PLACEHOLDER]` 化)+ `evaluation/responses/cti-taa-responses.tsv` 的 `GT` 列(单 actor)+ `evaluation/alias_dict.pickle` + `evaluation/related_dict.pickle`。**评分器已提供**:notebook `compute_taa_accuracy` + `threat_actor_connection`(别名链 BFS=C,相关组链 BFS=P,否则 I)。

---

## Section M — 指标定义(写死,依据已注明)

依据:CTI-ATE Micro-F1 来自 CTIBench 论文正文(指标声明)+ TechniqueRAG 用同一套 set 化 P/R/F1(论文 Table 2/4);TAA correct/plausible 来自 cti-bench 仓库评分器代码;P/R/F1@k 来自 TechniqueRAG Table 4。**不是自定义。**

`normalize_id(tid, level)`:`level=="technique"` → `tid.split(".")[0].upper()`(`T1059.001`→`T1059`);`level=="subtechnique"` → `tid.strip().upper()`。

**Micro-F1(集合预测,无排序;给 CTI-ATE / annotation)**:单条记录 gold 集 G、系统输出集 P → `TP=|P∩G|, FP=|P\G|, FN=|G\P|`。micro = 全记录求和后算:`P=ΣTP/(ΣTP+ΣFP)`,`R=ΣTP/(ΣTP+ΣFN)`,`F1=2PR/(P+R)`(P+R=0→0)。归一到指定 level 后做精确集合运算。

**P/R/F1@k(检索,有排序;给异构检索的多标签 category)**:同上公式,但 P = top-k 结果去重后的 attack_id(归一到 level)。报 k∈{1,3,5,10}。

**TAA correct/plausible(给 actor 归因)**:忠实移植仓库——`threat_actor_connection(gt, pred, alias_dict, related_dict)` 返回 C/P/I;`Correct Acc = #C/total`,`Plausible Acc = (#C+#P)/total`。

**hit@k/MRR**:仅保留给**单目标 category**(precise:单 attack_id)。多标签 category(otx_malware/relationship_*)一律换 P/R/F1@k 或 Recall@k。

---

## Section 2 — 能力分项表 + 验收(铁律:分开报,绝不平均)

| 能力 | 指标 | gold 来源 | 外部锚(已验证可用) | 验收线 |
|---|---|---|---|---|
| technique 抽取/检索 | Micro-F1(tech 级)/ P/R/F1@k | LLM 自建(经认证) | CTI-ATE 59 人工 gold | 用户定(参考论文 RAG-no-ft 65–79) |
| actor 归因 | correct / plausible acc | LLM 自建(经认证) | CTI-TAA 50 人工 gold + dict | 用户定 |
| 异构检索(OTX/PDF/IOC) | nDCG@k / Recall@k(ranx) | LLM 自建 query-set | 无 → 靠认证过的标注器背书 | 用户定 |
| 生成 grounding | RAGAS faithfulness / ctx-precision | reference_answer | — | 用户定 |

**粒度**:全部先做 **technique 级**(CTI-ATE gold 即 technique 级,只能给 technique 级发证;sub 级无外部锚、暂不做)。

---

## §A — Phase A:指标 + 外部锚地基 `[RIE: R-I-E]`

### A.1 现状/影响链
新建 `src/rag_cti/evaluation/set_metrics.py`(§M 的 normalize_id + Micro-F1 + P/R/F1@k)、`src/rag_cti/evaluation/taa_metrics.py`(移植 TAA 评分器 + 加载 dict)。**禁止 import `_is_match`。**

| 文件 | 改什么 | 影响 |
|---|---|---|
| `src/rag_cti/evaluation/set_metrics.py` | 新建 | 无下游 |
| `src/rag_cti/evaluation/taa_metrics.py` | 新建,逐行移植仓库 `threat_actor_connection`/`compute_taa_accuracy` | 无下游 |
| `data/eval/ctibench/` | 放入 cti-ate.tsv / cti-taa.tsv / cti-taa-responses.tsv / *.pickle | 数据,不入 Qdrant |
| `tests/unit/test_set_metrics.py`, `tests/unit/test_taa_metrics.py` | 新建,手算样例 | 无 |

### A.2 Steps
1. `[RIE: R]` `git clone maveryn/cti-bench`,把 5 个 anchor 文件拷进 `data/eval/ctibench/`。**verify:** 贴 cti-ate.tsv 行数(59)、列名、一条 GT 样例;贴 pickle 能 load 且 key 数。
2. `[RIE: R]` 探查你 Qdrant 里 `attack_id` 粒度:抽样若干 mitre chunk metadata,看 attack_id 带不带 `.xxx`。**verify:** 贴 ≥10 个真实 attack_id 值,报"带子技术后缀比例 = X%"。(决定 sub 级以后做不做有意义。)
3. `[RIE: I-E]` 写 `set_metrics.py`。**verify:** `pytest tests/unit/test_set_metrics.py -q` 全绿。手算样例(写进单测,期望值手算非跑后 copy):
   - G=["T1059.001"], pred=["T1059.001","T1003","T1059.002"];tech 级 G_g={T1059} P_g={T1059,T1003} → TP=1 FP=1 FN=0。
   - 多标签 G=["T1566.001","T1204.002"], pred=["T1566.001","T1059"];tech 级 → TP=1 FP=1 FN=1。
   - 两条 micro 合并 tech 级:ΣTP=2 ΣFP=2 ΣFN=1 → P=0.5 R=0.667 F1=0.571(手算填死)。
4. `[RIE: I-E]` 写 `taa_metrics.py`,移植仓库逻辑。**verify:** `pytest tests/unit/test_taa_metrics.py -q` 全绿;含 hard case:别名连通对(→C)、相关组连通对(→P)、无关对(→I),用 dict 里真实连通的 actor 对。
5. `[RIE: E]` Evaluator gate:查无 `_is_match`、micro 公式对、TAA 忠实移植。**暂停汇报 Phase A。**

---

## §B — Phase B:输出头(系统当前不吐 ID/actor) `[RIE: I-E]`

### B.1 现状/设计
`prompts.py` 追加两个 prompt(不动旧的);`generator.py` 加两个方法(不动 `generate()`):
- `annotate_techniques(text, query_result) -> list[str]`:prompt 给输入文本 + 候选(`query_result.results` 的 `(attack_id, content)`),要求只吐逗号分隔 technique ID;用 `parse_gold_ids` 解析。候选 = `pipeline.run(text, top_k=40)` 后 rerank 注入 top-10(偏离论文 k=3 的理由:你 corpus 含 OTX/PDF 噪声,留余量;写进报告)。
- `attribute_actor(text, query_result) -> str`:prompt 给输入 + 候选,要求只吐一个 actor 名(无散文)。
- 两者均 **eval-only,不接产品 trace**,复用 `_call_llm`。

| 文件 | 改什么 | 影响 |
|---|---|---|
| `src/rag_cti/generation/prompts.py` | 追加 2 个 prompt 常量 | 无 |
| `src/rag_cti/generation/generator.py` | 加 2 方法 | `generate()` 不动 |
| `tests/unit/test_generation.py` | 加 2 个 parser 单测 | 无 |

### B.2 Steps
1. `[RIE: I-E]` 实现 2 prompt + 2 方法 + parser 单测(用真实 LLM 输出样式:含散文噪声/含 `T1059.001,T1027`/含 `NONE`/actor 名带空格,断言解析正确)。**verify:** `pytest tests/unit/test_generation.py -q` 全绿。**暂停汇报 Phase B。**

---

## §C — Phase C:标注器认证(命门,硬 gate) `[RIE: I]`

### C.1 目的
证明 B 的输出头能复现人工 gold,才准用它生成自建 gold。**认证只对 CTI-ATE/CTI-TAA 人工 GT,绝不对 LLM 生成数据。**

**建议认证线(用户可改,但不准设为 0 蒙混):**
- technique 标注器:CTI-ATE Micro-F1(tech 级)**≥ 0.65**。依据:论文 off-the-shelf RAG(无微调)在 Procedures 的 F1 下沿约 65;低于此说明标注器连"现成 RAG 复现人工 gold"的水准都不到,产出的自建 gold 不可信。
- actor attributor:CTI-TAA Plausible Acc **≥ 0.50**(单 actor、50 条小样本,先用宽松 plausible 线打底,Correct Acc 同报供参考)。
- 任一不过 → 该能力的自建 gold **不准生成**,只报外部锚分 + 停。

新建 `scripts/certify_annotator.py`。

### C.2 Steps
1. `[RIE: I]` technique 认证:对 CTI-ATE 59 条,`Description` → retrieve → `annotate_techniques` → 用 `set_metrics` 算 Micro-F1(tech 级)。
2. `[RIE: I]` actor 认证:对 CTI-TAA 50 条,`Text`([PLACEHOLDER] 版)→ retrieve → `attribute_actor` → 用 `taa_metrics` 算 correct/plausible(对 responses.tsv 的 GT)。
3. `[RIE: I]` 出认证结论:对照用户给的阈值,输出"通过/不通过 + 是否准许用于生成自建 gold"。**调真 Groq;禁 mock。** **verify:** 按 CLAUDE.md §4 报告 Phase C 认证表 + 小样本警示。
4. **硬 gate:认证不通过 → 停,报告给用户,不准进 Phase D。** 通过才继续。**暂停汇报 Phase C。**

---

## §D — Phase D:自建 gold 修复 + 能力分项跑分(前置:C 通过) `[RIE: I]`

### D.1 现状/影响链
用**已认证**标注器程序化修自建 gold(用户不手标、CC 不手编):
- `relationship_direct`:gold 从单 attack_id → 用认证标注器对该 actor×tactic 生成 technique 集合,换 Recall@k/F1@k 评。
- `otx_actor`:**移除 `actor_in_content` 后门**,只认 pulse_id(消假高)。
- `fuzzy`:判据统一(全 attack_id 或显式分流,写明)。
- 这些改在自建 eval 的判据/ gold 侧,**不碰检索管线**。

| 文件 | 改什么 | 影响 |
|---|---|---|
| `data/eval/query_set_v2.jsonl` | 认证标注器程序化扩充/重标 gold(产出新文件 `query_set_v3.jsonl`,保留 v2 可回溯) | 自建 eval 输入 |
| `scripts/eval_attribution.py` | 移除 actor_in_content 后门、多标签 category 换 set 化 P/R/F1@k、统一 fuzzy | 只改判据/指标 |
| `src/rag_cti/evaluation/ragas_eval.py` | 加 context_precision/recall(复用 reference_answer) | 只加指标 |
| `scripts/eval_capabilities.py` | 新建:四能力分项汇总跑分,各自指标,**绝不平均** | 顶层入口 |
| 依赖 | `pip install ranx`(异构检索 nDCG/Recall@k) | 新依赖 |

### D.2 Steps
1. `[RIE: I]` 用认证标注器生成 `query_set_v3.jsonl`(扩 relationship_direct gold);记录每条新 gold 由哪次认证背书。**verify:** 贴扩充前后 gold 规模对比 + 抽样 5 条新 gold。
2. `[RIE: I-E]` 改 `eval_attribution.py`:去后门、多标签换 set 指标、统一 fuzzy。**verify:** 单测覆盖"去后门后 otx_actor 不再因 actor_in_content 命中"。
3. `[RIE: I]` `eval_capabilities.py` 跑四能力分项 + RAGAS 扩展,真 Groq。**verify:** 按 §4 报告四行独立分数表,每行带数据/指标/外部锚;CTI-ATE/TAA 两行同时给"系统在自建集的分"与"在外部锚的分",并列不混。
4. `[RIE: E]` Evaluator gate:查无平均、无后门残留、relationship gold 来自认证标注器而非手编、多标签用 set 指标。**暂停汇报 Phase D。**

---

## Step 执行顺序
```
A(地基) → B(输出头) → C(认证,硬gate)──不过则停──→ D(修gold+分项跑分)
每个 Phase 末暂停汇报。
```

## File Structure(穷举;禁止动列表外文件)
- 新建 `src/rag_cti/evaluation/set_metrics.py`, `taa_metrics.py` — A
- 新建 `scripts/certify_annotator.py` — C
- 新建 `scripts/eval_capabilities.py` — D
- 新建 `data/eval/ctibench/*`(数据), `data/eval/query_set_v3.jsonl` — A / D
- 改 `src/rag_cti/generation/prompts.py`(追加), `generator.py`(加 2 方法) — B
- 改 `scripts/eval_attribution.py`(判据/指标), `src/rag_cti/evaluation/ragas_eval.py`(加指标) — D
- 改/加 `tests/unit/test_set_metrics.py`, `test_taa_metrics.py`, `test_generation.py` — A/B
- **不碰**:`chunking.py`/ingest/seed/fetch、`retrieval/*`、`reranker.py`、`retrieval_metrics.py` 的 `_is_match` 本体、`config.py`
