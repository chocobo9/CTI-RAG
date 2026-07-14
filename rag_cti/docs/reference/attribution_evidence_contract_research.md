# CTI-RAG Attribution Evidence Contract 研究

> 研究问题：CTI-RAG 如何建立稳定、可审计的 actor attribution evidence contract，而不是按返回的证据类型或来源数量判断？  
> 日期：2026-07-13  
> 范围：概念与判据研究；不是实施计划。

## 结论摘要

**不存在一个跨组织、跨任务、无需本地数据校准的通用“归因公式”。** Cyber attribution 同时涉及不完备信息、欺骗、来源依赖、actor/campaign 命名差异和开放世界中的未知候选。MITRE ATT&CK 也明确把 Group 视为 community-tracked activity cluster，指出不同组织的定义可能部分重叠或互相不同，Associated Groups 不是精确同一关系。[MITRE ATT&CK Groups](https://attack.mitre.org/groups/)

但可以建立一个相当稳定的**判断过程与数据 contract**：

1. 把待判断对象表达为精确、带时间范围的 `AttributionClaim`，而不是含糊的“这是 APT29”。
2. 保留每条 evidence 的原始 provenance、source identity、derivation chain 和 observed time。
3. 先判定 evidence 对 claim 的关系：`supports / contradicts / contextual / not-relevant / unresolved`，再谈权重。
4. 显式记录 competing hypotheses，包括 `another-known-actor`、`shared tooling/infrastructure`、`false flag` 和 `unknown actor`。
5. 先把同一上游来源或同一 observation 派生出的报道合并为一个 **dependency cluster**，再聚合；十篇转载不是十个独立支持。
6. 用 deterministic gates 保证 provenance、适用时间、claim-evidence link、冲突披露和最低 evidence coverage；用模型帮助做语义分类和提出假设，但不能让模型自行决定权限、独立性或最终发布等级。
7. 输出至少两个不同维度：`analytic judgment`（对 claim 的判断）与 `confidence in basis`（证据基础质量）。不能把情报界的 Words of Estimative Probability 当作已经测得的数学概率。FIRST 明确说明其百分比用于表达术语间关系，并非 quantitative probability。[FIRST Communicating Uncertainties](https://www.first.org/global/sigs/cti/curriculum/cti-reporting)
8. 系统必须能 `abstain`。推荐的机器判决不是单一的 `confirmed/probable/possible`，而是结构化的 `supported / leaning-supported / unresolved / leaning-refuted / refuted`，外加独立的 `high / moderate / low` evidence-basis confidence 和明确的 gaps。

因此，CTI-RAG 当前“按返回证据类型数量”只能作为 coverage hint，不能作为 attribution verdict 的充分条件。

---

## 1. 什么可以稳定，什么不能

### 1.1 可以稳定的部分

可跨项目稳定的是：

- claim 的原子化与 scope；
- evidence provenance 和 derivation；
- source reliability 与 information credibility 分离；
- support、contradiction、unknown 分离；
- source dependence / duplicate observation 的折扣；
- competing hypotheses 和关键 assumptions；
- deterministic release gates；
- verdict 的理由、反证、gaps 和 revision triggers；
- 用历史标注案例做 calibration、risk-coverage 与 abstention 评估。

ODNI ICD 203 要求分析产品描述来源质量与可信度、解释不确定性、区分 underlying information / assumptions / judgments，并分析替代假设；这组要求可以直接成为 contract 的审计骨架。[ODNI ICD 203](https://www.dni.gov/files/documents/ICD/ICD-203.pdf)

### 1.2 不能假装稳定的部分

以下内容不能在没有数据依据时伪装成数学事实：

- `TTP + malware + infrastructure = 85% attribution`；
- “两个高可信来源”等于某个固定 posterior；
- 把 LLM self-confidence 当作 correctness probability；
- 把 `high confidence` 等同于“80% likely”；
- 为不同时间、不同 actor universe、不同 source ecosystem 使用同一套固定权重；
- 将不存在于候选表中的 unknown actor 强行归入最相似的已知 actor。

ICD 203 将事件发生的 likelihood 与“判断依据的 confidence”作为不同概念，并要求不要在同一句中混用。[ODNI ICD 203](https://www.dni.gov/files/documents/ICD/ICD-203.pdf) FIRST 也将 WEP 和 Level of Confidence in Assessment (LCA) 分开。[FIRST Communicating Uncertainties](https://www.first.org/global/sigs/cti/curriculum/cti-reporting)

**我们的推断：**若 CTI-RAG 没有带 ground truth 或高质量 adjudication 的历史 attribution cases，就不应输出声称已校准的数值概率。可以先输出 ordinal judgment + evidence-basis confidence；积累评估集后再校准概率或 decision threshold。

---

## 2. 候选方法比较

| 方法 | 对 CTI attribution 的价值 | 主要风险 | 建议定位 |
|---|---|---|---|
| Structured Analytic Techniques / ACH | 强迫列出竞争假设，重视 disconfirming 和 discriminating evidence，防止 premature closure | 不是概率模型；矩阵评分仍含分析判断 | **作为推理骨架直接采用** |
| Source reliability × information credibility | 把“谁说的”与“这句话本身是否可信”分开 | 等级是 ordinal；不可简单相乘成概率 | **作为每条 evidence 的必要元数据** |
| Provenance / evidence graph | 识别转载、派生、共同上游、同一 telemetry，支持审计与依赖折扣 | provenance 缺失时只能标 unknown | **作为聚合前置条件** |
| Bayesian inference / Bayesian network | 在有明确 hypothesis space、causal assumptions、prior 和 likelihood 数据时可一致地更新 belief | 先验和条件概率难获得；naive independence 会严重重复计数；开放世界困难 | **后续可校准层，不作为初始 contract 真理** |
| Dempster-Shafer / evidence theory | 可显式表达 belief、plausibility 与 ignorance | 组合规则对 independence 和高冲突敏感，工程解释复杂 | **研究候选，不建议作为首个生产判决器** |
| Subjective Logic | 可同时表达 belief/disbelief/uncertainty，并提供 trust discount/fusion vocabulary | operator 与 independence 假设仍需严格定义；数字容易造成虚假精确 | **可借其表示思想，不急于采用完整演算** |
| Claim-evidence entailment / NLI | 可批量判断一段 evidence 是否支持、反驳或不足以判断 claim | 检索错误、时间/实体错配、语用和多跳推理会误判；不是最终 attribution | **模型辅助分类，必须保留证据 span 与审核** |
| Calibration + selective prediction | 用可接受 coverage 换取较低错误率，给 abstention 可测目标 | 依赖有代表性的标注集；distribution shift 会破坏 calibration | **最终 verdict 发布门的核心评估方法** |
| Conformal prediction | 在满足 exchangeability 等条件时提供 coverage guarantee | CTI case 非平稳、actor/source/time group shift 明显；不能直接套保证 | **有分层校准集后再研究，当前不作为主方法** |

### 2.1 ACH 的合适用法

CIA 的 Structured Analytic Techniques primer 将 ACH 定义为：识别替代解释，并评估能够 disconfirm 而不只是 confirm 假设的证据；它还强调 ACH 用于防止 premature closure，并突出 discriminating evidence。[CIA Tradecraft Primer](https://www.cia.gov/resources/csi/static/955180a45afe3f5013772c313b16face/Tradecraft-Primer-apr09.pdf)

对 actor attribution，候选 hypothesis 不应只是一组已知 actor：

- `H1: campaign C is operated by actor A`；
- `H2: campaign C is operated by actor B`；
- `H3: shared/commodity capability caused the overlap`；
- `H4: infrastructure/tooling was transferred, reused or compromised`；
- `H5: deliberate deception / false flag`；
- `H_unknown: an unmodeled actor is responsible`。

证据的价值主要在**区分假设的能力**，不是 evidence type 是否新颖。例如 “uses PowerShell” 覆盖一个新类型，但对数百 actor 都一致，诊断价值很低；一个与受控基础设施注册和独家 malware build lineage 同时吻合的 observation 可能更有区分力。

ACH 本身不产生可校准概率。推荐把它用于 hypothesis coverage、contradiction 和 missing discriminators，而不把矩阵分数直接改名为 probability。

这一限制还有实证依据。一项对 50 名 practicing intelligence analysts 的随机实验发现，ACH 训练者并未完整遵循所有步骤，偏差改善结果混合，且 ACH 可能增加判断的不一致或错误；另一项实验也质疑标准 ACH matrix 是否能稳定降低 confirmation bias。[Dhami, Belton & Mandel, ACH randomized experiment](https://onlinelibrary.wiley.com/doi/full/10.1002/acp.3550) [Analysis of Competing Hypotheses and confirmation bias experiment](https://pmc.ncbi.nlm.nih.gov/articles/PMC11169332/)

**结论：**采用 ACH 的 alternatives、diagnosticity、contradictions、missing-expected evidence 和 sensitivity testing 字段；不采用 raw consistency/inconsistency count 作为 confidence score。

### 2.2 Bayesian inference 何时适合

Bayesian network 能表示 hypothesis、evidence 与 causal dependency，并用于系统地挑战 evidentiary reasoning。[Tse, Chow & Kwan, *Reasoning about Evidence using Bayesian Networks*](https://dl.ifip.org/IFIP-TC11/hal-01523702v1)

它适合以下条件：

- attribution task 类别稳定；
- hypothesis space 明确且保留 unknown；
- 有足够 adjudicated cases 估计 `P(evidence | actor, context)`；
- dependence 由 graph 表达，而不是 naive Bayes；
- prior 的来源和时间窗口可审计；
- posterior 在 held-out、time-split 数据上经过 calibration。

否则，Bayesian 数字主要反映设计者写入的 prior/likelihood，而非现实精度。**我们的推断：**CTI-RAG 可以未来把 evidence contract 作为 Bayesian layer 的输入，但不应现在用手工权重假装 likelihood。

### 2.3 Dempster-Shafer 与 Subjective Logic

Dempster-Shafer 的吸引力是显式保留 ignorance，而不是把所有 mass 强制分配给单一假设。但证据组合的独立性条件和高冲突问题是关键限制；相关讨论指出组合有效性依赖来源独立性。[Zadeh & Ralescu, *On the Combinability of Evidence in the Dempster-Shafer Theory*](https://arxiv.org/abs/1304.3119)

Subjective Logic 同样适合表达 belief、disbelief 和 uncertainty，也研究了 conflicting source 下的 trust revision。[Jøsang, Ivanovska & Muller, *Trust Revision for Conflicting Sources*](https://isif.org/media/trust-revision-conflicting-sources)

**我们的判断：**两者的“保留 unknown/uncertainty、先按 trust discount 再 fusion”思想有价值，但当前不应选择某套 fusion operator 作为生产真理。没有清晰 dependency graph 时，换一种数学记号仍会重复计算同一条上游报告。

### 2.4 Claim-evidence entailment 的边界

FEVER 将 claim-evidence 关系分为 `SUPPORTED / REFUTED / NOT ENOUGH INFO`，并为前两类保存必要 evidence sentence；其标注一致性并非完美，说明即使在 Wikipedia 闭世界任务中，关系判断也具有难度。[Thorne et al., FEVER](https://aclanthology.org/N18-1074/)

CTI-RAG 可以借用三分法，但需要扩展：

- `supports`：该 span 在给定 entity/time/scope 下支持 claim；
- `contradicts`：明确支持互斥 claim 或否定该 claim；
- `contextual`：与背景有关，但不能推出 claim；
- `not_relevant`：实体、时间或关系不匹配；
- `unresolved`：证据不足或语义无法可靠判定。

模型适合提出这个 classification 和 exact span；deterministic validator 检查 span 是否存在、时间与 entity 是否匹配、source 是否可追溯。NLI label 不应直接成为 attribution verdict。

---

## 3. 不把“数量”误当“独立支持”

### 3.1 先建立 derivation / dependency graph

W3C PROV-O 提供 `wasDerivedFrom`、`wasQuotedFrom`、`wasRevisionOf` 和 `hadPrimarySource` 等 provenance 关系，可用于表示一条报道如何从其他实体产生。[W3C PROV-O](https://www.w3.org/TR/prov-o/)

每条 evidence 至少需要：

- `evidence_id` 与不可变原文/span；
- `publisher/source_identity`；
- `author/producer`（若可知）；
- `published_at`、`observed_at`、`valid_time`；
- `source_url/raw_ref/content_hash`；
- `derived_from[] / quotes[] / primary_source_ref`；
- `collection_method`；
- `source_reliability` 与 `information_credibility`；
- `dependency_cluster_id`；
- `claim_relation` 与分析理由。

聚合单位应是**独立 observation lineage**，而不是 document count：

```text
Vendor A incident telemetry ──> Vendor A report
                         ├────> News article 1
                         ├────> OTX pulse copying report
                         └────> ATT&CK citation
```

这四个文档至多构成一个主要 observation lineage；ATT&CK/OTX 的再表达提高可发现性与 provenance richness，不自动增加四份独立 corroboration。

### 3.2 Source reliability 与 information credibility 分开

FIRST CTI SIG 建议分别评价 source reliability（A–F）和单条 information reliability/credibility（1–6）；一个通常可靠的 provider 也可能发布尚未调优的新 feed，而一条具体信息可以与其来源历史可靠性不同。[FIRST Source Evaluation](https://www.first.org/global/sigs/cti/curriculum/source-evaluation)

因此不能用一个 `source_score` 覆盖所有问题。至少分开：

- `source_reliability`：该 producer 对此类信息的历史能力、真实性与方法透明度；
- `information_credibility`：该具体 claim 是否逻辑一致、可验证、被独立来源 corroborate 或被反证；
- `access/directness`：first-hand telemetry、malware sample、incident response access、转述或分析推断；
- `method_quality`：collection 和 analysis 是否可复核；
- `possible_bias/deception`：利益、动机、false flag 风险。

这些是不同 axes。A1/B2 是审计标签，不应直接当作可相乘的 probability。

### 3.3 时间相关性不是统一 decay 常数

不同 evidence 的时间语义不同：

- IP/domain ownership 与 certificate linkage 可能快速失效；
- malware code lineage 可多年保留价值；
- TTP 可能被大量 actor 学习，区分力随普及下降；
- 一次公开 attribution claim 的历史事实不会“衰减消失”，但可能被后续研究修订；
- actor/campaign/name mapping 会演化。

因此记录 `observed_at / valid_from / valid_until / published_at / superseded_by`，并按 signal class 制定 temporal relevance，而不是统一 `exp(-λt)`。时间衰减可以是未来模型的一部分，但 λ 必须来自 case data 或明确 policy。

---

## 4. 推荐的 Attribution Evidence Contract 概念草案

在进入结构之前，contract 必须先声明 attribution level。Rid 与 Buchanan 的 Q Model 将 attribution 看作在 tactical、operational、strategic 层面降低不确定性的过程，并强调 operational attribution 不是简单二元判断，strategic attribution 又与政治语境和风险相关。[Rid & Buchanan, *Attributing Cyber Attacks*](https://doi.org/10.1080/01402390.2014.977382)

**我们的边界推断：**以公开 CTI、内部检索和可审核外部来源为基础的 CTI-RAG，默认只能给出 technical/operational analytic attribution。它不能把 activity-cluster association 静默升级为国家责任、政治归责或法律证明。

### 4.1 判断对象

```text
AttributionClaim
  claim_id
  subject: incident | campaign | activity_cluster | malware_sample
  predicate: operated_by | associated_with | sponsored_by | overlaps_with
  object: actor_or_cluster_id
  attribution_level: technical | operational | strategic
  scope: tenant / investigation / corpus
  valid_time: [from, to]
  claim_text
  alternatives[]               # 必含 unknown / shared-resource 等可行替代
```

必须区分：

- `campaign operated_by activity cluster`；
- `activity cluster overlaps_with named group`；
- `group sponsored_by state/organization`。

前一个成立不能自动推出后两个。MITRE 对 Group/Associated Group 的警告正说明 name mapping 不是身份等式。[MITRE ATT&CK Groups](https://attack.mitre.org/groups/)

### 4.2 Evidence item 与 claim link

```text
EvidenceItem
  evidence_id
  immutable_span_or_artifact_ref
  evidence_kind                 # telemetry, malware, infrastructure, report claim, ...
  source_identity
  collection_method
  provenance_edges[]
  dependency_cluster_id
  published_at / observed_at / valid_time
  source_reliability
  information_credibility
  directness                    # primary observation / direct claim / inference / hearsay
  integrity_status

ClaimEvidenceLink
  claim_id
  evidence_id
  relation: supports | contradicts | contextual | not_relevant | unresolved
  strength_basis                # diagnosticity explanation, not an uncalibrated probability
  discriminates_against[]       # 哪些 competing hypotheses
  assumptions[]
  extraction_method
  reviewer/model_version
```

`direct claim` 只表示 source 明确做出了归因陈述，不表示它为真；`indirect cue` 表示分析者通过 artifact/behavior 推断；`corroboration` 必须来自不同 dependency cluster；`contradiction` 必须和支持证据同等保留；`temporal relevance` 属于 link/context，而不是文档的永久属性。

### 4.3 Hypothesis assessment

```text
HypothesisAssessment
  hypothesis_id
  supporting_cluster_ids[]
  contradicting_cluster_ids[]
  contextual_evidence_ids[]
  unresolved_evidence_ids[]
  key_assumptions[]
  missing_discriminators[]
  viable_alternatives[]
  deception_or_transfer_risks[]
```

此结构体现 ACH：不是累计“像 A 的证据”，而是比较同一 evidence 对各 hypothesis 的一致/不一致，并优先寻找能排除候选的 discriminator。[CIA Tradecraft Primer](https://www.cia.gov/resources/csi/static/955180a45afe3f5013772c313b16face/Tradecraft-Primer-apr09.pdf)

### 4.4 Verdict

```text
AttributionVerdict
  judgment: supported | leaning_supported | unresolved | leaning_refuted | refuted
  confidence_in_basis: high | moderate | low
  publishable_claim_text
  decisive_evidence_clusters[]
  material_contradictions[]
  viable_alternatives[]
  knowledge_gaps[]
  assumptions[]
  revision_triggers[]
  abstained: bool
  policy_version / model_version / assessed_at
```

推荐语义：

- `supported`：关键 provenance/gates 通过；存在有诊断性的支持；重大替代解释已被检查；无未解释的 material contradiction。它不等于法律意义上的“confirmed”。
- `leaning_supported`：支持方向更强，但仍有重要替代解释、依赖或缺口。
- `unresolved`：证据基础不足、相互冲突、主要来源依赖、unknown actor 仍同样可行，或系统无法可靠判定。
- `leaning_refuted`：反证方向更强，但不足以排除 claim。
- `refuted`：高质量且适用的证据与 claim 不相容，且反证本身通过 provenance/gates。

`confidence_in_basis` 描述证据与分析基础质量，不描述 claim 的数学概率。FIRST 对 LCA 的描述可作为报告语言基准：high 对应良好质量、多个 collection capabilities 且可形成清晰判断；moderate 表示多种解释或缺乏充分 correlation；low 表示碎片化或来源可靠性可疑。[FIRST Communicating Uncertainties](https://www.first.org/global/sigs/cti/curriculum/cti-reporting)

**为什么不用 `confirmed/probable/possible/insufficient`：**`confirmed` 容易被理解为客观身份已证明；`probable/possible` 又容易和 WEP/数学概率混淆。若产品必须使用这些词，应将其作为 presentation mapping，并明确内部 judgment、basis confidence 与其映射版本。

---

## 5. Deterministic 与模型判断的边界

### 5.1 必须 deterministic / policy-owned

- claim schema、entity identity 与 time scope 是否完整；
- citation/span 是否真实存在于本轮 Evidence Ledger；
- raw provenance、content hash、source URL/reference 是否可解析；
- duplicate/derived-from/dependency cluster 的合并规则；
- 一个 dependency cluster 只贡献一次 independent corroboration；
- source allowlist、权限、handling markings、外部采集与 promotion policy；
- contradiction 不得从输出中静默删除；
- minimum gates、budget、deadline、no-progress、release/abstention conditions；
- verdict vocabulary 与 confidence vocabulary；
- output 中每个关键 claim 必须指向 claim-evidence links；
- policy/model/data version 与 audit trail。

### 5.2 模型可提出，但输出必须可验证

- query decomposition；
- 原子 claim 提取；
- exact evidence span 提取；
- `supports/contradicts/contextual/unresolved` 候选分类；
- competing hypotheses、assumptions 与 gaps；
- evidence 的 diagnosticity explanation；
- next-best discriminator / source lookup 建议；
- narrative synthesis。

模型判断应结构化记录 model/version/prompt 与理由，并允许 human override。模型不得仅凭“感觉证据多”直接发出 `supported`。

### 5.3 Hybrid verdict admission

合理的控制方式是：

```text
model proposes semantic assessment
        ↓
deterministic validators construct dependency-aware evidence view
        ↓
policy checks minimum contract + material contradictions + alternatives
        ↓
calibrated decision rule accepts a verdict or abstains
        ↓
composer renders claim, confidence, evidence, contradictions and gaps
```

这里 deterministic gate 不负责宣称“世界真相”，而是负责判断：系统是否拥有足够、合法、可追溯的依据发布某个等级的 analytic judgment。

---

## 6. 与现有 CTI-RAG 对象的承载关系

以下是概念映射，不是实施步骤。

| 现有对象/字段 | 已能承载 | 仍缺的语义 |
|---|---|---|
| `Fact` | canonical subject-predicate-object；冲突可并存 | Fact 不是 attribution verdict；需要 hypothesis 与 time-scoped claim |
| `supports` / `FactCitation` | `evidence_id`、`origin`、per-support confidence、`label_availability`、observation time | source identity 与 publisher 之外的 upstream provenance、dependency cluster、claim relation、contradiction、method |
| `label_availability=direct/indirect/...` | label 是否直接可得的粗粒度信号 | directness 不能代表 truth 或 independence；需保留 source 原句和 derivation |
| `EvidenceLedger.chunks/facts/outlines` | per-run evidence authority、去重、citation ID guard、conflict surface | claim-evidence graph、source dependence、临时/持久 evidence status、hypotheses、verdict history |
| `FactRow.aggregate_credibility` | 当前 materialized credibility hint | 若仍基于 support count/origin，不能承担 attribution probability；需 dependency-aware 且经 calibration |
| source-claim artifacts | 来源声称的落点 | 将“source claimed X”与“system assesses X”彻底分层 |
| sufficiency verdict / coverage gaps | investigation continuation hint | typed gap、candidate discriminator、action-to-gap link、attribution contract admission |

当前 `EvidenceLedger` 以 chunk/fact ID 去重，能够防止同一 ID 重复，但不能证明两个不同 ID 来自独立 observation。现有 `supports` 把一 Fact 的多个出处保留，这是正确基础；下一层概念需要回答这些出处是否共享上游、是否只是转述、是否互相矛盾。

---

## 7. 反例：为什么 evidence type/source count 会失败

### 反例 A：五种类型，只有一个上游

同一 vendor 报告声称 Actor A，并列出 domain、IP、malware family、TTP、target sector。系统得到五种 evidence type；MITRE、新闻和 OTX 又分别转载。

- 旧规则：5 types + 4 sources，可能判 high confidence。
- Contract：1 dependency cluster；direct attribution claim 只有一个 producer；其余 technical cues 可能只证明 campaign cohesion，不独立证明 actor identity。
- 合理 verdict：最多 `leaning_supported / low-or-moderate basis`，取决于原始 telemetry access、method 和 alternatives。

### 反例 B：许多低诊断力 TTP

某 campaign 使用 PowerShell、spearphishing、scheduled task、credential dumping，全部与 Actor A 的 ATT&CK profile 重叠。

- 旧规则：四类/四技术支持 Actor A。
- Contract：这些行为可能与大量 actor 一致，对 `A vs B vs unknown` 的 discrimination 很弱；ATT&CK 还说明 group-technique mapping 只是公开报道的 subset。[MITRE ATT&CK Groups](https://attack.mitre.org/groups/)
- 合理 verdict：`unresolved`，继续寻找独特 code lineage、operator pattern、controlled infrastructure 或其他 discriminator。

### 反例 C：一个强反证被多数票淹没

三篇报道重复旧 attribution；后续 incident responder 公布原始 telemetry，证明基础设施在相关时段被第三方接管。

- 旧规则：3 support vs 1 contradiction，仍支持。
- Contract：三篇旧报道同一 dependency cluster；新 telemetry 是高 directness 的 material contradiction，必须阻止 `supported`，并触发 reassessment。

### 反例 D：Actor name 被当成身份等式

Vendor A 的 cluster 与 Vendor B 的 cluster 部分重叠，MITRE 将其列为 Associated Groups。

- 旧规则：alias 匹配后合并所有行为与基础设施。
- Contract：`overlaps_with` 不是 `same_as`；claim scope 保留各自 cluster definition 和 time range。
- 合理 verdict：只能陈述 overlap 或 reported association，不能自动断言同一 operator。

### 反例 E：证据陈旧但类型丰富

五年前 Actor A 使用某公开 malware 和 hosting pattern；当前 campaign 也出现相同模式。

- 旧规则：malware + infra + TTP 三类，满足数量。
- Contract：检查 signal-specific temporal relevance、commodity availability 和 transfer/reuse hypothesis。
- 合理 verdict：若没有当前 discriminator，则 `unresolved` 或 `leaning_supported`，并披露时间缺口。

---

## 8. Evaluation、calibration 与 abstention

### 8.1 评估单位

不能只评最终文本。至少分别评：

1. `claim extraction`：claim 是否原子、entity/time/scope 是否正确；
2. `evidence retrieval`：关键 supporting 与 contradicting evidence 是否被找到；
3. `claim-evidence relation`：support/refute/context/unresolved 分类；
4. `provenance/dependence`：转载和共同上游是否正确聚类；
5. `hypothesis analysis`：是否包含合理 alternatives/unknown；
6. `verdict`：judgment confusion matrix；
7. `confidence`：是否与实际 correctness / adjudicator agreement 对齐；
8. `selective behavior`：错误率与 coverage/abstention 的关系；
9. `revision`：加入反证后是否按预期降级或改判；
10. `grounding`：每个关键 narrative claim 是否由相邻 evidence 支持。

### 8.2 数据切分

推荐至少做：

- time-based split，防止训练/评估共享后续已知 attribution；
- campaign/actor-family holdout，检查对新 actor 的 abstention；
- source-family holdout，检查对新 publisher 与转载链的鲁棒性；
- dependency-cluster split，避免同一原报告的转载跨 train/test；
- source outage / provenance missing / contradictory evidence stress sets；
- false flag、commodity tooling、shared infrastructure、name-overlap 专项集。

### 8.3 Calibration

神经模型的 raw confidence 通常未校准；temperature scaling 等 post-hoc 方法必须在独立 calibration set 上验证。[Guo et al., *On Calibration of Modern Neural Networks*](https://proceedings.mlr.press/v70/guo17a)

若未来有足够 adjudicated cases，可测：

- reliability diagram；
- Expected Calibration Error (ECE)（同时报告 binning sensitivity）；
- Brier score / log loss（仅当有概率输出）；
- classwise calibration；
- time/source/actor subgroup calibration；
- calibration drift。

在此之前，ordinal confidence 的评估应关注每档实际正确率、inter-analyst agreement 和 error severity，而不是把 high/moderate/low 映射成未经验证的固定百分比。

### 8.4 Selective prediction / abstention

Selective classification 的核心是 risk-coverage trade-off：允许拒答以换取被接受样本上的更低风险。[El-Yaniv & Wiener, *On the Foundations of Noise-free Selective Classification*](https://jmlr.csail.mit.edu/papers/v11/el-yaniv10a.html) 对 CTI-RAG，应画：

- x 轴：non-abstained attribution coverage；
- y 轴：accepted verdict error rate 或高严重度 false-attribution rate；
- 分别观察 `supported`、`leaning_supported` 的 precision；
- 设置 false positive attribution 的风险预算，而不是追求最大 coverage。

Abstention triggers 可包括：

- provenance 不完整；
- 关键证据集中于一个 dependency cluster；
- material contradiction 未解决；
- unknown/alternative hypothesis 仍同等可行；
- entity/time mismatch；
- source policy 不允许引用；
- model ensemble/reviewer disagreement 超阈值；
- out-of-distribution / new actor/source pattern；
- calibration support 不足。

### 8.5 Conformal prediction 是否适用

Conformal prediction 可在 exchangeability 等条件下提供覆盖保证；其经典说明明确依赖样本独立同分布/可交换性。[Shafer & Vovk, *A Tutorial on Conformal Prediction*](https://jmlr.csail.mit.edu/papers/v9/shafer08a.html) CTI 的 actor、source、时间和 adversarial behavior 明显非平稳，因此不能直接宣称 distribution-free guarantee。

未来若积累足够标注数据，可研究按 actor era、source tier、task type 分层的 prediction sets，并持续检查 exchangeability/drift。当前更合适的是 transparent selective thresholds + time/source split evaluation。

---

## 9. 对当前设计问题的直接回答

### 是否存在稳定通用方法？

不存在稳定通用的数值公式；存在稳定的 process contract。核心是 structured claim、provenance graph、dependency-aware corroboration、competing hypotheses、contradiction、abstention 和 empirical calibration。

### 哪些方法最适合 CTI actor attribution？

第一层采用 ACH/structured analytic tradecraft + source/information 双轴评价 + provenance/evidence graph；第二层用 claim-evidence relation model 辅助；第三层用 deterministic policy admission；有 adjudicated dataset 后再加入 Bayesian/calibrated selective model。Dempster-Shafer/Subjective Logic 不是当前首选生产聚合器。

### 如何避免按来源/类型重复计数？

将 `document/source count` 替换成 `independent observation lineage / dependency cluster`；保留引用与派生关系；同一 cluster 内多文档只增强可追溯性，不增加独立 corroboration 数。

### 如何表示不同证据角色？

用 `EvidenceItem` 表 provenance/directness/time，用 `ClaimEvidenceLink` 表 supports/contradicts/contextual/unresolved，用 dependency graph 表 source dependence，用 hypothesis matrix 表 discrimination，用 verdict 保存 gaps、alternatives 和 revision triggers。

### 如何产生可校准 verdict 并允许 abstain？

先使用 ordinal judgment 与独立 basis confidence；对所有发布 verdict 保存 outcome/adjudication；在 time/source/dependency-aware split 上校准 admission threshold；用 risk-coverage 决定何时 abstain。没有 calibration set 时不输出数学概率。

### 哪些是 deterministic，哪些交给模型？

provenance、依赖聚类规则、政策、最低 gates、冲突披露、citation/claim link、发布与 abstention 由代码控制；claim/span/relation/hypothesis/gap 由模型提出并结构化记录，validator 校验，最终 verdict 受 policy gate 限制。

---

## 10. 最小概念性验收标准（不是实施计划）

一个 Attribution Evidence Contract 只有同时做到以下事情，才算“已经能拿来判断”：

- 可以准确说明正在归因的是 incident、campaign、activity cluster 还是 state sponsor；
- 每个关键 claim 都能追到 immutable evidence span/artifact；
- 能区分 direct source claim 与 system analytic judgment；
- 能把转载链折叠为同一 dependency cluster；
- 能显示 material supporting 与 contradicting evidence；
- 能比较至少一个合理 competing hypothesis 和 unknown；
- 能解释为什么某 evidence 具有 discrimination，而不只是列类型；
- 能因 provenance、冲突或缺口而 deterministic abstain；
- verdict 同时输出 judgment、basis confidence、gaps、assumptions、alternatives 和 revision triggers；
- 在 dependency-aware、time-split 的案例集上报告 accepted-error/coverage，而不是只报告答案看起来是否合理。

---

## 主要来源

- [ODNI, Intelligence Community Directive 203: Analytic Standards](https://www.dni.gov/files/documents/ICD/ICD-203.pdf)
- [CIA, *A Tradecraft Primer: Structured Analytic Techniques for Improving Intelligence Analysis*](https://www.cia.gov/resources/csi/static/955180a45afe3f5013772c313b16face/Tradecraft-Primer-apr09.pdf)
- [FIRST CTI SIG, Source Evaluation and Information Reliability](https://www.first.org/global/sigs/cti/curriculum/source-evaluation)
- [FIRST CTI SIG, Communicating Uncertainties in CTI Reporting](https://www.first.org/global/sigs/cti/curriculum/cti-reporting)
- [OASIS, STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/cs02/stix-v2.1-cs02.html)
- [W3C, PROV-O Recommendation](https://www.w3.org/TR/prov-o/)
- [MITRE ATT&CK, Groups](https://attack.mitre.org/groups/)
- [Rid & Buchanan, *Attributing Cyber Attacks* / Q Model](https://doi.org/10.1080/01402390.2014.977382)
- [Tse, Chow & Kwan, *Reasoning about Evidence using Bayesian Networks*](https://dl.ifip.org/IFIP-TC11/hal-01523702v1)
- [Dhami, Belton & Mandel, empirical evaluation of ACH](https://onlinelibrary.wiley.com/doi/full/10.1002/acp.3550)
- [Thorne et al., FEVER](https://aclanthology.org/N18-1074/)
- [Guo et al., *On Calibration of Modern Neural Networks*](https://proceedings.mlr.press/v70/guo17a)
- [El-Yaniv & Wiener, *On the Foundations of Noise-free Selective Classification*](https://jmlr.csail.mit.edu/papers/v11/el-yaniv10a.html)
- [Shafer & Vovk, *A Tutorial on Conformal Prediction*](https://jmlr.csail.mit.edu/papers/v9/shafer08a.html)
