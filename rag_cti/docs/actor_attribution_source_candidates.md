# CTI-RAG：面向 Actor Attribution 的开源数据源候选评估

> 调研时间：2026-07-10  
> 范围：仅使用项目官方文档、官方仓库、官方 API 或报告发布机构原站。本文评估的是“该来源能为 actor 判断提供什么证据”，而不是只比较 IOC 数量。

## 结论先行

现有采集链路是：

```text
MITRE actor name / alias
  -> OTX pulse discovery and raw preservation
  -> OTX indicators
  -> VirusTotal enrichment
```

它覆盖了 actor 查询入口、报告级共现和 IOC enrichment，但中间缺少两层关键证据：

1. **跨厂商 actor identity/alias resolution**：同一活动可能被 MITRE、Microsoft、Mandiant、CrowdStrike 等命名为不同 cluster；alias 并不总是严格等价。
2. **可引用的 attribution claim**：必须保存“谁在什么报告中、以何种措辞、在什么时间，把什么活动/恶意软件/IOC 归给哪个 actor”的原文证据。

因此建议的新增顺序不是“把所有 feed 都接进来”，而是：

- **P0：MISP Galaxy + Malpedia**，解决 actor/alias 和 actor-malware 的候选解析，但不把 taxonomy 当事实真值。
- **P0：CISA/NCSC 等政府联合通告 + 官方厂商研究报告**，补直接 attribution claim、原始引用和证据强度。
- **P1：CIRCL MISP OSINT feed**，补事件、标签、IOC 和报告级关系，但必须逐事件保留 producer、distribution/TLP、时间与引用。
- **P1：ThreatFox / MalwareBazaar / URLhaus**，补 IOC-malware、sample、delivery infrastructure 与时间佐证；默认不提升为 actor attribution。
- **P2：APTnotes、CISA KEV、ThaiCERT/ETDA Threat Group Cards**，分别用于报告发现、漏洞在野利用和 taxonomy 补充，不应直接决定 actor label。

最重要的设计原则是：**新增来源应生成独立 Support，而不是覆盖已有 Fact；actor 与 IOC 同时出现在一个 report/feed 中仍然只是共现，除非来源明确给出 actor-to-IOC claim。**

## 评估维度

本文使用以下维度判断来源价值：

- **Identity**：actor 名称、别名、跨厂商命名及 cluster 边界。
- **Direct claim**：来源是否直接作出 actor/country/campaign attribution，而不是由查询词或 tag 推断。
- **Actor-malware/IOC**：是否明确给出 actor 使用 malware/IOC 的关系。
- **Infrastructure**：是否能独立佐证 domain/IP/URL/hash、sample、DNS、证书或投递关系。
- **Time/confidence**：是否有 observed time、发布/修订时间、置信度、producer 或措辞强度。
- **Replayability**：能否固定 commit、release、version、raw response 或内容 hash 重放。
- **Access/license**：是否公开、是否需要 key/注册、再分发限制是否清楚。

## 候选来源总表

| 来源 | Identity | 直接归因 | Actor-malware / IOC | 基础设施佐证 | 可重放性 | 归因价值判断 |
|---|---:|---:|---:|---:|---:|---|
| MISP Galaxy | 高 | 低 | 中 | 低 | 高（Git commit/release） | **P0 taxonomy resolver**；不是 event evidence |
| Malpedia | 高 | 低 | 高（actor-family/reference） | 中（sample/YARA） | 高（version endpoint） | **P0 actor-malware bridge** |
| CISA/NCSC/联合政府通告 | 中 | 高 | 高 | 高 | 中高（页面/PDF/附件/revision） | **P0 direct-claim evidence** |
| 官方厂商研究集合 | 高 | 高 | 高 | 高 | 中（网页会变，需 raw snapshot） | **P0/P1 direct-claim evidence** |
| CIRCL MISP OSINT feed | 中 | 中（取决于 event producer） | 中 | 高 | 高（event JSON + manifest） | **P1 structured event evidence** |
| ThreatFox | 低 | 低 | 中高（IOC-malware） | 高 | 中（API/bulk snapshot） | **P1 corroboration，不是 actor truth** |
| MalwareBazaar | 低 | 低 | 高（sample-family） | 中高 | 高（hash/batch/time） | **P1 malware/sample pivot** |
| URLhaus | 无 | 无 | 中（URL-payload） | 高 | 高（API/bulk） | **P1 delivery infrastructure** |
| APTnotes | 低 | 无（只是索引） | 低 | 低 | 中高（CSV/JSON/SHA-1） | **P2 report discovery only** |
| CISA KEV | 无 | 几乎无 | 无 | 无 | 高（JSON/CSV/schema） | **P2 vulnerability context only** |
| ThaiCERT/ETDA Threat Group Cards | 高 | 低 | 中 | 低 | 中（portal/PDF） | **P2 taxonomy cross-check** |

## 1. MISP Galaxy：最适合做多来源 Actor Resolver

### 能提供什么

MISP Galaxy 把一个大型概念表示为可附着到 MISP event/attribute 的 cluster，cluster 可以包含 key-value 元数据，并提供 threat actor、tool、ransomware、MITRE ATT&CK 等默认知识库。官方仓库明确说明 cluster 可以被覆盖、替换、更新、fork 和共享，因此它更像一个**可版本化 taxonomy/knowledge vocabulary**，而不是不可争议的 truth set（[MISP Galaxy README](https://github.com/MISP/misp-galaxy)）。

对本项目最有价值的是：

- threat-actor clusters 的 canonical value、synonyms、references、country/target 等 metadata；
- Microsoft Activity Group、MITRE Intrusion Set 等不同 namespace；
- cluster-to-cluster textual relations；
- `threat-actor-classification` 可区分 threat actor、activity group、campaign、operation、unknown，并允许数组表达来源之间对类型的分歧（[MISP Galaxy release notes](https://github.com/MISP/misp-galaxy/releases)）。

### 对 multi-actor mapping 的帮助

MISP Galaxy 应用于 **candidate generation**：

```text
raw adversary occurrence
  -> exact/normalized alias lookup
  -> zero / one / multiple candidate cluster UUIDs
```

- zero candidate：`unmapped`；
- one candidate：仍需保留 resolver version 和 reference；
- multiple candidates：`taxonomy_ambiguous`，不得 first-match 或 last-write-wins；
- 一个 raw string 明确列出多个 actor：保留有序 actor set，不能压缩成单个 `Event.apt`。

### 边界与接法

- **不能作为直接归因证据**：taxonomy 说明名称可能如何对应，不证明某个 OTX pulse 属于该 actor。
- 建议固定仓库 commit/release，保存原始 cluster JSON、commit SHA、cluster UUID、namespace 和匹配路径。
- `MITRE -> OTX` 查询仍只是 discovery provenance；`OTX.adversary -> MISP Galaxy` 才是 actor claim resolution。
- 仓库聚合了许多上游来源；每个 cluster/reference 的来源和适用许可应单独保留，不能假定所有聚合内容具有一个统一的数据许可。

**判断：P0。它直接减少 alias 冲突和 multi-actor 被错误单标签化的风险，但只改善 normalization/identity，不独立提高 attribution confidence。**

## 2. Malpedia：Actor-Malware Bridge，而不是 IOC 归因器

### 能提供什么

Malpedia 官方 API 无需注册即可：

- 搜索 actor/family 名称和 synonyms；
- 获取全部或单个 actor/family metadata；
- 获取某 actor/family 的 bibliography；
- 获取所有 reference 及其对应 actor/family；
- 导出当前 Malpedia 的 MISP Galaxy view；
- 获取 Malpedia version 的 commit number/date（[Malpedia REST API](https://malpedia.caad.fkie.fraunhofer.de/usage/api)）。

Malpedia 的 actor 页面明确说明：其 actor group mapping 来自 MISP Galaxy，并用 Malpedia 收录的 malware families 增强。因此它最适合建立：

```text
Actor candidate <-> Malware family <-> report references
```

而不是直接建立：

```text
Actor -> owns/uses every IOC carrying that malware label
```

### 与当前链路的接法

- OTX pulse 中出现 malware name、file hash 或 reference 时，先解析到 Malpedia family ID；
- 用 Malpedia 的 actor-family/reference 作为独立 Support；
- OTX hash 可再 pivot 到 Malpedia sample info（样本内容需要注册）或 MalwareBazaar；
- 如果 OTX actor claim 与 Malpedia actor-family mapping 一致，可提高“报告内部关系的一致性”，但不能因为同一 IOC 被某 family 检出就自动确认 actor。

### 时间、许可与重放

- `/api/get/version` 给出 commit number/date，适合冻结 snapshot；每次构建应保存 version response 和 raw actor/family/reference payload。
- 网站内容以 [CC BY-NC-SA 3.0](https://malpedia.caad.fkie.fraunhofer.de/usage/tos) 发布；非公开材料一般按 TLP:AMBER 对待，且官方说明不保证数据正确。
- 因为是非商业共享许可，项目后续若公开发布派生数据或商业化，需要单独做 license review。

**判断：P0。它能显著改善 actor-malware relation 和 alias resolution，但不能单独解决 actor-IOC attribution。**

## 3. 政府联合通告：最高价值的直接 Attribution Evidence

### CISA Cybersecurity Advisories

CISA 对 Cybersecurity Advisory 的官方定义是：围绕具体问题的深入报告，通常包含 threat actor TTP、IOC 和 mitigation（[CISA Alerts & Advisories](https://www.cisa.gov/news-events/cybersecurity-advisories)）。部分通告提供 PDF、STIX 或 JSON/XML IOC 附件，并明确记录发布/修订日期、合作机构和 attribution 措辞。

例如 CISA/FBI 关于伊朗政府支持 actor 的通告明确区分了：

- CISA 在事件响应中直接观察到的行为；
- CISA/FBI 的 assessment；
- 第三方 reporting 的关联；
- 与具体行为对应的 IOC/TTP；
- ATT&CK version 和报告修订记录（[AA22-320A](https://www.cisa.gov/news-events/cybersecurity-advisories/aa22-320a)）。

这类数据能生成真正有证据等级的 Support：

```text
source agency + advisory ID + version + publication/revision time
  -> claim text/span
  -> actor/country/campaign candidate
  -> malware / CVE / IOC / TTP
  -> assessment wording (confirmed / assess / likely / suspected / associated)
```

2025 年的中国国家支持活动联合通告还明确提醒：Salt Typhoon、OPERATOR PANDA、RedMike、UNC5807、GhostEmperor 等行业名称与政府理解未必一一对应。这正说明 alias mapping 必须保存 `similar/overlap`，不能一律解释为 `same_actor`（[AA25-239A](https://www.cisa.gov/news-events/cybersecurity-advisories/aa25-239a)）。

### NCSC 及其他联合政府通告

英国 NCSC 维护官方 reports/advisories 集合，内容可直接指明 actor、行为和 IOC，例如 APT28 advisory（[NCSC Reports & Advisories](https://www.ncsc.gov.uk/section/keep-up-to-date/reports-advisories)）。应优先采集多机构共同签署的 advisory，因为 producer、分析措辞、技术附件和版本通常更明确；但“多机构共同发布”算一个联合 Support，不能虚增为多个独立来源。

### 接入方式

- 以 advisory ID/URL 为 document identity，保存 HTML、PDF 和 STIX/JSON/XML 附件的 raw snapshot 与 hash；
- 抽取每条 claim 的 text span、section、producer、publication/revision time、estimative language；
- 将明确绑定在 actor section/table 的 IOC 才投影为 actor-IOC claim；全局 IOC appendix 默认只先建 `report observes IOC`；
- 与 OTX 通过 report URL、IOC、hash、CVE、malware family 和 resolved actor candidate 做 overlap；
- 政府来源可以 corroborate 或 challenge OTX claim，但不能覆盖 OTX 原始 Support。

**判断：P0。它是当前最缺失的数据类型：可引用、带措辞强度、能关联 actor/TTP/malware/IOC 的直接 attribution evidence。**

## 4. 官方厂商报告集合：高价值，但必须保存“各厂商自己的视角”

### 候选集合

- [Microsoft Threat Actor Naming](https://learn.microsoft.com/en-us/unified-secops/microsoft-threat-actor-naming)：提供公开 actor 名称、类别/来源、旧名称及其他厂商名称。Microsoft 明确说 `Storm` 等 development group 是在身份/来源达到高置信前用于跟踪离散活动的临时 cluster，因此不能把每个 vendor name 都当作稳定组织实体。
- [Microsoft Security Blog](https://www.microsoft.com/en-us/security/blog/topic/threat-intelligence/)：公开 campaign、actor、malware、IOC 和 TTP 研究；其 naming 页面可作为 Microsoft namespace resolver。
- [Google Threat Intelligence / Mandiant Blog](https://cloud.google.com/blog/topics/threat-intelligence)：官方集合带 RSS，包含 frontline investigation 和 human-curated actor analysis。公开文章常能提供 UNC/APT、malware、IOC、时间线和 assessment wording。
- [NCSC Reports & Advisories](https://www.ncsc.gov.uk/section/keep-up-to-date/reports-advisories)：虽然属于政府来源，采集方式与厂商 report corpus 类似，可共用 document/claim parser。

### 为什么不能简单合并 actor 名称

厂商命名代表各自 telemetry 和分析边界。Microsoft 官方页面提供“other names”，但 Google/Mandiant 的 UNC cluster、Microsoft Storm cluster、MITRE group 可能只是部分 overlap。数据模型至少应支持：

```text
same-as
overlaps-with
subcluster-of
supersedes
possibly-related
vendor-tracks-as
```

每一条 mapping 必须有 producer、发布时间、原始措辞和 reference。跨厂商两条相同结论可作为两个 Support，但如果一篇报告只是引用另一篇，需标记 derived-from，避免把转述当独立 corroboration。

### 许可与重放风险

- 公开可读不等于允许整库再分发；默认保存内部 raw snapshot、URL、hash 和必要短 span，不对外重新发布全文。
- HTML 会更新或下线；采集时保存 retrieval time、HTTP metadata、content hash、页面/PDF，以及文章内 downloadable IOC。
- APTnotes 可帮助发现报告，但最终 Evidence 必须引用报告发布机构的原始 URL/PDF，而不是 APTnotes/Box 镜像。

**判断：P0/P1。对 attribution quality 的提升可能最大，但 parser、许可、版本化和引用链成本也最高；应先做少量高质量报告的 tracer bullet。**

## 5. CIRCL MISP OSINT Feed：结构化事件补充，质量需逐 Event 判断

CIRCL 公开 MISP OSINT feed 以逐 event JSON 暴露数据，并提供 `manifest.json` 和 `hashes.csv`（[CIRCL MISP OSINT feed](https://www.circl.lu/doc/misp/feed-osint/)）。MISP 本身支持 event、attribute、object、galaxy、sighting、distribution 和 STIX import/export，官方还强调其标准格式向后兼容（[MISP project](https://github.com/MISP/MISP)）。

### 可利用信息

- Event metadata：UUID、info、date/timestamp、Org/Orgc、published 状态、distribution；
- Attributes/Objects：IOC、comment、first/last seen 等；
- Tags/Galaxy：actor、malware、campaign、TLP/taxonomy；
- Object/reference：可以表达比扁平 IOC feed 更具体的关系。

### 归因边界

- `misp-galaxy:threat-actor=...` tag 是 event producer 的标签/claim，不自动等于已验证 truth；
- event 中 actor tag 与全部 attributes 同现，默认仍只能推导 `event claims actor` 与 `event observes IOC`；
- 只有明确 object/reference 或 report text 把 actor 与 IOC/malware 绑定时，才生成强关系；
- feed 聚合多个 producer，可靠性不能统一打一个固定分数，应按 Orgc、引用、distribution/TLP、时间和 corroboration 单独建 Support。

### 接法与重放

- 固定一次 manifest/hash snapshot，只抓 manifest 指向的 event JSON；
- 保存 event UUID、timestamp、raw hash、producer、distribution/TLP；
- 用 IOC 与现有 OTX/VT 做 overlap，用 galaxy cluster UUID 与 MISP resolver 对齐；
- 记录删除/修改，而不是静默覆盖旧 event version。

**判断：P1。结构和可重放性优秀，但归因质量高度异质；必须先做 producer-aware audit。**

## 6. abuse.ch：强 Corroboration，弱 Actor Attribution

### 6.1 ThreatFox

ThreatFox API 可按 IOC、hash、tag、malware family 查询；记录包含 malware label、confidence、reporter、reference、tag、`is_compromised` 等。提交 IOC 时 malware family 是必填项，malware labels 来自 Malpedia；API 还区分 compromised asset 与专用恶意基础设施（[ThreatFox Community API](https://threatfox.abuse.ch/api/)）。

对本项目最有用的是：

```text
OTX/VT IOC
  -> ThreatFox exact IOC lookup
  -> malware family + first/last seen + reporter + confidence + reference
```

但 `tags` 中出现 TA505 等 actor-like label 仍只是社区提交 metadata；除非 reference 原文明确支持，否则不能当 actor claim。confidence 是提交记录的 confidence，也不能直接等同于 actor attribution confidence。

### 6.2 MalwareBazaar

MalwareBazaar 可按 hash、signature、tag、imphash、TLSH、YARA、code-signing certificate 等查询，并提供 hourly/daily batch。返回数据包含 sample hash、first/last seen、signature、reporter、tags、相似性 hash 和 references/context（[MalwareBazaar Community API](https://bazaar.abuse.ch/api/)）。官方说明该平台只接收 confirmed/vetted malware，不是多引擎 benign/malicious scanner（[MalwareBazaar FAQ](https://bazaar.abuse.ch/faq/)）。

接入价值：

- OTX hash -> sample/family/reference；
- OTX/VT domain/URL -> URLhaus payload hash -> MalwareBazaar sample；
- sample similarity 可发现同 family/campaign 的候选，但 similarity 不等于 same actor；
- code-signing certificate、dropped-by/dropping context 可补基础设施/投递链证据。

### 6.3 URLhaus

URLhaus 是 abuse.ch/Spamhaus 运营的恶意 URL 共享平台，提供 URL 与 malware sample 查询和 bulk API（[URLhaus API](https://urlhaus.abuse.ch/api/)、[About](https://urlhaus.abuse.ch/about/)）。它最适合补：

```text
malicious URL -> payload hash -> malware family/sample
```

它几乎不提供可靠 actor identity；用途是验证 OTX URL 是否承载恶意 payload、建立 delivery infrastructure 和时间窗口。

### 访问、许可与独立性

- Community APIs 需要免费 Auth-Key，并受 fair-use 和 Terms of Use 约束；商业/营利用途可能需要增强版订阅。
- 建议保存 API query、retrieval time、raw response/hash；批量数据固定 batch time。
- ThreatFox、MalwareBazaar 和 Malpedia 之间存在显式标签依赖，VirusTotal 也可能吸收相同社区信号；这些不能简单计为完全独立的多个 votes。

**判断：P1。能显著提高 IOC/malware/infrastructure evidence quality 和 freshness，但对 actor attribution 只能提供间接支持。**

## 7. APTnotes：报告发现入口，不是 Mapping 数据集

APTnotes 官方 data repository 的定位是公开 APT campaign/activity/software 报告与博客的索引。CSV/JSON 仅保存 filename、title、source、Box link、SHA-1、date、year；报告被镜像到 Box 以防原链接消失（[APTnotes data](https://github.com/aptnotes/data)）。

### 能做什么

- 按 vendor/date/title 发现历史报告；
- 用 SHA-1 做报告文件去重和重放；
- 扩充当前 PDF corpus，尤其补历史 APT report coverage。

### 不能做什么

- 没有结构化 actor field、alias relation、claim span、IOC relation 或 confidence；
- title 中的 actor 名不能直接投影成 report attribution；
- Box 镜像不是原发布机构，最终 citation 应优先回到 vendor/government 原文；
- 仓库页面未显示明确统一的数据许可，且各报告版权属于原作者/厂商；不应默认允许全文再分发。

**判断：P2 / exploratory corpus discovery。它改善 source coverage，但不直接改善 normalization 或 attribution reliability。**

## 8. CISA KEV：验证“在野利用”，不能识别“谁在利用”

CISA KEV 是官方认定已在野利用漏洞的 authoritative catalog，提供 CSV、JSON 和 JSON Schema，并包含 date added、due date、vendor/product、ransomware campaign flag 等字段（[CISA KEV Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)）。

与现有链路的合理接法是：

```text
OTX/CISA/vendor report mentions CVE
  -> KEV confirms exploited-in-the-wild status and date
```

它不能单独支持：

```text
CVE -> specific actor
```

即使某 CVE 出现在 actor report 中，KEV 也只是漏洞活动性 Support，不是 actor identity Support。`knownRansomwareCampaignUse` 也只是 ransomware campaign 层面，不是具体 actor 映射。

**判断：P2。适合 vulnerability context、时间和 report quality enrichment；对 actor attribution 的边际价值低。**

## 9. ThaiCERT/ETDA Threat Group Cards：额外 Taxonomy Cross-check

泰国 ETDA/ThaiCERT 的 Threat Group Cards portal 旨在汇总 threat group profile、别名、工具、活动时间和来源报告；官方说明其目标是帮助分析人员理解潜在对手、既往行动和 TTP，并保留一个较旧的 TLP:WHITE PDF 版本（[Threat Group Cards portal](https://apt.etda.or.th/)、[v2.0 PDF](https://apt.etda.or.th/img/Threat_Group_Cards_v2.0.pdf)）。

价值：

- 补充 MISP/MITRE 未覆盖或命名不同的 actor/tool 候选；
- 对 alias、active period、tool association 做第三方 cross-check；
- 每个 relation 仍需回到 portal 引用的原报告。

限制：

- portal 是二次聚合 taxonomy，不是事件级直接 observation；
- PDF 官方已标记 outdated，不能作为当前状态；
- 未确认稳定 API 和明确机器可读 snapshot/license，自动化及重放成本高于 MISP/Malpedia。

**判断：P2。适合 resolver 人工审核和 coverage gap 分析，不应进入自动高置信 mapping 的主路径。**

## 推荐的数据模型与证据规则

新增来源不应继续写单一 `Event.apt`，而应落到以下独立对象：

```text
ActorIdentity
  canonical_id, namespace, canonical_name

ActorNameAssertion
  raw_label, producer, candidate_actor_ids[], relation_type,
  taxonomy_version, source_ref, valid_time

AttributionClaim
  subject(event/campaign/malware/IOC), predicate, actor_candidates[],
  claim_text/span, estimative_language, producer, published/revised_at

Observation
  indicator/sample/infrastructure, first_seen, last_seen, source

Support
  fact_or_claim_id, evidence_id, raw_ref, source_independence,
  extraction_version, confidence_basis
```

### 必须执行的 guardrails

1. `query_actor` 永远只是 OTX discovery provenance。
2. `event has actor tag` + `event has IOC` 不自动生成 `actor uses IOC`。
3. Taxonomy alias match 生成 candidate，不生成 attribution fact。
4. Multi-actor claim 保留 actor set、顺序、原始 span 和关系类型。
5. `same-as`、`overlaps-with`、`subcluster-of` 不得混成一个 alias relation。
6. 每条 claim 保存来源自己的措辞：`confirmed`、`assess`、`likely`、`suspected`、`associated` 不能统一压成一个固定 confidence。
7. 同一上游经 OTX、VT、ThreatFox/MalwareBazaar 转述时标记 provenance dependency，不能算多个独立 corroborations。
8. 所有 mutable API/page 必须保存 raw snapshot、retrieval time、content hash 和 source version/revision。

## 推荐的最小 Tracer Bullet

不要立即全量接所有来源。先选择 10–20 个包含 single、multi、alias ambiguity、unmapped 的 OTX pulses，完成一条小而完整的证据链：

```text
OTX raw adversary occurrence
  -> MISP Galaxy + Malpedia candidate resolution
  -> official CISA/NCSC/vendor report claim retrieval
  -> OTX IOC overlap
  -> ThreatFox/MalwareBazaar/URLhaus/VT corroboration
  -> Fact + multiple Supports + citation trace
```

验收指标应是：

- actor occurrence resolution coverage；
- multi-actor preservation rate；
- taxonomy ambiguity/unmapped rate；
- 有 direct original-report support 的 attribution claim 比例；
- actor-IOC relation 中有明确 per-relation citation 的比例；
- source dependency 去重后的独立 Support 数；
- 从 Fact 回溯到原始 claim span/raw response 的成功率；
- 版本冻结后重放结果的一致率。

## 优先级建议

- **P0：固定 MISP Galaxy 与 Malpedia snapshot**，实现 `alias -> set[candidate]`，输出 single/multi/ambiguous/unmapped，绝不 first-match。
- **P0：实现 government/vendor report claim schema 和一个 CISA advisory parser**，保留原文 span、assessment wording、版本和附件关系。
- **P0：把 legacy `Event.apt` 降为 consumer projection**；仅在 reviewed、唯一 resolved、vocabulary-compatible 时写入。
- **P1：对 CIRCL MISP OSINT 做小样本 producer-aware audit**，确认 galaxy tag、event attribute、object relation 能否可靠映射到 Support。
- **P1：用现有 OTX IOC 做 ThreatFox/MalwareBazaar/URLhaus 小规模 exact lookup**，量化 IOC-malware、URL-payload 和时间 overlap；不要作为 actor label vote。
- **P1：建立 provenance dependency**，识别 Malpedia labels、abuse.ch、VT 和引用报告之间的派生关系，防止重复计票。
- **P2：用 APTnotes 扩充历史报告发现，用 KEV 补 exploited-in-the-wild context，用 ETDA Cards 补 taxonomy gap**；三者都不进入自动 actor truth 路径。

